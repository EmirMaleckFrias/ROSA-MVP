"""Rigor del evidence worker: puerta de publicación, semillas y estabilidad,
interpretación por regla, intención completa del análisis, regresión entre
versiones, criterios antes de prerregistrar, predicción antes de buscar."""
from rosa import ejecucion as X
from rosa import priorizacion as PR
from rosa.bucle import analisis as AN
from rosa.bucle import pasos as PASOS
from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.evaluacion import panel_auditor


def test_puerta_de_publicacion_por_hallazgo_grave_abierto():
    h = {"id": "h1", "investigacionId": "inv", "afirmaciones": [{"veredicto": "sostenida"}], "experimento": {"confirma": "x", "refuta": "y"}, "estado": "propuesta", "decisionKiller": "avanzar", "procedencia": {"fuentes": []}, "dossierArtefactoId": None}
    e = {"investigaciones": [{"id": "inv", "datasets": []}], "corridas": [{"id": "cor", "investigacionId": "inv"}], "iteraciones": [{"id": "it1", "corridaId": "cor", "terminadaEn": 100, "revisionRegistro": {"hallazgos": [{"estado": "abierto", "gravedad": "media"}]}}], "artefactos": [], "ejecuciones": [], "planesAnalisis": []}
    assert "revision_registro_abierta" not in PR.bloqueos_de(e, h)  # gravedad media no retiene
    e["iteraciones"].append({"id": "it2", "corridaId": "cor", "terminadaEn": 200, "revisionRegistro": {"hallazgos": [{"estado": "abierto", "gravedad": "alta"}]}})
    assert "revision_registro_abierta" in PR.bloqueos_de(e, h)
    e["iteraciones"][-1]["revisionRegistro"]["hallazgos"][0]["estado"] = "atendido"
    assert "revision_registro_abierta" not in PR.bloqueos_de(e, h)
    # Por el dossier de la hipótesis.
    h["dossierArtefactoId"] = "art1"
    e["artefactos"].append({"id": "art1", "versiones": [{"n": 1, "procedencia": {"revision": {"hallazgos": [{"estado": "abierto", "gravedad": "alta"}]}}}]})
    assert PR.revision_registro_abierta(e, h) is True


def test_estabilidad_entre_semillas_e_interpretacion_por_regla():
    plan = {"alpha": 0.05}
    res = X.Resultado(estado="completado", runtime="docker", resultados={"p_valor": "0.03"}, control={"p_valor": "0.5"})
    assert X.estabilidad_entre_semillas(plan, res, [])["resultado"] == "no_comprobable"
    estable = [{"semilla": 1, "estado": "completado", "resultados": {"p_valor": "0.02"}}]
    assert X.estabilidad_entre_semillas(plan, res, estable)["resultado"] == "pasa"
    inestable = [{"semilla": 1, "estado": "completado", "resultados": {"p_valor": "0.3"}}]
    assert X.estabilidad_entre_semillas(plan, res, inestable)["resultado"] == "falla"
    # La comprobación entra en la lista determinista.
    todas = {c["comprobacion"] for c in X.comprobaciones_deterministas("np.random.seed(1)", {"variables": []}, res, estable)}
    assert "estabilidad_semillas" in todas
    # Interpretación por regla.
    assert AN.interpretacion_por_regla(plan, res, estable)["estado"] == "efecto_detectado"
    assert AN.interpretacion_por_regla(plan, res, inestable)["estado"] == "sin_efecto_detectable"
    assert AN.interpretacion_por_regla(plan, X.Resultado(estado="completado", runtime="docker", resultados={"p_valor": "0.2"}), [])["estado"] == "sin_efecto_detectable"
    assert AN.interpretacion_por_regla(plan, X.Resultado(estado="completado", runtime="docker", resultados={"p_valor": "0.01"}, control={"p_valor": "0.01"}), [])["estado"] == "no_evaluable"
    assert AN.interpretacion_por_regla(plan, X.Resultado(estado="completado", runtime="docker", resultados={"p_valor": "0.01"}, no_evaluable="n < 5"), [])["estado"] == "no_evaluable"
    assert AN.interpretacion_por_regla(plan, X.Resultado(estado="completado", runtime="docker", resultados={"coef": "0.4"}), []) is None  # sin p, decide el juez


