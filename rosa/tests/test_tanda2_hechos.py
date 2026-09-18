"""Hallazgo M-08, parte de estado: los hechos repetidos se funden al heredar
(`copiar_hechos`) y al cargar un estado guardado (migración), y los hechos sin
`afirmacionIds` se enlazan con las afirmaciones que quedan en las corridas.

Los pares de `PARES_ESPEJO` son los mismos que prueba
frontend/src/datos/tanda2_hechos.test.ts: la regla tiene que dar lo mismo en
los dos lados. Sin red ni gateway: todo son diccionarios en memoria y una base
SQLite temporal."""

import copy
import json
import tempfile
from pathlib import Path

import pytest

from rosa import hechos as H
from rosa.estado import acciones as A
from rosa.estado import almacen as AL
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen

INV = "inv-h"
T0 = 1_000_000

# (a, b, esperado): "identico", "solape" (equivalentes por solape de tokens) o None.
PARES_ESPEJO = [
    ("GFAP sube antes que NfL en portadores", "GFAP sube antes que NfL en portadores", "identico"),
    ("El GFAP plasmático sube antes que el NfL en portadores de mutación.", "GFAP plasmático sube antes que NfL en portadores de mutación", "solape"),
    ("El GFAP plasmático sube antes que el NfL.", "el gfap plasmático sube antes que el nfl", "identico"),
    ("Aβ42 baja en LCR 15 años antes del inicio", "Abeta42 baja en LCR 15 años antes del inicio", "identico"),
    ("Sube GFAP antes que NfL en la cohorte", "Sube NfL antes que GFAP en la cohorte", None),
    ("Chatterjee et al. señalan que el inicio joven implica poca copatología relacionada con la edad", "Chatterjee et al. señalan que el inicio joven implica poca copatología relacionada con la edad en comparación", "solape"),
    ("En Belder et al., el MMSE estuvo disponible en 231 de 270 visitas", "En Belder et al., el MMSE estuvo disponible en 214 de 270 visitas", None),
    ("Johansson et al. señalan que el orden de las patologías medido mediante biomarcadores concuerda con la secuencia", "Johansson et al. señalan que el orden de las patologías definido mediante biomarcadores concuerda con la secuencia", "solape"),
    ("", "algo que decir", None),
    ("GFAP y NfL suben en portadores", "TREM2 y APOE4 actúan en sinergia en microglía", None),
]


def _e():
    e = P.estado_inicial()
    assert A.crear_investigacion(e, {"titulo": "T", "objetivo": "GFAP y NfL en sangre", "condicionParada": "3 iteraciones"}, T0, INV) == INV
    return e


def _h(e, id_, enunciado, inv=INV, tipo="hecho", estado="sabido", fuente="f-1", pagina=4, referencia="Belder et al., 2026", afirmaciones=(), t=T0, **extra):
    h = P.nuevo_hecho(inv, tipo, "Biomarcadores", enunciado, estado, "fuente" if tipo == "hecho" else "inferencia", [{"fuenteId": fuente, "referencia": referencia, "pagina": pagina}] if fuente else [], t, afirmacion_ids=list(afirmaciones))
    h["id"] = id_
    h.update(extra)
    e["hechos"].append(h)
    return h


# -- 1. Mismo hecho: la regla espejo ------------------------------------------


@pytest.mark.parametrize("a,b,esperado", PARES_ESPEJO)
def test_equivalencia_de_textos_pares_espejo(a, b, esperado):
    from rosa import cuestiones as CU

    motivo = CU.equivalencia(a, b)
    if esperado is None:
        assert motivo is None
    elif esperado == "identico":
        assert motivo == "texto normalizado idéntico"
    else:
        assert motivo is not None and motivo.startswith("solape de tokens")


def test_las_tildes_y_la_enie_no_distinguen_dos_textos():
    # La variante sin tildes se calcula aquí, no se escribe en el código (regla de tildes del repositorio).
    from rosa import cuestiones as CU

    con = "El GFAP plasmático sube antes que el NfL en portadores de mutación; 15 años después baja."
    sin = CU._sin_tildes(con)
    assert sin != con.lower() and "mutacion" in sin and "anos" in sin
    assert CU.equivalencia(con, sin) == "texto normalizado idéntico"


def test_mismo_hecho_exige_mismo_tipo_estado_e_investigacion_y_nunca_funde_hipotesis():
    e = _e()
    a = _h(e, "he-a", "GFAP sube antes que NfL en portadores")
    b = _h(e, "he-b", "GFAP sube antes que NfL en portadores")
    assert H.mismo_hecho(a, b) == "texto normalizado idéntico"
    assert H.mismo_hecho(a, a) is None and H.mismo_hecho(a, {**b, "id": "he-a"}) is None
    assert H.mismo_hecho(a, {**b, "estado": "descartado"}) is None
    assert H.mismo_hecho(a, {**b, "tipo": "pregunta"}) is None
    assert H.mismo_hecho(a, {**b, "investigacionId": "otra"}) is None
    assert H.mismo_hecho({**a, "tipo": "hipotesis"}, {**b, "tipo": "hipotesis"}) is None
    p1 = {**a, "tipo": "pregunta", "estado": "abierto"}
    p2 = {**b, "tipo": "pregunta", "estado": "abierto"}
    assert H.mismo_hecho(p1, p2) == "texto normalizado idéntico"


def test_sustituto_y_sustituido_o_contradichos_no_son_repetidos():
    e = _e()
    viejo = _h(e, "he-viejo", "GFAP sube en fase 2 en portadores", estado="sabido")
    nuevo = _h(e, "he-nuevo", "GFAP sube en fase 2 en portadores", estado="sabido", sustituyeA=["he-viejo"])
    viejo["sustituidoPor"] = "he-nuevo"
    assert H.mismo_hecho(viejo, nuevo) is None and H.mismo_hecho(nuevo, viejo) is None
    x = _h(e, "he-x", "NfL sube en la cohorte de Belder")
    y = _h(e, "he-y", "NfL sube en la cohorte de Belder", contradiceA=["he-x"])
    assert H.mismo_hecho(x, y) is None
    # Sin el enlace sí son el mismo hecho.
    y["contradiceA"] = []
    assert H.mismo_hecho(x, y) == "texto normalizado idéntico"


