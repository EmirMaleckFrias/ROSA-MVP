"""Tanda 1 de la revisión del 17 de septiembre de 2026, grupo B1 (pasos de
literatura): la novedad no declara "sin precedente" sin haber evaluado nada
(S-02), la consulta a OpenAlex sale en inglés y `terminos_clave` respeta las
tildes (S-02), el verificador recibe el id de la fuente y la extracción
comprueba que la cita resuelve (S-03, S-04), la referencia corta se
desambigua al registrar (S-04), cada afirmación dice si viene de una sección
de fondo (M-10), la cola de hipótesis se cuenta por regla (S-16), la dirección
de la evidencia sale de las afirmaciones (M-07) y las firmas llevan las
entradas nuevas (S-16, M-06). Sin red ni modelos: todo simulado."""

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from rosa import verificador as V
from rosa.bucle import contexto as T
from rosa.bucle import pasos as PASOS
from rosa.bucle.pasos import Ctx
from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen
from rosa.fuentes import base as FB
from rosa.fuentes import clinicaltrials, exa, openalex, opentargets
from rosa.fuentes.base import FuenteNoDisponible


# ---------------------------------------------------------------------------
# Arnés: un almacén temporal con una investigación, una corrida y una iteración
# ---------------------------------------------------------------------------


def _preparar(titulo="BACE1 aporta información pronóstica adicional a GFAP en portadores de APOE ε4", biomarcador="p-tau181 en plasma"):
    al = Almacen(Path(tempfile.mkdtemp()) / "t.db")

    def fn(e):
        inv_id = A.crear_investigacion(e, {"titulo": "GFAP", "objetivo": "Orden de alteración de GFAP y NfL", "condicionParada": "3 iteraciones"}, 1000)
        c = P.nueva_corrida(inv_id, 1, 1000)
        c["estado"] = "en_marcha"
        e["corridas"].append(c)
        it = P.nueva_iteracion(c["id"], 1, 1000, [])
        e["iteraciones"].append(it)
        h = P.nueva_hipotesis(inv_id, 1, 1000, titulo=titulo, enunciado="En portadores de APOE ε4 con amiloide positivo, BACE1 en plasma añade valor pronóstico a GFAP", mecanismo="m", comprobacion={"biomarcador": biomarcador, "cohorte": "BioFINDER", "diseno": "cohorte"}, afirmaciones=[])
        e["hipotesis"].append(h)
        e["_ids"] = {"inv": inv_id, "cor": c["id"], "it": it["id"], "hip": h["id"]}
        return True

    al.mutar(fn, "preparar")
    ids = al.estado.pop("_ids")
    programas = SimpleNamespace(relevancia="relevancia", extraer="extraer", juzgar="juzgar")
    modelos = SimpleNamespace(cerebro=SimpleNamespace(model="sim"), juez=SimpleNamespace(model="sim-juez"), volumen=SimpleNamespace(model="sim-vol"))
    return al, ids, Ctx(al, programas, modelos, ids["cor"], ids["inv"], ids["it"], 1)


def _hip(al, ids):
    return next(h for h in al.estado["hipotesis"] if h["id"] == ids["hip"])


def _sin_red(monkeypatch, obras=None, total=0, relevancia=None, exa_disponible=False):
    """Deja el paso de novedad sin red: OpenAlex devuelve lo que se le diga,
    Open Targets y ClinicalTrials.gov no responden, los conectores no hacen
    nada, y el programa de relevancia responde con `relevancia` (una función
    de los kwargs) o lanza si es None."""
    consultas = []

    async def buscar_oa(texto, maximo=25, desde_anio=None):
        consultas.append(texto)
        return list(obras or []), total, 0.0

    async def no_responde(*a, **k):
        raise FuenteNoDisponible("simulado: sin red")

    async def conectores(ctx, h, genes, novedad, pista):
        return []

    async def llamar(self, rol, programa, **kw):
        if programa == "relevancia":
            if relevancia is None:
                raise RuntimeError("modelo de relevancia caído (simulado)")
            return SimpleNamespace(puntuacion=relevancia(kw), motivo="simulado")
        raise RuntimeError(f"programa simulado sin respuesta: {programa}")

    monkeypatch.setattr(openalex, "buscar", buscar_oa)
    monkeypatch.setattr(opentargets, "asociacion_alzheimer", no_responde)
    monkeypatch.setattr(clinicaltrials, "buscar", no_responde)
    monkeypatch.setattr(exa, "disponible", lambda: exa_disponible)
    monkeypatch.setattr(PASOS, "_novedad_por_conectores", conectores)
    monkeypatch.setattr(Ctx, "llamar", llamar)  # simulación local; el módulo real llama por el gateway
    return consultas


def _obra(titulo, ref="Kim et al., 2025", doi="10.1/x"):
    return {"titulo": titulo, "resumen": "r", "referencia": ref, "doi": doi}


def _paso(al, ids):
    it = next(i for i in al.estado["iteraciones"] if i["id"] == ids["it"])
    paso = {"id": "paso-nov", "tipo": "novedad", "titulo": "Novedad", "estado": "en_curso", "detalle": "", "indicacionHumana": False, "motivoFallo": None}
    al.mutar(lambda e: next(i for i in e["iteraciones"] if i["id"] == ids["it"])["plan"].append(paso) or True, "plan")
    return paso


def _pista_textos(al, ids):
    it = next(i for i in al.estado["iteraciones"] if i["id"] == ids["it"])
    textos = []
    for p in it["pistas"]:
        textos.append(p.get("titulo", ""))
        for linea in p.get("transcripcion", []) or []:
            textos.append(str(linea.get("texto") or ""))
        textos.append(p.get("resumen") or "")
    return "\n".join(textos)


# ---------------------------------------------------------------------------
# S-02: novedad
# ---------------------------------------------------------------------------


