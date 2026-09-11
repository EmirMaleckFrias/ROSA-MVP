# Guía de referencia para Rosa: lo que hay que saber antes de construirla

Compilada el 10 de septiembre de 2026 a partir de fuentes públicas (listadas al
final). Complementa a `TRASPASO.md`, que recoge las decisiones y el estado del
trabajo; esto es el conocimiento de fondo. Donde algo es una inferencia mía y
no un dato de fuente, lo digo.

Cómo leerla si hay poco tiempo: las secciones 1 y 2 son para hablar con el
compañero y con el investigador clinico principal sin quedarse fuera de la conversación; la 3 y la 5 son
las que se abren al escribir código; la 7 es la que evita un problema legal.

## 1. El Alzheimer a nivel de ingeniero

### 1.1 Qué es, en cuatro ideas

1. **Dos proteínas mal plegadas.** Placas extracelulares de **beta amiloide
   (Aβ)** y ovillos intracelulares de **tau hiperfosforilada**. Son los dos
   sellos histopatológicos y los dos grandes blancos terapéuticos.
2. **Neuroinflamación.** La microglía (el sistema inmune del cerebro) se
   activa ante Aβ y tau; el inflamasoma NLRP3 amplifica la cascada, daña las
   sinapsis y acelera la pérdida neuronal. Amiloide e inflamación se
   retroalimentan.
3. **Genética.** **APOE ε4** es el factor de riesgo genético común más
   fuerte en el Alzheimer de inicio tardío, con efectos distintos según el
   tipo celular; **TREM2** (variante R47H) altera la respuesta microglial y
   parece actuar en sinergia con APOE4. Hay variantes protectoras de APOE que
   se estudian como pista terapéutica.
4. **Un modelo multimecanismo.** El campo ha pasado de la hipótesis única del
   amiloide a reconocer al menos 17 aspectos de la fisiopatología con algún
   fármaco en ensayo. Para Rosa esto significa que "relevante" no es solo
   amiloide y tau.

### 1.2 Biomarcadores: por qué p-tau217 aparece en todo

- **p-tau217 en plasma**, solo o como cociente **p-tau217/Aβ42**, tiene una
  precisión comparable a la PET y al líquido cefalorraquídeo. Eso llevó a la
  **aprobación por la FDA del primer test de Alzheimer en sangre, en mayo de
  2025**. Es el biomarcador que más informa sobre la probabilidad de biología
  de Alzheimer subyacente, y puede anticiparse años a los síntomas.
- Los criterios de 2024 de la Alzheimer's Association definen la enfermedad
  **biológicamente** (por biomarcadores), no solo por síntomas: esa es la
  razón de que el diagnóstico se esté moviendo del síntoma a la sangre.
- Otros que se leerán en los artículos: Aβ42/40, p-tau181, p-tau231, NfL
  (neurofilamento de cadena ligera, daño axonal, no específico), GFAP
  (astroglía). En el RAG anterior ya hubo casos de control sobre p-tau217, NfL
  y GFAP.

### 1.3 Fármacos y el pipeline de 2026

| Hecho | Dato |
|---|---|
| Lecanemab | Aprobación tradicional de la FDA en julio de 2023; reduce un 27 % el declive en fase III |
| Donanemab | Aprobación de la FDA en julio de 2024 |
| Efecto de los anti-amiloide | Ralentizan la progresión alrededor de un 30 %; no la detienen |
| Pipeline 2026 (revisión de Cummings) | 158 agentes en 192 ensayos activos; 36 fármacos en fase 3, 84 en fase 2, 45 en fase 1; tres cuartas partes son modificadores de la enfermedad |
| Reparto por diana | Inflamación e inmunidad pasan del 6 % al 20 %; tau del 6 % al 20 %; amiloide baja del 33 % al 20 % |

Nombres que se van a leer: remternetug (anti-amiloide subcutáneo de nueva
generación), trontinemab, bepranemab (anti-tau), BIIB080 (antisentido contra
el ARNm de MAPT, el gen de tau), etalanetug (E2814, anti-tau en combinación con
lecanemab), AR1001 (inhibidor oral de PDE5 en fase 3), semaglutida (agonista
GLP-1, varios ensayos incluida una fase 3).

