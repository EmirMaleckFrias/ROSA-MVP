"""Marcos de argumentación de Dung sobre las hipótesis: el núcleo puro con
los ejemplos clásicos, los ataques por signo opuesto y declarados, la marca
sobre el estado (sin descartar nada, idempotente) y los casos adversariales
(registros antiguos o rotos, ids repetidos, títulos iguales, escala)."""

import copy
import random
import time
import unicodedata

from rosa import argumentacion as AR
from rosa.estado import acciones as A
from rosa.estado import plantilla as P

T = 1_700_000_000_000


# -- Núcleo puro -----------------------------------------------------------------


def test_cadena_a_b_c_deja_en_pie_a_y_c():
    args = {"a", "b", "c"}
    ataques = [("a", "b"), ("b", "c")]
    assert AR.extension_fundamentada(args, ataques) == {"a", "c"}
    assert AR.extensiones_preferidas(args, ataques) == [{"a", "c"}]
    assert AR.libre_de_conflicto({"a", "c"}, ataques) is True
    assert AR.libre_de_conflicto({"a", "b"}, ataques) is False
    assert AR.es_admisible({"a", "c"}, args, ataques) and not AR.es_admisible({"c"}, args, ataques)


def test_ataque_mutuo_deja_la_fundamentada_vacia_y_dos_preferidas():
    args = {"a", "b"}
    ataques = [("a", "b"), ("b", "a")]
    assert AR.extension_fundamentada(args, ataques) == set()
    assert AR.extensiones_preferidas(args, ataques) == [{"a"}, {"b"}]


def test_ciclo_de_tres_deja_la_fundamentada_vacia_y_solo_la_preferida_vacia():
    args = {"a", "b", "c"}
    ataques = [("a", "b"), ("b", "c"), ("c", "a")]
    assert AR.extension_fundamentada(args, ataques) == set()
    assert AR.extensiones_preferidas(args, ataques) == [set()]


def test_el_nucleo_aguanta_vacios_repetidos_autoataques_y_desconocidos():
    assert AR.extension_fundamentada(set(), []) == set()
    assert AR.extensiones_preferidas(set(), []) == [set()]
    assert AR.libre_de_conflicto(set(), [("a", "b")]) is True
    # Ataques repetidos y a ids que no están en el conjunto no cambian nada.
    assert AR.extension_fundamentada({"a", "b"}, [("a", "b"), ("a", "b"), ("z", "a"), ("b", "q")]) == {"a"}
    # Un argumento que se ataca a sí mismo nunca entra ni bloquea al resto.
    assert AR.extension_fundamentada({"a", "b"}, [("a", "a")]) == {"b"}
    assert AR.libre_de_conflicto({"a"}, [("a", "a")]) is False
    # Sin ataques, todo queda en pie.
    assert AR.extension_fundamentada({"a", "b", "c"}, []) == {"a", "b", "c"}


def test_conflictos_entre_es_simetrico_y_solo_mira_la_lista():
    ataques = [("a", "b"), ("c", "b"), ("z", "a"), ("a", "a")]
    assert AR.conflictos_entre(["a", "b", "c"], ataques) == {"a": ["b"], "b": ["a", "c"], "c": ["b"]}
    assert AR.conflictos_entre(["a", "a", "d"], ataques) == {"a": [], "d": []}
    assert AR.conflictos_entre([], ataques) == {}


def test_con_mas_de_doce_argumentos_las_preferidas_caen_a_la_fundamentada():
    args = {f"h{i}" for i in range(13)}
    ataques = [(f"h{i}", f"h{i + 1}") for i in range(12)]
    fundamentada = AR.extension_fundamentada(args, ataques)
    assert fundamentada == {f"h{i}" for i in range(0, 13, 2)}
    assert AR.extensiones_preferidas(args, ataques) == [fundamentada]


def test_preferidas_con_pocos_ataques_son_correctas_y_no_cuestan_decimas():
    # El caso real es disperso (doce hipótesis y uno o dos conflictos). La
    # versión anterior comparaba todos los admisibles entre sí (4096 x 4096
    # cuando no hay ataques) y tardaba décimas de segundo.
    args = {f"h{i}" for i in range(12)}
    t0 = time.perf_counter()
    assert AR.extensiones_preferidas(args, []) == [args]
    assert AR.extensiones_preferidas(args, [("h0", "h1"), ("h1", "h0")]) == [args - {"h1"}, args - {"h0"}]
    assert time.perf_counter() - t0 < 0.5
    # Propiedades que valen para cualquier marco: la fundamentada está en toda
    # preferida, toda preferida es admisible y ninguna contiene a otra.
    azar = random.Random(7)
    ids = [f"h{i}" for i in range(9)]
    for _ in range(20):
        ataques = [(azar.choice(ids), azar.choice(ids)) for _ in range(azar.randint(0, 30))]
        fundamentada = AR.extension_fundamentada(set(ids), ataques)
        preferidas = AR.extensiones_preferidas(set(ids), ataques)
        assert preferidas and all(fundamentada <= p for p in preferidas)
        assert all(AR.es_admisible(p, set(ids), ataques) for p in preferidas)
        assert not any(p < q for p in preferidas for q in preferidas)
        assert preferidas == AR.extensiones_preferidas(set(ids), list(reversed(ataques)))


