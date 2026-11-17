# Aceptación · 005

- AC-W01: preparar una carpeta copia PDF, DOCX y ZIP conservando subcarpetas.
- AC-W02: los demás formatos se omiten y una selección vacía produce error.
- AC-W03: `--clean` reemplaza la prueba anterior sin modificar el origen.
- AC-W04: `clean` conserva la entrada salvo que se use `--include-input`.
- AC-W05: un directorio sin marcador o una ruta solapada se rechazan.

## Evidencia

El 21 de octubre de 2026 se ejecutaron 56 pruebas en macOS con Python 3.14. La prueba
real copió un PDF desde Descargas a `prueba/entrada` y luego eliminó entrada y salida
mediante la CLI, conservando intacto el archivo original.

