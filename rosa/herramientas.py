"""Herramientas para el modelo (el "bucle de herramientas" de Claude Science):
los conectores del catalogo, la busqueda en el proyecto (ProjectSearch) y la
lectura del modelo de mundo, envueltos como `dspy.Tool` para un `dspy.ReAct`
acotado. Cada llamada a un conector deja su registro de consulta; el
resultado de la pregunta guarda esos registros junto a la respuesta, para
que se vea de donde salio cada dato.

ReAct es el patron "razonar y actuar": el modelo elige una herramienta,
lee el resultado, y repite hasta responder o agotar las iteraciones. Aqui
esta acotado a pocas iteraciones y solo a herramientas de lectura.
"""

from __future__ import annotations

import json
import re
from typing import Any

import dspy

from rosa import conectores as CON
from rosa.conectores.base import PERMISOS

MAX_ITERACIONES = 6
MAX_TEXTO_HERRAMIENTA = 3500


class PreguntarConHerramientas(dspy.Signature):
    """Responder una pregunta de investigacion consultando bases publicas y el
    propio proyecto con las herramientas disponibles. Reglas: usar una herramienta
    cuando la respuesta dependa de un dato de una base o del proyecto; nunca
    afirmar un dato que ninguna herramienta devolvio; si una herramienta no
    responde, decir "no pude comprobar", no "no existe"; separar lo que dicen las
    bases de lo que se infiere; nombrar la herramienta y el identificador detras
    de cada dato; escribir en espanol llano con los terminos tecnicos explicados
    la primera vez. Si con las herramientas no alcanza, decirlo y proponer que
    haria falta."""

    pregunta: str = dspy.InputField()
    contexto: str = dspy.InputField(desc="La mision y la memoria del proyecto")
    respuesta: str = dspy.OutputField(desc="Respuesta en llano con las herramientas e identificadores detras de cada dato")
    limites: str = dspy.OutputField(desc="Lo que no se pudo comprobar o queda fuera de lo que las bases saben")


def _recortar(obj: Any, maximo: int = MAX_TEXTO_HERRAMIENTA) -> str:
    t = json.dumps(obj, ensure_ascii=False, default=str)
    return t if len(t) <= maximo else t[:maximo] + " ... [recortado]"


def _permitido(nombre: str, origen: str) -> bool:
    nivel = PERMISOS.get(nombre, "permitir")
    if nivel == "bloquear":
        return False
    if nivel == "solo_persona":
        return origen == "persona"
    return True


def herramientas(estado: dict[str, Any], investigacion_id: str, registro: list[dict[str, Any]], origen: str = "persona", solo: list[str] | None = None) -> list[dspy.Tool]:
    """Las herramientas para un ReAct: cada conector disponible y permitido,
    mas la busqueda en el proyecto y el modelo de mundo. `registro` recibe
    cada consulta hecha."""
    tools: list[dspy.Tool] = []
    for nombre, c in CON.REGISTRO.items():
        if c.estado != "disponible" or not _permitido(nombre, origen) or (solo and nombre not in solo):
            continue

        def hacer(nombre=nombre):
            async def fn(**kw: str) -> str:
                reg, datos = await CON.consultar(nombre, resumen=f"pregunta: {nombre}", **{k: str(v) for k, v in kw.items()})
                registro.append(reg)
                if reg["error"]:
                    return f"NO PUDE COMPROBAR ({reg['fuente']}): {reg['error']}"
                return _recortar({"fuente": reg["fuente"], "n": reg["n"], "invariante": reg["invariante"], "datos": datos})

            return fn

        props = c.esquema.get("properties", {})
        tools.append(dspy.Tool(hacer(), name=nombre, desc=f"{c.fuente}: {c.descripcion}. Aporta: {c.aporta}. Licencia: {c.licencia}.", args={k: {"type": "string", "description": v.get("description", "")} for k, v in props.items()}, arg_types={k: str for k in props}, arg_desc={k: v.get("description", "") for k, v in props.items()}))

    async def buscar_en_proyecto(consulta: str) -> str:
        return _recortar(buscar_proyecto(estado, investigacion_id, consulta))

    async def leer_modelo_de_mundo(tema: str) -> str:
        hechos = [h for h in estado.get("hechos", []) if h["investigacionId"] == investigacion_id and h.get("estado") in ("sabido", "abierto")]
        t = tema.lower()
        hits = [h for h in hechos if t in (h.get("enunciado", "") + " " + h.get("tema", "")).lower()][:12]
        return _recortar([{"id": h["id"], "tipo": h.get("tipo"), "estado": h.get("estado"), "enunciado": h.get("enunciado"), "fuentes": [p.get("referencia") for p in h.get("procedencia", [])][:3]} for h in hits] or "Sin hechos sobre ese tema en el modelo de mundo")

    tools.append(dspy.Tool(buscar_en_proyecto, name="buscar_en_proyecto", desc="Busca en el propio proyecto: hipotesis, hechos, artefactos, decisiones, fuentes y datasets de esta investigacion. Usar antes de preguntar a una persona por algo que ya esta decidido.", args={"consulta": {"type": "string", "description": "Palabras del dominio, un identificador o una frase"}}, arg_types={"consulta": str}))
    tools.append(dspy.Tool(leer_modelo_de_mundo, name="leer_modelo_de_mundo", desc="Los hechos sabidos y abiertos del modelo de mundo sobre un tema, con sus fuentes.", args={"tema": {"type": "string", "description": "Tema o biomarcador"}}, arg_types={"tema": str}))
    return tools


