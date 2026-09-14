"""Guardias del servidor: cabecera X-Rosa en las escrituras, acciones internas,
cuerpos inválidos, hosts permitidos, ruta estática sin salto de directorio."""

import tempfile
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rosa import config
from rosa.estado.almacen import Almacen
from rosa.servidor import crear_app


@pytest.fixture
def cliente(monkeypatch):
    raiz = Path(tempfile.mkdtemp())
    monkeypatch.setattr(config, "RAIZ", raiz)
    dist = raiz / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>rosa</html>")
    (raiz / "secreto.txt").write_text("no debe salir")
    monkeypatch.setattr(config, "FRONTEND_DIST", dist)
    al = Almacen(raiz / "t.db")
    app = crear_app(al)
    # Estos tests aíslan las rutas del dominio. El acceso real se prueba en test_acceso_correo.
    app.state.acceso = SimpleNamespace(usuario=lambda token: 'test@alzheimerproject.com' if token == 'sesion-test' else None)
    app.state.correo = SimpleNamespace(preferencias=lambda email: al.instantanea()['avisos'])
    return TestClient(app, base_url="http://127.0.0.1:8765", cookies={'rosa_sesion': 'sesion-test'}), al


def test_escrituras_exigen_cabecera_y_json(cliente):
    c, al = cliente
    r = c.post("/api/acciones/anadirCriterio", json={"texto": "x"})
    assert r.status_code == 403  # sin X-Rosa
    r = c.post("/api/acciones/anadirCriterio", content="no es json", headers={"X-Rosa": "1", "Content-Type": "application/json"})
    assert r.status_code == 400
    r = c.post("/api/acciones/anadirCriterio", content="{}", headers={"X-Rosa": "1", "Content-Type": "text/plain"})
    assert r.status_code == 415
    r = c.post("/api/acciones/anadirCriterio", json={"texto": "un criterio nuevo"}, headers={"X-Rosa": "1"})
    assert r.status_code == 200 and r.json()["ok"] is True
    # Argumentos que el reducer rechaza con excepcion: 400 y estado intacto.
    v = al.version
    r = c.post("/api/acciones/ampliarPresupuesto", content='{"corrida_id": "c", "nuevo_limite": 1e999}', headers={"X-Rosa": "1", "Content-Type": "application/json"})
    assert r.status_code in (200, 400) and al.version == v
    # El sello de tiempo lo pone el servidor, no el cliente.
    r = c.post("/api/acciones/crearInvestigacion", json={"datos": {"titulo": "T", "objetivo": "O", "condicionParada": "1 iteraciones"}, "ahora": 0}, headers={"X-Rosa": "1"})
    assert r.status_code == 200 and al.estado["investigaciones"][0]["creadaEn"] > 1_000_000


def test_acciones_internas_y_host(cliente):
    c, al = cliente
    r = c.post("/api/acciones/registrarEvaluacion", json={"evaluacion": {}, "quien": "x"}, headers={"X-Rosa": "1"})
    assert r.status_code == 403
    token = (config.RAIZ / "datos" / "_token_interno").read_text().strip()
    r = c.post("/api/acciones/registrarEvaluacion", json={"evaluacion": {"tipo": "otro"}, "quien": "x"}, headers={"X-Rosa-Interno": token})
    assert r.status_code == 200 and r.json()["ok"] is False
    r = c.get("/api/salud", headers={"Host": "evil.example"})
    assert r.status_code == 400


def test_ruta_estatica_no_sale_de_dist(cliente):
    c, _ = cliente
    assert c.get("/").status_code == 200
    for ruta in ("/../secreto.txt", "/%2e%2e/secreto.txt", "/..%2Fsecreto.txt", "/assets/../../secreto.txt"):
        r = c.get(ruta)
        assert "no debe salir" not in r.text, ruta


def test_presupuesto_corta_antes_de_llamar():
    from rosa.modulos.contador import presupuesto_ok

    al = Almacen(Path(tempfile.mkdtemp()) / "t.db")
    inv = al.aplicar("crearInvestigacion", {"datos": {"titulo": "T", "objetivo": "O", "condicionParada": "1 iteraciones"}, "id_": "inv-t"})
    c_id = al.aplicar("iniciarCorrida", {"investigacion_id": inv})
    assert presupuesto_ok(al, c_id) is True
    al.mutar(lambda e: next(c for c in e["corridas"] if c["id"] == c_id)["gasto"].update(llamadas=10**6) or True)
    assert presupuesto_ok(al, c_id) is False


def test_prisma_rocrate_costes_e_integridad_responden(cliente):
    """Los endpoints nuevos se prueban de punta a punta: un import que falte
    solo se ve al llamarlos."""
    import io
    import json
    import zipfile

    from rosa.estado import plantilla as P

    c, al = cliente
    r = c.post("/api/acciones/crearInvestigacion", json={"datos": {"titulo": "T", "objetivo": "O", "condicionParada": "1 iteraciones"}}, headers={"X-Rosa": "1"})
    assert r.status_code == 200
    inv_id = al.estado["investigaciones"][0]["id"]

    def sembrar(e):
        cor = P.nueva_corrida(inv_id, 1, 1)
        cor["busqueda"]["consultas"] = [{"base": "PubMed", "consulta": "GFAP", "fecha": 1000, "resultados": 3, "iteracion": 1, "tema": "t"}]
        e["corridas"].append(cor)
        h = P.nueva_hipotesis(inv_id, 1, 1, titulo="H", enunciado="E", mecanismo="M")
        e["hipotesis"].append(h)
        return True

    al.mutar(sembrar, "prueba")
    cor_id = al.estado["corridas"][0]["id"]
    hip_id = al.estado["hipotesis"][0]["id"]
    r = c.get(f"/api/corridas/{cor_id}/prisma")
    assert r.status_code == 200 and r.json()["prisma"] == "2020" and r.json()["flujo"]["database_results"] == 3
    r = c.get(f"/api/hipotesis/{hip_id}/rocrate")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/zip")
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert "ro-crate-metadata.json" in z.namelist() and json.loads(z.read("prov.json"))["agent"]
    r = c.get(f"/api/investigaciones/{inv_id}/costes")
    assert r.status_code == 200 and r.json()["hipotesis"] == 1
    r = c.get("/api/registro/integridad")
    assert r.status_code == 200 and r.json()["ok"]
    r = c.get("/api/calidad/acuerdo")
    assert r.status_code == 200 and r.json()["casos"] == 0
    assert c.get("/api/corridas/nada/prisma").status_code == 404 and c.get("/api/hipotesis/nada/rocrate").status_code == 404
