"""Los ejecutores de paso: una funcion por tipo de paso del plan.

Cada ejecutor recibe el contexto de la corrida (almacen, programas, modelos,
ids) y el paso, lanza sus pistas y devuelve un resumen. Escribe en el estado
solo a traves del almacen. Los datos de trabajo de la corrida (fuentes con
sus fragmentos, afirmaciones con su veredicto, consultas hechas) viven en
claves privadas de la corrida (`_fuentes`, `_afirmaciones`,
`_consultasHechas`) que no viajan al navegador.

Reglas que se cumplen aqui:
- Una fuente que no responde es "no pude comprobar", nunca "no hay".
- Toda afirmacion nace `sin_verificar` y solo cambia por el verificador.
- Al modelo de mundo solo entran afirmaciones sostenidas o parciales.
- Las hipotesis nuevas entran a la cola como `propuesta`; nadie las acepta
  por ellas.
"""

from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass
from typing import Any

import dspy

from rosa import config, politicas
from rosa import causal as CAUSAL
from rosa import conectores as CON
from rosa import killer as K
from rosa import verificador as V
from rosa import torneo
from rosa.bucle import contexto as T
from rosa.bucle.pista import Pista
from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen
from rosa.fuentes import clinicaltrials, crossref, europepmc, openalex, opentargets, pdf, pubmed, unpaywall
from rosa.fuentes.base import FuenteNoDisponible
from rosa.gateway import Modelos
from rosa.modulos.contador import ContextoLlamada, PresupuestoAgotado, contexto_actual
from rosa.modulos.firmas import Programas

MAX_FUENTES_POR_CONSULTA = 12
MAX_FUENTES_EXTRAER = 14
MAX_FRAGMENTOS_POR_FUENTE = 6
MAX_PAGINAS_PDF = 14
RELEVANCIA_MINIMA = 5
TAU_COBERTURA = 20.0


class ModeloBloqueado(RuntimeError):
    pass


@dataclass
class Ctx:
    almacen: Almacen
    programas: Programas
    modelos: Modelos
    corrida_id: str
    investigacion_id: str
    iteracion_id: str
    numero: int

    # -- lecturas ---------------------------------------------------------

    @property
    def e(self) -> dict[str, Any]:
        return self.almacen.estado

    def corrida(self) -> dict[str, Any]:
        return next(c for c in self.e["corridas"] if c["id"] == self.corrida_id)

    def inv(self) -> dict[str, Any]:
        return next(i for i in self.e["investigaciones"] if i["id"] == self.investigacion_id)

    def iteracion(self) -> dict[str, Any]:
        return next(i for i in self.e["iteraciones"] if i["id"] == self.iteracion_id)

    def fuentes(self) -> dict[str, dict[str, Any]]:
        return self.corrida().setdefault("_fuentes", {})

    def afirmaciones(self) -> list[dict[str, Any]]:
        return self.corrida().setdefault("_afirmaciones", [])

    def fragmentos_verificador(self) -> list[V.Fragmento]:
        salida = []
        for f in self.fuentes().values():
            for fr in f.get("fragmentos", []):
                salida.append(V.Fragmento(f["id"], f["referencia"], fr["localizador"], fr["texto"], fr.get("encabezado", "")))
        return salida

    # -- escrituras --------------------------------------------------------

    def mutar(self, fn, nombre: str = "bucle") -> Any:
        return self.almacen.mutar(fn, nombre)

    def evento(self, tipo: str, texto: str, ruta: str | None = None) -> None:
        self.mutar(lambda e: A.con_evento(e, self.investigacion_id, tipo, texto, ruta, P.ahora_ms()) or True, "evento")

    def pista(self, paso_id: str | None, tipo: str, titulo: str, fuente: str) -> Pista:
        return Pista(self.almacen, self.iteracion_id, paso_id, tipo, titulo, fuente)

    # -- modelos -----------------------------------------------------------

    async def llamar(self, rol: str, programa, **kwargs) -> Any:
        """Una llamada a un modelo por rol, con el contexto para el contador.
        Si el modelo devuelve vacio o lo bloquea un filtro, reintenta una vez
        con el modelo de volumen y deja una incidencia."""
        lm = {"cerebro": self.modelos.cerebro, "juez": self.modelos.juez, "volumen": self.modelos.volumen}[rol]
        token = contexto_actual.set(ContextoLlamada(self.corrida_id, self.numero, rol))
        try:
            try:
                with dspy.context(lm=lm):
                    return await programa.acall(**kwargs)
            except PresupuestoAgotado:
                raise
            except Exception as ex:  # noqa: BLE001
                texto = str(ex)
                bloqueado = any(s in texto.lower() for s in ("content", "filter", "policy", "refus", "empty", "no output", "parse"))
                if not bloqueado or rol == "volumen":
                    raise
                self.incidencia("modelo_bloqueado", f"El modelo {lm.model} no respondio a una peticion", texto[:400], lm.model, "Se reintento con Sonnet 5 automaticamente; si vuelve a pasar, revisar el prompt o cambiar el modelo del rol.")
                with dspy.context(lm=self.modelos.volumen):
                    return await programa.acall(**kwargs)
        finally:
            contexto_actual.reset(token)

    def incidencia(self, tipo: str, titulo: str, detalle: str, recurso: str, alternativa: str | None) -> None:
        ahora = P.ahora_ms()

        def fn(e: dict[str, Any]) -> bool:
            for inc in e["incidencias"]:
                if inc["corridaId"] == self.corrida_id and inc["estado"] == "pendiente" and inc["recurso"] == recurso and inc["tipo"] == tipo:
                    return False
            e["incidencias"].append({"id": P.nuevo_id("inc"), "corridaId": self.corrida_id, "tipo": tipo, "titulo": titulo, "detalle": detalle, "recurso": recurso, "alternativa": alternativa, "estado": "pendiente", "creadaEn": ahora, "resueltaEn": None, "resolucion": None})
            A.con_evento(e, self.investigacion_id, "incidencia", f"Incidencia: {titulo}", f"#/investigaciones/{self.investigacion_id}/corrida", ahora)
            return True

        self.mutar(fn, "incidencia")


# ---------------------------------------------------------------------------
# Literatura
# ---------------------------------------------------------------------------


def _registrar_fuente(ctx: Ctx, datos: dict[str, Any], tipo: str, fragmentos: list[dict[str, str]], relevancia: int, marca: str | None, marca_detalle: str, comprobada_en: int | None, consulta: str | None = None) -> str:
    """Anade una fuente al almacen privado de la corrida (o la actualiza) y
    devuelve su id."""
    clave = (datos.get("doi") or datos.get("pmid") or datos.get("nct") or datos.get("titulo", "")).lower()

    def fn(e: dict[str, Any]) -> str:
        c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
        fuentes = c.setdefault("_fuentes", {})
        existente = next((f for f in fuentes.values() if f.get("_clave") == clave), None)
        if existente:
            vistos = {fr["localizador"] for fr in existente["fragmentos"]}
            existente["fragmentos"].extend(fr for fr in fragmentos if fr["localizador"] not in vistos)
            existente["relevancia"] = max(existente.get("relevancia", 0), relevancia)
            existente["textoCompleto"] = existente["textoCompleto"] or any(fr["localizador"] != "resumen" for fr in fragmentos)
            if consulta and consulta not in existente.setdefault("consultas", []):
                existente["consultas"].append(consulta)
            return existente["id"]
        tipo_estudio, nivel = pubmed.tipo_estudio(datos.get("tipos", []), datos.get("titulo", ""))
        f = P.nueva_fuente(
            referencia=datos["referencia"],
            titulo=datos.get("titulo", ""),
            tipo=tipo,
            doi=datos.get("doi"),
            pmid=datos.get("pmid"),
            nct=datos.get("nct"),
            pagina=None,
            fragmento=(fragmentos[0]["texto"][:300] if fragmentos else ""),
            retraccion=marca,
            retraccionComprobadaEn=comprobada_en,
            anio=datos.get("anio"),
            autores=list(datos.get("autores", []))[:12],
            centro=(datos.get("centro") or None),
            tipoEstudio=tipo_estudio if tipo != "ensayo" else "registro",
            nivelEvidencia=nivel,
            textoCompleto=any(fr["localizador"] != "resumen" for fr in fragmentos),
            citas=datos.get("citas"),
        )
        f["_clave"] = clave
        f["_marcaDetalle"] = marca_detalle
        f["fragmentos"] = fragmentos
        f["relevancia"] = relevancia
        f["extraida"] = False
        f["iteracion"] = ctx.numero
        f["consultas"] = [consulta] if consulta else []
        fuentes[f["id"]] = f
        return f["id"]

    return ctx.mutar(fn, "fuente")


async def _fragmentos_de(ctx: Ctx, datos: dict[str, Any], pista: Pista, con_texto_completo: bool) -> list[dict[str, str]]:
    """Resumen siempre; texto completo por paginas (PDF) o secciones (JATS)
    si esta disponible y la fuente es relevante."""
    fragmentos: list[dict[str, str]] = []
    if datos.get("resumen"):
        fragmentos.append({"localizador": "resumen", "texto": datos["resumen"], "encabezado": datos.get("titulo", "")})
    if not con_texto_completo:
        return fragmentos
    # 1. PDF en acceso abierto: pagina exacta.
    url_pdf = datos.get("pdf")
    if not url_pdf and datos.get("doi"):
        try:
            oa = await unpaywall.pdf_de(datos["doi"])
            url_pdf = oa["url"] if oa else None
        except FuenteNoDisponible as ex:
            pista.nota(f"Unpaywall no respondio para {datos['referencia']}: {ex}")
    if url_pdf:
        try:
            ruta = await pdf.descargar(url_pdf)
            if ruta:
                pags = pdf.paginas(ruta)[:MAX_PAGINAS_PDF]
                for p in pags:
                    fragmentos.append({"localizador": f"pág. {p['pagina']}", "texto": p["texto"], "encabezado": datos.get("titulo", ""), "_ruta": str(ruta)})
                pista.resultado(f"{datos['referencia']}: PDF con {len(pags)} paginas leidas")
                return fragmentos
        except FuenteNoDisponible as ex:
            pista.nota(f"PDF no descargable de {datos['referencia']}: {str(ex)[:120]}")
    # 2. XML de Europe PMC: seccion como localizador.
    if datos.get("pmcid"):
        try:
            secciones = await europepmc.texto_completo(datos["pmcid"])
            for s in secciones[:MAX_FRAGMENTOS_POR_FUENTE * 2]:
                fragmentos.append({"localizador": f"sección {s['seccion'][:60]}", "texto": s["texto"], "encabezado": s["seccion"]})
            if secciones:
                pista.resultado(f"{datos['referencia']}: texto completo en {len(secciones)} secciones (Europe PMC)")
        except FuenteNoDisponible as ex:
            pista.nota(f"Europe PMC sin texto completo para {datos['pmcid']}: {str(ex)[:120]}")
    return fragmentos


