"""Vigilancia de literatura: qué se publicó sobre cada hipótesis viva desde
la última comprobación.

Es la pieza de "revisión sistemática viva" que no necesita Websets ni
monitores de pago: una búsqueda semántica de Exa por hipótesis y día, acotada
con `startPublishedDate` a lo posterior a la última comprobación (o a la
creación de la hipótesis la primera vez). Cuesta 0,007 USD por hipótesis y
día y no llama a ningún modelo: lo que devuelve son publicaciones con su URL,
su DOI cuando lo lleva y el pasaje que más se parece al enunciado. Las
novedades quedan en `hipotesis.vigilancia` y cada comprobación con novedades
deja un evento en la línea de tiempo de la investigación. Decidir si una
novedad cambia algo sigue siendo de la persona (o de la siguiente iteración,
que la verá como fuente candidata).

No se vuelve a avisar de lo ya conocido: se descartan las publicaciones cuyo
DOI o PMID ya está en la procedencia de la hipótesis o en novedades
anteriores. Una hipótesis se vuelve a comprobar como muy pronto 24 horas
después de la última vez, así que reiniciar Rosa no repite consultas.

Filtro de pertinencia, sin modelos: Exa devuelve siempre los N documentos
más parecidos, aunque ninguno hable de la hipótesis (la primera pasada real
trajo 116 "novedades" para 19 hipótesis, casi todas ruido). Una publicación
cuenta como novedad solo si su título o su pasaje nombran los términos
clave de la hipótesis (siglas, genes, biomarcadores: GFAP, NfL, APOE...):
al menos dos cuando la hipótesis tiene tres o más, al menos uno si tiene
menos. Los términos que coinciden quedan en la novedad, para que se vea por
qué entró. `depurar` aplica la misma regla a lo ya guardado en cada pasada y
retira los eventos de vigilancia de las hipótesis que se quedan sin nada.
"""

from __future__ import annotations

from typing import Any

import re

from rosa.bucle import contexto as T
from rosa.bucle.pasos import fecha_iso_de_ms
from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.fuentes import exa
from rosa.fuentes.base import FuenteNoDisponible

ESTADOS_VIVOS = ("propuesta", "en_revision", "aceptada", "refinar", "aclarando")
INTERVALO_MS = 24 * 3600 * 1000
MAX_NUEVAS_GUARDADAS = 40
MAX_POR_COMPROBACION = 8


def _claves_conocidas(h: dict[str, Any]) -> set[str]:
    claves: set[str] = set()
    for f in ((h.get("procedencia") or {}).get("fuentes") or []):
        if f.get("doi"):
            claves.add(f"doi:{str(f['doi']).lower()}")
        if f.get("pmid"):
            claves.add(f"pmid:{f['pmid']}")
    for n in ((h.get("vigilancia") or {}).get("nuevas") or []):
        if n.get("doi"):
            claves.add(f"doi:{str(n['doi']).lower()}")
        if n.get("url"):
            claves.add(f"url:{n['url']}")
    return claves


def terminos_de(h: dict[str, Any]) -> list[str]:
    """Los términos con los que se reconoce que una publicación habla de la
    hipótesis: primero siglas, genes y biomarcadores (mayúsculas o cifras),
    después palabras largas del dominio si no hay bastantes."""
    texto = f"{h.get('titulo', '')} {h.get('enunciado', '')}"
    fuertes: list[str] = []
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,}", texto):
        # Siglas, genes y biomarcadores: dos mayúsculas o una cifra (GFAP, NfL, APOE, BACE1, p-tau181).
        if (sum(c.isupper() for c in tok) >= 2 or re.search(r"\d", tok)) and tok.lower() not in {x.lower() for x in fuertes}:
            fuertes.append(tok)
    resto = [x for x in T.terminos_clave(texto, maximo=12) if x.lower() not in {f.lower() for f in fuertes}]
    elegidos = fuertes + resto[: max(0, 3 - len(fuertes))]
    return elegidos[:8]


def coincidencias(terminos: list[str], texto: str) -> list[str]:
    t = (texto or "").lower()
    return [x for x in terminos if x.lower() in t]


def es_pertinente(terminos: list[str], n: dict[str, Any]) -> list[str]:
    """Los términos que coinciden si la novedad es pertinente; [] si no."""
    hallados = coincidencias(terminos, f"{n.get('titulo', '')} {n.get('pasaje', '')}")
    exigidos = 2 if len(terminos) >= 3 else 1
    return hallados if len(hallados) >= exigidos else []


def toca(h: dict[str, Any], ahora: int) -> bool:
    """Si la hipótesis está viva y hace al menos 24 horas de la última comprobación."""
    if h.get("estado") not in ESTADOS_VIVOS:
        return False
    ultima = (h.get("vigilancia") or {}).get("ultimaComprobacion")
    return ultima is None or ahora - int(ultima) >= INTERVALO_MS


def _nueva(a: dict[str, Any]) -> dict[str, Any]:
    return {
        "titulo": (a.get("titulo") or "")[:200],
        "referencia": a.get("referencia") or "",
        "url": a.get("url"),
        "doi": a.get("doi"),
        "fecha": a.get("fecha"),
        "preprint": bool(a.get("preprint")),
        "pasaje": (a.get("resumen") or "")[:400],
        "similitud": a.get("similitud"),
    }


