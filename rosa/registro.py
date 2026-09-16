"""Registro de versiones de una hipótesis: qué cambió de una versión a la
siguiente, campo a campo, y cómo se cuenta.

Reformular una hipótesis (rosa/estado/acciones.py, reformular_hipotesis) no
sobrescribe: guarda la versión anterior entera en `versiones` con la
instantánea de rosa/estado/plantilla.py version_de. Este módulo compara dos
de esas instantáneas (o una instantánea con la hipótesis actual) y devuelve
la lista de campos que cambiaron, en un orden fijo, con el valor de antes y
el de después. Todo es por regla, sin modelo: el mismo par de entradas da
siempre la misma salida, y cada entrada trae su motivo (el campo y los dos
valores).

Es el espejo exacto de frontend/src/lib/registro.ts: mismos campos, mismo
orden, mismas etiquetas y el mismo resumen en castellano. Los casos de
rosa/tests/test_registro.py y frontend/src/lib/registro.test.ts son los
mismos datos con la misma salida esperada; si un lado cambia, el otro tiene
que cambiar igual.

Reglas de tolerancia, iguales en los dos lados:
- Una clave ausente o None vale "" (vacío); una tarjeta None o ausente vale
  una tarjeta vacía, así que una tarjeta que aparece o desaparece entera
  cuenta campo a campo.
- Los riesgos (lista) se comparan unidos por "; " sin sus entradas vacías;
  un texto suelto en riesgos vale lo mismo que la lista ya unida.
- Los espacios de los extremos no cuentan como cambio. El conjunto de
  espacios que se recorta es el mismo en los dos lados (ESPACIOS): ni
  str.strip() ni String.prototype.trim() por separado, porque recortan
  conjuntos distintos (uno quita \\x1f y no el BOM, el otro al revés).
- Un valor que no es texto se normaliza igual en los dos lados: un número
  entero (también 2.0) se escribe sin decimales; un booleano, un
  diccionario o una lista anidada valen "" (no hay texto que enseñar), en
  vez de "True"/"true" o "{'a': 1}"/"[object Object]".
- Un recuento que no se puede hacer (clave ausente) es None, "no pude
  comprobar", nunca 0.
"""

from __future__ import annotations

import copy
import math
from typing import Any

Cambio = dict[str, str]

# Los campos que se comparan, en el orden en que se informan. Cada uno lleva
# su ruta dentro del diccionario, la etiqueta que ve una persona y el nombre
# con artículo que se usa dentro de la frase del resumen.
CAMPOS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("titulo", ("titulo",), "Título", "el título"),
    ("enunciado", ("enunciado",), "Enunciado", "el enunciado"),
    ("mecanismo", ("mecanismo",), "Mecanismo", "el mecanismo"),
    ("comprobacion.biomarcador", ("comprobacion", "biomarcador"), "Biomarcador", "el biomarcador"),
    ("comprobacion.cohorte", ("comprobacion", "cohorte"), "Cohorte", "la cohorte"),
    ("comprobacion.diseno", ("comprobacion", "diseno"), "Diseño", "el diseño"),
    ("tarjeta.diana", ("tarjeta", "diana"), "Diana", "la diana"),
    ("tarjeta.celula", ("tarjeta", "celula"), "Célula", "la célula"),
    ("tarjeta.etapa", ("tarjeta", "etapa"), "Etapa", "la etapa"),
    ("tarjeta.intervencion", ("tarjeta", "intervencion"), "Intervención", "la intervención"),
    ("tarjeta.direccion", ("tarjeta", "direccion"), "Dirección", "la dirección"),
    ("tarjeta.prediccionFalsable", ("tarjeta", "prediccionFalsable"), "Predicción falsable", "la predicción falsable"),
    ("tarjeta.riesgos", ("tarjeta", "riesgos"), "Riesgos", "los riesgos"),
    ("tarjeta.pasoRuta", ("tarjeta", "pasoRuta"), "Paso de la ruta", "el paso de la ruta"),
)

ORDEN_CAMPOS: tuple[str, ...] = tuple(c[0] for c in CAMPOS)
_RUTAS: dict[str, tuple[str, ...]] = {c[0]: c[1] for c in CAMPOS}
_ETIQUETAS: dict[str, str] = {c[0]: c[2] for c in CAMPOS}
_NOMBRES_EN_FRASE: dict[str, str] = {c[0]: c[3] for c in CAMPOS}

