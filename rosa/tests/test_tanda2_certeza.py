"""Tanda 2 de la revisión del 17 de septiembre de 2026, constructor "certeza":
un test de regresión por arreglo, escritos para fallar sin el cambio.

S-06 (a): dos entradas del mismo artículo (mismo DOI, PMID, NCT o título con
ids distintos) aportan una sola cohorte al techo.
M-10: el recálculo por regla, sin juez, de las conclusiones ya escritas
(`reacotar_conclusion`, y `marcar_candidatas` lo corre al cerrar).
M-04: `acotar` deja la lista de cohortes que contó en el techo.
M-06: la escalera nombra los factores reales del juez; la frase plantilla
distingue "nada" de "solo evidencia indirecta"; el motivo del techo se lo
dice al juez.
"""

from __future__ import annotations

import copy
import re
from types import SimpleNamespace

from rosa import certeza as C
from rosa import priorizacion as PR

SIN_TILDE = re.compile(r"\b(analisis|replica|revision|hipotesis|afirmacion|afirmaciones sostenidas en otra poblacion|poblacion|relacion|senalo|senaló|mas|pagina|explicacion|introduccion|recalculo|publicacion|imprecision)\b")


def _fuente(i, cohorte, **k):
    return {"id": f"f{i}", "referencia": f"Ref {i}", "cohorte": cohorte, **k}


def _af(i, relacion=None, veredicto="sostenida", clase="literatura", **k):
    a = {"afirmacionId": f"af-{i}", "texto": f"afirmación {i}", "cita": f"[Ref {i}, pág. {i + 1}]", "veredicto": veredicto, "tipo": "dato", "clase": clase, "sintetico": False, "cohorte": "", **k}
    if relacion is not None:
        a["relacion"] = relacion
    return a


def _h(afirmaciones, fuentes, **k):
    return {"afirmaciones": afirmaciones, "procedencia": {"fuentes": fuentes, "registro": []}, **k}


# ---------------------------------------------------------------------------
# S-06 (a): el mismo artículo registrado dos veces aporta una sola cohorte
# ---------------------------------------------------------------------------


def test_raket_dos_veces_con_el_mismo_doi_es_una_cohorte_y_el_techo_baja():
    # El caso real de hip-mu2tskgf-2920: Johansson (introducción, no aporta cohorte),
    # Raket 2026 como "TRAILBLAZER-ALZ (NCT...)" y otra vez como "donanemab trial".
    johansson = _fuente(0, "Swedish familial Alzheimer's disease study")
    raket_a = _fuente(1, "TRAILBLAZER-ALZ (NCT03367403) y TRAILBLAZER-ALZ 2 (NCT04437511)", doi="10.1001/jama.2026.1")
    raket_b = _fuente(2, "donanemab trial", doi="https://doi.org/10.1001/JAMA.2026.1.")
    afs = [_af(0, cita="[Ref 0, sección Introduction]"), _af(1, "apoya"), _af(2, "apoya")]
    con_doi = _h(afs, [johansson, raket_a, raket_b])
    assert C.cohortes_distintas(con_doi) == ["TRAILBLAZER-ALZ"]
    assert C.techo(con_doi)[0] == "muy_baja"
    # Sin el DOI no hay forma de saber que son el mismo artículo: dos cohortes, baja.
    sin_doi = _h(afs, [johansson, dict(raket_a, doi=None), dict(raket_b, doi=None)])
    assert C.cohortes_distintas(sin_doi) == ["TRAILBLAZER-ALZ", "donanemab trial"]
    assert C.techo(sin_doi)[0] == "baja"
    # La fusión no muta la entrada.
    copia = copy.deepcopy(con_doi)
    C.cohortes_distintas(con_doi)
    assert con_doi == copia


