"""El supervisor y el bucle de cada corrida.

`Supervisor.correr()` es una tarea que vive mientras el servidor:
- Cada dos segundos mira el estado. Para cada corrida viva sin tarea, lanza
  `correr_corrida`. Autoaprueba planes si la corrida lo pide. Atiende lo que
  la investigadora dejó marcado: hipótesis "no puedo juzgar" (las aclara),
  comentarios enviados (los responde), revisiones pedidas, retractaciones a
  recomprobar, replicaciones en curso.
- Al arrancar, lo que quedó a medias por un reinicio se marca (pistas
  fallidas con motivo) y la iteración retoma en el primer paso pendiente.

`correr_corrida` es el bucle de una corrida:
  sin iteración o iteración cerrada -> proponer plan -> esperando_plan
  plan aprobado -> ejecutar pasos en orden (cada paso, sus pistas)
  sin pasos -> cerrar iteración (resumen, informe, evento, condición de parada)
Se detiene cuando la corrida pasa a detenida o terminada. Pausada, pausada
por presupuesto o esperando aprobación: espera sin gastar.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import contextlib
from datetime import datetime, timezone
from pathlib import Path
import re
import traceback
from typing import Any

from rosa import argumentacion as ARG
from rosa import cuestiones as CU
from rosa import dependencias as DEP
from rosa import sesgo as SESGO
from rosa import certeza as CERTEZA, config, lecciones as LEC, parada as PARADA, politicas, priorizacion as PR, progreso as PROG, torneo
from rosa import revisor_registro as RR
# ROSA2018, 16 de septiembre de 2026: ruta terapéutica por regla, contrato del
# experimento, mapa de la enfermedad, cifras de aprendizaje y perfil por diana.
from rosa import cifras_aprendizaje as CIFRAS, dianas as DI, experimento as XP, mapa_enfermedad as MAPA, ruta as RUTA
from rosa.bucle import contexto as T
from rosa.bucle import evidencia as EV
from rosa.bucle import pasos as PASOS
from rosa.bucle.pasos import Ctx
from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen
from rosa.fuentes import crossref
from rosa.fuentes.base import FuenteNoDisponible
from rosa.gateway import Modelos
from rosa.modulos.contador import ContextoLlamada, PresupuestoAgotado, contexto_actual, tope_agotado_en
from rosa.modulos.firmas import Programas

# Lo que cuesta de verdad cada tipo de paso, en llamadas al modelo, medido en
# la primera corrida real (10 de septiembre de 2026): el cribado de relevancia
# es una llamada por artículo, la extracción una por fragmento, el juez una
# por afirmación. El modelo que propone el plan no conoce este coste, así que
# su cifra se sustituye por esta.
COSTE_POR_TIPO = {"literatura": 70, "ensayos": 4, "extraccion": 60, "verificacion": 80, "novedad": 25, "modelo": 4, "hipotesis": 90, "analisis": 14, "meta": 4, "indicacion": 0}

PLAN_POR_DEFECTO = [
    ("Buscar literatura", "PubMed, Europe PMC y preprints sobre las preguntas abiertas", "literatura", 30),
    ("Extraer afirmaciones con procedencia", "Un fragmento a la vez, cada afirmación con su cita literal", "extraccion", 40),
    ("Verificar cada afirmación", "Comprobaciones deterministas y juez", "verificacion", 30),
    ("Actualizar el modelo de mundo", "Hechos sostenidos y preguntas abiertas", "modelo", 5),
    ("Generar y revisar hipótesis", "Nuevas hipótesis a la cola, revisión inicial, supuestos y torneo", "hipotesis", 20),
    ("Comprobar novedad", "Open Targets, ClinicalTrials.gov y precedente en OpenAlex", "novedad", 10),
]


class Supervisor:
    def __init__(self, almacen: Almacen, programas: Programas, modelos: Modelos):
        self.almacen = almacen
        self.programas = programas
        self.modelos = modelos
        self.tareas: dict[str, asyncio.Task] = {}
        self._parar = asyncio.Event()
        # Reloj de cada corrida viva en memoria (segundos de trabajo, espera humana,
        # pausas): se vuelca al estado como mucho cada RELOJ_VOLCADO_MS o cuando la
        # corrida cambia de estado, en vez de una mutación de 17 MB cada 5 s (S-17).
        self._reloj: dict[str, dict[str, Any]] = {}
        # Tareas de corrida que murieron con excepción: cuántas veces seguidas y
        # cuándo, para relanzarlas con retroceso y no cada 2 s (S-14).
        self._fallos: dict[str, dict[str, Any]] = {}

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
            # Una ejecución in silico a medias no se repite sola (evitar ejecución
            # duplicada tras un reinicio): queda como error técnico con motivo.
            for run in e.get("ejecuciones", []):
                if run["estado"] == "en_curso":
                    run["estado"] = "error_tecnico"
                    run["error"] = "Interrumpida por un reinicio de Rosa. No se repite sola: pide el análisis otra vez si hace falta."
                    run["fin"] = ahora
                    cambiado = True
            for r in e.get("reproducciones", []):
                if r["estado"] == "en_curso":
                    r["estado"] = "error_tecnico"
                    r["_error"] = "Interrumpida por un reinicio"
                    cambiado = True
            # Migración idempotente (S-16): la serie de progreso cuenta las hipótesis
            # nuevas por ventana de fecha, no por número de iteración. Volver a
            # pasarla no cambia nada, así que corre en cada arranque.
            try:
                if PROG.recalcular_progreso(e):
                    cambiado = True
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            # Saneamiento (S-08): toda hipótesis viva cuya evidencia cambió desde su
            # última decisión del Killer vuelve a la cola de revisión.
            try:
                if pedir_revision_por_huella(e, ahora):
                    cambiado = True
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            return cambiado or False

        self.almacen.mutar(fn, "recuperacion")
        for c in self.almacen.estado["corridas"]:
            if c["estado"] not in ("detenida", "terminada"):
                self.almacen.mutar(lambda e, c=c: A.con_evento(e, c["investigacionId"], "corrida_estado", f"Rosa volvió a arrancar; la corrida {c['numero']} retoma donde estaba", None, ahora) or True, "evento")

    async def correr(self) -> None:
        self.recuperar_tras_reinicio()
        while not self._parar.is_set():
            try:
                self._tick()
                await self._atender_peticiones()
                await self._vigilar_si_toca()
                await self._indexar_si_toca()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._parar.wait(), timeout=2.0)
        for t in self.tareas.values():
            t.cancel()
        # Esperar a que las tareas terminen sus finally (escriben en el almacen)
        # antes de que main cierre SQLite.
        if self.tareas:
            await asyncio.gather(*self.tareas.values(), return_exceptions=True)
        # El reloj que quedó en memoria se escribe antes de cerrar.
        with contextlib.suppress(Exception):
            self._volcar_reloj(P.ahora_ms(), todas=True)

    def parar(self) -> None:
        """Pide parar: el bucle no arranca trabajo nuevo (peticiones, vigilancia,
        índice) y main.py deja terminar lo que va en vuelo hasta su tope."""
        self._parar.set()

    def _cerrando(self) -> bool:
        return self._parar.is_set()

    async def _indexar_si_toca(self) -> None:
        """Índice semántico del registro (rosa/indice_semantico.py): incrusta lo
        nuevo o cambiado cada diez minutos. Céntimos; sin clave no hace nada."""
        from rosa import indice_semantico

        ahora = P.ahora_ms()
        if self._cerrando() or ahora - getattr(self, "_ultima_indexacion", 0) < 10 * 60 * 1000:
            return
        self._ultima_indexacion = ahora
        try:
            n = await indice_semantico.indexar_estado(self.almacen)
            if n:
                print(f"Índice semántico: {n} textos nuevos o cambiados incrustados")
        except Exception:  # noqa: BLE001
            traceback.print_exc()

    async def _vigilar_si_toca(self) -> None:
        """Vigilancia de literatura (rosa/vigilancia.py): una pasada por hora;
        cada hipótesis viva se comprueba como mucho una vez al día. Sin Exa no
        hace nada. Un fallo no tumba el bucle."""
        from rosa import vigilancia

        ahora = P.ahora_ms()
        ultima = getattr(self, "_ultima_vigilancia", 0)
        if self._cerrando() or ahora - ultima < 3600 * 1000:
            return
        self._ultima_vigilancia = ahora
        try:
            resumen = await vigilancia.vigilar(self.almacen, ahora)
            if resumen["comprobadas"] or resumen["errores"] or resumen.get("retiradas"):
                print(f"Vigilancia de literatura: {resumen['comprobadas']} hipótesis comprobadas, {resumen['conNovedades']} con novedades ({resumen['nuevas']} publicaciones), {resumen['costeUsd']} USD, {resumen['errores']} sin respuesta, {resumen.get('retiradas', 0)} novedades retiradas por no nombrar la hipótesis")
        except Exception:  # noqa: BLE001
            traceback.print_exc()

    # -- por tick --------------------------------------------------------------

    def _tick(self, ahora: int | None = None) -> None:
        e = self.almacen.estado
        ahora = ahora if ahora is not None else P.ahora_ms()
        for c in e["corridas"]:
            if c["estado"] in ("detenida", "terminada"):
                continue
            t = self.tareas.get(c["id"])
            if t is None or t.done():
                if not self._puede_relanzar(c, t, ahora):
                    continue
                self.tareas[c["id"]] = asyncio.create_task(self.correr_corrida(c["id"]), name=f"corrida-{c['id']}")
        # El reloj se lleva en memoria; solo se escribe cuando toca volcarlo.
        volcar = self._reloj_en_memoria(e, ahora)
        # Autoaprobación de planes, reloj volcado y salida de "esperando aprobación".

        def fn(e2: dict[str, Any]) -> bool:
            cambiado = False
            for c in e2["corridas"]:
                if c["id"] in volcar and self._escribir_reloj(c, ahora):
                    cambiado = True
                # Una corrida detenida por una persona también cierra con su métrica.
                if c["estado"] in ("detenida", "terminada") and c.get("metrica") is None and c.get("progreso"):
                    c["metrica"] = PROG.metrica_de_corrida(e2, c["id"])
                    cambiado = True
                if c["estado"] in ("detenida", "terminada"):
                    continue
                if c["estado"] == "esperando_plan" and c["autoAprobarPlanSegundos"] is not None:
                    it = A.iteracion_actual_de(e2, c)
                    if it and not it["planAprobado"] and ahora - it["planPropuestoEn"] >= c["autoAprobarPlanSegundos"] * 1000 and c["estado"] not in ("detenida", "terminada"):
                        it["planAprobado"] = True
                        it["empezadaEn"] = ahora
                        c["estado"] = "en_marcha"
                        A.con_evento(e2, c["investigacionId"], "corrida_estado", f"Plan de la iteración {it['numero']} autoaprobado tras {c['autoAprobarPlanSegundos']} s sin respuesta", None, ahora)
                        cambiado = True
                if c["estado"] == "esperando_aprobacion":
                    pendientes = any(s["corridaId"] == c["id"] and s["estado"] == "pendiente" for s in e2["solicitudes"]) or any(i["corridaId"] == c["id"] and i["estado"] == "pendiente" and i["tipo"] not in INCIDENCIAS_QUE_NO_BLOQUEAN for i in e2["incidencias"])
                    if not pendientes:
                        c["estado"] = "en_marcha"
                        cambiado = True
            return cambiado or False

        self.almacen.mutar(fn, "tick")

    # -- reloj en memoria (S-17) ----------------------------------------------

    def _reloj_en_memoria(self, e: dict[str, Any], ahora: int) -> set[str]:
        """Acumula en `self._reloj` la espera humana, las pausas y los segundos de
        trabajo de cada corrida viva, y devuelve los ids cuyo reloj toca volcar al
        estado: han pasado RELOJ_VOLCADO_MS desde el último volcado, la corrida
        cambió de estado, o acaba de terminar (para que su balance sea exacto)."""
        volcar: set[str] = set()
        vivos = {c["id"] for c in e["corridas"]}
        for cid in list(self._reloj):
            if cid not in vivos:
                self._reloj.pop(cid, None)
                self._fallos.pop(cid, None)
        for c in e["corridas"]:
            cid = c["id"]
            r = self._reloj.get(cid)
            if c["estado"] in ("detenida", "terminada"):
                if r is not None:
                    volcar.add(cid)
                continue
            if r is None:
                r = self._reloj[cid] = {"estado": c["estado"], "esperaHumanaMs": int(c.get("esperaHumanaMs") or 0), "pausaMs": int(c.get("pausaMs") or 0), "_ultimoTic": None, "volcadoEn": ahora, "estadoVolcado": c["estado"]}
            r["estado"] = c["estado"]
            contabilizar_tiempo(r, ahora)
            r["segundos"] = round(tiempo_trabajo_ms({**c, "esperaHumanaMs": r["esperaHumanaMs"], "pausaMs": r["pausaMs"]}, ahora) / 1000)
            if ahora - int(r.get("volcadoEn") or 0) >= RELOJ_VOLCADO_MS or c["estado"] != r.get("estadoVolcado"):
                volcar.add(cid)
        return volcar

    def _escribir_reloj(self, c: dict[str, Any], ahora: int) -> bool:
        """Escribe en la corrida lo acumulado en memoria. Devuelve True si cambió algo."""
        r = self._reloj.get(c["id"])
        if r is None:
            return False
        cambiado = False
        for clave in ("esperaHumanaMs", "pausaMs"):
            if int(c.get(clave) or 0) != int(r.get(clave) or 0):
                c[clave] = int(r.get(clave) or 0)
                cambiado = True
        seg = int(r.get("segundos") if r.get("segundos") is not None else round(tiempo_trabajo_ms({**c, "esperaHumanaMs": r["esperaHumanaMs"], "pausaMs": r["pausaMs"]}, ahora) / 1000))
        if c["gasto"].get("segundos") != seg:
            c["gasto"]["segundos"] = seg
            cambiado = True
        r["volcadoEn"] = ahora
        r["estadoVolcado"] = c["estado"]
        if c["estado"] in ("detenida", "terminada"):
            self._reloj.pop(c["id"], None)
        return cambiado

    def _volcar_reloj(self, ahora: int, todas: bool = False) -> None:
        """Vuelca el reloj de todas las corridas con registro en memoria (al parar)."""
        ids = set(self._reloj) if todas else set()
        if not ids:
            return
        self.almacen.mutar(lambda e2: any([self._escribir_reloj(c, ahora) for c in e2["corridas"] if c["id"] in ids]) or False, "reloj")

    def _con_reloj(self, c: dict[str, Any]) -> dict[str, Any]:
        """La corrida con la espera humana y las pausas que hay en memoria, para
        que el tope en horas se compare con el valor al día y no con el volcado
        de hace medio minuto. Copia superficial: no toca el estado."""
        r = self._reloj.get(c["id"])
        if r is None:
            return c
        return {**c, "esperaHumanaMs": int(r.get("esperaHumanaMs") or 0), "pausaMs": int(r.get("pausaMs") or 0)}

    # -- relanzar con retroceso (S-14) -----------------------------------------

    def _puede_relanzar(self, c: dict[str, Any], t: asyncio.Task | None, ahora: int) -> bool:
        """Si la tarea de la corrida murió con una excepción, deja una incidencia
        visible y espera con retroceso (30 s, 60 s, 5 min) antes de relanzarla.
        Antes se relanzaba cada 2 s: la corrida decía "en marcha" para siempre,
        con un traceback por vuelta y dos escrituras del estado entero cada vez."""
        cid = c["id"]
        if t is None:
            return True
        if t.cancelled() or t.exception() is None:
            self._fallos.pop(cid, None)
            return True
        reg = self._fallos.get(cid)
        if reg is None or reg.get("tarea") is not t:
            ex = t.exception()
            traceback.print_exception(ex)
            n = 1 if reg is None or ahora - int(reg.get("relanzadaEn") or 0) > 10 * 60_000 else int(reg.get("n") or 0) + 1
            espera = RETROCESO_MS[min(n, len(RETROCESO_MS)) - 1]
            self._fallos[cid] = {"n": n, "en": ahora, "tarea": t, "espera": espera, "relanzadaEn": int((reg or {}).get("relanzadaEn") or 0)}
            with contextlib.suppress(Exception):
                self.almacen.mutar(lambda e2: _incidencia_bucle(e2, cid, ex, n, espera, ahora), "incidencia")
            return False
        if ahora - int(reg["en"]) < int(reg["espera"]):
            return False
        reg["relanzadaEn"] = ahora
        reg["tarea"] = None
        return True

    async def _atender_peticiones(self) -> None:
        """Lo que la investigadora dejó marcado y no requiere corrida en marcha."""
        e = self.almacen.estado
        for h in list(e["hipotesis"]):
            if self._cerrando():
                return  # Rosa está cerrando: nada nuevo al modelo
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
                # Una revisión pedida con la corrida parada no espera al siguiente paso
                # de hipótesis: revisión inicial, supuestos y Killer ahora.
                # Sin presupuesto en la corrida no se abre pista ni se cuenta intento: la
                # petición se cierra con una línea que dice qué pasó y cómo repetirla. Antes
                # la excepción del contador contaba como "el juez no respondió" y en tres
                # ticks (seis segundos) la revisión quedaba abandonada con el motivo falso.
                if tope_agotado_en(e, corrida["id"], corrida.get("iteracionActual")) is not None:
                    self.almacen.mutar(lambda e2: _abandonar_peticion_sin_presupuesto(e2, h["id"], corrida), "revision")
                    return
                texto_af, _ = T.afirmaciones_sostenidas(corrida.get("_afirmaciones", []))
                pista = ctx.pista(None, "modelo", f"Revisión pedida: {h['titulo'][:60]}", "Opus 5 (Killer)")
                decisiones_antes = _n_decisiones_killer(e, h["id"])
                intentos_antes = int(h.get("_killerIntentos") or 0)
                sin_presupuesto = False
                try:
                    await PASOS._revisar_hipotesis(ctx, h, texto_af[:8000], pista)
                    pista.cerrar("Revisión y Killer terminados")
                except PresupuestoAgotado:
                    sin_presupuesto = True
                    pista.fallar("Sin presupuesto en la corrida: la revisión pedida no se hizo")
                    self.almacen.mutar(lambda e2: _abandonar_peticion_sin_presupuesto(e2, h["id"], corrida), "revision")
                except Exception as ex:  # noqa: BLE001
                    traceback.print_exc()
                    pista.fallar(f"La revisión falló: {str(ex)[:160]}")
                finally:
                    # La marca se quita solo si el Killer llegó a decidir; si falló, la
                    # petición sigue viva hasta MAX_INTENTOS_KILLER intentos (S-08).
                    if not sin_presupuesto:
                        self.almacen.mutar(lambda e2: _cerrar_peticion_de_revision(e2, h["id"], decisiones_antes, intentos_antes), "revision")
                return
            if h.get("_analisisPedido") and (corrida["estado"] in ("detenida", "terminada", "esperando_plan") or A.iteracion_actual_de(e, corrida) is None):
                # Con la corrida parada, el análisis pedido no espera a un paso del plan.
                from rosa.bucle import analisis as AN

                p = h["_analisisPedido"]
                pista = ctx.pista(None, "modelo", f"Análisis pedido: {h['titulo'][:60]}", "Sandbox")
                try:
                    await AN.analizar_hipotesis(ctx, h, p["datasetId"], p.get("pregunta", ""), pista)
                except Exception as ex:  # noqa: BLE001
                    traceback.print_exc()
                    self.almacen.mutar(lambda e2: (next(x for x in e2["hipotesis"] if x["id"] == h["id"]).pop("_analisisPedido", None), True)[1], "analisis")
                    pista.fallar(f"El análisis fallo: {str(ex)[:160]}")
                else:
                    pista.cerrar("Análisis terminado")
                return
        for rep in [r for r in e.get("reproducciones", []) if r["estado"] == "pendiente"]:
            corrida = A.ultima_corrida_de(e, rep["investigacionId"])
            if corrida and (corrida["estado"] in ("detenida", "terminada", "esperando_plan") or A.iteracion_actual_de(e, corrida) is None):
                from rosa.bucle import analisis as AN

                ctx = self._ctx(corrida)
                pista = ctx.pista(None, "modelo", f"Reproducción: {rep['referencia'][:60]}", "Sandbox")
                try:
                    await AN.reproducir(ctx, rep, pista)
                except Exception as ex:  # noqa: BLE001
                    traceback.print_exc()
                    pista.fallar(f"La reproducción fallo: {str(ex)[:160]}")
                    self.almacen.mutar(lambda e2: AN._estado_rep(e2, rep["id"], "error_tecnico", None, None, str(ex)[:200]), "reproduccion")
                else:
                    pista.cerrar("Reproducción terminada")
                return
        for inv in list(e["investigaciones"]):
            if inv.get("_recomprobarRetracciones"):
                await self._recomprobar_retracciones(inv)
        for c in list(e.get("corridas", [])):
            if c.get("_revisarArnes") and c.get("estado") == "terminada":
                await self._revisar_arnes(c)
                return
        for cambio in list(e.get("aprendizaje", [])):
            if cambio.get("_evaluar"):
                await self._evaluar_cambio(cambio)
                return
            if cambio.get("_promover"):
                self._promover_programa(cambio)
        await self._completar_en_llano()

    async def _revisar_arnes(self, c: dict[str, Any]) -> None:
        """Meta-campaña (lo que rekursiv.ai llama auto-autoresearch, aquí con
        puerta): al terminar una corrida, el cerebro lee cómo rindió y propone
        hasta tres cambios del arnés. Un criterio entra como cambio de nivel 2
        propuesto y se evalúa solo contra las decisiones humanas
        (`_evaluar_cambio`): si empeora el acuerdo, `_fijar_evaluacion` lo revierte
        sin que nadie lo pida; si iguala o mejora, queda evaluado y lo promueve una
        persona (puerta "solo mejor o igual" en promover_aprendizaje). Una política
        queda registrada como nivel 3 para que la decida una persona. Los prompts no
        se tocan aquí."""
        e = self.almacen.estado
        inv = next((i for i in e["investigaciones"] if i["id"] == c["investigacionId"]), None)
        ahora = P.ahora_ms()
        if not inv:
            self.almacen.mutar(lambda e2: _quitar_marca_arnes(e2, c["id"]), "aprendizaje")
            return
        progreso = "\n".join(f"- iteración {p.get('iteracion')}: {p.get('peldanosSubidos', 0)} peldaños subidos, {p.get('peldanosBajados', 0)} bajados, {p.get('hechosNuevos', 0)} hechos nuevos, {p.get('hipotesisNuevas', 0)} hipótesis nuevas, fallidos {json.dumps(p.get('fallidos') or {}, ensure_ascii=False)}, {p.get('usdAcumulado', 0)} USD acumulados" for p in c.get("progreso") or []) or "Sin iteraciones cerradas"
        hallazgos: dict[str, int] = {}
        for it in e.get("iteraciones", []):
            if it.get("corridaId") == c["id"]:
                for hz in ((it.get("revisionRegistro") or {}).get("hallazgos") or []):
                    hallazgos[str(hz.get("clase", "otro"))] = hallazgos.get(str(hz.get("clase", "otro")), 0) + 1
        try:
            lecciones_txt = LEC.texto_de(LEC.recientes(e, inv["id"], maximo=12), maximo=12) or "Ninguna"
        except Exception:  # noqa: BLE001
            lecciones_txt = "Ninguna"
        ctx = self._ctx(c)
        try:
            pred = await ctx.llamar(
                "cerebro",
                self.programas.revisar_arnes,
                objetivo=inv["objetivo"],
                metrica=f"{PROG.resumen_metrica(c.get('metrica')) or 'sin métrica'}. Detalle: {json.dumps(c.get('metrica') or {}, ensure_ascii=False)[:1500]}",
                progreso=progreso,
                lecciones=lecciones_txt,
                hallazgos_revisor="\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in sorted(hallazgos.items())) or "Ninguno",
                criterios_actuales="\n".join(e.get("criteriosRevision", [])) or "Ninguno",
                politicas_actuales=json.dumps(politicas.resumen(), ensure_ascii=False)[:1500],
                arnes=json.dumps(c.get("arnes") or {}, ensure_ascii=False),
            )
            diagnostico = (getattr(pred, "diagnostico", "") or "").strip()
            propuestas = [{"tipo": getattr(p_, "tipo", ""), "descripcion": (getattr(p_, "descripcion", "") or "").strip(), "motivo": (getattr(p_, "motivo", "") or "").strip(), "riesgo": (getattr(p_, "riesgo", "") or "").strip()} for p_ in list(getattr(pred, "propuestas", []) or [])]
        except PASOS.PresupuestoAgotado:
            self.almacen.mutar(lambda e2: _quitar_marca_arnes(e2, c["id"], "sin presupuesto para la meta-campaña"), "aprendizaje")
            return
        except Exception as ex:  # noqa: BLE001
            traceback.print_exc()
            self.almacen.mutar(lambda e2: _quitar_marca_arnes(e2, c["id"], f"el cerebro no respondió: {str(ex)[:120]}"), "aprendizaje")
            return

        def fn(e2: dict[str, Any]) -> bool:
            c2 = next((x for x in e2["corridas"] if x["id"] == c["id"]), None)
            if not c2:
                return False
            c2.pop("_revisarArnes", None)
            nuevos = cambios_desde_propuestas(e2, c2, propuestas, ahora)
            c2["revisionArnes"] = {"fecha": ahora, "diagnostico": diagnostico[:600], "propuestas": len(nuevos), "descartadas": len(propuestas) - len(nuevos)}
            texto = f"Meta-campaña de la corrida {c2['numero']}: {diagnostico[:200]}" + (f" Propone {len(nuevos)} {'cambio' if len(nuevos) == 1 else 'cambios'} del arnés; los criterios se evalúan solos y una persona decide." if nuevos else " Sin cambios que proponer.")
            A.con_evento(e2, c2["investigacionId"], "aprendizaje", texto, "#/ajustes", ahora)
            return True

        self.almacen.mutar(fn, "aprendizaje")

    async def _reformular_por_persona(self, ctx: Ctx, h: dict[str, Any]) -> None:
        """La persona pidió refinar: Rosa reformula como versión nueva con su
        nota, y el Killer vuelve a juzgar la versión nueva."""
        nota = h.get("_reformularPedida") or "La persona pidió refinarla"
        texto_af, _ = T.afirmaciones_sostenidas(ctx.corrida().get("_afirmaciones", []))
        pista = ctx.pista(None, "modelo", f"Reformular a petición: {h['titulo'][:60]}", "GPT-6 Astra + Opus 5")
        try:
            if not politicas.puede_reformular(h.get("version", 1)):
                # A petición de una persona no se descarta por agotar reformulaciones: se le dice.
                pista.cerrar(f"La hipótesis ya está en la versión {h.get('version', 1)} y la política no permite más reformulaciones automáticas; editala o duplicala a mano")
                self.almacen.mutar(lambda e2: (next((x for x in e2["hipotesis"] if x["id"] == h["id"]), {}).get("procedencia", {}).get("mensajes", []).append({"id": P.nuevo_id("m"), "de": "rosa", "texto": f"No se reformuló: versión {h.get('version', 1)}, tope de {politicas.MAX_REFORMULACIONES} reformulaciones. Nota de la persona: {nota[:200]}", "creadoEn": P.ahora_ms()}), True)[1], "reformular")
                return
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
            self.almacen.mutar(lambda e2: (next((x for x in e2["hipotesis"] if x["id"] == h["id"]), {}).pop("_reformularPedida", None), next((x for x in e2["hipotesis"] if x["id"] == h["id"]), {}).pop("_revisionPedida", None), True)[2], "reformular")

    async def _evaluar_cambio(self, cambio: dict[str, Any]) -> None:
        """Evaluación de un criterio propuesto (nivel 2) sobre el conjunto
        reservado: las hipótesis con decisión humana de aceptar o descartar.
        Se corre el Killer con y sin el criterio y se mide el acuerdo con
        la persona (avanzar = aceptar; descartar o reformular = descartar).
        La cifra va al registro; la promoción sigue siendo de la persona."""
        e = self.almacen.estado
        # Conjunto reservado: solo hipótesis con decisión de una PERSONA (registro de
        # decisiones, etapa persona), nunca las que descarto el propio Killer.
        con_persona = {d["hipotesisId"] for d in e.get("decisiones", []) if d.get("etapa") == "persona" and d.get("decision") in ("aceptada", "descartada")}
        reservado = [h for h in e["hipotesis"] if h["estado"] in ("aceptada", "descartada") and h["id"] in con_persona][:6]
        ahora = P.ahora_ms()
        if not reservado:
            self.almacen.mutar(lambda e2: _fijar_evaluacion(e2, cambio["id"], {"conjunto": "hipótesis con decisión humana", "casos": 0, "antes": None, "despues": None, "nota": "Sin conjunto reservado todavía: hacen falta hipótesis aceptadas o descartadas por una persona"}, ahora), "aprendizaje")
            return
        corrida = A.ultima_corrida_de(e, cambio.get("investigacionId") or reservado[0]["investigacionId"]) or A.ultima_corrida_de(e, reservado[0]["investigacionId"])
        if not corrida:
            return
        # Sin presupuesto en la corrida no hay cifra. Si la corrida sigue viva se
        # pausa y la marca `_evaluar` espera a que lo amplíen; si ya terminó o está
        # detenida nadie va a ampliarlo: la evaluación queda incompleta (el criterio
        # sigue propuesto y el botón de evaluar, disponible). Antes la excepción del
        # contador ponía una corrida terminada en "pausada por presupuesto" y se
        # volvía a intentar en cada tick.
        tope = tope_agotado_en(e, corrida["id"], corrida.get("iteracionActual"))
        if tope is not None:
            self._sin_presupuesto_para_evaluar(corrida, cambio, len(reservado), ahora, tope)
            return
        ctx = self._ctx(corrida)
        from rosa import killer as K

        async def acuerdo_con(criterios: list[str]) -> dict[str, Any]:
            """El acuerdo del Killer con la persona, hipótesis por hipótesis:
            `acuerdos` es un diccionario id -> True/False solo con las que el juez
            llegó a juzgar; `fallos` cuenta las que no respondió. Un fallo del juez
            no es un desacuerdo: antes contaba como tal y el registro medía cuántas
            veces se cayó el gateway (S-24)."""
            acuerdos: dict[str, bool] = {}
            fallos = 0
            for h in reservado:
                inv = next(i for i in e["investigaciones"] if i["id"] == h["investigacionId"])
                deterministas = K.comprobaciones_deterministas(h, e)
                try:
                    pred = await ctx.llamar("juez", self.programas.killer, objetivo=inv["objetivo"], mision=PASOS._texto_mision(inv), hipotesis=T.hipotesis_texto(h) + "\n" + K.texto_tarjeta(h) + "\n" + DI.texto_perfil(h.get("perfilDiana")), afirmaciones="\n".join(f"- [{a['veredicto']}, {a['tipo']}] {a['texto']} {a['cita']}" for a in h["afirmaciones"]) or "Ninguna", supuestos="\n".join(f"- [{s['estado']}] {s['texto']}" for s in h["supuestos"]) or "Sin supuestos", modelo_de_mundo=T.modelo_de_mundo(e["hechos"], h["investigacionId"], maximo=30), comprobaciones_deterministas="\n".join(f"- {c['comprobacion']}: {c['resultado']}. {c['detalle']}" for c in deterministas), criterios_revision="\n".join(criterios))
                    comprobaciones = K.fusionar(deterministas, [{"comprobacion": c.comprobacion, "resultado": c.resultado, "detalle": c.detalle} for c in pred.revision.comprobaciones])
                    decision, _ = K.decidir(comprobaciones, bool((h.get("tarjeta") or {}).get("prediccionFalsable")), 1)
                except PresupuestoAgotado:
                    raise
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
                    fallos += 1
                    continue
                humana = h["estado"] == "aceptada"
                acuerdos[h["id"]] = (decision == "avanzar") == humana
            return {"acuerdos": acuerdos, "fallos": fallos, "juzgadas": len(acuerdos)}

        casos = len(reservado)
        try:
            sin = [c for c in e["criteriosRevision"] if c != cambio["descripcion"]]
            r_antes = await acuerdo_con(sin)
            # Si la primera pasada ya tuvo fallos, la cifra no va a ser comparable:
            # no se gastan otras seis llamadas al juez en la segunda.
            if r_antes["fallos"]:
                evaluacion = {"conjunto": "hipótesis con decisión humana", "casos": casos, "juzgadas": r_antes["juzgadas"], "sinRespuesta": r_antes["fallos"], "antes": None, "despues": None, "nota": f"{r_antes['fallos']} de {casos} sin respuesta del juez en la pasada de referencia; la segunda pasada no se hizo. Vuelve a evaluar cuando el juez responda"}
            else:
                evaluacion = evaluacion_pareada(r_antes, await acuerdo_con(sin + [cambio["descripcion"]]), casos)
        except PresupuestoAgotado:
            self._sin_presupuesto_para_evaluar(corrida, cambio, casos, ahora, None)
            return
        except Exception as ex:  # noqa: BLE001
            evaluacion = {"conjunto": "hipótesis con decisión humana", "casos": casos, "juzgadas": 0, "sinRespuesta": casos, "antes": None, "despues": None, "nota": f"La evaluación falló: {str(ex)[:120]}"}
        self.almacen.mutar(lambda e2: _fijar_evaluacion(e2, cambio["id"], evaluacion, ahora), "aprendizaje")

    def _sin_presupuesto_para_evaluar(self, corrida: dict[str, Any], cambio: dict[str, Any], casos: int, ahora: int, tope: str | None) -> None:
        """Qué se hace con una evaluación de criterio que se queda sin presupuesto:
        con la corrida viva, pausarla (la marca `_evaluar` se queda para cuando lo
        amplíen); con la corrida detenida o terminada, dejar la evaluación como
        incompleta, con su nota, para no reintentarla en cada tick."""
        if corrida["estado"] in ("detenida", "terminada"):
            self.almacen.mutar(lambda e2: _fijar_evaluacion(e2, cambio["id"], _evaluacion_sin_presupuesto(corrida, casos), ahora), "aprendizaje")
        else:
            self.almacen.mutar(lambda e2: _pausar_por_presupuesto(e2, corrida["id"], tope), "presupuesto")

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
                nota = f"No se encontró el candidato {origen.name}; nada que promover"
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

    async def _explicar_en_llano(self, ctx: Ctx, inv: dict[str, Any], resumen: str, hechos: list[dict], hipotesis: list[dict], sin_comprobar: list[dict], cola: str | None = None) -> dict[str, Any] | None:
        """El resumen de la iteración en lenguaje llano, con la estructura de los
        Plain Language Summary de Cochrane. Si el modelo falla, se queda sin
        resumen (la pantalla lo dice) y no se inventa nada.

        `hipotesis` son solo las nacidas en la iteración; `cola` es el listado
        por regla de toda la cola (título, estado, decisión del Killer con su
        motivo real y fecha de nacimiento). Antes el modelo solo veía las nuevas y
        escribía "quedan en cola dos hipótesis" cuando había nueve, con un motivo
        de suspensión inventado (S-16). La frase de recuento va aparte, en
        `colaPorRegla`, y el modelo no la toca."""
        e = self.almacen.estado
        c = ctx.corrida()
        propias = [h for h in e["hipotesis"] if h["investigacionId"] == inv["id"]]
        cola = cola if cola is not None else cola_de_hipotesis(e, inv["id"])
        frase_cola = frase_de_la_cola(e, inv["id"], len(hipotesis))
        conclusiones = []
        for h in propias:
            k = h.get("conclusion")
            if k:
                cambio = f" (antes: {k['cambio']['de']['certeza']}, {k['cambio']['de']['direccion']})" if k.get("cambio") else ""
                conclusiones.append(f"- {h['titulo']}: certeza {k['certeza']}, dirección {k['direccion']}{cambio}")
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
                estado_hipotesis=estado_de_la_cola(e, inv["id"]),
                cola=cola,
                sin_comprobar="\n".join(f"- {x.get('texto') or x.get('titulo')}" for x in sin_comprobar) or "Nada",
                conclusiones="\n".join(conclusiones) or "Ninguna hipótesis todavía",
                busqueda=busqueda,
            )
            r = pred.resumen
            return {
                "colaPorRegla": frase_cola,
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
        except PresupuestoAgotado:
            raise  # el cierre pausa la corrida y retoma el llano al ampliar (S-14)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return None

    async def _hipotesis_en_llano(self, ctx: Ctx, h: dict[str, Any]) -> None:
        c = h["comprobacion"]
        try:
            pred = await ctx.llamar("volumen", self.programas.hipotesis_en_llano, titulo=h["titulo"], enunciado=h["enunciado"], mecanismo=h["mecanismo"], comprobacion=f"Biomarcador: {c['biomarcador']}. Cohorte: {c['cohorte']}. Diseño: {c['diseno']}", relevancia=h["relevancia"]["justificacion"])
            texto = pred.explicacion.strip()
        except PresupuestoAgotado:
            raise  # sin marcar la bandera: se reintenta cuando haya presupuesto
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
        """El experimento o análisis que comprobaría la hipótesis. Queda como
        `experimento` en estado 'propuesto'; la persona lo asigna a un
        laboratorio o registra los datos cuando llegan."""
        inv = next((i for i in self.almacen.estado["investigaciones"] if i["id"] == h["investigacionId"]), None)
        try:
            from rosa import killer as K
            from rosa import skills as SK

            # La misión (capacidades del laboratorio, conocimiento operativo) y la skill de
            # tamaño muestral entran al proponente: antes no las recibía y el n salía "no estimable".
            skills_exp = SK.para_texto(f"{h.get('titulo', '')} {h.get('enunciado', '')} experimento protocolo ensayo tamaño muestral potencia", contexto="mision")
            pred = await ctx.llamar(
                "cerebro",
                self.programas.experimento,
                hipotesis=T.hipotesis_texto(h) + "\n" + K.texto_tarjeta(h) + "\n" + DI.texto_perfil(h.get("perfilDiana")),
                afirmaciones="\n".join(f"- [{a['veredicto']}] {a['texto']} {a['cita']}" for a in h["afirmaciones"]) or "Ninguna (hipótesis humana)",
                limites="; ".join(inv["limites"]) if inv and inv["limites"] else "Ninguno declarado",
                mision=PASOS._texto_mision(inv) if inv else "Sin misión aprobada",
                skills=SK.texto_para_prompt(skills_exp),
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
            # El contrato del experimento (rosa/experimento.py): lecturas separadas
            # (qué se mide, qué la confirma y qué la refuta), sistema experimental con
            # lo que no representa, propósito BEST del biomarcador, nivel del desenlace
            # y puente al beneficio. Una firma antigua sin esos campos deja los valores
            # vacíos y la lista de problemas lo dice; no rompe.
            _anadir_contrato(experimento, x)
        except PresupuestoAgotado:
            raise  # sin marcar la bandera: se reintenta cuando haya presupuesto
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
                y["procedencia"]["registro"].append(_linea_contrato(experimento))
                A.recalcular_bloqueos(e, y)
            return True

        self.almacen.mutar(fn, "experimento")

    async def _concluir_hipotesis(self, ctx: Ctx, h: dict[str, Any]) -> None:
        """La conclusión provisional de Rosa sobre la hipótesis con lo que hay.
        La escribe el juez. Se rehace al cerrar una iteración solo si cambió la
        huella de la evidencia contada (`huella_de_conclusion`), que se guarda en
        `conclusion.huella`; la dirección la fija la regla (`direccion_por_regla`)
        y la del juez queda aparte en `direccionDelJuez`."""
        huella = huella_de_conclusion(h)
        try:
            pred = await ctx.llamar(
                "juez",
                self.programas.concluir,
                hipotesis=T.hipotesis_texto(h),
                afirmaciones="\n".join(f"- [{a['veredicto']}, {a['tipo']}, clase {a.get('clase', 'literatura')}{', SINTÉTICO: no cuenta como evidencia' if a.get('sintetico') else ''}{MARCA_RELACION.get(a.get('relacion'), '')}{', añadida en la iteración ' + str(a['iteracion']) if a.get('relacion') and a.get('iteracion') else ''}{', cohorte ' + a['cohorte'] if a.get('cohorte') else ''}] {a['texto']} {a['cita']}" for a in h["afirmaciones"]) or "Ninguna",
                supuestos="\n".join(f"- [{s['estado']}] {s['texto']} ({s['evidencia']})" for s in h["supuestos"]) or "Sin supuestos evaluados",
                partidos="\n".join(f"- {p['resultado']} por {p['ejeDecisivo']}: {p['resumenDebate']}" for p in h["partidos"]) or "Sin partidos todavía",
                novedad="; ".join(f"{k}: {v['detalle']}" for k, v in h["novedad"].items()) + f". Cohortes distintas entre las fuentes: {len(PR.cohortes_de(h))}" + (f" ({', '.join(PR.cohortes_de(h))})" if PR.cohortes_de(h) else "") + ". " + SESGO.texto_para_grade(h["procedencia"]["fuentes"]),
                revisiones_humanas=T.revisiones_humanas(h) + (f"\nKiller: {h.get('decisionKiller')}" if h.get("decisionKiller") else ""),
                resultado_experimental=T.resultado_experimental(h),
                techo_por_regla=_texto_techo_por_regla(h),
            )
            c = pred.conclusion
            # La base se cuenta de forma determinista, no la estima el modelo. Lo
            # sintético no cuenta como evidencia.
            sostenidas = [a for a in h["afirmaciones"] if a["veredicto"] in ("sostenida", "parcial") and not a.get("sintetico")]
            fuentes = {f["referencia"] for f in h["procedencia"]["fuentes"]}
            anterior = h.get("conclusion")
            # El nivel del juez queda bajo el techo por regla (rosa/certeza.py): solo
            # literatura de una cohorte no pasa de muy baja; sin datos reales, de baja.
            factores = [{"factor": f.factor, "efecto": f.efecto, "explicacion": f.explicacion.strip()} for f in c.factores][:8]
            acotada = CERTEZA.acotar(c.certeza, h, factores)
            certeza_final = acotada["certeza"]
            # La dirección por regla (M-07): "mixta" o "en contra" solo con alguna
            # afirmación sostenida en contra o un resultado que refuta; lo que dijo el
            # juez se guarda aparte y, si discrepa, la frase lo dice.
            direccion_juez = str(getattr(c, "direccion", "") or "")
            direccion, supuesto_contradicho = direccion_por_regla(h, direccion_juez)
            cambio = None
            if anterior and (anterior.get("certeza") != certeza_final or anterior.get("direccion") != direccion):
                cambio = {"de": {"certeza": anterior.get("certeza"), "direccion": anterior.get("direccion"), "iteracion": anterior.get("iteracion")}, "motivo": (c.factores[0].explicacion.strip() if c.factores else "")}
            no_comprobado = [f"{k}: {v['detalle']}" for k, v in h["novedad"].items() if str(v.get("detalle", "")).startswith("No comprobado") and k != "agora"]
            consultas = ctx.corrida()["busqueda"]["consultas"]
            conclusion = {
                "certeza": certeza_final,
                "techo": acotada["techo"],
                "escalera": CERTEZA.escalera(h, certeza_final, factores),
                "direccion": direccion,
                "direccionDelJuez": direccion_juez,
                "hipotesisBreve": c.hipotesis_breve.strip(),
                "enunciado": frase_plantilla(direccion, certeza_final, c.hipotesis_breve.strip() or h["titulo"], supuesto_contradicho=supuesto_contradicho),
                "conclusion": c.conclusion.strip(),
                "factores": factores,
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
                "huella": huella,
            }
        except PresupuestoAgotado:
            raise  # sin marcar la bandera: se reintenta cuando haya presupuesto
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
                if conclusion.get("direccionDelJuez") and conclusion["direccionDelJuez"] != conclusion["direccion"]:
                    y["procedencia"]["registro"].append(f"iteración {ctx.numero}: el juez propuso dirección «{conclusion['direccionDelJuez']}» y la regla la dejó en «{conclusion['direccion']}» (mixta o en contra solo con alguna afirmación en contra)")
                # La ruta terapéutica se recalcula aquí porque es el momento en que
                # cambia la evidencia contada (rosa/ruta.py, por regla, sin modelo).
                y["ruta"] = _ruta_segura(e, y)
                # La conclusión rehecha atiende lo pendiente de revisar (propagación de
                # dependencias) y el peldaño siguiente de la escalera queda como cuestión.
                if y.get("pendienteRevision"):
                    DEP.atender_pendiente(e, "hipotesis", y["id"], config.QUIEN_ROSA, "conclusión rehecha con la evidencia actual", conclusion["fecha"])
                    A.recalcular_bloqueos(e, y)
                # La huella se fija aquí, sobre la hipótesis ya atendida: calculada antes
                # (con `pendienteRevision` todavía puesto) el siguiente cierre la veía
                # distinta y pagaba otra conclusión sin evidencia nueva.
                conclusion["huella"] = huella_de_conclusion(y)
                escalera = conclusion.get("escalera") or []
                if escalera and escalera[0].get("falta") and y["estado"] != "descartada":
                    CU.desde_escalera(e, y, escalera[0]["falta"], conclusion["fecha"])
                if conclusion.get("cambio"):
                    # Nivel 1 del aprendizaje: cambio lo que Rosa cree de esta hipotesis. Automatico y registrado.
                    de = conclusion["cambio"]["de"]
                    e.setdefault("aprendizaje", []).append(P.nuevo_cambio_aprendizaje(y["investigacionId"], 1, "creencia", f"{y['titulo'][:80]}: de {de.get('certeza')}/{de.get('direccion')} a {conclusion['certeza']}/{conclusion['direccion']}. {conclusion['cambio']['motivo'][:160]}", f"hipotesis:{y['id']}", "aplicado", config.QUIEN_ROSA, conclusion["fecha"]))
            return True

        self.almacen.mutar(fn, "conclusion")

    async def _evaluar_resultado(self, ctx: Ctx, h: dict[str, Any]) -> None:
        """Cierra el loop: los datos del laboratorio se comparan con los
        criterios congelados en el prerregistro, el veredicto entra como
        afirmación de tipo dato con su trayectoria, y la conclusión se rehace."""
        from rosa import datos as D

        from rosa.dossier import APRENDIZAJE_POR_RESULTADO

        x = h["experimento"]
        ruta = D.ruta_de(h["id"], x.get("ficheroDatos") or "")
        ahora = P.ahora_ms()
        derivada_texto = None
        if ruta is None or not ruta.exists():
            resultado = {"veredicto": "no_evaluable", "clasificacion": "fallo_tecnico", "resultado": "No se encontró el fichero de datos en el servidor.", "motivo": f"Se registro el nombre '{x.get('ficheroDatos')}' pero el fichero no se subio. Sube el fichero desde la ficha.", "limitaciones": "", "cifras": [], "exploratorio": "", "fecha": ahora, "fichero": x.get("ficheroDatos")}
        cabecera = ""
        if ruta is not None and ruta.exists():
            resumen, muestra = await asyncio.to_thread(D.resumir, ruta)
            cabecera = muestra.splitlines()[0] if muestra else ""
            # Los datos del laboratorio no salen al modelo fila a fila: el juez recibe el
            # resumen agregado y solo la cabecera de la muestra.
            muestra = cabecera + "\n[filas omitidas: los datos individuales del laboratorio no se envían al modelo; el veredicto se apoya en el resumen agregado]"
            try:
                pred = await ctx.llamar(
                    "juez",
                    self.programas.evaluar_resultado,
                    hipotesis=T.hipotesis_texto(h),
                    prerregistro=f"Protocolo:\n{x['protocolo']}\n\nEnsayo: {x['ensayo']}\n\nControles: {x.get('controles') or 'no declarados'}\nTamano muestral previsto: {x.get('tamanoMuestral') or 'no declarado'}\n\nCONFIRMA si: {x.get('confirma') or '(no separado; ver ensayo)'}\nREFUTA si: {x.get('refuta') or '(no separado; ver ensayo)'}\n\n" + A.texto_protocolo_real(x),
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
        # Datos de prueba (S-18): si el experimento va marcado como ensayo en seco o
        # sintético, la subida lo declaró, o el nombre o la cabecera del fichero dicen
        # "sintético", el resultado nunca cuenta como observación original.
        sintetico = es_resultado_sintetico(x, resultado.get("fichero"), cabecera)
        resultado["sintetico"] = sintetico
        # Veredicto por lectura (rosa/experimento.py): cada lectura del contrato se
        # juzga por regla con la cifra que la nombra; sin cifra es "no pude comprobar".
        # Si el juez no llegó a responder (fichero ausente, fallo), no hay nada que
        # juzgar: lista vacía y rama None con su explicación.
        juez_respondio = not (resultado["veredicto"] == "no_evaluable" and clasificacion == "fallo_tecnico" and not resultado.get("cifras"))
        vs = _veredictos_por_lectura(x, resultado) if juez_respondio else []
        resultado["veredictosPorLectura"] = vs
        resultado["lecturaDelNegativo"] = _lectura_del_negativo(vs)
        # Un resultado prueba la versión que se prerregistró; si la hipótesis cambió
        # después, se dice y la conclusión actual lo tiene en cuenta.
        version_probada = x.get("versionPrerregistrada") or h.get("version", 1)
        resultado["versionProbada"] = version_probada
        resultado["compatibleConActual"] = version_probada == h.get("version", 1)
        if not resultado["compatibleConActual"]:
            resultado["limitaciones"] = (resultado.get("limitaciones") or "") + f" El resultado probo la versión {version_probada}; la hipótesis está en la versión {h.get('version', 1)}: comprobar que la predicción sigue siendo la misma."
        quien = self.modelos.juez.model

        def fn(e: dict[str, Any]) -> bool:
            y = next((z for z in e["hipotesis"] if z["id"] == h["id"]), None)
            if not y or not y.get("experimento"):
                return False
            y["experimento"]["resultado"] = resultado
            y["_resultadoEvaluado"] = True
            fecha_txt = datetime.fromtimestamp(ahora / 1000).strftime("%d/%m/%Y")
            if clasificacion in ("apoyo_reproducido", "negativo_interpretable", "inconcluso", "correccion_contexto") and resultado["veredicto"] != "no_evaluable":
                cita = f"[Datos de prueba, SINTÉTICOS: {resultado['fichero']}, {fecha_txt}]" if sintetico else f"[Datos del laboratorio: {resultado['fichero']}, {fecha_txt}]"
                af_lab_id = P.nuevo_id("af")
                y["afirmaciones"].append({"afirmacionId": af_lab_id, "texto": resultado["resultado"], "cita": cita, "veredicto": "sostenida", "motivo": f"Cifra calculada de los datos {'de prueba (sintéticos, no cuentan como evidencia)' if sintetico else 'del laboratorio'} contra el prerregistro: {resultado['veredicto']} ({clasificacion.replace('_', ' ')}).", "entidadDistinta": False, "tipo": "dato", "clase": "observacion_original", "sintetico": sintetico, "trayectoria": {"id": resultado["fichero"], "celda": 0}, "fragmento": resultado["motivo"]})
                y["evidenciaEstadistica"] = "no_aplica" if sintetico else ("fuerte" if clasificacion == "apoyo_reproducido" else ("moderada" if clasificacion == "negativo_interpretable" else "debil"))
                # El resultado del laboratorio entra al modelo de mundo como hecho (la ficha lo
                # prometía y el registro no lo cumplía): frena una hipótesis nueva con la misma predicción.
                # Uno sintético nunca entra: al modelo de mundo solo llegan afirmaciones reales.
                if clasificacion in ("apoyo_reproducido", "negativo_interpretable") and not sintetico:
                    hecho = P.nuevo_hecho(y["investigacionId"], "hecho", "Resultado de laboratorio", f"{resultado['resultado'][:500]} (ensayo sobre «{y['titulo'][:60]}»: {resultado['veredicto']})", "sabido", "laboratorio", [{"fuenteId": None, "referencia": cita, "pagina": None}], ahora, prioridad=1, motivo=f"Resultado del laboratorio contra el prerregistro: {clasificacion.replace('_', ' ')}",
                                          afirmacion_ids=[af_lab_id], citas=[{"referencia": cita, "seccion": "datos del laboratorio", "clasificacion": "apoya" if clasificacion == "apoyo_reproducido" else "contrasta", "fragmento": (resultado.get("motivo") or "")[:300]}])
                    hecho["hipotesisIds"] = [y["id"]]
                    e["hechos"].append(hecho)
                    A.con_evento(e, y["investigacionId"], "hecho_nuevo", f"Hecho nuevo del laboratorio: {resultado['resultado'][:120]}", f"#/investigaciones/{y['investigacionId']}/mundo", ahora)
            # Que hace Rosa con cada clase de resultado (taxonomia de retorno).
            if clasificacion == "fallo_tecnico":
                y["experimento"]["estado"] = "asignado"  # se puede repetir; la hipotesis no cambia
                y["experimento"]["ficheroDatos"] = None
            elif clasificacion == "toxicidad_inviabilidad":
                t = y.get("tarjeta") or P.tarjeta_vacia()
                t["riesgos"] = (t.get("riesgos") or []) + [f"Toxicidad o inviabilidad observada en el laboratorio ({fecha_txt}): {resultado['resultado'][:120]}"]
                y["tarjeta"] = t
                y["decisionKiller"] = "suspender"
                y["revisiones"].append({"fecha": ahora, "quien": quien, "accion": "suspendida", "nota": "Toxicidad o inviabilidad: la vía de intervención se cierra en este contexto", "aCiegas": False})
            elif clasificacion == "negativo_interpretable":
                y["hallazgos"].append({"id": P.nuevo_id("hal"), "tipo": "valor_contradice_fuente", "resumen": "El laboratorio devolvió un negativo interpretable", "razonamiento": resultado["resultado"], "estado": "abierto", "respuestaDeRosa": None})
            elif clasificacion == "correccion_contexto":
                y["decisionKiller"] = "suspender"
                y["revisiones"].append({"fecha": ahora, "quien": quien, "accion": "suspendida", "nota": "Corrección de contexto: el efecto aparece en otro contexto; se crea una hipótesis derivada", "aCiegas": False})
                if derivada_texto is not None:
                    d = derivada_texto
                    nueva = P.nueva_hipotesis(y["investigacionId"], ctx.numero, ahora, titulo=d.titulo.strip(), enunciado=d.enunciado.strip(), mecanismo=d.mecanismo.strip(), comprobacion={"biomarcador": d.biomarcador, "cohorte": d.cohorte, "diseno": d.diseno}, cluster=y["cluster"], derivadaDe=y["id"], relevancia={"justificacion": f"Derivada de '{y['titulo'][:60]}' por corrección de contexto del laboratorio: {d.que_cambio}", "votoHumano": None}, afirmaciones=[a for a in y["afirmaciones"] if a.get("clase") == "observacion_original"][-1:])
                    nueva["procedencia"] = P.procedencia_vacia(f"Hipótesis derivada por corrección de contexto tras el resultado del laboratorio del {fecha_txt}. {d.que_cambio}", ahora)
                    e["hipotesis"].append(nueva)
                    resultado["hipotesisDerivadaId"] = nueva["id"]
                    e.setdefault("aprendizaje", []).append(P.nuevo_cambio_aprendizaje(y["investigacionId"], 1, "hipotesis_derivada", f"Corrección de contexto: '{y['titulo'][:60]}' deriva en '{nueva['titulo'][:60]}'", f"resultado:{y['id']}", "aplicado", quien, ahora))
                    A.con_evento(e, y["investigacionId"], "hipotesis_nueva", f"Hipótesis derivada por corrección de contexto: {nueva['titulo'][:80]}", f"#/investigaciones/{y['investigacionId']}/hipotesis/{nueva['id']}", ahora)
            A.registrar_decision(e, y, "retorno", "avanzar" if clasificacion == "apoyo_reproducido" else ("suspender" if clasificacion in ("toxicidad_inviabilidad", "correccion_contexto") else ("reformular" if clasificacion == "negativo_interpretable" else "avanzar")), f"Retorno del laboratorio: {clasificacion.replace('_', ' ')}. {resultado['resultado'][:200]}", quien, ahora)
            e.setdefault("aprendizaje", []).append(P.nuevo_cambio_aprendizaje(y["investigacionId"], 1, "creencia", f"Resultado del laboratorio ({clasificacion.replace('_', ' ')}) para '{y['titulo'][:60]}': {resultado['accionTomada'][:160]}", f"resultado:{y['id']}", "aplicado", quien, ahora))
            y["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "revisor", "texto": f"Datos del laboratorio evaluados contra el prerregistro: {resultado['veredicto']} ({clasificacion.replace('_', ' ')}). {resultado['resultado']} Que hace Rosa: {resultado['accionTomada']}", "creadoEn": ahora})
            y["procedencia"]["registro"].append(f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} datos {resultado['fichero']} evaluados: {resultado['veredicto']} / {clasificacion}" + (" (SINTÉTICOS: datos de prueba, no cuentan como evidencia ni entran al modelo de mundo)" if sintetico else ""))
            y.pop("_conclusionIntentada", None)
            A.recalcular_bloqueos(e, y)
            A.con_evento(e, h["investigacionId"], "revision_automatica", f"Datos del laboratorio evaluados ({clasificacion.replace('_', ' ')}): {h['titulo'][:80]}", f"#/investigaciones/{h['investigacionId']}/hipotesis/{h['id']}", ahora)
            # El resultado del laboratorio toca los pasos de efecto funcional y de
            # selectividad y toxicidad de la ruta terapéutica: se recalcula.
            y["ruta"] = _ruta_segura(e, y)
            return True

        self.almacen.mutar(fn, "resultado_experimento")
        y = next((z for z in self.almacen.estado["hipotesis"] if z["id"] == h["id"]), None)
        if y:
            await self._concluir_hipotesis(ctx, y)

    async def _completar_en_llano(self) -> None:
        """Rellena lo que falte: hipótesis sin versión en llano e iteraciones
        cerradas sin resumen en llano (las anteriores a esta función). Una
        cosa por tick, para no competir con la corrida. Si el presupuesto se
        agota a mitad, se deja para cuando lo amplien (sin marcar nada)."""
        try:
            await self._completar_en_llano_paso()
        except PresupuestoAgotado:
            return

    async def _completar_en_llano_paso(self) -> None:
        e = self.almacen.estado

        def _puede_gastar(corrida: dict[str, Any] | None) -> bool:
            # Rellenar en segundo plano gasta llamadas: no se hace sobre corridas que
            # una persona detuvo ni sobre corridas pausadas por presupuesto.
            return bool(corrida) and corrida["estado"] not in ("detenida", "pausada_por_presupuesto", "pausada", "terminada")

        for h in e["hipotesis"]:
            x = h.get("experimento")
            if x and x.get("estado") == "datos_recibidos" and not h.get("_resultadoEvaluado"):
                corrida = A.ultima_corrida_de(e, h["investigacionId"])
                if corrida and corrida["estado"] != "pausada_por_presupuesto":
                    await self._evaluar_resultado(self._ctx(corrida), h)
                    return
            if h.get("enLlano") is None and not h.get("_enLlanoIntentado"):
                corrida = A.ultima_corrida_de(e, h["investigacionId"])
                if _puede_gastar(corrida):
                    await self._hipotesis_en_llano(self._ctx(corrida), h)
                    return
            if h.get("conclusion") is None and not h.get("_conclusionIntentada"):
                corrida = A.ultima_corrida_de(e, h["investigacionId"])
                if _puede_gastar(corrida):
                    await self._concluir_hipotesis(self._ctx(corrida), h)
                    return
            if h.get("experimento") is None and not h.get("_experimentoIntentado") and h["estado"] != "descartada":
                corrida = A.ultima_corrida_de(e, h["investigacionId"])
                if _puede_gastar(corrida):
                    await self._proponer_experimento(self._ctx(corrida), h)
                    return
            if h.get("tarjeta") is None and not h.get("_tarjetaIntentada") and h["estado"] != "descartada":
                corrida = A.ultima_corrida_de(e, h["investigacionId"])
                if _puede_gastar(corrida):
                    await PASOS._completar_tarjeta(self._ctx(corrida), h, None)
                    return
        for inv in e["investigaciones"]:
            if inv.get("mision") is None and not inv.get("_misionIntentada"):
                corrida = A.ultima_corrida_de(e, inv["id"])
                if _puede_gastar(corrida):
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
                hip = PROG.hipotesis_nacidas_en(e, inv["id"], it, origen="rosa")
                llano = await self._explicar_en_llano(ctx, inv, it["resumen"], hechos, hip, [p for p in it["plan"] if p["estado"] in ("fallido", "omitido")])

                def fn(e2: dict[str, Any], it=it, llano=llano) -> bool:
                    x = next((y for y in e2["iteraciones"] if y["id"] == it["id"]), None)
                    if not x:
                        return False
                    x["_llanoIntentado"] = True
                    if llano:
                        x["resumenLlano"] = llano
                        _anadir_aprendizaje_al_llano(e2, it["corridaId"], x)
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
            self.almacen.mutar(lambda e: A.aclarar_hipotesis(e, h["id"], f"No pude aclararla ahora: el modelo no respondió ({str(ex)[:100]}). Vuelve a la cola tal cual.", P.ahora_ms()), "aclarar")
            return
        self.almacen.mutar(lambda e: A.aclarar_hipotesis(e, h["id"], pred.aclaracion, P.ahora_ms()), "aclarar")

    async def _responder_comentarios(self, ctx: Ctx, h: dict[str, Any]) -> None:
        comentarios = [m["texto"] for m in h["procedencia"]["mensajes"] if m["de"] == "investigadora"][-3:]
        ahora = P.ahora_ms()
        try:
            pred = await ctx.llamar("cerebro", ctx.programas.responder, hipotesis=T.hipotesis_texto(h), comentarios="\n\n".join(comentarios), afirmaciones="\n".join(f"- [{a['veredicto']}] {a['texto']} {a['cita']}" for a in h["afirmaciones"]))
            respuesta, enunciado = pred.respuesta, pred.enunciado_revisado.strip()
        except Exception as ex:  # noqa: BLE001
            respuesta, enunciado = f"No pude responder ahora: el modelo no respondió ({str(ex)[:100]}).", h["enunciado"]

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
        """Una trayectoria de replicación: se vuelven a juzgar las afirmaciones
        de la hipótesis con el juez (temperatura alta) y se cuenta si el
        conjunto se sostiene (fidelidad >= 0,5 y nada bloqueante)."""
        from rosa import verificador as V

        # Las copias conservan `fuenteId`: la cita se resuelve primero por el id de la
        # fuente y el localizador (S-04); dos fuentes homónimas ya no se cruzan.
        copias = [dict(a, fragmento="", localizador="") for a in h["afirmaciones"]]
        frags = ctx.fragmentos_verificador()
        for a in copias:
            fr = V.resolver_cita(a["cita"], frags, a.get("fuenteId") or None)
            if fr:
                a["fragmento"], a["localizador"], a["fuenteId"], a["encabezado"] = fr.texto[:400], fr.localizador, fr.fuente_id, fr.encabezado
            a["veredicto"] = "sin_verificar"
        trayectoria = int((h.get("replicacion") or {}).get("hechas") or 0)
        try:
            # Rol "replica": el juez a temperatura alta y sin caché, para que cada
            # trayectoria sea una lectura distinta; `rollout_id` la distingue además
            # en la clave de la caché de DSPy (S-20).
            recuento = await PASOS.verificar_afirmaciones(ctx, copias, None, h["enunciado"], rol="replica", rollout_id=trayectoria) if copias else {}
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
                x["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "revisor", "texto": f"Replicación terminada: {r['sostienen']} de {r['total']} trayectorias sostienen las afirmaciones.", "creadoEn": P.ahora_ms()})
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
                    except Exception as ex:  # noqa: BLE001  (un JSON raro de Crossref no debe dejar la bandera puesta para siempre)
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
                        # Propagación de dependencias (rosa/dependencias.py): los hechos que
                        # citan la fuente, las hipótesis y sus planes quedan pendientes.
                        if r[0] in ("retractado", "corregido", "preocupacion"):
                            DEP.propagar_retraccion(e, inv["id"], f["id"], f.get("doi"), ahora, causa="fuente_retractada" if r[0] == "retractado" else "fuente_corregida")
                    f["retraccionComprobadaEn"] = ahora
                if tocada:
                    # Seguimiento de dependencias (plan completo, seccion 9): la fuente
                    # cambio, así que la conclusión que dependía de ella se marca para
                    # recalcular; la anterior se guarda para el informe de diferencias.
                    h["_conclusionAnterior"] = h.get("conclusion")
                    h.pop("_conclusionIntentada", None)
                    h["_recalcularPorFuente"] = ahora
                    A.recalcular_bloqueos(e, h)
                    afectadas.append({"id": h["id"], "titulo": h["titulo"]})
            A.con_evento(e, inv["id"], "retraccion", f"Retractaciones recomprobadas en {len(dois)} DOI: {cambios} cambios" + (f"; {len(afectadas)} hipótesis se recalculan" if afectadas else "") + (" (algunas consultas no llegaron)" if any(v[0] == '__error__' for v in dois.values()) else ""), None, ahora)
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
        """El informe de diferencias del plan completo: que decía cada
        conclusión antes del cambio de fuente y que dice ahora. Los informes
        anteriores no se tocan: lo histórico sigue siendo histórico."""
        ahora = P.ahora_ms()

        def fn(e: dict[str, Any]) -> bool:
            L = [f"# Recálculo por {causa}", "", f"Fecha: {datetime.fromtimestamp(ahora / 1000).strftime('%d/%m/%Y %H:%M')}. Investigación: {inv['titulo']}.", ""]
            for hid in ids:
                h = next((z for z in e["hipotesis"] if z["id"] == hid), None)
                if not h:
                    continue
                antes = h.pop("_conclusionAnterior", None) or {}
                despues = h.get("conclusion") or {}
                h.pop("_recalcularPorFuente", None)
                L += [f"## {h['titulo']}", f"Antes: certeza {antes.get('certeza', 'sin conclusión')}, dirección {antes.get('direccion', '?')}. {antes.get('enunciado', '')}", f"Ahora: certeza {despues.get('certeza', 'sin conclusión')}, dirección {despues.get('direccion', '?')}. {despues.get('enunciado', '')}", f"Bloqueos ahora: {', '.join(h.get('bloqueos', [])) or 'ninguno'}", ""]
                if h.get("experimento") and h["experimento"].get("estado") in ("asignado", "en_curso"):
                    L.append("Experimento en marcha: el recálculo no lo cancela ni lo autoriza; decide una persona.")
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
                await self._cerrar_con_presupuesto(c, it)
                continue
            inv = next(i for i in e["investigaciones"] if i["id"] == c["investigacionId"])
            motivo = _condicion_de_parada(inv["condicionParada"], it["numero"] - 1, self._con_reloj(c), mision=inv.get("mision"))
            if motivo:
                # El tiempo o las llamadas se cumplieron a mitad de iteración: lo
                # pendiente se omite con motivo y la iteración se cierra ya.
                self.almacen.mutar(lambda e2: _omitir_pendientes(e2, it["id"], motivo), "parada")
                await self._cerrar_con_presupuesto(c, it)
                continue
            await self._ejecutar_paso(c, it, paso)

    async def _cerrar_con_presupuesto(self, c: dict[str, Any], it: dict[str, Any]) -> None:
        """`_cerrar_iteracion` con la misma puerta de presupuesto que los pasos: si
        el tope salta dentro del cierre (conclusiones con Opus, acumulación de
        evidencia), la corrida se pausa con su evento y la iteración queda abierta
        para retomar el cierre al ampliar. Antes la excepción tumbaba la tarea y
        el tick la relanzaba cada 2 s con la corrida "en marcha" (S-14)."""
        try:
            await self._cerrar_iteracion(c, it)
        except PresupuestoAgotado:
            self.almacen.mutar(lambda e2: _pausar_por_presupuesto(e2, c["id"]), "presupuesto")

    async def _proponer_mision(self, ctx: Ctx, inv: dict[str, Any]) -> None:
        """La misión estructurada (etapa 0 de ROSA2018) a partir del objetivo.
        Queda propuesta; la persona la aprueba (o la corrige) con el primer
        plan o desde Objetivo y datos."""
        try:
            pred = await ctx.llamar("cerebro", self.programas.mision, objetivo=inv["objetivo"], relevancia=inv["relevancia"] or "Sin definir", limites="; ".join(inv["limites"]) or "Ninguno", configuracion=T.configuracion(inv))
            m = pred.mision
            mision = {**P.mision_vacia(), "metaAmplia": inv["objetivo"], "poblacion": m.poblacion.strip(), "etapa": m.etapa.strip(), "celulaTejido": m.celula_tejido.strip(), "mecanismo": m.mecanismo.strip(), "tipoIntervencion": m.tipo_intervencion.strip(), "capacidadesLaboratorio": [c.strip() for c in m.capacidades_laboratorio if c.strip()][:6], "propuestaPorRosa": True}
            justificacion = m.justificacion.strip()
            # El planificador del programa: areas de investigación comparables, con
            # familias de mecanismo distintas y las que quedan sin explorar.
            try:
                from rosa import skills as SK

                guia = SK.texto_para_prompt(SK.para_texto("elección de problema misión áreas programa", contexto="mision"), maximo=2500)
                pa = await ctx.llamar("cerebro", self.programas.areas, meta_amplia=inv["objetivo"], mision=PASOS._texto_mision({"mision": mision}), modelo_de_mundo=T.modelo_de_mundo(self.almacen.estado["hechos"], inv["id"], maximo=30), limites=("; ".join(inv["limites"]) or "Ninguno") + "\n\nGuia de eleccion de problema (skill):\n" + guia)
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
                A.con_evento(e, i["id"], "mision", f"Rosa propone la misión: {justificacion[:140]}. Apruebala o corrigela en Objetivo y datos.", f"#/investigaciones/{i['id']}/investigacion", ahora)
            return True

        self.almacen.mutar(fn, "mision")

    async def _formular_pregunta(self, ctx: Ctx, c: dict[str, Any], inv: dict[str, Any]) -> None:
        """La pregunta concreta de la campaña, con la plantilla del plan
        completo, desde la meta, la misión y el área elegida. Queda
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
        motivo = _condicion_de_parada(inv["condicionParada"], numero - 1, self._con_reloj(c), mision=inv.get("mision")) if anterior else None
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
        analisis_omitidos: list[str] = []
        try:
            pregunta = (c.get("pregunta") or {}).get("enunciado") or (next((x for x in self.almacen.estado["corridas"] if x["id"] == c["id"]), {}).get("pregunta") or {}).get("enunciado")
            mundo = await T.modelo_de_mundo_para(self.almacen, inv["id"], inv["objetivo"] + (f" {pregunta}" if pregunta else ""))
            # Traspaso ejecutable: de la iteración anterior, o de la corrida anterior si esta es la primera.
            traspaso = T.traspaso_iteracion(e, anterior, c) if anterior else T.traspaso_de_corrida(e, inv["id"])
            if not anterior:
                self.almacen.mutar(lambda e2, t=traspaso: _fijar_traspaso(e2, c["id"], t), "traspaso")
            lecciones = await LEC.para(self.almacen, inv["id"], ("plan", "fuentes", "consultas", "hipotesis", "analisis"), inv["objetivo"] + (f" {pregunta}" if pregunta else ""))
            pred = await ctx.llamar(
                "cerebro",
                self.programas.plan,
                objetivo=inv["objetivo"] + (f"\nPregunta de esta campana: {pregunta}" if pregunta else ""),
                relevancia=inv["relevancia"],
                limites="; ".join(inv["limites"]) or "Ninguno declarado",
                condicion_parada=PARADA.texto_condicion(inv, c),
                modelo_de_mundo=mundo,
                resumen_iteracion_anterior=anterior["resumen"] if anterior else "",
                traspaso=traspaso,
                lecciones=lecciones,
                indicaciones_humanas=T.indicaciones_humanas(anterior, pendientes_solo=True) if anterior else "Ninguna.",
                hipotesis_vivas=T.hipotesis_vivas(e["hipotesis"], inv["id"]) + "\n" + T.vivero_texto(inv),
                # Registro de datasets del programa que coinciden con la pregunta (los de
                # acceso controlado con su aviso): sin este campo DSPy avisaba "Missing:
                # datasets_disponibles" y el planificador no veía los datos disponibles.
                datasets_disponibles=PASOS.datasets_para_plan(e, inv["id"], pregunta),
                numero_iteracion=numero,
            )
            hay_datos = any(d["estado"] == "aprobado" and (d.get("procedencia") or {}).get("hash") for d in inv.get("datasets", []))
            for p in list(pred.plan)[:7]:
                if p.tipo == "analisis" and not hay_datos:
                    # Sin datasets aprobados no hay nada que analizar; se dice en un evento en
                    # vez de borrar el paso en silencio (M-23).
                    analisis_omitidos.append((p.titulo or "Análisis in silico")[:80])
                    continue
                coste = COSTE_POR_TIPO.get(p.tipo, 20)
                if p.tipo == "literatura":
                    # La búsqueda en amplitud añade consultas al paso: su presupuesto crece con la fracción elegida.
                    coste = int(round(coste * (1 + politicas.AMPLITUD.get(PASOS.amplitud_de(inv), 0.0))))
                paso = P.nuevo_paso(p.titulo, p.detalle, coste, valor_decision=(p.valor_decision or "").strip(), espera=(getattr(p, "espera", "") or "").strip(), si_no_aparece=(getattr(p, "si_no_aparece", "") or "").strip())
                paso["tipo"] = p.tipo
                plan.append(paso)
            if hay_datos and not any(p.get("tipo") == "analisis" for p in plan) and (any(r["investigacionId"] == inv["id"] and r["estado"] == "pendiente" for r in e.get("reproducciones", [])) or any(h["investigacionId"] == inv["id"] and h.get("_analisisPedido") for h in e["hipotesis"])):
                paso = P.nuevo_paso("Análisis in silico", "Reproducciones pendientes de la puerta y análisis pedidos, en el sandbox", COSTE_POR_TIPO["analisis"])
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
                coste = COSTE_POR_TIPO.get(tipo, pres)
                if tipo == "literatura":
                    coste = int(round(coste * (1 + politicas.AMPLITUD.get(PASOS.amplitud_de(inv), 0.0))))
                paso = P.nuevo_paso(titulo, detalle, coste)
                paso["tipo"] = tipo
                plan.append(paso)
        # Las indicaciones humanas pendientes de la iteración anterior pasan a la nueva.
        if anterior:
            for p in anterior["plan"]:
                if p["indicacionHumana"] and p["estado"] == "pendiente":
                    plan.insert(0, dict(p, id=P.nuevo_id("paso")))
        ahora = P.ahora_ms()
        it = P.nueva_iteracion(c["id"], numero, ahora, plan, max(sum(p["presupuesto"] or 0 for p in plan), 20))

        def fn(e2: dict[str, Any]) -> bool:
            c2 = next(x for x in e2["corridas"] if x["id"] == c["id"])
            if c2["estado"] in ("detenida", "terminada"):
                # Una persona la detuvo mientras el modelo proponía el plan: la orden
                # de detener manda y el plan se descarta. Antes esta escritura la
                # resucitaba a "esperando_plan" y quedaban dos corridas vivas sobre
                # la misma investigación (corridas 11 y 12, 17 de septiembre de 2026).
                return False
            e2["iteraciones"].append(it)
            c2["iteracionActual"] = numero
            c2["estado"] = "esperando_plan"
            A.con_evento(e2, inv["id"], "corrida_estado", f"Plan de la iteración {numero} propuesto: {len(plan)} pasos. Espera tu aprobación.", f"#/investigaciones/{inv['id']}/corrida", ahora)
            for titulo in analisis_omitidos:
                A.con_evento(e2, inv["id"], "corrida_estado", f"El planificador proponía «{titulo}» y se dejó fuera del plan de la iteración {numero}: no hay ningún dataset aprobado con fichero en la investigación. Registra o aprueba un dataset en Objetivo y datos para que Rosa pueda analizar.", f"#/investigaciones/{inv['id']}/investigacion", ahora)
            return True

        self.almacen.mutar(fn, "plan_propuesto")

    async def _permiso_presupuesto(self, c: dict[str, Any], it: dict[str, Any]) -> bool:
        """Si la iteración pide más de la mitad de lo que queda en la corrida y
        la autonomía dice 'preguntar', se pide permiso una vez por iteración."""
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
            s = {"id": P.nuevo_id("sol"), "corridaId": c["id"], "tipo": "presupuesto_grande", "titulo": f"La iteración {it['numero']} quiere gastar {pedido} llamadas de las {restante} que quedan", "detalle": "Es más de la mitad del presupuesto restante. Puedes ajustar cuantas llamadas permitir.", "recurso": f"{pedido} llamadas al modelo", "alcances": ["una_vez", "esta_corrida"], "estado": "pendiente", "alcanceConcedido": None, "creadaEn": ahora, "resueltaEn": None, "hipotesisId": None, "argumentos": [{"nombre": "llamadas", "valor": str(pedido), "editable": True}], "_iteracionId": it["id"]}

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
                # Denegado: la iteración no puede gastar más de lo ya usado y la
                # corrida se pausa hasta que alguien amplie el tope o la reanude.
                it2["presupuesto"]["limite"] = it2["presupuesto"]["usado"]
                it2["_presupuestoDenegado"] = True
                c2 = next(x for x in e2["corridas"] if x["id"] == c["id"])
                c2["estado"] = "pausada_por_presupuesto"
                c2["presupuesto"]["motivoPausa"] = f"Permiso de gasto denegado: la iteración {it['numero']} queda sin presupuesto"
                A.con_evento(e2, c["investigacionId"], "presupuesto", f"Permiso de gasto denegado: la iteración {it['numero']} queda sin presupuesto y la corrida se pausó. Amplía el tope para seguir.", f"#/investigaciones/{c['investigacionId']}/corrida", P.ahora_ms())
            return True

        self.almacen.mutar(resolver, "presupuesto_autorizado")
        return ya["estado"] == "concedida"

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
        sin_trabajo_cls = getattr(PASOS, "SinTrabajo", None)
        try:
            gepa = getattr(self.almacen, "gepa_servicio", None)
            resumen = await gepa.ejecutar_paso(ctx, ejecutor, paso) if gepa else await ejecutor(ctx, paso)
            it_actual = next(x for x in self.almacen.estado["iteraciones"] if x["id"] == it["id"])
            propias = [p for p in it_actual["pistas"] if p["pasoId"] == paso["id"]]
            todas_fallaron = bool(propias) and all(p["estado"] in ("fallida", "detenida") for p in propias)
            if todas_fallaron:
                self.almacen.mutar(lambda e: _estado_paso(e, it["id"], paso["id"], "fallido", motivo="Ninguna de sus pistas terminó: " + "; ".join(p["resumen"] for p in propias)[:300]), "paso")
            elif paso_sin_trabajo(resumen, propias):
                # El paso corrió y no tenía nada sobre lo que trabajar (sin fuentes nuevas,
                # nada que verificar): no es "hecho" ni un fallo, y el motivo queda a la vista (M-23).
                self.almacen.mutar(lambda e: _estado_paso(e, it["id"], paso["id"], "sin_trabajo", detalle=resumen, motivo=(resumen or "El paso no encontró nada sobre lo que trabajar")[:300]), "paso")
            else:
                self.almacen.mutar(lambda e: _estado_paso(e, it["id"], paso["id"], "hecho", detalle=resumen), "paso")
        except PresupuestoAgotado:
            self.almacen.mutar(lambda e: _estado_paso(e, it["id"], paso["id"], "pendiente"), "paso")
            self.almacen.mutar(lambda e: _pausar_por_presupuesto(e, c["id"]), "presupuesto")
        except asyncio.CancelledError:
            raise
        except Exception as ex:  # noqa: BLE001
            if sin_trabajo_cls is not None and isinstance(ex, sin_trabajo_cls):
                motivo_sin = str(ex)[:300] or "El paso no encontró nada sobre lo que trabajar"
                self.almacen.mutar(lambda e: _estado_paso(e, it["id"], paso["id"], "sin_trabajo", detalle=motivo_sin, motivo=motivo_sin), "paso")
                return
            traceback.print_exc()

            def fallar_paso(e: dict[str, Any]) -> bool:
                _estado_paso(e, it["id"], paso["id"], "fallido", motivo=f"{type(ex).__name__}: {str(ex)[:200]}")
                it2 = next((x for x in e["iteraciones"] if x["id"] == it["id"]), None)
                # Las pistas del paso que quedaron en curso no pueden seguir "en curso" para siempre.
                for p_ in (it2 or {}).get("pistas", []):
                    if p_.get("pasoId") == paso["id"] and p_.get("estado") == "en_curso":
                        p_["estado"] = "fallida"
                        p_["resumen"] = f"Interrumpida por un fallo del paso: {type(ex).__name__}"
                return True

            self.almacen.mutar(fallar_paso, "paso")

    async def _revisar_registro(self, ctx: Ctx, inv: dict[str, Any], it: dict[str, Any], c: dict[str, Any], resumen: str, llano: dict[str, Any] | None) -> dict[str, Any]:
        e = self.almacen.estado
        texto = resumen + ("\n\n" + " ".join(str(v) for v in (llano or {}).values() if isinstance(v, str)) if llano else "")
        corpus = RR.corpus_del_registro(e, inv["id"], it, c)
        runs_ok = sum(1 for r in e.get("ejecuciones", []) if r.get("estado") == "completado" and r.get("investigacionId") == inv["id"])
        de_la_iteracion = PROG.hipotesis_nacidas_en(e, inv["id"], it, ahora=P.ahora_ms())
        regla = RR.comprobaciones_deterministas(texto, corpus, it, runs_ok, hipotesis=de_la_iteracion)
        hallazgos = list(regla)
        juez = None
        try:
            pred = await ctx.llamar("juez", self.programas.revisar_registro, texto=texto[:6000], registro=RR.texto_registro(e, inv["id"], it, c), hallazgos_por_regla="\n".join(f"- {h['clase']}: {h['detalle']}" for h in regla) or "Ninguno")
            juez = ctx.modelos.juez.model
            for hz in pred.revision.hallazgos:
                hallazgos.append({"clase": hz.clase, "gravedad": hz.gravedad, "detalle": hz.detalle.strip()[:400], "origen": "juez"})
            resumen_j = pred.revision.resumen.strip()
        except PresupuestoAgotado:
            raise  # el cierre pausa la corrida; una iteración no se cierra sin revisor por falta de presupuesto
        except Exception as ex:  # noqa: BLE001
            resumen_j = f"El juez no respondió: {str(ex)[:120]}; solo comprobaciones por regla"
        for i, hz in enumerate(hallazgos):
            hz["id"] = f"rr-{it['id']}-{i}"
            hz["estado"] = "abierto"
        return {"hallazgos": hallazgos, "porRegla": len(regla), "juez": juez, "resumen": resumen_j, "fecha": P.ahora_ms(), "estado": "con_hallazgos" if hallazgos else "limpia"}

    async def _cerrar_iteracion(self, c: dict[str, Any], it: dict[str, Any]) -> None:
        e = self.almacen.estado
        inv = next(i for i in e["investigaciones"] if i["id"] == c["investigacionId"])
        if it["plan"] and not any(p["estado"] in ("hecho", "fallido", "sin_trabajo") for p in it["plan"]):
            # Ningún paso llegó a ejecutarse (el tope se cumplió antes de empezar):
            # no hay nada que resumir, revisar ni aprender. Antes corrían igual el
            # resumen, el resumen en llano, las lecciones, el revisor de registro y la
            # meta-revisión sobre una iteración vacía (corridas 8 y 9).
            motivo = next((p.get("motivoFallo") for p in it["plan"] if p.get("motivoFallo")), "") or "ningún paso llegó a ejecutarse"
            ahora_v = P.ahora_ms()

            def vacio(e2: dict[str, Any]) -> bool:
                it2 = next(x for x in e2["iteraciones"] if x["id"] == it["id"])
                it2["terminadaEn"] = ahora_v
                it2["resumen"] = f"Iteración cerrada sin ejecutar ningún paso: {motivo}."
                A.con_evento(e2, inv["id"], "iteracion_terminada", f"Iteración {it['numero']} cerrada sin ejecutar ningún paso: {motivo}", f"#/investigaciones/{inv['id']}/corrida", ahora_v)
                return True

            self.almacen.mutar(vacio, "iteracion_vacia")
            return
        ctx = Ctx(self.almacen, self.programas, self.modelos, c["id"], inv["id"], it["id"], it["numero"])
        # Lo ya calculado en un cierre anterior que se cortó por presupuesto (S-14):
        # el resumen, la meta-revisión y el resumen en llano no se pagan dos veces.
        parcial = dict(it.get("_cierre") or {}) if isinstance(it.get("_cierre"), dict) else {}
        hechos_nuevos = [h for h in e["hechos"] if h["investigacionId"] == inv["id"] and h["actualizadoEn"] >= it["empezadaEn"] and h["historial"] and h["historial"][0]["quien"] == config.QUIEN_ROSA]
        # "Nuevas" son las nacidas en la ventana de esta iteración (rosa/progreso.py),
        # no las que comparten número de iteración con ella (S-16).
        hip_nuevas = PROG.hipotesis_nacidas_en(e, inv["id"], it, ahora=P.ahora_ms(), origen="rosa")
        cola = cola_de_hipotesis(e, inv["id"])
        afs = [a for a in c.get("_afirmaciones", []) if a["iteracion"] == it["numero"]]
        sin_comprobar = [a for a in afs if a["veredicto"] == "sin_verificar"] + [p for p in it["plan"] if p["estado"] == "fallido"]
        if parcial.get("resumen"):
            resumen = parcial["resumen"]
        else:
            try:
                pred = await ctx.llamar("cerebro", self.programas.resumir, plan_ejecutado=T.plan_ejecutado(it), cambios_modelo_de_mundo="\n".join(f"- {h['enunciado']}" for h in hechos_nuevos) or "Ninguno", hipotesis_nuevas="\n".join(f"- {h['titulo']}" for h in hip_nuevas) or "Ninguna", cola=cola, sin_comprobar="\n".join(f"- {x.get('texto') or x.get('titulo')}" for x in sin_comprobar) or "Nada")
                resumen = pred.resumen.strip()
            except PresupuestoAgotado:
                raise
            except Exception:  # noqa: BLE001
                hechas = sum(1 for p in it["pistas"] if p["estado"] == "hecha")
                resumen = f"{len(it['plan'])} pasos, {hechas} pistas completadas, {len(hechos_nuevos)} hechos y {len(hip_nuevas)} hipótesis nuevas"
            self.almacen.mutar(lambda e2: _guardar_cierre_parcial(e2, it["id"], resumen=resumen), "cierre_parcial")
        # El panorama y las debilidades se sintetizan al cerrar cada iteración
        # con dos o más hipótesis, aunque el plan no trajera un paso de meta.
        propias = [h for h in e["hipotesis"] if h["investigacionId"] == inv["id"]]
        if len(propias) >= 2 and not parcial.get("metaHecha") and not any(T.inferir_tipo_paso(p) == "meta" and p["estado"] == "hecho" for p in it["plan"]):
            try:
                await PASOS.paso_meta(ctx, {"id": None, "titulo": "Meta-revisión al cierre", "detalle": ""})
            except PresupuestoAgotado:
                raise
            except Exception as ex:  # noqa: BLE001
                traceback.print_exc()
            self.almacen.mutar(lambda e2: _guardar_cierre_parcial(e2, it["id"], metaHecha=True), "cierre_parcial")
        if isinstance(parcial.get("llano"), dict):
            llano = parcial["llano"]
        else:
            llano = await self._explicar_en_llano(ctx, inv, resumen, hechos_nuevos, hip_nuevas, sin_comprobar, cola=cola)
            if llano:
                self.almacen.mutar(lambda e2: _guardar_cierre_parcial(e2, it["id"], llano=llano), "cierre_parcial")
        # Acumulación de evidencia: lo leído en esta iteración vuelve a las hipótesis
        # vivas (a favor, indirecto o en contra) antes de rehacer sus conclusiones.
        con_evidencia: set[str] = set()
        pista_ev = ctx.pista(None, "modelo", "Evidencia nueva para las hipótesis vivas", "Sonnet 5")
        try:
            acumulado = await EV.acumular(ctx, it["numero"], pista_ev)
            con_evidencia = set(acumulado.get("ids", []))
            vivero_res = await EV.acumular_vivero(ctx, it["numero"], pista_ev)
            con_evidencia |= set(vivero_res.get("nacidas", []))
        except PresupuestoAgotado:
            pista_ev.fallar("Sin presupuesto: la evidencia nueva se enlaza al retomar el cierre")
            raise
        except Exception as ex:  # noqa: BLE001
            traceback.print_exc()
            pista_ev.fallar(f"La acumulación de evidencia falló: {str(ex)[:160]}")
        e = self.almacen.estado
        # Reconcluir solo lo que cambió (S-13): la huella de la evidencia contada de
        # cada hipótesis viva frente a la que guarda su conclusión; las demás la
        # conservan con una nota. Las que sí, en paralelo de tres en tres.
        vivas = [x for x in e["hipotesis"] if x["investigacionId"] == inv["id"] and x["estado"] not in ("descartada",)]
        a_concluir: list[dict[str, Any]] = []
        conservadas: list[tuple[str, str]] = []
        for h in vivas:
            motivo_rc = motivo_para_reconcluir(h, con_evidencia)
            if motivo_rc:
                a_concluir.append(h)
            else:
                conservadas.append((h["id"], f"iteración {it['numero']}: sin cambios en la evidencia contada; se conserva la conclusión de la iteración {(h.get('conclusion') or {}).get('iteracion')}"))
        if conservadas:
            self.almacen.mutar(lambda e2: _anotar_conservadas(e2, conservadas), "conclusion_conservada")
        if a_concluir:
            sem = asyncio.Semaphore(3)

            async def concluir_una(h: dict[str, Any]) -> None:
                async with sem:
                    await self._concluir_hipotesis(ctx, h)

            resultados = await asyncio.gather(*(concluir_una(h) for h in a_concluir), return_exceptions=True)
            for r in resultados:
                if isinstance(r, (PresupuestoAgotado, asyncio.CancelledError)):
                    raise r
                if isinstance(r, BaseException):
                    traceback.print_exception(r)
        ahora = P.ahora_ms()
        bloqueadas = [a for a in afs if a["veredicto"] in ("no_sostenida", "cita_no_resuelve", "sin_cita", "ausencia_refutada")]
        e = self.almacen.estado
        hip_nuevas = PROG.hipotesis_nacidas_en(e, inv["id"], it, ahora=ahora, origen="rosa")
        informe = _informe(inv, it, resumen, hechos_nuevos, hip_nuevas, afs, bloqueadas, [q for q in c["busqueda"].get("consultas", []) if q.get("iteracion") in (None, it["numero"])])
        # Revisor de registro: lo que el resumen y el resumen en llano dicen, contra
        # lo que el registro prueba. Por regla y después con el juez.
        revision = await self._revisar_registro(ctx, inv, it, c, resumen, llano)
        terminar = _condicion_de_parada(inv["condicionParada"], it["numero"], self._con_reloj(c), mision=inv.get("mision"))

        def fn(e2: dict[str, Any]) -> bool:
            it2 = next(x for x in e2["iteraciones"] if x["id"] == it["id"])
            it2["terminadaEn"] = ahora
            it2["resumen"] = resumen
            it2.pop("_cierre", None)
            if llano:
                it2["resumenLlano"] = llano
            it2["revisionRegistro"] = revision
            # Instantánea de progreso: certeza de cada hipótesis, peldaños subidos o
            # bajados, hechos nuevos y fallidos de la iteración (rosa/progreso.py). Las
            # hipótesis nuevas se cuentan aquí, sobre e2, para que las nacidas del
            # vivero en este mismo cierre cuenten.
            c_prog = next(x for x in e2["corridas"] if x["id"] == c["id"])
            nacidas = len(PROG.hipotesis_nacidas_en(e2, inv["id"], it2, ahora=ahora, origen="rosa"))
            c_prog.setdefault("progreso", []).append(PROG.instantanea(e2, c_prog, it2, len(hechos_nuevos), nacidas, len(bloqueadas), ahora))
            # Vistas de programa por regla (ROSA2018): dónde está la evidencia por
            # estadio, región y célula (mapa de la enfermedad), qué pasos de la ruta
            # terapéutica cubre cada diana (mapa de ruta) y las tres cifras de
            # aprendizaje. Cada una en su try: un fallo deja incidencia y no rompe el cierre.
            # La métrica de la corrida (`PROG.metrica_de_corrida`) lee las cifras de
            # la investigación a demanda, así que las ve en cuanto se escriben aquí.
            _vistas_de_programa_al_cerrar(e2, inv["id"], it2, ahora)
            # Lecciones por regla: lo que esta iteración enseña a no repetir (rosa/lecciones.py).
            nuevas_lecciones = LEC.registrar(e2, LEC.generar_al_cerrar(e2, c_prog, it2, revision, ahora))
            if nuevas_lecciones:
                A.con_evento(e2, inv["id"], "aprendizaje", f"{nuevas_lecciones} {'lección nueva' if nuevas_lecciones == 1 else 'lecciones nuevas'} de la iteración {it['numero']}: lo que Rosa no repetirá", f"#/investigaciones/{inv['id']}/investigacion", ahora)
            if revision["hallazgos"]:
                A.con_evento(e2, inv["id"], "revision_registro", f"El revisor de registro encontró {len(revision['hallazgos'])} hallazgos en la iteración {it['numero']}: " + RR.resumen_revision(revision["hallazgos"])[:140], f"#/investigaciones/{inv['id']}/corrida", ahora)
            # Bradley-Terry con intervalos sobre los partidos del torneo: es lo que
            # ordena a las candidatas; el Elo se queda como vista.
            bt = torneo.bradley_terry([x for x in e2["hipotesis"] if x["investigacionId"] == inv["id"]], semilla=it["numero"])
            for x in e2["hipotesis"]:
                if x["id"] in bt:
                    x["bt"] = bt[x["id"]]
            # Priorizacion: bloqueos no compensables y candidatas con diversidad.
            # Marcos de argumentación (rosa/argumentacion.py): qué candidatas se atacan
            # entre sí. Se marca, no se descarta; decide la persona.
            ARG.marcar_conflictos(e2, inv["id"])
            ids = PR.marcar_candidatas(e2, inv["id"])
            conflicto_txt = ARG.texto_conflictos(e2, inv["id"], ids)
            if conflicto_txt:
                A.con_evento(e2, inv["id"], "ranking_cambio", conflicto_txt[:400], f"#/investigaciones/{inv['id']}/ranking", ahora)
            if ids:
                titulos = [next(x["titulo"][:50] for x in e2["hipotesis"] if x["id"] == i) for i in ids]
                A.con_evento(e2, inv["id"], "ranking_cambio", f"Candidatas al laboratorio tras la iteración {it['numero']}: " + "; ".join(titulos), f"#/investigaciones/{inv['id']}/ranking", ahora)
            runs_it = [r for r in e2.get("ejecuciones", []) if r.get("investigacionId") == inv["id"] and r.get("inicio", 0) >= it["empezadaEn"]]
            A.guardar_artefacto(
                e2, inv["id"], f"Informe de la iteración {it['numero']}", "informe", informe, resumen[:140], it["numero"], ahora,
                procedencia={
                    "mensajes": {"plan": [{"titulo": p["titulo"], "estado": p["estado"]} for p in it2["plan"]], "pistas": [{"id": p["id"], "titulo": p["titulo"], "estado": p["estado"]} for p in it2.get("pistas", [])[:40]], "decisiones": [d["id"] for d in e2.get("decisiones", []) if d.get("investigacionId") == inv["id"] and d.get("fecha", 0) >= it["empezadaEn"]][:40]},
                    "codigo": None,
                    "registroEjecucion": [{"id": r["id"], "estado": r.get("estado"), "auditoria": (r.get("auditoria") or {}).get("veredicto"), "resultados": r.get("resultados")} for r in runs_it[:20]] or None,
                    "entorno": {"cerebro": self.modelos.cerebro.model, "juez": self.modelos.juez.model, "volumen": self.modelos.volumen.model, "arnes": c.get("arnes"), "sandbox": [r.get("entorno") for r in runs_it[:1]]},
                    "revision": revision,
                },
            )
            A.con_evento(e2, inv["id"], "iteracion_terminada", f"Iteración {it['numero']} terminada: {resumen[:160]}", f"#/investigaciones/{inv['id']}/corrida", ahora)
            # Toda hipótesis viva cuya evidencia cambió desde su última decisión del
            # Killer vuelve a la cola de revisión (S-08).
            with contextlib.suppress(Exception):
                pedir_revision_por_huella(e2, ahora, inv["id"])
            c2 = next(x for x in e2["corridas"] if x["id"] == c["id"])
            if terminar:
                c2["estado"] = "terminada"
                c2["terminadaEn"] = ahora
                c2["motivoCierre"] = terminar
                c2["metrica"] = PROG.metrica_de_corrida(e2, c2["id"])
                c2["_revisarArnes"] = True  # meta-campaña: el supervisor la recoge
                resumen_m = PROG.resumen_metrica(c2["metrica"])
                A.con_evento(e2, inv["id"], "corrida_estado", f"Corrida {c2['numero']} terminada: {terminar}" + (f". Balance: {resumen_m}" if resumen_m else ""), f"#/investigaciones/{inv['id']}/corrida", ahora)
            return True

        self.almacen.mutar(fn, "iteracion_cerrada")


