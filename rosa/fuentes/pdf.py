"""PDF por pagina con PyMuPDF. La pagina es la del visor (1-indexada) y,
antes de emitir una cita, se comprueba que el fragmento aparece literalmente
en esa pagina: un desfase de una pagina es un fallo grave.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pymupdf

from rosa import config
from rosa.fuentes.base import Limitador, pedir

_limitador = Limitador(2.0)


async def descargar(url: str) -> Path | None:
    """Guarda el PDF en `pdfs/<hash>.pdf`. None si lo que llega no es un PDF."""
    config.DIR_PDFS.mkdir(parents=True, exist_ok=True)
    destino = config.DIR_PDFS / (hashlib.sha1(url.encode()).hexdigest() + ".pdf")
    if destino.exists():
        return destino
    r = await pedir("GET", url, _limitador, headers={"Accept": "application/pdf"})
    if not r.content.startswith(b"%PDF"):
        return None
    destino.write_bytes(r.content)
    return destino


def paginas(ruta: Path) -> list[dict[str, Any]]:
    """[{pagina, texto}] con la pagina 1-indexada."""
    salida = []
    with pymupdf.open(str(ruta)) as doc:
        for p in doc:
            texto = p.get_text("text")
            if texto.strip():
                salida.append({"pagina": p.number + 1, "texto": texto})
    return salida


def _normalizar(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def fragmento_en_pagina(ruta: Path, fragmento: str, pagina: int) -> bool:
    """Comprobacion literal: las primeras 12 palabras del fragmento aparecen
    en el texto de esa pagina (normalizando espacios)."""
    palabras = _normalizar(fragmento).split(" ")
    aguja = " ".join(palabras[:12])
    if not aguja:
        return False
    with pymupdf.open(str(ruta)) as doc:
        if pagina < 1 or pagina > len(doc):
            return False
        return aguja in _normalizar(doc[pagina - 1].get_text("text"))
