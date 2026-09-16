"""El registro de datasets a nivel de programa y la lectura de célula única:
todo por regla, sin red, sin modelo. Las formas de entrada son las que
devuelven los conectores en rosa/conectores/bases.py y bases2.py."""

import importlib.util
import json

import numpy as np
import pandas as pd
import pytest

from rosa import datasets_programa as DP

HAY_ANNDATA = importlib.util.find_spec("anndata") is not None

# Un resultado de `geo_serie` tal como lo arma el conector (los n_samples de
# E-utilities llegan como texto; la plataforma puede traer varias GPL).
GSE1297 = {
    "accession": "GSE1297",
    "titulo": "Alzheimer's disease and the normal aged hippocampus",
    "resumen": "Hippocampal CA1 gene expression profiles from 31 subjects: controls and incipient, moderate and severe Alzheimer's disease, graded by MMSE and NFT (Braak) scores. Affymetrix HG-U133A.",
    "n_muestras": "31",
    "plataforma": "GPL96",
    "organismo": "Homo sapiens",
    "tipo": "Expression profiling by array",
    "fecha": "2004/02/04",
    "pubmed": ["14769913"],
    "ftp": "ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSE1nnn/GSE1297/",
}

# Una fila de `cellxgene_colecciones`.
SEA_AD_CX = {"id": "1ca90a2d-2943-483d-b678-b809bf464c30", "nombre": "SEA-AD: Seattle Alzheimer's Disease Brain Cell Atlas", "url": "https://cellxgene.cziscience.com/collections/1ca90a2d-2943-483d-b678-b809bf464c30", "datasets": 6, "celulas": 1378211, "doi": "10.1038/s41593-024-01774-5"}

# Una fila de `synapse_buscar` (entidades).
SYN = {"id": "syn3219045", "nombre": "ROSMAP", "tipo": "project", "descripcion": "Religious Orders Study and Memory and Aging Project: RNA-seq of dorsolateral prefrontal cortex. Access requires a Data Use Certificate."}


def _e():
    return {"investigaciones": [], "datasetsPrograma": []}


# -- Registro y deduplicación ---------------------------------------------------


def test_nuevo_registro_trae_todas_las_claves_y_normaliza():
    r = DP.nuevo_registro("geo", " gse1297 ", {"titulo": "Hippocampus single-nucleus RNA-seq in Braak V-VI", "n": 12}, 1000)
    assert r["id"].startswith("dsp")
    for k in ("id", "fuente", "accession", "titulo", "organismo", "tejido", "region", "estadio", "tipo", "n", "plataforma", "procesado", "acceso", "licencia", "url", "fichero", "muestrasCompartidasCon", "usadoEn", "registradoEn", "actualizadoEn", "registro"):
        assert k in r, k
    assert r["accession"] == "gse1297" and r["n"] == {"muestras": 12, "donantes": None, "celulas": None}
    assert r["tipo"] == "celula_unica" and r["region"] == "hipocampo" and r["tejido"] == "cerebro" and "Braak" in r["estadio"]
    assert r["acceso"] == "desconocido" and r["fichero"] is None
    # Cada inferencia deja su motivo.
    assert any("single-nucleus" in x for x in r["registro"]) and any("hippocampus" in x for x in r["registro"])


def test_fuente_desconocida_cae_a_manual_y_lo_dice():
    r = DP.nuevo_registro("dropbox", "X1", {"titulo": "t"}, 1)
    assert r["fuente"] == "manual" and any("desconocida" in x for x in r["registro"])


def test_sin_accession_deriva_un_identificador_estable_del_titulo():
    a = DP.nuevo_registro("manual", "", {"titulo": "Cohorte propia de plasma"}, 1)
    b = DP.nuevo_registro("manual", "", {"titulo": "Cohorte propia de plasma"}, 2)
    assert a["accession"] == b["accession"] and a["accession"].startswith("sin-accession-")
    e = _e()
    assert DP.registrar(e, a) == DP.registrar(e, b) and len(e["datasetsPrograma"]) == 1


def test_registrar_deduplica_por_fuente_y_accession_y_funde_usadoEn():
    e = {}
    id1 = DP.desde_geo(e, "GSE1297", GSE1297, "inv-1", 1000)
    id2 = DP.desde_geo(e, "gse1297", GSE1297, "inv-2", 2000)
    id3 = DP.desde_geo(e, "GSE1297", GSE1297, "inv-1", 3000)
    assert id1 == id2 == id3 and len(e["datasetsPrograma"]) == 1
    r = e["datasetsPrograma"][0]
    assert r["usadoEn"] == ["inv-1", "inv-2"] and r["registradoEn"] == 1000 and r["actualizadoEn"] == 3000
    # La misma accession en otra fuente es otro registro.
    DP.desde_expression_atlas(e, {"accession": "E-GEOD-1297", "descripcion": "Alzheimer hippocampus", "tipo": "MICROARRAY_1COLOUR_MRNA_DIFFERENTIAL", "especie": "Homo sapiens", "ensayos": 31}, "inv-1", 4000)
    assert len(e["datasetsPrograma"]) == 2


def test_ids_de_investigacion_heredados_con_sufijo_inv_no_se_confunden():
    e = _e()
    DP.desde_geo(e, "GSE1297", GSE1297, "inv-1", 1)
    DP.desde_geo(e, "GSE1297", GSE1297, "inv-1-inv-2", 2)
    DP.desde_geo(e, "GSE1297", GSE1297, "inv-1", 3)
    assert e["datasetsPrograma"][0]["usadoEn"] == ["inv-1", "inv-1-inv-2"]
    assert DP.marcar_uso(e, e["datasetsPrograma"][0]["id"], "inv-3") and e["datasetsPrograma"][0]["usadoEn"][-1] == "inv-3"
    assert not DP.marcar_uso(e, "dsp-no-existe", "inv-3")


def test_registro_antiguo_sin_claves_nuevas_no_rompe_y_se_completa():
    e = {"datasetsPrograma": [{"id": "dsp-viejo", "fuente": "geo", "accession": "GSE1297"}, {"fuente": "geo", "accession": "GSE5281", "n": 7, "usadoEn": "inv-1", "acceso": "publico"}]}
    id_ = DP.desde_geo(e, "GSE1297", GSE1297, "inv-9", 5)
    assert id_ == "dsp-viejo" and len(e["datasetsPrograma"]) == 2
    viejo = e["datasetsPrograma"][0]
    # Los campos vacíos del antiguo se rellenan con los del nuevo; el id se conserva.
    assert viejo["titulo"] == GSE1297["titulo"] and viejo["n"]["muestras"] == 31 and viejo["usadoEn"] == ["inv-9"]
    otro = e["datasetsPrograma"][1]
    # Los valores de otra época se leen como los de hoy: n: 7 son 7 muestras,
    # usadoEn "inv-1" es una lista de uno, acceso "publico" es abierto.
    assert otro["id"].startswith("dsp") and otro["n"] == {"muestras": 7, "donantes": None, "celulas": None} and otro["usadoEn"] == ["inv-1"] and otro["acceso"] == "abierto"
    # Texto y coincidencias también funcionan sobre lo antiguo.
    assert "GSE5281" in DP.texto_registro(e)
    assert isinstance(DP.coincidencias(e, "hipocampo"), list)


