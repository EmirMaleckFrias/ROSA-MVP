"""Las firmas DSPy de Rosa: que entra y que sale en cada paso del bucle.

Una firma (`dspy.Signature`) declara los campos de entrada y salida y, en
su docstring, la tarea. DSPy construye el prompt; GEPA lo optimiza despues
con la evidencia de la metrica. Por eso aqui no hay prompts largos: hay
contratos. Los nombres de los campos estan en espanol porque el modelo los
lee y la investigadora tambien.

Los modelos se eligen por rol al ejecutar (`dspy.context(lm=...)`):
- cerebro (GPT-6 Astra): plan, consultas, modelo de mundo, hipotesis, meta.
- volumen (Sonnet 5): extraccion de afirmaciones, triaje.
- juez (Opus 5): verificacion, comparacion por pares, revision.
"""

from __future__ import annotations

from typing import Literal

import dspy
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Tipos de salida
# ---------------------------------------------------------------------------


class PasoPropuesto(BaseModel):
    titulo: str = Field(description="Que se hace, en una linea")
    detalle: str = Field(description="Como, en una o dos lineas")
    tipo: Literal["literatura", "ensayos", "extraccion", "verificacion", "novedad", "modelo", "hipotesis", "meta"] = Field(description="Que herramienta de Rosa ejecuta el paso")
    presupuesto: int = Field(description="Llamadas al modelo que se permite gastar", ge=1, le=80)


class Consulta(BaseModel):
    base: Literal["pubmed", "europepmc", "preprints"]
    consulta: str = Field(description="La cadena exacta que se envia a la base, con operadores booleanos")
    tema: str = Field(description="Tema corto al que sirve la consulta")


class AfirmacionExtraida(BaseModel):
    texto: str = Field(description="Una afirmacion factual autocontenida, tal como la sostiene la fuente")
    fragmento: str = Field(description="Cita literal de la fuente que la respalda, copiada sin cambios (maximo 40 palabras)")
    tipo: Literal["dato", "literatura", "interpretacion"] = Field(description="dato si es una cifra o medida; literatura si es lo que la fuente afirma; interpretacion si es lectura de Rosa")
    tema: str


class VeredictoJuez(BaseModel):
    veredicto: Literal["sostenida", "parcial", "no_sostenida"]
    motivo: str = Field(description="Una linea: que sostiene el fragmento y que no")
    entidad_distinta: bool = Field(description="True si el dato es real pero de otra entidad (otro farmaco, cohorte, estudio, poblacion)")


class HechoPropuesto(BaseModel):
    enunciado: str
    tema: str
    tipo: Literal["hecho", "pregunta"]
    prioridad: int = Field(ge=1, le=9, description="1 es lo mas urgente")
    afirmaciones: list[int] = Field(description="Indices de las afirmaciones sostenidas que lo respaldan; vacio si es pregunta")


class HipotesisPropuesta(BaseModel):
    titulo: str = Field(description="Una linea, con las entidades concretas")
    enunciado: str = Field(description="Que se espera observar y en quien, falsable")
    mecanismo: str
    biomarcador: str = Field(description="Que se mediria")
    cohorte: str = Field(description="En que cohorte o poblacion")
    diseno: str = Field(description="Diseno del estudio que la comprobaria")
    cluster: str = Field(description="Familia tematica, dos o tres palabras")
    justificacion: str = Field(description="Por que importa para el objetivo, dos lineas")
    afirmaciones: list[int] = Field(description="Indices de las afirmaciones sostenidas que la motivan")
    supuestos: list[str] = Field(description="Supuestos que tendrian que ser ciertos, uno por linea")
    entidades_novedad: list[str] = Field(description="Simbolos de gen o proteina y terminos para comprobar novedad (Open Targets, ensayos)")
    derivada_de: str | None = Field(description="Id de la hipotesis previa de la que deriva, o null")


class Comparacion(BaseModel):
    mejor: Literal["A", "B"]
    eje: Literal["correccion", "utilidad", "especificidad", "novedad", "deseabilidad"] = Field(description="El criterio que decidio")
    resumen: str = Field(description="Dos lineas de debate: que tiene una que no tiene la otra")


