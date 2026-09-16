"""La ruta terapéutica por regla (rosa/ruta.py): cada paso cubierto por su
evidencia, la ruta vacía, la coherencia del paso declarado, la hipótesis
antigua sin tarjeta, la ejecución no válida que no cuenta y el mapa por
diana con un hueco."""

import itertools
import json

from rosa import ruta as R
from rosa.estado import plantilla as P

INV = "inv-t"
_ids = itertools.count(1)


def _e():
    return P.estado_inicial()


def _h(**campos):
    campos.setdefault("comprobacion", {"biomarcador": "", "cohorte": "", "diseno": ""})
    return P.nueva_hipotesis(INV, 1, 1000, titulo="GFAP sube antes que NfL", enunciado="En portadores de APOE4 el GFAP en plasma sube antes que el NfL", mecanismo="Reactividad astrocitaria", **campos)


def _af(texto, veredicto="sostenida", tipo="literatura", ref="A, 2024", **k):
    base = {"afirmacionId": f"af-{next(_ids)}", "texto": texto, "cita": f"[{ref}, pág. 3]", "veredicto": veredicto, "motivo": "", "entidadDistinta": False, "tipo": tipo, "clase": "literatura", "sintetico": False, "trayectoria": None, "fragmento": texto}
    base.update(k)
    return base


def _f(id_, referencia, tipo_estudio="cohorte", cohorte=None, **k):
    return P.nueva_fuente(id=id_, referencia=referencia, tipoEstudio=tipo_estudio, cohorte=cohorte, **k)


def _con(h, afs=(), fuentes=()):
    h["afirmaciones"] = list(afs)
    h["procedencia"]["fuentes"] = list(fuentes)
    return h


def _tarjeta(**k):
    t = P.tarjeta_vacia()
    t.update(k)
    return t


def _estados(ev):
    return {p["paso"]: p["estado"] for p in ev["pasos"]}


def _paso(ev, nombre):
    return next(p for p in ev["pasos"] if p["paso"] == nombre)


def _ejecucion(h, veredicto="valido", estado="completado", runtime="docker"):
    x = P.nueva_ejecucion(INV, h["id"], "plan-1", "hipotesis", "print(1)", 1, "abc", 1000)
    x["estado"] = estado
    x["runtime"] = runtime
    x["resultados"] = {"diferencia_medias": "12.3"}
    if veredicto is not None:
        x["auditoria"] = {"veredicto": veredicto, "comprobaciones": [], "motivo": "", "quien": "juez", "fecha": 1000}
    return x


# -- Forma y ruta vacía -------------------------------------------------------


def test_forma_del_resultado_y_orden_de_los_pasos():
    ev = R.evaluar_ruta(_e(), _h())
    assert [p["paso"] for p in ev["pasos"]] == list(P.PASOS_RUTA)
    assert set(ev) >= {"pasos", "siguiente", "cubiertos", "declarado", "coherente", "resumen", "hipotesisId", "motivoCoherencia", "porEstado"}
    for p in ev["pasos"]:
        assert set(p) == {"paso", "estado", "evidencia", "motivo"} and p["estado"] in R.ESTADOS_PASO and p["motivo"]
        for pieza in p["evidencia"]:
            assert set(pieza) == {"tipo", "id", "texto"} and pieza["tipo"] in R.TIPOS_EVIDENCIA
    json.dumps(ev, ensure_ascii=False)  # serializable, sin conjuntos


def test_ruta_vacia_distingue_vacio_de_no_comprobable():
    e = _e()
    h = _h()
    ev = R.evaluar_ruta(e, h)
    est = _estados(ev)
    # Sin tarjeta no hay con qué juzgar intervención, diana ni toxicidad: no comprobable, no vacío.
    assert est["opciones_intervencion"] == "no_comprobable" and est["compromiso_diana"] == "no_comprobable" and est["selectividad_toxicidad"] == "no_comprobable"
    assert est["mecanismo"] == "vacio" and est["efecto_funcional"] == "vacio" and est["exposicion"] == "vacio" and est["replicacion_independiente"] == "vacio" and est["evidencia_poblacion"] == "vacio"
    assert ev["cubiertos"] == 0 and ev["siguiente"] == "mecanismo" and ev["declarado"] is None and ev["coherente"] is True
    assert "0 de 8" in ev["resumen"] and "Mecanismo" in ev["resumen"] and ev["porEstado"]["no_comprobable"] == 3
    # Con tarjeta vacía, intervención y toxicidad pasan a vacío (se miró); la diana sigue sin declarar.
    h["tarjeta"] = _tarjeta()
    est2 = _estados(R.evaluar_ruta(e, h))
    assert est2["opciones_intervencion"] == "vacio" and est2["selectividad_toxicidad"] == "vacio" and est2["compromiso_diana"] == "no_comprobable"


# -- Cada paso por su evidencia ---------------------------------------------------


def test_mecanismo_por_apoyos_hechos_y_grafo_causal():
    e = _e()
    h = _con(_h(), [_af("GFAP sube en portadores APOE4")])
    p = _paso(R.evaluar_ruta(e, h), "mecanismo")
    assert p["estado"] == "parcial" and "un solo apoyo" in p["motivo"] and p["evidencia"][0]["tipo"] == "afirmacion"
    # Dos apoyos: cubierto. Una que contradice, una sintética y una socavada no cuentan.
    h2 = _con(_h(), [_af("GFAP sube"), _af("GFAP sube también en BioFINDER"), _af("GFAP no cambia", relacion="contradice"), _af("dato seco", sintetico=True), _af("apoyo atacado", socavadaPor=["af-x"])])
    p2 = _paso(R.evaluar_ruta(e, h2), "mecanismo")
    assert p2["estado"] == "cubierto" and len(p2["evidencia"]) == 2 and "2 afirmaciones" in p2["motivo"]
    # Un apoyo más el grafo causal acotado: cubierto; sin resolver: sigue parcial.
    h3 = _con(_h(grafoCausal={"identificacion": "acotado"}), [_af("GFAP sube")])
    assert _paso(R.evaluar_ruta(e, h3), "mecanismo")["estado"] == "cubierto"
    h3["grafoCausal"]["identificacion"] = "sin_resolver"
    p3 = _paso(R.evaluar_ruta(e, h3), "mecanismo")
    assert p3["estado"] == "parcial" and "sin resolver" in p3["motivo"]
    # Un hecho enlazado por afirmacionIds cuenta; descartado, sustituido o de otra investigación no.
    a = _af("GFAP sube")
    h4 = _con(_h(), [a])
    e["hechos"].append(P.nuevo_hecho(INV, "hecho", "GFAP", "El GFAP en plasma sube con la carga amiloide", "sabido", "fuente", [], 1000, afirmacion_ids=[a["afirmacionId"]]))
    e["hechos"].append(P.nuevo_hecho(INV, "hecho", "GFAP", "Descartado", "descartado", "fuente", [], 1000, afirmacion_ids=[a["afirmacionId"]]))
    e["hechos"].append(P.nuevo_hecho("inv-otra", "hecho", "GFAP", "De otra investigación", "sabido", "fuente", [], 1000, afirmacion_ids=[a["afirmacionId"]]))
    p4 = _paso(R.evaluar_ruta(e, h4), "mecanismo")
    assert p4["estado"] == "cubierto" and [x["tipo"] for x in p4["evidencia"]] == ["afirmacion", "hecho"] and "1 hecho" in p4["motivo"]
    # Solo afirmaciones sin verificar: no comprobable, no vacío.
    h5 = _con(_h(), [_af("pendiente", veredicto="sin_verificar"), _af("pendiente 2", veredicto="")])
    p5 = _paso(R.evaluar_ruta(e, h5), "mecanismo")
    assert p5["estado"] == "no_comprobable" and "2 afirmaciones sin verificar" in p5["motivo"]


