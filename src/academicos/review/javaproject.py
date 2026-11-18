"""Detección de estructura de proyectos Java y copia de trabajo (spec 006, J-04).

Nunca modifica el origen: lee, calcula huellas y copia fuentes a un directorio aparte.
"""
import hashlib
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

IGNORED_DIRS = {"build", "dist", "target", "out", "bin", ".git", ".idea", ".gradle",
                "__MACOSX", "node_modules", "private"}
IGNORED_FILES = {".DS_Store", "Thumbs.db"}
MAIN_RE = re.compile(r"public\s+static\s+void\s+main\s*\(")
PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
PUBLIC_TYPE_RE = re.compile(r"^\s*public\s+(?:final\s+|abstract\s+)*(?:class|interface|enum|record)\s+(\w+)", re.M)
TEST_DIRS = {"test", "tests", "prueba", "pruebas"}
TEST_NAME_RE = re.compile(r"(test|prueba)", re.I)
JUNIT_RE = re.compile(r"import\s+(?:static\s+)?org\.junit")
MAX_ZIP_FILES = 2000
MAX_ZIP_BYTES = 200 * 1024 * 1024


class ProjectError(ValueError):
    """Origen inválido o inseguro."""


@dataclass
class JavaFile:
    path: str            # relativo a la raíz del proyecto, con '/'
    package: str
    public_types: list
    has_main: bool
    uses_junit: bool
    packages_declared: int = 1


@dataclass
class ProjectInfo:
    kind: str            # netbeans | maven | ant | src | single
    root: str            # ruta absoluta de la raíz detectada
    source_roots: list   # relativas a la raíz
    files: list = field(default_factory=list)
    main_classes: list = field(default_factory=list)   # nombres completos
    test_files: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    origin: str = ""     # ruta original (carpeta, .java o .zip)

    def to_dict(self):
        return {"kind": self.kind, "origin": self.origin, "root": self.root,
                "source_roots": self.source_roots, "main_classes": self.main_classes,
                "test_files": self.test_files, "warnings": self.warnings,
                "java_files": [f.__dict__ for f in self.files]}


