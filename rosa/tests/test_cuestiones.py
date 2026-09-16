"""Cuestiones persistentes: deduplicación por normalización y por Jaccard,
fusión de ids y veces, tope, movimientos con historial, numeradas y cierre
por índice, poda al volver a una iteración, registros antiguos y textos en
inglés y castellano con tildes."""

import pytest

from rosa import cuestiones as CU
from rosa.estado import acciones as A
from rosa.estado import plantilla as P

INV = "inv-cu"
T0 = 1_000_000


@pytest.fixture
def e():
    estado = P.estado_inicial()
    assert A.crear_investigacion(estado, {"titulo": "T", "objetivo": "GFAP y NfL en sangre", "condicionParada": "3 iteraciones"}, T0, INV) == INV
    return estado


def test_estado_sin_la_clave_la_crea_con_setdefault():
    # Un rosa.db anterior al 16 de septiembre no trae "cuestiones": nada rompe y la clave aparece al primer uso.
    viejo = {"investigaciones": [], "hipotesis": []}
    assert CU.abiertas(viejo, INV) == [] and CU.numeradas(viejo, INV) == ("Ninguna cuestión abierta todavía.", []) and CU.resumen(viejo, INV) == {"abiertas": 0, "resueltas": 0, "descartadas": 0}
    assert CU.para_indice(viejo) == [] and CU.de_hipotesis(viejo, "hip-1") == [] and CU.buscar(viejo, "cu-x") is None
    assert CU.resolver(viejo, "cu-x", "he-1", "m", T0) is False and CU.descartar(viejo, "cu-x", "m", "Rosa", T0) is False and CU.reabrir(viejo, "cu-x", "m", "Rosa", T0) is False
    assert viejo["cuestiones"] == []
    c = CU.registrar({}, _cu("Primera cuestión de un estado vacío"))
    assert c is not None and c["estado"] == "abierta"


def test_entradas_descuidadas_del_integrador_no_rompen(e):
    # `ahora` que falta o no es número: se toma el de ahora, y los tiempos quedan enteros.
    c = CU.nueva(INV, "Sin tiempo declarado", "revisor", "", None)
    assert isinstance(c["creadaEn"], int) and c["creadaEn"] > 0 and c["historial"][0]["fecha"] == c["creadaEn"]
    assert CU.registrar(e, c) is c and CU.resolver(e, c["id"], "he-1", "ok", "no es un número") and isinstance(c["resueltaEn"], int)
    # Sin investigación no entra (no habría dónde mostrarla); solo signos tampoco.
    assert CU.registrar_con_motivo(e, CU.nueva(None, "Huérfana", "revisor", "", T0)) == (None, "sin investigación")
    assert CU.registrar_con_motivo(e, _cu("¿?? ... !!")) == (None, "texto vacío")
    assert CU.desde_killer(e, {"id": "hip-x", "titulo": "Sin investigación"}, "algo que falta", T0) is None
    assert CU.de_hipotesis(e, None) == [] and CU.de_hipotesis(e, "") == []
    # Registro antiguo con números guardados como texto o basura: se leen con el valor por defecto.
    e["cuestiones"].append({"id": "cu-raro", "investigacionId": INV, "texto": "Cuestión con números rotos", "veces": "abc", "creadaEn": "ayer", "prioridad": None, "historial": [{"fecha": "x", "quien": "Rosa", "de": None, "a": "abierta"}]})
    r = CU.registrar(e, _cu("cuestion con numeros rotos"))  # sin tildes
    assert r is e["cuestiones"][-1] and r["veces"] == 2 and r["prioridad"] == 5 and isinstance(r["actualizadaEn"], int)
    assert CU.abiertas(e, INV)[0]["id"] == "cu-raro"  # creadaEn ilegible cuenta como la más antigua
    assert CU.podar_desde(e, INV, None) == 0  # límite ilegible: el de ahora, nada posterior
    assert CU.buscar(e, "cu-raro") is not None


def _cu(texto, resolveria="una cohorte con seguimiento", ahora=T0 + 10, prioridad=5, origen=None, hip=None, hechos=None, quien="Rosa", inv=INV):
    return CU.nueva(inv, texto, origen or {"tipo": "pregunta_modelo", "id": None}, resolveria, ahora, prioridad=prioridad, hipotesis_ids=hip, hecho_ids=hechos, quien=quien)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_nueva_forma_completa_recortes_y_acotados():
    c = CU.nueva(INV, "  ¿Sube   GFAP antes que NfL? " + "x" * 400, {"tipo": "killer", "id": "hip-1"}, "y" * 400, T0, prioridad=0, hipotesis_ids=["hip-1", "hip-1", "", None], hecho_ids=None)
    assert c["id"].startswith("cu-") and c["investigacionId"] == INV and c["estado"] == "abierta"
    assert len(c["texto"]) <= 300 and c["texto"].startswith("¿Sube GFAP antes que NfL?") and len(c["queLaResolveria"]) == 300
    assert c["origen"] == {"tipo": "killer", "id": "hip-1"} and c["hipotesisIds"] == ["hip-1"] and c["hechoIds"] == []
    assert c["prioridad"] == 1 and c["creadaEn"] == T0 and c["actualizadaEn"] == T0 and c["resueltaEn"] is None and c["resolucion"] is None and c["veces"] == 1
    assert c["historial"] == [{"fecha": T0, "de": None, "a": "abierta", "quien": "Rosa", "motivo": "Abierta"}]
    assert CU.nueva(INV, "x", {"tipo": "killer"}, "", T0, prioridad=12)["prioridad"] == 9
    assert CU.nueva(INV, "x", {"tipo": "killer"}, "", T0, prioridad="no")["prioridad"] == 5
    # Un origen desconocido, una cadena o None caen en 'analisis' sin romper.
    assert CU.nueva(INV, "x", {"tipo": "marciano", "id": 7}, "", T0)["origen"] == {"tipo": "analisis", "id": "7"}
    assert CU.nueva(INV, "x", "revisor", "", T0)["origen"] == {"tipo": "revisor", "id": None}
    assert CU.nueva(INV, "x", None, "", T0)["origen"] == {"tipo": "analisis", "id": None}
    # Quién abre queda en el historial (una persona protege la cuestión de la poda).
    assert CU.nueva(INV, "x", "persona", "", T0, quien="Dra. Allegri")["historial"][0]["quien"] == "Dra. Allegri"


# ---------------------------------------------------------------------------
# Normalización y equivalencia
# ---------------------------------------------------------------------------