**Lo que esto implica para Rosa**: la literatura de 2026 está llena de
resultados de fase 2 y 3 con cifras exactas, y el error clásico es atribuir la
cifra de un fármaco a otro. La comprobación de entidad del verificador (dato de
otra entidad presentado como propio) es aquí crítica, no cosmética.

## 2. El investigador principal

**el investigador clinico principal**: doctor en Medicina y profesor de Neurología de la
Universidad de Buenos Aires, jefe de Neurología Cognitiva, Neuropsicología y
Neuropsiquiatría del Instituto Neurológico FLENI (Buenos Aires), investigador
principal del CONICET y del Consejo de Investigación del Ministerio de Salud
argentino. Miembro de la American Academy of Neurology. Perfil en Google
Scholar y ResearchGate.

**Sus líneas**: investigación clínica de **biomarcadores** en deterioro
cognitivo y demencias, tanto Alzheimer esporádico como familiar (autosómico
dominante). Publicaciones recientes sobre biomarcadores centrales en líquido
cefalorraquídeo precediendo a los inflamatorios y gliales en Alzheimer
autosómico dominante, sobre p-tau217 en plasma frente a PET de tau, y sobre
que predecir el inicio de los síntomas exige más que amiloide y tau. En agosto
de 2025 defendió públicamente la detección temprana, sencilla y de bajo coste
con biomarcadores en sangre. FLENI ha incorporado tecnología para analizarlos
en sangre. Colabora con la Universidad de Antioquia (Colombia), que tiene la
mayor cohorte del mundo de Alzheimer familiar por la mutación presenilina 1
E280A (esto último es conocimiento general del campo, no salió en las
fuentes de esta búsqueda).

**Lo que esto implica para Rosa** (inferencia mía): la persona que va a
validar las hipótesis piensa en términos de biomarcadores, cohortes
longitudinales, Alzheimer familiar como modelo del esporádico, y acceso
diagnóstico en Latinoamérica. Cuando Rosa priorice preguntas abiertas,
conviene que sepa expresarlas en ese lenguaje, y que las hipótesis lleven
siempre qué biomarcador o qué cohorte permitiría comprobarlas.

## 3. Fuentes de datos y sus APIs

### 3.1 Literatura

| Fuente | Qué da | Límite de peticiones | Clave |
|---|---|---|---|
| PubMed (E-utilities de NCBI) | 37 millones de citas biomédicas, resúmenes, MeSH | 3 por segundo; 10 con clave | Gratuita, recomendada |
| PMC | 10 millones de textos completos en acceso abierto | Con las E-utilities | Igual |
| Europe PMC (REST) | Índice unificado, texto completo y preprints | 10 por segundo, 500 por minuto, por IP | No |
| bioRxiv y medRxiv (API) | Preprints | Sin límite formal, uso responsable | No |
| Semantic Scholar (Academic Graph) | 200 millones de artículos, citas, grafo | 1 por segundo con clave; sin clave, cupo compartido y estrangulado | Gratuita, pedirla |
| OpenAlex | 250 millones de obras, autores, instituciones | 10 por segundo; desde 2026 precios por uso con presupuesto diario gratuito (0,01 dólares al día sin clave, 1 dólar con clave gratuita); tope de 100 por segundo | Gratuita, necesaria |
| Crossref | 150 millones de DOI, metadatos, **retractaciones** (`updated-by`) | 50 por segundo | No; conviene identificarse con un User-Agent |
| Unpaywall | Estado de acceso abierto y enlace al PDF legal | Uso razonable | Correo de contacto |
| CORE | 37 millones de textos completos | | Clave obligatoria para texto completo |

Las skills instaladas `paper-lookup` (once índices, procedencia reproducible),
`search-lit` (cada cita verificada por API antes de incluirse) y `verify-refs`
(auditoría contra PubMed y Crossref, detecta referencias fabricadas) ya
implementan esto. El RAG anterior tiene la comprobación de retractaciones por
Crossref en `retracciones.ts`.

### 3.2 Ensayos clínicos

**ClinicalTrials.gov, API v2** (la v1 se retiró): búsqueda estructurada,
unos 50 peticiones por minuto por IP, sin clave. Para Rosa es la fuente de
qué se está probando en humanos, con qué diana y en qué fase, y el contraste
natural para una hipótesis "nueva": si ya hay un ensayo, no es nueva.

### 3.3 Bases curadas y grafos de conocimiento

