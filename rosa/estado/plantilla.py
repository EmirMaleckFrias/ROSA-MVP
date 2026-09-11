"""Estado inicial y constructores de objetos del dominio.

La forma de cada objeto es la de `frontend/src/datos/tipos.ts`, campo por
campo y con los mismos nombres (camelCase). El frontend no valida: pinta lo
que recibe, asi que aqui se rellenan todos los campos siempre.

Los tiempos son milisegundos desde 1970, como `Date.now()` en el navegador.
"""

from __future__ import annotations

import itertools
import json
import time
from pathlib import Path
from typing import Any

from rosa import config

_contador = itertools.count(1)


def ahora_ms() -> int:
    return int(time.time() * 1000)


def nuevo_id(prefijo: str) -> str:
    """Ids legibles: prefijo, tiempo en base 36 y un contador. Mismo estilo que
    `nuevoId` del frontend para que se distingan a simple vista."""
    t = ahora_ms()
    base36 = ""
    digitos = "0123456789abcdefghijklmnopqrstuvwxyz"
    while t:
        t, r = divmod(t, 36)
        base36 = digitos[r] + base36
    return f"{prefijo}-{base36}-{next(_contador)}"


CLASES_ACCION = ["buscar_literatura", "correr_analisis", "gastar_grande", "escribir_modelo_mundo", "descartar_hipotesis", "contactar_laboratorio"]

CRITERIOS_INICIALES = [
    "Distinguir 'no esta en los documentos' de 'no pude comprobar'.",
    "Una cifra sin cita a pagina exacta no se afirma.",
    "Marcar como interpretacion lo que la fuente no dice literalmente.",
    "Si el dato es de otra entidad (otro farmaco, cohorte o estudio), no se atribuye.",
]

TIPOS_REVISION = ["inicial", "completa", "profunda", "observacion", "simulacion", "torneo"]


def casos_de_control() -> list[dict[str, Any]]:
    """Los 17 casos del RAG anterior, tal como se traspasaron (todos sin aprobar)."""
    ruta = Path(config.RAIZ) / "casos_evaluacion.jsonl"
    if not ruta.exists():
        return []
    casos = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        d = json.loads(linea)
        casos.append(
            {
                "clave": d["clave"],
                "categoria": d["categoria"],
                "pregunta": d["pregunta"],
                "respuestaEsperada": d.get("respuestaEsperada", ""),
                "estado": d.get("estado", "propuesto"),
                "critico": bool(d.get("critico", False)),
                "origen": d.get("origen", "generado"),
            }
        )
    return casos


def estado_inicial() -> dict[str, Any]:
    """Un estado vacio pero completo: sin investigaciones, con los ajustes por
    defecto y los casos de control reales."""
    return {
        "conexion": "en_linea",
        "investigaciones": [],
        "corridas": [],
        "iteraciones": [],
        "solicitudes": [],
        "incidencias": [],
        "permisos": [],
        "autonomia": {c: ("preguntar" if c in ("gastar_grande", "contactar_laboratorio", "descartar_hipotesis") else "actuar") for c in CLASES_ACCION},
        "hipotesis": [],
        "comentarios": [],
        "hechos": [],
        "artefactos": [],
        "casos": casos_de_control(),
        "metricas": [],
        "gepa": [],
        "memoria": [],
        "planesGuardados": [
            {"id": "plan-novedad", "nombre": "Comprobacion de novedad estandar", "pasos": ["Open Targets", "ClinicalTrials.gov v2", "Precedente en literatura (OpenAlex)"], "vecesUsado": 0, "exitos": 0},
        ],
        "criteriosRevision": list(CRITERIOS_INICIALES),
        "avisos": {
            "correo": {"activo": False, "direccion": ""},
            "slack": {"activo": False, "canal": ""},
            "cuando": {"hipotesisNueva": True, "permisoPendiente": True, "corridaDetenida": True, "resumenDiario": False},
        },
        "politicaEsperas": {"horas": 24, "accion": "recordar", "escalarA": ""},
        "eventos": [],
        "ultimaVisita": None,
    }


# ---------------------------------------------------------------------------
# Constructores
# ---------------------------------------------------------------------------


def nueva_corrida(investigacion_id: str, numero: int, ahora: int, limite: int | None = None) -> dict[str, Any]:
    return {
        "id": nuevo_id("cor"),
        "investigacionId": investigacion_id,
        "numero": numero,
        "estado": "esperando_plan",
        "empezadaEn": ahora,
        "terminadaEn": None,
        "iteracionActual": 1,
        "gasto": {"tokensEntrada": 0, "tokensSalida": 0, "llamadas": 0, "segundos": 0, "articulosLeidos": 0},
        "motivoCierre": None,
        "presupuesto": {"limiteLlamadas": limite or config.PRESUPUESTO_CORRIDA, "alertas": list(config.ALERTAS_PRESUPUESTO), "avisadas": []},
        "contexto": {"tokensUsados": 0, "tokensLimite": 400_000, "compactaciones": 0, "ultimaCompactacion": None},
        "busqueda": {"identificados": 0, "cribados": 0, "textoCompleto": 0, "usados": 0, "consultas": []},
        "coberturas": [],
        "metaRevisiones": [],
        "procesos": [],
        "panorama": [],
        "autoAprobarPlanSegundos": None,
        "arnes": _arnes(),
    }


def _arnes() -> dict[str, str]:
    from rosa.version import arnes

    return arnes()


def nuevo_paso(titulo: str, detalle: str, presupuesto: int | None = None, humano: bool = False) -> dict[str, Any]:
    return {"id": nuevo_id("paso"), "titulo": titulo, "detalle": detalle, "estado": "pendiente", "indicacionHumana": humano, "motivoFallo": None, "presupuesto": presupuesto}