# -- Signo de una hipótesis ---------------------------------------------------------


def test_signo_de_hipotesis_por_tarjeta_y_por_palabras_en_dos_idiomas():
    assert AR.signo_de_hipotesis({"tarjeta": {"direccion": "aumenta"}, "enunciado": "GFAP baja"}) == "+"
    assert AR.signo_de_hipotesis({"tarjeta": {"direccion": "disminuye"}, "enunciado": "GFAP sube"}) == "-"
    # Con 'modula' o sin tarjeta, deciden las palabras del enunciado.
    assert AR.signo_de_hipotesis({"tarjeta": {"direccion": "modula"}, "enunciado": "GFAP plasmático aumenta en portadores de APOE4"}) == "+"
    assert AR.signo_de_hipotesis({"tarjeta": None, "enunciado": "Lower plasma GFAP precedes amyloid positivity"}) == "-"
    assert AR.signo_de_hipotesis({"enunciado": "La actividad de TREM2 reduce la carga de placas"}) == "-"
    # Ambiguo (sube y baja a la vez), sin enunciado o registro antiguo sin claves: None.
    assert AR.signo_de_hipotesis({"enunciado": "GFAP sube mientras NfL baja"}) is None
    assert AR.signo_de_hipotesis({"tarjeta": {"direccion": "sin_intervencion"}, "enunciado": ""}) is None
    assert AR.signo_de_hipotesis({}) is None
    assert AR.signo_de_hipotesis({"tarjeta": "rota", "enunciado": None}) is None


def test_signo_de_hipotesis_aguanta_mayusculas_espacios_y_lo_que_no_es_dict():
    # La tarjeta la rellena un modelo: ' Aumenta ' o 'DISMINUYE' significan lo mismo.
    assert AR.signo_de_hipotesis({"tarjeta": {"direccion": " Aumenta "}, "enunciado": ""}) == "+"
    assert AR.signo_de_hipotesis({"tarjeta": {"direccion": "DISMINUYE"}, "enunciado": "GFAP sube"}) == "-"
    assert AR.signo_de_hipotesis({"tarjeta": {"direccion": None}, "enunciado": "GFAP sube"}) == "+"
    assert AR.signo_de_hipotesis(None) is None
    assert AR.signo_de_hipotesis("no soy un dict") is None


# -- Ataques sobre el estado --------------------------------------------------------


def _estado():
    e = P.estado_inicial()
    assert A.crear_investigacion(e, {"titulo": "Astrocitos y GFAP", "objetivo": "Orden de alteración de GFAP", "condicionParada": "3 iteraciones"}, T, id_="inv-t") == "inv-t"
    return e


def _hip(e, titulo, enunciado, direccion=None, inv="inv-t", **extra):
    h = P.nueva_hipotesis(inv, 1, T, titulo=titulo, enunciado=enunciado, **extra)
    if direccion is not None:
        h["tarjeta"] = dict(P.tarjeta_vacia(), diana="GFAP", direccion=direccion)
    e["hipotesis"].append(h)
    return h


def _rel(e, h, de, a, signo=None, id_=None):
    r = {"id": id_ or f"rel-{h['id']}", "investigacionId": h["investigacionId"], "de": de, "a": a, "tipo": "supuesto", "contexto": "", "hipotesisId": h["id"], "actualizadoEn": T}
    if signo is not None:
        r["signo"] = signo
    e["relaciones"].append(r)
    return r