def test_openalex_a_cero_obras_es_no_comprobado_y_no_sin_precedente(monkeypatch):
    al, ids, ctx = _preparar()
    consultas = _sin_red(monkeypatch, obras=[], total=0, relevancia=lambda kw: 2)
    asyncio.run(PASOS.paso_novedad(ctx, _paso(al, ids)))
    prec = _hip(al, ids)["novedad"]["precedente"]
    assert prec["estado"] == "no_comprobado", prec
    assert prec["detalle"].startswith("No comprobado"), prec
    assert "no devolvió obras" in prec["detalle"]
    assert consultas, "tenía que haber consultado OpenAlex"


def test_modelo_de_relevancia_caido_en_todas_es_no_comprobado_y_se_anota(monkeypatch):
    al, ids, ctx = _preparar()
    _sin_red(monkeypatch, obras=[_obra("GFAP and BACE1"), _obra("NfL", "Xie, 2026", "10.1/y")], total=2, relevancia=None)
    asyncio.run(PASOS.paso_novedad(ctx, _paso(al, ids)))
    prec = _hip(al, ids)["novedad"]["precedente"]
    assert prec["estado"] == "no_comprobado"
    assert "no respondió en 2 de 2" in prec["detalle"]
    # El fallo del modelo ya no se traga en silencio: queda en la pista.
    assert "Relevancia falló" in _pista_textos(al, ids)


def test_con_obras_evaluadas_y_ninguna_parecida_si_es_sin_precedente(monkeypatch):
    al, ids, ctx = _preparar()
    _sin_red(monkeypatch, obras=[_obra("GFAP and BACE1")], total=37, relevancia=lambda kw: 2)
    asyncio.run(PASOS.paso_novedad(ctx, _paso(al, ids)))
    prec = _hip(al, ids)["novedad"]["precedente"]
    assert prec["estado"] == "sin_precedente"
    assert "1 obras evaluadas de 37" in prec["detalle"]


def test_precedente_alto_sigue_siendo_ya_publicado(monkeypatch):
    al, ids, ctx = _preparar()
    _sin_red(monkeypatch, obras=[_obra("BACE1 adds prognostic value to GFAP")], total=1, relevancia=lambda kw: 9)
    asyncio.run(PASOS.paso_novedad(ctx, _paso(al, ids)))
    assert _hip(al, ids)["novedad"]["precedente"]["estado"] == "ya_publicado"


def test_la_consulta_va_en_ingles_con_siglas_y_sin_palabras_cortadas(monkeypatch):
    al, ids, ctx = _preparar()
    consultas = _sin_red(monkeypatch, obras=[], total=0, relevancia=lambda kw: 0)
    asyncio.run(PASOS.paso_novedad(ctx, _paso(al, ids)))
    q = consultas[0]
    assert "informaci" not in q and "pronóstica" not in q and "portadores" not in q, q
    for sigla in ("BACE1", "GFAP", "p-tau181"):
        assert sigla in q, (sigla, q)
    assert len(q.split()) <= 3, q


def test_sin_terminos_en_ingles_no_consulta_y_queda_no_comprobado(monkeypatch):
    al, ids, ctx = _preparar(titulo="Precedencia de la anormalidad plasmática sobre la cortical", biomarcador="proteína en plasma")
    al.mutar(lambda e: _hip(al, ids).update(enunciado="La anormalidad plasmática precede a la cortical") or True, "enunciado")
    consultas = _sin_red(monkeypatch, obras=[_obra("x")], total=1, relevancia=lambda kw: 9)
    asyncio.run(PASOS.paso_novedad(ctx, _paso(al, ids)))
    prec = _hip(al, ids)["novedad"]["precedente"]
    assert consultas == [], "sin términos buscables no se consulta OpenAlex"
    assert prec["estado"] == "no_comprobado" and "términos buscables" in prec["detalle"]
    # ClinicalTrials.gov tampoco se consulta con palabras en castellano.
    assert _hip(al, ids)["novedad"]["ensayos"]["estado"] == "no_comprobado"


def test_con_un_solo_termino_en_ingles_no_se_consulta_openalex(monkeypatch):
    al, ids, ctx = _preparar(titulo="La normalización de P-tau181 predice el beneficio clínico", biomarcador="P-tau181 en plasma")
    al.mutar(lambda e: _hip(al, ids).update(enunciado="La normalización de P-tau181 predice el beneficio") or True, "enunciado")
    consultas = _sin_red(monkeypatch, obras=[_obra("x")], total=12000, relevancia=lambda kw: 9)
    asyncio.run(PASOS.paso_novedad(ctx, _paso(al, ids)))
    assert consultas == []
    prec = _hip(al, ids)["novedad"]["precedente"]
    assert prec["estado"] == "no_comprobado" and "términos buscables" in prec["detalle"]
    assert "tiene 1" in _pista_textos(al, ids)
    # ClinicalTrials.gov sí se consulta con un término (aquí no responde: no comprobado, no "sin ensayo").
    assert _hip(al, ids)["novedad"]["ensayos"]["estado"] == "no_comprobado" and "no respondio" in _hip(al, ids)["novedad"]["ensayos"]["detalle"].lower().replace("ó", "o")


def test_lo_no_comprobado_y_lo_de_cero_obras_vuelve_a_intentarse():
    h = P.nueva_hipotesis("inv", 1, 1000, titulo="t", enunciado="e", mecanismo="m", comprobacion={"biomarcador": "GFAP", "cohorte": "c", "diseno": "d"}, afirmaciones=[])
    assert PASOS.novedad_pendiente(h)  # recién nacida: "No comprobado todavía"
    h["novedad"]["precedente"] = {"estado": "no_comprobado", "detalle": "La consulta no devolvió obras"}
    h["novedad"]["genetica"]["estado"] = "sin_evidencia"
    assert PASOS.novedad_pendiente(h)  # por estado, aunque el detalle no empiece por "No comprobado"
    h["novedad"]["precedente"] = {"estado": "sin_precedente", "detalle": "Sin precedente claro entre 0 obras que casan con: informaci GFAP"}
    assert PASOS.novedad_pendiente(h)  # registro antiguo: nunca evaluó nada
    h["novedad"]["precedente"] = {"estado": "sin_precedente", "detalle": "Sin precedente claro: 3 obras evaluadas de 40"}
    assert not PASOS.novedad_pendiente(h)
    # Registros rotos o antiguos no tumban el filtro.
    assert PASOS.novedad_pendiente({"novedad": {}})
    # Un "sin precedente" sin detalle (registro viejo) no se sabe si evaluó algo: la regla solo repesca "entre 0 obras".
    assert PASOS.novedad_pendiente({"novedad": {"precedente": {"estado": "sin_precedente"}}}) is False
    assert PASOS.novedad_pendiente({})