class Debilidad(BaseModel):
    texto: str = Field(description="La debilidad, como criterio de revision que se podria inyectar")
    hipotesis: list[str] = Field(description="Ids de las hipotesis afectadas")


class Direccion(BaseModel):
    titulo: str
    razon: str
    hallazgos: list[str]
    que_investigar: list[str]
    idea_ejemplo: str
    inesperada: bool
    hipotesis: list[str] = Field(description="Ids de hipotesis relacionadas")


class RevisionInicial(BaseModel):
    pasa: bool = Field(description="False si la hipotesis tiene un fallo evidente de correccion, seguridad o trivialidad")
    resumen: str
    supuestos: list[str] = Field(description="Supuestos descompuestos, independientes de las citas")


class SupuestoEvaluado(BaseModel):
    estado: Literal["respaldado", "plausible", "sin_evidencia", "contradicho"]
    evidencia: str = Field(description="Que afirmacion o fuente lo respalda o contradice; 'ninguna' si no hay")


# ---------------------------------------------------------------------------
# Firmas
# ---------------------------------------------------------------------------


class ProponerPlan(dspy.Signature):
    """Proponer el plan de la siguiente iteracion de una investigacion sobre Alzheimer.
    Entre 4 y 7 pasos, cada uno ejecutable por una herramienta de Rosa, en orden:
    literatura o ensayos primero, extraccion y verificacion despues, novedad si hay
    hipotesis, actualizar el modelo de mundo, generar o refinar hipotesis, y meta-revision
    solo cada varias iteraciones. Los pasos sirven a las preguntas abiertas del modelo de
    mundo y a las indicaciones humanas; no repiten lo que ya esta sabido. Cuando hay
    hipotesis vivas, se eligen las acciones por lo que discriminan entre ellas: buscar la
    evidencia que subiria o bajaria su certeza o cambiaria su direccion (lo mas fragil de
    cada una), no la que solo confirmaria la favorita."""

    objetivo: str = dspy.InputField()
    relevancia: str = dspy.InputField(desc="Que cuenta como relevante para la investigadora")
    limites: str = dspy.InputField(desc="Lo que no se hace")
    condicion_parada: str = dspy.InputField()
    modelo_de_mundo: str = dspy.InputField(desc="Hechos sabidos, preguntas abiertas y descartes, con prioridad")
    resumen_iteracion_anterior: str = dspy.InputField(desc="Vacio en la primera iteracion")
    indicaciones_humanas: str = dspy.InputField(desc="Lo que pidio la investigadora, si algo")
    hipotesis_vivas: str = dspy.InputField(desc="Las hipotesis en competencia con su certeza, direccion, lo mas fragil y que las subiria o bajaria")
    numero_iteracion: int = dspy.InputField()
    plan: list[PasoPropuesto] = dspy.OutputField()


class GenerarConsultas(dspy.Signature):
    """Escribir consultas de busqueda bibliografica precisas para las preguntas abiertas y
    para discriminar entre las hipotesis vivas (la evidencia que subiria o bajaria su
    certeza, incluida la que las contradiria). Entre 2 y 5 consultas, cada una a una base
    (PubMed con sintaxis de PubMed, Europe PMC o preprints), con operadores booleanos y
    sinonimos; ninguna repite consultas ya hechas."""

    objetivo: str = dspy.InputField()
    preguntas_abiertas: str = dspy.InputField()
    hipotesis_vivas: str = dspy.InputField(desc="Las hipotesis en competencia con lo que las subiria o bajaria")
    consultas_previas: str = dspy.InputField(desc="Cadenas ya enviadas en esta corrida, para no repetirlas")
    indicaciones_humanas: str = dspy.InputField()
    consultas: list[Consulta] = dspy.OutputField()