def test_las_claves_bibliograficas_funden_por_doi_pmid_nct_o_titulo_largo():
    assert C.claves_de_fuente({"doi": "https://dx.doi.org/10.1/ABC."}) == C.claves_de_fuente({"doi": "doi: 10.1/abc"}) == {"doi:10.1/abc"}
    assert C.claves_de_fuente({"pmid": 123, "nct": "nct04437511"}) == {"pmid:123", "nct:nct04437511"}
    assert C.claves_de_fuente({"titulo": "Plasma GFAP in preclinical Alzheimer disease"}) == C.claves_de_fuente({"titulo": "Plasma GFAP in Preclinical Alzheimer Disease!"})
    # Un título corto no identifica; lo que no es texto ni número no da clave; nunca la cadena vacía.
    assert C.claves_de_fuente({"titulo": "Short title"}) == set()
    assert C.claves_de_fuente({"doi": None, "pmid": True, "nct": ["NCT1"], "titulo": 7}) == set()
    assert C.claves_de_fuente({"doi": "  ", "pmid": "", "titulo": ""}) == set() and C.claves_de_fuente(None) == set() and C.claves_de_fuente("x") == set()
    afs = [_af(0, "apoya"), _af(1, "apoya")]
    for a, b in [({"pmid": "99"}, {"pmid": 99}), ({"nct": "NCT04437511"}, {"nct": "nct04437511"}), ({"titulo": "Donanemab in early symptomatic Alzheimer disease"}, {"titulo": "Donanemab in Early Symptomatic Alzheimer Disease."})]:
        h = _h(afs, [_fuente(0, "ADNI", **a), _fuente(1, "BioFINDER", **b)])
        assert C.cohortes_distintas(h) == ["ADNI"], (a, b)
    # Dos artículos distintos con títulos distintos no se tocan.
    h = _h(afs, [_fuente(0, "ADNI", titulo="Plasma GFAP in preclinical Alzheimer disease"), _fuente(1, "BioFINDER", titulo="Plasma NfL in prodromal Alzheimer disease")])
    assert C.cohortes_distintas(h) == ["ADNI", "BioFINDER"]


def test_el_articulo_fundido_toma_el_nombre_que_resuelve_al_catalogo_y_respeta_el_mismo_id():
    afs = [_af(0, "apoya"), _af(1, "apoya"), _af(2, "apoya")]
    # El primer nombre libre no manda si otro de la misma entrada resuelve al catálogo.
    h = _h(afs, [_fuente(0, "donanemab trial", doi="10.1/x"), _fuente(1, "TRAILBLAZER-ALZ 2", doi="10.1/x"), _fuente(2, "ADNI")])
    assert C.cohortes_distintas(h) == ["TRAILBLAZER-ALZ 2", "ADNI"]
    # Sin ninguno en el catálogo, el primero.
    h2 = _h(afs, [_fuente(0, "Cohorte Omega", doi="10.1/y"), _fuente(1, "Cohorte Sigma", doi="10.1/y"), _fuente(2, "ADNI")])
    assert C.cohortes_distintas(h2) == ["Cohorte Omega", "ADNI"]
    # Contrato que se conserva: el mismo id con dos cohortes declaradas son dos cohortes.
    fs = [{"id": "dup", "referencia": "Ref 0", "cohorte": "ADNI"}, {"id": "dup", "referencia": "Ref 0", "cohorte": "BIOCARD"}]
    assert C.cohortes_distintas(_h([_af(0)], fs)) == ["ADNI", "BIOCARD"]
    # La transitividad funde tres entradas: A comparte DOI con B, B comparte PMID con C.
    h3 = _h(afs, [_fuente(0, "ADNI", doi="10.1/z"), _fuente(1, "BioFINDER", doi="10.1/z", pmid="1"), _fuente(2, "A4", pmid="1")])
    assert C.cohortes_distintas(h3) == ["ADNI"] and C.fuentes_sin_cohorte(h3) == 0


def test_solo_las_entradas_que_cuentan_entran_en_la_fusion_y_sin_cohorte_no_repite_el_articulo():
    # La entrada A del artículo solo contradice; la B apoya: el artículo cuenta por B.
    h = _h([_af(0, "contradice"), _af(1, "apoya")], [_fuente(0, "ADNI", doi="10.1/w"), _fuente(1, "BioFINDER", doi="10.1/w")])
    assert C.cohortes_distintas(h) == ["BioFINDER"]
    # El mismo artículo dos veces sin cohorte en ninguna entrada es una sola fuente sin cohorte.
    h2 = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, None, doi="10.1/v"), _fuente(1, "", doi="10.1/v")])
    assert C.fuentes_sin_cohorte(h2) == 1 and "1 fuente sin cohorte identificada" in C.techo(h2)[1]
    # Con cohorte en una de las dos entradas, el artículo tiene cohorte.
    h3 = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, None, doi="10.1/v"), _fuente(1, "ADNI", doi="10.1/v")])
    assert C.fuentes_sin_cohorte(h3) == 0 and C.cohortes_distintas(h3) == ["ADNI"]
    # Sin afirmaciones (semilla del vivero) también se funde.
    assert C.cohortes_distintas(_h([], [_fuente(0, "ADNI", doi="10.1/u"), _fuente(1, "BioFINDER", doi="10.1/u")])) == ["ADNI"]


