# Evidencia de aceptación · 003

Fecha: 2026-10-21. Pruebas: `tests/test_catalog_recovery.py`, 17 nuevas, junto a 18 regresiones actualizadas al alcance 003.
Total: 35 pruebas aprobadas en Linux/Python 3.12 con MarkItDown 0.1.8.

| Criterio | Evidencia | Resultado |
|---|---|---|
| AC-C01 | test_repeat_converts_zero_and_events_persist | Dos conversiones iniciales; cero llamadas posteriores y cuatro eventos persistentes. |
| AC-C02 | test_only_changed_document_updates_with_history | Una conversión al cambiar una fuente; dos versiones recuperables y otra fuente omitida sin cambios. |
| AC-C03 | test_hard_exit_recovers_committed_work_and_retries_inflight | Subproceso termina con os._exit(23) durante segundo archivo; siguiente ejecución convierte solo el segundo. |
| AC-C04 | test_missing_view_is_restored_without_conversion; test_missing_and_corrupted_artifact_are_regenerated | Restaura vista sin conversor; regenera artefactos faltantes/alterados. |
| AC-C05 | test_failed_update_preserves_previous_output_and_version; test_manual_output_and_unregistered_output_are_preserved | Conserva salida válida ante fallo y protege ediciones manuales/salidas ajenas. |
| AC-C06 | test_renamed_source_reuses_content_and_records_new_location; test_converter_signature_invalidates_cache | Cambio de nombre reutiliza; cambio de firma reconvierte. |
| AC-C07 | test_hard_exit_recovers_committed_work_and_retries_inflight | Evento confirmado accesible aun sin reporte final. |
| AC-C08 | test_lock_blocks_second_writer; test_unknown_schema_and_foreign_database_are_rejected | Rechaza escritor adicional, esquema futuro y base ajena. |
| AC-C09 | test_nested_documents_are_incremental_when_archive_changes | Modificar un documento dentro del ZIP reconvierte solo ese documento. |

Casos adicionales:

- Interrupción entre artefacto y registro: no acepta huérfano; reintenta.
- Interrupción entre vista y vinculación: reconcilia desde conversión confirmada sin reconvertir.
- Fallo simulado de publicación: conserva vista previa; ignora temporal incompleto al retomar.
- `status` e `history` consultan estado y versiones sin iniciar el conversor.
- Integración con motor real: DOCX/PDF/ZIP y segunda ejecución sin reconversión.

Los casos usan documentos sintéticos. No se certifican fallos de hardware, sistemas de archivos de red, rendimiento en grandes corpus ni calidad con documentos reales. Validación en el Mac pendiente, C-08.
