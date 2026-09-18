"""La regla de Sonnet, comprobada de punta a punta sobre `Ctx.llamar`.

Regla de Emir (TRASPASO.md 7.4, 18 de septiembre de 2026): el cerebro es GPT-6
Astra y solo Astra; el juez es Claude Opus 5 y solo Opus. Cuando no responden,
ROSA2018 espera y reintenta con el MISMO modelo; nunca degrada el rol a Claude
Sonnet 5. Sonnet queda para el rol de volumen.

Aquí el modelo de volumen es un espía: anota si alguien lo copia y el programa
falso anota con qué modelo se ejecutó cada vez. Con el cerebro (o el juez)
lanzando tiempo agotado, devolviendo vacío o tardando justo el umbral,
`Ctx.llamar` no toca al de volumen ni una vez. Ningún test sale a la red ni
espera: dobles, dormir anulado y sondeo falso.
"""

from __future__ import annotations

import asyncio
import inspect
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import dspy
import pytest

from rosa import vigilante_modelos as VIG
from rosa.bucle import pasos as PASOS
from rosa.bucle.pasos import Ctx
from rosa.estado.almacen import Almacen

ASTRA = "openai/openai/gpt-6-astra"  # `lm.model` tal como lo construye gateway.lm
OPUS = "openai/anthropic/claude-opus-5"
SONNET = "openai/anthropic/claude-sonnet-5"


# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------


class LMFalso:
    """Un dspy.LM de mentira: `model`, `kwargs` y `copy(rollout_id=...)`."""

    def __init__(self, model: str, rollout_id: int | None = None) -> None:
        self.model = model
        self.kwargs: dict[str, Any] = {} if rollout_id is None else {"rollout_id": rollout_id}

    def copy(self, **kw: Any) -> "LMFalso":
        return LMFalso(self.model, kw.get("rollout_id"))


class VolumenEspia(LMFalso):
    """Sonnet: anota cada copia que alguien le pida (un reintento por contenido
    con este modelo sería una degradación del rol)."""

    def __init__(self) -> None:
        super().__init__(SONNET)
        self.copias: list[dict[str, Any]] = []

    def copy(self, **kw: Any) -> "LMFalso":
        self.copias.append(dict(kw))
        return LMFalso(self.model, kw.get("rollout_id"))


class ProgramaFalso:
    """`acall` sigue un plan: una excepción a lanzar, la cadena "duerme" (duerme
    `segundos` reales) o un valor a devolver. Anota con qué modelo (y qué
    rollout_id) se ejecutó cada llamada."""

    def __init__(self, *plan: Any, segundos: float = 0.3) -> None:
        self.plan = list(plan)
        self.segundos = segundos
        self.vistos: list[tuple[str | None, int | None]] = []

    async def acall(self, **kw: Any) -> Any:
        lm = dspy.settings.lm
        self.vistos.append((getattr(lm, "model", None), (getattr(lm, "kwargs", None) or {}).get("rollout_id")))
        paso = self.plan.pop(0) if self.plan else "ok"
        if isinstance(paso, BaseException):
            raise paso
        if paso == "duerme":
            await asyncio.sleep(self.segundos)
            return "tarde"
        return paso

    def modelos_vistos(self) -> set[str | None]:
        return {m for m, _ in self.vistos}


def _ctx() -> tuple[Almacen, Ctx, VolumenEspia]:
    al = Almacen(Path(tempfile.mkdtemp()) / "t.db")
    inv = "inv"
    al.aplicar("crearInvestigacion", {"datos": {"titulo": inv, "objetivo": "Astrocitos en el Alzheimer", "condicionParada": "1 iteración"}, "id_": inv})
    cid = al.aplicar("iniciarCorrida", {"investigacion_id": inv})
    it_id = f"it-{inv}"

    def preparar(e: dict[str, Any]) -> bool:
        c = next(x for x in e["corridas"] if x["id"] == cid)
        c["estado"] = "en_marcha"
        e["iteraciones"].append({"id": it_id, "corridaId": cid, "numero": 1, "plan": [{"id": "paso-1", "estado": "en_curso"}], "pistas": [], "planAprobado": True, "terminadaEn": None, "presupuesto": {"limite": None, "usado": 0}})
        return True

    al.mutar(preparar, "test")
    espia = VolumenEspia()
    modelos = SimpleNamespace(cerebro=LMFalso(ASTRA), juez=LMFalso(OPUS), volumen=espia, replica=LMFalso(OPUS))
    return al, Ctx(al, SimpleNamespace(juzgar=None), modelos, cid, inv, it_id, 1), espia


def _sin_red_ni_esperas(monkeypatch: pytest.MonkeyPatch, sondeos: list[bool] | None = None) -> dict[str, Any]:
    """Los ganchos reales de la corrida, pero sin dormir ni salir a la red."""
    original = VIG.ganchos_de_contexto
    marcas: dict[str, Any] = {"dormidas": [], "sondeos": 0}
    respuestas = list(sondeos or [])

    def parche(ctx: Any) -> VIG.Ganchos:
        g = original(ctx)

        async def dormir(s: float) -> None:
            marcas["dormidas"].append(s)

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