def test_mismo_mecanismo_con_signos_opuestos_da_ataque_simetrico():
    e = _estado()
    mas = _hip(e, "GFAP sube antes", "GFAP plasmático aumenta antes que NfL", "aumenta")
    menos = _hip(e, "GFAP baja antes", "GFAP plasmático disminuye antes que NfL", "disminuye")
    igual = _hip(e, "GFAP sube en APOE4", "GFAP aumenta en portadores", "aumenta")
    # Mismo mecanismo aunque cambien mayúsculas y espacios.
    _rel(e, mas, "GFAP", "Neurodegeneración")
    _rel(e, menos, " gfap ", "neurodegeneración ")
    _rel(e, igual, "Gfap", "NEURODEGENERACIÓN")
    ataques = AR.ataques_de(e, "inv-t")
    pares = {(a["de"], a["a"]) for a in ataques}
    assert pares == {(mas["id"], menos["id"]), (menos["id"], mas["id"]), (igual["id"], menos["id"]), (menos["id"], igual["id"])}
    assert all(a["motivo"] == "mismo_mecanismo_direccion_opuesta" for a in ataques)
    primero = next(a for a in ataques if a["de"] == mas["id"])
    assert "GFAP sobre Neurodegeneración" in primero["detalle"] and "'GFAP sube antes' dice que lo aumenta" in primero["detalle"] and "'GFAP baja antes' que lo disminuye" in primero["detalle"]
    assert primero["mecanismo"] == {"de": "GFAP", "a": "Neurodegeneración", "aumenta": mas["id"], "disminuye": menos["id"]}
    # La fundamentada queda vacía para las dos en conflicto mutuo, pero 'igual' también cae porque ataca y es atacada.
    assert AR.extension_fundamentada({mas["id"], menos["id"], igual["id"]}, [(a["de"], a["a"]) for a in ataques]) == set()
    # Las dos entradas espejo no comparten el diccionario del mecanismo.
    espejo = next(a for a in ataques if a["de"] == menos["id"] and a["a"] == mas["id"])
    assert espejo["mecanismo"] == primero["mecanismo"] and espejo["mecanismo"] is not primero["mecanismo"]


def test_el_signo_de_la_relacion_manda_sobre_la_tarjeta():
    e = _estado()
    h1 = _hip(e, "A", "GFAP aumenta", "aumenta")
    h2 = _hip(e, "B", "GFAP aumenta", "aumenta")
    _rel(e, h1, "GFAP", "Y", signo="+")
    _rel(e, h2, "GFAP", "Y", signo="-")  # el juez fijó el signo en la arista
    assert len(AR.ataques_de(e, "inv-t")) == 2
    # Un signo raro en la relación no se usa: se cae a la hipótesis, y las dos son '+'.
    e["relaciones"][-1]["signo"] = "?"
    assert AR.ataques_de(e, "inv-t") == []


def test_sin_signo_no_hay_ataque_ni_se_inventa_por_parecido_de_texto():
    e = _estado()
    h1 = _hip(e, "GFAP y astrocitos", "GFAP se relaciona con la reactividad astrocitaria")
    h2 = _hip(e, "GFAP y astrocitos (bis)", "GFAP se relaciona con la reactividad astrocitaria", "aumenta")
    _rel(e, h1, "GFAP", "Y")
    _rel(e, h2, "GFAP", "Y")
    assert AR.ataques_de(e, "inv-t") == []
    # Mecanismos distintos con signos opuestos tampoco se atacan.
    h3 = _hip(e, "NfL baja", "NfL disminuye", "disminuye")
    _rel(e, h3, "NfL", "Y")
    assert AR.ataques_de(e, "inv-t") == []
    # Relaciones sin 'de' o sin 'a' (registro roto) se ignoran sin romper.
    e["relaciones"].append({"id": "rel-rota", "hipotesisId": h2["id"], "de": "", "a": None})
    assert AR.ataques_de(e, "inv-t") == []


def test_una_hipotesis_con_los_dos_signos_sobre_el_mismo_mecanismo_no_ataca():
    # Registro incoherente: la misma hipótesis dice '+' y '-' sobre GFAP -> Y.
    # No se sabe qué afirma, así que no ataca a nadie ni nadie la ataca.
    e = _estado()
    h1 = _hip(e, "Ambigua", "")
    h2 = _hip(e, "Sube", "")
    _rel(e, h1, "GFAP", "Y", signo="+", id_="r1a")
    _rel(e, h1, "GFAP", "Y", signo="-", id_="r1b")
    _rel(e, h2, "GFAP", "Y", signo="+")
    assert AR.ataques_de(e, "inv-t") == []
    # Sobre otro mecanismo sí puede atacar: la ambigüedad es por mecanismo.
    _rel(e, h1, "TAU", "Z", signo="-", id_="r1c")
    _rel(e, h2, "TAU", "Z", signo="+", id_="r2c")
    assert {(a["de"], a["a"]) for a in AR.ataques_de(e, "inv-t")} == {(h1["id"], h2["id"]), (h2["id"], h1["id"])}


