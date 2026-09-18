"""El grafo de la investigación, materializado en el backend.

Es el mismo árbol que la persona ve en la pantalla Árbol: el port uno a uno de
`construirArbol` (frontend/src/lib/arbol.ts). El objetivo es el tronco, las
áreas del programa y los clusters de mecanismo son las ramas, las hipótesis
son las hojas, y alrededor lo que las sostiene: hechos del modelo de mundo,
fuentes, entidades canónicas, relaciones causales, rivales del torneo y el
experimento que llegó al laboratorio. Las reglas de construcción (ids, orden,
qué arista se acepta) deben coincidir con el TS para que el Killer razone
sobre el mismo grafo que ve la persona.

Aquí se amplía con nodos de dato, igual que el TS desde el 16 de septiembre
de 2026:

- 'afirmacion': las afirmaciones de tipo dato de cada hipótesis.
- 'ejecucion': los análisis in silico (RunRecord) sobre una hipótesis.
- 'dataset': el dataset del plan congelado de cada ejecución.
- 'laboratorio': el resultado del laboratorio contra el prerregistro.

Y con la profundidad hasta el dato: cuántos saltos separan a cada nodo de la
medición propia más cercana (`profundidadDato`) y de la fuente leída más
cercana (`profundidadLiteratura`). Una hipótesis con profundidad 1 tiene un
dato propio al lado; una con None vive solo de literatura o de nada.

Todo sale del estado; no se inventa ningún enlace. Las claves de los nodos y
de las aristas son las del TS (camelCase); los identificadores de tipo van sin
tilde porque se comparan con la interfaz. Un registro antiguo al que le falta
una clave se lee con el valor que hoy tiene por defecto (una afirmación sin
`clase` es literatura, un experimento sin `estado` está propuesto), nunca se
infiere otra cosa ni se rompe.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict, deque
from typing import Any, Iterable

# Identificadores de tipo, sin tilde: se comparan con la interfaz.
TIPOS_NODO = ("objetivo", "rama", "area", "hipotesis", "hecho", "pregunta", "fuente", "entidad", "experimento", "afirmacion", "ejecucion", "dataset", "laboratorio")
TIPOS_ENLACE = ("rama", "cita", "respalda", "entidad", "causal", "rival", "experimento", "dato")

# Los mismos nombres legibles que NOMBRE_TIPO y NOMBRE_ENLACE del TS: lo que
# lee el Killer en un prompt se llama igual que lo que la persona ve en la leyenda.
NOMBRE_TIPO: dict[str, str] = {
    "objetivo": "Objetivo",
    "rama": "Cluster de mecanismo",
    "area": "Área del programa",
    "hipotesis": "Hipótesis",
    "hecho": "Hecho del modelo de mundo",
    "pregunta": "Pregunta abierta",
    "fuente": "Fuente",
    "entidad": "Entidad canónica",
    "experimento": "Experimento en el laboratorio",
    "afirmacion": "Afirmación con dato",
    "ejecucion": "Análisis in silico",
    "dataset": "Conjunto de datos",
    "laboratorio": "Resultado del laboratorio",
}

NOMBRE_ENLACE: dict[str, str] = {
    "rama": "pertenece a",
    "cita": "cita",
    "respalda": "respalda",
    "entidad": "nombra",
    "causal": "relación causal",
    "rival": "rival en el torneo",
    "experimento": "se prueba en",
    "dato": "dato",
}

# Las aristas por las que viaja la evidencia hacia una hipótesis. Las de
# 'rama' son estructura del árbol y las de 'rival' son el torneo; las de
# 'entidad' y 'causal' unen conceptos: una hipótesis no está más cerca de un
# dato por nombrar la misma proteína que otra que sí lo midió. La profundidad
# hasta el dato se calcula cruzando solo estas (misma lista que el TS).
ENLACES_EVIDENCIA = ("dato", "experimento", "respalda", "cita")

ELO_POR_DEFECTO = 1500
SIN_CLUSTER = "Sin cluster"
# Valor por defecto de hoy para una afirmación sin clase (registros anteriores al libro de procedencia).
CLASE_POR_DEFECTO = "literatura"
CLASES_MEDICION = ("observacion_original", "derivado")
VEREDICTOS_SOSTENIDOS = ("sostenida", "parcial")
VEREDICTOS_NO_SOSTENIDOS = ("no_sostenida", "cita_no_resuelve", "sin_cita", "ausencia_refutada")

# Prioridad al listar vecinos para un prompt: primero lo medido, luego lo leído.
_PRIORIDAD_TIPO = {t: i for i, t in enumerate(("ejecucion", "laboratorio", "afirmacion", "dataset", "experimento", "hecho", "pregunta", "fuente", "hipotesis", "entidad", "rama", "area", "objetivo"))}

_INVERSO_RESULTADO = {"gano": "perdio", "perdio": "gano"}

# Valores del servidor (sin tilde, se comparan) tal como se leen en un texto.
_LEGIBLE = {
    "no_ejecutado": "no ejecutado",
    "en_curso": "en curso",
    "error_tecnico": "error técnico",
    "tiempo_agotado": "tiempo agotado",
    "efecto_detectado": "efecto detectado",
    "sin_efecto_detectable": "sin efecto detectable",
    "no_evaluable": "no evaluable",
    "apoyo_reproducido": "apoyo reproducido",
    "negativo_interpretable": "negativo interpretable",
    "fallo_tecnico": "fallo técnico",
    "toxicidad_inviabilidad": "toxicidad o inviabilidad",
    "correccion_contexto": "corrección de contexto",
    "observacion_original": "observación original",
    "sin_veredicto": "sin veredicto",
    "cita_no_resuelve": "la cita no resuelve",
    "conocimiento_operativo": "conocimiento operativo",
    "prediccion": "predicción",
}
_AUDITORIA = {"valido": "válida", "no_valido": "no válida", "no_evaluable_computacionalmente": "no evaluable computacionalmente", None: "ausente"}


def _legible(valor: Any) -> str:
    """Un valor del servidor como lo lee una persona: con tilde y sin guiones bajos."""
    v = str(valor or "")
    return _LEGIBLE.get(v, v.replace("_", " "))


# ---------------------------------------------------------------------------
# Ayudas
# ---------------------------------------------------------------------------


def _ruta(inv_id: str, pantalla: str, detalle: str | None = None) -> str:
    """Misma forma que `rutaDe` del frontend: #/investigaciones/<id>/<pantalla>[/<detalle>]."""
    base = f"#/investigaciones/{inv_id}/{pantalla}"
    return f"{base}/{detalle}" if detalle else base


