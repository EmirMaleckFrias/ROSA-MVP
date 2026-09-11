"""El almacen: un estado, una base SQLite, y quien quiera enterarse.

Es el equivalente de `frontend/src/datos/almacen.ts` en el servidor:

- `estado` es el diccionario canonico (forma de `EstadoRosa`).
- Cada cambio pasa por `aplicar(nombre, **args)` (una accion de la interfaz)
  o por `mutar(fn)` (el bucle, que cambia varias cosas a la vez). Los dos
  suben la version, guardan la instantanea en SQLite y avisan a los
  suscriptores (las conexiones SSE del servidor).
- La tabla `acciones` es un registro solo de anadir: que se pidio, con que
  argumentos y cuando. Sirve de auditoria y para reproducir el estado.
- La tabla `llamadas` guarda cada llamada a un modelo (modelo, tokens, ms,
  corrida, iteracion) para las pantallas de gasto y calidad.

SQLite en modo WAL con un solo escritor: este proceso. Un `threading.Lock`
serializa las escrituras porque DSPy hace llamadas en hilos.
"""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable

from rosa import config
from rosa.estado import acciones as A
from rosa.estado import plantilla as P

ESQUEMA = """
CREATE TABLE IF NOT EXISTS estado (
  clave TEXT PRIMARY KEY,
  version INTEGER NOT NULL,
  json TEXT NOT NULL,
  actualizado_en INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS acciones (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  t INTEGER NOT NULL,
  nombre TEXT NOT NULL,
  args TEXT NOT NULL,
  resultado TEXT,
  version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS llamadas (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  t INTEGER NOT NULL,
  modelo TEXT NOT NULL,
  rol TEXT,
  corrida_id TEXT,
  iteracion INTEGER,
  tokens_entrada INTEGER,
  tokens_salida INTEGER,
  ms INTEGER,
  ok INTEGER NOT NULL,
  error TEXT
);
CREATE INDEX IF NOT EXISTS ix_llamadas_corrida ON llamadas(corrida_id, seq);
"""


def _limpiar_para_cliente(valor: Any) -> Any:
    """Quita las claves privadas (empiezan por `_`) antes de mandar el estado
    al navegador. Son banderas internas del bucle."""
    if isinstance(valor, dict):
        return {k: _limpiar_para_cliente(v) for k, v in valor.items() if not (isinstance(k, str) and k.startswith("_"))}
    if isinstance(valor, list):
        return [_limpiar_para_cliente(v) for v in valor]
    return valor


