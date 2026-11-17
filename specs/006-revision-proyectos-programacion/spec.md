# Spec 006 · Revisión de proyectos de programación

Estado: aprobada con decisiones · Fecha: 2026-11-17.

## Decisiones

- D1: los criterios manuales (informe, defensa) se puntúan en un archivo aparte que llena la persona docente; el reporte los integra sin inventar puntaje.
- D2: el código de estudiantes se ejecuta únicamente en contenedor Docker, sin red, con límites de tiempo, memoria y CPU y sistema de archivos de solo lectura salvo un directorio temporal.
- D3: el umbral de similitud de código es 0.80, configurable.
- D4: los casos de prueba viven en una carpeta aparte por parcial, referenciada desde la rúbrica.

## Problema

La persona usuaria califica entregas de programación (hoy Java, en Estructura de Datos I)
compilando y ejecutando cada proyecto a mano, contrastando el resultado con una rúbrica
escrita aparte y comparando entregas de memoria. Falta un proceso repetible que reúna
evidencia por criterio, deje trazabilidad y permita reutilizar la rúbrica en otros parciales.

## Alcance

- Una **rúbrica configurable** en archivo (YAML) con criterios, pesos, escala, condición
  mínima y tope de nota si no se cumple. La primera configuración será la del parcial
  "Bóveda de fichas": Modelado y reglas 25 %, Estructuras e integración 30 %,
  Validación y pruebas 25 %, Informe y defensa 20 %, mínimo para 3.0 y tope 2.9.
- Una **revisión de proyecto Java** por estudiante: detectar estructura (NetBeans, Maven,
  carpeta `src` o archivo único), compilar con `javac`, ejecutar la aplicación y las
  pruebas del proyecto, y registrar salida, código de salida y duración.
- **Verificaciones estáticas** declaradas en la rúbrica (por ejemplo, uso de `java.util`
  de colecciones en la versión manual, presencia de lista, pila y tres colas).
- **Casos de prueba externos** definidos por la persona usuaria: archivos de entrada y
  salida o código de salida esperados, ejecutados contra cada entrega.
- **Similitud de código** entre entregas, reutilizando el comparador de la spec 002
  sobre fuente normalizado (sin comentarios ni espacios).
- **Reporte por estudiante** (JSON, Markdown y CSV) con evidencia por criterio y una
  **nota sugerida**. La nota final siempre la decide la persona docente.
- Integración con el catálogo existente para conservar procedencia y versiones.

## Requisitos

- RF-J01: leer una rúbrica YAML y rechazar pesos que no sumen 100 %.
- RF-J02: aceptar una carpeta o ZIP por estudiante y detectar la estructura del proyecto.
- RF-J03: compilar sin modificar los originales; trabajar en una copia temporal.
- RF-J04: registrar para cada paso (compilar, ejecutar, probar) salida, código de salida
  y duración, con tiempo máximo configurable.
- RF-J05: ejecutar verificaciones estáticas declaradas en la rúbrica e informar hallazgos
  con archivo y línea.
- RF-J06: ejecutar casos de prueba externos y comparar salida o código de salida.
- RF-J07: calcular nota sugerida por criterio y total; aplicar la condición mínima y el tope.
- RF-J08: marcar como "no verificable" lo que no pudo comprobarse (sin `javac`, sin
  entrada, tiempo agotado) en lugar de puntuarlo como fallo o acierto.
- RF-J09: calcular similitud entre entregas y listar pares por encima del umbral con
  los fragmentos coincidentes; la similitud es indicio, no prueba de copia.
- RF-J10: exportar reportes por estudiante y un consolidado de curso.
- RF-J11: compilar y ejecutar el código de estudiantes solo dentro de un contenedor Docker
  (`--network none`, límites de tiempo, memoria y CPU, usuario sin privilegios, montaje
  de solo lectura de la copia). Si Docker no está disponible, marcar "no verificable".
- RF-J12: leer criterios manuales desde un archivo aparte por estudiante y sumarlos a la
  nota sugerida; si falta, el criterio queda "pendiente".
- RF-J13: cargar casos de prueba desde una carpeta por parcial indicada en la rúbrica.

## Datos y privacidad

El código y los informes de estudiantes permanecen locales. Los reportes usan el
identificador de carpeta del estudiante; no se sube nada a servicios externos.

## Fuera de alcance

Calificación automática final sin revisión, evaluación del informe escrito o de la
defensa (se registran como criterios manuales), otros lenguajes distintos de Java,
detección de plagio contra fuentes de internet, interfaz gráfica.
