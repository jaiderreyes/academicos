"""Agrupar entregas por equipo (spec 007). Los equipos son de 2: a menudo ambos suben el mismo archivo.

Criterio: carpetas con exactamente el mismo conjunto de archivos (por contenido) son el mismo
equipo. Cuando los integrantes suben cosas distintas, la persona docente los une con un YAML
(`--equipos equipos.yaml`: lista de listas con parte del nombre de cada integrante).
"""
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Equipo:
    nombre: str
    miembros: list = field(default_factory=list)   # nombres limpios de quienes entregaron
    carpetas: list = field(default_factory=list)   # carpetas distintas a evaluar (sin duplicados)
    razon: str = ""


def limpiar_nombre(carpeta):
    n = re.sub(r"_\d+_assignsubmission_file$", "", Path(carpeta).name)
    n = re.sub(r"_\d+_?$", "", n).strip(" _")
    return " ".join(w.capitalize() for w in n.split())


def _hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def huella_carpeta(carpeta):
    return frozenset(_hash(p) for p in Path(carpeta).rglob("*") if p.is_file() and not p.is_symlink())


def _manual(ruta):
    if not ruta:
        return []
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or {}
    grupos = datos.get("equipos", datos) if isinstance(datos, dict) else datos
    if not isinstance(grupos, list) or not all(isinstance(g, list) and g for g in grupos):
        raise ValueError("equipos.yaml debe ser una lista de listas de nombres (o 'equipos: [[...]]')")
    return [[str(x).lower() for x in g] for g in grupos]


def agrupar(carpetas, equipos_yaml=None):
    """carpetas: lista de Path (una por estudiante). Devuelve lista de Equipo ordenada por nombre."""
    carpetas = sorted(Path(c) for c in carpetas)
    padre = {c: c for c in carpetas}

    def raiz(c):
        while padre[c] != c:
            padre[c] = padre[padre[c]]
            c = padre[c]
        return c

    def unir(a, b):
        padre[raiz(a)] = raiz(b)

    huellas = {c: huella_carpeta(c) for c in carpetas}
    vistas = {}
    for c in carpetas:
        h = huellas[c]
        if not h:
            continue
        if h in vistas:
            unir(c, vistas[h])
        else:
            vistas[h] = c
    for grupo in _manual(equipos_yaml):
        ids = [c for c in carpetas if any(g in c.name.lower() for g in grupo)]
        for a, b in zip(ids, ids[1:]):
            unir(a, b)
    grupos = {}
    for c in carpetas:
        grupos.setdefault(raiz(c), []).append(c)
    equipos = []
    for r, miembros in grupos.items():
        distintas, vistos = [], set()
        for c in miembros:
            if huellas[c] not in vistos or not huellas[c]:
                vistos.add(huellas[c])
                distintas.append(c)
        nombres = [limpiar_nombre(c) for c in miembros]
        if len(miembros) == 1:
            why = ""
        elif len({huellas[c] for c in miembros}) == 1 and huellas[miembros[0]]:
            why = "entregaron exactamente los mismos archivos"
        else:
            why = "unidos por equipos.yaml"
        equipos.append(Equipo(" + ".join(nombres), nombres, distintas, why))
    return sorted(equipos, key=lambda e: e.nombre)
