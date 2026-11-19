"""Pruebas de la revisión de proyectos distribuidos (spec 007)."""
import json
import subprocess
import zipfile
from argparse import Namespace
from pathlib import Path

import pytest

from academicos.review.stack import ejecucion as ej
from academicos.review.stack.cli import run_stack
from academicos.review.stack.equipos import agrupar, limpiar_nombre
from academicos.review.stack.evaluar import evaluar_equipo
from academicos.review.stack.proyecto import analizar_informe, cargar_proyecto, extraer, parse_compose, sin_proyecto
from academicos.review.stack.reporte import csv_consolidado, markdown_equipo, nota_final, recomendaciones
from academicos.review.stack.rubrica import StackRubricError, load_stack_rubric, parse_stack_rubric
from academicos.review.stack.senales import evaluar_rubrica

RUBRICA = Path(__file__).resolve().parent.parent / "rubricas" / "interoperabilidad-salud.yaml"

COMPOSE = """
services:
  db-sede1: {image: "postgres:16", healthcheck: {test: [CMD, pg_isready]}}
  db-sede2: {image: "postgres:16"}
  db-sede3: {image: "postgres:16"}
  hapi: {image: "hapiproject/hapi:v7"}
  api:
    build: .
    ports: ["8000:8000"]
    healthcheck: {test: [CMD, curl, localhost:8000/health]}
"""
MAIN = '''
from fastapi import Depends, FastAPI, HTTPException
app = FastAPI()
@app.get("/health")
def health(): return {"ok": True}
@app.get("/metrics")
def metrics(): return "latencia_ms 1\\nfallidos 0"
def require_role(*roles): ...
# roles: admisionista, medico, auditor; 403 forbidden si no coincide; jwt bearer
def normalizar(row):
    return {"resourceType": "Patient"}, {"resourceType": "Encounter"}, "Observation", "Condition", "Bundle", "ICD-10", "loinc"
def hsb(msg):  # MSH| ADT^A01 ORU^R01 OBX|
    if invalid: raise HTTPException(status_code=422)
    queue = []; retry = 3; backoff = 2; dead_letter = []; idempotente = hashlib.sha256(msg)
    for sede in sedes: pass   # enrutamiento sede1
def auditoria(prev_hash): ...   # cadena de hash
'''
RESUMEN = " ".join(["palabra"] * 180)
INFORME = f"""# Informe
Resumen
{RESUMEN}
Palabras clave: a, b
Introducción
Objetivo general: x. Objetivos específicos: y.
Marco teórico: CAP y ACID, idempotencia.
Estado del arte. Solución propuesta. Modelado UML. Proceso de desarrollo. Diseño de interfaces.
Prototipo. Viabilidad técnica: escalabilidad, Ley 1581, TLS. Interoperabilidad. Resultados: latencia.
Conclusiones. Anexos: bitácora.
Referencias
""" + "\n".join(f"Autor{i} ({2020 + i % 5}). Título." for i in range(9))


def proyecto(raiz, con_compose=True, con_informe=True):
    raiz.mkdir(parents=True, exist_ok=True)
    (raiz / "app").mkdir(exist_ok=True)
    (raiz / "app" / "main.py").write_text(MAIN, encoding="utf-8")
    (raiz / "README.md").write_text("docker compose up\nUsuarios de prueba: medico\nDatos sintéticos", encoding="utf-8")
    (raiz / ".gitignore").write_text(".env\n", encoding="utf-8")
    (raiz / "docs").mkdir(exist_ok=True)
    for n in ("casos-de-uso.png", "secuencia.svg", "clases.png", "estados.png", "arquitectura.png", "mapeo.md"):
        (raiz / "docs" / n).write_text("x", encoding="utf-8")
    (raiz / "ejemplos").mkdir(exist_ok=True)
    (raiz / "ejemplos" / "adt_invalido.hl7").write_text("MSH|", encoding="utf-8")
    (raiz / "ejemplos" / "adt_duplicado.hl7").write_text("MSH|", encoding="utf-8")
    if con_compose:
        (raiz / "docker-compose.yml").write_text(COMPOSE, encoding="utf-8")
    if con_informe:
        (raiz / "informe.md").write_text(INFORME, encoding="utf-8")
    return raiz


