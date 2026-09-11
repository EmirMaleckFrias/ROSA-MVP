"""El supervisor y el bucle de cada corrida.

`Supervisor.correr()` es una tarea que vive mientras el servidor:
- Cada dos segundos mira el estado. Para cada corrida viva sin tarea, lanza
  `correr_corrida`. Autoaprueba planes si la corrida lo pide. Atiende lo que
  la investigadora dejo marcado: hipotesis "no puedo juzgar" (las aclara),
  comentarios enviados (los responde), revisiones pedidas, retractaciones a
  recomprobar, replicaciones en curso.
- Al arrancar, lo que quedo a medias por un reinicio se marca (pistas
  fallidas con motivo) y la iteracion retoma en el primer paso pendiente.

`correr_corrida` es el bucle de una corrida:
  sin iteracion o iteracion cerrada -> proponer plan -> esperando_plan
  plan aprobado -> ejecutar pasos en orden (cada paso, sus pistas)
  sin pasos -> cerrar iteracion (resumen, informe, evento, condicion de parada)
Se detiene cuando la corrida pasa a detenida o terminada. Pausada, pausada
por presupuesto o esperando aprobacion: espera sin gastar.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone
from pathlib import Path
import re
import traceback
from typing import Any

from rosa import config, politicas, priorizacion as PR
from rosa.bucle import contexto as T
from rosa.bucle import pasos as PASOS
from rosa.bucle.pasos import Ctx
from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen
from rosa.fuentes import crossref
from rosa.fuentes.base import FuenteNoDisponible
from rosa.gateway import Modelos
from rosa.modulos.contador import ContextoLlamada, PresupuestoAgotado, contexto_actual
from rosa.modulos.firmas import Programas

# Lo que cuesta de verdad cada tipo de paso, en llamadas al modelo, medido en
# la primera corrida real (10 de septiembre de 2026): el cribado de relevancia
# es una llamada por articulo, la extraccion una por fragmento, el juez una
# por afirmacion. El modelo que propone el plan no conoce este coste, asi que
# su cifra se sustituye por esta.
COSTE_POR_TIPO = {"literatura": 70, "ensayos": 4, "extraccion": 60, "verificacion": 80, "novedad": 25, "modelo": 4, "hipotesis": 90, "analisis": 14, "meta": 4, "indicacion": 0}

PLAN_POR_DEFECTO = [
    ("Buscar literatura", "PubMed, Europe PMC y preprints sobre las preguntas abiertas", "literatura", 30),
    ("Extraer afirmaciones con procedencia", "Un fragmento a la vez, cada afirmacion con su cita literal", "extraccion", 40),
    ("Verificar cada afirmacion", "Comprobaciones deterministas y juez", "verificacion", 30),
    ("Actualizar el modelo de mundo", "Hechos sostenidos y preguntas abiertas", "modelo", 5),
    ("Generar y revisar hipotesis", "Nuevas hipotesis a la cola, revision inicial, supuestos y torneo", "hipotesis", 20),
    ("Comprobar novedad", "Open Targets, ClinicalTrials.gov y precedente en OpenAlex", "novedad", 10),
]


class Supervisor:
    def __init__(self, almacen: Almacen, programas: Programas, modelos: Modelos):
        self.almacen = almacen
        self.programas = programas
        self.modelos = modelos
        self.tareas: dict[str, asyncio.Task] = {}
        self._parar = asyncio.Event()

    # -- arranque -------------------------------------------------------------

    def recuperar_tras_reinicio(self) -> None:
        ahora = P.ahora_ms()

        def fn(e: dict[str, Any]) -> bool:
            cambiado = False
            for it in e["iteraciones"]:
                if it["terminadaEn"] is not None:
                    continue
                for p in it["pistas"]:
                    if p["estado"] == "en_curso":
                        p["estado"] = "fallida"
                        p["resumen"] = "Interrumpida por un reinicio de Rosa; el paso se retoma"
                        p["transcripcion"].append({"t": p["ms"], "tipo": "error", "texto": "Interrumpida por un reinicio de Rosa."})
                        cambiado = True
                for paso in it["plan"]:
                    if paso["estado"] == "en_curso":
                        paso["estado"] = "pendiente"
                        cambiado = True
            # Una ejecucion in silico a medias no se repite sola (evitar ejecucion
            # duplicada tras un reinicio): queda como error tecnico con motivo.
            for run in e.get("ejecuciones", []):
                if run["estado"] == "en_curso":
                    run["estado"] = "error_tecnico"
                    run["error"] = "Interrumpida por un reinicio de Rosa. No se repite sola: pide el analisis otra vez si hace falta."
                    run["fin"] = ahora
                    cambiado = True
            for r in e.get("reproducciones", []):
                if r["estado"] == "en_curso":
                    r["estado"] = "error_tecnico"
                    r["_error"] = "Interrumpida por un reinicio"
                    cambiado = True
            return cambiado or False

        self.almacen.mutar(fn, "recuperacion")
        for c in self.almacen.estado["corridas"]:
            if c["estado"] not in ("detenida", "terminada"):
                self.almacen.mutar(lambda e, c=c: A.con_evento(e, c["investigacionId"], "corrida_estado", f"Rosa volvio a arrancar; la corrida {c['numero']} retoma donde estaba", None, ahora) or True, "evento")

    async def correr(self) -> None:
        self.recuperar_tras_reinicio()
        while not self._parar.is_set():
            try:
                self._tick()
                await self._atender_peticiones()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._parar.wait(), timeout=2.0)
        for t in self.tareas.values():
            t.cancel()

    def parar(self) -> None:
        self._parar.set()

    # -- por tick --------------------------------------------------------------

    def _tick(self) -> None:
        e = self.almacen.estado
        ahora = P.ahora_ms()
        for c in e["corridas"]:
            if c["estado"] in ("detenida", "terminada"):
                continue
            t = self.tareas.get(c["id"])
            if t is None or t.done():
                if t is not None and t.done() and t.exception():
                    traceback.print_exception(t.exception())
                self.tareas[c["id"]] = asyncio.create_task(self.correr_corrida(c["id"]), name=f"corrida-{c['id']}")
        # Autoaprobacion de planes y segundos de reloj.

        def fn(e2: dict[str, Any]) -> bool:
            cambiado = False
            for c in e2["corridas"]:
                if c["estado"] in ("detenida", "terminada"):
                    continue
                seg = round((ahora - c["empezadaEn"]) / 1000)
                if seg != c["gasto"]["segundos"] and seg % 5 == 0:
                    c["gasto"]["segundos"] = seg
                    cambiado = True
                if c["estado"] == "esperando_plan" and c["autoAprobarPlanSegundos"] is not None:
                    it = A.iteracion_actual_de(e2, c)
                    if it and not it["planAprobado"] and ahora - it["planPropuestoEn"] >= c["autoAprobarPlanSegundos"] * 1000:
                        it["planAprobado"] = True
                        it["empezadaEn"] = ahora
                        c["estado"] = "en_marcha"
                        A.con_evento(e2, c["investigacionId"], "corrida_estado", f"Plan de la iteracion {it['numero']} autoaprobado tras {c['autoAprobarPlanSegundos']} s sin respuesta", None, ahora)
                        cambiado = True
                if c["estado"] == "esperando_aprobacion":
                    pendientes = any(s["corridaId"] == c["id"] and s["estado"] == "pendiente" for s in e2["solicitudes"]) or any(i["corridaId"] == c["id"] and i["estado"] == "pendiente" and i["tipo"] != "modelo_bloqueado" for i in e2["incidencias"])
                    if not pendientes:
                        c["estado"] = "en_marcha"
                        cambiado = True
            return cambiado or False

        self.almacen.mutar(fn, "tick")

    async def _atender_peticiones(self) -> None:
        """Lo que la investigadora dejo marcado y no requiere corrida en marcha."""
        e = self.almacen.estado
        for h in list(e["hipotesis"]):
            corrida = A.ultima_corrida_de(e, h["investigacionId"])
            if not corrida:
                continue
            ctx = self._ctx(corrida)
            if h["estado"] == "aclarando":
                await self._aclarar(ctx, h)
            if h.get("_comentariosNuevos"):
                await self._responder_comentarios(ctx, h)
            if h.get("replicacion") and h["replicacion"]["estado"] == "en_curso":
                await self._replicar_paso(ctx, h)
            if h.get("_reformularPedida") is not None and h["estado"] == "refinar":
                await self._reformular_por_persona(ctx, h)
            if h.get("_revisionPedida") and (corrida["estado"] in ("detenida", "terminada", "esperando_plan") or A.iteracion_actual_de(e, corrida) is None):
                # Una revision pedida con la corrida parada no espera al siguiente paso
                # de hipotesis: revision inicial, supuestos y Killer ahora.
                texto_af, _ = T.afirmaciones_sostenidas(corrida.get("_afirmaciones", []))
                pista = ctx.pista(None, "modelo", f"Revision pedida: {h['titulo'][:60]}", "Opus 5 (Killer)")
                try:
                    await PASOS._revisar_hipotesis(ctx, h, texto_af[:8000], pista)
                    pista.cerrar("Revision y Killer terminados")
                except Exception as ex:  # noqa: BLE001
                    traceback.print_exc()
                    pista.fallar(f"La revision fallo: {str(ex)[:160]}")
                finally:
                    self.almacen.mutar(lambda e2: (next((x for x in e2["hipotesis"] if x["id"] == h["id"]), {}).pop("_revisionPedida", None), True)[1], "revision")
                return
            if h.get("_analisisPedido") and (corrida["estado"] in ("detenida", "terminada", "esperando_plan") or A.iteracion_actual_de(e, corrida) is None):
                # Con la corrida parada, el analisis pedido no espera a un paso del plan.
                from rosa.bucle import analisis as AN

                p = h["_analisisPedido"]
                pista = ctx.pista(None, "modelo", f"Analisis pedido: {h['titulo'][:60]}", "Sandbox")
                try:
                    await AN.analizar_hipotesis(ctx, h, p["datasetId"], p.get("pregunta", ""), pista)
                except Exception as ex:  # noqa: BLE001
                    traceback.print_exc()
                    self.almacen.mutar(lambda e2: (next(x for x in e2["hipotesis"] if x["id"] == h["id"]).pop("_analisisPedido", None), True)[1], "analisis")
                    pista.fallar(f"El analisis fallo: {str(ex)[:160]}")
                else:
                    pista.cerrar("Analisis terminado")
                return
        for rep in [r for r in e.get("reproducciones", []) if r["estado"] == "pendiente"]:
            corrida = A.ultima_corrida_de(e, rep["investigacionId"])
            if corrida and (corrida["estado"] in ("detenida", "terminada", "esperando_plan") or A.iteracion_actual_de(e, corrida) is None):
                from rosa.bucle import analisis as AN

                ctx = self._ctx(corrida)
                pista = ctx.pista(None, "modelo", f"Reproduccion: {rep['referencia'][:60]}", "Sandbox")
                try:
                    await AN.reproducir(ctx, rep, pista)
                except Exception as ex:  # noqa: BLE001
                    traceback.print_exc()
                    pista.fallar(f"La reproduccion fallo: {str(ex)[:160]}")
                    self.almacen.mutar(lambda e2: AN._estado_rep(e2, rep["id"], "error_tecnico", None, None, str(ex)[:200]), "reproduccion")
                else:
                    pista.cerrar("Reproduccion terminada")
                return
        for inv in list(e["investigaciones"]):
            if inv.get("_recomprobarRetracciones"):
                await self._recomprobar_retracciones(inv)
        for cambio in list(e.get("aprendizaje", [])):
            if cambio.get("_evaluar"):
                await self._evaluar_cambio(cambio)
                return
            if cambio.get("_promover"):
                self._promover_programa(cambio)
        await self._completar_en_llano()

    async def _reformular_por_persona(self, ctx: Ctx, h: dict[str, Any]) -> None:
        """La persona pidio refinar: Rosa reformula como version nueva con su
        nota, y el Killer vuelve a juzgar la version nueva."""
        nota = h.get("_reformularPedida") or "La persona pidio refinarla"
        texto_af, _ = T.afirmaciones_sostenidas(ctx.corrida().get("_afirmaciones", []))
        pista = ctx.pista(None, "modelo", f"Reformular a peticion: {h['titulo'][:60]}", "GPT-6 Astra + Opus 5")
        try:
            ok = await PASOS._reformular(ctx, h, f"Persona: {nota}", config.QUIEN_ROSA, pista)
            if ok:
                nueva = next((y for y in self.almacen.estado["hipotesis"] if y["id"] == h["id"]), None)
                if nueva:
                    await PASOS._killer(ctx, nueva, texto_af[:8000], pista, profundidad=1)
            pista.cerrar("Reformulada y revisada" if ok else "No se pudo reformular")
        except Exception as ex:  # noqa: BLE001
            traceback.print_exc()
            pista.fallar(f"Fallo al reformular: {str(ex)[:160]}")
        finally:
            self.almacen.mutar(lambda e2: (next((x for x in e2["hipotesis"] if x["id"] == h["id"]), {}).pop("_reformularPedida", None), True)[1], "reformular")

    async def _evaluar_cambio(self, cambio: dict[str, Any]) -> None:
        """Evaluacion de un criterio propuesto (nivel 2) sobre el conjunto
        reservado: las hipotesis con decision humana de aceptar o descartar.
        Se corre el Killer con y sin el criterio y se mide el acuerdo con
        la persona (avanzar = aceptar; descartar o reformular = descartar).
        La cifra va al registro; la promocion sigue siendo de la persona."""
        e = self.almacen.estado
        reservado = [h for h in e["hipotesis"] if h["estado"] in ("aceptada", "descartada") and any(r["quien"] != config.QUIEN_ROSA and r["accion"] in ("aceptada", "descartada") for r in h["revisiones"])][:6]
        ahora = P.ahora_ms()
        if not reservado:
            self.almacen.mutar(lambda e2: _fijar_evaluacion(e2, cambio["id"], {"conjunto": "hipotesis con decision humana", "casos": 0, "antes": None, "despues": None, "nota": "Sin conjunto reservado todavia: hacen falta hipotesis aceptadas o descartadas por una persona"}, ahora), "aprendizaje")
            return
        corrida = A.ultima_corrida_de(e, cambio.get("investigacionId") or reservado[0]["investigacionId"]) or A.ultima_corrida_de(e, reservado[0]["investigacionId"])
        if not corrida:
            return
        ctx = self._ctx(corrida)
        from rosa import killer as K

        async def acuerdo_con(criterios: list[str]) -> float:
            aciertos = 0
            for h in reservado:
                inv = next(i for i in e["investigaciones"] if i["id"] == h["investigacionId"])
                deterministas = K.comprobaciones_deterministas(h, e)
                try:
                    pred = await ctx.llamar("juez", self.programas.killer, objetivo=inv["objetivo"], mision=PASOS._texto_mision(inv), hipotesis=T.hipotesis_texto(h) + "\n" + K.texto_tarjeta(h), afirmaciones="\n".join(f"- [{a['veredicto']}, {a['tipo']}] {a['texto']} {a['cita']}" for a in h["afirmaciones"]) or "Ninguna", supuestos="\n".join(f"- [{s['estado']}] {s['texto']}" for s in h["supuestos"]) or "Sin supuestos", modelo_de_mundo=T.modelo_de_mundo(e["hechos"], h["investigacionId"], maximo=30), comprobaciones_deterministas="\n".join(f"- {c['comprobacion']}: {c['resultado']}. {c['detalle']}" for c in deterministas), criterios_revision="\n".join(criterios))
                    comprobaciones = K.fusionar(deterministas, [{"comprobacion": c.comprobacion, "resultado": c.resultado, "detalle": c.detalle} for c in pred.revision.comprobaciones])
                    decision, _ = K.decidir(comprobaciones, bool((h.get("tarjeta") or {}).get("prediccionFalsable")), 1)
                except Exception:  # noqa: BLE001
                    continue
                humana = h["estado"] == "aceptada"
                if (decision == "avanzar") == humana:
                    aciertos += 1
            return round(aciertos / len(reservado), 3)

        try:
            sin = [c for c in e["criteriosRevision"] if c != cambio["descripcion"]]
            antes = await acuerdo_con(sin)
            despues = await acuerdo_con(sin + [cambio["descripcion"]])
            nota = "Mejora el acuerdo con las decisiones humanas" if despues > antes else ("Empeora el acuerdo" if despues < antes else "No cambia el acuerdo")
        except Exception as ex:  # noqa: BLE001
            antes, despues, nota = None, None, f"La evaluacion fallo: {str(ex)[:120]}"
        self.almacen.mutar(lambda e2: _fijar_evaluacion(e2, cambio["id"], {"conjunto": "hipotesis con decision humana", "casos": len(reservado), "antes": antes, "despues": despues, "nota": nota}, ahora), "aprendizaje")

    def _promover_programa(self, cambio: dict[str, Any]) -> None:
        """Un programa optimizado por GEPA promovido por una persona pasa de
        `mlruns/candidatos/` a `mlruns/optimizados/` y se carga en el
        siguiente arranque. El anterior queda como `.anterior` para revertir."""
        import shutil

        nombre = cambio["origen"].split(":")[-1]
        origen = Path(config.RAIZ) / "mlruns" / "candidatos" / f"{nombre}.json"
        destino = Path(config.RAIZ) / "mlruns" / "optimizados" / f"{nombre}.json"
        nota = ""
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            if destino.exists():
                shutil.copy(destino, destino.with_suffix(".json.anterior"))
            if origen.exists():
                shutil.copy(origen, destino)
                nota = f"Programa {nombre} promovido; se carga al reiniciar Rosa"
            else:
                nota = f"No se encontro el candidato {origen.name}; nada que promover"
        except Exception as ex:  # noqa: BLE001
            nota = f"No se pudo promover: {str(ex)[:120]}"

        def fn(e: dict[str, Any]) -> bool:
            c = next((x for x in e.get("aprendizaje", []) if x["id"] == cambio["id"]), None)
            if not c:
                return False
            c.pop("_promover", None)
            c["evaluacion"] = {**(c.get("evaluacion") or {"conjunto": "", "casos": 0, "antes": None, "despues": None}), "nota": nota}
            return True

        self.almacen.mutar(fn, "aprendizaje")

    async def _explicar_en_llano(self, ctx: Ctx, inv: dict[str, Any], resumen: str, hechos: list[dict], hipotesis: list[dict], sin_comprobar: list[dict]) -> dict[str, Any] | None:
        """El resumen de la iteracion en lenguaje llano, con la estructura de los
        Plain Language Summary de Cochrane. Si el modelo falla, se queda sin
        resumen (la pantalla lo dice) y no se inventa nada."""
        e = self.almacen.estado
        c = ctx.corrida()
        propias = [h for h in e["hipotesis"] if h["investigacionId"] == inv["id"]]
        conclusiones = []
        for h in propias:
            k = h.get("conclusion")
            if k:
                cambio = f" (antes: {k['cambio']['de']['certeza']}, {k['cambio']['de']['direccion']})" if k.get("cambio") else ""
                conclusiones.append(f"- {h['titulo']}: certeza {k['certeza']}, direccion {k['direccion']}{cambio}")
        afs = c.get("_afirmaciones", [])
        por_veredicto: dict[str, int] = {}
        for a in afs:
            if a["iteracion"] == ctx.numero:
                por_veredicto[a["veredicto"]] = por_veredicto.get(a["veredicto"], 0) + 1
        consultas = [q for q in c["busqueda"]["consultas"] if q.get("iteracion") == ctx.numero]
        it = ctx.iteracion() if ctx.iteracion_id else None
        fallidas = [p["titulo"] + ": " + p["resumen"] for p in (it["pistas"] if it else []) if p["estado"] == "fallida"]
        busqueda = "\n".join(f"- {q['base']}: {q['resultados']} resultados" for q in consultas) or "- Sin consultas nuevas"
        busqueda += "\nAfirmaciones verificadas en esta iteracion: " + (", ".join(f"{v} {k}" for k, v in por_veredicto.items()) or "ninguna")
        busqueda += "\nFuentes que no respondieron: " + ("; ".join(fallidas) if fallidas else "ninguna")
        try:
            pred = await ctx.llamar(
                "cerebro",
                self.programas.en_llano,
                objetivo=inv["objetivo"],
                resumen_tecnico=resumen,
                hechos_nuevos="\n".join(f"- {h['enunciado']}" for h in hechos) or "Ninguno",
                hipotesis_nuevas="\n".join(f"- {h['titulo']}: {h['enunciado']} Para que sirve: {h['relevancia']['justificacion']}" for h in hipotesis) or "Ninguna",
                sin_comprobar="\n".join(f"- {x.get('texto') or x.get('titulo')}" for x in sin_comprobar) or "Nada",
                conclusiones="\n".join(conclusiones) or "Ninguna hipotesis todavia",
                busqueda=busqueda,
            )
            r = pred.resumen
            return {
                "titulo": r.titulo.strip(),
                "mensajesClave": list(r.mensajes_clave)[:3],
                "queBuscaba": r.que_buscaba,
                "queHizo": r.que_hizo,
                "queEncontro": list(r.que_encontro),
                "limitaciones": r.limitaciones,
                "cambios": list(r.cambios),
                "quePropone": list(r.que_propone),
                "queFalta": r.que_falta,
                "queTeToca": r.que_te_toca,
                "alDia": {"fechaBusqueda": max((q["fecha"] for q in c["busqueda"]["consultas"]), default=None), "fuentesSinRespuesta": fallidas},
                "terminos": [{"termino": t.termino, "explicacion": t.explicacion} for t in r.terminos],
            }
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return None

    async def _hipotesis_en_llano(self, ctx: Ctx, h: dict[str, Any]) -> None:
        c = h["comprobacion"]
        try:
            pred = await ctx.llamar("volumen", self.programas.hipotesis_en_llano, titulo=h["titulo"], enunciado=h["enunciado"], mecanismo=h["mecanismo"], comprobacion=f"Biomarcador: {c['biomarcador']}. Cohorte: {c['cohorte']}. Diseno: {c['diseno']}", relevancia=h["relevancia"]["justificacion"])
            texto = pred.explicacion.strip()
        except Exception as ex:  # noqa: BLE001
            texto = ""
            traceback.print_exc()

        def fn(e: dict[str, Any]) -> bool:
            x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
            if not x:
                return False
            x["enLlano"] = texto or None
            x["_enLlanoIntentado"] = True
            return True

        self.almacen.mutar(fn, "en_llano")

    async def _proponer_experimento(self, ctx: Ctx, h: dict[str, Any]) -> None:
        """El experimento o analisis que comprobaria la hipotesis. Queda como
        `experimento` en estado 'propuesto'; la persona lo asigna a un
        laboratorio o registra los datos cuando llegan."""
        inv = next((i for i in self.almacen.estado["investigaciones"] if i["id"] == h["investigacionId"]), None)
        try:
            pred = await ctx.llamar(
                "cerebro",
                self.programas.experimento,
                hipotesis=T.hipotesis_texto(h),
                afirmaciones="\n".join(f"- [{a['veredicto']}] {a['texto']} {a['cita']}" for a in h["afirmaciones"]) or "Ninguna (hipotesis humana)",
                limites="; ".join(inv["limites"]) if inv and inv["limites"] else "Ninguno declarado",
            )
            x = pred.experimento
            pasos = [p.strip().lstrip("0123456789.) ").strip() for p in x.protocolo if p.strip()]
            experimento = {
                "protocolo": "\n".join(f"{i + 1}. {p}" for i, p in enumerate(pasos)),
                "ensayo": x.ensayo.strip(),
                "confirma": x.resultado_que_confirma.strip(),
                "refuta": x.resultado_que_refuta.strip(),
                "controles": (x.controles or "").strip(),
                "tamanoMuestral": (x.tamano_muestral or "").strip(),
                "alternativa": (x.alternativa or "").strip(),
                "decisionQueCambia": (x.decision_que_cambia or "").strip(),
                "costeEstimado": x.coste_estimado.strip(),
                "laboratorio": None,
                "estado": "propuesto",
                "ficheroDatos": None,
                "analisisPedido": x.analisis_pedido.strip(),
            }
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            experimento = None

        def fn(e: dict[str, Any]) -> bool:
            y = next((z for z in e["hipotesis"] if z["id"] == h["id"]), None)
            if not y:
                return False
            y["_experimentoIntentado"] = True
            if experimento and not y.get("experimento"):
                y["experimento"] = experimento
                y["procedencia"]["registro"].append("experimento propuesto por Rosa (protocolo, ensayo, controles, criterios, coste)")
                A.recalcular_bloqueos(e, y)
            return True

        self.almacen.mutar(fn, "experimento")

    async def _concluir_hipotesis(self, ctx: Ctx, h: dict[str, Any]) -> None:
        """La conclusion provisional de Rosa sobre la hipotesis con lo que hay.
        La escribe el juez. Se rehace al cerrar cada iteracion."""
        try:
            pred = await ctx.llamar(
                "juez",
                self.programas.concluir,
                hipotesis=T.hipotesis_texto(h),
                afirmaciones="\n".join(f"- [{a['veredicto']}, {a['tipo']}, clase {a.get('clase', 'literatura')}{', SINTETICO: no cuenta como evidencia' if a.get('sintetico') else ''}{', cohorte ' + a['cohorte'] if a.get('cohorte') else ''}] {a['texto']} {a['cita']}" for a in h["afirmaciones"]) or "Ninguna",
                supuestos="\n".join(f"- [{s['estado']}] {s['texto']} ({s['evidencia']})" for s in h["supuestos"]) or "Sin supuestos evaluados",
                partidos="\n".join(f"- {p['resultado']} por {p['ejeDecisivo']}: {p['resumenDebate']}" for p in h["partidos"]) or "Sin partidos todavia",
                novedad="; ".join(f"{k}: {v['detalle']}" for k, v in h["novedad"].items()) + f". Cohortes distintas entre las fuentes: {len(PR.cohortes_de(h))}" + (f" ({', '.join(PR.cohortes_de(h))})" if PR.cohortes_de(h) else ""),
                revisiones_humanas=T.revisiones_humanas(h) + (f"\nKiller: {h.get('decisionKiller')}" if h.get("decisionKiller") else ""),
                resultado_experimental=T.resultado_experimental(h),
            )
            c = pred.conclusion
            # La base se cuenta de forma determinista, no la estima el modelo. Lo
            # sintetico no cuenta como evidencia.
            sostenidas = [a for a in h["afirmaciones"] if a["veredicto"] in ("sostenida", "parcial") and not a.get("sintetico")]
            fuentes = {f["referencia"] for f in h["procedencia"]["fuentes"]}
            anterior = h.get("conclusion")
            cambio = None
            if anterior and (anterior.get("certeza") != c.certeza or anterior.get("direccion") != c.direccion):
                cambio = {"de": {"certeza": anterior.get("certeza"), "direccion": anterior.get("direccion"), "iteracion": anterior.get("iteracion")}, "motivo": (c.factores[0].explicacion.strip() if c.factores else "")}
            no_comprobado = [f"{k}: {v['detalle']}" for k, v in h["novedad"].items() if str(v.get("detalle", "")).startswith("No comprobado") and k != "agora"]
            consultas = ctx.corrida()["busqueda"]["consultas"]
            conclusion = {
                "certeza": c.certeza,
                "direccion": c.direccion,
                "hipotesisBreve": c.hipotesis_breve.strip(),
                "enunciado": frase_plantilla(c.direccion, c.certeza, c.hipotesis_breve.strip() or h["titulo"]),
                "conclusion": c.conclusion.strip(),
                "factores": [{"factor": f.factor, "efecto": f.efecto, "explicacion": f.explicacion.strip()} for f in c.factores][:8],
                "base": {"afirmaciones": len(h["afirmaciones"]), "sostenidas": len(sostenidas), "fuentes": len(fuentes), "datos": sum(1 for a in sostenidas if a["tipo"] == "dato"), "interpretaciones": sum(1 for a in sostenidas if a["tipo"] == "interpretacion")},
                "aFavor": list(c.a_favor),
                "enContra": list(c.en_contra),
                "loMasFragil": c.lo_mas_fragil.strip(),
                "subiria": c.subiria.strip(),
                "bajaria": c.bajaria.strip(),
                "noComprobado": no_comprobado,
                "cambio": cambio,
                "fechaBusqueda": max((q["fecha"] for q in consultas), default=None),
                "fecha": P.ahora_ms(),
                "iteracion": ctx.numero,
            }
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            conclusion = None

        def fn(e: dict[str, Any]) -> bool:
            y = next((z for z in e["hipotesis"] if z["id"] == h["id"]), None)
            if not y:
                return False
            y["_conclusionIntentada"] = ctx.numero
            if conclusion:
                y["conclusion"] = conclusion
                if conclusion.get("cambio"):
                    # Nivel 1 del aprendizaje: cambio lo que Rosa cree de esta hipotesis. Automatico y registrado.
                    de = conclusion["cambio"]["de"]
                    e.setdefault("aprendizaje", []).append(P.nuevo_cambio_aprendizaje(y["investigacionId"], 1, "creencia", f"{y['titulo'][:80]}: de {de.get('certeza')}/{de.get('direccion')} a {conclusion['certeza']}/{conclusion['direccion']}. {conclusion['cambio']['motivo'][:160]}", f"hipotesis:{y['id']}", "aplicado", config.QUIEN_ROSA, conclusion["fecha"]))
            return True

        self.almacen.mutar(fn, "conclusion")

    async def _evaluar_resultado(self, ctx: Ctx, h: dict[str, Any]) -> None:
        """Cierra el loop: los datos del laboratorio se comparan con los
        criterios congelados en el prerregistro, el veredicto entra como
        afirmacion de tipo dato con su trayectoria, y la conclusion se rehace."""
        from rosa import datos as D

        from rosa.dossier import APRENDIZAJE_POR_RESULTADO

        x = h["experimento"]
        ruta = D.ruta_de(h["id"], x.get("ficheroDatos") or "")
        ahora = P.ahora_ms()
        derivada_texto = None
        if ruta is None or not ruta.exists():
            resultado = {"veredicto": "no_evaluable", "clasificacion": "fallo_tecnico", "resultado": "No se encontro el fichero de datos en el servidor.", "motivo": f"Se registro el nombre '{x.get('ficheroDatos')}' pero el fichero no se subio. Sube el fichero desde la ficha.", "limitaciones": "", "cifras": [], "exploratorio": "", "fecha": ahora, "fichero": x.get("ficheroDatos")}
        else:
            resumen, muestra = await asyncio.to_thread(D.resumir, ruta)
            try:
                pred = await ctx.llamar(
                    "juez",
                    self.programas.evaluar_resultado,
                    hipotesis=T.hipotesis_texto(h),
                    prerregistro=f"Protocolo:\n{x['protocolo']}\n\nEnsayo: {x['ensayo']}\n\nControles: {x.get('controles') or 'no declarados'}\nTamano muestral previsto: {x.get('tamanoMuestral') or 'no declarado'}\n\nCONFIRMA si: {x.get('confirma') or '(no separado; ver ensayo)'}\nREFUTA si: {x.get('refuta') or '(no separado; ver ensayo)'}",
                    analisis_pedido=x.get("analisisPedido") or "Ninguno en particular: aplicar los criterios prerregistrados.",
                    resumen_datos=resumen,
                    muestra_datos=muestra,
                )
                r = pred.resultado
                dm = r.dimensiones
                resultado = {"veredicto": r.veredicto, "clasificacion": r.clasificacion, "dimensiones": {"falloTecnico": bool(dm.fallo_tecnico), "inconcluso": bool(dm.inconcluso), "efectoPequenoInterpretable": bool(dm.efecto_pequeno_interpretable), "efectoPredicho": bool(dm.efecto_predicho), "efectoInesperado": bool(dm.efecto_inesperado), "toxicidad": bool(dm.toxicidad), "nota": dm.nota.strip()}, "resultado": r.resultado.strip(), "motivo": r.motivo.strip(), "limitaciones": r.limitaciones.strip(), "cifras": [{"nombre": c.nombre, "valor": c.valor} for c in r.cifras][:12], "exploratorio": r.exploratorio.strip(), "fecha": ahora, "fichero": ruta.name}
                if r.clasificacion == "correccion_contexto" and r.contexto_corregido.strip():
                    try:
                        pd = await ctx.llamar("cerebro", self.programas.derivar, hipotesis=T.hipotesis_texto(h), resultado=f"{r.resultado} Contexto corregido: {r.contexto_corregido}")
                        derivada_texto = pd.derivada
                    except Exception:  # noqa: BLE001
                        traceback.print_exc()
            except Exception as ex:  # noqa: BLE001
                traceback.print_exc()
                resultado = {"veredicto": "no_evaluable", "clasificacion": "fallo_tecnico", "resultado": "El juez no pudo evaluar los datos.", "motivo": str(ex)[:300], "limitaciones": "", "cifras": [], "exploratorio": "", "fecha": ahora, "fichero": ruta.name}
        clasificacion = resultado.get("clasificacion") or "inconcluso"
        resultado["accionTomada"] = APRENDIZAJE_POR_RESULTADO.get(clasificacion, "")
        # Un resultado prueba la version que se prerregistro; si la hipotesis cambio
        # despues, se dice y la conclusion actual lo tiene en cuenta.
        version_probada = x.get("versionPrerregistrada") or h.get("version", 1)
        resultado["versionProbada"] = version_probada
        resultado["compatibleConActual"] = version_probada == h.get("version", 1)
        if not resultado["compatibleConActual"]:
            resultado["limitaciones"] = (resultado.get("limitaciones") or "") + f" El resultado probo la version {version_probada}; la hipotesis esta en la version {h.get('version', 1)}: comprobar que la prediccion sigue siendo la misma."
        quien = self.modelos.juez.model

        def fn(e: dict[str, Any]) -> bool:
            y = next((z for z in e["hipotesis"] if z["id"] == h["id"]), None)
            if not y or not y.get("experimento"):
                return False
            y["experimento"]["resultado"] = resultado
            y["_resultadoEvaluado"] = True
            fecha_txt = datetime.fromtimestamp(ahora / 1000).strftime("%d/%m/%Y")
            if clasificacion in ("apoyo_reproducido", "negativo_interpretable", "inconcluso", "correccion_contexto") and resultado["veredicto"] != "no_evaluable":
                cita = f"[Datos del laboratorio: {resultado['fichero']}, {fecha_txt}]"
                y["afirmaciones"].append({"texto": resultado["resultado"], "cita": cita, "veredicto": "sostenida", "motivo": f"Cifra calculada de los datos del laboratorio contra el prerregistro: {resultado['veredicto']} ({clasificacion.replace('_', ' ')}).", "entidadDistinta": False, "tipo": "dato", "clase": "observacion_original", "sintetico": False, "trayectoria": {"id": resultado["fichero"], "celda": 0}, "fragmento": resultado["motivo"]})
                y["evidenciaEstadistica"] = "fuerte" if clasificacion == "apoyo_reproducido" else ("moderada" if clasificacion == "negativo_interpretable" else "debil")
            # Que hace Rosa con cada clase de resultado (taxonomia de retorno).
            if clasificacion == "fallo_tecnico":
                y["experimento"]["estado"] = "asignado"  # se puede repetir; la hipotesis no cambia
                y["experimento"]["ficheroDatos"] = None
            elif clasificacion == "toxicidad_inviabilidad":
                t = y.get("tarjeta") or P.tarjeta_vacia()
                t["riesgos"] = (t.get("riesgos") or []) + [f"Toxicidad o inviabilidad observada en el laboratorio ({fecha_txt}): {resultado['resultado'][:120]}"]
                y["tarjeta"] = t
                y["decisionKiller"] = "suspender"
                y["revisiones"].append({"fecha": ahora, "quien": quien, "accion": "suspendida", "nota": "Toxicidad o inviabilidad: la via de intervencion se cierra en este contexto", "aCiegas": False})
            elif clasificacion == "negativo_interpretable":
                y["hallazgos"].append({"id": P.nuevo_id("hal"), "tipo": "valor_contradice_fuente", "resumen": "El laboratorio devolvio un negativo interpretable", "razonamiento": resultado["resultado"], "estado": "abierto", "respuestaDeRosa": None})
            elif clasificacion == "correccion_contexto":
                y["decisionKiller"] = "suspender"
                y["revisiones"].append({"fecha": ahora, "quien": quien, "accion": "suspendida", "nota": "Correccion de contexto: el efecto aparece en otro contexto; se crea una hipotesis derivada", "aCiegas": False})
                if derivada_texto is not None:
                    d = derivada_texto
                    nueva = P.nueva_hipotesis(y["investigacionId"], ctx.numero, ahora, titulo=d.titulo.strip(), enunciado=d.enunciado.strip(), mecanismo=d.mecanismo.strip(), comprobacion={"biomarcador": d.biomarcador, "cohorte": d.cohorte, "diseno": d.diseno}, cluster=y["cluster"], derivadaDe=y["id"], relevancia={"justificacion": f"Derivada de '{y['titulo'][:60]}' por correccion de contexto del laboratorio: {d.que_cambio}", "votoHumano": None}, afirmaciones=[a for a in y["afirmaciones"] if a.get("clase") == "observacion_original"][-1:])
                    nueva["procedencia"] = P.procedencia_vacia(f"Hipotesis derivada por correccion de contexto tras el resultado del laboratorio del {fecha_txt}. {d.que_cambio}", ahora)
                    e["hipotesis"].append(nueva)
                    resultado["hipotesisDerivadaId"] = nueva["id"]
                    e.setdefault("aprendizaje", []).append(P.nuevo_cambio_aprendizaje(y["investigacionId"], 1, "hipotesis_derivada", f"Correccion de contexto: '{y['titulo'][:60]}' deriva en '{nueva['titulo'][:60]}'", f"resultado:{y['id']}", "aplicado", quien, ahora))
                    A.con_evento(e, y["investigacionId"], "hipotesis_nueva", f"Hipotesis derivada por correccion de contexto: {nueva['titulo'][:80]}", f"#/investigaciones/{y['investigacionId']}/hipotesis/{nueva['id']}", ahora)
            A.registrar_decision(e, y, "retorno", "avanzar" if clasificacion == "apoyo_reproducido" else ("suspender" if clasificacion in ("toxicidad_inviabilidad", "correccion_contexto") else ("reformular" if clasificacion == "negativo_interpretable" else "avanzar")), f"Retorno del laboratorio: {clasificacion.replace('_', ' ')}. {resultado['resultado'][:200]}", quien, ahora)
            e.setdefault("aprendizaje", []).append(P.nuevo_cambio_aprendizaje(y["investigacionId"], 1, "creencia", f"Resultado del laboratorio ({clasificacion.replace('_', ' ')}) para '{y['titulo'][:60]}': {resultado['accionTomada'][:160]}", f"resultado:{y['id']}", "aplicado", quien, ahora))
            y["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "revisor", "texto": f"Datos del laboratorio evaluados contra el prerregistro: {resultado['veredicto']} ({clasificacion.replace('_', ' ')}). {resultado['resultado']} Que hace Rosa: {resultado['accionTomada']}", "creadoEn": ahora})
            y["procedencia"]["registro"].append(f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} datos {resultado['fichero']} evaluados: {resultado['veredicto']} / {clasificacion}")
            y.pop("_conclusionIntentada", None)
            A.recalcular_bloqueos(e, y)
            A.con_evento(e, h["investigacionId"], "revision_automatica", f"Datos del laboratorio evaluados ({clasificacion.replace('_', ' ')}): {h['titulo'][:80]}", f"#/investigaciones/{h['investigacionId']}/hipotesis/{h['id']}", ahora)
            return True

        self.almacen.mutar(fn, "resultado_experimento")
        y = next((z for z in self.almacen.estado["hipotesis"] if z["id"] == h["id"]), None)
        if y:
            await self._concluir_hipotesis(ctx, y)

    async def _completar_en_llano(self) -> None:
        """Rellena lo que falte: hipotesis sin version en llano e iteraciones
        cerradas sin resumen en llano (las anteriores a esta funcion). Una
        cosa por tick, para no competir con la corrida."""
        e = self.almacen.estado
        for h in e["hipotesis"]:
            x = h.get("experimento")
            if x and x.get("estado") == "datos_recibidos" and not h.get("_resultadoEvaluado"):
                corrida = A.ultima_corrida_de(e, h["investigacionId"])
                if corrida:
                    await self._evaluar_resultado(self._ctx(corrida), h)
                    return
            if h.get("enLlano") is None and not h.get("_enLlanoIntentado"):
                corrida = A.ultima_corrida_de(e, h["investigacionId"])
                if corrida:
                    await self._hipotesis_en_llano(self._ctx(corrida), h)
                    return
            if h.get("conclusion") is None and not h.get("_conclusionIntentada"):
                corrida = A.ultima_corrida_de(e, h["investigacionId"])
                if corrida:
                    await self._concluir_hipotesis(self._ctx(corrida), h)
                    return
            if h.get("experimento") is None and not h.get("_experimentoIntentado") and h["estado"] != "descartada":
                corrida = A.ultima_corrida_de(e, h["investigacionId"])
                if corrida:
                    await self._proponer_experimento(self._ctx(corrida), h)
                    return
            if h.get("tarjeta") is None and not h.get("_tarjetaIntentada") and h["estado"] != "descartada":
                corrida = A.ultima_corrida_de(e, h["investigacionId"])
                if corrida:
                    await PASOS._completar_tarjeta(self._ctx(corrida), h, None)
                    return
        for inv in e["investigaciones"]:
            if inv.get("mision") is None and not inv.get("_misionIntentada"):
                corrida = A.ultima_corrida_de(e, inv["id"])
                if corrida:
                    await self._proponer_mision(self._ctx(corrida), inv)
                    return
        for it in e["iteraciones"]:
            if it["terminadaEn"] is not None and it["resumen"] and it.get("resumenLlano") is None and not it.get("_llanoIntentado"):
                c = next((x for x in e["corridas"] if x["id"] == it["corridaId"]), None)
                inv = next((i for i in e["investigaciones"] if c and i["id"] == c["investigacionId"]), None)
                if not c or not inv:
                    continue
                ctx = Ctx(self.almacen, self.programas, self.modelos, c["id"], inv["id"], it["id"], it["numero"])
                hechos = [h for h in e["hechos"] if h["investigacionId"] == inv["id"] and it["empezadaEn"] <= h["actualizadoEn"] <= it["terminadaEn"] and h["historial"] and h["historial"][0]["quien"] == config.QUIEN_ROSA]
                hip = [h for h in e["hipotesis"] if h["investigacionId"] == inv["id"] and h["iteracion"] == it["numero"] and h["origen"] == "rosa"]
                llano = await self._explicar_en_llano(ctx, inv, it["resumen"], hechos, hip, [p for p in it["plan"] if p["estado"] in ("fallido", "omitido")])

                def fn(e2: dict[str, Any], it=it, llano=llano) -> bool:
                    x = next((y for y in e2["iteraciones"] if y["id"] == it["id"]), None)
                    if not x:
                        return False
                    x["_llanoIntentado"] = True
                    if llano:
                        x["resumenLlano"] = llano
                    return True

                self.almacen.mutar(fn, "en_llano")
                return

    def _ctx(self, corrida: dict[str, Any]) -> Ctx:
        it = A.iteracion_actual_de(self.almacen.estado, corrida)
        return Ctx(self.almacen, self.programas, self.modelos, corrida["id"], corrida["investigacionId"], it["id"] if it else "", corrida["iteracionActual"])

    async def _aclarar(self, ctx: Ctx, h: dict[str, Any]) -> None:
        ultima = next((r for r in reversed(h["revisiones"]) if r["accion"] == "no_puedo_juzgar"), None)
        if not ultima:
            return
        try:
            pred = await ctx.llamar("cerebro", ctx.programas.aclarar, hipotesis=T.hipotesis_texto(h), nota=ultima["nota"], afirmaciones="\n".join(f"- [{a['veredicto']}] {a['texto']} {a['cita']}" for a in h["afirmaciones"]))
        except Exception as ex:  # noqa: BLE001
            self.almacen.mutar(lambda e: A.aclarar_hipotesis(e, h["id"], f"No pude aclararla ahora: el modelo no respondio ({str(ex)[:100]}). Vuelve a la cola tal cual.", P.ahora_ms()), "aclarar")
            return
        self.almacen.mutar(lambda e: A.aclarar_hipotesis(e, h["id"], pred.aclaracion, P.ahora_ms()), "aclarar")

    async def _responder_comentarios(self, ctx: Ctx, h: dict[str, Any]) -> None:
        comentarios = [m["texto"] for m in h["procedencia"]["mensajes"] if m["de"] == "investigadora"][-3:]
        ahora = P.ahora_ms()
        try:
            pred = await ctx.llamar("cerebro", ctx.programas.responder, hipotesis=T.hipotesis_texto(h), comentarios="\n\n".join(comentarios), afirmaciones="\n".join(f"- [{a['veredicto']}] {a['texto']} {a['cita']}" for a in h["afirmaciones"]))
            respuesta, enunciado = pred.respuesta, pred.enunciado_revisado.strip()
        except Exception as ex:  # noqa: BLE001
            respuesta, enunciado = f"No pude responder ahora: el modelo no respondio ({str(ex)[:100]}).", h["enunciado"]

        def fn(e: dict[str, Any]) -> bool:
            x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
            if not x:
                return False
            x.pop("_comentariosNuevos", None)
            x["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "rosa", "texto": respuesta, "creadoEn": ahora})
            if enunciado and enunciado != x["enunciado"]:
                x["enunciado"] = enunciado
                x["revisiones"].append({"fecha": ahora, "quien": config.QUIEN_ROSA, "accion": "aclarada", "nota": "Enunciado revisado tras los comentarios", "aCiegas": False})
            return True

        self.almacen.mutar(fn, "responder_comentarios")

    async def _replicar_paso(self, ctx: Ctx, h: dict[str, Any]) -> None:
        """Una trayectoria de replicacion: se vuelven a juzgar las afirmaciones
        de la hipotesis con el juez (temperatura alta) y se cuenta si el
        conjunto se sostiene (fidelidad >= 0,5 y nada bloqueante)."""
        from rosa import verificador as V

        copias = [dict(a, fragmento="", localizador="", fuenteId="") for a in h["afirmaciones"]]
        # Localizar fragmentos por cita.
        frags = ctx.fragmentos_verificador()
        for a in copias:
            fr = V.resolver_cita(a["cita"], frags)
            if fr:
                a["fragmento"], a["localizador"], a["fuenteId"], a["encabezado"] = fr.texto[:400], fr.localizador, fr.fuente_id, fr.encabezado
            a["veredicto"] = "sin_verificar"
        try:
            with_temp = self.modelos
            recuento = await PASOS.verificar_afirmaciones(ctx, copias, None, h["enunciado"]) if copias else {}
        except Exception:  # noqa: BLE001
            recuento = {}
        veredictos = [a["veredicto"] for a in copias]
        fid = V.fidelidad(veredictos)
        sostiene = bool(copias) and fid is not None and fid >= 0.5 and not any(V.bloquea(v) for v in veredictos)

        def fn(e: dict[str, Any]) -> bool:
            x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
            if not x or not x["replicacion"] or x["replicacion"]["estado"] != "en_curso":
                return False
            r = x["replicacion"]
            r["hechas"] += 1
            r["sostienen" if sostiene else "contradicen"] += 1
            if r["hechas"] >= r["total"]:
                r["estado"] = "terminada"
                x["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "revisor", "texto": f"Replicacion terminada: {r['sostienen']} de {r['total']} trayectorias sostienen las afirmaciones.", "creadoEn": P.ahora_ms()})
            return True

        self.almacen.mutar(fn, "replicacion")

    async def _recomprobar_retracciones(self, inv: dict[str, Any]) -> None:
        ahora = P.ahora_ms()
        dois: dict[str, tuple[str | None, str]] = {}
        for h in self.almacen.estado["hipotesis"]:
            if h["investigacionId"] != inv["id"]:
                continue
            for f in h["procedencia"]["fuentes"]:
                if f.get("doi") and f["doi"] not in dois:
                    try:
                        dois[f["doi"]] = await crossref.marca_editorial(f["doi"])
                    except FuenteNoDisponible as ex:
                        dois[f["doi"]] = ("__error__", str(ex)[:100])
        cambios = 0
        afectadas: list[dict[str, Any]] = []

        def fn(e: dict[str, Any]) -> bool:
            nonlocal cambios
            i = next((x for x in e["investigaciones"] if x["id"] == inv["id"]), None)
            if i:
                i.pop("_recomprobarRetracciones", None)
            for h in e["hipotesis"]:
                if h["investigacionId"] != inv["id"]:
                    continue
                tocada = False
                for f in h["procedencia"]["fuentes"]:
                    r = dois.get(f.get("doi") or "")
                    if not r or r[0] == "__error__":
                        continue
                    if f["retraccion"] != r[0]:
                        cambios += 1
                        tocada = True
                        f["retraccion"] = r[0]
                    f["retraccionComprobadaEn"] = ahora
                if tocada:
                    # Seguimiento de dependencias (plan completo, seccion 9): la fuente
                    # cambio, asi que la conclusion que dependia de ella se marca para
                    # recalcular; la anterior se guarda para el informe de diferencias.
                    h["_conclusionAnterior"] = h.get("conclusion")
                    h.pop("_conclusionIntentada", None)
                    h["_recalcularPorFuente"] = ahora
                    A.recalcular_bloqueos(e, h)
                    afectadas.append({"id": h["id"], "titulo": h["titulo"]})
            A.con_evento(e, inv["id"], "retraccion", f"Retractaciones recomprobadas en {len(dois)} DOI: {cambios} cambios" + (f"; {len(afectadas)} hipotesis se recalculan" if afectadas else "") + (" (algunas consultas no llegaron)" if any(v[0] == '__error__' for v in dois.values()) else ""), None, ahora)
            return True

        self.almacen.mutar(fn, "retracciones")
        if afectadas:
            corrida = A.ultima_corrida_de(self.almacen.estado, inv["id"])
            if corrida:
                ctx = self._ctx(corrida)
                for a in afectadas:
                    y = next((z for z in self.almacen.estado["hipotesis"] if z["id"] == a["id"]), None)
                    if y:
                        await self._concluir_hipotesis(ctx, y)
                self._informe_de_diferencias(inv, [a["id"] for a in afectadas], "cambio de estado editorial de una fuente")

    def _informe_de_diferencias(self, inv: dict[str, Any], ids: list[str], causa: str) -> None:
        """El informe de diferencias del plan completo: que decia cada
        conclusion antes del cambio de fuente y que dice ahora. Los informes
        anteriores no se tocan: lo historico sigue siendo historico."""
        ahora = P.ahora_ms()

        def fn(e: dict[str, Any]) -> bool:
            L = [f"# Recalculo por {causa}", "", f"Fecha: {datetime.fromtimestamp(ahora / 1000).strftime('%d/%m/%Y %H:%M')}. Investigacion: {inv['titulo']}.", ""]
            for hid in ids:
                h = next((z for z in e["hipotesis"] if z["id"] == hid), None)
                if not h:
                    continue
                antes = h.pop("_conclusionAnterior", None) or {}
                despues = h.get("conclusion") or {}
                h.pop("_recalcularPorFuente", None)
                L += [f"## {h['titulo']}", f"Antes: certeza {antes.get('certeza', 'sin conclusion')}, direccion {antes.get('direccion', '?')}. {antes.get('enunciado', '')}", f"Ahora: certeza {despues.get('certeza', 'sin conclusion')}, direccion {despues.get('direccion', '?')}. {despues.get('enunciado', '')}", f"Bloqueos ahora: {', '.join(h.get('bloqueos', [])) or 'ninguno'}", ""]
                if h.get("experimento") and h["experimento"].get("estado") in ("asignado", "en_curso"):
                    L.append("Experimento en marcha: el recalculo no lo cancela ni lo autoriza; decide una persona.")
                    L.append("")
            A.guardar_artefacto(e, inv["id"], f"Informe de diferencias: {causa}", "informe", "\n".join(L), f"{len(ids)} conclusiones recalculadas", (A.ultima_corrida_de(e, inv["id"]) or {}).get("iteracionActual", 0), ahora)
            A.con_evento(e, inv["id"], "dependencias", f"Informe de diferencias: {len(ids)} conclusiones recalculadas por {causa}", f"#/investigaciones/{inv['id']}/artefactos", ahora)
            return True

        self.almacen.mutar(fn, "informe_diferencias")

    # -- el bucle de una corrida --------------------------------------------

    async def correr_corrida(self, corrida_id: str) -> None:
        while not self._parar.is_set():
            e = self.almacen.estado
            c = next((x for x in e["corridas"] if x["id"] == corrida_id), None)
            if not c or c["estado"] in ("detenida", "terminada"):
                return
            if c["estado"] in ("pausada", "pausada_por_presupuesto", "esperando_aprobacion"):
                await asyncio.sleep(1.0)
                continue
            it = A.iteracion_actual_de(e, c)
            if it is None or it["terminadaEn"] is not None:
                await self._proponer_plan(c, it)
                continue
            if not it["planAprobado"]:
                if c["estado"] != "esperando_plan":
                    self.almacen.mutar(lambda e2: _fijar_estado(e2, corrida_id, "esperando_plan"), "estado")
                await asyncio.sleep(1.0)
                continue
            if c["estado"] != "en_marcha":
                self.almacen.mutar(lambda e2: _fijar_estado(e2, corrida_id, "en_marcha"), "estado")
            if not await self._permiso_presupuesto(c, it):
                continue
            paso = next((p for p in it["plan"] if p["estado"] in ("en_curso", "pendiente")), None)
            if paso is None:
                await self._cerrar_iteracion(c, it)
                continue
            inv = next(i for i in e["investigaciones"] if i["id"] == c["investigacionId"])
            motivo = _condicion_de_parada(inv["condicionParada"], it["numero"] - 1, c, mision=inv.get("mision"))
            if motivo:
                # El tiempo o las llamadas se cumplieron a mitad de iteracion: lo
                # pendiente se omite con motivo y la iteracion se cierra ya.
                self.almacen.mutar(lambda e2: _omitir_pendientes(e2, it["id"], motivo), "parada")
                await self._cerrar_iteracion(c, it)
                continue
            await self._ejecutar_paso(c, it, paso)

    async def _proponer_mision(self, ctx: Ctx, inv: dict[str, Any]) -> None:
        """La mision estructurada (etapa 0 de ROSA2018) a partir del objetivo.
        Queda propuesta; la persona la aprueba (o la corrige) con el primer
        plan o desde Objetivo y datos."""
        try:
            pred = await ctx.llamar("cerebro", self.programas.mision, objetivo=inv["objetivo"], relevancia=inv["relevancia"] or "Sin definir", limites="; ".join(inv["limites"]) or "Ninguno", configuracion=T.configuracion(inv))
            m = pred.mision
            mision = {**P.mision_vacia(), "metaAmplia": inv["objetivo"], "poblacion": m.poblacion.strip(), "etapa": m.etapa.strip(), "celulaTejido": m.celula_tejido.strip(), "mecanismo": m.mecanismo.strip(), "tipoIntervencion": m.tipo_intervencion.strip(), "capacidadesLaboratorio": [c.strip() for c in m.capacidades_laboratorio if c.strip()][:6], "propuestaPorRosa": True}
            justificacion = m.justificacion.strip()
            # El planificador del programa: areas de investigacion comparables, con
            # familias de mecanismo distintas y las que quedan sin explorar.
            try:
                pa = await ctx.llamar("cerebro", self.programas.areas, meta_amplia=inv["objetivo"], mision=PASOS._texto_mision({"mision": mision}), modelo_de_mundo=T.modelo_de_mundo(self.almacen.estado["hechos"], inv["id"], maximo=30), limites="; ".join(inv["limites"]) or "Ninguno")
                mision["areas"] = [P.nueva_area(titulo=a.titulo.strip(), familiaMecanismo=a.familia_mecanismo.strip(), relevancia=a.relevancia.strip(), valorIntervencion=a.valor_intervencion.strip(), incertidumbre=a.incertidumbre.strip(), comprobabilidad=a.comprobabilidad.strip(), coste=a.coste.strip(), demora=a.demora.strip(), dependeDe=a.depende_de.strip(), estado="elegida" if a.elegir else ("sin_explorar" if "sin ruta" in a.comprobabilidad.lower() else "propuesta")) for a in list(pa.areas)[:6]]
                if not any(a["estado"] == "elegida" for a in mision["areas"]) and mision["areas"]:
                    mision["areas"][0]["estado"] = "elegida"
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        except Exception as ex:  # noqa: BLE001
            traceback.print_exc()
            mision, justificacion = None, str(ex)[:200]
        ahora = P.ahora_ms()

        def fn(e: dict[str, Any]) -> bool:
            i = next((x for x in e["investigaciones"] if x["id"] == inv["id"]), None)
            if not i:
                return False
            i["_misionIntentada"] = True
            if mision and i.get("mision") is None:
                mision["presupuesto"]["llamadas"] = (A.ultima_corrida_de(e, i["id"]) or {}).get("presupuesto", {}).get("limiteLlamadas", mision["presupuesto"]["llamadas"])
                i["mision"] = mision
                A.con_evento(e, i["id"], "mision", f"Rosa propone la mision: {justificacion[:140]}. Apruebala o corrigela en Objetivo y datos.", f"#/investigaciones/{i['id']}/investigacion", ahora)
            return True

        self.almacen.mutar(fn, "mision")

    async def _formular_pregunta(self, ctx: Ctx, c: dict[str, Any], inv: dict[str, Any]) -> None:
        """La pregunta concreta de la campana, con la plantilla del plan
        completo, desde la meta, la mision y el area elegida. Queda
        propuesta; se aprueba con el primer plan o se corrige en la corrida."""
        m = inv.get("mision") or {}
        elegida = next((a for a in m.get("areas", []) if a["estado"] == "elegida"), None)
        area = (f"{elegida['titulo']} ({elegida['familiaMecanismo']}). Relevancia: {elegida['relevancia']}. Comprobabilidad: {elegida['comprobabilidad']}. Coste: {elegida['coste']}. Demora: {elegida['demora']}." if elegida else f"Objetivo tal como lo escribio la persona: {inv['objetivo']}")
        try:
            pred = await ctx.llamar("cerebro", self.programas.pregunta, meta_amplia=m.get("metaAmplia") or inv["objetivo"], mision=PASOS._texto_mision(inv), area=area, modelo_de_mundo=T.modelo_de_mundo(self.almacen.estado["hechos"], inv["id"], maximo=30))
            q = pred.pregunta
            pregunta = {**P.pregunta_vacia(), "contexto": q.contexto.strip(), "etapa": q.etapa.strip(), "intervencion": q.intervencion.strip(), "comparador": q.comparador.strip(), "desenlace": q.desenlace.strip(), "ventana": q.ventana.strip(), "unidadBiologica": q.unidad_biologica.strip(), "mecanismos": q.mecanismos.strip(), "decision": q.decision.strip(), "umbralEfecto": q.umbral_efecto.strip(), "umbralResuelto": bool(q.umbral_resuelto) and "sin resolver" not in q.umbral_efecto.lower(), "pasoRuta": q.paso_ruta, "enunciado": q.enunciado.strip(), "propuestaPorRosa": True}
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            pregunta = None
        ahora = P.ahora_ms()

        def fn(e: dict[str, Any]) -> bool:
            c2 = next((x for x in e["corridas"] if x["id"] == c["id"]), None)
            if not c2:
                return False
            c2["_preguntaIntentada"] = True
            if pregunta and c2.get("pregunta") is None:
                c2["pregunta"] = pregunta
                A.con_evento(e, inv["id"], "corrida_estado", f"Pregunta de la corrida {c2['numero']}: {pregunta.get('enunciado', '')[:140]}", f"#/investigaciones/{inv['id']}/corrida", ahora)
            return True

        self.almacen.mutar(fn, "pregunta")

    async def _proponer_plan(self, c: dict[str, Any], anterior: dict[str, Any] | None) -> None:
        e = self.almacen.estado
        inv = next(i for i in e["investigaciones"] if i["id"] == c["investigacionId"])
        numero = (anterior["numero"] + 1) if anterior else 1
        motivo = _condicion_de_parada(inv["condicionParada"], numero - 1, c, mision=inv.get("mision")) if anterior else None
        if motivo:
            self.almacen.mutar(lambda e2: _terminar_corrida(e2, c["id"], motivo), "parada")
            return
        ctx = Ctx(self.almacen, self.programas, self.modelos, c["id"], inv["id"], anterior["id"] if anterior else "", numero)
        if inv.get("mision") is None and not inv.get("_misionIntentada"):
            await self._proponer_mision(ctx, inv)
            inv = next(i for i in self.almacen.estado["investigaciones"] if i["id"] == c["investigacionId"])
        if c.get("pregunta") is None and not c.get("_preguntaIntentada"):
            await self._formular_pregunta(ctx, c, inv)
        plan: list[dict[str, Any]] = []
        try:
            pregunta = (c.get("pregunta") or {}).get("enunciado") or (next((x for x in self.almacen.estado["corridas"] if x["id"] == c["id"]), {}).get("pregunta") or {}).get("enunciado")
            pred = await ctx.llamar(
                "cerebro",
                self.programas.plan,
                objetivo=inv["objetivo"] + (f"\nPregunta de esta campana: {pregunta}" if pregunta else ""),
                relevancia=inv["relevancia"],
                limites="; ".join(inv["limites"]) or "Ninguno declarado",
                condicion_parada=inv["condicionParada"],
                modelo_de_mundo=T.modelo_de_mundo(e["hechos"], inv["id"]),
                resumen_iteracion_anterior=anterior["resumen"] if anterior else "",
                indicaciones_humanas=T.indicaciones_humanas(anterior, pendientes_solo=True) if anterior else "Ninguna.",
                hipotesis_vivas=T.hipotesis_vivas(e["hipotesis"], inv["id"]),
                numero_iteracion=numero,
            )
            hay_datos = any(d["estado"] == "aprobado" and (d.get("procedencia") or {}).get("hash") for d in inv.get("datasets", []))
            for p in list(pred.plan)[:7]:
                if p.tipo == "analisis" and not hay_datos:
                    continue  # sin datasets aprobados no hay nada que analizar
                paso = P.nuevo_paso(p.titulo, p.detalle, COSTE_POR_TIPO.get(p.tipo, 20), valor_decision=(p.valor_decision or "").strip())
                paso["tipo"] = p.tipo
                plan.append(paso)
            if hay_datos and not any(p.get("tipo") == "analisis" for p in plan) and (any(r["investigacionId"] == inv["id"] and r["estado"] == "pendiente" for r in e.get("reproducciones", [])) or any(h["investigacionId"] == inv["id"] and h.get("_analisisPedido") for h in e["hipotesis"])):
                paso = P.nuevo_paso("Analisis in silico", "Reproducciones pendientes de la puerta y analisis pedidos, en el sandbox", COSTE_POR_TIPO["analisis"])
                paso["tipo"] = "analisis"
                plan.append(paso)
            plan = _ordenar_plan(plan, hay_novedad_pendiente=any(h["investigacionId"] == inv["id"] and h["novedad"]["precedente"]["detalle"].startswith("No comprobado") for h in e["hipotesis"]))
        except PresupuestoAgotado:
            self.almacen.mutar(lambda e2: _pausar_por_presupuesto(e2, c["id"]), "presupuesto")
            return
        except Exception as ex:  # noqa: BLE001
            ctx.incidencia("modelo_bloqueado", "No se pudo proponer el plan con el modelo", str(ex)[:400], self.modelos.cerebro.model, "Se usa el plan por defecto de Rosa; se puede editar antes de aprobarlo.")
        if not plan:
            for titulo, detalle, tipo, pres in PLAN_POR_DEFECTO:
                paso = P.nuevo_paso(titulo, detalle, COSTE_POR_TIPO.get(tipo, pres))
                paso["tipo"] = tipo
                plan.append(paso)
        # Las indicaciones humanas pendientes de la iteracion anterior pasan a la nueva.
        if anterior:
            for p in anterior["plan"]:
                if p["indicacionHumana"] and p["estado"] == "pendiente":
                    plan.insert(0, dict(p, id=P.nuevo_id("paso")))
        ahora = P.ahora_ms()
        it = P.nueva_iteracion(c["id"], numero, ahora, plan, max(sum(p["presupuesto"] or 0 for p in plan), 20))

        def fn(e2: dict[str, Any]) -> bool:
            e2["iteraciones"].append(it)
            c2 = next(x for x in e2["corridas"] if x["id"] == c["id"])
            c2["iteracionActual"] = numero
            c2["estado"] = "esperando_plan"
            A.con_evento(e2, inv["id"], "corrida_estado", f"Plan de la iteracion {numero} propuesto: {len(plan)} pasos. Espera tu aprobacion.", f"#/investigaciones/{inv['id']}/corrida", ahora)
            return True

        self.almacen.mutar(fn, "plan_propuesto")

    async def _permiso_presupuesto(self, c: dict[str, Any], it: dict[str, Any]) -> bool:
        """Si la iteracion pide mas de la mitad de lo que queda en la corrida y
        la autonomia dice 'preguntar', se pide permiso una vez por iteracion."""
        e = self.almacen.estado
        if it.get("_presupuestoAutorizado") or e["autonomia"].get("gastar_grande") == "actuar":
            return True
        restante = c["presupuesto"]["limiteLlamadas"] - c["gasto"]["llamadas"]
        pedido = it["presupuesto"]["limite"]
        if pedido <= restante * 0.5:
            return True
        ya = next((s for s in e["solicitudes"] if s["corridaId"] == c["id"] and s["tipo"] == "presupuesto_grande" and s.get("_iteracionId") == it["id"]), None)
        if ya is None:
            ahora = P.ahora_ms()
            s = {"id": P.nuevo_id("sol"), "corridaId": c["id"], "tipo": "presupuesto_grande", "titulo": f"La iteracion {it['numero']} quiere gastar {pedido} llamadas de las {restante} que quedan", "detalle": "Es mas de la mitad del presupuesto restante. Puedes ajustar cuantas llamadas permitir.", "recurso": f"{pedido} llamadas al modelo", "alcances": ["una_vez", "esta_corrida"], "estado": "pendiente", "alcanceConcedido": None, "creadaEn": ahora, "resueltaEn": None, "hipotesisId": None, "argumentos": [{"nombre": "llamadas", "valor": str(pedido), "editable": True}], "_iteracionId": it["id"]}

            def fn(e2: dict[str, Any]) -> bool:
                e2["solicitudes"].append(s)
                c2 = next(x for x in e2["corridas"] if x["id"] == c["id"])
                c2["estado"] = "esperando_aprobacion"
                A.con_evento(e2, c["investigacionId"], "permiso_pendiente", s["titulo"], f"#/investigaciones/{c['investigacionId']}/corrida", ahora)
                return True

            self.almacen.mutar(fn, "solicitud")
            return False
        if ya["estado"] == "pendiente":
            await asyncio.sleep(1.0)
            return False

        def resolver(e2: dict[str, Any]) -> bool:
            it2 = next(x for x in e2["iteraciones"] if x["id"] == it["id"])
            it2["_presupuestoAutorizado"] = True
            if ya["estado"] == "concedida":
                arg = next((a for a in ya["argumentos"] if a["nombre"] == "llamadas"), None)
                if arg and arg["valor"].isdigit():
                    it2["presupuesto"]["limite"] = int(arg["valor"])
                if ya["alcanceConcedido"] == "esta_corrida":
                    e2["autonomia"]["gastar_grande"] = e2["autonomia"]["gastar_grande"]  # el permiso queda registrado en `permisos`
            else:
                it2["presupuesto"]["limite"] = max(10, int(restante * 0.5))
            return True

        self.almacen.mutar(resolver, "presupuesto_autorizado")
        return True

    async def _ejecutar_paso(self, c: dict[str, Any], it: dict[str, Any], paso: dict[str, Any]) -> None:
        tipo = T.inferir_tipo_paso(paso)
        ctx = Ctx(self.almacen, self.programas, self.modelos, c["id"], c["investigacionId"], it["id"], it["numero"])
        self.almacen.mutar(lambda e: _estado_paso(e, it["id"], paso["id"], "en_curso"), "paso")
        if tipo == "indicacion":
            # La indicacion humana entra como contexto de los pasos que siguen.
            self.almacen.mutar(lambda e: _estado_paso(e, it["id"], paso["id"], "hecho", detalle=paso["detalle"]), "paso")
            return
        ejecutor = PASOS.EJECUTORES.get(tipo)
        if ejecutor is None:
            self.almacen.mutar(lambda e: _estado_paso(e, it["id"], paso["id"], "omitido", motivo=f"Rosa no tiene herramienta para '{tipo}'"), "paso")
            return
        try:
            resumen = await ejecutor(ctx, paso)
            it_actual = next(x for x in self.almacen.estado["iteraciones"] if x["id"] == it["id"])
            propias = [p for p in it_actual["pistas"] if p["pasoId"] == paso["id"]]
            todas_fallaron = bool(propias) and all(p["estado"] in ("fallida", "detenida") for p in propias)
            if todas_fallaron:
                self.almacen.mutar(lambda e: _estado_paso(e, it["id"], paso["id"], "fallido", motivo="Ninguna de sus pistas termino: " + "; ".join(p["resumen"] for p in propias)[:300]), "paso")
            else:
                self.almacen.mutar(lambda e: _estado_paso(e, it["id"], paso["id"], "hecho", detalle=resumen), "paso")
        except PresupuestoAgotado:
            self.almacen.mutar(lambda e: _estado_paso(e, it["id"], paso["id"], "pendiente"), "paso")
            self.almacen.mutar(lambda e: _pausar_por_presupuesto(e, c["id"]), "presupuesto")
        except asyncio.CancelledError:
            raise
        except Exception as ex:  # noqa: BLE001
            traceback.print_exc()
            self.almacen.mutar(lambda e: _estado_paso(e, it["id"], paso["id"], "fallido", motivo=f"{type(ex).__name__}: {str(ex)[:200]}"), "paso")

    async def _cerrar_iteracion(self, c: dict[str, Any], it: dict[str, Any]) -> None:
        e = self.almacen.estado
        inv = next(i for i in e["investigaciones"] if i["id"] == c["investigacionId"])
        ctx = Ctx(self.almacen, self.programas, self.modelos, c["id"], inv["id"], it["id"], it["numero"])
        hechos_nuevos = [h for h in e["hechos"] if h["investigacionId"] == inv["id"] and h["actualizadoEn"] >= it["empezadaEn"] and h["historial"] and h["historial"][0]["quien"] == config.QUIEN_ROSA]
        hip_nuevas = [h for h in e["hipotesis"] if h["investigacionId"] == inv["id"] and h["iteracion"] == it["numero"] and h["origen"] == "rosa"]
        afs = [a for a in c.get("_afirmaciones", []) if a["iteracion"] == it["numero"]]
        sin_comprobar = [a for a in afs if a["veredicto"] == "sin_verificar"] + [p for p in it["plan"] if p["estado"] == "fallido"]
        try:
            pred = await ctx.llamar("cerebro", self.programas.resumir, plan_ejecutado=T.plan_ejecutado(it), cambios_modelo_de_mundo="\n".join(f"- {h['enunciado']}" for h in hechos_nuevos) or "Ninguno", hipotesis_nuevas="\n".join(f"- {h['titulo']}" for h in hip_nuevas) or "Ninguna", sin_comprobar="\n".join(f"- {x.get('texto') or x.get('titulo')}" for x in sin_comprobar) or "Nada")
            resumen = pred.resumen.strip()
        except Exception:  # noqa: BLE001
            hechas = sum(1 for p in it["pistas"] if p["estado"] == "hecha")
            resumen = f"{len(it['plan'])} pasos, {hechas} pistas completadas, {len(hechos_nuevos)} hechos y {len(hip_nuevas)} hipotesis nuevas"
        # El panorama y las debilidades se sintetizan al cerrar cada iteracion
        # con dos o mas hipotesis, aunque el plan no trajera un paso de meta.
        propias = [h for h in e["hipotesis"] if h["investigacionId"] == inv["id"]]
        if len(propias) >= 2 and not any(T.inferir_tipo_paso(p) == "meta" and p["estado"] == "hecho" for p in it["plan"]):
            try:
                await PASOS.paso_meta(ctx, {"id": None, "titulo": "Meta-revision al cierre", "detalle": ""})
            except Exception as ex:  # noqa: BLE001
                traceback.print_exc()
        llano = await self._explicar_en_llano(ctx, inv, resumen, hechos_nuevos, hip_nuevas, sin_comprobar)
        for h in [x for x in e["hipotesis"] if x["investigacionId"] == inv["id"] and x["estado"] not in ("descartada",)][:8]:
            if h.get("_conclusionIntentada") != it["numero"]:
                await self._concluir_hipotesis(ctx, h)
        ahora = P.ahora_ms()
        bloqueadas = [a for a in afs if a["veredicto"] in ("no_sostenida", "cita_no_resuelve", "sin_cita", "ausencia_refutada")]
        informe = _informe(inv, it, resumen, hechos_nuevos, hip_nuevas, afs, bloqueadas)
        terminar = _condicion_de_parada(inv["condicionParada"], it["numero"], c, mision=inv.get("mision"))

        def fn(e2: dict[str, Any]) -> bool:
            it2 = next(x for x in e2["iteraciones"] if x["id"] == it["id"])
            it2["terminadaEn"] = ahora
            it2["resumen"] = resumen
            if llano:
                it2["resumenLlano"] = llano
            # Priorizacion: bloqueos no compensables y candidatas con diversidad.
            ids = PR.marcar_candidatas(e2, inv["id"])
            if ids:
                titulos = [next(x["titulo"][:50] for x in e2["hipotesis"] if x["id"] == i) for i in ids]
                A.con_evento(e2, inv["id"], "ranking_cambio", f"Candidatas al laboratorio tras la iteracion {it['numero']}: " + "; ".join(titulos), f"#/investigaciones/{inv['id']}/ranking", ahora)
            A.guardar_artefacto(e2, inv["id"], f"Informe de la iteracion {it['numero']}", "informe", informe, resumen[:140], it["numero"], ahora)
            A.con_evento(e2, inv["id"], "iteracion_terminada", f"Iteracion {it['numero']} terminada: {resumen[:160]}", f"#/investigaciones/{inv['id']}/corrida", ahora)
            c2 = next(x for x in e2["corridas"] if x["id"] == c["id"])
            if terminar:
                c2["estado"] = "terminada"
                c2["terminadaEn"] = ahora
                c2["motivoCierre"] = terminar
                A.con_evento(e2, inv["id"], "corrida_estado", f"Corrida {c2['numero']} terminada: {terminar}", f"#/investigaciones/{inv['id']}/corrida", ahora)
            return True

        self.almacen.mutar(fn, "iteracion_cerrada")


# ---------------------------------------------------------------------------
# Ayudantes puros
# ---------------------------------------------------------------------------


def _ordenar_plan(plan: list[dict[str, Any]], hay_novedad_pendiente: bool) -> list[dict[str, Any]]:
    """El orden relativo lo decide el modelo, salvo dos dependencias de Rosa:
    el modelo de mundo se actualiza antes de generar hipotesis, y la novedad
    se comprueba despues de generarlas (si no hay hipotesis pendientes de
    novedad, un paso de novedad antes de hipotesis no tendria nada que hacer)."""
    tipos = [p.get("tipo") for p in plan]
    if "modelo" in tipos and "hipotesis" in tipos and tipos.index("modelo") > tipos.index("hipotesis"):
        m = plan.pop(tipos.index("modelo"))
        plan.insert([p.get("tipo") for p in plan].index("hipotesis"), m)
        tipos = [p.get("tipo") for p in plan]
    if "novedad" in tipos and "hipotesis" in tipos and tipos.index("novedad") < tipos.index("hipotesis") and not hay_novedad_pendiente:
        n = plan.pop(tipos.index("novedad"))
        plan.insert([p.get("tipo") for p in plan].index("hipotesis") + 1, n)
        tipos = [p.get("tipo") for p in plan]
    # El analisis con datos va despues de las hipotesis (necesita su prediccion
    # falsable y la decision del Killer) y antes de la meta-revision.
    if "analisis" in tipos and "hipotesis" in tipos and tipos.index("analisis") < tipos.index("hipotesis"):
        a = plan.pop(tipos.index("analisis"))
        plan.insert([p.get("tipo") for p in plan].index("hipotesis") + 1, a)
    return plan


def _fijar_evaluacion(e: dict[str, Any], cambio_id: str, evaluacion: dict[str, Any], ahora: int) -> bool:
    c = next((x for x in e.get("aprendizaje", []) if x["id"] == cambio_id), None)
    if not c:
        return False
    c.pop("_evaluar", None)
    c["evaluacion"] = evaluacion
    if c["estado"] == "propuesto" and evaluacion.get("casos"):
        c["estado"] = "evaluado"
    A.con_evento(e, c.get("investigacionId"), "aprendizaje", f"Criterio evaluado sobre {evaluacion.get('casos', 0)} casos: acuerdo {evaluacion.get('antes')} antes, {evaluacion.get('despues')} despues. {evaluacion.get('nota', '')}", "#/ajustes", ahora)
    return True


def _omitir_pendientes(e: dict[str, Any], iteracion_id: str, motivo: str) -> bool:
    it = next((x for x in e["iteraciones"] if x["id"] == iteracion_id), None)
    if not it:
        return False
    for p in it["plan"]:
        if p["estado"] in ("pendiente", "en_curso"):
            p["estado"] = "omitido"
            p["motivoFallo"] = motivo
    return True


def _terminar_corrida(e: dict[str, Any], corrida_id: str, motivo: str) -> bool:
    c = next((x for x in e["corridas"] if x["id"] == corrida_id), None)
    if not c or c["estado"] in ("detenida", "terminada"):
        return False
    ahora = P.ahora_ms()
    c["estado"] = "terminada"
    c["terminadaEn"] = ahora
    c["motivoCierre"] = motivo
    A.con_evento(e, c["investigacionId"], "corrida_estado", f"Corrida {c['numero']} terminada: {motivo}", f"#/investigaciones/{c['investigacionId']}/corrida", ahora)
    return True


VERBO_CERTEZA = {"alta": "La evidencia reunida sostiene que", "moderada": "La evidencia reunida probablemente sostiene que", "baja": "La evidencia sugiere, con limitaciones, que", "muy_baja": "La evidencia es muy incierta sobre si"}
VERBO_CONTRA = {"alta": "La evidencia reunida contradice que", "moderada": "La evidencia reunida probablemente contradice que", "baja": "La evidencia sugiere, con limitaciones, que no se cumple que", "muy_baja": "La evidencia es muy incierta sobre si"}


def frase_plantilla(direccion: str, certeza: str, titulo: str) -> str:
    """La frase calibrada de (direccion, certeza), como las tablas de Santesso
    2020 y Cochrane Iberoamerica. El modelo no la escribe: se genera aqui para
    que 'probablemente' signifique siempre lo mismo. El titulo de la hipotesis
    hace de H con la inicial en minuscula."""
    h = titulo.strip().rstrip(".")
    h = h[:1].lower() + h[1:] if h and not h[:2].isupper() else h
    if direccion == "sin_evidencia_directa":
        return f"No encontramos evidencia directa sobre si {h}. Esto no significa que no exista."
    if direccion == "mixta":
        return f"La evidencia es contradictoria sobre si {h}; la certeza es {certeza.replace('_', ' ')}."
    if direccion == "en_contra":
        return f"{VERBO_CONTRA[certeza]} {h}."
    return f"{VERBO_CERTEZA[certeza]} {h}."


def _fijar_estado(e: dict[str, Any], corrida_id: str, estado: str) -> bool:
    c = next((x for x in e["corridas"] if x["id"] == corrida_id), None)
    if not c or c["estado"] == estado:
        return False
    c["estado"] = estado
    return True


def _pausar_por_presupuesto(e: dict[str, Any], corrida_id: str) -> bool:
    c = next((x for x in e["corridas"] if x["id"] == corrida_id), None)
    if not c or c["estado"] == "pausada_por_presupuesto":
        return False
    pendientes = any(s["corridaId"] == corrida_id and s["estado"] == "pendiente" for s in e["solicitudes"]) or any(i["corridaId"] == corrida_id and i["estado"] == "pendiente" for i in e["incidencias"])
    c["estado"] = "esperando_aprobacion" if pendientes else "pausada_por_presupuesto"
    A.con_evento(e, c["investigacionId"], "presupuesto", f"Presupuesto global agotado ({c['presupuesto']['limiteLlamadas']} llamadas): la corrida se pauso. Amplia el tope para seguir.", f"#/investigaciones/{c['investigacionId']}/corrida", P.ahora_ms())
    return True


def _estado_paso(e: dict[str, Any], iteracion_id: str, paso_id: str, estado: str, detalle: str | None = None, motivo: str | None = None) -> bool:
    it = next((x for x in e["iteraciones"] if x["id"] == iteracion_id), None)
    if not it:
        return False
    for p in it["plan"]:
        if p["id"] == paso_id:
            p["estado"] = estado
            if detalle:
                p["detalle"] = detalle[:300]
            p["motivoFallo"] = motivo
            return True
    return False


def _condicion_de_parada(texto: str, numero: int, c: dict[str, Any], ahora: int | None = None, mision: dict[str, Any] | None = None) -> str | None:
    """Solo se automatiza lo que se puede medir en el texto de la condicion:
    "N iteraciones", "N minutos" u "N horas" de corrida, y "N llamadas".
    Lo demas ("cuando el modelo de mundo deje de cambiar") lo decide la
    investigadora con el boton de detener. Devuelve el motivo o None.
    Ademas, el presupuesto de la mision en dinero y en horas para la corrida."""
    t = texto.lower()
    ahora = ahora if ahora is not None else P.ahora_ms()
    if mision and mision.get("presupuesto"):
        pres = mision["presupuesto"]
        usd = c["gasto"].get("usd", 0.0)
        if pres.get("usd") and usd >= pres["usd"]:
            return f"Se alcanzo el presupuesto de la mision en dinero ({usd:.2f} de {pres['usd']:.2f} USD estimados)"
        horas = (ahora - c["empezadaEn"]) / 3_600_000
        if pres.get("horas") and horas >= pres["horas"]:
            return f"Se alcanzo el presupuesto de la mision en tiempo ({horas:.1f} de {pres['horas']:.0f} horas)"
    m = re.search(r"(\d+)\s*iteraci", t)
    if m and numero >= int(m.group(1)):
        return f"Se alcanzaron las {m.group(1)} iteraciones de la condicion de parada"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(min\b|minuto|hora|h\b|dia|día)", t)
    if m:
        n = float(m.group(1).replace(",", "."))
        unidad = m.group(2)
        segundos = n * (60 if unidad.startswith("min") else 3600 if unidad in ("hora", "h") or unidad.startswith("hora") else 86400)
        transcurrido = (ahora - c["empezadaEn"]) / 1000
        if transcurrido >= segundos:
            return f"Se cumplio el tiempo de la condicion de parada ({m.group(1)} {unidad.rstrip('.')}{'' if unidad.endswith('s') or unidad in ('h', 'min') else 's'})"
    m = re.search(r"(\d+)\s*llamadas", t)
    if m and c["gasto"]["llamadas"] >= int(m.group(1)):
        return f"Se alcanzaron las {m.group(1)} llamadas de la condicion de parada"
    return None


def _informe(inv: dict[str, Any], it: dict[str, Any], resumen: str, hechos: list[dict], hipotesis: list[dict], afs: list[dict], bloqueadas: list[dict]) -> str:
    lineas = [f"# {inv['titulo']}: iteracion {it['numero']}", "", resumen, "", "## Plan ejecutado", T.plan_ejecutado(it), "", f"## Hechos nuevos ({len(hechos)})"]
    lineas += [f"- {h['enunciado']} <" + "; ".join(f"{p['referencia']}{', pag. ' + str(p['pagina']) if p['pagina'] else ''}" for p in h["procedencia"]) + ">" for h in hechos] or ["Ninguno"]
    lineas += ["", f"## Hipotesis nuevas en la cola ({len(hipotesis)})"] + ([f"- {h['titulo']}" for h in hipotesis] or ["Ninguna"])
    lineas += ["", f"## Afirmaciones ({len(afs)}), bloqueadas {len(bloqueadas)}"]
    for a in afs[:80]:
        lineas.append(f"- [{a['veredicto']}] {a['texto']} {a['cita']}" + (f" ({a['motivo']})" if a["veredicto"] != "sostenida" else ""))
    lineas += ["", "## Consultas hechas"] + [f"- {q['base']}: {q['consulta']} ({q['resultados']} resultados)" for q in []]
    return "\n".join(lineas)
