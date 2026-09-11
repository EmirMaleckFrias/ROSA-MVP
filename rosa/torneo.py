"""El torneo de hipotesis: Elo por pares con juez y debias.

Como en Co-Scientist: se emparejan hipotesis de Elo cercano (y las nuevas con
alguien del top para situarlas rapido), el juez compara A con B y luego B con
A; si discrepa, el partido queda en tablas y no mueve el Elo. K = 32. El Elo
inicial es 1500 (es el que usa la interfaz).

Bradley-Terry (`choix.ilsr_pairwise`) es la alternativa cuando haya muchas
hipotesis; con menos de 30, Elo es mas legible y se puede seguir a mano.
"""

from __future__ import annotations

import itertools
import random
from typing import Any

K = 32


def esperado(a: float, b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((b - a) / 400.0))


def actualizar(elo_a: float, elo_b: float, gano_a: bool) -> tuple[int, int]:
    ea = esperado(elo_a, elo_b)
    sa = 1.0 if gano_a else 0.0
    return round(elo_a + K * (sa - ea)), round(elo_b + K * ((1 - sa) - (1 - ea)))


def emparejar(hipotesis: list[dict[str, Any]], maximo: int = 6, semilla: int | None = None) -> list[tuple[dict, dict]]:
    """Pares para esta ronda: primero cada hipotesis sin partidos contra una
    del top, luego pares de Elo cercano que no se hayan enfrentado ya."""
    vivas = [h for h in hipotesis if h["estado"] in ("propuesta", "en_revision", "refinar", "aceptada")]
    if len(vivas) < 2:
        return []
    rng = random.Random(semilla)
    orden = sorted(vivas, key=lambda h: -h["elo"])
    pares: list[tuple[dict, dict]] = []
    usados: set[str] = set()
    for h in vivas:
        if len(pares) >= maximo:
            break
        if h["partidos"] or h["id"] in usados:
            continue
        rivales = [r for r in orden[:5] if r["id"] != h["id"] and r["id"] not in usados]
        if rivales:
            r = rng.choice(rivales)
            pares.append((h, r))
            usados.update({h["id"], r["id"]})
    for a, b in itertools.combinations(orden, 2):
        if len(pares) >= maximo:
            break
        if a["id"] in usados or b["id"] in usados:
            continue
        if b["id"] in a["rivales"] and abs(a["elo"] - b["elo"]) > 100:
            continue
        if abs(a["elo"] - b["elo"]) <= 150:
            pares.append((a, b))
            usados.update({a["id"], b["id"]})
    return pares


def registrar_partido(a: dict[str, Any], b: dict[str, Any], gano_a: bool | None, iteracion: int, resumen: str, eje: str) -> None:
    """Aplica el resultado a las dos hipotesis (en sitio). `gano_a=None` son
    tablas: se anota el debate pero el Elo no se mueve."""
    if gano_a is not None:
        a["elo"], b["elo"] = actualizar(a["elo"], b["elo"], gano_a)
    for h, rival, gano in ((a, b, gano_a), (b, a, None if gano_a is None else not gano_a)):
        h["historialElo"].append({"iteracion": iteracion, "elo": h["elo"]})
        if rival["id"] not in h["rivales"]:
            h["rivales"].append(rival["id"])
        h["partidos"].append({"iteracion": iteracion, "rivalId": rival["id"], "resultado": "gano" if gano else "perdio", "resumenDebate": resumen if gano is not None else f"Tablas (el juez discrepo al invertir el orden): {resumen}", "ejeDecisivo": eje})
        for r in h["revisionesAutomaticas"]:
            if r["tipo"] == "torneo":
                r["estado"] = "hecha" if r["estado"] == "pendiente" else "rehecha"
                r["resumen"] = f"Partido en la iteracion {iteracion} contra {rival['titulo'][:60]}: {'gano' if gano else ('tablas' if gano is None else 'perdio')}."
                r["fecha"] = None