def test_misma_referencia_baja_el_umbral_pero_sola_no_funde():
    e = _e()
    # Solape de tokens largos 0,67 (4 comunes de 6): sin referencia común no llega a 0,8.
    a = _h(e, "he-a", "Belder et al. excluyeron cuatro no portadores con EYO superior a 20 años", fuente="f-1", pagina=4)
    b = _h(e, "he-b", "Belder et al. excluyeron cuatro no portadores con EYO superior a 20 años por falta de comparables", fuente="f-2", pagina=4)
    assert H.mismo_hecho(a, b) is None
    b["procedencia"] = [{"fuenteId": "f-1", "referencia": "Belder et al., 2026", "pagina": 4}]
    motivo = H.mismo_hecho(a, b)
    assert motivo is not None and motivo.startswith("misma referencia y solape de tokens")
    # Con la misma referencia pero hechos distintos (el n y el efecto del mismo artículo) no hay fusión.
    c = _h(e, "he-c", "En Belder et al., el MMSE estuvo disponible en 231 de 270 visitas", fuente="f-1", pagina=4)
    d = _h(e, "he-d", "La cohorte de Belder et al. representó 38 variantes causantes de Alzheimer autosómico dominante", fuente="f-1", pagina=4)
    assert H.mismo_hecho(c, d) is None and H.mismo_hecho(a, c) is None
    # Misma afirmación compartida por dos hechos distintos: tampoco.
    c["afirmacionIds"] = ["af-1"]
    d["afirmacionIds"] = ["af-1"]
    assert H.mismo_hecho(c, d) is None
    # Con referencia común pero cifras distintas (marcas cortas) no se funde.
    c2 = _h(e, "he-c2", "En Belder et al., el MMSE estuvo disponible en 214 de 270 visitas", fuente="f-1", pagina=4)
    assert H.mismo_hecho(c, c2) is None


def test_mismo_hecho_tolera_registros_antiguos_sin_claves():
    a = {"id": "he-1", "investigacionId": INV, "tipo": "hecho", "estado": "sabido", "enunciado": "GFAP sube"}
    b = {"id": "he-2", "investigacionId": INV, "tipo": "hecho", "estado": "sabido", "enunciado": "GFAP sube"}
    assert H.mismo_hecho(a, b) == "texto normalizado idéntico"
    assert H.mismo_hecho({**a, "enunciado": None}, {**b, "enunciado": ""}) is None
    assert H.mismo_hecho({"id": "x"}, {"id": "y"}) is None


# -- 2. Fundir ----------------------------------------------------------------


def test_fundir_suma_procedencia_afirmaciones_citas_enlaces_y_anota_el_historial():
    e = _e()
    a = _h(e, "he-a", "GFAP sube antes que NfL", fuente="f-1", pagina=4, afirmaciones=["af-1"], t=T0)
    a["citas"] = [{"referencia": "Belder et al., 2026", "seccion": "pág. 4", "clasificacion": "apoya", "fragmento": "x"}]
    a["entidades"] = [{"id": "HGNC:4235", "etiqueta": "GFAP", "ontologia": "HGNC", "tipo": "gen", "alias": []}]
    b = _h(e, "he-b", "GFAP sube antes que NfL", fuente="f-2", pagina=None, referencia="Chatterjee et al., 2025", afirmaciones=["af-1", "af-2"], t=T0 + 500, prioridad=8, resuelveA=["cu-1"], contradiceA=["he-z", "he-a"])
    b["citas"] = [{"referencia": "Chatterjee et al., 2025", "seccion": "resumen", "clasificacion": "apoya", "fragmento": "y"}, {"referencia": "Belder et al., 2026", "seccion": "pág. 4", "clasificacion": "apoya", "fragmento": "x repetido"}]
    b["entidades"] = [{"id": "HGNC:4235", "etiqueta": "GFAP", "ontologia": "HGNC", "tipo": "gen", "alias": ["gfap"]}, {"id": "HGNC:7752", "etiqueta": "NEFL", "ontologia": "HGNC", "tipo": "gen", "alias": []}]
    b["pendienteRevision"] = {"motivo": "revisar", "desde": T0}
    copia_b = copy.deepcopy(b)
    H.fundir(a, b, T0 + 900, "texto normalizado idéntico")
    assert [(p["fuenteId"], p["pagina"]) for p in a["procedencia"]] == [("f-1", 4), ("f-2", None)]
    assert a["afirmacionIds"] == ["af-1", "af-2"]
    assert [c["seccion"] for c in a["citas"]] == ["pág. 4", "resumen"]
    assert [x["id"] for x in a["entidades"]] == ["HGNC:4235", "HGNC:7752"]
    assert a["resuelveA"] == ["cu-1"] and a["contradiceA"] == ["he-z"]  # el enlace a sí mismo desaparece
    assert a["prioridad"] == 8 and a["pendienteRevision"] == {"motivo": "revisar", "desde": T0}
    assert a["actualizadoEn"] == T0  # fundir no es conocimiento nuevo
    ultimo = a["historial"][-1]
    assert ultimo["fecha"] == T0 + 900 and ultimo["de"] == "sabido" and ultimo["a"] == "sabido" and ultimo["quien"] == "Rosa"
    assert ultimo["motivo"] == "Fundido con he-b: «GFAP sube antes que NfL» (texto normalizado idéntico); se suman su procedencia y sus afirmaciones"
    assert b == copia_b  # el repetido no se toca


def test_fundir_duplicados_deja_el_mas_antiguo_remapea_enlaces_y_devuelve_el_mapa():
    e = _e()
    a = _h(e, "he-a", "GFAP sube antes que NfL en portadores", fuente="f-1")
    b = _h(e, "he-b", "El GFAP sube antes que el NfL en portadores", fuente="f-2", t=T0 + 1)
    c = _h(e, "he-c", "TREM2 R47H atenúa la respuesta microglial", sustituyeA=["he-b", "he-fuera"], contradiceA=["he-a"])
    d = _h(e, "he-d", "GFAP sube antes que NfL en portadores", fuente="f-3", t=T0 + 2, sustituidoPor="he-b")
    supervivientes, mapa, fusiones = H.fundir_duplicados([a, b, c, d], T0 + 10)
    assert [h["id"] for h in supervivientes] == ["he-a", "he-c"]
    assert mapa == {"he-b": "he-a", "he-d": "he-a"}
    assert [(s, r) for s, r, _ in fusiones] == [("he-a", "he-b"), ("he-a", "he-d")]
    assert [p["fuenteId"] for p in a["procedencia"]] == ["f-1", "f-2", "f-3"]
    assert c["sustituyeA"] == ["he-a", "he-fuera"] and c["contradiceA"] == ["he-a"]
    # `d` apuntaba con sustituidoPor a `b`, que ahora es `a`, es decir, a sí mismo: desaparece.
    assert a.get("sustituidoPor") is None
    assert H.fundir_duplicados([], T0) == ([], {}, [])


