"""Cliente HTTP compartido: límite de tasa por fuente, reintentos y tiempo
límite. Cada fuente declara cuántas peticiones por segundo admite y el
cliente se encarga de esperar.

Diseño: un `Limitador` por dominio con el algoritmo de cubo de fichas (deja
pasar N por segundo y hace esperar al resto), reintentos con espera
exponencial en 429 y 5xx, y un único `httpx.AsyncClient` con el User-Agent
de Rosa (que lleva el correo de contacto, como piden Crossref y Unpaywall).

También viven aquí la referencia corta ("Apellido et al., 2025") con la que
Rosa nombra una fuente a la persona y su desambiguación cuando dos fuentes
distintas de una corrida se llamarían igual.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Iterable

import httpx

from rosa import config


class FuenteNoDisponible(RuntimeError):
    """La fuente no respondió o respondió con error. No significa "no hay"."""


class NoEncontrado(FuenteNoDisponible):
    """La fuente respondió 404: el identificador no existe allí. Es la única
    respuesta de error que sí significa "no está" (y no cuenta como caída)."""


_COMPARTIDOS: dict[str, "Limitador"] = {}


def compartido(clave: str, por_segundo: float) -> "Limitador":
    """Un limitador por host compartido entre módulos: PubMed, ClinVar y GEO
    pegan al mismo E-utilities, y el límite es por IP, no por módulo."""
    if clave not in _COMPARTIDOS:
        _COMPARTIDOS[clave] = Limitador(por_segundo)
    return _COMPARTIDOS[clave]


def json_de(r: httpx.Response) -> Any:
    """`r.json()` que convierte un cuerpo no parseable (HTML de error con 200)
    en FuenteNoDisponible en vez de en una excepción suelta."""
    try:
        return r.json()
    except ValueError as ex:
        raise FuenteNoDisponible(f"{r.url}: respuesta no parseable ({str(ex)[:60]})")


class Limitador:
    def __init__(self, por_segundo: float):
        self.intervalo = 1.0 / por_segundo
        self._siguiente = 0.0
        self._lock = asyncio.Lock()

    async def esperar(self) -> None:
        async with self._lock:
            ahora = time.monotonic()
            if ahora < self._siguiente:
                await asyncio.sleep(self._siguiente - ahora)
                ahora = time.monotonic()
            self._siguiente = max(ahora, self._siguiente) + self.intervalo


_cliente: httpx.AsyncClient | None = None


def cliente() -> httpx.AsyncClient:
    global _cliente
    if _cliente is None or _cliente.is_closed:
        _cliente = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0), headers={"User-Agent": config.USER_AGENT}, follow_redirects=True)
    return _cliente


async def cerrar() -> None:
    global _cliente
    if _cliente is not None and not _cliente.is_closed:
        await _cliente.aclose()
    _cliente = None


async def pedir(metodo: str, url: str, limitador: Limitador, *, intentos: int = 3, **kwargs: Any) -> httpx.Response:
    """GET o POST con límite de tasa y reintentos. Lanza FuenteNoDisponible."""
    ultimo: Exception | None = None
    for intento in range(intentos):
        await limitador.esperar()
        try:
            r = await cliente().request(metodo, url, **kwargs)
        except httpx.HTTPError as ex:
            ultimo = ex
            await asyncio.sleep(0.5 * 2**intento)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            ultimo = FuenteNoDisponible(f"{url}: HTTP {r.status_code}")
            espera = r.headers.get("retry-after")
            try:
                segundos = min(float(espera), 60.0) if espera else 0.5 * 2**intento
            except ValueError:
                segundos = 0.5 * 2**intento
            await asyncio.sleep(segundos)
            continue
        if r.status_code == 404:
            raise NoEncontrado(f"{url}: HTTP 404")
        if r.status_code >= 400:
            raise FuenteNoDisponible(f"{url}: HTTP {r.status_code} {r.text[:200]}")
        return r
    raise FuenteNoDisponible(f"{url}: sin respuesta tras {intentos} intentos ({ultimo})")


def _apellido(nombre: str) -> str:
    return nombre.split(",")[0].split(" ")[-1] if " " in nombre and "," not in nombre else nombre.split(",")[0]


def referencia_corta(autores: list[str], anio: int | None, dominio: str | None = None, identificador: str | None = None) -> str:
    """"Cohorte clínica, 2025" a partir de la lista de apellidos.

    Sin autores (páginas de reguladores, registros, PDF sin metadatos) la
    referencia lleva algo que la distinga: el dominio de la URL o el
    identificador corto (PMCID, DOI, NCT), y el año: "Sin autor (fda.gov),
    2024". Treinta y cuatro fuentes llamadas exactamente "Sin autor" no se
    distinguen en la procedencia ni en el dossier."""
    # Un None o una cadena vacía dentro de la lista (un conector que no pudo
    # leer un nombre) no es un autor: se salta, y si no queda ninguno la fuente
    # es "Sin autor" con su marca.
    autores = [str(a).strip() for a in (autores or []) if a and str(a).strip()]
    if not autores:
        marca = _marca_sin_autor(dominio, identificador)
        cuerpo = f"Sin autor ({marca})" if marca else "Sin autor"
        return f"{cuerpo}, {anio}" if anio else cuerpo
    primero = _apellido(autores[0])
    if len(autores) == 1:
        cuerpo = primero
    elif len(autores) == 2:
        cuerpo = f"{primero} y {_apellido(autores[1])}"
    else:
        cuerpo = f"{primero} et al."
    return f"{cuerpo}, {anio}" if anio else cuerpo


def _marca_sin_autor(dominio: str | None, identificador: str | None) -> str:
    d = (dominio or "").strip().lower()
    d = re.sub(r"^https?://", "", d).split("/")[0]
    d = re.sub(r"^www\.", "", d)
    if d:
        return d[:40]
    i = (identificador or "").strip()
    return i[:40]


_ANIO_FINAL = re.compile(r"^(.*?,\s*)((?:19|20)\d{2})([a-z]?)$")


def desambiguar_referencia(referencia: str, existentes: "Iterable[str]", id_corto: str | None = None) -> str:
    """La referencia corta que se registra cuando ya existe otra igual en la
    corrida: se añade una letra al año ("Bhagunde et al., 2026" y luego
    "Bhagunde et al., 2026b", "2026c"...) o, si no hay año, el id corto entre
    paréntesis. La primera fuente se queda como está: la letra solo la llevan
    las siguientes. Si `referencia` no choca con ninguna, vuelve tal cual.

    Es texto para la persona: la resolución de citas va por `fuenteId`, así
    que el orden de llegada no cambia ningún veredicto."""
    ocupadas = {(r or "").strip().lower() for r in existentes}
    ref = (referencia or "").strip() or "Sin autor"
    if ref.lower() not in ocupadas:
        return ref
    m = _ANIO_FINAL.match(ref)
    if m:
        base, anio = m.group(1), m.group(2)
        for letra in "bcdefghijklmnopqrstuvwxyz":
            candidata = f"{base}{anio}{letra}"
            if candidata.lower() not in ocupadas:
                return candidata
    if id_corto:
        candidata = f"{ref} ({id_corto.strip()[:24]})"
        if candidata.lower() not in ocupadas:
            return candidata
    for n in range(2, 100):
        candidata = f"{ref} ({n})"
        if candidata.lower() not in ocupadas:
            return candidata
    return ref
