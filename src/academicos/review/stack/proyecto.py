"""Preparar y leer un proyecto distribuido entregado (spec 007).

Extrae zip/rar/7z/tar solo dentro de una carpeta de trabajo (nunca fuera), lee código, documentos,
docker-compose, el informe y las etiquetas de .git SIN ejecutar git ni nada de lo entregado.
"""
import html
import re
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", "site-packages", ".idea", ".vscode",
             ".mypy_cache", ".pytest_cache", "__MACOSX", "target", ".gradle"}
ZIP_EXT, TAR_EXT, OTROS_EXT = (".zip",), (".tar", ".tgz", ".tar.gz", ".tar.bz2", ".tar.xz"), (".rar", ".7z")
MAX_TOTAL = 1536 * 1024 * 1024
MAX_ARCHIVO_TEXTO = 1024 * 1024
MAX_NIVEL = 2
CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".cs", ".rb", ".php", ".kt", ".sql", ".sh",
            ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".conf", ".properties", ".xml", ".hl7",
            ".csv", ".html", ".htm", ".css", ".gradle", ".env", ".tf", ".proto"}
DOC_EXT = {".md", ".txt", ".rst"}
DOC_NOMBRES = {".gitignore", ".dockerignore", ".env.example", ".env.ejemplo", ".env.sample", "readme"}
CODE_NOMBRES = {"dockerfile", "makefile", "jenkinsfile"}
SECCIONES = [  # plantilla v7 (sección 10 del enunciado)
    r"resumen", r"introducci[oó]n", r"objetivos", r"marco te[oó]rico", r"estado del arte",
    r"soluci[oó]n propuesta", r"modelado|uml", r"proceso de desarrollo", r"dise[nñ]o de interfaces",
    r"prototipo", r"viabilidad", r"interoperabilidad", r"resultados", r"conclusiones", r"referencias", r"anexos?",
]
_COMPOSE = re.compile(r"(^|/)(docker-)?compose(\.[\w-]+)?\.ya?ml$", re.I)
_BD = re.compile(r"postgres|citus|mysql|mariadb|mongo|cockroach|timescale|mssql|sqlserver|oracle", re.I)


@dataclass
class Proyecto:
    raiz: Path
    archivos: list = field(default_factory=list)       # rutas relativas (posix) de todo lo entregado
    codigo: dict = field(default_factory=dict)          # ruta -> texto (código y configuración)
    docs: dict = field(default_factory=dict)            # ruta -> texto (md, txt, .gitignore…)
    compose: dict | None = None                         # {archivo, servicios}
    informe: dict | None = None                         # {archivo, texto|None, ...}
    etiquetas: set | None = None                        # None = no hay .git que mirar
    enlaces: list = field(default_factory=list)         # repositorios de GitHub citados en la entrega
    avisos: list = field(default_factory=list)


# --- extracción segura -------------------------------------------------------------------

def _omitible(partes):
    return any(p in SKIP_DIRS for p in partes)


def _dentro(destino, objetivo):
    try:
        objetivo.resolve().relative_to(destino.resolve())
        return True
    except ValueError:
        return False


def _zip(path, destino, presupuesto, avisos):
    try:
        with zipfile.ZipFile(path) as z:
            for i in z.infolist():
                partes = Path(i.filename).parts
                if i.is_dir() or _omitible(partes) or i.filename.startswith("/") or ".." in partes:
                    continue
                if (i.external_attr >> 16) & 0o170000 == 0o120000:      # enlace simbólico
                    continue
                presupuesto["resta"] -= i.file_size
                if presupuesto["resta"] < 0:
                    avisos.append(f"{path.name}: se detuvo la extracción por superar el tamaño máximo")
                    return True
                out = destino / i.filename
                if not _dentro(destino, out):
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(i) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        return True
    except (zipfile.BadZipFile, OSError, NotImplementedError, RuntimeError) as exc:
        avisos.append(f"{path.name}: zip ilegible ({exc.__class__.__name__})")
        return False


