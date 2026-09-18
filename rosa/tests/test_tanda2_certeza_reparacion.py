"""Tanda 2, constructor "certeza", segunda pasada (18 de septiembre de 2026):
lo que el adversario devolvió sobre S-06 (a), M-10, M-04 y M-06, un test de
regresión por hallazgo, escritos para fallar sin el arreglo.

F1: la frase plantilla conserva el supuesto contradicho también con dirección
    "sin_evidencia_directa", con las mismas palabras que rosa/bucle/corrida.py.
F2: el recálculo por regla (`reacotar_conclusion`) deja el mismo rastro que el
    cierre: `cambio`, `recalculadaEn`, línea con fecha en el registro y, desde
    `marcar_candidatas`, evento y cambio de creencia cuando una certeza baja; la
    frase de M-06 llega a una conclusión guardada aunque la certeza no se mueva.
F3: el mismo id con dos cohortes declaradas cuenta dos aunque compartan DOI.
F4: para contar fuentes sin cohorte, el id manda y la referencia solo vale
    cuando no hay id (dos ids distintos con la misma referencia son dos).
F5: una certeza anterior irreconocible "pasa", no "sube".
F6 y F7: la clave `sintetico` sin tilde en el docstring; las parciales no se
    llaman sostenidas.

Ningún test llama al gateway ni a la red: todo es regla determinista.
"""

from __future__ import annotations

import copy
import re

from rosa import certeza as C
from rosa import priorizacion as PR

SIN_TILDE = re.compile(r"\b(analisis|replica|revision|hipotesis|afirmacion|poblacion|relacion|mas|pagina|explicacion|introduccion|recalculo|publicacion|imprecision|paso|bajo|subio|conclusion|generacion|regeneracion)\b")


def _fuente(i, cohorte, **k):
    return {"id": f"f{i}", "referencia": f"Ref {i}", "cohorte": cohorte, **k}


def _af(i, relacion=None, veredicto="sostenida", clase="literatura", **k):
    a = {"afirmacionId": f"af-{i}", "texto": f"afirmación {i}", "cita": f"[Ref {i}, pág. {i + 1}]", "veredicto": veredicto, "tipo": "dato", "clase": clase, "sintetico": False, "cohorte": "", **k}
    if relacion is not None:
        a["relacion"] = relacion
    return a


def _h(afirmaciones, fuentes, **k):
    return {"afirmaciones": afirmaciones, "procedencia": {"fuentes": fuentes, "registro": []}, **k}


def _conclusion(**k):
    base = {"certeza": "baja", "hipotesisBreve": "GFAP sube antes que NfL", "direccion": "apoya", "enunciado": "La evidencia sugiere, con limitaciones, que GFAP sube antes que NfL.", "factores": [], "conclusion": "texto del juez", "aFavor": ["a"], "enContra": [], "iteracion": 2, "cambio": None}
    base.update(k)
    return base


def _hipotesis_completa(**k):
    base = {**_h([_af(0, "apoya")], [_fuente(0, "ADNI")]), "id": "h1", "investigacionId": "inv", "titulo": "GFAP sube antes que NfL", "estado": "propuesta", "elo": 1200, "creadaEn": 1, "cluster": "c", "decisionKiller": "avanzar", "experimento": None}
    base.update(k)
    return base


def _estado(*hips):
    return {"hipotesis": list(hips), "investigaciones": [{"id": "inv", "datasets": []}], "planesAnalisis": [], "ejecuciones": [], "artefactos": [], "corridas": [], "iteraciones": [], "eventos": [], "aprendizaje": []}


SUPUESTO = C.MARCA_SUPUESTO_CONTRADICHO


# ---------------------------------------------------------------------------
# F1: el supuesto contradicho sobrevive en "sin evidencia directa"
# ---------------------------------------------------------------------------


