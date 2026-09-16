"""Ruta terapéutica por regla: qué paso de los ocho tiene evidencia, cuál toca
y si el paso que declara la tarjeta va por delante de lo que hay.

La ruta terapéutica (plan completo ROSA2018, sección 10) son los ocho pasos
que separan una idea sobre un mecanismo de una evidencia útil en personas:
mecanismo, opciones de intervención, compromiso de diana, efecto funcional,
selectividad y toxicidad, entrega y exposición, replicación independiente y
evidencia en la población. Hasta ahora existía solo como etiqueta
(`tarjeta.pasoRuta`, elegida por el modelo o por una persona) y la interfaz la
dibujaba con el paso declarado en color; `rosa/dossier.py` recuerda que
completar un paso no completa la ruta. Aquí cada paso se calcula con una regla
determinista sobre lo que hay en el estado, con su evidencia y su motivo, y la
etiqueta declarada se contrasta con lo calculado.

Vocabulario, para quien no viene de biología:

- Diana: la molécula o el proceso sobre el que se quiere actuar (GFAP, la
  activación de los astrocitos). Biomarcador: lo que se mide para saber si la
  diana cambió (GFAP en plasma).
- Compromiso de diana (target engagement): la prueba de que la intervención o
  la medida llega a la diana y la cambia de forma medible.
- Exposición: que el fármaco o el marcador llega a donde tiene que llegar
  (sangre, LCR, cerebro) con qué dosis y cuánto tiempo. LCR es el líquido
  cefalorraquídeo, el que rodea el cerebro; la barrera hematoencefálica es el
  filtro entre la sangre y el cerebro.
- Cohorte: un grupo de personas estudiado junto (ADNI, BioFINDER). Dos
  artículos de la misma cohorte son una sola evidencia.
- GRADE: la escala de certeza de la medicina basada en evidencia (muy baja,
  baja, moderada, alta) que usa `rosa/certeza.py`.

Estados de un paso:

- cubierto: hay evidencia de la clase que el paso pide.
- parcial: hay algo (declarado, mencionado o medido a medias) pero no lo que
  el paso pide.
- vacio: se miró y no hay nada para el paso.
- no_comprobable: la información para juzgar no está (afirmaciones sin
  verificar, fuentes sin tipo de estudio, ejecuciones sin auditar, hipótesis
  sin tarjeta). Nunca se convierte en "vacío": una cosa es no haber y otra no
  poder mirar.

Qué cuenta en cada paso (todo determinista; el motivo va con el valor). Un
"apoyo" es lo que `certeza.apoyos` cuenta: afirmación sostenida o parcial,
no sintética, con relación de origen, a favor o a favor indirecta, y no
socavada. "Verificada" es sostenida o parcial no sintética, en cualquier
relación (también las que contradicen): sirve para los pasos en los que el
sentido no importa, solo si el terreno se miró.

1. mecanismo: apoyos (afirmaciones) y hechos del modelo de mundo enlazados a
   la hipótesis por `afirmacionIds` (no descartados ni sustituidos). Uno solo
   es parcial; dos o más, cubierto; uno con el grafo causal identificable o
   acotado (`h.grafoCausal.identificacion != sin_resolver`), cubierto: el
   grafo refuerza, no sustituye.
2. opciones_intervencion: la tarjeta fija `intervencion` con `direccion`
   distinta de sin_intervencion (cubierto); solo la nombra sin dirección, o
   la tarjeta no la fija pero algún apoyo nombra una intervención, un fármaco
   o una modulación (parcial). El vocabulario distingue "inhibitor" e
   "inhibition" de "inhibitory" (las interneuronas inhibitorias son
   mecanismo) y no cuenta "compuesto" ("grupo compuesto por" no es una
   intervención). Sin tarjeta y sin afirmaciones verificadas, no comprobable.
3. compromiso_diana: apoyos de tipo dato con `nivelMedicion` medida o
   resultado_analisis (ausente cuenta como resultado_analisis, el valor de
   hoy) que nombren la diana de la tarjeta o el biomarcador de la
   comprobación, por nombre o por identificador canónico de
   `rosa/ontologias.py` (sin contar enfermedades ni tejidos, que casarían con
   todo). Un análisis in silico con `auditoria.veredicto` valido cuenta como
   cubierto; no válido o sobre datos sintéticos (`runtime` local_sintetico)
   no cuenta y se dice; completado sin auditar es no comprobable. Sin diana
   ni biomarcador ni ejecuciones, no comprobable.
4. efecto_funcional: apoyos que hablen de un desenlace funcional o clínico
   (cognición, memoria, demencia, síntomas, función celular): de tipo dato,
   cubierto; de literatura o interpretación, parcial. Antes de buscar se
   quitan las etiquetas de población ("cognitively unimpaired", "deterioro
   cognitivo leve"), los nombres de cohorte con "memory" y los usos de
   "functional" que no son desenlace (conectividad, RM, anotación): describir
   a quién se midió no es medir un desenlace. Un resultado de
   laboratorio con clasificación apoyo_reproducido cubre; negativo
   interpretable, inconcluso, corrección de contexto o toxicidad son parcial
   (se midió, no se reprodujo); fallo técnico o datos recibidos sin evaluar,
   no comprobable.
5. selectividad_toxicidad: un resultado de laboratorio con
   `dimensiones.toxicidad` o clasificación toxicidad_inviabilidad cubre el
   paso (queda evaluado y cierra la vía en este contexto); afirmaciones
   verificadas de tipo dato sobre toxicidad, seguridad, efectos adversos o
   selectividad, cubierto; `tarjeta.riesgos` no vacía, dimensiones evaluadas
   sin toxicidad o menciones de literatura, parcial (declarado no es medido).
   La excitotoxicidad y la "selective vulnerability" son mecanismo, no
   toxicidad ni selectividad de una intervención, y no cuentan.
6. exposicion: afirmaciones verificadas o fuentes que nombren plasma, suero,
   sangre o LCR (por `rosa/metodos.py` muestras_en_texto, que ya sabe que
   "blood-brain barrier" no es una muestra de sangre), la barrera
   hematoencefálica, dosis o farmacocinética. Dato medido, cubierto; solo
   menciones o títulos de fuentes, parcial.
7. replicacion_independiente: `metodos.cohortes_distintas` (alias, nombres
   largos y registros NCT resuelven a la misma cohorte del catálogo) sobre
   las fuentes que aportan apoyo según `certeza._Vista.fuentes_que_cuentan`
   (con un apoyo emparejado, o sin ninguna afirmación emparejable). Dos o
   más, cubierto; una, parcial; afirmaciones todas sin verificar, no
   comprobable (las cohortes esperan); fuentes con cohorte que solo
   contradicen o socavan, vacío; fuentes sin cohorte identificada, no
   comprobable (no se puede afirmar que sean independientes ni que no lo
   sean); sin fuentes, vacío.
8. evidencia_poblacion: apoyos con n numérico >= 50 (`certeza._entero`, que
   lee "120", "n = 120" o 120) cuya fuente emparejada tenga `tipoEstudio`
   cohorte, caso_control, transversal o ensayo_aleatorizado (estudios
   primarios en personas). Con diseño humano pero sin n suficiente, parcial;
   fuentes sin tipo de estudio (o "otro"), no comprobable; diseños
   preclínicos o in vitro, vacío. Las revisiones sistemáticas y los registros
   no cuentan aquí: la población se cuenta por estudio primario.

Coherencia: el paso declarado en la tarjeta no puede ir por delante del
primer paso vacío. Un paso parcial no rompe la coherencia (hay algo), y uno
no comprobable tampoco (no se acusa de lo que no se pudo mirar). Una tarjeta
antigua sin `pasoRuta` declara "mecanismo", el valor de hoy; sin tarjeta no
hay paso declarado y la coherencia es cierta por vacuidad.

`mapa_ruta` agrupa las hipótesis vivas de una investigación por diana o
proceso canónico (tarjeta.diana, si no el biomarcador de la comprobación, si
no la primera entidad canónica de `h.entidades` que no sea una enfermedad) y
dice, por paso, cuántas hipótesis lo cubren y la certeza GRADE máxima entre
ellas; los huecos son los pasos que ninguna hipótesis cubre ni parcialmente y
ningún hecho del modelo de mundo sobre esa diana toca (un hecho toca el
mecanismo siempre, y las opciones de intervención, el efecto funcional, la
selectividad y la exposición si su enunciado las nombra; los otros tres pasos
piden datos estructurados que un hecho no lleva).

Nada de aquí llama a un modelo ni a la red. Un registro antiguo sin las
claves nuevas se trata como el valor de hoy; una entrada que no es un
diccionario se trata como vacía, nunca rompe.
"""

