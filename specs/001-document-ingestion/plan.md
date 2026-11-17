# Plan técnico · 001

## Decisiones vigentes

| Decisión | Motivo | Requisitos |
|---|---|---|
| Python 3.11+ y paquete instalable | Integración con herramientas documentales y ejecución local | RF-01, RF-03, RF-10 |
| argparse como CLI | Comando pequeño con pocas dependencias propias | RF-10 |
| pathlib para recorrido | Rutas y subcarpetas portables | RF-01, RC-03 |
| zipfile y TemporaryDirectory | Extracción temporal controlada | RF-02, RC-01, RC-02 |
| Adaptador MarkItDown | Encapsular motor DOCX/PDF | RF-03, RC-04, RC-05 |
| SHA-256 y reporte JSON | Identificar entradas y registrar resultados | RF-07 |
| Archivos Markdown con escritura exclusiva | Evitar sobrescritura de resultados | RF-05 |
| Monolito modular | Primer incremento sin infraestructura adicional | RC-05 |

## Correspondencia con código existente

- `src/academicos/cli.py`: interfaz, límites, resumen y códigos.
- `src/academicos/pipeline.py`: recorrido, ZIP, reportes y resultados.
- `src/academicos/converters.py`: motor documental.
- `tests/test_pipeline.py`: escenarios de recorrido y extracción con conversor simulado.
- `tests/test_integration.py`: documentos sintéticos con motor real.

## Restricciones de esta base

No se entrega un lockfile; las versiones transitivas pueden variar.
Una salida existente se omite por ruta, no por comparación de contenido. La spec 002 incorpora comparación de hashes de entrada entre documentos, sin borrar copias.
No hay ejecución paralela, reanudación persistente ni aislamiento de conversión.
El PDF puede perder disposición y estructura; el éxito técnico no certifica fidelidad documental.

## Secuencia restante

1. Completar cobertura de comportamientos especificados sin evidencia automatizada directa.
2. Instalar y ejecutar en el Mac con una copia de una muestra real.
3. Comparar contenido, listas, encabezados y tablas con los originales.
4. Registrar defectos y ajustar spec o implementación cuando proceda.
5. Cerrar 001 con evidencia; redactar 002 para OCR si ese es el siguiente objetivo.

Ampliación 003: ya hay historial persistente, actualización incremental y caché por hash/firma; sustituye las restricciones anteriores en esos aspectos.
