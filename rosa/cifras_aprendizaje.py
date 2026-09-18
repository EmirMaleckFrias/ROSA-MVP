"""Las tres cifras de aprendizaje que el informe pide y ROSA2018 no medía.

Son aritmética sobre el registro; ningún modelo interviene y cada valor
viene con el motivo que lo produjo. Las tres, con el término definido:

1. Acierto de lo prerregistrado. Un prerregistro es lo que ROSA2018 deja por
   escrito antes de mirar los datos: qué espera ver (dirección esperada de
   un plan de análisis, criterio de confirmación de un experimento) y qué
   hará según salga. La cifra es la fracción de esas predicciones que
   salieron como se dijo. Regla: un caso es un plan de análisis congelado
   con una ejecución válida (auditoría "válido") e interpretada, o un
   experimento prerregistrado con resultado del laboratorio. El caso "tiene
   dirección" si el plan declaró `direccionEsperada` (y no es exploratorio)
   o el experimento declaró `confirma`. Con dirección, el resultado
   "efecto_detectado" (análisis) o "confirma" (laboratorio) es un acierto;
   "sin_efecto_detectable" o "refuta" es un fallo; "no_evaluable" o
   "inconcluso" no entra en la tasa. Sin dirección, el caso se cuenta aparte
   y no toca la tasa: no se inventa un sentido donde el prerregistro no lo
   puso. Si la dirección declarada predice ausencia de efecto ("sin
   diferencia", "no difference"), la regla se invierte a medias: detectar un
   efecto es un fallo, pero no detectarlo no es un acierto, porque una prueba
   de significación no demuestra que un efecto no exista (haría falta una
   prueba de equivalencia); ese caso cuenta como no evaluable con su motivo.
   El sentido del efecto (mayor o menor) no se comprueba aquí porque el
   registro no estructura el orden de los grupos; se dice en el motivo.

2. Tiempo hasta cada decisión. Desde que nace la hipótesis (`creadaEn`)
   hasta la primera decisión registrada de cada etapa (killer_1, killer_2,
   priorizacion, persona, retorno). Mediana (el valor del medio) y p90 (el
   valor por debajo del cual queda el 90 % de los casos, por rango más
   cercano). Las hipótesis vivas sin ninguna decisión se miden aparte, desde
   que nacieron hasta ahora.

3. Reutilización de lo heredado. Un hecho heredado es uno copiado de otra
   investigación al crear esta (su id lleva el sufijo de la investigación de
   destino; misma regla que `rosa.bucle.contexto.es_heredado`). Se cuenta
   como usado si alguna de sus afirmaciones o de sus fuentes coincide con
   una afirmación o fuente de una hipótesis viva de esta investigación, o si
   está sabido en el modelo de mundo y una hipótesis lo nombra en su
   procedencia.

Todo tolera registros antiguos sin las claves nuevas: lo que falta se trata
como ausente, nunca rompe; los valores que el registro compara con el
servidor ("valido", "confirma", "sabido") se leen sin distinguir mayúsculas.
Sin datos, la tasa es None, no 0. Las tres cifras son lineales en el tamaño
del registro (índices invertidos, nada cuadrático).
16 de septiembre de 2026.
"""

from __future__ import annotations

import math
import re
import statistics
import time
from typing import Any

from rosa import certeza as CERTEZA
from rosa.bucle.contexto import es_heredado

ETAPAS = ("killer_1", "killer_2", "priorizacion", "persona", "retorno")
INTERPRETACIONES = ("efecto_detectado", "sin_efecto_detectable", "no_evaluable")
VEREDICTOS_LABORATORIO = ("confirma", "refuta", "inconcluso", "no_evaluable")
MS_POR_HORA = 3_600_000.0

