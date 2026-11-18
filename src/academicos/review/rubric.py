"""Rúbricas configurables y cálculo de nota sugerida (spec 006, J-02/J-03).

La nota que se calcula aquí es una *sugerencia*: la decisión final es de la persona
docente. Lo que no pudo verificarse se informa como pendiente; nunca se puntúa de
forma implícita como acierto o fallo.
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .checks import CheckError, parse_checks

PESO_TOTAL = 100
TIPOS = {"automatico", "manual"}


class RubricError(ValueError):
    """Rúbrica inválida o puntajes fuera de rango."""


@dataclass(frozen=True)
class Nivel:
    nombre: str
    min: float
    max: float
    requiere: tuple = ()      # ids de verificaciones, casos, requisitos o "compila"
    manual: bool = False      # solo la persona docente puede confirmarlo
    descripcion: str = ""


@dataclass(frozen=True)
class Criterio:
    id: str
    nombre: str
    peso: float
    tipo: str = "automatico"
    evidencia: tuple = ()   # ids de verificaciones o casos que sustentan la nota
    niveles: tuple = ()     # niveles acumulativos (deficiente → excelente) con requisitos


AUTO_REQUISITOS = {"compila"}


@dataclass(frozen=True)
class Requisito:
    id: str
    descripcion: str
    auto: str = ""          # "compila": se deriva del paso de compilación


@dataclass(frozen=True)
class Rubrica:
    nombre: str
    escala_min: float
    escala_max: float
    aprobacion: float
    tope: float
    criterios: tuple
    requisitos: tuple = field(default_factory=tuple)
    verificaciones: tuple = field(default_factory=tuple)
    casos: str = ""
    clase_principal: str = ""   # clase con main() que se ejecuta (p. ej. app.Main)


def _num(valor, campo):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise RubricError(f"'{campo}' debe ser numérico")
    return float(valor)


def _parse_niveles(cid, crudos, emin, emax):
    if not crudos:
        return ()
    if not isinstance(crudos, list) or len(crudos) < 2:
        raise RubricError(f"{cid}: 'niveles' necesita al menos dos niveles")
    niveles, previo = [], None
    for i, n in enumerate(crudos):
        if not isinstance(n, dict) or not n.get("nivel"):
            raise RubricError(f"{cid}: cada nivel necesita 'nivel'")
        nombre = str(n["nivel"])
        lo, hi = _num(n.get("min"), f"{cid}.{nombre}.min"), _num(n.get("max"), f"{cid}.{nombre}.max")
        if not emin <= lo <= hi <= emax:
            raise RubricError(f"{cid}.{nombre}: rango fuera de la escala o invertido")
        if previo is not None and lo <= previo:
            raise RubricError(f"{cid}.{nombre}: los niveles deben ir de menor a mayor sin solaparse")
        req = n.get("requiere") or []
        if not isinstance(req, list) or not all(isinstance(x, str) for x in req):
            raise RubricError(f"{cid}.{nombre}: 'requiere' debe ser una lista de ids")
        manual = bool(n.get("manual", False))
        if i == 0 and (req or manual):
            raise RubricError(f"{cid}: el primer nivel es la base y no lleva requisitos")
        if i > 0 and not req and not manual:
            raise RubricError(f"{cid}.{nombre}: define 'requiere' o marca 'manual: true'")
        niveles.append(Nivel(nombre, lo, hi, tuple(req), manual, str(n.get("descripcion", ""))))
        previo = hi
    return tuple(niveles)


def parse_rubric(datos):
    if not isinstance(datos, dict):
        raise RubricError("la rúbrica debe ser un mapa YAML")
    nombre = datos.get("nombre")
    if not isinstance(nombre, str) or not nombre.strip():
        raise RubricError("falta 'nombre'")
    escala = datos.get("escala") or {}
    emin = _num(escala.get("min", 0.0), "escala.min")
    emax = _num(escala.get("max", 5.0), "escala.max")
    if emin >= emax:
        raise RubricError("escala.min debe ser menor que escala.max")
    aprobacion = _num(datos.get("aprobacion", 3.0), "aprobacion")
    if not emin <= aprobacion <= emax:
        raise RubricError("aprobacion fuera de la escala")
    minima = datos.get("condicion_minima") or {}
    tope = _num(minima.get("tope", aprobacion), "condicion_minima.tope")
    if not emin <= tope <= emax:
        raise RubricError("condicion_minima.tope fuera de la escala")
    if tope >= aprobacion and minima.get("requisitos"):
        raise RubricError("el tope debe ser menor que la nota de aprobación")

    crudos = datos.get("criterios")
    if not isinstance(crudos, list) or not crudos:
        raise RubricError("'criterios' debe ser una lista no vacía")
    criterios, vistos = [], set()
    for c in crudos:
        if not isinstance(c, dict) or not c.get("id"):
            raise RubricError("cada criterio necesita 'id'")
        cid = str(c["id"])
        if cid in vistos:
            raise RubricError(f"criterio repetido: {cid}")
        vistos.add(cid)
        peso = _num(c.get("peso"), f"criterios.{cid}.peso")
        if peso <= 0:
            raise RubricError(f"el peso de {cid} debe ser positivo")
        tipo = c.get("tipo", "automatico")
        if tipo not in TIPOS:
            raise RubricError(f"tipo inválido en {cid}: {tipo}")
        ev = c.get("evidencia") or []
        if not isinstance(ev, list) or not all(isinstance(x, str) for x in ev):
            raise RubricError(f"evidencia de {cid} debe ser una lista de ids")
        if ev and tipo == "manual":
            raise RubricError(f"{cid} es manual; no puede tener evidencia automática")
        niveles = _parse_niveles(cid, c.get("niveles"), emin, emax)
        if niveles and tipo == "manual":
            raise RubricError(f"{cid} es manual; no puede tener niveles automáticos")
        if niveles and ev:
            raise RubricError(f"{cid}: usa 'niveles' o 'evidencia', no ambos")
        criterios.append(Criterio(cid, str(c.get("nombre", cid)), peso, tipo, tuple(ev), niveles))
    suma = sum(c.peso for c in criterios)
    if abs(suma - PESO_TOTAL) > 1e-9:
        raise RubricError(f"los pesos suman {suma:g} %, deben sumar {PESO_TOTAL} %")

    requisitos, rvistos = [], set()
    for r in minima.get("requisitos") or []:
        if not isinstance(r, dict) or not r.get("id"):
            raise RubricError("cada requisito necesita 'id'")
        rid = str(r["id"])
        if rid in rvistos:
            raise RubricError(f"requisito repetido: {rid}")
        rvistos.add(rid)
        auto = str(r.get("auto") or "")
        if auto and auto not in AUTO_REQUISITOS:
            raise RubricError(f"requisito {rid}: auto inválido '{auto}'")
        requisitos.append(Requisito(rid, str(r.get("descripcion", rid)), auto))
    try:
        verificaciones = parse_checks(datos.get("verificaciones"),
                                      {r.id for r in requisitos})
    except CheckError as exc:
        raise RubricError(str(exc)) from exc
    ejec = datos.get("ejecucion") or {}
    if not isinstance(ejec, dict):
        raise RubricError("'ejecucion' debe ser un mapa")
    clase_principal = str(ejec.get("clase_principal") or "")
    casos = datos.get("casos") or ""
    if casos and not isinstance(casos, str):
        raise RubricError("'casos' debe ser una ruta de carpeta")
    return Rubrica(nombre.strip(), emin, emax, aprobacion, tope,
                   tuple(criterios), tuple(requisitos), verificaciones, casos, clase_principal)


def load_rubric(path):
    path = Path(path)
    try:
        datos = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RubricError(f"YAML inválido en {path.name}: {exc}") from exc
    return parse_rubric(datos)


def score(rubrica, puntajes, requisitos=None):
    """Calcular nota sugerida.

    puntajes: {criterio_id: nota en la escala | None}. Faltante o None = pendiente.
    requisitos: {requisito_id: True | False | None}. Faltante o None = sin verificar.
    """
    puntajes = puntajes or {}
    requisitos = requisitos or {}
    ids = {c.id for c in rubrica.criterios}
    desconocidos = set(puntajes) - ids
    if desconocidos:
        raise RubricError(f"criterios desconocidos: {sorted(desconocidos)}")
    rids = {r.id for r in rubrica.requisitos}
    if set(requisitos) - rids:
        raise RubricError(f"requisitos desconocidos: {sorted(set(requisitos) - rids)}")

    detalle, total, pendientes_peso = [], 0.0, 0.0
    for c in rubrica.criterios:
        nota = puntajes.get(c.id)
        if nota is None:
            pendientes_peso += c.peso
            detalle.append({"id": c.id, "nombre": c.nombre, "tipo": c.tipo,
                            "peso": c.peso, "nota": None, "aporte": None,
                            "estado": "pendiente"})
            continue
        nota = _num(nota, f"puntajes.{c.id}")
        if not rubrica.escala_min <= nota <= rubrica.escala_max:
            raise RubricError(
                f"nota de {c.id} fuera de la escala "
                f"[{rubrica.escala_min:g}, {rubrica.escala_max:g}]")
        aporte = nota * c.peso / PESO_TOTAL
        total += aporte
        detalle.append({"id": c.id, "nombre": c.nombre, "tipo": c.tipo,
                        "peso": c.peso, "nota": nota, "aporte": round(aporte, 4),
                        "estado": "puntuado"})

    incumplidos = [r.id for r in rubrica.requisitos if requisitos.get(r.id) is False]
    sin_verificar = [r.id for r in rubrica.requisitos if requisitos.get(r.id) is None]
    bruta = total
    tope_aplicado = bool(incumplidos) and total > rubrica.tope
    if tope_aplicado:
        total = rubrica.tope
    maximo = bruta + pendientes_peso * rubrica.escala_max / PESO_TOTAL
    if incumplidos:
        maximo = min(maximo, rubrica.tope)
    completo = pendientes_peso == 0 and not sin_verificar
    return {
        "rubrica": rubrica.nombre,
        "criterios": detalle,
        "nota_sugerida": round(total, 2),
        "nota_sin_tope": round(bruta, 2),
        "maximo_posible": round(maximo, 2),
        "completo": completo,
        "tope_aplicado": tope_aplicado,
        "requisitos_incumplidos": incumplidos,
        "requisitos_sin_verificar": sin_verificar,
        "aprueba": (round(total, 2) >= rubrica.aprobacion) if completo else None,
    }
