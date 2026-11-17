"""Compilar y ejecutar código de estudiantes dentro de Docker (spec 006, J-05).

Reglas: sin red, sin privilegios, límites de memoria/CPU/procesos/tiempo, copia del
proyecto montada en solo lectura y trabajo en tmpfs. Cada contenedor usa --rm, un nombre
`academicos-<id>` y la etiqueta `academicos.review=1`. Este módulo nunca ejecuta
`docker prune` ni borra imágenes o volúmenes.
"""
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_IMAGE = "eclipse-temurin:17-jdk"
MAX_OUTPUT_CHARS = 20000
NAME_PREFIX = "academicos-"
LABEL = "academicos.review=1"


@dataclass
class StepResult:
    step: str
    status: str            # ok | fail | timeout | no_verificable
    exit_code: object = None
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0
    command: str = ""
    note: str = ""

    def to_dict(self):
        return dict(self.__dict__)


def _truncate(text):
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n[... recortado, {len(text) - MAX_OUTPUT_CHARS} caracteres más]"


def _decode(data):
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    return data or ""


@dataclass
class DockerRunner:
    image: str = DEFAULT_IMAGE
    memory: str = "512m"
    cpus: str = "1"
    pids: int = 128
    tmpfs_mb: int = 128
    docker: str = "docker"
    run: object = field(default=subprocess.run, repr=False)  # inyectable en pruebas

    # ---- disponibilidad -------------------------------------------------
    def available(self):
        try:
            r = self.run([self.docker, "version", "--format", "{{.Server.Version}}"],
                         capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return r.returncode == 0

    def image_present(self):
        try:
            r = self.run([self.docker, "image", "inspect", self.image],
                         capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return r.returncode == 0

    def pull_image(self, timeout=600):
        """Descargar la imagen (solo si la persona lo pide de forma explícita)."""
        r = self.run([self.docker, "pull", self.image], capture_output=True, text=True,
                     timeout=timeout)
        return r.returncode == 0

    # ---- construcción del comando --------------------------------------
    def build_command(self, name, work, out, script, out_writable, network="none"):
        out_mode = "rw" if out_writable else "ro"
        return [
            self.docker, "run", "--rm", "--name", name, "--label", LABEL,
            "--network", network,
            "--memory", self.memory, "--memory-swap", self.memory,
            "--cpus", str(self.cpus), "--pids-limit", str(self.pids),
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--read-only", "--tmpfs", f"/tmp:rw,size={self.tmpfs_mb}m",
            "--user", "1000:1000",
            "-v", f"{work}:/work:ro", "-v", f"{out}:/out:{out_mode}",
            "-w", "/tmp",
            self.image, "sh", "-c", script,
        ]

    def _kill(self, name):
        try:
            self.run([self.docker, "kill", name], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def step(self, label, script, work, out, out_writable, timeout, stdin=None):
        if not self.available():
            return StepResult(label, "no_verificable",
                              note="Docker no está disponible", command=script)
        name = NAME_PREFIX + uuid.uuid4().hex[:12]
        cmd = self.build_command(name, work, out, script, out_writable)
        started = time.monotonic()
        try:
            r = self.run(cmd, capture_output=True, input=stdin, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            self._kill(name)
            return StepResult(label, "timeout", None, _truncate(_decode(exc.stdout)),
                              _truncate(_decode(exc.stderr)),
                              round(time.monotonic() - started, 2), script,
                              f"superó {timeout} s y se detuvo el contenedor")
        except OSError as exc:
            return StepResult(label, "no_verificable", note=f"no se pudo lanzar Docker: {exc}",
                              command=script)
        dur = round(time.monotonic() - started, 2)
        code = r.returncode
        stderr = _decode(r.stderr)
        if code == 125 and "Unable to find image" in stderr:
            return StepResult(label, "no_verificable", code, "", _truncate(stderr), dur,
                              script, f"falta la imagen {self.image}; descárgala una vez")
        status = "ok" if code == 0 else "fail"
        return StepResult(label, status, code, _truncate(_decode(r.stdout)),
                          _truncate(stderr), dur, script)

    # ---- pasos de alto nivel -------------------------------------------
    def compile(self, info, work, out, timeout=120):
        """javac sobre las fuentes que no dependen de JUnit; salida en `out`."""
        incluidos = [f for f in info.files if not f.uses_junit or f.has_main]
        files = [f.path for f in incluidos]
        if not files:
            return StepResult("compilar", "no_verificable", note="no hay fuentes para compilar")
        args = " ".join(shlex.quote("/work/" + p) for p in files)
        script = f"javac -encoding UTF-8 -d /out {args}"
        res = self.step("compilar", script, work, out, True, timeout)
        skipped = [f.path for f in info.files if f not in incluidos]
        if skipped:
            res.note = (res.note + "; " if res.note else "") + \
                "omitidos por JUnit: " + ", ".join(skipped)
        return res

    def execute(self, main_class, work, out, args=(), stdin=None, timeout=30):
        """java -cp /out <clase>, con una copia escribible del proyecto en /tmp/w."""
        a = " ".join(shlex.quote(x) for x in args)
        script = (f"cp -r /work/. /tmp/w && cd /tmp/w && "
                  f"java -Xmx256m -cp /out {shlex.quote(main_class)} {a}").strip()
        return self.step("ejecutar", script, work, out, False, timeout, stdin=stdin)


def compile_and_run(runner, info, work, main_class=None, args=(), stdin=None,
                    compile_timeout=120, run_timeout=30):
    """Compilar y, si compila, ejecutar. Devuelve la lista de pasos en orden."""
    out = Path(tempfile.mkdtemp(prefix="academicos-out-"))
    out.chmod(0o777)
    try:
        steps = [runner.compile(info, work, out, compile_timeout)]
        if steps[0].status != "ok":
            return steps
        clase = main_class or (info.main_classes[0] if info.main_classes else None)
        if clase is None:
            steps.append(StepResult("ejecutar", "no_verificable",
                                    note="no se detectó clase con main()"))
            return steps
        steps.append(runner.execute(clase, work, out, args, stdin, run_timeout))
        return steps
    finally:
        import shutil
        shutil.rmtree(out, ignore_errors=True)


SELFCHECK_JAVA = """
public class Check {
  public static void main(String[] a) throws Exception {
    String modo = a.length > 0 ? a[0] : "ok";
    if (modo.equals("red")) {
      try (java.net.Socket s = new java.net.Socket()) {
        s.connect(new java.net.InetSocketAddress("1.1.1.1", 53), 2000);
        System.out.println("RED_ABIERTA");
      } catch (Exception e) { System.out.println("RED_BLOQUEADA"); }
    } else if (modo.equals("escribir")) {
      try { new java.io.FileWriter("/work/x.txt").close(); System.out.println("ESCRIBIO_WORK"); }
      catch (Exception e) { System.out.println("WORK_SOLO_LECTURA"); }
    } else if (modo.equals("bucle")) { while (true) { } }
    else { System.out.println("HOLA"); }
  }
}
"""


def selfcheck(runner=None, pull=False):
    """Comprobar en la máquina real: ejecución, red bloqueada, /work de solo lectura, tiempo."""
    runner = runner or DockerRunner()
    informe = {"image": runner.image, "docker": runner.available(), "checks": {}}
    if not informe["docker"]:
        informe["ok"] = False
        return informe
    if not runner.image_present():
        if not pull:
            informe["ok"] = False
            informe["note"] = f"falta la imagen; ejecuta: docker pull {runner.image}"
            return informe
        runner.pull_image()
    from .javaproject import detect_project
    with tempfile.TemporaryDirectory(prefix="academicos-selfcheck-") as t:
        work = Path(t) / "p"
        work.mkdir()
        (work / "Check.java").write_text(SELFCHECK_JAVA, encoding="utf-8")
        work.chmod(0o755)
        info = detect_project(work)
        out = Path(t) / "out"
        out.mkdir()
        out.chmod(0o777)
        comp = runner.compile(info, work, out)
        informe["checks"]["compila"] = comp.status == "ok"
        if comp.status == "ok":
            for modo, esperado in (("ok", "HOLA"), ("red", "RED_BLOQUEADA"),
                                   ("escribir", "WORK_SOLO_LECTURA")):
                r = runner.execute("Check", work, out, [modo], timeout=30)
                informe["checks"][modo] = esperado in r.stdout
            r = runner.execute("Check", work, out, ["bucle"], timeout=5)
            informe["checks"]["tiempo_maximo"] = r.status == "timeout"
            informe["checks"]["sin_contenedores_huerfanos"] = _sin_huerfanos(runner)
    informe["ok"] = bool(informe["checks"]) and all(informe["checks"].values())
    return informe


def _sin_huerfanos(runner):
    try:
        r = runner.run([runner.docker, "ps", "-a", "--filter", f"label={LABEL}", "-q"],
                       capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and not r.stdout.strip()


if __name__ == "__main__":
    import json
    resultado = selfcheck(pull="--pull" in sys.argv)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    sys.exit(0 if resultado.get("ok") else 1)
