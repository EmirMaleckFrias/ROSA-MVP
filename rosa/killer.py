"""El Hypothesis Killer (ROSA2018, etapa 4): la parte sin modelo.

El Killer es una lista de comprobaciones fija. Unas las resuelve Rosa aqui,
de forma determinista, con lo que ya tiene (veredictos del verificador,
cohortes de las fuentes, la comprobacion de novedad con recuperacion); las
otras las hace el juez (Opus 5, de otra familia que el generador) con la
firma `MatarHipotesis`. La decision no la da ningun modelo: se deriva de los
resultados con `decidir`, siguiendo la regla que salio de la investigacion
del 11 de septiembre de 2026:

- descartar en este contexto solo si falla la evidencia misma: citas que no
  resuelven, afirmaciones no sostenidas, o un supuesto del que depende la
  hipotesis contradicho;
- reformular si falla algo arreglable: direccion causal, falsabilidad,
  factibilidad, redundancia;
- suspender (no evaluable) si una comprobacion critica quedo sin poder
  comprobarse porque una fuente no respondio o falta el dato;
- avanzar solo si nada critico falla y hay prediccion falsable.

Separar deteccion de decision evita el fallo documentado en revisores LLM
que senalan el problema y aun asi aprueban.
"""

from __future__ import annotations

import re
from typing import Any

from rosa import politicas
from rosa.priorizacion import cohortes_de

BLOQUEANTES = ("no_sostenida", "cita_no_resuelve", "sin_cita", "ausencia_refutada")

# Que comprobaciones llevan a que decision cuando fallan.
DESCARTAN = ("citas_reales", "fidelidad_evidencia", "supuestos")
REFORMULAN = ("direccion_causal", "falsabilidad", "factibilidad", "redundancia")
# Las que, sin poder comprobarse, suspenden.
CRITICAS = ("citas_reales", "fidelidad_evidencia", "supuestos", "falsabilidad", "novedad")

# Cohortes del Alzheimer que Rosa reconoce en titulos y resumenes cuando el
# extractor no la dijo. Comparar por nombre es la regla de Cochrane 7.2.2
# (misma cohorte = mismo estudio); aqui solo se normaliza el nombre.
COHORTES_CONOCIDAS = [
    "ADNI", "BioFINDER", "A4", "AIBL", "ROSMAP", "MSBB", "Mayo", "NACC", "UK Biobank", "SEA-AD", "WRAP", "DIAN", "Knight ADRC", "BIOCARD", "ALFA", "Amsterdam Dementia Cohort",
    "Gothenburg", "H70", "TRIAD", "MCSA", "Framingham", "Rotterdam", "PREVENT-AD", "HABS", "OASIS", "EPAD", "Sydney Memory", "Three-City", "Whitehall", "AMP-AD",
]


def cohorte_en_texto(texto: str) -> str:
    t = texto or ""
    m = re.search(r"\bNCT\d{8}\b", t)
    if m:
        return m.group(0)
    for c in COHORTES_CONOCIDAS:
        if re.search(r"(?<![A-Za-z])" + re.escape(c) + r"(?![A-Za-z])", t, re.I):
            return c
    return ""