def test_f1_la_frase_sin_evidencia_directa_dice_el_supuesto_contradicho_en_sus_dos_formas():
    nada = C.frase_plantilla("sin_evidencia_directa", "muy_baja", "GFAP sube", supuesto_contradicho=True)
    assert nada == "No encontramos evidencia directa sobre si GFAP sube, y un supuesto del que depende está contradicho por las fuentes. Esto no significa que no exista."
    indirecta = C.frase_plantilla("sin_evidencia_directa", "baja", "GFAP sube", supuesto_contradicho=True, indirectas=3)
    assert indirecta.startswith("Solo encontramos evidencia indirecta sobre si GFAP sube: 3 afirmaciones sostenidas o parciales")
    assert SUPUESTO in indirecta and indirecta.endswith("; la certeza es baja. Que no haya evidencia directa no significa que no exista.")
    # Sin supuesto contradicho no se inventa; la marca es la subcadena común a las tres formas.
    for d, n in (("sin_evidencia_directa", None), ("sin_evidencia_directa", 2), ("apoya", None)):
        assert SUPUESTO not in C.frase_plantilla(d, "baja", "GFAP sube", indirectas=n)
        assert SUPUESTO in C.frase_plantilla(d, "baja", "GFAP sube", supuesto_contradicho=True, indirectas=n)
    # Un recuento que no se puede leer vale como cero, no rompe.
    assert C.frase_plantilla("sin_evidencia_directa", "baja", "X", indirectas="tres") == C.frase_plantilla("sin_evidencia_directa", "baja", "X")
    assert C.frase_plantilla("sin_evidencia_directa", "baja", "X", indirectas=-2) == C.frase_plantilla("sin_evidencia_directa", "baja", "X")


def test_f1_la_frase_canonica_es_la_de_corrida_en_todas_las_combinaciones():
    from rosa.bucle import corrida as CO

    distintas = [(d, c, s) for d in ("apoya", "mixta", "en_contra", "sin_evidencia_directa") for c in C.NIVELES for s in (False, True) if CO.frase_plantilla(d, c, "GFAP sube antes que NfL", supuesto_contradicho=s) != C.frase_plantilla(d, c, "GFAP sube antes que NfL", supuesto_contradicho=s)]
    assert distintas == []


def test_f1_reacotar_conserva_el_supuesto_en_una_conclusion_sin_evidencia_directa_que_baja():
    enunciado = C.frase_plantilla("sin_evidencia_directa", "baja", "GFAP sube antes que NfL", supuesto_contradicho=True)
    h = _h([_af(0, "apoya_indirecta")], [_fuente(0, "ADNI")], titulo="GFAP sube antes que NfL", conclusion=_conclusion(direccion="sin_evidencia_directa", enunciado=enunciado))
    r = C.reacotar_conclusion(h, 1000)
    assert r["cambio"] and r["bajo"] and h["conclusion"]["certeza"] == "muy_baja"
    nuevo = h["conclusion"]["enunciado"]
    assert SUPUESTO in nuevo and nuevo.startswith("Solo encontramos evidencia indirecta") and "una afirmación sostenida o parcial" in nuevo
    # La coletilla "aunque un supuesto..." de la dirección "apoya" también se reconoce.
    # (`hipotesisBreve` manda sobre el título, como en el cierre.)
    h2 = _h([_af(0, "apoya")], [_fuente(0, "ADNI")], titulo="T", conclusion=_conclusion(enunciado="La evidencia sugiere, con limitaciones, que GFAP sube antes que NfL, aunque un supuesto del que depende está contradicho por las fuentes."))
    C.reacotar_conclusion(h2, 1000)
    assert h2["conclusion"]["enunciado"] == "La evidencia es muy incierta sobre si GFAP sube antes que NfL, aunque un supuesto del que depende está contradicho por las fuentes."


# ---------------------------------------------------------------------------
# F2: una sola implementación con todo el rastro
# ---------------------------------------------------------------------------


