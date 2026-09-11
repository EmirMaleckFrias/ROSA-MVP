# Investigacion para el backend de Rosa

Fecha: 10 de septiembre de 2026. Resumen de doce investigaciones hechas sobre
documentacion oficial, papers y codigo fuente de los sistemas que hoy se
llaman "AI scientist", mas las APIs de las fuentes que Rosa consulta. Al final
esta la arquitectura que se construyo con todo esto y por que.

Lo que se copio de cada sistema esta marcado con "Rosa toma". Lo que se
descarto, con "Rosa no toma" y el motivo.

## 1. Los sistemas de referencia

### 1.1 Kosmos (Edison Scientific, 2025)

Ciclo: el modelo de mundo `W_t` es una funcion del modelo anterior y de los
resumenes de las tareas de la iteracion. Cada iteracion lanza hasta 10 tareas
en paralelo (busquedas de literatura y analisis de datos), cada una con su
trayectoria identificada. Los informes citan ids de trayectoria y de fuente.
Cinco replicaciones independientes para las afirmaciones importantes. Acierto
medido: 85 % en afirmaciones de datos, 82 % en literatura, 58 % en
interpretaciones. Se paro por presupuesto (200 corridas por iteracion) y por
estabilidad del modelo de mundo.

Rosa toma: el modelo de mundo como estado explicito y persistente; tareas en
paralelo dentro de una iteracion con transcripcion por tarea ("pistas");
tipo de afirmacion (dato, literatura, interpretacion) porque no se verifican
igual; replicacion bajo demanda.

### 1.2 Co-Scientist (Google, Nature 2025) y sus reimplementaciones

Seis agentes mas un supervisor con cola de tareas: Generation (literatura,
debate, supuestos, expansion), Reflection (revision inicial sin herramientas,
completa con literatura, verificacion profunda descomponiendo supuestos,
observacion, simulacion, torneo), Ranking (Elo, 1200 inicial, debate
multiturno en el top y comparacion simple en el resto), Proximity (grafo de
similitud), Evolution (seis estrategias que producen hipotesis nuevas con
`parent_ids`, nunca sobreescriben), Meta-review (debilidades recurrentes que
se inyectan como criterios). La version de agosto de 2026 cambio Elo por
TrueSkill con emparejamiento UCB. Las reimplementaciones publicas (Kaimen,
conradry, raktim) coinciden en: SQLite WAL con cola de tareas con leases,
idempotencia por `match_id`, SSE al frontend, filtrado de citas a URLs
realmente vistas en trazas de herramientas.

Rosa toma: los seis tipos de revision como campos separados de la hipotesis;
el torneo por pares con juez y debias A/B y B/A; la meta-revision con
debilidades inyectables; el prior de las hipotesis humanas (entran con la
misma incertidumbre que las de Rosa); las revisiones humanas estructuradas
como entrada del siguiente debate.

Rosa no toma: la cola de tareas con leases y multiples workers. Un solo
proceso con asyncio basta para una investigadora y una Mac, y quita una capa
de fallos. Si hace falta escalar, la cola de Kaimen es el diseno a copiar.

### 1.3 PaperQA2 y 3 (FutureHouse)

Pipeline: buscar, trocear (5000 caracteres con solape de 250), puntuar
relevancia de cada fragmento 0 a 10 con el modelo (RCS), quedarse con los
mejores, responder citando fragmentos, y decir "I cannot answer" cuando no
hay respaldo. Clientes de metadatos con `is_retracted` y `source_quality`.

Rosa toma: la puntuacion de relevancia por fragmento antes de extraer; la
abstencion explicita; la marca de retractacion como parte de los metadatos de
cada fuente.

### 1.4 Robin (FutureHouse) y Virtual Lab (Stanford)

Robin: torneo pareado de hipotesis con Bradley-Terry (`choix.ilsr_pairwise`)
en vez de Elo, mas experimentos propuestos con protocolo y coste. Virtual
Lab: reuniones con agenda, un agente por rol, un critico obligatorio, y el
"principal investigator" sintetiza; el humano fija la agenda y las reglas.

