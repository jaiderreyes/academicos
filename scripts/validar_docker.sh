#!/usr/bin/env bash
# Valida en TU equipo el aislamiento de la revisión en Docker (spec 006, J-05).
# No usa `docker prune` ni borra nada: solo descarga la imagen si no la tienes (con --pull)
# y lanza contenedores efímeros (--rm) con el prefijo "academicos-".
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; fi
PYTHONPATH=src "$PY" -m academicos.review.runner "$@"