def test_f2_reacotar_deja_cambio_recalculada_en_y_linea_con_fecha_cuando_la_certeza_baja():
    h = _hipotesis_completa(conclusion=_conclusion())
    r = C.reacotar_conclusion(h, 1_700_000_000_000)
    c = h["conclusion"]
    assert r["bajo"] and r["texto"].startswith("bajó de baja a muy baja al recalcular el techo por regla: ")
    assert c["cambio"] == {"de": {"certeza": "baja", "direccion": "apoya", "iteracion": 2}, "motivo": f"Recálculo del techo por regla: {c['techo']['motivo']}"[:300]}
    assert c["recalculadaEn"] == 1_700_000_000_000
    linea = h["procedencia"]["registro"][-1]
    assert linea.startswith("2023-11-14T22:13:20+00:00 la certeza bajó de baja a muy baja al recalcular el techo por regla: ")
    # Lo que escribió el juez y su fecha no se tocan.
    assert c["conclusion"] == "texto del juez" and c["iteracion"] == 2 and c["aFavor"] == ["a"]
    # Segunda pasada: nada cambia, ni una línea más, y `cambio` se conserva tal cual.
    cambio = copy.deepcopy(c["cambio"])
    r2 = C.reacotar_conclusion(h, 1_800_000_000_000)
    assert not r2["cambio"] and not r2["bajo"] and r2["nota"] == "sin cambios al recalcular el techo por regla"
    assert len(h["procedencia"]["registro"]) == 1 and c["cambio"] == cambio and c["recalculadaEn"] == 1_700_000_000_000


def test_f2_subir_no_es_bajada_y_una_certeza_rara_no_da_bajo():
    h = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")], titulo="T", conclusion=_conclusion(certeza="muy_baja", techo={"nivel": "muy_baja", "motivo": "x", "acotada": True, "certezaDelJuez": "baja"}))
    r = C.reacotar_conclusion(h, 5000)
    assert r["cambio"] and not r["bajo"] and r["texto"].startswith("subió de muy baja a baja") and h["conclusion"]["recalculadaEn"] == 5000
    assert h["conclusion"]["cambio"]["de"]["certeza"] == "muy_baja"
    # Sin instante dado, se apunta el actual (milisegundos, no segundos).
    h2 = _hipotesis_completa(conclusion=_conclusion())
    C.reacotar_conclusion(h2)
    assert h2["conclusion"]["recalculadaEn"] > 1_600_000_000_000
    # Un instante que no es número no rompe: vale como ahora.
    h3 = _hipotesis_completa(conclusion=_conclusion())
    C.reacotar_conclusion(h3, "ayer")
    assert isinstance(h3["conclusion"]["recalculadaEn"], int)


