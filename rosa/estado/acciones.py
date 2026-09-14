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

import copy

from datetime import datetime, timezone
from typing import Any

from rosa import config, politicas
from rosa import parada as PARADA
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
    if not c or not isinstance(nuevo_limite, (int, float)) or isinstance(nuevo_limite, bool):
        return False
    limite = int(round(nuevo_limite))
    if limite <= c["gasto"]["llamadas"] or limite <= 0:
        return False
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


def aprobar_plan(e: Estado, iteracion_id: str, ahora: int, quien: str = "Investigadora") -> bool:
    it = _buscar(e["iteraciones"], iteracion_id)
    if not it or it["planAprobado"]:
        return False
    it["planAprobado"] = True
    it["empezadaEn"] = ahora
    c = corrida_de(e, it["corridaId"])
    if c and c["estado"] == "esperando_plan":
        c["estado"] = "en_marcha"
    if c:
        # Aprobar el primer plan aprueba tambien la mision tal como esta en
        # pantalla: la persona la vio encima del plan. Despues se puede editar.
        inv = _buscar(e["investigaciones"], c["investigacionId"])
        if inv and inv.get("mision") and not inv["mision"].get("aprobadaEn"):
            inv["mision"]["aprobadaEn"] = ahora
            inv["mision"]["aprobadaPor"] = quien
            con_evento(e, inv["id"], "mision", "Mision aprobada junto con el primer plan", f"#/investigaciones/{inv['id']}/investigacion", ahora)
        # La pregunta de la campana, si Rosa la formulo, queda aprobada con el plan.
        if c.get("pregunta") and not c["pregunta"].get("aprobadaEn"):
            c["pregunta"]["aprobadaEn"] = ahora
        con_evento(e, c["investigacionId"], "corrida_estado", f"Plan de la iteracion {it['numero']} aprobado", None, ahora)
    return True


def actualizar_pregunta(e: Estado, corrida_id: str, pregunta: dict, quien: str, ahora: int) -> bool:
    """La persona corrige la pregunta de la campana. Cambiarla despues de
    empezar deja rastro en el registro; la version anterior se conserva en
    el historial de la propia pregunta."""
    c = corrida_de(e, corrida_id)
    if not c or not isinstance(pregunta, dict):
        return False
    base = c.get("pregunta") or P.pregunta_vacia()
    nueva = dict(base)
    for k in ("contexto", "etapa", "intervencion", "comparador", "desenlace", "ventana", "unidadBiologica", "mecanismos", "decision", "umbralEfecto"):
        if k in pregunta:
            nueva[k] = str(pregunta[k]).strip()
    if pregunta.get("pasoRuta") in P.PASOS_RUTA:
        nueva["pasoRuta"] = pregunta["pasoRuta"]
    nueva["umbralResuelto"] = bool(nueva["umbralEfecto"]) and "sin resolver" not in nueva["umbralEfecto"].lower()
    nueva["propuestaPorRosa"] = False
    nueva["aprobadaEn"] = ahora
    nueva.setdefault("_anteriores", []).append({k: v for k, v in base.items() if not k.startswith("_")})
    c["pregunta"] = nueva
    con_evento(e, c["investigacionId"], "corrida_estado", f"Pregunta de la corrida {c['numero']} corregida por {quien}", f"#/investigaciones/{c['investigacionId']}/corrida", ahora)
    return True


def actualizar_metodo(e: Estado, metodo_id: str, cambios: dict, quien: str, ahora: int) -> bool:
    """El registro de metodos lo edita una persona (validacion, estado,
    contextos, responsable). Retirar o restringir un metodo es una decision
    con nombre y fecha."""
    m = _buscar(e.get("metodos", []), metodo_id)
    if not m or not isinstance(cambios, dict):
        return False
    for k in ("evalua", "entradas", "salidas", "validacion", "fallosConocidos", "version", "coste", "responsable"):
        if k in cambios:
            m[k] = str(cambios[k]).strip()
    for k in ("contextos", "exclusiones", "dependeDe", "probadoEn"):
        if isinstance(cambios.get(k), list):
            m[k] = [str(x).strip() for x in cambios[k] if str(x).strip()]
    if cambios.get("estado") in ("propuesto", "implementado", "probado_en_contexto", "restringido", "retirado"):
        if cambios["estado"] != m["estado"]:
            e.setdefault("aprendizaje", []).append(P.nuevo_cambio_aprendizaje(None, 2, "programa", f"Metodo '{m['nombre'][:60]}': de {m['estado']} a {cambios['estado']}", f"metodo:{metodo_id}", "promovido", quien, ahora))
        m["estado"] = cambios["estado"]
    m["actualizadoEn"] = ahora
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
                a["valor"] = str(argumentos[a["nombre"]]).strip() or a["valor"]
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


def revisar_hipotesis(e: Estado, hipotesis_id: str, accion: str, nota: str, quien: str, ahora: int, a_ciegas: bool = False, revision_humana: dict | None = None, etapa: str = "persona", version_esperada: int | None = None, segundos_revision: float | None = None) -> bool:
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h or accion not in ESTADO_TRAS_ACCION:
        return False
    # Concurrencia: la decision se tomo mirando una version concreta. Si la
    # hipotesis cambio entre medias (Rosa la reformulo), no se aplica sobre la
    # nueva; la interfaz se resincroniza y la persona vuelve a mirar.
    if version_esperada is not None and int(version_esperada) != h.get("version", 1):
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
    # Toda decision humana queda en el registro de decisiones (DecisionRecord).
    if accion in ("aceptar", "descartar", "refinar", "reabrir") and etapa == "persona":
        d = registrar_decision(e, h, "persona", {"aceptar": "aceptada", "descartar": "descartada", "refinar": "refinar", "reabrir": "reabierta"}[accion], nota_limpia or textos[accion], quien, ahora)
        if segundos_revision is not None:
            d["segundosRevision"] = round(float(segundos_revision), 1)  # carga de revision: la metrica que pide el plan
    if accion == "refinar" and etapa == "persona":
        h["_reformularPedida"] = nota_limpia or "La persona pidio refinarla"  # el bucle la reformula como version nueva
    if accion == "reabrir":
        h["decisionKiller"] = None
        h["_revisionPedida"] = True
    recalcular_bloqueos(e, h)
    return True


def evaluar_aprendizaje(e: Estado, cambio_id: str, ahora: int) -> bool:
    """Pedir la evaluacion de un cambio de nivel 2 sobre el conjunto
    reservado (las hipotesis con decision humana). El bucle la hace."""
    c = _buscar(e.get("aprendizaje", []), cambio_id)
    if not c or c["nivel"] != 2 or c["estado"] not in ("propuesto", "evaluado") or c["tipo"] != "criterio":
        return False
    c["_evaluar"] = ahora
    return True


# ---------------------------------------------------------------------------
# ROSA2018: mision, versiones, decisiones, puerta, analisis, aprendizaje
# ---------------------------------------------------------------------------


