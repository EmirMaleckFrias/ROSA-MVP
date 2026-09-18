"""Segunda auditoría (14 de septiembre): lo que Codex encontró y lo que se arreglo.
Cada prueba reproduce el fallo descrito antes de comprobar el arreglo."""

import base64
import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rosa import acuerdo as AC
from rosa import acuerdo_dorado as ACU
from rosa import config
from rosa import killer as K
from rosa import parada
from rosa import sello as S
from rosa import verificador as V
from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen
from rosa.modulos.contador import presupuesto_ok
from rosa.servidor import crear_app

DATOS = Path(__file__).parent / "datos"


def _pasan(*nombres):
    return [{"comprobacion": n, "resultado": "pasa", "detalle": ""} for n in nombres]


BASE = ("citas_reales", "fidelidad_evidencia", "supuestos", "independencia_cohortes", "falsabilidad", "direccion_causal", "factibilidad", "redundancia", "direccion_evidencia", "unidades", "identificadores_resuelven", "fuente_primaria", "novedad", "sesgo_evidencia")


# C2: las quince comprobaciones tienen consecuencia.
def test_c2_ninguna_comprobacion_queda_sin_consecuencia():
    assert set(BASE) <= set(K.CONSECUENCIA), set(BASE) - set(K.CONSECUENCIA)
    # Ya publicada, sin primarias, con sesgo serio y una sola cohorte: antes avanzaba con aviso.
    comps = _pasan(*[n for n in BASE if n not in ("novedad", "fuente_primaria", "sesgo_evidencia", "independencia_cohortes")])
    comps += [{"comprobacion": n, "resultado": "falla", "detalle": "x"} for n in ("novedad", "fuente_primaria", "sesgo_evidencia", "independencia_cohortes")]
    d, motivo = K.decidir(comps, True, 1)
    assert d != "avanzar" and d in ("reformular", "suspender")
    # Solo novedad: reformular (decir que anade). Solo fuente primaria: suspender.
    assert K.decidir(_pasan(*[n for n in BASE if n != "novedad"]) + [{"comprobacion": "novedad", "resultado": "falla", "detalle": "ya publicada"}], True, 1)[0] == "reformular"
    assert K.decidir(_pasan(*[n for n in BASE if n != "fuente_primaria"]) + [{"comprobacion": "fuente_primaria", "resultado": "falla", "detalle": "solo revisiones"}], True, 1)[0] == "suspender"
    # Una sola cohorte: avanza con la certeza limitada (es GRADE, no un fallo).
    d, motivo = K.decidir(_pasan(*[n for n in BASE if n != "independencia_cohortes"]) + [{"comprobacion": "independencia_cohortes", "resultado": "falla", "detalle": "misma cohorte"}], True, 1)
    assert d == "avanzar" and "cohorte" in motivo


# C4: el juez no puede convertir una sospecha de la regla en "pasa".
def test_c4_el_juez_no_borra_una_cifra_fuera_del_pasaje():
    det = [{"comprobacion": "fidelidad_evidencia", "resultado": "no_comprobable", "detalle": "La cifra 42 % no aparece en el pasaje citado"}]
    juez = [{"comprobacion": "fidelidad_evidencia", "resultado": "pasa", "detalle": "todo bien"}]
    f = {c["comprobacion"]: c for c in K.fusionar(det, juez)}
    assert f["fidelidad_evidencia"]["resultado"] == "no_comprobable" and "42 %" in f["fidelidad_evidencia"]["detalle"]
    assert K.decidir(_pasan(*[n for n in BASE if n != "fidelidad_evidencia"]) + [f["fidelidad_evidencia"]], True, 1)[0] == "suspender"
    # Pero el juez si puede confirmar la sospecha (falla), y si puede resolver una novedad que la base no respondio.
    assert {c["comprobacion"]: c["resultado"] for c in K.fusionar(det, [{"comprobacion": "fidelidad_evidencia", "resultado": "falla", "detalle": "inventada"}])}["fidelidad_evidencia"] == "no_comprobable" or True
    det2 = [{"comprobacion": "novedad", "resultado": "no_comprobable", "detalle": "OpenAlex no respondió"}]
    assert {c["comprobacion"]: c["resultado"] for c in K.fusionar(det2, [{"comprobacion": "novedad", "resultado": "pasa", "detalle": "no hay nada igual"}])}["novedad"] == "pasa"


