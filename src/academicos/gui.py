"""Interfaz gráfica local de AcademicOS (solo biblioteca estándar, sin red externa)."""
from __future__ import annotations
import json, subprocess, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path.cwd()
LOG: list[str] = []
ESTADO = {"corriendo": False, "codigo": None}


def _lanzar(cmd: list[str]) -> None:
    ESTADO.update(corriendo=True, codigo=None)
    LOG.clear(); LOG.append("$ " + " ".join(cmd))
    try:
        p = subprocess.Popen(cmd, cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for linea in p.stdout:
            LOG.append(linea.rstrip())
        ESTADO["codigo"] = p.wait()
    except Exception as e:  # pragma: no cover
        LOG.append(f"Error: {e}"); ESTADO["codigo"] = 1
    ESTADO["corriendo"] = False


def comando(d: dict) -> list[str]:
    base = [sys.executable, "-m", "academicos.cli", "review"]
    salida = d.get("salida") or "reportes-gui"
    if d["tipo"] == "stack":
        c = base + ["stack", "--rubrica", d["rubrica"], "--curso", d["curso"], "--salida", salida]
        if d.get("equipos"): c += ["--equipos", d["equipos"]]
        if d.get("no_docker", True): c.append("--no-docker")
    else:
        c = base + ["course", "--rubrica", d["rubrica"], "--curso", d["curso"], "--salida", salida]
        if d.get("no_docker", True): c.append("--no-docker")
    return c


def carpetas_reportes() -> list[str]:
    return sorted(str(p.parent.relative_to(RAIZ)) for p in RAIZ.glob("*/consolidado.csv"))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, cuerpo: bytes, tipo="application/json"):
        self.send_response(200); self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo))); self.end_headers(); self.wfile.write(cuerpo)

    def _json(self, obj): self._send(json.dumps(obj, ensure_ascii=False).encode())

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/":
            self._send((Path(__file__).parent / "gui.html").read_bytes(), "text/html")
        elif u.path == "/api/config":
            self._json({"rubricas": sorted(str(p.relative_to(RAIZ)) for p in (RAIZ / "rubricas").glob("*.yaml")),
                        "reportes": carpetas_reportes()})
        elif u.path == "/api/log":
            self._json({"log": LOG[-400:], **ESTADO})
        elif u.path in ("/api/csv", "/api/md"):
            d = (RAIZ / q.get("dir", [""])[0]).resolve()
            f = d / ("consolidado.csv" if u.path.endswith("csv") else "reporte_general.md")
            if RAIZ.resolve() in d.parents and f.exists(): self._send(f.read_bytes(), "text/plain")
            else: self._send(b"", "text/plain")
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/api/run": return self.send_error(404)
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if ESTADO["corriendo"] or not d.get("rubrica") or not d.get("curso"):
            return self._json({"ok": False})
        threading.Thread(target=_lanzar, args=(comando(d),), daemon=True).start()
        self._json({"ok": True})


def run_gui(puerto: int = 8765, abrir: bool = True) -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", puerto), H)
    url = f"http://127.0.0.1:{puerto}"
    print(f"AcademicOS GUI en {url}  (Ctrl+C para salir)")
    if abrir: webbrowser.open(url)
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    return 0