# -- 3. copiar_hechos, crear con herencia y bifurcar ---------------------------


def test_copiar_hechos_funde_los_repetidos_al_heredar_y_no_toca_el_origen():
    e = _e()
    a = _h(e, "he-a", "GFAP sube antes que NfL en portadores", fuente="f-1", afirmaciones=["af-1"])
    b = _h(e, "he-b", "El GFAP sube antes que el NfL en portadores", fuente="f-2", afirmaciones=["af-2"], t=T0 + 1)
    c = _h(e, "he-c", "TREM2 R47H atenúa la respuesta microglial", sustituyeA=["he-b"])
    origen = copy.deepcopy(e["hechos"])
    assert A.crear_investigacion(e, {"titulo": "D", "objetivo": "O", "condicionParada": "1", "heredarModeloDe": INV}, T0 + 100, id_="inv-d") == "inv-d"
    heredados = [h for h in e["hechos"] if h["investigacionId"] == "inv-d"]
    assert [h["id"] for h in heredados] == ["he-a-inv-d", "he-c-inv-d"]
    ha, hc = heredados
    assert [p["fuenteId"] for p in ha["procedencia"]] == ["f-1", "f-2"] and ha["afirmacionIds"] == ["af-1", "af-2"]
    assert ha["historial"][-1]["fecha"] == T0 + 100 and "Fundido con he-b-inv-d" in ha["historial"][-1]["motivo"]
    assert hc["sustituyeA"] == ["he-a-inv-d"]  # apuntaba a la copia de b, que se fundió en la de a
    assert e["hechos"][: len(origen)] == origen  # el origen sigue con sus tres hechos, intactos
    assert (a, b, c) == tuple(origen)


def test_copiar_hechos_devuelve_los_que_quedan_y_sin_ahora_fecha_con_el_actualizado_mas_reciente():
    e = _e()
    _h(e, "he-a", "GFAP sube antes que NfL", t=T0)
    _h(e, "he-b", "GFAP sube antes que NfL", t=T0 + 77)
    _h(e, "he-c", "Otro hecho distinto sobre APOE4", t=T0 + 5)
    assert A.crear_investigacion(e, {"titulo": "D", "objetivo": "O", "condicionParada": "1"}, T0, id_="inv-d") == "inv-d"
    assert A.copiar_hechos(e, INV, "inv-d") == 2
    ha = next(h for h in e["hechos"] if h["id"] == "he-a-inv-d")
    assert ha["historial"][-1]["fecha"] == T0 + 77
    # Copiar de una investigación sin hechos no rompe ni añade nada.
    assert A.copiar_hechos(e, "inv-vacia", "inv-d") == 0


def test_bifurcar_funde_al_heredar_y_conserva_sustituto_y_sustituido():
    e = _e()
    viejo = _h(e, "he-viejo", "GFAP sube en fase 2", estado="descartado")
    nuevo = _h(e, "he-nuevo", "GFAP sube ya en fase 1", sustituyeA=["he-viejo", "he-de-otra"])
    viejo["sustituidoPor"] = "he-nuevo"
    _h(e, "he-r1", "NfL sube en la cohorte de Belder", fuente="f-1")
    _h(e, "he-r2", "NfL sube en la cohorte de Belder.", fuente="f-9", pagina=2)
    rama = A.bifurcar_investigacion(e, INV, "rama de prueba", T0 + 50)
    copias = {h["id"]: h for h in e["hechos"] if h["investigacionId"] == rama}
    assert sorted(copias) == sorted([f"he-viejo-{rama}", f"he-nuevo-{rama}", f"he-r1-{rama}"])
    assert copias[f"he-nuevo-{rama}"]["sustituyeA"] == [f"he-viejo-{rama}", "he-de-otra"]
    assert copias[f"he-viejo-{rama}"]["sustituidoPor"] == f"he-nuevo-{rama}"
    assert [p["fuenteId"] for p in copias[f"he-r1-{rama}"]["procedencia"]] == ["f-1", "f-9"]
    assert nuevo["sustituyeA"] == ["he-viejo", "he-de-otra"]


# -- 4. Enlace con las afirmaciones ------------------------------------------


def _af(id_, texto, fuente="f-1", localizador="pág. 4", veredicto="sostenida", fragmento="fragmento literal"):
    return {"id": id_, "texto": texto, "fuenteId": fuente, "localizador": localizador, "veredicto": veredicto, "fragmento": fragmento}


def test_afirmaciones_que_sostienen_misma_fuente_pagina_cifras_y_cobertura():
    e = _e()
    h = _h(e, "he-a", "En Belder et al., el MMSE estuvo disponible en 231 de 270 visitas y el CDR en 214 de 270 visitas. [Belder et al., 2026, pág. 4]", fuente="f-1", pagina=4)
    buena = _af("af-1", "El MMSE estuvo disponible en 231 de 270 visitas y el CDR en 214 de 270 visitas.")
    otra_pagina = _af("af-2", "El MMSE estuvo disponible en 231 de 270 visitas y el CDR en 214 de 270 visitas.", localizador="pág. 5")
    otra_fuente = _af("af-3", "El MMSE estuvo disponible en 231 de 270 visitas y el CDR en 214 de 270 visitas.", fuente="f-2")
    no_sostenida = _af("af-4", "El MMSE estuvo disponible en 231 de 270 visitas y el CDR en 214 de 270 visitas.", veredicto="cita_no_resuelve")
    otra_cifra = _af("af-5", "El MMSE estuvo disponible en 213 de 270 visitas y el CDR en 214 de 270 visitas.")
    otro_hecho = _af("af-6", "Se excluyeron cuatro individuos no portadores con EYO mayor a 20 años por falta de portadores comparables.")
    sin_pagina = _af("af-7", "El MMSE estuvo disponible en 231 de 270 visitas y el CDR en 214 de 270 visitas, según la tabla.", localizador="sección Methods")
    parcial = _af("af-8", "MMSE disponible en 231 de 270 visitas; CDR en 214 de 270 visitas.", veredicto="parcial")
    ids = [a["id"] for a in H.afirmaciones_que_sostienen(h, [buena, otra_pagina, otra_fuente, no_sostenida, otra_cifra, otro_hecho, sin_pagina, parcial, buena])]
    assert ids == ["af-1", "af-7", "af-8"]
    # Sin candidatas o con una lista rara no rompe y no inventa: "no pude comprobar".
    assert H.afirmaciones_que_sostienen(h, []) == [] and H.afirmaciones_que_sostienen(h, [None, {}, {"id": "x"}]) == []
    # Una entrada de revisión de hipótesis nunca se enlaza.
    assert H.afirmaciones_que_sostienen({**h, "tipo": "hipotesis"}, [buena]) == []
    # Dirección invertida: misma bolsa de palabras, otro orden.
    h2 = _h(e, "he-b", "GFAP se altera antes que NfL en la progresión a MCI amiloide positivo en los participantes", fuente="f-1", pagina=None)
    assert H.afirmaciones_que_sostienen(h2, [_af("af-9", "NfL se altera antes que GFAP en la progresión a MCI amiloide positivo en los participantes")]) == []
    assert [a["id"] for a in H.afirmaciones_que_sostienen(h2, [_af("af-10", "GFAP se altera antes que NfL en la progresión a MCI amiloide positivo en los participantes estudiados")])] == ["af-10"]


