"""GEPA automático: pruebas sin red ni llamadas pagadas."""
import asyncio
import json
from types import SimpleNamespace

import dspy
import pytest

from rosa import gepa_continuo as G
from rosa.estado.almacen import Almacen


class Programa(dspy.Signature):
    """Contrato original fijo."""
    pregunta: str = dspy.InputField()
    respuesta: str = dspy.OutputField()


@pytest.fixture
def servicio(tmp_path, monkeypatch):
    almacen = Almacen(tmp_path / "prueba.db")
    almacen.mutar(lambda e: e.update(corridas=[{"id": "vieja", "estado": "terminada", "investigacionId": "inv"}],
        investigaciones=[{"id": "inv", "datasets": []}], iteraciones=[], gepa=[]) or True)
    programas = SimpleNamespace(consultas=dspy.Predict(Programa))
    lm = dspy.LM("openai/simulado", api_base=G.URL_GATEWAY)
    modelos = SimpleNamespace(cerebro=lm, juez=lm, reflexion=lm)
    s = G.Servicio(almacen, programas, modelos)
    monkeypatch.setattr(G, "AUTOMATICOS", {"consultas": "cerebro"})
    # Cualquier LM real sería un error en estas pruebas.
    def prohibido(*args, **kwargs):
        raise AssertionError("Una prueba intentó acceder al Gateway")
    monkeypatch.setattr(dspy.LM, "forward", prohibido)
    yield s
    s.registro.cerrar()
    almacen.cerrar()


def partes():
    return tuple([{"corrida": f"c{j}", "entradas": {"pregunta": f"caso-{j}-{i}"}} for i in range(10)] for j in range(3))


def simular(monkeypatch, fallo_juez=False, regresion=False, al_compilar=None):
    vistos = []
    def forward(self, **kwargs):
        if self.signature is G.AuditarSalida:
            if fallo_juez:
                raise RuntimeError("Juez sin respuesta")
            mejor = "mejorada" in kwargs["salida"]
            nota = (0.4 if regresion else 0.8) if mejor else 0.5
            return dspy.Prediction(fidelidad=nota, cobertura=nota, cumplimiento=nota, critico=False, feedback="Comprobado")
        return dspy.Prediction(respuesta="mejorada" if self.signature.instructions == "mejorada" else "base")
    monkeypatch.setattr(dspy.Predict, "forward", forward)
    class Optimizador:
        def __init__(self, **kwargs):
            assert kwargs["max_metric_calls"] == 120
            assert "auto" not in kwargs
        def compile(self, base, trainset, valset):
            vistos.extend(x.pregunta for x in trainset + valset)
            if al_compilar:
                al_compilar()
            p = base.deepcopy()
            p.signature = p.signature.with_instructions("mejorada")
            p.detailed_results = SimpleNamespace(val_aggregate_scores=[0.5, 0.8])
            return p
    monkeypatch.setattr(dspy, "GEPA", Optimizador)
    return vistos


