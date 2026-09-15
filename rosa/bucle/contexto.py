"""Del estado al texto que leen los modelos.

Cada función toma partes del estado y las convierte en texto compacto y
numerado, para que las firmas puedan citar "afirmación 7" o "hipótesis
hip-x". Nada de esto llama a un modelo, salvo `modelo_de_mundo_para`, que
pide un embedding al índice semántico para elegir qué hechos entran.

Dos reglas del 15 de septiembre de 2026, tras la corrida que juzgó la
relevancia con las preguntas de otra investigación:

- Conocimiento y criterio se separan. Los hechos heredados de otra
  investigación (`heredarModeloDe`, bifurcar) siguen siendo conocimiento y
  entran al modelo de mundo con la etiqueta de su origen; pero las preguntas
  abiertas heredadas no deciden qué se lee: el criterio de relevancia
  empieza por el objetivo y la pregunta de la corrida, y solo admite una
  pregunta heredada si nombra algo del objetivo.
- El árbol se lee bajo demanda. Con 140 hechos y un tope de 60 líneas, la
  mitad no llegaba nunca al modelo, y las que llegaban eran las de mayor
  prioridad, no las que venían al caso. `modelo_de_mundo_para` da un mapa
  del árbol (qué hay, por tema, cuánto es heredado) más los hechos más
  parecidos a lo que se está haciendo en ese paso, elegidos con el índice
  semántico; sin índice, cae al orden por prioridad de antes.
"""

from __future__ import annotations

import re
from typing import Any

from rosa import certeza as CERTEZA
from rosa import indice_semantico, politicas


def es_heredado(h: dict[str, Any]) -> bool:
    """Un hecho copiado de otra investigación (al crear esta con
    `heredarModeloDe` o al bifurcar): su id lleva el sufijo `-<id de la
    investigación de destino>`, así que contiene "-inv-"."""
    return "-inv-" in str(h.get("id", ""))


def origen_de_heredado(h: dict[str, Any], hechos_por_id: dict[str, dict[str, Any]], investigaciones: list[dict[str, Any]]) -> str | None:
    """Título de la investigación de la que viene un hecho heredado, siguiendo
    la cadena de copias hasta la original. None si no se puede seguir."""
    titulos = {i["id"]: i.get("titulo") or i["id"] for i in investigaciones}
    actual = h
    titulo = None
    for _ in range(8):
        sufijo = f"-{actual.get('investigacionId', '')}"
        if not sufijo.strip("-") or not str(actual.get("id", "")).endswith(sufijo):
            break
        original = hechos_por_id.get(str(actual["id"])[: -len(sufijo)])
        if not original:
            break
        titulo = titulos.get(original.get("investigacionId"), titulo)
        actual = original
    return titulo


def _linea_hecho(h: dict[str, Any], origen: str | None = None) -> str:
    proc = "; ".join(f"{p['referencia']}{', pág. ' + str(p['pagina']) if p['pagina'] else ''}" for p in h["procedencia"][:3])
    extra = f" [descartado: {h['motivoDescarte']}]" if h["estado"] == "descartado" else ""
    heredado = f" [heredado de «{origen}»]" if origen else (" [heredado de otra investigación]" if es_heredado(h) else "")
    return f"- ({h['estado']}, prioridad {h['prioridad']}, {h['tipo']}, {h['tema']}) {h['enunciado']}{' <' + proc + '>' if proc else ''}{extra}{heredado}"


