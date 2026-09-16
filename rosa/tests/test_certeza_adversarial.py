"""Intentos de romper rosa/certeza.py (16 de septiembre de 2026): entradas
vacías o de tipo equivocado, valores no hashables, mayúsculas, referencias
ambiguas, el mismo artículo citado en varias páginas, ids repetidos, coste con
miles de afirmaciones, determinismo, no mutación y textos con tilde y sin
guiones largos. Cada test fija un fallo que existió y cómo debe comportarse."""
import copy
import random
import re
import time

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


PUBLICAS_CON_H = ("techo", "balance_pesos", "cohortes_distintas", "fuentes_sin_cohorte", "sostenidas_reales", "evidencia_directa", "apoyos", "contras")


def test_none_y_tipos_equivocados_en_toda_la_api_publica_valen_como_vacio():
    # Antes: AttributeError ('NoneType' object has no attribute 'get') en todas.
    for h in (None, "texto", 3, [], [{"afirmaciones": []}], {"afirmaciones": None, "procedencia": None}):
        for nombre in PUBLICAS_CON_H:
            getattr(C, nombre)(h)
        assert C.techo(h) == ("muy_baja", "no hay ninguna afirmación sostenida que no sea sintética")
        assert C.balance_pesos(h) == {"aFavor": 0.0, "enContra": 0.0, "socavadas": 0, "detalle": "0 apoyos con peso 0 a favor. 0 en contra con peso 0"}
        assert [p["a"] for p in C.escalera(h, "muy_baja")] == ["baja", "moderada", "alta"] and C.escalera(h, None)[0]["a"] == "baja"
        assert C.acotar("alta", h)["certeza"] == "muy_baja" and C.acotar(None, h)["techo"]["certezaDelJuez"] == "muy_baja"
    for a in (None, "texto", 3, ["apoya"]):
        assert C.fuente_de({}, a) is None and C.fuente_de(None, a) is None
        assert C.peso_afirmacion(a)["peso"] == 0.0 and C.peso_afirmacion(a, "fuente")["factores"][1]["motivo"].startswith("sin fuente emparejada")
        assert C.socavada(a) is False
    assert C.etiqueta_relacion(["apoya"]) == "relación sin clasificar" and C.etiqueta_relacion({"a": 1}) == "relación sin clasificar"


def test_valores_no_hashables_no_rompen_y_no_cuentan_ni_penalizan():
    # Antes: TypeError (unhashable type: 'list') al buscar en PESO_DISENO, PESO_SESGO o ETIQUETAS_RELACION.
    f = {"id": "f0", "referencia": "Ref 0", "cohorte": "ADNI", "tipoEstudio": ["revision_narrativa"], "riesgoSesgo": {"global": ["alto"]}}
    a = dict(_af(0), fuenteId="f0")
    r = C.peso_afirmacion(a, f)
    assert r["peso"] == 1.0 and r["factores"][1]["valor"] == 1.0 and r["factores"][2]["valor"] == 1.0
    h = _h([a], [f])
    assert C.techo(h)[0] == "muy_baja" and C.balance_pesos(h)["aFavor"] == 1.0 and C.cohortes_distintas(h) == ["ADNI"]
    # relacion, veredicto o clase como lista: no cuenta, sin excepción.
    rara = dict(_af(1), relacion=["apoya"])
    assert C.apoyos(_h([rara], [])) == [] and C.contras(_h([rara], [])) == [] and "sin clasificar" in C.peso_afirmacion(rara)["factores"][0]["motivo"]
    assert C.apoyos(_h([dict(_af(1), veredicto=["sostenida"])], [])) == []
    assert C.evidencia_directa(_h([dict(_af(1), clase=["derivado"])], [])) == [] and C.apoyos(_h([dict(_af(1), clase=["derivado"])], [])) != []
    # fuenteId o id de fuente no hashables: se empareja por la cita.
    assert C.fuente_de(_h([], [{"id": ["x"], "referencia": "Ref 1", "cohorte": "A4"}]), dict(_af(1), fuenteId={"a": 1}))["cohorte"] == "A4"
    # riesgoSesgo que no es diccionario, socavadaPor diccionario, n diccionario.
    assert C.peso_afirmacion(_af(0), {"riesgoSesgo": "alto"})["factores"][2]["valor"] == 1.0
    assert C.socavada({"socavadaPor": {"x": 1}}) and C.peso_afirmacion(dict(_af(0), n={"x": 1}))["factores"][3]["valor"] == 1.0