def test_enlazar_anade_ids_y_citas_y_es_idempotente():
    e = _e()
    h = _h(e, "he-a", "En Belder et al., el MMSE estuvo disponible en 231 de 270 visitas y el CDR en 214 de 270 visitas.", fuente="f-1", pagina=4)
    af = _af("af-1", "El MMSE estuvo disponible en 231 de 270 visitas y el CDR en 214 de 270 visitas.", fragmento="MMSE was available for 231 of 270 visits " * 20)
    assert H.enlazar(h, [af]) == 1
    assert h["afirmacionIds"] == ["af-1"]
    assert h["citas"] == [{"referencia": "Belder et al., 2026", "seccion": "pág. 4", "clasificacion": "apoya", "fragmento": af["fragmento"][:300]}]
    assert H.enlazar(h, [af]) == 0 and h["afirmacionIds"] == ["af-1"] and len(h["citas"]) == 1
    # Un hecho antiguo sin las claves del grafo también se enlaza.
    viejo = {"id": "he-v", "investigacionId": INV, "tipo": "hecho", "estado": "sabido", "enunciado": h["enunciado"], "procedencia": h["procedencia"]}
    assert H.enlazar(viejo, [af]) == 1 and viejo["afirmacionIds"] == ["af-1"]


# -- 5. Migración del estado guardado -----------------------------------------


def _estado_para_migrar():
    e = _e()
    assert A.crear_investigacion(e, {"titulo": "Otra", "objetivo": "O", "condicionParada": "1"}, T0, "inv-otra") == "inv-otra"
    a = _h(e, "he-a", "Belder et al. excluyeron cuatro no portadores con EYO superior a 20 años porque no había portadores comparables", fuente="f-1", pagina=4)
    _h(e, "he-b", "Belder et al. excluyeron cuatro no portadores con EYO superior a 20 años porque no había portadores comparables.", fuente="f-2", pagina=4, referencia="Belder et al., 2026 (segunda descarga)", t=T0 + 1)
    _h(e, "he-c", "En Belder et al., el MMSE estuvo disponible en 231 de 270 visitas y el CDR en 214 de 270 visitas.", fuente="f-1", pagina=4)
    _h(e, "he-d", "TREM2 R47H atenúa la respuesta microglial", contradiceA=["he-b"], sustituyeA=["he-fuera"])
    _h(e, "he-p", "Qué orden siguen NfL y GFAP en la fase preclínica", tipo="pregunta", estado="abierto", fuente=None)
    # El mismo texto en otra investigación no se funde con estos.
    _h(e, "he-o", "Belder et al. excluyeron cuatro no portadores con EYO superior a 20 años porque no había portadores comparables", inv="inv-otra", fuente="f-1", pagina=4)
    a["afirmacionIds"] = []
    e["cuestiones"] = [{"id": "cu-1", "investigacionId": INV, "texto": "¿Por qué se excluyeron?", "estado": "resuelta", "origen": {"tipo": "pregunta_modelo", "id": "he-b"}, "hechoIds": ["he-b", "he-c"], "resolucion": {"por": "he-b", "motivo": "m"}, "historial": []}]
    # Corridas con la forma real (la migración completa del almacén las recorre) y las afirmaciones en su clave privada.
    corrida = P.nueva_corrida(INV, 1, T0)
    corrida["id"] = "cor-1"
    corrida["_afirmaciones"] = [
        _af("af-1", "Se excluyeron cuatro individuos no portadores (NC) con EYO mayor a 20 años por falta de portadores (MC) comparables en ese rango.", fuente="f-1"),
        _af("af-2", "El MMSE estuvo disponible en 231 de 270 visitas y el CDR en 214 de 270 visitas.", fuente="f-1"),
        _af("af-3", "Se excluyeron cuatro individuos no portadores con EYO mayor a 20 años por falta de portadores comparables.", fuente="f-2"),
        _af("af-4", "Un texto que no dice nada de esto y no debe enlazarse con ningún hecho.", fuente="f-1"),
    ]
    corrida_antigua = P.nueva_corrida(INV, 0, T0)  # sin `_afirmaciones`
    corrida_antigua["id"] = "cor-0"
    e["corridas"] = [corrida_antigua, corrida]
    return e


