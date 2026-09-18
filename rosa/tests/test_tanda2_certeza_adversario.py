"""Adversario del constructor "certeza" (tanda 2, 17 y 18 de septiembre de
2026): S-06 (a), M-10, M-03, M-04 y M-06.

Dos clases de test:

- Los que DEMUESTRAN UN FALLO fallan con el árbol de hoy y pasan cuando se
  repare; cada uno nombra el hallazgo en su docstring (F1, F2, F5, F6, F7).
- Los que FIJAN lo que se comprobó que funciona: el caso real de Raket 2026
  (S-06), el invariante del recorte de nombres (M-03), la misma regla de
  claves en certeza.py y pasos.py, y que el recálculo tolera estados raros.

Ningún test llama al gateway ni a la red: todo es regla determinista.
"""

from __future__ import annotations

import copy

from rosa import certeza as C
from rosa import metodos as M
from rosa import priorizacion as PR
from rosa.bucle import corrida as CO


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
    base = {"certeza": "baja", "hipotesisBreve": "GFAP sube antes que NfL", "direccion": "apoya", "enunciado": "La evidencia sugiere, con limitaciones, que GFAP sube antes que NfL.", "factores": [], "conclusion": "texto del juez", "aFavor": ["a"], "enContra": [], "iteracion": 1, "cambio": None}
    base.update(k)
    return base


def _hipotesis_completa(**k):
    """Una hipótesis con las claves que `marcar_candidatas` y el recálculo de
    corrida.py exigen (bloqueos, candidatas, eventos)."""
    base = {**_h([_af(0, "apoya")], [_fuente(0, "ADNI")]), "id": "h1", "investigacionId": "inv", "titulo": "GFAP sube antes que NfL", "estado": "propuesta", "elo": 1200, "creadaEn": 1, "cluster": "c", "decisionKiller": "avanzar", "experimento": None, "afirmacionesRaw": None}
    base.update(k)
    return base


def _estado(*hips):
    return {"hipotesis": list(hips), "investigaciones": [{"id": "inv", "datasets": []}], "planesAnalisis": [], "ejecuciones": [], "artefactos": [], "corridas": [], "iteraciones": [], "eventos": [], "aprendizaje": []}


SUPUESTO = "supuesto del que depende está contradicho"


# ---------------------------------------------------------------------------
# F1 (media): la copia canónica de `frase_plantilla` pierde el supuesto contradicho
# cuando la dirección es "sin_evidencia_directa"; la original de corrida.py lo dice.
# ---------------------------------------------------------------------------


def test_f1_frase_sin_evidencia_directa_conserva_el_supuesto_contradicho():
    """`direccion_por_regla` (corrida.py:2446) devuelve `supuesto_contradicho=True`
    también con dirección "sin_evidencia_directa", y la frase de corrida.py lo
    dice ("..., y un supuesto del que depende está contradicho por las
    fuentes"). La copia canónica de certeza.py lo calla en esa dirección, así
    que al sustituir una por otra (pendiente declarado por el constructor) la
    conclusión pierde el aviso y test_tanda2_cierre.py:375 rompe."""
    for indirectas in (None, 3):
        frase = C.frase_plantilla("sin_evidencia_directa", "muy_baja", "GFAP sube", supuesto_contradicho=True, indirectas=indirectas)
        assert SUPUESTO in frase, frase
    # Sin supuesto contradicho, no se inventa.
    assert SUPUESTO not in C.frase_plantilla("sin_evidencia_directa", "muy_baja", "GFAP sube", indirectas=3)


def test_f1_la_copia_canonica_dice_lo_mismo_que_corrida_en_todos_los_casos():
    """Si corrida.py va a delegar en certeza.py (pendiente del constructor), la
    canónica tiene que ser un superconjunto de la original: mismo texto en
    todas las (dirección, certeza, supuesto) cuando no se pasan indirectas."""
    distintas = []
    for direccion in ("apoya", "mixta", "en_contra", "sin_evidencia_directa"):
        for certeza in C.NIVELES:
            for supuesto in (False, True):
                a = CO.frase_plantilla(direccion, certeza, "GFAP sube antes que NfL", supuesto_contradicho=supuesto)
                b = C.frase_plantilla(direccion, certeza, "GFAP sube antes que NfL", supuesto_contradicho=supuesto)
                if a != b:
                    distintas.append((direccion, certeza, supuesto, a, b))
    assert distintas == [], distintas


