"""Tamano muestral para dos grupos, continuo y binario. Adaptado del
calculador de la skill clinical-trial-protocol (Anthropic, Apache-2.0) para
Rosa: sin argparse, sin escritura de ficheros, resultados como diccionarios.
"""

from __future__ import annotations

import math

from scipy import stats


def _z(p: float) -> float:
    return float(stats.norm.ppf(p))


def continuo(delta: float, sigma: float, alfa: float = 0.05, potencia: float = 0.8, sigma2: float | None = None, abandono: float = 0.0, bilateral: bool = True) -> dict[str, float]:
    """n por grupo para detectar una diferencia de medias `delta` con
    desviación `sigma` (y `sigma2` en el segundo grupo si difiere)."""
    if delta == 0 or sigma <= 0:
        raise ValueError("delta distinto de cero y sigma positiva")
    za = _z(1 - alfa / 2) if bilateral else _z(1 - alfa)
    zb = _z(potencia)
    var = sigma**2 + (sigma2**2 if sigma2 else sigma**2)
    n = (za + zb) ** 2 * var / delta**2
    n_ajustado = n / (1 - abandono) if 0 <= abandono < 1 else n
    return {"n_por_grupo": math.ceil(n), "n_por_grupo_con_abandono": math.ceil(n_ajustado), "n_total": 2 * math.ceil(n_ajustado), "alfa": alfa, "potencia": potencia, "delta": delta, "sigma": sigma, "efecto_d": round(delta / sigma, 3)}


def binario(p1: float, p2: float, alfa: float = 0.05, potencia: float = 0.8, abandono: float = 0.0, bilateral: bool = True) -> dict[str, float]:
    """n por grupo para detectar la diferencia entre dos proporciones."""
    if not (0 < p1 < 1 and 0 < p2 < 1) or p1 == p2:
        raise ValueError("proporciones en (0, 1) y distintas")
    za = _z(1 - alfa / 2) if bilateral else _z(1 - alfa)
    zb = _z(potencia)
    pm = (p1 + p2) / 2
    n = (za * math.sqrt(2 * pm * (1 - pm)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p1 - p2) ** 2
    n_ajustado = n / (1 - abandono) if 0 <= abandono < 1 else n
    return {"n_por_grupo": math.ceil(n), "n_por_grupo_con_abandono": math.ceil(n_ajustado), "n_total": 2 * math.ceil(n_ajustado), "alfa": alfa, "potencia": potencia, "p1": p1, "p2": p2}


def tabla_potencias(delta: float, sigma: float, alfa: float = 0.05) -> list[dict[str, float]]:
    return [continuo(delta, sigma, alfa, pot) for pot in (0.8, 0.9)]
