"""Los modelos de Rosa, todos por el AI Gateway de Vercel.

Decidido por la persona responsable el 9 y 10 de septiembre de 2026 (TRASPASO.md 2.2 y 2.3):
GPT-6 Astra de cerebro, Claude Opus 5 de juez, Claude Sonnet 5 en alto
volumen. Claude Fable 5.1 queda fuera: sus filtros de doble uso en biologia
devuelven vacio por la API en hipotesis mecanisticas y dianas terapeuticas.

La clave sale del entorno (ROSA_GATEWAY_KEY en .env, ignorado por git) y
nunca del codigo. El prefijo ``openai/`` es el de LiteLLM para "endpoint
compatible con OpenAI"; el resto es el id del modelo en el gateway.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import dspy
from dotenv import load_dotenv

load_dotenv()

URL_GATEWAY = os.environ.get("ROSA_GATEWAY_URL", "https://ai-gateway.vercel.sh/v1")

CEREBRO = "openai/gpt-6-astra"
JUEZ = "anthropic/claude-opus-5"
VOLUMEN = "anthropic/claude-sonnet-5"


class ClaveAusente(RuntimeError):
    pass


def clave() -> str:
    valor = os.environ.get("ROSA_GATEWAY_KEY", "")
    if not valor:
        raise ClaveAusente("Falta ROSA_GATEWAY_KEY en el entorno (.env). Se copia del .env del RAG; nunca al codigo ni a un chat.")
    return valor


def lm(modelo: str, **kwargs) -> dspy.LM:
    """Un modelo del gateway listo para DSPy. `modelo` es el id del gateway."""
    return dspy.LM(f"openai/{modelo}", api_base=URL_GATEWAY, api_key=clave(), **kwargs)


@dataclass(frozen=True)
class Modelos:
    cerebro: dspy.LM
    juez: dspy.LM
    volumen: dspy.LM
    """El reflexivo de GEPA: la documentacion pide un modelo fuerte a temperature=1.0 y max_tokens=32000."""
    reflexion: dspy.LM


def modelos() -> Modelos:
    return Modelos(
        cerebro=lm(CEREBRO),
        juez=lm(JUEZ, max_tokens=8000),  # el Killer devuelve once comprobaciones con detalle: sin margen se trunca el JSON
        volumen=lm(VOLUMEN),
        reflexion=lm(JUEZ, temperature=1.0, max_tokens=32000),
    )
