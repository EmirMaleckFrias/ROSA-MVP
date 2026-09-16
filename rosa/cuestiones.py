"""Cuestiones persistentes por investigación (lo que rekursiv.ai llama Issues).

Hasta ahora una "pregunta abierta" era un hecho del modelo de mundo con tipo
'pregunta' y estado 'abierto': sin origen, sin "qué la resolvería", sin enlace
a hipótesis y sin cierre nunca. Además había otras dos listas de pendientes
separadas (los hallazgos del revisor de registro y las incidencias). Una
cuestión reúne todo eso en un solo objeto con vida propia:

- de dónde salió (`origen`: pregunta del modelo de mundo, Killer, revisor,
  paso fallido, persona, análisis, laboratorio o escalera de certeza), con el
  id del objeto que la provocó;
- qué la resolvería (`queLaResolveria`), para que el modelo pueda señalar
  cuándo un hecho nuevo la responde;
- a qué hipótesis y hechos está enganchada (`hipotesisIds`, `hechoIds`);
- tres estados con historial: 'abierta', 'resuelta' (con `resolucion`: por
  qué hecho o persona y por qué) y 'descartada' (con motivo obligatorio).

Deduplicación por regla, dentro de la investigación: dos textos son la misma
cuestión si coinciden normalizados (minúsculas, sin tildes ni signos, letras
griegas por su nombre, espacios colapsados) o si el solape de Jaccard entre
sus tokens de más de tres letras es >= UMBRAL_JACCARD y además coinciden sus
marcas cortas: los tokens de hasta tres caracteres que no son palabras vacías
(siglas como NfL o LCR, cifras como 40 o p53, negaciones como "no" o "sin"),
que el solape de tokens largos no ve y que cambian el sentido de la pregunta.
Tercera guarda: si los dos textos comparten una palabra de orden o dirección
(antes, después, causa, predice, before, after...), los tokens compartidos
tienen que ir en el mismo orden; "¿Sube GFAP antes que NfL?" y "¿Sube NfL antes
que GFAP?" son la misma bolsa de palabras y preguntan lo contrario.
Al fundir, se unen los ids, sube `veces` y la prioridad baja al mínimo de las
dos; si quien vuelve a preguntar es una persona, queda un movimiento en el
historial (protege la cuestión de la poda). Si la equivalente ya está resuelta
o descartada, se devuelve tal cual, sin reabrir: quien pregunte otra vez ve
que ya se cerró. Tope de MAX_CUESTIONES_ABIERTAS abiertas por investigación
para las que abre Rosa; las que abre una persona entran siempre.

Todo lo que aquí decide algo es determinista y devuelve su motivo:
`registrar_con_motivo` dice si la cuestión entró, con quién se fundió y por
qué regla, o por qué no entró. El estado guarda la lista en `e["cuestiones"]`
(este módulo usa siempre `setdefault`, así que un estado antiguo sin la clave
no rompe). Los registros antiguos sin alguna clave, o con una clave guardada
con otro tipo (origen como cadena, ids como cadena, una entrada que no es un
diccionario), se leen con el valor por defecto de hoy y nunca rompen. Al
bifurcar una investigación, `copiar_a_investigacion` lleva las cuestiones con
los hechos copiados (misma regla de id que `acciones.copiar_hechos`). 16 de
septiembre de 2026.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any

from rosa import config
from rosa.estado import plantilla as P

ORIGENES = ("pregunta_modelo", "killer", "revisor", "paso_fallido", "persona", "analisis", "laboratorio", "escalera")
ESTADOS = ("abierta", "resuelta", "descartada")
MAX_CUESTIONES_ABIERTAS = 60
UMBRAL_JACCARD = 0.8
LARGO_TEXTO = 300
PRIORIDAD_MINIMA, PRIORIDAD_MAXIMA, PRIORIDAD_POR_DEFECTO = 1, 9, 5
_ORIGEN_POR_DEFECTO = "analisis"

# Letras griegas frecuentes en el texto biomédico, por su nombre: "Aβ42" y
# "Abeta42" son la misma cosa, y sin esto la β desaparecía y "Aβ" quedaba en "a".
_GRIEGAS = {"α": "alfa", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "κ": "kappa", "λ": "lambda", "μ": "mu", "σ": "sigma", "τ": "tau", "ω": "omega"}

def _sin_tildes(texto: str) -> str:
    """Minúsculas y sin marcas diacríticas (NFKD): la tilde de 'así' y la
    virgulilla de 'año' desaparecen y quedan las letras base, sin marca."""
    return "".join(c for c in unicodedata.normalize("NFKD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")


# Palabras vacías de hasta tres caracteres, en castellano e inglés: no cuentan
# como marca corta. Se comparan con texto ya normalizado, así que la lista pasa
# por la misma normalización al cargar el módulo (escribirlas con o sin tilde da
# igual; una pasada de tildes sobre este fichero no la rompe). La negación
# ("no", "not", "ni", "sin") queda fuera a propósito: cambia el sentido y por
# tanto distingue.
_VACIAS_CORTAS = frozenset(
    _sin_tildes(p)
    for p in (
        "a al así aún con de del e el en era es esa ese eso fue ha han hay he la las le les lo los más me mi mis muy nos o os por que se ser si son su sus tan te tu tus u un una uno y ya vs etc "
        "an and are as at be but by can did do for had has her his how if in is it its may of on or our out she so the to up was we who why you all any yet"
    ).split()
)

# Palabras de orden o de dirección, en castellano e inglés (ya normalizadas).
# Cuando dos textos comparten una de estas, el solape de tokens no basta: "¿Sube
# GFAP antes que NfL?" y "¿Sube NfL antes que GFAP?" comparten todos los tokens y
# preguntan lo contrario. Con una de estas palabras en común, los tokens
# compartidos (cortos incluidos) tienen que aparecer en el mismo orden en los
# dos textos. Sin ninguna (una carencia del Killer reordenada), el orden no
# importa y la fusión sigue funcionando por bolsa de palabras. Solo entran las
# de orden temporal, las causales o predictivas y las comparativas: las
# preposiciones flojas (desde, hacia, hasta, from, until) y los verbos genéricos
# (explica, genera, produce) casi nunca se invierten y, en la lista, hacían que
# una misma pregunta reordenada dejara de fundirse.
_DIRECCION = frozenset(
    _sin_tildes(p)
    for p in (
        "antes después previo previa previos previas posterior posteriores anterior anteriores precede preceden precedido precedida "
        "primero primera luego tras sigue siguen seguido seguida causa causan causado causada provoca provocan predice predicen "
        "predictor predictora mayor mayores menor menores superior inferior aumenta aumentan reduce reducen induce inducen depende dependen "
        "before after prior precedes preceded earlier later first then follows followed following cause causes caused predict "
        "predicts predicted predictor higher lower greater larger smaller than increase increases decrease decreases induce induces "
        "mediate mediates depend depends upstream downstream"
    ).split()
)

_ETIQUETAS_ORIGEN = {
    "pregunta_modelo": "pregunta del modelo de mundo",
    "killer": "Killer",
    "revisor": "revisor de registro",
    "paso_fallido": "paso fallido",
    "persona": "persona",
    "analisis": "análisis",
    "laboratorio": "laboratorio",
    "escalera": "escalera de certeza",
}


# ---------------------------------------------------------------------------
# Normalización y equivalencia
# ---------------------------------------------------------------------------


@lru_cache(maxsize=16384)
def _perfil(texto: str) -> tuple[str, frozenset[str], frozenset[str], tuple[str, ...]]:
    """(texto normalizado, tokens largos, marcas cortas, tokens con contenido en
    el orden en que aparecen) de un texto, calculado una sola vez por cadena:
    registrar compara la cuestión nueva con todas las de la investigación, y
    sin caché eso volvía a normalizar miles de textos en cada alta (cuadrático:
    con tres mil cerradas, cada alta costaba 110 ms). El cuarto elemento son
    los tokens largos y las marcas cortas por orden de primera aparición, sin
    repetir: sirve para la guarda de dirección de `equivalencia`."""
    s = unicodedata.normalize("NFKD", str(texto or "").lower())  # NFKD primero: el signo micro pasa a mu griega
    s = "".join(_GRIEGAS.get(c, c) for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^0-9a-z\s]+", " ", s.lower())
    normalizado = re.sub(r"\s+", " ", s).strip()
    partes = normalizado.split()
    largos = frozenset(t for t in partes if len(t) > 3)
    marcas = frozenset(t for t in partes if len(t) <= 3 and t not in _VACIAS_CORTAS)
    orden = tuple(dict.fromkeys(t for t in partes if t in largos or t in marcas))
    return normalizado, largos, marcas, orden


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni signos, letras griegas por su nombre (Aβ42 y
    Abeta42 coinciden), espacios colapsados. Sirve para comparar dos textos que
    dicen lo mismo con distinta ortografía."""
    return _perfil(str(texto or ""))[0]


