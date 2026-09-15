"""Conectores de Exa: búsqueda semántica de publicaciones y documentos
parecidos. Con clave (`ROSA_EXA_KEY`) se registran vivos; sin ella quedan en
el catálogo como `requiere_cuenta` con el motivo, para que se vea qué falta.
Solo recuperación: nunca los endpoints que razonan con modelos de Exa."""

from __future__ import annotations

from rosa import config
from rosa.conectores.base import Resultado, conector, inerte
from rosa.fuentes import exa

_DOC = "https://exa.ai/docs/reference/getting-started"
_LICENCIA = "Servicio comercial: 7 USD por mil búsquedas, 1 USD por mil páginas; clave por proyecto"


def _esq(**campos: str) -> dict:
    return {"type": "object", "properties": {k: {"type": "string", "description": v} for k, v in campos.items()}, "required": [next(iter(campos))]}


if config.CLAVE_EXA:

    @conector(
        "exa_publicaciones",
        "Exa (índice de publicaciones)",
        "Busca publicaciones por significado, en lenguaje natural, en un índice de unos 350 millones de trabajos",
        "Encuentra el trabajo que no comparte vocabulario con la pregunta; complementa a PubMed, Europe PMC y OpenAlex",
        _esq(pregunta="La pregunta o la hipótesis, en lenguaje natural (sin operadores booleanos)", desde_anio="Año mínimo de publicación (opcional)"),
        _LICENCIA,
        "5 por segundo (límite propio de Rosa)",
        _DOC,
        clave="si",
        grupo="literatura",
    )
    async def exa_publicaciones(pregunta: str, desde_anio: str = "") -> Resultado:
        anio = int(desde_anio) if str(desde_anio).strip().isdigit() else None
        articulos, n, coste = await exa.buscar(pregunta, maximo=10, desde_anio=anio)
        ids = [a["doi"] or a["pmid"] or a["url"] for a in articulos if a.get("doi") or a.get("pmid") or a.get("url")]
        con_doi = sum(1 for a in articulos if a.get("doi"))
        return Resultado({"articulos": articulos, "costeUsd": coste}, n, ids, None, (con_doi == n, f"{con_doi} de {n} resultados con DOI resuelto desde la URL" if n else "sin resultados"))

    @conector(
        "exa_similares",
        "Exa (documentos parecidos)",
        "Documentos parecidos a una URL dada (un artículo, un preprint, un registro de ensayo)",
        "La pregunta de novedad al revés: qué se parece a este trabajo",
        _esq(url="URL del documento de partida"),
        _LICENCIA,
        "5 por segundo (límite propio de Rosa)",
        _DOC,
        clave="si",
        grupo="literatura",
    )
    async def exa_similares(url: str) -> Resultado:
        articulos, coste = await exa.similares(url, maximo=6)
        ids = [a["doi"] or a["url"] for a in articulos]
        return Resultado({"articulos": articulos, "costeUsd": coste}, len(articulos), ids, None, (bool(articulos), f"{len(articulos)} documentos parecidos"))

    @conector(
        "exa_referencias",
        "Exa (referencias de un artículo)",
        "Los enlaces bibliográficos (DOI, PubMed, preprints) que aparecen en la página de un artículo: su lista de referencias cuando la editorial la publica",
        "El vecindario de citas de un trabajo, para el precedente y para el Árbol",
        _esq(url="URL de la página del artículo"),
        _LICENCIA,
        "5 por segundo (límite propio de Rosa)",
        _DOC,
        clave="si",
        grupo="literatura",
    )
    async def exa_referencias(url: str) -> Resultado:
        refs, coste = await exa.enlaces(url)
        ids = [x["doi"] or x["pmid"] or x["url"] for x in refs]
        con_id = sum(1 for x in refs if x["doi"] or x["pmid"])
        return Resultado({"referencias": refs, "costeUsd": coste}, len(refs), ids, None, (con_id == len(refs) and len(refs) > 0, f"{con_id} de {len(refs)} enlaces con DOI o PMID" if refs else "la página no expone enlaces bibliográficos"))

else:
    _MOTIVO = "Falta la clave de Exa: ROSA_EXA_KEY en el .env del servidor (se crea en dashboard.exa.ai). Sin ella Rosa busca solo en PubMed, Europe PMC y OpenAlex."
    inerte("exa_publicaciones", "Exa (índice de publicaciones)", "Busca publicaciones por significado, en lenguaje natural", "Encuentra el trabajo que no comparte vocabulario con la pregunta", "requiere_cuenta", _MOTIVO, _DOC, "literatura", _LICENCIA)
    inerte("exa_similares", "Exa (documentos parecidos)", "Documentos parecidos a una URL dada", "La pregunta de novedad al revés", "requiere_cuenta", _MOTIVO, _DOC, "literatura", _LICENCIA)
    inerte("exa_referencias", "Exa (referencias de un artículo)", "Los enlaces bibliográficos de la página de un artículo", "El vecindario de citas de un trabajo", "requiere_cuenta", _MOTIVO, _DOC, "literatura", _LICENCIA)