| Recurso | Qué es | Acceso |
|---|---|---|
| **Open Targets** | 7,8 millones de asociaciones diana-enfermedad, más de 20 fuentes integradas, evidencia por asociación | API GraphQL gratuita; skill `gget` la consulta |
| **PrimeKG** | Grafo de medicina de precisión: 129.000 nodos, 4 millones de aristas, 29 tipos de relación (fármaco-diana, gen-enfermedad, fenotipo-enfermedad) | Descarga desde Harvard Dataverse, CSV; skill `primekg` |
| **NCATS Translator (ARAX)** | Grafo biomédico federado con procedencia por arista y publicaciones | API TRAPI; skill `ncats-arax` |
| **AD Knowledge Portal** (Sage Bionetworks, sobre Synapse) | 800 TB de datos de más de 11.000 individuos: secuenciación, imagen, conducta, de 14 programas del NIH; incluye ROSMAP y enlaces a ADNI | Registro en Synapse, acuerdos de uso por dato, APIs de Synapse |
| **Agora** | Más de 500 dianas candidatas nominadas por los equipos de AMP-AD, con evidencia y "drogabilidad" | Web abierta, código abierto |
| **NIAGADS GenomicsDB** | 69 conjuntos de estadísticas GWAS con más de 150 millones de variantes anotadas de 23 estudios de Alzheimer y demencias relacionadas | API REST que devuelve JSON |
| **GWAS Catalog** (NHGRI-EBI) | 15 publicaciones de Alzheimer con 38 conjuntos de estadísticas descargables | Descarga pública |
| **AlzForum** | Bases curadas de mutaciones y de terapias, noticias del campo | Web; sin API pública conocida |
| **GEO (NCBI)** | Datos de expresión, incluido RNA-Seq | E-utilities y descarga |

**Lo que esto implica**: la comprobación de novedad de una hipótesis no se hace
solo contra la literatura; se hace contra Open Targets (¿ya hay evidencia
gen-enfermedad?), ClinicalTrials.gov (¿ya se está probando?) y Agora (¿ya está
nominada como diana?). Tres consultas baratas que ahorran una corrida de horas.

## 4. Quién ya hace esto, y cómo

- **Kosmos** (Edison Scientific, antes FutureHouse): campañas largas sobre una
  pregunta, unos 1.500 artículos leídos y 42.000 líneas de código de análisis
  por corrida; 79,4 % de conclusiones correctas según su propia evaluación;
  cada conclusión trazable al pasaje o a la línea de código; su innovación es
  un **modelo de mundo estructurado** que mantiene la coherencia durante
  decenas de millones de tokens; su fallo reconocido es perseguir resultados
  significativos pero irrelevantes; entre sus siete descubrimientos hay uno
  sobre tau en Alzheimer. Avisa por Slack, Teams y correo; tiene API.
- **Co-Scientist** (Google DeepMind, Nature 2026): agentes de generación,
  reflexión (revisor), proximidad (deduplicación), ranking por **torneo Elo**,
  evolución y meta-revisión; objetivo en lenguaje natural; la científica puede
  aportar ideas. Producto cerrado.
- **Biomni** (Stanford, abierto): entorno con 105 paquetes, 59 bases de datos y
  150 herramientas y un agente que las recorre; igualó a científicos senior en
  diagnóstico de enfermedades raras, genes causales y reposicionamiento.
- Ninguno hace que un modelo aprenda pesos durante el bucle; lo que crece es la
  memoria estructurada, las hipótesis clasificadas y el corpus curado.

### 4.1 Claude Science y los programas de Anthropic (comprobado el 10 sep 2026)

- **Claude Science** (lanzado el 30 de junio de 2026): un "banco de trabajo" para
  científicos, en beta para macOS y Linux, dentro de los planes Pro, Max, Team y
  Enterprise. Un agente coordinador delega en especialistas con **más de 60
  skills y conectores** (genómica, single-cell, proteómica, biología
  estructural, quimioinformática, literatura), acceso a UniProt, PDB, Ensembl,
  Reactome, ClinVar, ChEMBL y GEO, modelos de NVIDIA BioNeMo (Evo 2, Boltz-2,
  OpenFold3), y un **agente revisor que verifica citas y cálculos**. Los datos
  grandes o sensibles no salen de donde están (corre en el portátil, en una
  máquina Linux o en un nodo de HPC; solo se envía a Claude el contexto de cada
  paso) y cada salida lleva un historial auditable con el código exacto. Es
  la referencia comercial más cercana a lo que Rosa quiere ser en la parte de
  análisis; lo que no tiene es el bucle de investigación autónomo de días ni
  el modelo de mundo.
