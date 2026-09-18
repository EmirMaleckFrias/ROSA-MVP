"""Las tres cifras de aprendizaje (acierto de lo prerregistrado, tiempo hasta
cada decisión, reutilización de lo heredado): aritmética sobre el registro,
tasas exactas, casos sin dirección, sin datos devuelve None y no 0, medianas,
registros antiguos sin claves, ids repetidos y heredados, textos con tildes."""

from rosa import cifras_aprendizaje as C
from rosa.estado import acciones as A
from rosa.estado import plantilla as P

H = 3_600_000  # una hora en milisegundos


def _estado(inv="inv-a", ahora=0):
    e = P.estado_inicial()
    assert A.crear_investigacion(e, {"titulo": "T", "objetivo": "O", "condicionParada": "3 iteraciones"}, ahora, id_=inv) == inv
    return e


def _hip(e, inv, ahora=0, **campos):
    h = P.nueva_hipotesis(inv, 1, ahora, titulo="GFAP sube antes que NfL", enunciado="E", **campos)
    e["hipotesis"].append(h)
    return h


def _plan(e, inv, hid, **campos):
    plan = P.nuevo_plan_analisis(inv, hid, "ds1", 1000, prueba="t de Welch", **campos)
    e["planesAnalisis"].append(plan)
    return plan


def _run(e, plan, interpretacion, veredicto="valido", fin=2000, hash_plan=None):
    run = P.nueva_ejecucion(plan["investigacionId"], plan["hipotesisId"], plan["id"], "hipotesis", "print('RESULTADO p=0.01')", 12345, "hd", 1500)
    run["estado"] = "completado"
    run["fin"] = fin
    run["hashPlan"] = plan["hashPlan"] if hash_plan is None else hash_plan
    run["interpretacion"] = {"estado": interpretacion, "resumen": "r"} if interpretacion else None
    run["auditoria"] = {"veredicto": veredicto, "comprobaciones": [], "motivo": "", "quien": "juez", "fecha": fin} if veredicto else None
    e["ejecuciones"].append(run)
    return run


def _experimento(h, confirma, veredicto, prerregistrado=5000, fecha=9000):
    h["experimento"] = {"protocolo": "p", "ensayo": "ELISA de GFAP", "costeEstimado": "", "laboratorio": "Lab", "estado": "datos_recibidos", "ficheroDatos": None, "analisisPedido": "", "confirma": confirma, "refuta": "GFAP igual", "prerregistradoEn": prerregistrado, "resultado": {"veredicto": veredicto, "resultado": "", "motivo": "", "limitaciones": "", "cifras": [], "exploratorio": "", "fecha": fecha, "fichero": None} if veredicto else None}


# -- 1. Acierto de lo prerregistrado ------------------------------------------


