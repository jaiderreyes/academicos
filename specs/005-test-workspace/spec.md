# Spec 005 · Preparación y limpieza de pruebas

## Problema

La persona usuaria necesita seleccionar material nuevo desde la CLI y reiniciar una
prueba sin copiar archivos manualmente ni arriesgar documentos originales.

## Alcance

- `prepare` copia PDF, DOCX y ZIP desde un archivo o carpeta a `entrada`.
- `prepare --clean` elimina previamente las copias de entrada y todos los resultados.
- `clean` elimina siempre los resultados; `--include-input` elimina también las copias de entrada.
- La limpieza solo opera en espacios creados por academicOS y nunca sigue enlaces simbólicos.
- Los documentos de origen nunca se modifican ni eliminan.

## Requisitos

- RF-W01: aceptar una ruta existente de archivo o carpeta.
- RF-W02: conservar rutas relativas al copiar carpetas y omitir formatos no soportados.
- RF-W03: informar cuántos archivos fueron copiados y qué rutas usa la prueba.
- RF-W04: limpiar de forma explícita y limitada a `entrada` y `salida`.
- RF-W05: rechazar origen y espacio de trabajo solapados.

## Fuera de alcance

OCR, selección interactiva de Finder, eliminación de los documentos originales y
clasificación temática automática.