async def _consulta_literatura(ctx: Ctx, paso: dict[str, Any], consulta: dict[str, str], preguntas: str) -> dict[str, int]:
    base = consulta["base"]
    nombre_base = {"pubmed": "PubMed", "europepmc": "Europe PMC", "preprints": "bioRxiv y medRxiv (via Europe PMC)"}[base]
    pista = ctx.pista(paso["id"], "literatura", consulta["tema"][:80] or consulta["consulta"][:80], nombre_base)
    resultado = {"identificados": 0, "cribados": 0, "textoCompleto": 0, "leidos": 0}
    try:
        pista.accion(f"Consulta: {consulta['consulta']}")
        ahora = P.ahora_ms()
        if base == "pubmed":
            ids, total = await pubmed.buscar(consulta["consulta"], maximo=MAX_FUENTES_POR_CONSULTA)
            pista.accion("esearch + efetch", {"base": "PubMed E-utilities", "parametros": f"db=pubmed&term={consulta['consulta']}&retmax={MAX_FUENTES_POR_CONSULTA}", "resultados": f"{total} PMID, se traen {len(ids)}"})
            articulos = await pubmed.detalles(ids)
        else:
            articulos, total = await europepmc.buscar(consulta["consulta"], maximo=MAX_FUENTES_POR_CONSULTA, solo_preprints=(base == "preprints"))
            pista.accion("REST search", {"base": "Europe PMC", "parametros": f"query={consulta['consulta']}{' AND SRC:PPR' if base == 'preprints' else ''}&pageSize={MAX_FUENTES_POR_CONSULTA}&resultType=core", "resultados": f"{total} resultados, se traen {len(articulos)}"})
        resultado["identificados"] = total

        def anotar(e: dict[str, Any]) -> bool:
            c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
            c["busqueda"]["consultas"].append({"base": nombre_base, "consulta": consulta["consulta"], "fecha": ahora, "resultados": total, "iteracion": ctx.numero, "tema": consulta["tema"]})
            c["busqueda"]["identificados"] += total
            c.setdefault("_consultasHechas", []).append(consulta["consulta"])
            return True

        ctx.mutar(anotar, "consulta")
        pista.resultado(f"{total} resultados en {nombre_base}; {len(articulos)} para cribar")
        if not articulos:
            pista.cerrar(f"{total} resultados, ninguno traido", "hecha")
            return resultado

        # Cribado por relevancia (Sonnet 5), como el RCS de PaperQA.
        puntuados: list[tuple[int, dict[str, Any], str]] = []
        sem = asyncio.Semaphore(4)

        async def puntuar(a: dict[str, Any]) -> None:
            async with sem:
                try:
                    pred = await ctx.llamar("volumen", ctx.programas.relevancia, preguntas_abiertas=preguntas, titulo=a.get("titulo", ""), resumen=K.como_dato((a.get("resumen") or "")[:3000]))
                    puntuados.append((int(pred.puntuacion), a, pred.motivo))
                except PresupuestoAgotado:
                    raise
                except Exception as ex:  # noqa: BLE001
                    puntuados.append((0, a, f"sin puntuar: {str(ex)[:80]}"))

        await asyncio.gather(*(puntuar(a) for a in articulos if a.get("titulo")))
        puntuados.sort(key=lambda x: -x[0])
        relevantes = [x for x in puntuados if x[0] >= RELEVANCIA_MINIMA]
        resultado["cribados"] = len(relevantes)
        pista.resultado(f"Cribado: {len(relevantes)} de {len(puntuados)} relevantes (puntuacion >= {RELEVANCIA_MINIMA}); descartados: " + ", ".join(f"{a['referencia']} ({p})" for p, a, _ in puntuados if p < RELEVANCIA_MINIMA)[:300])

        for i, (puntuacion, a, motivo) in enumerate(relevantes):
            if pista.detenida():
                break
            marca, detalle, comprobada = None, "Sin DOI: no se pudo comprobar en Crossref", None
            if a.get("doi"):
                try:
                    marca, detalle = await crossref.marca_editorial(a["doi"])
                    comprobada = P.ahora_ms()
                except FuenteNoDisponible as ex:
                    detalle = f"Crossref no respondio: {str(ex)[:100]}. No se afirma que este limpio."
            if marca == "retractado":
                pista.error(f"{a['referencia']} esta RETRACTADO ({detalle}); se guarda marcado y no se usa como respaldo")
            con_texto = i < 4 and puntuacion >= 7
            fragmentos = await _fragmentos_de(ctx, a, pista, con_texto)
            if any(fr["localizador"] != "resumen" for fr in fragmentos):
                resultado["textoCompleto"] += 1
            tipo = "preprint" if a.get("preprint") or base == "preprints" else "articulo"
            _registrar_fuente(ctx, a, tipo, fragmentos, puntuacion, marca, detalle, comprobada, consulta["consulta"])
            resultado["leidos"] += 1
            pista.resultado(f"{a['referencia']} (relevancia {puntuacion}): {motivo[:100]}")

        pista.cerrar(f"{total} resultados, {len(relevantes)} relevantes, {resultado['textoCompleto']} con texto completo")
    except PresupuestoAgotado:
        pista.cerrar("Presupuesto agotado: la pista se retoma al ampliarlo", "detenida")
        raise
    except FuenteNoDisponible as ex:
        pista.fallar(f"{nombre_base} no respondio: {str(ex)[:160]}. No es 'sin resultados': la consulta no llego.")
        _contar_fallo_fuente(ctx, nombre_base, str(ex))
    return resultado


def _contar_fallo_fuente(ctx: Ctx, base: str, error: str) -> None:
    def fn(e: dict[str, Any]) -> bool:
        c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
        fallos = c.setdefault("_fallosFuente", {})
        fallos[base] = fallos.get(base, 0) + 1
        return True

    ctx.mutar(fn, "fallo_fuente")
    if ctx.corrida().get("_fallosFuente", {}).get(base, 0) >= 3:
        ctx.incidencia("fuente_sin_respuesta", f"{base} lleva 3 fallos seguidos", error[:400], base, "Comprobar la conexion o esperar; Rosa sigue con las demas fuentes.")


async def paso_literatura(ctx: Ctx, paso: dict[str, Any]) -> str:
    inv = ctx.inv()
    e = ctx.e
    preguntas = T.preguntas_abiertas(e["hechos"], ctx.investigacion_id, inv["objetivo"])
    previas = ctx.corrida().get("_consultasHechas", [])
    pred = await ctx.llamar("cerebro", ctx.programas.consultas, objetivo=inv["objetivo"], preguntas_abiertas=preguntas, hipotesis_vivas=T.hipotesis_vivas(e["hipotesis"], ctx.investigacion_id), consultas_previas="\n".join(previas[-20:]) or "Ninguna", indicaciones_humanas=T.indicaciones_humanas(ctx.iteracion()) + ("\n" + paso["detalle"] if paso.get("detalle") else ""))
    consultas = [c.model_dump() for c in pred.consultas][:5]
    if not consultas:
        return "El modelo no propuso consultas"
    resultados = await asyncio.gather(*(_consulta_literatura(ctx, paso, c, preguntas) for c in consultas))
    total = {k: sum(r[k] for r in resultados) for k in resultados[0]} if resultados else {}
    leidos_por_tema = {q["tema"][:60]: r["leidos"] for q, r in zip(consultas, resultados)}

    def actualizar(e2: dict[str, Any]) -> bool:
        c = next(x for x in e2["corridas"] if x["id"] == ctx.corrida_id)
        c["busqueda"]["cribados"] += total.get("cribados", 0)
        c["busqueda"]["textoCompleto"] += total.get("textoCompleto", 0)
        c["gasto"]["articulosLeidos"] += total.get("leidos", 0)
        for q in consultas:
            tema = q["tema"][:60]
            cob = next((x for x in c["coberturas"] if x["tema"] == tema), None)
            if cob is None:
                cob = {"tema": tema, "leidos": 0, "fraccion": 0.0, "tau": TAU_COBERTURA}
                c["coberturas"].append(cob)
            cob["leidos"] += leidos_por_tema.get(tema, 0)
            cob["fraccion"] = round(1 - math.exp(-cob["leidos"] / cob["tau"]), 3)
        return True

    ctx.mutar(actualizar, "busqueda")
    return f"{len(consultas)} consultas, {total.get('identificados', 0)} identificados, {total.get('cribados', 0)} relevantes, {total.get('textoCompleto', 0)} con texto completo"


# ---------------------------------------------------------------------------
# Ensayos clinicos
# ---------------------------------------------------------------------------


async def paso_ensayos(ctx: Ctx, paso: dict[str, Any]) -> str:
    inv = ctx.inv()
    preguntas = T.preguntas_abiertas(ctx.e["hechos"], ctx.investigacion_id, inv["objetivo"])
    terminos = T.terminos_clave(preguntas + " " + paso.get("detalle", ""), maximo=3)
    pista = ctx.pista(paso["id"], "ensayos", "Ensayos registrados sobre " + (", ".join(terminos) or "el objetivo"), "ClinicalTrials.gov v2")
    try:
        termino = " ".join(terminos)
        pista.accion("GET /api/v2/studies", {"base": "ClinicalTrials.gov v2", "parametros": f"query.cond=Alzheimer Disease&query.term={termino}&pageSize=25&countTotal=true", "resultados": "..."})
        estudios, total = await clinicaltrials.buscar("Alzheimer Disease", termino=termino, maximo=25)
        pista.resultado(f"{total} estudios; se registran {len(estudios)}")
        ahora = P.ahora_ms()
        for s in estudios:
            texto = f"{s['titulo']}. Estado: {s['estado']}. Fases: {', '.join(s['fases'])}. Intervenciones: {', '.join(x for x in s['intervenciones'] if x)}. Desenlaces primarios: {'; '.join(x for x in s['desenlaces'] if x)}. Inicio: {s['inicio']}. Patrocinador: {s['patrocinador']}."
            datos = {"referencia": f"{s['nct']}", "titulo": s["titulo"], "nct": s["nct"], "anio": int(s["inicio"][:4]) if s.get("inicio") and s["inicio"][:4].isdigit() else None, "tipos": ["registro"]}
            _registrar_fuente(ctx, datos, "ensayo", [{"localizador": "resumen", "texto": texto, "encabezado": s["titulo"]}], 6, None, "Registro de ensayo; no aplica retractacion", ahora, f"cond=Alzheimer Disease term={termino}")

        def anotar(e: dict[str, Any]) -> bool:
            c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
            c["busqueda"]["consultas"].append({"base": "ClinicalTrials.gov v2", "consulta": f"cond=Alzheimer Disease term={termino}", "fecha": ahora, "resultados": total, "iteracion": ctx.numero, "tema": "Ensayos registrados"})
            c["busqueda"]["identificados"] += total
            return True

        ctx.mutar(anotar, "consulta")
        pista.cerrar(f"{total} estudios, {len(estudios)} registrados como fuentes")
        return f"{total} ensayos encontrados, {len(estudios)} registrados"
    except FuenteNoDisponible as ex:
        pista.fallar(f"ClinicalTrials.gov no respondio: {str(ex)[:160]}. No es 'sin ensayos': la consulta no llego.")
        _contar_fallo_fuente(ctx, "ClinicalTrials.gov v2", str(ex))
        return "ClinicalTrials.gov no respondio"


# ---------------------------------------------------------------------------
# Extraccion
# ---------------------------------------------------------------------------