def test_f1_reacotar_no_pierde_el_supuesto_contradicho_de_una_conclusion_sin_evidencia_directa():
    """Una conclusión "sin evidencia directa" con supuesto contradicho (frase de
    corrida.py) cuya certeza baja al recalcular: la frase nueva debe seguir
    avisando del supuesto. Hoy la marca que busca `reacotar_conclusion`
    ("aunque un supuesto...") no coincide con la forma de esta dirección ("y
    un supuesto...") y, aunque coincidiera, la frase la callaría."""
    enunciado = CO.frase_plantilla("sin_evidencia_directa", "baja", "GFAP sube antes que NfL", supuesto_contradicho=True)
    assert SUPUESTO in enunciado
    h = _h([_af(0, "apoya_indirecta")], [_fuente(0, "ADNI")], titulo="GFAP sube antes que NfL", conclusion=_conclusion(direccion="sin_evidencia_directa", enunciado=enunciado))
    r = C.reacotar_conclusion(h)
    assert r["cambio"] and h["conclusion"]["certeza"] == "muy_baja"
    assert SUPUESTO in h["conclusion"]["enunciado"], h["conclusion"]["enunciado"]


# ---------------------------------------------------------------------------
# F2 (media): dos implementaciones del mismo recálculo (corrida.py
# `recalcular_conclusiones_por_regla` y priorizacion.py `reacotar_conclusiones`)
# que escriben conclusiones distintas y dejan rastro distinto.
# ---------------------------------------------------------------------------


def _sin_evidencia_directa_con_indirectas(certeza="baja"):
    """Una hipótesis con un solo apoyo indirecto de una cohorte (techo muy baja)
    y una conclusión "sin evidencia directa" escrita con certeza `certeza`."""
    return _hipotesis_completa(
        afirmaciones=[_af(0, "apoya_indirecta")],
        conclusion=_conclusion(certeza=certeza, direccion="sin_evidencia_directa", enunciado=CO.frase_plantilla("sin_evidencia_directa", certeza, "GFAP sube antes que NfL")),
    )


def test_f2_las_dos_rutas_de_recalculo_escriben_la_misma_conclusion():
    """El cierre de la iteración corre primero `recalcular_conclusiones_por_regla`
    (corrida.py:1809) y después `marcar_candidatas` (corrida.py:1840), que a su
    vez corre `reacotar_conclusiones`. Con la misma entrada tienen que dejar la
    misma certeza, techo, escalera y enunciado; hoy el enunciado difiere ("No
    encontramos evidencia directa" frente a "Solo encontramos evidencia
    indirecta"), así que la frase de M-06 nunca llega a una conclusión real:
    la ruta de corrida.py gana siempre por orden."""
    ea, eb = _estado(_sin_evidencia_directa_con_indirectas()), _estado(_sin_evidencia_directa_con_indirectas())
    CO.recalcular_conclusiones_por_regla(ea, 1000)
    PR.reacotar_conclusiones(eb)
    ca, cb = ea["hipotesis"][0]["conclusion"], eb["hipotesis"][0]["conclusion"]
    assert ca["certeza"] == cb["certeza"] == "muy_baja"
    assert ca["techo"]["nivel"] == cb["techo"]["nivel"] and ca["escalera"] == cb["escalera"]
    assert ca["enunciado"] == cb["enunciado"], (ca["enunciado"], cb["enunciado"])


