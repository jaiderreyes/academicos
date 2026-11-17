# Plan · 002

1. Añadir módulo validation.py con hash por bloques y un índice textual en memoria.
2. Envolver cada conversión con lectura SHA-256 inicial y final; publicar Markdown solo tras igualdad.
3. Mantener mapa de hashes por ejecución; anotar duplicado sin eliminar salidas.
4. Comparar solo resultados convertidos nuevos con el corpus previo; no usar Markdown antiguos de procedencia desconocida.
5. Añadir reporte por documento con integridad, duplicidad, comparación local y estado académico no evaluado.
6. Probar alteración, fallos, copias en ZIP, normalización, umbral y reinicio de estado.

Jaccard = cantidad de secuencias comunes / cantidad de secuencias en la unión; no es porcentaje de texto plagiado.
Comparación exhaustiva en memoria: adecuada para un prototipo y corpus pequeños. No hay objetivo de rendimiento validado.
Los hashes se calculan sobre bytes originales; las coincidencias se calculan sobre texto convertido.
Las referencias son rutas relativas de origen. No se asocia autoría a nombres de archivos o metadatos.
