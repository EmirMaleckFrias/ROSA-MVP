"""Normalizacion de entidades a identificadores canonicos.

Mientras "GFAP", "glial fibrillary acidic protein" y "P14136" sean tres
cadenas distintas, el modelo de mundo es un cuaderno con procedencia, no un
grafo consultable. Aqui cada entidad que aparece en un hecho, una hipotesis
o un nodo causal se enlaza a un identificador estable:

  genes y proteinas: HGNC (rest.genenames.org; con UniProt, Ensembl y Entrez
    en el mismo registro; limite documentado de 10 peticiones por segundo);
  enfermedades: MONDO; tipos celulares: Cell Ontology (CL); tejidos:
    UBERON; procesos: Gene Ontology (GO); compuestos: ChEBI; todo por OLS4
    del EBI (www.ebi.ac.uk/ols4/api), comparando la etiqueta o un sinonimo
    exacto en el cliente porque `exact=true` no garantiza el primer puesto.

Los sinonimos quedan como alias del mismo nodo. Un diccionario curado del
dominio (amiloide, tau, astrocito, hipocampo...) resuelve sin red y de forma
determinista lo que aparece en casi todo el corpus; lo que no esta ahi se
busca en las bases y se guarda en la cache del estado (`entidades`).

El patron es el que recomienda la literatura de 2025 y 2026 sobre
normalizacion de conceptos biomedicos (Dobbins 2025; OntologyAligner 2026):
candidatos por busqueda lexica en la ontologia y eleccion por coincidencia
exacta de etiqueta o sinonimo; el modelo de lenguaje no elige aqui.
"""

from __future__ import annotations

import re
from typing import Any

from rosa.fuentes.base import FuenteNoDisponible, Limitador, json_de, pedir

_lim_hgnc = Limitador(5.0)
_lim_ols = Limitador(4.0)

HGNC = "https://rest.genenames.org"
OLS = "https://www.ebi.ac.uk/ols4/api"

# Entidades del dominio que aparecen en casi todo el corpus: resueltas a mano
# a su identificador canonico para no depender de la red ni de la suerte.
# (patron, id, etiqueta, ontologia, tipo)
CURADAS: tuple[tuple[str, str, str, str, str], ...] = (
    (r"\balzheimer|\bAD\b|enfermedad de alzheimer", "MONDO:0004975", "Alzheimer disease", "MONDO", "enfermedad"),
    (r"deterioro cognitivo leve|mild cognitive impairment|\bMCI\b|\bDCL\b", "MONDO:0004975", "Alzheimer disease", "MONDO", "enfermedad"),
    (r"demencia frontotemporal|frontotemporal dementia|\bFTD\b", "MONDO:0017276", "frontotemporal dementia", "MONDO", "enfermedad"),
    (r"parkinson", "MONDO:0005180", "Parkinson disease", "MONDO", "enfermedad"),
    (r"amiloide|amyloid|abeta|aβ|a-beta|\bab42\b|\bab40\b", "CHEBI:64645", "amyloid-beta", "CHEBI", "compuesto"),
    (r"\bp-?tau\d*\b|ptau\d*|tau fosforil|phospho-?tau|\btau\b", "HGNC:6893", "MAPT (tau)", "HGNC", "gen"),
    (r"\bgfap\b|glial fibrillary", "HGNC:4235", "GFAP", "HGNC", "gen"),
    (r"\bnfl\b|\bnf-l\b|neurofilament light|neurofilamento", "HGNC:7739", "NEFL (NfL)", "HGNC", "gen"),
    (r"\bapoe\s*-?\s*[eε]?4\b|\bapoe4\b|\bapoe\b", "HGNC:613", "APOE", "HGNC", "gen"),
    (r"\btrem-?2\b", "HGNC:17761", "TREM2", "HGNC", "gen"),
    (r"\bapp\b|amyloid precursor", "HGNC:620", "APP", "HGNC", "gen"),
    (r"astrocit|astrocyt|astroglia", "CL:0000127", "astrocyte", "CL", "celula"),
    (r"microglia", "CL:0000129", "microglial cell", "CL", "celula"),
    (r"neurona|neuron\b|neurons\b", "CL:0000540", "neuron", "CL", "celula"),
    (r"oligodendrocit|oligodendrocyt", "CL:0000128", "oligodendrocyte", "CL", "celula"),
    (r"hipocamp|hippocamp", "UBERON:0002421", "hippocampal formation", "UBERON", "tejido"),
    (r"corteza (pre)?frontal|prefrontal cortex|frontal cortex", "UBERON:0001870", "frontal cortex", "UBERON", "tejido"),
    (r"corteza entorrinal|entorhinal", "UBERON:0002728", "entorhinal cortex", "UBERON", "tejido"),
    (r"liquido cefalorraquideo|cerebrospinal fluid|\bcsf\b|\blcr\b", "UBERON:0001359", "cerebrospinal fluid", "UBERON", "tejido"),
    (r"\bplasma\b|\bsangre\b|\bblood\b|\bserum\b|\bsuero\b", "UBERON:0001969", "blood plasma", "UBERON", "tejido"),
    (r"neuroinflama|neuroinflamm", "GO:0150076", "neuroinflammatory response", "GO", "proceso"),
    (r"activacion (de )?astrocit|astrocyte activation|astrogliosis|reactive astro", "GO:0048143", "astrocyte activation", "GO", "proceso"),
    (r"activacion (de la )?microglia|microglial (cell )?activation", "GO:0001774", "microglial cell activation", "GO", "proceso"),
    (r"autofagia|autophagy", "GO:0006914", "autophagy", "GO", "proceso"),
    (r"sinaps|synap", "GO:0045202", "synapse", "GO", "componente"),
    (r"lecanemab", "CHEBI:229272", "lecanemab", "CHEBI", "compuesto"),
    (r"donepezil|donepezilo", "CHEBI:53289", "donepezil", "CHEBI", "compuesto"),
    (r"memantin", "CHEBI:64312", "memantine", "CHEBI", "compuesto"),
)
_CURADAS = [(re.compile(p, re.I), i, e, o, t) for p, i, e, o, t in CURADAS]

