import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

from .converters import MarkItDownConverter
from .pipeline import Limits, Pipeline
from .catalog import catalog_history, catalog_status
from .reports import export_reports
from .terminal import TerminalMonitor, watch
from .workspace import clean_workspace, prepare_material
from .review.cli import add_parser as add_review_parser, run_review
from .review.rubric import RubricError


def main(argv=None):
    parser = argparse.ArgumentParser(description="academicOS · biblioteca documental local")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest", help="Convertir DOCX/PDF/ZIP con seguimiento")
    ingest.add_argument("source", type=Path)
    ingest.add_argument("--output", type=Path, required=True)
    ingest.add_argument("--max-zip-mb", type=int, default=500)
    ingest.add_argument("--max-zip-files", type=int, default=2000)
    ingest.add_argument("--max-depth", type=int, default=3)
    ingest.add_argument("--ui", choices=['auto','live','plain','none'], default='auto')
    status = sub.add_parser("status", help="Consultar catálogo e historial de ejecuciones")
    status.add_argument("--output", type=Path, required=True)
    history = sub.add_parser("history", help="Consultar versiones de una ruta de origen")
    history.add_argument("path", help="Ruta relativa, también virtual dentro de ZIP")
    history.add_argument("--source", type=Path, required=True)
    history.add_argument("--output", type=Path, required=True)
    monitor = sub.add_parser('watch', help='Observar avance desde otra terminal')
    monitor.add_argument('--output', type=Path, required=True)
    monitor.add_argument('--once', action='store_true', help='Consultar una vez en JSON')
    monitor.add_argument('--ui', choices=['auto','live','plain'], default='auto')
    report = sub.add_parser('report', help='Exportar reportes JSON, Markdown y CSV desde el catálogo')
    report.add_argument('--output', type=Path, required=True)
    report.add_argument('--run', help='ID de ejecución; por defecto la más reciente')
    prepare = sub.add_parser('prepare', help='Copiar material nuevo a un espacio de prueba')
    prepare.add_argument('material', type=Path, help='Archivo o carpeta con PDF, DOCX o ZIP')
    prepare.add_argument('--workspace', type=Path, default=Path('prueba'))
    prepare.add_argument('--clean', action='store_true', help='Limpiar entrada y resultados anteriores')
    clean = sub.add_parser('clean', help='Limpiar un espacio de prueba administrado')
    clean.add_argument('--workspace', type=Path, default=Path('prueba'))
    clean.add_argument('--include-input', action='store_true', help='Eliminar también las copias de entrada')
    add_review_parser(sub)
    args = parser.parse_args(argv)
    try:
        if args.command == 'review':
            return run_review(args)
        if args.command == 'prepare':
            print(json.dumps(prepare_material(args.material, args.workspace, args.clean), ensure_ascii=False, indent=2))
            return 0
        if args.command == 'clean':
            print(json.dumps(clean_workspace(args.workspace, args.include_input), ensure_ascii=False, indent=2))
            return 0
        if args.command in {"status", "history"}:
            result = (catalog_status(args.output) if args.command == "status" else
                      catalog_history(args.output, args.source, Path(args.path).as_posix()))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == 'watch':
            return watch(args.output, args.ui, args.once)
        if args.command == 'report':
            result = export_reports(args.output, args.run)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if min(args.max_zip_mb, args.max_zip_files, args.max_depth) < 1:
            parser.error("Los límites deben ser positivos")
        with TerminalMonitor(args.ui) as monitor:
            converter = MarkItDownConverter()
            report, rows = Pipeline(converter, Limits(
                max_files=args.max_zip_files,
                max_bytes=args.max_zip_mb * 1024 * 1024,
                max_depth=args.max_depth,
            ), progress_callback=monitor.update).run(args.source, args.output)
    except KeyboardInterrupt:
        print('Seguimiento cerrado.' if args.command == 'watch' else 'Ejecución interrumpida; avances confirmados conservados.')
        return 130
    except (ValueError, ImportError, OSError, sqlite3.Error, RubricError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    for status, count in sorted(Counter(row["status"] for row in rows).items()):
        print(f"{status}: {count}")
    print(f"Reportes: {report.with_suffix('.md')} | {report.with_suffix('.csv')} | {report}")
    return 1 if any(row["status"].startswith("error") or row["status"] in {"sin_texto", "conflicto_salida"} for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
