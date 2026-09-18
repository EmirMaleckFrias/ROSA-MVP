"""Tanda 1, cierre (17 de septiembre de 2026): las interfaces que un grupo
dejó pendientes de otro, resueltas y fijadas con un test cada una. Cada test
falla sin su arreglo:

- S-19: el contador acumula lo que factura el gateway (`usage.cost`) en
  `gasto.usdReal` y marca `usdEsEstimado` cuando tuvo que usar la tabla.
- M-01: "sin información" en el riesgo de sesgo no es "riesgo alto" tampoco en
  el camino del Killer (`comprobacion_sesgo` relee los dominios con la misma
  regla que el peso GRADE; `juicio_global_por_dominios` no escala por dominios
  sin texto).
- S-18: la casilla "datos de prueba" de la ficha llega al reducer por el
  endpoint multipart.
- S-23: `revisar_hipotesis` es idempotente (misma regla que acciones.ts).
- S-09: la clave pública `killerPendiente` mientras el juez no responde, y se
  quita al juzgar.
- S-09/S-08: la petición de revisión no cuenta dos veces el intento cuando el
  Killer ya lo contó.
- Novedad: la marca de revisión tras comprobar la novedad solo si algún estado
  cambió (o es la primera comprobación), no en cada iteración.
- S-05: la extracción compara contra el texto ya guardado de la página y da un
  motivo propio cuando el extractor no devuelve pasaje.
- S-20: `Ctx.llamar(rollout_id=...)` distingue trayectorias en la caché.
- M-04: `anotar_cohortes` escribe también `hipotesis.cohortesDistintas`.
- Killer: supuestos que no son diccionarios no lo tumban; la novedad no
  comprobada lleva el prefijo que `fusionar` reconoce.
- S-04: la réplica conserva `fuenteId` y resuelve la cita por él.
- S-01: con `parar()` el supervisor no arranca trabajo nuevo.
- S-09: una suspensión técnica (`sinJuez`) no es un cierre científico para las
  lecciones ni para el traspaso al planificador.
- S-12: el dossier distingue "auditoría sin respuesta" de "en desacuerdo".
- literatura-02: las fuentes sin autores de Europe PMC, OpenAlex y PubMed
  llevan su identificador, no "Sin autor" a secas.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import dspy.clients.base_lm
import pytest

from rosa import certeza as CERTEZA
from rosa import killer as K
from rosa import lecciones as LEC
from rosa import priorizacion as PR
from rosa import sesgo as SESGO
from rosa import verificador as V
from rosa.bucle import contexto as T
from rosa.bucle import corrida as CO
from rosa.bucle import pasos as PASOS
from rosa.bucle.pasos import Ctx
from rosa.dossier import texto_dossier
from rosa.estado import acciones as A
from rosa.fuentes import base as FB
from rosa.fuentes import openalex
from rosa.modulos import contador as CT
from rosa.tests.test_integracion_pasos import _afirmacion, _ctx, _hipotesis
from rosa.tests.test_lecciones import _estado_cierre
from rosa.tests.test_servidor import cliente  # noqa: F401  (fixture)
from rosa.tests.test_tanda1_pasos_killer import _decisiones, _hip, _llamar, _preparar, _revision_killer
from rosa.tests import test_tanda1_pasos_literatura as LIT


# ---------------------------------------------------------------------------
# S-19: coste real del gateway
# ---------------------------------------------------------------------------


def _llamada_contada(al, ctx, historia, usage: dict[str, Any], n: int) -> None:
    contador = CT.Contador(al)
    lm = SimpleNamespace(model="openai/anthropic/claude-opus-5")
    inputs = {"messages": [{"role": "user", "content": f"llamada {n}"}]}
    token = CT.contexto_actual.set(CT.ContextoLlamada(ctx.corrida_id, ctx.numero, "juez"))
    try:
        contador.on_lm_start(f"c-{n}", lm, inputs)
        historia.append({"messages": inputs["messages"], "usage": usage, "model": lm.model, "outputs": ["x"]})
        contador.on_lm_end(f"c-{n}", ["x"])
    finally:
        CT.contexto_actual.reset(token)


def test_el_contador_acumula_el_coste_del_gateway_y_marca_lo_estimado(monkeypatch):
    al, ctx = _ctx()
    historia: list[dict[str, Any]] = []
    monkeypatch.setattr(dspy.clients.base_lm, "GLOBAL_HISTORY", historia)
    _llamada_contada(al, ctx, historia, {"prompt_tokens": 1000, "completion_tokens": 100, "cost": 0.0123}, 1)
    g = next(c for c in al.estado["corridas"] if c["id"] == ctx.corrida_id)["gasto"]
    assert g["usdReal"] == pytest.approx(0.0123, abs=1e-4) and g["usd"] == pytest.approx(0.0123, abs=1e-4)
    assert g.get("usdEsEstimado") is not True
    # Sin `cost`: la tabla de respaldo suma a `usd`, no a `usdReal`, y queda marcado.
    _llamada_contada(al, ctx, historia, {"prompt_tokens": 1_000_000, "completion_tokens": 0}, 2)
    g = next(c for c in al.estado["corridas"] if c["id"] == ctx.corrida_id)["gasto"]
    assert g["usdReal"] == pytest.approx(0.0123, abs=1e-4)
    assert g["usd"] == pytest.approx(5.0123, abs=1e-3), "Opus a 5 USD por millón de entrada en la tabla de respaldo"
    assert g["usdEsEstimado"] is True and g["llamadas"] == 2
    al.cerrar()


# ---------------------------------------------------------------------------
# M-01: sin información no es riesgo alto
# ---------------------------------------------------------------------------


def _dominio(id_: str, juicio: str, motivo: str) -> dict[str, Any]:
    return {"id": id_, "nombre": id_, "juicio": juicio, "motivo": motivo, "respuestas": []}


def test_sin_informacion_no_escala_a_alto_ni_en_el_global_ni_en_el_killer():
    ni = [_dominio(f"D{i}", "algunas_dudas", "3 preguntas sin información en el texto") for i in range(6)]
    assert SESGO.juicio_global_por_dominios(ni) == "algunas_dudas"
    con_respuestas = [_dominio(f"D{i}", "algunas_dudas", "respuestas en el sentido del riesgo: q1=Y") for i in range(3)]
    assert SESGO.juicio_global_por_dominios(con_respuestas) == "alto", "tres dudas con respuestas sí escalan, como en RoB 2"
    assert SESGO.juicio_global_por_dominios(con_respuestas[:2] + ni[:4]) == "algunas_dudas"
    assert SESGO.juicio_global_por_dominios([_dominio("D1", "bajo", "x"), _dominio("D2", "alto", "respuestas en el sentido del riesgo")]) == "alto"
    assert SESGO.juicio_global_por_dominios([]) == "no_aplica"
    # `evaluar` sin respuestas (todo NI) ya no da "alto".
    ev = SESGO.evaluar("robins_i", [], "sim", 1)
    assert ev["global"] == "algunas_dudas"
    # La comprobación del Killer relee por dominios: una fuente "alto" guardada solo por
    # falta de texto no cuenta como sesgada; una con dominios informados sí.
    guardada_alto_por_ni = {"instrumento": "ROBINS-I", "global": "alto", "dominios": ni}
    informada_bajo = {"instrumento": "RoB 2", "global": "bajo", "dominios": [_dominio("D1", "bajo", "todas las preguntas del dominio van en el sentido de bajo riesgo")]}
    solo_ni = SESGO.comprobacion_sesgo([{"id": "f1", "referencia": "A", "riesgoSesgo": guardada_alto_por_ni}])
    assert solo_ni["resultado"] == "no_comprobable" and "no daba información" in solo_ni["detalle"]
    mixta = SESGO.comprobacion_sesgo([{"id": "f1", "referencia": "A", "riesgoSesgo": guardada_alto_por_ni}, {"id": "f2", "referencia": "B", "riesgoSesgo": informada_bajo}])
    assert mixta["resultado"] == "pasa" and "1 sin información suficiente" in mixta["detalle"]
    alto_real = {"instrumento": "RoB 2", "global": "alto", "dominios": [_dominio("D1", "alto", "respuestas en el sentido del riesgo: q1=Y")]}
    assert SESGO.comprobacion_sesgo([{"id": "f1", "referencia": "A", "riesgoSesgo": alto_real}])["resultado"] == "falla"
    # Una sola regla para el peso GRADE y para el Killer.
    assert CERTEZA.juicio_sesgo_util(guardada_alto_por_ni) == SESGO.juicio_util(guardada_alto_por_ni) == (None, "6 dominios sin información en el texto y ninguno con riesgo: sin evaluar, no se penaliza")
    assert SESGO.juicio_util({"global": "alto"}) == ("alto", "juicio global alto")
    assert SESGO.juicio_util(None) == (None, "riesgo de sesgo sin evaluar")


# ---------------------------------------------------------------------------
# S-18: la casilla de datos de prueba llega al reducer
# ---------------------------------------------------------------------------


def test_subir_datos_recibe_la_casilla_de_datos_sinteticos(cliente):  # noqa: F811
    c, al = cliente
    r = c.post("/api/acciones/crearInvestigacion", json={"datos": {"titulo": "T", "objetivo": "O", "condicionParada": "1 iteraciones"}}, headers={"X-Rosa": "1"})
    assert r.status_code == 200
    inv_id = al.estado["investigaciones"][-1]["id"]
    h = _hipotesis(investigacionId=inv_id)
    h["experimento"] = {"protocolo": "p", "ensayo": "e", "costeEstimado": "c", "laboratorio": None, "estado": "propuesto", "ficheroDatos": None, "analisisPedido": ""}
    al.mutar(lambda e: e["hipotesis"].append(h) or True, "prueba")
    r = c.post(f"/api/hipotesis/{h['id']}/datos", files={"fichero": ("resultados_ELISA.csv", b"a,b\n1,2\n", "text/csv")}, data={"analisis": "x", "sintetico": "on"}, headers={"X-Rosa": "1"})
    assert r.status_code == 200, r.text
    x = next(y for y in al.estado["hipotesis"] if y["id"] == h["id"])
    assert x["experimento"]["datosSinteticos"] is True, "la casilla marcada ('on') tiene que llegar al reducer"
    # Sin la casilla, un fichero con nombre clínico real cuenta como real.
    h2 = _hipotesis(investigacionId=inv_id)
    h2["experimento"] = dict(h["experimento"], ficheroDatos=None, datosSinteticos=False)
    al.mutar(lambda e: e["hipotesis"].append(h2) or True, "prueba")
    r = c.post(f"/api/hipotesis/{h2['id']}/datos", files={"fichero": ("resultados_ELISA.csv", b"a,b\n1,2\n", "text/csv")}, data={"analisis": "x"}, headers={"X-Rosa": "1"})
    assert r.status_code == 200, r.text
    x2 = next(y for y in al.estado["hipotesis"] if y["id"] == h2["id"])
    assert x2["experimento"].get("datosSinteticos") is False


# ---------------------------------------------------------------------------
# S-23: revisar_hipotesis idempotente
# ---------------------------------------------------------------------------


def test_revisar_hipotesis_no_registra_dos_veces_una_decision_ya_aplicada():
    al, ctx = _ctx()
    h = _hipotesis()
    al.mutar(lambda e: e["hipotesis"].append(h) or True, "prueba")
    assert al.aplicar("revisarHipotesis", {"hipotesis_id": h["id"], "accion": "aceptar", "nota": "", "quien": "Dra. A"}) is not False
    x = _hip(al, h)
    n_rev, n_hechos = len(x["revisiones"]), len(al.estado["hechos"])
    assert x["estado"] == "aceptada"
    # El mismo POST otra vez (doble clic o reintento tras un 5xx): no cambia nada.
    assert al.aplicar("revisarHipotesis", {"hipotesis_id": h["id"], "accion": "aceptar", "nota": "", "quien": "Dra. A"}) is False
    x = _hip(al, h)
    assert len(x["revisiones"]) == n_rev and len(al.estado["hechos"]) == n_hechos
    # Otra decisión distinta sí se aplica.
    assert al.aplicar("revisarHipotesis", {"hipotesis_id": h["id"], "accion": "reabrir", "nota": "", "quien": "Dra. A"}) is not False
    assert _hip(al, h)["estado"] == "en_revision"
    al.cerrar()


# ---------------------------------------------------------------------------
# S-09: killerPendiente pública y sin doble cuenta del intento
# ---------------------------------------------------------------------------


def test_killer_pendiente_es_publica_mientras_el_juez_no_responde_y_se_quita_al_juzgar(monkeypatch):
    h = _hipotesis()
    al, ctx = _preparar(monkeypatch, h)
    monkeypatch.setattr(Ctx, "llamar", _llamar({"killer": RuntimeError("timeout")}))
    asyncio.run(PASOS._killer(ctx, h, "", None))
    x = _hip(al, h)
    assert x["killerPendiente"] == {"intentos": 1, "maximo": PASOS.MAX_INTENTOS_JUEZ, "motivo": f"el juez no respondió (intento 1 de {PASOS.MAX_INTENTOS_JUEZ})"}
    assert "killerPendiente" in al.instantanea()["hipotesis"][0], "es pública: la ficha la lee"
    assert "_killerIntentos" not in al.instantanea()["hipotesis"][0]
    # El juez vuelve: la decisión borra la marca pública junto con las privadas.
    monkeypatch.setattr(Ctx, "llamar", _llamar({"killer": _revision_killer()}))
    asyncio.run(PASOS._killer(ctx, _hip(al, h), "", None))
    x = _hip(al, h)
    assert "killerPendiente" not in x and "_killerIntentos" not in x and len(_decisiones(al, h)) == 1
    # Al tope técnico también desaparece (hay una decisión explícita).
    monkeypatch.setattr(Ctx, "llamar", _llamar({"killer": RuntimeError("timeout")}))
    for _ in range(PASOS.MAX_INTENTOS_JUEZ):
        asyncio.run(PASOS._killer(ctx, _hip(al, h), "", None))
    x = _hip(al, h)
    assert "killerPendiente" not in x and _decisiones(al, h)[-1]["sinJuez"] is True


def test_la_peticion_de_revision_no_cuenta_dos_veces_el_intento_que_ya_conto_el_killer():
    h = {"id": "h", "estado": "propuesta", "_revisionPedida": True, "_killerIntentos": 1, "killerPendiente": {"intentos": 1}, "procedencia": {"registro": []}}
    e = {"hipotesis": [h], "decisiones": []}
    # El Killer ya subió el contador de 0 a 1 durante la llamada: aquí no se suma otra vez.
    assert CO._cerrar_peticion_de_revision(e, "h", 0, intentos_antes=0) is True
    assert h["_killerIntentos"] == 1 and h["_revisionPedida"] is True
    # Si el Killer no llegó a contar (otra excepción), se cuenta aquí.
    CO._cerrar_peticion_de_revision(e, "h", 0, intentos_antes=1)
    assert h["_killerIntentos"] == 2
    # Con decisión nueva se limpia todo, también la clave pública.
    e["decisiones"].append({"hipotesisId": "h", "etapa": "killer_1", "fecha": 5})
    CO._cerrar_peticion_de_revision(e, "h", 0, intentos_antes=2)
    assert "killerPendiente" not in h and "_killerIntentos" not in h and "_revisionPedida" not in h


# ---------------------------------------------------------------------------
# Novedad: la marca de revisión solo si algo cambió
# ---------------------------------------------------------------------------


def test_la_novedad_repetida_sin_cambios_no_vuelve_a_pedir_revision(monkeypatch):
    al, ids, ctx = LIT._preparar()
    LIT._sin_red(monkeypatch, obras=[], total=0, relevancia=lambda kw: 2)
    al.mutar(lambda e: next(x for x in e["hipotesis"] if x["id"] == ids["hip"]).__setitem__("decisionKiller", "suspender") or True, "prueba")
    asyncio.run(PASOS.paso_novedad(ctx, LIT._paso(al, ids)))
    x = LIT._hip(al, ids)
    assert x["_novedadIntentos"] == 1 and x.get("_revisionPedida") is True, "la primera comprobación sí pide juicio"
    al.mutar(lambda e: next(y for y in e["hipotesis"] if y["id"] == ids["hip"]).pop("_revisionPedida", None) or True, "prueba")
    asyncio.run(PASOS.paso_novedad(ctx, LIT._paso(al, ids)))
    x = LIT._hip(al, ids)
    assert x["_novedadIntentos"] == 2 and x.get("_revisionPedida") is None, "misma novedad, mismo juicio: no se repite"
    assert PASOS._estados_de_novedad(None) == {} and PASOS._estados_de_novedad({"a": {"estado": "x"}, "b": "raro"}) == {"a": "x"}


# ---------------------------------------------------------------------------
# S-05: extracción contra el texto guardado, y sin pasaje
# ---------------------------------------------------------------------------


def test_la_extraccion_marca_el_pasaje_ausente_y_compara_contra_el_texto_guardado(monkeypatch):
    al, ids, ctx = LIT._preparar()
    fid = PASOS._registrar_fuente(ctx, {"referencia": "Kim et al., 2025", "titulo": "T", "doi": "10.1/t", "tipos": [], "resumen": ""}, "articulo", [{"localizador": "pág. 3", "texto": "GFAP sube en la fase preclínica " * 10, "encabezado": "T"}], 8, None, "limpio", 1, "q")
    assert fid
    abierto = []
    monkeypatch.setattr(PASOS.pdf, "fragmento_en_pagina", lambda *a, **k: abierto.append(a) or True)

    async def llamar(self, rol, programa, **kw):
        return SimpleNamespace(afirmaciones=[
            SimpleNamespace(texto="Sin pasaje", fragmento="", tipo="dato", tema="GFAP", cohorte="", nivel_medicion="resultado_analisis", n="", comparador="", efecto="", incertidumbre=""),
            SimpleNamespace(texto="Inventada", fragmento="NfL baja en la fase tardía", tipo="dato", tema="NfL", cohorte="", nivel_medicion="resultado_analisis", n="", comparador="", efecto="", incertidumbre=""),
            SimpleNamespace(texto="Literal", fragmento="GFAP sube en la fase preclínica", tipo="dato", tema="GFAP", cohorte="", nivel_medicion="resultado_analisis", n="", comparador="", efecto="", incertidumbre=""),
        ])

    monkeypatch.setattr(Ctx, "llamar", llamar)
    paso = {"id": "paso-ext", "tipo": "extraccion", "titulo": "Extraer", "estado": "en_curso", "detalle": "", "indicacionHumana": False, "motivoFallo": None}
    al.mutar(lambda e: next(i for i in e["iteraciones"] if i["id"] == ids["it"])["plan"].append(paso) or True, "plan")
    asyncio.run(PASOS.paso_extraccion(ctx, paso))
    por_texto = {a["texto"]: a for a in ctx.afirmaciones()}
    assert por_texto["Sin pasaje"]["veredicto"] == "cita_no_resuelve" and "no devolvió el pasaje" in por_texto["Sin pasaje"]["motivo"]
    assert por_texto["Inventada"]["veredicto"] == "cita_no_resuelve" and "no aparece literalmente" in por_texto["Inventada"]["motivo"]
    assert por_texto["Literal"]["veredicto"] == "sin_verificar"
    assert abierto == [], "la página no se reabre del PDF por afirmación: se compara con el texto guardado"


# ---------------------------------------------------------------------------
# S-20: rollout_id en Ctx.llamar
# ---------------------------------------------------------------------------


class _LM:
    def __init__(self, model: str, rollout_id: int | None = None):
        self.model = model
        self.rollout_id = rollout_id
        self.kwargs: dict[str, Any] = {}

    def copy(self, **kw):
        return _LM(self.model, kw.get("rollout_id"))


def test_ctx_llamar_pasa_el_rollout_id_a_una_copia_del_modelo(monkeypatch):
    al, ctx = _ctx()
    ctx.modelos = SimpleNamespace(juez=_LM("juez"), cerebro=_LM("cerebro"), volumen=_LM("volumen"), replica=_LM("replica"))
    vistos: list[Any] = []

    class Programa:
        async def acall(self, **kw):
            vistos.append(PASOS.dspy.settings.lm)
            return "ok"

    monkeypatch.setattr(Ctx, "_acotar_contexto", lambda self, rol, kw: kw)
    assert asyncio.run(ctx.llamar("replica", Programa(), rollout_id=2, x=1)) == "ok"
    assert asyncio.run(ctx.llamar("replica", Programa(), x=1)) == "ok"
    assert vistos[0].rollout_id == 2 and vistos[0].model == "replica", "con rollout_id se llama a una copia del modelo con ese id"
    assert vistos[1].rollout_id is None, "sin rollout_id el modelo va tal cual"
    al.cerrar()


# ---------------------------------------------------------------------------
# M-04 y Killer con registros raros
# ---------------------------------------------------------------------------


def test_anotar_cohortes_escribe_la_lista_en_la_hipotesis_y_en_la_conclusion():
    h = _hipotesis(afirmaciones=[_afirmacion(cohorte="ADNI"), _afirmacion(afirmacionId="af-2", cohorte="BioFINDER-2", cita="[B et al., 2024, pág. 2]")])
    h["procedencia"]["fuentes"] = [{"id": "f1", "referencia": "A et al., 2025", "pagina": 3, "cohorte": "ADNI"}, {"id": "f2", "referencia": "B et al., 2024", "pagina": 2, "cohorte": "BioFINDER-2"}]
    h["conclusion"] = None
    lista = PR.anotar_cohortes(h)
    assert h["cohortesDistintas"] == lista and isinstance(lista, list)
    h["conclusion"] = {"certeza": "baja"}
    PR.anotar_cohortes(h)
    assert h["conclusion"]["cohortesDistintas"] == h["cohortesDistintas"]


def test_el_killer_aguanta_supuestos_que_no_son_diccionarios_y_prefija_la_novedad_pendiente():
    h = _hipotesis(supuestos=["un texto suelto", None, {"id": "s1", "texto": "x", "estado": "contradicho", "evidencia": "y"}])
    h["novedad"]["precedente"] = {"estado": "no_comprobado", "detalle": "la consulta no devolvió obras"}
    e = {"hipotesis": [h], "corridas": [], "decisiones": []}
    c = {x["comprobacion"]: x for x in K.comprobaciones_deterministas(h, e)}
    assert c["supuestos"]["resultado"] == "falla" and "1 supuestos contradichos" in c["supuestos"]["detalle"]
    assert c["novedad"]["resultado"] == "no_comprobable" and c["novedad"]["detalle"].startswith("No comprobado: la consulta")


# ---------------------------------------------------------------------------
# S-04: la réplica conserva fuenteId
# ---------------------------------------------------------------------------


def test_la_replica_conserva_el_fuente_id_y_lo_pasa_al_resolver_la_cita(monkeypatch):
    al, ctx = _ctx()
    h = _hipotesis(afirmaciones=[_afirmacion(fuenteId="f-A"), _afirmacion(afirmacionId="af-2", fuenteId="f-B", cita="[Bhagunde et al., 2026, sección Results]")])
    h["replicacion"] = {"total": 3, "hechas": 1, "sostienen": 1, "contradicen": 0, "estado": "en_curso", "empezadaEn": 1}
    al.mutar(lambda e: e["hipotesis"].append(h) or True, "prueba")
    resueltas: list[tuple[str, Any]] = []
    monkeypatch.setattr(V, "resolver_cita", lambda cita, frags, fuente_id=None: resueltas.append((cita, fuente_id)) or None)
    vistas: dict[str, Any] = {}

    async def verificar(ctx_, copias, pista, pregunta, rol="juez", rollout_id=None):
        vistas["copias"], vistas["rol"], vistas["rollout_id"] = copias, rol, rollout_id
        return {}

    monkeypatch.setattr(PASOS, "verificar_afirmaciones", verificar)
    sup = CO.Supervisor(al, SimpleNamespace(), ctx.modelos)
    asyncio.run(sup._replicar_paso(ctx, h))
    assert resueltas == [("[A et al., 2025, pág. 3]", "f-A"), ("[Bhagunde et al., 2026, sección Results]", "f-B")]
    assert [a["fuenteId"] for a in vistas["copias"]] == ["f-A", "f-B"], "las copias conservan el id de la fuente"
    assert vistas["rol"] == "replica" and vistas["rollout_id"] == 1, "la trayectoria (hechas) distingue la lectura en la caché"
    assert _hip(al, h)["replicacion"]["hechas"] == 2
    al.cerrar()


# ---------------------------------------------------------------------------
# S-01: parar() corta el trabajo nuevo
# ---------------------------------------------------------------------------


def test_con_parar_el_supervisor_no_arranca_trabajo_nuevo(monkeypatch):
    al, ctx = _ctx()
    h = _hipotesis(estado="aclarando")
    al.mutar(lambda e: e["hipotesis"].append(h) or True, "prueba")
    sup = CO.Supervisor(al, SimpleNamespace(), ctx.modelos)
    aclaradas: list[str] = []

    async def aclarar(ctx_, x):
        aclaradas.append(x["id"])

    monkeypatch.setattr(sup, "_aclarar", aclarar)
    sup.parar()
    asyncio.run(sup._atender_peticiones())
    asyncio.run(sup._vigilar_si_toca())
    asyncio.run(sup._indexar_si_toca())
    assert aclaradas == [] and not hasattr(sup, "_ultima_vigilancia") and not hasattr(sup, "_ultima_indexacion")
    # Sin parar sí atiende.
    sup._parar.clear()
    asyncio.run(sup._atender_peticiones())
    assert aclaradas == [h["id"]]
    al.cerrar()


# ---------------------------------------------------------------------------
# S-09: sinJuez no es un cierre científico
# ---------------------------------------------------------------------------


def test_una_suspension_tecnica_del_juez_no_entra_en_lecciones_ni_en_el_traspaso():
    e, c, it = _estado_cierre()
    e["hipotesis"].append({"id": "h2", "investigacionId": "inv", "titulo": "Hipótesis con juez caído", "estado": "propuesta", "elo": 1400, "revisiones": []})
    e["decisiones"].append({"id": "d2", "investigacionId": "inv", "hipotesisId": "h2", "etapa": "killer_1", "decision": "suspender", "sinJuez": True, "fecha": 1250, "comprobaciones": [{"comprobacion": "supuestos", "resultado": "falla"}], "queHariaFalta": "que el juez responda"})
    e["decisiones"].append({"id": "d3", "investigacionId": "inv", "hipotesisId": "h2", "etapa": "killer_1", "decision": "suspender", "fecha": 1260, "comprobaciones": [{"comprobacion": "sesgo_evidencia", "resultado": "falla"}], "queHariaFalta": "otra fuente"})
    textos = [l["texto"] for l in LEC.generar_al_cerrar(e, c, it, it["revisionRegistro"], 2000)]
    cerradas = [t for t in textos if "Hipótesis con juez caído" in t]
    assert len(cerradas) == 1 and "sesgo evidencia" in cerradas[0] and "supuestos" not in cerradas[0]
    c["estado"], c["terminadaEn"] = "terminada", 5000
    traspaso = T.traspaso_de_corrida(e, "inv")
    linea = next((l for l in traspaso.splitlines() if "Hipótesis cerradas por el Killer" in l), "")
    assert "Hipótesis con juez caído" in linea and "por sesgo evidencia" in linea and "por supuestos" not in linea


# ---------------------------------------------------------------------------
# S-12: auditoría sin respuesta en el dossier
# ---------------------------------------------------------------------------


def test_el_dossier_distingue_la_auditoria_sin_respuesta_del_desacuerdo():
    al, ctx = _ctx()
    h = _hipotesis()
    base = {"investigacionId": "inv", "hipotesisId": h["id"], "etapa": "killer_1", "version": 1, "decision": "descartar_en_contexto", "quien": "juez", "motivo": "m", "comprobaciones": [], "queHariaFalta": ""}
    e = al.estado
    e["hipotesis"].append(h)
    e["decisiones"].extend([
        {**base, "id": "d1", "fecha": 10, "auditoria": {"quien": "auditor", "acuerdo": None, "motivo": "", "fecha": 11, "estado": "no_respondio"}},
        {**base, "id": "d2", "fecha": 20, "auditoria": {"quien": "auditor", "acuerdo": False, "motivo": "discrepo", "fecha": 21}},
        {**base, "id": "d3", "fecha": 30, "auditoria": {"quien": "auditor", "acuerdo": True, "motivo": "ok", "fecha": 31}},
    ])
    texto = texto_dossier(e, h, e["investigaciones"][0], None, 9000)
    assert "sin respuesta del auditor" in texto and texto.count("EN DESACUERDO") == 1 and "de acuerdo. ok" in texto
    al.cerrar()


# ---------------------------------------------------------------------------
# literatura-02: fuentes sin autores con identificador
# ---------------------------------------------------------------------------


def test_las_fuentes_sin_autores_de_openalex_llevan_su_identificador():
    obra = openalex._obra({"id": "https://openalex.org/W123", "doi": "https://doi.org/10.1000/ABC", "title": "T", "authorships": [], "publication_year": 2024, "type": "article", "ids": {}})
    assert obra["referencia"] == FB.referencia_corta([], 2024, identificador="10.1000/abc")
    assert "Sin autor" in obra["referencia"] and "10.1000/abc" in obra["referencia"], obra["referencia"]
    sin_doi = openalex._obra({"id": "https://openalex.org/W123", "title": "T", "authorships": [], "publication_year": 2024, "ids": {}})
    assert "W123" in sin_doi["referencia"]
    con_autores = openalex._obra({"id": "https://openalex.org/W9", "title": "T", "authorships": [{"author": {"display_name": "Ana Kim"}}], "publication_year": 2024, "ids": {}})
    assert "Sin autor" not in con_autores["referencia"]
