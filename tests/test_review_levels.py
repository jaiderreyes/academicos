from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from academicos.review.evaluate import _elegir_main, evaluar_entrega
from academicos.review.javaproject import JavaFile, ProjectInfo
from academicos.review.levels import evaluar_criterio, ids_desconocidos
from academicos.review.rubric import RubricError, load_rubric, parse_rubric
from academicos.review.runner import DockerRunner
from academicos.cli import main

ROOT = Path(__file__).resolve().parents[1]
BOVEDA = ROOT / "rubricas" / "boveda-fichas.yaml"


def crit(**extra):
    niveles = [
        {"nivel": "deficiente", "min": 0.0, "max": 2.9},
        {"nivel": "regular", "min": 3.0, "max": 3.9, "requiere": ["a", "b"]},
        {"nivel": "bueno", "min": 4.0, "max": 4.4, "requiere": ["c"]},
        {"nivel": "excelente", "min": 4.5, "max": 5.0, "manual": True},
    ]
    d = {"nombre": "R", "criterios": [{"id": "x", "peso": 100, "niveles": niveles}]}
    d.update(extra)
    return parse_rubric(d).criterios[0]


class LevelsTests(unittest.TestCase):
    def test_sube_hasta_bueno_y_deja_excelente_al_docente(self):
        r = evaluar_criterio(crit(), {"a": True, "b": True, "c": True})
        self.assertEqual((r["nivel"], r["nota"], r["estado"]), ("bueno", 4.0, "puntuado"))
        self.assertEqual(r["requiere_confirmacion"], "excelente")

    def test_requisito_incumplido_bloquea_y_da_avance_proporcional(self):
        r = evaluar_criterio(crit(), {"a": True, "b": False, "c": True})
        self.assertEqual(r["nivel"], "deficiente")
        self.assertEqual(r["bloqueado_por"], ["b"])
        self.assertEqual(r["nota"], 1.45)  # 2.9 * (1/2)

    def test_niveles_son_acumulativos(self):
        r = evaluar_criterio(crit(), {"a": False, "b": True, "c": True})
        self.assertEqual(r["nivel"], "deficiente")  # cumplir 'bueno' no salta 'regular'

    def test_sin_verificar_deja_pendiente_pero_informa_lo_confirmado(self):  # AC-J03
        r = evaluar_criterio(crit(), {"a": True, "b": True})  # c ausente
        self.assertEqual((r["estado"], r["nota"]), ("pendiente", None))
        self.assertEqual(r["sin_verificar"], ["c"])
        self.assertEqual(r["nivel"], "regular")
        self.assertEqual(r["nota_minima_confirmada"], 3.0)

    def test_registra_lo_no_verificado_del_siguiente_nivel_aunque_este_bloqueado(self):
        r = evaluar_criterio(crit(), {"a": False})   # b queda sin verificar
        self.assertEqual(r["bloqueado_por"], ["a"])
        self.assertEqual(r["no_verificados_siguiente"], ["b"])

    def test_false_domina_sobre_none_en_el_mismo_nivel(self):
        r = evaluar_criterio(crit(), {"a": False})
        self.assertEqual(r["estado"], "puntuado")
        self.assertEqual(r["bloqueado_por"], ["a"])

    def test_definiciones_invalidas(self):
        base = [{"nivel": "d", "min": 0, "max": 2.9}]
        con = lambda extra: parse_rubric({"nombre": "R", "criterios": [
            {"id": "x", "peso": 100, "niveles": base + extra}]})
        with self.assertRaisesRegex(RubricError, "requiere"):
            con([{"nivel": "r", "min": 3, "max": 3.9}])
        with self.assertRaisesRegex(RubricError, "sin solaparse"):
            con([{"nivel": "r", "min": 2.0, "max": 3.9, "requiere": ["a"]}])
        with self.assertRaisesRegex(RubricError, "base"):
            parse_rubric({"nombre": "R", "criterios": [{"id": "x", "peso": 100, "niveles": [
                {"nivel": "d", "min": 0, "max": 2.9, "requiere": ["a"]},
                {"nivel": "r", "min": 3, "max": 3.9, "requiere": ["a"]}]}]})
        with self.assertRaisesRegex(RubricError, "no ambos"):
            parse_rubric({"nombre": "R", "criterios": [{"id": "x", "peso": 100, "evidencia": ["a"], "niveles":
                          base + [{"nivel": "r", "min": 3, "max": 3.9, "requiere": ["a"]}]}]})
        with self.assertRaisesRegex(RubricError, "manual"):
            parse_rubric({"nombre": "R", "criterios": [{"id": "x", "peso": 100, "tipo": "manual", "niveles":
                          base + [{"nivel": "r", "min": 3, "max": 3.9, "requiere": ["a"]}]}]})

    def test_rubrica_boveda_tiene_ids_consistentes_con_sus_casos(self):
        from academicos.review.cases import load_cases
        r = load_rubric(BOVEDA)
        ids = [c["id"] for c in load_cases(ROOT / "casos" / "boveda-fichas", {q.id for q in r.requisitos})]
        self.assertEqual(ids_desconocidos(r, ids), {})
        self.assertEqual(r.clase_principal, "app.Main")
        self.assertEqual([n.nombre for n in r.criterios[0].niveles], ["deficiente", "regular", "bueno", "excelente"])
        self.assertTrue(ids_desconocidos(r, []))  # sin casos, los ids de casos serían desconocidos

    def test_cli_rubric_check_de_boveda_ok(self):
        self.assertEqual(main(["review", "rubric-check", str(BOVEDA)]), 0)


