"""Hechos del modelo de mundo: cuándo dos hechos son el mismo, cómo se funden
y cómo se enlazan con las afirmaciones que los sostienen (hallazgo M-08 de la
revisión del 17 de septiembre de 2026, con las guardas que pidió el adversario
del 18 de septiembre).

Regla de "mismo hecho" (`mismo_hecho`), la misma que `mismoHecho` en
frontend/src/datos/acciones.ts:

1. Solo se comparan hechos de la misma investigación, del mismo tipo (hecho
   con hecho, pregunta con pregunta; las entradas de revisión de una
   hipótesis, tipo `hipotesis`, nunca se funden) y en el mismo estado. Un
   hecho sabido y su versión descartada no son duplicados: alguien decidió
   sobre uno de ellos.
2. Dos hechos enlazados entre sí por `sustituyeA`, `sustituidoPor` o
   `contradiceA` tampoco: uno sustituye o contradice al otro a propósito.
3. Texto normalizado idéntico (minúsculas, sin tildes ni signos, letras
   griegas por su nombre): mismo hecho, venga de donde venga.
4. Paráfrasis (`cuestiones.equivalencia`: solape de tokens largos de al menos
   0,8, mismas marcas cortas, mismo orden cuando comparten una palabra de
   dirección) solo con cuatro guardas más, las mismas que aplica el bucle en
   rosa/bucle/pasos.py hecho_duplicado para que las dos mitades del hallazgo
   den lo mismo:
   a. comparten una referencia (`comparte_referencia`: mismo `fuenteId` o la
      misma referencia corta normalizada). Una paráfrasis con otra fuente es
      una replicación y vive aparte. Si ninguno de los dos tiene procedencia
      (dos preguntas del modelo, dos inferencias) no hay fuente que
      distinguir y la guarda no aplica;
   b. los mismos números, también escritos con letra (`numeros_de`:
      "excluyeron cuatro" y "excluyeron seis" son la misma bolsa de tokens
      largos);
   c. las mismas siglas y nombres con cifra tal como están escritos
      (`siglas_de`: GFAP frente a sTREM2 o YKL40, PSEN1 frente a APOE4; el
      solape de tokens los trata como una palabra más entre diez);
   d. las mismas negaciones largas (`negaciones_de`: "nunca", "jamás",
      "never"...; "no", "not", "sin" y "ni" ya son marcas cortas).
5. Si además comparten una referencia fina (una afirmación, o la misma fuente
   en la misma página) el umbral de solape baja a 0,6, con todas las guardas.
   La referencia compartida sola no basta: en el estado real del 18 de
   septiembre de 2026, 29 grupos de hechos compartían fuente y página y eran
   hechos distintos (el n, el comparador, el efecto de un mismo artículo), y
   tres afirmaciones sostenían dos hechos distintos cada una.

Medido sobre la copia del estado real (611 hechos): las 8 fusiones que hacía
la regla anterior comparten referencia, números, siglas y negaciones, así que
las guardas no pierden ninguna y cierran los pares que el adversario plantó.

Al fundir (`fundir`) sobrevive el hecho más antiguo de la lista y se le suman
la procedencia, las afirmaciones, las citas, las entidades y los enlaces del
repetido; queda un movimiento en su historial que nombra al repetido y el
motivo. `actualizadoEn` no cambia: fundir no es conocimiento nuevo. Un hecho
guardado con esas listas en null (no ausentes) se trata como si estuvieran
vacías (`_lista_en`), para que una herencia o una bifurcación no fallen
enteras por un registro antiguo.

Enlace con afirmaciones (`afirmaciones_que_sostienen`): una afirmación
sostiene un hecho si viene de la misma fuente (mismo `fuenteId`), está
sostenida o parcial, su página coincide con la del hecho cuando las dos se
conocen, no entra en conflicto con él (`conflicto`: no niega algo que el hecho
afirma ni al revés, y no cambia la sigla de la que habla), y o bien su texto
es equivalente al del hecho o bien cubre al menos el 60 % de los tokens con
contenido del hecho (sin la cita entre corchetes ni el nombre de la obra), con
todas las cifras del hecho presentes en la afirmación y sin invertir el orden
cuando comparten una palabra de dirección. Lo que se mide es qué parte del
hecho está en la afirmación; lo que la afirmación añade no cuenta, salvo una
negación adyacente a una palabra del hecho o una sigla que sustituye a la del
hecho, porque una frase de resultados paralela ("GFAP sube...", "NfL sube...",
"GFAP no sube...") comparte fuente, página y casi todas las palabras y dice
otra cosa. Un hecho sin afirmación que lo sostenga se queda sin enlace: eso es
"no pude comprobar", no "no hay". Se asume que la negación afecta a la
primera palabra con contenido que la sigue (hasta tres posiciones, saltando
las vacías) y que LCR/CSF, MCI/DCL y PET/TEP son la misma sigla en dos
idiomas.

`migrar` aplica las dos cosas a un estado ya guardado: primero enlaza, luego
funde por investigación, remapea lo que apuntaba a los repetidos (otros
hechos, `hechoIds`, origen y resolución de las cuestiones, las celdas del mapa
de la enfermedad y el detalle de reutilización de las cifras de aprendizaje) y
deja un evento por investigación cuando cambió algo. Es idempotente: la
segunda pasada no encuentra nada que fundir ni que enlazar y no escribe
evento. Los recuentos agregados del mapa y de las cifras se recalculan al
cerrar la siguiente iteración; aquí solo se corrigen los ids.
"""