class PuntuarRelevancia(dspy.Signature):
    """Puntuar de 0 a 10 cuanto ayuda este articulo a responder las preguntas abiertas.
    0 es nada; 10 es evidencia directa. Un articulo de otra enfermedad, otra molecula
    u otra poblacion puntua bajo aunque comparta palabras."""

    preguntas_abiertas: str = dspy.InputField()
    titulo: str = dspy.InputField()
    resumen: str = dspy.InputField()
    puntuacion: int = dspy.OutputField(ge=0, le=10)
    motivo: str = dspy.OutputField(desc="Una linea")


class ExtraerAfirmaciones(dspy.Signature):
    """Extraer las afirmaciones factuales relevantes de un fragmento de una fuente.
    Cada afirmacion se apoya en una cita literal copiada del fragmento, sin parafrasear
    y sin cruzar de fragmento. No se anade nada que el fragmento no diga ni se inventan
    cifras. Si el fragmento no dice nada relevante, la lista va vacia."""

    preguntas_abiertas: str = dspy.InputField()
    referencia: str = dspy.InputField(desc="Referencia corta de la fuente")
    localizador: str = dspy.InputField(desc="Pagina, seccion o 'resumen'")
    fragmento: str = dspy.InputField()
    afirmaciones: list[AfirmacionExtraida] = dspy.OutputField()


class JuzgarAfirmacion(dspy.Signature):
    """Juzgar si el fragmento citado sostiene la afirmacion. `sostenida` si el fragmento
    la respalda tal como esta escrita; `parcial` si respalda una parte o con matices que
    la afirmacion omite; `no_sostenida` si no la respalda o la contradice. Si el dato es
    real pero corresponde a otra entidad (otro farmaco, cohorte, estudio o poblacion que
    aparece en el fragmento o en su encabezado), es `no_sostenida` con entidad_distinta.
    Las comparaciones explicitas entre entidades estan exentas."""

    pregunta: str = dspy.InputField(desc="La pregunta o tema al que sirve la afirmacion")
    afirmacion: str = dspy.InputField()
    fragmento: str = dspy.InputField(desc="El texto citado, con su encabezado")
    pistas: str = dspy.InputField(desc="Cifras e identificadores encontrados o ausentes en el fragmento, ya normalizados")
    veredicto: VeredictoJuez = dspy.OutputField()


class ActualizarModeloDeMundo(dspy.Signature):
    """Actualizar el modelo de mundo con las afirmaciones sostenidas de la iteracion.
    Proponer hechos nuevos (solo con respaldo en afirmaciones sostenidas, indicando cuales)
    y preguntas abiertas nuevas o repriorizadas. Nada de lo que ya esta en el modelo se
    repite. Lo que la fuente dice va como hecho; lo que Rosa infiere va como pregunta."""

    objetivo: str = dspy.InputField()
    modelo_de_mundo: str = dspy.InputField()
    afirmaciones_sostenidas: str = dspy.InputField(desc="Numeradas, con su cita")
    hechos: list[HechoPropuesto] = dspy.OutputField()


class GenerarHipotesis(dspy.Signature):
    """Generar entre 1 y 3 hipotesis nuevas, falsables y especificas, que respondan a las
    preguntas abiertas con mayor prioridad usando solo afirmaciones sostenidas. Cada una
    con mecanismo, biomarcador, cohorte y diseno de comprobacion. No repetir hipotesis ya
    propuestas ni descartadas (se listan con su motivo de descarte). Si una deriva de una
    aceptada o refinar, se indica. Los criterios de revision son restricciones."""

    objetivo: str = dspy.InputField()
    configuracion: str = dspy.InputField(desc="Preferencias, atributos y restricciones de la investigadora")
    modelo_de_mundo: str = dspy.InputField()
    afirmaciones_sostenidas: str = dspy.InputField(desc="Numeradas, con su cita")
    hipotesis_existentes: str = dspy.InputField(desc="Con id, estado y motivo de descarte o nota de refinar")
    criterios_revision: str = dspy.InputField()
    hipotesis: list[HipotesisPropuesta] = dspy.OutputField()


