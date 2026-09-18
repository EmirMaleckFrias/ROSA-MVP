"""El banco de objetivos puntúa una corrida sobre el registro, sin modelos; y
los conectores de PubTator 3 con respuestas simuladas iguales a las de la API
real (comprobadas en vivo el 15 de septiembre de 2026)."""
import asyncio

import httpx

from rosa.conectores import pubtator
from rosa.conectores.base import REGISTRO
from rosa.evaluacion import banco


def _estado(obj):
    return {
        "corridas": [{"id": "c1", "investigacionId": "inv", "busqueda": {"consultas": [{"consulta": "(GFAP[tiab] AND NfL[tiab])"}, {"consulta": "lecanemab AND \"Clarity AD\""}, {"consulta": "semaglutide AND evoke"}]},
                      "_fuentes": {"f1": {"titulo": "Lecanemab in Early Alzheimer's Disease"}, "f2": {"titulo": "Biomarker chronology in autosomal dominant Alzheimer"}, "f3": {"titulo": "Donanemab in Early Symptomatic Alzheimer's Disease"}},
                      "gasto": {"llamadas": 320, "usd": 2.1, "exaUsd": 0.09, "segundos": 3600}}],
        "hipotesis": [{"id": "h1", "investigacionId": "inv", "titulo": "El acoplamiento de GFAP con NfL distingue respuesta", "decisionKiller": "descartar_en_contexto"}],
        "iteraciones": [{"corridaId": "c1", "resumen": "ROSA2018 propone que el acoplamiento de GFAP con NfL distingue respuesta; pendiente de validación.", "resumenLlano": {}, "revisionRegistro": {"porRegla": 1, "hallazgos": [{}, {}]}}],
        "investigaciones": [{"id": "inv", "objetivo": obj["objetivo"]}],
    }


def test_banco_carga_objetivos_y_puntua_una_corrida():
    objetivos = banco.cargar_objetivos()
    assert len(objetivos) >= 5 and all(o["clave"] and o["nombres_que_deben_buscarse"] for o in objetivos)
    obj = next(o for o in objetivos if o["clave"] == "biomarcador_beneficio_clinico")
    e = _estado(obj)
    r = banco.puntuar(e, "c1", obj)
    assert r["criterios"]["nombres_buscados"] == 3 / 7 and set(r["detalle"]["nombresBuscados"]) == {"semaglutid", "evoke", "lecanemab"}
    assert r["criterios"]["titulos_encontrados"] == 2 / 3 and r["detalle"]["titulosQueFaltan"] == ["semaglutide & alzheimer"]
    assert abs(r["criterios"]["fuera_de_objetivo"] - 2 / 3) < 1e-9 and r["detalle"]["fuentesFueraDeObjetivo"][0].startswith("Biomarker chronology")
    assert r["criterios"]["estado_honesto"] == 0.0 and r["detalle"]["descartadasComoVivas"] == 1
    assert 0 < r["puntuacion"] < 1 and r["registro"]["hallazgosPorRegla"] == 1 and r["coste"]["exaUsd"] == 0.09
    # El resumen que sí dice "descartada" no penaliza.
    e["iteraciones"][0]["resumen"] = "La hipótesis del acoplamiento de GFAP con NfL distingue respuesta quedó descartada por el Killer."
    assert banco.puntuar(e, "c1", obj)["criterios"]["estado_honesto"] == 1.0
    assert banco.elegir_objetivo(e, "c1", objetivos)["clave"] == "biomarcador_beneficio_clinico"


def test_pubtator_registrados_y_funcionan_con_api_simulada(monkeypatch):
    assert {"pubtator_entidad", "pubtator_relaciones", "pubtator_literatura"} <= set(REGISTRO)

    async def pedir_falso(metodo, url, limitador, **kwargs):
        pet = httpx.Request(metodo, url)
        if url.endswith("/entity/autocomplete/"):
            return httpx.Response(200, json=[{"_id": "@GENE_GFAP", "biotype": "gene", "db_id": "2670", "db": "ncbi_gene", "name": "GFAP"}], request=pet)
        if url.endswith("/relations"):
            assert kwargs["params"]["e1"] == "@GENE_GFAP" and kwargs["params"].get("type") == "associate"
            return httpx.Response(200, json=[{"type": "associate", "source": "@DISEASE_Neoplasms", "target": "@GENE_GFAP", "publications": 754}, {"type": "associate", "source": "@DISEASE_Alzheimer_Disease", "target": "@GENE_GFAP", "publications": 343}], request=pet)
        if url.endswith("/search/"):
            return httpx.Response(200, json={"count": 21338, "results": [{"pmid": 37829140, "title": "Research trends of GFAP", "journal": "Front Aging Neurosci", "date": "2023-09-27T00:00:00Z", "score": 88041.6}]}, request=pet)
        raise AssertionError(url)

    monkeypatch.setattr(pubtator, "pedir", pedir_falso)
    r = asyncio.run(pubtator.pubtator_relaciones("GFAP", "associate"))
    assert r.n == 2 and r.datos["entidad"] == "@GENE_GFAP" and r.datos["relaciones"][0]["publicaciones"] == 754 and r.invariante[0] is True
    assert "@DISEASE_Alzheimer_Disease" in r.ids and "@GENE_GFAP" not in r.ids
    lit = asyncio.run(pubtator.pubtator_literatura("@GENE_GFAP AND @DISEASE_Alzheimer_Disease"))
    assert lit.n == 21338 and lit.ids == ["37829140"] and lit.datos["articulos"][0]["fecha"] == "2023-09-27"
    ent = asyncio.run(pubtator.pubtator_entidad("GFAP", "gene"))
    assert ent.ids == ["@GENE_GFAP"] and ent.invariante[0] is True


def test_la_amplitud_no_penaliza_fuera_de_objetivo_y_se_mide_por_lo_enlazado():
    objetivos = banco.cargar_objetivos()
    obj = next(o for o in objetivos if o["clave"] == "biomarcador_beneficio_clinico")
    e = {
        "corridas": [{"id": "c1", "investigacionId": "inv", "busqueda": {"consultas": [{"consulta": "lecanemab", "modo": "foco"}, {"consulta": "retina", "modo": "amplitud"}]},
                      "_fuentes": {"f1": {"id": "f1", "titulo": "Lecanemab in Early Alzheimer's Disease", "modo": "foco"}, "f2": {"id": "f2", "titulo": "Biomarker chronology in autosomal dominant Alzheimer", "modo": "amplitud"}, "f3": {"id": "f3", "titulo": "Retinal amyloid", "modo": "amplitud"}},
                      "_afirmaciones": [{"id": "af-1", "fuenteId": "f3"}, {"id": "af-2", "fuenteId": "f2"}],
                      "gasto": {}}],
        "hipotesis": [{"id": "h1", "investigacionId": "inv", "titulo": "x", "afirmaciones": [{"afirmacionId": "af-1", "relacion": "apoya"}]}],
        "iteraciones": [], "investigaciones": [{"id": "inv", "objetivo": obj["objetivo"]}],
    }
    r = banco.puntuar(e, "c1", obj)
    # La fuente de amplitud sobre autosómico dominante no cuenta como "fuera de objetivo": solo se miden las de foco.
    assert r["criterios"]["fuera_de_objetivo"] == 1.0
    assert r["amplitud"] == {"consultas": 1, "fuentes": 2, "enlazadas": 1}