from __future__ import annotations

import functools
import re
from typing import Any

from rosa import config
from rosa import cuestiones as CU
from rosa import verificador as V
from rosa.estado import plantilla as P

UMBRAL_MISMA_REFERENCIA = 0.6
UMBRAL_COBERTURA = 0.6
MINIMO_TOKENS_COMUNES = 5
TIPOS_FUNDIBLES = ("hecho", "pregunta")
VEREDICTOS_QUE_SOSTIENEN = ("sostenida", "parcial")
ENLACES_LISTA = ("sustituyeA", "resuelveA", "contradiceA")
_CITA_ENTRE_CORCHETES = re.compile(r"\[[^\]]*\]")
_PAGINA = re.compile(r"p[aá]g\.\s*(\d+)")
_TOKEN_CRUDO = re.compile(r"\w+(?:-\w+)*")

# Números escritos con letra: `cuestiones.equivalencia` solo distingue las
# cifras escritas con dígitos (marcas cortas). Misma lista que
# rosa/bucle/pasos.py _NUMEROS_EN_LETRA; cuando el bucle importe de aquí, una
# sola.
NUMEROS_EN_LETRA = frozenset(
    "cero uno una dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince veinte treinta cuarenta cincuenta cien ciento mil millon millones mitad tercio doble triple "
    "zero one two three four five six seven eight nine ten eleven twelve twenty thirty forty fifty hundred thousand million half third double triple".split()
)
# Negaciones de más de tres letras, ya normalizadas: el solape de tokens largos
# las trata como una palabra más y "nunca redujo" pasa por "redujo".
NEGACIONES_LARGAS = frozenset(CU.normalizar(p) for p in "nunca jamás tampoco ninguna ningún ninguno never neither nor none without".split())
# Negaciones que cambian el sentido de la palabra que sigue (las cortas son
# marcas cortas en `cuestiones`; aquí sirven para la guarda de adyacencia).
NEGACIONES = NEGACIONES_LARGAS | frozenset({"no", "not", "sin", "ni"})
# La misma sigla en dos idiomas: un hecho en castellano y una afirmación en
# inglés hablan de lo mismo. Solo pares de tres letras o más (las de dos, como
# AD, MC o NC, no cuentan como sigla).
SINONIMOS_SIGLA = {"csf": "lcr", "dcl": "mci", "tep": "pet"}
# Una referencia sin autor ("Sin autor", "Sin autor, 2023", que escribe
# rosa/fuentes/base.py cuando la fuente no trae autores) no identifica una obra:
# en el estado real del 18 de septiembre de 2026 la llevaban tres fuentes
# distintas. Solo el id de fuente vale para esas.
REFERENCIA_GENERICA = "sin autor"
_MAXIMO_SALTO_NEGACION = 3


# ---------------------------------------------------------------------------
# Mismo hecho
# ---------------------------------------------------------------------------


def _texto(v: Any) -> str:
    return str(v or "")


def _lista(v: Any) -> list[Any]:
    return list(v) if isinstance(v, list) else []


def _lista_en(h: dict[str, Any], clave: str) -> list[Any]:
    """La lista guardada en `h[clave]`, creándola vacía si falta o no es una
    lista (un registro antiguo con `afirmacionIds: null`). Devuelve la misma
    lista que queda en el hecho, para añadir en sitio."""
    v = h.get(clave)
    if not isinstance(v, list):
        v = []
        h[clave] = v
    return v


def sin_cita(texto: str) -> str:
    """El enunciado sin la cita entre corchetes que el paso de modelo añade al final."""
    return _CITA_ENTRE_CORCHETES.sub(" ", texto)


def referencias(h: dict[str, Any]) -> set[tuple[Any, ...]]:
    """Las referencias finas de un hecho: cada afirmación que lo sostiene y
    cada (fuente, página) de su procedencia con página conocida."""
    refs: set[tuple[Any, ...]] = {("af", str(a)) for a in _lista(h.get("afirmacionIds")) if a}
    for p in _lista(h.get("procedencia")):
        if isinstance(p, dict) and p.get("fuenteId") and p.get("pagina") is not None:
            refs.add(("fp", str(p["fuenteId"]), p["pagina"]))
    return refs


