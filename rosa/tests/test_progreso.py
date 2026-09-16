"""La serie de progreso por iteración, la métrica única de la corrida y la
parada por peldaños o por estancamiento."""
from rosa import parada as PARADA
from rosa import progreso as PROG
from rosa.bucle.corrida import _condicion_de_parada as f


def _h(id_, certeza, estado="propuesta", inv="inv"):
    return {"id": id_, "investigacionId": inv, "estado": estado, "conclusion": {"certeza": certeza, "direccion": "apoya", "techo": {"nivel": certeza}}}


def test_instantanea_cuenta_peldanos_subidos_bajados_y_fallidos():
    c = {"id": "cor", "investigacionId": "inv", "gasto": {"usd": 2.5, "llamadas": 40}, "arnes": {"commit": "abc"}, "progreso": []}
    it1 = {"numero": 1, "empezadaEn": 1000, "plan": [{"estado": "hecho"}, {"estado": "fallido"}], "pistas": [{"estado": "hecha"}, {"estado": "fallida"}]}
    e = {"hipotesis": [_h("h1", "muy_baja"), _h("h2", "baja"), _h("h3", "alta", estado="descartada"), _h("h4", "baja", inv="otra")],
         "decisiones": [{"investigacionId": "inv", "etapa": "killer_1", "decision": "descartar_en_contexto", "fecha": 1500}, {"investigacionId": "inv", "etapa": "killer_1", "decision": "avanzar", "fecha": 1600}, {"investigacionId": "inv", "etapa": "killer_1", "decision": "suspender", "fecha": 500}]}
    p1 = PROG.instantanea(e, c, it1, hechos_nuevos=3, hipotesis_nuevas=1, afirmaciones_bloqueadas=2, ahora=2000)
    assert [x["hipotesisId"] for x in p1["certezas"]] == ["h1", "h2"]  # descartadas y otras investigaciones fuera
    assert p1["peldanosTotales"] == 1 and p1["peldanosSubidos"] == 1 and p1["peldanosBajados"] == 0  # h2 nace en baja
    assert p1["fallidos"] == {"pasos": 1, "pistas": 1, "killer": 1, "afirmacionesBloqueadas": 2}
    assert p1["hechosNuevos"] == 3 and p1["usdAcumulado"] == 2.5 and p1["arnes"] == "abc"
    c["progreso"].append(p1)
    # Segunda iteración: h1 sube a baja, h2 baja a muy baja, nace h5 en moderada.
    e["hipotesis"] = [_h("h1", "baja"), _h("h2", "muy_baja"), _h("h5", "moderada")]
    it2 = {"numero": 2, "empezadaEn": 2000, "plan": [], "pistas": []}
    p2 = PROG.instantanea(e, c, it2, 0, 1, 0, 3000)
    assert p2["peldanosSubidos"] == 3 and p2["peldanosBajados"] == 1 and p2["peldanosTotales"] == 3
    c["progreso"].append(p2)
    m = PROG.metrica_de_corrida({"corridas": [c], "investigaciones": [], "hipotesis": e["hipotesis"], "iteraciones": []}, "cor")
    assert m["peldanosSubidos"] == 4 and m["peldanosBajados"] == 1 and m["peldanosNetos"] == 3 and m["peldanosPorDolar"] == 1.2
    assert m["hipotesisEnBajaOMas"] == 2 and m["hechosNuevos"] == 3 and m["hipotesisNuevas"] == 2 and m["fallidos"]["killer"] == 1
    assert "subió 3 peldaños netos de certeza en 2 iteraciones; 1.2 por dólar; 2 hipótesis en certeza baja o más" == PROG.resumen_metrica(m)
    assert PROG.iteraciones_sin_avance(c) == 0 and PROG.hipotesis_en_nivel(c, "baja") == 2 and PROG.hipotesis_en_nivel(c, "moderada") == 1


def test_parada_por_certeza_y_por_estancamiento():
    p = PARADA.normalizar_parada({"certeza": "baja", "cuantas": 2, "sinCambio": "3"})
    assert p["certeza"] == "baja" and p["cuantas"] == 2 and p["sinCambio"] == 3
    assert PARADA.normalizar_parada({"certeza": "muy_baja"}) is None  # muy baja no es objetivo
    assert PARADA.normalizar_parada({"cuantas": 3}) is None  # cuantas sin certeza no vale
    assert PARADA.normalizar_parada({"certeza": "alta"})["cuantas"] == 1
    assert PARADA.resumen_parada(p) == "2 hipótesis en certeza baja o 3 iteraciones sin avance, lo que llegue primero"
    sin_avance = {"iteracion": 1, "peldanosSubidos": 0, "hechosNuevos": 0, "certezas": [{"hipotesisId": "h1", "peldano": 0}]}
    c = {"empezadaEn": 0, "gasto": {"llamadas": 10}, "parada": p, "progreso": [dict(sin_avance, iteracion=1), dict(sin_avance, iteracion=2)]}
    assert f("nunca", 2, c, ahora=1000) is None  # dos sin avance, límite 3; una sola hipótesis en muy baja
    c["progreso"].append(dict(sin_avance, iteracion=3))
    assert f("nunca", 3, c, ahora=1000) == "3 iteraciones seguidas sin subir ninguna hipótesis de certeza ni añadir hechos, límite fijado para esta corrida"
    c2 = {"empezadaEn": 0, "gasto": {"llamadas": 10}, "parada": p, "progreso": [{"iteracion": 1, "peldanosSubidos": 2, "hechosNuevos": 1, "certezas": [{"hipotesisId": "h1", "peldano": 1}, {"hipotesisId": "h2", "peldano": 2}]}]}
    assert f("nunca", 1, c2, ahora=1000) == "2 hipótesis alcanzaron la certeza baja fijada para esta corrida"
    # Sin progreso todavía, ninguna de las dos se dispara.
    assert f("nunca", 1, {"empezadaEn": 0, "gasto": {"llamadas": 0}, "parada": p, "progreso": []}, ahora=1000) is None
