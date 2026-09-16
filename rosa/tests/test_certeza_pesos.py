"""Peso por regla de la evidencia y techo GRADE que distingue apoya, contradice
y socava (16 de septiembre de 2026). Todo determinista y con motivo."""
from rosa import certeza as C


def _fuente(i, cohorte, **k):
    return {"id": f"f{i}", "referencia": f"Ref {i}", "titulo": f"T{i}", "cohorte": cohorte, **k}


def _af(i, relacion=None, veredicto="sostenida", clase="literatura", **k):
    a = {"afirmacionId": f"af-{i}", "texto": f"afirmación {i}", "cita": f"[Ref {i}, pág. {i + 1}]", "veredicto": veredicto, "tipo": "dato", "clase": clase, "sintetico": False, "cohorte": "", **k}
    if relacion is not None:
        a["relacion"] = relacion
    return a


def _h(afirmaciones, fuentes):
    return {"afirmaciones": afirmaciones, "procedencia": {"fuentes": fuentes}}


def test_contradice_no_cuenta_como_sostenida_ni_aporta_cohorte():
    # Dos apoyos de origen de BIOCARD (f0) y una afirmación en contra de ADNI (f1).
    f0, f1 = _fuente(0, "BIOCARD"), _fuente(1, "ADNI")
    origen = [dict(_af(0), afirmacionId="af-0a"), dict(_af(0), afirmacionId="af-0b")]
    contra = _af(1, "contradice", iteracion=3, motivoRelacion="sentido contrario")
    h = _h(origen + [contra], [f0, f1])
    assert [a["afirmacionId"] for a in C.sostenidas_reales(h)] == ["af-0a", "af-0b"]
    assert C.contras(h) == [contra] and C.apoyos(h) == origen
    # La fuente que solo contradice no aporta cohorte: sigue siendo una sola.
    assert C.cohortes_distintas(h) == ["BIOCARD"]
    nivel, motivo = C.techo(h)
    assert nivel == "muy_baja" and "una sola cohorte" in motivo
    # La misma afirmación a favor sí aporta la segunda cohorte y sube el techo a baja.
    h2 = _h(origen + [dict(contra, relacion="apoya")], [f0, f1])
    assert C.cohortes_distintas(h2) == ["BIOCARD", "ADNI"] and C.techo(h2)[0] == "baja"


def test_una_fuente_que_solo_contradice_no_sube_el_techo_a_baja_y_en_contra_igual_da_muy_baja():
    f0, f1 = _fuente(0, "BIOCARD"), _fuente(1, "ADNI")
    # Un apoyo (1.0) y una en contra (1.0): la evidencia en contra pesa tanto como la a favor.
    h = _h([_af(0), _af(1, "contradice")], [f0, f1])
    nivel, motivo = C.techo(h)
    assert nivel == "muy_baja" and "la evidencia en contra pesa tanto o más que la a favor" in motivo
    assert C.acotar("alta", h)["certeza"] == "muy_baja"
    e = C.escalera(h, "muy_baja")
    assert e[0]["a"] == "baja" and "resolver la evidencia en contra" in e[0]["falta"] and "1 afirmación en contra pesa 1" in e[0]["falta"]
    # Solo en contra, sin ningún apoyo: muy baja con el mismo motivo, no "no hay sostenidas".
    nivel, motivo = C.techo(_h([_af(1, "contradice")], [f1]))
    assert nivel == "muy_baja" and "la evidencia en contra pesa tanto o más que la a favor" in motivo and "no queda ningún apoyo" in motivo
    assert C.cohortes_distintas(_h([_af(1, "contradice")], [f1])) == []