def _tar(path, destino, presupuesto, avisos):
    try:
        with tarfile.open(path) as t:
            for m in t:
                partes = Path(m.name).parts
                if not m.isfile() or _omitible(partes) or m.name.startswith("/") or ".." in partes:
                    continue
                presupuesto["resta"] -= m.size
                if presupuesto["resta"] < 0:
                    avisos.append(f"{path.name}: se detuvo la extracción por superar el tamaño máximo")
                    return True
                out = destino / m.name
                if not _dentro(destino, out):
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                with t.extractfile(m) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        return True
    except (tarfile.TarError, OSError) as exc:
        avisos.append(f"{path.name}: tar ilegible ({exc.__class__.__name__})")
        return False


def _herramientas_externas(path, destino):
    """Comandos candidatos para .rar/.7z, en orden de preferencia."""
    d, p = str(destino), str(path)
    return [(["bsdtar", "-xf", p, "-C", d], "bsdtar"),
            (["7zz", "x", "-y", f"-o{d}", p], "7zz"), (["7z", "x", "-y", f"-o{d}", p], "7z"),
            (["7za", "x", "-y", f"-o{d}", p], "7za"),
            (["unrar", "x", "-o+", "-idq", p, d + "/"], "unrar"), (["unar", "-q", "-o", d, "-f", p], "unar")]


def _externo(path, destino, avisos, ejecutar=None):
    real = ejecutar is None
    if real:
        ejecutar = lambda cmd: subprocess.run(cmd, capture_output=True, timeout=300)  # noqa: E731
    for cmd, nombre in _herramientas_externas(path, destino):
        if real and shutil.which(nombre) is None:
            continue
        try:
            r = ejecutar(cmd)
        except (OSError, subprocess.SubprocessError):
            continue
        if getattr(r, "returncode", 1) == 0:
            _quitar_enlaces(destino)
            return True
    avisos.append(f"{path.name}: no se pudo extraer (instala bsdtar, 7z o unrar para abrir archivos {path.suffix})")
    return False


def _quitar_enlaces(raiz):
    for p in Path(raiz).rglob("*"):
        if p.is_symlink():
            try:
                p.unlink()
            except OSError:
                pass


def _es(path, exts):
    n = path.name.lower()
    return any(n.endswith(e) for e in exts)


def _extraer_en(path, destino, nivel, presupuesto, avisos):
    destino.mkdir(parents=True, exist_ok=True)
    if _es(path, ZIP_EXT):
        ok = _zip(path, destino, presupuesto, avisos)
    elif _es(path, TAR_EXT):
        ok = _tar(path, destino, presupuesto, avisos)
    else:
        ok = _externo(path, destino, avisos)
    if ok and nivel < MAX_NIVEL:
        _anidados(destino, nivel + 1, presupuesto, avisos)


def _anidados(raiz, nivel, presupuesto, avisos):
    for p in sorted(Path(raiz).rglob("*")):
        if p.is_file() and not p.is_symlink() and _es(p, ZIP_EXT + TAR_EXT + OTROS_EXT):
            if _omitible(p.relative_to(raiz).parts):
                continue
            _extraer_en(p, p.with_name(p.name + ".x"), nivel, presupuesto, avisos)


def extraer(origenes, destino, avisos=None):
    """Copia/extrae las carpetas de entrega `origenes` en `destino`. Devuelve la lista de avisos."""
    avisos = avisos if avisos is not None else []
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    presupuesto = {"resta": MAX_TOTAL}
    for origen in origenes:
        origen = Path(origen)
        for p in sorted(origen.rglob("*")):
            if not p.is_file() or p.is_symlink():
                continue
            rel = p.relative_to(origen)
            if _omitible(rel.parts):
                continue
            if _es(p, ZIP_EXT + TAR_EXT + OTROS_EXT):
                _extraer_en(p, destino / origen.name / (rel.as_posix() + ".x"), 1, presupuesto, avisos)
            else:
                out = destino / origen.name / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                presupuesto["resta"] -= p.stat().st_size
                if presupuesto["resta"] >= 0:
                    shutil.copy2(p, out)
    return avisos