def test_novedad_exa_dominios_cero_documentos_y_modelo_caido(monkeypatch):
    al, ids, ctx = _preparar()
    h = _hip(al, ids)
    monkeypatch.setattr(exa, "disponible", lambda: True)

    async def buscar_vacio(*a, **k):
        return [], 0, 0.0

    monkeypatch.setattr(exa, "buscar", buscar_vacio)
    pista = ctx.pista(None, "novedad", "t", "Exa")
    novedad = {}
    asyncio.run(PASOS._novedad_exa_dominios(ctx, h, pista, novedad, "patentes", ["patents.google.com"], "¿Alguien lo patentó?", ("patente_relacionada", "parcial", "sin_patente"), "patentes"))
    assert novedad["patentes"]["estado"] == "no_comprobado" and novedad["patentes"]["detalle"].startswith("No comprobado")
    assert "no devolvió documentos" in novedad["patentes"]["detalle"], novedad["patentes"]

    async def buscar_uno(*a, **k):
        return [{"titulo": "Patent on GFAP", "resumen": "r", "url": "u", "fecha": "2020"}], 1, 0.0

    async def llamar(self, rol, programa, **kw):
        raise RuntimeError("caído")

    monkeypatch.setattr(exa, "buscar", buscar_uno)
    monkeypatch.setattr(Ctx, "llamar", llamar)  # simulación local
    asyncio.run(PASOS._novedad_exa_dominios(ctx, h, pista, novedad, "patentes", ["patents.google.com"], "¿Alguien lo patentó?", ("patente_relacionada", "parcial", "sin_patente"), "patentes"))
    assert novedad["patentes"]["estado"] == "no_comprobado" and "1 de 1" in novedad["patentes"]["detalle"]
    pista.cerrar("fin")


# ---------------------------------------------------------------------------
# S-02: terminos_clave y terminos_para_ingles
# ---------------------------------------------------------------------------


def test_terminos_clave_no_corta_en_la_tilde():
    t = T.terminos_clave("BACE1 aporta información pronóstica adicional a GFAP")
    assert "información" in t and "informaci" not in t
    assert t[0] == "BACE1" and "GFAP" in t
    assert "señalización" in T.terminos_clave("La señalización astrocitaria")


def test_terminos_para_ingles_toma_siglas_genes_y_cifras_de_entidades_tarjeta_y_biomarcador():
    h = {"titulo": "Precedencia de GFAP sobre NfL en portadores de APOE ε4", "tarjeta": {"diana": "BACE1"}, "comprobacion": {"biomarcador": "p-tau181 en plasma"}}
    assert T.terminos_para_ingles(h) == ["BACE1", "p-tau181", "GFAP"]
    assert T.terminos_para_ingles(h, maximo=4) == ["BACE1", "p-tau181", "GFAP", "NfL"]
    assert T.terminos_para_ingles({"_entidades": ["GFAP", "NfL", "APOE4"], "titulo": "x"}) == ["GFAP", "NfL", "APOE4"]
    assert T.terminos_para_ingles({"titulo": "Precedencia de la anormalidad plasmática"}) == []
    # Los alias de HGNC de las entidades canónicas (FLJ45472, DDPAC) no entran: con ellos OpenAlex vuelve a dar 0.
    assert T.terminos_para_ingles({"titulo": "Reducción de GFAP", "entidades": [{"id": "HGNC:4235", "etiqueta": "GFAP", "alias": ["FLJ45472"]}, {"id": "HGNC:6893", "etiqueta": "MAPT", "alias": ["DDPAC", "FLJ31424", "FTDP-17"]}]}) == ["GFAP", "MAPT"]
    # Castellano pegado a una sigla, siglas castellanas y guiones tipográficos.
    assert T.terminos_para_ingles({"titulo": "Especificidad amiloide-PET de la brecha GFAP–NfL en LCR"}) == ["PET", "GFAP", "NfL"]
    assert T.terminos_para_ingles({"titulo": "GFAP en LCR y DCL"}) == ["GFAP", "CSF", "MCI"]
    assert T.terminos_para_ingles({"titulo": "Tau-PET basal y p-tau181"}) == ["Tau-PET", "p-tau181"]
    # Registros rotos y None no tumban nada.
    assert T.terminos_para_ingles({"tarjeta": None, "comprobacion": "raro", "_entidades": [1, None], "entidades": [{"id": "x"}, "y"]}) == []
    assert T.terminos_para_ingles(None) == []


# ---------------------------------------------------------------------------
# S-03 y S-04: fuenteId al verificador, cita comprobada al extraer, referencia única
# ---------------------------------------------------------------------------


def test_verificar_afirmaciones_pasa_el_fuente_id_al_determinista(monkeypatch):
    al, ids, ctx = _preparar()
    fid = PASOS._registrar_fuente(ctx, {"referencia": "Sin autor", "titulo": "A", "url": "https://a", "tipos": [], "resumen": "GFAP sube."}, "articulo", [{"localizador": "resumen", "texto": "GFAP sube.", "encabezado": "A"}], 8, None, "limpio", 1, "q")
    recibidos = []

    def comprobar(texto, cita, fragmento_citado, fragmentos, alcance, excluir=None, fuente_id=None):
        recibidos.append(fuente_id)
        return V.Resultado("sostenida", "simulado")

    monkeypatch.setattr(V, "comprobar_determinista", comprobar)
    a = {"texto": "GFAP sube.", "cita": "[Sin autor, resumen]", "fragmento": "GFAP sube.", "veredicto": "sin_verificar", "fuenteId": fid, "localizador": "resumen"}
    r = asyncio.run(PASOS.verificar_afirmaciones(ctx, [a], None, "GFAP"))
    assert recibidos == [fid] and r == {"sostenida": 1}


