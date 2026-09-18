"""El transporte SMTP del correo de ROSA2018 (Google Workspace u otro servidor),
con un servidor SMTP falso: sin red, sin contraseñas reales."""
import asyncio
import json
import smtplib

import pytest

from rosa import correo as modulo
from rosa.correo import Correo
from rosa.estado.almacen import Almacen

SMTP = {'proveedor': 'smtp', 'smtpServidor': 'smtp.gmail.com', 'smtpPuerto': 587, 'smtpUsuario': 'rosa@alzheimerproject.com',
        'remitente': 'rosa@alzheimerproject.com', 'clave': 'abcd efgh ijkl mnop'.replace(' ', ''), 'url': 'http://localhost:8765'}


class ServidorFalso:
    """Registra lo que ROSA2018 hace con el servidor y falla como se le pida."""
    enviados = []
    fallo = None

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port
        self.pasos = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.pasos.append('quit')

    def ehlo(self):
        self.pasos.append('ehlo')

    def starttls(self):
        self.pasos.append('starttls')

    def login(self, usuario, clave):
        self.pasos.append('login')
        if ServidorFalso.fallo == 'auth':
            raise smtplib.SMTPAuthenticationError(535, b'bad credentials')
        assert usuario == SMTP['smtpUsuario'] and clave == SMTP['clave']

    def send_message(self, mensaje):
        if ServidorFalso.fallo == 'espera':
            raise smtplib.SMTPResponseException(421, b'try later')
        if ServidorFalso.fallo == 'red':
            raise OSError('sin red')
        self.pasos.append('send')
        ServidorFalso.enviados.append((mensaje, self))


@pytest.fixture
def smtp_falso(monkeypatch):
    ServidorFalso.enviados = []
    ServidorFalso.fallo = None
    monkeypatch.setattr(modulo.smtplib, 'SMTP', ServidorFalso)
    monkeypatch.setattr(modulo.smtplib, 'SMTP_SSL', ServidorFalso)
    return ServidorFalso


@pytest.fixture
def servicio(tmp_path):
    al = Almacen(tmp_path / 'rosa.db')
    c = Correo(al)
    yield c
    c.cerrar()
    al.cerrar()


def enviar(c):
    asyncio.run(c.enviar_uno(None))
    return c.db.execute('SELECT estado,error,proveedor,intentos FROM cola ORDER BY rowid DESC LIMIT 1').fetchone()


def test_configuracion_smtp_valida_y_configurado_exige_servidor_y_usuario(servicio):
    c = servicio
    c.configurar({'proveedor': 'smtp', 'remitente': SMTP['remitente'], 'clave': SMTP['clave'], 'url': SMTP['url']})
    assert not c.estado()['configurado']
    c.configurar({'smtpServidor': 'smtp.gmail.com', 'smtpUsuario': SMTP['smtpUsuario']})
    assert c.estado()['configurado'] and c.estado()['proveedor'] == 'smtp' and 'clave' not in c.estado()
    with pytest.raises(ValueError):
        c.configurar({'proveedor': 'paloma'})
    with pytest.raises(ValueError):
        c.configurar({'smtpServidor': 'smtp.gmail.com/../x'})
    with pytest.raises(ValueError):
        c.configurar({'smtpPuerto': 70000})
    with pytest.raises(ValueError):
        c.configurar({'smtpPuerto': '587'})


def test_envia_por_starttls_con_message_id_y_marca_aceptado(servicio, smtp_falso):
    c = servicio
    c.configurar(SMTP)
    ident = c.prueba('persona@alzheimerproject.com')
    fila = enviar(c)
    assert fila['estado'] == 'aceptado' and fila['proveedor'] == f'<{ident}@rosa.alzheimerproject>' and fila['error'] is None
    mensaje, servidor = smtp_falso.enviados[0]
    assert servidor.host == 'smtp.gmail.com' and servidor.port == 587
    assert servidor.pasos == ['ehlo', 'starttls', 'ehlo', 'login', 'send', 'quit']
    assert mensaje['To'] == 'persona@alzheimerproject.com' and mensaje['From'] == SMTP['remitente']
    assert mensaje['Subject'].startswith('ROSA2018: ') and 'No ha utilizado ningún modelo de IA' in mensaje.get_content()


def test_puerto_465_usa_tls_implicito(servicio, smtp_falso):
    c = servicio
    c.configurar({**SMTP, 'smtpPuerto': 465})
    c.prueba('persona@alzheimerproject.com')
    assert enviar(c)['estado'] == 'aceptado'
    _, servidor = smtp_falso.enviados[0]
    assert servidor.port == 465 and 'starttls' not in servidor.pasos


def test_credenciales_malas_no_se_reintentan_y_no_filtran_la_clave(servicio, smtp_falso):
    c = servicio
    c.configurar(SMTP)
    c.prueba('persona@alzheimerproject.com')
    smtp_falso.fallo = 'auth'
    fila = enviar(c)
    assert fila['estado'] == 'fallido' and 'contraseña de aplicación' in fila['error'] and SMTP['clave'] not in fila['error']


def test_espera_del_servidor_y_red_caida_se_reintentan(servicio, smtp_falso):
    c = servicio
    c.configurar(SMTP)
    c.prueba('persona@alzheimerproject.com')
    smtp_falso.fallo = 'espera'
    fila = enviar(c)
    assert fila['estado'] == 'pendiente' and fila['intentos'] == 1
    c.db.execute("UPDATE cola SET proximo=0")
    smtp_falso.fallo = 'red'
    fila = enviar(c)
    assert fila['estado'] == 'pendiente' and fila['intentos'] == 2
    c.db.execute("UPDATE cola SET proximo=0")
    smtp_falso.fallo = None
    assert enviar(c)['estado'] == 'aceptado'


def test_resend_sigue_igual_sin_tocar_smtp(servicio, smtp_falso):
    import httpx

    c = servicio
    c.configurar({'remitente': 'rosa@alzheimerproject.com', 'clave': 'clave-de-prueba', 'url': 'http://localhost:8765'})
    assert c.estado()['proveedor'] == 'resend' and c.estado()['configurado']
    c.prueba('persona@alzheimerproject.com')

    async def correr():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'id': 'ok'}))) as cliente:
            await c.enviar_uno(cliente)

    asyncio.run(correr())
    assert c.db.execute('SELECT estado FROM cola').fetchone()[0] == 'aceptado' and smtp_falso.enviados == []
    assert json.loads(c.db.execute('SELECT json FROM ajustes').fetchone()[0])['proveedor'] == 'resend'