def test_estado_sin_la_clave_la_crea_con_setdefault():
    e = {"investigaciones": []}
    DP.desde_geo(e, "GSE1297", GSE1297, None, 1)
    assert "datasetsPrograma" in e and e["datasetsPrograma"][0]["usadoEn"] == []


def test_entradas_vacias_no_rompen():
    e = _e()
    assert DP.desde_cellxgene(e, None, "inv-1", 1) is None
    assert DP.desde_cellxgene(e, {}, "inv-1", 1) is None
    assert DP.desde_synapse(e, {"nombre": "sin id"}, "inv-1", 1) is None
    assert DP.desde_arrayexpress(e, None, "inv-1", 1) is None
    assert DP.desde_expression_atlas(e, {"descripcion": "sin accession"}, "inv-1", 1) is None
    assert DP.desde_dataset_subido(e, "inv-1", {"nombre": "  "}, 1) is None
    assert e["datasetsPrograma"] == []
    assert DP.texto_registro(e) == "Ningún dataset registrado en el programa todavía."
    assert DP.coincidencias(e, "") == [] and DP.coincidencias(e, "hipocampo") == []
    assert DP.detectar_muestras_compartidas("", "GSE1") == []
    assert DP.evaluar_acceso("", "abierto") == ("abierto", "", [])
    assert DP.inferir_tipo("")[0] == "otro" and DP.inferir_tejido("") == ("", "", "tejido sin comprobar: el texto no nombra tejido ni región")


# -- Mapeo de cada conector ----------------------------------------------------


def test_desde_geo_mapea_la_forma_real_de_geo_serie():
    e = _e()
    DP.desde_geo(e, "GSE1297", GSE1297, "inv-1", 1000)
    r = e["datasetsPrograma"][0]
    assert r["fuente"] == "geo" and r["accession"] == "GSE1297"
    assert r["titulo"] == GSE1297["titulo"] and r["organismo"] == "Homo sapiens" and r["plataforma"] == "GPL96"
    assert r["n"]["muestras"] == 31 and r["n"]["donantes"] is None  # GEO no da donantes: no se inventan
    assert r["tipo"] == "bulk" and r["tejido"] == "cerebro" and r["region"] == "hipocampo"
    assert "Braak" in r["estadio"] and "MMSE" in r["estadio"] and "incipiente" in r["estadio"]
    assert r["acceso"] == "abierto" and r["licencia"] == "Dominio público (NCBI GEO)"
    assert r["url"] == "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE1297"
    assert r["muestrasCompartidasCon"] == [] and r["usadoEn"] == ["inv-1"]
    assert any("14769913" in x for x in r["registro"]) and any("2004/02/04" in x for x in r["registro"])
    assert any("donantes" in x and "no los da" in x for x in r["registro"])


def test_desde_geo_serie_de_secuenciacion_decide_celula_unica_por_el_texto():
    e = _e()
    DP.desde_geo(e, "GSE174367", {**GSE1297, "accession": "GSE174367", "titulo": "Single-nucleus chromatin accessibility and transcriptomic characterization of Alzheimer's disease", "resumen": "snRNA-seq and snATAC-seq of prefrontal cortex from 12 donors", "tipo": "Expression profiling by high throughput sequencing", "n_muestras": 24}, "inv-1", 1)
    r = e["datasetsPrograma"][0]
    assert r["tipo"] == "celula_unica" and r["region"] == "corteza prefrontal" and r["n"]["muestras"] == 24
    assert "crudos en SRA" in r["procesado"]
    e2 = _e()
    DP.desde_geo(e2, "GSE33000", {**GSE1297, "accession": "GSE33000", "titulo": "Gene expression in prefrontal cortex", "resumen": "Bulk microarray", "tipo": "Expression profiling by high throughput sequencing"}, None, 1)
    assert e2["datasetsPrograma"][0]["tipo"] == "bulk"
    e3 = _e()
    DP.desde_geo(e3, "GSE9", {**GSE1297, "accession": "GSE9", "tipo": "Genome variation profiling by SNP array", "resumen": ""}, None, 1)
    assert e3["datasetsPrograma"][0]["tipo"] == "genetica"


def test_desde_geo_sin_respuesta_es_no_pude_comprobar():
    e = _e()
    DP.desde_geo(e, "GSE99999", None, "inv-1", 7)
    r = e["datasetsPrograma"][0]
    assert r["accession"] == "GSE99999" and r["titulo"] == "" and r["usadoEn"] == ["inv-1"]
    assert any("no respondió" in x and "sin comprobar" in x and "no significa" in x for x in r["registro"])
    # Cuando GEO responde después, el mismo registro se completa.
    DP.desde_geo(e, "GSE99999", {**GSE1297, "accession": "GSE99999"}, "inv-1", 8)
    assert len(e["datasetsPrograma"]) == 1 and e["datasetsPrograma"][0]["titulo"] == GSE1297["titulo"]


def test_desde_cellxgene_mapea_la_fila_del_conector():
    e = _e()
    DP.desde_cellxgene(e, SEA_AD_CX, "inv-1", 1)
    r = e["datasetsPrograma"][0]
    assert r["fuente"] == "cellxgene" and r["accession"] == SEA_AD_CX["id"] and r["tipo"] == "celula_unica"
    assert r["n"]["celulas"] == 1378211 and r["n"]["muestras"] is None
    assert r["acceso"] == "abierto" and r["licencia"] == "CC BY 4.0" and r["url"] == SEA_AD_CX["url"]
    assert any("10.1038/s41593-024-01774-5" in x for x in r["registro"])
    assert any("s3://sea-ad-single-cell-profiling" in x for x in r["registro"])
    assert any("organismo" in x for x in r["registro"])  # el catálogo no lo da: se dice


def test_desde_synapse_nace_controlado_con_la_nota_del_proyecto():
    e = _e()
    DP.desde_synapse(e, SYN, "inv-1", 1)
    r = e["datasetsPrograma"][0]
    assert r["fuente"] == "synapse" and r["accession"] == "syn3219045" and r["acceso"] == "controlado"
    assert r["url"] == "https://www.synapse.org/Synapse:syn3219045" and r["tipo"] == "bulk" and r["region"] == "corteza prefrontal"
    assert any(DP.NOTA_CONTROLADO in x for x in r["registro"]) and any("ROSMAP" in x for x in r["registro"])