# --- lectura -----------------------------------------------------------------------------

def _clase(path):
    n, s = path.name.lower(), path.suffix.lower()
    if n in CODE_NOMBRES or s in CODE_EXT:
        return "codigo"
    if n in DOC_NOMBRES or s in DOC_EXT or n.startswith("readme"):
        return "docs"
    return None


def _leer(path):
    try:
        if path.stat().st_size > MAX_ARCHIVO_TEXTO:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:2048]:
        return None
    return data.decode("utf-8", errors="replace")


def _publicados(servicio):
    """Puertos del anfitrión que publica un servicio (acepta ${VAR:-8000}; sin valor por defecto se omite)."""
    out = []
    for p in servicio.get("ports") or []:
        if isinstance(p, dict):
            pub = p.get("published")
        else:
            texto = re.sub(r"\$\{[^}:-]+:?-([^}]*)\}", r"\1", str(p))
            partes = texto.split(":")
            pub = partes[-2] if len(partes) >= 2 else None
        if pub is None:
            continue
        pub = str(pub).split("-")[0].split("/")[0]
        if pub.isdigit():
            out.append(int(pub))
    return out


def parse_compose(texto):
    """Servicios de un docker-compose.yml: imagen, build, healthcheck, puertos y banderas de riesgo."""
    try:
        datos = yaml.safe_load(texto)
    except yaml.YAMLError:
        return None
    if not isinstance(datos, dict) or not isinstance(datos.get("services"), dict):
        return None
    servicios = {}
    for nombre, s in datos["services"].items():
        s = s if isinstance(s, dict) else {}
        servicios[str(nombre)] = {
            "imagen": str(s.get("image") or ""), "build": bool(s.get("build")),
            "healthcheck": bool(s.get("healthcheck")), "puertos": _publicados(s),
            "privileged": bool(s.get("privileged")), "network_mode": str(s.get("network_mode") or ""),
            "volumenes": [str(v if not isinstance(v, dict) else v.get("source", "")) for v in s.get("volumes") or []],
            "cap_add": list(s.get("cap_add") or []), "pid": str(s.get("pid") or ""),
        }
    return {"servicios": servicios}


def sin_proyecto(proy):
    """True si no hay código ni compose que evaluar (solo informe, enlace o nada)."""
    return proy.compose is None and not any(Path(r).suffix.lower() in {".py", ".js", ".ts", ".java", ".go", ".cs", ".sql"}
                                            for r in proy.codigo)


def es_base(nombre, servicio):
    return bool(_BD.search(servicio["imagen"]))