def test_migrar_enlaza_funde_remapea_y_anota_una_sola_vez():
    e = _estado_para_migrar()
    eventos_antes = len(e["eventos"])
    r = H.migrar(e, T0 + 999)
    # he-a, he-b y he-c en INV y he-o en la otra investigación: cuatro enlazados antes de fundir he-b en he-a.
    assert r == {"enlazados": 4, "enlaces": 4, "fundidos": 1}
    ids = [h["id"] for h in e["hechos"]]
    assert ids == ["he-a", "he-c", "he-d", "he-p", "he-o"]
    a = next(h for h in e["hechos"] if h["id"] == "he-a")
    # Primero se enlaza cada uno con su afirmación y después la fusión suma los dos enlaces y las dos fuentes.
    assert a["afirmacionIds"] == ["af-1", "af-3"] and [p["fuenteId"] for p in a["procedencia"]] == ["f-1", "f-2"]
    assert a["historial"][-1]["fecha"] == T0 + 999 and "Fundido con he-b" in a["historial"][-1]["motivo"]
    assert next(h for h in e["hechos"] if h["id"] == "he-c")["afirmacionIds"] == ["af-2"]
    assert next(h for h in e["hechos"] if h["id"] == "he-o")["afirmacionIds"] == ["af-1"]  # heredado: encuentra la fuente por su id único
    d = next(h for h in e["hechos"] if h["id"] == "he-d")
    assert d["contradiceA"] == ["he-a"] and d["sustituyeA"] == ["he-fuera"]
    cu = e["cuestiones"][0]
    assert cu["hechoIds"] == ["he-a", "he-c"] and cu["origen"]["id"] == "he-a" and cu["resolucion"]["por"] == "he-a"
    nuevos = e["eventos"][eventos_antes:]
    assert [ev["investigacionId"] for ev in nuevos] == [INV, "inv-otra"]
    assert nuevos[0]["tipo"] == "hecho_nuevo" and nuevos[0]["t"] == T0 + 999 and nuevos[0]["ruta"] == f"#/investigaciones/{INV}/mundo"
    assert nuevos[0]["texto"] == "Revisión del modelo de mundo al cargar: 1 hecho repetido se fundió con el hecho más antiguo que decía lo mismo con otras palabras; 3 hechos quedaron enlazados con las afirmaciones que los sostienen."
    assert nuevos[1]["texto"] == "Revisión del modelo de mundo al cargar: 1 hecho quedó enlazado con las afirmaciones que lo sostienen."
    # Segunda pasada: nada que hacer, ningún evento nuevo, mismo estado.
    copia = copy.deepcopy(e)
    assert H.migrar(e, T0 + 2000) == {"enlazados": 0, "enlaces": 0, "fundidos": 0}
    assert e == copia


def test_migrar_tolera_estados_vacios_o_antiguos():
    assert H.migrar({}) == {"enlazados": 0, "enlaces": 0, "fundidos": 0}
    assert H.migrar({"hechos": []}) == {"enlazados": 0, "enlaces": 0, "fundidos": 0}
    assert H.migrar({"hechos": "no es una lista"}) == {"enlazados": 0, "enlaces": 0, "fundidos": 0}
    # Hechos sin las claves del grafo, sin procedencia, sin corridas ni cuestiones ni eventos.
    e = {"hechos": [
        {"id": "he-1", "investigacionId": INV, "tipo": "hecho", "estado": "sabido", "enunciado": "GFAP sube antes que NfL"},
        {"id": "he-2", "investigacionId": INV, "tipo": "hecho", "estado": "sabido", "enunciado": "GFAP sube antes que NfL"},
        "basura",
        {"id": "he-3", "investigacionId": INV, "tipo": "hecho", "estado": "sabido"},
    ]}
    assert H.migrar(e, T0) == {"enlazados": 0, "enlaces": 0, "fundidos": 1}
    assert [h["id"] if isinstance(h, dict) else h for h in e["hechos"]] == ["he-1", "basura", "he-3"]
    assert e["eventos"][-1]["investigacionId"] == INV and "1 hecho repetido" in e["eventos"][-1]["texto"]
    # Una fuente sin afirmaciones guardadas: el hecho se queda sin enlace y sin evento ("no pude comprobar").
    e2 = {"hechos": [{"id": "he-1", "investigacionId": INV, "tipo": "hecho", "estado": "sabido", "enunciado": "GFAP sube antes que NfL", "procedencia": [{"fuenteId": "f-x", "referencia": "R", "pagina": 1}]}], "corridas": [{"id": "c", "_afirmaciones": [_af("af-1", "GFAP sube antes que NfL", fuente="f-otra")]}], "eventos": []}
    assert H.migrar(e2, T0) == {"enlazados": 0, "enlaces": 0, "fundidos": 0} and e2["eventos"] == [] and e2["hechos"][0].get("afirmacionIds") is None


def test_el_almacen_migra_al_cargar_y_la_segunda_carga_no_cambia_nada():
    ruta = Path(tempfile.mkdtemp()) / "t.db"
    al = Almacen(ruta)
    al.aplicar("crearInvestigacion", {"datos": {"titulo": "T", "objetivo": "O", "condicionParada": "3 iteraciones"}, "id_": INV})

    def envejecer(e):
        viejo = _estado_para_migrar()
        e["hechos"] = viejo["hechos"]
        e["cuestiones"] = viejo["cuestiones"]
        e["corridas"] = viejo["corridas"]
        e["investigaciones"].append(next(i for i in viejo["investigaciones"] if i["id"] == "inv-otra"))
        return True

    al.mutar(envejecer)
    guardado = json.loads(al._con.execute("SELECT json FROM estado WHERE clave='rosa'").fetchone()[0])
    assert [h["id"] for h in guardado["hechos"]] == ["he-a", "he-b", "he-c", "he-d", "he-p", "he-o"]
    al.cerrar()
    al2 = Almacen(ruta)
    assert [h["id"] for h in al2.estado["hechos"]] == ["he-a", "he-c", "he-d", "he-p", "he-o"]
    a = next(h for h in al2.estado["hechos"] if h["id"] == "he-a")
    assert a["afirmacionIds"] == ["af-1", "af-3"]
    revisiones = [ev for ev in al2.estado["eventos"] if ev["texto"].startswith("Revisión del modelo de mundo al cargar")]
    assert len(revisiones) == 2
    # Se persiste con la siguiente escritura y la segunda carga no vuelve a anotar nada.
    al2.mutar(lambda e: True)
    al2.cerrar()
    al3 = Almacen(ruta)
    assert len([ev for ev in al3.estado["eventos"] if ev["texto"].startswith("Revisión del modelo de mundo al cargar")]) == 2
    assert [h["id"] for h in al3.estado["hechos"]] == ["he-a", "he-c", "he-d", "he-p", "he-o"]
    al3.cerrar()


def test_si_la_migracion_falla_la_carga_sigue(monkeypatch, capsys):
    import rosa.hechos as HM

    def rompe(_e):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(HM, "migrar", rompe)
    e = P.estado_inicial()
    AL._migrar_hechos_repetidos(e)
    assert "fallo simulado" in capsys.readouterr().err


# -- 6. Guardas del adversario (18 de septiembre de 2026) ----------------------
# Las cuatro guardas de paráfrasis del bucle (referencia compartida, mismos
# números, mismas siglas, mismas negaciones largas) y las dos guardas simétricas
# del enlace con afirmaciones (negación adyacente, cambio de sigla).