class RevisarInicial(dspy.Signature):
    """Revision inicial de una hipotesis sin herramientas: correccion evidente, trivialidad,
    seguridad y si es comprobable. Descomponer sus supuestos en frases independientes."""

    objetivo: str = dspy.InputField()
    hipotesis: str = dspy.InputField(desc="Titulo, enunciado, mecanismo y comprobacion")
    criterios_revision: str = dspy.InputField()
    revision: RevisionInicial = dspy.OutputField()


class EvaluarSupuesto(dspy.Signature):
    """Evaluar un supuesto de una hipotesis contra las afirmaciones sostenidas disponibles.
    `respaldado` solo si una afirmacion lo sostiene directamente; `contradicho` si alguna
    lo niega; `plausible` si es consistente pero sin evidencia directa; `sin_evidencia` si
    nada aplica. No inventar evidencia."""

    supuesto: str = dspy.InputField()
    afirmaciones_sostenidas: str = dspy.InputField()
    evaluacion: SupuestoEvaluado = dspy.OutputField()


class CompararHipotesis(dspy.Signature):
    """Comparar dos hipotesis para el mismo objetivo y decidir cual es mejor, como en un
    debate cientifico de tres turnos resumido: correccion frente a la evidencia, utilidad
    para el objetivo, especificidad (falsable, con biomarcador y cohorte), novedad frente
    al modelo de mundo y deseabilidad (que la investigadora quiera comprobarla). Se
    indica el eje decisivo. Las revisiones humanas pesan mas que las automaticas."""

    objetivo: str = dspy.InputField()
    hipotesis_a: str = dspy.InputField()
    hipotesis_b: str = dspy.InputField()
    evidencia: str = dspy.InputField(desc="Afirmaciones sostenidas y hechos relevantes")
    revisiones_humanas: str = dspy.InputField(desc="Lo que dijeron las personas sobre A y B, si algo")
    comparacion: Comparacion = dspy.OutputField()


class MetaRevisar(dspy.Signature):
    """Meta-revision: leer las hipotesis y sus revisiones y encontrar debilidades
    recurrentes (patrones, no casos aislados), escritas como criterios de revision que
    se puedan inyectar. Tambien sintetizar el panorama: entre 2 y 4 direcciones de
    investigacion con hallazgos, que investigar y una idea ejemplo cada una."""

    objetivo: str = dspy.InputField()
    hipotesis: str = dspy.InputField(desc="Todas, con id, estado, elo, afirmaciones y revisiones")
    modelo_de_mundo: str = dspy.InputField()
    debilidades: list[Debilidad] = dspy.OutputField()
    direcciones: list[Direccion] = dspy.OutputField()


class AclararHipotesis(dspy.Signature):
    """La investigadora marco la hipotesis como 'no puedo juzgar' con una nota. Reescribir
    lo que falta para que se pueda juzgar: contexto, que es inferencia de Rosa y que es
    literal de la fuente, y que comprobacion concreta zanjaria la duda. Sin anadir
    afirmaciones nuevas sin cita."""

    hipotesis: str = dspy.InputField()
    nota: str = dspy.InputField()
    afirmaciones: str = dspy.InputField(desc="Las afirmaciones de la hipotesis con su veredicto")
    aclaracion: str = dspy.OutputField()


class ResponderComentarios(dspy.Signature):
    """Responder a los comentarios de la investigadora sobre una hipotesis, punto por punto,
    diciendo que se cambia, que se mantiene y por que, citando las afirmaciones cuando aplica."""

    hipotesis: str = dspy.InputField()
    comentarios: str = dspy.InputField()
    afirmaciones: str = dspy.InputField()
    respuesta: str = dspy.OutputField()
    enunciado_revisado: str = dspy.OutputField(desc="El enunciado tras atender los comentarios; igual al original si no cambia")


class ResumirIteracion(dspy.Signature):
    """Resumir la iteracion en tres o cuatro lineas para la investigadora y para la siguiente
    iteracion: que se busco, que se sostuvo, que entro al modelo de mundo, que hipotesis
    hay en la cola y que quedo sin poder comprobar."""

    plan_ejecutado: str = dspy.InputField(desc="Pasos con su estado y resumen de pistas")
    cambios_modelo_de_mundo: str = dspy.InputField()
    hipotesis_nuevas: str = dspy.InputField()
    sin_comprobar: str = dspy.InputField()
    resumen: str = dspy.OutputField()


