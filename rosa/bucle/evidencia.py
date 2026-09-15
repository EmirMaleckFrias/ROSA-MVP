"""Acumulación de evidencia: lo que Rosa lee en cada iteración vuelve a las
hipótesis que ya existen.

Hasta el 15 de septiembre de 2026 una hipótesis nacía con las afirmaciones y
fuentes que la motivaron y ahí se quedaba: sus afirmaciones solo crecían con
un resultado de laboratorio o un análisis in silico, y sus fuentes (de donde
se cuentan las cohortes distintas) se fijaban una sola vez. La conclusión se
rehacía al cerrar cada iteración, pero sobre la misma evidencia, así que no
cambiaba. Por eso todas las hipótesis se quedaban en certeza muy baja.

Al cerrar cada iteración, para cada hipótesis viva:

1. Candidatas: las afirmaciones sostenidas o parciales de esta iteración que
   más se parecen a la hipótesis (embeddings por el gateway y coseno; sin
   embeddings, por términos clave compartidos), quitando las que ya tiene,
   las de otra entidad y las sospechosas de inyección.
2. Relación: un modelo de volumen decide, por población, marcador y sentido,
   si cada candidata la apoya, la apoya de forma indirecta, la contradice o no
   habla de ella (`AsignarEvidencia`). En la duda, fuera.
3. Se añaden las aceptadas con su cita, su cohorte, su relación y la
   iteración; la fuente entra en la procedencia de la hipótesis (y con ella
   su cohorte, que es lo que sube el techo de certeza); queda una línea en el
   registro de procedencia y un evento; y la conclusión se rehace.

Nunca inventa: solo enlaza afirmaciones ya verificadas, con su cita literal.
"""

from __future__ import annotations

import traceback
from typing import Any

import numpy as np

from rosa import certeza as CERTEZA
from rosa import indice_semantico
from rosa import politicas
from rosa import killer as K
from rosa import vigilancia
from rosa.bucle import contexto as T
from rosa.estado import acciones as A
from rosa.estado import plantilla as P

MAX_CANDIDATAS_POR_HIPOTESIS = 8
UMBRAL_SIMILITUD = 0.30
MAX_HIPOTESIS_POR_CIERRE = 20
RELACIONES_QUE_CUENTAN = ("apoya", "apoya_indirecta", "contradice")


class PresupuestoAgotadoEvidencia(Exception):
    pass


def _texto_h(h: dict[str, Any]) -> str:
    return f"{h.get('titulo', '')}. {h.get('enunciado', '')}"


def _texto_a(a: dict[str, Any]) -> str:
    return f"{a.get('texto', '')} {a.get('fragmento', '')[:300] if a.get('fragmento') else ''}".strip()


def afirmaciones_nuevas(corrida: dict[str, Any], iteracion: int) -> list[dict[str, Any]]:
    """Las afirmaciones de esta iteración que pueden ser evidencia: sostenidas
    o parciales, con fuente, de la entidad correcta y sin sospecha de inyección."""
    return [
        a for a in corrida.get("_afirmaciones", [])
        if a.get("iteracion") == iteracion and a.get("veredicto") in ("sostenida", "parcial") and a.get("fuenteId")
        and not a.get("entidadDistinta") and not a.get("sospechosoInyeccion") and not a.get("sintetico") and (a.get("texto") or "").strip()
    ]


def _ya_tiene(h: dict[str, Any], a: dict[str, Any]) -> bool:
    ids = {x.get("afirmacionId") for x in h.get("afirmaciones", []) if x.get("afirmacionId")}
    textos = {(x.get("texto") or "").strip().lower() for x in h.get("afirmaciones", [])}
    return a.get("id") in ids or (a.get("texto") or "").strip().lower() in textos


def candidatas_por_terminos(h: dict[str, Any], afs: list[dict[str, Any]]) -> list[tuple[dict[str, Any], float]]:
    """Sin embeddings: las afirmaciones que nombran los términos clave de la
    hipótesis (siglas, genes, biomarcadores), con la misma exigencia que la
    vigilancia: dos términos si la hipótesis tiene tres o más, uno si no."""
    terminos = vigilancia.terminos_de(h)
    if not terminos:
        return []
    exigidos = 2 if len(terminos) >= 3 else 1
    salida = []
    for a in afs:
        hallados = vigilancia.coincidencias(terminos, _texto_a(a))
        if len(hallados) >= exigidos:
            salida.append((a, round(len(hallados) / len(terminos), 3)))
    salida.sort(key=lambda x: -x[1])
    return salida[:MAX_CANDIDATAS_POR_HIPOTESIS]


