"""Reportes por estudiante y consolidado de curso (spec 006, J-08)."""
import csv
import io
import json
import re
from pathlib import Path


def _slug(texto):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", texto).strip("_") or "estudiante"


def _estado(v):
    return {True: "cumple", False: "NO cumple", None: "sin verificar"}[v]


_PISTAS = {
    "compila": "Compila con el comando del enunciado (`javac -encoding UTF-8 -d out $(find src -name \"*.java\")`) "
               "antes de entregar: un solo .java con varias clases públicas o texto que no es código no compila.",
    "tiene_pruebas": "Agrega pruebas en una carpeta `test/` (o `tests/`) que cubran los casos mínimos del enunciado.",
}


def por_mejorar(r):
    """Qué falta y qué recomendar, derivado solo de los hechos del resultado (sin inventar)."""
    desc = dict(r.get("descripciones", {}))
    desc.update({v["id"]: v.get("descripcion", v["id"]) for v in r.get("verificaciones", [])})
    desc.update({c["id"]: c.get("descripcion", c["id"]) for c in r.get("casos", [])})
    desc["compila"] = "El proyecto compila"
    falta, recs, vistos = [], [], set()

    def anotar(cid, motivo):
        if cid in vistos:
            return
        vistos.add(cid)
        falta.append(f"{desc.get(cid, cid)} ({motivo})")
        if cid in _PISTAS:
            recs.append(_PISTAS[cid])

    comp = r.get("compilacion", {})
    for n in r.get("niveles", []):
        sig = n.get("siguiente_nivel")
        for cid in n.get("bloqueado_por", []):
            anotar(cid, f"no cumplido; frena {n['id']} → {sig}")
        for cid in sorted(set(n.get("sin_verificar", [])) | set(n.get("no_verificados_siguiente", []))):
            anotar(cid, f"sin verificar; necesario para {n['id']} → {sig}")
    for c in r.get("casos", []):
        if c["estado"] == "revisar":
            falta.append(f"Revisión docente del caso heurístico «{c['id']}» (la salida no coincidió con el texto esperado; puede ser solo otra redacción)")
        if c["estado"] == "fail":
            recs.append(f"Revisa el caso «{c['id']}»: " + "; ".join(c.get("fallas", [])[:2]))
    if comp.get("status") == "fail":
        recs.insert(0, _PISTAS["compila"])
    for x in r.get("confirmaciones_docentes", []):
        falta.append(f"Confirmación docente de {x['criterio']} → {x['nivel']} (solo la persona docente)")
    for a in r.get("avisos", [])[3:]:
        if "pendientes" in a:
            falta.append("Criterios manuales sin puntuar (p. ej. informe y defensa)")
        elif "difiere" in a:
            recs.append("Usa exactamente el nombre de clase principal del enunciado (respeta mayúsculas): " + a)
    return falta, list(dict.fromkeys(recs))


def _seccion_mejora(r):
    falta, recs = por_mejorar(r)
    L = ["", "## Qué falta", ""] + ([f"- {x}" for x in falta] or ["- Nada pendiente de verificar."])
    L += ["", "## Recomendaciones", ""] + ([f"- {x}" for x in recs] or ["- Sin recomendaciones automáticas."])
    return L