class Termino(BaseModel):
    termino: str
    explicacion: str = Field(description="Una frase, sin otra jerga dentro")


class ResumenLlano(BaseModel):
    titulo: str = Field(description="La pregunta de la iteracion, como pregunta, en una linea")
    mensajes_clave: list[str] = Field(description="Dos o tres frases. La primera responde a la pregunta con el verbo de la certeza (indica / probablemente / puede que / no esta claro) y dice que no se pudo comprobar; la ultima dice que toca ahora. Sin recomendaciones clinicas")
    que_buscaba: str = Field(description="Una o dos frases")
    que_hizo: str = Field(description="Que fuentes consulto y cuantos resultados, cuantas afirmaciones verifico y con que veredicto, que fuentes no respondieron")
    que_encontro: list[str] = Field(description="Entre 2 y 5 frases cortas, una por hallazgo, sin siglas sin explicar; las cifras con su denominador")
    limitaciones: str = Field(description="Por que hay que fiarse solo hasta cierto punto, en llano: una sola cohorte, muestras pequenas, otro biomarcador, etc.")
    cambios: list[str] = Field(description="Que hipotesis subieron o bajaron de certeza o cambiaron de direccion respecto a la iteracion anterior, con motivo. Vacio en la primera iteracion o si nada cambio")
    que_propone: list[str] = Field(description="Una frase por hipotesis, con la forma 'Si X, entonces Y'. Vacio si no hubo hipotesis nuevas")
    que_falta: str = Field(description="Que no se pudo comprobar o que evidencia falta, en una o dos frases")
    que_te_toca: str = Field(description="Que decision o accion espera a la persona, en una frase")
    terminos: list[Termino] = Field(description="Cada termino tecnico usado arriba, explicado en una frase")


class ExplicarEnLlano(dspy.Signature):
    """Escribir el resumen de la iteracion con la estructura de un resumen en lenguaje
    llano de Cochrane: titulo como pregunta, mensajes clave primero, que buscaba, que hizo,
    que encontro, limitaciones de la evidencia, que cambio, que propone, que falta y que le
    toca a la persona. Lenguaje corriente: frases de unas 20 palabras, voz activa, sin
    siglas sin explicar, cifras con denominador ("de 100 personas..."), sin la palabra
    "significativo", sin recomendaciones clinicas, sin "demuestra" ni "confirma". Los
    verbos siguen la certeza: alta "indica", moderada "probablemente", baja "puede que",
    muy baja "no esta claro si". Ausencia de evidencia no es evidencia de ausencia; una
    fuente que no respondio se dice como "no pudimos comprobar". Cada termino tecnico se
    explica en el glosario en una frase. No se anade nada que no este en el material."""

    objetivo: str = dspy.InputField()
    resumen_tecnico: str = dspy.InputField(desc="El resumen de la iteracion tal como lo escribio Rosa")
    hechos_nuevos: str = dspy.InputField()
    hipotesis_nuevas: str = dspy.InputField(desc="Titulo, enunciado y para que sirve, de cada una")
    sin_comprobar: str = dspy.InputField()
    conclusiones: str = dspy.InputField(desc="Certeza y direccion de cada hipotesis de la investigacion, y su cambio respecto a la iteracion anterior")
    busqueda: str = dspy.InputField(desc="Fuentes consultadas con resultados, afirmaciones verificadas por veredicto, fuentes que no respondieron")
    resumen: ResumenLlano = dspy.OutputField()


