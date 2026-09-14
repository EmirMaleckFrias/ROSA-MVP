"""Coste por decision, no por llamada.

Rosa registra el coste de cada llamada al modelo (tabla `llamadas`): es el
dato de ingenieria. Lo que decide presupuestos es el agregado: cuanto cuesta
una hipotesis que llega al dossier, cuanto una decision que una persona
tomo, y como evoluciona esa cifra por iteracion. El tiempo de revision
humana entra en el coste (segundos de revision por decision, valorados con
una tarifa declarada en politicas): sin eso la comparacion con investigar
sin Rosa no es honesta. Todo es aritmetica sobre el estado y el registro de
llamadas; ningun modelo interviene.
"""

from __future__ import annotations

from typing import Any

from rosa import config, politicas


def _usd_llamadas(llamadas: list[dict[str, Any]]) -> float:
    return round(sum(config.coste_usd(str(l.get("modelo") or ""), int(l.get("tokensEntrada") or 0), int(l.get("tokensSalida") or 0)) for l in llamadas), 4)


def costes_de_investigacion(e: dict[str, Any], investigacion_id: str, llamadas_por_corrida: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Agregado por investigacion (campana): dolares del modelo, horas de
    revision humana y su valor, y el coste por dossier, por candidata y por
    decision humana. `llamadas_por_corrida` viene de Almacen.llamadas_de."""
    corridas = [c for c in e.get("corridas", []) if c.get("investigacionId") == investigacion_id]
    hipotesis = [h for h in e.get("hipotesis", []) if h.get("investigacionId") == investigacion_id]
    ids_h = {h["id"] for h in hipotesis}
    decisiones = [d for d in e.get("decisiones", []) if d.get("hipotesisId") in ids_h]
    de_persona = [d for d in decisiones if d.get("etapa") == "persona"]
    dossiers = [a for a in e.get("artefactos", []) if a.get("investigacionId") == investigacion_id and a.get("tipo") == "dossier"]
    def _hip_de(a: dict[str, Any]) -> str | None:
        # La procedencia va en cada version del artefacto (cinco pestanas).
        for fuente in (a.get("procedencia"), ((a.get("versiones") or [{}])[-1]).get("procedencia")):
            hip = ((fuente or {}).get("mensajes") or {}).get("hipotesis")
            if hip:
                return str(hip)
        return None

    con_dossier = {_hip_de(a) for a in dossiers} - {None}
    candidatas = [h for h in hipotesis if h.get("candidata")]
    usd_modelo = round(sum(float((c.get("gasto") or {}).get("usd") or 0.0) for c in corridas), 4)
    llamadas = sum(int((c.get("gasto") or {}).get("llamadas") or 0) for c in corridas)
    segundos_revision = sum(float(d.get("segundosRevision") or 0.0) for d in de_persona)
    horas_revision = round(segundos_revision / 3600, 3)
    usd_revision = round(horas_revision * politicas.TARIFA_HORA_REVISION_USD, 2)
    usd_total = round(usd_modelo + usd_revision, 2)
    por_iteracion: list[dict[str, Any]] = []
    for c in corridas:
        agrupado: dict[int, list[dict[str, Any]]] = {}
        for l in llamadas_por_corrida.get(c["id"], []):
            agrupado.setdefault(int(l.get("iteracion") or 0), []).append(l)
        for n in sorted(agrupado):
            ls = agrupado[n]
            por_iteracion.append({"corridaId": c["id"], "corrida": c.get("numero"), "iteracion": n, "llamadas": len(ls), "usd": _usd_llamadas(ls), "ms": sum(int(l.get("ms") or 0) for l in ls)})
    # Tendencia: coste medio por iteracion en las tres ultimas frente a las tres primeras.
    tendencia = None
    if len(por_iteracion) >= 4:
        primeras = [x["usd"] for x in por_iteracion[:3]]
        ultimas = [x["usd"] for x in por_iteracion[-3:]]
        tendencia = round(sum(ultimas) / len(ultimas) - sum(primeras) / len(primeras), 4)
    return {
        "investigacionId": investigacion_id,
        "corridas": len(corridas),
        "llamadas": llamadas,
        "usdModelo": usd_modelo,
        "horasRevision": horas_revision,
        "tarifaHoraRevisionUsd": politicas.TARIFA_HORA_REVISION_USD,
        "usdRevision": usd_revision,
        "usdTotal": usd_total,
        "hipotesis": len(hipotesis),
        "hipotesisConDossier": len(con_dossier),
        "candidatas": len(candidatas),
        "decisionesHumanas": len(de_persona),
        "decisionesHumanasUtiles": sum(1 for d in de_persona if d.get("decision") in ("aprobar", "aprobada", "avanzar", "priorizar", "laboratorio")),
        "usdPorDossier": round(usd_total / len(con_dossier), 2) if con_dossier else None,
        "usdPorCandidata": round(usd_total / len(candidatas), 2) if candidatas else None,
        "usdPorDecisionHumana": round(usd_total / len(de_persona), 2) if de_persona else None,
        "segundosMediosPorDecision": round(segundos_revision / len(de_persona), 1) if de_persona else None,
        "porIteracion": por_iteracion,
        "tendenciaUsdPorIteracion": tendencia,
        "nota": "El coste total suma los dolares del modelo (tokens por la tabla de precios de Rosa) y las horas de revision humana valoradas a la tarifa declarada en politicas. Las cifras por dossier, candidata y decision dividen ese total.",
    }
