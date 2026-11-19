"""`academicos review stack`: revisión de proyectos distribuidos con docker compose (spec 007)."""
import json
import shutil
import tempfile
from pathlib import Path

from ..similarity import UMBRAL, aplicar_sancion, cargar_base, comparar, markdown as sim_markdown
from .equipos import agrupar
from .evaluar import clonador, crear_runner, evaluar_equipo
from .reporte import exportar
from .rubrica import load_stack_rubric

EXT_BASE = (".py", ".js", ".ts", ".java", ".go", ".sql")


def add_stack_parser(rsub):
    p = rsub.add_parser("stack", help="Revisar proyectos distribuidos (docker compose, FHIR, HSB…) por equipo")
    p.add_argument("--rubrica", type=Path, required=True, help="Rúbrica por señales (p. ej. rubricas/interoperabilidad-salud.yaml)")
    p.add_argument("--curso", type=Path, required=True, help="Carpeta con una subcarpeta por estudiante")
    p.add_argument("--salida", type=Path, required=True, help="Carpeta de reportes")
    p.add_argument("--equipos", type=Path, help="YAML con equipos (lista de listas de nombres) para unir integrantes que subieron cosas distintas")
    p.add_argument("--base", type=Path, help="Repositorio de referencia del enunciado: se resta de la similitud")
    p.add_argument("--no-docker", action="store_true", help="Solo análisis estático; no ejecuta docker compose up")
    p.add_argument("--solo", action="append", default=[], metavar="TEXTO", help="Evaluar solo equipos cuyo nombre contenga TEXTO; repetible")
    p.add_argument("--umbral", type=float, default=UMBRAL, help="Umbral de similitud (0.80 por defecto)")
    p.add_argument("--sancion-similitud", type=float, default=None, metavar="PUNTAJE",
                   help="Decisión docente: nota 0.0 al equipo con una pareja de similitud >= PUNTAJE (la nota automática se conserva)")
    p.add_argument("--excepto", action="append", default=[], metavar="TEXTO", help="Equipo que no recibe la sanción; repetible")
    p.add_argument("--no-clonar", action="store_true",
                   help="No clonar los repositorios de GitHub que citan las entregas sin código")
    p.add_argument("--trabajo", type=Path, help="Carpeta de trabajo para extraer (por defecto, temporal)")
    p.add_argument("--conservar", action="store_true", help="No borrar lo extraído (para revisarlo a mano)")
    return p


def run_stack(args):
    rubrica = load_stack_rubric(args.rubrica)
    carpetas = sorted(p for p in args.curso.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not carpetas:
        raise ValueError(f"no hay subcarpetas de estudiantes en {args.curso}")
    equipos = agrupar(carpetas, args.equipos)
    if args.solo:
        equipos = [e for e in equipos if any(s.lower() in e.nombre.lower() for s in args.solo)]
        if not equipos:
            raise ValueError("--solo no coincide con ningún equipo")
    base = cargar_base(args.base, EXT_BASE) if args.base else None
    runner = crear_runner(not args.no_docker)
    if runner is not None and not runner.available():
        print("Aviso: Docker no está disponible; las pruebas de ejecución quedarán sin verificar.")
    propio = args.trabajo is None
    trabajo = args.trabajo or Path(tempfile.mkdtemp(prefix="acad-stack-"))
    resultados = []
    try:
        for eq in equipos:
            r = evaluar_equipo(rubrica, eq, trabajo, runner, base, conservar=args.conservar,
                               clonar=None if getattr(args, "no_clonar", False) else clonador())
            resultados.append(r)
            print(json.dumps({"equipo": r["equipo"], "integrantes": len(r["miembros"]), "nota": r["nota"],
                              "maximo_posible": r["maximo_posible"], "sin_proyecto": r["sin_proyecto"]},
                             ensure_ascii=False))
    finally:
        if propio and not args.conservar:
            shutil.rmtree(trabajo, ignore_errors=True)
    sim = comparar({r["equipo"]: r["_huella"] for r in resultados if "_huella" in r}, args.umbral)
    if args.sancion_similitud is not None:
        afectados = aplicar_sancion(resultados, sim, args.sancion_similitud, args.excepto)
        print(f"Sanción docente (nota 0.0) a {len(afectados)} equipo(s) con similitud >= {args.sancion_similitud:.2f}")
    salida = exportar(resultados, rubrica, args.salida, sim)
    (salida / "similitud.md").write_text(sim_markdown(sim), encoding="utf-8")
    print(f"Reporte general: {salida / 'reporte_general.md'}")
    print(f"Consolidado: {salida / 'consolidado.csv'} · reportes por equipo en {salida / 'equipos'}")
    print(f"Similitud: {len(sim['pares'])} par(es) sobre {args.umbral:.2f} → {salida / 'similitud.md'}")
    return 0
