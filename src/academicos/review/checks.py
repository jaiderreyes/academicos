"""Verificaciones estáticas declaradas en la rúbrica (spec 006, J-06 / RF-J05).

Tipos:
- requiere_tipo: debe declararse al menos un tipo (class/interface/enum/record) cuyo
  nombre cumpla alguna expresión de `nombres`.
- prohibido_uso: ninguna línea de código (sin comentarios ni cadenas) debe cumplir
  `patron`; `archivos` (regex sobre la ruta) acota dónde se busca.
Cada resultado cita archivo y línea y puede alimentar un requisito de la rúbrica.
"""
import re
from pathlib import Path

TIPOS = {"requiere_tipo", "prohibido_uso"}
TYPE_DECL_RE = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_]\w*)")


class CheckError(ValueError):
    """Verificación mal definida."""


def parse_checks(crudas, requisitos_validos=()):
    if crudas is None:
        return ()
    if not isinstance(crudas, list):
        raise CheckError("'verificaciones' debe ser una lista")
    vistos, salida = set(), []
    for c in crudas:
        if not isinstance(c, dict) or not c.get("id"):
            raise CheckError("cada verificación necesita 'id'")
        cid = str(c["id"])
        if cid in vistos:
            raise CheckError(f"verificación repetida: {cid}")
        vistos.add(cid)
        tipo = c.get("tipo")
        if tipo not in TIPOS:
            raise CheckError(f"{cid}: tipo inválido '{tipo}'")
        req = c.get("requisito")
        if req is not None and requisitos_validos and req not in requisitos_validos:
            raise CheckError(f"{cid}: requisito desconocido '{req}'")
        regexes = c.get("nombres") if tipo == "requiere_tipo" else [c.get("patron")]
        if not regexes or not all(isinstance(r, str) and r for r in regexes):
            raise CheckError(f"{cid}: falta " + ("'nombres'" if tipo == "requiere_tipo" else "'patron'"))
        for r in regexes + ([c["archivos"]] if c.get("archivos") else []):
            try:
                re.compile(r)
            except re.error as exc:
                raise CheckError(f"{cid}: expresión inválida {r!r}: {exc}") from exc
        salida.append({"id": cid, "tipo": tipo, "requisito": req,
                       "descripcion": str(c.get("descripcion", cid)),
                       "nombres": list(c["nombres"]) if tipo == "requiere_tipo" else None,
                       "patron": c.get("patron"), "archivos": c.get("archivos")})
    return tuple(salida)


def strip_comments_and_strings(text):
    """Quitar comentarios y literales de texto conservando los saltos de línea."""
    out, i, n = [], 0, len(text)
    while i < n:
        two = text[i:i + 2]
        if two == "//":
            while i < n and text[i] != "\n":
                i += 1
        elif two == "/*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append("".join("\n" if ch == "\n" else " " for ch in text[i:j]))
            i = j
        elif text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"' and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            out.append('""')
            i = min(j + 1, n)
        elif text[i] == "'":
            j = i + 1
            while j < n and text[j] != "'" and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            out.append("' '")
            i = min(j + 1, n)
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _sources(root, files):
    for f in files:
        path = Path(root) / f.path
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        yield f.path, raw, strip_comments_and_strings(raw)


def run_checks(checks, root, files):
    """Ejecutar verificaciones sobre `files` (JavaFile) bajo `root`. Devuelve lista de dicts."""
    fuentes = list(_sources(root, files))
    resultados = []
    for c in checks:
        hallazgos = []
        if c["tipo"] == "requiere_tipo":
            pats = [re.compile(p, re.I) for p in c["nombres"]]
            for ruta, raw, limpio in fuentes:
                for m in TYPE_DECL_RE.finditer(limpio):
                    if any(p.fullmatch(m.group(1)) for p in pats):
                        linea = limpio.count("\n", 0, m.start()) + 1
                        hallazgos.append({"archivo": ruta, "linea": linea, "texto": m.group(1)})
            cumple = bool(hallazgos)
        else:
            patron = re.compile(c["patron"])
            alcance = re.compile(c["archivos"]) if c["archivos"] else None
            evaluados = 0
            for ruta, raw, limpio in fuentes:
                if alcance and not alcance.search(ruta):
                    continue
                evaluados += 1
                crudas = raw.splitlines()
                for n, linea in enumerate(limpio.splitlines(), 1):
                    if patron.search(linea):
                        texto = crudas[n - 1].strip() if n <= len(crudas) else linea.strip()
                        hallazgos.append({"archivo": ruta, "linea": n, "texto": texto})
            # Sin archivos dentro del alcance no se puede afirmar nada.
            cumple = (not hallazgos) if evaluados else None
        resultados.append({"id": c["id"], "tipo": c["tipo"], "requisito": c["requisito"],
                           "descripcion": c["descripcion"], "cumple": cumple,
                           "hallazgos": hallazgos})
    return resultados


def requisitos_desde_checks(resultados):
    """{requisito: True|False|None} — False si falla alguna asociada; None si alguna no es verificable."""
    req = {}
    for r in resultados:
        if r["requisito"] is None:
            continue
        actual = req.get(r["requisito"], True)
        if r["cumple"] is False or actual is False:
            req[r["requisito"]] = False
        elif r["cumple"] is None or actual is None:
            req[r["requisito"]] = None
        else:
            req[r["requisito"]] = True
    return req