class HipotesisEnLlano(dspy.Signature):
    """Explicar una hipotesis cientifica a alguien que no es medico ni cientifico, en tres
    o cuatro frases: que se cree que pasa, en quien, como se comprobaria y por que
    importaria. Lenguaje corriente, cada termino tecnico explicado entre parentesis la
    primera vez. Sin anadir certeza que la hipotesis no tiene: es algo por comprobar."""

    titulo: str = dspy.InputField()
    enunciado: str = dspy.InputField()
    mecanismo: str = dspy.InputField()
    comprobacion: str = dspy.InputField()
    relevancia: str = dspy.InputField()
    explicacion: str = dspy.OutputField()


class ExperimentoPropuesto(BaseModel):
    protocolo: str = Field(description="Pasos numerados del experimento o analisis, concretos: poblacion, mediciones, tiempos, comparacion")
    ensayo: str = Field(description="Que se mide y con que tecnica (por ejemplo inmunoensayo de GFAP en plasma, PET de amiloide)")
    resultado_que_confirma: str = Field(description="Que valor o patron confirmaria la hipotesis")
    resultado_que_refuta: str = Field(description="Que valor o patron la refutaria")
    coste_estimado: str = Field(description="Orden de magnitud en tiempo y dinero, con el supuesto que lo justifica; 'no estimable' si no hay base")
    analisis_pedido: str = Field(description="Si se puede comprobar con datos ya existentes (ADNI, A4, BIOCARD), que analisis exacto se pediria; vacio si hace falta un experimento nuevo")


class ProponerExperimento(dspy.Signature):
    """Disenar el experimento o analisis que comprobaria la hipotesis: protocolo en pasos,
    que se mide y como, que resultado la confirma y cual la refuta, coste estimado y, si
    existen datos publicos que sirvan, el analisis exacto que se pediria. Concreto y
    realista; sin inventar cohortes ni tecnicas. Si algo no se puede estimar, se dice."""

    hipotesis: str = dspy.InputField(desc="Titulo, enunciado, mecanismo y comprobacion propuesta")
    afirmaciones: str = dspy.InputField(desc="Las afirmaciones sostenidas que la motivan, con su cita")
    limites: str = dspy.InputField(desc="Restricciones de la investigacion (por ejemplo solo humanos, sin datos de pacientes)")
    experimento: ExperimentoPropuesto = dspy.OutputField()


class FactorCerteza(BaseModel):
    factor: Literal["riesgo_de_sesgo", "inconsistencia", "evidencia_indirecta", "imprecision", "sesgo_de_publicacion", "efecto_grande", "gradiente", "replicacion_independiente"] = Field(description="Los cinco factores GRADE que bajan la certeza y los que la suben")
    efecto: Literal["baja", "sube", "neutro"]
    explicacion: str = Field(description="Una frase concreta con la evidencia que lo motiva")


class ConclusionHipotesis(BaseModel):
    hipotesis_breve: str = Field(description="La hipotesis como oracion con verbo, en una linea y sin punto final, para completar 'la evidencia sostiene que ...' (por ejemplo 'GFAP se altera antes que NfL en portadores de APOE e4 con amiloide positivo')")
    certeza: Literal["alta", "moderada", "baja", "muy_baja"] = Field(description="Certeza de la evidencia (GRADE): alta si varios estudios independientes y directos coinciden; moderada si la evidencia es consistente pero de una sola cohorte, indirecta o imprecisa; baja si solo hay indicios, inferencias o estudios con limitaciones serias; muy baja si no hay evidencia directa o es contradictoria")
    direccion: Literal["apoya", "mixta", "en_contra", "sin_evidencia_directa"] = Field(description="Hacia donde apunta la evidencia reunida respecto a la hipotesis. Es independiente de la certeza: no mezclar las dos en una frase")
    conclusion: str = Field(description="Tres o cuatro frases en lenguaje corriente. El verbo principal sigue la certeza: alta 'la evidencia indica que'; moderada 'probablemente'; baja 'puede que'; muy baja 'no esta claro si'. Sin porcentajes ni probabilidades inventadas; las cifras que se den van con su denominador (por ejemplo 'una sola cohorte de 195 personas')")
    factores: list[FactorCerteza] = Field(description="Por que este grado: cada factor que lo bajo o lo subio, con su evidencia")
    a_favor: list[str] = Field(description="Lo que la apoya, una frase por punto, citando la afirmacion o fuente")
    en_contra: list[str] = Field(description="Lo que la debilita o contradice, una frase por punto; vacio si nada")
    lo_mas_fragil: str = Field(description="El supuesto o dato del que mas depende y menos respaldo tiene")
    subiria: str = Field(description="Que hallazgo concreto subiria la certeza (por ejemplo una segunda cohorte independiente con el mismo resultado)")
    bajaria: str = Field(description="Que hallazgo concreto bajaria la certeza o cambiaria la direccion")