- **Conectores de Claude for Life Sciences** (2026): Benchling, 10x Genomics,
  PubMed, BioRender, Synapse.org (el AD Knowledge Portal vive en Synapse) y
  Scholar Gateway de Wiley para revistas con acceso autenticado.
- **Life Sciences Verification Program (LSVP)**: beta cerrada, por invitación,
  en alianza con el gobierno de Estados Unidos, para que profesionales de
  ciencias de la vida usen **Claude Mythos 5.1** (la misma arquitectura que
  Fable 5.1, con salvaguardas de biología reducidas). Hoy restringido a
  organizaciones de Estados Unidos; Anthropic dice trabajar en abrirlo
  internacionalmente. Es la única vía por la que Fable o Mythos podrían entrar
  en Rosa, y hoy AI Robotix (República Dominicana) no cumple el requisito.
- **AI for Science Program**: hasta 20.000 dólares en créditos de API por seis
  meses para investigadores adscritos a instituciones de investigación
  (académicas y sin ánimo de lucro; no menciona empresas), con cribado de
  bioseguridad del proyecto y la política de uso normal. Se evalúa el primer
  lunes de cada mes. Una convocatoria específica de Claude Science dio 30.000
  dólares a 50 proyectos (plazo cerrado el 15 de julio de 2026). Inferencia
  mía: el INTEC, como institución académica, podría solicitarlo; AI Robotix
  como empresa probablemente no.
- **Plan Claude Team para científicos** (27 de agosto de 2026): 10.000 asientos
  gratuitos o con descuento para investigadores de instituciones académicas y
  sin ánimo de lucro (estándar gratis, premium a 15 dólares al mes con cinco
  veces más uso), y hasta 50.000 dólares en créditos por proyecto en
  convocatoria continua con revisión por mérito.

## 5. Ingeniería de Rosa

### 5.1 El bucle

Iteraciones cortas con presupuesto propio y punto de guardado: planificar,
buscar (literatura, ensayos, grafos), extraer afirmaciones con procedencia,
verificar, actualizar el modelo de mundo, comprobar novedad, reordenar las
preguntas abiertas, volver a empezar. Antes de la primera iteración: qué cuenta
como relevante, quién revisa, cuándo se para. **La aprobación va antes del
efecto**: una hipótesis no entra al modelo de mundo como aceptada, ni se gasta
un presupuesto grande en perseguirla, sin que alguien la haya visto.

### 5.2 Orquestación durable

Un bucle de días necesita ejecución durable: reintentos, tiempos límite, estado
que sobrevive a un reinicio. Las dos opciones serias en Python:

- **Temporal**: sistema de ejecución durable de propósito general; garantiza
  que el flujo termine aunque falle la infraestructura. Cada paso es una
  "actividad" con política de reintento y tiempo límite.
- **LangGraph**: grafos de estado para agentes, con checkpoints entre nodos
  (ojo: no guarda estado dentro de un nodo). Hay integración oficial con
  Temporal: los nodos se declaran como actividad de Temporal o como código
  determinista dentro del flujo.

Patrón recomendado por la literatura consultada: Temporal para la
orquestación central y LangGraph (o DSPy directamente) para la lógica del
agente. Inferencia mía: Convex, que ya conocemos del RAG, cubre un bucle de
horas con su planificador de tareas y sus cadenas reanudables, pero para días
y Python, Temporal es el estándar.

### 5.3 DSPy y GEPA, con la API exacta

- Primitivas: `Signature` (entrada y salida tipadas), `Module` (`Predict`,
  `ChainOfThought`, `ReAct`, `ProgramOfThought`), programa compuesto, métrica,
  optimizador. `dspy.RLM` para razonar sobre contextos de más de 100.000 tokens
  con un intérprete de Python en sandbox.
- Modelo por el gateway: `dspy.LM("openai/<id del gateway>", api_base=URL,
  api_key=CLAVE)`; el prefijo `openai/` es el de LiteLLM para endpoints
  compatibles. Comprobado con los tres modelos elegidos.
