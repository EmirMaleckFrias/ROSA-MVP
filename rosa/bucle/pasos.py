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
from datetime import datetime, timezone
import math
import re
import traceback
from dataclasses import dataclass
from typing import Any

import dspy

from rosa import acuerdo_dorado as ACU
from rosa import ontologias as ONTO
from rosa import politicas
from rosa import sesgo as SESGO
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
from rosa import certeza as CERTEZA
from rosa import indice_semantico, reranker
from rosa.bucle import vivero as VIVERO
from rosa.fuentes import clinicaltrials, crossref, europepmc, exa, openalex, opentargets, pdf, pubmed, unpaywall
from rosa.fuentes.base import FuenteNoDisponible
from rosa.gateway import Modelos
from rosa.modulos.contador import ContextoLlamada, PresupuestoAgotado, contexto_actual, presupuesto_ok
from rosa.modulos.firmas import Programas

MAX_FUENTES_POR_CONSULTA = politicas.MAX_FUENTES_POR_CONSULTA
MAX_FUENTES_CON_RERANKER = politicas.MAX_FUENTES_CON_RERANKER
MAX_CRIBADO_MODELO = politicas.MAX_CRIBADO_MODELO


def maximo_por_consulta() -> int:
    """Cuántos candidatos se traen por consulta: más si el reranker va a cortar."""
    return MAX_FUENTES_CON_RERANKER if reranker.disponible() else MAX_FUENTES_POR_CONSULTA


async def cortar_con_reranker(pregunta: str, articulos: list[dict[str, Any]], pista: Pista | None, maximo: int = MAX_CRIBADO_MODELO) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], float]]]:
    """Ordena los artículos por pertinencia con el reranker del gateway y
    devuelve (los que ve el modelo, los que quedan fuera con su pertinencia).
    Si el reranker no está o falla, todos pasan al modelo, como antes."""
    if len(articulos) <= maximo or not reranker.disponible():
        return articulos, []
    try:
        orden = await reranker.reordenar(pregunta, [reranker.texto_de_articulo(a) for a in articulos])
    except FuenteNoDisponible as ex:
        if pista:
            pista.nota(f"Reranker no disponible ({str(ex)[:80]}); el modelo criba todos los candidatos")
        return articulos, []
    puntuacion = {i: s for i, s in orden}
    ordenados = sorted(range(len(articulos)), key=lambda i: -puntuacion.get(i, -1.0))
    dentro = [articulos[i] for i in ordenados[:maximo]]
    fuera = [(articulos[i], puntuacion.get(i, 0.0)) for i in ordenados[maximo:]]
    if pista:
        pista.accion("Reranker", {"base": "AI Gateway", "parametros": f"model={reranker.MODELO}&documentos={len(articulos)}&top_n={maximo}", "resultados": f"{len(dentro)} al modelo, {len(fuera)} fuera del corte"})
    return dentro, fuera
MAX_FUENTES_EXTRAER = politicas.MAX_FUENTES_EXTRAER
MAX_FRAGMENTOS_POR_FUENTE = politicas.MAX_FRAGMENTOS_POR_FUENTE
MAX_PAGINAS_PDF = 14
RELEVANCIA_MINIMA = politicas.RELEVANCIA_MINIMA
TAU_COBERTURA = 20.0


class ModeloBloqueado(RuntimeError):
    pass


SEGUNDOS_MAX_LLAMADA = 600  # una llamada al gateway que tarda mas de esto es un fallo, no una espera


def _pregunta_de(ctx: "Ctx") -> str | None:
    """El enunciado de la pregunta de la corrida, si Rosa ya la formuló."""
    return ((ctx.corrida().get("pregunta") or {}).get("enunciado")) or None


def _criterio(ctx: "Ctx", inv: dict[str, Any]) -> str:
    """El criterio de relevancia de este paso: objetivo, pregunta de la corrida
    y preguntas abiertas propias (ver contexto.preguntas_abiertas)."""
    return T.preguntas_abiertas(ctx.e["hechos"], ctx.investigacion_id, inv["objetivo"], pregunta=_pregunta_de(ctx))


def destino_de_propuesta(afirmaciones: list[dict[str, Any]], fuentes: list[dict[str, Any]]) -> tuple[str, str, str]:
    """('nace' | 'vivero', nivel, motivo). Una propuesta del generador nace como
    hipótesis solo si su evidencia ya da para certeza baja por regla (dos
    cohortes distintas); si no, va al vivero a esperar la segunda cohorte."""
    nivel, motivo = CERTEZA.techo({"afirmaciones": afirmaciones, "procedencia": {"fuentes": fuentes}})
    return ("nace" if CERTEZA.NIVELES.index(nivel) >= 1 else "vivero"), nivel, motivo


def _consulta_del_paso(ctx: "Ctx", inv: dict[str, Any], extra: str = "") -> str:
    """Con qué se eligen los hechos del modelo de mundo para un paso: el
    objetivo, la pregunta de la corrida y lo propio del paso."""
    return " ".join(x for x in (inv["objetivo"], _pregunta_de(ctx) or "", extra) if x)[:2000]


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
        Si el modelo devuelve vacío o lo bloquea un filtro, reintenta una vez
        con el modelo de volumen y deja una incidencia."""
        lm = {"cerebro": self.modelos.cerebro, "juez": self.modelos.juez, "volumen": self.modelos.volumen}[rol]
        # El corte de presupuesto de verdad: antes de llamar. (El callback de DSPy no
        # puede cortar: DSPy captura lo que lance y sigue.)
        if not presupuesto_ok(self.almacen, self.corrida_id, self.numero):
            raise PresupuestoAgotado(f"Presupuesto de la corrida {self.corrida_id} (o de su iteración {self.numero}) agotado")
        kwargs = self._acotar_contexto(rol, kwargs)
        token = contexto_actual.set(ContextoLlamada(self.corrida_id, self.numero, rol))
        try:
            try:
                with dspy.context(lm=lm):
                    return await asyncio.wait_for(programa.acall(**kwargs), timeout=SEGUNDOS_MAX_LLAMADA)
            except PresupuestoAgotado:
                raise
            except asyncio.TimeoutError:
                self.incidencia("modelo_sin_respuesta", f"El modelo {lm.model} no respondió en {SEGUNDOS_MAX_LLAMADA} s", "Tiempo agotado esperando al gateway", lm.model, "Se reintenta en el siguiente paso; si se repite, revisar el gateway.")
                raise RuntimeError(f"El modelo {lm.model} no respondió en {SEGUNDOS_MAX_LLAMADA} s")
            except Exception as ex:  # noqa: BLE001
                texto = str(ex)
                bloqueado = any(s in texto.lower() for s in ("content", "filter", "policy", "refus", "empty", "no output", "parse"))
                if not bloqueado or rol == "volumen":
                    raise
                if rol == "juez":
                    # El juez no cae a otro modelo sin decirlo: se reintenta una vez con el
                    # mismo y, si vuelve a fallar, la decision queda "no respondio".
                    self.incidencia("modelo_bloqueado", f"El juez {lm.model} no respondió a una petición", texto[:400], lm.model, "Se reintentó una vez con el mismo modelo; el juez nunca se sustituye por otro sin registrarlo.")
                    with dspy.context(lm=lm):
                        return await asyncio.wait_for(programa.acall(**kwargs), timeout=SEGUNDOS_MAX_LLAMADA)
                self.incidencia("modelo_bloqueado", f"El modelo {lm.model} no respondió a una petición", texto[:400], lm.model, "Se reintentó con Sonnet 5 automáticamente; si vuelve a pasar, revisar el prompt o cambiar el modelo del rol.")
                with dspy.context(lm=self.modelos.volumen):
                    return await asyncio.wait_for(programa.acall(**kwargs), timeout=SEGUNDOS_MAX_LLAMADA)
        finally:
            contexto_actual.reset(token)

    def _acotar_contexto(self, rol: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Politica de contexto: cada rol tiene un presupuesto de tokens de
        entrada (politicas.TOKENS_MAX_POR_ROL). Si el prompt lo excede, las
        entradas de texto mas largas se recortan (se conserva el principio y
        el final, con una marca) y queda registrado en la corrida como
        compactacion. Estimacion: 4 caracteres por token."""
        tope = politicas.TOKENS_MAX_POR_ROL.get(rol)
        if not tope:
            return kwargs
        textos = {k: v for k, v in kwargs.items() if isinstance(v, str)}
        total = sum(len(v) for v in textos.values()) // 4
        if total <= tope:
            return kwargs
        exceso_chars = (total - tope) * 4
        nuevos = dict(kwargs)
        for k, v in sorted(textos.items(), key=lambda kv: -len(kv[1])):
            if exceso_chars <= 0:
                break
            recorte = min(exceso_chars, max(0, len(v) - 2000))
            if recorte <= 0:
                continue
            mitad = (len(v) - recorte) // 2
            nuevos[k] = v[:mitad] + f"\n[... {recorte // 4} tokens recortados por la política de contexto del rol {rol} ...]\n" + v[len(v) - mitad:]
            exceso_chars -= recorte

        def fn(e: dict[str, Any]) -> bool:
            c = next((x for x in e["corridas"] if x["id"] == self.corrida_id), None)
            if not c:
                return False
            c["contexto"]["compactaciones"] = int(c["contexto"].get("compactaciones") or 0) + 1
            c["contexto"]["ultimaCompactacion"] = P.ahora_ms()
            return True

        self.mutar(fn, "compactacion")
        return nuevos

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


def claves_de_fuente(datos: dict[str, Any]) -> set[str]:
    """Identificadores normalizados con los que se reconoce una fuente ya vista:
    doi:..., pmid:..., nct:... y título:... (sin puntuación). Nunca la cadena
    vacía: dos fuentes sin nada en común no se fusionan."""
    claves: set[str] = set()
    doi = (datos.get("doi") or "").strip().lower()
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", doi).rstrip(".")
    if doi:
        claves.add(f"doi:{doi}")
    for campo in ("pmid", "nct"):
        v = str(datos.get(campo) or "").strip().lower()
        if v:
            claves.add(f"{campo}:{v}")
    titulo = re.sub(r"[^a-z0-9]+", " ", (datos.get("titulo") or "").lower()).strip()
    if len(titulo) >= 20:
        claves.add(f"titulo:{titulo}")
    return claves


