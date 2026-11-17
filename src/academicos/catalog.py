"""Catálogo local persistente: contenido, ubicaciones, versiones y avance."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .storage import safe_path

APPLICATION_ID = 0x41434F53
SCHEMA_VERSION = 1

SCHEMA = '''
BEGIN;
CREATE TABLE runs (
 id TEXT PRIMARY KEY, source_root TEXT NOT NULL, converter_key TEXT NOT NULL,
 state TEXT NOT NULL, started_at TEXT DEFAULT CURRENT_TIMESTAMP, finished_at TEXT
);
CREATE TABLE contents (
 sha256 TEXT PRIMARY KEY, first_root TEXT NOT NULL, first_source TEXT NOT NULL,
 first_seen TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE locations (
 id INTEGER PRIMARY KEY, source_root TEXT NOT NULL, source TEXT NOT NULL,
 latest_seen_sha TEXT, current_conversion_id INTEGER,
 current_output_sha TEXT, output_path TEXT,
 UNIQUE(source_root, source)
);
CREATE TABLE conversions (
 id INTEGER PRIMARY KEY, cache_key TEXT NOT NULL, input_sha TEXT NOT NULL,
 converter_key TEXT NOT NULL, suffix TEXT NOT NULL, artifact TEXT NOT NULL,
 output_sha TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX conversion_cache ON conversions(cache_key);
CREATE TABLE location_versions (
 id INTEGER PRIMARY KEY, location_id INTEGER NOT NULL REFERENCES locations(id),
 conversion_id INTEGER NOT NULL REFERENCES conversions(id),
 created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(location_id, conversion_id)
);
CREATE TABLE attempts (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 source TEXT NOT NULL, state TEXT NOT NULL,
 started_at TEXT DEFAULT CURRENT_TIMESTAMP, finished_at TEXT
);
CREATE TABLE events (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 payload TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
PRAGMA application_id = 1094930259;
PRAGMA user_version = 1;
COMMIT;
'''


class Catalog:
    def __init__(self, output: Path):
        path = safe_path(output, output / 'catalogo.sqlite3')
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        try:
            app = self.db.execute('PRAGMA application_id').fetchone()[0]
            version = self.db.execute('PRAGMA user_version').fetchone()[0]
            tables = self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if not tables and app == 0 and version == 0:
                self.db.executescript(SCHEMA)
            elif app != APPLICATION_ID or version != SCHEMA_VERSION:
                raise ValueError('El catálogo pertenece a otra aplicación o usa un esquema no soportado')
            self.db.execute('PRAGMA foreign_keys = ON')
            self.db.execute('PRAGMA synchronous = FULL')
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def start_run(self, source_root, converter_key):
        run_id = uuid4().hex
        with self.db:
            self.db.execute("UPDATE attempts SET state='interrupted', finished_at=CURRENT_TIMESTAMP WHERE state='running'")
            self.db.execute("UPDATE runs SET state='interrupted', finished_at=CURRENT_TIMESTAMP WHERE state='running'")
            self.db.execute('INSERT INTO runs(id,source_root,converter_key,state) VALUES(?,?,?,?)',
                            (run_id, source_root, converter_key, 'running'))
        return run_id

    def finish_run(self, run_id, state):
        with self.db:
            self.db.execute('UPDATE runs SET state=?, finished_at=CURRENT_TIMESTAMP WHERE id=?', (state, run_id))
            self.db.execute("UPDATE attempts SET state='interrupted', finished_at=CURRENT_TIMESTAMP WHERE run_id=? AND state='running'", (run_id,))

    def start_attempt(self, run_id, source):
        with self.db:
            cursor = self.db.execute("INSERT INTO attempts(run_id,source,state) VALUES(?,?,'running')", (run_id, source))
            return cursor.lastrowid

    def record(self, run_id, row, attempt_id=None):
        with self.db:
            self.db.execute('INSERT INTO events(run_id,payload) VALUES(?,?)',
                            (run_id, json.dumps(row, ensure_ascii=False)))
            if attempt_id is not None:
                self.db.execute('UPDATE attempts SET state=?, finished_at=CURRENT_TIMESTAMP WHERE id=?',
                                (row['status'], attempt_id))

    def observe(self, root, source, digest):
        previous = self.db.execute('SELECT first_root,first_source FROM contents WHERE sha256=?', (digest,)).fetchone()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO contents(sha256,first_root,first_source) VALUES(?,?,?)',
                            (digest, root, source))
            self.db.execute('INSERT INTO locations(source_root,source,latest_seen_sha) VALUES(?,?,?) ON CONFLICT(source_root,source) DO UPDATE SET latest_seen_sha=excluded.latest_seen_sha',
                            (root, source, digest))
        location = self.db.execute('SELECT * FROM locations WHERE source_root=? AND source=?', (root, source)).fetchone()
        duplicate = None
        if previous and (previous['first_root'], previous['first_source']) != (root, source):
            duplicate = dict(previous)
        return dict(location), duplicate

    def lookup(self, key):
        row = self.db.execute('SELECT * FROM conversions WHERE cache_key=? ORDER BY id DESC LIMIT 1', (key,)).fetchone()
        return dict(row) if row else None

    def add_conversion(self, key, digest, converter_key, suffix, artifact, output_sha):
        with self.db:
            cursor = self.db.execute('INSERT INTO conversions(cache_key,input_sha,converter_key,suffix,artifact,output_sha) VALUES(?,?,?,?,?,?)',
                                    (key, digest, converter_key, suffix, artifact, output_sha))
            return dict(self.db.execute('SELECT * FROM conversions WHERE id=?', (cursor.lastrowid,)).fetchone())

    def bind(self, location, conversion, target):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO location_versions(location_id,conversion_id) VALUES(?,?)',
                            (location['id'], conversion['id']))
            self.db.execute('UPDATE locations SET current_conversion_id=?, current_output_sha=?, output_path=? WHERE id=?',
                            (conversion['id'], conversion['output_sha'], str(target), location['id']))


def _read_catalog(output: Path):
    path = output.expanduser().resolve() / 'catalogo.sqlite3'
    if not path.is_file():
        raise ValueError('No existe catálogo en esta carpeta')
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    if (db.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID or
            db.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION):
        db.close()
        raise ValueError('Catálogo o esquema no soportado')
    return db


def catalog_status(output: Path):
    with closing(_read_catalog(output)) as db:
        counts = {table: db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                  for table in ['contents', 'locations', 'conversions', 'location_versions', 'events']}
        runs = [dict(row) for row in db.execute('SELECT * FROM runs ORDER BY started_at DESC, rowid DESC LIMIT 10')]
        unfinished = db.execute("SELECT COUNT(*) FROM attempts WHERE state='running'").fetchone()[0]
        return {'schema_version': SCHEMA_VERSION, 'counts': counts, 'recent_runs': runs, 'unfinished_attempts': unfinished}


def catalog_history(output: Path, source_root: Path, source: str):
    with closing(_read_catalog(output)) as db:
        return [dict(row) for row in db.execute(
            """SELECT v.id AS version_id, v.created_at, c.input_sha, c.converter_key,
                      c.artifact, c.output_sha, l.output_path,
                      (l.current_conversion_id=c.id) AS is_current
               FROM location_versions v JOIN locations l ON l.id=v.location_id
               JOIN conversions c ON c.id=v.conversion_id
               WHERE l.source_root=? AND l.source=? ORDER BY v.id""",
            (str(source_root.expanduser().resolve()), source))]
