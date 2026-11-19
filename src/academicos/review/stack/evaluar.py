"""Evaluar un equipo: extraer → leer → ejecutar (opcional) → señales → huella de similitud (spec 007)."""
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

from ..similarity import huella_de
from .clonar import autores as autores_git, clonar_enlaces
from .ejecucion import ComposeRunner
from .proyecto import cargar_proyecto, extraer, sin_proyecto
from .senales import evaluar_rubrica

CODIGO_SIMILITUD = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".cs", ".sql"}


def slug(texto):
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")[:80] or "equipo"


def archivos_similitud(proy):
    return [SimpleNamespace(path=r) for r in sorted(proy.codigo) if Path(r).suffix.lower() in CODIGO_SIMILITUD]


def evaluar_equipo(rubrica, equipo, trabajo, runner=None, base=None, conservar=False, clonar=None):
    """Devuelve el resultado del equipo (dict). `runner=None` = solo análisis estático."""
    work = Path(trabajo) / slug(equipo.nombre)
    if work.exists():
        shutil.rmtree(work)
    avisos = extraer(equipo.carpetas, work)
    proy = cargar_proyecto(work, avisos)
    clones = []
    if clonar is not None and sin_proyecto(proy) and proy.enlaces:
        clones, avisos_clon = clonar(proy.enlaces, work)
        proy = cargar_proyecto(work, avisos + avisos_clon)
    ejec = runner.evaluar(work, proy, rubrica.espera_segundos) if runner is not None else None
    res = evaluar_rubrica(rubrica, proy, ejec)
    res.update({
        "estudiante": equipo.nombre, "equipo": equipo.nombre, "miembros": list(equipo.miembros),
        "razon_equipo": equipo.razon, "avisos": proy.avisos, "sin_proyecto": sin_proyecto(proy),
        "enlaces": proy.enlaces, "ejecucion": ejec, "archivos": len(proy.archivos),
        "compose": proy.compose["archivo"] if proy.compose else None,
        "informe": proy.informe["archivo"] if proy.informe else None,
        "servicios": sorted(proy.compose["servicios"]) if proy.compose else [],
        "clonados": [c.name for c in clones],
        "autores": {c.name: autores_git(c) for c in clones},
    })
    archivos = archivos_similitud(proy)
    res["_huella"] = huella_de(work, archivos, base=base)
    if not conservar:
        shutil.rmtree(work, ignore_errors=True)
    return res


def clonador(ejecutar=None):
    """Función `clonar(urls, work)` lista para pasar a evaluar_equipo."""
    return lambda urls, work: clonar_enlaces(urls, work, ejecutar)


def crear_runner(usar_docker):
    if not usar_docker:
        return None
    return ComposeRunner()      # informa «Docker no está disponible» por equipo si falta