def registrar_decision(e: Estado, h: dict, etapa: str, decision: str, motivo: str, quien: str, ahora: int, comprobaciones: list[dict] | None = None, que_haria_falta: str = "") -> dict:
    if etapa.startswith("killer") and decision not in politicas.DECISIONES_KILLER:
        raise ValueError(f"decision del Killer fuera de la politica: {decision}")
    d = P.nueva_decision(h["investigacionId"], h["id"], h.get("version", 1), etapa, decision, motivo, quien, ahora, comprobaciones, que_haria_falta)
    # Cuanto contexto habia al decidir: sirve para vigilar si la calidad de las
    # decisiones cae cuando crece el modelo de mundo (context rot).
    d["contexto"] = {"hechos": sum(1 for x in e.get("hechos", []) if x.get("investigacionId") == h["investigacionId"]), "hipotesisVivas": sum(1 for x in e.get("hipotesis", []) if x.get("investigacionId") == h["investigacionId"] and x.get("estado") != "descartada")}
    e.setdefault("decisiones", []).append(d)
    return d


def recalcular_bloqueos(e: Estado, h: dict) -> list[str]:
    """Los bloqueos no compensables, calculados con la misma regla que
    `frontend/src/lib/priorizacion.ts`. Se guardan en la hipotesis para que
    el ranking, el dossier y la pantalla digan lo mismo."""
    from rosa.priorizacion import bloqueos_de

    b = bloqueos_de(e, h)
    h["bloqueos"] = b
    if b:
        h["candidata"] = False
    return b


def aprobar_mision(e: Estado, investigacion_id: str, mision: dict, quien: str, ahora: int) -> bool:
    """La persona aprueba la mision (corrigiendo lo que quiera). Los campos
    vacios se quedan vacios: la mision aprobada es lo que se ve, no lo que
    Rosa propuso."""
    inv = _buscar(e["investigaciones"], investigacion_id)
    if not inv or not isinstance(mision, dict):
        return False
    base = inv.get("mision") or P.mision_vacia()
    pres = mision.get("presupuesto") or {}
    nueva = {
        **base,
        "poblacion": str(mision.get("poblacion", base["poblacion"])).strip(),
        "etapa": str(mision.get("etapa", base["etapa"])).strip(),
        "celulaTejido": str(mision.get("celulaTejido", base["celulaTejido"])).strip(),
        "mecanismo": str(mision.get("mecanismo", base["mecanismo"])).strip(),
        "tipoIntervencion": str(mision.get("tipoIntervencion", base["tipoIntervencion"])).strip(),
        "capacidadesLaboratorio": [str(c).strip() for c in mision.get("capacidadesLaboratorio", base["capacidadesLaboratorio"]) if str(c).strip()],
        "presupuesto": {k: (float(pres[k]) if pres.get(k) is not None and str(pres[k]).strip() != "" else float(base["presupuesto"][k])) for k in ("llamadas", "usd", "horas")},
        "aprobadaEn": ahora,
        "aprobadaPor": quien,
    }
    if isinstance(mision.get("metaAmplia"), str):
        nueva["metaAmplia"] = mision["metaAmplia"].strip()
    if isinstance(mision.get("responsables"), dict):
        base_r = base.get("responsables") or P.mision_vacia()["responsables"]
        nueva["responsables"] = {k: str(mision["responsables"].get(k, base_r.get(k, ""))).strip() for k in base_r}
    if nueva["presupuesto"]["llamadas"] <= 0 or nueva["presupuesto"]["usd"] <= 0 or nueva["presupuesto"]["horas"] <= 0:
        return False
    nueva["presupuesto"]["llamadas"] = int(nueva["presupuesto"]["llamadas"])
    inv["mision"] = nueva
    inv.pop("_misionIntentada", None)
    # El presupuesto en llamadas de la corrida viva sigue a la mision.
    c = ultima_corrida_de(e, investigacion_id)
    if c and c["estado"] not in ("detenida", "terminada") and c["presupuesto"]["limiteLlamadas"] != nueva["presupuesto"]["llamadas"] and nueva["presupuesto"]["llamadas"] > c["gasto"]["llamadas"]:
        c["presupuesto"]["limiteLlamadas"] = nueva["presupuesto"]["llamadas"]
    con_evento(e, investigacion_id, "mision", f"Mision aprobada por {quien}", f"#/investigaciones/{investigacion_id}/investigacion", ahora)
    return True


def resolver_hallazgo_registro(e: Estado, iteracion_id: str, hallazgo_id: str, estado: str, respuesta: str, quien: str, ahora: int) -> bool:
    """Una persona atiende o descarta un hallazgo del revisor de registro,
    con su respuesta. Si no queda ninguno abierto, la revision pasa a limpia."""
    it = _buscar(e["iteraciones"], iteracion_id)
    if not it or not it.get("revisionRegistro") or estado not in ("atendido", "descartado", "abierto"):
        return False
    hz = next((x for x in it["revisionRegistro"]["hallazgos"] if x.get("id") == hallazgo_id), None)
    if not hz:
        return False
    hz["estado"] = estado
    hz["respuesta"] = respuesta.strip()[:400]
    hz["resueltoPor"] = quien.strip() or "persona"
    hz["resueltoEn"] = ahora
    it["revisionRegistro"]["estado"] = "con_hallazgos" if any(x.get("estado", "abierto") == "abierto" for x in it["revisionRegistro"]["hallazgos"]) else "limpia"
    return True


def fijar_permiso_conector(e: Estado, nombre: str, nivel: str, quien: str, ahora: int) -> bool:
    """Permiso por conector: permitir, solo cuando una persona pregunta, o
    bloquear. Queda en el estado y en el proceso (la capa de conectores lo
    lee en cada llamada). Es una decision de politica: va al aprendizaje."""
    from rosa.conectores import REGISTRO
    from rosa.conectores.base import NIVELES_PERMISO, PERMISOS

    if nombre not in REGISTRO or nivel not in NIVELES_PERMISO:
        return False
    anterior = e.setdefault("permisosConectores", {}).get(nombre, "permitir")
    if anterior == nivel:
        return False
    e["permisosConectores"][nombre] = nivel
    PERMISOS[nombre] = nivel
    e.setdefault("aprendizaje", []).append(P.nuevo_cambio_aprendizaje(None, 3, "politica", f"Conector {REGISTRO[nombre].fuente}: de {anterior} a {nivel}", f"conector:{nombre}", "promovido", quien, ahora))
    for c in e.get("conectores", []):
        if c["nombre"] == nombre:
            c["permiso"] = nivel
    return True


def anadir_memoria(e: Estado, investigacion_id: str, texto: str, quien: str, ahora: int) -> bool:
    """Memoria del proyecto (como la memoria de Claude Science): hechos
    cortos y estables que Rosa lee en cada mision (preferencias, restricciones,
    decisiones confirmadas). Los escribe y borra una persona; nunca resultados
    ni copias de literatura."""
    inv = _buscar(e["investigaciones"], investigacion_id)
    limpio = texto.strip()
    if not inv or not limpio or len(limpio) > 400:
        return False
    inv.setdefault("memoria", []).append({"id": P.nuevo_id("mem"), "texto": limpio, "quien": quien.strip() or "persona", "fecha": ahora})
    return True


