"""PDF por pagina con PyMuPDF. La pagina es la del visor (1-indexada) y,
antes de emitir una cita, se comprueba que el fragmento aparece literalmente
en esa pagina: un desfase de una pagina es un fallo grave.
"""

from __future__ import annotations

import hashlib
import httpx
import re
from pathlib import Path
from typing import Any

import pymupdf

from rosa import config
from rosa.fuentes.base import Limitador, cliente, pedir

_limitador = Limitador(2.0)
MAX_PDF_BYTES = 50 * 1024 * 1024


async def descargar(url: str) -> Path | None:
    """Guarda el PDF en `pdfs/<hash>.pdf`. None si lo que llega no es un PDF."""
    config.DIR_PDFS.mkdir(parents=True, exist_ok=True)
    destino = config.DIR_PDFS / (hashlib.sha1(url.encode()).hexdigest() + ".pdf")
    if destino.exists():
        return destino
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    if not host or host in ("localhost",) or host.startswith(("127.", "10.", "192.168.", "169.254.", "0.")) or host.endswith(".local") or re.match(r"^172\.(1[6-9]|2\d|3[01])\.", host):
        return None  # una URL de terceros nunca apunta al propio servidor ni a la red local
    await _limitador.esperar()
    partes: list[bytes] = []
    total = 0
    try:
        async with cliente().stream("GET", url, headers={"Accept": "application/pdf"}) as r:
            if r.status_code >= 400:
                return None
            async for trozo in r.aiter_bytes():
                total += len(trozo)
                if total > MAX_PDF_BYTES:
                    return None  # mas de 50 MB no es un articulo
                partes.append(trozo)
    except httpx.HTTPError:
        return None
    contenido = b"".join(partes)
    if not contenido.startswith(b"%PDF"):
        return None
    destino.write_bytes(contenido)
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
