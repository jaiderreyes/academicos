"""Evidencias de entrega pedidas por el enunciado (sección 9): presencia, no calidad.

Solo mira nombres de archivo (incluidos los de dentro de .zip, sin extraer): README, informe,
archivos de entrada válidos e inválidos y las capturas exigidas. Que exista no prueba que sea
bueno: el criterio «Informe y defensa» lo puntúa la persona docente.
"""
import io
import re
import unicodedata
import zipfile
from pathlib import Path

CAPTURAS = [  # (id, descripción, patrón sobre el nombre sin acentos)
    ("compilacion_manual", "Compilación manual", r"compil\w*[_\- ]*manual|manual[_\- ]*compil"),
    ("compilacion_biblioteca", "Compilación con biblioteca", r"compil\w*[_\- ]*(biblioteca|java[_\-.]?util)|(biblioteca|java[_\-.]?util)[_\- ]*compil"),
    ("recorrido_lista", "Recorrido de lista", r"recorrido|(^|[^a-z])lista"),
    ("cambios_pila", "Cambios de pila", r"(^|[^a-z])pila"),
    ("orden_colas", "Orden de colas", r"(^|[^a-z])cola|prioridad"),
    ("mensaje_sol", "Mensaje SOL", r"\bsol\b|mensaje|[_\-]sol"),
    ("error_f05", "Error de F05", r"f05|error"),
    ("comparacion_versiones", "Comparación de versiones", r"comparaci|versiones|equivalen"),
]
_IMG = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic")
_DOC = (".pdf", ".docx", ".doc", ".odt", ".md", ".txt")
MAX_ANIDADO = 60 * 1024 * 1024


def _sin_acentos(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").lower()


def _nombres(carpeta):
    """Rutas relativas de todo lo que hay, mirando dentro de .zip (un nivel de anidado)."""
    out = []
    for p in sorted(Path(carpeta).rglob("*")):
        if not p.is_file() or p.is_symlink() or "__MACOSX" in p.parts or ".git" in p.parts or p.name.startswith("."):
            continue
        rel = p.relative_to(carpeta).as_posix()
        out.append(rel)
        if p.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(p) as z:
                    for i in z.infolist():
                        if i.is_dir() or "__MACOSX" in i.filename:
                            continue
                        out.append(f"{rel}!/{i.filename}")
                        if i.filename.lower().endswith(".zip") and i.file_size <= MAX_ANIDADO:
                            try:
                                with zipfile.ZipFile(io.BytesIO(z.read(i))) as z2:
                                    out += [f"{rel}!/{i.filename}!/{j.filename}" for j in z2.infolist()
                                            if not j.is_dir() and "__MACOSX" not in j.filename]
                            except (zipfile.BadZipFile, OSError):
                                pass
            except (zipfile.BadZipFile, OSError):
                pass
    return out


def escanear(carpeta):
    nombres = _nombres(carpeta)
    base = lambda n: n.rsplit("/", 1)[-1]
    low = [(n, _sin_acentos(base(n))) for n in nombres]
    readme = [n for n, b in low if re.match(r"readme(\.|$)", b)]
    informe = [n for n, b in low if b.endswith(_DOC) and re.search(r"informe|reporte", b)]
    imgs = [(n, b) for n, b in low if b.endswith(_IMG)]
    capturas = {}
    for cid, desc, pat in CAPTURAS:
        capturas[cid] = any(re.search(pat, b) for _, b in imgs)
    datos = [(n, b) for n, b in low if b.endswith(".txt") and re.search(r"(^|/)datos/", _sin_acentos(n).replace("!/", "/"))]
    inval = [n for n, b in datos if re.search(r"inv|err|incorrect|sin_apertura|repetid|fuera|incomplet|inexist", b)]
    valid = [n for n, b in datos if n not in inval]
    return {"readme": readme[:3], "informe": informe[:3], "capturas_total": len(imgs),
            "capturas": capturas, "datos_validos": len(valid), "datos_invalidos": len(inval)}


def lineas_md(e):
    ok = lambda b: "sí" if b else "NO"
    L = ["", "## Evidencias de entrega (sección 9 del enunciado)", "",
         "Solo presencia de archivos, no calidad. Sin defensa: lo que falte descuenta del criterio Informe.", "",
         f"- README: {ok(e['readme'])}",
         f"- Informe (pdf/doc): {ok(e['informe'])}" + (f" · `{e['informe'][0].rsplit('/', 1)[-1]}`" if e["informe"] else ""),
         f"- Archivos de entrada: {e['datos_validos']} válido(s) y {e['datos_invalidos']} inválido(s)",
         f"- Capturas: {e['capturas_total']} imagen(es); cubren "
         f"{sum(e['capturas'].values())} de {len(CAPTURAS)} exigidas"]
    faltan = [d for cid, d, _ in CAPTURAS if not e["capturas"][cid]]
    if faltan:
        L.append("  - Sin captura identificable de: " + ", ".join(faltan))
    pj = e.get("puntaje")
    if pj:
        L += ["", f"**Criterio Informe: {pj['presentes']} de {pj['total']} entregables → "
                  f"{5.0 * pj['presentes'] / pj['total']:.2f}.** Descuenta lo que falta: " +
                  (", ".join(pj["faltan"]) if pj["faltan"] else "nada")]
    return L


def items(e):
    """Los 12 entregables de la sección 9: README, informe, entradas válidas e inválidas, 8 capturas."""
    base = [("README", bool(e["readme"])), ("Informe", bool(e["informe"])),
            ("Entradas válidas", e["datos_validos"] > 0), ("Entradas inválidas", e["datos_invalidos"] > 0)]
    return base + [(f"Captura: {d}", e["capturas"][cid]) for cid, d, _ in CAPTURAS]


def puntaje_evidencias(e, escala_max=5.0):
    """Nota del criterio Informe: escala máxima × fracción de entregables presentes.

    Devuelve (nota, detalle). Decisión docente: sin defensa; los entregables faltantes descuentan."""
    it = items(e)
    presentes = sum(1 for _, ok in it if ok)
    nota = round(escala_max * presentes / len(it), 2)
    return nota, {"presentes": presentes, "total": len(it), "faltan": [n for n, ok in it if not ok]}