# Una dirección esperada que predice ausencia de efecto, en castellano o en
# inglés, buscada como palabra entera sobre el texto en minúsculas. Solo vale
# si el texto no lleva además una palabra de sentido (mayor, menor, sube...):
# "igual o mayor" predice efecto; "sin diferencia entre grupos" no.
PREDICCION_NULA = re.compile(
    r"\b(?:"
    r"sin (?:diferencias?|efectos?|cambios?|asociaci[oó]n|relaci[oó]n|correlaci[oó]n)"
    r"|no(?: hay| habr[aá]| se esperan?| existen?)? (?:diferencias?|efectos?|cambios?|asociaci[oó]n|relaci[oó]n|correlaci[oó]n)"
    r"|ning[uú]n[ao]? (?:diferencia|efecto|cambio|asociaci[oó]n|relaci[oó]n|correlaci[oó]n)"
    r"|(?:efecto|diferencia|asociaci[oó]n) nul[oa]"
    r"|no difieren?"
    r"|igual(?:es)?"
    r"|no (?:significant )?(?:difference|effect|change|association|relationship|correlation)s?"
    r"|null (?:effect|difference|association)"
    r"|does not differ|do not differ|unchanged|equal"
    r")\b"
)
PALABRAS_DE_SENTIDO = re.compile(r"mayor|menor|m[aá]s alt|m[aá]s baj|\bsub[ea]|\bbaj[ae]|aument|disminu|reduc|eleva|crecien|increas|decreas|higher|lower|greater|smaller|larger|positiv|negativ|invers|directa|[<>↑↓]")

REGLA_ACIERTO = (
    "Un caso es un plan congelado con ejecución válida e interpretada, o un experimento prerregistrado con resultado. "
    "Tiene dirección si el plan declaró dirección esperada (y no es exploratorio) o el experimento declaró qué lo confirma. "
    "Con dirección: efecto detectado o veredicto 'confirma' es acierto; sin efecto detectable o 'refuta' es fallo; no evaluable o inconcluso no entra en la tasa. "
    "Si la dirección predice ausencia de efecto, detectar uno es fallo y no detectarlo es no evaluable (una prueba de significación no demuestra la ausencia). "
    "Sin dirección se cuenta aparte y no toca la tasa. El sentido del efecto (mayor o menor) no se comprueba: el registro no lo estructura."
)
REGLA_TIEMPO = "Horas desde `creadaEn` de la hipótesis hasta la primera decisión registrada de cada etapa; mediana y p90 por rango más cercano. Una decisión anterior a la creación cuenta como 0 horas y se anota en fechasInvertidas. Las vivas sin decisión se miden hasta ahora."
REGLA_REUTILIZACION = "Heredado: id con el sufijo de la investigación de destino (es_heredado) o id que termina en '-<investigación>' cuyo original existe. Usado: comparte afirmación o fuente (id o referencia) con una hipótesis viva, o está sabido y una hipótesis lo nombra en su procedencia."

GLOSARIO = {
    "prerregistro": "lo que ROSA2018 deja por escrito antes de mirar los datos: qué espera ver y qué hará según salga",
    "acierto": "el resultado cayó del lado que el prerregistro llamó 'confirma'",
    "decision": "cada juicio registrado sobre una hipótesis: del Killer (killer_1, killer_2), de la priorización, de una persona o del retorno del laboratorio",
    "mediana": "el valor del medio: la mitad de los casos queda por debajo",
    "p90": "el valor por debajo del cual queda el 90 % de los casos",
    "hecho_heredado": "un hecho del modelo de mundo copiado de otra investigación al crear esta",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _ms(v: Any) -> int | None:
    """Un tiempo en milisegundos o None si no es un número finito."""
    if isinstance(v, bool) or v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError, OverflowError):
        return None


def _texto(v: Any) -> str:
    return str(v).strip() if isinstance(v, str) else ""


def _clave(v: Any) -> str:
    """Un valor que el registro compara con el servidor ('valido', 'confirma',
    'sabido'), leído sin distinguir mayúsculas ni espacios de más."""
    return _texto(v).lower()


