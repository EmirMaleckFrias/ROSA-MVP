"""Progreso de una corrida: la serie por iteración y la métrica única.

Lo que rekursiv.ai dibuja como "progress across research waves" con su banda
de fallidos, para ROSA2018: al cerrar cada iteración se guarda una instantánea
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

import math
from typing import Any

from rosa import certeza as CERTEZA

CIERRES_KILLER = ("descartar_en_contexto", "suspender")


def peldano(nivel: str | None) -> int:
    return CERTEZA.NIVELES.index(nivel) if nivel in CERTEZA.NIVELES else 0


def _ms(v: Any) -> int | None:
    """Un instante en milisegundos, o None si el registro trae otra cosa."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return int(v)


def hipotesis_nacidas_en(e: dict[str, Any], investigacion_id: Any, it: dict[str, Any] | None, ahora: int | None = None, origen: str | None = None) -> list[dict[str, Any]]:
    """Las hipótesis de la investigación que nacieron dentro de la ventana de la
    iteración `it`: `it.empezadaEn <= creadaEn <= it.terminadaEn` (o `ahora`
    si la iteración sigue abierta). Es la única definición de "hipótesis nueva
    de esta iteración" del cierre, el informe, el progreso y el revisor.

    Antes se comparaba `h.iteracion == it.numero`, y como el número de
    iteración vuelve a 1 en cada corrida, una hipótesis del 15 de septiembre
    contaba como nueva en la iteración 1 de todas las corridas siguientes
    (corridas 4 a 12: "5 hipótesis nuevas" con 0 nacimientos reales). La
    ventana por fecha funciona también hacia atrás, para recalcular la serie
    de progreso de las corridas viejas sin claves privadas.

    `origen`: "rosa" para contar solo las de ROSA2018 (resumen y llano), None para
    todas (el revisor, que también mira las humanas). Una hipótesis sin
    `creadaEn` legible o una iteración sin `empezadaEn` no cuentan: mejor
    "ninguna" que un recuento inventado."""
    if not isinstance(it, dict):
        return []
    desde = _ms(it.get("empezadaEn"))
    if desde is None:
        return []
    hasta = _ms(it.get("terminadaEn"))
    if hasta is None:
        hasta = _ms(ahora) if ahora is not None else None
    salida = []
    for h in e.get("hipotesis", []) or []:
        if not isinstance(h, dict) or h.get("investigacionId") != investigacion_id:
            continue
        if origen is not None and h.get("origen") != origen:
            continue
        creada = _ms(h.get("creadaEn"))
        if creada is None or creada < desde or (hasta is not None and creada > hasta):
            continue
        salida.append(h)
    return salida


def recalcular_progreso(e: dict[str, Any]) -> int:
    """Recalcula `hipotesisNuevas` de cada instantánea de progreso con
    `hipotesis_nacidas_en` (nacidas de ROSA2018 en la ventana de su iteración) y
    vuelve a calcular la métrica de las corridas que ya la tenían. Devuelve
    cuántas instantáneas cambiaron. Es idempotente: pasarla dos veces da lo
    mismo, así que puede engancharse a la migración del almacén o correr al
    arrancar el supervisor. Una instantánea cuya iteración no aparece en el
    estado se deja como está (no se inventa un cero)."""
    cambiadas = 0
    for c in e.get("corridas", []) or []:
        if not isinstance(c, dict) or not isinstance(c.get("progreso"), list):
            continue
        tocada = False
        for p in c["progreso"]:
            if not isinstance(p, dict):
                continue
            it = next((x for x in e.get("iteraciones", []) if isinstance(x, dict) and x.get("corridaId") == c.get("id") and x.get("numero") == p.get("iteracion")), None)
            if it is None or _ms(it.get("empezadaEn")) is None:
                continue
            n = len(hipotesis_nacidas_en(e, c.get("investigacionId"), it, ahora=_ms(p.get("fecha")), origen="rosa"))
            if p.get("hipotesisNuevas") != n:
                p["hipotesisNuevas"] = n
                cambiadas += 1
                tocada = True
        if tocada and c.get("metrica") is not None:
            c["metrica"] = metrica_de_corrida(e, c["id"])
    return cambiadas


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
        # Pasos que corrieron y no tenían nada que hacer (sin fuentes nuevas, nada
        # que verificar): no son fallos, pero tampoco trabajo; se cuentan aparte.
        "sinTrabajo": sum(1 for p_ in it.get("plan", []) if p_.get("estado") == "sin_trabajo"),
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
        "fallidos": {k: sum(int((p.get("fallidos") or {}).get(k) or 0) for p in serie) for k in ("pasos", "pistas", "killer", "afirmacionesBloqueadas", "sinTrabajo")},
        "banco": None,
        # Las tres cifras de aprendizaje (rosa/cifras_aprendizaje.py) tal como las
        # dejó el bucle en la investigación al cerrar la iteración; aquí solo se
        # leen. None si todavía no se calcularon o si la investigación no está.
        "aprendizaje": aprendizaje_de(e, c.get("investigacionId")),
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


