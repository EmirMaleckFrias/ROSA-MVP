"""Pruebas del único acceso interactivo de ROSA2018: correo y contraseña."""
import hashlib

import pytest
from fastapi.testclient import TestClient

from rosa import config
from rosa.acceso import Acceso
from rosa.correo import Correo
from rosa.estado.almacen import Almacen
from rosa.servidor import crear_app


CORREO = "persona@alzheimerproject.com"
CLAVE = "clave de prueba segura"
SAL = b"rosa-acceso-contrasena-v1"


@pytest.fixture
def acceso(tmp_path, monkeypatch):
    huella = hashlib.scrypt(CLAVE.encode(), salt=SAL, n=2**14, r=8, p=1, dklen=32).hex()
    monkeypatch.setattr(config, "ROSA_LOGIN_EMAIL", CORREO)
    monkeypatch.setattr(config, "ROSA_LOGIN_PASSWORD_HASH", huella)
    almacen = Almacen(tmp_path / "rosa.db")
    correo = Correo(almacen)
    yield Acceso(correo)
    correo.cerrar()
    almacen.cerrar()


def test_acepta_solo_la_cuenta_y_contrasena_configuradas(acceso):
    token, correo = acceso.entrar_con_contrasena(CORREO.upper(), CLAVE, "127.0.0.1")
    assert correo == CORREO
    assert acceso.usuario(token) == CORREO


@pytest.mark.parametrize("correo,contrasena", [
    ("otra@alzheimerproject.com", CLAVE),
    (CORREO, "contraseña incorrecta"),
])
def test_no_revela_si_fallo_el_correo_o_la_contrasena(acceso, correo, contrasena):
    with pytest.raises(ValueError, match="Correo o contraseña incorrectos"):
        acceso.entrar_con_contrasena(correo, contrasena, "127.0.0.1")


def test_entrada_sin_verificar_esta_cerrada(acceso):
    with pytest.raises(ValueError, match="desactivada"):
        acceso.entrar_sin_verificar(CORREO)


def test_endpoint_crea_cookie_solo_para_las_credenciales_validas(tmp_path, monkeypatch):
    huella = hashlib.scrypt(CLAVE.encode(), salt=SAL, n=2**14, r=8, p=1, dklen=32).hex()
    monkeypatch.setattr(config, "RAIZ", tmp_path)
    monkeypatch.setattr(config, "ROSA_LOGIN_EMAIL", CORREO)
    monkeypatch.setattr(config, "ROSA_LOGIN_PASSWORD_HASH", huella)
    monkeypatch.setattr(config, "ROSA_TOKEN", "")

    async def sin_red(self):
        import asyncio
        await asyncio.Event().wait()

    monkeypatch.setattr(Correo, "correr", sin_red)
    almacen = Almacen(tmp_path / "web.db")
    with TestClient(crear_app(almacen), base_url="http://localhost") as cliente:
        mala = cliente.post("/api/acceso/entrar", json={"correo": CORREO, "contrasena": "mal"}, headers={"X-Rosa": "1"})
        buena = cliente.post("/api/acceso/entrar", json={"correo": CORREO, "contrasena": CLAVE}, headers={"X-Rosa": "1"})
        assert mala.status_code == 401
        assert buena.status_code == 200 and "HttpOnly" in buena.headers["set-cookie"]
        assert cliente.get("/api/acceso/estado").json()["correo"] == CORREO
        assert cliente.post("/api/acceso/entrar_sin_verificar", json={"correo": CORREO}, headers={"X-Rosa": "1"}).status_code == 410
    almacen.cerrar()
