"""Segundo bloque de conectores: el resto de los grupos destacados de Claude
Science (regulacion, genomica clinica, cancer, quimica, regulatorio,
literatura, recursos), las herramientas de enriquecimiento, las bases
especificas del Alzheimer y las entradas inertes de lo que Rosa no puede
usar hoy y por que. Donde una fuente no tiene API JSON propia se usa EBI
Search (`ebi.ac.uk/ebisearch`), que indexa ChEBI, Rhea, EMDB, PRIDE,
MetaboLights, MGnify, ArrayExpress y Rfam con un unico contrato.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

from rosa import config
from rosa.conectores.base import Resultado, conector, inerte
from rosa.conectores.bases import HUMANO, _esq, _params_ncbi
from rosa.fuentes.base import Limitador, pedir

_lim = {k: Limitador(v) for k, v in {"ebi": 5.0, "quickgo": 5.0, "interpro": 3.0, "ncbi": 2.0, "eqtl": 2.0, "pheweb": 1.0, "clingen": 1.0, "civic": 2.0, "encode": 2.0, "jaspar": 2.0, "intact": 2.0, "cbio": 2.0, "pubchem": 4.0, "bindingdb": 1.0, "fda": 0.6, "arxiv": 0.5, "grants": 1.0, "antibody": 1.0, "ucsc": 2.0, "enrichr": 1.0, "gprofiler": 1.0, "dgidb": 2.0, "niagads": 1.0, "epmc": 5.0, "gxa": 1.0, "ot": 2.0, "biomart": 0.5}.items()}


# ---------------------------------------------------------------------------
# EBI Search: un contrato para varias bases de EMBL-EBI
# ---------------------------------------------------------------------------


async def _ebisearch(dominio: str, consulta: str, campos: str, n: int = 8) -> Resultado:
    r = await pedir("GET", f"https://www.ebi.ac.uk/ebisearch/ws/rest/{dominio}", _lim["ebi"], params={"query": consulta, "format": "json", "size": n, "fields": campos})
    d = r.json()
    ent = d.get("entries", [])
    datos = [{"id": e.get("id"), **{k: (v[0] if isinstance(v, list) and v else v) for k, v in (e.get("fields") or {}).items()}} for e in ent]
    total = int(d.get("hitCount", len(ent)) or 0)
    return Resultado({"total": total, "entradas": datos}, total, [e.get("id") for e in ent if e.get("id")], None, (True, f"{total} resultados en {dominio}"))


@conector("chebi_buscar", "ChEBI (via EBI Search)", "Entidades quimicas de interes biologico por nombre", "Identificador y nombre canonico de un compuesto que la hipotesis nombra", _esq(consulta="Nombre del compuesto"), "CC BY 4.0", "5 por segundo en Rosa", "https://www.ebi.ac.uk/ebisearch/documentation", grupo="quimica")
async def chebi_buscar(consulta: str) -> Resultado:
    return await _ebisearch("chebi", consulta, "name,description")


@conector("rhea_reacciones", "Rhea (via EBI Search)", "Reacciones bioquimicas en las que participa una proteina o un compuesto", "La reaccion exacta detras de un mecanismo enzimatico", _esq(consulta="Accession UniProt o nombre de compuesto"), "CC BY 4.0", "5 por segundo en Rosa", "https://www.rhea-db.org/help/rest-api", grupo="quimica")
async def rhea_reacciones(consulta: str) -> Resultado:
    return await _ebisearch("rhea", consulta, "name,description")


@conector("emdb_mapas", "EMDB (via EBI Search)", "Mapas de crio-microscopia electronica de una proteina o complejo", "Estructura experimental de complejos grandes (fibrillas de amiloide y tau)", _esq(consulta="Nombre de proteina o accession"), "CC0", "5 por segundo en Rosa", "https://www.ebi.ac.uk/emdb/api", grupo="estructuras")
async def emdb_mapas(consulta: str) -> Resultado:
    return await _ebisearch("emdb", consulta, "title,resolution")


@conector("pride_proyectos", "PRIDE (via EBI Search)", "Proyectos de proteomica por termino", "Datasets proteomicos publicos para comprobar una hipotesis a nivel de proteina", _esq(consulta="Terminos"), "Por proyecto", "5 por segundo en Rosa", "https://www.ebi.ac.uk/pride/ws/archive/v2/", grupo="omicas")
async def pride_proyectos(consulta: str) -> Resultado:
    return await _ebisearch("pride", consulta, "name,description")


@conector("metabolights_estudios", "MetaboLights (via EBI Search)", "Estudios de metabolomica por termino", "Datasets metabolomicos publicos", _esq(consulta="Terminos"), "Por estudio", "5 por segundo en Rosa", "https://www.ebi.ac.uk/metabolights/", grupo="omicas")
async def metabolights_estudios(consulta: str) -> Resultado:
    return await _ebisearch("metabolights", consulta, "name,description")


@conector("mgnify_estudios", "MGnify (via EBI Search)", "Estudios de metagenomica por termino", "Microbioma (eje intestino-cerebro) si una hipotesis lo toca", _esq(consulta="Terminos"), "Por estudio", "5 por segundo en Rosa", "https://www.ebi.ac.uk/metagenomics/api/", grupo="omicas")
async def mgnify_estudios(consulta: str) -> Resultado:
    return await _ebisearch("metagenomics_projects", consulta, "name,description")


@conector("arrayexpress_experimentos", "ArrayExpress y BioStudies", "Experimentos de expresion por termino", "Datasets de expresion que no estan en GEO", _esq(consulta="Terminos"), "Por experimento", "5 por segundo en Rosa", "https://www.ebi.ac.uk/biostudies/help", grupo="omicas")
async def arrayexpress_experimentos(consulta: str) -> Resultado:
    r = await pedir("GET", "https://www.ebi.ac.uk/biostudies/api/v1/search", _lim["ebi"], params={"query": consulta, "collection": "arrayexpress", "pageSize": 8})
    d = r.json()
    hits = d.get("hits", [])
    datos = [{"accession": h.get("accession"), "titulo": (h.get("title") or "")[:160], "tipo": h.get("type"), "fecha": h.get("release_date")} for h in hits]
    return Resultado({"total": d.get("totalHits", len(hits)), "experimentos": datos}, d.get("totalHits", len(hits)), [h.get("accession") for h in hits if h.get("accession")], None, (True, f"{d.get('totalHits', 0)} experimentos"))


@conector("rfam_familia", "Rfam (via EBI Search)", "Familias de RNA no codificante por termino", "Si la hipotesis toca un RNA no codificante", _esq(consulta="Nombre o accession"), "CC0", "5 por segundo en Rosa", "https://rfam.org/", grupo="rna")
async def rfam_familia(consulta: str) -> Resultado:
    return await _ebisearch("rfam", consulta, "name,description")


# ---------------------------------------------------------------------------
# Genes, ontologias, dominios
# ---------------------------------------------------------------------------


@conector("quickgo_anotaciones", "Gene Ontology (QuickGO)", "Anotaciones GO de proceso biologico de una proteina", "Que hace la proteina segun la ontologia, con identificadores GO", _esq(uniprot="Accession UniProt"), "CC BY 4.0", "5 por segundo en Rosa", "https://www.ebi.ac.uk/QuickGO/api/index.html", grupo="genes_ontologias")
async def quickgo_anotaciones(uniprot: str) -> Resultado:
    r = await pedir("GET", "https://www.ebi.ac.uk/QuickGO/services/annotation/search", _lim["quickgo"], params={"geneProductId": uniprot, "aspect": "biological_process", "limit": 25}, headers={"Accept": "application/json"})
    d = r.json()
    res = d.get("results", [])
    vistos: dict[str, str] = {}
    for a in res:
        vistos.setdefault(a.get("goId"), a.get("goName"))
    datos = [{"go": k, "nombre": v} for k, v in vistos.items()]
    return Resultado(datos, d.get("numberOfHits", len(res)), list(vistos)[:20], None, (True, f"{len(vistos)} terminos distintos"))


@conector("interpro_dominios", "InterPro y Pfam", "Dominios y familias de una proteina", "La arquitectura de dominios que sostiene o refuta un mecanismo de union", _esq(uniprot="Accession UniProt"), "CC0", "3 por segundo en Rosa", "https://interpro-documentation.readthedocs.io/", grupo="proteinas")
async def interpro_dominios(uniprot: str) -> Resultado:
    r = await pedir("GET", f"https://www.ebi.ac.uk/interpro/api/entry/interpro/protein/uniprot/{quote(uniprot)}", _lim["interpro"], headers={"Accept": "application/json"})
    if r.status_code == 204 or not r.text.strip():
        return Resultado([], 0, [], None, (True, "sin dominios (respuesta vacia legitima)"))
    d = r.json()
    res = d.get("results", [])
    datos = [{"id": (x.get("metadata") or {}).get("accession"), "nombre": (x.get("metadata") or {}).get("name"), "tipo": (x.get("metadata") or {}).get("type")} for x in res]
    return Resultado(datos, d.get("count", len(res)), [x["id"] for x in datos if x["id"]], None, (True, f"{len(datos)} entradas InterPro"))


@conector("biomart_gen", "Ensembl BioMart", "Identificadores cruzados de un gen (HGNC, Entrez, UniProt) por consulta BioMart", "Mapeo de identificadores en bloque cuando MyGene no baste", _esq(ensembl="Identificador Ensembl"), "Sin restricciones", "0,5 por segundo en Rosa (servicio lento)", "https://www.ensembl.org/info/data/biomart/biomart_restful.html", grupo="genes_ontologias")
async def biomart_gen(ensembl: str) -> Resultado:
    xml = f'<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE Query><Query virtualSchemaName="default" formatter="TSV" header="0" uniqueRows="1" count="" datasetConfigVersion="0.6"><Dataset name="hsapiens_gene_ensembl" interface="default"><Filter name="ensembl_gene_id" value="{ensembl}"/><Attribute name="ensembl_gene_id"/><Attribute name="hgnc_symbol"/><Attribute name="entrezgene_id"/><Attribute name="uniprotswissprot"/><Attribute name="description"/></Dataset></Query>'
    r = await pedir("GET", "https://www.ensembl.org/biomart/martservice", _lim["biomart"], params={"query": xml})
    filas = [l.split("\t") for l in r.text.strip().splitlines() if l.strip()]
    datos = [{"ensembl": f[0], "hgnc": f[1], "entrez": f[2], "uniprot": f[3], "descripcion": f[4][:120] if len(f) > 4 else ""} for f in filas if len(f) >= 4]
    return Resultado(datos, len(datos), [ensembl], None, (bool(datos), f"{len(datos)} filas"))


@conector("clinvar_gen", "ClinVar (NCBI E-utilities)", "Cuantas variantes de un gen tienen registro en ClinVar y cuantas con la enfermedad", "Si el gen ya tiene variantes con significado clinico para el Alzheimer", _esq(simbolo="Simbolo HGNC", enfermedad="Termino de enfermedad, por ejemplo Alzheimer"), "Dominio publico", "3 por segundo, 10 con clave NCBI", "https://www.ncbi.nlm.nih.gov/clinvar/docs/programmatic_access/", grupo="variantes")
async def clinvar_gen(simbolo: str, enfermedad: str = "Alzheimer") -> Resultado:
    r = await pedir("GET", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", _lim["ncbi"], params=_params_ncbi(db="clinvar", term=f"{simbolo}[gene]", retmax=0))
    total = int(r.json().get("esearchresult", {}).get("count", 0) or 0)
    r2 = await pedir("GET", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", _lim["ncbi"], params=_params_ncbi(db="clinvar", term=f"{simbolo}[gene] AND {enfermedad}[dis]", retmax=5))
    es = r2.json().get("esearchresult", {})
    con = int(es.get("count", 0) or 0)
    return Resultado({"variantes_gen": total, "con_enfermedad": con, "ids": es.get("idlist", [])}, total, es.get("idlist", []), None, (True, f"{total} variantes del gen; {con} con {enfermedad}"))


# ---------------------------------------------------------------------------
# Genetica humana y genomica clinica
# ---------------------------------------------------------------------------


@conector("finngen_gen", "FinnGen (PheWeb R12)", "Asociaciones de fenotipos con un gen en la cohorte finlandesa", "Replicacion genetica independiente en otra poblacion", _esq(simbolo="Simbolo HGNC"), "Terminos FinnGen (resumenes publicos)", "1 por segundo en Rosa", "https://r12.finngen.fi/", grupo="genetica_humana")
async def finngen_gen(simbolo: str) -> Resultado:
    r = await pedir("GET", f"https://r12.finngen.fi/api/gene_phenos/{quote(simbolo)}", _lim["pheweb"])
    d = r.json()
    filas = d.get("phenotypes", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
    def mlogp(x: dict[str, Any]) -> float:
        return float((x.get("assoc") or {}).get("mlogp") or 0)
    filas.sort(key=mlogp, reverse=True)
    def fila(x: dict[str, Any]) -> dict[str, Any]:
        a = x.get("assoc") or {}
        ph = x.get("pheno") or {}
        v = a.get("variant") or x.get("variant") or {}
        return {"fenotipo": ph.get("phenostring") or a.get("phenocode"), "codigo": a.get("phenocode"), "mlogp": a.get("mlogp"), "beta": a.get("beta"), "n_casos": a.get("n_case"), "variante": (v.get("varid") if isinstance(v, dict) else v), "rsid": ((v.get("annotation") or {}).get("gnomad") or {}).get("rsids") if isinstance(v, dict) else None}
    datos = [fila(x) for x in filas[:10]]
    ad = [fila(x) for x in filas if "alzheimer" in str(((x.get("pheno") or {}).get("phenostring") or (x.get("assoc") or {}).get("phenocode") or "")).lower()][:5]
    return Resultado({"total": len(filas), "mejores": datos, "alzheimer": ad}, len(filas), [x["codigo"] for x in datos if x.get("codigo")], "R12", (True, f"{len(filas)} fenotipos; {len(ad)} de Alzheimer"))


_cache_clingen: dict[str, Any] = {"t": 0.0, "filas": []}


@conector("clingen_gen", "ClinGen", "Validez gen-enfermedad curada por paneles de expertos (fichero oficial de curaciones, cacheado un dia)", "Si un panel ya clasifico la relacion gen-enfermedad (definitiva, moderada, limitada, refutada)", _esq(simbolo="Simbolo HGNC"), "CC0", "1 descarga al dia", "https://search.clinicalgenome.org/kb/gene-validity/download", grupo="genomica_clinica")
async def clingen_gen(simbolo: str) -> Resultado:
    import csv
    import io

    if time.time() - _cache_clingen["t"] > 86400 or not _cache_clingen["filas"]:
        r = await pedir("GET", "https://search.clinicalgenome.org/kb/gene-validity/download", _lim["clingen"])
        filas = [f for f in csv.reader(io.StringIO(r.text)) if len(f) >= 7 and f[0] and not f[0].startswith("+") and f[0] not in ("GENE SYMBOL", "CLINGEN GENE DISEASE VALIDITY CURATIONS") and not f[0].startswith(("FILE CREATED", "WEBPAGE"))]
        _cache_clingen.update(t=time.time(), filas=filas)
    hits = [f for f in _cache_clingen["filas"] if f[0].upper() == simbolo.upper()]
    datos = [{"gen": f[0], "enfermedad": f[2], "mondo": f[3], "herencia": f[4], "clasificacion": f[6], "fecha": f[8] if len(f) > 8 else ""} for f in hits]
    return Resultado(datos, len(hits), [f[3] for f in hits], None, (True, f"{len(hits)} curaciones de {len(_cache_clingen['filas'])}"))


@conector("civic_gen", "CIViC (GraphQL)", "Interpretaciones clinicas de variantes de un gen (oncologia)", "Contexto oncologico del gen; poco relevante salvo genes compartidos", _esq(simbolo="Simbolo HGNC"), "CC0", "2 por segundo en Rosa", "https://griffithlab.github.io/civic-v2/", grupo="genomica_clinica")
async def civic_gen(simbolo: str) -> Resultado:
    q = "query($n: String!) { genes(name: $n) { nodes { id name description variants { totalCount } } } }"
    r = await pedir("POST", "https://civicdb.org/api/graphql", _lim["civic"], json={"query": q, "variables": {"n": simbolo}})
    nodos = (((r.json().get("data") or {}).get("genes") or {}).get("nodes")) or []
    datos = [{"id": n.get("id"), "gen": n.get("name"), "descripcion": (n.get("description") or "")[:200], "variantes": (n.get("variants") or {}).get("totalCount")} for n in nodos]
    return Resultado(datos, len(nodos), [str(n["id"]) for n in datos if n.get("id")], None, (True, f"{len(nodos)} genes"))


@conector("opentargets_graphql", "Open Targets Platform (GraphQL; MCP oficial equivalente)", "Consulta GraphQL libre a Open Targets, para lo que la consulta fija de asociacion no cubre (tractabilidad, seguridad, farmacos, credible sets)", "Lo que el MCP oficial de Open Targets ofrece: query_open_targets_graphql", _esq(consulta="Consulta GraphQL", variables="JSON con las variables"), "CC0", "No publicado; 2 por segundo en Rosa", "https://platform-docs.opentargets.org/data-access/graphql-api", grupo="genomica_clinica")
async def opentargets_graphql(consulta: str, variables: str = "{}") -> Resultado:
    import json as _json

    r = await pedir("POST", "https://api.platform.opentargets.org/api/v4/graphql", _lim["ot"], json={"query": consulta, "variables": _json.loads(variables or "{}")})
    d = r.json()
    if d.get("errors"):
        return Resultado(d, 0, [], None, (False, "GraphQL devolvio errores: " + str(d["errors"])[:160]))
    return Resultado(d.get("data"), 1, [], None, (True, "consulta valida"))


@conector("niagads_gen", "NIAGADS Open Access (vista previa)", "Registro de un gen en NIAGADS: variantes de ADSP y sumstats de Alzheimer", "La base genetica especifica del Alzheimer; API en vista previa", _esq(ensembl="Identificador Ensembl"), "No documentada con claridad", "En vista previa, sin cifra publicada", "https://api.niagads.org/docs/introduction/getting-started", grupo="alzheimer")
async def niagads_gen(ensembl: str) -> Resultado:
    r = await pedir("GET", f"https://api.niagads.org/genomics/record/gene/{quote(ensembl)}", _lim["niagads"], headers={"Accept": "application/json"})
    d = r.json()
    return Resultado(d, 1 if d else 0, [ensembl], None, (bool(d), "registro devuelto" if d else "sin registro"))


# ---------------------------------------------------------------------------
# Regulacion, interacciones, cancer
# ---------------------------------------------------------------------------


@conector("encode_experimentos", "ENCODE", "Experimentos de ENCODE cuya diana es un gen (ChIP-seq y otros)", "Regulacion: quien se une al gen y donde", _esq(simbolo="Simbolo HGNC"), "CC BY 4.0", "2 por segundo en Rosa", "https://www.encodeproject.org/help/rest-api/", grupo="regulacion")
async def encode_experimentos(simbolo: str) -> Resultado:
    r = await pedir("GET", "https://www.encodeproject.org/search/", _lim["encode"], params={"type": "Experiment", "target.label": simbolo, "format": "json", "limit": 8}, headers={"Accept": "application/json"})
    d = r.json()
    g = d.get("@graph", [])
    datos = [{"accession": x.get("accession"), "ensayo": x.get("assay_title"), "biosample": (x.get("biosample_ontology") or {}).get("term_name")} for x in g]
    return Resultado({"total": d.get("total", len(g)), "experimentos": datos}, d.get("total", len(g)), [x["accession"] for x in datos if x["accession"]], None, (True, f"{d.get('total', 0)} experimentos"))


@conector("jaspar_motivos", "JASPAR", "Matrices de motivos de union de un factor de transcripcion", "Si el factor que la hipotesis nombra tiene motivo conocido", _esq(nombre="Nombre del factor de transcripcion"), "CC BY 4.0", "2 por segundo en Rosa", "https://jaspar.elixir.no/api/v1/docs/", grupo="regulacion")
async def jaspar_motivos(nombre: str) -> Resultado:
    r = await pedir("GET", "https://jaspar.elixir.no/api/v1/matrix/", _lim["jaspar"], params={"search": nombre, "format": "json", "page_size": 8, "collection": "CORE", "tax_group": "vertebrates"})
    d = r.json()
    res = d.get("results", [])
    datos = [{"matriz": x.get("matrix_id"), "nombre": x.get("name"), "coleccion": x.get("collection")} for x in res]
    return Resultado({"total": d.get("count", len(res)), "motivos": datos}, d.get("count", len(res)), [x["matriz"] for x in datos if x["matriz"]], None, (True, f"{d.get('count', 0)} matrices"))


@conector("unibind_sitios", "UniBind", "Conjuntos de sitios de union directos de un factor de transcripcion", "Sitios de union con soporte experimental", _esq(nombre="Nombre del factor"), "CC BY 4.0", "2 por segundo en Rosa", "https://unibind.uio.no/api/", grupo="regulacion")
async def unibind_sitios(nombre: str) -> Resultado:
    r = await pedir("GET", "https://unibind.uio.no/api/v1/datasets/", _lim["jaspar"], params={"tf": nombre, "format": "json", "page_size": 8})
    d = r.json()
    res = d.get("results", [])
    return Resultado({"total": d.get("count", len(res)), "datasets": [{"id": x.get("id"), "celula": x.get("cell_line"), "tf": x.get("tf_name")} for x in res]}, d.get("count", len(res)), [str(x.get("id")) for x in res if x.get("id")], None, (True, f"{d.get('count', 0)} datasets"))


@conector("intact_interacciones", "IntAct", "Interacciones moleculares con evidencia experimental de una proteina", "Interactores con experimento detras, no solo predichos", _esq(uniprot="Accession UniProt"), "CC BY 4.0", "2 por segundo en Rosa", "https://www.ebi.ac.uk/intact/documentation", grupo="estructuras")
async def intact_interacciones(uniprot: str) -> Resultado:
    r = await pedir("POST", "https://www.ebi.ac.uk/intact/ws/interaction/findInteractionWithFacet", _lim["intact"], data={"query": uniprot, "page": 0, "pageSize": 10})
    d = r.json().get("data") or {}
    cont = d.get("content", [])
    datos = [{"a": x.get("moleculeA"), "b": x.get("moleculeB"), "tipo": x.get("type"), "deteccion": x.get("detectionMethod"), "miscore": x.get("intactMiscore")} for x in cont]
    total = d.get("totalElements", len(cont))
    return Resultado({"total": total, "interacciones": datos}, total, [], None, (True, f"{total} interacciones con evidencia experimental"))


@conector("complexportal_complejos", "Complex Portal", "Complejos macromoleculares curados que contienen una proteina", "Con quien forma complejo la diana", _esq(uniprot="Accession UniProt"), "CC0", "2 por segundo en Rosa", "https://www.ebi.ac.uk/intact/complex-ws/", grupo="estructuras")
async def complexportal_complejos(uniprot: str) -> Resultado:
    r = await pedir("GET", f"https://www.ebi.ac.uk/intact/complex-ws/search/{quote(uniprot)}", _lim["intact"], params={"format": "json"})
    d = r.json()
    el = d.get("elements", [])
    datos = [{"id": x.get("complexAC"), "nombre": x.get("complexName"), "organismo": x.get("organismName")} for x in el]
    return Resultado({"total": d.get("size", len(el)), "complejos": datos}, d.get("size", len(el)), [x["id"] for x in datos if x["id"]], None, (True, f"{d.get('size', 0)} complejos"))


@conector("cbioportal_gen", "cBioPortal", "Ficha de un gen en cBioPortal (identificadores) y numero de estudios", "Contexto oncologico; util solo para genes compartidos con cancer", _esq(simbolo="Simbolo HGNC"), "Por estudio (mayoria abiertos)", "2 por segundo en Rosa", "https://www.cbioportal.org/api", grupo="cancer")
async def cbioportal_gen(simbolo: str) -> Resultado:
    r = await pedir("GET", f"https://www.cbioportal.org/api/genes/{quote(simbolo)}", _lim["cbio"], headers={"Accept": "application/json"})
    d = r.json()
    return Resultado({"entrez": d.get("entrezGeneId"), "simbolo": d.get("hugoGeneSymbol"), "tipo": d.get("type")}, 1 if d.get("entrezGeneId") else 0, [str(d.get("entrezGeneId"))] if d.get("entrezGeneId") else [], None, (bool(d.get("entrezGeneId")), "gen resuelto"))


@conector("ucsc_genes_region", "UCSC Genome Browser", "Genes anotados (knownGene) en una region de hg38", "Que hay alrededor de un locus GWAS", _esq(cromosoma="chr19", inicio="posicion inicial", fin="posicion final"), "Sin restricciones", "2 por segundo en Rosa", "https://api.genome.ucsc.edu/", grupo="genomas")
async def ucsc_genes_region(cromosoma: str, inicio: str, fin: str) -> Resultado:
    r = await pedir("GET", "https://api.genome.ucsc.edu/getData/track", _lim["ucsc"], params={"genome": "hg38", "track": "knownGene", "chrom": cromosoma, "start": int(inicio), "end": int(fin)})
    d = r.json()
    genes = d.get("knownGene", [])
    nombres = sorted({g.get("geneName") for g in genes if g.get("geneName")})
    return Resultado({"transcritos": len(genes), "genes": nombres[:30]}, len(genes), nombres[:20], "hg38", (True, f"{len(nombres)} genes en la region"))


# ---------------------------------------------------------------------------
# Quimica y regulatorio
# ---------------------------------------------------------------------------


@conector("pubchem_compuesto", "PubChem (PUG REST)", "Propiedades de un compuesto por nombre: formula, peso, SMILES, IUPAC", "Identidad quimica de un farmaco o metabolito que la hipotesis nombra", _esq(nombre="Nombre del compuesto"), "Dominio publico", "5 por segundo, 400 por minuto", "https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest", grupo="quimica")
async def pubchem_compuesto(nombre: str) -> Resultado:
    r = await pedir("GET", f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(nombre)}/property/MolecularFormula,MolecularWeight,IUPACName,CanonicalSMILES/JSON", _lim["pubchem"])
    props = (r.json().get("PropertyTable") or {}).get("Properties", [])
    datos = [{"cid": p.get("CID"), "formula": p.get("MolecularFormula"), "peso": p.get("MolecularWeight"), "iupac": p.get("IUPACName"), "smiles": p.get("CanonicalSMILES")} for p in props]
    return Resultado(datos, len(datos), [str(p["cid"]) for p in datos if p.get("cid")], None, (len(datos) == 1, f"{len(datos)} compuestos con ese nombre"))


@conector("bindingdb_ligandos", "BindingDB", "Ligandos con afinidad medida contra una proteina (por UniProt), con corte de afinidad", "Cuantos compuestos se unen a la diana y con que afinidad", _esq(uniprot="Accession UniProt", corte_nM="Afinidad maxima en nM, por ejemplo 1000"), "CC BY 3.0 US", "1 por segundo en Rosa", "https://www.bindingdb.org/rwd/bind/BindingDBRESTfulAPI.jsp", grupo="quimica")
async def bindingdb_ligandos(uniprot: str, corte_nM: str = "1000") -> Resultado:
    r = await pedir("GET", "https://bindingdb.org/axis2/services/BDBService/getLigandsByUniprots", _lim["bindingdb"], params={"uniprot": uniprot, "cutoff": corte_nM, "response": "application/json"})
    d = r.json()
    aff = ((d.get("getLigandsByUniprotsResponse") or {}).get("affinities")) or []
    aff = aff if isinstance(aff, list) else [aff]
    datos = [{"monomero": a.get("monomerid"), "smiles": (a.get("smile") or "")[:80], "tipo": a.get("affinity_type"), "afinidad_nM": a.get("affinity")} for a in aff[:10]]
    return Resultado({"total": len(aff), "ligandos": datos}, len(aff), [str(a.get("monomerid")) for a in aff[:20] if a.get("monomerid")], None, (True, f"{len(aff)} ligandos bajo {corte_nM} nM"))


@conector("openfda_etiquetas", "openFDA (FDA drug data)", "Etiquetas de farmacos aprobados cuyo texto de indicaciones menciona un termino", "Que farmacos estan aprobados para la indicacion y que dice su etiqueta", _esq(termino="Termino en indicaciones, por ejemplo Alzheimer"), "Dominio publico", "40 por minuto sin clave", "https://open.fda.gov/apis/drug/label/", grupo="regulatorio")
async def openfda_etiquetas(termino: str) -> Resultado:
    from rosa.fuentes.base import FuenteNoDisponible

    try:
        r = await pedir("GET", "https://api.fda.gov/drug/label.json", _lim["fda"], params={"search": f"indications_and_usage:{termino}", "limit": 10})
    except FuenteNoDisponible as ex:
        if "NOT_FOUND" in str(ex) or "No matches" in str(ex):
            return Resultado({"total": 0, "etiquetas": []}, 0, [], None, (True, "cero etiquetas (openFDA responde 404 cuando no hay coincidencias; probar con comodin, por ejemplo alzheimer*)"))
        raise
    d = r.json()
    res = d.get("results", [])
    datos = [{"marca": ((x.get("openfda") or {}).get("brand_name") or [""])[0], "generico": ((x.get("openfda") or {}).get("generic_name") or [""])[0], "indicaciones": (x.get("indications_and_usage") or [""])[0][:200]} for x in res]
    total = ((d.get("meta") or {}).get("results") or {}).get("total", len(res))
    return Resultado({"total": total, "etiquetas": datos}, total, [x["generico"] for x in datos if x["generico"]], None, (True, f"{total} etiquetas"))


# ---------------------------------------------------------------------------
# Enriquecimiento y farmaco-gen
# ---------------------------------------------------------------------------


@conector("enrichr_enriquecer", "Enrichr", "Sobre representacion de una lista de genes en una libreria (GO, KEGG, Reactome, tipos celulares)", "Que proceso o tipo celular comparte una lista de genes de un analisis", _esq(genes="Simbolos separados por coma", libreria="Por ejemplo GO_Biological_Process_2023 o Reactome_2022"), "Uso libre con cita; algunas librerias con licencia propia", "1 por segundo en Rosa", "https://maayanlab.cloud/Enrichr/help#api", grupo="enriquecimiento")
async def enrichr_enriquecer(genes: str, libreria: str = "GO_Biological_Process_2023") -> Resultado:
    lista = [g.strip() for g in genes.replace(";", ",").split(",") if g.strip()]
    r = await pedir("POST", "https://maayanlab.cloud/Enrichr/addList", _lim["enrichr"], files={"list": (None, "\n".join(lista)), "description": (None, "rosa")})
    uid = r.json().get("userListId")
    r2 = await pedir("GET", "https://maayanlab.cloud/Enrichr/enrich", _lim["enrichr"], params={"userListId": uid, "backgroundType": libreria})
    filas = r2.json().get(libreria, [])
    datos = [{"termino": f[1], "p": f[2], "p_ajustada": f[6], "genes": f[5][:10]} for f in filas[:10]]
    return Resultado({"libreria": libreria, "n_genes": len(lista), "terminos": datos}, len(filas), [], None, (len(lista) >= 3, f"{len(lista)} genes enviados; {len(filas)} terminos"))


@conector("gprofiler_enriquecer", "g:Profiler", "Sobre representacion multi fuente (GO, Reactome, WikiPathways, HP) de una lista de genes", "Enriquecimiento con correccion g:SCS y varias fuentes a la vez", _esq(genes="Simbolos separados por coma"), "Uso libre con cita", "1 por segundo en Rosa", "https://biit.cs.ut.ee/gprofiler/page/apis", grupo="enriquecimiento")
async def gprofiler_enriquecer(genes: str) -> Resultado:
    lista = [g.strip() for g in genes.replace(";", ",").split(",") if g.strip()]
    r = await pedir("POST", "https://biit.cs.ut.ee/gprofiler/api/gost/profile/", _lim["gprofiler"], json={"organism": "hsapiens", "query": lista, "sources": ["GO:BP", "REAC", "HP"], "no_evidences": True})
    res = r.json().get("result", [])
    res.sort(key=lambda x: x.get("p_value", 1))
    datos = [{"fuente": x.get("source"), "termino": x.get("name"), "id": x.get("native"), "p": x.get("p_value"), "tamano": x.get("term_size")} for x in res[:12]]
    return Resultado({"n_genes": len(lista), "terminos": datos}, len(res), [x["id"] for x in datos if x["id"]], None, (len(lista) >= 3, f"{len(res)} terminos significativos"))


@conector("dgidb_gen", "DGIdb 5 (GraphQL)", "Interacciones farmaco-gen agregadas de mas de 40 fuentes", "Que farmacos tocan el gen y con que tipo de interaccion", _esq(simbolo="Simbolo HGNC"), "Por fuente (software MIT)", "2 por segundo en Rosa", "https://dgidb.org/api", grupo="farmacos")
async def dgidb_gen(simbolo: str) -> Resultado:
    q = "query($n: [String!]!) { genes(names: $n) { nodes { name interactions { drug { name approved } interactionTypes { type } interactionScore } } } }"
    r = await pedir("POST", "https://dgidb.org/api/graphql", _lim["dgidb"], json={"query": q, "variables": {"n": [simbolo]}})
    nodos = (((r.json().get("data") or {}).get("genes") or {}).get("nodes")) or []
    inter = nodos[0].get("interactions", []) if nodos else []
    inter.sort(key=lambda x: -(x.get("interactionScore") or 0))
    datos = [{"farmaco": (x.get("drug") or {}).get("name"), "aprobado": (x.get("drug") or {}).get("approved"), "tipos": [t.get("type") for t in x.get("interactionTypes", [])], "puntuacion": x.get("interactionScore")} for x in inter[:15]]
    return Resultado({"total": len(inter), "interacciones": datos}, len(inter), [d["farmaco"] for d in datos if d["farmaco"]], None, (True, f"{len(inter)} interacciones"))


# ---------------------------------------------------------------------------
# Literatura y recursos
# ---------------------------------------------------------------------------


@conector("epmc_anotaciones", "Europe PMC Annotations API", "Entidades anotadas por mineria de texto en un articulo: genes y proteinas, enfermedades, quimicos", "Que genes y enfermedades nombra de verdad un articulo, sin leerlo entero", _esq(pmid="PMID del articulo"), "Por articulo (texto abierto)", "10 por segundo, 500 por minuto", "https://europepmc.org/annotationsapi", grupo="literatura")
async def epmc_anotaciones(pmid: str) -> Resultado:
    r = await pedir("GET", "https://www.ebi.ac.uk/europepmc/annotations_api/annotationsByArticleIds", _lim["epmc"], params={"articleIds": f"MED:{pmid}", "type": "Gene_Proteins,Diseases,Chemicals", "format": "JSON"})
    d = r.json()
    arts = d if isinstance(d, list) else []
    anots = arts[0].get("annotations", []) if arts else []
    por_tipo: dict[str, dict[str, int]] = {}
    for a in anots:
        por_tipo.setdefault(a.get("type", "otro"), {})
        k = a.get("exact") or ""
        por_tipo[a["type"]][k] = por_tipo[a["type"]].get(k, 0) + 1
    datos = {t: sorted(v.items(), key=lambda kv: -kv[1])[:12] for t, v in por_tipo.items()}
    return Resultado(datos, len(anots), [], None, (bool(arts), f"{len(anots)} anotaciones en {len(por_tipo)} tipos"))


_cache_gxa: dict[str, Any] = {"t": 0.0, "exps": []}


@conector("expression_atlas_experimentos", "Expression Atlas (EMBL-EBI)", "Experimentos curados de expresion basal y diferencial cuyo titulo menciona un termino", "Datasets ya curados y reanalizados, con contraste enfermedad frente a control", _esq(termino="Texto a buscar"), "Terminos EMBL-EBI", "1 por segundo en Rosa; el catalogo se cachea una hora", "https://www.ebi.ac.uk/gxa/help/index.html", grupo="expresion")
async def expression_atlas_experimentos(termino: str) -> Resultado:
    if time.time() - _cache_gxa["t"] > 3600 or not _cache_gxa["exps"]:
        r = await pedir("GET", "https://www.ebi.ac.uk/gxa/json/experiments", _lim["gxa"])
        d = r.json()
        _cache_gxa.update(t=time.time(), exps=d.get("experiments", d if isinstance(d, list) else []))
    t = termino.lower()
    hits = [e for e in _cache_gxa["exps"] if t in (str(e.get("experimentDescription", "")) + " " + str(e.get("experimentAccession", ""))).lower()]
    datos = [{"accession": e.get("experimentAccession"), "descripcion": (e.get("experimentDescription") or "")[:160], "tipo": e.get("experimentType"), "especie": e.get("species"), "ensayos": e.get("numberOfAssays")} for e in hits[:12]]
    return Resultado(datos, len(hits), [e["accession"] for e in datos if e["accession"]], None, (True, f"{len(hits)} experimentos de {len(_cache_gxa['exps'])}"))


@conector("arxiv_buscar", "arXiv", "Preprints de arXiv por termino (metodos, estadistica, aprendizaje automatico aplicado)", "Metodos nuevos de analisis antes de que salgan en revista", _esq(consulta="Terminos"), "Por articulo (licencias arXiv)", "1 cada 3 segundos recomendado; 0,5 por segundo en Rosa", "https://info.arxiv.org/help/api/", grupo="literatura")
async def arxiv_buscar(consulta: str) -> Resultado:
    r = await pedir("GET", "https://export.arxiv.org/api/query", _lim["arxiv"], params={"search_query": f"all:{consulta}", "max_results": 6})
    ns = {"a": "http://www.w3.org/2005/Atom", "o": "http://a9.com/-/spec/opensearch/1.1/"}
    root = ET.fromstring(r.text)
    ent = root.findall("a:entry", ns)
    datos = [{"id": (e.findtext("a:id", default="", namespaces=ns) or "").rsplit("/", 1)[-1], "titulo": " ".join((e.findtext("a:title", default="", namespaces=ns) or "").split())[:160], "fecha": (e.findtext("a:published", default="", namespaces=ns) or "")[:10]} for e in ent]
    total = int(root.findtext("o:totalResults", default="0", namespaces=ns) or 0)
    return Resultado({"total": total, "articulos": datos}, total, [d["id"] for d in datos if d["id"]], None, (True, f"{total} resultados"))


@conector("grants_buscar", "Grants.gov", "Convocatorias federales de EE. UU. por palabra clave", "Financiacion abierta para la linea de trabajo", _esq(palabra="Palabra clave"), "Dominio publico", "1 por segundo en Rosa", "https://www.grants.gov/api/", grupo="recursos")
async def grants_buscar(palabra: str) -> Resultado:
    r = await pedir("POST", "https://api.grants.gov/v1/api/search2", _lim["grants"], json={"keyword": palabra, "rows": 8, "oppStatuses": "forecasted|posted"})
    d = (r.json().get("data") or {})
    hits = d.get("oppHits", [])
    datos = [{"numero": h.get("number"), "titulo": (h.get("title") or "")[:160], "agencia": h.get("agencyCode"), "cierre": h.get("closeDate")} for h in hits]
    return Resultado({"total": d.get("hitCount", len(hits)), "convocatorias": datos}, d.get("hitCount", len(hits)), [h["numero"] for h in datos if h["numero"]], None, (True, f"{d.get('hitCount', 0)} convocatorias"))


@conector("antibodyregistry_buscar", "Antibody Registry", "Anticuerpos registrados (RRID) contra una diana", "Reactivos con identificador para el protocolo del experimento", _esq(diana="Nombre de la proteina diana"), "CC BY 4.0", "1 por segundo en Rosa", "https://www.antibodyregistry.org/", grupo="recursos")
async def antibodyregistry_buscar(diana: str) -> Resultado:
    r = await pedir("GET", "https://www.antibodyregistry.org/api/antibodies", _lim["antibody"], params={"search": diana, "page": 1, "size": 8}, headers={"Accept": "application/json"})
    d = r.json()
    items = d.get("items", [])
    datos = [{"rrid": x.get("abId") or x.get("rrid"), "nombre": (x.get("abName") or "")[:120], "diana": x.get("abTarget"), "vendedor": x.get("vendorName"), "clonalidad": x.get("clonality")} for x in items[:8]]
    total = d.get("totalElements", len(items))
    return Resultado({"total": total, "anticuerpos": datos}, total, [str(x["rrid"]) for x in datos if x["rrid"]], None, (any((x.get("diana") or "").upper().startswith(diana.upper()) for x in datos), f"{total} resultados; la busqueda es de texto libre, revisar la diana de cada uno"))


@conector("cellguide_tipo_celular", "CellGuide (via Cell Ontology en OLS4)", "Resuelve un tipo celular a su identificador de Cell Ontology con definicion", "Que Rosa nombre los tipos celulares (microglia, astrocito) con identificador, como hace CellGuide", _esq(termino="Nombre del tipo celular"), "CL: CC BY 4.0", "5 por segundo en Rosa", "https://cellxgene.cziscience.com/cellguide", grupo="socios")
async def cellguide_tipo_celular(termino: str) -> Resultado:
    r = await pedir("GET", "https://www.ebi.ac.uk/ols4/api/search", _lim["ebi"], params={"q": termino, "ontology": "cl", "rows": 5})
    docs = r.json().get("response", {}).get("docs", [])
    datos = [{"id": d.get("short_form"), "etiqueta": d.get("label"), "definicion": (d.get("description") or [""])[0][:240], "cellguide": f"https://cellxgene.cziscience.com/cellguide/{d.get('short_form')}" if d.get("short_form") else None} for d in docs]
    return Resultado(datos, len(datos), [d["id"] for d in datos if d["id"]], None, (any((d["etiqueta"] or "").lower() == termino.lower() for d in datos), "coincidencia exacta" if any((d["etiqueta"] or "").lower() == termino.lower() for d in datos) else "sin coincidencia exacta"))


# ---------------------------------------------------------------------------
# Lo que existe en Claude Science y Rosa no puede usar hoy, con su motivo
# ---------------------------------------------------------------------------

inerte("benchling", "Benchling", "Cuaderno electronico y registros de experimentos del laboratorio", "Preguntas sobre experimentos propios", "requiere_cuenta", "Tenant Enterprise de pago con clave de API; el programa no tiene Benchling. Cuando lo tenga: SDK benchling-sdk, 60 peticiones por 30 s", "https://docs.benchling.com", "socios")
inerte("biorender", "BioRender", "Busqueda y generacion de figuras cientificas", "Figuras para el dossier", "requiere_cuenta", "Servidor MCP cerrado autenticado por usuario de BioRender; sin API publica", "https://www.biorender.com", "socios")
inerte("tenx_cloud", "10x Genomics Cloud Analysis", "Cell Ranger y Space Ranger en la nube de 10x (30 tools MCP, MIT)", "Procesar FASTQ de celula unica propios", "requiere_cuenta", "Cuenta 10x y token; Rosa trabaja con matrices ya procesadas (GEO, CELLxGENE, SEA-AD)", "https://github.com/10XGenomics/txg-mcp", "socios")
inerte("owkin", "Owkin (Pathology Explorer)", "Laminas de patologia de TCGA convertidas en datos consultables", "Patologia digital oncologica", "requiere_cuenta", "MCP cerrado de Owkin; dominio oncologico", "https://www.owkin.com", "socios")
inerte("medidata", "Medidata", "Ranking predictivo de centros de ensayo y ayuda de plataforma", "Reclutamiento de centros para un ensayo propio", "requiere_cuenta", "Plataforma comercial de ensayos clinicos", "https://www.medidata.com", "socios")
inerte("wiley_scholar_gateway", "Wiley Scholar Gateway", "Busqueda semantica en revistas Wiley con DOI verificable", "Texto completo de Wiley con licencia institucional", "requiere_cuenta", "OAuth institucional; Rosa usa Unpaywall y Europe PMC para el texto abierto", "https://docs.scholargateway.ai/", "socios")
inerte("consensus", "Consensus", "Sintesis sobre 220 millones de articulos", "Segunda opinion de literatura", "requiere_cuenta", "MCP cerrado con cuenta; Rosa ya tiene PubMed, Europe PMC, OpenAlex, Crossref y Semantic Scholar", "https://consensus.app", "socios")
inerte("tooluniverse", "ToolUniverse (Harvard MIMS)", "Mas de 1000 herramientas cientificas con servidor MCP (Apache-2.0)", "Un agregador en vez de clientes propios", "fichero_local", "Se puede montar como servidor MCP local con `uv pip install tooluniverse`; Rosa implementa directamente las bases que necesita para conservar el registro de consultas e invariantes", "https://github.com/mims-harvard/ToolUniverse", "socios")
inerte("cortellis", "Cortellis (Clarivate)", "Inteligencia regulatoria", "Sumisiones y aprobaciones", "requiere_cuenta", "Suscripcion comercial", "https://clarivate.com", "socios")
inerte("adisinsight", "AdisInsight (Springer Nature)", "Pipelines de farmacos y ensayos", "Estado de desarrollo de farmacos", "requiere_cuenta", "Suscripcion comercial; ChEMBL, DGIdb, openFDA y ClinicalTrials.gov cubren lo publico", "https://adisinsight.springer.com", "socios")
inerte("kegg", "KEGG", "Ruta hsa05010 Alzheimer disease y genes, compuestos, farmacos", "Rutas curadas", "licencia", "Solo uso academico por usuarios academicos; una empresa necesita licencia de Pathway Solutions; 3 peticiones por segundo o bloqueo de IP. Reactome (CC0) lo sustituye", "https://www.kegg.jp/kegg/legal.html", "genes_ontologias")
inerte("drugbank", "DrugBank", "Farmacologia, dianas e interacciones de farmacos", "Farmacologia detallada", "licencia", "CC BY-NC con aprobacion humana; descargas academicas pausadas desde mayo de 2026. ChEMBL, DGIdb y openFDA cubren lo publico", "https://go.drugbank.com/academic_research", "farmacos")
inerte("drugcentral", "DrugCentral", "Compendio abierto de farmacos aprobados (CC BY-SA)", "Alternativa abierta a DrugBank", "sin_api", "La API OpenAPI devolvio 404 el 11 de septiembre de 2026; solo volcado PostgreSQL. Vigilar", "https://drugcentral.org/download", "farmacos")
inerte("alzforum_mutations", "AlzForum Mutations", "Curacion humana de variantes en APP, PSEN1, PSEN2, APOE, MAPT, SORL1, TREM2", "La curacion de mutaciones mas usada del campo", "sin_api", "Solo web; todos los derechos reservados; exportacion bajo peticion por correo", "https://www.alzforum.org/mutations", "alzheimer")
inerte("agora", "Agora (AD Knowledge Portal)", "Mas de 950 dianas nominadas por AMP-AD y TREAT-AD con evidencia armonizada", "Dianas nominadas por consorcios del Alzheimer", "sin_api", "Sin API publica documentada; los JSON viven en Synapse (Agora Live Data) y se leen con synapse_buscar y synapseclient con token", "https://agora.adknowledgeportal.org/", "alzheimer")
inerte("archs4", "ARCHS4", "Mas de 1,5 millones de muestras RNA-seq reprocesadas uniformemente", "Expresion por gen en todo GEO/SRA", "fichero_local", "Requiere descargar un H5 de mas de 30 GB; CC BY 4.0 con restriccion no comercial. Pendiente de decidir si se descarga al servidor", "https://maayanlab.cloud/archs4/help.html", "expresion")
inerte("msigdb", "MSigDB", "Colecciones de conjuntos de genes (Hallmark, C2, C5)", "GSEA con conjuntos curados", "requiere_cuenta", "Registro gratuito para descargar; Enrichr y g:Profiler cubren la sobre representacion sin registro", "https://www.gsea-msigdb.org/gsea/register.jsp", "enriquecimiento")
inerte("eqtl_catalogue", "eQTL Catalogue", "eQTL y sQTL por tejido", "Efecto de variantes sobre la expresion en cerebro", "sin_api", "La API REST se retiro (HTTP 410 el 11 de septiembre de 2026); los datos se sirven por FTP y tabix segun ebi.ac.uk/eqtl/Data_access. Pendiente un lector de ficheros", "https://www.ebi.ac.uk/eqtl/Data_access/", "genetica_humana")
inerte("biobank_japan", "BioBank Japan (PheWeb)", "Asociaciones en la cohorte japonesa", "Replicacion en poblacion asiatica", "sin_api", "El PheWeb de pheweb.jp no expone la API JSON de genes (404); solo paginas web", "https://pheweb.jp/", "genetica_humana")
inerte("opengwas", "OpenGWAS (IEU)", "Resumenes GWAS completos para aleatorizacion mendeliana", "MR y colocalizacion", "requiere_cuenta", "JWT obligatorio desde mayo de 2024 (token de 14 dias); GWAS Catalog sumstats cubre parte", "https://api.opengwas.io/api/", "genetica_humana")
inerte("lincs_l1000", "LINCS L1000 (clue.io)", "Firmas transcriptomicas de perturbacion para reposicionamiento", "Invertir una firma de Alzheimer con farmacos", "requiere_cuenta", "user_key personal con registro academico", "https://clue.io/developer-resources", "farmacos")
inerte("adni", "ADNI", "Cohorte clinica, biofluidos, genetica e imagen", "La cohorte de referencia", "requiere_cuenta", "Acuerdo de uso de datos con revision; decision del programa: solo datos publicos por ahora", "https://adni.loni.usc.edu/", "alzheimer")
inerte("ukbiobank", "UK Biobank", "500.000 participantes con genomica, proteomica e imagen", "Cohorte poblacional", "requiere_cuenta", "Solo dentro del Research Analysis Platform; solicitudes pausadas hasta finales de 2026", "https://www.ukbiobank.ac.uk/", "alzheimer")
inerte("zinc", "ZINC", "Espacio quimico comprable para cribado virtual", "Compuestos comprables", "sin_api", "Sin relevancia para el programa actual (no hay cribado virtual); API de docking.org", "https://cartblanche22.docking.org/", "quimica")
inerte("ketcher", "Ketcher", "Dibujo 2D de moleculas", "Herramienta de interfaz, no de datos", "sin_api", "Es un editor grafico de la aplicacion de Claude Science", "https://lifescience.opensource.epam.com/ketcher/", "quimica")
