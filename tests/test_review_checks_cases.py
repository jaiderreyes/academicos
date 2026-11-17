from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from academicos.review.cases import (CaseError, evaluar_salida, load_cases, requisitos_desde_casos,
                                     run_cases)
from academicos.review.checks import (CheckError, parse_checks, requisitos_desde_checks,
                                      run_checks, strip_comments_and_strings)
from academicos.review.javaproject import JavaFile, ProjectInfo
from academicos.review.manual import load_manual
from academicos.review.rubric import RubricError, load_rubric, parse_rubric
from academicos.review.runner import DockerRunner, StepResult

BOVEDA = Path(__file__).resolve().parents[1] / "rubricas" / "boveda-fichas.yaml"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rub(**extra):
    d = {"nombre": "R", "criterios": [{"id": "a", "peso": 70}, {"id": "i", "peso": 30, "tipo": "manual"}],
         "condicion_minima": {"tope": 2.9, "requisitos": [{"id": "r1"}]}}
    d.update(extra)
    return parse_rubric(d)


class ManualTests(unittest.TestCase):
    def test_lee_solo_manuales_y_deja_pendiente_lo_nulo(self):  # AC-J08 / AC-J12
        with TemporaryDirectory() as t:
            r = rub()
            write(Path(t) / "e.yaml", "estudiante: E\npuntajes: {i: 3.5}\nobservaciones: ok\n")
            self.assertEqual(load_manual(Path(t) / "e.yaml", r)["puntajes"], {"i": 3.5})
            write(Path(t) / "n.yaml", "puntajes: {i: null}\n")
            self.assertEqual(load_manual(Path(t) / "n.yaml", r)["puntajes"], {})
            write(Path(t) / "x.yaml", "puntajes: {a: 4}\n")
            with self.assertRaisesRegex(RubricError, "automático"):
                load_manual(Path(t) / "x.yaml", r)
            write(Path(t) / "y.yaml", "puntajes: {zzz: 4}\n")
            with self.assertRaisesRegex(RubricError, "desconocido"):
                load_manual(Path(t) / "y.yaml", r)
            write(Path(t) / "z.yaml", "puntajes: {i: 9}\n")
            with self.assertRaisesRegex(RubricError, "fuera de la escala"):
                load_manual(Path(t) / "z.yaml", r)


class ChecksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def files(self, mapa):
        out = []
        for ruta, texto in mapa.items():
            write(self.root / ruta, texto)
            out.append(JavaFile(ruta, "", [], False, False))
        return out

    def test_quita_comentarios_y_cadenas_conservando_lineas(self):
        t = 'int a; // import java.util.List;\n/* x\n y */ String s = "import java.util.List";\nint b;\n'
        limpio = strip_comments_and_strings(t)
        self.assertNotIn("java.util", limpio)
        self.assertEqual(limpio.count("\n"), t.count("\n"))

    def test_prohibido_uso_cita_archivo_y_linea_e_ignora_comentarios(self):  # AC-J06
        chk = parse_checks([{"id": "p", "tipo": "prohibido_uso", "archivos": "(?i)manual",
                             "patron": r"import\s+java\.util\.(LinkedList|Stack)\b"}])
        fs = self.files({
            "src/manual/Pila.java": "package manual;\n// import java.util.Stack;\nimport java.util.LinkedList;\nclass Pila {}\n",
            "src/app/Main.java": "import java.util.LinkedList;\nclass Main {}\n"})
        r = run_checks(chk, self.root, fs)[0]
        self.assertFalse(r["cumple"])
        self.assertEqual([(h["archivo"], h["linea"]) for h in r["hallazgos"]], [("src/manual/Pila.java", 3)])

    def test_alcance_sin_archivos_no_afirma_nada(self):
        chk = parse_checks([{"id": "p", "tipo": "prohibido_uso", "archivos": "manual", "patron": "x"}])
        r = run_checks(chk, self.root, self.files({"src/A.java": "class A {}\n"}))[0]
        self.assertIsNone(r["cumple"])

    def test_requiere_tipo_por_nombre_sin_distinguir_mayusculas(self):
        chk = parse_checks([{"id": "l", "tipo": "requiere_tipo", "nombres": [r"\w*lista\w*"],
                             "requisito": "r1"}])
        fs = self.files({"s/listafichas.java": "public class listafichas {}\n"})
        r = run_checks(chk, self.root, fs)[0]
        self.assertTrue(r["cumple"])
        self.assertEqual(r["hallazgos"][0]["texto"], "listafichas")
        fs2 = self.files({"s/Otra.java": "// class Lista\nclass Otra {}\n"})
        self.assertFalse(run_checks(chk, self.root, fs2)[0]["cumple"])

    def test_requisitos_desde_checks_combina(self):
        a = {"requisito": "r", "cumple": True}
        self.assertEqual(requisitos_desde_checks([a, dict(a)]), {"r": True})
        self.assertEqual(requisitos_desde_checks([a, dict(a, cumple=None)]), {"r": None})
        self.assertEqual(requisitos_desde_checks([dict(a, cumple=None), dict(a, cumple=False)]), {"r": False})
        self.assertEqual(requisitos_desde_checks([{"requisito": None, "cumple": False}]), {})

    def test_definiciones_invalidas(self):
        with self.assertRaisesRegex(CheckError, "tipo inválido"):
            parse_checks([{"id": "x", "tipo": "otro"}])
        with self.assertRaisesRegex(CheckError, "expresión inválida"):
            parse_checks([{"id": "x", "tipo": "prohibido_uso", "patron": "("}])
        with self.assertRaisesRegex(CheckError, "requisito desconocido"):
            parse_checks([{"id": "x", "tipo": "prohibido_uso", "patron": "a", "requisito": "zz"}], {"r1"})
        with self.assertRaisesRegex(RubricError, "requisito desconocido"):
            rub(verificaciones=[{"id": "x", "tipo": "prohibido_uso", "patron": "a", "requisito": "zz"}])

    def test_rubrica_boveda_carga_verificaciones_y_casos(self):
        r = load_rubric(BOVEDA)
        self.assertEqual([v["id"] for v in r.verificaciones],
                         ["tipo_lista", "tipo_pila", "tipo_cola", "manual_sin_java_util"])
        self.assertTrue(r.casos.endswith("casos/boveda-fichas"))


