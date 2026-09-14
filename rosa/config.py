"""Configuracion de Rosa: rutas, puertos y contacto para las APIs.

Todo lo que puede variar entre la Mac de la persona responsable y otra maquina vive aqui y se
lee del entorno (.env). Los valores por defecto sirven para arrancar sin
tocar nada: base de datos `rosa.db` en la raiz del repo, servidor en el
puerto 8765, MLflow en `mlflow.db`.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

RAIZ = Path(__file__).resolve().parent.parent

RUTA_BD = Path(os.environ.get("ROSA_BD", RAIZ / "rosa.db"))
PUERTO = int(os.environ.get("ROSA_PUERTO", "8765"))
HOST = os.environ.get("ROSA_HOST", "127.0.0.1")
MLFLOW_URI = os.environ.get("ROSA_MLFLOW_URI", f"sqlite:///{RAIZ / 'mlflow.db'}")
MLFLOW_UI = os.environ.get("ROSA_MLFLOW_UI", "http://127.0.0.1:5000")
FRONTEND_DIST = RAIZ / "frontend" / "dist"

# Contacto que se manda a Crossref, Unpaywall y OpenAlex. Es publico por
# diseno (piden un correo real para el "polite pool").
CORREO_CONTACTO = os.environ.get("ROSA_CORREO", "contacto-interno@example.invalid")
USER_AGENT = f"Rosa/0.1 (Alzheimer Project; mailto:{CORREO_CONTACTO})"

# Claves opcionales de fuentes. Sin ellas Rosa funciona con los cupos publicos.
CLAVE_NCBI = os.environ.get("ROSA_NCBI_KEY", "")
CLAVE_OPENALEX = os.environ.get("ROSA_OPENALEX_KEY", "")
CLAVE_S2 = os.environ.get("ROSA_S2_KEY", "")
# Espejo del estado en Convex (opcional): URL del deployment y clave de despliegue. Solo en .env.
CONVEX_URL = os.environ.get("CONVEX_URL", "").rstrip("/")
CONVEX_DEPLOY_KEY = os.environ.get("CONVEX_DEPLOY_KEY", "")

# Directorio donde se guardan los PDF descargados (texto completo por pagina).
DIR_PDFS = Path(os.environ.get("ROSA_PDFS", RAIZ / "pdfs"))

# Quien firma lo que hace Rosa en los historiales.
QUIEN_ROSA = "Rosa"

# Presupuesto por defecto de una corrida nueva, en llamadas al modelo.
# Una iteracion completa cuesta entre 120 y 250 llamadas (medido); 1500 da
# margen para varias iteraciones antes de que la corrida se pause y pregunte.
PRESUPUESTO_CORRIDA = int(os.environ.get("ROSA_PRESUPUESTO", "1500"))
ALERTAS_PRESUPUESTO = [0.5, 0.8, 0.95]
PRESUPUESTO_ITERACION = int(os.environ.get("ROSA_PRESUPUESTO_ITERACION", "300"))

# Precios estimados por millon de tokens (entrada, salida) en dolares, para
# el presupuesto en dinero de la mision. Son estimaciones para ordenar el
# gasto, no la factura: la factura real la da el AI Gateway. Se pueden
# sobreescribir con ROSA_PRECIOS='{"openai/gpt-6-astra": [5, 20], ...}'.
_PRECIOS_POR_DEFECTO = {
    "openai/gpt-6-astra": (5.0, 20.0),
    "anthropic/claude-opus-5": (15.0, 75.0),
    "anthropic/claude-sonnet-5": (3.0, 15.0),
}
try:
    import json as _json

    PRECIOS = {k: tuple(v) for k, v in _json.loads(os.environ.get("ROSA_PRECIOS", "{}")).items()} or dict(_PRECIOS_POR_DEFECTO)
except Exception:  # noqa: BLE001
    PRECIOS = dict(_PRECIOS_POR_DEFECTO)


def coste_usd(modelo: str, tokens_entrada: int, tokens_salida: int) -> float:
    # DSPy nombra los modelos del gateway como "openai/anthropic/claude-opus-5":
    # se quita el prefijo del proveedor compatible antes de buscar el precio.
    limpio = modelo.removeprefix("openai/") if modelo.count("/") > 1 else modelo
    entrada, salida = PRECIOS.get(modelo) or PRECIOS.get(limpio) or PRECIOS.get(modelo.split("/")[-1]) or (5.0, 20.0)
    return (tokens_entrada * entrada + tokens_salida * salida) / 1_000_000
