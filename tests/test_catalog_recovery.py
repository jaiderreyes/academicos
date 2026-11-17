import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from academicos.catalog import Catalog, catalog_status
from academicos.cli import main
from academicos.pipeline import Pipeline
from academicos.storage import atomic_write, workspace_lock


class CountingReader:
    cache_key = 'test-reader-v1'

    def __init__(self):
        self.calls = []

    def convert(self, path):
        value = path.read_text()
        self.calls.append(value)
        if value == 'FAIL':
            raise ValueError('No convertir')
        return value


class CatalogRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input'
        self.source.mkdir()
        self.output = self.root / 'output'
        self.reader = CountingReader()

    def put(self, name, content):
        path = self.source / name
        path.write_text(content)
        return path

    def run_pipeline(self, converter=None):
        return Pipeline(converter or self.reader).run(self.source, self.output)[1]

    def query(self, sql):
        with sqlite3.connect(self.output / 'catalogo.sqlite3') as db:
            return db.execute(sql).fetchall()

    def test_repeat_converts_zero_and_events_persist(self):
        self.put('a.pdf', 'A')
        self.put('b.docx', 'B')
        self.run_pipeline()
        self.assertEqual(self.reader.calls, ['A', 'B'])
        reader = CountingReader()
        rows = self.run_pipeline(reader)
        self.assertEqual(reader.calls, [])
        self.assertTrue(all(r['status'] == 'omitido_sin_cambios' for r in rows))
        self.assertEqual(catalog_status(self.output)['counts']['events'], 4)

    def test_only_changed_document_updates_with_history(self):
        path = self.put('a.pdf', 'A')
        self.put('b.pdf', 'B')
        self.run_pipeline()
        path.write_text('A nueva versión')
        self.reader.calls.clear()
        rows = self.run_pipeline()
        self.assertEqual(self.reader.calls, ['A nueva versión'])
        self.assertEqual([r['status'] for r in rows], ['actualizado', 'omitido_sin_cambios'])
        self.assertEqual((self.output / 'documentos/a.pdf.md').read_text(), 'A nueva versión\n')
        versions = self.query("SELECT c.artifact FROM location_versions v JOIN locations l ON l.id=v.location_id JOIN conversions c ON c.id=v.conversion_id WHERE l.source='a.pdf' ORDER BY v.id")
        self.assertEqual([((self.output / p).read_text()) for (p,) in versions], ['A\n', 'A nueva versión\n'])

    def test_failed_update_preserves_previous_output_and_version(self):
        path = self.put('a.pdf', 'A')
        self.run_pipeline()
        path.write_text('FAIL')
        row = self.run_pipeline()[0]
        self.assertEqual(row['status'], 'error_conversion')
        self.assertTrue(row['previous_output_preserved'])
        self.assertEqual((self.output / 'documentos/a.pdf.md').read_text(), 'A\n')
        self.assertEqual(self.query('SELECT COUNT(*) FROM location_versions')[0][0], 1)
        path.write_text('A corregida')
        self.assertEqual(self.run_pipeline()[0]['status'], 'actualizado')

    def test_missing_view_is_restored_without_conversion(self):
        self.put('a.pdf', 'A')
        first = self.run_pipeline()[0]
        Path(first['output']).unlink()
        self.reader.calls.clear()
        row = self.run_pipeline()[0]
        self.assertEqual(row['status'], 'restaurado')
        self.assertEqual(self.reader.calls, [])
        self.assertEqual(Path(row['output']).read_text(), 'A\n')

    def test_missing_and_corrupted_artifact_are_regenerated(self):
        self.put('a.pdf', 'A')
        row = self.run_pipeline()[0]
        artifact = self.output / row['artifact']
        artifact.unlink()
        self.reader.calls.clear()
        self.run_pipeline()
        self.assertEqual(self.reader.calls, ['A'])
        artifact.write_text('CORRUPTO')
        self.reader.calls.clear()
        self.run_pipeline()
        self.assertEqual(self.reader.calls, ['A'])
        self.assertEqual(artifact.read_text(), 'A\n')

    def test_manual_output_and_unregistered_output_are_preserved(self):
        self.put('a.pdf', 'A')
        row = self.run_pipeline()[0]
        target = Path(row['output'])
        target.write_text('Mi edición manual')
        self.assertEqual(self.run_pipeline()[0]['status'], 'conflicto_salida')
        self.assertEqual(target.read_text(), 'Mi edición manual')
        self.put('b.pdf', 'B')
        old = self.output / 'documentos/b.pdf.md'
        old.write_text('Salida sin catálogo')
        rows = self.run_pipeline()
        self.assertTrue(all(r['status'] == 'conflicto_salida' for r in rows))
        self.assertEqual(old.read_text(), 'Salida sin catálogo')

    def test_renamed_source_reuses_content_and_records_new_location(self):
        path = self.put('a.pdf', 'A')
        row = self.run_pipeline()[0]
        path.rename(self.source / 'renamed.pdf')
        self.reader.calls.clear()
        moved = self.run_pipeline()[0]
        self.assertEqual(self.reader.calls, [])
        self.assertEqual(moved['status'], 'reutilizado')
        self.assertEqual(moved['sha256_before'], row['sha256_before'])
        self.assertEqual(moved['duplicate_of'], 'a.pdf')
        self.assertEqual(catalog_status(self.output)['counts']['locations'], 2)
        self.assertTrue(Path(row['output']).exists())

    def test_converter_signature_invalidates_cache(self):
        self.put('a.pdf', 'A')
        self.run_pipeline()
        converter = CountingReader()
        converter.cache_key = 'test-reader-v2'
        self.assertEqual(self.run_pipeline(converter)[0]['status'], 'actualizado')
        self.assertEqual(converter.calls, ['A'])
        self.assertEqual(catalog_status(self.output)['counts']['location_versions'], 2)

    def test_nested_documents_are_incremental_when_archive_changes(self):
        archive = self.source / 'curso.zip'
        with ZipFile(archive, 'w') as z:
            z.writestr('a.pdf', 'A')
            z.writestr('b.pdf', 'B')
        self.run_pipeline()
        with ZipFile(archive, 'w') as z:
            z.writestr('a.pdf', 'A2')
            z.writestr('b.pdf', 'B')
        self.reader.calls.clear()
        rows = self.run_pipeline()
        self.assertEqual(self.reader.calls, ['A2'])
        self.assertEqual([r['status'] for r in rows], ['actualizado', 'omitido_sin_cambios'])

    def test_hard_exit_recovers_committed_work_and_retries_inflight(self):
        self.put('a.pdf', 'A')
        self.put('b.pdf', 'B')
        code = '''
import os, sys
from pathlib import Path
from academicos.pipeline import Pipeline
class CrashReader:
    cache_key = 'test-reader-v1'
    def convert(self, path):
        text = path.read_text()
        if text == 'B':
            os._exit(23)
        return text
Pipeline(CrashReader()).run(Path(sys.argv[1]), Path(sys.argv[2]))
'''
        result = subprocess.run([sys.executable, '-c', code, str(self.source), str(self.output)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 23, result.stderr)
        status = catalog_status(self.output)
        self.assertEqual(status['counts']['events'], 1)
        self.assertEqual(status['unfinished_attempts'], 1)
        self.assertEqual(list(self.output.glob('reporte-*.json')), [])
        rows = self.run_pipeline()
        self.assertEqual(self.reader.calls, ['B'])
        self.assertEqual([r['status'] for r in rows], ['omitido_sin_cambios', 'convertido'])
        self.assertEqual(self.query('SELECT state FROM runs ORDER BY rowid'), [('interrupted',), ('completed',)])
        self.assertEqual(catalog_status(self.output)['unfinished_attempts'], 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM attempts WHERE state='interrupted'"), [(1,)])

    def test_interruption_after_artifact_before_commit_retries_safely(self):
        self.put('a.pdf', 'A')
        with patch.object(Catalog, 'add_conversion', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_pipeline()
        self.assertEqual(self.query('SELECT COUNT(*) FROM conversions'), [(0,)])
        self.assertFalse((self.output / 'documentos/a.pdf.md').exists())
        self.reader.calls.clear()
        row = self.run_pipeline()[0]
        self.assertEqual(self.reader.calls, ['A'])
        self.assertEqual(row['status'], 'convertido')

    def test_interruption_after_view_before_bind_reconciles_without_conversion(self):
        self.put('a.pdf', 'A')
        with patch.object(Catalog, 'bind', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_pipeline()
        self.assertEqual(self.query('SELECT COUNT(*) FROM conversions'), [(1,)])
        self.assertEqual(self.query('SELECT COUNT(*) FROM location_versions'), [(0,)])
        self.reader.calls.clear()
        row = self.run_pipeline()[0]
        self.assertEqual(self.reader.calls, [])
        self.assertEqual(row['status'], 'reutilizado')
        self.assertEqual(self.query('SELECT COUNT(*) FROM location_versions'), [(1,)])

    def test_failed_atomic_publish_keeps_old_view_and_temp_is_not_reused(self):
        path = self.put('a.pdf', 'A')
        self.run_pipeline()
        path.write_text('A2')
        real_atomic = atomic_write
        def fail_view(target, data):
            if 'documentos' in target.parts:
                (target.parent / '.academicos-interrumpido.tmp').write_bytes(b'incompleto')
                raise OSError('Fallo de escritura simulado')
            return real_atomic(target, data)
        with patch('academicos.pipeline.atomic_write', side_effect=fail_view):
            row = self.run_pipeline()[0]
        self.assertEqual(row['status'], 'error_conversion')
        self.assertEqual((self.output / 'documentos/a.pdf.md').read_text(), 'A\n')
        self.reader.calls.clear()
        row = self.run_pipeline()[0]
        self.assertEqual(self.reader.calls, [])
        self.assertEqual(Path(row['output']).read_text(), 'A2\n')

    def test_lock_blocks_second_writer(self):
        self.output.mkdir()
        with workspace_lock(self.output):
            with self.assertRaisesRegex(ValueError, 'Otra ejecución'):
                self.run_pipeline()

    def test_unknown_schema_and_foreign_database_are_rejected(self):
        self.put('a.pdf', 'A')
        self.run_pipeline()
        with sqlite3.connect(self.output / 'catalogo.sqlite3') as db:
            db.execute('PRAGMA user_version=99')
        with self.assertRaisesRegex(ValueError, 'esquema'):
            self.run_pipeline()
        self.assertEqual(self.query('PRAGMA user_version'), [(99,)])
        other = self.root / 'foreign'
        other.mkdir()
        with sqlite3.connect(other / 'catalogo.sqlite3') as db:
            db.execute('CREATE TABLE unrelated(value)')
        with self.assertRaises(ValueError):
            Pipeline(self.reader).run(self.source, other)

    def test_cli_status_reads_catalog_without_converter(self):
        self.put('a.pdf', 'A')
        self.run_pipeline()
        stream = io.StringIO()
        with patch.object(sys, 'argv', ['academicos', 'status', '--output', str(self.output)]):
            with contextlib.redirect_stdout(stream):
                self.assertEqual(main(), 0)
        self.assertEqual(json.loads(stream.getvalue())['counts']['conversions'], 1)

    def test_cli_history_exposes_previous_and_current_artifact(self):
        path = self.put('a.pdf', 'A')
        self.run_pipeline()
        path.write_text('A2')
        self.run_pipeline()
        stream = io.StringIO()
        args = ['academicos', 'history', 'a.pdf', '--source', str(self.source), '--output', str(self.output)]
        with patch.object(sys, 'argv', args), contextlib.redirect_stdout(stream):
            self.assertEqual(main(), 0)
        versions = json.loads(stream.getvalue())
        self.assertEqual([v['is_current'] for v in versions], [0, 1])
        self.assertEqual([(self.output / v['artifact']).read_text() for v in versions], ['A\n', 'A2\n'])
