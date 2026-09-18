"""El verificador: los contratos de TRASPASO.md 4.1, tal cual.

Orden de comprobación para cada afirmación:

1. Deterministas, sin modelo:
   - `sin_cita`: no hay cita.
   - `cita_no_resuelve`: la cita no apunta a una fuente conocida, o el
     fragmento citado no aparece en la fuente (o en la página indicada).
   - `no_sostenida` por identificador: un NCT, DOI, rs o PMID de la
     afirmación no está en el fragmento.
   - `ausencia_refutada`: la afirmación declara ausente un identificador que
     sí aparece en algún fragmento del alcance.
   - Cifras: se normalizan y van al juez como pista, no como veredicto.
2. Juez (Opus 5) para lo que queda: `sostenida`, `parcial`, `no_sostenida`
   (con `entidad_distinta` como marca).
3. `sin_verificar` cuando el juez no dictaminó. Nunca se aprueba por omisión.

Bloquean: no_sostenida, cita_no_resuelve, sin_cita, ausencia_refutada.
Fidelidad = sostenidas / juzgadas por el juez; None si no se juzgó nada.

Resolución de la cita (17 de septiembre de 2026). La cita `[referencia,
localizador]` es texto para personas; el identificador es `fuenteId`, que la
afirmación ya trae. `resolver_cita` busca primero por (fuente_id,
localizador) y solo cae a la referencia cuando no hay id (afirmaciones
antiguas, réplicas). Los localizadores que produce la extracción
(`LOCALIZADORES_ADMITIDOS`) son la lista única: pasos.py la importa para no
extraer de un localizador que aquí no resolvería.

Literalidad (`pasaje_en_texto`). El texto de un PDF trae ligaduras, guiones
de fin de línea, comillas tipográficas y, en los preprints, números de línea
intercalados; el extractor copia la frase limpia. Los dos lados pasan por la
misma `normalizar_texto` antes de compararse, y el pasaje tiene que estar
entero: ni una cola ni una cabeza inventadas pasan.
"""

from __future__ import annotations

import functools
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

BLOQUEAN = {"no_sostenida", "cita_no_resuelve", "sin_cita", "ausencia_refutada"}

# Los localizadores que produce `_fragmentos_de` (pasos.py) y que la cita puede
# llevar. Lista única: si se añade un recurso de texto completo nuevo, su
# localizador se añade aquí y el patrón de citas lo admite solo.
LOCALIZADORES_ADMITIDOS = re.compile(r"(?:p[aá]g\.\s*\d+(?:\s*-\s*\d+)?|resumen|secci[oó]n\s+[^\]]+?|texto\s+web,\s*parte\s+\d+)", re.IGNORECASE)
LOCALIZADORES_EN_LLANO = "pág. N, pág. N-M, resumen, sección X y texto web, parte N"

# "[referencia, localizador]" al final de la afirmación. La referencia puede
# llevar comas ("Cohorte clínica, 2025") y el localizador también ("texto web,
# parte 3"): por eso no vale cortar por la última coma.
PATRON_CITA = re.compile(r"\[(.+?),\s*(" + LOCALIZADORES_ADMITIDOS.pattern + r")\s*\]\s*\.?\s*$", re.IGNORECASE)


def es_localizador_admitido(localizador: str) -> bool:
    """True si el verificador sabría resolver una cita con ese localizador."""
    return bool(localizador) and LOCALIZADORES_ADMITIDOS.fullmatch(localizador.strip()) is not None


FORMULAS_ABSTENCION = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"no (?:lo |la )?encuentro",
        r"no (?:aparece|figura|consta)",
        r"no hay (?:evidencia|informaci[oó]n|datos)",
        r"los documentos no (?:indican|mencionan|contienen|permiten)",
        r"no (?:pude|se pudo|fue posible) comprobar",
    ]
]
FORMULA_NO_COMPROBADO = re.compile(r"no (?:pude|se pudo|fue posible) comprobar", re.IGNORECASE)