def test_verificar_afirmaciones_aguanta_un_verificador_sin_el_parametro(monkeypatch):
    al, ids, ctx = _preparar()

    def comprobar_viejo(texto, cita, fragmento_citado, fragmentos, alcance, excluir=None):
        return V.Resultado("sostenida", "viejo")

    monkeypatch.setattr(V, "comprobar_determinista", comprobar_viejo)
    a = {"texto": "x", "cita": "[A, resumen]", "veredicto": "sin_verificar", "fuenteId": "f1"}
    assert asyncio.run(PASOS.verificar_afirmaciones(ctx, [a], None, "GFAP")) == {"sostenida": 1}


def test_registrar_fuente_desambigua_la_referencia_repetida_y_no_la_misma_fuente(monkeypatch):
    al, ids, ctx = _preparar()
    monkeypatch.delattr(FB, "desambiguar_referencia", raising=False)  # respaldo local
    f1 = PASOS._registrar_fuente(ctx, {"referencia": "Bhagunde et al., 2026", "titulo": "Modelo farmacocinético de donanemab en plasma", "doi": "10.1/a", "tipos": [], "resumen": "a"}, "articulo", [{"localizador": "sección Results", "texto": "a" * 100, "encabezado": "Results"}], 8, None, "limpio", 1, "q")
    f2 = PASOS._registrar_fuente(ctx, {"referencia": "Bhagunde et al., 2026", "titulo": "Otro artículo distinto sobre ensayos de anticuerpos", "doi": "10.1/b", "tipos": [], "resumen": "b"}, "articulo", [{"localizador": "sección Results", "texto": "b" * 100, "encabezado": "Results"}], 8, None, "limpio", 1, "q")
    f3 = PASOS._registrar_fuente(ctx, {"referencia": "Bhagunde et al., 2026", "titulo": "Modelo farmacocinético de donanemab en plasma", "doi": "10.1/a", "tipos": [], "resumen": "a"}, "articulo", [], 8, None, "limpio", 1, "q2")
    fuentes = ctx.fuentes()
    assert f1 != f2 and f3 == f1
    assert fuentes[f1]["referencia"] == "Bhagunde et al., 2026"
    assert fuentes[f2]["referencia"] == "Bhagunde et al., 2026b"
    # Dos "Sin autor" sin año: ordinal.
    s1 = PASOS._registrar_fuente(ctx, {"referencia": "Sin autor", "titulo": "Página uno de la FDA sobre donanemab", "url": "https://u1", "tipos": [], "resumen": "u"}, "articulo", [], 8, None, "limpio", 1, "q")
    s2 = PASOS._registrar_fuente(ctx, {"referencia": "Sin autor", "titulo": "Página dos de ALZFORUM sobre posdinemab", "url": "https://u2", "tipos": [], "resumen": "v"}, "articulo", [], 8, None, "limpio", 1, "q")
    assert fuentes[s1]["referencia"] == "Sin autor" and fuentes[s2]["referencia"] == "Sin autor (2)"
    # Con el verificador real, cada cita resuelve a su propio fragmento.
    frags = ctx.fragmentos_verificador()
    assert V.resolver_cita("[Bhagunde et al., 2026b, sección Results]", frags).fuente_id == f2
    assert V.resolver_cita("[Bhagunde et al., 2026, sección Results]", frags).fuente_id == f1


def test_registrar_fuente_usa_la_desambiguacion_del_grupo_a_si_existe(monkeypatch):
    al, ids, ctx = _preparar()
    monkeypatch.setattr(FB, "desambiguar_referencia", lambda ref, existentes: f"{ref} [A]" if ref in existentes else ref, raising=False)
    f1 = PASOS._registrar_fuente(ctx, {"referencia": "Kim, 2025", "titulo": "Primer artículo de Kim sobre GFAP", "doi": "10.1/k1", "tipos": [], "resumen": "a"}, "articulo", [], 8, None, "limpio", 1, "q")
    f2 = PASOS._registrar_fuente(ctx, {"referencia": "Kim, 2025", "titulo": "Segundo artículo de Kim sobre NfL", "doi": "10.1/k2", "tipos": [], "resumen": "b"}, "articulo", [], 8, None, "limpio", 1, "q")
    assert ctx.fuentes()[f1]["referencia"] == "Kim, 2025" and ctx.fuentes()[f2]["referencia"] == "Kim, 2025 [A]"


def _extraer_con(monkeypatch, al, ids, ctx, fragmentos, texto_fuente="Kim et al., 2025"):
    fid = PASOS._registrar_fuente(ctx, {"referencia": texto_fuente, "titulo": "T", "doi": "10.1/t", "tipos": [], "resumen": ""}, "articulo", fragmentos, 8, None, "limpio", 1, "q")

    async def llamar(self, rol, programa, **kw):
        assert programa == "extraer"
        frag = kw["fragmento"]
        return SimpleNamespace(afirmaciones=[SimpleNamespace(texto="GFAP sube en la fase preclínica", fragmento="GFAP sube", tipo="dato", tema="GFAP", cohorte="", nivel_medicion="resultado_analisis", n="195", comparador="controles", efecto="sube", incertidumbre="")])

    monkeypatch.setattr(Ctx, "llamar", llamar)  # simulación local
    it = next(i for i in al.estado["iteraciones"] if i["id"] == ids["it"])
    paso = {"id": "paso-ext", "tipo": "extraccion", "titulo": "Extraer", "estado": "en_curso", "detalle": "", "indicacionHumana": False, "motivoFallo": None}
    al.mutar(lambda e: next(i for i in e["iteraciones"] if i["id"] == ids["it"])["plan"].append(paso) or True, "plan")
    asyncio.run(PASOS.paso_extraccion(ctx, paso))
    return fid, ctx.afirmaciones()


