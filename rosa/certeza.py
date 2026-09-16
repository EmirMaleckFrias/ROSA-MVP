"""Techo de certeza por regla (GRADE), peso de la evidencia y la escalera para
subir.

La certeza de la evidencia sobre una hipótesis la escribe el juez
(`ConcluirHipotesis`), con sus factores y su explicación. Pero el nivel queda
acotado por una regla determinista sobre lo que Rosa tiene contado, igual que
el Killer o el riesgo de sesgo: el juez explica dentro de la caja, no la fija.

La regla solo baja, nunca sube. Con lo que hay en el registro:

Reglas de estructura (qué clase de evidencia hay):

- "sin apoyos": sin ninguna afirmación sostenida o parcial que cuente como
  apoyo (no sintética, no en contra, no socavada): muy baja.
- "una cohorte": solo literatura de una cohorte (o sin cohorte identificada),
  sin réplica ni evidencia directa: muy baja. Si el juez documentó un efecto
  grande, baja.
- "dos cohortes": solo literatura pero de dos o más cohortes distintas: como
  mucho baja.
- "evidencia directa": un resultado de laboratorio contra el prerregistro o un
  análisis in silico sobre datos reales (nunca sintéticos) de una cohorte:
  como mucho moderada.
- "réplica directa": evidencia directa y dos o más cohortes distintas: puede
  llegar a alta.

Reglas de peso (cuánto pesa lo que hay; 16 de septiembre de 2026):

Cada afirmación pesa según su relación con la hipótesis (`PESO_RELACION`), el
diseño del estudio del que viene (`PESO_DISENO`, solo penaliza lo conocido
como débil), el riesgo de sesgo de esa fuente (`PESO_SESGO`) y el tamaño de
muestra (`PESO_N`). El peso es el producto de esos factores con el signo de
la relación, y cada factor lleva su motivo (`peso_afirmacion`). La suma de los
apoyos es `aFavor`; la de las que contradicen, `enContra` (en positivo). Una
afirmación que socava no pesa por sí misma: descuenta el apoyo que ataca,
que deja de contar mientras esté socavado (`balance_pesos`).

- "en contra pesa": si enContra >= aFavor y enContra > 0: muy baja.
- "peso mínimo para baja": aFavor >= 1.0 (dos revisiones narrativas suman
  0.6 y no llegan).
- "peso mínimo para moderada": aFavor >= 1.5 y enContra <= aFavor / 2.
- "peso mínimo para alta": aFavor >= 2.5 y enContra <= aFavor / 3.

El nivel final es el menor entre el que da la estructura y el que da el peso,
y el motivo dice cuál de los dos frena. Lo que no apoya no cuenta como apoyo:
una afirmación que contradice, una que socava y una socavada quedan fuera de
las sostenidas que sostienen el techo, y una fuente cuyas afirmaciones
emparejables son todas de esa clase no aporta cohorte. Una fuente sin ninguna
afirmación emparejable (registros anteriores a la acumulación de evidencia)
sigue contando, porque no se puede afirmar lo contrario. Un registro antiguo
sin relación, sin tipo de estudio o sin riesgo de sesgo pesa 1.0 por cada
factor ausente: da exactamente lo que daba antes de esta regla. Una relación
vacía ("" o None) es la de origen; `socavadaPor` se acepta como lista o como
una sola cadena.

Emparejar una afirmación con su fuente (`fuente_de`): por `fuenteId` si lo
trae; si no, porque su cita empieza por "[" + referencia (la cita se construye
como "[referencia, localizador]"). Cuando varias referencias encajan gana la
más larga ("Kim et al., 2025, Nature" antes que "Kim et al., 2025"). Dos
fuentes con la misma referencia (dos artículos del mismo primer autor y año)
o con el mismo id (el mismo artículo citado en varias páginas) son una sola
identidad a efectos de emparejar: la afirmación empareja con todas, y la
cuenta de fuentes sin cohorte no repite la misma identidad. Todo lo que se
compara con una tabla (relación, diseño, riesgo de sesgo) se normaliza a
minúsculas sin espacios alrededor; un valor que no es texto se convierte a
texto y, si no se reconoce, no penaliza ni cuenta. Nada de lo que llega
rompe: una hipótesis o una afirmación que no sea un diccionario vale como
vacía.

Una hipótesis nueva de Rosa arranca casi siempre en muy baja y no es un
fallo: es el punto de partida de toda hipótesis que nadie ha probado. La
escalera dice qué le falta para el siguiente nivel, por regla, para que la
persona vea el camino en vez de una etiqueta roja; cuando lo que frena es el
peso, lo dice (apoyos de más peso, o resolver la evidencia en contra). Los
peldaños son consecutivos: cada uno da por cumplido lo que pidieron los
anteriores (la segunda cohorte, la evidencia directa y la réplica aportan
como mucho un apoyo de peso entero, 1.0, y el peso que un peldaño exigió
queda alcanzado para el siguiente), así que solo avisa del peso cuando
seguiría faltando después. La evidencia en contra que hoy frena se dice
siempre, porque está ahí. 15 y 16 de septiembre de 2026.
"""