def test_f2_marcar_candidatas_da_evento_y_cambio_de_creencia_solo_cuando_una_certeza_baja():
    baja = _hipotesis_completa(id="h1", conclusion=_conclusion())
    sube = _hipotesis_completa(id="h2", afirmaciones=[_af(0, "apoya"), _af(1, "apoya")], conclusion=_conclusion(certeza="muy_baja", techo={"nivel": "muy_baja", "motivo": "x", "acotada": True, "certezaDelJuez": "baja"}))
    sube["procedencia"]["fuentes"] = [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")]
    descartada = _hipotesis_completa(id="h3", estado="descartada", conclusion=_conclusion())
    otra_inv = _hipotesis_completa(id="h4", investigacionId="otra", conclusion=_conclusion())
    e = _estado(baja, sube, descartada, otra_inv)
    e["investigaciones"].append({"id": "otra", "datasets": []})
    PR.marcar_candidatas(e, "inv", 9000)
    eventos = [x for x in e["eventos"] if x["tipo"] == "revision_automatica"]
    assert len(eventos) == 1 and eventos[0]["t"] == 9000 and eventos[0]["investigacionId"] == "inv"
    assert eventos[0]["texto"].startswith("La certeza de «GFAP sube antes que NfL» bajó de baja a muy baja al recalcular el techo por regla: ")
    assert eventos[0]["ruta"] == "#/investigaciones/inv/hipotesis/h1"
    assert len(e["aprendizaje"]) == 1 and e["aprendizaje"][0]["tipo"] == "creencia" and e["aprendizaje"][0]["nivel"] == 1 and e["aprendizaje"][0]["origen"] == "hipotesis:h1"
    # La descartada se recalcula (techo al día) pero no alarma; la de otra investigación no se toca.
    assert descartada["conclusion"]["certeza"] == "muy_baja" and descartada["conclusion"]["recalculadaEn"] == 9000
    assert otra_inv["conclusion"]["certeza"] == "baja" and "recalculadaEn" not in otra_inv["conclusion"]
    assert sube["conclusion"]["certeza"] == "baja"
    # Segunda pasada: nada nuevo.
    PR.marcar_candidatas(e, "inv", 9500)
    assert len([x for x in e["eventos"] if x["tipo"] == "revision_automatica"]) == 1 and len(e["aprendizaje"]) == 1
    # Un estado sin la lista de eventos (a medio construir) no rompe ni inventa la lista.
    e2 = {"hipotesis": [_hipotesis_completa(conclusion=_conclusion())], "investigaciones": [{"id": "inv", "datasets": []}]}
    cambios = PR.reacotar_conclusiones(e2, "inv", 1)
    assert cambios and cambios[0]["bajo"] and cambios[0]["investigacionId"] == "inv" and "eventos" not in e2 and "aprendizaje" not in e2


def test_f2_la_frase_de_m06_llega_a_una_conclusion_guardada_sin_mover_la_certeza():
    # Ya acotada a muy baja por otra ruta, con la frase antigua "No encontramos evidencia
    # directa" y dos apoyos indirectos: la frase se vuelve a generar, sin `cambio` ni evento.
    vieja = C.frase_plantilla("sin_evidencia_directa", "muy_baja", "GFAP sube antes que NfL")
    h = _hipotesis_completa(afirmaciones=[_af(0, "apoya_indirecta"), _af(1, "apoya_indirecta", veredicto="parcial")], conclusion=_conclusion(certeza="muy_baja", direccion="sin_evidencia_directa", enunciado=vieja, techo={"nivel": "muy_baja", "motivo": "m", "acotada": True, "certezaDelJuez": "muy_baja"}))
    e = _estado(h)
    PR.marcar_candidatas(e, "inv", 4000)
    c = h["conclusion"]
    assert c["certeza"] == "muy_baja" and c["cambio"] is None and "recalculadaEn" not in c
    assert c["enunciado"].startswith("Solo encontramos evidencia indirecta sobre si GFAP sube antes que NfL: 2 afirmaciones sostenidas o parciales")
    assert e["eventos"] == [] and e["aprendizaje"] == []
    assert any("la frase de la conclusión se volvió a generar por regla sin mover la certeza" in r for r in h["procedencia"]["registro"])
    n = len(h["procedencia"]["registro"])
    PR.marcar_candidatas(e, "inv", 4500)
    assert len(h["procedencia"]["registro"]) == n, "idempotente"


def test_f2_un_enunciado_que_no_es_plantilla_solo_se_sustituye_si_la_certeza_cambia():
    # Escrito por una persona: la certeza no se mueve, la frase se respeta.
    h = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")], titulo="T", conclusion=_conclusion(enunciado="Lo que escribió la médica.", techo={"nivel": "baja", "motivo": "x", "acotada": False, "certezaDelJuez": "baja"}))
    r = C.reacotar_conclusion(h, 1)
    assert h["conclusion"]["enunciado"] == "Lo que escribió la médica." and not r["enunciadoCambio"]
    # Si la certeza cambia, la frase sigue a la certeza (como en el cierre).
    h2 = _hipotesis_completa(conclusion=_conclusion(enunciado="Lo que escribió la médica."))
    C.reacotar_conclusion(h2, 1)
    assert h2["conclusion"]["enunciado"].startswith("La evidencia es muy incierta sobre si")
    # Sin enunciado y sin cambio de certeza, no se inventa uno.
    h3 = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")], conclusion={"certeza": "baja", "techo": {"nivel": "baja", "motivo": "x", "certezaDelJuez": "baja"}})
    C.reacotar_conclusion(h3, 1)
    assert "enunciado" not in h3["conclusion"]
    assert C.es_frase_plantilla("  La evidencia reunida sostiene que X.") and not C.es_frase_plantilla(None) and not C.es_frase_plantilla("La evidencia, según el juez, ...")


def test_f2_en_el_orden_real_del_cierre_las_dos_rutas_no_se_pisan():
    """corrida.py recalcula primero (`recalcular_conclusiones_por_regla`, que
    delega en `reacotar_conclusion`) y `marcar_candidatas` después: la segunda
    pasada no repite evento, cambio de creencia ni línea de certeza, no toca
    `recalculadaEn` ni `cambio`, y la conclusión queda con la frase de M-06.
    Vale tanto si corrida.py ya escribe la frase con "solo evidencia
    indirecta" como si escribiera la antigua: entonces la segunda pasada la
    pone al día y deja su línea."""
    from rosa.bucle import corrida as CO

    h = _hipotesis_completa(afirmaciones=[_af(0, "apoya_indirecta")], conclusion=_conclusion(direccion="sin_evidencia_directa", enunciado=CO.frase_plantilla("sin_evidencia_directa", "baja", "GFAP sube antes que NfL")))
    e = _estado(h)
    CO.recalcular_conclusiones_por_regla(e, 1000, "inv")
    assert h["conclusion"]["certeza"] == "muy_baja" and len(e["eventos"]) == 1
    PR.marcar_candidatas(e, "inv", 2000)
    assert len(e["eventos"]) == 1 and len(e["aprendizaje"]) == 1
    assert h["conclusion"]["recalculadaEn"] == 1000 and h["conclusion"]["cambio"]["de"]["certeza"] == "baja"
    assert h["conclusion"]["enunciado"].startswith("Solo encontramos evidencia indirecta sobre si GFAP sube antes que NfL: una afirmación sostenida o parcial")
    lineas = h["procedencia"]["registro"]
    assert sum("la certeza bajó" in x for x in lineas) == 1 and sum("se volvió a generar" in x for x in lineas) <= 1
    # Tercera pasada por cualquiera de las dos rutas: nada.
    n = len(lineas)
    assert CO.recalcular_conclusiones_por_regla(e, 3000, "inv") == [] and PR.reacotar_conclusiones(e, "inv", 3500) == []
    assert len(lineas) == n and len(e["eventos"]) == 1


def test_f2_el_techo_nuevo_o_movido_sin_cambio_de_certeza_deja_linea_pero_no_cambio():
    # Conclusión antigua sin techo cuya certeza ya está en el techo: línea "techo calculado", sin `cambio`.
    h = _hipotesis_completa(conclusion=_conclusion(certeza="muy_baja"))
    r = C.reacotar_conclusion(h, 1)
    assert r["cambio"] and not r["bajo"] and "techo GRADE calculado por regla para una conclusión que no lo tenía: muy baja" in r["nota"]
    assert h["conclusion"]["cambio"] is None and "recalculadaEn" not in h["conclusion"] and len(h["procedencia"]["registro"]) == 1
    # El techo sube (llega la segunda cohorte) pero el juez estaba en muy baja: línea del techo, certeza quieta.
    h2 = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")], conclusion=_conclusion(certeza="muy_baja", techo={"nivel": "muy_baja", "motivo": "x", "acotada": False, "certezaDelJuez": "muy_baja"}))
    r2 = C.reacotar_conclusion(h2, 1)
    assert r2["cambio"] and "el techo por regla pasó de muy baja a baja sin mover la certeza" in r2["nota"] and h2["conclusion"]["certeza"] == "muy_baja"
    # Solo cambia el motivo del techo (misma cifra): se apunta como cambio de estado, sin línea.
    h3 = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")], conclusion=_conclusion(techo={"nivel": "baja", "motivo": "motivo viejo", "acotada": False, "certezaDelJuez": "baja"}))
    r3 = C.reacotar_conclusion(h3, 1)
    assert r3["cambio"] and h3["procedencia"]["registro"] == [] and r3["nota"] == "recálculo del techo por regla sin mover la certeza ni la frase"


def test_f2_una_conclusion_antigua_sin_direccion_no_cambia_de_sentido_al_regenerar_la_frase():
    # Sin `direccion` guardada, la frase "No encontramos evidencia directa" seguiría
    # siendo de esa dirección, no pasaría a "La evidencia es muy incierta sobre si".
    h = _hipotesis_completa(afirmaciones=[_af(0, "apoya_indirecta")], conclusion={"certeza": "baja", "hipotesisBreve": "GFAP sube antes que NfL", "enunciado": "No encontramos evidencia directa sobre si GFAP sube antes que NfL. Esto no significa que no exista."})
    C.reacotar_conclusion(h, 1)
    assert h["conclusion"]["enunciado"].startswith("Solo encontramos evidencia indirecta sobre si GFAP sube antes que NfL")
    h2 = _hipotesis_completa(conclusion={"certeza": "baja", "hipotesisBreve": "X", "enunciado": "La evidencia es contradictoria sobre si X; la certeza es baja."})
    C.reacotar_conclusion(h2, 1)
    assert h2["conclusion"]["enunciado"] == "La evidencia es contradictoria sobre si X; la certeza es muy baja."
    h3 = _hipotesis_completa(conclusion={"certeza": "baja", "hipotesisBreve": "X", "enunciado": "La evidencia sugiere, con limitaciones, que no se cumple que X."})
    C.reacotar_conclusion(h3, 1)
    assert h3["conclusion"]["enunciado"] == "La evidencia es muy incierta sobre si X."
    # "La evidencia es muy incierta sobre si" no distingue apoya de en contra: se queda en apoya, como el cierre.
    assert C._direccion_de_plantilla("La evidencia es muy incierta sobre si X.") is None and C._direccion_de_plantilla(None) is None
    # Con `direccion` guardada, manda la guardada.
    h4 = _hipotesis_completa(conclusion={"certeza": "baja", "direccion": "apoya", "hipotesisBreve": "X", "enunciado": "La evidencia es contradictoria sobre si X; la certeza es baja."})
    C.reacotar_conclusion(h4, 1)
    assert h4["conclusion"]["enunciado"] == "La evidencia es muy incierta sobre si X."


def test_f2_delegar_desde_corrida_cumple_el_contrato_de_los_tests_m14_del_cierre():
    """El pendiente para rosa/bucle/corrida.py `recalcular_conclusiones_por_regla`
    es este cuerpo: una llamada a `PR.reacotar_conclusiones` y el mapeo a su
    forma de salida. Se comprueba aquí lo que test_tanda2_cierre.py exige de la
    ruta de corrida.py: `cambio`, `recalculadaEn`, un solo evento con la ruta
    de la ficha, la línea "bajó de baja a muy baja", el cambio de creencia de
    nivel 1, idempotencia, y que la descartada se recalcula sin evento."""

    def recalcular_delegado(e, ahora, investigacion_id=None):
        return [{"id": c["hipotesisId"], "de": c["antes"]["certeza"], "a": c["despues"]["certeza"], "techo": c["despues"]["techo"]} for c in PR.reacotar_conclusiones(e, investigacion_id, ahora)]

    h = _hipotesis_completa(conclusion=_conclusion(iteracion=1))
    h["conclusion"]["fecha"] = 100
    e = _estado(h)
    cambios = recalcular_delegado(e, 5000)
    k = h["conclusion"]
    assert cambios == [{"id": "h1", "de": "baja", "a": "muy_baja", "techo": "muy_baja"}]
    assert k["certeza"] == "muy_baja" and k["techo"]["certezaDelJuez"] == "baja" and k["techo"]["acotada"] is True
    assert k["escalera"][0]["de"] == "muy_baja" and k["escalera"][0]["a"] == "baja"
    assert k["enunciado"].startswith("La evidencia es muy incierta sobre si") and k["cambio"]["de"]["certeza"] == "baja" and k["cambio"]["motivo"].startswith("Recálculo del techo por regla")
    assert k["recalculadaEn"] == 5000 and k["fecha"] == 100 and k["iteracion"] == 1
    assert len(e["eventos"]) == 1 and e["eventos"][0]["tipo"] == "revision_automatica" and "bajó de baja a muy baja al recalcular el techo por regla" in e["eventos"][0]["texto"]
    assert e["eventos"][0]["ruta"] == "#/investigaciones/inv/hipotesis/h1"
    assert any("bajó de baja a muy baja" in r for r in h["procedencia"]["registro"])
    assert e["aprendizaje"][-1]["tipo"] == "creencia" and e["aprendizaje"][-1]["nivel"] == 1
    assert recalcular_delegado(e, 6000) == [] and len(e["eventos"]) == 1
    d = _hipotesis_completa(id="d", estado="descartada", conclusion=_conclusion(certeza="moderada"))
    e["hipotesis"].append(d)
    assert recalcular_delegado(e, 7000)[0]["a"] == "muy_baja" and len(e["eventos"]) == 1
    e["hipotesis"].append({"id": "rara", "investigacionId": "inv", "conclusion": {"certeza": "baja"}, "afirmaciones": "texto", "procedencia": None})
    recalcular_delegado(e, 8000)
    assert recalcular_delegado({"hipotesis": [None, {"conclusion": None}, {"conclusion": {"sin_certeza": 1}}]}, 1) == []


# ---------------------------------------------------------------------------
# F3 y F4: identidades al contar cohortes y fuentes
# ---------------------------------------------------------------------------


def test_f3_el_mismo_id_con_dos_cohortes_cuenta_dos_aunque_compartan_doi():
    af = _af(0, "apoya")
    fs = [{"id": "dup", "referencia": "Ref 0", "cohorte": "ADNI", "doi": "10.1/x", "pmid": "7", "titulo": "Plasma GFAP in preclinical Alzheimer disease"}, {"id": "dup", "referencia": "Ref 0", "cohorte": "BIOCARD", "doi": "10.1/x", "pmid": "7", "titulo": "Plasma GFAP in preclinical Alzheimer disease"}]
    h = _h([af], fs)
    assert C.cohortes_distintas(h) == ["ADNI", "BIOCARD"] and C.fuentes_sin_cohorte(h) == 0 and C.techo(h)[0] == "baja"
    # Con ids distintos, el DOI compartido sí las funde (S-06): el contrato de siempre.
    h2 = _h([_af(0, "apoya"), _af(1, "apoya")], [dict(fs[0], id="a"), dict(fs[1], id="b", referencia="Ref 1")])
    assert C.cohortes_distintas(h2) == ["ADNI"]
    # Una tercera entrada con otro id y el mismo DOI se funde con la primera del id repetido, no con las dos.
    h3 = _h([af, _af(1, "apoya")], fs + [{"id": "otro", "referencia": "Ref 1", "cohorte": "A4", "doi": "10.1/x"}])
    assert C.cohortes_distintas(h3) == ["ADNI", "BIOCARD"]
    # Y sin cohorte en ninguna entrada, el artículo repetido es una sola fuente sin cohorte.
    h4 = _h([af], [dict(fs[0], cohorte=None), dict(fs[1], cohorte="")])
    assert C.fuentes_sin_cohorte(h4) == 1


def test_f4_para_contar_fuentes_el_id_manda_y_la_referencia_solo_vale_sin_id():
    def sin_cohorte(fuentes):
        return C.fuentes_sin_cohorte({"afirmaciones": [], "procedencia": {"fuentes": fuentes}})

    # Dos artículos del mismo primer autor y año, ids distintos: dos fuentes (lo de siempre).
    assert sin_cohorte([{"id": "a", "referencia": "Kim et al., 2025", "cohorte": None}, {"id": "b", "referencia": "Kim et al., 2025", "cohorte": None}]) == 2
    # Sin id, la referencia es la identidad.
    assert sin_cohorte([{"referencia": "Kim et al., 2025", "cohorte": None}, {"referencia": "Kim et al., 2025", "cohorte": None}]) == 1
    # Una con id y otra sin él, misma referencia: dos identidades (la precedencia de HEAD).
    assert sin_cohorte([{"id": "a", "referencia": "Kim et al., 2025", "cohorte": None}, {"referencia": "Kim et al., 2025", "cohorte": None}]) == 2
    # El mismo id dos veces sigue siendo una; y el mismo DOI con ids distintos, una (S-06).
    assert sin_cohorte([{"id": "a", "referencia": "Kim et al., 2025", "cohorte": None}, {"id": "a", "referencia": "Kim et al., 2025", "cohorte": None}]) == 1
    assert sin_cohorte([{"id": "a", "referencia": "Kim et al., 2025", "cohorte": None, "doi": "10.1/k"}, {"id": "b", "referencia": "Kim et al., 2025", "cohorte": None, "doi": "10.1/k"}]) == 1
    # El motivo del techo cuenta lo mismo.
    h = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, None, referencia="Kim et al., 2025"), _fuente(1, None, referencia="Kim et al., 2025")])
    assert "2 fuentes sin cohorte identificada" in C.techo(h)[1]
    # Emparejar no cambia: la cita "[Kim et al., 2025, pág. 3]" sigue emparejando con las dos.
    assert C.fuente_de(h, {"cita": "[Kim et al., 2025, pág. 3]"}) is h["procedencia"]["fuentes"][0]


