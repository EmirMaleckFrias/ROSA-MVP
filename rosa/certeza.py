"""Techo de certeza por regla (GRADE) y la escalera para subir.

La certeza de la evidencia sobre una hipótesis la escribe el juez
(`ConcluirHipotesis`), con sus factores y su explicación. Pero el nivel queda
acotado por una regla determinista sobre lo que Rosa tiene contado, igual que
el Killer o el riesgo de sesgo: el juez explica dentro de la caja, no la fija.

La regla solo baja, nunca sube. Con lo que hay en el registro:

- Sin ninguna afirmación sostenida que no sea sintética: muy baja.
- Solo literatura de una cohorte (o sin cohorte identificada), sin réplica ni
  evidencia directa: muy baja. Si el juez documentó un efecto grande, baja.
- Solo literatura pero de dos o más cohortes distintas: como mucho baja.
- Evidencia directa (un resultado de laboratorio contra el prerregistro o un
  análisis in silico sobre datos reales, nunca sintéticos) de una cohorte:
  como mucho moderada.
- Evidencia directa y dos o más cohortes distintas: puede llegar a alta.

Una hipótesis nueva de Rosa arranca casi siempre en muy baja y no es un
fallo: es el punto de partida de toda hipótesis que nadie ha probado. La
escalera dice qué le falta para el siguiente nivel, por regla, para que la
persona vea el camino en vez de una etiqueta roja. 15 de septiembre de 2026.
"""

from __future__ import annotations

import re
from typing import Any

NIVELES = ("muy_baja", "baja", "moderada", "alta")
CLASES_DIRECTAS = ("observacion_original", "derivado")
_GENERICOS_COHORTE = {"cohorte", "cohort", "study", "estudio", "longitudinal", "portadores", "familias", "alzheimer", "disease", "enfermedad", "mutaciones", "carriers", "participantes", "pacientes", "et", "al", "the", "of", "de", "del", "la", "los", "las", "con", "and", "familial", "autosomal", "dominant", "autosómico", "dominante"}


def _tokens_cohorte(nombre: str) -> set[str]:
    limpio = re.sub(r"\(.*?\)", " ", (nombre or "").lower())
    return {t for t in re.findall(r"[a-záéíóúñ0-9][a-záéíóúñ0-9\-]{2,}", limpio) if t not in _GENERICOS_COHORTE}


def cohortes_distintas(h: dict[str, Any]) -> list[str]:
    """Las cohortes nombradas en las fuentes de la hipótesis, agrupando los
    nombres que se refieren a la misma ("ADAD", "ADAD (Belder et al.)" y
    "Belder et al., cohorte ADAD" son una). Dos artículos de la misma cohorte
    son una sola evidencia; una fuente sin cohorte identificada no cuenta como
    independiente, porque no se puede afirmar que lo sea."""
    grupos: list[tuple[str, set[str]]] = []
    for f in h.get("procedencia", {}).get("fuentes", []):
        nombre = (f.get("cohorte") or "").strip()
        if not nombre:
            continue
        toks = _tokens_cohorte(nombre) or {nombre.lower()}
        for i, (rep, tk) in enumerate(grupos):
            if toks & tk:
                grupos[i] = (rep, tk | toks)
                break
        else:
            grupos.append((nombre, set(toks)))
    return [rep for rep, _ in grupos]


def fuentes_sin_cohorte(h: dict[str, Any]) -> int:
    return sum(1 for f in h.get("procedencia", {}).get("fuentes", []) if not (f.get("cohorte") or "").strip())


def sostenidas_reales(h: dict[str, Any]) -> list[dict[str, Any]]:
    """Afirmaciones sostenidas o parciales que cuentan como evidencia: lo
    sintético (ensayo en seco) nunca cuenta."""
    return [a for a in h.get("afirmaciones", []) if a.get("veredicto") in ("sostenida", "parcial") and not a.get("sintetico")]


def evidencia_directa(h: dict[str, Any]) -> list[dict[str, Any]]:
    """Las afirmaciones que vienen de datos, no de literatura: un resultado de
    laboratorio evaluado contra el prerregistro o un análisis in silico sobre
    datos reales."""
    return [a for a in sostenidas_reales(h) if a.get("tipo") == "dato" and a.get("clase") in CLASES_DIRECTAS]