def test_de_fondo_se_marca_por_seccion(monkeypatch):
    al, ids, ctx = _preparar()
    frs = [
        {"localizador": "sección Introduction", "texto": "GFAP sube " * 20, "encabezado": "Introduction"},
        {"localizador": "sección Results", "texto": "GFAP sube " * 20, "encabezado": "Results"},
        {"localizador": "sección Discusión", "texto": "GFAP sube " * 20, "encabezado": "Discusión"},
        {"localizador": "sección Results and discussion", "texto": "GFAP sube " * 20, "encabezado": "Results and discussion"},
        {"localizador": "pág. 3", "texto": "GFAP sube " * 20, "encabezado": "T"},
        {"localizador": "sección 1. Background", "texto": "GFAP sube " * 20, "encabezado": "1. Background"},
    ]
    _, afs = _extraer_con(monkeypatch, al, ids, ctx, frs)
    por_loc = {a["localizador"]: a["deFondo"] for a in afs}
    assert por_loc == {"sección Introduction": True, "sección Results": False, "sección Discusión": True, "sección Results and discussion": False, "pág. 3": False, "sección 1. Background": True}, por_loc
    assert all(a["veredicto"] == "sin_verificar" for a in afs)
    assert PASOS.es_de_fondo(None) is False and PASOS.es_de_fondo("", None) is False


def test_la_extraccion_marca_el_localizador_no_reconocido_con_su_motivo(monkeypatch):
    al, ids, ctx = _preparar()
    monkeypatch.setattr(V, "resolver_cita", lambda cita, fragmentos, **k: None)
    _, afs = _extraer_con(monkeypatch, al, ids, ctx, [{"localizador": "texto web, parte 2", "texto": "GFAP sube " * 20, "encabezado": "T"}])
    assert len(afs) == 1
    assert afs[0]["veredicto"] == "cita_no_resuelve"
    assert "Localizador no reconocido" in afs[0]["motivo"] and "texto web, parte 2" in afs[0]["motivo"]
    assert afs[0]["cita"] == "[Kim et al., 2025, texto web, parte 2]" and afs[0]["fuenteId"]
    assert "no reconoce el localizador" in _pista_textos(al, ids)


def test_la_extraccion_pasa_el_fuente_id_a_resolver_cita_si_lo_admite(monkeypatch):
    al, ids, ctx = _preparar()
    vistos = []

    def resolver(cita, fragmentos, fuente_id=None):
        vistos.append(fuente_id)
        return fragmentos[0]

    monkeypatch.setattr(V, "resolver_cita", resolver)
    fid, afs = _extraer_con(monkeypatch, al, ids, ctx, [{"localizador": "texto web, parte 1", "texto": "GFAP sube " * 20, "encabezado": "T"}])
    assert vistos == [fid] and afs[0]["veredicto"] == "sin_verificar"


def test_un_localizador_que_resuelve_por_id_pero_no_por_patron_solo_avisa(monkeypatch):
    al, ids, ctx = _preparar()
    monkeypatch.setattr(V, "resolver_cita", lambda cita, fragmentos, fuente_id=None: fragmentos[0])
    monkeypatch.setattr(V, "LOCALIZADORES_ADMITIDOS", __import__("re").compile(r"resumen"), raising=False)
    _, afs = _extraer_con(monkeypatch, al, ids, ctx, [{"localizador": "apéndice B", "texto": "GFAP sube " * 20, "encabezado": "T"}])
    assert afs[0]["veredicto"] == "sin_verificar"
    assert "la réplica por texto no lo reconocería" in _pista_textos(al, ids)


@pytest.mark.parametrize("localizador", ["resumen", "pág. 4", "sección Results", "texto web, parte 3"])
def test_los_cuatro_localizadores_de_fragmentos_de_resuelven_con_el_verificador(localizador):
    """Contrato entre pasos.py y verificador.py: cada localizador que fabrica
    `_fragmentos_de` tiene que resolver como cita. Con el verificador del grupo A
    (LOCALIZADORES_ADMITIDOS) pasan los cuatro; hasta entonces "texto web" se
    marca xfail, no se esconde."""
    frag = V.Fragmento("f1", "Sin autor, 2024", localizador, "GFAP sube", "T")
    resuelto = V.resolver_cita(f"[Sin autor, 2024, {localizador}]", [frag])
    if localizador.startswith("texto web") and getattr(V, "LOCALIZADORES_ADMITIDOS", None) is None:
        pytest.xfail("verificador.py aún sin LOCALIZADORES_ADMITIDOS (grupo A)")
    assert resuelto is frag


# ---------------------------------------------------------------------------
# S-16: la cola por regla
# ---------------------------------------------------------------------------


def _h(inv, titulo, estado, decision, creada, it):
    h = P.nueva_hipotesis(inv, it, creada, titulo=titulo, enunciado="e", mecanismo="m", comprobacion={"biomarcador": "GFAP", "cohorte": "c", "diseno": "d"}, afirmaciones=[])
    h["estado"] = estado
    h["decisionKiller"] = decision
    return h


