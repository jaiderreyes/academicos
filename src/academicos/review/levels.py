"""Niveles acumulativos de la rúbrica (spec 006, RF-J07).

Cada criterio se califica por niveles (deficiente, regular, bueno, excelente). Para subir
de nivel deben cumplirse los requisitos de ese nivel *y* los de todos los anteriores.
Reglas de honestidad:
- un requisito incumplido (False) bloquea el ascenso;
- un requisito sin verificar (None) deja el criterio pendiente: no se concluye;
- un nivel marcado `manual` solo lo confirma la persona docente;
- la nota automática de un nivel es su límite inferior (criterio conservador) o, si la rúbrica
  lo indica (`ejecucion.nota_en_nivel: medio`), el centro de su rango.
"""


def evaluar_criterio(criterio, hechos, punto="minimo"):
    """Devuelve el estado del criterio según los `hechos` {id: True|False|None}."""
    niveles = criterio.niveles
    alcanzado, bloqueo, sin_verificar, confirmar = 0, [], [], None
    for i in range(1, len(niveles)):
        n = niveles[i]
        if n.manual:
            confirmar = n.nombre
            break
        valores = {r: hechos.get(r) for r in n.requiere}
        falsos = [r for r, v in valores.items() if v is False]
        nulos = [r for r, v in valores.items() if v is None]
        if falsos:
            bloqueo = falsos
            break
        if nulos:
            sin_verificar = nulos
            break
        alcanzado = i
    base = niveles[alcanzado]
    siguiente = niveles[alcanzado + 1] if alcanzado + 1 < len(niveles) else None
    res = {"id": criterio.id, "nivel": base.nombre, "bloqueado_por": bloqueo,
           "sin_verificar": sin_verificar, "requiere_confirmacion": confirmar,
           "siguiente_nivel": siguiente.nombre if siguiente else None,
           # Lo que no pudo comprobarse del siguiente nivel aunque otro requisito ya lo bloquee
           "no_verificados_siguiente": [r for r in (siguiente.requiere if siguiente and not siguiente.manual else ())
                                        if hechos.get(r) is None]}
    if sin_verificar:
        res.update(estado="pendiente", nota=None, nota_minima_confirmada=base.min)
        return res
    if alcanzado == 0:
        # Nivel base: la nota refleja el avance hacia el siguiente nivel.
        req = [r for r in (siguiente.requiere if siguiente else ())]
        cumplidos = sum(1 for r in req if hechos.get(r) is True)
        progreso = cumplidos / len(req) if req else 0.0
        res["progreso"] = round(progreso, 3)
        nota = base.min + (base.max - base.min) * progreso
    else:
        # "minimo": límite inferior del nivel (conservador); "medio": centro del rango (decisión docente).
        nota = (base.min + base.max) / 2 if punto == "medio" else base.min
        # Último nivel alcanzado sin pendientes: cumple todo lo pedido → máximo del rango.
        if punto == "medio" and siguiente is None:
            nota = base.max
    res.update(estado="puntuado", nota=round(nota, 4))
    return res


def ids_desconocidos(rubrica, ids_casos=()):
    """Ids usados en `requiere` que no existen: un error de escritura dejaría el criterio pendiente."""
    conocidos = {"compila"} | {v["id"] for v in rubrica.verificaciones} \
        | {r.id for r in rubrica.requisitos} | set(ids_casos)
    usados = {}
    for c in rubrica.criterios:
        for n in c.niveles:
            for r in n.requiere:
                if r not in conocidos:
                    usados.setdefault(r, []).append(f"{c.id}.{n.nombre}")
    return usados
