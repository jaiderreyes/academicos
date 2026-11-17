# academicOS con desarrollo guiado por especificaciones

Esta entrega incorpora un flujo de Spec-Driven Development (SDD) al prototipo existente.
Es una estructura Markdown independiente de herramientas. No instala ni configura GitHub Spec Kit.
La especificación 001 documenta la base; 002 amplía validaciones y 003 incorpora el alcance de catálogo aprobado por el creador. La validación en el Mac y con documentos reales sigue pendiente.
No representa una definición aprobada de todo academicOS.

## Orden de lectura

1. `specs/constitution.md`: principios comunes de academicOS.
2. `specs/001-document-ingestion/spec.md`: problema, alcance y comportamiento observable.
3. `specs/001-document-ingestion/plan.md`: decisiones de implementación.
4. `specs/001-document-ingestion/tasks.md`: trabajo terminado y pendiente.
5. `specs/001-document-ingestion/acceptance.md`: escenarios y evidencias.
6. `specs/002-document-validation/`: integridad, copias exactas y comparación textual local.
7. `specs/003-catalog-versions-recovery/`: catálogo persistente, versiones y recuperación (alcance aprobado).
8. `specs/004-terminal-monitoring-reports/`: panel de seguimiento y reportes solicitados.
9. `specs/005-test-workspace/`: preparación y limpieza segura de pruebas desde la CLI.
10. `README.md`: instalación y ejecución.

## Flujo para cada funcionalidad nueva

Especificar → aclarar supuestos → diseñar → dividir en tareas → implementar → validar.

Antes de cambiar código, identifica el requisito y su criterio de aceptación.
Cuando una idea cambie el comportamiento, actualiza primero la spec y después el plan y las tareas.
No cierres tareas por haber escrito código: adjunta evidencia o marca explícitamente que falta validación.
Las decisiones rutinarias se resuelven dentro del alcance existente. Consulta al creador cuando la ambigüedad cambie el producto, sus usuarios o el tratamiento de datos.

## Ejemplo de siguiente incremento

Idea: procesar PDF escaneados.
Crear `specs/005-ocr/spec.md` con idioma español, documentos de muestra, calidad esperada, límites de recursos y estados ante fallo.
Solo después seleccionar motor OCR y elaborar su plan de integración.
No añadir OCR a 001 sin modificar su alcance explícitamente.

## Prompt para un asistente de programación

> Lee START_HERE.md, specs/constitution.md y todos los documentos de specs/001-document-ingestion , specs/002-document-validation , specs/003-catalog-versions-recovery y specs/004-terminal-monitoring-reports. Identifica las tareas pendientes. Implementa únicamente la siguiente tarea de código dentro del alcance autorizado; para validaciones que requieran mi Mac o mis documentos, entrega pasos y conserva su estado pendiente. Mantén trazabilidad entre requisito, código y evidencia. No inventes resultados ni añadas servicios externos.