async def comprobar_hipotesis(h: dict[str, Any], ahora: int) -> tuple[list[dict[str, Any]], float, str | None]:
    """Busca lo publicado desde la última comprobación. Devuelve (nuevas,
    coste, error). Con error no hay novedades, pero tampoco se afirma que no
    las haya: la comprobación no cuenta como hecha."""
    desde_ms = (h.get("vigilancia") or {}).get("ultimaComprobacion") or h.get("creadaEn") or ahora
    desde = fecha_iso_de_ms(desde_ms)
    try:
        articulos, _, coste = await exa.buscar(h["enunciado"][:600], maximo=MAX_POR_COMPROBACION, desde_fecha=desde, pregunta_pasajes=h["enunciado"][:500])
    except FuenteNoDisponible as ex:
        return [], 0.0, str(ex)[:160]
    conocidas = _claves_conocidas(h)
    terminos = terminos_de(h)
    nuevas = []
    for a in articulos:
        clave_doi = f"doi:{a['doi']}" if a.get("doi") else None
        clave_url = f"url:{a['url']}" if a.get("url") else None
        if (clave_doi and clave_doi in conocidas) or (clave_url and clave_url in conocidas) or (a.get("pmid") and f"pmid:{a['pmid']}" in conocidas):
            continue
        if not a.get("titulo"):
            continue
        candidata = _nueva(a)
        candidata["terminos"] = es_pertinente(terminos, candidata)
        if not candidata["terminos"]:
            continue
        nuevas.append(candidata)
        if clave_doi:
            conocidas.add(clave_doi)
        if clave_url:
            conocidas.add(clave_url)
    return nuevas, coste, None


def depurar(almacen: Any) -> int:
    """Aplica la regla de pertinencia a las novedades ya guardadas y retira los
    eventos de vigilancia de las hipótesis que se quedan sin ninguna. Devuelve
    cuántas novedades se retiraron. Idempotente."""
    retiradas = {"n": 0}

    def fn(e: dict[str, Any]) -> bool:
        vacias: set[str] = set()
        for h in e.get("hipotesis", []):
            v = h.get("vigilancia")
            if not v or not v.get("nuevas"):
                continue
            terminos = terminos_de(h)
            filtradas = []
            for n in v["nuevas"]:
                hallados = es_pertinente(terminos, n)
                if hallados:
                    n["terminos"] = hallados
                    filtradas.append(n)
                else:
                    retiradas["n"] += 1
            v["nuevas"] = filtradas
            if not filtradas:
                vacias.add(h["id"])
        if vacias:
            e["eventos"] = [ev for ev in e.get("eventos", []) if not (ev.get("tipo") == "vigilancia" and any(str(ev.get("ruta") or "").endswith(f"/hipotesis/{hid}") for hid in vacias))]
        return retiradas["n"] > 0 or bool(vacias)

    almacen.mutar(fn, "vigilancia_depurar")
    return retiradas["n"]


async def vigilar(almacen: Any, ahora: int | None = None) -> dict[str, Any]:
    """Una pasada sobre todas las hipótesis vivas a las que les toca. Escribe
    en el estado y devuelve un resumen {comprobadas, conNovedades, nuevas,
    costeUsd, errores, retiradas}."""
    ahora = P.ahora_ms() if ahora is None else ahora
    resumen = {"comprobadas": 0, "conNovedades": 0, "nuevas": 0, "costeUsd": 0.0, "errores": 0, "retiradas": 0}
    if not exa.disponible():
        return resumen
    resumen["retiradas"] = depurar(almacen)
    pendientes = [dict(h) for h in almacen.estado.get("hipotesis", []) if toca(h, ahora)]
    for h in pendientes:
        nuevas, coste, error = await comprobar_hipotesis(h, ahora)
        resumen["costeUsd"] = round(resumen["costeUsd"] + coste, 6)
        if error:
            resumen["errores"] += 1

            def anotar_error(e: dict[str, Any], h=h, error=error) -> bool:
                x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
                if not x:
                    return False
                v = x.setdefault("vigilancia", {"ultimaComprobacion": None, "nuevas": [], "costeUsd": 0.0, "comprobaciones": 0})
                v["ultimoError"] = f"No pude comprobar: {error}"
                return True

            almacen.mutar(anotar_error, "vigilancia")
            continue
        resumen["comprobadas"] += 1
        resumen["nuevas"] += len(nuevas)
        if nuevas:
            resumen["conNovedades"] += 1

        def aplicar(e: dict[str, Any], h=h, nuevas=nuevas, coste=coste) -> bool:
            x = next((y for y in e["hipotesis"] if y["id"] == h["id"]), None)
            if not x:
                return False
            v = x.setdefault("vigilancia", {"ultimaComprobacion": None, "nuevas": [], "costeUsd": 0.0, "comprobaciones": 0})
            v["ultimaComprobacion"] = ahora
            v["comprobaciones"] = int(v.get("comprobaciones") or 0) + 1
            v["costeUsd"] = round(float(v.get("costeUsd") or 0.0) + coste, 6)
            v["ultimoError"] = None
            v["nuevas"] = (nuevas + list(v.get("nuevas") or []))[:MAX_NUEVAS_GUARDADAS]
            if nuevas:
                cuantas = "1 publicación nueva" if len(nuevas) == 1 else f"{len(nuevas)} publicaciones nuevas"
                nombran = sorted({t_ for n in nuevas for t_ in n.get("terminos", [])})[:4]
                texto = f"Vigilancia: {cuantas} sobre «{x['titulo'][:70]}» desde la última comprobación" + (f" (nombran {', '.join(nombran)})" if nombran else "")
                A.con_evento(e, x["investigacionId"], "vigilancia", texto, f"#/investigaciones/{x['investigacionId']}/hipotesis/{x['id']}", ahora)
            return True

        almacen.mutar(aplicar, "vigilancia")
    return resumen