- **`dspy.GEPA`**: presupuesto con exactamente uno de `auto` ("light",
  "medium", "heavy"), `max_full_evals` o `max_metric_calls`;
  `reflection_lm` obligatorio y fuerte (la documentación sugiere un modelo de
  primera fila a `temperature=1.0` y `max_tokens=32000`);
  `reflection_minibatch_size` 3 por defecto; `candidate_selection_strategy`
  "pareto" o "current_best"; `use_merge` True; `track_stats` para resultados
  detallados; `log_dir` para checkpoints.
- **La métrica** tiene esta firma: `metric(gold, pred, trace, pred_name,
  pred_trace, program_trace=None)` y devuelve `dspy.Prediction(score=float,
  feedback=str)` (o un diccionario con `score` y `feedback`). El `feedback`
  textual es lo que GEPA lee. En Rosa, ese texto es la crítica del verificador.
- `gepa.compile(student, trainset=..., valset=...)`: `trainset` obligatorio y
  no vacío; `valset` opcional pero recomendado y de unos 35 ejemplos como
  máximo para explorar dentro del presupuesto. Reutilizar "logs, pruebas
  unitarias y salidas de evaluadores" como feedback.
- Observabilidad: `mlflow.dspy.autolog()` registra cada compilación como
  corrida con evaluaciones anidadas, parámetros y progresión de la métrica.
- Circularidad a evitar: el juez se calibra con etiquetas humanas; el extractor
  y el generador se optimizan contra el juez. Nunca el juez contra sí mismo.

### 5.4 Leer PDF científicos

- **GROBID**: el estándar para estructura bibliográfica de artículos
  académicos (autores, secciones, referencias); F1 de 0,87 en referencias de
  PMC y 0,90 en bioRxiv; con él se procesaron 8,1 millones de artículos de
  S2ORC. Salida TEI.
- **MinerU**: el más preciso en fórmulas y tablas de artículos; tablas a HTML,
  fórmulas a LaTeX; el defecto para ingesta a escala de arXiv.
- **Docling** (IBM, MIT): documento estructurado tipado, tablas en rejilla de
  celdas, corre en CPU, ingiere PDF, Office y más.
- **Marker**: el más rápido a escala (hasta 120 páginas por segundo en GPU en
  lote), con pase opcional de refinamiento por modelo.
- Tendencia de 2026: las capas de maquetación y OCR se han fundido en modelos
  de visión y lenguaje dentro de las tres herramientas.
- Inferencia mía para Rosa: GROBID para referencias y estructura, y Docling o
  MinerU para el texto por página, manteniendo la regla del RAG de que un
  fragmento no cruce de página y la cita lleve la página exacta.

### 5.5 Almacén vectorial, embeddings y rerankers

- Almacén: **pgvector** para la mayoría de equipos (hasta 50 millones de
  vectores, sobre Postgres, que además sirve para el modelo de mundo
  relacional); **Qdrant** cuando mande el filtrado complejo y la búsqueda
  híbrida con vectores dispersos; **LanceDB** o **Chroma** para local y
  prototipos. Inferencia mía: pgvector, porque Rosa necesita tablas normales
  (hechos, hipótesis, revisiones) tanto como vectores.
- Embeddings en el gateway: `openai/text-embedding-3-large` (el del RAG),
  `voyage/voyage-4-large` (mejor calidad general y multilingüe según el
  catálogo, 32.000 tokens), `google/gemini-embedding-2` (multimodal con PDF).
  Se compara con las métricas de recuperación del RAG (MRR, acierto en los 5 y
  20 primeros).
- Rerankers en el gateway: `voyage/rerank-2.5`, `cohere/rerank-v4-pro`. Un
  reranker especializado puede sustituir la primera pasada del calificador
  del RAG, que hoy lee cada candidato con el modelo grande. Se mide antes.

### 5.6 Modelos y hardware

Decidido: GPT-6 Astra de cerebro, Claude Opus 5 de juez, Claude Sonnet 5 en
alto volumen. Claude Fable 5.1 queda fuera: sus filtros de doble uso en
biología devuelven vacío por la API en cinéticas de agregación, hipótesis
mecanísticas y dianas terapéuticas, comprobado el 10 sep 2026 (detalle en
`TRASPASO.md`, 2.2 y 2.3).
Tres Mac de Apple para servir y ajustar piezas localmente (M5 Ultra con hasta
512 GB si son las actuales): ajuste LoRA con MLX de modelos abiertos, no
preentrenamiento; tres máquinas independientes, no una memoria sumada.

## 6. Evaluación

