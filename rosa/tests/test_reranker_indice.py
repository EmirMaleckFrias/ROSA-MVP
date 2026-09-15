"""Reranker e índice semántico por el gateway, sin red: la petición que se
manda, el corte del cribado, la caída sin reranker, y la búsqueda por
significado con vectores simulados."""
import asyncio
import hashlib

import httpx
import numpy as np
import pytest

from rosa import indice_semantico as IS
from rosa import reranker as RR
from rosa.bucle import pasos
from rosa.fuentes.base import FuenteNoDisponible


@pytest.fixture
def reranker_falso(monkeypatch):
    monkeypatch.setattr(RR, "MODELO", "cohere/rerank-v3.5")
    monkeypatch.setenv("ROSA_GATEWAY_KEY", "clave-de-prueba")
    llamadas = []

    async def pedir_falso(metodo, url, limitador, **kwargs):
        llamadas.append((url, kwargs))
        docs = kwargs["json"]["documents"]
        # El documento que contiene "GFAP" es el pertinente; los demás bajan.
        resultados = [{"index": i, "relevance_score": 0.9 if "GFAP" in d else 0.1 + i / 100} for i, d in enumerate(docs)]
        return httpx.Response(200, json={"results": resultados}, request=httpx.Request(metodo, url))

    monkeypatch.setattr(RR, "pedir", pedir_falso)
    return llamadas


def test_reordenar_manda_el_modelo_y_ordena_por_pertinencia(reranker_falso):
    assert RR.disponible()
    orden = asyncio.run(RR.reordenar("¿GFAP precede a NfL?", ["Sobre riñón", "Plasma GFAP rises before NfL", "Otra cosa"]))
    assert orden[0] == (1, 0.9) and [i for i, _ in orden] == [1, 2, 0]
    url, kwargs = reranker_falso[0]
    assert url.endswith("/v2/rerank") and kwargs["json"]["model"] == "cohere/rerank-v3.5"
    assert kwargs["headers"]["Authorization"] == "Bearer clave-de-prueba"


def test_cortar_con_reranker_deja_al_modelo_los_mejores_y_registra_los_demas(reranker_falso):
    articulos = [{"titulo": f"Artículo {i}", "resumen": "riñón"} for i in range(6)] + [{"titulo": "Plasma GFAP precede NfL", "resumen": ""}]
    dentro, fuera = asyncio.run(pasos.cortar_con_reranker("¿GFAP precede a NfL?", articulos, None, maximo=3))
    assert dentro[0]["titulo"] == "Plasma GFAP precede NfL" and len(dentro) == 3 and len(fuera) == 4
    assert all(s < 0.5 for _, s in fuera)
    # Con pocos candidatos no se llama al reranker.
    pocos, nada = asyncio.run(pasos.cortar_con_reranker("q", articulos[:2], None, maximo=3))
    assert pocos == articulos[:2] and nada == [] and len(reranker_falso) == 1


def test_sin_reranker_o_caido_todos_pasan_al_modelo(monkeypatch):
    monkeypatch.setattr(RR, "MODELO", "")
    articulos = [{"titulo": f"A{i}", "resumen": ""} for i in range(20)]
    assert asyncio.run(pasos.cortar_con_reranker("q", articulos, None, maximo=5)) == (articulos, [])
    monkeypatch.setattr(RR, "MODELO", "cohere/rerank-v3.5")
    monkeypatch.setenv("ROSA_GATEWAY_KEY", "x")

    async def caido(*a, **k):
        raise FuenteNoDisponible("gateway 503")

    monkeypatch.setattr(RR, "pedir", caido)
    assert asyncio.run(pasos.cortar_con_reranker("q", articulos, None, maximo=5)) == (articulos, [])


def _vector(texto: str) -> list[float]:
    # Vectores deterministas: textos con la misma palabra clave quedan cerca.
    base = np.zeros(8, dtype=np.float32)
    for palabra in texto.lower().replace(".", " ").split():
        h = int(hashlib.md5(palabra.encode()).hexdigest(), 16)
        base[h % 8] += 1.0
    return base.tolist()