def quitar_memoria(e: Estado, investigacion_id: str, memoria_id: str) -> bool:
    inv = _buscar(e["investigaciones"], investigacion_id)
    if not inv:
        return False
    antes = len(inv.get("memoria", []) or [])
    inv["memoria"] = [m for m in inv.get("memoria", []) or [] if m["id"] != memoria_id]
    return len(inv["memoria"]) != antes


def registrar_pregunta_bases(e: Estado, investigacion_id: str, pregunta: dict, ahora: int) -> bool:
    """La respuesta de una pregunta con herramientas entra a la investigacion
    con sus consultas, para que se vea de donde salio cada dato."""
    inv = _buscar(e["investigaciones"], investigacion_id)
    if not inv or not isinstance(pregunta, dict) or not pregunta.get("pregunta"):
        return False
    inv.setdefault("preguntasABases", []).append({"id": P.nuevo_id("pb"), "fecha": ahora, **{k: pregunta.get(k) for k in ("pregunta", "respuesta", "limites", "herramientas", "consultas", "iteraciones", "quien", "error")}})
    return True


def registrar_evaluacion(e: Estado, evaluacion: dict, quien: str, ahora: int) -> bool:
    """Un panel de evaluacion del sistema (por ahora, el panel del Killer con
    fallos plantados) entra al estado como registro con fecha: resumen,
    detalle por tipo de fallo y los casos. Sirve para comparar versiones del
    prompt o del modelo con la misma prueba. Si el modelo del juez cambio
    respecto al panel anterior, o el acuerdo cayo, queda una incidencia."""
    if not isinstance(evaluacion, dict) or evaluacion.get("tipo") not in ("panel_killer",) or not isinstance(evaluacion.get("resumen"), dict):
        return False
    anteriores = [x for x in e.get("evaluaciones", []) if x.get("tipo") == evaluacion["tipo"]]
    anterior = anteriores[-1] if anteriores else None
    reg = {"id": P.nuevo_id("eval"), "tipo": evaluacion["tipo"], "fecha": int(evaluacion.get("fecha") or ahora), "quien": quien.strip() or "persona", "resumen": evaluacion["resumen"], "porFallo": evaluacion.get("porFallo") or {}, "fallos": evaluacion.get("fallos") or {}, "casos": list(evaluacion.get("casos") or [])[:400]}
    e.setdefault("evaluaciones", []).append(reg)
    r = reg["resumen"]
    e.setdefault("aprendizaje", []).append(P.nuevo_cambio_aprendizaje(None, 2, "programa", f"Panel del Killer: deteccion {r.get('tasaDeteccion')}, abstencion {r.get('abstencion')}, sobre-matanza en gris {r.get('sobreMatanzaGris')} ({r.get('casos')} casos, {r.get('usd')} USD)", f"evaluacion:{reg['id']}", "promovido", quien, ahora))
    avisos = []
    if anterior and anterior["resumen"].get("juez") and r.get("juez") and anterior["resumen"]["juez"] != r["juez"]:
        avisos.append(f"el modelo del juez cambio de {anterior['resumen']['juez']} a {r['juez']}")
    ka = ((anterior or {}).get("resumen", {}).get("acuerdo") or {}).get("decision") or {}
    kb = (r.get("acuerdo") or {}).get("decision") or {}
    if ka.get("kappa") is not None and kb.get("kappa") is not None and ka["kappa"] - kb["kappa"] > 0.15:
        avisos.append(f"el acuerdo por decision bajo de kappa {ka['kappa']} a {kb['kappa']}")
    if anterior and anterior["resumen"].get("tasaDeteccion") is not None and r.get("tasaDeteccion") is not None and anterior["resumen"]["tasaDeteccion"] - r["tasaDeteccion"] > 0.15:
        avisos.append(f"la deteccion bajo de {anterior['resumen']['tasaDeteccion']} a {r['tasaDeteccion']}")
    if avisos:
        e.setdefault("incidencias", []).append({"id": P.nuevo_id("inc"), "corridaId": None, "tipo": "calibracion_juez", "titulo": "El panel del Killer cambio respecto al anterior", "detalle": "; ".join(avisos) + ". Revisa antes de confiar en las decisiones nuevas.", "estado": "pendiente", "creadaEn": ahora, "resueltaEn": None, "resolucion": None, "opciones": ["revisar", "aceptar"]})
    return True


def registrar_sello_externo(e: Estado, hipotesis_id: str, sello: dict, ahora: int) -> bool:
    """El sello RFC 3161 del prerregistro (hash, autoridades, hora firmada y
    los tokens) queda en el experimento y en el registro de procedencia."""
    from rosa import sello as S

    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h or not h.get("experimento") or not isinstance(sello, dict) or not sello.get("hash"):
        return False
    x = h["experimento"]
    x["selloExterno"] = {k: sello.get(k) for k in ("algoritmo", "hash", "pedidoEn", "ok", "testigos", "primeraHora", "error")} | {"sellos": [{k: s_.get(k) for k in ("tsa", "url", "ca", "ok", "genTime", "serial", "politica", "tsrBase64", "error", "ms")} for s_ in sello.get("sellos") or []]}
    h["procedencia"]["registro"].append(f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} prerregistro: {S.texto_para_registro(sello)}")
    return True


TIPOS_CONOCIMIENTO_OPERATIVO = ("protocolo", "reactivo", "medicion", "muestra", "otro")


def anadir_conocimiento_operativo(e: Estado, investigacion_id: str, texto: str, tipo: str, quien: str, ahora: int) -> bool:
    """Lo que el laboratorio sabe y nunca se escribe (que protocolo no es
    fiable, que lote de anticuerpo falla, que medicion tiene un artefacto).
    Entra como evidencia de clase `conocimiento_operativo`, con su propio
    estatus: Rosa lo lee al planificar experimentos y lo cita en el dossier,
    pero no lo mezcla con la literatura ni lo cuenta como observacion."""
    inv = _buscar(e["investigaciones"], investigacion_id)
    t = (texto or "").strip()
    if not inv or len(t) < 8 or tipo not in TIPOS_CONOCIMIENTO_OPERATIVO:
        return False
    inv.setdefault("conocimientoOperativo", []).append({"id": P.nuevo_id("op"), "texto": t[:1200], "tipo": tipo, "quien": (quien or "").strip() or "persona", "fecha": ahora, "clase": "conocimiento_operativo"})
    return True


def quitar_conocimiento_operativo(e: Estado, investigacion_id: str, id_: str) -> bool:
    inv = _buscar(e["investigaciones"], investigacion_id)
    if not inv:
        return False
    antes = len(inv.get("conocimientoOperativo") or [])
    inv["conocimientoOperativo"] = [x for x in inv.get("conocimientoOperativo") or [] if x["id"] != id_]
    return len(inv["conocimientoOperativo"]) != antes


def _modelo_juez() -> str:
    from rosa import gateway

    return gateway.JUEZ