def test_expression_atlas_y_arrayexpress_e_geod_comparten_muestras_con_su_gse():
    e = _e()
    DP.desde_expression_atlas(e, {"accession": "E-GEOD-1297", "descripcion": "Alzheimer's disease and the normal aged hippocampus", "tipo": "MICROARRAY_1COLOUR_MRNA_DIFFERENTIAL", "especie": "Homo sapiens", "ensayos": 31}, "inv-1", 1)
    r = e["datasetsPrograma"][0]
    assert r["fuente"] == "expression_atlas" and r["muestrasCompartidasCon"] == ["GSE1297"] and r["tipo"] == "bulk"
    assert r["n"]["muestras"] == 31 and "contraste enfermedad frente a control" in r["procesado"] and r["organismo"] == "Homo sapiens"
    assert any("importación de GSE1297" in x for x in r["registro"])
    DP.desde_expression_atlas(e, {"accession": "E-CURD-140", "descripcion": "Single nucleus RNA-seq of human MTG", "tipo": "SINGLE_NUCLEUS_RNASEQ_MRNA_BASELINE", "especie": "Homo sapiens", "ensayos": 84}, "inv-1", 2)
    assert e["datasetsPrograma"][1]["tipo"] == "celula_unica" and e["datasetsPrograma"][1]["muestrasCompartidasCon"] == [] and e["datasetsPrograma"][1]["region"] == "giro temporal medio"
    DP.desde_arrayexpress(e, {"accession": "E-GEOD-48350", "titulo": "Alzheimer brain regions", "tipo": "study", "fecha": "2013-06-20"}, "inv-1", 3)
    assert e["datasetsPrograma"][2]["muestrasCompartidasCon"] == ["GSE48350"] and e["datasetsPrograma"][2]["url"].endswith("/E-GEOD-48350")
    DP.desde_arrayexpress(e, {"accession": "E-MTAB-8108", "titulo": "Proteomics of CSF", "tipo": "study", "fecha": None}, None, 4)
    assert e["datasetsPrograma"][3]["muestrasCompartidasCon"] == [] and e["datasetsPrograma"][3]["tipo"] == "proteomica" and e["datasetsPrograma"][3]["tejido"] == "líquido cefalorraquídeo"


def test_desde_dataset_subido_mapea_el_libro_de_procedencia():
    e = _e()
    ds = {"id": "ds-1", "nombre": "OASIS-1 volúmenes", "descripcion": "nWBV por CDR", "procedencia": {"origen": "OASIS-1", "hash": "abcdef0123456789", "fichero": "oasis1.csv", "filas": 416, "licencia": "OASIS Data Use Terms", "acceso": "abierto", "cohorte": "OASIS", "sintetico": False}}
    DP.desde_dataset_subido(e, "inv-1", ds, 1)
    r = e["datasetsPrograma"][0]
    assert r["fuente"] == "manual" and r["accession"] == "OASIS-1" and r["fichero"] == "oasis1.csv" and r["n"]["muestras"] == 416
    assert r["acceso"] == "registro" and r["tipo"] == "imagen" and "CDR" in r["estadio"]
    e2 = _e()
    DP.desde_dataset_subido(e2, "inv-1", {"nombre": "Datos del laboratorio", "procedencia": {"hash": "ff00ff00ff00ff00", "acceso": "colaboracion"}}, 1)
    assert e2["datasetsPrograma"][0]["accession"] == "sha256:ff00ff00ff00" and e2["datasetsPrograma"][0]["acceso"] == "controlado"
    e3 = _e()
    DP.desde_dataset_subido(e3, "inv-1", {"nombre": "Propio", "procedencia": {"acceso": "propio"}}, 1)
    assert e3["datasetsPrograma"][0]["acceso"] == "desconocido"


# -- Acceso controlado ------------------------------------------------------------


def test_acceso_controlado_por_cohorte_y_por_frase():
    for texto, termino in (("Samples were obtained from ROSMAP participants", "ROSMAP"), ("Alzheimer's Disease Neuroimaging Initiative plasma", "ADNI"), ("Mount Sinai Brain Bank tissue", "MSBB"), ("Data available through the AD Knowledge Portal", "AD Knowledge Portal"), ("Individual-level data are controlled access through dbGaP", "controlled access")):
        acceso, motivo, terminos = DP.evaluar_acceso(texto, "abierto")
        assert acceso == "controlado" and termino in terminos and "no lo pide" in motivo, texto


def test_marcar_acceso_controlado_sobre_un_registro_geo():
    e = _e()
    DP.desde_geo(e, "GSE125583", {**GSE1297, "accession": "GSE125583", "titulo": "RNA-seq of fusiform gyrus", "resumen": "Brain tissue from 219 ROSMAP and Mount Sinai Brain Bank donors."}, "inv-1", 1)
    r = e["datasetsPrograma"][0]
    assert r["acceso"] == "controlado"
    assert any("ROSMAP" in x and "MSBB" in x and DP.NOTA_CONTROLADO in x for x in r["registro"])
    # Un acceso controlado no vuelve a abierto aunque llegue otra entrada abierta.
    DP.registrar(e, DP.nuevo_registro("geo", "GSE125583", {"titulo": "RNA-seq of fusiform gyrus", "acceso": "abierto"}, 2))
    assert e["datasetsPrograma"][0]["acceso"] == "controlado" and len(e["datasetsPrograma"]) == 1
    # Un acceso desconocido sí se completa con uno concreto.
    e2 = _e()
    DP.registrar(e2, DP.nuevo_registro("manual", "X", {"titulo": "t"}, 1))
    DP.registrar(e2, DP.nuevo_registro("manual", "X", {"titulo": "t", "acceso": "abierto"}, 2))
    assert e2["datasetsPrograma"][0]["acceso"] == "abierto"


def test_sea_ad_no_baja_a_controlado_solo_por_nombrar_el_portal():
    acceso, motivo, terminos = DP.evaluar_acceso("SEA-AD raw 10x data are available through the AD Knowledge Portal; processed h5ad on AWS", "abierto")
    assert acceso == "abierto" and terminos == [] and "SEA-AD" in motivo
    # Pero si además nombra una cohorte controlada, baja.
    assert DP.evaluar_acceso("SEA-AD compared with ROSMAP via the AD Knowledge Portal", "abierto")[0] == "controlado"


def test_oasis_es_acceso_con_registro():
    acceso, motivo, _ = DP.evaluar_acceso("OASIS-3 longitudinal MRI", "abierto")
    assert acceso == "registro" and "registro gratuito" in motivo
    # Si ya es controlado, OASIS no lo sube.
    assert DP.evaluar_acceso("OASIS-3 and ADNI", "abierto")[0] == "controlado"
    assert DP.evaluar_acceso("OASIS-3", "controlado")[0] == "controlado"


# -- Muestras compartidas --------------------------------------------------------