def test_cola_de_hipotesis_cuenta_bien_con_estados_mixtos():
    inv = "inv-1"
    hs = [
        _h(inv, "A", "propuesta", "descartar_en_contexto", 1_700_000_000_000, 1),
        _h(inv, "B", "en_revision", "descartar_en_contexto", 1_700_000_000_000, 1),
        _h(inv, "C", "propuesta", "descartar_en_contexto", 1_700_000_000_000, 2),
        _h(inv, "D", "propuesta", "suspender", 1_700_000_000_000, 2),
        _h(inv, "E", "en_revision", "suspender", 1_700_000_000_000, 2),
        _h(inv, "F", "propuesta", "suspender", 1_700_000_000_000, 3),
        _h(inv, "G", "en_revision", "suspender", 1_700_000_000_000, 3),
        _h(inv, "H", "propuesta", None, 1_700_000_000_000, 3),
        _h(inv, "I", "propuesta", None, 1_700_000_000_000, 3),
        _h(inv, "J aceptada", "aceptada", "avanzar", 1_700_000_000_000, 1),
        _h(inv, "K aceptada", "aceptada", "avanzar", 1_700_000_000_000, 1),
        _h(inv, "L descartada", "descartada", "descartar_en_contexto", 1_700_000_000_000, 1),
        _h("otra", "M de otra investigación", "propuesta", None, 1_700_000_000_000, 1),
    ]
    e = {"hipotesis": hs, "decisiones": [{"hipotesisId": hs[0]["id"], "etapa": "killer_1", "fecha": 5, "decision": "descartar_en_contexto", "motivo": "La evidencia no sostiene la hipótesis", "comprobaciones": [{"comprobacion": "supuestos", "resultado": "falla", "detalle": "1 supuesto contradicho"}, {"comprobacion": "citas_reales", "resultado": "pasa"}]}]}
    texto = T.cola_de_hipotesis(e, inv)
    lineas = texto.split("\n")
    assert lineas[0].startswith("9 en cola: 3 con descarte propuesto, 4 suspendidas, 2 sin juzgar."), lineas[0]
    assert "Además 2 aceptadas" in lineas[0]
    assert T.recuento_cola(e, inv) == {"total": 9, "descarte": 3, "suspendidas": 4, "sinJuzgar": 2, "otras": 0}
    cuerpo = "\n".join(lineas[1:])
    assert "«A»" in cuerpo and "falla en supuestos: La evidencia no sostiene" in cuerpo
    assert "«L descartada»" not in cuerpo and "otra investigación" not in cuerpo
    assert "«J aceptada» [estado aceptada; Killer: avanzar" in cuerpo
    assert "«H» [estado propuesta; Killer: sin juzgar; nació el 2023-11-14, iteración 3]" in cuerpo
    # Sin motivo registrado, no se inventa: la línea de D solo lleva la decisión.
    assert "«D» [estado propuesta; Killer: suspender; nació" in cuerpo


def test_cola_de_hipotesis_aguanta_registros_antiguos_y_vacios():
    assert T.cola_de_hipotesis({"hipotesis": []}, "inv") == "0 en cola. Ninguna hipótesis viva."
    e = {"hipotesis": [{"id": "h1", "investigacionId": "inv", "estado": "propuesta", "titulo": None}], "decisiones": None}
    texto = T.cola_de_hipotesis(e, "inv")
    assert texto.startswith("1 en cola: 0 con descarte propuesto, 0 suspendidas, 1 sin juzgar.")
    assert "nació el sin fecha, iteración ?" in texto
    assert T.frase_recuento_cola({"total": 2, "descarte": 0, "suspendidas": 0, "sinJuzgar": 0, "otras": 2}).endswith("2 con otra decisión del Killer.")


# ---------------------------------------------------------------------------
# M-07: dirección por regla
# ---------------------------------------------------------------------------


def _a(relacion=None, veredicto="sostenida", **k):
    return {"texto": "t", "cita": "[A, resumen]", "veredicto": veredicto, "relacion": relacion, **k}


def test_direccion_mixta_exige_una_afirmacion_en_contra():
    assert T.direccion_por_regla([_a(), _a("apoya")], "mixta") == "apoya"
    assert T.direccion_por_regla([_a(), _a("contradice")], "mixta") == "mixta"
    assert T.direccion_por_regla([_a(), _a("contradice")], "apoya") == "mixta"
    assert T.direccion_por_regla([_a("contradice")], "apoya") == "en_contra"
    assert T.direccion_por_regla([_a()], "en_contra") == "apoya"
    assert T.direccion_por_regla([], "mixta") == "sin_evidencia_directa"
    assert T.direccion_por_regla(None, "apoya") == "sin_evidencia_directa"
    # Solo apoyos indirectos: el juez puede decir "sin evidencia directa"; con uno directo, no.
    assert T.direccion_por_regla([_a("apoya_indirecta")], "sin_evidencia_directa") == "sin_evidencia_directa"
    assert T.direccion_por_regla([_a("apoya_indirecta"), _a()], "sin_evidencia_directa") == "apoya"
    # Lo sintético, lo no sostenido y lo socavado no cuentan.
    assert T.direccion_por_regla([_a("contradice", sintetico=True), _a()], "mixta") == "apoya"
    assert T.direccion_por_regla([_a("contradice", veredicto="no_sostenida"), _a()], "mixta") == "apoya"
    assert T.direccion_por_regla([_a(socavadaPor=["x"])], "apoya") == "sin_evidencia_directa"
    # Un experimento que refuta manda.
    assert T.direccion_por_regla([_a()], "apoya", {"resultado": {"veredicto": "refuta"}}) == "en_contra"
    assert T.direccion_por_regla([_a()], "apoya", {"resultado": "raro"}) == "apoya"


# ---------------------------------------------------------------------------
# S-16 y M-06: las firmas
# ---------------------------------------------------------------------------


def test_las_firmas_llevan_las_entradas_nuevas():
    from rosa.modulos import firmas as F

    for firma in (F.ResumirIteracion, F.ExplicarEnLlano):
        assert "cola" in firma.input_fields
        assert "recuento" in firma.input_fields["cola"].json_schema_extra["desc"]
    assert "techo_por_regla" in F.ConcluirHipotesis.input_fields
    certeza = F.ConclusionHipotesis.model_fields["certeza"].description
    assert "dos o más cohortes" in certeza and "réplica directa" in certeza and "techo_por_regla" in certeza
    assert "no hay evidencia directa o es contradictoria" not in certeza
    direccion = F.ConclusionHipotesis.model_fields["direccion"].description
    assert "EN CONTRA" in direccion and "supuesto contradicho" in direccion
    # Un registro antiguo del juez sin indices_que_lo_niegan sigue parseando.
    s = F.SupuestoEvaluado(estado="contradicho", evidencia="afirmación 3")
    assert s.indices_que_lo_niegan == []
    assert F.SupuestoEvaluado(estado="contradicho", evidencia="x", indices_que_lo_niegan=[3, 5]).indices_que_lo_niegan == [3, 5]


