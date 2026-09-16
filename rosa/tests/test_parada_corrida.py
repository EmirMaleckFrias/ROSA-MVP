"""La parada propia de una corrida: horas, iteraciones, llamadas o texto
fijados al crearla; se detiene con lo que llegue primero, además de la
condición de la investigación."""
from rosa import parada as PARADA
from rosa.bucle.corrida import _condicion_de_parada as f
from rosa.estado import acciones as A


def test_normalizar_parada_acota_y_descarta_lo_vacio():
    assert PARADA.normalizar_parada({"horas": 1 / 60})["horas"] == 1 / 60
    assert PARADA.normalizar_parada({"horas": 10 / 60})["horas"] * 3600 == 600
    assert PARADA.resumen_parada({"horas": 48}) == "2 días"
    assert PARADA.normalizar_parada(None) is None and PARADA.normalizar_parada({}) is None
    assert PARADA.normalizar_parada({"horas": "", "iteraciones": None, "llamadas": "", "texto": "  "}) is None
    p = PARADA.normalizar_parada({"horas": "2,5", "iteraciones": 6.9, "llamadas": "3", "texto": " hasta que cambie "})
    assert p == {"horas": 2.5, "iteraciones": 6, "llamadas": 10, "texto": "hasta que cambie", "certeza": None, "cuantas": None, "sinCambio": None}
    assert PARADA.normalizar_parada({"horas": -1, "iteraciones": "abc"}) is None
    assert PARADA.normalizar_parada({"horas": 9999})["horas"] == 336
    assert PARADA.normalizar_parada("2 horas") is None


def test_resumen_parada_y_texto_condicion():
    assert PARADA.resumen_parada(None) == ""
    assert PARADA.resumen_parada({"horas": 2}) == "2 horas"
    assert PARADA.resumen_parada({"horas": 0.5, "iteraciones": 6}) == "30 minutos o 6 iteraciones, lo que llegue primero"
    assert PARADA.resumen_parada({"horas": 1, "iteraciones": 3, "llamadas": 500, "texto": "sin cambios"}) == "1 hora, 3 iteraciones, 500 llamadas al modelo o «sin cambios», lo que llegue primero"
    inv = {"condicionParada": "cuando el modelo de mundo deje de cambiar"}
    assert PARADA.texto_condicion(inv, {"parada": None}) == "cuando el modelo de mundo deje de cambiar"
    assert PARADA.texto_condicion(inv, {"parada": {"horas": 2, "iteraciones": None, "llamadas": None, "texto": ""}}).startswith("Esta corrida: como mucho 2 horas. Además sigue valiendo")


def test_la_corrida_se_detiene_con_lo_que_llegue_primero():
    c = {"empezadaEn": 0, "gasto": {"llamadas": 50}, "parada": {"horas": 2, "iteraciones": 6, "llamadas": 800, "texto": ""}}
    # Ni el tiempo, ni las iteraciones, ni las llamadas propias, ni la condición de la investigación.
    assert f("cuando el modelo de mundo deje de cambiar", 3, c, ahora=3_600_000) is None
    assert f("cuando el modelo de mundo deje de cambiar", 3, c, ahora=7_200_000).startswith("Se cumplió el tiempo fijado para esta corrida (2 horas)")
    assert f("cuando el modelo de mundo deje de cambiar", 6, c, ahora=1000) == "Se alcanzaron las 6 iteraciones fijadas para esta corrida"
    assert f("x", 1, dict(c, gasto={"llamadas": 800}), ahora=1000) == "Se alcanzaron las 800 llamadas fijadas para esta corrida"
    # La condición de la investigación sigue valiendo aunque la propia no haya llegado.
    assert f("2 iteraciones", 2, c, ahora=1000).startswith("Se alcanzaron las 2 iteraciones de la condición")
    # Texto propio automatizable.
    c2 = {"empezadaEn": 0, "gasto": {"llamadas": 0}, "parada": {"horas": None, "iteraciones": None, "llamadas": None, "texto": "30 minutos"}}
    assert f("nunca", 1, c2, ahora=29 * 60_000) is None and f("nunca", 1, c2, ahora=31 * 60_000).endswith("(fijada para esta corrida)")
    # Sin parada propia, todo como antes.
    assert f("2 horas", 1, {"empezadaEn": 0, "gasto": {"llamadas": 0}}, ahora=7_200_000)


def test_iniciar_corrida_guarda_la_parada_y_alinea_el_presupuesto():
    e = {"investigaciones": [{"id": "inv", "titulo": "t", "estado": "activa", "condicionParada": "cuando cambie"}], "corridas": [], "eventos": []}
    cid = A.iniciar_corrida(e, "inv", 1000, parada={"horas": "1.5", "llamadas": 400, "texto": ""})
    c = e["corridas"][0]
    assert c["id"] == cid and c["parada"] == {"horas": 1.5, "iteraciones": None, "llamadas": 400, "texto": "", "certeza": None, "cuantas": None, "sinCambio": None}
    assert c["presupuesto"]["limiteLlamadas"] == 400
    assert e["eventos"][-1]["texto"].endswith("Se detiene con 1.5 horas o 400 llamadas al modelo, lo que llegue primero")
    # Sin parada: como antes, y no se crea otra mientras la anterior viva.
    assert A.iniciar_corrida(e, "inv", 2000) is False
    c["estado"] = "terminada"
    cid2 = A.iniciar_corrida(e, "inv", 3000)
    c2 = next(x for x in e["corridas"] if x["id"] == cid2)
    assert c2["parada"] is None and c2["numero"] == 2 and "Se detiene" not in e["eventos"][-1]["texto"]
