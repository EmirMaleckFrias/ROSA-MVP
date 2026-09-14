"""Cliente HTTP compartido: limite de tasa por fuente, reintentos y tiempo
limite. Cada fuente declara cuantas peticiones por segundo admite y el
cliente se encarga de esperar.

Diseno: un `Limitador` por dominio con el algoritmo de cubo de fichas (deja
pasar N por segundo y hace esperar al resto), reintentos con espera
exponencial en 429 y 5xx, y un unico `httpx.AsyncClient` con el User-Agent
de Rosa (que lleva el correo de contacto, como piden Crossref y Unpaywall).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from rosa import config


class FuenteNoDisponible(RuntimeError):
    """La fuente no respondio o respondio con error. No significa "no hay"."""


class NoEncontrado(FuenteNoDisponible):
    """La fuente respondio 404: el identificador no existe alli. Es la unica
    respuesta de error que si significa "no esta" (y no cuenta como caida)."""


_COMPARTIDOS: dict[str, "Limitador"] = {}


def compartido(clave: str, por_segundo: float) -> "Limitador":
    """Un limitador por host compartido entre modulos: PubMed, ClinVar y GEO
    pegan al mismo E-utilities, y el limite es por IP, no por modulo."""
    if clave not in _COMPARTIDOS:
        _COMPARTIDOS[clave] = Limitador(por_segundo)
    return _COMPARTIDOS[clave]


def json_de(r: httpx.Response) -> Any:
    """`r.json()` que convierte un cuerpo no parseable (HTML de error con 200)
    en FuenteNoDisponible en vez de en una excepcion suelta."""
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
    """GET o POST con limite de tasa y reintentos. Lanza FuenteNoDisponible."""
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


def referencia_corta(autores: list[str], anio: int | None) -> str:
    """"Cohorte clinica, 2025" a partir de la lista de apellidos."""
    if not autores:
        return f"Sin autor, {anio}" if anio else "Sin autor"
    primero = autores[0].split(",")[0].split(" ")[-1] if " " in autores[0] and "," not in autores[0] else autores[0].split(",")[0]
    if len(autores) == 1:
        cuerpo = primero
    elif len(autores) == 2:
        segundo = autores[1].split(",")[0].split(" ")[-1] if " " in autores[1] and "," not in autores[1] else autores[1].split(",")[0]
        cuerpo = f"{primero} y {segundo}"
    else:
        cuerpo = f"{primero} et al."
    return f"{cuerpo}, {anio}" if anio else cuerpo