def test_normalizar_tokens_y_equivalencia():
    assert CU.normalizar("  ¿Qué POBLACIÓN, año?  ") == "que poblacion ano"  # sin tildes
    assert CU.tokens("¿Sube GFAP antes que NfL en sangre?") == {"sube", "gfap", "antes", "sangre"}
    assert CU.equivalencia("¿Sube GFAP antes que NfL en sangre?", "sube gfap antes que nfl en sangre") == "texto normalizado idéntico"
    motivo = CU.equivalencia("¿Sube GFAP antes que NfL en sangre?", "¿Sube GFAP antes que NfL en sangre en preclínicos?")
    assert motivo and motivo.startswith("solape de tokens 0,80")
    assert CU.equivalencia("¿Sube GFAP antes que NfL?", "¿Baja TREM2 en microglía?") is None
    assert CU.equivalencia("", "algo") is None and CU.equivalencia("tau", "NfL") is None
    # Inglés y castellano no se confunden por parecerse en siglas.
    assert CU.equivalencia("Does GFAP rise before NfL in blood?", "¿Sube GFAP antes que NfL en sangre?") is None
    # Siglas y cifras cortas distinguen preguntas que comparten todos los tokens largos.
    assert CU.siglas_cortas("¿Sube GFAP antes que NfL o p53 a los 40 años en LCR?") == {"nfl", "p53", "40", "lcr"}
    assert CU.jaccard("¿Sube GFAP antes que NfL?", "¿Sube GFAP antes que tau?") == 1.0
    assert CU.equivalencia("¿Sube GFAP antes que NfL?", "¿Sube GFAP antes que tau?") is None
    assert CU.equivalencia("¿Cambia el orden en la cohorte 3?", "¿Cambia el orden en la cohorte 4?") is None
    assert CU.equivalencia("¿Cambia el orden de alteración en la cohorte A4 preclínica?", "¿Cambia el orden de alteración en la cohorte A4 preclínica temprana?") is not None  # 5 de 6 tokens, misma sigla


# ---------------------------------------------------------------------------
# Registro y deduplicación
# ---------------------------------------------------------------------------


def test_registrar_nueva_y_dedupe_por_normalizacion_funde_ids_veces_y_prioridad(e):
    a = _cu("¿Sube GFAP antes que NfL en sangre?", prioridad=6, hip=["hip-1"], hechos=["he-1"])
    res, motivo = CU.registrar_con_motivo(e, a)
    assert res is a and motivo == "nueva" and e["cuestiones"] == [a]
    b = _cu("sube gfap antes que nfl en sangre", resolveria="", ahora=T0 + 50, prioridad=2, hip=["hip-2", "hip-1"], hechos=["he-2"])
    res, motivo = CU.registrar_con_motivo(e, b)
    assert res is a and motivo == f"fundida con {a['id']}: texto normalizado idéntico"
    assert len(e["cuestiones"]) == 1 and a["veces"] == 2 and a["prioridad"] == 2 and a["actualizadaEn"] == T0 + 50
    assert a["hipotesisIds"] == ["hip-1", "hip-2"] and a["hechoIds"] == ["he-1", "he-2"]
    assert a["queLaResolveria"] == "una cohorte con seguimiento"  # la primera no se pisa
    assert len(a["historial"]) == 1  # fundir no es un movimiento de estado


def test_registrar_dedupe_por_jaccard_y_no_por_debajo_del_umbral(e):
    a = CU.registrar(e, _cu("¿Sube GFAP antes que NfL en sangre?"))
    b = CU.registrar(e, _cu("¿Sube GFAP antes que NfL en sangre en preclínicos?", ahora=T0 + 20))
    assert b is a and a["veces"] == 2 and len(e["cuestiones"]) == 1
    # 3 de 5 tokens compartidos (0,6): otra cuestión.
    c = CU.registrar(e, _cu("¿Sube GFAP antes que NfL en líquido cefalorraquídeo?"))
    assert c is not a and len(e["cuestiones"]) == 2
    # Misma cuestión en otra investigación: no se funde entre investigaciones.
    A.crear_investigacion(e, {"titulo": "T2", "objetivo": "O", "condicionParada": "1 iteración"}, T0, "inv-otra")
    d = CU.registrar(e, _cu("¿Sube GFAP antes que NfL en sangre?", inv="inv-otra"))
    assert d is not a and len(e["cuestiones"]) == 3


def test_registrar_devuelve_la_resuelta_sin_reabrir_y_no_repite_ids(e):
    a = CU.registrar(e, _cu("¿Qué cohorte independiente replica el orden GFAP, NfL, p-tau181?"))
    assert CU.resolver(e, a["id"], "he-9", "Lo responde BIOCARD", T0 + 100)
    res, motivo = CU.registrar_con_motivo(e, _cu("que cohorte independiente replica el orden gfap nfl p-tau181", ahora=T0 + 200))
    assert res is a and a["estado"] == "resuelta" and a["veces"] == 1 and motivo.startswith(f"ya resuelta: {a['id']}")
    assert len(e["cuestiones"]) == 1
    # El mismo objeto (mismo id) dos veces no se duplica.
    res, motivo = CU.registrar_con_motivo(e, a)
    assert res is a and motivo == f"ya registrada: {a['id']}" and len(e["cuestiones"]) == 1
    # Texto vacío no entra.
    assert CU.registrar_con_motivo(e, _cu("   ")) == (None, "texto vacío")
    assert CU.registrar_con_motivo(e, "no soy un dict") == (None, "cuestión inválida")


def test_tope_de_abiertas_por_investigacion(e):
    for i in range(CU.MAX_CUESTIONES_ABIERTAS):
        assert CU.registrar(e, _cu(f"Cuestión número {i} sobre el biomarcador de la cohorte {i}")) is not None
    assert CU.resumen(e, INV)["abiertas"] == 60
    res, motivo = CU.registrar_con_motivo(e, _cu("Una cuestión más que ya no cabe en la lista"))
    assert res is None and motivo == "tope de 60 abiertas alcanzado" and CU.resumen(e, INV)["abiertas"] == 60
    # Una equivalente de una ya abierta sigue fundiéndose aunque haya tope.
    res, motivo = CU.registrar_con_motivo(e, _cu("cuestion numero 3 sobre el biomarcador de la cohorte 3"))  # sin tildes
    assert res is not None and res["veces"] == 2 and motivo.startswith("fundida con")
    # Al resolver una, vuelve a haber sitio.
    assert CU.resolver(e, e["cuestiones"][0]["id"], "he-1", "respondida", T0 + 500)
    assert CU.registrar(e, _cu("Una cuestión más que ya no cabe en la lista")) is not None
    # Otra investigación tiene su propio tope.
    A.crear_investigacion(e, {"titulo": "T2", "objetivo": "O", "condicionParada": "1 iteración"}, T0, "inv-otra")
    assert CU.registrar(e, _cu("Primera de la otra investigación", inv="inv-otra")) is not None


# ---------------------------------------------------------------------------
# Movimientos de estado
# ---------------------------------------------------------------------------


