"""Adversario del vigilante de modelos (rosa/vigilante_modelos.py y `Ctx.llamar`).

Cada test intenta romper el bloque del 18 de septiembre de 2026 (regla de Emir,
TRASPASO.md 7.4: el cerebro es GPT-6 Astra y solo Astra, el juez Opus 5 y solo
Opus; cuando no responden ROSA2018 espera y reintenta con el mismo modelo). Los
tests marcados HUECO en su docstring FALLAN con el código de hoy y documentan lo
que falta; los demás son intentos de rotura que el vigilante aguantó y quedan
como guardia. Ningún test sale a la red ni espera: dobles, dormir anulado y
sondeo falso.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import dspy
import httpx
import pytest

from rosa import gateway as GW
from rosa import vigilante_modelos as VIG
from rosa.bucle import corrida as CO
from rosa.bucle import pasos as PASOS
from rosa.bucle.pasos import Ctx
from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen

ASTRA = "openai/openai/gpt-6-astra"  # `lm.model` tal como lo construye gateway.lm
OPUS = "openai/anthropic/claude-opus-5"
SONNET = "openai/anthropic/claude-sonnet-5"


# ---------------------------------------------------------------------------
# Dobles (los mismos que usa test_vigilante_llamadas.py, reducidos a lo que hace falta)
# ---------------------------------------------------------------------------


class LMFalso:
    """Un dspy.LM de mentira: `model`, `kwargs` y `copy(rollout_id=...)`."""

    def __init__(self, model: str, rollout_id: int | None = None) -> None:
        self.model = model
        self.kwargs: dict[str, Any] = {} if rollout_id is None else {"rollout_id": rollout_id}

    def copy(self, **kw: Any) -> "LMFalso":
        return LMFalso(self.model, kw.get("rollout_id"))


class VolumenProhibido(LMFalso):
    """Sonnet: si alguien lo copia o lo pone en contexto, el test falla."""

    def __init__(self) -> None:
        super().__init__(SONNET)

    def copy(self, **kw: Any) -> "LMFalso":
        pytest.fail("se intentó usar el modelo de volumen (Sonnet) para otro rol")


class ProgramaFalso:
    """`acall` sigue un plan: una excepción a lanzar, la cadena "duerme" (duerme
    `segundos` reales, más que el umbral del test) o un valor a devolver.
    Registra qué modelo y qué rollout_id vio en cada llamada."""

    def __init__(self, *plan: Any, segundos: float = 0.3) -> None:
        self.plan = list(plan)
        self.segundos = segundos
        self.vistos: list[tuple[str | None, int | None]] = []

    async def acall(self, **kw: Any) -> Any:
        lm = dspy.settings.lm
        modelo = getattr(lm, "model", None)
        if modelo == SONNET:
            pytest.fail("el programa se ejecutó con Sonnet en contexto")
        self.vistos.append((modelo, (getattr(lm, "kwargs", None) or {}).get("rollout_id")))
        paso = self.plan.pop(0) if self.plan else "ok"
        if isinstance(paso, BaseException):
            raise paso
        if paso == "duerme":
            await asyncio.sleep(self.segundos)
            return "tarde"
        return paso


class Registro:
    """Ganchos que anotan lo que el vigilante quiso hacer, sin estado."""

    def __init__(self, sondeos: list[bool] | None = None, ahora: int = 1_700_000_000_000) -> None:
        self.salud: list[tuple[str, str, dict[str, Any]]] = []
        self.incidencias: list[tuple[str, dict[str, Any]]] = []
        self.eventos: list[tuple[str, str]] = []
        self.dormidas: list[float] = []
        self.sondeos = list(sondeos or [])
        self.sondeos_hechos = 0
        self.t = ahora

    def ganchos(self) -> VIG.Ganchos:
        async def dormir(s: float) -> None:
            self.dormidas.append(s)
            self.t += int(s * 1000)

        async def sondear(lm: Any) -> bool:
            self.sondeos_hechos += 1
            return self.sondeos.pop(0) if self.sondeos else False

        def ahora() -> int:
            self.t += 1
            return self.t

        return VIG.Ganchos(
            dormir=dormir,
            sondear=sondear,
            incidencia=lambda a, d: self.incidencias.append((a, d)),
            evento=lambda t, x: self.eventos.append((t, x)),
            salud=lambda r, m, c: self.salud.append((r, m, c)),
            ahora=ahora,
        )


def _ejecutor(programa: ProgramaFalso):
    async def ejecutar(modelo: Any) -> Any:
        with dspy.context(lm=modelo):
            return await programa.acall()

    return ejecutar


def _umbral_corto(monkeypatch: pytest.MonkeyPatch, segundos: float = 0.02) -> None:
    for rol in ("cerebro", "juez", "volumen", "replica"):
        monkeypatch.setitem(VIG.TIEMPO_AVISO_S, rol, segundos)


def _ctx(inv: str = "inv", con_iteracion: bool = True) -> tuple[Almacen, Ctx]:
    al = Almacen(Path(tempfile.mkdtemp()) / "t.db")
    al.aplicar("crearInvestigacion", {"datos": {"titulo": inv, "objetivo": "Astrocitos en el Alzheimer", "condicionParada": "1 iteración"}, "id_": inv})
    cid = al.aplicar("iniciarCorrida", {"investigacion_id": inv})
    it_id = f"it-{inv}"

    def preparar(e: dict[str, Any]) -> bool:
        c = next(x for x in e["corridas"] if x["id"] == cid)
        c["estado"] = "en_marcha"
        if con_iteracion:
            e["iteraciones"].append({"id": it_id, "corridaId": cid, "numero": 1, "plan": [{"id": "paso-1", "estado": "en_curso"}], "pistas": [], "planAprobado": True, "terminadaEn": None, "presupuesto": {"limite": None, "usado": 0}})
        return True

    al.mutar(preparar, "test")
    modelos = SimpleNamespace(cerebro=LMFalso(ASTRA), juez=LMFalso(OPUS), volumen=VolumenProhibido(), replica=LMFalso(OPUS))
    programas = SimpleNamespace(juzgar=None)
    return al, Ctx(al, programas, modelos, cid, inv, it_id if con_iteracion else "", 1)


def _sin_red_ni_esperas(monkeypatch: pytest.MonkeyPatch, sondeos: list[bool] | None = None, dormir_real_s: float = 0.0) -> dict[str, Any]:
    """Los ganchos reales de la corrida, pero sin dormir ni salir a la red.
    `dormir_real_s` > 0 duerme ese poco de verdad (para cruzar tareas o para
    poder cancelar a mitad de la espera)."""
    original = VIG.ganchos_de_contexto
    marcas: dict[str, Any] = {"dormidas": [], "sondeos": 0}
    respuestas = list(sondeos or [])

    def parche(ctx: Any) -> VIG.Ganchos:
        g = original(ctx)

        async def dormir(s: float) -> None:
            marcas["dormidas"].append(s)
            if dormir_real_s > 0:
                await asyncio.sleep(dormir_real_s)

        async def sondear(lm: Any) -> bool:
            marcas["sondeos"] += 1
            return respuestas.pop(0) if respuestas else False

        g.dormir = dormir
        g.sondear = sondear
        return g

    monkeypatch.setattr(VIG, "ganchos_de_contexto", parche)
    return marcas


def _corrida(al: Almacen, cid: str) -> dict[str, Any]:
    return next(c for c in al.estado["corridas"] if c["id"] == cid)


def _incidencias(al: Almacen, cid: str, estado: str | None = None) -> list[dict[str, Any]]:
    return [i for i in al.estado["incidencias"] if i["corridaId"] == cid and (estado is None or i["estado"] == estado)]


def _eventos_modelo(al: Almacen) -> list[str]:
    return [ev["tipo"] for ev in al.estado["eventos"] if str(ev["tipo"]).startswith("modelo_")]


# ---------------------------------------------------------------------------
# (a) y (b): el ejecutor se traga la excepción del vigilante y sigue con el siguiente
# ---------------------------------------------------------------------------


def _con_fuente_y_afirmaciones(al: Almacen, ctx: Ctx, n: int) -> list[dict[str, Any]]:
    """Una fuente con un fragmento y `n` afirmaciones cuya cita resuelve a él sin
    cifras ni identificadores: el verificador determinista las manda al juez."""
    texto = "Los astrocitos reactivos aumentan GFAP en plasma en la fase preclínica del Alzheimer."

    def fn(e: dict[str, Any]) -> bool:
        c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
        c["_fuentes"] = {"f1": {"id": "f1", "referencia": "Smith 2026", "fragmentos": [{"localizador": "pág. 3", "texto": texto, "encabezado": "Resultados"}]}}
        return True

    al.mutar(fn, "test")
    return [{"id": f"a{i}", "texto": "Los astrocitos reactivos aumentan GFAP en plasma en la fase preclínica.", "cita": "[Smith 2026, pág. 3]", "fragmento": None, "fuenteId": "f1", "localizador": "pág. 3", "veredicto": "sin_verificar", "motivo": ""} for i in range(n)]


def test_verificar_afirmaciones_no_se_traga_modelo_sin_respuesta(monkeypatch):
    """HUECO (alto). Los ejecutores de rosa/bucle/pasos.py capturan `except
    Exception` por elemento tras `except PresupuestoAgotado: raise` (juzgar en
    verificar_afirmaciones 1999, relevancia 1320 y 1465, extraer 1867, tarjeta
    2342, sesgo 2858, supuestos 3411, novedad 4120, y el Killer 3081 que lo manda
    a `_registrar_juez_sin_respuesta`). `ModeloSinRespuesta` es una RuntimeError:
    se traga, la afirmación queda "sin_verificar: El juez no dictaminó" y se pasa
    a la siguiente, que vuelve a hacer 4 intentos (4 x 300 s + 105 s = 22 min con
    los tiempos reales). El supervisor nunca recibe la excepción: la corrida
    queda en `esperando_modelo` con la tarea viva, y el tic no la sondea ni la
    relanza mientras la tarea vive. Con 100 afirmaciones y Opus caído: 25 tandas
    de 4 en paralelo, unas 9 horas de "sin_verificar" en vez de esperar. En el
    Killer, además, cada espera cuenta como "intento N de 3" y a la tercera la
    hipótesis queda suspendida "hasta que una persona pida la revisión": lo
    contrario de "espera el tiempo que haga falta"."""
    _sin_red_ni_esperas(monkeypatch)
    al, ctx = _ctx()
    juez = ProgramaFalso(*[httpx.ReadTimeout("el gateway no contesta")] * 60)
    ctx.programas.juzgar = juez
    afirmaciones = _con_fuente_y_afirmaciones(al, ctx, 6)  # más que el semáforo de 4
    try:
        recuento = asyncio.run(PASOS.verificar_afirmaciones(ctx, afirmaciones, None, "GFAP en el Alzheimer"))
    except VIG.ModeloSinRespuesta:
        return  # correcto: la excepción llega al supervisor, que pone la corrida a esperar y retoma el paso
    c = _corrida(al, ctx.corrida_id)
    pytest.fail(
        f"verificar_afirmaciones se tragó ModeloSinRespuesta: devolvió {recuento}, el juez recibió {len(juez.vistos)} intentos "
        f"({len(afirmaciones)} afirmaciones x {VIG.MAX_INTENTOS}), la corrida quedó en '{c['estado']}' con esperandoModelo={c.get('esperandoModelo')} "
        f"y el paso siguió como si nada; motivo de la primera: {afirmaciones[0]['motivo']!r}"
    )


# ---------------------------------------------------------------------------
# (g) la incidencia y la espera que no se cierran cuando el modelo demuestra que vive
# ---------------------------------------------------------------------------


def test_un_exito_del_mismo_modelo_saca_a_la_corrida_de_esperando_modelo_y_resuelve_la_incidencia(monkeypatch):
    """HUECO (medio). Tras un `ModeloSinRespuesta` que el ejecutor se tragó (test
    anterior), o tras un reinicio con la corrida en `esperando_modelo`, la
    siguiente llamada al mismo rol responde a la primera. `llamar_vigilado` solo
    limpia (`quitar_espera_modelo`, `resolver`) cuando hubo fallos EN ESA llamada:
    la salud pasa a ok con `recuperadoEn`, pero la corrida sigue en
    `esperando_modelo` con `esperandoModelo` de 4 intentos, la incidencia "Claude
    Opus 5 no responde" sigue pendiente (la franja la enseña "resolviéndose solo")
    y no hay evento `modelo_recuperado`, mientras la corrida sigue trabajando. La
    tarea muere limpia al siguiente paso, el supervisor sondea a los 60 s y la
    relanza con un "volvió tras 4 intentos" que no describe lo que pasó."""
    _sin_red_ni_esperas(monkeypatch)
    al, ctx = _ctx()
    with pytest.raises(VIG.ModeloSinRespuesta):
        asyncio.run(ctx.llamar("juez", ProgramaFalso(*[TimeoutError()] * 8), x=1))
    assert _corrida(al, ctx.corrida_id)["estado"] == "esperando_modelo", "precondición: la espera agotada dejó la corrida esperando"
    assert asyncio.run(ctx.llamar("juez", ProgramaFalso("ok"), x=2)) == "ok"
    assert al.estado["saludModelos"]["juez"]["estado"] == "ok", "la salud sí se entera de que el juez volvió"
    c = _corrida(al, ctx.corrida_id)
    assert c["estado"] == "en_marcha" and c["esperandoModelo"] is None, f"el juez respondió pero la corrida sigue en {c['estado']} con esperandoModelo={c['esperandoModelo']}"
    assert _incidencias(al, ctx.corrida_id, "pendiente") == [], "la incidencia 'no responde' sigue pendiente aunque el modelo respondió"
    assert _eventos_modelo(al) == ["modelo_sin_respuesta", "modelo_recuperado"]


# ---------------------------------------------------------------------------
# (h) un modelo vivo pero lento se declara caído: bucle con coste
# ---------------------------------------------------------------------------


def test_un_modelo_vivo_pero_lento_no_se_declara_caido(monkeypatch):
    """HUECO (medio). El sondeo responde en cada espera (el modelo está vivo), pero
    la petición tarda más que TIEMPO_AVISO_S (medido: cerebro máximo 327 s, 2 de
    258 llamadas por encima de 240 s). El vigilante la corta, la cuenta como caída
    (`caidas` +1, evento "no responde", incidencia) y, al cuarto corte, lanza
    `ModeloSinRespuesta`: la corrida pasa a `esperando_modelo`, el supervisor
    sondea a los 60 s, el sondeo responde, relanza el MISMO paso con el MISMO
    prompt (nunca terminó, así que la caché no lo tiene) y se repiten 4 x 240 s.
    Bucle sin fin que paga cada generación cortada hasta que el tope en horas
    detiene la corrida. Un intento cortado con el sondeo respondiendo es "modelo
    lento con esta petición", no "modelo caído": debe acabar en un fallo del paso
    con incidencia clara (o en un tope mayor), nunca en `ModeloSinRespuesta`."""
    _umbral_corto(monkeypatch)
    programa = ProgramaFalso(*["duerme"] * 6)
    reg = Registro(sondeos=[True] * 10)
    try:
        asyncio.run(VIG.llamar_vigilado(_ejecutor(programa), "cerebro", LMFalso(ASTRA), ganchos=reg.ganchos()))
    except VIG.ModeloSinRespuesta as ex:
        assert reg.sondeos_hechos >= 3 and reg.dormidas == [], "precondición: el sondeo respondió en cada espera"
        pytest.fail(f"un modelo que responde a {reg.sondeos_hechos} sondeos seguidos se declaró caído: {ex}")
    except Exception:  # noqa: BLE001
        pass  # fallar el paso con otra excepción (modelo lento, bloqueado) es aceptable: no entra en el bucle del supervisor


# ---------------------------------------------------------------------------
# (c) y (g): las peticiones de la persona se atienden dentro del bucle de tics
# ---------------------------------------------------------------------------


# El test "atender_peticiones no espera al vigilante dentro del bucle de tics"
# exigía que `_atender_peticiones` en sí volviera en menos de 0,2 s, pero lo que
# importa es que `correr()` no la espere en línea: esa propiedad la cubre
# rosa/tests/test_vigilante_corrida_adversario.py::test_una_peticion_lenta_dentro_del_bucle_congela_los_tics
# (los tics siguen mientras la petición dura). Se retiró el 18 de septiembre.


def test_una_llamada_sobre_una_corrida_detenida_no_la_deja_esperando_a_un_modelo(monkeypatch):
    """HUECO (medio). `_atender_peticiones` construye el Ctx sobre
    `ultima_corrida_de`, que puede estar detenida o terminada: la revisión pedida
    con la corrida parada lo hace a propósito (corrida.py ~553) y aclarar,
    comentarios, replicación y reformular no miran el estado. Si el modelo no
    responde, el vigilante escribe `esperandoModelo` en la corrida detenida y
    abre sobre ella la incidencia `modelo_sin_respuesta`; al agotar los intentos
    la excepción la traga el `except Exception` de `_atender_peticiones` y nadie
    limpia: el tic salta las corridas detenidas y terminadas y `_modelo_recuperado`
    exige `esperando_modelo`. La incidencia queda pendiente y la franja enseña
    "resolviéndose solo" para siempre sobre una corrida que ya acabó."""
    _sin_red_ni_esperas(monkeypatch)
    al, ctx = _ctx()
    al.mutar(lambda e: A.detener_corrida(e, ctx.corrida_id, "Detenida por la investigadora.", P.ahora_ms()), "detener")
    with pytest.raises(VIG.ModeloSinRespuesta):
        asyncio.run(ctx.llamar("juez", ProgramaFalso(*[TimeoutError()] * 8), x=1))
    c = _corrida(al, ctx.corrida_id)
    assert c["estado"] == "detenida"
    assert c["esperandoModelo"] is None, f"una corrida detenida quedó 'esperando' a {c['esperandoModelo']}"
    assert _incidencias(al, ctx.corrida_id, "pendiente") == [], "incidencia automática pendiente para siempre sobre una corrida detenida"


# ---------------------------------------------------------------------------
# (g) detener la corrida mientras el vigilante espera
# ---------------------------------------------------------------------------


def test_detener_la_corrida_mientras_el_vigilante_espera_no_deja_incidencia_ni_espera_colgadas(monkeypatch):
    """HUECO (bajo). La persona pulsa "Detener" mientras el vigilante duerme entre
    intentos: la tarea se cancela y `detener_corrida` (rosa/estado/acciones.py)
    solo cambia el estado. Quedan `esperandoModelo` relleno en una corrida
    detenida y la incidencia `modelo_sin_respuesta` pendiente para siempre: el
    vigilante ya no corre y el supervisor solo resuelve en `esperando_modelo`. La
    franja de modelos la enseñará "resolviéndose solo" en una corrida que ya no
    existe. El apagado del servidor sí está cubierto (el arranque adelanta el
    sondeo y `_modelo_recuperado` resuelve); detener a mano, no."""
    marcas = _sin_red_ni_esperas(monkeypatch, dormir_real_s=5.0)
    al, ctx = _ctx()
    programa = ProgramaFalso(TimeoutError(), "ok")

    async def escenario() -> None:
        tarea = asyncio.create_task(ctx.llamar("cerebro", programa, x=1))
        for _ in range(400):
            await asyncio.sleep(0.005)
            if marcas["dormidas"]:
                break
        assert marcas["dormidas"] == [15], "precondición: el vigilante está en su primera espera"
        tarea.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarea

    asyncio.run(escenario())
    assert _corrida(al, ctx.corrida_id)["estado"] == "esperando_modelo" and _incidencias(al, ctx.corrida_id, "pendiente"), "precondición: la espera quedó anotada"
    al.mutar(lambda e: A.detener_corrida(e, ctx.corrida_id, "Detenida por la investigadora.", P.ahora_ms()), "detener")
    c = _corrida(al, ctx.corrida_id)
    assert c["estado"] == "detenida"
    assert c["esperandoModelo"] is None, f"una corrida detenida sigue 'esperando' a {c['esperandoModelo']}"
    assert _incidencias(al, ctx.corrida_id, "pendiente") == [], "la incidencia automática queda pendiente para siempre en una corrida detenida"


# ---------------------------------------------------------------------------
# (i) textos: el detalle inventa un tiempo cuando el fallo fue instantáneo
# ---------------------------------------------------------------------------


def test_el_detalle_no_inventa_un_tiempo_de_espera_cuando_el_fallo_fue_instantaneo():
    """HUECO (bajo). `texto_detalle_intento` dice siempre "no respondió en 300 s",
    también cuando la excepción fue un ConnectError o un 503 que llegó en
    milisegundos. La persona lee que ROSA2018 esperó cinco minutos cuando no
    esperó nada, y la duración total "desde las HH:MM" no cuadra con los
    intentos."""
    programa = ProgramaFalso(httpx.ConnectError("no hay ruta al gateway"), "ok")
    reg = Registro()
    assert asyncio.run(VIG.llamar_vigilado(_ejecutor(programa), "juez", LMFalso(OPUS), ganchos=reg.ganchos())) == "ok"
    detalle = reg.incidencias[0][1]["detalle"]
    assert "ConnectError" in detalle, detalle
    assert "en 300 s" not in detalle, f"el fallo fue instantáneo y el detalle dice que esperó 300 s: {detalle!r}"


# ---------------------------------------------------------------------------
# (h) coste: LiteLLM sigue reintentando por dentro de cada intento del vigilante
# ---------------------------------------------------------------------------


def test_gateway_lm_no_deja_que_litellm_reintente_por_dentro(monkeypatch):
    """HUECO (bajo). `gateway.lm` deja `num_retries` en el 3 por defecto de dspy.LM:
    ante un 5xx o un 429 inmediatos LiteLLM hace 4 peticiones dentro de cada
    intento del vigilante (16 por ciclo de 4), con su propio retroceso, y contra
    un gateway que limita por ritmo eso empeora el 429 que se quiere esperar. El
    corte por intento (240/300 s) acota el caso de la corrida 13 (4 x 5 min en
    serie), pero el que reintenta debe ser solo el vigilante."""
    monkeypatch.setenv("ROSA_GATEWAY_KEY", "clave-de-prueba")
    modelo = GW.lm("openai/gpt-6-astra")
    assert modelo.kwargs.get("timeout") == 300
    assert modelo.num_retries == 0, f"dspy.LM reintentará {modelo.num_retries} veces por dentro de cada intento del vigilante"


# ---------------------------------------------------------------------------
# Intentos de rotura que aguantó (guardias)
# ---------------------------------------------------------------------------


def test_cuatro_llamadas_paralelas_de_la_misma_corrida_abren_una_incidencia_y_un_evento(monkeypatch):
    """El juez se llama en paralelo (semáforo de 4 en verificar_afirmaciones). Las
    cuatro fallan a la vez y vuelven a la vez: una incidencia, un evento de caída,
    uno de recuperación, una caída en la salud. Lo aguanta porque `Almacen.mutar`
    devuelve False cuando el reducer devuelve False y el evento se emite solo si
    la incidencia cambió."""
    _sin_red_ni_esperas(monkeypatch, dormir_real_s=0.01)
    al, ctx = _ctx()
    programas = [ProgramaFalso(TimeoutError(), f"r{i}") for i in range(4)]

    async def todas() -> list[Any]:
        return await asyncio.gather(*(ctx.llamar("juez", p, x=i) for i, p in enumerate(programas)))

    assert asyncio.run(todas()) == ["r0", "r1", "r2", "r3"]
    propias = _incidencias(al, ctx.corrida_id)
    assert len(propias) == 1 and propias[0]["estado"] == "resuelta", propias
    assert _eventos_modelo(al) == ["modelo_sin_respuesta", "modelo_recuperado"]
    s = al.estado["saludModelos"]["juez"]
    assert s["caidas"] == 1 and s["estado"] == "ok"
    c = _corrida(al, ctx.corrida_id)
    assert c["estado"] == "en_marcha" and c["esperandoModelo"] is None


def test_una_excepcion_del_propio_vigilante_no_se_reclasifica_ni_reintenta():
    """HUECO (bajo). Una llamada vigilada dentro de otra (hoy no la hay: ninguna
    herramienta de rosa/herramientas.py llama a `ctx.llamar`; mañana un ReAct
    podría): `ModeloSinRespuesta` sale como "otro" (bien), pero `ModeloBloqueado`
    lleva en su mensaje el error original ("Empty response") y `clasificar_fallo`
    lo devuelve como "contenido": el vigilante exterior reintentaría con otro
    rollout_id lo que el interior ya agotó (3 x 3 llamadas de pago). Las
    excepciones propias deben ir antes que las palabras."""
    interior_sin = VIG.ModeloSinRespuesta("juez", "anthropic/claude-opus-5", 4, 1_700_000_000_000)
    interior_bloq = VIG.ModeloBloqueado("cerebro", "openai/gpt-6-astra", 2, "RuntimeError: Empty response from the model")
    assert VIG.clasificar_fallo(interior_sin) == "otro", str(interior_sin)
    assert VIG.clasificar_fallo(interior_bloq) == "otro", str(interior_bloq)