def test_acierto_tasas_exactas_por_fuente_y_por_nivel():
    e = _estado()
    h1 = _hip(e, "inv-a", conclusion={"certeza": "baja", "direccion": "apoya"})
    h2 = _hip(e, "inv-a")
    # Análisis: A acierto, B fallo, C sin dirección, D exploratorio (sin dirección),
    # E auditoría no válida (no es caso), F no evaluable, G reproducción (fuera).
    _run(e, _plan(e, "inv-a", h1["id"], direccionEsperada="GFAP mayor en EA que en control"), "efecto_detectado")
    _run(e, _plan(e, "inv-a", h1["id"], direccionEsperada="lower in AD"), "sin_efecto_detectable")
    _run(e, _plan(e, "inv-a", h2["id"], direccionEsperada=""), "efecto_detectado")
    _run(e, _plan(e, "inv-a", h2["id"], tipo="exploratorio", direccionEsperada="mayor"), "efecto_detectado")
    _run(e, _plan(e, "inv-a", h2["id"], direccionEsperada="mayor"), "efecto_detectado", veredicto="no_valido")
    _run(e, _plan(e, "inv-a", h2["id"], direccionEsperada="mayor"), "no_evaluable")
    _run(e, _plan(e, "inv-a", None, tipo="reproduccion", direccionEsperada="igual"), "efecto_detectado")
    # Laboratorio: l1 acierto (moderada), l2 sin criterio, l3 inconcluso, l4 sin
    # prerregistro (fuera), l5 fallo, l6 resultado anterior al prerregistro.
    l1 = _hip(e, "inv-a", conclusion={"certeza": "moderada"})
    _experimento(l1, "GFAP sube un 20 %", "confirma")
    l2 = _hip(e, "inv-a")
    _experimento(l2, "", "refuta")
    l3 = _hip(e, "inv-a")
    _experimento(l3, "GFAP sube", "inconcluso")
    l4 = _hip(e, "inv-a")
    _experimento(l4, "GFAP sube", "confirma", prerregistrado=None)
    l5 = _hip(e, "inv-a", conclusion={"certeza": "altisima"})  # nivel desconocido: no entra en porNivel
    _experimento(l5, "GFAP sube", "refuta")
    l6 = _hip(e, "inv-a")
    _experimento(l6, "GFAP sube", "confirma", prerregistrado=9000, fecha=5000)
    r = C.acierto_prerregistrado(e, "inv-a")
    assert r["casos"] == 10 and r["conDireccion"] == 4 and r["aciertos"] == 2 and r["tasa"] == 0.5
    assert r["sinDireccion"] == 4 and r["noEvaluables"] == 2
    assert r["porFuente"]["analisis"] == {"casos": 5, "conDireccion": 2, "aciertos": 1, "tasa": 0.5, "sinDireccion": 2, "noEvaluables": 1}
    assert r["porFuente"]["laboratorio"] == {"casos": 5, "conDireccion": 2, "aciertos": 1, "tasa": 0.5, "sinDireccion": 2, "noEvaluables": 1}
    assert r["porNivel"] == {"baja": {"casos": 2, "aciertos": 1}, "moderada": {"casos": 1, "aciertos": 1}}
    assert r["excluidos"] == {"planesSinCongelar": 0, "planesSinEjecucionValida": 1, "planesReproduccion": 1, "laboratorioSinPrerregistro": 1}
    clases = [c["clase"] for c in r["detalle"]]
    assert clases == ["acierto", "fallo", "sin_direccion", "sin_direccion", "no_evaluable", "acierto", "sin_direccion", "no_evaluable", "fallo", "sin_direccion"]
    assert all(c["motivo"] for c in r["detalle"])
    assert "exploratorio" in r["detalle"][3]["motivo"] and "anterior al prerregistro" in r["detalle"][9]["motivo"]
    assert "sentido del efecto no se comprueba" in r["detalle"][0]["motivo"]


def test_acierto_filtra_por_investigacion_y_none_agrega_todas():
    e = _estado("inv-a")
    assert A.crear_investigacion(e, {"titulo": "T2", "objetivo": "O", "condicionParada": "1 iteración"}, 0, id_="inv-b") == "inv-b"
    ha = _hip(e, "inv-a")
    hb = _hip(e, "inv-b")
    _run(e, _plan(e, "inv-a", ha["id"], direccionEsperada="mayor"), "efecto_detectado")
    _run(e, _plan(e, "inv-b", hb["id"], direccionEsperada="mayor"), "sin_efecto_detectable")
    assert C.acierto_prerregistrado(e, "inv-a")["tasa"] == 1.0
    assert C.acierto_prerregistrado(e, "inv-b")["tasa"] == 0.0
    todo = C.acierto_prerregistrado(e)
    assert todo["conDireccion"] == 2 and todo["tasa"] == 0.5


def test_acierto_toma_la_ultima_ejecucion_valida_y_detecta_plan_cambiado():
    e = _estado()
    h = _hip(e, "inv-a")
    plan = _plan(e, "inv-a", h["id"], direccionEsperada="mayor")
    _run(e, plan, "sin_efecto_detectable", fin=2000)
    _run(e, plan, "efecto_detectado", fin=3000)  # la última manda
    _run(e, plan, "sin_efecto_detectable", fin=2500, veredicto="no_valido")  # no cuenta
    r = C.acierto_prerregistrado(e, "inv-a")
    assert r["casos"] == 1 and r["aciertos"] == 1
    # La ejecución corrió otro hash: el plan cambió después, no prueba lo congelado.
    plan2 = _plan(e, "inv-a", h["id"], direccionEsperada="mayor")
    _run(e, plan2, "efecto_detectado", fin=4000, hash_plan="otro")
    r = C.acierto_prerregistrado(e, "inv-a")
    assert r["casos"] == 2 and r["conDireccion"] == 1 and r["detalle"][1]["clase"] == "sin_direccion" and "hash" in r["detalle"][1]["motivo"]


def test_acierto_ids_repetidos_no_duplican_casos():
    e = _estado()
    h = _hip(e, "inv-a")
    plan = _plan(e, "inv-a", h["id"], direccionEsperada="mayor")
    e["planesAnalisis"].append(plan)  # el mismo plan dos veces en el registro
    _run(e, plan, "efecto_detectado")
    r = C.acierto_prerregistrado(e, "inv-a")
    assert r["casos"] == 1 and r["conDireccion"] == 1 and r["tasa"] == 1.0
    # Dos hipótesis con el mismo id y experimento: un solo caso.
    h2 = _hip(e, "inv-a")
    h2["id"] = h["id"]
    _experimento(h, "sube", "confirma")
    _experimento(h2, "sube", "refuta")
    assert C.acierto_prerregistrado(e, "inv-a")["porFuente"]["laboratorio"]["casos"] == 1


