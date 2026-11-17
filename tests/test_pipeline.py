from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile
from io import BytesIO

from academicos.pipeline import Limits, Pipeline


class FakeConverter:
    def convert(self, path):
        content = path.read_text()
        if content == 'FAIL':
            raise ValueError('Documento defectuoso')
        return content


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input'
        self.source.mkdir()
        self.output = self.root / 'output'

    def run_pipeline(self, limits=None):
        return Pipeline(FakeConverter(), limits).run(self.source, self.output)[1]

    def test_recursive_and_distinct_extensions(self):
        folder = self.source / 'curso'
        folder.mkdir()
        (folder / 'guia.docx').write_text('# Word')
        (folder / 'guia.pdf').write_text('# PDF')
        rows = self.run_pipeline()
        self.assertEqual([r['status'] for r in rows], ['convertido', 'convertido'])
        self.assertEqual((self.output / 'documentos/curso/guia.pdf.md').read_text(), '# PDF\n')
        self.assertTrue((folder / 'guia.docx').exists())

    def test_zip_and_nested_zip(self):
        nested = BytesIO()
        with ZipFile(nested, 'w') as z:
            z.writestr('tesis.pdf', '# Tesis')
        with ZipFile(self.source / 'material.zip', 'w') as z:
            z.writestr('guia.docx', '# Guía')
            z.writestr('anexo.zip', nested.getvalue())
        rows = self.run_pipeline()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r['status'] == 'convertido' for r in rows))
        self.assertTrue((self.output / 'documentos/material.zip/__zip__/anexo.zip/__zip__/tesis.pdf.md').exists())

    def test_reject_traversal_before_conversion(self):
        with ZipFile(self.source / 'bad.zip', 'w') as z:
            z.writestr('ok.pdf', 'ok')
            z.writestr('../escape.pdf', 'escape')
        rows = self.run_pipeline()
        self.assertEqual(rows[0]['status'], 'error_zip')
        self.assertEqual(len(rows), 1)
        self.assertFalse((self.root / 'escape.pdf').exists())

    def test_size_and_count_limits(self):
        with ZipFile(self.source / 'big.zip', 'w') as z:
            z.writestr('a.pdf', '1234567890')
            z.writestr('b.pdf', '1234567890')
        for limits in [Limits(max_bytes=5), Limits(max_files=1)]:
            self.assertEqual(self.run_pipeline(limits)[0]['status'], 'error_zip')

    def test_depth_limit(self):
        with ZipFile(self.source / 'a.zip', 'w') as z:
            payload = BytesIO()
            with ZipFile(payload, 'w') as child:
                child.writestr('a.pdf', 'ok')
            z.writestr('b.zip', payload.getvalue())
        self.assertEqual(self.run_pipeline(Limits(max_depth=1))[0]['status'], 'error_zip')

    def test_global_budget_across_archives(self):
        for name in ['a.zip', 'b.zip']:
            with ZipFile(self.source / name, 'w') as z:
                z.writestr('a.pdf', '123456')
        rows = self.run_pipeline(Limits(max_bytes=10))
        self.assertEqual([r['status'] for r in rows], ['convertido', 'error_zip'])

    def test_existing_output_and_errors(self):
        (self.source / 'a.pdf').write_text('ok')
        (self.source / 'b.pdf').write_text('FAIL')
        (self.source / 'c.pdf').write_text('')
        self.run_pipeline()
        (self.source / 'a.pdf').write_text('changed')
        rows = self.run_pipeline()
        self.assertEqual([r['status'] for r in rows], ['actualizado', 'error_conversion', 'sin_texto'])
        self.assertEqual((self.output / 'documentos/a.pdf.md').read_text(), 'changed\n')

    def test_output_excluded_and_symlinks_skipped(self):
        self.output = self.source / 'output'
        self.output.mkdir()
        (self.output / 'generated.pdf').write_text('ignore')
        (self.root / 'external.pdf').write_text('private')
        (self.source / 'link.pdf').symlink_to(self.root / 'external.pdf')
        self.assertEqual(self.run_pipeline(), [])

    def test_invalid_output(self):
        with self.assertRaises(ValueError):
            Pipeline(FakeConverter()).run(self.source, self.source)
        with self.assertRaises(ValueError):
            Pipeline(FakeConverter()).run(self.source, self.root)


if __name__ == '__main__':
    unittest.main()
