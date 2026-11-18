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


from .evidencias import lineas_md as _lineas_evidencias  # noqa: E402


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
    if r.get("evidencias"):
        L += _lineas_evidencias(r["evidencias"])
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
    rs = sorted(resultados, key=lambda x: x["estudiante"])
    sanc = [r for r in rs if r.get("sancion")]
    L = ["# Reporte general por estudiante", "",
         f"**{len(rs)} entregas** · {len(sanc)} con ajuste docente por similitud · "
         f"{sum(1 for r in rs if not r.get('calificacion'))} sin código evaluable", "",
         "> Nota final = parcial automática (sin informe ni «excelente»), salvo ajuste docente (⚠ = 0.0 por similitud).", "",
         "## Resumen", "",
         "| Estudiante | Nota final | Modelado | Estructuras | Validación | Observación |",
         "|---|---|---|---|---|---|"]
    detalle = []
    for r in rs:
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
        nombre = _corto(r["estudiante"])
        obs = []
        if r.get("errores"):
            obs.append("sin código evaluable")
        if comp == "fail":
            obs.append("no compila")
        if r.get("sancion"):
            obs.append("ajuste por similitud")
        elif parejas.get(r["estudiante"]):
            obs.append("similitud a revisar")
        col = lambda i: (niv[i]["nivel"] if i in niv else "—")
        nota_txt = "—" if nf is None else f"{nf:.2f}" + (" ⚠" if r.get("sancion") else "")
        L.append(f"| {nombre} | {nota_txt} | {col('modelado')} | {col('estructuras')} | {col('validacion')} | {', '.join(obs) or '—'} |")
        d = [f"### {nombre}", ""]
        if r.get("errores"):
            d += [f"- Error: {'; '.join(r['errores'])}", ""]
        else:
            d += [f"- **Nota final:** {nota_txt} · parcial automática {k['nota_sugerida']:.2f} (máx. {k['maximo_posible']:.2f})"]
            d += ["- **Niveles:** " + ", ".join(f"{i} → {n['nivel']}" + ("" if n["nota"] is None else f" ({n['nota']:.2f})")
                                               for i, n in niv.items())]
            if r.get("sancion"):
                d += [f"- **Ajuste docente:** nota 0.0. {r['sancion']['motivo']}. Coincide con: " +
                      "; ".join(_corto(x) for x in r["sancion"]["parejas"])]
            elif parejas.get(r["estudiante"]):
                d += ["- **Similitud con:** " + "; ".join(f"{_corto(b)} ({v:.2f})" for b, v in parejas[r["estudiante"]])]
            if falta:
                d += ["- **Qué falta:**"] + [f"  - {x}" for x in falta]
            if recs:
                d += ["- **Recomendaciones:**"] + [f"  - {x}" for x in recs]
            d += [""]
        detalle += d
    L += ["", "## Detalle por estudiante", ""] + detalle
    (outdir / "reporte_general.csv").write_text(buf.getvalue(), encoding="utf-8")
    (outdir / "reporte_general.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return {"csv": str(outdir / "reporte_general.csv"), "md": str(outdir / "reporte_general.md")}


def _corto(nombre):
    n = re.sub(r"(_assignsubmission_file)$", "", nombre)
    n = re.sub(r"_?\d{4,}_?$", "", n)
    return re.sub(r"_\d?$", "", n).replace("_", " ").strip().title()


_CHIP = {"deficiente": "#fde2e0:#9b1c1c", "regular": "#fff1cc:#8a5a00", "bueno": "#dff3e4:#1b6b34",
         "excelente": "#d6e8ff:#164e91"}


def _esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def export_general_html(resultados, sim, outdir):
    """Reporte general legible: resumen arriba y una tarjeta desplegable por estudiante."""
    from html import escape  # noqa: F401
    outdir = Path(outdir)
    parejas = {}
    for p in (sim or {}).get("pares", []):
        parejas.setdefault(p["a"], []).append((p["b"], p["puntaje"]))
        parejas.setdefault(p["b"], []).append((p["a"], p["puntaje"]))
    rs = sorted(resultados, key=lambda x: x["estudiante"])
    ok = [r for r in rs if r.get("calificacion")]
    sanc = [r for r in rs if r.get("sancion")]
    sin = [r for r in rs if not r.get("calificacion")]
    prom = [x for x in (_nota_final(r) for r in ok) if x is not None]
    media = sum(prom) / len(prom) if prom else 0
    tarjetas = []
    for r in rs:
        nf = _nota_final(r)
        k = r.get("calificacion")
        niv = r.get("niveles", [])
        chips = "".join(
            '<span class="chip" style="background:%s;color:%s" title="%s">%s: %s</span>' % (
                _CHIP.get(n["nivel"], "#eee:#333").split(":")[0], _CHIP.get(n["nivel"], "#eee:#333").split(":")[1],
                _esc(n["id"]), _esc(n["id"][:4].title()), _esc(n["nivel"])) for n in niv)
        if not k:
            nota_html, cls = '<span class="nota na">sin nota</span>', "bad"
        elif r.get("sancion"):
            nota_html, cls = '<span class="nota cero">0.0</span>', "bad"
        else:
            nota_html, cls = f'<span class="nota">{nf:.2f}</span>', ""
        etiqueta = ""
        if r.get("sancion"):
            etiqueta = '<span class="tag rojo">Ajuste docente por similitud</span>'
        elif parejas.get(r["estudiante"]):
            etiqueta = '<span class="tag ambar">Similitud a revisar</span>'
        if (r.get("compilacion") or {}).get("status") == "fail":
            etiqueta += '<span class="tag rojo">No compila</span>'
        falta, recs = por_mejorar(r) if k else ([], [])
        cuerpo = []
        if r.get("errores"):
            cuerpo.append("<h4>Error</h4><ul>" + "".join(f"<li>{_esc(e)}</li>" for e in r["errores"]) + "</ul>")
        if k:
            cuerpo.append(f"<p class='peq'>Parcial automática <b>{k['nota_sugerida']:.2f}</b> · máximo posible "
                          f"<b>{k['maximo_posible']:.2f}</b> (falta el informe y confirmar «excelente»).</p>")
            cuerpo.append("<table class='niv'><tr><th>Criterio</th><th>Nivel</th><th>Nota</th></tr>" + "".join(
                f"<tr><td>{_esc(n['id'])}</td><td>{_esc(n['nivel'])}</td><td>{'—' if n['nota'] is None else format(n['nota'], '.2f')}</td></tr>"
                for n in niv) + "</table>")
        if r.get("sancion"):
            cuerpo.append("<div class='aviso rojo'><b>Ajuste docente: nota final %.1f.</b> %s. Coincide con: %s.<br>"
                          "<small>Es una decisión de la persona docente; la similitud es un indicio, no una prueba.</small></div>" % (
                              r["sancion"]["nota"], _esc(r["sancion"]["motivo"]),
                              _esc("; ".join(_corto(x) for x in r["sancion"]["parejas"]))))
        elif parejas.get(r["estudiante"]):
            cuerpo.append("<div class='aviso ambar'>Similitud con: " + _esc("; ".join(
                f"{_corto(b)} ({v:.2f})" for b, v in parejas[r['estudiante']])) + "</div>")
        if falta:
            cuerpo.append("<h4>Qué falta</h4><ul>" + "".join(f"<li>{_esc(x)}</li>" for x in falta) + "</ul>")
        if recs:
            cuerpo.append("<h4>Recomendaciones</h4><ul>" + "".join(f"<li>{_esc(x)}</li>" for x in recs) + "</ul>")
        tarjetas.append(
            f'<details class="card {cls}" data-n="{_esc(_corto(r["estudiante"]).lower())}"><summary>'
            f'<span class="nom">{_esc(_corto(r["estudiante"]))}</span>{nota_html}'
            f'<span class="chips">{chips}</span><span class="tags">{etiqueta}</span></summary>'
            f'<div class="cuerpo">{"".join(cuerpo)}</div></details>')
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Reporte general por estudiante</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f5f6f8;color:#1f2430}}
header{{background:#1f2a44;color:#fff;padding:24px 32px}} h1{{margin:0 0 4px;font-size:22px}}
.sub{{opacity:.8;font-size:13px}} .res{{display:flex;gap:12px;flex-wrap:wrap;padding:16px 32px}}
.k{{background:#fff;border-radius:10px;padding:12px 18px;box-shadow:0 1px 2px #0001;min-width:130px}}
.k b{{display:block;font-size:24px}} .k span{{font-size:12px;color:#667}}
.barra{{padding:0 32px 8px}} input{{padding:9px 12px;width:280px;border:1px solid #ccd;border-radius:8px;font-size:14px}}
main{{padding:8px 32px 40px;max-width:1100px}}
.card{{background:#fff;border-radius:10px;margin:8px 0;box-shadow:0 1px 2px #0001;border-left:5px solid #2e9b57}}
.card.bad{{border-left-color:#c0392b}} summary{{display:flex;align-items:center;gap:14px;padding:12px 16px;cursor:pointer;flex-wrap:wrap}}
.nom{{font-weight:600;min-width:260px}} .nota{{font-size:20px;font-weight:700;min-width:64px}}
.nota.cero{{color:#c0392b}} .nota.na{{font-size:13px;color:#888;font-weight:400}}
.chip{{display:inline-block;padding:2px 9px;border-radius:12px;font-size:12px;margin-right:5px}}
.tag{{display:inline-block;padding:2px 9px;border-radius:12px;font-size:12px;margin-right:5px;color:#fff}}
.rojo{{background:#c0392b}} .ambar{{background:#c98a00}}
.cuerpo{{padding:4px 20px 16px;border-top:1px solid #eee}} h4{{margin:14px 0 4px;font-size:13px;color:#445}}
ul{{margin:4px 0 0;padding-left:20px;font-size:13.5px;line-height:1.5}} .peq{{font-size:13.5px}}
.niv{{border-collapse:collapse;font-size:13px}} .niv td,.niv th{{padding:3px 14px 3px 0;text-align:left}}
.aviso{{padding:10px 14px;border-radius:8px;font-size:13.5px;margin:10px 0}}
.aviso.rojo{{background:#fdecea;color:#7a1f16}} .aviso.ambar{{background:#fff4d6;color:#6b4a00}}
</style></head><body>
<header><h1>Reporte general por estudiante</h1>
<div class="sub">Nota final = parcial automática (sin informe ni «excelente»), salvo ajuste docente. Haz clic en un estudiante para ver el detalle.</div></header>
<div class="res"><div class="k"><b>{len(rs)}</b><span>entregas</span></div>
<div class="k"><b>{media:.2f}</b><span>promedio de nota final</span></div>
<div class="k"><b>{len(sanc)}</b><span>con ajuste por similitud</span></div>
<div class="k"><b>{len(sin)}</b><span>sin código evaluable</span></div></div>
<div class="barra"><input id="q" placeholder="Buscar estudiante…" oninput="f()"></div>
<main>{"".join(tarjetas)}</main>
<script>function f(){{var q=document.getElementById('q').value.toLowerCase();
document.querySelectorAll('.card').forEach(function(c){{c.style.display=c.dataset.n.indexOf(q)<0?'none':''}})}}</script>
</body></html>"""
    ruta = outdir / "reporte_general.html"
    ruta.write_text(html, encoding="utf-8")
    return str(ruta)