def test_socavada_y_socava_quedan_fuera_del_techo_y_de_las_cohortes():
    f0, f1 = _fuente(0, "BIOCARD"), _fuente(1, "ADNI")
    apoyo = dict(_af(0), afirmacionId="af-0", socavadaPor=["af-1"])
    socava = _af(1, "socava", socavaA="af-0", motivoRelacion="la plataforma no mide GFAP en plasma")
    h = _h([apoyo, socava], [f0, f1])
    assert C.socavada(apoyo) and not C.socavada(socava)
    assert C.sostenidas_reales(h) == [] and C.apoyos(h) == [] and C.contras(h) == []
    # Ni la fuente del apoyo socavado ni la de la que socava aportan cohorte.
    assert C.cohortes_distintas(h) == [] and C.fuentes_sin_cohorte(h) == 0
    nivel, motivo = C.techo(h)
    assert nivel == "muy_baja" and "1 apoyo socavado" in motivo
    b = C.balance_pesos(h)
    assert b["aFavor"] == 0.0 and b["enContra"] == 0.0 and b["socavadas"] == 1 and "1 apoyo socavado que no cuenta" in b["detalle"] and "1 afirmación lo socava" in b["detalle"]
    assert C.peso_afirmacion(apoyo)["peso"] == 0.0 and "socavada por 1 afirmación" in C.peso_afirmacion(apoyo)["factores"][0]["motivo"]
    assert C.peso_afirmacion(socava)["peso"] == 0.0 and C.peso_afirmacion(socava)["factores"][0]["valor"] == 0.0
    # Resuelto el ataque (socavadaPor vacío), el apoyo vuelve a contar y su fuente también.
    h2 = _h([dict(apoyo, socavadaPor=[]), socava], [f0, f1])
    assert C.sostenidas_reales(h2) == [dict(apoyo, socavadaPor=[])] and C.cohortes_distintas(h2) == ["BIOCARD"]
    assert "una sola cohorte" in C.techo(h2)[1]


def test_dos_revisiones_narrativas_no_llegan_a_baja_pero_dos_cohortes_primarias_si():
    narrativas = [_fuente(0, "BIOCARD", tipoEstudio="revision_narrativa"), _fuente(1, "ADNI", tipoEstudio="revision_narrativa")]
    h = _h([_af(0), _af(1, "apoya")], narrativas)
    b = C.balance_pesos(h)
    assert b["aFavor"] == 0.6 and b["enContra"] == 0.0 and "revisión narrativa: pesa 0.3" in b["detalle"]
    nivel, motivo = C.techo(h)
    assert nivel == "muy_baja" and "los apoyos son de bajo peso (revisiones narrativas, sesgo alto o muestras pequeñas)" in motivo and "llegaría a baja" in motivo
    e = C.escalera(h, "muy_baja")
    assert e[0]["falta"].startswith("apoyos de más peso: un estudio primario en vez de una revisión narrativa")
    assert C.acotar("baja", h)["certeza"] == "muy_baja" and C.acotar("baja", h)["techo"]["acotada"] is True
    primarias = [_fuente(0, "BIOCARD", tipoEstudio="cohorte"), _fuente(1, "ADNI", tipoEstudio="caso_control")]
    h2 = _h([_af(0), _af(1, "apoya")], primarias)
    assert C.balance_pesos(h2)["aFavor"] == 2.0 and C.techo(h2)[0] == "baja" and "2 cohortes distintas" in C.techo(h2)[1]
    # In vitro (0.6) más preclínico (0.6) suman 1.2 y sí llegan a baja: solo se penaliza lo débil, no se prohíbe.
    h3 = _h([_af(0), _af(1, "apoya")], [_fuente(0, "BIOCARD", tipoEstudio="in_vitro"), _fuente(1, "ADNI", tipoEstudio="preclinico")])
    assert C.balance_pesos(h3)["aFavor"] == 1.2 and C.techo(h3)[0] == "baja"
    # Un diseño débil que no es revisión narrativa recibe su propio remedio en la escalera (0.6 + 0.3 indirecto = 0.9).
    h4 = _h([_af(0), _af(1, "apoya_indirecta")], [_fuente(0, "BIOCARD", tipoEstudio="in_vitro"), _fuente(1, "ADNI", tipoEstudio="preclinico")])
    falta = C.escalera(h4, "muy_baja")[0]["falta"]
    assert C.techo(h4)[0] == "muy_baja" and "diseño más fuerte" in falta and "in vitro" in falta and "preclínico" in falta