# --- rúbrica ------------------------------------------------------------------------------

def test_rubrica_real_suma_5():
    r = load_stack_rubric(RUBRICA)
    assert round(sum(c.max for c in r.criterios), 2) == 5.0
    assert len(r.criterios) == 13 and r.bonus_max == 0.25 and len(r.bonus) == 4


def test_rubrica_invalida():
    base = {"nombre": "x", "escala": {"max": 1.0}, "criterios": [
        {"id": "a", "max": 0.5, "senales": [{"id": "s", "tipo": "manual"}]}]}
    with pytest.raises(StackRubricError, match="suman"):
        parse_stack_rubric(base)
    base["criterios"][0]["max"] = 1.0
    base["criterios"][0]["senales"][0]["tipo"] = "magia"
    with pytest.raises(StackRubricError, match="tipo inválido"):
        parse_stack_rubric(base)
    base["criterios"][0]["senales"] = [{"id": "s", "tipo": "contenido"}]
    with pytest.raises(StackRubricError, match="patron"):
        parse_stack_rubric(base)


# --- proyecto y señales -------------------------------------------------------------------

def test_proyecto_completo_cumple_senales(tmp_path):
    proy = cargar_proyecto(proyecto(tmp_path / "p"))
    res = evaluar_rubrica(load_stack_rubric(RUBRICA), proy)
    por = {c["id"]: c for c in res["criterios"]}
    est = {s["id"]: s["estado"] for c in res["criterios"] for s in c["senales"]}
    assert est["uml_casos_uso"] and est["uml_secuencia"] and est["uml_estados"] and est["mapeo_campos"]
    assert est["tres_sedes"] is True and est["healthchecks"] is True
    assert est["hl7_adt"] and est["idempotencia"] and est["mensajes_muertos"] and est["ejemplo_duplicado"]
    assert est["resumen_150_250"] is True and est["referencias_8"] is True and est["plantilla_completa"] is True
    assert por["uml"]["estado"] == "excelente"
    assert est["ejec_health"] is None and est["ejec_levanta"] is None      # sin Docker: sin verificar
    assert est["etiqueta_v10"] is None                                       # sin .git: sin verificar
    assert por["sustentacion"]["nota"] is None and por["sustentacion"]["estado"] == "pendiente docente"
    assert res["pendiente_docente"] == 0.15
    assert res["maximo_posible"] > res["parcial"]


def test_sin_compose_ni_informe_es_no_cumplido(tmp_path):
    proy = cargar_proyecto(proyecto(tmp_path / "p", con_compose=False, con_informe=False))
    est = {s["id"]: s["estado"] for c in evaluar_rubrica(load_stack_rubric(RUBRICA), proy)["criterios"] for s in c["senales"]}
    assert est["tres_sedes"] is False and est["compose_existe"] is False and est["informe_existe"] is False


def test_sin_proyecto_y_enlace_github(tmp_path):
    d = tmp_path / "solo"
    d.mkdir()
    (d / "parcial").write_text("https://github.com/equipo/historia-clinica", encoding="utf-8")
    proy = cargar_proyecto(d)
    assert sin_proyecto(proy) and proy.enlaces == ["https://github.com/equipo/historia-clinica"]


def test_informe_ilegible_deja_sin_verificar(tmp_path, monkeypatch):
    d = proyecto(tmp_path / "p", con_informe=False)
    (d / "informe.pdf").write_bytes(b"%PDF-1.4 roto")
    monkeypatch.setattr("academicos.review.stack.proyecto._texto_pdf", lambda p: None)
    est = {s["id"]: s["estado"] for c in evaluar_rubrica(load_stack_rubric(RUBRICA), cargar_proyecto(d))["criterios"]
           for s in c["senales"]}
    assert est["informe_existe"] is True and est["resumen_150_250"] is None and est["referencias_8"] is None


