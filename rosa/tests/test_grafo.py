"""El grafo de la investigación en el backend (rosa/grafo.py): el port de
`construirArbol` del frontend más los nodos de dato, la profundidad hasta el
dato y la vecindad que lee el Killer."""

from rosa import grafo as G
from rosa.estado import plantilla as P

AHORA = 1_757_900_000_000


def _entidad(id_, etiqueta, alias=None):
    return {"id": id_, "etiqueta": etiqueta, "ontologia": "HGNC", "tipo": "gen", "alias": alias or []}


def _afirmacion(tipo, **k):
    base = {"texto": "GFAP sube", "cita": "[A, pág. 1]", "veredicto": "sostenida", "motivo": "", "entidadDistinta": False, "tipo": tipo, "clase": "literatura", "sintetico": False, "trayectoria": None, "fragmento": "GFAP sube"}
    base.update(k)
    return base


def _estado():
    """Una investigación con áreas, dos hipótesis del mismo cluster (rivales),
    una tercera suelta, hechos que comparten fuente, fuentes leídas y sin
    leer, una ejecución válida con plan y dataset, otra fallida y un
    resultado de laboratorio."""
    e = P.estado_inicial()
    area = P.nueva_area(id="area-1", titulo="astrocitos", familiaMecanismo="glía", estado="elegida")
    dataset = {"id": "gse1297", "nombre": "GSE1297 hipocampo", "descripcion": "", "tamanoMb": 1, "columnas": 3, "columnasSinDiccionario": 0, "valoresCentinela": 0, "nombresDuplicados": 0, "clasificacion": "publico", "estado": "aprobado", "origen": "catalogo", "procedencia": {**P.procedencia_dataset_vacia(), "origen": "GEO", "sintetico": False}}
    inv = {"id": "inv-g", "titulo": "Biomarcadores tempranos", "objetivo": "Orden de alteración de GFAP y NfL", "creadaEn": AHORA, "mision": {**P.mision_vacia(), "areas": [area]}, "datasets": [dataset]}
    plan = P.nuevo_plan_analisis("inv-g", "hip-1", "gse1297", AHORA, id="plan-1", prueba="t de Welch")
    run1 = P.nueva_ejecucion("inv-g", "hip-1", "plan-1", "hipotesis", "print(1)", 1, "abc", AHORA)
    run1.update(id="run-1", estado="completado", fin=AHORA + 10, auditoria={"veredicto": "valido", "comprobaciones": [], "motivo": "", "quien": "juez", "fecha": AHORA}, interpretacion={"estado": "efecto_detectado", "resumen": "GFAP mayor en el grupo con patología (p = 0,01)"})
    run2 = P.nueva_ejecucion("inv-g", "hip-1", "plan-1", "hipotesis", "print(2)", 2, "abc", AHORA)
    run2.update(id="run-2", estado="error_tecnico", error="ImportError")
    f1 = P.nueva_fuente(id="f-1", referencia="Cohorte clínica, 2023", titulo="Plasma GFAP precedes NfL", fragmento="GFAP rose two years before NfL in amyloid-positive participants")
    f2 = P.nueva_fuente(id="f-2", referencia="Revisión, 2022", titulo="Glial markers review")
    f3 = P.nueva_fuente(id="f-3", referencia="Ensayo, 2024", titulo="NfL trajectories", textoCompleto=True)
    h1 = P.nueva_hipotesis(
        "inv-g", 1, AHORA, id="hip-1", titulo="GFAP sube antes que NfL", cluster="Astrocitos", elo=1540, candidata=True,
        entidades=[_entidad("HGNC:4235", "GFAP", ["glial fibrillary acidic protein"]), _entidad("HGNC:7752", "NfL")],
        grafoCausal={"nodos": [{"id": "n1", "etiqueta": "GFAP", "rol": "causa", "idCanonico": "HGNC:4235"}, {"id": "n2", "etiqueta": "NfL", "rol": "efecto", "idCanonico": "HGNC:7752"}, {"id": "n3", "etiqueta": "sin canon", "rol": "otro"}], "aristas": [{"de": "n1", "a": "n2", "tipo": "inferencia_con_evidencia", "contexto": ""}, {"de": "n1", "a": "n3", "tipo": "supuesto", "contexto": ""}], "identificacion": "acotado", "supuestosCumplidos": [], "supuestosFaltantes": [], "resumen": "", "calculadoEn": AHORA},
        partidos=[{"iteracion": 1, "rivalId": "hip-2", "resultado": "gano", "resumenDebate": "", "ejeDecisivo": "correccion"}, {"iteracion": 1, "rivalId": "hip-fantasma", "resultado": "gano", "resumenDebate": "", "ejeDecisivo": "correccion"}],
        experimento={"protocolo": "ELISA", "ensayo": "GFAP plasmático", "costeEstimado": "", "laboratorio": "INTEC", "estado": "datos_recibidos", "ficheroDatos": None, "analisisPedido": "", "prerregistradoEn": AHORA, "resultado": {"veredicto": "confirma", "resultado": "GFAP 20 % mayor en el grupo tratado", "motivo": "", "limitaciones": "", "cifras": [], "exploratorio": "", "fecha": AHORA, "fichero": None, "clasificacion": "apoyo_reproducido"}},
        afirmaciones=[_afirmacion("literatura"), _afirmacion("dato", texto="GFAP mayor en el grupo con patología", clase="derivado", trayectoria={"id": "run-1", "celda": 0})],
    )
    h1["procedencia"]["fuentes"] = [f1, f2]
    h2 = P.nueva_hipotesis("inv-g", 2, AHORA, id="hip-2", titulo="NfL sube antes que GFAP", cluster="Astrocitos", partidos=[{"iteracion": 1, "rivalId": "hip-1", "resultado": "perdio", "resumenDebate": "", "ejeDecisivo": "correccion"}])
    h2["procedencia"]["fuentes"] = [f3]
    h3 = P.nueva_hipotesis("inv-g", 2, AHORA, id="hip-3", titulo="Tau independiente", experimento={"protocolo": "", "ensayo": "", "costeEstimado": "", "laboratorio": None, "estado": "propuesto", "ficheroDatos": None, "analisisPedido": ""}, bloqueos=["trazabilidad_insuficiente"])
    otra = P.nueva_hipotesis("inv-otra", 1, AHORA, id="hip-otra", titulo="De otra investigación")
    he1 = P.nuevo_hecho("inv-g", "hecho", "GFAP", "GFAP plasmático sube antes que NfL en amiloide positivo", "sabido", "fuente", [{"fuenteId": "f-1", "referencia": "Cohorte clínica, 2023", "pagina": 3}], AHORA)
    he1.update(id="he-1", entidades=[_entidad("HGNC:4235", "GFAP")])
    he2 = P.nuevo_hecho("inv-g", "pregunta", "NfL", "¿Cuánto tarda NfL en subir tras GFAP? " * 4, "abierto", "inferencia", [{"fuenteId": "f-3", "referencia": "Ensayo, 2024", "pagina": None}], AHORA)
    he2.update(id="he-2")
    he3 = P.nuevo_hecho("inv-g", "hecho", "APOE", "Solo con una fuente que nadie cita", "sabido", "fuente", [{"fuenteId": "f-99", "referencia": "", "pagina": None}], AHORA)
    he3.update(id="he-3")
    corrida = P.nueva_corrida("inv-g", 1, AHORA)
    corrida["id"] = "cor-1"
    e.update(investigaciones=[inv], hipotesis=[h1, h2, h3, otra], hechos=[he1, he2, he3], ejecuciones=[run1, run2], planesAnalisis=[plan], corridas=[corrida], iteraciones=[P.nueva_iteracion("cor-1", 3, AHORA, [])])
    return e, inv