def test_umbrales_de_peso_para_moderada_y_alta_con_evidencia_directa():
    f0, f1 = _fuente(0, "BIOCARD"), _fuente(1, "A4")
    silico = _af(1, "apoya", clase="derivado")
    # Dos apoyos (2.0) con evidencia directa de dos cohortes: la estructura da alta, el peso frena en moderada.
    h = _h([_af(0), silico], [f0, f1])
    nivel, motivo = C.techo(h)
    assert nivel == "moderada" and "pesan poco para alta" in motivo and "llegaría a alta" in motivo
    assert "apoyos de más peso: otro apoyo independiente" in C.escalera(h, "moderada")[0]["falta"]
    # Tres apoyos (3.0): alta.
    h3 = _h([_af(0), dict(_af(0), afirmacionId="af-0b"), silico], [f0, f1])
    assert C.techo(h3)[0] == "alta"
    # Tres apoyos y una en contra (1.0 <= 3.0 / 3): sigue en alta.
    assert C.techo(_h([_af(0), dict(_af(0), afirmacionId="af-0b"), silico, _af(2, "contradice")], [f0, f1, _fuente(2, "ADNI")]))[0] == "alta"
    # Tres apoyos y dos en contra (2.0 > 3.0 / 2): ni alta ni moderada; baja, y la escalera pide resolver lo que hay en contra.
    h5 = _h([_af(0), dict(_af(0), afirmacionId="af-0b"), silico, _af(2, "contradice"), _af(3, "contradice")], [f0, f1, _fuente(2, "ADNI"), _fuente(3, "OASIS")])
    nivel, motivo = C.techo(h5)
    assert nivel == "baja" and "pasa de la mitad" in motivo
    e = C.escalera(h5, "baja")
    assert [x["a"] for x in e] == ["moderada", "alta"] and all("resolver la evidencia en contra" in x["falta"] for x in e)
    # Un apoyo indirecto (0.5) más uno directo (1.0) no llegan a moderada aunque haya evidencia directa.
    h6 = _h([_af(0, "apoya_indirecta"), silico], [f0, f1])
    assert C.balance_pesos(h6)["aFavor"] == 1.5 and C.techo(h6)[0] == "moderada"
    h7 = _h([_af(0, "apoya_indirecta"), dict(silico, relacion="apoya_indirecta")], [f0, f1])
    assert C.balance_pesos(h7)["aFavor"] == 1.0 and C.techo(h7)[0] == "baja" and "un apoyo directo en la misma población" in C.escalera(h7, "baja")[0]["falta"]