class Almacen:
    def __init__(self, ruta: Path | str | None = None):
        self.ruta = Path(ruta) if ruta else config.RUTA_BD
        self._lock = threading.RLock()
        self._con = sqlite3.connect(str(self.ruta), timeout=30.0, check_same_thread=False, isolation_level=None)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA synchronous=NORMAL")
        self._con.execute("PRAGMA busy_timeout=30000")
        self._con.executescript(ESQUEMA)
        self.version = 0
        self.estado: dict[str, Any] = self._cargar()
        self._suscriptores: set[asyncio.Queue] = set()
        self._bucle_asyncio: asyncio.AbstractEventLoop | None = None

    # -- persistencia ------------------------------------------------------

    def _cargar(self) -> dict[str, Any]:
        fila = self._con.execute("SELECT version, json FROM estado WHERE clave='rosa'").fetchone()
        if fila is None:
            estado = P.estado_inicial()
            self._con.execute("INSERT INTO estado VALUES ('rosa', 0, ?, ?)", (json.dumps(estado, ensure_ascii=False), P.ahora_ms()))
            return estado
        self.version = fila[0]
        estado = json.loads(fila[1])
        # Campos nuevos que un estado guardado con una version anterior no tenga.
        for k, v in P.estado_inicial().items():
            estado.setdefault(k, v)
        _migrar(estado)
        return estado

    def _guardar(self) -> None:
        self._con.execute("UPDATE estado SET version=?, json=?, actualizado_en=? WHERE clave='rosa'", (self.version, json.dumps(self.estado, ensure_ascii=False), P.ahora_ms()))

    # -- lectura -----------------------------------------------------------

    def instantanea(self) -> dict[str, Any]:
        """Copia del estado tal como la ve el navegador."""
        with self._lock:
            e = _limpiar_para_cliente(self.estado)
            e["conexion"] = "en_linea"
            return e

    def instantanea_json(self) -> str:
        return json.dumps(self.instantanea(), ensure_ascii=False)

    # -- escritura ---------------------------------------------------------

    def mutar(self, fn: Callable[[dict[str, Any]], Any], nombre: str = "bucle", args: dict | None = None) -> Any:
        """Aplica `fn(estado)` bajo el cerrojo. Si devuelve algo distinto de
        False, sube la version, guarda y avisa."""
        with self._lock:
            resultado = fn(self.estado)
            if resultado is False:
                return False
            self.version += 1
            self._guardar()
            self._con.execute("INSERT INTO acciones(t, nombre, args, resultado, version) VALUES (?,?,?,?,?)", (P.ahora_ms(), nombre, json.dumps(args or {}, ensure_ascii=False, default=str), json.dumps(resultado, default=str), self.version))
            self._avisar()
            return resultado

    def aplicar(self, nombre: str, args: dict[str, Any]) -> Any:
        """Una accion de la interfaz por nombre (ver ACCIONES). Devuelve el
        resultado del reducer; lanza KeyError si la accion no existe."""
        fn, con_ahora = ACCIONES[nombre]
        kwargs = dict(args)
        if con_ahora and "ahora" not in kwargs:
            kwargs["ahora"] = P.ahora_ms()
        return self.mutar(lambda e: fn(e, **kwargs), nombre, args)

    def registrar_llamada(self, modelo: str, rol: str | None, corrida_id: str | None, iteracion: int | None, tokens_entrada: int, tokens_salida: int, ms: int, ok: bool, error: str | None = None) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO llamadas(t, modelo, rol, corrida_id, iteracion, tokens_entrada, tokens_salida, ms, ok, error) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (P.ahora_ms(), modelo, rol, corrida_id, iteracion, tokens_entrada, tokens_salida, ms, 1 if ok else 0, error),
            )

    def evidencia_de(self, corrida_id: str) -> dict[str, Any] | None:
        """La cadena de trazabilidad de una corrida: consultas, fuentes (con la
        consulta que las trajo) y afirmaciones con veredicto. Sin los
        fragmentos completos, para que pese poco."""
        with self._lock:
            c = next((x for x in self.estado["corridas"] if x["id"] == corrida_id), None)
            if not c:
                return None
            fuentes = []
            for f in c.get("_fuentes", {}).values():
                fuentes.append(
                    {
                        "id": f["id"],
                        "referencia": f["referencia"],
                        "titulo": f["titulo"],
                        "tipo": f["tipo"],
                        "doi": f.get("doi"),
                        "pmid": f.get("pmid"),
                        "nct": f.get("nct"),
                        "anio": f.get("anio"),
                        "tipoEstudio": f.get("tipoEstudio"),
                        "relevancia": f.get("relevancia", 0),
                        "retraccion": f.get("retraccion"),
                        "retraccionDetalle": f.get("_marcaDetalle", ""),
                        "textoCompleto": bool(f.get("textoCompleto")),
                        "fragmentos": len(f.get("fragmentos", [])),
                        "extraida": bool(f.get("extraida")),
                        "iteracion": f.get("iteracion", 0),
                        "consultas": list(f.get("consultas", [])),
                    }
                )
            afirmaciones = [
                {k: a.get(k) for k in ("id", "texto", "cita", "veredicto", "motivo", "entidadDistinta", "tipo", "tema", "fuenteId", "localizador", "iteracion")}
                for a in c.get("_afirmaciones", [])
            ]
            return {"corridaId": corrida_id, "version": self.version, "consultas": list(c["busqueda"]["consultas"]), "fuentes": fuentes, "afirmaciones": afirmaciones}

    def llamadas_de(self, corrida_id: str, limite: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            filas = self._con.execute("SELECT t, modelo, rol, iteracion, tokens_entrada, tokens_salida, ms, ok, error FROM llamadas WHERE corrida_id=? ORDER BY seq DESC LIMIT ?", (corrida_id, limite)).fetchall()
        claves = ["t", "modelo", "rol", "iteracion", "tokensEntrada", "tokensSalida", "ms", "ok", "error"]
        return [dict(zip(claves, f)) for f in filas]

    # -- suscripciones (SSE) ----------------------------------------------

    def enganchar_bucle(self, bucle: asyncio.AbstractEventLoop) -> None:
        self._bucle_asyncio = bucle

    def suscribir(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._suscriptores.add(q)
        return q

    def desuscribir(self, q: asyncio.Queue) -> None:
        self._suscriptores.discard(q)

    def _avisar(self) -> None:
        if not self._suscriptores or self._bucle_asyncio is None:
            return
        version = self.version

        def poner() -> None:
            for q in list(self._suscriptores):
                if q.full():
                    # Un cliente lento: se le quita lo viejo, solo importa lo ultimo.
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(version)

        try:
            self._bucle_asyncio.call_soon_threadsafe(poner)
        except RuntimeError:
            pass

    def cerrar(self) -> None:
        with self._lock:
            self._con.commit()
            self._con.close()


def _migrar(estado: dict[str, Any]) -> None:
    _migrar_fragmentos(estado)
    _migrar_consultas(estado)
    _migrar_conclusiones(estado)
    _migrar_experimentos(estado)
    _migrar_rosa2018(estado)


def _migrar_rosa2018(estado: dict[str, Any]) -> None:
    """Campos de septiembre de 2026 (mision, tarjeta, versiones, decisiones,
    puerta, procedencia de datasets) en estados guardados antes. Las
    politicas se refrescan siempre desde el codigo: no viven en el estado."""
    estado["politicas"] = P._politicas()
    if not estado.get("metodos"):
        estado["metodos"] = P.metodos_iniciales()
    for inv in estado.get("investigaciones", []):
        inv.setdefault("mision", None)
        inv.setdefault("puertaReproduccion", P.puerta_reproduccion())
        if inv.get("mision"):
            for k, v in P.mision_vacia().items():
                inv["mision"].setdefault(k, v)
        for ds in inv.get("datasets", []):
            ds.setdefault("procedencia", None)
    for c in estado.get("corridas", []):
        c.setdefault("pregunta", None)
        c["gasto"].setdefault("usd", 0.0)
    for h in estado.get("hipotesis", []):
        h.setdefault("tarjeta", None)
        h.setdefault("version", 1)
        h.setdefault("versiones", [])
        h.setdefault("decisionKiller", None)
        h.setdefault("bloqueos", [])
        h.setdefault("candidata", False)
        h.setdefault("dossierArtefactoId", None)
        h.setdefault("ejecuciones", [])
        for a in h.get("afirmaciones", []):
            a.setdefault("clase", "derivado" if a.get("tipo") == "dato" and a.get("trayectoria") else "literatura")
            a.setdefault("sintetico", False)
    # Los bloqueos se recalculan al arrancar: la regla vive en el codigo y puede
    # haber cambiado desde que se guardaron.
    from rosa.priorizacion import bloqueos_de

    for h in estado.get("hipotesis", []):
        h["bloqueos"] = bloqueos_de(estado, h)


def _migrar_experimentos(estado: dict[str, Any]) -> None:
    """Los experimentos del primer esquema (protocolo en un parrafo, criterios
    dentro del ensayo) se regeneran si aun no se asignaron. Los ya
    prerregistrados no se tocan: el prerregistro es inmutable."""
    for h in estado.get("hipotesis", []):
        x = h.get("experimento")
        if x and "confirma" not in x and x.get("estado") == "propuesto":
            h["experimento"] = None
            h.pop("_experimentoIntentado", None)


def _migrar_conclusiones(estado: dict[str, Any]) -> None:
    """Las conclusiones escritas con el primer esquema (grado unico, sin
    certeza, direccion ni factores) se retiran para que el bucle las
    reescriba con el esquema GRADE."""
    for h in estado.get("hipotesis", []):
        c = h.get("conclusion")
        if c and ("certeza" not in c or "hipotesisBreve" not in c):
            h["conclusion"] = None
            h.pop("_conclusionIntentada", None)
    for it in estado.get("iteraciones", []):
        r = it.get("resumenLlano")
        if r and "mensajesClave" not in r:
            it.pop("resumenLlano", None)  # ausente = pendiente; None = el modelo fallo
            it.pop("_llanoIntentado", None)


def _migrar_fragmentos(estado: dict[str, Any]) -> None:
    """Las hipotesis anteriores al 10 de septiembre de 2026 no llevaban el
    pasaje literal en cada afirmacion; se recupera de las afirmaciones de la
    corrida por su cita y texto."""
    for h in estado.get("hipotesis", []):
        if all("fragmento" in a for a in h.get("afirmaciones", [])):
            continue
        corridas = [c for c in estado.get("corridas", []) if c["investigacionId"] == h["investigacionId"]]
        indice = {}
        for c in corridas:
            for a in c.get("_afirmaciones", []):
                indice[(a["cita"], a["texto"])] = (a.get("fragmento") or "")[:600]
        for a in h.get("afirmaciones", []):
            a.setdefault("fragmento", indice.get((a["cita"], a["texto"]), ""))


def _migrar_consultas(estado: dict[str, Any]) -> None:
    """Ajustes a estados guardados por versiones anteriores de Rosa. Cada uno
    es idempotente. Hoy: las consultas de busqueda anteriores al 10 de
    septiembre de 2026 no llevaban `iteracion`; se infiere por la fecha dentro
    de la ventana de cada iteracion de su corrida."""
    for c in estado.get("corridas", []):
        its = sorted([i for i in estado.get("iteraciones", []) if i["corridaId"] == c["id"]], key=lambda i: i["numero"])
        for q in c.get("busqueda", {}).get("consultas", []):
            if q.get("iteracion"):
                continue
            for i in its:
                fin = i["terminadaEn"] if i["terminadaEn"] is not None else float("inf")
                if i["planPropuestoEn"] <= q["fecha"] <= fin:
                    q["iteracion"] = i["numero"]
                    break
            else:
                if its:
                    q["iteracion"] = its[-1]["numero"]


def _con_ahora(fn: Callable) -> bool:
    return "ahora" in inspect.signature(fn).parameters


# Nombre de la accion en la interfaz -> (funcion, si necesita `ahora`).
# Los nombres son los de `acciones` en almacen.ts, en camelCase, para que la
# correspondencia sea de uno a uno.
_TABLA: dict[str, Callable] = {
    "marcarVisita": A.marcar_visita,
    "pausarCorrida": A.pausar_corrida,
    "reanudarCorrida": A.reanudar_corrida,
    "detenerCorrida": A.detener_corrida,
    "ampliarPresupuesto": A.ampliar_presupuesto,
    "dirigirCorrida": A.dirigir_corrida,
    "editarPlan": A.editar_plan,
    "aprobarPlan": A.aprobar_plan,
    "fijarAutoaprobacionPlan": A.fijar_autoaprobacion_plan,
    "detenerPista": A.detener_pista,
    "detenerProceso": A.detener_proceso,
    "volverAIteracion": A.volver_a_iteracion,
    "resolverSolicitud": A.resolver_solicitud,
    "resolverSolicitudes": A.resolver_solicitudes,
    "revocarPermiso": A.revocar_permiso,
    "resolverIncidencia": A.resolver_incidencia,
    "fijarAutonomia": A.fijar_autonomia,
    "revisarHipotesis": A.revisar_hipotesis,
    "votarRelevancia": A.votar_relevancia,
    "solicitarRevision": A.solicitar_revision,
    "replicarHipotesis": A.replicar_hipotesis,
    "proponerHipotesis": A.proponer_hipotesis,
    "asignarExperimento": A.asignar_experimento,
    "registrarDatosExperimento": A.registrar_datos_experimento,
    "anadirComentario": A.anadir_comentario,
    "editarComentario": A.editar_comentario,
    "quitarComentario": A.quitar_comentario,
    "enviarComentarios": A.enviar_comentarios,
    "inyectarDebilidad": A.inyectar_debilidad,
    "recomprobarRetracciones": A.recomprobar_retracciones,
    "crearInvestigacion": A.crear_investigacion,
    "bifurcarInvestigacion": A.bifurcar_investigacion,
    "actualizarConfiguracion": A.actualizar_configuracion,
    "anadirDataset": A.anadir_dataset,
    "decidirDataset": A.decidir_dataset,
    "aprobarDiccionario": A.aprobar_diccionario,
    "corregirDataset": A.corregir_dataset,
    "clasificarDataset": A.clasificar_dataset,
    "destacarArtefacto": A.destacar_artefacto,
    "guardarArtefacto": A.guardar_artefacto,
    "cambiarEstadoCaso": A.cambiar_estado_caso,
    "editarRespuestaCaso": A.editar_respuesta_caso,
    "editarRecuerdo": A.editar_recuerdo,
    "borrarRecuerdo": A.borrar_recuerdo,
    "anadirCriterio": A.anadir_criterio,
    "borrarCriterio": A.borrar_criterio,
    "actualizarAvisos": A.actualizar_avisos,
    "actualizarPoliticaEsperas": A.actualizar_politica_esperas,
    "borrarPlanGuardado": A.borrar_plan_guardado,
    "iniciarCorrida": A.iniciar_corrida,
    # ROSA2018
    "aprobarMision": A.aprobar_mision,
    "reformularHipotesis": A.reformular_hipotesis,
    "eximirPuerta": A.eximir_puerta,
    "cerrarPuerta": A.cerrar_puerta,
    "anadirReproduccion": A.anadir_reproduccion,
    "pedirAnalisis": A.pedir_analisis,
    "promoverAprendizaje": A.promover_aprendizaje,
    "revertirAprendizaje": A.revertir_aprendizaje,
    "generarDossier": A.generar_dossier,
    "actualizarProcedenciaDataset": A.actualizar_procedencia_dataset,
    "evaluarAprendizaje": A.evaluar_aprendizaje,
    "actualizarPregunta": A.actualizar_pregunta,
    "actualizarMetodo": A.actualizar_metodo,
    "enmendarExperimento": A.enmendar_experimento,
    "registrarProtocoloReal": A.registrar_protocolo_real,
    "cambiarEstadoArea": A.cambiar_estado_area,
}

ACCIONES: dict[str, tuple[Callable, bool]] = {n: (f, _con_ahora(f)) for n, f in _TABLA.items()}


def copia_profunda(e: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(e)