def test_muestras_compartidas_por_reanalisis_misma_cohorte_y_subconjunto():
    e = _e()
    DP.desde_geo(e, "GSE9000", {**GSE1297, "accession": "GSE9000", "titulo": "Reanalysis of hippocampal arrays", "resumen": "This dataset is a reanalysis of GSE5281 and a subset of GSE1297, same cohort."}, "inv-1", 1)
    r = e["datasetsPrograma"][0]
    assert r["muestrasCompartidasCon"] == ["GSE5281", "GSE1297"]
    assert not any(x == "GSE9000" for x in r["muestrasCompartidasCon"])  # nunca consigo mismo
    assert any("comparte muestras con GSE5281" in x and "reanaliza" in x for x in r["registro"])


def test_superseries_comparte_con_sus_subseries():
    hallado = DP.detectar_muestras_compartidas("This SuperSeries is composed of the following SubSeries: GSE48350 GSE48351.", "GSE48352")
    assert [x["accession"] for x in hallado] == ["GSE48350", "GSE48351"] and all("SuperSeries" in x["motivo"] for x in hallado)


def test_accession_citado_sin_frase_queda_como_posible_y_a_comprobar():
    hallado = DP.detectar_muestras_compartidas("Compare with GSE5281 and syn3388564 and E-MTAB-8108 and PXD012345.", "GSE1")
    assert [x["accession"] for x in hallado] == ["GSE5281", "syn3388564", "E-MTAB-8108", "PXD012345"]
    assert all("posible" in x["motivo"] and "comprobar" in x["motivo"] for x in hallado)
    # Repetidos y el propio no se cuentan.
    assert [x["accession"] for x in DP.detectar_muestras_compartidas("GSE1 GSE1 gse2 GSE2", "gse1")] == ["GSE2"]


def test_muestras_compartidas_se_funden_al_registrar_dos_veces():
    e = _e()
    DP.desde_geo(e, "GSE1", {**GSE1297, "accession": "GSE1", "resumen": "Reanalysis of GSE2"}, None, 1)
    DP.desde_geo(e, "GSE1", {**GSE1297, "accession": "GSE1", "resumen": "Reanalysis of GSE3"}, None, 2)
    assert e["datasetsPrograma"][0]["muestrasCompartidasCon"] == ["GSE2", "GSE3"]


# -- Texto y coincidencias --------------------------------------------------------


def test_texto_registro_lleva_tildes_y_sin_guiones_largos():
    e = _e()
    DP.desde_geo(e, "GSE1297", GSE1297, "inv-1", 1)
    DP.desde_cellxgene(e, SEA_AD_CX, "inv-2", 2)
    DP.desde_synapse(e, SYN, "inv-2", 3)
    t = DP.texto_registro(e, "inv-2")
    assert "\u2014" not in t  # sin guiones largos
    assert "célula única" in t and "expresión en tejido (bulk)" in t and "células" in t
    assert t.startswith("Datasets registrados en el programa: 3 (los de esta investigación primero)")
    assert "1 de acceso controlado que el proyecto no pide" in t
    lineas = t.splitlines()
    # Los de inv-2 primero (los dos más recientes), GSE1297 después.
    assert "GSE1297" in lineas[-1] and "syn3219045" in lineas[1]
    assert "controlado (el proyecto no lo pide)" in lineas[1]
    assert "comparte muestras" not in t
    # Tope y resto.
    corto = DP.texto_registro(e, None, maximo=1)
    assert corto.endswith("... y 2 más.") and corto.count("\n- ") == 1
    # Textos del módulo sin tildes perdidas.
    for palabra in ("expresión", "célula", "proteómica", "genética", "región", "Ningún", "más"):
        assert palabra in " ".join([t, corto, DP.texto_registro({}), DP.ETIQUETA_TIPO["proteomica"], DP.ETIQUETA_TIPO["genetica"], DP.inferir_tejido("")[2]])


def test_coincidencias_por_tejido_estadio_y_tipo_con_motivo():
    e = _e()
    DP.desde_geo(e, "GSE1297", GSE1297, "inv-1", 1)
    DP.desde_cellxgene(e, {**SEA_AD_CX, "nombre": "SEA-AD: single-nucleus atlas of the middle temporal gyrus, Braak staged"}, "inv-1", 2)
    DP.desde_geo(e, "GSE7", {**GSE1297, "accession": "GSE7", "titulo": "Plasma proteomics in ROSMAP", "resumen": "Olink panel", "tipo": "Protein profiling by protein array"}, None, 3)
    c = DP.coincidencias(e, "¿Qué cambia en el hipocampo en célula única con Braak?")
    # Los dos empatan a tres términos (GSE1297: tejido, región y estadio; SEA-AD:
    # tejido, estadio y tipo): el recuento no inventa un orden entre ellos.
    assert {x["accession"] for x in c[:2]} == {"GSE1297", SEA_AD_CX["id"]} and len(c) == 2
    por_acc = {x["accession"]: x for x in c}
    assert por_acc["GSE1297"]["coincide"] == ["tejido: cerebro", "región: hipocampo", "estadio: Braak"] and por_acc["GSE1297"]["motivo"].startswith("coincide en ")
    assert por_acc[SEA_AD_CX["id"]]["coincide"] == ["tejido: cerebro", "estadio: Braak", "tipo: célula única"]
    assert all(x["accession"] != "GSE7" for x in c)
    # Con la región sola, GSE1297 gana por un término (región) al atlas del giro temporal.
    solo = DP.coincidencias(e, "hipocampo")
    assert solo[0]["accession"] == "GSE1297" and solo[0]["coincide"] == ["tejido: cerebro", "región: hipocampo"]
    assert len(solo) == 2 and solo[1]["accession"] == SEA_AD_CX["id"] and solo[1]["coincide"] == ["tejido: cerebro"]
    # La pregunta en inglés casa igual; y una de proteómica en plasma trae la controlada con aviso.
    c2 = DP.coincidencias(e, "plasma proteomics")
    assert c2 and c2[0]["accession"] == "GSE7" and c2[0]["aviso"] == DP.NOTA_CONTROLADO and c2[0]["acceso"] == "controlado"
    # "expresión" a solas pide bulk y célula única.
    c3 = DP.coincidencias(e, "expresión de genes en Alzheimer")
    assert {x["accession"] for x in c3} == {"GSE1297", SEA_AD_CX["id"]}
    # Sin términos no hay coincidencias, y a igualdad de términos la abierta va antes que la controlada.
    assert DP.coincidencias(e, "¿Y ahora qué?") == []


def test_coincidencias_con_campos_tecleados_en_ingles():
    e = {"datasetsPrograma": [{"id": "dsp-x", "fuente": "manual", "accession": "M1", "titulo": "Own cohort", "tejido": "blood", "estadio": "MCI", "tipo": "proteomica"}]}
    c = DP.coincidencias(e, "sangre en deterioro cognitivo leve, proteómica")
    assert c and c[0]["coincide"] == ["tejido: sangre", "estadio: deterioro cognitivo leve", "tipo: proteómica"]


# -- Célula única: perfil y pseudobulk -------------------------------------------


