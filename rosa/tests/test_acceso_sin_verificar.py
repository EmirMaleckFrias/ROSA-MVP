"""Entrada sin verificación mientras no hay proveedor de correo (pedida el 15
de septiembre de 2026): abierta al dominio corporativo, cerrada en cuanto se
configura el correo."""
import pytest
from fastapi.testclient import TestClient

from rosa import config
from rosa.acceso import Acceso
from rosa.correo import Correo
from rosa.estado.almacen import Almacen
from rosa.servidor import crear_app

EMAIL = 'persona@alzheimerproject.com'
OTRO = 'equipo@alzheimerproject.com'
CONFIG = {'remitente': 'rosa@alzheimerproject.com', 'clave': 'clave-de-prueba', 'url': 'http://localhost:5174'}


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'RAIZ', tmp_path)
    monkeypatch.setattr(config, 'HOST', '127.0.0.1')

    async def sin_red(self):
        import asyncio
        await asyncio.Event().wait()

    monkeypatch.setattr(Correo, 'correr', sin_red)
    al = Almacen(tmp_path / 'web.db')
    app = crear_app(al)
    with TestClient(app, base_url='http://localhost', client=('10.0.0.7', 12345)) as cliente:
        yield cliente, app, al
    al.cerrar()


def test_sin_correo_configurado_entra_cualquiera_del_dominio_y_se_cierra_al_configurar(tmp_path):
    al = Almacen(tmp_path / 'rosa.db')
    c = Correo(al)
    a = Acceso(c)
    with pytest.raises(ValueError):
        a.entrar_sin_verificar('alguien@gmail.com')
    token, email = a.entrar_sin_verificar(EMAIL.upper())
    assert email == EMAIL and a.usuario(token) == EMAIL
    token2, _ = a.entrar_sin_verificar(OTRO)
    assert a.usuario(token2) == OTRO and c.db.execute('SELECT COUNT(*) FROM cuentas').fetchone()[0] == 2
    c.configurar(CONFIG)
    with pytest.raises(ValueError):
        a.entrar_sin_verificar(EMAIL)
    assert a.usuario(token) == EMAIL  # las sesiones ya abiertas siguen valiendo hasta que caduquen
    c.cerrar()
    al.cerrar()


def test_web_entra_sin_verificar_desde_cualquier_equipo_y_luego_solo_con_enlace(web, monkeypatch):
    cliente, app, al = web
    monkeypatch.delenv('ROSA_ADMIN', raising=False)
    monkeypatch.delattr(config, 'ROSA_ADMIN', raising=False)
    assert cliente.get('/api/estado').status_code == 401
    assert cliente.post('/api/acceso/entrar_sin_verificar', json={'correo': 'x@gmail.com'}, headers={'X-Rosa': '1'}).status_code == 403
    r = cliente.post('/api/acceso/entrar_sin_verificar', json={'correo': EMAIL}, headers={'X-Rosa': '1'})
    assert r.status_code == 200 and r.json()['verificada'] is False and 'HttpOnly' in r.headers['set-cookie']
    estado = cliente.get('/api/acceso/estado').json()
    # Una cuenta que entra sin verificar nunca administra (S-21): administra ROSA_ADMIN o la primera confirmada por enlace.
    assert estado['correo'] == EMAIL and not estado['administrador']
    assert cliente.get('/api/estado').status_code == 200
    # Sin la cabecera X-Rosa (una web ajena) no entra nadie.
    assert cliente.post('/api/acceso/entrar_sin_verificar', json={'correo': OTRO}).status_code == 403
    # Al configurar el correo, la puerta sin verificar se cierra. Configurarlo exige administrar:
    # una cuenta sin verificar no administra, así que hace falta ROSA_ADMIN (S-21).
    assert cliente.post('/api/correo/configuracion', json=CONFIG, headers={'X-Rosa': '1'}).status_code == 403
    monkeypatch.setenv('ROSA_ADMIN', EMAIL)
    assert cliente.post('/api/correo/configuracion', json=CONFIG, headers={'X-Rosa': '1'}).status_code == 200
    assert cliente.post('/api/acceso/salir', json={}, headers={'X-Rosa': '1'}).status_code == 200
    assert cliente.post('/api/acceso/entrar_sin_verificar', json={'correo': OTRO}, headers={'X-Rosa': '1'}).status_code == 403
    assert cliente.get('/api/estado').status_code == 401