def _incidencias(al: Almacen, cid: str, tipo: str | None = None) -> list[dict[str, Any]]:
    return [i for i in al.estado["incidencias"] if i["corridaId"] == cid and (tipo is None or i["tipo"] == tipo)]


def _nunca_sonnet(programa: ProgramaFalso, espia: VolumenEspia, esperado: str) -> None:
    assert programa.vistos, "el programa tuvo que ejecutarse al menos una vez"
    assert programa.modelos_vistos() == {esperado}, f"el programa se ejecutó con otros modelos: {programa.vistos}"
    assert SONNET not in programa.modelos_vistos(), "Sonnet entró en contexto para un rol que no es el de volumen"
    assert espia.copias == [], f"alguien pidió copias del modelo de volumen: {espia.copias}"


MODELO_DEL_ROL = {"cerebro": ASTRA, "juez": OPUS, "replica": OPUS}


# ---------------------------------------------------------------------------
# Tiempo agotado: se reintenta con el mismo modelo hasta MAX_INTENTOS y se espera
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rol", ["cerebro", "juez", "replica"])
def test_con_el_modelo_del_rol_sin_responder_nunca_se_llama_al_de_volumen(monkeypatch, rol):
    marcas = _sin_red_ni_esperas(monkeypatch)
    al, ctx, espia = _ctx()
    programa = ProgramaFalso(*[TimeoutError("el gateway no contesta")] * 10)
    with pytest.raises(VIG.ModeloSinRespuesta) as ex:
        asyncio.run(ctx.llamar(rol, programa, x=1))
    _nunca_sonnet(programa, espia, MODELO_DEL_ROL[rol])
    assert len(programa.vistos) == VIG.MAX_INTENTOS, "cuatro intentos con el mismo modelo, ni uno más ni uno menos"
    assert ex.value.rol == rol and ex.value.intentos == VIG.MAX_INTENTOS
    assert marcas["dormidas"] == [15, 30, 60], "las esperas del contrato compartido entre los cuatro intentos"
    c = _corrida(al, ctx.corrida_id)
    assert c["estado"] == "esperando_modelo" and c["esperandoModelo"]["rol"] == rol, "la corrida espera al mismo modelo; no cambia de modelo ni muere"
    inc = _incidencias(al, ctx.corrida_id, "modelo_sin_respuesta")
    assert len(inc) == 1 and "resolviendo sola" in (inc[0]["alternativa"] or "") and "Sonnet" not in (inc[0]["alternativa"] or "")
    assert [e["tipo"] for e in al.estado["eventos"] if e["tipo"].startswith("modelo_")] == ["modelo_sin_respuesta"]


def test_el_modelo_que_falla_siempre_sigue_sin_sustituirse_en_la_segunda_ronda(monkeypatch):
    """Modelo que falla siempre: tras `ModeloSinRespuesta`, la siguiente llamada
    (la que haría el supervisor al relanzar el paso) vuelve a intentarlo con el
    mismo modelo, vuelve a agotar los intentos y sigue sin tocar a Sonnet."""
    _sin_red_ni_esperas(monkeypatch)
    al, ctx, espia = _ctx()
    programa = ProgramaFalso(*[ConnectionError("sin red")] * 20)
    for ronda in (1, 2):
        with pytest.raises(VIG.ModeloSinRespuesta):
            asyncio.run(ctx.llamar("cerebro", programa, x=ronda))
    _nunca_sonnet(programa, espia, ASTRA)
    assert len(programa.vistos) == 2 * VIG.MAX_INTENTOS
    assert al.estado["saludModelos"]["cerebro"]["estado"] == "sin_respuesta" and al.estado["saludModelos"]["cerebro"]["modelo"] == "openai/gpt-6-astra"
    assert len(_incidencias(al, ctx.corrida_id, "modelo_sin_respuesta")) == 1, "veinte fallos seguidos abren una sola incidencia"


# ---------------------------------------------------------------------------
# Respuesta vacía o filtro: mismo modelo variando el rollout_id; después el paso falla
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rol", ["cerebro", "juez", "replica"])
@pytest.mark.parametrize("fallo", [ValueError("Empty response from the model"), RuntimeError("content_filter: the request was blocked by the content policy")])
def test_con_respuesta_vacia_o_filtro_se_varia_el_rollout_id_y_nunca_se_cae_a_sonnet(monkeypatch, rol, fallo):
    _sin_red_ni_esperas(monkeypatch)
    al, ctx, espia = _ctx()
    programa = ProgramaFalso(*[type(fallo)(str(fallo))] * 6)
    with pytest.raises(VIG.ModeloBloqueado) as ex:
        asyncio.run(ctx.llamar(rol, programa, x=1))
    _nunca_sonnet(programa, espia, MODELO_DEL_ROL[rol])
    assert len(programa.vistos) == 1 + VIG.MAX_REINTENTOS_CONTENIDO
    rollouts = [r for _, r in programa.vistos]
    assert rollouts[0] is None and len(set(rollouts)) == len(rollouts), f"cada reintento por contenido lleva un rollout_id distinto: {rollouts}"
    assert ex.value.rol == rol and ex.value.motivo == "contenido"
    inc = _incidencias(al, ctx.corrida_id, "modelo_bloqueado")
    assert len(inc) == 1 and "Sonnet" not in (inc[0]["alternativa"] or "") and "mismo modelo" in inc[0]["detalle"]
    assert _corrida(al, ctx.corrida_id)["estado"] == "en_marcha", "un filtro no es una caída: la corrida no pasa a esperando_modelo"


