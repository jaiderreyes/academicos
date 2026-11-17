# Primera prueba de academicOS

La carpeta está preparada así:

- `prueba/entrada/`: coloca aquí el material nuevo que se procesará.
- `prueba/salida/`: catálogo, Markdown y reportes generados.
- `primera_prueba.command`: ejecuta la ingesta desde Finder o Terminal.

## Ejecutar

Desde Terminal:

```bash
cd "/Users/jaiderreyes/Downloads/academicos"
bash primera_prueba.command
```

También puedes abrir `primera_prueba.command` desde Finder.

Prepara una carpeta completa y limpia la prueba anterior desde la CLI:

```bash
bash scripts/academicos.sh prepare "/ruta/al/material-nuevo" --workspace ./prueba --clean
```

Luego ejecuta `bash primera_prueba.command`. Solo se copian PDF, DOCX y ZIP; los
originales no se modifican. Para vaciar entrada y salida sin cargar material nuevo:

```bash
bash scripts/academicos.sh clean --workspace ./prueba --include-input
```