# Dos campos guardan identificadores, no texto: la dirección de la
# intervención y el paso de la ruta terapéutica. En el resumen se muestran con
# su etiqueta en castellano. Las del paso de la ruta son las mismas que
# PASO_RUTA en frontend/src/lib/etiquetas.ts (el mismo sitio que usa la
# pantalla) y sus claves las de PASOS_RUTA en rosa/estado/plantilla.py; si
# cambian allí, cambian aquí (los tests lo vigilan).
DIRECCION_LEGIBLE: dict[str, str] = {
    "aumenta": "aumenta",
    "disminuye": "disminuye",
    "modula": "modula",
    "sin_intervencion": "sin intervención",
}

PASO_RUTA_LEGIBLE: dict[str, str] = {
    "mecanismo": "Mecanismo",
    "opciones_intervencion": "Opciones de intervención",
    "compromiso_diana": "Compromiso de diana",
    "efecto_funcional": "Efecto funcional",
    "selectividad_toxicidad": "Selectividad y toxicidad",
    "exposicion": "Entrega y exposición",
    "replicacion_independiente": "Replicación independiente",
    "evidencia_poblacion": "Evidencia en la población",
}

# Un valor entra entre paréntesis en el resumen solo si es corto y de una
# sola línea; un enunciado de tres frases se nombra pero no se copia.
LARGO_MAXIMO_EN_RESUMEN = 40

SIN_CAMBIOS = "Sin cambios en los campos de la hipótesis"

# Cómo se nombra en el resumen un cambio guardado sin campo (registro roto):
# se dice que algo cambió, no se calla.
CAMPO_SIN_NOMBRE = "un campo sin nombre"

SEPARADOR_RIESGOS = "; "

# Los caracteres que se recortan en los extremos, en los dos lados igual: la
# unión de lo que quitan str.strip() en Python y trim() en JavaScript
# (espacio, tabulador, saltos de línea, separadores de información \x1c a
# \x1f, NEL, los espacios Unicode de la categoría Zs, los separadores de
# línea y párrafo y el BOM). Misma lista que ESPACIOS en registro.ts.
ESPACIOS = " \t\n\r\f\v\x1c\x1d\x1e\x1f\x85\u00a0\u1680" + "".join(chr(c) for c in range(0x2000, 0x200B)) + "\u2028\u2029\u202f\u205f\u3000\ufeff"


def _recortar(texto: str) -> str:
    return texto.strip(ESPACIOS)


def _leer(obj: Any, ruta: tuple[str, ...]) -> Any:
    """Baja por la ruta de claves; cualquier tramo que no sea un diccionario
    (None, tarjeta ausente, registro antiguo) devuelve None."""
    actual = obj
    for clave in ruta:
        if not isinstance(actual, dict):
            return None
        actual = actual.get(clave)
    return actual


def _escalar(valor: Any) -> str:
    """Un valor suelto a texto: el texto recortado; un número entero (también
    2.0) sin decimales; otro número tal cual; lo demás (None, booleanos,
    diccionarios, listas anidadas, NaN, infinito) es vacío. Misma regla que
    `escalar` en registro.ts, para que un valor que no es texto no separe
    los dos lados ("True" frente a "true", "{'a': 1}" frente a
    "[object Object]")."""
    if isinstance(valor, str):
        return _recortar(valor)
    if valor is None or isinstance(valor, bool):
        return ""
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, float):
        if math.isnan(valor) or math.isinf(valor):
            return ""
        if valor.is_integer():
            return str(int(valor))
        return repr(valor)
    return ""


def _texto(valor: Any) -> str:
    """Normaliza un valor a texto comparable: None es vacío, una lista se une
    por "; " sin sus entradas vacías, y los espacios de los extremos no
    cuentan."""
    if isinstance(valor, (list, tuple)):
        partes = [_escalar(x) for x in valor]
        return SEPARADOR_RIESGOS.join(p for p in partes if p)
    return _escalar(valor)


def valor_campo(h: Any, campo: Any) -> str:
    """El valor normalizado de un campo en una instantánea (o en la hipótesis
    actual). Campo desconocido (o que no es texto): vacío."""
    ruta = _RUTAS.get(campo) if isinstance(campo, str) else None
    if ruta is None:
        return ""
    return _texto(_leer(h, ruta))