class _Mini:
    """Lo mínimo que `pseudobulk_por_donante` necesita de un AnnData."""

    def __init__(self, obs, X, genes, layers=None, raw=None):
        self.obs = obs
        self.X = X
        self.var_names = pd.Index(genes)
        self.layers = layers or {}
        self.raw = raw


def _mini():
    obs = pd.DataFrame({"donor": ["d1", "d1", "d2", "d2", "d2", "d3"], "tipo": ["Astro", "Astro", "Astro", "Micro", "Micro", "Micro"]})
    X = np.array([[1, 2, 0], [3, 4, 0], [5, 6, 1], [7, 8, 0], [9, 10, 0], [0, 0, 5]])
    return _Mini(obs, X, ["GFAP", "APOE", "TREM2"])


def test_pseudobulk_suma_por_donante_y_tipo_y_devuelve_enteros():
    df = DP.pseudobulk_por_donante(_mini(), "donor", "tipo", minimo_celulas=0)
    assert list(df.index.names) == ["donante", "tipoCelular"] and list(df.columns) == ["GFAP", "APOE", "TREM2"]
    assert df.loc[("d1", "Astro")].tolist() == [4, 6, 0] and df.loc[("d2", "Micro")].tolist() == [16, 18, 0] and df.loc[("d2", "Astro")].tolist() == [5, 6, 1]
    assert df.to_numpy().dtype.kind == "i" and df.attrs["cuentasCrudas"] is True and df.attrs["capa"] == "X" and df.attrs["aviso"] == ""
    assert {"donante": "d1", "tipoCelular": "Astro", "celulas": 2} in df.attrs["celulas"] and df.attrs["excluidos"] == []
    assert any("6 células de 3 donantes en 4 grupos" in x for x in df.attrs["registro"])


def test_pseudobulk_excluye_grupos_pequenos_con_motivo():
    df = DP.pseudobulk_por_donante(_mini(), "donor", "tipo", minimo_celulas=2)
    assert df.index.tolist() == [("d1", "Astro"), ("d2", "Micro")]
    assert {(x["donante"], x["tipoCelular"]) for x in df.attrs["excluidos"]} == {("d2", "Astro"), ("d3", "Micro")}
    assert all("1 célula, menos del mínimo de 2" in x["motivo"] for x in df.attrs["excluidos"])


def test_pseudobulk_con_matriz_dispersa_y_capa():
    from scipy import sparse

    m = _mini()
    m.layers = {"counts": sparse.csr_matrix(m.X)}
    m.X = np.log1p(m.X / m.X.sum(axis=1, keepdims=True).clip(min=1))  # X normalizada
    df = DP.pseudobulk_por_donante(m, "donor", "tipo", capa="counts", minimo_celulas=0)
    assert df.loc[("d2", "Micro")].tolist() == [16, 18, 0] and df.attrs["capa"] == "layers['counts']"
    # Sin capa: X no son cuentas y no hay raw, así que suma X con aviso.
    df2 = DP.pseudobulk_por_donante(m, "donor", "tipo", minimo_celulas=0)
    assert df2.attrs["cuentasCrudas"] is False and "no parece de cuentas crudas" in df2.attrs["aviso"] and df2.to_numpy().dtype.kind == "f"
    # Con raw de cuentas, la elige sola.
    m.raw = _Mini(m.obs, sparse.csr_matrix(np.array([[1, 2, 0], [3, 4, 0], [5, 6, 1], [7, 8, 0], [9, 10, 0], [0, 0, 5]])), ["GFAP", "APOE", "TREM2"])
    df3 = DP.pseudobulk_por_donante(m, "donor", "tipo", minimo_celulas=0)
    assert df3.attrs["capa"] == "raw.X" and df3.loc[("d1", "Astro")].tolist() == [4, 6, 0]


def test_pseudobulk_errores_explicados():
    m = _mini()
    with pytest.raises(ValueError, match="no está en obs"):
        DP.pseudobulk_por_donante(m, "donante", "tipo")
    with pytest.raises(ValueError, match="no está en layers"):
        DP.pseudobulk_por_donante(m, "donor", "tipo", capa="counts")
    with pytest.raises(ValueError, match="no tiene raw"):
        DP.pseudobulk_por_donante(m, "donor", "tipo", capa="raw.X")
    vacio = _Mini(pd.DataFrame({"donor": pd.Series([], dtype=str), "tipo": pd.Series([], dtype=str)}), np.zeros((0, 2)), ["A", "B"])
    df = DP.pseudobulk_por_donante(vacio, "donor", "tipo")
    assert df.shape == (0, 2) and df.attrs["aviso"] == "sin células"


def test_parece_cuentas_distingue_normalizado():
    assert DP.parece_cuentas(np.array([[0, 1], [2, 3]]))[0] is True
    assert DP.parece_cuentas(np.array([[0.5, 1], [2, 3]]))[0] is False
    assert DP.parece_cuentas(np.array([[-1, 1], [2, 3]]))[0] is False
    assert DP.parece_cuentas(None) == (None, "sin matriz X")


@pytest.mark.skipif(HAY_ANNDATA, reason="anndata está instalado: se prueba el perfil real")
def test_perfil_h5ad_sin_anndata_devuelve_el_motivo_sin_romper(tmp_path):
    p = DP.perfil_h5ad(tmp_path / "no.h5ad")
    assert p["motivo"] == "anndata no está instalado en este entorno"
    assert p["celulas"] is None and p["cuentasCrudas"] is None and p["columnasObs"] == []


@pytest.mark.skipif(not HAY_ANNDATA, reason="anndata no está instalado en este entorno")
def test_perfil_y_pseudobulk_sobre_anndata_sintetico(tmp_path):
    import anndata
    from scipy import sparse

    rng = np.random.default_rng(0)
    X = sparse.csr_matrix(rng.poisson(1.0, size=(60, 5)).astype(np.float32))
    obs = pd.DataFrame({"donor_id": [f"d{i % 4}" for i in range(60)], "Subclass": ["Astro" if i % 3 else "Micro" for i in range(60)]}, index=[f"c{i}" for i in range(60)])
    adata = anndata.AnnData(X=X, obs=obs, var=pd.DataFrame(index=[f"g{j}" for j in range(5)]))
    ruta = tmp_path / "sint.h5ad"
    adata.write_h5ad(ruta)
    p = DP.perfil_h5ad(ruta)
    assert p["celulas"] == 60 and p["donantes"] == 4 and set(p["tiposCelulares"]) == {"Astro", "Micro"} and p["cuentasCrudas"] is True
    assert "donor_id" in p["columnasObs"] and "donor_id" in p["motivo"] and "Subclass" in p["motivo"]
    df = DP.pseudobulk_por_donante(anndata.read_h5ad(ruta), "donor_id", "Subclass", minimo_celulas=0)
    esperado = np.asarray(X[(obs["donor_id"] == "d1") & (obs["Subclass"] == "Astro")].sum(axis=0)).ravel()
    assert df.loc[("d1", "Astro")].tolist() == esperado.astype(int).tolist()
    assert DP.perfil_h5ad(tmp_path / "no.h5ad")["motivo"].startswith("el fichero no existe")