def _dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _lista(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _dicts(e: Any, clave: str) -> list[dict[str, Any]]:
    """La lista `clave` del estado, solo con sus entradas que son diccionarios."""
    return [x for x in _lista(_dict(e).get(clave)) if isinstance(x, dict)]


def _mediana(valores: list[float]) -> float | None:
    return round(statistics.median(valores), 2) if valores else None


def _p90(valores: list[float]) -> float | None:
    """Percentil 90 por rango más cercano: el valor en la posición ceil(0.9 n)."""
    if not valores:
        return None
    orden = sorted(valores)
    k = max(1, math.ceil(0.9 * len(orden)))
    return round(orden[k - 1], 2)


def _tasa(aciertos: int, total: int) -> float | None:
    return round(aciertos / total, 3) if total > 0 else None


def _nivel_de(h: dict[str, Any] | None) -> str | None:
    """El nivel GRADE de la conclusión de la hipótesis, si consta y es uno de los cuatro."""
    if not isinstance(h, dict):
        return None
    nivel = _clave(_dict(h.get("conclusion")).get("certeza"))
    return nivel if nivel in CERTEZA.NIVELES else None


def _hipotesis_de(e: Any, investigacion_id: str | None) -> list[dict[str, Any]]:
    return [h for h in _dicts(e, "hipotesis") if investigacion_id is None or h.get("investigacionId") == investigacion_id]


def _viva(h: dict[str, Any]) -> bool:
    """Misma regla que el resto de ROSA2018: viva es toda hipótesis no descartada
    (la fusión también descarta). Un estado ausente cuenta como viva."""
    return _clave(h.get("estado")) != "descartada"


def _por_id(lista: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Primero gana: con ids repetidos, el primero de la lista es el que se consulta."""
    salida: dict[str, dict[str, Any]] = {}
    for x in lista:
        i = x.get("id")
        if isinstance(i, str) and i not in salida:
            salida[i] = x
    return salida


# ---------------------------------------------------------------------------
# 1. Acierto de lo prerregistrado
# ---------------------------------------------------------------------------


def _ejecuciones_por_plan(e: Any) -> dict[Any, list[dict[str, Any]]]:
    """Las ejecuciones agrupadas por `planId`, una sola pasada sobre el registro."""
    salida: dict[Any, list[dict[str, Any]]] = {}
    for r in _dicts(e, "ejecuciones"):
        salida.setdefault(r.get("planId"), []).append(r)
    return salida


def _ejecucion_valida_de(plan: dict[str, Any], ejecuciones: list[dict[str, Any]]) -> dict[str, Any] | None:
    """La última ejecución del plan (por `fin`, o `inicio` si no terminó) con
    auditoría 'válido' e interpretación conocida. None si no hay ninguna:
    entonces el plan no es un caso todavía."""
    candidatas = []
    for r in ejecuciones:
        if _clave(_dict(r.get("auditoria")).get("veredicto")) == "valido" and _clave(_dict(r.get("interpretacion")).get("estado")) in INTERPRETACIONES:
            candidatas.append(r)
    if not candidatas:
        return None
    return max(candidatas, key=lambda r: (_ms(r.get("fin")) or _ms(r.get("inicio")) or 0))


def predice_ausencia_de_efecto(direccion: str) -> bool:
    """True si la dirección esperada dice que no habrá efecto ("sin diferencia",
    "no difference") y no lleva ninguna palabra de sentido (mayor, menor,
    sube...). Regla cerrada y explicable; en la duda, predice efecto."""
    d = _clave(direccion)
    return bool(d) and PREDICCION_NULA.search(d) is not None and PALABRAS_DE_SENTIDO.search(d) is None


def _caso_plan(plan: dict[str, Any], run: dict[str, Any], nivel: str | None) -> dict[str, Any]:
    estado = _clave(_dict(run.get("interpretacion")).get("estado"))
    direccion = _texto(plan.get("direccionEsperada"))
    tipo = _clave(plan.get("tipo")) or "confirmatorio"
    caso = {
        "fuente": "analisis",
        "hipotesisId": plan.get("hipotesisId"),
        "planId": plan.get("id"),
        "ejecucionId": run.get("id"),
        "hashPlan": plan.get("hashPlan"),
        "direccionEsperada": direccion,
        "resultado": estado,
        "nivel": nivel,
        "prerregistradoEn": _ms(plan.get("congeladoEn")),
        "resultadoEn": _ms(run.get("fin")) or _ms(run.get("inicio")),
    }
    if _texto(run.get("hashPlan")) and _texto(run.get("hashPlan")) != _texto(plan.get("hashPlan")):
        return {**caso, "clase": "sin_direccion", "motivo": "la ejecución corrió otra versión del plan (hash distinto): no prueba lo que se congeló"}
    if tipo == "exploratorio":
        return {**caso, "clase": "sin_direccion", "motivo": "plan exploratorio: no predice, explora"}
    if not direccion:
        return {**caso, "clase": "sin_direccion", "motivo": "el plan no declaró dirección esperada"}
    if predice_ausencia_de_efecto(direccion):
        if estado == "efecto_detectado":
            return {**caso, "clase": "fallo", "motivo": f"predijo ausencia de efecto ({direccion[:80]}) y la prueba prerregistrada detectó uno"}
        if estado == "sin_efecto_detectable":
            return {**caso, "clase": "no_evaluable", "motivo": f"predijo ausencia de efecto ({direccion[:80]}) y la prueba no detectó ninguno: compatible, pero no detectar un efecto no demuestra su ausencia (haría falta una prueba de equivalencia), así que no cuenta como acierto"}
        return {**caso, "clase": "no_evaluable", "motivo": "el análisis no fue evaluable: no dice ni a favor ni en contra"}
    if estado == "efecto_detectado":
        return {**caso, "clase": "acierto", "motivo": f"predijo efecto ({direccion[:80]}) y la prueba prerregistrada lo detectó; el sentido del efecto no se comprueba aquí"}
    if estado == "sin_efecto_detectable":
        return {**caso, "clase": "fallo", "motivo": f"predijo efecto ({direccion[:80]}) y la prueba prerregistrada no lo detectó"}
    return {**caso, "clase": "no_evaluable", "motivo": "el análisis no fue evaluable: no dice ni a favor ni en contra"}


def _caso_experimento(h: dict[str, Any], x: dict[str, Any], nivel: str | None) -> dict[str, Any]:
    r = _dict(x.get("resultado"))
    veredicto = _clave(r.get("veredicto"))
    criterio = _texto(x.get("confirma"))
    prerregistrado = _ms(x.get("prerregistradoEn"))
    fecha = _ms(r.get("fecha"))
    caso = {
        "fuente": "laboratorio",
        "hipotesisId": h.get("id"),
        "planId": None,
        "ejecucionId": None,
        "hashPlan": None,
        "direccionEsperada": criterio,
        "resultado": veredicto or None,
        "nivel": nivel,
        "prerregistradoEn": prerregistrado,
        "resultadoEn": fecha,
    }
    if not criterio:
        return {**caso, "clase": "sin_direccion", "motivo": "el prerregistro no separó el criterio de confirmación (se congeló solo el ensayo)"}
    if prerregistrado is not None and fecha is not None and fecha < prerregistrado:
        return {**caso, "clase": "sin_direccion", "motivo": "el resultado es anterior al prerregistro: no cuenta como predicción"}
    if veredicto == "confirma":
        return {**caso, "clase": "acierto", "motivo": "el laboratorio dio el resultado que el prerregistro llamó 'confirma'"}
    if veredicto == "refuta":
        return {**caso, "clase": "fallo", "motivo": "el laboratorio dio el resultado que el prerregistro llamó 'refuta'"}
    if veredicto in ("inconcluso", "no_evaluable"):
        return {**caso, "clase": "no_evaluable", "motivo": f"resultado {veredicto.replace('_', ' ')}: no dice ni a favor ni en contra"}
    return {**caso, "clase": "no_evaluable", "motivo": f"veredicto desconocido ('{veredicto[:40]}'): no se interpreta"}


def _agregado(casos: list[dict[str, Any]]) -> dict[str, Any]:
    con_direccion = [c for c in casos if c["clase"] in ("acierto", "fallo")]
    aciertos = sum(1 for c in con_direccion if c["clase"] == "acierto")
    return {
        "casos": len(casos),
        "conDireccion": len(con_direccion),
        "aciertos": aciertos,
        "tasa": _tasa(aciertos, len(con_direccion)),
        "sinDireccion": sum(1 for c in casos if c["clase"] == "sin_direccion"),
        "noEvaluables": sum(1 for c in casos if c["clase"] == "no_evaluable"),
    }


def acierto_prerregistrado(e: dict[str, Any], investigacion_id: str | None = None) -> dict[str, Any]:
    """Fracción de las predicciones prerregistradas (con dirección y resultado
    evaluable) que salieron como se dijo. Ver REGLA_ACIERTO."""
    hipotesis = _hipotesis_de(e, investigacion_id)
    hip_por_id = _por_id(hipotesis)
    ejecuciones_por_plan = _ejecuciones_por_plan(e)
    excluidos = {"planesSinCongelar": 0, "planesSinEjecucionValida": 0, "planesReproduccion": 0, "laboratorioSinPrerregistro": 0}
    casos: list[dict[str, Any]] = []
    vistos: set[tuple[Any, Any]] = set()
    for plan in _dicts(e, "planesAnalisis"):
        if investigacion_id is not None and plan.get("investigacionId") != investigacion_id:
            continue
        if _clave(plan.get("tipo")) == "reproduccion":
            excluidos["planesReproduccion"] += 1
            continue
        if not _texto(plan.get("hashPlan")):
            excluidos["planesSinCongelar"] += 1
            continue
        run = _ejecucion_valida_de(plan, ejecuciones_por_plan.get(plan.get("id"), []))
        if run is None:
            excluidos["planesSinEjecucionValida"] += 1
            continue
        clave = (plan.get("id"), run.get("id"))
        if clave in vistos:
            continue  # el mismo plan repetido en el registro no es otro caso
        vistos.add(clave)
        casos.append(_caso_plan(plan, run, _nivel_de(hip_por_id.get(plan.get("hipotesisId")))))
    for h in hipotesis:
        x = h.get("experimento")
        if not isinstance(x, dict):
            continue
        r = x.get("resultado")
        if not isinstance(r, dict) or not _texto(r.get("veredicto")):
            continue
        if _ms(x.get("prerregistradoEn")) is None:
            excluidos["laboratorioSinPrerregistro"] += 1
            continue
        clave = ("experimento", h.get("id"))
        if clave in vistos:
            continue
        vistos.add(clave)
        casos.append(_caso_experimento(h, x, _nivel_de(h)))
    por_nivel: dict[str, dict[str, int]] = {}
    for c in casos:
        if c["nivel"] and c["clase"] in ("acierto", "fallo"):
            bucket = por_nivel.setdefault(c["nivel"], {"casos": 0, "aciertos": 0})
            bucket["casos"] += 1
            bucket["aciertos"] += 1 if c["clase"] == "acierto" else 0
    total = _agregado(casos)
    return {
        **total,
        "porFuente": {"analisis": _agregado([c for c in casos if c["fuente"] == "analisis"]), "laboratorio": _agregado([c for c in casos if c["fuente"] == "laboratorio"])},
        # En el orden de la escalera GRADE (muy baja, baja, moderada, alta), no en el de aparición.
        "porNivel": {nivel: por_nivel[nivel] for nivel in CERTEZA.NIVELES if nivel in por_nivel},
        "excluidos": excluidos,
        "detalle": casos,
        "regla": REGLA_ACIERTO,
    }


# ---------------------------------------------------------------------------
# 2. Tiempo hasta cada decisión
# ---------------------------------------------------------------------------


def _ahora_ms(ahora: Any) -> int:
    """El instante de referencia: el que llega si es un número; si no, el reloj."""
    v = _ms(ahora) if ahora is not None else None
    return v if v is not None else int(time.time() * 1000)


def tiempo_hasta_decision(e: dict[str, Any], investigacion_id: str | None = None, ahora: int | None = None) -> dict[str, Any]:
    """Horas desde que nace cada hipótesis hasta su primera decisión de cada
    etapa; mediana y p90; las vivas sin decisión, aparte. Ver REGLA_TIEMPO."""
    ahora_ms = _ahora_ms(ahora)
    hipotesis = _hipotesis_de(e, investigacion_id)
    por_hipotesis: dict[str, list[dict[str, Any]]] = {}
    for d in _dicts(e, "decisiones"):
        hid = d.get("hipotesisId")
        if isinstance(hid, str):
            por_hipotesis.setdefault(hid, []).append(d)
    duraciones: list[float] = []
    por_etapa: dict[str, list[float]] = {}
    abiertas: list[float] = []
    detalle: list[dict[str, Any]] = []
    sin_fecha_creacion = 0
    fechas_invertidas = 0
    decisiones_sin_fecha = 0
    for h in hipotesis:
        creada = _ms(h.get("creadaEn"))
        if creada is None:
            sin_fecha_creacion += 1
            continue
        primeras: dict[str, int] = {}
        for d in por_hipotesis.get(h.get("id"), []):
            # Una decisión que dice ser de otra investigación no es de esta hipótesis
            # (los ids de hipótesis no se comparten entre investigaciones); sin la
            # clave, se acepta como registro antiguo.
            if d.get("investigacionId") not in (None, h.get("investigacionId")):
                continue
            fecha = _ms(d.get("fecha"))
            if fecha is None:
                decisiones_sin_fecha += 1
                continue
            etapa = _clave(d.get("etapa")) or "sin_etapa"
            if etapa not in primeras or fecha < primeras[etapa]:
                primeras[etapa] = fecha
        if not primeras:
            if _viva(h):
                abiertas.append(round(max(0, ahora_ms - creada) / MS_POR_HORA, 4))
            continue
        for etapa, fecha in primeras.items():
            if fecha < creada:
                fechas_invertidas += 1
            horas = round(max(0, fecha - creada) / MS_POR_HORA, 4)
            duraciones.append(horas)
            por_etapa.setdefault(etapa, []).append(horas)
            detalle.append({"hipotesisId": h.get("id"), "etapa": etapa, "horas": round(horas, 2), "creadaEn": creada, "decididaEn": fecha})
    return {
        "casos": len(duraciones),
        "hipotesis": len(hipotesis),
        "medianaHoras": _mediana(duraciones),
        "p90Horas": _p90(duraciones),
        "porEtapa": {etapa: {"casos": len(v), "medianaHoras": _mediana(v)} for etapa, v in sorted(por_etapa.items(), key=lambda kv: (ETAPAS.index(kv[0]) if kv[0] in ETAPAS else len(ETAPAS), kv[0]))},
        "abiertasSinDecision": len(abiertas),
        "abiertasSinDecisionHoras": _mediana(abiertas),
        "sinFechaCreacion": sin_fecha_creacion,
        "decisionesSinFecha": decisiones_sin_fecha,
        "fechasInvertidas": fechas_invertidas,
        "detalle": detalle,
        "regla": REGLA_TIEMPO,
    }


# ---------------------------------------------------------------------------
# 3. Reutilización de lo heredado
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"[\w-]+")


def _referencia_normalizada(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v).strip().lower()) if isinstance(v, str) and v.strip() else ""


def _hecho_heredado(h: dict[str, Any], investigacion_id: str, ids_todos: set[str]) -> bool:
    """La regla canónica (sufijo con '-inv-') más el caso de una investigación
    cuyo id no empieza por 'inv-': el id termina en '-<investigación>' y el
    original, sin el sufijo, existe en el registro."""
    if es_heredado(h):
        return True
    id_ = _texto(h.get("id"))
    sufijo = f"-{investigacion_id}"
    return bool(investigacion_id) and id_.endswith(sufijo) and id_[: -len(sufijo)] in ids_todos


def _id_original(h: dict[str, Any], investigacion_id: str) -> str:
    id_ = _texto(h.get("id"))
    sufijo = f"-{investigacion_id}"
    return id_[: -len(sufijo)] if investigacion_id and id_.endswith(sufijo) else id_


def _huellas_hipotesis(h: dict[str, Any]) -> dict[str, Any]:
    """Lo que deja huella de un hecho en una hipótesis: sus afirmaciones, los ids
    y referencias de sus fuentes, y las palabras enteras de su procedencia
    (registro y mensajes), para buscar ids de hechos sin regex por par."""
    afirmaciones = {_texto(a.get("afirmacionId")) for a in _lista(h.get("afirmaciones")) if isinstance(a, dict)} - {""}
    proc = _dict(h.get("procedencia"))
    fuentes = [f for f in _lista(proc.get("fuentes")) if isinstance(f, dict)]
    ids_fuentes = {_texto(f.get("id")) for f in fuentes} - {""}
    referencias = {_referencia_normalizada(f.get("referencia")) for f in fuentes} - {""}
    textos = [m.get("texto") for m in _lista(proc.get("mensajes")) if isinstance(m, dict)] + _lista(proc.get("registro"))
    texto = "\n".join(t for t in textos if isinstance(t, str))
    return {"afirmaciones": afirmaciones, "fuentes": ids_fuentes, "referencias": referencias, "texto": texto, "tokens": set(_TOKEN.findall(texto))}


def _nombrado_en(texto: str, id_: str) -> bool:
    """El id aparece como palabra entera (no 'he-1' dentro de 'he-10')."""
    return bool(id_) and re.search(rf"(?<![\w-]){re.escape(id_)}(?![\w-])", texto) is not None


def reutilizacion_heredada(e: dict[str, Any], investigacion_id: str) -> dict[str, Any]:
    """Cuántos de los hechos heredados de otra investigación se usaron en
    alguna hipótesis de esta. Ver REGLA_REUTILIZACION. Lineal: cada huella de
    las hipótesis se indexa una vez y cada hecho consulta los índices."""
    hechos = _dicts(e, "hechos")
    ids_todos = {_texto(x.get("id")) for x in hechos} - {""}
    heredados = [x for x in hechos if x.get("investigacionId") == investigacion_id and _hecho_heredado(x, investigacion_id, ids_todos)]
    hipotesis = [h for h in _hipotesis_de(e, investigacion_id) if isinstance(h.get("id"), str)]
    huellas = [_huellas_hipotesis(h) for h in hipotesis]
    vivas = [_viva(h) for h in hipotesis]
    # Índices invertidos: de cada huella a las posiciones (en el orden del
    # registro) de las hipótesis que la llevan. Las reglas 1 (afirmación) y 2
    # (fuente) solo miran hipótesis vivas; la 3 (nombrado) mira todas.
    por_afirmacion: dict[str, list[int]] = {}
    por_fuente: dict[str, list[int]] = {}
    por_referencia: dict[str, list[int]] = {}
    por_token: dict[str, list[int]] = {}
    for i, hu in enumerate(huellas):
        if vivas[i]:
            for a in hu["afirmaciones"]:
                por_afirmacion.setdefault(a, []).append(i)
            for f in hu["fuentes"]:
                por_fuente.setdefault(f, []).append(i)
            for r in hu["referencias"]:
                por_referencia.setdefault(r, []).append(i)
        for t in hu["tokens"]:
            por_token.setdefault(t, []).append(i)
    detalle: list[dict[str, Any]] = []
    con_herencia: set[str] = set()
    usados = 0
    for x in heredados:
        afirm = {_texto(a) for a in _lista(x.get("afirmacionIds")) if _texto(a)}
        proc = [p for p in _lista(x.get("procedencia")) if isinstance(p, dict)]
        fuentes = {_texto(p.get("fuenteId")) for p in proc} - {""}
        refs = {_referencia_normalizada(p.get("referencia")) for p in proc} - {""}
        ids_hecho = {_texto(x.get("id")), _id_original(x, investigacion_id)} - {""}
        sabido = _clave(x.get("estado")) == "sabido"
        por_afirm = {i for a in afirm for i in por_afirmacion.get(a, ())}
        por_fuen = {i for f in fuentes for i in por_fuente.get(f, ())} | {i for r in refs for i in por_referencia.get(r, ())}
        por_nombre: set[int] = set()
        if sabido:
            for id_ in ids_hecho:
                if _TOKEN.fullmatch(id_):
                    por_nombre.update(por_token.get(id_, ()))
                else:  # un id con otros caracteres: la regex de palabra entera, como respaldo
                    por_nombre.update(i for i, hu in enumerate(huellas) if _nombrado_en(hu["texto"], id_))
        usado_por: list[str] = []
        motivos: list[str] = []
        for i in sorted(por_afirm | por_fuen | por_nombre):
            usado_por.append(hipotesis[i]["id"])
            if i in por_afirm:
                motivos.append("comparte afirmación con una hipótesis viva")
            elif i in por_fuen:
                motivos.append("comparte fuente con una hipótesis viva")
            else:
                motivos.append("sabido y nombrado en la procedencia de una hipótesis")
        if usado_por:
            usados += 1
            con_herencia.update(usado_por)
        detalle.append({"hechoId": x.get("id"), "estado": _texto(x.get("estado")) or None, "tema": _texto(x.get("tema")) or None, "usadoPor": usado_por, "motivo": "; ".join(dict.fromkeys(motivos)) or "ninguna hipótesis de esta investigación lo usa"})
    return {
        "hechosHeredados": len(heredados),
        "usados": usados,
        "tasa": _tasa(usados, len(heredados)),
        "hipotesisConHerencia": len(con_herencia),
        "hipotesisVivas": sum(1 for v in vivas if v),
        "detalle": detalle,
        "regla": REGLA_REUTILIZACION,
    }


# ---------------------------------------------------------------------------
# Resumen y texto en llano
# ---------------------------------------------------------------------------


def resumen_cifras(e: dict[str, Any], investigacion_id: str, ahora: int | None = None) -> dict[str, Any]:
    """Las tres cifras de una investigación, con su texto en llano y el glosario."""
    r = {
        "investigacionId": investigacion_id,
        "fecha": _ahora_ms(ahora),
        "acierto": acierto_prerregistrado(e, investigacion_id),
        "tiempo": tiempo_hasta_decision(e, investigacion_id, ahora),
        "reutilizacion": reutilizacion_heredada(e, investigacion_id),
        "glosario": dict(GLOSARIO),
    }
    r["texto"] = texto_cifras(r)
    return r


def _n(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _entero(v: Any) -> int:
    """Un contador del resumen leído con tolerancia: None, texto o bool valen 0."""
    if isinstance(v, bool) or v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError, OverflowError):
        return 0


def _horas_txt(h: Any) -> str:
    """Horas en llano: minutos por debajo de una hora, días a partir de dos."""
    if isinstance(h, bool) or not isinstance(h, (int, float)) or h != h:
        return "sin dato"
    h = max(0.0, float(h))
    if h < 1:
        m = int(round(h * 60))
        if m < 60:
            return _n(m, "minuto", "minutos")
        h = 1.0  # 59,6 minutos se redondean a una hora, no a "60 minutos"
    if h >= 48:
        return f"{h / 24:.1f}".replace(".", ",") + " días"
    return f"{h:.1f}".replace(".", ",") + " horas"


def _texto_acierto(a: dict[str, Any]) -> str:
    con = _entero(a.get("conDireccion"))
    sin_dir, no_ev = _entero(a.get("sinDireccion")), _entero(a.get("noEvaluables"))
    aparte = []
    if sin_dir:
        aparte.append(_n(sin_dir, "caso sin dirección declarada", "casos sin dirección declarada"))
    if no_ev:
        aparte.append(_n(no_ev, "no evaluable", "no evaluables"))
    total_aparte = sin_dir + no_ev
    cola = f" Aparte {'queda' if total_aparte == 1 else 'quedan'} {' y '.join(aparte)}, que no {'entra' if total_aparte == 1 else 'entran'} en la cuenta." if aparte else ""
    if con == 0:
        return "Todavía no hay predicciones prerregistradas (lo que ROSA2018 dejó escrito que esperaba ver antes de mirar los datos) con dirección y resultado evaluable: el acierto no se puede medir." + cola
    ok = _entero(a.get("aciertos"))
    frase = f"De {_n(con, 'predicción prerregistrada', 'predicciones prerregistradas')} con dirección, {ok} {'salió' if ok == 1 else 'salieron'} como se dijo"
    pf = _dict(a.get("porFuente"))
    an, lab = _dict(pf.get("analisis")), _dict(pf.get("laboratorio"))
    partes = []
    if _entero(an.get("conDireccion")):
        partes.append(f"{_entero(an.get('aciertos'))} de {_entero(an.get('conDireccion'))} en análisis in silico")
    if _entero(lab.get("conDireccion")):
        partes.append(f"{_entero(lab.get('aciertos'))} de {_entero(lab.get('conDireccion'))} en el laboratorio")
    if len(partes) > 1:
        frase += f" ({'; '.join(partes)})"
    return frase + "." + cola


def _texto_tiempo(t: dict[str, Any]) -> str:
    casos = _entero(t.get("casos"))
    abiertas = _entero(t.get("abiertasSinDecision"))
    cola = f" {_n(abiertas, 'hipótesis viva lleva', 'hipótesis vivas llevan')} {_horas_txt(t.get('abiertasSinDecisionHoras'))} de mediana sin ninguna decisión." if abiertas else ""
    if casos == 0:
        return "Ninguna hipótesis tiene todavía una decisión registrada, así que el tiempo hasta decidir no se puede medir." + cola
    frase = f"Desde que nace una hipótesis hasta su primera decisión de cada etapa pasan {_horas_txt(t.get('medianaHoras'))} de mediana (el valor del medio) y {_horas_txt(t.get('p90Horas'))} en el 90 % de los casos, sobre {_n(casos, 'decisión', 'decisiones')}"
    etapas = [f"{str(etapa).replace('_', ' ')}: {_horas_txt(_dict(v).get('medianaHoras'))}" for etapa, v in _dict(t.get("porEtapa")).items()]
    if len(etapas) > 1:
        frase += f" ({'; '.join(etapas)})"
    return frase + "." + cola


def _texto_reutilizacion(r: dict[str, Any]) -> str:
    n = _entero(r.get("hechosHeredados"))
    if n == 0:
        return "Esta investigación no heredó hechos de otra, así que la reutilización no aplica."
    usados = _entero(r.get("usados"))
    hips = _entero(r.get("hipotesisConHerencia"))
    return f"De {_n(n, 'hecho heredado', 'hechos heredados')} de otra investigación, {usados} se {'usó' if usados == 1 else 'usaron'} en alguna hipótesis de esta ({_n(hips, 'hipótesis con herencia', 'hipótesis con herencia')})."


def texto_cifras(resumen: dict[str, Any]) -> str:
    """Las tres cifras en castellano llano, una frase por cifra, con cada
    término definido la primera vez. Con algo que no es un diccionario
    devuelve ''; una cifra ausente o rota se dice como "no se puede medir"."""
    if not isinstance(resumen, dict):
        return ""
    return "\n".join([_texto_acierto(_dict(resumen.get("acierto"))), _texto_tiempo(_dict(resumen.get("tiempo"))), _texto_reutilizacion(_dict(resumen.get("reutilizacion")))])