def test_intencion_completa_y_hash_del_plan_estable():
    viejo = P.nuevo_plan_analisis("inv", "h1", "ds", 1000, prueba="t de Student", variables=["gfap (dependiente)"])
    viejo["hashPlan"] = P.hash_plan(viejo)
    con_intencion = dict(viejo, siConfirma="subir la certeza", siRefuta="bajar la dirección", siNoEvaluable="pedir otro dataset", planPadre="plan-0", cambioRespectoAlPadre="otro dataset")
    assert P.hash_plan(con_intencion) != viejo["hashPlan"]  # la intención es parte del plan
    assert P.hash_plan(dict(viejo, siConfirma="", planPadre=None)) == viejo["hashPlan"]  # vacíos no cambian los hashes ya congelados
    assert AN.cambio_respecto_al_padre(None, "ds2", "t", "OASIS") == ""
    assert AN.cambio_respecto_al_padre({"datasetId": "ds", "prueba": "t de Student"}, "ds2", "t de Student", "OASIS").startswith("otro dataset (OASIS): réplica")
    assert "variante del método" in AN.cambio_respecto_al_padre({"datasetId": "ds", "prueba": "t de Student"}, "ds", "Mann-Whitney", "")
    assert AN.cambio_respecto_al_padre({"datasetId": "ds", "prueba": "t"}, "ds", "t", "") == "misma receta sobre el mismo dataset (repetición)"


def test_regresion_de_comprobaciones_entre_versiones():
    e = {"decisiones": [{"hipotesisId": "h1", "etapa": "killer_1", "version": 1, "fecha": 10, "comprobaciones": [{"comprobacion": "fidelidad_evidencia", "resultado": "pasa"}, {"comprobacion": "falsabilidad", "resultado": "falla"}]}]}
    h = {"id": "h1", "version": 2}
    ahora = [{"comprobacion": "fidelidad_evidencia", "resultado": "falla", "detalle": "cita rota"}, {"comprobacion": "falsabilidad", "resultado": "pasa"}]
    r = PASOS.regresion_de_comprobaciones(e, h, ahora)
    assert [x["comprobacion"] for x in r] == ["fidelidad_evidencia"] and r[0]["antes"] == "pasa"
    assert PASOS.regresion_de_comprobaciones(e, {"id": "h1", "version": 1}, ahora) == []
    assert PASOS.regresion_de_comprobaciones(e, {"id": "h2", "version": 2}, ahora) == []


def test_no_se_prerregistra_sin_criterios_y_los_pasos_llevan_prediccion():
    h = {"id": "h1", "investigacionId": "inv", "titulo": "t", "enunciado": "e", "mecanismo": "m", "iteracion": 1, "version": 1, "comprobacion": {"biomarcador": "GFAP", "cohorte": "c", "diseno": "d"},
         "experimento": {"confirma": "", "refuta": "", "ensayo": "", "protocolo": "p", "costeEstimado": "bajo", "analisisPedido": "", "decisionQueCambia": "", "estado": "propuesto"}, "procedencia": {"registro": []}}
    e = {"hipotesis": [h], "corridas": [], "artefactos": [], "eventos": [], "investigaciones": [{"id": "inv"}]}
    assert A.asignar_experimento(e, "h1", "Lab X", 1000) is False
    assert e["eventos"][-1]["tipo"] == "incidencia" and "faltan el criterio" in e["eventos"][-1]["texto"]
    # Con criterios separados o con el esquema anterior (criterios dentro del ensayo) sí se prerregistra.
    e["hipotesis"][0]["experimento"].update(confirma="sube", refuta="baja")
    e["hipotesis"][0]["procedencia"]["registro"] = []
    assert A.asignar_experimento(e, "h1", "Lab X", 1000) is True
    paso = P.nuevo_paso("Buscar en ADNI", "detalle", 20, espera="el mismo orden de alteración", si_no_aparece="la hipótesis sigue en una cohorte")
    assert paso["espera"] == "el mismo orden de alteración" and paso["siNoAparece"] == "la hipótesis sigue en una cohorte"
    assert P.nuevo_paso("x", "y")["espera"] == ""


def test_panel_del_auditor_detecta_todos_los_fallos_plantados_sin_falsos_positivos():
    r = panel_auditor.correr()
    fallidos = [c for c in r["casos"] if not c["detectado"]]
    assert fallidos == [], fallidos
    assert r["deteccion"] == 1.0 and r["falsosPositivosEnLimpio"] == []