def test_analizar_informe_resumen_y_referencias():
    a = analizar_informe(INFORME)
    assert a["resumen_palabras"] == 180 and a["referencias"] == 9 and a["secciones"] >= 14


def test_docx_se_lee(tmp_path):
    d = proyecto(tmp_path / "p", con_informe=False)
    xml = "<w:document><w:body>" + "".join(f"<w:p><w:r><w:t>{l}</w:t></w:r></w:p>" for l in INFORME.splitlines()) + "</w:body></w:document>"
    with zipfile.ZipFile(d / "Informe_final.docx", "w") as z:
        z.writestr("word/document.xml", xml)
    inf = cargar_proyecto(d).informe
    assert inf["archivo"] == "Informe_final.docx" and inf["resumen_palabras"] == 180


def test_etiqueta_v10_desde_git(tmp_path):
    d = proyecto(tmp_path / "p")
    (d / ".git" / "refs" / "tags").mkdir(parents=True)
    (d / ".git" / "refs" / "tags" / "v1.0").write_text("abc", encoding="utf-8")
    est = {s["id"]: s["estado"] for c in evaluar_rubrica(load_stack_rubric(RUBRICA), cargar_proyecto(d))["criterios"]
           for s in c["senales"]}
    assert est["etiqueta_v10"] is True


# --- extracción segura --------------------------------------------------------------------

def test_extraer_zip_anidado_y_zip_slip(tmp_path):
    ent = tmp_path / "ent"
    ent.mkdir()
    interno = tmp_path / "interno.zip"
    with zipfile.ZipFile(interno, "w") as z:
        z.writestr("proy/docker-compose.yml", COMPOSE)
        z.writestr("proy/node_modules/x/index.js", "basura")
    with zipfile.ZipFile(ent / "entrega.zip", "w") as z:
        z.write(interno, "interno.zip")
        z.writestr("../../escape.txt", "no debe salir")
        z.writestr("/abs.txt", "no")
    destino = tmp_path / "work"
    extraer([ent], destino)
    proy = cargar_proyecto(destino)
    assert proy.compose and len(proy.compose["servicios"]) == 5
    assert not any("node_modules" in a for a in proy.archivos)
    assert not (tmp_path / "escape.txt").exists() and not (tmp_path / "abs.txt").exists()


def test_rar_sin_herramienta_avisa(tmp_path, monkeypatch):
    ent = tmp_path / "ent"
    ent.mkdir()
    (ent / "x.rar").write_bytes(b"Rar!")
    monkeypatch.setattr("academicos.review.stack.proyecto.shutil.which", lambda n: None)
    avisos = extraer([ent], tmp_path / "w")
    assert any("no se pudo extraer" in a for a in avisos)


# --- equipos ------------------------------------------------------------------------------

def test_agrupar_por_contenido_y_yaml(tmp_path):
    for n, contenido in (("ANA PEREZ_1_assignsubmission_file", "igual"), ("LUIS GOMEZ_2_assignsubmission_file", "igual"),
                         ("MARIA RUIZ_3_assignsubmission_file", "informe"), ("JOSE DIAZ_4_assignsubmission_file", "codigo")):
        d = tmp_path / n
        d.mkdir()
        (d / "a.txt").write_text(contenido, encoding="utf-8")
    carpetas = sorted(p for p in tmp_path.iterdir())
    eq = agrupar(carpetas)
    nombres = {e.nombre: e for e in eq}
    assert "Ana Perez + Luis Gomez" in nombres and len(nombres["Ana Perez + Luis Gomez"].carpetas) == 1
    assert "mismos archivos" in nombres["Ana Perez + Luis Gomez"].razon and len(eq) == 3
    y = tmp_path / "equipos.yaml"
    y.write_text("equipos:\n  - [maria ruiz, jose diaz]\n", encoding="utf-8")
    eq2 = agrupar(carpetas, y)
    union = [e for e in eq2 if len(e.miembros) == 2 and "Maria" in e.nombre][0]
    assert len(union.carpetas) == 2 and "equipos.yaml" in union.razon