def test_resolver_descartar_reabrir_con_historial(e):
    a = CU.registrar(e, _cu("¿Hay réplica independiente del orden de alteración?"))
    assert CU.resolver(e, "cu-no-existe", "he-1", "x", T0 + 1) is False
    assert CU.descartar(e, a["id"], "   ", "Dra. Allegri", T0 + 1) is False  # exige motivo
    assert a["estado"] == "abierta" and len(a["historial"]) == 1
    assert CU.resolver(e, a["id"], "he-7", "Respondida por el hecho: BIOCARD replica el orden", T0 + 100, quien="Rosa")
    assert a["estado"] == "resuelta" and a["resueltaEn"] == T0 + 100 and a["actualizadaEn"] == T0 + 100
    assert a["resolucion"] == {"por": "he-7", "motivo": "Respondida por el hecho: BIOCARD replica el orden"}
    assert a["historial"][-1] == {"fecha": T0 + 100, "de": "abierta", "a": "resuelta", "quien": "Rosa", "motivo": "Respondida por el hecho: BIOCARD replica el orden", "por": "he-7"}
    assert CU.resolver(e, a["id"], "he-8", "otra vez", T0 + 101) is False  # ya no está abierta
    assert CU.descartar(e, a["id"], "no aplica", "Dra. Allegri", T0 + 102) is False
    assert CU.reabrir(e, a["id"], "El hecho he-7 se retiró", "Dra. Allegri", T0 + 200)
    assert a["estado"] == "abierta" and a["resueltaEn"] is None and a["resolucion"] is None
    assert a["historial"][-1] == {"fecha": T0 + 200, "de": "resuelta", "a": "abierta", "quien": "Dra. Allegri", "motivo": "El hecho he-7 se retiró"}
    assert CU.reabrir(e, a["id"], "ya abierta", "Rosa", T0 + 201) is False
    assert CU.descartar(e, a["id"], "Fuera del alcance de la misión", "Dra. Allegri", T0 + 300)
    assert a["estado"] == "descartada" and a["historial"][-1]["a"] == "descartada" and a["historial"][-1]["quien"] == "Dra. Allegri"
    assert CU.reabrir(e, a["id"], "", "Rosa", T0 + 400) and a["historial"][-1]["motivo"] == "Reabierta sin motivo declarado"
    assert [m["a"] for m in a["historial"]] == ["abierta", "resuelta", "abierta", "descartada", "abierta"]
    # Resolver sin `por` cae en quien resuelve.
    assert CU.resolver(e, a["id"], "", "", T0 + 500, quien="Dr. Pérez") and a["resolucion"] == {"por": "Dr. Pérez", "motivo": "Resuelta"}


# ---------------------------------------------------------------------------
# Lectura: abiertas, de_hipotesis, numeradas, texto, resumen, índice
# ---------------------------------------------------------------------------


def test_abiertas_orden_de_hipotesis_y_resumen(e):
    a = CU.registrar(e, _cu("Cuestión de prioridad cinco creada primero", prioridad=5, ahora=T0 + 1, hip=["hip-1"]))
    b = CU.registrar(e, _cu("Cuestión de prioridad dos creada después", prioridad=2, ahora=T0 + 2))
    c = CU.registrar(e, _cu("Cuestión de prioridad cinco creada la última", prioridad=5, ahora=T0 + 3, origen={"tipo": "killer", "id": "hip-1"}))
    d = CU.registrar(e, _cu("Cuestión que se descarta luego", prioridad=1, ahora=T0 + 4, hip=["hip-1"]))
    assert CU.descartar(e, d["id"], "duplicada en espíritu", "Dra. Allegri", T0 + 5)
    assert [x["id"] for x in CU.abiertas(e, INV)] == [b["id"], a["id"], c["id"]]
    assert [x["id"] for x in CU.abiertas(e, INV, maximo=1)] == [b["id"]]
    assert CU.abiertas(e, "inv-inexistente") == []
    # de_hipotesis: por hipotesisIds o por origen killer/escalera; abiertas primero.
    assert [x["id"] for x in CU.de_hipotesis(e, "hip-1")] == [a["id"], c["id"], d["id"]]
    assert CU.de_hipotesis(e, "hip-99") == []
    assert CU.resumen(e, INV) == {"abiertas": 3, "resueltas": 0, "descartadas": 1}
    assert CU.resumen(e, "inv-inexistente") == {"abiertas": 0, "resueltas": 0, "descartadas": 0}


def test_numeradas_texto_abiertas_y_para_indice(e):
    e["hipotesis"].append(P.nueva_hipotesis(INV, 1, T0, id="hip-1", titulo="GFAP se altera antes que NfL"))
    assert CU.numeradas(e, INV) == ("Ninguna cuestión abierta todavía.", [])
    assert CU.texto_abiertas(e, INV) == "Sin cuestiones abiertas todavía."
    a = CU.registrar(e, _cu("¿Qué cohorte independiente replica el orden?", resolveria="una segunda cohorte con seguimiento", prioridad=2))
    b = CU.registrar(e, _cu("una segunda cohorte independiente que muestre lo mismo", resolveria="", prioridad=3, origen={"tipo": "killer", "id": "hip-1"}, hip=["hip-1"]))
    c = CU.registrar(e, _cu("Peldaño de certeza pendiente", resolveria="", prioridad=4, origen={"tipo": "escalera", "id": "hip-sin-titulo"}))
    d = CU.registrar(e, _cu("Pedida por la médica", resolveria="", prioridad=5, origen={"tipo": "persona", "id": None}, quien="Dra. Allegri"))
    texto, lista = CU.numeradas(e, INV)
    assert [x["id"] for x in lista] == [a["id"], b["id"], c["id"], d["id"]]
    lineas = texto.split("\n")
    assert lineas[0] == "1. ¿Qué cohorte independiente replica el orden? (la resolvería: una segunda cohorte con seguimiento) [origen: pregunta del modelo de mundo]"
    assert lineas[1] == "2. una segunda cohorte independiente que muestre lo mismo [origen: Killer sobre H «GFAP se altera antes que NfL»]"
    assert lineas[2] == "3. Peldaño de certeza pendiente [origen: escalera de certeza sobre H hip-sin-titulo]"
    assert lineas[3] == "4. Pedida por la médica [origen: persona (Dra. Allegri)]"  # el modelo ve quién la pidió
    texto2, lista2 = CU.numeradas(e, INV, maximo=2)
    assert len(lista2) == 2 and texto2.count("\n") == 1
    t = CU.texto_abiertas(e, INV, maximo=2)
    assert t.startswith("Cuestiones abiertas (2 de 4):\n1. ¿Qué cohorte independiente replica el orden? (prioridad 2) (la resolvería:")
    items = CU.para_indice(e)
    assert len(items) == 4 and items[0] == {"id": f"cuestion:{a['id']}", "tipo": "cuestion", "investigacionId": INV, "texto": "¿Qué cohorte independiente replica el orden?. una segunda cohorte con seguimiento"}
    assert items[1]["texto"] == "una segunda cohorte independiente que muestre lo mismo"
    assert CU.resolver(e, a["id"], "he-1", "ok", T0 + 9) and len(CU.para_indice(e)) == 3


