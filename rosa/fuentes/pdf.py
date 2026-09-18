"""PDF por página con PyMuPDF. La página es la del visor (1-indexada) y,
antes de emitir una cita, se comprueba que el fragmento aparece literalmente
en esa página: un desfase de una página es un fallo grave.

La comprobación literal usa la misma regla que el verificador
(`rosa.verificador.pasaje_en_texto`, con `normalizar_texto_pdf` como única
normalización): ligaduras, guiones de fin de línea, comillas tipográficas y
números de línea de preprints no tumban una cita con la página correcta, y
una página equivocada sigue fallando. Los preprints (medRxiv, bioRxiv)
numeran las líneas y PyMuPDF las intercala como líneas sueltas; `paginas()`
las quita antes de guardar el fragmento siguiendo la cadena de la numeración
a lo largo del documento, así el extractor copia de un texto limpio y una
cifra de tabla que no sigue la cadena se queda donde estaba.
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


SALTO_MAXIMO_EN_SECUENCIA = 3  # números de línea que PyMuPDF puede perder seguidos sin que la cadena se rompa


def _continua_la_cadena(numeradas: list[tuple[int, int]], k: int) -> bool:
    """Un salto en la cadena (PyMuPDF perdió uno o más números) se acepta solo
    si el número siguiente de la página continúa desde él, o si no hay
    siguiente. Así una cifra de tabla que cae en el hueco ("53" entre las
    líneas 51 y 52) no se lleva el sitio del número de línea real que viene
    detrás, que antes quedaba como residuo en el texto que ve el extractor."""
    if k + 1 >= len(numeradas):
        return True
    v, siguiente = numeradas[k][1], numeradas[k + 1][1]
    return v < siguiente <= v + SALTO_MAXIMO_EN_SECUENCIA


def quitar_numeracion_en_secuencia(texto: str, siguiente: int | None, permitir_inicio: bool) -> tuple[str, int | None]:
    """Quita solo las líneas que son un número Y siguen la cadena de la
    numeración: `siguiente`, o hasta tres más si PyMuPDF perdió alguno (el
    salto se acepta solo si el número que viene detrás continúa desde él, ver
    `_continua_la_cadena`). Una cifra de tabla que va sola en su línea pero no
    sigue la cadena ("73", "40") se queda. Con `permitir_inicio`, una línea
    que no sigue la cadena pero abre otra (tres números consecutivos seguidos:
    1, 2, 3) la empieza, para la primera página numerada y para una numeración
    que reinicia (material suplementario). Devuelve el texto y el siguiente
    número esperado, para pasárselo a la página que viene. Límite: dos cifras
    de tabla seguidas que imitan la cadena (53, 54 justo donde se esperaba 52)
    no se distinguen de los números de línea sin mirar la maqueta."""
    lineas = (texto or "").split("\n")
    numeradas = [(i, int(l)) for i, l in enumerate(lineas) if _LINEA_NUMERO.match(l)]
    quitar: set[int] = set()
    esperado = siguiente
    for k, (i, v) in enumerate(numeradas):
        if esperado is not None and (v == esperado or (esperado < v <= esperado + SALTO_MAXIMO_EN_SECUENCIA and _continua_la_cadena(numeradas, k))):
            quitar.add(i)
            esperado = v + 1
        elif permitir_inicio and k + 2 < len(numeradas) and numeradas[k + 1][1] == v + 1 and numeradas[k + 2][1] == v + 2:
            quitar.add(i)
            esperado = v + 1
    return "\n".join(l for i, l in enumerate(lineas) if i not in quitar), esperado


def quitar_numeros_de_linea(texto: str) -> str:
    """Quita los números de línea cuando la página está numerada como un
    preprint; si no lo está, devuelve el texto tal cual (una tabla con cifras
    sueltas no se toca). En la página numerada solo se van los números que
    siguen la cadena: una cifra de tabla intercalada se queda."""
    if not tiene_lineas_numeradas(texto):
        return texto
    return quitar_numeracion_en_secuencia(texto, None, permitir_inicio=True)[0]


def paginas(ruta: Path) -> list[dict[str, Any]]:
    """[{pagina, texto}] con la página 1-indexada. En los preprints con
    líneas numeradas, el texto va sin los números de línea, también en las
    páginas que la heurística por página no detecta (una figura con pocas
    líneas, una tabla): ahí se quitan solo los números que continúan la
    cadena de la página anterior. Un documento sin ninguna página numerada no
    se toca."""
    with pymupdf.open(str(ruta)) as doc:
        crudas = [(p.number + 1, p.get_text("text")) for p in doc]
    documento_numerado = any(tiene_lineas_numeradas(t) for _, t in crudas)
    siguiente: int | None = None
    salida = []
    for numero, texto in crudas:
        if tiene_lineas_numeradas(texto):
            texto, siguiente = quitar_numeracion_en_secuencia(texto, siguiente, permitir_inicio=True)
        elif documento_numerado and siguiente is not None:
            texto, siguiente = quitar_numeracion_en_secuencia(texto, siguiente, permitir_inicio=False)
        if texto.strip():
            salida.append({"pagina": numero, "texto": texto})
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
