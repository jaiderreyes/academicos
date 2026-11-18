"""Subcomando `academicos review ...` (spec 006, J-09)."""
import json
from pathlib import Path

from .cases import CaseError, load_cases
from .evaluate import evaluar_entrega
from .levels import ids_desconocidos
from .report import export_course, export_student
from .rubric import RubricError, load_rubric
from .runner import DEFAULT_IMAGE, DockerRunner, selfcheck


def add_parser(sub):
    rev = sub.add_parser("review", help="Revisión de proyectos de programación (Java)")
    rsub = rev.add_subparsers(dest="review_command", required=True)

    chk = rsub.add_parser("rubric-check", help="Validar una rúbrica YAML")
    chk.add_argument("rubrica", type=Path)

    dck = rsub.add_parser("docker-check", help="Validar el aislamiento en Docker de este equipo")
    dck.add_argument("--image", default=DEFAULT_IMAGE)
    dck.add_argument("--pull", action="store_true", help="Descargar la imagen si falta")

    def comunes(p):
        p.add_argument("--rubrica", type=Path, required=True)
        p.add_argument("--salida", type=Path, required=True, help="Carpeta de reportes")
        p.add_argument("--manuales", type=Path, help="Carpeta con <estudiante>.yaml de criterios manuales")
        p.add_argument("--casos", type=Path, help="Carpeta de casos (por defecto, la de la rúbrica)")
        p.add_argument("--image", default=DEFAULT_IMAGE)
        p.add_argument("--no-docker", action="store_true",
                       help="Solo análisis estático; compilar y ejecutar queda sin verificar")

    run = rsub.add_parser("run", help="Evaluar un estudiante")
    comunes(run)
    run.add_argument("--estudiante", type=Path, required=True, help="Carpeta del estudiante")
    run.add_argument("--proyecto", type=Path, help="Carpeta, .java o .zip concreto a evaluar")

    course = rsub.add_parser("course", help="Evaluar todas las carpetas de un curso")
    comunes(course)
    course.add_argument("--curso", type=Path, required=True, help="Carpeta con una subcarpeta por estudiante")
    return rev


def _runner(args):
    if args.no_docker:
        return DockerRunner(image=args.image, docker="__sin_docker__")
    return DockerRunner(image=args.image)


def _casos_dir(args, rubrica):
    if args.casos:
        return args.casos
    if rubrica.casos:
        return (args.rubrica.parent / rubrica.casos).resolve()
    return None


def _manual(args, nombre):
    if not args.manuales:
        return None
    for ext in (".yaml", ".yml"):
        p = args.manuales / f"{nombre}{ext}"
        if p.is_file():
            return p
    return None


def _resumen(r):
    k = r.get("calificacion")
    clave = "nota_sugerida" if k and k["completo"] else "nota_parcial"
    return {"estudiante": r["estudiante"], "proyecto": r.get("proyecto"),
            clave: k and k["nota_sugerida"], "completa": k and k["completo"],
            "compilacion": r.get("compilacion", {}).get("status"), "errores": r["errores"]}


def run_review(args):
    if args.review_command == "rubric-check":
        r = load_rubric(args.rubrica)
        ids_casos, nota = [], None
        if r.casos:
            carpeta = (args.rubrica.parent / r.casos).resolve()
            try:
                ids_casos = [c["id"] for c in load_cases(carpeta, {q.id for q in r.requisitos})]
            except CaseError as exc:
                nota = f"casos no cargados: {exc}"
        desconocidos = ids_desconocidos(r, ids_casos) if not nota else {}
        print(json.dumps({"rubrica": r.nombre, "clase_principal": r.clase_principal,
                          "criterios": [{"id": c.id, "peso": c.peso, "tipo": c.tipo,
                                         "niveles": [n.nombre + ("*" if n.manual else "") for n in c.niveles]}
                                        for c in r.criterios],
                          "requisitos": [(q.id, q.auto or "verificaciones/casos") for q in r.requisitos],
                          "verificaciones": [v["id"] for v in r.verificaciones],
                          "casos": ids_casos, "nota": nota, "ids_desconocidos": desconocidos,
                          "tope": r.tope, "aprobacion": r.aprobacion}, ensure_ascii=False, indent=2))
        return 1 if desconocidos else 0
    if args.review_command == "docker-check":
        res = selfcheck(DockerRunner(image=args.image), pull=args.pull)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1
    rubrica = load_rubric(args.rubrica)
    runner = _runner(args)
    casos = _casos_dir(args, rubrica)
    if not args.no_docker and not runner.available():
        print("Aviso: Docker no está disponible; compilar y ejecutar quedará sin verificar.")
    if args.review_command == "run":
        r = evaluar_entrega(rubrica, args.rubrica.parent, args.estudiante, runner, args.proyecto,
                            _manual(args, args.estudiante.name), casos)
        rutas = export_student(r, args.salida)
        print(json.dumps({**_resumen(r), "reportes": rutas}, ensure_ascii=False, indent=2))
        return 1 if r["errores"] else 0
    carpetas = sorted(p for p in args.curso.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not carpetas:
        raise RubricError(f"no hay subcarpetas de estudiantes en {args.curso}")
    resultados = []
    for carpeta in carpetas:
        r = evaluar_entrega(rubrica, args.rubrica.parent, carpeta, runner, None,
                            _manual(args, carpeta.name), casos)
        export_student(r, args.salida)
        resultados.append(r)
        print(json.dumps(_resumen(r), ensure_ascii=False))
    print(f"Consolidado: {export_course(resultados, args.salida)}")
    return 1 if any(r["errores"] for r in resultados) else 0
