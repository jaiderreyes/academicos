"""Clonar los repositorios de GitHub que citan las entregas sin código (spec 007).

Solo `git clone` de URLs github.com públicas, en la carpeta de trabajo (nunca en la entrega), sin pedir
credenciales (un repositorio privado falla en vez de quedarse esperando). No ejecuta nada del repositorio.
También cuenta commits por autor (con nuestra propia configuración de git, no la del repositorio clonado).
"""
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

URL = re.compile(r"^https://(?:www\.)?github\.com/([\w.\-]+)/([\w.\-]+?)(?:\.git)?/?$")


def normalizar(url):
    m = URL.match(url.strip().rstrip(").,;"))
    return f"https://github.com/{m.group(1)}/{m.group(2)}.git" if m else None


def _git(cmd, timeout):
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "echo", "GIT_CONFIG_NOSYSTEM": "1"}
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
    return r.returncode, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")


def clonar_enlaces(urls, destino, ejecutar=None, maximo=2, timeout=300):
    """Devuelve (carpetas_clonadas, avisos)."""
    ejecutar = ejecutar or _git
    destino = Path(destino)
    clonadas, avisos, vistos = [], [], set()
    for u in urls:
        url = normalizar(u)
        if not url or url in vistos:
            continue
        vistos.add(url)
        if len(clonadas) >= maximo:
            avisos.append(f"{u}: se omite (máximo {maximo} repositorios por equipo)")
            continue
        carpeta = destino / "_clones" / url.rsplit("/", 2)[-2] / url.rsplit("/", 1)[-1][:-4]
        carpeta.parent.mkdir(parents=True, exist_ok=True)
        try:
            code, _, err = ejecutar(["git", "clone", "--quiet", url, str(carpeta)], timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            avisos.append(f"{u}: no se pudo clonar ({exc.__class__.__name__})")
            continue
        if code == 0:
            clonadas.append(carpeta)
        else:
            avisos.append(f"{u}: no se pudo clonar (¿privado o inexistente?) {err.strip()[-120:]}")
    return clonadas, avisos


def autores(carpeta, ejecutar=None):
    """Commits por autor de un repositorio clonado: {nombre: commits}."""
    ejecutar = ejecutar or _git
    try:
        code, salida, _ = ejecutar(["git", "-C", str(carpeta), "log", "--format=%an"], 60)
    except (OSError, subprocess.SubprocessError):
        return {}
    return dict(Counter(l.strip() for l in salida.splitlines() if l.strip())) if code == 0 else {}
