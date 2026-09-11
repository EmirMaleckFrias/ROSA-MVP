"""Del estado al texto que leen los modelos.

Cada funcion toma partes del estado y las convierte en texto compacto y
numerado, para que las firmas puedan citar "afirmacion 7" o "hipotesis
hip-x". Nada de esto llama a un modelo.
"""

from __future__ import annotations

import re
from typing import Any


def modelo_de_mundo(hechos: list[dict[str, Any]], investigacion_id: str, maximo: int = 60) -> str:
    propios = [h for h in hechos if h["investigacionId"] == investigacion_id]
    if not propios:
        return "Vacio: es la primera iteracion. No hay hechos sabidos ni preguntas abiertas todavia."
    orden = {"abierto": 0, "sabido": 1, "descartado": 2}
    propios.sort(key=lambda h: (orden.get(h["estado"], 3), h["prioridad"]))
    lineas = []
    for h in propios[:maximo]:
        proc = "; ".join(f"{p['referencia']}{', pag. ' + str(p['pagina']) if p['pagina'] else ''}" for p in h["procedencia"][:3])
        extra = f" [descartado: {h['motivoDescarte']}]" if h["estado"] == "descartado" else ""
        lineas.append(f"- ({h['estado']}, prioridad {h['prioridad']}, {h['tipo']}, {h['tema']}) {h['enunciado']}{' <' + proc + '>' if proc else ''}{extra}")
    return "\n".join(lineas)


def preguntas_abiertas(hechos: list[dict[str, Any]], investigacion_id: str, objetivo: str, maximo: int = 8) -> str:
    abiertas = sorted([h for h in hechos if h["investigacionId"] == investigacion_id and h["estado"] == "abierto"], key=lambda h: h["prioridad"])
    if not abiertas:
        return f"Sin preguntas abiertas todavia. El objetivo es: {objetivo}"
    return "\n".join(f"{i + 1}. {h['enunciado']}" for i, h in enumerate(abiertas[:maximo]))


def afirmaciones_sostenidas(afirmaciones: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Texto numerado de las afirmaciones sostenidas o parciales, y la lista
    en ese mismo orden para resolver indices."""
    validas = [a for a in afirmaciones if a["veredicto"] in ("sostenida", "parcial")]
    lineas = [f"{i + 1}. ({a['tipo']}{', parcial' if a['veredicto'] == 'parcial' else ''}) {a['texto']} {a['cita']}" for i, a in enumerate(validas)]
    return ("\n".join(lineas) if lineas else "Ninguna afirmacion sostenida todavia."), validas


def hipotesis_existentes(hipotesis: list[dict[str, Any]], investigacion_id: str) -> str:
    propias = [h for h in hipotesis if h["investigacionId"] == investigacion_id]
    if not propias:
        return "Ninguna."
    lineas = []
    for h in propias:
        nota = ""
        if h["estado"] == "descartada":
            ult = next((r for r in reversed(h["revisiones"]) if r["accion"] == "descartada"), None)
            nota = f" motivo: {ult['nota']}" if ult else ""
        elif h["estado"] == "refinar":
            ult = next((r for r in reversed(h["revisiones"]) if r["accion"] == "refinar"), None)
            nota = f" pide refinar: {ult['nota']}" if ult else ""
        lineas.append(f"- {h['id']} [{h['estado']}, elo {h['elo']}] {h['titulo']}{nota}")
    return "\n".join(lineas)


def hipotesis_texto(h: dict[str, Any]) -> str:
    c = h["comprobacion"]
    return f"Titulo: {h['titulo']}\nEnunciado: {h['enunciado']}\nMecanismo: {h['mecanismo']}\nComprobacion: biomarcador {c['biomarcador']}; cohorte {c['cohorte']}; diseno {c['diseno']}\nCluster: {h['cluster']}"


def hipotesis_para_torneo(h: dict[str, Any]) -> str:
    afs = "\n".join(f"  - [{a['veredicto']}] {a['texto']} {a['cita']}" for a in h["afirmaciones"][:8])
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
    """Un paso editado o anadido por la investigadora no trae `tipo`; se
    infiere del titulo. Si no se reconoce, se trata como indicacion."""
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
        ("meta", "meta"),
        ("panorama", "meta"),
    ]:
        if clave in t:
            return tipo
    return "indicacion"


def terminos_clave(texto: str, maximo: int = 6) -> list[str]:
    """Palabras del dominio para consultas rapidas: siglas, genes, y palabras
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


def hipotesis_vivas(hipotesis: list[dict[str, Any]], investigacion_id: str, maximo: int = 8) -> str:
    """Las hipotesis en competencia con su estado de creencia, para que el
    plan y las consultas elijan lo que las discrimina: que evidencia subiria
    o bajaria su certeza, y de que dependen mas."""
    vivas = [h for h in hipotesis if h["investigacionId"] == investigacion_id and h["estado"] not in ("descartada",)]
    if not vivas:
        return "Ninguna todavia."
    vivas.sort(key=lambda h: -h["elo"])
    lineas = []
    for h in vivas[:maximo]:
        k = h.get("conclusion") or {}
        lineas.append(f"- {h['id']} [{h['estado']}, elo {h['elo']}, certeza {k.get('certeza', 'sin conclusion')}, direccion {k.get('direccion', '?')}] {h['titulo']}")
        if k:
            lineas.append(f"    depende mas de: {k.get('loMasFragil', '')}")
            lineas.append(f"    subiria si: {k.get('subiria', '')}")
            lineas.append(f"    bajaria si: {k.get('bajaria', '')}")
    return "\n".join(lineas)
