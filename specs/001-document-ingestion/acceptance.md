# Criterios de aceptación y trazabilidad · 001

Fecha del inventario: 2026-10-21. Las pruebas citadas se ejecutaron en la entrega del prototipo anterior.
`Parcial` indica que hay implementación o evidencia limitada, pero aún falta validación específica.

| ID | Dado / Cuando / Entonces | Requisitos | Evidencia actual y estado |
|---|---|---|---|
| AC-01 | Dada una subcarpeta con DOCX y PDF del mismo nombre, al procesarla aparecen dos Markdown distintos con contenido esperado. | RF-01, RF-03 | `test_recursive_and_distinct_extensions`, `test_word_pdf_and_zip_with_real_converter`: comprobado con muestras sintéticas; mayúsculas pendientes. |
| AC-02 | Dado un ZIP con otro ZIP, al procesarlo conserva el espacio de nombres y encuentra el documento interior. | RF-02, RF-03 | `test_zip_and_nested_zip`: comprobado con conversor simulado. |
| AC-03 | Dados originales y una salida previa, al repetir la ingesta los Markdown previos permanecen intactos y se informa omisión. | RF-04, RF-05 | `test_existing_output_and_errors`: comprobado para salida; integridad por hash de originales pendiente en muestra real. |
| AC-04 | Dados un documento fallido, otro vacío y otro correcto, al procesarlos se registra cada resultado sin detener los demás. | RF-06, RF-08 | `test_existing_output_and_errors`: comprobado con conversor simulado. |
| AC-05 | Dado un ZIP con ruta ../, al procesarlo se rechaza sin escribir fuera de temporales. Otras variantes prohibidas también deben rechazarse. | RC-01 | `test_reject_traversal_before_conversion`: parcial; cifrado, enlaces y duplicados requieren pruebas específicas. |
| AC-06 | Dados ZIP que exceden presupuesto o anidamiento, al procesarlos se registra error y no se supera la extracción permitida. | RC-02 | Pruebas `test_size_and_count_limits`, `test_depth_limit`, `test_global_budget_across_archives`: comprobado para casos sintéticos. |
| AC-07 | Dada salida dentro de entrada y un enlace a archivo externo, al procesar se excluyen; salida igual o ancestro se rechaza. | RC-03 | `test_output_excluded_and_symlinks_skipped`, `test_invalid_output`: comprobado para esos casos. |
| AC-08 | Dada una ejecución, al finalizar existe reporte con campos previstos, estados y hash cuando corresponda. | RF-07 | Integración comprueba existencia; aserciones completas de campos y hash pendientes. |
| AC-09 | Dados DOC/RAR/7z y archivos ajenos al alcance, al procesarlos se distingue no soportado de ignorado. | RF-09 | Implementado; prueba específica pendiente. |
| AC-10 | Dadas ejecuciones correctas, parciales e inválidas, la CLI entrega códigos 0, 1 y 2 respectivamente. | RF-10 | Ayuda CLI comprobada; automatización de códigos pendiente. |
| AC-11 | Dada instalación en el Mac, al convertir una muestra sin claves API funciona localmente y se revisa la calidad del contenido. | RF-03, RC-04 | Integración sintética Linux comprobada; Mac y muestra real pendientes. |
| AC-12 | Dado un conversor con contrato convert(Path) -> str, el pipeline lo utiliza sin depender de MarkItDown. | RC-05 | `FakeConverter` en las nueve pruebas del pipeline: comprobado. |

## Protocolo de validación en el Mac

1. Copiar una muestra pequeña a una carpeta de prueba y registrar SHA-256 de los originales.
2. Instalar según README y registrar Python y versión instalada de MarkItDown.
3. Ejecutar ingesta hacia una carpeta nueva; conservar reporte y código de salida.
4. Comparar títulos, párrafos, listas, tablas y caracteres españoles con las fuentes.
5. Confirmar que los hashes de originales no cambiaron y que una repetición no sobrescribe Markdown.
6. Registrar por criterio: resultado, evidencia y defecto si lo hay. No incluir documentos privados en Git.

Cierre: todos los criterios aplicables cuentan con evidencia; cualquier desviación se registra y se resuelve o se modifica explícitamente el alcance. Ninguna marca de implementación sustituye aceptación.
