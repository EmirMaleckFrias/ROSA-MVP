"""Datos sinteticos con la forma de un dataset real, para el ensayo en seco.

Antes de gastar una ejecucion sobre los datos reales, el plan de analisis
congelado se corre sobre una tabla inventada con las mismas columnas y los
mismos tipos (numeros en el rango observado, categorias del mismo conjunto,
identificadores y fechas plausibles). Asi se detectan variables mal
nombradas, particiones imposibles o pruebas inaplicables sin tocar los
datos reales y sin gastar el presupuesto de reparacion sobre ellos. No es un
gemelo digital: la tabla no conserva ninguna relacion entre columnas, y por
eso sus cifras nunca cuentan como resultado.

Todo es local: el fichero real se lee en esta maquina y ningun valor sale
hacia un modelo. La tabla sintetica lleva marca en el nombre y en la
primera fila de comentario del plan.
"""

from __future__ import annotations

import csv
import random
import re
from pathlib import Path
from typing import Any

from rosa import datos as D

FILAS_POR_DEFECTO = 200
MAX_CATEGORIAS = 40


def _perfil_columnas(cabecera: list[str], filas: list[list[str]]) -> list[dict[str, Any]]:
    """Por columna: tipo, rango numerico o conjunto de categorias, fraccion de vacios."""
    perfil = []
    for i, col in enumerate(cabecera):
        valores = [f[i] if i < len(f) else "" for f in filas]
        no_vacios = [v for v in valores if v.strip()]
        vacios = 1 - (len(no_vacios) / len(valores)) if valores else 0.0
        nums = [n for n in (D._numero(v) for v in no_vacios) if n is not None]
        p: dict[str, Any] = {"columna": col, "vacios": round(vacios, 3)}
        if no_vacios and len(nums) >= max(3, len(no_vacios) * 0.6):
            enteros = all(float(n).is_integer() for n in nums)
            p.update(tipo="numerica", minimo=min(nums), maximo=max(nums), enteros=enteros)
            if enteros and len(set(nums)) <= 2 and all(x in (0.0, 1.0) for x in nums):
                p.update(tipo="binaria")
        elif no_vacios and all(re.match(r"^\d{4}-\d{2}-\d{2}", v.strip()) for v in no_vacios[:20]):
            fechas = sorted(v.strip()[:10] for v in no_vacios)
            p.update(tipo="fecha", minimo=fechas[0], maximo=fechas[-1])
        elif no_vacios and len(set(no_vacios)) == len(no_vacios) and len(no_vacios) > 10:
            p.update(tipo="identificador", prefijo=re.sub(r"\d+$", "", no_vacios[0])[:8] or "ID")
        elif no_vacios and len(set(no_vacios)) <= MAX_CATEGORIAS:
            cuenta: dict[str, int] = {}
            for v in no_vacios:
                cuenta[v] = cuenta.get(v, 0) + 1
            p.update(tipo="categorica", categorias=sorted(cuenta), pesos=[cuenta[c] for c in sorted(cuenta)])
        else:
            p.update(tipo="texto", longitud=int(sum(len(v) for v in no_vacios) / max(1, len(no_vacios))))
        perfil.append(p)
    return perfil


def _valor(p: dict[str, Any], rng: random.Random, i: int) -> str:
    if rng.random() < min(0.5, p.get("vacios", 0.0)):
        return ""
    t = p["tipo"]
    if t == "binaria":
        return str(rng.randint(0, 1))
    if t == "numerica":
        lo, hi = p["minimo"], p["maximo"]
        if lo == hi:
            return str(int(lo)) if p.get("enteros") else str(lo)
        x = rng.uniform(lo, hi)
        return str(int(round(x))) if p.get("enteros") else f"{x:.4g}"
    if t == "fecha":
        anio = rng.randint(int(p["minimo"][:4]), int(p["maximo"][:4]))
        return f"{anio:04d}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
    if t == "identificador":
        return f"{p['prefijo']}{i + 1:05d}"
    if t == "categorica":
        return rng.choices(p["categorias"], weights=p["pesos"], k=1)[0]
    return "texto sintetico " + "".join(rng.choice("abcdefghij") for _ in range(min(12, max(3, p.get("longitud", 8)))))


def generar(ruta_real: Path, destino: Path, filas: int = FILAS_POR_DEFECTO, semilla: int = 12345) -> dict[str, Any]:
    """Escribe en `destino` una tabla sintetica con la forma de `ruta_real`.
    Devuelve el perfil usado (sin valores individuales del fichero real, solo
    rangos y categorias). Lanza ValueError si el fichero real no es tabular."""
    tabla = D._leer_tabla(ruta_real)
    if tabla is None:
        raise ValueError("el dataset real no es una tabla legible: no se puede fabricar una sintetica")
    cabecera, filas_reales = tabla
    perfil = _perfil_columnas(cabecera, filas_reales)
    rng = random.Random(semilla)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cabecera)
        for i in range(filas):
            w.writerow([_valor(p, rng, i) for p in perfil])
    return {"columnas": len(cabecera), "filas": filas, "semilla": semilla, "perfil": [{k: v for k, v in p.items() if k not in ("pesos",)} for p in perfil]}