# ---------------------------------------------------------------------------
# Adversario del grupo B1 (17 de septiembre de 2026): lo que se rompió al probar
# con textos reales y registros antiguos, y lo que ningún test cubría
# ---------------------------------------------------------------------------


def test_terminos_para_ingles_descarta_estadistica_metadatos_y_mayusculas_con_tilde():
    """Antes: un enunciado con estadística daba la consulta "HR IC OR", un
    título en mayúsculas con tilde daba "TULO EN MAY" (cortado en la tilde,
    la misma clase de fallo que S-02) y "APOE e4" daba "e4". Con esas
    consultas OpenAlex devuelve obras ajenas, el modelo las puntúa bajo y la
    hipótesis quedaba "sin precedente" con obras evaluadas: falso."""
    h = {"titulo": "La atrofia hipocampal basal predice la conversión a demencia", "enunciado": "En personas con deterioro cognitivo leve, la atrofia predice la conversión (HR 1,8; IC 95 % 1,2 a 2,6; OR 2,1); n=340, SD 4,2, AUC 0,7, DOI 10.1000/x, PMID 12345"}
    assert T.terminos_para_ingles(h) == []
    # Un título escrito en mayúsculas no da siglas fiables ("MEMORIA" parece una); solo pasan los tokens con cifra.
    assert T.terminos_para_ingles({"titulo": "TÍTULO EN MAYÚSCULAS SOBRE LA MEMORIA Y EL GFAP"}) == []
    assert T.terminos_para_ingles({"titulo": "TÍTULO EN MAYÚSCULAS SOBRE P-TAU181 Y GFAP", "_entidades": ["GFAP"]}) == ["GFAP", "P-TAU181"]
    assert T.terminos_para_ingles({"titulo": "APOE e4 y edad", "enunciado": "APOE e4 adelanta el cruce a los 65 años"}) == ["APOE"]
    assert T.terminos_para_ingles({"titulo": "Marta GRADE PRISMA", "enunciado": "según Marta y GRADE y PRISMA en USD"}) == []
    # Un compuesto de un término ya recogido (TSPO-PET tras TSPO) no gasta el sitio de otro.
    assert T.terminos_para_ingles({"_entidades": ["TSPO"], "titulo": "Semaglutida y TSPO-PET", "enunciado": "medida por TSPO-PET y NfL"}) == ["TSPO", "NfL"]
    # Lo legítimo sigue entrando: siglas del dominio de dos letras que no están en la lista negra no se tocan.
    assert T.terminos_para_ingles({"titulo": "Aβ42 y p-tau217 en LCR frente a PET"}) == ["p-tau217", "CSF", "PET"]


def test_es_de_fondo_no_mira_el_titulo_del_articulo_en_paginas_ni_resumen():
    """En páginas de PDF, resumen y texto web el encabezado del fragmento es el
    título del artículo; un artículo titulado "Background parenchymal..." no
    es de fondo. Solo en "sección X" el encabezado es el nombre de la sección."""
    assert PASOS.es_de_fondo("pág. 2", "Background parenchymal enhancement and GFAP") is False
    assert PASOS.es_de_fondo("resumen", "Discussion of plasma NfL cut-offs") is False
    assert PASOS.es_de_fondo("texto web, parte 1", "Introduction to biomarkers") is False
    assert PASOS.es_de_fondo("sección Introduction", "Introduction") is True
    # Localizador truncado a 60 caracteres pero encabezado completo: manda el encabezado de la sección.
    assert PASOS.es_de_fondo("sección Results", "Results") is False
    assert PASOS.es_de_fondo("sección 2", "Background and rationale") is True
    assert PASOS.es_de_fondo("   ", "Introduction") is False and PASOS.es_de_fondo(None, "Discussion") is False


def _hipotesis_sin_terminos(al, inv_id, n):
    """n hipótesis en castellano sin siglas ni cifras: ninguna da términos en
    inglés, así que con Exa apagada todas quedan "no comprobado" siempre."""
    ids = []

    def fn(e):
        for i in range(n):
            h = P.nueva_hipotesis(inv_id, 1, 1000 + i, titulo=f"Hipótesis número {'uno dos tres cuatro cinco seis siete ocho'.split()[i]} sobre la memoria", enunciado="La anormalidad plasmática precede a la cortical", mecanismo="m", comprobacion={"biomarcador": "proteína en plasma", "cohorte": "c", "diseno": "d"}, afirmaciones=[])
            e["hipotesis"].append(h)
            ids.append(h["id"])
        return True

    al.mutar(fn, "hipotesis")
    return ids