def tokens(texto: str) -> set[str]:
    """Tokens de más de tres letras del texto normalizado. 'GFAP' cuenta,
    'NfL' y 'tau' no: los cortos van aparte, en `marcas_cortas`."""
    return set(_perfil(str(texto or ""))[1])


def jaccard(a: str, b: str) -> float:
    ta, tb = _perfil(str(a or ""))[1], _perfil(str(b or ""))[1]
    union = ta | tb
    if not union:
        return 0.0
    return len(ta & tb) / len(union)


def marcas_cortas(texto: str) -> set[str]:
    """Tokens de hasta tres caracteres del texto normalizado que no son
    palabras vacías: siglas (nfl, app, lcr), cifras (40, p53), negaciones (no,
    sin) y otras palabras cortas con contenido. Son lo que el solape de tokens
    largos no ve y lo que distingue "¿sube NfL?" de "¿sube tau?" o "amiloide
    positivos" de "no amiloide positivos". Se miden sobre el texto normalizado,
    así que valen igual escritas en mayúscula o en minúscula."""
    return set(_perfil(str(texto or ""))[2])


siglas_cortas = marcas_cortas  # nombre anterior, conservado para quien ya lo use


def mismo_orden(a: str, b: str) -> bool:
    """True si los tokens con contenido que comparten los dos textos (largos y
    marcas cortas) aparecen en el mismo orden en ambos. 'sube gfap antes que
    nfl' y 'sube nfl antes que gfap' comparten todo y lo dicen al revés."""
    oa, ob = _perfil(str(a or ""))[3], _perfil(str(b or ""))[3]
    comunes = set(oa) & set(ob)
    return [t for t in oa if t in comunes] == [t for t in ob if t in comunes]