def test_muchas_hipotesis_en_el_mismo_mecanismo_cuestan_lo_que_ocupa_la_salida():
    # 1500 hipótesis sobre la misma arista, una sola en contra: 2998 ataques.
    # La versión anterior evaluaba el signo por cada par (más de un millón de
    # pares) y tardaba segundos; ahora el signo se calcula una vez por relación.
    n = 1500
    e = {
        "hipotesis": [{"id": f"h{i}", "investigacionId": "inv", "titulo": f"H{i}", "enunciado": "GFAP aumenta en portadores" if i else "GFAP disminuye en portadores"} for i in range(n)],
        "relaciones": [{"id": f"r{i}", "de": "GFAP", "a": "Y", "hipotesisId": f"h{i}"} for i in range(n)],
    }
    t0 = time.perf_counter()
    ataques = AR.ataques_de(e, "inv")
    r = AR.marcar_conflictos(e, "inv")
    assert time.perf_counter() - t0 < 1.0
    assert len(ataques) == 2 * (n - 1) and r == {"ataques": 2 * (n - 1), "conflictos": n - 1, "fundamentada": []}
    assert e["hipotesis"][0]["conflictoCon"] == sorted(f"h{i}" for i in range(1, n))


def test_ataque_declarado_es_simetrico_aunque_el_registro_lo_lleve_una_sola():
    # El Killer escribe `ataca` solo en la hipótesis que está juzgando. Si el
    # ataque fuera direccional, la juzgada quedaría en pie y la otra caería por
    # el orden en que se juzgaron. "No pueden ser ciertas a la vez" es simétrico.
    e = _estado()
    h1 = _hip(e, "A", "x")
    h2 = _hip(e, "B", "y")
    h1["ataca"] = [
        {"hipotesisId": h2["id"], "motivo": "contradiccion_declarada", "detalle": "El Killer (v1) la declaró incompatible con B: mismo marcador, sentido opuesto"},
        {"hipotesisId": h2["id"], "motivo": "contradiccion_declarada", "detalle": "El Killer (v1) la declaró incompatible con B: mismo marcador, sentido opuesto"},  # repetido tal cual
        {"hipotesisId": h1["id"], "motivo": "contradiccion_declarada", "detalle": "a sí misma"},
        {"hipotesisId": "hip-no-existe", "motivo": "contradiccion_declarada", "detalle": ""},
        "basura",
    ]
    ataques = AR.ataques_de(e, "inv-t")
    detalle = "El Killer (v1) la declaró incompatible con B: mismo marcador, sentido opuesto"
    assert ataques == [
        {"de": h1["id"], "a": h2["id"], "motivo": "contradiccion_declarada", "detalle": detalle},
        {"de": h2["id"], "a": h1["id"], "motivo": "contradiccion_declarada", "detalle": detalle},
    ]
    r = AR.marcar_conflictos(e, "inv-t")
    assert r == {"ataques": 2, "conflictos": 1, "fundamentada": []}
    assert h1["conflictoCon"] == [h2["id"]] and h1["enExtensionFundamentada"] is False
    assert h2["conflictoCon"] == [h1["id"]] and h2["enExtensionFundamentada"] is False
    # Sin detalle, el módulo escribe uno en castellano con los títulos.
    h1["ataca"] = [{"hipotesisId": h2["id"]}]
    assert AR.ataques_de(e, "inv-t")[0]["detalle"] == "El juez declaró que 'A' y 'B' no pueden ser ciertas a la vez"


