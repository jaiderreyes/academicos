# Evidencia · 002

Fecha: 2026-10-21. Ocho pruebas nuevas aprobadas; conjunto completo de 18 pruebas aprobado, incluida integración real DOCX/PDF/ZIP.

| Criterio | Evidencia en tests/test_validation.py | Estado |
|---|---|---|
| AC-V01 | test_unchanged_integrity_and_academic_status; test_converter_modification_blocks_output | Aprobado sintético |
| AC-V02 | test_converter_failure_still_verifies_source; test_disappearing_source_never_claims_integrity | Aprobado sintético |
| AC-V03 | test_duplicates_across_names_and_zip_preserve_results | Aprobado sintético |
| AC-V04 | test_text_equivalent_but_different_bytes; test_partial_similarity_and_unrelated_or_short_text | Aprobado sintético |
| AC-V05 | test_partial_similarity_and_unrelated_or_short_text | Aprobado sintético |
| AC-V06 | test_new_run_resets_state_and_existing_outputs_not_compared | Aprobado sintético |
| AC-V07 | test_unchanged_integrity_and_academic_status | Aprobado para documento normal; los campos se inicializan por documento, incluso ante fallos |

Pendiente: muestra real, Mac, cobertura de fuentes externas y valoración humana. No se declara cerrada la evaluación académica.

Ampliación 003: la prueba de copias exactas ahora comprueba una conversión y reutilización de otras dos vistas; la prueba de repetición espera omitido_sin_cambios. El índice textual se reinicia pero la identidad binaria persiste.