def test_opciones_de_intervencion_por_tarjeta_o_por_afirmaciones():
    e = _e()
    h = _h(tarjeta=_tarjeta(intervencion="anticuerpo anti-GFAP", direccion="disminuye"))
    p = _paso(R.evaluar_ruta(e, h), "opciones_intervencion")
    assert p["estado"] == "cubierto" and "anticuerpo anti-GFAP" in p["motivo"] and "disminuye" in p["motivo"]
    h["tarjeta"]["direccion"] = "sin_intervencion"
    p = _paso(R.evaluar_ruta(e, h), "opciones_intervencion")
    assert p["estado"] == "parcial" and "falta decir si aumenta" in p["motivo"]
    # Sin tarjeta pero con literatura que nombra un fármaco (castellano e inglés): parcial.
    h2 = _con(_h(), [_af("El fármaco redujo la reactividad astrocitaria"), _af("The drug reduced plasma GFAP in treated mice")])
    p2 = _paso(R.evaluar_ruta(e, h2), "opciones_intervencion")
    assert p2["estado"] == "parcial" and len(p2["evidencia"]) == 2 and "sin tarjeta" in p2["motivo"]
    # Tarjeta con dirección pero sin nombre de intervención y sin literatura: vacío con el motivo.
    h3 = _con(_h(tarjeta=_tarjeta(direccion="aumenta")), [_af("GFAP sube")])
    p3 = _paso(R.evaluar_ruta(e, h3), "opciones_intervencion")
    assert p3["estado"] == "vacio" and "aunque declara dirección 'aumenta'" in p3["motivo"]
    # "grupo compuesto por 120 personas" no es una intervención.
    h4 = _con(_h(tarjeta=_tarjeta()), [_af("Grupo compuesto por 120 personas sin deterioro")])
    assert _paso(R.evaluar_ruta(e, h4), "opciones_intervencion")["estado"] == "vacio"


def test_compromiso_de_diana_por_dato_medido_o_analisis_valido():
    e = _e()
    h = _con(_h(tarjeta=_tarjeta(diana="GFAP")), [_af("Plasma GFAP was 120 pg/mL in carriers", tipo="dato", nivelMedicion="medida", n="80")])
    p = _paso(R.evaluar_ruta(e, h), "compromiso_diana")
    assert p["estado"] == "cubierto" and "«GFAP»" in p["motivo"] and p["evidencia"][0]["tipo"] == "afirmacion"
    # El nombre largo resuelve por identificador canónico (ontologías), no por cadena.
    h2 = _con(_h(tarjeta=_tarjeta(diana="GFAP")), [_af("Glial fibrillary acidic protein rose 40 %", tipo="dato")])  # sin nivelMedicion: registro antiguo, cuenta como resultado_analisis
    assert _paso(R.evaluar_ruta(e, h2), "compromiso_diana")["estado"] == "cubierto"
    # Un dato que no nombra la diana: parcial. Una interpretación del autor no es una medida.
    h3 = _con(_h(tarjeta=_tarjeta(diana="GFAP")), [_af("NfL was 30 pg/mL", tipo="dato", nivelMedicion="medida"), _af("GFAP probablemente sube", tipo="dato", nivelMedicion="interpretacion_autor")])
    p3 = _paso(R.evaluar_ruta(e, h3), "compromiso_diana")
    assert p3["estado"] == "parcial" and "ninguno nombra la diana" in p3["motivo"] and len(p3["evidencia"]) == 1
    # El biomarcador de la comprobación vale como diana cuando no hay tarjeta.
    h4 = _con(_h(comprobacion={"biomarcador": "NfL", "cohorte": "", "diseno": ""}), [_af("NfL en plasma: 30 pg/mL", tipo="dato", nivelMedicion="medida")])
    assert _paso(R.evaluar_ruta(e, h4), "compromiso_diana")["estado"] == "cubierto"
    # Una enfermedad en la diana no casa con todo: "Alzheimer" en el texto no cubre la diana.
    h5 = _con(_h(tarjeta=_tarjeta(diana="GFAP en la enfermedad de Alzheimer")), [_af("Alzheimer disease patients were older", tipo="dato", nivelMedicion="medida")])
    assert _paso(R.evaluar_ruta(e, h5), "compromiso_diana")["estado"] == "parcial"


