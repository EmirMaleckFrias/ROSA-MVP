"""Exa: búsqueda semántica de publicaciones y de la web, para agentes.

Exa (exa.ai) indexa la web con un modelo neural de embeddings y recupera por
significado, no por coincidencia de palabras; desde julio de 2026 tiene un
índice dedicado de unos 350 millones de publicaciones académicas que se
activa con `category="publication"`. Rosa lo usa como complemento de PubMed,
Europe PMC y OpenAlex en dos sitios: la búsqueda de literatura (una consulta
en lenguaje natural encuentra el trabajo que no comparte vocabulario con la
hipótesis) y la comprobación de novedad del Killer (¿alguien ya propuso esto
con otras palabras?).

Solo se usan los endpoints de recuperación (`search`, `contents`,
`findSimilar`). Nunca `answer`, `research` ni los tipos `deep`: razonan con
modelos de Exa que no pasan por el AI Gateway de Vercel, y en Rosa el
razonamiento es de Astra, Opus 5 y Sonnet 5.

Procedencia: Exa devuelve URL, no DOI ni PMID garantizados. Aquí se extrae el
DOI de la URL cuando la lleva (doi.org, o un 10.xxxx/... en la ruta) y el PMID
de las URL de PubMed; lo demás queda como URL, y `claves_de_fuente` fusiona
por DOI, PMID o título normalizado como con las otras bases. La clave va solo
en la cabecera `x-api-key`, desde `ROSA_EXA_KEY`; nunca en argumentos, logs ni
en el registro de consulta.

Precio (septiembre de 2026): 7 USD por mil búsquedas (hasta 10 resultados) y
1 USD por mil páginas de contenido. Se anota `costDollars` cuando la API lo da.
"""

from __future__ import annotations

import re
from typing import Any

from rosa import config
from rosa.fuentes.base import FuenteNoDisponible, Limitador, json_de, pedir, referencia_corta

BASE = "https://api.exa.ai"
_limitador = Limitador(5.0)

_DOI = re.compile(r"10\.\d{4,9}/[^\s?#]+", re.IGNORECASE)
_PMID = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")
_PMCID = re.compile(r"(PMC\d+)")
_FECHA = re.compile(r"^(\d{4})")


def disponible() -> bool:
    return bool(config.CLAVE_EXA)


def _cabeceras() -> dict[str, str]:
    if not config.CLAVE_EXA:
        raise FuenteNoDisponible("Exa: sin clave (ROSA_EXA_KEY). No se pudo comprobar en Exa")
    return {"x-api-key": config.CLAVE_EXA, "Content-Type": "application/json"}


# Editoriales cuyas URL llevan el identificador del artículo pero no el prefijo
# del DOI: el DOI se reconstruye con el prefijo de la editorial.
_EDITORIALES = ((re.compile(r"nature\.com/articles/([a-z0-9.-]+)", re.IGNORECASE), "10.1038/"),)


def doi_de_url(url: str) -> str | None:
    url = url or ""
    for patron, prefijo in _EDITORIALES:
        e = patron.search(url)
        if e:
            return (prefijo + e.group(1)).lower()
    m = _DOI.search(url)
    if not m:
        return None
    doi = m.group(0).rstrip(".,;)/")
    # Quitar sufijos de sitios que añaden segmentos tras el DOI (/full, /pdf).
    doi = re.sub(r"/(full|pdf|abstract|html)$", "", doi, flags=re.IGNORECASE)
    return doi.lower()


def _autores(valor: Any) -> list[str]:
    if not valor:
        return []
    if isinstance(valor, list):
        nombres = [str(x) for x in valor]
    else:
        nombres = re.split(r"[;,]\s*|\s+and\s+", str(valor))
    apellidos = []
    for n in nombres:
        n = n.strip()
        if not n:
            continue
        apellidos.append(n.split(" ")[-1] if " " in n else n)
    return apellidos[:12]