def test_cerradas_por_hecho_con_indices_fuera_de_rango_repetidos_y_no_numericos(e):
    a = CU.registrar(e, _cu("¿Qué cohorte independiente replica el orden GFAP, NfL, p-tau181?"))
    b = CU.registrar(e, _cu("¿A qué edad empieza a subir GFAP en portadores de APOE4?"))
    c = CU.registrar(e, _cu("¿Cambia el orden en síndrome de Down?"))
    texto, lista = CU.numeradas(e, INV)
    hecho = P.nuevo_hecho(INV, "hecho", "biomarcadores", "En BIOCARD el orden GFAP, NfL y p-tau181 se replica con 10 años de seguimiento", "sabido", "fuente", [], T0 + 50)
    ids = CU.cerradas_por_hecho(e, INV, hecho, [1, 1, 7, 0, -1, "3", "tres", None, 2.0], lista, T0 + 60)
    assert ids == [a["id"], c["id"], b["id"]]
    for x in (a, b, c):
        assert x["estado"] == "resuelta" and x["resolucion"]["por"] == hecho["id"] and x["resolucion"]["motivo"].startswith("Respondida por el hecho: En BIOCARD el orden")
    # Ya resueltas: una segunda pasada no resuelve nada; sin índices tampoco.
    assert CU.cerradas_por_hecho(e, INV, hecho, [1, 2, 3], lista, T0 + 70) == []
    d = CU.registrar(e, _cu("Otra cuestión abierta"))
    _, lista2 = CU.numeradas(e, INV)
    assert CU.cerradas_por_hecho(e, INV, hecho, [], lista2, T0 + 80) == [] and CU.cerradas_por_hecho(e, INV, hecho, None, lista2, T0 + 80) == []
    # Una pregunta no responde a otra pregunta; un hecho sin id tampoco; otra investigación tampoco.
    pregunta = P.nuevo_hecho(INV, "pregunta", "t", "¿Y en LCR?", "abierto", "inferencia", [], T0 + 90)
    assert CU.cerradas_por_hecho(e, INV, pregunta, [1], lista2, T0 + 90) == []
    assert CU.cerradas_por_hecho(e, INV, {"enunciado": "sin id"}, [1], lista2, T0 + 90) == []
    assert CU.cerradas_por_hecho(e, "inv-otra", hecho, [1], lista2, T0 + 90) == [] and d["estado"] == "abierta"
    assert CU.cerradas_por_hecho(e, INV, hecho, [1], lista2, T0 + 91) == [d["id"]]


# ---------------------------------------------------------------------------
# Poda al volver a una iteración
# ---------------------------------------------------------------------------


def test_podar_desde_respeta_las_de_persona_y_deshace_movimientos_de_rosa(e):
    limite = T0 + 1000
    antes = CU.registrar(e, _cu("Creada antes del límite por Rosa", ahora=T0 + 100))
    antes_resuelta = CU.registrar(e, _cu("Creada antes y resuelta después por Rosa", ahora=T0 + 200))
    antes_persona = CU.registrar(e, _cu("Creada antes y descartada después por una persona", ahora=T0 + 300))
    despues_rosa = CU.registrar(e, _cu("Creada después del límite por Rosa", ahora=T0 + 2000))
    despues_persona = CU.registrar(e, _cu("Creada después del límite por la médica", ahora=T0 + 2100, origen="persona", quien="Dra. Allegri"))
    despues_rosa_tocada = CU.registrar(e, _cu("Creada después por Rosa y descartada por la médica", ahora=T0 + 2200))
    A.crear_investigacion(e, {"titulo": "T2", "objetivo": "O", "condicionParada": "1 iteración"}, T0, "inv-otra")
    otra_inv = CU.registrar(e, _cu("De otra investigación, después del límite", ahora=T0 + 2300, inv="inv-otra"))
    assert CU.resolver(e, antes_resuelta["id"], "he-podado", "Respondida por el hecho: X", T0 + 2500)
    assert CU.descartar(e, antes_persona["id"], "no interesa", "Dra. Allegri", T0 + 2600)
    assert CU.descartar(e, despues_rosa_tocada["id"], "no interesa", "Dra. Allegri", T0 + 2700)
    assert CU.podar_desde(e, INV, limite) == 1
    ids = {c["id"] for c in e["cuestiones"]}
    assert despues_rosa["id"] not in ids
    assert {antes["id"], antes_resuelta["id"], antes_persona["id"], despues_persona["id"], despues_rosa_tocada["id"], otra_inv["id"]} <= ids
    # La resuelta por Rosa después del límite vuelve a abierta y pierde la resolución; el historial queda hasta el límite.
    assert antes_resuelta["estado"] == "abierta" and antes_resuelta["resolucion"] is None and antes_resuelta["resueltaEn"] is None
    assert len(antes_resuelta["historial"]) == 1 and antes_resuelta["actualizadaEn"] == limite
    # La descartada por una persona después del límite no se toca.
    assert antes_persona["estado"] == "descartada" and len(antes_persona["historial"]) == 2
    assert despues_rosa_tocada["estado"] == "descartada"
    # Sin la clave en el estado, la poda no rompe y devuelve 0.
    assert CU.podar_desde({}, INV, limite) == 0


# ---------------------------------------------------------------------------
# Ayudas para el integrador
# ---------------------------------------------------------------------------


def test_desde_pregunta_hecho_killer_y_escalera(e):
    h = P.nueva_hipotesis(INV, 1, T0, id="hip-1", titulo="GFAP se altera antes que NfL en amiloide positivos")
    e["hipotesis"].append(h)
    hecho = P.nuevo_hecho(INV, "pregunta", "biomarcadores", "¿Qué cohorte independiente replica el orden de alteración?", "abierto", "inferencia", [], T0 + 10, prioridad=2)
    c1 = CU.desde_pregunta_hecho(e, hecho, "Una cohorte distinta de la original con el mismo orden", T0 + 10)
    assert c1 and c1["origen"] == {"tipo": "pregunta_modelo", "id": hecho["id"]} and c1["hechoIds"] == [hecho["id"]] and c1["prioridad"] == 2 and c1["hipotesisIds"] == []
    assert c1["queLaResolveria"] == "Una cohorte distinta de la original con el mismo orden"
    c2 = CU.desde_killer(e, h, "una segunda cohorte independiente que muestre lo mismo", T0 + 20)
    assert c2 and c2 is not c1 and c2["origen"] == {"tipo": "killer", "id": "hip-1"} and c2["hipotesisIds"] == ["hip-1"] and c2["prioridad"] == 3
    assert c2["texto"] == "una segunda cohorte independiente que muestre lo mismo" and "«GFAP se altera antes que NfL en amiloide positivos»" in c2["queLaResolveria"]
    # La escalera dice casi lo mismo para la misma hipótesis: se funde con la del Killer (Jaccard), sin cuestión nueva.
    c3 = CU.desde_escalera(e, h, "una segunda cohorte independiente que muestre lo mismo en la literatura", T0 + 30)
    assert c3 is c2 and c2["veces"] == 2 and c2["prioridad"] == 3 and len(e["cuestiones"]) == 2
    c4 = CU.desde_escalera(e, h, "evidencia directa: un análisis in silico sobre un dataset público aprobado", T0 + 40)
    assert c4 and c4["origen"] == {"tipo": "escalera", "id": "hip-1"} and c4["prioridad"] == 4 and c4["hipotesisIds"] == ["hip-1"]
    assert CU.de_hipotesis(e, "hip-1") == [c2, c4]
    # Entradas vacías o mal formadas: None, sin romper.
    assert CU.desde_pregunta_hecho(e, {"id": "he-x", "investigacionId": INV, "enunciado": "  "}, "x", T0) is None
    assert CU.desde_pregunta_hecho(e, None, "x", T0) is None
    assert CU.desde_killer(e, h, "", T0) is None and CU.desde_killer(e, None, "algo", T0) is None
    assert CU.desde_escalera(e, h, "   ", T0) is None
    # Una hipótesis sin título ni id no rompe el texto.
    c5 = CU.desde_killer(e, {"investigacionId": INV}, "un control negativo con otra proteína", T0 + 50)
    assert c5 and c5["hipotesisIds"] == [] and c5["origen"] == {"tipo": "killer", "id": None} and c5["queLaResolveria"] == "Una afirmación sostenida o un análisis que aporte eso"
    assert CU.etiqueta_origen(e, c5) == "Killer"


