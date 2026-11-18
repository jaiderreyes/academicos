"""Similitud de código entre entregas (spec 006, RF-J09).

Mismo método que la spec 002 (Jaccard de n-gramas de 5) pero sobre tokens de código sin
comentarios ni literales. Se calcula de dos formas y se toma la mayor:
  - literal: identificadores tal cual;
  - normalizada: identificadores y números reemplazados por marcadores, de modo que
    renombrar variables no oculte la coincidencia.
Es un indicio para revisar a mano, nunca una prueba de copia. Todo ocurre en local.
"""
import re
from pathlib import Path

from .checks import strip_comments_and_strings

UMBRAL = 0.80
MIN_TOKENS = 50
N = 5
_TOKEN = re.compile(r"[A-Za-z_]\w*|\d+(?:\.\d+)?|[^\s\w]")
# Palabras reservadas y tipos comunes: se conservan al normalizar (dan estructura).
_CLAVE = set("""abstract boolean break byte case catch char class continue default do double else enum
extends final finally float for if implements import instanceof int interface long new package private
protected public return short static super switch this throw throws try void while null true false
String Integer Object List ArrayList LinkedList Deque Queue Stack Map HashMap Scanner""".split())


def _tokens(texto):
    return _TOKEN.findall(strip_comments_and_strings(texto))


def _normalizar(tokens):
    out = []
    for t in tokens:
        if t[0].isdigit():
            out.append("NUM")
        elif (t[0].isalpha() or t[0] == "_") and t not in _CLAVE:
            out.append("ID")
        else:
            out.append(t)
    return out


def _shingles(tokens):
    return {" ".join(tokens[i:i + N]) for i in range(len(tokens) - N + 1)}


def huella_de(raiz, archivos, excluir=()):
    """Huella de un proyecto: dict con conjuntos de n-gramas literales y normalizados."""
    toks = []
    for f in sorted(archivos, key=lambda a: a.path):
        if f.path in excluir:
            continue
        try:
            texto = (Path(raiz) / f.path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        toks.extend(_tokens(texto))
    if len(toks) < MIN_TOKENS:
        return {"tokens": len(toks), "literal": set(), "normalizada": set()}
    return {"tokens": len(toks), "literal": _shingles(toks), "normalizada": _shingles(_normalizar(toks))}


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def comparar(huellas, umbral=UMBRAL):
    """huellas: {estudiante: huella}. Devuelve {pares, insuficientes, umbral}."""
    nombres = sorted(huellas)
    insuf = [n for n in nombres if not huellas[n]["literal"]]
    pares = []
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            ha, hb = huellas[a], huellas[b]
            if not ha["literal"] or not hb["literal"]:
                continue
            lit = _jaccard(ha["literal"], hb["literal"])
            nor = _jaccard(ha["normalizada"], hb["normalizada"])
            if max(lit, nor) >= umbral:
                comunes = sorted(ha["literal"] & hb["literal"], key=lambda s: (-len(s), s))[:3]
                pares.append({"a": a, "b": b, "literal": round(lit, 4), "normalizada": round(nor, 4),
                              "puntaje": round(max(lit, nor), 4), "fragmentos": comunes})
    pares.sort(key=lambda p: -p["puntaje"])
    return {"umbral": umbral, "algoritmo": f"jaccard_{N}gramas_tokens", "pares": pares,
            "insuficientes": insuf,
            "aviso": "La similitud es un indicio para revisar a mano, no una prueba de copia."}


def markdown(res):
    L = ["# Similitud de código entre entregas", "",
         f"Umbral {res['umbral']:.2f} · {res['algoritmo']}. {res['aviso']}", ""]
    if res["pares"]:
        L += ["| Estudiante A | Estudiante B | Literal | Normalizada | Fragmentos comunes |", "|---|---|---|---|---|"]
        for p in res["pares"]:
            frag = " ; ".join(f"`{f}`" for f in p["fragmentos"]) or "—"
            L.append(f"| {p['a']} | {p['b']} | {p['literal']:.2f} | {p['normalizada']:.2f} | {frag} |")
    else:
        L.append("Ningún par supera el umbral.")
    if res["insuficientes"]:
        L += ["", "Sin código suficiente para comparar: " + ", ".join(res["insuficientes"])]
    return "\n".join(L) + "\n"