def equivalencia(a: str, b: str) -> str | None:
    """Motivo por el que dos textos son la misma cuestión, o None si no lo
    son. Primero la coincidencia exacta normalizada; después el solape de
    tokens largos, que solo vale si las marcas cortas coinciden en los dos
    textos (si no, son preguntas distintas aunque el resto sea igual) y, cuando
    comparten una palabra de orden o dirección (antes, después, causa, predice,
    before, after...), si los tokens compartidos van en el mismo orden (si no,
    una pregunta es la inversa de la otra). La regla prefiere dejar dos
    cuestiones parecidas a perder una en silencio."""
    na, ta, ma, oa = _perfil(str(a or ""))
    nb, tb, mb, ob = _perfil(str(b or ""))
    if not na or not nb:
        return None
    if na == nb:
        return "texto normalizado idéntico"
    if ma != mb:
        return None
    union = ta | tb
    j = len(ta & tb) / len(union) if union else 0.0
    if j < UMBRAL_JACCARD:
        return None
    if (set(oa) & set(ob) & _DIRECCION) and not mismo_orden(a, b):
        return None  # misma bolsa de palabras, pero dicen el orden o la dirección al revés
    return f"solape de tokens {j:.2f} >= {UMBRAL_JACCARD:.1f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def _recortar(texto: Any, largo: int = LARGO_TEXTO) -> str:
    return re.sub(r"\s+", " ", str(texto or "")).strip()[:largo].strip()


def _entero(x: Any, defecto: int = 0) -> int:
    """Un entero de un registro guardado; si falta o no es número, el defecto."""
    try:
        return int(x)
    except (TypeError, ValueError):
        return defecto


def _ms(ahora: Any) -> int:
    """Un tiempo en milisegundos; si falta o no es número, el de ahora. Un
    booleano no es un tiempo (int(True) daría el milisegundo 1 de 1970)."""
    if isinstance(ahora, bool):
        return P.ahora_ms()
    try:
        return int(ahora)
    except (TypeError, ValueError):
        return P.ahora_ms()


def _acotar_prioridad(prioridad: Any) -> int:
    try:
        p = int(prioridad)
    except (TypeError, ValueError):
        p = PRIORIDAD_POR_DEFECTO
    return max(PRIORIDAD_MINIMA, min(PRIORIDAD_MAXIMA, p))


def _ids_limpios(ids: Any) -> list[str]:
    """Lista de ids sin vacíos ni repetidos, en orden. Una cadena suelta es un
    solo id (un registro antiguo con hipotesisIds "hip-1" no se parte en letras)."""
    if isinstance(ids, str):
        ids = [ids]
    elif isinstance(ids, (set, frozenset)):
        ids = sorted(str(x or "") for x in ids)  # el orden de un set cambia con la semilla de hash: se fija
    if not isinstance(ids, (list, tuple)):
        ids = []
    salida: list[str] = []
    for x in ids:
        s = str(x or "").strip()
        if s and s not in salida:
            salida.append(s)
    return salida


def _origen_limpio(origen: Any) -> dict[str, Any]:
    """Un origen siempre es {"tipo": uno de ORIGENES, "id": str | None}. Un
    tipo desconocido cae en 'analisis' (genérico) para que un error del
    integrador no tumbe el bucle; una cadena se toma como tipo."""
    if isinstance(origen, str):
        origen = {"tipo": origen, "id": None}
    if not isinstance(origen, dict):
        origen = {}
    tipo = str(origen.get("tipo") or "").strip()
    id_ = origen.get("id")
    return {"tipo": tipo if tipo in ORIGENES else _ORIGEN_POR_DEFECTO, "id": str(id_) if id_ not in (None, "") else None}


def nueva(investigacion_id: str, texto: str, origen: dict[str, Any], que_la_resolveria: str, ahora: int, prioridad: int = PRIORIDAD_POR_DEFECTO, hipotesis_ids: list[str] | None = None, hecho_ids: list[str] | None = None, quien: str = config.QUIEN_ROSA) -> dict[str, Any]:
    """Una cuestión abierta, todavía fuera del estado (la mete `registrar`)."""
    ahora = _ms(ahora)
    quien = str(quien or config.QUIEN_ROSA).strip() or config.QUIEN_ROSA
    return {
        "id": P.nuevo_id("cu"),
        "investigacionId": investigacion_id,
        "texto": _recortar(texto),
        "estado": "abierta",
        "origen": _origen_limpio(origen),
        "queLaResolveria": _recortar(que_la_resolveria),
        "hipotesisIds": _ids_limpios(hipotesis_ids),
        "hechoIds": _ids_limpios(hecho_ids),
        "prioridad": _acotar_prioridad(prioridad),
        "creadaEn": ahora,
        "actualizadaEn": ahora,
        "resueltaEn": None,
        "resolucion": None,
        "veces": 1,
        "historial": [{"fecha": ahora, "de": None, "a": "abierta", "quien": quien, "motivo": "Abierta"}],
    }


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


def _lista(e: dict[str, Any]) -> list[Any]:
    """La lista viva del estado (la misma cada vez: `registrar` le hace append)."""
    lista = e.setdefault("cuestiones", [])
    if not isinstance(lista, list):
        lista = e["cuestiones"] = []
    return lista


def _registros(e: dict[str, Any]) -> list[dict[str, Any]]:
    """Solo las entradas que son diccionarios: una entrada rota (None, una
    cadena) en un estado antiguo no tumba ninguna lectura."""
    return [c for c in _lista(e) if isinstance(c, dict)]