# ---------------------------------------------------------------------------
# Ayudantes puros
# ---------------------------------------------------------------------------

# Cada cuánto se escribe el reloj de una corrida viva al estado (S-17). El resto
# del tiempo vive en memoria del supervisor y el tope en horas lo lee de ahí.
RELOJ_VOLCADO_MS = 30_000
# Espera antes de relanzar una tarea de corrida que murió con excepción: 30 s la
# primera vez, 60 s la segunda, 5 minutos a partir de la tercera (S-14).
RETROCESO_MS = (30_000, 60_000, 300_000)
# Incidencias que no retienen a la corrida en "esperando aprobación".
INCIDENCIAS_QUE_NO_BLOQUEAN = ("modelo_bloqueado", "bucle_reventado")
# Veces que se intenta una revisión pedida cuando el Killer no llega a decidir.
MAX_INTENTOS_KILLER = 3
_SINTETICO = re.compile(r"sint[eé]tic", re.IGNORECASE)
# Lo que devuelven los ejecutores cuando corren y no había nada sobre lo que trabajar.
_SIN_TRABAJO = re.compile(r"^(no hay fuentes nuevas|nada pendiente de verificar|sin afirmaciones sostenidas nuevas|sin datasets aprobados|0 ensayos encontrados|0 hipótesis nuevas en la cola, 0 revisadas, 0 partidos|todas las hipótesis tienen la novedad comprobada)", re.IGNORECASE)