def _articulo(r: dict[str, Any]) -> dict[str, Any]:
    """Un resultado de Exa con la forma de los artículos de OpenAlex y Europe
    PMC, para que el cribado, la fusión y el registro sean los mismos."""
    url = r.get("url") or ""
    fecha = r.get("publishedDate") or ""
    m = _FECHA.match(fecha)
    anio = int(m.group(1)) if m else None
    autores = _autores(r.get("author"))
    destacados = [h.strip() for h in (r.get("highlights") or []) if h and h.strip()]
    resumen = (r.get("summary") or "").strip() or " ".join(destacados) or (r.get("text") or "")[:1500]
    pm = _PMID.search(url)
    pmc = _PMCID.search(url) if "ncbi.nlm.nih.gov/pmc" in url or "europepmc.org" in url else None
    return {
        "exa": r.get("id") or url,
        "url": url,
        "doi": doi_de_url(url),
        "pmid": pm.group(1) if pm else None,
        "pmcid": pmc.group(1) if pmc else None,
        "titulo": (r.get("title") or "").strip(),
        "autores": autores,
        "referencia": referencia_corta(autores, anio),
        "anio": anio,
        "fecha": fecha[:10] or None,
        "tipo": "publication",
        "preprint": any(d in url for d in ("biorxiv.org", "medrxiv.org", "arxiv.org", "researchsquare.com", "ssrn.com")),
        "pdf": url if url.lower().endswith(".pdf") else None,
        "resumen": resumen,
        "destacados": destacados,
        "puntuacionExa": r.get("score"),
    }


def _coste(d: dict[str, Any]) -> float:
    c = d.get("costDollars") or {}
    try:
        return float(c.get("total") or 0.0)
    except (TypeError, ValueError):
        return 0.0


async def buscar(texto: str, maximo: int = 10, desde_anio: int | None = None, dominios: list[str] | None = None, categoria: str | None = "publication", destacados: int = 3) -> tuple[list[dict[str, Any]], int, float]:
    """Búsqueda semántica. `texto` va en lenguaje natural (una pregunta o una
    hipótesis), no con operadores booleanos. Devuelve (artículos, n, coste
    en USD). Exa no da un total: `n` es el número de resultados traídos."""
    cuerpo: dict[str, Any] = {
        "query": texto[:1000],
        "type": "auto",
        "numResults": max(1, min(maximo, 100)),
        "contents": {"highlights": {"numSentences": 3, "highlightsPerUrl": max(1, destacados)}},
    }
    if categoria:
        cuerpo["category"] = categoria
    if desde_anio:
        cuerpo["startPublishedDate"] = f"{desde_anio}-01-01T00:00:00.000Z"
    if dominios:
        cuerpo["includeDomains"] = dominios[:50]
    r = await pedir("POST", f"{BASE}/search", _limitador, headers=_cabeceras(), json=cuerpo)
    d = json_de(r)
    resultados = d.get("results") or []
    articulos = [_articulo(x) for x in resultados if isinstance(x, dict) and x.get("url")]
    return articulos, len(articulos), _coste(d)


async def similares(url: str, maximo: int = 6, categoria: str | None = "publication") -> tuple[list[dict[str, Any]], float]:
    """Documentos parecidos a uno dado: la pregunta de novedad al revés
    (¿qué se parece a este trabajo?)."""
    cuerpo: dict[str, Any] = {"url": url, "numResults": max(1, min(maximo, 50)), "excludeSourceDomain": False, "contents": {"highlights": {"numSentences": 2, "highlightsPerUrl": 2}}}
    if categoria:
        cuerpo["category"] = categoria
    r = await pedir("POST", f"{BASE}/findSimilar", _limitador, headers=_cabeceras(), json=cuerpo)
    d = json_de(r)
    return [_articulo(x) for x in (d.get("results") or []) if isinstance(x, dict) and x.get("url")], _coste(d)


async def contenidos(urls: list[str], maximo_caracteres: int = 20000) -> tuple[list[dict[str, Any]], float]:
    """Texto limpio de páginas abiertas. Sirve para localizar; la cita de Rosa
    sigue saliendo del PDF o el XML con su página o sección."""
    if not urls:
        return [], 0.0
    cuerpo = {"urls": urls[:20], "text": {"maxCharacters": max(1000, min(maximo_caracteres, 100000))}}
    r = await pedir("POST", f"{BASE}/contents", _limitador, headers=_cabeceras(), json=cuerpo)
    d = json_de(r)
    filas = [{"url": x.get("url"), "titulo": (x.get("title") or "").strip(), "texto": x.get("text") or "", "fecha": (x.get("publishedDate") or "")[:10] or None} for x in (d.get("results") or []) if isinstance(x, dict)]
    return filas, _coste(d)