def _estado_de(c: dict[str, Any]) -> str:
    est = c.get("estado")
    return est if est in ESTADOS else "abierta"


def _origen_de(c: dict[str, Any]) -> dict[str, Any]:
    """El origen de un registro leído, siempre con la forma {"tipo", "id"}."""
    return _origen_limpio(c.get("origen"))


def _propias(e: dict[str, Any], investigacion_id: str) -> list[dict[str, Any]]:
    return [c for c in _registros(e) if c.get("investigacionId") == investigacion_id]


def _creada_en(c: dict[str, Any]) -> int:
    """Cuándo se creó un registro: `creadaEn` si es legible; si falta (registro
    antiguo), la fecha del movimiento de apertura del historial (el que tiene
    `de` None: es el único que dice cuándo nació); si tampoco, 0 (la más antigua
    de todas). Un historial cuyo primer movimiento es una resolución no dice
    nada de la apertura: el registro existía antes y no se le inventa fecha.
    Antes una cuestión sin `creadaEn` pero abierta después del límite se
    salvaba de la poda por contar como 0."""
    if c.get("creadaEn") not in (None, "") and not isinstance(c.get("creadaEn"), bool):
        try:
            return int(c["creadaEn"])
        except (TypeError, ValueError):
            pass
    historial = c.get("historial")
    if isinstance(historial, list):
        for m in historial:
            if isinstance(m, dict) and m.get("de") is None and m.get("fecha") not in (None, ""):
                try:
                    return int(m["fecha"])
                except (TypeError, ValueError):
                    return 0
    return 0


def _clave_orden(c: dict[str, Any]) -> tuple[int, int]:
    return (_acotar_prioridad(c.get("prioridad", PRIORIDAD_POR_DEFECTO)), _creada_en(c))


def _recortar_lista(lista: list[Any], maximo: int | None) -> list[Any]:
    """Los primeros hasta el límite pedido; None o un número negativo es sin
    límite (antes un -1 quitaba la última en silencio)."""
    if maximo is None or _entero(maximo, -1) < 0:
        return lista
    return lista[: _entero(maximo)]


def buscar(e: dict[str, Any], cuestion_id: str) -> dict[str, Any] | None:
    """La cuestión con ese id, o None. Un id vacío no casa con nada (antes
    `buscar(e, None)` devolvía un registro antiguo sin id y `resolver` lo cerraba)."""
    if not cuestion_id:
        return None
    for c in _registros(e):
        if c.get("id") == cuestion_id:
            return c
    return None


def abiertas(e: dict[str, Any], investigacion_id: str, maximo: int | None = None) -> list[dict[str, Any]]:
    """Las abiertas de la investigación, por prioridad (1 primero) y antigüedad."""
    salida = sorted((c for c in _propias(e, investigacion_id) if _estado_de(c) == "abierta"), key=_clave_orden)
    return _recortar_lista(salida, maximo)


def de_hipotesis(e: dict[str, Any], hipotesis_id: str) -> list[dict[str, Any]]:
    """Todas las cuestiones enganchadas a la hipótesis, abiertas primero."""
    if not hipotesis_id:
        return []

    def enganchada(c: dict[str, Any]) -> bool:
        origen = _origen_de(c)
        return hipotesis_id in _ids_limpios(c.get("hipotesisIds")) or (origen["id"] == hipotesis_id and origen["tipo"] in ("killer", "escalera"))

    propias = [c for c in _registros(e) if enganchada(c)]
    return sorted(propias, key=lambda c: (0 if _estado_de(c) == "abierta" else 1, *_clave_orden(c)))


def resumen(e: dict[str, Any], investigacion_id: str) -> dict[str, int]:
    conteo = {"abiertas": 0, "resueltas": 0, "descartadas": 0}
    for c in _propias(e, investigacion_id):
        conteo[{"abierta": "abiertas", "resuelta": "resueltas", "descartada": "descartadas"}[_estado_de(c)]] += 1
    return conteo


def _titulo_hipotesis(e: dict[str, Any], hipotesis_id: str | None) -> str:
    if not hipotesis_id:
        return ""
    for h in e.get("hipotesis", []) or []:
        if h.get("id") == hipotesis_id:
            return str(h.get("titulo") or "").strip()
    return ""


def _quien_abrio(c: dict[str, Any]) -> str:
    """Quién abrió la cuestión según el primer movimiento del historial; sin
    historial legible, Rosa (valor de hoy para un registro antiguo)."""
    historial = c.get("historial")
    if isinstance(historial, list):
        for m in historial:
            if isinstance(m, dict):
                return str(m.get("quien") or config.QUIEN_ROSA).strip() or config.QUIEN_ROSA
    return config.QUIEN_ROSA


def _de_persona(c: dict[str, Any]) -> bool:
    """True si la abrió alguien que no es Rosa."""
    return _quien_abrio(c) != config.QUIEN_ROSA