def etiquetar_comprobacion(e: Estado, hipotesis_id: str, comprobacion: str, veredicto_humano: str, quien: str, ahora: int, nota: str = "") -> bool:
    """Una persona cualificada dice si una comprobacion del Killer acierta:
    su veredicto (pasa, falla, no_comprobable) queda en el conjunto dorado
    junto al del juez, la version juzgada y el modelo. Es la materia prima
    del acuerdo juez-humano (kappa por comprobacion)."""
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h or veredicto_humano not in ("pasa", "falla", "no_comprobable") or not comprobacion:
        return False
    decisiones = [d for d in e.get("decisiones", []) if d.get("hipotesisId") == hipotesis_id and str(d.get("etapa", "")).startswith("killer")]
    ultima = decisiones[-1] if decisiones else None
    del_juez = next((c for c in (ultima or {}).get("comprobaciones", []) if c.get("comprobacion") == comprobacion), None)
    if not del_juez:
        return False
    caso = {
        "id": P.nuevo_id("oro"),
        "hipotesisId": hipotesis_id,
        "version": h.get("version", 1),
        "decisionId": (ultima or {}).get("id"),
        "comprobacion": comprobacion,
        "veredictoJuez": del_juez.get("resultado"),
        "detalleJuez": (del_juez.get("detalle") or "")[:300],
        "veredictoHumano": veredicto_humano,
        "nota": (nota or "").strip()[:500],
        "quien": (quien or "").strip() or "persona",
        "fecha": ahora,
        "modeloJuez": (ultima or {}).get("modelo") or _modelo_juez(),
    }
    dorado = e.setdefault("conjuntoDorado", [])
    # Una etiqueta nueva de la misma persona sobre la misma comprobacion y version sustituye a la anterior.
    e["conjuntoDorado"] = [c for c in dorado if not (c["hipotesisId"] == hipotesis_id and c["comprobacion"] == comprobacion and c["version"] == caso["version"] and c["quien"] == caso["quien"])] + [caso]
    h["procedencia"]["registro"].append(f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} conjunto dorado: {quien} dice que '{comprobacion}' {veredicto_humano} (el juez dijo {del_juez.get('resultado')})")
    return True


ESTADOS_AREA = ("propuesta", "elegida", "pausada", "sin_explorar")


def cambiar_estado_area(e: Estado, investigacion_id: str, area_id: str, estado: str | None, quien: str, ahora: int, condicion_reapertura: str = "", corrida_id: str | None = None, motivo: str = "") -> bool:
    """Las areas del programa las gobierna una persona: elegir, pausar con la
    condicion que la reabriria, reabrir, dejar sin explorar, o asignarla a una
    campana (corrida) concreta. Cada cambio queda con fecha, autor y motivo en
    el historial del area, porque decidir que NO se investiga es una decision
    tan auditable como la contraria (plan completo, etapa B)."""
    inv = _buscar(e["investigaciones"], investigacion_id)
    if not inv or not inv.get("mision"):
        return False
    a = _buscar(inv["mision"].get("areas", []), area_id)
    if not a:
        return False
    cambio = False
    if estado is not None:
        if estado not in ESTADOS_AREA:
            return False
        if estado == "pausada" and not condicion_reapertura.strip():
            return False  # pausar sin decir que la reabriria es abandonar sin registro
        if estado != a["estado"]:
            a.setdefault("historial", []).append({"fecha": ahora, "de": a["estado"], "a": estado, "quien": quien.strip() or "persona", "motivo": (motivo or condicion_reapertura).strip()[:300]})
            a["estado"] = estado
            cambio = True
        if estado == "pausada":
            a["condicionReapertura"] = condicion_reapertura.strip()[:300]
        elif estado == "elegida" and a.get("condicionReapertura"):
            a["condicionReapertura"] = ""  # reabierta: la condicion se cumplio o se levanto
    if corrida_id is not None:
        c = _buscar(e["corridas"], corrida_id) if corrida_id else None
        if corrida_id and (not c or c["investigacionId"] != investigacion_id):
            return False
        if (corrida_id or None) != a.get("corridaId"):
            a["corridaId"] = corrida_id or None
            a.setdefault("historial", []).append({"fecha": ahora, "de": a["estado"], "a": a["estado"], "quien": quien.strip() or "persona", "motivo": (f"asignada a la campana {c['numero']}" if c else "desasignada de su campana")})
            cambio = True
    if cambio:
        con_evento(e, investigacion_id, "mision", f"Area '{a['titulo'][:60]}': {a['estado'].replace('_', ' ')}" + (f" (campana {c['numero']})" if corrida_id and c else ""), f"#/investigaciones/{investigacion_id}/investigacion", ahora)
    return cambio


def reformular_hipotesis(e: Estado, hipotesis_id: str, cambios: dict, quien: str, motivo: str, ahora: int) -> bool:
    """Una version nueva de la hipotesis. La anterior se guarda entera en
    `versiones`; la nueva vuelve a la cola como propuesta y el Killer la
    juzga otra vez. Si ya agoto las reformulaciones de la politica, devuelve
    False: quien llama la descarta en este contexto."""
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h or not isinstance(cambios, dict):
        return False
    version = h.get("version", 1)
    if not politicas.puede_reformular(version):
        return False
    texto = {k: str(cambios.get(k, "")).strip() for k in ("titulo", "enunciado", "mecanismo")}
    if not texto["enunciado"] and not texto["titulo"]:
        return False
    h.setdefault("versiones", []).append(P.version_de(h, ahora, quien, motivo.strip() or "Reformulada"))
    h["version"] = version + 1
    for k, v in texto.items():
        if v:
            h[k] = v
    comp = cambios.get("comprobacion") or {}
    if isinstance(comp, dict):
        for k in ("biomarcador", "cohorte", "diseno"):
            if str(comp.get(k, "")).strip():
                h["comprobacion"][k] = str(comp[k]).strip()
    tarjeta = cambios.get("tarjeta")
    if isinstance(tarjeta, dict):
        base = h.get("tarjeta") or P.tarjeta_vacia()
        h["tarjeta"] = {**base, **{k: v for k, v in tarjeta.items() if k in base}}
    h["estado"] = "propuesta"
    h["decisionKiller"] = None
    h["candidata"] = False
    h.pop("_reformularPedida", None)
    h["_revisionPedida"] = True
    h["hallazgos"] = [x for x in h["hallazgos"] if x["estado"] != "abierto"] + [{**x, "estado": "atendido", "respuestaDeRosa": f"Atendido en la version {version + 1}: {motivo.strip()[:200]}"} for x in h["hallazgos"] if x["estado"] == "abierto"]
    h["revisiones"].append({"fecha": ahora, "quien": quien, "accion": "reformulada", "nota": f"Version {version + 1}: {motivo.strip()[:300]}", "aCiegas": False})
    h["procedencia"]["registro"].append(f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} version {version + 1} ({quien}): {motivo.strip()[:120]}")
    con_evento(e, h["investigacionId"], "hipotesis_decidida", f"Reformulada (version {version + 1}): {h['titulo']}", f"#/investigaciones/{h['investigacionId']}/hipotesis/{h['id']}", ahora)
    recalcular_bloqueos(e, h)
    return True


