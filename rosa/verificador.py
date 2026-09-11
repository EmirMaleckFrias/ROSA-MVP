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
    """Casa con una formula de abstencion y no afirma nada de su cosecha."""
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


def expresiones_identificadoras(texto: str) -> set[str]:
    """Siglas en mayusculas, nombres propios, tokens con digitos (no numeros
    pequenos sueltos ni anios) y nombres de farmaco por sufijo INN, para la
    comprobacion de ausencia refutada."""
    salida = set()
    for tok in re.findall(r"[A-Za-z0-9][\w\-/]{1,}", texto):
        if re.fullmatch(r"[A-Z][A-Z0-9\-]{1,}", tok) and len(tok) >= 2:
            salida.add(tok)
        elif len(tok) >= 6 and tok.lower().endswith(SUFIJOS_INN):
            salida.add(tok)
        elif re.search(r"\d", tok) and not re.fullmatch(r"\d{1,3}", tok) and not re.fullmatch(r"(19|20)\d{2}", tok):
            salida.add(tok)
        elif re.fullmatch(r"[A-Z][a-z]{3,}", tok) and tok.lower() not in {"esta", "este", "esto", "para", "pero", "como", "cuando", "donde", "porque", "sobre", "entre", "hasta", "desde", "tras"}:
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


def comprobar_determinista(texto: str, cita: str, fragmento_citado: str | None, fragmentos: list[Fragmento], alcance: list[Fragmento]) -> Resultado:
    """Las comprobaciones sin modelo. Si devuelve `necesita_juez`, la
    afirmacion va al juez con las pistas."""
    if not cita or not cita.strip():
        if es_ausencia_pura(texto):
            return _ausencia(texto, alcance)
        return Resultado("sin_cita", "La afirmacion no lleva cita.")
    frag = resolver_cita(cita, fragmentos)
    if frag is None:
        return Resultado("cita_no_resuelve", f"La cita {cita} no apunta a ninguna fuente ni localizador conocidos.")
    if fragmento_citado and normalizar(" ".join(fragmento_citado.split()[:10])) not in normalizar(frag.texto):
        return Resultado("cita_no_resuelve", "El fragmento citado no aparece en la fuente en ese localizador.", fragmento=frag)

    ids_afirmacion = identificadores_de(texto)
    ids_fragmento = identificadores_de(frag.texto + " " + frag.encabezado)
    faltan = {i for i in ids_afirmacion if not any(i in j or j in i for j in ids_fragmento)}
    if faltan:
        return Resultado("no_sostenida", f"Identificadores que no aparecen en el fragmento citado: {', '.join(sorted(faltan))}.", fragmento=frag)

    if es_ausencia_pura(texto):
        r = _ausencia(texto, alcance)
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
        pistas.append(f"Cifras de la afirmacion que NO aparecen en el fragmento: {', '.join(ausentes)}")
    if ids_afirmacion:
        pistas.append(f"Identificadores comprobados: {', '.join(sorted(ids_afirmacion))}")
    return Resultado("sin_verificar", "Pendiente del juez.", pistas="; ".join(pistas) or "Sin cifras ni identificadores.", necesita_juez=True, fragmento=frag)


def _ausencia(texto: str, alcance: list[Fragmento]) -> Resultado:
    """Una declaracion de ausencia: se refuta si el identificador ausente si
    esta en algun fragmento del alcance. 'No pude comprobar' no se refuta."""
    if FORMULA_NO_COMPROBADO.search(texto):
        return Resultado("sostenida", "Declaracion honesta de comprobacion no hecha; no se juzga contra las fuentes.")
    for expr in expresiones_identificadoras(texto):
        for f in alcance:
            if frase_contigua_en(expr, f.texto):
                return Resultado("ausencia_refutada", f"Declara ausente '{expr}', que aparece en {f.referencia} ({f.localizador}). La busqueda no llego.", fragmento=f)
    return Resultado("sostenida", "Declaracion de ausencia sin contradiccion en el alcance.")


def fidelidad(veredictos: list[str]) -> float | None:
    juzgadas = [v for v in veredictos if v in ("sostenida", "parcial", "no_sostenida")]
    if not juzgadas:
        return None
    return sum(1 for v in juzgadas if v == "sostenida") / len(juzgadas)


def bloquea(veredicto: str) -> bool:
    return veredicto in BLOQUEAN


def texto_abstencion(motivo: str) -> str:
    """Los tres textos de abstencion, y solo estos."""
    return {
        "sin_respaldo": "no encuentro respaldo suficiente",
        "reloj": "no pude comprobar la respuesta en el tiempo disponible",
        "juez": "la comprobacion no estuvo disponible",
    }[motivo]