def _ordenados(propios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    orden = {"abierto": 0, "sabido": 1, "descartado": 2}
    return sorted(propios, key=lambda h: (orden.get(h["estado"], 3), h["prioridad"]))


def mapa_del_modelo(propios: list[dict[str, Any]], hechos_por_id: dict[str, dict[str, Any]] | None = None, investigaciones: list[dict[str, Any]] | None = None) -> str:
    """Diez líneas que dicen qué hay en el árbol aunque no se enseñe entero:
    cuántos hechos por estado, los temas con más hechos y cuántos son
    heredados y de dónde."""
    if not propios:
        return "Modelo de mundo vacío."
    por_estado = {k: sum(1 for h in propios if h["estado"] == k) for k in ("sabido", "abierto", "descartado")}
    temas: dict[str, int] = {}
    for h in propios:
        temas[h.get("tema") or "sin tema"] = temas.get(h.get("tema") or "sin tema", 0) + 1
    lineas = [f"Mapa del modelo de mundo: {len(propios)} hechos ({por_estado['sabido']} sabidos, {por_estado['abierto']} preguntas abiertas, {por_estado['descartado']} descartados)."]
    lineas.append("Temas: " + "; ".join(f"{t} ({n})" for t, n in sorted(temas.items(), key=lambda x: -x[1])[:8]) + ".")
    heredados = [h for h in propios if es_heredado(h)]
    if heredados:
        origenes: dict[str, int] = {}
        for h in heredados:
            o = origen_de_heredado(h, hechos_por_id or {}, investigaciones or []) or "otra investigación"
            origenes[o] = origenes.get(o, 0) + 1
        lineas.append(f"Heredados: {len(heredados)} hechos vienen de " + "; ".join(f"«{o}» ({n})" for o, n in sorted(origenes.items(), key=lambda x: -x[1])) + ". Se midieron en la población de aquella investigación: valen como contexto, no como datos de esta.")
    return "\n".join(lineas)


def modelo_de_mundo(hechos: list[dict[str, Any]], investigacion_id: str, maximo: int = 60, investigaciones: list[dict[str, Any]] | None = None) -> str:
    """El modelo de mundo por prioridad (sin índice): mapa más las `máximo`
    primeras líneas por estado y prioridad. Los hechos heredados llevan su
    origen si se pasan las investigaciones."""
    propios = [h for h in hechos if h["investigacionId"] == investigacion_id]
    if not propios:
        return "Vacío: es la primera iteración. No hay hechos sabidos ni preguntas abiertas todavía."
    por_id = {h["id"]: h for h in hechos}
    elegidos = _ordenados(propios)[:maximo]
    cuerpo = "\n".join(_linea_hecho(h, origen_de_heredado(h, por_id, investigaciones) if investigaciones and es_heredado(h) else None) for h in elegidos)
    return mapa_del_modelo(propios, por_id, investigaciones) + f"\n\nHechos ({len(elegidos)} de {len(propios)}, por prioridad):\n" + cuerpo


NUCLEO_ABIERTAS = 10
NUCLEO_DESCARTADOS = 5


def nucleo_del_modelo(propios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lo que entra siempre, sea cual sea el paso: las preguntas abiertas
    propias de mayor prioridad y los hechos descartados con su motivo (para
    no volver a caer en lo mismo)."""
    abiertas = sorted([h for h in propios if h["estado"] == "abierto" and not es_heredado(h)], key=lambda h: h["prioridad"])[:NUCLEO_ABIERTAS]
    descartados = sorted([h for h in propios if h["estado"] == "descartado"], key=lambda h: h["prioridad"])[:NUCLEO_DESCARTADOS]
    return abiertas + descartados


async def modelo_de_mundo_para(almacen: Any, investigacion_id: str, consulta: str, maximo: int = 60) -> str:
    """El modelo de mundo para un paso concreto: el mapa del árbol, el núcleo
    (preguntas abiertas propias y descartados) y, hasta `máximo`, los hechos
    más parecidos a `consulta` según el índice semántico. Si el índice no
    está o falla, se completa por prioridad, como antes. Cuesta un embedding."""
    e = almacen.estado
    hechos = e["hechos"]
    propios = [h for h in hechos if h["investigacionId"] == investigacion_id]
    if not propios:
        return "Vacío: es la primera iteración. No hay hechos sabidos ni preguntas abiertas todavía."
    por_id = {h["id"]: h for h in hechos}
    investigaciones = e.get("investigaciones", [])
    elegidos = nucleo_del_modelo(propios)
    ya = {h["id"] for h in elegidos}
    modo = "por prioridad"
    if indice_semantico.disponible() and (consulta or "").strip():
        try:
            hits = await indice_semantico.de_almacen(almacen).buscar(consulta[:2000], k=maximo, investigacion_id=investigacion_id, tipos=("hecho",))
            for hit in hits:
                hid = str(hit["id"]).split(":", 1)[-1]
                if hid in por_id and hid not in ya and por_id[hid]["investigacionId"] == investigacion_id:
                    elegidos.append(por_id[hid])
                    ya.add(hid)
                if len(elegidos) >= maximo:
                    break
            modo = "por parecido con este paso"
        except Exception as ex:  # noqa: BLE001  el índice nunca tumba un paso
            modo = f"por prioridad; el índice semántico no respondió ({type(ex).__name__})"
    for h in _ordenados(propios):
        if len(elegidos) >= maximo:
            break
        if h["id"] not in ya:
            elegidos.append(h)
            ya.add(h["id"])
    cuerpo = "\n".join(_linea_hecho(h, origen_de_heredado(h, por_id, investigaciones) if es_heredado(h) else None) for h in elegidos)
    return mapa_del_modelo(propios, por_id, investigaciones) + f"\n\nHechos pertinentes ({len(elegidos)} de {len(propios)}, {modo}):\n" + cuerpo


def preguntas_abiertas(hechos: list[dict[str, Any]], investigacion_id: str, objetivo: str, maximo: int = 8, pregunta: str | None = None) -> str:
    """El criterio de relevancia: primero el objetivo y la pregunta de la
    corrida, después las preguntas abiertas propias por prioridad. Una
    pregunta heredada de otra investigación solo entra si nombra algo del
    objetivo (un nombre propio, o dos términos clave): el conocimiento
    heredado sirve para razonar, no para decidir qué se lee."""
    cabecera = f"Objetivo: {objetivo.strip()}" + (f"\nPregunta de esta corrida: {pregunta.strip()}" if pregunta and pregunta.strip() else "")
    abiertas = sorted([h for h in hechos if h["investigacionId"] == investigacion_id and h["estado"] == "abierto"], key=lambda h: h["prioridad"])
    propias = [h for h in abiertas if not es_heredado(h)]
    base = f"{objetivo} {pregunta or ''}"
    nombres = {n.lower() for n in nombres_propios(base)}
    terminos = {t.lower() for t in terminos_clave(base, maximo=30) if len(t) >= 5 and t.lower() not in nombres}

    def pertinente(h: dict[str, Any]) -> bool:
        t = h["enunciado"].lower()
        return any(n in t for n in nombres) or sum(x in t for x in terminos) >= 2

    heredadas = [h for h in abiertas if es_heredado(h) and pertinente(h)]
    elegidas = (propias + heredadas)[:maximo]
    if not elegidas:
        return cabecera + "\nSin preguntas abiertas propias todavía."
    return cabecera + "\nPreguntas abiertas:\n" + "\n".join(f"{i + 1}. {h['enunciado']}" + (" (heredada)" if es_heredado(h) else "") for i, h in enumerate(elegidas))


def terminos_registro(objetivo: str, pregunta: str | None = None, detalle: str = "", maximo: int = 3) -> list[str]:
    """Términos para ClinicalTrials.gov, que está en inglés: primero los
    nombres propios (fármacos, ensayos), después siglas y genes. Nunca
    palabras sueltas en castellano ("mantiene precedencia" dio 0 estudios)."""
    texto = " ".join(x for x in (objetivo, pregunta or "", detalle or "") if x)
    salida: list[str] = []

    def anadir(x: str) -> None:
        if x.lower() not in {v.lower() for v in salida} and not any(x.lower() in v.lower() for v in salida):
            salida.append(x)

    for n in nombres_propios(texto):
        anadir(n)
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", texto):
        if (tok.isupper() and len(tok) >= 3 and tok.lower() not in _GENERICAS) or (re.search(r"\d", tok) and re.search(r"[A-Za-z]", tok)):
            anadir(tok)
    return salida[:maximo]


def afirmaciones_sostenidas(afirmaciones: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Texto numerado de las afirmaciones sostenidas o parciales, y la lista
    en ese mismo orden para resolver índices."""
    validas = [a for a in afirmaciones if a["veredicto"] in ("sostenida", "parcial")]
    lineas = [f"{i + 1}. ({a['tipo']}{', parcial' if a['veredicto'] == 'parcial' else ''}) {a['texto']} {a['cita']}" for i, a in enumerate(validas)]
    return ("\n".join(lineas) if lineas else "Ninguna afirmación sostenida todavía."), validas


def hipotesis_existentes(hipotesis: list[dict[str, Any]], investigacion_id: str, maximo: int | None = None, con_descartadas: int | None = None) -> str:
    """Las hipótesis vivas de la investigación, por Elo, con tope; de las
    descartadas solo las últimas (su motivo evita repetirlas). Sin tope, el
    prompt del Killer crecia con cada iteración."""
    maximo = politicas.MAX_HIPOTESIS_EN_CONTEXTO if maximo is None else maximo
    con_descartadas = politicas.MAX_DESCARTADAS_EN_CONTEXTO if con_descartadas is None else con_descartadas
    propias = [h for h in hipotesis if h["investigacionId"] == investigacion_id]
    if not propias:
        return "Ninguna."
    vivas = sorted([h for h in propias if h["estado"] != "descartada"], key=lambda h: -h.get("elo", 0))[:maximo]
    descartadas = sorted([h for h in propias if h["estado"] == "descartada"], key=lambda h: -((h.get("revisiones") or [{}])[-1].get("fecha") or 0))[:con_descartadas]
    omitidas = len(propias) - len(vivas) - len(descartadas)
    lineas = []
    for h in vivas + descartadas:
        nota = ""
        if h["estado"] == "descartada":
            ult = next((r for r in reversed(h["revisiones"]) if r["accion"] == "descartada"), None)
            nota = f" motivo: {ult['nota']}" if ult else ""
        elif h["estado"] == "refinar":
            ult = next((r for r in reversed(h["revisiones"]) if r["accion"] == "refinar"), None)
            nota = f" pide refinar: {ult['nota']}" if ult else ""
        lineas.append(f"- {h['id']} [{h['estado']}, elo {h['elo']}] {h['titulo']}{nota}")
    if omitidas > 0:
        lineas.append(f"- ({omitidas} hipótesis más no se listan por tope de contexto)")
    return "\n".join(lineas)


def hipotesis_texto(h: dict[str, Any]) -> str:
    c = h["comprobacion"]
    return f"Título: {h['titulo']}\nEnunciado: {h['enunciado']}\nMecanismo: {h['mecanismo']}\nComprobacion: biomarcador {c['biomarcador']}; cohorte {c['cohorte']}; diseño {c['diseno']}\nCluster: {h['cluster']}"


def hipotesis_para_torneo(h: dict[str, Any]) -> str:
    afs = "\n".join(f"  - [{a['veredicto']}{', EN CONTRA' if a.get('relacion') == 'contradice' else (', indirecta' if a.get('relacion') == 'apoya_indirecta' else '')}] {a['texto']} {a['cita']}" for a in h["afirmaciones"][:8])
    sup = "\n".join(f"  - [{s['estado']}] {s['texto']}" for s in h["supuestos"][:6])
    return f"{hipotesis_texto(h)}\nAfirmaciones:\n{afs or '  (ninguna)'}\nSupuestos:\n{sup or '  (ninguno)'}\nRevisiones automaticas: " + "; ".join(f"{r['tipo']}: {r['resumen']}" for r in h["revisionesAutomaticas"] if r["estado"] != "pendiente")


def revisiones_humanas(h: dict[str, Any]) -> str:
    partes = []
    for r in h["revisionesHumanas"]:
        partes.append(f"{r['quien']}: supuestos cuestionados: {r['supuestosCuestionados']}; literatura que falta: {r['literaturaQueFalta']}; problema experimental: {r['problemaExperimental']}")
    for r in h["revisiones"]:
        if r["quien"] != "Rosa" and r["nota"]:
            partes.append(f"{r['quien']} ({r['accion']}): {r['nota']}")
    if h["relevancia"].get("votoHumano"):
        partes.append(f"Voto de relevancia humano: {h['relevancia']['votoHumano']}")
    return "\n".join(partes) if partes else "Ninguna."


def todas_las_hipotesis(hipotesis: list[dict[str, Any]], investigacion_id: str) -> str:
    propias = [h for h in hipotesis if h["investigacionId"] == investigacion_id]
    bloques = []
    for h in propias:
        revs = "; ".join(f"{r['quien']} {r['accion']}: {r['nota']}" for r in h["revisiones"][-4:])
        bloques.append(f"## {h['id']} [{h['estado']}, elo {h['elo']}, origen {h['origen']}]\n{hipotesis_para_torneo(h)}\nRevisiones: {revs}")
    return "\n\n".join(bloques) if bloques else "Ninguna."


def configuracion(inv: dict[str, Any]) -> str:
    c = inv["configuracion"]
    return f"Preferencias: {c['preferencias'] or 'ninguna'}\nAtributos deseados: {', '.join(c['atributos']) or 'ninguno'}\nRestricciones: {', '.join(c['restricciones']) or 'ninguna'}\nLimites de la investigacion: {'; '.join(inv['limites']) or 'ninguno'}"


def indicaciones_humanas(iteracion: dict[str, Any] | None, pendientes_solo: bool = False) -> str:
    if not iteracion:
        return "Ninguna."
    pasos = [p for p in iteracion["plan"] if p["indicacionHumana"] and (not pendientes_solo or p["estado"] in ("pendiente", "en_curso"))]
    return "\n".join(f"- {p['detalle']}" for p in pasos) if pasos else "Ninguna."


def plan_ejecutado(iteracion: dict[str, Any]) -> str:
    lineas = []
    for p in iteracion["plan"]:
        pistas = [x for x in iteracion["pistas"] if x["pasoId"] == p["id"]]
        res = "; ".join(f"{x['titulo']}: {x['resumen']}" for x in pistas)
        lineas.append(f"- [{p['estado']}] {p['titulo']}{' (fallo: ' + p['motivoFallo'] + ')' if p['motivoFallo'] else ''}{' | ' + res if res else ''}")
    return "\n".join(lineas)


def inferir_tipo_paso(paso: dict[str, Any]) -> str:
    """Un paso editado o añadido por la investigadora no trae `tipo`; se
    infiere del título. Si no se reconoce, se trata como indicación."""
    if paso.get("tipo"):
        return paso["tipo"]
    if paso.get("indicacionHumana"):
        return "indicacion"
    t = (paso.get("titulo", "") + " " + paso.get("detalle", "")).lower()
    for clave, tipo in [
        ("ensayo", "ensayos"),
        ("clinicaltrials", "ensayos"),
        ("literatura", "literatura"),
        ("buscar", "literatura"),
        ("pubmed", "literatura"),
        ("extra", "extraccion"),
        ("afirmaci", "extraccion"),
        ("verific", "verificacion"),
        ("noved", "novedad"),
        ("modelo de mundo", "modelo"),
        ("hechos", "modelo"),
        ("hipotesis", "hipotesis"),
        ("torneo", "hipotesis"),
        ("analisis", "analisis"),
        ("in silico", "analisis"),
        ("reproduc", "analisis"),
        ("meta", "meta"),
        ("panorama", "meta"),
    ]:
        if clave in t:
            return tipo
    return "indicacion"


def terminos_clave(texto: str, maximo: int = 6) -> list[str]:
    """Palabras del dominio para consultas rápidas: siglas, genes, y palabras
    largas que no sean conectores."""
    parar = {"sobre", "entre", "hasta", "desde", "para", "como", "cuando", "donde", "porque", "aunque", "mientras", "antes", "despues", "portadores", "pacientes", "personas", "estudio", "nivel", "niveles", "plasma", "cambio", "cambios"}
    vistos: list[str] = []
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", texto):
        if tok.lower() in parar or tok.lower() in {v.lower() for v in vistos}:
            continue
        if tok.isupper() or re.search(r"\d", tok) or len(tok) >= 7:
            vistos.append(tok)
        if len(vistos) >= maximo:
            break
    return vistos


_SUFIJOS_FARMACO = ("mab", "tide", "nib", "stat", "ast", "vir", "pril", "sartan", "gliptin", "mide")
_GENERICAS = {"alzheimer", "covid", "gwas", "pet", "mri", "csf", "adni", "apoe", "gfap", "nfl", "mci", "dcl", "cdr", "cdr-sb", "mmse", "sd", "ic", "hr", "or", "rr", "iqr", "usd", "fda", "ema", "oms", "who", "nia", "nih", "doi", "pmid", "rosa", "grade", "prisma", "pubmed"}


def nombres_propios(texto: str) -> list[str]:
    """Fármacos, ensayos y cohortes nombrados en un texto: lo que hay que
    buscar por nombre exacto porque la búsqueda por significado lo pierde.
    Reglas sin modelo: siglas con cifra o guion (INVOKE-2, AL002,
    TRAILBLAZER-ALZ 2), palabras en mayúsculas de cuatro letras o más que no
    son términos generales, fármacos por sufijo (-mab, -tide, -nib) y nombres
    de ensayo en minúscula pegados a "+" o "/" (evoke/evoke+)."""
    vistos: list[str] = []

    def anadir(x: str) -> None:
        x = x.strip(" ,.;:()")
        # Ni genéricas, ni repetidas, ni una sigla que es trozo de un nombre ya
        # recogido (INVOKE dentro de INVOKE-2); "evoke" y "evoke+" son dos ensayos.
        if len(x) < 3 or x.lower() in _GENERICAS or x.lower() in {v.lower() for v in vistos}:
            return
        if x.isupper() and any(x.lower() in v.lower() for v in vistos):
            return
        vistos.append(x)

    for m in re.finditer(r"[A-Z]{2,}[A-Z0-9\-]*\d[A-Z0-9\-]*(?:\s\d)?|[A-Z]{2,}-[A-Z]+(?:\s\d)?", texto or ""):
        anadir(m.group(0))
    for m in re.finditer(r"\b[A-Z]{4,}\b", texto or ""):
        anadir(m.group(0))
    for m in re.finditer(r"\b([a-z]{4,}\+)", texto or ""):
        anadir(m.group(1))
    for m in re.finditer(r"\b([a-z]{8,})\b", texto or ""):
        if any(m.group(1).endswith(s) for s in _SUFIJOS_FARMACO):
            anadir(m.group(1))
    for m in re.finditer(r"\b([a-z]{4,})/([a-z]{4,}\+?)", texto or ""):
        anadir(m.group(1))
        anadir(m.group(2))
    return vistos[:12]


def hipotesis_vivas(hipotesis: list[dict[str, Any]], investigacion_id: str, maximo: int = 8) -> str:
    """Las hipótesis en competencia con su estado de creencia, para que el
    plan y las consultas elijan lo que las discrimina: que evidencia subiría
    o bajaría su certeza, y de que dependen más."""
    vivas = [h for h in hipotesis if h["investigacionId"] == investigacion_id and h["estado"] not in ("descartada",)]
    if not vivas:
        return "Ninguna todavía."
    vivas.sort(key=lambda h: -h["elo"])
    lineas = []
    for h in vivas[:maximo]:
        k = h.get("conclusion") or {}
        lineas.append(f"- {h['id']} [{h['estado']}, elo {h['elo']}, certeza {k.get('certeza', 'sin conclusión')}, dirección {k.get('direccion', '?')}] {h['titulo']}")
        if k:
            lineas.append(f"    depende más de: {k.get('loMasFragil', '')}")
            lineas.append(f"    subiría si: {k.get('subiria', '')}")
            lineas.append(f"    bajaría si: {k.get('bajaria', '')}")
            escalera = k.get("escalera") or []
            cohortes = CERTEZA.cohortes_distintas(h)
            if escalera:
                lineas.append(f"    peldaño siguiente (por regla): para subir a {escalera[0]['a'].replace('_', ' ')} le falta {escalera[0]['falta']}. Cohortes distintas hoy: {len(cohortes)}" + (f" ({', '.join(cohortes)})" if cohortes else ""))
    return "\n".join(lineas)


def vivero_texto(inv: dict[str, Any], maximo: int = 8) -> str:
    """Las ideas del vivero para el plan, las consultas y el generador: no son
    hipótesis todavía; cada una dice qué le falta para nacer. Buscar esa
    evidencia es un paso tan válido como subir una hipótesis viva."""
    semillas = list(inv.get("vivero") or [])
    if not semillas:
        return "Vivero de ideas: vacío."
    semillas.sort(key=lambda s: -(s.get("actualizadaEn") or 0))
    lineas = [f"Vivero de ideas ({len(semillas)}; no son hipótesis todavía: nacen cuando su evidencia dé para certeza baja):"]
    for s in semillas[:maximo]:
        cohortes = CERTEZA.cohortes_distintas({"procedencia": {"fuentes": s.get("fuentes", [])}})
        lineas.append(f"- {s['id']} (desde la iteración {s.get('iteracion')}, {len(s.get('afirmaciones', []))} afirmaciones, cohortes: {', '.join(cohortes) or 'ninguna identificada'}) {s['titulo']}")
        lineas.append(f"    le falta: {s.get('falta', '')}")
    return "\n".join(lineas)


def resultado_experimental(h: dict[str, Any]) -> str:
    x = h.get("experimento") or {}
    r = x.get("resultado")
    if not r:
        return "Ninguno"
    cifras = "; ".join(f"{c['nombre']}: {c['valor']}" for c in r.get("cifras", []))
    return f"Veredicto contra el prerregistro: {r['veredicto']}. {r['resultado']} Motivo: {r['motivo']} Limitaciones: {r['limitaciones']} Cifras: {cifras or 'ninguna'}. Exploratorio (no prerregistrado): {r.get('exploratorio') or 'nada'}"
