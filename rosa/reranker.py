"""Reranker por el AI Gateway de Vercel: ordenar candidatos por pertinencia
antes de gastar una llamada de Sonnet en cada uno.

Un reranker recibe una pregunta y N documentos y devuelve una puntuación de
pertinencia por documento en una sola petición. Es un modelo pequeño y
barato (Cohere rerank-v3.5 sale a 0 USD por documento en el gateway;
Voyage rerank-2.5-lite a 0,02 USD por millón de tokens), y va por el mismo
gateway que el resto de modelos de Rosa, como exige la regla del proyecto.

Dónde se usa: en el cribado de literatura (de hasta 30 candidatos por
consulta, Sonnet solo ve los 12 mejores; el resto queda registrado como
excluido con su pertinencia) y en la novedad (los candidatos de OpenAlex y
Exa se ordenan antes de juzgarlos). Si el reranker no responde, Rosa sigue
como antes: cribado completo con el modelo. Nunca decide él solo: solo
ordena y corta; la puntuación final sigue siendo del programa de relevancia.

Añadido el 15 de septiembre de 2026.
"""

from __future__ import annotations

import os
from typing import Any

from rosa.fuentes.base import FuenteNoDisponible, Limitador, json_de, pedir
from rosa.gateway import URL_GATEWAY, clave

MODELO = os.environ.get("ROSA_RERANK_MODELO", "cohere/rerank-v3.5")
_limitador = Limitador(5.0)


def disponible() -> bool:
    """Con clave del gateway y modelo configurado. ROSA_RERANK_MODELO= (vacío)
    lo apaga sin tocar código."""
    return bool(MODELO) and bool(os.environ.get("ROSA_GATEWAY_KEY", ""))


def _url() -> str:
    base = URL_GATEWAY.rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return f"{base}/v2/rerank"


def _puntuaciones(d: dict[str, Any]) -> list[tuple[int, float]]:
    """Acepta la forma de Cohere (results[].index, relevance_score) y la del
    AI SDK (ranking[].originalIndex, score)."""
    salida: list[tuple[int, float]] = []
    for fila in d.get("results") or d.get("ranking") or []:
        if not isinstance(fila, dict):
            continue
        indice = fila.get("index", fila.get("originalIndex"))
        puntuacion = fila.get("relevance_score", fila.get("score"))
        if isinstance(indice, int) and isinstance(puntuacion, (int, float)):
            salida.append((indice, float(puntuacion)))
    salida.sort(key=lambda x: -x[1])
    return salida


async def reordenar(pregunta: str, documentos: list[str], top_n: int | None = None) -> list[tuple[int, float]]:
    """Devuelve [(índice del documento, pertinencia 0..1)] de mayor a menor.
    Lanza FuenteNoDisponible si el gateway no responde: quien llama decide
    seguir sin reranker."""
    if not documentos:
        return []
    cuerpo: dict[str, Any] = {"model": MODELO, "query": pregunta[:2000], "documents": [(d or "")[:4000] for d in documentos]}
    if top_n:
        cuerpo["top_n"] = max(1, min(top_n, len(documentos)))
    r = await pedir("POST", _url(), _limitador, headers={"Authorization": f"Bearer {clave()}", "Content-Type": "application/json"}, json=cuerpo)
    puntuaciones = _puntuaciones(json_de(r))
    if not puntuaciones:
        raise FuenteNoDisponible("reranker: respuesta sin puntuaciones")
    return puntuaciones


def texto_de_articulo(a: dict[str, Any]) -> str:
    """El documento que ve el reranker: título y resumen o pasajes."""
    return f"{a.get('titulo') or ''}\n{(a.get('resumen') or '')[:3000]}".strip()