def test_ejecucion_valida_cuenta_y_no_valida_sintetica_o_sin_auditar_no():
    e = _e()
    h = _h(tarjeta=_tarjeta(diana="GFAP"))
    e["ejecuciones"].append(_ejecucion(h, veredicto="valido"))
    p = _paso(R.evaluar_ruta(e, h), "compromiso_diana")
    assert p["estado"] == "cubierto" and p["evidencia"][0]["tipo"] == "ejecucion" and "diferencia_medias=12.3" in p["evidencia"][0]["texto"] and "auditoría válida" in p["motivo"]
    # No válida: no cuenta y se dice.
    e2 = _e()
    e2["ejecuciones"].append(_ejecucion(h, veredicto="no_valido"))
    p2 = _paso(R.evaluar_ruta(e2, h), "compromiso_diana")
    assert p2["estado"] == "parcial" and "no válida" in p2["motivo"] and "no cuenta" in p2["motivo"] and p2["evidencia"] == []
    # Válida pero sobre datos sintéticos: no cuenta.
    e3 = _e()
    e3["ejecuciones"].append(_ejecucion(h, veredicto="valido", runtime="local_sintetico"))
    p3 = _paso(R.evaluar_ruta(e3, h), "compromiso_diana")
    assert p3["estado"] == "parcial" and "sintéticos" in p3["motivo"]
    # Completada sin auditar: no comprobable, no vacío.
    e4 = _e()
    e4["ejecuciones"].append(_ejecucion(h, veredicto=None))
    p4 = _paso(R.evaluar_ruta(e4, h), "compromiso_diana")
    assert p4["estado"] == "no_comprobable" and "sin auditar" in p4["motivo"]
    # Enlazada solo por h.ejecuciones (sin hipotesisId): también cuenta; repetida por id, una vez.
    e5 = _e()
    x = _ejecucion(h, veredicto="valido")
    x["hipotesisId"] = None
    h5 = dict(h, ejecuciones=[x["id"]])
    e5["ejecuciones"] += [x, dict(x)]
    p5 = _paso(R.evaluar_ruta(e5, h5), "compromiso_diana")
    assert p5["estado"] == "cubierto" and len(p5["evidencia"]) == 1 and p5["motivo"].startswith("1 análisis in silico")


def test_efecto_funcional_por_desenlace_clinico_o_laboratorio():
    e = _e()
    h = _con(_h(), [_af("MMSE declined 3 points per year in high-GFAP participants", tipo="dato", nivelMedicion="medida")])
    p = _paso(R.evaluar_ruta(e, h), "efecto_funcional")
    assert p["estado"] == "cubierto" and "1 dato medido" in p["motivo"]
    h2 = _con(_h(), [_af("Se asocia a peor cognición en la revisión")])
    p2 = _paso(R.evaluar_ruta(e, h2), "efecto_funcional")
    assert p2["estado"] == "parcial" and "sin dato medido" in p2["motivo"]
    # El laboratorio reprodujo el efecto: cubierto, evidencia de tipo laboratorio.
    h3 = _h(experimento={"protocolo": "", "ensayo": "", "costeEstimado": "", "laboratorio": "L", "estado": "datos_recibidos", "ficheroDatos": "d.csv", "analisisPedido": "", "prerregistroArtefactoId": "art-1", "resultado": {"veredicto": "confirma", "clasificacion": "apoyo_reproducido", "resultado": "La viabilidad celular subió un 20 %", "motivo": "", "limitaciones": "", "cifras": [], "exploratorio": "", "fecha": 1, "fichero": "d.csv"}})
    p3 = _paso(R.evaluar_ruta(e, h3), "efecto_funcional")
    assert p3["estado"] == "cubierto" and p3["evidencia"][0] == {"tipo": "laboratorio", "id": "art-1", "texto": "La viabilidad celular subió un 20 %"}
    h3["experimento"]["resultado"]["clasificacion"] = "negativo_interpretable"
    p4 = _paso(R.evaluar_ruta(e, h3), "efecto_funcional")
    assert p4["estado"] == "parcial" and "negativo interpretable" in p4["motivo"]
    h3["experimento"]["resultado"]["clasificacion"] = "fallo_tecnico"
    assert _paso(R.evaluar_ruta(e, h3), "efecto_funcional")["estado"] == "no_comprobable"
    h3["experimento"]["resultado"] = None
    p6 = _paso(R.evaluar_ruta(e, h3), "efecto_funcional")
    assert p6["estado"] == "no_comprobable" and "sin evaluar" in p6["motivo"]


def test_selectividad_y_toxicidad_declarada_no_es_medida():
    e = _e()
    h = _h(tarjeta=_tarjeta(riesgos=["ARIA en portadores APOE4"]))
    p = _paso(R.evaluar_ruta(e, h), "selectividad_toxicidad")
    assert p["estado"] == "parcial" and "declarado, no medido" in p["motivo"]
    # Dimensión de toxicidad del laboratorio: cubierto y avisa de que cierra la vía.
    h2 = _h(tarjeta=_tarjeta(riesgos=["r"]), experimento={"estado": "datos_recibidos", "laboratorio": "L", "resultado": {"veredicto": "inconcluso", "clasificacion": "toxicidad_inviabilidad", "resultado": "Muerte celular al 50 %", "dimensiones": {"falloTecnico": False, "inconcluso": False, "efectoPequenoInterpretable": False, "efectoPredicho": False, "efectoInesperado": False, "toxicidad": True, "nota": ""}}})
    p2 = _paso(R.evaluar_ruta(e, h2), "selectividad_toxicidad")
    assert p2["estado"] == "cubierto" and "se cierra" in p2["motivo"] and p2["evidencia"][0]["tipo"] == "laboratorio"
    # Dimensiones evaluadas sin toxicidad: parcial (no es un ensayo de selectividad).
    h2["experimento"]["resultado"].update(clasificacion="apoyo_reproducido", dimensiones={"toxicidad": False})
    h2["tarjeta"]["riesgos"] = []
    p3 = _paso(R.evaluar_ruta(e, h2), "selectividad_toxicidad")
    assert p3["estado"] == "parcial" and "no marcó toxicidad" in p3["motivo"]
    # Un dato sobre efectos adversos cubre aunque contradiga la hipótesis (aquí importa que se midió).
    h3 = _con(_h(tarjeta=_tarjeta()), [_af("ARIA-E occurred in 12 % of treated participants", tipo="dato", relacion="contradice")])
    assert _paso(R.evaluar_ruta(e, h3), "selectividad_toxicidad")["estado"] == "cubierto"
    # "selective vulnerability" es mecanismo, no selectividad de fármaco.
    h4 = _con(_h(tarjeta=_tarjeta()), [_af("Selective vulnerability of CA1 neurons")])
    assert _paso(R.evaluar_ruta(e, h4), "selectividad_toxicidad")["estado"] == "vacio"