ONTOLOGIA_POR_TIPO = {"enfermedad": "mondo", "celula": "cl", "tejido": "uberon", "proceso": "go", "compuesto": "chebi"}


def anotar_curadas(texto: str) -> list[dict[str, str]]:
    """Entidades del diccionario curado presentes en el texto, sin red, sin
    repetir identificador. Determinista."""
    vistos: set[str] = set()
    salida = []
    for patron, id_, etiqueta, onto, tipo in _CURADAS:
        if id_ in vistos:
            continue
        m = patron.search(texto or "")
        if m:
            vistos.add(id_)
            salida.append({"texto": m.group(0), "id": id_, "etiqueta": etiqueta, "ontologia": onto, "tipo": tipo, "origen": "curada"})
    return salida


async def gen_hgnc(simbolo: str) -> dict[str, Any] | None:
    """Un simbolo (aprobado, alias o anterior) al registro HGNC: hgnc_id,
    simbolo aprobado, nombre, UniProt, Ensembl, Entrez y alias. None si no
    existe. Lanza FuenteNoDisponible si HGNC no responde."""
    s = (simbolo or "").strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9\-]{0,15}", s):
        return None
    for campo in ("symbol", "alias_symbol", "prev_symbol"):
        r = await pedir("GET", f"{HGNC}/fetch/{campo}/{s}", _lim_hgnc, headers={"Accept": "application/json"})
        docs = (json_de(r).get("response") or {}).get("docs") or []
        if docs:
            d = docs[0]
            uni = d.get("uniprot_ids") or []
            return {
                "id": d.get("hgnc_id"),
                "simbolo": d.get("symbol"),
                "nombre": d.get("name"),
                "uniprot": uni[0] if uni else None,
                "ensembl": d.get("ensembl_gene_id"),
                "entrez": str(d.get("entrez_id") or "") or None,
                "alias": sorted(set((d.get("alias_symbol") or []) + (d.get("prev_symbol") or []))),
                "ontologia": "HGNC",
                "tipo": "gen",
                "resueltoPor": campo,
            }
    return None