def etiqueta_origen(e: dict[str, Any], c: dict[str, Any]) -> str:
    """'Killer sobre H «título»', 'pregunta del modelo de mundo', 'persona
    (Dra. Allegri)'... Lo que ve el modelo para saber de dónde viene cada
    cuestión y, si la pidió una persona, quién."""
    origen = _origen_de(c)
    tipo = origen["tipo"]
    etiqueta = _ETIQUETAS_ORIGEN[tipo]
    if tipo in ("killer", "escalera"):
        hid = origen["id"] or next(iter(_ids_limpios(c.get("hipotesisIds"))), None)
        titulo = _titulo_hipotesis(e, hid)
        if titulo:
            etiqueta += f" sobre H «{titulo[:80]}»"
        elif hid:
            etiqueta += f" sobre H {hid}"
    elif tipo == "persona" and _de_persona(c):
        etiqueta += f" ({_quien_abrio(c)[:60]})"
    return etiqueta


def _linea(e: dict[str, Any], i: int, c: dict[str, Any], con_prioridad: bool = False) -> str:
    # Espacios y saltos de línea colapsados: una línea por cuestión, o el modelo
    # no puede señalarla por su número (un registro antiguo puede traer saltos).
    texto = _recortar(c.get("texto"))
    resolveria = _recortar(c.get("queLaResolveria"))
    linea = f"{i}. {texto}"
    if con_prioridad:
        linea += f" (prioridad {_acotar_prioridad(c.get('prioridad', PRIORIDAD_POR_DEFECTO))})"
    if resolveria:
        linea += f" (la resolvería: {resolveria})"
    return linea + f" [origen: {etiqueta_origen(e, c)}]"


def _total_abiertas(e: dict[str, Any], investigacion_id: str) -> int:
    return sum(1 for c in _propias(e, investigacion_id) if _estado_de(c) == "abierta")


def numeradas(e: dict[str, Any], investigacion_id: str, maximo: int = 15) -> tuple[str, list[dict[str, Any]]]:
    """Texto numerado de las abiertas y la lista en el mismo orden, para que
    el modelo señale por índice cuál resuelve un hecho nuevo (mismo patrón
    que `contexto.afirmaciones_sostenidas`)."""
    lista = abiertas(e, investigacion_id, maximo)
    if not lista:
        total = _total_abiertas(e, investigacion_id)
        # Con maximo 0 y cuestiones abiertas no se dice "ninguna": hay, pero no se listan.
        if total == 0:
            return "Ninguna cuestión abierta todavía.", []
        return ("Hay 1 cuestión abierta, no listada." if total == 1 else f"Hay {total} cuestiones abiertas, ninguna listada."), []
    return "\n".join(_linea(e, i + 1, c) for i, c in enumerate(lista)), lista


def texto_abiertas(e: dict[str, Any], investigacion_id: str, maximo: int = 8) -> str:
    """Las abiertas para el criterio de relevancia (qué se lee y por qué)."""
    lista = abiertas(e, investigacion_id, maximo)
    total = _total_abiertas(e, investigacion_id)
    if total == 0:
        return "Sin cuestiones abiertas todavía."
    cabecera = f"Cuestiones abiertas ({len(lista)} de {total}):"
    if not lista:
        return cabecera
    return cabecera + "\n" + "\n".join(_linea(e, i + 1, c, con_prioridad=True) for i, c in enumerate(lista))


def copiar_a_investigacion(e: dict[str, Any], origen_id: str, destino_id: str, mapa_hechos: dict[str, str] | None = None) -> int:
    """Al bifurcar o heredar el modelo de mundo, las cuestiones viajan con los
    hechos (`acciones.copiar_hechos`): cada cuestión de la investigación de
    origen se copia a la de destino con la misma regla de id que los hechos
    (`<id>-<id del destino>`, así lleva "-inv-" y `contexto.es_heredado` la
    reconoce), con `hechoIds` y el id del origen remapeados a las copias de los
    hechos según `mapa_hechos` (un enlace a un hecho que no viaja se conserva),
    y con el historial copiado, no compartido. Los `hipotesisIds` se quedan como
    están: las hipótesis no se copian al bifurcar. La copia conserva `creadaEn`
    y el historial del original (sin movimiento nuevo), así la poda al volver a
    una iteración la trata igual que a la original. Una copia que ya existe
    (misma llamada repetida) no se duplica. Devuelve cuántas copió."""
    if not origen_id or not destino_id or origen_id == destino_id:
        return 0
    mapa = {str(k): str(v) for k, v in (mapa_hechos or {}).items()} if isinstance(mapa_hechos, dict) else {}
    lista = _lista(e)
    existentes = {c.get("id") for c in _registros(e)}
    copiadas = 0
    for c in _propias(e, origen_id):
        nuevo_id = f"{c['id']}-{destino_id}" if isinstance(c.get("id"), str) and c["id"].strip() else P.nuevo_id("cu")
        if nuevo_id in existentes:
            continue
        origen = _origen_de(c)
        if origen["id"] in mapa:
            origen = {"tipo": origen["tipo"], "id": mapa[origen["id"]]}
        copia = {
            "id": nuevo_id,
            "investigacionId": destino_id,
            "texto": _recortar(c.get("texto")),
            "estado": _estado_de(c),
            "origen": origen,
            "queLaResolveria": _recortar(c.get("queLaResolveria")),
            "hipotesisIds": _ids_limpios(c.get("hipotesisIds")),
            "hechoIds": _ids_limpios([mapa.get(x, x) for x in _ids_limpios(c.get("hechoIds"))]),
            "prioridad": _acotar_prioridad(c.get("prioridad", PRIORIDAD_POR_DEFECTO)),
            "creadaEn": _creada_en(c),
            "actualizadaEn": _entero(c.get("actualizadaEn"), _creada_en(c)),
            "resueltaEn": c.get("resueltaEn") if _estado_de(c) == "resuelta" else None,
            "resolucion": dict(c["resolucion"]) if _estado_de(c) == "resuelta" and isinstance(c.get("resolucion"), dict) else None,
            "veces": max(1, _entero(c.get("veces"), 1)),
            "historial": [dict(m) for m in (c.get("historial") or []) if isinstance(m, dict)],
        }
        if copia["resolucion"] and copia["resolucion"].get("por") in mapa:
            copia["resolucion"]["por"] = mapa[copia["resolucion"]["por"]]
        if not copia["texto"]:
            continue  # una entrada rota del origen no se propaga
        lista.append(copia)
        existentes.add(nuevo_id)
        copiadas += 1
    return copiadas