from __future__ import annotations

import re
from typing import Any

from rosa import certeza as C
from rosa import metodos as METODOS
from rosa import ontologias as ONTO
from rosa.estado.plantilla import PASOS_RUTA

ESTADOS_PASO = ("cubierto", "parcial", "vacio", "no_comprobable")
TIPOS_EVIDENCIA = ("afirmacion", "ejecucion", "laboratorio", "hecho", "fuente")

# Mismas etiquetas que `frontend/src/lib/etiquetas.ts` (PASO_RUTA), para que el
# texto del backend y el de la pantalla digan lo mismo.
ETIQUETAS_PASO: dict[str, str] = {
    "mecanismo": "Mecanismo",
    "opciones_intervencion": "Opciones de intervención",
    "compromiso_diana": "Compromiso de diana",
    "efecto_funcional": "Efecto funcional",
    "selectividad_toxicidad": "Selectividad y toxicidad",
    "exposicion": "Entrega y exposición",
    "replicacion_independiente": "Replicación independiente",
    "evidencia_poblacion": "Evidencia en la población",
}

# Una frase por paso, para quien lee la ruta por primera vez.
DEFINICIONES_PASO: dict[str, str] = {
    "mecanismo": "qué proceso biológico explica el efecto y con qué evidencia",
    "opciones_intervencion": "con qué se podría actuar sobre la diana (fármaco, anticuerpo, modulación) y en qué dirección",
    "compromiso_diana": "que la intervención o la medida llega a la diana y la cambia de forma medible",
    "efecto_funcional": "que cambiar la diana cambia algo que importa: cognición, síntomas, función celular",
    "selectividad_toxicidad": "que el efecto es sobre la diana y no sobre otras, y qué daño produce",
    "exposicion": "que el fármaco o el marcador llega a donde tiene que llegar (sangre, LCR, cerebro), con qué dosis y cuánto tiempo",
    "replicacion_independiente": "que el efecto se ha visto en al menos dos cohortes distintas (grupos de personas estudiados por separado)",
    "evidencia_poblacion": "que hay estudios primarios en personas (cohortes, casos y controles, transversales o ensayos) con al menos 50 participantes",
}

ETIQUETAS_ESTADO: dict[str, str] = {"cubierto": "cubierto", "parcial": "parcial", "vacio": "vacío", "no_comprobable": "no comprobable"}
ETIQUETAS_EVIDENCIA: dict[str, str] = {"afirmacion": "afirmación", "ejecucion": "análisis in silico", "laboratorio": "laboratorio", "hecho": "hecho", "fuente": "fuente"}

# Diseños que cuentan como estudio primario en población humana.
DISENOS_HUMANOS = ("cohorte", "caso_control", "transversal", "ensayo_aleatorizado")
N_MINIMO_POBLACION = 50
# Matrices del catálogo de métodos que hablan de exposición.
MUESTRAS_EXPOSICION = ("muestra:plasma", "muestra:suero", "muestra:sangre", "muestra:lcr")
# Cuántas piezas de evidencia viajan por paso; el motivo lleva el total.
MAX_EVIDENCIA = 10
# Entidades canónicas que no sirven para reconocer una diana en un texto:
# una enfermedad o un tejido casan con casi todo el corpus.
_TIPOS_NO_DIANA = ("enfermedad", "tejido")