def test_el_torneo_escribe_en_las_dos_direcciones_y_no_se_duplica_nada():
    e = _estado()
    h1 = _hip(e, "A", "x")
    h2 = _hip(e, "B", "y")
    detalle = "El juez del torneo las declaró incompatibles en la iteración 2: resumen"
    h1["ataca"] = [{"hipotesisId": h2["id"], "motivo": "contradiccion_declarada", "detalle": detalle}]
    h2["ataca"] = [{"hipotesisId": h1["id"], "motivo": "contradiccion_declarada", "detalle": detalle}]
    assert len(AR.ataques_de(e, "inv-t")) == 2
    assert AR.marcar_conflictos(e, "inv-t") == {"ataques": 2, "conflictos": 1, "fundamentada": []}
    t = AR.texto_conflictos(e, "inv-t")
    assert t.count("\n") == 0 and t.count(detalle) == 1
    assert t.startswith("'A' y 'B' se contradicen (contradicción declarada por el juez: El juez del torneo")
    # Si cada lado trae un detalle distinto (el Killer juzgó a las dos en momentos
    # distintos), los dos se conservan en la misma entrada y salen en la misma línea.
    otro = "El Killer (v2) la declaró incompatible con A"
    h2["ataca"][0]["detalle"] = otro
    ataques = AR.ataques_de(e, "inv-t")
    assert len(ataques) == 2 and all(a["detalle"] == f"{detalle}; {otro}" for a in ataques)
    t2 = AR.texto_conflictos(e, "inv-t")
    assert t2.count("\n") == 0 and t2.count(detalle) == 1 and t2.count(otro) == 1
    # Un par que comparte dos mecanismos con signos opuestos: una entrada por dirección,
    # el primer mecanismo como dato y los dos en el detalle.
    _rel(e, h1, "GFAP", "Y", signo="+", id_="ry1")
    _rel(e, h2, "GFAP", "Y", signo="-", id_="ry2")
    _rel(e, h1, "GFAP", "Z", signo="+", id_="rz1")
    _rel(e, h2, "GFAP", "Z", signo="-", id_="rz2")
    deterministas = [a for a in AR.ataques_de(e, "inv-t") if a["motivo"] == "mismo_mecanismo_direccion_opuesta"]
    assert len(deterministas) == 2 and all(a["mecanismo"]["a"] == "Y" and "GFAP sobre Z" in a["detalle"] for a in deterministas)
    assert AR.marcar_conflictos(e, "inv-t") == {"ataques": 4, "conflictos": 1, "fundamentada": []}


def test_el_motivo_del_registro_se_respeta_y_uno_desconocido_cae_a_declarado():
    e = _estado()
    h1 = _hip(e, "A", "x")
    h2 = _hip(e, "B", "y")
    h3 = _hip(e, "C", "z")
    h1["ataca"] = [
        {"hipotesisId": h2["id"], "motivo": "mismo_mecanismo_direccion_opuesta", "detalle": "GFAP sobre Y en sentidos opuestos"},
        {"hipotesisId": h3["id"], "motivo": "algo_que_no_existe", "detalle": "d"},
    ]
    ataques = AR.ataques_de(e, "inv-t")
    assert {(a["a"], a["motivo"]) for a in ataques if a["de"] == h1["id"]} == {(h2["id"], "mismo_mecanismo_direccion_opuesta"), (h3["id"], "contradiccion_declarada")}
    lineas = AR.texto_conflictos(e, "inv-t").split("\n")
    assert len(lineas) == 2
    assert any("'A' y 'B' se contradicen (mismo mecanismo, direcciones opuestas: GFAP sobre Y en sentidos opuestos)" in l for l in lineas)
    assert any("'A' y 'C' se contradicen (contradicción declarada por el juez: d)" in l for l in lineas)


def test_ataca_con_ids_no_hashables_o_de_otro_tipo_no_rompe():
    e = {"hipotesis": [{"id": "h1", "investigacionId": "inv", "ataca": [{"hipotesisId": ["h2"]}, {"hipotesisId": {"x": 1}}, {"hipotesisId": 7}, {"hipotesisId": None}]}, {"id": "h2", "investigacionId": "inv"}, {"id": 3, "investigacionId": "inv"}]}
    assert AR.ataques_de(e, "inv") == []
    assert AR.marcar_conflictos(e, "inv") == {"ataques": 0, "conflictos": 0, "fundamentada": ["h1", "h2"]}
    # Un `ataca` que es una cadena o un dict (registro roto) tampoco cuenta.
    e["hipotesis"][0]["ataca"] = "h2"
    assert AR.ataques_de(e, "inv") == []
    e["hipotesis"][0]["ataca"] = {"hipotesisId": "h2"}
    assert AR.ataques_de(e, "inv") == []