def eximir_puerta(e: Estado, investigacion_id: str, motivo: str, quien: str, ahora: int) -> bool:
    """Saltarse la puerta de reproduccion es una excepcion de politica: la
    firma una persona, con motivo, y queda en el registro de aprendizaje
    como cambio de nivel 3."""
    inv = _buscar(e["investigaciones"], investigacion_id)
    texto = motivo.strip()
    if not inv or not texto:
        return False
    puerta = inv.setdefault("puertaReproduccion", P.puerta_reproduccion())
    if puerta["estado"] == "eximida":
        return False
    puerta.update(estado="eximida", eximidaPor=quien, motivo=texto, fecha=ahora)
    e.setdefault("aprendizaje", []).append(P.nuevo_cambio_aprendizaje(investigacion_id, 3, "politica", f"Puerta de reproduccion eximida: {texto}", "puertaReproduccion", "aplicado", quien, ahora))
    con_evento(e, investigacion_id, "aprendizaje", f"Puerta de reproduccion eximida por {quien}: {texto[:120]}", f"#/investigaciones/{investigacion_id}/investigacion", ahora)
    return True


def cerrar_puerta(e: Estado, investigacion_id: str, quien: str, ahora: int) -> bool:
    inv = _buscar(e["investigaciones"], investigacion_id)
    if not inv:
        return False
    puerta = inv.setdefault("puertaReproduccion", P.puerta_reproduccion())
    if puerta["estado"] != "eximida":
        return False
    puerta.update(estado="abierta" if puerta["superadas"] >= puerta["requeridas"] else "bloqueada", eximidaPor=None, motivo="", fecha=ahora)
    con_evento(e, investigacion_id, "aprendizaje", f"Puerta de reproduccion vuelta a exigir por {quien}", None, ahora)
    return True


def anadir_reproduccion(e: Estado, investigacion_id: str, dataset_id: str, datos: dict, ahora: int) -> str | bool:
    """Registrar un analisis publicado que hay que reproducir: referencia,
    cifra publicada, valor y tolerancia. Se fija antes de ejecutar; el bucle
    lo corre y marca superada o fallida."""
    inv = _buscar(e["investigaciones"], investigacion_id)
    ds = _dataset(e, investigacion_id, dataset_id)
    if not inv or not ds:
        return False
    try:
        valor = float(str(datos.get("valorPublicado", "")).replace(",", "."))
        tol = float(str(datos.get("tolerancia", "0.1")).replace(",", "."))
    except ValueError:
        return False
    if not str(datos.get("referencia", "")).strip() or not str(datos.get("descripcion", "")).strip() or tol <= 0 or tol > 1:
        return False
    r = P.nueva_reproduccion(
        investigacion_id,
        dataset_id,
        ahora,
        referencia=str(datos.get("referencia", "")).strip(),
        doi=str(datos.get("doi", "")).strip(),
        descripcion=str(datos.get("descripcion", "")).strip(),
        cifraPublicada=str(datos.get("cifraPublicada", "")).strip(),
        valorPublicado=valor,
        tolerancia=tol,
    )
    e.setdefault("reproducciones", []).append(r)
    inv.setdefault("puertaReproduccion", P.puerta_reproduccion())
    con_evento(e, investigacion_id, "analisis", f"Reproduccion registrada: {r['referencia']} ({r['descripcion'][:80]})", f"#/investigaciones/{investigacion_id}/investigacion", ahora)
    return r["id"]


