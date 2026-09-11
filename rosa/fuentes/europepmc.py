"""Europe PMC: busqueda unificada (incluye preprints de bioRxiv y medRxiv) y
texto completo en XML (JATS) de los articulos de PMC en acceso abierto.

Limite: 10 por segundo, 500 por minuto. Sin clave.
- `search` con `resultType=core` devuelve titulo, autores, resumen, DOI,
  PMID, PMCID, `isOpenAccess`, `hasTextMinedTerms`, y `source` (MED, PMC,
  PPR para preprints).
- `/{PMCID}/fullTextXML` devuelve el articulo en JATS. Sin numeros de pagina:
  el localizador de la cita es la seccion, no la pagina. Si hay PDF, el
  conector pdf.py da la pagina exacta.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from rosa.fuentes.base import Limitador, pedir, referencia_corta

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
_limitador = Limitador(6.0)


async def buscar(consulta: str, maximo: int = 50, solo_preprints: bool = False, desde_anio: int | None = None) -> tuple[list[dict[str, Any]], int]:
    q = consulta
    if solo_preprints:
        q = f"({q}) AND SRC:PPR"
    if desde_anio:
        q = f"({q}) AND PUB_YEAR:[{desde_anio} TO 3000]"
    r = await pedir("GET", f"{BASE}/search", _limitador, params={"query": q, "format": "json", "pageSize": min(maximo, 100), "resultType": "core"})
    d = r.json()
    total = int(d.get("hitCount", 0) or 0)
    salida = []
    for x in d.get("resultList", {}).get("result", []):
        autores = [a.get("lastName") or a.get("collectiveName") or "" for a in x.get("authorList", {}).get("author", [])]
        autores = [a for a in autores if a]
        anio = int(x["pubYear"]) if str(x.get("pubYear", "")).isdigit() else None
        salida.append(
            {
                "pmid": x.get("pmid"),
                "pmcid": x.get("pmcid"),
                "doi": (x.get("doi") or "").lower() or None,
                "titulo": x.get("title", "").rstrip("."),
                "autores": autores,
                "referencia": referencia_corta(autores, anio),
                "anio": anio,
                "revista": x.get("journalTitle") or x.get("bookOrReportDetails", {}).get("publisher", ""),
                "resumen": x.get("abstractText", "") or "",
                "preprint": x.get("source") == "PPR",
                "accesoAbierto": x.get("isOpenAccess") == "Y",
                "textoCompleto": x.get("inEPMC") == "Y" or x.get("hasPDF") == "Y",
                "citas": int(x.get("citedByCount", 0) or 0),
                "tipos": x.get("pubTypeList", {}).get("pubType", []),
            }
        )
    return salida, total


async def texto_completo(pmcid: str) -> list[dict[str, str]]:
    """Secciones del articulo: [{seccion, texto}]. Vacio si no hay XML."""
    r = await pedir("GET", f"{BASE}/{pmcid}/fullTextXML", _limitador)
    try:
        raiz = ET.fromstring(r.text)
    except ET.ParseError:
        return []
    secciones: list[dict[str, str]] = []
    for sec in raiz.iter("sec"):
        titulo_el = sec.find("title")
        titulo = "".join(titulo_el.itertext()).strip() if titulo_el is not None else "Sin titulo"
        parrafos = ["".join(p.itertext()).strip() for p in sec.findall("p")]
        texto = "\n".join(p for p in parrafos if p)
        if texto:
            secciones.append({"seccion": titulo, "texto": texto})
    if not secciones:
        cuerpo = raiz.find(".//body")
        if cuerpo is not None:
            texto = "\n".join("".join(p.itertext()).strip() for p in cuerpo.iter("p"))
            if texto.strip():
                secciones.append({"seccion": "Cuerpo", "texto": texto})
    return secciones
