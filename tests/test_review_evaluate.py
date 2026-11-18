import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from academicos.cli import main
from academicos.review.evaluate import evaluar_entrega
from academicos.review.javaproject import fingerprint
from academicos.review.report import export_course, export_student, markdown
from academicos.review.rubric import parse_rubric
from academicos.review.runner import DockerRunner

MAIN = "public class Main {\n  public static void main(String[] a) {}\n}\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class FakeDocker:
    def __init__(self, available=True, compila=0, salida=b""):
        self.available, self.compila, self.salida, self.runs = available, compila, salida, []

    def __call__(self, cmd, **kw):
        if cmd[1] == "version":
            if not self.available:
                raise FileNotFoundError("docker")
            return SimpleNamespace(returncode=0, stdout="27", stderr="")
        self.runs.append(cmd)
        es_compilar = "javac" in cmd[-1]
        return SimpleNamespace(returncode=self.compila if es_compilar else 0,
                               stdout=b"" if es_compilar else self.salida,
                               stderr=b"error: x" if es_compilar and self.compila else b"")


def rubrica():
    return parse_rubric({
        "nombre": "R", "aprobacion": 3.0,
        "criterios": [{"id": "est", "peso": 70, "evidencia": ["t_lista", "orden"]},
                      {"id": "inf", "peso": 30, "tipo": "manual"}],
        "condicion_minima": {"tope": 2.9, "requisitos": [
            {"id": "compila", "auto": "compila"}, {"id": "base"}]},
        "verificaciones": [{"id": "t_lista", "tipo": "requiere_tipo", "nombres": ["lista\\w*"],
                            "requisito": "base"}]})


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.est = self.root / "Estudiante Uno"
        write(self.est / "Proyecto" / "src" / "Main.java", MAIN)
        write(self.est / "Proyecto" / "src" / "Lista.java", "public class Lista {}\n")
        write(self.est / "Proyecto" / "build" / "Viejo.class", "bin")
        write(self.root / "casos" / "casos.yaml", """
casos:
  - id: orden
    requisito: base
    esperado: {salida_orden: [P1, P2]}
""")
        write(self.root / "man" / "Estudiante Uno.yaml", "puntajes: {inf: 4.0}\nobservaciones: buen informe\n")

    def evaluar(self, docker, manual=True, casos=True):
        return evaluar_entrega(rubrica(), self.root, self.est, DockerRunner(run=docker),
                               manual_path=(self.root / "man" / "Estudiante Uno.yaml") if manual else None,
                               casos_dir=(self.root / "casos") if casos else None)

    def test_todo_cumple_da_nota_completa_y_no_toca_el_original(self):  # AC-J04
        antes = fingerprint(self.est)
        r = self.evaluar(FakeDocker(salida=b"P1 x\nP2 y\n"))
        k = r["calificacion"]
        self.assertTrue(k["completo"])
        self.assertEqual(k["nota_sugerida"], 4.7)  # 5*.7 + 4*.3
        self.assertEqual(r["proyecto"], "Proyecto")
        self.assertTrue(r["integridad"]["intacto"])
        self.assertEqual(fingerprint(self.est), antes)
        self.assertEqual(r["requisitos"], {"compila": True, "base": True})

    def test_no_compila_aplica_tope_y_casos_quedan_sin_verificar(self):  # AC-J02
        r = self.evaluar(FakeDocker(compila=1))
        k = r["calificacion"]
        self.assertEqual(r["requisitos"]["compila"], False)
        self.assertTrue(k["tope_aplicado"] or k["nota_sin_tope"] <= 2.9)
        self.assertLessEqual(k["nota_sugerida"], 2.9)
        self.assertEqual(r["casos"][0]["estado"], "no_verificable")

    def test_sin_docker_todo_lo_dinamico_es_no_verificable(self):  # AC-J03 / AC-J11
        r = self.evaluar(FakeDocker(available=False))
        self.assertEqual(r["compilacion"]["status"], "no_verificable")
        self.assertIsNone(r["requisitos"]["compila"])
        self.assertTrue(r["verificaciones"][0]["cumple"])      # lo estático sí corre
        k = r["calificacion"]
        self.assertFalse(k["completo"])
        est = [c for c in k["criterios"] if c["id"] == "est"][0]
        self.assertEqual(est["estado"], "pendiente")           # evidencia incompleta, no se concluye
        self.assertTrue(any("evidencia incompleta" in a for a in r["avisos"]))

    def test_sin_archivo_manual_queda_pendiente(self):  # AC-J12
        r = self.evaluar(FakeDocker(salida=b"P1\nP2\n"), manual=False)
        inf = [c for c in r["calificacion"]["criterios"] if c["id"] == "inf"][0]
        self.assertEqual(inf["estado"], "pendiente")
        self.assertFalse(r["calificacion"]["completo"])
        self.assertTrue(any("manuales" in a for a in r["avisos"]))

    def test_sin_carpeta_de_casos_avisa_y_no_inventa(self):
        r = self.evaluar(FakeDocker(), casos=False)
        self.assertEqual(r["casos"], [])
        est = [c for c in r["calificacion"]["criterios"] if c["id"] == "est"][0]
        self.assertEqual(est["estado"], "pendiente")

    def test_sin_proyecto_java_informa_error(self):
        vacio = self.root / "Vacio"
        write(vacio / "notas.txt", "x")
        r = evaluar_entrega(rubrica(), self.root, vacio, DockerRunner(run=FakeDocker()))
        self.assertTrue(r["errores"])
        self.assertNotIn("calificacion", r)

    def test_reportes_md_json_y_csv(self):
        r = self.evaluar(FakeDocker(salida=b"P1\nP2\n"))
        rutas = export_student(r, self.root / "sal")
        self.assertEqual(json.loads(Path(rutas["json"]).read_text(encoding="utf-8"))["estudiante"], "Estudiante Uno")
        md = Path(rutas["md"]).read_text(encoding="utf-8")
        self.assertIn("## Nota sugerida", md)
        self.assertIn("Original sin cambios: sí", md)
        parcial = markdown(self.evaluar(FakeDocker(available=False)))
        self.assertIn("Nota PARCIAL (no es una calificación)", parcial)
        csv_path = export_course([r, self.evaluar(FakeDocker(available=False))], self.root / "sal")
        with open(csv_path, encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
        self.assertEqual([f["completa"] for f in filas], ["True", "False"])

    def test_cli_rubric_check_y_no_docker(self):
        yml = self.root / "r.yaml"
        write(yml, "nombre: R\ncriterios:\n  - {id: a, peso: 100, evidencia: [t]}\nverificaciones:\n"
                   "  - {id: t, tipo: requiere_tipo, nombres: ['lista\\w*']}\n")
        self.assertEqual(main(["review", "rubric-check", str(yml)]), 0)
        sal = self.root / "out"
        code = main(["review", "run", "--rubrica", str(yml), "--estudiante", str(self.est),
                     "--salida", str(sal), "--no-docker"])
        self.assertEqual(code, 0)
        self.assertTrue((sal / "Estudiante_Uno.json").is_file())


if __name__ == "__main__":
    unittest.main()