def _num(x: Any) -> str:
    """Un número como lo escribe la interfaz: 1500, no 1500.0."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    return str(int(f)) if f.is_integer() else str(round(f, 1))


def _clave(x: Any) -> str | None:
    """Un identificador usable como clave: cadena o entero; cualquier otra cosa
    (una lista, un diccionario, None, un booleano) es un registro malformado y no enlaza."""
    if isinstance(x, bool):
        return None
    return str(x) if isinstance(x, (str, int)) and str(x) != "" else None


def _lista(x: Any) -> list[Any]:
    """Un campo que debe ser lista: si falta o es otra cosa (None, cadena, número), se lee como vacío."""
    return x if isinstance(x, list) else []


def _dic(x: Any) -> dict[str, Any]:
    """Un campo que debe ser diccionario: si falta o es otra cosa, se lee como vacío."""
    return x if isinstance(x, dict) else {}


def _iteracion_de(h: dict[str, Any]) -> int:
    try:
        return int(h.get("iteracion") or 1)
    except (TypeError, ValueError):
        return 1


def _cluster_de(h: dict[str, Any]) -> str:
    return str(h.get("cluster") or SIN_CLUSTER)


def _recortar(texto: Any, largo: int = 90) -> str:
    t = " ".join(str(texto or "").split())
    return f"{t[: largo - 3]}..." if len(t) > largo else t


def _texto_no_vacio(x: Any) -> bool:
    """Un fragmento o texto cuenta solo si tiene algo más que espacios (el TS hace trim)."""
    return bool(str(x).strip()) if isinstance(x, str) else bool(x)


def _nodo(id_: str, tipo: str, etiqueta: str, peso: float, iteracion: int, sub: str | None = None, href: str | None = None, estado: str | None = None, alerta: str | None = None, alias: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    n: dict[str, Any] = {"id": str(id_), "tipo": tipo, "etiqueta": etiqueta, "sub": sub, "peso": peso, "iteracion": iteracion, "href": href, "estado": estado, "alerta": alerta, "alias": alias or []}
    n.update(extra)
    return n


def _copia(n: dict[str, Any]) -> dict[str, Any]:
    """Una copia de un nodo para devolverla fuera: quien la mute no toca el grafo cacheado."""
    return {**n, "alias": list(n.get("alias") or [])}


def hipotesis_de(e: dict[str, Any], inv_id: Any) -> list[dict[str, Any]]:
    """Las hipótesis de la investigación, descartando registros sin id o que no
    son diccionarios. El id de la investigación se compara como cadena, así
    que un id entero heredado enlaza igual."""
    objetivo = _clave(inv_id)
    return [h for h in _lista(_dic(e).get("hipotesis")) if isinstance(h, dict) and _clave(h.get("id")) and _clave(h.get("investigacionId")) == objetivo]


def hechos_de(e: dict[str, Any], inv_id: Any) -> list[dict[str, Any]]:
    """Los hechos y preguntas de la investigación, con la misma regla que `hipotesis_de`."""
    objetivo = _clave(inv_id)
    return [h for h in _lista(_dic(e).get("hechos")) if isinstance(h, dict) and _clave(h.get("id")) and _clave(h.get("investigacionId")) == objetivo]


def _fuentes_de_hipotesis(h: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in _lista(_dic(h.get("procedencia")).get("fuentes")) if isinstance(f, dict) and _clave(f.get("id"))]


def _ejecuciones_de(e: dict[str, Any], hip: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[tuple[dict[str, Any], list[dict[str, Any]]]]]:
    """Las ejecuciones de cada hipótesis (en su orden), con la misma regla que
    el TS: primero las que la nombran en `hipotesisId` (en el orden del
    estado) y después las que ella lista en `ejecuciones` (en el orden de la
    lista), sin repetir. Una ejecución repetida en el estado cuenta una vez:
    la primera manda. Devuelve (ejecuciones por id, [(hipótesis, ejecuciones)])."""
    por_id: dict[str, dict[str, Any]] = {}
    por_hip: dict[str, list[dict[str, Any]]] = {}
    for r in _lista(_dic(e).get("ejecuciones")):
        if not isinstance(r, dict):
            continue
        rid = _clave(r.get("id"))
        if not rid or rid in por_id:
            continue
        por_id[rid] = r
        hid = _clave(r.get("hipotesisId"))
        if hid:
            por_hip.setdefault(hid, []).append(r)
    salida = []
    for h in hip:
        vistas: set[str] = set()
        propias: list[dict[str, Any]] = []
        for r in [*por_hip.get(str(h["id"]), []), *[por_id.get(_clave(x) or "") for x in _lista(h.get("ejecuciones"))]]:
            if r is None or str(r["id"]) in vistas:
                continue
            vistas.add(str(r["id"]))
            propias.append(r)
        salida.append((h, propias))
    return por_id, salida


def iteracion_en(iteraciones: Iterable[Any], t: Any) -> int | None:
    """La iteración de la investigación en marcha en el instante `t` (ms): la
    que lo contiene (empezó antes y no había terminado) o, en un hueco entre
    dos (esperando la aprobación de un plan), la última que había empezado.
    Con varias candidatas gana la que empezó más tarde, sea cual sea el orden
    de la lista, para que el resultado no dependa de cómo llegó el estado.
    None si no hay iteraciones fechadas antes de `t` (registro antiguo).
    Mismo comportamiento que `iteracionEn` del TS."""
    if isinstance(t, bool) or not isinstance(t, (int, float)) or t != t or t in (float("inf"), float("-inf")):
        return None
    contiene: dict[str, Any] | None = None
    previa: dict[str, Any] | None = None
    for it in iteraciones:
        if not isinstance(it, dict):
            continue
        empieza = it.get("empezadaEn")
        if isinstance(empieza, bool) or not isinstance(empieza, (int, float)) or empieza > t:
            continue
        termina = it.get("terminadaEn")
        abierta = termina is None or not isinstance(termina, (int, float)) or t <= termina
        mejor = contiene if abierta else previa
        numero = _iteracion_de({"iteracion": it.get("numero")})
        if mejor is None or empieza > mejor["empezadaEn"] or (empieza == mejor["empezadaEn"] and numero > mejor["numero"]):
            elegida = {"empezadaEn": empieza, "numero": numero}
            if abierta:
                contiene = elegida
            else:
                previa = elegida
    ganadora = contiene or previa
    return ganadora["numero"] if ganadora else None


# ---------------------------------------------------------------------------
# Qué cuenta como medición propia y como literatura leída
# ---------------------------------------------------------------------------


def es_medicion_propia(n: dict[str, Any]) -> tuple[bool, str]:
    """MEDICIÓN PROPIA: un dato que ROSA2018 o el laboratorio produjeron, no que
    leyeron. Cuenta como tal, y solo esto:

    - un nodo 'ejecucion' con estado 'completado' y auditoría 'valido' (el
      código corrió y el auditor independiente lo dio por bueno);
    - un nodo 'laboratorio' (un resultado del laboratorio contra el prerregistro);
    - un nodo 'afirmacion' de clase 'observacion_original' o 'derivado', no
      sintética y con veredicto 'sostenida' o 'parcial'.

    Una afirmación sin clase es literatura (el valor de hoy) y no cuenta; un
    análisis en curso, con error técnico o con tiempo agotado no es una
    medición ("tiempo agotado" no es "sin efecto"). Devuelve (cuenta, motivo)
    para que la regla sea explicable."""
    tipo = n.get("tipo")
    if tipo == "ejecucion":
        if n.get("estado") != "completado":
            return False, f"ejecución con estado {_legible(n.get('estado')) or 'desconocido'}, no completada"
        if n.get("auditoria") != "valido":
            return False, f"ejecución completada pero auditoría {_AUDITORIA.get(n.get('auditoria'), _legible(n.get('auditoria')))}"
        return True, "ejecución completada y auditada como válida"
    if tipo == "laboratorio":
        return True, "resultado del laboratorio contra el prerregistro"
    if tipo == "afirmacion":
        if n.get("clase") not in CLASES_MEDICION:
            return False, f"afirmación de clase {_legible(n.get('clase')) or 'sin clase'}, no es observación ni derivado"
        if n.get("sintetico"):
            return False, "afirmación sobre datos sintéticos: no cuenta como evidencia"
        if n.get("veredicto") not in VEREDICTOS_SOSTENIDOS:
            return False, f"afirmación con veredicto {_legible(n.get('veredicto')) or 'sin veredicto'}"
        return True, "afirmación de dato propio sostenida" if n.get("veredicto") == "sostenida" else "afirmación de dato propio sostenida en parte"
    return False, f"un nodo de tipo {tipo} no es una medición"


def es_literatura_leida(n: dict[str, Any]) -> tuple[bool, str]:
    """LITERATURA LEÍDA: un nodo 'fuente' de la que ROSA2018 tiene el texto completo
    o al menos un fragmento literal (no en blanco). Una fuente solo citada,
    sin pasaje, no cuenta: nadie la leyó."""
    if n.get("tipo") != "fuente":
        return False, f"un nodo de tipo {n.get('tipo')} no es una fuente"
    if n.get("leida"):
        return True, "fuente con texto completo o fragmento literal"
    return False, "fuente citada sin texto completo ni fragmento"


def _fuente_leida(f: dict[str, Any]) -> bool:
    """La regla de la marca de lectura de una fuente: texto completo o un fragmento con algo más que espacios."""
    return bool(f.get("textoCompleto")) or _texto_no_vacio(f.get("fragmento"))


# ---------------------------------------------------------------------------
# Construcción
# ---------------------------------------------------------------------------


def construir(e: dict[str, Any], inv: dict[str, Any]) -> dict[str, Any]:
    """Construye el grafo de la investigación `inv` a partir del estado `e`.

    Devuelve {"nodos", "enlaces", "vecinos", "porId", "iteracionMax"}, con los
    nodos ya anotados con `profundidadDato`, `profundidadLiteratura` y
    `medicion` (el motivo por el que cuentan como medición propia, o None).
    El orden de creación es el del TS y importa: una arista solo se acepta si
    sus dos extremos ya existen. Un estado o una investigación que no son
    diccionarios se leen como vacíos."""
    e = _dic(e)
    inv = _dic(inv)
    inv_id = _clave(inv.get("id")) or ""
    nodos: list[dict[str, Any]] = []
    enlaces: list[dict[str, Any]] = []
    vistos: set[str] = set()
    enlaces_vistos: set[str] = set()
    por_id: dict[str, dict[str, Any]] = {}

    def anadir(n: dict[str, Any]) -> None:
        if n["id"] in vistos:
            return
        vistos.add(n["id"])
        nodos.append(n)
        por_id[n["id"]] = n

    def enlazar(de: str, a: str, tipo: str, etiqueta: str | None = None) -> None:
        # Solo entre nodos que ya existen; sin bucles; sin duplicados (y para
        # 'rival' tampoco la inversa: un partido es una sola arista).
        de, a = str(de), str(a)
        if de == a or de not in vistos or a not in vistos:
            return
        clave = f"{de}|{a}|{tipo}"
        inversa = f"{a}|{de}|{tipo}"
        if clave in enlaces_vistos or (tipo == "rival" and inversa in enlaces_vistos):
            return
        enlaces_vistos.add(clave)
        enlaces.append({"de": de, "a": a, "tipo": tipo, "etiqueta": etiqueta})

    def bajar_iteracion(id_: str, iteracion: int) -> None:
        # Un nodo compartido nace en la primera iteración en la que existió.
        por_id[id_]["iteracion"] = min(por_id[id_]["iteracion"], iteracion)

    hip = hipotesis_de(e, inv_id)
    hechos = hechos_de(e, inv_id)
    corridas_inv = {_clave(c.get("id")) for c in _lista(e.get("corridas")) if isinstance(c, dict) and _clave(c.get("investigacionId")) == inv_id}
    iteraciones_inv = [i for i in _lista(e.get("iteraciones")) if isinstance(i, dict) and _clave(i.get("corridaId")) in corridas_inv]
    numeros = [_iteracion_de({"iteracion": i.get("numero")}) for i in iteraciones_inv]
    iteracion_max = max([1, *[_iteracion_de(h) for h in hip], *numeros])

    # Tronco y áreas del programa.
    anadir(_nodo("objetivo", "objetivo", str(inv.get("titulo") or ""), 4, 0, sub=str(inv.get("objetivo") or ""), href=_ruta(inv_id, "investigacion")))
    areas = [a for a in _lista(_dic(inv.get("mision")).get("areas")) if isinstance(a, dict) and _clave(a.get("id"))]
    for a in areas:
        anadir(_nodo(f"area-{a['id']}", "area", str(a.get("titulo") or ""), 2, 0, sub=str(a.get("familiaMecanismo") or ""), estado=a.get("estado"), href=_ruta(inv_id, "investigacion")))
        enlazar("objetivo", f"area-{a['id']}", "rama")

    # Una rama solo cuando agrupa dos o más hipótesis: un cluster con una sola
    # hipótesis no aporta nada como nodo. Esas hipótesis cuelgan del tronco.
    # Se agrupa en una pasada (el orden de aparición es el del TS).
    por_cluster: dict[str, list[dict[str, Any]]] = {}
    for h in hip:
        por_cluster.setdefault(_cluster_de(h), []).append(h)
    con_rama: set[str] = set()
    for c, n in por_cluster.items():
        if len(n) < 2:
            continue
        con_rama.add(c)
        anadir(_nodo(f"rama-{c}", "rama", c, 2 + min(3, len(n)) * 0.4, min(_iteracion_de(h) for h in n), sub=f"{len(n)} hipótesis", href=_ruta(inv_id, "ranking")))
        enlazar("objetivo", f"rama-{c}", "rama")
        # Un área cuyo título o familia coincide con el cluster lo adopta.
        area = next((a for a in areas if str(a.get("titulo") or "").lower() == c.lower() or str(a.get("familiaMecanismo") or "").lower() == c.lower()), None)
        if area:
            enlazar(f"area-{area['id']}", f"rama-{c}", "rama")

    # Hipótesis y su experimento en el laboratorio.
    for h in hip:
        bloqueos = _lista(h.get("bloqueos"))
        if h.get("estado") == "descartada":
            alerta: str | None = "descartada"
        elif h.get("decisionKiller") == "descartar_en_contexto":
            alerta = "el Killer propone descartar"
        elif bloqueos:
            alerta = f"{len(bloqueos)} {'bloqueo' if len(bloqueos) == 1 else 'bloqueos'}"
        else:
            alerta = None
        elo = h.get("elo")
        if elo is None:
            elo = ELO_POR_DEFECTO
        try:
            elo_f = float(elo)
        except (TypeError, ValueError):
            elo_f = float(ELO_POR_DEFECTO)
        sub = f"{_cluster_de(h)} · Elo {_num(elo)}" + (" · candidata" if h.get("candidata") else "")
        anadir(_nodo(h["id"], "hipotesis", str(h.get("titulo") or ""), 1.5 + max(0.0, (elo_f - 1300) / 200), _iteracion_de(h), sub=sub, href=_ruta(inv_id, "hipotesis", h["id"]), estado=h.get("estado"), alerta=alerta))
        enlazar(f"rama-{_cluster_de(h)}" if _cluster_de(h) in con_rama else "objetivo", h["id"], "rama")
        ex = _dic(h.get("experimento"))
        # Un experimento sin estado se trata como propuesto (el valor de hoy): no llegó al laboratorio.
        if ex and (ex.get("estado") or "propuesto") != "propuesto":
            etiqueta = f"Experimento en {ex['laboratorio']}" if ex.get("laboratorio") else "Experimento"
            anadir(_nodo(f"ex-{h['id']}", "experimento", etiqueta, 2, _iteracion_de(h), sub=str(ex.get("estado")).replace("_", " ") + (" · prerregistrado" if ex.get("prerregistradoEn") else ""), href=_ruta(inv_id, "hipotesis", h["id"]), estado=ex.get("estado")))
            enlazar(h["id"], f"ex-{h['id']}", "experimento")

    # Entidades canónicas: un nodo por identificador, con sus alias.
    def entidad(x: Any, iteracion: int) -> str | None:
        if not isinstance(x, dict) or not _clave(x.get("id")):
            return None
        id_ = f"ent-{x['id']}"
        if id_ not in vistos:
            anadir(_nodo(id_, "entidad", str(x.get("etiqueta") or x["id"]), 1, iteracion, sub=f"{x.get('ontologia') or ''} {x['id']} · {x.get('tipo') or ''}".strip(), alias=[str(x["id"]), *[str(a) for a in _lista(x.get("alias"))]]))
        else:
            bajar_iteracion(id_, iteracion)
        return id_

    for h in hip:
        for x in _lista(h.get("entidades")):
            id_ent = entidad(x, _iteracion_de(h))
            if id_ent:
                enlazar(h["id"], id_ent, "entidad")

    # Hechos y preguntas del modelo de mundo, unidos a las hipótesis que
    # comparten fuente (o que los originaron). Con un índice fuente -> hipótesis
    # el coste es lineal en hechos y en citas, no hechos por hipótesis.
    fuentes_de: list[set[str]] = [{_clave(f["id"]) or "" for f in _fuentes_de_hipotesis(h)} for h in hip]
    posicion_hip: dict[str, int] = {}
    hip_por_fuente: dict[str, set[int]] = {}
    for i, h in enumerate(hip):
        posicion_hip.setdefault(str(h["id"]), i)
        for fid in fuentes_de[i]:
            hip_por_fuente.setdefault(fid, set()).add(i)
    for he in hechos:
        he_id = str(he["id"])
        tipo = "pregunta" if he.get("tipo") == "pregunta" or he.get("estado") == "abierto" else "hecho"
        procedencia = [p for p in _lista(he.get("procedencia")) if isinstance(p, dict)]
        posiciones: set[int] = set()
        if he_id.startswith("he-") and he_id[3:] in posicion_hip:
            posiciones.add(posicion_hip[he_id[3:]])
        for p in procedencia:
            posiciones |= hip_por_fuente.get(_clave(p.get("fuenteId")) or "", set())
        relacionadas = [hip[i] for i in sorted(posiciones)]
        iteracion = min(_iteracion_de(h) for h in relacionadas) if relacionadas else iteracion_max
        anadir(_nodo(f"he-{he_id}", tipo, _recortar(he.get("enunciado"), 90), 1 + min(2.0, len(relacionadas) * 0.3), iteracion, sub=f"{he.get('tema') or ''} · {he.get('estado') or ''}", href=_ruta(inv_id, "mundo"), estado=he.get("estado")))
        for h in relacionadas:
            enlazar(f"he-{he_id}", h["id"], "respalda")
        for x in _lista(he.get("entidades")):
            id_ent = entidad(x, iteracion)
            if id_ent:
                enlazar(f"he-{he_id}", id_ent, "entidad")

    # Fuentes: un nodo por artículo, citado por las hipótesis (y respaldando
    # hechos). Una fuente está leída si alguna de sus citas trae el texto
    # completo o un fragmento: la marca se sube en cualquier cita, no solo en
    # la primera (misma regla que el TS).
    for h in hip:
        for f in _fuentes_de_hipotesis(h):
            id_ = f"fu-{f['id']}"
            if id_ not in vistos:
                retraccion = f.get("retraccion")
                anadir(_nodo(id_, "fuente", str(f.get("referencia") or ""), 1, _iteracion_de(h), sub=str(f.get("titulo") or ""), alerta=f"marca editorial: {retraccion}" if retraccion else None, estado=retraccion or None, leida=_fuente_leida(f)))
            elif _fuente_leida(f) and not por_id[id_]["leida"]:
                por_id[id_]["leida"] = True
            enlazar(h["id"], id_, "cita")
    for he in hechos:
        for p in _lista(he.get("procedencia")):
            fid = _clave(p.get("fuenteId")) if isinstance(p, dict) else None
            if fid and f"fu-{fid}" in vistos:
                enlazar(f"fu-{fid}", f"he-{he['id']}", "respalda")

    # Relaciones causales de cada hipótesis, entre entidades canónicas.
    for h in hip:
        g = h.get("grafoCausal")
        if not isinstance(g, dict):
            continue
        canon = {_clave(n.get("id")): _clave(n.get("idCanonico")) for n in _lista(g.get("nodos")) if isinstance(n, dict) and _clave(n.get("id"))}
        for a in _lista(g.get("aristas")):
            if not isinstance(a, dict):
                continue
            de = canon.get(_clave(a.get("de")))
            hasta = canon.get(_clave(a.get("a")))
            if de and hasta and f"ent-{de}" in vistos and f"ent-{hasta}" in vistos:
                enlazar(f"ent-{de}", f"ent-{hasta}", "causal", str(a.get("tipo") or "").replace("_", " "))

    # Rivales del torneo.
    for h in hip:
        for p in _lista(h.get("partidos")):
            rival = _clave(p.get("rivalId")) if isinstance(p, dict) else None
            if rival and rival in vistos:
                enlazar(h["id"], rival, "rival", p.get("resultado") if isinstance(p.get("resultado"), str) else None)

    # ---- Ampliación: nodos de dato, en el orden del TS (por hipótesis:
    # afirmaciones, análisis con su dataset, laboratorio; al final, la arista
    # de cada afirmación a la ejecución que produjo su cifra). ----------------
    planes = {_clave(p.get("id")): p for p in _lista(e.get("planesAnalisis")) if isinstance(p, dict) and _clave(p.get("id"))}
    datasets = {_clave(d.get("id")): d for d in _lista(inv.get("datasets")) if isinstance(d, dict) and _clave(d.get("id"))}
    run_por_id, runs_por_hip = _ejecuciones_de(e, hip)
    # El nodo de una ejecución lleva su id, salvo que ese id ya sea de otro nodo
    # (una hipótesis con el mismo identificador): entonces va con prefijo 'ej-',
    # para no pisar la hipótesis ni unir dos hipótesis con una arista 'dato' inventada.
    nodo_de_ejecucion: dict[str, str] = {}

    def id_nodo_ejecucion(run: dict[str, Any]) -> str:
        rid = str(run["id"])
        if rid not in nodo_de_ejecucion:
            nodo_de_ejecucion[rid] = f"ej-{rid}" if rid in vistos and por_id[rid]["tipo"] != "ejecucion" else rid
        return nodo_de_ejecucion[rid]

    def iteracion_de_ejecucion(h: dict[str, Any], run: dict[str, Any] | None) -> int:
        # Cuándo corrió un análisis: la iteración en marcha en su instante de inicio,
        # nunca antes de que naciera la hipótesis; sin iteraciones fechadas, la de la hipótesis.
        it_h = _iteracion_de(h)
        en_marcha = iteracion_en(iteraciones_inv, run.get("inicio")) if run else None
        return max(it_h, en_marcha if en_marcha is not None else it_h)

    def id_afirmacion(h: dict[str, Any], af: dict[str, Any], i: int) -> str:
        return f"af-{_clave(af.get('afirmacionId'))}" if _clave(af.get("afirmacionId")) else f"af-{h['id']}-{i}"

    def afirmaciones_de_dato(h: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
        return [(i, af) for i, af in enumerate(_lista(h.get("afirmaciones"))) if isinstance(af, dict) and af.get("tipo") == "dato"]

    for h, ejecuciones_h in runs_por_hip:
        it_h = _iteracion_de(h)
        # Afirmaciones de tipo dato. Una afirmación compartida (afirmacionId) es un
        # solo nodo enlazado a todas las hipótesis que la usan.
        for i, af in afirmaciones_de_dato(h):
            id_ = id_afirmacion(h, af, i)
            tray = _clave(_dic(af.get("trayectoria")).get("id"))
            # Una afirmación derivada de un análisis no trae iteración propia: es la del análisis.
            if af.get("iteracion") is not None:
                it_af = _iteracion_de(af)
            elif tray:
                it_af = iteracion_de_ejecucion(h, run_por_id.get(tray))
            else:
                it_af = it_h
            if id_ not in vistos:
                # Sin clase se lee 'literatura', el valor de hoy: no se infiere de la trayectoria.
                clase = str(af.get("clase") or CLASE_POR_DEFECTO)
                sintetico = bool(af.get("sintetico"))
                veredicto = af.get("veredicto")
                if sintetico:
                    alerta_af: str | None = "dato sintético: no cuenta como evidencia"
                elif veredicto in VEREDICTOS_NO_SOSTENIDOS:
                    alerta_af = "el verificador no la sostiene"
                else:
                    alerta_af = None
                anadir(_nodo(id_, "afirmacion", _recortar(af.get("texto"), 90), 1, it_af, sub=f"{_legible(clase)} · {_legible(veredicto or 'sin_veredicto')}" + (" · sintético" if sintetico else ""), href=_ruta(inv_id, "hipotesis", h["id"]), estado=veredicto, alerta=alerta_af, clase=clase, sintetico=sintetico, veredicto=veredicto, cita=str(af.get("cita") or "")))
            else:
                bajar_iteracion(id_, it_af)
            enlazar(h["id"], id_, "dato")
        # Ejecuciones in silico sobre la hipótesis, con el dataset de su plan.
        for run in ejecuciones_h:
            rid = id_nodo_ejecucion(run)
            it_run = iteracion_de_ejecucion(h, run)
            if rid not in vistos:
                auditoria = _clave(_dic(run.get("auditoria")).get("veredicto"))
                interpretacion = _dic(run.get("interpretacion"))
                estado_run = str(run.get("estado") or "no_ejecutado")
                etiqueta = _recortar(interpretacion.get("resumen"), 90) or f"Ejecución {run['id']}"
                # Por qué no cuenta o hay que mirarlo con cuidado (mismas frases que el TS
                # para los tres casos que este nombra; los demás dicen por qué no cuenta).
                if estado_run in ("error_tecnico", "tiempo_agotado"):
                    alerta_run: str | None = f"{_legible(estado_run)}: no es \"sin efecto\""
                elif estado_run != "completado":
                    alerta_run = f"no cuenta: {_legible(estado_run)}"
                elif auditoria == "no_valido":
                    alerta_run = "el auditor no lo dio por válido"
                elif auditoria != "valido":
                    alerta_run = f"auditoría {_AUDITORIA.get(auditoria, _legible(auditoria))}" if auditoria else "sin auditoría"
                else:
                    alerta_run = None
                anadir(_nodo(rid, "ejecucion", etiqueta, 1.5, it_run, sub=f"{_legible(estado_run)} · auditoría {_AUDITORIA.get(auditoria, _legible(auditoria))}" + (f" · {_legible(interpretacion.get('estado'))}" if interpretacion.get("estado") else ""), href=_ruta(inv_id, "hipotesis", h["id"]), estado=estado_run, alerta=alerta_run, auditoria=auditoria, planId=run.get("planId"), ejecucionId=str(run["id"])))
            else:
                bajar_iteracion(rid, it_run)
            enlazar(h["id"], rid, "dato")
            # El conjunto de datos del plan. Sin plan ('sin-plan') o sin conjunto no hay nodo: no se inventa.
            plan = planes.get(_clave(run.get("planId")))
            ds_id = _clave(_dic(plan).get("datasetId"))
            if ds_id:
                if f"ds-{ds_id}" not in vistos:
                    ds = datasets.get(ds_id) or {}
                    proc = _dic(ds.get("procedencia"))
                    sintetico_ds = bool(proc.get("sintetico"))
                    anadir(_nodo(f"ds-{ds_id}", "dataset", str(ds.get("nombre") or ds_id), 1, it_run, sub=" · ".join(x for x in (str(ds.get("clasificacion") or ""), str(ds.get("estado") or ""), str(proc.get("origen") or "")) if x) or None, href=_ruta(inv_id, "investigacion"), estado=ds.get("estado"), alerta="sintético" if sintetico_ds else None, sintetico=sintetico_ds))
                else:
                    bajar_iteracion(f"ds-{ds_id}", it_run)
                enlazar(rid, f"ds-{ds_id}", "dato")
        # Resultado del laboratorio: cuelga del experimento, o de la hipótesis si no hay nodo de experimento.
        res = _dic(h.get("experimento")).get("resultado")
        if res and isinstance(res, dict):
            veredicto_lab = str(res.get("veredicto") or "sin_veredicto")
            anadir(_nodo(f"lab-{h['id']}", "laboratorio", f"Resultado del laboratorio: {_legible(veredicto_lab)}", 2, it_h, sub=_recortar(res.get("resultado") or _legible(res.get("clasificacion")), 90) or None, href=_ruta(inv_id, "hipotesis", h["id"]), estado=veredicto_lab, veredicto=veredicto_lab, clasificacion=res.get("clasificacion")))
            enlazar(f"ex-{h['id']}" if f"ex-{h['id']}" in vistos else h["id"], f"lab-{h['id']}", "dato")

    # La afirmación con dato apunta a la ejecución que produjo su cifra (solo si
    # esa ejecución está en el grafo: una trayectoria desconocida no crea nada).
    for h in hip:
        for i, af in afirmaciones_de_dato(h):
            tray = _clave(_dic(af.get("trayectoria")).get("id"))
            nodo_run = nodo_de_ejecucion.get(tray or "")
            if nodo_run:
                enlazar(id_afirmacion(h, af, i), nodo_run, "dato")

    # ---- Peso por conexiones para fuentes y entidades; vecinos -----------------
    grado: dict[str, int] = {}
    for en in enlaces:
        grado[en["de"]] = grado.get(en["de"], 0) + 1
        grado[en["a"]] = grado.get(en["a"], 0) + 1
    for n in nodos:
        if n["tipo"] in ("entidad", "fuente"):
            n["peso"] = 1 + min(2.5, grado.get(n["id"], 0) * 0.25)
    vecinos: dict[str, set[str]] = {}
    for en in enlaces:
        vecinos.setdefault(en["de"], set()).add(en["a"])
        vecinos.setdefault(en["a"], set()).add(en["de"])

    g = {"nodos": nodos, "enlaces": enlaces, "vecinos": vecinos, "porId": por_id, "iteracionMax": iteracion_max}
    profundidades(g)
    return g


# ---------------------------------------------------------------------------
# Profundidad hasta el dato
# ---------------------------------------------------------------------------


def _distancias(g: dict[str, Any], fuentes: Iterable[str], enlaces: Iterable[str] | None) -> dict[str, int]:
    """BFS desde varias fuentes a la vez sobre vecinos no dirigidos: la
    distancia de cada nodo a la fuente más cercana. Si `enlaces` no es None,
    solo se cruzan aristas de esos tipos. Los vecinos se recorren ordenados
    para que el resultado no dependa del orden interno de los conjuntos."""
    permitidos = set(enlaces) if enlaces is not None else None
    ady: dict[str, set[str]] = {}
    for en in g["enlaces"]:
        if permitidos is not None and en["tipo"] not in permitidos:
            continue
        ady.setdefault(en["de"], set()).add(en["a"])
        ady.setdefault(en["a"], set()).add(en["de"])
    dist: dict[str, int] = {}
    cola: deque[str] = deque()
    for f in fuentes:
        if f not in dist:
            dist[f] = 0
            cola.append(f)
    while cola:
        actual = cola.popleft()
        for v in sorted(ady.get(actual, ())):
            if v not in dist:
                dist[v] = dist[actual] + 1
                cola.append(v)
    return dist


def profundidades(g: dict[str, Any], enlaces: Iterable[str] | None = ENLACES_EVIDENCIA) -> dict[str, Any]:
    """Anota en cada nodo `profundidadDato` (saltos hasta la medición propia
    más cercana, ver `es_medicion_propia`), `profundidadLiteratura` (saltos
    hasta la fuente leída más cercana, ver `es_literatura_leida`) y `medicion`
    (el motivo por el que el nodo cuenta como medición propia, o None). None
    si no hay camino. BFS sobre vecinos no dirigidos, cruzando solo las
    aristas de `enlaces` (por defecto las de evidencia; None cruza todas).
    Devuelve el mismo grafo, mutado."""
    mediciones = []
    for n in g["nodos"]:
        cuenta, motivo = es_medicion_propia(n)
        n["medicion"] = motivo if cuenta else None
        if cuenta:
            mediciones.append(n["id"])
    leidas = [n["id"] for n in g["nodos"] if es_literatura_leida(n)[0]]
    d_dato = _distancias(g, mediciones, enlaces)
    d_lit = _distancias(g, leidas, enlaces)
    for n in g["nodos"]:
        n["profundidadDato"] = d_dato.get(n["id"])
        n["profundidadLiteratura"] = d_lit.get(n["id"])
    return g


# ---------------------------------------------------------------------------
# Caché pequeña
# ---------------------------------------------------------------------------

_CACHE: "OrderedDict[tuple, dict[str, Any]]" = OrderedDict()
_CACHE_MAX = 4


def _max_tiempo(*valores: Any) -> int:
    m = 0
    for v in valores:
        try:
            m = max(m, int(v or 0))
        except (TypeError, ValueError):
            continue
    return m


def _huella(inv: dict[str, Any], hip: list[dict[str, Any]], hechos: list[dict[str, Any]], runs: list[dict[str, Any]], planes: list[Any], iteraciones: list[Any]) -> str:
    """Resumen (blake2b) de los campos que cambian la forma del grafo sin
    cambiar recuentos ni tiempos: una hipótesis que pasa a descartada, un
    experimento que llega al laboratorio, una ejecución que el auditor da por
    válida, una fuente que se lee más tarde, un veredicto que cambia. Se
    proyectan solo esos campos, no el registro entero (los mensajes, el
    código y los fragmentos no entran), así que cuesta mucho menos que
    construir el grafo."""

    def fuente(f: Any) -> tuple:
        f = _dic(f)
        return (_clave(f.get("id")), f.get("referencia"), f.get("titulo"), f.get("retraccion"), bool(f.get("textoCompleto")), _texto_no_vacio(f.get("fragmento")))

    def entidad(x: Any) -> tuple:
        x = _dic(x)
        return (_clave(x.get("id")), x.get("etiqueta"), x.get("ontologia"), x.get("tipo"), tuple(str(a) for a in _lista(x.get("alias"))))

    def afirmacion(a: Any) -> tuple:
        a = _dic(a)
        return (a.get("tipo"), _clave(a.get("afirmacionId")), a.get("clase"), bool(a.get("sintetico")), a.get("veredicto"), a.get("texto"), a.get("cita"), _clave(_dic(a.get("trayectoria")).get("id")), a.get("iteracion"))

    def hipotesis(h: dict[str, Any]) -> tuple:
        ex = _dic(h.get("experimento"))
        res = _dic(ex.get("resultado"))
        gc = _dic(h.get("grafoCausal"))
        return (
            _clave(h.get("id")), h.get("titulo"), h.get("cluster"), h.get("elo"), bool(h.get("candidata")), h.get("estado"), h.get("decisionKiller"), len(_lista(h.get("bloqueos"))), h.get("iteracion"),
            (bool(ex), ex.get("estado"), ex.get("laboratorio"), bool(ex.get("prerregistradoEn")), bool(res), res.get("veredicto"), res.get("resultado"), res.get("clasificacion")),
            tuple(entidad(x) for x in _lista(h.get("entidades"))),
            tuple(fuente(f) for f in _lista(_dic(h.get("procedencia")).get("fuentes"))),
            tuple((_clave(_dic(n).get("id")), _clave(_dic(n).get("idCanonico"))) for n in _lista(gc.get("nodos"))),
            tuple((_clave(_dic(a).get("de")), _clave(_dic(a).get("a")), _dic(a).get("tipo")) for a in _lista(gc.get("aristas"))),
            tuple((_clave(_dic(p).get("rivalId")), _dic(p).get("resultado")) for p in _lista(h.get("partidos"))),
            tuple(afirmacion(a) for a in _lista(h.get("afirmaciones"))),
            tuple(_clave(r) for r in _lista(h.get("ejecuciones"))),
        )

    def hecho(he: dict[str, Any]) -> tuple:
        return (_clave(he.get("id")), he.get("tipo"), he.get("estado"), he.get("tema"), he.get("enunciado"), tuple(_clave(_dic(p).get("fuenteId")) for p in _lista(he.get("procedencia"))), tuple(entidad(x) for x in _lista(he.get("entidades"))))

    def ejecucion(r: dict[str, Any]) -> tuple:
        return (_clave(r.get("id")), _clave(r.get("hipotesisId")), r.get("estado"), _clave(_dic(r.get("auditoria")).get("veredicto")), _clave(r.get("planId")), _dic(r.get("interpretacion")).get("estado"), _dic(r.get("interpretacion")).get("resumen"), r.get("inicio"))

    def dataset(d: Any) -> tuple:
        d = _dic(d)
        proc = _dic(d.get("procedencia"))
        return (_clave(d.get("id")), d.get("nombre"), d.get("clasificacion"), d.get("estado"), proc.get("origen"), bool(proc.get("sintetico")))

    proyeccion = (
        inv.get("titulo"), inv.get("objetivo"),
        tuple((_clave(_dic(i).get("corridaId")), _dic(i).get("numero"), _dic(i).get("empezadaEn"), _dic(i).get("terminadaEn")) for i in iteraciones),
        tuple((_clave(_dic(a).get("id")), _dic(a).get("titulo"), _dic(a).get("familiaMecanismo"), _dic(a).get("estado")) for a in _lista(_dic(inv.get("mision")).get("areas"))),
        tuple(dataset(d) for d in _lista(inv.get("datasets"))),
        tuple(hipotesis(h) for h in hip),
        tuple(hecho(he) for he in hechos),
        tuple(ejecucion(r) for r in runs),
        tuple((_clave(_dic(p).get("id")), _clave(_dic(p).get("datasetId"))) for p in planes),
    )
    return hashlib.blake2b(repr(proyeccion).encode("utf-8"), digest_size=16).hexdigest()


def clave_cache(e: dict[str, Any], inv: dict[str, Any]) -> tuple:
    """Clave de la caché: id de la investigación, recuentos de hipótesis,
    hechos y ejecuciones (y de afirmaciones, fuentes y partidos, que cambian
    sin que cambie el número de hipótesis), el mayor tiempo que se encuentre
    (creadaEn, actualizadoEn, fin de ejecución, última revisión) y la huella
    de los campos que dan forma al grafo (`_huella`), para que un cambio en
    sitio sin recuentos ni tiempos nuevos no devuelva un grafo viejo."""
    e = _dic(e)
    inv = _dic(inv)
    inv_id = _clave(inv.get("id")) or ""
    hip = hipotesis_de(e, inv_id)
    hechos = hechos_de(e, inv_id)
    ids_hip = {_clave(h.get("id")) for h in hip}
    runs = [r for r in _lista(e.get("ejecuciones")) if isinstance(r, dict) and (_clave(r.get("investigacionId")) == inv_id or _clave(r.get("hipotesisId")) in ids_hip)]
    tiempos: list[Any] = [inv.get("creadaEn")]
    for h in hip:
        tiempos += [h.get("creadaEn"), h.get("ultimaRevisionAutomatica"), h.get("prerregistradaEn"), _dic(h.get("experimento")).get("prerregistradoEn")]
        revs = _lista(h.get("revisiones"))
        if revs and isinstance(revs[-1], dict):
            tiempos.append(revs[-1].get("fecha"))
    for he in hechos:
        tiempos.append(he.get("actualizadoEn"))
    for r in runs:
        tiempos += [r.get("inicio"), r.get("fin")]
    n_af = sum(len(_lista(h.get("afirmaciones"))) for h in hip)
    n_fu = sum(len(_lista(_dic(h.get("procedencia")).get("fuentes"))) for h in hip)
    n_pa = sum(len(_lista(h.get("partidos"))) for h in hip)
    n_ent = sum(len(_lista(h.get("entidades"))) for h in hip) + sum(len(_lista(he.get("entidades"))) for he in hechos)
    huella = _huella(inv, hip, hechos, runs, _lista(e.get("planesAnalisis")), _lista(e.get("iteraciones")))
    return (inv_id, len(hip), len(hechos), len(runs), n_af, n_fu, n_pa, n_ent, _max_tiempo(*tiempos), huella)


def construir_cacheado(e: dict[str, Any], inv: dict[str, Any]) -> dict[str, Any]:
    """`construir` con una caché de 4 entradas por clave (`clave_cache`). El
    grafo devuelto se comparte: no mutarlo (las funciones de vecindad de este
    módulo devuelven copias). La clave incluye una huella de los campos que
    dan forma al grafo, así que editar un registro en sitio también la invalida."""
    clave = clave_cache(e, inv)
    g = _CACHE.get(clave)
    if g is not None:
        _CACHE.move_to_end(clave)
        return g
    g = construir(e, inv)
    _CACHE[clave] = g
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return g


def vaciar_cache() -> None:
    _CACHE.clear()


# ---------------------------------------------------------------------------
# Vecindad
# ---------------------------------------------------------------------------


def vecinos_de(g: dict[str, Any], id_: str, tipos: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Los nodos vecinos de `id_` (no dirigido), en orden de creación, opcionalmente
    filtrados por tipo de nodo. Devuelve copias: mutarlas no toca el grafo
    (que puede ser el cacheado). Lista vacía si el id no existe."""
    permitidos = set(tipos) if tipos is not None else None
    ids = g["vecinos"].get(_clave(id_) or "", set())
    if not ids:
        return []
    return [_copia(n) for n in g["nodos"] if n["id"] in ids and (permitidos is None or n["tipo"] in permitidos)]


