"""PubMed por E-utilities: buscar PMIDs y traer titulo, autores, revista,
anio, DOI, PMCID y resumen.

Limite: 3 peticiones por segundo sin clave, 10 con `ROSA_NCBI_KEY`.
`esearch` devuelve ids; `efetch` con `rettype=abstract&retmode=xml` devuelve
el articulo completo en XML, que se parsea con ElementTree.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from rosa import config
from rosa.fuentes.base import Limitador, pedir, referencia_corta

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_limitador = Limitador(9.0 if config.CLAVE_NCBI else 2.5)


def _params(**kw: Any) -> dict[str, Any]:
    p = {"tool": "rosa", "email": config.CORREO_CONTACTO, **kw}
    if config.CLAVE_NCBI:
        p["api_key"] = config.CLAVE_NCBI
    return p


async def buscar(consulta: str, maximo: int = 50, desde_anio: int | None = None) -> tuple[list[str], int]:
    """Devuelve (PMIDs, total encontrados)."""
    params = _params(db="pubmed", term=consulta, retmax=maximo, retmode="json", sort="relevance")
    if desde_anio:
        params["mindate"] = str(desde_anio)
        params["maxdate"] = "3000"
        params["datetype"] = "pdat"
    r = await pedir("GET", f"{BASE}/esearch.fcgi", _limitador, params=params)
    d = r.json().get("esearchresult", {})
    return list(d.get("idlist", [])), int(d.get("count", 0) or 0)


def _texto(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


async def detalles(pmids: list[str]) -> list[dict[str, Any]]:
    """Articulos con: pmid, doi, pmcid, titulo, autores, referencia, anio,
    revista, resumen, tipos (lista de PublicationType)."""
    if not pmids:
        return []
    salida: list[dict[str, Any]] = []
    for i in range(0, len(pmids), 100):
        lote = pmids[i : i + 100]
        r = await pedir("POST", f"{BASE}/efetch.fcgi", _limitador, data=_params(db="pubmed", id=",".join(lote), rettype="abstract", retmode="xml"))
        raiz = ET.fromstring(r.text)
        for art in raiz.findall(".//PubmedArticle"):
            med = art.find("MedlineCitation")
            if med is None:
                continue
            pmid = _texto(med.find("PMID"))
            a = med.find("Article")
            if a is None:
                continue
            titulo = _texto(a.find("ArticleTitle"))
            resumen = " ".join(_texto(x) for x in a.findall("Abstract/AbstractText"))
            autores = []
            for au in a.findall("AuthorList/Author"):
                ap = _texto(au.find("LastName"))
                if ap:
                    autores.append(ap)
                elif _texto(au.find("CollectiveName")):
                    autores.append(_texto(au.find("CollectiveName")))
            anio_txt = _texto(a.find("Journal/JournalIssue/PubDate/Year")) or _texto(a.find("Journal/JournalIssue/PubDate/MedlineDate"))[:4]
            anio = int(anio_txt) if anio_txt.isdigit() else None
            revista = _texto(a.find("Journal/ISOAbbreviation")) or _texto(a.find("Journal/Title"))
            doi = pmcid = None
            for idn in art.findall("PubmedData/ArticleIdList/ArticleId"):
                if idn.get("IdType") == "doi":
                    doi = _texto(idn).lower()
                elif idn.get("IdType") == "pmc":
                    pmcid = _texto(idn)
            tipos = [_texto(t) for t in a.findall("PublicationTypeList/PublicationType")]
            salida.append(
                {
                    "pmid": pmid,
                    "doi": doi,
                    "pmcid": pmcid,
                    "titulo": titulo,
                    "autores": autores,
                    "referencia": referencia_corta(autores, anio),
                    "anio": anio,
                    "revista": revista,
                    "resumen": resumen,
                    "tipos": tipos,
                }
            )
    return salida


def tipo_estudio(tipos: list[str], titulo: str) -> tuple[str, int]:
    """Clasifica por PublicationType de PubMed. Nivel de evidencia potencial 1
    a 5, no calidad real."""
    t = " ".join(tipos).lower() + " " + titulo.lower()
    if "meta-analysis" in t or "systematic review" in t:
        return "revision_sistematica", 5
    if "randomized controlled trial" in t or "clinical trial, phase" in t:
        return "ensayo_aleatorizado", 4
    if "cohort" in t or "longitudinal" in t or "prospective" in t:
        return "cohorte", 3
    if "case-control" in t:
        return "caso_control", 3
    if "cross-sectional" in t:
        return "transversal", 2
    if "case reports" in t:
        return "serie_de_casos", 1
    if "review" in t:
        return "revision_narrativa", 2
    if "in vitro" in t or "cell" in t:
        return "in_vitro", 1
    if "mice" in t or "mouse" in t or "rat " in t or "animal" in t:
        return "preclinico", 1
    return "otro", 2