def test_peso_afirmacion_con_sus_factores_y_balance_en_castellano():
    fuente = _fuente(0, "BIOCARD", tipoEstudio="transversal", riesgoSesgo={"instrumento": "AXIS", "global": "alto"})
    a = _af(0, "apoya", n="12 participantes")
    r = C.peso_afirmacion(a, fuente)
    assert r["peso"] == 0.28  # 1.0 * 0.8 (transversal) * 0.5 (sesgo alto) * 0.7 (n < 20)
    assert [f["factor"] for f in r["factores"]] == ["relacion", "diseno", "sesgo", "n"]
    assert [f["valor"] for f in r["factores"]] == [1.0, 0.8, 0.5, 0.7]
    assert "a favor" in r["factores"][0]["motivo"] and "transversal: pesa 0.8" in r["factores"][1]["motivo"] and "riesgo de sesgo alto: pesa 0.5" in r["factores"][2]["motivo"] and "n = 12" in r["factores"][3]["motivo"]
    assert C.peso_afirmacion(dict(a, relacion="contradice"), fuente)["peso"] == -0.28
    assert C.peso_afirmacion(dict(a, relacion="apoya_indirecta"), fuente)["peso"] == 0.14
    assert C.peso_afirmacion(dict(a, relacion="socava"), fuente)["peso"] == 0.0
    # Sin fuente emparejada ni n: nada penaliza.
    limpio = C.peso_afirmacion(_af(0, "apoya"))
    assert limpio["peso"] == 1.0 and all(f["valor"] == 1.0 for f in limpio["factores"]) and "sin fuente emparejada" in limpio["factores"][1]["motivo"]
    # Tramos de n: 19 / 20 / 99 / 100, como entero, como texto o con separador de miles; desconocido no penaliza.
    assert [C.peso_afirmacion(_af(0, n=n))["factores"][3]["valor"] for n in (19, "20", "99 personas", "n = 100", "n=1,234", "", None, "no consta")] == [0.7, 0.9, 0.9, 1.0, 1.0, 1.0, 1.0, 1.0]
    # Sesgo: algunas dudas 0.8, bajo 1.0, sin evaluar 1.0.
    assert C.peso_afirmacion(a, dict(fuente, riesgoSesgo={"global": "algunas_dudas"}))["factores"][2]["valor"] == 0.8
    assert C.peso_afirmacion(a, dict(fuente, riesgoSesgo={"global": "bajo"}))["factores"][2]["valor"] == 1.0
    assert C.peso_afirmacion(a, dict(fuente, riesgoSesgo=None))["factores"][2]["valor"] == 1.0
    # El balance suma por relación y explica en castellano.
    h = _h([a, dict(_af(1, "contradice"), n="300"), _af(2, "apoya_indirecta")], [fuente, _fuente(1, "ADNI", tipoEstudio="cohorte"), _fuente(2, "OASIS")])
    b = C.balance_pesos(h)
    assert b == {"aFavor": 0.78, "enContra": 1.0, "socavadas": 0, "detalle": b["detalle"]}
    assert b["detalle"].startswith("2 apoyos con peso 0.78 a favor. 1 en contra con peso 1") and "resta peso:" in b["detalle"] and "muestra pequeña" in b["detalle"]


def test_registros_antiguos_sin_relacion_ni_diseno_ni_sesgo_dan_exactamente_lo_de_hoy():
    LIT = {"veredicto": "sostenida", "tipo": "dato", "clase": "literatura", "sintetico": False}
    LAB = {"veredicto": "sostenida", "tipo": "dato", "clase": "observacion_original", "sintetico": False}
    viejas = [{"id": f"f{i}", "cohorte": c} for i, c in enumerate(("biocard", "adni"))]
    assert C.techo(_h([LIT, LIT], viejas)) == ("baja", "solo literatura, sin experimento ni análisis sobre datos reales, aunque de 2 cohortes distintas")
    assert C.techo(_h([LIT, LIT], viejas[:1])) == ("muy_baja", "solo literatura de una sola cohorte, sin réplica ni evidencia directa")
    assert C.techo(_h([LIT, LIT, LAB], viejas))[0] == "alta"
    assert C.balance_pesos(_h([LIT, LIT], viejas)) == {"aFavor": 2.0, "enContra": 0.0, "socavadas": 0, "detalle": "2 apoyos con peso 2 a favor. 0 en contra con peso 0"}
    # Claves ausentes por todas partes: ni tipo, ni clase, ni sintetico, ni id, ni referencia, ni procedencia.
    minima = {"afirmaciones": [{"veredicto": "sostenida"}, {"veredicto": "parcial"}], "procedencia": {"fuentes": [{"cohorte": "biocard"}, {"cohorte": "adni"}]}}
    # El nivel es el de siempre; la etiqueta de cada cohorte es ahora la canónica del catálogo (rosa/metodos.py).
    assert C.techo(minima)[0] == "baja" and len(C.sostenidas_reales(minima)) == 2 and C.cohortes_distintas(minima) == ["BIOCARD", "ADNI"]
    assert C.techo({})[0] == "muy_baja" and C.techo({"afirmaciones": None, "procedencia": None})[0] == "muy_baja"
    assert C.balance_pesos({}) == {"aFavor": 0.0, "enContra": 0.0, "socavadas": 0, "detalle": "0 apoyos con peso 0 a favor. 0 en contra con peso 0"}
    assert C.escalera({}, "muy_baja")[0]["a"] == "baja" and C.escalera({}, "alta") == []
    # Una fuente sin ninguna afirmación emparejable sigue contando (los tests antiguos no enlazan cita con referencia).
    assert C.cohortes_distintas(_h([dict(LIT, cita="[Otra cosa, pág. 1]")], viejas)) == ["BIOCARD", "ADNI"]


