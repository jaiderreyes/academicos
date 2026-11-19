"""Similitud de código entre entregas (spec 006, RF-J09).

Mismo método que la spec 002 (Jaccard de n-gramas de 5) pero sobre tokens de código sin
comentarios ni literales. Se calcula de dos formas y se toma la mayor:
  - literal: identificadores tal cual;
  - normalizada: identificadores y números reemplazados por marcadores, de modo que
    renombrar variables no oculte la coincidencia.
Es un indicio para revisar a mano, nunca una prueba de copia. Todo ocurre en local.
"""
import hashlib
import re
from pathlib import Path
from types import SimpleNamespace

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


def firma_archivo(texto):
    """Firma de un archivo ignorando comentarios y espacios (detecta archivos sin modificar)."""
    return hashlib.sha256(" ".join(_tokens(texto)).encode("utf-8")).hexdigest()


def cargar_base(carpeta, extensiones=(".java",)):
    """Base entregada por la persona docente: firmas por archivo y huella para restar."""
    carpeta = Path(carpeta)
    archivos = [SimpleNamespace(path=p.relative_to(carpeta).as_posix())
                for p in sorted(carpeta.rglob("*")) if p.is_file() and p.suffix.lower() in extensiones]
    if not archivos:
        raise ValueError(f"no hay archivos {'/'.join(extensiones)} en la base {carpeta}")
    firmas = {firma_archivo((carpeta / a.path).read_text(encoding="utf-8", errors="replace")) for a in archivos}
    return {"nombre": carpeta.name, "firmas": firmas, "archivos": len(archivos),
            "huella": huella_de(carpeta, archivos, minimo=0)}


def archivos_sin_modificar(raiz, archivos, base):
    """Rutas de archivos idénticos (salvo comentarios/espacios) a alguno de la base."""
    out = set()
    for f in archivos:
        try:
            texto = (Path(raiz) / f.path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if firma_archivo(texto) in base["firmas"]:
            out.add(f.path)
    return out


def huella_de(raiz, archivos, excluir=(), base=None, minimo=MIN_TOKENS):
    """Huella de un proyecto: dict con conjuntos de n-gramas literales y normalizados.

    Con `base`, se restan los n-gramas de la base: solo cuenta el código añadido."""
    toks, firmas = [], {}
    for f in sorted(archivos, key=lambda a: a.path):
        if f.path in excluir:
            continue
        try:
            texto = (Path(raiz) / f.path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        t = _tokens(texto)
        toks.extend(t)
        if len(t) >= N:
            firmas[f.path] = firma_archivo(texto)
    lit, nor = _shingles(toks), _shingles(_normalizar(toks))
    if base:
        lit, nor = lit - base["huella"]["literal"], nor - base["huella"]["normalizada"]
    if len(toks) < minimo or (base and len(lit) < MIN_TOKENS - N + 1):
        return {"tokens": len(toks), "literal": set(), "normalizada": set(), "firmas": {}}
    return {"tokens": len(toks), "literal": lit, "normalizada": nor, "firmas": firmas}


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
                fa, fb = ha.get("firmas", {}), hb.get("firmas", {})
                iguales = [(pa, pb) for pa, sa in sorted(fa.items()) for pb, sb in sorted(fb.items()) if sa == sb]
                pares.append({"a": a, "b": b, "archivos_a": len(fa), "archivos_b": len(fb),
                              "archivos_identicos": iguales, "literal": round(lit, 4), "normalizada": round(nor, 4),
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
        L += ["", "## Archivos idénticos por pareja", "",
              "Idénticos = mismos tokens de código, sin contar comentarios ni espacios, y fuera de la base entregada.", ""]
        for p in res["pares"]:
            n = len(p["archivos_identicos"])
            L.append(f"### {p['a']} ↔ {p['b']}")
            L.append(f"{n} archivo(s) idéntico(s) de {p['archivos_a']} y {p['archivos_b']} con código propio.")
            L += [f"- `{x}` = `{y}`" for x, y in p["archivos_identicos"]] + [""]
    else:
        L.append("Ningún par supera el umbral.")
    if res["insuficientes"]:
        L += ["", "Sin código suficiente para comparar: " + ", ".join(res["insuficientes"])]
    return "\n".join(L) + "\n"


def aplicar_sancion(resultados, sim, desde, excepto=()):
    """Decisión docente: nota 0.0 a quienes aparezcan en un par con puntaje >= `desde`.

    No toca la nota automática: añade r["sancion"] con motivo y pareja, para revertirlo con
    solo quitar la opción. `excepto` lista estudiantes (texto contenido en el nombre) a salvar.
    Devuelve los nombres afectados."""
    por_nombre = {r["estudiante"]: r for r in resultados}
    afectados = []
    for p in sim["pares"]:
        if p["puntaje"] < desde:
            continue
        for yo, otro in ((p["a"], p["b"]), (p["b"], p["a"])):
            r = por_nombre.get(yo)
            if r is None or any(e.lower() in yo.lower() for e in excepto):
                continue
            r.setdefault("sancion", {"nota": 0.0, "parejas": [],
                                     "motivo": f"Decisión docente: similitud de código >= {desde:.2f} en parcial individual"})
            if otro not in r["sancion"]["parejas"]:
                r["sancion"]["parejas"].append(otro)
            if yo not in afectados:
                afectados.append(yo)
    return afectados