# ---------------------------------------------------------------------------
# Registros antiguos y textos
# ---------------------------------------------------------------------------


def test_registros_antiguos_sin_claves_nuevas_no_rompen(e):
    e["cuestiones"] = [
        {"id": "cu-viejo-1", "investigacionId": INV, "texto": "Cuestión vieja sin más claves"},
        {"id": "cu-viejo-2", "investigacionId": INV, "texto": "Otra vieja con estado raro", "estado": "pendiente", "prioridad": "3", "historial": None, "origen": None},
        {"id": "cu-viejo-3", "investigacionId": INV, "texto": "Vieja resuelta", "estado": "resuelta"},
    ]
    ab = CU.abiertas(e, INV)
    assert [c["id"] for c in ab] == ["cu-viejo-2", "cu-viejo-1"]  # prioridad "3" antes que la 5 por defecto
    texto, lista = CU.numeradas(e, INV)
    assert texto == "1. Otra vieja con estado raro [origen: análisis]\n2. Cuestión vieja sin más claves [origen: análisis]" and len(lista) == 2
    assert CU.texto_abiertas(e, INV).startswith("Cuestiones abiertas (2 de 2):")
    assert CU.resumen(e, INV) == {"abiertas": 2, "resueltas": 1, "descartadas": 0}
    assert len(CU.para_indice(e)) == 2 and CU.de_hipotesis(e, "hip-1") == []
    # Registrar una equivalente de la vieja la funde y le crea las claves que le faltaban.
    r = CU.registrar(e, _cu("cuestion vieja sin mas claves", hip=["hip-1"]))  # sin tildes
    assert r is e["cuestiones"][0] and r["veces"] == 2 and r["hipotesisIds"] == ["hip-1"] and r["hechoIds"] == [] and r["prioridad"] == 5
    # Resolver y descartar sobre registros sin historial crean el historial.
    assert CU.resolver(e, "cu-viejo-2", "he-1", "ok", T0 + 5) and e["cuestiones"][1]["historial"][-1]["de"] == "abierta"
    assert CU.reabrir(e, "cu-viejo-3", "otra vez", "Dra. Allegri", T0 + 6) and e["cuestiones"][2]["estado"] == "abierta"
    # La poda trata el registro sin historial como de Rosa (valor de hoy) y sin creadaEn como antiguo (0).
    assert CU.podar_desde(e, INV, T0) == 0 and len(e["cuestiones"]) == 3
    e["cuestiones"].append({"id": "cu-viejo-4", "investigacionId": INV, "texto": "Nueva sin historial", "creadaEn": T0 + 999})
    assert CU.podar_desde(e, INV, T0) == 1


def test_textos_en_ingles_y_castellano_con_tildes(e):
    a = CU.registrar(e, _cu("¿Qué población tiene más riesgo según la edad?"))
    b = CU.registrar(e, _cu("que poblacion tiene mas riesgo segun la edad", ahora=T0 + 1))  # sin tildes
    assert b is a and a["veces"] == 2 and a["texto"] == "¿Qué población tiene más riesgo según la edad?"  # se conserva el texto con tildes
    c = CU.registrar(e, _cu("Which population is at higher risk by age?"))
    assert c is not a and len(e["cuestiones"]) == 2
    d = CU.registrar(e, _cu("Which population is at higher risk by age", ahora=T0 + 2))
    assert d is c and c["veces"] == 2
    texto, _ = CU.numeradas(e, INV)
    assert "¿Qué población tiene más riesgo según la edad?" in texto and "Which population is at higher risk by age?" in texto
    assert "la resolvería" in texto and "Ninguna cuestión" not in texto


# ---------------------------------------------------------------------------
# Adversarial (segunda pasada, 16 de septiembre de 2026): lo que rompió
# ---------------------------------------------------------------------------


def test_marcas_cortas_en_minuscula_negacion_griegas_y_vacias_con_tilde():
    # Antes la salvaguarda solo miraba tokens cortos con mayúscula o dígito del texto original:
    # "nfl" y "tau" en minúscula no contaban y las dos preguntas se fundían (Jaccard 1,0).
    assert CU.jaccard("sube gfap antes que nfl en sangre", "sube gfap antes que tau en sangre") == 1.0
    assert CU.equivalencia("sube gfap antes que nfl en sangre", "sube gfap antes que tau en sangre") is None
    assert CU.equivalencia("does gfap rise before nfl in blood", "does gfap rise before tau in blood") is None
    # La misma sigla en mayúscula y en minúscula sí es la misma marca (se mide sobre el texto normalizado).
    assert CU.equivalencia("¿Sube GFAP antes que NfL en sangre?", "¿Sube GFAP antes que nfl en sangre en preclínicos?") is not None
    # La negación cambia el sentido: no se funde.
    assert CU.equivalencia("¿Sube en amiloide positivos?", "¿Sube en no amiloide positivos?") is None
    assert CU.equivalencia("¿Se mide con seguimiento longitudinal?", "¿Se mide sin seguimiento longitudinal?") is None
    # Las palabras vacías no cuentan como marca, con o sin tilde (la lista se normaliza al cargar).
    assert CU.marcas_cortas("así que más aún, de la que él y ella") == set()
    assert CU.marcas_cortas("¿Sube GFAP antes que NfL o p53 a los 40 años en LCR?") == {"nfl", "p53", "40", "lcr"}
    assert CU.siglas_cortas is CU.marcas_cortas  # nombre anterior conservado
    # Letras griegas por su nombre: Aβ no desaparece ("a"), y coincide con Abeta.
    assert CU.normalizar("¿Baja Aβ42 y TNF-α en LCR?") == "baja abeta42 y tnf alfa en lcr"
    assert CU.equivalencia("¿Baja Aβ42 en plasma?", "¿Baja Abeta42 en plasma?") == "texto normalizado idéntico"
    assert CU.equivalencia("¿Baja Aβ en LCR?", "¿Baja en LCR?") is None
    assert CU.normalizar("5 µg y 5 μg") == "5 mug y 5 mug"  # signo micro y mu griega, lo mismo
    # Las reglas siguen siendo simétricas y deterministas.
    for a, b in (("¿Sube GFAP antes que NfL en sangre?", "¿Sube GFAP antes que NfL en sangre en preclínicos?"), ("x y z", "z y x")):
        assert CU.equivalencia(a, b) == CU.equivalencia(b, a)


