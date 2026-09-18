"""Adversario del constructor "corrida" (vigilante de modelos, 18 de septiembre
de 2026; TRASPASO.md 7.4 y la hora perdida de la corrida 13).

Cada test afirma el comportamiento CORRECTO que el contrato compartido y la
regla de Emir exigen; el que falla hoy señala el hueco que hay que reparar.
Todo con dobles: ningún modelo, ninguna red, ningún dormir de verdad salvo
0,3-0,5 s a escala en el test de los tics.

Lo que se ataca:

- (c) Una petición lenta dentro de `_atender_peticiones` (el vigilante
  reintentando al juez o al cerebro desde una revisión pedida, un "en llano"
  o una meta-campaña) sigue congelando los tics: `correr()` la espera.
- (h, c) Mientras la corrida está en `esperando_modelo`, `_completar_en_llano`
  sigue pidiéndole rellenos de fondo al mismo modelo caído.
- La orden de la persona manda: una pausa a mano hecha mientras el paso corría
  no puede convertirse en `esperando_modelo` y deshacerse sola al volver el
  modelo.
- El cierre de la iteración traga `ModeloSinRespuesta` en sus `except
  Exception` y cierra la iteración degradada en vez de esperar al modelo.
- `detener_corrida` deja `esperandoModelo` relleno en una corrida detenida.
- Dos corridas que esperan al mismo modelo cuentan dos caídas si un sondeo
  responde y el otro no, dentro del mismo minuto.
- (b) Un sondeo que se cuelga retiene la espera para siempre: el tic no lo
  acota ni lo sustituye.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from rosa.bucle import corrida as CO
from rosa.bucle import pasos as PASOS
from rosa.bucle.pasos import Ctx
from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.tests import test_vigilante_corrida as VC
from rosa.tests.test_integracion_corrida import _preparar, _supervisor

ASTRA = VC.ASTRA
OPUS = VC.OPUS
MIN = VC.MIN
MODELO_DEL_ROL = {"cerebro": ASTRA, "juez": OPUS, "replica": OPUS, "volumen": "anthropic/claude-sonnet-5"}


def _espera(rol: str = "cerebro", modelo: str = ASTRA, proximo: int = 0, intentos: int = 4) -> dict[str, Any]:
    return {"rol": rol, "modelo": modelo, "desde": 1000, "ultimoSondeo": None, "proximoSondeo": proximo, "pasoId": None, "intentos": intentos}


def _poner_esperando(al, cid: str, espera: dict[str, Any] | None = None) -> None:
    al.mutar(lambda e: next(x for x in e["corridas"] if x["id"] == cid).update({"estado": "esperando_modelo", "esperandoModelo": espera or _espera()}) or True, "estado")


# ---------------------------------------------------------------------------
# (c) Los tics siguen congelándose desde `_atender_peticiones`
# ---------------------------------------------------------------------------


def test_una_peticion_lenta_dentro_del_bucle_congela_los_tics(monkeypatch):
    """`correr()` espera `_atender_peticiones` dentro del bucle del tic. Con el
    vigilante en `Ctx.llamar`, una revisión pedida al juez caído dura hasta
    4 x 300 s + 105 s (unos 22 minutos) y, mientras, no hay tics: ni sondeos
    para las corridas en `esperando_modelo`, ni relanzamientos, ni reloj. Aquí
    la petición dura 0,5 s a escala de un tic de 0,01 s: en 0,3 s tendría que
    haber decenas de tics, como los hay con la vigilancia lenta."""
    al, ids = _preparar()
    sup, ctx, _ = _supervisor(al, ids, {}, monkeypatch)
    from rosa import indice_semantico, vigilancia

    monkeypatch.setattr(CO, "INTERVALO_TIC_S", 0.01)

    async def vigilar(almacen, ahora):
        return {"comprobadas": 0, "errores": 0, "conNovedades": 0, "nuevas": 0, "costeUsd": 0}

    async def indexar(almacen):
        return 0

    monkeypatch.setattr(vigilancia, "vigilar", vigilar)
    monkeypatch.setattr(indice_semantico, "indexar_estado", indexar)

    async def peticion_lenta():
        await asyncio.sleep(0.5)  # el vigilante reintentando al juez desde una revisión pedida, a escala

    monkeypatch.setattr(sup, "_atender_peticiones", peticion_lenta)

    async def dormida(cid):
        await asyncio.sleep(3600)

    monkeypatch.setattr(sup, "correr_corrida", dormida)
    tics: list[float] = []
    original = sup._tick

    def tick(ahora=None):
        tics.append(asyncio.get_running_loop().time())
        original(ahora)

    monkeypatch.setattr(sup, "_tick", tick)

    async def cuerpo():
        tarea = asyncio.create_task(sup.correr())
        await asyncio.sleep(0.3)
        n = len(tics)
        sup.parar()
        await asyncio.wait_for(tarea, timeout=5)
        return n

    n = asyncio.run(cuerpo())
    assert n >= 10, f"solo {n} tic(s) en 0,3 s: la petición lenta congela el bucle igual que lo hacía la vigilancia"


def test_mientras_la_corrida_espera_a_astra_no_se_le_piden_rellenos_de_fondo(monkeypatch):
    """`_completar_en_llano_paso` rellena una cosa por tic (versión en llano,
    conclusión, experimento, tarjeta, misión) y su puerta `_puede_gastar` deja
    fuera las corridas detenidas, pausadas y sin presupuesto, pero no la que
    está en `esperando_modelo`. Resultado: mientras ROSA2018 espera a que Astra
    vuelva, le sigue pidiendo rellenos a Astra desde el bucle del tic (cada uno,
    otros 4 intentos de 240 s con el tic congelado) y la incidencia
    `modelo_sin_respuesta` se reabre desde una tarea que no es la corrida."""
    al, ids = _preparar()
    sup, ctx, _ = _supervisor(al, ids, {}, monkeypatch)
    _poner_esperando(al, ids["cor"])
    llamadas: list[str] = []

    def anotar(nombre):
        async def fn(*a, **k):
            llamadas.append(nombre)

        return fn

    monkeypatch.setattr(sup, "_hipotesis_en_llano", anotar("en_llano"))
    monkeypatch.setattr(sup, "_concluir_hipotesis", anotar("concluir"))
    monkeypatch.setattr(sup, "_proponer_experimento", anotar("experimento"))
    monkeypatch.setattr(sup, "_proponer_mision", anotar("mision"))
    monkeypatch.setattr(PASOS, "_completar_tarjeta", anotar("tarjeta"))
    asyncio.run(sup._completar_en_llano_paso())
    assert llamadas == [], f"con la corrida en esperando_modelo se pidió al modelo caído: {llamadas}"


# ---------------------------------------------------------------------------
# La orden de la persona manda sobre la espera automática
# ---------------------------------------------------------------------------


def test_una_pausa_a_mano_durante_el_paso_no_se_pierde_cuando_el_modelo_cae(monkeypatch):
    """La persona pulsa Pausar mientras el paso corre (la pausa se aplica al
    terminar el paso, como siempre). El paso termina con `ModeloSinRespuesta`:
    `_entrar_en_esperando_modelo` solo respeta detenida y terminada, así que
    pisa la pausa con `esperando_modelo`; el primer sondeo que responde la pone
    en marcha y relanza el paso sin que nadie la reanudara. El vigilante
    (`fijar_espera_modelo`) sí respeta la pausa: aquí debe pasar lo mismo."""
    al, ids = _preparar()
    sup, ctx, _ = _supervisor(al, ids, {}, monkeypatch)
    paso = VC._con_paso(al, ids["it"])

    class EjecutorConPausaDeLaPersona(VC.EjecutorFalso):
        async def __call__(self, ctx, paso):
            if self.llamadas == 0:
                # La persona pulsa Pausar mientras el primer intento del paso corre.
                assert al.aplicar("pausarCorrida", {"corrida_id": ids["cor"]}) is True
            return await super().__call__(ctx, paso)

    ejecutor = EjecutorConPausaDeLaPersona(fallos=1)
    monkeypatch.setattr(PASOS, "EJECUTORES", {"literatura": ejecutor})
    VC._detener_al_cerrar(sup, al, monkeypatch)
    VC._sondeo_que(sup, monkeypatch, True)

    async def cuerpo():
        try:
            await asyncio.wait_for(sup.correr_corrida(ids["cor"]), timeout=5)
            c = VC._corrida(al, ids["cor"])
            assert c["estado"] == "pausada", f"la pausa de la persona quedó pisada: la corrida está en {c['estado']!r}"
            # Y aunque el modelo vuelva, una corrida pausada no retoma el paso sola: el
            # tic puede darle su tarea (que duerme en la pausa), pero el ejecutor no se
            # vuelve a llamar hasta que la persona reanude.
            sup._tick(ahora=P.ahora_ms() + 2 * CO.INTERVALO_SONDEO_S * 1000)
            for t in list(sup._sondeos.values()):
                await t
            await asyncio.sleep(0.05)
            c = VC._corrida(al, ids["cor"])
            assert c["estado"] == "pausada" and ejecutor.llamadas == 1, f"la corrida pausada retomó sola: estado {c['estado']!r}, {ejecutor.llamadas} llamadas al ejecutor"
        finally:
            for t in list(sup.tareas.values()):
                t.cancel()
            await asyncio.gather(*sup.tareas.values(), return_exceptions=True)

    asyncio.run(cuerpo())


# ---------------------------------------------------------------------------
# El cierre de la iteración traga la excepción del vigilante
# ---------------------------------------------------------------------------


def test_el_cierre_con_el_cerebro_y_el_juez_caidos_espera_en_vez_de_cerrar_degradado(monkeypatch):
    """`correr_corrida` captura `ModeloSinRespuesta` alrededor de
    `_cerrar_con_presupuesto`, pero dentro de `_cerrar_iteracion` cada llamada
    al modelo va en un `except Exception` con respaldo (resumen por regla,
    "el juez no respondió: solo comprobaciones por regla", conclusiones
    impresas y perdidas): la excepción nunca llega arriba. Con Astra y Opus
    caídos, ROSA2018 espera unos 20 minutos por llamada y después cierra la
    iteración con un resumen por regla y sin revisor, en vez de esperar a que
    vuelvan (regla de Emir: espera el tiempo que haga falta, no degrada)."""
    al, ids = _preparar()
    sup, ctx, _ = _supervisor(al, ids, {}, monkeypatch)

    async def llamar_caido(self, rol, programa, **kw):
        raise CO.ModeloSinRespuesta(rol, MODELO_DEL_ROL.get(rol, ASTRA), 4, P.ahora_ms() - 20 * MIN)

    monkeypatch.setattr(Ctx, "llamar", llamar_caido)
    c = VC._corrida(al, ids["cor"])
    it = VC._it(al, ids["it"])
    with pytest.raises(CO.ModeloSinRespuesta):
        asyncio.run(sup._cerrar_iteracion(c, it))
    assert VC._it(al, ids["it"])["terminadaEn"] is None, "la iteración se cerró sin el modelo"


# ---------------------------------------------------------------------------
# Reducers y funciones del estado
# ---------------------------------------------------------------------------


def test_detener_una_corrida_que_espera_a_un_modelo_borra_el_registro_de_espera():
    """Una corrida detenida ya no espera a nadie: `esperandoModelo` tiene que
    quedar en None, o la franja de modelos de la interfaz seguirá diciendo
    "esperando a GPT-6 Astra" sobre una corrida parada."""
    e = {"corridas": [{"id": "c1", "investigacionId": "inv", "numero": 1, "estado": "esperando_modelo", "esperandoModelo": _espera()}], "eventos": [], "investigaciones": []}
    assert A.detener_corrida(e, "c1", "Basta por hoy", 5000) is True
    c = e["corridas"][0]
    assert c["estado"] == "detenida" and c["esperandoModelo"] is None


def test_dos_corridas_con_el_mismo_modelo_no_cuentan_dos_caidas_si_solo_un_sondeo_responde():
    """Dos corridas esperan a Astra; en el mismo tic se lanzan dos sondeos. Uno
    responde (la corrida A vuelve y la salud del cerebro pasa a ok) y el otro
    no (la corrida B sigue esperando). `_sondeo_fallido` ve la salud en ok y
    cuenta una caída nueva: la misma caída se cuenta dos veces por un sondeo
    de un segundo de diferencia. La salud del rol debería mirar si alguna
    corrida sigue esperando a ese modelo antes de darlo por recuperado, o no
    contar caída nueva mientras otra corrida siga esperando."""
    e = {
        "corridas": [
            {"id": "a", "investigacionId": "inv", "numero": 1, "estado": "esperando_modelo", "esperandoModelo": _espera()},
            {"id": "b", "investigacionId": "inv", "numero": 2, "estado": "esperando_modelo", "esperandoModelo": _espera()},
        ],
        "eventos": [],
        "incidencias": [],
        "saludModelos": {"cerebro": {"modelo": ASTRA, "estado": "sin_respuesta", "desde": 1000, "intentos": 4, "proximoIntentoEn": 0, "ultimaRespuestaEn": None, "ultimaLatenciaMs": None, "caidas": 1, "recuperadoEn": None}},
    }
    assert CO._modelo_recuperado(e, "a", 10_000) is True
    assert CO._sondeo_fallido(e, "b", 10_001) is True
    assert e["saludModelos"]["cerebro"]["caidas"] == 1, "la misma caída se contó dos veces"


# ---------------------------------------------------------------------------
# (b) Un sondeo que se cuelga
# ---------------------------------------------------------------------------


def test_un_sondeo_que_se_cuelga_no_retiene_la_espera_para_siempre(monkeypatch):
    """`_sondear_si_toca` no lanza otro sondeo mientras el anterior siga en
    vuelo, y `_sondear_modelo` espera `self._sondear(lm)` sin tope propio. Si
    el sondeo se cuelga (un `gateway.sondear` sustituido, una conexión que no
    cierra), la corrida queda en `esperando_modelo` para siempre sin que nada
    lo diga: ni intentos que suban ni sondeo nuevo. Diez minutos después por
    el reloj del tic, el supervisor tendría que haber cortado ese sondeo y
    contado el intento o lanzado otro."""
    al, ids, sup, paso, ejecutor = VC._preparar_esperando(monkeypatch, fallos=99)

    async def cuerpo():
        puerta = asyncio.Event()

        async def colgado(lm):
            await puerta.wait()
            return False

        monkeypatch.setattr(sup, "_sondear", colgado)
        t0 = VC._corrida(al, ids["cor"])["esperandoModelo"]["proximoSondeo"]
        sup._tick(ahora=t0)
        s1 = sup._sondeos[ids["cor"]]
        await asyncio.sleep(0)
        sup._tick(ahora=t0 + 10 * MIN)
        await asyncio.sleep(0)
        s2 = sup._sondeos[ids["cor"]]
        esp = VC._corrida(al, ids["cor"])["esperandoModelo"]
        try:
            assert s2 is not s1 or s1.done() or esp["intentos"] > 4, "un sondeo colgado retiene la espera para siempre"
        finally:
            puerta.set()
            for t in {s1, s2}:
                t.cancel()
            await asyncio.gather(s1, s2, return_exceptions=True)

    asyncio.run(cuerpo())