def test_limpiar_nombre():
    assert limpiar_nombre(Path("/x/JUAN CARLOS OYOLA HERNANDEZ_197907_assignsubmission_file")) == "Juan Carlos Oyola Hernandez"


# --- ejecución con Docker simulado --------------------------------------------------------

def _runner(salidas, http=lambda url: 200, disponible=True):
    llamadas = []

    def ejecutar(cmd, cwd, timeout):
        llamadas.append(cmd)
        if "ps" in cmd:
            return 0, salidas.get("ps", ""), ""
        return salidas.get("codigo", 0), "", salidas.get("err", "")
    return ej.ComposeRunner(ejecutar=ejecutar, http=http, disponible=disponible), llamadas


PS = json.dumps({"Service": "api", "Publishers": [{"PublishedPort": 8000}]})


def test_ejecucion_ok_y_siempre_baja(tmp_path):
    proy = cargar_proyecto(proyecto(tmp_path / "p"))
    r, llamadas = _runner({"ps": PS})
    res = r.evaluar(tmp_path / "p", proy, 60)
    assert res["levanta"] and res["health"] and res["metrics"]
    assert "down" in llamadas[-1] and "-v" in llamadas[-1]


def test_ejecucion_health_falla(tmp_path):
    proy = cargar_proyecto(proyecto(tmp_path / "p"))
    r, _ = _runner({"ps": PS}, http=lambda url: 200 if url.endswith("/health") else 404)
    res = r.evaluar(tmp_path / "p", proy, 60)
    assert res["health"] is True and res["metrics"] is False


def test_ejecucion_up_falla_y_baja(tmp_path):
    proy = cargar_proyecto(proyecto(tmp_path / "p"))
    r, llamadas = _runner({"codigo": 1, "err": "build error"})
    res = r.evaluar(tmp_path / "p", proy, 60)
    assert res["levanta"] is False and "build error" in res["detalle"]["levanta"]
    assert "down" in llamadas[-1]


def test_sin_docker_queda_sin_verificar(tmp_path):
    proy = cargar_proyecto(proyecto(tmp_path / "p"))
    r, llamadas = _runner({}, disponible=False)
    res = r.evaluar(tmp_path / "p", proy, 60)
    assert res["levanta"] is None and not llamadas


def test_compose_riesgoso_no_se_ejecuta(tmp_path):
    d = proyecto(tmp_path / "p")
    (d / "docker-compose.yml").write_text(
        "services:\n  x:\n    image: a\n    privileged: true\n    volumes: ['/var/run/docker.sock:/var/run/docker.sock', '/etc:/h']\n",
        encoding="utf-8")
    proy = cargar_proyecto(d)
    r, llamadas = _runner({})
    res = r.evaluar(d, proy, 60)
    assert res["levanta"] is None and "seguridad" in res["motivo"] and not llamadas
    assert any("docker.sock" in x for x in ej.riesgos(proy.compose))


def test_parse_compose_puertos_con_variables():
    c = parse_compose('services:\n  a: {build: ., ports: ["${PORT:-9000}:8000", "127.0.0.1:8080:80"]}')
    assert c["servicios"]["a"]["puertos"] == [9000, 8080]


# --- equipo, reportes y CLI ---------------------------------------------------------------

def _equipo_dir(curso, nombre, **kw):
    d = curso / f"{nombre}_1_assignsubmission_file"
    proyecto(d, **kw)
    return d


def test_evaluar_equipo_y_reportes(tmp_path):
    curso = tmp_path / "curso"
    d = _equipo_dir(curso, "ANA PEREZ")
    eq = agrupar([d])[0]
    r = evaluar_equipo(load_stack_rubric(RUBRICA), eq, tmp_path / "w")
    assert not (tmp_path / "w" / "ana-perez").exists()               # limpia lo extraído
    md = markdown_equipo(r, load_stack_rubric(RUBRICA))
    assert "## Criterios" in md and "Sustentación individual" in md and "Sin verificar" in md
    assert nota_final(r) == r["nota"] and 0 < r["nota"] <= 5
    rub = load_stack_rubric(RUBRICA)
    rows = csv_consolidado([r], rub).splitlines()
    assert rows[0].startswith("estudiante,equipo,nota_sugerida") and len(rows) == 2
    r["sancion"] = {"nota": 0.0, "motivo": "m", "parejas": ["x"]}
    assert nota_final(r) == 0.0 and "0.0 por similitud" in markdown_equipo(r, rub)