Rosa toma: el experimento propuesto con protocolo, ensayo y coste estimado
(campo `experimento` de la hipotesis); el critico obligatorio antes de
sintetizar. Bradley-Terry queda como alternativa a Elo cuando haya mas de 30
hipotesis por investigacion (Elo con pocos partidos es ruidoso pero legible).

### 1.5 Agent Laboratory y AgentRxiv

Fases fijas (literatura, plan, datos, experimentos, interpretacion, informe,
revision) con agentes de rol que dialogan por turnos hasta un comando
terminal (`PLAN`, `SUBMIT_CODE`, `INTERPRETATION`). mle-solver: EDIT y
REPLACE sobre el codigo con reward model 0 a 1 y reparacion automatica.
paper-solver: andamiaje por secciones y rubrica NeurIPS. Coste medido: 2,33
USD por paper con gpt-4o. Limitacion admitida: el revisor automatico
sobreestima 2,3 puntos sobre 10 frente a humanos.

Rosa toma: la idea de que cada fase termina con un artefacto explicito y
revisable; el aviso de que un revisor automatico no sustituye al humano (por
eso la cola de hipotesis es humana).

Rosa no toma: el dialogo por turnos entre roles. Con DSPy cada paso es una
firma con entrada y salida tipadas; el dialogo se sustituye por composicion.

### 1.6 Denario y cmbagent; Curie

cmbagent: planificacion con revisor del plan (una sola ronda; mas rondas
empeoran), control paso a paso con un agente por paso, historial reiniciado
en cada paso y solo el contexto trasladado ("context carryover"), tope de
intentos por paso y terminacion al agotarlos. Curie: arquitecto que escribe
planes con hipotesis y variables, tecnicos que construyen el flujo, un
validador del montaje (busca datos simulados, marcadores de posicion,
variables sin usar) y un validador de ejecucion que reejecuta el flujo en
limpio y exige el fichero de resultados; 3,4 veces mas conclusiones correctas
que la linea base.

Rosa toma: el plan se propone y se aprueba antes de ejecutarse; cada paso
tiene presupuesto e intentos; la iteracion cierra con un resumen que se
traslada a la siguiente en vez de arrastrar todo el historial; la
verificacion del montaje (una pista que no produjo fichero no cuenta como
hecha) para cuando entren analisis de datos.

### 1.7 SciAgents, ResearchAgent, HypoGeniC, Biomni

SciAgents: caminos aleatorizados en un grafo ontologico como semilla de
hipotesis; siete campos por hipotesis (hipotesis, resultado esperado,
mecanismo, principios de diseno, propiedades inesperadas, comparacion,
novedad). ResearchAgent: cinco criterios por etapa con rubrica Likert,
refinamiento solo de los criterios con nota baja, tres iteraciones. HypoGeniC:
banco de hipotesis con recompensa UCB (acierto mas exploracion) y banco de
ejemplos mal predichos que dispara generacion nueva. Biomni: un solo agente
con entorno de 150 herramientas y 59 bases, plan como lista de control con
casillas, `execute` y `solution` como acciones, recuperacion de herramientas
por prompt, critico opcional.

Rosa toma: la hipotesis con mecanismo, comprobacion (biomarcador, cohorte,
diseno) y novedad como campos obligatorios; la lista de control del plan con
pasos hechos, fallidos y omitidos con motivo; los criterios de revision como
lista editable (Ajustes) que el revisor lee.

## 2. DSPy 3.3.1 y GEPA

- `dspy.LM("openai/<id del gateway>", api_base=URL, api_key=...)` es la unica
  forma de hablar con los modelos. `lm.history[-1]` trae `usage` y `cost`;
  `cost` es `None` para modelos que LiteLLM no tiene tarifados, asi que Rosa
  cuenta llamadas y tokens, no dolares.
- Modulos: `dspy.Predict` para parseo y extraccion, `dspy.ChainOfThought`
  para revisiones y comparaciones. Salidas tipadas con pydantic. Llamada
  asincrona con `await modulo.acall(...)` dentro de `dspy.context(lm=...)`
  para elegir modelo por rol.
- Callbacks (`dspy.utils.callback.BaseCallback`): `on_lm_start` y
  `on_lm_end` sirven para contar llamadas, cortar por presupuesto y registrar
  cada llamada en la base.