def _aristas(g, tipo=None):
    return {(en["de"], en["a"], en["tipo"]) for en in g["enlaces"] if tipo is None or en["tipo"] == tipo}


def test_ids_y_aristas_del_port_coinciden_con_el_frontend():
    e, inv = _estado()
    g = G.construir(e, inv)
    ids = [n["id"] for n in g["nodos"]]
    assert len(ids) == len(set(ids)), "ids repetidos"
    # Tronco, área, una sola rama (el cluster con dos hipótesis), hojas, experimento.
    assert ids[:3] == ["objetivo", "area-area-1", "rama-Astrocitos"]
    assert {"hip-1", "hip-2", "hip-3", "ex-hip-1"} <= set(ids)
    assert "ex-hip-3" not in ids, "un experimento propuesto no es nodo"
    assert "hip-otra" not in ids, "las hipótesis de otra investigación quedan fuera"
    assert [n["id"] for n in g["nodos"] if n["tipo"] == "rama"] == ["rama-Astrocitos"]
    # Entidades, hechos y fuentes con su prefijo.
    assert {"ent-HGNC:4235", "ent-HGNC:7752", "he-he-1", "he-he-2", "he-he-3", "fu-f-1", "fu-f-2", "fu-f-3"} <= set(ids)
    assert "fu-f-99" not in ids, "una fuente que ninguna hipótesis cita no es nodo"
    assert g["iteracionMax"] == 3
    a = _aristas(g)
    esperadas = {
        ("objetivo", "area-area-1", "rama"),
        ("objetivo", "rama-Astrocitos", "rama"),
        ("area-area-1", "rama-Astrocitos", "rama"),  # el título 'astrocitos' adopta el cluster 'Astrocitos' sin mayúsculas
        ("rama-Astrocitos", "hip-1", "rama"),
        ("rama-Astrocitos", "hip-2", "rama"),
        ("objetivo", "hip-3", "rama"),  # cluster de una sola hipótesis: cuelga del tronco
        ("hip-1", "ex-hip-1", "experimento"),
        ("hip-1", "ent-HGNC:4235", "entidad"),
        ("hip-1", "ent-HGNC:7752", "entidad"),
        ("he-he-1", "hip-1", "respalda"),  # comparten la fuente f-1
        ("he-he-1", "ent-HGNC:4235", "entidad"),
        ("he-he-2", "hip-2", "respalda"),  # comparten la fuente f-3
        ("hip-1", "fu-f-1", "cita"),
        ("hip-1", "fu-f-2", "cita"),
        ("hip-2", "fu-f-3", "cita"),
        ("fu-f-1", "he-he-1", "respalda"),
        ("fu-f-3", "he-he-2", "respalda"),
        ("ent-HGNC:4235", "ent-HGNC:7752", "causal"),
        ("hip-1", "hip-2", "rival"),
    }
    assert esperadas <= a
    # La arista causal a un nodo sin idCanonico no existe; el rival fantasma tampoco.
    assert len([x for x in a if x[2] == "causal"]) == 1
    assert [x for x in a if x[2] == "rival"] == [("hip-1", "hip-2", "rival")], "el partido inverso de hip-2 se deduplica"
    assert next(en for en in g["enlaces"] if en["tipo"] == "causal")["etiqueta"] == "inferencia con evidencia"
    assert next(en for en in g["enlaces"] if en["tipo"] == "rival")["etiqueta"] == "gano"
    # Ninguna arista apunta a un nodo inexistente; ninguna es un bucle; ninguna se repite.
    for en in g["enlaces"]:
        assert en["de"] in g["porId"] and en["a"] in g["porId"] and en["de"] != en["a"]
    assert len(g["enlaces"]) == len(a)
    # Vecinos no dirigidos.
    assert "hip-1" in g["vecinos"]["fu-f-1"] and "fu-f-1" in g["vecinos"]["hip-1"]


def test_nodos_llevan_etiqueta_sub_peso_estado_alerta_y_alias_como_el_ts():
    e, inv = _estado()
    g = G.construir(e, inv)
    n = g["porId"]
    assert n["objetivo"]["etiqueta"] == "Biomarcadores tempranos" and n["objetivo"]["sub"] == "Orden de alteración de GFAP y NfL" and n["objetivo"]["peso"] == 4 and n["objetivo"]["iteracion"] == 0
    assert n["area-area-1"]["estado"] == "elegida" and n["area-area-1"]["sub"] == "glía"
    assert n["rama-Astrocitos"]["sub"] == "2 hipótesis" and n["rama-Astrocitos"]["peso"] == 2 + 2 * 0.4 and n["rama-Astrocitos"]["iteracion"] == 1
    assert n["hip-1"]["sub"] == "Astrocitos · Elo 1540 · candidata" and n["hip-1"]["peso"] == 1.5 + (1540 - 1300) / 200 and n["hip-1"]["alerta"] is None
    assert n["hip-3"]["alerta"] == "1 bloqueo" and n["hip-3"]["sub"] == "Sin cluster · Elo 1500"
    assert n["ex-hip-1"]["etiqueta"] == "Experimento en INTEC" and n["ex-hip-1"]["sub"] == "datos recibidos · prerregistrado" and n["ex-hip-1"]["estado"] == "datos_recibidos"
    assert n["ent-HGNC:4235"]["alias"] == ["HGNC:4235", "glial fibrillary acidic protein"] and n["ent-HGNC:4235"]["sub"] == "HGNC HGNC:4235 · gen"
    assert n["he-he-2"]["tipo"] == "pregunta" and n["he-he-2"]["etiqueta"].endswith("...") and len(n["he-he-2"]["etiqueta"]) == 90
    assert n["he-he-1"]["tipo"] == "hecho" and n["he-he-1"]["peso"] == 1 + 0.3 and n["he-he-1"]["iteracion"] == 1
    assert n["he-he-3"]["iteracion"] == 3, "un hecho sin hipótesis relacionada nace en la iteración máxima"
    assert n["fu-f-1"]["etiqueta"] == "Cohorte clínica, 2023" and n["fu-f-1"]["sub"] == "Plasma GFAP precedes NfL"
    # Peso por grado en fuentes y entidades: f-1 tiene dos conexiones (cita y respalda).
    assert n["fu-f-1"]["peso"] == 1 + 2 * 0.25 and n["fu-f-2"]["peso"] == 1.25
    assert n["ent-HGNC:4235"]["peso"] == 1 + 3 * 0.25  # hip-1, he-1 y la causal
    # Fuente leída: fragmento o texto completo.
    assert n["fu-f-1"]["leida"] is True and n["fu-f-2"]["leida"] is False and n["fu-f-3"]["leida"] is True
    assert n["hip-1"]["href"] == "#/investigaciones/inv-g/hipotesis/hip-1"