def _incidencia_bucle(e: dict[str, Any], corrida_id: str, ex: BaseException, n: int, espera_ms: int, ahora: int) -> bool:
    """La incidencia visible de una tarea de corrida que murió con excepción: qué
    excepción, cuántas veces seguidas y cuándo se reintenta. Una pendiente del
    mismo tipo se actualiza en vez de duplicarse."""
    c = next((x for x in e["corridas"] if x["id"] == corrida_id), None)
    if not c:
        return False
    espera = f"{espera_ms // 1000} s" if espera_ms < 120_000 else f"{espera_ms // 60_000} min"
    titulo = f"El bucle de la corrida {c['numero']} se cayó ({type(ex).__name__}); se reintenta en {espera}" + (f" (fallo {n} seguido)" if n > 1 else "")
    detalle = f"{type(ex).__name__}: {str(ex)[:400]}"
    for inc in e["incidencias"]:
        if inc["corridaId"] == corrida_id and inc["estado"] == "pendiente" and inc["tipo"] == "bucle_reventado":
            inc["titulo"] = titulo
            inc["detalle"] = detalle
            inc["creadaEn"] = ahora
            A.con_evento(e, c["investigacionId"], "incidencia", f"Incidencia: {titulo}", f"#/investigaciones/{c['investigacionId']}/corrida", ahora)
            return True
    e["incidencias"].append({"id": P.nuevo_id("inc"), "corridaId": corrida_id, "tipo": "bucle_reventado", "titulo": titulo, "detalle": detalle, "recurso": "bucle", "alternativa": "Si se repite, detén la corrida y abre otra; el error queda en la consola del servidor.", "estado": "pendiente", "creadaEn": ahora, "resueltaEn": None, "resolucion": None})
    A.con_evento(e, c["investigacionId"], "incidencia", f"Incidencia: {titulo}", f"#/investigaciones/{c['investigacionId']}/corrida", ahora)
    return True