F1 = [("f-1", "Belder et al., 2026", 4)]
F1_P7 = [("f-1", "Belder et al., 2026", 7)]
F2_MISMA_OBRA = [("f-2", "Belder et al., 2026", None)]
F2_OTRA_OBRA = [("f-2", "Johansson et al., 2023", 2)]
F3_OTRA_OBRA = [("f-3", "Johansson et al., 2023", 2)]  # un id de fuente es único en el estado: otra obra lleva otro id
GFAP_ELEVA = "GFAP plasmático se eleva en portadores presintomáticos de mutación antes del inicio clínico estimado"
GFAP_ELEVA_PARAFRASIS = "El GFAP plasmático se eleva en los portadores presintomáticos de mutación antes del inicio clínico estimado"

# (a, procedencia_a, b, procedencia_b, esperado): "identico", "solape", "referencia" (vía del umbral 0,6) o None.
# Los mismos pares que frontend/src/datos/tanda2_hechos.test.ts PARES_ESPEJO_HECHOS.
PARES_ESPEJO_HECHOS = [
    (GFAP_ELEVA, F1, "sTREM2 plasmático se eleva en portadores presintomáticos de mutación antes del inicio clínico estimado", [("f-2", "Otro et al., 2024", 4)], None),
    ("GFAP sube en portadores en fase preclínica", F1, "YKL40 sube en portadores en fase preclínica", F1, None),
    ("La cohorte incluyó portadores de PSEN1 con EYO negativo", F1, "La cohorte incluyó portadores de APOE4 con EYO negativo", F1, None),
    ("El tratamiento redujo la carga amiloide en la cohorte tratada frente a placebo", F1, "El tratamiento nunca redujo la carga amiloide en la cohorte tratada frente a placebo", F1, None),
    ("Treatment reduced amyloid burden in the treated cohort compared with placebo", F1, "Treatment never reduced amyloid burden in the treated cohort compared with placebo", F1, None),
    ("Belder et al. excluyeron cuatro no portadores con EYO superior a los veinte años del análisis", F1, "Belder et al. excluyeron seis no portadores con EYO superior a los veinte años del análisis", F1, None),
    (GFAP_ELEVA, F1, GFAP_ELEVA_PARAFRASIS, F2_OTRA_OBRA, None),  # otra obra sin referencia común: una replicación vive aparte
    (GFAP_ELEVA, F1, GFAP_ELEVA_PARAFRASIS, F2_MISMA_OBRA, "solape"),  # la misma obra traída en otra corrida
    (GFAP_ELEVA, F1, GFAP_ELEVA_PARAFRASIS, F1_P7, "solape"),  # misma fuente, otra página
    ("GFAP sube antes que NfL en portadores", F1, "GFAP sube antes que NfL en portadores", [("f-9", "Chatterjee et al., 2025", 1)], "identico"),  # texto idéntico: venga de donde venga
    ("Qué orden siguen NfL y GFAP en la fase preclínica", [], "¿Qué orden siguen NfL y GFAP en fase preclínica?", [], "solape"),  # sin procedencia ninguno: no hay fuente que distinguir
    ("Qué orden siguen NfL y GFAP en la fase preclínica", F1, "¿Qué orden siguen NfL y GFAP en fase preclínica?", [], None),  # uno con fuente y otro sin ella
    ("Belder et al. excluyeron cuatro no portadores con EYO superior a 20 años", F1, "Belder et al. excluyeron cuatro no portadores con EYO superior a 20 años por falta de comparables", F1, "referencia"),
    ("En Belder et al., el MMSE estuvo disponible en 231 de 270 visitas", F1, "La cohorte de Belder et al. representó 38 variantes causantes de Alzheimer autosómico dominante", F1, None),
    ("Según Belder, el GFAP plasmático se eleva antes del inicio clínico en portadores de mutación", F1, "Según los autores, el GFAP plasmático se eleva antes del inicio clínico en portadores de mutación", F1, "solape"),  # la mayúscula inicial no es una sigla
    (GFAP_ELEVA, [("f-1", "Sin autor, 2023", 1)], GFAP_ELEVA_PARAFRASIS, [("f-2", "Sin autor, 2023", 1)], None),  # dos obras sin autor no son la misma obra
    (GFAP_ELEVA, [("f-1", "Sin autor", 1)], GFAP_ELEVA_PARAFRASIS, [("f-1", "Sin autor (alzforum.org)", 3)], "solape"),  # el mismo id de fuente sí
]


def _con_procedencia(e, id_, texto, proc, t=T0):
    h = _h(e, id_, texto, fuente=None, t=t)
    h["procedencia"] = [{"fuenteId": f, "referencia": r, "pagina": p} for f, r, p in proc]
    return h


@pytest.mark.parametrize("a,pa,b,pb,esperado", PARES_ESPEJO_HECHOS)
def test_mismo_hecho_pares_espejo_con_procedencia(a, pa, b, pb, esperado):
    e = _e()
    ha = _con_procedencia(e, "he-a", a, pa)
    hb = _con_procedencia(e, "he-b", b, pb, t=T0 + 1)
    motivo = H.mismo_hecho(ha, hb)
    if esperado is None:
        assert motivo is None
    elif esperado == "identico":
        assert motivo == "texto normalizado idéntico"
    elif esperado == "solape":
        assert motivo is not None and motivo.startswith("solape de tokens")
    else:
        assert motivo is not None and motivo.startswith("misma referencia y solape de tokens")
    # Simétrica.
    assert (H.mismo_hecho(hb, ha) is None) == (motivo is None)


def test_las_guardas_de_parafrasis_nombran_lo_que_distingue():
    e = _e()
    a = _con_procedencia(e, "he-a", GFAP_ELEVA, F1)
    assert H.guardas_de_parafrasis(a, _con_procedencia(e, "he-b", GFAP_ELEVA_PARAFRASIS, F2_OTRA_OBRA)) == "otra fuente sin referencia común: una replicación vive aparte"
    assert H.guardas_de_parafrasis(a, _con_procedencia(e, "he-c", GFAP_ELEVA.replace("GFAP", "sTREM2"), F1)) == "siglas distintas"
    assert H.guardas_de_parafrasis(a, _con_procedencia(e, "he-d", GFAP_ELEVA.replace("se eleva", "nunca se eleva"), F1)) == "una negación que el otro no tiene"
    assert H.guardas_de_parafrasis(a, _con_procedencia(e, "he-e", GFAP_ELEVA + " en dos cohortes", F1)) == "números distintos"
    assert H.guardas_de_parafrasis(a, _con_procedencia(e, "he-f", GFAP_ELEVA_PARAFRASIS, F2_MISMA_OBRA)) is None
    # La cita entre corchetes del paso de modelo no cuenta ni como número ni como sigla.
    assert H.guardas_de_parafrasis(a, _con_procedencia(e, "he-g", GFAP_ELEVA_PARAFRASIS + " [Belder et al., 2026, pág. 4]", F1)) is None