def pedir_analisis(e: Estado, hipotesis_id: str, dataset_id: str, pregunta: str, ahora: int) -> bool:
    """Pedir a Rosa un analisis in silico de la hipotesis sobre un dataset
    aprobado y fijado por hash. El bucle congela el plan, escribe el codigo,
    lo ejecuta en el sandbox y lo audita."""
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h:
        return False
    ds = _dataset(e, h["investigacionId"], dataset_id)
    if not ds or ds["estado"] != "aprobado" or not (ds.get("procedencia") or {}).get("hash"):
        return False
    if h.get("_analisisPedido"):
        return False
    h["_analisisPedido"] = {"datasetId": dataset_id, "pregunta": pregunta.strip(), "pedidoEn": ahora}
    h["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "investigadora", "texto": f"Analisis pedido sobre {ds['nombre']}: {pregunta.strip() or 'aplicar la prediccion falsable de la hipotesis'}", "creadoEn": ahora})
    con_evento(e, h["investigacionId"], "analisis", f"Analisis in silico pedido sobre {ds['nombre']}: {h['titulo'][:80]}", f"#/investigaciones/{h['investigacionId']}/hipotesis/{h['id']}", ahora)
    return True


def promover_aprendizaje(e: Estado, cambio_id: str, quien: str, ahora: int) -> bool:
    """Promover un cambio de nivel 2 (criterio o programa). Solo una persona.
    Un criterio promovido entra a los criterios de revision; un programa
    promovido se carga en el siguiente arranque (el servidor mueve el fichero)."""
    c = _buscar(e.get("aprendizaje", []), cambio_id)
    if not c or c["nivel"] != 2 or c["estado"] not in ("propuesto", "evaluado"):
        return False
    c["estado"] = "promovido"
    c["resueltoEn"] = ahora
    c["resueltoPor"] = quien
    if c["tipo"] == "criterio" and c["descripcion"] not in e["criteriosRevision"]:
        e["criteriosRevision"].append(c["descripcion"])
    if c["tipo"] == "programa":
        c["_promover"] = True
    con_evento(e, c.get("investigacionId"), "aprendizaje", f"Cambio de nivel 2 promovido por {quien}: {c['descripcion'][:100]}", "#/ajustes", ahora)
    return True


def revertir_aprendizaje(e: Estado, cambio_id: str, quien: str, motivo: str, ahora: int) -> bool:
    c = _buscar(e.get("aprendizaje", []), cambio_id)
    if not c or c["nivel"] == 3 or c["estado"] == "revertido":
        return False
    c["estado"] = "revertido"
    c["resueltoEn"] = ahora
    c["resueltoPor"] = quien
    if motivo.strip():
        c["evaluacion"] = {**(c.get("evaluacion") or {"conjunto": "", "casos": 0, "antes": None, "despues": None}), "nota": motivo.strip()}
    if c["tipo"] == "criterio" and c["descripcion"] in e["criteriosRevision"]:
        e["criteriosRevision"].remove(c["descripcion"])
    con_evento(e, c.get("investigacionId"), "aprendizaje", f"Cambio revertido por {quien}: {c['descripcion'][:100]}", "#/ajustes", ahora)
    return True


def generar_dossier(e: Estado, hipotesis_id: str, quien: str, ahora: int) -> str | bool:
    """El Wet-Lab Dossier: se arma de forma determinista con lo que hay en el
    estado (sin modelo) y se guarda como artefacto. Si la hipotesis tiene
    bloqueos, el dossier los pone en la primera pagina en vez de esconderlos."""
    from rosa.dossier import texto_dossier

    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h:
        return False
    inv = _buscar(e["investigaciones"], h["investigacionId"])
    corrida = ultima_corrida_de(e, h["investigacionId"])
    recalcular_bloqueos(e, h)
    contenido = texto_dossier(e, h, inv, corrida, ahora)
    # Revisor de registro por regla sobre el dossier: cifras e identificadores
    # que no esten en el registro de esta hipotesis quedan escritos al final.
    from rosa import revisor_registro as RR

    corpus = RR.corpus_del_registro(e, h["investigacionId"], None, corrida, hipotesis=h)
    runs_ok = sum(1 for r in e.get("ejecuciones", []) if r.get("estado") == "completado" and r.get("hipotesisId") == h["id"])
    hallazgos = RR.comprobaciones_deterministas(contenido, corpus, None, runs_ok if RR._EJECUCION.search(contenido) else 1)
    contenido += "\n\n## Revision del registro (por regla)\n" + ("\n".join(f"- [{x['gravedad']}] {x['clase'].replace('_', ' ')}: {x['detalle']}" for x in hallazgos) if hallazgos else "Sin discrepancias entre el dossier y el registro de la hipotesis.")
    art_id = guardar_artefacto(e, h["investigacionId"], f"Dossier para el laboratorio: {h['titulo'][:80]}", "dossier", contenido, f"Version {h.get('version', 1)} de la hipotesis; {len(h.get('bloqueos', []))} bloqueos; revision del registro: {len(hallazgos)} hallazgos", corrida["iteracionActual"] if corrida else h["iteracion"], ahora, procedencia={"mensajes": {"hipotesis": h["id"], "version": h.get("version", 1)}, "revision": {"hallazgos": hallazgos, "porRegla": len(hallazgos), "juez": None, "resumen": RR.resumen_revision(hallazgos)}})
    h["dossierArtefactoId"] = art_id
    h["procedencia"]["registro"].append(f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} dossier generado por {quien}")
    con_evento(e, h["investigacionId"], "hipotesis_decidida", f"Dossier para el laboratorio generado: {h['titulo'][:80]}", f"#/investigaciones/{h['investigacionId']}/artefactos/{art_id}", ahora)
    return art_id


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
    h["procedencia"]["registro"] = [f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} hipotesis humana añadida por {quien}"]
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
        art_id = guardar_artefacto(e, h["investigacionId"], f"Prerregistro: {h['titulo'][:80]}", "informe", contenido, f"Congelado el {datetime.fromtimestamp(ahora / 1000).strftime('%d/%m/%Y %H:%M')} al asignarlo a {lab}", corrida["iteracionActual"] if corrida else h["iteracion"], ahora, procedencia={"mensajes": {"hipotesis": h["id"], "version": h.get("version", 1), "decisiones": [d["id"] for d in e.get("decisiones", []) if d.get("hipotesisId") == h["id"]][:30]}, "entorno": {"arnes": corrida.get("arnes") if corrida else None}})
        x["prerregistradoEn"] = ahora
        x["prerregistroArtefactoId"] = art_id
        x["versionPrerregistrada"] = h.get("version", 1)  # el resultado probara esta version
        h["procedencia"]["registro"].append(f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} prerregistro congelado al asignar a {lab} (version {h.get('version', 1)})")
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
        f"Congelado el {datetime.fromtimestamp(ahora / 1000).strftime('%d/%m/%Y %H:%M')}. Asignado a: {laboratorio}. Hipotesis {h['id']} version {h.get('version', 1)}, iteracion {h['iteracion']}, prerregistrada el {datetime.fromtimestamp((h.get('prerregistradaEn') or h.get('creadaEn') or ahora) / 1000).strftime('%d/%m/%Y')}. El resultado del laboratorio probara esta version; si la hipotesis cambia despues, se comprobara la compatibilidad.",
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
        f"Diseño: {c['diseno']}",
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
    if x.get("controles") or x.get("tamanoMuestral") or x.get("alternativa"):
        lineas += ["", "## Controles, tamaño muestral y alternativa", f"Controles: {x.get('controles') or 'no declarados'}", f"Tamaño muestral: {x.get('tamanoMuestral') or 'no declarado'}", f"Explicacion alternativa y como se distingue: {x.get('alternativa') or 'no declarada'}"]
    if x.get("decisionQueCambia"):
        lineas += ["", "## Que decision cambia con el resultado", x["decisionQueCambia"]]
    if x.get("analisisPedido"):
        lineas += ["", "## Analisis sobre datos existentes", x["analisisPedido"]]
    if k:
        lineas += ["", "## Estado de la evidencia al prerregistrar", f"Certeza: {k.get('certeza')}. Direccion: {k.get('direccion')}.", k.get("enunciado", ""), f"Subiria la certeza si: {k.get('subiria', '')}", f"Bajaria si: {k.get('bajaria', '')}"]
    if arnes:
        lineas += ["", "## Version de Rosa", f"Commit {arnes.get('commit')}, firmas {arnes.get('firmas')}, programas optimizados: {arnes.get('optimizados')}."]
    lineas += ["", "Lo que se analice fuera de este registro se reporta como exploratorio, separado de lo prerregistrado."]
    return "\n".join(lineas)


CAMPOS_ENMENDABLES = ("protocolo", "ensayo", "controles", "tamanoMuestral", "confirma", "refuta", "analisisPedido")


def enmendar_experimento(e: Estado, hipotesis_id: str, campo: str, despues: str, motivo: str, quien: str, ahora: int) -> bool:
    """Una enmienda fechada del prerregistro (plan completo, seccion 3): se
    puede cambiar el protocolo o los criterios despues de congelarlos, pero
    queda escrito que, cuando, quien y por que, con el texto anterior al
    lado. Sin fecha de prerregistro no hay nada que enmendar: se edita. Con
    datos ya evaluados no se enmienda: los criterios ya se aplicaron."""
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h or not h.get("experimento") or campo not in CAMPOS_ENMENDABLES:
        return False
    x = h["experimento"]
    if not x.get("prerregistradoEn") or x.get("resultado"):
        return False
    nuevo, razon = despues.strip(), motivo.strip()
    if not nuevo or not razon or nuevo == (x.get(campo) or ""):
        return False
    x.setdefault("enmiendas", []).append({"fecha": ahora, "quien": quien.strip() or "persona", "campo": campo, "antes": x.get(campo) or "", "despues": nuevo, "motivo": razon})
    x[campo] = nuevo
    h["procedencia"]["registro"].append(f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} enmienda {len(x['enmiendas'])} del prerregistro por {quien}: {campo} ({razon[:80]})")
    con_evento(e, h["investigacionId"], "hipotesis_decidida", f"Enmienda {len(x['enmiendas'])} del prerregistro ({campo}): {h['titulo'][:80]}", f"#/investigaciones/{h['investigacionId']}/hipotesis/{h['id']}", ahora)
    return True


def registrar_protocolo_real(e: Estado, hipotesis_id: str, protocolo_real: dict, quien: str, ahora: int) -> bool:
    """Lo que el laboratorio hizo de verdad, separado de lo que se planeo:
    protocolo ejecutado, desviaciones respecto al prerregistro e identidad de
    las muestras (lote, linea celular, cohorte, fechas). El juez lo lee al
    evaluar los datos: una desviacion que toca el criterio convierte el
    resultado en fallo tecnico o lo limita, no lo maquilla."""
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h or not h.get("experimento") or not isinstance(protocolo_real, dict):
        return False
    x = h["experimento"]
    if x.get("estado") == "propuesto":
        return False
    texto = str(protocolo_real.get("texto", "")).strip()
    if not texto:
        return False
    x["protocoloReal"] = {"texto": texto[:4000], "desviaciones": str(protocolo_real.get("desviaciones", "")).strip()[:2000], "identidadMuestras": str(protocolo_real.get("identidadMuestras", "")).strip()[:2000], "registradoEn": ahora, "quien": quien.strip() or "persona"}
    h["procedencia"]["registro"].append(f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} protocolo real registrado por {quien}" + ("; con desviaciones" if x["protocoloReal"]["desviaciones"] else "; sin desviaciones declaradas"))
    if x.get("resultado") and x.get("ficheroDatos"):
        # Si los datos ya se evaluaron, el protocolo real cambia lo que el juez
        # leyo: se vuelve a evaluar contra el prerregistro con esta informacion.
        x.pop("resultado", None)
        h.pop("_resultadoEvaluado", None)
    return True


def texto_protocolo_real(x: dict) -> str:
    """El bloque que se le pasa al juez junto al prerregistro."""
    pr = x.get("protocoloReal")
    partes = []
    if pr:
        partes.append(f"PROTOCOLO REALMENTE EJECUTADO (registrado por {pr.get('quien')}):\n{pr.get('texto')}")
        partes.append("DESVIACIONES RESPECTO AL PRERREGISTRO: " + (pr.get("desviaciones") or "ninguna declarada"))
        partes.append("IDENTIDAD DE LAS MUESTRAS: " + (pr.get("identidadMuestras") or "no declarada"))
    else:
        partes.append("PROTOCOLO REALMENTE EJECUTADO: no registrado (asumir el prerregistrado y decirlo en limitaciones)")
    if x.get("enmiendas"):
        partes.append("ENMIENDAS FECHADAS DEL PRERREGISTRO:\n" + "\n".join(f"- {datetime.fromtimestamp(en['fecha'] / 1000).strftime('%d/%m/%Y')} {en['quien']}, {en['campo']}: '{en['antes'][:160]}' pasa a '{en['despues'][:160]}'. Motivo: {en['motivo'][:160]}" for en in x["enmiendas"]))
    return "\n\n".join(partes)


def registrar_datos_experimento(e: Estado, hipotesis_id: str, fichero: str, analisis: str) -> bool:
    h = _buscar(e["hipotesis"], hipotesis_id)
    if not h or not fichero.strip() or not h["experimento"]:
        return False
    h["experimento"]["ficheroDatos"] = fichero.strip()
    h["experimento"]["analisisPedido"] = analisis.strip()
    h["experimento"]["estado"] = "datos_recibidos"
    h["experimento"].pop("resultado", None)
    h.pop("_resultadoEvaluado", None)  # el bucle evalua los datos contra el prerregistro
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


def inyectar_debilidad(e: Estado, corrida_id: str, debilidad_id: str, quien: str = "Investigadora", ahora: int | None = None) -> bool:
    """Inyectar una debilidad como criterio de revision cambia como razona
    Rosa: es un cambio de nivel 2 que la persona promueve directamente al
    pulsar el boton, y queda en el registro de aprendizaje."""
    c = corrida_de(e, corrida_id)
    if not c:
        return False
    ahora = ahora if ahora is not None else P.ahora_ms()
    for m in c["metaRevisiones"]:
        for d in m["debilidades"]:
            if d["id"] == debilidad_id:
                if d["inyectada"]:
                    return False
                d["inyectada"] = True
                if d["texto"] not in e["criteriosRevision"]:
                    e["criteriosRevision"].append(d["texto"])
                existente = next((x for x in e.get("aprendizaje", []) if x["origen"] == f"debilidad:{debilidad_id}"), None)
                if existente:
                    existente.update(estado="promovido", resueltoEn=ahora, resueltoPor=quien)
                else:
                    e.setdefault("aprendizaje", []).append(P.nuevo_cambio_aprendizaje(c["investigacionId"], 2, "criterio", d["texto"], f"debilidad:{debilidad_id}", "promovido", quien, ahora))
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
        # Que parte de la condicion mide Rosa y que parte decide una persona.
        "condicionParadaAutomatizada": PARADA.partes_automatizadas(t("condicionParada")),
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
        "mision": None,
        "puertaReproduccion": P.puerta_reproduccion(),
    }
    mision = datos.get("mision")
    if isinstance(mision, dict) and any(str(mision.get(k, "")).strip() for k in ("poblacion", "etapa", "mecanismo", "tipoIntervencion")):
        # La persona ya escribio la mision al crear: queda aprobada por ella.
        inv["mision"] = P.mision_vacia()
        e["investigaciones"].append(inv)
        aprobar_mision(e, inv["id"], mision, str(datos.get("quien") or "Investigadora"), ahora)
        return inv["id"] if not datos.get("heredarModeloDe") else _heredar(e, inv, datos)
    e["investigaciones"].append(inv)
    return _heredar(e, inv, datos)


