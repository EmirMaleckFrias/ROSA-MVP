"""Arranque de Rosa: servidor HTTP, supervisor del bucle y trazas MLflow en
un solo proceso.

    uv run python -m rosa.main

Abre http://127.0.0.1:8765 si el frontend esta compilado (frontend/dist), o
usa el servidor de Vite en el 5174, que reenvia /api aqui.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
import sys

import dspy
import uvicorn

from rosa import config
from rosa.bucle.corrida import Supervisor
from rosa.estado.almacen import Almacen
from rosa.gateway import modelos as cargar_modelos
from rosa.modulos.contador import Contador
from rosa.modulos.firmas import Programas
from rosa.servidor import crear_app


def configurar_mlflow() -> None:
    try:
        import mlflow

        mlflow.set_tracking_uri(config.MLFLOW_URI)
        mlflow.set_experiment("rosa")
        mlflow.dspy.autolog(log_traces=True, silent=True)
    except Exception as ex:  # noqa: BLE001
        print(f"MLflow no disponible ({ex}); Rosa sigue sin trazas.", file=sys.stderr)


async def principal() -> None:
    if config.HOST not in ("127.0.0.1", "localhost", "::1") and not config.ROSA_TOKEN:
        print(f"Rosa no arranca escuchando en {config.HOST} sin ROSA_TOKEN en .env: cualquier equipo de la red podria gastar en el gateway y alterar el estado.", file=sys.stderr)
        raise SystemExit(2)
    almacen = Almacen()
    modelos = cargar_modelos()
    programas = Programas()
    cargados = programas.cargar_optimizados(config.RAIZ / "mlruns" / "optimizados")
    if cargados:
        print(f"Programas optimizados por GEPA cargados: {', '.join(cargados)}")
    contador = Contador(almacen)
    from rosa.gepa_continuo import Servicio
    gepa = Servicio(almacen, programas, modelos)
    almacen.gepa_servicio = gepa
    from rosa.conectores import base as conectores_base
    conectores_base.OBSERVADOR = gepa.observar_conector
    dspy.configure(lm=modelos.cerebro, callbacks=[contador, gepa.trazador])
    configurar_mlflow()

    app = crear_app(almacen)
    servidor = uvicorn.Server(uvicorn.Config(app, host=config.HOST, port=config.PUERTO, log_level="warning", loop="asyncio"))
    supervisor = Supervisor(almacen, programas, modelos)

    bucle = asyncio.get_running_loop()
    almacen.enganchar_bucle(bucle)
    # Espejo del estado en Convex, si hay clave en .env. Solo lectura remota;
    # SQLite sigue siendo la fuente de verdad.
    from rosa.espejo_convex import Espejo

    espejo = Espejo(almacen)
    app.state.espejo = espejo
    espejo.arrancar()
    if espejo.estado["activo"]:
        print(f"Espejo en Convex activo: {config.CONVEX_URL}")

    def parar(*_: object) -> None:
        supervisor.parar()
        servidor.should_exit = True

    for s in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            bucle.add_signal_handler(s, parar)

    print(f"Rosa en http://{config.HOST}:{config.PUERTO}  (base {config.RUTA_BD.name}, versión {almacen.version})")
    tarea_gepa = asyncio.create_task(gepa.correr(), name="gepa-continuo")
    try:
        await asyncio.gather(servidor.serve(), supervisor.correr())
    finally:
        gepa.parar.set()
        try:
            # Un compile de GEPA en marcha no se puede cortar desde fuera; el apagado no se queda colgado esperándolo.
            await asyncio.wait_for(tarea_gepa, timeout=15)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            print("GEPA continuo no terminó en 15 s; se apaga sin esperarlo (el ciclo en curso queda auditado como interrumpido)", file=sys.stderr)
        conectores_base.OBSERVADOR = None
        gepa.registro.cerrar()
    # Apagado ordenado: primero las tareas del bucle y el espejo, despues SQLite.
    await espejo.parar()
    almacen.cerrar()


if __name__ == "__main__":
    asyncio.run(principal())
