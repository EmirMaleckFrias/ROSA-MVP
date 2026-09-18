"""Lo que el revisor de registro atrapa por regla desde el 15 de septiembre de
2026 (tras el análisis de la corrida sobre biomarcadores y beneficio clínico):
recuentos del texto que no cuadran con el registro, hipótesis descartadas por
el Killer presentadas como vivas, y los nombres propios del objetivo que
tienen que buscarse por nombre exacto."""
from rosa import revisor_registro as RR
from rosa.bucle import contexto as T
from rosa.bucle import pasos as PS


def _estado():
    it = {"numero": 1, "empezadaEn": 1000, "plan": [{"estado": "hecho"}, {"estado": "hecho"}, {"estado": "pendiente"}], "pistas": [{"estado": "hecha"}, {"estado": "fallida"}]}
    hechos = [{"investigacionId": "inv", "actualizadoEn": 500 + i, "enunciado": f"hecho {i}"} for i in range(29)] + [{"investigacionId": "inv", "actualizadoEn": 2000, "enunciado": f"nuevo {i}"} for i in range(11)]
    afs = [{"iteracion": 1, "veredicto": "sostenida"}] * 30 + [{"iteracion": 1, "veredicto": "parcial"}] * 5 + [{"iteracion": 0, "veredicto": "sostenida"}] * 5
    consultas = [{"base": "PubMed", "iteracion": 1}] * 3 + [{"base": "Exa (búsqueda semántica de publicaciones)", "iteracion": 1}] * 5
    corrida = {"_afirmaciones": afs, "busqueda": {"consultas": consultas, "identificados": 120, "cribados": 8, "textoCompleto": 3, "traidos": 20}, "_fuentes": {f"f{i}": {"relevancia": 7} for i in range(8)}}
    e = {"hechos": hechos, "hipotesis": [{"investigacionId": "inv", "iteracion": 1, "titulo": "El acoplamiento de GFAP con NfL distingue respuesta", "decisionKiller": "descartar_en_contexto", "estado": "propuesta"}], "ejecuciones": [], "investigaciones": [{"id": "inv", "datasets": []}]}
    return e, it, corrida


def test_recuentos_del_texto_lee_n_y_n_de_m():
    r = RR.recuentos_del_texto("ROSA2018 leyó 59 hechos, 40 de 59 afirmaciones sostenidas, 2 búsquedas de Exa, 11 fuentes nuevas y 3 hipótesis.")
    assert (59, "hechos", "59 hechos") in r
    assert (40, "afirmaciones", "40 de 59 afirmaciones") in r and (59, "afirmaciones", "40 de 59 afirmaciones") in r
    assert (2, "consultas", "2 búsquedas") in r and (11, "fuentes", "11 fuentes") in r and (3, "hipotesis", "3 hipótesis") in r


def test_recuentos_del_registro_y_contradicciones_por_regla():
    e, it, corrida = _estado()
    rec = RR.recuentos_del_registro(e, "inv", it, corrida)
    assert rec["hechos"] == {40, 11} and rec["afirmaciones"] == {40, 35, 30, 5} and rec["consultas"] == {8, 3, 5}
    corpus = RR.corpus_del_registro(e, "inv", it, corrida)
    texto = "ROSA2018 incorporó 59 hechos, verificó 30 afirmaciones sostenidas y 8 hechos nuevos; hizo 2 búsquedas en Exa y trajo 20 fuentes."
    hz = RR.comprobaciones_deterministas(texto, corpus, it, 0)
    detalle = " ".join(h["detalle"] for h in hz if h["clase"] == "contradiccion_con_registro" and "Recuentos" in h["detalle"])
    assert "«59 hechos»" in detalle and "«8 hechos" in detalle and "«2 búsquedas»" in detalle
    assert "30 afirmaciones" not in detalle and "20 fuentes" not in detalle
    bien = "ROSA2018 incorporó 11 hechos nuevos (40 en total), verificó 35 afirmaciones (30 sostenidas y 5 parciales) con 8 consultas, 5 de ellas en Exa."
    assert not [h for h in RR.comprobaciones_deterministas(bien, corpus, it, 0) if "Recuentos" in h["detalle"]]


def test_hipotesis_descartada_por_el_killer_no_puede_salir_como_viva():
    e, it, corrida = _estado()
    corpus = RR.corpus_del_registro(e, "inv", it, corrida)
    hips = e["hipotesis"]
    optimista = "ROSA2018 propone que el acoplamiento de GFAP con NfL distingue respuesta informativa; queda pendiente de validación empírica."
    hz = RR.comprobaciones_deterministas(optimista, corpus, it, 0, hipotesis=hips)
    assert any(h["gravedad"] == "alta" and "descartar_en_contexto" in h["detalle"] for h in hz)
    honesto = "La hipótesis «El acoplamiento de GFAP con NfL distingue respuesta» fue descartada en contexto por el Killer: le falta el ensayo."
    assert not [h for h in RR.comprobaciones_deterministas(honesto, corpus, it, 0, hipotesis=hips) if "Killer" in h["detalle"]]


def test_nombres_propios_y_consultas_por_nombre():
    objetivo = ("Comparar los ensayos recientes en los que la diana se movió y la clínica no (semaglutida en evoke/evoke+, posdinemab, AL002 en INVOKE-2) "
                "con aquellos en los que ambos se movieron (lecanemab en Clarity AD, donanemab en TRAILBLAZER-ALZ 2), con GFAP y NfL como biomarcadores en Alzheimer.")
    nombres = T.nombres_propios(objetivo)
    for esperado in ("AL002", "INVOKE-2", "TRAILBLAZER-ALZ 2", "evoke+", "evoke", "posdinemab", "lecanemab", "donanemab"):
        assert esperado in nombres, (esperado, nombres)
    assert "INVOKE" not in nombres and "GFAP" not in nombres and "Alzheimer" not in nombres
    plan = [{"consulta": "lecanemab AND Clarity AD"}, {"consulta": "semaglutide AND evoke"}]
    extra = PS.consultas_por_nombre(nombres, plan, ['"posdinemab"'])
    assert [q["consulta"] for q in extra] == ['"AL002"', '"INVOKE-2"', '"TRAILBLAZER-ALZ 2"', '"evoke+"']
    assert all(q["base"] == "europepmc" and q["_por_nombre"] for q in extra)
