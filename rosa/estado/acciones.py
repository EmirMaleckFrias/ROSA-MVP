"""Las acciones de la interfaz, portadas de `frontend/src/datos/acciones.ts`.

Cada funcion recibe el estado (un diccionario con la forma de `EstadoRosa`) y
lo cambia en sitio. Devuelve `True` si cambio algo (o el id creado, cuando la
accion crea un objeto) y `False` si la regla del dominio no lo permitio. El
almacen (almacen.py) solo persiste y avisa cuando la accion devolvio algo
distinto de `False`.

Las reglas son las mismas que en el frontend, y en el mismo orden:
- La aprobacion va antes del efecto: aceptar una hipotesis la mete al modelo
  de mundo como abierta, nunca como sabida.
- Descartar y "no puedo juzgar" exigen motivo.
- Un permiso con alcance mayor que "una vez" queda listado y es revocable.
- Los comentarios se acumulan pendientes y salen juntos al enviar.
- El plan no se ejecuta hasta que se aprueba.
- El presupuesto pausa la corrida; una pregunta pendiente tiene prioridad.
- Toda accion relevante deja un evento.

Si el frontend genera el id (para navegar al instante), lo manda en `id` y
aqui se respeta; si no, se genera uno.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from rosa import config
from rosa.estado import plantilla as P

Estado = dict[str, Any]


def _buscar(lista: list[dict], id_: str) -> dict | None:
    for x in lista:
        if x.get("id") == id_:
            return x
    return None


def con_evento(e: Estado, investigacion_id: str, tipo: str, texto: str, ruta: str | None, t: int) -> None:
    e["eventos"].append(P.nuevo_evento(investigacion_id, tipo, texto, ruta, t))


def iteracion_actual_de(e: Estado, corrida: dict) -> dict | None:
    propias = [i for i in e["iteraciones"] if i["corridaId"] == corrida["id"]]
    if not propias:
        return None
    return max(propias, key=lambda i: i["numero"])


def corrida_de(e: Estado, corrida_id: str) -> dict | None:
    return _buscar(e["corridas"], corrida_id)


def ultima_corrida_de(e: Estado, investigacion_id: str) -> dict | None:
    propias = [c for c in e["corridas"] if c["investigacionId"] == investigacion_id]
    return max(propias, key=lambda c: c["numero"]) if propias else None


# ---------------------------------------------------------------------------
# Visita
# ---------------------------------------------------------------------------


def marcar_visita(e: Estado, ahora: int) -> bool:
    e["ultimaVisita"] = ahora
    return True


# ---------------------------------------------------------------------------
# Corrida
# ---------------------------------------------------------------------------


def pausar_corrida(e: Estado, corrida_id: str) -> bool:
    c = corrida_de(e, corrida_id)
    if not c or c["estado"] != "en_marcha":
        return False
    c["estado"] = "pausada"
    return True


def reanudar_corrida(e: Estado, corrida_id: str) -> bool:
    c = corrida_de(e, corrida_id)
    if not c or c["estado"] != "pausada":
        return False
    c["estado"] = "en_marcha"
    return True


def detener_corrida(e: Estado, corrida_id: str, motivo: str, ahora: int, vigilar_literatura_dias: int | None = None) -> bool:
    texto = motivo.strip() or "Detenida por la investigadora."
    c = corrida_de(e, corrida_id)
    if not c or c["estado"] in ("detenida", "terminada"):
        return False
    c["estado"] = "detenida"
    c["terminadaEn"] = ahora
    c["motivoCierre"] = texto
    if vigilar_literatura_dias and vigilar_literatura_dias > 0:
        inv = _buscar(e["investigaciones"], c["investigacionId"])
        if inv:
            inv["vigilarLiteraturaHasta"] = ahora + vigilar_literatura_dias * 86_400_000
    con_evento(e, c["investigacionId"], "corrida_estado", f"Corrida {c['numero']} detenida: {texto}", None, ahora)
    return True


def ampliar_presupuesto(e: Estado, corrida_id: str, nuevo_limite: float, ahora: int) -> bool:
    c = corrida_de(e, corrida_id)
    if not c or not isinstance(nuevo_limite, (int, float)) or nuevo_limite <= c["gasto"]["llamadas"]:
        return False
    limite = round(nuevo_limite)
    c["presupuesto"]["limiteLlamadas"] = limite
    c["presupuesto"]["avisadas"] = [a for a in c["presupuesto"]["avisadas"] if c["gasto"]["llamadas"] / limite >= a]
    if c["estado"] == "pausada_por_presupuesto":
        c["estado"] = "en_marcha"
    con_evento(e, c["investigacionId"], "presupuesto", f"Presupuesto ampliado a {limite} llamadas", None, ahora)
    return True


def dirigir_corrida(e: Estado, corrida_id: str, texto: str) -> bool:
    limpio = texto.strip()
    if not limpio:
        return False
    c = corrida_de(e, corrida_id)
    if not c:
        return False
    it = iteracion_actual_de(e, c)
    if not it:
        return False
    paso = P.nuevo_paso("Indicacion de la investigadora", limpio, None, humano=True)
    idx = next((i for i, p in enumerate(it["plan"]) if p["estado"] == "en_curso"), -1)
    it["plan"].insert(len(it["plan"]) if idx == -1 else idx + 1, paso)
    return True


def editar_plan(e: Estado, iteracion_id: str, plan: list[dict]) -> bool:
    it = _buscar(e["iteraciones"], iteracion_id)
    if not it or it["planAprobado"]:
        return False
    limpio = [p for p in plan if str(p.get("titulo", "")).strip()]
    if not limpio:
        return False
    it["plan"] = limpio
    return True


def aprobar_plan(e: Estado, iteracion_id: str, ahora: int) -> bool:
    it = _buscar(e["iteraciones"], iteracion_id)
    if not it or it["planAprobado"]:
        return False
    it["planAprobado"] = True
    it["empezadaEn"] = ahora
    c = corrida_de(e, it["corridaId"])
    if c and c["estado"] == "esperando_plan":
        c["estado"] = "en_marcha"
    if c:
        con_evento(e, c["investigacionId"], "corrida_estado", f"Plan de la iteracion {it['numero']} aprobado", None, ahora)
    return True


def fijar_autoaprobacion_plan(e: Estado, corrida_id: str, segundos: int | None) -> bool:
    c = corrida_de(e, corrida_id)
    if not c:
        return False
    c["autoAprobarPlanSegundos"] = segundos
    return True


def detener_pista(e: Estado, pista_id: str, indicacion: str) -> bool:
    nota = indicacion.strip()
    for it in e["iteraciones"]:
        for p in it["pistas"]:
            if p["id"] == pista_id and p["estado"] == "en_curso":
                p["estado"] = "detenida"
                p["resumen"] = "Detenida por la investigadora" if not nota else f"Detenida: {nota}"
                p["transcripcion"].append({"t": len(p["transcripcion"]) * 2500, "tipo": "nota", "texto": "Detenida por la investigadora." if not nota else f"Detenida por la investigadora: {nota}"})
                return True
    return False


def detener_proceso(e: Estado, corrida_id: str, proceso_id: str, indicacion: str) -> bool:
    c = corrida_de(e, corrida_id)
    if not c:
        return False
    for p in c["procesos"]:
        if p["id"] == proceso_id:
            p["estado"] = "detenido"
            p["cpu"] = 0
            p["memoriaMb"] = 0
    if indicacion.strip():
        dirigir_corrida(e, corrida_id, f"Proceso detenido por la investigadora: {indicacion.strip()}")
    return True


def volver_a_iteracion(e: Estado, iteracion_id: str, que: str, ahora: int) -> bool:
    origen = _buscar(e["iteraciones"], iteracion_id)
    if not origen or origen["terminadaEn"] is None:
        return False
    c = corrida_de(e, origen["corridaId"])
    if not c:
        return False
    actual = iteracion_actual_de(e, c)
    numero = (actual["numero"] if actual else origen["numero"]) + 1
    base = (actual["plan"] if (que == "mundo" and actual) else origen["plan"])
    plan = [{**p, "id": P.nuevo_id("paso"), "estado": "pendiente", "motivoFallo": None} for p in base]
    nueva = P.nueva_iteracion(c["id"], numero, ahora, plan, origen["presupuesto"]["limite"])
    if actual and actual["terminadaEn"] is None:
        actual["terminadaEn"] = ahora
        actual["resumen"] = actual["resumen"] or f"Cerrada al volver a la iteracion {origen['numero']}"
    e["iteraciones"].append(nueva)
    if que in ("mundo", "ambos"):
        limite = origen["terminadaEn"]
        e["hechos"] = [h for h in e["hechos"] if not (h["investigacionId"] == c["investigacionId"] and h["actualizadoEn"] > limite and all(m["quien"] == config.QUIEN_ROSA for m in h["historial"]))]
    c["iteracionActual"] = numero
    if c["estado"] in ("en_marcha", "esperando_plan"):
        c["estado"] = "esperando_plan"
    con_evento(e, c["investigacionId"], "corrida_estado", f"Se volvio a la iteracion {origen['numero']} ({que}); la {numero} espera tu aprobacion del plan", None, ahora)
    return True


# ---------------------------------------------------------------------------
# Permisos, incidencias y autonomia
# ---------------------------------------------------------------------------


def resolver_solicitud(e: Estado, solicitud_id: str, decision: str, alcance: str | None, ahora: int, argumentos: dict[str, str] | None = None) -> bool:
    s = _buscar(e["solicitudes"], solicitud_id)
    if not s or s["estado"] != "pendiente":
        return False
    if decision == "conceder" and (alcance is None or alcance not in s["alcances"]):
        return False
    c = corrida_de(e, s["corridaId"])
    s["estado"] = "concedida" if decision == "conceder" else "denegada"
    s["alcanceConcedido"] = alcance if decision == "conceder" else None
    s["resueltaEn"] = ahora
    if argumentos:
        for a in s["argumentos"]:
            if a["editable"] and a["nombre"] in argumentos:
                a["valor"] = argumentos[a["nombre"]].strip() or a["valor"]
    if decision == "conceder" and alcance and alcance != "una_vez":
        e["permisos"].append(
            {
                "id": P.nuevo_id("per"),
                "tipo": s["tipo"],
                "recurso": s["recurso"],
                "alcance": alcance,
                "concedidoEn": ahora,
                "investigacionId": None if alcance == "siempre" else (c["investigacionId"] if c else None),
            }
        )
    if s["tipo"] == "aceptar_hipotesis" and s.get("hipotesisId") and decision == "conceder":
        revisar_hipotesis(e, s["hipotesisId"], "aceptar", "Aceptada desde la tarjeta de permiso", "Investigadora", ahora, False)
    quedan = any(x["corridaId"] == s["corridaId"] and x["estado"] == "pendiente" for x in e["solicitudes"])
    if c and c["estado"] == "esperando_aprobacion" and not quedan:
        c["estado"] = "en_marcha"
    if c:
        con_evento(e, c["investigacionId"], "permiso_resuelto", f"{'Permitido' if decision == 'conceder' else 'Denegado'}: {s['recurso']}", None, ahora)
    return True


def resolver_solicitudes(e: Estado, ids: list[str], decision: str, alcance: str | None, ahora: int) -> bool:
    algo = False
    for id_ in ids:
        s = _buscar(e["solicitudes"], id_)
        if not s:
            continue
        if decision == "conceder" and alcance is not None and alcance not in s["alcances"]:
            continue
        algo = resolver_solicitud(e, id_, decision, alcance, ahora) or algo
    return algo


def revocar_permiso(e: Estado, permiso_id: str) -> bool:
    antes = len(e["permisos"])
    e["permisos"] = [p for p in e["permisos"] if p["id"] != permiso_id]
    return len(e["permisos"]) != antes


def resolver_incidencia(e: Estado, incidencia_id: str, resolucion: str, ahora: int) -> bool:
    inc = _buscar(e["incidencias"], incidencia_id)
    if not inc or inc["estado"] != "pendiente":
        return False
    texto = resolucion.strip() or inc.get("alternativa") or "Resuelta por la investigadora"
    inc["estado"] = "resuelta"
    inc["resueltaEn"] = ahora
    inc["resolucion"] = texto
    c = corrida_de(e, inc["corridaId"])
    if c:
        con_evento(e, c["investigacionId"], "incidencia", f"Incidencia resuelta: {inc['titulo']} ({texto})", None, ahora)
    return True


def fijar_autonomia(e: Estado, clase: str, nivel: str) -> bool:
    if clase not in P.CLASES_ACCION or nivel not in ("sugerir", "preguntar", "actuar"):
        return False
    e["autonomia"][clase] = nivel
    return True


# ---------------------------------------------------------------------------
# Hipotesis
# ---------------------------------------------------------------------------

ESTADO_TRAS_ACCION = {"aceptar": "aceptada", "descartar": "descartada", "refinar": "refinar", "reabrir": "en_revision", "no_puedo_juzgar": "aclarando"}
ACCION_REVISION = {"aceptar": "aceptada", "descartar": "descartada", "refinar": "refinar", "reabrir": "reabierta", "no_puedo_juzgar": "no_puedo_juzgar"}


def revisar_hipotesis(e: Estado, hipotesis_id: str, accion: str, nota: str, quien: str, ahora: int, a_ciegas: bool = False, revision_humana: dict | None = None) -> bool:
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h or accion not in ESTADO_TRAS_ACCION:
        return False
    nota_limpia = (nota or "").strip()
    if accion in ("descartar", "no_puedo_juzgar") and not nota_limpia:
        return False
    h["estado"] = ESTADO_TRAS_ACCION[accion]
    h["revisiones"].append({"fecha": ahora, "quien": quien, "accion": ACCION_REVISION[accion], "nota": nota_limpia, "aCiegas": bool(a_ciegas)})
    if nota_limpia:
        h["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "investigadora", "texto": nota_limpia, "creadoEn": ahora})
    if revision_humana and any(str(revision_humana.get(k, "")).strip() for k in ("supuestosCuestionados", "literaturaQueFalta", "problemaExperimental")):
        h["revisionesHumanas"].append({**revision_humana, "fecha": ahora, "quien": quien})
    e["hechos"] = [x for x in e["hechos"] if not (x["tipo"] == "hipotesis" and x["id"] == f"he-{hipotesis_id}")]
    if accion in ("aceptar", "descartar"):
        aceptar = accion == "aceptar"
        e["hechos"].append(
            {
                "id": f"he-{hipotesis_id}",
                "investigacionId": h["investigacionId"],
                "tipo": "hipotesis",
                "tema": "Revision humana",
                "enunciado": f"Hipotesis aceptada para perseguir: {h['titulo']}" if aceptar else h["titulo"],
                "estado": "abierto" if aceptar else "descartado",
                "origen": "inferencia",
                "procedencia": [{"fuenteId": f["id"], "referencia": f["referencia"], "pagina": f["pagina"]} for f in h["procedencia"]["fuentes"]],
                "motivoDescarte": None if aceptar else f"{nota_limpia} ({quien})",
                "actualizadoEn": ahora,
                "prioridad": 1 if aceptar else 9,
                "citas": [],
                "historial": [{"fecha": ahora, "de": None, "a": "abierto" if aceptar else "descartado", "quien": quien, "motivo": nota_limpia or ("Aceptada" if aceptar else "Descartada")}],
            }
        )
    textos = {
        "aceptar": f"Aceptada: {h['titulo']}",
        "descartar": f"Descartada: {h['titulo']}",
        "refinar": f"Pedida refinacion: {h['titulo']}",
        "reabrir": f"Reabierta: {h['titulo']}",
        "no_puedo_juzgar": f'Marcada como "no puedo juzgar": {h["titulo"]}',
    }
    con_evento(e, h["investigacionId"], "hipotesis_decidida", textos[accion], f"#/investigaciones/{h['investigacionId']}/hipotesis/{h['id']}", ahora)
    return True


def aclarar_hipotesis(e: Estado, hipotesis_id: str, aclaracion: str, ahora: int) -> bool:
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h or h["estado"] != "aclarando":
        return False
    h["estado"] = "en_revision"
    h["revisiones"].append({"fecha": ahora, "quien": config.QUIEN_ROSA, "accion": "aclarada", "nota": aclaracion, "aCiegas": False})
    h["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "rosa", "texto": aclaracion, "creadoEn": ahora})
    return True


def votar_relevancia(e: Estado, hipotesis_id: str, voto: str) -> bool:
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h or voto not in ("alta", "media", "baja"):
        return False
    h["relevancia"]["votoHumano"] = voto
    return True


def solicitar_revision(e: Estado, hipotesis_id: str, ahora: int) -> bool:
    """Deja constancia de la peticion; el bucle hace la revision real y
    sustituye este resumen provisional."""
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h:
        return False
    h["ultimaRevisionAutomatica"] = ahora
    h.setdefault("_revisionPedida", True)
    h["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "revisor", "texto": "Revision pedida por la investigadora. Rosa la hara en cuanto tenga el modelo libre.", "creadoEn": ahora})
    con_evento(e, h["investigacionId"], "revision_automatica", f"Revision pedida sobre: {h['titulo']}", f"#/investigaciones/{h['investigacionId']}/hipotesis/{h['id']}", ahora)
    return True


def replicar_hipotesis(e: Estado, hipotesis_id: str, total: int, ahora: int) -> bool:
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h or (h["replicacion"] and h["replicacion"]["estado"] == "en_curso") or total < 2:
        return False
    h["replicacion"] = {"total": total, "hechas": 0, "sostienen": 0, "contradicen": 0, "estado": "en_curso", "empezadaEn": ahora}
    h["revisiones"].append({"fecha": ahora, "quien": "Investigadora", "accion": "replicada", "nota": f"{total} trayectorias independientes", "aCiegas": False})
    h["coste"]["analisis"] = h["coste"]["analisis"] + total * 1.2
    con_evento(e, h["investigacionId"], "revision_automatica", f"Replicacion x{total} lanzada sobre: {h['titulo']}", f"#/investigaciones/{h['investigacionId']}/hipotesis/{h['id']}", ahora)
    return True


def proponer_hipotesis(e: Estado, investigacion_id: str, datos: dict, quien: str, ahora: int, id_: str | None = None) -> str | bool:
    def t(k: str) -> str:
        return str(datos.get(k, "")).strip()

    if not t("titulo") or not t("enunciado") or (not t("biomarcador") and not t("cohorte")):
        return False
    corrida = ultima_corrida_de(e, investigacion_id)
    iteracion = corrida["iteracionActual"] if corrida else 0
    h = P.nueva_hipotesis(
        investigacion_id,
        iteracion,
        ahora,
        titulo=t("titulo"),
        enunciado=t("enunciado"),
        mecanismo=t("mecanismo"),
        comprobacion={"biomarcador": t("biomarcador"), "cohorte": t("cohorte"), "diseno": t("diseno")},
        origen="humana",
        cluster=t("cluster") or "Sin cluster",
        relevancia={"justificacion": "Propuesta por la investigadora; Rosa la justificara al revisarla.", "votoHumano": "alta"},
        revisiones=[{"fecha": ahora, "quien": quien, "accion": "propuesta", "nota": "Propuesta por una persona", "aCiegas": False}],
    )
    if id_:
        h["id"] = id_
    h["procedencia"] = P.procedencia_vacia(f"Hipotesis propuesta por {quien}. Rosa la revisara y la metera al torneo en la siguiente iteracion.", ahora)
    h["procedencia"]["mensajes"][0]["de"] = "investigadora"
    h["procedencia"]["registro"] = [f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} hipotesis humana anadida por {quien}"]
    e["hipotesis"].append(h)
    con_evento(e, investigacion_id, "hipotesis_nueva", f"Hipotesis propuesta por {quien}: {h['titulo']}", f"#/investigaciones/{investigacion_id}/hipotesis/{h['id']}", ahora)
    return h["id"]


def asignar_experimento(e: Estado, hipotesis_id: str, laboratorio: str, ahora: int | None = None) -> bool:
    """Asignar el experimento a un laboratorio lo prerregistra: hipotesis,
    protocolo, criterio de exito y de refutacion quedan congelados con fecha
    en un artefacto inmutable, antes de que exista ningun dato. Es lo que pide
    el prerregistro (OSF, AsPredicted) y la revision de Zitnik 2026 para
    poder reportar despues que fraccion de lo probado se sostuvo."""
    h = _buscar(e["hipotesis"], hipotesis_id)
    lab = laboratorio.strip()
    if not h or not lab or not h["experimento"]:
        return False
    ahora = ahora if ahora is not None else P.ahora_ms()
    x = h["experimento"]
    x["laboratorio"] = lab
    x["estado"] = "asignado"
    if not x.get("prerregistradoEn"):
        corrida = ultima_corrida_de(e, h["investigacionId"])
        contenido = texto_prerregistro(h, lab, ahora, corrida.get("arnes") if corrida else None)
        art_id = guardar_artefacto(e, h["investigacionId"], f"Prerregistro: {h['titulo'][:80]}", "informe", contenido, f"Congelado el {datetime.fromtimestamp(ahora / 1000).strftime('%d/%m/%Y %H:%M')} al asignarlo a {lab}", corrida["iteracionActual"] if corrida else h["iteracion"], ahora)
        x["prerregistradoEn"] = ahora
        x["prerregistroArtefactoId"] = art_id
        h["procedencia"]["registro"].append(f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} prerregistro congelado al asignar a {lab}")
        con_evento(e, h["investigacionId"], "hipotesis_decidida", f"Experimento prerregistrado y asignado a {lab}: {h['titulo']}", f"#/investigaciones/{h['investigacionId']}/artefactos/{art_id}", ahora)
    return True


def texto_prerregistro(h: dict, laboratorio: str, ahora: int, arnes: dict | None) -> str:
    """El registro inmutable. Mismo contenido en el frontend (acciones.ts)."""
    x = h["experimento"]
    c = h["comprobacion"]
    k = h.get("conclusion") or {}
    lineas = [
        f"# Prerregistro: {h['titulo']}",
        "",
        f"Congelado el {datetime.fromtimestamp(ahora / 1000).strftime('%d/%m/%Y %H:%M')}. Asignado a: {laboratorio}. Hipotesis {h['id']}, iteracion {h['iteracion']}, prerregistrada el {datetime.fromtimestamp(h['prerregistradaEn'] / 1000).strftime('%d/%m/%Y')}.",
        "",
        "## Hipotesis (no se modifica despues de esta fecha)",
        h["enunciado"],
        "",
        "## Mecanismo propuesto",
        h["mecanismo"],
        "",
        "## Como se comprobara",
        f"Biomarcador: {c['biomarcador']}",
        f"Cohorte: {c['cohorte']}",
        f"Diseno: {c['diseno']}",
        "",
        "## Protocolo",
        x["protocolo"],
        "",
        "## Ensayo y criterios fijados de antemano",
        x["ensayo"],
        "",
        "## Coste estimado",
        x["costeEstimado"],
    ]
    if x.get("analisisPedido"):
        lineas += ["", "## Analisis sobre datos existentes", x["analisisPedido"]]
    if k:
        lineas += ["", "## Estado de la evidencia al prerregistrar", f"Certeza: {k.get('certeza')}. Direccion: {k.get('direccion')}.", k.get("enunciado", ""), f"Subiria la certeza si: {k.get('subiria', '')}", f"Bajaria si: {k.get('bajaria', '')}"]
    if arnes:
        lineas += ["", "## Version de Rosa", f"Commit {arnes.get('commit')}, firmas {arnes.get('firmas')}, programas optimizados: {arnes.get('optimizados')}."]
    lineas += ["", "Lo que se analice fuera de este registro se reporta como exploratorio, separado de lo prerregistrado."]
    return "\n".join(lineas)


def registrar_datos_experimento(e: Estado, hipotesis_id: str, fichero: str, analisis: str) -> bool:
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h or not fichero.strip() or not h["experimento"]:
        return False
    h["experimento"]["ficheroDatos"] = fichero.strip()
    h["experimento"]["analisisPedido"] = analisis.strip()
    h["experimento"]["estado"] = "datos_recibidos"
    return True


# ---------------------------------------------------------------------------
# Comentarios anclados
# ---------------------------------------------------------------------------


def anadir_comentario(e: Estado, hipotesis_id: str, ancla: dict, nota: str, ahora: int) -> bool:
    limpia = nota.strip()
    if not limpia or not str(ancla.get("cita", "")).strip() or len(limpia) > 1000:
        return False
    e["comentarios"].append({"id": P.nuevo_id("com"), "hipotesisId": hipotesis_id, "ancla": ancla, "nota": limpia, "estado": "pendiente", "creadoEn": ahora})
    return True


def editar_comentario(e: Estado, comentario_id: str, nota: str) -> bool:
    limpia = nota.strip()
    if not limpia or len(limpia) > 1000:
        return False
    for c in e["comentarios"]:
        if c["id"] == comentario_id and c["estado"] == "pendiente":
            c["nota"] = limpia
            return True
    return False


def quitar_comentario(e: Estado, comentario_id: str) -> bool:
    antes = len(e["comentarios"])
    e["comentarios"] = [c for c in e["comentarios"] if not (c["id"] == comentario_id and c["estado"] == "pendiente")]
    return len(e["comentarios"]) != antes


def enviar_comentarios(e: Estado, hipotesis_id: str, mensaje: str, quien: str, ahora: int) -> bool:
    pendientes = [c for c in e["comentarios"] if c["hipotesisId"] == hipotesis_id and c["estado"] == "pendiente"]
    texto = mensaje.strip()
    if not pendientes and not texto:
        return False
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h:
        return False
    lineas = [f"Sobre «{c['ancla']['cita']}»: {c['nota']}" for c in pendientes]
    cuerpo = "\n".join(l for l in [texto, *lineas] if l)
    n = len(pendientes)
    for c in pendientes:
        c["estado"] = "enviado"
    if h["estado"] == "propuesta":
        h["estado"] = "en_revision"
    h["revisiones"].append({"fecha": ahora, "quien": quien, "accion": "comentada", "nota": (f"{n} {'comentario' if n == 1 else 'comentarios'}" if n else "Mensaje"), "aCiegas": False})
    h["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "investigadora", "texto": cuerpo, "creadoEn": ahora})
    h["_comentariosNuevos"] = True
    return True


# ---------------------------------------------------------------------------
# Meta-revision y modelo de mundo
# ---------------------------------------------------------------------------


def inyectar_debilidad(e: Estado, corrida_id: str, debilidad_id: str) -> bool:
    c = corrida_de(e, corrida_id)
    if not c:
        return False
    for m in c["metaRevisiones"]:
        for d in m["debilidades"]:
            if d["id"] == debilidad_id:
                if d["inyectada"]:
                    return False
                d["inyectada"] = True
                if d["texto"] not in e["criteriosRevision"]:
                    e["criteriosRevision"].append(d["texto"])
                return True
    return False


def recomprobar_retracciones(e: Estado, investigacion_id: str, ahora: int) -> bool:
    """Marca la peticion; el bucle consulta Crossref de verdad y actualiza
    `retraccion` y `retraccionComprobadaEn` en cada fuente."""
    inv = _buscar(e["investigaciones"], investigacion_id)
    if not inv:
        return False
    inv["_recomprobarRetracciones"] = ahora
    con_evento(e, investigacion_id, "retraccion", "Recomprobacion de retractaciones pedida (Crossref y Retraction Watch)", None, ahora)
    return True


# ---------------------------------------------------------------------------
# Investigaciones y datos
# ---------------------------------------------------------------------------


def crear_investigacion(e: Estado, datos: dict, ahora: int, id_: str | None = None) -> str | bool:
    def t(k: str) -> str:
        return str(datos.get(k, "") or "").strip()

    if not t("titulo") or not t("objetivo") or not t("condicionParada"):
        return False
    cfg = datos.get("configuracion") or {}
    inv = {
        "id": id_ or P.nuevo_id("inv"),
        "titulo": t("titulo"),
        "objetivo": t("objetivo"),
        "relevancia": t("relevancia"),
        "limites": [l.strip() for l in datos.get("limites", []) if str(l).strip()],
        "condicionParada": t("condicionParada"),
        "revisores": [r.strip() for r in datos.get("revisores", []) if str(r).strip()],
        "estado": "activa",
        "creadaEn": ahora,
        "ramaDe": None,
        "configuracion": {
            "preferencias": str(cfg.get("preferencias", "")).strip(),
            "atributos": [a.strip() for a in cfg.get("atributos", []) if str(a).strip()],
            "restricciones": [r.strip() for r in cfg.get("restricciones", []) if str(r).strip()],
        },
        "datasets": [],
        "vigilarLiteraturaHasta": None,
    }
    e["investigaciones"].append(inv)
    heredar = datos.get("heredarModeloDe")
    if heredar:
        for h in [x for x in e["hechos"] if x["investigacionId"] == heredar]:
            e["hechos"].append({**h, "id": f"{h['id']}-{inv['id']}", "investigacionId": inv["id"]})
    return inv["id"]


def bifurcar_investigacion(e: Estado, investigacion_id: str, motivo: str, ahora: int, id_: str | None = None) -> str | bool:
    origen = _buscar(e["investigaciones"], investigacion_id)
    if not origen:
        return False
    nuevo = id_ or P.nuevo_id("inv")
    rama = {
        **origen,
        "id": nuevo,
        "titulo": f"{origen['titulo']} (rama)",
        "objetivo": origen["objetivo"] if not motivo.strip() else f"{origen['objetivo']}\n\nRama: {motivo.strip()}",
        "creadaEn": ahora,
        "ramaDe": origen["id"],
        "vigilarLiteraturaHasta": None,
        "datasets": [dict(d) for d in origen["datasets"]],
    }
    e["investigaciones"].append(rama)
    for h in [x for x in e["hechos"] if x["investigacionId"] == investigacion_id]:
        e["hechos"].append({**h, "id": f"{h['id']}-{nuevo}", "investigacionId": nuevo})
    return nuevo


def actualizar_configuracion(e: Estado, investigacion_id: str, configuracion: dict) -> bool:
    inv = _buscar(e["investigaciones"], investigacion_id)
    if not inv:
        return False
    inv["configuracion"] = {
        "preferencias": str(configuracion.get("preferencias", "")).strip(),
        "atributos": [a.strip() for a in configuracion.get("atributos", []) if str(a).strip()],
        "restricciones": [r.strip() for r in configuracion.get("restricciones", []) if str(r).strip()],
    }
    return True


def anadir_dataset(e: Estado, investigacion_id: str, dataset: dict) -> bool:
    inv = _buscar(e["investigaciones"], investigacion_id)
    if not inv or not str(dataset.get("nombre", "")).strip():
        return False
    inv["datasets"].append({**dataset, "id": P.nuevo_id("ds"), "estado": "pendiente"})
    return True


def _dataset(e: Estado, investigacion_id: str, dataset_id: str) -> dict | None:
    inv = _buscar(e["investigaciones"], investigacion_id)
    return _buscar(inv["datasets"], dataset_id) if inv else None


def decidir_dataset(e: Estado, investigacion_id: str, dataset_id: str, decision: str) -> bool:
    ds = _dataset(e, investigacion_id, dataset_id)
    if not ds or decision not in ("aprobado", "rechazado"):
        return False
    if decision == "aprobado" and (ds["columnasSinDiccionario"] > 0 or ds["valoresCentinela"] > 0 or ds["nombresDuplicados"] > 0):
        return False
    ds["estado"] = decision
    return True


def aprobar_diccionario(e: Estado, investigacion_id: str, dataset_id: str) -> bool:
    ds = _dataset(e, investigacion_id, dataset_id)
    if not ds:
        return False
    ds["columnasSinDiccionario"] = 0
    return True


def corregir_dataset(e: Estado, investigacion_id: str, dataset_id: str) -> bool:
    ds = _dataset(e, investigacion_id, dataset_id)
    if not ds:
        return False
    ds["valoresCentinela"] = 0
    ds["nombresDuplicados"] = 0
    return True


def clasificar_dataset(e: Estado, investigacion_id: str, dataset_id: str, clasificacion: str) -> bool:
    ds = _dataset(e, investigacion_id, dataset_id)
    if not ds or clasificacion not in ("publico", "interno", "personas"):
        return False
    ds["clasificacion"] = clasificacion
    return True


# ---------------------------------------------------------------------------
# Artefactos
# ---------------------------------------------------------------------------


def destacar_artefacto(e: Estado, artefacto_id: str) -> bool:
    a = _buscar(e["artefactos"], artefacto_id)
    if not a:
        return False
    a["destacado"] = not a["destacado"]
    return True


def guardar_artefacto(e: Estado, investigacion_id: str, nombre: str, tipo: str, contenido: str, resumen: str, iteracion: int, ahora: int, id_: str | None = None) -> str:
    existente = next((a for a in e["artefactos"] if a["investigacionId"] == investigacion_id and a["nombre"] == nombre), None)
    if existente:
        existente["versiones"].append({"n": len(existente["versiones"]) + 1, "creadaEn": ahora, "resumen": resumen, "contenido": contenido, "iteracion": iteracion})
        return existente["id"]
    nuevo = id_ or P.nuevo_id("art")
    e["artefactos"].append({"id": nuevo, "investigacionId": investigacion_id, "nombre": nombre, "tipo": tipo, "destacado": False, "versiones": [{"n": 1, "creadaEn": ahora, "resumen": resumen, "contenido": contenido, "iteracion": iteracion}]})
    return nuevo


# ---------------------------------------------------------------------------
# Calidad y ajustes
# ---------------------------------------------------------------------------


def cambiar_estado_caso(e: Estado, clave: str, nuevo: str) -> bool:
    if nuevo not in ("aprobado", "descartado", "propuesto"):
        return False
    for c in e["casos"]:
        if c["clave"] == clave:
            c["estado"] = nuevo
            return True
    return False


def editar_respuesta_caso(e: Estado, clave: str, respuesta: str) -> bool:
    limpia = respuesta.strip()
    if not limpia or len(limpia) > 2000:
        return False
    for c in e["casos"]:
        if c["clave"] == clave:
            c["respuestaEsperada"] = limpia
            return True
    return False


def editar_recuerdo(e: Estado, id_: str, texto: str) -> bool:
    r = _buscar(e["memoria"], id_)
    if not r or not texto.strip():
        return False
    r["texto"] = texto.strip()
    return True


def borrar_recuerdo(e: Estado, id_: str) -> bool:
    antes = len(e["memoria"])
    e["memoria"] = [r for r in e["memoria"] if r["id"] != id_]
    return len(e["memoria"]) != antes


def anadir_criterio(e: Estado, texto: str) -> bool:
    limpio = texto.strip()
    if not limpio or limpio in e["criteriosRevision"]:
        return False
    e["criteriosRevision"].append(limpio)
    return True


def borrar_criterio(e: Estado, indice: int) -> bool:
    if not (0 <= indice < len(e["criteriosRevision"])):
        return False
    del e["criteriosRevision"][indice]
    return True


def actualizar_avisos(e: Estado, avisos: dict) -> bool:
    e["avisos"] = avisos
    return True


def actualizar_politica_esperas(e: Estado, politica: dict) -> bool:
    horas = politica.get("horas")
    if not isinstance(horas, (int, float)) or horas <= 0:
        return False
    e["politicaEsperas"] = {**politica, "escalarA": str(politica.get("escalarA", "")).strip()}
    return True


def borrar_plan_guardado(e: Estado, id_: str) -> bool:
    antes = len(e["planesGuardados"])
    e["planesGuardados"] = [p for p in e["planesGuardados"] if p["id"] != id_]
    return len(e["planesGuardados"]) != antes


# ---------------------------------------------------------------------------
# Acciones que solo existen en el servidor
# ---------------------------------------------------------------------------


def iniciar_corrida(e: Estado, investigacion_id: str, ahora: int, limite: int | None = None) -> str | bool:
    """Arranca una corrida nueva si la investigacion no tiene ninguna viva.
    El bucle la ve en `esperando_plan` sin iteraciones y propone el plan."""
    inv = _buscar(e["investigaciones"], investigacion_id)
    if not inv:
        return False
    ultima = ultima_corrida_de(e, investigacion_id)
    if ultima and ultima["estado"] not in ("detenida", "terminada"):
        return False
    c = P.nueva_corrida(investigacion_id, (ultima["numero"] + 1) if ultima else 1, ahora, limite)
    e["corridas"].append(c)
    inv["estado"] = "activa"
    con_evento(e, investigacion_id, "corrida_estado", f"Corrida {c['numero']} creada; Rosa propone el plan de la iteracion 1", f"#/investigaciones/{investigacion_id}/corrida", ahora)
    return c["id"]