def test_sin_datos_devuelve_none_y_no_cero():
    e = _estado()
    a = C.acierto_prerregistrado(e, "inv-a")
    assert a["casos"] == 0 and a["tasa"] is None and a["porFuente"]["analisis"]["tasa"] is None and a["porNivel"] == {}
    t = C.tiempo_hasta_decision(e, "inv-a", ahora=10 * H)
    assert t["casos"] == 0 and t["medianaHoras"] is None and t["p90Horas"] is None and t["abiertasSinDecisionHoras"] is None
    r = C.reutilizacion_heredada(e, "inv-a")
    assert r["hechosHeredados"] == 0 and r["tasa"] is None and r["hipotesisConHerencia"] == 0
    # Con casos pero todos sin dirección la tasa sigue siendo None (no 0).
    h = _hip(e, "inv-a")
    _run(e, _plan(e, "inv-a", h["id"], direccionEsperada=""), "efecto_detectado")
    a = C.acierto_prerregistrado(e, "inv-a")
    assert a["casos"] == 1 and a["sinDireccion"] == 1 and a["tasa"] is None
    res = C.resumen_cifras(e, "inv-a", ahora=10 * H)
    assert res["acierto"]["tasa"] is None and "no se puede medir" in res["texto"] and "no heredó hechos" in res["texto"]
    assert "1 caso sin dirección declarada" in res["texto"]


# -- 2. Tiempo hasta cada decisión ---------------------------------------------


def test_tiempo_hasta_decision_medianas_p90_y_por_etapa():
    e = _estado()
    h1 = _hip(e, "inv-a", ahora=0)
    h2 = _hip(e, "inv-a", ahora=0)
    h3 = _hip(e, "inv-a", ahora=0)  # viva sin decisión
    h4 = _hip(e, "inv-a", ahora=0, estado="descartada")  # descartada sin decisión: no cuenta como abierta
    A.registrar_decision(e, h1, "killer_1", "avanzar", "m", "rosa", 2 * H)
    A.registrar_decision(e, h1, "killer_1", "reformular", "m", "rosa", 5 * H)  # segunda de la etapa: no cuenta
    e["decisiones"].append(P.nueva_decision("inv-a", h1["id"], 1, "persona", "aceptada", "m", "Investigadora", 10 * H))
    A.registrar_decision(e, h2, "killer_1", "suspender", "m", "rosa", 4 * H)
    e["decisiones"].append(P.nueva_decision("inv-a", h2["id"], 1, "priorizacion", "candidata", "m", "rosa", 6 * H))
    e["decisiones"][-1]["fecha"] = None  # sin fecha: se ignora
    t = C.tiempo_hasta_decision(e, "inv-a", ahora=6 * H)
    assert t["casos"] == 3 and t["hipotesis"] == 4
    assert t["medianaHoras"] == 4.0 and t["p90Horas"] == 10.0  # [2, 10, 4]: rango ceil(2,7) = 3 -> 10
    assert t["porEtapa"] == {"killer_1": {"casos": 2, "medianaHoras": 3.0}, "persona": {"casos": 1, "medianaHoras": 10.0}}
    assert list(t["porEtapa"]) == ["killer_1", "persona"]  # orden de las etapas, no alfabético
    assert t["abiertasSinDecision"] == 1 and t["abiertasSinDecisionHoras"] == 6.0
    assert t["decisionesSinFecha"] == 1 and t["fechasInvertidas"] == 0
    assert {d["hipotesisId"] for d in t["detalle"]} == {h1["id"], h2["id"]}
    assert h3["id"] not in {d["hipotesisId"] for d in t["detalle"]} and h4["id"] not in {d["hipotesisId"] for d in t["detalle"]}


def test_tiempo_fechas_invertidas_y_sin_creacion_no_rompen():
    e = _estado()
    h = _hip(e, "inv-a", ahora=10 * H)
    A.registrar_decision(e, h, "killer_1", "avanzar", "m", "rosa", 8 * H)  # decidida antes de nacer
    e["hipotesis"].append({"id": "h-vieja", "investigacionId": "inv-a"})  # sin creadaEn
    e["decisiones"].append({"hipotesisId": "h-vieja", "decision": "aceptada"})  # sin etapa ni fecha
    t = C.tiempo_hasta_decision(e, "inv-a", ahora=20 * H)
    assert t["casos"] == 1 and t["medianaHoras"] == 0.0 and t["fechasInvertidas"] == 1 and t["sinFechaCreacion"] == 1
    assert C.tiempo_hasta_decision(e, "inv-a")["casos"] == 1  # sin `ahora`: usa el reloj y no falla


