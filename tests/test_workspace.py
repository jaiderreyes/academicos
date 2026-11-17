import contextlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from academicos.cli import main
from academicos.workspace import clean_workspace, prepare_material


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.material = self.root / 'material'
        self.material.mkdir()
        self.workspace = self.root / 'prueba'

    def test_prepare_copies_supported_files_and_preserves_tree(self):
        nested = self.material / 'curso'
        nested.mkdir()
        (nested / 'guia.PDF').write_text('pdf')
        (nested / 'notas.txt').write_text('ignorar')
        result = prepare_material(self.material, self.workspace)
        self.assertEqual(result['copied'], ['curso/guia.PDF'])
        self.assertTrue((self.workspace / 'entrada/curso/guia.PDF').is_file())
        self.assertFalse((self.workspace / 'entrada/curso/notas.txt').exists())

    def test_prepare_clean_replaces_previous_test_and_preserves_originals(self):
        original = self.material / 'nuevo.docx'
        original.write_text('nuevo')
        prepare_material(self.material, self.workspace)
        (self.workspace / 'entrada/anterior.pdf').write_text('anterior')
        (self.workspace / 'salida/reporte.json').write_text('{}')
        prepare_material(self.material, self.workspace, clean=True)
        self.assertFalse((self.workspace / 'entrada/anterior.pdf').exists())
        self.assertFalse((self.workspace / 'salida/reporte.json').exists())
        self.assertEqual(original.read_text(), 'nuevo')

    def test_clean_requires_marker_and_input_flag(self):
        (self.material / 'a.pdf').write_text('a')
        prepare_material(self.material, self.workspace)
        (self.workspace / 'salida/result.md').write_text('x')
        clean_workspace(self.workspace)
        self.assertTrue((self.workspace / 'entrada/a.pdf').exists())
        self.assertFalse((self.workspace / 'salida/result.md').exists())
        clean_workspace(self.workspace, include_input=True)
        self.assertEqual(list((self.workspace / 'entrada').iterdir()), [])
        with self.assertRaises(ValueError):
            clean_workspace(self.root / 'otra')

    def test_rejects_empty_and_overlapping_material(self):
        with self.assertRaises(ValueError):
            prepare_material(self.material, self.material / 'prueba')
        empty = self.root / 'empty'
        empty.mkdir()
        with self.assertRaises(ValueError):
            prepare_material(empty, self.workspace)

    def test_prepare_refuses_unmanaged_nonempty_workspace(self):
        (self.material / 'a.pdf').write_text('a')
        (self.workspace / 'entrada').mkdir(parents=True)
        (self.workspace / 'entrada/privado.pdf').write_text('no borrar')
        with self.assertRaises(ValueError):
            prepare_material(self.material, self.workspace, clean=True)
        self.assertTrue((self.workspace / 'entrada/privado.pdf').exists())

    def test_cli_prepare_and_clean(self):
        (self.material / 'a.zip').write_bytes(b'zip')
        with patch('sys.argv', ['academicos', 'prepare', str(self.material), '--workspace', str(self.workspace), '--clean']):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
        with patch('sys.argv', ['academicos', 'clean', '--workspace', str(self.workspace), '--include-input']):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)


if __name__ == '__main__':
    unittest.main()
