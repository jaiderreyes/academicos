"""Levantar un proyecto con `docker compose up` de forma aislada y sondear /health y /metrics (spec 007).

Seguridad: no ejecuta nada si el compose pide privilegios del anfitrión (privileged, network host,
docker.sock, montajes fuera de la carpeta). Usa un nombre de proyecto único y siempre hace
`down -v --remove-orphans` al terminar. Todo comando pasa por `ejecutar`, inyectable para pruebas.
"""
import hashlib
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

PUERTOS_PROHIBIDOS = {22, 2375, 2376}


def _correr(cmd, cwd, timeout):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")


def _http(url, timeout=3.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (solo 127.0.0.1)
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, OSError, ValueError):
        return None


def riesgos(compose):
    """Motivos por los que NO se ejecuta este compose en el equipo de la persona docente."""
    out = []
    for nombre, s in compose["servicios"].items():
        if s["privileged"]:
            out.append(f"{nombre}: privileged")
        if s["network_mode"] == "host":
            out.append(f"{nombre}: network_mode host")
        if s["pid"] == "host":
            out.append(f"{nombre}: pid host")
        if s["cap_add"]:
            out.append(f"{nombre}: cap_add {','.join(map(str, s['cap_add']))}")
        for v in s["volumenes"]:
            origen = v.split(":")[0]
            if "docker.sock" in v:
                out.append(f"{nombre}: monta docker.sock")
            elif origen.startswith(("/", "~")) or origen.startswith(".."):
                out.append(f"{nombre}: montaje fuera del proyecto ({origen})")
    return out


class ComposeRunner:
    def __init__(self, ejecutar=None, http=None, dormir=time.sleep, disponible=None):
        self.ejecutar = ejecutar or _correr
        self.http = http or _http
        self.dormir = dormir
        self._disponible = disponible

    def available(self):
        if self._disponible is not None:
            return self._disponible
        if shutil.which("docker") is None:
            return False
        try:
            code, _, _ = self.ejecutar(["docker", "compose", "version"], None, 20)
            return code == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def evaluar(self, raiz, proyecto, espera=240):
        """Devuelve {levanta, health, metrics, motivo, detalle}. None = no se pudo verificar."""
        comp = proyecto.compose
        if not comp:
            return {"levanta": False, "health": False, "metrics": False, "motivo": "no hay docker-compose.yml",
                    "detalle": {"levanta": "no hay docker-compose.yml"}}
        if not self.available():
            return {"levanta": None, "health": None, "metrics": None, "motivo": "Docker no está disponible"}
        peligros = riesgos(comp)
        if peligros:
            return {"levanta": None, "health": None, "metrics": None,
                    "motivo": "no se ejecutó por seguridad: " + "; ".join(peligros[:4])}
        cdir = str((Path(raiz) / comp["archivo"]).parent)
        archivo = Path(comp["archivo"]).name
        nombre = "acad" + hashlib.sha1(str(raiz).encode()).hexdigest()[:10]
        base = ["docker", "compose", "-p", nombre, "-f", archivo]
        res = {"levanta": False, "health": None, "metrics": None, "detalle": {}, "motivo": ""}
        try:
            code, _, err = self.ejecutar(base + ["up", "-d", "--build", "--wait", "--wait-timeout", str(espera)],
                                         cdir, espera + 900)
            res["levanta"] = code == 0
            res["detalle"]["levanta"] = "ok" if code == 0 else ("falló: " + err.strip()[-300:])
            _, salida, _ = self.ejecutar(base + ["ps", "--format", "json"], cdir, 60)
            self._sondear(comp, salida, res)
        except subprocess.TimeoutExpired:
            res["detalle"]["levanta"] = "tiempo de espera agotado"
        except (OSError, subprocess.SubprocessError) as exc:
            res["detalle"]["levanta"] = f"error al ejecutar docker ({exc.__class__.__name__})"
        finally:
            try:
                self.ejecutar(base + ["down", "-v", "--remove-orphans"], cdir, 300)
            except (OSError, subprocess.SubprocessError):
                res["motivo"] = "revisa que no queden contenedores acad* corriendo (docker ps)"
        return res

    def _sondear(self, comp, salida_ps, res):
        """Sondea /health y /metrics en los puertos publicados de los servicios construidos por el equipo."""
        publicados = {}
        for linea in (salida_ps or "").splitlines():
            try:
                d = json.loads(linea)
            except ValueError:
                continue
            for p in d.get("Publishers") or []:
                if p.get("PublishedPort"):
                    publicados.setdefault(d.get("Service", ""), set()).add(int(p["PublishedPort"]))
        propios = [n for n, s in comp["servicios"].items() if s["build"] and publicados.get(n)]
        if not propios:
            res["detalle"]["health"] = res["detalle"]["metrics"] = "ningún servicio propio publica puertos"
            return
        for ruta, clave in (("/health", "health"), ("/metrics", "metrics")):
            fallas = []
            for n in propios:
                ok = any(self.http(f"http://127.0.0.1:{p}{ruta}") == 200
                         for p in sorted(publicados[n]) if p not in PUERTOS_PROHIBIDOS)
                if not ok:
                    fallas.append(n)
            res[clave] = not fallas
            res["detalle"][clave] = ("responden: " + ", ".join(propios)) if not fallas else \
                ("sin respuesta 200 en " + ", ".join(fallas))
