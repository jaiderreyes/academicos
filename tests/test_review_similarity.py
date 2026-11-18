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