def test_nodos_de_dato_afirmacion_ejecucion_dataset_y_laboratorio():
    e, inv = _estado()
    g = G.construir(e, inv)
    n = g["porId"]
    # La afirmación de literatura no es nodo; la de dato sí, con el índice al no tener afirmacionId.
    assert "af-hip-1-0" not in n and n["af-hip-1-1"]["tipo"] == "afirmacion"
    assert n["af-hip-1-1"]["clase"] == "derivado" and n["af-hip-1-1"]["veredicto"] == "sostenida" and n["af-hip-1-1"]["sintetico"] is False
    assert n["run-1"]["tipo"] == "ejecucion" and n["run-1"]["estado"] == "completado" and n["run-1"]["auditoria"] == "valido" and n["run-1"]["alerta"] is None
    assert n["run-2"]["alerta"] == 'error técnico: no es "sin efecto"' and n["run-2"]["sub"] == "error técnico · auditoría ausente"
    # La iteración de un análisis es la que estaba en marcha cuando empezó (la 3, abierta en AHORA), nunca antes que la hipótesis.
    assert n["run-1"]["iteracion"] == 3 and n["ds-gse1297"]["iteracion"] == 3 and n["af-hip-1-1"]["iteracion"] == 3, "la afirmación derivada hereda la iteración del análisis"
    assert n["run-1"]["ejecucionId"] == "run-1"
    assert n["run-1"]["sub"] == "completado · auditoría válida · efecto detectado"
    assert n["ds-gse1297"]["tipo"] == "dataset" and n["ds-gse1297"]["etiqueta"] == "GSE1297 hipocampo" and n["ds-gse1297"]["sub"] == "publico · aprobado · GEO"
    assert n["lab-hip-1"]["tipo"] == "laboratorio" and n["lab-hip-1"]["estado"] == "confirma" and n["lab-hip-1"]["sub"] == "GFAP 20 % mayor en el grupo tratado"
    assert n["lab-hip-1"]["etiqueta"] == "Resultado del laboratorio: confirma" and n["af-hip-1-1"]["sub"] == "derivado · sostenida"
    datos = _aristas(g, "dato")
    assert datos == {
        ("hip-1", "af-hip-1-1", "dato"),
        ("hip-1", "run-1", "dato"),
        ("af-hip-1-1", "run-1", "dato"),  # la trayectoria de la afirmación es la ejecución
        ("run-1", "ds-gse1297", "dato"),
        ("hip-1", "run-2", "dato"),
        ("run-2", "ds-gse1297", "dato"),
        ("ex-hip-1", "lab-hip-1", "dato"),  # cuelga del experimento porque existe
    }
    for en in g["enlaces"]:
        assert en["de"] in g["porId"] and en["a"] in g["porId"]


def test_laboratorio_cuelga_de_la_hipotesis_si_no_hay_nodo_de_experimento():
    e, inv = _estado()
    h1 = e["hipotesis"][0]
    h1["experimento"]["estado"] = "propuesto"  # sin nodo ex, pero con resultado
    g = G.construir(e, inv)
    assert "ex-hip-1" not in g["porId"] and ("hip-1", "lab-hip-1", "dato") in _aristas(g)


def test_medicion_propia_y_literatura_leida_son_reglas_explicables():
    assert G.es_medicion_propia({"tipo": "ejecucion", "estado": "completado", "auditoria": "valido"}) == (True, "ejecución completada y auditada como válida")
    assert G.es_medicion_propia({"tipo": "ejecucion", "estado": "completado", "auditoria": "no_valido"})[0] is False
    assert G.es_medicion_propia({"tipo": "ejecucion", "estado": "error_tecnico", "auditoria": "valido"})[0] is False
    assert G.es_medicion_propia({"tipo": "laboratorio"})[0] is True
    assert G.es_medicion_propia({"tipo": "afirmacion", "clase": "observacion_original", "sintetico": False, "veredicto": "parcial"}) == (True, "afirmación de dato propio sostenida en parte")
    ok, motivo = G.es_medicion_propia({"tipo": "afirmacion", "clase": "derivado", "sintetico": True, "veredicto": "sostenida"})
    assert ok is False and "sintéticos" in motivo
    assert G.es_medicion_propia({"tipo": "afirmacion", "clase": "literatura", "sintetico": False, "veredicto": "sostenida"})[0] is False
    assert G.es_medicion_propia({"tipo": "afirmacion", "clase": "derivado", "sintetico": False, "veredicto": "no_sostenida"})[0] is False
    assert G.es_medicion_propia({"tipo": "fuente", "leida": True})[0] is False
    assert G.es_literatura_leida({"tipo": "fuente", "leida": True}) == (True, "fuente con texto completo o fragmento literal")
    assert G.es_literatura_leida({"tipo": "fuente", "leida": False})[0] is False
    assert G.es_literatura_leida({"tipo": "hecho"})[0] is False


