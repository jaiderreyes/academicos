"""Preparación segura de espacios de prueba locales."""
import json
from pathlib import Path
import shutil

from .storage import atomic_write, safe_path

SUPPORTED = {'.pdf', '.docx', '.zip'}
MARKER = '.academicos-workspace.json'


def _paths(workspace: Path):
    root = workspace.expanduser().resolve()
    return root, root / 'entrada', root / 'salida', root / MARKER


def _initialize(workspace: Path):
    root, source, output, marker = _paths(workspace)
    if not marker.exists():
        for directory in (source, output):
            if directory.exists() and (directory.is_symlink() or not directory.is_dir() or any(directory.iterdir())):
                raise ValueError('La carpeta existente no está vacía ni administrada por academicOS')
    source.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    atomic_write(marker, json.dumps({'kind': 'academicos-test-workspace', 'version': 1}).encode())
    return root, source, output


def _require_managed(workspace: Path):
    root, source, output, marker = _paths(workspace)
    if not marker.is_file():
        raise ValueError('La carpeta no es un espacio de prueba administrado por academicOS')
    try:
        data = json.loads(marker.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('El marcador del espacio de prueba no es válido') from exc
    if data.get('kind') != 'academicos-test-workspace' or data.get('version') != 1:
        raise ValueError('El marcador del espacio de prueba no es compatible')
    for path in (source, output):
        if not path.is_dir() or path.is_symlink():
            raise ValueError('El espacio de prueba no tiene una estructura segura')
    return root, source, output


def _clear(directory: Path):
    removed = 0
    for child in list(directory.iterdir()):
        safe_path(directory, child)
        if child.is_symlink() or child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child)
        removed += 1
    return removed


def clean_workspace(workspace: Path, include_input=False):
    root, source, output = _require_managed(workspace)
    removed_output = _clear(output)
    removed_input = _clear(source) if include_input else 0
    return {
        'workspace': str(root), 'input': str(source), 'output': str(output),
        'removed_input_items': removed_input, 'removed_output_items': removed_output,
    }


def prepare_material(material: Path, workspace: Path, clean=False):
    material = material.expanduser().resolve()
    root = workspace.expanduser().resolve()
    if not material.exists():
        raise ValueError('La ruta del material no existe')
    if material == root or material.is_relative_to(root) or root.is_relative_to(material):
        raise ValueError('El material y el espacio de prueba no pueden estar solapados')
    root, destination, _ = _initialize(root)
    if clean:
        clean_workspace(root, include_input=True)
    if material.is_file():
        candidates = [(material, Path(material.name))] if material.suffix.lower() in SUPPORTED else []
    elif material.is_dir():
        candidates = [(path, path.relative_to(material)) for path in sorted(material.rglob('*'))
                      if path.is_file() and not path.is_symlink() and path.suffix.lower() in SUPPORTED]
    else:
        candidates = []
    if not candidates:
        raise ValueError('No se encontraron archivos PDF, DOCX o ZIP')
    copied = []
    for source, relative in candidates:
        target = safe_path(destination, destination / relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(relative.as_posix())
    return {
        'workspace': str(root), 'input': str(destination), 'output': str(root / 'salida'),
        'copied': copied, 'copied_count': len(copied),
    }