def test_fuente_de_empareja_por_id_o_por_cita_de_forma_tolerante():
    fuentes = [{"id": "kim", "referencia": "Kim et al., 2025", "cohorte": "ADNI"}, {"id": "kim2", "referencia": "Kim et al., 2025a", "cohorte": "A4"}, {"id": "xie", "referencia": "Xie et al., 2026.", "cohorte": "BIOCARD"}, {"id": "vacia", "referencia": "", "cohorte": "X"}]
    h = {"afirmaciones": [], "procedencia": {"fuentes": fuentes}}
    assert C.fuente_de(h, {"fuenteId": "xie", "cita": "[Kim et al., 2025, pág. 2]"})["id"] == "xie"  # el id manda sobre la cita
    assert C.fuente_de(h, {"cita": "[Kim et al., 2025, pág. 2]"})["id"] == "kim"
    assert C.fuente_de(h, {"cita": "[Kim et al., 2025a, resumen]"})["id"] == "kim2"  # el prefijo no se confunde con la 2025a
    assert C.fuente_de(h, {"cita": "[KIM  ET AL.,  2025; resumen]"})["id"] == "kim"  # mayúsculas y espacios
    assert C.fuente_de(h, {"cita": "[Xie et al., 2026, pág. 7]"})["id"] == "xie"  # referencia con punto final
    assert C.fuente_de(h, {"cita": "Xie et al., 2026 (resumen)"})["id"] == "xie"  # sin corchete
    assert C.fuente_de(h, {"cita": "[Otro, 2024, pág. 1]"}) is None and C.fuente_de(h, {"cita": ""}) is None and C.fuente_de(h, {}) is None
    assert C.fuente_de(h, {"fuenteId": "no-existe", "cita": ""}) is None
    assert C.fuente_de({"afirmaciones": []}, {"fuenteId": "kim"}) is None  # sin procedencia no rompe
    # Una referencia vacía nunca empareja con todo.
    assert C.fuente_de({"procedencia": {"fuentes": [fuentes[3]]}}, {"cita": "[Cualquiera, pág. 1]"}) is None


def test_etiqueta_relacion():
    assert [C.etiqueta_relacion(r) for r in (None, "apoya", "apoya_indirecta", "contradice", "socava")] == ["de origen", "a favor", "apoyo indirecto", "en contra", "socava un apoyo"]
    assert C.etiqueta_relacion("no_pertinente") == "relación sin clasificar"