async def candidatas_por_parecido(vivas: list[dict[str, Any]], afs: list[dict[str, Any]]) -> dict[str, list[tuple[dict[str, Any], float]]]:
    """Con embeddings: coseno entre cada hipótesis y cada afirmación; por
    hipótesis, las mejores por encima del umbral."""
    vectores, _ = await indice_semantico.incrustar([_texto_h(h) for h in vivas] + [_texto_a(a) for a in afs])
    m = np.asarray(vectores, dtype=np.float32)
    normas = np.linalg.norm(m, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    m = m / normas
    hs, xs = m[: len(vivas)], m[len(vivas):]
    sims = hs @ xs.T
    salida: dict[str, list[tuple[dict[str, Any], float]]] = {}
    for i, h in enumerate(vivas):
        orden = np.argsort(-sims[i])
        pares = [(afs[int(j)], round(float(sims[i, int(j)]), 4)) for j in orden if float(sims[i, int(j)]) >= UMBRAL_SIMILITUD]
        salida[h["id"]] = pares[:MAX_CANDIDATAS_POR_HIPOTESIS]
    return salida


async def elegir_candidatas(vivas: list[dict[str, Any]], afs: list[dict[str, Any]], pista: Any = None) -> dict[str, list[tuple[dict[str, Any], float]]]:
    if indice_semantico.disponible():
        try:
            return await candidatas_por_parecido(vivas, afs)
        except Exception as ex:  # noqa: BLE001  sin embeddings se sigue por términos
            if pista:
                pista.nota(f"Embeddings no disponibles ({type(ex).__name__}); candidatas por términos clave")
    return {h["id"]: candidatas_por_terminos(h, afs) for h in vivas}


def _entrada(a: dict[str, Any], relacion: str, motivo: str, iteracion: int) -> dict[str, Any]:
    """La afirmación tal como la guarda la hipótesis: la misma forma que al
    nacer, más la relación y la iteración en que llegó."""
    return {
        "afirmacionId": a.get("id"), "texto": a["texto"], "cita": a["cita"], "veredicto": a["veredicto"], "motivo": a.get("motivo", ""),
        "entidadDistinta": False, "tipo": a.get("tipo", "dato"), "clase": a.get("clase", "literatura"), "sintetico": False, "cohorte": a.get("cohorte", ""),
        "sospechosoInyeccion": bool(a.get("sospechosoInyeccion")), "nivelMedicion": a.get("nivelMedicion", "resultado_analisis"), "n": a.get("n", ""),
        "comparador": a.get("comparador", ""), "efecto": a.get("efecto", ""), "incertidumbre": a.get("incertidumbre", ""), "sinResolver": list(a.get("sinResolver", [])),
        "trayectoria": None, "fragmento": (a.get("fragmento") or "")[:600], "relacion": relacion, "motivoRelacion": motivo[:300], "iteracion": iteracion,
    }


async def acumular(ctx: Any, iteracion: int, pista: Any = None) -> dict[str, Any]:
    """Una pasada al cerrar la iteración. Devuelve {hipotesis, candidatas,
    anadidas, enContra, ids} con los ids de las hipótesis que ganaron evidencia."""
    from rosa.bucle.pasos import PresupuestoAgotado, _fuente_publica

    resumen: dict[str, Any] = {"hipotesis": 0, "candidatas": 0, "anadidas": 0, "enContra": 0, "ids": []}
    e = ctx.e
    corrida = ctx.corrida()
    afs = afirmaciones_nuevas(corrida, iteracion)
    vivas = sorted([h for h in e["hipotesis"] if h["investigacionId"] == ctx.investigacion_id and h["estado"] not in ("descartada",)], key=lambda h: -h.get("elo", 0))[:MAX_HIPOTESIS_POR_CIERRE]
    if not afs or not vivas:
        if pista:
            pista.cerrar("Sin afirmaciones nuevas o sin hipótesis vivas: nada que acumular")
        return resumen
    resumen["hipotesis"] = len(vivas)
    candidatas = await elegir_candidatas(vivas, afs, pista)
    fuentes = ctx.fuentes()
    for h in vivas:
        cands = [(a, s) for a, s in candidatas.get(h["id"], []) if not _ya_tiene(h, a)]
        if not cands:
            continue
        resumen["candidatas"] += len(cands)
        lista = "\n".join(f"{i + 1}. [{a['veredicto']}, {a.get('tipo', 'dato')}{', cohorte ' + a['cohorte'] if a.get('cohorte') else ''}] {a['texto']} {a['cita']}" for i, (a, _) in enumerate(cands))
        try:
            pred = await ctx.llamar("volumen", ctx.programas.asignar_evidencia, hipotesis=T.hipotesis_texto(h), afirmaciones=K.como_dato(lista))
        except PresupuestoAgotado:
            raise
        except Exception:  # noqa: BLE001  una hipótesis que falla no tumba las demás
            traceback.print_exc()
            continue
        aceptadas: list[tuple[dict[str, Any], str, str]] = []
        for r in list(getattr(pred, "relaciones", []) or []):
            indice, relacion, motivo = getattr(r, "indice", 0), getattr(r, "relacion", ""), getattr(r, "motivo", "") or ""
            if 1 <= int(indice) <= len(cands) and relacion in RELACIONES_QUE_CUENTAN:
                aceptadas.append((cands[int(indice) - 1][0], relacion, motivo))
        if not aceptadas:
            continue
        ahora = P.ahora_ms()

        def fn(e2: dict[str, Any], h=h, aceptadas=aceptadas, ahora=ahora) -> bool:
            y = next((z for z in e2["hipotesis"] if z["id"] == h["id"]), None)
            if not y:
                return False
            ids_fuentes = {f["id"] for f in y["procedencia"]["fuentes"]}
            nuevas_fuentes = 0
            for a, relacion, motivo in aceptadas:
                y["afirmaciones"].append(_entrada(a, relacion, motivo, iteracion))
                f = fuentes.get(a["fuenteId"])
                if f and a["fuenteId"] not in ids_fuentes:
                    y["procedencia"]["fuentes"].append(_fuente_publica(f, a))
                    ids_fuentes.add(a["fuenteId"])
                    nuevas_fuentes += 1
            en_contra = sum(1 for _, r, _ in aceptadas if r == "contradice")
            indirectas = sum(1 for _, r, _ in aceptadas if r == "apoya_indirecta")
            y["procedencia"]["registro"].append(f"Iteración {iteracion}: {len(aceptadas)} afirmaciones nuevas enlazadas ({len(aceptadas) - en_contra - indirectas} a favor, {indirectas} indirectas, {en_contra} en contra), {nuevas_fuentes} fuentes nuevas")
            y["_evidenciaNueva"] = iteracion
            y.pop("_conclusionIntentada", None)
            A.recalcular_bloqueos(e2, y)
            texto = f"Evidencia nueva para «{y['titulo'][:60]}»: {len(aceptadas)} afirmaciones" + (f", {en_contra} en contra" if en_contra else "") + (f", {nuevas_fuentes} fuentes nuevas" if nuevas_fuentes else "")
            A.con_evento(e2, y["investigacionId"], "revision_automatica", texto, f"#/investigaciones/{y['investigacionId']}/hipotesis/{y['id']}", ahora)
            return True

        ctx.mutar(fn, "evidencia_acumulada")
        resumen["anadidas"] += len(aceptadas)
        resumen["enContra"] += sum(1 for _, r, _ in aceptadas if r == "contradice")
        resumen["ids"].append(h["id"])
        if pista:
            pista.resultado(f"{h['titulo'][:60]}: {len(aceptadas)} afirmaciones nuevas")
    if pista:
        pista.cerrar(f"{resumen['anadidas']} afirmaciones enlazadas a {len(resumen['ids'])} hipótesis ({resumen['enContra']} en contra) de {resumen['candidatas']} candidatas" if resumen["anadidas"] else f"{resumen['candidatas']} candidatas, ninguna pertinente")
    return resumen


def _texto_semilla(s: dict[str, Any]) -> str:
    c = s.get("comprobacion") or {}
    return f"Título: {s['titulo']}\nEnunciado: {s['enunciado']}\nMecanismo: {s.get('mecanismo', '')}\nComprobación: biomarcador {c.get('biomarcador', '')}; cohorte {c.get('cohorte', '')}; diseño {c.get('diseno', '')}"


async def acumular_vivero(ctx: Any, iteracion: int, pista: Any = None) -> dict[str, Any]:
    """La misma acumulación sobre las ideas del vivero: las que llegan al
    listón (certeza baja por regla) nacen como hipótesis; las que llevan
    demasiadas iteraciones sin ganar nada se retiran con su motivo."""
    from rosa.bucle import vivero as VIVERO
    from rosa.bucle.pasos import PresupuestoAgotado, _fuente_publica

    resumen: dict[str, Any] = {"semillas": 0, "anadidas": 0, "nacidas": [], "retiradas": []}
    semillas = [dict(x) for x in (ctx.inv().get("vivero") or [])]
    if not semillas:
        return resumen
    resumen["semillas"] = len(semillas)
    afs = afirmaciones_nuevas(ctx.corrida(), iteracion)
    pseudo = [VIVERO.como_hipotesis(x) for x in semillas]
    candidatas = await elegir_candidatas(pseudo, afs, pista) if afs else {}
    fuentes = ctx.fuentes()
    for s_, ph in zip(semillas, pseudo):
        cands = [(a, sc) for a, sc in candidatas.get(s_["id"], []) if not _ya_tiene(ph, a)]
        aceptadas: list[tuple[dict[str, Any], str, str]] = []
        if cands:
            lista = "\n".join(f"{i + 1}. [{a['veredicto']}, {a.get('tipo', 'dato')}{', cohorte ' + a['cohorte'] if a.get('cohorte') else ''}] {a['texto']} {a['cita']}" for i, (a, _) in enumerate(cands))
            try:
                pred = await ctx.llamar("volumen", ctx.programas.asignar_evidencia, hipotesis=_texto_semilla(s_), afirmaciones=K.como_dato(lista))
                for r in list(getattr(pred, "relaciones", []) or []):
                    indice, relacion, motivo = getattr(r, "indice", 0), getattr(r, "relacion", ""), getattr(r, "motivo", "") or ""
                    if 1 <= int(indice) <= len(cands) and relacion in RELACIONES_QUE_CUENTAN:
                        aceptadas.append((cands[int(indice) - 1][0], relacion, motivo))
            except PresupuestoAgotado:
                raise
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        ahora = P.ahora_ms()

        def fn(e2: dict[str, Any], s_=s_, aceptadas=aceptadas, ahora=ahora) -> bool:
            inv2 = next((i for i in e2["investigaciones"] if i["id"] == ctx.investigacion_id), None)
            x = next((y for y in (inv2 or {}).get("vivero", []) if y["id"] == s_["id"]), None)
            if x is None:
                return False
            ids_f = {f["id"] for f in x["fuentes"]}
            for a, relacion, motivo in aceptadas:
                x["afirmaciones"].append(_entrada(a, relacion, motivo, iteracion))
                f = fuentes.get(a["fuenteId"])
                if f and a["fuenteId"] not in ids_f:
                    x["fuentes"].append(_fuente_publica(f, a))
                    ids_f.add(a["fuenteId"])
            if aceptadas:
                x["actualizadaEn"] = ahora
                x["historial"].append(f"Iteración {iteracion}: {len(aceptadas)} afirmaciones nuevas ({sum(1 for _, r, _ in aceptadas if r == 'contradice')} en contra)")
            x["falta"] = VIVERO.falta_de(x)
            nivel, _ = CERTEZA.techo(VIVERO.como_hipotesis(x))
            if CERTEZA.NIVELES.index(nivel) >= 1:
                h = VIVERO.nacer(e2, x, iteracion, ahora, ctx.corrida_id)
                resumen["nacidas"].append(h["id"])
            elif not aceptadas and iteracion - int(x.get("iteracion", iteracion)) >= politicas.ITERACIONES_MAX_EN_VIVERO:
                VIVERO.retirar(e2, x, f"{politicas.ITERACIONES_MAX_EN_VIVERO} iteraciones sin evidencia nueva; le seguía faltando: {x['falta'][:120]}", ahora)
                resumen["retiradas"].append(x["titulo"])
            return True

        ctx.mutar(fn, "vivero")
        resumen["anadidas"] += len(aceptadas)
    if pista:
        pista.resultado(f"Vivero: {resumen['semillas']} ideas, {resumen['anadidas']} afirmaciones nuevas, {len(resumen['nacidas'])} nacen, {len(resumen['retiradas'])} se retiran")
    return resumen
