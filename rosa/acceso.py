"""Acceso corporativo con contraseña y sesión revocable.

Solo se persisten hashes de las sesiones. La contraseña se compara con una
huella scrypt configurada fuera del repositorio, en ``.env``.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time

from rosa import config
from rosa.correo import direccion

COOKIE = "rosa_sesion"
DURACION = 12 * 3600
DOMINIO = "alzheimerproject.com"
_SAL_CONTRASENA = b"rosa-acceso-contrasena-v1"


def huella(token):
    return hashlib.sha256(token.encode()).hexdigest()


def correo_admin():
    """La cuenta administradora fijada por configuración (ROSA_ADMIN), en
    minúsculas, o cadena vacía. Se lee de `config` si ya la expone y, si no,
    del entorno."""
    valor = getattr(config, "ROSA_ADMIN", None)
    if valor is None:
        valor = os.environ.get("ROSA_ADMIN", "")
    return str(valor or "").strip().lower()


def _credenciales_configuradas():
    """Devuelve el correo y huella configurados, o dos cadenas vacías.

    Se acepta solo una huella SHA-256/scrypt de 32 bytes en hexadecimal. Así,
    un .env incompleto no abre por accidente una ruta de autenticación débil.
    """
    email = str(getattr(config, "ROSA_LOGIN_EMAIL", "") or "").strip().lower()
    huella_configurada = str(getattr(config, "ROSA_LOGIN_PASSWORD_HASH", "") or "").strip().lower()
    if not email or len(huella_configurada) != 64:
        return "", ""
    try:
        bytes.fromhex(huella_configurada)
    except ValueError:
        return "", ""
    return email, huella_configurada


def _huella_contrasena(contrasena):
    if not isinstance(contrasena, str) or not 1 <= len(contrasena) <= 256:
        return ""
    return hashlib.scrypt(contrasena.encode("utf-8"), salt=_SAL_CONTRASENA, n=2**14, r=8, p=1, dklen=32).hex()


class Acceso:
    def __init__(self, correo):
        self.correo = correo
        self.db = correo.db
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS cuentas (correo TEXT PRIMARY KEY, creada REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS enlaces (hash TEXT PRIMARY KEY, correo TEXT NOT NULL, vence REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS sesiones (hash TEXT PRIMARY KEY, correo TEXT NOT NULL, vence REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS limites_acceso (correo TEXT NOT NULL, ip TEXT NOT NULL, t REAL NOT NULL);
        """)
        # Cuándo se confirmó la cuenta por enlace (NULL si entró sin verificar).
        columnas = {fila[1] for fila in self.db.execute("PRAGMA table_info(cuentas)")}
        if "verificada" not in columnas:
            with self.db:
                self.db.execute("ALTER TABLE cuentas ADD COLUMN verificada REAL")

    def _dominio_corporativo(self, email):
        email = direccion(email.strip().lower())
        if email.rsplit("@", 1)[1] != DOMINIO:
            raise ValueError(f"Solo se admiten cuentas @{DOMINIO}")
        return email

    def _limitar_y_purgar(self, email, ip, ahora):
        """Purga enlaces y sesiones caducados y aplica los topes de intentos (3
        por correo en 15 minutos, 20 por IP y 100 en total por hora). Lo
        comparten `solicitar` y `entrar_sin_verificar`. Debe llamarse dentro de
        una transacción abierta."""
        self.db.execute("DELETE FROM limites_acceso WHERE t<?", (ahora - 3600,))
        self.db.execute("DELETE FROM enlaces WHERE vence<?", (ahora,))
        self.db.execute("DELETE FROM sesiones WHERE vence<?", (ahora,))
        cuenta = self.db.execute("SELECT COUNT(*) FROM limites_acceso WHERE correo=? AND t>?", (email, ahora - 900)).fetchone()[0]
        desde_ip = self.db.execute("SELECT COUNT(*) FROM limites_acceso WHERE ip=?", (ip,)).fetchone()[0]
        total = self.db.execute("SELECT COUNT(*) FROM limites_acceso").fetchone()[0]
        if cuenta >= 3 or desde_ip >= 20 or total >= 100:
            raise ValueError("Demasiados intentos. Espera unos minutos antes de volver a intentarlo")
        self.db.execute("INSERT INTO limites_acceso VALUES (?,?,?)", (email, ip, ahora))

    def solicitar(self, email, ip):
        email = self._dominio_corporativo(email)
        c = self.correo._config()
        if not c["clave"] or not c["remitente"]:
            raise ValueError("El administrador debe conectar el servicio de correo antes de iniciar sesión")
        ahora = time.time()
        with self.db:
            self._limitar_y_purgar(email, ip, ahora)
            token = secrets.token_urlsafe(32)
            self.db.execute("INSERT INTO enlaces VALUES (?,?,?)", (huella(token), email, ahora + 900))
            self.correo._encolar("acceso", email,
                "Confirma tu acceso a Rosa con este enlace de un solo uso (caduca en 15 minutos):\n\n"
                + c["url"].rstrip("/") + "/#acceso=" + token + "\n\n"
                "Si no lo has solicitado, no abras el enlace. Nadie puede entrar sin confirmar tu correo.", ahora)

    def entrar_con_contrasena(self, email, contrasena, ip="desconocida"):
        """Crea una sesión solo si coincide la cuenta corporativa configurada.

        El mismo mensaje se usa para correo y contraseña incorrectos para no
        revelar qué cuentas existen. Los límites se aplican antes de comparar
        la huella para contener intentos automatizados.
        """
        email = self._dominio_corporativo(email)
        configurado, esperada = _credenciales_configuradas()
        ahora = time.time()
        with self.db:
            self._limitar_y_purgar(email, ip, ahora)
            recibida = _huella_contrasena(contrasena)
            coincide = bool(configurado and secrets.compare_digest(email, configurado) and recibida and secrets.compare_digest(recibida, esperada))
            if not coincide:
                raise ValueError("Correo o contraseña incorrectos")
            self.db.execute("INSERT OR IGNORE INTO cuentas(correo, creada) VALUES (?,?)", (email, ahora))
            self.db.execute("UPDATE cuentas SET verificada=COALESCE(verificada, ?) WHERE correo=?", (ahora, email))
            sesion = secrets.token_urlsafe(32)
            self.db.execute("INSERT INTO sesiones VALUES (?,?,?)", (huella(sesion), email, ahora + DURACION))
        return sesion, email

    def confirmar(self, token):
        if not isinstance(token, str) or not 30 <= len(token) <= 100:
            raise ValueError("Enlace inválido o caducado; solicita otro")
        ahora = time.time()
        with self.db:
            fila = self.db.execute("DELETE FROM enlaces WHERE hash=? AND vence>? RETURNING correo", (huella(token), ahora)).fetchone()
            if not fila:
                raise ValueError("Enlace inválido, ya utilizado o caducado; solicita otro")
            email = fila[0]
            self.db.execute("INSERT OR IGNORE INTO cuentas(correo, creada) VALUES (?,?)", (email, ahora))
            # La confirmación por enlace es lo que cuenta para administrar (S-21).
            self.db.execute("UPDATE cuentas SET verificada=COALESCE(verificada, ?) WHERE correo=?", (ahora, email))
            self.db.execute("DELETE FROM enlaces WHERE correo=?", (email,))
            sesion = secrets.token_urlsafe(32)
            self.db.execute("INSERT INTO sesiones VALUES (?,?,?)", (huella(sesion), email, ahora + DURACION))
        return sesion, email

    def entrar_sin_verificar(self, email, ip="desconocida"):
        """Compatibilidad explícitamente cerrada para la antigua puerta local."""
        raise ValueError("La entrada sin verificación está desactivada")

    def es_admin(self, email):
        """Administra la cuenta de ROSA_ADMIN o, si no está configurada, la
        primera confirmada por enlace. Nunca una que entró sin verificar."""
        if not email:
            return False
        fijado = correo_admin()
        if fijado:
            return str(email).strip().lower() == fijado
        fila = self.db.execute("SELECT correo FROM cuentas WHERE verificada IS NOT NULL ORDER BY verificada, rowid LIMIT 1").fetchone()
        return bool(fila and fila[0] == email)

    def usuario(self, token):
        if not token or len(token) > 100:
            return None
        fila = self.db.execute("SELECT correo FROM sesiones WHERE hash=? AND vence>?", (huella(token), time.time())).fetchone()
        return fila[0] if fila else None

    def salir(self, token):
        with self.db:
            self.db.execute("DELETE FROM sesiones WHERE hash=?", (huella(token or ""),))