def test_p90_por_rango_mas_cercano():
    assert C._p90([2.0, 4.0, 10.0]) == 10.0
    assert C._p90([float(i) for i in range(1, 11)]) == 9.0
    assert C._p90([]) is None and C._mediana([]) is None


# -- 3. Reutilización de lo heredado ------------------------------------------


def _hecho(e, inv, id_, estado="sabido", fuente_id="f-x", referencia="Ref", afirmaciones=None):
    h = P.nuevo_hecho(inv, "hecho", "Tema", f"Enunciado {id_}", estado, "fuente", [{"fuenteId": fuente_id, "referencia": referencia, "pagina": 1}], 100, afirmacion_ids=afirmaciones or [])
    h["id"] = id_
    e["hechos"].append(h)
    return h


def test_reutilizacion_heredada_por_afirmacion_fuente_referencia_y_nombre():
    e = _estado("inv-o")
    _hecho(e, "inv-o", "he-1", afirmaciones=["af-1"])
    _hecho(e, "inv-o", "he-2", fuente_id="f-2")
    _hecho(e, "inv-o", "he-3", fuente_id="f-otra", referencia="Jones  2023")
    _hecho(e, "inv-o", "he-4")  # sabido y nombrado en la procedencia
    _hecho(e, "inv-o", "he-40")  # sabido pero no nombrado ('he-4' no debe colarse dentro de 'he-40')
    _hecho(e, "inv-o", "he-5", estado="abierto")  # nombrado pero abierto: la regla pide sabido
    _hecho(e, "inv-o", "he-6", afirmaciones=["af-6"])  # solo lo usa una descartada
    assert A.crear_investigacion(e, {"titulo": "D", "objetivo": "O", "condicionParada": "1", "heredarModeloDe": "inv-o"}, 0, id_="inv-d") == "inv-d"
    assert sorted(x["id"] for x in e["hechos"] if x["investigacionId"] == "inv-d") == ["he-1-inv-d", "he-2-inv-d", "he-3-inv-d", "he-4-inv-d", "he-40-inv-d", "he-5-inv-d", "he-6-inv-d"]
    _hecho(e, "inv-d", "he-propio", afirmaciones=["af-1"])  # propio de la investigación: no es heredado
    ha = _hip(e, "inv-d", afirmaciones=[{"texto": "t", "cita": "c", "veredicto": "sostenida", "motivo": "", "entidadDistinta": False, "tipo": "literatura", "trayectoria": None, "afirmacionId": "af-1"}])
    ha["procedencia"]["fuentes"] = [P.nueva_fuente(id="f-2", referencia="Otra")]
    hb = _hip(e, "inv-d")
    hb["procedencia"]["fuentes"] = [P.nueva_fuente(id="f-zzz", referencia="Jones 2023")]
    hc = _hip(e, "inv-d", estado="descartada", afirmaciones=[{"texto": "t", "cita": "c", "veredicto": "sostenida", "motivo": "", "entidadDistinta": False, "tipo": "literatura", "trayectoria": None, "afirmacionId": "af-6"}])
    hc["procedencia"]["registro"] = ["iteración 1: nace a partir del hecho he-4 y de la pregunta he-5"]
    r = C.reutilizacion_heredada(e, "inv-d")
    assert r["hechosHeredados"] == 7 and r["usados"] == 4 and r["tasa"] == 0.571 and r["hipotesisConHerencia"] == 3 and r["hipotesisVivas"] == 2
    por_id = {d["hechoId"]: d for d in r["detalle"]}
    assert por_id["he-1-inv-d"]["usadoPor"] == [ha["id"]] and "afirmación" in por_id["he-1-inv-d"]["motivo"]
    assert por_id["he-2-inv-d"]["usadoPor"] == [ha["id"]] and "fuente" in por_id["he-2-inv-d"]["motivo"]
    assert por_id["he-3-inv-d"]["usadoPor"] == [hb["id"]]
    assert por_id["he-4-inv-d"]["usadoPor"] == [hc["id"]] and "nombrado" in por_id["he-4-inv-d"]["motivo"]
    assert por_id["he-40-inv-d"]["usadoPor"] == [] and por_id["he-5-inv-d"]["usadoPor"] == [] and por_id["he-6-inv-d"]["usadoPor"] == []
    assert "ninguna hipótesis" in por_id["he-6-inv-d"]["motivo"]
    # Desde la investigación de origen no hay nada heredado.
    assert C.reutilizacion_heredada(e, "inv-o")["hechosHeredados"] == 0