def _registrar_fuente(ctx: Ctx, datos: dict[str, Any], tipo: str, fragmentos: list[dict[str, str]], relevancia: int, marca: str | None, marca_detalle: str, comprobada_en: int | None, consulta: str | None = None) -> str:
    """Añade una fuente al almacen privado de la corrida (o la actualiza) y
    devuelve su id."""
    claves = claves_de_fuente(datos)

    def fn(e: dict[str, Any]) -> str:
        c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
        fuentes = c.setdefault("_fuentes", {})
        # La misma fuente puede llegar de PubMed sin DOI y de Europe PMC con DOI:
        # coincide si comparte cualquier identificador normalizado (o el titulo
        # normalizado). Sin identificadores ni titulo, nunca se fusiona.
        existente = next((f for f in fuentes.values() if claves and (set(f.get("_claves") or ([f["_clave"]] if f.get("_clave") else [])) & claves)), None)
        if existente:
            existente["_claves"] = sorted(set(existente.get("_claves") or []) | claves)
            for campo in ("doi", "pmid", "nct"):
                if not existente.get(campo) and datos.get(campo):
                    existente[campo] = datos[campo]
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
        f["_claves"] = sorted(claves)
        f["_clave"] = next(iter(sorted(claves)), "")
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
    """Resumen siempre; texto completo por páginas (PDF) o secciones (JATS)
    si está disponible y la fuente es relevante."""
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
            pista.nota(f"Unpaywall no respondió para {datos['referencia']}: {ex}")
    if url_pdf:
        try:
            ruta = await pdf.descargar(url_pdf)
            if ruta:
                pags = pdf.paginas(ruta)[:MAX_PAGINAS_PDF]
                for p in pags:
                    fragmentos.append({"localizador": f"pág. {p['pagina']}", "texto": p["texto"], "encabezado": datos.get("titulo", ""), "_ruta": str(ruta)})
                pista.resultado(f"{datos['referencia']}: PDF con {len(pags)} páginas leídas")
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
    # 3. Último recurso: el texto limpio de la página, por Exa. Sin número de
    #    página, así que el localizador lo dice ("texto web, parte N"): sirve
    #    para verificar contra el pasaje literal, no sustituye a la cita a la
    #    página exacta de un PDF.
    if not any(fr["localizador"] != "resumen" for fr in fragmentos) and exa.disponible():
        url = datos.get("url") or (f"https://doi.org/{datos['doi']}" if datos.get("doi") else None)
        if url:
            try:
                paginas, coste = await exa.contenidos([url], maximo_caracteres=40000)
                _anotar_coste_exa(ctx, coste)
                texto = (paginas[0].get("texto") if paginas else "") or ""
                trozos = trocear_texto(texto)
                for i, t in enumerate(trozos[: MAX_FRAGMENTOS_POR_FUENTE * 2], start=1):
                    fragmentos.append({"localizador": f"texto web, parte {i}", "texto": t, "encabezado": datos.get("titulo", ""), "_url": url})
                if trozos:
                    pista.resultado(f"{datos['referencia']}: texto de la página en {min(len(trozos), MAX_FRAGMENTOS_POR_FUENTE * 2)} partes (Exa, sin paginación)")
                else:
                    pista.nota(f"{datos['referencia']}: Exa no devolvió texto para {url[:80]}")
            except FuenteNoDisponible as ex:
                pista.nota(f"Exa sin texto para {datos['referencia']}: {str(ex)[:120]}")
    return fragmentos


def trocear_texto(texto: str, tamano: int = 2500, minimo: int = 200) -> list[str]:
    """Parte un texto largo en trozos de unos `tamano` caracteres cortando en
    saltos de párrafo (o en punto y espacio si el párrafo es enorme). Los
    trozos más cortos que `minimo` se pegan al anterior; el texto vacío da []."""
    texto = (texto or "").strip()
    if not texto:
        return []
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    trozos: list[str] = []
    actual = ""
    for p in parrafos:
        while len(p) > tamano:
            corte = p.rfind(". ", 0, tamano)
            corte = corte + 1 if corte >= minimo else tamano
            trozo, p = p[:corte].strip(), p[corte:].strip()
            if actual:
                trozos.append(actual)
                actual = ""
            trozos.append(trozo)
        if len(actual) + len(p) + 1 > tamano and actual:
            trozos.append(actual)
            actual = p
        else:
            actual = f"{actual}\n{p}".strip() if actual else p
    if actual:
        if trozos and len(actual) < minimo:
            trozos[-1] = f"{trozos[-1]}\n{actual}"
        else:
            trozos.append(actual)
    return trozos


NOMBRES_BASE = {"pubmed": "PubMed", "europepmc": "Europe PMC", "preprints": "bioRxiv y medRxiv (vía Europe PMC)", "exa": "Exa (búsqueda semántica de publicaciones)", "gris": "Exa (literatura gris: reguladores, registros, portales del campo)"}


def consultas_por_nombre(nombres: list[str], consultas: list[dict[str, Any]], previas: list[str], maximo: int = 4) -> list[dict[str, Any]]:
    """Red de seguridad determinista: cada nombre propio del objetivo que
    ninguna consulta del plan (ni ninguna hecha antes) nombra, va como consulta
    por nombre exacto a Europe PMC. Así una corrida no termina sin haber
    buscado los ensayos que la persona escribió en el objetivo."""
    hechas = [q.get("consulta", "").lower() for q in consultas] + [p_.lower() for p_ in previas]
    salida = []
    for n in nombres:
        if any(n.lower() in h for h in hechas):
            continue
        salida.append({"base": "europepmc", "consulta": f'"{n}"', "tema": f"Por nombre exacto: {n}", "_por_nombre": True})
        if len(salida) >= maximo:
            break
    return salida


def bases_disponibles() -> list[str]:
    """Las bases que el planificador puede elegir ahora. Exa y la literatura
    gris (que va por Exa) solo con clave."""
    bases = ["pubmed", "europepmc", "preprints"]
    if exa.disponible():
        bases.extend(["exa", "gris"])
    return bases


def base_efectiva(consulta: dict[str, Any]) -> dict[str, Any]:
    """Si el planificador eligió una base que no está disponible (exa sin clave),
    la consulta va a Europe PMC, que admite lenguaje natural razonablemente,
    con una nota. Nunca se pierde una consulta por falta de clave."""
    if consulta.get("base") not in bases_disponibles():
        return {**consulta, "base": "europepmc", "tema": consulta.get("tema", ""), "_desviada_de": consulta.get("base")}
    return consulta


async def _consulta_literatura(ctx: Ctx, paso: dict[str, Any], consulta: dict[str, str], preguntas: str) -> dict[str, int]:
    base = consulta["base"]
    nombre_base = NOMBRES_BASE[base]
    pista = ctx.pista(paso["id"], "literatura", consulta["tema"][:80] or consulta["consulta"][:80], nombre_base)
    resultado = {"identificados": 0, "cribados": 0, "textoCompleto": 0, "leidos": 0}
    try:
        pista.accion(f"Consulta: {consulta['consulta']}")
        if consulta.get("_desviada_de"):
            pista.nota(f"El plan la dirigía a {consulta['_desviada_de']}, que no está disponible (sin clave); va a {nombre_base}")
        ahora = P.ahora_ms()
        if base == "pubmed":
            ids, total = await pubmed.buscar(consulta["consulta"], maximo=maximo_por_consulta())
            pista.accion("esearch + efetch", {"base": "PubMed E-utilities", "parametros": f"db=pubmed&term={consulta['consulta']}&retmax={maximo_por_consulta()}", "resultados": f"{total} PMID, se traen {len(ids)}"})
            articulos = await pubmed.detalles(ids)
        elif base in ("exa", "gris"):
            # Búsqueda semántica: la consulta es una pregunta en lenguaje natural.
            # Los pasajes destacados se guían con las preguntas abiertas, para
            # que el pasaje que vuelve sea el que responde. Exa no da un total:
            # identificados = traídos. "gris" busca sin categoría y acotado a los
            # dominios de reguladores, registros y portales del campo.
            gris = base == "gris"
            articulos, total, coste_exa = await exa.buscar(consulta["consulta"], maximo=maximo_por_consulta(), categoria=None if gris else "publication", dominios=exa.DOMINIOS_GRIS if gris else None, pregunta_pasajes=preguntas[:500] or None)
            pista.accion("search (neural)", {"base": "Exa", "parametros": (f"includeDomains={','.join(exa.DOMINIOS_GRIS[:4])}..." if gris else "category=publication") + f"&numResults={MAX_FUENTES_POR_CONSULTA}&type=auto&highlights.query=preguntas abiertas", "resultados": f"{total} documentos, {coste_exa:.4f} USD"})
            _anotar_coste_exa(ctx, coste_exa)
            if articulos:
                # Orden por afinidad del mejor pasaje con las preguntas, cuando Exa la da.
                articulos.sort(key=lambda a: -(a.get("similitud") or 0.0))
        else:
            articulos, total = await europepmc.buscar(consulta["consulta"], maximo=maximo_por_consulta(), solo_preprints=(base == "preprints"))
            pista.accion("REST search", {"base": "Europe PMC", "parametros": f"query={consulta['consulta']}{' AND SRC:PPR' if base == 'preprints' else ''}&pageSize={maximo_por_consulta()}&resultType=core", "resultados": f"{total} resultados, se traen {len(articulos)}"})
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
            pista.cerrar(f"{total} resultados, ninguno traído", "hecha")
            return resultado

        # Corte previo por pertinencia con el reranker del gateway: el modelo
        # solo puntúa a los mejores; los demás quedan excluidos con su cifra.
        al_modelo, fuera = await cortar_con_reranker(f"{preguntas}\n{consulta['tema']}", [a for a in articulos if a.get("titulo")], pista)
        # Cribado por relevancia (Sonnet 5), como el RCS de PaperQA.
        puntuados: list[tuple[int, dict[str, Any], str]] = []
        for a, s in fuera:
            puntuados.append((min(RELEVANCIA_MINIMA - 1, int(round(s * 10))), a, f"fuera del corte del reranker (pertinencia {s:.2f}); no se gastó una llamada al modelo"))
        sem = asyncio.Semaphore(4)

        async def puntuar(a: dict[str, Any]) -> None:
            async with sem:
                try:
                    pred = await ctx.llamar("volumen", ctx.programas.relevancia, preguntas_abiertas=preguntas, titulo=a.get("titulo", ""), resumen=K.como_dato((a.get("resumen") or "")[:3000]))
                    puntuados.append((int(pred.puntuacion), a, pred.motivo))
                except PresupuestoAgotado:
                    raise
                except Exception as ex:  # noqa: BLE001
                    # Un fallo del modelo no vuelve irrelevante al articulo: se conserva con nota.
                    puntuados.append((RELEVANCIA_MINIMA, a, f"sin puntuar (el modelo no respondió: {str(ex)[:60]}); se conserva para no perderlo"))

        await asyncio.gather(*(puntuar(a) for a in al_modelo))
        puntuados.sort(key=lambda x: -x[0])
        relevantes = [x for x in puntuados if x[0] >= RELEVANCIA_MINIMA]
        descartados = [x for x in puntuados if x[0] < RELEVANCIA_MINIMA]
        resultado["cribados"] = len(relevantes)
        pista.resultado(f"Cribado: {len(relevantes)} de {len(puntuados)} relevantes (puntuacion >= {RELEVANCIA_MINIMA}); descartados: " + ", ".join(f"{a['referencia']} ({p})" for p, a, _ in descartados)[:300])

        def anotar_cribado(e: dict[str, Any]) -> bool:
            # Cada excluido con su motivo: es el item 16b de PRISMA 2020 y la caja de
            # exclusiones de la herramienta automatica del diagrama.
            c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
            b = c["busqueda"]
            b["traidos"] = int(b.get("traidos") or 0) + len(puntuados)
            ex = b.setdefault("excluidos", [])
            for p_, a_, motivo_ in descartados:
                ex.append({"referencia": a_.get("referencia", ""), "titulo": (a_.get("titulo") or "")[:160], "doi": a_.get("doi"), "pmid": a_.get("pmid"), "relevancia": int(p_), "motivo": (motivo_ or "")[:240], "iteracion": ctx.numero, "consulta": consulta["consulta"][:160], "base": nombre_base})
            if len(ex) > 600:
                del ex[: len(ex) - 600]
            return True

        ctx.mutar(anotar_cribado, "cribado")

        for i, (puntuacion, a, motivo) in enumerate(relevantes):
            if pista.detenida():
                break
            marca, detalle, comprobada = None, "Sin DOI: no se pudo comprobar en Crossref", None
            if a.get("doi"):
                try:
                    marca, detalle = await crossref.marca_editorial(a["doi"])
                    comprobada = P.ahora_ms()
                except FuenteNoDisponible as ex:
                    detalle = f"Crossref no respondió: {str(ex)[:100]}. No se afirma que este limpio."
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
        pista.fallar(f"{nombre_base} no respondió: {str(ex)[:160]}. No es 'sin resultados': la consulta no llegó.")
        _contar_fallo_fuente(ctx, nombre_base, str(ex))
    return resultado


def fecha_iso_de_ms(ms: Any) -> str | None:
    """AAAA-MM-DD a partir de milisegundos desde la época; None si no hay."""
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date().isoformat() if ms else None
    except (TypeError, ValueError, OSError):
        return None