def test_f2_una_certeza_que_cambia_al_marcar_candidatas_deja_rastro_visible():
    """La interfaz enseña el cambio de certeza por `conclusion.cambio`
    (EnLlano.tsx:185, digest.ts:120) y la ruta de corrida.py lo escribe junto
    con `recalculadaEn` y un evento. Si `marcar_candidatas` mueve la certeza
    por su cuenta, tiene que dejar el mismo rastro; hoy solo deja una línea en
    el registro de procedencia y la pantalla no ve que la certeza bajó."""
    h = _sin_evidencia_directa_con_indirectas()
    e = _estado(h)
    PR.marcar_candidatas(e, "inv")
    c = h["conclusion"]
    if c["certeza"] != "baja":
        cambio = c.get("cambio")
        assert isinstance(cambio, dict) and cambio.get("de", {}).get("certeza") == "baja", "la certeza bajó sin `cambio`: la pantalla no lo enseña"
        assert c.get("recalculadaEn") is not None


def test_f2_en_el_orden_del_cierre_la_frase_de_m06_llega_a_la_conclusion():
    """M-06 pedía que la conclusión distinga "nada" de "solo evidencia
    indirecta". En el orden real del cierre (corrida.py primero, después
    marcar_candidatas) una conclusión con apoyos indirectos cuya certeza baja
    tiene que quedar diciéndolo; hoy queda "No encontramos evidencia directa"
    porque la segunda ruta ya no ve cambio."""
    h = _sin_evidencia_directa_con_indirectas()
    e = _estado(h)
    CO.recalcular_conclusiones_por_regla(e, 1000, "inv")
    PR.marcar_candidatas(e, "inv")
    assert h["conclusion"]["certeza"] == "muy_baja"
    assert "evidencia indirecta" in h["conclusion"]["enunciado"], h["conclusion"]["enunciado"]


# ---------------------------------------------------------------------------
# F5 (baja): la nota del recálculo dice "sube" cuando la certeza anterior no se reconoce.
# ---------------------------------------------------------------------------


def test_f5_la_nota_no_dice_sube_cuando_la_certeza_anterior_es_irreconocible():
    h = {"afirmaciones": [], "procedencia": {}, "conclusion": {"certeza": "altisima", "direccion": "apoya", "enunciado": "x"}}
    r = C.reacotar_conclusion(h)
    assert r["despues"]["certeza"] == "muy_baja"
    assert "sube" not in r["nota"], r["nota"]


# ---------------------------------------------------------------------------
# F6 (baja): la pasada accidental de scripts/acentuar_py.py acentuó un identificador
# en un docstring de certeza.py.
# ---------------------------------------------------------------------------


def test_f6_el_docstring_de_es_sintetica_nombra_la_clave_sin_tilde():
    doc = C.es_sintetica.__doc__ or ""
    assert "`sintético`" not in doc, "la clave del registro es `sintetico`; acentuarla en la documentación confunde"
    assert "`sintetico`" in doc


# ---------------------------------------------------------------------------
# F7 (baja): la frase de "solo evidencia indirecta" llama "sostenidas" a las parciales.
# ---------------------------------------------------------------------------


def test_f7_la_frase_indirecta_no_llama_sostenida_a_una_afirmacion_parcial():
    h = _h([_af(0, "apoya_indirecta", veredicto="parcial")], [_fuente(0, "ADNI")])
    n = len(C.apoyos_indirectos(h))
    assert n == 1
    frase = C.frase_plantilla("sin_evidencia_directa", "muy_baja", "GFAP sube", indirectas=n)
    assert "una afirmación sostenida con" not in frase or "parcial" in frase, frase


# ---------------------------------------------------------------------------
# Lo que sí se comprobó: S-06 (a) sobre el caso real, M-03 invariante, misma regla de claves.
# ---------------------------------------------------------------------------