def test_priorizacion_y_acotar_dan_la_misma_lista_fundida():
    h = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, "ADNI", doi="10.1/t"), _fuente(1, "BioFINDER", doi="10.1/t")])
    assert PR.cohortes_de(h) == C.cohortes_distintas(h) == ["ADNI"]
    acotada = C.acotar("baja", h)
    # M-04: la conclusión lleva la lista que contó el techo desde que se escribe.
    assert acotada["techo"]["cohortesDistintas"] == ["ADNI"] and acotada["certeza"] == "muy_baja" and acotada["techo"]["acotada"]
    assert set(acotada["techo"]) == {"nivel", "motivo", "acotada", "certezaDelJuez", "cohortesDistintas"}
    assert C.acotar("alta", {"afirmaciones": [], "procedencia": {}})["techo"]["cohortesDistintas"] == []


# ---------------------------------------------------------------------------
# M-10 y M-14: recálculo por regla sin juez
# ---------------------------------------------------------------------------


def _conclusion(**k):
    base = {"certeza": "baja", "hipotesisBreve": "GFAP sube antes que NfL", "direccion": "apoya", "enunciado": "La evidencia sugiere, con limitaciones, que GFAP sube antes que NfL.", "factores": [], "conclusion": "texto del juez", "aFavor": ["a"], "enContra": []}
    base.update(k)
    return base


