"""Crossref: metadatos por DOI y, sobre todo, retractaciones.

Desde enero de 2025 la base de Retraction Watch esta integrada: en el
articulo retractado aparece `updated-by[]` con `type` (retraction,
expression_of_concern, correction, erratum...) y `source` (publisher o
retraction-watch). Limite: 5 por segundo publico, 10 con `mailto`.

Cuidado medido el 10 de septiembre de 2026: `is_retracted` de OpenAlex tiene
falsos positivos por errores de metadatos del editor; aqui se mira el tipo
de la nota y se devuelve la marca mas grave encontrada.
"""

from __future__ import annotations

from typing import Any

from rosa import config
from rosa.fuentes.base import FuenteNoDisponible, Limitador, pedir

BASE = "https://api.crossref.org/works"
_limitador = Limitador(4.0)

_GRAVEDAD = {"retraction": "retractado", "partial_retraction": "retractado", "removal": "retractado", "withdrawal": "retractado", "expression_of_concern": "preocupacion", "erratum": "erratum", "correction": "erratum", "corrigendum": "erratum"}


async def marca_editorial(doi: str) -> tuple[str | None, str]:
    """Devuelve (marca, detalle). marca en {retractado, preocupacion, erratum, None}.
    Lanza FuenteNoDisponible si Crossref no responde (no es "sin marca")."""
    r = await pedir("GET", f"{BASE}/{doi}", _limitador, params={"mailto": config.CORREO_CONTACTO})
    obra = r.json().get("message", {})
    marca: str | None = None
    detalles: list[str] = []
    orden = ["retractado", "preocupacion", "erratum"]
    for u in obra.get("updated-by", []) or []:
        tipo = str(u.get("type", "")).lower().replace("-", "_")
        m = _GRAVEDAD.get(tipo)
        if not m:
            continue
        detalles.append(f"{u.get('label') or tipo} ({u.get('source', 'editor')}, DOI {u.get('DOI', '')})")
        if marca is None or orden.index(m) < orden.index(marca):
            marca = m
    return marca, "; ".join(detalles) if detalles else "Sin notas editoriales en Crossref"


async def metadatos(doi: str) -> dict[str, Any]:
    r = await pedir("GET", f"{BASE}/{doi}", _limitador, params={"mailto": config.CORREO_CONTACTO})
    m = r.json().get("message", {})
    partes = (m.get("issued") or m.get("published") or {}).get("date-parts") or [[None]]
    return {
        "doi": doi.lower(),
        "titulo": (m.get("title") or [""])[0],
        "revista": (m.get("container-title") or [""])[0],
        "anio": partes[0][0],
        "tipo": m.get("type"),
        "citas": m.get("is-referenced-by-count"),
        "autores": [a.get("family") or a.get("name") or "" for a in m.get("author", [])],
    }


async def existe(doi: str) -> bool:
    try:
        await metadatos(doi)
        return True
    except FuenteNoDisponible as ex:
        if "HTTP 404" in str(ex):
            return False
        raise
