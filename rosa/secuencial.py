"""Evidencia acumulada por hipotesis con e-valores (Popper, Huang y otros,
2025): cada prueba con p-valor se convierte en un e-valor con el calibrador
e = kappa * p^(kappa - 1), kappa en (0, 1); el producto de los e-valores de
las pruebas validas es la evidencia acumulada, y se rechaza la nula al
nivel alfa cuando el producto alcanza 1/alfa. A diferencia de sumar p-valores
o contar "cuantas pruebas salieron", esto controla el error de tipo I aunque
se sigan anadiendo pruebas.
"""

from __future__ import annotations

import re
from typing import Any

KAPPA = 0.5
ALFA = 0.1


def e_valor(p: float, kappa: float = KAPPA) -> float:
    p = min(max(p, 1e-12), 1.0)
    return kappa * p ** (kappa - 1)


def p_de(resultados: dict[str, str]) -> float | None:
    """El p-valor principal de una ejecucion: la clave que empieza por p y
    tiene un numero entre 0 y 1. Si hay varias, la primera en orden de
    prioridad (p_valor, p_bilateral, p)."""
    candidatas = sorted(resultados.keys(), key=lambda k: (0 if k in ("p_valor", "p_bilateral", "p") else 1, k))
    for k in candidatas:
        if not re.match(r"^p($|_|val|bil)", k, re.I):
            continue
        try:
            v = float(str(resultados[k]).replace(",", "."))
        except ValueError:
            continue
        if 0 < v <= 1:
            return v
    return None


def agregar(ejecuciones: list[dict[str, Any]]) -> dict[str, Any] | None:
    """La evidencia acumulada de las ejecuciones validas (auditoria valida)
    de una hipotesis. None si ninguna aporta p-valor."""
    validas = [x for x in ejecuciones if (x.get("auditoria") or {}).get("veredicto") == "valido" and x.get("estado") == "completado"]
    pruebas = []
    e_total = 1.0
    for x in validas:
        p = p_de(x.get("resultados", {}))
        if p is None:
            continue
        e = e_valor(p)
        e_total *= e
        pruebas.append({"ejecucionId": x["id"], "p": p, "e": round(e, 4)})
    if not pruebas:
        return None
    return {"eAcumulado": round(e_total, 4), "pruebas": pruebas, "alfa": ALFA, "kappa": KAPPA, "rechazaNula": e_total >= 1 / ALFA}
