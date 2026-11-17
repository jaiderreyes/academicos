# Plan · 006

Añadir el paquete `academicos.review` con módulos independientes de la conversión
documental: `rubric` (carga y validación YAML, cálculo de nota), `javaproject`
(detección de estructura y copia temporal), `runner` (compilar y ejecutar con límites),
`checks` (verificaciones estáticas y casos externos) y `similarity_code` (normalización
y comparación). La CLI incorporará `review` con subcomandos `rubric-check`, `run`,
`compare` y `report`. Los resultados se guardan en el catálogo SQLite de la spec 003 y
se exportan con el mecanismo de reportes de la spec 004.

Dependencias: `pyyaml` para la rúbrica; Docker es requisito externo: `runner` lanza una imagen con JDK
(`docker run --rm --network none --memory --cpus --read-only`, montaje de solo lectura
de la copia temporal y `tmpfs` de trabajo) con tiempo máximo por paso. Sin Docker, los
pasos de ejecución se marcan "no verificable". Los casos de prueba se leen de una
carpeta por parcial y los criterios manuales de un archivo por estudiante.

Orden: rúbrica y cálculo (sin Java) → estructura y copia → compilación y ejecución →
verificaciones y casos externos → similitud → reportes y CLI. Se valida primero con
datos sintéticos y luego con las entregas reales ya revisadas a mano, para contrastar
la nota sugerida con la nota asignada.