def para_indice(e: dict[str, Any]) -> list[dict[str, Any]]:
    """Las abiertas como entradas del índice semántico: id 'cuestion:<id>',
    texto con la cuestión y lo que la resolvería, para reencontrarlas por
    significado cuando llega un hecho nuevo."""
    items: list[dict[str, Any]] = []
    for c in _registros(e):
        if _estado_de(c) != "abierta" or not c.get("id"):
            continue
        texto = f"{_recortar(c.get('texto'))}. {_recortar(c.get('queLaResolveria'))}".strip(". ")
        if texto:
            items.append({"id": f"cuestion:{c['id']}", "tipo": "cuestion", "investigacionId": c.get("investigacionId"), "texto": texto})
    return items


# ---------------------------------------------------------------------------
# Registro con deduplicación
# ---------------------------------------------------------------------------


def _fundir(existente: dict[str, Any], cuestion: dict[str, Any]) -> None:
    existente["hipotesisIds"] = _ids_limpios(_ids_limpios(existente.get("hipotesisIds")) + _ids_limpios(cuestion.get("hipotesisIds")))
    existente["hechoIds"] = _ids_limpios(_ids_limpios(existente.get("hechoIds")) + _ids_limpios(cuestion.get("hechoIds")))
    existente["veces"] = _entero(existente.get("veces"), 1) + 1
    existente["prioridad"] = min(_acotar_prioridad(existente.get("prioridad", PRIORIDAD_POR_DEFECTO)), _acotar_prioridad(cuestion.get("prioridad", PRIORIDAD_POR_DEFECTO)))
    cuando = _entero(cuestion.get("actualizadaEn"), _entero(cuestion.get("creadaEn")))
    existente["actualizadaEn"] = max(_entero(existente.get("actualizadaEn")), cuando)
    if not str(existente.get("queLaResolveria") or "").strip() and str(cuestion.get("queLaResolveria") or "").strip():
        existente["queLaResolveria"] = _recortar(cuestion["queLaResolveria"])
    # Si quien vuelve a preguntar es una persona, queda su huella en el historial
    # (mismo estado antes y después): sin ella, la poda al volver a una iteración
    # trataba la cuestión como solo de Rosa y borraba la pregunta de la médica.
    # Cuando repite Rosa (el Killer cada iteración) no se anota, para no inflarlo.
    if _de_persona(cuestion):
        if not isinstance(existente.get("historial"), list):
            existente["historial"] = []
        estado = _estado_de(existente)
        existente["historial"].append({"fecha": cuando or P.ahora_ms(), "de": estado, "a": estado, "quien": _quien_abrio(cuestion), "motivo": "Preguntada otra vez"})