def efecto_grande_documentado(factores: list[Any]) -> bool:
    for f in factores or []:
        factor = f.get("factor") if isinstance(f, dict) else getattr(f, "factor", None)
        efecto = f.get("efecto") if isinstance(f, dict) else getattr(f, "efecto", None)
        if factor == "efecto_grande" and efecto == "sube":
            return True
    return False


def techo(h: dict[str, Any], factores: list[Any] | None = None) -> tuple[str, str]:
    """(nivel máximo, motivo) con lo que hay en el registro de la hipótesis."""
    sostenidas = sostenidas_reales(h)
    if not sostenidas:
        return "muy_baja", "no hay ninguna afirmación sostenida que no sea sintética"
    cohortes = cohortes_distintas(h)
    n = len(cohortes)
    directa = evidencia_directa(h)
    sin = fuentes_sin_cohorte(h)
    texto_cohortes = f"{n} cohortes distintas" if n >= 2 else ("una sola cohorte" if n == 1 else "ninguna cohorte identificada en las fuentes")
    if sin:
        texto_cohortes += f" ({sin} {'fuente' if sin == 1 else 'fuentes'} sin cohorte identificada, que no cuentan como independientes)"
    if directa:
        clases = sorted({a.get("clase") for a in directa})
        que = "resultado de laboratorio" if "observacion_original" in clases else "análisis sobre datos reales"
        if n >= 2:
            return "alta", f"hay evidencia directa ({que}) y {texto_cohortes}"
        return "moderada", f"hay evidencia directa ({que}) pero {texto_cohortes}: falta la réplica independiente"
    if n >= 2:
        return "baja", f"solo literatura, sin experimento ni análisis sobre datos reales, aunque de {texto_cohortes}"
    if efecto_grande_documentado(factores or []):
        return "baja", f"solo literatura de {texto_cohortes}, pero el juez documentó un efecto grande"
    return "muy_baja", f"solo literatura de {texto_cohortes}, sin réplica ni evidencia directa"


def acotar(certeza_del_juez: str, h: dict[str, Any], factores: list[Any] | None = None) -> dict[str, Any]:
    """La certeza final: la del juez si cabe bajo el techo; el techo si no.
    Devuelve {certeza, techo: {nivel, motivo, acotada, certezaDelJuez}}."""
    nivel, motivo = techo(h, factores)
    if certeza_del_juez not in NIVELES:
        certeza_del_juez = "muy_baja"
    final = certeza_del_juez if NIVELES.index(certeza_del_juez) <= NIVELES.index(nivel) else nivel
    return {"certeza": final, "techo": {"nivel": nivel, "motivo": motivo, "acotada": final != certeza_del_juez, "certezaDelJuez": certeza_del_juez}}


def escalera(h: dict[str, Any], certeza: str, factores: list[Any] | None = None) -> list[dict[str, str]]:
    """Qué le falta a la hipótesis para cada nivel por encima del actual, por
    regla. Cada peldaño: {de, a, falta}. Vacía si ya está en alta."""
    cohortes = len(cohortes_distintas(h))
    directa = bool(evidencia_directa(h))
    actual = NIVELES.index(certeza) if certeza in NIVELES else 0
    pasos: list[dict[str, str]] = []
    if actual < 1:
        if cohortes < 2:
            falta = "una segunda cohorte independiente que muestre lo mismo (en la literatura o por análisis), o un efecto grande documentado en la evidencia que ya hay"
            if fuentes_sin_cohorte(h):
                falta += f"; {fuentes_sin_cohorte(h)} de sus fuentes no tienen la cohorte identificada: nombrarla (qué estudio o población) puede bastar"
        else:
            falta = "que el juez deje de ver riesgo de sesgo, inconsistencia o imprecisión graves en las cohortes que ya hay"
        pasos.append({"de": "muy_baja", "a": "baja", "falta": falta})
    if actual < 2:
        falta = "evidencia directa: un análisis in silico sobre un dataset público aprobado (no sintético) o un resultado de laboratorio contra el prerregistro" if not directa else "que la evidencia directa sea consistente y precisa: intervalo que no cruce el efecto mínimo"
        pasos.append({"de": "baja", "a": "moderada", "falta": falta})
    if actual < 3:
        falta = "réplica de ese resultado directo en una cohorte independiente, con las reglas de análisis congeladas antes de mirar los datos" if cohortes < 2 or not directa else "consistencia entre las cohortes y ausencia de sesgo de publicación"
        pasos.append({"de": "moderada", "a": "alta", "falta": falta})
    return pasos
