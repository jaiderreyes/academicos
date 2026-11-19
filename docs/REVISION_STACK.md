# Revisión de proyectos distribuidos (`academicos review stack`)

```bash
cd /Users/jaiderreyes/academicos && source .venv/bin/activate
# 1) solo análisis estático (rápido, sin Docker)
academicos review stack --rubrica rubricas/interoperabilidad-salud.yaml \
  --curso "/Users/jaiderreyes/Downloads/00578-AB-08-S-2026-02-SISTEMAS DISTRIBUIDOS" \
  --salida reportes-sd --equipos manuales/equipos-sistemas-distribuidos.yaml --no-docker
# 2) con docker compose up por equipo (lento: hace build; necesita Docker Desktop abierto)
academicos review stack ... (sin --no-docker) [--solo "oyola"]   # prueba primero con un equipo
```

Salidas en `--salida`: `reporte_general.md`, `consolidado.csv` (una fila por estudiante), `equipos/<equipo>.md`, `similitud.md`.

- Los `.rar` se abren con `bsdtar` (viene en macOS), `7z`, `unrar` o `unar`.
- `--base <carpeta>` resta el repositorio de referencia de la similitud.
- `--sancion-similitud 1.0 --excepto "TEXTO"` pone 0.0 al equipo (reversible; la nota automática se conserva).
- La sustentación individual (0,15) no se calcula: queda en la columna `sustentacion` del CSV.
- Ver `specs/007-revision-proyectos-distribuidos/spec.md`.
