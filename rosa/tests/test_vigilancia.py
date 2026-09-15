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
    {"titulo": "Preprint nuevo sobre NfL y APOE4", "referencia": "Pre, 2026", "url": "https://www.medrxiv.org/content/10.1101/2026.09.01.1v1", "doi": "10.1101/2026.09.01.1", "fecha": "2026-09-15", "preprint": True, "resumen": "y", "similitud": 0.5},
    {"titulo": "Ruido: barrera hematoencefálica y fibronectina", "referencia": "Ruido, 2026", "url": "https://doi.org/10.1000/ruido", "doi": "10.1000/ruido", "fecha": "2026-09-15", "preprint": False, "resumen": "Nada que ver con la hipótesis.", "similitud": None},
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
    assert resumen == {"comprobadas": 1, "conNovedades": 1, "nuevas": 2, "costeUsd": 0.007, "errores": 0, "retiradas": 0}
    # Solo la hipótesis viva; la descartada no se consulta.
    assert len(consultas) == 1 and consultas[0]["desde_fecha"] == "2025-09-12" and consultas[0]["pregunta_pasajes"].startswith("En portadores")
    h = next(x for x in almacen.estado["hipotesis"] if x["id"] == "hip-1")
    v = h["vigilancia"]
    assert v["ultimaComprobacion"] == T0 and v["comprobaciones"] == 1 and v["costeUsd"] == 0.007 and v["ultimoError"] is None
    assert [n["doi"] for n in v["nuevas"]] == ["10.1000/nuevo", "10.1101/2026.09.01.1"]
    assert v["nuevas"][1]["preprint"] is True and v["nuevas"][0]["pasaje"] == "GFAP antes que NfL."
    assert v["nuevas"][0]["terminos"] == ["GFAP", "NfL"] and v["nuevas"][1]["terminos"] == ["NfL", "APOE4"]
    eventos = [ev for ev in almacen.estado["eventos"] if ev["tipo"] == "vigilancia"]
    assert len(eventos) == 1 and "2 publicaciones nuevas" in eventos[0]["texto"] and "nombran APOE4, GFAP, NfL" in eventos[0]["texto"] and eventos[0]["ruta"].endswith("/hipotesis/hip-1")
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


def test_terminos_de_prefiere_siglas_y_biomarcadores():
    assert vigilancia.terminos_de({"titulo": "Precedencia de GFAP sobre NfL en APOE ε4", "enunciado": "la GFAP se altera antes que el NfL"}) == ["GFAP", "NfL", "APOE"]
    assert vigilancia.terminos_de({"titulo": "BACE1 y p-tau181", "enunciado": ""}) == ["BACE1", "p-tau181"]
    assert vigilancia.es_pertinente(["GFAP", "NfL", "APOE"], {"titulo": "Fibronectin and blood-brain barrier", "pasaje": "APOE4 carriers"}) == []
    assert vigilancia.es_pertinente(["GFAP", "NfL", "APOE"], {"titulo": "Plasma GFAP precedes NfL", "pasaje": ""}) == ["GFAP", "NfL"]
    assert vigilancia.es_pertinente(["APOE", "general"], {"titulo": "APOE4 and something", "pasaje": ""}) == ["APOE"]


def test_depurar_retira_el_ruido_guardado_y_sus_eventos(almacen, monkeypatch):
    monkeypatch.setattr(config, "CLAVE_EXA", "x")

    def sembrar_ruido(e):
        h = next(x for x in e["hipotesis"] if x["id"] == "hip-1")
        h["vigilancia"] = {"ultimaComprobacion": T0, "comprobaciones": 1, "costeUsd": 0.007, "nuevas": [
            {"titulo": "Fibronectina y barrera", "pasaje": "nada", "url": "https://x/1", "doi": None},
            {"titulo": "GFAP y NfL en APOE4", "pasaje": "", "url": "https://x/2", "doi": None},
        ]}
        e["eventos"].append({"id": "ev-1", "investigacionId": "inv-1", "t": T0, "tipo": "vigilancia", "texto": "x", "ruta": "#/investigaciones/inv-1/hipotesis/hip-1"})
        h2 = next(x for x in e["hipotesis"] if x["id"] == "hip-2")
        h2["vigilancia"] = {"ultimaComprobacion": T0, "comprobaciones": 1, "costeUsd": 0.007, "nuevas": [{"titulo": "Otra cosa", "pasaje": "", "url": "https://x/3", "doi": None}]}
        e["eventos"].append({"id": "ev-2", "investigacionId": "inv-1", "t": T0, "tipo": "vigilancia", "texto": "y", "ruta": "#/investigaciones/inv-1/hipotesis/hip-2"})
        return True

    almacen.mutar(sembrar_ruido, "prueba")
    assert vigilancia.depurar(almacen) == 2
    h1 = next(x for x in almacen.estado["hipotesis"] if x["id"] == "hip-1")
    assert [n["titulo"] for n in h1["vigilancia"]["nuevas"]] == ["GFAP y NfL en APOE4"] and h1["vigilancia"]["nuevas"][0]["terminos"] == ["GFAP", "NfL", "APOE4"]
    ev = {x["id"] for x in almacen.estado["eventos"] if x["tipo"] == "vigilancia"}
    assert ev == {"ev-1"}  # hip-1 conserva una novedad; hip-2 se quedó sin ninguna y pierde su evento
    assert vigilancia.depurar(almacen) == 0

