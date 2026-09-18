"""Acceso sin contraseña: correo corporativo verificado y sesión revocable.

Solo se persisten hashes de los tokens de acceso y de sesión. La cuenta se
crea al confirmar el enlace, nunca al escribir una dirección en el formulario.

Administración (S-21, 17 de septiembre de 2026): es administradora la cuenta
que diga `ROSA_ADMIN` en .env (lo pone el ingeniero que opera Rosa, como
`ROSA_TOKEN`) o, si falta, la primera cuenta confirmada por enlace de correo.
Una cuenta creada por la puerta sin verificar nunca hereda el papel, aunque
sea la primera: entrar por esa puerta solo exige escribir una dirección.
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
        """Entrada sin enlace de correo, solo mientras no haya proveedor de
        correo configurado (pedida por Emir el 15 de septiembre de 2026 para
        que el equipo pueda entrar antes de conectar el correo). Se exige el
        dominio corporativo; la cuenta se crea o se reutiliza y la sesión
        dura lo mismo que una verificada. En cuanto se configura el correo,
        esta puerta se cierra y solo vale el enlace. No hay más comprobación
        de identidad que la dirección escrita: es acceso abierto al dominio,
        por eso lleva los mismos topes de intentos que `solicitar`, purga las
        sesiones caducadas y la cuenta que crea queda sin verificar (nunca
        administra)."""
        email = self._dominio_corporativo(email)
        c = self.correo._config()
        if c["clave"] and c["remitente"]:
            raise ValueError("El correo ya está configurado: entra con el enlace que llega a tu buzón")
        ahora = time.time()
        with self.db:
            self._limitar_y_purgar(email, ip, ahora)
            self.db.execute("INSERT OR IGNORE INTO cuentas(correo, creada) VALUES (?,?)", (email, ahora))
            sesion = secrets.token_urlsafe(32)
            self.db.execute("INSERT INTO sesiones VALUES (?,?,?)", (huella(sesion), email, ahora + DURACION))
        return sesion, email

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
