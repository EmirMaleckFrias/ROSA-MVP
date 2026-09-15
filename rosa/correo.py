"""Avisos transaccionales sin modelos. SQLite privado, fuera del espejo.

Dos transportes, a elegir en la configuración (`proveedor`):
- "resend": la API HTTP de Resend, con clave de idempotencia por envío
  (https://resend.com/docs/dashboard/emails/idempotency-keys).
- "smtp": un servidor SMTP con STARTTLS o TLS implícito, pensado para la
  cuenta de Google Workspace del equipo (smtp.gmail.com, puerto 587, usuario
  la propia dirección y una contraseña de aplicación) o cualquier otro. No
  hace falta verificar un dominio en un tercero: el correo sale del buzón
  corporativo que ya existe. Añadido el 15 de septiembre de 2026.
Un solo trabajador por proceso. Nunca se reintenta fuera de la ventana de
idempotencia del proveedor; aceptado no significa entregado al buzón.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import smtplib
import sqlite3
import time
import uuid
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

BASE = {"remitente": "", "url": "http://localhost:5174", "hora": 8, "zona": "America/Santo_Domingo", "clave": "",
        "proveedor": "resend", "smtpServidor": "", "smtpPuerto": 587, "smtpUsuario": ""}
PROVEEDORES = ("resend", "smtp")
ASUNTOS = {
    "hipotesisNueva": "Hay nuevas hipótesis para revisar",
    "permisoPendiente": "Rosa necesita tu atención",
    "corridaDetenida": "Una corrida se ha pausado o finalizado",
    "resumenDiario": "Tu resumen diario de Rosa",
    "prueba": "El correo de Rosa está conectado",
    "acceso": "Confirma tu acceso a Alzheimer Project",
}


def direccion(valor: str) -> str:
    if not isinstance(valor, str) or len(valor) > 200 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", valor):
        raise ValueError("Escribe una sola dirección de correo válida, sin nombre ni espacios")
    return valor


class Correo:
    def __init__(self, almacen, ruta: Path | str | None = None):
        self.almacen = almacen
        ruta = ruta or (almacen.ruta.parent / "datos" / "_correo" / (almacen.ruta.name + ".db"))
        if str(ruta) != ":memory:":
            ruta = Path(ruta)
            ruta.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(ruta, os.O_CREAT | os.O_WRONLY, 0o600)
            os.close(fd)
            ruta.chmod(0o600)
        self.db = sqlite3.connect(str(ruta))
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS ajustes (id INTEGER PRIMARY KEY, json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS preferencias_correo (correo TEXT PRIMARY KEY, json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS vistos (id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS transiciones (id TEXT PRIMARY KEY, estado TEXT NOT NULL, numero INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS cola (
                id TEXT PRIMARY KEY, tipo TEXT NOT NULL, destinatario TEXT NOT NULL,
                carga TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'pendiente',
                creado REAL NOT NULL, proximo REAL NOT NULL, intentos INTEGER NOT NULL DEFAULT 0,
                primero REAL, error TEXT, proveedor TEXT);
        """)
        self.error = None

    def preferencias(self, email):
        from rosa.estado.plantilla import estado_inicial
        base = estado_inicial()['avisos']
        base['correo'] = {'activo': True, 'direccion': email}
        fila = self.db.execute('SELECT json FROM preferencias_correo WHERE correo=?', (email,)).fetchone()
        return json.loads(fila[0]) if fila else base

    def guardar_preferencias(self, email, avisos):
        from rosa.estado.acciones import actualizar_avisos
        e = {}
        if not actualizar_avisos(e, avisos):
            raise ValueError('Avisos inválidos')
        e['avisos']['correo']['direccion'] = email
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO preferencias_correo VALUES (?,?)', (email, json.dumps(e['avisos'])))
        return True

    def cerrar(self):
        self.db.close()

    def _config(self):
        fila = self.db.execute("SELECT json FROM ajustes WHERE id=1").fetchone()
        return BASE | (json.loads(fila[0]) if fila else {})

    @staticmethod
    def _listo(c):
        """Si con esta configuración se puede enviar: clave y remitente siempre;
        con SMTP, además servidor y usuario."""
        if not (c["clave"] and c["remitente"]):
            return False
        if c.get("proveedor", "resend") == "smtp":
            return bool(c.get("smtpServidor") and c.get("smtpUsuario"))
        return True

    def estado(self):
        c = self._config()
        return {**{k: v for k, v in c.items() if k != "clave"}, "claveGuardada": bool(c["clave"]),
                "configurado": self._listo(c), "error": self.error,
                "historial": [dict(r) for r in self.db.execute(
                    "SELECT id,tipo,destinatario,estado,creado,intentos,error,proveedor FROM cola ORDER BY creado DESC LIMIT 30")]}

    def configurar(self, cambios):
        c = self._config()
        for k in ("remitente", "url", "zona", "clave", "proveedor", "smtpServidor", "smtpUsuario"):
            if k in cambios:
                if not isinstance(cambios[k], str) or len(cambios[k]) > 500:
                    raise ValueError("Configuración de correo inválida")
                if k != "clave" or cambios[k]:
                    c[k] = cambios[k].strip()
        if c["proveedor"] not in PROVEEDORES:
            raise ValueError("Proveedor de correo desconocido: usa 'resend' o 'smtp'")
        if "smtpPuerto" in cambios:
            c["smtpPuerto"] = cambios["smtpPuerto"]
        if type(c["smtpPuerto"]) is not int or not 1 <= c["smtpPuerto"] <= 65535:
            raise ValueError("El puerto SMTP debe ser un número entre 1 y 65535")
        if c["smtpServidor"] and not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", c["smtpServidor"]):
            raise ValueError("El servidor SMTP debe ser un nombre de máquina, como smtp.gmail.com")
        if c["proveedor"] == "smtp" and c["smtpUsuario"] and any(ord(x) < 33 or ord(x) > 126 for x in c["smtpUsuario"]):
            raise ValueError("El usuario SMTP contiene caracteres inválidos")
        if cambios.get("borrarClave") is True:
            c["clave"] = ""
        if c["remitente"]:
            direccion(c["remitente"])
        if any(ord(x) < 33 or ord(x) > 126 for x in c["clave"]):
            raise ValueError("La clave contiene caracteres inválidos")
        u = urlsplit(c["url"])
        if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password or u.query or u.fragment or any(x.isspace() for x in c["url"]):
            raise ValueError("La URL de Rosa debe ser http(s), sin credenciales, parámetros ni fragmento")
        if u.scheme == 'http' and u.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('Fuera de localhost, Rosa necesita una URL HTTPS para proteger las sesiones')
        c["hora"] = cambios.get("hora", c["hora"])
        if type(c["hora"]) is not int or not 0 <= c["hora"] <= 23:
            raise ValueError("La hora debe estar entre 0 y 23")
        try:
            ZoneInfo(c["zona"])
        except (KeyError, ValueError):
            raise ValueError("Zona horaria desconocida") from None
        with self.db:
            # Cambiar transporte cancela lo pendiente, nunca cambia un payload
            # ya usado con la misma clave de idempotencia.
            if c != self._config():
                self.db.execute("UPDATE cola SET estado='cancelado',carga=CASE WHEN tipo='acceso' THEN '{}' ELSE carga END WHERE estado='pendiente'")
            self.db.execute("INSERT OR REPLACE INTO ajustes VALUES (1,?)", (json.dumps(c),))
        return self.estado()

    def _encolar(self, tipo, destino, texto, ahora):
        c = self._config()
        carga = {"from": c["remitente"], "to": [destino], "subject": "Rosa: " + ASUNTOS[tipo],
                 "text": texto + "\n\nAbrir Rosa: " + c["url"].rstrip("/") + "/#/inicio\n\n"
                 "Por privacidad, este correo no incluye documentos, datos clínicos ni conclusiones científicas. "
                 "Consulta las evidencias y limitaciones en Rosa. Cambia los avisos en Ajustes."}
        id_ = str(uuid.uuid4())
        self.db.execute("INSERT INTO cola (id,tipo,destinatario,carga,creado,proximo) VALUES (?,?,?,?,?,?)",
                        (id_, tipo, destino, json.dumps(carga), ahora, ahora))
        return id_

    def prueba(self, destino):
        c = self._config()
        destino = direccion(destino)
        if not self._listo(c):
            raise ValueError("Guarda primero el remitente y la clave del proveedor (y, con SMTP, el servidor y el usuario)")
        ahora = time.time()
        if self.db.execute("SELECT 1 FROM cola WHERE tipo='prueba' AND creado>?", (ahora - 60,)).fetchone():
            raise ValueError("Espera un minuto antes de enviar otra prueba")
        with self.db:
            return self._encolar("prueba", destino, "Este es un correo real de prueba, enviado a petición tuya. No ha utilizado ningún modelo de IA.", ahora)

    def observar(self, e, ahora=None):
        ahora = time.time() if ahora is None else ahora
        c = self._config()
        def habilitado(destino, tipo):
            if not destino or not self._listo(c):
                return False
            p = self.preferencias(destino)
            return p['correo']['activo'] and p['cuando'].get(tipo, False)
        investigaciones = {x["id"]: x for x in e.get("investigaciones", [])}
        corridas = {x["id"]: x for x in e.get("corridas", [])}
        def responsable(x):
            corrida = corridas.get(x.get("corridaId") or x.get('_corridaOrigen'), {})
            inv = investigaciones.get(x.get("investigacionId") or corrida.get("investigacionId"), {})
            return x.get("_correoResponsable") or corrida.get("_correoResponsable") or inv.get("_correoResponsable")
        candidatos = []
        for h in e.get("hipotesis", []):
            candidatos.append(("h:" + h["id"], "hipotesisNueva", responsable(h)))
        for tabla in ("solicitudes", "incidencias"):
            candidatos.extend((tabla + ":" + x["id"], "permisoPendiente", responsable(x)) for x in e.get(tabla, []) if x.get("estado") == "pendiente")
        for x in e.get("corridas", []):
            s = x.get("estado")
            if s == "esperando_plan":
                its = [it for it in e.get("iteraciones", []) if it.get("corridaId") == x["id"]]
                it = max(its, key=lambda it: it.get("numero", 0), default={})
                if it and it.get('plan') and not it.get('planAprobado'):
                    candidatos.append((f"plan:{x['id']}:{it['id']}", "permisoPendiente", responsable(x)))
        with self.db:
            inicial = not self.db.execute("SELECT 1 FROM vistos WHERE id='inicializado'").fetchone()
            self.db.execute("INSERT OR IGNORE INTO vistos VALUES ('inicializado')")
            for x in e.get('corridas', []):
                anterior = self.db.execute('SELECT estado,numero FROM transiciones WHERE id=?', (x['id'],)).fetchone()
                s = x.get('estado', '')
                numero = (anterior['numero'] + int(anterior['estado'] != s)) if anterior else 1
                self.db.execute('INSERT OR REPLACE INTO transiciones VALUES (?,?,?)', (x['id'], s, numero))
                if s in ('detenida', 'terminada', 'pausada', 'pausada_por_presupuesto'):
                    candidatos.append((f"corrida:{x['id']}:{numero}", 'corridaDetenida', responsable(x)))
            grupos = {}
            for id_, tipo, destino in candidatos:
                nuevo = self.db.execute("INSERT OR IGNORE INTO vistos VALUES (?)", (id_,)).rowcount
                if nuevo and not inicial and habilitado(destino, tipo):
                    grupos[tipo, destino] = grupos.get((tipo, destino), 0) + 1
            for (tipo, destino), n in grupos.items():
                self._encolar(tipo, destino, f"{ASUNTOS[tipo]}.\nNovedades desde la última comprobación: {n}.", ahora)
            local = datetime.fromtimestamp(ahora, ZoneInfo(c["zona"]))
            diario = "diario:" + local.date().isoformat()
            if local.hour >= c["hora"] and self.db.execute("INSERT OR IGNORE INTO vistos VALUES (?)", (diario,)).rowcount:
                if not inicial:
                    destinos = {responsable(x) for x in e.get('corridas', [])} - {None}
                    for destino in destinos:
                        if not habilitado(destino, 'resumenDiario'):
                            continue
                        propias = [x for x in e.get('corridas', []) if responsable(x) == destino]
                        pendientes = sum(x.get("estado") == "pendiente" and responsable(x) == destino for tabla in ("solicitudes", "incidencias") for x in e.get(tabla, []))
                        self._encolar("resumenDiario", destino,
                            f"Resumen del {local.date().isoformat()} ({c['zona']}).\n"
                            f"Corridas iniciadas por tu cuenta: {len(propias)}.\n"
                            f"Permisos e incidencias pendientes: {pendientes}.\n"
                            "Este es un resumen de estado, no una evaluación científica.", ahora)
            for r in self.db.execute("SELECT id,tipo,destinatario FROM cola WHERE estado='pendiente'").fetchall():
                if r["tipo"] not in ("prueba", "acceso") and not habilitado(r['destinatario'], r['tipo']):
                    self.db.execute("UPDATE cola SET estado='cancelado' WHERE id=?", (r["id"],))

    async def enviar_uno(self, cliente, ahora=None):
        ahora = time.time() if ahora is None else ahora
        r = self.db.execute("SELECT * FROM cola WHERE estado='pendiente' AND proximo<=? ORDER BY CASE tipo WHEN 'acceso' THEN 0 WHEN 'prueba' THEN 1 ELSE 2 END,creado LIMIT 1", (ahora,)).fetchone()
        if not r:
            return
        if r['tipo'] == 'acceso' and ahora - r['creado'] >= 900:
            with self.db:
                self.db.execute("UPDATE cola SET estado='cancelado',carga='{}',error='El enlace de acceso caducó' WHERE id=?", (r['id'],))
            return
        if r["primero"] is not None and ahora - r["primero"] >= 23 * 3600:
            with self.db:
                self.db.execute("UPDATE cola SET estado='fallido',error='Ventana de reintento agotada; comprueba el proveedor antes de repetir' WHERE id=?", (r["id"],))
            return
        c = self._config()
        if not c["clave"]:
            return
        with self.db:
            self.db.execute("UPDATE cola SET intentos=intentos+1,primero=COALESCE(primero,?) WHERE id=?", (ahora, r["id"]))
        error, reintentar, proveedor = None, False, None
        if c.get("proveedor", "resend") == "smtp":
            proveedor, error, reintentar = await asyncio.to_thread(self._enviar_smtp, c, r["id"], json.loads(r["carga"]))
            self._cerrar_envio(r, ahora, error, reintentar, proveedor)
            return
        try:
            resp = await cliente.post("https://api.resend.com/emails", headers={"Authorization": "Bearer " + c["clave"], "Idempotency-Key": r["id"]}, json=json.loads(r["carga"]))
            if resp.is_success:
                dato = resp.json()
                proveedor = dato.get("id") if isinstance(dato, dict) else None
                if not isinstance(proveedor, str) or not proveedor:
                    error, reintentar = "Respuesta del proveedor sin identificador", True
            else:
                error = {401: "Clave de Resend inválida", 403: "Revisa los permisos, el dominio remitente y el destinatario permitido en Resend", 429: "Límite del proveedor; se reintentará"}.get(resp.status_code, f"El proveedor rechazó el envío (HTTP {resp.status_code})")
                reintentar = resp.status_code == 429 or resp.status_code >= 500
        except (httpx.HTTPError, ValueError):
            # Nunca guardar respuesta cruda, petición ni excepción con secretos.
            error, reintentar = "No se pudo confirmar el envío; se reintentará con el mismo identificador", True
        self._cerrar_envio(r, ahora, error, reintentar, proveedor)

    def _cerrar_envio(self, r, ahora, error, reintentar, proveedor):
        estado = "aceptado" if error is None else ("pendiente" if reintentar and r["intentos"] < 4 else "fallido")
        actual = self.db.execute('SELECT estado FROM cola WHERE id=?', (r['id'],)).fetchone()
        if error and actual and actual[0] == 'cancelado':
            estado = 'cancelado'
        with self.db:
            self.db.execute("UPDATE cola SET estado=?,error=?,proveedor=?,proximo=? WHERE id=?",
                            (estado, error, proveedor, ahora + 60 * 2 ** r["intentos"], r["id"]))
            if r['tipo'] == 'acceso' and estado != 'pendiente':
                self.db.execute("UPDATE cola SET carga='{}' WHERE id=?", (r['id'],))

    @staticmethod
    def _enviar_smtp(c, id_, carga):
        """Un envío por SMTP en un hilo aparte (smtplib es bloqueante). Devuelve
        (identificador, error, reintentar). El Message-ID lleva el id de la
        cola: si el servidor lo recibe dos veces, el buzón puede deduplicarlo.
        Nunca se guarda la respuesta cruda del servidor ni la contraseña."""
        mensaje = EmailMessage()
        mensaje["From"] = carga["from"]
        mensaje["To"] = ", ".join(carga["to"])
        mensaje["Subject"] = carga["subject"]
        mensaje["Message-ID"] = f"<{id_}@rosa.alzheimerproject>"
        mensaje.set_content(carga["text"])
        try:
            if c["smtpPuerto"] == 465:
                servidor = smtplib.SMTP_SSL(c["smtpServidor"], c["smtpPuerto"], timeout=20)
            else:
                servidor = smtplib.SMTP(c["smtpServidor"], c["smtpPuerto"], timeout=20)
                servidor.ehlo()
                servidor.starttls()
                servidor.ehlo()
            with servidor:
                servidor.login(c["smtpUsuario"], c["clave"])
                servidor.send_message(mensaje)
            return mensaje["Message-ID"], None, False
        except smtplib.SMTPAuthenticationError:
            return None, "El servidor SMTP rechazó el usuario o la contraseña. Con Google Workspace hace falta una contraseña de aplicación, no la de la cuenta", False
        except smtplib.SMTPRecipientsRefused:
            return None, "El servidor SMTP rechazó al destinatario", False
        except smtplib.SMTPSenderRefused:
            return None, "El servidor SMTP rechazó al remitente: debe ser la misma cuenta que el usuario o un alias suyo", False
        except smtplib.SMTPResponseException as ex:
            transitorio = 400 <= ex.smtp_code < 500
            return None, ("El servidor SMTP pidió esperar; se reintentará" if transitorio else "El servidor SMTP rechazó el mensaje"), transitorio
        except (OSError, smtplib.SMTPException):
            return None, "No se pudo conectar con el servidor SMTP; se reintentará", True

    async def correr(self):
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as cliente:
            while True:
                try:
                    with self.almacen._lock:
                        # Solo metadatos necesarios, nunca copiar documentos o
                        # fragmentos clínicos para preparar una notificación.
                        campos = ('id', 'investigacionId', 'corridaId', 'estado', '_correoResponsable', '_corridaOrigen', 'numero', 'planAprobado')
                        e = {tabla: [{k: x[k] for k in campos if k in x} | ({'plan': bool(x.get('plan'))} if tabla == 'iteraciones' else {})
                                     for x in self.almacen.estado.get(tabla, [])]
                             for tabla in ('investigaciones', 'corridas', 'hipotesis', 'solicitudes', 'incidencias', 'iteraciones')}
                    self.observar(e)
                    await self.enviar_uno(cliente)
                    self.error = None
                except Exception:
                    self.error = "El trabajador de correo no pudo completar el ciclo; volverá a intentarlo"
                await asyncio.sleep(5)
