"""Reportes de la revisión de proyectos distribuidos (spec 007): por equipo, general y CSV."""
import csv
import io
from pathlib import Path

from .evaluar import slug

MARCA = {True: "✔", False: "✘", None: "…"}


def nota_final(r):
    """0.0 si hay sanción docente por similitud; si no, la nota automática (sin sustentación)."""
    return r["sancion"]["nota"] if r.get("sancion") else r["nota"]


def recomendaciones(r):
    """Qué falta, en el orden de la rúbrica: señales no cumplidas, de mayor a menor nota en juego."""
    out = []
    for c in r["criterios"]:
        faltan = [s for s in c["senales"] if s["estado"] is False and s["tipo"] != "manual"]
        if faltan:
            out.append((c["max"], c["nombre"], [s["descripcion"] for s in faltan]))
    return [(n, f) for _, n, f in sorted(out, key=lambda x: -x[0])]


def _resumen_ejecucion(r):
    e = r.get("ejecucion")
    if e is None:
        return "no se ejecutó (modo estático)"
    if e.get("levanta") is None:
        return e.get("motivo") or "sin verificar"
    d = e.get("detalle", {})
    partes = [f"levanta: {'sí' if e['levanta'] else 'no'}"]
    for k in ("health", "metrics"):
        if e.get(k) is not None:
            partes.append(f"/{k}: {'sí' if e[k] else 'no'}")
    if not e["levanta"] and d.get("levanta"):
        partes.append(d["levanta"])
    return " · ".join(partes)


def markdown_equipo(r, rubrica):
    L = [f"# {r['equipo']}", ""]
    L.append("- **Integrantes que entregaron:** " + ", ".join(r["miembros"]) +
             (f" ({r['razon_equipo']})" if r["razon_equipo"] else ""))
    L.append(f"- **Nota sugerida:** {nota_final(r):.2f} de {rubrica.escala_max:g}"
             + (" ⚠ 0.0 por similitud (decisión docente)" if r.get("sancion") else ""))
    L.append(f"  - Automática: {r['parcial']:.2f} de criterios + {r['bonus_puntos']:.2f} de bonus = {r['nota']:.2f}")
    L.append(f"  - Máximo posible con lo que no se pudo verificar: {r['maximo_posible']:.2f}")
    L.append(f"  - Pendiente de la persona docente: sustentación individual, hasta {r['pendiente_docente']:.2f}")
    L.append(f"- **Ejecución:** {_resumen_ejecucion(r)}")
    if r["compose"]:
        L.append(f"- **Servicios del compose** (`…/{'/'.join(r['compose'].split('/')[-2:])}`): " + ", ".join(f"`{s}`" for s in r["servicios"]))
    if r.get("clonados"):
        L.append("- **Repositorio clonado de GitHub:** " + ", ".join(f"`{c}`" for c in r["clonados"]))
        for nombre, por in r.get("autores", {}).items():
            if por:
                L.append(f"  - Commits en `{nombre}`: " + ", ".join(f"{a} ({n})" for a, n in sorted(por.items(), key=lambda x: -x[1])))
    if r["informe"]:
        L.append(f"- **Informe:** `{r['informe'].rsplit('/', 1)[-1]}`")
    if r.get("sancion"):
        L += ["", f"> **Ajuste docente:** {r['sancion']['motivo']}. Coincide con: " + ", ".join(r["sancion"]["parejas"])]
    if r["sin_proyecto"]:
        L += ["", "> **Sin proyecto evaluable.** La entrega no trae código ni docker-compose." +
              (" Cita estos repositorios (descárgalos y evalúalos aparte): " + ", ".join(r["enlaces"]) if r["enlaces"] else "")]
    L += ["", "## Criterios", "", "| Criterio | Fase | Nota | Máx. | Estado |", "|---|---|---|---|---|"]
    for c in r["criterios"]:
        nota = "—" if c["nota"] is None else f"{c['nota']:.2f}"
        L.append(f"| {c['nombre']} | {c['fase']} | {nota} | {c['max']:.2f} | {c['estado']} |")
    L += ["", "## Detalle por señal", ""]
    for c in r["criterios"]:
        L.append(f"**{c['nombre']}**")
        for s in c["senales"]:
            L.append(f"- {MARCA[s['estado']]} {s['descripcion']}" + (f" — {s['detalle']}" if s["detalle"] else ""))
        L.append("")
    rec = recomendaciones(r)
    L += ["## Qué falta y recomendaciones", ""]
    if rec:
        for nombre, faltan in rec:
            L.append(f"- **{nombre}:** " + "; ".join(faltan))
    else:
        L.append("Todas las señales medibles se cumplen.")
    pend = [s for c in r["criterios"] for s in c["senales"] if s["estado"] is None and s["tipo"] != "manual"]
    if pend:
        L += ["", "### Sin verificar (no cuentan como acierto ni como fallo)", ""]
        L += [f"- {s['descripcion']}: {s['detalle']}" for s in pend]
    L += ["", f"## Bonus (hasta {rubrica.bonus_max:g})", ""]
    L += [f"- {MARCA[b['estado']]} {b['descripcion']}" + (f" — {b['detalle']}" if b["estado"] else "") for b in r["bonus"]]
    if r["avisos"]:
        L += ["", "## Avisos de extracción", ""] + [f"- {a}" for a in r["avisos"]]
    return "\n".join(L) + "\n"