def test_reacotar_baja_la_certeza_cuando_una_frase_de_introduccion_deja_de_aportar_cohorte():
    # Dos cohortes a la vista, pero una es una frase de introducción: el techo real es muy baja.
    h = _h([_af(0, "apoya", cita="[Ref 0, sección Introduction]"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")], id="h1", titulo="T", conclusion=_conclusion())
    r = C.reacotar_conclusion(h)
    assert r["cambio"] and r["antes"]["certeza"] == "baja" and r["despues"]["certeza"] == "muy_baja"
    assert "bajó de baja a muy baja" in r["nota"] and "frases de introducción" in r["nota"]
    c = h["conclusion"]
    assert c["certeza"] == "muy_baja" and c["techo"]["nivel"] == "muy_baja" and c["techo"]["certezaDelJuez"] == "baja" and c["techo"]["acotada"]
    assert c["cohortesDistintas"] == ["BioFINDER"] and h["cohortesDistintas"] == ["BioFINDER"]
    assert c["escalera"][0]["a"] == "baja" and "segunda cohorte" in c["escalera"][0]["falta"]
    assert c["enunciado"].startswith("La evidencia es muy incierta sobre si GFAP sube antes que NfL")
    # Lo que escribió el juez no se toca.
    assert c["conclusion"] == "texto del juez" and c["aFavor"] == ["a"]
    # Segunda pasada: nada cambia y la nota lo dice.
    r2 = C.reacotar_conclusion(h)
    assert not r2["cambio"] and r2["nota"] == "sin cambios al recalcular el techo por regla"


def test_reacotar_recupera_el_nivel_del_juez_cuando_el_techo_sube_y_conserva_el_supuesto_contradicho():
    # El juez dijo baja; la regla acotó a muy baja con una cohorte. Llega la segunda cohorte:
    # la certeza vuelve a la del juez sin llamarlo, y la coletilla del supuesto se conserva.
    enunciado = "La evidencia es muy incierta sobre si GFAP sube antes que NfL, aunque un supuesto del que depende está contradicho por las fuentes."
    h = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")], titulo="T", conclusion=_conclusion(certeza="muy_baja", enunciado=enunciado, techo={"nivel": "muy_baja", "motivo": "x", "acotada": True, "certezaDelJuez": "baja"}))
    r = C.reacotar_conclusion(h)
    assert r["cambio"] and h["conclusion"]["certeza"] == "baja" and "subió de muy baja a baja" in r["nota"]
    assert h["conclusion"]["enunciado"] == "La evidencia sugiere, con limitaciones, que GFAP sube antes que NfL, aunque un supuesto del que depende está contradicho por las fuentes."
    # El juez nunca queda por encima del techo: con juez "alta" guardado y solo literatura, baja.
    h2 = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")], conclusion=_conclusion(certeza="alta", techo={"certezaDelJuez": "alta"}))
    assert C.reacotar_conclusion(h2)["despues"]["certeza"] == "baja"


def test_reacotar_tolera_conclusiones_antiguas_y_registros_raros():
    assert C.reacotar_conclusion(None) is None and C.reacotar_conclusion({"conclusion": None}) is None
    assert C.reacotar_conclusion({"conclusion": {"direccion": "apoya"}}) is None  # sin certeza no hay nada que acotar
    assert C.reacotar_conclusion({"conclusion": "texto"}) is None
    # Conclusión antigua: sin techo, sin factores, sin enunciado, certeza rara.
    h = _h([_af(0, "apoya")], [_fuente(0, "ADNI")], conclusion={"certeza": "altisima", "factores": "no es lista", "techo": "no es dict"})
    r = C.reacotar_conclusion(h)
    assert h["conclusion"]["certeza"] == "muy_baja" and h["conclusion"]["techo"]["certezaDelJuez"] == "muy_baja" and r["antes"]["techo"] is None
    assert isinstance(h["conclusion"]["escalera"], list) and h["conclusion"]["cohortesDistintas"] == ["ADNI"]
    # Sin dirección ni título, la frase plantilla no rompe (certeza cambió de "altisima" a muy baja).
    h2 = _h([_af(0, "apoya")], [_fuente(0, "ADNI")], conclusion={"certeza": "alta", "enunciado": "vieja"})
    C.reacotar_conclusion(h2)
    assert h2["conclusion"]["enunciado"].startswith("La evidencia es muy incierta sobre si")
    # Factores como objetos (lo que devuelve el juez antes de serializar) también valen.
    h3 = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")], conclusion=_conclusion(certeza="muy_baja", factores=[SimpleNamespace(factor="imprecision", efecto="baja", explicacion="n = 40")], techo={"certezaDelJuez": "muy_baja"}))
    C.reacotar_conclusion(h3)
    assert "imprecisión (n = 40)" in h3["conclusion"]["escalera"][0]["falta"]


def test_marcar_candidatas_reacota_las_conclusiones_y_deja_linea_en_el_registro():
    h = {**_h([_af(0, "apoya", cita="[Ref 0, sección Introduction]"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")]), "id": "h1", "investigacionId": "inv", "titulo": "T", "estado": "propuesta", "elo": 1200, "creadaEn": 1, "cluster": "c", "conclusion": _conclusion()}
    otra = {**_h([_af(0, "apoya")], [_fuente(0, "ADNI")]), "id": "h2", "investigacionId": "otra", "titulo": "U", "estado": "propuesta", "elo": 1200, "creadaEn": 1, "cluster": "c", "conclusion": _conclusion()}
    rota = {"id": "h3", "investigacionId": "inv", "titulo": "V", "estado": "propuesta", "elo": 1200, "creadaEn": 1, "cluster": "c", "conclusion": {"certeza": "baja"}, "afirmaciones": "rara", "procedencia": "rara"}
    e = {"hipotesis": [h, otra, rota], "investigaciones": [{"id": "inv", "datasets": []}, {"id": "otra", "datasets": []}], "planesAnalisis": [], "ejecuciones": [], "artefactos": [], "corridas": [], "iteraciones": []}
    cambios = PR.reacotar_conclusiones(e, "inv")
    assert [c["hipotesisId"] for c in cambios] == ["h1", "h3"] and cambios[0]["despues"]["certeza"] == "muy_baja"
    # La línea la escribe certeza.py con la fecha ISO delante, como el cierre de corrida.py.
    assert len(h["procedencia"]["registro"]) == 1 and h["procedencia"]["registro"][0].endswith(cambios[0]["nota"]) and h["procedencia"]["registro"][0][:4].isdigit()
    assert otra["conclusion"]["certeza"] == "baja", "otra investigación no se toca"
    assert rota["conclusion"]["certeza"] == "muy_baja" and rota["procedencia"] == "rara", "un registro raro se acota sin romper a las demás ni inventarle procedencia"
    # marcar_candidatas la corre al cerrar la iteración: la conclusión queda acotada y con sus cohortes.
    # (El registro roto sale del estado: `bloqueos_de` no lo tolera, y eso no es de esta tanda.)
    e["hipotesis"].remove(rota)
    h["conclusion"] = _conclusion()
    h["procedencia"]["registro"] = []
    PR.marcar_candidatas(e, "inv")
    assert h["conclusion"]["certeza"] == "muy_baja" and h["conclusion"]["cohortesDistintas"] == ["BioFINDER"] and h["cohortesDistintas"] == ["BioFINDER"]
    assert len(h["procedencia"]["registro"]) == 1
    PR.marcar_candidatas(e, "inv")
    assert len(h["procedencia"]["registro"]) == 1, "sin cambio no se repite la línea"
    # Sin investigación dada, recorre todas.
    otra["conclusion"] = _conclusion(certeza="alta", techo={"certezaDelJuez": "alta"})
    assert [c["hipotesisId"] for c in PR.reacotar_conclusiones(e)] == ["h2"]


# ---------------------------------------------------------------------------
# M-06: escalera con los factores reales, frase que distingue "nada" de "solo indirecta"
# ---------------------------------------------------------------------------


def test_la_escalera_nombra_los_factores_del_juez_solo_en_el_peldano_que_la_regla_no_frena():
    dos = _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")])
    factores = [{"factor": "riesgo_de_sesgo", "efecto": "baja", "explicacion": "pérdidas del 40 % en el seguimiento."}, {"factor": "imprecision", "efecto": "baja", "explicacion": "n = 40"}, {"factor": "efecto_grande", "efecto": "sube", "explicacion": "no cuenta"}, {"factor": "gradiente", "efecto": "neutro", "explicacion": "no cuenta"}]
    e = C.escalera(dos, "muy_baja", factores)
    assert e[0]["falta"] == "que se resuelva lo que el juez señaló al bajar la certeza: riesgo de sesgo (pérdidas del 40 % en el seguimiento); imprecisión (n = 40)"
    assert e[1]["falta"].startswith("evidencia directa") and e[2]["falta"].startswith("réplica")
    # Sin factores del juez, el texto por defecto de siempre.
    assert "que el juez deje de ver riesgo de sesgo" in C.escalera(dos, "muy_baja")[0]["falta"]
    assert "que el juez deje de ver riesgo de sesgo" in C.escalera(dos, "muy_baja", [{"factor": "efecto_grande", "efecto": "sube"}])[0]["falta"]
    # Cuando la estructura frena, manda la pieza estructural, no el factor del juez.
    una = _h([_af(0, "apoya")], [_fuente(0, "ADNI")])
    assert C.escalera(una, "muy_baja", factores)[0]["falta"].startswith("una segunda cohorte independiente")
    # Los factores se usan una vez: en el peldaño de alta vuelve el texto por defecto.
    lab = _h([_af(0, "apoya"), _af(1, "apoya", clase="observacion_original"), _af(2, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER"), _fuente(2, "A4")])
    e2 = C.escalera(lab, "baja", factores)
    assert [p["a"] for p in e2] == ["moderada", "alta"] and e2[0]["falta"].startswith("que se resuelva lo que el juez señaló") and "consistencia entre las cohortes" in e2[1]["falta"]
    # Factores como objetos y factores rotos.
    assert C.factores_que_bajan([SimpleNamespace(factor="inconsistencia", efecto="baja", explicacion=""), {"factor": 3, "efecto": "baja"}, {"efecto": "baja"}, None, "x"]) == ["inconsistencia"]
    assert C.factores_que_bajan(None) == [] and C.factores_que_bajan([{"factor": "rareza", "efecto": "BAJA", "explicacion": "a"}]) == ["rareza (a)"]


def test_frase_plantilla_distingue_nada_de_solo_indirecta():
    assert C.frase_plantilla("sin_evidencia_directa", "muy_baja", "GFAP sube antes que NfL.") == "No encontramos evidencia directa sobre si GFAP sube antes que NfL. Esto no significa que no exista."
    f = C.frase_plantilla("sin_evidencia_directa", "baja", "GFAP sube antes que NfL", indirectas=7)
    assert f.startswith("Solo encontramos evidencia indirecta sobre si GFAP sube antes que NfL: 7 afirmaciones sostenidas") and "la certeza es baja" in f and "no significa que no exista" in f
    assert "una afirmación sostenida o parcial con" in C.frase_plantilla("sin_evidencia_directa", "muy_baja", "X", indirectas=1)
    assert C.frase_plantilla("sin_evidencia_directa", "baja", "X", indirectas=0) == C.frase_plantilla("sin_evidencia_directa", "baja", "X", indirectas=None)
    # El resto de direcciones, como en corrida.py; una certeza rara vale como muy baja.
    assert C.frase_plantilla("apoya", "moderada", "GFAP sube") == "La evidencia reunida probablemente sostiene que GFAP sube."
    assert C.frase_plantilla("en_contra", "baja", "GFAP sube") == "La evidencia sugiere, con limitaciones, que no se cumple que GFAP sube."
    assert C.frase_plantilla("mixta", "rara", "GFAP sube") == "La evidencia es contradictoria sobre si GFAP sube; la certeza es muy baja."
    assert C.frase_plantilla("apoya", "alta", "APOE4 y GFAP", supuesto_contradicho=True).endswith("APOE4 y GFAP, aunque un supuesto del que depende está contradicho por las fuentes.")
    assert C.frase_plantilla("apoya", "alta", "") == "La evidencia reunida sostiene que ."


def test_solo_apoyo_indirecto_y_el_motivo_del_techo_se_lo_dice_al_juez():
    todas = _h([_af(0, "apoya_indirecta"), _af(1, "apoya_indirecta")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")])
    assert C.solo_apoyo_indirecto(todas) and len(C.apoyos_indirectos(todas)) == 2
    nivel, motivo = C.techo(todas)
    assert nivel == "baja" and "los 2 apoyos son todos indirectos" in motivo and "pesan la mitad" in motivo
    mezcla = _h([_af(0, "apoya_indirecta"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")])
    assert not C.solo_apoyo_indirecto(mezcla) and len(C.apoyos_indirectos(mezcla)) == 1 and "todos indirectos" not in C.techo(mezcla)[1]
    assert not C.solo_apoyo_indirecto(_h([], [])) and C.apoyos_indirectos({"afirmaciones": None}) == []
    # Un apoyo indirecto socavado no cuenta.
    assert C.apoyos_indirectos(_h([dict(_af(0, "apoya_indirecta"), socavadaPor=["x"])], [_fuente(0, "ADNI")])) == []


def test_todo_texto_nuevo_lleva_tildes_y_no_tiene_guiones_largos():
    factores = [{"factor": "riesgo_de_sesgo", "efecto": "baja", "explicacion": "x"}, {"factor": "imprecision", "efecto": "baja", "explicacion": "y"}, {"factor": "sesgo_de_publicacion", "efecto": "baja", "explicacion": ""}]
    textos = [C.frase_plantilla(d, c, "GFAP sube", indirectas=n) for d in ("sin_evidencia_directa", "apoya", "mixta", "en_contra") for c in C.NIVELES for n in (0, 1, 3)]
    casos = [
        _h([_af(0, "apoya_indirecta"), _af(1, "apoya_indirecta")], [_fuente(0, "ADNI", doi="10.1/a"), _fuente(1, "BioFINDER", doi="10.1/a")]),
        _h([_af(0, "apoya", cita="[Ref 0, sección Introduction]"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")], conclusion=_conclusion()),
        _h([_af(0, "apoya"), _af(1, "apoya")], [_fuente(0, "ADNI"), _fuente(1, "BioFINDER")], conclusion=_conclusion(certeza="muy_baja", techo={"certezaDelJuez": "baja"})),
    ]
    for h in casos:
        textos.append(C.techo(h)[1])
        for c in C.NIVELES:
            textos.extend(p["falta"] for p in C.escalera(h, c, factores))
        r = C.reacotar_conclusion(h)
        if r:
            textos.append(r["nota"])
    textos.extend(C.ETIQUETAS_FACTOR.values())
    for t in textos:
        assert "\u2014" not in t, t
        assert not SIN_TILDE.search(t), t