def test_exposicion_por_matriz_dosis_o_farmacocinetica():
    e = _e()
    h = _con(_h(), [_af("Plasma GFAP: 120 pg/mL", tipo="dato", nivelMedicion="medida")])
    p = _paso(R.evaluar_ruta(e, h), "exposicion")
    assert p["estado"] == "cubierto" and "plasma" in p["motivo"]
    # Solo el título de una fuente lo nombra: parcial con evidencia de tipo fuente.
    h2 = _con(_h(), [_af("GFAP sube")], [_f("f1", "B, 2023", titulo="CSF and plasma biomarkers of astrogliosis")])
    p2 = _paso(R.evaluar_ruta(e, h2), "exposicion")
    assert p2["estado"] == "parcial" and p2["evidencia"][0]["tipo"] == "fuente" and "LCR" in p2["evidencia"][0]["texto"]
    # "blood pressure" no es una muestra de sangre; "blood-brain barrier" y "dosis" sí son exposición.
    assert _paso(R.evaluar_ruta(e, _con(_h(), [_af("Blood pressure was higher in carriers")])), "exposicion")["estado"] == "vacio"
    p3 = _paso(R.evaluar_ruta(e, _con(_h(), [_af("Crosses the blood-brain barrier at a dose of 10 mg/kg", tipo="dato")])), "exposicion")
    assert p3["estado"] == "cubierto" and "blood-brain barrier" in p3["motivo"]
    assert _paso(R.evaluar_ruta(e, _con(_h(), [_af("Una dosis de 10 mg/kg por vía oral", tipo="dato")])), "exposicion")["estado"] == "cubierto"
    # "amyloid clearance" es mecanismo, no farmacocinética.
    assert _paso(R.evaluar_ruta(e, _con(_h(), [_af("Amyloid clearance is impaired")])), "exposicion")["estado"] == "vacio"


def test_replicacion_independiente_por_cohortes_del_catalogo():
    e = _e()
    fuentes = [_f("f1", "A, 2024", cohorte="ADNI"), _f("f2", "B, 2025", cohorte="Swedish BioFINDER-2")]
    h = _con(_h(), [_af("GFAP sube", ref="A, 2024"), _af("GFAP sube", ref="B, 2025")], fuentes)
    p = _paso(R.evaluar_ruta(e, h), "replicacion_independiente")
    assert p["estado"] == "cubierto" and "ADNI" in p["motivo"] and "BioFINDER" in p["motivo"] and len(p["evidencia"]) == 2
    # Alias de la misma cohorte: una sola.
    h2 = _con(_h(), [_af("GFAP sube", ref="A, 2024"), _af("GFAP sube", ref="B, 2025")], [_f("f1", "A, 2024", cohorte="ADNI"), _f("f2", "B, 2025", cohorte="Alzheimer's Disease Neuroimaging Initiative")])
    p2 = _paso(R.evaluar_ruta(e, h2), "replicacion_independiente")
    assert p2["estado"] == "parcial" and "una sola cohorte" in p2["motivo"]
    # Fuentes sin cohorte: no se puede afirmar independencia: no comprobable.
    h3 = _con(_h(), [_af("GFAP sube", ref="A, 2024")], [_f("f1", "A, 2024"), _f("f2", "B, 2025")])
    p3 = _paso(R.evaluar_ruta(e, h3), "replicacion_independiente")
    assert p3["estado"] == "no_comprobable" and "ninguna con cohorte identificada" in p3["motivo"]
    # Las cohortes que solo contradicen no replican el efecto.
    h4 = _con(_h(), [_af("GFAP no cambia", ref="A, 2024", relacion="contradice"), _af("GFAP no cambia", ref="B, 2025", relacion="contradice")], fuentes)
    p4 = _paso(R.evaluar_ruta(e, h4), "replicacion_independiente")
    assert p4["estado"] == "vacio" and "no aportan apoyo" in p4["motivo"]


def test_evidencia_en_poblacion_por_n_y_diseno_humano():
    e = _e()
    h = _con(_h(), [_af("GFAP was higher in 120 carriers", tipo="dato", n="n = 120", fuenteId="f1")], [_f("f1", "A, 2024", "cohorte")])
    p = _paso(R.evaluar_ruta(e, h), "evidencia_poblacion")
    assert p["estado"] == "cubierto" and "n >= 50" in p["motivo"] and p["evidencia"][0]["texto"].startswith("n = 120 (cohorte)")
    # n pequeño: parcial. Emparejamiento por cita cuando no hay fuenteId.
    h2 = _con(_h(), [_af("GFAP sube", tipo="dato", n="30", ref="A, 2024")], [_f("f1", "A, 2024", "caso_control")])
    p2 = _paso(R.evaluar_ruta(e, h2), "evidencia_poblacion")
    assert p2["estado"] == "parcial" and "casos y controles" in p2["motivo"]
    # Preclínico: vacío con el diseño nombrado. Sin tipo de estudio: no comprobable.
    h3 = _con(_h(), [_af("GFAP sube en 5xFAD", tipo="dato", n="200", fuenteId="f1")], [_f("f1", "A, 2024", "preclinico")])
    p3 = _paso(R.evaluar_ruta(e, h3), "evidencia_poblacion")
    assert p3["estado"] == "vacio" and "preclínico" in p3["motivo"]
    h4 = _con(_h(), [_af("GFAP sube", tipo="dato", n=200, fuenteId="f1")], [_f("f1", "A, 2024", "otro")])
    p4 = _paso(R.evaluar_ruta(e, h4), "evidencia_poblacion")
    assert p4["estado"] == "no_comprobable" and "tipo de estudio" in p4["motivo"]
    # Revisión sistemática: no cuenta, y se explica. n como entero y como "1.200".
    h5 = _con(_h(), [_af("Pooled n of 1.200", tipo="dato", n="1.200 participantes", fuenteId="f1")], [_f("f1", "A, 2024", "revision_sistematica")])
    p5 = _paso(R.evaluar_ruta(e, h5), "evidencia_poblacion")
    assert p5["estado"] == "vacio" and "estudio primario" in p5["motivo"]
    h6 = _con(_h(), [_af("RCT with 1200 participants", tipo="dato", n="1.200", fuenteId="f1")], [_f("f1", "A, 2024", "ensayo_aleatorizado")])
    assert _paso(R.evaluar_ruta(e, h6), "evidencia_poblacion")["estado"] == "cubierto"


# -- Coherencia del paso declarado ------------------------------------------------


