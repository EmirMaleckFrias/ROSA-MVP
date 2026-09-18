"""Priorización con bloqueos no compensables y diversidad (ROSA2018, etapa 8).

Dos reglas, las dos deterministas y las dos repetidas en
`frontend/src/lib/priorizacion.ts` para que la pantalla y el servidor digan
lo mismo:

1. Bloqueos. Antes de mirar el Elo, cada hipótesis pasa por una lista de
   condiciones que, si se cumple una sola, la sacan de los candidatos. No se
   compensan con puntos: una hipótesis con evidencia no trazable no va al
   laboratorio por mucho que gane debates.
2. Candidatos. Entre las que no tienen bloqueos y el Killer dejó avanzar, se
   eligen hasta N por Elo, con diversidad: no dos del mismo cluster mientras
   haya otros clusters disponibles (la idea del grafo de proximidad de
   Co-Scientist y de la selección por máxima relevancia marginal). Cero
   candidatos es un resultado válido.
"""

from __future__ import annotations

from typing import Any

from rosa import politicas

BLOQUEANTES = ("no_sostenida", "cita_no_resuelve", "sin_cita", "ausencia_refutada")


def _bloqueo(nombre: str) -> str:
    """Solo se emiten bloqueos de la lista canónica de políticas."""
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
    # Interpretable: criterios de confirmación y refutación separados, o un
    # prerregistro congelado con el esquema anterior (criterios dentro del ensayo).
    if not x or not ((x.get("confirma") or "").strip() and (x.get("refuta") or "").strip()) and not (x.get("prerregistradoEn") and (x.get("ensayo") or "").strip()):
        b.append(_bloqueo("sin_experimento_interpretable"))
    if h["estado"] == "descartada" or h.get("decisionKiller") == "descartar_en_contexto":
        b.append(_bloqueo("descartada_por_killer"))
    # Un registro roto con `procedencia` como texto o None no debe tumbar la carga del estado.
    procedencia = h.get("procedencia")
    fuentes = procedencia.get("fuentes") if isinstance(procedencia, dict) else None
    if any(isinstance(f, dict) and f.get("retraccion") == "retractado" for f in (fuentes if isinstance(fuentes, list) else [])):
        b.append(_bloqueo("fuente_retractada"))
    # Puerta de publicación (el "evidence worker" de rekursiv): un hallazgo grave y
    # abierto del revisor de registro, en el dossier de la hipótesis o en la última
    # iteración cerrada de la investigación, retiene la candidatura y la exportación.
    if revision_registro_abierta(e, h):
        b.append(_bloqueo("revision_registro_abierta"))
    # Propagación de dependencias (rosa/dependencias.py): algo de lo que la hipótesis
    # depende cambió (una fuente se retractó, un hecho fue sustituido o contradicho) y
    # Rosa o una persona todavía no la revisó. Se levanta al volver a concluirla.
    if h.get("pendienteRevision"):
        b.append(_bloqueo("dependencia_pendiente"))
    return b


def revision_registro_abierta(e: dict[str, Any], h: dict[str, Any]) -> bool:
    """Verdadero si el dossier de la hipótesis o la última iteración cerrada de
    su investigación tienen hallazgos del revisor de registro abiertos y de
    gravedad alta (un DOI que no está en el registro, una ejecución afirmada y
    no completada, un recuento que no cuadra). Misma regla en
    frontend/src/lib/priorizacion.ts."""

    def grave_abierto(hallazgos: list[dict[str, Any]] | None) -> bool:
        return any(x.get("estado") == "abierto" and x.get("gravedad") == "alta" for x in (hallazgos or []))

    if h.get("dossierArtefactoId"):
        art = next((a for a in e.get("artefactos", []) if a["id"] == h["dossierArtefactoId"]), None)
        ultima = (art.get("versiones") or [{}])[-1] if art else {}
        if art and grave_abierto(((ultima.get("procedencia") or {}).get("revision") or {}).get("hallazgos")):
            return True
    corridas = {c["id"] for c in e.get("corridas", []) if c["investigacionId"] == h["investigacionId"]}
    cerradas = [it for it in e.get("iteraciones", []) if it.get("corridaId") in corridas and it.get("terminadaEn")]
    if not cerradas:
        return False
    ultima = max(cerradas, key=lambda it: it["terminadaEn"])
    return grave_abierto((ultima.get("revisionRegistro") or {}).get("hallazgos"))


def candidatos(e: dict[str, Any], investigacion_id: str, maximo: int | None = None) -> list[dict[str, Any]]:
    """Las hipótesis que hoy irían al laboratorio, en orden. Solo las que el
    Killer dejó avanzar, sin bloqueos, con diversidad por cluster."""
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
    """Recalcula bloqueos y candidatas de toda la investigación y devuelve
    los ids de las candidatas. El bucle lo llama al cerrar cada iteración."""
    for h in e["hipotesis"]:
        if h["investigacionId"] == investigacion_id:
            h["bloqueos"] = bloqueos_de(e, h)
            h["candidata"] = False
            anotar_cohortes(h)
    ids = [h["id"] for h in candidatos(e, investigacion_id)]
    for h in e["hipotesis"]:
        if h["id"] in ids:
            h["candidata"] = True
    return ids


def cohortes_de(h: dict[str, Any]) -> list[str]:
    """Cohortes distintas entre las fuentes de la hipótesis que aportan apoyo:
    la misma cuenta que usa el techo GRADE (`rosa/certeza.py`), que a su vez
    agrupa por el catálogo canónico de rosa/metodos.py (`cohortes_distintas`:
    alias, NCT y ensayos resuelven a la misma). Una sola regla para el Killer,
    el juez, el dossier y la pantalla (17 de septiembre de 2026, hallazgo M-04:
    antes había tres cuentas y la franja del ranking decía 7 donde el techo
    contaba 6). Devuelve la etiqueta canónica (o el nombre dado si no está en
    el catálogo), una por grupo; una fuente que solo contradice o socava, o
    cuyos apoyos son todos de introducción, no aporta cohorte."""
    from rosa import certeza as CERTEZA

    return CERTEZA.cohortes_distintas(h)


def anotar_cohortes(h: dict[str, Any]) -> list[str]:
    """Escribe la lista canónica que da `cohortes_de` en
    `h["cohortesDistintas"]` (siempre, es lo que la interfaz lee primero) y en
    `h["conclusion"]["cohortesDistintas"]` si la hipótesis ya tiene conclusión,
    para que el frontend la lea en vez de recalcularla con otra regla.
    Devuelve la lista."""
    cohortes = cohortes_de(h)
    h["cohortesDistintas"] = list(cohortes)
    if isinstance(h.get("conclusion"), dict):
        h["conclusion"]["cohortesDistintas"] = list(cohortes)
    return cohortes
