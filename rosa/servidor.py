"""El servidor HTTP de Rosa (FastAPI).

Tres rutas y nada mas, porque el frontend ya sabe hacer el resto:

- `GET /api/estado`: la instantanea completa del estado (forma `EstadoRosa`).
- `GET /api/eventos`: Server-Sent Events. Cada vez que el estado cambia, el
  servidor manda la instantanea completa con `id` igual a la version. El
  navegador reconecta solo si se corta.
- `POST /api/acciones/{nombre}`: una acción de la interfaz con sus
  argumentos en JSON. Devuelve `{ok, resultado, version}`.

Ademas `GET /api/llamadas/{corridaId}` da las ultimas llamadas a modelos y,
si existe `frontend/dist`, sirve la interfaz compilada en la raiz.
"""

from __future__ import annotations

import asyncio
import json
import contextlib
import time
import sys
import secrets
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from rosa import config
from rosa.estado import plantilla as P
from rosa.estado.almacen import ACCIONES, Almacen
from rosa.acceso import Acceso, COOKIE, DURACION
from urllib.parse import urlsplit


# Acciones que solo aplica el propio servidor (subidas, panel del Killer,
# preguntas con herramientas): no se aceptan desde el navegador.
ACCIONES_INTERNAS = {"registrarPreguntaBases", "registrarEvaluacion", "registrarDatosExperimento", "registrarSelloExterno"}
MAX_CUERPO_ACCION = 1_000_000
HOSTS_LOCALES = ("127.0.0.1", "localhost", "::1")


async def _leer_acotado(fichero: UploadFile, maximo: int) -> bytes:
    """Lee una subida por trozos y corta en cuanto pasa el máximo, antes de
    cargarla entera en memoria."""
    declarado = fichero.size
    if declarado is not None and declarado > maximo:
        raise HTTPException(413, f"El fichero supera los {maximo // (1024 * 1024)} MB")
    partes: list[bytes] = []
    total = 0
    while True:
        trozo = await fichero.read(1024 * 1024)
        if not trozo:
            break
        total += len(trozo)
        if total > maximo:
            raise HTTPException(413, f"El fichero supera los {maximo // (1024 * 1024)} MB")
        partes.append(trozo)
    return b"".join(partes)


def token_interno() -> str:
    """Un secreto por instalación, en un fichero fuera de git, para las
    acciones internas (el panel del Killer lo lee del mismo disco)."""
    ruta = config.RAIZ / "datos" / "_token_interno"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if not ruta.exists():
        ruta.write_text(secrets.token_hex(24), encoding="utf-8")
        ruta.chmod(0o600)
    return ruta.read_text(encoding="utf-8").strip()


