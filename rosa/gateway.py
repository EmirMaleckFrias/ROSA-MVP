"""Los modelos de Rosa, todos por el AI Gateway de Vercel.

Decidido por la persona responsable el 9 y 10 de septiembre de 2026 (TRASPASO.md 2.2 y 2.3):
GPT-6 Astra de cerebro, Claude Opus 5 de juez, Claude Sonnet 5 en alto
volumen. Claude Fable 5.1 queda fuera: sus filtros de doble uso en biología
devuelven vacío por la API en hipótesis mecanísticas y dianas terapéuticas.

La clave sale del entorno (ROSA_GATEWAY_KEY en .env, ignorado por git) y
nunca del código. El prefijo ``openai/`` es el de LiteLLM para "endpoint
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
        raise ClaveAusente("Falta ROSA_GATEWAY_KEY en el entorno (.env). Se copia del .env del RAG; nunca al código ni a un chat.")
    return valor


def lm(modelo: str, **kwargs) -> dspy.LM:
    """Un modelo del gateway listo para DSPy. `modelo` es el id del gateway.

    Caché. DSPy guarda cada respuesta en ~/.dspy_cache con la clave del
    request entero; una llamada idéntica (mismo prompt, mismos parámetros) se
    sirve del disco sin gastar. Eso es deliberado para el cerebro, el juez y
    el volumen: los repetidos entre corridas (la misma afirmación juzgada
    contra el mismo pasaje) salen gratis. Hay dos sitios donde NO se quiere la
    misma respuesta y hay que esquivarla (17 de septiembre de 2026, S-20):

    - las trayectorias de replicación (`rol="replica"`): el LM se construye con
      `cache=False`, porque va a temperatura 1,0 y su sentido es dar lecturas
      distintas; con caché, "5 de 5 trayectorias sostienen" era una sola
      llamada real repetida cinco veces;
    - las dos lecturas del examen de GEPA (rosa/gepa_continuo.py): usan el
      juez con `rollout_id` 0 y 1, que entra en la clave de la caché sin
      cambiar el prompt.

    `rollout_id` es la vía general: `Ctx.llamar(rol, programa, rollout_id=n,
    ...)` (rosa/bucle/pasos.py) puede pasarlo y el contexto usa
    `lm.copy(rollout_id=n)`; solo tiene efecto con temperatura distinta de 0
    (DSPy avisa si no)."""
    kwargs.setdefault("timeout", 300)  # segundos por petición HTTP al gateway; sin esto LiteLLM espera 6000
    return dspy.LM(f"openai/{modelo}", api_base=URL_GATEWAY, api_key=clave(), **kwargs)


@dataclass(frozen=True)
class Modelos:
    cerebro: dspy.LM
    juez: dspy.LM
    volumen: dspy.LM
    """El reflexivo de GEPA: la documentación pide un modelo fuerte a temperature=1.0 y max_tokens=32000."""
    reflexion: dspy.LM
    """El juez a temperatura alta para las trayectorias de replicación: lecturas distintas, no la misma llamada repetida."""
    replica: dspy.LM | None = None


def modelos() -> Modelos:
    return Modelos(
        cerebro=lm(CEREBRO),
        juez=lm(JUEZ, max_tokens=16000),  # el Killer razona largo y devuelve once comprobaciones con detalle: a 8000 aún se truncaba
        volumen=lm(VOLUMEN),
        reflexion=lm(JUEZ, temperature=1.0, max_tokens=32000),
        # Sin caché: cada trayectoria es una lectura nueva del juez (ver `lm`).
        replica=lm(JUEZ, temperature=1.0, max_tokens=16000, cache=False),
    )
