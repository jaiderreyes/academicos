# academicOS 0.5.0

Proyecto Python para transformar documentos locales en Markdown con catálogo, historial y recuperación.
Empieza por [START_HERE.md](START_HERE.md) para conocer el flujo de desarrollo guiado por especificaciones.
La spec 003 implementa el alcance aprobado: catálogo persistente, versiones y recuperación.

## Instalar en tu Mac

Requiere macOS o Linux y Python 3.11 o superior. Descomprime el proyecto y abre la terminal en `academicos`:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
academicos --help
```

Se descargan dependencias al instalar. La conversión básica usa MarkItDown local sin claves API ni servicios externos configurados.
Windows nativo no está soportado en esta edición: el bloqueo usa POSIX; puede evaluarse ejecución dentro de Linux/WSL.
No se entrega aún un lockfile de dependencias.

## Ventana de seguimiento en terminal

Ejecuta desde la carpeta del proyecto, después de instalar o actualizar con `python -m pip install -e .`:

```bash
bash scripts/academicos.sh ingest "$HOME/Documents/PruebaAcademicOS" --output "$HOME/Documents/AcademicOS-Salida" --ui live
```

El panel muestra fase, archivo actual, documentos terminados/descubiertos, nuevos/actualizados, reutilizaciones, copias exactas, errores, conflictos, tiempo y últimos resultados.
Es una interfaz de terminal en Bash o zsh; Python realiza el procesamiento y Rich dibuja el panel.
`--ui auto` es el predeterminado: panel en TTY y líneas simples si rediriges la salida. También existen `plain` y `none`.
El tiempo sigue avanzando visualmente durante una conversión, pero no se mide progreso interno del conversor.
Si hay ZIP sin completar o con errores, el total se muestra provisional; no se inventa un porcentaje.

En otra ventana de Terminal, usando academicOS instalado o el mismo lanzador:

```bash
bash scripts/academicos.sh watch --output "$HOME/Documents/AcademicOS-Salida"
```

`watch` observa la ejecución más reciente y continúa esperando futuras ejecuciones hasta Ctrl+C.
Cerrar el observador no detiene la conversión. Ctrl+C en la terminal de **ingest** sí la interrumpe, conserva avances confirmados y devuelve código 130.
Para una consulta en JSON, sin interfaz continua:

```bash
academicos watch --output "$HOME/Documents/AcademicOS-Salida" --once
```

Si un proceso murió, watch muestra que falta un escritor activo; no modifica el catálogo. La siguiente ingesta normaliza su estado como explica la spec 003.
Si la salida proviene de una versión anterior sin snapshots, watch informa que espera una ejecución de esta versión.

## Reportes de avance y resultados

Cada ejecución genera `reporte-<id>.json`, `.md` y `.csv` en la carpeta de salida.
Markdown incluye resumen y resultados por archivo. CSV permite filtrar estados y duraciones; neutraliza campos que podrían interpretarse como fórmulas en una hoja de cálculo. JSON mantiene los eventos originales, con hashes y procedencia.
Los reportes no contienen el texto completo de los documentos.

Puedes regenerarlos a partir de lo que quedó confirmado en SQLite:

```bash
academicos report --output "$HOME/Documents/AcademicOS-Salida"
academicos report --output "$HOME/Documents/AcademicOS-Salida" --run ID_DE_EJECUCION
```

Para una ejecución que sigue abierta se exportan como `reporte-<id>-parcial.*`, sin sobrescribir el reporte final. Un proceso terminado abruptamente puede seguir abierto en el catálogo hasta la próxima ingesta; el reporte lo identifica como parcial.
`seguimiento-<id>.json` guarda el último estado de la ventana; no es un historial de todas las transiciones. Los resultados confirmados permanecen en los eventos SQLite.
La duración por documento corresponde a su intento, incluyendo verificación, conversión/reutilización y publicación. No equivale exclusivamente al tiempo del motor.
La nueva interfaz conserva esquema SQLite 1 y firma de conversión de 003: actualizar desde 0.3.0 no requiere reconvertir documentos válidos.

## Procesar y retomar

### Preparar material nuevo y limpiar una prueba

Desde la carpeta del proyecto puedes copiar un archivo o una carpeta completa al
espacio de prueba y eliminar la ejecución anterior en un solo comando:

```bash
bash scripts/academicos.sh prepare "/ruta/al/material-nuevo" --workspace ./prueba --clean
bash primera_prueba.command
```

Solo se copian PDF, DOCX y ZIP; los originales no se modifican. Para limpiar únicamente
los resultados y conservar la entrada:

```bash
bash scripts/academicos.sh clean --workspace ./prueba
```

Para limpiar también las copias de entrada:

```bash
bash scripts/academicos.sh clean --workspace ./prueba --include-input
```

Prueba con una copia pequeña de tus documentos:

```bash
academicos ingest "$HOME/Documents/PruebaAcademicOS" --output "$HOME/Documents/AcademicOS-Salida"
```

Ejecuta exactamente el mismo comando para continuar o actualizar:

- Sin cambios: verifica hashes y reutiliza conversiones completas, sin llamar al conversor.
- Original modificado: genera su nueva versión y actualiza su vista Markdown; conserva versiones previas.
- Interrupción: conserva avances ya confirmados en SQLite y reintenta documentos pendientes o fallidos.
- Vista eliminada: la restaura desde un artefacto válido sin reconvertir.
- Artefacto faltante o alterado: vuelve a convertir su fuente cuando esté disponible.
- Copia o cambio de nombre: reutiliza contenido idéntico con la misma extensión y firma de conversor, conservando ubicaciones distintas.

Los archivos ZIP deben recorrerse y extraerse para comprobar sus documentos internos, aunque no necesiten reconversión.
Los archivos fuente siempre se leen para verificar su hash: no reconvertir no significa no leer.

## Consultar estado e historial

```bash
academicos status --output "$HOME/Documents/AcademicOS-Salida"
academicos history "curso/guia.docx" --source "$HOME/Documents/PruebaAcademicOS" --output "$HOME/Documents/AcademicOS-Salida"
```

`status` informa cantidades, últimas ejecuciones e intentos sin terminar. Después de una muerte abrupta, una ejecución puede aparecer `running`: al iniciar la siguiente ingesta, bajo bloqueo exclusivo, pasa a `interrupted`.
`history` devuelve versiones de esa ubicación, su hash fuente, firma del conversor y ruta de cada artefacto relativa a la salida. Una ubicación desconocida devuelve lista vacía.
Para documentos de ZIP usa la ruta virtual, por ejemplo `lecturas.zip/__zip__/tema/a.pdf`.
La consulta no necesita iniciar MarkItDown y no modifica el catálogo.

## Organización de la salida

```text
AcademicOS-Salida/
  catalogo.sqlite3
  artefactos/<hash-del-Markdown>.md
  documentos/curso/guia.docx.md
  documentos/lecturas.zip/__zip__/tema/a.pdf.md
  reporte-<ejecucion>.json
