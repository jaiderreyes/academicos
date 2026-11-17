# Validación de la entrega inicial

Fecha: 21 de octubre de 2026.

Se ejecutaron y aprobaron 10 pruebas en Linux con Python 3.12 y MarkItDown 0.1.8:

- Recorrido de subcarpetas y distinción entre extensiones con igual nombre.
- Conversión desde ZIP y ZIP anidado.
- Rechazo de rutas ZIP que intentan salir de la carpeta de extracción.
- Límites de tamaño y cantidad de entradas.
- Límite de anidamiento.
- Presupuesto de extracción compartido entre varios ZIP.
- Omisión de salidas existentes y continuidad ante documentos fallidos o vacíos.
- Exclusión de la salida y de enlaces simbólicos.
- Rechazo de ubicaciones de salida incompatibles.
- Integración real: DOCX generado, PDF con texto generado y DOCX dentro de ZIP convertidos con MarkItDown; se verificó contenido en los tres Markdown.

Los documentos de prueba son sintéticos. Esto comprueba el funcionamiento básico, no la fidelidad de documentos reales complejos.
No se ejecutó en el Mac ni en la Raspberry Pi del usuario. Falta validar instalación y calidad sobre una muestra real.
OCR, RAR/7z, DOC antiguo y aislamiento del conversor quedan fuera del alcance.

## Ampliación 002

Se ejecutaron y aprobaron 18 pruebas en total (las diez anteriores y ocho nuevas) con Python 3.12 y MarkItDown 0.1.8 en Linux.
Las ocho nuevas comprueban hashes y estados académicos; detección de alteración y bloqueo de salida; verificación aun si falla el conversor; archivo eliminado; duplicados por nombre y dentro de ZIP sin eliminar resultados; textos equivalentes con distintos bytes; coincidencias parciales, textos distintos y cortos; reinicio del índice y omisiones no comparadas.
La ampliación aún requiere validación en el Mac y documentos reales. No se ha ejecutado contraste con fuentes externas ni revisión de originalidad académica.

## Ampliación 003 — versión 0.3.0

35 pruebas aprobadas: 17 nuevas de persistencia/recuperación y 18 regresiones con expectativas actualizadas al nuevo comportamiento incremental.
Se verificaron cero reconversiones al repetir, una al cambiar una fuente, historial accesible, interrupción abrupta en subproceso, caché dañada/faltante, bloqueo de escritores y protección de salidas editadas.
También se inyectaron interrupciones entre publicación y confirmación, y fallo de publicación con temporal incompleto.
La integración real DOCX/PDF/ZIP incluye ahora segunda ejecución reutilizada.
Evidencia detallada: specs/003-catalog-versions-recovery/acceptance.md.
Pendiente: Mac, corpus real y rendimiento; no se incluyen OCR ni consulta de fuentes externas.

Se construyó e instaló el paquete 0.3.0 en una carpeta aislada, y se verificó la CLI instalada con DOCX/PDF/ZIP: ingesta inicial, repetición sin reconversión, actualización de un original, status e history.

## Ampliación 004 — versión 0.4.0

50 pruebas aprobadas: 15 nuevas de seguimiento/reportes y 35 regresiones.
Se probó observador en proceso independiente: lee fase de conversión; al cerrarlo con SIGINT el escritor continúa y completa su ejecución.
Se comprobó exportación desde eventos tras os._exit, reportes parciales separados, neutralización CSV, rutas con markup/control y argumentos Bash con espacios.
El panel vivo se ejecutó y revisó en terminal TTY. La caché mantiene firma pipeline-3 y SQLite conserva esquema 1.
Pendiente: terminal y documentos reales del Mac del creador.

Se construyó e instaló el paquete 0.4.0 en carpeta aislada. Se verificó con DOCX/PDF/ZIP una salida creada por la versión instalada 0.3.0: tres documentos reutilizados sin reconversión, esquema 1, watch --once, exportación MD/CSV/JSON y salida plain sin ANSI. El lanzador pasa bash -n.
