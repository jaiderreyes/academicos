import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from academicos.converters import MarkItDownConverter
from academicos.pipeline import Pipeline

available = all(importlib.util.find_spec(name) for name in ['markitdown', 'docx', 'reportlab'])


@unittest.skipUnless(available, 'Requiere markitdown, python-docx y reportlab')
class IntegrationTests(unittest.TestCase):
    def test_word_pdf_and_zip_with_real_converter(self):
        from docx import Document
        from reportlab.pdfgen.canvas import Canvas
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'entrada'
            source.mkdir()
            doc = Document()
            doc.add_heading('academicOS', 1)
            doc.add_paragraph('Documento de prueba para ingesta local.')
            doc.save(source / 'guia.docx')
            pdf = Canvas(str(source / 'articulo.pdf'))
            pdf.drawString(72, 720, 'academicOS PDF de prueba')
            pdf.save()
            with ZipFile(source / 'curso.zip', 'w') as archive:
                archive.write(source / 'guia.docx', 'unidad/guia.docx')
            report, rows = Pipeline(MarkItDownConverter()).run(source, root / 'salida')
            self.assertTrue(report.is_file())
            self.assertEqual(len(rows), 3)
            self.assertEqual([row['status'] for row in rows], ['convertido', 'convertido', 'reutilizado'])
            for row in rows:
                self.assertIn('academicOS', Path(row['output']).read_text())

            # Una nueva instancia debe reutilizar las tres salidas verificadas.
            _, repeated = Pipeline(MarkItDownConverter()).run(source, root / 'salida')
            self.assertTrue(all(row['status'] == 'omitido_sin_cambios' for row in repeated))
