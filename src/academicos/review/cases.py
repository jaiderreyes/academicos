"""Casos de prueba externos de la persona docente (spec 006, RF-J06 / RF-J13).

Viven en una carpeta aparte por parcial (`casos.yaml` + archivos de entrada), nunca en el
proyecto del estudiante. Dentro del contenedor quedan disponibles en `_casos/`.
"""
import re
import shutil
import tempfile
from pathlib import Path

import yaml


class CaseError(ValueError):
    """Caso mal definido."""


def load_cases(folder, requisitos_validos=()):
    folder = Path(folder)
    archivo = folder / "casos.yaml"
    if not archivo.is_file():
        raise CaseError(f"falta {archivo}")
    try:
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise CaseError(f"YAML inválido en {archivo.name}: {exc}") from exc
    crudos = datos.get("casos")
    if not isinstance(crudos, list) or not crudos:
        raise CaseError("'casos' debe ser una lista no vacía")
    casos, vistos = [], set()
    for c in crudos:
        if not isinstance(c, dict) or not c.get("id"):
            raise CaseError("cada caso necesita 'id'")
        cid = str(c["id"])
        if cid in vistos:
            raise CaseError(f"caso repetido: {cid}")
        vistos.add(cid)
        req = c.get("requisito")
        if req is not None and requisitos_validos and req not in requisitos_validos:
            raise CaseError(f"{cid}: requisito desconocido '{req}'")
        esperado = c.get("esperado") or {}
        if not isinstance(esperado, dict):
            raise CaseError(f"{cid}: 'esperado' debe ser un mapa")
        for k in ("salida_regex", "salida_no_regex"):
            for r in esperado.get(k) or []:
                try:
                    re.compile(r)
                except re.error as exc:
                    raise CaseError(f"{cid}: expresión inválida {r!r}: {exc}") from exc
        args = [str(a) for a in (c.get("args") or [])]
        casos.append({"id": cid, "descripcion": str(c.get("descripcion", cid)),
                      "args": args, "stdin": c.get("stdin"), "requisito": req,
                      "esperado": esperado, "timeout": int(c.get("timeout", 30))})
    return casos


def evaluar_salida(esperado, step):
    """Comparar un paso ejecutado con lo esperado. Devuelve lista de fallas (vacía = cumple)."""
    fallas = []
    # Sin `codigo_salida` no se exige ninguno: el enunciado puede no fijarlo.
    codigo = esperado.get("codigo_salida")
    if codigo is not None and step.exit_code != codigo:
        fallas.append(f"código de salida {step.exit_code}, esperado {codigo}")
    salida = step.stdout
    for t in esperado.get("salida_contiene") or []:
        if t not in salida:
            fallas.append(f"no aparece {t!r}")
    for t in esperado.get("salida_no_contiene") or []:
        if t in salida:
            fallas.append(f"aparece {t!r} y no debía")
    for r in esperado.get("salida_regex") or []:
        if not re.search(r, salida, re.M):
            fallas.append(f"no coincide la expresión {r!r}")
    for r in esperado.get("salida_no_regex") or []:
        if re.search(r, salida, re.M):
            fallas.append(f"coincide la expresión prohibida {r!r}")
    orden = esperado.get("salida_orden") or []
    if orden:
        pos = 0
        for t in orden:
            i = salida.find(t, pos)
            if i == -1:
                fallas.append(f"{t!r} no aparece en el orden esperado {orden}")
                break
            pos = i + len(t)
    return fallas


def run_cases(runner, info, work, casos_dir, casos, main_class=None, compile_timeout=120):
    """Compilar una vez y ejecutar cada caso. Devuelve {'compilacion': StepResult, 'casos': [...]}."""
    out = Path(tempfile.mkdtemp(prefix="academicos-out-"))
    out.chmod(0o777)
    try:
        comp = runner.compile(info, work, out, compile_timeout)
        resultados = []
        clase = main_class or (info.main_classes[0] if info.main_classes else None)
        for c in casos:
            base = {"id": c["id"], "descripcion": c["descripcion"], "requisito": c["requisito"]}
            if comp.status != "ok":
                resultados.append({**base, "estado": "no_verificable", "paso": None,
                                   "fallas": ["no se pudo ejecutar: la compilación no fue exitosa"]})
                continue
            if clase is None:
                resultados.append({**base, "estado": "no_verificable",
                                   "fallas": ["no se detectó clase con main()"], "paso": None})
                continue
            stdin = c["stdin"].encode("utf-8") if isinstance(c["stdin"], str) else None
            paso = runner.execute(clase, work, out, c["args"], stdin, c["timeout"],
                                  casos_dir=casos_dir)
            if paso.status in ("timeout", "no_verificable"):
                resultados.append({**base, "estado": paso.status, "fallas": [paso.note],
                                   "paso": paso.to_dict()})
                continue
            fallas = evaluar_salida(c["esperado"], paso)
            resultados.append({**base, "estado": "ok" if not fallas else "fail",
                               "fallas": fallas, "paso": paso.to_dict()})
        return {"compilacion": comp, "casos": resultados}
    finally:
        shutil.rmtree(out, ignore_errors=True)


def requisitos_desde_casos(resultados):
    """{requisito: True|False|None}: None si algún caso asociado no fue verificable."""
    req = {}
    for r in resultados:
        if r["requisito"] is None:
            continue
        actual = req.get(r["requisito"], True)
        if r["estado"] == "ok":
            nuevo = actual
        elif r["estado"] == "fail":
            nuevo = False
        else:
            nuevo = actual if actual is False else None
        req[r["requisito"]] = nuevo
    return req