def test_coherencia_del_paso_declarado_con_el_primer_vacio():
    e = _e()
    h = _con(_h(tarjeta=_tarjeta(pasoRuta="efecto_funcional")), [])
    ev = R.evaluar_ruta(e, h)
    assert ev["declarado"] == "efecto_funcional" and ev["coherente"] is False and "va por delante" in ev["motivoCoherencia"] and "«Mecanismo» sigue vacío" in ev["motivoCoherencia"]
    h["tarjeta"]["pasoRuta"] = "mecanismo"
    ev = R.evaluar_ruta(e, h)
    assert ev["coherente"] is True and "no va por delante" in ev["motivoCoherencia"]
    # Con el mecanismo cubierto, declarar opciones de intervención (el primer vacío) es coherente.
    h2 = _con(_h(tarjeta=_tarjeta(pasoRuta="opciones_intervencion")), [_af("GFAP sube"), _af("GFAP sube más")])
    ev2 = R.evaluar_ruta(e, h2)
    assert _estados(ev2)["mecanismo"] == "cubierto" and ev2["siguiente"] == "opciones_intervencion" and ev2["coherente"] is True
    h2["tarjeta"]["pasoRuta"] = "compromiso_diana"
    assert R.evaluar_ruta(e, h2)["coherente"] is False
    # Un paso parcial o no comprobable no rompe la coherencia: solo el vacío.
    h3 = _con(_h(tarjeta=_tarjeta(intervencion="x", direccion="aumenta", pasoRuta="compromiso_diana")), [_af("GFAP sube"), _af("GFAP sube más")])
    ev3 = R.evaluar_ruta(e, h3)
    assert _estados(ev3)["compromiso_diana"] == "no_comprobable" and ev3["coherente"] is True
    # Tarjeta antigua sin pasoRuta: declara mecanismo (el valor de hoy). Paso desconocido: no se contrasta.
    h4 = _h(tarjeta={"diana": "", "celula": "", "etapa": "", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "", "riesgos": []})
    ev4 = R.evaluar_ruta(e, h4)
    assert ev4["declarado"] == "mecanismo" and ev4["coherente"] is True
    h4["tarjeta"]["pasoRuta"] = "paso_inventado"
    ev5 = R.evaluar_ruta(e, h4)
    assert ev5["declarado"] == "paso_inventado" and ev5["coherente"] is True and "no es un paso de la ruta" in ev5["motivoCoherencia"]


# -- Registros antiguos y entradas rotas --------------------------------------------


def test_hipotesis_antigua_sin_tarjeta_ni_claves_nuevas_no_rompe():
    e = _e()
    vieja = {"id": "hip-vieja", "investigacionId": INV, "titulo": "Vieja", "enunciado": "E", "afirmaciones": [{"texto": "GFAP sube", "cita": "[A, pág. 1]", "veredicto": "sostenida", "tipo": "literatura"}], "procedencia": {"fuentes": [{"id": "f1", "referencia": "A"}]}}
    ev = R.evaluar_ruta(e, vieja)
    assert ev["declarado"] is None and ev["coherente"] is True and _estados(ev)["mecanismo"] == "parcial" and ev["hipotesisId"] == "hip-vieja"
    assert _estados(ev)["replicacion_independiente"] == "no_comprobable" and _estados(ev)["evidencia_poblacion"] == "no_comprobable"
    # Entradas rotas: None, cadenas donde van listas, números donde van diccionarios.
    for e_, h_ in ((None, None), ({}, {}), ("x", 3), (e, {"afirmaciones": "texto", "tarjeta": "x", "experimento": 3, "procedencia": None, "grafoCausal": [], "ejecuciones": "run-1", "entidades": {"id": 1}})):
        r = R.evaluar_ruta(e_, h_)
        assert len(r["pasos"]) == 8 and r["cubiertos"] == 0 and r["siguiente"] == "mecanismo"
        json.dumps(r, ensure_ascii=False)
    # Determinista: dos evaluaciones iguales.
    h = _con(_h(tarjeta=_tarjeta(diana="GFAP", riesgos=["r"])), [_af("Plasma GFAP 120 pg/mL", tipo="dato", n="120", fuenteId="f1")], [_f("f1", "A, 2024", cohorte="ADNI")])
    assert R.evaluar_ruta(e, h) == R.evaluar_ruta(e, h)


def test_ids_repetidos_y_hechos_heredados_cuentan_una_vez():
    e = _e()
    a = _af("GFAP sube")
    h = _con(_h(), [a, dict(a)])  # la misma afirmación dos veces (fusión que heredó un duplicado)
    hecho = P.nuevo_hecho(INV, "hecho", "GFAP", "El GFAP sube con la carga amiloide", "sabido", "fuente", [], 1000, afirmacion_ids=[a["afirmacionId"]])
    heredado = dict(hecho, id=f"{hecho['id']}-{INV}")  # copiado de otra investigación: sufijo '-inv-'
    e["hechos"] += [hecho, dict(hecho), heredado, dict(heredado)]
    p = _paso(R.evaluar_ruta(e, h), "mecanismo")
    # Dos ids de hecho distintos (el original y el heredado), cada uno una vez; la afirmación repetida cuenta como dos apoyos porque así la cuenta certeza.py.
    assert [x["tipo"] for x in p["evidencia"]].count("hecho") == 2 and p["estado"] == "cubierto"
    # La evidencia se recorta a MAX_EVIDENCIA, el motivo lo dice y el recorte reparte por tipos:
    # el hecho enlazado sigue visible aunque haya quince afirmaciones delante.
    afs = [_af(f"GFAP sube {i}") for i in range(15)]
    h2 = _con(_h(), afs)
    e["hechos"].append(P.nuevo_hecho(INV, "hecho", "GFAP", "Hecho enlazado a la última", "sabido", "fuente", [], 1000, afirmacion_ids=[afs[-1]["afirmacionId"]]))
    p2 = _paso(R.evaluar_ruta(e, h2), "mecanismo")
    assert len(p2["evidencia"]) == R.MAX_EVIDENCIA and "10 de 16" in p2["motivo"] and [x["tipo"] for x in p2["evidencia"]].count("hecho") == 1
    assert p2["evidencia"][0]["tipo"] == "afirmacion" and p2["evidencia"][1]["tipo"] == "hecho"  # por turnos, en el orden de llegada


# -- Mapa por diana ------------------------------------------------------------------