def test_s06_el_caso_real_de_raket_2026_cuenta_una_cohorte_y_el_techo_baja_a_muy_baja():
    """Las tres fuentes de hip-mu2tskgf-2920 tal como están en rosa.db el 18 de
    septiembre de 2026 (mismo DOI y PMID en las dos entradas de Raket, título
    con un espacio duro, la cohorte de la primera cortada a 60 con el NCT
    roto). El Killer y el dossier (`PR.cohortes_de`) tienen que ver lo mismo."""
    johansson = {"id": "f-mu2t9u05-1007", "referencia": "Johansson et al., 2023", "titulo": "Plasma biomarker profiles in autosomal dominant Alzheimer's disease.", "doi": "10.1093/brain/awac399", "pmid": "36626935", "cohorte": "Swedish familial Alzheimer's disease study"}
    raket_a = {"id": "f-mu36jztz-613", "referencia": "Raket et al., 2026", "titulo": "Donanemab treatment effect by baseline tau burden\xa0and disease severity", "doi": "10.1002/alz.71577", "pmid": "42273802", "cohorte": "TRAILBLAZER-ALZ (NCT03367403) y TRAILBLAZER-ALZ 2 (NCT044375"}
    raket_b = {"id": "f-mu44f394-8230", "referencia": "Raket et al., 2026", "titulo": "Donanemab treatment effect by baseline tau burden and disease severity", "doi": "https://doi.org/10.1002/ALZ.71577", "pmid": 42273802, "cohorte": "donanemab trial"}
    afs = [
        dict(_af(0, "apoya"), cita="[Johansson et al., 2023, sección Introduction]", fuenteId="f-mu2t9u05-1007"),
        dict(_af(1, "apoya"), cita="[Raket et al., 2026, pág. 4]", fuenteId="f-mu36jztz-613"),
        dict(_af(2, "apoya"), cita="[Raket et al., 2026, pág. 7]", fuenteId="f-mu44f394-8230"),
    ]
    h = _h(afs, [johansson, raket_a, raket_b])
    assert C.cohortes_distintas(h) == ["TRAILBLAZER-ALZ"]
    assert PR.cohortes_de(h) == ["TRAILBLAZER-ALZ"]
    nivel, motivo = C.techo(h)
    assert nivel == "muy_baja" and "una sola cohorte" in motivo and "frases de introducción" in motivo
    acotada = C.acotar("baja", h)
    assert acotada["certeza"] == "muy_baja" and acotada["techo"]["cohortesDistintas"] == ["TRAILBLAZER-ALZ"]
    # Con una tercera fuente de otra cohorte, vuelve a baja: la fusión no se pasa de frenada.
    h["procedencia"]["fuentes"].append(_fuente(3, "ADNI", doi="10.1/otro"))
    h["afirmaciones"].append(_af(3, "apoya"))
    assert C.techo(h)[0] == "baja" and C.cohortes_distintas(h) == ["TRAILBLAZER-ALZ", "ADNI"]


def test_s06_la_fusion_por_articulo_no_muta_ni_depende_del_orden_de_las_fuentes():
    fuentes = [_fuente(0, "donanemab trial", doi="10.1/x"), _fuente(1, "ADNI"), _fuente(2, "TRAILBLAZER-ALZ 2", doi="10.1/x")]
    afs = [_af(0, "apoya"), _af(1, "apoya"), _af(2, "apoya")]
    esperado = {"TRAILBLAZER-ALZ 2", "ADNI"}
    for orden in ([0, 1, 2], [2, 1, 0], [1, 2, 0]):
        h = _h([afs[i] for i in orden], [copy.deepcopy(fuentes[i]) for i in orden])
        antes = copy.deepcopy(h)
        assert set(C.cohortes_distintas(h)) == esperado, orden
        assert h == antes


def test_m03_recortar_conserva_lo_que_canoniza_el_nombre_entero_y_es_idempotente():
    nombres = [
        "TRAILBLAZER-ALZ (NCT03367403) y TRAILBLAZER-ALZ 2 (NCT04437511)",
        "Participantes con Alzheimer temprano del ensayo de fase 3 de donanemab, brazo activo y placebo (NCT04437511)",
        "Older adults from the Mayo Clinic Study of Aging with plasma GFAP and amyloid PET at baseline and follow-up visits",
        "Portadores de PSEN1 E280A de Antioquia (API Colombia) y no portadores emparejados por edad, sexo y nivel educativo",
        "Cohort of familial Alzheimer's disease mutation carriers from the Dominantly Inherited Alzheimer Network observational study",
        "Adults with Down syndrome from the Alzheimer Biomarker Consortium Down Syndrome with plasma p-tau217 and amyloid PET",
        "Insight 46 participants from the 1946 British birth cohort with amyloid PET and plasma biomarkers at age seventy years",
        "Participants recruited to prevent cognitive decline in a memory clinic cohort of older adults with subjective complaints",
        "Cognitively unimpaired older adults with amyloid load measured by PET at baseline and at follow-up in the memory clinic",
        "solanezumab-1&2 (EXPEDITION NCT00905372, EXPEDITION2 NCT00904683) y EXPEDITION3 (NCT01900665), análisis conjunto",
        "x" * 61 + " a4",
        "NCT04437511" * 6,
    ]
    for n in nombres:
        r = M.recortar_nombre_cohorte(n)
        assert r, n
        c0, c1 = M.canonizar_cohorte(n), M.canonizar_cohorte(r)
        assert (c0 or {}).get("id") == (c1 or {}).get("id"), (n, r, c0, c1)
        assert M.recortar_nombre_cohorte(r) == r, (r, M.recortar_nombre_cohorte(r))
        # Solo el paréntesis de identificadores puede pasar de 60.
        if len(r) > 60:
            assert r.endswith(")") and (M.canonizar_cohorte(r[r.rfind("("):]) is not None or "NCT" in r[r.rfind("("):]), r
        assert "\u2014" not in r or "\u2014" in n