def test_numeros_siglas_negaciones_y_referencia_compartida():
    assert H.numeros_de("Se excluyeron cuatro de 1.234,5 participantes, un 27 % del total en 2026") == {"cuatro", "1234.5", "27", "2026"}
    assert H.numeros_de("") == set() and H.numeros_de(None) == set()
    assert H.siglas_de("La p-tau217 plasmática y el pTau217, Aβ42, NfL, sTREM2, APOE4, ApoE, CDR-SB, 18F-florbetapir, tau, MMSE") == {"ptau217", "abeta42", "nfl", "strem2", "apoe4", "apoe", "cdrsb", "18fflorbetapir", "mmse"}
    # Belder, Los, Treatment (solo la primera mayúscula), 2026 (cifra suelta), et/al: no son siglas.
    assert H.siglas_de("Belder et al. 2026 señalan que Los autores y Treatment") == set()
    # Las siglas de la referencia se quitan; LCR y CSF son la misma sigla.
    assert H.siglas_de("GFAP en LCR según DIAN-OBS", {"dian", "obs"}) == {"gfap", "lcr"}
    assert H.siglas_de("GFAP in CSF") == {"gfap", "lcr"}
    assert H.negaciones_de("El tratamiento nunca redujo, jamás, la carga; never neither") == {"nunca", "jamas", "never", "neither"}
    assert H.negaciones_de("no sube sin cambios") == set()  # las cortas son marcas cortas, no negaciones largas
    assert H.comparte_referencia([{"fuenteId": "f-1", "referencia": "Belder et al., 2026"}], [{"fuenteId": "f-2", "referencia": "belder et al. 2026"}])
    assert H.comparte_referencia([{"fuenteId": "f-1"}], [{"fuenteId": "f-1", "referencia": "x"}])
    assert not H.comparte_referencia([{"fuenteId": "f-1", "referencia": "A"}], [{"fuenteId": "f-2", "referencia": "B"}])
    assert not H.comparte_referencia([], []) and not H.comparte_referencia(None, [{"fuenteId": "f"}]) and not H.comparte_referencia("basura", [{"referencia": ""}])
    # "Sin autor" (lo que escribe rosa/fuentes/base.py sin autores) no identifica una obra: solo el id de fuente vale.
    assert not H.comparte_referencia([{"fuenteId": "f-1", "referencia": "Sin autor, 2023"}], [{"fuenteId": "f-2", "referencia": "Sin autor, 2023"}])
    assert H.comparte_referencia([{"fuenteId": "f-1", "referencia": "Sin autor"}], [{"fuenteId": "f-1", "referencia": "Sin autor (alzforum.org)"}])


def test_la_migracion_sigue_fundiendo_la_misma_obra_traida_en_otra_corrida():
    """El caso real (inv-mu2sz2ns-3): el mismo artículo descargado en dos
    corridas, con `fuenteId` distinto y la misma referencia corta. La
    replicación de otra obra (otro id de fuente, otra referencia) vive aparte,
    también después de que el superviviente haya sumado la segunda descarga."""
    e = _e()
    _con_procedencia(e, "he-a", GFAP_ELEVA, F1)
    _con_procedencia(e, "he-b", GFAP_ELEVA_PARAFRASIS, F2_MISMA_OBRA, t=T0 + 1)
    _con_procedencia(e, "he-c", GFAP_ELEVA_PARAFRASIS, F3_OTRA_OBRA, t=T0 + 2)
    r = H.migrar(e, T0 + 999)
    assert r["fundidos"] == 1 and [h["id"] for h in e["hechos"]] == ["he-a", "he-c"]
    a = e["hechos"][0]
    assert [p["fuenteId"] for p in a["procedencia"]] == ["f-1", "f-2"]
    # Un tercer hecho con el id de fuente de la segunda descarga sí se funde: el id de fuente es la misma obra.
    _con_procedencia(e, "he-d", GFAP_ELEVA_PARAFRASIS + ".", [("f-2", "Belder 2026 (otra descarga)", 9)], t=T0 + 3)
    assert H.migrar(e, T0 + 1000)["fundidos"] == 1 and [h["id"] for h in e["hechos"]] == ["he-a", "he-c"]


# -- 7. Conflicto entre un hecho y una afirmación --------------------------------


def test_negados_de_salta_las_vacias_y_para_en_otra_negacion():
    assert H.negados_de("GFAP no sube en portadores") == {"sube"}
    assert H.negados_de("la diferencia no fue estadísticamente significativa") == {"estadisticamente"}
    assert H.negados_de("sin embargo, no no cambia") == {"embargo", "cambia"}
    assert H.negados_de("no") == frozenset() and H.negados_de("") == frozenset()
    assert H.negados_de("Treatment never reduced amyloid") == {"reduced"}


