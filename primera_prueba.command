#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

printf '\n%s\n' 'academicOS · Primera prueba'
printf '%s\n' "Entrada: $project_dir/prueba/entrada"
printf '%s\n\n' "Salida:  $project_dir/prueba/salida"

exec "$project_dir/scripts/academicos.sh" ingest \
  "$project_dir/prueba/entrada" \
  --output "$project_dir/prueba/salida" \
  --ui live
