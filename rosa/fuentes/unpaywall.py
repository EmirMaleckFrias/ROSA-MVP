"""Unpaywall: el enlace legal al PDF en acceso abierto de un DOI.
`GET /v2/{doi}?email=` sin clave; 100000 llamadas al dia como cortesia."""

from __future__ import annotations

from typing import Any

from rosa import config
from rosa.fuentes.base import FuenteNoDisponible, Limitador, pedir

BASE = "https://api.unpaywall.org/v2"
_limitador = Limitador(3.0)


async def pdf_de(doi: str) -> dict[str, Any] | None:
    """{url, version, licencia, tipo_host} o None si no hay copia abierta."""
    try:
        r = await pedir("GET", f"{BASE}/{doi}", _limitador, params={"email": config.CORREO_CONTACTO})
    except FuenteNoDisponible as ex:
        if "HTTP 404" in str(ex):
            return None
        raise
    d = r.json()
    mejor = d.get("best_oa_location") or {}
    url = mejor.get("url_for_pdf")
    if not url:
        for loc in d.get("oa_locations", []) or []:
            if loc.get("url_for_pdf"):
                mejor, url = loc, loc["url_for_pdf"]
                break
    if not url:
        return None
    return {"url": url, "version": mejor.get("version"), "licencia": mejor.get("license"), "host": mejor.get("host_type"), "estadoOa": d.get("oa_status")}