def estado_por_puntuacion(mejor: int, alto: str, parcial: str, ninguno: str) -> str:
    """La misma regla que el precedente en la literatura: 8 o más es "ya
    existe", de 5 a 7 es parcial, menos es nada claro."""
    return alto if mejor >= 8 else parcial if mejor >= 5 else ninguno


async def _novedad_exa_dominios(ctx: Ctx, h: dict[str, Any], pista: Pista, novedad: dict[str, Any], clave: str, dominios: list[str], pregunta: str, estados: tuple[str, str, str], etiqueta: str) -> None:
    """Una comprobación de novedad sobre un conjunto de dominios de Exa
    (patentes, financiación): búsqueda semántica del enunciado, acotada a lo
    publicado antes de que Rosa propusiera la hipótesis, y cribado de los tres
    mejores con el programa de relevancia. Sin Exa queda "no comprobado" con
    el motivo, nunca "no hay"."""
    if not exa.disponible():
        novedad[clave] = {"estado": "no_comprobado", "detalle": f"No comprobado: requiere Exa (ROSA_EXA_KEY) para buscar en {etiqueta}", "url": None}
        return
    try:
        docs, n, coste = await exa.buscar(h["enunciado"][:600], maximo=5, categoria=None, dominios=dominios, pregunta_pasajes=h["enunciado"][:500], hasta_fecha=fecha_iso_de_ms(h.get("creadaEn")))
        pista.accion(f"Exa ({etiqueta}): enunciado completo", {"base": "Exa", "parametros": f"includeDomains={','.join(dominios[:3])}...&numResults=5&endPublishedDate=creación de la hipótesis", "resultados": f"{n} documentos, {coste:.4f} USD"})
        _anotar_coste_exa(ctx, coste)
        mejor, mejor_ref, mejor_url = 0, "", None
        for d in [x for x in docs if x.get("titulo")][:3]:
            try:
                p = await ctx.llamar("volumen", ctx.programas.relevancia, preguntas_abiertas=f"{pregunta}: {h['enunciado']}", titulo=d["titulo"], resumen=(d.get("resumen") or "")[:2500])
                if int(p.puntuacion) > mejor:
                    mejor, mejor_ref, mejor_url = int(p.puntuacion), f"{d['titulo'][:90]} ({d.get('fecha') or 'sin fecha'})", d.get("url")
            except PresupuestoAgotado:
                raise
            except Exception:  # noqa: BLE001
                continue
        estado = estado_por_puntuacion(mejor, *estados)
        if estado == estados[0]:
            detalle = f"Ya existe algo muy cercano en {etiqueta}: {mejor_ref} (puntuación {mejor}/10)"
        elif estado == estados[1]:
            detalle = f"Relación parcial en {etiqueta}: {mejor_ref} (puntuación {mejor}/10)"
        else:
            detalle = f"Nada claro en {etiqueta} entre {n} documentos anteriores a la hipótesis"
        novedad[clave] = {"estado": estado, "detalle": detalle, "url": mejor_url if estado != estados[2] else None}
    except FuenteNoDisponible as ex:
        novedad[clave] = {"estado": "no_comprobado", "detalle": f"No comprobado: Exa no respondió al buscar en {etiqueta} ({str(ex)[:60]})", "url": None}


def _anotar_coste_exa(ctx: Ctx, usd: float) -> None:
    """El gasto en Exa se suma al gasto de la corrida (`gasto.exaUsd`), junto al
    de los modelos, para que el coste por decisión lo incluya."""
    if not usd:
        return

    def fn(e: dict[str, Any]) -> bool:
        c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
        c["gasto"]["exaUsd"] = round(float(c["gasto"].get("exaUsd") or 0.0) + float(usd), 6)
        return True

    ctx.mutar(fn, "gasto_exa")


def _contar_fallo_fuente(ctx: Ctx, base: str, error: str) -> None:
    def fn(e: dict[str, Any]) -> bool:
        c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
        fallos = c.setdefault("_fallosFuente", {})
        fallos[base] = fallos.get(base, 0) + 1
        return True

    ctx.mutar(fn, "fallo_fuente")
    if ctx.corrida().get("_fallosFuente", {}).get(base, 0) >= 3:
        ctx.incidencia("fuente_sin_respuesta", f"{base} lleva 3 fallos seguidos", error[:400], base, "Comprobar la conexión o esperar; Rosa sigue con las demás fuentes.")


async def paso_literatura(ctx: Ctx, paso: dict[str, Any]) -> str:
    inv = ctx.inv()
    e = ctx.e
    preguntas = _criterio(ctx, inv)
    previas = ctx.corrida().get("_consultasHechas", [])
    nombres = T.nombres_propios(f"{inv['objetivo']} {preguntas}")
    pred = await ctx.llamar("cerebro", ctx.programas.consultas, objetivo=inv["objetivo"], preguntas_abiertas=preguntas, hipotesis_vivas=T.hipotesis_vivas(e["hipotesis"], ctx.investigacion_id) + "\n" + T.vivero_texto(inv), consultas_previas="\n".join(previas[-20:]) or "Ninguna", indicaciones_humanas=T.indicaciones_humanas(ctx.iteracion()) + ("\n" + paso["detalle"] if paso.get("detalle") else ""), bases_disponibles=", ".join(bases_disponibles()), nombres_propios=", ".join(nombres) or "Ninguno")
    consultas = [base_efectiva(c.model_dump()) for c in pred.consultas][:5]
    consultas += consultas_por_nombre(nombres, consultas, previas)
    if not consultas:
        return "El modelo no propuso consultas"
    crudos = await asyncio.gather(*(_consulta_literatura(ctx, paso, c, preguntas) for c in consultas), return_exceptions=True)
    for c, r in zip(consultas, crudos):
        if isinstance(r, PresupuestoAgotado):
            raise r
        if isinstance(r, BaseException):
            # Una consulta que reventó no tumba las otras cuatro.
            traceback.print_exc()
            ctx.pista(paso["id"], "literatura", f"Consulta fallida: {c.get('consulta', '')[:50]}", "").fallar(f"{type(r).__name__}: {str(r)[:160]}")
    pares = [(q, r) for q, r in zip(consultas, crudos) if isinstance(r, dict)]
    resultados = [r for _, r in pares]
    total = {k: sum(r[k] for r in resultados) for k in resultados[0]} if resultados else {}
    leidos_por_tema: dict[str, int] = {}
    for q, r in pares:
        leidos_por_tema[q["tema"][:60]] = leidos_por_tema.get(q["tema"][:60], 0) + r["leidos"]

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
    terminos = T.terminos_registro(inv["objetivo"], _pregunta_de(ctx), paso.get("detalle", ""), maximo=3)
    pista = ctx.pista(paso["id"], "ensayos", "Ensayos registrados sobre " + (", ".join(terminos) or "el objetivo"), "ClinicalTrials.gov v2")
    try:
        # Nombres propios y siglas unidos con OR: ClinicalTrials.gov está en inglés y su
        # sintaxis (Essie) trata el espacio como AND, así que "A B C" no devuelve nada.
        termino = " OR ".join(terminos)
        pista.accion("GET /api/v2/studies", {"base": "ClinicalTrials.gov v2", "parametros": f"query.cond=Alzheimer Disease&query.term={termino}&pageSize=25&countTotal=true", "resultados": "..."})
        estudios, total = await clinicaltrials.buscar("Alzheimer Disease", termino=termino, maximo=25)
        pista.resultado(f"{total} estudios; se registran {len(estudios)}")
        ahora = P.ahora_ms()
        for s in estudios:
            texto = f"{s['titulo']}. Estado: {s['estado']}. Fases: {', '.join(s['fases'])}. Intervenciones: {', '.join(x for x in s['intervenciones'] if x)}. Desenlaces primarios: {'; '.join(x for x in s['desenlaces'] if x)}. Inicio: {s['inicio']}. Patrocinador: {s['patrocinador']}."
            datos = {"referencia": f"{s['nct']}", "titulo": s["titulo"], "nct": s["nct"], "anio": int(s["inicio"][:4]) if s.get("inicio") and s["inicio"][:4].isdigit() else None, "tipos": ["registro"]}
            _registrar_fuente(ctx, datos, "ensayo", [{"localizador": "resumen", "texto": texto, "encabezado": s["titulo"]}], 6, None, "Registro de ensayo; no aplica retractación", ahora, f"cond=Alzheimer Disease term={termino}")

        def anotar(e: dict[str, Any]) -> bool:
            c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
            c["busqueda"]["consultas"].append({"base": "ClinicalTrials.gov v2", "consulta": f"cond=Alzheimer Disease term={termino}", "fecha": ahora, "resultados": total, "iteracion": ctx.numero, "tema": "Ensayos registrados"})
            c["busqueda"]["identificados"] += total
            return True

        ctx.mutar(anotar, "consulta")
        pista.cerrar(f"{total} estudios, {len(estudios)} registrados como fuentes")
        return f"{total} ensayos encontrados, {len(estudios)} registrados"
    except FuenteNoDisponible as ex:
        pista.fallar(f"ClinicalTrials.gov no respondio: {str(ex)[:160]}. No es 'sin ensayos': la consulta no llegó.")
        _contar_fallo_fuente(ctx, "ClinicalTrials.gov v2", str(ex))
        return "ClinicalTrials.gov no respondio"


# ---------------------------------------------------------------------------
# Extraccion
# ---------------------------------------------------------------------------


async def paso_extraccion(ctx: Ctx, paso: dict[str, Any]) -> str:
    inv = ctx.inv()
    preguntas = _criterio(ctx, inv)
    pendientes = sorted([f for f in ctx.fuentes().values() if not f.get("extraida") and f.get("retraccion") != "retractado"], key=lambda f: -f.get("relevancia", 0))[:MAX_FUENTES_EXTRAER]
    if not pendientes:
        return "No hay fuentes nuevas de las que extraer"
    pista = ctx.pista(paso["id"], "extraccion", f"Extraer afirmaciones de {len(pendientes)} fuentes", "Sonnet 5")
    pista.accion("Un fragmento a la vez (resumen, página o sección), sin cruzar de fragmento; cada afirmación con su cita literal")
    sem = asyncio.Semaphore(4)
    total = 0
    hechas = 0

    async def extraer(f: dict[str, Any]) -> None:

        fallos_fragmentos = 0
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
                pista.nota(f"{f['referencia']} ({fr['localizador']}): el fragmento contiene texto que parece una instrucción para un modelo; se marca y se enseña, no se bloquea")
            async with sem:
                try:
                    # El fragmento entra delimitado como dato (spotlighting), nunca como instruccion.
                    pred = await ctx.llamar("volumen", ctx.programas.extraer, preguntas_abiertas=preguntas, referencia=f["referencia"], localizador=fr["localizador"], fragmento=K.como_dato(texto))
                except PresupuestoAgotado:
                    raise
                except Exception as ex:  # noqa: BLE001
                    pista.error(f"{f['referencia']} ({fr['localizador']}): el extractor fallo: {str(ex)[:120]}")
                    fallos_fragmentos += 1
                    continue
            for a in pred.afirmaciones:
                # Comprobacion literal en PDF: la pagina de la cita tiene que contener el fragmento.
                if fr.get("_ruta") and fr["localizador"].startswith("pág.") and not pdf.fragmento_en_pagina(__import__("pathlib").Path(fr["_ruta"]), a.fragmento, int(fr["localizador"].split(" ")[1])):
                    pista.nota(f"{f['referencia']}: fragmento no encontrado literalmente en la {fr['localizador']}; la afirmacion se marca cita_no_resuelve")
                    veredicto_inicial = "cita_no_resuelve"
                    motivo = "El fragmento citado no aparece literalmente en la página indicada."
                else:
                    veredicto_inicial, motivo = "sin_verificar", "Pendiente de verificación"
                cohorte = (getattr(a, "cohorte", "") or "").strip()[:60]
                nivel = getattr(a, "nivel_medicion", "resultado_analisis") or "resultado_analisis"
                registro = {k: (getattr(a, k, "") or "").strip()[:80] for k in ("n", "comparador", "efecto", "incertidumbre")}
                # Comprobaciones automaticas del registro de evidencia (plan completo,
                # seccion 3): lo que un dato deberia traer y no trae queda sin resolver.
                sin_resolver = [k for k in ("n", "comparador", "efecto") if a.tipo == "dato" and not registro[k]]
                if a.tipo == "dato" and nivel == "interpretacion_autor":
                    sin_resolver.append("una interpretación de los autores no es una medida: se rebaja a literatura")
                    tipo_af = "literatura"
                else:
                    tipo_af = a.tipo
                nuevas.append({"id": P.nuevo_id("af"), "texto": a.texto.strip(), "cita": f"[{f['referencia']}, {fr['localizador']}]", "fragmento": a.fragmento.strip(), "veredicto": veredicto_inicial, "motivo": motivo, "entidadDistinta": False, "tipo": tipo_af, "clase": "literatura", "sintetico": False, "cohorte": cohorte, "sospechosoInyeccion": sospechoso, "nivelMedicion": nivel, **registro, "sinResolver": sin_resolver, "tema": a.tema, "fuenteId": f["id"], "localizador": fr["localizador"], "iteracion": ctx.numero, "encabezado": fr.get("encabezado", "")})

        def guardar(e: dict[str, Any]) -> bool:
            c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
            c.setdefault("_afirmaciones", []).extend(nuevas)
            fuente = c["_fuentes"][f["id"]]
            # Con algun fragmento sin extraer por fallo del modelo, la fuente queda pendiente para reintentar.
            fuente["extraida"] = fallos_fragmentos == 0
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
        pista.cerrar("Presupuesto agotado a mitad de la extracción", "detenida")
        raise
    return f"{total} afirmaciones extraidas de {hechas} fuentes"