def test_adversarial_ids_repetidos_relacion_desconocida_veredictos_y_texto_en_ingles():
    # Dos fuentes con el mismo id y cohortes en inglés que son la misma: una sola cohorte.
    fuentes = [{"id": "dup", "referencia": "Smith et al., 2024", "cohorte": "ADNI cohort"}, {"id": "dup", "referencia": "Smith et al., 2024", "cohorte": "The ADNI study"}]
    a = _af(0, "apoya", fuenteId="dup", cita="[Smith et al., 2024, p. 3]")
    h = _h([a, dict(a, afirmacionId="af-0")], fuentes)
    assert C.cohortes_distintas(h) == ["ADNI"] and C.techo(h)[0] == "muy_baja"
    # La relación que no se reconoce no cuenta ni a favor ni en contra, y lo dice.
    rara = _af(1, "no_pertinente")
    assert C.apoyos(_h([rara], [])) == [] and C.contras(_h([rara], [])) == []
    r = C.peso_afirmacion(rara)
    assert r["peso"] == 0.0 and "sin clasificar" in r["factores"][0]["motivo"]
    # Veredictos que no cuentan aunque la relación sea a favor; lo sintético tampoco.
    for mala in (_af(1, "apoya", veredicto="refutada"), _af(1, "apoya", veredicto="cita_no_resuelve"), dict(_af(1, "apoya"), sintetico=True), {"relacion": "apoya"}):
        assert C.apoyos(_h([mala], [])) == [] and C.peso_afirmacion(mala)["peso"] == 0.0
    # Una fuente cuya única afirmación emparejable está refutada no aporta cohorte; sin emparejar, sí.
    f1 = _fuente(1, "ADNI")
    assert C.cohortes_distintas(_h([_af(0), _af(1, veredicto="refutada")], [_fuente(0, "BIOCARD"), f1])) == ["BIOCARD"]
    assert C.cohortes_distintas(_h([_af(0), dict(_af(1, veredicto="refutada"), cita="[sin referencia]")], [_fuente(0, "BIOCARD"), f1])) == ["BIOCARD", "ADNI"]
    # socavadaPor con None o lista vacía no es socavada.
    assert not C.socavada({"socavadaPor": None}) and not C.socavada({"socavadaPor": []}) and not C.socavada({})
    # El peso es determinista: la misma entrada da la misma salida, y los factores están redondeados.
    assert C.peso_afirmacion(a, fuentes[0]) == C.peso_afirmacion(dict(a), dict(fuentes[0]))
    assert C.peso_afirmacion(_af(0, "apoya", n="7"), _fuente(0, "X", tipoEstudio="revision_narrativa", riesgoSesgo={"global": "alto"}))["peso"] == 0.105


