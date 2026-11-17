"""Exportación local a partir de eventos confirmados; no modifica el catálogo."""
from collections import Counter
from contextlib import closing
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import unicodedata

from .catalog import _read_catalog
from .storage import atomic_write, safe_path


def clean_text(value):
    text = str(value if value is not None else '')
    return ''.join(' ' if char in '\r\n\t' else char for char in text
                   if char in '\r\n\t' or not unicodedata.category(char).startswith('C'))


def summarize(rows):
    counts = Counter(row['status'] for row in rows)
    return {
        'records': len(rows),
        'documents_finished': sum(Path(row['source']).suffix.lower() in {'.pdf', '.docx'} for row in rows),
        'converted': counts['convertido'] + counts['actualizado'],
        'reused': counts['reutilizado'] + counts['restaurado'] + counts['omitido_sin_cambios'],
        'duplicates': sum(row.get('duplicate_of') is not None for row in rows),
        'errors': sum(count for status, count in counts.items() if status.startswith('error')),
        'conflicts': counts['conflicto_salida'],
        'empty': counts['sin_texto'],
        'unsupported': counts['no_soportado'],
        'statuses': dict(counts),
    }


def read_run(output: Path, run_id=None):
    with closing(_read_catalog(output)) as db:
        db.execute('BEGIN')
        run = (db.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone() if run_id else
               db.execute('SELECT * FROM runs ORDER BY rowid DESC LIMIT 1').fetchone())
        if not run:
            raise ValueError('No se encontró la ejecución solicitada')
        if not re.fullmatch('[0-9a-f]{32}', run['id']):
            raise ValueError('Identificador de ejecución inválido')
        rows = [json.loads(row[0]) for row in db.execute('SELECT payload FROM events WHERE run_id=? ORDER BY id', (run['id'],))]
        return dict(run), rows


def _md(value):
    return re.sub(r'([\\`*_{}\[\]()<>|#!])', r'\\\1', clean_text(value))


def _csv(value):
    text = clean_text(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


def export_reports(output: Path, run_id=None):
    output = output.expanduser().resolve()
    run, rows = read_run(output, run_id)
    summary = summarize(rows)
    prefix = 'reporte-' + run['id'] + ('-parcial' if run['state'] == 'running' else '')
    paths = {extension: safe_path(output, output / (prefix + '.' + extension)) for extension in ['json', 'md', 'csv']}
    # JSON mantiene el formato de lista usado desde 001.
    atomic_write(paths['json'], json.dumps(rows, ensure_ascii=False, indent=2).encode('utf-8'))
    labels = {'completed': 'Finalizada', 'interrupted': 'Interrumpida', 'running': 'Parcial: ejecución no cerrada'}
    lines = ['# academicOS · Reporte de ejecución', '',
             '**Ejecución:** ' + run['id'], '',
             '**Estado del catálogo:** ' + labels.get(run['state'], _md(run['state'])), '',
             '**Entrada:** ' + _md(run['source_root']), '',
             '**Inicio (UTC):** ' + _md(run['started_at']), '',
             '**Fin (UTC):** ' + _md(run['finished_at'] or 'No registrado'), '',
             '**Exportado (UTC):** ' + datetime.now(timezone.utc).isoformat(), '',
             '## Resumen', '', '| Indicador | Cantidad |', '|---|---:|']
    for key, label in [('documents_finished','Documentos con resultado'), ('converted','Conversiones nuevas/actualizadas'),
                       ('reused','Reutilizados/restaurados/sin cambios'), ('duplicates','Copias exactas detectadas'),
                       ('errors','Errores'), ('conflicts','Conflictos'), ('empty','Sin texto'), ('unsupported','No soportados')]:
        lines.append(f'| {label} | {summary[key]} |')
    lines += ['', 'Los resultados confirmados no incluyen un intento que siga incompleto. Una ejecución finalizada puede contener errores.',
              '', '## Resultados por archivo', '', '| Origen | Estado | Duración (s) | Integridad | Copia de | Incidencia |', '|---|---|---:|---|---|---|']
    for row in rows:
        lines.append('| ' + ' | '.join(_md(row.get(key, '')) for key in
                     ['source','status','duration_seconds','integrity','duplicate_of','error']) + ' |')
    lines += ['', 'La similitud local y la integridad no certifican autoría ni ausencia de plagio. No se consultan fuentes externas.', '']
    atomic_write(paths['md'], '\n'.join(lines).encode('utf-8'))
    fields = ['source','status','duration_seconds','integrity','duplicate_of','sha256_before','sha256_after','output','error']
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(fields)
    for row in rows:
        writer.writerow([_csv(row.get(field, '')) for field in fields])
    atomic_write(paths['csv'], stream.getvalue().encode('utf-8-sig'))
    return {'run': run, 'summary': summary, 'paths': {key: str(path) for key, path in paths.items()}}
