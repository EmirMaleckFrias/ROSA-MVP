"""Arreglos sobre el GEPA automático de Codex (16 de septiembre de 2026): las
trazas se escriben desde un hilo propio y la redacción es lineal; el ciclo no
corre con corridas vivas y comprueba barato; los casos solo se consumen al
terminar; el examen se separa por investigación; las comprobaciones por regla
dan cero sin juez; la promoción queda en el registro de aprendizaje y se
revierte desde allí; el arnés público nombra las versiones."""
import time
from types import SimpleNamespace

import dspy
import pytest

from rosa import gepa_continuo as G
from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen


class Programa(dspy.Signature):
    """Contrato original fijo."""
    pregunta: str = dspy.InputField()
    respuesta: str = dspy.OutputField()


@pytest.fixture
def servicio(tmp_path, monkeypatch):
    almacen = Almacen(tmp_path / "prueba.db")
    almacen.mutar(lambda e: e.update(corridas=[{"id": "vieja", "estado": "terminada", "investigacionId": "inv"}], investigaciones=[{"id": "inv", "datasets": []}], iteraciones=[], gepa=[]) or True)
    programas = SimpleNamespace(consultas=dspy.Predict(Programa))
    lm = dspy.LM("openai/simulado", api_base=G.URL_GATEWAY)
    s = G.Servicio(almacen, programas, SimpleNamespace(cerebro=lm, juez=lm, reflexion=lm, volumen=lm))
    monkeypatch.setattr(G, "AUTOMATICOS", {"consultas": "cerebro"})
    monkeypatch.setattr(dspy.LM, "forward", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Gateway")))
    yield s
    s.registro.cerrar()
    almacen.cerrar()


def test_redaccion_lineal_y_recorte():
    largo = "a" * 40_000
    t = time.perf_counter()
    salida = G.sanear({"texto": largo, "correo": "persona@example.test", "api_key": "x"})
    assert time.perf_counter() - t < 0.5
    assert "[recortado" in salida["texto"] and salida["correo"] == "[REDACTADO]" and salida["api_key"] == "[REDACTADO]"
    assert G.sanear("escribe a maria.lopez+rosa@intec.edu.do hoy") == "escribe a [REDACTADO] hoy"


def test_registro_escribe_en_hilo_y_retiene(servicio):
    for i in range(20):
        servicio.registro.guardar("modelo", {"corrida": "vieja", "programa": "consultas", "prompt": f"p{i}"})
    servicio.registro.guardar("programa", {"corrida": "vieja", "programa": "consultas", "entradas": {"pregunta": "q"}})
    servicio.registro.flush()
    assert servicio.registro.resumen() == {"modelo": 20, "programa": 1}
    assert servicio.registro.nuevas_desde("consultas", 0) == 1
    # Retención: lo de modelo más viejo que la retención se borra; lo de programa se queda.
    with servicio.registro.lock, servicio.registro.db:
        servicio.registro.db.execute("UPDATE trazas SET fecha = fecha - ?", (G.RETENCION_DIAS_MODELO * 86400 + 10,))
    assert servicio.registro.retener() == 20
    assert servicio.registro.resumen() == {"programa": 1}


def test_ciclo_no_corre_con_corridas_vivas_ni_recarga_sin_trazas_nuevas(servicio, monkeypatch):
    llamadas = []
    monkeypatch.setattr(servicio, "_optimizar", lambda *a: llamadas.append(a))
    monkeypatch.setattr(servicio.registro, "filas", lambda programa: pytest.fail("no debía cargar trazas"))
    servicio.almacen.mutar(lambda e: e["corridas"].append({"id": "viva", "estado": "en_marcha", "investigacionId": "inv"}) or True)
    assert servicio.ciclo() is False
    assert servicio.almacen.estado["gepaAutomatico"]["estado"] == "esperando_corridas"
    servicio.almacen.mutar(lambda e: e["corridas"].pop() or True)
    # Sin trazas nuevas, la comprobación barata corta antes de cargar nada.
    assert servicio.ciclo() is False and not llamadas


def test_dividir_separa_por_investigacion_no_por_corrida():
    filas = [{"corrida": f"c{i}", "entradas": {"pregunta": f"p{i}-{j}"}} for i in range(20) for j in range(3)]
    # Todas las corridas son de dos investigaciones: ninguna investigación cae en dos particiones.
    inv_de = {f"c{i}": ("A" if i % 2 else "B") for i in range(20)}
    a, b, c = G.dividir(filas, inv_de)
    invs = [{inv_de[f["corrida"]] for f in p} for p in (a, b, c)]
    assert not (invs[0] & invs[1]) and not (invs[0] & invs[2]) and not (invs[1] & invs[2])


def test_comprobaciones_deterministas():
    assert G.comprobaciones_deterministas("consultas", {}, None) == ["salida vacía"]
    assert "una consulta sin texto o sin base" in G.comprobaciones_deterministas("consultas", {}, {"consultas": [{"consulta": "GFAP", "base": ""}]})
    assert G.comprobaciones_deterministas("consultas", {}, {"consultas": [{"consulta": "GFAP", "base": "pubmed"}]}) == []
    assert "una afirmación cuya cita no nombra la fuente dada" in G.comprobaciones_deterministas("extraer", {"referencia": "Kim et al., 2025"}, {"afirmaciones": [{"texto": "x", "cita": "[Otro, pág. 2]"}]})
    assert G.comprobaciones_deterministas("extraer", {"referencia": "Kim et al., 2025"}, {"afirmaciones": [{"texto": "x", "cita": "[Kim et al., 2025, pág. 2]"}]}) == []
    assert "la salida contiene texto redactado" in G.comprobaciones_deterministas("resumir", {}, "hola [REDACTADO]")


def _partes():
    return tuple([{"corrida": f"c{j}", "entradas": {"pregunta": f"caso-{j}-{i}"}} for i in range(10)] for j in range(3))


def test_fallo_transitorio_no_consume_casos_y_uno_definitivo_si(servicio, monkeypatch):
    class Optimizador:
        def __init__(self, **kwargs):
            pass
        def compile(self, base, trainset, valset):
            raise G.FalloTransitorio("gateway caído")
    monkeypatch.setattr(dspy, "GEPA", Optimizador)
    servicio._optimizar("consultas", "cerebro", _partes())
    g = servicio.almacen.estado["gepa"][-1]
    assert g["estado"] == "fallida" and "reintentará" in g["nota"]
    with servicio.registro.lock:
        assert servicio.registro.db.execute("SELECT count(*) FROM usados").fetchone()[0] == 0

    class OptimizadorRoto:
        def __init__(self, **kwargs):
            pass
        def compile(self, base, trainset, valset):
            raise ValueError("programa inválido")
    monkeypatch.setattr(dspy, "GEPA", OptimizadorRoto)
    servicio._optimizar("consultas", "cerebro", _partes())
    with servicio.registro.lock:
        assert servicio.registro.db.execute("SELECT count(*) FROM usados").fetchone()[0] == 30


def test_promocion_queda_en_aprendizaje_y_revertir_devuelve_la_version_anterior(servicio, monkeypatch):
    def forward(self, **kwargs):
        if self.signature is G.AuditarSalida:
            nota = 0.9 if "mejorada" in kwargs["salida"] else 0.5
            return dspy.Prediction(fidelidad=nota, cobertura=nota, cumplimiento=nota, critico=False, feedback="ok")
        return dspy.Prediction(respuesta="mejorada" if self.signature.instructions == "mejorada" else "base")
    monkeypatch.setattr(dspy.Predict, "forward", forward)

    class Optimizador:
        def __init__(self, **kwargs):
            pass
        def compile(self, base, trainset, valset):
            p = base.deepcopy()
            p.signature = p.signature.with_instructions("mejorada")
            p.detailed_results = SimpleNamespace(val_aggregate_scores=[0.5, 0.9])
            return p
    monkeypatch.setattr(dspy, "GEPA", Optimizador)
    servicio._optimizar("consultas", "cerebro", _partes())
    e = servicio.almacen.estado
    g = e["gepa"][-1]
    assert g["promovido"] and g["gasto"]["llamadas"] >= 0 and g["particiones"] == [10, 10, 10]
    cambio = e["aprendizaje"][-1]
    assert cambio["tipo"] == "programa" and cambio["estado"] == "promovido" and cambio["origen"] == f"gepa:{g['id']}" and cambio["programa"] == "consultas" and cambio["version"] == g["version"]
    assert e["_gepaActivos"]["consultas"] == g["version"]
    # Una corrida nueva fija la versión al crearse y la nombra en el arnés público.
    inv = A.crear_investigacion(e, {"titulo": "t", "objetivo": "o", "condicionParada": "3 iteraciones"}, 1000)
    cid = A.iniciar_corrida(e, inv, 2000)
    c = next(x for x in e["corridas"] if x["id"] == cid)
    assert c["_gepaVersiones"] == {"consultas": g["version"]} and c["arnes"]["optimizados"] == f"consultas@{g['version'][:8]}"
    # Revertir desde el registro de aprendizaje devuelve la base a las corridas nuevas.
    assert A.revertir_aprendizaje(e, cambio["id"], "Emir", "no convence", 3000) is True
    assert "consultas" not in e["_gepaActivos"]
    assert c["_gepaVersiones"] == {"consultas": g["version"]}  # la corrida ya creada no cambia