def test_paso_novedad_rota_las_pendientes_y_no_repite_siempre_las_mismas_seis(monkeypatch):
    """Con siete hipótesis que se quedan en "no comprobado", la primera pasada
    atiende a seis; la segunda tiene que empezar por la séptima, no repetir
    las mismas seis para siempre (con eso las demás nunca se comprobaban)."""
    al, ids, ctx = _preparar(titulo="Precedencia de la anormalidad plasmática", biomarcador="proteína en plasma")
    al.mutar(lambda e: _hip(al, ids).update(enunciado="La anormalidad plasmática precede a la cortical") or True, "enunciado")
    nuevas = _hipotesis_sin_terminos(al, ids["inv"], 6)
    todas = [ids["hip"], *nuevas]
    _sin_red(monkeypatch, obras=[], total=0, relevancia=lambda kw: 2)
    asyncio.run(PASOS.paso_novedad(ctx, _paso(al, ids)))
    intentos = {h["id"]: h.get("_novedadIntentos", 0) for h in al.estado["hipotesis"] if h["id"] in todas}
    assert sorted(intentos.values()) == [0, 1, 1, 1, 1, 1, 1], intentos
    sin_turno = next(k for k, v in intentos.items() if v == 0)
    assert all(PASOS.novedad_pendiente(h) for h in al.estado["hipotesis"] if h["id"] in todas), "siguen pendientes: no hay términos ni Exa"
    asyncio.run(PASOS.paso_novedad(ctx, _paso(al, ids)))
    intentos = {h["id"]: h.get("_novedadIntentos", 0) for h in al.estado["hipotesis"] if h["id"] in todas}
    assert intentos[sin_turno] == 1, "la séptima tenía que ir la primera en la segunda pasada"
    assert sorted(intentos.values()) == [1, 1, 2, 2, 2, 2, 2], intentos
    # La clave es privada: no viaja al navegador.
    assert all(k.startswith("_") for k in ("_novedadIntentos",))


def test_paso_novedad_aguanta_un_registro_sin_novedad_ni_procedencia(monkeypatch):
    """`novedad_pendiente` deja pasar un registro antiguo sin `novedad`; el
    cuerpo del paso no puede romperse con él (antes: KeyError en h["novedad"])."""
    al, ids, ctx = _preparar()

    def romper(e):
        h = _hip(al, ids)
        h.pop("novedad", None)
        h.pop("procedencia", None)
        h.pop("_entidades", None)
        return True

    al.mutar(romper, "viejo")
    _sin_red(monkeypatch, obras=[_obra("BACE1 and GFAP")], total=1, relevancia=lambda kw: 2)
    asyncio.run(PASOS.paso_novedad(ctx, _paso(al, ids)))
    h = _hip(al, ids)
    assert h["novedad"]["precedente"]["estado"] == "sin_precedente"
    assert h["procedencia"]["registro"] and "novedad ->" in h["procedencia"]["registro"][-1]


def test_sin_terminos_clinicaltrials_dice_que_no_se_consulto_no_que_no_respondio(monkeypatch):
    al, ids, ctx = _preparar(titulo="Precedencia de la anormalidad plasmática", biomarcador="proteína en plasma")
    al.mutar(lambda e: _hip(al, ids).update(enunciado="La anormalidad plasmática precede a la cortical") or True, "enunciado")
    llamadas = []

    async def buscar_ct(*a, **k):
        llamadas.append(k)
        return [], 0

    _sin_red(monkeypatch, obras=[], total=0, relevancia=lambda kw: 2)
    monkeypatch.setattr(clinicaltrials, "buscar", buscar_ct)
    asyncio.run(PASOS.paso_novedad(ctx, _paso(al, ids)))
    ens = _hip(al, ids)["novedad"]["ensayos"]
    assert llamadas == [], "sin términos en inglés no se consulta ClinicalTrials.gov"
    assert ens["estado"] == "no_comprobado" and ens["detalle"].startswith("No comprobado")
    assert "no respondió" not in ens["detalle"] and "términos buscables" in ens["detalle"], ens


def test_el_juez_recibe_el_fragmento_de_su_propia_fuente_cuando_el_determinista_no_lo_resolvio(monkeypatch):
    """Dos fuentes "Sin autor" con un resumen cada una. La afirmación trae el
    fuenteId de la segunda; si el determinista manda al juez sin fragmento, el
    juez tiene que leer el texto de la segunda, no el de la primera ni nada."""
    al, ids, ctx = _preparar()
    f1 = PASOS._registrar_fuente(ctx, {"referencia": "Sin autor", "titulo": "Página uno sobre GFAP", "url": "https://u1", "tipos": [], "resumen": "PRIMERA: GFAP baja."}, "articulo", [{"localizador": "resumen", "texto": "PRIMERA: GFAP baja.", "encabezado": "Uno"}], 8, None, "limpio", 1, "q")
    f2 = PASOS._registrar_fuente(ctx, {"referencia": "Sin autor", "titulo": "Página dos sobre NfL", "url": "https://u2", "tipos": [], "resumen": "SEGUNDA: GFAP sube."}, "articulo", [{"localizador": "resumen", "texto": "SEGUNDA: GFAP sube.", "encabezado": "Dos"}], 8, None, "limpio", 1, "q")
    assert f1 != f2
    monkeypatch.setattr(V, "comprobar_determinista", lambda *a, **k: V.Resultado("sin_verificar", "Pendiente del juez.", pistas="", necesita_juez=True, fragmento=None))
    recibidos = []

    async def llamar(self, rol, programa, **kw):
        assert programa == "juzgar"
        recibidos.append(kw["fragmento"])
        return SimpleNamespace(veredicto=SimpleNamespace(veredicto="sostenida", motivo="ok", entidad_distinta=False))

    monkeypatch.setattr(Ctx, "llamar", llamar)  # simulación local
    a = {"texto": "GFAP sube.", "cita": "[Sin autor, resumen]", "fragmento": None, "veredicto": "sin_verificar", "fuenteId": f2, "localizador": "resumen"}
    r = asyncio.run(PASOS.verificar_afirmaciones(ctx, [a], None, "GFAP"))
    assert r == {"sostenida": 1} and len(recibidos) == 1
    assert "SEGUNDA: GFAP sube." in recibidos[0] and "PRIMERA" not in recibidos[0], recibidos[0]
    assert "Encabezado: Dos" in recibidos[0]
    # Una afirmación antigua sin fuenteId ni localizador no rompe: el juez recibe lo que la afirmación traía.
    b = {"texto": "GFAP sube.", "cita": "[Sin autor, resumen]", "fragmento": "lo que traía", "veredicto": "sin_verificar"}
    asyncio.run(PASOS.verificar_afirmaciones(ctx, [b], None, "GFAP"))
    assert "lo que traía" in recibidos[1]
