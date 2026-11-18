"""Evaluación de una entrega de punta a punta (spec 006, J-08/J-09).

Orquesta detección, copia, verificaciones, compilación/casos en Docker, criterios manuales
y nota sugerida. Todo lo que no se pudo comprobar queda marcado, nunca se puntúa por defecto.
"""
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .cases import load_cases, requisitos_desde_casos, run_cases, CaseError
from .checks import requisitos_desde_checks, run_checks
from .javaproject import (ProjectError, detect_project, fingerprint, find_candidates,
                          prepare_copy)
from .manual import load_manual
from .rubric import score

AVISOS_ALCANCE = [
    "La nota es una sugerencia; la decisión final es de la persona docente.",
    "Se compila el proyecto completo: no se distingue entre variante manual y java.util.",
    "Las verificaciones estáticas son indicios basados en nombres y patrones de texto.",
]


def _combinar(*mapas):
    """Combina requisitos: False domina, luego None (sin verificar), luego True."""
    out = {}
    for m in mapas:
        for k, v in m.items():
            actual = out.get(k, True)
            if v is False or actual is False:
                out[k] = False
            elif v is None or actual is None:
                out[k] = None
            else:
                out[k] = True
    return out


def _puntaje_por_evidencia(rubrica, criterio, estados, avisos):
    """Fracción de evidencia superada × escala; pendiente si falta alguna evidencia.

    Con evidencia incompleta no se concluye: existir una clase no prueba que funcione.
    """
    sin_ejecutar = [e for e in criterio.evidencia if e not in estados]
    sin_verificar = [e for e in criterio.evidencia if estados.get(e, None) is None]
    if sin_verificar:
        ok = sum(1 for e in criterio.evidencia if estados.get(e))
        avisos.append(f"criterio '{criterio.id}' pendiente: evidencia incompleta "
                      f"({len(criterio.evidencia) - len(sin_verificar)}/{len(criterio.evidencia)} verificable; "
                      f"sin verificar: {sin_verificar}" + (f"; sin ejecutar: {sin_ejecutar}" if sin_ejecutar else "") + ")")
        return None
    ok = sum(1 for e in criterio.evidencia if estados[e])
    return round(rubrica.escala_min + (rubrica.escala_max - rubrica.escala_min) * ok / len(criterio.evidencia), 4)


def evaluar_entrega(rubrica, rubrica_dir, estudiante_dir, runner, proyecto=None,
                    manual_path=None, casos_dir=None):
    estudiante_dir = Path(estudiante_dir)
    resultado = {"estudiante": estudiante_dir.name, "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "rubrica": rubrica.nombre, "avisos": list(AVISOS_ALCANCE), "errores": []}
    origen = Path(proyecto) if proyecto else None
    if origen is None:
        cands = find_candidates(estudiante_dir) if estudiante_dir.is_dir() else [estudiante_dir]
        if not cands:
            resultado["errores"].append("no se encontró proyecto Java (carpeta, .java o .zip)")
            return resultado
        origen = cands[0]
        resultado["alternativas"] = [c.name for c in cands[1:]]
    resultado["proyecto"] = origen.name
    antes = fingerprint(origen)
    with tempfile.TemporaryDirectory(prefix="academicos-eval-") as tmp:
        tmp = Path(tmp)
        try:
            info = detect_project(origen, extract_to=tmp / "zip")
            work = prepare_copy(info, tmp / "copia")
        except ProjectError as exc:
            resultado["errores"].append(str(exc))
            return resultado
        work.chmod(0o755)
        resultado["estructura"] = {"tipo": info.kind, "raices": info.source_roots,
                                   "clases_principales": info.main_classes,
                                   "archivos_java": len(info.files), "archivos_prueba": info.test_files,
                                   "avisos": info.warnings}
        # 1) verificaciones estáticas
        checks = run_checks(rubrica.verificaciones, info.root, info.files)
        resultado["verificaciones"] = checks
        # 2) casos externos + compilación (Docker)
        casos = []
        casos_dir = Path(casos_dir) if casos_dir else None
        if casos_dir is not None:
            try:
                casos = load_cases(casos_dir, {r.id for r in rubrica.requisitos})
            except CaseError as exc:
                resultado["avisos"].append(f"casos no cargados: {exc}")
                casos_dir = None
        ejec = run_cases(runner, info, work, casos_dir or work, casos)
        comp = ejec["compilacion"]
        resultado["compilacion"] = comp.to_dict()
        resultado["casos"] = ejec["casos"]
    resultado["integridad"] = {"archivos": len(antes), "intacto": fingerprint(origen) == antes}

    # 3) requisitos
    estado_compila = {"ok": True, "fail": False}.get(comp.status)
    auto = {r.id: estado_compila for r in rubrica.requisitos if r.auto == "compila"}
    requisitos = _combinar(requisitos_desde_checks(checks), requisitos_desde_casos(ejec["casos"]), auto)
    requisitos = {r.id: requisitos.get(r.id) for r in rubrica.requisitos}

    # 4) criterios: manuales desde archivo; automáticos desde su evidencia
    puntajes = {}
    if manual_path and Path(manual_path).is_file():
        manual = load_manual(manual_path, rubrica)
        puntajes.update(manual["puntajes"])
        resultado["manual"] = {"archivo": Path(manual_path).name, "observaciones": manual["observaciones"]}
    elif any(c.tipo == "manual" for c in rubrica.criterios):
        resultado["avisos"].append("sin archivo de criterios manuales: quedan pendientes")
    estados = {c["id"]: c["cumple"] for c in checks}
    estados.update({c["id"]: (True if c["estado"] == "ok" else False if c["estado"] == "fail" else None)
                    for c in ejec["casos"]})
    for c in rubrica.criterios:
        if c.tipo == "automatico" and c.evidencia:
            puntajes[c.id] = _puntaje_por_evidencia(rubrica, c, estados, resultado["avisos"])
    resultado["requisitos"] = requisitos
    resultado["calificacion"] = score(rubrica, puntajes, requisitos)
    return resultado