def _guardar_cierre_parcial(e: dict[str, Any], iteracion_id: str, **partes: Any) -> bool:
    """Guarda en `it._cierre` lo ya calculado del cierre (resumen, meta hecha,
    resumen en llano) para no pagarlo otra vez si el cierre se corta."""
    it = next((x for x in e["iteraciones"] if x["id"] == iteracion_id), None)
    if not it:
        return False
    parcial = it.get("_cierre") if isinstance(it.get("_cierre"), dict) else {}
    parcial.update(partes)
    it["_cierre"] = parcial
    return True


def _anotar_conservadas(e: dict[str, Any], notas: list[tuple[str, str]]) -> bool:
    cambiado = False
    for hid, nota in notas:
        h = next((x for x in e["hipotesis"] if x["id"] == hid), None)
        if h is None:
            continue
        registro = (h.get("procedencia") or {}).get("registro")
        if isinstance(registro, list) and (not registro or registro[-1] != nota):
            registro.append(nota)
            cambiado = True
    return cambiado


def _texto_techo_por_regla(h: dict[str, Any]) -> str:
    """El techo GRADE por regla (rosa/certeza.py) como una línea para el juez
    de la conclusión: 'baja: solo literatura, pero de dos cohortes distintas'.
    Si la regla no puede calcularse (registro raro), lo dice en vez de romper."""
    try:
        nivel, motivo = CERTEZA.techo(h)
        return f"{str(nivel).replace('_', ' ')}: {motivo}"
    except Exception as ex:  # noqa: BLE001
        return f"sin techo calculable ({type(ex).__name__})"


