# Proyecto academicOS

## Visión inicial propuesta

Un espacio de trabajo para organizar y reutilizar conocimiento académico: docencia, investigación y gestión de proyectos.
Se parte de una biblioteca local procesable y trazable. El alcance definitivo de academicOS se definirá con su creador.

## Primer módulo: ingesta documental

Entrada: carpetas locales con DOCX, PDF y ZIP.
Salida: Markdown por documento y reporte JSON por ejecución.
Criterios: preservar originales, continuar ante errores individuales, controlar extracción y mantener procedencia.

## Arquitectura del código

- `cli.py`: argumentos, resumen y códigos de salida.
- `pipeline.py`: recorrido, extracción temporal, límites, trazabilidad y escritura.
- `converters.py`: adaptador de MarkItDown; sustituible por otro motor sin cambiar el recorrido.
- `tests/`: pruebas del pipeline e integración documental.

El pipeline recibe un objeto con `convert(Path) -> str`, lo que permite incorporar un adaptador de Docling u otro conversor después.
La primera versión es un monolito modular en Python: un único proyecto con responsabilidades separadas.

## Hoja de ruta propuesta

| Incremento | Resultado | Condición para cerrarlo |
|---|---|---|
| 0.1 Ingesta | DOCX/PDF/ZIP a Markdown | Validar con una muestra real del usuario |
| 0.2 Calidad e inventario | OCR, SQLite, historial y actualización incremental | Reprocesar solo lo necesario y revisar escaneos |
| 0.3 Biblioteca | Metadatos por curso, tema y proyecto; búsqueda textual | Encontrar fuentes y recuperar originales |
| 0.4 Asistencia con IA | Preguntas sobre documentos con referencias | Respuestas verificables contra fuentes |
| 0.5 Experiencia de uso | Interfaz y tareas académicas priorizadas | Validar el flujo docente e investigador |

Estas etapas no son funcionalidades ya implementadas ni compromisos de calendario.

## Decisiones pendientes

- ¿academicOS será personal, institucional o multiusuario?
- ¿La prioridad posterior es investigación, docencia o seguimiento de proyectos?
- ¿Se conservarán imágenes y tablas complejas como recursos externos?
- ¿Qué documentos pueden procesarse con proveedores externos si después se integra IA?

## Ejecución sugerida

Desarrollo y conversiones iniciales en el Mac. Evaluar Raspberry Pi como ejecutor de tareas ligeras cuando se mida el consumo real.
No se requieren Docker, Kubernetes, Go ni una base vectorial para este primer incremento.

## Ampliación de validación

La spec 002 añade verificación de integridad antes/después, detección de copias exactas sin borrarlas y coincidencias textuales locales. Se implementa `src/academicos/validation.py`. No certifica originalidad académica; contraste externo pendiente.

## Incremento 0.3.0 — spec 003 aprobada

Catálogo SQLite, conversión incremental, artefactos e historial, registro por documento, escritura atómica y recuperación de interrupciones. Nuevos módulos catalog.py y storage.py; comandos status e history. El OCR y la búsqueda siguen pendientes. Ver la spec 003 y README para el comportamiento vigente.

## Incremento 0.4.0 — seguimiento solicitado

Spec 004: panel de terminal, observador watch, reportes MD/CSV/JSON y lanzador Bash. Módulos tracking.py, terminal.py y reports.py. Se conserva el esquema y la firma de conversión de 003.
