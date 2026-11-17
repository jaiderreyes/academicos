"""Panel de terminal y observador independiente; ambos reciben snapshots."""
import fcntl
import json
from pathlib import Path
import sys
import time

from .reports import clean_text

STAGES = {
    'explorando': 'Explorando carpetas', 'preparando': 'Inventario inicial listo',
    'extrayendo_zip': 'Extrayendo ZIP', 'leyendo_hash': 'Verificando documento',
    'buscando_cache': 'Buscando conversión previa', 'convirtiendo': 'Convirtiendo a Markdown',
    'verificando_integridad': 'Comprobando integridad final', 'publicando': 'Guardando resultado',
    'resultado_guardado': 'Resultado registrado', 'generando_reportes': 'Generando reportes',
    'finalizada': 'Finalizada', 'interrumpida': 'Interrumpida',
}


def duration(seconds):
    seconds = max(0, int(seconds))
    return f'{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}'


def render_dashboard(snapshot):
    from rich.console import Group
    from rich.panel import Panel
    from rich.progress_bar import ProgressBar
    from rich.spinner import Spinner
    from rich.table import Table
    from rich.text import Text
    if not snapshot:
        return Panel(Text('Esperando una ejecución de academicOS…'), title='academicOS · Seguimiento')
    summary = snapshot['summary']
    state = snapshot['state']
    end = snapshot.get('finished_epoch') or time.time()
    elapsed = duration(end - snapshot['started_epoch'])
    labels = {'running':'En ejecución', 'completed':'Finalizada', 'interrupted':'Interrumpida',
              'abandoned':'Sin escritor activo: ejecución no cerrada'}
    title = Text('academicOS · Seguimiento', style='bold cyan')
    info = Table.grid(padding=(0, 2), expand=True)
    info.add_column(style='bold', width=17)
    info.add_column(ratio=1)
    info.add_row('Estado', Text(labels.get(state, clean_text(state))))
    info.add_row('Ejecución', Text(clean_text(snapshot['run_id'])))
    info.add_row('Fase', Text(STAGES.get(snapshot['stage'], clean_text(snapshot['stage']))))
    info.add_row('Archivo actual', Text(clean_text(snapshot.get('current_source') or '—'), overflow='ellipsis', no_wrap=True))
    info.add_row('Tiempo', Text(elapsed))
    done, total = summary['documents_finished'], snapshot['documents_discovered']
    exact = snapshot['inventory_complete']
    info.add_row('Documentos', Text(f'{done} / {total} ' + (f'inventariados · {done/total:.0%}' if exact and total else 'inventariados' if exact else 'descubiertos · total provisional')))
    info.add_row('Resultados', Text(f"Nuevos/actualizados: {summary['converted']}   Reutilizados: {summary['reused']}   Copias: {summary['duplicates']}"))
    info.add_row('Incidencias', Text(f"Errores: {summary['errors']}   Conflictos: {summary['conflicts']}   Sin texto: {summary['empty']}   No soportados: {summary['unsupported']}"))
    info.add_row('ZIP', Text(f"{snapshot['archives_finished']} / {snapshot['archives_discovered']} recorridos · {snapshot['archives_failed']} fallidos"))
    if snapshot.get('tracking_warning'):
        info.add_row('Seguimiento', Text('No se pudo guardar snapshot: ' + clean_text(snapshot['tracking_warning'])))
    if state == 'running':
        info.add_row('Última señal', Text(f"Hace {max(0, int(time.time()-snapshot['updated_epoch']))} s; reloj visual no implica avance dentro del archivo"))
    recent = Table('Último estado', 'Archivo', expand=True, show_lines=False)
    for row in snapshot.get('recent', []):
        recent.add_row(Text(clean_text(row['status'])), Text(clean_text(row['source']), overflow='ellipsis', no_wrap=True))
    meter = (ProgressBar(total=max(total, 1), completed=done) if exact and total else
             Spinner('dots', text=Text('Descubriendo alcance…')) if state == 'running' else Text('Sin porcentaje definitivo de inventario' if not exact else 'Sin documentos procesables'))
    return Panel(Group(info, meter, recent), title=title, border_style='cyan')


class TerminalMonitor:
    def __init__(self, mode='auto', stream=None):
        self.stream = stream or sys.stderr
        self.mode = ('live' if self.stream.isatty() else 'plain') if mode == 'auto' else mode
        self.snapshot = None
        self.live = None
        self.last_line = None

    def __enter__(self):
        if self.mode == 'live':
            from rich.console import Console
            from rich.live import Live
            self.live = Live(console=Console(file=self.stream), refresh_per_second=4,
                             get_renderable=lambda: render_dashboard(self.snapshot),
                             redirect_stdout=True, redirect_stderr=True)
            self.live.__enter__()
        return self

    def __exit__(self, *args):
        if self.live:
            return self.live.__exit__(*args)

    def update(self, snapshot):
        self.snapshot = snapshot
        if self.mode == 'plain':
            summary = snapshot['summary']
            line = (f"{snapshot['stage']} | {summary['documents_finished']}/{snapshot['documents_discovered']} documentos"
                    f" | nuevos={summary['converted']} reutilizados={summary['reused']} errores={summary['errors']}"
                    f" | {clean_text(snapshot.get('current_source', ''))}")
            if line != self.last_line:
                print(line, file=self.stream, flush=True)
                self.last_line = line


def writer_is_active(output):
    try:
        with (output / '.academicos.lock').open('rb') as stream:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    except FileNotFoundError:
        pass
    return False


def latest_snapshot(output):
    paths = sorted(output.glob('seguimiento-*.json'), key=lambda path: path.stat().st_mtime_ns, reverse=True)
    for path in paths:
        try:
            snapshot = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if snapshot['state'] == 'running' and not writer_is_active(output):
            snapshot['state'] = 'abandoned'
        return snapshot
    return None


def watch(output, mode='auto', once=False, interval=0.5):
    output = output.expanduser().resolve()
    if once:
        snapshot = latest_snapshot(output)
        print(json.dumps(snapshot or {'state':'waiting', 'message':'Sin seguimiento disponible'}, ensure_ascii=False, indent=2))
        return 0
    if mode == 'auto' and not sys.stderr.isatty():
        mode = 'plain'
    with TerminalMonitor(mode) as monitor:
        while True:
            snapshot = latest_snapshot(output)
            if snapshot:
                monitor.update(snapshot)
            elif monitor.last_line != 'waiting' and monitor.mode == 'plain':
                print('Esperando una ejecución de academicOS…', file=monitor.stream, flush=True)
                monitor.last_line = 'waiting'
            time.sleep(interval)