def test_las_descartadas_y_las_de_otra_investigacion_no_cuentan():
    e = _estado()
    assert A.crear_investigacion(e, {"titulo": "Otra", "objetivo": "O", "condicionParada": "1"}, T, id_="inv-2") == "inv-2"
    h1 = _hip(e, "A", "GFAP aumenta", "aumenta")
    h2 = _hip(e, "B", "GFAP disminuye", "disminuye", estado="descartada")
    h3 = _hip(e, "C", "GFAP disminuye", "disminuye", inv="inv-2")
    for h in (h1, h2, h3):
        _rel(e, h, "GFAP", "Y")
    h1["ataca"] = [{"hipotesisId": h2["id"], "motivo": "contradiccion_declarada", "detalle": "d"}, {"hipotesisId": h3["id"], "motivo": "contradiccion_declarada", "detalle": "d"}]
    assert AR.ataques_de(e, "inv-t") == []
    assert AR.marcar_conflictos(e, "inv-t") == {"ataques": 0, "conflictos": 0, "fundamentada": [h1["id"]]}
    assert h1["conflictoCon"] == [] and h1["enExtensionFundamentada"] is True
    # La descartada de esta investigación queda vacía y fuera; la de otra investigación no se toca.
    assert h2["conflictoCon"] == [] and h2["enExtensionFundamentada"] is False
    assert h3["conflictoCon"] == [] and "enExtensionFundamentada" not in h3
    # Si una marcada pasa a descartada, sus marcas se vacían al volver a marcar.
    h1["estado"] = "descartada"
    AR.marcar_conflictos(e, "inv-t")
    assert h1["conflictoCon"] == [] and h1["enExtensionFundamentada"] is False


def test_marcar_conflictos_sobre_el_estado_inicial_es_idempotente_y_no_descarta():
    e = _estado()
    mas = _hip(e, "GFAP sube antes", "GFAP plasmático aumenta antes que NfL", "aumenta", candidata=True, bloqueos=["trazabilidad_insuficiente"])
    menos = _hip(e, "GFAP baja antes", "GFAP plasmático disminuye antes que NfL", "disminuye", candidata=True)
    aparte = _hip(e, "TREM2 protege", "La actividad de TREM2 reduce la carga de placas")
    _rel(e, mas, "GFAP", "Neurodegeneración")
    _rel(e, menos, "GFAP", "Neurodegeneración")
    _rel(e, aparte, "TREM2", "Placas")
    antes = {h["id"]: (h["estado"], h.get("candidata"), list(h.get("bloqueos") or [])) for h in e["hipotesis"]}
    r = AR.marcar_conflictos(e, "inv-t")
    assert r == {"ataques": 2, "conflictos": 1, "fundamentada": [aparte["id"]]}
    assert mas["conflictoCon"] == [menos["id"]] and mas["enExtensionFundamentada"] is False
    assert menos["conflictoCon"] == [mas["id"]] and menos["enExtensionFundamentada"] is False
    assert aparte["conflictoCon"] == [] and aparte["enExtensionFundamentada"] is True
    # Nada descartado, candidata y bloqueos intactos.
    assert {h["id"]: (h["estado"], h.get("candidata"), list(h.get("bloqueos") or [])) for h in e["hipotesis"]} == antes
    # Idempotente: la segunda pasada deja el estado idéntico.
    copia = copy.deepcopy(e)
    assert AR.marcar_conflictos(e, "inv-t") == r
    assert e == copia
    # El resto del estado inicial (relaciones de la base curada incluidas) sigue ahí.
    assert any(rel["tipo"] == "base_curada" for rel in e["relaciones"])
    # Con solo fuentes simétricas, estar en la fundamentada es no tener conflictos.
    assert all(h["enExtensionFundamentada"] == (h["conflictoCon"] == []) for h in e["hipotesis"])


def test_marcar_conflictos_aguanta_estado_vacio_y_registros_antiguos():
    assert AR.marcar_conflictos({}, "inv-x") == {"ataques": 0, "conflictos": 0, "fundamentada": []}
    assert AR.texto_conflictos({}, "inv-x") == ""
    # Hipótesis antiguas sin tarjeta, sin ataca, sin estado; relaciones sin signo ni hipotesisId.
    e = {
        "hipotesis": [{"id": "h1", "investigacionId": "inv", "enunciado": "GFAP aumenta", "ataca": {"hipotesisId": "h2"}}, {"id": "h2", "investigacionId": "inv", "enunciado": "GFAP disminuye", "ataca": [{"hipotesisId": None}]}, {"id": None, "investigacionId": "inv"}, "tampoco soy un dict"],
        "relaciones": [{"id": "r1", "de": "GFAP", "a": "Y", "hipotesisId": "h1"}, {"id": "r2", "de": "GFAP", "a": "Y", "hipotesisId": "h2"}, {"id": "r-base", "de": "GFAP", "a": "Y"}, "no soy un dict"],
    }
    # `ataca` con forma rara (un dict en vez de lista, hipotesisId None) no rompe ni cuenta.
    assert AR.texto_conflictos(e, "inv", []) == ""
    r = AR.marcar_conflictos(e, "inv")
    assert r == {"ataques": 2, "conflictos": 1, "fundamentada": []}
    assert e["hipotesis"][0]["conflictoCon"] == ["h2"] and e["hipotesis"][1]["conflictoCon"] == ["h1"]
    assert "conflictoCon" not in e["hipotesis"][2]
    # Un registro antiguo descartado sin las claves nuevas las recibe vacías, sin romper.
    e["hipotesis"].append({"id": "h4", "investigacionId": "inv", "estado": "descartada"})
    assert AR.marcar_conflictos(e, "inv") == r
    assert e["hipotesis"][-1]["conflictoCon"] == [] and e["hipotesis"][-1]["enExtensionFundamentada"] is False