def test_mayusculas_y_espacios_se_normalizan_en_lo_que_se_compara_con_una_tabla():
    # Una relación en mayúsculas cuenta igual (en contra es más conservador, nunca sube).
    h = _h([_af(0), dict(_af(1), relacion=" Contradice ")], [_fuente(0, "BIOCARD"), _fuente(1, "ADNI")])
    assert len(C.contras(h)) == 1 and C.techo(h)[0] == "muy_baja" and "en contra pesa tanto" in C.techo(h)[1]
    assert C.etiqueta_relacion("APOYA") == "a favor" and C.etiqueta_relacion(" socava") == "socava un apoyo" and C.etiqueta_relacion("   ") == "de origen"
    # Diseño y sesgo en mayúsculas penalizan como en minúsculas.
    f = _fuente(0, "BIOCARD", tipoEstudio=" Revision_narrativa", riesgoSesgo={"global": "ALTO"})
    r = C.peso_afirmacion(_af(0), f)
    assert r["peso"] == 0.15 and "revisión narrativa: pesa 0.3" in r["factores"][1]["motivo"] and "riesgo de sesgo alto: pesa 0.5" in r["factores"][2]["motivo"]
    # La certeza del juez en mayúsculas se entiende; una que no existe es muy baja.
    h2 = _h([_af(0), _af(1, "apoya")], [_fuente(0, "BIOCARD"), _fuente(1, "ADNI")])
    assert C.acotar("Baja", h2) == {"certeza": "baja", "techo": {**C.acotar("baja", h2)["techo"], "certezaDelJuez": "baja"}}
    assert C.acotar("altísima", h2)["certeza"] == "muy_baja"
    assert C.escalera(h2, "BAJA")[0]["a"] == "moderada"


def test_dos_fuentes_con_la_misma_referencia_son_una_identidad_al_emparejar():
    # Dos artículos del mismo primer autor y año comparten referencia ("Kim et al., 2025"). Antes, todas las
    # citas se emparejaban con la primera fuente y la segunda, sin afirmaciones "emparejables", contaba como
    # cohorte aunque solo contradijera.
    fuentes = [{"id": "a", "referencia": "Kim et al., 2025", "cohorte": "ADNI"}, {"id": "b", "referencia": "Kim et al., 2025", "cohorte": "A4"}, {"id": "c", "referencia": "Otro, 2020", "cohorte": "BIOCARD"}]
    contras = [{"veredicto": "sostenida", "cita": "[Kim et al., 2025, pág. 1]", "relacion": "contradice"}, {"veredicto": "sostenida", "cita": "[Kim et al., 2025, pág. 9]", "relacion": "contradice"}]
    apoyo = {"veredicto": "sostenida", "cita": "[Otro, 2020, pág. 1]"}
    h = _h(contras + [apoyo], fuentes)
    assert C.cohortes_distintas(h) == ["BIOCARD"] and C.techo(h)[0] == "muy_baja"
    # Si una de las dos apoya, no se puede separar: las dos cuentan (no se afirma lo que no se sabe).
    h2 = _h([dict(contras[0], relacion="apoya"), contras[1], apoyo], fuentes)
    assert C.cohortes_distintas(h2) == ["ADNI", "A4", "BIOCARD"]
    # Con fuenteId manda el id y sí se separan: solo "b" apoya, "a" no aporta cohorte.
    h3 = _h([dict(contras[0], fuenteId="a"), dict(contras[1], relacion="apoya", fuenteId="b"), apoyo], fuentes)
    assert C.cohortes_distintas(h3) == ["A4", "BIOCARD"]
    assert C.fuente_de(h3, h3["afirmaciones"][1])["id"] == "b"


