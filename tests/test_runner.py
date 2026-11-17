from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import subprocess
import unittest

from academicos.review.javaproject import JavaFile, ProjectInfo
from academicos.review.runner import (LABEL, DockerRunner, compile_and_run, selfcheck)


class FakeDocker:
    """Simula `docker`: registra llamadas y responde según un guion."""

    def __init__(self, available=True, script=None):
        self.available = available
        self.calls = []
        self.script = script or (lambda cmd: SimpleNamespace(returncode=0, stdout=b"", stderr=b""))

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        if cmd[1] == "version":
            if not self.available:
                raise FileNotFoundError("docker")
            return SimpleNamespace(returncode=0, stdout="27.0", stderr="")
        if cmd[1] == "kill":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return self.script(cmd, **kw) if self.script.__code__.co_argcount > 1 \
            else self.script(cmd)

    def runs(self):
        return [c for c, _ in self.calls if c[1] == "run"]


def info(*files):
    jf = [JavaFile(p, "", ["X"], m, j) for p, m, j in files]
    return ProjectInfo("src", "/x", ["."], jf, ["Main"], [], [], "/x")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name) / "w"
        self.work.mkdir()
        self.out = Path(self.tmp.name) / "o"
        self.out.mkdir()

    def test_comando_con_aislamiento_completo(self):  # AC-J10
        d = FakeDocker()
        r = DockerRunner(run=d)
        r.step("x", "echo hi", self.work, self.out, False, 5)
        cmd = d.runs()[0]
        ju = " ".join(cmd)
        for esperado in ("--rm", "--network none", "--read-only", "--cap-drop ALL",
                         "no-new-privileges", "--pids-limit 128", "--memory 512m",
                         "--memory-swap 512m", "--user 1000:1000", f"label {LABEL}".replace("label ", "--label ")):
            self.assertIn(esperado, ju)
        self.assertIn(f"{self.work}:/work:ro", cmd)
        self.assertIn(f"{self.out}:/out:ro", cmd)
        self.assertTrue(cmd[cmd.index("--name") + 1].startswith("academicos-"))
        self.assertNotIn("prune", ju)

    def test_compilar_monta_out_escribible_y_ejecutar_no(self):
        d = FakeDocker()
        r = DockerRunner(run=d)
        i = info(("A.java", True, False))
        r.compile(i, self.work, self.out)
        r.execute("Main", self.work, self.out)
        self.assertIn(f"{self.out}:/out:rw", d.runs()[0])
        self.assertIn(f"{self.out}:/out:ro", d.runs()[1])

    def test_sin_docker_es_no_verificable(self):  # AC-J11
        r = DockerRunner(run=FakeDocker(available=False))
        res = r.step("compilar", "javac", self.work, self.out, True, 5)
        self.assertEqual(res.status, "no_verificable")
        self.assertIn("no está disponible", res.note)

    def test_timeout_detiene_el_contenedor(self):  # AC-J05
        d = FakeDocker(script=lambda cmd: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(cmd, 5, output=b"parcial", stderr=b"")))
        r = DockerRunner(run=d)
        res = r.step("ejecutar", "java", self.work, self.out, False, 5)
        self.assertEqual(res.status, "timeout")
        self.assertEqual(res.stdout, "parcial")
        kill = [c for c, _ in d.calls if c[1] == "kill"]
        self.assertEqual(len(kill), 1)
        self.assertTrue(kill[0][2].startswith("academicos-"))

    def test_salida_se_recorta_y_codigo_de_salida_se_registra(self):
        grande = b"x" * 30000
        d = FakeDocker(script=lambda cmd: SimpleNamespace(returncode=3, stdout=grande, stderr=b"err"))
        res = DockerRunner(run=d).step("ejecutar", "java", self.work, self.out, False, 5)
        self.assertEqual((res.status, res.exit_code), ("fail", 3))
        self.assertIn("recortado", res.stdout)
        self.assertLess(len(res.stdout), 20100)

    def test_imagen_faltante_es_no_verificable_con_mensaje(self):
        d = FakeDocker(script=lambda cmd: SimpleNamespace(
            returncode=125, stdout=b"", stderr=b"Unable to find image 'x' locally"))
        res = DockerRunner(run=d).step("ejecutar", "java", self.work, self.out, False, 5)
        self.assertEqual(res.status, "no_verificable")
        self.assertIn("descárgala", res.note)

    def test_compilar_omite_pruebas_junit_y_lo_informa(self):
        d = FakeDocker()
        i = info(("A.java", True, False), ("ATest.java", False, True))
        res = DockerRunner(run=d).compile(i, self.work, self.out)
        script = d.runs()[0][-1]
        self.assertIn("/work/A.java", script)
        self.assertNotIn("ATest.java", script.split("-d /out")[1])
        self.assertIn("omitidos por JUnit: ATest.java", res.note)

    def test_compile_and_run_corta_si_no_compila(self):
        d = FakeDocker(script=lambda cmd: SimpleNamespace(returncode=1, stdout=b"", stderr=b"error: x"))
        pasos = compile_and_run(DockerRunner(run=d), info(("A.java", True, False)), self.work)
        self.assertEqual([p.step for p in pasos], ["compilar"])
        self.assertEqual(pasos[0].status, "fail")
        self.assertEqual(len(d.runs()), 1)

    def test_compile_and_run_sin_main_no_ejecuta(self):
        i = info(("A.java", False, False))
        i.main_classes = []
        pasos = compile_and_run(DockerRunner(run=FakeDocker()), i, self.work)
        self.assertEqual(pasos[-1].status, "no_verificable")
        self.assertIn("main()", pasos[-1].note)

    def test_compile_and_run_ejecuta_y_limpia_directorio_de_salida(self):
        d = FakeDocker(script=lambda cmd: SimpleNamespace(returncode=0, stdout=b"HOLA\n", stderr=b""))
        pasos = compile_and_run(DockerRunner(run=d), info(("A.java", True, False)), self.work,
                                args=["datos/f.txt"])
        self.assertEqual([p.status for p in pasos], ["ok", "ok"])
        self.assertIn("datos/f.txt", d.runs()[1][-1])
        out = d.runs()[0][d.runs()[0].index("-v") + 3].split(":")[0]
        self.assertFalse(Path(out).exists())

    def test_selfcheck_sin_docker_y_sin_imagen_no_descarga(self):
        self.assertFalse(selfcheck(DockerRunner(run=FakeDocker(available=False)))["ok"])
        d = FakeDocker(script=lambda cmd: SimpleNamespace(returncode=1, stdout="", stderr=""))
        res = selfcheck(DockerRunner(run=d))
        self.assertFalse(res["ok"])
        self.assertIn("docker pull", res["note"])
        self.assertFalse([c for c, _ in d.calls if c[1] == "pull"])


if __name__ == "__main__":
    unittest.main()
