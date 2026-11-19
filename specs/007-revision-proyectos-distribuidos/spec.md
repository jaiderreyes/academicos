# Spec 007 — Revisión de proyectos distribuidos (docker compose)

Extiende la spec 006 (Java por casos de salida) a parciales donde cada equipo entrega un sistema con
`docker compose`, base de datos distribuida, FHIR/HSB e informe. Primer uso: parcial «Plataforma
distribuida de interoperabilidad en salud» (Sistemas Distribuidos, UAJS).

## Decisiones docentes
- Se analiza código, `docker-compose.yml` e informe **y** se intenta `docker compose up` aislado.
- Se califica **por equipo** (2 estudiantes). Entregas con exactamente los mismos archivos = mismo equipo;
  `--equipos equipos.yaml` une integrantes que subieron cosas distintas.
- Si la evidencia muestra el elemento, cuenta como excelente. Sustentación individual (0,15) = ajuste docente.
- Similitud entre equipos con base = repositorio de referencia `historia-clinica-distribuida`.

## Requisitos
- RS-01 Rúbrica YAML por señales (`rubricas/interoperabilidad-salud.yaml`): 13 criterios que suman 5,0 + bonus 0,25.
- RS-02 Tipos de señal: archivo, contenido, compose, informe, ejecución, git, manual; alternativas `o:` (archivo o informe).
- RS-03 Extracción segura de zip/rar/7z/tar (anidados, sin salir de la carpeta de trabajo, sin enlaces, con tope de tamaño).
- RS-04 Nunca se ejecuta lo entregado salvo `docker compose` y solo si el compose no pide privilegios del anfitrión
  (privileged, network host, docker.sock, cap_add, montajes fuera del proyecto). Siempre `down -v`.
- RS-05 Lo que no se puede verificar (sin Docker, informe ilegible, sin `.git`) queda «sin verificar»: no suma ni resta.
- RS-06 Reportes: por equipo, general, `consolidado.csv` (una fila por estudiante), `similitud.md`.
- RS-07 Sanción por similitud (`--sancion-similitud`, `--excepto`) reversible: la nota automática se conserva.

## Criterios de aceptación
- AC-S01 La rúbrica real carga y suma 5,0 (`test_rubrica_real_suma_5`).
- AC-S02 Zip anidado y zip-slip no escapan de la carpeta de trabajo (`test_extraer_zip_anidado_y_zip_slip`).
- AC-S03 Compose riesgoso no se ejecuta y se informa (`test_compose_riesgoso_no_se_ejecuta`).
- AC-S04 `docker compose down -v` se ejecuta aunque `up` falle (`test_ejecucion_up_falla_y_baja`).
- AC-S05 Sin Docker, las señales de ejecución quedan sin verificar (`test_sin_docker_queda_sin_verificar`).
- AC-S06 Entregas idénticas forman un solo equipo; el YAML une integrantes (`test_agrupar_por_contenido_y_yaml`).
- AC-S07 Informe ilegible → señales del informe sin verificar (`test_informe_ilegible_deja_sin_verificar`).
- AC-S08 Curso completo en modo estático genera reportes y aplica sanción (`test_cli_curso_sin_docker_con_sancion`).

## Fuera de alcance (pendiente)
- Persistencia en `revisiones.sqlite3` (el esquema actual es de la rúbrica de Java).
- Probado en esta sesión solo con un doble de Docker; la primera corrida real en tu Mac es la verificación de `up`.