def test_gana_la_referencia_mas_larga_que_encaje_en_la_cita():
    fuentes = [{"id": "a", "referencia": "Kim et al., 2025", "cohorte": "ADNI", "tipoEstudio": "revision_narrativa"}, {"id": "b", "referencia": "Kim et al., 2025, Nature", "cohorte": "A4"}]
    h = _h([{"veredicto": "sostenida", "cita": "[Kim et al., 2025, Nature, pág. 1]"}, {"veredicto": "sostenida", "cita": "[Kim et al., 2025, pág. 4]"}], fuentes)
    assert C.fuente_de(h, h["afirmaciones"][0])["id"] == "b" and C.fuente_de(h, h["afirmaciones"][1])["id"] == "a"
    assert C.balance_pesos(h)["aFavor"] == 1.3  # 1.0 (b, sin diseño) + 0.3 (a, narrativa)
    # Con el orden de las fuentes invertido, lo mismo.
    h["procedencia"]["fuentes"].reverse()
    assert C.fuente_de(h, h["afirmaciones"][0])["id"] == "b" and C.balance_pesos(h)["aFavor"] == 1.3
    # Cita sin corchete, con punto final en la referencia, con espacios de más y en mayúsculas.
    fx = [{"id": "x", "referencia": "Xie   et al., 2026.", "cohorte": "BIOCARD"}]
    for cita in ("[Xie et al., 2026, pág. 7]", "Xie et al., 2026 (resumen)", "[XIE ET AL., 2026.; tabla 2]", "[xie et al., 2026]", "Xie et al., 2026"):
        assert C.fuente_de(_h([], fx), {"cita": cita}) is not None, cita
    for cita in ("[Xie et al., 2026a, pág. 7]", "[Xie et al., 20260]", "[Otro que cita a Xie et al., 2026]", "[", "", "]"):
        assert C.fuente_de(_h([], fx), {"cita": cita}) is None, cita


def test_el_mismo_articulo_en_varias_paginas_cuenta_una_vez_como_fuente_sin_cohorte():
    # Al nacer, la hipótesis lleva una entrada de fuente por (artículo, página): el mismo id repetido.
    entradas = [{"id": "f0", "referencia": "Ref 0", "cohorte": None, "pagina": p} for p in (2, 5, 9)]
    afs = [dict(_af(0), afirmacionId=f"af-{p}", cita=f"[Ref 0, pág. {p}]") for p in (2, 5, 9)]
    h = _h(afs, entradas)
    assert C.fuentes_sin_cohorte(h) == 1 and "1 de sus fuentes no tienen la cohorte identificada" in C.escalera(h, "muy_baja")[0]["falta"]
    assert "(1 fuente sin cohorte identificada" in C.techo(h)[1]
    # Si una de las entradas ya tiene la cohorte nombrada, la identidad no cuenta como sin cohorte.
    entradas[1]["cohorte"] = "ADNI"
    assert C.fuentes_sin_cohorte(h) == 0 and C.cohortes_distintas(h) == ["ADNI"]
    # Dos artículos distintos sin cohorte, sin id ni referencia, siguen siendo dos.
    assert C.fuentes_sin_cohorte(_h([], [{"cohorte": ""}, {"cohorte": None}])) == 2


def test_n_de_numpy_flotante_entero_y_textos_raros():
    valores = {12: 0.7, 19.0: 0.7, 20.0: 0.9, 12.5: 1.0, "n = 1.234": 1.0, "3.000 participantes": 1.0, "0": 1.0, "-5": 1.0, True: 1.0, "n/a": 1.0, "veinte": 1.0}
    for n, esperado in valores.items():
        assert C.peso_afirmacion(dict(_af(0), n=n))["factores"][3]["valor"] == esperado, n
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        return
    assert C.peso_afirmacion(dict(_af(0), n=np.int64(12)))["factores"][3]["valor"] == 0.7
    assert C.peso_afirmacion(dict(_af(0), n=np.float64(120.0)))["factores"][3]["valor"] == 1.0
    assert "muestra mediana" in C.peso_afirmacion(dict(_af(0), n=45))["factores"][3]["motivo"]