from __future__ import annotations

import numbers
import re
from typing import Any

NIVELES = ("muy_baja", "baja", "moderada", "alta")
CLASES_DIRECTAS = ("observacion_original", "derivado")
VEREDICTOS_QUE_CUENTAN = ("sostenida", "parcial")
# La relación None es la de las afirmaciones que motivaron el nacimiento (de origen).
RELACIONES_APOYO = (None, "apoya", "apoya_indirecta")

PESO_RELACION: dict[str | None, float] = {"apoya": 1.0, "apoya_indirecta": 0.5, "contradice": -1.0, "socava": 0.0, None: 1.0}
# Solo penaliza lo conocido como débil; el resto de diseños y el desconocido pesan 1.0.
PESO_DISENO: dict[str, float] = {"revision_narrativa": 0.3, "otro": 0.5, "serie_de_casos": 0.5, "in_vitro": 0.6, "preclinico": 0.6, "transversal": 0.8}
PESO_SESGO: dict[str, float] = {"alto": 0.5, "algunas_dudas": 0.8}
PESO_N: dict[str, float] = {"menos_de_20": 0.7, "de_20_a_99": 0.9, "100_o_mas": 1.0, "desconocido": 1.0}
# Por nivel: (peso mínimo a favor, divisor máximo de la evidencia en contra respecto a la a favor).
UMBRALES_PESO: dict[str, tuple[float, int | None]] = {"baja": (1.0, None), "moderada": (1.5, 2), "alta": (2.5, 3)}

ETIQUETAS_RELACION: dict[str | None, str] = {None: "de origen", "apoya": "a favor", "apoya_indirecta": "apoyo indirecto", "contradice": "en contra", "socava": "socava un apoyo"}
ETIQUETAS_DISENO = {
    "revision_sistematica": "revisión sistemática", "ensayo_aleatorizado": "ensayo aleatorizado", "cohorte": "cohorte", "caso_control": "casos y controles",
    "transversal": "transversal", "serie_de_casos": "serie de casos", "preclinico": "preclínico", "in_vitro": "in vitro", "revision_narrativa": "revisión narrativa",
    "registro": "registro", "otro": "sin diseño reconocido",
}
ETIQUETAS_SESGO = {"bajo": "riesgo de sesgo bajo", "algunas_dudas": "algunas dudas de sesgo", "alto": "riesgo de sesgo alto"}
_MOTIVO_BAJO_PESO_BAJA = "los apoyos son de bajo peso (revisiones narrativas, sesgo alto o muestras pequeñas)"
_MOTIVOS_RELACION = {
    None: "de origen (motivó el nacimiento de la hipótesis): cuenta entera",
    "apoya": "a favor (misma población, marcador y sentido): cuenta entera",
    "apoya_indirecta": "apoyo indirecto (otra población, desenlace o plataforma): cuenta la mitad",
    "contradice": "en contra (misma población y marcador, sentido contrario o sin efecto): resta entera",
    "socava": "socava un apoyo: no pesa por sí misma, descuenta el apoyo que ataca",
}
# Lo que puede seguir a la referencia dentro de una cita "[referencia, localizador]".
_DELIMITADORES_CITA = ",;:] ."
_GENERICOS_COHORTE = {"cohorte", "cohort", "study", "estudio", "longitudinal", "portadores", "familias", "alzheimer", "disease", "enfermedad", "mutaciones", "carriers", "participantes", "pacientes", "et", "al", "the", "of", "de", "del", "la", "los", "las", "con", "and", "familial", "autosomal", "dominant", "autosómico", "dominante"}


def _tokens_cohorte(nombre: str) -> set[str]:
    limpio = re.sub(r"\(.*?\)", " ", (nombre or "").lower())
    return {t for t in re.findall(r"[a-záéíóúñ0-9][a-záéíóúñ0-9\-]{2,}", limpio) if t not in _GENERICOS_COHORTE}


def _norm(t: Any) -> str:
    return re.sub(r"\s+", " ", str(t or "")).strip().lower()


def _nivel_texto(nivel: str) -> str:
    return nivel.replace("_", " ")


def _dict(x: Any) -> dict[str, Any]:
    """Un diccionario o, si no lo es (None, texto, lista), uno vacío."""
    return x if isinstance(x, dict) else {}


def _dicts(x: Any) -> list[dict[str, Any]]:
    """Los diccionarios de una lista; cualquier otra cosa vale como lista vacía."""
    return [d for d in x if isinstance(d, dict)] if isinstance(x, (list, tuple)) else []


def _fuentes(h: Any) -> list[dict[str, Any]]:
    return _dicts(_dict(_dict(h).get("procedencia")).get("fuentes"))