def test_reutilizacion_detecta_sufijo_de_investigacion_sin_inv():
    e = _estado("origen")
    _hecho(e, "origen", "he-x", afirmaciones=["af-x"])
    assert A.crear_investigacion(e, {"titulo": "D", "objetivo": "O", "condicionParada": "1"}, 0, id_="destino") == "destino"
    assert A.copiar_hechos(e, "origen", "destino") == 1
    assert e["hechos"][-1]["id"] == "he-x-destino"
    r = C.reutilizacion_heredada(e, "destino")
    assert r["hechosHeredados"] == 1 and r["usados"] == 0 and r["tasa"] == 0.0
    # Un id que termina como el de la investigación pero sin original no es heredado.
    e["hechos"].append(P.nuevo_hecho("destino", "hecho", "T", "E", "sabido", "fuente", [], 0))
    e["hechos"][-1]["id"] = "he-suelto-destino"
    assert C.reutilizacion_heredada(e, "destino")["hechosHeredados"] == 1


def test_registros_antiguos_sin_claves_no_rompen():
    e = _estado()
    e["hipotesis"].append({"id": "h-min", "investigacionId": "inv-a"})
    e["planesAnalisis"].append({"id": "p-old", "investigacionId": "inv-a", "hipotesisId": "h-min", "hashPlan": "abc"})
    e["planesAnalisis"].append({"id": "p-sin-hash", "investigacionId": "inv-a", "hipotesisId": "h-min"})
    e["ejecuciones"].append({"planId": "p-old"})  # sin auditoría ni interpretación
    e["ejecuciones"].append({"id": "r-suelta"})  # sin plan
    e["decisiones"].append({"hipotesisId": "h-min"})
    e["hechos"].append({"id": "he-z-inv-a", "investigacionId": "inv-a"})  # heredado sin afirmaciones ni procedencia
    e["hechos"].append("basura")  # una entrada que ni es dict
    e["hipotesis"].append({"id": "h-exp", "investigacionId": "inv-a", "experimento": {"resultado": {"veredicto": "confirma"}}, "conclusion": "texto viejo"})
    a = C.acierto_prerregistrado(e, "inv-a")
    assert a["casos"] == 0 and a["excluidos"]["planesSinEjecucionValida"] == 1 and a["excluidos"]["planesSinCongelar"] == 1 and a["excluidos"]["laboratorioSinPrerregistro"] == 1
    t = C.tiempo_hasta_decision(e, "inv-a", ahora=5 * H)
    assert t["casos"] == 0 and t["sinFechaCreacion"] == 2
    r = C.reutilizacion_heredada(e, "inv-a")
    assert r["hechosHeredados"] == 1 and r["usados"] == 0
    res = C.resumen_cifras(e, "inv-a", ahora=5 * H)
    assert set(res) == {"investigacionId", "fecha", "acierto", "tiempo", "reutilizacion", "glosario", "texto"}
    assert C.texto_cifras({}) and C.texto_cifras(None) == "" and C.texto_cifras({"acierto": None, "tiempo": None, "reutilizacion": None})


# -- Texto en llano -------------------------------------------------------------