def comprobaciones_deterministas(h: dict[str, Any], e: dict[str, Any]) -> list[dict[str, str]]:
    """Las comprobaciones que Rosa resuelve sin modelo."""
    afs = h.get("afirmaciones", [])
    c: list[dict[str, str]] = []
    # 1. Citas reales: ninguna afirmacion con cita que no resuelve o sin cita.
    rotas = [a for a in afs if a["veredicto"] in ("cita_no_resuelve", "sin_cita")]
    if not afs:
        c.append({"comprobacion": "citas_reales", "resultado": "falla", "detalle": "La hipotesis no cita ninguna afirmacion"})
    elif rotas:
        c.append({"comprobacion": "citas_reales", "resultado": "falla", "detalle": f"{len(rotas)} afirmaciones con cita que no resuelve o sin cita: " + "; ".join(a["texto"][:80] for a in rotas[:3])})
    else:
        c.append({"comprobacion": "citas_reales", "resultado": "pasa", "detalle": "Todas las citas resuelven a una fuente y a un pasaje literal"})
    # 2. Fidelidad: sostenidas frente a no sostenidas y ausencias refutadas.
    no_sost = [a for a in afs if a["veredicto"] in ("no_sostenida", "ausencia_refutada")]
    sin_ver = [a for a in afs if a["veredicto"] == "sin_verificar"]
    sostenidas = [a for a in afs if a["veredicto"] in ("sostenida", "parcial")]
    if no_sost:
        c.append({"comprobacion": "fidelidad_evidencia", "resultado": "falla", "detalle": f"{len(no_sost)} afirmaciones que la fuente no sostiene" + (" (una es dato de otra entidad)" if any(a.get("entidadDistinta") for a in no_sost) else "") + ": " + "; ".join(a["texto"][:80] for a in no_sost[:3])})
    elif afs and sin_ver and not sostenidas:
        c.append({"comprobacion": "fidelidad_evidencia", "resultado": "no_comprobable", "detalle": f"{len(sin_ver)} afirmaciones sin verificar todavia (el juez no dictamino)"})
    elif sostenidas:
        parciales = sum(1 for a in sostenidas if a["veredicto"] == "parcial")
        c.append({"comprobacion": "fidelidad_evidencia", "resultado": "pasa", "detalle": f"Las afirmaciones estan sostenidas por su fuente" + (f"; {parciales} solo parcialmente" if parciales else "")})
    else:
        c.append({"comprobacion": "fidelidad_evidencia", "resultado": "no_comprobable", "detalle": "Sin afirmaciones verificadas"})
    # 4. Independencia de cohortes.
    cohortes = cohortes_de(h)
    fuentes = h.get("procedencia", {}).get("fuentes", [])
    primarias = [f for f in fuentes if f.get("tipoEstudio") not in ("revision_narrativa", "revision_sistematica", "otro")]
    if len(fuentes) <= 1:
        c.append({"comprobacion": "independencia_cohortes", "resultado": "falla" if fuentes else "no_aplica", "detalle": "Una sola fuente: no hay replicacion independiente" if fuentes else "Sin fuentes"})
    elif len(cohortes) >= 2:
        c.append({"comprobacion": "independencia_cohortes", "resultado": "pasa", "detalle": f"{len(cohortes)} cohortes distintas: " + ", ".join(cohortes)})
    elif len(cohortes) == 1:
        c.append({"comprobacion": "independencia_cohortes", "resultado": "falla", "detalle": f"Todas las fuentes con cohorte identificada salen de la misma ({cohortes[0]}): varias publicaciones no son varias evidencias"})
    else:
        c.append({"comprobacion": "independencia_cohortes", "resultado": "no_comprobable", "detalle": f"{len(fuentes)} fuentes sin cohorte identificada; {len(primarias)} parecen primarias"})
    # 8. Novedad con recuperacion.
    n = h.get("novedad", {})
    prec = n.get("precedente", {})
    if str(prec.get("detalle", "")).startswith("No comprobado"):
        c.append({"comprobacion": "novedad", "resultado": "no_comprobable", "detalle": prec.get("detalle", "")[:160]})
    elif prec.get("estado") == "ya_publicado":
        c.append({"comprobacion": "novedad", "resultado": "falla", "detalle": prec.get("detalle", "")[:160]})
    elif prec.get("estado") == "parcial":
        c.append({"comprobacion": "novedad", "resultado": "pasa", "detalle": "Precedente parcial: " + prec.get("detalle", "")[:140]})
    else:
        c.append({"comprobacion": "novedad", "resultado": "pasa", "detalle": prec.get("detalle", "Sin precedente claro")[:160]})
    # Factibilidad parcial: si ClinicalTrials no respondio, no comprobable (el juez completa).
    ens = n.get("ensayos", {})
    if str(ens.get("detalle", "")).startswith("No comprobado"):
        c.append({"comprobacion": "factibilidad", "resultado": "no_comprobable", "detalle": "ClinicalTrials.gov no respondio: no se pudo ver si existe un ensayo o cohorte que la mida"})
    return c


def fusionar(deterministas: list[dict[str, str]], del_juez: list[dict[str, str]]) -> list[dict[str, str]]:
    """Las deterministas mandan; el juez solo aporta las que Rosa no resolvio."""
    hechas = {c["comprobacion"] for c in deterministas if c["resultado"] != "no_comprobable"}
    salida = list(deterministas)
    for c in del_juez:
        nombre = c.get("comprobacion")
        if nombre in hechas:
            continue
        # Si Rosa dejo una no_comprobable y el juez la resolvio, se sustituye.
        salida = [x for x in salida if x["comprobacion"] != nombre]
        salida.append({"comprobacion": nombre, "resultado": c.get("resultado", "no_comprobable"), "detalle": str(c.get("detalle", ""))[:400]})
    return salida


