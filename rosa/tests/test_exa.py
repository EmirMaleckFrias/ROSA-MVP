"""Exa como fuente y conector: mapeo de resultados, clave solo en cabecera,
comportamiento sin clave y desvío de consultas. Sin red."""
import asyncio
import importlib

import httpx
import pytest

from rosa import config
from rosa.fuentes import exa
from rosa.fuentes.base import FuenteNoDisponible

RESPUESTA = {
    "requestId": "r1",
    "costDollars": {"total": 0.008},
    "results": [
        {
            "id": "https://www.nature.com/articles/s41591-025-01234-5",
            "url": "https://www.nature.com/articles/s41591-025-01234-5",
            "title": "Plasma GFAP rises before NfL in APOE e4 carriers",
            "publishedDate": "2025-06-01T00:00:00.000Z",
            "author": "Ana Pérez; Luis Gómez; Marta Ruiz; Juan Díaz",
            "score": 0.61,
            "highlights": ["GFAP increased 3.2 years before NfL.", "Effect was restricted to amyloid-positive carriers."],
        },
        {
            "url": "https://doi.org/10.1002/alz.13579",
            "title": "Astrocyte reactivity and neuroaxonal injury",
            "publishedDate": "2024-11-12",
            "author": ["Chen W", "Smith J"],
            "highlights": [],
            "text": "Full text snippet about astrocytes and axons.",
        },
        {"url": "https://pubmed.ncbi.nlm.nih.gov/39912345/", "title": "A PubMed record", "publishedDate": "2026-01-05"},
        {"url": "https://www.biorxiv.org/content/10.1101/2026.02.01.123456v1.full", "title": "A preprint", "publishedDate": "2026-02-01"},
        {"title": "sin url, se ignora"},
    ],
}


@pytest.fixture
def con_clave(monkeypatch):
    monkeypatch.setattr(config, "CLAVE_EXA", "exa_clave_de_prueba")
    llamadas = []

    async def pedir_falso(metodo, url, limitador, **kwargs):
        llamadas.append((metodo, url, kwargs))
        return httpx.Response(200, json=RESPUESTA, request=httpx.Request(metodo, url))

    monkeypatch.setattr(exa, "pedir", pedir_falso)
    return llamadas


def test_buscar_mapea_a_la_forma_de_las_otras_bases(con_clave):
    articulos, n, coste = asyncio.run(exa.buscar("¿GFAP sube antes que NfL en portadores de APOE4?", maximo=10, desde_anio=2023))
    assert n == 4 and coste == 0.008
    a = articulos[0]
    assert a["doi"] == "10.1038/s41591-025-01234-5" and a["anio"] == 2025 and a["referencia"] == "Pérez et al., 2025"
    assert "3.2 years" in a["resumen"] and a["titulo"].startswith("Plasma GFAP")
    b = articulos[1]
    assert b["doi"] == "10.1002/alz.13579" and b["referencia"] == "Chen y Smith, 2024" and b["resumen"].startswith("Full text")
    assert articulos[2]["pmid"] == "39912345" and articulos[2]["doi"] is None
    assert articulos[3]["preprint"] is True and articulos[3]["doi"] == "10.1101/2026.02.01.123456v1"
    metodo, url, kwargs = con_clave[0]
    assert metodo == "POST" and url.endswith("/search")
    assert kwargs["json"]["category"] == "publication" and kwargs["json"]["startPublishedDate"].startswith("2023-01-01")
    assert kwargs["json"]["type"] == "auto" and "deep" not in kwargs["json"]["type"]


def test_la_clave_va_solo_en_la_cabecera(con_clave):
    asyncio.run(exa.buscar("pregunta", maximo=3))
    _, _, kwargs = con_clave[0]
    assert kwargs["headers"]["x-api-key"] == "exa_clave_de_prueba"
    assert "exa_clave_de_prueba" not in str(kwargs["json"])


def test_sin_clave_no_hay_resultado_sino_no_pude_comprobar(monkeypatch):
    monkeypatch.setattr(config, "CLAVE_EXA", "")
    assert not exa.disponible()
    with pytest.raises(FuenteNoDisponible):
        asyncio.run(exa.buscar("pregunta"))


def test_similares_y_contenidos_usan_sus_endpoints(con_clave):
    parecidos, _ = asyncio.run(exa.similares("https://doi.org/10.1002/alz.13579", maximo=4))
    assert len(parecidos) == 4 and con_clave[-1][1].endswith("/findSimilar")
    textos, _ = asyncio.run(exa.contenidos(["https://doi.org/10.1002/alz.13579"]))
    assert con_clave[-1][1].endswith("/contents") and con_clave[-1][2]["json"]["text"]["maxCharacters"] == 20000
    assert isinstance(textos, list)


def test_conectores_inertes_sin_clave_y_vivos_con_ella(monkeypatch):
    import rosa.conectores.exa as modulo
    from rosa.conectores.base import REGISTRO

    monkeypatch.setattr(config, "CLAVE_EXA", "")
    importlib.reload(modulo)
    assert REGISTRO["exa_publicaciones"].estado == "requiere_cuenta" and "ROSA_EXA_KEY" in REGISTRO["exa_publicaciones"].motivo
    monkeypatch.setattr(config, "CLAVE_EXA", "x")
    importlib.reload(modulo)
    assert REGISTRO["exa_publicaciones"].estado == "disponible" and REGISTRO["exa_publicaciones"].clave == "si"
    monkeypatch.setattr(config, "CLAVE_EXA", "")
    importlib.reload(modulo)


def test_el_plan_puede_elegir_exa_solo_con_clave_y_si_no_se_desvia(monkeypatch):
    from rosa.bucle import pasos

    monkeypatch.setattr(config, "CLAVE_EXA", "")
    assert pasos.bases_disponibles() == ["pubmed", "europepmc", "preprints"]
    desviada = pasos.base_efectiva({"base": "exa", "consulta": "¿GFAP precede a NfL?", "tema": "orden"})
    assert desviada["base"] == "europepmc" and desviada["_desviada_de"] == "exa"
    assert pasos.base_efectiva({"base": "pubmed", "consulta": "gfap[tiab]", "tema": "x"})["base"] == "pubmed"
    monkeypatch.setattr(config, "CLAVE_EXA", "x")
    assert "exa" in pasos.bases_disponibles()
    assert pasos.base_efectiva({"base": "exa", "consulta": "q", "tema": "t"})["base"] == "exa"
    assert pasos.NOMBRES_BASE["exa"].startswith("Exa")