def test_profundidad_hasta_el_dato_y_hasta_la_literatura():
    e, inv = _estado()
    g = G.construir(e, inv)
    pd = {n["id"]: n["profundidadDato"] for n in g["nodos"]}
    pl = {n["id"]: n["profundidadLiteratura"] for n in g["nodos"]}
    # Mediciones propias a 0; la hipótesis con ejecución válida a 1.
    assert pd["run-1"] == 0 and pd["lab-hip-1"] == 0 and pd["af-hip-1-1"] == 0
    assert pd["hip-1"] == 1 and pd["ex-hip-1"] == 1 and pd["ds-gse1297"] == 1
    # Lo que cuelga de la hipótesis (fuentes, hecho, la ejecución fallida) está a dos saltos.
    assert pd["run-2"] == 2 and pd["fu-f-1"] == 2 and pd["fu-f-2"] == 2 and pd["he-he-1"] == 2
    # El hecho que solo tiene fuente (y la hipótesis que solo tiene literatura) no llegan a ningún dato.
    assert pd["he-he-2"] is None and pd["hip-2"] is None and pd["fu-f-3"] is None and pd["hip-3"] is None and pd["he-he-3"] is None
    # La estructura del árbol y el torneo no transmiten evidencia: el objetivo y las entidades quedan sin camino.
    assert pd["objetivo"] is None and pd["rama-Astrocitos"] is None and pd["ent-HGNC:4235"] is None
    # Literatura leída: f-1 y f-3 (f-2 solo está citada).
    assert pl["fu-f-1"] == 0 and pl["fu-f-3"] == 0 and pl["fu-f-2"] == 2
    assert pl["hip-1"] == 1 and pl["he-he-1"] == 1 and pl["hip-2"] == 1 and pl["he-he-2"] == 1
    assert pl["run-1"] == 2 and pl["af-hip-1-1"] == 2 and pl["hip-3"] is None and pl["he-he-3"] is None
    # Cruzando todas las aristas, el tronco sí alcanza el dato (es la variante, no la regla).
    G.profundidades(g, enlaces=None)
    assert g["porId"]["objetivo"]["profundidadDato"] == 3 and g["porId"]["hip-2"]["profundidadDato"] == 2


def test_vecinos_de_hipotesis_y_de_hecho():
    e, inv = _estado()
    h1, h2, h3 = e["hipotesis"][:3]
    v = G.vecinos_de_hipotesis(e, inv, h1)
    assert [x["id"] for x in v["hechos"]] == ["he-he-1"]
    assert v["fuentes"] == 2 and v["fuentesLeidas"] == 1
    assert [(x["id"], x["resultado"]) for x in v["rivales"]] == [("hip-2", "gano")]
    assert [x["id"] for x in v["ejecuciones"]] == ["run-1", "run-2"]
    assert [x["id"] for x in v["entidades"]] == ["ent-HGNC:4235", "ent-HGNC:7752"]
    assert v["profundidadDato"] == 1 and v["profundidadLiteratura"] == 1
    # Desde el rival, el mismo partido se lee al revés.
    v2 = G.vecinos_de_hipotesis(e, inv, h2)
    assert [(x["id"], x["resultado"]) for x in v2["rivales"]] == [("hip-1", "perdio")]
    assert v2["profundidadDato"] is None and v2["hechos"][0]["id"] == "he-he-2"
    v3 = G.vecinos_de_hipotesis(e, inv, h3)
    assert v3 == {"hechos": [], "fuentes": 0, "fuentesLeidas": 0, "rivales": [], "ejecuciones": [], "entidades": [], "profundidadDato": None, "profundidadLiteratura": None}
    he1 = e["hechos"][0]
    vh = G.vecinos_de_hecho(e, inv, he1)
    assert [x["id"] for x in vh["hipotesis"]] == ["hip-1"] and [x["id"] for x in vh["fuentes"]] == ["fu-f-1"] and [x["id"] for x in vh["entidades"]] == ["ent-HGNC:4235"]
    assert vh["profundidadDato"] == 2 and vh["profundidadLiteratura"] == 1
    assert G.vecinos_de_hecho(e, inv, {"id": "no-existe"})["hipotesis"] == []
    # vecinos_de filtra por tipo y respeta el orden de creación.
    g = G.construir(e, inv)
    assert [x["id"] for x in G.vecinos_de(g, "hip-1", ("fuente",))] == ["fu-f-1", "fu-f-2"]
    assert G.vecinos_de(g, "no-existe") == []


def test_texto_vecinos_es_castellano_delimitado_y_sin_fragmentos():
    e, inv = _estado()
    t = G.texto_vecinos(e, inv, "hip-1", maximo=4)
    lineas = t.split("\n")
    assert lineas[0].startswith("<<< vecinos del grafo de Hipótesis «GFAP sube antes que NfL» (11 en total; profundidad hasta el dato: 1 salto; hasta la literatura leída: 1 salto)")
    assert lineas[-1] == ">>>"
    assert lineas[-2] == "... y 7 vecinos más no listados"
    cuerpo = [x for x in lineas[1:-2]]
    assert len(cuerpo) == 4 and all(x.startswith("- ") for x in cuerpo)
    # Lo medido va primero: las dos ejecuciones, la afirmación de dato y el experimento.
    assert cuerpo[0] == "- Análisis in silico, dato: GFAP mayor en el grupo con patología (p = 0,01) (completado · auditoría válida · efecto detectado)"
    assert cuerpo[1] == '- Análisis in silico, dato: Ejecución run-2 (error técnico · auditoría ausente) [error técnico: no es "sin efecto"]'
    assert cuerpo[2].startswith("- Afirmación con dato, dato: GFAP mayor en el grupo con patología")
    assert cuerpo[3].startswith("- Experimento en el laboratorio, se prueba en: Experimento en INTEC")
    # Con todo: las fuentes llevan la marca de leída y nunca el fragmento.
    todo = G.texto_vecinos(e, inv, "hip-1", maximo=50)
    assert "- Fuente, cita: Cohorte clínica, 2023 (Plasma GFAP precedes NfL) [leída]" in todo
    assert "- Fuente, cita: Revisión, 2022 (Glial markers review) [solo citada, sin texto]" in todo
    assert "GFAP rose two years" not in todo
    assert "- Hipótesis, rival en el torneo: NfL sube antes que GFAP" in todo
    assert "no listados" not in todo
    # Un nodo que no existe no es "no hay": es "no pude comprobar".
    assert "no pude comprobar" in G.texto_vecinos(e, inv, "nada")
    # Un nodo sin vecinos lo dice.
    assert "Sin vecinos" in G.texto_vecinos(e, inv, "he-he-3")