def test_texto_cifras_en_llano_con_tildes():
    e = _estado()
    h = _hip(e, "inv-a", ahora=0)
    for _ in range(4):
        _run(e, _plan(e, "inv-a", h["id"], direccionEsperada="mayor"), "efecto_detectado")
    _run(e, _plan(e, "inv-a", h["id"], direccionEsperada="mayor"), "sin_efecto_detectable")
    _run(e, _plan(e, "inv-a", h["id"], direccionEsperada=""), "efecto_detectado")
    l1 = _hip(e, "inv-a", ahora=0)
    _experimento(l1, "sube", "refuta")
    A.registrar_decision(e, h, "killer_1", "avanzar", "m", "rosa", 1 * H)
    e["decisiones"].append(P.nueva_decision("inv-a", h["id"], 1, "persona", "aceptada", "m", "Investigadora", 3 * H))
    res = C.resumen_cifras(e, "inv-a", ahora=int(0.5 * H))
    lineas = res["texto"].split("\n")
    assert lineas[0].startswith("De 6 predicciones prerregistradas con dirección, 4 salieron como se dijo (4 de 5 en análisis in silico; 0 de 1 en el laboratorio).")
    assert lineas[0].endswith(" Aparte queda 1 caso sin dirección declarada, que no entra en la cuenta.")
    assert lineas[1].startswith("Desde que nace una hipótesis hasta su primera decisión de cada etapa pasan 2,0 horas de mediana (el valor del medio) y 3,0 horas en el 90 % de los casos, sobre 2 decisiones (killer 1: 1,0 horas; persona: 3,0 horas).")
    assert "1 hipótesis viva lleva 30 minutos de mediana sin ninguna decisión" in lineas[1]
    assert lineas[2] == "Esta investigación no heredó hechos de otra, así que la reutilización no aplica."
    assert res["glosario"]["prerregistro"].startswith("lo que ROSA2018 deja por escrito")
    # Singulares y días.
    e2 = _estado("inv-s")
    hs = _hip(e2, "inv-s", ahora=0)
    _run(e2, _plan(e2, "inv-s", hs["id"], direccionEsperada="mayor"), "efecto_detectado")
    e2["decisiones"].append(P.nueva_decision("inv-s", hs["id"], 1, "persona", "aceptada", "m", "I", 72 * H))
    texto = C.texto_cifras(C.resumen_cifras(e2, "inv-s", ahora=80 * H))
    assert "De 1 predicción prerregistrada con dirección, 1 salió como se dijo." in texto
    assert "pasan 3,0 días de mediana" in texto and "sobre 1 decisión" in texto
    # Reutilización con herencia, en singular y plural.
    e3 = _estado("inv-o")
    _hecho(e3, "inv-o", "he-1", afirmaciones=["af-1"])
    _hecho(e3, "inv-o", "he-2")
    A.crear_investigacion(e3, {"titulo": "D", "objetivo": "O", "condicionParada": "1", "heredarModeloDe": "inv-o"}, 0, id_="inv-d")
    _hip(e3, "inv-d", afirmaciones=[{"texto": "t", "cita": "c", "veredicto": "sostenida", "motivo": "", "entidadDistinta": False, "tipo": "literatura", "trayectoria": None, "afirmacionId": "af-1"}])
    texto3 = C.texto_cifras(C.resumen_cifras(e3, "inv-d", ahora=H))
    assert "De 2 hechos heredados de otra investigación, 1 se usó en alguna hipótesis de esta (1 hipótesis con herencia)." in texto3
    for palabra in ("dirección", "hipótesis", "decisión", "investigación", "análisis"):
        assert palabra in res["texto"] + texto3


# -- Adversariales: lo que rompió la primera versión y no debe volver a romper ---


def test_fechas_infinitas_nan_y_ahora_no_numerico_no_rompen():
    e = _estado()
    e["hipotesis"].append(P.nueva_hipotesis("inv-a", 1, float("inf")))  # int(inf) lanzaba OverflowError
    h = _hip(e, "inv-a", ahora=0)
    e["decisiones"].append({"hipotesisId": h["id"], "etapa": "killer_1", "fecha": float("nan")})
    t = C.tiempo_hasta_decision(e, "inv-a", ahora=10 * H)
    assert t["sinFechaCreacion"] == 1 and t["decisionesSinFecha"] == 1 and t["casos"] == 0
    # `ahora` que no es un número: se usa el reloj, no se pierden las abiertas en silencio.
    assert C.tiempo_hasta_decision(e, "inv-a", ahora="abc")["abiertasSinDecision"] == 1
    assert C.resumen_cifras(e, "inv-a", ahora="abc")["fecha"] > 0
    # Estado que no es un diccionario o vacío: las tres cifras con None, sin excepción.
    for vacio in (None, {}, {"hipotesis": None, "hechos": "basura", "decisiones": {"a": 1}}):
        res = C.resumen_cifras(vacio, "inv-a", ahora=0)
        assert res["acierto"]["tasa"] is None and res["tiempo"]["medianaHoras"] is None and res["reutilizacion"]["tasa"] is None
        assert "no se puede medir" in res["texto"]


def test_mayusculas_en_valores_del_registro_se_leen_igual():
    e = _estado()
    h = _hip(e, "inv-a", conclusion={"certeza": "Moderada"})
    plan = _plan(e, "inv-a", h["id"], direccionEsperada="mayor", tipo="Confirmatorio")
    _run(e, plan, "Efecto_Detectado", veredicto="Valido")  # antes: plan fuera como "sin ejecución válida"
    plan2 = _plan(e, "inv-a", h["id"], direccionEsperada="mayor", tipo="Exploratorio")
    _run(e, plan2, "efecto_detectado")
    _experimento(h, "sube", "Confirma")  # antes: "veredicto desconocido"
    r = C.acierto_prerregistrado(e, "inv-a")
    assert r["excluidos"]["planesSinEjecucionValida"] == 0
    assert [c["clase"] for c in r["detalle"]] == ["acierto", "sin_direccion", "acierto"]
    assert r["detalle"][0]["resultado"] == "efecto_detectado" and r["detalle"][2]["resultado"] == "confirma"
    assert r["porNivel"] == {"moderada": {"casos": 2, "aciertos": 2}}
    # Etapa y estado con mayúsculas en tiempo y reutilización.
    e["decisiones"].append(P.nueva_decision("inv-a", h["id"], 1, "Killer_1", "avanzar", "m", "rosa", 2 * H))
    e["decisiones"].append(P.nueva_decision("inv-a", h["id"], 1, "killer_1", "avanzar", "m", "rosa", 3 * H))
    t = C.tiempo_hasta_decision(e, "inv-a", ahora=5 * H)
    assert t["porEtapa"] == {"killer_1": {"casos": 1, "medianaHoras": 2.0}}
    hd = _hip(e, "inv-a", estado="Descartada")
    assert hd["id"] not in {d["hipotesisId"] for d in C.tiempo_hasta_decision(e, "inv-a", ahora=5 * H)["detalle"]}
    assert C.tiempo_hasta_decision(e, "inv-a", ahora=5 * H)["abiertasSinDecision"] == 0