def _n_decisiones_killer(e: dict[str, Any], hipotesis_id: str) -> int:
    return sum(1 for d in e.get("decisiones", []) if d.get("hipotesisId") == hipotesis_id and str(d.get("etapa", "")).startswith("killer"))


def _cerrar_peticion_de_revision(e: dict[str, Any], hipotesis_id: str, decisiones_antes: int, intentos_antes: int | None = None) -> bool:
    """Quita `_revisionPedida` solo si el Killer escribió una decisión nueva; si
    no, cuenta el intento y a partir de MAX_INTENTOS_KILLER deja de insistir con
    una línea en el registro (S-08). Si el propio Killer ya contó el intento
    durante la llamada (`_registrar_juez_sin_respuesta` en pasos.py sube
    `_killerIntentos` cuando el juez no responde), aquí no se cuenta otra vez:
    con la doble cuenta el tope de tres llegaba al segundo fallo real."""
    h = next((x for x in e["hipotesis"] if x["id"] == hipotesis_id), None)
    if h is None:
        return False
    if _n_decisiones_killer(e, hipotesis_id) > decisiones_antes:
        h.pop("_revisionPedida", None)
        h.pop("_killerIntentos", None)
        h.pop("killerPendiente", None)
        return True
    actuales = int(h.get("_killerIntentos") or 0)
    ya_contado = intentos_antes is not None and actuales > int(intentos_antes)
    intentos = actuales if ya_contado else actuales + 1
    h["_killerIntentos"] = intentos
    if intentos >= MAX_INTENTOS_KILLER:
        h.pop("_revisionPedida", None)
        h.pop("killerPendiente", None)
        registro = (h.get("procedencia") or {}).get("registro")
        if isinstance(registro, list):
            registro.append(f"revisión pedida abandonada tras {intentos} intentos sin decisión del Killer (el juez no respondió); vuelve a pedirla desde la ficha")
    return True


