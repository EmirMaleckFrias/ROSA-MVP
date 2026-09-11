"""Panel de prueba del Hypothesis Killer (plan completo, etapa E; ROSA2018,
etapa 6): hipotesis reales de Rosa a las que se les planta un fallo conocido
y se mide si el Killer lo detecta, si lo detecta la comprobacion correcta,
y cuanto se abstiene (suspender) o mata de mas en un conjunto gris.

Por que existe. El Killer decide por regla sobre comprobaciones, pero varias
de esas comprobaciones las hace el juez (Opus 5). Sin un panel con fallos
plantados no hay forma de saber que tasa de deteccion tiene, ni de ver si
una version nueva del prompt o del modelo lo empeora. Es la misma logica que
un conjunto de control: la respuesta correcta se conoce de antemano.

Uso: `uv run python -m rosa.evaluacion.panel_killer --hipotesis 5` con el
servidor corriendo (lee el estado por HTTP y escribe el resultado como
registro de evaluacion). Cuesta dinero: cada variante es una llamada al juez.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import dspy
import httpx

from rosa import config
from rosa import killer as K
from rosa.bucle import contexto as T
from rosa.gateway import modelos as cargar_modelos
from rosa.modulos.firmas import Programas

URL = f"http://{config.HOST}:{config.PUERTO}"

# Que decision se espera para cada fallo plantado y que comprobacion deberia
# fallar. `esperadas` admite varias decisiones cuando la regla las permite.
FALLOS: dict[str, dict[str, Any]] = {
    "original": {"esperadas": None, "comprobacion": None, "descripcion": "La hipotesis tal como esta: se compara con la decision real que tomo el Killer"},
    "cifra_alterada": {"esperadas": ("descartar_en_contexto",), "comprobacion": "fidelidad_evidencia", "descripcion": "Una cifra de una afirmacion multiplicada por 10 (o la direccion invertida) sin tocar el pasaje citado"},
    "prediccion_vaga": {"esperadas": ("reformular",), "comprobacion": "falsabilidad", "descripcion": "La prediccion falsable sustituida por una frase que ninguna observacion podria refutar"},
    "causal_sin_temporalidad": {"esperadas": ("reformular",), "comprobacion": "direccion_causal", "descripcion": "El enunciado afirma causalidad directa con evidencia solo transversal"},
    "misma_cohorte": {"esperadas": ("avanzar", "suspender"), "comprobacion": "independencia_cohortes", "descripcion": "Todas las fuentes marcadas como la misma cohorte: debe avanzar con aviso, no descartar"},
    "supuesto_contradicho": {"esperadas": ("descartar_en_contexto",), "comprobacion": "supuestos", "descripcion": "Un supuesto necesario marcado como contradicho por la evidencia"},
    "gris_parcial": {"esperadas": ("avanzar", "suspender", "reformular"), "comprobacion": None, "descripcion": "Un pasaje recortado que solo sostiene a medias la afirmacion (veredicto parcial): no debe descartar"},
}


def _con_numero(texto: str) -> re.Match | None:
    return re.search(r"(?<![\w.])(\d+(?:[.,]\d+)?)(?![\w])", texto)


def plantar(h: dict[str, Any], fallo: str) -> dict[str, Any] | None:
    """Una copia de la hipotesis con el fallo plantado, o None si no se puede
    plantar en esta hipotesis (por ejemplo, sin cifras que alterar)."""
    x = copy.deepcopy(h)
    t = x.get("tarjeta") or {}
    afs = x.get("afirmaciones", [])
    sostenidas = [a for a in afs if a.get("veredicto") in ("sostenida", "parcial")]
    if fallo == "original":
        return x
    if fallo == "cifra_alterada":
        for a in sostenidas:
            m = _con_numero(a["texto"])
            if m:
                v = float(m.group(1).replace(",", "."))
                nuevo = f"{v * 10:g}"
                a["texto"] = a["texto"][: m.start(1)] + nuevo + a["texto"][m.end(1) :]
                a["_plantado"] = f"cifra {m.group(1)} pasa a {nuevo}"
                return x
        for a in sostenidas:
            if K.direccion_de(a["texto"]) == "sube":
                a["texto"] = re.sub(r"\b(increas\w*|higher|elevat\w*|aument\w*|mayor|sube)\b", "decreased", a["texto"], count=1, flags=re.I)
                a["_plantado"] = "direccion invertida"
                return x
            if K.direccion_de(a["texto"]) == "baja":
                a["texto"] = re.sub(r"\b(decreas\w*|lower|reduc\w*|disminu\w*|menor|baja)\b", "increased", a["texto"], count=1, flags=re.I)
                a["_plantado"] = "direccion invertida"
                return x
        return None
    if fallo == "prediccion_vaga":
        if not t:
            return None
        t["prediccionFalsable"] = "El biomarcador estara relacionado de alguna manera con la progresion de la enfermedad en algunos pacientes"
        return x
    if fallo == "causal_sin_temporalidad":
        bio = (x.get("comprobacion") or {}).get("biomarcador") or t.get("diana") or "el biomarcador"
        x["enunciado"] = f"{bio} causa directamente el deterioro cognitivo en esta poblacion; no es un marcador sino el mecanismo. " + x["enunciado"]
        x["titulo"] = f"{bio} es la causa directa del deterioro"
        for a in afs:
            a["texto"] = re.sub(r"longitudinal|prospective|prospectivo|follow-up|seguimiento|baseline|preced\w*", "cross-sectional", a["texto"], flags=re.I)
        return x
    if fallo == "misma_cohorte":
        fuentes = x.get("procedencia", {}).get("fuentes", [])
        if len(fuentes) < 2:
            return None
        for f in fuentes:
            f["cohorte"] = "COHORTE-UNICA"
        for a in afs:
            a["cohorte"] = "COHORTE-UNICA"
        return x
    if fallo == "supuesto_contradicho":
        bio = (x.get("comprobacion") or {}).get("biomarcador") or t.get("diana") or "la medida"
        x.setdefault("supuestos", []).append({"id": "sup-plantado", "texto": f"{bio} se mide de forma comparable entre las cohortes citadas (misma plataforma y preanalitica)", "estado": "contradicho", "evidencia": "Las cohortes citadas usan plataformas distintas y no hay calibracion cruzada: las cifras no son comparables", "necesario": True})
        return x
    if fallo == "gris_parcial":
        for a in sostenidas:
            if a.get("fragmento") and len(a["fragmento"].split()) > 12:
                a["fragmento"] = " ".join(a["fragmento"].split()[:8]) + " ..."
                a["veredicto"] = "parcial"
                a["_plantado"] = "pasaje recortado, veredicto parcial"
                return x
        return None
    raise ValueError(fallo)


def _afs_texto(h: dict[str, Any]) -> str:
    return "\n".join(f"- [{a['veredicto']}, {a['tipo']}, clase {a.get('clase', 'literatura')}{', SINTETICO' if a.get('sintetico') else ''}{', cohorte ' + a['cohorte'] if a.get('cohorte') else ''}] {a['texto']} {a['cita']}" + (f"\n    Pasaje: \"{a['fragmento'][:240]}\"" if a.get("fragmento") else "") for a in h["afirmaciones"]) or "Ninguna"


def _mision_texto(inv: dict[str, Any]) -> str:
    from rosa.bucle.pasos import _texto_mision

    return _texto_mision(inv)


def juzgar(programas: Programas, juez: dspy.LM, e: dict[str, Any], h: dict[str, Any], volumen: dspy.LM | None = None) -> dict[str, Any]:
    """Una pasada del Killer sobre una hipotesis (copia local del estado):
    comprobaciones deterministas, el juez, fusion y decision por regla. Es el
    mismo camino que `pasos._killer`, sin escribir en el estado."""
    inv = next(i for i in e["investigaciones"] if i["id"] == h["investigacionId"])
    deterministas = K.comprobaciones_deterministas(h, e)
    t0 = time.time()
    pred = None
    ultimo: Exception | None = None
    # Mismo camino que Ctx.llamar: si el JSON largo del juez llega mal formado, se
    # reintenta una vez con el juez y despues con el modelo de volumen.
    for lm in (juez, juez, volumen or juez):
        try:
            with dspy.context(lm=lm):
                pred = _llamar_killer(programas, e, h, inv, deterministas)
            break
        except Exception as ex:  # noqa: BLE001
            ultimo = ex
            if not any(s_ in str(ex).lower() for s_ in ("parse", "json", "empty", "content")):
                raise
    if pred is None:
        raise RuntimeError(str(ultimo))
    rev = pred.revision
    return _resultado(rev, deterministas, h, juez, t0)


def _llamar_killer(programas: Programas, e: dict[str, Any], h: dict[str, Any], inv: dict[str, Any], deterministas: list[dict[str, str]]):
    if True:
        return programas.killer(
            objetivo=inv["objetivo"],
            mision=_mision_texto(inv),
            hipotesis=T.hipotesis_texto(h) + "\n" + K.texto_tarjeta(h),
            afirmaciones=_afs_texto(h),
            supuestos="\n".join(f"- [{s['estado']}] {s['texto']} ({s['evidencia']})" for s in h.get("supuestos", [])) or "Sin supuestos evaluados",
            modelo_de_mundo=T.modelo_de_mundo(e["hechos"], inv["id"], maximo=40) + "\n\nOtras hipotesis vivas:\n" + T.hipotesis_existentes([x for x in e["hipotesis"] if x["id"] != h["id"]], inv["id"]),
            comprobaciones_deterministas="\n".join(f"- {c['comprobacion']}: {c['resultado']}. {c['detalle']}" for c in deterministas),
            criterios_revision="\n".join(e["criteriosRevision"]),
        )


def _resultado(rev, deterministas: list[dict[str, str]], h: dict[str, Any], juez: dspy.LM, t0: float) -> dict[str, Any]:
    del_juez = [{"comprobacion": c.comprobacion, "resultado": c.resultado, "detalle": c.detalle} for c in rev.comprobaciones]
    comprobaciones = K.fusionar(deterministas, del_juez)
    if rev.supuesto_invalidante.strip() and any(s_.get("estado") == "contradicho" for s_ in h.get("supuestos", [])) and not any(c["comprobacion"] == "supuestos" and c["resultado"] == "falla" for c in comprobaciones):
        comprobaciones = [c for c in comprobaciones if c["comprobacion"] != "supuestos"] + [{"comprobacion": "supuestos", "resultado": "falla", "detalle": f"Supuesto invalidante: {rev.supuesto_invalidante[:200]}"}]
    tiene_prediccion = bool((h.get("tarjeta") or {}).get("prediccionFalsable")) and "no falsable" not in (h.get("tarjeta") or {}).get("prediccionFalsable", "").lower()
    decision, motivo = K.decidir(comprobaciones, tiene_prediccion, h.get("version", 1))
    uso = juez.history[-1].get("usage", {}) if juez.history else {}
    ent, sal = int(uso.get("prompt_tokens", 0) or 0), int(uso.get("completion_tokens", 0) or 0)
    return {"decision": decision, "motivo": motivo[:300], "comprobaciones": comprobaciones, "delJuez": del_juez, "deterministas": deterministas, "segundos": round(time.time() - t0, 1), "usd": round(config.coste_usd(juez.model, ent, sal), 4), "resumenJuez": rev.resumen.strip()[:300]}


def evaluar_caso(fallo: str, esperado: dict[str, Any], real: str | None, r: dict[str, Any]) -> dict[str, Any]:
    """Detectado: la decision cae en las esperadas y, si hay comprobacion
    objetivo, esa comprobacion la marco alguien (juez o determinista) como falla."""
    por_nombre = {c["comprobacion"]: c["resultado"] for c in r["comprobaciones"]}
    juez_por_nombre = {c["comprobacion"]: c["resultado"] for c in r["delJuez"]}
    comp = esperado["comprobacion"]
    comp_falla = por_nombre.get(comp) == "falla" if comp else None
    juez_falla = juez_por_nombre.get(comp) == "falla" if comp else None
    if fallo == "original":
        acuerdo = None if real is None else r["decision"] == real
        return {"detectado": None, "acuerdoConReal": acuerdo, "comprobacionFalla": None, "juezFalla": None}
    decision_ok = r["decision"] in esperado["esperadas"]
    detectado = decision_ok and (comp_falla if comp else True)
    return {"detectado": bool(detectado), "decisionEsperada": decision_ok, "comprobacionFalla": comp_falla, "juezFalla": juez_falla, "acuerdoConReal": None}


async def correr(n_hipotesis: int, fallos: list[str], paralelo: int, salida: Path | None, registrar: bool) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60) as cli:
        e = (await cli.get(f"{URL}/api/estado")).json()
    candidatas = [h for h in e["hipotesis"] if h["estado"] != "descartada" and len([a for a in h.get("afirmaciones", []) if a.get("veredicto") in ("sostenida", "parcial")]) >= 2 and h.get("tarjeta") and (h.get("tarjeta") or {}).get("prediccionFalsable")]
    # Primero las que el Killer real dejo avanzar: en una hipotesis que ya se
    # descarta por otro motivo, un fallo plantado no se puede medir.
    candidatas.sort(key=lambda h: (0 if h.get("decisionKiller") == "avanzar" else 1 if h.get("decisionKiller") in (None, "suspender") else 2, -len(h.get("afirmaciones", []))))
    elegidas = candidatas[:n_hipotesis]
    if not elegidas:
        raise SystemExit("No hay hipotesis con tarjeta y afirmaciones sostenidas en el estado; el panel necesita hipotesis reales")
    modelos = cargar_modelos()
    dspy.configure(lm=modelos.cerebro)
    programas = Programas()
    casos: list[tuple[dict[str, Any], str, dict[str, Any]]] = []
    for h in elegidas:
        for f in fallos:
            v = plantar(h, f)
            if v is not None:
                casos.append((h, f, v))
    print(f"{len(elegidas)} hipotesis, {len(casos)} casos; juez {modelos.juez.model}", file=sys.stderr)
    sem = asyncio.Semaphore(paralelo)
    resultados: list[dict[str, Any]] = []

    async def uno(h: dict[str, Any], f: dict[str, Any], v: dict[str, Any], fallo: str) -> None:
        async with sem:
            try:
                r = await asyncio.to_thread(juzgar, programas, modelos.juez, e, v, modelos.volumen)
            except Exception as ex:  # noqa: BLE001
                r = {"decision": "error", "motivo": str(ex)[:300], "comprobaciones": [], "delJuez": [], "deterministas": [], "segundos": 0, "usd": 0, "resumenJuez": ""}
            ev = evaluar_caso(fallo, FALLOS[fallo], h.get("decisionKiller"), r)
            plantado = next((a.get("_plantado") for a in v.get("afirmaciones", []) if a.get("_plantado")), "")
            resultados.append({"hipotesisId": h["id"], "titulo": h["titulo"][:100], "fallo": fallo, "plantado": plantado, "decisionReal": h.get("decisionKiller"), **ev, "decision": r["decision"], "motivo": r["motivo"], "comprobacionesFallidas": [c["comprobacion"] for c in r["comprobaciones"] if c["resultado"] == "falla"], "juezFallidas": [c["comprobacion"] for c in r["delJuez"] if c["resultado"] == "falla"], "segundos": r["segundos"], "usd": r["usd"]})
            print(f"  {fallo:24s} {h['titulo'][:40]:40s} -> {r['decision']:22s} detectado={ev.get('detectado')} juezFalla={ev.get('juezFalla')} {r['usd']:.3f} USD", file=sys.stderr)

    await asyncio.gather(*(uno(h, FALLOS[f], v, f) for h, f, v in casos))
    # Resumen por fallo.
    por_fallo: dict[str, Any] = {}
    for f in fallos:
        rs = [r for r in resultados if r["fallo"] == f]
        if not rs:
            continue
        if f == "original":
            por_fallo[f] = {"casos": len(rs), "acuerdoConReal": sum(1 for r in rs if r["acuerdoConReal"]), "conDecisionReal": sum(1 for r in rs if r.get("decisionReal")), "descartadas": sum(1 for r in rs if r["decision"] == "descartar_en_contexto"), "suspendidas": sum(1 for r in rs if r["decision"] == "suspender")}
        else:
            por_fallo[f] = {"casos": len(rs), "detectados": sum(1 for r in rs if r["detectado"]), "decisionEsperada": sum(1 for r in rs if r.get("decisionEsperada")), "comprobacionFalla": sum(1 for r in rs if r.get("comprobacionFalla")), "juezFalla": sum(1 for r in rs if r.get("juezFalla")), "suspendidas": sum(1 for r in rs if r["decision"] == "suspender"), "descartadas": sum(1 for r in rs if r["decision"] == "descartar_en_contexto"), "errores": sum(1 for r in rs if r["decision"] == "error")}
    plantados = [r for r in resultados if r["fallo"] not in ("original", "gris_parcial")]
    grises = [r for r in resultados if r["fallo"] == "gris_parcial"]
    resumen = {
        "casos": len(resultados),
        "hipotesis": len(elegidas),
        "tasaDeteccion": round(sum(1 for r in plantados if r["detectado"]) / len(plantados), 3) if plantados else None,
        "tasaJuezDetecta": round(sum(1 for r in plantados if r.get("juezFalla")) / len([r for r in plantados if FALLOS[r["fallo"]]["comprobacion"]]), 3) if plantados else None,
        "abstencion": round(sum(1 for r in resultados if r["decision"] == "suspender") / len(resultados), 3),
        "sobreMatanzaGris": round(sum(1 for r in grises if r["decision"] == "descartar_en_contexto") / len(grises), 3) if grises else None,
        "usd": round(sum(r["usd"] for r in resultados), 3),
        "segundos": round(sum(r["segundos"] for r in resultados), 1),
        "juez": modelos.juez.model,
    }
    salida_dict = {"tipo": "panel_killer", "fecha": int(time.time() * 1000), "resumen": resumen, "porFallo": por_fallo, "fallos": {k: v["descripcion"] for k, v in FALLOS.items() if k in fallos}, "casos": resultados}
    if salida:
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(json.dumps(salida_dict, ensure_ascii=False, indent=1))
        print(f"Escrito {salida}", file=sys.stderr)
    if registrar:
        async with httpx.AsyncClient(timeout=60) as cli:
            r = await cli.post(f"{URL}/api/acciones/registrarEvaluacion", json={"evaluacion": {k: v for k, v in salida_dict.items() if k != "casos"} | {"casos": [{k: v for k, v in c.items() if k not in ("motivo",)} for c in resultados]}, "quien": "panel_killer"})
            print(f"Registro en el estado: {r.status_code} {r.text[:120]}", file=sys.stderr)
    return salida_dict


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--hipotesis", type=int, default=5)
    ap.add_argument("--fallos", default=",".join(FALLOS))
    ap.add_argument("--paralelo", type=int, default=4)
    ap.add_argument("--salida", default=str(config.RAIZ / "rosa" / "evaluacion" / "resultados" / f"panel_killer-{time.strftime('%Y-%m-%d-%H%M')}.json"))
    ap.add_argument("--sin-registrar", action="store_true")
    a = ap.parse_args()
    out = asyncio.run(correr(a.hipotesis, [f for f in a.fallos.split(",") if f in FALLOS], a.paralelo, Path(a.salida), not a.sin_registrar))
    print(json.dumps({"resumen": out["resumen"], "porFallo": out["porFallo"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
