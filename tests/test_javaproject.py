from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from academicos.review.javaproject import (ProjectError, detect_project, fingerprint,
                                           find_candidates, prepare_copy, safe_extract)

MAIN = "public class Main {\n  public static void main(String[] a) {}\n}\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class JavaProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_netbeans_default_package_y_pruebas(self):
        p = self.root / "JT"
        write(p / "nbproject" / "project.xml", "<project/>")
        write(p / "build.xml", "<project/>")
        write(p / "src" / "Main.java", MAIN)
        write(p / "src" / "Lista.java", "public class Lista {}\n")
        write(p / "test" / "CasosPrueba.java", "public class CasosPrueba {}\n")
        write(p / "build" / "classes" / "Viejo.java", "class Viejo {}\n")  # se ignora
        info = detect_project(p)
        self.assertEqual(info.kind, "netbeans")
        self.assertEqual(info.main_classes, ["Main"])
        self.assertIn("src", info.source_roots)
        self.assertEqual(info.test_files, ["test/CasosPrueba.java"])
        self.assertFalse(any("build/" in f.path for f in info.files))

    def test_paquetes_y_raiz_de_fuentes_y_clase_principal_completa(self):
        p = self.root / "E"
        write(p / "src" / "app" / "Main.java",
              "package app;\n" + MAIN)
        write(p / "src" / "dominio" / "Ficha.java", "package dominio;\npublic class Ficha {}\n")
        info = detect_project(p)
        self.assertEqual(info.kind, "src")
        self.assertEqual(info.source_roots, ["src"])
        self.assertEqual(info.main_classes, ["app.Main"])
        self.assertEqual(info.warnings, [])

    def test_maven_y_junit(self):
        p = self.root / "M"
        write(p / "pom.xml", "<project/>")
        write(p / "src/main/java/x/App.java", "package x;\n" + MAIN.replace("Main", "App"))
        write(p / "src/test/java/x/AppTest.java",
              "package x;\nimport org.junit.Test;\npublic class AppTest {}\n")
        info = detect_project(p)
        self.assertEqual(info.kind, "maven")
        self.assertEqual(info.source_roots, ["src/main/java", "src/test/java"])
        self.assertEqual(info.test_files, ["src/test/java/x/AppTest.java"])

    def test_archivo_unico_concatenado_avisa(self):  # el caso de Diego
        f = self.root / "prcl_final.java"
        write(f, "package a;\npublic class A {}\npackage b;\npublic class B {\n"
                 "  public static void main(String[] x) {}\n}\n")
        write(self.root / "otro.java", "class Otro {}\n")
        info = detect_project(f)
        self.assertEqual(info.kind, "single")
        self.assertEqual(len(info.files), 1)  # no mira vecinos
        self.assertTrue(any("declaraciones 'package'" in w for w in info.warnings))
        self.assertTrue(any("tipos públicos" in w for w in info.warnings))
        self.assertEqual(info.main_classes, [])  # no se inventa una clase principal
        self.assertTrue(any("varios paquetes" in w for w in info.warnings))

    def test_carpeta_pruebas_en_espanol_cuenta_como_pruebas(self):
        p = self.root / "E"
        write(p / "src" / "app" / "Main.java", "package app;\n" + MAIN)
        write(p / "src" / "pruebas" / "CasosPruebas.java",
              "package pruebas;\n" + MAIN.replace("Main", "CasosPruebas"))
        info = detect_project(p)
        self.assertEqual(info.test_files, ["src/pruebas/CasosPruebas.java"])
        self.assertEqual(sorted(info.main_classes), ["app.Main", "pruebas.CasosPruebas"])

    def test_paquete_que_no_coincide_con_carpeta_avisa(self):
        p = self.root / "X"
        write(p / "src" / "otra" / "Main.java", "package app;\n" + MAIN)
        info = detect_project(p)
        self.assertTrue(any("no coincide con la carpeta" in w for w in info.warnings))

    def test_zip_con_carpeta_contenedora(self):
        z = self.root / "p.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("JT/build.xml", "<project/>")
            zf.writestr("JT/nbproject/project.xml", "<project/>")
            zf.writestr("JT/src/Main.java", MAIN)
            zf.writestr("__MACOSX/JT/._Main.java", "basura")
        info = detect_project(z, extract_to=self.root / "x")
        self.assertEqual(info.kind, "netbeans")
        self.assertEqual(info.main_classes, ["Main"])
        self.assertEqual(len(info.files), 1)

    def test_zip_slip_se_rechaza(self):
        z = self.root / "mal.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("../fuera.java", "class F {}")
        with self.assertRaisesRegex(ProjectError, "fuera del destino"):
            safe_extract(z, self.root / "d")
        self.assertFalse((self.root / "fuera.java").exists())

    def test_zip_invalido_y_sin_java_y_origen_inexistente(self):
        z = self.root / "roto.zip"
        z.write_bytes(b"no es zip")
        with self.assertRaisesRegex(ProjectError, "ZIP inválido"):
            detect_project(z, extract_to=self.root / "d")
        vacio = self.root / "vacio"
        write(vacio / "README.md", "hola")
        with self.assertRaisesRegex(ProjectError, "no hay archivos .java"):
            detect_project(vacio)
        with self.assertRaisesRegex(ProjectError, "no existe"):
            detect_project(self.root / "nada")

    def test_copia_excluye_compilados_y_no_toca_el_origen(self):  # AC-J04
        p = self.root / "P"
        write(p / "src" / "Main.java", MAIN)
        write(p / "build" / "classes" / "Main.class", "bin")
        write(p / "src" / "Viejo.class", "bin")
        write(p / "datos" / "f.txt", "1|X|1|P1|REVELAR")
        write(p / ".DS_Store", "x")
        antes = fingerprint(p)
        info = detect_project(p)
        dest = self.root / "copia"
        prepare_copy(info, dest)
        copiados = sorted(x.relative_to(dest).as_posix() for x in dest.rglob("*") if x.is_file())
        self.assertEqual(copiados, ["datos/f.txt", "src/Main.java"])
        self.assertEqual(fingerprint(p), antes)

    def test_copia_rechaza_destino_con_contenido_y_copia_archivo_unico(self):
        f = self.root / "A.java"
        write(f, MAIN)
        info = detect_project(f)
        d = self.root / "d"
        write(d / "algo.txt", "x")
        with self.assertRaisesRegex(ProjectError, "no está vacío"):
            prepare_copy(info, d)
        prepare_copy(info, self.root / "limpio")
        self.assertTrue((self.root / "limpio" / "A.java").is_file())

    def test_candidatos_prefieren_carpeta_sobre_zip(self):
        s = self.root / "estudiante"
        write(s / "Proyecto" / "src" / "Main.java", MAIN)
        write(s / ".DS_Store", "x")
        (s / "Proyecto.zip").write_bytes(b"PK")
        write(s / "notas.docx", "x")
        nombres = [c.name for c in find_candidates(s)]
        self.assertEqual(nombres, ["Proyecto", "Proyecto.zip"])


if __name__ == "__main__":
    unittest.main()


class ZipAnidadoTest(unittest.TestCase):
    def test_zip_dentro_de_zip_se_lee_sin_tocar_el_original(self):
        import io, tempfile, zipfile
        from pathlib import Path
        from academicos.review.javaproject import detect_project, fingerprint
        d = Path(tempfile.mkdtemp())
        interno = io.BytesIO()
        with zipfile.ZipFile(interno, "w") as z:
            z.writestr("proy/src/app/Main.java", "package app; public class Main { public static void main(String[] a){} }")
        externo = d / "entrega.zip"
        with zipfile.ZipFile(externo, "w") as z:
            z.writestr("informe.pdf", "x")
            z.writestr("proyecto.zip", interno.getvalue())
        antes = fingerprint(externo)
        info = detect_project(externo, extract_to=d / "work")
        self.assertEqual(info.main_classes, ["app.Main"])
        self.assertTrue(any("anidado" in w for w in info.warnings))
        self.assertEqual(fingerprint(externo), antes)
