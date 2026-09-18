"""Marcos de argumentación de Dung sobre las hipótesis de una investigación.

Para qué está: hoy dos hipótesis pueden llegar juntas a candidatas al
laboratorio aunque digan lo contrario una de la otra (la misma diana sobre el
mismo efecto, una dice que lo aumenta y la otra que lo disminuye). Ningún
campo del estado lo expresaba. Este módulo lo MARCA; nunca descarta: quien
decide qué pasa con dos hipótesis que se contradicen es una persona.

Qué es un marco de argumentación (Dung, 1995): un grafo dirigido cuyos nodos
son argumentos (aquí, hipótesis vivas) y cuyas aristas son ataques ("A ataca
a B"). No dice quién tiene razón; dice qué conjuntos de argumentos pueden
sostenerse a la vez:

- Un conjunto es *libre de conflicto* si ningún miembro ataca a otro miembro.
- La *función característica* F(S) devuelve los argumentos que S defiende:
  aquellos cuyos atacantes están todos atacados por algún miembro de S.
- La *extensión fundamentada* (grounded) es el mínimo punto fijo de F:
  se arranca del vacío y se aplica F hasta que no cambia. Es la lectura más
  cautelosa: un argumento entra solo si nadie lo ataca o si todos sus
  atacantes ya están derrotados. Dos hipótesis que se atacan mutuamente
  quedan las dos fuera, y esa es exactamente la señal que buscamos.
- Las *extensiones preferidas* son los conjuntos admisibles (libres de
  conflicto y que se defienden a sí mismos) máximos por inclusión. En un
  ataque mutuo hay dos: una con cada hipótesis. Son las alternativas entre
  las que una persona tendría que elegir.

De dónde salen los ataques (solo dos fuentes, ninguna por parecido de texto):

1. Declarados: `h["ataca"] = [{"hipotesisId", "motivo", "detalle"}]`, que
   escribe el juez (el Killer o el torneo). "No pueden ser ciertas a la vez"
   es una relación simétrica, así que el ataque se cuenta en las dos
   direcciones aunque el registro lo lleve solo una de las dos hipótesis: si
   fuera direccional, la que se juzgó primero quedaría en pie y la otra caería
   por el orden en que se juzgaron, no por su mérito.
2. Deterministas: dos relaciones del modelo de mundo (`e["relaciones"]`)
   con el mismo mecanismo (mismo `de` y mismo `a`, sin distinguir mayúsculas
   ni espacios), de hipótesis distintas y con signos opuestos. El signo sale
   de `r["signo"]` si existe y, si no, de la hipótesis (`tarjeta.direccion`
   o las palabras del enunciado). Si a alguna le falta el signo, o una misma
   hipótesis lleva los dos signos sobre el mismo mecanismo, no hay ataque: no
   se inventa. Estos ataques también son simétricos.

Con solo fuentes simétricas, la extensión fundamentada coincide con las
hipótesis sin conflicto; la maquinaria de Dung completa (fundamentada,
preferidas) está para cuando entren ataques con dirección (por ejemplo, una
afirmación que socava el método de otra).

El módulo funciona con y sin los campos nuevos (`ataca`, `signo`): un
registro antiguo sin esas claves se trata como si el campo estuviera vacío.
"""

from __future__ import annotations

from typing import Any, Iterable

# Hasta este tamaño las extensiones preferidas se calculan por fuerza bruta
# (2^12 = 4096 subconjuntos); por encima se devuelve solo la fundamentada.
MAX_ARGUMENTOS_FUERZA_BRUTA = 12

MOTIVO_DECLARADO = "contradiccion_declarada"
MOTIVO_MECANISMO = "mismo_mecanismo_direccion_opuesta"
MOTIVOS = (MOTIVO_DECLARADO, MOTIVO_MECANISMO)

Ataque = tuple[str, str]


# ---------------------------------------------------------------------------
# Núcleo puro: conjuntos de identificadores y pares (atacante, atacado)
# ---------------------------------------------------------------------------


def _normalizar(args: Iterable[str], ataques: Iterable[Ataque]) -> tuple[set[str], set[Ataque]]:
    """Conjunto de argumentos y relación de ataque restringida a ellos. Los
    ataques que nombran algo fuera del conjunto se ignoran; los repetidos se
    funden."""
    conjunto = set(args)
    relacion = {(x, y) for x, y in ataques if x in conjunto and y in conjunto}
    return conjunto, relacion