def test_escalera_no_pide_peso_que_la_pieza_estructural_ya_aporta():
    LIT = {"veredicto": "sostenida", "tipo": "dato", "clase": "literatura", "sintetico": False}
    SILICO = {"veredicto": "sostenida", "tipo": "dato", "clase": "derivado", "sintetico": False}
    # Un apoyo de literatura y un análisis in silico de una sola cohorte (2.0): la réplica que pide el
    # peldaño de alta ya aporta el 1.0 que falta para 2.5, así que no se pide peso además.
    e = C.escalera(_h([LIT, SILICO], [_fuente(0, "BIOCARD")]), "moderada")
    assert len(e) == 1 and e[0]["falta"].startswith("réplica de ese resultado directo") and "apoyos de más peso" not in e[0]["falta"]
    # Un solo apoyo (1.0): cada peldaño pide su pieza (segunda cohorte, evidencia directa, réplica) y ninguna nota de peso.
    for p in C.escalera(_h([LIT], [_fuente(0, "BIOCARD")]), "muy_baja"):
        assert "apoyos de más peso" not in p["falta"] and "resolver la evidencia en contra" not in p["falta"]
    # Semilla del vivero sin afirmaciones: tampoco se le pide "apoyos de más peso" (suman 0) por delante de la segunda cohorte.
    e0 = C.escalera({"afirmaciones": [], "procedencia": {"fuentes": [{"id": "x", "cohorte": ""}]}}, "muy_baja")
    assert "no tienen la cohorte identificada" in e0[0]["falta"] and "apoyos de más peso" not in e0[0]["falta"]
    # Baja por efecto grande con una cohorte: el peldaño de moderada no cuenta una segunda cohorte fantasma
    # (ese peldaño no se emite), pero la evidencia directa que pide sí aporta su peso: 1.0 + 1.0 >= 1.5.
    factores = [{"factor": "efecto_grande", "efecto": "sube"}]
    e1 = C.escalera(_h([LIT], [_fuente(0, "BIOCARD")]), "baja", factores)
    assert [p["a"] for p in e1] == ["moderada", "alta"] and all("apoyos de más peso" not in p["falta"] for p in e1)
    # Los peldaños son consecutivos: dos apoyos indirectos de revisiones narrativas (0.15 + 0.15) de dos cohortes.
    # El peldaño de baja exige llegar a 1.0; el de moderada da por cumplido ese peso y la evidencia directa que pide
    # aporta 1.0 más (>= 1.5), y el de alta suma la réplica (>= 2.5): ninguno de los dos repite la nota de peso.
    narrativas = [_fuente(0, "BIOCARD", tipoEstudio="revision_narrativa"), _fuente(1, "ADNI", tipoEstudio="revision_narrativa")]
    e2 = C.escalera(_h([_af(0, "apoya_indirecta"), _af(1, "apoya_indirecta")], narrativas), "muy_baja")
    assert e2[0]["falta"].startswith("apoyos de más peso: un estudio primario en vez de una revisión narrativa (suman 0.3; baja exige al menos 1)")
    assert e2[1]["falta"].startswith("evidencia directa") and "apoyos de más peso" not in e2[1]["falta"]
    assert e2[2]["falta"].startswith("réplica") and "apoyos de más peso" not in e2[2]["falta"]
    # Cuando ni con lo anterior llega, lo dice con las dos cifras: tres apoyos de 0.15 (0.45) de una sola cohorte
    # sin evidencia directa; en baja tendrían 1.0 y la evidencia directa deja 2.0 >= 1.5, pero para alta la réplica
    # deja 3.0 >= 2.5 también. Solo un apoyo indirecto de narrativa (0.15) y baja por efecto grande: la evidencia
    # directa (1.0) deja 1.15 < 1.5 y el peldaño de moderada lo dice.
    e3 = C.escalera(_h([_af(0, "apoya_indirecta")], narrativas[:1]), "baja", [{"factor": "efecto_grande", "efecto": "sube"}])
    assert e3[0]["falta"].startswith("evidencia directa") and "suman 0.15 y con lo anterior llegarían a 1.15; moderada exige al menos 1.5" in e3[0]["falta"]
    assert e3[1]["falta"].startswith("réplica") and "apoyos de más peso" not in e3[1]["falta"]
    # La evidencia en contra que hoy frena se dice siempre, con las cifras de hoy, aunque la segunda cohorte la compensara.
    e3 = C.escalera(_h([_af(0), _af(1, "contradice")], [_fuente(0, "BIOCARD"), _fuente(1, "ADNI")]), "muy_baja")
    assert "segunda cohorte independiente" in e3[0]["falta"] and "resolver la evidencia en contra: 1 afirmación en contra pesa 1 frente a 1 a favor" in e3[0]["falta"]


def test_relacion_vacia_es_de_origen_y_socavada_por_admite_cadena():
    # Una relación vacía ("") es la de origen, igual que la clave ausente: cuenta entera y no es "sin clasificar".
    vacia = dict(_af(0), relacion="")
    h = _h([vacia, _af(1, "contradice")], [_fuente(0, "BIOCARD"), _fuente(1, "ADNI")])
    assert C.apoyos(h) == [vacia] and C.contras(h) == [h["afirmaciones"][1]]
    r = C.peso_afirmacion(vacia)
    assert r["peso"] == 1.0 and r["factores"][0]["motivo"].startswith("de origen")
    assert C.balance_pesos(_h([vacia], [_fuente(0, "BIOCARD")]))["aFavor"] == 1.0
    assert C.etiqueta_relacion("") == "de origen" and C.etiqueta_relacion(None) == "de origen"
    # socavadaPor como una sola cadena cuenta como una afirmación que socava; como tupla, también.
    for valor in ("af-9", ("af-9",), ["af-9"], [None]):
        a = dict(_af(0), socavadaPor=valor)
        assert C.socavada(a) and C.peso_afirmacion(a)["peso"] == 0.0 and "socavada por 1 afirmación que ataca" in C.peso_afirmacion(a)["factores"][0]["motivo"]
    assert "socavada por 2 afirmaciones que atacan" in C.peso_afirmacion(dict(_af(0), socavadaPor=["a", "b"]))["factores"][0]["motivo"]