def test_estado_none_o_investigacion_vacia_no_rompen_ni_escriben():
    assert AR.marcar_conflictos(None, "inv") == {"ataques": 0, "conflictos": 0, "fundamentada": []}
    assert AR.texto_conflictos(None, "inv") == ""
    assert AR.ataques_de(None, "inv") == []
    assert AR.ataques_de("no soy un estado", "inv") == []
    assert AR.marcar_conflictos({"hipotesis": None, "relaciones": None}, "inv") == {"ataques": 0, "conflictos": 0, "fundamentada": []}
    # Sin investigación no hay marco: una hipótesis con investigacionId None no se
    # empareja con investigacion_id None ni se le escribe nada.
    e = {"hipotesis": [{"id": "h", "investigacionId": None, "estado": "descartada"}, {"id": "h2", "investigacionId": None}]}
    assert AR.marcar_conflictos(e, None) == {"ataques": 0, "conflictos": 0, "fundamentada": []}
    assert AR.marcar_conflictos(e, "") == {"ataques": 0, "conflictos": 0, "fundamentada": []}
    assert all("conflictoCon" not in h for h in e["hipotesis"])


def test_ids_repetidos_no_comparten_la_lista_conflicto_con():
    e = {
        "hipotesis": [{"id": "h1", "investigacionId": "inv", "enunciado": "GFAP aumenta"}, {"id": "h1", "investigacionId": "inv", "enunciado": "GFAP aumenta"}, {"id": "h2", "investigacionId": "inv", "enunciado": "GFAP disminuye"}],
        "relaciones": [{"id": "r1", "de": "GFAP", "a": "Y", "hipotesisId": "h1"}, {"id": "r2", "de": "GFAP", "a": "Y", "hipotesisId": "h2"}],
    }
    assert AR.marcar_conflictos(e, "inv") == {"ataques": 2, "conflictos": 1, "fundamentada": []}
    a, b = e["hipotesis"][0], e["hipotesis"][1]
    assert a["conflictoCon"] == b["conflictoCon"] == ["h2"] and a["conflictoCon"] is not b["conflictoCon"]
    a["conflictoCon"].append("basura")
    assert b["conflictoCon"] == ["h2"]


def test_relaciones_repetidas_de_la_misma_hipotesis_no_multiplican_ataques():
    e = _estado()
    h1 = _hip(e, "A", "GFAP aumenta", "aumenta")
    h2 = _hip(e, "B", "GFAP disminuye", "disminuye")
    for i in range(3):
        _rel(e, h1, "GFAP", "Y", id_=f"rel-a-{i}")
        _rel(e, h2, "GFAP", "Y", id_=f"rel-b-{i}")
    ataques = AR.ataques_de(e, "inv-t")
    assert len(ataques) == 2 and AR.marcar_conflictos(e, "inv-t")["conflictos"] == 1


# -- Texto en llano ------------------------------------------------------------------


def test_texto_conflictos_en_castellano_y_filtrado_por_ids():
    e = _estado()
    mas = _hip(e, "GFAP sube antes", "GFAP plasmático aumenta antes que NfL", "aumenta")
    menos = _hip(e, "GFAP baja antes", "GFAP plasmático disminuye antes que NfL", "disminuye")
    aparte = _hip(e, "TREM2 protege", "TREM2 reduce la carga de placas")
    _rel(e, mas, "GFAP", "Neurodegeneración")
    _rel(e, menos, "GFAP", "Neurodegeneración")
    assert AR.texto_conflictos(e, "inv-t", [aparte["id"]]) == ""
    t = AR.texto_conflictos(e, "inv-t")
    assert t == "'GFAP baja antes' y 'GFAP sube antes' se contradicen (mismo mecanismo, direcciones opuestas: GFAP sobre Neurodegeneración; 'GFAP sube antes' dice que lo aumenta y 'GFAP baja antes' que lo disminuye); no pueden ser ciertas a la vez, así que si las dos van al laboratorio una de las dos sobra o hay que diseñar el experimento que las separe."
    # Con ids, basta con que participe una de la lista.
    assert AR.texto_conflictos(e, "inv-t", [mas["id"]]) == t
    assert AR.texto_conflictos(e, "inv-t", [mas["id"], aparte["id"]]) == t
    # Un ataque declarado además del determinista se cuenta en la misma línea.
    aparte["ataca"] = [{"hipotesisId": mas["id"], "motivo": "contradiccion_declarada", "detalle": "TREM2 explica el dato sin astrocitos"}]
    t2 = AR.texto_conflictos(e, "inv-t")
    lineas = t2.split("\n")
    assert len(lineas) == 2
    assert any("'GFAP sube antes' y 'TREM2 protege' se contradicen (contradicción declarada por el juez: TREM2 explica el dato sin astrocitos)" in l for l in lineas)
    # Sin título se usa el id, y el texto no rompe.
    mas["titulo"] = ""
    assert mas["id"] in AR.texto_conflictos(e, "inv-t")