- **El juez** se calibra con casos etiquetados por humanos antes de fijarlo.
  Los 17 casos del RAG están sin aprobar. Hay que escribir casos del dominio
  del Alzheimer con el compañero.
- **Qué se mide**: tasa de afirmaciones sostenidas, cobertura, ausencias
  refutadas, atribuciones a otra entidad, y por separado cuántas veces el juez
  dice "sin verificar" cuando no sabe.
- **Taxonomía de cuándo abstenerse** (RefusalBench): ambigüedad,
  contradicción, información faltante, premisa falsa, desajuste de
  granularidad, desajuste epistémico. Los modelos usan "falta información"
  como comodín y la precisión de rechazo cae del 73 % al 36 % en contextos
  multidocumento: Rosa lee multidocumento siempre.
- **Benchmarks de agentes científicos** para situar a Rosa: LAB-Bench 2,
  BixBench (los modelos de frontera de 2025 sacaban 17 % en respuesta abierta),
  BiomniBench (evaluación a nivel de proceso), BioVerge (hipótesis),
  HeurekaBench.
- **Fidelidad**: Vectara HHEM y FaithJudge; RAGTruth; HalluLens. Los tableros
  van tres meses por detrás de los lanzamientos.

## 7. Ética, legal y gobernanza

### 7.1 República Dominicana

- **Ley 172-13** (13 de diciembre de 2013) de protección de datos personales:
  derecho a la intimidad y a la autodeterminación informativa. Los **datos de
  salud** solo pueden tratarlos centros y profesionales de salud conforme a la
  legislación sanitaria y respetando el secreto profesional; cualquier
  tratamiento, incluidos agentes de IA, debe operar con finalidad clara,
  control de acceso, trazabilidad y confidencialidad.
- **CONABIOS** (Consejo Nacional de Bioética en Salud): evalúa, aprueba y
  puede suspender protocolos de investigación en seres humanos en el país, y
  les da seguimiento. Requisitos para someter un protocolo: aprobación previa
  por el comité de bioética de la institución o uno independiente reconocido,
  consentimiento informado, currículos de los investigadores, póliza de seguro
  para participantes y presupuesto. **Desde el 1 de septiembre de 2026, por la
  Resolución 03-25, no se aceptan protocolos cuya evaluación ética inicial la
  haya hecho un comité no certificado.** Publica un manual de normas y
  procedimientos operativos.
- Implicación: mientras Rosa trabaje solo con literatura publicada, no toca
  datos de pacientes. En cuanto entren cohortes, historias clínicas o
  biomarcadores de personas, hay que anonimizar antes (skill `deidentify`,
  que corre en local sin red), y la fase preclínica y clínica del proyecto pasa
  por comité certificado y por CONABIOS.

### 7.2 Integridad científica con IA

- La Office of Research Integrity de Estados Unidos publicó en 2026 una guía
  sobre IA generativa e integridad; SciELO y otros insisten en la agencia
  humana: la IA propone, la persona responde. En 2026 miles de artículos han
  sido sometidos a verificación automatizada de reproducibilidad.
- Traducido a Rosa: cada hipótesis lleva procedencia hasta el pasaje, se
  distingue lo que dice la fuente de lo que infiere el modelo, las hipótesis
  se preregistran antes de probarlas (la skill `hypothesis-generation` genera
  planes preparados para preregistro), y las decisiones quedan auditadas.

## 8. Vocabulario que va a aparecer

Aβ42, Aβ40 y su cociente; p-tau181, p-tau217, p-tau231; NfL; GFAP; APOE ε4;
TREM2 R47H; MAPT (gen de tau); PSEN1, PSEN2, APP (Alzheimer familiar);
deterioro cognitivo leve (MCI); Alzheimer preclínico; PET de amiloide y de
tau; ARIA (anomalías de imagen por amiloide, el efecto adverso de los
anti-amiloide); CDR-SB (escala de progresión de los ensayos); MMSE; ADNI,
ROSMAP, AMP-AD, A4, DIAN (Alzheimer familiar); GWAS; single-cell y snRNA-seq;
módulos de coexpresión; reposicionamiento de fármacos; identificación y
validación de dianas; drogabilidad; lab-in-the-loop; grafo de conocimiento;
procedencia; preregistro.

## 9. Preguntas para la primera reunión con el compañero

