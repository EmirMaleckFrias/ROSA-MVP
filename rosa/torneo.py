"""El torneo de hipotesis: Elo por pares con juez y debias.

Como en Co-Scientist: se emparejan hipotesis de Elo cercano (y las nuevas con
alguien del top para situarlas rapido), el juez compara A con B y luego B con
A; si discrepa, el partido queda en tablas y no mueve el Elo. from rosa import politicas

K = politicas.ELO_K. El Elo
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
    """Pares para esta ronda: primero cada hipótesis sin partidos contra una
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
        h["partidos"].append({"iteracion": iteracion, "rivalId": rival["id"], "resultado": "tablas" if gano is None else ("gano" if gano else "perdio"), "resumenDebate": resumen if gano is not None else f"Tablas (el juez discrepo al invertir el orden): {resumen}", "ejeDecisivo": eje})
        for r in h["revisionesAutomaticas"]:
            if r["tipo"] == "torneo":
                r["estado"] = "hecha" if r["estado"] == "pendiente" else "rehecha"
                r["resumen"] = f"Partido en la iteración {iteracion} contra {rival['titulo'][:60]}: {'gano' if gano else ('tablas' if gano is None else 'perdio')}."
                r["fecha"] = None


# ---------------------------------------------------------------------------
# Bradley-Terry con intervalos por bootstrap (plan completo, ranking)
# ---------------------------------------------------------------------------


def _partidos_unicos(hipotesis: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """(ganador, perdedor) por cada partido decidido. Cada partido se guarda en
    las dos hipótesis (ganó en una, perdió en la otra), así que basta con los
    'ganó'. Las tablas no cuentan."""
    ids = {h["id"] for h in hipotesis}
    pares = []
    for h in hipotesis:
        for p in h.get("partidos", []):
            if p["resultado"] == "gano" and p["rivalId"] in ids:
                pares.append((h["id"], p["rivalId"]))
    return pares


def _ajustar_bt(ids: list[str], pares: list[tuple[str, str]], iteraciones: int = 200) -> dict[str, float]:
    """Algoritmo de minorización y maximización de Hunter (2004) para las
    fuerzas de Bradley-Terry, con un suavizado mínimo para que una hipótesis
    invicta o sin victorias no se vaya a infinito o a cero."""
    import math

    idx = {i: k for k, i in enumerate(ids)}
    n = len(ids)
    if n == 0:
        return {}
    victorias = [0.5] * n  # suavizado: media victoria a cada uno
    enfrentamientos = [[0.0] * n for _ in range(n)]
    for g, p in pares:
        victorias[idx[g]] += 1
        enfrentamientos[idx[g]][idx[p]] += 1
        enfrentamientos[idx[p]][idx[g]] += 1
    for k in range(n):
        for j in range(n):
            if j != k:
                enfrentamientos[k][j] += 1.0 / n  # un enfrentamiento virtual repartido
    fuerza = [1.0] * n
    for _ in range(iteraciones):
        nueva = []
        for k in range(n):
            denominador = sum(enfrentamientos[k][j] / (fuerza[k] + fuerza[j]) for j in range(n) if j != k)
            nueva.append(victorias[k] / denominador if denominador > 0 else fuerza[k])
        media_geom = math.exp(sum(math.log(x) for x in nueva) / n)
        fuerza = [x / media_geom for x in nueva]
    return {ids[k]: fuerza[k] for k in range(n)}


def bradley_terry(hipotesis: list[dict[str, Any]], remuestras: int = 200, semilla: int = 0) -> dict[str, dict[str, Any]]:
    """Fuerza de cada hipótesis en escala Elo (1500 + 400 log10 p) con un
    intervalo del 95 % por bootstrap de los partidos. Con menos de dos
    partidos decididos no hay estimación. El Elo se conserva como vista; esto
    es lo que ordena a las candidatas."""
    import math

    vivas = [h for h in hipotesis if h["estado"] != "descartada"]
    ids = [h["id"] for h in vivas]
    pares = _partidos_unicos(vivas)
    if len(pares) < 2 or len(ids) < 2:
        return {}
    escala = lambda p: round(1500 + 400 * math.log10(p))  # noqa: E731
    central = _ajustar_bt(ids, pares)
    rng = random.Random(semilla)
    muestras: dict[str, list[float]] = {i: [] for i in ids}
    for _ in range(remuestras):
        re = [pares[rng.randrange(len(pares))] for _ in pares]
        f = _ajustar_bt(ids, re, iteraciones=60)
        for i in ids:
            muestras[i].append(f[i])
    salida = {}
    for h in vivas:
        m = sorted(muestras[h["id"]])
        lo, hi = m[int(0.025 * len(m))], m[max(0, int(0.975 * len(m)) - 1)]
        salida[h["id"]] = {"fuerza": escala(central[h["id"]]), "ic95": [escala(lo), escala(hi)], "partidos": sum(1 for g, p in pares if h["id"] in (g, p))}
    return salida
