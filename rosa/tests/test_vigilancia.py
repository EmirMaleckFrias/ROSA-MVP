"""Vigilancia de literatura por hipótesis: una búsqueda al día, sin repetir lo
conocido, con evento cuando hay novedades y sin afirmar nada si Exa no
responde. Sin red."""
import asyncio

import pytest

from rosa import config, vigilancia
from rosa.estado.almacen import Almacen
from rosa.fuentes import exa
from rosa.fuentes.base import FuenteNoDisponible

DIA = 24 * 3600 * 1000
T0 = 1757900000000

ARTICULOS = [
    {"titulo": "Trabajo ya conocido", "referencia": "Conocido, 2026", "url": "https://doi.org/10.1000/conocido", "doi": "10.1000/conocido", "fecha": "2026-09-14", "preprint": False, "resumen": "x", "similitud": 0.7},
    {"titulo": "Trabajo nuevo", "referencia": "Nuevo et al., 2026", "url": "https://doi.org/10.1000/nuevo", "doi": "10.1000/nuevo", "fecha": "2026-09-15", "preprint": False, "resumen": "GFAP antes que NfL.", "similitud": 0.81},
    {"titulo": "Preprint nuevo", "referencia": "Pre, 2026", "url": "https://www.medrxiv.org/content/10.1101/2026.09.01.1v1", "doi": "10.1101/2026.09.01.1", "fecha": "2026-09-15", "preprint": True, "resumen": "y", "similitud": 0.5},
    {"titulo": "", "referencia": "Sin título", "url": "https://x.org/1", "doi": None, "fecha": None, "preprint": False, "resumen": "", "similitud": None},
]


@pytest.fixture
def almacen(tmp_path):
    al = Almacen(tmp_path / "rosa.db")

    def sembrar(e):
        e["investigaciones"].append({"id": "inv-1", "titulo": "GFAP y NfL", "objetivo": "orden"})
        e["hipotesis"].append({"id": "hip-1", "investigacionId": "inv-1", "titulo": "GFAP precede a NfL", "enunciado": "En portadores de APOE4 la GFAP sube antes que el NfL", "estado": "propuesta", "creadaEn": T0 - 3 * DIA,
                               "procedencia": {"fuentes": [{"doi": "10.1000/CONOCIDO", "pmid": None}]}})
        e["hipotesis"].append({"id": "hip-2", "investigacionId": "inv-1", "titulo": "Descartada", "enunciado": "algo", "estado": "descartada", "creadaEn": T0 - 3 * DIA, "procedencia": {"fuentes": []}})
        return True

    al.mutar(sembrar, "prueba")
    yield al
    al.cerrar()


def test_vigilar_encuentra_novedades_sin_repetir_lo_conocido_y_deja_evento(almacen, monkeypatch):
    monkeypatch.setattr(config, "CLAVE_EXA", "x")
    consultas = []

    async def buscar_falso(texto, **kw):
        consultas.append(kw)
        return list(ARTICULOS), len(ARTICULOS), 0.007

    monkeypatch.setattr(exa, "buscar", buscar_falso)
    resumen = asyncio.run(vigilancia.vigilar(almacen, T0))
    assert resumen == {"comprobadas": 1, "conNovedades": 1, "nuevas": 2, "costeUsd": 0.007, "errores": 0}
    # Solo la hipótesis viva; la descartada no se consulta.
    assert len(consultas) == 1 and consultas[0]["desde_fecha"] == "2025-09-12" and consultas[0]["pregunta_pasajes"].startswith("En portadores")
    h = next(x for x in almacen.estado["hipotesis"] if x["id"] == "hip-1")
    v = h["vigilancia"]
    assert v["ultimaComprobacion"] == T0 and v["comprobaciones"] == 1 and v["costeUsd"] == 0.007 and v["ultimoError"] is None
    assert [n["doi"] for n in v["nuevas"]] == ["10.1000/nuevo", "10.1101/2026.09.01.1"]
    assert v["nuevas"][1]["preprint"] is True and v["nuevas"][0]["pasaje"] == "GFAP antes que NfL."
    eventos = [ev for ev in almacen.estado["eventos"] if ev["tipo"] == "vigilancia"]
    assert len(eventos) == 1 and "2 publicaciones nuevas" in eventos[0]["texto"] and eventos[0]["ruta"].endswith("/hipotesis/hip-1")
    # Dentro de las 24 horas no se repite; pasado un día, sí, y no vuelve a anotar lo ya visto.
    assert asyncio.run(vigilancia.vigilar(almacen, T0 + DIA - 1))["comprobadas"] == 0
    resumen2 = asyncio.run(vigilancia.vigilar(almacen, T0 + DIA + 1))
    assert resumen2["comprobadas"] == 1 and resumen2["nuevas"] == 0
    h = next(x for x in almacen.estado["hipotesis"] if x["id"] == "hip-1")
    assert h["vigilancia"]["comprobaciones"] == 2 and len(h["vigilancia"]["nuevas"]) == 2
    assert len([ev for ev in almacen.estado["eventos"] if ev["tipo"] == "vigilancia"]) == 1


def test_sin_clave_no_hace_nada_y_sin_respuesta_no_afirma(almacen, monkeypatch):
    monkeypatch.setattr(config, "CLAVE_EXA", "")
    assert asyncio.run(vigilancia.vigilar(almacen, T0))["comprobadas"] == 0
    assert "vigilancia" not in next(x for x in almacen.estado["hipotesis"] if x["id"] == "hip-1")
    monkeypatch.setattr(config, "CLAVE_EXA", "x")

    async def caida(texto, **kw):
        raise FuenteNoDisponible("Exa: HTTP 503")

    monkeypatch.setattr(exa, "buscar", caida)
    resumen = asyncio.run(vigilancia.vigilar(almacen, T0))
    assert resumen["errores"] == 1 and resumen["comprobadas"] == 0
    v = next(x for x in almacen.estado["hipotesis"] if x["id"] == "hip-1")["vigilancia"]
    assert v["ultimaComprobacion"] is None and v["comprobaciones"] == 0 and v["ultimoError"].startswith("No pude comprobar")
    assert not [ev for ev in almacen.estado["eventos"] if ev["tipo"] == "vigilancia"]
