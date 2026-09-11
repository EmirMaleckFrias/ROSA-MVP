"""Las politicas de Rosa: los limites que ningun agente puede editar.

El documento de concepto ROSA2018 (version 1.0, septiembre de 2026) exige
que las reglas de gobierno vivan fuera del alcance de los agentes. En Rosa
eso significa este fichero: el estado (`rosa.db`) lo escriben el bucle y la
interfaz, pero este modulo solo cambia con un commit, y el commit queda
registrado en el `arnes` de cada corrida. Cambiar una politica es un cambio
de aprendizaje de nivel 3: lo hace una persona, se anota en el registro de
aprendizaje y se puede auditar.

Cada constante lleva su motivo. Si alguna vez hace falta cambiarla, cambiar
tambien el motivo.
"""

from __future__ import annotations

# Hipotesis vivas por mision. Mas alla de esto, la cola deja de ser
# revisable por una persona en una sesion y el torneo pierde partidos por
# hipotesis. Rosa deja de generar (no descarta) al llegar aqui.
MAX_HIPOTESIS_VIVAS_POR_MISION = 20

# Evaluaciones costosas (analisis in silico con datos) por mision y corrida.
# Cada una gasta codigo, tiempo de maquina y una auditoria; el documento fija
# cinco para la demostracion.
MAX_EVALUACIONES_COSTOSAS = 5

# Candidatos que salen al laboratorio por ciclo: entre cero y tres. Cero es
# un resultado legitimo (abstenerse); mas de tres no se puede ejecutar.
MAX_CANDIDATOS_LABORATORIO = 3

# Reformulaciones por hipotesis. A la tercera vez que el Killer pide
# reformular, la hipotesis se descarta en este contexto: reformular sin
# limite es la forma de esquivar una critica sin responderla.
MAX_REFORMULACIONES = 2

# Analisis publicados que hay que reproducir, dentro de tolerancia, antes de
# que el modulo de analisis con datos pueda descubrir algo nuevo. Sin esta
# puerta, un resultado nuevo no se distingue de un error del pipeline.
REPRODUCCIONES_REQUERIDAS = 3

# Fraccion de los descartes del Killer que se auditan con un modelo de otra
# familia. Un critico que mata ideas buenas es tan caro como uno que deja
# pasar malas; la auditoria mide lo primero.
FRACCION_DESCARTES_AUDITADOS = 0.34

# Tiempo maximo de una ejecucion in silico y memoria maxima, para el sandbox.
SEGUNDOS_MAX_EJECUCION = 180
MEMORIA_MAX_EJECUCION_MB = 2048

# Presupuesto por defecto de una mision en dinero (dolares, estimado a partir
# de los tokens) y en horas de reloj. Se pueden fijar por mision; estos son
# los topes si nadie dice nada.
PRESUPUESTO_USD_POR_DEFECTO = 60.0
PRESUPUESTO_HORAS_POR_DEFECTO = 72.0

# Decisiones que puede tomar el Killer sobre una hipotesis. El generador no
# esta en la lista: nunca aprueba lo suyo.
DECISIONES_KILLER = ("avanzar", "reformular", "suspender", "descartar_en_contexto")

# Clases de evidencia del libro de procedencia. Cada afirmacion y cada dato
# llevan una; no se mezclan en el mismo recuento.
CLASES_EVIDENCIA = ("observacion_original", "derivado", "literatura", "prediccion")

# Resultados que puede devolver el laboratorio. Cada uno tiene una accion
# distinta en el aprendizaje (ver `rosa/bucle/corrida.py`).
RESULTADOS_LABORATORIO = ("apoyo_reproducido", "negativo_interpretable", "inconcluso", "fallo_tecnico", "toxicidad_inviabilidad", "correccion_contexto")

# Bloqueos no compensables: si uno se cumple, la hipotesis no entra al
# ranking de candidatos aunque puntue alto en todo lo demas.
BLOQUEOS = ("trazabilidad_insuficiente", "datos_no_autorizados", "analisis_invalido", "sin_experimento_interpretable", "descartada_por_killer", "fuente_retractada")


def puede_reformular(version: int) -> bool:
    """`version` es la version actual de la hipotesis (1 al nacer). Se puede
    reformular mientras la siguiente version no supere el limite."""
    return version - 1 < MAX_REFORMULACIONES


def resumen() -> dict[str, object]:
    """Para la pantalla de Ajustes: las politicas tal como estan en codigo."""
    return {
        "maxHipotesisVivas": MAX_HIPOTESIS_VIVAS_POR_MISION,
        "maxEvaluacionesCostosas": MAX_EVALUACIONES_COSTOSAS,
        "maxCandidatos": MAX_CANDIDATOS_LABORATORIO,
        "maxReformulaciones": MAX_REFORMULACIONES,
        "reproduccionesRequeridas": REPRODUCCIONES_REQUERIDAS,
        "fraccionDescartesAuditados": FRACCION_DESCARTES_AUDITADOS,
        "segundosMaxEjecucion": SEGUNDOS_MAX_EJECUCION,
        "memoriaMaxEjecucionMb": MEMORIA_MAX_EJECUCION_MB,
        "presupuestoUsd": PRESUPUESTO_USD_POR_DEFECTO,
        "presupuestoHoras": PRESUPUESTO_HORAS_POR_DEFECTO,
    }