# ---------------------------------------------------------------------------
# F5, F6 y F7: textos
# ---------------------------------------------------------------------------


def test_f5_una_certeza_anterior_irreconocible_pasa_no_sube_ni_baja():
    h = {"afirmaciones": [], "procedencia": {"registro": []}, "conclusion": {"certeza": "altisima", "direccion": "apoya", "enunciado": "x"}}
    r = C.reacotar_conclusion(h, 1)
    assert r["despues"]["certeza"] == "muy_baja" and not r["bajo"]
    assert r["nota"].startswith("la certeza pasó de altisima a muy baja al recalcular el techo por regla: ") and "sube" not in r["nota"] and "subió" not in r["nota"]
    assert h["conclusion"]["cambio"]["de"]["certeza"] == "altisima"
    # Sin certeza (None) tampoco "sube": pasa de "sin certeza".
    h2 = {"afirmaciones": [], "procedencia": {}, "conclusion": {"certeza": None}}
    assert C.reacotar_conclusion(h2, 1)["nota"].startswith("la certeza pasó de sin certeza a muy baja")


def test_f6_f7_la_clave_sintetico_sin_tilde_y_las_parciales_no_se_llaman_sostenidas():
    doc = C.es_sintetica.__doc__ or ""
    assert "`sintetico`" in doc and "`sintético`" not in doc
    h = _h([_af(0, "apoya_indirecta", veredicto="parcial")], [_fuente(0, "ADNI")])
    frase = C.frase_plantilla("sin_evidencia_directa", "muy_baja", "GFAP sube", indirectas=len(C.apoyos_indirectos(h)))
    assert "una afirmación sostenida o parcial con el mismo patrón" in frase and "una afirmación sostenida con" not in frase
    assert "4 afirmaciones sostenidas o parciales con" in C.frase_plantilla("sin_evidencia_directa", "baja", "X", indirectas=4)


