"""El techo de certeza por regla: el juez explica dentro de la caja, no la fija."""
from rosa import certeza as C


def _h(afirmaciones, cohortes=("biocard",)):
    return {"afirmaciones": afirmaciones, "procedencia": {"fuentes": [{"id": f"f{i}", "cohorte": c} for i, c in enumerate(cohortes)]}}


LIT = {"veredicto": "sostenida", "tipo": "dato", "clase": "literatura", "sintetico": False}
LAB = {"veredicto": "sostenida", "tipo": "dato", "clase": "observacion_original", "sintetico": False}
SILICO = {"veredicto": "sostenida", "tipo": "dato", "clase": "derivado", "sintetico": False}
SECO = {"veredicto": "sostenida", "tipo": "dato", "clase": "derivado", "sintetico": True}


def test_sin_afirmaciones_o_solo_sinteticas_es_muy_baja_aunque_el_juez_diga_alta():
    for h in (_h([]), _h([SECO]), _h([{"veredicto": "refutada", "tipo": "dato", "clase": "literatura"}])):
        r = C.acotar("alta", h)
        assert r["certeza"] == "muy_baja" and r["techo"]["acotada"] is True and r["techo"]["certezaDelJuez"] == "alta"


def test_una_cohorte_de_literatura_no_pasa_de_muy_baja_salvo_efecto_grande():
    h = _h([LIT, LIT])
    assert C.acotar("moderada", h)["certeza"] == "muy_baja"
    assert "una sola cohorte" in C.techo(h)[1]
    factores = [{"factor": "efecto_grande", "efecto": "sube", "explicacion": "104 de 120"}]
    assert C.acotar("moderada", h, factores)["certeza"] == "baja"
    assert C.acotar("muy_baja", h, factores)["certeza"] == "muy_baja"  # nunca sube


def test_dos_cohortes_de_literatura_como_mucho_baja():
    h = _h([LIT, LIT], cohortes=("biocard", "adni"))
    assert C.acotar("alta", h)["certeza"] == "baja"
    assert C.acotar("baja", h)["techo"]["acotada"] is False


def test_evidencia_directa_sube_el_techo_a_moderada_y_con_replica_a_alta():
    h = _h([LIT, SILICO], cohortes=("biocard",))
    assert C.acotar("alta", h)["certeza"] == "moderada" and "falta la réplica" in C.techo(h)[1]
    h2 = _h([LIT, LAB], cohortes=("biocard", "a4"))
    assert C.acotar("alta", h2)["certeza"] == "alta" and "resultado de laboratorio" in C.techo(h2)[1]
    # Un análisis en seco (sintético) no es evidencia directa.
    assert C.acotar("alta", _h([LIT, SECO], cohortes=("biocard",)))["certeza"] == "muy_baja"


def test_escalera_dice_que_falta_para_cada_nivel():
    h = _h([LIT])
    e = C.escalera(h, "muy_baja")
    assert [x["a"] for x in e] == ["baja", "moderada", "alta"]
    assert "segunda cohorte independiente" in e[0]["falta"] and "dataset público aprobado" in e[1]["falta"]
    e2 = C.escalera(_h([LIT, LAB], cohortes=("biocard", "a4")), "alta")
    assert e2 == []
    # Con evidencia directa de una sola cohorte, lo que falta para alta es la réplica.
    e3 = C.escalera(_h([LIT, SILICO], cohortes=("biocard",)), "moderada")
    assert len(e3) == 1 and e3[0]["a"] == "alta" and "réplica" in e3[0]["falta"]
    # Con dos cohortes y evidencia directa, lo que falta es consistencia, no otra cohorte.
    e4 = C.escalera(_h([LIT, SILICO], cohortes=("biocard", "adni")), "moderada")
    assert len(e4) == 1 and "consistencia" in e4[0]["falta"]
