# 001 · Ingesta documental a Markdown

Estado: borrador revisable del incremento inicial. La spec 002 amplía integridad y detección de copias; ante diferencias sobre esos aspectos, rige 002.
Fecha: 2026-10-21.

## Problema y resultado esperado

El creador de academicOS tiene documentos Word y PDF distribuidos entre carpetas y comprimidos.
Necesita reunir su contenido textual en Markdown reutilizable, preservando fuentes y sabiendo qué se convirtió y qué requiere revisión.

## Usuario inicial y supuestos

Un usuario ejecuta la herramienta desde terminal en su Mac, sobre documentos propios.
Python es la implementación inicial. Se usa una carpeta de entrada y otra de salida.
Esta edición es local y monousuario; no presupone el alcance final de academicOS.
Las conversiones no se ejecutan simultáneamente contra la misma salida.

## Historias de usuario

- HU-01: Como docente e investigador, quiero convertir documentos de varias subcarpetas con una ejecución para reducir trabajo manual.
- HU-02: Quiero incluir documentos dentro de ZIP sin alterar mis originales.
- HU-03: Quiero identificar conversiones, errores y documentos sin texto para revisar los casos pendientes.
- HU-04: Quiero repetir una ejecución sin sobrescribir mis Markdown existentes.

## Requisitos funcionales

| ID | Comportamiento requerido |
|---|---|
| RF-01 | Recorrer subcarpetas y seleccionar PDF, DOCX y ZIP sin distinguir mayúsculas en la extensión. |
| RF-02 | Extraer ZIP temporalmente; permitir ZIP anidados dentro de límites configurables. |
| RF-03 | Generar un Markdown por documento con texto no vacío, manteniendo rutas y extensión fuente en el nombre. |
| RF-04 | Conservar sin cambios los archivos originales. |
| RF-05 | Omitir Markdown existentes; registrar la omisión sin afirmar que el contenido está actualizado. |
| RF-06 | Continuar con otros documentos tras errores de conversión o de un ZIP. |
| RF-07 | Emitir un reporte JSON por ejecución con origen relativo y estado; incluir salida y SHA-256 en conversiones y omisiones existentes. |
| RF-08 | Marcar texto vacío como `sin_texto`; no crear su Markdown y sugerir revisión por posible OCR. |
| RF-09 | Registrar DOC, RAR y 7z como `no_soportado`; ignorar otros formatos. |
| RF-10 | Proporcionar comando de terminal con entrada, salida y límites ZIP; resumir estados y devolver códigos de salida documentados. |

## Requisitos de calidad y protección

| ID | Comportamiento requerido |
|---|---|
| RC-01 | Rechazar rutas ZIP absolutas, segmentos `..`, nombres con barra inversa o `:`, enlaces ZIP, duplicados exactos y ZIP cifrados. |
| RC-02 | Limitar entradas y bytes ZIP globalmente por ejecución, y profundidad por cadena de anidamiento. |
| RC-03 | Excluir salida y enlaces simbólicos del recorrido; rechazar salida igual a entrada o que la contenga. |
| RC-04 | Ejecutar la conversión básica localmente, sin claves API ni proveedores externos configurados. La instalación sí puede necesitar red. |
| RC-05 | Permitir sustituir el conversor mediante un adaptador sin cambiar el recorrido de carpetas. |

## Convenciones observables

- `curso/guia.docx` → `documentos/curso/guia.docx.md`.
- `lecturas.zip` con `tema/a.pdf` → `documentos/lecturas.zip/__zip__/tema/a.pdf.md`.
- Reporte: `reporte-<identificador>.json`.
- Estados: `convertido`, `omitido_existente`, `sin_texto`, `no_soportado`, `error_conversion`, `error_zip`. La ampliación 002 añade `error_lectura` y `error_integridad`.
- Códigos CLI: 0 sin errores ni texto vacío; 1 ante errores parciales o texto vacío; 2 ante configuración inválida o dependencia ausente.
- Formatos no soportados no causan por sí solos código 1. Una entrada sin documentos produce reporte vacío y código 0.
- Límites iniciales: 2000 entradas ZIP, 500 MiB extraídos acumulados y 3 niveles ZIP.

## Fuera de alcance

OCR; DOC antiguo; RAR/7z; documentos cifrados; sincronización; eliminación automática de duplicados; actualización incremental; extracción de imágenes; fidelidad de diseño; interfaz web; múltiples usuarios; búsqueda; agentes; RAG.
Los límites ZIP no son un sandbox del conversor: aislamiento, timeout y límites de memoria son una ampliación posterior.

## Condición de cierre

Comprobar los criterios de acceptance.md, incluyendo una muestra real y la ejecución en el Mac del creador.
El prototipo ya tiene pruebas sintéticas; la aceptación completa sigue pendiente.

## Decisiones abiertas para futuras specs

Alcance personal o multiusuario; prioridad entre investigación y docencia; calidad mínima de OCR; conservación de imágenes; política de datos para IA externa.
No bloquean el alcance local definido en este incremento.

## Ampliación vigente 003

La spec 003 reemplaza la omisión por existencia con caché verificada, actualización incremental y versiones. Los estados actuales son los del README. Las copias exactas pueden reutilizar conversión entre ejecuciones; no se eliminan vistas ni originales. La comparación textual sigue limitada a conversiones nuevas de la ejecución. Un resultado reutilizado no se declara comparado. CAT-01 a CAT-12 rigen persistencia y recuperación.