def test_persona_que_repite_deja_huella_y_la_poda_la_respeta(e):
    limite = T0 + 1000
    # Rosa abre después del límite; la médica vuelve a preguntar lo mismo y se funde.
    a = CU.registrar(e, _cu("¿La plataforma Simoa mide GFAP igual que Lumipulse?", ahora=T0 + 2000))
    b = CU.registrar(e, _cu("la plataforma simoa mide gfap igual que lumipulse", ahora=T0 + 2100, quien="Dra. Allegri", origen="persona"))
    assert b is a and a["veces"] == 2
    assert a["historial"][-1] == {"fecha": T0 + 2100, "de": "abierta", "a": "abierta", "quien": "Dra. Allegri", "motivo": "Preguntada otra vez"}
    # Antes la fusión no dejaba huella y la poda borraba la pregunta de la médica.
    assert CU.podar_desde(e, INV, limite) == 0 and CU.buscar(e, a["id"]) is a
    # Cuando repite Rosa (el Killer cada iteración) no se anota nada.
    c = CU.registrar(e, _cu("La plataforma Simoa mide GFAP igual que Lumipulse", ahora=T0 + 2200))
    assert c is a and a["veces"] == 3 and len(a["historial"]) == 2
    # Una creada antes del límite por Rosa que la médica repreguntó después tampoco se toca.
    d = CU.registrar(e, _cu("¿Qué cohorte independiente replica el orden?", ahora=T0 + 100))
    CU.registrar(e, _cu("que cohorte independiente replica el orden", ahora=T0 + 3000, quien="Dra. Allegri", origen="persona"))
    assert CU.podar_desde(e, INV, limite) == 0 and d["estado"] == "abierta" and len(d["historial"]) == 2


def test_tope_no_frena_a_la_persona(e):
    for i in range(CU.MAX_CUESTIONES_ABIERTAS):
        assert CU.registrar(e, _cu(f"Cuestión automática número {i} sobre el marcador {i}")) is not None
    assert CU.registrar_con_motivo(e, _cu("Una más de Rosa que no cabe"))[1] == "tope de 60 abiertas alcanzado"
    res, motivo = CU.registrar_con_motivo(e, _cu("¿Qué pasa con la plataforma de medida?", quien="Dra. Allegri", origen="persona"))
    assert res is not None and motivo == "nueva" and CU.resumen(e, INV)["abiertas"] == 61
    assert CU.etiqueta_origen(e, res) == "persona (Dra. Allegri)"


def test_buscar_con_id_vacio_no_casa_con_un_registro_sin_id(e):
    e["cuestiones"].append({"investigacionId": INV, "texto": "Registro antiguo sin id"})
    assert CU.buscar(e, None) is None and CU.buscar(e, "") is None
    assert CU.resolver(e, None, "he-1", "x", T0) is False and CU.descartar(e, "", "m", "Rosa", T0) is False
    assert e["cuestiones"][0].get("estado") is None  # nadie lo tocó
    # Un hecho nuevo con una lista numerada que trae un registro sin id tampoco resuelve nada.
    hecho = P.nuevo_hecho(INV, "hecho", "t", "Algo", "sabido", "fuente", [], T0)
    assert CU.cerradas_por_hecho(e, INV, hecho, [1], [e["cuestiones"][0]], T0) == []


def test_maximo_negativo_es_sin_limite_y_cero_no_dice_ninguna(e):
    for i in range(3):
        CU.registrar(e, _cu(f"Cuestión distinta número {i} sobre el marcador {i}"))
    assert len(CU.abiertas(e, INV, maximo=-1)) == 3  # antes quitaba la última
    assert CU.abiertas(e, INV, maximo=0) == [] and CU.abiertas(e, INV, maximo="2") == CU.abiertas(e, INV, maximo=2)
    assert CU.numeradas(e, INV, maximo=0) == ("Hay 3 cuestiones abiertas, ninguna listada.", [])
    assert CU.texto_abiertas(e, INV, maximo=0) == "Cuestiones abiertas (0 de 3):"
    assert CU.numeradas(e, "inv-vacia", maximo=0) == ("Ninguna cuestión abierta todavía.", [])


def test_entradas_rotas_en_la_lista_y_claves_con_otro_tipo_no_rompen(e):
    e["cuestiones"].extend([None, "basura", 7])
    e["cuestiones"].append({"id": "cu-s", "investigacionId": INV, "texto": "Origen como cadena", "origen": "killer", "hipotesisIds": "hip-1", "hechoIds": None})
    assert [c["id"] for c in CU.abiertas(e, INV)] == ["cu-s"] and CU.buscar(e, "cu-s") is not None
    assert CU.numeradas(e, INV)[0] == "1. Origen como cadena [origen: Killer sobre H hip-1]"
    assert [c["id"] for c in CU.de_hipotesis(e, "hip-1")] == ["cu-s"] and CU.de_hipotesis(e, "hip-10") == []  # no por subcadena
    assert CU.resumen(e, INV) == {"abiertas": 1, "resueltas": 0, "descartadas": 0} and len(CU.para_indice(e)) == 1
    # Fundir con hipotesisIds como cadena no lo parte en letras.
    r = CU.registrar(e, _cu("origen como cadena", hip=["hip-2"]))
    assert r["id"] == "cu-s" and r["hipotesisIds"] == ["hip-1", "hip-2"] and r["hechoIds"] == []
    # La poda conserva las entradas rotas en su sitio y no cuenta ninguna.
    assert CU.podar_desde(e, INV, T0) == 0 and None in e["cuestiones"] and "basura" in e["cuestiones"]
    # La clave "cuestiones" con un tipo que no es lista se sustituye por una lista vacía.
    raro = {"cuestiones": "no soy una lista"}
    assert CU.abiertas(raro, INV) == [] and raro["cuestiones"] == []


def test_saltos_de_linea_colapsados_y_poda_en_sitio(e):
    e["cuestiones"].append({"id": "cu-v", "investigacionId": INV, "texto": "Primera línea\nsegunda línea\n\ttercera", "queLaResolveria": "algo\ncon salto"})
    texto, lista = CU.numeradas(e, INV)
    assert "\n" not in texto and texto == "1. Primera línea segunda línea tercera (la resolvería: algo con salto) [origen: análisis]"
    assert CU.para_indice(e)[0]["texto"] == "Primera línea segunda línea tercera. algo con salto"
    lista_viva = e["cuestiones"]
    CU.registrar(e, _cu("Creada después del límite", ahora=T0 + 5000))
    assert CU.podar_desde(e, INV, T0 + 1000) == 1 and e["cuestiones"] is lista_viva and len(lista_viva) == 1


def test_cerradas_por_hecho_ignora_booleanos_cadenas_y_hecho_sin_enunciado(e):
    a = CU.registrar(e, _cu("Algo abierto"))
    _, lista = CU.numeradas(e, INV)
    assert CU.cerradas_por_hecho(e, INV, {"id": "he-1"}, [True], lista, T0) == []  # True valdría 1
    assert CU.cerradas_por_hecho(e, INV, {"id": "he-1"}, "1", lista, T0) == [] and a["estado"] == "abierta"
    assert CU.cerradas_por_hecho(e, INV, {"id": "he-1"}, [1], lista, T0) == [a["id"]]
    assert a["resolucion"] == {"por": "he-1", "motivo": "Respondida por el hecho he-1"}  # sin enunciado no queda un dos puntos colgando