async def termino_ols(texto: str, ontologia: str) -> dict[str, Any] | None:
    """Un termino a su clase en una ontologia de OLS4: solo si la etiqueta o
    un sinonimo exacto coinciden (en el cliente). None si no hay coincidencia."""
    t = (texto or "").strip()
    if len(t) < 3:
        return None
    r = await pedir("GET", f"{OLS}/search", _lim_ols, params={"q": t, "ontology": ontologia, "rows": 10, "queryFields": "label,synonym", "fieldList": "iri,obo_id,label,synonym,ontology_prefix,is_defining_ontology,description"})
    docs = (json_de(r).get("response") or {}).get("docs") or []
    tl = t.lower()

    def coincide(d: dict[str, Any]) -> bool:
        if (d.get("label") or "").lower() == tl:
            return True
        return any((s or "").lower() == tl for s in d.get("synonym") or [])

    candidatos = [d for d in docs if coincide(d)]
    candidatos.sort(key=lambda d: (not d.get("is_defining_ontology", False)))
    if not candidatos:
        return None
    d = candidatos[0]
    return {"id": d.get("obo_id") or d.get("short_form"), "etiqueta": d.get("label"), "ontologia": d.get("ontology_prefix") or ontologia.upper(), "iri": d.get("iri"), "sinonimos": (d.get("synonym") or [])[:12], "definicion": ((d.get("description") or [""])[0] or "")[:300], "tipo": next((k for k, v in ONTOLOGIA_POR_TIPO.items() if v == ontologia), "termino")}


async def normalizar(simbolos: list[str], terminos: list[tuple[str, str]], cache: dict[str, Any]) -> list[dict[str, Any]]:
    """Resuelve simbolos de gen (HGNC) y terminos (OLS4, con la ontologia
    indicada) usando y alimentando la cache `cache` (texto -> resultado o
    None). Una fuente que no responde deja la entrada sin resolver, no la
    marca como inexistente."""
    salida: list[dict[str, Any]] = []
    for s in simbolos:
        clave = f"gen:{s.upper()}"
        if clave not in cache:
            try:
                cache[clave] = await gen_hgnc(s)
            except FuenteNoDisponible:
                continue  # sin respuesta: se reintenta otra vez, no se guarda "no existe"
        if cache[clave]:
            salida.append({"texto": s, **cache[clave], "origen": "hgnc"})
    for texto, onto in terminos:
        clave = f"{onto}:{texto.lower()}"
        if clave not in cache:
            try:
                cache[clave] = await termino_ols(texto, onto)
            except FuenteNoDisponible:
                continue
        if cache[clave]:
            salida.append({"texto": texto, **cache[clave], "origen": "ols"})
    return salida


def fusionar(*listas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Una entidad por identificador, con los textos que la nombraron como alias."""
    por_id: dict[str, dict[str, Any]] = {}
    for lista in listas:
        for x in lista:
            if not x.get("id"):
                continue
            actual = por_id.setdefault(x["id"], {"id": x["id"], "etiqueta": x.get("etiqueta") or x.get("simbolo") or x["id"], "ontologia": x.get("ontologia", ""), "tipo": x.get("tipo", "termino"), "alias": []})
            for a in [x.get("texto"), x.get("simbolo")] + list(x.get("alias") or []):
                if a and a not in actual["alias"] and a != actual["etiqueta"]:
                    actual["alias"].append(a)
            for k in ("uniprot", "ensembl", "entrez", "iri"):
                if x.get(k) and not actual.get(k):
                    actual[k] = x[k]
    return list(por_id.values())


def ids_de(entidades: list[dict[str, Any]] | None) -> set[str]:
    return {x["id"] for x in (entidades or []) if x.get("id")}


def comparten(a: list[dict[str, Any]] | None, b: list[dict[str, Any]] | None, minimo: int = 2) -> list[str]:
    """Identificadores canonicos que dos entidades del estado comparten, si
    son al menos `minimo`: es la senal de que hablan de lo mismo con otras
    palabras (para redundancia de hipotesis y deduplicacion de hechos)."""
    comunes = sorted(ids_de(a) & ids_de(b))
    return comunes if len(comunes) >= minimo else []