def test_cache_devuelve_el_mismo_grafo_y_se_invalida_al_cambiar_el_estado():
    G.vaciar_cache()
    e, inv = _estado()
    g1 = G.construir_cacheado(e, inv)
    assert G.construir_cacheado(e, inv) is g1
    e["hipotesis"][1]["afirmaciones"].append(_afirmacion("dato", clase="observacion_original"))
    g2 = G.construir_cacheado(e, inv)
    assert g2 is not g1 and "af-hip-2-0" in g2["porId"]
    e["hechos"][0]["actualizadoEn"] = AHORA + 5000
    assert G.construir_cacheado(e, inv) is not g2
    # Como mucho cuatro entradas.
    for i in range(6):
        G.construir_cacheado(e, {**inv, "id": f"inv-{i}"})
    assert len(G._CACHE) == 4
    G.vaciar_cache()


def test_estado_inicial_vacio_no_rompe():
    e = P.estado_inicial()
    inv = {"id": "inv-vacia", "titulo": "", "objetivo": ""}
    g = G.construir(e, inv)
    assert [n["id"] for n in g["nodos"]] == ["objetivo"] and g["enlaces"] == [] and g["iteracionMax"] == 1
    assert g["porId"]["objetivo"]["profundidadDato"] is None
    assert G.vecinos_de_hipotesis(e, inv, {"id": "x"})["profundidadDato"] is None
    assert G.vecinos_de_hecho(e, inv, {"id": "x"}) == {"hipotesis": [], "fuentes": [], "entidades": [], "profundidadDato": None, "profundidadLiteratura": None}
    assert "no pude comprobar" in G.texto_vecinos(e, inv, "x")
    assert "Sin vecinos" in G.texto_vecinos(e, inv, "objetivo")
    # Sin mision ni datasets ni id: tampoco.
    assert G.construir({}, {})["nodos"][0]["id"] == "objetivo"


def test_registros_antiguos_sin_las_claves_nuevas_no_rompen():
    e = P.estado_inicial()
    inv = {"id": "inv-v", "titulo": "Old investigation", "objetivo": "", "mision": None}
    # Hipótesis con lo mínimo: sin procedencia, partidos, afirmaciones, elo, cluster ni iteración.
    vieja = {"id": "hip-v", "investigacionId": "inv-v", "titulo": "Amyloid precedes tau"}
    otra = {"id": "hip-w", "investigacionId": "inv-v", "titulo": "Tau precedes amyloid", "procedencia": {"fuentes": [{"id": "f-v", "referencia": "Old source"}]}, "experimento": {"laboratorio": None}, "grafoCausal": {"nodos": [{"id": "a"}], "aristas": [{"de": "a", "a": "b"}]}, "partidos": [{"rivalId": "hip-v"}], "afirmaciones": [{"tipo": "dato", "texto": "n = 40"}]}
    hecho = {"id": "he-v", "investigacionId": "inv-v", "enunciado": "Something old"}
    run = {"id": "run-v", "hipotesisId": "hip-w"}
    e.update(investigaciones=[inv], hipotesis=[vieja, otra], hechos=[hecho], ejecuciones=[run, {"hipotesisId": "hip-w"}])
    g = G.construir(e, inv)
    n = g["porId"]
    assert set(n) == {"objetivo", "rama-Sin cluster", "hip-v", "hip-w", "he-he-v", "fu-f-v", "af-hip-w-0", "run-v"}
    assert n["hip-v"]["sub"] == "Sin cluster · Elo 1500" and n["hip-v"]["iteracion"] == 1 and n["hip-v"]["alerta"] is None
    assert "ex-hip-w" not in n, "un experimento sin estado se trata como propuesto"
    assert n["fu-f-v"]["leida"] is False and n["fu-f-v"]["sub"] == ""
    assert n["af-hip-w-0"]["clase"] == "literatura" and n["af-hip-w-0"]["veredicto"] is None and n["af-hip-w-0"]["profundidadDato"] is None
    assert n["run-v"]["estado"] == "no_ejecutado" and n["run-v"]["auditoria"] is None and n["run-v"]["profundidadDato"] is None and "ds-" not in " ".join(n)
    assert ("hip-w", "hip-v", "rival") in _aristas(g) and n["he-he-v"]["tipo"] == "hecho"
    assert G.texto_vecinos(e, inv, "hip-w", maximo=8).count("\n- ") == 5


def test_ids_repetidos_y_afirmaciones_compartidas_dan_un_solo_nodo():
    e, inv = _estado()
    h1, h2 = e["hipotesis"][:2]
    # La misma fuente en dos hipótesis: un nodo, dos citas.
    h2["procedencia"]["fuentes"].append(dict(h1["procedencia"]["fuentes"][0]))
    # La misma afirmación compartida (afirmacionId) en dos hipótesis: un nodo, dos aristas de dato.
    compartida = _afirmacion("dato", afirmacionId="obs-1", clase="observacion_original")
    h1["afirmaciones"].append(compartida)
    h2["afirmaciones"].append(dict(compartida))
    # Una hipótesis con el mismo id repetida en el estado.
    e["hipotesis"].append(dict(h2))
    g = G.construir(e, inv)
    assert [n["id"] for n in g["nodos"] if n["id"] == "fu-f-1"] == ["fu-f-1"]
    assert {("hip-1", "fu-f-1", "cita"), ("hip-2", "fu-f-1", "cita")} <= _aristas(g, "cita")
    assert [n["id"] for n in g["nodos"] if n["id"] == "af-obs-1"] == ["af-obs-1"]
    assert {("hip-1", "af-obs-1", "dato"), ("hip-2", "af-obs-1", "dato")} <= _aristas(g, "dato")
    assert [n["id"] for n in g["nodos"] if n["id"] == "hip-2"] == ["hip-2"]
    assert len(g["enlaces"]) == len(_aristas(g))
    # hip-2 ahora tiene un dato propio a un salto, y el rival hip-1 no se duplica.
    assert g["porId"]["hip-2"]["profundidadDato"] == 1 and g["porId"]["rama-Astrocitos"]["sub"] == "3 hipótesis"
    assert [x for x in _aristas(g, "rival")] == [("hip-1", "hip-2", "rival")]


# ---------------------------------------------------------------------------
# Adversarial: lo que rompió la primera versión y no debe volver a romper.
# ---------------------------------------------------------------------------


