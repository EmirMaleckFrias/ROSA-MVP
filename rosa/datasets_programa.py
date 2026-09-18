"""Registro curado de datasets a nivel de programa y lectura de célula única.

Hoy ROSA2018 descubre datasets con los conectores (`geo_series`, `geo_serie`,
`cellxgene_colecciones`, `synapse_buscar`, `arrayexpress_experimentos`,
`expression_atlas_experimentos`) y cura solo el fichero que una persona sube a
una investigación (libro de procedencia en `plantilla.procedencia_dataset_vacia`).
Lo que faltaba, y este módulo añade, son tres cosas:

1. Un **registro a nivel de programa** (`e["datasetsPrograma"]`): cada dataset
   público que ROSA2018 nombró alguna vez queda una sola vez, con su fuente, su
   accession, lo que se sabe de él (tejido, región, estadio, tipo, n,
   plataforma, acceso, licencia), en qué investigaciones se usó y con qué
   otros datasets comparte muestras. Un "dataset" aquí es un conjunto de datos
   publicado con identificador estable (una serie GSE de GEO, una colección de
   CELLxGENE, una entidad syn de Synapse, un experimento E-MTAB o E-GEOD).
2. Reglas deterministas y explicables sobre esos metadatos: qué tipo de dato
   es, de qué tejido y estadio habla, si reutiliza muestras de otro dataset
   (un GSE que "reanaliza" otro, una SuperSeries, la importación E-GEOD de una
   serie GEO) y si la cohorte de origen es de acceso controlado (ADNI, ROSMAP,
   MSBB, AD Knowledge Portal). Cada juicio deja su motivo en `registro`.
3. La lectura de **célula única**: `perfil_h5ad` describe un fichero h5ad (el
   formato de AnnData: una matriz células por genes con tablas de anotación) y
   `pseudobulk_por_donante` suma las cuentas de todas las células de un mismo
   donante y tipo celular. "Pseudobulk" quiere decir eso: convertir miles de
   células en una muestra por donante, porque las células de un mismo donante
   no son observaciones independientes y compararlas entre sí infla los
   p-valores. La regla de ROSA2018 es comparar donantes, nunca células.

Reglas que este módulo respeta: una fuente que no responde es "no pude
comprobar", nunca "no hay"; un registro antiguo sin las claves nuevas (o con
valores de otra época: `n: 7`, `usadoEn: "inv-1"`, fuente `GEO`, acceso
`publico`) se lee como el valor de hoy y nunca rompe; solo datos públicos (un
dataset controlado se registra como tal con la nota de que el proyecto no lo
pide); nada de puntuaciones combinadas. Las funciones de lectura
(`texto_registro`, `coincidencias`, `buscar`) no modifican el estado; las de
escritura (`registrar`, `marcar_uso`, `desde_*`) sí, y solo en
`e["datasetsPrograma"]`.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

from rosa import metodos as METODOS
from rosa.estado import plantilla as P

FUENTES = ("geo", "cellxgene", "synapse", "arrayexpress", "expression_atlas", "manual")
TIPOS = ("bulk", "celula_unica", "proteomica", "genetica", "imagen", "otro")
ACCESOS = ("abierto", "registro", "controlado", "desconocido")
# De menos a más restrictivo: al fundir dos registros gana el más restrictivo
# (un controlado nunca vuelve a abierto; un "con registro" no baja a abierto).
_RANGO_ACCESO = {"desconocido": 0, "abierto": 1, "registro": 2, "controlado": 3}

ETIQUETA_FUENTE = {"geo": "GEO", "cellxgene": "CELLxGENE", "synapse": "Synapse", "arrayexpress": "ArrayExpress", "expression_atlas": "Expression Atlas", "manual": "manual"}
ETIQUETA_TIPO = {"bulk": "expresión en tejido (bulk)", "celula_unica": "célula única", "proteomica": "proteómica", "genetica": "genética", "imagen": "imagen", "otro": "otro"}
ETIQUETA_ACCESO = {"abierto": "abierto", "registro": "con registro", "controlado": "controlado (el proyecto no lo pide)", "desconocido": "acceso sin comprobar"}

NOTA_CONTROLADO = "acceso controlado: el proyecto trabaja solo con datos públicos y no lo pide"


# Cohortes (por su etiqueta canónica en rosa/metodos.py) cuyo dato individual
# exige acuerdo de uso. La copia procesada en GEO o CELLxGENE puede ser
# pública, pero las variables clínicas y los datos por persona no lo son.
COHORTES_CONTROLADAS = ("ADNI", "ROSMAP", "MSBB", "AMP-AD")
# Cohortes públicas con registro gratuito (OASIS): se piden, sin acuerdo de uso.
COHORTES_CON_REGISTRO = ("OASIS",)
# `metodos.cohortes_en_texto` solo acepta las siglas en mayúsculas (para que
# "ros" no sea ROSMAP). Aquí el coste de no ver una cohorte controlada es usar
# un dato que el proyecto no pide, así que estas siglas, que en minúsculas no
# significan otra cosa, se aceptan también en minúsculas.
_SIGLAS_INEQUIVOCAS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ROSMAP", ("rosmap", "ros/map", "ros-map")),
    ("ADNI", ("adni",)),
    ("MSBB", ("msbb",)),
    ("AMP-AD", ("amp-ad", "ampad")),
    ("SEA-AD", ("sea-ad", "seaad")),
    ("OASIS", ("oasis-1", "oasis-2", "oasis-3", "oasis-4", "oasis1", "oasis3")),
)
# Frases que por sí solas marcan acceso controlado.
_FRASES_CONTROLADO = (
    ("ad knowledge portal", "AD Knowledge Portal"),
    ("controlled access", "controlled access"),
    ("controlled-access", "controlled-access"),
    ("data use certificate", "data use certificate"),
    ("data use agreement", "data use agreement"),
    ("dbgap", "dbGaP"),
    ("niagads", "NIAGADS"),
)

_ACCESSION = re.compile(r"\b(GSE\d{1,7}|E-(?:MTAB|GEOD|MEXP|TABM|ENAD|CURD)-\d{1,7}|syn\d{5,10}|PXD\d{5,7})\b", re.I)
_REUTILIZACION = (
    (re.compile(r"\b(?:re-?analy[sz](?:is|ed|e)|re-?processed|re-?processing)\b", re.I), "el resumen dice que reanaliza datos ya publicados"),
    (re.compile(r"\bsame (?:cohort|donors?|subjects?|samples?|individuals?|patients?|participants?|brains?)\b", re.I), "el resumen habla de la misma cohorte o de los mismos donantes"),
    (re.compile(r"\bsubset of\b", re.I), "el resumen dice que es un subconjunto de otro dataset"),
    (re.compile(r"\bsuperseries\b", re.I), "la serie es una SuperSeries de GEO: agrupa las SubSeries que cita, con sus muestras"),
    (re.compile(r"\bpreviously (?:published|described|reported|deposited|generated)\b", re.I), "el resumen dice que las muestras ya se publicaron o depositaron antes"),
    (re.compile(r"\b(?:deposited|available|described|published) (?:under|as|in|at)\b", re.I), "el resumen remite a otro depósito de los mismos datos"),
)
# Fin de frase: una frase de reutilización solo explica los accessions de su
# misma oración ("Reanalysis of public data. See also GSE9" no dice que GSE9
# se reanalice).
_FIN_DE_FRASE = re.compile(r"[.!?;]\s")

# Vocabulario de tejido y región. Etiqueta que ve la persona (con tildes) y
# alias en minúsculas; los alias se normalizan (sin tildes) antes de comparar,
# así que los castellanos llevan su tilde. Un alias que termina en "*" admite
# sufijo (transcriptom* cubre transcriptome y transcriptomic).
_TEJIDOS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("cerebro", "hipocampo", ("hippocampus", "hippocampal", "hipocampo", "hipocampal", "ca1", "ca3", "dentate gyrus", "giro dentado")),
    ("cerebro", "corteza entorrinal", ("entorhinal", "entorrinal")),
    ("cerebro", "giro temporal medio", ("middle temporal gyrus", "medial temporal gyrus", "mtg", "giro temporal medio")),
    ("cerebro", "corteza temporal", ("temporal cortex", "superior temporal", "inferior temporal", "temporal lobe", "corteza temporal", "lóbulo temporal")),
    ("cerebro", "corteza prefrontal", ("prefrontal", "dlpfc", "ba9")),
    ("cerebro", "corteza frontal", ("frontal cortex", "frontal gyrus", "frontal lobe", "corteza frontal")),
    ("cerebro", "corteza parietal", ("parietal",)),
    ("cerebro", "corteza occipital", ("occipital", "visual cortex", "corteza visual")),
    ("cerebro", "corteza cingulada", ("cingulate", "cingulada", "cingulado")),
    ("cerebro", "cerebelo", ("cerebellum", "cerebellar", "cerebelo")),
    ("cerebro", "amígdala", ("amygdala", "amigdala")),
    ("cerebro", "sustancia blanca", ("white matter", "sustancia blanca")),
    ("cerebro", "", ("brain", "cerebro", "cerebral", "cortex", "corteza", "cortical", "neocortex", "postmortem", "post-mortem", "neuron*", "glia*", "astrocyt*", "microglia*", "oligodendrocyt*")),
    ("sangre", "", ("blood", "plasma", "serum", "pbmc", "leukocyt*", "monocyt*", "sangre", "suero", "sanguine*")),
    ("líquido cefalorraquídeo", "", ("csf", "cerebrospinal", "lcr", "cefalorraquídeo")),
    ("retina", "", ("retina", "retinal")),
    ("iPSC / organoide", "", ("ipsc", "organoid*", "organoide*", "induced pluripotent")),
)

_ESTADIOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Braak", ("braak",)),
    ("CERAD", ("cerad",)),
    ("ADNC", ("adnc", "neuropathologic change", "neuropathological change")),
    ("Thal", ("thal phase", "thal")),
    ("CDR", ("cdr", "clinical dementia rating")),
    ("MMSE", ("mmse", "mini-mental", "mini mental")),
    ("deterioro cognitivo leve", ("mci", "mild cognitive impairment", "deterioro cognitivo leve", "dcl")),
    ("preclínico", ("preclinical", "preclínico", "asymptomatic", "asintomático")),
    ("incipiente", ("incipient", "early-stage", "early stage", "early ad", "incipiente")),
    ("moderado", ("moderate", "moderado", "moderada")),
    ("grave", ("severe", "grave", "late-stage", "late stage", "avanzado", "avanzada")),
    ("inicio temprano", ("early-onset", "early onset", "eoad", "inicio temprano")),
    ("inicio tardío", ("late-onset", "late onset", "inicio tardío")),
    ("APOE4", ("apoe4", "apoe e4", "apoe-e4", "e4 carrier*", "portador* de apoe4")),
)

# El orden importa: célula única antes que bulk porque "expression profiling
# by high throughput sequencing" es la misma frase de GEO para los dos; e
# imagen al final porque las fuentes de ROSA2018 son depósitos de expresión y un
# resumen de RNA-seq que dice "amyloid PET positive" sigue siendo expresión.
_TIPOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("celula_unica", ("single-cell", "single cell", "single-nucleus", "single nucleus", "snrna*", "scrna*", "nuclei", "10x genomics", "10x chromium", "célula única", "células únicas", "núcleo único", "drop-seq", "smart-seq*", "snatac*", "scatac*", "multiome", "cellxgene", "sea-ad")),
    ("proteomica", ("proteom*", "mass spectrometry", "tmt", "olink", "somascan", "protein profiling", "proteoma")),
    ("genetica", ("gwas", "genotyp*", "whole genome", "whole-genome", "wgs", "exome", "snp array", "genome variation", "genetic association", "genome-wide association", "genética", "genotipo", "polygenic", "poligénic*")),
    ("bulk", ("expression profiling", "gene expression", "differential expression", "expresión génica", "expresión de genes", "expresión diferencial", "rna-seq", "rnaseq", "rna sequencing", "microarray", "transcriptom*", "affymetrix", "illumina", "agilent", "bulk", "mrna", "hta-2", "u133", "hg-u133")),
    ("imagen", ("mri", "pet", "imaging", "neuroimaging", "resonancia", "tomografía", "imagen", "volumetr*", "volumen*", "brain volume", "nwbv", "cortical thickness", "grosor cortical", "atrophy", "atrofia", "amyloid pet", "tau pet")),
)
# "expresión" a solas no decide entre bulk y célula única: una pregunta que
# solo dice eso pide los dos tipos.
_EXPRESION_GENERICA = ("expresión", "expression", "expresan", "expressed")

# Columnas habituales de donante y de tipo celular en los h5ad públicos
# (SEA-AD, CELLxGENE, series GEO de célula única).
CANDIDATAS_DONANTE = ("donor_id", "Donor ID", "donor", "donorID", "individualID", "individual_id", "individual", "subject", "subject_id", "patient", "patient_id", "sample_id", "sample")
CANDIDATAS_TIPO = ("cell_type", "Subclass", "Supertype", "Class", "subclass", "supertype", "celltype", "cell_type_ontology_term_label", "broad.cell.type", "subclass_label", "cluster", "leiden", "louvain")


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------


def _norm(texto: Any) -> str:
    """Minúsculas, sin tildes y con espacios simples, para comparar."""
    s = unicodedata.normalize("NFKD", str(texto if texto is not None else "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()


# Valores de otra época o tecleados a mano que se leen como los de hoy. Las
# claves se escriben con su tilde y se normalizan (minúsculas, sin tildes)
# con `_norm` al importar, igual que el texto con el que se comparan.
_ALIAS_FUENTE = {_norm(k): v for k, v in {"geo": "geo", "ncbi geo": "geo", "gds": "geo", "cellxgene": "cellxgene", "cxg": "cellxgene", "cellxgene discover": "cellxgene", "synapse": "synapse", "ad knowledge portal": "synapse", "arrayexpress": "arrayexpress", "array express": "arrayexpress", "biostudies": "arrayexpress", "expression_atlas": "expression_atlas", "expression atlas": "expression_atlas", "gxa": "expression_atlas", "manual": "manual", "subido": "manual", "subida": "manual", "propio": "manual"}.items()}
_ALIAS_TIPO = {_norm(k): v for k, v in {"bulk": "bulk", "expresión": "bulk", "expression": "bulk", "rna-seq": "bulk", "rnaseq": "bulk", "microarray": "bulk", "transcriptómica": "bulk", "celula_unica": "celula_unica", "célula única": "celula_unica", "single_cell": "celula_unica", "single-cell": "celula_unica", "single cell": "celula_unica", "single_nucleus": "celula_unica", "scrna": "celula_unica", "snrna": "celula_unica", "scrna-seq": "celula_unica", "snrna-seq": "celula_unica", "proteómica": "proteomica", "proteomics": "proteomica", "genética": "genetica", "genetics": "genetica", "genómica": "genetica", "genomics": "genetica", "imagen": "imagen", "imaging": "imagen", "image": "imagen", "neuroimagen": "imagen", "otro": "otro", "other": "otro"}.items()}
_ALIAS_ACCESO = {_norm(k): v for k, v in {"abierto": "abierto", "abierta": "abierto", "público": "abierto", "public": "abierto", "open": "abierto", "open access": "abierto", "registro": "registro", "con registro": "registro", "registration": "registro", "controlado": "controlado", "controlada": "controlado", "controlled": "controlado", "controlled access": "controlado", "restringido": "controlado", "restricted": "controlado", "colaboración": "controlado", "desconocido": "desconocido", "unknown": "desconocido", "propio": "desconocido"}.items()}


def _patron(alias: str) -> re.Pattern[str]:
    cola = "" if alias.endswith("*") else r"(?![a-z0-9])"
    return re.compile(r"(?<![a-z0-9])" + re.escape(alias.rstrip("*")) + cola)


_CACHE_PATRONES: dict[str, re.Pattern[str]] = {}


def _hay(alias: str, texto_norm: str) -> bool:
    p = _CACHE_PATRONES.get(alias)
    if p is None:
        p = _CACHE_PATRONES[alias] = _patron(_norm(alias.rstrip("*")) + ("*" if alias.endswith("*") else ""))
    return bool(p.search(texto_norm))


def _entero(v: Any) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        n = int(float(str(v).strip().replace(",", "")))
    except (TypeError, ValueError, OverflowError):
        return None
    return n if n >= 0 else None


def _tiempo(ahora: Any) -> int:
    """El instante en milisegundos; si no viene o no es un número, el de ahora."""
    n = _entero(ahora)
    return n if n is not None else P.ahora_ms()


def _texto(*partes: Any) -> str:
    return " ".join(str(p) for p in partes if p)


def _cadena(v: Any) -> str:
    return str(v).strip() if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""


def _partes(v: Any) -> list[str]:
    """Un campo multivalor ('hipocampo; corteza entorrinal') como lista."""
    return [x.strip() for x in str(v or "").split(";") if x.strip()]


def inferir_tipo(texto: str) -> tuple[str, str]:
    """El tipo de dato por las palabras del texto, con el motivo. Devuelve
    ("otro", motivo) si nada encaja: nunca inventa."""
    t = _norm(texto)
    for tipo, aliases in _TIPOS:
        for a in aliases:
            if _hay(a, t):
                return tipo, f"tipo {ETIQUETA_TIPO[tipo]}: el texto dice '{a.rstrip('*')}'"
    return "otro", "tipo otro: el texto no nombra expresión, célula única, proteómica, genética ni imagen"


def inferir_tejido(texto: str) -> tuple[str, str, str]:
    """(tejido, región, motivo). Todos los tejidos y regiones que el texto
    nombra, unidos por '; ' en el orden del vocabulario: un dataset de seis
    regiones (GSE5281) las conserva todas. La región solo se rellena para el
    cerebro; un texto que solo dice 'brain' da tejido cerebro y región vacía."""
    t = _norm(texto)
    tejidos: list[str] = []
    regiones: list[str] = []
    dichos: list[str] = []
    for tejido, region, aliases in _TEJIDOS:
        for a in aliases:
            if _hay(a, t):
                if tejido not in tejidos:
                    tejidos.append(tejido)
                if region and region not in regiones:
                    regiones.append(region)
                dichos.append(a.rstrip("*"))
                break
    if not tejidos:
        return "", "", "tejido sin comprobar: el texto no nombra tejido ni región"
    donde = "; ".join(tejidos) + ((", región " if len(regiones) == 1 else ", regiones ") + "; ".join(regiones) if regiones else "")
    return "; ".join(tejidos), "; ".join(regiones), f"tejido {donde}: el texto dice " + ", ".join(f"'{d}'" for d in dichos)


def inferir_estadio(texto: str) -> tuple[str, str]:
    """Las escalas y estadios nombrados (Braak, CERAD, deterioro cognitivo leve,
    preclínico...), unidos por '; ', con el motivo."""
    t = _norm(texto)
    hallados: list[str] = []
    dichos: list[str] = []
    for etiqueta, aliases in _ESTADIOS:
        for a in aliases:
            if _hay(a, t):
                hallados.append(etiqueta)
                dichos.append(a.rstrip("*"))
                break
    if not hallados:
        return "", "estadio sin comprobar: el texto no nombra escalas ni estadios"
    return "; ".join(hallados), "estadio " + ", ".join(hallados) + ": el texto dice " + ", ".join(f"'{d}'" for d in dichos)


def inferir_organismo(texto: str) -> str:
    t = _norm(texto)
    if _hay("homo sapiens", t) or _hay("human", t) or _hay("humano*", t):
        return "Homo sapiens"
    if _hay("mus musculus", t) or _hay("mouse", t) or _hay("mice", t) or _hay("raton*", t):
        return "Mus musculus"
    return ""


# ---------------------------------------------------------------------------
# Reglas: muestras compartidas y acceso controlado
# ---------------------------------------------------------------------------


def _normalizar_accession(acc: str) -> str:
    acc = (acc or "").strip()
    return acc.lower() if acc.lower().startswith("syn") else acc.upper()


def detectar_muestras_compartidas(texto: str, propio: str = "") -> list[dict[str, str]]:
    """Otros datasets con los que este comparte muestras, por regla: cualquier
    accession (GSE, E-MTAB, E-GEOD, syn, PXD) citado en el título o resumen,
    con el motivo que lo acompaña ("reanalysis of", "same cohort", "subset
    of", SuperSeries...). La frase que explica cada accession es la más
    cercana dentro de su misma oración (antes que él, o después si no hay
    ninguna antes); un accession citado sin frase de reutilización también
    sale, marcado como posible y a comprobar."""
    if not isinstance(texto, str) or not texto.strip():
        return []
    frases = sorted(((m.start(), m.end(), motivo) for patron, motivo in _REUTILIZACION for m in patron.finditer(texto)), key=lambda x: x[0])
    salida: list[dict[str, str]] = []
    vistos = {_normalizar_accession(propio).upper()} if propio else set()
    for m in _ACCESSION.finditer(texto):
        acc = _normalizar_accession(m.group(1))
        if acc.upper() in vistos:
            continue
        vistos.add(acc.upper())
        frase = _frase_mas_cercana(texto, frases, m.start(), m.end())
        if frase:
            motivo = frase + f"; cita {acc}"
        else:
            motivo = f"el texto cita {acc} sin decir la relación: posible reutilización de muestras, comprobar"
        salida.append({"accession": acc, "motivo": motivo})
    return salida


def _frase_mas_cercana(texto: str, frases: list[tuple[int, int, str]], ini: int, fin: int) -> str:
    antes = [f for f in frases if f[1] <= ini and not _FIN_DE_FRASE.search(texto[f[1] : ini])]
    if antes:
        return antes[-1][2]
    despues = [f for f in frases if f[0] >= fin and not _FIN_DE_FRASE.search(texto[fin : f[0]])]
    return despues[0][2] if despues else ""


def equivalencia_geo(accession: str) -> dict[str, str] | None:
    """E-GEOD-1297 es la importación de GSE1297 en ArrayExpress y Expression
    Atlas: mismas muestras, otro identificador."""
    m = re.fullmatch(r"E-GEOD-(\d+)", str(accession or "").strip(), re.I)
    if not m:
        return None
    gse = f"GSE{m.group(1)}"
    return {"accession": gse, "motivo": f"{str(accession).strip().upper()} es la importación de {gse} (GEO) en ArrayExpress y Expression Atlas: mismas muestras"}


def _cohortes_nombradas(texto: str) -> set[str]:
    """Las etiquetas canónicas de las cohortes que nombra el texto: las que ve
    `metodos.cohortes_en_texto` (misma regla que el Killer) más las siglas
    inequívocas escritas en minúsculas."""
    etiquetas = {c["etiqueta"] for c in METODOS.cohortes_en_texto(texto or "")}
    t = _norm(texto)
    for etiqueta, aliases in _SIGLAS_INEQUIVOCAS:
        if etiqueta not in etiquetas and any(_hay(a, t) for a in aliases):
            etiquetas.add(etiqueta)
    return etiquetas


def evaluar_acceso(texto: str, acceso_actual: str = "desconocido") -> tuple[str, str, list[str]]:
    """(acceso, motivo, términos). Controlado si el texto nombra una cohorte
    de acceso controlado (ADNI, ROSMAP, MSBB, AMP-AD) o una frase de acceso
    controlado (AD Knowledge Portal, controlled access, dbGaP, NIAGADS).
    Excepción única: SEA-AD publica sus datos procesados abiertos en AWS y
    solo los crudos viven en el AD Knowledge Portal; si el texto nombra
    SEA-AD y la única señal es el portal, el acceso no baja a controlado.
    Con registro (OASIS) solo si no hay señal de controlado. Sin señal,
    devuelve el acceso actual sin tocarlo."""
    if not isinstance(texto, str) or not texto.strip():
        return acceso_actual, "", []
    t = _norm(texto)
    cohortes = _cohortes_nombradas(texto)
    terminos = [c for c in COHORTES_CONTROLADAS if c in cohortes]
    frases = [visible for clave, visible in _FRASES_CONTROLADO if clave in t]
    if "SEA-AD" in cohortes and not terminos and frases and all(f == "AD Knowledge Portal" for f in frases):
        return acceso_actual, "el texto nombra SEA-AD y el AD Knowledge Portal: los datos procesados de SEA-AD son abiertos en AWS y solo los crudos 10x son controlados; el acceso no cambia", []
    todos = terminos + frases
    if todos:
        return "controlado", "el texto nombra " + ", ".join(todos) + "; " + NOTA_CONTROLADO, todos
    con_registro = [c for c in COHORTES_CON_REGISTRO if c in cohortes]
    if con_registro and acceso_actual in ("abierto", "desconocido"):
        return "registro", "el texto nombra " + ", ".join(con_registro) + ": datos públicos con registro gratuito, sin acuerdo de uso", con_registro
    return acceso_actual, "", []


def marcar_acceso_controlado(registro: dict[str, Any], texto: str) -> bool:
    """Aplica `evaluar_acceso` al registro: si el texto nombra ADNI, ROSMAP,
    MSBB, el AD Knowledge Portal o 'controlled access', el acceso pasa a
    'controlado' y queda la nota de que el proyecto no lo pide. Un acceso ya
    controlado nunca vuelve a abierto. Devuelve si cambió algo."""
    if not isinstance(registro, dict):
        return False
    acceso, motivo, _ = evaluar_acceso(texto, registro.get("acceso") or "desconocido")
    lineas = registro.get("registro")
    if not isinstance(lineas, list):
        lineas = registro["registro"] = []
    if motivo and motivo not in lineas:
        lineas.append(motivo)
    if acceso == "controlado" and registro.get("acceso") != "controlado":
        registro["acceso"] = "controlado"
        return True
    if acceso == "registro" and registro.get("acceso") in ("abierto", "desconocido", None):
        registro["acceso"] = "registro"
        return True
    return False


# ---------------------------------------------------------------------------
# El registro
# ---------------------------------------------------------------------------


def _n_vacio() -> dict[str, int | None]:
    return {"muestras": None, "donantes": None, "celulas": None}


def _fuente_norm(v: Any) -> str:
    """La fuente como la escribe hoy el módulo; lo que no se reconoce es manual."""
    if v in FUENTES:
        return str(v)
    return _ALIAS_FUENTE.get(_norm(v), "manual")


def _tipo_norm(v: Any) -> str:
    if v in TIPOS:
        return str(v)
    return _ALIAS_TIPO.get(_norm(v), "otro")


def _acceso_norm(v: Any) -> str:
    if v in ACCESOS:
        return str(v)
    return _ALIAS_ACCESO.get(_norm(v), "desconocido")


def _id_heredado(fuente: str, accession: str) -> str:
    """Un id estable para un registro antiguo sin id: el mismo registro recibe
    el mismo id en cada lectura, así una pantalla y el bucle hablan del mismo."""
    return "dsp-heredado-" + hashlib.sha256(f"{fuente}|{accession.upper()}".encode("utf-8")).hexdigest()[:10]


def _lista_unica(v: Any) -> list[str]:
    """Una lista de cadenas sin repetir; una cadena suelta (registro antiguo
    con `usadoEn: "inv-1"`) cuenta como lista de un elemento."""
    if isinstance(v, str):
        v = [v]
    salida: list[str] = []
    for x in v if isinstance(v, (list, tuple, set)) else []:
        if isinstance(x, str) and x.strip() and x.strip() not in salida:
            salida.append(x.strip())
    return salida


def _lineas_unicas(lineas: Any) -> list[str]:
    if isinstance(lineas, str):
        lineas = [lineas]
    salida: list[str] = []
    for x in lineas if isinstance(lineas, (list, tuple)) else []:
        if isinstance(x, str) and x.strip() and x not in salida:
            salida.append(x)
    return salida


def _completar(r: dict[str, Any]) -> dict[str, Any]:
    """Un registro antiguo sin las claves de hoy, o con valores de otra época,
    se completa con los valores de hoy: `n: 7` son 7 muestras, `usadoEn:
    "inv-1"` es una lista, la fuente `GEO` es `geo`, el acceso `publico` es
    `abierto`, el tipo `single_cell` es `celula_unica`. Nunca rompe por una
    clave que falte. Modifica y devuelve el mismo diccionario."""
    fuente_bruta = r.get("fuente")
    r["fuente"] = _fuente_norm(fuente_bruta)
    r["accession"] = _cadena(r.get("accession"))
    lineas = _lineas_unicas(r.get("registro"))
    if fuente_bruta not in FUENTES and r["fuente"] == "manual" and fuente_bruta not in (None, "", "manual"):
        nota = f"fuente '{fuente_bruta}' desconocida: se registra como manual"
        if nota not in lineas:
            lineas.append(nota)
    if not _cadena(r.get("id")):
        r["id"] = _id_heredado(r["fuente"], r["accession"])
    for k in ("titulo", "organismo", "tejido", "region", "estadio", "plataforma", "procesado", "licencia", "url"):
        r[k] = _cadena(r.get(k))
    r["tipo"] = _tipo_norm(r.get("tipo"))
    r["acceso"] = _acceso_norm(r.get("acceso"))
    n = r.get("n")
    if isinstance(n, dict):
        r["n"] = {**_n_vacio(), **{k: _entero(n.get(k)) for k in ("muestras", "donantes", "celulas")}}
    else:
        r["n"] = {**_n_vacio(), "muestras": _entero(n)}
    r["fichero"] = r.get("fichero") if isinstance(r.get("fichero"), str) and r.get("fichero") else None
    r["muestrasCompartidasCon"] = [_normalizar_accession(x) for x in _lista_unica(r.get("muestrasCompartidasCon"))]
    r["usadoEn"] = _lista_unica(r.get("usadoEn"))
    r["registradoEn"] = _entero(r.get("registradoEn"))
    r["actualizadoEn"] = _entero(r.get("actualizadoEn")) or r["registradoEn"]
    r["registro"] = lineas
    return r


def nuevo_registro(fuente: str, accession: str, datos: dict[str, Any] | None, ahora: Any) -> dict[str, Any]:
    """Un registro nuevo, normalizado. `datos` trae lo que se sepa con las
    claves del registro (el título, el organismo, el tejido y la región, el
    estadio, el tipo, n como dict o como entero de muestras, la plataforma, lo
    procesado, el acceso, la licencia, la url, el fichero, las muestras
    compartidas, los usos y las líneas de registro) más un resumen o una
    descripción que solo alimentan las reglas y no se guardan. Lo que falte
    se infiere del texto por regla y se explica en `registro`; lo que no se
    pueda inferir queda vacío, no inventado. `ahora` son milisegundos; si no
    viene, el instante actual."""
    d = dict(datos) if isinstance(datos, dict) else {}
    lineas: list[str] = _lineas_unicas(d.get("registro"))
    if fuente not in FUENTES:
        fuente_norm = _fuente_norm(fuente)
        if fuente_norm == "manual" and fuente not in (None, "", "manual"):
            lineas.append(f"fuente '{fuente}' desconocida: se registra como manual")
        fuente = fuente_norm
    accession = _cadena(accession) or _cadena(d.get("accession"))
    titulo = _cadena(d.get("titulo"))
    if not accession:
        accession = "sin-accession-" + hashlib.sha256(_norm(_texto(fuente, titulo)).encode("utf-8")).hexdigest()[:10]
        lineas.append("sin accession: se deriva un identificador estable del título para no duplicarlo")
    texto = _texto(titulo, d.get("resumen"), d.get("descripcion"), d.get("tejido"), d.get("region"), d.get("estadio"))
    tipo = d.get("tipo")
    if tipo not in TIPOS:
        tipo = _tipo_norm(tipo) if tipo else "otro"
        if tipo == "otro":
            tipo, motivo_tipo = inferir_tipo(_texto(texto, d.get("tipoFuente")))
            lineas.append(motivo_tipo)
    tejido = _cadena(d.get("tejido"))
    region = _cadena(d.get("region"))
    if not tejido and not region:
        tejido, region, motivo_tej = inferir_tejido(texto)
        lineas.append(motivo_tej)
    estadio = _cadena(d.get("estadio"))
    if not estadio:
        estadio, motivo_est = inferir_estadio(texto)
        lineas.append(motivo_est)
    organismo = _cadena(d.get("organismo")) or inferir_organismo(texto)
    n_bruto = d.get("n")
    if isinstance(n_bruto, dict):
        n = {**_n_vacio(), **{k: _entero(n_bruto.get(k)) for k in ("muestras", "donantes", "celulas")}}
    else:
        n = {**_n_vacio(), "muestras": _entero(n_bruto)}
    compartidas = [_normalizar_accession(x) for x in _lista_unica(d.get("muestrasCompartidasCon"))]
    declaradas = set(compartidas)
    eq = equivalencia_geo(accession)
    if eq and eq["accession"] not in compartidas:
        compartidas.append(eq["accession"])
        declaradas.add(eq["accession"])
        lineas.append(f"comparte muestras con {eq['accession']}: {eq['motivo']}")
    for c in detectar_muestras_compartidas(_texto(titulo, d.get("resumen"), d.get("descripcion")), accession):
        if c["accession"] not in compartidas:
            compartidas.append(c["accession"])
        # Un accession que quien llama ya declaró (la equivalencia E-GEOD, por
        # ejemplo) no necesita la línea de "posible reutilización, comprobar".
        if c["accession"] not in declaradas or "sin decir la relación" not in c["motivo"]:
            lineas.append(f"comparte muestras con {c['accession']}: {c['motivo']}")
    instante = _tiempo(ahora)
    r: dict[str, Any] = {
        "id": _cadena(d.get("id")) if _cadena(d.get("id")).startswith("dsp-") else P.nuevo_id("dsp"),
        "fuente": fuente,
        "accession": accession,
        "titulo": titulo[:300],
        "organismo": organismo,
        "tejido": tejido,
        "region": region,
        "estadio": estadio,
        "tipo": tipo,
        "n": n,
        "plataforma": _cadena(d.get("plataforma")),
        "procesado": _cadena(d.get("procesado")),
        "acceso": _acceso_norm(d.get("acceso")) if d.get("acceso") else "desconocido",
        "licencia": _cadena(d.get("licencia")),
        "url": _cadena(d.get("url")),
        "fichero": d.get("fichero") if isinstance(d.get("fichero"), str) and d.get("fichero") else None,
        "muestrasCompartidasCon": compartidas,
        "usadoEn": _lista_unica(d.get("usadoEn")),
        "registradoEn": instante,
        "actualizadoEn": instante,
        "registro": _lineas_unicas(lineas),
    }
    marcar_acceso_controlado(r, texto)
    return r


def _es_actual(r: dict[str, Any]) -> bool:
    """Si el registro ya tiene la forma de hoy (claves y valores válidos)."""
    return bool(_cadena(r.get("id"))) and r.get("fuente") in FUENTES and r.get("tipo") in TIPOS and r.get("acceso") in ACCESOS and isinstance(r.get("n"), dict) and isinstance(r.get("usadoEn"), list) and isinstance(r.get("muestrasCompartidasCon"), list) and isinstance(r.get("registro"), list) and isinstance(r.get("accession"), str)


def completar_todos(e: dict[str, Any]) -> int:
    """Completa en el estado todos los registros de otra época (para la carga
    del estado, donde el almacén crea las claves que faltan). Devuelve
    cuántos cambió. Si `datasetsPrograma` falta o no es una lista, la crea."""
    cambiados = 0
    for r in _lista(e, crear=True):
        if isinstance(r, dict) and not _es_actual(r):
            _completar(r)
            cambiados += 1
    return cambiados


def _clave(r: dict[str, Any]) -> tuple[str, str]:
    """(fuente, accession en mayúsculas): gse1297 es GSE1297 y la fuente 'GEO'
    de un registro antiguo es 'geo'."""
    fuente = r.get("fuente")
    return (fuente if fuente in FUENTES else _fuente_norm(fuente), _cadena(r.get("accession")).upper())


def _lista(e: dict[str, Any], crear: bool) -> list[Any]:
    """`e["datasetsPrograma"]` como lista. Con `crear`, la crea si falta o si
    lo que hay no es una lista (un estado antiguo con `None`); sin `crear`,
    devuelve una lista vacía y no toca el estado."""
    v = e.get("datasetsPrograma") if isinstance(e, dict) else None
    if isinstance(v, list):
        return v
    if crear and isinstance(e, dict):
        e["datasetsPrograma"] = []
        return e["datasetsPrograma"]
    return []


def buscar(e: dict[str, Any], fuente: str, accession: str) -> dict[str, Any] | None:
    """El registro de (fuente, accession) tal como está en el estado, o None.
    No modifica el estado."""
    clave = (_fuente_norm(fuente), _cadena(accession).upper())
    for r in _lista(e, crear=False):
        if isinstance(r, dict) and _clave(r) == clave:
            return r
    return None


def _fundir(existente: dict[str, Any], nuevo: dict[str, Any]) -> None:
    """Funde `nuevo` en `existente` (los dos ya completos): los campos vacíos
    se rellenan, el tipo 'otro' cede ante uno concreto, el n se completa por
    clave, el acceso más restrictivo gana, y usadoEn, muestrasCompartidasCon
    y registro se unen sin repetir."""
    for k in ("titulo", "organismo", "tejido", "region", "estadio", "plataforma", "procesado", "licencia", "url"):
        if not existente.get(k) and nuevo.get(k):
            existente[k] = nuevo[k]
    if existente["tipo"] == "otro" and nuevo["tipo"] != "otro":
        existente["tipo"] = nuevo["tipo"]
    for k in ("muestras", "donantes", "celulas"):
        if existente["n"].get(k) is None and nuevo["n"].get(k) is not None:
            existente["n"][k] = nuevo["n"][k]
    if _RANGO_ACCESO[nuevo["acceso"]] > _RANGO_ACCESO[existente["acceso"]]:
        if existente["acceso"] != "desconocido":
            existente["registro"].append(f"acceso pasa de {ETIQUETA_ACCESO[existente['acceso']]} a {ETIQUETA_ACCESO[nuevo['acceso']]}: gana el más restrictivo")
        existente["acceso"] = nuevo["acceso"]
    if not existente.get("fichero") and nuevo.get("fichero"):
        existente["fichero"] = nuevo["fichero"]
    existente["usadoEn"] = _lista_unica(existente["usadoEn"] + nuevo["usadoEn"])
    existente["muestrasCompartidasCon"] = _lista_unica(existente["muestrasCompartidasCon"] + nuevo["muestrasCompartidasCon"])
    existente["registro"] = _lineas_unicas(existente["registro"] + nuevo["registro"])
    fechas = [x for x in (existente.get("actualizadoEn"), nuevo.get("actualizadoEn"), nuevo.get("registradoEn")) if x]
    existente["actualizadoEn"] = max(fechas) if fechas else None
    if existente.get("registradoEn") is None:
        existente["registradoEn"] = nuevo.get("registradoEn")


def registrar(e: dict[str, Any], entrada: dict[str, Any]) -> str:
    """Mete el registro en `e["datasetsPrograma"]` (la crea con setdefault si
    falta) sin repetir: la misma (fuente, accession) es el mismo dataset. Al
    fundir, `usadoEn` y `muestrasCompartidasCon` se unen; los campos vacíos
    del que ya estaba se rellenan con los del nuevo; el acceso más
    restrictivo gana (un controlado nunca vuelve a abierto); las líneas de
    registro nuevas se añaden. Si en la lista ya había varios registros con
    esa clave (duplicados de otra época) se funden en el primero. Devuelve el
    id que queda; con una entrada que no es un diccionario no toca nada y
    devuelve ''. Cuesta una pasada por la lista, no una completación de cada
    registro: sirve con miles de datasets."""
    if not isinstance(entrada, dict):
        return ""
    lista = _lista(e, crear=True)
    for r in lista:
        # Un registro de otra época se completa una sola vez, la primera vez
        # que se escribe en la lista; comprobar si hace falta cuesta unas
        # lecturas de diccionario por registro, no una completación.
        if isinstance(r, dict) and not _es_actual(r):
            _completar(r)
    nuevo = _completar(dict(entrada))
    clave = _clave(nuevo)
    indices = [i for i, r in enumerate(lista) if isinstance(r, dict) and _clave(r) == clave]
    if not indices:
        lista.append(nuevo)
        return nuevo["id"]
    existente = _completar(lista[indices[0]])
    for i in reversed(indices[1:]):
        duplicado = _completar(lista.pop(i))
        existente["registro"].append(f"fundido con el registro duplicado {duplicado['id']} de la misma fuente y accession")
        _fundir(existente, duplicado)
    _fundir(existente, nuevo)
    return existente["id"]


def marcar_uso(e: dict[str, Any], dataset_programa_id: str, investigacion_id: str) -> bool:
    """Anota que la investigación usó el dataset. Devuelve si lo encontró."""
    for r in _lista(e, crear=False):
        if isinstance(r, dict) and _cadena(r.get("id")) == _cadena(dataset_programa_id) and dataset_programa_id:
            _completar(r)
            if isinstance(investigacion_id, str) and investigacion_id.strip() and investigacion_id.strip() not in r["usadoEn"]:
                r["usadoEn"].append(investigacion_id.strip())
            return True
    return False


# ---------------------------------------------------------------------------
# Desde cada conector (la forma es la que devuelve cada uno, leída en
# rosa/conectores/bases.py y bases2.py; no se inventan campos)
# ---------------------------------------------------------------------------


def _usos(investigacion_id: str | None) -> list[str]:
    return [investigacion_id.strip()] if isinstance(investigacion_id, str) and investigacion_id.strip() else []


def _lista_de(v: Any) -> list[str]:
    """Una lista de cadenas a partir de una lista, una tupla o una cadena
    suelta (el conector da listas; un registro antiguo puede traer texto)."""
    if isinstance(v, str):
        return [v] if v.strip() else []
    return [str(x) for x in v if x not in (None, "")] if isinstance(v, (list, tuple)) else []


def desde_geo(e: dict[str, Any], accession: str, datos_geo_serie: dict[str, Any] | None, investigacion_id: str | None, ahora: Any) -> str | None:
    """Registra una serie GEO a partir de lo que devuelve `geo_serie`:
    accession, titulo, resumen, n_muestras (texto en E-utilities), plataforma
    (GPL, puede ser 'GPL96;GPL570'), organismo (taxon), tipo (gdstype), fecha,
    pubmed, ftp. También acepta una fila de `geo_series` (sin resumen ni ftp).
    Si el conector no respondió (`datos_geo_serie` es None o no es un
    diccionario) el dataset queda registrado con la nota de que no se pudo
    comprobar, nunca como inexistente. Sin accession y sin datos no hay nada
    que registrar: devuelve None."""
    s = datos_geo_serie if isinstance(datos_geo_serie, dict) else None
    accession = _cadena(accession).upper() or (_cadena(s.get("accession")).upper() if s else "")
    if s is None:
        if not accession:
            return None
        r = nuevo_registro("geo", accession, {"url": _url_geo(accession), "licencia": "Dominio público (NCBI GEO)", "acceso": "abierto", "usadoEn": _usos(investigacion_id), "registro": [f"GEO no respondió al pedir los metadatos de {accession}: quedan sin comprobar; no significa que la serie no exista"]}, ahora)
        return registrar(e, r)
    if not accession and not _cadena(s.get("titulo")):
        return None
    gds = _cadena(s.get("tipo"))
    lineas = [f"origen GEO, tipo de serie según GEO: {gds}" if gds else "origen GEO"]
    if s.get("fecha"):
        lineas.append(f"publicada en GEO el {s['fecha']}")
    pubmed = _lista_de(s.get("pubmed"))
    if pubmed:
        lineas.append("artículos PubMed: " + ", ".join(pubmed[:5]))
    lineas.append("donantes: el resumen de GEO no los da; las muestras pueden ser varias por donante (regiones pareadas, réplicas)")
    tipo = _tipo_desde_gds(gds, _texto(s.get("titulo"), s.get("resumen")))
    procesado = "Ficheros procesados por los autores (series matrix y suplementarios) en el FTP de GEO" + ("; crudos en SRA si es secuenciación" if "sequencing" in gds.lower() else "")
    r = nuevo_registro("geo", accession, {
        "titulo": s.get("titulo"),
        "resumen": s.get("resumen"),
        "organismo": s.get("organismo"),
        "tipo": tipo,
        "tipoFuente": gds,
        "n": {"muestras": _entero(s.get("n_muestras"))},
        "plataforma": s.get("plataforma"),
        "procesado": procesado,
        "acceso": "abierto",
        "licencia": "Dominio público (NCBI GEO)",
        "url": _url_geo(accession),
        "usadoEn": _usos(investigacion_id),
        "registro": lineas,
    }, ahora)
    return registrar(e, r)


def _url_geo(accession: str) -> str:
    return f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={accession}" if accession else ""


def _tipo_desde_gds(gds: str, texto: str) -> str | None:
    """El gdstype de GEO decide proteómica, genética y 'otro' (metilación,
    unión a genoma); para expresión, el título y el resumen deciden si es
    célula única o bulk. None deja la inferencia general a `nuevo_registro`."""
    g = gds.lower()
    if "protein" in g:
        return "proteomica"
    if "genome variation" in g or "snp" in g:
        return "genetica"
    if "methylation" in g or "genome binding" in g or "occupancy" in g:
        return "otro"
    if "expression profiling" in g or "non-coding rna" in g:
        tipo, _ = inferir_tipo(texto)
        return "celula_unica" if tipo == "celula_unica" else "bulk"
    return None


def desde_cellxgene(e: dict[str, Any], coleccion: dict[str, Any] | None, investigacion_id: str | None, ahora: Any) -> str | None:
    """Registra una colección de CELLxGENE Discover a partir de una fila de
    `cellxgene_colecciones`: id (collection_id), nombre, url, datasets (número),
    celulas (suma), doi. CELLxGENE es célula única por definición y exige
    CC BY 4.0 a todo lo que publica; el conector no devuelve organismo ni
    descripción, así que quedan sin comprobar salvo que el nombre los diga."""
    if not isinstance(coleccion, dict) or not _cadena(coleccion.get("id")):
        return None
    id_ = _cadena(coleccion["id"])
    lineas = ["origen CELLxGENE Discover: h5ad curado con el esquema de CZ (cuentas crudas en raw.X, tipo celular con Cell Ontology)"]
    if _entero(coleccion.get("datasets")) is not None:
        lineas.append(f"{_entero(coleccion.get('datasets'))} datasets en la colección")
    if coleccion.get("doi"):
        lineas.append(f"DOI de la colección: {coleccion['doi']}")
    lineas.append("organismo: el catálogo de colecciones no lo da por fila; comprobar en la colección")
    nombre = _cadena(coleccion.get("nombre"))
    if "SEA-AD" in _cohortes_nombradas(nombre):
        lineas.append("SEA-AD: los h5ad procesados también están abiertos en AWS (s3://sea-ad-single-cell-profiling, lectura sin firma); los crudos 10x son controlados vía AD Knowledge Portal y el proyecto no los pide")
    r = nuevo_registro("cellxgene", id_, {
        "titulo": nombre,
        "tipo": "celula_unica",
        "n": {"celulas": _entero(coleccion.get("celulas"))},
        "procesado": "h5ad por dataset con cuentas crudas en raw.X y anotación de tipo celular; descarga por dataset desde la colección",
        "acceso": "abierto",
        "licencia": "CC BY 4.0",
        "url": _cadena(coleccion.get("url")) or f"https://cellxgene.cziscience.com/collections/{id_}",
        "usadoEn": _usos(investigacion_id),
        "registro": lineas,
    }, ahora)
    return registrar(e, r)


def desde_synapse(e: dict[str, Any], entidad: dict[str, Any] | None, investigacion_id: str | None, ahora: Any) -> str | None:
    """Registra una entidad de Synapse (AD Knowledge Portal) a partir de una
    fila de `synapse_buscar`: id (syn...), nombre, tipo (node_type: project,
    folder, file, dataset...), descripcion. La búsqueda anónima solo ve
    metadatos públicos; los datos individuales exigen cuenta y acuerdo de
    uso, así que el acceso nace controlado con la nota del proyecto."""
    if not isinstance(entidad, dict) or not _cadena(entidad.get("id")):
        return None
    id_ = _normalizar_accession(_cadena(entidad["id"]))
    lineas = [f"origen Synapse (AD Knowledge Portal), entidad de tipo {_cadena(entidad.get('tipo')) or 'desconocido'}", "Synapse: los metadatos son públicos; los datos individuales exigen cuenta y acuerdo de uso (Data Use Certificate); " + NOTA_CONTROLADO]
    r = nuevo_registro("synapse", id_, {
        "titulo": entidad.get("nombre"),
        "descripcion": entidad.get("descripcion"),
        "procesado": "según la entidad; comprobar en Synapse qué ficheros procesados publica",
        "acceso": "controlado",
        "licencia": "Por nivel de acceso; datos individuales con acuerdo de uso",
        "url": f"https://www.synapse.org/Synapse:{id_}",
        "usadoEn": _usos(investigacion_id),
        "registro": lineas,
    }, ahora)
    return registrar(e, r)


def desde_arrayexpress(e: dict[str, Any], experimento: dict[str, Any] | None, investigacion_id: str | None, ahora: Any) -> str | None:
    """Registra un experimento de ArrayExpress (BioStudies) a partir de una
    fila de `arrayexpress_experimentos`: accession (E-MTAB-..., E-GEOD-...),
    titulo, tipo, fecha. Un E-GEOD es la importación de una serie GEO:
    `nuevo_registro` anota que comparte todas las muestras con ese GSE."""
    if not isinstance(experimento, dict) or not _cadena(experimento.get("accession")):
        return None
    acc = _cadena(experimento["accession"]).upper()
    lineas = ["origen ArrayExpress (BioStudies)" + (f", tipo {experimento.get('tipo')}" if _cadena(experimento.get("tipo")) else "")]
    if experimento.get("fecha"):
        lineas.append(f"publicado el {experimento['fecha']}")
    r = nuevo_registro("arrayexpress", acc, {
        "titulo": experimento.get("titulo"),
        "tipoFuente": experimento.get("tipo"),
        "procesado": "Ficheros procesados y crudos según el experimento (BioStudies)",
        "acceso": "abierto",
        "licencia": "Por experimento (BioStudies); comprobar en la ficha",
        "url": f"https://www.ebi.ac.uk/biostudies/arrayexpress/studies/{acc}",
        "usadoEn": _usos(investigacion_id),
        "registro": lineas,
    }, ahora)
    return registrar(e, r)


def desde_expression_atlas(e: dict[str, Any], experimento: dict[str, Any] | None, investigacion_id: str | None, ahora: Any) -> str | None:
    """Registra un experimento de Expression Atlas a partir de una fila de
    `expression_atlas_experimentos`: accession, descripcion, tipo
    (experimentType: RNASEQ_MRNA_DIFFERENTIAL, MICROARRAY_..._DIFFERENTIAL,
    SINGLE_NUCLEUS_RNASEQ_MRNA_BASELINE, PROTEOMICS_...), especie, ensayos.
    Expression Atlas reanaliza datos de GEO y ArrayExpress con un flujo único,
    así que un E-GEOD comparte muestras con su GSE (lo anota `nuevo_registro`)."""
    if not isinstance(experimento, dict) or not _cadena(experimento.get("accession")):
        return None
    acc = _cadena(experimento["accession"]).upper()
    et = _cadena(experimento.get("tipo")).upper()
    if "SINGLE" in et:
        tipo: str | None = "celula_unica"
    elif "PROTEOMICS" in et:
        tipo = "proteomica"
    elif et:
        tipo = "bulk"
    else:
        tipo = None
    contraste = "con contraste enfermedad frente a control" if "DIFFERENTIAL" in et else ("expresión basal, sin contraste" if "BASELINE" in et else "")
    lineas = ["origen Expression Atlas (EMBL-EBI)" + (f", tipo {et}" if et else "")]
    if _cadena(experimento.get("especie")):
        lineas.append(f"especie según Expression Atlas: {experimento['especie']}")
    r = nuevo_registro("expression_atlas", acc, {
        "titulo": experimento.get("descripcion"),
        "organismo": experimento.get("especie"),
        "tipo": tipo,
        "n": {"muestras": _entero(experimento.get("ensayos"))},
        "procesado": ("Reanalizado por Expression Atlas con su flujo estándar " + contraste).strip(),
        "acceso": "abierto",
        "licencia": "Términos EMBL-EBI",
        "url": f"https://www.ebi.ac.uk/gxa/experiments/{acc}",
        "usadoEn": _usos(investigacion_id),
        "registro": lineas,
    }, ahora)
    return registrar(e, r)


_ACCESO_DESDE_PROCEDENCIA = {"abierto": "abierto", "controlado": "controlado", "colaboracion": "controlado", "propio": "desconocido"}


def desde_dataset_subido(e: dict[str, Any], investigacion_id: str | None, dataset: dict[str, Any] | None, ahora: Any) -> str | None:
    """Registra en el programa un dataset que una persona subió a una
    investigación (forma de `Dataset` con su `procedencia`, ver tipos.ts):
    fuente manual, accession el origen declarado o el hash del fichero, y el
    acceso mapeado desde el libro de procedencia ('colaboracion' cuenta como
    controlado; 'propio' queda sin comprobar porque lo decide el equipo). Las
    filas 0 de la plantilla vacía no son un n: quedan sin comprobar."""
    if not isinstance(dataset, dict) or not _cadena(dataset.get("nombre")):
        return None
    proc = dataset.get("procedencia") if isinstance(dataset.get("procedencia"), dict) else {}
    hash_ = _cadena(proc.get("hash"))
    accession = _cadena(proc.get("origen")) or (f"sha256:{hash_[:12]}" if hash_ else "")
    lineas = ["origen manual: dataset subido por una persona a la investigación" + (f" {investigacion_id}" if _cadena(investigacion_id) else "")]
    if hash_:
        lineas.append(f"hash sha256 del fichero: {hash_}")
    if _cadena(proc.get("cohorte")):
        lineas.append(f"cohorte declarada: {proc['cohorte']}")
    if proc.get("sintetico"):
        lineas.append("dato sintético: nunca cuenta como observación")
    acceso = _ACCESO_DESDE_PROCEDENCIA.get(_cadena(proc.get("acceso")), "desconocido")
    if proc.get("acceso") == "propio":
        lineas.append("acceso 'propio' en el libro de procedencia: dato del laboratorio; el acceso lo decide el equipo, aquí queda sin comprobar")
    filas = _entero(proc.get("filas"))
    r = nuevo_registro("manual", accession, {
        "titulo": dataset.get("nombre"),
        "descripcion": _texto(dataset.get("descripcion"), proc.get("cohorte")),
        "n": {"muestras": filas if filas else None},
        "procesado": "fichero tabular subido; diccionario de columnas en el libro de procedencia",
        "acceso": acceso,
        "licencia": proc.get("licencia"),
        "fichero": proc.get("fichero"),
        "usadoEn": _usos(investigacion_id),
        "registro": lineas,
    }, ahora)
    return registrar(e, r)


# ---------------------------------------------------------------------------
# Texto para el prompt y la pantalla; coincidencias con una pregunta
# ---------------------------------------------------------------------------


def _linea(r: dict[str, Any]) -> str:
    partes = [f"{r['accession']} ({ETIQUETA_FUENTE.get(r['fuente'], r['fuente'])}; {ETIQUETA_TIPO.get(r['tipo'], r['tipo'])}; {ETIQUETA_ACCESO.get(r['acceso'], r['acceso'])})"]
    if r.get("titulo"):
        partes[0] += f": {r['titulo'][:110]}"
    detalles: list[str] = []
    if r.get("organismo"):
        detalles.append(r["organismo"])
    n = r.get("n") or {}
    if n.get("muestras") is not None:
        detalles.append(f"{n['muestras']} muestras")
    if n.get("donantes") is not None:
        detalles.append(f"{n['donantes']} donantes")
    if n.get("celulas") is not None:
        detalles.append(f"{n['celulas']} células")
    if r.get("tejido") or r.get("region"):
        detalles.append((r.get("tejido") or "región") + (f" ({r['region']})" if r.get("region") else ""))
    if r.get("estadio"):
        detalles.append(r["estadio"])
    if r.get("plataforma"):
        detalles.append(r["plataforma"])
    if detalles:
        partes.append("; ".join(detalles))
    if r.get("usadoEn"):
        partes.append("usado en " + ", ".join(r["usadoEn"][:4]) + (f" y {len(r['usadoEn']) - 4} más" if len(r["usadoEn"]) > 4 else ""))
    if r.get("muestrasCompartidasCon"):
        partes.append("comparte muestras con " + ", ".join(r["muestrasCompartidasCon"][:4]) + (f" y {len(r['muestrasCompartidasCon']) - 4} más" if len(r["muestrasCompartidasCon"]) > 4 else ""))
    return "- " + ". ".join(partes) + "."


def _filas_completas(e: dict[str, Any]) -> list[dict[str, Any]]:
    """Copias completadas de los registros: la lectura no modifica el estado."""
    return [_completar(dict(r)) for r in _lista(e, crear=False) if isinstance(r, dict)]


def texto_registro(e: dict[str, Any], investigacion_id: str | None = None, maximo: int = 12) -> str:
    """El registro en texto, para el prompt del planificador y para la
    pantalla. Con `investigacion_id`, los datasets usados en esa
    investigación van primero; después, los más recientes. Se corta en
    `maximo` líneas y dice cuántos quedan fuera. Sin datasets, lo dice. No
    modifica el estado."""
    filas = _filas_completas(e)
    if not filas:
        return "Ningún dataset registrado en el programa todavía."
    if investigacion_id:
        filas.sort(key=lambda r: (0 if investigacion_id in r["usadoEn"] else 1, -(r.get("actualizadoEn") or 0)))
    else:
        filas.sort(key=lambda r: -(r.get("actualizadoEn") or 0))
    maximo = max(1, _entero(maximo) or 1)
    n_controlados = sum(1 for r in filas if r["acceso"] == "controlado")
    cabecera = f"Datasets registrados en el programa: {len(filas)}"
    if investigacion_id:
        cabecera += " (los de esta investigación primero)"
    if n_controlados:
        cabecera += f"; {n_controlados} de acceso controlado que el proyecto no pide"
    lineas = [cabecera + "."] + [_linea(r) for r in filas[:maximo]]
    if len(filas) > maximo:
        lineas.append(f"... y {len(filas) - maximo} más.")
    return "\n".join(lineas)


def terminos_de(pregunta: str) -> dict[str, list[str]]:
    """Los términos de una pregunta que sirven para casar con el registro:
    tejido, región, estadio y tipo, por el mismo vocabulario que usa la
    inferencia. Una pregunta que dice 'expresión' y 'célula única' pide los
    dos tipos: la búsqueda no elige por ella."""
    t = _norm(pregunta)
    tejidos: list[str] = []
    regiones: list[str] = []
    for tejido, region, aliases in _TEJIDOS:
        if any(_hay(a, t) for a in aliases):
            if tejido not in tejidos:
                tejidos.append(tejido)
            if region and region not in regiones:
                regiones.append(region)
    estadios = [etq for etq, aliases in _ESTADIOS if any(_hay(a, t) for a in aliases)]
    tipos = [tipo for tipo, aliases in _TIPOS if any(_hay(a, t) for a in aliases)]
    if not tipos and any(_hay(a, t) for a in _EXPRESION_GENERICA):
        tipos = ["bulk"]
    # Una pregunta de expresión en tejido la responde también un dataset de
    # célula única (se puede agregar por donante); al revés no.
    if "bulk" in tipos and "celula_unica" not in tipos:
        tipos.append("celula_unica")
    return {"tejido": tejidos, "region": regiones, "estadio": estadios, "tipo": tipos}


def _terminos_de_registro(r: dict[str, Any]) -> dict[str, list[str]]:
    """Los mismos términos, sacados de los campos del registro (que pueden
    venir en castellano de la inferencia o en inglés si alguien los tecleó;
    tejido, región y estadio admiten varios valores separados por ';')."""
    base = terminos_de(_texto(r.get("titulo"), r.get("tejido"), r.get("region"), r.get("estadio")))
    for campo in ("tejido", "region", "estadio"):
        conocidos = [_norm(x) for x in base[campo]]
        for parte in _partes(r.get(campo)):
            if _norm(parte) not in conocidos:
                base[campo].append(parte)
                conocidos.append(_norm(parte))
    if r.get("tipo") in TIPOS and r["tipo"] != "otro" and r["tipo"] not in base["tipo"]:
        base["tipo"].append(r["tipo"])
    return base


def coincidencias(e: dict[str, Any], pregunta: str) -> list[dict[str, Any]]:
    """Qué datasets del registro hablan de lo que pregunta la corrida, por
    términos (tejido, región, estadio, tipo). Cada coincidencia lleva la
    lista de lo que casó y el motivo en una frase; las de más términos
    primero, y a igualdad, las de acceso abierto antes que las controladas
    (que llevan `aviso`) y después por accession, para que el orden sea el
    mismo en cada llamada. Nada de puntuación combinada: el número de
    términos es un recuento. No modifica el estado."""
    pedidos = terminos_de(pregunta)
    if not any(pedidos.values()):
        return []
    salida: list[dict[str, Any]] = []
    etiquetas = {"tejido": "tejido", "region": "región", "estadio": "estadio", "tipo": "tipo"}
    for r in _filas_completas(e):
        propios = _terminos_de_registro(r)
        casan: list[str] = []
        for campo in ("tejido", "region", "estadio", "tipo"):
            mios = {_norm(x) for x in propios[campo]}
            for pedido in pedidos[campo]:
                if _norm(pedido) in mios:
                    visible = ETIQUETA_TIPO.get(pedido, pedido) if campo == "tipo" else pedido
                    casan.append(f"{etiquetas[campo]}: {visible}")
        if not casan:
            continue
        item = {"id": r["id"], "accession": r["accession"], "fuente": r["fuente"], "tipo": r["tipo"], "acceso": r["acceso"], "titulo": r["titulo"], "coincide": casan, "motivo": "coincide en " + "; ".join(casan)}
        if r["acceso"] == "controlado":
            item["aviso"] = NOTA_CONTROLADO
        salida.append(item)
    salida.sort(key=lambda x: (-len(x["coincide"]), 1 if x["acceso"] == "controlado" else 0, x["accession"]))
    return salida


# ---------------------------------------------------------------------------
# Célula única: perfil de un h5ad y pseudobulk por donante
# ---------------------------------------------------------------------------


def _celulas(n: int) -> str:
    return f"{n} célula" if n == 1 else f"{n} células"


def _perfil_vacio(motivo: str) -> dict[str, Any]:
    return {"celulas": None, "donantes": None, "columnasObs": [], "tiposCelulares": [], "capas": [], "cuentasCrudas": None, "motivo": motivo}


def _columna(columnas: list[str], candidatas: tuple[str, ...]) -> str | None:
    por_norm = {_norm(c): c for c in columnas}
    for cand in candidatas:
        if _norm(cand) in por_norm:
            return por_norm[_norm(cand)]
    return None


def _a_denso(x: Any, filas: int | None = None) -> Any:
    """Las primeras `filas` de una matriz (densa, dispersa o backed) como
    ndarray. Devuelve None si no se puede."""
    import numpy as np

    try:
        from scipy import sparse
    except ImportError:  # pragma: no cover
        sparse = None
    try:
        parte = x[:filas] if filas is not None else x
        if hasattr(parte, "to_memory"):
            parte = parte.to_memory()
        if sparse is not None and sparse.issparse(parte):
            return np.asarray(parte.todense())
        if hasattr(parte, "toarray"):
            return np.asarray(parte.toarray())
        return np.asarray(parte)
    except Exception:  # noqa: BLE001
        return None


def parece_cuentas(x: Any, filas: int = 2000) -> tuple[bool | None, str]:
    """Si una matriz parece de cuentas crudas: enteros no negativos en una
    muestra de filas. (None, motivo) si no se pudo mirar. Es la comprobación
    de la skill de control de calidad de célula única, hecha función."""
    import numpy as np

    if x is None:
        return None, "sin matriz X"
    denso = _a_denso(x, filas)
    if denso is None or denso.size == 0:
        return None, "no pude leer valores de la matriz"
    try:
        v = denso.astype(float, copy=False)
    except (TypeError, ValueError):
        return False, "la matriz no es numérica: no son cuentas crudas"
    if np.isnan(v).any():
        return False, "la matriz tiene valores faltantes (NaN): no son cuentas crudas"
    if (v < 0).any():
        return False, "la matriz tiene valores negativos: está transformada (log o escalada), no son cuentas crudas"
    if not np.allclose(v, np.round(v)):
        return False, "la matriz tiene decimales: está normalizada, no son cuentas crudas"
    n_filas = denso.shape[0] if denso.ndim >= 1 else 1
    return True, f"enteros no negativos en las primeras {min(filas, n_filas)} células: parecen cuentas crudas"


def perfil_h5ad(ruta: str | Path | None) -> dict[str, Any]:
    """Describe un fichero h5ad sin cargarlo entero (modo backed): células,
    donantes (por la primera columna candidata de obs), columnas de obs,
    tipos celulares (primera columna candidata), capas (layers y raw.X) y si
    X parece de cuentas crudas. Si anndata no está instalado devuelve el
    motivo y nada más, sin romper."""
    try:
        import anndata
    except ImportError:
        return _perfil_vacio("anndata no está instalado en este entorno")
    if not ruta:
        return _perfil_vacio("sin ruta de fichero")
    try:
        p = Path(ruta)
    except TypeError:
        return _perfil_vacio(f"la ruta no es un fichero: {ruta!r}")
    if not p.exists():
        return _perfil_vacio(f"el fichero no existe: {p}")
    try:
        adata = anndata.read_h5ad(p, backed="r")
    except Exception as ex:  # noqa: BLE001
        return _perfil_vacio(f"no pude leer el h5ad: {type(ex).__name__}: {str(ex)[:200]}")
    motivos: list[str] = []
    try:
        obs = adata.obs
        columnas = [str(c) for c in obs.columns]
        col_don = _columna(columnas, CANDIDATAS_DONANTE)
        col_tipo = _columna(columnas, CANDIDATAS_TIPO)
        donantes = int(obs[col_don].nunique()) if col_don else None
        motivos.append(f"donantes por la columna '{col_don}'" if col_don else "sin columna de donante reconocible en obs: el pseudobulk necesita una (donor_id, individualID, subject...)")
        tipos = sorted(str(x) for x in obs[col_tipo].dropna().unique())[:80] if col_tipo else []
        motivos.append(f"tipos celulares por la columna '{col_tipo}'" if col_tipo else "sin columna de tipo celular reconocible en obs")
        capas = [str(k) for k in getattr(adata, "layers", {}).keys()]
        if getattr(adata, "raw", None) is not None:
            capas.append("raw.X")
        crudas, motivo_crudas = parece_cuentas(adata.X)
        motivos.append("X: " + motivo_crudas)
        if crudas is False and "raw.X" in capas:
            motivos.append("hay raw.X: probablemente ahí están las cuentas crudas; el pseudobulk debe usarla")
        return {"celulas": int(adata.n_obs), "donantes": donantes, "columnasObs": columnas, "tiposCelulares": tipos, "capas": capas, "cuentasCrudas": crudas, "motivo": "; ".join(motivos)}
    except Exception as ex:  # noqa: BLE001
        return _perfil_vacio(f"no pude perfilar el h5ad: {type(ex).__name__}: {str(ex)[:200]}")
    finally:
        try:
            if getattr(adata, "file", None) is not None:
                adata.file.close()
        except Exception:  # noqa: BLE001
            pass


def _matriz_para_pseudobulk(adata: Any, capa: str | None) -> tuple[Any, Any, str, bool | None, str]:
    """(matriz, nombres de genes, origen, parece cuentas, motivo). Con `capa`
    se usa esa layer; sin ella, X si parece de cuentas, si no raw.X si existe
    y parece de cuentas, y si no X con aviso."""
    capas = getattr(adata, "layers", None) or {}
    if capa:
        if capa == "raw.X":
            raw = getattr(adata, "raw", None)
            if raw is None:
                raise ValueError("se pidió la capa raw.X pero el AnnData no tiene raw")
            crudas, motivo = parece_cuentas(raw.X)
            return raw.X, list(raw.var_names), "raw.X", crudas, motivo
        if capa not in capas:
            raise ValueError(f"la capa '{capa}' no está en layers; capas: {list(capas.keys())}")
        crudas, motivo = parece_cuentas(capas[capa])
        return capas[capa], list(adata.var_names), f"layers['{capa}']", crudas, motivo
    crudas, motivo = parece_cuentas(adata.X)
    if crudas:
        return adata.X, list(adata.var_names), "X", crudas, motivo
    raw = getattr(adata, "raw", None)
    if raw is not None:
        crudas_raw, motivo_raw = parece_cuentas(raw.X)
        if crudas_raw:
            return raw.X, list(raw.var_names), "raw.X", crudas_raw, f"X no sirve ({motivo}); {motivo_raw}"
    return adata.X, list(adata.var_names), "X", crudas, motivo


def _pseudobulk_vacio(genes: list[str], origen: str, crudas: bool | None, aviso: str, registro: list[str]) -> Any:
    import numpy as np
    import pandas as pd

    df = pd.DataFrame(np.zeros((0, len(genes))), index=pd.MultiIndex.from_arrays([[], []], names=["donante", "tipoCelular"]), columns=genes)
    df.attrs.update({"capa": origen, "cuentasCrudas": crudas, "celulas": [], "excluidos": [], "aviso": aviso, "registro": registro})
    return df


def pseudobulk_por_donante(adata: Any, columna_donante: str, columna_tipo: str, capa: str | None = None, minimo_celulas: int = 10) -> Any:
    """Suma las cuentas de todas las células de cada (donante, tipo celular).
    Devuelve un DataFrame de pandas con índice (donante, tipoCelular) y una
    columna por gen; en `df.attrs` van 'capa' (de dónde salieron las
    cuentas), 'cuentasCrudas', 'celulas' (lista de {donante, tipoCelular,
    celulas} por grupo conservado), 'excluidos' (grupos con menos de
    `minimo_celulas`, con el motivo), 'aviso' si la matriz no parece de
    cuentas crudas o no se pudo comprobar, y 'registro'. Todo lo de `attrs`
    es serializable a JSON. Las células sin donante o sin tipo celular (NaN)
    se excluyen y se cuentan en el registro: no forman un donante llamado
    'nan'. La suma se hace con una matriz indicadora dispersa (grupos por
    células) multiplicada por la matriz de expresión, así que vale para
    millones de células sin densificar. Sirve para un AnnData o para
    cualquier objeto con `obs` (DataFrame), `X` y `var_names`."""
    import numpy as np
    import pandas as pd
    from scipy import sparse

    obs = getattr(adata, "obs", None)
    if obs is None or not hasattr(obs, "columns") or not hasattr(obs, "shape"):
        raise ValueError("el objeto no tiene una tabla obs (DataFrame de anotación por célula)")
    for c in (columna_donante, columna_tipo):
        if c not in obs.columns:
            raise ValueError(f"la columna '{c}' no está en obs; columnas disponibles: {list(map(str, obs.columns))[:30]}")
    matriz, genes, origen, crudas, motivo = _matriz_para_pseudobulk(adata, capa)
    n_celulas = int(obs.shape[0])
    forma = getattr(matriz, "shape", None)
    if forma is not None and len(forma) >= 1 and int(forma[0]) != n_celulas:
        raise ValueError(f"la matriz {origen} tiene {int(forma[0])} filas y obs tiene {n_celulas} células: no son el mismo conjunto de células")
    if n_celulas == 0:
        return _pseudobulk_vacio(genes, origen, crudas, "sin células", ["sin células: pseudobulk vacío"])
    don_serie = obs[columna_donante]
    tipo_serie = obs[columna_tipo]
    validas = (don_serie.notna() & tipo_serie.notna()).to_numpy()
    n_sin_grupo = int((~validas).sum())
    registro = [f"cuentas desde {origen}: {motivo}"]
    if n_sin_grupo:
        registro.append(f"{_celulas(n_sin_grupo)} sin donante o sin tipo celular en obs: excluidas del pseudobulk")
    if not validas.any():
        return _pseudobulk_vacio(genes, origen, crudas, "sin células con donante y tipo celular", registro + ["ninguna célula tiene donante y tipo celular a la vez: pseudobulk vacío"])
    donantes = don_serie.astype(str).to_numpy()[validas]
    tipos = tipo_serie.astype(str).to_numpy()[validas]
    posiciones = np.flatnonzero(validas)
    grupos = pd.MultiIndex.from_arrays([donantes, tipos], names=["donante", "tipoCelular"])
    codigos, unicos = grupos.factorize()
    unicos = unicos.set_names(["donante", "tipoCelular"])  # factorize pierde los nombres
    codigos = np.asarray(codigos)
    indicadora = sparse.csr_matrix((np.ones(len(posiciones)), (codigos, posiciones)), shape=(len(unicos), n_celulas))
    try:
        if hasattr(matriz, "to_memory"):
            matriz = matriz.to_memory()
        if not sparse.issparse(matriz):
            matriz = np.asarray(matriz)
        suma = indicadora @ matriz
        suma = np.asarray(suma.todense()) if sparse.issparse(suma) else np.asarray(suma)
    except Exception as ex:  # noqa: BLE001
        raise ValueError(f"no pude multiplicar la matriz {origen} por la indicadora de grupos: {type(ex).__name__}: {str(ex)[:160]}") from ex
    if crudas:
        suma = np.rint(suma).astype(np.int64)  # cuentas: enteros, como las exige pydeseq2
    df = pd.DataFrame(suma, index=unicos, columns=genes)
    por_grupo = pd.Series(np.bincount(codigos, minlength=len(unicos)), index=unicos)
    minimo = max(0, _entero(minimo_celulas) or 0)
    excluidos = [{"donante": d, "tipoCelular": t, "celulas": int(n), "motivo": f"{_celulas(int(n))}, menos del mínimo de {minimo}: la suma sería ruido de pocas células"} for (d, t), n in por_grupo.items() if n < minimo]
    conserva = por_grupo >= minimo
    df = df.loc[conserva.to_numpy()]
    registro.append(f"{_celulas(len(posiciones))} de {len(set(donantes))} donantes en {len(unicos)} grupos (donante y tipo celular); {len(excluidos)} grupos excluidos por tener menos de {_celulas(minimo)}")
    if crudas:
        aviso = ""
    elif crudas is None:
        aviso = "no pude comprobar si la matriz son cuentas crudas: revisar antes de usar el pseudobulk en pydeseq2"
    else:
        aviso = "la matriz no parece de cuentas crudas: el pseudobulk suma valores normalizados, que no sirven para pydeseq2 ni para modelos de cuentas"
    celulas_por_grupo = [{"donante": d, "tipoCelular": t, "celulas": int(n)} for (d, t), n in por_grupo[conserva].items()]
    df.attrs.update({"capa": origen, "cuentasCrudas": crudas, "celulas": celulas_por_grupo, "excluidos": excluidos, "aviso": aviso, "registro": registro})
    return df