def _abandonar_peticion_sin_presupuesto(e: dict[str, Any], hipotesis_id: str, corrida: dict[str, Any]) -> bool:
    """Cierra una revisión pedida que no se puede atender porque la corrida no
    tiene presupuesto: quita la marca sin contar intento, deja la línea en el
    registro de la hipótesis y un evento que dice cómo repetirla."""
    h = next((x for x in e["hipotesis"] if x["id"] == hipotesis_id), None)
    if h is None:
        return False
    h.pop("_revisionPedida", None)
    h.pop("_killerIntentos", None)
    h.pop("killerPendiente", None)
    nota = f"revisión pedida no atendida: la corrida {corrida.get('numero')} ({str(corrida.get('estado', '')).replace('_', ' ')}) no tiene presupuesto; amplíalo o abre otra corrida y vuelve a pedirla"
    registro = (h.get("procedencia") or {}).get("registro")
    if isinstance(registro, list):
        registro.append(nota)
    A.con_evento(e, h["investigacionId"], "presupuesto", f"No se pudo revisar «{str(h.get('titulo') or '')[:70]}»: la corrida {corrida.get('numero')} no tiene presupuesto. Amplíalo o abre otra corrida y vuelve a pedir la revisión.", f"#/investigaciones/{h['investigacionId']}/hipotesis/{h['id']}", P.ahora_ms())
    return True


