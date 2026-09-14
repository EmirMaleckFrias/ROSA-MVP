"""El verificador: los contratos de TRASPASO.md 4.1, tal cual.

Orden de comprobacion para cada afirmacion:

1. Deterministas, sin modelo:
   - `sin_cita`: no hay cita.
   - `cita_no_resuelve`: la cita no apunta a una fuente conocida, o el
     fragmento citado no aparece en la fuente (o en la pagina indicada).
   - `no_sostenida` por identificador: un NCT, DOI, rs o PMID de la
     afirmacion no esta en el fragmento.
   - `ausencia_refutada`: la afirmacion declara ausente un identificador que
     si aparece en algun fragmento del alcance.
   - Cifras: se normalizan y van al juez como pista, no como veredicto.
2. Juez (Opus 5) para lo que queda: `sostenida`, `parcial`, `no_sostenida`
   (con `entidad_distinta` como marca).
3. `sin_verificar` cuando el juez no dictamino. Nunca se aprueba por omision.

Bloquean: no_sostenida, cita_no_resuelve, sin_cita, ausencia_refutada.
Fidelidad = sostenidas / juzgadas por el juez; None si no se juzgo nada.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

BLOQUEAN = {"no_sostenida", "cita_no_resuelve", "sin_cita", "ausencia_refutada"}

PATRON_CITA = re.compile(r"\[(.+?),\s*(p[aá]g\.\s*\d+(?:-\d+)?|resumen|secci[oó]n\s+[^\]]+)\]\s*\.?\s*$", re.IGNORECASE)

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


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


def normalizar_cifra(c: str) -> str:
    """'1.234,5' y '1,234.5' quedan iguales; '12,5' y '12.5' tambien."""
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


# Sufijos de la nomenclatura internacional de farmacos (INN): un token que
# termina asi es un identificador aunque vaya en minusculas.
SUFIJOS_INN = ("mab", "nib", "statin", "pril", "sartan", "olol", "azole", "cillin", "mycin", "vir", "tide", "parin", "gliptin", "flozin", "prazole", "dipine", "afil", "setron", "triptan", "cept", "ciclib", "rafenib", "lisib", "tinib", "zomib", "gene", "lutide")


# Terminos del dominio que aparecen en casi todo el corpus: que una abstencion
# los mencione no la refuta. Se amplian con las palabras del objetivo de la
# investigacion (ver `terminos_del_dominio`).
TERMINOS_DOMINIO_BASE = {"alzheimer", "parkinson", "demencia", "dementia", "ad", "mci", "dcl", "apoe", "amiloide", "amyloid", "tau", "cerebro", "brain", "paciente", "pacientes", "patients", "cohorte", "cohort", "estudio", "study", "ensayo", "trial", "biomarcador", "biomarker", "plasma", "sangre", "lcr", "csf", "rosa"}


def terminos_del_dominio(objetivo: str = "", extra: set[str] | None = None) -> set[str]:
    """Las palabras del objetivo de la investigación (y las de base) que no
    cuentan como identificadores en una declaración de ausencia."""
    palabras = {t.lower() for t in re.findall(r"[A-Za-z][\w\-]{2,}", objetivo or "")}
    return TERMINOS_DOMINIO_BASE | palabras | (extra or set())


def expresiones_identificadoras(texto: str, excluir: set[str] | None = None) -> set[str]:
    """Identificadores de verdad para la comprobación de ausencia refutada:
    siglas (GFAP, ADNI), códigos y tokens con digitos (NCT0123, p-tau217,
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


def pasaje_en_texto(pasaje: str, texto: str) -> bool:
    """El pasaje citado tiene que estar entero en la fuente, no solo sus diez
    primeras palabras (así no pasa un comienzo real con una continuación
    inventada). Se normalizan espacios, guiones y comillas, y se tolera un
    fallo local: de las ventanas de 10 palabras con paso 5, puede faltar una
    (una errata del extractor no tumba una cita real)."""
    p = normalizar(pasaje).replace("-", " ").split()
    t = " " + " ".join(normalizar(texto).replace("-", " ").split()) + " "
    if not p:
        return True
    if len(p) <= 10:
        return f" {' '.join(p)} " in t
    ventanas = [p[i:i + 10] for i in range(0, len(p) - 10 + 1, 5)]
    if ventanas[-1] != p[-10:]:
        ventanas.append(p[-10:])
    faltan = sum(1 for v in ventanas if f" {' '.join(v)} " not in t)
    return faltan <= 1


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


def _clave_localizador(loc: str) -> str:
    return normalizar(loc).replace("pag.", "pag").replace("pág.", "pag").replace(" ", "")


def resolver_cita(cita: str, fragmentos: list[Fragmento]) -> Fragmento | None:
    m = PATRON_CITA.match(cita.strip())
    if not m:
        return None
    ref, loc = normalizar(m.group(1)), _clave_localizador(m.group(2))
    for f in fragmentos:
        if normalizar(f.referencia) == ref and _clave_localizador(f.localizador) == loc:
            return f
    return None


def comprobar_determinista(texto: str, cita: str, fragmento_citado: str | None, fragmentos: list[Fragmento], alcance: list[Fragmento], excluir: set[str] | None = None) -> Resultado:
    """Las comprobaciones sin modelo. Si devuelve `necesita_juez`, la
    afirmacion va al juez con las pistas."""
    if not cita or not cita.strip():
        if es_ausencia_pura(texto):
            return _ausencia(texto, alcance, excluir)
        return Resultado("sin_cita", "La afirmación no lleva cita.")
    frag = resolver_cita(cita, fragmentos)
    if frag is None:
        return Resultado("cita_no_resuelve", f"La cita {cita} no apunta a ninguna fuente ni localizador conocidos.")
    if fragmento_citado and not pasaje_en_texto(fragmento_citado, frag.texto):
        return Resultado("cita_no_resuelve", "El fragmento citado no aparece entero en la fuente en ese localizador (se comprueba el pasaje completo, no solo su comienzo).", fragmento=frag)

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
    return Resultado("sin_verificar", "Pendiente del juez.", pistas="; ".join(pistas) or "Sin cifras ni identificadores.", necesita_juez=True, fragmento=frag)


def _ausencia(texto: str, alcance: list[Fragmento], excluir: set[str] | None = None) -> Resultado:
    """Una declaración de ausencia: se refuta si el identificador ausente si
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
