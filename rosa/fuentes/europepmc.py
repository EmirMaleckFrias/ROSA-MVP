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

import re
import xml.etree.ElementTree as ET
from typing import Any

from rosa.fuentes import base as FB
from rosa.fuentes.base import Limitador, NoEncontrado, compartido, pedir, referencia_corta

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
_limitador = compartido("europepmc", 6.0)


# Un nombre que termina en "+" ("evoke+", "Study 201+"): entre comillas o suelto,
# y no ya dentro de un campo (TITLE_ABS:"evoke+" se trata aparte).
_NOMBRE_MAS_ENTRECOMILLADO = re.compile(r'(?<![A-Za-z_]:)"([^"]+?)\+"')
_NOMBRE_MAS_SUELTO = re.compile(r'(?<![\w:"+-])([A-Za-z][\w-]*)\+(?=$|[\s)])')
_CAMPO_CON_MAS = re.compile(r'((?:TITLE_ABS|TITLE|ABSTRACT|AUTH|JOURNAL):)"([^"]+?)\+"', re.IGNORECASE)


def traducir_consulta(consulta: str) -> str:
    """Europe PMC ignora el «+» final de un nombre: `"evoke+"` devuelve lo
    mismo que `"evoke"` (2.901 resultados, la mayoría con el verbo inglés).
    Un nombre que termina en «+» se envía como `TITLE_ABS:"nombre"`, que al
    menos exige la palabra en el título o el resumen y deja fuera las
    menciones de paso del texto completo (revisión del 17 de septiembre de
    2026, S-07). Lo demás va tal cual: el registro de la consulta guarda lo
    que escribió el plan y la pista enseña lo que se envió."""
    q = consulta or ""
    q = _CAMPO_CON_MAS.sub(lambda m: f'{m.group(1)}"{m.group(2)}"', q)
    q = _NOMBRE_MAS_ENTRECOMILLADO.sub(lambda m: f'TITLE_ABS:"{m.group(1)}"', q)
    q = _NOMBRE_MAS_SUELTO.sub(lambda m: f'TITLE_ABS:"{m.group(1)}"', q)
    return q


async def buscar(consulta: str, maximo: int = 50, solo_preprints: bool = False, desde_anio: int | None = None) -> tuple[list[dict[str, Any]], int]:
    q = traducir_consulta(consulta)
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
                "referencia": referencia_corta(autores, anio, identificador=((x.get("doi") or "").lower() or None) or (f"PMID {x.get('pmid')}" if x.get("pmid") else None) or x.get("pmcid")),
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
    """Secciones del artículo: [{seccion, texto}]. Vacío si no hay XML.

    Con caché en disco (`rosa.fuentes.base.cache_leer`, espacio "europepmc",
    clave el PMCID): el XML de un artículo ya leído en otra corrida no se
    vuelve a pedir (S-06 f). Solo se guarda un resultado con secciones: un
    artículo sin texto completo hoy puede tenerlo mañana."""
    en_cache = FB.cache_leer("europepmc", str(pmcid or ""))
    if isinstance(en_cache, list) and en_cache and all(isinstance(x, dict) and x.get("texto") for x in en_cache):
        return [{"seccion": str(x.get("seccion") or "Sin título"), "texto": str(x["texto"])} for x in en_cache]
    try:
        r = await pedir("GET", f"{BASE}/{pmcid}/fullTextXML", _limitador)
    except NoEncontrado:
        return []  # sin texto completo abierto para ese PMCID: no es una caida
    try:
        raiz = ET.fromstring(r.text)
    except ET.ParseError:
        return []
    secciones: list[dict[str, str]] = []
    for sec in raiz.iter("sec"):
        titulo_el = sec.find("title")
        titulo = "".join(titulo_el.itertext()).strip() if titulo_el is not None else "Sin título"
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
    if secciones:
        FB.cache_guardar("europepmc", str(pmcid), secciones)
    return secciones