def test_recomendaciones_ordena_por_nota_en_juego(tmp_path):
    curso = tmp_path / "curso"
    d = _equipo_dir(curso, "ANA PEREZ", con_compose=False, con_informe=False)
    r = evaluar_equipo(load_stack_rubric(RUBRICA), agrupar([d])[0], tmp_path / "w")
    rec = recomendaciones(r)
    assert rec and any("docker-compose" in f for _, fs in rec for f in fs)


def test_cli_curso_sin_docker_con_sancion(tmp_path):
    curso = tmp_path / "curso"
    a = _equipo_dir(curso, "ANA PEREZ")
    b = _equipo_dir(curso, "BETO RUIZ")
    (b / "README.md").write_text("otro readme distinto", encoding="utf-8")   # mismo código, distinta huella de archivos
    c = _equipo_dir(curso, "CARLA DIAZ", con_compose=False)
    (c / "app" / "main.py").write_text("print('otro')\n" * 80 + "x = 1\n" * 60, encoding="utf-8")
    args = Namespace(rubrica=RUBRICA, curso=curso, salida=tmp_path / "rep", equipos=None, base=None, no_docker=True,
                     solo=[], umbral=0.8, sancion_similitud=1.0, excepto=[], trabajo=None, conservar=False)
    assert run_stack(args) == 0
    sal = tmp_path / "rep"
    assert (sal / "reporte_general.md").is_file() and (sal / "consolidado.csv").is_file() and (sal / "similitud.md").is_file()
    assert len(list((sal / "equipos").glob("*.md"))) == 3
    general = (sal / "reporte_general.md").read_text(encoding="utf-8")
    assert "Ana Perez" in general and "⚠" in general           # A y B comparten código: sanción
    filas = (sal / "consolidado.csv").read_text(encoding="utf-8").splitlines()
    assert any(f.startswith("Ana Perez,") and ",0.00," in f for f in filas)
    carla = [f.split(",") for f in filas if f.startswith("Carla Diaz,")][0]
    assert carla[2] != "0.00"


def test_cli_solo_y_error_sin_coincidencia(tmp_path):
    curso = tmp_path / "curso"
    _equipo_dir(curso, "ANA PEREZ")
    args = Namespace(rubrica=RUBRICA, curso=curso, salida=tmp_path / "rep", equipos=None, base=None, no_docker=True,
                     solo=["nadie"], umbral=0.8, sancion_similitud=None, excepto=[], trabajo=None, conservar=False)
    with pytest.raises(ValueError, match="--solo"):
        run_stack(args)


# --- alternativas (archivo o informe) e informe sin nombre típico -------------------------

def test_alternativa_en_informe_cumple_diagrama_sin_archivo(tmp_path):
    d = proyecto(tmp_path / "p")
    for f in (d / "docs").iterdir():
        f.unlink()
    (d / "informe.md").write_text(INFORME + "\nDiagrama de casos de uso. Diagrama de secuencia.\n", encoding="utf-8")
    est = {s["id"]: s["estado"] for c in evaluar_rubrica(load_stack_rubric(RUBRICA), cargar_proyecto(d))["criterios"]
           for s in c["senales"]}
    assert est["uml_casos_uso"] is True and est["uml_secuencia"] is True
    assert est["uml_estados"] is False and est["uml_clases"] is False


def test_alternativas_se_leen_en_la_rubrica():
    r = load_stack_rubric(RUBRICA)
    uml = {s.id: s for c in r.criterios for s in c.senales}["uml_casos_uso"]
    assert uml.tipo == "archivo" and len(uml.alternativas) == 1 and uml.alternativas[0].tipo == "informe"