def _claves_de_referencia(procedencia: Any) -> set[tuple[str, str]]:
    salida: set[tuple[str, str]] = set()
    for p in _lista(procedencia):
        if not isinstance(p, dict):
            continue
        if p.get("fuenteId"):
            salida.add(("id", str(p["fuenteId"])))
        ref = CU.normalizar(_texto(p.get("referencia")))
        if ref and not ref.startswith(REFERENCIA_GENERICA):
            salida.add(("ref", ref))
    return salida


def comparte_referencia(procedencia_a: Any, procedencia_b: Any) -> bool:
    """True si las dos procedencias comparten una fuente (mismo `fuenteId`) o
    una referencia corta (misma cadena normalizada): la señal de que dos
    enunciados parecidos salen del mismo artículo y no de dos cohortes. Misma
    regla que rosa/bucle/pasos.py comparte_referencia (allí la referencia se
    normaliza con el verificador, que conserva la puntuación; aquí con
    `cuestiones.normalizar`, que la quita: "Belder et al., 2026" y "Belder et
    al. 2026" son la misma obra). Una referencia genérica ("Sin autor...") no
    cuenta: dos obras sin autor no son la misma obra."""
    return bool(_claves_de_referencia(procedencia_a) & _claves_de_referencia(procedencia_b))


def _tokens_de_referencias(*hechos: dict[str, Any]) -> set[str]:
    """Los tokens normalizados de las referencias de la procedencia: el nombre
    de la obra no es contenido del hecho ("Belder", "2026")."""
    salida: set[str] = set()
    for h in hechos:
        for p in _lista(h.get("procedencia")):
            if isinstance(p, dict):
                salida |= set(CU.normalizar(_texto(p.get("referencia"))).split())
    return salida


def numeros_de(texto: str) -> set[str]:
    """Las cifras del texto (normalizadas como en el verificador: "1.234,5" y
    "1,234.5" son la misma) y los números escritos con letra. Misma regla que
    rosa/bucle/pasos.py _numeros_de."""
    t = _texto(texto)
    return {tok for tok in CU.normalizar(t).split() if tok in NUMEROS_EN_LETRA} | set(V.cifras_de(t))


def negaciones_de(texto: str) -> set[str]:
    """Las negaciones largas del texto normalizado (nunca, jamás, never...)."""
    return {tok for tok in CU.normalizar(texto).split() if tok in NEGACIONES_LARGAS}


def siglas_de(texto: str, excluir: set[str] | frozenset[str] = frozenset()) -> set[str]:
    """Las siglas y los nombres con cifra del texto tal como está escrito:
    tokens de al menos tres caracteres con una mayúscula fuera de la primera
    letra (GFAP, sTREM2, NfL, ApoE) o con algún dígito (APOE4, p-tau217,
    YKL40), normalizados y sin espacios ("p-tau217" queda "ptau217"). Las
    palabras que solo empiezan por mayúscula (Belder, Treatment, La) no
    cuentan: son el principio de la frase o un nombre propio, y "Belder et
    al. señalan" y "Los autores señalan" son el mismo hecho. Fuera quedan las
    cifras sueltas (van en `numeros_de`), los tokens de `excluir` (la
    referencia de la obra) y "et"/"al". LCR/CSF, MCI/DCL y PET/TEP se
    reducen a una sola sigla."""
    salida: set[str] = set()
    for n, partes in _siglas_crudas(_texto(texto)):
        if n in excluir or all(p in excluir for p in partes):
            continue
        salida.add(SINONIMOS_SIGLA.get(n, n))
    return salida