def test_diseno_sin_reconocer_pesa_la_mitad_y_la_escalera_pide_identificarlo():
    # El clasificador de PubMed devuelve "otro" cuando no reconoce el diseño; pesa 0.5 y el remedio es identificarlo,
    # no "un diseño más fuerte". Dos "otro" de dos cohortes con un apoyo indirecto: 0.5 + 0.25 = 0.75 < 1.
    otros = [_fuente(0, "BIOCARD", tipoEstudio="otro"), _fuente(1, "ADNI", tipoEstudio="otro")]
    h = _h([_af(0), _af(1, "apoya_indirecta")], otros)
    b = C.balance_pesos(h)
    assert b["aFavor"] == 0.75 and "sin diseño reconocido: pesa 0.5" in b["detalle"]
    assert C.techo(h)[0] == "muy_baja" and "suman 0.75 y baja exige al menos 1" in C.techo(h)[1]
    falta = C.escalera(h, "muy_baja")[0]["falta"]
    assert falta.startswith("apoyos de más peso: identificar el diseño de los estudios que constan sin diseño reconocido") and "diseño más fuerte" not in falta
    # Dos "otro" con apoyo directo (0.5 + 0.5 = 1.0) llegan justo a baja: se penaliza, no se prohíbe.
    assert C.techo(_h([_af(0), _af(1, "apoya")], otros))[0] == "baja"
    # Una revisión narrativa y un in vitro juntos reciben los dos remedios, cada uno con su nombre.
    mezcla = _h([_af(0), _af(1, "apoya")], [_fuente(0, "BIOCARD", tipoEstudio="revision_narrativa"), _fuente(1, "ADNI", tipoEstudio="in_vitro")])
    falta = C.escalera(mezcla, "muy_baja")[0]["falta"]
    assert "un estudio primario en vez de una revisión narrativa" in falta and "diseño más fuerte (cohorte, casos y controles o ensayo) en vez de in vitro" in falta


def test_entradas_con_tipos_raros_no_rompen():
    # Cohorte numérica, referencia None, riesgo de sesgo y tipo de estudio que no son lo esperado, socavadaPor entero, n diccionario.
    h = {"procedencia": {"fuentes": [None, "f", 1, {"id": None, "referencia": None, "cohorte": 5, "tipoEstudio": 7, "riesgoSesgo": 9}, {"id": "ok", "cohorte": "ADNI"}]},
         "afirmaciones": [None, "a", 3, {"veredicto": "sostenida", "cita": 5, "fuenteId": 0, "relacion": 3, "socavadaPor": 4, "n": {"x": 1}}, {"veredicto": "sostenida"}]}
    nivel, motivo = C.techo(h)
    assert nivel == "muy_baja" and motivo
    assert C.cohortes_distintas(h) == ["ADNI"] and C.fuentes_sin_cohorte(h) == 1
    assert [p["a"] for p in C.escalera(h, "muy_baja")] == ["baja", "moderada", "alta"]
    assert C.balance_pesos(h)["aFavor"] == 1.0 and C.acotar("alta", h)["certeza"] == "muy_baja"
    for a in C._afirmaciones(h):
        assert C.peso_afirmacion(a, C.fuente_de(h, a))["factores"]
    # afirmaciones o fuentes que no son listas, y procedencia que no es un diccionario.
    for raro in ({"afirmaciones": "x", "procedencia": "y"}, {"afirmaciones": {"a": 1}, "procedencia": {"fuentes": "z"}}, {"afirmaciones": None, "procedencia": None}):
        assert C.techo(raro)[0] == "muy_baja" and C.escalera(raro, "muy_baja") and C.balance_pesos(raro)["aFavor"] == 0.0
