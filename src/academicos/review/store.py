"""Historial local de revisiones de proyectos (spec 006 sobre las convenciones de la 003).

Base SQLite aparte (`revisiones.sqlite3`) en la carpeta de salida: no toca el esquema del
catálogo de conversión (CAT-12 rechaza versiones ajenas). Guarda por ejecución y estudiante la
nota, el nivel por criterio, los casos y la similitud; nunca borra ejecuciones anteriores.
"""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

APPLICATION_ID = 0x41435256   # "ACRV"
SCHEMA_VERSION = 1
NOMBRE = "revisiones.sqlite3"

SCHEMA = """
BEGIN;
CREATE TABLE review_runs (id TEXT PRIMARY KEY, rubrica TEXT NOT NULL, rubrica_sha TEXT NOT NULL,
  curso TEXT, umbral REAL, started_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE review_students (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES review_runs(id),
  estudiante TEXT NOT NULL, proyecto TEXT, fecha TEXT, nota REAL, maximo_posible REAL,
  completa INTEGER, tope_aplicado INTEGER, compilacion TEXT, intacto INTEGER, errores TEXT,
  manual TEXT, resultado TEXT NOT NULL, UNIQUE(run_id, estudiante));
CREATE TABLE review_levels (student_id INTEGER NOT NULL REFERENCES review_students(id),
  criterio TEXT NOT NULL, nivel TEXT, nota REAL, estado TEXT, bloqueado_por TEXT, sin_verificar TEXT,
  requiere_confirmacion TEXT, PRIMARY KEY(student_id, criterio));
CREATE TABLE review_cases (student_id INTEGER NOT NULL REFERENCES review_students(id),
  caso TEXT NOT NULL, estado TEXT NOT NULL, PRIMARY KEY(student_id, caso));
CREATE TABLE review_similarity (run_id TEXT NOT NULL REFERENCES review_runs(id),
  a TEXT NOT NULL, b TEXT NOT NULL, literal REAL, normalizada REAL, puntaje REAL, fragmentos TEXT,
  PRIMARY KEY(run_id, a, b));
PRAGMA application_id = 1094931030;
PRAGMA user_version = 1;
COMMIT;
"""


def _j(x):
    return json.dumps(x, ensure_ascii=False)


class ReviewStore:
    def __init__(self, carpeta):
        carpeta = Path(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(carpeta / NOMBRE)
        self.db.row_factory = sqlite3.Row
        try:
            app = self.db.execute("PRAGMA application_id").fetchone()[0]
            ver = self.db.execute("PRAGMA user_version").fetchone()[0]
            tablas = self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if not tablas and app == 0 and ver == 0:
                self.db.executescript(SCHEMA)
            elif app != APPLICATION_ID or ver != SCHEMA_VERSION:
                raise ValueError("El historial de revisiones pertenece a otra aplicación o usa un esquema no soportado")
            self.db.execute("PRAGMA foreign_keys = ON")
            self.db.execute("PRAGMA synchronous = FULL")
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def start_run(self, rubrica_path, rubrica_nombre, curso=None, umbral=None):
        rid = uuid4().hex
        sha = hashlib.sha256(Path(rubrica_path).read_bytes()).hexdigest()
        with self.db:
            self.db.execute("INSERT INTO review_runs(id,rubrica,rubrica_sha,curso,umbral) VALUES(?,?,?,?,?)",
                            (rid, rubrica_nombre, sha, str(curso) if curso else None, umbral))
        return rid

    def add_student(self, run_id, r):
        k = r.get("calificacion") or {}
        limpio = {a: b for a, b in r.items() if not a.startswith("_")}
        with self.db:
            cur = self.db.execute(
                "INSERT OR REPLACE INTO review_students(run_id,estudiante,proyecto,fecha,nota,maximo_posible,"
                "completa,tope_aplicado,compilacion,intacto,errores,manual,resultado) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, r["estudiante"], r.get("proyecto"), r.get("fecha"), k.get("nota_sugerida"),
                 k.get("maximo_posible"), k.get("completo"), k.get("tope_aplicado"),
                 (r.get("compilacion") or {}).get("status"), (r.get("integridad") or {}).get("intacto"),
                 _j(r.get("errores", [])), _j(r.get("manual")) if r.get("manual") else None, _j(limpio)))
            sid = cur.lastrowid
            for n in r.get("niveles", []):
                self.db.execute("INSERT OR REPLACE INTO review_levels VALUES(?,?,?,?,?,?,?,?)",
                                (sid, n["id"], n["nivel"], n["nota"], n["estado"], _j(n["bloqueado_por"]),
                                 _j(n["sin_verificar"]), n.get("requiere_confirmacion")))
            for c in r.get("casos", []):
                self.db.execute("INSERT OR REPLACE INTO review_cases VALUES(?,?,?)", (sid, c["id"], c["estado"]))
        return sid

    def add_similarity(self, run_id, sim):
        with self.db:
            for p in sim["pares"]:
                self.db.execute("INSERT OR REPLACE INTO review_similarity VALUES(?,?,?,?,?,?,?)",
                                (run_id, p["a"], p["b"], p["literal"], p["normalizada"], p["puntaje"],
                                 _j(p["fragmentos"])))


def historial(carpeta, estudiante=None):
    """Notas y niveles por ejecución, más recientes primero. Solo lectura."""
    ruta = Path(carpeta).expanduser().resolve() / NOMBRE
    if not ruta.is_file():
        raise ValueError("No hay historial de revisiones en esta carpeta")
    db = sqlite3.connect(ruta.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    with closing(db):
        if (db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID or
                db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION):
            raise ValueError("Historial o esquema no soportado")
        q = ("SELECT s.id, s.estudiante, s.nota, s.maximo_posible, s.completa, s.compilacion, "
             "r.started_at, r.rubrica, r.rubrica_sha FROM review_students s JOIN review_runs r ON r.id=s.run_id")
        args = ()
        if estudiante:
            q += " WHERE s.estudiante=?"
            args = (estudiante,)
        out = []
        for row in db.execute(q + " ORDER BY r.started_at DESC, s.id DESC", args):
            d = dict(row)
            d["niveles"] = {x["criterio"]: x["nivel"] for x in db.execute(
                "SELECT criterio,nivel FROM review_levels WHERE student_id=?", (d.pop("id"),))}
            out.append(d)
        return out