@functools.lru_cache(maxsize=16384)
def _siglas_crudas(texto: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """(sigla normalizada, sus partes) de cada sigla del texto, antes de quitar
    las de la referencia. Con caché: enlazar compara cada hecho con todas las
    afirmaciones de su fuente y volvía a recorrer el mismo texto cientos de veces."""
    salida: dict[str, tuple[str, ...]] = {}
    for tok in _TOKEN_CRUDO.findall(texto):
        if len(tok) < 3:
            continue
        if not (any(c.isupper() for c in tok[1:]) or any(c.isdigit() for c in tok)):
            continue
        partes = tuple(CU.normalizar(tok).split())
        n = "".join(partes)
        if not n or n.isdigit() or n in ("et", "al"):
            continue
        salida.setdefault(n, partes)
    return tuple(salida.items())


def enlazados(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """True si uno sustituye o contradice al otro: no son repetidos, son una pareja deliberada."""
    ia, ib = a.get("id"), b.get("id")
    if not ia or not ib:
        return False
    for x, y in ((a, ib), (b, ia)):
        if y in _lista(x.get("sustituyeA")) or y in _lista(x.get("contradiceA")) or x.get("sustituidoPor") == y:
            return True
    return False


def guardas_de_parafrasis(a: dict[str, Any], b: dict[str, Any]) -> str | None:
    """Por qué dos hechos con palabras parecidas no pueden ser el mismo, o None
    si pasan las cuatro guardas: referencia compartida (cuando alguno tiene
    procedencia), mismos números, mismas siglas y mismas negaciones largas."""
    pa, pb = _lista(a.get("procedencia")), _lista(b.get("procedencia"))
    if (pa or pb) and not comparte_referencia(pa, pb):
        return "otra fuente sin referencia común: una replicación vive aparte"
    la, lb = sin_cita(_texto(a.get("enunciado"))), sin_cita(_texto(b.get("enunciado")))
    if numeros_de(la) != numeros_de(lb):
        return "números distintos"
    if negaciones_de(la) != negaciones_de(lb):
        return "una negación que el otro no tiene"
    ref = _tokens_de_referencias(a, b)
    if siglas_de(la, ref) != siglas_de(lb, ref):
        return "siglas distintas"
    return None


def mismo_hecho(a: dict[str, Any], b: dict[str, Any]) -> str | None:
    """Motivo por el que `a` y `b` son el mismo hecho, o None. Misma regla que
    `mismoHecho` en frontend/src/datos/acciones.ts."""
    if a is b or (a.get("id") and a.get("id") == b.get("id")):
        return None
    tipo = a.get("tipo")
    if tipo not in TIPOS_FUNDIBLES or b.get("tipo") != tipo:
        return None
    if a.get("estado") != b.get("estado") or a.get("investigacionId") != b.get("investigacionId"):
        return None
    if enlazados(a, b):
        return None
    ea, eb = _texto(a.get("enunciado")), _texto(b.get("enunciado"))
    na, nb = CU.normalizar(ea), CU.normalizar(eb)
    if not na or not nb:
        return None
    if na == nb:
        return "texto normalizado idéntico"
    if guardas_de_parafrasis(a, b):
        return None
    motivo = CU.equivalencia(ea, eb)
    if motivo:
        return motivo
    if not (referencias(a) & referencias(b)):
        return None
    if CU.marcas_cortas(ea) != CU.marcas_cortas(eb):
        return None
    j = CU.jaccard(ea, eb)
    if j < UMBRAL_MISMA_REFERENCIA:
        return None
    if (set(CU._perfil(ea)[3]) & set(CU._perfil(eb)[3]) & CU._DIRECCION) and not CU.mismo_orden(ea, eb):
        return None
    return f"misma referencia y solape de tokens {j:.2f} >= {UMBRAL_MISMA_REFERENCIA:.1f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Fundir
# ---------------------------------------------------------------------------


def _sumar(destino: list[Any], extra: list[Any], clave=None) -> None:
    """Añade a `destino` los elementos de `extra` que no estén ya, por igualdad o por `clave`."""
    vistos = {clave(x) if clave else _congelar(x) for x in destino}
    for x in extra:
        k = clave(x) if clave else _congelar(x)
        if k not in vistos:
            destino.append(x)
            vistos.add(k)


def _congelar(x: Any) -> Any:
    if isinstance(x, dict):
        return tuple(sorted((k, _congelar(v)) for k, v in x.items()))
    if isinstance(x, list):
        return tuple(_congelar(v) for v in x)
    return x


def fundir(destino: dict[str, Any], duplicado: dict[str, Any], ahora: int, motivo: str) -> None:
    """Suma al hecho `destino` lo que aporta `duplicado` y anota la fusión en
    el historial. Cambia `destino` en sitio; `duplicado` no se toca. Una lista
    guardada en null se trata como vacía. Misma regla que `fundirHechos` en
    frontend/src/datos/acciones.ts."""
    _sumar(_lista_en(destino, "procedencia"), [p for p in _lista(duplicado.get("procedencia")) if isinstance(p, dict)], lambda p: (p.get("fuenteId"), p.get("pagina")))
    _sumar(_lista_en(destino, "afirmacionIds"), [str(x) for x in _lista(duplicado.get("afirmacionIds")) if x])
    _sumar(_lista_en(destino, "citas"), [c for c in _lista(duplicado.get("citas")) if isinstance(c, dict)], lambda c: (c.get("referencia"), c.get("seccion")))
    if _lista(duplicado.get("entidades")):
        _sumar(_lista_en(destino, "entidades"), [x for x in _lista(duplicado.get("entidades")) if isinstance(x, dict)], lambda x: x.get("id"))
    for clave in ENLACES_LISTA:
        extra = [x for x in _lista(duplicado.get(clave)) if x and x != destino.get("id")]
        if extra or clave in destino:
            _sumar(_lista_en(destino, clave), extra)
    if not destino.get("sustituidoPor") and duplicado.get("sustituidoPor") and duplicado["sustituidoPor"] != destino.get("id"):
        destino["sustituidoPor"] = duplicado["sustituidoPor"]
    if not destino.get("pendienteRevision") and duplicado.get("pendienteRevision"):
        destino["pendienteRevision"] = duplicado["pendienteRevision"]
    if not destino.get("motivoDescarte") and duplicado.get("motivoDescarte"):
        destino["motivoDescarte"] = duplicado["motivoDescarte"]
    if destino.get("cerradoEn") is None and duplicado.get("cerradoEn") is not None:
        destino["cerradoEn"] = duplicado["cerradoEn"]
    try:
        destino["prioridad"] = max(int(destino.get("prioridad") or 0), int(duplicado.get("prioridad") or 0))
    except (TypeError, ValueError):
        pass
    estado = destino.get("estado")
    _lista_en(destino, "historial").append(
        {
            "fecha": int(ahora),
            "de": estado,
            "a": estado,
            "quien": config.QUIEN_ROSA,
            "motivo": f"Fundido con {duplicado.get('id')}: «{_texto(duplicado.get('enunciado'))[:160]}» ({motivo}); se suman su procedencia y sus afirmaciones",
        }
    )


def _clave_de_bloque(h: dict[str, Any]) -> tuple[Any, ...]:
    """Dos hechos solo pueden ser el mismo si coinciden en tipo, estado,
    investigación y marcas cortas (siglas cortas, cifras, negaciones): todas
    las vías de `mismo_hecho` lo exigen. Agrupar por esta clave evita comparar
    todos con todos sin cambiar el resultado (2.200 hechos, 200 repetidos: de
    3,8 s a 0,6 s; el estado real del 18 de septiembre de 2026, 611 hechos,
    tarda 0,1 s). Las guardas de paráfrasis no entran en la clave: la vía de
    texto idéntico no las exige y "GFAP" y "gfap" normalizan igual."""
    return (h.get("tipo"), h.get("estado"), h.get("investigacionId"), frozenset(CU.marcas_cortas(_texto(h.get("enunciado")))))


def fundir_duplicados(hechos: list[dict[str, Any]], ahora: int) -> tuple[list[dict[str, Any]], dict[str, str], list[tuple[str, str, str]]]:
    """Funde los hechos repetidos de una lista (en orden: el primero de cada
    grupo sobrevive). Devuelve (supervivientes, mapa id repetido a id
    superviviente, fusiones como (superviviente, repetido, motivo)). Los
    enlaces de los supervivientes que apuntaban a un repetido se remapean;
    un enlace de un hecho a sí mismo desaparece."""
    supervivientes: list[dict[str, Any]] = []
    bloques: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    mapa: dict[str, str] = {}
    fusiones: list[tuple[str, str, str]] = []
    for h in hechos:
        if not isinstance(h, dict):
            supervivientes.append(h)
            continue
        destino = None
        motivo = None
        candidatos = bloques.setdefault(_clave_de_bloque(h), [])
        for s in candidatos:
            motivo = mismo_hecho(s, h)
            if motivo:
                destino = s
                break
        if destino is None or motivo is None:
            supervivientes.append(h)
            candidatos.append(h)
            continue
        fundir(destino, h, ahora, motivo)
        if h.get("id"):
            mapa[str(h["id"])] = str(destino.get("id"))
            fusiones.append((str(destino.get("id")), str(h["id"]), motivo))
    if mapa:
        remapear_enlaces_de_hechos(supervivientes, mapa)
    return supervivientes, mapa, fusiones


def remapear_enlaces_de_hechos(hechos: list[dict[str, Any]], mapa: dict[str, str]) -> int:
    """Cambia en `hechos` los enlaces (sustituyeA, resuelveA, contradiceA,
    sustituidoPor) que apuntan a un id del mapa por su destino. Devuelve
    cuántos hechos cambiaron."""
    cambiados = 0
    for h in hechos:
        if not isinstance(h, dict):
            continue
        cambio = False
        for clave in ENLACES_LISTA:
            lista = h.get(clave)
            if not isinstance(lista, list) or not any(x in mapa for x in lista):
                continue
            nueva = list(dict.fromkeys(mapa.get(x, x) for x in lista))
            nueva = [x for x in nueva if x != h.get("id")]
            h[clave] = nueva
            cambio = True
        sp = h.get("sustituidoPor")
        if sp in mapa:
            h["sustituidoPor"] = None if mapa[sp] == h.get("id") else mapa[sp]
            cambio = True
        cambiados += 1 if cambio else 0
    return cambiados


def _remapear_lista_de_ids(contenedor: dict[str, Any], clave: str, mapa: dict[str, str]) -> bool:
    ids = contenedor.get(clave)
    if not isinstance(ids, list) or not any(x in mapa for x in ids):
        return False
    contenedor[clave] = list(dict.fromkeys(mapa.get(x, x) for x in ids))
    return True


def _remapear_investigacion(inv: dict[str, Any], mapa: dict[str, str]) -> bool:
    """Los ids de hechos que una investigación guarda fuera de `hechos`: las
    celdas del mapa de la enfermedad (`hechos` y `preguntas`) y el detalle de
    reutilización de las cifras de aprendizaje (`hechoId`). Dos filas del
    detalle que pasan a nombrar el mismo hecho se funden en una (se unen sus
    `usadoPor`)."""
    cambio = False
    m = inv.get("mapaEnfermedad")
    if isinstance(m, dict):
        for c in _lista(m.get("celdas")):
            if isinstance(c, dict):
                for clave in ("hechos", "preguntas"):
                    cambio = _remapear_lista_de_ids(c, clave, mapa) or cambio
    cif = inv.get("cifrasAprendizaje")
    reu = cif.get("reutilizacion") if isinstance(cif, dict) else None
    detalle = reu.get("detalle") if isinstance(reu, dict) else None
    if isinstance(detalle, list) and any(isinstance(d, dict) and d.get("hechoId") in mapa for d in detalle):
        nuevo: list[Any] = []
        por_id: dict[str, dict[str, Any]] = {}
        for d in detalle:
            if not isinstance(d, dict):
                nuevo.append(d)
                continue
            hid = d.get("hechoId")
            if hid in mapa:
                d["hechoId"] = hid = mapa[hid]
            previo = por_id.get(str(hid)) if hid else None
            if previo is None:
                nuevo.append(d)
                if hid:
                    por_id[str(hid)] = d
                continue
            _sumar(_lista_en(previo, "usadoPor"), [x for x in _lista(d.get("usadoPor")) if x])
        reu["detalle"] = nuevo
        cambio = True
    return cambio


def remapear_enlaces(e: dict[str, Any], mapa: dict[str, str]) -> int:
    """Remapea en todo el estado lo que apuntaba a un hecho fundido: los
    enlaces de los demás hechos; en las cuestiones, `hechoIds`, el id del
    origen y el hecho que las resolvió; y en cada investigación, las celdas
    del mapa de la enfermedad y el detalle de reutilización de las cifras.
    Devuelve cuántos registros cambiaron."""
    if not mapa:
        return 0
    cambiados = remapear_enlaces_de_hechos([h for h in _lista(e.get("hechos")) if isinstance(h, dict)], mapa)
    for c in _lista(e.get("cuestiones")):
        if not isinstance(c, dict):
            continue
        cambio = _remapear_lista_de_ids(c, "hechoIds", mapa)
        origen = c.get("origen")
        if isinstance(origen, dict) and origen.get("id") in mapa:
            origen["id"] = mapa[origen["id"]]
            cambio = True
        res = c.get("resolucion")
        if isinstance(res, dict) and res.get("por") in mapa:
            res["por"] = mapa[res["por"]]
            cambio = True
        cambiados += 1 if cambio else 0
    for inv in _lista(e.get("investigaciones")):
        if isinstance(inv, dict) and _remapear_investigacion(inv, mapa):
            cambiados += 1
    return cambiados


# ---------------------------------------------------------------------------
# Enlace con las afirmaciones que sostienen un hecho
# ---------------------------------------------------------------------------


def pagina_de(localizador: Any) -> int | None:
    m = _PAGINA.match(_texto(localizador).strip().lower())
    return int(m.group(1)) if m else None


def _contenido(texto: str) -> set[str]:
    return CU.tokens(texto) | CU.marcas_cortas(texto)


def _cifras(tokens: set[str]) -> set[str]:
    return {t for t in tokens if t.isdigit()}


@functools.lru_cache(maxsize=16384)
def negados_de(texto: str) -> frozenset[str]:
    """Las palabras con contenido que van justo detrás de una negación en el
    texto normalizado: en "GFAP no sube en portadores" es "sube"; en "no fue
    significativa", "significativa" (se saltan hasta tres palabras vacías).
    Es lo que la negación cambia de sentido."""
    partes = CU.normalizar(texto).split()
    salida: set[str] = set()
    for i, tok in enumerate(partes):
        if tok not in NEGACIONES:
            continue
        for sig in partes[i + 1 : i + 1 + _MAXIMO_SALTO_NEGACION]:
            if sig in NEGACIONES:
                break
            if sig not in CU._VACIAS_CORTAS:
                salida.add(sig)
                break
    return frozenset(salida)


def conflicto(hecho: dict[str, Any], afirmacion: dict[str, Any]) -> str | None:
    """Por qué la afirmación no puede sostener el hecho aunque comparta sus
    palabras, o None. Dos guardas simétricas: una palabra que los dos textos
    tienen y solo uno niega ("GFAP sube" frente a "GFAP no sube", "redujo"
    frente a "nunca redujo", "sin diferencia" frente a "diferencia"); y un
    cambio de sigla (al hecho le falta en la afirmación una sigla y la
    afirmación trae otra que el hecho no tiene: "GFAP sube..." frente a "NfL
    sube..."). Las cifras van aparte, en `cobertura`."""
    limpio = sin_cita(_texto(hecho.get("enunciado")))
    texto_af = _texto(afirmacion.get("texto"))
    comunes = _contenido(limpio) & _contenido(texto_af)
    if (negados_de(limpio) ^ negados_de(texto_af)) & comunes:
        return "niega una palabra que el otro afirma"
    ref = _tokens_de_referencias(hecho)
    sh, sa = siglas_de(limpio, ref), siglas_de(texto_af, ref)
    if (sh - sa) and (sa - sh):
        return "habla de otra sigla"
    return None


def cobertura(hecho: dict[str, Any], afirmacion: dict[str, Any]) -> float:
    """Qué parte de los tokens con contenido del hecho (sin la cita entre
    corchetes ni las palabras de la referencia de la obra) aparece en el texto
    de la afirmación. 0 si comparten menos de cinco tokens, si alguna cifra
    del hecho falta en la afirmación, si dicen la dirección al revés o si hay
    `conflicto` (negación adyacente, cambio de sigla)."""
    if conflicto(hecho, afirmacion):
        return 0.0
    return _cobertura_sin_guardas(hecho, afirmacion)


def _cobertura_sin_guardas(hecho: dict[str, Any], afirmacion: dict[str, Any]) -> float:
    limpio = sin_cita(_texto(hecho.get("enunciado")))
    texto_af = _texto(afirmacion.get("texto"))
    ref: set[str] = set()
    for p in _lista(hecho.get("procedencia")):
        if isinstance(p, dict):
            ref |= _contenido(_texto(p.get("referencia")))
    th = _contenido(limpio) - ref - {"et", "al"}
    ta = _contenido(texto_af)
    comunes = th & ta
    if not th or len(comunes) < MINIMO_TOKENS_COMUNES:
        return 0.0
    if not _cifras(th) <= _cifras(ta):
        return 0.0
    if (set(CU._perfil(limpio)[3]) & set(CU._perfil(texto_af)[3]) & CU._DIRECCION) and not CU.mismo_orden(limpio, texto_af):
        return 0.0
    return len(comunes) / len(th)


def sostiene(hecho: dict[str, Any], afirmacion: dict[str, Any]) -> bool:
    """True si la afirmación (de la misma fuente, sostenida o parcial, en la
    misma página cuando ambas se conocen, sin conflicto con el hecho) dice lo
    que dice el hecho."""
    fuentes = {p.get("fuenteId") for p in _lista(hecho.get("procedencia")) if isinstance(p, dict)}
    if not afirmacion.get("fuenteId") or afirmacion.get("fuenteId") not in fuentes:
        return False
    if afirmacion.get("veredicto") not in VEREDICTOS_QUE_SOSTIENEN:
        return False
    paginas = {p.get("pagina") for p in _lista(hecho.get("procedencia")) if isinstance(p, dict) and p.get("pagina") is not None}
    pagina = pagina_de(afirmacion.get("localizador"))
    if paginas and pagina is not None and pagina not in paginas:
        return False
    if conflicto(hecho, afirmacion):
        return False
    limpio = sin_cita(_texto(hecho.get("enunciado")))
    if CU.equivalencia(limpio, _texto(afirmacion.get("texto"))):
        return True
    return _cobertura_sin_guardas(hecho, afirmacion) >= UMBRAL_COBERTURA


def afirmaciones_que_sostienen(hecho: dict[str, Any], candidatas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Las afirmaciones de `candidatas` que sostienen el hecho, en su orden.
    Una lista vacía significa que no se pudo comprobar, no que el hecho sea falso."""
    if hecho.get("tipo") not in TIPOS_FUNDIBLES:
        return []
    vistas: set[str] = set()
    salida: list[dict[str, Any]] = []
    for a in candidatas:
        if not isinstance(a, dict) or not a.get("id") or a["id"] in vistas:
            continue
        if sostiene(hecho, a):
            vistas.add(str(a["id"]))
            salida.append(a)
    return salida


def enlazar(hecho: dict[str, Any], afirmaciones: list[dict[str, Any]]) -> int:
    """Añade al hecho los ids de las afirmaciones que lo sostienen y una cita
    por cada una (patrón Scite, como hace el paso de modelo). Devuelve cuántos
    enlaces nuevos. Idempotente; una lista guardada en null se trata como vacía."""
    nuevas = [a for a in afirmaciones_que_sostienen(hecho, afirmaciones) if str(a["id"]) not in {str(x) for x in _lista(hecho.get("afirmacionIds"))}]
    if not nuevas:
        return 0
    referencia_de = {p.get("fuenteId"): _texto(p.get("referencia")) for p in _lista(hecho.get("procedencia")) if isinstance(p, dict)}
    ids = _lista_en(hecho, "afirmacionIds")
    citas = _lista_en(hecho, "citas")
    for a in nuevas:
        ids.append(str(a["id"]))
        cita = {"referencia": referencia_de.get(a.get("fuenteId"), ""), "seccion": _texto(a.get("localizador")), "clasificacion": "apoya", "fragmento": _texto(a.get("fragmento"))[:300]}
        if not any(isinstance(c, dict) and c.get("referencia") == cita["referencia"] and c.get("seccion") == cita["seccion"] for c in citas):
            citas.append(cita)
    return len(nuevas)


def afirmaciones_por_fuente(e: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Las afirmaciones guardadas en las corridas (clave privada `_afirmaciones`),
    por id de fuente. Los ids de fuente son únicos en todo el estado, así que
    un hecho heredado encuentra las afirmaciones de la corrida de origen."""
    por_fuente: dict[str, list[dict[str, Any]]] = {}
    for c in _lista(e.get("corridas")):
        if not isinstance(c, dict):
            continue
        for a in _lista(c.get("_afirmaciones")):
            if isinstance(a, dict) and a.get("fuenteId"):
                por_fuente.setdefault(str(a["fuenteId"]), []).append(a)
    return por_fuente


# ---------------------------------------------------------------------------
# Migración de un estado guardado
# ---------------------------------------------------------------------------


def migrar(e: dict[str, Any], ahora: int | None = None) -> dict[str, int]:
    """Enlaza los hechos sin afirmaciones con las que quedan en las corridas y
    funde los repetidos de cada investigación, remapeando lo que apuntaba a
    ellos. Deja un evento por investigación que cambió. Idempotente.
    Devuelve el recuento: hechos enlazados, enlaces, hechos fundidos."""
    hechos = e.get("hechos")
    recuento = {"enlazados": 0, "enlaces": 0, "fundidos": 0}
    if not isinstance(hechos, list) or not hechos:
        return recuento
    t = int(ahora) if ahora is not None else P.ahora_ms()
    por_fuente = afirmaciones_por_fuente(e)
    enlazados_por_inv: dict[str, int] = {}
    if por_fuente:
        for h in hechos:
            if not isinstance(h, dict) or h.get("tipo") not in TIPOS_FUNDIBLES or _lista(h.get("afirmacionIds")):
                continue
            candidatas: list[dict[str, Any]] = []
            for p in _lista(h.get("procedencia")):
                if isinstance(p, dict) and p.get("fuenteId"):
                    candidatas.extend(por_fuente.get(str(p["fuenteId"]), []))
            if not candidatas:
                continue
            n = enlazar(h, candidatas)
            if n:
                recuento["enlazados"] += 1
                recuento["enlaces"] += n
                inv = str(h.get("investigacionId") or "")
                enlazados_por_inv[inv] = enlazados_por_inv.get(inv, 0) + 1
    por_inv: dict[str, list[dict[str, Any]]] = {}
    for h in hechos:
        if isinstance(h, dict):
            por_inv.setdefault(str(h.get("investigacionId") or ""), []).append(h)
    mapa: dict[str, str] = {}
    fusiones_por_inv: dict[str, list[tuple[str, str, str]]] = {}
    for inv, lista in por_inv.items():
        _, m, fusiones = fundir_duplicados(lista, t)
        if m:
            mapa.update(m)
            fusiones_por_inv[inv] = fusiones
    if mapa:
        e["hechos"] = [h for h in hechos if not (isinstance(h, dict) and str(h.get("id")) in mapa)]
        remapear_enlaces(e, mapa)
        recuento["fundidos"] = len(mapa)
    for inv in sorted(set(enlazados_por_inv) | set(fusiones_por_inv)):
        if not inv:
            continue
        partes = []
        fusiones = fusiones_por_inv.get(inv, [])
        if len(fusiones) == 1:
            partes.append("1 hecho repetido se fundió con el hecho más antiguo que decía lo mismo con otras palabras")
        elif fusiones:
            partes.append(f"{len(fusiones)} hechos repetidos se fundieron con el hecho más antiguo que decía lo mismo con otras palabras")
        n_enlazados = enlazados_por_inv.get(inv, 0)
        if n_enlazados == 1:
            partes.append("1 hecho quedó enlazado con las afirmaciones que lo sostienen")
        elif n_enlazados:
            partes.append(f"{n_enlazados} hechos quedaron enlazados con las afirmaciones que los sostienen")
        e.setdefault("eventos", []).append(P.nuevo_evento(inv, "hecho_nuevo", "Revisión del modelo de mundo al cargar: " + "; ".join(partes) + ".", f"#/investigaciones/{inv}/mundo", t))
    return recuento