async def paso_extraccion(ctx: Ctx, paso: dict[str, Any]) -> str:
    inv = ctx.inv()
    preguntas = T.preguntas_abiertas(ctx.e["hechos"], ctx.investigacion_id, inv["objetivo"])
    pendientes = sorted([f for f in ctx.fuentes().values() if not f.get("extraida") and f.get("retraccion") != "retractado"], key=lambda f: -f.get("relevancia", 0))[:MAX_FUENTES_EXTRAER]
    if not pendientes:
        return "No hay fuentes nuevas de las que extraer"
    pista = ctx.pista(paso["id"], "extraccion", f"Extraer afirmaciones de {len(pendientes)} fuentes", "Sonnet 5")
    pista.accion("Un fragmento a la vez (resumen, pagina o seccion), sin cruzar de fragmento; cada afirmacion con su cita literal")
    sem = asyncio.Semaphore(4)
    total = 0
    hechas = 0

    async def extraer(f: dict[str, Any]) -> None:
        nonlocal total, hechas
        nuevas: list[dict[str, Any]] = []
        frags = f.get("fragmentos", [])
        # Con texto completo, el resumen se salta (las cifras estan en el cuerpo).
        if len(frags) > 1:
            frags = [fr for fr in frags if fr["localizador"] != "resumen"]
        for fr in frags[:MAX_FRAGMENTOS_POR_FUENTE]:
            if pista.detenida():
                return
            texto = fr["texto"][:6000]
            if len(texto.strip()) < 80:
                continue
            sospechoso = K.sospechoso_inyeccion(texto)
            if sospechoso:
                pista.nota(f"{f['referencia']} ({fr['localizador']}): el fragmento contiene texto que parece una instruccion para un modelo; se marca y se enseña, no se bloquea")
            async with sem:
                try:
                    # El fragmento entra delimitado como dato (spotlighting), nunca como instruccion.
                    pred = await ctx.llamar("volumen", ctx.programas.extraer, preguntas_abiertas=preguntas, referencia=f["referencia"], localizador=fr["localizador"], fragmento=K.como_dato(texto))
                except PresupuestoAgotado:
                    raise
                except Exception as ex:  # noqa: BLE001
                    pista.error(f"{f['referencia']} ({fr['localizador']}): el extractor fallo: {str(ex)[:120]}")
                    continue
            for a in pred.afirmaciones:
                # Comprobacion literal en PDF: la pagina de la cita tiene que contener el fragmento.
                if fr.get("_ruta") and fr["localizador"].startswith("pág.") and not pdf.fragmento_en_pagina(__import__("pathlib").Path(fr["_ruta"]), a.fragmento, int(fr["localizador"].split(" ")[1])):
                    pista.nota(f"{f['referencia']}: fragmento no encontrado literalmente en la {fr['localizador']}; la afirmacion se marca cita_no_resuelve")
                    veredicto_inicial = "cita_no_resuelve"
                    motivo = "El fragmento citado no aparece literalmente en la pagina indicada."
                else:
                    veredicto_inicial, motivo = "sin_verificar", "Pendiente de verificacion"
                cohorte = (getattr(a, "cohorte", "") or "").strip()[:60]
                nivel = getattr(a, "nivel_medicion", "resultado_analisis") or "resultado_analisis"
                registro = {k: (getattr(a, k, "") or "").strip()[:80] for k in ("n", "comparador", "efecto", "incertidumbre")}
                # Comprobaciones automaticas del registro de evidencia (plan completo,
                # seccion 3): lo que un dato deberia traer y no trae queda sin resolver.
                sin_resolver = [k for k in ("n", "comparador", "efecto") if a.tipo == "dato" and not registro[k]]
                if a.tipo == "dato" and nivel == "interpretacion_autor":
                    sin_resolver.append("una interpretacion de los autores no es una medida: se rebaja a literatura")
                    tipo_af = "literatura"
                else:
                    tipo_af = a.tipo
                nuevas.append({"id": P.nuevo_id("af"), "texto": a.texto.strip(), "cita": f"[{f['referencia']}, {fr['localizador']}]", "fragmento": a.fragmento.strip(), "veredicto": veredicto_inicial, "motivo": motivo, "entidadDistinta": False, "tipo": tipo_af, "clase": "literatura", "sintetico": False, "cohorte": cohorte, "sospechosoInyeccion": sospechoso, "nivelMedicion": nivel, **registro, "sinResolver": sin_resolver, "tema": a.tema, "fuenteId": f["id"], "localizador": fr["localizador"], "iteracion": ctx.numero, "encabezado": fr.get("encabezado", "")})

        def guardar(e: dict[str, Any]) -> bool:
            c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
            c.setdefault("_afirmaciones", []).extend(nuevas)
            fuente = c["_fuentes"][f["id"]]
            fuente["extraida"] = True
            # La cohorte de la fuente: la que mas dijeron sus afirmaciones, o la que
            # se reconoce en el titulo y el resumen. Sirve para contar cohortes, no
            # articulos, al medir replicacion.
            if not fuente.get("cohorte"):
                dichas = [a["cohorte"] for a in nuevas if a.get("cohorte")]
                fuente["cohorte"] = (max(set(dichas), key=dichas.count) if dichas else K.cohorte_en_texto(fuente.get("titulo", "") + " " + " ".join(fr.get("texto", "")[:600] for fr in fuente.get("fragmentos", [])[:1]))) or None
            c["busqueda"]["usados"] = len({a["fuenteId"] for a in c["_afirmaciones"]})
            return True

        ctx.mutar(guardar, "afirmaciones")
        total += len(nuevas)
        hechas += 1
        pista.resultado(f"Fuente {hechas} de {len(pendientes)}: {f['referencia']}, {len(nuevas)} afirmaciones ({total} acumuladas)")

    try:
        await asyncio.gather(*(extraer(f) for f in pendientes))
        pista.cerrar(f"{len(pendientes)} fuentes, {total} afirmaciones con cita")
    except PresupuestoAgotado:
        pista.cerrar("Presupuesto agotado a mitad de la extraccion", "detenida")
        raise
    return f"{total} afirmaciones extraidas de {hechas} fuentes"


# ---------------------------------------------------------------------------
# Verificacion
# ---------------------------------------------------------------------------


async def verificar_afirmaciones(ctx: Ctx, afirmaciones: list[dict[str, Any]], pista: Pista | None, pregunta: str) -> dict[str, int]:
    """Deterministas primero, juez despues. Cambia el veredicto en sitio (y en
    el almacen). Devuelve el recuento por veredicto."""
    frags = ctx.fragmentos_verificador()
    por_id = {f.fuente_id: f for f in frags}
    recuento: dict[str, int] = {}
    al_juez: list[tuple[dict[str, Any], V.Resultado]] = []
    for a in afirmaciones:
        r = V.comprobar_determinista(a["texto"], a["cita"], a.get("fragmento"), frags, frags)
        if r.necesita_juez:
            al_juez.append((a, r))
        else:
            a["veredicto"], a["motivo"] = r.veredicto, r.motivo
            recuento[r.veredicto] = recuento.get(r.veredicto, 0) + 1
    if pista:
        pista.resultado(f"Deterministas: {sum(recuento.values())} resueltas sin juez ({', '.join(f'{k} {v}' for k, v in recuento.items()) or 'ninguna'}); {len(al_juez)} van al juez")
    sem = asyncio.Semaphore(4)
    juzgadas = 0

    async def juzgar(a: dict[str, Any], r: V.Resultado) -> None:
        nonlocal juzgadas
        frag = r.fragmento
        async with sem:
            try:
                pred = await ctx.llamar("juez", ctx.programas.juzgar, pregunta=pregunta, afirmacion=a["texto"], fragmento=K.como_dato(f"Encabezado: {frag.encabezado if frag else a.get('encabezado', '')}\n\n{(frag.texto if frag else a.get('fragmento', ''))[:6000]}"), pistas=r.pistas)
                v = pred.veredicto
                a["veredicto"] = v.veredicto
                a["motivo"] = v.motivo
                a["entidadDistinta"] = bool(v.entidad_distinta) and v.veredicto == "no_sostenida"
            except PresupuestoAgotado:
                raise
            except Exception as ex:  # noqa: BLE001
                a["veredicto"] = "sin_verificar"
                a["motivo"] = f"El juez no dictamino: {str(ex)[:120]}"
        juzgadas += 1
        recuento[a["veredicto"]] = recuento.get(a["veredicto"], 0) + 1
        if pista and juzgadas % 10 == 0:
            pista.resultado(f"Juez: {juzgadas} de {len(al_juez)}")

    await asyncio.gather(*(juzgar(a, r) for a, r in al_juez))
    ctx.mutar(lambda e: True, "veredictos")
    return recuento


async def paso_verificacion(ctx: Ctx, paso: dict[str, Any]) -> str:
    pendientes = [a for a in ctx.afirmaciones() if a["veredicto"] == "sin_verificar"]
    if not pendientes:
        return "Nada pendiente de verificar"
    pista = ctx.pista(paso["id"], "verificacion", f"Verificar {len(pendientes)} afirmaciones", "Opus 5 (juez)")
    pista.accion("Comprobaciones deterministas: citas que resuelven, fragmento literal, identificadores, cifras normalizadas")
    inv = ctx.inv()
    try:
        recuento = await verificar_afirmaciones(ctx, pendientes, pista, inv["objetivo"])
    except PresupuestoAgotado:
        pista.cerrar("Presupuesto agotado a mitad de la verificacion", "detenida")
        raise
    bloqueadas = sum(v for k, v in recuento.items() if V.bloquea(k))
    resumen = f"{len(pendientes)} afirmaciones: " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in sorted(recuento.items(), key=lambda x: -x[1])) + f"; {bloqueadas} bloqueadas"
    pista.cerrar(resumen)
    fid = V.fidelidad([a["veredicto"] for a in pendientes])
    ahora = P.ahora_ms()

    def metricas(e: dict[str, Any]) -> bool:
        e["metricas"].append(
            {
                "fecha": ahora,
                "juez": "anthropic/claude-opus-5",
                "casos": len(pendientes),
                "acuerdoConHumanos": 0,
                "sostenidas": round(fid, 3) if fid is not None else 0,
                "cobertura": round(1 - recuento.get("cita_no_resuelve", 0) / max(1, len(pendientes)), 3),
                "ausenciasRefutadas": recuento.get("ausencia_refutada", 0),
                "entidadDistinta": sum(1 for a in pendientes if a.get("entidadDistinta")),
                "sinVerificar": recuento.get("sin_verificar", 0),
                "aciertoPorTipo": {"dato": None, "literatura": None, "interpretacion": None},
            }
        )
        return True

    ctx.mutar(metricas, "metricas")
    return resumen


# ---------------------------------------------------------------------------
# Modelo de mundo
# ---------------------------------------------------------------------------


def _fuente_publica(f: dict[str, Any], afirmacion: dict[str, Any] | None = None) -> dict[str, Any]:
    """La Fuente tal como la ve la interfaz, con la pagina y el fragmento de
    la afirmacion concreta si se da."""
    publica = {k: v for k, v in f.items() if not k.startswith("_") and k not in ("fragmentos", "relevancia", "extraida", "iteracion", "consultas")}
    publica.setdefault("cohorte", None)
    if afirmacion:
        loc = afirmacion.get("localizador", "")
        m = re.match(r"p[aá]g\.\s*(\d+)", loc)
        publica["pagina"] = int(m.group(1)) if m else None
        publica["fragmento"] = afirmacion.get("fragmento", "")[:400]
    return publica