class FakeDocker:
    def __init__(self, salida=b"SOL", available=True):
        self.salida, self.available = salida, available

    def __call__(self, cmd, **kw):
        if cmd[1] == "version":
            if not self.available:
                raise FileNotFoundError
            return SimpleNamespace(returncode=0, stdout="27", stderr="")
        return SimpleNamespace(returncode=0, stdout=b"" if "javac" in cmd[-1] else self.salida, stderr=b"")


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class EvaluateNivelesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.est = self.root / "E"
        w(self.est / "P" / "src" / "app" / "main.java",
          "package app;\npublic class main { public static void main(String[] a) {} }\n")
        w(self.root / "casos" / "casos.yaml", "casos:\n  - id: c1\n    esperado: {salida_regex: ['SOL']}\n")
        self.r = parse_rubric({
            "nombre": "R", "ejecucion": {"clase_principal": "app.Main"},
            "criterios": [{"id": "x", "peso": 70, "niveles": [
                {"nivel": "d", "min": 0, "max": 2.9},
                {"nivel": "regular", "min": 3.0, "max": 3.9, "requiere": ["compila", "c1"]},
                {"nivel": "excelente", "min": 4.5, "max": 5.0, "manual": True}]},
                {"id": "i", "peso": 30, "tipo": "manual"}]})

    def evaluar(self, docker, manual=None):
        return evaluar_entrega(self.r, self.root, self.est, DockerRunner(run=docker),
                               manual_path=manual, casos_dir=self.root / "casos")

    def test_eleccion_de_clase_principal_sin_mayusculas_avisa(self):
        r = self.evaluar(FakeDocker())
        self.assertTrue(any("difiere de 'app.Main'" in a for a in r["avisos"]))
        self.assertEqual(r["niveles"][0]["nivel"], "regular")
        self.assertEqual(r["confirmaciones_docentes"], [{"criterio": "x", "nivel": "excelente"}])

    def test_ajuste_docente_con_motivo_reemplaza_y_conserva_sugerencia(self):
        w(self.root / "m.yaml", "puntajes: {i: 4}\najustes:\n  x: {nota: 4.6, motivo: justificó invariantes}\n")
        r = self.evaluar(FakeDocker(), self.root / "m.yaml")
        k = r["calificacion"]
        x = [c for c in k["criterios"] if c["id"] == "x"][0]
        self.assertEqual(x["nota"], 4.6)
        self.assertEqual(r["manual"]["ajustes"]["x"]["sugerencia_automatica"], 3.0)
        self.assertEqual(r["confirmaciones_docentes"], [])  # ya lo resolvió la persona docente
        self.assertEqual(k["nota_sugerida"], 4.42)  # 4.6*.7 + 4*.3

    def test_ajuste_sin_motivo_o_a_criterio_manual_se_rechaza(self):
        w(self.root / "m1.yaml", "ajustes:\n  x: {nota: 4.6}\n")
        with self.assertRaisesRegex(RubricError, "motivo"):
            self.evaluar(FakeDocker(), self.root / "m1.yaml")
        w(self.root / "m2.yaml", "ajustes:\n  i: {nota: 4, motivo: x}\n")
        with self.assertRaisesRegex(RubricError, "es manual"):
            self.evaluar(FakeDocker(), self.root / "m2.yaml")

    def test_sin_docker_criterio_pendiente_con_motivo(self):
        r = self.evaluar(FakeDocker(available=False))
        n = r["niveles"][0]
        self.assertEqual(n["estado"], "pendiente")
        self.assertTrue(any("criterio 'x' pendiente" in a for a in r["avisos"]))

    def test_id_mal_escrito_en_la_rubrica_se_avisa(self):
        r2 = parse_rubric({"nombre": "R", "criterios": [{"id": "x", "peso": 100, "niveles": [
            {"nivel": "d", "min": 0, "max": 2.9},
            {"nivel": "r", "min": 3.0, "max": 3.9, "requiere": ["c_typo"]}]}]})
        res = evaluar_entrega(r2, self.root, self.est, DockerRunner(run=FakeDocker()),
                              casos_dir=self.root / "casos")
        self.assertTrue(any("'c_typo'" in a and "no existe" in a for a in res["avisos"]))

    def test_elegir_main_prefiere_exacto_y_evita_pruebas(self):
        info = ProjectInfo("src", "/x", ["."], [], ["pruebas.Casos", "app.Main"], [], [], "/x")
        self.assertEqual(_elegir_main(self.r, info, []), "app.Main")
        info.main_classes = ["pruebas.CasosPrueba", "otra.Entrada"]
        self.r2 = parse_rubric({"nombre": "R", "criterios": [{"id": "a", "peso": 100}]})
        self.assertEqual(_elegir_main(self.r2, info, []), "otra.Entrada")


if __name__ == "__main__":
    unittest.main()


class PuntoEnNivelTest(unittest.TestCase):
    def test_medio_usa_el_centro_del_rango(self):
        c = crit()
        base = evaluar_criterio(c, {"a": True, "b": True, "c": True})
        medio = evaluar_criterio(c, {"a": True, "b": True, "c": True}, "medio")
        n = [x for x in c.niveles if x.nombre == medio["nivel"]][0]
        self.assertEqual(base["nota"], n.min)
        self.assertEqual(medio["nota"], (n.min + n.max) / 2)