def _heredar(e: Estado, inv: dict, datos: dict) -> str:
    heredar = datos.get("heredarModeloDe")
    if heredar:
        for h in [x for x in e["hechos"] if x["investigacionId"] == heredar]:
            e["hechos"].append({**copy.deepcopy(h), "id": f"{h['id']}-{inv['id']}", "investigacionId": inv["id"]})
    return inv["id"]


def bifurcar_investigacion(e: Estado, investigacion_id: str, motivo: str, ahora: int, id_: str | None = None) -> str | bool:
    origen = _buscar(e["investigaciones"], investigacion_id)
    if not origen:
        return False
    nuevo = id_ or P.nuevo_id("inv")
    # Copia profunda: la puerta, la mision con sus areas, la memoria y los datasets
    # de la rama no pueden ser los mismos objetos que los del origen (los reducers
    # mutan en sitio y el cambio se persistiria en las dos investigaciones).
    rama = {
        **copy.deepcopy(origen),
        "id": nuevo,
        # Lo que la persona escribe al bifurcar es el nombre de la rama (y su
        # motivo): asi la rama se distingue de la original a primera vista.
        "titulo": motivo.strip()[:90] if motivo.strip() else f"{origen['titulo']} (rama)",
        "objetivo": origen["objetivo"] if not motivo.strip() else f"{origen['objetivo']}\n\nRama de '{origen['titulo']}': {motivo.strip()}",
        "creadaEn": ahora,
        "ramaDe": origen["id"],
        "vigilarLiteraturaHasta": None,
        "preguntasABases": [],
    }
    e["investigaciones"].append(rama)
    for h in [x for x in e["hechos"] if x["investigacionId"] == investigacion_id]:
        e["hechos"].append({**copy.deepcopy(h), "id": f"{h['id']}-{nuevo}", "investigacionId": nuevo})
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


def anadir_dataset(e: Estado, investigacion_id: str, dataset: dict, id_: str | None = None) -> str | bool:
    inv = _buscar(e["investigaciones"], investigacion_id)
    if not inv or not str(dataset.get("nombre", "")).strip():
        return False
    ds = {**dataset, "id": id_ or P.nuevo_id("ds"), "estado": "pendiente"}
    ds.setdefault("procedencia", None)
    for k in ("columnasSinDiccionario", "valoresCentinela", "nombresDuplicados"):
        ds[k] = int(ds.get(k) or 0)
    inv["datasets"].append(ds)
    return ds["id"]


