"""Evaluar señales y calcular la nota sugerida de un proyecto distribuido (spec 007).

Honestidad: una señal es True (hay evidencia), False (no la hay) o None (no se pudo verificar:
sin Docker, informe ilegible, sin .git, o es manual). Lo pendiente nunca cuenta como acierto.
"""
import re
import unicodedata
from pathlib import Path

from .proyecto import es_base

_DATOS = (".csv", ".hl7")
_ETIQUETAS_V10 = {"v1.0", "1.0", "v1.0.0", "1.0.0"}


def _sin_acentos(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").lower()


def _corpus(proy, en):
    codigo = {k: v for k, v in proy.codigo.items() if not k.lower().endswith(_DATOS)}
    if en == "codigo":
        return codigo
    if en == "docs":
        return proy.docs
    return {**proy.codigo, **proy.docs}


def _resumir(items, n=2):
    ms = [Path(i).name for i in items[:n]]
    return ", ".join(ms) + (f" y {len(items) - n} más" if len(items) > n else "")


def _archivo(s, proy):
    rx = re.compile(s.patron, re.I)
    vistos, rutas = set(), []
    for rel in proy.archivos:
        p = Path(rel)
        if s.extensiones and p.suffix.lower().lstrip(".") not in s.extensiones:
            continue
        if rx.search(_sin_acentos(p.name)) and p.stem.lower() not in vistos:
            vistos.add(p.stem.lower())
            rutas.append(rel)
    return len(rutas) >= s.minimo, (f"{len(rutas)} archivo(s): {_resumir(rutas)}" if rutas else "ninguno")


def _contenido(s, proy):
    rx = re.compile(s.patron, re.I | re.M)
    rutas = [r for r, t in _corpus(proy, s.en).items() if rx.search(t)]
    return len(rutas) >= s.minimo, (f"en {len(rutas)} archivo(s): {_resumir(rutas)}" if rutas else "sin coincidencias")


def _compose(s, proy):
    c = proy.compose
    if not c:
        return False, "no hay docker-compose.yml"
    sv = c["servicios"]
    n = {"servicios": len(sv), "bases": sum(es_base(k, v) for k, v in sv.items()),
         "healthchecks": sum(v["healthcheck"] for v in sv.values()),
         "citus": sum("citus" in v["imagen"].lower() for v in sv.values()),
         "build": sum(v["build"] for v in sv.values())}[s.campo]
    return n >= s.minimo, f"{n} {s.campo} en {c['archivo']}"


def _informe(s, proy):
    inf = proy.informe
    if not inf:
        return False, "no se encontró informe (pdf, docx o md)"
    if s.campo == "existe":
        return True, inf["archivo"]
    if inf.get("texto") is None:
        return None, f"no se pudo leer {inf['archivo']} (instala pdftotext o markitdown)"
    if s.patron:
        n = len(re.findall(s.patron, inf["texto"], re.I | re.S))
        return n >= s.minimo, f"{n} coincidencia(s) en el informe"
    v = inf.get(s.campo)
    if v is None:
        return False, f"no se identificó {s.campo.replace('_', ' ')} en el informe"
    ok = v >= s.minimo and (s.maximo is None or v <= s.maximo)
    return ok, f"{v}"


def _ejecucion(s, ejec):
    if not ejec or ejec.get(s.prueba) is None:
        motivo = (ejec or {}).get("motivo") or "sin Docker (no se ejecutó)"
        return None, motivo
    return bool(ejec[s.prueba]), ejec.get("detalle", {}).get(s.prueba, "")


def _git(s, proy):
    if proy.etiquetas is None:
        return None, "la entrega no incluye .git"
    ok = bool(_ETIQUETAS_V10 & {t.lower() for t in proy.etiquetas})
    return ok, ("etiquetas: " + ", ".join(sorted(proy.etiquetas)) if proy.etiquetas else "sin etiquetas")


def evaluar_senal(s, proy, ejec=None):
    """Devuelve (estado True|False|None, detalle). Con alternativas (`o:`) basta cumplir una."""
    estado, detalle = _evaluar_una(s, proy, ejec)
    if not s.alternativas or estado is True:
        return estado, detalle
    for a in s.alternativas:
        e2, d2 = _evaluar_una(a, proy, ejec)
        if e2 is True:
            return True, d2
        if e2 is None and estado is False:
            estado, detalle = None, d2
    return estado, detalle


def _evaluar_una(s, proy, ejec):
    if s.tipo == "archivo":
        return _archivo(s, proy)
    if s.tipo == "contenido":
        return _contenido(s, proy)
    if s.tipo == "compose":
        return _compose(s, proy)
    if s.tipo == "informe":
        return _informe(s, proy)
    if s.tipo == "ejecucion":
        return _ejecucion(s, ejec)
    if s.tipo == "git":
        return _git(s, proy)
    return None, "la confirma la persona docente"


def _criterio(c, proy, ejec):
    filas = []
    for s in c.senales:
        estado, detalle = evaluar_senal(s, proy, ejec)
        filas.append({"id": s.id, "descripcion": s.descripcion, "tipo": s.tipo, "estado": estado,
                      "detalle": detalle, "peso": s.peso})
    medibles = [f for f in filas if f["tipo"] != "manual"]
    base = {"id": c.id, "nombre": c.nombre, "fase": c.fase, "max": c.max, "senales": filas}
    w = sum(f["peso"] for f in medibles)
    if not medibles:
        return {**base, "nota": None, "maximo_posible": c.max, "estado": "pendiente docente", "manual": True}
    ok = sum(f["peso"] for f in medibles if f["estado"] is True)
    pend = sum(f["peso"] for f in medibles if f["estado"] is None)
    nota = round(c.max * ok / w, 2)
    posible = round(c.max * (ok + pend) / w, 2)
    if posible < c.max / 2:
        estado = "no cumplido"
    elif pend and nota < c.max / 2:
        estado = "pendiente de verificar"
    elif nota >= c.max - 1e-9:
        estado = "excelente"
    elif nota >= c.max / 2:
        estado = "cumplido parcial"
    else:
        estado = "no cumplido"
    return {**base, "nota": nota, "maximo_posible": posible, "estado": estado, "manual": False}


def evaluar_rubrica(rubrica, proy, ejec=None):
    criterios = [_criterio(c, proy, ejec) for c in rubrica.criterios]
    parcial = round(sum(c["nota"] for c in criterios if c["nota"] is not None), 2)
    posible = round(sum(c["maximo_posible"] for c in criterios), 2)
    docente = round(sum(c["max"] for c in criterios if c["manual"]), 2)
    bonus = []
    for b in rubrica.bonus:
        estado, detalle = evaluar_senal(b, proy, ejec)
        bonus.append({"id": b.id, "descripcion": b.descripcion, "estado": estado, "detalle": detalle})
    ok = sum(1 for b in bonus if b["estado"] is True)
    pts = round(rubrica.bonus_max * ok / len(bonus), 3) if bonus else 0.0
    return {"criterios": criterios, "parcial": parcial, "maximo_posible": min(posible, rubrica.escala_max),
            "pendiente_docente": docente, "bonus": bonus, "bonus_puntos": pts,
            "nota": min(round(parcial + pts, 2), rubrica.escala_max)}