@pytest.fixture
def indice_falso(monkeypatch):
    monkeypatch.setattr(IS, "MODELO", "openai/text-embedding-3-small")
    monkeypatch.setenv("ROSA_GATEWAY_KEY", "x")
    llamadas = []

    async def incrustar_falso(textos):
        llamadas.append(list(textos))
        return [_vector(t) for t in textos], sum(len(t.split()) for t in textos)

    monkeypatch.setattr(IS, "incrustar", incrustar_falso)
    return llamadas


def test_indice_incrusta_solo_lo_nuevo_y_busca_por_similitud(indice_falso):
    ind = IS.Indice(":memory:")
    items = [
        {"id": "hecho:1", "tipo": "hecho", "investigacionId": "inv", "texto": "GFAP sube antes que NfL"},
        {"id": "hecho:2", "tipo": "hecho", "investigacionId": "inv", "texto": "la barrera hematoencefálica pierde integridad"},
        {"id": "hipotesis:1", "tipo": "hipotesis", "investigacionId": "otra", "texto": "GFAP precede a NfL en APOE4"},
    ]
    assert asyncio.run(ind.indexar(items)) == 3 and ind.total() == 3
    assert asyncio.run(ind.indexar(items)) == 0 and len(indice_falso) == 1  # nada cambió: sin llamada
    items[0]["texto"] = "GFAP sube antes que NfL (revisado)"
    assert asyncio.run(ind.indexar(items)) == 1
    r = asyncio.run(ind.buscar("GFAP antes que NfL", k=2))
    assert r[0]["id"] in ("hecho:1", "hipotesis:1") and r[0]["similitud"] > 0.5
    solo_inv = asyncio.run(ind.buscar("GFAP antes que NfL", k=5, investigacion_id="inv"))
    assert all(x["investigacionId"] == "inv" for x in solo_inv)
    # Lo que desaparece del estado se retira del índice.
    assert asyncio.run(ind.indexar(items[:2])) == 0 and ind.total() == 2
    ind.cerrar()


def test_hipotesis_parecidas_encuentra_la_descartada(indice_falso, tmp_path):
    from rosa.estado.almacen import Almacen

    al = Almacen(tmp_path / "rosa.db")

    def sembrar(e):
        e["hipotesis"] += [
            {"id": "h1", "investigacionId": "inv", "titulo": "GFAP precede a NfL", "enunciado": "GFAP sube antes que NfL en APOE4", "estado": "descartada", "decisionKiller": "descartar"},
            {"id": "h2", "investigacionId": "inv", "titulo": "Otra cosa", "enunciado": "riñón y creatinina", "estado": "propuesta"},
            {"id": "h3", "investigacionId": "inv", "titulo": "GFAP antes que NfL en portadores", "enunciado": "GFAP sube antes que NfL en APOE4 amiloide", "estado": "propuesta"},
        ]
        return True

    al.mutar(sembrar, "prueba")
    parecidas = asyncio.run(IS.hipotesis_parecidas(al, al.estado["hipotesis"][2], umbral=0.6))
    assert parecidas and parecidas[0]["id"] == "h1" and parecidas[0]["estado"] == "descartada" and parecidas[0]["decisionKiller"] == "descartar"
    assert all(x["id"] != "h3" for x in parecidas)
    assert IS.resumen(al)["vectores"] >= 3
    al.cerrar()


def test_sin_clave_el_indice_no_hace_nada(monkeypatch, tmp_path):
    monkeypatch.setattr(IS, "MODELO", "")
    from rosa.estado.almacen import Almacen

    al = Almacen(tmp_path / "rosa.db")
    assert asyncio.run(IS.indexar_estado(al)) == 0 and IS.resumen(al)["disponible"] is False
    al.cerrar()