def test_todo_texto_nuevo_lleva_tildes_y_no_tiene_guiones_largos():
    textos = [C.frase_plantilla(d, c, "GFAP sube", supuesto_contradicho=s, indirectas=n) for d in ("sin_evidencia_directa", "apoya", "mixta", "en_contra") for c in C.NIVELES for s in (False, True) for n in (0, 1, 3)]
    casos = [
        _hipotesis_completa(conclusion=_conclusion()),
        _hipotesis_completa(conclusion=_conclusion(certeza="muy_baja")),
        _hipotesis_completa(afirmaciones=[_af(0, "apoya_indirecta")], conclusion=_conclusion(certeza="muy_baja", direccion="sin_evidencia_directa", enunciado=C.frase_plantilla("sin_evidencia_directa", "muy_baja", "GFAP sube antes que NfL"), techo={"nivel": "muy_baja", "motivo": "m", "certezaDelJuez": "muy_baja"})),
        {"afirmaciones": [], "procedencia": {"registro": []}, "conclusion": {"certeza": "altisima"}},
    ]
    for h in casos:
        r = C.reacotar_conclusion(h, 1)
        textos.extend([r["nota"], r["texto"]])
        textos.extend(str(x) for x in h["procedencia"]["registro"])
        if h["conclusion"].get("cambio"):
            textos.append(h["conclusion"]["cambio"]["motivo"])
    e = _estado(_hipotesis_completa(conclusion=_conclusion()))
    PR.marcar_candidatas(e, "inv", 1)
    textos.extend(x["texto"] for x in e["eventos"])
    textos.extend(x["descripcion"] for x in e["aprendizaje"])
    for t in textos:
        assert "\u2014" not in t, t
        assert not SIN_TILDE.search(t), t
