# 003 · Catálogo persistente, versiones y recuperación

Estado: alcance aprobado; implementación y validación automatizada completas. Validación en el Mac/corpus real pendiente.
Fecha: 2026-10-21. Amplía 001 y 002; reemplaza la omisión incondicional de Markdown existentes.

## Objetivo

Recordar el trabajo completado entre ejecuciones, actualizar documentos modificados y retomar una ejecución interrumpida sin aceptar resultados incompletos.

## Requisitos

| ID | Comportamiento observable |
|---|---|
| CAT-01 | Mantener catálogo SQLite en la salida con ejecuciones, contenidos, ubicaciones, conversiones, versiones y eventos por documento. |
| CAT-02 | Identificar contenido por SHA-256 y ubicación por raíz de entrada absoluta + ruta relativa, incluyendo la ruta virtual de ZIP. Mover o copiar bytes idénticos permite reutilizar conversión, sin asumir que son el mismo documento conceptual. |
| CAT-03 | Reutilizar una conversión solo si coincide hash fuente, extensión y firma del conversor/configuración; verificar la existencia y hash de su artefacto Markdown. |
| CAT-04 | Actualizar la vista Markdown del documento modificado y conservar artefactos e historial anteriores; no reconvertir documentos que no cambiaron. |
| CAT-05 | Persistir inicio y resultado por documento. Las ejecuciones interrumpidas retienen eventos y conversiones ya confirmadas. Retomar mediante el mismo comando; reintentar documentos incompletos o fallidos. |
| CAT-06 | Publicar artefactos, vistas Markdown y reportes con archivo temporal, sincronización y reemplazo atómico. Un temporal o artefacto huérfano sin registro confirmado no cuenta como conversión válida. |
| CAT-07 | Recuperar la vista actual si falta pero hay artefacto válido; regenerar si el artefacto registrado falta o está alterado. |
| CAT-08 | Proteger salidas preexistentes no reconocidas o editadas manualmente: registrar conflicto y conservarlas si no coinciden con el resultado esperado ni con la vista previamente registrada. |
| CAT-09 | Evitar dos escritores simultáneos sobre una salida con bloqueo de proceso liberado por el SO al finalizar, incluso ante muerte abrupta. |
| CAT-10 | Mantener hashes antes/después y estados de originalidad de 002, incluso cuando se reutiliza una conversión. Detectar copias exactas entre ejecuciones. |
| CAT-11 | Exponer consulta de estado del catálogo y documentar cómo obtener historial. No borrar originales, versiones ni resultados de archivos que desaparecen. |
| CAT-12 | Versionar esquema y rechazar una versión de catálogo no soportada. No adoptar silenciosamente una base ajena. |

## Firma del conversor

MarkItDown: versión instalada + configuración básica + versión del pipeline.
Adaptadores propios: pueden declarar `cache_key` estable que debe cambiar cuando cambien motor o configuración. En su ausencia se usa el tipo cualificado; esta alternativa no detecta cambios internos y se documenta.

## Persistencia y límites

SQLite y el sistema de archivos no comparten una transacción. Se publican artefactos completos antes de registrar conversiones; después se actualiza la vista y su vinculación. Al retomar se valida el artefacto y se reconcilia una vista cuyo hash coincide.
Puede quedar un artefacto huérfano si el proceso muere antes de confirmar su registro; ese documento se reintenta. No se promete conversión exactamente una vez del trabajo no confirmado.
Se garantiza recuperación probada ante interrupción de proceso; no se certifica recuperación de fallo de hardware, volumen de red o corrupción total de disco.
La raíz de entrada delimita ubicaciones; un mismo contenido puede reaprovecharse entre raíces con ubicaciones distintas.
La comparación textual local sigue limitada al corpus de documentos convertidos nuevos en una ejecución; no se convierte en búsqueda persistente.
No hay OCR, búsqueda FTS, servidor, sincronización, recolección de artefactos ni backups automáticos en este incremento.

## Criterios de aceptación principales

- AC-C01: primera ejecución convierte dos documentos; segunda sin cambios realiza cero llamadas al conversor.
- AC-C02: modificar uno de esos documentos provoca exactamente una conversión y deja accesibles los dos resultados históricos de su ubicación.
- AC-C03: interrumpir durante el segundo documento y retomar reutiliza el primero y reintenta el segundo; no acepta un temporal como resultado válido.
- AC-C04: recuperar vista eliminada sin reconvertir; regenerar artefacto faltante o alterado.
- AC-C05: fallo al actualizar conserva vista anterior; edición manual produce conflicto sin sobrescritura.
- AC-C06: mover contenido conserva identidad por hash y reutiliza conversión; cambio de firma reconvierte.
- AC-C07: eventos de avance se conservan en SQLite aun si no llegó a emitirse el reporte final.
- AC-C08: segundo escritor queda bloqueado; esquema desconocido se rechaza.
- AC-C09: documentos dentro de ZIP respetan las mismas reglas incrementales.
