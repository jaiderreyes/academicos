# Aceptación · 006

- AC-J01: una rúbrica cuyos pesos no suman 100 % se rechaza con un error claro.
- AC-J02: una entrega que no compila en su versión manual recibe tope 2.9 y el motivo
  queda en el reporte.
- AC-J03: una entrega sin `javac` disponible se marca "no verificable", no como fallo.
- AC-J04: los originales no cambian (mismo SHA-256 antes y después de la revisión).
- AC-J05: un proyecto que supera el tiempo máximo se detiene y se registra como tal.
- AC-J06: las verificaciones estáticas citan archivo y línea.
- AC-J07: dos entregas con código casi idéntico aparecen como par sobre el umbral.
- AC-J08: el reporte distingue criterios automáticos de criterios manuales (informe,
  defensa) y no inventa puntaje para los manuales.
- AC-J09: sobre las tres entregas reales, la nota sugerida queda dentro de ±0.3 de la
  nota asignada a mano, o la diferencia se explica en el reporte.
- AC-J10: el código de una entrega se ejecuta con `--network none`; un intento de red falla.
- AC-J11: sin Docker, los pasos de ejecución se marcan "no verificable" y la rúbrica
  estática igual se evalúa.
- AC-J12: un criterio manual sin puntuar queda "pendiente" y el total se muestra parcial.
- AC-J13: los casos de prueba se toman de la carpeta del parcial, no del proyecto del estudiante.