def test_prediccion_de_ausencia_de_efecto_no_cuenta_como_acierto():
    e = _estado()
    h = _hip(e, "inv-a")
    casos = [
        ("sin diferencia entre grupos", "efecto_detectado", "fallo"),
        ("No difference between AD and controls", "sin_efecto_detectable", "no_evaluable"),
        ("GFAP no difiere entre grupos", "sin_efecto_detectable", "no_evaluable"),
        ("no hay asociación", "no_evaluable", "no_evaluable"),
        ("igual o mayor en EA", "efecto_detectado", "acierto"),  # lleva sentido: predice efecto
        ("no menor que en controles", "efecto_detectado", "acierto"),
        ("higher GFAP in AD", "sin_efecto_detectable", "fallo"),
    ]
    for direccion, estado, _ in casos:
        _run(e, _plan(e, "inv-a", h["id"], direccionEsperada=direccion), estado)
    r = C.acierto_prerregistrado(e, "inv-a")
    assert [c["clase"] for c in r["detalle"]] == [c for _, _, c in casos]
    assert r["conDireccion"] == 4 and r["aciertos"] == 2 and r["tasa"] == 0.5 and r["noEvaluables"] == 3
    assert "ausencia de efecto" in r["detalle"][0]["motivo"] and "equivalencia" in r["detalle"][1]["motivo"]
    assert "ausencia" in C.REGLA_ACIERTO
    assert C.predice_ausencia_de_efecto("") is False and C.predice_ausencia_de_efecto("mayor") is False
    assert C.predice_ausencia_de_efecto("Sin efecto") and C.predice_ausencia_de_efecto("null effect") and C.predice_ausencia_de_efecto("iguales")


def test_reutilizacion_es_lineal_y_da_lo_mismo_que_la_regla_por_pares():
    import time

    e = _estado("inv-o")
    n = 1500
    for i in range(n):
        _hecho(e, "inv-o", f"he-{i}", fuente_id=f"f-{i}", referencia=f"Ref {i}", afirmaciones=[f"af-{i}"])
    assert A.crear_investigacion(e, {"titulo": "D", "objetivo": "O", "condicionParada": "1", "heredarModeloDe": "inv-o"}, 0, id_="inv-d") == "inv-d"
    for j in range(150):
        h = _hip(e, "inv-d", afirmaciones=[{"afirmacionId": f"af-{(j * 11 + k) % n}"} for k in range(5)], estado="descartada" if j % 5 == 0 else "propuesta")
        h["procedencia"]["registro"] = [f"iteración {k}: nace del hecho he-{(j * 7 + k) % n} y de he-{(j * 7 + k) % n}-inv-d" for k in range(20)]
        h["procedencia"]["fuentes"] = [P.nueva_fuente(id=f"f-{(j * 13 + k) % n}", referencia=f"Ref  {(j * 17 + k) % n}") for k in range(5)]
    t0 = time.perf_counter()
    r = C.reutilizacion_heredada(e, "inv-d")
    assert time.perf_counter() - t0 < 3.0  # la versión por pares tardaba decenas de segundos
    assert r["hechosHeredados"] == n and 0 < r["usados"] < n
    # Misma respuesta que la regla escrita por pares, hecho a hecho.
    hips = [h for h in e["hipotesis"] if h["investigacionId"] == "inv-d"]
    for d in r["detalle"][:200]:
        x = next(x for x in e["hechos"] if x["id"] == d["hechoId"])
        esperado = []
        for h in hips:
            viva = h["estado"] != "descartada"
            af = {a["afirmacionId"] for a in h["afirmaciones"]}
            fu = {f["id"] for f in h["procedencia"]["fuentes"]}
            refs = {C._referencia_normalizada(f["referencia"]) for f in h["procedencia"]["fuentes"]}
            texto = "\n".join(h["procedencia"]["registro"])
            if (viva and (set(x["afirmacionIds"]) & af or {p["fuenteId"] for p in x["procedencia"]} & fu or {C._referencia_normalizada(p["referencia"]) for p in x["procedencia"]} & refs)) or (x["estado"] == "sabido" and (C._nombrado_en(texto, x["id"]) or C._nombrado_en(texto, x["id"][: -len("-inv-d")]))):
                esperado.append(h["id"])
        assert d["usadoPor"] == esperado