def nueva_iteracion(corrida_id: str, numero: int, ahora: int, plan: list[dict[str, Any]], limite: int | None = None) -> dict[str, Any]:
    return {
        "id": nuevo_id("it"),
        "corridaId": corrida_id,
        "numero": numero,
        "empezadaEn": ahora,
        "terminadaEn": None,
        "plan": plan,
        "planAprobado": False,
        "planPropuestoEn": ahora,
        "pistas": [],
        "presupuesto": {"limite": limite or config.PRESUPUESTO_ITERACION, "usado": 0},
        "resumen": "",
    }


def nueva_pista(iteracion_id: str, paso_id: str | None, tipo: str, titulo: str, fuente: str) -> dict[str, Any]:
    return {"id": nuevo_id("pi"), "iteracionId": iteracion_id, "pasoId": paso_id, "tipo": tipo, "titulo": titulo, "fuente": fuente, "estado": "en_curso", "resumen": "empezando", "ms": 0, "transcripcion": []}


def nueva_fuente(**campos: Any) -> dict[str, Any]:
    base = {
        "id": nuevo_id("f"),
        "referencia": "",
        "titulo": "",
        "tipo": "articulo",
        "doi": None,
        "pmid": None,
        "nct": None,
        "pagina": None,
        "fragmento": "",
        "retraccion": None,
        "retraccionComprobadaEn": None,
        "anio": None,
        "tipoEstudio": "otro",
        "nivelEvidencia": 2,
        "textoCompleto": False,
        "citas": None,
    }
    base.update(campos)
    return base


def procedencia_vacia(mensaje: str, ahora: int, codigo: str = "", registro: list[str] | None = None) -> dict[str, Any]:
    import dspy

    return {
        "mensajes": [{"id": nuevo_id("m"), "de": "rosa", "texto": mensaje, "creadoEn": ahora}],
        "codigo": codigo,
        "registro": registro or [],
        "entorno": {
            "lenguaje": "Python",
            "version": "3.12",
            "paquetes": [{"nombre": "dspy", "version": dspy.__version__}],
            "modelos": [
                {"nombre": "openai/gpt-6-astra (cerebro)", "version": "gateway"},
                {"nombre": "anthropic/claude-opus-5 (juez)", "version": "gateway"},
                {"nombre": "anthropic/claude-sonnet-5 (extractor)", "version": "gateway"},
            ],
        },
        "fuentes": [],
    }


def novedad_pendiente() -> dict[str, Any]:
    return {
        "openTargets": {"estado": "sin_evidencia", "detalle": "No comprobado todavia"},
        "ensayos": {"estado": "sin_ensayo", "detalle": "No comprobado todavia", "nct": None},
        "agora": {"estado": "no_nominada", "detalle": "No comprobado: Agora no tiene API publica estable. No se afirma ausencia."},
        "precedente": {"estado": "sin_precedente", "detalle": "No comprobado todavia"},
    }


def revisiones_automaticas_pendientes() -> list[dict[str, Any]]:
    return [{"tipo": t, "estado": "pendiente", "resumen": "", "fecha": None} for t in TIPOS_REVISION]


def nueva_hipotesis(investigacion_id: str, iteracion: int, ahora: int, **campos: Any) -> dict[str, Any]:
    h = {
        "id": nuevo_id("hip"),
        "investigacionId": investigacion_id,
        "titulo": "",
        "enunciado": "",
        "mecanismo": "",
        "comprobacion": {"biomarcador": "", "cohorte": "", "diseno": ""},
        "estado": "propuesta",
        "elo": 1500,
        "historialElo": [{"iteracion": iteracion, "elo": 1500}],
        "rivales": [],
        "novedad": novedad_pendiente(),
        "afirmaciones": [],
        "procedencia": procedencia_vacia("Hipotesis generada por Rosa.", ahora),
        "hallazgos": [],
        "revisiones": [{"fecha": ahora, "quien": config.QUIEN_ROSA, "accion": "propuesta", "nota": f"Iteracion {iteracion}", "aCiegas": False}],
        "creadaEn": ahora,
        "iteracion": iteracion,
        "origen": "rosa",
        "derivadaDe": None,
        "cluster": "Sin cluster",
        "evidenciaEstadistica": "no_aplica",
        "relevancia": {"justificacion": "", "votoHumano": None},
        "partidos": [],
        "revisionesAutomaticas": revisiones_automaticas_pendientes(),
        "supuestos": [],
        "revisionesHumanas": [],
        "replicacion": None,
        "ultimaRevisionAutomatica": None,
        "coste": {"literatura": 0, "analisis": 0},
        "experimento": None,
        "prerregistradaEn": ahora,
    }
    h.update(campos)
    return h


def nuevo_hecho(investigacion_id: str, tipo: str, tema: str, enunciado: str, estado: str, origen: str, procedencia: list[dict[str, Any]], ahora: int, prioridad: int = 5, motivo: str = "") -> dict[str, Any]:
    return {
        "id": nuevo_id("he"),
        "investigacionId": investigacion_id,
        "tipo": tipo,
        "tema": tema,
        "enunciado": enunciado,
        "estado": estado,
        "origen": origen,
        "procedencia": procedencia,
        "motivoDescarte": None,
        "actualizadoEn": ahora,
        "prioridad": prioridad,
        "citas": [],
        "historial": [{"fecha": ahora, "de": None, "a": estado, "quien": config.QUIEN_ROSA, "motivo": motivo or "Anadido por Rosa"}],
    }


def nuevo_evento(investigacion_id: str, tipo: str, texto: str, ruta: str | None, t: int) -> dict[str, Any]:
    return {"id": nuevo_id("ev"), "investigacionId": investigacion_id, "t": t, "tipo": tipo, "texto": texto, "ruta": ruta}