def markdown(r):
    L = [f"# Revisión · {r['estudiante']}", "",
         f"Rúbrica: {r['rubrica']} · Proyecto: {r.get('proyecto', '—')} · {r['fecha']}", ""]
    if r["errores"]:
        L += ["## Errores", *[f"- {e}" for e in r["errores"]], ""]
        return "\n".join(L) + "\n"
    k = r["calificacion"]
    estado = "completa" if k["completo"] else "PARCIAL (hay criterios o requisitos sin resolver)"
    titulo = "Nota sugerida" if k["completo"] else "Nota PARCIAL (no es una calificación)"
    L += [f"## {titulo}", "",
          f"**{k['nota_sugerida']:.2f}** ({estado}) · máximo posible {k['maximo_posible']:.2f}"
          + (f" · tope aplicado (nota sin tope {k['nota_sin_tope']:.2f})" if k["tope_aplicado"] else ""), "",
          "| Criterio | Tipo | Peso | Nota | Estado |", "|---|---|---|---|---|"]
    for c in k["criterios"]:
        nota = "—" if c["nota"] is None else f"{c['nota']:.2f}"
        L.append(f"| {c['nombre']} | {c['tipo']} | {c['peso']:g} % | {nota} | {c['estado']} |")
    if r.get("niveles"):
        L += ["", "## Niveles por criterio", "",
              "| Criterio | Nivel confirmado | Bloqueado por | Sin verificar | Nota automática |", "|---|---|---|---|---|"]
        for n in r["niveles"]:
            nota = "—" if n["nota"] is None else f"{n['nota']:.2f}"
            sin = sorted(set(n["sin_verificar"]) | set(n.get("no_verificados_siguiente", [])))
            L.append(f"| {n['id']} | {n['nivel']} | {', '.join(n['bloqueado_por']) or '—'} | {', '.join(sin) or '—'} | {nota} |")
        L += ["", ("La nota automática es el centro del rango del nivel confirmado (criterio de la rúbrica)."
                if r.get("nota_en_nivel") == "medio" else "La nota automática es el límite inferior del nivel confirmado.")]
    if r.get("confirmaciones_docentes"):
        L += ["", "**Pendiente de tu revisión** (solo la persona docente puede confirmarlo): " +
              "; ".join(f"{x['criterio']} → {x['nivel']}" for x in r["confirmaciones_docentes"]) +
              ". Si corresponde, regístralo en `ajustes` del archivo manual con su motivo."]
    if r.get("manual", {}).get("ajustes"):
        L += ["", "### Ajustes docentes", ""]
        for cid, a in r["manual"]["ajustes"].items():
            sug = a.get("sugerencia_automatica")
            L.append(f"- {cid}: {a['nota']:.2f} (sugerencia automática: {'—' if sug is None else f'{sug:.2f}'}) · {a['motivo']}")
    L += ["", "## Condición mínima", ""]
    for rid, v in r["requisitos"].items():
        L.append(f"- {rid}: {_estado(v)}")
    e = r["estructura"]
    L += ["", "## Estructura", "", f"- Tipo: {e['tipo']} · archivos Java: {e['archivos_java']}",
          f"- Clases con main(): {', '.join(e['clases_principales']) or 'ninguna detectada'}",
          f"- Archivos de prueba: {', '.join(e['archivos_prueba']) or 'ninguno'}"]
    for a in e["avisos"]:
        L.append(f"- Aviso: {a}")
    c = r["compilacion"]
    L += ["", "## Compilación", "", f"- Estado: **{c['status']}** · {c.get('note') or ''}".rstrip(" ·")]
    if c["status"] == "fail" and c["stderr"]:
        L += ["", "```", c["stderr"][:1500], "```"]
    L += ["", "## Verificaciones estáticas", ""]
    for v in r["verificaciones"]:
        L.append(f"- {v['descripcion']}: {_estado(v['cumple'])}")
        for h in v["hallazgos"][:5]:
            L.append(f"  - `{h['archivo']}:{h['linea']}` {h['texto']}")
    if r["casos"]:
        L += ["", "## Casos de prueba", ""]
        for cs in r["casos"]:
            L.append(f"- {cs['descripcion']}: {cs['estado']}" + (f" — {'; '.join(cs['fallas'])}" if cs["fallas"] else ""))
    if r.get("manual"):
        L += ["", "## Criterios manuales", "", f"Archivo: {r['manual']['archivo']}"]
        if r["manual"]["observaciones"]:
            L.append(f"Observaciones: {r['manual']['observaciones']}")
    if r.get("sancion"):
        sc = r["sancion"]
        L += ["", "## Ajuste docente por similitud", "",
              f"**Nota final: {sc['nota']:.1f}** (la nota automática de arriba se conserva como referencia).",
              f"{sc['motivo']}. Coincide con: " + "; ".join(sc["parejas"]) + ".",
              "Es una decisión de la persona docente, no una conclusión de la herramienta: la similitud es un indicio. "
              "Quitar `--sancion-similitud` al volver a correr revierte el ajuste."]
    L += _seccion_mejora(r)
    i = r["integridad"]
    L += ["", "## Integridad y alcance", "",
          f"- Original sin cambios: {'sí' if i['intacto'] else 'NO'} ({i['archivos']} archivos comparados por SHA-256)",
          *[f"- {a}" for a in r["avisos"]], ""]
    return "\n".join(L)