def _atacantes_de(conjunto: set[str], relacion: set[Ataque]) -> dict[str, set[str]]:
    atacantes: dict[str, set[str]] = {a: set() for a in conjunto}
    for x, y in relacion:
        atacantes[y].add(x)
    return atacantes


def _caracteristica(conjunto: set[str], atacantes: dict[str, set[str]], relacion: set[Ataque], s: set[str]) -> set[str]:
    """F(S): los argumentos cuyos atacantes están todos atacados por S."""
    atacados_por_s = {y for x, y in relacion if x in s}
    return {a for a in conjunto if atacantes[a] <= atacados_por_s}


def libre_de_conflicto(args: set[str], ataques: list[Ataque]) -> bool:
    """Cierto si ningún miembro de `args` ataca a otro miembro (ni a sí mismo)."""
    conjunto = set(args)
    return not any(x in conjunto and y in conjunto for x, y in ataques)


def extension_fundamentada(args: set[str], ataques: list[Ataque]) -> set[str]:
    """Extensión fundamentada (grounded): mínimo punto fijo de F, iterando
    desde el vacío. Como F es monótona, converge en como mucho |args| + 1
    pasos. Un argumento sin atacantes entra en el primer paso; el que está
    en un ataque mutuo o en un ciclo sin nadie que lo rompa no entra nunca."""
    conjunto, relacion = _normalizar(args, ataques)
    atacantes = _atacantes_de(conjunto, relacion)
    s: set[str] = set()
    while True:
        siguiente = _caracteristica(conjunto, atacantes, relacion, s)
        if siguiente == s:
            return s
        s = siguiente


def es_admisible(s: set[str], args: set[str], ataques: list[Ataque]) -> bool:
    """Admisible: libre de conflicto y contenido en F(S), es decir, se
    defiende a sí mismo de todos sus atacantes. Lo que `s` nombre fuera de
    `args` no cuenta."""
    conjunto, relacion = _normalizar(args, ataques)
    s = set(s) & conjunto
    if not libre_de_conflicto(s, list(relacion)):
        return False
    atacantes = _atacantes_de(conjunto, relacion)
    return s <= _caracteristica(conjunto, atacantes, relacion, s)


def extensiones_preferidas(args: set[str], ataques: list[Ataque]) -> list[set[str]]:
    """Extensiones preferidas: conjuntos admisibles máximos por inclusión,
    ordenados de forma determinista (tamaño y luego ids). Por fuerza bruta si
    hay como mucho MAX_ARGUMENTOS_FUERZA_BRUTA argumentos; por encima devuelve
    solo la fundamentada (que está contenida en toda preferida, así que es una
    aproximación por defecto, nunca una invención). Con el ciclo impar
    a -> b -> c -> a la única preferida es el conjunto vacío.

    Los subconjuntos se recorren de mayor a menor tamaño: un admisible que no
    está contenido en ninguna preferida ya encontrada es máximo, porque todo
    superconjunto suyo admisible habría salido antes. Así la comparación es
    contra las preferidas (pocas) y no contra todos los admisibles (con pocos
    ataques son casi los 4096 subconjuntos, y compararlos entre sí costaba
    décimas de segundo)."""
    conjunto, relacion = _normalizar(args, ataques)
    if len(conjunto) > MAX_ARGUMENTOS_FUERZA_BRUTA:
        return [extension_fundamentada(conjunto, list(relacion))]
    orden = sorted(conjunto)
    n = len(orden)
    atacantes = _atacantes_de(conjunto, relacion)
    lista_relacion = list(relacion)
    preferidas: list[frozenset[str]] = []
    for mascara in sorted(range(1 << n), key=lambda m: -bin(m).count("1")):
        s = {orden[i] for i in range(n) if mascara >> i & 1}
        if any(s <= p for p in preferidas):
            continue
        if libre_de_conflicto(s, lista_relacion) and s <= _caracteristica(conjunto, atacantes, relacion, s):
            preferidas.append(frozenset(s))
    return [set(s) for s in sorted(preferidas, key=lambda s: (len(s), sorted(s)))]


def conflictos_entre(ids: list[str], ataques: list[Ataque]) -> dict[str, list[str]]:
    """Por cada id de la lista, con quién de la misma lista se ataca en
    cualquier dirección (ordenado, sin repetidos, sin él mismo). Todo id de
    la lista aparece como clave, aunque su lista quede vacía."""
    conjunto = set(ids)
    salida: dict[str, set[str]] = {i: set() for i in ids}
    for x, y in ataques:
        if x in conjunto and y in conjunto and x != y:
            salida[x].add(y)
            salida[y].add(x)
    return {i: sorted(v) for i, v in salida.items()}


