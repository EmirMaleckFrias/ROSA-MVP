"""PubTator 3 (NCBI): entidades y relaciones extraídas de toda la literatura.

PubTator 3 anota genes, enfermedades, químicos, variantes, especies y líneas
celulares en 36 millones de resúmenes y 6 millones de textos completos, y
extrae relaciones entre entidades (asociación, tratamiento, causa,
interacción, correlación) con el número de publicaciones que las sostienen.
API pública y gratuita, sin clave. Los identificadores tienen la forma
`@GENE_GFAP`, `@DISEASE_Alzheimer_Disease`, `@CHEMICAL_...`.

Para ROSA2018 es el esqueleto de evidencia del grafo causal: antes de que el
modelo proponga que A afecta a B, se puede ver cuántas publicaciones
relacionan A con B según PubTator. Como toda base, "no responde" es "no pude
comprobar", nunca "no hay". Comprobado en vivo el 15 de septiembre de 2026.
Referencia: https://www.ncbi.nlm.nih.gov/research/pubtator3/api
"""

from __future__ import annotations

from typing import Any

from rosa.conectores.base import Resultado, conector
from rosa.conectores.bases import _esq
from rosa.fuentes.base import Limitador, json_de, pedir

BASE = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"
_lim = Limitador(3.0)
DOC = "https://www.ncbi.nlm.nih.gov/research/pubtator3/api"
LICENCIA = "Dominio público (NCBI); sin clave"
LIMITE = "3 por segundo (límite propio de ROSA2018)"
TIPOS_RELACION = ("associate", "positive_correlate", "negative_correlate", "cause", "treat", "prevent", "inhibit", "stimulate", "interact", "cotreat", "drug_interact", "compare")


async def resolver(termino: str, concepto: str | None = None, limite: int = 5) -> list[dict[str, Any]]:
    """Identificadores de PubTator para un término (gene, disease, chemical,
    variant, species, cellline)."""
    params: dict[str, Any] = {"query": termino, "limit": limite}
    if concepto:
        params["concept"] = concepto
    r = await pedir("GET", f"{BASE}/entity/autocomplete/", _lim, params=params)
    filas = json_de(r)
    return [{"id": x.get("_id"), "tipo": x.get("biotype"), "nombre": x.get("name"), "baseId": x.get("db_id"), "base": x.get("db")} for x in (filas or []) if isinstance(x, dict) and x.get("_id")]


@conector(
    "pubtator_entidad",
    "PubTator 3 (NCBI)",
    "Resuelve un término (gen, enfermedad, químico, variante) a su identificador de PubTator, con el de la base de origen (NCBI Gene, MeSH)",
    "El identificador con el que se consultan las relaciones y la literatura anotada",
    _esq(termino="Nombre o símbolo, por ejemplo GFAP o Alzheimer", concepto="gene, disease, chemical, variant, species o cellline (opcional)"),
    LICENCIA, LIMITE, DOC, grupo="literatura",
)
async def pubtator_entidad(termino: str, concepto: str = "") -> Resultado:
    filas = await resolver(termino, concepto or None)
    exacto = [f for f in filas if (f["nombre"] or "").lower() == termino.lower()]
    return Resultado(filas, len(filas), [f["id"] for f in filas], None, (bool(exacto), f"coincidencia exacta: {exacto[0]['id']}" if exacto else "sin coincidencia exacta; revisar el primero"))


@conector(
    "pubtator_relaciones",
    "PubTator 3 (NCBI)",
    "Relaciones extraídas de la literatura para una entidad (con qué se asocia, qué la causa, qué la trata) y cuántas publicaciones sostienen cada una",
    "Evidencia bibliográfica contada para las aristas del grafo causal: antes de proponer que A afecta a B, cuántos artículos relacionan A con B",
    _esq(entidad="Identificador de PubTator, por ejemplo @GENE_GFAP (o un término, que se resuelve primero)", tipo="Tipo de relación: associate, cause, treat, positive_correlate, negative_correlate... (opcional)", con="Segunda entidad para acotar, por ejemplo @DISEASE_Alzheimer_Disease (opcional)"),
    LICENCIA, LIMITE, DOC, grupo="literatura",
)
async def pubtator_relaciones(entidad: str, tipo: str = "", con: str = "") -> Resultado:
    if not entidad.startswith("@"):
        resueltas = await resolver(entidad)
        if not resueltas:
            return Resultado([], 0, [], None, (False, f"'{entidad}' no resuelve a ninguna entidad de PubTator"))
        entidad = resueltas[0]["id"]
    params: dict[str, Any] = {"e1": entidad}
    if tipo:
        params["type"] = tipo
    if con:
        params["e2"] = con
    r = await pedir("GET", f"{BASE}/relations", _lim, params=params)
    filas = json_de(r) or []
    relaciones = [{"tipo": x.get("type"), "de": x.get("source"), "a": x.get("target"), "publicaciones": int(x.get("publications") or 0)} for x in filas if isinstance(x, dict)]
    relaciones.sort(key=lambda x: -x["publicaciones"])
    ids = sorted(({x["de"] for x in relaciones} | {x["a"] for x in relaciones}) - {entidad, None})
    total = sum(x["publicaciones"] for x in relaciones)
    return Resultado({"entidad": entidad, "relaciones": relaciones[:50]}, len(relaciones), ids[:50], None, (len(relaciones) > 0, f"{len(relaciones)} relaciones con {total} publicaciones de soporte" if relaciones else "sin relaciones anotadas"))


@conector(
    "pubtator_literatura",
    "PubTator 3 (NCBI)",
    "Artículos que mencionan juntas dos o más entidades (búsqueda por identificador, no por palabras)",
    "Literatura que co-menciona las entidades de una hipótesis, sin depender de sinónimos",
    _esq(consulta="Consulta con identificadores, por ejemplo '@GENE_GFAP AND @DISEASE_Alzheimer_Disease'", pagina="Página de resultados (opcional, 1 por defecto)"),
    LICENCIA, LIMITE, DOC, grupo="literatura",
)
async def pubtator_literatura(consulta: str, pagina: str = "1") -> Resultado:
    r = await pedir("GET", f"{BASE}/search/", _lim, params={"text": consulta, "page": int(pagina) if str(pagina).isdigit() else 1})
    d = json_de(r) or {}
    filas = [{"pmid": str(x.get("pmid") or ""), "titulo": x.get("title") or "", "revista": x.get("journal") or "", "fecha": (x.get("date") or "")[:10], "puntuacion": x.get("score")} for x in (d.get("results") or []) if isinstance(x, dict)]
    total = int(d.get("count") or 0)
    return Resultado({"total": total, "articulos": filas}, total, [f["pmid"] for f in filas if f["pmid"]], None, (total > 0, f"{total} artículos co-mencionan las entidades" if total else "ninguna co-mención anotada"))