async def paso_modelo(ctx: Ctx, paso: dict[str, Any]) -> str:
    inv = ctx.inv()
    e = ctx.e
    nuevas = [a for a in ctx.afirmaciones() if a["iteracion"] == ctx.numero]
    texto, validas = T.afirmaciones_sostenidas(nuevas)
    pista = ctx.pista(paso["id"], "modelo", "Actualizar hechos y preguntas", "GPT-6 Astra")
    if not validas:
        pista.cerrar("Sin afirmaciones sostenidas nuevas: el modelo de mundo no cambia")
        return "Sin afirmaciones sostenidas nuevas"
    pista.accion(f"Leyendo el modelo de mundo y {len(validas)} afirmaciones sostenidas o parciales")
    pred = await ctx.llamar("cerebro", ctx.programas.mundo, objetivo=inv["objetivo"], modelo_de_mundo=T.modelo_de_mundo(e["hechos"], ctx.investigacion_id), afirmaciones_sostenidas=texto)
    ahora = P.ahora_ms()
    fuentes = ctx.fuentes()
    anadidos = 0
    preguntas = 0

    def aplicar(e2: dict[str, Any]) -> bool:
        nonlocal anadidos, preguntas
        existentes = {V.normalizar(h["enunciado"]) for h in e2["hechos"] if h["investigacionId"] == ctx.investigacion_id}
        for hp in pred.hechos:
            if V.normalizar(hp.enunciado) in existentes:
                continue
            respaldo = [validas[i - 1] for i in hp.afirmaciones if 1 <= i <= len(validas)]
            if hp.tipo == "hecho" and not respaldo:
                continue  # un hecho sin afirmacion sostenida no entra
            procedencia = []
            for a in respaldo:
                if a["fuenteId"] not in fuentes:
                    continue
                m = re.match(r"p[aá]g\.\s*(\d+)", a["localizador"])
                entrada = {"fuenteId": a["fuenteId"], "referencia": fuentes[a["fuenteId"]]["referencia"], "pagina": int(m.group(1)) if m else None}
                if entrada not in procedencia:
                    procedencia.append(entrada)
            h = P.nuevo_hecho(ctx.investigacion_id, "hecho" if hp.tipo == "hecho" else "pregunta", hp.tema, hp.enunciado, "sabido" if hp.tipo == "hecho" else "abierto", "fuente" if hp.tipo == "hecho" else "inferencia", procedencia, ahora, hp.prioridad, f"Añadido en la iteracion {ctx.numero}")
            e2["hechos"].append(h)
            existentes.add(V.normalizar(hp.enunciado))
            if hp.tipo == "hecho":
                anadidos += 1
                A.con_evento(e2, ctx.investigacion_id, "hecho_nuevo", f"Hecho nuevo: {hp.enunciado[:120]}", f"#/investigaciones/{ctx.investigacion_id}/mundo", ahora)
            else:
                preguntas += 1
        return True

    ctx.mutar(aplicar, "modelo_de_mundo")
    pista.resultado(f"{anadidos} hechos y {preguntas} preguntas nuevas")
    # Instantanea del modelo de mundo como artefacto.
    contenido = "# Modelo de mundo\n\n" + T.modelo_de_mundo(ctx.e["hechos"], ctx.investigacion_id, maximo=500)
    ctx.mutar(lambda e2: A.guardar_artefacto(e2, ctx.investigacion_id, "Modelo de mundo", "modelo_mundo", contenido, f"Iteracion {ctx.numero}: {anadidos} hechos y {preguntas} preguntas nuevas", ctx.numero, ahora), "artefacto")
    pista.cerrar(f"{anadidos} hechos, {preguntas} preguntas")
    return f"{anadidos} hechos y {preguntas} preguntas nuevas en el modelo de mundo"


# ---------------------------------------------------------------------------
# Hipotesis: generar, revisar, torneo
# ---------------------------------------------------------------------------


def _texto_mision(inv: dict[str, Any]) -> str:
    m = inv.get("mision") or {}
    memoria = inv.get("memoria") or []
    texto_mem = (" Memoria del proyecto (hechos fijados por las personas): " + " | ".join(x["texto"] for x in memoria[:12])) if memoria else ""
    if not m:
        return "Sin mision estructurada todavia." + texto_mem
    return f"Poblacion: {m.get('poblacion') or 'sin fijar'}. Etapa: {m.get('etapa') or 'sin fijar'}. Celula o tejido: {m.get('celulaTejido') or 'sin fijar'}. Mecanismo: {m.get('mecanismo') or 'sin fijar'}. Tipo de intervencion: {m.get('tipoIntervencion') or 'sin fijar'}. Capacidades del laboratorio: {'; '.join(m.get('capacidadesLaboratorio', [])) or 'sin declarar'}." + texto_mem


async def _completar_tarjeta(ctx: Ctx, h: dict[str, Any], pista: Pista | None) -> None:
    """La tarjeta (contrato minimo) de una hipotesis que no la trae: humana o
    anterior a septiembre de 2026. La escribe el modelo de volumen: es
    descriptivo, no juzga."""
    try:
        pred = await ctx.llamar("volumen", ctx.programas.tarjeta, hipotesis=T.hipotesis_texto(h), mision=_texto_mision(ctx.inv()), afirmaciones="\n".join(f"- [{a['veredicto']}] {a['texto']} {a['cita']}" for a in h["afirmaciones"]) or "Ninguna")
        t = pred.tarjeta
        tarjeta = {"diana": t.diana.strip(), "celula": t.celula.strip(), "etapa": t.etapa.strip(), "intervencion": t.intervencion.strip(), "direccion": t.direccion, "prediccionFalsable": t.prediccion_falsable.strip(), "riesgos": [r.strip() for r in t.riesgos if r.strip()][:6], "pasoRuta": getattr(t, "paso_ruta", "mecanismo") or "mecanismo"}
    except PresupuestoAgotado:
        raise
    except Exception as ex:  # noqa: BLE001
        if pista:
            pista.error(f"No se pudo completar la tarjeta de {h['titulo'][:50]}: {str(ex)[:100]}")
        tarjeta = None

    def fn(e: dict[str, Any]) -> bool:
        x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
        if not x:
            return False
        x["_tarjetaIntentada"] = True
        if tarjeta:
            x["tarjeta"] = tarjeta
        return True

    ctx.mutar(fn, "tarjeta")