- GEPA: `dspy.GEPA(metric, max_metric_calls, reflection_lm,
  reflection_minibatch_size, candidate_selection_strategy="pareto",
  track_stats, log_dir)`. La metrica devuelve `dspy.Prediction(score,
  feedback)` y el feedback textual es lo que GEPA lee para proponer
  instrucciones nuevas. Ya esta probado en `rosa/ejemplo_gepa.py` contra el
  gateway; los programas optimizados se guardan como JSON y se cargan con
  `programa.load(ruta)`.
- MLflow 3.16: `mlflow.dspy.autolog()` traza cada llamada;
  `sqlite:///mlflow.db` como backend (el de ficheros esta deprecado);
  `log_compiles=True` cubre `GEPA.compile`. Con varios procesos escribiendo
  hay bloqueos de SQLite; Rosa es un proceso.

## 3. Fuentes y sus APIs (comprobadas el 10 de septiembre de 2026)

| Fuente | Endpoint | Limite | Clave | Notas |
|---|---|---|---|---|
| PubMed E-utilities | `eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi`, `efetch.fcgi` | 3 por segundo (10 con clave) | Opcional | `retmax` hasta 10000; abstracts por `efetch db=pubmed rettype=abstract retmode=xml` |
| Europe PMC | `www.ebi.ac.uk/europepmc/webservices/rest/search`, `/{PMCID}/fullTextXML` | 10 por segundo, 500 por minuto | No | Incluye preprints (`SRC:PPR`), `HAS_FT:Y` para texto completo |
| OpenAlex | `api.openalex.org/works` | 100 por segundo; presupuesto diario 1 USD con clave gratuita, 0,10 sin clave | Gratuita, necesaria | Singleton gratis; `filter` 0,0001 USD; `search` 0,001 USD; el `mailto` ya no da nada; `is_retracted` tiene falsos positivos (Lancet Commission 2020) |
| Crossref | `api.crossref.org/works/{doi}` | 5 por segundo publico, 10 con `mailto` | No | `updated-by[].type == "retraction"` con `source` publisher o retraction-watch |
| Retraction Watch | `gitlab.com/crossref/retraction-watch-data` (CSV diario) | | No | 72450 filas; columnas `OriginalPaperDOI`, `RetractionNature` |
| Unpaywall | `api.unpaywall.org/v2/{doi}?email=` | 100000 al dia | Correo | `best_oa_location.url_for_pdf`; comparte datos con OpenAlex |
| Semantic Scholar | `api.semanticscholar.org/graph/v1/paper/search`, `/paper/{id}/citations` | 1 por segundo con clave; sin clave devuelve 429 casi siempre | Gratuita, pedirla | `contexts` e `intents` de cada cita (para clasificar apoya, menciona, contrasta) |
| ClinicalTrials.gov v2 | `clinicaltrials.gov/api/v2/studies` | Sin cifra oficial; 1 por segundo es prudente | No | `query.cond`, `query.intr`, `filter.advanced` en Essie, `pageSize` hasta 1000, `countTotal` |
| Open Targets | `api.platform.opentargets.org/api/v4/graphql` | Uso razonable | No | `search(queryString, entityNames:["target"])` y `target(ensemblId){associatedDiseases}`; Alzheimer es `MONDO_0004975` |
| Agora (AD Knowledge Portal) | Sin API publica estable | | | Rosa no afirma "no nominada": dice "no comprobado" |

Regla que sale de todo esto: distinguir siempre "la fuente no lo tiene" de
"no pude consultar la fuente". Un tiempo agotado no es "sin ensayos".

## 4. Texto completo y pagina exacta

- Docling 2.126 (MIT): cada elemento lleva `prov[].page_no` 1-indexado y
  `bbox`; tablas como DataFrame; `HybridChunker` conserva la pagina en cada
  fragmento. Es la opcion principal cuando entren PDFs pesados.
- GROBID 0.9.1 (Docker): cabecera, referencias con DOI y frases con
  `coords="pagina,x,y,ancho,alto"`. Complemento para bibliografia.