def _afirmaciones(h: Any) -> list[dict[str, Any]]:
    return _dicts(_dict(h).get("afirmaciones"))


def _nombre_cohorte(f: dict[str, Any]) -> str:
    """El nombre de la cohorte de una fuente como texto limpio; vacío si no
    consta o no es texto."""
    nombre = f.get("cohorte")
    return str(nombre).strip() if isinstance(nombre, str) else ""


def _clave(v: Any) -> str | None:
    """Un valor que se compara con una tabla (relación, diseño, juicio de
    sesgo): texto en minúsculas sin espacios alrededor; None si está vacío.
    Lo que no es texto se convierte a texto para que nunca rompa una búsqueda
    en un diccionario; si no se reconoce, no cuenta ni penaliza."""
    if v is None or isinstance(v, bool):
        return None if v is None else str(v).lower()
    if isinstance(v, str):
        limpio = v.strip().lower()
        return limpio or None
    return str(v).strip().lower() or None


def _hashable(v: Any) -> bool:
    try:
        hash(v)
    except TypeError:
        return False
    return True


def etiqueta_relacion(rel: str | None) -> str:
    """La relación de una afirmación con la hipótesis en castellano: 'a favor',
    'apoyo indirecto', 'en contra', 'socava un apoyo' o 'de origen' (None o
    vacío, la que motivó el nacimiento)."""
    return ETIQUETAS_RELACION.get(_clave(rel), "relación sin clasificar")


def _relacion(a: dict[str, Any]) -> str | None:
    """La relación tal como cuenta: una clave ausente o vacía es None (de
    origen, la que motivó el nacimiento); el resto, en minúsculas."""
    return _clave(a.get("relacion"))


def _socavadores(a: dict[str, Any]) -> list[Any]:
    """Quiénes socavan esta afirmación: `socavadaPor` como lista; una cadena
    suelta cuenta como una. Vacío o ausente: nadie."""
    v = _dict(a).get("socavadaPor")
    if not v:
        return []
    if isinstance(v, (list, tuple, set, frozenset)):
        return list(v)
    return [v]


def socavada(a: dict[str, Any]) -> bool:
    """True si otra afirmación ataca el método o la inferencia de esta
    (`socavadaPor` no vacío): mientras lo esté, no cuenta como apoyo."""
    return bool(_socavadores(a))


def _cortes(cuerpo: str) -> list[int]:
    """Las longitudes de prefijo de una cita que pueden ser una referencia
    entera: hasta el final o hasta justo antes de un delimitador, de la más
    larga a la más corta (gana la referencia más larga que encaje)."""
    cortes = [k for k, c in enumerate(cuerpo) if k > 0 and c in _DELIMITADORES_CITA]
    cortes.append(len(cuerpo))
    return sorted(set(cortes), reverse=True)


class _Indice:
    """Las fuentes de una hipótesis indexadas por id y por referencia
    normalizada, para emparejar cada afirmación en tiempo constante. Las
    fuentes que comparten id o referencia son una identidad: la afirmación
    empareja con todas."""

    def __init__(self, fuentes: list[dict[str, Any]]) -> None:
        self.fuentes = fuentes
        self.por_id: dict[Any, list[int]] = {}
        self.por_ref: dict[str, list[int]] = {}
        self.identidad: list[Any] = []
        for j, f in enumerate(fuentes):
            fid = f.get("id")
            ref = _norm(f.get("referencia")).rstrip(".")
            if fid and _hashable(fid):
                self.por_id.setdefault(fid, []).append(j)
            if ref:
                self.por_ref.setdefault(ref, []).append(j)
            self.identidad.append(("id", fid) if fid and _hashable(fid) else (("ref", ref) if ref else ("pos", j)))

    def resolver(self, a: dict[str, Any]) -> list[int]:
        """Los índices de las fuentes con las que empareja la afirmación; []
        si ninguna."""
        fid = a.get("fuenteId")
        if fid and _hashable(fid) and fid in self.por_id:
            return self.por_id[fid]
        cita = _norm(a.get("cita"))
        if not cita or not self.por_ref:
            return []
        cuerpos = (cita[1:], cita) if cita.startswith("[") else (cita,)
        for cuerpo in cuerpos:
            for k in _cortes(cuerpo):
                encontrados = self.por_ref.get(cuerpo[:k])
                if encontrados:
                    return encontrados
        return []


def fuente_de(h: dict[str, Any], a: dict[str, Any]) -> dict[str, Any] | None:
    """La fuente de la procedencia de la que viene la afirmación: por
    `fuenteId` si lo trae, o porque su cita empieza por "[" + referencia de la
    fuente (sin distinguir mayúsculas ni espacios; gana la referencia más
    larga que encaje). Si varias fuentes comparten id o referencia, la
    primera. None si no se puede emparejar: entonces ni el diseño ni el sesgo
    la penalizan."""
    if not isinstance(a, dict):
        return None
    indice = _Indice(_fuentes(h))
    encontrados = indice.resolver(a)
    return indice.fuentes[encontrados[0]] if encontrados else None