def test_clave_diana_por_tarjeta_biomarcador_entidades_o_nada():
    assert R.clave_diana(_h(tarjeta=_tarjeta(diana="GFAP")))["clave"] == "HGNC:4235"
    assert R.clave_diana(_h(tarjeta=_tarjeta(diana="neurofilament light chain")))["clave"] == "HGNC:7739"
    assert R.clave_diana(_h(comprobacion={"biomarcador": "p-tau181", "cohorte": "", "diseno": ""}))["origen"] == "biomarcador"
    c = R.clave_diana(_h(tarjeta=_tarjeta(diana="proteína X rara")))
    assert c["clave"] == "texto:proteína x rara" and c["etiqueta"] == "proteína X rara"
    # La diana casa con una entidad resuelta por HGNC aunque no esté en el diccionario curado.
    c2 = R.clave_diana(_h(tarjeta=_tarjeta(diana="TREM2"), entidades=[{"id": "MONDO:0004975", "etiqueta": "Alzheimer disease", "tipo": "enfermedad", "alias": []}, {"id": "HGNC:17761", "etiqueta": "TREM2", "tipo": "gen", "alias": ["TREM-2"]}]))
    assert c2["clave"] == "HGNC:17761"
    # Sin tarjeta ni biomarcador: la primera entidad que no sea una enfermedad; sin nada, sin_diana.
    assert R.clave_diana(_h(entidades=[{"id": "MONDO:0004975", "etiqueta": "Alzheimer disease", "tipo": "enfermedad"}, {"id": "GO:0150076", "etiqueta": "neuroinflammatory response", "tipo": "proceso"}]))["clave"] == "GO:0150076"
    assert R.clave_diana(_h())["clave"] == "sin_diana" and R.clave_diana(None)["clave"] == "sin_diana"


def test_mapa_con_dos_hipotesis_y_un_hueco():
    e = _e()
    h1 = _con(_h(tarjeta=_tarjeta(diana="GFAP", intervencion="anticuerpo anti-GFAP", direccion="disminuye"), conclusion={"certeza": "baja", "direccion": "apoya"}), [_af("Plasma GFAP 120 pg/mL en 200 portadores", tipo="dato", nivelMedicion="medida", n="200", fuenteId="f1"), _af("GFAP sube en ADNI", fuenteId="f1")], [_f("f1", "A, 2024", "cohorte", cohorte="ADNI")])
    h1b = _con(_h(tarjeta=_tarjeta(diana="glial fibrillary acidic protein"), conclusion={"certeza": "moderada", "direccion": "apoya"}), [_af("GFAP sube"), _af("GFAP sube más")])
    h2 = _h(tarjeta=_tarjeta(diana="NfL"))
    descartada = _h(tarjeta=_tarjeta(diana="tau"), estado="descartada")
    fusionada = _h(tarjeta=_tarjeta(diana="APOE"), fusionadaEn=h1["id"])
    otra_inv = P.nueva_hipotesis("inv-otra", 1, 1000, tarjeta=_tarjeta(diana="TREM2"))
    e["hipotesis"] += [h1, dict(h1), h1b, h2, descartada, fusionada, otra_inv]  # h1 repetida: cuenta una vez
    e["hechos"].append(P.nuevo_hecho(INV, "hecho", "NfL", "Un anticuerpo anti-NfL no existe; el NfL marca daño axonal", "sabido", "fuente", [], 1000))
    e["hechos"].append(P.nuevo_hecho(INV, "hecho", "NfL", "Descartado", "descartado", "fuente", [], 1000))
    m = R.mapa_ruta(e, INV)
    assert [f["etiqueta"] for f in m["filas"]] == ["GFAP", "NEFL (NfL)"] and m["filas"][0]["hipotesis"] == [h1["id"], h1b["id"]]
    gfap = m["filas"][0]["pasos"]
    assert gfap["mecanismo"] == {"hipotesis": 2, "parciales": 0, "hechos": 0, "certezaMax": "moderada"}
    assert gfap["opciones_intervencion"]["hipotesis"] == 1 and gfap["opciones_intervencion"]["certezaMax"] == "baja"
    assert gfap["compromiso_diana"]["hipotesis"] == 1 and gfap["exposicion"]["hipotesis"] == 1 and gfap["evidencia_poblacion"]["hipotesis"] == 1
    assert gfap["replicacion_independiente"]["hipotesis"] == 0 and gfap["replicacion_independiente"]["parciales"] == 1  # una sola cohorte
    assert m["filas"][0]["huecos"] == ["efecto_funcional", "selectividad_toxicidad"]
    nfl = m["filas"][1]
    # Sin hipótesis que cubra nada, el hecho sobre NfL toca el mecanismo y las opciones de intervención (nombra un anticuerpo).
    assert nfl["hechos"] == 1 and nfl["pasos"]["mecanismo"]["hechos"] == 1 and nfl["pasos"]["opciones_intervencion"]["hechos"] == 1
    assert nfl["huecos"] == ["compromiso_diana", "efecto_funcional", "selectividad_toxicidad", "exposicion", "replicacion_independiente", "evidencia_poblacion"]
    assert "2 dianas o procesos" in m["resumen"] and "3 hipótesis vivas" in m["resumen"] and "GFAP" in m["resumen"] and "Efecto funcional" in m["resumen"] and "Selectividad y toxicidad" in m["resumen"]
    json.dumps(m, ensure_ascii=False)
    assert R.mapa_ruta(e, "inv-inexistente")["filas"] == [] and "Sin hipótesis vivas" in R.mapa_ruta(None, INV)["resumen"]


# -- Texto en castellano -----------------------------------------------------------


def test_texto_ruta_explica_cada_paso_y_acepta_hipotesis_o_evaluacion():
    e = _e()
    h = _con(_h(tarjeta=_tarjeta(diana="GFAP", pasoRuta="mecanismo")), [_af("Plasma GFAP 120 pg/mL", tipo="dato", nivelMedicion="medida"), _af("GFAP sube")])
    t = R.texto_ruta(h, e)
    assert t.startswith("Ruta terapéutica: ") and "1. Mecanismo (qué proceso biológico" in t and "3. Compromiso de diana (" in t and ": cubierto." in t
    assert "   - [afirmación] Plasma GFAP 120 pg/mL" in t and "8. Evidencia en la población" in t
    assert R.texto_ruta(R.evaluar_ruta(e, h)) == t
    # Sin estado, evalúa sin hechos ni ejecuciones y no rompe.
    assert "Ruta terapéutica" in R.texto_ruta(h) and "Ruta terapéutica" in R.texto_ruta(None)
    # Todo el texto en castellano lleva sus tildes: no aparecen las formas sin acento más comunes.
    # Se arman por concatenación para que la pasada de tildes (scripts/acentuar_py.py) no las "corrija".
    sin_tilde = [a + b for a, b in ((" hipo", "tesis"), ("poblaci", "on"), ("replicaci", "on"), ("intervenci", "on"), ("exposici", "on"), ("f", "armaco"), ("vac", "io."))]
    for palabra in sin_tilde:
        assert palabra not in t.lower().replace("_", " "), palabra