def _relaciones_de(g: dict[str, Any], id_: str, tipo: str | None = None) -> dict[str, dict[str, Any]]:
    """Las aristas que tocan a `id_`, por id del otro extremo (la primera de
    cada par gana), en una sola pasada por los enlaces."""
    salida: dict[str, dict[str, Any]] = {}
    for en in g["enlaces"]:
        if tipo is not None and en["tipo"] != tipo:
            continue
        if en["de"] == id_:
            salida.setdefault(en["a"], en)
        elif en["a"] == id_:
            salida.setdefault(en["de"], en)
    return salida


def vecinos_de_hipotesis(e: dict[str, Any], inv: dict[str, Any], h: dict[str, Any]) -> dict[str, Any]:
    """Lo que rodea a una hipótesis en el grafo, para el Killer: hechos que la
    respaldan, cuántas fuentes cita (y cuántas leídas), rivales con el
    resultado del partido desde su punto de vista, ejecuciones, entidades y
    su profundidad hasta el dato y hasta la literatura. Con una hipótesis que
    no está en el grafo devuelve todo vacío y None."""
    g = construir_cacheado(e, inv)
    id_ = _clave(h.get("id")) if isinstance(h, dict) else None
    nodo = g["porId"].get(id_) if id_ else None
    if not nodo or not id_:
        return {"hechos": [], "fuentes": 0, "fuentesLeidas": 0, "rivales": [], "ejecuciones": [], "entidades": [], "profundidadDato": None, "profundidadLiteratura": None}
    partidos = _relaciones_de(g, id_, "rival")
    rivales = []
    for r in vecinos_de(g, id_, ("hipotesis",)):
        en = partidos.get(r["id"])
        if not en:
            continue
        resultado = en.get("etiqueta")
        if en["de"] != id_:
            resultado = _INVERSO_RESULTADO.get(resultado, resultado)
        rivales.append({**r, "resultado": resultado})
    fuentes = vecinos_de(g, id_, ("fuente",))
    return {
        "hechos": vecinos_de(g, id_, ("hecho", "pregunta")),
        "fuentes": len(fuentes),
        "fuentesLeidas": sum(1 for f in fuentes if f.get("leida")),
        "rivales": rivales,
        "ejecuciones": vecinos_de(g, id_, ("ejecucion",)),
        "entidades": vecinos_de(g, id_, ("entidad",)),
        "profundidadDato": nodo.get("profundidadDato"),
        "profundidadLiteratura": nodo.get("profundidadLiteratura"),
    }


