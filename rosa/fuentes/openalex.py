"""OpenAlex: precedente en la literatura y acceso abierto.

Desde febrero de 2026 cobra por uso: 1 USD al dia gratis con clave (que se
pide en openalex.org/settings/api y va en `ROSA_OPENALEX_KEY`), 0,10 USD sin
clave. Una busqueda (`search=`) cuesta 0,001 USD; un filtro
(`filter=title_and_abstract.search:...`) 0,0001 USD; leer una obra por DOI es
gratis. Rosa usa el filtro y lee `meta.cost_usd` para anotar el gasto.
"""

from __future__ import annotations

from typing import Any

from rosa import config
from rosa.fuentes.base import Limitador, pedir, referencia_corta

BASE = "https://api.openalex.org"
_limitador = Limitador(5.0)

CAMPOS = "id,doi,title,publication_year,publication_date,type,is_retracted,cited_by_count,open_access,best_oa_location,authorships,ids,abstract_inverted_index"


def _params(**kw: Any) -> dict[str, Any]:
    p = dict(kw)
    if config.CLAVE_OPENALEX:
        p["api_key"] = config.CLAVE_OPENALEX
    return p


def reconstruir_resumen(indice: dict[str, list[int]] | None) -> str:
    if not indice:
        return ""
    posiciones = sorted((i, palabra) for palabra, idx in indice.items() for i in idx)
    return " ".join(p for _, p in posiciones)


def _obra(w: dict[str, Any]) -> dict[str, Any]:
    autores = [a.get("author", {}).get("display_name", "").split(" ")[-1] for a in w.get("authorships", [])[:12]]
    autores = [a for a in autores if a]
    anio = w.get("publication_year")
    oa = w.get("best_oa_location") or {}
    return {
        "openalex": w.get("id"),
        "doi": (w.get("doi") or "").replace("https://doi.org/", "").lower() or None,
        "pmid": (w.get("ids", {}).get("pmid") or "").replace("https://pubmed.ncbi.nlm.nih.gov/", "") or None,
        "titulo": w.get("title") or "",
        "autores": autores,
        "referencia": referencia_corta(autores, anio),
        "anio": anio,
        "tipo": w.get("type"),
        "retractadoSegunOpenAlex": bool(w.get("is_retracted")),
        "citas": w.get("cited_by_count"),
        "pdf": oa.get("pdf_url"),
        "accesoAbierto": bool((w.get("open_access") or {}).get("is_oa")),
        "resumen": reconstruir_resumen(w.get("abstract_inverted_index")),
    }


async def buscar(texto: str, maximo: int = 25, desde_anio: int | None = None) -> tuple[list[dict[str, Any]], int, float]:
    """Precedente: obras cuyo titulo o resumen casan con el texto. Devuelve
    (obras, total, coste_usd)."""
    filtro = f"title_and_abstract.search:{texto}"
    if desde_anio:
        filtro += f",publication_year:>{desde_anio - 1}"
    r = await pedir("GET", f"{BASE}/works", _limitador, params=_params(filter=filtro, per_page=min(maximo, 100), select=CAMPOS, sort="cited_by_count:desc"))
    d = r.json()
    return [_obra(w) for w in d.get("results", [])], int(d.get("meta", {}).get("count", 0) or 0), float(d.get("meta", {}).get("cost_usd", 0) or 0)


async def por_doi(doi: str) -> dict[str, Any] | None:
    r = await pedir("GET", f"{BASE}/works/doi:{doi}", _limitador, params=_params(select=CAMPOS))
    return _obra(r.json())