def test_fuente_leida_en_cualquier_cita_y_no_por_un_fragmento_en_blanco():
    e, inv = _estado()
    h1, h2 = e["hipotesis"][:2]
    # f-2 la cita hip-1 sin fragmento; hip-2 la vuelve a citar con fragmento: está leída (regla del TS).
    f2_leida = {**h1["procedencia"]["fuentes"][1], "fragmento": "Glial markers rise early"}
    h2["procedencia"]["fuentes"].append(f2_leida)
    g = G.construir(e, inv)
    assert g["porId"]["fu-f-2"]["leida"] is True and g["porId"]["fu-f-2"]["profundidadLiteratura"] == 0
    # Un fragmento de solo espacios no es un pasaje leído; una fuente con textoCompleto sí, aunque el fragmento esté vacío.
    e, inv = _estado()
    e["hipotesis"][0]["procedencia"]["fuentes"][1]["fragmento"] = "   \n\t"
    e["hipotesis"][0]["procedencia"]["fuentes"][0]["fragmento"] = ""
    e["hipotesis"][0]["procedencia"]["fuentes"][0]["textoCompleto"] = True
    g = G.construir(e, inv)
    assert g["porId"]["fu-f-2"]["leida"] is False and g["porId"]["fu-f-1"]["leida"] is True
    assert G.es_literatura_leida(g["porId"]["fu-f-2"]) == (False, "fuente citada sin texto completo ni fragmento")


def test_afirmacion_sin_clase_es_literatura_y_no_cuenta_como_medicion():
    # Regla: una clave ausente en un registro antiguo vale lo de hoy ('literatura'),
    # aunque la afirmación tenga trayectoria a una ejecución válida. No se infiere 'derivado'.
    e, inv = _estado()
    vieja = _afirmacion("dato", texto="n = 40", veredicto="sostenida", trayectoria={"id": "run-1", "celda": 0})
    del vieja["clase"]
    e["hipotesis"][1]["afirmaciones"].append(vieja)
    g = G.construir(e, inv)
    n = g["porId"]["af-hip-2-0"]
    assert n["clase"] == "literatura" and n["medicion"] is None
    cuenta, motivo = G.es_medicion_propia(n)
    assert cuenta is False and motivo == "afirmación de clase literatura, no es observación ni derivado"
    # Sigue a un salto del dato porque su trayectoria apunta a la ejecución válida; hip-2 a dos.
    assert n["profundidadDato"] == 1 and g["porId"]["hip-2"]["profundidadDato"] == 2
    assert ("af-hip-2-0", "run-1", "dato") in _aristas(g)
    # Una que sí es medición dice por qué en el nodo, como el TS.
    assert g["porId"]["af-hip-1-1"]["medicion"] == "afirmación de dato propio sostenida"
    assert g["porId"]["run-1"]["medicion"] == "ejecución completada y auditada como válida"
    assert g["porId"]["lab-hip-1"]["medicion"] == "resultado del laboratorio contra el prerregistro"
    assert g["porId"]["run-2"]["medicion"] is None and g["porId"]["hip-1"]["medicion"] is None
    # El verificador no la sostiene: alerta visible en el prompt.
    e["hipotesis"][1]["afirmaciones"].append(_afirmacion("dato", clase="derivado", veredicto="no_sostenida"))
    g = G.construir(e, inv)
    assert g["porId"]["af-hip-2-1"]["alerta"] == "el verificador no la sostiene" and g["porId"]["af-hip-2-1"]["medicion"] is None


def test_cache_se_invalida_al_cambiar_un_registro_en_sitio_sin_recuentos_ni_tiempos():
    G.vaciar_cache()
    e, inv = _estado()
    g0 = G.construir_cacheado(e, inv)
    assert G.construir_cacheado(e, inv) is g0
    e["hipotesis"][2]["estado"] = "descartada"
    assert G.construir_cacheado(e, inv)["porId"]["hip-3"]["alerta"] == "descartada"
    e["hipotesis"][2]["experimento"]["estado"] = "enviado"
    assert "ex-hip-3" in G.construir_cacheado(e, inv)["porId"]
    e["ejecuciones"][1].update(estado="completado", auditoria={"veredicto": "valido"})
    assert G.construir_cacheado(e, inv)["porId"]["run-2"]["profundidadDato"] == 0
    e["hipotesis"][0]["procedencia"]["fuentes"][1]["fragmento"] = "ahora leída"
    assert G.construir_cacheado(e, inv)["porId"]["fu-f-2"]["leida"] is True
    e["hipotesis"][0]["afirmaciones"][1]["veredicto"] = "no_sostenida"
    assert G.construir_cacheado(e, inv)["porId"]["af-hip-1-1"]["medicion"] is None
    e["hipotesis"][1]["cluster"] = "Otro"
    assert "rama-Astrocitos" not in G.construir_cacheado(e, inv)["porId"]
    # Cambiar un campo que el grafo no lee (el código de la procedencia) no invalida.
    g1 = G.construir_cacheado(e, inv)
    e["hipotesis"][0]["procedencia"]["codigo"] = "print('otro')"
    assert G.construir_cacheado(e, inv) is g1
    # Dos estados iguales dan la misma clave (la huella es determinista).
    e2, inv2 = _estado()
    e3, inv3 = _estado()
    assert G.clave_cache(e2, inv2) == G.clave_cache(e3, inv3)
    G.vaciar_cache()


def test_las_salidas_son_copias_y_mutarlas_no_toca_la_cache():
    G.vaciar_cache()
    e, inv = _estado()
    v = G.vecinos_de_hipotesis(e, inv, e["hipotesis"][0])
    v["hechos"][0]["etiqueta"] = "MUTADO"
    v["entidades"][0]["alias"].append("MUTADO")
    vh = G.vecinos_de_hecho(e, inv, e["hechos"][0])
    vh["hipotesis"][0]["sub"] = "MUTADO"
    g = G.construir_cacheado(e, inv)
    assert g["porId"]["he-he-1"]["etiqueta"] != "MUTADO" and "MUTADO" not in g["porId"]["ent-HGNC:4235"]["alias"] and g["porId"]["hip-1"]["sub"] != "MUTADO"
    for n in G.vecinos_de(g, "hip-1"):
        assert n is not g["porId"][n["id"]]
    G.vaciar_cache()