def _entero(valor: Any) -> int | None:
    """El n como entero si se puede leer ("120", "n = 120", "104 participantes",
    120, 120.0, un entero de numpy); None si no consta."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, numbers.Integral):
        return int(valor)
    if isinstance(valor, numbers.Real):
        try:
            v = float(valor)
        except (TypeError, ValueError, OverflowError):
            return None
        return int(v) if v.is_integer() else None
    if not isinstance(valor, str):
        return None
    # Un número con signo menos delante ("-5") no es un n válido: no se lee.
    m = re.search(r"(?<![\d-])\d+(?:[.,]\d{3})*(?!\d)", valor)
    if not m:
        return None
    return int(re.sub(r"[.,]", "", m.group(0)))


def _tramo_n(n: int | None) -> str:
    """Un n que no consta o no es válido (cero o negativo) no penaliza."""
    if n is None or n <= 0:
        return "desconocido"
    if n < 20:
        return "menos_de_20"
    if n < 100:
        return "de_20_a_99"
    return "100_o_mas"


def _factor_relacion(a: dict[str, Any]) -> tuple[float, str]:
    """La magnitud con signo que aporta la relación, o 0 con el motivo por el
    que la afirmación no cuenta (sintética, no sostenida, socavada, socava)."""
    rel = _relacion(a)
    if a.get("sintetico"):
        return 0.0, "sintética (ensayo en seco): no cuenta como evidencia"
    if a.get("veredicto") not in VEREDICTOS_QUE_CUENTAN:
        return 0.0, f"veredicto {a.get('veredicto') or 'sin veredicto'}: solo cuentan las sostenidas o parciales"
    if socavada(a):
        cuantas = len(_socavadores(a))
        return 0.0, f"{etiqueta_relacion(rel)}, pero socavada por {cuantas} {'afirmación que ataca' if cuantas == 1 else 'afirmaciones que atacan'} su método o su inferencia: no cuenta mientras no se resuelva"
    if rel not in PESO_RELACION:
        return 0.0, f"relación '{rel}' sin clasificar: no cuenta"
    return PESO_RELACION[rel], _MOTIVOS_RELACION[rel]


def peso_afirmacion(a: dict[str, Any], fuente: dict[str, Any] | None = None) -> dict[str, Any]:
    """{peso, factores}: el peso de una afirmación como evidencia y por qué.
    Producto de la magnitud de la relación por el diseño, el sesgo y el n,
    con el signo de la relación; 0 si socava, si está socavada, si es
    sintética o si no está sostenida. Cada factor: {factor, valor, motivo}."""
    a = _dict(a)
    fuente = fuente if isinstance(fuente, dict) else None
    magnitud, motivo_rel = _factor_relacion(a)
    factores: list[dict[str, Any]] = [{"factor": "relacion", "valor": magnitud, "motivo": motivo_rel}]

    tipo = _clave((fuente or {}).get("tipoEstudio"))
    if fuente is None:
        d, motivo_d = 1.0, "sin fuente emparejada: el diseño no se penaliza"
    elif not tipo:
        d, motivo_d = 1.0, "diseño del estudio sin clasificar: no se penaliza"
    else:
        d = PESO_DISENO.get(tipo, 1.0)
        motivo_d = f"{ETIQUETAS_DISENO.get(tipo, tipo)}: " + ("no se penaliza" if d == 1.0 else f"pesa {d:g}")
    factores.append({"factor": "diseno", "valor": d, "motivo": motivo_d})

    global_ = _clave(_dict((fuente or {}).get("riesgoSesgo")).get("global"))
    if fuente is None:
        s, motivo_s = 1.0, "sin fuente emparejada: el sesgo no se penaliza"
    elif global_ not in PESO_SESGO and global_ != "bajo":
        s, motivo_s = 1.0, "riesgo de sesgo sin evaluar: no se penaliza"
    else:
        s = PESO_SESGO.get(global_, 1.0)
        motivo_s = f"{ETIQUETAS_SESGO.get(global_, global_)}: " + ("no se penaliza" if s == 1.0 else f"pesa {s:g}")
    factores.append({"factor": "sesgo", "valor": s, "motivo": motivo_s})

    n = _entero(a.get("n"))
    tramo = _tramo_n(n)
    pn = PESO_N[tramo]
    if tramo == "desconocido":
        motivo_n = "n desconocido o no válido: no se penaliza"
    elif pn == 1.0:
        motivo_n = f"n = {n}: no se penaliza"
    else:
        motivo_n = f"n = {n}: {'muestra pequeña' if tramo == 'menos_de_20' else 'muestra mediana (de 20 a 99)'}, pesa {pn:g}"
    factores.append({"factor": "n", "valor": pn, "motivo": motivo_n})

    signo = -1.0 if magnitud < 0 else 1.0
    peso = signo * abs(magnitud) * d * s * pn
    return {"peso": round(peso, 4) + 0.0, "factores": factores}


class _Vista:
    """Una sola pasada sobre la hipótesis: afirmaciones, fuentes, con qué
    fuente empareja cada afirmación y cuánto pesa. Todo lo que calcula el
    módulo sale de aquí, así que el coste crece con el tamaño del registro,
    no con su cuadrado."""

    def __init__(self, h: Any) -> None:
        self.fuentes = _fuentes(h)
        self.afs = _afirmaciones(h)
        self.indice = _Indice(self.fuentes)
        self.emparejadas: list[list[int]] = [self.indice.resolver(a) for a in self.afs]
        self.pesos: list[dict[str, Any]] = [peso_afirmacion(a, self.fuente_principal(i)) for i, a in enumerate(self.afs)]
        reales = [i for i, a in enumerate(self.afs) if a.get("veredicto") in VEREDICTOS_QUE_CUENTAN and not a.get("sintetico")]
        self.apoyos: list[int] = [i for i in reales if _relacion(self.afs[i]) in RELACIONES_APOYO and not socavada(self.afs[i])]
        self.contras: list[int] = [i for i in reales if _relacion(self.afs[i]) == "contradice"]
        self.socavadas = sum(1 for i in reales if socavada(self.afs[i]))
        self.socavan = sum(1 for i in reales if _relacion(self.afs[i]) == "socava")

    def fuente_principal(self, i: int) -> dict[str, Any] | None:
        encontrados = self.emparejadas[i]
        return self.fuentes[encontrados[0]] if encontrados else None

    def fuentes_que_cuentan(self) -> list[dict[str, Any]]:
        """Las fuentes que aportan cohorte: las que tienen al menos un apoyo no
        socavado emparejado, y las que no tienen ninguna afirmación emparejable
        (no se puede afirmar que no apoyen). Una fuente cuyas afirmaciones
        emparejables son todas en contra, socavan, están socavadas o no están
        sostenidas no cuenta."""
        if not self.afs:
            return self.fuentes
        de_apoyo = set(self.apoyos)
        con_afirmacion: set[int] = set()
        con_apoyo: set[int] = set()
        for i, encontrados in enumerate(self.emparejadas):
            for j in encontrados:
                con_afirmacion.add(j)
                if i in de_apoyo:
                    con_apoyo.add(j)
        return [f for j, f in enumerate(self.fuentes) if j not in con_afirmacion or j in con_apoyo]

    def cohortes(self) -> list[str]:
        # Método como nodo (rosa/metodos.py): el catálogo canónico con alias decide
        # qué nombres son la misma cohorte; sin catálogo, la regla de tokens de siempre.
        from rosa import metodos as METODOS

        return METODOS.cohortes_distintas([{**f, "id": f"c{i}"} for i, f in enumerate(self.fuentes_que_cuentan()) if _nombre_cohorte(f)])

    def sin_cohorte(self) -> int:
        """Cuántas identidades de fuente (mismo id o misma referencia son una)
        que aportan apoyo no tienen cohorte en ninguna de sus entradas."""
        posiciones = {id(f): j for j, f in enumerate(self.fuentes)}
        nombradas: set[Any] = set()
        vistas: list[Any] = []
        for f in self.fuentes_que_cuentan():
            clave = self.indice.identidad[posiciones[id(f)]]
            if clave not in vistas:
                vistas.append(clave)
            if _nombre_cohorte(f):
                nombradas.add(clave)
        return sum(1 for clave in vistas if clave not in nombradas)

    def directa(self) -> list[dict[str, Any]]:
        return [self.afs[i] for i in self.apoyos if self.afs[i].get("tipo") == "dato" and self.afs[i].get("clase") in CLASES_DIRECTAS]

    def motivos_bajo_peso(self) -> list[str]:
        """Qué resta peso a los apoyos, sin repetir: revisión narrativa, sesgo
        alto, muestra pequeña, apoyo solo indirecto."""
        vistos: list[str] = []
        for i in self.apoyos:
            for f in self.pesos[i]["factores"]:
                if 0.0 < f["valor"] < 1.0 and f["motivo"] not in vistos:
                    vistos.append(f["motivo"])
        return vistos

    def balance(self) -> dict[str, Any]:
        a_favor = round(sum(self.pesos[i]["peso"] for i in self.apoyos), 3) + 0.0
        en_contra = round(abs(sum(self.pesos[i]["peso"] for i in self.contras)), 3) + 0.0
        n_ap, n_co = len(self.apoyos), len(self.contras)
        partes = [f"{n_ap} {'apoyo' if n_ap == 1 else 'apoyos'} con peso {a_favor:g} a favor", f"{n_co} en contra con peso {en_contra:g}"]
        if self.socavadas:
            partes.append(f"{self.socavadas} {'apoyo socavado que no cuenta' if self.socavadas == 1 else 'apoyos socavados que no cuentan'}" + (f" ({self.socavan} {'afirmación lo socava' if self.socavan == 1 else 'afirmaciones los socavan'})" if self.socavan else ""))
        restan = self.motivos_bajo_peso()
        if restan:
            partes.append("resta peso: " + "; ".join(restan))
        return {"aFavor": a_favor, "enContra": en_contra, "socavadas": self.socavadas, "detalle": ". ".join(partes)}


def apoyos(h: dict[str, Any]) -> list[dict[str, Any]]:
    """Las afirmaciones que sostienen la hipótesis: sostenidas o parciales, no
    sintéticas, de origen o a favor (directo o indirecto) y no socavadas."""
    v = _Vista(h)
    return [v.afs[i] for i in v.apoyos]


def contras(h: dict[str, Any]) -> list[dict[str, Any]]:
    """Las afirmaciones sostenidas o parciales que contradicen la hipótesis."""
    v = _Vista(h)
    return [v.afs[i] for i in v.contras]


def sostenidas_reales(h: dict[str, Any]) -> list[dict[str, Any]]:
    """Afirmaciones sostenidas o parciales que cuentan como evidencia a favor:
    lo sintético (ensayo en seco) nunca cuenta, y desde el 16 de septiembre
    de 2026 tampoco las que contradicen, las que socavan ni las socavadas.
    Es `apoyos`; se conserva el nombre para quien ya lo usaba."""
    return apoyos(h)


def evidencia_directa(h: dict[str, Any]) -> list[dict[str, Any]]:
    """Las afirmaciones que vienen de datos, no de literatura: un resultado de
    laboratorio evaluado contra el prerregistro o un análisis in silico sobre
    datos reales."""
    return _Vista(h).directa()


def balance_pesos(h: dict[str, Any]) -> dict[str, Any]:
    """{aFavor, enContra, socavadas, detalle}: la suma de pesos de los apoyos,
    la de las que contradicen (en positivo), cuántos apoyos están socavados y
    un detalle en castellano de dónde sale cada cifra."""
    return _Vista(h).balance()


def cohortes_distintas(h: dict[str, Any]) -> list[str]:
    """Las cohortes nombradas en las fuentes de la hipótesis que aportan apoyo,
    agrupando los nombres que se refieren a la misma ("ADAD", "ADAD (Belder et
    al.)" y "Belder et al., cohorte ADAD" son una). Dos artículos de la misma
    cohorte son una sola evidencia; una fuente sin cohorte identificada no
    cuenta como independiente, porque no se puede afirmar que lo sea; una
    fuente que solo contradice o socava no aporta cohorte."""
    return _Vista(h).cohortes()


def fuentes_sin_cohorte(h: dict[str, Any]) -> int:
    """Cuántas fuentes que aportan apoyo no tienen la cohorte identificada (el
    mismo artículo citado en varias páginas cuenta una vez)."""
    return _Vista(h).sin_cohorte()


def efecto_grande_documentado(factores: list[Any]) -> bool:
    for f in factores or []:
        factor = f.get("factor") if isinstance(f, dict) else getattr(f, "factor", None)
        efecto = f.get("efecto") if isinstance(f, dict) else getattr(f, "efecto", None)
        if factor == "efecto_grande" and efecto == "sube":
            return True
    return False


def _frena_peso(a_favor: float, en_contra: float, nivel: str, restan: list[str] | None = None) -> str | None:
    """Por qué el peso no da para `nivel` ("peso mínimo para ..."), o None si
    da. `restan` son los factores que restan peso a los apoyos de hoy, para
    que el motivo diga cuáles."""
    minimo, divisor = UMBRALES_PESO[nivel]
    if a_favor < minimo:
        detalle = f" (resta peso: {'; '.join(restan)})" if restan else ""
        if nivel == "baja":
            return f"{_MOTIVO_BAJO_PESO_BAJA}: suman {a_favor:g} y baja exige al menos {minimo:g}{detalle}"
        return f"los apoyos pesan poco para {_nivel_texto(nivel)}: suman {a_favor:g} y hace falta al menos {minimo:g}{detalle}"
    if divisor and en_contra > a_favor / divisor:
        return f"la evidencia en contra ({en_contra:g}) pasa de {'la mitad' if divisor == 2 else 'un tercio'} de la a favor ({a_favor:g}), lo que {_nivel_texto(nivel)} no admite"
    return None


def _techo_peso(a_favor: float, en_contra: float) -> str:
    for nivel in ("alta", "moderada", "baja"):
        if _frena_peso(a_favor, en_contra, nivel) is None:
            return nivel
    return "muy_baja"


def _techo_estructura(v: _Vista, factores: list[Any] | None) -> tuple[str, str]:
    """El techo por la clase de evidencia que hay (cohortes, evidencia directa,
    efecto grande), dando por hecho que hay al menos un apoyo."""
    n = len(v.cohortes())
    directa = v.directa()
    sin = v.sin_cohorte()
    texto_cohortes = f"{n} cohortes distintas" if n >= 2 else ("una sola cohorte" if n == 1 else "ninguna cohorte identificada en las fuentes")
    if sin:
        texto_cohortes += f" ({sin} {'fuente' if sin == 1 else 'fuentes'} sin cohorte identificada, que no cuentan como independientes)"
    if directa:
        clases = sorted(str(a.get("clase")) for a in directa)
        que = "resultado de laboratorio" if "observacion_original" in clases else "análisis sobre datos reales"
        if n >= 2:
            return "alta", f"hay evidencia directa ({que}) y {texto_cohortes}"
        return "moderada", f"hay evidencia directa ({que}) pero {texto_cohortes}: falta la réplica independiente"
    if n >= 2:
        return "baja", f"solo literatura, sin experimento ni análisis sobre datos reales, aunque de {texto_cohortes}"
    if efecto_grande_documentado(factores or []):
        return "baja", f"solo literatura de {texto_cohortes}, pero el juez documentó un efecto grande"
    return "muy_baja", f"solo literatura de {texto_cohortes}, sin réplica ni evidencia directa"


def _techo(v: _Vista, factores: list[Any] | None) -> tuple[str, str]:
    balance = v.balance()
    a_favor, en_contra = balance["aFavor"], balance["enContra"]
    if not v.apoyos:
        if en_contra > 0:
            return "muy_baja", f"la evidencia en contra pesa tanto o más que la a favor (a favor {a_favor:g}, en contra {en_contra:g}): no queda ningún apoyo sostenido"
        if v.socavadas:
            return "muy_baja", f"no hay ninguna afirmación sostenida que no sea sintética y siga en pie: {v.socavadas} {'apoyo socavado' if v.socavadas == 1 else 'apoyos socavados'}"
        return "muy_baja", "no hay ninguna afirmación sostenida que no sea sintética"
    if en_contra > 0 and en_contra >= a_favor:
        return "muy_baja", f"la evidencia en contra pesa tanto o más que la a favor (a favor {a_favor:g}, en contra {en_contra:g})"
    nivel, motivo = _techo_estructura(v, factores)
    nivel_peso = _techo_peso(a_favor, en_contra)
    if NIVELES.index(nivel_peso) < NIVELES.index(nivel):
        freno = _frena_peso(a_favor, en_contra, NIVELES[NIVELES.index(nivel_peso) + 1], v.motivos_bajo_peso()) or ""
        return nivel_peso, f"{freno}; por la clase de evidencia llegaría a {_nivel_texto(nivel)} ({motivo})"
    return nivel, motivo


def techo(h: dict[str, Any], factores: list[Any] | None = None) -> tuple[str, str]:
    """(nivel máximo, motivo) con lo que hay en el registro de la hipótesis: el
    menor entre el techo por estructura y el techo por peso."""
    return _techo(_Vista(h), factores)


def acotar(certeza_del_juez: str, h: dict[str, Any], factores: list[Any] | None = None) -> dict[str, Any]:
    """La certeza final: la del juez si cabe bajo el techo; el techo si no.
    Devuelve {certeza, techo: {nivel, motivo, acotada, certezaDelJuez}}."""
    nivel, motivo = techo(h, factores)
    juez = _clave(certeza_del_juez)
    if juez not in NIVELES:
        juez = "muy_baja"
    final = juez if NIVELES.index(juez) <= NIVELES.index(nivel) else nivel
    return {"certeza": final, "techo": {"nivel": nivel, "motivo": motivo, "acotada": final != juez, "certezaDelJuez": juez}}


def _remedios_de_peso(v: _Vista) -> list[str]:
    """Qué apoyo de más peso haría falta, según qué factor resta en los apoyos
    de hoy: diseño (revisión narrativa, diseño sin reconocer, diseño débil),
    sesgo, muestra o relación solo indirecta. Si nada resta, otro apoyo."""
    # Qué factor resta en algún apoyo (valor entre 0 y 1) y qué diseños débiles hay.
    bajos = {f["factor"] for i in v.apoyos for f in v.pesos[i]["factores"] if 0.0 < f["valor"] < 1.0}
    disenos = {_clave((v.fuente_principal(i) or {}).get("tipoEstudio")) for i in v.apoyos} & set(PESO_DISENO)
    remedios: list[str] = []
    if "diseno" in bajos:
        if "revision_narrativa" in disenos:
            remedios.append("un estudio primario en vez de una revisión narrativa")
        if "otro" in disenos:
            remedios.append("identificar el diseño de los estudios que constan sin diseño reconocido (cohorte, casos y controles, ensayo), que hoy pesan la mitad")
        debiles = sorted(ETIQUETAS_DISENO.get(d, d) for d in disenos if d and d not in ("revision_narrativa", "otro"))
        if debiles:
            remedios.append("un estudio con diseño más fuerte (cohorte, casos y controles o ensayo) en vez de " + ", ".join(debiles))
    if "sesgo" in bajos:
        remedios.append("una fuente con menos riesgo de sesgo")
    if "n" in bajos:
        remedios.append("una muestra mayor (n de 100 o más)")
    if "relacion" in bajos and not remedios:
        remedios.append("un apoyo directo en la misma población y marcador, no solo indirecto")
    if not remedios:
        remedios.append("otro apoyo independiente")
    return remedios


def _falta_por_peso(v: _Vista, balance: dict[str, Any], nivel: str, extra: float = 0.0) -> str | None:
    """Lo que falta por peso para `nivel`, en el lenguaje de la escalera; None
    si el peso ya da. La evidencia en contra que hoy frena se dice siempre,
    con las cifras de hoy. `extra` es el peso que ya aportarían los peldaños
    anteriores y las piezas estructurales que este pide (una cohorte más, la
    evidencia directa, la réplica: 1.0 cada una como mucho): del peso a favor
    solo se avisa cuando seguiría faltando después."""
    minimo, divisor = UMBRALES_PESO[nivel]
    a_favor, en_contra = balance["aFavor"], balance["enContra"]
    if en_contra > 0 and (en_contra >= a_favor or (divisor and en_contra > a_favor / divisor)):
        n_contras = len(v.contras)
        limite = f" (para {_nivel_texto(nivel)} no puede pasar de {'la mitad' if divisor == 2 else 'un tercio'} de la a favor)" if divisor else ""
        return f"resolver la evidencia en contra: {n_contras} {'afirmación en contra pesa' if n_contras == 1 else 'afirmaciones en contra pesan'} {en_contra:g} frente a {a_favor:g} a favor{limite}"
    con_extra = round(a_favor + extra, 3)
    if con_extra < minimo:
        suma = f"suman {a_favor:g}" + (f" y con lo anterior llegarían a {con_extra:g}" if extra else "")
        return f"apoyos de más peso: {', '.join(_remedios_de_peso(v))} ({suma}; {_nivel_texto(nivel)} exige al menos {minimo:g})"
    return None


def escalera(h: dict[str, Any], certeza: str, factores: list[Any] | None = None) -> list[dict[str, str]]:
    """Qué le falta a la hipótesis para cada nivel por encima del actual, por
    regla. Cada peldaño: {de, a, falta}. Vacía si ya está en alta. Cuando lo
    que frena es el peso de la evidencia, el "falta" lo dice. Los peldaños
    son consecutivos: cada uno da por cumplido lo que pidieron los
    anteriores."""
    v = _Vista(h)
    cohortes = len(v.cohortes())
    directa = bool(v.directa())
    balance = v.balance()
    a_favor = balance["aFavor"]
    nivel_actual = _clave(certeza)
    actual = NIVELES.index(nivel_actual) if nivel_actual in NIVELES else 0
    # Peso que ya aportarían los peldaños anteriores: las piezas estructurales
    # que pidieron (la segunda cohorte, la evidencia directa, la réplica; 1.0 cada
    # una) y el peso mínimo que exigieron, que al llegar a ese nivel se alcanzó.
    acumulado = 0.0
    pasos: list[dict[str, str]] = []

    def peldano(de: str, a: str, pieza: str | None, por_defecto: str) -> None:
        nonlocal acumulado
        if pieza is not None:
            acumulado += 1.0
        freno = _falta_por_peso(v, balance, a, acumulado)
        if pieza is not None:
            falta = pieza + (f"; además, {freno}" if freno else "")
        else:
            falta = freno or por_defecto
        minimo = UMBRALES_PESO[a][0]
        if a_favor + acumulado < minimo:
            acumulado = round(minimo - a_favor, 3)
        pasos.append({"de": de, "a": a, "falta": falta})

    if actual < 1:
        pieza = None
        if cohortes < 2:
            pieza = "una segunda cohorte independiente que muestre lo mismo (en la literatura o por análisis), o un efecto grande documentado en la evidencia que ya hay"
            sin = v.sin_cohorte()
            if sin:
                pieza += f"; {sin} de sus fuentes no tienen la cohorte identificada: nombrarla (qué estudio o población) puede bastar"
        peldano("muy_baja", "baja", pieza, "que el juez deje de ver riesgo de sesgo, inconsistencia o imprecisión graves en las cohortes que ya hay")
    if actual < 2:
        pieza = None if directa else "evidencia directa: un análisis in silico sobre un dataset público aprobado (no sintético) o un resultado de laboratorio contra el prerregistro"
        peldano("baja", "moderada", pieza, "que la evidencia directa sea consistente y precisa: intervalo que no cruce el efecto mínimo")
    if actual < 3:
        pieza = None if (cohortes >= 2 and directa) else "réplica de ese resultado directo en una cohorte independiente, con las reglas de análisis congeladas antes de mirar los datos"
        peldano("moderada", "alta", pieza, "consistencia entre las cohortes y ausencia de sesgo de publicación")
    return pasos