# -- Adversariales (segunda pasada) ------------------------------------------------


def test_nuevo_registro_con_ahora_vacio_o_texto_no_rompe():
    for ahora in (None, "1000", 1.5, "x", [], {}):
        r = DP.nuevo_registro("geo", "GSE1", {"titulo": "t"}, ahora)
        assert isinstance(r["registradoEn"], int) and r["registradoEn"] == r["actualizadoEn"]
    assert DP.nuevo_registro("geo", "GSE1", {}, "1000")["registradoEn"] == 1000
    # datos que no son un diccionario o con `registro` en cadena tampoco rompen.
    assert DP.nuevo_registro("geo", "GSE1", "no soy un dict", 1)["accession"] == "GSE1"
    assert DP.nuevo_registro("geo", "GSE2", {"registro": "una línea"}, 1)["registro"][0] == "una línea"
    # Un id ajeno en datos no se cuela como id del registro; uno dsp- sí se respeta.
    assert DP.nuevo_registro("geo", "GSE3", {"id": "ds-123"}, 1)["id"] != "ds-123"
    assert DP.nuevo_registro("geo", "GSE3", {"id": "dsp-fijo"}, 1)["id"] == "dsp-fijo"


def test_registrar_con_entradas_que_no_son_diccionarios_y_estado_sucio():
    e = {}
    for ent in (None, "x", 5, []):
        assert DP.registrar(e, ent) == ""
    assert e.get("datasetsPrograma", []) == []  # no toca nada
    # `datasetsPrograma` de otra época que no es una lista (None) se crea de nuevo.
    for v in (None, "x", {}, 5):
        e2 = {"datasetsPrograma": v}
        assert DP.registrar(e2, DP.nuevo_registro("geo", "GSE1", {}, 1)).startswith("dsp")
        assert isinstance(e2["datasetsPrograma"], list) and len(e2["datasetsPrograma"]) == 1
        # Las lecturas sobre un estado así no lo tocan ni rompen.
        assert DP.texto_registro({"datasetsPrograma": v}) == "Ningún dataset registrado en el programa todavía."
        assert DP.coincidencias({"datasetsPrograma": v}, "hipocampo") == []
        assert DP.buscar({"datasetsPrograma": v}, "geo", "GSE1") is None
        assert not DP.marcar_uso({"datasetsPrograma": v}, "dsp-x", "inv-1")
    # Elementos que no son diccionarios dentro de la lista se saltan en todas las funciones.
    e3 = {"datasetsPrograma": [None, "x", 5, {"fuente": "geo", "accession": "GSE1"}]}
    assert DP.registrar(e3, DP.nuevo_registro("geo", "GSE1", {"titulo": "t"}, 1)) == e3["datasetsPrograma"][3]["id"]
    assert len(e3["datasetsPrograma"]) == 4 and "GSE1" in DP.texto_registro(e3)
    assert DP.buscar(e3, "geo", "GSE1") is e3["datasetsPrograma"][3]
    assert DP.marcar_uso(e3, e3["datasetsPrograma"][3]["id"], "inv-1")
    assert DP.coincidencias(e3, "x") == []


def test_registro_antiguo_con_valores_de_otra_epoca_se_lee_como_hoy_y_se_funde():
    e = {"datasetsPrograma": [{"fuente": "GEO", "accession": "gse1", "tipo": "single_cell", "acceso": "publico", "n": 7, "usadoEn": "inv-1", "region": "hippocampus", "muestrasCompartidasCon": "gse2"}]}
    assert DP.buscar(e, "GEO", "GSE1") is e["datasetsPrograma"][0]  # la fuente en mayúsculas es la misma
    id_ = DP.registrar(e, DP.nuevo_registro("geo", "GSE1", {"usadoEn": ["inv-2"]}, 1))
    r = e["datasetsPrograma"][0]
    assert len(e["datasetsPrograma"]) == 1 and r["id"] == id_
    assert r["fuente"] == "geo" and r["tipo"] == "celula_unica" and r["acceso"] == "abierto" and r["n"]["muestras"] == 7
    assert r["usadoEn"] == ["inv-1", "inv-2"] and r["muestrasCompartidasCon"] == ["GSE2"]
    # Una fuente que no existe cae a manual y lo dice, una sola vez.
    e2 = {"datasetsPrograma": [{"fuente": "dropbox", "accession": "A"}]}
    DP.completar_todos(e2)
    DP.completar_todos(e2)
    assert e2["datasetsPrograma"][0]["fuente"] == "manual" and sum("desconocida" in x for x in e2["datasetsPrograma"][0]["registro"]) == 1


def test_completar_todos_y_las_lecturas_no_mutan_el_estado():
    e = {"datasetsPrograma": [{"fuente": "geo", "accession": "GSE9", "n": 3}]}
    antes = json.dumps(e, sort_keys=True)
    DP.texto_registro(e)
    c1 = DP.coincidencias(e, "x")
    DP.buscar(e, "geo", "GSE9")
    assert json.dumps(e, sort_keys=True) == antes  # la lectura no escribe
    assert c1 == []
    # El id de un registro antiguo sin id es el mismo en cada lectura y en la escritura.
    e2 = {"datasetsPrograma": [{"fuente": "geo", "accession": "GSE9", "titulo": "Hippocampus"}]}
    ids = {DP.coincidencias(e2, "hipocampo")[0]["id"] for _ in range(3)}
    assert len(ids) == 1 and ids.pop().startswith("dsp-heredado-")
    assert DP.completar_todos(e2) == 1 and e2["datasetsPrograma"][0]["id"].startswith("dsp-heredado-")
    assert DP.completar_todos(e2) == 0
    # Sin la clave, la crea.
    e3 = {}
    assert DP.completar_todos(e3) == 0 and e3["datasetsPrograma"] == []


def test_duplicados_heredados_con_la_misma_clave_se_funden_en_el_primero():
    e = {"datasetsPrograma": [{"id": "a", "fuente": "geo", "accession": "GSE1", "usadoEn": ["inv-1"]}, {"id": "b", "fuente": "geo", "accession": "gse1", "usadoEn": ["inv-2"], "acceso": "controlado"}, {"id": "c", "fuente": "geo", "accession": "GSE2"}]}
    assert DP.registrar(e, DP.nuevo_registro("geo", "GSE1", {"usadoEn": ["inv-3"]}, 1)) == "a"
    assert [r["id"] for r in e["datasetsPrograma"]] == ["a", "c"]
    r = e["datasetsPrograma"][0]
    assert r["usadoEn"] == ["inv-1", "inv-2", "inv-3"] and r["acceso"] == "controlado" and any("fundido con el registro duplicado b" in x for x in r["registro"])