```

`documentos` es la vista actual por ubicación. `artefactos` conserva resultados por su contenido, reutilizables entre varias ubicaciones.
`catalogo.sqlite3` relaciona contenido, raíz de entrada, ubicaciones, conversiones, versiones, intentos y eventos.
Las ubicaciones se distinguen por raíz absoluta y ruta relativa; el hash identifica bytes, no un autor ni un documento conceptual.
No se eliminan resultados de fuentes desaparecidas ni versiones antiguas.
Para un respaldo completo conserva la carpeta de salida entera y tus originales. Haz la copia con academicOS detenido; no hay backup automático.

## Protección y migración

No se modifican originales. La salida debe ser una carpeta de trabajo dedicada.
Una vista Markdown se reemplaza solo si coincide con la registrada o con el nuevo resultado esperado.
Si la editas manualmente, se registra `conflicto_salida` y se conserva. Guarda tus notas en archivos separados o usa otra carpeta de salida para reconstruir.
En una salida antigua sin catálogo, un Markdown solo se reconoce si coincide con una conversión nueva verificable; si difiere, se conserva como conflicto.
No borres el catálogo para resolver un error: perderías su vínculo con las versiones. Conserva todo para diagnosticar o elige una salida nueva.
Dos escritores simultáneos sobre una salida se rechazan; macOS/Linux liberan el bloqueo al terminar el proceso.

## Validaciones y límites

- DOCX, PDF y ZIP, con subcarpetas y ZIP anidados. DOC, RAR y 7z se registran como no soportados; otros formatos se ignoran.
- Hash SHA-256 antes/después por documento procesable, incluso ante errores; cambios detectados bloquean nueva publicación.
- Copias exactas referenciadas por hash, también entre ejecuciones. No se eliminan originales ni vistas por ubicación.
- Similitud local: Jaccard de secuencias de cinco palabras; mínimo 30 palabras y umbral 0.80. Muestra hasta tres fragmentos comunes por coincidencia.
- El corpus textual solo incluye conversiones nuevas de la ejecución; resultados reutilizados no se vuelven a comparar. No se consulta Internet ni bases académicas.
- Similitud no es porcentaje de plagio. Originalidad académica permanece `no_evaluada` y fuentes externas `no_consultadas`.
- ZIP: rechazo de rutas peligrosas, enlaces, entradas duplicadas exactas y cifrado. Presupuesto global de extracción y profundidad configurable.

```bash
academicos ingest ./entrada --output ./salida --max-zip-mb 200 --max-zip-files 1000 --max-depth 2
```

Predeterminados: 500 MiB extraídos, 2000 entradas y 3 niveles ZIP.
Estos límites no aíslan al conversor ni limitan su tiempo/memoria. Prototipo para documentos propios; los archivos de terceros requieren aislamiento adicional.
La integridad comprobada cubre documento directo o copia temporal extraída durante el procesamiento, no autenticidad previa ni el ZIP contenedor entero.
Markdown no reproduce exactamente diagramación, imágenes, fórmulas o tablas complejas. No hay OCR en esta entrega.

## Resultados y códigos

Estados satisfactorios: `convertido`, `actualizado`, `reutilizado`, `restaurado`, `omitido_sin_cambios`.
Otros: `sin_texto`, `no_soportado`, `conflicto_salida`, `error_lectura`, `error_integridad`, `error_conversion`, `error_zip`.

- Código 0: sin errores, conflictos ni texto vacío; también cuando no se encontraron documentos.
- Código 1: errores por documento, conflictos o texto vacío.
- Código 2: configuración, dependencia, bloqueo o catálogo incompatible.

Los formatos no soportados no cambian por sí solos el código de salida.
Cada resultado se confirma inmediatamente en SQLite; el reporte JSON se publica al finalizar o al capturar una interrupción.
Una terminación abrupta puede impedir el reporte, pero no elimina eventos confirmados.

## Garantías de recuperación

Los artefactos y vistas se escriben en temporales, se sincronizan y se publican mediante reemplazo atómico.
Un artefacto solo se reutiliza con registro de conversión confirmado y hash válido. Temporales y artefactos huérfanos no se aceptan como caché.
Puede repetirse trabajo si el proceso murió antes de confirmar su registro. SQLite y archivos no comparten transacción; la recuperación valida y reconcilia la vista.
Se probaron interrupciones de proceso, no fallos físicos de almacenamiento.

## Desarrollo y pruebas

```bash
python -m pip install -e '.[test]'
PYTHONPATH=src python -m unittest discover -s tests -v
```

50 pruebas verificadas en Linux con Python 3.12, incluida conversión real DOCX/PDF/ZIP, recuperación tras terminación abrupta, seguimiento independiente y reportes.
Falta validar en el Mac del creador y con un corpus real. Evidencias en `docs/VALIDACION.md` , `specs/003-catalog-versions-recovery/acceptance.md` y `specs/004-terminal-monitoring-reports/acceptance.md`.
Los adaptadores propios deberían declarar `cache_key` y cambiarla ante cambios de motor/configuración; la firma alternativa por nombre de clase no detecta cambios internos.

Abre la carpeta en VS Code. Para versionar el proyecto:

```bash
git init
git add .
git commit -m "academicOS: ingesta, validación y catálogo recuperable"
```

Añade a `.gitignore` las carpetas privadas de entrada o salida que crees dentro del proyecto. No subas documentos ni catálogos personales.
# academicos