def test_informe_con_nombre_del_proyecto_se_encuentra(tmp_path):
    d = proyecto(tmp_path / "p", con_informe=False)
    cuerpo = "".join(f"<w:p><w:r><w:t>{l}</w:t></w:r></w:p>" for l in INFORME.splitlines()) + \
             "<w:p><w:r><w:t>" + " ".join(["relleno"] * 900) + "</w:t></w:r></w:p>"
    with zipfile.ZipFile(d / "Plataforma distribuida para unificar la historia clinica.docx", "w") as z:
        z.writestr("word/document.xml", f"<w:document><w:body>{cuerpo}</w:body></w:document>")
        z.writestr("word/media/imagen.png", bytes(range(256)) * 400)
    inf = cargar_proyecto(d).informe
    assert inf and inf["archivo"].startswith("Plataforma") and inf["resumen_palabras"] == 180
    (d / "guia.pdf").write_bytes(b"%PDF")
    assert cargar_proyecto(d).informe["archivo"].startswith("Plataforma")


# --- clonar los enlaces de GitHub de entregas sin código ----------------------------------

def test_normalizar_url_github():
    from academicos.review.stack.clonar import normalizar
    assert normalizar("https://github.com/a/b") == "https://github.com/a/b.git"
    assert normalizar("https://github.com/a/b.git).") == "https://github.com/a/b.git"
    assert normalizar("https://github.com/Yeiner0205/Historia-clinica-distribuida") == \
        "https://github.com/Yeiner0205/Historia-clinica-distribuida.git"
    assert normalizar("https://evil.example/a/b") is None and normalizar("file:///etc") is None
    assert normalizar("https://github.com/a") is None


def test_clonar_enlaces_con_fallo_y_limite(tmp_path):
    from academicos.review.stack.clonar import clonar_enlaces
    llamadas = []

    def falso(cmd, timeout):
        llamadas.append(cmd)
        if "privado" in cmd[-2]:
            return 128, "", "Authentication failed"
        proyecto(Path(cmd[-1]))
        return 0, "", ""
    urls = ["https://github.com/a/privado", "https://github.com/a/uno", "https://github.com/a/uno",
            "https://github.com/a/dos", "https://github.com/a/tres", "https://evil.example/x/y"]
    clonadas, avisos = clonar_enlaces(urls, tmp_path, falso, maximo=2)
    assert [c.name for c in clonadas] == ["uno", "dos"] and len(llamadas) == 3     # sin duplicados ni dominios ajenos
    assert any("privado" in a for a in avisos) and any("máximo" in a for a in avisos)
    assert all(c[0] == "git" and c[1] == "clone" for c in llamadas)


def test_equipo_sin_codigo_clona_y_se_evalua(tmp_path):
    from academicos.review.stack.clonar import autores
    d = tmp_path / "curso" / "ANDRES ACOSTA_1_assignsubmission_file"
    d.mkdir(parents=True)
    (d / "parcial").write_text("https://github.com/andres/parcial-historia-clinica.git", encoding="utf-8")

    def falso(cmd, timeout):
        if cmd[1] == "clone":
            proyecto(Path(cmd[-1]))
            return 0, "", ""
        return 0, "ana\nana\nluis\n", ""
    clonar = lambda urls, work: __import__("academicos.review.stack.clonar", fromlist=["x"]).clonar_enlaces(urls, work, falso)
    rub = load_stack_rubric(RUBRICA)
    sin = evaluar_equipo(rub, agrupar([d])[0], tmp_path / "w1")
    con = evaluar_equipo(rub, agrupar([d])[0], tmp_path / "w2", clonar=clonar)
    assert sin["sin_proyecto"] and sin["nota"] == 0.0 and sin["enlaces"]
    assert not con["sin_proyecto"] and con["nota"] > 3 and con["clonados"] == ["parcial-historia-clinica"]
    assert autores(tmp_path, falso) == {"ana": 2, "luis": 1}
    assert "Repositorio clonado de GitHub" in markdown_equipo({**con, "autores": {"x": {"ana": 2}}}, rub)