def registrar_con_motivo(e: dict[str, Any], cuestion: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Mete la cuestión en el estado sin repetir y dice qué pasó.

    Devuelve (cuestión resultante o None, motivo). Motivos: 'nueva';
    'fundida con <id>: <regla>' (abierta equivalente: se unen ids, sube veces,
    baja prioridad); 'ya <resuelta|descartada>: <id>' (equivalente cerrada,
    se devuelve sin reabrir); 'texto vacío', 'sin investigación', 'cuestión
    inválida' y 'tope de N abiertas alcanzado' (no entra, None). El tope solo
    frena a las que abre Rosa: la pregunta de una persona entra siempre (el
    tope acota el ruido automático, no a la médica)."""
    lista = _lista(e)
    if not isinstance(cuestion, dict):
        return None, "cuestión inválida"
    if not normalizar(cuestion.get("texto") or ""):
        return None, "texto vacío"  # vacío o solo signos, sin letras ni cifras
    if not cuestion.get("investigacionId"):
        return None, "sin investigación"
    if not isinstance(cuestion.get("id"), str) or not cuestion["id"].strip():
        # Un dict armado a mano sin id entraba y después `buscar` no lo encontraba
        # nunca (ni resolver, ni cerradas_por_hecho): se le da id aquí.
        cuestion["id"] = P.nuevo_id("cu")
    ya = buscar(e, cuestion["id"])
    if ya is not None:
        return ya, f"ya registrada: {ya['id']}"
    inv_id = cuestion.get("investigacionId")
    propias = _propias(e, inv_id)
    # Primero una abierta equivalente (se funde), después una cerrada (se devuelve tal cual).
    for c in propias:
        if _estado_de(c) != "abierta":
            continue
        motivo = equivalencia(c.get("texto") or "", cuestion["texto"])
        if motivo:
            _fundir(c, cuestion)
            return c, f"fundida con {c.get('id')}: {motivo}"
    for c in propias:
        if _estado_de(c) == "abierta":
            continue
        motivo = equivalencia(c.get("texto") or "", cuestion["texto"])
        if motivo:
            return c, f"ya {_estado_de(c)}: {c.get('id')} ({motivo})"
    n_abiertas = sum(1 for c in propias if _estado_de(c) == "abierta")
    if n_abiertas >= MAX_CUESTIONES_ABIERTAS and not _de_persona(cuestion):
        return None, f"tope de {MAX_CUESTIONES_ABIERTAS} abiertas alcanzado"
    lista.append(cuestion)
    return cuestion, "nueva"


def registrar(e: dict[str, Any], cuestion: dict[str, Any]) -> dict[str, Any] | None:
    """Como `registrar_con_motivo`, devolviendo solo la cuestión (o None si no
    entró por tope o texto vacío)."""
    return registrar_con_motivo(e, cuestion)[0]


# ---------------------------------------------------------------------------
# Movimientos de estado
# ---------------------------------------------------------------------------


def _mover(c: dict[str, Any], a: str, quien: str, motivo: str, ahora: int, por: str | None = None) -> None:
    ahora = _ms(ahora)
    de = _estado_de(c)
    if not isinstance(c.get("historial"), list):
        c["historial"] = []  # registro antiguo sin historial (o con None): se empieza aquí
    movimiento: dict[str, Any] = {"fecha": ahora, "de": de, "a": a, "quien": str(quien or config.QUIEN_ROSA).strip() or config.QUIEN_ROSA, "motivo": _recortar(motivo, 400)}
    if por:
        movimiento["por"] = por  # quién o qué hecho la resolvió: la poda lo necesita para restaurar la resolución
    c["historial"].append(movimiento)
    c["estado"] = a
    c["actualizadaEn"] = ahora


def resolver(e: dict[str, Any], cuestion_id: str, por: str, motivo: str, ahora: int, quien: str = config.QUIEN_ROSA) -> bool:
    """Cierra una abierta como resuelta. `por` es el id del hecho que la
    responde o el nombre de la persona que la da por respondida."""
    c = buscar(e, cuestion_id)
    if c is None or _estado_de(c) != "abierta":
        return False
    ahora = _ms(ahora)
    por = str(por or "").strip() or str(quien or config.QUIEN_ROSA)
    motivo = str(motivo or "").strip() or "Resuelta"
    c["resolucion"] = {"por": por, "motivo": _recortar(motivo, 400)}
    c["resueltaEn"] = ahora
    _mover(c, "resuelta", quien, motivo, ahora, por=por)
    return True


def descartar(e: dict[str, Any], cuestion_id: str, motivo: str, quien: str, ahora: int) -> bool:
    """Cierra una abierta como descartada. Exige motivo, como el descarte de hipótesis."""
    c = buscar(e, cuestion_id)
    if c is None or _estado_de(c) != "abierta" or not str(motivo or "").strip():
        return False
    _mover(c, "descartada", quien, motivo, ahora)
    return True


def reabrir(e: dict[str, Any], cuestion_id: str, motivo: str, quien: str, ahora: int) -> bool:
    """Vuelve a abrir una resuelta o descartada; la resolución anterior queda
    en el historial y se limpia del objeto."""
    c = buscar(e, cuestion_id)
    if c is None or _estado_de(c) == "abierta":
        return False
    _mover(c, "abierta", quien, str(motivo or "").strip() or "Reabierta sin motivo declarado", ahora)
    c["resueltaEn"] = None
    c["resolucion"] = None
    return True


def podar_desde(e: dict[str, Any], investigacion_id: str, limite_ms: int) -> int:
    """Al volver a una iteración anterior (modelo de mundo): quita las
    cuestiones de la investigación creadas después del límite cuyo historial es
    todo de Rosa (misma regla que la poda de hechos en `acciones.volver_a_iteracion`);
    las que tocó una persona se quedan. En las creadas antes del límite se
    deshacen los movimientos posteriores hechos solo por Rosa (una resuelta por
    un hecho que se acaba de podar vuelve a abierta); si una persona intervino
    después del límite, no se toca. Devuelve cuántas quitó."""
    limite_ms = _ms(limite_ms)
    lista = _lista(e)
    conservadas: list[Any] = []
    quitadas = 0

    def de_rosa(m: dict[str, Any]) -> bool:
        return str(m.get("quien") or config.QUIEN_ROSA) == config.QUIEN_ROSA

    for c in lista:
        if not isinstance(c, dict) or c.get("investigacionId") != investigacion_id:
            conservadas.append(c)
            continue
        historial = [m for m in (c.get("historial") or []) if isinstance(m, dict)]
        if _creada_en(c) > limite_ms and all(de_rosa(m) for m in historial):
            quitadas += 1
            continue
        posteriores = [m for m in historial if _entero(m.get("fecha")) > limite_ms]
        if posteriores and all(de_rosa(m) for m in posteriores):
            c["historial"] = [m for m in historial if _entero(m.get("fecha")) <= limite_ms]
            estado = posteriores[0].get("de")
            c["estado"] = estado if estado in ESTADOS else "abierta"
            if c["estado"] == "resuelta":
                # Vuelve a la resolución que tenía en el límite (el movimiento que la
                # resolvió guarda `por`); antes se quedaba la resolución posterior,
                # apuntando a un hecho que la misma poda acababa de borrar.
                ultimo = next((m for m in reversed(c["historial"]) if m.get("a") == "resuelta"), None)
                if ultimo is not None:
                    c["resueltaEn"] = _entero(ultimo.get("fecha"), limite_ms)
                    c["resolucion"] = {"por": str(ultimo.get("por") or ultimo.get("quien") or config.QUIEN_ROSA), "motivo": str(ultimo.get("motivo") or "Resuelta")}
            else:
                c["resueltaEn"] = None
                c["resolucion"] = None
            c["actualizadaEn"] = limite_ms
        conservadas.append(c)
    lista[:] = conservadas  # en sitio: quien tenga la lista en la mano sigue viendo la misma
    return quitadas


# ---------------------------------------------------------------------------
# Ayudas para el integrador
# ---------------------------------------------------------------------------


def desde_pregunta_hecho(e: dict[str, Any], hecho: dict[str, Any], que_la_resolveria: str, ahora: int) -> dict[str, Any] | None:
    """Una pregunta del modelo de mundo (hecho tipo 'pregunta') como cuestión:
    origen pregunta_modelo con el id del hecho, enganchada a ese hecho, con su
    prioridad. Devuelve la cuestión registrada (o la equivalente ya existente),
    None si no entró."""
    if not isinstance(hecho, dict) or not str(hecho.get("enunciado") or "").strip():
        return None
    c = nueva(hecho.get("investigacionId"), hecho["enunciado"], {"tipo": "pregunta_modelo", "id": hecho.get("id")}, que_la_resolveria, ahora, prioridad=hecho.get("prioridad", PRIORIDAD_POR_DEFECTO), hecho_ids=[hecho.get("id")] if hecho.get("id") else [])
    return registrar(e, c)


def desde_killer(e: dict[str, Any], h: dict[str, Any], que_haria_falta: str, ahora: int) -> dict[str, Any] | None:
    """Lo que el Killer dice que haría falta para que la hipótesis avance,
    como cuestión de prioridad 3 enganchada a la hipótesis."""
    if not isinstance(h, dict) or not str(que_haria_falta or "").strip():
        return None
    titulo = str(h.get("titulo") or "").strip()[:80]
    resolveria = f"Una afirmación sostenida o un análisis que aporte eso para «{titulo}»" if titulo else "Una afirmación sostenida o un análisis que aporte eso"
    c = nueva(h.get("investigacionId"), que_haria_falta, {"tipo": "killer", "id": h.get("id")}, resolveria, ahora, prioridad=3, hipotesis_ids=[h.get("id")] if h.get("id") else [])
    return registrar(e, c)


def desde_escalera(e: dict[str, Any], h: dict[str, Any], falta: str, ahora: int) -> dict[str, Any] | None:
    """El peldaño siguiente de la escalera de certeza (rosa/certeza.py) como
    cuestión de prioridad 4 enganchada a la hipótesis."""
    if not isinstance(h, dict) or not str(falta or "").strip():
        return None
    titulo = str(h.get("titulo") or "").strip()[:80]
    resolveria = f"Evidencia que suba un peldaño la certeza de «{titulo}»" if titulo else "Evidencia que suba un peldaño la certeza de la hipótesis"
    c = nueva(h.get("investigacionId"), falta, {"tipo": "escalera", "id": h.get("id")}, resolveria, ahora, prioridad=4, hipotesis_ids=[h.get("id")] if h.get("id") else [])
    return registrar(e, c)


def cerradas_por_hecho(e: dict[str, Any], investigacion_id: str, hecho: dict[str, Any], indices: list[Any], numeradas_lista: list[dict[str, Any]], ahora: int) -> list[str]:
    """Resuelve las cuestiones que el modelo señaló por índice (1-based sobre
    `numeradas_lista`) con el hecho nuevo. Índices fuera de rango, repetidos o
    no numéricos se ignoran. Solo resuelve un hecho de tipo 'hecho' (un registro
    antiguo sin tipo cuenta como tal) que no esté descartado: una pregunta no
    responde a otra pregunta, una conjetura (tipo 'hipotesis') tampoco, y un
    hecho descartado ya no es conocimiento. Devuelve los ids resueltos."""
    if not isinstance(hecho, dict) or not hecho.get("id"):
        return []
    if (hecho.get("tipo") or "hecho") != "hecho" or hecho.get("estado") == "descartado":
        return []
    resueltas: list[str] = []
    vistos: set[int] = set()
    enunciado = _recortar(hecho.get("enunciado"), 200)
    motivo = f"Respondida por el hecho: {enunciado}" if enunciado else f"Respondida por el hecho {hecho['id']}"
    if isinstance(indices, (str, bytes)) or not isinstance(indices, (list, tuple, set, frozenset)):
        indices = []  # una cadena "1, 3" no es una lista de índices; no se adivina
    for i in indices:
        if isinstance(i, bool):
            continue  # True valdría 1 y resolvería la primera sin que nadie la señalara
        try:
            k = int(i)
        except (TypeError, ValueError):
            continue
        if k in vistos or not 1 <= k <= len(numeradas_lista):
            continue
        vistos.add(k)
        c = numeradas_lista[k - 1]
        if not isinstance(c, dict) or c.get("investigacionId") != investigacion_id:
            continue
        if resolver(e, c.get("id"), str(hecho["id"]), motivo, ahora):
            resueltas.append(c["id"])
    return resueltas