def test_none_tipos_raros_e_ids_enteros_no_rompen():
    for e, inv in ((None, None), ({}, None), (None, {}), ([], "x"), ({"hipotesis": None, "hechos": "no"}, {"id": 3, "mision": [], "datasets": "x"})):
        g = G.construir(e, inv)
        assert [n["id"] for n in g["nodos"]] == ["objetivo"] and g["enlaces"] == []
    # investigacionId entero en un registro heredado: enlaza igual (se compara como cadena).
    e = P.estado_inicial()
    inv = {"id": 7, "titulo": "t", "objetivo": ""}
    e.update(investigaciones=[inv], hipotesis=[{"id": 1, "investigacionId": 7, "titulo": "x", "procedencia": {"fuentes": [{"id": 9, "fragmento": "leído"}]}}], hechos=[{"id": 2, "investigacionId": "7", "enunciado": "h", "procedencia": [{"fuenteId": "9"}]}], ejecuciones=[{"id": 11, "hipotesisId": "1", "estado": "completado", "auditoria": {"veredicto": "valido"}}])
    g = G.construir(e, inv)
    assert {"1", "fu-9", "he-2", "11"} <= set(g["porId"]) and {("he-2", "1", "respalda"), ("fu-9", "he-2", "respalda"), ("1", "11", "dato")} <= _aristas(g)
    assert G.vecinos_de_hipotesis(e, inv, {"id": 1})["profundidadDato"] == 1
    assert "no pude comprobar" in G.texto_vecinos(e, inv, 5) and "Hipótesis «x»" in G.texto_vecinos(e, inv, 1)
    assert G.vecinos_de_hipotesis(e, inv, None)["fuentes"] == 0 and G.vecinos_de_hecho(e, inv, None)["hipotesis"] == []
    # maximo 0 o negativo: ningún vecino listado, y el recuento de los que faltan es el total.
    e, inv = _estado()
    for m in (0, -3, "2"):
        t = G.texto_vecinos(e, inv, "hip-1", maximo=m)
        assert t.endswith(">>>") and ("... y 11 vecinos más no listados" in t or m == "2")
    assert G.texto_vecinos(e, inv, "hip-1", maximo="2").count("\n- ") == 2
    assert G.texto_vecinos(e, inv, "hip-1", maximo=None).count("\n- ") == 8


def test_ejecucion_listada_en_la_hipotesis_y_plan_sin_dataset():
    e, inv = _estado()
    # Una reproducción (sin hipotesisId) que la hipótesis lista en 'ejecuciones' entra al grafo, como en el TS.
    run3 = P.nueva_ejecucion("inv-g", None, "plan-1", "reproduccion", "print(3)", 3, "abc", AHORA)
    run3["id"] = "run-3"
    # Otra con planId 'sin-plan' (registro antiguo): nodo sin dataset, sin romper.
    run4 = P.nueva_ejecucion("inv-g", "hip-2", "sin-plan", "hipotesis", "print(4)", 4, "abc", AHORA)
    run4["id"] = "run-4"
    e["ejecuciones"] += [run3, run4]
    e["hipotesis"][1]["ejecuciones"] = ["run-3", "run-1", "no-existe", None, 7]
    g = G.construir(e, inv)
    a = _aristas(g, "dato")
    assert {("hip-2", "run-3", "dato"), ("hip-2", "run-4", "dato"), ("hip-2", "run-1", "dato"), ("hip-1", "run-1", "dato"), ("run-3", "ds-gse1297", "dato")} <= a
    assert not any(x[1].startswith("ds-") and x[0] == "run-4" for x in a)
    # run-1 la comparten hip-1 y hip-2: un solo nodo, en la iteración en marcha cuando empezó (la 3).
    assert [n["id"] for n in g["nodos"] if n["id"] == "run-1"] == ["run-1"] and g["porId"]["run-1"]["iteracion"] == 3
    # Sin instante de inicio (registro antiguo) la iteración es la de la hipótesis; nunca anterior a ella.
    run4["inicio"] = None
    run3["inicio"] = AHORA - 10 ** 9  # antes de toda iteración fechada
    g = G.construir(e, inv)
    assert g["porId"]["run-4"]["iteracion"] == 2 and g["porId"]["run-3"]["iteracion"] == 2
    # Orden del TS por hipótesis: primero las que la nombran (orden del estado), luego las listadas (orden de la lista).
    assert [n["id"] for n in g["nodos"] if n["tipo"] == "ejecucion"] == ["run-1", "run-2", "run-4", "run-3"]
    # Los vecinos van en orden de creación de los nodos: run-1 nació bajo hip-1; run-2 no es de hip-2.
    assert [x["id"] for x in G.vecinos_de_hipotesis(e, inv, e["hipotesis"][1])["ejecuciones"]] == ["run-1", "run-4", "run-3"]
    # Una ejecución repetida en el estado cuenta una vez y la primera manda.
    e["ejecuciones"].append({**run4, "estado": "completado", "auditoria": {"veredicto": "valido"}})
    g = G.construir(e, inv)
    assert [n["id"] for n in g["nodos"] if n["id"] == "run-4"] == ["run-4"] and g["porId"]["run-4"]["estado"] == "no_ejecutado"


def test_orden_de_creacion_de_los_nodos_de_dato_es_el_del_ts():
    e, inv = _estado()
    g = G.construir(e, inv)
    # Por hipótesis: afirmaciones, análisis con su dataset, laboratorio; no todas las afirmaciones primero.
    assert [n["id"] for n in g["nodos"] if n["tipo"] in ("afirmacion", "ejecucion", "dataset", "laboratorio")] == ["af-hip-1-1", "run-1", "ds-gse1297", "run-2", "lab-hip-1"]
    # Una afirmación compartida nace en la iteración mínima aunque la primera hipótesis que la usa sea posterior.
    comp = _afirmacion("dato", afirmacionId="obs-9", clase="observacion_original")
    e["hipotesis"][0]["afirmaciones"].append({**comp, "iteracion": 5})
    e["hipotesis"][1]["afirmaciones"].append({**comp, "iteracion": 2})
    assert G.construir(e, inv)["porId"]["af-obs-9"]["iteracion"] == 2


def test_hechos_y_clusters_en_tiempo_lineal():
    import time

    e = P.estado_inicial()
    inv = {"id": "inv-big", "titulo": "t", "objetivo": ""}
    hips = []
    for i in range(400):
        h = P.nueva_hipotesis("inv-big", 1, AHORA, id=f"h{i}", titulo=f"H {i}", cluster=f"c{i % 200}")
        h["procedencia"]["fuentes"] = [P.nueva_fuente(id=f"f{i}", fragmento="x"), P.nueva_fuente(id=f"f{(i + 1) % 400}")]
        h["afirmaciones"] = [_afirmacion("dato", afirmacionId=f"a{i}-{k}") for k in range(5)]
        hips.append(h)
    hechos = []
    for j in range(3000):
        he = P.nuevo_hecho("inv-big", "hecho", "t", f"Hecho {j}", "sabido", "fuente", [{"fuenteId": f"f{j % 400}", "referencia": "", "pagina": None}], AHORA)
        he["id"] = f"he{j}"
        hechos.append(he)
    e.update(investigaciones=[inv], hipotesis=hips, hechos=hechos)
    t0 = time.perf_counter()
    g = G.construir(e, inv)
    assert time.perf_counter() - t0 < 2.0
    # Cada hecho respalda a las dos hipótesis que citan su fuente; ninguna arista suelta.
    assert sum(1 for en in g["enlaces"] if en["tipo"] == "respalda" and en["de"].startswith("he-")) == 6000
    assert all(en["de"] in g["porId"] and en["a"] in g["porId"] for en in g["enlaces"])
    assert len(g["porId"]) == 1 + 200 + 400 + 400 + 3000 + 2000