- PyMuPDF 1.28 (AGPL): `page.number + 1`, `get_text("blocks")`. Ligero y
  suficiente para arrancar: es lo que usa el conector `rosa/fuentes/pdf.py`.
  Antes de emitir una cita a una pagina, se comprueba que el fragmento
  literal aparece en esa pagina (`page.search_for`).
- MinerU y marker: mas precision con OCR o formulas, pero exigen GPU o
  licencias con condiciones; no hacen falta para articulos nacidos digitales.

## 5. Servidor, tiempo real y persistencia

- FastAPI + sse-starlette: `EventSourceResponse` con `ping` cada 15 s;
  `Last-Event-ID` lo gestiona el servidor reenviando desde su buffer o, mas
  simple, mandando el estado completo con `id` igual al numero de version.
  Rosa manda el estado completo: pesa decenas de KB y elimina toda la logica
  de parches.
- SQLite en modo WAL, un solo escritor, `synchronous=NORMAL`,
  `busy_timeout` 30 s. Tabla de estado (instantanea JSON), tabla de acciones
  (append-only: nombre, argumentos, fecha) y tabla de llamadas a modelos.
  Alembic y Postgres con pgvector cuando haya varios servidores.
- Convex: el cliente Python no se actualiza desde diciembre de 2024 y su
  `subscribe` bloquea. Con dos personas y una Mac, FastAPI + SSE + SQLite es
  menos piezas. Decision tomada aqui; se puede revisar.
- Orquestacion durable: Temporal (`brew install temporal`, `temporal server
  start-dev`) o DBOS son la opcion seria si el bucle tiene que sobrevivir
  reinicios sin perder un paso. La primera version guarda el estado tras
  cada cambio y, al arrancar, marca como fallidas las pistas que quedaron a
  medias y retoma la iteracion desde el primer paso pendiente. Es suficiente
  para empezar y no anade un servicio.
- Sandbox: `dspy.PythonInterpreter` (Deno + Pyodide) no tiene tiempo limite
  propio; hay que envolverlo. Apple `container` (macOS 26) da una VM por
  contenedor sin licencia. Entra cuando Rosa ejecute analisis de datos.

## 6. Abstencion y calibracion

Taxonomia (AbstentionBench, RefusalBench): abstenerse por falta de evidencia,
por pregunta mal planteada, por conflicto entre fuentes, o por no poder
consultar. Cada una con texto distinto. Metricas: tasa de abstencion
correcta, sobreafirmacion (afirmar mas fuerte que la fuente), verificacion
numerica (cifra normalizada presente en el fragmento). Todo esto ya estaba
en los contratos del verificador del RAG (TRASPASO 4.1) y se conserva tal
cual en `rosa/verificador.py`.

## 7. La arquitectura que se construyo

```
rosa/
  gateway.py            modelos por el gateway (cerebro, juez, volumen)
  config.py             rutas, puertos, correo de contacto para las APIs
  estado/
    plantilla.py        estado inicial vacio (misma forma que tipos.ts)
    acciones.py         los reducers de la interfaz, portados a Python
    almacen.py          SQLite WAL, version, suscriptores, registro de acciones
  fuentes/
    base.py             cliente HTTP con limite de tasa y reintentos
    pubmed.py, europepmc.py, crossref.py, openalex.py, unpaywall.py,
    clinicaltrials.py, opentargets.py, pdf.py
  modulos/
    firmas.py           las firmas DSPy (plan, consultas, extraccion, juez,
                        hipotesis, comparacion, meta-revision)
    contador.py         callback que cuenta llamadas y corta por presupuesto
  verificador.py        comprobaciones deterministas + juez (contratos 4.1)
  torneo.py             Elo por pares con debias
  bucle/
    corrida.py          el bucle: plan, aprobacion, pasos, pistas, cierre
  servidor.py           FastAPI: /api/estado, /api/eventos (SSE), /api/acciones
  main.py               arranque: servidor + bucles + MLflow
```

El frontend no cambia de pantallas: `frontend/src/datos/almacen.ts` prueba
`/api/estado`; si responde, entra en modo servidor (estado por SSE, acciones
por POST); si no, sigue con la muestra y la simulacion. Vite reenvia `/api`
al puerto 8765.
