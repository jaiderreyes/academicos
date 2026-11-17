from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from academicos.review.rubric import RubricError, load_rubric, parse_rubric, score

BOVEDA = Path(__file__).resolve().parents[1] / "rubricas" / "boveda-fichas.yaml"
TODOS = {"compila_manual": True, "estructuras_basicas": True,
         "orden_prioridad_fifo": True, "encadenar": True}


def base(**cambios):
    datos = {
        "nombre": "Prueba",
        "escala": {"min": 0, "max": 5},
        "aprobacion": 3.0,
        "criterios": [
            {"id": "a", "peso": 60}, {"id": "b", "peso": 40, "tipo": "manual"}],
        "condicion_minima": {"tope": 2.9, "requisitos": [{"id": "r1"}]},
    }
    datos.update(cambios)
    return datos


class RubricParseTests(unittest.TestCase):
    def test_boveda_fichas_carga_con_pesos_del_enunciado(self):
        r = load_rubric(BOVEDA)
        pesos = {c.id: c.peso for c in r.criterios}
        self.assertEqual(pesos, {"modelado": 25, "estructuras": 30,
                                 "validacion": 25, "informe": 20})
        self.assertEqual(r.tope, 2.9)
        self.assertEqual(len(r.requisitos), 4)

    def test_pesos_que_no_suman_100_se_rechazan(self):  # AC-J01
        with self.assertRaisesRegex(RubricError, "suman 90"):
            parse_rubric(base(criterios=[{"id": "a", "peso": 50}, {"id": "b", "peso": 40}]))

    def test_criterio_repetido_tipo_invalido_y_peso_no_positivo(self):
        with self.assertRaisesRegex(RubricError, "repetido"):
            parse_rubric(base(criterios=[{"id": "a", "peso": 50}, {"id": "a", "peso": 50}]))
        with self.assertRaisesRegex(RubricError, "tipo inválido"):
            parse_rubric(base(criterios=[{"id": "a", "peso": 100, "tipo": "x"}]))
        with self.assertRaisesRegex(RubricError, "positivo"):
            parse_rubric(base(criterios=[{"id": "a", "peso": 0}, {"id": "b", "peso": 100}]))

    def test_tope_no_menor_que_aprobacion_se_rechaza(self):
        with self.assertRaisesRegex(RubricError, "menor que la nota"):
            parse_rubric(base(condicion_minima={"tope": 3.0, "requisitos": [{"id": "r1"}]}))

    def test_yaml_invalido_y_forma_incorrecta(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "mala.yaml"
            p.write_text("nombre: [sin cerrar", encoding="utf-8")
            with self.assertRaisesRegex(RubricError, "YAML inválido"):
                load_rubric(p)
        with self.assertRaisesRegex(RubricError, "mapa"):
            parse_rubric(["no", "es", "mapa"])


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.r = parse_rubric(base())

    def test_nota_ponderada_completa(self):
        res = score(self.r, {"a": 4.0, "b": 3.0}, {"r1": True})
        self.assertEqual(res["nota_sugerida"], 3.6)  # 4*.6 + 3*.4
        self.assertTrue(res["completo"])
        self.assertTrue(res["aprueba"])
        self.assertFalse(res["tope_aplicado"])

    def test_requisito_incumplido_aplica_tope(self):  # AC-J02
        res = score(self.r, {"a": 5.0, "b": 5.0}, {"r1": False})
        self.assertEqual(res["nota_sin_tope"], 5.0)
        self.assertEqual(res["nota_sugerida"], 2.9)
        self.assertTrue(res["tope_aplicado"])
        self.assertEqual(res["requisitos_incumplidos"], ["r1"])
        self.assertFalse(res["aprueba"])

    def test_tope_no_sube_una_nota_baja(self):
        res = score(self.r, {"a": 1.0, "b": 1.0}, {"r1": False})
        self.assertEqual(res["nota_sugerida"], 1.0)
        self.assertFalse(res["tope_aplicado"])

    def test_requisito_sin_verificar_no_aplica_tope_ni_cierra_nota(self):  # AC-J03
        res = score(self.r, {"a": 5.0, "b": 5.0}, {})
        self.assertEqual(res["nota_sugerida"], 5.0)
        self.assertEqual(res["requisitos_sin_verificar"], ["r1"])
        self.assertFalse(res["completo"])
        self.assertIsNone(res["aprueba"])

    def test_criterio_manual_pendiente_muestra_total_parcial(self):  # AC-J12
        res = score(self.r, {"a": 4.0}, {"r1": True})
        self.assertEqual(res["nota_sugerida"], 2.4)
        self.assertEqual(res["maximo_posible"], 4.4)  # 2.4 + 40% * 5
        self.assertFalse(res["completo"])
        pend = [c for c in res["criterios"] if c["estado"] == "pendiente"]
        self.assertEqual([c["id"] for c in pend], ["b"])
        self.assertIsNone(pend[0]["nota"])

    def test_maximo_posible_respeta_tope(self):
        res = score(self.r, {"a": 4.0}, {"r1": False})
        self.assertEqual(res["maximo_posible"], 2.9)

    def test_valida_rangos_y_nombres(self):
        with self.assertRaisesRegex(RubricError, "fuera de la escala"):
            score(self.r, {"a": 5.1, "b": 3.0}, {"r1": True})
        with self.assertRaisesRegex(RubricError, "desconocidos"):
            score(self.r, {"zzz": 3.0})
        with self.assertRaisesRegex(RubricError, "desconocidos"):
            score(self.r, {"a": 3.0}, {"zzz": True})
        with self.assertRaisesRegex(RubricError, "numérico"):
            score(self.r, {"a": "alto"})

    def test_boveda_fichas_ejemplo_realista(self):
        r = load_rubric(BOVEDA)
        notas = {"modelado": 4.5, "estructuras": 4.0, "validacion": 4.5, "informe": 3.0}
        res = score(r, notas, TODOS)
        self.assertEqual(res["nota_sugerida"], 4.05)
        self.assertTrue(res["aprueba"])
        res = score(r, notas, dict(TODOS, compila_manual=False))
        self.assertEqual(res["nota_sugerida"], 2.9)


if __name__ == "__main__":
    unittest.main()