def test_ids_repetidos_o_heredados_no_colapsan_ni_rompen():
    # Dos afirmaciones heredadas de otra investigación con el mismo afirmacionId (sufijo -inv-) cuentan las dos.
    a1 = dict(_af(0), afirmacionId="af-7-inv-2")
    a2 = dict(_af(0), afirmacionId="af-7-inv-2", texto="otra")
    h = _h([a1, a2], [_fuente(0, "BIOCARD")])
    assert C.balance_pesos(h)["aFavor"] == 2.0 and len(C.sostenidas_reales(h)) == 2
    # El mismo objeto dos veces en la lista: cuenta dos veces (el registro es el que manda), sin excepción.
    assert C.balance_pesos(_h([a1, a1], [_fuente(0, "BIOCARD")]))["aFavor"] == 2.0
    # socavadaPor que apunta a un id que no existe sigue socavando (lo marcó el integrador; resolverlo es vaciar la lista).
    assert C.apoyos(_h([dict(a1, socavadaPor=["no-existe"])], [])) == []
    # Fuentes con el mismo id y cohortes distintas: una identidad con dos nombres, dos cohortes (catálogo canónico de rosa/metodos.py).
    fs = [{"id": "dup", "referencia": "Ref 0", "cohorte": "ADNI"}, {"id": "dup", "referencia": "Ref 0", "cohorte": "BIOCARD"}]
    assert C.cohortes_distintas(_h([a1], fs)) == ["ADNI", "BIOCARD"] and C.fuentes_sin_cohorte(_h([a1], fs)) == 0


def test_cohortes_en_ingles_y_en_castellano_son_la_misma():
    fs = [{"id": "a", "referencia": "Ref 0", "cohorte": "ADNI cohort"}, {"id": "b", "referencia": "Ref 1", "cohorte": "cohorte ADNI (Kim et al.)"}, {"id": "c", "referencia": "Ref 2", "cohorte": "The study"}]
    h = _h([_af(0), _af(1, "apoya"), _af(2, "apoya")], fs)
    # La etiqueta representativa es la canónica del catálogo (rosa/metodos.py), no el primer nombre tal cual.
    assert C.cohortes_distintas(h) == ["ADNI", "The study"]
    assert C.techo(h)[0] == "baja"


def test_coste_lineal_con_miles_de_afirmaciones_y_cientos_de_fuentes():
    # Antes: 2,3 s en techo y 1,6 s en escalera con 3.000 por 500 (emparejar cada afirmación recorría todas las fuentes).
    rnd = random.Random(7)
    fuentes = [{"id": f"f{i}", "referencia": f"Autor{i} et al., 20{i % 30:02d}", "cohorte": rnd.choice(["ADNI", "BIOCARD", "A4", None]), "tipoEstudio": rnd.choice(["cohorte", "revision_narrativa", None])} for i in range(500)]
    afs = []
    for j in range(3000):
        i = rnd.randrange(500)
        afs.append({"afirmacionId": f"af-{j}", "cita": f"[Autor{i} et al., 20{i % 30:02d}, pág. {j}]", "veredicto": rnd.choice(["sostenida", "parcial", "refutada"]), "tipo": "dato", "clase": rnd.choice(["literatura", "derivado"]), "n": rnd.choice(["", "12", "n = 300"]), "relacion": rnd.choice([None, "apoya", "apoya_indirecta", "contradice", "socava"])})
    h = _h(afs, fuentes)
    t = time.perf_counter()
    C.techo(h)
    C.escalera(h, "muy_baja")
    C.balance_pesos(h)
    assert time.perf_counter() - t < 1.5


def test_determinista_no_muta_la_entrada_y_no_depende_del_orden_de_las_afirmaciones():
    fs = [_fuente(0, "BIOCARD", tipoEstudio="transversal", riesgoSesgo={"global": "alto"}), _fuente(1, "ADNI", tipoEstudio="cohorte"), _fuente(2, None)]
    afs = [dict(_af(0), n="12", socavadaPor=("x",)), _af(1, "apoya", clase="derivado"), _af(2, "contradice"), _af(0, "apoya_indirecta"), _af(1, "socava", socavaA="af-0")]
    h = _h(afs, fs)
    antes = copy.deepcopy(h)
    salidas = (C.techo(h), C.escalera(h, "muy_baja"), C.balance_pesos(h), C.cohortes_distintas(h), C.fuentes_sin_cohorte(h), [C.peso_afirmacion(a, C.fuente_de(h, a)) for a in afs])
    assert h == antes
    assert salidas == (C.techo(copy.deepcopy(h)), C.escalera(copy.deepcopy(h), "muy_baja"), C.balance_pesos(copy.deepcopy(h)), C.cohortes_distintas(copy.deepcopy(h)), C.fuentes_sin_cohorte(copy.deepcopy(h)), [C.peso_afirmacion(a, C.fuente_de(h, a)) for a in afs])
    for semilla in range(5):
        barajadas = list(afs)
        random.Random(semilla).shuffle(barajadas)
        h2 = _h(barajadas, fs)
        assert C.techo(h2)[0] == salidas[0][0] and C.balance_pesos(h2)["aFavor"] == salidas[2]["aFavor"] and C.balance_pesos(h2)["enContra"] == salidas[2]["enContra"]
        assert set(C.cohortes_distintas(h2)) == set(salidas[3])


