from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from academicos.pipeline import Pipeline
from academicos.validation import LocalSimilarityIndex, file_hash


TEXT = ' '.join('palabra' + str(i) for i in range(70))


class Reader:
    def convert(self, path):
        return path.read_text()


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input'
        self.source.mkdir()
        self.output = self.root / 'output'

    def run_pipeline(self, converter=None):
        return Pipeline(converter or Reader()).run(self.source, self.output)[1]

    def test_unchanged_integrity_and_academic_status(self):
        path = self.source / 'a.pdf'
        path.write_text(TEXT)
        before = file_hash(path)
        row = self.run_pipeline()[0]
        self.assertEqual(row['sha256_before'], before)
        self.assertEqual(row['sha256_after'], before)
        self.assertEqual(row['integrity'], 'verificada')
        self.assertEqual(row['academic_originality'], 'no_evaluada')
        self.assertEqual(row['external_sources'], 'no_consultadas')

    def test_converter_modification_blocks_output(self):
        class Mutator:
            def convert(self, path):
                path.write_text('alterado')
                return TEXT
        (self.source / 'a.pdf').write_text('original')
        row = self.run_pipeline(Mutator())[0]
        self.assertEqual(row['status'], 'error_integridad')
        self.assertEqual(row['integrity'], 'fallida')
        self.assertNotEqual(row['sha256_before'], row['sha256_after'])
        self.assertFalse((self.output / 'documentos/a.pdf.md').exists())

    def test_converter_failure_still_verifies_source(self):
        class Failing:
            def convert(self, path):
                raise ValueError('fallo')
        (self.source / 'a.pdf').write_text('original')
        row = self.run_pipeline(Failing())[0]
        self.assertEqual(row['status'], 'error_conversion')
        self.assertEqual(row['integrity'], 'verificada')

    def test_disappearing_source_never_claims_integrity(self):
        class Deleter:
            def convert(self, path):
                path.unlink()
                return TEXT
        (self.source / 'a.pdf').write_text(TEXT)
        row = self.run_pipeline(Deleter())[0]
        self.assertEqual(row['status'], 'error_integridad')
        self.assertEqual(row['integrity'], 'no_verificada')
        self.assertIsNone(row['sha256_after'])

    def test_duplicates_across_names_and_zip_preserve_results(self):
        (self.source / 'a.pdf').write_text(TEXT)
        (self.source / 'b.pdf').write_text(TEXT)
        with ZipFile(self.source / 'c.zip', 'w') as z:
            z.writestr('copy.pdf', TEXT)
        rows = self.run_pipeline()
        self.assertIsNone(rows[0]['duplicate_of'])
        self.assertEqual([r['duplicate_of'] for r in rows[1:]], ['a.pdf', 'a.pdf'])
        self.assertEqual([r['status'] for r in rows], ['convertido', 'reutilizado', 'reutilizado'])
        self.assertTrue(all(Path(r['output']).exists() for r in rows))

    def test_text_equivalent_but_different_bytes(self):
        (self.source / 'a.docx').write_text(TEXT)
        (self.source / 'b.pdf').write_text(TEXT.upper().replace(' ', ', '))
        rows = self.run_pipeline()
        self.assertNotEqual(rows[0]['sha256_before'], rows[1]['sha256_before'])
        comparison = rows[1]['local_comparison']
        self.assertEqual(comparison['status'], 'coincidencias_detectadas')
        self.assertEqual(comparison['matches'][0]['score'], 1.0)
        self.assertEqual(comparison['matches'][0]['source'], 'a.docx')
        self.assertTrue(comparison['matches'][0]['shared_fragments'])

    def test_partial_similarity_and_unrelated_or_short_text(self):
        index = LocalSimilarityIndex()
        self.assertEqual(index.compare_and_add('a', TEXT)['status'], 'sin_referencias_previas')
        changed = TEXT.replace('palabra69', 'otrofinal')
        self.assertEqual(index.compare_and_add('b', changed)['status'], 'coincidencias_detectadas')
        unrelated = ' '.join('distinto' + str(i) for i in range(70))
        self.assertEqual(index.compare_and_add('c', unrelated)['status'], 'sin_coincidencias_sobre_umbral')
        self.assertEqual(index.compare_and_add('d', 'muy corto')['status'], 'texto_insuficiente')

    def test_new_run_resets_state_and_existing_outputs_not_compared(self):
        (self.source / 'a.pdf').write_text(TEXT)
        pipeline = Pipeline(Reader())
        pipeline.run(self.source, self.output)
        _, rows = pipeline.run(self.source, self.output)
        self.assertEqual(rows[0]['status'], 'omitido_sin_cambios')
        self.assertIsNone(rows[0]['duplicate_of'])
        self.assertEqual(rows[0]['local_comparison']['status'], 'no_evaluado')
        self.assertEqual(rows[0]['integrity'], 'verificada')