def decidir(comprobaciones: list[dict[str, str]], tiene_prediccion: bool, version: int) -> tuple[str, str]:
    """(decision, motivo). Regla fija; ningun modelo la escribe."""
    por_nombre = {c["comprobacion"]: c for c in comprobaciones}
    fallan = [c for c in comprobaciones if c["resultado"] == "falla"]
    fallan_descarte = [c for c in fallan if c["comprobacion"] in DESCARTAN]
    if fallan_descarte:
        return "descartar_en_contexto", "La evidencia no sostiene la hipotesis: " + "; ".join(f"{c['comprobacion']}: {c['detalle'][:120]}" for c in fallan_descarte)
    no_comp = [c for c in comprobaciones if c["resultado"] == "no_comprobable" and c["comprobacion"] in CRITICAS]
    fallan_reform = [c for c in fallan if c["comprobacion"] in REFORMULAN]
    if not tiene_prediccion and "falsabilidad" not in {c["comprobacion"] for c in fallan_reform}:
        fallan_reform.append({"comprobacion": "falsabilidad", "resultado": "falla", "detalle": "La tarjeta no tiene prediccion falsable"})
    if fallan_reform:
        if not politicas.puede_reformular(version):
            return "descartar_en_contexto", f"Agoto las {politicas.MAX_REFORMULACIONES} reformulaciones de la politica y sigue fallando: " + "; ".join(f"{c['comprobacion']}: {c['detalle'][:100]}" for c in fallan_reform)
        return "reformular", "Arreglable reescribiendo: " + "; ".join(f"{c['comprobacion']}: {c['detalle'][:120]}" for c in fallan_reform)
    if no_comp:
        return "suspender", "No evaluable todavia: " + "; ".join(f"{c['comprobacion']}: {c['detalle'][:120]}" for c in no_comp)
    otras = [c for c in fallan if c["comprobacion"] not in DESCARTAN + REFORMULAN]
    nota = ("Avanza con avisos: " + "; ".join(f"{c['comprobacion']}: {c['detalle'][:100]}" for c in otras)) if otras else "Pasa todas las comprobaciones criticas y tiene prediccion falsable"
    if por_nombre.get("independencia_cohortes", {}).get("resultado") == "falla":
        nota += ". Una sola cohorte: la certeza queda limitada hasta que haya replicacion independiente"
    return "avanzar", nota


def texto_tarjeta(h: dict[str, Any]) -> str:
    t = h.get("tarjeta") or {}
    if not t:
        return "Tarjeta: sin rellenar"
    return (
        f"Tarjeta: diana o proceso {t.get('diana') or 'sin especificar'}; celula o tejido {t.get('celula') or 'sin especificar'}; etapa {t.get('etapa') or 'sin especificar'}; "
        f"intervencion {t.get('intervencion') or 'ninguna'} ({t.get('direccion', 'sin_intervencion')}); prediccion falsable: {t.get('prediccionFalsable') or 'NINGUNA'}; "
        f"riesgos: {'; '.join(t.get('riesgos', [])) or 'ninguno declarado'}; paso de la ruta terapeutica: {t.get('pasoRuta', 'mecanismo')}"
    )


def muestrear_para_auditoria(indice: int) -> bool:
    """Que descartes se auditan: uno de cada k segun la fraccion de la
    politica, determinista por el orden en que llegan (auditable, sin azar)."""
    k = max(1, round(1 / politicas.FRACCION_DESCARTES_AUDITADOS))
    return indice % k == 0


def sospechoso_inyeccion(texto: str) -> bool:
    """Patrones de instruccion dirigida al modelo dentro de un fragmento. No
    bloquea (falsos positivos en texto tecnico); marca para ensenarlo."""
    t = (texto or "").lower()
    patrones = [r"ignore (all |the )?(previous|above|prior) instructions", r"\bsystem prompt\b", r"\bas an ai\b", r"you must (now )?(respond|answer|output)", r"\bassistant:\s", r"disregard (all|the) (previous|above)", r"\bprompt injection\b", r"</?\s*(system|assistant|instruction)s?\s*>"]
    return any(re.search(p, t) for p in patrones)


MARCA_INICIO = "<<<DATO_RECUPERADO>>>"
MARCA_FIN = "<<<FIN_DATO_RECUPERADO>>>"


def como_dato(texto: str) -> str:
    """Delimita un texto recuperado para que el modelo lo trate como dato
    (spotlighting por delimitadores). Se quitan marcas falsas dentro."""
    limpio = (texto or "").replace(MARCA_INICIO, "").replace(MARCA_FIN, "")
    return f"{MARCA_INICIO}\n{limpio}\n{MARCA_FIN}"
