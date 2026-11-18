# Revisión de proyectos de programación (Java)

Spec 006. Todo es local; los originales no se modifican (se compara SHA-256 antes y después).

## Flujo

1. **Rúbrica** (`rubricas/<parcial>.yaml`): criterios con peso, niveles acumulativos
   (deficiente / regular / bueno / excelente), requisitos, verificaciones estáticas,
   carpeta de `casos` y `ejecucion.clase_principal`. Valídala con:
   `academicos review rubric-check rubricas/boveda-fichas.yaml`
2. **Casos** (`casos/<parcial>/casos.yaml` + archivos de datos): se toman de la carpeta del
   parcial, no del proyecto del estudiante. La invocación y la medición de Modelado y
   Validación salen de la rúbrica y del enunciado.
3. **Docker**: compilar y ejecutar solo ocurre en contenedor (`--network none`, sin
   privilegios, solo lectura). Prueba el aislamiento con `academicos review docker-check --pull`.
   Sin Docker esos pasos quedan "no verificable", nunca como fallo.
4. **Manuales** (`manuales/<carpeta del estudiante>.yaml`, ver `manuales/EJEMPLO.yaml`):
   puntajes de criterios manuales (informe, defensa), `ajustes` con `motivo` y observaciones.
   Esta carpeta no se sube a GitHub.

## Comandos

```
academicos review run    --rubrica R --estudiante CARPETA --salida reportes [--manuales manuales] [--casos DIR]
academicos review course --rubrica R --curso CARPETA_CURSO --salida reportes [--umbral 0.80]
```

`course` genera un reporte por estudiante (`.md` y `.json`), `consolidado.csv` y `similitud.md`.

## Cómo leer el resultado

- **Nivel confirmado**: el más alto cuyos requisitos están todos verificados. La nota
  automática es el límite inferior de ese nivel.
- **Pendiente de tu revisión**: el nivel "excelente" solo lo confirma la persona docente
  (regístralo en `ajustes`). Un criterio con evidencia sin verificar queda pendiente.
- **Condición mínima**: si no se cumple, la nota tiene tope 2.9 y el motivo queda escrito.
  Una nota con criterios pendientes se rotula PARCIAL.
- **Similitud**: Jaccard de n-gramas de 5 tokens (literal y con identificadores
  normalizados), umbral 0.80. Es un indicio para revisar, no prueba de copia.