def test_al_fundir_gana_el_acceso_mas_restrictivo():
    e = {}
    DP.registrar(e, DP.nuevo_registro("geo", "GSE1", {"acceso": "abierto"}, 1))
    DP.registrar(e, DP.nuevo_registro("geo", "GSE1", {"acceso": "registro"}, 2))
    assert e["datasetsPrograma"][0]["acceso"] == "registro"
    DP.registrar(e, DP.nuevo_registro("geo", "GSE1", {"acceso": "abierto"}, 3))
    assert e["datasetsPrograma"][0]["acceso"] == "registro"
    DP.registrar(e, DP.nuevo_registro("geo", "GSE1", {"acceso": "desconocido"}, 4))
    assert e["datasetsPrograma"][0]["acceso"] == "registro"
    assert any("gana el más restrictivo" in x for x in e["datasetsPrograma"][0]["registro"])


def test_cohortes_controladas_en_minusculas_tambien_cuentan():
    for texto in ("samples from rosmap participants", "adni plasma", "msbb tissue", "ROS/MAP donors"):
        assert DP.evaluar_acceso(texto, "abierto")[0] == "controlado", texto
    # "ros" a solas sigue sin ser ROSMAP (especies reactivas de oxígeno).
    assert DP.evaluar_acceso("ros production in astrocytes", "abierto")[0] == "abierto"
    # La excepción SEA-AD vale igual en minúsculas.
    assert DP.evaluar_acceso("sea-ad through the ad knowledge portal", "abierto")[0] == "abierto"
    # Un texto que no es cadena no rompe.
    assert DP.evaluar_acceso(None, "abierto") == ("abierto", "", [])
    assert not DP.marcar_acceso_controlado(None, "ADNI")


def test_frase_de_reutilizacion_es_la_mas_cercana_y_de_la_misma_oracion():
    h = DP.detectar_muestras_compartidas("This is a reanalysis of GSE1 and a subset of GSE2.", "GSE9")
    assert [(x["accession"], "reanaliza" in x["motivo"], "subconjunto" in x["motivo"]) for x in h] == [("GSE1", True, False), ("GSE2", False, True)]
    # La frase después del accession también vale ("GSE1 was reanalyzed").
    assert "reanaliza" in DP.detectar_muestras_compartidas("GSE1 was reanalyzed here.", "GSE9")[0]["motivo"]
    # Otra oración no explica el accession: queda como posible y a comprobar.
    h2 = DP.detectar_muestras_compartidas("Reanalysis of public data. See also GSE9 for context.", "GSE1")
    assert h2[0]["accession"] == "GSE9" and "posible" in h2[0]["motivo"]
    # Texto que no es cadena, propio en minúsculas y accessions con mayúsculas raras.
    assert DP.detectar_muestras_compartidas(None, "x") == [] and DP.detectar_muestras_compartidas(123, "x") == []
    assert DP.detectar_muestras_compartidas("subset of GSE1297 and SYN123456 and e-geod-5", "gse1297") == [{"accession": "syn123456", "motivo": "el resumen dice que es un subconjunto de otro dataset; cita syn123456"}, {"accession": "E-GEOD-5", "motivo": "el resumen dice que es un subconjunto de otro dataset; cita E-GEOD-5"}]


def test_e_geod_no_recibe_una_linea_contradictoria_y_la_equivalencia_es_general():
    e = {}
    DP.desde_expression_atlas(e, {"accession": "E-GEOD-1297", "descripcion": "GSE1297: Alzheimer hippocampus", "tipo": "MICROARRAY_1COLOUR_MRNA_DIFFERENTIAL"}, None, 1)
    lineas = [x for x in e["datasetsPrograma"][0]["registro"] if "GSE1297" in x]
    assert len(lineas) == 1 and "importación de GSE1297" in lineas[0] and e["datasetsPrograma"][0]["muestrasCompartidasCon"] == ["GSE1297"]
    # Registrar un E-GEOD a mano también enlaza con su GSE.
    r = DP.nuevo_registro("arrayexpress", "e-geod-5281", {}, 1)
    assert r["muestrasCompartidasCon"] == ["GSE5281"] and r["accession"] == "e-geod-5281"


def test_tejido_y_region_conservan_todas_las_regiones_del_texto():
    tejido, region, motivo = DP.inferir_tejido("Entorhinal cortex, hippocampus, medial temporal gyrus, posterior cingulate, superior frontal gyrus and primary visual cortex")
    assert tejido == "cerebro" and region == "hipocampo; corteza entorrinal; giro temporal medio; corteza frontal; corteza occipital; corteza cingulada" and "regiones" in motivo
    assert DP.inferir_tejido("plasma and brain tissue")[0] == "cerebro; sangre"
    e = {}
    DP.desde_geo(e, "GSE5281", {**GSE1297, "accession": "GSE5281", "titulo": "Alzheimer's disease and the normal aged brain", "resumen": "Entorhinal cortex, hippocampus, medial temporal gyrus, posterior cingulate, superior frontal gyrus, primary visual cortex"}, None, 1)
    # La pregunta por cualquiera de las regiones casa, y el texto las lista.
    for pregunta in ("hipocampo", "corteza entorrinal", "visual cortex"):
        assert DP.coincidencias(e, pregunta)[0]["accession"] == "GSE5281", pregunta
    assert "cerebro (hipocampo; corteza entorrinal" in DP.texto_registro(e)
    # Coincide también por un tejido tecleado como segundo valor.
    e2 = {"datasetsPrograma": [{"fuente": "manual", "accession": "M", "titulo": "t", "tejido": "sangre; líquido cefalorraquídeo"}]}
    assert DP.coincidencias(e2, "CSF")[0]["coincide"] == ["tejido: líquido cefalorraquídeo"]


def test_un_rna_seq_que_menciona_pet_sigue_siendo_expresion():
    assert DP.inferir_tipo("Blood RNA-seq from amyloid PET positive participants")[0] == "bulk"
    assert DP.inferir_tipo("MRI volumes by CDR")[0] == "imagen"
    assert DP.inferir_tipo("snRNA-seq of PET-positive donors")[0] == "celula_unica"


def test_desde_geo_sin_nada_que_registrar_y_con_datos_raros():
    e = {}
    assert DP.desde_geo(e, "", None, None, 1) is None and DP.desde_geo(e, None, {}, None, 1) is None
    assert e.get("datasetsPrograma", []) == []
    # Datos que no son un diccionario cuentan como "no pude comprobar".
    assert DP.desde_geo(e, "GSE1", ["x"], "inv-1", 1).startswith("dsp")
    assert any("sin comprobar" in x for x in e["datasetsPrograma"][0]["registro"])
    # pubmed como cadena no se trocea en dígitos.
    e2 = {}
    DP.desde_geo(e2, "GSE1", {"accession": "GSE1", "pubmed": "14769913", "tipo": "Expression profiling by array"}, None, 1)
    assert any(x == "artículos PubMed: 14769913" for x in e2["datasetsPrograma"][0]["registro"])
    # Synapse con id en mayúsculas se guarda como syn.
    e3 = {}
    DP.desde_synapse(e3, {"id": "SYN123456", "nombre": "x"}, None, 1)
    assert e3["datasetsPrograma"][0]["accession"] == "syn123456"