# -- Adversarios: lo que rompió la primera versión y ya no rompe ------------------------


def test_replicacion_con_afirmaciones_sin_verificar_es_no_comprobable():
    """Dos fuentes con cohorte y todas las afirmaciones sin verificar: las
    cohortes esperan, no "solo contradicen". Antes salía vacío con ese motivo falso."""
    e = _e()
    fuentes = [_f("f1", "A, 2024", cohorte="ADNI"), _f("f2", "B, 2025", cohorte="Swedish BioFINDER-2")]
    h = _con(_h(), [_af("GFAP sube", veredicto="sin_verificar", ref="A, 2024"), _af("GFAP sube", veredicto="", ref="B, 2025")], fuentes)
    p = _paso(R.evaluar_ruta(e, h), "replicacion_independiente")
    assert p["estado"] == "no_comprobable" and "sin verificar" in p["motivo"] and "a la espera" in p["motivo"] and "contradicen" not in p["motivo"]
    assert [x["tipo"] for x in p["evidencia"]] == ["fuente", "fuente"]
    # Con una verificada que contradice y otra sin verificar, las cohortes no replican y el motivo lo dice sin acusar en falso.
    h2 = _con(_h(), [_af("GFAP no cambia", ref="A, 2024", relacion="contradice"), _af("GFAP sube", veredicto="sin_verificar", ref="B, 2025")], fuentes)
    p2 = _paso(R.evaluar_ruta(e, h2), "replicacion_independiente")
    assert p2["estado"] == "vacio" and "siguen sin verificar" in p2["motivo"]


def test_replicacion_resuelve_el_nct_por_el_catalogo_y_solo_lista_las_que_apoyan():
    """Una fuente con solo `nct` (sin campo cohorte) es una cohorte del
    catálogo (NCT02008357 es A4); antes se contaba como "no aporta apoyo"."""
    e = _e()
    h = _con(_h(), [_af("GFAP sube", ref="A, 2024")], [_f("f1", "A, 2024", nct="NCT02008357")])
    p = _paso(R.evaluar_ruta(e, h), "replicacion_independiente")
    assert p["estado"] == "parcial" and "A4" in p["motivo"] and p["evidencia"][0]["texto"].endswith("cohorte NCT02008357")
    # A4 por NCT más ADNI por nombre: dos cohortes. Una tercera que solo contradice no entra en la evidencia del paso.
    fuentes = [_f("f1", "A, 2024", nct="NCT02008357"), _f("f2", "B, 2025", cohorte="ADNI"), _f("f3", "C, 2023", cohorte="BioFINDER")]
    h2 = _con(_h(), [_af("GFAP sube", ref="A, 2024"), _af("GFAP sube", ref="B, 2025"), _af("GFAP no cambia", ref="C, 2023", relacion="contradice")], fuentes)
    p2 = _paso(R.evaluar_ruta(e, h2), "replicacion_independiente")
    assert p2["estado"] == "cubierto" and "A4" in p2["motivo"] and "ADNI" in p2["motivo"] and "BioFINDER" not in p2["motivo"]
    assert [x["id"] for x in p2["evidencia"]] == ["f1", "f2"]
    # Fuentes sin cohorte ni NCT siguen siendo no comprobables y el motivo nombra los dos campos.
    h3 = _con(_h(), [_af("GFAP sube", ref="A, 2024")], [_f("f1", "A, 2024")])
    p3 = _paso(R.evaluar_ruta(e, h3), "replicacion_independiente")
    assert p3["estado"] == "no_comprobable" and "NCT" in p3["motivo"]


def test_efecto_funcional_no_confunde_etiquetas_de_poblacion_con_desenlaces():
    """"Cognitively unimpaired", "deterioro cognitivo leve", "Memory and Aging
    Project" o "functional connectivity" describen a quién se midió o con qué,
    no un desenlace. Antes cualquier dato con esas palabras cubría el paso."""
    e = _e()
    for texto in (
        "Plasma GFAP was 120 pg/mL in cognitively unimpaired carriers",
        "GFAP was higher in the Rush Memory and Aging Project",
        "Functional connectivity MRI showed a GFAP association",
        "GFAP en deterioro cognitivo leve: 100 pg/mL",
        "GFAP en participantes cognitivamente sanos: 80 pg/mL",
        "Participants were recruited from a memory clinic",
    ):
        p = _paso(R.evaluar_ruta(e, _con(_h(), [_af(texto, tipo="dato", nivelMedicion="medida")])), "efecto_funcional")
        assert p["estado"] == "vacio", (texto, p["motivo"])
    # Los desenlaces de verdad siguen contando, en inglés y en castellano.
    for texto in ("Cognitive decline was faster in high-GFAP participants", "Progression to dementia was faster", "La progresión a demencia fue más rápida", "MMSE declined 2 points", "Dementia onset occurred earlier in carriers"):
        p = _paso(R.evaluar_ruta(e, _con(_h(), [_af(texto, tipo="dato", nivelMedicion="medida")])), "efecto_funcional")
        assert p["estado"] == "cubierto", (texto, p["motivo"])


def test_opciones_de_intervencion_no_confunden_inhibitory_con_inhibidor():
    e = _e()
    assert _paso(R.evaluar_ruta(e, _con(_h(tarjeta=_tarjeta()), [_af("Inhibitory interneurons were lost in CA1")])), "opciones_intervencion")["estado"] == "vacio"
    for texto in ("A GFAP inhibitor reduced astrogliosis", "Inhibition of GSK3 lowered p-tau", "La inhibición de GSK3 bajó p-tau", "Un inhibidor de BACE1"):
        assert _paso(R.evaluar_ruta(e, _con(_h(tarjeta=_tarjeta()), [_af(texto)])), "opciones_intervencion")["estado"] == "parcial", texto


