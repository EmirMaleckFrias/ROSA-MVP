"""Sello de tiempo de un tercero (RFC 3161) para lo que ROSA2018 congela.

El prerregistro de un experimento y el plan de un analisis quedan congelados
en el estado de ROSA2018 con fecha. Pero esa fecha la pone ROSA2018: quien dude puede
decir que se cambio despues. Un sello RFC 3161 resuelve eso: se manda el
hash SHA-256 del contenido a una autoridad de sellado de tiempo (TSA) y ella
devuelve un token firmado con la hora en que lo vio. ROSA2018 guarda el token;
cualquiera lo verifica con OpenSSL sin confiar en ROSA2018:

    openssl ts -verify -digest <hash> -in sello.tsr -CAfile cacert.pem

Se piden dos sellos a autoridades de familias distintas (una caida o una
duda sobre una no invalida la otra). No hace falta cuenta ni clave. Es la
version barata del prerregistro externo: OSF exige un token personal y
queda como opcion (`OSF_TOKEN`), no como requisito.

Todo lo de aqui es sincrono y bloqueante: se llama desde un hilo.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from typing import Any

import httpx
from pyasn1.codec.der import decoder, encoder
from pyasn1.type import univ
from pyasn1_modules import rfc2459, rfc3161, rfc5652

# Autoridades publicas, sin cuenta. Orden: se piden todas; con una basta.
AUTORIDADES: tuple[dict[str, str], ...] = (
    {"nombre": "freeTSA", "url": "https://freetsa.org/tsr", "ca": "https://freetsa.org/files/cacert.pem"},
    {"nombre": "DigiCert", "url": "http://timestamp.digicert.com", "ca": "https://knowledge.digicert.com/general-information/rfc3161-compliant-time-stamp-authority-server"},
    {"nombre": "Sectigo", "url": "http://timestamp.sectigo.com", "ca": "https://sectigo.com/resource-library/time-stamping-server"},
)
OID_SHA256 = "2.16.840.1.101.3.4.2.1"
SEGUNDOS = 30


def hash_canonico(contenido: str | bytes | dict | list) -> str:
    """SHA-256 en hexadecimal. Un dict o lista se serializa en JSON canónico
    (claves ordenadas, sin espacios) para que el hash no dependa del orden."""
    if isinstance(contenido, (dict, list)):
        datos = json.dumps(contenido, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    elif isinstance(contenido, str):
        datos = contenido.encode("utf-8")
    else:
        datos = contenido
    return hashlib.sha256(datos).hexdigest()


def _peticion(hash_hex: str, nonce: int) -> bytes:
    req = rfc3161.TimeStampReq()
    req["version"] = 1
    imp = rfc3161.MessageImprint()
    alg = rfc2459.AlgorithmIdentifier()
    alg["algorithm"] = univ.ObjectIdentifier(OID_SHA256)
    alg["parameters"] = univ.Null("")
    imp["hashAlgorithm"] = alg
    imp["hashedMessage"] = univ.OctetString(bytes.fromhex(hash_hex))
    req["messageImprint"] = imp
    req["nonce"] = univ.Integer(nonce)
    req["certReq"] = True
    return encoder.encode(req)


def leer_token(tsr_der: bytes) -> dict[str, Any]:
    """Los campos del TSTInfo de una respuesta DER: estado, hora firmada
    (genTime), número de serie, política, hash sellado y nonce."""
    resp, _ = decoder.decode(tsr_der, asn1Spec=rfc3161.TimeStampResp())
    estado = int(resp["status"]["status"])
    if estado not in (0, 1):
        texto = " ".join(str(s) for s in resp["status"]["statusString"]) if resp["status"]["statusString"].hasValue() else ""
        return {"estado": estado, "error": f"la autoridad no concedio el sello (estado {estado}) {texto}".strip()}
    token = resp["timeStampToken"]
    firmado, _ = decoder.decode(token["content"], asn1Spec=rfc5652.SignedData())
    tst, _ = decoder.decode(firmado["encapContentInfo"]["eContent"], asn1Spec=rfc3161.TSTInfo())
    gen = str(tst["genTime"])  # GeneralizedTime, p. ej. 20260914135217Z
    iso = f"{gen[0:4]}-{gen[4:6]}-{gen[6:8]}T{gen[8:10]}:{gen[10:12]}:{gen[12:14]}Z" if len(gen) >= 14 else gen
    return {
        "estado": estado,
        "genTime": iso,
        "serial": str(int(tst["serialNumber"])),
        "politica": str(tst["policy"]),
        "hash": bytes(tst["messageImprint"]["hashedMessage"]).hex(),
        "nonce": int(tst["nonce"]) if tst["nonce"].hasValue() else None,
    }


def pedir_sello(hash_hex: str, autoridad: dict[str, str], cliente: httpx.Client | None = None) -> dict[str, Any]:
    """Un sello de una autoridad. Nunca lanza: devuelve `ok` y, si no, `error`.
    Comprueba que el hash y el nonce del token son los que se mandaron."""
    nonce = secrets.randbits(63)
    t0 = time.monotonic()
    base = {"tsa": autoridad["nombre"], "url": autoridad["url"], "ca": autoridad.get("ca"), "ok": False}
    try:
        cuerpo = _peticion(hash_hex, nonce)
        cli = cliente or httpx.Client(timeout=SEGUNDOS, follow_redirects=False)
        try:
            r = cli.post(autoridad["url"], content=cuerpo, headers={"Content-Type": "application/timestamp-query", "Accept": "application/timestamp-reply"})
        finally:
            if cliente is None:
                cli.close()
        if r.status_code != 200:
            return base | {"error": f"HTTP {r.status_code}", "ms": int((time.monotonic() - t0) * 1000)}
        campos = leer_token(r.content)
        if campos.get("error"):
            return base | {"error": campos["error"], "ms": int((time.monotonic() - t0) * 1000)}
        if campos["hash"] != hash_hex.lower():
            return base | {"error": "el hash sellado no es el pedido", "ms": int((time.monotonic() - t0) * 1000)}
        if campos["nonce"] is not None and campos["nonce"] != nonce:
            return base | {"error": "el nonce del token no es el pedido (respuesta reutilizada)", "ms": int((time.monotonic() - t0) * 1000)}
        return base | {"ok": True, "genTime": campos["genTime"], "serial": campos["serial"], "politica": campos["politica"], "tsrBase64": base64.b64encode(r.content).decode("ascii"), "ms": int((time.monotonic() - t0) * 1000)}
    except Exception as ex:  # noqa: BLE001
        return base | {"error": f"{type(ex).__name__}: {str(ex)[:160]}", "ms": int((time.monotonic() - t0) * 1000)}


def sellar(contenido: str | bytes | dict | list, autoridades: tuple[dict[str, str], ...] = AUTORIDADES, minimo_ok: int = 1) -> dict[str, Any]:
    """Sella un contenido con todas las autoridades. `ok` si al menos
    `minimo_ok` respondieron con un token valido. Nunca lanza."""
    h = hash_canonico(contenido)
    sellos = [pedir_sello(h, a) for a in autoridades]
    buenos = [s for s in sellos if s["ok"]]
    return {
        "algoritmo": "sha256",
        "hash": h,
        "pedidoEn": int(time.time() * 1000),
        "sellos": sellos,
        "ok": len(buenos) >= minimo_ok,
        "testigos": [s["tsa"] for s in buenos],
        "primeraHora": min((s["genTime"] for s in buenos), default=None),
        "error": None if buenos else "; ".join(f"{s['tsa']}: {s.get('error')}" for s in sellos)[:400],
    }


def verificar_token(tsr_base64: str, hash_hex: str) -> dict[str, Any]:
    """Re-lee un token guardado y comprueba que sella ese hash. No verifica la
    firma de la autoridad (para eso esta OpenSSL con su certificado); si el
    hash coincide y la hora esta, el token es el que se guardo."""
    try:
        campos = leer_token(base64.b64decode(tsr_base64))
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": f"token ilegible: {type(ex).__name__}"}
    if campos.get("error"):
        return {"ok": False, "error": campos["error"]}
    return {"ok": campos["hash"] == hash_hex.lower(), "genTime": campos["genTime"], "serial": campos["serial"]}


def comando_verificacion(hash_hex: str, fichero_tsr: str = "sello.tsr", ca: str = "cacert.pem") -> str:
    """Lo que una persona ejecuta para comprobar el sello sin ROSA2018."""
    return f"openssl ts -verify -digest {hash_hex} -in {fichero_tsr} -CAfile {ca}"


def texto_para_registro(sello: dict[str, Any]) -> str:
    """Una línea legible para el registro de procedencia y el dossier."""
    if not sello.get("ok"):
        return f"sello externo no conseguido ({sello.get('error') or 'sin respuesta'}); el hash {sello.get('hash', '')[:16]} queda registrado para reintentar"
    testigos = ", ".join(f"{s['tsa']} (serie {s['serial']}, {s['genTime']})" for s in sello["sellos"] if s["ok"])
    return f"sha256 {sello['hash']} sellado por {testigos}"
