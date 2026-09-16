"""Progreso de una corrida: la serie por iteración y la métrica única.

Lo que rekursiv.ai dibuja como "progress across research waves" con su banda
de fallidos, para Rosa: al cerrar cada iteración se guarda una instantánea
con la certeza de cada hipótesis (peldaño GRADE 0 a 3), cuántos peldaños se
subieron o bajaron respecto a la instantánea anterior, cuántos hechos e
hipótesis nacieron, qué falló (pasos, pistas, cierres del Killer,
afirmaciones bloqueadas) y el gasto acumulado. Al terminar la corrida, la
métrica única: peldaños netos subidos por dólar, más lo que dé el banco de
objetivos si la investigación encaja con alguno. Es la vara de Emir: el valor
de una corrida es cuánto suben las hipótesis que ya existen, no cuántas nacen.
16 de septiembre de 2026.
"""

from __future__ import annotations

from typing import Any

from rosa import certeza as CERTEZA

CIERRES_KILLER = ("descartar_en_contexto", "suspender")


def peldano(nivel: str | None) -> int:
    return CERTEZA.NIVELES.index(nivel) if nivel in CERTEZA.NIVELES else 0


def instantanea(e: dict[str, Any], c: dict[str, Any], it: dict[str, Any], hechos_nuevos: int, hipotesis_nuevas: int, afirmaciones_bloqueadas: int, ahora: int) -> dict[str, Any]:
    """La instantánea de progreso al cerrar la iteración `it` de la corrida `c`."""
    anterior = (c.get("progreso") or [{}])[-1] if c.get("progreso") else {}
    peldano_previo = {x["hipotesisId"]: x["peldano"] for x in anterior.get("certezas", [])}
    certezas = []
    subidos = bajados = 0
    for h in e["hipotesis"]:
        if h["investigacionId"] != c["investigacionId"] or h["estado"] == "descartada":
            continue
        k = h.get("conclusion") or {}
        p = peldano(k.get("certeza"))
        certezas.append({"hipotesisId": h["id"], "certeza": k.get("certeza") or "muy_baja", "direccion": k.get("direccion"), "peldano": p, "techo": (k.get("techo") or {}).get("nivel")})
        antes = peldano_previo.get(h["id"])
        if antes is None:
            subidos += p  # una hipótesis que nace en baja ya sube un peldaño
        elif p > antes:
            subidos += p - antes
        elif p < antes:
            bajados += antes - p
    cierres = [d for d in e.get("decisiones", []) if d.get("investigacionId") == c["investigacionId"] and str(d.get("etapa", "")).startswith("killer") and d.get("decision") in CIERRES_KILLER and (d.get("fecha") or 0) >= (it.get("empezadaEn") or 0)]
    fallidos = {
        "pasos": sum(1 for p_ in it.get("plan", []) if p_.get("estado") in ("fallido", "omitido")),
        "pistas": sum(1 for p_ in it.get("pistas", []) if p_.get("estado") in ("fallida", "detenida")),
        "killer": len(cierres),
        "afirmacionesBloqueadas": int(afirmaciones_bloqueadas),
    }
    return {
        "iteracion": it["numero"],
        "fecha": ahora,
        "certezas": certezas,
        "peldanosTotales": sum(x["peldano"] for x in certezas),
        "peldanosSubidos": subidos,
        "peldanosBajados": bajados,
        "hipotesisVivas": len(certezas),
        "hechosNuevos": int(hechos_nuevos),
        "hipotesisNuevas": int(hipotesis_nuevas),
        "fallidos": fallidos,
        "usdAcumulado": round(float((c.get("gasto") or {}).get("usd") or 0.0), 4),
        "llamadasAcumuladas": int((c.get("gasto") or {}).get("llamadas") or 0),
        "arnes": (c.get("arnes") or {}).get("commit"),
    }


def metrica_de_corrida(e: dict[str, Any], corrida_id: str) -> dict[str, Any] | None:
    """La métrica única de la corrida, a partir de su serie de progreso."""
    c = next((x for x in e["corridas"] if x["id"] == corrida_id), None)
    if not c:
        return None
    serie = c.get("progreso") or []
    subidos = sum(int(p.get("peldanosSubidos") or 0) for p in serie)
    bajados = sum(int(p.get("peldanosBajados") or 0) for p in serie)
    netos = subidos - bajados
    usd = float((c.get("gasto") or {}).get("usd") or 0.0)
    ultima = serie[-1] if serie else {}
    metrica: dict[str, Any] = {
        "iteraciones": len(serie),
        "peldanosSubidos": subidos,
        "peldanosBajados": bajados,
        "peldanosNetos": netos,
        "usd": round(usd, 4),
        "peldanosPorDolar": round(netos / usd, 3) if usd > 0 else None,
        "hipotesisEnBajaOMas": sum(1 for x in ultima.get("certezas", []) if int(x.get("peldano") or 0) >= 1),
        "hechosNuevos": sum(int(p.get("hechosNuevos") or 0) for p in serie),
        "hipotesisNuevas": sum(int(p.get("hipotesisNuevas") or 0) for p in serie),
        "fallidos": {k: sum(int((p.get("fallidos") or {}).get(k) or 0) for p in serie) for k in ("pasos", "pistas", "killer", "afirmacionesBloqueadas")},
        "banco": None,
    }
    try:
        from rosa.evaluacion import banco as B

        objetivo = B.elegir_objetivo(e, corrida_id, B.cargar_objetivos())
        if objetivo:
            r = B.puntuar(e, corrida_id, objetivo)
            metrica["banco"] = {"objetivo": objetivo.get("clave"), "puntuacion": r.get("puntuacion"), "criterios": r.get("criterios")}
    except Exception:  # noqa: BLE001  el banco es opcional; la métrica no
        metrica["banco"] = None
    return metrica


def resumen_metrica(m: dict[str, Any] | None) -> str:
    """Una línea para la persona: 'subió 3 peldaños netos en 4 iteraciones (0,21 por dólar)'."""
    if not m:
        return ""
    netos = m.get("peldanosNetos", 0)
    partes = [f"{'subió' if netos >= 0 else 'bajó'} {abs(netos)} {'peldaño' if abs(netos) == 1 else 'peldaños'} netos de certeza en {m.get('iteraciones', 0)} {'iteración' if m.get('iteraciones') == 1 else 'iteraciones'}"]
    if m.get("peldanosPorDolar") is not None:
        partes.append(f"{m['peldanosPorDolar']:g} por dólar")
    if m.get("hipotesisEnBajaOMas"):
        partes.append(f"{m['hipotesisEnBajaOMas']} {'hipótesis' } en certeza baja o más")
    return "; ".join(partes)


def iteraciones_sin_avance(c: dict[str, Any]) -> int:
    """Cuántas iteraciones seguidas, desde la última, no subieron ningún
    peldaño ni añadieron hechos."""
    n = 0
    for p in reversed(c.get("progreso") or []):
        if int(p.get("peldanosSubidos") or 0) == 0 and int(p.get("hechosNuevos") or 0) == 0:
            n += 1
        else:
            break
    return n


def hipotesis_en_nivel(c: dict[str, Any], nivel: str) -> int:
    serie = c.get("progreso") or []
    if not serie:
        return 0
    return sum(1 for x in serie[-1].get("certezas", []) if int(x.get("peldano") or 0) >= peldano(nivel))
