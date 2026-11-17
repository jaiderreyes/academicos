# Plan técnico · 003

- `catalog.py`: SQLite, transacciones, consultas, historial y versión de esquema.
- `storage.py`: publicación atómica y bloqueo exclusivo POSIX (macOS/Linux).
- `pipeline.py`: hashes, selección de caché, conversión y recuperación de vistas.
- `converters.py`: firma de versión/configuración.
- `cli.py`: consultas `status` y `history` y códigos de conflicto.

Carpeta de salida:

- `catalogo.sqlite3`: estado e historial.
- `artefactos/<hash-Markdown>.md`: versiones completas por contenido.
- `documentos/<ruta-fuente>.md`: vista actual reconocida por ubicación.
- `reporte-<ejecución>.json`: resultados de una ejecución.

Cada inicio de documento y resultado se confirman inmediatamente. Una interrupción abrupta deja la ejecución en running; el próximo escritor, ya bajo bloqueo, la marca interrupted y sus intentos sin terminar como interrupted.
El historial relaciona ubicaciones y conversiones, manteniendo las versiones aunque cambie la fuente o falle su actualización.
La caché exige hash fuente, sufijo, firma y hash del artefacto. Las copias exactas pueden reutilizar el artefacto pero conservan vistas por ubicación.

Migración desde entregas anteriores: no existe catálogo previo que importar. Se generan artefactos verificables y se reconoce una vista antigua solo si coincide con el nuevo resultado. Si difiere, se preserva y se informa conflicto; también puede empezarse con otra carpeta de salida.
