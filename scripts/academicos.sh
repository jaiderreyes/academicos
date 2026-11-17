#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/.." && pwd)"
if [[ -x "$project_dir/.venv/bin/academicos" ]]; then
    exec "$project_dir/.venv/bin/academicos" "$@"
elif command -v academicos >/dev/null 2>&1; then
    exec academicos "$@"
else
    printf '%s\n' 'Instala primero academicOS en el entorno .venv del proyecto. Consulta README.md.' >&2
    exit 2
fi