async def _killer(ctx: Ctx, h: dict[str, Any], texto_afirmaciones: str, pista: Pista | None, profundidad: int = 0) -> str:
    """El Hypothesis Killer sobre la version actual de la hipotesis. Devuelve
    la decision. Si decide reformular, reformula (version nueva) y vuelve a
    juzgar la nueva version, hasta el limite de la politica."""
    e = ctx.e
    inv = ctx.inv()
    h = next((y for y in e["hipotesis"] if y["id"] == h["id"]), h)
    if h.get("tarjeta") is None and not h.get("_tarjetaIntentada"):
        await _completar_tarjeta(ctx, h, pista)
        h = next((y for y in e["hipotesis"] if y["id"] == h["id"]), h)
    try:
        await contexto_de_bases(ctx, h, pista)
    except Exception as ex:  # noqa: BLE001
        if pista:
            pista.nota(f"Las bases no respondieron para la diana: {str(ex)[:100]}")
    h = next((y for y in e["hipotesis"] if y["id"] == h["id"]), h)
    deterministas = K.comprobaciones_deterministas(h, e)
    afs_texto = "\n".join(f"- [{a['veredicto']}, {a['tipo']}, clase {a.get('clase', 'literatura')}{', SINTETICO' if a.get('sintetico') else ''}{', cohorte ' + a['cohorte'] if a.get('cohorte') else ''}] {a['texto']} {a['cita']}" + (f"\n    Pasaje: \"{a['fragmento'][:240]}\"" if a.get("fragmento") else "") for a in h["afirmaciones"]) or "Ninguna"
    try:
        pred = await ctx.llamar(
            "juez",
            ctx.programas.killer,
            objetivo=inv["objetivo"],
            mision=_texto_mision(inv),
            hipotesis=T.hipotesis_texto(h) + "\n" + K.texto_tarjeta(h),
            afirmaciones=afs_texto,
            supuestos="\n".join(f"- [{s['estado']}] {s['texto']} ({s['evidencia']})" for s in h["supuestos"]) or "Sin supuestos evaluados",
            modelo_de_mundo=T.modelo_de_mundo(e["hechos"], ctx.investigacion_id, maximo=40) + "\n\nOtras hipotesis vivas:\n" + T.hipotesis_existentes([x for x in e["hipotesis"] if x["id"] != h["id"]], ctx.investigacion_id),
            comprobaciones_deterministas="\n".join(f"- {c['comprobacion']}: {c['resultado']}. {c['detalle']}" for c in deterministas),
            criterios_revision="\n".join(e["criteriosRevision"]),
        )
        rev = pred.revision
        del_juez = [{"comprobacion": c.comprobacion, "resultado": c.resultado, "detalle": c.detalle} for c in rev.comprobaciones]
        resumen, sugerida, falta, alternativas, invalidante = rev.resumen.strip(), rev.reformulacion_sugerida.strip(), rev.que_haria_falta.strip(), list(rev.alternativas)[:4], rev.supuesto_invalidante.strip()
    except PresupuestoAgotado:
        raise
    except Exception as ex:  # noqa: BLE001
        if pista:
            pista.error(f"El Killer no respondio para {h['titulo'][:50]}: {str(ex)[:100]}; la hipotesis queda suspendida hasta la siguiente revision")
        del_juez, resumen, sugerida, falta, alternativas, invalidante = [], f"El juez no respondio: {str(ex)[:120]}", "", "Repetir la revision cuando el modelo responda", [], ""
    comprobaciones = K.fusionar(deterministas, del_juez)
    # El supuesto invalidante del juez solo tumba si algun supuesto esta contradicho
    # de verdad; si no, es un aviso de lo que haria falta comprobar.
    if invalidante and any(s_.get("estado") == "contradicho" for s_ in h.get("supuestos", [])) and not any(c["comprobacion"] == "supuestos" and c["resultado"] == "falla" for c in comprobaciones):
        comprobaciones = [c for c in comprobaciones if c["comprobacion"] != "supuestos"] + [{"comprobacion": "supuestos", "resultado": "falla", "detalle": f"Supuesto invalidante: {invalidante[:200]}"}]
    elif invalidante and not falta:
        falta = f"Comprobar el supuesto: {invalidante[:200]}"
    tiene_prediccion = bool((h.get("tarjeta") or {}).get("prediccionFalsable")) and "no falsable" not in (h.get("tarjeta") or {}).get("prediccionFalsable", "").lower()
    decision, motivo = K.decidir(comprobaciones, tiene_prediccion, h.get("version", 1))
    if not del_juez and decision == "avanzar":
        decision, motivo = "suspender", "El juez no respondio: no se puede dar por revisada"
    ahora = P.ahora_ms()
    quien = ctx.modelos.juez.model
    fallidas = [c for c in comprobaciones if c["resultado"] in ("falla", "no_comprobable")]
    version_juzgada = h.get("version", 1)

    def aplicar(e2: dict[str, Any]) -> dict[str, Any] | bool:
        x = next((y for y in e2["hipotesis"] if y["id"] == h["id"]), None)
        if not x:
            return False
        if x.get("version", 1) != version_juzgada:
            # Escritura tardia: la hipotesis cambio mientras el juez pensaba. La
            # decision queda registrada sobre la version que juzgo y no toca la actual.
            d = A.registrar_decision(e2, x, "killer_1", decision, f"[Sobre la version {version_juzgada}; la hipotesis ya esta en la {x.get('version', 1)} y se volvera a juzgar] {motivo}", quien, ahora, comprobaciones, falta)
            d["version"] = version_juzgada
            x["_revisionPedida"] = True
            return d
        d = A.registrar_decision(e2, x, "killer_1", decision, motivo, quien, ahora, comprobaciones, falta)
        d["_alternativas"] = alternativas
        x["decisionKiller"] = decision
        # Motor causal minimo: grafo local tipado e identificacion por regla, con
        # las alternativas del Killer como nodos. Entra al modelo de mundo como arista.
        indep = next((c["resultado"] for c in comprobaciones if c["comprobacion"] == "independencia_cohortes"), None)
        x["grafoCausal"] = CAUSAL.grafo_local(x, alternativas, True if indep == "pasa" else False if indep == "falla" else None, ahora)
        CAUSAL.registrar_relacion(e2, x, x["grafoCausal"], ahora)
        for r in x["revisionesAutomaticas"]:
            if r["tipo"] == "completa":
                r.update(estado="hecha" if r["estado"] == "pendiente" else "rehecha", resumen=f"Killer: {decision}. {resumen}", fecha=ahora)
        x["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "revisor", "texto": f"Hypothesis Killer (v{x.get('version', 1)}): {decision.replace('_', ' ')}. {resumen}" + (f" Alternativas a considerar: {'; '.join(alternativas)}" if alternativas else ""), "creadoEn": ahora})
        x["revisiones"].append({"fecha": ahora, "quien": quien, "accion": "killer", "nota": f"{decision.replace('_', ' ')}: {motivo[:240]}", "aCiegas": False})
        if decision == "suspender":
            x["revisiones"].append({"fecha": ahora, "quien": quien, "accion": "suspendida", "nota": falta[:240] or motivo[:240], "aCiegas": False})
        if decision == "descartar_en_contexto":
            if e2["autonomia"].get("descartar_hipotesis") == "actuar":
                A.revisar_hipotesis(e2, x["id"], "descartar", f"Descartada en este contexto por el Killer: {motivo[:300]}", quien, ahora, False, None, etapa="killer_1")
            else:
                x["estado"] = "en_revision"
                x["hallazgos"].append({"id": P.nuevo_id("hal"), "tipo": "conclusion_no_sigue", "resumen": "El Killer propone descartarla en este contexto", "razonamiento": motivo, "estado": "abierto", "respuestaDeRosa": None})
                A.con_evento(e2, ctx.investigacion_id, "killer", f"El Killer propone descartar: {x['titulo'][:80]}. Decide tu.", f"#/investigaciones/{ctx.investigacion_id}/hipotesis/{x['id']}", ahora)
        elif decision == "avanzar":
            A.con_evento(e2, ctx.investigacion_id, "killer", f"El Killer deja avanzar (v{x.get('version', 1)}): {x['titulo'][:80]}", f"#/investigaciones/{ctx.investigacion_id}/hipotesis/{x['id']}", ahora)
        A.recalcular_bloqueos(e2, x)
        return d

    d = ctx.mutar(aplicar, "killer")
    actual = next((y for y in ctx.e["hipotesis"] if y["id"] == h["id"]), h)
    if actual.get("version", 1) != version_juzgada:
        if pista:
            pista.nota(f"La hipotesis cambio a la version {actual.get('version', 1)} mientras se juzgaba la {version_juzgada}: la decision queda registrada sobre la {version_juzgada} y la nueva se juzga aparte")
        return decision
    if pista:
        pista.resultado(f"Killer sobre '{h['titulo'][:50]}' (v{h.get('version', 1)}): {decision.replace('_', ' ')}. " + "; ".join(f"{c['comprobacion']} {c['resultado']}" for c in fallidas)[:200])
    # Auditoria de una muestra de descartes y reformulaciones, con otro metodo (debate) y otra familia (cerebro).
    if decision in ("descartar_en_contexto", "reformular") and isinstance(d, dict):
        c = ctx.corrida()
        indice = c.get("_descartesVistos", 0)
        ctx.mutar(lambda e2: (next(x for x in e2["corridas"] if x["id"] == ctx.corrida_id).__setitem__("_descartesVistos", indice + 1), True)[1], "auditoria_contador")
        if K.muestrear_para_auditoria(indice):
            await _auditar_descarte(ctx, h, d, fallidas, afs_texto, pista)
    if decision == "reformular" and profundidad < politicas.MAX_REFORMULACIONES:
        ok = await _reformular(ctx, h, "Killer: " + motivo + (f". Sugerencia: {sugerida}" if sugerida else ""), quien, pista)
        if ok:
            nueva = next((y for y in ctx.e["hipotesis"] if y["id"] == h["id"]), h)
            return await _killer(ctx, nueva, texto_afirmaciones, pista, profundidad + 1)
    return decision


async def _auditar_descarte(ctx: Ctx, h: dict[str, Any], decision: dict[str, Any], fallidas: list[dict[str, str]], evidencia: str, pista: Pista | None) -> None:
    """Segundo metodo, otra familia: el cerebro defiende la hipotesis y luego
    juzga si la decision del Killer resiste. Un desacuerdo no revierte nada:
    va a la persona con las dos posturas."""
    try:
        pred = await ctx.llamar("cerebro", ctx.programas.auditar_descarte, hipotesis=T.hipotesis_texto(h) + "\n" + K.texto_tarjeta(h), decision=f"{decision['decision']}: {decision['motivo']}", comprobaciones_fallidas="\n".join(f"- {c['comprobacion']}: {c['resultado']}. {c['detalle']}" for c in fallidas) or "ninguna", evidencia=evidencia + "\n\nSupuestos:\n" + "\n".join(f"- [{s['estado']}] {s['texto']}" for s in h["supuestos"]))
        au = pred.auditoria
        auditoria = {"quien": ctx.modelos.cerebro.model, "acuerdo": bool(au.acuerdo), "motivo": (au.motivo.strip() + (f" Mejor argumento a favor: {au.mejor_argumento_a_favor.strip()}" if not au.acuerdo else ""))[:600], "fecha": P.ahora_ms(), "comprobacionDiscutida": au.comprobacion_discutida.strip()[:80]}
    except PresupuestoAgotado:
        raise
    except Exception as ex:  # noqa: BLE001
        auditoria = {"quien": ctx.modelos.cerebro.model, "acuerdo": True, "motivo": f"El auditor no respondio: {str(ex)[:120]}", "fecha": P.ahora_ms(), "comprobacionDiscutida": ""}

    def fn(e: dict[str, Any]) -> bool:
        d = next((x for x in e.get("decisiones", []) if x["id"] == decision["id"]), None)
        if not d:
            return False
        d["auditoria"] = auditoria
        if not auditoria["acuerdo"]:
            x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
            if x:
                x["hallazgos"].append({"id": P.nuevo_id("hal"), "tipo": "conclusion_no_sigue", "resumen": "La auditoria discrepa del Killer", "razonamiento": auditoria["motivo"], "estado": "abierto", "respuestaDeRosa": None})
            A.con_evento(e, h["investigacionId"], "killer", f"Auditoria en desacuerdo con el Killer sobre '{h['titulo'][:60]}': revisa las dos posturas", f"#/investigaciones/{h['investigacionId']}/hipotesis/{h['id']}", P.ahora_ms())
        return True

    ctx.mutar(fn, "auditoria_descarte")
    if pista:
        pista.resultado(f"Auditoria del descarte de '{h['titulo'][:40]}': {'de acuerdo' if auditoria['acuerdo'] else 'EN DESACUERDO'}")


async def _reformular(ctx: Ctx, h: dict[str, Any], motivo: str, quien: str, pista: Pista | None) -> bool:
    """Version nueva de la hipotesis que atiende el motivo. Si la politica ya
    no permite reformular, se descarta en este contexto (o se propone
    descartar, segun la autonomia)."""
    e = ctx.e
    texto_af, _ = T.afirmaciones_sostenidas(ctx.afirmaciones())
    if not politicas.puede_reformular(h.get("version", 1)):
        ahora = P.ahora_ms()

        def agotada(e2: dict[str, Any]) -> bool:
            x = next((y for y in e2["hipotesis"] if y["id"] == h["id"]), None)
            if not x:
                return False
            m = f"Agoto las {politicas.MAX_REFORMULACIONES} reformulaciones de la politica: {motivo[:200]}"
            A.registrar_decision(e2, x, "killer_1", "descartar_en_contexto", m, quien, ahora)
            x["decisionKiller"] = "descartar_en_contexto"
            if e2["autonomia"].get("descartar_hipotesis") == "actuar":
                A.revisar_hipotesis(e2, x["id"], "descartar", m, quien, ahora, False, None, etapa="killer_1")
            else:
                x["estado"] = "en_revision"
                A.con_evento(e2, ctx.investigacion_id, "killer", f"Sin reformulaciones disponibles: el Killer propone descartar {x['titulo'][:70]}", f"#/investigaciones/{ctx.investigacion_id}/hipotesis/{x['id']}", ahora)
            return True

        ctx.mutar(agotada, "reformulacion_agotada")
        return False
    try:
        pred = await ctx.llamar("cerebro", ctx.programas.reformular, hipotesis=T.hipotesis_texto(h) + "\n" + K.texto_tarjeta(h), motivo=motivo, afirmaciones=texto_af[:8000] or "Ninguna", modelo_de_mundo=T.modelo_de_mundo(e["hechos"], ctx.investigacion_id, maximo=30))
        r = pred.reformulacion
        t = r.tarjeta
        cambios = {"titulo": r.titulo, "enunciado": r.enunciado, "mecanismo": r.mecanismo, "comprobacion": {"biomarcador": r.biomarcador, "cohorte": r.cohorte, "diseno": r.diseno}, "tarjeta": {"diana": t.diana, "celula": t.celula, "etapa": t.etapa, "intervencion": t.intervencion, "direccion": t.direccion, "prediccionFalsable": t.prediccion_falsable, "riesgos": [x.strip() for x in t.riesgos if x.strip()][:6], "pasoRuta": getattr(t, "paso_ruta", "mecanismo") or "mecanismo"}}
        ok = ctx.mutar(lambda e2: A.reformular_hipotesis(e2, h["id"], cambios, quien, f"{motivo[:200]} | {r.que_cambio.strip()[:200]}", P.ahora_ms()), "reformular")
        if pista:
            pista.resultado(f"Reformulada como version {h.get('version', 1) + 1}: {r.titulo[:70]}" if ok else "No se pudo reformular")
        return bool(ok)
    except PresupuestoAgotado:
        raise
    except Exception as ex:  # noqa: BLE001
        if pista:
            pista.error(f"La reformulacion fallo: {str(ex)[:120]}")
        return False


async def _revisar_hipotesis(ctx: Ctx, h: dict[str, Any], texto_afirmaciones: str, pista: Pista | None) -> None:
    """Revision inicial (juez), supuestos (volumen), y el Killer con su
    decision derivada por regla."""
    inv = ctx.inv()
    ahora = P.ahora_ms()
    try:
        pred = await ctx.llamar("juez", ctx.programas.revisar_inicial, objetivo=inv["objetivo"], hipotesis=T.hipotesis_texto(h), criterios_revision="\n".join(ctx.e["criteriosRevision"]))
        rev = pred.revision
    except PresupuestoAgotado:
        raise
    except Exception as ex:  # noqa: BLE001
        if pista:
            pista.error(f"Revision inicial fallo para {h['titulo'][:60]}: {str(ex)[:100]}")
        return
    supuestos_texto = list(rev.supuestos)[:8] or [s["texto"] for s in h["supuestos"]]
    evaluados: list[dict[str, Any]] = []
    sem = asyncio.Semaphore(4)

    async def evaluar(s: str) -> None:
        async with sem:
            try:
                p2 = await ctx.llamar("volumen", ctx.programas.evaluar_supuesto, supuesto=s, afirmaciones_sostenidas=texto_afirmaciones)
                evaluados.append({"id": P.nuevo_id("sup"), "texto": s, "estado": p2.evaluacion.estado, "evidencia": p2.evaluacion.evidencia, "hijos": []})
            except PresupuestoAgotado:
                raise
            except Exception:  # noqa: BLE001
                evaluados.append({"id": P.nuevo_id("sup"), "texto": s, "estado": "sin_evidencia", "evidencia": "No se pudo evaluar", "hijos": []})

    await asyncio.gather(*(evaluar(s) for s in supuestos_texto))
    contradichos = [s for s in evaluados if s["estado"] == "contradicho"]

    def aplicar(e: dict[str, Any]) -> bool:
        x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
        if not x:
            return False
        x["supuestos"] = evaluados
        for r in x["revisionesAutomaticas"]:
            if r["tipo"] == "inicial":
                r.update(estado="hecha" if r["estado"] == "pendiente" else "rehecha", resumen=("Pasa: " if rev.pasa else "NO pasa: ") + rev.resumen, fecha=ahora)
            elif r["tipo"] == "profunda":
                r.update(estado="hecha" if r["estado"] == "pendiente" else "rehecha", resumen=f"{len(evaluados)} supuestos: " + ", ".join(f"{s['estado']} {sum(1 for t in evaluados if t['estado'] == s['estado'])}" for s in {v['estado']: v for v in evaluados}.values()), fecha=ahora)
            elif r["tipo"] == "completa":
                r.update(estado="hecha" if r["estado"] == "pendiente" else "rehecha", resumen=f"{sum(1 for a in x['afirmaciones'] if a['veredicto'] == 'sostenida')} de {len(x['afirmaciones'])} afirmaciones sostenidas; {len(contradichos)} supuestos contradichos", fecha=ahora)
        x["ultimaRevisionAutomatica"] = ahora
        if not rev.pasa:
            x["hallazgos"].append({"id": P.nuevo_id("hal"), "tipo": "conclusion_no_sigue", "resumen": "La revision inicial no la da por buena", "razonamiento": rev.resumen, "estado": "abierto", "respuestaDeRosa": None})
        for s in contradichos:
            x["hallazgos"].append({"id": P.nuevo_id("hal"), "tipo": "valor_contradice_fuente", "resumen": f"Supuesto contradicho: {s['texto'][:100]}", "razonamiento": s["evidencia"], "estado": "abierto", "respuestaDeRosa": None})
        x["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "revisor", "texto": f"Revision inicial: {rev.resumen}", "creadoEn": ahora})
        return True

    ctx.mutar(aplicar, "revision_hipotesis")
    actual = next((y for y in ctx.e["hipotesis"] if y["id"] == h["id"]), None)
    if actual and actual["estado"] not in ("descartada", "aceptada"):
        await _killer(ctx, actual, texto_afirmaciones, pista)


async def _torneo(ctx: Ctx, pista: Pista) -> int:
    inv = ctx.inv()
    propias = [h for h in ctx.e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id]
    pares = torneo.emparejar(propias, maximo=6, semilla=ctx.numero)
    if not pares:
        pista.nota("Menos de dos hipotesis vivas: no hay torneo")
        return 0
    texto_af, _ = T.afirmaciones_sostenidas(ctx.afirmaciones())
    evidencia = (texto_af[:6000] + "\n\nModelo de mundo:\n" + T.modelo_de_mundo(ctx.e["hechos"], ctx.investigacion_id, maximo=30))
    jugados = 0
    cambios: list[str] = []
    for a, b in pares:
        try:
            p1 = await ctx.llamar("juez", ctx.programas.comparar, objetivo=inv["objetivo"], hipotesis_a=T.hipotesis_para_torneo(a), hipotesis_b=T.hipotesis_para_torneo(b), evidencia=evidencia, revisiones_humanas=f"Sobre A: {T.revisiones_humanas(a)}\nSobre B: {T.revisiones_humanas(b)}")
            p2 = await ctx.llamar("juez", ctx.programas.comparar, objetivo=inv["objetivo"], hipotesis_a=T.hipotesis_para_torneo(b), hipotesis_b=T.hipotesis_para_torneo(a), evidencia=evidencia, revisiones_humanas=f"Sobre A: {T.revisiones_humanas(b)}\nSobre B: {T.revisiones_humanas(a)}")
        except PresupuestoAgotado:
            raise
        except Exception as ex:  # noqa: BLE001
            pista.error(f"Partido {a['titulo'][:40]} vs {b['titulo'][:40]}: el juez fallo ({str(ex)[:80]})")
            continue
        gano_a_1 = p1.comparacion.mejor == "A"
        gano_a_2 = p2.comparacion.mejor == "B"  # en la segunda llamada A y B van invertidas
        gano_a: bool | None = gano_a_1 if gano_a_1 == gano_a_2 else None

        def aplicar(e: dict[str, Any]) -> bool:
            x = next(y for y in e["hipotesis"] if y["id"] == a["id"])
            y_ = next(y for y in e["hipotesis"] if y["id"] == b["id"])
            torneo.registrar_partido(x, y_, gano_a, ctx.numero, p1.comparacion.resumen, p1.comparacion.eje)
            for r in x["revisionesAutomaticas"] + y_["revisionesAutomaticas"]:
                if r["tipo"] == "torneo":
                    r["fecha"] = P.ahora_ms()
            return True

        ctx.mutar(aplicar, "partido")
        jugados += 1
        resultado = "tablas" if gano_a is None else ("gana A" if gano_a else "gana B")
        pista.resultado(f"{a['titulo'][:50]} vs {b['titulo'][:50]}: {resultado} por {p1.comparacion.eje}")
        cambios.append(f"{a['titulo'][:40]} vs {b['titulo'][:40]}: {resultado}")
    if jugados:
        ctx.evento("ranking_cambio", f"Torneo de la iteracion {ctx.numero}: {jugados} partidos", f"#/investigaciones/{ctx.investigacion_id}/ranking")
    return jugados


async def paso_hipotesis(ctx: Ctx, paso: dict[str, Any]) -> str:
    inv = ctx.inv()
    e = ctx.e
    texto_af, validas = T.afirmaciones_sostenidas(ctx.afirmaciones())
    pista = ctx.pista(paso["id"], "modelo", "Generar y revisar hipotesis", "GPT-6 Astra + Opus 5")
    nuevas_ids: list[str] = []
    vivas = sum(1 for x in e["hipotesis"] if x["investigacionId"] == ctx.investigacion_id and x["estado"] not in ("descartada",))
    if vivas >= politicas.MAX_HIPOTESIS_VIVAS_POR_MISION:
        pista.nota(f"Hay {vivas} hipotesis vivas: la politica fija {politicas.MAX_HIPOTESIS_VIVAS_POR_MISION} por mision, asi que no se generan nuevas hasta que se decidan algunas")
        validas = []
    if validas:
        pista.accion(f"Generando hipotesis a partir de {len(validas)} afirmaciones sostenidas y las preguntas abiertas")
        try:
            pred = await ctx.llamar("cerebro", ctx.programas.hipotesis, objetivo=inv["objetivo"], configuracion=T.configuracion(inv), modelo_de_mundo=T.modelo_de_mundo(e["hechos"], ctx.investigacion_id), afirmaciones_sostenidas=texto_af[:12000], hipotesis_existentes=T.hipotesis_existentes(e["hipotesis"], ctx.investigacion_id), criterios_revision="\n".join(e["criteriosRevision"]))
            propuestas = list(pred.hipotesis)[:3]
        except PresupuestoAgotado:
            pista.cerrar("Presupuesto agotado antes de generar", "detenida")
            raise
        ahora = P.ahora_ms()
        fuentes = ctx.fuentes()
        existentes_titulos = {V.normalizar(h["titulo"]) for h in e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id}
        for hp in propuestas:
            if V.normalizar(hp.titulo) in existentes_titulos:
                continue
            respaldo = [validas[i - 1] for i in hp.afirmaciones if 1 <= i <= len(validas)]
            if not respaldo:
                pista.nota(f"Descartada antes de entrar: '{hp.titulo[:60]}' no cita ninguna afirmacion sostenida")
                continue
            afirmaciones = [{"afirmacionId": a.get("id"), "texto": a["texto"], "cita": a["cita"], "veredicto": a["veredicto"], "motivo": a["motivo"], "entidadDistinta": a.get("entidadDistinta", False), "tipo": a["tipo"], "clase": a.get("clase", "literatura"), "sintetico": False, "cohorte": a.get("cohorte", ""), "sospechosoInyeccion": bool(a.get("sospechosoInyeccion")), "nivelMedicion": a.get("nivelMedicion", "resultado_analisis"), "n": a.get("n", ""), "comparador": a.get("comparador", ""), "efecto": a.get("efecto", ""), "incertidumbre": a.get("incertidumbre", ""), "sinResolver": list(a.get("sinResolver", [])), "trayectoria": None, "fragmento": (a.get("fragmento") or "")[:600]} for a in respaldo]
            vistas: set[str] = set()
            fuentes_h = []
            for a in respaldo:
                if a["fuenteId"] in fuentes and a["fuenteId"] + a["localizador"] not in vistas:
                    vistas.add(a["fuenteId"] + a["localizador"])
                    fuentes_h.append(_fuente_publica(fuentes[a["fuenteId"]], a))
            derivada = hp.derivada_de if hp.derivada_de and any(h["id"] == hp.derivada_de for h in e["hipotesis"]) else None
            h = P.nueva_hipotesis(
                ctx.investigacion_id,
                ctx.numero,
                ahora,
                titulo=hp.titulo.strip(),
                enunciado=hp.enunciado.strip(),
                mecanismo=hp.mecanismo.strip(),
                comprobacion={"biomarcador": hp.biomarcador, "cohorte": hp.cohorte, "diseno": hp.diseno},
                cluster=hp.cluster or "Sin cluster",
                relevancia={"justificacion": hp.justificacion, "votoHumano": None},
                afirmaciones=afirmaciones,
                supuestos=[{"id": P.nuevo_id("sup"), "texto": s, "estado": "sin_evidencia", "evidencia": "Pendiente", "hijos": []} for s in hp.supuestos[:8]],
                derivadaDe=derivada,
                evidenciaEstadistica="moderada" if any(a["tipo"] == "dato" for a in afirmaciones) else "no_aplica",
                coste={"literatura": round(len(respaldo) * 0.15, 2), "analisis": 0},
                tarjeta={"diana": (hp.diana or "").strip(), "celula": (hp.celula or "").strip(), "etapa": (hp.etapa or "").strip(), "intervencion": (hp.intervencion or "").strip(), "direccion": hp.direccion or "sin_intervencion", "prediccionFalsable": (hp.prediccion_falsable or "").strip(), "riesgos": [r.strip() for r in (hp.riesgos or []) if r.strip()][:6], "pasoRuta": getattr(hp, "paso_ruta", "mecanismo") or "mecanismo"},
            )
            h["procedencia"] = P.procedencia_vacia(f"Generada en la iteracion {ctx.numero} a partir de {len(respaldo)} afirmaciones sostenidas. Supuestos y novedad se comprueban a continuacion.", ahora, codigo=f"programas.hipotesis(objetivo, modelo_de_mundo, afirmaciones_sostenidas[{len(validas)}])", registro=[f"iteracion {ctx.numero}: generar -> {hp.titulo[:60]}"])
            h["procedencia"]["fuentes"] = fuentes_h
            h["_entidades"] = list(hp.entidades_novedad)[:6]
            ctx.mutar(lambda e2, h=h: (e2["hipotesis"].append(h), A.con_evento(e2, ctx.investigacion_id, "hipotesis_nueva", f"Hipotesis nueva en la cola: {h['titulo']}", f"#/investigaciones/{ctx.investigacion_id}/hipotesis/{h['id']}", ahora)) and True, "hipotesis_nueva")
            nuevas_ids.append(h["id"])
            existentes_titulos.add(V.normalizar(h["titulo"]))
            pista.resultado(f"Nueva: {h['titulo'][:90]}")
    else:
        pista.nota("Sin afirmaciones sostenidas: no se generan hipotesis nuevas en esta iteracion")

    # Revision de las nuevas y de las humanas sin revisar.
    a_revisar = [h for h in ctx.e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id and (h["id"] in nuevas_ids or (h["origen"] == "humana" and h["ultimaRevisionAutomatica"] is None) or h.get("_revisionPedida"))]
    for h in a_revisar:
        await _revisar_hipotesis(ctx, h, texto_af[:8000], pista)
        ctx.mutar(lambda e2, h=h: (next(x for x in e2["hipotesis"] if x["id"] == h["id"]).pop("_revisionPedida", None), True)[1], "revision")
        pista.resultado(f"Revisada: {h['titulo'][:70]}")
    partidos = await _torneo(ctx, pista)
    pista.cerrar(f"{len(nuevas_ids)} hipotesis nuevas, {len(a_revisar)} revisadas, {partidos} partidos")
    return f"{len(nuevas_ids)} hipotesis nuevas en la cola, {len(a_revisar)} revisadas, {partidos} partidos de torneo"


# ---------------------------------------------------------------------------
# Novedad
# ---------------------------------------------------------------------------


async def _novedad_por_conectores(ctx: Ctx, h: dict[str, Any], genes: list[str], novedad: dict[str, Any], pista: Pista) -> list[dict[str, Any]]:
    """Las tres comprobaciones de novedad que anaden los conectores: si la
    genetica humana ya vincula el gen con el Alzheimer (GWAS Catalog, ClinVar),
    si ya hay farmacos contra la diana (ChEMBL, DGIdb) y si existe un dataset
    publico para comprobar la hipotesis (GEO, CELLxGENE). Cada llamada deja su
    registro de consulta con la invariante comprobada. Una fuente que no
    responde queda como "no comprobado", nunca como "no hay"."""
    regs: list[dict[str, Any]] = []
    novedad.setdefault("genetica", {"estado": "no_comprobado", "detalle": "No comprobado todavia"})
    novedad.setdefault("farmacos", {"estado": "no_comprobado", "detalle": "No comprobado todavia"})
    novedad.setdefault("datosPublicos", {"estado": "no_comprobado", "detalle": "No comprobado todavia", "series": []})
    gen = genes[0] if genes else None
    if gen:
        reg_g, gwas = await CON.consultar("gwas_asociaciones_gen", resumen=f"GWAS Catalog: {gen}", simbolo=gen)
        reg_c, clin = await CON.consultar("clinvar_gen", resumen=f"ClinVar: {gen}", simbolo=gen)
        regs += [reg_g, reg_c]
        pista.accion(f"GWAS Catalog y ClinVar: {gen}", {"base": "GWAS Catalog v2, ClinVar", "parametros": f"gene_name={gen}", "resultados": f"{(gwas or {}).get('n_alzheimer', '?')} asociaciones AD; {(clin or {}).get('con_enfermedad', '?')} variantes ClinVar con Alzheimer"})
        if gwas is None and clin is None:
            novedad["genetica"] = {"estado": "no_comprobado", "detalle": "No comprobado: GWAS Catalog y ClinVar no respondieron"}
        else:
            n_ad = (gwas or {}).get("n_alzheimer", 0)
            n_cv = (clin or {}).get("con_enfermedad", 0)
            if n_ad or n_cv:
                mejor = min(((a.get("p") or 1.0) for a in (gwas or {}).get("alzheimer", [])), default=None)
                novedad["genetica"] = {"estado": "vinculo_conocido", "detalle": f"{gen}: {n_ad} asociaciones GWAS con Alzheimer" + (f" (mejor p {mejor:.1e})" if mejor else "") + f"; {n_cv} variantes en ClinVar con Alzheimer. La genetica humana ya vincula el gen: la novedad tiene que estar en el mecanismo o el contexto, no en el vinculo"}
            else:
                novedad["genetica"] = {"estado": "sin_vinculo", "detalle": f"{gen}: sin asociaciones GWAS con Alzheimer entre {(gwas or {}).get('total_asociaciones', 0)} registradas y sin variantes ClinVar con la enfermedad. Si la hipotesis afirma un vinculo genetico, es nuevo y hay que decir por que la genetica no lo vio"}
        reg_m, ids = await CON.consultar("mygene_gen", resumen=f"MyGene: {gen}", simbolo=gen)
        regs.append(reg_m)
        chembl = None
        if ids and ids.get("uniprot"):
            reg_ch, chembl = await CON.consultar("chembl_diana", resumen=f"ChEMBL: {ids['uniprot']}", uniprot=ids["uniprot"])
            regs.append(reg_ch)
        reg_d, dg = await CON.consultar("dgidb_gen", resumen=f"DGIdb: {gen}", simbolo=gen)
        regs.append(reg_d)
        pista.accion(f"ChEMBL y DGIdb: {gen}", {"base": "ChEMBL, DGIdb", "parametros": f"uniprot={(ids or {}).get('uniprot')}", "resultados": f"{len((chembl or {}).get('mecanismos', []))} mecanismos; {(dg or {}).get('total', '?')} interacciones"})
        if chembl is None and dg is None:
            novedad["farmacos"] = {"estado": "no_comprobado", "detalle": "No comprobado: ChEMBL y DGIdb no respondieron"}
        else:
            mecs = (chembl or {}).get("mecanismos", [])
            aprob = [x for x in (dg or {}).get("interacciones", []) if x.get("aprobado")]
            fases = [m.get("fase_maxima") for m in mecs if m.get("fase_maxima") is not None]
            if mecs or aprob:
                novedad["farmacos"] = {"estado": "farmacos_existentes", "detalle": f"{gen}: {len(mecs)} mecanismos de accion en ChEMBL" + (f" (fase maxima {max(fases)})" if fases else "") + f"; {len(aprob)} farmacos aprobados con interaccion en DGIdb" + (": " + ", ".join(str(x.get('farmaco')) for x in aprob[:4]) if aprob else "") + ". La diana es abordable; una hipotesis de intervencion puede reposicionar"}
            else:
                novedad["farmacos"] = {"estado": "sin_farmacos", "detalle": f"{gen}: sin mecanismos en ChEMBL ni farmacos con interaccion en DGIdb. Si la hipotesis propone intervenir, no hay herramienta farmacologica lista"}
    bio = ((h.get("comprobacion") or {}).get("biomarcador") or (h.get("tarjeta") or {}).get("diana") or gen or "").strip()
    if bio:
        reg_geo, geo = await CON.consultar("geo_series", resumen=f"GEO: Alzheimer {bio}", terminos=f"Alzheimer {bio}")
        reg_cx, cx = await CON.consultar("cellxgene_colecciones", resumen="CELLxGENE: Alzheimer", termino="Alzheimer")
        regs += [reg_geo, reg_cx]
        pista.accion(f"GEO y CELLxGENE: {bio}", {"base": "GEO gds, CELLxGENE Discover", "parametros": f"Alzheimer {bio}", "resultados": f"{(geo or {}).get('total', '?')} series GEO; {reg_cx.get('n') if cx is not None else '?'} colecciones"})
        if geo is None and cx is None:
            novedad["datosPublicos"] = {"estado": "no_comprobado", "detalle": "No comprobado: GEO y CELLxGENE no respondieron", "series": []}
        else:
            series = [{"accession": s_["accession"], "titulo": s_["titulo"], "n": s_.get("n_muestras"), "plataforma": s_.get("plataforma")} for s_ in (geo or {}).get("series", [])[:5]]
            n_geo = (geo or {}).get("total", 0)
            n_cx = reg_cx.get("n") or 0
            if n_geo or n_cx:
                novedad["datosPublicos"] = {"estado": "hay_datos", "detalle": f"{n_geo} series GEO humanas con 'Alzheimer {bio}' y {n_cx} colecciones de celula unica con Alzheimer en CELLxGENE: la hipotesis se puede empezar a comprobar in silico sin pedir datos", "series": series}
            else:
                novedad["datosPublicos"] = {"estado": "sin_datos", "detalle": f"Ninguna serie GEO humana con 'Alzheimer {bio}' ni coleccion CELLxGENE: comprobarla exige datos propios o del laboratorio", "series": []}
    return regs


async def contexto_de_bases(ctx: Ctx, h: dict[str, Any], pista: Pista | None) -> None:
    """El contexto de la diana desde las bases: identificadores (MyGene),
    funcion (UniProt), expresion en cerebro (Human Protein Atlas), interactores
    (STRING) y rutas (Reactome). Se calcula una vez por hipotesis y version, y
    se ensena en la tarjeta. El Killer usa los identificadores en la
    comprobacion `identificadores_resuelven`."""
    diana = ((h.get("tarjeta") or {}).get("diana") or "").strip()
    if not diana or (h.get("contextoBases") or {}).get("version") == h.get("version", 1):
        return
    simbolo = diana.split()[0].strip(",;()") if diana else ""
    regs: list[dict[str, Any]] = []
    ctxb: dict[str, Any] = {"diana": diana, "identificadores": {}, "funcion": "", "expresionCerebro": "", "interactores": [], "rutas": [], "version": h.get("version", 1), "consultadoEn": P.ahora_ms()}
    if CON.bases.parece_simbolo(simbolo):
        reg, ids = await CON.consultar("mygene_gen", resumen=f"MyGene: {simbolo}", simbolo=simbolo)
        regs.append(reg)
        if ids:
            ctxb["identificadores"] = {k: ids.get(k) for k in ("simbolo", "nombre", "ensembl", "uniprot", "entrez")}
            if ids.get("uniprot"):
                reg_u, uni = await CON.consultar("uniprot_proteina", resumen=f"UniProt: {simbolo}", simbolo=simbolo)
                reg_r, rutas = await CON.consultar("reactome_rutas", resumen=f"Reactome: {ids['uniprot']}", uniprot=ids["uniprot"])
                regs += [reg_u, reg_r]
                ctxb["funcion"] = (uni or {}).get("funcion", "")[:500]
                ctxb["rutas"] = [{"id": r_["id"], "nombre": r_["nombre"]} for r_ in (rutas or [])[:8]]
            if ids.get("ensembl"):
                reg_h, hpa = await CON.consultar("hpa_expresion", resumen=f"HPA: {ids['ensembl']}", ensembl=ids["ensembl"])
                regs.append(reg_h)
                if hpa:
                    partes = []
                    for k in ("RNA tissue specificity", "RNA brain regional specificity", "RNA single cell type specificity"):
                        if hpa.get(k):
                            partes.append(f"{k.replace('RNA ', '').lower()}: {hpa[k]}")
                    ntpm = hpa.get("RNA brain regional specific nTPM") or hpa.get("RNA single cell type specific nTPM")
                    if isinstance(ntpm, dict) and ntpm:
                        top = sorted(ntpm.items(), key=lambda kv: -float(kv[1] or 0))[:4]
                        partes.append("mayor nTPM en " + ", ".join(f"{k} ({v})" for k, v in top))
                    ctxb["expresionCerebro"] = "; ".join(partes)[:400]
            reg_s, inter = await CON.consultar("string_interactores", resumen=f"STRING: {simbolo}", simbolo=simbolo)
            regs.append(reg_s)
            ctxb["interactores"] = [{"simbolo": i_["interactor"], "puntuacion": i_["puntuacion"]} for i_ in (inter or [])[:8]]
        if pista:
            pista.accion(f"Bases para {simbolo}", {"base": "MyGene, UniProt, HPA, STRING, Reactome", "parametros": simbolo, "resultados": f"Ensembl {ctxb['identificadores'].get('ensembl') or 'no resuelve'}; {len(ctxb['interactores'])} interactores; {len(ctxb['rutas'])} rutas"})

    def aplicar(e: dict[str, Any]) -> bool:
        x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
        if not x:
            return False
        x["contextoBases"] = ctxb
        x.setdefault("consultas", []).extend(regs)
        return True

    ctx.mutar(aplicar, "contexto_bases")
    h["contextoBases"] = ctxb
    h.setdefault("consultas", []).extend(regs)


async def paso_novedad(ctx: Ctx, paso: dict[str, Any]) -> str:
    pendientes = [h for h in ctx.e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id and h["estado"] not in ("descartada",) and h["novedad"]["precedente"]["detalle"].startswith("No comprobado")]
    if not pendientes:
        return "Todas las hipotesis tienen la novedad comprobada"
    pista = ctx.pista(paso["id"], "novedad", f"Novedad de {len(pendientes)} hipotesis", "Open Targets, ClinicalTrials.gov, OpenAlex")
    for h in pendientes[:6]:
        if pista.detenida():
            break
        entidades = h.get("_entidades") or T.terminos_clave(h["titulo"], maximo=4)
        novedad = {k: dict(v) for k, v in h["novedad"].items()}
        # Open Targets: genes o proteinas.
        genes = [x for x in entidades if re.fullmatch(r"[A-Z][A-Z0-9\-]{1,9}", x)]
        detalles = []
        for g in genes[:3]:
            try:
                r = await opentargets.asociacion_alzheimer(g)
                pista.accion(f"Open Targets: {g}", {"base": "Open Targets GraphQL", "parametros": f"search({g}) + target.associatedDiseases(MONDO_0004975)", "resultados": f"{r.get('puntuacion')}"})
                if not r["encontrado"]:
                    detalles.append(f"{g}: no es una diana en Open Targets")
                elif r["puntuacion"] is None:
                    detalles.append(f"{g}: diana sin asociacion registrada con Alzheimer")
                else:
                    detalles.append(f"{g}: asociacion {r['puntuacion']} (" + ", ".join(f"{k} {v}" for k, v in r["tipos"].items()) + ")")
            except FuenteNoDisponible as ex:
                detalles.append(f"{g}: Open Targets no respondio ({str(ex)[:60]}); no se afirma ausencia")
        if genes:
            con_asociacion = any("asociacion 0." in d and float(d.split("asociacion ")[1].split(" ")[0]) >= 0.3 for d in detalles)
            novedad["openTargets"] = {"estado": "evidencia_previa" if con_asociacion else "sin_evidencia", "detalle": "; ".join(detalles)}
        else:
            novedad["openTargets"] = {"estado": "sin_evidencia", "detalle": "No aplica: la hipotesis no nombra una diana molecular"}
        # ClinicalTrials.gov.
        try:
            termino = " ".join(T.terminos_clave(h["titulo"] + " " + h["comprobacion"]["biomarcador"], maximo=3))
            estudios, total = await clinicaltrials.buscar("Alzheimer Disease", termino=termino, maximo=5)
            pista.accion(f"ClinicalTrials.gov: {termino}", {"base": "ClinicalTrials.gov v2", "parametros": f"query.cond=Alzheimer Disease&query.term={termino}", "resultados": f"{total}"})
            if total > 0:
                novedad["ensayos"] = {"estado": "ensayo_existente", "detalle": f"{total} ensayos con esos terminos; el mas cercano: {estudios[0]['nct']} ({estudios[0]['titulo'][:80]}). Hay que leer si mide lo mismo.", "nct": estudios[0]["nct"]}
            else:
                novedad["ensayos"] = {"estado": "sin_ensayo", "detalle": f"Ningun ensayo registrado con: {termino}", "nct": None}
        except FuenteNoDisponible as ex:
            novedad["ensayos"] = {"estado": "sin_ensayo", "detalle": f"No comprobado: ClinicalTrials.gov no respondio ({str(ex)[:60]})", "nct": None}
        # Precedente en literatura (OpenAlex) con cribado del modelo.
        try:
            termino = " ".join(T.terminos_clave(h["titulo"], maximo=4))
            obras, total, coste = await openalex.buscar(termino, maximo=6)
            pista.accion(f"OpenAlex: {termino}", {"base": "OpenAlex", "parametros": f"filter=title_and_abstract.search:{termino}", "resultados": f"{total} obras, {coste} USD"})
            mejor = 0
            mejor_ref = ""
            for o in obras[:5]:
                if not o["titulo"]:
                    continue
                try:
                    p = await ctx.llamar("volumen", ctx.programas.relevancia, preguntas_abiertas=f"Alguien ya propuso o demostro esto: {h['enunciado']}", titulo=o["titulo"], resumen=o["resumen"][:2500])
                    if int(p.puntuacion) > mejor:
                        mejor, mejor_ref = int(p.puntuacion), f"{o['referencia']} ({o['doi'] or 'sin DOI'})"
                except PresupuestoAgotado:
                    raise
                except Exception:  # noqa: BLE001
                    continue
            if mejor >= 8:
                novedad["precedente"] = {"estado": "ya_publicado", "detalle": f"Ya publicado o muy cercano: {mejor_ref} (puntuacion {mejor}/10)"}
            elif mejor >= 5:
                novedad["precedente"] = {"estado": "parcial", "detalle": f"Precedente parcial: {mejor_ref} (puntuacion {mejor}/10)"}
            else:
                novedad["precedente"] = {"estado": "sin_precedente", "detalle": f"Sin precedente claro entre {total} obras que casan con: {termino}"}
        except FuenteNoDisponible as ex:
            novedad["precedente"] = {"estado": "sin_precedente", "detalle": f"No comprobado: OpenAlex no respondio ({str(ex)[:60]})"}

        # Conectores: genetica humana, farmacos y datos publicos para la misma diana.
        consultas = await _novedad_por_conectores(ctx, h, genes[:1], novedad, pista)

        def aplicar(e: dict[str, Any], h=h, novedad=novedad, consultas=consultas) -> bool:
            x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
            if not x:
                return False
            x["novedad"] = novedad
            x.setdefault("consultas", []).extend(consultas)
            x["procedencia"]["registro"].append(f"iteracion {ctx.numero}: novedad -> Open Targets {novedad['openTargets']['estado']}, ensayos {novedad['ensayos']['estado']}, precedente {novedad['precedente']['estado']}, genetica {novedad.get('genetica', {}).get('estado')}, farmacos {novedad.get('farmacos', {}).get('estado')}, datos publicos {novedad.get('datosPublicos', {}).get('estado')}")
            return True

        ctx.mutar(aplicar, "novedad")
        pista.resultado(f"{h['titulo'][:60]}: precedente {novedad['precedente']['estado']}, ensayos {novedad['ensayos']['estado']}, Open Targets {novedad['openTargets']['estado']}")
    pista.cerrar(f"Novedad comprobada en {min(len(pendientes), 6)} hipotesis")
    return f"Novedad comprobada en {min(len(pendientes), 6)} hipotesis"


# ---------------------------------------------------------------------------
# Meta-revision y panorama
# ---------------------------------------------------------------------------


async def paso_meta(ctx: Ctx, paso: dict[str, Any]) -> str:
    inv = ctx.inv()
    e = ctx.e
    propias = [h for h in e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id]
    pista = ctx.pista(paso["id"], "modelo", "Meta-revision y panorama", "GPT-6 Astra")
    if not propias:
        pista.cerrar("Sin hipotesis: no hay meta-revision")
        return "Sin hipotesis que meta-revisar"
    pred = await ctx.llamar("cerebro", ctx.programas.meta, objetivo=inv["objetivo"], hipotesis=T.todas_las_hipotesis(e["hipotesis"], ctx.investigacion_id)[:20000], modelo_de_mundo=T.modelo_de_mundo(e["hechos"], ctx.investigacion_id))
    ahora = P.ahora_ms()
    ids = {h["id"] for h in propias}

    def aplicar(e2: dict[str, Any]) -> bool:
        c = next(x for x in e2["corridas"] if x["id"] == ctx.corrida_id)
        debilidades = [{"id": P.nuevo_id("deb"), "texto": d.texto, "hipotesisAfectadas": [x for x in d.hipotesis if x in ids], "inyectada": False} for d in pred.debilidades[:6]]
        c["metaRevisiones"].append({"iteracion": ctx.numero, "fecha": ahora, "debilidades": debilidades})
        c["panorama"] = [{"titulo": d.titulo, "razon": d.razon, "hallazgosRecientes": d.hallazgos[:5], "queInvestigar": d.que_investigar[:5], "ideaEjemplo": d.idea_ejemplo, "inesperada": d.inesperada, "hipotesisIds": [x for x in d.hipotesis if x in ids]} for d in pred.direcciones[:4]]
        # Cada debilidad es un cambio de nivel 2 propuesto: cambiaria como razona
        # Rosa. Queda en el registro de aprendizaje hasta que una persona lo promueva.
        existentes = {a["descripcion"] for a in e2.get("aprendizaje", [])}
        for d in debilidades:
            if d["texto"] not in existentes and d["texto"] not in e2["criteriosRevision"]:
                e2.setdefault("aprendizaje", []).append(P.nuevo_cambio_aprendizaje(ctx.investigacion_id, 2, "criterio", d["texto"], f"debilidad:{d['id']}", "propuesto", config.QUIEN_ROSA, ahora))
        return True

    ctx.mutar(aplicar, "meta_revision")
    pista.cerrar(f"{len(pred.debilidades)} debilidades, {len(pred.direcciones)} direcciones")
    return f"{len(pred.debilidades)} debilidades recurrentes y {len(pred.direcciones)} direcciones en el panorama"


# ---------------------------------------------------------------------------
# Analisis in silico (ROSA2018, etapas 5 a 7)
# ---------------------------------------------------------------------------


async def paso_analisis(ctx: Ctx, paso: dict[str, Any]) -> str:
    """Primero las reproducciones pendientes de la puerta; despues los
    analisis que pidio la persona; despues, si la autonomia lo permite, un
    analisis por hipotesis que el Killer dejo avanzar y aun no tiene datos,
    sobre el primer dataset aprobado. Todo dentro de las politicas."""
    from rosa.bucle import analisis as AN

    e = ctx.e
    inv = ctx.inv()
    datasets_ok = [d for d in inv.get("datasets", []) if d["estado"] == "aprobado" and (d.get("procedencia") or {}).get("hash")]
    pista = ctx.pista(paso["id"], "modelo", "Analisis in silico", "Sandbox + GPT-6 Astra + Opus 5")
    hechos = 0
    for rep in [r for r in e.get("reproducciones", []) if r["investigacionId"] == ctx.investigacion_id and r["estado"] == "pendiente"][:3]:
        await AN.reproducir(ctx, rep, pista)
        hechos += 1
    if not datasets_ok:
        pista.cerrar("Sin datasets aprobados con fichero: no hay analisis que hacer" + (f"; {hechos} reproducciones" if hechos else ""))
        return "Sin datasets aprobados con fichero"
    pedidos = [h for h in e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id and h.get("_analisisPedido")]
    for h in pedidos:
        p = h["_analisisPedido"]
        await AN.analizar_hipotesis(ctx, h, p["datasetId"], p.get("pregunta", ""), pista)
        hechos += 1
    if e["autonomia"].get("correr_analisis") == "actuar":
        candidatas = [h for h in e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id and h.get("decisionKiller") == "avanzar" and not h.get("ejecuciones") and h["estado"] not in ("descartada",) and (h.get("tarjeta") or {}).get("prediccionFalsable")]
        for h in sorted(candidatas, key=lambda x: -x["elo"])[:2]:
            if pista.detenida():
                break
            await AN.analizar_hipotesis(ctx, h, datasets_ok[0]["id"], "", pista)
            hechos += 1
    pista.cerrar(f"{hechos} analisis o reproducciones")
    return f"{hechos} analisis in silico o reproducciones ejecutados"


EJECUTORES = {
    "literatura": paso_literatura,
    "ensayos": paso_ensayos,
    "extraccion": paso_extraccion,
    "verificacion": paso_verificacion,
    "novedad": paso_novedad,
    "modelo": paso_modelo,
    "hipotesis": paso_hipotesis,
    "meta": paso_meta,
    "analisis": paso_analisis,
}