# ---------------------------------------------------------------------------
# Sobre el estado de ROSA2018
# ---------------------------------------------------------------------------


def signo_de_hipotesis(h: dict[str, Any]) -> str | None:
    """'+' si la hipótesis dice que su diana aumenta el efecto, '-' si dice
    que lo disminuye, None si no se sabe. Primero la tarjeta
    (`tarjeta.direccion`: 'aumenta' o 'disminuye', sin distinguir mayúsculas
    ni espacios); si la tarjeta no lo fija ('modula', 'sin_intervencion' o
    sin tarjeta), las palabras del enunciado con la heurística del Killer
    ('sube' o 'baja'; '' si hay las dos o ninguna). Sirve para castellano e
    inglés porque la heurística cubre ambos. Con algo que no sea un
    diccionario devuelve None."""
    from rosa.killer import direccion_de  # solo para esta función

    if not isinstance(h, dict):
        return None
    tarjeta = h.get("tarjeta") or {}
    direccion = str(tarjeta.get("direccion") or "").strip().lower() if isinstance(tarjeta, dict) else ""
    if direccion == "aumenta":
        return "+"
    if direccion == "disminuye":
        return "-"
    palabras = direccion_de(str(h.get("enunciado") or ""))
    return {"sube": "+", "baja": "-"}.get(palabras)


def _hipotesis(e: Any) -> list[Any]:
    """La lista de hipótesis del estado, o vacía si el estado no es un
    diccionario o no la tiene."""
    if not isinstance(e, dict):
        return []
    return list(e.get("hipotesis") or [])


def _vivas(e: Any, investigacion_id: str) -> list[dict[str, Any]]:
    """Las hipótesis de la investigación que participan del marco: con id, no
    descartadas. Lo que no sea un diccionario o no tenga id se ignora; sin
    investigación no hay marco."""
    if not investigacion_id:
        return []
    return [h for h in _hipotesis(e) if isinstance(h, dict) and h.get("investigacionId") == investigacion_id and h.get("estado") != "descartada" and isinstance(h.get("id"), str) and h.get("id")]


def _nombre(h: dict[str, Any] | None, id_: str) -> str:
    """El título en una sola línea si lo hay; si no, el id. Para los textos
    que lee una persona."""
    if not h:
        return id_
    return " ".join(str(h.get("titulo") or "").split()) or id_