def test_desde_dataset_subido_con_hash_entero_y_filas_cero():
    e = {}
    DP.desde_dataset_subido(e, "inv-1", {"nombre": "x", "procedencia": {"filas": 0, "hash": 12345678901234}}, 1)
    r = e["datasetsPrograma"][0]
    assert r["accession"] == "sha256:123456789012" and r["n"]["muestras"] is None
    assert DP.desde_dataset_subido(e, "inv-1", None, 1) is None and DP.desde_dataset_subido(e, "inv-1", {"nombre": "y", "procedencia": "no dict"}, 1).startswith("dsp")


def test_texto_registro_con_maximo_raro_y_muchos_usos():
    e = {}
    DP.registrar(e, DP.nuevo_registro("geo", "GSE1", {"usadoEn": [f"inv-{i}" for i in range(7)], "muestrasCompartidasCon": [f"GSE{i}" for i in range(2, 9)]}, 1))
    t = DP.texto_registro(e, None, maximo=0)
    assert "usado en inv-0, inv-1, inv-2, inv-3 y 3 más" in t and "comparte muestras con GSE2, GSE3, GSE4, GSE5 y 3 más" in t
    assert DP.texto_registro(e, None, maximo="x").count("\n- ") == 1 and DP.texto_registro(e, None, maximo=None).count("\n- ") == 1


def test_pseudobulk_excluye_celulas_sin_donante_o_tipo_y_explica_formas_incompatibles():
    obs = pd.DataFrame({"donor": ["d1", None, "d2", np.nan], "tipo": pd.Categorical(["A", "A", None, "B"])})
    X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
    df = DP.pseudobulk_por_donante(_Mini(obs, X, ["g1", "g2"]), "donor", "tipo", minimo_celulas=0)
    assert df.index.tolist() == [("d1", "A")] and df.loc[("d1", "A")].tolist() == [1, 2]
    assert any("3 células sin donante o sin tipo celular" in x for x in df.attrs["registro"])
    assert json.dumps(df.attrs)  # todo lo de attrs es serializable
    # Ninguna célula completa: pseudobulk vacío explicado, sin excepción.
    obs2 = pd.DataFrame({"donor": [None, None], "tipo": ["A", "B"]})
    df2 = DP.pseudobulk_por_donante(_Mini(obs2, np.ones((2, 2)), ["g1", "g2"]), "donor", "tipo")
    assert df2.shape == (0, 2) and "sin células con donante" in df2.attrs["aviso"]
    # Matriz con otras filas que obs: error en castellano, no un fallo de scipy.
    with pytest.raises(ValueError, match="no son el mismo conjunto de células"):
        DP.pseudobulk_por_donante(_Mini(obs, np.zeros((3, 2)), ["g1", "g2"]), "donor", "tipo")
    # Una matriz ilegible: aviso de "no pude comprobar" si se puede multiplicar, error explicado si no.

    class Rara:
        shape = (4, 2)

        def __getitem__(self, k):
            raise RuntimeError("no")

    with pytest.raises(ValueError, match="no pude multiplicar"):
        DP.pseudobulk_por_donante(_Mini(obs, Rara(), ["g1", "g2"]), "donor", "tipo", minimo_celulas=0)
    # minimo_celulas raro.
    for m in (None, -5, "3"):
        assert DP.pseudobulk_por_donante(_mini(), "donor", "tipo", minimo_celulas=m).shape[1] == 3
    with pytest.raises(ValueError, match="tabla obs"):
        DP.pseudobulk_por_donante(_Mini([1], X, ["a", "b"]), "donor", "tipo")


def test_parece_cuentas_con_matrices_raras():
    assert DP.parece_cuentas(np.array([1, 2, 3]))[0] is True
    assert DP.parece_cuentas(np.array([["a", "b"]]))[0] is False and "no es numérica" in DP.parece_cuentas(np.array([["a", "b"]]))[1]
    assert DP.parece_cuentas(np.zeros((0, 3))) == (None, "no pude leer valores de la matriz")


def test_textos_generados_llevan_tildes_y_no_guiones_largos():
    import inspect
    import re
    import unicodedata

    def sin_tildes(palabra):
        return "".join(c for c in unicodedata.normalize("NFKD", palabra) if not unicodedata.combining(c))

    fuente = inspect.getsource(DP)
    assert "\u2014" not in fuente
    # Todo lo que el módulo escribe para una persona, sobre un estado en castellano.
    e = {}
    DP.desde_geo(e, "GSE1", {"accession": "GSE1", "titulo": "Expresión génica en hipocampo, deterioro cognitivo leve", "resumen": "Reanálisis de GSE2 en la cohorte ADNI", "tipo": "Expression profiling by array", "n_muestras": "3"}, "inv-1", 1)
    DP.desde_geo(e, "GSE3", None, "inv-1", 2)
    DP.desde_dataset_subido(e, "inv-1", {"nombre": "Propio", "procedencia": {"acceso": "propio", "sintetico": True}}, 3)
    df = DP.pseudobulk_por_donante(_mini(), "donor", "tipo", minimo_celulas=100)
    # Solo los valores que lee una persona, no las claves (que son identificadores sin tilde).
    textos = [DP.texto_registro(e, "inv-1"), DP.texto_registro({}), DP._perfil_vacio("anndata no está instalado en este entorno")["motivo"], DP.inferir_tejido("")[2], DP.inferir_estadio("")[1], DP.inferir_tipo("")[1], " ".join(DP.ETIQUETA_TIPO.values()), " ".join(DP.ETIQUETA_ACCESO.values()), DP.NOTA_CONTROLADO, df.attrs["aviso"], *df.attrs["registro"], *(x["motivo"] for x in df.attrs["excluidos"])]
    for r in e["datasetsPrograma"]:
        textos += [r["titulo"], r["tejido"], r["region"], r["estadio"], r["procesado"], r["licencia"], *r["registro"]]
    for c in DP.coincidencias(e, "hipocampo"):
        textos.append(c["motivo"] + " " + c.get("aviso", ""))
    todo = "\n".join(textos)
    assert "\u2014" not in todo
    con_tilde = ("célula", "células", "expresión", "proteómica", "genética", "región", "ningún", "investigación", "todavía", "público", "públicos", "única", "más", "mínimo", "según", "también", "vía", "sintético", "respondió", "reanálisis", "observación", "relación", "reutilización", "importación", "artículos")
    for palabra in con_tilde:
        assert not re.search(r"(?<![a-záéíóúñ])" + sin_tildes(palabra) + r"(?![a-záéíóúñ])", todo), palabra
    assert "célula única" in todo and "expresión" in todo and "Ningún" in todo and "mínimo" in todo
