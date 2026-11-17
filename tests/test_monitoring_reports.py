import contextlib
import csv
from io import BytesIO, StringIO
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

from academicos.catalog import catalog_status
from academicos.cli import main
from academicos.pipeline import Pipeline
from academicos.reports import export_reports, summarize
from academicos.storage import workspace_lock
from academicos.terminal import TerminalMonitor, latest_snapshot, render_dashboard
from academicos.validation import file_hash


class Reader:
    cache_key = 'ui-tests-reader'
    def convert(self, path):
        return path.read_text()


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input'
        self.source.mkdir()
        self.output = self.root / 'output'

    def put(self, name='a.pdf', text='academicOS documento'):
        path = self.source / name
        path.write_text(text)
        return path

    def run_pipeline(self, callback=None, converter=None):
        return Pipeline(converter or Reader(), progress_callback=callback).run(self.source, self.output)

    def test_phases_before_conversion_and_final_counts(self):
        self.put()
        snapshots = []
        outer = self
        class InspectingReader(Reader):
            def convert(self, path):
                outer.assertEqual(snapshots[-1]['stage'], 'convirtiendo')
                outer.assertEqual(snapshots[-1]['summary']['documents_finished'], 0)
                outer.assertEqual(latest_snapshot(outer.output)['state'], 'running')
                return super().convert(path)
        report, rows = self.run_pipeline(snapshots.append, InspectingReader())
        stages = [s['stage'] for s in snapshots]
        for stage in ['explorando','preparando','leyendo_hash','buscando_cache','convirtiendo','verificando_integridad','publicando','resultado_guardado','generando_reportes','finalizada']:
            self.assertIn(stage, stages)
        final = latest_snapshot(self.output)
        self.assertEqual(final['state'], 'completed')
        self.assertEqual(final['summary'], summarize(rows))
        self.assertEqual(final['summary']['documents_finished'], 1)
        self.assertGreaterEqual(rows[0]['duration_seconds'], 0)
        self.assertTrue(report.with_suffix('.md').is_file())
        self.assertTrue(report.with_suffix('.csv').is_file())

    def test_zip_total_is_provisional_until_nested_archive_finished(self):
        nested = BytesIO()
        with ZipFile(nested, 'w') as archive:
            archive.writestr('b.pdf', 'B')
        with ZipFile(self.source / 'a.zip', 'w') as archive:
            archive.writestr('a.pdf', 'A')
            archive.writestr('nested.zip', nested.getvalue())
        snapshots = []
        self.run_pipeline(snapshots.append)
        during = [s for s in snapshots if s['stage'] == 'convirtiendo']
        self.assertTrue(all(not s['inventory_complete'] for s in during))
        self.assertEqual(snapshots[-1]['documents_discovered'], 2)
        self.assertEqual(snapshots[-1]['archives_discovered'], 2)
        self.assertTrue(snapshots[-1]['inventory_complete'])

    def test_bad_zip_never_claims_complete_inventory(self):
        (self.source / 'bad.zip').write_bytes(b'corrupt')
        self.run_pipeline()
        snapshot = latest_snapshot(self.output)
        self.assertEqual(snapshot['archives_failed'], 1)
        self.assertFalse(snapshot['inventory_complete'])
        self.assertEqual(snapshot['summary']['errors'], 1)

    def test_observer_failure_does_not_cancel_documents(self):
        self.put()
        def bad_callback(snapshot):
            raise RuntimeError('Fallo de interfaz')
        _, rows = self.run_pipeline(bad_callback)
        self.assertEqual(rows[0]['status'], 'convertido')
        self.assertEqual(latest_snapshot(self.output)['state'], 'completed')

    def test_repeat_reuses_existing_cache_and_summary(self):
        self.put()
        self.run_pipeline()
        _, rows = self.run_pipeline()
        self.assertEqual(rows[0]['status'], 'omitido_sin_cambios')
        snapshot = latest_snapshot(self.output)
        self.assertEqual(snapshot['summary']['converted'], 0)
        self.assertEqual(snapshot['summary']['reused'], 1)
        self.assertEqual(catalog_status(self.output)['counts']['conversions'], 1)

    def test_watch_once_is_read_only_and_abandoned_run_is_detected(self):
        self.put()
        self.run_pipeline()
        progress = next(self.output.glob('seguimiento-*.json'))
        state = json.loads(progress.read_text())
        state['state'] = 'running'
        progress.write_text(json.dumps(state))
        before_db = file_hash(self.output / 'catalogo.sqlite3')
        before_snapshot = file_hash(progress)
        with workspace_lock(self.output):
            self.assertEqual(latest_snapshot(self.output)['state'], 'running')
        self.assertEqual(latest_snapshot(self.output)['state'], 'abandoned')
        stream = StringIO()
        args = ['academicos','watch','--output',str(self.output),'--once']
        with patch.object(sys,'argv',args), contextlib.redirect_stdout(stream):
            self.assertEqual(main(), 0)
        self.assertEqual(json.loads(stream.getvalue())['state'], 'abandoned')
        self.assertEqual(file_hash(self.output / 'catalogo.sqlite3'), before_db)
        self.assertEqual(file_hash(progress), before_snapshot)

    def test_report_formats_and_csv_formula_protection(self):
        self.put('=2+2.pdf', 'A')
        _, rows = self.run_pipeline()
        exported = export_reports(self.output)
        md = Path(exported['paths']['md']).read_text()
        self.assertIn('Conversiones nuevas/actualizadas', md)
        self.assertEqual(json.loads(Path(exported['paths']['json']).read_text()), rows)
        with Path(exported['paths']['csv']).open(encoding='utf-8-sig',newline='') as stream:
            csv_rows = list(csv.DictReader(stream))
        self.assertEqual(csv_rows[0]['source'], "'=2+2.pdf")
        self.assertEqual(exported['summary']['converted'], 1)

    def test_report_regeneration_after_hard_exit_uses_confirmed_events(self):
        self.put('a.pdf','A')
        self.put('b.pdf','B')
        code = '''
import os, sys
from pathlib import Path
from academicos.pipeline import Pipeline
class CrashReader:
    cache_key='crash-ui'
    def convert(self,path):
        text=path.read_text()
        if text=='B': os._exit(23)
        return text
Pipeline(CrashReader()).run(Path(sys.argv[1]),Path(sys.argv[2]))
'''
        result = subprocess.run([sys.executable,'-c',code,str(self.source),str(self.output)],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,23,result.stderr)
        self.assertEqual(latest_snapshot(self.output)['state'],'abandoned')
        exported = export_reports(self.output)
        self.assertEqual(exported['summary']['documents_finished'],1)
        self.assertEqual(exported['run']['state'],'running')
        self.assertIn('Parcial: ejecución no cerrada',Path(exported['paths']['md']).read_text())
        self.assertEqual(catalog_status(self.output)['counts']['events'],1)

    def test_plain_and_rendering_do_not_interpret_control_codes_or_markup(self):
        self.put('[bold]a\x1b[2J.pdf','A')
        stream=StringIO()
        with TerminalMonitor('plain',stream) as monitor:
            self.run_pipeline(monitor.update)
        self.assertNotIn('\x1b',stream.getvalue())
        from rich.console import Console
        rendered=StringIO()
        console=Console(file=rendered,width=110,color_system=None)
        console.print(render_dashboard(latest_snapshot(self.output)))
        self.assertIn('[bold]a',rendered.getvalue())
        self.assertNotIn('\x1b',rendered.getvalue())
        self.assertIn('100%',rendered.getvalue())

    def test_ctrl_c_ingestion_returns_130_and_saves_partial_reports(self):
        self.put('a.pdf','A')
        self.put('b.pdf','B')
        class InterruptReader(Reader):
            def convert(self,path):
                if path.read_text()=='B': raise KeyboardInterrupt
                return super().convert(path)
        args=['academicos','ingest',str(self.source),'--output',str(self.output),'--ui','none']
        with patch.object(sys,'argv',args),patch('academicos.cli.MarkItDownConverter',return_value=InterruptReader()),contextlib.redirect_stdout(StringIO()):
            self.assertEqual(main(),130)
        self.assertEqual(latest_snapshot(self.output)['state'],'interrupted')
        report=next(self.output.glob('reporte-*.md'))
        self.assertIn('Interrumpida',report.read_text())
        self.assertEqual(catalog_status(self.output)['counts']['events'],1)

    def test_ctrl_c_watch_does_not_change_completed_ingestion(self):
        self.put()
        self.run_pipeline()
        before=file_hash(self.output/'catalogo.sqlite3')
        args=['academicos','watch','--output',str(self.output),'--ui','plain']
        with patch.object(sys,'argv',args),patch('academicos.terminal.time.sleep',side_effect=KeyboardInterrupt),contextlib.redirect_stdout(StringIO()),contextlib.redirect_stderr(StringIO()):
            self.assertEqual(main(),130)
        self.assertEqual(file_hash(self.output/'catalogo.sqlite3'),before)

    def test_bash_launcher_preserves_spaces_and_exit_code(self):
        project=self.root/'project with spaces'
        scripts=project/'scripts'
        scripts.mkdir(parents=True)
        script=scripts/'academicos.sh'
        original=Path(__file__).parents[1]/'scripts/academicos.sh'
        script.write_text(original.read_text())
        command=project/'.venv/bin/academicos'
        command.parent.mkdir(parents=True)
        command.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\nsys.exit(7)\n')
        command.chmod(0o755)
        result=subprocess.run(['bash',str(script),'ingest','my folder','--output','my output'],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,7,result.stderr)
        self.assertEqual(json.loads(result.stdout),['ingest','my folder','--output','my output'])

    def test_cli_report_exports_selected_run(self):
        self.put()
        self.run_pipeline()
        run_id=latest_snapshot(self.output)['run_id']
        stream=StringIO()
        args=['academicos','report','--output',str(self.output),'--run',run_id]
        with patch.object(sys,'argv',args),contextlib.redirect_stdout(stream):
            self.assertEqual(main(),0)
        self.assertEqual(json.loads(stream.getvalue())['run']['id'],run_id)

    def test_running_export_has_partial_name_separate_from_final(self):
        self.put()
        exported=[]
        def snapshot_callback(snapshot):
            if snapshot['stage']=='resultado_guardado':
                exported.append(export_reports(self.output, snapshot['run_id']))
        report, _=self.run_pipeline(snapshot_callback)
        self.assertEqual(len(exported),1)
        self.assertIn('-parcial.md', exported[0]['paths']['md'])
        self.assertNotEqual(exported[0]['paths']['md'],str(report.with_suffix('.md')))
        self.assertIn('Finalizada', report.with_suffix('.md').read_text())

    def test_separate_watch_can_close_while_writer_keeps_running(self):
        import selectors
        import signal
        import time
        self.put()
        marker=self.root/'converting'
        release=self.root/'release'
        code='''
from pathlib import Path
import sys,time
from academicos.pipeline import Pipeline
class BlockingReader:
    cache_key='blocking-ui'
    def convert(self,path):
        Path(sys.argv[3]).write_text('ready')
        deadline=time.monotonic()+12
        while not Path(sys.argv[4]).exists():
            if time.monotonic()>deadline: raise ValueError('Test timeout')
            time.sleep(0.02)
        return path.read_text()
Pipeline(BlockingReader()).run(Path(sys.argv[1]),Path(sys.argv[2]))
'''
        worker=subprocess.Popen([sys.executable,'-c',code,str(self.source),str(self.output),str(marker),str(release)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        watcher=None
        try:
            deadline=time.monotonic()+8
            while not marker.exists() and time.monotonic()<deadline:
                if worker.poll() is not None:
                    self.fail(worker.communicate()[1])
                time.sleep(0.02)
            self.assertTrue(marker.exists())
            once=subprocess.run([sys.executable,'-m','academicos.cli','watch','--output',str(self.output),'--once'],capture_output=True,text=True,timeout=5)
            self.assertEqual(once.returncode,0,once.stderr)
            snapshot=json.loads(once.stdout)
            self.assertEqual(snapshot['state'],'running')
            self.assertEqual(snapshot['stage'],'convirtiendo')
            watcher=subprocess.Popen([sys.executable,'-m','academicos.cli','watch','--output',str(self.output),'--ui','plain'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            with selectors.DefaultSelector() as selector:
                selector.register(watcher.stderr,selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5),'Observador sin salida')
                self.assertIn('convirtiendo',watcher.stderr.readline())
            watcher.send_signal(signal.SIGINT)
            watcher.communicate(timeout=5)
            self.assertEqual(watcher.returncode,130)
            self.assertIsNone(worker.poll())
            release.write_text('continue')
            _,stderr=worker.communicate(timeout=5)
            self.assertEqual(worker.returncode,0,stderr)
            self.assertEqual(latest_snapshot(self.output)['state'],'completed')
        finally:
            for process in [watcher,worker]:
                if process and process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
