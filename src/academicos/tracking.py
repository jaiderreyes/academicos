"""Estado de seguimiento separado de la presentación y del catálogo."""
import copy
import json
from pathlib import Path
import time

from .reports import summarize
from .storage import atomic_write, safe_path


class RunTracker:
    def __init__(self, output, run_id, source_root, callback=None):
        self.path = safe_path(output, output / ('seguimiento-' + run_id + '.json'))
        self.callback = callback
        self.rows = []
        self.state = {
            'run_id': run_id, 'source_root': source_root, 'state': 'running',
            'stage': 'explorando', 'current_source': '', 'started_epoch': time.time(),
            'updated_epoch': time.time(), 'finished_epoch': None,
            'documents_discovered': 0, 'archives_discovered': 0, 'archives_finished': 0,
            'archives_failed': 0, 'scan_complete': False,
            'inventory_complete': False, 'recent': [], 'summary': summarize([]),
        }
        self.publish()

    def publish(self):
        self.state['updated_epoch'] = time.time()
        self.state['inventory_complete'] = (self.state['scan_complete'] and
            self.state['archives_finished'] >= self.state['archives_discovered'] and
            self.state['archives_failed'] == 0)
        try:
            atomic_write(self.path, json.dumps(self.state, ensure_ascii=False).encode('utf-8'))
        except OSError as exc:
            self.state['tracking_warning'] = str(exc)
        if self.callback:
            try:
                self.callback(copy.deepcopy(self.state))
            except Exception:
                self.callback = None

    def stage(self, stage, source=''):
        self.state.update(stage=stage, current_source=str(source))
        self.publish()

    def discovered(self, paths, scan_complete=None):
        for path in paths:
            suffix = Path(path).suffix.lower()
            self.state['documents_discovered'] += suffix in {'.pdf', '.docx'}
            self.state['archives_discovered'] += suffix == '.zip'
        if scan_complete is not None:
            self.state['scan_complete'] = scan_complete
        self.publish()

    def archive_finished(self, failed):
        self.state['archives_finished'] += 1
        self.state['archives_failed'] += int(failed)
        self.publish()

    def record(self, row):
        self.rows.append(row)
        self.state['summary'] = summarize(self.rows)
        self.state['recent'] = [{'source': r['source'], 'status': r['status']} for r in self.rows[-6:]]
        self.state.update(stage='resultado_guardado', current_source=row['source'])
        self.publish()

    def finish(self, state):
        self.state.update(state=state, stage='finalizada' if state == 'completed' else 'interrumpida',
                          current_source='', finished_epoch=time.time())
        self.publish()