class ConcluirHipotesis(dspy.Signature):
    """Escribir la conclusion provisional sobre una hipotesis con la evidencia reunida hasta
    ahora, al modo de un 'summary of findings' de GRADE: no si es cierta (eso lo decide un
    experimento) sino (1) la certeza de la evidencia y por que (factores que la bajan o
    suben), (2) hacia donde apunta esa evidencia, (3) que la apoya, que la debilita, de que
    depende y que la cambiaria. Solo se usa lo que esta en las afirmaciones sostenidas, los
    supuestos evaluados, los partidos del torneo y la comprobacion de novedad. Reglas: una
    sola cohorte no es replicacion (baja la certeza por imprecision o inconsistencia no
    comprobable); evidencia en otra poblacion es indirecta; una interpretacion no es un dato;
    ausencia de evidencia no es evidencia de ausencia; no inventar porcentajes de confianza.
    Lenguaje corriente, terminos tecnicos explicados la primera vez."""

    hipotesis: str = dspy.InputField()
    afirmaciones: str = dspy.InputField(desc="Con veredicto, tipo y cita")
    supuestos: str = dspy.InputField(desc="Con su estado: respaldado, plausible, sin evidencia, contradicho")
    partidos: str = dspy.InputField(desc="Resultado y eje decisivo de cada comparacion en el torneo")
    novedad: str = dspy.InputField()
    revisiones_humanas: str = dspy.InputField()
    conclusion: ConclusionHipotesis = dspy.OutputField()


class Programas:
    """Los modulos ya instanciados. `dspy.Predict` para extraccion y parseo;
    `dspy.ChainOfThought` donde el razonamiento intermedio ayuda al juicio."""

    def __init__(self) -> None:
        self.plan = dspy.ChainOfThought(ProponerPlan)
        self.consultas = dspy.Predict(GenerarConsultas)
        self.relevancia = dspy.Predict(PuntuarRelevancia)
        self.extraer = dspy.Predict(ExtraerAfirmaciones)
        self.juzgar = dspy.ChainOfThought(JuzgarAfirmacion)
        self.mundo = dspy.ChainOfThought(ActualizarModeloDeMundo)
        self.hipotesis = dspy.ChainOfThought(GenerarHipotesis)
        self.revisar_inicial = dspy.ChainOfThought(RevisarInicial)
        self.evaluar_supuesto = dspy.Predict(EvaluarSupuesto)
        self.comparar = dspy.ChainOfThought(CompararHipotesis)
        self.meta = dspy.ChainOfThought(MetaRevisar)
        self.aclarar = dspy.ChainOfThought(AclararHipotesis)
        self.responder = dspy.ChainOfThought(ResponderComentarios)
        self.resumir = dspy.Predict(ResumirIteracion)
        self.en_llano = dspy.Predict(ExplicarEnLlano)
        self.hipotesis_en_llano = dspy.Predict(HipotesisEnLlano)
        self.experimento = dspy.ChainOfThought(ProponerExperimento)
        self.concluir = dspy.ChainOfThought(ConcluirHipotesis)

    def cargar_optimizados(self, directorio) -> list[str]:
        """Carga los programas optimizados por GEPA que existan en el directorio
        (`<nombre>.json`). Devuelve los que cargo."""
        from pathlib import Path

        cargados = []
        for nombre, modulo in vars(self).items():
            ruta = Path(directorio) / f"{nombre}.json"
            if ruta.exists():
                modulo.load(str(ruta))
                cargados.append(nombre)
        return cargados