def vecinos_de_hecho(e: dict[str, Any], inv: dict[str, Any], hecho: dict[str, Any]) -> dict[str, Any]:
    """Lo que rodea a un hecho o pregunta del modelo de mundo: las hipótesis
    que respalda, las fuentes que lo sostienen y las entidades que nombra.
    Vacío y None si el hecho no está en el grafo."""
    g = construir_cacheado(e, inv)
    id_ = f"he-{_clave(hecho.get('id')) if isinstance(hecho, dict) else None}"
    if id_ not in g["porId"]:
        return {"hipotesis": [], "fuentes": [], "entidades": [], "profundidadDato": None, "profundidadLiteratura": None}
    nodo = g["porId"][id_]
    return {
        "hipotesis": vecinos_de(g, id_, ("hipotesis",)),
        "fuentes": vecinos_de(g, id_, ("fuente",)),
        "entidades": vecinos_de(g, id_, ("entidad",)),
        "profundidadDato": nodo.get("profundidadDato"),
        "profundidadLiteratura": nodo.get("profundidadLiteratura"),
    }


def _linea(texto: Any, largo: int = 120) -> str:
    """Una etiqueta en una sola línea, sin saltos ni delimitadores del bloque."""
    return _recortar(str(texto or "").replace("<<<", "").replace(">>>", ""), largo)