def diff_hipotesis(antes: Any, despues: Any) -> list[Cambio]:
    """Los campos que cambiaron entre dos instantáneas, en el orden fijo de
    CAMPOS. Sin entradas cuando nada cambia. Tolera None, claves ausentes y
    tarjeta None: una tarjeta que aparece o desaparece entera cuenta campo a
    campo (solo los campos que dejan de estar vacíos o pasan a estarlo)."""
    cambios: list[Cambio] = []
    for campo in ORDEN_CAMPOS:
        a = valor_campo(antes, campo)
        d = valor_campo(despues, campo)
        if a != d:
            cambios.append({"campo": campo, "antes": a, "despues": d})
    return cambios


def etiqueta_campo(campo: Any) -> str:
    """La etiqueta en castellano de un campo del diff. Un campo desconocido
    vuelve tal cual, para que nunca se pierda en pantalla; uno que no es
    texto (None) es vacío."""
    if not isinstance(campo, str):
        return ""
    return _ETIQUETAS.get(campo, campo)


def valor_legible(campo: Any, valor: Any) -> str:
    """El valor tal como se enseña en el resumen: los identificadores de la
    dirección y del paso de la ruta pasan a su etiqueta; un identificador que
    no esté en la tabla se enseña con espacios en vez de guiones bajos; el
    resto del texto va tal cual. Un valor que no es texto se normaliza antes
    con la misma regla del diff."""
    texto = _texto(valor)
    if not texto:
        return ""
    if campo == "tarjeta.direccion":
        return DIRECCION_LEGIBLE.get(texto, texto.replace("_", " "))
    if campo == "tarjeta.pasoRuta":
        return PASO_RUTA_LEGIBLE.get(texto, texto.replace("_", " "))
    return texto


def _corto(texto: str) -> bool:
    return 0 < len(texto) <= LARGO_MAXIMO_EN_RESUMEN and "\n" not in texto and "\r" not in texto


def _detalle(campo: str, antes: str, despues: str) -> str:
    """Lo que va entre paréntesis detrás del nombre del campo: "(A -> B)" si
    los dos valores son cortos, "(nuevo: B)" si antes no había nada,
    "(quitado: A)" si ahora no hay nada, y nada si alguno es largo."""
    a = valor_legible(campo, antes)
    d = valor_legible(campo, despues)
    if a and d:
        return f" ({a} -> {d})" if _corto(a) and _corto(d) else ""
    if not a and _corto(d):
        return f" (nuevo: {d})"
    if not d and _corto(a):
        return f" (quitado: {a})"
    return ""


def resumen_diff(cambios: list[Cambio] | None) -> str:
    """Una frase en castellano con lo que cambió: "Cambió el enunciado y la
    cohorte (ADNI -> BioFINDER)". Sin cambios: SIN_CAMBIOS. Los campos van
    en el orden en que vienen (el de diff_hipotesis); uno desconocido se
    nombra por su clave; uno sin clave (registro roto) se nombra
    CAMPO_SIN_NOMBRE. Una entrada que no es diccionario, o una lista que no
    es lista, se ignora en vez de romper."""
    partes: list[str] = []
    for c in cambios if isinstance(cambios, (list, tuple)) else []:
        if not isinstance(c, dict):
            continue
        campo = c.get("campo")
        campo = campo if isinstance(campo, str) else ""
        nombre = _NOMBRES_EN_FRASE.get(campo) or campo or CAMPO_SIN_NOMBRE
        partes.append(nombre + _detalle(campo, _texto(c.get("antes")), _texto(c.get("despues"))))
    if not partes:
        return SIN_CAMBIOS
    if len(partes) == 1:
        lista = partes[0]
    else:
        lista = ", ".join(partes[:-1]) + " y " + partes[-1]
    return "Cambió " + lista


