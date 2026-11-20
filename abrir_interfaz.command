#!/usr/bin/env bash
# Doble clic para abrir la interfaz gráfica de AcademicOS
cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
printf '\nAcademicOS · interfaz en http://127.0.0.1:8765 (Ctrl+C para cerrar)\n\n'
exec "$PY" -m academicos.cli gui