def test_registrar_no_es_cuadratico_con_miles_de_cerradas(e):
    import time

    CU._perfil.cache_clear()
    t = time.perf_counter()
    for i in range(800):
        c = CU.registrar(e, _cu(f"Cuestión cerrada número {i} sobre el biomarcador y la cohorte de seguimiento {i}"))
        assert CU.resolver(e, c["id"], "he-1", "ok", T0 + 20)
    for i in range(60):
        CU.registrar(e, _cu(f"Cuestión abierta número {i} sobre el marcador plasmático {i}"))
    for i in range(100):
        CU.registrar(e, _cu(f"Cuestión nueva de prueba número {i} sobre otra cosa distinta {i}"))
    # Sin la caché de perfiles, solo las 800 cerradas tardaban más de un minuto.
    assert time.perf_counter() - t < 8.0
    info = CU._perfil.cache_info()
    assert info.hits > info.misses and CU.resumen(e, INV) == {"abiertas": 60, "resueltas": 800, "descartadas": 0}


# ---------------------------------------------------------------------------
# Adversarial (tercera pasada, 16 de septiembre de 2026): lo que rompió
# ---------------------------------------------------------------------------


def test_inversion_de_orden_o_direccion_no_se_funde(e):
    # Misma bolsa de palabras, pregunta contraria: antes se fundían con Jaccard 1,0.
    assert CU.jaccard("¿Sube GFAP antes que NfL en sangre?", "¿Sube NfL antes que GFAP en sangre?") == 1.0
    assert CU.equivalencia("¿Sube GFAP antes que NfL en sangre?", "¿Sube NfL antes que GFAP en sangre?") is None
    assert CU.equivalencia("Does GFAP rise before NfL in blood?", "Does NfL rise before GFAP in blood?") is None
    assert CU.equivalencia("¿La microglía activada causa la pérdida sináptica?", "¿La pérdida sináptica causa la microglía activada?") is None
    assert CU.equivalencia("¿GFAP predice el declive cognitivo?", "¿El declive cognitivo predice GFAP?") is None
    # Con dos marcadores de nombre corto (tau, NfL) las marcas cortas coinciden y solo el orden distingue.
    assert CU.equivalencia("¿Sube tau antes que NfL?", "¿Sube NfL antes que tau?") is None
    assert CU.mismo_orden("¿Sube tau antes que NfL?", "¿Sube NfL antes que tau?") is False
    # Sin palabra de orden, reordenar la frase sigue siendo la misma cuestión (la carencia del Killer reescrita).
    assert CU.equivalencia("¿Qué cohorte independiente replica el orden GFAP, NfL, p-tau181?", "¿Replica alguna cohorte independiente el orden GFAP, NfL, p-tau181?") is not None
    assert CU.equivalencia("Una cohorte independiente con seguimiento longitudinal", "Seguimiento longitudinal en una cohorte independiente") is not None
    # Preposiciones flojas y palabras con doble sentido no activan la guarda: la misma pregunta reordenada se funde.
    assert CU.equivalencia("¿Cambia GFAP desde la fase preclínica en la cohorte A4?", "¿Cambia GFAP en la cohorte A4 desde la fase preclínica?") is not None
    assert CU.equivalencia("¿La media de GFAP supera el umbral en amiloide positivos?", "¿La media de GFAP en amiloide positivos supera el umbral?") is not None
    # Con palabra de orden y el mismo orden, la ampliación sigue fundiéndose.
    assert CU.equivalencia("¿Sube GFAP antes que NfL en sangre?", "¿Sube GFAP antes que NfL en sangre en preclínicos?") is not None
    # Simetría y determinismo.
    for a, b in (("¿Sube GFAP antes que NfL?", "¿Sube NfL antes que GFAP?"), ("¿Sube tau antes que NfL?", "¿Sube NfL antes que tau?")):
        assert CU.equivalencia(a, b) == CU.equivalencia(b, a) is None
    a = CU.registrar(e, _cu("¿Sube GFAP antes que NfL en sangre?"))
    b = CU.registrar(e, _cu("¿Sube NfL antes que GFAP en sangre?"))
    assert a is not b and len(e["cuestiones"]) == 2 and a["veces"] == 1


def test_ids_desde_un_set_salen_ordenados_y_deterministas():
    # El orden de iteración de un set de cadenas cambia con la semilla de hash del proceso.
    c = CU.nueva(INV, "x", "killer", "", T0, hipotesis_ids={"hip-b", "hip-zz", "hip-a", "hip-1"}, hecho_ids=frozenset({"he-2", "he-1"}))
    assert c["hipotesisIds"] == ["hip-1", "hip-a", "hip-b", "hip-zz"] and c["hechoIds"] == ["he-1", "he-2"]
    assert CU.nueva(INV, "x", "killer", "", T0, hipotesis_ids=("hip-b", "hip-a"))["hipotesisIds"] == ["hip-b", "hip-a"]  # una tupla conserva su orden


def test_registrar_da_id_a_un_dict_sin_id(e):
    # Un dict armado a mano entraba sin id y buscar, resolver y cerradas_por_hecho no lo encontraban nunca.
    a = CU.registrar(e, {"investigacionId": INV, "texto": "Sin id, construida a mano"})
    assert a is not None and isinstance(a["id"], str) and a["id"].startswith("cu-") and CU.buscar(e, a["id"]) is a
    b = CU.registrar(e, {"investigacionId": INV, "texto": "Otra sin id", "id": "  "})
    assert b["id"].startswith("cu-") and b is not a and len(e["cuestiones"]) == 2
    assert CU.resolver(e, a["id"], "he-1", "ok", T0 + 1) and a["estado"] == "resuelta"
    _, lista = CU.numeradas(e, INV)
    assert CU.cerradas_por_hecho(e, INV, {"id": "he-2"}, [1], lista, T0 + 2) == [b["id"]]


def test_singular_cuando_hay_una_sola_abierta_sin_listar(e):
    CU.registrar(e, _cu("La única cuestión"))
    assert CU.numeradas(e, INV, maximo=0) == ("Hay 1 cuestión abierta, no listada.", [])
    CU.registrar(e, _cu("Otra cuestión distinta sobre otro marcador"))
    assert CU.numeradas(e, INV, maximo=0) == ("Hay 2 cuestiones abiertas, ninguna listada.", [])


def test_creada_en_ausente_se_toma_del_movimiento_de_apertura(e):
    limite = T0 + 1000
    # Sin creadaEn pero con apertura (de None) después del límite: se poda, como un hecho de Rosa.
    e["cuestiones"].append({"id": "cu-a", "investigacionId": INV, "texto": "Abierta después sin creadaEn", "historial": [{"fecha": T0 + 5000, "de": None, "a": "abierta", "quien": "Rosa"}]})
    # Sin creadaEn y cuyo primer movimiento es una resolución (existía antes): no se le inventa fecha, cuenta como la más antigua.
    e["cuestiones"].append({"id": "cu-b", "investigacionId": INV, "texto": "Resuelta después, nacida quién sabe cuándo", "estado": "resuelta", "historial": [{"fecha": T0 + 5000, "de": "abierta", "a": "resuelta", "quien": "Rosa"}]})
    # Apertura con fecha ilegible: 0.
    e["cuestiones"].append({"id": "cu-c", "investigacionId": INV, "texto": "Apertura ilegible", "historial": [{"fecha": "ayer", "de": None, "a": "abierta", "quien": "Rosa"}]})
    assert [c["id"] for c in CU.abiertas(e, INV)] == ["cu-c", "cu-a"]  # 0 antes que T0 + 5000
    assert CU.podar_desde(e, INV, limite) == 1
    ids = [c["id"] for c in e["cuestiones"]]
    assert "cu-a" not in ids and "cu-b" in ids and "cu-c" in ids
    # La resolución posterior de cu-b se deshace (movimiento de Rosa después del límite): vuelve a abierta.
    b = CU.buscar(e, "cu-b")
    assert b["estado"] == "abierta" and b["historial"] == [] and b["resolucion"] is None