def test_m03_el_recorte_de_pasos_py_sigue_rompiendo_el_nct_hasta_que_se_aplique_el_pendiente():
    """Dato para quien aplique el pendiente en rosa/bucle/pasos.py:1669: en el
    estado real hay 49 nombres de cohorte de 60 caracteres justos, con el NCT
    partido ("EXPEDITION2 NCT0090"). `recortar_nombre_cohorte` no puede
    repararlos a posteriori (la información ya se perdió), solo evitar los
    nuevos; los antiguos siguen resolviendo por el primer NCT que sobrevivió."""
    roto = "solanezumab-1&2 (EXPEDITION NCT00905372, EXPEDITION2 NCT0090"
    assert len(roto) == 60
    assert M.recortar_nombre_cohorte(roto) == roto
    assert M.canonizar_cohorte(roto)["etiqueta"] == "NCT00905372"


def test_las_claves_de_fuente_de_certeza_y_pasos_coinciden_en_registros_corrientes():
    from rosa.bucle import pasos as PASOS

    registros = [
        {"doi": "https://doi.org/10.1002/ALZ.71577.", "pmid": "42273802", "titulo": "Donanemab treatment effect by baseline tau burden\xa0and disease severity"},
        {"doi": "doi: 10.1093/brain/awac399", "pmid": 36626935, "titulo": "Plasma biomarker profiles in autosomal dominant Alzheimer's disease."},
        {"nct": "NCT04437511", "titulo": "A Study of Donanemab (LY3002813) in Participants With Early Alzheimer's Disease"},
        {"titulo": "Short"},
        {"doi": "", "pmid": "", "nct": None, "titulo": None},
        {"referencia": "Kim et al., 2025"},
    ]
    for r in registros:
        assert C.claves_de_fuente(r) == PASOS.claves_de_fuente(r), r


def test_el_recalculo_tolera_estados_raros_sin_romper_el_cierre():
    sin_conclusion = _hipotesis_completa(id="h2")
    sin_conclusion.pop("conclusion", None)
    certeza_none = _hipotesis_completa(id="h3", conclusion=_conclusion(certeza=None))
    factores_raros = _hipotesis_completa(id="h4", conclusion=_conclusion(factores=[None, "x", 3, {"factor": None, "efecto": "baja"}]))
    e = _estado(sin_conclusion, certeza_none, factores_raros)
    assert PR.reacotar_conclusiones(_estado()) == []
    cambios = PR.reacotar_conclusiones(e, "inv")
    assert all(c["hipotesisId"] in ("h3", "h4") for c in cambios)
    assert certeza_none["conclusion"]["certeza"] == "muy_baja"
    PR.marcar_candidatas(e, "inv")
    assert "conclusion" not in sin_conclusion
    # Idempotencia: la segunda pasada no toca nada ni añade líneas al registro.
    registros = [len(h["procedencia"]["registro"]) for h in e["hipotesis"]]
    assert PR.reacotar_conclusiones(e, "inv") == []
    assert [len(h["procedencia"]["registro"]) for h in e["hipotesis"]] == registros
