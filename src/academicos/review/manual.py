"""Puntajes de criterios manuales (spec 006, RF-J12): los llena la persona docente."""
from pathlib import Path

import yaml

from .rubric import RubricError, _num


def load_manual(path, rubrica):
    """Leer `puntajes` de un YAML por estudiante. Solo criterios de tipo manual.

    Un criterio ausente o con valor nulo queda pendiente; nunca se inventa puntaje.
    """
    path = Path(path)
    try:
        datos = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RubricError(f"YAML inválido en {path.name}: {exc}") from exc
    if not isinstance(datos, dict):
        raise RubricError(f"{path.name}: debe ser un mapa YAML")
    crudos = datos.get("puntajes") or {}
    if not isinstance(crudos, dict):
        raise RubricError(f"{path.name}: 'puntajes' debe ser un mapa")
    manuales = {c.id for c in rubrica.criterios if c.tipo == "manual"}
    todos = {c.id for c in rubrica.criterios}
    puntajes = {}
    for cid, nota in crudos.items():
        if cid not in todos:
            raise RubricError(f"{path.name}: criterio desconocido '{cid}'")
        if cid not in manuales:
            raise RubricError(f"{path.name}: '{cid}' es automático; no se puntúa a mano")
        if nota is None:
            continue
        nota = _num(nota, f"puntajes.{cid}")
        if not rubrica.escala_min <= nota <= rubrica.escala_max:
            raise RubricError(f"{path.name}: nota de {cid} fuera de la escala")
        puntajes[cid] = nota
    ajustes = {}
    for cid, a in (datos.get("ajustes") or {}).items():
        if cid not in todos:
            raise RubricError(f"{path.name}: ajuste a criterio desconocido '{cid}'")
        if cid in manuales:
            raise RubricError(f"{path.name}: '{cid}' es manual; usa 'puntajes'")
        if not isinstance(a, dict) or not str(a.get("motivo") or "").strip():
            raise RubricError(f"{path.name}: el ajuste de '{cid}' necesita 'nota' y 'motivo'")
        nota = _num(a.get("nota"), f"ajustes.{cid}.nota")
        if not rubrica.escala_min <= nota <= rubrica.escala_max:
            raise RubricError(f"{path.name}: ajuste de {cid} fuera de la escala")
        ajustes[cid] = {"nota": nota, "motivo": str(a["motivo"]).strip()}
    return {"estudiante": datos.get("estudiante"), "puntajes": puntajes, "ajustes": ajustes,
            "observaciones": str(datos.get("observaciones") or "")}