def _entero(valor: Any) -> int | None:
    """Un número de versión: un entero, o un flotante con valor entero (2.0
    llega así cuando el JSON pasó por Python), como Number.isInteger en el
    otro lado. Un booleano, un texto o 1.5 no valen."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return None


def instantanea_extendida(h: Any) -> dict[str, Any]:
    """Lo que la instantánea de version_de no guarda y conviene recordar de
    cada versión: certeza y dirección de la conclusión, cuántas afirmaciones
    y fuentes tenía, la última decisión del Killer y el Elo. Una clave que
    falta es None ("no pude comprobar"), no 0 ni ""; sin hipótesis, todo
    None."""
    if not isinstance(h, dict):
        return {"certeza": None, "direccion": None, "nAfirmaciones": None, "nFuentes": None, "decisionKiller": None, "elo": None}
    conclusion = h.get("conclusion")
    conclusion = conclusion if isinstance(conclusion, dict) else {}
    procedencia = h.get("procedencia")
    procedencia = procedencia if isinstance(procedencia, dict) else {}
    afirmaciones = h.get("afirmaciones")
    fuentes = procedencia.get("fuentes")
    return {
        "certeza": conclusion.get("certeza"),
        "direccion": conclusion.get("direccion"),
        "nAfirmaciones": len(afirmaciones) if isinstance(afirmaciones, list) else None,
        "nFuentes": len(fuentes) if isinstance(fuentes, list) else None,
        "decisionKiller": h.get("decisionKiller"),
        "elo": h.get("elo"),
    }


def version_con_diff(version_anterior: dict[str, Any], h_actual: Any, h_anterior: Any = None) -> dict[str, Any]:
    """Copia de la versión anterior con "cambios" (qué cambió de esa versión a
    la hipótesis actual) y las claves de instantanea_extendida. Se llama en
    el momento de reformular, con `h_actual` recién reformulada: así los
    cambios van de la versión n a la n+1. Para reconstruir la cadena entera
    más tarde está revisiones_prov. Si se pasa `h_anterior` (la hipótesis
    tal como estaba antes de reformular), las claves salen de ella; si no,
    las que la versión ya tuviera se conservan y las que falten quedan en
    None. No muta la entrada."""
    v = copy.deepcopy(version_anterior) if isinstance(version_anterior, dict) else {}
    v["cambios"] = diff_hipotesis(version_anterior, h_actual)
    extendida = instantanea_extendida(h_anterior)
    for clave, valor in extendida.items():
        if h_anterior is not None or clave not in v:
            v[clave] = valor
    return v


def _numeros_de_version(ordenadas: list[dict[str, Any]]) -> list[int]:
    """El número efectivo de cada versión guardada, ya ordenadas: el `n`
    declarado si avanza sobre el anterior; si falta, su posición; si se
    repite o retrocede, el anterior más uno. Así la cadena es estrictamente
    creciente y ninguna entidad aparece dos veces."""
    numeros: list[int] = []
    previo: int | None = None
    for i, v in enumerate(ordenadas):
        n = _entero(v.get("n"))
        if n is None:
            n = i + 1
        if previo is not None and n <= previo:
            n = previo + 1
        numeros.append(n)
        previo = n
    return numeros


def revisiones_prov(h: Any) -> list[dict[str, Any]]:
    """Las revisiones de la hipótesis para el RO-Crate (PROV wasRevisionOf):
    una por versión guardada, de la versión n a la n+1, con la fecha, quien
    la pidió y el motivo que guardó version_de, y los cambios recalculados
    desde las instantáneas (la versión guardada y la siguiente, que es la
    hipótesis actual para la última). Las versiones se ordenan por `n`
    (estable; una sin `n` toma su posición) y se numeran de forma
    estrictamente creciente (_numeros_de_version): un `n` repetido o una
    versión actual atrasada se corrigen para que cada entidad aparezca una
    vez y cada `revisionDe` sea la entidad anterior. Entradas que no son
    diccionarios se ignoran."""
    if not isinstance(h, dict):
        return []
    hid = h.get("id") or ""
    versiones = [v for v in (h.get("versiones") or []) if isinstance(v, dict)]
    con_indice = list(enumerate(versiones))
    con_indice.sort(key=lambda par: (_entero(par[1].get("n")) if _entero(par[1].get("n")) is not None else par[0] + 1, par[0]))
    ordenadas = [v for _, v in con_indice]
    numeros = _numeros_de_version(ordenadas)
    salida: list[dict[str, Any]] = []
    for i, v in enumerate(ordenadas):
        n = numeros[i]
        if i + 1 < len(ordenadas):
            siguiente: Any = ordenadas[i + 1]
            n_siguiente: int | None = numeros[i + 1]
        else:
            siguiente = h
            n_siguiente = _entero(h.get("version"))
        if n_siguiente is None or n_siguiente <= n:
            n_siguiente = n + 1
        salida.append({
            "entidad": f"hipotesis-{hid}-v{n_siguiente}",
            "revisionDe": f"hipotesis-{hid}-v{n}",
            "fecha": v.get("fecha"),
            "quien": _texto(v.get("quien")),
            "motivo": _texto(v.get("motivo")),
            "cambios": diff_hipotesis(v, siguiente),
        })
    return salida