def _profundidad_txt(p: Any) -> str:
    return "sin camino" if p is None else f"{int(p)} {'salto' if int(p) == 1 else 'saltos'}"


def texto_vecinos(e: dict[str, Any], inv: dict[str, Any], id_: str, maximo: int = 8) -> str:
    """Los vecinos de un nodo en castellano, una línea por vecino con la
    relación, el tipo y la etiqueta, para meterlo en un prompt. Va delimitado
    (<<< vecinos ... >>>) y no lleva fragmentos de fuentes: solo referencia y
    título. Lo medido va primero, luego lo leído. Se muestran como mucho
    `maximo` vecinos (0 o menos: ninguno) y se dice cuántos quedan fuera. Un
    id que no está en el grafo devuelve "no pude comprobar", nunca "no hay"."""
    g = construir_cacheado(e, inv)
    clave = _clave(id_) or ""
    nodo = g["porId"].get(clave)
    if not nodo:
        return f"<<< vecinos del grafo\nEl nodo «{_linea(id_, 60)}» no está en el grafo de la investigación; no pude comprobar sus vecinos.\n>>>"
    try:
        tope = max(0, int(maximo))
    except (TypeError, ValueError):
        tope = 8
    orden = {n["id"]: i for i, n in enumerate(g["nodos"])}
    vecinos = sorted(vecinos_de(g, clave), key=lambda n: (_PRIORIDAD_TIPO.get(n["tipo"], 99), orden.get(n["id"], 0)))
    cabecera = f"<<< vecinos del grafo de {NOMBRE_TIPO.get(nodo['tipo'], nodo['tipo'])} «{_linea(nodo['etiqueta'], 100)}» ({len(vecinos)} en total; profundidad hasta el dato: {_profundidad_txt(nodo.get('profundidadDato'))}; hasta la literatura leída: {_profundidad_txt(nodo.get('profundidadLiteratura'))})"
    if not vecinos:
        return f"{cabecera}\nSin vecinos: nada en el registro lo sostiene ni lo relaciona con otra cosa.\n>>>"
    relaciones = _relaciones_de(g, clave)
    lineas = [cabecera]
    for v in vecinos[:tope]:
        en = relaciones.get(v["id"])
        relacion = NOMBRE_ENLACE.get(en["tipo"], en["tipo"]) if en else "relacionado"
        detalle = f" ({_linea(v['sub'], 80)})" if v.get("sub") else ""
        marca = ""
        if v["tipo"] == "fuente":
            marca = " [leída]" if v.get("leida") else " [solo citada, sin texto]"
        elif v.get("alerta"):
            marca = f" [{_linea(v['alerta'], 60)}]"
        lineas.append(f"- {NOMBRE_TIPO.get(v['tipo'], v['tipo'])}, {relacion}: {_linea(v['etiqueta'])}{detalle}{marca}")
    if len(vecinos) > tope:
        restantes = len(vecinos) - tope
        lineas.append(f"... y {restantes} {'vecino más' if restantes == 1 else 'vecinos más'} no listados")
    lineas.append(">>>")
    return "\n".join(lineas)
