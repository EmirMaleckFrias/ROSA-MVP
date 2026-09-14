"""Acceso sin contraseña: correo corporativo verificado y sesión revocable.

Solo se persisten hashes de los tokens de acceso y de sesión. La cuenta se
crea al confirmar el enlace, nunca al escribir una dirección en el formulario.
"""
from __future__ import annotations

import hashlib
import secrets
import time

from rosa.correo import direccion

COOKIE = "rosa_sesion"
DURACION = 12 * 3600


def huella(token):
    return hashlib.sha256(token.encode()).hexdigest()


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

    def solicitar(self, email, ip):
        email = direccion(email.strip().lower())
        if email.rsplit("@", 1)[1] != "alzheimerproject.com":
            raise ValueError("Solo se admiten cuentas @alzheimerproject.com")
        c = self.correo._config()
        if not c["clave"] or not c["remitente"]:
            raise ValueError("El administrador debe conectar el servicio de correo antes de iniciar sesión")
        ahora = time.time()
        with self.db:
            self.db.execute("DELETE FROM limites_acceso WHERE t<?", (ahora - 3600,))
            self.db.execute("DELETE FROM enlaces WHERE vence<?", (ahora,))
            self.db.execute("DELETE FROM sesiones WHERE vence<?", (ahora,))
            cuenta = self.db.execute("SELECT COUNT(*) FROM limites_acceso WHERE correo=? AND t>?", (email, ahora - 900)).fetchone()[0]
            desde_ip = self.db.execute("SELECT COUNT(*) FROM limites_acceso WHERE ip=?", (ip,)).fetchone()[0]
            total = self.db.execute("SELECT COUNT(*) FROM limites_acceso").fetchone()[0]
            if cuenta >= 3 or desde_ip >= 20 or total >= 100:
                raise ValueError("Demasiados intentos. Espera unos minutos antes de volver a pedir el enlace")
            token = secrets.token_urlsafe(32)
            self.db.execute("INSERT INTO limites_acceso VALUES (?,?,?)", (email, ip, ahora))
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
            self.db.execute("INSERT OR IGNORE INTO cuentas VALUES (?,?)", (email, ahora))
            self.db.execute("DELETE FROM enlaces WHERE correo=?", (email,))
            sesion = secrets.token_urlsafe(32)
            self.db.execute("INSERT INTO sesiones VALUES (?,?,?)", (huella(sesion), email, ahora + DURACION))
        return sesion, email

    def usuario(self, token):
        if not token or len(token) > 100:
            return None
        fila = self.db.execute("SELECT correo FROM sesiones WHERE hash=? AND vence>?", (huella(token), time.time())).fetchone()
        return fila[0] if fila else None

    def salir(self, token):
        with self.db:
            self.db.execute("DELETE FROM sesiones WHERE hash=?", (huella(token or ""),))
