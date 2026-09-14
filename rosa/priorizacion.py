"""Priorizacion con bloqueos no compensables y diversidad (ROSA2018, etapa 8).

Dos reglas, las dos deterministas y las dos repetidas en
`frontend/src/lib/priorizacion.ts` para que la pantalla y el servidor digan
lo mismo:

1. Bloqueos. Antes de mirar el Elo, cada hipotesis pasa por una lista de
   condiciones que, si se cumple una sola, la sacan de los candidatos. No se
   compensan con puntos: una hipotesis con evidencia no trazable no va al
   laboratorio por mucho que gane debates.
2. Candidatos. Entre las que no tienen bloqueos y el Killer dejo avanzar, se
   eligen hasta N por Elo, con diversidad: no dos del mismo cluster mientras
   haya otros clusters disponibles (la idea del grafo de proximidad de
   Co-Scientist y de la seleccion por maxima relevancia marginal). Cero
   candidatos es un resultado valido.
"""

from __future__ import annotations

from typing import Any

from rosa import politicas

BLOQUEANTES = ("no_sostenida", "cita_no_resuelve", "sin_cita", "ausencia_refutada")


def _bloqueo(nombre: str) -> str:
    """Solo se emiten bloqueos de la lista canonica de politicas."""
    assert nombre in politicas.BLOQUEOS, nombre
    return nombre


def bloqueos_de(e: dict[str, Any], h: dict[str, Any]) -> list[str]:
    b: list[str] = []
    afs = h.get("afirmaciones", [])
    sostenidas = [a for a in afs if a["veredicto"] in ("sostenida", "parcial")]
    if not sostenidas or any(a["veredicto"] in BLOQUEANTES for a in afs):
        b.append(_bloqueo("trazabilidad_insuficiente"))
    inv = next((i for i in e["investigaciones"] if i["id"] == h["investigacionId"]), None)
    datasets = {d["id"]: d for d in (inv or {}).get("datasets", [])}
    planes = {p["id"]: p for p in e.get("planesAnalisis", [])}
    ejecuciones = [x for x in e.get("ejecuciones", []) if x.get("hipotesisId") == h["id"]]
    for x in ejecuciones:
        plan = planes.get(x["planId"])
        ds = datasets.get(plan["datasetId"]) if plan else None
        if ds is None or ds["estado"] != "aprobado" or (ds.get("procedencia") or {}).get("usoIAAutorizado") != "si":
            b.append(_bloqueo("datos_no_autorizados"))
            break
    auditadas = [x for x in ejecuciones if x.get("auditoria")]
    if auditadas and auditadas[-1]["auditoria"]["veredicto"] == "no_valido":
        b.append(_bloqueo("analisis_invalido"))
    x = h.get("experimento")
    # Interpretable: criterios de confirmacion y refutacion separados, o un
    # prerregistro congelado con el esquema anterior (criterios dentro del ensayo).
    if not x or not ((x.get("confirma") or "").strip() and (x.get("refuta") or "").strip()) and not (x.get("prerregistradoEn") and (x.get("ensayo") or "").strip()):
        b.append(_bloqueo("sin_experimento_interpretable"))
    if h["estado"] == "descartada" or h.get("decisionKiller") == "descartar_en_contexto":
        b.append(_bloqueo("descartada_por_killer"))
    if any(f.get("retraccion") == "retractado" for f in h.get("procedencia", {}).get("fuentes", [])):
        b.append(_bloqueo("fuente_retractada"))
    return b


def candidatos(e: dict[str, Any], investigacion_id: str, maximo: int | None = None) -> list[dict[str, Any]]:
    """Las hipotesis que hoy irian al laboratorio, en orden. Solo las que el
    Killer dejo avanzar, sin bloqueos, con diversidad por cluster."""
    maximo = maximo if maximo is not None else politicas.MAX_CANDIDATOS_LABORATORIO
    vivas = [h for h in e["hipotesis"] if h["investigacionId"] == investigacion_id and h["estado"] not in ("descartada",) and h.get("decisionKiller") == "avanzar" and not bloqueos_de(e, h)]
    # Orden por Bradley-Terry cuando hay partidos suficientes; si no, por Elo.
    vivas.sort(key=lambda h: (-((h.get("bt") or {}).get("fuerza") or h["elo"]), h["creadaEn"]))
    elegidas: list[dict[str, Any]] = []
    clusters_usados: set[str] = set()
    pendientes = list(vivas)
    while pendientes and len(elegidas) < maximo:
        siguiente = next((h for h in pendientes if h["cluster"].lower() not in clusters_usados), None)
        if siguiente is None:
            siguiente = pendientes[0]
        elegidas.append(siguiente)
        clusters_usados.add(siguiente["cluster"].lower())
        pendientes.remove(siguiente)
    return elegidas


def marcar_candidatas(e: dict[str, Any], investigacion_id: str) -> list[str]:
    """Recalcula bloqueos y candidatas de toda la investigacion y devuelve
    los ids de las candidatas. El bucle lo llama al cerrar cada iteracion."""
    for h in e["hipotesis"]:
        if h["investigacionId"] == investigacion_id:
            h["bloqueos"] = bloqueos_de(e, h)
            h["candidata"] = False
    ids = [h["id"] for h in candidatos(e, investigacion_id)]
    for h in e["hipotesis"]:
        if h["id"] in ids:
            h["candidata"] = True
    return ids


def cohortes_de(h: dict[str, Any]) -> list[str]:
    """Cohortes distintas entre las fuentes de la hipotesis. Dos articulos de
    la misma cohorte son una sola evidencia."""
    vistas: list[str] = []
    for f in h.get("procedencia", {}).get("fuentes", []):
        c = (f.get("cohorte") or "").strip().lower()
        if c and c not in vistas:
            vistas.append(c)
    return vistas