class FakeDocker:
    def __init__(self, salida=b"", codigo=0):
        self.salida, self.codigo, self.runs = salida, codigo, []

    def __call__(self, cmd, **kw):
        if cmd[1] == "version":
            return SimpleNamespace(returncode=0, stdout="27", stderr="")
        self.runs.append(cmd)
        return SimpleNamespace(returncode=self.codigo, stdout=self.salida, stderr=b"")


class CasesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / "w"
        self.work.mkdir()
        self.info = ProjectInfo("src", str(self.work), ["."], [JavaFile("A.java", "", ["A"], True, False)],
                                ["A"], [], [], str(self.work))
        write(self.root / "casos" / "casos.yaml", """
casos:
  - id: orden
    args: ["_casos/f.txt"]
    requisito: r1
    esperado: {salida_orden: [P1, P2, P3], codigo_salida: 0}
  - id: error
    esperado: {codigo_salida: 2, salida_contiene: ["línea 3"]}
""")

    def test_carga_y_validaciones(self):
        casos = load_cases(self.root / "casos", {"r1"})
        self.assertEqual([c["id"] for c in casos], ["orden", "error"])
        with self.assertRaisesRegex(CaseError, "falta"):
            load_cases(self.root / "nada")
        with self.assertRaisesRegex(CaseError, "requisito desconocido"):
            load_cases(self.root / "casos", {"otro"})

    def test_evaluar_salida(self):
        s = StepResult("e", "ok", 0, stdout="P1 a\nP2 b\nP3 c\n")
        self.assertEqual(evaluar_salida({"salida_orden": ["P1", "P2", "P3"]}, s), [])
        self.assertTrue(evaluar_salida({"salida_orden": ["P2", "P1"]}, s))
        self.assertTrue(evaluar_salida({"codigo_salida": 3}, s))
        self.assertTrue(evaluar_salida({"salida_no_contiene": ["P3"]}, s))
        self.assertTrue(evaluar_salida({"salida_regex": [r"^P9"]}, s))

    def test_run_cases_monta_casos_de_solo_lectura_y_evalua(self):  # AC-J13
        d = FakeDocker(salida=b"P1 a\nP2 b\nP3 c\n")
        casos = load_cases(self.root / "casos")[:1]
        res = run_cases(DockerRunner(run=d), self.info, self.work, self.root / "casos", casos)
        self.assertEqual(res["casos"][0]["estado"], "ok")
        ejec = d.runs[1]
        self.assertIn(f"{self.root / 'casos'}:/casos:ro", ejec)
        self.assertIn("_casos/f.txt", ejec[-1])
        self.assertEqual(requisitos_desde_casos(res["casos"]), {"r1": True})

    def test_caso_que_falla_marca_requisito_false(self):
        d = FakeDocker(salida=b"P3 c\nP1 a\n")
        res = run_cases(DockerRunner(run=d), self.info, self.work, self.root / "casos",
                        load_cases(self.root / "casos")[:1])
        self.assertEqual(res["casos"][0]["estado"], "fail")
        self.assertEqual(requisitos_desde_casos(res["casos"]), {"r1": False})

    def test_no_compila_deja_casos_no_verificables(self):
        d = FakeDocker(codigo=1)
        res = run_cases(DockerRunner(run=d), self.info, self.work, self.root / "casos",
                        load_cases(self.root / "casos"))
        self.assertEqual({c["estado"] for c in res["casos"]}, {"no_verificable"})
        self.assertEqual(res["compilacion"].status, "fail")
        self.assertEqual(requisitos_desde_casos(res["casos"]), {"r1": None})
        self.assertEqual(len(d.runs), 1)


if __name__ == "__main__":
    unittest.main()
