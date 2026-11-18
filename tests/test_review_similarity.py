import tempfile, unittest
from pathlib import Path
from types import SimpleNamespace as NS
from academicos.review.similarity import huella_de, comparar, markdown

BASE = """
public class A { // comentario
  private int total = 0;
  public void sumar(int valor) { for (int i = 0; i < valor; i++) { total = total + i * 2; if (total > 100) { total = 0; } } }
  public int leer() { return total; }
  public static void main(String[] args) { A a = new A(); a.sumar(7); System.out.println(a.leer()); }
}
"""
OTRO = """
import java.util.*;
class Pila { Deque<String> d = new ArrayDeque<>(); void push(String s){ d.push(s);} String pop(){ return d.pop(); }
  boolean vacia(){ return d.isEmpty(); } int tam(){ return d.size(); } String tope(){ return d.peek(); }
  void limpiar(){ while(!d.isEmpty()){ d.pop(); } } }
"""


def proyecto(texto):
    d = tempfile.mkdtemp()
    (Path(d) / "A.java").write_text(texto, encoding="utf-8")
    return huella_de(d, [NS(path="A.java")])


class SimilitudTest(unittest.TestCase):
    def test_casi_identicos_superan_umbral(self):
        r = comparar({"x": proyecto(BASE), "y": proyecto(BASE.replace("// comentario", "// otro"))})
        self.assertEqual(len(r["pares"]), 1)
        self.assertGreaterEqual(r["pares"][0]["puntaje"], 0.99)

    def test_renombrar_variables_se_detecta_por_la_normalizada(self):
        ren = BASE.replace("total", "acum").replace("valor", "n")
        r = comparar({"x": proyecto(BASE), "y": proyecto(ren)})
        self.assertEqual(len(r["pares"]), 1)
        self.assertLess(r["pares"][0]["literal"], r["pares"][0]["normalizada"])

    def test_distintos_no_aparecen(self):
        self.assertEqual(comparar({"x": proyecto(BASE), "y": proyecto(OTRO)})["pares"], [])

    def test_poco_codigo_es_insuficiente(self):
        r = comparar({"x": proyecto("class A {}"), "y": proyecto(BASE)})
        self.assertEqual(r["insuficientes"], ["x"])
        self.assertEqual(r["pares"], [])
        self.assertIn("indicio", markdown(r))

    def test_umbral_configurable(self):
        a, b = proyecto(BASE), proyecto(BASE + "\nclass Extra { int f(int q){ return q * 3 + 1; } void g(){ f(2); f(3); } }")
        self.assertEqual(comparar({"x": a, "y": b}, 0.99)["pares"], [])
        self.assertEqual(len(comparar({"x": a, "y": b}, 0.3)["pares"]), 1)

if __name__ == "__main__":
    unittest.main()


class BaseTest(unittest.TestCase):
    def _carpeta(self, nombre, texto):
        d = Path(tempfile.mkdtemp()) / nombre
        d.mkdir()
        (d / "A.java").write_text(texto, encoding="utf-8")
        return d

    def test_la_base_se_resta_y_los_archivos_sin_modificar_se_detectan(self):
        from academicos.review.similarity import cargar_base, archivos_sin_modificar
        base = cargar_base(self._carpeta("base", BASE))
        d = self._carpeta("est", BASE.replace("// comentario", "// mio  "))
        self.assertEqual(archivos_sin_modificar(d, [NS(path="A.java")], base), {"A.java"})
        # idéntico a la base: tras restarla no queda código propio
        h = huella_de(d, [NS(path="A.java")], base=base)
        self.assertEqual(h["literal"], set())

    def test_solo_el_codigo_anadido_cuenta_para_la_similitud(self):
        from academicos.review.similarity import cargar_base
        GRANDE = BASE + "".join(f"\nclass C{i} {{ int m{i}(int a){{ if (a > {i}) {{ return a * {i} + a; }} return a - {i}; }} }}" for i in range(25))
        base = cargar_base(self._carpeta("base", GRANDE))
        extra1 = "\nclass P { int f(int q){ for (int i=0;i<q;i++){ q = q + i * 3; } return q; } int g(int w){ return w - f(w); } }"
        extra2 = "\nclass Z { String h(String s){ if (s == null) { return \"\"; } return s.trim() + s.length(); } void k(){ h(null); h(\"a\"); } }"
        d1 = self._carpeta("e1", GRANDE + extra1)
        d2 = self._carpeta("e2", GRANDE + extra2)
        sin = comparar({"a": huella_de(d1, [NS(path="A.java")]), "b": huella_de(d2, [NS(path="A.java")])})
        con = comparar({"a": huella_de(d1, [NS(path="A.java")], base=base), "b": huella_de(d2, [NS(path="A.java")], base=base)})
        self.assertEqual(len(sin["pares"]), 1)       # sin base parecen copias por el código común
        self.assertEqual(con["pares"], [])           # restando la base ya no


class ArchivosIdenticosTest(unittest.TestCase):
    def test_lista_archivos_identicos_y_cuenta(self):
        r = comparar({"x": proyecto(BASE), "y": proyecto(BASE.replace("// comentario", "// otro"))})
        p = r["pares"][0]
        self.assertEqual(p["archivos_identicos"], [("A.java", "A.java")])
        self.assertIn("Archivos idénticos por pareja", markdown(r))


class SancionTest(unittest.TestCase):
    def test_aplica_cero_conserva_nota_y_respeta_excepciones(self):
        from academicos.review.similarity import aplicar_sancion
        res = [{"estudiante": n} for n in ("Ana", "Luis", "Eva")]
        sim = {"pares": [{"a": "Ana", "b": "Luis", "puntaje": 1.0}, {"a": "Ana", "b": "Eva", "puntaje": 0.85}]}
        out = aplicar_sancion(res, sim, 1.0)
        self.assertEqual(sorted(out), ["Ana", "Luis"])
        self.assertEqual(res[0]["sancion"]["nota"], 0.0)
        self.assertNotIn("sancion", res[2])
        res2 = [{"estudiante": n} for n in ("Ana", "Luis")]
        self.assertEqual(aplicar_sancion(res2, sim, 1.0, excepto=["luis"]), ["Ana"])
