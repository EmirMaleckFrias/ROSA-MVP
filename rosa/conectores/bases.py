"""Los conectores a bases publicas, por grupo. Cada uno envuelve una API REST
o GraphQL sin clave (salvo NCBI y Semantic Scholar, opcionales), con el
limite de peticiones que la fuente publica y su licencia. Las formas de
respuesta se comprobaron en vivo el 11 de septiembre de 2026.
"""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import quote

from rosa import config
from rosa.conectores.base import Resultado, conector
from rosa.fuentes.base import Limitador, pedir

ALZHEIMER_MONDO = "MONDO_0004975"
ALZHEIMER_EFO = "EFO_0000249"
HUMANO = 9606

_lim = {
    "ols": Limitador(5.0), "mygene": Limitador(5.0), "myvariant": Limitador(2.0), "uniprot": Limitador(5.0), "ensembl": Limitador(10.0),
    "string": Limitador(1.0), "reactome": Limitador(5.0), "gwas": Limitador(5.0), "chembl": Limitador(3.0), "hpa": Limitador(3.0),
    "alphafold": Limitador(3.0), "pdb": Limitador(3.0), "biorxiv": Limitador(2.0), "s2": Limitador(1.0), "ncbi": Limitador(2.0),
    "cellxgene": Limitador(1.0), "synapse": Limitador(2.0), "gtex": Limitador(3.0),
}


def _esq(**props: str) -> dict[str, Any]:
    return {"type": "object", "properties": {k: {"type": "string", "description": v} for k, v in props.items()}, "required": list(props)}


# ---------------------------------------------------------------------------
# Ontologias e identificadores
# ---------------------------------------------------------------------------


@conector("ols_resolver", "OLS4 (EMBL-EBI)", "Resuelve un termino de enfermedad o fenotipo a su identificador de ontologia (MONDO, EFO, HPO)", "El identificador que exigen Open Targets y GWAS Catalog; sinonimos y definicion", _esq(termino="Texto libre, por ejemplo 'Alzheimer disease'", ontologia="mondo, efo o hp"), "Cada ontologia la suya: MONDO y HPO CC BY 4.0, EFO Apache-2.0", "No publicado; 5 por segundo en Rosa", "https://www.ebi.ac.uk/ols4/api-docs", grupo="genes_ontologias")
async def ols_resolver(termino: str, ontologia: str = "mondo") -> Resultado:
    r = await pedir("GET", "https://www.ebi.ac.uk/ols4/api/search", _lim["ols"], params={"q": termino, "ontology": ontologia, "rows": 5})
    docs = r.json().get("response", {}).get("docs", [])
    filas = [{"id": d.get("short_form"), "etiqueta": d.get("label"), "definicion": (d.get("description") or [""])[0][:300], "ontologia": d.get("ontology_prefix")} for d in docs]
    exacto = [f for f in filas if (f["etiqueta"] or "").lower() == termino.lower()]
    return Resultado(filas, len(filas), [f["id"] for f in filas if f["id"]], None, (bool(exacto), f"coincidencia exacta: {exacto[0]['id']}" if exacto else "sin coincidencia exacta; revisar el primer resultado"))


@conector("mygene_gen", "MyGene.info (BioThings)", "Normaliza un simbolo de gen humano a Ensembl, UniProt y Entrez con su nombre", "Identificadores estables para la tarjeta y para consultar las demas bases", _esq(simbolo="Simbolo HGNC, por ejemplo APOE"), "Software Apache-2.0; los datos heredan la fuente", "5000 terminos por POST; 5 por segundo en Rosa", "https://docs.mygene.info/", grupo="genes_ontologias")
async def mygene_gen(simbolo: str) -> Resultado:
    r = await pedir("GET", "https://mygene.info/v3/query", _lim["mygene"], params={"q": f"symbol:{simbolo}", "species": "human", "fields": "symbol,name,ensembl.gene,uniprot.Swiss-Prot,entrezgene,summary"})
    hits = r.json().get("hits", [])
    exactos = [h for h in hits if (h.get("symbol") or "").upper() == simbolo.upper()]
    h = exactos[0] if exactos else (hits[0] if hits else None)
    if not h:
        return Resultado(None, 0, [], None, (False, "el simbolo no resuelve a ningun gen humano"))
    ens = h.get("ensembl")
    ens_id = (ens[0] if isinstance(ens, list) else ens or {}).get("gene") if ens else None
    uni = (h.get("uniprot") or {}).get("Swiss-Prot")
    uni = uni[0] if isinstance(uni, list) else uni
    datos = {"simbolo": h.get("symbol"), "nombre": h.get("name"), "ensembl": ens_id, "uniprot": uni, "entrez": str(h.get("entrezgene") or h.get("_id")), "resumen": (h.get("summary") or "")[:400]}
    return Resultado(datos, 1, [i for i in (ens_id, uni) if i], None, (len(exactos) == 1 and bool(ens_id), "un unico gen con Ensembl" if len(exactos) == 1 and ens_id else f"{len(exactos)} coincidencias exactas; Ensembl {'si' if ens_id else 'no'}"))