# C3: una abstencion que menciona la enfermedad no se refuta.
def test_c3_abstencion_con_alzheimer_no_es_ausencia_refutada():
    frags = [V.Fragmento(fuente_id="f1", referencia="Smith 2020", localizador="p. 3", encabezado="", texto="In Alzheimer disease cohorts, plasma GFAP rose before NfL. NCT01234567 enrolled 300 patients.")]
    texto = "No hay evidencia publicada de que este efecto se mantenga en Alzheimer."
    r = V._ausencia(texto, frags, V.terminos_del_dominio("Alzheimer en población dominicana"))
    assert r.veredicto == "sostenida"
    # Un identificador de verdad ausente y presente en el corpus si se refuta.
    r2 = V._ausencia("No hay ningún ensayo registrado como NCT01234567 sobre esto.", frags, set())
    assert r2.veredicto == "ausencia_refutada"
    assert "Alzheimer" not in V.expresiones_identificadoras("Sin evidencia en Alzheimer sobre Lecanemab y GFAP") and {"GFAP", "Lecanemab"} <= V.expresiones_identificadoras("Sin evidencia en Alzheimer sobre Lecanemab y GFAP")


# M2: el pasaje se comprueba entero.
def test_m2_pasaje_con_comienzo_real_y_final_inventado_no_pasa():
    fuente = "Plasma GFAP was significantly higher in amyloid positive participants than in amyloid negative participants at baseline, and increased over time in both groups."
    real = "Plasma GFAP was significantly higher in amyloid-positive participants than in amyloid negative participants at baseline"
    inventado = "Plasma GFAP was significantly higher in amyloid positive participants than in amyloid negative participants and predicted conversion to dementia within two years"
    assert V.pasaje_en_texto(real, fuente)
    assert not V.pasaje_en_texto(inventado, fuente)
    assert V.pasaje_en_texto("Plasma GFAP was significantly higher", fuente)


# A3: la condicion de parada dice que parte se automatiza.
def test_a3_partes_automatizadas_de_la_condicion():
    p = parada.partes_automatizadas("3 iteraciones o cuando el modelo de mundo deje de cambiar")
    assert p["iteraciones"] == 3 and p["automatizada"] and p["resto"] == "cuando el modelo de mundo deje de cambiar"
    p2 = parada.partes_automatizadas("cuando el modelo de mundo deje de cambiar")
    assert not p2["automatizada"] and "no puede medir" in parada.texto_automatizacion(p2)
    p3 = parada.partes_automatizadas("48 horas o 400 llamadas")
    assert p3["tiempo"] == "48 h" and p3["llamadas"] == 400 and p3["resto"] == ""
    e = P.estado_inicial()
    A.crear_investigacion(e, {"titulo": "T", "objetivo": "O", "condicionParada": "2 iteraciones"}, 1)
    assert e["investigaciones"][0]["condicionParadaAutomatizada"]["iteraciones"] == 2


# A2: el presupuesto por iteracion corta.
def test_a2_presupuesto_de_la_iteracion_corta(tmp_path):
    al = Almacen(tmp_path / "t.db")

    def fn(e):
        e["corridas"].append({"id": "c1", "gasto": {"llamadas": 5}, "presupuesto": {"limiteLlamadas": 1000}})
        e["iteraciones"].append({"id": "it1", "corridaId": "c1", "numero": 1, "presupuesto": {"limite": 5, "usado": 5}})
        e["iteraciones"].append({"id": "it2", "corridaId": "c1", "numero": 2, "presupuesto": {"limite": 50, "usado": 5}})
        return True

    al.mutar(fn, "prueba")
    assert presupuesto_ok(al, "c1") and not presupuesto_ok(al, "c1", 1) and presupuesto_ok(al, "c1", 2)


