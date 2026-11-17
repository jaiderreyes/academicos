# Tareas · 006

- [x] J-01 Aprobar la spec y decidir las preguntas abiertas (D1-D4).
- [x] J-02 Definir el esquema YAML de rúbrica y la rúbrica "Bóveda de fichas".
- [x] J-03 Implementar carga, validación y cálculo de nota con tope.
- [x] J-04 Detectar estructura de proyecto Java y preparar copia temporal.
- [x] J-05 Implementar compilación y ejecución en Docker con límites y registro.
- [x] J-05b Leer criterios manuales y casos de prueba desde carpetas aparte.
- [x] J-06 Implementar verificaciones estáticas y casos de prueba externos.
- [ ] J-07 Implementar similitud de código entre entregas.
- [ ] J-08 Generar reportes por estudiante y consolidado.
- [ ] J-09 Integrar comandos CLI y catálogo.
- [ ] J-10 Pruebas automatizadas con proyectos Java sintéticos.
- [ ] J-11 Validación con las tres entregas reales ya calificadas a mano.

Nota J-05: el código y las pruebas con Docker simulado están hechos (11 pruebas). Falta la
validación en el equipo real: `scripts/validar_docker.sh --pull` debe devolver `"ok": true`
(compila, ejecuta, red bloqueada, /work solo lectura, tiempo máximo, sin contenedores huérfanos).
