# Plan · 004

`tracking.py`: snapshot atómico de seguimiento por ejecución y conteos.
`terminal.py`: representación Rich, texto simple y observador de solo lectura.
`reports.py`: resumen común y exportación recuperable de eventos a JSON/MD/CSV.
Pipeline: callback opcional y transiciones de fase, conteo de descubrimientos y duración por intento.
CLI: `--ui`, `watch` y `report`. Lanzador `scripts/academicos.sh` para Bash.

Los snapshots son archivos `seguimiento-<run>.json`. watch elige el snapshot más reciente por mtime, sin escribir; usa bloqueo compartido no bloqueante para comprobar si hay escritor exclusivo de 003.
Los porcentajes solo se muestran cuando el inventario es conocido, incluidos ZIP anidados. El estado terminado no equivale a que todos los documentos sean correctos: se muestran incidencias.
Reportes salen de un snapshot consistente de runs y events leídos en transacción de solo lectura. La exportación no modifica esas tablas.
No se cambia la firma del conversor ni el esquema SQLite.

Los reportes exportados mientras runs.state=running usan sufijo -parcial, de modo que una exportación concurrente nunca pisa el nombre del reporte final. La presentación usa Rich Live: https://rich.readthedocs.io/en/latest/live.html .
