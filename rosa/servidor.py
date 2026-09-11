"""El servidor HTTP de Rosa (FastAPI).

Tres rutas y nada mas, porque el frontend ya sabe hacer el resto:

- `GET /api/estado`: la instantanea completa del estado (forma `EstadoRosa`).
- `GET /api/eventos`: Server-Sent Events. Cada vez que el estado cambia, el
  servidor manda la instantanea completa con `id` igual a la version. El
  navegador reconecta solo si se corta.
- `POST /api/acciones/{nombre}`: una accion de la interfaz con sus
  argumentos en JSON. Devuelve `{ok, resultado, version}`.

Ademas `GET /api/llamadas/{corridaId}` da las ultimas llamadas a modelos y,
si existe `frontend/dist`, sirve la interfaz compilada en la raiz.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from rosa import config
from rosa.estado.almacen import ACCIONES, Almacen


def crear_app(almacen: Almacen) -> FastAPI:
    app = FastAPI(title="Rosa", version="0.1")
    app.state.almacen = almacen

    @app.on_event("startup")
    async def _arranque() -> None:
        almacen.enganchar_bucle(asyncio.get_running_loop())

    @app.get("/api/estado")
    async def estado() -> JSONResponse:
        return JSONResponse(content=almacen.instantanea(), headers={"Cache-Control": "no-store", "X-Rosa-Version": str(almacen.version)})

    @app.get("/api/eventos")
    async def eventos(request: Request) -> EventSourceResponse:
        cola = almacen.suscribir()

        async def generar():
            try:
                yield {"event": "estado", "id": str(almacen.version), "data": almacen.instantanea_json(), "retry": 2000}
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        await asyncio.wait_for(cola.get(), timeout=10)
                    except asyncio.TimeoutError:
                        continue
                    # Coalescer: si llegaron varias versiones, solo importa la ultima.
                    while not cola.empty():
                        cola.get_nowait()
                    yield {"event": "estado", "id": str(almacen.version), "data": almacen.instantanea_json()}
            finally:
                almacen.desuscribir(cola)

        # El latido es un evento real (no un comentario) para que el navegador
        # pueda detectar un flujo muerto: si pasa por un proxy (Vite en
        # desarrollo) y el servidor se reinicia, el proxy puede dejar la
        # conexion abierta sin datos y EventSource no se entera solo.
        return EventSourceResponse(generar(), ping=15, ping_message_factory=lambda: ServerSentEvent(event="latido", data=str(almacen.version)), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/acciones/{nombre}")
    async def accion(nombre: str, request: Request) -> dict[str, Any]:
        if nombre not in ACCIONES:
            raise HTTPException(404, f"Accion desconocida: {nombre}")
        try:
            args = await request.json()
        except json.JSONDecodeError:
            args = {}
        if not isinstance(args, dict):
            raise HTTPException(400, "Los argumentos van como objeto JSON")
        try:
            resultado = almacen.aplicar(nombre, args)
        except TypeError as ex:
            raise HTTPException(400, f"Argumentos invalidos para {nombre}: {ex}")
        return {"ok": resultado is not False, "resultado": resultado, "version": almacen.version}

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
            raise HTTPException(404, "Hipotesis sin experimento propuesto")
        contenido = await fichero.read()
        try:
            ruta = D.guardar(hipotesis_id, fichero.filename or "datos", contenido)
        except ValueError as ex:
            raise HTTPException(413, str(ex))
        resultado = almacen.aplicar("registrarDatosExperimento", {"hipotesis_id": hipotesis_id, "fichero": ruta.name, "analisis": analisis})
        return {"ok": resultado is not False, "fichero": ruta.name, "bytes": len(contenido), "version": almacen.version}

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
            raise HTTPException(404, "Investigacion desconocida")
        contenido = await fichero.read()
        dataset_id = P.nuevo_id("ds")
        try:
            ruta = D.guardar_dataset(investigacion_id, dataset_id, fichero.filename or "datos", contenido)
        except ValueError as ex:
            raise HTTPException(413, str(ex))
        perfil = D.perfil_dataset(ruta)
        es_sintetico = sintetico.strip().lower() in ("si", "sí", "true", "1", "yes")
        procedencia = {**P.procedencia_dataset_vacia(), "hash": hash_fichero(ruta), "fichero": ruta.name, "filas": perfil["filas"], "diccionario": perfil["diccionario"], "columnas": perfil["columnas"], "sintetico": es_sintetico, "fechaObtencion": P.ahora_ms(), "clase": "prediccion" if es_sintetico else "observacion_original", "permiteLlmTerceros": es_sintetico}
        dataset = {
            "nombre": nombre.strip() or (fichero.filename or "datos"),
            "descripcion": descripcion.strip(),
            "tamanoMb": round(len(contenido) / (1024 * 1024), 2),
            "columnas": len(perfil["columnas"]),
            "columnasSinDiccionario": len(perfil["diccionario"]),
            "valoresCentinela": perfil["valoresCentinela"],
            "nombresDuplicados": perfil["nombresDuplicados"],
            "clasificacion": "publico" if es_sintetico else "interno",
            "origen": "subida",
            "procedencia": procedencia,
        }
        resultado = almacen.aplicar("anadirDataset", {"investigacion_id": investigacion_id, "dataset": dataset, "id_": dataset_id})
        return {"ok": resultado is not False, "datasetId": dataset_id, "fichero": ruta.name, "bytes": len(contenido), "perfil": {k: perfil[k] for k in ("filas", "valoresCentinela", "nombresDuplicados", "tabular")}, "version": almacen.version}

    @app.get("/api/politicas")
    async def politicas_actuales() -> dict[str, Any]:
        from rosa import politicas

        return politicas.resumen()

    @app.get("/api/conectores")
    async def conectores_actuales() -> list[dict[str, Any]]:
        from rosa.conectores import catalogo

        return catalogo()

    @app.get("/api/salud")
    async def salud() -> dict[str, Any]:
        return {"ok": True, "version": almacen.version}

    if config.FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{ruta:path}")
        async def frontend(ruta: str) -> FileResponse:
            candidato = config.FRONTEND_DIST / ruta
            if ruta and candidato.is_file():
                return FileResponse(candidato)
            return FileResponse(config.FRONTEND_DIST / "index.html")

    return app