def _texto_docx(path):
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, KeyError, OSError):
        return None
    xml = re.sub(r"</w:p>|<w:br/>|<w:tab/>", "\n", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def _texto_pdf(path):
    exe = shutil.which("pdftotext")
    if exe:
        try:
            r = subprocess.run([exe, "-layout", str(path), "-"], capture_output=True, timeout=120)
            if r.returncode == 0:
                return r.stdout.decode("utf-8", errors="replace")
        except (OSError, subprocess.SubprocessError):
            pass
    try:  # respaldo: markitdown (dependencia de AcademicOS)
        from markitdown import MarkItDown
        return MarkItDown().convert(str(path)).text_content
    except Exception:
        return None


def texto_informe(path):
    s = Path(path).suffix.lower()
    if s == ".docx":
        return _texto_docx(path)
    if s == ".pdf":
        return _texto_pdf(path)
    return _leer(Path(path))


def analizar_informe(texto):
    """Campos medibles del informe (presencia y conteos, no calidad)."""
    if texto is None:
        return {}
    res = None
    for m in re.finditer(r"(?is)\bresumen\b[\s:.\-–—]{0,8}(.*?)(?=\babstract\b|palabras\s+clave|keywords|\bintroducci[oó]n\b)", texto):
        n = len(re.findall(r"\w+", m.group(1)))
        if 30 <= n <= 700:
            res = n
            break
    refs = 0
    idx = [m.start() for m in re.finditer(r"(?im)^\s*(\d+[\.\s]+)?referencias( bibliogr[aá]ficas)?\s*$", texto)]
    cola = texto[idx[-1]:] if idx else ""
    if cola:
        refs = len(re.findall(r"\((?:19|20)\d{2}[a-z]?\)", cola)) or len(re.findall(r"https?://|doi", cola, re.I))
    secciones = sum(1 for s in SECCIONES if re.search(s, texto, re.I))
    return {"resumen_palabras": res, "referencias": refs, "secciones": secciones,
            "palabras": len(re.findall(r"\w+", texto))}


def _buscar_informe(archivos, raiz):
    """Informe = pdf/docx/md llamado informe|reporte; si no hay, el pdf/docx más grande que no sea
    README, guía, enunciado o plantilla (muchos equipos lo nombran con el título del proyecto)."""
    pref = {".pdf": 0, ".docx": 1, ".md": 2}
    raiz = Path(raiz)
    por_nombre, otros = [], []
    for rel in archivos:
        n, s = Path(rel).name.lower(), Path(rel).suffix.lower()
        if s not in pref or n.startswith("readme") or re.search(r"plantilla|gu[ií]a|enunciado|decision|sustentaci", n):
            continue
        (por_nombre if re.search(r"informe|reporte|report", n) else otros).append(rel)
    for rel in sorted(por_nombre, key=lambda r: (pref[Path(r).suffix.lower()], len(r))):
        t = texto_informe(raiz / rel)
        if t:
            return {"archivo": rel, "texto": t, **analizar_informe(t)}
    if por_nombre:
        return {"archivo": por_nombre[0], "texto": None}
    grandes = [r for r in otros if Path(r).suffix.lower() in (".pdf", ".docx") and (raiz / r).stat().st_size > 50_000]
    for rel in sorted(grandes, key=lambda r: -(raiz / r).stat().st_size):
        t = texto_informe(raiz / rel)
        if t and len(re.findall(r"\w+", t)) > 800:
            return {"archivo": rel, "texto": t, **analizar_informe(t)}
    return None


def _etiquetas(raiz):
    gits = [p for p in Path(raiz).rglob(".git") if p.is_dir()]
    if not gits:
        return None
    tags = set()
    for g in gits:
        for t in (g / "refs" / "tags").rglob("*") if (g / "refs" / "tags").is_dir() else []:
            if t.is_file():
                tags.add(t.relative_to(g / "refs" / "tags").as_posix())
        packed = g / "packed-refs"
        if packed.is_file():
            tags.update(re.findall(r"refs/tags/(\S+)", _leer(packed) or ""))
    return tags


def cargar_proyecto(raiz, avisos=None):
    raiz = Path(raiz)
    proy = Proyecto(raiz, avisos=list(avisos or []))
    composes = []
    for p in sorted(raiz.rglob("*")):
        rel = p.relative_to(raiz)
        if not p.is_file() or p.is_symlink() or _omitible(rel.parts) or ".git" in rel.parts:
            continue
        r = rel.as_posix()
        proy.archivos.append(r)
        clase = _clase(p)
        if clase is None and p.suffix == "" and p.stat().st_size <= 4096:
            clase = "docs"          # notas sueltas sin extensión (p. ej. un enlace a GitHub)
        if clase:
            t = _leer(p)
            if t is not None:
                (proy.codigo if clase == "codigo" else proy.docs)[r] = t
        if _COMPOSE.search(r):
            composes.append(r)
    for r in sorted(composes, key=lambda x: (x.count("/"), x)):
        c = parse_compose(proy.codigo.get(r, ""))
        if c:
            c["archivo"] = r
            proy.compose = c
            break
    proy.informe = _buscar_informe(proy.archivos, raiz)
    proy.etiquetas = _etiquetas(raiz)
    enlaces = set()
    for texto in list(proy.docs.values()) + [t for r, t in proy.codigo.items() if len(t) < 4096]:
        enlaces.update(re.findall(r"https?://(?:www\.)?github\.com/[\w.\-]+/[\w.\-]+", texto))
    proy.enlaces = sorted(enlaces)
    return proy
