"""El contrato del experimento: qué se mide, en qué sistema y qué significa
cada resultado (16 de septiembre de 2026).

Hasta hoy el experimento de una hipótesis tenía un solo ensayo y un solo par
de criterios (qué lo confirma, qué lo refuta), y el resultado del laboratorio
un solo veredicto con dimensiones. Eso deja dos huecos que el informe de
ROSA2018 señala:

1. Un negativo no dice nada por sí solo. Si la intervención no llegó a la
   diana (sin exposición, compuesto inactivo, ensayo que no funcionó), el
   negativo habla del ensayo; si la diana sí se comprometió y el efecto no
   apareció, el negativo habla del mecanismo. Para distinguirlo hacen falta
   lecturas separadas: compromiso de diana por un lado, efecto por otro, y
   viabilidad para descartar toxicidad. Es la lectura en dos ramas (informe,
   página 12). "Compromiso de diana" (target engagement) significa que la
   intervención llegó a la molécula o al proceso al que apunta y lo modificó
   de forma medible.
2. Un cambio molecular no es beneficio clínico. Un biomarcador que baja en
   un cultivo no dice que una persona vaya a estar mejor. El contrato declara
   el nivel del desenlace (molecular, celular, fisiológico o de imagen,
   funcional o clínico) y el puente: qué tendría que pasar además para que
   el resultado importe a la población del programa. El propósito del
   biomarcador sigue el vocabulario BEST de la FDA y el NIH (2016), que es la
   clasificación oficial de para qué sirve un biomarcador.

Todo lo que hay aquí es regla determinista con su motivo al lado; ningún
modelo decide. Los modelos pydantic de este fichero los añade el integrador a
`ExperimentoPropuesto` (rosa/modulos/firmas.py) y las claves nuevas del
estado a `Experimento` (frontend/src/datos/tipos.ts); este módulo no toca
ninguno de los dos. Reglas que se conservan:

- Un registro antiguo sin las claves nuevas se trata como el valor de hoy:
  `normalizar_contrato` deriva una lectura de tipo biomarcador con el ensayo y
  el par confirma/refuta, y nada más; lo que no está declarado no se inventa.
- Una cifra que no lleva el nombre de la lectura es "no pude comprobar"
  (no_evaluable), nunca "no hay efecto". Una cifra que podría ser de varias
  lecturas («GFAP» con «GFAP en plasma» y «GFAP en LCR») es ambigua: no se
  asigna a ninguna y se dice; nunca se adivina.
- Los valores del vocabulario escritos de otra forma («Biomarcador», «iPSC»,
  «compromiso de diana») se llevan a su clave; lo que no corresponde a
  ninguna («ratón») se queda tal cual y la validación lo señala.
- Una mención negada de un conjunto de datos de acceso controlado («GEO, no
  ADNI») no cuenta como uso: el proponente repite la regla que se le dio.
- Las claves del estado van en camelCase como en tipos.ts (`queConfirma`,
  `quePrueba`); las de los modelos pydantic en snake_case como en firmas.py.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Vocabularios cerrados, con definición en una frase
# ---------------------------------------------------------------------------

# Propósitos de un biomarcador según BEST (Biomarkers, EndpointS, and other
# Tools; FDA-NIH Biomarker Working Group, 2016). Un biomarcador es una
# característica que se mide como indicador de un proceso biológico normal,
# patológico o de la respuesta a una intervención.
PROPOSITOS_BIOMARCADOR: dict[str, dict[str, str]] = {
    "susceptibilidad_riesgo": {
        "etiqueta": "susceptibilidad o riesgo",
        "definicion": "Indica el potencial de desarrollar la enfermedad en una persona que hoy no la tiene de forma clínicamente aparente (por ejemplo, ser portador de APOE e4).",
    },
    "diagnostico": {
        "etiqueta": "diagnóstico",
        "definicion": "Detecta o confirma la presencia de la enfermedad, o identifica a las personas con un subtipo de ella (por ejemplo, PET de amiloide positivo).",
    },
    "monitorizacion": {
        "etiqueta": "monitorización",
        "definicion": "Se mide de forma repetida para seguir el estado de la enfermedad o la exposición a una intervención o a un agente (por ejemplo, NfL en plasma cada seis meses).",
    },
    "pronostico": {
        "etiqueta": "pronóstico",
        "definicion": "En personas que ya tienen la enfermedad, indica la probabilidad de un evento clínico, de recurrencia o de progresión (por ejemplo, p-tau217 alto y progresión a demencia).",
    },
    "prediccion_respuesta": {
        "etiqueta": "predicción de respuesta",
        "definicion": "Identifica a las personas con más probabilidad que otras similares de tener un efecto favorable o desfavorable ante una intervención concreta (por ejemplo, APOE e4 y ARIA con anticuerpos antiamiloide).",
    },
    "farmacodinamico_respuesta": {
        "etiqueta": "farmacodinámico o de respuesta",
        "definicion": "Cambia en respuesta a la exposición a una intervención: muestra que hubo una respuesta biológica, incluido el compromiso de diana (por ejemplo, caída de amiloide en PET tras el tratamiento).",
    },
    "seguridad": {
        "etiqueta": "seguridad",
        "definicion": "Se mide antes o después de una exposición para indicar la probabilidad, la presencia o la extensión de una toxicidad como efecto adverso (por ejemplo, microhemorragias en RM).",
    },
}

# En qué nivel se lee el desenlace. Cuanto más abajo, más lejos del beneficio
# para una persona.
NIVELES_DESENLACE: dict[str, dict[str, str]] = {
    "molecular": {
        "etiqueta": "molecular",
        "definicion": "Una molécula o su cantidad o estado: proteína, ARN, metabolito, fosforilación (por ejemplo, GFAP en plasma, p-tau181).",
    },
    "celular": {
        "etiqueta": "celular",
        "definicion": "El comportamiento o el estado de células: viabilidad, morfología, fagocitosis, activación, sinapsis contadas (por ejemplo, microglía que fagocita amiloide).",
    },
    "fisiologico_imagen": {
        "etiqueta": "fisiológico o de imagen",
        "definicion": "La función de un tejido u órgano medida en el organismo vivo: PET, resonancia, EEG, presión, volumen (por ejemplo, atrofia del hipocampo en resonancia).",
    },
    "funcional_clinico": {
        "etiqueta": "funcional o clínico",
        "definicion": "Lo que la persona hace, siente o le ocurre: cognición, función en la vida diaria, síntomas, diagnóstico clínico, progresión a demencia.",
    },
}

# Sistemas experimentales: qué prueba cada uno por defecto y, sobre todo, qué
# no representa. Un negativo o un positivo se lee dentro de esos límites.
SISTEMAS_EXPERIMENTALES: dict[str, dict[str, Any]] = {
    "observacional_humano": {
        "etiqueta": "observacional en humanos",
        "definicion": "Cohorte, casos y controles o corte transversal en personas: se observa, no se interviene.",
        "que_no_representa": "no establece causalidad (confusión, causa inversa, selección) ni permite intervenir; las asociaciones dependen de la cohorte y de la plataforma de medida",
        "intervencional": False,
    },
    "datos_publicos_existentes": {
        "etiqueta": "datos públicos ya existentes",
        "definicion": "Reanálisis de datos ya recogidos y de acceso abierto (GEO, SEA-AD abierto, OASIS con registro gratuito).",
        "que_no_representa": "no es una medición nueva ni un diseño pensado para esta pregunta; hereda la selección, los faltantes y la calidad de la cohorte original, y solo permite lo que sus variables contienen",
        "intervencional": False,
    },
    "celulas_humanas_donante": {
        "etiqueta": "células humanas de donante",
        "definicion": "Células primarias de personas donantes (microglía, astrocitos o neuronas de tejido post mortem o de biopsia) en cultivo.",
        "que_no_representa": "no reproduce la interacción entre tipos celulares ni el entorno del tejido envejecido; las células cambian de fenotipo al cultivarse y el donante introduce variabilidad no controlada",
        "intervencional": True,
    },
    "ipsc": {
        "etiqueta": "células iPSC",
        "definicion": "Neuronas o glía derivadas de células madre pluripotentes inducidas (iPSC) humanas, reprogramadas desde células de una persona.",
        "que_no_representa": "no reproduce la edad (su madurez epigenética es fetal) ni el entorno del tejido; hay variabilidad entre líneas y clones y el fondo genético de cada donante pesa",
        "intervencional": True,
    },
    "organoide": {
        "etiqueta": "organoide cerebral",
        "definicion": "Agregado tridimensional de células derivadas de iPSC que se organiza en capas parecidas a las del cerebro en desarrollo.",
        "que_no_representa": "no tiene vasos sanguíneos ni microglía salvo que se añadan, no llega a la maduración adulta, tiene un núcleo necrótico por falta de oxígeno y varía entre lotes",
        "intervencional": True,
    },
    "cocultivo": {
        "etiqueta": "cocultivo",
        "definicion": "Dos o más tipos celulares cultivados juntos para medir cómo se afectan entre sí (por ejemplo, neuronas con microglía).",
        "que_no_representa": "no reproduce la arquitectura del tejido ni las señales del resto del organismo; las proporciones entre tipos celulares las fija el protocolo, no la biología",
        "intervencional": True,
    },
    "animal": {
        "etiqueta": "animal",
        "definicion": "Modelo animal, casi siempre ratón transgénico con amiloide o tau humanos.",
        "que_no_representa": "no reproduce la variación genética humana ni la edad; los ratones con amiloide no desarrollan tau ni neurodegeneración completa",
        "intervencional": True,
    },
    "in_silico": {
        "etiqueta": "in silico",
        "definicion": "Modelo computacional o análisis sobre datos ya existentes, sin medir nada nuevo.",
        "que_no_representa": "no mide nada nuevo: hereda lo que contienen los datos de entrada y los supuestos del modelo; un resultado in silico es una predicción hasta que se mide",
        "intervencional": False,
    },
}

# Qué clase de cosa mide cada lectura. Separarlas es lo que permite leer un
# negativo en dos ramas.
TIPOS_LECTURA: dict[str, dict[str, str]] = {
    "compromiso_diana": {
        "etiqueta": "compromiso de diana",
        "definicion": "Demuestra que la intervención llegó a la diana y la modificó: ocupación, fosforilación, expresión o actividad de la molécula a la que apunta.",
    },
    "viabilidad": {
        "etiqueta": "viabilidad",
        "definicion": "Demuestra que las células o el modelo sobrevivieron y toleraron la intervención; sin ella un efecto puede ser toxicidad.",
    },
    "funcion_mecanismo": {
        "etiqueta": "función o mecanismo",
        "definicion": "Mide el proceso biológico que la hipótesis propone, en la dirección que predice (por ejemplo, fagocitosis, secreción de citoquinas, sinapsis).",
    },
    "biomarcador": {
        "etiqueta": "biomarcador",
        "definicion": "Una medida indirecta del estado biológico que se puede tomar en personas (por ejemplo, GFAP en plasma, PET de amiloide).",
    },
    "seguridad": {
        "etiqueta": "seguridad",
        "definicion": "Señales de daño o de efectos adversos de la intervención (por ejemplo, muerte celular fuera de la diana, microhemorragias).",
    },
}

TIPOS_EFECTO = ("funcion_mecanismo", "biomarcador")

# Datos de acceso controlado que Rosa no usa (decisión del 11 de septiembre de
# 2026: solo datos públicos). Se buscan como palabra entera, sin distinguir
# mayúsculas, admitiendo la oleada como sufijo («ADNI-3», «ADNI2», «ADNI-GO»);
# «A4» va sin sufijo para que «A42» (amiloide) no cuente. Una mención negada
# en las tres palabras anteriores («nunca ADNI», «GEO, no ADNI», «en lugar de
# ROSMAP») no es un uso: el proponente repite a menudo la regla que se le dio.
DATOS_ACCESO_CONTROLADO = ("ADNI", "ROSMAP", "MSBB", "AD Knowledge Portal", "AMP-AD", "NIAGADS", "A4", "NACC", "UK Biobank", "AIBL")


def _patron_controlado(nombre: str) -> re.Pattern[str]:
    base = re.escape(nombre)
    if nombre == "A4":
        return re.compile(rf"(?<![\w-]){base}(?![\w-])", re.I)
    return re.compile(rf"(?<![\w-]){base}(?:[-\s]?\d+)?(?!\w)", re.I)


_CONTROLADOS: tuple[tuple[str, re.Pattern[str]], ...] = tuple((d, _patron_controlado(d)) for d in DATOS_ACCESO_CONTROLADO)
_NEGACION_DATOS = re.compile(r"(?:\b(?:no|nunca|jamas|sin|ni|not|never|without|nor)\b|\ben (?:lugar|vez) de\b|\binstead of\b|\bexcluy\w*|\bexclud\w*|\bdescart\w*|\bevit\w*|\bavoid\w*|\bsalvo\b|\bexcepto\b)(?:\s+\w+){0,3}\s*[:,]?\s*$")


def _datos_controlados(texto: Any) -> list[str]:
    """Los conjuntos de datos de acceso controlado que un texto nombra como uso
    (no negados), con su nombre canónico, ordenados y sin repetir."""
    t = _sin_tildes(_texto(texto))
    if not t:
        return []
    hallados: set[str] = set()
    for nombre, patron in _CONTROLADOS:
        for m in patron.finditer(t):
            antes = t[max(0, m.start() - 40): m.start()]
            if _NEGACION_DATOS.search(antes):
                continue
            hallados.add(nombre)
    return sorted(hallados)


# Palabras con las que un criterio habla de beneficio para una persona.
# «funcional» a secas no está (un «ensayo funcional» de fagocitosis es
# celular) ni «deterioro» solo (puede ser de una membrana): se exige el
# sentido clínico.
_BENEFICIO = re.compile(r"\b(beneficio clinico|mejora\w* (?:de )?(?:la )?cognici\w+|cognici\w+|cognitiv\w+|demencia|deterioro cognitiv\w*|declive cognitiv\w*|funcion (?:diaria|en la vida diaria|cognitiva)|capacidad funcional|actividades de la vida diaria|sintoma\w*|calidad de vida|memoria (?:episodica|de trabajo|verbal|semantica|espacial)|perdida de memoria|clinical benefit|cognitive\w*|cognition|dementia|cognitive decline|symptom\w*|quality of life|daily living|memory)\b", re.I)

Proposito = Literal["susceptibilidad_riesgo", "diagnostico", "monitorizacion", "pronostico", "prediccion_respuesta", "farmacodinamico_respuesta", "seguridad"]
NivelDesenlace = Literal["molecular", "celular", "fisiologico_imagen", "funcional_clinico"]
TipoSistema = Literal["observacional_humano", "datos_publicos_existentes", "celulas_humanas_donante", "ipsc", "organoide", "cocultivo", "animal", "in_silico"]
TipoLectura = Literal["compromiso_diana", "viabilidad", "funcion_mecanismo", "biomarcador", "seguridad"]
VeredictoLectura = Literal["confirma", "refuta", "inconcluso", "no_evaluable"]
RamaNegativo = Literal["diana_comprometida_sin_efecto", "diana_no_comprometida", "sin_lecturas_separadas"]

# Claves nuevas del estado (camelCase, como en tipos.ts) con su valor vacío.
CLAVES_CONTRATO: dict[str, Any] = {"lecturas": [], "sistema": None, "propositoBiomarcador": None, "nivelDesenlace": None, "puenteAlBeneficio": ""}
_CLAVES_LECTURA = ("nombre", "tipo", "queConfirma", "queRefuta", "control", "unidad")


def vocabularios() -> dict[str, Any]:
    """Los cuatro vocabularios con etiqueta y definición, para la interfaz."""
    return {
        "propositosBiomarcador": {k: dict(v) for k, v in PROPOSITOS_BIOMARCADOR.items()},
        "nivelesDesenlace": {k: dict(v) for k, v in NIVELES_DESENLACE.items()},
        "sistemasExperimentales": {k: {"etiqueta": v["etiqueta"], "definicion": v["definicion"], "queNoRepresenta": v["que_no_representa"], "intervencional": v["intervencional"]} for k, v in SISTEMAS_EXPERIMENTALES.items()},
        "tiposLectura": {k: dict(v) for k, v in TIPOS_LECTURA.items()},
    }


def etiqueta(vocabulario: dict[str, dict[str, Any]], clave: Any) -> str:
    """La etiqueta legible de una clave; la clave misma con espacios si no está en el vocabulario."""
    v = vocabulario.get(str(clave)) if clave is not None else None
    return v["etiqueta"] if v else str(clave or "").replace("_", " ")


def que_no_representa_por_defecto(tipo: Any) -> str:
    """El límite general de un sistema experimental; vacío si el tipo no se conoce."""
    s = SISTEMAS_EXPERIMENTALES.get(str(tipo)) if tipo else None
    return s["que_no_representa"] if s else ""


# ---------------------------------------------------------------------------
# Modelos pydantic para ExperimentoPropuesto (el integrador los añade a firmas.py)
# ---------------------------------------------------------------------------


class LecturaPropuesta(BaseModel):
    """Una medida del experimento con su criterio y su control. Un experimento
    interpretable lleva al menos una de compromiso de diana y una de efecto."""

    nombre: str = Field(description="Qué se mide y con qué técnica, en pocas palabras (por ejemplo 'p-tau181 en medio de cultivo por Simoa')")
    tipo: TipoLectura = Field(description="compromiso_diana: la intervención llegó a la diana y la modificó; viabilidad: el modelo toleró la intervención; funcion_mecanismo: el proceso que la hipótesis propone; biomarcador: medida indirecta tomable en personas; seguridad: daño fuera de la diana")
    que_confirma: str = Field(description="Qué valor o patrón de esta lectura confirmaría la hipótesis, con umbral y dirección cuando se pueda ('aumento de al menos 20 % frente al control')")
    que_refuta: str = Field(description="Qué valor o patrón de esta lectura la refutaría ('cambio menor del 5 % con potencia para detectar 20 %')")
    control: str = Field(default="", description="El control de esta lectura: positivo (demuestra que el montaje la detecta) y negativo (descarta señal espuria). Sin control un negativo no se interpreta")
    unidad: str = Field(default="", description="La unidad de la medida (pg/mL, %, células por campo); vacío si no aplica")


class SistemaPropuesto(BaseModel):
    """En qué sistema se hace el experimento y, sobre todo, qué no representa."""

    tipo: TipoSistema = Field(description="observacional_humano, datos_publicos_existentes (GEO, SEA-AD abierto, OASIS), celulas_humanas_donante, ipsc, organoide, cocultivo, animal o in_silico")
    que_prueba: str = Field(description="Qué parte de la hipótesis puede probar este sistema y por qué es el adecuado")
    que_no_representa: str = Field(default="", description="Qué parte de la biología humana o de la enfermedad este sistema no reproduce, en concreto para esta hipótesis (edad, variación genética, interacción entre células, exposición)")


class ContratoPropuesto(BaseModel):
    """Los campos nuevos de `ExperimentoPropuesto`. El integrador puede hacer
    que `ExperimentoPropuesto` herede de esta clase o copiar sus campos."""

    lecturas: list[LecturaPropuesta] = Field(default_factory=list, description="Las lecturas separadas del experimento: al menos una de compromiso de diana y una de efecto (función o biomarcador) cuando hay intervención; una de viabilidad en sistemas celulares")
    sistema: SistemaPropuesto | None = Field(default=None, description="El sistema experimental con lo que prueba y lo que no representa")
    proposito_biomarcador: Proposito | None = Field(default=None, description="Para qué sirve el biomarcador que se mide, según BEST de la FDA y el NIH; None si ninguna lectura es un biomarcador")
    nivel_desenlace: NivelDesenlace | None = Field(default=None, description="El nivel del desenlace principal: molecular, celular, fisiologico_imagen o funcional_clinico")
    puente_al_beneficio: str = Field(default="", description="Qué tendría que pasar además para que este resultado importe a la población del programa; obligatorio si el desenlace es molecular o celular")


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------

_ESPACIOS = re.compile(r"\s+")
_STOP = {"de", "del", "la", "el", "los", "las", "en", "por", "con", "y", "o", "a", "al", "un", "una", "the", "of", "in", "and", "or", "for", "vs", "frente", "control"}


def _texto(v: Any) -> str:
    """Cadena limpia; None y lo que no es texto se convierten sin romper. Una
    lista o tupla (por ejemplo un protocolo en pasos) se une con espacios en
    vez de volcarse como su representación de Python."""
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return _ESPACIOS.sub(" ", " ".join(_texto(e) for e in v)).strip()
    if isinstance(v, str):
        return _ESPACIOS.sub(" ", v).strip()
    return _ESPACIOS.sub(" ", str(v)).strip()


def _sin_tildes(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def _clave(t: Any) -> str:
    """Forma comparable de un nombre: minúsculas, sin tildes, sin signos, un espacio."""
    limpio = re.sub(r"[^\w%]+", " ", _sin_tildes(_texto(t)).lower())
    return _ESPACIOS.sub(" ", limpio).strip()


def _tokens(t: Any) -> set[str]:
    return {w for w in _clave(t).split() if w not in _STOP and len(w) > 1}


def _clave_vocabulario(valor: Any, vocabulario: dict[str, dict[str, Any]]) -> tuple[str, bool]:
    """La clave del vocabulario a la que corresponde un valor escrito de otra
    forma («Biomarcador», «iPSC», «Diagnóstico», «in silico», «compromiso de
    diana»): minúsculas, sin tildes, espacios como guion bajo, o la etiqueta
    legible de una clave. Devuelve (clave, True) si corresponde a una; si no,
    (el texto limpio tal como venía, False) para que la validación lo diga.
    Es una normalización de forma, no una interpretación: «ratón» no se
    convierte en «animal»."""
    t = _texto(valor)
    if not t:
        return "", False
    if t in vocabulario:
        return t, True
    k = re.sub(r"[^\w]+", "_", _sin_tildes(t).lower()).strip("_")
    if k in vocabulario:
        return k, True
    ck = _clave(t)
    for clave, v in vocabulario.items():
        if ck == _clave(v.get("etiqueta", "")):
            return clave, True
    return t, False


def _campo(obj: Any, *nombres: str, por_defecto: Any = "") -> Any:
    """Lee un campo de un dict o de un objeto (pydantic), probando varios nombres (camelCase y snake_case)."""
    for n in nombres:
        if isinstance(obj, dict):
            if n in obj and obj[n] is not None:
                return obj[n]
        elif hasattr(obj, n) and getattr(obj, n) is not None:
            return getattr(obj, n)
    return por_defecto


_SIMBOLO_RE = re.compile(r"(?<![\w-])([A-Za-zβα][\w-]*\d[\w-]*|[A-Z][A-Za-z]*[A-Z][A-Za-z]*)(?![\w-])")


def _simbolos(texto: Any) -> set[str]:
    """Los símbolos de molécula o gen de un texto (GFAP, NfL, TREM2, p-tau181):
    palabras con un dígito o con dos mayúsculas, de tres letras o más, en forma
    comparable. Sirven para emparejar nombres escritos en idiomas distintos."""
    return {_clave(m.group(1)) for m in _SIMBOLO_RE.finditer(_texto(texto)) if len(m.group(1)) >= 3}


def _forma(t: Any) -> tuple[str, set[str]]:
    """(clave comparable, tokens) de un nombre, calculados una vez."""
    k = _clave(t)
    return k, _tokens(k)


def _coincide_formas(a: tuple[str, set[str]], b: tuple[str, set[str]]) -> bool:
    ka, ta = a
    kb, tb = b
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    if not ta or not tb:
        # Un nombre de una sola letra o de solo palabras vacías («p», «n»,
        # «control») no nombra a ninguna lectura por contención.
        return False
    # Contención por palabra entera: las claves ya van en minúsculas, sin
    # signos y con un solo espacio, así basta rodearlas de espacios.
    if f" {ka} " in f" {kb} " or f" {kb} " in f" {ka} ":
        return True
    corto, largo = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return corto <= largo


def _coincide(lectura: str, cifra: str) -> bool:
    """Una cifra nombra una lectura si sus nombres coinciden, uno contiene al
    otro por palabra entera, o todas las palabras del más corto (sin vacías)
    están en el otro."""
    return _coincide_formas(_forma(lectura), _forma(cifra))


# ---------------------------------------------------------------------------
# Normalizar: del registro antiguo al contrato de hoy, sin inventar
# ---------------------------------------------------------------------------


def _lectura_limpia(l: Any) -> dict[str, Any] | None:
    """Una lectura del estado con sus seis claves; acepta camelCase y snake_case
    y objetos pydantic. El tipo se lleva a su clave del vocabulario si venía
    escrito de otra forma («Biomarcador»). Las claves de más de un dict (el
    `id` que ponga la interfaz, marcas) se conservan: no son del contrato,
    pero tampoco se pierden al normalizar. None si no tiene ni nombre ni
    criterios."""
    if l is None or isinstance(l, (str, int, float, bool, list, tuple)):
        return None
    d: dict[str, Any] = {k: v for k, v in l.items() if k not in ("que_confirma", "que_refuta")} if isinstance(l, dict) else {}
    d.update({
        "nombre": _texto(_campo(l, "nombre")),
        "tipo": _clave_vocabulario(_campo(l, "tipo"), TIPOS_LECTURA)[0],
        "queConfirma": _texto(_campo(l, "queConfirma", "que_confirma")),
        "queRefuta": _texto(_campo(l, "queRefuta", "que_refuta")),
        "control": _texto(_campo(l, "control")),
        "unidad": _texto(_campo(l, "unidad")),
    })
    if not (d["nombre"] or d["queConfirma"] or d["queRefuta"]):
        return None
    return d


def _sistema_limpio(s: Any) -> dict[str, str] | None:
    """El sistema con sus tres claves. Una cadena suelta («ipsc», «iPSC») se
    toma como el tipo, sin inventar lo que prueba ni lo que no representa."""
    if s is None or isinstance(s, (int, float, bool, list, tuple)):
        return None
    if isinstance(s, str):
        tipo = _clave_vocabulario(s, SISTEMAS_EXPERIMENTALES)[0]
        return {"tipo": tipo, "quePrueba": "", "queNoRepresenta": ""} if tipo else None
    d = {"tipo": _clave_vocabulario(_campo(s, "tipo"), SISTEMAS_EXPERIMENTALES)[0], "quePrueba": _texto(_campo(s, "quePrueba", "que_prueba")), "queNoRepresenta": _texto(_campo(s, "queNoRepresenta", "que_no_representa"))}
    if not (d["tipo"] or d["quePrueba"] or d["queNoRepresenta"]):
        return None
    return d


def normalizar_contrato(experimento: Any, con_motivos: bool = False) -> dict[str, Any] | tuple[dict[str, Any], list[str]]:
    """El experimento con las claves nuevas del estado (`lecturas`, `sistema`,
    `propositoBiomarcador`, `nivelDesenlace`, `puenteAlBeneficio`) rellenadas
    desde los campos antiguos cuando faltan. Devuelve una copia; con
    `con_motivos=True` devuelve también la lista de lo que hizo y por qué.

    Un registro antiguo (solo `ensayo`, `confirma`, `refuta`, `controles`)
    produce una sola lectura de tipo biomarcador con ese ensayo, ese par de
    criterios y esos controles: es lo que aquel contrato decía, sin añadir
    nada. El sistema, el propósito, el nivel y el puente no se deducen: lo que
    no está declarado queda vacío y `validar_contrato` lo dice. Un valor fuera
    del vocabulario se deja vacío y se anota (no rompe). Lo que no sea un
    diccionario vale como experimento vacío."""
    motivos: list[str] = []
    x: dict[str, Any] = dict(experimento) if isinstance(experimento, dict) else {}
    if not isinstance(experimento, dict) and experimento is not None:
        motivos.append("el experimento no es un diccionario: se trata como vacío")

    # Lecturas declaradas, o una derivada del ensayo antiguo.
    crudas = x.get("lecturas")
    lecturas: list[dict[str, Any]] = []
    if isinstance(crudas, list):
        for l in crudas:
            limpia = _lectura_limpia(l)
            if limpia:
                lecturas.append(limpia)
            elif l is not None:
                motivos.append("se descartó una lectura sin nombre ni criterios")
    elif crudas is not None:
        motivos.append("la clave lecturas no era una lista: se ignora")
    if not lecturas:
        ensayo, confirma, refuta = _texto(x.get("ensayo")), _texto(x.get("confirma")), _texto(x.get("refuta"))
        if ensayo or confirma or refuta:
            lecturas = [{"nombre": ensayo or "medida principal", "tipo": "biomarcador", "queConfirma": confirma, "queRefuta": refuta, "control": _texto(x.get("controles")), "unidad": ""}]
            motivos.append("registro antiguo: una lectura de tipo biomarcador derivada del ensayo y del par confirma/refuta" + (", con los controles del experimento" if lecturas[0]["control"] else ", sin control declarado"))
        else:
            motivos.append("sin ensayo ni criterios: no hay lectura que derivar")
    x["lecturas"] = lecturas

    sistema = _sistema_limpio(x.get("sistema"))
    if x.get("sistema") is not None and sistema is None:
        motivos.append("el sistema declarado no tiene tipo ni texto: se deja vacío")
    elif isinstance(x.get("sistema"), str) and sistema:
        motivos.append(f"el sistema venía como texto («{_texto(x['sistema'])}»): se toma como su tipo, sin lo que prueba ni lo que no representa")
    x["sistema"] = sistema

    for clave, vocab, nombre in (("propositoBiomarcador", PROPOSITOS_BIOMARCADOR, "propósito del biomarcador"), ("nivelDesenlace", NIVELES_DESENLACE, "nivel del desenlace")):
        crudo = _texto(x.get(clave))
        valor, en_vocabulario = _clave_vocabulario(crudo, vocab)
        if valor and not en_vocabulario:
            motivos.append(f"{nombre} «{valor}» fuera del vocabulario: se deja vacío")
            valor = ""
        elif valor and valor != crudo:
            motivos.append(f"{nombre} «{crudo}» escrito de otra forma: se toma como «{valor}»")
        x[clave] = valor or None
    x["puenteAlBeneficio"] = _texto(x.get("puenteAlBeneficio"))
    return (x, motivos) if con_motivos else x


def contrato_desde_propuesta(propuesta: Any) -> dict[str, Any]:
    """Las claves nuevas del estado a partir de un `ExperimentoPropuesto` (o de
    cualquier objeto o dict con `lecturas`, `sistema`, `proposito_biomarcador`,
    `nivel_desenlace`, `puente_al_beneficio`). Para `corrida._proponer_experimento`:
    `experimento.update(contrato_desde_propuesta(x))`. Sin esos atributos
    devuelve los valores vacíos, así una firma antigua sigue funcionando."""
    lecturas = _campo(propuesta, "lecturas", por_defecto=[]) or []
    return normalizar_contrato({
        "lecturas": [l for l in (_lectura_limpia(v) for v in (lecturas if isinstance(lecturas, list) else [])) if l],
        "sistema": _sistema_limpio(_campo(propuesta, "sistema", por_defecto=None)),
        "propositoBiomarcador": _campo(propuesta, "proposito_biomarcador", "propositoBiomarcador", por_defecto=None),
        "nivelDesenlace": _campo(propuesta, "nivel_desenlace", "nivelDesenlace", por_defecto=None),
        "puenteAlBeneficio": _campo(propuesta, "puente_al_beneficio", "puenteAlBeneficio"),
    })


# ---------------------------------------------------------------------------
# Validar: la lista de lo que le falta al contrato, en castellano
# ---------------------------------------------------------------------------


def validar_contrato(experimento: Any) -> list[str]:
    """Los problemas del contrato, uno por frase, en orden fijo. Trabaja sobre
    el contrato normalizado (así un registro antiguo se juzga por lo que
    decía). Lista vacía: nada que objetar por regla. No hay puntuación: un
    problema es un problema."""
    x = normalizar_contrato(experimento)
    if not isinstance(experimento, dict) or not experimento:
        return ["no hay experimento propuesto"]
    problemas: list[str] = []
    lecturas: list[dict[str, Any]] = x["lecturas"]
    sistema = x["sistema"]
    tipo_sistema = (sistema or {}).get("tipo") or ""
    info_sistema = SISTEMAS_EXPERIMENTALES.get(tipo_sistema)

    # 1. Lecturas
    if not lecturas:
        problemas.append("el experimento no tiene ninguna lectura (qué se mide, qué la confirma y qué la refuta)")
    vistas: dict[str, str] = {}
    for i, l in enumerate(lecturas, 1):
        nombre = l["nombre"] or f"lectura {i}"
        if not l["nombre"]:
            problemas.append(f"la lectura {i} no tiene nombre (qué se mide y con qué técnica)")
        if l["tipo"] not in TIPOS_LECTURA:
            problemas.append(f"la lectura «{nombre}» tiene un tipo fuera del vocabulario: «{l['tipo'] or 'vacío'}» (compromiso de diana, viabilidad, función o mecanismo, biomarcador, seguridad)")
        if not l["queConfirma"]:
            problemas.append(f"la lectura «{nombre}» no dice qué resultado confirma la hipótesis")
        if not l["queRefuta"]:
            problemas.append(f"la lectura «{nombre}» no dice qué resultado la refuta")
        if l["queConfirma"] and l["queRefuta"] and _clave(l["queConfirma"]) == _clave(l["queRefuta"]):
            problemas.append(f"la lectura «{nombre}» confirma y refuta con el mismo criterio")
        if not l["control"]:
            problemas.append(f"falta el control de la lectura «{nombre}»: sin control positivo y negativo un negativo no se interpreta")
        k = _clave(l["nombre"])
        if k and k in vistas:
            problemas.append(f"la lectura «{nombre}» aparece dos veces")
        elif k:
            vistas[k] = nombre

    # 2. Sistema
    if sistema is None:
        problemas.append("el experimento no declara el sistema experimental (observacional en humanos, datos públicos, células de donante, iPSC, organoide, cocultivo, animal o in silico)")
    else:
        if not tipo_sistema:
            problemas.append("el sistema experimental no tiene tipo")
        elif info_sistema is None:
            problemas.append(f"el sistema experimental «{tipo_sistema}» no está en el vocabulario")
        if not sistema["quePrueba"]:
            problemas.append("el sistema no dice qué prueba de la hipótesis")
        if not sistema["queNoRepresenta"]:
            limite = que_no_representa_por_defecto(tipo_sistema)
            problemas.append("el sistema no dice qué no representa" + (f"; el límite general de «{etiqueta(SISTEMAS_EXPERIMENTALES, tipo_sistema)}» es: {limite}" if limite else ""))

    # 3. Datos de acceso controlado: solo datos públicos. Campo por campo, para
    # que una negación no cruce de un texto al siguiente.
    textos_datos = [x.get("analisisPedido"), (sistema or {}).get("quePrueba", "")]
    if tipo_sistema in ("datos_publicos_existentes", "in_silico"):
        textos_datos.append(x.get("protocolo"))
    hallados = sorted({d for t in textos_datos for d in _datos_controlados(t)})
    if hallados:
        problemas.append(f"el análisis nombra datos de acceso controlado ({', '.join(hallados)}): Rosa trabaja solo con datos públicos (GEO, SEA-AD abierto, OASIS con registro)")

    # 4. Las dos ramas del negativo: en un sistema con intervención hace falta
    # una lectura de compromiso de diana aparte del efecto, y viabilidad en células.
    tipos = {l["tipo"] for l in lecturas}
    if info_sistema and info_sistema["intervencional"]:
        if "compromiso_diana" not in tipos:
            problemas.append("sin una lectura de compromiso de diana un negativo no distingue «la diana no se tocó» de «se tocó y no pasó nada»")
        if not tipos & set(TIPOS_EFECTO):
            problemas.append("sin una lectura de efecto (función o mecanismo, o biomarcador) el compromiso de diana no prueba la hipótesis")
        if tipo_sistema != "animal" and "viabilidad" not in tipos:
            problemas.append("sin una lectura de viabilidad un efecto en células puede ser toxicidad")

    # 5. Propósito BEST del biomarcador.
    proposito = x["propositoBiomarcador"]
    if "biomarcador" in tipos and not proposito:
        problemas.append("hay una lectura de biomarcador sin propósito BEST declarado (susceptibilidad o riesgo, diagnóstico, monitorización, pronóstico, predicción de respuesta, farmacodinámico, seguridad)")
    crudo, en_vocabulario = _clave_vocabulario(experimento.get("propositoBiomarcador"), PROPOSITOS_BIOMARCADOR)
    if crudo and not en_vocabulario:
        problemas.append(f"el propósito del biomarcador «{crudo}» está fuera del vocabulario BEST")

    # 6. Nivel del desenlace y puente al beneficio.
    nivel = x["nivelDesenlace"]
    crudo_nivel, en_vocabulario = _clave_vocabulario(experimento.get("nivelDesenlace"), NIVELES_DESENLACE)
    if crudo_nivel and not en_vocabulario:
        problemas.append(f"el nivel del desenlace «{crudo_nivel}» está fuera del vocabulario")
    elif not nivel:
        problemas.append("el experimento no declara el nivel del desenlace (molecular, celular, fisiológico o de imagen, funcional o clínico)")
    if nivel in ("molecular", "celular") and not x["puenteAlBeneficio"]:
        # Solo los criterios de confirmación: lo que el experimento dice que
        # demostraría. La decisión que cambia habla del paso siguiente y puede
        # nombrar la cognición sin vender el resultado como beneficio.
        criterios = " ".join([l["queConfirma"] for l in lecturas] + [_texto(x.get("confirma"))])
        m = _BENEFICIO.search(_sin_tildes(criterios))
        if m:
            problemas.append(f"el desenlace {etiqueta(NIVELES_DESENLACE, nivel)} se presenta como beneficio clínico sin puente: el criterio habla de «{m.group(0)}» pero lo que se mide es {etiqueta(NIVELES_DESENLACE, nivel)}; falta decir qué tendría que pasar además para que importe a una persona")
        else:
            problemas.append(f"el desenlace es {etiqueta(NIVELES_DESENLACE, nivel)} y el experimento no declara el puente al beneficio (qué tendría que pasar además para que el resultado importe a una persona)")
    return problemas


# ---------------------------------------------------------------------------
# Lo que se congela en el prerregistro
# ---------------------------------------------------------------------------


def lecturas_para_hash(experimento: Any) -> list[dict[str, str]]:
    """La lista canónica de lecturas que se congela al prerregistrar: solo las
    seis claves del contrato, textos limpios, ordenadas por tipo, nombre y
    criterios. Es la misma lista para el mismo contrato con las lecturas en
    otro orden o con claves de más (ids, marcas de la interfaz)."""
    x = normalizar_contrato(experimento)
    canonicas = [{k: _texto(l.get(k)) for k in _CLAVES_LECTURA} for l in x["lecturas"]]
    return sorted(canonicas, key=lambda l: (l["tipo"], _clave(l["nombre"]), _clave(l["queConfirma"]), _clave(l["queRefuta"]), _clave(l["control"]), l["unidad"]))


def es_interpretable(experimento: Any) -> tuple[bool, str]:
    """Si el experimento tiene criterios que congelar: alguna lectura con su
    criterio de confirmación y el de refutación (un registro antiguo los
    aporta por el par confirma/refuta), o al menos un ensayo declarado. Es lo
    que `asignar_experimento` comprueba hoy con `confirma`, `refuta` y
    `ensayo`; con el contrato nuevo la comprobación pasa por aquí para que un
    experimento solo con lecturas también se pueda prerregistrar. Devuelve
    (sí o no, motivo)."""
    x = normalizar_contrato(experimento)
    if not isinstance(experimento, dict) or not experimento:
        return False, "no hay experimento propuesto"
    completas = [l for l in x["lecturas"] if l["queConfirma"] and l["queRefuta"]]
    if completas:
        return True, f"{len(completas)} de {len(x['lecturas'])} lecturas con criterio de confirmación y de refutación"
    crudas = experimento.get("lecturas")
    explicitas = isinstance(crudas, list) and any(_lectura_limpia(l) for l in crudas)
    if explicitas:
        return False, "ninguna lectura tiene a la vez el criterio de confirmación y el de refutación: sin ellos un negativo no se interpreta"
    if _texto(experimento.get("ensayo")):
        return True, "solo hay un ensayo declarado, sin criterios por lectura (registro antiguo)"
    return False, "sin lecturas ni ensayo: no hay criterio que congelar"


def hash_lecturas(experimento: Any) -> str:
    """SHA-256 de la lista canónica (mismo hash canónico que rosa/sello.py)."""
    from rosa.sello import hash_canonico

    return hash_canonico(lecturas_para_hash(experimento))


def bloque_prerregistro(experimento: Any) -> list[str]:
    """Las líneas del contrato para `texto_prerregistro`: lecturas fijadas de
    antemano, sistema, propósito, nivel y puente, y el hash de las lecturas.
    Lista vacía si no hay nada que congelar. Solo para prerregistros nuevos:
    un artefacto ya congelado no se reescribe."""
    x = normalizar_contrato(experimento)
    if not any(x[k] for k in CLAVES_CONTRATO):
        return []
    L = ["", "## Lecturas fijadas de antemano (contrato del experimento)"]
    if x["lecturas"]:
        for l in lecturas_para_hash(x):
            L.append(f"- {l['nombre'] or 'sin nombre'} [{etiqueta(TIPOS_LECTURA, l['tipo'])}{', ' + l['unidad'] if l['unidad'] else ''}]: confirma si {l['queConfirma'] or 'sin criterio'}; refuta si {l['queRefuta'] or 'sin criterio'}; control: {l['control'] or 'sin control declarado'}")
        L.append(f"Hash SHA-256 de las lecturas en orden canónico: {hash_lecturas(x)}")
    else:
        L.append("Lecturas: ninguna declarada; no hay criterio por lectura que congelar.")
    L += _lineas_sistema_y_puente(x)
    return L


def _lineas_sistema_y_puente(x: dict[str, Any]) -> list[str]:
    L: list[str] = []
    s = x["sistema"]
    if s:
        tipo = s.get("tipo") or ""
        info = SISTEMAS_EXPERIMENTALES.get(tipo)
        cabeza = f"Sistema experimental: {etiqueta(SISTEMAS_EXPERIMENTALES, tipo) or 'sin tipo'}" + (f" ({info['definicion']})" if info else "")
        L.append(cabeza)
        L.append(f"  Prueba: {s.get('quePrueba') or 'no declarado'}")
        if s.get("queNoRepresenta"):
            L.append(f"  No representa: {s['queNoRepresenta']}")
        else:
            limite = que_no_representa_por_defecto(tipo)
            L.append("  No representa: no declarado" + (f"; límite general de este sistema: {limite}" if limite else ""))
    else:
        L.append("Sistema experimental: no declarado")
    p = x["propositoBiomarcador"]
    L.append(f"Propósito del biomarcador (BEST): {etiqueta(PROPOSITOS_BIOMARCADOR, p)}. {PROPOSITOS_BIOMARCADOR[p]['definicion']}" if p else "Propósito del biomarcador (BEST): no declarado")
    n = x["nivelDesenlace"]
    L.append(f"Nivel del desenlace: {etiqueta(NIVELES_DESENLACE, n)}. {NIVELES_DESENLACE[n]['definicion']}" if n else "Nivel del desenlace: no declarado")
    L.append(f"Puente al beneficio: {x['puenteAlBeneficio']}" if x["puenteAlBeneficio"] else "Puente al beneficio: no declarado; el resultado, por sí solo, no habla de beneficio para una persona")
    return L


def texto_contrato(experimento: Any) -> str:
    """El contrato en texto para el dossier y la ficha: sistema, lecturas,
    propósito, nivel, puente y los problemas por regla."""
    if not isinstance(experimento, dict) or not experimento:
        return "Sin contrato de experimento."
    x = normalizar_contrato(experimento)
    L = ["Contrato del experimento (qué se mide, en qué sistema y qué significa cada resultado):"]
    L += _lineas_sistema_y_puente(x)
    if x["lecturas"]:
        L.append(f"Lecturas ({len(x['lecturas'])}):")
        for l in x["lecturas"]:
            L.append(f"- {l['nombre'] or 'sin nombre'} [{etiqueta(TIPOS_LECTURA, l['tipo'])}{', ' + l['unidad'] if l['unidad'] else ''}]: confirma si {l['queConfirma'] or 'sin criterio'}; refuta si {l['queRefuta'] or 'sin criterio'}; control: {l['control'] or 'sin control declarado'}")
    else:
        L.append("Lecturas: ninguna declarada.")
    problemas = validar_contrato(experimento)
    L.append("Problemas del contrato por regla: " + ("; ".join(problemas) if problemas else "ninguno") + ".")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Veredicto por lectura, a partir de cifras nombradas
# ---------------------------------------------------------------------------

_NUMERO = re.compile(r"(?<![\w.,])([+\-−–]?)\s?(\d+(?:[.,]\d+)?)\s*(%|por ciento|percent)?")
# Dirección: solo verbos o sustantivos de cambio. "mayor", "menor", "alto" o
# "bajo" son comparativos ("cambio menor del 5 %") y no dicen hacia dónde va.
_SUBE = re.compile(r"\b(aument\w*|sub(?:e|a|en|an|ir|ida|idas|iendo|io)|increment\w*|elev\w*|crec\w*|mas alt\w+|increas\w*|ris(?:e|es|ing)|up-?regul\w*)\b")
_BAJA = re.compile(r"\b(disminu\w*|baj(?:a|e|an|en|ar|ada|adas|ando)|reduc\w*|descen\w*|ca(?:e|en|ida|idas)|mas baj\w+|decreas\w*|reduction|reduced|drop\w*|declin\w*|down-?regul\w*)\b")
_CAMBIO = re.compile(r"\b(cambio\w*|diferencia\w*|variaci\w+|delta|change\w*|difference\w*|variation\w*)\b")
_SIN_CAMBIO = re.compile(r"\b(sin cambio\w*|no cambi\w*|sin diferencia\w*|no difer\w*|no significativ\w*|no change|unchanged|n\.?s\.?)\b")
# Comparadores, escritos con sus tildes; al buscar se comparan sin tildes y en
# minúsculas, igual que el criterio (`_sin_tildes`), así da igual cómo venga
# escrito el criterio y el acentuador no los rompe.
_COMPARADORES_CRUDOS: tuple[tuple[str, str], ...] = (
    (">=", "ge"), ("≥", "ge"), ("=>", "ge"), ("al menos", "ge"), ("como mínimo", "ge"), ("un mínimo de", "ge"), ("mínimo de", "ge"), ("por lo menos", "ge"), ("no menos de", "ge"), ("no menos del", "ge"), ("igual o mayor", "ge"), ("igual o superior", "ge"), ("mayor o igual", "ge"), ("no menor", "ge"), ("at least", "ge"), ("greater than or equal", "ge"), ("no less than", "ge"),
    ("<=", "le"), ("≤", "le"), ("=<", "le"), ("como máximo", "le"), ("un máximo de", "le"), ("máximo de", "le"), ("a lo sumo", "le"), ("como mucho", "le"), ("no más de", "le"), ("no más del", "le"), ("menor o igual", "le"), ("igual o menor", "le"), ("igual o inferior", "le"), ("no mayor", "le"), ("no supera", "le"), ("at most", "le"), ("less than or equal", "le"), ("no more than", "le"),
    (">", "gt"), ("más de", "gt"), ("más del", "gt"), ("mayor que", "gt"), ("mayor a", "gt"), ("mayor del", "gt"), ("por encima de", "gt"), ("por encima del", "gt"), ("superior a", "gt"), ("superior al", "gt"), ("supera", "gt"), ("superan", "gt"), ("encima de", "gt"), ("more than", "gt"), ("greater than", "gt"), ("above", "gt"), ("exceed", "gt"), ("exceeds", "gt"), ("over", "gt"),
    ("<", "lt"), ("menos de", "lt"), ("menos del", "lt"), ("menor que", "lt"), ("menor a", "lt"), ("menor del", "lt"), ("por debajo de", "lt"), ("por debajo del", "lt"), ("inferior a", "lt"), ("inferior al", "lt"), ("debajo de", "lt"), ("less than", "lt"), ("below", "lt"), ("under", "lt"), ("fewer than", "lt"),
)
# Comparadores que van detrás del número («20 % o más», «5 % or less»).
_POSTFIJOS_CRUDOS: tuple[tuple[str, str], ...] = (
    ("o más", "ge"), ("o superior", "ge"), ("o mayor", "ge"), ("en adelante", "ge"), ("or more", "ge"), ("or higher", "ge"), ("or greater", "ge"), ("and above", "ge"),
    ("o menos", "le"), ("o inferior", "le"), ("o menor", "le"), ("or less", "le"), ("or lower", "le"), ("or fewer", "le"), ("and below", "le"),
)


def _patron_comparador(palabra: str) -> re.Pattern[str]:
    """El comparador como palabra entera (sin tildes, minúsculas): «over» no
    cuenta dentro de «recovery» ni «o más» dentro de «cambio más»."""
    p = _sin_tildes(palabra).lower()
    ini = r"(?<!\w)" if p[0].isalnum() else ""
    fin = r"(?!\w)" if p[-1].isalnum() else ""
    return re.compile(ini + re.escape(p) + fin)


_COMPARADORES: tuple[tuple[re.Pattern[str], str], ...] = tuple((_patron_comparador(palabra), op) for palabra, op in _COMPARADORES_CRUDOS)
_POSTFIJOS: tuple[tuple[re.Pattern[str], str], ...] = tuple((_patron_comparador(palabra), op) for palabra, op in _POSTFIJOS_CRUDOS)
# Lo que puede haber entre el comparador y su número («al menos un 20 %»,
# «igual o mayor que 20», «supera los 20», «at least a 20 %»).
_RELLENO = re.compile(r"^(?:[\s:,]*(?:que|a|al|de|del|el|la|los|las|un|una|unos|unas|valor|aproximadamente|unos|the|an|of|by|to|about|around|approximately|roughly)(?!\w))*[\s:,]*$")
# El número que precede a un postfijo, con su porcentaje o una sola palabra
# de unidad («2,5 veces o más», «20 pg/mL or more»).
_NUMERO_FIN = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*(%|por ciento|percent)?(?:\s*[^\d\s%]+)?[\s:,]*$")
_OPERADORES = {"ge": lambda v, u: v >= u, "le": lambda v, u: v <= u, "gt": lambda v, u: v > u, "lt": lambda v, u: v < u}
_SIMBOLO = {"ge": ">=", "le": "<=", "gt": ">", "lt": "<"}


def _numero(texto: str) -> tuple[float | None, int, bool]:
    """(valor con signo explícito, signo explícito -1/0/+1, es porcentaje) del
    primer número del texto; (None, 0, False) si no hay número."""
    m = _NUMERO.search(texto)
    if not m:
        return None, 0, False
    signo = -1 if m.group(1) in ("-", "−", "–") else (1 if m.group(1) == "+" else 0)
    valor = float(m.group(2).replace(",", "."))
    return (-valor if signo < 0 else valor), signo, bool(m.group(3))


def _direccion(texto: str) -> int:
    """+1 si el texto habla de subida, -1 de bajada, 0 si no lo dice o dice las dos."""
    sube, baja = bool(_SUBE.search(texto)), bool(_BAJA.search(texto))
    return 0 if sube == baja else (1 if sube else -1)


def _comparadores(texto: str) -> list[tuple[str, float, bool, int]]:
    """Todos los (operador, umbral, umbral en porcentaje, posición) del texto:
    cada comparador seguido de un número a menos de 30 caracteres (o, en los
    postfijos, precedido por él), en orden de aparición. Un comparador que
    solapa con otro ya registrado no cuenta («=<» y «<», «no más de» y «más
    de», «al menos» y «menos del»): el más largo, que se busca antes, manda."""
    hallados: dict[int, tuple[str, float, bool, int]] = {}
    ocupados: list[tuple[int, int]] = []

    def solapa(ini: int, fin: int) -> bool:
        return any(ini < f and i < fin for i, f in ocupados)

    for patron, op in _COMPARADORES:
        for m in patron.finditer(texto):
            if solapa(m.start(), m.end()):
                continue
            cola = texto[m.end(): m.end() + 30]
            n = _NUMERO.search(cola)
            if n and not n.group(1).strip() and _RELLENO.match(cola[: n.start()]):
                hallados[m.start()] = (op, float(n.group(2).replace(",", ".")), bool(n.group(3)), m.start())
                ocupados.append((m.start(), m.end()))
    # Postfijos: el número va delante («20 % o más»). Se guardan en la posición
    # del número para que el orden de aparición siga siendo el del texto.
    for patron, op in _POSTFIJOS:
        for m in patron.finditer(texto):
            if solapa(m.start(), m.end()):
                continue
            desde = max(0, m.start() - 30)
            n = _NUMERO_FIN.search(texto[desde: m.start()])
            if n:
                pos = desde + n.start()
                if pos not in hallados and not solapa(pos, m.end()):
                    hallados[pos] = (op, float(n.group(1).replace(",", ".")), bool(n.group(2)), pos)
                    ocupados.append((m.start(), m.end()))
    return [hallados[k] for k in sorted(hallados)]


def evaluar_criterio(criterio: Any, valor: Any) -> tuple[bool | None, str]:
    """Si una cifra cumple un criterio escrito, por regla: (True, False o None
    cuando la regla no puede aplicarlo) y el motivo. Entiende un comparador
    con umbral (\"al menos 20 %\", \"p < 0,05\", \"more than 30 %\"), la
    dirección (\"aumenta\", \"reduce\", \"decrease\") y el signo de la cifra
    (\"+35 %\", \"-12 %\", \"reducción del 12 %\"). No compara un porcentaje
    con una cifra sin porcentaje. Lo que no entiende lo dice y devuelve None."""
    c = _sin_tildes(_texto(criterio)).lower()
    v = _sin_tildes(_texto(valor)).lower()
    if not c:
        return None, "no hay criterio escrito"
    if not v:
        return None, "la cifra está vacía"
    n, signo, v_pct = _numero(v)
    dir_valor = signo if signo else _direccion(v)
    valor_sin_cambio = bool(_SIN_CAMBIO.search(v))
    if valor_sin_cambio and n is None:
        n, dir_valor = 0.0, 0
    comps = _comparadores(c)
    dir_crit = _direccion(c)
    # Criterio de ausencia de cambio («sin cambio significativo») frente a una
    # cifra que dice lo mismo («n.s.», «sin cambio»): se cumple sin número.
    if not comps and not dir_crit and _SIN_CAMBIO.search(c) and valor_sin_cambio and (n is None or n == 0):
        return True, "el criterio pide ausencia de cambio y la cifra dice que no hubo cambio"
    if n is None:
        return None, f"la cifra «{_texto(valor)}» no trae un número"
    if comps:
        sin_cambio = n == 0 and valor_sin_cambio
        compatibles = [cp for cp in comps if cp[2] == v_pct or sin_cambio]
        if not compatibles:
            c_pct = comps[0][2]
            return None, f"el criterio está {'en porcentaje' if c_pct else 'sin porcentaje'} y la cifra {'en porcentaje' if v_pct else 'sin porcentaje'}: no se comparan por regla"
        if dir_crit and dir_valor and dir_crit != dir_valor:
            return False, f"la cifra va en la dirección contraria a la del criterio ({'baja' if dir_valor < 0 else 'sube'} cuando el criterio pide que {'suba' if dir_crit > 0 else 'baje'})"
        absoluto = bool(dir_crit) or bool(_CAMBIO.search(c))
        magnitud = abs(n) if absoluto else n
        if dir_crit and dir_valor:
            nota = f" en la dirección pedida ({'subida' if dir_crit > 0 else 'bajada'})"
        elif dir_crit:
            nota = f" (la cifra no trae signo ni dirección: se lee como {'subida' if dir_crit > 0 else 'bajada'}, que es lo que pide el criterio)"
        else:
            nota = " (en valor absoluto: el criterio habla de cambio sin dirección)" if absoluto and n < 0 else ""
        cifra_txt = f"la cifra {magnitud:g}{'%' if v_pct else ''}"
        umbral_txt = lambda cp: f"{_SIMBOLO[cp[0]]} {cp[1]:g}{'%' if cp[2] else ''}"  # noqa: E731
        cumplidos = [cp for cp in compatibles if _OPERADORES[cp[0]](magnitud, cp[1])]
        fallidos = [cp for cp in compatibles if cp not in cumplidos]
        if not fallidos:
            return True, f"{cifra_txt} cumple el umbral {' y '.join(umbral_txt(cp) for cp in compatibles)}" + nota
        if not cumplidos:
            return False, f"{cifra_txt} no cumple el umbral {' ni '.join(umbral_txt(cp) for cp in compatibles)}" + nota
        # Varios umbrales y la cifra cumple unos y no otros: son un rango (los
        # dos hacen falta) salvo que entre ellos haya una «o», que los hace
        # alternativos.
        ini, fin = min(cp[3] for cp in compatibles), max(cp[3] for cp in compatibles)
        alternativo = bool(re.search(r"\s(?:o|u|or|either)\s", c[ini:fin]))
        if alternativo:
            return True, f"{cifra_txt} cumple el umbral {' y '.join(umbral_txt(cp) for cp in cumplidos)} y no {' ni '.join(umbral_txt(cp) for cp in fallidos)}; el criterio los da como alternativos («o»), así que basta uno" + nota
        return False, f"{cifra_txt} cumple el umbral {' y '.join(umbral_txt(cp) for cp in cumplidos)} pero no {' ni '.join(umbral_txt(cp) for cp in fallidos)}; el criterio pide los dos" + nota
    if dir_crit and dir_valor:
        cumple = dir_crit == dir_valor
        return cumple, f"sin umbral en el criterio: la cifra {'sube' if dir_valor > 0 else 'baja'} y el criterio pide que {'suba' if dir_crit > 0 else 'baje'}"
    if dir_crit and n == 0 and _SIN_CAMBIO.search(v):
        return False, "la cifra dice que no hubo cambio y el criterio pide una dirección"
    return None, "el criterio no tiene umbral ni dirección que se pueda aplicar por regla" if not dir_crit else "el criterio pide una dirección y la cifra no trae signo ni dirección"


_CONFIRMA_PAL = re.compile(r"\b(confirm\w*|cumple el criterio de confirmaci\w*|en la direccion predich\w+|direccion y magnitud predich\w+|support(?:s|ed)?|met the confirmation)\b")
_REFUTA_PAL = re.compile(r"\b(refut\w*|cumple el criterio de refutaci\w*|direccion contrari\w+|sin efecto|no hubo efecto|no se observ\w* (?:ningun |el )?efecto|no effect|contrary to)\b")
_INCONCLUSO_PAL = re.compile(r"\b(inconclus\w*|no alcanz\w* (?:la )?potencia|cruza el (?:efecto|umbral|cero)|no permit\w* concluir|inconclusive|underpowered)\b")
# Una negación delante de confirmar, refutar o cumplir («no confirma», «no
# cumple el criterio de confirmación», «did not meet», «failed to confirm»)
# deja la frase en inconcluso: no cumplir la confirmación no es refutar.
_NEGADO = re.compile(r"\b(?:(?:no|ni|sin|nunca|not|nor|never)\s+(?:se\s+|lo\s+|la\s+|did\s+|does\s+)?|fail\w*\s+to\s+)(confirm\w*|refut\w*|cumpl\w*|satisf\w*|alcanz\w*|meet\w*|met\b)")


def _veredicto_en_frase(frase: str) -> str | None:
    f = _sin_tildes(frase).lower()
    if _INCONCLUSO_PAL.search(f):
        return "inconcluso"
    if _NEGADO.search(f):
        return "inconcluso"
    refuta, confirma = bool(_REFUTA_PAL.search(f)), bool(_CONFIRMA_PAL.search(f))
    if refuta and confirma:
        return "inconcluso"
    return "refuta" if refuta else ("confirma" if confirma else None)


def _frases_sobre(texto: str, nombres: list[str]) -> list[str]:
    """Las frases del texto del juez que hablan de la lectura: llevan su nombre
    (o el de una cifra suya) o comparten un símbolo con él (GFAP, NfL), que es
    lo que sobrevive cuando el juez escribe en otro idioma."""
    frases = [f.strip() for f in re.split(r"(?<=[.;!?])\s+|\n", texto) if f.strip()]
    simbolos = set().union(*(_simbolos(n) for n in nombres)) if nombres else set()
    return [f for f in frases if any(_coincide(n, f) for n in nombres if _clave(n)) or (simbolos and simbolos & _simbolos(f))]


def veredicto_por_lecturas(lecturas: Any, cifras_o_resultado: Any, texto_juez: str | None = None) -> list[dict[str, Any]]:
    """Un veredicto por lectura, por regla, a partir de las cifras nombradas
    del resultado: una cifra cuenta para una lectura si su nombre coincide
    con el de la lectura (`_coincide`). Con cifra, se aplican el criterio de
    confirmación y el de refutación (`evaluar_criterio`); si la regla no puede
    aplicarlos, se busca en el texto del juez una frase que hable de esa
    lectura y diga confirma, refuta o inconcluso; si hay una sola lectura y el
    resultado trae veredicto global, esa lectura lo hereda. Sin cifra que la
    nombre, la lectura es no_evaluable: no pude comprobar, no "no hay efecto".

    `cifras_o_resultado` puede ser la lista de cifras ({nombre, valor}, dicts
    u objetos pydantic) o el dict `resultado` del estado, del que se toman
    `cifras`, `veredicto` y los textos (`motivo`, `resultado`, `limitaciones`)
    como texto del juez si no se pasa otro. Cada entrada: lectura, tipo,
    veredicto, motivo y las cifras que se usaron."""
    if isinstance(lecturas, dict):
        lecturas = normalizar_contrato(lecturas)["lecturas"]
    lista = [l for l in (_lectura_limpia(v) for v in (lecturas if isinstance(lecturas, list) else [])) if l]
    es_resultado = (isinstance(cifras_o_resultado, dict) and not ("nombre" in cifras_o_resultado and "valor" in cifras_o_resultado)) or (not isinstance(cifras_o_resultado, (dict, list)) and hasattr(cifras_o_resultado, "cifras"))
    if es_resultado:
        resultado = cifras_o_resultado
        cifras_crudas = _campo(resultado, "cifras", por_defecto=[]) or []
        global_ = _texto(_campo(resultado, "veredicto")) or None
        if texto_juez is None:
            texto_juez = " ".join(_texto(_campo(resultado, k)) for k in ("resultado", "motivo", "limitaciones"))
    else:
        cifras_crudas = cifras_o_resultado if isinstance(cifras_o_resultado, list) else ([cifras_o_resultado] if cifras_o_resultado else [])
        global_ = None
    cifras = [(_texto(_campo(c, "nombre")), _texto(_campo(c, "valor"))) for c in cifras_crudas if c is not None]
    cifras = [(n, v) for n, v in cifras if n]
    texto_juez = _texto(texto_juez)
    # Primer paso: la cifra lleva el nombre de la lectura. Segundo paso, solo
    # para las lecturas que se quedaron sin cifra y con las cifras que ninguna
    # lectura reclamó: comparten un símbolo (GFAP, TREM2), que es lo que
    # sobrevive cuando la lectura está en castellano y la cifra en inglés.
    # Una cifra que nombra a varias lecturas («GFAP» con «GFAP en plasma» y
    # «GFAP en LCR») es ambigua: no se asigna a ninguna y se dice, salvo que
    # coincida exactamente con una sola.
    nombres = [l["nombre"] or "medida principal" for l in lista]
    formas = [_forma(nombre) for nombre in nombres]
    estrictas: list[list[tuple[str, str]]] = [[] for _ in nombres]
    ambiguas: list[list[str]] = [[] for _ in nombres]
    reclamadas: set[str] = set()
    for n, v in cifras:
        fn = _forma(n)
        idxs = [i for i, forma in enumerate(formas) if _coincide_formas(forma, fn)]
        if len(idxs) > 1:
            exactas = [i for i in idxs if formas[i][0] == fn[0]]
            idxs = exactas if len(exactas) == 1 else idxs
        if len(idxs) == 1:
            estrictas[idxs[0]].append((n, v))
            reclamadas.add(n)
        elif idxs:
            for i in idxs:
                ambiguas[i].append(n)
            reclamadas.add(n)  # tampoco entra al emparejamiento por símbolo
    libres = [(n, v) for n, v in cifras if n not in reclamadas]
    # Segundo paso: una cifra libre va a la única lectura sin cifra con la que
    # comparte un símbolo; si lo comparte con varias, también es ambigua.
    simbolos_sin_cifra = [_simbolos(nombre) if not estrictas[i] else set() for i, nombre in enumerate(nombres)]
    por_simbolo: list[list[tuple[str, str]]] = [[] for _ in nombres]
    for n, v in libres:
        s = _simbolos(n)
        idxs = [i for i, sl in enumerate(simbolos_sin_cifra) if sl and s & sl]
        if len(idxs) == 1:
            por_simbolo[idxs[0]].append((n, v))
        else:
            for i in idxs:
                ambiguas[i].append(n)
    salida: list[dict[str, Any]] = []
    for i, (l, nombre) in enumerate(zip(lista, nombres)):
        propias = estrictas[i] or por_simbolo[i]
        emparejada_por_simbolo = not estrictas[i] and bool(por_simbolo[i])
        entrada = {"lectura": nombre, "tipo": l["tipo"], "veredicto": "no_evaluable", "motivo": "", "cifras": [f"{n} = {v}" for n, v in propias]}
        if not propias:
            motivo = f"ninguna cifra del resultado lleva el nombre de la lectura «{nombre}»: no pude comprobar esta lectura"
            if ambiguas[i]:
                otras = sorted({nombres[j] for j, amb in enumerate(ambiguas) if j != i and set(amb) & set(ambiguas[i])})
                motivo = f"la cifra «{'», «'.join(sorted(set(ambiguas[i])))}» podría corresponder a esta lectura o a {', '.join('«' + o + '»' for o in otras) or 'otra'} y no se asigna a ninguna: no pude comprobar esta lectura"
            elif not cifras:
                motivo += " (el resultado no trae cifras)"
            if global_ and len(lista) == 1:
                motivo += f"; el juez dio un veredicto global ({global_}) pero no se comprueba por lectura sin una cifra que la nombre"
            entrada["motivo"] = motivo
            salida.append(entrada)
            continue
        veredicto, motivo = _decidir_con_cifras(l, propias)
        if emparejada_por_simbolo:
            motivo = f"la cifra se emparejó por el símbolo compartido ({', '.join(sorted(_simbolos(nombre) & {s for n, _ in propias for s in _simbolos(n)}))}), no por el nombre completo; " + motivo
        if veredicto is None:
            frases = _frases_sobre(texto_juez, [nombre] + [n for n, _ in propias]) if texto_juez else []
            dichos = [(f, _veredicto_en_frase(f)) for f in frases]
            dichos = [(f, d) for f, d in dichos if d]
            if dichos:
                distintos = {d for _, d in dichos}
                veredicto = dichos[0][1] if len(distintos) == 1 else "inconcluso"
                motivo += "; " + (f"el juez dice de esta lectura: «{dichos[0][0][:160]}»" if len(distintos) == 1 else "el juez dice cosas distintas de esta lectura en frases distintas")
            elif global_ and len(lista) == 1 and global_ in ("confirma", "refuta", "inconcluso", "no_evaluable"):
                veredicto, motivo = global_, motivo + f"; única lectura: hereda el veredicto global del juez ({global_})"
            else:
                veredicto, motivo = "inconcluso", motivo + "; hay cifra pero ni la regla ni el texto del juez la deciden: hace falta lectura humana"
        entrada["veredicto"], entrada["motivo"] = veredicto, motivo
        salida.append(entrada)
    return salida


def _decidir_con_cifras(l: dict[str, Any], propias: list[tuple[str, str]]) -> tuple[str | None, str]:
    """Aplica los dos criterios a las cifras de la lectura. Decide con la
    primera cifra a la que la regla puede aplicar algún criterio; si dos
    cifras deciden distinto, inconcluso."""
    decisiones: list[tuple[str, str]] = []
    motivos_sin_regla: list[str] = []
    for n, v in propias:
        c_ok, c_motivo = evaluar_criterio(l["queConfirma"], v)
        r_ok, r_motivo = evaluar_criterio(l["queRefuta"], v)
        if c_ok is None and r_ok is None:
            motivos_sin_regla.append(f"«{n} = {v}»: confirmación: {c_motivo}; refutación: {r_motivo}")
            continue
        if c_ok and r_ok:
            decisiones.append(("inconcluso", f"«{n} = {v}» cumple los dos criterios a la vez: se solapan ({c_motivo}; {r_motivo})"))
        elif c_ok:
            decisiones.append(("confirma", f"«{n} = {v}» cumple el criterio de confirmación ({c_motivo})" + (f"; el de refutación no se pudo aplicar por regla ({r_motivo})" if r_ok is None else "")))
        elif r_ok:
            decisiones.append(("refuta", f"«{n} = {v}» cumple el criterio de refutación ({r_motivo})" + (f"; el de confirmación no se pudo aplicar por regla ({c_motivo})" if c_ok is None else "")))
        else:
            pendiente = " ni el de refutación" if r_ok is False else ""
            decisiones.append(("inconcluso", f"«{n} = {v}» no cumple el criterio de confirmación{pendiente} ({c_motivo}; {r_motivo})" if c_ok is False else f"«{n} = {v}» no cumple el criterio de refutación ({r_motivo}; confirmación: {c_motivo})"))
    if not decisiones:
        return None, "la regla no pudo aplicar los criterios a las cifras: " + " | ".join(motivos_sin_regla)
    distintos = {d for d, _ in decisiones}
    if len(distintos) == 1:
        return decisiones[0][0], "; ".join(m for _, m in decisiones)
    return "inconcluso", "las cifras de esta lectura deciden distinto: " + "; ".join(f"{d} porque {m}" for d, m in decisiones)


# ---------------------------------------------------------------------------
# La lectura del negativo en dos ramas
# ---------------------------------------------------------------------------


def lectura_del_negativo(veredictos: Any) -> dict[str, Any]:
    """Qué dice un negativo, según las lecturas separadas (informe, página 12):

    - diana_comprometida_sin_efecto: la lectura de compromiso de diana confirma
      y las de efecto refutan. El negativo cuestiona el mecanismo de la
      hipótesis: la intervención hizo lo que debía en la diana y el efecto
      predicho no apareció.
    - diana_no_comprometida: la lectura de compromiso de diana refuta. El
      negativo habla de la actividad del compuesto, de la exposición o del
      ensayo; la hipótesis queda sin probar.
    - sin_lecturas_separadas: no hay lectura de compromiso de diana aparte del
      efecto, así que las dos ramas no se distinguen.
    - None: no es un negativo (el efecto apareció), o el compromiso o el efecto
      quedaron inconclusos o sin evaluar (no pude comprobar la rama).

    Devuelve {"rama": ..., "explicacion": ...} con la explicación en castellano."""
    lista = [v for v in (veredictos if isinstance(veredictos, list) else []) if isinstance(v, dict)]
    if not lista:
        return {"rama": None, "explicacion": "sin veredictos por lectura: no hay nada que leer"}
    ver = lambda v: _texto(v.get("veredicto")).lower()  # noqa: E731
    nom = lambda v: _texto(v.get("lectura")) or "sin nombre"  # noqa: E731
    tipo = lambda v: _clave_vocabulario(v.get("tipo"), TIPOS_LECTURA)[0]  # noqa: E731
    compromiso = [v for v in lista if tipo(v) == "compromiso_diana"]
    efecto = [v for v in lista if tipo(v) in TIPOS_EFECTO]
    viabilidad_falla = [nom(v) for v in lista if tipo(v) == "viabilidad" and ver(v) == "refuta"]
    nota_viabilidad = f" Además falló la viabilidad ({', '.join(viabilidad_falla)}): parte de lo observado puede ser toxicidad." if viabilidad_falla else ""
    ef_confirma = [nom(v) for v in efecto if ver(v) == "confirma"]
    ef_refuta = [nom(v) for v in efecto if ver(v) == "refuta"]
    ef_otros = [f"{nom(v)} {ver(v) or 'sin veredicto'}" for v in efecto if ver(v) not in ("confirma", "refuta")]

    # Primero: ¿hay un negativo que leer? Si el efecto apareció no lo hay; si
    # el efecto quedó sin decidir, no pude comprobarlo.
    if ef_confirma:
        return {"rama": None, "explicacion": f"no es un negativo: el efecto apareció ({', '.join(ef_confirma)})." + nota_viabilidad}
    if not efecto and not compromiso:
        cuales = ", ".join(f"{nom(v)} ({etiqueta(TIPOS_LECTURA, tipo(v)) or 'sin tipo'})" for v in lista)
        return {"rama": None, "explicacion": f"no hay lectura de efecto ni de compromiso de diana (solo {cuales}): no hay negativo que leer." + nota_viabilidad}
    if not compromiso:
        if ef_refuta:
            parcial = f" El negativo es parcial: {', '.join(ef_otros)}." if ef_otros else ""
            return {"rama": "sin_lecturas_separadas", "explicacion": f"el experimento no separó la lectura de compromiso de diana de la del efecto ({', '.join(ef_refuta)} refuta): un negativo así no distingue si la diana no se tocó o si se tocó y no pasó nada.{parcial}" + nota_viabilidad}
        return {"rama": None, "explicacion": f"el efecto quedó sin decidir ({', '.join(ef_otros)}): no pude comprobar si hay un negativo." + nota_viabilidad}
    comp_confirma = [nom(v) for v in compromiso if ver(v) == "confirma"]
    comp_refuta = [nom(v) for v in compromiso if ver(v) == "refuta"]
    if comp_refuta and not comp_confirma:
        return {"rama": "diana_no_comprometida", "explicacion": f"la diana no se comprometió ({', '.join(comp_refuta)} refuta): el negativo habla de la actividad del compuesto, de la exposición o del ensayo, no del mecanismo; la hipótesis queda sin probar." + nota_viabilidad}
    if comp_refuta and comp_confirma:
        return {"rama": None, "explicacion": f"las lecturas de compromiso de diana se contradicen ({', '.join(comp_confirma)} confirma; {', '.join(comp_refuta)} refuta): no pude comprobar en qué rama cae el negativo." + nota_viabilidad}
    if not comp_confirma:
        pendientes = ", ".join(f"{nom(v)} {ver(v) or 'sin veredicto'}" for v in compromiso)
        return {"rama": None, "explicacion": f"la lectura de compromiso de diana no decide ({pendientes}): no pude comprobar en qué rama cae el negativo." + nota_viabilidad}
    if not efecto:
        return {"rama": None, "explicacion": f"la diana se comprometió ({', '.join(comp_confirma)} confirma) pero no hay lectura de efecto que decir si el mecanismo respondió." + nota_viabilidad}
    if ef_refuta and not ef_otros:
        return {"rama": "diana_comprometida_sin_efecto", "explicacion": f"la diana se comprometió ({', '.join(comp_confirma)} confirma) y el efecto no apareció ({', '.join(ef_refuta)} refuta): el negativo cuestiona el mecanismo de la hipótesis, no el ensayo." + nota_viabilidad}
    if ef_refuta:
        return {"rama": None, "explicacion": f"la diana se comprometió ({', '.join(comp_confirma)} confirma), parte del efecto refuta ({', '.join(ef_refuta)}) y parte no decide ({', '.join(ef_otros)}): el negativo es parcial y no se lee en una sola rama." + nota_viabilidad}
    return {"rama": None, "explicacion": f"la diana se comprometió ({', '.join(comp_confirma)} confirma) pero el efecto quedó sin decidir ({', '.join(ef_otros)}): no es un negativo interpretable." + nota_viabilidad}


def texto_lectura_del_negativo(veredictos: Any) -> str:
    """Una línea para el dossier o la ficha, con la rama por su nombre y su explicación."""
    r = lectura_del_negativo(veredictos)
    nombres = {"diana_comprometida_sin_efecto": "Diana comprometida sin efecto (cuestiona el mecanismo)", "diana_no_comprometida": "Diana no comprometida (actividad, exposición o ensayo)", "sin_lecturas_separadas": "Sin lecturas separadas"}
    return f"{nombres.get(r['rama'], 'Sin rama')}: {r['explicacion']}"