def test_texto_es_determinista_con_titulos_iguales_y_los_distingue_por_id():
    def estado():
        return {
            "hipotesis": [{"id": f"h{i}", "investigacionId": "inv", "titulo": "Mismo título", "enunciado": "GFAP aumenta" if i % 2 else "GFAP disminuye"} for i in range(1, 5)],
            "relaciones": [{"id": "r1", "de": "GFAP", "a": "Y", "hipotesisId": "h1"}, {"id": "r2", "de": "GFAP", "a": "Y", "hipotesisId": "h2"}, {"id": "r3", "de": "TAU", "a": "Z", "hipotesisId": "h3"}, {"id": "r4", "de": "TAU", "a": "Z", "hipotesisId": "h4"}],
        }
    e1, e2 = estado(), estado()
    e2["relaciones"].reverse()
    e2["hipotesis"].reverse()
    t = AR.texto_conflictos(e1, "inv")
    assert t == AR.texto_conflictos(e2, "inv")
    lineas = t.split("\n")
    assert len(lineas) == 2
    # A igual título, cada hipótesis lleva su id para que la frase se entienda.
    assert lineas[0].startswith("'Mismo título (h1)' y 'Mismo título (h2)' se contradicen (mismo mecanismo, direcciones opuestas: GFAP sobre Y; 'Mismo título (h1)' dice que lo aumenta y 'Mismo título (h2)' que lo disminuye)")
    assert lineas[1].startswith("'Mismo título (h3)' y 'Mismo título (h4)' se contradicen")
    # Con títulos distintos no se añade el id.
    e1["hipotesis"][0]["titulo"] = "Otro"
    assert "(h1)" not in AR.texto_conflictos(e1, "inv")


def test_un_titulo_con_saltos_de_linea_no_parte_la_linea_del_par():
    e = {
        "hipotesis": [{"id": "h1", "investigacionId": "inv", "titulo": "GFAP\n  sube\tantes", "enunciado": "GFAP aumenta"}, {"id": "h2", "investigacionId": "inv", "titulo": "GFAP baja", "enunciado": "GFAP disminuye"}],
        "relaciones": [{"id": "r1", "de": "GFAP", "a": "Y", "hipotesisId": "h1"}, {"id": "r2", "de": "GFAP", "a": "Y", "hipotesisId": "h2"}],
    }
    t = AR.texto_conflictos(e, "inv")
    assert "\n" not in t and "'GFAP sube antes'" in t
    assert "GFAP sube antes" in AR.ataques_de(e, "inv")[0]["detalle"]


def test_los_textos_generados_llevan_tildes_y_no_guiones_largos():
    e = _estado()
    h1 = _hip(e, "A", "GFAP aumenta", "aumenta")
    h2 = _hip(e, "B", "GFAP disminuye", "disminuye")
    _rel(e, h1, "GFAP", "Y")
    _rel(e, h2, "GFAP", "Y")
    h1["ataca"] = [{"hipotesisId": h2["id"]}]
    textos = [a["detalle"] for a in AR.ataques_de(e, "inv-t")] + [AR.texto_conflictos(e, "inv-t")]
    junto = "\n".join(textos)
    assert "\u2014" not in junto  # guion largo (U+2014), escrito como escape para no meterlo en el código
    # Las mismas palabras sin tilde ni ñ (quitadas por código, para no escribirlas
    # mal en el fichero) no aparecen en lo generado.
    for con_tilde in ("declaró", "contradicción", "así que", "diseñar"):
        assert con_tilde in junto
        sin_tilde = "".join(c for c in unicodedata.normalize("NFD", con_tilde) if not unicodedata.combining(c))
        assert sin_tilde != con_tilde and sin_tilde not in junto