# Identificadores: NCT, DOI, rs, PMID.
PATRON_IDENTIFICADORES = re.compile(r"\b(NCT\d{8}|10\.\d{4,9}/[^\s\]\),;]+|rs\d{3,}|PMID:?\s*\d{5,9})\b", re.IGNORECASE)
PATRON_CIFRA = re.compile(r"(?<![\w.])(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*(%|por ciento)?")
VERBOS_AFIRMACION = re.compile(r"\b(fue|fueron|hubo|alcanz[oó]|mostr[oó]|obtuvo|registr[oó]|redujo|aument[oó])\s+(?:un |una |el |la |de |del )?\d", re.IGNORECASE)
SEGUNDA_CLAUSULA = re.compile(r"\b(pero|aunque|sin embargo|no obstante|en cambio|mientras que)\b|;", re.IGNORECASE)


def normalizar(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


# Artefactos del texto que sale de un PDF (PyMuPDF) o de una página web.
_LINEA_SOLO_NUMERO = re.compile(r"(?m)^[ \t]*\d{1,4}[ \t]*$\n?")  # números de línea de preprints (medRxiv, bioRxiv)
_GUION_FIN_DE_LINEA = re.compile(r"(?<=\w)-[ \t]*\n[ \t]*(?=\w)")  # "imag-\ning" -> "imaging"
_MARCA_DE_CITA = re.compile(r"\s*[\(\[]\d{1,3}(?:\s*[,\-–]\s*\d{1,3})*[\)\]]")  # "(4, 5)", "[12]", "(6-17)"
_SUPERINDICES = re.compile(r"[\u00b9\u00b2\u00b3\u2070-\u2079]+")  # marcas de cita en superíndice
_INVISIBLES = re.compile(r"[\u00ad\u200b\u200c\u200d\u2060\ufeff]")  # guion suave y anchos cero
_ETIQUETA_HTML = re.compile(r"</?(?:sub|sup|i|b|em|strong|u|span|p|br|h[1-6])\b[^>]*>", re.IGNORECASE)  # <sub>181</sub> en los resúmenes de Europe PMC
_ELISION = re.compile(r"\[\s*(?:\.{3}|\u2026)\s*\]|\(\s*(?:\.{3}|\u2026)\s*\)|\.{3,}|\u2026")  # "...", "[...]", "(...)"
_COMILLAS = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u00b4": "'", "`": "'", "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u00ab": '"', "\u00bb": '"', "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-"})


def normalizar_texto(s: str, quitar_numeros_de_linea: bool = True) -> str:
    """La normalización compartida entre el fragmento que copia el extractor y
    el texto de la fuente (página de PDF, sección, texto web). Se aplica a los
    dos lados, siempre la misma, para que comparar sea comparar iguales:

    1. NFKC: ligaduras (ﬁ, ﬂ, ﬀ) a letras sueltas, espacios duros a espacio.
    2. Fuera los guiones suaves y los caracteres de ancho cero.
    3. Fuera las líneas que son solo un número de 1 a 4 cifras (numeración de
       líneas de los preprints, la causa de dos tercios de los bloqueos).
    4. Fuera las marcas de cita numéricas "(4, 5)", "[12]" y los superíndices.
    5. Fuera las etiquetas HTML de los resúmenes ("p-tau<sub>181</sub>").
    6. Guion de fin de línea unido: "pre-\nsymptomatic" -> "presymptomatic".
    7. Comillas, apóstrofos y guiones tipográficos a ASCII.
    8. Lo de `normalizar`: sin tildes, espacios colapsados, minúsculas.
    Devuelve texto legible (con espacios); `_compacto` lo aplana para comparar.

    `quitar_numeros_de_linea=False` conserva las líneas que son solo un
    número: una tabla de un PDF también pone cada cifra en su línea y el
    pasaje que las copia ("Placebo 42 Lecanemab 180") tiene que poder
    compararse contra el texto con sus cifras. `_cuerpos` prepara las dos
    variantes de la fuente y el pasaje vale si está en cualquiera de ellas."""
    if not s:
        return ""
    s = _SUPERINDICES.sub("", str(s))  # antes de NFKC, que los convertiría en cifras normales
    s = unicodedata.normalize("NFKC", s)
    s = _INVISIBLES.sub("", s)
    if quitar_numeros_de_linea:
        s = _LINEA_SOLO_NUMERO.sub("", s)
    s = _MARCA_DE_CITA.sub("", s)
    s = _ETIQUETA_HTML.sub("", s)
    s = _GUION_FIN_DE_LINEA.sub("", s)
    s = s.translate(_COMILLAS)
    return normalizar(s)


def _palabras(s: str) -> list[str]:
    return normalizar_texto(s).split()


# Marca de cita pegada a la palabra o al signo anterior, como la deja un PDF
# o una página web al perder el superíndice: "stages,2 making", "changes11 or",
# "(clearance)4 by", "efficacy.9,10 however", "amyloid-pet,18-20 tau-pet". Solo
# se quita en una variante del texto de la FUENTE (nunca del pasaje), así
# "p-tau181" no se confunde con "p-tau217": el pasaje conserva su cifra y
# solo casa con la variante que también la tiene. Un decimal ("1.10") y una
# cifra tras "=" o espacio no se tocan.
# Lo que sí se tolera, a sabiendas: un pasaje al que el extractor quitó una
# cifra pegada a una palabra de cuatro letras o más ("APOE carriers" por
# "APOE4 carriers") casa con esta variante. Es una omisión, no un invento, y
# la pista de cifras se lo enseña al juez.
# Tras una palabra, solo si la palabra tiene cuatro letras o más ("changes11",
# "samples32", "load5"): "tau217", "Aβ42", "IgG1" o "cog14" llevan cifra propia
# y no se tocan.
_MARCA_PEGADA = re.compile(r"(?<!\d[\.,;:])(?:(?<=[^\W\d_]{4})\d{1,3}|(?<=[\)\]\.,;:])\d{1,3})(?:\s*[,\-]\s*\d{1,3})*(?=[\s\.,;:\)\]]|$)")
# La misma marca solo tras un signo ("stages,2", "(clearance)4", "efficacy.9,10"),
# y, tras una palabra con cifra propia ("p-tau217,21", "Aβ42,7"), solo la cola
# de citas separada por comas: la cifra del identificador se queda.
_MARCA_TRAS_SIGNO = re.compile(r"(?<!\d[\.,;:])(?<=[\)\]\.,;:])\d{1,3}(?:\s*[,\-]\s*\d{1,3})*(?=[\s\.,;:\)\]]|$)")
_COLA_TRAS_IDENTIFICADOR = re.compile(r"([^\W\d_]\d{1,3})(?:\s*,\s*\d{1,3})+(?=[\s\.,;:\)\]]|$)")


@functools.lru_cache(maxsize=512)
def _cuerpos(texto: str) -> tuple[str, ...]:
    """El texto de la fuente compacto, en sus variantes: sin las líneas que son
    solo un número (preprints con numeración de líneas), con ellas (tablas con
    una cifra por línea) y sin las marcas de cita pegadas a las palabras. Las
    variantes iguales se funden. Con caché: la misma página se compara contra
    decenas de afirmaciones."""
    legible = normalizar_texto(texto)
    sin = _compacto(legible.split())
    con = _compacto(normalizar_texto(texto, quitar_numeros_de_linea=False).split())
    sin_marcas = _compacto(_MARCA_PEGADA.sub("", legible).split())
    sin_marcas_conservando_identificadores = _compacto(_COLA_TRAS_IDENTIFICADOR.sub(r"\1", _MARCA_TRAS_SIGNO.sub("", legible)).split())
    salida = [sin]
    for v in (con, sin_marcas, sin_marcas_conservando_identificadores):
        if v not in salida:
            salida.append(v)
    return tuple(salida)


def _agujas(palabras: list[str]) -> tuple[str, ...]:
    """El tramo compacto y, si su primera palabra tiene dos letras o más, el
    mismo tramo sin la primera letra: el texto web y algunos PDF pierden la
    letra capital del primer párrafo ("onanemab is an immunoglobulin", "o
    single trial has") y el extractor la repone. Solo la primera letra del
    primer tramo; el resto del pasaje tiene que estar entero igual."""
    entera = _compacto(palabras)
    if palabras and len(palabras[0]) >= 2 and palabras[0][0].isalpha():
        return (entera, _compacto([palabras[0][1:]] + palabras[1:]))
    return (entera,)


def _esta(aguja: str, cuerpos: tuple[str, ...]) -> bool:
    return any(aguja in c for c in cuerpos)


def _alguna(agujas: tuple[str, ...], cuerpos: tuple[str, ...]) -> bool:
    return any(_esta(a, cuerpos) for a in agujas)


def _compacto(palabras: list[str]) -> str:
    """Las palabras pegadas sin puntuación ni guiones: así "follow-up",
    "follow up" y "follow-\nup" quedan iguales y un punto final o una coma no
    tumban una cita real."""
    return re.sub(r"[\W_]+", "", "".join(palabras))


VENTANA = 10
PASO = 5


def _ventanas(p: list[str]) -> list[list[str]]:
    ventanas = [p[i:i + VENTANA] for i in range(0, len(p) - VENTANA + 1, PASO)]
    if ventanas[-1] != p[-VENTANA:]:
        ventanas.append(p[-VENTANA:])
    return ventanas


def pasaje_en_texto(pasaje: str, texto: str) -> bool:
    """El pasaje citado tiene que estar entero en la fuente. Los dos lados
    pasan por `normalizar_texto` y se comparan compactos (sin espacios ni
    puntuación). Con 10 palabras o menos, el pasaje entero tiene que estar.
    Con más, se mira por ventanas de 10 palabras con paso 5: la primera y la
    última ventana tienen que estar siempre (así no pasa un comienzo real con
    una cola inventada, ni una cabeza inventada con un final real), y solo en
    pasajes de más de 20 palabras (cuatro ventanas o más) se tolera que falte
    una ventana interior: una errata del extractor no tumba una cita larga,
    pero una palabra cambiada rompe dos ventanas y sí la tumba."""
    return pasaje_faltante(pasaje, texto) is None


def pasaje_faltante(pasaje: str, texto: str) -> str | None:
    """None si el pasaje está entero; si no, el tramo (normalizado) que no se
    encontró en la fuente, para decirlo en el motivo.

    Una elisión explícita ("...", "[...]") parte el pasaje en tramos: cada
    tramo tiene que estar entero y en el mismo orden que en la fuente. Es la
    convención normal de cita y no esconde nada; una palabra añadida entre
    corchetes, en cambio, no está en la fuente y sí tumba el pasaje."""
    tramos = [x for x in _ELISION.split(pasaje or "") if x and x.strip()]
    if len(tramos) > 1:
        # Un tramo que se queda vacío al normalizar (una marca de cita "(4)"
        # suelta junto a la elisión) no cuenta como tramo.
        tramos = [x for x in tramos if _palabras(x)] or tramos[:1]
    if len(tramos) > 1:
        cuerpos = _cuerpos(texto or "")
        desde = [0] * len(cuerpos)
        for tramo in tramos:
            falta = _tramo_faltante(tramo, texto)
            if falta is not None:
                return falta
            aguja, cabeza = _compacto(_palabras(tramo)), _compacto(_palabras(tramo)[:VENTANA])
            en_orden = False
            for i, c in enumerate(cuerpos):
                pos = c.find(aguja, desde[i])
                if pos < 0:
                    pos = c.find(cabeza, desde[i])
                if pos >= 0:
                    desde[i] = pos + 1
                    en_orden = True
            if not en_orden:
                return " ".join(_palabras(tramo)[:VENTANA]) + " (fuera de orden respecto al tramo anterior)"
        return None
    return _tramo_faltante(pasaje, texto)


def _tramo_faltante(pasaje: str, texto: str) -> str | None:
    if not pasaje or not str(pasaje).strip():
        return None  # sin pasaje no hay nada que comprobar; quien llama decide qué hacer con eso
    p = _palabras(pasaje)
    if not p:
        # El pasaje tenía algo pero se quedó en nada al normalizar ("42", "(4, 5)", "<sub></sub>"):
        # no es un pasaje que se pueda comprobar y no se da por literal.
        return str(pasaje).strip()[:80] + " (el pasaje no tiene texto comprobable)"
    cuerpos = _cuerpos(texto or "")
    if _alguna(_agujas(p), cuerpos):
        return None
    if len(p) <= VENTANA:
        return " ".join(p)
    ventanas = _ventanas(p)
    # La letra capital perdida solo puede faltar al principio: la primera ventana
    # admite las dos agujas, las demás solo la literal.
    faltan = [i for i, v in enumerate(ventanas) if not (_alguna(_agujas(v), cuerpos) if i == 0 else _esta(_compacto(v), cuerpos))]
    if not faltan:
        return None
    ultima = len(ventanas) - 1
    interiores = [i for i in faltan if i not in (0, ultima)]
    if 0 not in faltan and ultima not in faltan and len(ventanas) >= 4 and len(interiores) <= 1:
        return None
    return " ".join(ventanas[faltan[0]])


def normalizar_cifra(c: str) -> str:
    """'1.234,5' y '1,234.5' quedan iguales; '12,5' y '12.5' también."""
    c = c.strip()
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", c):
        return c.replace(".", "").replace(",", "")
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+[.,]\d+", c):
        entero, dec = re.split(r"[.,](?=\d+$)", c)
        return entero.replace(".", "").replace(",", "") + "." + dec
    return c.replace(",", ".")


def cifras_de(texto: str) -> set[str]:
    return {normalizar_cifra(m.group(1)) for m in PATRON_CIFRA.finditer(texto)}


def identificadores_de(texto: str) -> set[str]:
    return {re.sub(r"\s+", "", m.group(1).upper().replace("PMID:", "PMID")) for m in PATRON_IDENTIFICADORES.finditer(texto)}


def es_ausencia_pura(texto: str) -> bool:
    """Casa con una fórmula de abstención y no afirma nada de su cosecha."""
    if not any(p.search(texto) for p in FORMULAS_ABSTENCION):
        return False
    if SEGUNDA_CLAUSULA.search(texto):
        return False
    if VERBOS_AFIRMACION.search(texto):
        return False
    # Una cifra con forma de medida descalifica; un entero pegado a un nombre no.
    for m in PATRON_CIFRA.finditer(texto):
        bruto, pct = m.group(1), m.group(2)
        if pct or re.search(r"[.,]\d", bruto):
            return False
    return True


# Sufijos de la nomenclatura internacional de fármacos (INN): un token que
# termina así es un identificador aunque vaya en minúsculas.
SUFIJOS_INN = ("mab", "nib", "statin", "pril", "sartan", "olol", "azole", "cillin", "mycin", "vir", "tide", "parin", "gliptin", "flozin", "prazole", "dipine", "afil", "setron", "triptan", "cept", "ciclib", "rafenib", "lisib", "tinib", "zomib", "gene", "lutide")


# Términos del dominio que aparecen en casi todo el corpus: que una abstención
# los mencione no la refuta. Se amplían con las palabras del objetivo de la
# investigación (ver `terminos_del_dominio`).
TERMINOS_DOMINIO_BASE = {"alzheimer", "parkinson", "demencia", "dementia", "ad", "mci", "dcl", "apoe", "amiloide", "amyloid", "tau", "cerebro", "brain", "paciente", "pacientes", "patients", "cohorte", "cohort", "estudio", "study", "ensayo", "trial", "biomarcador", "biomarker", "plasma", "sangre", "lcr", "csf", "rosa"}


def terminos_del_dominio(objetivo: str = "", extra: set[str] | None = None) -> set[str]:
    """Las palabras del objetivo de la investigación (y las de base) que no
    cuentan como identificadores en una declaración de ausencia."""
    palabras = {t.lower() for t in re.findall(r"[A-Za-z][\w\-]{2,}", objetivo or "")}
    return TERMINOS_DOMINIO_BASE | palabras | (extra or set())


def expresiones_identificadoras(texto: str, excluir: set[str] | None = None) -> set[str]:
    """Identificadores de verdad para la comprobación de ausencia refutada:
    siglas (GFAP, ADNI), códigos y tokens con dígitos (NCT0123, p-tau217,
    GSE1297) y nombres de fármaco por sufijo INN (lecanemab). Una palabra
    capitalizada suelta ("Alzheimer", "Sin") no es un identificador: castigaba
    justo la abstención honesta que el diseño quiere premiar."""
    excluir = {x.lower() for x in (excluir or set())} | TERMINOS_DOMINIO_BASE
    salida = set()
    for tok in re.findall(r"[A-Za-z0-9][\w\-/]{1,}", texto):
        if tok.lower() in excluir:
            continue
        if re.fullmatch(r"[A-Z][A-Z0-9\-]{1,}", tok) and len(tok) >= 2:
            salida.add(tok)
        elif len(tok) >= 6 and tok.lower().endswith(SUFIJOS_INN):
            salida.add(tok)
        elif re.search(r"\d", tok) and not re.fullmatch(r"\d{1,3}", tok) and not re.fullmatch(r"(19|20)\d{2}", tok):
            salida.add(tok)
    return salida


def frase_contigua_en(expresion: str, texto: str) -> bool:
    patron = r"(?<![\w])" + re.escape(normalizar(expresion)) + r"(?![\w])"
    return re.search(patron, normalizar(texto)) is not None


@dataclass
class Fragmento:
    fuente_id: str
    referencia: str
    localizador: str
    texto: str
    encabezado: str = ""


@dataclass
class Resultado:
    veredicto: str
    motivo: str
    entidad_distinta: bool = False
    pistas: str = ""
    necesita_juez: bool = False
    fragmento: Fragmento | None = None


def _clave_localizador(loc: str | None) -> str:
    return normalizar(loc).replace("pag.", "pag").replace("pág.", "pag").replace(" ", "")


def _partes_cita(cita: str) -> tuple[str, str] | None:
    m = PATRON_CITA.match((cita or "").strip())
    if not m:
        return None
    return normalizar(m.group(1)), _clave_localizador(m.group(2))


def candidatos_cita(cita: str, fragmentos: list[Fragmento], fuente_id: str | None = None) -> list[Fragmento]:
    """Los fragmentos a los que puede apuntar la cita, en orden de preferencia.

    1. Con `fuente_id`: los fragmentos de esa fuente cuyo localizador es el de
       la cita. La referencia no se mira (dos fuentes homónimas ya no chocan).
       Si la cita no sigue el patrón pero termina con el localizador de un
       fragmento de la fuente, también vale.
    2. Sin id, o con un id que no está entre los fragmentos (afirmación
       antigua cuya fuente ya no está, réplica): por referencia y
       localizador, como siempre. Si varias fuentes comparten referencia y
       localizador, salen todas; `comprobar_determinista` elige la que contiene
       el pasaje.
    3. Con un id que SÍ está entre los fragmentos pero sin ese localizador:
       nada. No se cae a la referencia, porque caería en una fuente homónima
       distinta y la afirmación se juzgaría contra el texto equivocado; el
       motivo dirá que la fuente no tiene ese localizador.
    """
    partes = _partes_cita(cita)
    if fuente_id:
        propios = [f for f in fragmentos if f.fuente_id == fuente_id]
        if partes:
            por_loc = [f for f in propios if _clave_localizador(f.localizador) == partes[1]]
            if por_loc:
                return por_loc
        else:
            cuerpo = _clave_localizador((cita or "").strip().strip(".").strip().strip("[]"))
            por_cola = [f for f in propios if f.localizador and cuerpo.endswith(_clave_localizador(f.localizador))]
            if por_cola:
                return por_cola
        if propios:
            return []
    if not partes:
        return []
    ref, loc = partes
    return [f for f in fragmentos if normalizar(f.referencia) == ref and _clave_localizador(f.localizador) == loc]


def resolver_cita(cita: str, fragmentos: list[Fragmento], fuente_id: str | None = None) -> Fragmento | None:
    """El fragmento al que apunta la cita: por (fuente_id, localizador) cuando
    viene el id; si no, por referencia y localizador. None si no resuelve."""
    candidatos = candidatos_cita(cita, fragmentos, fuente_id)
    return candidatos[0] if candidatos else None


def motivo_cita_no_resuelta(cita: str, fragmentos: list[Fragmento], fuente_id: str | None = None) -> str:
    """Por qué no resolvió, para que la persona vea la causa real y no un
    "cita sin fuente" genérico: localizador no reconocido, fuente desconocida
    o fuente conocida sin ese localizador."""
    partes = _partes_cita(cita)
    if not partes:
        return f"La cita {cita} no lleva un localizador reconocido (se admiten {LOCALIZADORES_EN_LLANO})."
    ref, loc = partes
    # Con id, los localizadores que se listan son los de ESA fuente; los de
    # una homónima confundirían a la persona ("tiene sección Discussion" cuando
    # la que tiene Discussion es la otra).
    de_la_fuente = [f for f in fragmentos if fuente_id and f.fuente_id == fuente_id] or [f for f in fragmentos if normalizar(f.referencia) == ref]
    if not de_la_fuente:
        return f"La cita {cita} no apunta a ninguna fuente conocida de la corrida."
    localizadores = sorted({f.localizador or "(sin localizador)" for f in de_la_fuente})
    muestra = ", ".join(localizadores[:6]) + (" y otros" if len(localizadores) > 6 else "")
    return f"La fuente {de_la_fuente[0].referencia} no tiene el localizador de la cita {cita} (tiene: {muestra})."


def comprobar_determinista(texto: str, cita: str, fragmento_citado: str | None, fragmentos: list[Fragmento], alcance: list[Fragmento], excluir: set[str] | None = None, fuente_id: str | None = None) -> Resultado:
    """Las comprobaciones sin modelo. Si devuelve `necesita_juez`, la
    afirmación va al juez con las pistas. `fuente_id` es el de la afirmación
    (`fuenteId`): con él la cita resuelve a su fuente aunque otra se llame
    igual."""
    if not cita or not cita.strip():
        if es_ausencia_pura(texto):
            return _ausencia(texto, alcance, excluir)
        return Resultado("sin_cita", "La afirmación no lleva cita.")
    candidatos = candidatos_cita(cita, fragmentos, fuente_id or None)
    if not candidatos:
        return Resultado("cita_no_resuelve", motivo_cita_no_resuelta(cita, fragmentos, fuente_id or None))
    frag = candidatos[0]
    ambigua = len({c.fuente_id for c in candidatos}) > 1
    if fragmento_citado and fragmento_citado.strip():
        con_pasaje = [c for c in candidatos if pasaje_en_texto(fragmento_citado, c.texto)]
        if not con_pasaje:
            falta = pasaje_faltante(fragmento_citado, frag.texto) or ""
            donde = f"{frag.referencia} ({frag.localizador})"
            if ambigua:
                donde = f"ninguna de las {len(candidatos)} fuentes que se llaman {frag.referencia} ({frag.localizador})"
            return Resultado("cita_no_resuelve", f"El pasaje citado no aparece entero en {donde}: la fuente y el localizador existen, falla la literalidad del pasaje (tras normalizar tipografía y números de línea). Tramo que no se encontró: \"{falta[:160]}\".", fragmento=frag)
        frag = con_pasaje[0]

    ids_afirmacion = identificadores_de(texto)
    ids_fragmento = identificadores_de(frag.texto + " " + frag.encabezado)
    faltan = {i for i in ids_afirmacion if not any(i in j or j in i for j in ids_fragmento)}
    if faltan:
        return Resultado("no_sostenida", f"Identificadores que no aparecen en el fragmento citado: {', '.join(sorted(faltan))}.", fragmento=frag)

    if es_ausencia_pura(texto):
        r = _ausencia(texto, alcance, excluir)
        if r.veredicto == "ausencia_refutada":
            return r

    cif_af = cifras_de(texto)
    cif_fr = cifras_de(frag.texto)
    presentes = sorted(cif_af & cif_fr)
    ausentes = sorted(cif_af - cif_fr)
    pistas = []
    if presentes:
        pistas.append(f"Cifras presentes en el fragmento: {', '.join(presentes)}")
    if ausentes:
        pistas.append(f"Cifras de la afirmación que NO aparecen en el fragmento: {', '.join(ausentes)}")
    if ids_afirmacion:
        pistas.append(f"Identificadores comprobados: {', '.join(sorted(ids_afirmacion))}")
    if ambigua:
        pistas.append(f"Referencia ambigua: {len(candidatos)} fuentes de la corrida se llaman {frag.referencia}; la afirmación no trae fuenteId, se juzga contra la primera que contiene el pasaje")
    return Resultado("sin_verificar", "Pendiente del juez.", pistas="; ".join(pistas) or "Sin cifras ni identificadores.", necesita_juez=True, fragmento=frag)


def _ausencia(texto: str, alcance: list[Fragmento], excluir: set[str] | None = None) -> Resultado:
    """Una declaración de ausencia: se refuta si el identificador ausente sí
    está en algún fragmento del alcance. 'No pude comprobar' no se refuta, y
    los términos del dominio (la enfermedad, la cohorte del objetivo) no
    cuentan como identificadores."""
    if FORMULA_NO_COMPROBADO.search(texto):
        return Resultado("sostenida", "Declaración honesta de comprobación no hecha; no se juzga contra las fuentes.")
    for expr in expresiones_identificadoras(texto, excluir):
        for f in alcance:
            if frase_contigua_en(expr, f.texto):
                return Resultado("ausencia_refutada", f"Declara ausente '{expr}', que aparece en {f.referencia} ({f.localizador}). La búsqueda no llegó.", fragmento=f)
    return Resultado("sostenida", "Declaración de ausencia sin contradicción en el alcance.")


def fidelidad(veredictos: list[str]) -> float | None:
    juzgadas = [v for v in veredictos if v in ("sostenida", "parcial", "no_sostenida")]
    if not juzgadas:
        return None
    return sum(1 for v in juzgadas if v == "sostenida") / len(juzgadas)


def bloquea(veredicto: str) -> bool:
    return veredicto in BLOQUEAN


def texto_abstencion(motivo: str) -> str:
    """Los tres textos de abstención, y solo estos."""
    return {
        "sin_respaldo": "no encuentro respaldo suficiente",
        "reloj": "no pude comprobar la respuesta en el tiempo disponible",
        "juez": "la comprobación no estuvo disponible",
    }[motivo]