def test_selectividad_excitotoxicidad_es_mecanismo_y_la_marca_de_toxicidad_se_lee_en_mayusculas():
    e = _e()
    assert _paso(R.evaluar_ruta(e, _con(_h(tarjeta=_tarjeta()), [_af("Glutamate excitotoxicity drives neuronal loss", tipo="dato")])), "selectividad_toxicidad")["estado"] == "vacio"
    assert _paso(R.evaluar_ruta(e, _con(_h(tarjeta=_tarjeta()), [_af("Cytotoxicity of the compound at 10 µM", tipo="dato")])), "selectividad_toxicidad")["estado"] == "cubierto"
    h = _h(experimento={"estado": "datos_recibidos", "resultado": {"clasificacion": "inconcluso", "resultado": "x", "dimensiones": {"toxicidad": "TRUE"}}})
    assert _paso(R.evaluar_ruta(e, h), "selectividad_toxicidad")["estado"] == "cubierto"
    h["experimento"]["resultado"]["dimensiones"]["toxicidad"] = "false"
    assert _paso(R.evaluar_ruta(e, h), "selectividad_toxicidad")["estado"] == "parcial"


def test_registros_sin_id_no_se_funden_en_uno():
    """Tres hechos sin id son tres hechos; dos ejecuciones con id vacío son
    dos; dos hipótesis sin id son dos filas de hipótesis. Antes el
    deduplicado por id vacío se quedaba con una sola."""
    e = _e()
    h = _con(_h(), [_af("GFAP sube")])
    a = h["afirmaciones"][0]
    for i in range(3):
        x = P.nuevo_hecho(INV, "hecho", "GFAP", f"Hecho {i} sin id", "sabido", "fuente", [], 1000, afirmacion_ids=[a["afirmacionId"]])
        x["id"] = None
        e["hechos"].append(x)
    p = _paso(R.evaluar_ruta(e, h), "mecanismo")
    assert [x["tipo"] for x in p["evidencia"]].count("hecho") == 3 and "3 hechos" in p["motivo"]
    e2 = _e()
    h2 = _h(tarjeta=_tarjeta(diana="GFAP"))
    for _ in range(2):
        x = _ejecucion(h2, veredicto="valido")
        x["id"] = ""
        e2["ejecuciones"].append(x)
    p2 = _paso(R.evaluar_ruta(e2, h2), "compromiso_diana")
    assert p2["estado"] == "cubierto" and len(p2["evidencia"]) == 2 and p2["motivo"].startswith("2 análisis in silico")
    e3 = _e()
    h3, h4 = _h(), _h()
    h3["id"] = None
    h4["id"] = None
    e3["hipotesis"] += [h3, h4]
    m = R.mapa_ruta(e3, INV)
    assert m["filas"][0]["hipotesis"] == [None, None] and "2 hipótesis vivas" in m["resumen"]


def test_afirmacion_antigua_sin_id_no_se_enlaza_con_un_hecho_por_su_posicion():
    """El id de respaldo 'afirmacion-1' sirve para mostrar la evidencia, no
    para emparejar: un hecho con afirmacionIds ['afirmacion-1'] no es suyo."""
    e = _e()
    h = _con(_h(), [{"texto": "GFAP sube", "cita": "[A]", "veredicto": "sostenida", "tipo": "literatura"}])
    e["hechos"].append(P.nuevo_hecho(INV, "hecho", "x", "Hecho ajeno", "sabido", "fuente", [], 1000, afirmacion_ids=["afirmacion-1"]))
    p = _paso(R.evaluar_ruta(e, h), "mecanismo")
    assert p["estado"] == "parcial" and [x["tipo"] for x in p["evidencia"]] == ["afirmacion"] and p["evidencia"][0]["id"] == "afirmacion-1"


def test_paso_declarado_se_lee_como_identificador():
    e = _e()
    h = _h(tarjeta=_tarjeta(pasoRuta=" Mecanismo "))
    ev = R.evaluar_ruta(e, h)
    assert ev["declarado"] == "mecanismo" and ev["coherente"] is True and "no es un paso" not in ev["motivoCoherencia"]
    h["tarjeta"]["pasoRuta"] = "Efecto_Funcional"
    ev2 = R.evaluar_ruta(e, h)
    assert ev2["declarado"] == "efecto_funcional" and ev2["coherente"] is False


def test_poblacion_con_apoyos_sin_fuente_emparejada_lo_dice():
    e = _e()
    h = _con(_h(), [_af("GFAP sube en 200 personas", tipo="dato", n="200")], [])
    p = _paso(R.evaluar_ruta(e, h), "evidencia_poblacion")
    assert p["estado"] == "no_comprobable" and p["motivo"].startswith("1 apoyo sin fuente emparejada") and "tipo de estudio" not in p["motivo"]


def test_texto_ruta_etiqueta_la_evidencia_en_castellano():
    e = _e()
    h = _con(_h(tarjeta=_tarjeta(diana="GFAP")), [_af("Plasma GFAP 120 pg/mL", tipo="dato", nivelMedicion="medida")])
    e["ejecuciones"].append(_ejecucion(h, veredicto="valido"))
    t = R.texto_ruta(h, e)
    assert "[afirmación] Plasma GFAP" in t and "[análisis in silico] análisis in silico run-" in t and "[afirmacion]" not in t and "[ejecucion]" not in t


def test_mapa_desempata_por_etiqueta_y_clave_y_casa_el_texto_libre_como_palabra_entera():
    e = _e()
    h1 = _h(tarjeta=_tarjeta(diana="Proteína X"))
    h2 = _h(tarjeta=_tarjeta(diana="Proteína XY"))
    h3 = _h(tarjeta=_tarjeta(diana="proteína x"))  # misma clave normalizada que h1
    e["hipotesis"] += [h2, h1, h3]
    e["hechos"].append(P.nuevo_hecho(INV, "hecho", "X", "La proteína X modula la respuesta; la proteína XY no", "sabido", "fuente", [], 1000))
    e["hechos"].append(P.nuevo_hecho(INV, "hecho", "XY", "La proteína XY es tóxica", "sabido", "fuente", [], 1000))
    m = R.mapa_ruta(e, INV)
    assert [f["clave"] for f in m["filas"]] == ["texto:proteína x", "texto:proteína xy"] and m["filas"][0]["hipotesis"] == [h1["id"], h3["id"]]
    # "proteína x" como palabra entera: el primer hecho nombra a las dos; el segundo solo a XY.
    assert m["filas"][0]["hechos"] == 1 and m["filas"][1]["hechos"] == 2
    assert m["filas"][0]["pasos"]["opciones_intervencion"]["hechos"] == 1 and m["filas"][1]["pasos"]["selectividad_toxicidad"]["hechos"] == 1
    assert R.mapa_ruta(e, INV) == m