# ---------------------------------------------------------------------------
# Verificacion
# ---------------------------------------------------------------------------


async def verificar_afirmaciones(ctx: Ctx, afirmaciones: list[dict[str, Any]], pista: Pista | None, pregunta: str) -> dict[str, int]:
    """Deterministas primero, juez después. Cambia el veredicto en sitio (y en
    el almacen). Devuelve el recuento por veredicto."""
    frags = ctx.fragmentos_verificador()
    por_id = {f.fuente_id: f for f in frags}
    recuento: dict[str, int] = {}
    al_juez: list[tuple[dict[str, Any], V.Resultado]] = []
    # Los terminos del objetivo (la enfermedad, la cohorte) no cuentan como
    # identificadores en una declaracion de ausencia: estan en todo el corpus.
    excluir = V.terminos_del_dominio(pregunta)
    for a in afirmaciones:
        r = V.comprobar_determinista(a["texto"], a["cita"], a.get("fragmento"), frags, frags, excluir)
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
        pista.cerrar("Presupuesto agotado a mitad de la verificación", "detenida")
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
                "juez": ctx.modelos.juez.model,
                "casos": len(pendientes),
                # Acuerdo con las personas: sale del conjunto dorado (etiquetas humanas
                # sobre veredictos del Killer), no de una constante.
                "acuerdoConHumanos": (ACU.acuerdo_dorado(e).get("global") or {}).get("kappa"),
                "sostenidas": round(fid, 3) if fid is not None else 0,
                "cobertura": round(1 - recuento.get("cita_no_resuelve", 0) / max(1, len(pendientes)), 3),
                "ausenciasRefutadas": recuento.get("ausencia_refutada", 0),
                "entidadDistinta": sum(1 for a in pendientes if a.get("entidadDistinta")),
                "sinVerificar": recuento.get("sin_verificar", 0),
                "aciertoPorTipo": ACU.acierto_por_tipo(e),
            }
        )
        return True

    ctx.mutar(metricas, "metricas")
    return resumen


# ---------------------------------------------------------------------------
# Modelo de mundo
# ---------------------------------------------------------------------------


def _fuente_publica(f: dict[str, Any], afirmacion: dict[str, Any] | None = None) -> dict[str, Any]:
    """La Fuente tal como la ve la interfaz, con la página y el fragmento de
    la afirmación concreta si se da."""
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
    mundo = await T.modelo_de_mundo_para(ctx.almacen, ctx.investigacion_id, _consulta_del_paso(ctx, inv, texto[:1500]))
    pred = await ctx.llamar("cerebro", ctx.programas.mundo, objetivo=inv["objetivo"], modelo_de_mundo=mundo, afirmaciones_sostenidas=texto)
    ahora = P.ahora_ms()
    fuentes = ctx.fuentes()
    anadidos = 0
    preguntas = 0
    # Genes nombrados en los hechos nuevos, resueltos en HGNC (con cache en el estado).
    cache_ent = dict(ctx.e.get("entidadesCache") or {})
    simbolos_nuevos = sorted({s_ for hp in pred.hechos for s_ in simbolos_de_genes(hp.enunciado)})[:12]
    genes_resueltos = await ONTO.normalizar(simbolos_nuevos, [], cache_ent) if simbolos_nuevos else []

    def aplicar(e2: dict[str, Any]) -> bool:
        nonlocal anadidos, preguntas
        e2["entidadesCache"] = {k: v for k, v in list(cache_ent.items())[-2000:]}
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
            h = P.nuevo_hecho(ctx.investigacion_id, "hecho" if hp.tipo == "hecho" else "pregunta", hp.tema, hp.enunciado, "sabido" if hp.tipo == "hecho" else "abierto", "fuente" if hp.tipo == "hecho" else "inferencia", procedencia, ahora, hp.prioridad, f"Añadido en la iteración {ctx.numero}")
            # Entidades canonicas del hecho: diccionario curado mas los genes que HGNC
            # resolvio (cache `entidadesCache` del estado). Con ellas el modelo de mundo
            # se puede consultar y deduplicar por identificador, no por cadena.
            h["entidades"] = ONTO.fusionar(ONTO.anotar_curadas(hp.enunciado), [x for x in genes_resueltos if x["texto"].upper() in {s_.upper() for s_ in simbolos_de_genes(hp.enunciado)}])
            ids_nuevo = ONTO.ids_de(h["entidades"])
            if ids_nuevo and any(len(ids_nuevo & ONTO.ids_de(x.get("entidades"))) >= 2 and V.normalizar(x["enunciado"])[:40] == V.normalizar(hp.enunciado)[:40] for x in e2["hechos"] if x["investigacionId"] == ctx.investigacion_id):
                continue  # mismo comienzo y mismas entidades canonicas: es el mismo hecho con otras palabras
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
    contenido = "# Modelo de mundo\n\n" + T.modelo_de_mundo(ctx.e["hechos"], ctx.investigacion_id, maximo=500, investigaciones=ctx.e["investigaciones"])
    ctx.mutar(lambda e2: A.guardar_artefacto(e2, ctx.investigacion_id, "Modelo de mundo", "modelo_mundo", contenido, f"Iteración {ctx.numero}: {anadidos} hechos y {preguntas} preguntas nuevas", ctx.numero, ahora), "artefacto")
    pista.cerrar(f"{anadidos} hechos, {preguntas} preguntas")
    return f"{anadidos} hechos y {preguntas} preguntas nuevas en el modelo de mundo"


# ---------------------------------------------------------------------------
# Hipotesis: generar, revisar, torneo
# ---------------------------------------------------------------------------


def _texto_mision(inv: dict[str, Any]) -> str:
    m = inv.get("mision") or {}
    memoria = inv.get("memoria") or []
    texto_mem = (" Memoria del proyecto (hechos fijados por las personas): " + " | ".join(x["texto"] for x in memoria[:12])) if memoria else ""
    operativo = inv.get("conocimientoOperativo") or []
    if operativo:
        # Lo que el laboratorio sabe y no esta en ningun articulo: protocolos poco
        # fiables, lotes que fallan, artefactos de medida. Clase de evidencia propia.
        texto_mem += " Conocimiento operativo del laboratorio (no publicado; clase conocimiento_operativo): " + " | ".join(f"[{x['tipo']}] {x['texto']}" for x in operativo[:12])
    if not m:
        return "Sin misión estructurada todavía." + texto_mem
    return f"Población: {m.get('poblacion') or 'sin fijar'}. Etapa: {m.get('etapa') or 'sin fijar'}. Célula o tejido: {m.get('celulaTejido') or 'sin fijar'}. Mecanismo: {m.get('mecanismo') or 'sin fijar'}. Tipo de intervención: {m.get('tipoIntervencion') or 'sin fijar'}. Capacidades del laboratorio: {'; '.join(m.get('capacidadesLaboratorio', [])) or 'sin declarar'}." + texto_mem