def markdown_general(resultados, rubrica, sim=None):
    n_est = sum(len(r["miembros"]) for r in resultados)
    sanc = sum(1 for r in resultados if r.get("sancion"))
    L = ["# Reporte general por equipo", "",
         f"**{len(resultados)} equipos** ({n_est} entregas) · {sanc} con ajuste por similitud · "
         f"{sum(1 for r in resultados if r['sin_proyecto'])} sin proyecto evaluable", "",
         "> Nota sugerida = suma de criterios por evidencia (cada señal cumplida suma su parte del criterio) + bonus. "
         "No incluye la sustentación individual (hasta 0.15), que decide la persona docente. "
         "«Máx. posible» cuenta lo que no se pudo verificar. ⚠ = 0.0 por similitud.", "",
         "## Resumen", "",
         "| Equipo | Integrantes | Nota | Máx. posible | Ejecución | Observación |", "|---|---|---|---|---|---|"]
    for r in resultados:
        obs = []
        if r.get("sancion"):
            obs.append("ajuste por similitud")
        if r["sin_proyecto"]:
            obs.append("sin proyecto" + (" (enlace GitHub)" if r["enlaces"] else ""))
        if r["avisos"]:
            obs.append("avisos de extracción")
        nf = f"{nota_final(r):.2f}" + (" ⚠" if r.get("sancion") else "")
        L.append(f"| {r['equipo']} | {len(r['miembros'])} | {nf} | {r['maximo_posible']:.2f} | "
                 f"{_resumen_ejecucion(r)} | {', '.join(obs) or '—'} |")
    L += ["", "## Nota por criterio", ""]
    cab = [c.nombre for c in rubrica.criterios]
    L += ["| Equipo | " + " | ".join(f"{c.id} ({c.max:.2f})" for c in rubrica.criterios) + " |",
          "|---|" + "---|" * len(cab)]
    for r in resultados:
        L.append(f"| {r['equipo']} | " + " | ".join("—" if c["nota"] is None else f"{c['nota']:.2f}" for c in r["criterios"]) + " |")
    L += ["", "## Detalle por equipo", ""]
    for r in resultados:
        rec = recomendaciones(r)
        L += [f"### {r['equipo']}", "",
              f"- **Nota sugerida:** {nota_final(r):.2f} (automática {r['nota']:.2f}; máx. posible {r['maximo_posible']:.2f})"]
        if r.get("sancion"):
            L.append("- **Ajuste docente:** " + r["sancion"]["motivo"] + ". Coincide con: " + ", ".join(r["sancion"]["parejas"]))
        if rec:
            L.append("- **Qué falta:**")
            L += [f"  - {n}: " + "; ".join(f) for n, f in rec[:6]]
        L.append("")
    if sim and sim["pares"]:
        L += ["## Similitud entre equipos", "", "Detalle completo en `similitud.md`.", ""]
        L += [f"- {p['a']} ↔ {p['b']}: {p['puntaje']:.2f}" for p in sim["pares"]]
    return "\n".join(L) + "\n"


def csv_consolidado(resultados, rubrica):
    """Una fila por estudiante: hereda la nota de su equipo; `sustentacion` y `ajuste_docente` quedan para la persona docente."""
    buf = io.StringIO()
    ids = [c.id for c in rubrica.criterios]
    w = csv.writer(buf)
    w.writerow(["estudiante", "equipo", "nota_sugerida", "nota_automatica", "maximo_posible", "bonus"] + ids +
               ["sin_proyecto", "ejecucion", "sustentacion", "ajuste_docente"])
    for r in resultados:
        por = {c["id"]: c["nota"] for c in r["criterios"]}
        for m in r["miembros"]:
            w.writerow([m, r["equipo"], f"{nota_final(r):.2f}", f"{r['nota']:.2f}", f"{r['maximo_posible']:.2f}",
                        f"{r['bonus_puntos']:.2f}"] + ["" if por[i] is None else f"{por[i]:.2f}" for i in ids] +
                       [r["sin_proyecto"], _resumen_ejecucion(r), "",
                        (r["sancion"]["motivo"] if r.get("sancion") else "")])
    return buf.getvalue()


def exportar(resultados, rubrica, salida, sim=None):
    salida = Path(salida)
    (salida / "equipos").mkdir(parents=True, exist_ok=True)
    for r in resultados:
        (salida / "equipos" / f"{slug(r['equipo'])}.md").write_text(markdown_equipo(r, rubrica), encoding="utf-8")
    (salida / "reporte_general.md").write_text(markdown_general(resultados, rubrica, sim), encoding="utf-8")
    (salida / "consolidado.csv").write_text(csv_consolidado(resultados, rubrica), encoding="utf-8")
    return salida
