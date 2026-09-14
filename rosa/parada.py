"""Que parte de una condicion de parada puede automatizar Rosa.

La persona escribe la condicion en lenguaje corriente ("3 iteraciones o
cuando el modelo de mundo deje de cambiar"). El bucle solo puede medir tres
cosas: un numero de iteraciones, un tiempo de corrida y un numero de
llamadas al modelo (mas el presupuesto de la mision en dolares y horas). Lo
demas lo decide la persona con el boton de detener. Esta funcion dice, al
escribirla, que quedo automatizado y que no, para que la interfaz lo
muestre en vez de prometer mas de lo que hace. Espejo en
`frontend/src/lib/parada.ts`.
"""

from __future__ import annotations

import re
from typing import Any

_ITERACIONES = re.compile(r"(\d+)\s*iteraci\w*")
_TIEMPO = re.compile(r"(\d+(?:[.,]\d+)?)\s*(min\b|minutos?|horas?|h\b|dias?|días?)")
_LLAMADAS = re.compile(r"(\d+)\s*llamadas?")


def partes_automatizadas(texto: str) -> dict[str, Any]:
    """{iteraciones, tiempo, llamadas, resto, automatizada}. `resto` es lo que
    queda de la condicion una vez quitadas las partes medibles; si no esta
    vacio, esa parte la decide una persona."""
    t = (texto or "").lower()
    salida: dict[str, Any] = {"iteraciones": None, "tiempo": None, "llamadas": None, "resto": "", "automatizada": False}
    resto = t
    m = _ITERACIONES.search(t)
    if m:
        salida["iteraciones"] = int(m.group(1))
        resto = resto.replace(m.group(0), " ")
    m = _TIEMPO.search(t)
    if m:
        unidad = m.group(2)
        salida["tiempo"] = f"{m.group(1)} {'min' if unidad.startswith('min') else 'h' if unidad in ('h', 'hora') or unidad.startswith('hora') else 'd'}"
        resto = resto.replace(m.group(0), " ")
    m = _LLAMADAS.search(t)
    if m:
        salida["llamadas"] = int(m.group(1))
        resto = resto.replace(m.group(0), " ")
    # El resto se conserva tal como lo escribio la persona: solo se limpian los
    # conectores sueltos de los bordes ("o", ", o", "y") y los espacios dobles.
    resto = re.sub(r"\s+", " ", resto).strip(" ,;.")
    resto = re.sub(r"^(o|y|u|e|,|;)\s+", "", resto).strip(" ,;.")
    resto = re.sub(r"\s+(o|y|u|e)$", "", resto).strip(" ,;.")
    salida["resto"] = resto if len(resto) >= 4 else ""
    salida["automatizada"] = any(salida[k] is not None for k in ("iteraciones", "tiempo", "llamadas"))
    return salida


def texto_automatizacion(partes: dict[str, Any]) -> str:
    """Una frase para la interfaz y el informe."""
    medibles = []
    if partes.get("iteraciones") is not None:
        medibles.append(f"{partes['iteraciones']} iteraciones")
    if partes.get("tiempo"):
        medibles.append(f"{partes['tiempo']} de corrida")
    if partes.get("llamadas") is not None:
        medibles.append(f"{partes['llamadas']} llamadas")
    if not medibles:
        return "Rosa no puede medir esta condicion: la corrida sigue hasta que la detengas o hasta agotar el presupuesto de la mision."
    frase = "Rosa para sola al llegar a " + " o ".join(medibles) + " (y al agotar el presupuesto de la mision)"
    if partes.get("resto"):
        frase += f'. El resto ("{partes["resto"][:80]}") lo decides tu con el boton de detener'
    return frase + "."