def test_fuzz_registros_corruptos_no_rompen_ni_dejan_aristas_sueltas():
    import copy
    import random

    rng = random.Random(7)
    base_e, base_inv = _estado()

    def mutar(x, profundidad=0):
        if isinstance(x, dict):
            for k in list(x):
                r = rng.random()
                if r < 0.08:
                    del x[k]
                elif r < 0.14:
                    x[k] = None
                elif r < 0.18:
                    x[k] = rng.choice([[], {}, "", 0, True, 3.5, "texto", ["a"], {"b": 1}])
                elif profundidad < 5:
                    mutar(x[k], profundidad + 1)
        elif isinstance(x, list):
            for i in range(len(x)):
                if rng.random() < 0.05:
                    x[i] = rng.choice([None, "", 0, [], {}])
                else:
                    mutar(x[i], profundidad + 1)

    for _ in range(300):
        e = copy.deepcopy(base_e)
        inv = copy.deepcopy(base_inv)
        mutar(e)
        mutar(inv)
        g = G.construir(e, inv)
        ids = [n["id"] for n in g["nodos"]]
        assert len(ids) == len(set(ids))
        for en in g["enlaces"]:
            assert en["de"] in g["porId"] and en["a"] in g["porId"] and en["de"] != en["a"]
        G.clave_cache(e, inv)
        G.texto_vecinos(e, inv, "hip-1")
        G.vecinos_de_hipotesis(e, inv, {"id": "hip-1"})
    G.vaciar_cache()


def test_textos_generados_llevan_tildes_y_no_guiones_largos():
    import inspect
    import re

    fuente = inspect.getsource(G)
    assert "\u2014" not in fuente
    e, inv = _estado()
    e["ejecuciones"].append({**e["ejecuciones"][1], "id": "run-t", "estado": "tiempo_agotado"})
    g = G.construir(e, inv)
    textos = [str(v) for n in g["nodos"] for v in n.values()] + [G.texto_vecinos(e, inv, i, maximo=50) for i in g["porId"]] + list(G.NOMBRE_TIPO.values()) + list(G.NOMBRE_ENLACE.values())
    todo = "\n".join(textos)
    assert "\u2014" not in todo
    import unicodedata

    def sin_tilde(s):
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()

    for palabra in ("hipótesis ", "auditoría", "ejecución ", "sintético", "leída", "técnico", "válida", "análisis"):
        # La forma sin tilde solo puede aparecer dentro de un identificador (sin espacio), nunca en texto.
        assert not re.search(rf"(?<![\w-]){sin_tilde(palabra)}", todo), palabra
    assert 'tiempo agotado: no es "sin efecto"' in todo


def test_ejecucion_con_el_id_de_una_hipotesis_no_pisa_el_nodo_ni_une_dos_hipotesis():
    e, inv = _estado()
    # Una ejecución cuyo id coincide con el de otra hipótesis: sin la regla, hip-1 quedaría
    # unida a hip-2 por una arista 'dato' inventada. Con ella, el nodo va con prefijo 'ej-'.
    run = P.nueva_ejecucion("inv-g", "hip-1", "plan-1", "hipotesis", "print(9)", 9, "abc", AHORA)
    run["id"] = "hip-2"
    e["ejecuciones"].append(run)
    e["hipotesis"][0]["afirmaciones"].append(_afirmacion("dato", texto="cifra del choque", clase="derivado", trayectoria={"id": "hip-2", "celda": 1}))
    g = G.construir(e, inv)
    a = _aristas(g)
    assert g["porId"]["hip-2"]["tipo"] == "hipotesis" and g["porId"]["ej-hip-2"]["tipo"] == "ejecucion" and g["porId"]["ej-hip-2"]["ejecucionId"] == "hip-2"
    assert ("hip-1", "ej-hip-2", "dato") in a and ("hip-1", "hip-2", "dato") not in a
    assert ("af-hip-1-2", "ej-hip-2", "dato") in a and ("af-hip-1-2", "hip-2", "dato") not in a
    assert ("ej-hip-2", "ds-gse1297", "dato") in a
    assert [x["id"] for x in G.vecinos_de_hipotesis(e, inv, e["hipotesis"][0])["ejecuciones"]] == ["run-1", "run-2", "ej-hip-2"]
    assert [x["id"] for x in G.vecinos_de_hipotesis(e, inv, e["hipotesis"][0])["rivales"]] == ["hip-2"]


def test_iteracion_en_un_instante_como_el_ts():
    its = [{"numero": 1, "empezadaEn": 100, "terminadaEn": 200}, {"numero": 2, "empezadaEn": 300, "terminadaEn": 400}, {"numero": 3, "empezadaEn": 500, "terminadaEn": None}]
    assert G.iteracion_en(its, 150) == 1, "la contiene"
    assert G.iteracion_en(its, 250) == 1, "en el hueco manda la última que había empezado"
    assert G.iteracion_en(its, 350) == 2 and G.iteracion_en(its, 500) == 3 and G.iteracion_en(its, 10 ** 12) == 3
    assert G.iteracion_en(its, 50) is None, "antes de toda iteración fechada"
    assert G.iteracion_en(list(reversed(its)), 350) == 2, "no depende del orden de la lista"
    # Dos abiertas a la vez: gana la que empezó más tarde; con el mismo inicio, la de número mayor.
    assert G.iteracion_en([{"numero": 4, "empezadaEn": 100, "terminadaEn": None}, {"numero": 5, "empezadaEn": 120, "terminadaEn": None}], 130) == 5
    assert G.iteracion_en([{"numero": 4, "empezadaEn": 100, "terminadaEn": None}, {"numero": 6, "empezadaEn": 100, "terminadaEn": None}], 130) == 6
    # Entradas rotas: sin fecha, con texto, con booleanos; t None, texto o booleano.
    assert G.iteracion_en([{"numero": 1}, {"numero": 2, "empezadaEn": "ayer"}, "x", None, {"numero": 3, "empezadaEn": True}], 500) is None
    assert G.iteracion_en(its, None) is None and G.iteracion_en(its, "500") is None and G.iteracion_en(its, True) is None and G.iteracion_en([], 5) is None
    assert G.iteracion_en(its, float("nan")) is None and G.iteracion_en(its, float("inf")) is None