def aprendizaje_de(e: dict[str, Any], investigacion_id: Any) -> dict[str, Any] | None:
    """Las cifras de aprendizaje de la investigación, recortadas a las tres
    que van en la métrica: acierto prerregistrado (qué fracción de lo que ROSA2018
    predijo por escrito salió como dijo), tiempo hasta decisión (horas desde
    que nace una hipótesis hasta que el Killer o una persona la decide) y
    reutilización heredada (cuántos hechos heredados de otra investigación
    volvieron a usarse). No las calcula: las calcula el bucle al cerrar la
    iteración y las deja en `investigacion.cifrasAprendizaje`. None si no
    están, si la clave no es un diccionario o si la investigación no existe."""
    inv = next((i for i in (e.get("investigaciones") or []) if isinstance(i, dict) and i.get("id") == investigacion_id), None)
    cifras = inv.get("cifrasAprendizaje") if inv else None
    if not isinstance(cifras, dict):
        return None
    return {k: (cifras.get(k) if isinstance(cifras.get(k), dict) else None) for k in ("acierto", "tiempo", "reutilizacion")}


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
    frase = frase_acierto(m.get("aprendizaje"))
    if frase:
        partes.append(frase)
    return "; ".join(partes)


def _entero(v: Any) -> int | None:
    """Un recuento como entero, o None si no es un número finito (un None, un
    texto o un NaN heredado de un registro roto no se imprimen como cifra)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return int(v)


def frase_acierto(aprendizaje: Any) -> str:
    """La frase del acierto prerregistrado para la persona: 'acertó 1 de 2
    predicciones prerregistradas (50 %)'. Acierto prerregistrado quiere decir
    la fracción de predicciones que ROSA2018 dejó escritas antes de ver los datos
    y que después salieron como dijo. Solo cuando hay tasa (alguna predicción
    con dirección ya evaluada): sin casos se calla, nunca dice '0 %'. Una tasa
    que no sea un número finito (NaN, infinito, texto) también calla, en vez
    de lanzar."""
    if not isinstance(aprendizaje, dict) or not isinstance(aprendizaje.get("acierto"), dict):
        return ""
    acierto = aprendizaje["acierto"]
    tasa = acierto.get("tasa")
    if isinstance(tasa, bool) or not isinstance(tasa, (int, float)) or not math.isfinite(tasa):
        return ""
    aciertos, con_direccion = _entero(acierto.get("aciertos")), _entero(acierto.get("conDireccion"))
    porcentaje = f"{round(float(tasa) * 100):d} %"
    if aciertos is None or con_direccion is None:
        return f"acierto de las predicciones prerregistradas: {porcentaje}"
    return f"acertó {aciertos} de {con_direccion} {'predicción prerregistrada' if con_direccion == 1 else 'predicciones prerregistradas'} ({porcentaje})"


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