def test_con_respuesta_vacia_que_se_arregla_al_variar_el_rollout_id_se_devuelve_la_del_mismo_modelo(monkeypatch):
    _sin_red_ni_esperas(monkeypatch)
    al, ctx, espia = _ctx()
    programa = ProgramaFalso(ValueError("Empty response from the model"), "respuesta buena")
    assert asyncio.run(ctx.llamar("cerebro", programa, x=1)) == "respuesta buena"
    _nunca_sonnet(programa, espia, ASTRA)
    assert [r for _, r in programa.vistos] == [None, VIG.rollout_de_reintento(None, 1)]
    assert _incidencias(al, ctx.corrida_id) == [], "un vacío que se arregla al reintentar no deja incidencia"


# ---------------------------------------------------------------------------
# El rol de volumen tampoco se sustituye por otro (ni al revés)
# ---------------------------------------------------------------------------


def test_el_de_volumen_que_devuelve_vacio_falla_tal_cual_sin_pedirle_nada_al_cerebro(monkeypatch):
    _sin_red_ni_esperas(monkeypatch)
    al, ctx, espia = _ctx()
    programa = ProgramaFalso(ValueError("Empty response from the model"))
    with pytest.raises(ValueError):
        asyncio.run(ctx.llamar("volumen", programa, x=1))
    assert programa.modelos_vistos() == {SONNET} and len(programa.vistos) == 1, "el volumen no reintenta por contenido ni cambia de modelo"
    assert espia.copias == []
    assert _incidencias(al, ctx.corrida_id) == []


# ---------------------------------------------------------------------------
# Justo en el umbral: el modelo tarda lo que dura el tope
# ---------------------------------------------------------------------------


def test_un_modelo_que_tarda_justo_el_umbral_no_se_sustituye_ni_se_declara_caido(monkeypatch):
    """El intento dura lo mismo que TIEMPO_AVISO_S. Puede acabar por sí mismo
    ("tarde") o cortarse: si se corta y el sondeo responde, es "lento con esta
    petición" y se amplía el tope una vez; el segundo intento responde. En
    ningún caso hay `ModeloSinRespuesta`, ni Sonnet, ni caída contada."""
    for rol in ("cerebro", "juez", "volumen", "replica"):
        monkeypatch.setitem(VIG.TIEMPO_AVISO_S, rol, 0.05)
    marcas = _sin_red_ni_esperas(monkeypatch, sondeos=[True] * 5)
    al, ctx, espia = _ctx()
    programa = ProgramaFalso("duerme", "ok", segundos=0.05)
    resultado = asyncio.run(ctx.llamar("cerebro", programa, x=1))
    assert resultado in ("tarde", "ok")
    _nunca_sonnet(programa, espia, ASTRA)
    assert len(programa.vistos) <= 2 and marcas["dormidas"] == [], "un modelo vivo pero lento no entra en el bucle esperar-sondear-relanzar"
    salud = al.estado["saludModelos"].get("cerebro") or {}
    assert salud.get("estado") == "ok" and int(salud.get("caidas") or 0) == 0, f"tardar justo el umbral no es una caída: {salud}"
    assert _corrida(al, ctx.corrida_id)["estado"] == "en_marcha"
    assert _incidencias(al, ctx.corrida_id, "modelo_sin_respuesta") == []


# ---------------------------------------------------------------------------
# Guardias sobre el código: el respaldo a Sonnet no vuelve
# ---------------------------------------------------------------------------


def test_ctx_llamar_ya_no_tiene_el_respaldo_al_modelo_de_volumen():
    fuente = inspect.getsource(Ctx.llamar)
    assert "Se reintentó con Sonnet" not in fuente
    assert "lm=self.modelos.volumen" not in fuente, "el respaldo 'reintenta una vez con el modelo de volumen' volvió a Ctx.llamar"
    assert "llamar_vigilado" in fuente
    assert set(VIG.ROLES_QUE_NO_SE_SUSTITUYEN) == {"cerebro", "juez", "replica"}
    assert PASOS.ModeloBloqueado is VIG.ModeloBloqueado, "una sola excepción de bloqueo, la del vigilante"