# Vocabulario por regla, en castellano e inglés, tolerante a texto sin tildes
# (como sale de algunos PDF).
_INTERVENCION = re.compile(
    r"intervenci[oó]n|f[aá]rmaco|farmacol[oó]gic|pharmacolog|\bdrugs?\b|tratamiento|\btreat(?:ment|ed|ing)?\b|terapia|terap[eé]utic|\btherap|modula|inhibidor|\binhibitors?\b|inhibici[oó]n|\binhibition\b|\binhibit(?:s|ed|ing)?\b|agonist|antagonist|anticuerpo|antibod|bloqueo de|bloquea|blockade|blocker|knock-?(?:out|down|in)|silenciamiento|silencing|\bsi ?RNA\b|\bshRNA\b|\bCRISPR\b|sobreexpres|overexpress|activador|activator|mol[eé]cula peque|small molecule|inmunoterap|immunotherap|vacuna|vaccine|suplement|\bdieta\b|\bdiet\b|ejercicio|exercise|lecanemab|donanemab|aducanumab|donepezil|memantin",
    re.I,
)
_FUNCIONAL = re.compile(
    r"cognic|cognit|\bMMSE\b|\bMoCA\b|\bCDR\b|ADAS[-\s]?Cog|memoria|\bmemory\b|funcional|functional|demencia|dementia|conversi[oó]n a|conversion to|progression to|progresi[oó]n a\b|progresi[oó]n cl[ií]nica|clinical progression|disease progression|deterioro|\bdecline\b|s[ií]ntoma|symptom|supervivencia|survival|calidad de vida|quality of life|vida diaria|\b[iI]?ADLs?\b|conducta|behavio|neuropsicol|neuropsychol|viabilidad celular|cell viability|plasticidad sin[aá]ptica|synaptic plasticity|\bLTP\b",
    re.I,
)
# Lo que se quita del texto antes de buscar un desenlace funcional: etiquetas de
# población ("cognitively unimpaired", "deterioro cognitivo leve"), nombres de
# cohorte ("Memory and Aging Project", "memory clinic") y usos de "functional"
# que no son un desenlace (conectividad, RM, anotación).
_FUNCIONAL_NO = re.compile(
    r"cognitively[-\s]+(?:unimpaired|normal|healthy|intact|impaired)|cognitivamente[-\s]+(?:sanos?|normales?|intactos?|preservados?)|deterioro cognitivo leve|mild cognitive impairment|subjective cognitive decline|queja subjetiva de memoria|memory (?:and ag(?:e)?ing|clinic)|cl[ií]nica de (?:la )?memoria|functional (?:connectivity|mri|imaging|annotation|enrichment|genomics?|assays?)|conectividad funcional|resonancia (?:magn[eé]tica )?funcional",
    re.I,
)
_SEGURIDAD = re.compile(
    r"t[oó]xic|seguridad|\bsafety\b|advers[oa]s?\b|adverse|efectos secundarios|side[-\s]effects?|\bARIA\b|selectivi(?:dad|ty)|off[-\s]?target|tolerab|hepatot|cardiot|nefrot|nephrot|citot[oó]x|cytotox|\bletal|\blethal|hemorrag|hemorrhag|microhemorr|microbleed|\bedema\b",
    re.I,
)
# "excitotoxicity" es un mecanismo de daño neuronal, no la toxicidad de una intervención.
_SEGURIDAD_NO = re.compile(r"excitotoxic\w*|excitot[oó]xic\w*", re.I)
_EXPOSICION = re.compile(
    r"barrera hematoencef|blood[-‐–\s]?brain[-‐–\s]?barrier|\bBBB\b|\bdosis\b|\bdoses?\b|dosing|dosage|farmacocin|pharmacokin|\bPK\b|biodisponib|bioavailab|penetraci[oó]n cerebral|brain penetra|\bCNS penetra|vida media|half[-\s]?life|CSF[/:\s]?to[-\s]?plasma|CSF[/:]plasma|plasma[/:]CSF|\bC ?max\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Utilidades: nada de aquí rompe con un registro raro
# ---------------------------------------------------------------------------


def _d(x: Any) -> dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _l(x: Any) -> list[Any]:
    return list(x) if isinstance(x, (list, tuple)) else []


def _s(x: Any) -> str:
    if x is None or isinstance(x, bool):
        return ""
    return x.strip() if isinstance(x, str) else str(x).strip()


def _norm(t: Any) -> str:
    return re.sub(r"\s+", " ", _s(t)).lower()


def _n(k: int, singular: str, plural: str) -> str:
    return f"{k} {singular if k == 1 else plural}"


def _enumerar(xs: list[str]) -> str:
    xs = [x for x in xs if x]
    if not xs:
        return ""
    if len(xs) == 1:
        return xs[0]
    return ", ".join(xs[:-1]) + " y " + xs[-1]


def _texto_af(a: dict[str, Any]) -> str:
    return " ".join(_s(a.get(k)) for k in ("texto", "fragmento") if _s(a.get(k)))


def _id_af(a: dict[str, Any], i: int) -> str:
    return _s(a.get("afirmacionId")) or _s(a.get("id")) or f"afirmacion-{i + 1}"


def _ev(tipo: str, id_: Any, texto: Any) -> dict[str, str]:
    return {"tipo": tipo, "id": _s(id_), "texto": _s(texto)[:200]}


def _recortar(evidencia: list[dict[str, str]]) -> list[dict[str, str]]:
    """Hasta MAX_EVIDENCIA piezas repartidas por turnos entre los tipos que
    haya (afirmación, hecho, ejecución, laboratorio, fuente), en el orden en
    que llegaron: con 18 afirmaciones y 15 hechos se ven los dos, no solo las
    diez primeras afirmaciones."""
    if len(evidencia) <= MAX_EVIDENCIA:
        return list(evidencia)
    colas: dict[str, list[dict[str, str]]] = {}
    for x in evidencia:
        colas.setdefault(x.get("tipo", ""), []).append(x)
    salida: list[dict[str, str]] = []
    while len(salida) < MAX_EVIDENCIA and any(colas.values()):
        for cola in colas.values():
            if cola and len(salida) < MAX_EVIDENCIA:
                salida.append(cola.pop(0))
    return salida


def _paso(paso: str, estado: str, evidencia: list[dict[str, str]], motivo: str) -> dict[str, Any]:
    total = len(evidencia)
    if total > MAX_EVIDENCIA:
        motivo = f"{motivo} (se muestran {MAX_EVIDENCIA} de {total} piezas de evidencia)"
    return {"paso": paso, "estado": estado, "evidencia": _recortar(evidencia), "motivo": motivo}


def _patron_nombre(nombre: str) -> re.Pattern[str]:
    """El nombre como palabra entera dentro de un texto en minúsculas: "tau"
    no casa con "restaurant" y "A4" no casa con "A40"."""
    return re.compile(r"(?<![a-z0-9])" + re.escape(_norm(nombre)) + r"(?![a-z0-9])")


def _mismo_nombre(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    corto, largo = (na, nb) if len(na) <= len(nb) else (nb, na)
    return len(corto) >= 3 and bool(_patron_nombre(corto).search(largo))


def _ids_curados(texto: str) -> set[str]:
    return {x["id"] for x in ONTO.anotar_curadas(texto) if x.get("tipo") not in _TIPOS_NO_DIANA}


def _texto_ejecucion(x: dict[str, Any]) -> str:
    resultados = _d(x.get("resultados"))
    cifras = "; ".join(f"{k}={v}" for k, v in list(resultados.items())[:3])
    interp = _d(x.get("interpretacion"))
    return f"análisis in silico {_s(x.get('id'))}: " + (cifras or _s(interp.get("resumen")) or "sin cifras")


class _Registro:
    """Una sola lectura de la hipótesis y del estado: afirmaciones con su
    índice, cuáles apoyan y cuáles están verificadas, con qué fuente empareja
    cada una, tarjeta, experimento y resultado del laboratorio. Reutiliza
    `certeza._Vista`, que es quien decide qué cuenta como apoyo."""

    def __init__(self, e: Any, h: Any, indice_hechos: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.e = _d(e)
        self.h = _d(h)
        # afirmacionId -> hechos que la enlazan; `mapa_ruta` lo construye una vez para todas las hipótesis.
        self.indice_hechos = indice_hechos if indice_hechos is not None else _indice_hechos(self.e)
        self.vista = C._Vista(self.h)
        self.afs: list[dict[str, Any]] = self.vista.afs
        self.apoyos: list[int] = list(self.vista.apoyos)
        self.verificadas: list[int] = [i for i, a in enumerate(self.afs) if a.get("veredicto") in C.VEREDICTOS_QUE_CUENTAN and not a.get("sintetico")]
        self.sin_verificar: list[int] = [i for i, a in enumerate(self.afs) if _norm(a.get("veredicto")) in ("", "sin_verificar")]
        self.fuentes: list[dict[str, Any]] = self.vista.fuentes
        tarjeta = self.h.get("tarjeta")
        self.tarjeta: dict[str, Any] | None = tarjeta if isinstance(tarjeta, dict) else None
        self.experimento = _d(self.h.get("experimento"))
        self.resultado = _d(self.experimento.get("resultado"))
        self.id_laboratorio = _s(self.experimento.get("prerregistroArtefactoId")) or _s(self.h.get("id")) or "laboratorio"

    def fuente(self, i: int) -> dict[str, Any] | None:
        return self.vista.fuente_principal(i)

    def ev_af(self, i: int) -> dict[str, str]:
        a = self.afs[i]
        return _ev("afirmacion", _id_af(a, i), a.get("texto"))

    def es_dato(self, i: int) -> bool:
        return _norm(self.afs[i].get("tipo")) == "dato"

    def pendiente(self, contexto: str) -> str | None:
        """El motivo de 'no comprobable' cuando hay afirmaciones sin verificar y
        ninguna verificada; None si no es el caso."""
        if self.sin_verificar and not self.verificadas:
            return f"{_n(len(self.sin_verificar), 'afirmación', 'afirmaciones')} sin verificar todavía y ninguna verificada: no se puede juzgar {contexto}"
        return None

    def fuentes_unicas(self) -> list[dict[str, Any]]:
        vistos: set[str] = set()
        salida = []
        for j, f in enumerate(self.fuentes):
            clave = _s(f.get("id")) or _s(f.get("referencia")) or f"pos-{j}"
            if clave in vistos:
                continue
            vistos.add(clave)
            salida.append(f)
        return salida


def _hechos_vivos(e: dict[str, Any]) -> list[dict[str, Any]]:
    """Los hechos del modelo de mundo que cuentan: tipo hecho (o sin tipo, en
    registros antiguos), no descartados ni sustituidos, una vez por id (un
    hecho heredado con sufijo '-inv-' es otro id y cuenta aparte)."""
    vistos: set[str] = set()
    salida = []
    for j, x in enumerate(_l(e.get("hechos"))):
        if not isinstance(x, dict):
            continue
        # Un hecho sin id (registro roto) cuenta por su posición: dos sin id no son el mismo.
        xid = _s(x.get("id")) or f"pos-{j}"
        if xid in vistos:
            continue
        vistos.add(xid)
        if _norm(x.get("estado")) == "descartado" or x.get("sustituidoPor"):
            continue
        if _norm(x.get("tipo")) not in ("", "hecho"):
            continue
        salida.append(x)
    return salida


def _indice_hechos(e: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """afirmacionId -> hechos vivos que la enlazan. Se construye una vez por
    estado para que el coste crezca con el tamaño del registro, no con
    hipótesis por hechos."""
    indice: dict[str, list[dict[str, Any]]] = {}
    for x in _hechos_vivos(e):
        for i in _l(x.get("afirmacionIds")):
            clave = _s(i)
            if clave:
                indice.setdefault(clave, []).append(x)
    return indice


def _hechos_de(reg: _Registro) -> list[dict[str, Any]]:
    """Los hechos del modelo de mundo de la misma investigación enlazados a la
    hipótesis por `afirmacionIds`, cada uno una vez. Solo enlazan los ids
    reales de la afirmación (`afirmacionId` o `id`): una afirmación antigua sin
    id no se empareja con nada."""
    vistos: set[str] = set()
    salida = []
    for a in reg.afs:
        clave = _s(a.get("afirmacionId")) or _s(a.get("id"))
        if not clave:
            continue
        for x in reg.indice_hechos.get(clave, []):
            xid = _s(x.get("id")) or f"obj-{id(x)}"
            if xid in vistos or x.get("investigacionId") != reg.h.get("investigacionId"):
                continue
            vistos.add(xid)
            salida.append(x)
    return salida


def _ejecuciones_de(reg: _Registro) -> list[dict[str, Any]]:
    """Las ejecuciones in silico de la hipótesis: por `hipotesisId` o porque su
    id está en `h.ejecuciones`; una vez por id."""
    ids = {_s(i) for i in _l(reg.h.get("ejecuciones"))}
    ids.discard("")
    hid = reg.h.get("id")
    vistos: set[str] = set()
    salida = []
    for j, x in enumerate(_l(reg.e.get("ejecuciones"))):
        if not isinstance(x, dict):
            continue
        xid = _s(x.get("id"))
        clave = xid or f"pos-{j}"
        if clave in vistos:
            continue
        vistos.add(clave)
        if (hid is not None and x.get("hipotesisId") == hid) or (xid and xid in ids):
            salida.append(x)
    return salida


def _nombres_diana(h: dict[str, Any]) -> list[str]:
    t = _d(h.get("tarjeta"))
    c = _d(h.get("comprobacion"))
    nombres: list[str] = []
    for x in (t.get("diana"), c.get("biomarcador")):
        s = _s(x)
        if s and _norm(s) not in {_norm(n) for n in nombres}:
            nombres.append(s)
    return nombres


def _ids_diana(h: dict[str, Any], nombres: list[str]) -> set[str]:
    ids: set[str] = set()
    for n in nombres:
        ids |= _ids_curados(n)
    for ent in _l(h.get("entidades")):
        if not isinstance(ent, dict) or not _s(ent.get("id")) or ent.get("tipo") in _TIPOS_NO_DIANA:
            continue
        etiquetas = [_s(ent.get("etiqueta"))] + [_s(a) for a in _l(ent.get("alias"))]
        if any(_mismo_nombre(n, x) for n in nombres for x in etiquetas if x):
            ids.add(_s(ent["id"]))
    return ids


def _nombra_diana(texto: str, nombres: list[str], ids: set[str]) -> bool:
    t = _norm(texto)
    if not t:
        return False
    if any(len(_norm(n)) >= 2 and _patron_nombre(n).search(t) for n in nombres):
        return True
    return bool(ids and ids & _ids_curados(texto))


def _es_funcional(texto: str) -> bool:
    """El texto habla de un desenlace funcional o clínico, quitadas antes las
    etiquetas de población y los usos de "functional" que no son desenlace."""
    return bool(_FUNCIONAL.search(_FUNCIONAL_NO.sub(" ", texto or "")))


def _es_seguridad(texto: str) -> bool:
    """El texto habla de toxicidad, seguridad, efectos adversos o selectividad
    (sin contar la excitotoxicidad, que es mecanismo)."""
    return bool(_SEGURIDAD.search(_SEGURIDAD_NO.sub(" ", texto or "")))


def _exposicion_en(texto: str) -> list[str]:
    """Las señales de exposición de un texto: matrices del catálogo de métodos
    (plasma, suero, sangre, LCR) y términos de dosis o farmacocinética."""
    hallado: list[str] = []
    for m in METODOS.muestras_en_texto(texto):
        etiqueta = _s(m.get("etiqueta")) or _s(m.get("id"))
        if _s(m.get("id")) in MUESTRAS_EXPOSICION and etiqueta not in hallado:
            hallado.append(etiqueta)
    m2 = _EXPOSICION.search(texto or "")
    if m2:
        termino = m2.group(0).lower()
        if termino not in hallado:
            hallado.append(termino)
    return hallado


# ---------------------------------------------------------------------------
# Los ocho pasos
# ---------------------------------------------------------------------------


def _paso_mecanismo(reg: _Registro) -> dict[str, Any]:
    paso = "mecanismo"
    hechos = _hechos_de(reg)
    grafo = _d(reg.h.get("grafoCausal"))
    ident = _norm(grafo.get("identificacion"))
    refuerza = ident in ("identificable", "acotado")
    if refuerza:
        nota_grafo = f"; el grafo causal está {ident} y refuerza el mecanismo"
    elif ident == "sin_resolver":
        nota_grafo = "; el grafo causal está sin resolver"
    else:
        nota_grafo = "; sin grafo causal calculado"
    ev = [reg.ev_af(i) for i in reg.apoyos] + [_ev("hecho", x.get("id"), x.get("enunciado")) for x in hechos]
    if not ev:
        pend = reg.pendiente("el mecanismo")
        if pend:
            return _paso(paso, "no_comprobable", [], pend + nota_grafo)
        return _paso(paso, "vacio", [], "ninguna afirmación sostenida o parcial apoya la hipótesis y ningún hecho del modelo de mundo está enlazado a ella" + nota_grafo)
    detalle = _n(len(reg.apoyos), "afirmación que apoya", "afirmaciones que apoyan") + (f" y {_n(len(hechos), 'hecho del modelo de mundo enlazado', 'hechos del modelo de mundo enlazados')}" if hechos else "")
    if len(ev) == 1 and not refuerza:
        return _paso(paso, "parcial", ev, f"un solo apoyo ({detalle}){nota_grafo}: hace falta otro apoyo o un grafo causal identificable o acotado")
    return _paso(paso, "cubierto", ev, detalle + nota_grafo)


def _paso_opciones(reg: _Registro) -> dict[str, Any]:
    paso = "opciones_intervencion"
    t = reg.tarjeta
    intervencion = _s(t.get("intervencion")) if t else ""
    direccion = _norm(t.get("direccion")) if t else ""
    con_direccion = direccion not in ("", "sin_intervencion")
    nombran = [i for i in reg.apoyos if _INTERVENCION.search(_texto_af(reg.afs[i]))]
    ev = [reg.ev_af(i) for i in nombran]
    frase_nombran = f"{_n(len(nombran), 'afirmación que apoya nombra', 'afirmaciones que apoyan nombran')} una intervención, un fármaco o una modulación"
    if t is not None and intervencion and con_direccion:
        return _paso(paso, "cubierto", ev, f"la tarjeta fija la intervención «{intervencion}» con dirección '{direccion}'" + (f"; {frase_nombran}" if nombran else ""))
    if t is not None and intervencion:
        return _paso(paso, "parcial", ev, f"la tarjeta nombra la intervención «{intervencion}» pero la dirección es 'sin_intervencion': falta decir si aumenta, disminuye o modula la diana" + (f"; {frase_nombran}" if nombran else ""))
    sin_tarjeta = "sin tarjeta" if t is None else ("la tarjeta no fija intervención" + (f" aunque declara dirección '{direccion}'" if con_direccion else ""))
    if nombran:
        return _paso(paso, "parcial", ev, f"{sin_tarjeta}, pero {frase_nombran}: hay opciones en la literatura sin recoger en el contrato")
    if t is None and not reg.verificadas:
        return _paso(paso, "no_comprobable", [], reg.pendiente("las opciones de intervención") or "sin tarjeta y sin afirmaciones verificadas: no hay con qué juzgar las opciones de intervención")
    return _paso(paso, "vacio", [], f"{sin_tarjeta} y ninguna afirmación que apoya nombra una intervención, un fármaco o una modulación")


def _paso_compromiso(reg: _Registro) -> dict[str, Any]:
    paso = "compromiso_diana"
    nombres = _nombres_diana(reg.h)
    ids = _ids_diana(reg.h, nombres)
    etiqueta_diana = _enumerar([f"«{n}»" for n in nombres]) or "sin declarar"
    validas: list[dict[str, Any]] = []
    no_validas: list[dict[str, Any]] = []
    sinteticas: list[dict[str, Any]] = []
    sin_auditar: list[dict[str, Any]] = []
    otras: list[dict[str, Any]] = []
    for x in _ejecuciones_de(reg):
        auditoria = _d(x.get("auditoria"))
        veredicto = _norm(auditoria.get("veredicto"))
        if _norm(x.get("runtime")) == "local_sintetico":
            sinteticas.append(x)
        elif veredicto == "valido":
            validas.append(x)
        elif veredicto == "no_valido":
            no_validas.append(x)
        elif not auditoria and _norm(x.get("estado")) == "completado":
            sin_auditar.append(x)
        else:
            otras.append(x)
    datos = [i for i in reg.apoyos if reg.es_dato(i) and (_norm(reg.afs[i].get("nivelMedicion")) or "resultado_analisis") in ("medida", "resultado_analisis")]
    medidas = [i for i in datos if _nombra_diana(_texto_af(reg.afs[i]), nombres, ids)]
    notas: list[str] = []
    if no_validas:
        notas.append(f"{_n(len(no_validas), 'análisis con auditoría no válida', 'análisis con auditoría no válida')} (no cuenta)")
    if sinteticas:
        notas.append(f"{_n(len(sinteticas), 'análisis sobre datos sintéticos', 'análisis sobre datos sintéticos')} (no cuenta)")
    if sin_auditar:
        notas.append(f"{_n(len(sin_auditar), 'análisis completado sin auditar', 'análisis completados sin auditar')} todavía")
    if otras:
        notas.append(f"{_n(len(otras), 'análisis en curso, con error técnico o no evaluable', 'análisis en curso, con error técnico o no evaluables')} (no cuenta)")
    sufijo = ("; " + "; ".join(notas)) if notas else ""
    if not nombres and not (validas or no_validas or sinteticas or sin_auditar or otras):
        return _paso(paso, "no_comprobable", [], "la tarjeta no fija la diana y la comprobación no fija el biomarcador, y no hay análisis in silico: no hay contra qué comprobar el compromiso de diana")
    ev = [reg.ev_af(i) for i in medidas] + [_ev("ejecucion", x.get("id"), _texto_ejecucion(x)) for x in validas]
    if medidas or validas:
        partes = []
        if medidas:
            partes.append(f"{_n(len(medidas), 'dato medido nombra', 'datos medidos nombran')} la diana o el biomarcador ({etiqueta_diana})")
        if validas:
            partes.append(f"{_n(len(validas), 'análisis in silico', 'análisis in silico')} con auditoría válida")
        return _paso(paso, "cubierto", ev, "; ".join(partes) + sufijo)
    if datos or no_validas or sinteticas:
        partes = []
        if datos:
            partes.append(f"{_n(len(datos), 'dato medido', 'datos medidos')} pero ninguno nombra la diana ni el biomarcador ({etiqueta_diana})")
        return _paso(paso, "parcial", [reg.ev_af(i) for i in datos], "; ".join(partes) + sufijo if partes else sufijo.lstrip("; "))
    if sin_auditar or otras:
        return _paso(paso, "no_comprobable", [], "ningún dato medido nombra la diana; " + "; ".join(notas))
    pend = reg.pendiente("el compromiso de diana")
    if pend:
        return _paso(paso, "no_comprobable", [], pend)
    return _paso(paso, "vacio", [], f"ningún dato medido nombra la diana o el biomarcador ({etiqueta_diana}) y no hay análisis in silico")


def _paso_efecto(reg: _Registro) -> dict[str, Any]:
    paso = "efecto_funcional"
    r = reg.resultado
    clasificacion = _norm(r.get("clasificacion"))
    funcionales = [i for i in reg.apoyos if _es_funcional(_texto_af(reg.afs[i]))]
    con_dato = [i for i in funcionales if reg.es_dato(i)]
    sin_dato = [i for i in funcionales if i not in con_dato]
    ev_lab = [_ev("laboratorio", reg.id_laboratorio, r.get("resultado") or clasificacion.replace("_", " "))] if clasificacion else []
    ev = ev_lab + [reg.ev_af(i) for i in con_dato] + [reg.ev_af(i) for i in sin_dato]
    frase_sin_dato = f"{_n(len(sin_dato), 'afirmación de literatura o interpretación menciona', 'afirmaciones de literatura o interpretación mencionan')} un desenlace funcional sin dato medido"
    if clasificacion == "apoyo_reproducido" or con_dato:
        partes = []
        if clasificacion == "apoyo_reproducido":
            partes.append("el laboratorio reprodujo el efecto predicho (apoyo reproducido contra el prerregistro)")
        if con_dato:
            partes.append(f"{_n(len(con_dato), 'dato medido', 'datos medidos')} sobre un desenlace funcional o clínico (cognición, síntomas, función celular)")
        if sin_dato:
            partes.append(frase_sin_dato)
        return _paso(paso, "cubierto", ev, "; ".join(partes))
    parciales = {
        "negativo_interpretable": "el laboratorio midió el efecto y devolvió un negativo interpretable: el efecto funcional no se reprodujo",
        "inconcluso": "el laboratorio devolvió un resultado inconcluso: sin potencia para decir si hay efecto",
        "correccion_contexto": "el laboratorio devolvió una corrección de contexto: el efecto aplica a otra célula, etapa o población",
        "toxicidad_inviabilidad": "el laboratorio devolvió toxicidad o inviabilidad: el efecto funcional no se pudo medir en este contexto",
    }
    if clasificacion in parciales or sin_dato:
        partes = [parciales[clasificacion]] if clasificacion in parciales else []
        if sin_dato:
            partes.append(frase_sin_dato)
        return _paso(paso, "parcial", ev, "; ".join(partes))
    if clasificacion == "fallo_tecnico":
        return _paso(paso, "no_comprobable", ev_lab, "el laboratorio devolvió un fallo técnico: el experimento no probó la hipótesis y no dice nada del efecto funcional")
    if _norm(reg.experimento.get("estado")) == "datos_recibidos" and not r:
        return _paso(paso, "no_comprobable", [], "datos del laboratorio recibidos y sin evaluar todavía contra el prerregistro")
    pend = reg.pendiente("el efecto funcional")
    if pend:
        return _paso(paso, "no_comprobable", [], pend)
    return _paso(paso, "vacio", [], "ninguna afirmación que apoya habla de un desenlace funcional o clínico y no hay resultado de laboratorio")


def _paso_selectividad(reg: _Registro) -> dict[str, Any]:
    paso = "selectividad_toxicidad"
    t = reg.tarjeta
    crudo = t.get("riesgos") if t is not None else None
    # Un registro antiguo puede traer los riesgos como una cadena suelta: cuenta como uno.
    riesgos = [_s(crudo)] if isinstance(crudo, str) and _s(crudo) else [_s(x) for x in _l(crudo) if _s(x)]
    r = reg.resultado
    dimensiones = _d(r.get("dimensiones"))
    clasificacion = _norm(r.get("clasificacion"))
    marca = dimensiones.get("toxicidad")
    toxicidad = marca is True or marca == 1 or _norm(marca) == "true" or clasificacion == "toxicidad_inviabilidad"
    seguridad = [i for i in reg.verificadas if _es_seguridad(_texto_af(reg.afs[i]))]
    con_dato = [i for i in seguridad if reg.es_dato(i)]
    sin_dato = [i for i in seguridad if i not in con_dato]
    frase_riesgos = f"la tarjeta declara {_n(len(riesgos), 'riesgo', 'riesgos')} ({'; '.join(riesgos)[:160]}): declarado, no medido" if riesgos else ""
    frase_sin_dato = f"{_n(len(sin_dato), 'afirmación verificada menciona', 'afirmaciones verificadas mencionan')} toxicidad, seguridad o selectividad sin dato medido"
    ev = ([_ev("laboratorio", reg.id_laboratorio, r.get("resultado") or "toxicidad registrada por el laboratorio")] if toxicidad else []) + [reg.ev_af(i) for i in con_dato] + [reg.ev_af(i) for i in sin_dato]
    if toxicidad:
        partes = ["el laboratorio registró toxicidad (dimensión 'toxicidad' del resultado): el paso queda evaluado y la vía de intervención se cierra en este contexto"]
        if con_dato:
            partes.append(f"{_n(len(con_dato), 'dato medido', 'datos medidos')} sobre toxicidad, seguridad o selectividad")
        if frase_riesgos:
            partes.append(frase_riesgos)
        return _paso(paso, "cubierto", ev, "; ".join(partes))
    if con_dato:
        partes = [f"{_n(len(con_dato), 'dato medido', 'datos medidos')} sobre toxicidad, seguridad, efectos adversos o selectividad"]
        if sin_dato:
            partes.append(frase_sin_dato)
        if frase_riesgos:
            partes.append(frase_riesgos)
        return _paso(paso, "cubierto", ev, "; ".join(partes))
    if dimensiones or sin_dato or riesgos:
        partes = []
        if dimensiones:
            partes.append("el juez evaluó las dimensiones del resultado de laboratorio y no marcó toxicidad (no sustituye a un ensayo de selectividad)")
        if sin_dato:
            partes.append(frase_sin_dato)
        if frase_riesgos:
            partes.append(frase_riesgos)
        return _paso(paso, "parcial", ev, "; ".join(partes))
    if t is None and not reg.verificadas and not r:
        return _paso(paso, "no_comprobable", [], reg.pendiente("la selectividad y la toxicidad") or "sin tarjeta, sin resultado de laboratorio y sin afirmaciones verificadas: no hay con qué juzgar la selectividad y la toxicidad")
    pend = reg.pendiente("la selectividad y la toxicidad")
    if pend:
        return _paso(paso, "no_comprobable", [], pend)
    return _paso(paso, "vacio", [], ("la tarjeta no declara riesgos" if t is not None else "sin tarjeta") + ", ninguna afirmación verificada habla de toxicidad, seguridad o selectividad y no hay resultado de laboratorio")


def _paso_exposicion(reg: _Registro) -> dict[str, Any]:
    paso = "exposicion"
    senales_af: dict[int, list[str]] = {}
    for i in reg.verificadas:
        s = _exposicion_en(_texto_af(reg.afs[i]))
        if s:
            senales_af[i] = s
    con_dato = [i for i in senales_af if reg.es_dato(i)]
    sin_dato = [i for i in senales_af if i not in con_dato]
    fuentes_exp: list[tuple[dict[str, Any], list[str]]] = []
    for f in reg.fuentes_unicas():
        s = _exposicion_en(" ".join(_s(f.get(k)) for k in ("titulo", "fragmento", "referencia") if _s(f.get(k))))
        if s:
            fuentes_exp.append((f, s))
    senales: list[str] = []
    for lista in list(senales_af.values()) + [s for _, s in fuentes_exp]:
        for x in lista:
            if x not in senales:
                senales.append(x)
    ev = [reg.ev_af(i) for i in con_dato] + [reg.ev_af(i) for i in sin_dato] + [_ev("fuente", f.get("id"), f"{_s(f.get('referencia')) or _s(f.get('titulo')) or 'fuente'}: {', '.join(s)}") for f, s in fuentes_exp]
    if con_dato:
        return _paso(paso, "cubierto", ev, f"{_n(len(con_dato), 'dato medido', 'datos medidos')} en {_enumerar(senales)}: la evidencia mide en la matriz o con la dosis que la ruta pide" + (f"; {_n(len(sin_dato), 'mención', 'menciones')} más sin dato" if sin_dato else ""))
    if senales_af or fuentes_exp:
        partes = []
        if sin_dato:
            partes.append(f"{_n(len(sin_dato), 'afirmación verificada nombra', 'afirmaciones verificadas nombran')} {_enumerar(senales)} sin dato medido")
        if fuentes_exp:
            partes.append(f"{_n(len(fuentes_exp), 'fuente lo nombra', 'fuentes lo nombran')} en su título o fragmento")
        return _paso(paso, "parcial", ev, "; ".join(partes))
    if not reg.fuentes and not reg.afs:
        return _paso(paso, "vacio", [], "sin fuentes ni afirmaciones: nada habla de plasma, suero, sangre, LCR, barrera hematoencefálica, dosis ni farmacocinética")
    pend = reg.pendiente("la exposición")
    if pend:
        return _paso(paso, "no_comprobable", [], pend)
    return _paso(paso, "vacio", [], "ninguna afirmación verificada ni fuente nombra plasma, suero, sangre, LCR, barrera hematoencefálica, dosis ni farmacocinética")


def _nombre_cohorte(f: dict[str, Any]) -> str:
    return _s(f.get("cohorte")) or _s(f.get("nct"))


def _paso_replicacion(reg: _Registro) -> dict[str, Any]:
    paso = "replicacion_independiente"
    # Las fuentes que aportan apoyo según certeza (con un apoyo emparejado, o sin
    # ninguna afirmación emparejable); el catálogo de metodos resuelve alias y NCT.
    que_cuentan = reg.vista.fuentes_que_cuentan()
    cohortes = METODOS.cohortes_distintas(que_cuentan)
    sin_cohorte = METODOS.fuentes_sin_cohorte(que_cuentan)
    apoyan = [f for f in que_cuentan if _nombre_cohorte(f)]
    nombradas = [f for f in reg.fuentes_unicas() if _nombre_cohorte(f)]

    def evidencia(fuentes: list[dict[str, Any]]) -> list[dict[str, str]]:
        vistos: set[str] = set()
        salida = []
        for j, f in enumerate(fuentes):
            clave = _s(f.get("id")) or _s(f.get("referencia")) or f"pos-{j}"
            if clave in vistos:
                continue
            vistos.add(clave)
            salida.append(_ev("fuente", f.get("id"), f"{_s(f.get('referencia')) or _s(f.get('titulo')) or 'fuente'}: cohorte {_nombre_cohorte(f)}"))
        return salida

    nota_sin = f"; {_n(sin_cohorte, 'fuente sin cohorte identificada no cuenta', 'fuentes sin cohorte identificada no cuentan')} como independiente" if sin_cohorte else ""
    if len(cohortes) >= 2:
        return _paso(paso, "cubierto", evidencia(apoyan), f"{len(cohortes)} cohortes distintas entre las fuentes que apoyan: {_enumerar(cohortes)}{nota_sin}")
    if len(cohortes) == 1:
        return _paso(paso, "parcial", evidencia(apoyan), f"una sola cohorte identificada ({cohortes[0]}): hace falta al menos una segunda cohorte independiente{nota_sin}")
    pend = reg.pendiente("la replicación")
    if pend and reg.fuentes:
        return _paso(paso, "no_comprobable", evidencia(nombradas), pend + (f"; hay {_n(len(nombradas), 'fuente con cohorte identificada', 'fuentes con cohorte identificada')} ({_enumerar([_nombre_cohorte(f) for f in nombradas][:4])}) a la espera de que se verifiquen sus afirmaciones" if nombradas else ""))
    if nombradas:
        return _paso(paso, "vacio", evidencia(nombradas), f"las fuentes con cohorte identificada ({_enumerar([_nombre_cohorte(f) for f in nombradas][:4])}) no aportan apoyo (sus afirmaciones emparejadas contradicen, socavan, están socavadas o siguen sin verificar): no hay replicación del efecto{nota_sin}")
    if reg.fuentes:
        return _paso(paso, "no_comprobable", [], f"{_n(len(reg.fuentes_unicas()), 'fuente', 'fuentes')} y ninguna con cohorte identificada (campo cohorte o NCT): no se puede afirmar que sean independientes ni que no lo sean")
    return _paso(paso, "vacio", [], "sin fuentes: no hay cohortes que comparar")


def _paso_poblacion(reg: _Registro) -> dict[str, Any]:
    paso = "evidencia_poblacion"
    grandes: list[tuple[int, int, str]] = []
    con_diseno: list[tuple[int, str]] = []
    disenos_vistos: list[str] = []
    sin_fuente = 0
    for i in reg.apoyos:
        f = reg.fuente(i)
        if f is None:
            sin_fuente += 1
            continue
        tipo = _norm(f.get("tipoEstudio"))
        if tipo and tipo != "otro" and tipo not in disenos_vistos:
            disenos_vistos.append(tipo)
        if tipo in DISENOS_HUMANOS:
            con_diseno.append((i, tipo))
            n = C._entero(reg.afs[i].get("n"))
            if n is not None and n >= N_MINIMO_POBLACION:
                grandes.append((i, n, tipo))
    etiqueta = lambda t: C.ETIQUETAS_DISENO.get(t, t)  # noqa: E731
    if grandes:
        ev = [dict(reg.ev_af(i), texto=f"n = {n} ({etiqueta(t)}): {_s(reg.afs[i].get('texto'))}"[:200]) for i, n, t in grandes]
        disenos = sorted({t for _, _, t in grandes}, key=DISENOS_HUMANOS.index)
        return _paso(paso, "cubierto", ev, f"{_n(len(grandes), 'afirmación que apoya', 'afirmaciones que apoyan')} con n >= {N_MINIMO_POBLACION} de estudios primarios en personas ({_enumerar([etiqueta(t) for t in disenos])})")
    if con_diseno:
        ev = [reg.ev_af(i) for i, _ in con_diseno]
        disenos = sorted({t for _, t in con_diseno}, key=DISENOS_HUMANOS.index)
        return _paso(paso, "parcial", ev, f"{_n(len(con_diseno), 'afirmación', 'afirmaciones')} de estudios en personas ({_enumerar([etiqueta(t) for t in disenos])}) pero ninguna con n >= {N_MINIMO_POBLACION} conocido (n desconocido o menor)")
    if reg.apoyos:
        if sin_fuente == len(reg.apoyos):
            return _paso(paso, "no_comprobable", [], f"{_n(len(reg.apoyos), 'apoyo sin fuente emparejada', 'apoyos sin fuente emparejada')} (ni por fuenteId ni por cita): no se puede saber el diseño ni la población de la que vienen")
        if not disenos_vistos:
            return _paso(paso, "no_comprobable", [], f"las fuentes de los {len(reg.apoyos)} apoyos no tienen tipo de estudio clasificado (o es 'otro'): no se puede saber si son estudios en población humana" + (f"; {sin_fuente} sin fuente emparejada" if sin_fuente else ""))
        excluidos = [etiqueta(t) for t in disenos_vistos]
        nota = "; las revisiones sistemáticas y los registros no cuentan aquí: la población se cuenta por estudio primario" if any(t in ("revision_sistematica", "registro") for t in disenos_vistos) else ""
        return _paso(paso, "vacio", [], f"los apoyos vienen de diseños {_enumerar(excluidos)} y ninguno es un estudio primario en población humana (cohorte, casos y controles, transversal o ensayo aleatorizado){nota}" + (f"; {sin_fuente} sin fuente emparejada" if sin_fuente else ""))
    pend = reg.pendiente("la evidencia en la población")
    if pend:
        return _paso(paso, "no_comprobable", [], pend)
    return _paso(paso, "vacio", [], "sin apoyos: no hay evidencia en población que contar")


_REGLAS = {
    "mecanismo": _paso_mecanismo,
    "opciones_intervencion": _paso_opciones,
    "compromiso_diana": _paso_compromiso,
    "efecto_funcional": _paso_efecto,
    "selectividad_toxicidad": _paso_selectividad,
    "exposicion": _paso_exposicion,
    "replicacion_independiente": _paso_replicacion,
    "evidencia_poblacion": _paso_poblacion,
}


# ---------------------------------------------------------------------------
# Evaluación de una hipótesis
# ---------------------------------------------------------------------------


def _coherencia(reg: _Registro, pasos: list[dict[str, Any]]) -> tuple[str | None, bool, str]:
    """(paso declarado, coherente, motivo). El paso declarado no puede ir por
    delante del primer paso vacío."""
    t = reg.tarjeta
    if t is None:
        return None, True, "sin tarjeta: no hay paso declarado que contrastar con lo calculado"
    declarado = _norm(t.get("pasoRuta")) or "mecanismo"
    if declarado not in PASOS_RUTA:
        return declarado, True, f"la tarjeta declara '{declarado}', que no es un paso de la ruta: no se contrasta"
    etiqueta = ETIQUETAS_PASO[declarado]
    vacios = [p["paso"] for p in pasos if p["estado"] == "vacio" and p["paso"] in PASOS_RUTA]
    if not vacios:
        return declarado, True, f"la tarjeta declara «{etiqueta}» y ningún paso está vacío"
    primero = vacios[0]
    if PASOS_RUTA.index(declarado) <= PASOS_RUTA.index(primero):
        return declarado, True, f"la tarjeta declara «{etiqueta}» y el primer paso vacío es «{ETIQUETAS_PASO[primero]}»: el paso declarado no va por delante de la evidencia"
    return declarado, False, f"la tarjeta declara «{etiqueta}» pero «{ETIQUETAS_PASO[primero]}» sigue vacío: el paso declarado va por delante de la evidencia; conviene bajar el paso o traer evidencia para «{ETIQUETAS_PASO[primero]}»"


def _capitalizar(t: str) -> str:
    return t[:1].upper() + t[1:] if t else t


def _resumen_evaluacion(pasos: list[dict[str, Any]], siguiente: str | None, cubiertos: int, motivo_coherencia: str) -> str:
    def etiquetas(estado: str) -> list[str]:
        return [ETIQUETAS_PASO.get(p["paso"], p["paso"]) for p in pasos if p["estado"] == estado]

    partes = [f"{cubiertos} de {len(pasos)} pasos cubiertos" + (f" ({_enumerar(etiquetas('cubierto'))})" if cubiertos else "")]
    parciales = etiquetas("parcial")
    if parciales:
        partes.append(f"{_n(len(parciales), 'parcial', 'parciales')} ({_enumerar(parciales)})")
    no_comprobables = etiquetas("no_comprobable")
    if no_comprobables:
        partes.append(f"sin poder comprobar: {_enumerar(no_comprobables)}")
    partes.append(f"siguiente paso: {ETIQUETAS_PASO.get(siguiente, siguiente)}" if siguiente else "ruta completa: los ocho pasos tienen evidencia")
    return _capitalizar("; ".join(partes)) + ". " + _capitalizar(motivo_coherencia) + "."


def evaluar_ruta(e: Any, h: Any) -> dict[str, Any]:
    """La ruta terapéutica de una hipótesis calculada por regla.

    Devuelve {hipotesisId, pasos, siguiente, cubiertos, declarado, coherente,
    motivoCoherencia, porEstado, resumen}. `pasos` sigue el orden de
    `PASOS_RUTA`; cada uno lleva {paso, estado, evidencia, motivo} con
    evidencia [{tipo, id, texto}] y tipo en `TIPOS_EVIDENCIA`. `siguiente` es
    el primer paso no cubierto (None si los ocho lo están). `declarado` es
    `tarjeta.pasoRuta` (mecanismo si la tarjeta no lo trae; None sin
    tarjeta) y `coherente` dice si no va por delante del primer paso vacío.
    Todo es serializable a JSON y determinista: con el mismo estado sale lo
    mismo."""
    return _evaluar(_Registro(e, h))


def _evaluar(reg: _Registro) -> dict[str, Any]:
    pasos = [_REGLAS[p](reg) for p in PASOS_RUTA]
    siguiente = next((p["paso"] for p in pasos if p["estado"] != "cubierto"), None)
    cubiertos = sum(1 for p in pasos if p["estado"] == "cubierto")
    declarado, coherente, motivo_coherencia = _coherencia(reg, pasos)
    por_estado = {estado: sum(1 for p in pasos if p["estado"] == estado) for estado in ESTADOS_PASO}
    return {
        "hipotesisId": reg.h.get("id"),
        "pasos": pasos,
        "siguiente": siguiente,
        "cubiertos": cubiertos,
        "declarado": declarado,
        "coherente": coherente,
        "motivoCoherencia": motivo_coherencia,
        "porEstado": por_estado,
        "resumen": _resumen_evaluacion(pasos, siguiente, cubiertos, motivo_coherencia),
    }


# ---------------------------------------------------------------------------
# Mapa de la investigación por diana
# ---------------------------------------------------------------------------


def clave_diana(h: Any) -> dict[str, str]:
    """{clave, etiqueta, origen}: la diana o proceso canónico de una hipótesis.
    Por orden: `tarjeta.diana` (resuelta al diccionario curado de
    `rosa/ontologias.py` o a una entidad de `h.entidades` que la nombre; si no
    resuelve, el texto normalizado con prefijo 'texto:'), el biomarcador de la
    comprobación con la misma regla, la primera entidad canónica que sea gen,
    compuesto, proceso, célula o componente (si no, la primera que no sea una
    enfermedad), y si nada de eso hay, 'sin_diana'."""
    h = _d(h)
    entidades = [x for x in _l(h.get("entidades")) if isinstance(x, dict) and _s(x.get("id"))]
    for texto, origen in ((_d(h.get("tarjeta")).get("diana"), "tarjeta"), (_d(h.get("comprobacion")).get("biomarcador"), "biomarcador")):
        s = _s(texto)
        if not s:
            continue
        curadas = [x for x in ONTO.anotar_curadas(s) if x.get("tipo") not in _TIPOS_NO_DIANA]
        if curadas:
            return {"clave": curadas[0]["id"], "etiqueta": curadas[0]["etiqueta"], "origen": origen}
        for ent in entidades:
            if ent.get("tipo") in _TIPOS_NO_DIANA:
                continue
            nombres = [_s(ent.get("etiqueta"))] + [_s(a) for a in _l(ent.get("alias"))]
            if any(_mismo_nombre(s, n) for n in nombres if n):
                return {"clave": _s(ent["id"]), "etiqueta": _s(ent.get("etiqueta")) or _s(ent["id"]), "origen": origen}
        return {"clave": "texto:" + _norm(s), "etiqueta": s, "origen": origen}
    preferidas = [x for x in entidades if x.get("tipo") in ("gen", "compuesto", "proceso", "celula", "componente")] or [x for x in entidades if x.get("tipo") not in _TIPOS_NO_DIANA]
    if preferidas:
        ent = preferidas[0]
        return {"clave": _s(ent["id"]), "etiqueta": _s(ent.get("etiqueta")) or _s(ent["id"]), "origen": "entidades"}
    return {"clave": "sin_diana", "etiqueta": "Sin diana declarada", "origen": "ninguna"}


def _certeza_de(h: dict[str, Any]) -> str | None:
    c = _norm(_d(h.get("conclusion")).get("certeza"))
    return c if c in C.NIVELES else None


def _max_nivel(a: str | None, b: str | None) -> str | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if C.NIVELES.index(a) >= C.NIVELES.index(b) else b


def _pasos_de_hecho(x: dict[str, Any]) -> list[str]:
    """Qué pasos toca un hecho por su enunciado: el mecanismo siempre; los
    demás solo si los nombra. Compromiso de diana, replicación y evidencia en
    la población piden datos estructurados que un hecho no lleva."""
    texto = _s(x.get("enunciado")) + " " + _s(x.get("tema"))
    pasos = ["mecanismo"]
    if _INTERVENCION.search(texto):
        pasos.append("opciones_intervencion")
    if _es_funcional(texto):
        pasos.append("efecto_funcional")
    if _es_seguridad(texto):
        pasos.append("selectividad_toxicidad")
    if _exposicion_en(texto):
        pasos.append("exposicion")
    return pasos


def _ids_de_hecho(x: dict[str, Any]) -> set[str]:
    """Los identificadores canónicos de un hecho: los que trae en `entidades` o,
    en un registro antiguo sin ellas, los del diccionario curado sobre su enunciado."""
    return ONTO.ids_de([y for y in _l(x.get("entidades")) if isinstance(y, dict)]) or {y["id"] for y in ONTO.anotar_curadas(_s(x.get("enunciado")))}


def _hecho_de_clave(texto_hecho: str, ids: set[str], clave: str, patron: re.Pattern[str] | None) -> bool:
    """Si un hecho (su texto normalizado y sus identificadores canónicos) habla
    de la diana de una fila: por identificador canónico, o por nombre como
    palabra entera cuando la clave es texto libre."""
    if clave == "sin_diana":
        return False
    if patron is not None:
        return bool(patron.search(texto_hecho))
    return clave in ids


def mapa_ruta(e: Any, investigacion_id: str) -> dict[str, Any]:
    """La vista de programa: las hipótesis vivas de la investigación (no
    descartadas, no fusionadas en otra) agrupadas por diana o proceso
    canónico, con cuántas cubren cada paso, la certeza GRADE máxima entre las
    que lo cubren y los huecos (pasos sin hipótesis que los cubra ni
    parcialmente y sin hecho del modelo de mundo que los toque).

    Devuelve {investigacionId, filas, resumen}; cada fila es {clave, etiqueta,
    hipotesis: [ids], pasos: {paso: {hipotesis, parciales, hechos,
    certezaMax}}, huecos: [pasos], hechos: n}. Las filas van de más a menos
    pasos con alguna hipótesis que los cubra."""
    e = _d(e)
    vistos: set[str] = set()
    hipotesis: list[dict[str, Any]] = []
    for j, h in enumerate(_l(e.get("hipotesis"))):
        if not isinstance(h, dict) or h.get("investigacionId") != investigacion_id:
            continue
        hid = _s(h.get("id")) or f"pos-{j}"
        if hid in vistos:
            continue
        vistos.add(hid)
        if _norm(h.get("estado")) == "descartada" or h.get("fusionadaEn"):
            continue
        hipotesis.append(h)
    hechos = [(x, _ids_de_hecho(x), _pasos_de_hecho(x), _norm(x.get("enunciado")) + " " + _norm(x.get("tema"))) for x in _hechos_vivos(e) if x.get("investigacionId") == investigacion_id]
    indice = _indice_hechos(e)
    filas: dict[str, dict[str, Any]] = {}
    for h in hipotesis:
        cd = clave_diana(h)
        fila = filas.setdefault(cd["clave"], {"clave": cd["clave"], "etiqueta": cd["etiqueta"], "hipotesis": [], "pasos": {p: {"hipotesis": 0, "parciales": 0, "hechos": 0, "certezaMax": None} for p in PASOS_RUTA}, "huecos": [], "hechos": 0})
        fila["hipotesis"].append(h.get("id"))
        certeza = _certeza_de(h)
        for p in _evaluar(_Registro(e, h, indice))["pasos"]:
            celda = fila["pasos"][p["paso"]]
            if p["estado"] == "cubierto":
                celda["hipotesis"] += 1
                celda["certezaMax"] = _max_nivel(celda["certezaMax"], certeza)
            elif p["estado"] == "parcial":
                celda["parciales"] += 1
    for fila in filas.values():
        patron = _patron_nombre(fila["etiqueta"]) if fila["clave"].startswith("texto:") else None
        propios = [pasos for _x, ids, pasos, texto in hechos if _hecho_de_clave(texto, ids, fila["clave"], patron)]
        fila["hechos"] = len(propios)
        for pasos in propios:
            for p in pasos:
                fila["pasos"][p]["hechos"] += 1
        fila["huecos"] = [p for p in PASOS_RUTA if fila["pasos"][p]["hipotesis"] == 0 and fila["pasos"][p]["parciales"] == 0 and fila["pasos"][p]["hechos"] == 0]
    # De más a menos pasos con alguna hipótesis que los cubra; a igualdad, por etiqueta y por clave (determinista).
    ordenadas = sorted(filas.values(), key=lambda f: (-sum(1 for p in PASOS_RUTA if f["pasos"][p]["hipotesis"] > 0), f["etiqueta"].lower(), f["clave"]))
    return {"investigacionId": investigacion_id, "filas": ordenadas, "resumen": _resumen_mapa(ordenadas, len(hipotesis))}


def _resumen_mapa(filas: list[dict[str, Any]], n_hipotesis: int) -> str:
    if not filas:
        return "Sin hipótesis vivas en esta investigación: no hay ruta que mapear."
    primera = filas[0]
    avanzados = sum(1 for p in PASOS_RUTA if primera["pasos"][p]["hipotesis"] > 0)
    comunes = [ETIQUETAS_PASO[p] for p in PASOS_RUTA if all(p in f["huecos"] for f in filas)]
    partes = [f"{_n(len(filas), 'diana o proceso', 'dianas o procesos')} con {_n(n_hipotesis, 'hipótesis viva', 'hipótesis vivas')}", f"la más avanzada es {primera['etiqueta']} ({avanzados} de {len(PASOS_RUTA)} pasos con alguna hipótesis que los cubre)"]
    partes.append(f"huecos en todas las filas: {_enumerar(comunes)}" if comunes else "ningún paso está vacío en todas las filas")
    return _capitalizar("; ".join(partes)) + "."


# ---------------------------------------------------------------------------
# Texto en castellano
# ---------------------------------------------------------------------------


def texto_ruta(h_o_evaluacion: Any, e: Any = None) -> str:
    """La ruta en castellano, paso a paso, con la definición de cada paso la
    primera vez y hasta tres piezas de evidencia por paso. Acepta la
    evaluación de `evaluar_ruta` o una hipótesis (entonces la evalúa con `e`,
    o sin hechos ni ejecuciones si `e` no se da)."""
    x = _d(h_o_evaluacion)
    ev = x if "pasos" in x and "siguiente" in x else evaluar_ruta(e, x)
    lineas = [f"Ruta terapéutica: {ev.get('resumen', '')}".rstrip()]
    for i, p in enumerate(_l(ev.get("pasos")), 1):
        p = _d(p)
        paso = _s(p.get("paso"))
        etiqueta = ETIQUETAS_PASO.get(paso, paso)
        definicion = DEFINICIONES_PASO.get(paso)
        estado = ETIQUETAS_ESTADO.get(_s(p.get("estado")), _s(p.get("estado")) or "sin estado")
        lineas.append(f"{i}. {etiqueta}" + (f" ({definicion})" if definicion else "") + f": {estado}. {_capitalizar(_s(p.get('motivo')))}".rstrip())
        for pieza in _l(p.get("evidencia"))[:3]:
            pieza = _d(pieza)
            tipo = _s(pieza.get("tipo"))
            lineas.append(f"   - [{ETIQUETAS_EVIDENCIA.get(tipo, tipo or 'evidencia')}] {_s(pieza.get('texto'))}")
    return "\n".join(lineas)