def crear_app(almacen: Almacen) -> FastAPI:
    @contextlib.asynccontextmanager
    async def _vida(_app: FastAPI):
        # Arranque: el almacen conoce el bucle de eventos para despertar a los
        # suscriptores del SSE desde el hilo del bucle de investigacion.
        almacen.enganchar_bucle(asyncio.get_running_loop())
        from rosa.correo import Correo

        correo = Correo(almacen)
        app.state.correo = correo
        app.state.acceso = Acceso(correo)
        tarea = asyncio.create_task(correo.correr())
        try:
            yield
        finally:
            tarea.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tarea
            correo.cerrar()

    app = FastAPI(title="Rosa", version="0.1", lifespan=_vida)
    app.state.almacen = almacen
    app.state.token_interno = token_interno()
    app.state.semaforo_preguntas = asyncio.Semaphore(2)
    app.state.preguntas_hoy = {"dia": "", "n": 0}

    def instalacion_local(request):
        # Solo instalación local directa, nunca por un proxy o desde la red.
        origen = request.headers.get('origin')
        return (config.HOST in HOSTS_LOCALES and request.client is not None
                and request.client.host in HOSTS_LOCALES and request.url.hostname in HOSTS_LOCALES
                and (not origen or urlsplit(origen).hostname in HOSTS_LOCALES)
                and not request.headers.get('x-forwarded-for')
                and not app.state.acceso.db.execute('SELECT 1 FROM cuentas LIMIT 1').fetchone())

    def es_admin(email):
        fila = app.state.acceso.db.execute('SELECT correo FROM cuentas ORDER BY rowid LIMIT 1').fetchone()
        return bool(email and fila and fila[0] == email)

    def estado_de(request):
        e = almacen.instantanea()
        if request.state.usuario:
            e['avisos'] = app.state.correo.preferencias(request.state.usuario)
        return e
    # Solo se aceptan peticiones dirigidas al nombre con el que se sirve Rosa:
    # frena el "DNS rebinding" (una web ajena que resuelve a 127.0.0.1).
    permitidos = list(HOSTS_LOCALES) + ([config.HOST] if config.HOST not in HOSTS_LOCALES else []) + [f"{h}:{config.PUERTO}" for h in HOSTS_LOCALES]
    # Nunca un comodin: en 0.0.0.0 (el unico caso en que el ataque tiene sentido)
    # los nombres con los que se sirve Rosa van en ROSA_HOSTS.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=permitidos + list(config.HOSTS_PERMITIDOS))

    @app.middleware("http")
    async def _guardias(request: Request, call_next):
        path = request.url.path
        publico = path in ('/api/acceso/estado', '/api/acceso/solicitar', '/api/acceso/confirmar', '/api/acceso/salir', '/api/acceso/configuracion', '/api/acceso/entrar_sin_verificar')
        acceso = getattr(app.state, 'acceso', None)
        usuario = acceso.usuario(request.cookies.get(COOKIE)) if acceso else None
        request.state.usuario = usuario
        interno = secrets.compare_digest(request.headers.get('x-rosa-interno', ''), app.state.token_interno)
        if path.startswith('/api/') and not publico and not usuario and not interno:
            return JSONResponse({'detail': 'Inicia sesión con tu correo verificado'}, status_code=401)
        # 1. Si hay token configurado (servidor expuesto fuera de la maquina), toda
        #    la API lo exige, por cabecera o, para el flujo SSE, por parametro.
        if config.ROSA_TOKEN and path.startswith("/api/") and not usuario and not publico and not interno:
            dado = request.headers.get("x-rosa-token") or request.query_params.get("token")
            if not dado or not secrets.compare_digest(dado, config.ROSA_TOKEN):
                return JSONResponse({"detail": "Falta el token de acceso a Rosa"}, status_code=401)
        # 2. Toda escritura desde el navegador lleva la cabecera X-Rosa: una pagina
        #    ajena no puede mandarla sin preflight, y sin CORS el preflight falla.
        if request.method == "POST" and request.url.path.startswith("/api/") and request.headers.get("x-rosa") != "1" and not request.headers.get("x-rosa-interno"):
            return JSONResponse({"detail": "Falta la cabecera X-Rosa (la interfaz la manda siempre)"}, status_code=403)
        respuesta = await call_next(request)
        if path.startswith('/api/'):
            respuesta.headers['Cache-Control'] = 'no-store'
        respuesta.headers['Referrer-Policy'] = 'no-referrer'
        return respuesta

    @app.get('/api/acceso/estado')
    async def acceso_estado(request: Request):
        c = app.state.correo.estado()
        local = instalacion_local(request)
        ultimo = next((x for x in c['historial'] if x['tipo'] == 'acceso'), None) if local else None
        aviso = (ultimo['error'] or ('El proveedor aceptó el último correo de acceso. Comprueba el buzón y spam.' if ultimo['estado'] == 'aceptado' else 'El último correo de acceso está ' + ultimo['estado'])) if ultimo else None
        return {'correo': request.state.usuario, 'administrador': es_admin(request.state.usuario),
                'correoConfigurado': c['configurado'], 'instalacionLocal': local, 'avisoInstalacion': aviso}

    async def objeto_pequeno(request):
        cuerpo = bytearray()
        async for parte in request.stream():
            cuerpo.extend(parte)
            if len(cuerpo) > 4096:
                raise HTTPException(413, 'Petición demasiado grande')
        try:
            obj = json.loads(cuerpo)
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, 'JSON inválido') from None
        if not isinstance(obj, dict):
            raise HTTPException(400, 'Se espera un objeto JSON')
        return obj

    @app.post('/api/acceso/configuracion')
    async def acceso_configurar(request: Request):
        if not instalacion_local(request):
            raise HTTPException(403, 'La instalación inicial solo se configura en el equipo de Rosa antes de crear cuentas')
        obj = await objeto_pequeno(request)
        try:
            app.state.correo.configurar(obj)
        except ValueError as ex:
            raise HTTPException(400, str(ex)) from None
        return {'ok': True}

    @app.post('/api/acceso/solicitar')
    async def acceso_solicitar(request: Request):
        obj = await objeto_pequeno(request)
        email = obj.get('correo')
        if not isinstance(email, str):
            raise HTTPException(400, 'Falta el correo corporativo')
        try:
            app.state.acceso.solicitar(email, request.client.host if request.client else 'desconocida')
        except ValueError as ex:
            raise HTTPException(400, str(ex)) from None
        return {'ok': True, 'mensaje': 'Revisa tu correo para confirmar el acceso. El enlace caduca en 15 minutos.'}

    @app.post('/api/acceso/confirmar')
    async def acceso_confirmar(request: Request):
        obj = await objeto_pequeno(request)
        try:
            token, email = app.state.acceso.confirmar(obj.get('enlace'))
        except ValueError as ex:
            raise HTTPException(400, str(ex)) from None
        respuesta = JSONResponse({'ok': True, 'correo': email})
        seguro = urlsplit(app.state.correo._config()['url']).scheme == 'https'
        respuesta.set_cookie(COOKIE, token, max_age=DURACION, httponly=True, secure=seguro, samesite='strict', path='/')
        return respuesta

    @app.post('/api/acceso/entrar_sin_verificar')
    async def acceso_sin_verificar(request: Request):
        # Mientras no haya proveedor de correo, cualquier persona con una
        # dirección del dominio entra escribiéndola. La puerta se cierra sola
        # al configurar el correo (lo comprueba Acceso.entrar_sin_verificar).
        obj = await objeto_pequeno(request)
        email = obj.get('correo')
        if not isinstance(email, str):
            raise HTTPException(400, 'Falta el correo corporativo')
        try:
            token, email = app.state.acceso.entrar_sin_verificar(email)
        except ValueError as ex:
            raise HTTPException(403, str(ex)) from None
        respuesta = JSONResponse({'ok': True, 'correo': email, 'verificada': False})
        seguro = urlsplit(app.state.correo._config()['url']).scheme == 'https'
        respuesta.set_cookie(COOKIE, token, max_age=DURACION, httponly=True, secure=seguro, samesite='strict', path='/')
        return respuesta

    @app.post('/api/acceso/salir')
    async def acceso_salir(request: Request):
        app.state.acceso.salir(request.cookies.get(COOKIE))
        respuesta = JSONResponse({'ok': True})
        respuesta.delete_cookie(COOKIE, path='/')
        return respuesta


    @app.get("/api/estado")
    async def estado(request: Request) -> JSONResponse:
        return JSONResponse(content=estado_de(request), headers={"Cache-Control": "no-store", "X-Rosa-Version": str(almacen.version)})

    @app.get("/api/correo")
    async def correo_estado(request: Request):
        resultado = app.state.correo.estado()
        resultado['administrador'] = es_admin(request.state.usuario)
        if not resultado['administrador']:
            resultado['historial'] = [x for x in resultado['historial'] if x['destinatario'] == request.state.usuario]
        return JSONResponse(resultado, headers={"Cache-Control": "no-store"})

    @app.post("/api/correo/configuracion")
    async def correo_configuracion(request: Request):
        if not es_admin(request.state.usuario):
            raise HTTPException(403, 'Solo el administrador puede configurar el proveedor')
        cuerpo = bytearray()
        async for parte in request.stream():
            cuerpo.extend(parte)
            if len(cuerpo) > 4096:
                raise HTTPException(413, "Configuración demasiado grande")
        try:
            cambios = json.loads(cuerpo)
            if not isinstance(cambios, dict):
                raise ValueError("Se espera un objeto de configuración")
            resultado = app.state.correo.configurar(cambios)
        except (ValueError, UnicodeDecodeError) as ex:
            raise HTTPException(400, str(ex)) from None
        return JSONResponse(resultado, headers={"Cache-Control": "no-store"})

    @app.post("/api/correo/prueba")
    async def correo_prueba(request: Request):
        try:
            id_ = app.state.correo.prueba(request.state.usuario)
        except ValueError as ex:
            raise HTTPException(400, str(ex)) from None
        return {"ok": True, "id": id_}

    @app.get("/api/eventos")
    async def eventos(request: Request) -> EventSourceResponse:
        cola = almacen.suscribir()

        async def generar():
            try:
                yield {"event": "estado", "id": str(almacen.version), "data": json.dumps(estado_de(request)), "retry": 2000}
                while True:
                    if request.state.usuario and not app.state.acceso.usuario(request.cookies.get(COOKIE)):
                        break
                    if await request.is_disconnected():
                        break
                    try:
                        await asyncio.wait_for(cola.get(), timeout=10)
                    except asyncio.TimeoutError:
                        continue
                    # Coalescer: si llegaron varias versiones, solo importa la ultima.
                    while not cola.empty():
                        cola.get_nowait()
                    if request.state.usuario and not app.state.acceso.usuario(request.cookies.get(COOKIE)):
                        break
                    yield {"event": "estado", "id": str(almacen.version), "data": json.dumps(estado_de(request))}
            finally:
                almacen.desuscribir(cola)

        # El latido es un evento real (no un comentario) para que el navegador
        # pueda detectar un flujo muerto: si pasa por un proxy (Vite en
        # desarrollo) y el servidor se reinicia, el proxy puede dejar la
        # conexion abierta sin datos y EventSource no se entera solo.
        return EventSourceResponse(generar(), ping=15, ping_message_factory=lambda: ServerSentEvent(event="latido", data=str(almacen.version)), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/gepa/{accion_gepa}")
    async def controlar_gepa(accion_gepa: str, request: Request):
        if not es_admin(request.state.usuario):
            raise HTTPException(403, "Solo administración puede controlar la optimización global")
        servicio = getattr(almacen, "gepa_servicio", None)
        if servicio is None:
            raise HTTPException(503, "El servicio GEPA no está iniciado en este servidor")
        if accion_gepa not in ("pausar", "reanudar", "restablecer"):
            raise HTTPException(400, "Control GEPA desconocido")
        servicio.control(accion_gepa)
        return {"ok": True}

    @app.post("/api/acciones/{nombre}")
    async def accion(nombre: str, request: Request) -> dict[str, Any]:
        if nombre not in ACCIONES:
            raise HTTPException(404, f"Acción desconocida: {nombre}")
        if nombre in ACCIONES_INTERNAS and not secrets.compare_digest(request.headers.get("x-rosa-interno", ""), app.state.token_interno):
            raise HTTPException(403, f"{nombre} solo la aplica el servidor de Rosa")
        if "application/json" not in request.headers.get("content-type", ""):
            raise HTTPException(415, "Los argumentos van como application/json")
        cuerpo = await request.body()
        if len(cuerpo) > MAX_CUERPO_ACCION:
            raise HTTPException(413, f"El cuerpo de una acción no puede pasar de {MAX_CUERPO_ACCION // 1000} kB")
        try:
            args = json.loads(cuerpo or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(400, "El cuerpo no es JSON valido")
        if not isinstance(args, dict):
            raise HTTPException(400, "Los argumentos van como objeto JSON")
        try:
            if nombre == 'actualizarAvisos' and request.state.usuario:
                resultado = app.state.correo.guardar_preferencias(request.state.usuario, args.get('avisos'))
                almacen._avisar()
            else:
                resultado = almacen.aplicar(nombre, args, actor=request.state.usuario)
        except (TypeError, ValueError, KeyError, AttributeError, OverflowError, IndexError) as ex:
            # El almacen ya deshizo la mutacion a medias; el cliente recibe un 400 con el motivo.
            raise HTTPException(400, f"Argumentos inválidos para {nombre}: {type(ex).__name__}: {str(ex)[:200]}")
        if nombre == "asignarExperimento" and resultado is not False and isinstance(args.get("hipotesis_id"), str):
            # El prerregistro recien congelado se sella con un tercero, fuera de la peticion.
            asyncio.get_running_loop().create_task(_sellar_prerregistro(args["hipotesis_id"]))
        return {"ok": resultado is not False, "resultado": resultado, "version": almacen.version}

    async def _sellar_prerregistro(hipotesis_id: str) -> dict[str, Any]:
        """Sella el artefacto de prerregistro (RFC 3161, dos o tres autoridades)
        y lo registra en la hipótesis. Nunca lanza: el fallo queda en el estado."""
        from rosa import sello as S

        h = next((x for x in almacen.estado["hipotesis"] if x["id"] == hipotesis_id), None)
        x = (h or {}).get("experimento") or {}
        art = next((a for a in almacen.estado.get("artefactos", []) if a["id"] == x.get("prerregistroArtefactoId")), None)
        if not h or not art:
            return {"ok": False, "error": "sin prerregistro que sellar"}
        contenido = (art.get("versiones") or [{}])[-1].get("contenido") or ""
        resultado = await asyncio.to_thread(S.sellar, contenido)
        almacen.aplicar("registrarSelloExterno", {"hipotesis_id": hipotesis_id, "sello": resultado})
        return resultado

    @app.post("/api/hipotesis/{hipotesis_id}/sellar")
    async def sellar(hipotesis_id: str) -> dict[str, Any]:
        """Botón "Sellar con un tercero": pide (o repite) el sello del prerregistro."""
        return await _sellar_prerregistro(hipotesis_id)

    @app.get("/api/corridas/{corrida_id}/prisma")
    async def prisma_de(corrida_id: str) -> dict[str, Any]:
        """El flujo de búsqueda en PRISMA 2020 (variables oficiales del diagrama,
        ítems 6, 7, 8, 16a y 16b), la extensión viva y la declaración de la IA,
        con el Markdown listo para un manuscrito. Sin ningún modelo."""
        from rosa import prisma as PRISMA

        def armar() -> dict[str, Any] | None:
            with almacen._lock:
                c = next((x for x in almacen.estado["corridas"] if x["id"] == corrida_id), None)
                if not c:
                    return None
                return PRISMA.informe(almacen.estado, c, almacen.llamadas_de(corrida_id, 5000), P.ahora_ms())

        r = await asyncio.to_thread(armar)
        if r is None:
            raise HTTPException(404, "Corrida desconocida")
        return r

    @app.get("/api/investigaciones/{investigacion_id}/costes")
    async def costes(investigacion_id: str) -> dict[str, Any]:
        """Coste por decisión de una investigación: dólares del modelo más horas
        de revisión humana a la tarifa declarada; por dossier, por candidata y
        por decisión; y la tendencia por iteración."""
        from rosa import costes as C

        def armar() -> dict[str, Any] | None:
            with almacen._lock:
                if not any(i["id"] == investigacion_id for i in almacen.estado["investigaciones"]):
                    return None
                por_corrida = {c["id"]: almacen.llamadas_de(c["id"], 20000) for c in almacen.estado["corridas"] if c.get("investigacionId") == investigacion_id}
                return C.costes_de_investigacion(almacen.estado, investigacion_id, por_corrida)

        r = await asyncio.to_thread(armar)
        if r is None:
            raise HTTPException(404, "Investigación desconocida")
        return r

    @app.get("/api/hipotesis/{hipotesis_id}/rocrate")
    async def rocrate_de(hipotesis_id: str) -> Response:
        """El expediente de la hipótesis como RO-Crate (zip) con procedencia
        W3C PROV: verificable con herramientas de terceros, sin Rosa."""
        from rosa import rocrate as RC

        def armar() -> bytes | None:
            with almacen._lock:
                h = next((x for x in almacen.estado["hipotesis"] if x["id"] == hipotesis_id), None)
                if not h:
                    return None
                return RC.zip_bytes(RC.armar(almacen.estado, h, P.ahora_ms()))

        datos = await asyncio.to_thread(armar)
        if datos is None:
            raise HTTPException(404, "Hipótesis desconocida")
        return Response(content=datos, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="rosa-{hipotesis_id}.crate.zip"', "Cache-Control": "no-store"})

    @app.get("/api/registro/integridad")
    async def integridad() -> dict[str, Any]:
        """Recorre la cadena de hashes del registro de acciones."""
        return await asyncio.to_thread(almacen.verificar_cadena)

    @app.get("/api/calidad/acuerdo")
    async def acuerdo_jueces() -> dict[str, Any]:
        """Acuerdo juez-humano del conjunto dorado, por comprobación."""
        from rosa import acuerdo_dorado as ACU

        return ACU.acuerdo_dorado(almacen.instantanea())

    @app.get("/api/llamadas/{corrida_id}")
    async def llamadas(corrida_id: str) -> list[dict[str, Any]]:
        return almacen.llamadas_de(corrida_id)

    @app.get("/api/corridas/{corrida_id}/evidencia")
    async def evidencia(corrida_id: str) -> JSONResponse:
        datos = almacen.evidencia_de(corrida_id)
        if datos is None:
            raise HTTPException(404, "Corrida desconocida")
        return JSONResponse(content=datos, headers={"Cache-Control": "no-store"})

    @app.post("/api/hipotesis/{hipotesis_id}/datos")
    async def subir_datos(hipotesis_id: str, fichero: UploadFile = File(...), analisis: str = Form("")) -> dict[str, Any]:
        """Los datos del laboratorio para una hipotesis con experimento
        asignado: se guardan en `datos/<hipotesis>/` y se registra el fichero;
        el bucle los evalua contra el prerregistro y rehace la conclusion."""
        from rosa import datos as D

        h = next((x for x in almacen.estado["hipotesis"] if x["id"] == hipotesis_id), None)
        if not h or not h.get("experimento"):
            raise HTTPException(404, "Hipótesis sin experimento propuesto")
        contenido = await _leer_acotado(fichero, D.MAX_BYTES)
        tamano = len(contenido)
        try:
            ruta = await asyncio.to_thread(D.guardar, hipotesis_id, fichero.filename or "datos", contenido)
        except ValueError as ex:
            raise HTTPException(413, str(ex))
        resultado = almacen.aplicar("registrarDatosExperimento", {"hipotesis_id": hipotesis_id, "fichero": ruta.name, "analisis": analisis})
        return {"ok": resultado is not False, "fichero": ruta.name, "bytes": tamano, "version": almacen.version}

    @app.post("/api/investigaciones/{investigacion_id}/datasets")
    async def subir_dataset(investigacion_id: str, fichero: UploadFile = File(...), nombre: str = Form(""), descripcion: str = Form(""), sintetico: str = Form("no")) -> dict[str, Any]:
        """Un dataset con su libro de procedencia: el fichero se guarda en
        `datos/_datasets/<investigacion>/<dataset>/`, se calcula su sha256, se
        perfila (columnas, filas, centinelas, duplicados, diccionario por
        rellenar) y queda pendiente hasta que la persona complete origen,
        licencia y permisos y apruebe el contrato. Nada del fichero pasa por
        un modelo aqui."""
        from rosa import datos as D
        from rosa.ejecucion import hash_fichero
        from rosa.estado import plantilla as P

        inv = next((i for i in almacen.estado["investigaciones"] if i["id"] == investigacion_id), None)
        if not inv:
            raise HTTPException(404, "Investigación desconocida")
        contenido = await _leer_acotado(fichero, D.MAX_BYTES)
        tamano = len(contenido)
        dataset_id = P.nuevo_id("ds")
        try:
            ruta = await asyncio.to_thread(D.guardar_dataset, investigacion_id, dataset_id, fichero.filename or "datos", contenido)
        except ValueError as ex:
            raise HTTPException(413, str(ex))
        del contenido
        try:
            # El perfilado y el hash de un fichero de 100 MB tardan segundos: fuera del bucle de eventos.
            perfil = await asyncio.to_thread(D.perfil_dataset, ruta)
        except Exception as ex:  # noqa: BLE001
            with contextlib.suppress(OSError):
                ruta.unlink()
            raise HTTPException(400, f"No se pudo perfilar el fichero: {type(ex).__name__}: {str(ex)[:160]}")
        es_sintetico = sintetico.strip().lower() in ("si", "sí", "true", "1", "yes")
        procedencia = {**P.procedencia_dataset_vacia(), "hash": await asyncio.to_thread(hash_fichero, ruta), "fichero": ruta.name, "filas": perfil["filas"], "diccionario": perfil["diccionario"], "columnas": perfil["columnas"], "sintetico": es_sintetico, "fechaObtencion": P.ahora_ms(), "clase": "prediccion" if es_sintetico else "observacion_original", "permiteLlmTerceros": es_sintetico}
        dataset = {
            "nombre": nombre.strip() or (fichero.filename or "datos"),
            "descripcion": descripcion.strip(),
            "tamanoMb": round(tamano / (1024 * 1024), 2),
            "columnas": len(perfil["columnas"]),
            "columnasSinDiccionario": len(perfil["diccionario"]),
            "valoresCentinela": perfil["valoresCentinela"],
            "nombresDuplicados": perfil["nombresDuplicados"],
            "clasificacion": "publico" if es_sintetico else "interno",
            "origen": "subida",
            "procedencia": procedencia,
        }
        resultado = almacen.aplicar("anadirDataset", {"investigacion_id": investigacion_id, "dataset": dataset, "id_": dataset_id})
        return {"ok": resultado is not False, "datasetId": dataset_id, "fichero": ruta.name, "bytes": tamano, "perfil": {k: perfil[k] for k in ("filas", "valoresCentinela", "nombresDuplicados", "tabular")}, "version": almacen.version}

    @app.get("/api/politicas")
    async def politicas_actuales() -> dict[str, Any]:
        from rosa import politicas

        return politicas.resumen()

    @app.post("/api/investigaciones/{investigacion_id}/preguntar")
    async def preguntar_con_herramientas(investigacion_id: str, cuerpo: dict[str, Any]) -> dict[str, Any]:
        """Una pregunta con herramientas (conectores, búsqueda en el proyecto,
        modelo de mundo) hecha por una persona desde la interfaz. Corre un
        ReAct acotado con el cerebro y guarda la respuesta con sus consultas."""
        from rosa import herramientas as H
        from rosa.bucle.pasos import _texto_mision
        from rosa.gateway import modelos as cargar_modelos

        inv = next((i for i in almacen.estado["investigaciones"] if i["id"] == investigacion_id), None)
        pregunta = str(cuerpo.get("pregunta", "")).strip()
        if not inv or not pregunta:
            raise HTTPException(400, "Falta la pregunta o la investigación")
        quien = str(cuerpo.get("quien", "persona"))[:80]
        hoy = time.strftime("%Y-%m-%d")
        cont = app.state.preguntas_hoy
        if cont["dia"] != hoy:
            cont.update(dia=hoy, n=0)
        if cont["n"] >= config.PREGUNTAS_MAX_DIA:
            raise HTTPException(429, f"Tope de {config.PREGUNTAS_MAX_DIA} preguntas con herramientas por dia alcanzado (ROSA_PREGUNTAS_MAX_DIA)")
        cont["n"] += 1
        modelos_ = getattr(app.state, "modelos", None) or cargar_modelos()
        app.state.modelos = modelos_
        async with app.state.semaforo_preguntas:
            try:
                r = await asyncio.wait_for(H.preguntar(modelos_.cerebro, almacen.estado, investigacion_id, pregunta[:2000], f"Objetivo: {inv['objetivo']}. {_texto_mision(inv)}", almacen=almacen), timeout=600)
                r["pregunta"], r["quien"], r["error"] = pregunta[:2000], quien, None
            except Exception as ex:  # noqa: BLE001
                print(f"preguntar con herramientas fallo: {type(ex).__name__}: {str(ex)[:300]}", file=sys.stderr)
                r = {"pregunta": pregunta[:2000], "quien": quien, "respuesta": "", "limites": "", "herramientas": [], "consultas": [], "iteraciones": 0, "error": "El modelo o una herramienta no respondieron; el detalle está en el registro del servidor"}
        almacen.aplicar("registrarPreguntaBases", {"investigacion_id": investigacion_id, "pregunta": r})
        return {"ok": r.get("error") is None, "resultado": {k: v for k, v in r.items() if k != "consultas"} | {"consultas": len(r.get("consultas", []))}, "version": almacen.version}

    @app.get("/api/espejo")
    async def espejo_estado() -> dict[str, Any]:
        """Estado del espejo del estado en Convex (apagado si no hay clave)."""
        esp = getattr(app.state, "espejo", None)
        if esp is None:
            from rosa import espejo_convex

            return {"activo": espejo_convex.activo(), "url": None, "ultimaVersion": None, "sincronizadoEn": None, "entidades": 0, "pendiente": False, "error": None, "envios": 0, "ms": 0}
        return {k: (v if k != "url" else (v.split("//")[-1] if v else None)) for k, v in esp.estado.items()}

    @app.get("/api/skills")
    async def skills_actuales() -> list[dict[str, Any]]:
        from rosa import skills as SK

        return SK.catalogo()

    @app.get("/api/buscar")
    async def buscar_por_significado(q: str, investigacion: str | None = None, k: int = 8):
        """Búsqueda por significado en el registro (hechos, hipótesis, fuentes)
        con el índice semántico; complementa a la búsqueda por palabras de la
        interfaz. Sin clave del gateway devuelve una lista vacía y lo dice."""
        from rosa import indice_semantico

        if not indice_semantico.disponible():
            return {"disponible": False, "resultados": []}
        indice = indice_semantico.de_almacen(almacen)
        try:
            resultados = await indice.buscar(q[:500], k=max(1, min(k, 30)), investigacion_id=investigacion or None)
        except Exception as ex:  # noqa: BLE001
            return {"disponible": True, "resultados": [], "error": f"No se pudo buscar: {str(ex)[:120]}"}
        return {"disponible": True, "resultados": resultados}

    @app.get("/api/conectores")
    async def conectores_actuales() -> list[dict[str, Any]]:
        from rosa.conectores import catalogo

        return catalogo()

    @app.get("/api/salud")
    async def salud() -> dict[str, Any]:
        return {"ok": True, "version": almacen.version}

    if config.FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

        raiz_dist = config.FRONTEND_DIST.resolve()

        @app.get("/{ruta:path}")
        async def frontend(ruta: str) -> FileResponse:
            # Sin salto de directorio: el fichero tiene que quedar dentro de dist.
            candidato = (raiz_dist / ruta).resolve()
            if ruta and candidato.is_relative_to(raiz_dist) and candidato.is_file():
                return FileResponse(candidato)
            return FileResponse(raiz_dist / "index.html")

    return app