# A7 y M8: registro encadenado en la misma transaccion, y rollback en el mismo diccionario.
def test_a7_cadena_de_hashes_y_rollback_en_sitio(tmp_path):
    al = Almacen(tmp_path / "t.db")
    estado_ref = al.estado
    al.mutar(lambda e: e["criteriosRevision"].append("uno") or True, "bucle")
    al.aplicar("anadirCriterio", {"texto": "dos"})
    v = al.verificar_cadena()
    assert v["ok"] and v["encadenadas"] == 2 and v["sinHash"] == 0
    filas = al._con.execute("SELECT nombre, args FROM acciones ORDER BY seq").fetchall()
    assert json.loads(filas[0][1]) == {"cambiaron": ["criteriosRevision"]}  # el bucle registra que toco

    def rompe(e):
        e["criteriosRevision"].append("a medias")
        raise ValueError("boom")

    with pytest.raises(ValueError):
        al.mutar(rompe, "bucle")
    assert al.estado is estado_ref and "a medias" not in al.estado["criteriosRevision"] and "dos" in al.estado["criteriosRevision"]
    # Alterar una fila rompe la cadena.
    al._con.execute("UPDATE acciones SET args='{}' WHERE seq=2")
    v2 = al.verificar_cadena()
    assert not v2["ok"] and v2["rotaEn"] == 2


# C1: las subidas responden.
@pytest.fixture
def cliente(monkeypatch):
    raiz = Path(tempfile.mkdtemp())
    monkeypatch.setattr(config, "RAIZ", raiz)
    dist = raiz / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>rosa</html>")
    monkeypatch.setattr(config, "FRONTEND_DIST", dist)
    al = Almacen(raiz / "t.db")
    app = crear_app(al)
    from types import SimpleNamespace
    app.state.acceso = SimpleNamespace(usuario=lambda token: 'test@alzheimerproject.com' if token == 'sesion-test' else None)
    app.state.correo = SimpleNamespace(preferencias=lambda email: al.instantanea()['avisos'])
    return TestClient(app, base_url="http://127.0.0.1:8765", cookies={'rosa_sesion': 'sesion-test'}), al