def export_student(r, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    base = _slug(r["estudiante"])
    (outdir / f"{base}.json").write_text(json.dumps({k: v for k, v in r.items() if not k.startswith("_")}, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / f"{base}.md").write_text(markdown(r), encoding="utf-8")
    return {"json": str(outdir / f"{base}.json"), "md": str(outdir / f"{base}.md")}


def export_course(resultados, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["estudiante", "proyecto", "nota_final", "nota", "maximo_posible", "completa", "tope_aplicado",
                "requisitos_incumplidos", "requisitos_sin_verificar", "compilacion", "original_intacto", "errores", "ajuste_docente"])
    for r in resultados:
        k = r.get("calificacion")
        sanc = r.get("sancion")
        w.writerow([r["estudiante"], r.get("proyecto", ""),
                    sanc["nota"] if sanc else ("" if not k else k["nota_sugerida"]),
                    "" if not k else k["nota_sugerida"], "" if not k else k["maximo_posible"],
                    "" if not k else k["completo"], "" if not k else k["tope_aplicado"],
                    "" if not k else ";".join(k["requisitos_incumplidos"]),
                    "" if not k else ";".join(k["requisitos_sin_verificar"]),
                    r.get("compilacion", {}).get("status", ""),
                    r.get("integridad", {}).get("intacto", ""), " | ".join(r["errores"]),
                    (r["sancion"]["motivo"] + " (con " + "; ".join(r["sancion"]["parejas"]) + ")") if r.get("sancion") else ""])
    ruta = outdir / "consolidado.csv"
    ruta.write_text(buf.getvalue(), encoding="utf-8")
    return str(ruta)


def _nota_final(r):
    if r.get("sancion"):
        return r["sancion"]["nota"]
    k = r.get("calificacion")
    return k["nota_sugerida"] if k else None


def export_general(resultados, sim, outdir):
    """Reporte general por estudiante: una tabla (CSV) y un documento (MD) con todos."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    parejas = {}
    for p in (sim or {}).get("pares", []):
        parejas.setdefault(p["a"], []).append((p["b"], p["puntaje"]))
        parejas.setdefault(p["b"], []).append((p["a"], p["puntaje"]))
    ids = []
    for r in resultados:
        for n in r.get("niveles", []):
            if n["id"] not in ids:
                ids.append(n["id"])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["estudiante", "proyecto", "nota_final", "nota_automatica", "maximo_posible", "completa",
                "compila"] + [f"{i}_nivel" for i in ids] + [f"{i}_nota" for i in ids] +
               ["similitud_con", "ajuste_docente", "que_falta", "recomendaciones", "errores"])
    L = ["# Reporte general por estudiante", "",
         "La nota final es la automática parcial (sin informe ni confirmación de «excelente»), salvo ajuste docente. "
         f"{len(resultados)} entrega(s).", "",
         "| Estudiante | Nota final | Parcial automática (máx.) | Compila | Similitud |", "|---|---|---|---|---|"]
    detalle = []
    for r in sorted(resultados, key=lambda x: x["estudiante"]):
        k = r.get("calificacion")
        nf = _nota_final(r)
        niv = {n["id"]: n for n in r.get("niveles", [])}
        falta, recs = por_mejorar(r) if k else ([], [])
        sim_txt = "; ".join(f"{b} ({v:.2f})" for b, v in parejas.get(r["estudiante"], []))
        comp = (r.get("compilacion") or {}).get("status", "")
        w.writerow([r["estudiante"], r.get("proyecto", ""), "" if nf is None else nf,
                    "" if not k else k["nota_sugerida"], "" if not k else k["maximo_posible"],
                    "" if not k else k["completo"], comp,
                    *[niv[i]["nivel"] if i in niv else "" for i in ids],
                    *["" if i not in niv or niv[i]["nota"] is None else niv[i]["nota"] for i in ids],
                    sim_txt, r["sancion"]["motivo"] if r.get("sancion") else "",
                    " | ".join(falta), " | ".join(recs), " | ".join(r.get("errores", []))])
        auto = "—" if not k else f"{k['nota_sugerida']:.2f} (máx. {k['maximo_posible']:.2f})"
        L.append(f"| {r['estudiante']} | {'—' if nf is None else f'{nf:.2f}'}{' ⚠' if r.get('sancion') else ''} | {auto} | {comp or '—'} | {sim_txt or '—'} |")
        d = [f"### {r['estudiante']}", ""]
        if r.get("errores"):
            d += ["Errores: " + "; ".join(r["errores"]), ""]
        else:
            d += ["- Niveles: " + ", ".join(f"{i} → {n['nivel']}" + ("" if n["nota"] is None else f" ({n['nota']:.2f})")
                                           for i, n in niv.items())]
            if r.get("sancion"):
                d += [f"- **Ajuste docente: nota final {r['sancion']['nota']:.1f}** — {r['sancion']['motivo']}; "
                      "coincide con " + "; ".join(r["sancion"]["parejas"])]
            if falta:
                d += ["- Qué falta: " + " · ".join(falta)]
            if recs:
                d += ["- Recomendaciones: " + " · ".join(recs)]
            d += [""]
        detalle += d
    L += ["", "⚠ = nota final con ajuste docente por similitud.", "", "## Detalle", ""] + detalle
    (outdir / "reporte_general.csv").write_text(buf.getvalue(), encoding="utf-8")
    (outdir / "reporte_general.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return {"csv": str(outdir / "reporte_general.csv"), "md": str(outdir / "reporte_general.md")}