def test_el_motivo_del_techo_dice_que_resta_peso():
    # Un solo apoyo indirecto (0.5): el motivo fijo habla de narrativas, sesgo y muestras, pero el detalle dice la verdad.
    h = _h([_af(0, "apoya_indirecta")], [_fuente(0, "BIOCARD"), _fuente(1, "ADNI")])
    nivel, motivo = C.techo(h)
    assert nivel == "muy_baja" and "resta peso: apoyo indirecto" in motivo and "cuenta la mitad" in motivo
    # Dos cohortes (la estructura daría baja) pero un apoyo de 0.56 y otro de 0.3: frena el peso y dice por qué.
    h2 = _h([_af(0, n="8"), _af(1, "apoya")], [_fuente(0, "BIOCARD", riesgoSesgo={"global": "algunas_dudas"}), _fuente(1, "ADNI", tipoEstudio="revision_narrativa")])
    nivel, motivo = C.techo(h2)
    assert nivel == "muy_baja" and "resta peso: algunas dudas de sesgo: pesa 0.8; n = 8: muestra pequeña, pesa 0.7; revisión narrativa: pesa 0.3" in motivo and "llegaría a baja" in motivo
    # Cuando la estructura frena igual o más que el peso, el motivo es el de la estructura (el menor de los dos manda).
    h3 = _h([_af(0, n="8")], [_fuente(0, "BIOCARD", riesgoSesgo={"global": "algunas_dudas"})])
    assert C.techo(h3) == ("muy_baja", "solo literatura de una sola cohorte, sin réplica ni evidencia directa")


def test_todo_texto_generado_lleva_tildes_y_no_tiene_guiones_largos():
    sin_tilde = re.compile(r"\b(analisis|replica|revision|hipotesis|sintetica|sintetico|diseno|pequena|afirmacion|poblacion|metodo|relacion|tambien|mas|pagina|preclinico|clinico|estadistico|numero|llegaria|ningun|tamano|medicion|publico|documento|replicacion|indole|valido)\b")
    casos = [
        _h([], []),
        _h([_af(0)], [_fuente(0, None)]),
        _h([_af(0), _af(1, "contradice")], [_fuente(0, "BIOCARD"), _fuente(1, "ADNI")]),
        _h([dict(_af(0), socavadaPor=["af-1"]), _af(1, "socava", socavaA="af-0")], [_fuente(0, "BIOCARD"), _fuente(1, "ADNI")]),
        _h([_af(0, "apoya_indirecta", n="7"), _af(1, "apoya", clase="derivado")], [_fuente(0, "BIOCARD", tipoEstudio="revision_narrativa", riesgoSesgo={"global": "alto"}), _fuente(1, "ADNI", tipoEstudio="otro")]),
        _h([_af(0), _af(1, "apoya", clase="observacion_original"), _af(2, "apoya"), _af(3, "contradice"), _af(4, "contradice")], [_fuente(i, c, tipoEstudio=t) for i, (c, t) in enumerate((("BIOCARD", "in_vitro"), ("ADNI", "preclinico"), ("A4", "transversal"), ("OASIS", "serie_de_casos"), ("DIAN", "cohorte")))]),
    ]
    textos: list[str] = []
    for h in casos:
        for certeza in C.NIVELES:
            textos.append(C.techo(h, [{"factor": "efecto_grande", "efecto": "sube"}])[1])
            textos.extend(p["falta"] for p in C.escalera(h, certeza))
        textos.append(C.balance_pesos(h)["detalle"])
        for a in h["afirmaciones"]:
            textos.extend(f["motivo"] for f in C.peso_afirmacion(a, C.fuente_de(h, a))["factores"])
    for t in textos:
        assert "\u2014" not in t, t  # guion largo
        assert not sin_tilde.search(t), t
