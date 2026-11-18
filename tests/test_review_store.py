import json, sqlite3, tempfile, unittest
from pathlib import Path
from academicos.review.store import ReviewStore, historial, NOMBRE

RES = {"estudiante": "Ana", "proyecto": "P", "fecha": "2026-11-18T10:00:00+00:00", "errores": [],
       "calificacion": {"nota_sugerida": 3.2, "maximo_posible": 4.2, "completo": False, "tope_aplicado": False},
       "compilacion": {"status": "ok"}, "integridad": {"intacto": True},
       "niveles": [{"id": "modelado", "nivel": "bueno", "nota": 4.0, "estado": "puntuado",
                    "bloqueado_por": [], "sin_verificar": [], "requiere_confirmacion": "excelente"}],
       "casos": [{"id": "ejemplo_valido", "estado": "ok"}, {"id": "err_id_repetido", "estado": "fail"}],
       "manual": {"archivo": "Ana.yaml", "observaciones": "x", "ajustes": {"modelado": {"nota": 3.8, "motivo": "m"}}},
       "_huella": {"literal": {"no serializable"}}}


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.rub = self.d / "r.yaml"
        self.rub.write_text("nombre: x", encoding="utf-8")

    def guardar(self):
        s = ReviewStore(self.d)
        rid = s.start_run(self.rub, "boveda", "curso", 0.8)
        s.add_student(rid, RES)
        s.add_similarity(rid, {"pares": [{"a": "Ana", "b": "Luis", "literal": .9, "normalizada": .95,
                                           "puntaje": .95, "fragmentos": ["a b c d e"]}]})
        s.close()
        return rid

    def test_guarda_nota_niveles_casos_y_similitud(self):
        self.guardar()
        db = sqlite3.connect(self.d / NOMBRE)
        self.assertEqual(db.execute("SELECT nota,maximo_posible FROM review_students").fetchone(), (3.2, 4.2))
        self.assertEqual(db.execute("SELECT nivel FROM review_levels").fetchone()[0], "bueno")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM review_cases").fetchone()[0], 2)
        self.assertEqual(db.execute("SELECT puntaje FROM review_similarity").fetchone()[0], 0.95)
        guardado = json.loads(db.execute("SELECT resultado FROM review_students").fetchone()[0])
        self.assertNotIn("_huella", guardado)

    def test_conserva_ejecuciones_anteriores(self):
        self.guardar(); self.guardar()
        h = historial(self.d, "Ana")
        self.assertEqual(len(h), 2)
        self.assertEqual(h[0]["niveles"], {"modelado": "bueno"})

    def test_rechaza_base_ajena(self):
        ajena = Path(tempfile.mkdtemp())
        sqlite3.connect(ajena / NOMBRE).executescript("CREATE TABLE t(x); PRAGMA user_version=7;")
        with self.assertRaises(ValueError):
            ReviewStore(ajena)

    def test_historial_sin_base(self):
        with self.assertRaises(ValueError):
            historial(Path(tempfile.mkdtemp()))

if __name__ == "__main__":
    unittest.main()


class MejoraTest(unittest.TestCase):
    def test_falta_y_recomendaciones_salen_de_los_hechos(self):
        from academicos.review.report import por_mejorar
        r = {"compilacion": {"status": "fail"}, "descripciones": {"orden_prioridad_fifo": "Respeta prioridad y FIFO"},
             "verificaciones": [{"id": "tiene_pruebas", "descripcion": "Incluye pruebas"}],
             "casos": [{"id": "c1", "descripcion": "d", "estado": "fail", "fallas": ["falta SOL"]}],
             "niveles": [{"id": "validacion", "siguiente_nivel": "regular", "bloqueado_por": ["compila", "tiene_pruebas"],
                          "sin_verificar": [], "no_verificados_siguiente": ["orden_prioridad_fifo"]}],
             "confirmaciones_docentes": [{"criterio": "modelado", "nivel": "excelente"}],
             "avisos": ["a", "b", "c", "sin archivo de criterios manuales: quedan pendientes"]}
        falta, recs = por_mejorar(r)
        self.assertTrue(any("Incluye pruebas" in f for f in falta))
        self.assertTrue(any("Respeta prioridad" in f for f in falta))
        self.assertTrue(any("Confirmación docente" in f for f in falta))
        self.assertTrue(recs[0].startswith("Compila con el comando"))
        self.assertTrue(any("«c1»" in x for x in recs))

    def test_sin_pendientes(self):
        from academicos.review.report import por_mejorar
        self.assertEqual(por_mejorar({}), ([], []))