def _nombres(por_id: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Un nombre por hipótesis para el texto. Si dos hipótesis vivas llevan el
    mismo título, cada una lleva su id detrás para que la frase se entienda."""
    crudos = {i: _nombre(h, i) for i, h in por_id.items()}
    repetidos = {n for n in crudos.values() if sum(1 for v in crudos.values() if v == n) > 1}
    return {i: (f"{n} ({i})" if n in repetidos and n != i else n) for i, n in crudos.items()}


def _clave_mecanismo(r: dict[str, Any]) -> tuple[str, str] | None:
    de = str(r.get("de") or "").lower().strip()
    a = str(r.get("a") or "").lower().strip()
    if not de or not a:
        return None
    return de, a


def _signo_de_relacion(r: dict[str, Any], h: dict[str, Any]) -> str | None:
    signo = r.get("signo")
    if signo in ("+", "-"):
        return signo
    return signo_de_hipotesis(h)


def ataques_de(e: dict[str, Any], investigacion_id: str) -> list[dict[str, Any]]:
    """Los ataques entre hipótesis vivas (estado distinto de 'descartada') de
    la investigación, cada uno con su motivo y su detalle en castellano:

    - `contradiccion_declarada`: lo que el juez escribió en `h["ataca"]`.
      Como "no pueden ser ciertas a la vez" es simétrico, se emite en las dos
      direcciones aunque solo una hipótesis lleve el registro (el Killer
      escribe en una; el torneo, en las dos: da igual). Se ignoran los que
      apuntan a la propia hipótesis, a una descartada, a otra investigación
      o a un id que no es una cadena. Si el registro trae un `motivo`
      conocido se respeta; si no, es `contradiccion_declarada`.
    - `mismo_mecanismo_direccion_opuesta`: dos relaciones del modelo de
      mundo con el mismo (de, a) de hipótesis distintas y signos opuestos.
      Simétrico. Si falta el signo de alguna, o una hipótesis lleva los dos
      signos sobre el mismo mecanismo, no hay ataque.

    Sin repetidos: como mucho una entrada por (de, a, motivo). Los
    deterministas llevan además `mecanismo` = {"de", "a", "aumenta",
    "disminuye"} (el mecanismo compartido y qué hipótesis va en cada
    dirección), que es lo que permite explicar el ataque sin releer nada.
    El coste es lineal en las relaciones más el número de ataques emitidos."""
    vivas = _vivas(e, investigacion_id)
    por_id = {h["id"]: h for h in vivas}
    salida: list[dict[str, Any]] = []
    vistos: dict[tuple[str, str, str], dict[str, Any]] = {}

    def anadir(de: str, a: str, motivo: str, detalle: str, mecanismo: dict[str, str] | None = None) -> None:
        # Una entrada por (de, a, motivo). Si el mismo par llega con otro detalle
        # (el Killer juzgó a las dos en momentos distintos, o comparten dos
        # mecanismos), el detalle nuevo se suma al que había en vez de perderse.
        clave = (de, a, motivo)
        if de == a:
            return
        existente = vistos.get(clave)
        if existente is not None:
            if detalle and detalle not in existente["detalle"]:
                existente["detalle"] = f"{existente['detalle']}; {detalle}" if existente["detalle"] else detalle
            return
        ataque: dict[str, Any] = {"de": de, "a": a, "motivo": motivo, "detalle": detalle}
        if mecanismo:
            ataque["mecanismo"] = dict(mecanismo)
        vistos[clave] = ataque
        salida.append(ataque)

    # 1. Declarados por el juez, en las dos direcciones.
    for h in vivas:
        declarados = h.get("ataca")
        for declarado in (declarados if isinstance(declarados, list) else []):
            if not isinstance(declarado, dict):
                continue
            objetivo = declarado.get("hipotesisId")
            if not isinstance(objetivo, str) or objetivo not in por_id:
                continue
            motivo = declarado.get("motivo") if declarado.get("motivo") in MOTIVOS else MOTIVO_DECLARADO
            detalle = str(declarado.get("detalle") or "").strip() or f"El juez declaró que '{_nombre(h, h['id'])}' y '{_nombre(por_id[objetivo], objetivo)}' no pueden ser ciertas a la vez"
            anadir(h["id"], objetivo, motivo, detalle)
            anadir(objetivo, h["id"], motivo, detalle)

    # 2. Deterministas: mismo mecanismo, signos opuestos. Primero un signo por
    # (mecanismo, hipótesis); una hipótesis con los dos signos queda en None.
    relaciones = (e.get("relaciones") or []) if isinstance(e, dict) else []
    por_mecanismo: dict[tuple[str, str], dict[str, Any]] = {}
    for r in relaciones:
        if not isinstance(r, dict) or not isinstance(r.get("hipotesisId"), str) or r["hipotesisId"] not in por_id:
            continue
        clave = _clave_mecanismo(r)
        if clave is None:
            continue
        hid = r["hipotesisId"]
        grupo = por_mecanismo.setdefault(clave, {"de": str(r.get("de")).strip(), "a": str(r.get("a")).strip(), "signos": {}})
        signo = _signo_de_relacion(r, por_id[hid])
        signos: dict[str, str | None] = grupo["signos"]
        if hid not in signos:
            signos[hid] = signo
        elif signos[hid] != signo:
            signos[hid] = None
    for grupo in por_mecanismo.values():
        aumentan = [i for i, s in grupo["signos"].items() if s == "+"]
        disminuyen = [i for i, s in grupo["signos"].items() if s == "-"]
        for mas_id in aumentan:
            for menos_id in disminuyen:
                mas, menos = por_id[mas_id], por_id[menos_id]
                mecanismo = {"de": grupo["de"], "a": grupo["a"], "aumenta": mas_id, "disminuye": menos_id}
                detalle = f"Mismo mecanismo ({mecanismo['de']} sobre {mecanismo['a']}) con direcciones opuestas: '{_nombre(mas, mas_id)}' dice que lo aumenta y '{_nombre(menos, menos_id)}' que lo disminuye"
                anadir(mas_id, menos_id, MOTIVO_MECANISMO, detalle, mecanismo)
                anadir(menos_id, mas_id, MOTIVO_MECANISMO, detalle, mecanismo)
    return salida


def _pares(ataques: list[dict[str, Any]]) -> list[Ataque]:
    return [(a["de"], a["a"]) for a in ataques]


def marcar_conflictos(e: dict[str, Any], investigacion_id: str) -> dict[str, Any]:
    """Escribe en cada hipótesis viva de la investigación dos campos:
    `conflictoCon` (ids ordenados con quien se ataca en cualquier dirección;
    lista vacía si nadie) y `enExtensionFundamentada` (si queda en pie en la
    lectura más cautelosa del marco). No descarta nada, no toca `candidata`
    ni `bloqueos`. Es idempotente: correrla dos veces deja el estado igual.
    Cada hipótesis recibe su propia lista, nunca una compartida.

    Las descartadas de la misma investigación quedan con `conflictoCon = []`
    y `enExtensionFundamentada = False`: no participan del marco, y así los
    dos campos están siempre presentes y al día en toda la investigación
    (la plantilla ya trae `conflictoCon` vacío al nacer). Las hipótesis de
    otras investigaciones no se tocan. Con un estado que no es un diccionario
    no escribe nada.

    Devuelve {"ataques": entradas de ataques_de, "conflictos": pares de
    hipótesis en conflicto, "fundamentada": ids en la extensión
    fundamentada, ordenados}."""
    vivas = _vivas(e, investigacion_id)
    ataques = ataques_de(e, investigacion_id)
    pares = _pares(ataques)
    ids = [h["id"] for h in vivas]
    fundamentada = extension_fundamentada(set(ids), pares)
    conflictos = conflictos_entre(ids, pares)
    for h in vivas:
        h["conflictoCon"] = list(conflictos.get(h["id"], []))
        h["enExtensionFundamentada"] = h["id"] in fundamentada
    if investigacion_id:
        for h in _hipotesis(e):
            if isinstance(h, dict) and h.get("investigacionId") == investigacion_id and h.get("estado") == "descartada":
                h["conflictoCon"] = []
                h["enExtensionFundamentada"] = False
    n_pares = len({frozenset((x, y)) for x, y in pares if x != y})
    return {"ataques": len(ataques), "conflictos": n_pares, "fundamentada": sorted(fundamentada)}


def texto_conflictos(e: dict[str, Any], investigacion_id: str, ids: list[str] | None = None) -> str:
    """Los conflictos en castellano y en llano, una línea por par, para la
    persona y para los prompts. Si se pasa `ids`, solo los pares en los que
    participa al menos una de esas hipótesis (útil para las candidatas al
    laboratorio: también avisa si una candidata contradice a una viva que no
    lo es). Cadena vacía si no hay conflictos.

    El orden es determinista (por nombre y, a igual nombre, por id), los
    títulos van en una sola línea y, si dos hipótesis se llaman igual, cada
    una lleva su id detrás. Una razón declarada por el juez sale una vez por
    par aunque el registro la lleve en las dos hipótesis."""
    vivas = _vivas(e, investigacion_id)
    por_id = {h["id"]: h for h in vivas}
    nombres = _nombres(por_id)

    def nombre(i: str) -> str:
        return nombres.get(i, i)

    ataques = ataques_de(e, investigacion_id)
    filtro = set(ids) if ids is not None else None
    por_par: dict[frozenset[str], list[dict[str, Any]]] = {}
    for a in ataques:
        if a["de"] == a["a"]:
            continue
        if filtro is not None and a["de"] not in filtro and a["a"] not in filtro:
            continue
        por_par.setdefault(frozenset((a["de"], a["a"])), []).append(a)
    lineas: list[str] = []
    for par in sorted(por_par, key=lambda p: (sorted(nombre(i) for i in p), sorted(p))):
        x, y = sorted(par, key=lambda i: (nombre(i), i))
        motivos = por_par[par]
        razones: list[str] = []
        determinista = next((m for m in motivos if m["motivo"] == MOTIVO_MECANISMO), None)
        if determinista is not None:
            mec = determinista.get("mecanismo") or {}
            if mec:
                razones.append(f"mismo mecanismo, direcciones opuestas: {mec['de']} sobre {mec['a']}; '{nombre(mec['aumenta'])}' dice que lo aumenta y '{nombre(mec['disminuye'])}' que lo disminuye")
            else:
                razones.append("mismo mecanismo, direcciones opuestas: " + determinista["detalle"])
        detalles_vistos: set[str] = set()
        for m in motivos:
            if m["motivo"] == MOTIVO_DECLARADO and m["detalle"] not in detalles_vistos:
                detalles_vistos.add(m["detalle"])
                razones.append(f"contradicción declarada por el juez: {m['detalle']}")
        lineas.append(f"'{nombre(x)}' y '{nombre(y)}' se contradicen ({'; '.join(razones)}); no pueden ser ciertas a la vez, así que si las dos van al laboratorio una de las dos sobra o hay que diseñar el experimento que las separe.")
    return "\n".join(lineas)