def buscar_proyecto(estado: dict[str, Any], investigacion_id: str, consulta: str, maximo: int = 12) -> list[dict[str, Any]]:
    """ProjectSearch: referencias y fragmentos, no instrucciones. Distingue
    decisiones de personas de propuestas de Rosa."""
    palabras = [p for p in re.split(r"[^a-z0-9áéíóúñ]+", consulta.lower()) if len(p) > 2]
    if not palabras:
        return []

    def punt(texto: str) -> int:
        t = (texto or "").lower()
        return sum(1 for p in palabras if p in t)

    hits: list[dict[str, Any]] = []
    for h in estado.get("hipotesis", []):
        if h["investigacionId"] != investigacion_id:
            continue
        p = punt(h.get("titulo", "") + " " + h.get("enunciado", ""))
        if p:
            hits.append({"tipo": "hipotesis", "id": h["id"], "puntos": p, "texto": h["titulo"][:140], "estado": h.get("estado"), "decision": h.get("decisionKiller"), "quien": h.get("origen")})
    for hch in estado.get("hechos", []):
        if hch["investigacionId"] != investigacion_id:
            continue
        p = punt(hch.get("enunciado", ""))
        if p:
            hits.append({"tipo": "hecho", "id": hch["id"], "puntos": p, "texto": hch["enunciado"][:160], "estado": hch.get("estado")})
    for a in estado.get("artefactos", []):
        if a["investigacionId"] != investigacion_id:
            continue
        ult = a["versiones"][-1] if a.get("versiones") else {}
        p = punt(a.get("nombre", "") + " " + ult.get("resumen", "") + " " + ult.get("contenido", "")[:3000])
        if p:
            hits.append({"tipo": "artefacto", "id": a["id"], "puntos": p, "texto": f"{a['nombre']} (version {ult.get('n')})", "estado": a.get("tipo")})
    for d in estado.get("decisiones", []):
        if d.get("investigacionId") != investigacion_id:
            continue
        p = punt(d.get("motivo", "") + " " + d.get("decision", ""))
        if p:
            hits.append({"tipo": "decision", "id": d["id"], "puntos": p, "texto": f"{d.get('etapa')}: {d.get('decision')} ({d.get('motivo', '')[:100]})", "quien": d.get("quien"), "es_de_persona": d.get("etapa") == "persona"})
    for inv in estado.get("investigaciones", []):
        if inv["id"] != investigacion_id:
            continue
        for ds in inv.get("datasets", []):
            p = punt(ds.get("nombre", "") + " " + ds.get("descripcion", ""))
            if p:
                hits.append({"tipo": "dataset", "id": ds["id"], "puntos": p, "texto": ds["nombre"][:140], "estado": ds.get("estado")})
        for m in inv.get("memoria", []) or []:
            p = punt(m.get("texto", ""))
            if p:
                hits.append({"tipo": "memoria", "id": m["id"], "puntos": p, "texto": m["texto"][:160], "quien": m.get("quien")})
    hits.sort(key=lambda x: -x["puntos"])
    return hits[:maximo]


async def preguntar(programas_lm: dspy.LM, estado: dict[str, Any], investigacion_id: str, pregunta: str, contexto: str, origen: str = "persona") -> dict[str, Any]:
    """Una pregunta con herramientas. Devuelve respuesta, limites, las
    herramientas usadas y los registros de consulta."""
    registro: list[dict[str, Any]] = []
    tools = herramientas(estado, investigacion_id, registro, origen=origen)
    agente = dspy.ReAct(PreguntarConHerramientas, tools=tools, max_iters=MAX_ITERACIONES)
    with dspy.context(lm=programas_lm):
        pred = await agente.acall(pregunta=pregunta, contexto=contexto)
    traj = getattr(pred, "trajectory", {}) or {}
    usadas = [v for k, v in traj.items() if k.startswith("tool_name_") and v not in ("finish",)]
    limpio = lambda t: t.replace("\u2014", ", ").replace("\u2013", "-").strip()  # noqa: E731  sin guiones largos en la interfaz
    return {"respuesta": limpio(pred.respuesta), "limites": limpio(pred.limites), "herramientas": usadas, "consultas": registro, "iteraciones": len([k for k in traj if k.startswith("tool_name_")])}
