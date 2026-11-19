"""Rúbrica por señales para proyectos distribuidos (spec 007).

A diferencia de la rúbrica de Java (niveles + casos de salida), aquí cada criterio tiene una nota
máxima y una lista de señales con peso. La nota sugerida es max × fracción de señales cumplidas;
las señales que no pudieron verificarse (sin Docker) o que son manuales quedan pendientes y nunca
cuentan como acierto ni como fallo.
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..rubric import RubricError

TIPOS = {"archivo", "contenido", "compose", "informe", "ejecucion", "git", "manual"}
COMPOSE_CAMPOS = {"servicios", "bases", "healthchecks", "citus", "build"}
INFORME_CAMPOS = {"existe", "resumen_palabras", "referencias", "secciones"}
EJEC_PRUEBAS = {"levanta", "health", "metrics"}
GIT_CAMPOS = {"etiqueta_v10"}
EN = {"codigo", "docs", "todo"}


class StackRubricError(RubricError):
    """Rúbrica de proyecto distribuido inválida."""


@dataclass(frozen=True)
class Senal:
    id: str
    descripcion: str
    tipo: str
    patron: str = ""
    campo: str = ""
    prueba: str = ""
    extensiones: tuple = ()
    en: str = "todo"
    minimo: int = 1
    maximo: int | None = None
    peso: float = 1.0
    alternativas: tuple = ()   # otras formas de cumplir la misma señal (basta una)


@dataclass(frozen=True)
class CriterioStack:
    id: str
    nombre: str
    fase: int
    max: float
    senales: tuple


@dataclass(frozen=True)
class RubricaStack:
    nombre: str
    escala_max: float
    aprobacion: float
    bonus_max: float
    criterios: tuple
    bonus: tuple = field(default_factory=tuple)
    espera_segundos: int = 240
    imagen_diagrama: tuple = ("png", "jpg", "jpeg", "svg", "puml", "dot", "drawio", "mmd", "pdf")


def _num(v, campo):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise StackRubricError(f"'{campo}' debe ser numérico")
    return float(v)


def _senal(cid, s, diagramas):
    if not isinstance(s, dict) or not s.get("id"):
        raise StackRubricError(f"{cid}: cada señal necesita 'id'")
    sid, tipo = str(s["id"]), s.get("tipo")
    if tipo not in TIPOS:
        raise StackRubricError(f"{sid}: tipo inválido '{tipo}'")
    patron, campo, prueba = str(s.get("patron") or ""), str(s.get("campo") or ""), str(s.get("prueba") or "")
    if tipo in ("archivo", "contenido") and not patron:
        raise StackRubricError(f"{sid}: falta 'patron'")
    if tipo == "compose" and campo not in COMPOSE_CAMPOS:
        raise StackRubricError(f"{sid}: compose.campo debe ser uno de {sorted(COMPOSE_CAMPOS)}")
    if tipo == "informe" and not patron and campo not in INFORME_CAMPOS:
        raise StackRubricError(f"{sid}: informe necesita 'patron' o campo de {sorted(INFORME_CAMPOS)}")
    if tipo == "ejecucion" and prueba not in EJEC_PRUEBAS:
        raise StackRubricError(f"{sid}: ejecucion.prueba debe ser uno de {sorted(EJEC_PRUEBAS)}")
    if tipo == "git" and campo not in GIT_CAMPOS:
        raise StackRubricError(f"{sid}: git.campo debe ser uno de {sorted(GIT_CAMPOS)}")
    en = str(s.get("en") or "todo")
    if en not in EN:
        raise StackRubricError(f"{sid}: 'en' debe ser codigo, docs o todo")
    ext = s.get("extensiones") or ()
    if ext == "diagrama":
        ext = diagramas
    ext = tuple(str(e).lower().lstrip(".") for e in ext)
    peso = _num(s.get("peso", 1), f"{sid}.peso")
    if peso <= 0:
        raise StackRubricError(f"{sid}: el peso debe ser positivo")
    maximo = s.get("maximo")
    alts = tuple(_senal(cid, {**a, "id": f"{sid}~{i}", "descripcion": a.get("descripcion", s.get("descripcion", sid))}, diagramas)
                 for i, a in enumerate(s.get("o") or []))
    return Senal(sid, str(s.get("descripcion", sid)), tipo, patron, campo, prueba, ext, en,
                 int(s.get("minimo", 1)), None if maximo is None else int(maximo), peso, alts)


def parse_stack_rubric(datos):
    if not isinstance(datos, dict) or not str(datos.get("nombre") or "").strip():
        raise StackRubricError("la rúbrica necesita 'nombre'")
    escala = datos.get("escala") or {}
    emax = _num(escala.get("max", 5.0), "escala.max")
    ejec = datos.get("ejecucion") or {}
    diagramas = tuple(str(e).lower() for e in ejec.get("imagen_diagrama") or
                      ("png", "jpg", "jpeg", "svg", "puml", "dot", "drawio", "mmd", "pdf"))
    crudos = datos.get("criterios")
    if not isinstance(crudos, list) or not crudos:
        raise StackRubricError("'criterios' debe ser una lista no vacía")
    criterios, ids, suma = [], set(), 0.0
    for c in crudos:
        if not isinstance(c, dict) or not c.get("id"):
            raise StackRubricError("cada criterio necesita 'id'")
        cid = str(c["id"])
        if cid in ids:
            raise StackRubricError(f"criterio repetido: {cid}")
        ids.add(cid)
        mx = _num(c.get("max"), f"{cid}.max")
        if mx <= 0:
            raise StackRubricError(f"{cid}: 'max' debe ser positivo")
        senales = tuple(_senal(cid, s, diagramas) for s in c.get("senales") or [])
        if not senales:
            raise StackRubricError(f"{cid}: necesita al menos una señal")
        sids = [s.id for s in senales]
        if len(set(sids)) != len(sids):
            raise StackRubricError(f"{cid}: señales repetidas")
        criterios.append(CriterioStack(cid, str(c.get("nombre", cid)), int(c.get("fase", 0)), mx, senales))
        suma += mx
    if abs(suma - emax) > 1e-9:
        raise StackRubricError(f"los criterios suman {suma:g}, deben sumar {emax:g}")
    todos = [s.id for c in criterios for s in c.senales]
    bonus = tuple(_senal("bonus", b, diagramas) for b in datos.get("bonus") or [])
    if set(todos) & {b.id for b in bonus} or len(set(todos)) != len(todos):
        raise StackRubricError("ids de señal repetidos entre criterios y bonus")
    return RubricaStack(str(datos["nombre"]).strip(), emax, _num(datos.get("aprobacion", 3.0), "aprobacion"),
                        _num(datos.get("bonus_max", 0.0), "bonus_max"), tuple(criterios), bonus,
                        int(ejec.get("espera_segundos", 240)), diagramas)


def load_stack_rubric(path):
    try:
        datos = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise StackRubricError(f"YAML inválido en {Path(path).name}: {exc}") from exc
    return parse_stack_rubric(datos)