def actualizar_procedencia_dataset(e: Estado, investigacion_id: str, dataset_id: str, procedencia: dict) -> bool:
    """La persona completa el libro de procedencia: origen, version,
    licencia, permisos, uso de IA autorizado, sintetico, cohorte, clase. El
    hash y el diccionario los fija el servidor al subir el fichero y aqui no
    se pueden cambiar."""
    ds = _dataset(e, investigacion_id, dataset_id)
    if not ds or not isinstance(procedencia, dict):
        return False
    base = ds.get("procedencia") or P.procedencia_dataset_vacia()
    editables = ("origen", "version", "licencia", "permisos", "cohorte")
    nueva = {**base, **{k: str(procedencia[k]).strip() for k in editables if k in procedencia}}
    if procedencia.get("usoIAAutorizado") in ("si", "no", "desconocido"):
        nueva["usoIAAutorizado"] = procedencia["usoIAAutorizado"]
    if procedencia.get("acceso") in ("abierto", "controlado", "colaboracion", "propio"):
        nueva["acceso"] = procedencia["acceso"]
    if "permiteLlmTerceros" in procedencia:
        nueva["permiteLlmTerceros"] = bool(procedencia["permiteLlmTerceros"])
    if "restriccionIA" in procedencia:
        nueva["restriccionIA"] = str(procedencia["restriccionIA"]).strip()[:400]
    if "sintetico" in procedencia:
        nueva["sintetico"] = bool(procedencia["sintetico"])
    if procedencia.get("clase") in politicas.CLASES_EVIDENCIA:
        nueva["clase"] = procedencia["clase"]
    if procedencia.get("fechaObtencion") is None or isinstance(procedencia.get("fechaObtencion"), (int, float)):
        nueva["fechaObtencion"] = procedencia.get("fechaObtencion", base["fechaObtencion"])
    if isinstance(procedencia.get("diccionario"), list):
        nueva["diccionario"] = [{"columna": str(c.get("columna", "")), "descripcion": str(c.get("descripcion", "")).strip(), "tipo": c.get("tipo", "texto"), "unidad": str(c.get("unidad", "")).strip()} for c in procedencia["diccionario"] if isinstance(c, dict) and str(c.get("columna", ""))]
        ds["columnasSinDiccionario"] = sum(1 for c in nueva["diccionario"] if not c["descripcion"])
    ds["procedencia"] = nueva
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
    proc = ds.get("procedencia")
    # Un dataset con fichero no se aprueba sin libro de procedencia: origen,
    # licencia y si el uso con IA esta autorizado. "Desconocido" no aprueba.
    if decision == "aprobado" and proc and proc.get("hash") and (not proc.get("origen") or not proc.get("licencia") or proc.get("usoIAAutorizado") != "si"):
        return False
    ds["estado"] = decision
    for h in e["hipotesis"]:
        if h["investigacionId"] == investigacion_id:
            recalcular_bloqueos(e, h)
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


def procedencia_artefacto(**partes: Any) -> dict[str, Any]:
    """Las cinco pestanas de procedencia de una version (como en Claude
    Science): mensajes (de donde salio: pistas, decisiones, eventos), codigo
    (el script que la produjo), registroEjecucion (lo que de verdad corrio:
    ejecuciones con estado y cifras), entorno (imagen y versiones de
    paquetes, modelos usados) y revision (los hallazgos del revisor). Lo que
    no aplica queda None, no se inventa."""
    base = {"mensajes": None, "codigo": None, "registroEjecucion": None, "entorno": None, "revision": None}
    base.update({k: v for k, v in partes.items() if k in base})
    return base


def guardar_artefacto(e: Estado, investigacion_id: str, nombre: str, tipo: str, contenido: str, resumen: str, iteracion: int, ahora: int, id_: str | None = None, procedencia: dict | None = None) -> str:
    """Mismo nombre en la misma investigacion = version nueva (no se
    sobrescribe). Cada version lleva su procedencia en cinco pestanas."""
    version = {"n": 1, "creadaEn": ahora, "resumen": resumen, "contenido": contenido, "iteracion": iteracion, "procedencia": procedencia_artefacto(**(procedencia or {}))}
    existente = next((a for a in e["artefactos"] if a["investigacionId"] == investigacion_id and a["nombre"] == nombre), None)
    if existente:
        version["n"] = len(existente["versiones"]) + 1
        existente["versiones"].append(version)
        return existente["id"]
    nuevo = id_ or P.nuevo_id("art")
    e["artefactos"].append({"id": nuevo, "investigacionId": investigacion_id, "nombre": nombre, "tipo": tipo, "destacado": False, "versiones": [version]})
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


def borrar_criterio(e: Estado, indice: int | None = None, texto: str | None = None) -> bool:
    """Con `texto` se borra la primera coincidencia exacta; la posicion es el
    respaldo. Dos pestanas que borran a la vez no se llevan un criterio ajeno."""
    lista = e["criteriosRevision"]
    if texto is not None:
        if texto not in lista:
            return False
        lista.remove(texto)
        return True
    if indice is None or not (0 <= indice < len(lista)):
        return False
    del lista[indice]
    return True


def actualizar_avisos(e: Estado, avisos: dict) -> bool:
    """Se normaliza campo a campo desde la plantilla: un cuerpo malformado no
    puede romper la interfaz de todos los navegadores conectados."""
    if not isinstance(avisos, dict):
        return False
    base = P.estado_inicial()["avisos"]
    correo = avisos.get("correo") if isinstance(avisos.get("correo"), dict) else {}
    slack = avisos.get("slack") if isinstance(avisos.get("slack"), dict) else {}
    cuando = avisos.get("cuando") if isinstance(avisos.get("cuando"), dict) else {}
    e["avisos"] = {
        "correo": {"activo": bool(correo.get("activo", base["correo"]["activo"])), "direccion": str(correo.get("direccion", base["correo"]["direccion"]))[:200]},
        "slack": {"activo": bool(slack.get("activo", base["slack"]["activo"])), "canal": str(slack.get("canal", base["slack"]["canal"]))[:200]},
        "cuando": {k: bool(cuando.get(k, v)) for k, v in base["cuando"].items()},
    }
    return True


def actualizar_politica_esperas(e: Estado, politica: dict) -> bool:
    if not isinstance(politica, dict):
        return False
    horas = politica.get("horas")
    if not isinstance(horas, (int, float)) or isinstance(horas, bool) or horas <= 0 or horas > 24 * 365:
        return False
    accion = politica.get("accion", "recordar")
    if accion not in ("recordar", "escalar", "detener", "continuar"):
        return False
    e["politicaEsperas"] = {"horas": horas, "accion": accion, "escalarA": str(politica.get("escalarA", "")).strip()[:200]}
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
    if inv.get("estado") == "cerrada":
        con_evento(e, investigacion_id, "corrida_estado", "Investigacion reabierta al crear una corrida nueva", f"#/investigaciones/{investigacion_id}/corrida", ahora)
    inv["estado"] = "activa"
    con_evento(e, investigacion_id, "corrida_estado", f"Corrida {c['numero']} creada; Rosa propone el plan de la iteracion 1", f"#/investigaciones/{investigacion_id}/corrida", ahora)
    return c["id"]
