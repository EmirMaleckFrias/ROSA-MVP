"""La versión del arnes: que ROSA2018 exacta produjo cada corrida.

El paper de Zitnik y colaboradores (2026) pide que una auditoría pueda saber,
para cada hipótesis, con que versión del modelo y que configuración del
arnes se genero. Los modelos ya quedan registrados por llamada; esto añade
el código: el commit de git y un hash de las firmas DSPy (los contratos de
cada paso), que es lo que GEPA cambia al optimizar.
"""

from __future__ import annotations

import hashlib
import subprocess
from functools import lru_cache
from pathlib import Path

from rosa import config


@lru_cache(maxsize=1)
def arnes() -> dict[str, str]:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.RAIZ, capture_output=True, text=True, timeout=5).stdout.strip() or "sin-git"
        sucio = subprocess.run(["git", "status", "--porcelain"], cwd=config.RAIZ, capture_output=True, text=True, timeout=5).stdout.strip() != ""
    except Exception:  # noqa: BLE001
        commit, sucio = "sin-git", False
    firmas = Path(config.RAIZ) / "rosa" / "modulos" / "firmas.py"
    h = hashlib.sha256(firmas.read_bytes()).hexdigest()[:12] if firmas.exists() else "sin-firmas"
    optimizados = sorted(p.name for p in (Path(config.RAIZ) / "mlruns" / "optimizados").glob("*.json")) if (Path(config.RAIZ) / "mlruns" / "optimizados").exists() else []
    return {"commit": commit + ("+cambios" if sucio else ""), "firmas": h, "optimizados": ",".join(optimizados) or "ninguno"}