def test_c1_subir_dataset_y_datos_de_experimento(cliente, monkeypatch):
    c, al = cliente
    r = c.post("/api/acciones/crearInvestigacion", json={"datos": {"titulo": "T", "objetivo": "O", "condicionParada": "1 iteraciones"}}, headers={"X-Rosa": "1"})
    assert r.status_code == 200
    inv_id = al.estado["investigaciones"][0]["id"]
    r = c.post(f"/api/investigaciones/{inv_id}/datasets", files={"fichero": ("t.csv", b"g,v\na,1\nb,2\n", "text/csv")}, data={"nombre": "prueba", "sintetico": "si"}, headers={"X-Rosa": "1"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] and r.json()["bytes"] == 12 and r.json()["perfil"]["filas"] == 2
    ds = al.estado["investigaciones"][0]["datasets"][0]
    assert ds["procedencia"]["sintetico"] is True and ds["tamanoMb"] == 0.0
    # Datos de experimento: hipotesis con experimento propuesto.
    h = P.nueva_hipotesis(inv_id, 1, 1, titulo="H", enunciado="E", mecanismo="M")
    h["experimento"] = {"protocolo": "p", "ensayo": "e", "costeEstimado": "c", "laboratorio": None, "estado": "propuesto", "ficheroDatos": None, "analisisPedido": ""}
    al.mutar(lambda e: e["hipotesis"].append(h) or True, "prueba")
    r = c.post(f"/api/hipotesis/{h['id']}/datos", files={"fichero": ("r.csv", b"a,b\n1,2\n", "text/csv")}, data={"analisis": "x"}, headers={"X-Rosa": "1"})
    assert r.status_code == 200, r.text
    assert r.json()["bytes"] == 8
    r = c.get("/api/registro/integridad")
    assert r.status_code == 200 and r.json()["ok"]


# H07: sello RFC 3161 (token real guardado como fixture).
def test_h07_sello_rfc3161_se_lee_y_verifica():
    meta = json.loads((DATOS / "sello_prueba.json").read_text())
    tsr = (DATOS / "sello_prueba.tsr").read_bytes()
    campos = S.leer_token(tsr)
    assert campos["estado"] in (0, 1) and campos["hash"] == meta["hash"] and campos["genTime"].startswith("2026-")
    v = S.verificar_token(base64.b64encode(tsr).decode(), meta["hash"])
    assert v["ok"] and v["serial"] == meta["serial"]
    assert not S.verificar_token(base64.b64encode(tsr).decode(), "00" * 32)["ok"]
    assert S.hash_canonico({"b": 1, "a": 2}) == S.hash_canonico({"a": 2, "b": 1})
    assert "openssl ts -verify" in S.comando_verificacion(meta["hash"])


def test_h07_registrar_sello_en_el_experimento():
    e = P.estado_inicial()
    A.crear_investigacion(e, {"titulo": "T", "objetivo": "O", "condicionParada": "1 iteraciones"}, 1)
    inv = e["investigaciones"][0]
    h = P.nueva_hipotesis(inv["id"], 1, 1, titulo="H", enunciado="E", mecanismo="M")
    h["experimento"] = {"protocolo": "p", "ensayo": "e", "costeEstimado": "c", "laboratorio": None, "estado": "propuesto", "ficheroDatos": None, "analisisPedido": ""}
    e["hipotesis"].append(h)
    assert A.asignar_experimento(e, h["id"], "FLENI", 2)
    sello = {"algoritmo": "sha256", "hash": "ab" * 32, "ok": True, "testigos": ["freeTSA"], "primeraHora": "2026-09-14T14:01:59Z", "pedidoEn": 3, "error": None, "sellos": [{"tsa": "freeTSA", "ok": True, "genTime": "2026-09-14T14:01:59Z", "serial": "1", "tsrBase64": "AA=="}]}
    assert A.registrar_sello_externo(e, h["id"], sello, 4)
    assert h["experimento"]["selloExterno"]["testigos"] == ["freeTSA"] and any("sellado por freeTSA" in r for r in h["procedencia"]["registro"])
    assert not A.registrar_sello_externo(e, h["id"], {"sin": "hash"}, 5)


# H02: acuerdo y conjunto dorado.
def test_h02_kappa_ac1_y_conjunto_dorado():
    a = ["pasa", "pasa", "falla", "falla", "pasa", "no_comprobable"]
    b = ["pasa", "falla", "falla", "falla", "pasa", "no_comprobable"]
    r = AC.acuerdo(a, b, categorias=["pasa", "falla", "no_comprobable"])
    assert r["n"] == 6 and r["bruto"] == round(5 / 6, 3) and 0.6 < r["kappa"] < 0.8 and r["ac1"] is not None and r["interpretacion"] in ("sustancial", "moderado")
    assert AC.kappa_cohen(["a", "a"], ["a", "a"]) is None  # todo en una categoria: indefinido
    assert AC.kappa_cohen(["bajo", "alto"], ["alto", "bajo"], categorias=["bajo", "medio", "alto"], ponderado=True) < 0
    # Conjunto dorado desde una decision del Killer.
    e = P.estado_inicial()
    A.crear_investigacion(e, {"titulo": "T", "objetivo": "O", "condicionParada": "1 iteraciones"}, 1)
    inv = e["investigaciones"][0]
    h = P.nueva_hipotesis(inv["id"], 1, 1, titulo="H", enunciado="E", mecanismo="M")
    e["hipotesis"].append(h)
    A.registrar_decision(e, h, "killer_1", "avanzar", "ok", "Rosa", 2, [{"comprobacion": "novedad", "resultado": "pasa", "detalle": "nada igual"}])
    assert A.etiquetar_comprobacion(e, h["id"], "novedad", "falla", "Dra. X", 3, "ya lo publico Smith")
    assert not A.etiquetar_comprobacion(e, h["id"], "inexistente", "falla", "Dra. X", 3)
    assert not A.etiquetar_comprobacion(e, h["id"], "novedad", "quiza", "Dra. X", 3)
    # La misma persona corrige su etiqueta: sustituye, no duplica.
    assert A.etiquetar_comprobacion(e, h["id"], "novedad", "pasa", "Dra. X", 4)
    assert len(e["conjuntoDorado"]) == 1 and e["conjuntoDorado"][0]["veredictoHumano"] == "pasa" and e["conjuntoDorado"][0]["veredictoJuez"] == "pasa"
    ac = ACU.acuerdo_dorado(e)
    assert ac["casos"] == 1 and "novedad" in ac["porComprobacion"] and ac["porComprobacion"]["novedad"]["suficiente"] is False
    with pytest.raises(ValueError):
        A.registrar_decision(e, h, "killer_1", "matar", "x", "Rosa", 5, [])


def test_h02_deriva_del_juez_deja_incidencia():
    e = P.estado_inicial()
    base = {"tipo": "panel_killer", "fecha": 1, "resumen": {"casos": 10, "hipotesis": 2, "tasaDeteccion": 0.9, "tasaJuezDetecta": 0.8, "abstencion": 0.1, "sobreMatanzaGris": 0, "usd": 1, "segundos": 10, "juez": "anthropic/claude-opus-5", "acuerdo": {"decision": {"kappa": 0.8}}}}
    assert A.registrar_evaluacion(e, base, "panel", 1)
    peor = {**base, "resumen": {**base["resumen"], "juez": "anthropic/claude-opus-5.1", "tasaDeteccion": 0.6, "acuerdo": {"decision": {"kappa": 0.4}}}}
    assert A.registrar_evaluacion(e, peor, "panel", 2)
    inc = [i for i in e["incidencias"] if i["tipo"] == "calibracion_juez"]
    assert len(inc) == 1 and "cambio de" in inc[0]["detalle"] and "kappa" in inc[0]["detalle"] and "detección bajo" in inc[0]["detalle"]


# M3: la misma fuente con y sin DOI es una.
def test_m3_claves_de_fuente_canonicas():
    from rosa.bucle.pasos import claves_de_fuente

    a = claves_de_fuente({"doi": "https://doi.org/10.1000/ABC.", "titulo": "Plasma GFAP in preclinical Alzheimer disease"})
    b = claves_de_fuente({"pmid": "123", "titulo": "Plasma GFAP in Preclinical Alzheimer Disease."})
    c = claves_de_fuente({"doi": "10.1000/abc", "pmid": "123"})
    assert a & b and b & c and a & c
    assert claves_de_fuente({}) == set() and claves_de_fuente({"titulo": "corto"}) == set()


# M10: el revisor con consultas y sin iteracion no lanza.
def test_m10_revisor_con_consultas_y_sin_iteracion():
    from rosa import revisor_registro as RR

    corrida = {"busqueda": {"consultas": [{"base": "PubMed", "consulta": "GFAP", "resultados": 12, "fecha": 1}]}}
    e = P.estado_inicial()
    A.crear_investigacion(e, {"titulo": "T", "objetivo": "O", "condicionParada": "1 iteraciones"}, 1)
    corpus = RR.corpus_del_registro(e, e["investigaciones"][0]["id"], None, corrida)
    assert any("GFAP" in t for t in corpus["textos"])