def _read(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _skip(rel_parts):
    return any(p in IGNORED_DIRS for p in rel_parts[:-1]) or rel_parts[-1] in IGNORED_FILES


def _java_files(root):
    root = Path(root)
    for p in sorted(root.rglob("*.java")):
        rel = p.relative_to(root)
        if p.is_symlink() or _skip(rel.parts):
            continue
        yield p, rel


def _analyze(root, warnings):
    files, mains, tests = [], [], []
    source_roots = set()
    for p, rel in _java_files(root):
        text = _read(p)
        packages = PACKAGE_RE.findall(text)
        pkg = packages[0] if packages else ""
        public = PUBLIC_TYPE_RE.findall(text)
        has_main = bool(MAIN_RE.search(text))
        junit = bool(JUNIT_RE.search(text))
        jf = JavaFile(rel.as_posix(), pkg, public, has_main, junit, len(packages))
        files.append(jf)
        if len(packages) > 1:
            warnings.append(f"{jf.path}: {len(packages)} declaraciones 'package' "
                            "(archivo concatenado; no compila tal cual)")
        if len(public) > 1:
            warnings.append(f"{jf.path}: {len(public)} tipos públicos en un archivo "
                            "(Java exige uno por archivo)")
        folder = rel.parent
        if pkg and len(packages) == 1:
            suffix = Path(*pkg.split("."))
            if folder.parts[-len(suffix.parts):] == suffix.parts:
                folder = Path(*folder.parts[:len(folder.parts) - len(suffix.parts)])
            else:
                warnings.append(f"{jf.path}: el paquete '{pkg}' no coincide con la carpeta")
        source_roots.add(folder.as_posix() if folder.parts else ".")
        if has_main and len(packages) <= 1:
            stem = rel.stem
            mains.append(f"{pkg}.{stem}" if pkg else stem)
        if junit or TEST_DIRS & set(x.lower() for x in rel.parts[:-1]) \
                or TEST_NAME_RE.search(rel.stem):
            tests.append(rel.as_posix())
    return files, mains, tests, sorted(source_roots)


def _kind_of(root):
    root = Path(root)
    if (root / "pom.xml").is_file():
        return "maven"
    if (root / "nbproject" / "project.xml").is_file():
        return "netbeans"
    if (root / "build.xml").is_file():
        return "ant"
    return "src"


def detect_project(origin, extract_to=None):
    """Analizar una carpeta, un archivo .java o un .zip.

    Para .zip se necesita `extract_to` (directorio elegido por quien llama). Un .java
    suelto se analiza solo a sí mismo, sin mirar a sus vecinos.
    """
    origin = Path(origin)
    if not origin.exists():
        raise ProjectError(f"no existe: {origin}")
    warnings = []
    if origin.is_file() and origin.suffix.lower() == ".java":
        text = _read(origin)
        packages = PACKAGE_RE.findall(text)
        public = PUBLIC_TYPE_RE.findall(text)
        has_main = bool(MAIN_RE.search(text))
        junit = bool(JUNIT_RE.search(text))
        jf = JavaFile(origin.name, packages[0] if packages else "", public, has_main,
                      junit, len(packages))
        if len(packages) > 1:
            warnings.append(f"{origin.name}: {len(packages)} declaraciones 'package' "
                            "(archivo concatenado; no compila tal cual)")
        if len(public) > 1:
            warnings.append(f"{origin.name}: {len(public)} tipos públicos en un archivo "
                            "(Java exige uno por archivo)")
        mains = []
        if has_main and len(packages) <= 1:
            mains = [f"{jf.package + '.' if jf.package else ''}{origin.stem}"]
        elif has_main:
            warnings.append(f"{origin.name}: hay main() pero con varios paquetes no se "
                            "puede deducir la clase principal sin separar el archivo")
        tests = [origin.name] if junit or TEST_NAME_RE.search(origin.stem) else []
        return ProjectInfo("single", str(origin.parent), ["."], [jf], mains,
                           tests, warnings, str(origin))
    if origin.is_file() and origin.suffix.lower() == ".zip":
        if extract_to is None:
            raise ProjectError("para un .zip indica extract_to")
        root = safe_extract(origin, extract_to)
        root = _descend_single_dir(root)
    elif origin.is_dir():
        root = origin
    else:
        raise ProjectError(f"formato no soportado: {origin.name}")
    files, mains, tests, source_roots = _analyze(root, warnings)
    if not files and origin.is_file() and origin.suffix.lower() == ".zip":
        # zip dentro de zip: solo dentro del destino de trabajo; el original nunca se toca
        _expandir_zips_anidados(root)
        files, mains, tests, source_roots = _analyze(root, warnings)
        if files:
            warnings.append("el código estaba dentro de un .zip anidado")
    if not files:
        raise ProjectError(f"no hay archivos .java en {origin.name}")
    return ProjectInfo(_kind_of(root), str(root), source_roots, files, mains, tests,
                       warnings, str(origin))


def _expandir_zips_anidados(root, max_nivel=3):
    """Si no hay .java pero hay .zip dentro (p. ej. un zip dentro de otro), los extrae junto a ellos.

    Usa safe_extract (protección contra rutas fuera del destino). Devuelve la raíz donde buscar."""
    root = Path(root)
    for nivel in range(max_nivel):
        if any(True for _ in _java_files(root)):
            return root
        zips = [z for z in sorted(root.rglob("*.zip")) if not z.is_symlink() and "__MACOSX" not in z.parts]
        if not zips:
            return root
        for i, z in enumerate(zips):
            try:
                safe_extract(z, z.parent / f"_anidado_{nivel}_{i}")
            except (ProjectError, OSError):
                continue
    return root


def _descend_single_dir(root):
    """Si el ZIP trae una única carpeta contenedora, usarla como raíz."""
    root = Path(root)
    while True:
        entries = [e for e in root.iterdir() if e.name not in IGNORED_FILES
                   and e.name != "__MACOSX"]
        if any((root / n).exists() for n in ("pom.xml", "build.xml", "nbproject")):
            return root
        if len(entries) == 1 and entries[0].is_dir():
            root = entries[0]
            continue
        return root


def safe_extract(zip_path, dest):
    """Extraer sin salirse de `dest` y con límites de archivos y tamaño."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    base = dest.resolve()
    try:
        with zipfile.ZipFile(zip_path) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ZIP_FILES:
                raise ProjectError(f"el ZIP tiene {len(infos)} entradas (máximo {MAX_ZIP_FILES})")
            if sum(i.file_size for i in infos) > MAX_ZIP_BYTES:
                raise ProjectError("el ZIP descomprimido supera el tamaño máximo")
            for i in infos:
                target = (base / i.filename).resolve()
                if base != target and base not in target.parents:
                    raise ProjectError(f"entrada fuera del destino: {i.filename}")
                if (i.external_attr >> 16) & 0o170000 == 0o120000:
                    continue  # enlaces simbólicos: se omiten
                if i.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(i) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
    except zipfile.BadZipFile as exc:
        raise ProjectError(f"ZIP inválido: {zip_path}") from exc
    return base


def fingerprint(path):
    """SHA-256 por archivo (clave relativa con '/'); sirve para probar que el origen no cambió."""
    path = Path(path)
    if path.is_file():
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()}
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob("*")) if p.is_file() and not p.is_symlink()}


def prepare_copy(info, dest):
    """Copiar solo fuentes y recursos a `dest` (vacío o inexistente); excluye compilados."""
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise ProjectError(f"el destino no está vacío: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    root = Path(info.root)
    if info.kind == "single":
        src = Path(info.origin)
        shutil.copy2(src, dest / src.name)
        return dest
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_symlink() or not p.is_file() or _skip(rel.parts):
            continue
        if p.suffix == ".class":
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
    return dest


def find_candidates(student_dir):
    """Listar posibles proyectos dentro de una carpeta de estudiante, de mejor a peor.

    Prefiere carpetas (NetBeans/Maven/src) sobre .java sueltos y estos sobre .zip, y deja
    los ZIP como alternativas cuando su contenido ya está como carpeta.
    """
    student_dir = Path(student_dir)
    cands = []
    for e in sorted(student_dir.iterdir()):
        if e.name in IGNORED_FILES or e.name == "__MACOSX" or e.name.startswith("."):
            continue
        if e.is_dir() and any(True for _ in _java_files(e)):
            cands.append((0, e))
        elif e.is_file() and e.suffix.lower() == ".java":
            cands.append((1, e))
        elif e.is_file() and e.suffix.lower() == ".zip":
            cands.append((2, e))
    return [p for _, p in sorted(cands, key=lambda t: (t[0], t[1].name))]