async def _completar_tarjeta(ctx: Ctx, h: dict[str, Any], pista: Pista | None) -> None:
    """La tarjeta (contrato mínimo) de una hipótesis que no la trae: humana o
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


MAX_FUENTES_SESGO = 3


async def _anotar_entidades(ctx: Ctx, h: dict[str, Any]) -> None:
    """`h["entidades"]`: identificadores canonicos (HGNC, MONDO, CL, UBERON, GO,
    ChEBI) de lo que nombra la hipotesis. Se recalcula si cambio la version."""
    if (h.get("_entidadesVersion") == h.get("version", 1)) and h.get("entidades") is not None:
        return
    t = h.get("tarjeta") or {}
    texto = " ".join([h.get("titulo", ""), h.get("enunciado", ""), h.get("mecanismo", ""), t.get("diana", ""), t.get("celula", ""), (h.get("comprobacion") or {}).get("biomarcador", "")])
    curadas = ONTO.anotar_curadas(texto)
    simbolos = simbolos_de_genes(" ".join([h.get("titulo", ""), t.get("diana", ""), (h.get("comprobacion") or {}).get("biomarcador", "")]))[:6]
    cache_ent = dict(ctx.e.get("entidadesCache") or {})
    try:
        genes = await ONTO.normalizar(simbolos, [], cache_ent) if simbolos else []
    except Exception:  # noqa: BLE001
        genes = []
    entidades = ONTO.fusionar(curadas, genes)

    def fn(e: dict[str, Any]) -> bool:
        x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
        if not x:
            return False
        x["entidades"] = entidades
        x["_entidadesVersion"] = x.get("version", 1)
        e["entidadesCache"] = {k: v for k, v in list(cache_ent.items())[-2000:]}
        return True

    ctx.mutar(fn, "entidades")
    h["entidades"] = entidades


def _fuentes_de_hipotesis(ctx: Ctx, h: dict[str, Any]) -> list[dict[str, Any]]:
    """Las fuentes privadas de la corrida que respaldan la hipótesis."""
    privadas = ctx.fuentes()
    ids = [f["id"] for f in (h.get("procedencia") or {}).get("fuentes", [])]
    return [privadas[i] for i in ids if i in privadas]


def _texto_fuente_para_sesgo(f: dict[str, Any]) -> str:
    partes = [f.get("titulo") or "", f.get("resumen") or f.get("fragmento") or ""]
    partes += [fr.get("texto", "") for fr in (f.get("fragmentos") or [])[:8]]
    return "\n".join(x for x in partes if x)[:9000]


async def _evaluar_sesgo_fuentes(ctx: Ctx, h: dict[str, Any], pista: Pista | None) -> None:
    """Riesgo de sesgo por instrumento para las fuentes primarias de la
    hipotesis que aun no lo tienen (hasta MAX_FUENTES_SESGO por pasada, las
    mas relevantes). Se guarda en la fuente privada y en la copia publica."""
    pendientes = []
    for f in _fuentes_de_hipotesis(ctx, h):
        if f.get("riesgoSesgo") or f.get("retraccion") == "retractado":
            continue
        clave = SESGO.instrumento_para(f.get("tipoEstudio"), (f.get("titulo") or "") + " " + (f.get("resumen") or ""))
        if clave:
            pendientes.append((f, clave))
    pendientes.sort(key=lambda x: -x[0].get("relevancia", 0))
    for f, clave in pendientes[:MAX_FUENTES_SESGO]:
        try:
            pred = await ctx.llamar("juez", ctx.programas.senalizacion, instrumento_y_preguntas=SESGO.texto_preguntas(clave), referencia=f.get("referencia", ""), texto=K.como_dato(_texto_fuente_para_sesgo(f)))
            respuestas = [{"id": r.id, "respuesta": r.respuesta, "cita": r.cita} for r in pred.respuestas]
        except PresupuestoAgotado:
            raise
        except Exception as ex:  # noqa: BLE001
            if pista:
                pista.error(f"Riesgo de sesgo de {f.get('referencia', '')[:40]} sin evaluar: {str(ex)[:100]}")
            continue
        evaluacion = SESGO.evaluar(clave, respuestas, ctx.modelos.juez.model, P.ahora_ms())
        compacta = {k: evaluacion[k] for k in ("instrumento", "clave", "version", "global", "resumen", "fecha", "modelo")} | {"dominios": [{"id": d["id"], "nombre": d["nombre"], "juicio": d["juicio"], "motivo": d["motivo"]} for d in evaluacion["dominios"]]}
        if pista:
            pista.resultado(f"{f.get('referencia', '')[:50]}: {evaluacion['resumen'][:160]}")

        def fn(e: dict[str, Any], fid=f["id"], ev=evaluacion, comp=compacta) -> bool:
            c = next(x for x in e["corridas"] if x["id"] == ctx.corrida_id)
            priv = c.get("_fuentes", {}).get(fid)
            if priv is not None:
                priv["riesgoSesgo"] = ev
            for x in e["hipotesis"]:
                for fu in (x.get("procedencia") or {}).get("fuentes", []):
                    if fu.get("id") == fid:
                        fu["riesgoSesgo"] = comp
            return True

        ctx.mutar(fn, "riesgo_sesgo")


async def _killer(ctx: Ctx, h: dict[str, Any], texto_afirmaciones: str, pista: Pista | None, profundidad: int = 0) -> str:
    """El Hypothesis Killer sobre la versión actual de la hipótesis. Devuelve
    la decisión. Si decide reformular, reformula (versión nueva) y vuelve a
    juzgar la nueva versión, hasta el límite de la política."""
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
    # Entidades canonicas de la hipotesis (HGNC para la diana, diccionario curado
    # para lo demas) y redundancia por identificador: dos hipotesis vivas que
    # comparten dos o mas entidades canonicas hablan quiza de lo mismo con otras
    # palabras; el juez lo recibe como pista, no como veredicto.
    await _anotar_entidades(ctx, h)
    if not any(c["comprobacion"] == "redundancia" for c in deterministas):
        parecidas = [(x, ONTO.comparten(h.get("entidades"), x.get("entidades"))) for x in e["hipotesis"] if x["id"] != h["id"] and x["investigacionId"] == h["investigacionId"] and x["estado"] != "descartada"]
        parecidas = [(x, c) for x, c in parecidas if c]
        if parecidas:
            deterministas.append({"comprobacion": "redundancia", "resultado": "no_comprobable", "detalle": "Comparte entidades canónicas con: " + "; ".join(f"{x['titulo'][:60]} ({', '.join(c)})" for x, c in parecidas[:3]) + ". El juez decide si es la misma hipótesis con otras palabras."})
    # Redundancia por significado (índice semántico): también contra las
    # descartadas, porque repetir una descartada con otras palabras es el
    # anclaje que más cuesta ver.
    if not any(c["comprobacion"] == "redundancia" for c in deterministas):
        try:
            semejantes = await indice_semantico.hipotesis_parecidas(ctx.almacen, h)
        except FuenteNoDisponible as ex:
            semejantes = []
            if pista:
                pista.nota(f"Índice semántico sin respuesta: {str(ex)[:80]}")
        if semejantes:
            resultado = "falla" if any(x["estado"] == "descartada" and x["similitud"] >= 0.95 for x in semejantes) else "no_comprobable"
            deterministas.append({"comprobacion": "redundancia", "resultado": resultado, "detalle": "Por significado se parece a: " + "; ".join(f"{x['titulo'][:60]} (similitud {x['similitud']:.2f}, {x['estado']}{', Killer: ' + x['decisionKiller'] if x.get('decisionKiller') else ''})" for x in semejantes[:3]) + (". Repite casi literalmente una hipótesis ya descartada." if resultado == "falla" else ". El juez decide si es la misma hipótesis con otras palabras.")})
    # Riesgo de sesgo por instrumento (RoB 2, ROBINS-I, QUADAS-2, ROBIS, SYRCLE):
    # el modelo responde las preguntas de senalizacion de cada fuente primaria y
    # el veredicto lo pone la regla del instrumento. Sustituye al juicio libre.
    await _evaluar_sesgo_fuentes(ctx, h, pista)
    deterministas = [c for c in deterministas if c["comprobacion"] != "sesgo_evidencia"] + [SESGO.comprobacion_sesgo(_fuentes_de_hipotesis(ctx, h))]
    # El comprobador de supuestos causales entra como una comprobacion mas: si
    # la identificacion no cierra, direccion_causal queda "no comprobable" con
    # los supuestos que faltan (el juez o un experimento los resuelven).
    if not any(c["comprobacion"] == "direccion_causal" for c in deterministas):
        indep_previa = next((c["resultado"] for c in deterministas if c["comprobacion"] == "independencia_cohortes"), None)
        grafo_previo = CAUSAL.grafo_local(h, [], True if indep_previa == "pasa" else False if indep_previa == "falla" else None, P.ahora_ms())
        if grafo_previo["identificacion"] == "identificable":
            deterministas.append({"comprobacion": "direccion_causal", "resultado": "pasa", "detalle": "Identificación por regla: " + "; ".join(grafo_previo["supuestosCumplidos"])[:300]})
        elif grafo_previo["identificacion"] in ("acotado", "sin_resolver"):
            deterministas.append({"comprobacion": "direccion_causal", "resultado": "no_comprobable", "detalle": f"Identificación {grafo_previo['identificacion']}: faltan " + "; ".join(grafo_previo["supuestosFaltantes"])[:300]})
    afs_texto = "\n".join(f"- [{a['veredicto']}, {a['tipo']}, clase {a.get('clase', 'literatura')}{', SINTÉTICO' if a.get('sintetico') else ''}{', EN CONTRA de la hipótesis' if a.get('relacion') == 'contradice' else (', apoyo indirecto' if a.get('relacion') == 'apoya_indirecta' else '')}{', cohorte ' + a['cohorte'] if a.get('cohorte') else ''}] {a['texto']} {a['cita']}" + (f"\n    Pasaje: \"{a['fragmento'][:240]}\"" if a.get("fragmento") else "") for a in h["afirmaciones"]) or "Ninguna"
    mundo_h = await T.modelo_de_mundo_para(ctx.almacen, ctx.investigacion_id, f"{h['titulo']}. {h['enunciado']}", maximo=40)
    try:
        pred = await ctx.llamar(
            "juez",
            ctx.programas.killer,
            objetivo=inv["objetivo"],
            mision=_texto_mision(inv),
            hipotesis=T.hipotesis_texto(h) + "\n" + K.texto_tarjeta(h),
            afirmaciones=afs_texto,
            supuestos="\n".join(f"- [{s['estado']}] {s['texto']} ({s['evidencia']})" for s in h["supuestos"]) or "Sin supuestos evaluados",
            modelo_de_mundo=mundo_h + "\n\nOtras hipótesis vivas:\n" + T.hipotesis_existentes([x for x in e["hipotesis"] if x["id"] != h["id"]], ctx.investigacion_id),
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
            pista.error(f"El Killer no respondió para {h['titulo'][:50]}: {str(ex)[:100]}; la hipótesis queda suspendida hasta la siguiente revisión")
        del_juez, resumen, sugerida, falta, alternativas, invalidante = [], f"El juez no respondió: {str(ex)[:120]}", "", "Repetir la revisión cuando el modelo responda", [], ""
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
        decision, motivo = "suspender", "El juez no respondió: no se puede dar por revisada"
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
            d = A.registrar_decision(e2, x, "killer_1", decision, f"[Sobre la versión {version_juzgada}; la hipótesis ya está en la {x.get('version', 1)} y se volverá a juzgar] {motivo}", quien, ahora, comprobaciones, falta)
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
            pista.nota(f"La hipótesis cambio a la versión {actual.get('version', 1)} mientras se juzgaba la {version_juzgada}: la decisión queda registrada sobre la {version_juzgada} y la nueva se juzga aparte")
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
    """Segundo método, otra familia: el cerebro defiende la hipótesis y luego
    juzga si la decisión del Killer resiste. Un desacuerdo no revierte nada:
    va a la persona con las dos posturas."""
    try:
        pred = await ctx.llamar("cerebro", ctx.programas.auditar_descarte, hipotesis=T.hipotesis_texto(h) + "\n" + K.texto_tarjeta(h), decision=f"{decision['decision']}: {decision['motivo']}", comprobaciones_fallidas="\n".join(f"- {c['comprobacion']}: {c['resultado']}. {c['detalle']}" for c in fallidas) or "ninguna", evidencia=evidencia + "\n\nSupuestos:\n" + "\n".join(f"- [{s['estado']}] {s['texto']}" for s in h["supuestos"]))
        au = pred.auditoria
        auditoria = {"quien": ctx.modelos.cerebro.model, "acuerdo": bool(au.acuerdo), "motivo": (au.motivo.strip() + (f" Mejor argumento a favor: {au.mejor_argumento_a_favor.strip()}" if not au.acuerdo else ""))[:600], "fecha": P.ahora_ms(), "comprobacionDiscutida": au.comprobacion_discutida.strip()[:80]}
    except PresupuestoAgotado:
        raise
    except Exception as ex:  # noqa: BLE001
        auditoria = {"quien": ctx.modelos.cerebro.model, "acuerdo": True, "motivo": f"El auditor no respondió: {str(ex)[:120]}", "fecha": P.ahora_ms(), "comprobacionDiscutida": ""}

    def fn(e: dict[str, Any]) -> bool:
        d = next((x for x in e.get("decisiones", []) if x["id"] == decision["id"]), None)
        if not d:
            return False
        d["auditoria"] = auditoria
        if not auditoria["acuerdo"]:
            x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
            if x:
                x["hallazgos"].append({"id": P.nuevo_id("hal"), "tipo": "conclusion_no_sigue", "resumen": "La auditoría discrepa del Killer", "razonamiento": auditoria["motivo"], "estado": "abierto", "respuestaDeRosa": None})
            A.con_evento(e, h["investigacionId"], "killer", f"Auditoría en desacuerdo con el Killer sobre '{h['titulo'][:60]}': revisa las dos posturas", f"#/investigaciones/{h['investigacionId']}/hipotesis/{h['id']}", P.ahora_ms())
        return True

    ctx.mutar(fn, "auditoria_descarte")
    if pista:
        pista.resultado(f"Auditoría del descarte de '{h['titulo'][:40]}': {'de acuerdo' if auditoria['acuerdo'] else 'EN DESACUERDO'}")


async def _reformular(ctx: Ctx, h: dict[str, Any], motivo: str, quien: str, pista: Pista | None) -> bool:
    """Versión nueva de la hipótesis que atiende el motivo. Si la política ya
    no permite reformular, se descarta en este contexto (o se propone
    descartar, según la autonomía)."""
    e = ctx.e
    texto_af, _ = T.afirmaciones_sostenidas(ctx.afirmaciones())
    if not politicas.puede_reformular(h.get("version", 1)):
        ahora = P.ahora_ms()

        def agotada(e2: dict[str, Any]) -> bool:
            x = next((y for y in e2["hipotesis"] if y["id"] == h["id"]), None)
            if not x:
                return False
            m = f"Agotó las {politicas.MAX_REFORMULACIONES} reformulaciones de la política: {motivo[:200]}"
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
            pista.resultado(f"Reformulada como versión {h.get('version', 1) + 1}: {r.titulo[:70]}" if ok else "No se pudo reformular")
        return bool(ok)
    except PresupuestoAgotado:
        raise
    except Exception as ex:  # noqa: BLE001
        if pista:
            pista.error(f"La reformulación fallo: {str(ex)[:120]}")
        return False


async def _revisar_hipotesis(ctx: Ctx, h: dict[str, Any], texto_afirmaciones: str, pista: Pista | None) -> None:
    """Revisión inicial (juez), supuestos (volumen), y el Killer con su
    decisión derivada por regla."""
    inv = ctx.inv()
    ahora = P.ahora_ms()
    try:
        pred = await ctx.llamar("juez", ctx.programas.revisar_inicial, objetivo=inv["objetivo"], hipotesis=T.hipotesis_texto(h), criterios_revision="\n".join(ctx.e["criteriosRevision"]))
        rev = pred.revision
    except PresupuestoAgotado:
        raise
    except Exception as ex:  # noqa: BLE001
        if pista:
            pista.error(f"Revisión inicial fallo para {h['titulo'][:60]}: {str(ex)[:100]}")
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
            x["hallazgos"].append({"id": P.nuevo_id("hal"), "tipo": "conclusion_no_sigue", "resumen": "La revisión inicial no la da por buena", "razonamiento": rev.resumen, "estado": "abierto", "respuestaDeRosa": None})
        for s in contradichos:
            x["hallazgos"].append({"id": P.nuevo_id("hal"), "tipo": "valor_contradice_fuente", "resumen": f"Supuesto contradicho: {s['texto'][:100]}", "razonamiento": s["evidencia"], "estado": "abierto", "respuestaDeRosa": None})
        x["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "revisor", "texto": f"Revisión inicial: {rev.resumen}", "creadoEn": ahora})
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
        pista.nota("Menos de dos hipótesis vivas: no hay torneo")
        return 0
    texto_af, _ = T.afirmaciones_sostenidas(ctx.afirmaciones())
    evidencia = (texto_af[:6000] + "\n\nModelo de mundo:\n" + await T.modelo_de_mundo_para(ctx.almacen, ctx.investigacion_id, _consulta_del_paso(ctx, inv), maximo=30))
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
        ctx.evento("ranking_cambio", f"Torneo de la iteración {ctx.numero}: {jugados} partidos", f"#/investigaciones/{ctx.investigacion_id}/ranking")
    return jugados


async def paso_hipotesis(ctx: Ctx, paso: dict[str, Any]) -> str:
    inv = ctx.inv()
    e = ctx.e
    texto_af, validas = T.afirmaciones_sostenidas(ctx.afirmaciones())
    pista = ctx.pista(paso["id"], "modelo", "Generar y revisar hipótesis", "GPT-6 Astra + Opus 5")
    nuevas_ids: list[str] = []
    vivas = sum(1 for x in e["hipotesis"] if x["investigacionId"] == ctx.investigacion_id and x["estado"] not in ("descartada",))
    if vivas >= politicas.MAX_HIPOTESIS_VIVAS_POR_MISION:
        pista.nota(f"Hay {vivas} hipótesis vivas: la política fija {politicas.MAX_HIPOTESIS_VIVAS_POR_MISION} por misión, así que no se generan nuevas hasta que se decidan algunas")
        validas = []
    if validas:
        pista.accion(f"Generando hipótesis a partir de {len(validas)} afirmaciones sostenidas y las preguntas abiertas")
        try:
            mundo = await T.modelo_de_mundo_para(ctx.almacen, ctx.investigacion_id, _consulta_del_paso(ctx, inv, texto_af[:1500]))
            pred = await ctx.llamar("cerebro", ctx.programas.hipotesis, objetivo=inv["objetivo"], configuracion=T.configuracion(inv), modelo_de_mundo=mundo, afirmaciones_sostenidas=texto_af[:12000], hipotesis_existentes=T.hipotesis_existentes(e["hipotesis"], ctx.investigacion_id) + "\n\n" + T.vivero_texto(inv), criterios_revision="\n".join(e["criteriosRevision"]))
            propuestas = list(pred.hipotesis)[: politicas.MAX_PROPUESTAS_POR_ITERACION]
        except PresupuestoAgotado:
            pista.cerrar("Presupuesto agotado antes de generar", "detenida")
            raise
        ahora = P.ahora_ms()
        fuentes = ctx.fuentes()
        existentes_titulos = {V.normalizar(h["titulo"]) for h in e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id} | {V.normalizar(t) for t in VIVERO.titulos(inv)}
        for hp in propuestas:
            if V.normalizar(hp.titulo) in existentes_titulos:
                continue
            respaldo = [validas[i - 1] for i in hp.afirmaciones if 1 <= i <= len(validas)]
            if not respaldo:
                pista.nota(f"Descartada antes de entrar: '{hp.titulo[:60]}' no cita ninguna afirmación sostenida")
                continue
            afirmaciones = [{"afirmacionId": a.get("id"), "texto": a["texto"], "cita": a["cita"], "veredicto": a["veredicto"], "motivo": a["motivo"], "entidadDistinta": a.get("entidadDistinta", False), "tipo": a["tipo"], "clase": a.get("clase", "literatura"), "sintetico": False, "cohorte": a.get("cohorte", ""), "sospechosoInyeccion": bool(a.get("sospechosoInyeccion")), "nivelMedicion": a.get("nivelMedicion", "resultado_analisis"), "n": a.get("n", ""), "comparador": a.get("comparador", ""), "efecto": a.get("efecto", ""), "incertidumbre": a.get("incertidumbre", ""), "sinResolver": list(a.get("sinResolver", [])), "trayectoria": None, "fragmento": (a.get("fragmento") or "")[:600]} for a in respaldo]
            vistas: set[str] = set()
            fuentes_h = []
            for a in respaldo:
                if a["fuenteId"] in fuentes and a["fuenteId"] + a["localizador"] not in vistas:
                    vistas.add(a["fuenteId"] + a["localizador"])
                    fuentes_h.append(_fuente_publica(fuentes[a["fuenteId"]], a))
            # Regla del 15 de septiembre: nace solo si su evidencia ya da para certeza
            # baja (dos cohortes distintas); con una sola cohorte va al vivero.
            destino, nivel_nace, motivo_nace = destino_de_propuesta(afirmaciones, fuentes_h)
            if destino == "vivero":
                semilla = VIVERO.nueva_semilla(ctx.investigacion_id, ctx.numero, ahora, hp, afirmaciones, fuentes_h, motivo_nace, ctx.corrida_id)
                ctx.mutar(lambda e2, s=semilla: VIVERO.anadir(e2, ctx.investigacion_id, s, ahora), "vivero")
                existentes_titulos.add(V.normalizar(hp.titulo))
                pista.nota(f"Al vivero, no nace todavía: '{hp.titulo[:60]}' ({motivo_nace}). Le falta: {semilla['falta'][:120]}")
                continue
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
            h["procedencia"] = P.procedencia_vacia(f"Generada en la iteración {ctx.numero} a partir de {len(respaldo)} afirmaciones sostenidas. Supuestos y novedad se comprueban a continuación.", ahora, codigo=f"programas.hipotesis(objetivo, modelo_de_mundo, afirmaciones_sostenidas[{len(validas)}])", registro=[f"iteración {ctx.numero}: generar -> {hp.titulo[:60]}"])
            h["procedencia"]["fuentes"] = fuentes_h
            h["_entidades"] = list(hp.entidades_novedad)[:6]
            h["_corridaOrigen"] = ctx.corrida_id
            ctx.mutar(lambda e2, h=h: (e2["hipotesis"].append(h), A.con_evento(e2, ctx.investigacion_id, "hipotesis_nueva", f"Hipótesis nueva en la cola: {h['titulo']}", f"#/investigaciones/{ctx.investigacion_id}/hipotesis/{h['id']}", ahora)) and True, "hipotesis_nueva")
            nuevas_ids.append(h["id"])
            existentes_titulos.add(V.normalizar(h["titulo"]))
            pista.resultado(f"Nueva: {h['titulo'][:90]}")
    else:
        pista.nota("Sin afirmaciones sostenidas: no se generan hipótesis nuevas en esta iteración")

    # Revision de las nuevas y de las humanas sin revisar.
    a_revisar = [h for h in ctx.e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id and (h["id"] in nuevas_ids or (h["origen"] == "humana" and h["ultimaRevisionAutomatica"] is None) or h.get("_revisionPedida"))]
    for h in a_revisar:
        version_antes = h.get("version", 1)
        await _revisar_hipotesis(ctx, h, texto_af[:8000], pista)

        def quitar_peticion(e2: dict[str, Any], h=h, v=version_antes) -> bool:
            x = next((y for y in e2["hipotesis"] if y["id"] == h["id"]), None)
            # Si la hipotesis cambio de version mientras se revisaba, la peticion sigue viva.
            if x and x.get("version", 1) == v:
                x.pop("_revisionPedida", None)
            return True

        ctx.mutar(quitar_peticion, "revision")
        pista.resultado(f"Revisada: {h['titulo'][:70]}")
    partidos = await _torneo(ctx, pista)
    pista.cerrar(f"{len(nuevas_ids)} hipótesis nuevas, {len(a_revisar)} revisadas, {partidos} partidos")
    return f"{len(nuevas_ids)} hipótesis nuevas en la cola, {len(a_revisar)} revisadas, {partidos} partidos de torneo"


# ---------------------------------------------------------------------------
# Novedad
# ---------------------------------------------------------------------------


async def _novedad_por_conectores(ctx: Ctx, h: dict[str, Any], genes: list[str], novedad: dict[str, Any], pista: Pista) -> list[dict[str, Any]]:
    """Las tres comprobaciones de novedad que añaden los conectores: si la
    genética humana ya vincula el gen con el Alzheimer (GWAS Catalog, ClinVar),
    si ya hay fármacos contra la diana (ChEMBL, DGIdb) y si existe un dataset
    publico para comprobar la hipótesis (GEO, CELLxGENE). Cada llamada deja su
    registro de consulta con la invariante comprobada. Una fuente que no
    responde queda como "no comprobado", nunca como "no hay"."""
    regs: list[dict[str, Any]] = []
    novedad.setdefault("genetica", {"estado": "no_comprobado", "detalle": "No comprobado todavía"})
    novedad.setdefault("farmacos", {"estado": "no_comprobado", "detalle": "No comprobado todavía"})
    novedad.setdefault("datosPublicos", {"estado": "no_comprobado", "detalle": "No comprobado todavía", "series": []})
    gen = genes[0] if genes else None
    if gen:
        reg_g, gwas = await CON.consultar("gwas_asociaciones_gen", resumen=f"GWAS Catalog: {gen}", simbolo=gen)
        reg_c, clin = await CON.consultar("clinvar_gen", resumen=f"ClinVar: {gen}", simbolo=gen)
        regs += [reg_g, reg_c]
        pista.accion(f"GWAS Catalog y ClinVar: {gen}", {"base": "GWAS Catalog v2, ClinVar", "parametros": f"gene_name={gen}", "resultados": f"{(gwas or {}).get('n_alzheimer', '?')} asociaciones AD; {(clin or {}).get('con_enfermedad', '?')} variantes ClinVar con Alzheimer"})
        fallos = [n for n, r_ in (("GWAS Catalog", reg_g), ("ClinVar", reg_c)) if r_.get("error")]
        n_ad = (gwas or {}).get("n_alzheimer", 0)
        n_cv = (clin or {}).get("con_enfermedad", 0)
        if len(fallos) == 2 or (fallos and not (n_ad or n_cv)):
            # Una fuente que no responde es "no pude comprobar", nunca "no hay".
            novedad["genetica"] = {"estado": "no_comprobado", "detalle": "No comprobado: " + " y ".join(fallos) + " no respondieron" + (f"; la que respondió no encontró vínculo" if len(fallos) == 1 else "")}
        else:
            nota_fallo = f" (no pude comprobar {fallos[0]})" if fallos else ""
            if n_ad or n_cv:
                mejor = min(((a.get("p") or 1.0) for a in (gwas or {}).get("alzheimer", [])), default=None)
                novedad["genetica"] = {"estado": "vinculo_conocido", "detalle": f"{gen}: {n_ad} asociaciones GWAS con Alzheimer" + (f" (mejor p {mejor:.1e})" if mejor else "") + f"; {n_cv} variantes en ClinVar con Alzheimer. La genética humana ya vincula el gen: la novedad tiene que estar en el mecanismo o el contexto, no en el vínculo" + nota_fallo}
            else:
                novedad["genetica"] = {"estado": "sin_vinculo", "detalle": f"{gen}: sin asociaciones GWAS con Alzheimer entre {(gwas or {}).get('total_asociaciones', 0)} registradas y sin variantes ClinVar con la enfermedad. Si la hipótesis afirma un vínculo genético, es nuevo y hay que decir por que la genética no lo vio"}
        reg_m, ids = await CON.consultar("mygene_gen", resumen=f"MyGene: {gen}", simbolo=gen)
        regs.append(reg_m)
        chembl = None
        reg_ch: dict[str, Any] = {}
        if ids and ids.get("uniprot"):
            reg_ch, chembl = await CON.consultar("chembl_diana", resumen=f"ChEMBL: {ids['uniprot']}", uniprot=ids["uniprot"])
            regs.append(reg_ch)
        reg_d, dg = await CON.consultar("dgidb_gen", resumen=f"DGIdb: {gen}", simbolo=gen)
        regs.append(reg_d)
        pista.accion(f"ChEMBL y DGIdb: {gen}", {"base": "ChEMBL, DGIdb", "parametros": f"uniprot={(ids or {}).get('uniprot')}", "resultados": f"{len((chembl or {}).get('mecanismos', []))} mecanismos; {(dg or {}).get('total', '?')} interacciones"})
        fallos_f = [n for n, r_ in (("ChEMBL", reg_ch if ids and ids.get("uniprot") else None), ("DGIdb", reg_d)) if r_ is not None and r_.get("error")]
        mecs = (chembl or {}).get("mecanismos", [])
        if reg_d.get("error") and not mecs:
            novedad["farmacos"] = {"estado": "no_comprobado", "detalle": "No comprobado: " + " y ".join(fallos_f) + " no respondieron"}
        else:
            nota_fallo_f = f" (no pude comprobar {fallos_f[0]})" if fallos_f else ""
            aprob = [x for x in (dg or {}).get("interacciones", []) if x.get("aprobado")]
            fases = [m.get("fase_maxima") for m in mecs if m.get("fase_maxima") is not None]
            if mecs or aprob:
                novedad["farmacos"] = {"estado": "farmacos_existentes", "detalle": f"{gen}: {len(mecs)} mecanismos de acción en ChEMBL" + (f" (fase máxima {max(fases)})" if fases else "") + f"; {len(aprob)} fármacos aprobados con interacción en DGIdb" + (": " + ", ".join(str(x.get('farmaco')) for x in aprob[:4]) if aprob else "") + ". La diana es abordable; una hipótesis de intervención puede reposicionar" + nota_fallo_f}
            else:
                novedad["farmacos"] = {"estado": "sin_farmacos", "detalle": f"{gen}: sin mecanismos en ChEMBL ni fármacos con interacción en DGIdb. Si la hipótesis propone intervenir, no hay herramienta farmacológica lista" + nota_fallo_f}
    bio = ((h.get("comprobacion") or {}).get("biomarcador") or (h.get("tarjeta") or {}).get("diana") or gen or "").strip()
    if bio:
        reg_geo, geo = await CON.consultar("geo_series", resumen=f"GEO: Alzheimer {bio}", terminos=f"Alzheimer {bio}")
        reg_cx, cx = await CON.consultar("cellxgene_colecciones", resumen="CELLxGENE: Alzheimer", termino="Alzheimer")
        regs += [reg_geo, reg_cx]
        pista.accion(f"GEO y CELLxGENE: {bio}", {"base": "GEO gds, CELLxGENE Discover", "parametros": f"Alzheimer {bio}", "resultados": f"{(geo or {}).get('total', '?')} series GEO; {reg_cx.get('n') if cx is not None else '?'} colecciones"})
        fallos_d = [n for n, r_ in (("GEO", reg_geo), ("CELLxGENE", reg_cx)) if r_.get("error")]
        series = [{"accession": s_["accession"], "titulo": s_["titulo"], "n": s_.get("n_muestras"), "plataforma": s_.get("plataforma")} for s_ in (geo or {}).get("series", [])[:5]]
        n_geo = (geo or {}).get("total", 0)
        n_cx = (reg_cx.get("n") or 0) if not reg_cx.get("error") else 0
        if len(fallos_d) == 2 or (fallos_d and not (n_geo or n_cx)):
            novedad["datosPublicos"] = {"estado": "no_comprobado", "detalle": "No comprobado: " + " y ".join(fallos_d) + " no respondieron", "series": []}
        else:
            nota_fallo_d = f" (no pude comprobar {fallos_d[0]})" if fallos_d else ""
            if n_geo or n_cx:
                novedad["datosPublicos"] = {"estado": "hay_datos", "detalle": f"{n_geo} series GEO humanas con 'Alzheimer {bio}' y {n_cx} colecciones de célula única con Alzheimer en CELLxGENE: la hipótesis se puede empezar a comprobar in silico sin pedir datos" + nota_fallo_d, "series": series}
            else:
                novedad["datosPublicos"] = {"estado": "sin_datos", "detalle": f"Ninguna serie GEO humana con 'Alzheimer {bio}' ni colección CELLxGENE: comprobarla exige datos propios o del laboratorio", "series": []}
    return regs


ALIAS_GEN = {"NFL": "NEFL", "NF-L": "NEFL", "P-TAU": "MAPT", "PTAU": "MAPT", "P-TAU181": "MAPT", "P-TAU217": "MAPT", "TAU": "MAPT", "ABETA": "APP", "AB42": "APP", "AB40": "APP", "APOE4": "APOE", "APOE-E4": "APOE", "TREM-2": "TREM2"}
NO_GEN = {"PET", "MCI", "MMSE", "CDR", "CSF", "LCR", "ADNI", "AD", "EA", "IC", "CI", "HR", "OR", "SD", "DE", "RNA", "DNA", "ARN", "ADN", "ELISA", "SIMOA", "MRI", "RM", "TC", "MR", "NCT", "GEO", "GSE", "UK", "USA", "EE", "UU", "BIOFINDER", "AIBL", "WRAP", "ROSMAP", "MSBB", "MAYO", "SEA", "MAP", "ROS", "CA1", "CA3", "IADG", "UP", "DOWN", "GWAS", "SNP", "QTL", "TPM", "NTPM", "FDR", "ANOVA", "AUC", "ROC", "BIOCARD", "PREVENT", "DIAN", "A4", "ATN", "ANA", "VS"}


def simbolos_de_genes(texto: str) -> list[str]:
    """Candidatos a símbolo de gen en un texto libre: tokens en mayúsculas de 2
    a 10 caracteres, con alias del dominio (NfL a NEFL, p-tau a MAPT, Abeta a
    APP) y una lista de siglas que no son genes. MyGene decide después cual
    resuelve de verdad."""
    vistos: list[str] = []
    for bruto in re.findall(r"[A-Za-z][A-Za-z0-9\-\u03b5]{1,14}", texto or ""):
        bruto = bruto.replace("\u03b5", "E")
        # Un alias compuesto (p-tau181, NF-L) se resuelve entero; si no, se separa por guion (GFAP-NfL).
        partes = [bruto] if bruto.upper() in ALIAS_GEN else bruto.split("-")
        for tok in partes:
            t = ALIAS_GEN.get(tok.upper(), tok.upper())
            if not t or t in NO_GEN or t in vistos or not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", t):
                continue
            if not (tok.isupper() or tok.upper() in ALIAS_GEN or re.search(r"\d", tok)):
                continue  # palabras normales en minusculas no cuentan
            vistos.append(t)
    return vistos[:6]


async def contexto_de_bases(ctx: Ctx, h: dict[str, Any], pista: Pista | None) -> None:
    """El contexto de la diana desde las bases: identificadores (MyGene),
    funcion (UniProt), expresion en cerebro (Human Protein Atlas), interactores
    (STRING) y rutas (Reactome). Se calcula una vez por hipotesis y version, y
    se ensena en la tarjeta. El Killer usa los identificadores en la
    comprobacion `identificadores_resuelven`."""
    diana = ((h.get("tarjeta") or {}).get("diana") or "").strip()
    if (h.get("contextoBases") or {}).get("version") == h.get("version", 1):
        return
    candidatos = simbolos_de_genes(" ".join([diana, (h.get("comprobacion") or {}).get("biomarcador") or "", h.get("titulo", "")]))
    if not diana and not candidatos:
        return
    regs: list[dict[str, Any]] = []
    ctxb: dict[str, Any] = {"diana": diana or ", ".join(candidatos[:3]), "identificadores": {}, "funcion": "", "expresionCerebro": "", "interactores": [], "rutas": [], "version": h.get("version", 1), "consultadoEn": P.ahora_ms(), "candidatos": candidatos[:5]}
    ids = None
    simbolo = ""
    for cand in candidatos[:3]:
        reg, ids = await CON.consultar("mygene_gen", resumen=f"MyGene: {cand}", simbolo=cand)
        regs.append(reg)
        if ids and ids.get("ensembl"):
            simbolo = cand
            break
        ids = None
    if simbolo:
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
        pista.accion(f"Bases para {simbolo or diana[:30] or 'la diana'}", {"base": "MyGene, UniProt, HPA, STRING, Reactome", "parametros": ", ".join(candidatos[:3]) or diana[:40], "resultados": f"Ensembl {ctxb['identificadores'].get('ensembl') or 'ningún candidato resuelve'}; {len(ctxb['interactores'])} interactores; {len(ctxb['rutas'])} rutas"})

    def aplicar(e: dict[str, Any]) -> bool:
        x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
        if not x:
            return False
        x["contextoBases"] = ctxb
        x.setdefault("consultas", []).extend(regs)
        return True

    ctx.mutar(aplicar, "contexto_bases")


async def paso_novedad(ctx: Ctx, paso: dict[str, Any]) -> str:
    pendientes = [h for h in ctx.e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id and h["estado"] not in ("descartada",) and (h["novedad"]["precedente"]["detalle"].startswith("No comprobado") or (h["novedad"].get("genetica") or {}).get("estado") == "no_comprobado")]
    if not pendientes:
        return "Todas las hipótesis tienen la novedad comprobada"
    pista = ctx.pista(paso["id"], "novedad", f"Novedad de {len(pendientes)} hipótesis", "Open Targets, ClinicalTrials.gov, OpenAlex")
    for h in pendientes[:6]:
        if pista.detenida():
            break
        entidades = h.get("_entidades") or T.terminos_clave(h["titulo"], maximo=4)
        novedad = {k: dict(v) for k, v in h["novedad"].items()}
        # Open Targets: genes o proteinas.
        genes = [x for x in entidades if re.fullmatch(r"[A-Z][A-Z0-9\-]{1,9}", x) and x not in NO_GEN] or simbolos_de_genes(" ".join([h["titulo"], ((h.get("tarjeta") or {}).get("diana") or ""), ((h.get("comprobacion") or {}).get("biomarcador") or "")]))
        detalles = []
        for g in genes[:3]:
            try:
                r = await opentargets.asociacion_alzheimer(g)
                pista.accion(f"Open Targets: {g}", {"base": "Open Targets GraphQL", "parametros": f"search({g}) + target.associatedDiseases(MONDO_0004975)", "resultados": f"{r.get('puntuacion')}"})
                if not r["encontrado"]:
                    detalles.append(f"{g}: no es una diana en Open Targets")
                elif r["puntuacion"] is None:
                    detalles.append(f"{g}: diana sin asociación registrada con Alzheimer")
                else:
                    detalles.append(f"{g}: asociación {r['puntuacion']} (" + ", ".join(f"{k} {v}" for k, v in r["tipos"].items()) + ")")
            except FuenteNoDisponible as ex:
                detalles.append(f"{g}: Open Targets no respondió ({str(ex)[:60]}); no se afirma ausencia")
        if genes:
            def _punt(d: str) -> float:
                m_ = re.search(r"asociacion ([0-9]+(?:\.[0-9]+)?)", d)
                return float(m_.group(1)) if m_ else 0.0

            con_asociacion = any(_punt(d) >= 0.3 for d in detalles)
            if detalles and all("no respondió" in d.lower() or "no pude" in d.lower() for d in detalles):
                novedad["openTargets"] = {"estado": "no_comprobado", "detalle": "No comprobado: Open Targets no respondió para " + "; ".join(detalles)[:200]}
                detalles = None
            if detalles is not None:
                novedad["openTargets"] = {"estado": "evidencia_previa" if con_asociacion else "sin_evidencia", "detalle": "; ".join(detalles)}
        else:
            novedad["openTargets"] = {"estado": "sin_evidencia", "detalle": "No aplica: la hipótesis no nombra una diana molecular"}
        # ClinicalTrials.gov.
        try:
            termino = " ".join(T.terminos_clave(h["titulo"] + " " + h["comprobacion"]["biomarcador"], maximo=3))
            estudios, total = await clinicaltrials.buscar("Alzheimer Disease", termino=termino, maximo=5)
            pista.accion(f"ClinicalTrials.gov: {termino}", {"base": "ClinicalTrials.gov v2", "parametros": f"query.cond=Alzheimer Disease&query.term={termino}", "resultados": f"{total}"})
            if total > 0:
                novedad["ensayos"] = {"estado": "ensayo_existente", "detalle": f"{total} ensayos con esos términos; el más cercano: {estudios[0]['nct']} ({estudios[0]['titulo'][:80]}). Hay que leer si mide lo mismo.", "nct": estudios[0]["nct"]}
            else:
                novedad["ensayos"] = {"estado": "sin_ensayo", "detalle": f"Ningún ensayo registrado con: {termino}", "nct": None}
        except FuenteNoDisponible as ex:
            novedad["ensayos"] = {"estado": "no_comprobado", "detalle": f"No comprobado: ClinicalTrials.gov no respondio ({str(ex)[:60]})", "nct": None}
        # Precedente en literatura (OpenAlex) con cribado del modelo.
        try:
            termino = " ".join(T.terminos_clave(h["titulo"], maximo=4))
            obras, total, coste = await openalex.buscar(termino, maximo=6)
            pista.accion(f"OpenAlex: {termino}", {"base": "OpenAlex", "parametros": f"filter=title_and_abstract.search:{termino}", "resultados": f"{total} obras, {coste} USD"})
            candidatas = list(obras[:5])
            if exa.disponible():
                # Por significado, con el enunciado entero: la pregunta de novedad
                # difícil es "¿alguien ya propuso esto con otras palabras?".
                try:
                    # Solo lo publicado antes de que Rosa propusiera la hipótesis: la
                    # novedad honesta, también cuando se vuelve a juzgar meses después.
                    obras_exa, n_exa, coste_exa = await exa.buscar(h["enunciado"][:600], maximo=6, pregunta_pasajes=h["enunciado"][:500], hasta_fecha=fecha_iso_de_ms(h.get("creadaEn")))
                    pista.accion("Exa: enunciado completo", {"base": "Exa", "parametros": "category=publication&numResults=6&endPublishedDate=creación de la hipótesis&highlights.query=enunciado", "resultados": f"{n_exa} documentos, {coste_exa:.4f} USD"})
                    _anotar_coste_exa(ctx, coste_exa)
                    vistos = {o.get("doi") for o in candidatas if o.get("doi")}
                    candidatas.extend(o for o in obras_exa[:5] if not (o.get("doi") and o["doi"] in vistos))
                    total += n_exa
                except FuenteNoDisponible as ex:
                    pista.nota(f"Exa no respondió: {str(ex)[:80]}; la novedad se comprueba solo con OpenAlex")
            candidatas, _fuera = await cortar_con_reranker(f"Alguien ya propuso o demostró esto: {h['enunciado']}", [o for o in candidatas if o.get("titulo")], pista, maximo=5)
            mejor = 0
            mejor_ref = ""
            for o in candidatas:
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
                novedad["precedente"] = {"estado": "ya_publicado", "detalle": f"Ya publicado o muy cercano: {mejor_ref} (puntuación {mejor}/10)"}
            elif mejor >= 5:
                novedad["precedente"] = {"estado": "parcial", "detalle": f"Precedente parcial: {mejor_ref} (puntuación {mejor}/10)"}
            else:
                novedad["precedente"] = {"estado": "sin_precedente", "detalle": f"Sin precedente claro entre {total} obras que casan con: {termino}"}
        except FuenteNoDisponible as ex:
            novedad["precedente"] = {"estado": "no_comprobado", "detalle": f"No comprobado: OpenAlex no respondió ({str(ex)[:60]})"}

        # Patentes y financiación (Exa): una idea ya protegida o ya financiada no es nueva.
        await _novedad_exa_dominios(ctx, h, pista, novedad, "patentes", exa.DOMINIOS_PATENTES, "Alguien ya patentó o reivindicó esto", ("patente_relacionada", "parcial", "sin_patente"), "patentes")
        await _novedad_exa_dominios(ctx, h, pista, novedad, "financiacion", exa.DOMINIOS_FINANCIACION, "Alguien ya financió un proyecto para comprobar esto", ("proyecto_financiado", "parcial", "sin_proyecto"), "convocatorias y proyectos financiados")

        # Conectores: genetica humana, farmacos y datos publicos para la misma diana.
        consultas = await _novedad_por_conectores(ctx, h, genes[:1], novedad, pista)

        def aplicar(e: dict[str, Any], h=h, novedad=novedad, consultas=consultas) -> bool:
            x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
            if not x:
                return False
            x["novedad"] = novedad
            x.setdefault("consultas", []).extend(consultas)
            if x.get("decisionKiller") == "suspender":
                # El Killer la suspendio antes de tener la novedad: hay que volver a juzgarla.
                x["_revisionPedida"] = True
            x["procedencia"]["registro"].append(f"iteración {ctx.numero}: novedad -> Open Targets {novedad['openTargets']['estado']}, ensayos {novedad['ensayos']['estado']}, precedente {novedad['precedente']['estado']}, genética {novedad.get('genetica', {}).get('estado')}, fármacos {novedad.get('farmacos', {}).get('estado')}, datos públicos {novedad.get('datosPublicos', {}).get('estado')}")
            return True

        ctx.mutar(aplicar, "novedad")
        pista.resultado(f"{h['titulo'][:60]}: precedente {novedad['precedente']['estado']}, ensayos {novedad['ensayos']['estado']}, Open Targets {novedad['openTargets']['estado']}")
    pista.cerrar(f"Novedad comprobada en {min(len(pendientes), 6)} hipótesis")
    return f"Novedad comprobada en {min(len(pendientes), 6)} hipótesis"


# ---------------------------------------------------------------------------
# Meta-revision y panorama
# ---------------------------------------------------------------------------


async def paso_meta(ctx: Ctx, paso: dict[str, Any]) -> str:
    inv = ctx.inv()
    e = ctx.e
    propias = [h for h in e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id]
    pista = ctx.pista(paso["id"], "modelo", "Meta-revisión y panorama", "GPT-6 Astra")
    if not propias:
        pista.cerrar("Sin hipótesis: no hay meta-revisión")
        return "Sin hipótesis que meta-revisar"
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


def _cerrar_analisis_fallido(e: dict[str, Any], hipotesis_id: str) -> bool:
    """Un análisis que reventó por excepción: se quita la petición y las
    ejecuciones en curso de la hipótesis pasan a error técnico."""
    x = next((y for y in e["hipotesis"] if y["id"] == hipotesis_id), None)
    if x:
        x.pop("_analisisPedido", None)
    for r in e.get("ejecuciones", []):
        if r.get("hipotesisId") == hipotesis_id and r.get("estado") == "en_curso":
            r["estado"] = "error_tecnico"
            r["error"] = (r.get("error") or "") + " Interrumpida por una excepción del paso de análisis."
    return True


async def paso_analisis(ctx: Ctx, paso: dict[str, Any]) -> str:
    """Primero las reproducciones pendientes de la puerta; después los
    análisis que pidió la persona; después, si la autonomía lo permite, un
    análisis por hipótesis que el Killer dejo avanzar y aún no tiene datos,
    sobre el primer dataset aprobado. Todo dentro de las políticas."""
    from rosa.bucle import analisis as AN

    e = ctx.e
    inv = ctx.inv()
    datasets_ok = [d for d in inv.get("datasets", []) if d["estado"] == "aprobado" and (d.get("procedencia") or {}).get("hash")]
    pista = ctx.pista(paso["id"], "modelo", "Análisis in silico", "Sandbox + GPT-6 Astra + Opus 5")
    hechos = 0
    for rep in [r for r in e.get("reproducciones", []) if r["investigacionId"] == ctx.investigacion_id and r["estado"] == "pendiente"][:3]:
        try:
            await AN.reproducir(ctx, rep, pista)
        except PresupuestoAgotado:
            raise
        except Exception as ex:  # noqa: BLE001
            traceback.print_exc()
            pista.error(f"La reproducción {rep['referencia'][:40]} fallo: {str(ex)[:120]}")
            ctx.mutar(lambda e2, rep=rep, ex=ex: AN._estado_rep(e2, rep["id"], "error_tecnico", None, None, f"{type(ex).__name__}: {str(ex)[:200]}"), "reproduccion")
        hechos += 1
    if not datasets_ok:
        pista.cerrar("Sin datasets aprobados con fichero: no hay análisis que hacer" + (f"; {hechos} reproducciones" if hechos else ""))
        return "Sin datasets aprobados con fichero"
    pedidos = [h for h in e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id and h.get("_analisisPedido")]
    for h in pedidos:
        p = h["_analisisPedido"]
        try:
            await AN.analizar_hipotesis(ctx, h, p["datasetId"], p.get("pregunta", ""), pista)
        except PresupuestoAgotado:
            raise
        except Exception as ex:  # noqa: BLE001
            traceback.print_exc()
            pista.error(f"El análisis pedido de {h['titulo'][:40]} fallo: {str(ex)[:120]}")
            ctx.mutar(lambda e2, h=h: _cerrar_analisis_fallido(e2, h["id"]), "analisis")
        hechos += 1
    if e["autonomia"].get("correr_analisis") == "actuar":
        candidatas = [h for h in e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id and h.get("decisionKiller") == "avanzar" and not h.get("ejecuciones") and h["estado"] not in ("descartada",) and (h.get("tarjeta") or {}).get("prediccionFalsable")]
        for h in sorted(candidatas, key=lambda x: -x["elo"])[:2]:
            if pista.detenida():
                break
            try:
                await AN.analizar_hipotesis(ctx, h, datasets_ok[0]["id"], "", pista)
            except PresupuestoAgotado:
                raise
            except Exception as ex:  # noqa: BLE001
                traceback.print_exc()
                pista.error(f"El análisis de {h['titulo'][:40]} fallo: {str(ex)[:120]}")
                ctx.mutar(lambda e2, h=h: _cerrar_analisis_fallido(e2, h["id"]), "analisis")
            hechos += 1
    pista.cerrar(f"{hechos} análisis o reproducciones")
    return f"{hechos} análisis in silico o reproducciones ejecutados"


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
