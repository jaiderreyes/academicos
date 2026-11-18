import io, tempfile, unittest, zipfile
from pathlib import Path
from academicos.review.evidencias import escanear, lineas_md


class EvidenciasTest(unittest.TestCase):
    def test_detecta_readme_informe_datos_capturas_y_zip_anidado(self):
        d = Path(tempfile.mkdtemp())
        (d / "proy" / "datos").mkdir(parents=True)
        (d / "proy" / "capturas").mkdir()
        (d / "proy" / "README.md").write_text("x")
        (d / "proy" / "datos" / "ejemplo_valido.txt").write_text("x")
        (d / "proy" / "datos" / "inv_id_repetido.txt").write_text("x")
        for n in ("01_compilacion_manual.png", "06_mensaje_sol.png", "07_error_f05.png"):
            (d / "proy" / "capturas" / n).write_bytes(b"x")
        interno = io.BytesIO()
        with zipfile.ZipFile(interno, "w") as z:
            z.writestr("informe_boveda.pdf", "x")
        with zipfile.ZipFile(d / "entrega.zip", "w") as z:
            z.writestr("repo.zip", interno.getvalue())
        e = escanear(d)
        self.assertTrue(e["readme"])
        self.assertTrue(e["informe"])               # dentro de un zip anidado
        self.assertEqual((e["datos_validos"], e["datos_invalidos"]), (1, 1))
        self.assertTrue(e["capturas"]["compilacion_manual"] and e["capturas"]["error_f05"])
        self.assertFalse(e["capturas"]["cambios_pila"])
        self.assertIn("Sin captura identificable", "\n".join(lineas_md(e)))
