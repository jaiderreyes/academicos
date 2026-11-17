# 004 · Seguimiento en terminal y reportes

Estado: solicitado por el creador; implementado y validado en Linux. Validación en el Mac pendiente.

## Resultado

Ver la actividad de academicOS en una terminal Bash/zsh: fase, documento actual, contadores, tiempo y últimos resultados. Poder abrir otra terminal para observar sin iniciar otro escritor y consultar/exportar reportes por ejecución.

## Requisitos

| ID | Comportamiento |
|---|---|
| UI-01 | Ingesta con panel vivo en terminal interactiva; modos auto/live/plain/none. Auto usa texto sin secuencias de control cuando no hay TTY. |
| UI-02 | Mostrar ejecución, fase, archivo actual, documentos terminados/descubiertos, conversiones nuevas, reutilizaciones, duplicados, errores y tiempo transcurrido. |
| UI-03 | No inventar porcentajes: los ZIP pueden añadir documentos. Mostrar total provisional mientras existan comprimidos sin completar o con errores de inventario. No estimar avance dentro de una conversión. |
| UI-04 | `watch --output` observa desde otra terminal, sin iniciar conversor ni modificar catálogo. Ctrl+C cierra solo el observador; `--once` emite una consulta. Detectar escritor ausente sin declarar activa una ejecución abandonada. |
| UI-05 | Guardar progreso por ejecución en snapshot atómico actualizado en transiciones y resultados; elapsed se refresca visualmente aunque el conversor siga ocupado. |
| UI-06 | Publicar reportes JSON, Markdown y CSV al terminar, también ante interrupción capturada. Poder regenerarlos desde eventos confirmados con `report --output [--run ID]`. |
| UI-07 | Registrar duración de cada intento/documento; resumir estados y listar incidencias con procedencia. CSV preparado para apertura en hoja de cálculo sin evaluar nombres como fórmulas. |
| UI-08 | Separar presentación del motor. Un error del callback de presentación no cancela documentos; no interpretar rutas como markup o secuencias de terminal. |
| UI-09 | Lanzador Bash que delega en la CLI instalada, conserva argumentos con espacios y propaga códigos de salida. |
| UI-10 | Mantener esquema SQLite 1 y firmas de conversión de 003: un cambio de interfaz no invalida las conversiones existentes. |

## Límites

Es una interfaz de terminal (TUI), no una ventana gráfica de escritorio. Bash inicia Python; Rich dibuja el panel. No hay tareas programadas, control remoto, pausa/reanudación interactiva ni ETA fiable en este incremento.
La consulta watch depende de snapshots de esta versión. Si aún no existen, espera y lo informa; no inventa datos de ejecuciones antiguas.
Un proceso muerto abruptamente puede impedir reportes finales; `report` recupera eventos confirmados. El lector no modifica el estado SQLite; la siguiente ingesta de 003 normaliza ejecuciones abandonadas.
Los snapshots no se actualizan continuamente durante una conversión bloqueante; muestran su fase, antigüedad y el reloj visual. No prueban que el conversor esté respondiendo.

## Aceptación

- AC-U01: callback recibe fases antes de convertir y resultados confirmados después; snapshot final coincide con reportes.
- AC-U02: ZIP anidado aumenta descubiertos y no muestra porcentaje definitivo prematuro; ZIP fallido mantiene advertencia.
- AC-U03: ejecutar dos veces mantiene caché y firmas; panel resume reutilización.
- AC-U04: watch consulta sin escribir catálogo y diferencia escritor vivo de ejecución abandonada.
- AC-U05: reportes Markdown/CSV/JSON contienen estados coherentes; se regeneran tras una muerte abrupta.
- AC-U06: salida redirigida no incluye ANSI; nombres con controles o markup no afectan la terminal; CSV neutraliza fórmulas.
- AC-U07: Ctrl+C de ingesta conserva eventos y reportes parciales con código 130; Ctrl+C de watch no cancela la ingesta.
- AC-U08: lanzador Bash conserva rutas con espacios y el código de salida; regresiones de 003 siguen aprobadas.