def _verdadero(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return str(v or "").strip().lower() in ("1", "true", "si", "sí", "yes", "sintetico", "sintético")


def es_resultado_sintetico(experimento: dict[str, Any] | None, fichero: Any, cabecera: str = "") -> bool:
    """Un resultado de laboratorio es de prueba si el experimento lo declara
    (`ensayoEnSeco`, `sintetico`, `datosSinteticos`, que escribe la subida con la
    casilla marcada) o si el nombre del fichero o su cabecera dicen "sintético".
    Nunca cuenta como observación original (S-18)."""
    x = experimento if isinstance(experimento, dict) else {}
    if any(_verdadero(x.get(k)) for k in ("ensayoEnSeco", "sintetico", "datosSinteticos")):
        return True
    return bool(_SINTETICO.search(str(fichero or ""))) or bool(_SINTETICO.search(str(cabecera or "")))


def paso_sin_trabajo(resumen: Any, pistas_propias: list[dict[str, Any]]) -> bool:
    """Un paso corrió sin nada que hacer si no abrió ninguna pista o si devolvió
    una de las frases de "nada que hacer" de los ejecutores (M-23)."""
    if not pistas_propias:
        return True
    return bool(_SIN_TRABAJO.match(str(resumen or "").strip()))


def _huella_evidencia_local(h: dict[str, Any]) -> str:
    """La huella de la evidencia con el mismo contrato que `rosa.killer.huella_evidencia`
    (ids, veredictos, relaciones y socavadaPor de las afirmaciones, ids de fuentes,
    versión, textos de supuestos, estado de novedad), por si el Killer aún no la trae."""
    afs = []
    for a in h.get("afirmaciones") or []:
        if not isinstance(a, dict):
            continue
        afs.append([str(a.get("afirmacionId") or f"{a.get('texto', '')[:80]}|{a.get('cita', '')}"), str(a.get("veredicto")), str(a.get("relacion")), sorted(str(x) for x in (a.get("socavadaPor") or []))])
    fuentes = sorted(str(f.get("id") or f.get("doi") or f.get("referencia")) for f in ((h.get("procedencia") or {}).get("fuentes") or []) if isinstance(f, dict))
    supuestos = sorted(str(s.get("texto")) for s in (h.get("supuestos") or []) if isinstance(s, dict))
    novedad = sorted((str(k), str((v or {}).get("estado"))) for k, v in (h.get("novedad") or {}).items() if isinstance(v, dict))
    cuerpo = json.dumps([sorted(afs), fuentes, h.get("version", 1), supuestos, novedad], ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(cuerpo.encode("utf-8")).hexdigest()


def huella_evidencia(h: dict[str, Any]) -> str:
    """`rosa.killer.huella_evidencia` si existe (grupo D); si no, la local con el mismo contrato."""
    try:
        from rosa import killer as K

        fn = getattr(K, "huella_evidencia", None)
        if callable(fn):
            v = fn(h)
            if isinstance(v, str) and v:
                return v
    except Exception:  # noqa: BLE001
        traceback.print_exc()
    return _huella_evidencia_local(h)


def huella_de_conclusion(h: dict[str, Any]) -> str:
    """Lo que de verdad mueve una conclusión GRADE: la huella de la evidencia más
    la decisión del Killer, el estado de los supuestos, las revisiones humanas, el
    resultado experimental y lo pendiente de revisar. Los partidos del torneo se
    dejan fuera a propósito: mueven el Elo, no la certeza (S-13)."""
    supuestos = sorted((str(s.get("texto")), str(s.get("estado"))) for s in (h.get("supuestos") or []) if isinstance(s, dict))
    resultado = ((h.get("experimento") or {}) if isinstance(h.get("experimento"), dict) else {}).get("resultado")
    resultado_clave = [resultado.get("fecha"), resultado.get("veredicto"), resultado.get("clasificacion")] if isinstance(resultado, dict) else None
    try:
        humanas = T.revisiones_humanas(h)
    except Exception:  # noqa: BLE001
        humanas = ""
    novedad = sorted((str(k), str((v or {}).get("detalle"))[:200]) for k, v in (h.get("novedad") or {}).items() if isinstance(v, dict))
    cuerpo = json.dumps([huella_evidencia(h), h.get("decisionKiller"), supuestos, humanas, resultado_clave, bool(h.get("pendienteRevision")), novedad], ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(cuerpo.encode("utf-8")).hexdigest()


def motivo_para_reconcluir(h: dict[str, Any], con_evidencia: set[str] | None = None) -> str | None:
    """Por qué hay que rehacer la conclusión de `h` al cerrar, o None si se
    conserva: sin conclusión previa, evidencia nueva en esta iteración, cambio
    editorial de una fuente, pendiente de revisar, marca quitada por un resultado
    (laboratorio, in silico), o la huella de la evidencia contada cambió."""
    conclusion = h.get("conclusion")
    if not isinstance(conclusion, dict):
        return "sin conclusión previa"
    if con_evidencia and h.get("id") in con_evidencia:
        return "evidencia nueva en esta iteración"
    if h.get("_recalcularPorFuente"):
        return "cambio editorial de una fuente"
    if h.get("pendienteRevision"):
        return "pendiente de revisar"
    if "_conclusionIntentada" not in h:
        return "resultado o evidencia nueva marcada"
    if conclusion.get("huella") != huella_de_conclusion(h):
        return "la evidencia contada cambió"
    return None


def _ultima_decision_killer(e: dict[str, Any], h: dict[str, Any]) -> dict[str, Any] | None:
    propias = [d for d in e.get("decisiones", []) if isinstance(d, dict) and d.get("hipotesisId") == h.get("id") and str(d.get("etapa", "")).startswith("killer")]
    return max(propias, key=lambda d: int(d.get("fecha") or 0)) if propias else None


def _hubo_evidencia_despues(e: dict[str, Any], h: dict[str, Any], fecha: int) -> bool:
    """Para decisiones anteriores a la huella: hubo un evento de evidencia nueva
    (o un resultado de laboratorio) para esta hipótesis después de la decisión."""
    sufijo = f"/hipotesis/{h.get('id')}"
    for ev in e.get("eventos", []) or []:
        if not isinstance(ev, dict) or ev.get("tipo") != "revision_automatica" or int(ev.get("t") or 0) <= fecha:
            continue
        if str(ev.get("ruta") or "").endswith(sufijo) and str(ev.get("texto") or "").startswith("Evidencia nueva para"):
            return True
    resultado = ((h.get("experimento") or {}) if isinstance(h.get("experimento"), dict) else {}).get("resultado")
    return isinstance(resultado, dict) and int(resultado.get("fecha") or 0) > fecha


def pedir_revision_por_huella(e: dict[str, Any], ahora: int, investigacion_id: str | None = None) -> int:
    """Marca `_revisionPedida` en toda hipótesis viva (propuesta o en revisión) que
    ya pasó por el Killer y cuya huella de evidencia difiere de la que el Killer
    vio al decidir (`decision.huella`, o `_huellaKiller`; para decisiones sin
    huella, un evento de evidencia nueva posterior). Cada huella se pide una sola
    vez (`_huellaRevisionPedida`) y se respeta el tope de intentos. Devuelve
    cuántas peticiones nuevas dejó (S-08)."""
    n = 0
    for h in e.get("hipotesis", []) or []:
        if not isinstance(h, dict) or h.get("estado") not in ("propuesta", "en_revision") or h.get("fusionadaEn"):
            continue
        if investigacion_id is not None and h.get("investigacionId") != investigacion_id:
            continue
        d = _ultima_decision_killer(e, h)
        if d is None:
            continue  # nunca juzgada: la juzga el paso de hipótesis como nueva
        if int(h.get("_killerIntentos") or 0) >= MAX_INTENTOS_KILLER:
            continue
        actual = huella_evidencia(h)
        guardada = d.get("huella") or h.get("_huellaKiller")
        cambio = (guardada != actual) if guardada else _hubo_evidencia_despues(e, h, int(d.get("fecha") or 0))
        if not cambio or h.get("_huellaRevisionPedida") == actual:
            continue
        h["_huellaRevisionPedida"] = actual
        if h.get("_revisionPedida"):
            continue
        h["_revisionPedida"] = True
        registro = (h.get("procedencia") or {}).get("registro")
        if isinstance(registro, list):
            registro.append(f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} revisión pedida: la evidencia cambió desde la última decisión del Killer")
        n += 1
    return n


def _direccion_por_regla_local(h: dict[str, Any], direccion_juez: str) -> tuple[str, bool]:
    """Dirección de la conclusión por regla (M-07): "en_contra" o "mixta" solo si
    hay alguna afirmación sostenida en contra (relación contradice, no sintética)
    o un resultado experimental que refuta; "sin_evidencia_directa" si no hay
    apoyos o el juez lo dijo y no hay apoyos directos; "apoya" en el resto.
    Devuelve también si el juez apoyaba su "mixta" en un supuesto contradicho."""
    sostenidas = [a for a in (h.get("afirmaciones") or []) if isinstance(a, dict) and a.get("veredicto") in ("sostenida", "parcial") and not a.get("sintetico")]
    contras = sum(1 for a in sostenidas if a.get("relacion") == "contradice")
    apoyos = sum(1 for a in sostenidas if a.get("relacion") in (None, "apoya", "apoya_indirecta"))
    resultado = ((h.get("experimento") or {}) if isinstance(h.get("experimento"), dict) else {}).get("resultado")
    refuta = isinstance(resultado, dict) and resultado.get("veredicto") == "refuta" and not resultado.get("sintetico")
    if refuta or (contras and not apoyos):
        return "en_contra", False
    if contras:
        return "mixta", False
    if apoyos == 0 or direccion_juez == "sin_evidencia_directa":
        return "sin_evidencia_directa", False
    return "apoya", False


def direccion_por_regla(h: dict[str, Any], direccion_juez: str) -> tuple[str, bool]:
    """La dirección por regla del grupo B1 (`T.direccion_por_regla(afirmaciones,
    propuesta, experimento)`, rosa/bucle/contexto.py) si existe; si no, la local
    con la misma regla. Devuelve (dirección, supuesto_contradicho): lo segundo es
    True cuando el juez apoyaba su "mixta" o "en contra" en un supuesto
    contradicho y la regla la dejó en "apoya"; la frase plantilla lo dice."""
    direccion = None
    fn = getattr(T, "direccion_por_regla", None)
    if callable(fn):
        try:
            v = fn(h.get("afirmaciones"), direccion_juez, h.get("experimento") if isinstance(h.get("experimento"), dict) else None)
            if isinstance(v, str) and v:
                direccion = v
        except Exception:  # noqa: BLE001
            traceback.print_exc()
    if direccion is None:
        direccion, _ = _direccion_por_regla_local(h, direccion_juez)
    hay_supuesto_contradicho = any(isinstance(s_, dict) and s_.get("estado") == "contradicho" for s_ in (h.get("supuestos") or []))
    return direccion, bool(direccion == "apoya" and hay_supuesto_contradicho and direccion_juez in ("mixta", "en_contra"))


ESTADOS_EN_COLA = ("propuesta", "en_revision")
_ETIQUETA_KILLER = {"descartar_en_contexto": "descarte propuesto por el Killer", "descartar": "descarte propuesto por el Killer", "suspender": "suspendida por el Killer", "reformular": "reformular", "avanzar": "avanzar"}


def _motivo_killer(e: dict[str, Any], h: dict[str, Any]) -> str:
    d = _ultima_decision_killer(e, h)
    motivo = str((d or {}).get("motivo") or "").strip()
    return motivo[:200] if motivo else "sin motivo registrado"


def _cola_de_hipotesis_local(e: dict[str, Any], investigacion_id: str) -> str:
    """El listado por regla de la cola: cada hipótesis viva con título, estado,
    decisión del Killer con su motivo real y fecha de nacimiento, más la línea de
    recuento. Es lo que leen el resumen técnico y el llano en vez de inventarlo."""
    vivas = [h for h in e.get("hipotesis", []) if isinstance(h, dict) and h.get("investigacionId") == investigacion_id and h.get("estado") != "descartada" and not h.get("fusionadaEn")]
    lineas = []
    for h in sorted(vivas, key=lambda x: int(x.get("creadaEn") or 0)):
        creada = int(h.get("creadaEn") or 0)
        fecha = datetime.fromtimestamp(creada / 1000).strftime("%d/%m/%Y") if creada else "fecha desconocida"
        decision = h.get("decisionKiller")
        killer = f"{_ETIQUETA_KILLER.get(str(decision), str(decision))}: {_motivo_killer(e, h)}" if decision else "sin juzgar todavía"
        lineas.append(f"- {str(h.get('titulo') or '')[:100]} [estado {h.get('estado')}; Killer: {killer}; nació el {fecha}]")
    return (frase_de_la_cola(e, investigacion_id) + "\n" + "\n".join(lineas)) if lineas else "Ninguna hipótesis viva en la cola"


def cola_de_hipotesis(e: dict[str, Any], investigacion_id: str) -> str:
    """`T.cola_de_hipotesis` (grupo B) si existe; si no, la local con el mismo contrato."""
    fn = getattr(T, "cola_de_hipotesis", None)
    if callable(fn):
        try:
            v = fn(e, investigacion_id)
            if isinstance(v, str) and v:
                return v
        except Exception:  # noqa: BLE001
            traceback.print_exc()
    return _cola_de_hipotesis_local(e, investigacion_id)


def frase_de_la_cola(e: dict[str, Any], investigacion_id: str, nacidas: int | None = None) -> str:
    """La frase de recuento de la cola, generada por regla y que el modelo no toca:
    "9 hipótesis en cola: 5 con descarte propuesto por el Killer, 4 suspendidas,
    0 sin juzgar; 0 nacieron en esta iteración"."""
    en_cola = [h for h in e.get("hipotesis", []) if isinstance(h, dict) and h.get("investigacionId") == investigacion_id and h.get("estado") in ESTADOS_EN_COLA and not h.get("fusionadaEn")]
    descarte = sum(1 for h in en_cola if h.get("decisionKiller") in ("descartar_en_contexto", "descartar"))
    suspendidas = sum(1 for h in en_cola if h.get("decisionKiller") == "suspender")
    sin_juzgar = sum(1 for h in en_cola if not h.get("decisionKiller"))
    otras = len(en_cola) - descarte - suspendidas - sin_juzgar
    n = len(en_cola)
    frase = f"{n} hipótesis en cola: {descarte} con descarte propuesto por el Killer, {suspendidas} {'suspendida' if suspendidas == 1 else 'suspendidas'}, {sin_juzgar} sin juzgar" + (f", {otras} con otra decisión" if otras else "")
    if nacidas is not None:
        frase += f"; {nacidas} {'nació' if nacidas == 1 else 'nacieron'} en esta iteración"
    return frase


def estado_de_la_cola(e: dict[str, Any], investigacion_id: str) -> str:
    """Una línea por hipótesis viva con la decisión del Killer y su motivo real
    (última decisión registrada), para que el resumen en llano no invente el
    motivo de una suspensión."""
    vivas = [h for h in e.get("hipotesis", []) if isinstance(h, dict) and h.get("investigacionId") == investigacion_id and h.get("estado") != "descartada" and not h.get("fusionadaEn")]
    if not vivas:
        return "Ninguna"
    return "\n".join(f"- {str(h.get('titulo') or '')[:100]}: decisión del Killer «{h.get('decisionKiller') or 'sin decisión todavía'}» ({_motivo_killer(e, h) if h.get('decisionKiller') else 'aún no juzgada'}), estado «{h.get('estado')}»" for h in vivas)


def _evaluacion_sin_presupuesto(corrida: dict[str, Any], casos: int) -> dict[str, Any]:
    """La evaluación que queda cuando la corrida no tiene presupuesto: incompleta
    (0 juzgadas de N), con la nota de qué hacer."""
    return {"conjunto": "hipótesis con decisión humana", "casos": casos, "juzgadas": 0, "sinRespuesta": casos, "antes": None, "despues": None, "nota": f"Sin presupuesto en la corrida {corrida.get('numero')} ({str(corrida.get('estado', '')).replace('_', ' ')}): la evaluación no se hizo. Amplía el presupuesto de una corrida viva o abre otra y vuelve a evaluar"}


def evaluacion_pareada(r_antes: dict[str, Any], r_despues: dict[str, Any], casos: int) -> dict[str, Any]:
    """La evaluación de un criterio a partir de las dos pasadas del Killer: el
    acuerdo antes y después se calcula solo sobre las hipótesis juzgadas en las
    dos (comparación pareada). Si el juez no respondió en alguna, `juzgadas` <
    `casos`, la nota lo dice y `_fijar_evaluacion` no da por evaluado nada."""
    pareadas = [hid for hid in r_antes.get("acuerdos", {}) if hid in r_despues.get("acuerdos", {})]
    juzgadas = len(pareadas)
    sin_respuesta = casos - juzgadas
    antes = round(sum(1 for hid in pareadas if r_antes["acuerdos"][hid]) / juzgadas, 3) if juzgadas else None
    despues = round(sum(1 for hid in pareadas if r_despues["acuerdos"][hid]) / juzgadas, 3) if juzgadas else None
    if sin_respuesta > 0:
        nota = f"{sin_respuesta} de {casos} sin respuesta del juez: la cifra no se da por medida. Vuelve a evaluar cuando el juez responda" + (f" (sobre las {juzgadas} juzgadas: {antes} antes, {despues} después)" if juzgadas else "")
    elif despues is not None and antes is not None and despues > antes:
        nota = "Mejora el acuerdo con las decisiones humanas"
    elif despues is not None and antes is not None and despues < antes:
        nota = "Empeora el acuerdo"
    else:
        nota = "No cambia el acuerdo"
    return {"conjunto": "hipótesis con decisión humana", "casos": casos, "juzgadas": juzgadas, "sinRespuesta": sin_respuesta, "antes": antes, "despues": despues, "nota": nota}


def _ruta_segura(e: dict[str, Any], h: dict[str, Any]) -> dict[str, Any] | None:
    """`RUTA.evaluar_ruta` sin que un fallo de la regla tumbe la mutación que
    guarda la conclusión o el resultado: si falla, se deja la ruta anterior
    (o None) y el error queda en la consola."""
    try:
        return RUTA.evaluar_ruta(e, h)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return h.get("ruta")


def _anadir_contrato(experimento: dict[str, Any], propuesta: Any) -> None:
    """Añade al experimento las claves del contrato (`XP.CLAVES_CONTRATO`), la
    lista de problemas y la huella de las lecturas. Va aparte de la llamada al
    modelo: si la regla del contrato fallara, el protocolo que el cerebro ya
    devolvió (una llamada pagada) no se pierde; quedan los valores vacíos, un
    problema que lo dice y el error en la consola."""
    try:
        experimento.update(XP.contrato_desde_propuesta(propuesta))
        experimento["problemasContrato"] = XP.validar_contrato(experimento)
        experimento["hashLecturas"] = XP.hash_lecturas(experimento)
    except Exception as ex:  # noqa: BLE001
        traceback.print_exc()
        for k, v in XP.CLAVES_CONTRATO.items():
            experimento.setdefault(k, copy.deepcopy(v))
        experimento["problemasContrato"] = [f"no pude leer el contrato de la propuesta ({type(ex).__name__}): lecturas, sistema y propósito quedan sin declarar"]
        try:
            experimento["hashLecturas"] = XP.hash_lecturas(experimento)
        except Exception:  # noqa: BLE001
            experimento["hashLecturas"] = ""


def _linea_contrato(experimento: dict[str, Any]) -> str:
    """La línea del registro de procedencia que resume el contrato del experimento."""
    lecturas = experimento.get("lecturas") if isinstance(experimento.get("lecturas"), list) else []
    sistema = experimento.get("sistema") or {}
    problemas = experimento.get("problemasContrato") if isinstance(experimento.get("problemasContrato"), list) else []
    tipo = sistema.get("tipo") if isinstance(sistema, dict) else None
    return f"contrato del experimento: {len(lecturas)} {'lectura' if len(lecturas) == 1 else 'lecturas'}, sistema {XP.etiqueta(XP.SISTEMAS_EXPERIMENTALES, tipo) if tipo else 'no declarado'}, {len(problemas)} {'problema' if len(problemas) == 1 else 'problemas'}"


def _veredictos_por_lectura(experimento: dict[str, Any], resultado: dict[str, Any]) -> list[dict[str, Any]]:
    """`XP.veredicto_por_lecturas` protegido: un experimento antiguo sin lecturas
    da lista vacía, y un fallo de la regla también (con el error en consola)."""
    try:
        return XP.veredicto_por_lecturas(experimento, resultado)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return []


def _lectura_del_negativo(veredictos: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        r = XP.lectura_del_negativo(veredictos)
        return {"rama": r.get("rama"), "explicacion": r.get("explicacion", "")}
    except Exception as ex:  # noqa: BLE001
        traceback.print_exc()
        return {"rama": None, "explicacion": f"No pude leer el negativo por lecturas ({type(ex).__name__})."}


def _cuestiones_por_hueco(e: dict[str, Any], investigacion_id: str, huecos: list[Any], ahora: int, maximo: int = 6) -> int:
    """Cada hueco del mapa de la enfermedad (una combinación de estadio, región
    o célula que la misión nombra y nada cubre) se abre como cuestión para que
    el planificador busque en amplitud por ahí. No se repite una abierta con el
    mismo texto; `CU.registrar` además funde las equivalentes y respeta el tope."""
    abiertas = {str(c.get("texto") or "") for c in CU.abiertas(e, investigacion_id)}
    nuevas = 0
    for hueco in huecos[:maximo] if isinstance(huecos, list) else []:
        if not isinstance(hueco, dict) or not isinstance(hueco.get("motivo"), str):
            continue
        texto = hueco["motivo"].strip()
        if not texto or texto in abiertas:
            continue
        cuestion = CU.nueva(investigacion_id, texto, {"tipo": "analisis", "id": None}, "un hecho o una hipótesis que sitúe esa combinación por su contenido", ahora)
        # `registrar` devuelve también la cuestión con la que se fundió o la que
        # ya estaba resuelta: solo cuenta como nueva la que de verdad entró.
        _, motivo = CU.registrar_con_motivo(e, cuestion)
        abiertas.add(texto)
        if motivo == "nueva":
            nuevas += 1
    return nuevas


def _anadir_aprendizaje_al_llano(e: dict[str, Any], corrida_id: str, it: dict[str, Any]) -> None:
    """Pega al resumen en llano de la iteración el párrafo de las cifras de
    aprendizaje (clave `aprendizaje`) cuando las cifras guardadas en la
    investigación son las de esa misma iteración. Sirve para el resumen en
    llano que llega tarde (`_completar_en_llano_paso`), que si no se quedaría
    sin ese párrafo aunque el cierre ya lo hubiera calculado."""
    llano = it.get("resumenLlano")
    if not isinstance(llano, dict) or llano.get("aprendizaje"):
        return
    c = next((x for x in e.get("corridas", []) if isinstance(x, dict) and x.get("id") == corrida_id), None)
    inv = next((i for i in e.get("investigaciones", []) if isinstance(i, dict) and c and i.get("id") == c.get("investigacionId")), None)
    cifras = (inv or {}).get("cifrasAprendizaje")
    if isinstance(cifras, dict) and cifras.get("iteracion") == it.get("numero") and isinstance(cifras.get("texto"), str) and cifras["texto"]:
        llano["aprendizaje"] = cifras["texto"]


def _vistas_de_programa_al_cerrar(e2: dict[str, Any], inv_id: str, it2: dict[str, Any], ahora: int) -> None:
    """Escribe en la investigación `mapaEnfermedad`, `mapaRuta` y
    `cifrasAprendizaje` (cada uno con fecha e iteración), añade el texto de las
    cifras al resumen en llano de la iteración y abre una cuestión por hueco
    del mapa. Cada pieza va en su propio try: si falla, queda una incidencia y
    las demás siguen; el cierre de la iteración nunca se cae por una vista."""
    inv2 = next((i for i in e2["investigaciones"] if isinstance(i, dict) and i.get("id") == inv_id), None)
    if inv2 is None:
        return
    if not isinstance(it2, dict):
        it2 = {}  # iteración con forma rara: se escriben las vistas sin número ni resumen en llano
    n = it2.get("numero")
    try:
        mapa = MAPA.mapa(e2, inv_id)
        # Las etiquetas y definiciones se copian: el estado no debe compartir
        # referencias con las constantes del módulo (una mutación las cambiaría).
        inv2["mapaEnfermedad"] = {**mapa, "fecha": ahora, "iteracion": n, "etiquetas": copy.deepcopy(MAPA.ETIQUETAS), "definiciones": {"estadio": dict(MAPA.DEFINICIONES_ESTADIO), "nivel": dict(MAPA.DEFINICIONES_NIVEL)}}
        abiertas = _cuestiones_por_hueco(e2, inv_id, list(mapa.get("huecos") or []), ahora)
        if abiertas:
            A.con_evento(e2, inv_id, "aprendizaje", f"El mapa de la enfermedad deja {abiertas} {'hueco' if abiertas == 1 else 'huecos'} que la misión nombra y nada cubre; quedan como cuestiones abiertas para buscar en amplitud", f"#/investigaciones/{inv_id}/investigacion", ahora)
    except Exception as ex:  # noqa: BLE001
        traceback.print_exc()
        A.con_evento(e2, inv_id, "incidencia", f"No pude construir el mapa de la enfermedad al cerrar la iteración {n}: {type(ex).__name__}: {str(ex)[:160]}", f"#/investigaciones/{inv_id}/corrida", ahora)
    try:
        inv2["mapaRuta"] = {**RUTA.mapa_ruta(e2, inv_id), "fecha": ahora, "iteracion": n}
    except Exception as ex:  # noqa: BLE001
        traceback.print_exc()
        A.con_evento(e2, inv_id, "incidencia", f"No pude construir el mapa de la ruta terapéutica al cerrar la iteración {n}: {type(ex).__name__}: {str(ex)[:160]}", f"#/investigaciones/{inv_id}/corrida", ahora)
    try:
        cifras = {**CIFRAS.resumen_cifras(e2, inv_id, ahora), "fecha": ahora, "iteracion": n}
        inv2["cifrasAprendizaje"] = cifras
        # El texto de las tres cifras entra al resumen en llano como párrafo aparte
        # (clave `aprendizaje`), antes del detalle técnico; solo si hay resumen en
        # llano: si falta, `_completar_en_llano` lo rellena después y el texto sigue
        # disponible en la investigación.
        llano = it2.get("resumenLlano")
        if isinstance(llano, dict) and cifras.get("texto"):
            llano["aprendizaje"] = cifras["texto"]
    except Exception as ex:  # noqa: BLE001
        traceback.print_exc()
        A.con_evento(e2, inv_id, "incidencia", f"No pude calcular las cifras de aprendizaje al cerrar la iteración {n}: {type(ex).__name__}: {str(ex)[:160]}", f"#/investigaciones/{inv_id}/corrida", ahora)


def _ordenar_plan(plan: list[dict[str, Any]], hay_novedad_pendiente: bool) -> list[dict[str, Any]]:
    """El orden relativo lo decide el modelo, salvo dos dependencias de Rosa:
    el modelo de mundo se actualiza antes de generar hipótesis, y la novedad
    se comprueba después de generarlas (si no hay hipótesis pendientes de
    novedad, un paso de novedad antes de hipótesis no tendría nada que hacer)."""
    tipos = [p.get("tipo") for p in plan]
    if "modelo" in tipos and "hipotesis" in tipos and tipos.index("modelo") > tipos.index("hipotesis"):
        m = plan.pop(tipos.index("modelo"))
        plan.insert([p.get("tipo") for p in plan].index("hipotesis"), m)
        tipos = [p.get("tipo") for p in plan]
    if "novedad" in tipos and "hipotesis" in tipos and tipos.index("novedad") < tipos.index("hipotesis") and not hay_novedad_pendiente:
        n = plan.pop(tipos.index("novedad"))
        plan.insert([p.get("tipo") for p in plan].index("hipotesis") + 1, n)
        tipos = [p.get("tipo") for p in plan]
    # El análisis con datos va después de las hipótesis (necesita su predicción
    # falsable y la decisión del Killer) y antes de la meta-revisión.
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
    # Una evaluación incompleta (el juez no respondió en alguna hipótesis) no da
    # por medido nada: el criterio sigue propuesto y el botón de evaluar sigue ahí (S-24).
    completa = evaluacion.get("juzgadas") is None or int(evaluacion.get("juzgadas") or 0) >= int(evaluacion.get("casos") or 0)
    if not completa:
        A.con_evento(e, c.get("investigacionId"), "aprendizaje", f"Criterio sin evaluar: {evaluacion.get('nota', '')}", "#/ajustes", ahora)
        return True
    if c["estado"] == "propuesto" and evaluacion.get("casos"):
        c["estado"] = "evaluado"
    # Lo que propuso la meta-campaña se revierte solo si empeora: nadie tiene que
    # limpiar detrás de Rosa. Lo que propuso una persona queda evaluado y lo decide ella.
    if str(c.get("origen") or "").startswith("arnes:") and A.empeora_al_evaluar(c):
        c["estado"] = "revertido"
        c["resueltoEn"] = ahora
        c["resueltoPor"] = config.QUIEN_ROSA
        c["evaluacion"] = {**evaluacion, "nota": (evaluacion.get("nota") or "") + " Revertido por Rosa: la meta-campaña solo conserva lo que iguala o mejora."}
    A.con_evento(e, c.get("investigacionId"), "aprendizaje", f"Criterio evaluado sobre {evaluacion.get('casos', 0)} casos: acuerdo {evaluacion.get('antes')} antes, {evaluacion.get('despues')} después. {c['evaluacion'].get('nota', '')}", "#/ajustes", ahora)
    return True


def _quitar_marca_arnes(e: dict[str, Any], corrida_id: str, motivo: str = "") -> bool:
    c = next((x for x in e["corridas"] if x["id"] == corrida_id), None)
    if not c:
        return False
    c.pop("_revisarArnes", None)
    if motivo:
        A.con_evento(e, c["investigacionId"], "incidencia", f"La meta-campaña de la corrida {c['numero']} no se hizo: {motivo}", "#/ajustes", P.ahora_ms())
    return True


MAX_PROPUESTAS_ARNES = 3


def _normal(texto: str) -> str:
    return " ".join((texto or "").lower().split())


def cambios_desde_propuestas(e: dict[str, Any], c: dict[str, Any], propuestas: list[dict[str, Any]], ahora: int) -> list[dict[str, Any]]:
    """Convierte las propuestas de la meta-campaña en cambios de aprendizaje: un
    criterio es nivel 2 propuesto con evaluación pendiente (`_evaluar`); una
    política es nivel 3 propuesto (solo registro, la decide una persona). Se
    descartan las repetidas, las que ya son criterio vigente, las vacías y las de
    tipo desconocido; como mucho MAX_PROPUESTAS_ARNES. Devuelve los cambios creados."""
    vigentes = {_normal(x) for x in e.get("criteriosRevision", [])}
    previas = {_normal(x.get("descripcion", "")) for x in e.get("aprendizaje", []) if x.get("estado") != "revertido"}
    creados: list[dict[str, Any]] = []
    for p in propuestas:
        descripcion = (p.get("descripcion") or "").strip()
        tipo = p.get("tipo")
        if not descripcion or tipo not in ("criterio", "politica") or _normal(descripcion) in vigentes or _normal(descripcion) in previas:
            continue
        motivo = (p.get("motivo") or "").strip()
        riesgo = (p.get("riesgo") or "").strip()
        texto = descripcion + (f" Motivo: {motivo[:200]}" if motivo else "") + (f" Riesgo: {riesgo[:160]}" if riesgo else "")
        cambio = P.nuevo_cambio_aprendizaje(c["investigacionId"], 2 if tipo == "criterio" else 3, tipo, texto[:600], f"arnes:{c['id']}", "propuesto", config.QUIEN_ROSA, ahora)
        if tipo == "criterio":
            # El criterio evaluado es la descripción sola (es lo que entra a criteriosRevision).
            cambio["descripcion"] = descripcion[:400]
            cambio["nota"] = (f"Motivo: {motivo[:300]}" if motivo else "") + (f" Riesgo: {riesgo[:200]}" if riesgo else "")
            cambio["_evaluar"] = ahora
        e.setdefault("aprendizaje", []).append(cambio)
        previas.add(_normal(descripcion))
        creados.append(cambio)
        if len(creados) >= MAX_PROPUESTAS_ARNES:
            break
    return creados


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
    c["metrica"] = PROG.metrica_de_corrida(e, c["id"])
    c["_revisarArnes"] = True  # meta-campaña: el supervisor la recoge
    resumen_m = PROG.resumen_metrica(c["metrica"])
    A.con_evento(e, c["investigacionId"], "corrida_estado", f"Corrida {c['numero']} terminada: {motivo}" + (f". Balance: {resumen_m}" if resumen_m else ""), f"#/investigaciones/{c['investigacionId']}/corrida", ahora)
    return True


MARCA_RELACION = {"contradice": ", EN CONTRA de la hipótesis", "apoya_indirecta": ", apoyo indirecto (otra población, desenlace o plataforma)", "apoya": ", a favor", "socava": ", SOCAVA un apoyo (ataca el método o la inferencia de otra afirmación, no la hipótesis; el apoyo socavado no cuenta para el techo)"}
VERBO_CERTEZA = {"alta": "La evidencia reunida sostiene que", "moderada": "La evidencia reunida probablemente sostiene que", "baja": "La evidencia sugiere, con limitaciones, que", "muy_baja": "La evidencia es muy incierta sobre si"}
VERBO_CONTRA = {"alta": "La evidencia reunida contradice que", "moderada": "La evidencia reunida probablemente contradice que", "baja": "La evidencia sugiere, con limitaciones, que no se cumple que", "muy_baja": "La evidencia es muy incierta sobre si"}


def frase_plantilla(direccion: str, certeza: str, titulo: str, supuesto_contradicho: bool = False) -> str:
    """La frase calibrada de (dirección, certeza), como las tablas de Santesso
    2020 y Cochrane Iberoamerica. El modelo no la escribe: se genera aquí para
    que 'probablemente' signifique siempre lo mismo. El título de la hipótesis
    hace de H con la inicial en minúscula. `supuesto_contradicho`: la dirección
    es a favor por las afirmaciones, pero un supuesto del que depende está
    contradicho; se dice, en vez de llamar "contradictoria" a la evidencia."""
    h = titulo.strip().rstrip(".")
    h = h[:1].lower() + h[1:] if h and not h[:2].isupper() else h
    if direccion == "sin_evidencia_directa":
        return f"No encontramos evidencia directa sobre si {h}. Esto no significa que no exista."
    if direccion == "mixta":
        return f"La evidencia es contradictoria sobre si {h}; la certeza es {certeza.replace('_', ' ')}."
    if direccion == "en_contra":
        return f"{VERBO_CONTRA[certeza]} {h}."
    if supuesto_contradicho:
        return f"{VERBO_CERTEZA[certeza]} {h}, aunque un supuesto del que depende está contradicho por las fuentes."
    return f"{VERBO_CERTEZA[certeza]} {h}."


def _fijar_traspaso(e: dict[str, Any], corrida_id: str, texto: str) -> bool:
    c = next((x for x in e["corridas"] if x["id"] == corrida_id), None)
    if not c:
        return False
    c["traspasoRecibido"] = (texto or "")[:4000]
    return True


def _fijar_estado(e: dict[str, Any], corrida_id: str, estado: str) -> bool:
    c = next((x for x in e["corridas"] if x["id"] == corrida_id), None)
    if not c or c["estado"] == estado:
        return False
    c["estado"] = estado
    return True


def motivo_de_pausa_por_presupuesto(e: dict[str, Any], c: dict[str, Any], tope: str | None = None) -> str:
    """El texto que dice qué tope saltó de verdad. Antes siempre culpaba al tope
    global aunque el que cortó fuera el de la iteración (447 con 400 de 1500
    gastadas), y "ampliar" no lo levantaba (S-15)."""
    it = A.iteracion_actual_de(e, c)
    tope = tope or tope_agotado_en(e, c["id"], (it or {}).get("numero")) or "corrida"
    gasto = int(c["gasto"].get("llamadas") or 0)
    limite = int(c["presupuesto"].get("limiteLlamadas") or 0)
    if tope == "iteracion" and it is not None:
        pres = it.get("presupuesto") or {}
        return f"La iteración {it['numero']} gastó las {int(pres.get('limite') or 0)} llamadas que le tocaban (la corrida lleva {gasto} de {limite}): la corrida se pausó. Amplía el tope para seguir."
    return f"La corrida agotó su tope de {limite} llamadas ({gasto} gastadas): se pausó. Amplía el tope para seguir."


def _pausar_por_presupuesto(e: dict[str, Any], corrida_id: str, tope: str | None = None) -> bool:
    """Pausa la corrida por presupuesto con el motivo real. Una corrida detenida o
    terminada no se toca: la evaluación de un criterio o una revisión pedida
    sobre una corrida ya cerrada sin presupuesto la ponía en "pausada por
    presupuesto" y el tick la relanzaba como si siguiera viva (adversario de la
    tanda 1, 17 de septiembre de 2026)."""
    c = next((x for x in e["corridas"] if x["id"] == corrida_id), None)
    if not c or c["estado"] in ("pausada_por_presupuesto", "detenida", "terminada"):
        return False
    pendientes = any(s["corridaId"] == corrida_id and s["estado"] == "pendiente" for s in e["solicitudes"]) or any(i["corridaId"] == corrida_id and i["estado"] == "pendiente" and i["tipo"] not in INCIDENCIAS_QUE_NO_BLOQUEAN for i in e["incidencias"])
    c["estado"] = "esperando_aprobacion" if pendientes else "pausada_por_presupuesto"
    motivo = motivo_de_pausa_por_presupuesto(e, c, tope)
    c["presupuesto"]["motivoPausa"] = motivo
    A.con_evento(e, c["investigacionId"], "presupuesto", motivo, f"#/investigaciones/{c['investigacionId']}/corrida", P.ahora_ms())
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


# Un tic del supervisor cada segundo; si entre dos tics pasan más de dos minutos,
# el proceso estuvo suspendido (el equipo dormido, el portátil cerrado) y ese
# hueco no es tiempo de trabajo de la corrida.
UMBRAL_SUSPENSION_MS = 120_000
# Estados en los que la corrida espera a una persona: el plan sin aprobar, un
# permiso pendiente, la pausa a mano y la pausa por presupuesto (alguien tiene
# que ampliarlo). Ese tiempo no cuenta contra el tope en horas.
ESTADOS_DE_ESPERA_HUMANA = ("esperando_plan", "esperando_aprobacion", "pausada", "pausada_por_presupuesto")


def tiempo_trabajo_ms(c: dict[str, Any], ahora: int) -> int:
    """Milisegundos que la corrida ha trabajado de verdad: el reloj de pared menos
    lo que pasó esperando a una persona (plan sin aprobar, permiso de gasto, pausa)
    y menos las pausas del proceso. Es lo que se compara con el tope en horas.
    Antes se comparaba el reloj de pared: la corrida 8 gastó 21 de sus 60 minutos
    esperando la aprobación del plan y la 7 se cerró al despertar el Mac tras una
    noche dormido (Emir, 17 de septiembre de 2026)."""
    return max(0, int(ahora - c["empezadaEn"] - int(c.get("esperaHumanaMs") or 0) - int(c.get("pausaMs") or 0)))


def contabilizar_tiempo(c: dict[str, Any], ahora: int) -> bool:
    """En cada tic: si la corrida espera a una persona, el tiempo desde el tic
    anterior va a `esperaHumanaMs`; si entre tics pasó más de UMBRAL_SUSPENSION_MS,
    el hueco va a `pausaMs`. Devuelve True si cambió algo público."""
    ultimo = c.get("_ultimoTic")
    c["_ultimoTic"] = ahora
    if not isinstance(ultimo, (int, float)) or ahora <= ultimo:
        return False
    delta = int(ahora - ultimo)
    if c.get("estado") in ESTADOS_DE_ESPERA_HUMANA:
        c["esperaHumanaMs"] = int(c.get("esperaHumanaMs") or 0) + delta
        return True
    if delta > UMBRAL_SUSPENSION_MS:
        c["pausaMs"] = int(c.get("pausaMs") or 0) + delta
        return True
    return False


def _condicion_de_parada(texto: str, numero: int, c: dict[str, Any], ahora: int | None = None, mision: dict[str, Any] | None = None) -> str | None:
    """Solo se automatiza lo que se puede medir en el texto de la condición:
    "N iteraciones", "N minutos" u "N horas" de corrida, y "N llamadas".
    Lo demás ("cuando el modelo de mundo deje de cambiar") lo decide la
    investigadora con el botón de detener. Devuelve el motivo o None.
    Además, el presupuesto de la misión en dinero y en horas para la corrida,
    y la parada propia de la corrida (`c["parada"]`: horas, iteraciones,
    llamadas o texto fijados al crearla), lo que llegue primero."""
    ahora = ahora if ahora is not None else P.ahora_ms()
    propia = c.get("parada") or {}
    if propia:
        horas_propias = propia.get("horas")
        if horas_propias and tiempo_trabajo_ms(c, ahora) / 3_600_000 >= float(horas_propias):
            return f"Se cumplió el tiempo fijado para esta corrida ({PARADA.resumen_parada({'horas': horas_propias})})"
        if propia.get("iteraciones") and numero >= int(propia["iteraciones"]):
            return f"Se alcanzaron las {int(propia['iteraciones'])} iteraciones fijadas para esta corrida"
        if propia.get("llamadas") and c["gasto"].get("llamadas", 0) >= int(propia["llamadas"]):
            return f"Se alcanzaron las {int(propia['llamadas'])} llamadas fijadas para esta corrida"
        # Parada por peldaños: N hipótesis han llegado al nivel de certeza pedido.
        if propia.get("certeza") and PROG.hipotesis_en_nivel(c, str(propia["certeza"])) >= int(propia.get("cuantas") or 1):
            n = PROG.hipotesis_en_nivel(c, str(propia["certeza"]))
            return f"{n} {'hipótesis alcanzó' if n == 1 else 'hipótesis alcanzaron'} la certeza {str(propia['certeza']).replace('_', ' ')} fijada para esta corrida"
        # Parada por estancamiento: iteraciones seguidas sin subir ningún peldaño ni añadir hechos.
        if propia.get("sinCambio") and PROG.iteraciones_sin_avance(c) >= int(propia["sinCambio"]):
            return f"{int(propia['sinCambio'])} iteraciones seguidas sin subir ninguna hipótesis de certeza ni añadir hechos, límite fijado para esta corrida"
        if propia.get("texto"):
            motivo_texto = _parada_por_texto(str(propia["texto"]), numero, c, ahora)
            if motivo_texto:
                return motivo_texto + " (fijada para esta corrida)"
    # Lo que la persona fijó para esta corrida manda sobre la condición general de
    # la investigación en ese mismo eje: con "3 horas" en la corrida, el "1 hora"
    # de la investigación no la cierra (pasó en la corrida 9). El presupuesto de la
    # misión sigue contando siempre.
    omitir = {eje for eje, clave in (("tiempo", "horas"), ("iteraciones", "iteraciones"), ("llamadas", "llamadas")) if propia.get(clave)}
    return _parada_por_texto(texto, numero, c, ahora, mision, omitir=frozenset(omitir))


def _parada_por_texto(texto: str, numero: int, c: dict[str, Any], ahora: int, mision: dict[str, Any] | None = None, omitir: frozenset[str] = frozenset()) -> str | None:
    """`omitir`: ejes ("tiempo", "iteraciones", "llamadas") que la corrida ya fijó por
    su cuenta y que el texto de la investigación no debe volver a aplicar."""
    t = texto.lower()
    if mision and mision.get("presupuesto"):
        pres = mision["presupuesto"]
        usd = c["gasto"].get("usd", 0.0)
        if pres.get("usd") and usd >= pres["usd"]:
            return f"Se alcanzó el presupuesto de la misión en dinero ({usd:.2f} de {pres['usd']:.2f} USD estimados)"
        horas = tiempo_trabajo_ms(c, ahora) / 3_600_000
        if pres.get("horas") and horas >= pres["horas"]:
            return f"Se alcanzó el presupuesto de la misión en tiempo ({horas:.1f} de {pres['horas']:.0f} horas)"
    m = re.search(r"(\d+)\s*iteraci", t)
    if m and "iteraciones" not in omitir and numero >= int(m.group(1)):
        return f"Se alcanzaron las {m.group(1)} iteraciones de la condición de parada"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(min\b|minuto|hora|h\b|dia|día)", t)
    if m and "tiempo" not in omitir:
        n = float(m.group(1).replace(",", "."))
        unidad = m.group(2)
        segundos = n * (60 if unidad.startswith("min") else 3600 if unidad in ("hora", "h") or unidad.startswith("hora") else 86400)
        transcurrido = tiempo_trabajo_ms(c, ahora) / 1000
        if transcurrido >= segundos:
            return f"Se cumplio el tiempo de la condición de parada ({m.group(1)} {unidad.rstrip('.')}{'' if unidad.endswith('s') or unidad in ('h', 'min') else 's'})"
    m = re.search(r"(\d+)\s*llamadas", t)
    if m and "llamadas" not in omitir and c["gasto"]["llamadas"] >= int(m.group(1)):
        return f"Se alcanzaron las {m.group(1)} llamadas de la condición de parada"
    return None


def _informe(inv: dict[str, Any], it: dict[str, Any], resumen: str, hechos: list[dict], hipotesis: list[dict], afs: list[dict], bloqueadas: list[dict], consultas: list[dict] | None = None) -> str:
    lineas = [f"# {inv['titulo']}: iteración {it['numero']}", "", resumen, "", "## Plan ejecutado", T.plan_ejecutado(it), "", f"## Hechos nuevos ({len(hechos)})"]
    lineas += [f"- {h['enunciado']} <" + "; ".join(f"{p['referencia']}{', pág. ' + str(p['pagina']) if p['pagina'] else ''}" for p in h["procedencia"]) + ">" for h in hechos] or ["Ninguno"]
    lineas += ["", f"## Hipótesis nuevas en la cola ({len(hipotesis)})"] + ([f"- {h['titulo']}" for h in hipotesis] or ["Ninguna"])
    lineas += ["", f"## Afirmaciones ({len(afs)}), bloqueadas {len(bloqueadas)}"]
    for a in afs[:80]:
        lineas.append(f"- [{a['veredicto']}] {a['texto']} {a['cita']}" + (f" ({a['motivo']})" if a["veredicto"] != "sostenida" else ""))
    lineas += ["", f"## Consultas hechas ({len(consultas or [])})"] + ([f"- {q.get('base', '')}: {q.get('consulta', '')} ({q.get('resultados', '?')} resultados, {datetime.fromtimestamp(q['fecha'] / 1000).strftime('%d/%m/%Y') if q.get('fecha') else 'sin fecha'})" for q in (consultas or [])] or ["Ninguna en esta iteración"])
    return "\n".join(lineas)
