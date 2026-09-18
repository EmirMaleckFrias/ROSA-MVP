"""Regla de Emir (18 sep 2026): con la autonomía de gasto en "actuar", una
iteración que pide más de la mitad del presupuesto restante no espera permiso:
deja un aviso (evento «presupuesto») una sola vez y sigue. La plantilla nueva
arranca en "actuar" y los estados antiguos se migran una sola vez."""

from __future__ import annotations

import asyncio

from rosa.bucle import corrida as CO
from rosa.estado import almacen as AL
from rosa.estado import plantilla as P


class _Almacen:
    def __init__(self, estado):
        self.estado = estado

    def mutar(self, fn, nombre="test"):
        return fn(self.estado)


def _estado_con_corrida(autonomia: str):
    e = P.estado_inicial()
    e["autonomia"]["gastar_grande"] = autonomia
    e["investigaciones"].append({"id": "inv-1", "titulo": "t", "objetivo": "o"})
    c = {"id": "cor-1", "investigacionId": "inv-1", "numero": 1, "estado": "en_marcha", "presupuesto": {"limiteLlamadas": 1000, "alertas": [], "avisadas": [], "motivoPausa": ""}, "gasto": {"llamadas": 200}}
    e["corridas"].append(c)
    it = {"id": "it-1", "corridaId": "cor-1", "numero": 2, "presupuesto": {"limite": 700, "usado": 0}}
    e["iteraciones"].append(it)
    return e, c, it


def _supervisor(e):
    sup = CO.Supervisor.__new__(CO.Supervisor)
    sup.almacen = _Almacen(e)
    return sup


def test_con_actuar_no_pide_permiso_y_avisa_una_sola_vez():
    e, c, it = _estado_con_corrida("actuar")
    sup = _supervisor(e)
    assert asyncio.run(sup._permiso_presupuesto(c, it)) is True
    assert asyncio.run(sup._permiso_presupuesto(c, it)) is True
    avisos = [x for x in e["eventos"] if x["tipo"] == "presupuesto"]
    assert len(avisos) == 1
    assert "700 llamadas de las 800 que quedan" in avisos[0]["texto"]
    assert "sigue sin preguntar" in avisos[0]["texto"]
    assert e["solicitudes"] == []
    assert c["estado"] == "en_marcha"


def test_con_actuar_y_gasto_pequeno_no_avisa():
    e, c, it = _estado_con_corrida("actuar")
    it["presupuesto"]["limite"] = 100
    assert asyncio.run(_supervisor(e)._permiso_presupuesto(c, it)) is True
    assert not [x for x in e["eventos"] if x["tipo"] == "presupuesto"]


def test_con_preguntar_sigue_pidiendo_permiso():
    e, c, it = _estado_con_corrida("preguntar")
    assert asyncio.run(_supervisor(e)._permiso_presupuesto(c, it)) is False
    assert len(e["solicitudes"]) == 1 and c["estado"] == "esperando_aprobacion"


def test_plantilla_nueva_arranca_en_actuar():
    e = P.estado_inicial()
    assert e["autonomia"]["gastar_grande"] == "actuar"
    assert e["autonomia"]["descartar_hipotesis"] == "preguntar"


def test_migracion_pasa_preguntar_a_actuar_una_sola_vez():
    e = {"autonomia": {"gastar_grande": "preguntar"}}
    AL._migrar_gasto_grande_automatico(e)
    assert e["autonomia"]["gastar_grande"] == "actuar" and e["_gastoGrandeMigrado"] is True
    e["autonomia"]["gastar_grande"] = "preguntar"  # la persona lo vuelve a poner a mano
    AL._migrar_gasto_grande_automatico(e)
    assert e["autonomia"]["gastar_grande"] == "preguntar"
    AL._migrar_gasto_grande_automatico({"autonomia": None})  # registro raro: no rompe