def test_conflicto_es_simetrico_y_no_salta_por_lo_que_la_afirmacion_anade():
    e = _e()
    h = _h(e, "he-a", "GFAP sube en portadores en fase preclínica de la enfermedad")
    # El hecho niega y la afirmación afirma: también es conflicto (la guarda del adversario era de un solo sentido).
    negado = _h(e, "he-n", "GFAP no sube en portadores en fase preclínica de la enfermedad")
    afirmativa = _af("af-1", "GFAP sube en portadores en fase preclínica de la enfermedad")
    assert H.conflicto(negado, afirmativa) == "niega una palabra que el otro afirma"
    assert not H.sostiene(negado, afirmativa) and H.cobertura(negado, afirmativa) == 0.0
    assert H.conflicto(h, _af("af-2", "GFAP no sube en portadores en fase preclínica de la enfermedad")) == "niega una palabra que el otro afirma"
    # Una negación sobre algo que el hecho no menciona no estorba.
    extra = _af("af-3", "GFAP sube en portadores en fase preclínica de la enfermedad; NfL no cambia")
    assert H.conflicto(h, extra) is None and H.sostiene(h, extra)
    # La afirmación habla además de otro marcador: al hecho no le falta ninguna sigla.
    dos = _af("af-4", "GFAP y NfL suben en portadores en fase preclínica de la enfermedad")
    assert H.conflicto(h, dos) is None and H.sostiene(h, dos)
    # Cambio de sigla: falta la del hecho y aparece otra.
    assert H.conflicto(h, _af("af-5", "YKL40 sube en portadores en fase preclínica de la enfermedad")) == "habla de otra sigla"
    assert not H.sostiene(h, _af("af-5", "YKL40 sube en portadores en fase preclínica de la enfermedad"))
    # LCR y CSF son la misma sigla en dos idiomas.
    lcr = _h(e, "he-l", "GFAP en LCR sube en portadores de mutación en fase preclínica")
    csf = _af("af-6", "El GFAP en CSF sube en portadores de mutación en fase preclínica")
    assert H.conflicto(lcr, csf) is None and H.sostiene(lcr, csf)
    # La sigla que solo está en la referencia de la obra no cuenta.
    con_ref = _h(e, "he-r", "Según DIAN-OBS, GFAP sube en portadores en fase preclínica de la enfermedad", referencia="DIAN-OBS 2026")
    assert H.conflicto(con_ref, _af("af-7", "GFAP sube en portadores en fase preclínica de la enfermedad")) is None
    # Registros raros: sin texto no hay conflicto ni enlace.
    assert H.conflicto({"enunciado": None}, {"texto": None}) is None and H.conflicto({}, {}) is None
    assert H.afirmaciones_que_sostienen({**h, "enunciado": ""}, [afirmativa]) == []


def test_la_via_de_equivalencia_de_sostiene_tambien_respeta_el_conflicto():
    """Sin la guarda antes del atajo de equivalencia, "GFAP sube..." y "YKL40
    sube..." (mismas marcas cortas, solape 0,89) se daban por equivalentes."""
    e = _e()
    h = _h(e, "he-a", "GFAP sube en portadores en fase preclínica de la enfermedad de Alzheimer autosómica dominante")
    from rosa import cuestiones as CU

    otra = _af("af-1", "YKL40 sube en portadores en fase preclínica de la enfermedad de Alzheimer autosómica dominante")
    assert CU.equivalencia(h["enunciado"], otra["texto"]) is not None  # el atajo por sí solo la daría por buena
    assert not H.sostiene(h, otra)


# -- 8. Listas en null y remapeo del mapa y de las cifras ------------------------


def test_fundir_y_enlazar_tratan_una_lista_en_null_como_vacia():
    e = _e()
    a = _h(e, "he-a", "GFAP sube antes que NfL", afirmacionIds=None, citas=None, historial=None, entidades=None, procedencia=None, sustituyeA=None)
    b = _h(e, "he-b", "GFAP sube antes que NfL", fuente="f-2", afirmaciones=["af-2"], t=T0 + 1, sustituyeA=["he-z"])
    b["entidades"] = [{"id": "HGNC:4235", "etiqueta": "GFAP", "ontologia": "HGNC", "tipo": "gen", "alias": []}]
    H.fundir(a, b, T0 + 9, "texto normalizado idéntico")
    assert [p["fuenteId"] for p in a["procedencia"]] == ["f-2"] and a["afirmacionIds"] == ["af-2"] and a["citas"] == []
    assert [x["id"] for x in a["entidades"]] == ["HGNC:4235"] and a["sustituyeA"] == ["he-z"]
    assert len(a["historial"]) == 1 and a["historial"][0]["fecha"] == T0 + 9
    viejo = {"id": "he-v", "investigacionId": INV, "tipo": "hecho", "estado": "sabido", "enunciado": "GFAP sube antes que NfL en portadores de mutación en fase preclínica", "procedencia": [{"fuenteId": "f-1", "referencia": "R", "pagina": 4}], "afirmacionIds": None, "citas": None}
    assert H.enlazar(viejo, [_af("af-1", "GFAP sube antes que NfL en portadores de mutación en fase preclínica")]) == 1
    assert viejo["afirmacionIds"] == ["af-1"] and len(viejo["citas"]) == 1


def test_remapear_enlaces_corrige_el_mapa_de_la_enfermedad_y_las_cifras():
    e = _e()
    inv = next(i for i in e["investigaciones"] if i["id"] == INV)
    inv["mapaEnfermedad"] = {"celdas": [{"estadio": "preclinico", "region": None, "tipoCelular": "astrocito", "hechos": ["he-a", "he-b", "he-x"], "hipotesis": [], "preguntas": ["he-b", "he-p"]}, {"estadio": None, "region": None, "tipoCelular": "microglia", "hechos": ["he-c"], "hipotesis": [], "preguntas": []}, "basura"], "huecos": [], "sinEjes": 0}
    inv["cifrasAprendizaje"] = {"reutilizacion": {"detalle": [
        {"hechoId": "he-a", "estado": "sabido", "tema": "B", "usadoPor": ["hip-1"], "motivo": "m1"},
        {"hechoId": "he-b", "estado": "sabido", "tema": "B", "usadoPor": ["hip-2", "hip-1"], "motivo": "m2"},
        {"hechoId": "he-c", "estado": "sabido", "tema": "B", "usadoPor": [], "motivo": "m3"},
        {"hechoId": None, "estado": None, "tema": None, "usadoPor": [], "motivo": "sin hecho"},
        "basura",
    ]}}
    # Otra investigación sin mapa ni cifras, y una con mapa en null: no rompen.
    e["investigaciones"].append({"id": "inv-sin", "mapaEnfermedad": None, "cifrasAprendizaje": None})
    e["investigaciones"].append("basura")
    assert H.remapear_enlaces(e, {"he-b": "he-a"}) == 1
    celdas = inv["mapaEnfermedad"]["celdas"]
    assert celdas[0]["hechos"] == ["he-a", "he-x"] and celdas[0]["preguntas"] == ["he-a", "he-p"] and celdas[1]["hechos"] == ["he-c"]
    detalle = inv["cifrasAprendizaje"]["reutilizacion"]["detalle"]
    assert [d.get("hechoId") if isinstance(d, dict) else d for d in detalle] == ["he-a", "he-c", None, "basura"]
    assert detalle[0]["usadoPor"] == ["hip-1", "hip-2"] and detalle[0]["motivo"] == "m1"
    # Sin nada que cambiar, no toca.
    copia = copy.deepcopy(inv)
    assert H.remapear_enlaces(e, {"he-nada": "he-a"}) == 0 and inv == copia
    assert H.remapear_enlaces(e, {}) == 0