def test_ahora_booleano_no_es_el_milisegundo_uno(e):
    c = CU.nueva(INV, "Con ahora booleano", "revisor", "", True)
    assert c["creadaEn"] > T0 and c["historial"][0]["fecha"] == c["creadaEn"]
    a = CU.registrar(e, c)
    assert CU.resolver(e, a["id"], "he-1", "ok", False) and a["resueltaEn"] > T0


def test_un_hecho_descartado_o_una_conjetura_no_resuelven(e):
    a = CU.registrar(e, _cu("¿Qué cohorte replica el orden?"))
    _, lista = CU.numeradas(e, INV)
    descartado = P.nuevo_hecho(INV, "hecho", "t", "BIOCARD lo replica", "descartado", "fuente", [], T0)
    conjetura = P.nuevo_hecho(INV, "hipotesis", "t", "Quizá BIOCARD lo replique", "sabido", "inferencia", [], T0)
    assert CU.cerradas_por_hecho(e, INV, descartado, [1], lista, T0) == [] and a["estado"] == "abierta"
    assert CU.cerradas_por_hecho(e, INV, conjetura, [1], lista, T0) == [] and a["estado"] == "abierta"
    # Un registro antiguo sin tipo cuenta como hecho (valor de hoy) y sí resuelve.
    assert CU.cerradas_por_hecho(e, INV, {"id": "he-viejo", "enunciado": "Lo replica"}, [1], lista, T0) == [a["id"]]


def test_poda_que_vuelve_a_resuelta_restaura_la_resolucion_del_limite(e):
    limite = T0 + 100
    a = CU.registrar(e, _cu("¿Cuál es la edad de inicio?", ahora=T0))
    assert CU.resolver(e, a["id"], "he-1", "Respondida por el hecho: A4", T0 + 50)
    assert a["historial"][-1]["por"] == "he-1"
    # Rosa reabre y vuelve a resolver después del límite con un hecho que la poda borra.
    assert CU.reabrir(e, a["id"], "se retiró he-1", "Rosa", T0 + 200) and CU.resolver(e, a["id"], "he-podado", "Respondida por el hecho: X", T0 + 300)
    assert CU.podar_desde(e, INV, limite) == 0
    assert a["estado"] == "resuelta" and a["resolucion"] == {"por": "he-1", "motivo": "Respondida por el hecho: A4"} and a["resueltaEn"] == T0 + 50
    assert [m["a"] for m in a["historial"]] == ["abierta", "resuelta"] and a["actualizadaEn"] == limite
    # Un movimiento antiguo sin `por` cae en quien resolvió.
    e["cuestiones"].append({"id": "cu-v", "investigacionId": INV, "texto": "Vieja", "estado": "abierta", "creadaEn": T0, "historial": [{"fecha": T0, "de": None, "a": "abierta", "quien": "Rosa"}, {"fecha": T0 + 10, "de": "abierta", "a": "resuelta", "quien": "Dra. Allegri", "motivo": "Lo sé"}, {"fecha": T0 + 500, "de": "resuelta", "a": "abierta", "quien": "Rosa"}]})
    assert CU.podar_desde(e, INV, limite) == 0
    v = CU.buscar(e, "cu-v")
    assert v["estado"] == "resuelta" and v["resolucion"] == {"por": "Dra. Allegri", "motivo": "Lo sé"} and v["resueltaEn"] == T0 + 10


def test_copiar_a_investigacion_sigue_a_los_hechos_al_bifurcar(e):
    A.crear_investigacion(e, {"titulo": "Rama", "objetivo": "O", "condicionParada": "1 iteración"}, T0, "inv-rama")
    hecho = P.nuevo_hecho(INV, "pregunta", "t", "¿Qué cohorte replica el orden?", "abierto", "inferencia", [], T0)
    a = CU.desde_pregunta_hecho(e, hecho, "otra cohorte", T0)
    b = CU.registrar(e, _cu("Resuelta antes de bifurcar", hechos=["he-x", hecho["id"]], hip=["hip-1"]))
    assert CU.resolver(e, b["id"], hecho["id"], "la responde", T0 + 1)
    e["cuestiones"].append({"investigacionId": INV, "texto": "   "})  # entrada rota: no viaja
    mapa = {hecho["id"]: f"{hecho['id']}-inv-rama"}
    assert CU.copiar_a_investigacion(e, INV, "inv-rama", mapa) == 2
    copias = CU._propias(e, "inv-rama")
    ca, cb = copias
    assert ca["id"] == f"{a['id']}-inv-rama" and "-inv-" in ca["id"] and ca["investigacionId"] == "inv-rama"
    assert ca["origen"] == {"tipo": "pregunta_modelo", "id": f"{hecho['id']}-inv-rama"} and ca["hechoIds"] == [f"{hecho['id']}-inv-rama"]
    assert cb["estado"] == "resuelta" and cb["hechoIds"] == ["he-x", f"{hecho['id']}-inv-rama"] and cb["resolucion"]["por"] == f"{hecho['id']}-inv-rama" and cb["hipotesisIds"] == ["hip-1"]
    # El original no cambia y el historial no se comparte.
    assert a["investigacionId"] == INV and a["hechoIds"] == [hecho["id"]] and b["resolucion"]["por"] == hecho["id"]
    assert ca["historial"] == a["historial"] and ca["historial"] is not a["historial"] and ca["historial"][0] is not a["historial"][0]
    # Repetir la copia no duplica; origen igual a destino o vacío no hace nada.
    assert CU.copiar_a_investigacion(e, INV, "inv-rama", mapa) == 0 and len(copias) == 2
    assert CU.copiar_a_investigacion(e, INV, INV, mapa) == 0 and CU.copiar_a_investigacion(e, "", "inv-rama") == 0
    # La rama tiene sus propias abiertas, dedupe aparte, y de_hipotesis ve la original y la copia.
    assert CU.resumen(e, "inv-rama") == {"abiertas": 1, "resueltas": 1, "descartadas": 0}
    assert CU.resumen(e, INV) == {"abiertas": 2, "resueltas": 1, "descartadas": 0}  # la entrada rota sin estado cuenta como abierta en el origen, pero no viajó
    assert [c["id"] for c in CU.de_hipotesis(e, "hip-1")] == [b["id"], cb["id"]]
    assert CU.cerradas_por_hecho(e, "inv-rama", {"id": "he-r"}, [1], CU.numeradas(e, "inv-rama")[1], T0 + 30) == [ca["id"]] and a["estado"] == "abierta"
