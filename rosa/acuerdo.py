"""Acuerdo entre dos evaluadores: kappa de Cohen, kappa ponderado, AC1 de Gwet.

Sirve para saber si el juez (o el Killer entero) acierta frente a una persona
cualificada, por tipo de comprobacion y no como promedio global. Kappa
corrige el acuerdo por el que se esperaria por azar; el ponderado (pesos
lineales) trata las categorias ordenadas (bajo, algunas dudas, alto) de modo
que equivocarse en un escalon cuesta menos que en dos. AC1 de Gwet resiste la
paradoja de kappa cuando una categoria domina (casi todo "acierta"), y se
reporta al lado, no en su lugar. Todo es determinista y sin dependencias.

Referencias: Cohen 1960 y 1968; Landis y Koch 1977 (los tramos de
interpretacion, que ellos mismos llamaron arbitrarios); Gwet 2008.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Any, Sequence

TRAMOS_LANDIS_KOCH = (
    (0.81, "casi perfecto"),
    (0.61, "sustancial"),
    (0.41, "moderado"),
    (0.21, "regular"),
    (0.0, "leve"),
)


def interpretar(kappa: float | None) -> str:
    if kappa is None:
        return "sin datos"
    if kappa < 0:
        return "peor que el azar"
    for umbral, nombre in TRAMOS_LANDIS_KOCH:
        if kappa >= umbral:
            return nombre
    return "leve"


def matriz_confusion(a: Sequence[Any], b: Sequence[Any], categorias: Sequence[Any] | None = None) -> dict[str, Any]:
    """Filas: evaluador a; columnas: evaluador b."""
    if len(a) != len(b):
        raise ValueError("las dos listas deben tener la misma longitud")
    cats = list(categorias) if categorias is not None else sorted(set(a) | set(b), key=str)
    idx = {c: i for i, c in enumerate(cats)}
    m = [[0] * len(cats) for _ in cats]
    for x, y in zip(a, b):
        m[idx[x]][idx[y]] += 1
    return {"categorias": cats, "matriz": m, "n": len(a)}


def kappa_cohen(a: Sequence[Any], b: Sequence[Any], categorias: Sequence[Any] | None = None, ponderado: bool = False) -> float | None:
    """Kappa de Cohen. Con `ponderado` usa pesos lineales |i - j| / (k - 1)
    sobre el orden de `categorias` (obligatorio darlas en orden). None si no
    hay datos o si el acuerdo esperado es 1 (todo en una categoria)."""
    n = len(a)
    if n == 0 or len(b) != n:
        return None
    mc = matriz_confusion(a, b, categorias)
    cats, m = mc["categorias"], mc["matriz"]
    k = len(cats)
    if k <= 1:
        return None
    filas = [sum(f) for f in m]
    cols = [sum(m[i][j] for i in range(k)) for j in range(k)]
    if ponderado:
        peso = lambda i, j: abs(i - j) / (k - 1)  # noqa: E731
        desacuerdo_obs = sum(peso(i, j) * m[i][j] for i in range(k) for j in range(k)) / n
        desacuerdo_esp = sum(peso(i, j) * filas[i] * cols[j] for i in range(k) for j in range(k)) / (n * n)
        if desacuerdo_esp == 0:
            return None
        return round(1 - desacuerdo_obs / desacuerdo_esp, 4)
    po = sum(m[i][i] for i in range(k)) / n
    pe = sum(filas[i] * cols[i] for i in range(k)) / (n * n)
    if pe >= 1:
        return None
    return round((po - pe) / (1 - pe), 4)


def ac1_gwet(a: Sequence[Any], b: Sequence[Any], categorias: Sequence[Any] | None = None) -> float | None:
    n = len(a)
    if n == 0 or len(b) != n:
        return None
    mc = matriz_confusion(a, b, categorias)
    cats, m = mc["categorias"], mc["matriz"]
    k = len(cats)
    if k <= 1:
        return None
    po = sum(m[i][i] for i in range(k)) / n
    # pi_j: proporcion media de asignaciones a la categoria j entre los dos evaluadores.
    pis = [(sum(m[j]) + sum(m[i][j] for i in range(k))) / (2 * n) for j in range(k)]
    pe = sum(p * (1 - p) for p in pis) / (k - 1)
    if pe >= 1:
        return None
    return round((po - pe) / (1 - pe), 4)


def intervalo_bootstrap(a: Sequence[Any], b: Sequence[Any], categorias: Sequence[Any] | None = None, ponderado: bool = False, repeticiones: int = 1000, semilla: int = 7) -> tuple[float, float] | None:
    """IC 95 % por bootstrap del kappa (percentiles 2,5 y 97,5)."""
    n = len(a)
    if n < 5:
        return None
    rng = random.Random(semilla)
    valores: list[float] = []
    pares = list(zip(a, b))
    for _ in range(repeticiones):
        muestra = [pares[rng.randrange(n)] for _ in range(n)]
        kap = kappa_cohen([x for x, _ in muestra], [y for _, y in muestra], categorias, ponderado)
        if kap is not None:
            valores.append(kap)
    if len(valores) < repeticiones // 2:
        return None
    valores.sort()
    return (round(valores[int(0.025 * len(valores))], 3), round(valores[min(len(valores) - 1, int(0.975 * len(valores)))], 3))


def acuerdo(a: Sequence[Any], b: Sequence[Any], categorias: Sequence[Any] | None = None, ordenadas: bool = False) -> dict[str, Any]:
    """Todo junto, listo para guardar: n, acuerdo bruto, kappa (ponderado si
    las categorias son ordenadas), AC1, IC bootstrap, matriz e interpretacion."""
    n = len(a)
    if n == 0:
        return {"n": 0, "bruto": None, "kappa": None, "ac1": None, "ic95": None, "matriz": None, "interpretacion": "sin datos", "ponderado": ordenadas}
    kap = kappa_cohen(a, b, categorias, ponderado=ordenadas)
    return {
        "n": n,
        "bruto": round(sum(1 for x, y in zip(a, b) if x == y) / n, 3),
        "kappa": kap,
        "ac1": ac1_gwet(a, b, categorias),
        "ic95": intervalo_bootstrap(a, b, categorias, ponderado=ordenadas),
        "matriz": matriz_confusion(a, b, categorias),
        "interpretacion": interpretar(kap),
        "ponderado": ordenadas,
        "distribucion": dict(Counter(str(x) for x in b)),
    }
