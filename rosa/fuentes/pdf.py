"""PDF por página con PyMuPDF. La página es la del visor (1-indexada) y,
antes de emitir una cita, se comprueba que el fragmento aparece literalmente
en esa página: un desfase de una página es un fallo grave.

La comprobación literal usa la misma regla que el verificador
(`rosa.verificador.pasaje_en_texto`, con `normalizar_texto` en los dos lados):
ligaduras, guiones de fin de línea, comillas tipográficas y números de línea
de preprints no tumban una cita con la página correcta, y una página
equivocada sigue fallando. Los preprints (medRxiv, bioRxiv) numeran las
líneas y PyMuPDF las intercala como líneas sueltas; `paginas()` las quita
antes de guardar el fragmento, así el extractor copia de un texto limpio.
"""

from __future__ import annotations

import hashlib
import httpx
import re
from pathlib import Path
from typing import Any

import pymupdf

from rosa import config
from rosa import verificador as V
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
                    return None  # más de 50 MB no es un artículo
                partes.append(trozo)
    except httpx.HTTPError:
        return None
    contenido = b"".join(partes)
    if not contenido.startswith(b"%PDF"):
        return None
    destino.write_bytes(contenido)
    return destino


_LINEA_NUMERO = re.compile(r"^\s*\d{1,4}\s*$")
UMBRAL_LINEAS_NUMERADAS = 0.3


UMBRAL_CONSECUTIVOS = 0.6


def tiene_lineas_numeradas(texto: str) -> bool:
    """True si la página lleva la numeración de líneas de un preprint: al menos
    el 30 % de sus líneas son un entero suelto Y esos enteros van en orden
    consecutivo (cada uno es el anterior más uno en el 60 % de los casos o
    más). Una tabla con una cifra por línea ("42", "180", "7") cumple lo
    primero pero no lo segundo, y sus cifras no se tocan."""
    lineas = [l for l in (texto or "").split("\n") if l.strip()]
    if len(lineas) < 10:
        return False
    numeros = [int(l) for l in lineas if _LINEA_NUMERO.match(l)]
    if len(numeros) < UMBRAL_LINEAS_NUMERADAS * len(lineas) or len(numeros) < 2:
        return False
    consecutivos = sum(1 for a, b in zip(numeros, numeros[1:]) if b == a + 1)
    return consecutivos >= UMBRAL_CONSECUTIVOS * (len(numeros) - 1)


def quitar_numeros_de_linea(texto: str) -> str:
    """Quita las líneas que son solo un número cuando la página está numerada
    como un preprint. Si no lo está, devuelve el texto tal cual (una tabla
    con cifras sueltas no se toca)."""
    if not tiene_lineas_numeradas(texto):
        return texto
    return "\n".join(l for l in texto.split("\n") if not _LINEA_NUMERO.match(l))


def paginas(ruta: Path) -> list[dict[str, Any]]:
    """[{pagina, texto}] con la página 1-indexada. En los preprints con
    líneas numeradas, el texto va sin los números de línea."""
    salida = []
    with pymupdf.open(str(ruta)) as doc:
        for p in doc:
            texto = quitar_numeros_de_linea(p.get_text("text"))
            if texto.strip():
                salida.append({"pagina": p.number + 1, "texto": texto})
    return salida


def fragmento_en_texto_de_pagina(texto_pagina: str, fragmento: str) -> bool:
    """Comprobación literal contra el texto ya extraído de la página (el
    `fr["texto"]` del fragmento): la misma regla que el verificador, sin
    reabrir el PDF por cada afirmación. Un fragmento vacío no es literal."""
    if not fragmento or not fragmento.strip():
        return False
    return V.pasaje_en_texto(fragmento, texto_pagina or "")


def fragmento_en_pagina(ruta: Path, fragmento: str, pagina: int) -> bool:
    """Comprobación literal contra la página `pagina` (1-indexada) del PDF en
    `ruta`, con la misma regla que `fragmento_en_texto_de_pagina`. Fuera de
    rango, False."""
    if not fragmento or not fragmento.strip():
        return False
    with pymupdf.open(str(ruta)) as doc:
        if pagina < 1 or pagina > len(doc):
            return False
        return fragmento_en_texto_de_pagina(doc[pagina - 1].get_text("text"), fragmento)