def test_reutilizacion_ids_con_otros_caracteres_espacios_y_tema_no_texto():
    e = _estado("inv-o")
    x1 = _hecho(e, "inv-o", "he.1", afirmaciones=[])  # id con punto: la tokenización no vale, cae a la regex
    x1["tema"] = {"raro": True}  # tema antiguo que no es texto: no se comparte la referencia
    _hecho(e, "inv-o", "he-2", afirmaciones=["af-2 "])  # espacio de más en el id de la afirmación
    _hecho(e, "inv-o", "he-3", fuente_id=" f-3")
    A.crear_investigacion(e, {"titulo": "D", "objetivo": "O", "condicionParada": "1", "heredarModeloDe": "inv-o"}, 0, id_="inv-d")
    ha = _hip(e, "inv-d", afirmaciones={"no": "es lista"})  # afirmaciones antiguas que no son lista
    ha["procedencia"]["registro"] = "nace del hecho he.1 y de he.10"  # registro antiguo como texto, no lista
    hb = _hip(e, "inv-d", afirmaciones=[{"afirmacionId": "af-2"}])
    hb["procedencia"]["fuentes"] = [P.nueva_fuente(id="f-3 ", referencia="")]
    hb["procedencia"]["registro"] = ["viene de he.1"]
    r = C.reutilizacion_heredada(e, "inv-d")
    por_id = {d["hechoId"]: d for d in r["detalle"]}
    assert por_id["he.1-inv-d"]["usadoPor"] == [hb["id"]] and por_id["he.1-inv-d"]["tema"] is None
    assert por_id["he-2-inv-d"]["usadoPor"] == [hb["id"]] and por_id["he-3-inv-d"]["usadoPor"] == [hb["id"]]
    assert r["usados"] == 3 and r["hipotesisConHerencia"] == 1
    import json

    json.dumps(r)  # todo serializable, sin conjuntos ni referencias al estado


def test_por_nivel_en_orden_grade_y_decision_de_otra_investigacion_no_cuenta():
    e = _estado()
    for nivel in ("alta", "muy_baja", "moderada", "baja"):
        h = _hip(e, "inv-a", conclusion={"certeza": nivel})
        _experimento(h, "sube", "confirma")
    assert list(C.acierto_prerregistrado(e, "inv-a")["porNivel"]) == ["muy_baja", "baja", "moderada", "alta"]
    assert A.crear_investigacion(e, {"titulo": "B", "objetivo": "O", "condicionParada": "1"}, 0, id_="inv-b") == "inv-b"
    h = _hip(e, "inv-a", ahora=0)
    e["decisiones"].append(P.nueva_decision("inv-b", h["id"], 1, "killer_1", "avanzar", "m", "rosa", 5 * H))  # registro corrupto
    e["decisiones"].append({"hipotesisId": h["id"], "etapa": "killer_1", "fecha": 7 * H})  # antiguo, sin investigacionId: vale
    t = C.tiempo_hasta_decision(e, "inv-a", ahora=10 * H)
    assert t["casos"] == 1 and t["detalle"][0]["horas"] == 7.0


def test_horas_en_llano_redondeos_y_cifras_rotas_en_el_texto():
    assert C._horas_txt(0.999) == "1,0 horas" and C._horas_txt(0.5) == "30 minutos" and C._horas_txt(0) == "0 minutos"
    assert C._horas_txt(47.99) == "48,0 horas" and C._horas_txt(48) == "2,0 días" and C._horas_txt(-3) == "0 minutos"
    assert C._horas_txt(None) == "sin dato" and C._horas_txt("7") == "sin dato" and C._horas_txt(float("nan")) == "sin dato" and C._horas_txt(True) == "sin dato"
    # Una cifra que no es un diccionario o con contadores rotos no tumba el texto.
    texto = C.texto_cifras({"acierto": "roto", "tiempo": {"casos": "3", "medianaHoras": None, "porEtapa": "x"}, "reutilizacion": {"hechosHeredados": None}})
    assert texto.count("\n") == 2 and "no se puede medir" in texto and "sobre 3 decisiones" in texto and "no heredó" in texto
    for linea in texto.split("\n"):
        assert "\u2014" not in linea  # sin guiones largos en el texto que lee la persona
