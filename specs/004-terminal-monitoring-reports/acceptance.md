# Evidencia · 004

Fecha: 2026-10-21. Conjunto completo: 50 pruebas aprobadas en Linux/Python 3.12, MarkItDown 0.1.8 y Rich 14.3.4.
15 pruebas nuevas en tests/test_monitoring_reports.py, más 35 regresiones.

| Criterio | Evidencia | Resultado |
|---|---|---|
| AC-U01 | test_phases_before_conversion_and_final_counts | Fase visible antes de la conversión, estado activo comprobado bajo bloqueo, resultado y duración confirmados. |
| AC-U02 | test_zip_total_is_provisional_until_nested_archive_finished; test_bad_zip_never_claims_complete_inventory | Descubrimiento dinámico y ausencia de porcentaje definitivo con ZIP incompleto/fallido. |
| AC-U03 | test_repeat_reuses_existing_cache_and_summary | Sin reconversión; caché conservada y reutilización resumida. |
| AC-U04 | test_watch_once_is_read_only_and_abandoned_run_is_detected; test_separate_watch_can_close_while_writer_keeps_running | Observación desde otro proceso y detección de escritor ausente; consulta no cambia catálogo ni snapshot. |
| AC-U05 | test_report_formats_and_csv_formula_protection; test_report_regeneration_after_hard_exit_uses_confirmed_events; test_cli_report_exports_selected_run; test_running_export_has_partial_name_separate_from_final | Exporta resultados confirmados y separa nombres parciales/finales. |
| AC-U06 | test_plain_and_rendering_do_not_interpret_control_codes_or_markup; test_report_formats_and_csv_formula_protection | Texto sin ANSI, rutas sin markup activo y CSV preparado contra fórmulas. |
| AC-U07 | test_ctrl_c_ingestion_returns_130_and_saves_partial_reports; test_ctrl_c_watch_does_not_change_completed_ingestion; test_separate_watch_can_close_while_writer_keeps_running | Código 130; cerrar observador deja escritor en marcha y luego este finaliza correctamente. |
| AC-U08 | test_bash_launcher_preserves_spaces_and_exit_code y regresiones de 003 | Lanzador preserva argumentos y código; recuperación/caché anteriores siguen pasando. |

Además se ejecutó y revisó el panel vivo en terminal TTY: dos documentos, resultado final 2/2, contadores y tabla de últimos resultados sin errores.
Los documentos y fallos son sintéticos. Falta probar terminal, fuentes y calidad de conversión en el Mac del creador. No hay garantía de ETA ni porcentaje interno del conversor.