1. Qué cuenta como "relevante": ¿una diana nueva, una hipótesis mecanística,
   una asociación biomarcador-progresión, un candidato a reposicionamiento?
2. Contra qué se mide la novedad: ¿Open Targets, ClinicalTrials.gov, Agora,
   la literatura, todo?
3. Quién revisa y con qué frecuencia; qué formato quiere el investigador clinico principal para leer
   una hipótesis.
4. Qué datos entran además de literatura: ¿RNA-Seq de GEO, cohortes propias,
   datos de FLENI? Si hay personas, cuándo pasa por CONABIOS.
5. Cuándo se para una corrida y qué se guarda entre iteraciones.
6. Qué tienen las tres Mac exactamente (chip y memoria) y si Rosa debe poder
   correr entera sin salir de la empresa.

## 10. Fuentes

Alzheimer y fármacos: https://consultorsalud.com/alzheimer-biomarcador-p-tau217-nuevos-farmacos/ ;
https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12524931/ ;
https://alz-journals.onlinelibrary.wiley.com/doi/10.1002/trc2.70251 ;
https://www.alz.org/news/2026/alzheimers-disease-drug-development-pipeline-is-growing ;
https://pmc.ncbi.nlm.nih.gov/articles/PMC12897309/ ;
https://alz-journals.onlinelibrary.wiley.com/doi/10.1002/alz.71552 ;
https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11710122/

Perfil institucional del investigador clinico principal: referencia retirada durante la anonimización.
https://scholar.google.com/citations?user=-SIKk2UAAAAJ&hl=es ;
https://pmc.ncbi.nlm.nih.gov/articles/PMC13060398/ ;
https://www.medrxiv.org/content/10.1101/2025.05.14.25326954.full.pdf

Datos y APIs: https://support.nlm.nih.gov/kbArticle/?pn=KA-05317 ;
https://europepmc.org/RestfulWebService ;
https://api.semanticscholar.org/api-docs/ ;
https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication ;
https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/ ;
https://dev.to/avabuildsdata/how-to-search-clinicaltrialsgov-programmatically-the-v2-api-is-actually-good-now-2i2a ;
https://platform-docs.opentargets.org/associations ;
https://adknowledgeportal.synapse.org/Data%20Access ;
https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12727157/ ;
https://alz-journals.onlinelibrary.wiley.com/doi/10.1002/alz.13509

Claude Science y programas: https://www.anthropic.com/news/claude-science-ai-workbench ; https://www.statnews.com/2026/06/30/anthropic-release-claude-science-ceo-dario-amodei/ ; https://support.claude.com/en/articles/11199177-anthropic-s-ai-for-science-program ; https://www.anthropic.com/claude/mythos ; https://www.unite.ai/anthropic-opens-10000-free-and-discounted-claude-seats-for-scientists/

Referencias del campo: https://advances.edisonscientific.com/research/announcing-kosmos/ ;
https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/ ;
https://www.nature.com/articles/s41586-026-10644-y

Ingeniería: https://dspy.ai/api/optimizers/GEPA/overview/ ;
https://dspy.ai/tutorials/optimizer_tracking/ ;
https://arxiv.org/abs/2507.19457 ;
https://docs.temporal.io/develop/python/integrations/langgraph ;
https://www.langchain.com/resources/langgraph-vs-temporal ;
https://grobid.readthedocs.io/en/latest/Principles/ ;
https://themenonlab.blog/blog/best-open-source-pdf-to-markdown-tools-2026 ;
https://4xxi.com/articles/vector-database-comparison/

Evaluación: https://arxiv.org/html/2510.10390 ;
https://arxiv.org/abs/2503.00096 ;
https://github.com/vectara/FaithJudge

Ética y legal: https://phlaw.com/es/post/ley-172-13-sobre-proteccion-de-datos-personales/ ;
https://www.tenebit.com/rd/blog/ley-172-13-datos-personales-pacientes-salud-rd/ ;
https://conabios.gob.do/identidad/ ;
https://diariosalud.do/conabios-comites-etica-certificados-protocolos-investigacion ;
https://conabios.gob.do/wp-content/uploads/2025/02/1.Manual-de-Normas-y-Procedimientos-Operativos-V2-13-02.pdf ;
https://universoabierto.org/2026/08/19/la-inteligencia-artificial-generativa-y-la-integridad-cientifica-guia-de-la-office-of-research-integrity-de-estados-unidos/