def test_promocion_examen_separado_y_versiones_congeladas(servicio, monkeypatch):
    vistos = simular(monkeypatch)
    servicio._optimizar("consultas", "cerebro", partes())
    g = servicio.almacen.estado["gepa"][-1]
    assert g["promovido"] and g["estado"] == "terminada"
    assert not any("caso-2" in x for x in vistos)
    assert G.firma(servicio.resolver("vieja", servicio.programas.consultas)[0]).instructions == Programa.instructions
    servicio.almacen.mutar(lambda e: e["corridas"].append({"id": "nueva"}) or True)
    elegido, _, version = servicio.resolver("nueva", servicio.programas.consultas)
    assert elegido.signature.instructions == "mejorada"
    assert elegido.lm is None
    assert version == g["version"]
    servicio.control("restablecer")
    assert servicio.resolver("nueva", servicio.programas.consultas)[2] == version
    assert not servicio.almacen.estado["_gepaActivos"]
    with servicio.registro.lock:
        assert servicio.registro.db.execute("SELECT count(*) FROM usados").fetchone()[0] == 30
    assert (servicio.ruta / f"{version}.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("fallo,regresion,pausa", [(True, False, False), (False, True, False), (False, False, True)])
def test_no_promover_fallos_regresion_o_pausa(servicio, monkeypatch, fallo, regresion, pausa):
    simular(monkeypatch, fallo, regresion, (lambda: servicio.control("pausar")) if pausa else None)
    servicio._optimizar("consultas", "cerebro", partes())
    assert not servicio.almacen.estado["gepa"][-1]["promovido"]
    assert not servicio.almacen.estado.get("_gepaActivos")


def test_fuera_gateway_no_llama_ni_promueve(servicio, monkeypatch):
    vistos = simular(monkeypatch)
    servicio.modelos.cerebro.kwargs["api_base"] = "https://otro.invalid"
    servicio._optimizar("consultas", "cerebro", partes())
    assert not vistos
    assert servicio.almacen.estado["gepa"][-1]["estado"] == "fallida"


def test_division_estable_por_corrida_y_sin_duplicados():
    filas = [{"corrida": f"c{i}", "entradas": {"pregunta": f"p{i}-{j}"}} for i in range(30) for j in range(3)]
    filas += [{"corrida": "c0", "entradas": {"pregunta": "duplicada"}}, {"corrida": "c1", "entradas": {"pregunta": "duplicada"}}]
    a, b, c = G.dividir(filas)
    assert a and b and c
    assert not ({f["corrida"] for f in a} & {f["corrida"] for f in b + c})
    assert not ({f["corrida"] for f in b} & {f["corrida"] for f in c})
    assert all(f["entradas"]["pregunta"] != "duplicada" for f in a + b + c)
    assert G.dividir(filas) == G.dividir(filas)


@pytest.mark.parametrize("a,b", [([0.5]*8, [0.51]*8), ([0.5]*8, [0.3, 1, 1, 1, 1, 1, 1, 1]), ([0]*8, [float("nan")]*8), ([0]*8, [2]*8), ([], []), ([0.5]*5, [0.9]*5)])
def test_criterio_conservador(a, b):
    assert not G.aprobar(a, b)


def test_criterio_tolera_ruido_del_juez_pero_no_regresiones_claras():
    # Un caso una décima peor no tira la promoción; uno dos décimas peor, sí.
    assert G.aprobar([0.5] * 8, [0.4] + [0.9] * 7)
    assert not G.aprobar([0.5] * 8, [0.3] + [0.9] * 7)


def test_secretos_y_registro_privado(servicio):
    servicio.registro.guardar("prueba", {"api_key": "NO_GUARDAR", "texto": "persona@example.test", "tokens_entrada": 42})
    servicio.registro.flush()
    texto = servicio.registro.db.execute("SELECT json FROM trazas").fetchone()[0]
    assert "NO_GUARDAR" not in texto and "persona@" not in texto
    assert json.loads(texto)["tokens_entrada"] == 42
    assert "trazas" not in servicio.almacen.instantanea()


def test_permisos_y_corrida_activa_excluidos(servicio, monkeypatch):
    def fallo(*args):
        pytest.fail("No hay datos elegibles suficientes")
    monkeypatch.setattr(servicio, "_optimizar", fallo)
    assert not servicio.ciclo()
    assert not G.permitido({"datasets": [{"clasificacion": "personas", "procedencia": {"permiteLlmTerceros": True}}]})
    # Un dataset público sin permiso de LLM de terceros no excluye la investigación para los
    # programas de literatura (no ven filas); sí la excluiría para un programa que las viera.
    assert G.permitido({"datasets": [{"clasificacion": "publico"}]})
    assert not G.permitido({"datasets": [{"clasificacion": "publico"}]}, "codigo")
    assert G.permitido({"datasets": []})


def test_traza_contexto_conector_y_limpieza(servicio):
    async def ejecutar(ctx, paso):
        servicio.observar_conector("conector", {"consulta": "simulada", "resultado": []})
        raise ValueError("Fallo simulado")
    with pytest.raises(ValueError):
        asyncio.run(servicio.ejecutar_paso(SimpleNamespace(corrida_id="vieja", numero=1), ejecutar, {"id": "paso"}))
    assert G.CONTEXTO.get() is None
    servicio.registro.flush()
    assert servicio.registro.db.execute("SELECT corrida FROM trazas").fetchone()[0] == "vieja"


def test_archivo_alterado_no_cambia_en_silencio(servicio):
    version = "a" * 64
    servicio.almacen.mutar(lambda e: e["corridas"][0].update(_gepaVersiones={"consultas": version}) or True)
    # No se sustituye en silencio ni se deja la corrida muerta: vuelve a la base, lo anota
    # en la corrida y deja una incidencia visible.
    elegido, nombre, ver = servicio.resolver("vieja", servicio.programas.consultas)
    assert ver == "base" and elegido is servicio.programas.consultas
    e = servicio.almacen.estado
    assert e["corridas"][0]["_gepaVersiones"]["consultas"] is None
    assert any(ev["tipo"] == "incidencia" and "integridad" in ev["texto"] for ev in e["eventos"])


def test_control_http_autenticado_y_solo_administracion(servicio):
    import sqlite3
    from fastapi.testclient import TestClient
    from rosa.servidor import crear_app
    app = crear_app(servicio.almacen)
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE TABLE cuentas(correo TEXT)")
    db.execute("INSERT INTO cuentas VALUES('admin@alzheimerproject.com')")
    app.state.acceso = SimpleNamespace(db=db, usuario=lambda token: {"admin": "admin@alzheimerproject.com", "otra": "otra@alzheimerproject.com"}.get(token))
    servicio.almacen.gepa_servicio = servicio
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    try:
        assert c.post("/api/gepa/pausar", headers={"X-Rosa": "1"}).status_code == 401
        c.cookies.set("rosa_sesion", "otra")
        assert c.post("/api/gepa/pausar", headers={"X-Rosa": "1"}).status_code == 403
        c.cookies.set("rosa_sesion", "admin")
        assert c.post("/api/gepa/pausar").status_code == 403
        assert c.post("/api/gepa/pausar", headers={"X-Rosa": "1"}).status_code == 200
        assert servicio._detenido()
        assert c.post("/api/gepa/reanudar", headers={"X-Rosa": "1"}).status_code == 200
        assert not servicio._detenido()
        assert c.post("/api/gepa/inventado", headers={"X-Rosa": "1"}).status_code == 400
    finally:
        c.close()
        db.close()


def test_captura_prompt_respuesta_y_error_sin_contaminar_contexto(servicio, monkeypatch):
    async def aforward(self, **kwargs):
        servicio.trazador.on_lm_start("llamada", servicio.modelos.cerebro, {"messages": [{"role": "user", "content": kwargs["pregunta"]}]})
        servicio.trazador.on_lm_end("llamada", ["respuesta"])
        return dspy.Prediction(respuesta="respuesta")
    monkeypatch.setattr(dspy.Predict, "aforward", aforward)
    ctx = SimpleNamespace(corrida_id="vieja", numero=1, inv=lambda: {"datasets": []})
    pred = asyncio.run(servicio.llamar(ctx, servicio.programas.consultas, servicio.modelos.cerebro, {"pregunta": "prueba"}))
    assert pred.respuesta == "respuesta"
    servicio.registro.flush()
    traza = servicio.registro.filas("consultas")[0]
    assert traza["entradas"] == {"pregunta": "prueba"} and traza["ok"]
    assert traza["version"] == "base"
    modelo = json.loads(servicio.registro.db.execute("SELECT json FROM trazas WHERE tipo='modelo'").fetchone()[0])
    assert modelo["traza"] == traza["traza"] and modelo["prompt"]["messages"][0]["content"] == "prueba"
    assert G.CONTEXTO.get() is None
