# 002 · Integridad, duplicados y revisión de coincidencias

Estado: alcance acordado como las tres validaciones; detección local implementable, fuentes externas pendientes.
Fecha: 2026-10-21. Amplía 001 sin cambiar la política de conservar cada Markdown.

## Distinciones de producto

Integridad: igualdad de SHA-256 del documento antes y después de su procesamiento.
Duplicidad exacta: mismo SHA-256 entre documentos de la ejecución, con referencia al primero encontrado.
Coincidencia textual local: similitud del texto extraído respecto a los documentos convertidos antes en la ejecución.
Originalidad académica: revisión de fuentes, citas y contexto por una persona; el software no certifica autoría ni ausencia de plagio.

## Requisitos

| ID | Comportamiento |
|---|---|
| VAL-01 | Calcular SHA-256 antes y después para cada PDF/DOCX procesable, incluso ante error del conversor. Registrar verificada, fallida o no_verificada. |
| VAL-02 | Si los hashes difieren, registrar error_integridad, conservar hashes y no publicar nuevo Markdown. Una salida anterior no se elimina. |
| VAL-03 | Identificar duplicados binarios en la misma ejecución por hash de entrada y referenciar el primer origen. Conservar un resultado por ruta; no borrar ni omitir copias automáticamente. |
| VAL-04 | Comparar localmente texto convertido mediante conjuntos de secuencias de cinco palabras y Jaccard. Usar minúsculas y normalización Unicode NFC; ignorar puntuación. |
| VAL-05 | Exigir al menos 30 palabras; reportar similitudes >= 0.80 con ruta, puntuación, algoritmo y hasta tres fragmentos comunes de cinco palabras. Conservar ambas salidas. |
| VAL-06 | Diferenciar no_evaluado (sin conversión o con error), texto_insuficiente, sin_referencias_previas, sin_coincidencias_sobre_umbral y coincidencias_detectadas. No tratar ninguno como prueba de originalidad. |
| VAL-07 | Marcar originalidad académica como no_evaluada y fuentes externas como no_consultadas en cada registro PDF/DOCX. No enviar documentos a servicios externos. |
| VAL-08 | Si falla lectura inicial o final, no declarar integridad verificada. Un hash inicial ausente impide detectar duplicado exacto. |

## Alcance de la evidencia

La verificación cubre el documento directo o su copia temporal extraída del ZIP durante su procesamiento.
No prueba autenticidad previa, firma digital, autoría, cambios posteriores, integridad de toda la carpeta ni ausencia de cambios transitorios restaurados entre hashes.
El formato y los metadatos pueden cambiar el hash binario sin cambiar el texto; VAL-04 ayuda a distinguir esos casos.
Las omisiones de salidas existentes se validan por hash del archivo fuente, pero no entran al corpus textual; no se certifica la vigencia del Markdown previo.
La comparación local es direccional: cada registro referencia solo documentos convertidos anteriormente en la ejecución. La ausencia de coincidencias depende del corpus y del orden.
Las referencias bibliográficas, citas y plantillas no se excluyen; pueden producir similitudes legítimas.

## Originalidad académica frente a fuentes externas — pendiente

No se implementa un detector universal ni porcentaje de plagio.
Antes de integrar fuentes externas se deben definir corpus/proveedor autorizado, permisos sobre datos, cobertura, evidencia de pasajes y revisión humana.
Las futuras coincidencias externas deberán incluir fuente, localización, fragmentos y fecha de consulta. La persona revisora distinguirá citas correctas de usos indebidos.

## Criterios de aceptación

- AC-V01: conversión normal conserva hash; conversor que altera el archivo produce error_integridad y ningún Markdown nuevo.
- AC-V02: error del conversor conserva la comprobación final; fuente desaparecida queda no_verificada.
- AC-V03: copias idénticas con distinto nombre y una copia dentro de ZIP quedan relacionadas, sin eliminar originales ni resultados.
- AC-V04: textos equivalentes con cambios de formato/caso obtienen coincidencia local aunque sus bytes difieran.
- AC-V05: textos diferentes no superan umbral; menos de 30 palabras se informa como insuficiente.
- AC-V06: al reutilizar Pipeline en otra ejecución se reinician hash y corpus; una salida omitida no se declara comparada.
- AC-V07: cada documento contiene estado no_evaluada de originalidad académica y no_consultadas de fuentes externas.

## Ampliación vigente 003

La spec 003 reemplaza la omisión por existencia con caché verificada, actualización incremental y versiones. Los estados actuales son los del README. Las copias exactas pueden reutilizar conversión entre ejecuciones; no se eliminan vistas ni originales. La comparación textual sigue limitada a conversiones nuevas de la ejecución. Un resultado reutilizado no se declara comparado. CAT-01 a CAT-12 rigen persistencia y recuperación.