@conector("ensembl_gen", "Ensembl REST", "Coordenadas, biotipo y descripcion de un gen humano (GRCh38)", "Build y posicion, para que la identidad del dato viaje con la afirmacion", _esq(simbolo="Simbolo HGNC"), "Sin restricciones", "15 por segundo (cabeceras X-RateLimit)", "https://rest.ensembl.org/", grupo="genomas")
async def ensembl_gen(simbolo: str) -> Resultado:
    r = await pedir("GET", f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{quote(simbolo)}", _lim["ensembl"], params={"content-type": "application/json"})
    d = r.json()
    datos = {"ensembl": d.get("id"), "simbolo": d.get("display_name"), "biotipo": d.get("biotype"), "cromosoma": d.get("seq_region_name"), "inicio": d.get("start"), "fin": d.get("end"), "build": d.get("assembly_name"), "descripcion": (d.get("description") or "")[:200]}
    return Resultado(datos, 1 if d.get("id") else 0, [d["id"]] if d.get("id") else [], str(d.get("version") or ""), (d.get("assembly_name") == "GRCh38", f"build {d.get('assembly_name')}"))


@conector("myvariant_variante", "MyVariant.info (BioThings)", "Anota una variante por rsID: gen, significado clinico en ClinVar, frecuencia en gnomAD, CADD", "Si una variante nombrada en una hipotesis es patogenica, frecuente o rara", _esq(rsid="Identificador dbSNP, por ejemplo rs429358"), "Software Apache-2.0; ClinVar dominio publico, gnomAD ficheros publicos", "1000 peticiones por IP y dia sin clave", "https://docs.myvariant.info/", grupo="variantes")
async def myvariant_variante(rsid: str) -> Resultado:
    r = await pedir("GET", "https://myvariant.info/v1/query", _lim["myvariant"], params={"q": f"dbsnp.rsid:{rsid}", "fields": "clinvar.rcv.clinical_significance,gnomad_genome.af.af,dbsnp.gene.symbol,cadd.phred", "assembly": "hg38"})
    hits = r.json().get("hits", [])
    if not hits:
        return Resultado(None, 0, [], None, (False, "rsID sin registro"))
    h = hits[0]
    rcv = (h.get("clinvar") or {}).get("rcv") or []
    rcv = rcv if isinstance(rcv, list) else [rcv]
    sig = sorted({x.get("clinical_significance", "") for x in rcv if x.get("clinical_significance")})
    gen = (h.get("dbsnp") or {}).get("gene")
    gen = (gen[0] if isinstance(gen, list) else gen or {}).get("symbol") if gen else None
    af = ((h.get("gnomad_genome") or {}).get("af") or {}).get("af")
    datos = {"hgvs": h.get("_id"), "gen": gen, "clinvar": sig, "gnomad_af": af, "cadd_phred": (h.get("cadd") or {}).get("phred"), "build": "hg38"}
    return Resultado(datos, 1, [h.get("_id", rsid)], None, (bool(gen), f"gen {gen}" if gen else "sin gen anotado"))


# ---------------------------------------------------------------------------
# Proteinas, expresion, estructuras
# ---------------------------------------------------------------------------


@conector("uniprot_proteina", "UniProt REST", "Funcion y longitud de la proteina revisada (Swiss-Prot) de un gen humano", "La funcion en una frase para el resumen en llano y para la tarjeta", _esq(simbolo="Simbolo HGNC"), "CC BY 4.0", "Sin limite estricto; 5 por segundo en Rosa", "https://www.uniprot.org/help/programmatic_access", grupo="genes_ontologias")
async def uniprot_proteina(simbolo: str) -> Resultado:
    r = await pedir("GET", "https://rest.uniprot.org/uniprotkb/search", _lim["uniprot"], params={"query": f"gene_exact:{simbolo} AND organism_id:{HUMANO} AND reviewed:true", "fields": "accession,protein_name,gene_names,cc_function,length", "format": "json", "size": 3})
    res = r.json().get("results", [])
    if not res:
        return Resultado(None, 0, [], r.headers.get("x-uniprot-release"), (False, "sin entrada revisada"))
    e = res[0]
    funcion = ""
    for c in e.get("comments", []):
        if c.get("commentType") == "FUNCTION":
            funcion = " ".join(t.get("value", "") for t in c.get("texts", []))[:600]
    datos = {"accession": e.get("primaryAccession"), "nombre": ((e.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName", {}).get("value"), "longitud": (e.get("sequence") or {}).get("length"), "funcion": funcion}
    return Resultado(datos, len(res), [x.get("primaryAccession") for x in res], r.headers.get("x-uniprot-release"), (len(res) == 1, f"{len(res)} entradas revisadas"))


@conector("hpa_expresion", "Human Protein Atlas", "Expresion por tejido y region cerebral, especificidad y clase de proteina de un gen", "Donde se expresa lo que la hipotesis nombra: cerebro, tipo celular, sangre", _esq(ensembl="Identificador Ensembl, por ejemplo ENSG00000130203"), "CC BY 4.0 con cita de version", "No publicado; 3 por segundo en Rosa", "https://www.proteinatlas.org/about/help/dataaccess", grupo="proteinas")
async def hpa_expresion(ensembl: str) -> Resultado:
    r = await pedir("GET", f"https://www.proteinatlas.org/{quote(ensembl)}.json", _lim["hpa"])
    d = r.json()
    claves = {k: d.get(k) for k in ("Gene", "Gene description", "Protein class", "Biological process", "RNA tissue specificity", "RNA tissue specific nTPM", "RNA brain regional specificity", "RNA brain regional specific nTPM", "RNA single cell type specificity", "RNA single cell type specific nTPM", "Blood expression cluster", "Subcellular location") if k in d}
    return Resultado(claves, 1 if d.get("Gene") else 0, [ensembl], None, (bool(d.get("Gene")), f"gen {d.get('Gene')}"))


@conector("gtex_expresion", "GTEx v10", "Expresion mediana (TPM) de un gen en un tejido, por ejemplo hipocampo", "Si el gen se expresa en el tejido que la hipotesis dice", _esq(gencode="Identificador GENCODE con version, por ejemplo ENSG00000130203.10", tejido="tissueSiteDetailId, por ejemplo Brain_Hippocampus"), "Terminos GTEx (datos abiertos del portal)", "No publicado; 3 por segundo en Rosa", "https://gtexportal.org/api/v2/redoc", grupo="expresion")
async def gtex_expresion(gencode: str, tejido: str = "Brain_Hippocampus") -> Resultado:
    r = await pedir("GET", "https://gtexportal.org/api/v2/expression/medianGeneExpression", _lim["gtex"], params={"gencodeId": gencode, "tissueSiteDetailId": tejido, "datasetId": "gtex_v10"})
    filas = r.json().get("data", [])
    datos = [{"gen": f.get("geneSymbol"), "tejido": f.get("tissueSiteDetailId"), "mediana": f.get("median"), "unidad": f.get("unit")} for f in filas]
    return Resultado(datos, len(datos), [gencode], "gtex_v10", (len(datos) == 1, f"{len(datos)} filas"))


@conector("alphafold_estructura", "AlphaFold DB", "Modelo predicho de una proteina con su confianza (pLDDT) y version", "Si hay estructura para razonar sobre un sitio de union", _esq(uniprot="Accession UniProt, por ejemplo P02649"), "CC BY 4.0", "No publicado; 3 por segundo en Rosa", "https://alphafold.ebi.ac.uk/api-docs", grupo="estructuras")
async def alphafold_estructura(uniprot: str) -> Resultado:
    r = await pedir("GET", f"https://alphafold.ebi.ac.uk/api/prediction/{quote(uniprot)}", _lim["alphafold"])
    lst = r.json()
    if not lst:
        return Resultado(None, 0, [], None, (False, "sin modelo"))
    m = lst[0]
    datos = {"modelo": m.get("modelEntityId"), "plddt_medio": m.get("globalMetricValue"), "fraccion_confiable": (m.get("fractionPlddtConfident") or 0) + (m.get("fractionPlddtVeryHigh") or 0), "version": m.get("latestVersion"), "pdb": m.get("pdbUrl"), "creado": m.get("modelCreatedDate")}
    return Resultado(datos, len(lst), [m.get("modelEntityId")], str(m.get("latestVersion")), (m.get("globalMetricValue") is not None, f"pLDDT medio {m.get('globalMetricValue')}"))


@conector("pdb_estructuras", "RCSB PDB", "Cuantas estructuras experimentales hay para una proteina (por accession UniProt) y cuales", "Si el mecanismo se apoya en una estructura real", _esq(uniprot="Accession UniProt"), "CC0", "Pocas por segundo; 1000 identificadores por lote", "https://search.rcsb.org/", grupo="estructuras")
async def pdb_estructuras(uniprot: str) -> Resultado:
    cuerpo = {"query": {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession", "operator": "exact_match", "value": uniprot}}, "return_type": "entry", "request_options": {"paginate": {"start": 0, "rows": 10}}}
    r = await pedir("POST", "https://search.rcsb.org/rcsbsearch/v2/query", _lim["pdb"], json=cuerpo)
    if r.status_code == 204 or not r.text.strip():
        return Resultado({"total": 0, "entradas": []}, 0, [], None, (True, "cero estructuras (respuesta vacia legitima)"))
    d = r.json()
    ids = [x.get("identifier") for x in d.get("result_set", [])]
    return Resultado({"total": d.get("total_count", 0), "entradas": ids}, d.get("total_count", 0), ids, None, (True, f"{d.get('total_count', 0)} entradas"))


# ---------------------------------------------------------------------------
# Redes, rutas, genetica, farmacos
# ---------------------------------------------------------------------------


@conector("string_interactores", "STRING (MCP y REST oficiales)", "Los interactores funcionales de una proteina con su puntuacion combinada", "La vecindad que se mueve si la diana falla; candidatos a confusor o mediador", _esq(simbolo="Simbolo HGNC"), "CC BY 4.0", "1 por segundo, sin paralelo; caller_identity obligatorio", "https://string-db.org/help/api/", grupo="proteinas")
async def string_interactores(simbolo: str) -> Resultado:
    r = await pedir("GET", "https://version-12-0.string-db.org/api/json/interaction_partners", _lim["string"], params={"identifiers": simbolo, "species": HUMANO, "limit": 10, "caller_identity": "rosa-alzheimer-project"})
    filas = r.json()
    datos = [{"interactor": f.get("preferredName_B"), "puntuacion": f.get("score"), "experimental": f.get("escore"), "bases": f.get("dscore"), "texto": f.get("tscore")} for f in filas]
    return Resultado(datos, len(datos), [f["interactor"] for f in datos if f["interactor"]], "12.0", (all((f.get("preferredName_A") or "").upper() == simbolo.upper() for f in filas), "el simbolo resolvio a la proteina pedida" if filas else "sin interactores"))


@conector("reactome_rutas", "Reactome ContentService", "Las rutas curadas en las que participa una proteina (por accession UniProt)", "La ruta biologica de la diana, con identificador estable", _esq(uniprot="Accession UniProt"), "CC0", "No publicado; 5 por segundo en Rosa", "https://reactome.org/dev/content-service", grupo="genes_ontologias")
async def reactome_rutas(uniprot: str) -> Resultado:
    r = await pedir("GET", f"https://reactome.org/ContentService/data/mapping/UniProt/{quote(uniprot)}/pathways", _lim["reactome"], params={"species": HUMANO})
    if r.status_code == 204 or not r.text.strip():
        return Resultado([], 0, [], None, (True, "cero rutas (respuesta vacia legitima)"))
    filas = r.json()
    datos = [{"id": f.get("stId"), "nombre": f.get("displayName"), "enfermedad": f.get("isInDisease")} for f in filas]
    return Resultado(datos, len(datos), [f["id"] for f in datos if f["id"]], None, (True, f"{len(datos)} rutas"))


@conector("gwas_asociaciones_gen", "GWAS Catalog REST v2", "Asociaciones GWAS de un gen, separando las de Alzheimer del resto", "Si la genetica humana ya vincula el gen con la enfermedad, y con que p", _esq(simbolo="Simbolo HGNC"), "CC0 / terminos EMBL-EBI", "15 por segundo", "https://www.ebi.ac.uk/gwas/rest/api/v2/docs", grupo="genetica_humana")
async def gwas_asociaciones_gen(simbolo: str) -> Resultado:
    r = await pedir("GET", "https://www.ebi.ac.uk/gwas/rest/api/v2/associations", _lim["gwas"], params={"gene_name": simbolo, "size": 50})
    d = r.json()
    filas = (d.get("_embedded") or {}).get("associations", [])
    total = (d.get("page") or {}).get("totalElements", len(filas))

    def es_ad(a: dict[str, Any]) -> bool:
        return any((t.get("efo_id") in (ALZHEIMER_MONDO, ALZHEIMER_EFO)) or "alzheimer" in (t.get("efo_trait") or "").lower() for t in a.get("efo_traits", [])) or any("alzheimer" in (x or "").lower() for x in a.get("reported_trait", []))

    ad = [a for a in filas if es_ad(a)]
    datos = {"total_asociaciones": total, "en_esta_pagina": len(filas), "alzheimer": [{"estudio": a.get("accession_id"), "p": a.get("p_value"), "rasgo": "; ".join(a.get("reported_trait", [])[:2]), "efecto": a.get("beta") or a.get("or_value")} for a in ad[:10]], "n_alzheimer": len(ad)}
    return Resultado(datos, total, [a.get("accession_id") for a in ad[:20] if a.get("accession_id")], None, (True, f"{len(ad)} de {len(filas)} asociaciones vistas son de Alzheimer"))


@conector("chembl_diana", "ChEMBL REST", "La diana ChEMBL de una proteina (por accession UniProt) y los mecanismos de accion de farmacos que la tocan", "Si ya hay farmacos contra la diana, en que fase y con que accion: plausibilidad y reposicionamiento", _esq(uniprot="Accession UniProt"), "CC BY-SA 3.0 con atribucion de URL y version", "Sin cifra publicada; paginas de 20; 3 por segundo en Rosa", "https://www.ebi.ac.uk/chembl/api/data/docs", grupo="directorio")
async def chembl_diana(uniprot: str) -> Resultado:
    r = await pedir("GET", "https://www.ebi.ac.uk/chembl/api/data/target.json", _lim["chembl"], params={"target_components__accession": uniprot, "limit": 5})
    targets = r.json().get("targets", [])
    if not targets:
        return Resultado({"diana": None, "mecanismos": []}, 0, [], None, (True, "sin diana ChEMBL para esa proteina (cero legitimo)"))
    t = targets[0]
    r2 = await pedir("GET", "https://www.ebi.ac.uk/chembl/api/data/mechanism.json", _lim["chembl"], params={"target_chembl_id": t["target_chembl_id"], "limit": 20})
    mecs = r2.json().get("mechanisms", [])
    datos = {"diana": t["target_chembl_id"], "nombre": t.get("pref_name"), "mecanismos": [{"molecula": m.get("molecule_chembl_id"), "accion": m.get("action_type"), "mecanismo": m.get("mechanism_of_action"), "fase_maxima": m.get("max_phase")} for m in mecs]}
    return Resultado(datos, len(mecs), [t["target_chembl_id"]] + [m.get("molecule_chembl_id") for m in mecs[:10] if m.get("molecule_chembl_id")], None, (True, f"{len(mecs)} mecanismos registrados"))


# ---------------------------------------------------------------------------
# Datos publicos: GEO, CELLxGENE, Synapse
# ---------------------------------------------------------------------------


def _params_ncbi(**kw: Any) -> dict[str, Any]:
    p = {"tool": "rosa", "email": config.CORREO_CONTACTO, "retmode": "json", **kw}
    if getattr(config, "CLAVE_NCBI", ""):
        p["api_key"] = config.CLAVE_NCBI
    return p


@conector("geo_series", "GEO (NCBI E-utilities, db=gds)", "Busca series de expresion (GSE) por terminos y devuelve titulo, n de muestras, plataforma, organismo y fecha", "Si existe un dataset publico para comprobar la hipotesis, y cual", _esq(terminos="Terminos de busqueda, por ejemplo 'Alzheimer hippocampus GFAP'"), "Dominio publico (NCBI)", "3 por segundo, 10 con clave NCBI", "https://www.ncbi.nlm.nih.gov/geo/info/geo_paccess.html", grupo="omicas")
async def geo_series(terminos: str) -> Resultado:
    consulta = " AND ".join(f"{t}[All Fields]" for t in terminos.split()) + " AND gse[ETYP] AND Homo sapiens[Organism]"
    r = await pedir("GET", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", _lim["ncbi"], params=_params_ncbi(db="gds", term=consulta, retmax=8))
    es = r.json().get("esearchresult", {})
    ids = es.get("idlist", [])
    total = int(es.get("count", 0) or 0)
    series = []
    if ids:
        r2 = await pedir("GET", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi", _lim["ncbi"], params=_params_ncbi(db="gds", id=",".join(ids)))
        res = r2.json().get("result", {})
        for i in ids:
            s = res.get(i) or {}
            series.append({"accession": s.get("accession"), "titulo": (s.get("title") or "")[:160], "n_muestras": s.get("n_samples"), "plataforma": s.get("gpl"), "organismo": s.get("taxon"), "tipo": s.get("gdstype"), "fecha": s.get("pdat"), "pubmed": [str(x) for x in (s.get("pubmedids") or [])][:3]})
    return Resultado({"total": total, "series": series}, total, [s["accession"] for s in series if s.get("accession")], None, (len(series) == min(len(ids), 8), f"{total} series; {len(series)} resumidas"))


@conector("geo_serie", "GEO (NCBI E-utilities, db=gds)", "Los metadatos de una serie GSE concreta para el libro de procedencia", "Rellena origen, n, plataforma, organismo, fecha y articulo del dataset", _esq(accession="Accession GSE, por ejemplo GSE1297"), "Dominio publico (NCBI)", "3 por segundo, 10 con clave NCBI", "https://www.ncbi.nlm.nih.gov/geo/info/geo_paccess.html", grupo="omicas")
async def geo_serie(accession: str) -> Resultado:
    r = await pedir("GET", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", _lim["ncbi"], params=_params_ncbi(db="gds", term=f"{accession}[Accession] AND gse[ETYP]", retmax=3))
    ids = r.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return Resultado(None, 0, [], None, (False, "accession sin registro"))
    r2 = await pedir("GET", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi", _lim["ncbi"], params=_params_ncbi(db="gds", id=",".join(ids)))
    res = r2.json().get("result", {})
    s = next((res[i] for i in ids if (res.get(i) or {}).get("accession") == accession), res.get(ids[0]) or {})
    datos = {"accession": s.get("accession"), "titulo": s.get("title"), "resumen": (s.get("summary") or "")[:600], "n_muestras": s.get("n_samples"), "plataforma": s.get("gpl"), "organismo": s.get("taxon"), "tipo": s.get("gdstype"), "fecha": s.get("pdat"), "pubmed": [str(x) for x in (s.get("pubmedids") or [])], "ftp": s.get("ftplink")}
    return Resultado(datos, 1, [accession], None, (s.get("accession") == accession, f"accession {s.get('accession')} con {s.get('n_samples')} muestras"))


_cache_cellxgene: dict[str, Any] = {"t": 0.0, "colecciones": []}


@conector("cellxgene_colecciones", "CZ CELLxGENE Discover", "Colecciones de celula unica cuyo nombre o descripcion mencionan un termino (por ejemplo Alzheimer), con sus datasets", "Si hay un atlas de celula unica publico (SEA-AD y otros) para la pregunta", _esq(termino="Texto a buscar en nombre y descripcion"), "CC BY 4.0", "No publicado; el catalogo completo pesa 3 MB y se cachea una hora", "https://api.cellxgene.cziscience.com/curation/ui/", grupo="socios")
async def cellxgene_colecciones(termino: str) -> Resultado:
    if time.time() - _cache_cellxgene["t"] > 3600 or not _cache_cellxgene["colecciones"]:
        r = await pedir("GET", "https://api.cellxgene.cziscience.com/curation/v1/collections", _lim["cellxgene"], params={"visibility": "PUBLIC"})
        _cache_cellxgene.update(t=time.time(), colecciones=r.json())
    t = termino.lower()
    hits = [c for c in _cache_cellxgene["colecciones"] if t in (c.get("name") or "").lower() or t in (c.get("description") or "").lower()]
    datos = [{"id": c.get("collection_id"), "nombre": (c.get("name") or "")[:140], "url": c.get("collection_url"), "datasets": len(c.get("datasets") or []), "celulas": sum(int(d.get("cell_count") or 0) for d in c.get("datasets") or []), "doi": c.get("doi")} for c in hits[:15]]
    return Resultado(datos, len(hits), [d["id"] for d in datos if d["id"]], None, (True, f"{len(hits)} colecciones de {len(_cache_cellxgene['colecciones'])}"))


@conector("synapse_buscar", "Synapse.org (AD Knowledge Portal)", "Busca entidades publicas en Synapse por terminos (busqueda anonima)", "Que estudios del AD Knowledge Portal tocan la pregunta; el acceso a datos individuales requiere cuenta y acuerdo de uso", _esq(terminos="Terminos separados por espacio"), "Por nivel; los datos individuales exigen certificado de uso", "No publicado; 2 por segundo en Rosa", "https://rest-docs.synapse.org/rest/", grupo="socios")
async def synapse_buscar(terminos: str) -> Resultado:
    r = await pedir("POST", "https://repo-prod.prod.sagebase.org/repo/v1/search", _lim["synapse"], json={"queryTerm": terminos.split(), "size": 8})
    d = r.json()
    hits = d.get("hits", [])
    datos = {"total": d.get("found", len(hits)), "entidades": [{"id": h.get("id"), "nombre": (h.get("name") or "")[:140], "tipo": h.get("node_type"), "descripcion": (h.get("description") or "")[:200]} for h in hits]}
    return Resultado(datos, d.get("found", len(hits)), [h.get("id") for h in hits if h.get("id")], None, (True, f"{d.get('found', 0)} entidades publicas"))


# ---------------------------------------------------------------------------
# Literatura complementaria
# ---------------------------------------------------------------------------


@conector("biorxiv_preprint", "bioRxiv y medRxiv API", "Los detalles de un preprint por DOI y si ya se publico en revista", "Si una afirmacion se apoya en un preprint y si ese preprint paso revision", _esq(doi="DOI del preprint, por ejemplo 10.1101/2024.01.01.573777", servidor="biorxiv o medrxiv"), "Por preprint (CC BY a ninguna); no cachear texto completo", "No documentado; bloquean agentes 'bot'", "https://api.biorxiv.org/", grupo="directorio")
async def biorxiv_preprint(doi: str, servidor: str = "biorxiv") -> Resultado:
    r = await pedir("GET", f"https://api.biorxiv.org/details/{servidor}/{doi}/na/json", _lim["biorxiv"])
    col = r.json().get("collection", [])
    if not col:
        return Resultado(None, 0, [], None, (False, "DOI sin registro en ese servidor"))
    v = col[-1]
    datos = {"doi": v.get("doi"), "titulo": v.get("title"), "fecha": v.get("date"), "version": v.get("version"), "categoria": v.get("category"), "licencia": v.get("license"), "publicado": v.get("published") if v.get("published") not in (None, "NA") else None}
    return Resultado(datos, len(col), [doi], str(v.get("version")), (True, f"{len(col)} versiones; publicado: {datos['publicado'] or 'no'}"))


@conector("s2_citas", "Semantic Scholar Academic Graph", "Numero de citas e influyentes de un articulo por DOI", "Quien cito y cuanto peso tiene la fuente; complementa a OpenAlex", _esq(doi="DOI del articulo"), "Licencia propia de la API", "1 por segundo con clave; pool compartido sin clave", "https://api.semanticscholar.org/api-docs/", clave="opcional", grupo="literatura")
async def s2_citas(doi: str) -> Resultado:
    cab = {"x-api-key": config.CLAVE_S2} if getattr(config, "CLAVE_S2", "") else {}
    r = await pedir("GET", f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}", _lim["s2"], params={"fields": "citationCount,influentialCitationCount,title,year"}, headers=cab)
    d = r.json()
    datos = {"titulo": d.get("title"), "anio": d.get("year"), "citas": d.get("citationCount"), "influyentes": d.get("influentialCitationCount"), "paperId": d.get("paperId")}
    return Resultado(datos, 1 if d.get("paperId") else 0, [d.get("paperId")] if d.get("paperId") else [], None, (d.get("citationCount") is not None, f"{d.get('citationCount')} citas"))


SIMBOLO_GEN = re.compile(r"^[A-Z][A-Z0-9-]{1,10}$")


def parece_simbolo(texto: str) -> bool:
    """Un simbolo HGNC plausible (APOE, TREM2, GFAP, NfL no; NEFL si)."""
    return bool(SIMBOLO_GEN.match((texto or "").strip()))
