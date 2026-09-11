# Las herramientas de Claude Science y como aplicarlas a Rosa

Investigacion del 11 de septiembre de 2026. Fuentes primarias: la
documentacion oficial de Claude Science (claude.com/docs/claude-science), el
repositorio publico con los prompts del sistema, las skills y la configuracion
MCP de Claude Science (github.com/Shoko-official/Claude-Science-System-Prompts,
material bajo Apache-2.0 en `skills/` y `mcp/`), la nota de Anthropic sobre
salud y ciencias de la vida (anthropic.com/news/healthcare-life-sciences) y la
documentacion de cada base de datos. Las secciones 4 y 5 salen de tres
informes de busqueda encargados para esta investigacion; cada afirmacion
lleva su URL.

Que es cada cosa, en una frase. Un **conector** es una pieza que le da al
modelo acceso a una fuente externa (PubMed, ChEMBL) como una herramienta que
puede llamar con argumentos; en Claude Science casi todos son servidores
**MCP** (Model Context Protocol, un protocolo estandar para exponer
herramientas a un modelo por HTTP). Una **skill** es un fichero de
instrucciones (`SKILL.md`) con referencias y scripts que el modelo carga
cuando la tarea lo pide: como se corre un metodo, que herramientas usar y que
verificar. Un **artefacto** es un fichero versionado con procedencia
(mensajes, codigo, registro de ejecucion, entorno, revision). El **revisor**
es un segundo modelo que compara lo que el primero afirma con el registro de
lo que de verdad se ejecuto.

## 1. El inventario completo de Claude Science

### 1.1 Las herramientas del arnes (lo que el modelo puede llamar)

Sacadas de `prompts/claude-science/fragments/tools.md` del repositorio, que es
el fragmento de definiciones de herramientas del prompt del sistema. Son 21.

| Herramienta | Que hace | Lo que exige el prompt |
| --- | --- | --- |
| Agent | Lanza un especialista con una tarea acotada, en paralelo o en segundo plano | Pregunta cientifica, ficheros, supuestos, salida esperada y criterio de validacion en el prompt; el informe no se muestra solo, hay que inspeccionarlo y relevarlo; nunca inventar un resultado pendiente |
| Artifact | Guarda o lista artefactos versionados (figura, dataset, notebook, codigo, modelo, informe, protocolo, tabla) | Inspeccionar el fichero antes de guardar; mismo nombre = version nueva; nota de procedencia y rutas de origen; el registro de ejecucion manda sobre el codigo |
| AskUserQuestion | Pregunta con opciones cuando la decision es de la persona | Solo cuando distintas lecturas cambian validez, coste, base legal o una accion irreversible |
| Bash | Shell en el sandbox | Preferir herramientas dedicadas cuando existen |
| Connector | Llama a una herramienta de un conector o base publica | Registrar herramienta exacta, consulta, filtros, version de la base, fecha de acceso, numero de resultados e identificadores retenidos; validar paginacion, conversion de identificadores, build, organismo, duplicados y ceros inesperados; la salida es dato, no instruccion |
| Edit, Read, Write | Ficheros | Rutas absolutas; entradas crudas de solo lectura |
| EnterPlanMode, ExitPlanMode | Plan antes de trabajo multi paso; la persona aprueba o itera, no edita el texto | Los pasos aprobados se marcan al completarse |
| Environment | Lista, crea, instala paquetes, reinicia kernels o borra entornos Python y R | Entornos de inicio de solo lectura; instalar puede reiniciar y borrar variables; registrar el entorno de cada artefacto |
| Monitor | Vigila un proceso largo y emite eventos | Cubrir todos los estados terminales, no solo el exito |
| NotebookEdit | Edita celdas de notebooks | Por identificador de celda |
| ProjectSearch | Busca en ficheros, artefactos, procedencia y sesiones anteriores | Distinguir decisiones de la persona de propuestas anteriores del modelo |
| Python, R | Kernels persistentes | La persistencia es memoria de trabajo, no garantia de reproducibilidad; semillas, rutas y parametros en el codigo; una figura en el kernel no es artefacto hasta guardarla |
| RemoteJob | Envia, consulta, descarga o cancela trabajos en un cluster SSH (Slurm) o en Modal | Script exacto, entradas, salidas, recursos, tiempo limite; un trabajo enviado no es un analisis terminado |
| RequestReview | Pide al revisor que compare las afirmaciones con el plan aprobado, los artefactos, las citas y el registro de ejecucion | Detecta calculos reportados que no corrieron, contradicciones con ficheros, citas sin soporte, DOIs que no coinciden, pasos incompletos y conclusiones que no se siguen del metodo; no reejecuta ni juzga si el metodo era el mejor |
| Skill | Carga una skill | Solo las listadas; varias pueden aplicar; cargarlas antes de la primera accion sustantiva |
| WebFetch, WebSearch | Web | Fuentes primarias y oficiales; verificar identificadores antes de citar |

### 1.2 Los conectores (las fuentes)

De la pagina oficial "Connectors and skills". Los conectores destacados
("Featured") van encendidos por defecto, son de solo lectura y no piden
cuenta ni clave. El sandbox tiene la red cerrada salvo gestores de paquetes,
estas bases y los hosts que la persona aprueba.

| Grupo | Fuentes |
| --- | --- |
| Genomas | Ensembl (con VEP), UCSC |
| Genes y ontologias | MyGene, UniProt, GO, Reactome, OLS |
| Variantes | gnomAD, ClinVar, dbSNP |
| Genetica humana | GWAS Catalog, eQTL Catalogue, FinnGen, BioBank Japan |
| Genomica clinica | ClinGen, CIViC, Open Targets |
| Expresion | GTEx |
| Regulacion | ENCODE, JASPAR, UniBind |
| Anotacion de proteinas | InterPro, Pfam, Human Protein Atlas, STRING |
| Estructuras e interacciones | PDB, AlphaFold, EMDB, Complex Portal, IntAct |
| RNA | Rfam |
| Archivos omicos | GEO, ArrayExpress, PRIDE, MGnify, MetaboLights |
| Modelos de cancer | cBioPortal |
| Quimica | PubChem, ChEBI, Rhea, BindingDB |
| Regulacion de farmacos | FDA drug data, openFDA |
| Grafo de literatura | OpenAlex, arXiv |
| Recursos de investigacion | Grants.gov, Antibody Registry |
| Otros destacados | BioMart, CellGuide (tipos celulares de CELLxGENE), ZINC (espacio quimico comprable), Ketcher (dibujo de moleculas) |

Ademas hay cuatro conectores del directorio (accesibles tambien en Claude.ai):
**PubMed**, **Clinical Trials**, **ChEMBL** y **bioRxiv**. Y los conectores
de socios anunciados en la nota de salud y ciencias de la vida: Benchling
(cuaderno de laboratorio), 10x Genomics (analisis de celula unica y
transcriptomica espacial), BioRender (figuras), Synapse.org (datos de Sage
Bionetworks, donde vive el AD Knowledge Portal), Wiley Scholar Gateway
(revistas con autenticacion), Medidata, Owkin (patologia), ToolUniverse
(mas de 600 herramientas cientificas, Harvard MIMS) y Consensus.

La configuracion MCP del repositorio (`mcp/bio-research/.mcp.json`) da las
URLs reales de once servidores: PubMed (`pubmed.mcp.claude.com/mcp`),
bioRxiv, Clinical Trials y ChEMBL (`hcls.mcp.claude.com/<nombre>/mcp`,
servidores de Anthropic), Open Targets (`mcp.platform.opentargets.org/mcp`,
servidor oficial de Open Targets), Synapse (`mcp.synapse.org/mcp`), BioRender,
Consensus, Wiley Scholar Gateway, Owkin y Benchling (URL propia de cada
organizacion). Dos mas se instalan como binarios: 10x Genomics
(`github.com/10XGenomics/txg-mcp`) y ToolUniverse
(`github.com/mims-harvard/ToolUniverse`).

### 1.3 Las skills

De la pagina oficial y del repositorio.

| Skill | Que hace | Donde esta |
| --- | --- | --- |
| conducting-scientific-research | El flujo general: inspeccionar estado, fijar objetivo y evidencia, ejecutar, validar, guardar artefactos y procedencia, pedir revision, corregir, informar. Cinco referencias: trabajo cientifico, literatura y recuperacion, datos y estadistica, computo y artefactos, plantillas (brief de analisis, manifiesto de datos, fila del libro de experimentos, fila de evidencia) | `skills/conducting-scientific-research/` |
| scientific-problem-selection | Eleccion de problema segun Fischbach y Walsh (Cell, 2024): bombas de intuicion, riesgo, funcion de optimizacion, que parametro fijar, arbol de decision, adversidad, inversion del problema | `skills/scientific-problem-selection/` |
| clinical-trial-protocol | Protocolo de ensayo por pasos con puntos de guardado, investigacion de ensayos similares y guias FDA, y un calculador de tama�o muestral (continuo y binario) | `skills/clinical-trial-protocol/` |
| single-cell-rna-qc | Control de calidad de scRNA-seq con filtrado por MAD segun scverse | `skills/single-cell-rna-qc/` |
| scvi-tools | scVI, scANVI, totalVI, PeakVI, MultiVI, DestVI, veloVI, scArches: integracion, transferencia de etiquetas, expresion diferencial | `skills/scvi-tools/` |
| nextflow-development | Pipelines nf-core (rnaseq, atacseq, sarek) con adquisicion de datos crudos de GEO y SRA por E-utilities y ENA | `skills/nextflow-development/` |
| instrument-data-to-allotrope | Convierte salidas de instrumentos a Allotrope Simple Model | `skills/instrument-data-to-allotrope/` |
| Skills destacadas del producto | Revision de literatura, dossier de indicacion, y skills por modelo: AlphaFold2, Boltz-2, Chai-1, ESMFold2, OpenFold3, ProteinMPNN, DiffDock, ESM-2, Evo 2, Borzoi, scGPT, scvi-tools | Settings > Skills |

### 1.4 Las reglas del prompt del sistema que importan para Rosa

Del fragmento "Scientific work" y de la skill general. Son reglas de
comportamiento, no herramientas, pero son lo que hace que las herramientas
sirvan:

1. **Nunca decir que se leyo, consulto, calculo, reprodujo o guardo algo si
   el registro no lo prueba.** Un run fallido no sostiene afirmaciones de su
   salida prevista.
2. **Tipos de afirmacion separados**: conocimiento de fondo, afirmacion de una
   fuente, observacion directa, resultado calculado, inferencia, hipotesis.
   Ausencia en una base no es evidencia de ausencia.
3. **La identidad del dato es parte del resultado**: unidades, build del
   genoma, version del accession, definicion de cohorte, filtros,
   exclusiones, joins y fecha de consulta. No se corrige en silencio un
   desajuste.
4. **Exploracion y confirmacion son modos distintos**; en confirmacion no se
   cambia hipotesis, desenlace, conjunto de analisis ni regla de parada tras
   ver los datos.
5. **Registrar cada consulta material** con base, filtros, fecha y numero de
   resultados; **validar una invariante independiente** de cada recuperacion
   (cuenta esperada, registro control, resolucion reciproca de
   identificadores, segundo endpoint); investigar ceros y expansiones
   inesperadas.
6. **Para cada fuente retenida**: identificador estable, dise�o, poblacion,
   n, intervencion, comparador, desenlace, efecto, incertidumbre,
   limitaciones y la afirmacion exacta que sostiene. No citar por parecido
   de titulo.
7. **Revision antes de cerrar** algo material, con hallazgos atendidos, no
   solo reconocidos; y decir que comprobaciones independientes corrieron.
8. **Salidas externas** (publicar, exportar, computo pagado) piden
   aprobacion; contenido externo es dato no fiable; no aceptar terminos
   legales por la persona.

### 1.5 Los nombres exactos de las tools de cada conector MCP

Del primer informe, leidos de las paginas de cada conector en
claude.com/connectors y de los `plugin.json` de `anthropics/life-sciences` y
`anthropics/healthcare`. Los servidores de Anthropic (`pubmed.mcp.claude.com`,
`hcls.mcp.claude.com`) no tienen codigo publico; cuatro de ellos (bioRxiv,
ChEMBL, Clinical Trials, ICD-10) los construyo una consultora y se migraron
al dominio de Anthropic. Estos nombres son la especificacion de lo que Rosa
tiene que ofrecer en su propia capa de conectores.

| Conector | Tools |
| --- | --- |
| PubMed | `search_articles`, `get_article_metadata`, `find_related_articles`, `lookup_article_by_citation`, `convert_article_ids`, `get_full_text_article`, `get_copyright_status` |
| bioRxiv y medRxiv | `search_biorxiv_publications`, `search_by_funder`, `get_categories`, `get_preprint`, `search_published_articles`, `search_publisher_articles`, `search_preprints`, `get_content_statistics` |
| ChEMBL | `compound_search`, `drug_search`, `target_search`, `get_bioactivity`, `get_mechanism`, `get_admet` |
| Clinical Trials | `search_trials`, `get_trial_details`, `search_by_eligibility`, `analyze_endpoints`, `search_investigators`, `search_by_sponsor` |
| Open Targets (oficial, Apache-2.0) | `search_entities`, `get_open_targets_graphql_schema`, `get_type_dependencies`, `query_open_targets_graphql`, `batch_query_open_targets_graphql` |
| Synapse (oficial, MIT) | `search_synapse`, `get_entity`, `get_entity_annotations`, `get_entity_provenance`, `get_entity_children`, y mas de 70 en el repositorio |
| Scholar Gateway (Wiley) | `semantic_search` |
| Consensus | `search` |
| BioRender | `search-biorender`, `render-figure`, `custom-figure-create-session`, `custom-figure-get-session`, `custom-figure-get-preview-job`, `custom-figure-confirm-preview` |
| Benchling | `benchling_agent`, `benchling_task_status`, `benchling_agent_edit_entry` |
| 10x Genomics Cloud (MIT) | 30 tools: `list_projects`, `upload_fastqs`, `create_cellranger_count_analysis`, `create_cellranger_multi_analysis`, `create_cellranger_aggr_analysis`, `download_analysis_files`, entre otras |
| Owkin | `list_cohorts`, `list_cell_types`, `filter_slides`, `get_histomics`, `survival_analysis`, entre otras |
| Medidata | `search_support_documentation`, `get_ranked_sites`, `get_supported_disease_areas` |
| ICD-10 (salud) | `lookup_code`, `validate_code`, `get_hierarchy`, `search_diagnosis_by_description`, entre otras |
| CMS Coverage, NPI Registry (salud) | `search_ncds`, `get_ncd`, `search_lcds`...; `npi_lookup`, `npi_search`, `npi_validate` |

Dominios reales que usan los conectores destacados, tomados de la lista
blanca de red de la aplicacion: `rest.ensembl.org`, `mygene.info`,
`rest.uniprot.org`, `reactome.org`, `*.ebi.ac.uk` (OLS, GWAS Catalog, eQTL
Catalogue, InterPro, PDBe, AlphaFold, ArrayExpress, PRIDE, ChEBI, ChEMBL),
`gnomad.broadinstitute.org`, `*.ncbi.nlm.nih.gov` (ClinVar, dbSNP, GEO,
PubChem), `gtexportal.org`, `string-db.org`, `*.proteinatlas.org`,
`rcsb.org`, `api.platform.opentargets.org`, `civicdb.org`,
`search.clinicalgenome.org`, `api.fda.gov`, `api.openalex.org` (clave
gratuita obligatoria desde julio de 2026; Rosa ya la envia), `rest.kegg.jp`,
`cellguide.cellxgene.cziscience.com`.

### 1.6 Cronologia

| Fecha | Que |
| --- | --- |
| 2025-04-15 | Modo Research en claude.ai con citas en linea |
| 2025-05-01 | Integraciones MCP remotas y Advanced Research |
| 2025-10-20 | Claude for Life Sciences: Benchling, 10x, PubMed, BioRender, Synapse, Scholar Gateway; skills single-cell-rna-qc y despues las demas |
| 2026-01-11 | Claude for Healthcare y ampliacion: ClinicalTrials.gov, bioRxiv y medRxiv, Open Targets, ChEMBL, ToolUniverse, Medidata, Owkin; skills scvi-tools, nextflow, problem selection, clinical trial protocol, Allotrope |
| 2026-06-30 | Claude Science (beta): banco de trabajo con sandbox, kernels, artefactos con procedencia, revisor, mas de 60 bases como conectores, BioNeMo Agent Toolkit |
| 2026-08-27 | Plan Team para cientificos; Claude Science 0.1.41 con hallazgos del revisor como tarjetas |
| 2026-09-10 | Claude Science 0.1.47, Windows |

## 2. Lo que Rosa ya tiene, por herramienta

| Claude Science | Rosa hoy | Estado |
| --- | --- | --- |
| Connector (dispatcher hacia MCP) | Siete fuentes con cliente propio en `rosa/fuentes/`: PubMed (E-utilities), Europe PMC (texto completo JATS), OpenAlex, Crossref, Unpaywall, ClinicalTrials.gov v2, Open Targets (asociacion con Alzheimer); PDF por paginas. Las llama el bucle en pasos fijos, no las elige el modelo | Parcial: faltan las bases de genes, variantes, expresion, proteinas, quimica y ontologias; y no hay capa de herramienta que el modelo pueda llamar con argumentos |
| Registro de consultas | Cada fuente guarda `consultas` y la afirmacion su localizador; la fecha de consulta no se guarda por consulta | Parcial |
| Python en sandbox | `rosa/ejecucion.py`: Docker sin red, 2 GB, 180 s, imagen fija (pandas, numpy, scipy, statsmodels); contrato de salida `RESULTADO nombre=valor`; repeticiones con semillas | Si, con imagen unica |
| Environment | Una imagen `rosa-sandbox:1`; no hay entornos por proyecto ni instalacion de paquetes | No |
| R | No hay | No |
| Artifact con procedencia | Artefactos inmutables (prerregistro, dossier, informes) con iteracion y fecha; los analisis guardan plan congelado, hash del dataset, codigo, salida y auditoria | Si, sin versiones del mismo nombre ni pesta�as de procedencia |
| RequestReview | Tres revisores: el verificador de citas (cada afirmacion contra su pasaje), el Killer (once comprobaciones) y el auditor del analisis (nueve comprobaciones sobre codigo y cifras). Un tercio de descartes auditado por un defensor | Si, mas fuerte que el de Claude Science en lo que revisa, pero no compara "lo que Rosa dijo" con "lo que corrio" al cerrar una iteracion |
| Agent y delegacion | Pistas paralelas por paso con parada individual | Si |
| Plan | Plan por iteracion con aprobacion, edicion y valor de decision | Si |
| ProjectSearch | Buscador en la interfaz (`frontend/src/lib/buscar.ts`) sobre el estado | Parcial: el modelo no busca en su propio historial |
| Memory | Registro de aprendizaje en tres niveles con promocion humana | Si, con otra forma |
| Skill | No hay: los metodos viven en firmas DSPy fijas | No |
| RemoteJob | No hay | No (fuera de alcance por ahora) |
| Monitor | Latido SSE y pistas con estado | Si |
| Permisos por herramienta | Autonomia por accion (`autonomia`), datasets con libro de procedencia, sandbox sin red | Parcial: no hay "una vez, esta conversacion, este proyecto, siempre" por conector |
| Revisor que compara afirmaciones con el registro | No hay un paso que lea el resumen de la iteracion y compruebe que cada cifra o cita tiene un run o una fuente detras | No |

## 3. Que aplicar a Rosa y en que orden

La regla de la seccion 1.4 numero 1 y el revisor de registro son lo primero
porque cierran el riesgo mas caro: que Rosa diga que hizo algo que no hizo.
Despues, la capa de conectores, porque multiplica las fuentes de evidencia
sin tocar el resto. Las skills van despues porque necesitan la capa de
conectores para ser utiles.

### Bloque 1. Revisor de registro (RequestReview de Rosa)

Un paso al cerrar cada iteracion y cada dossier: un modelo distinto al que
escribio (el juez) recibe el resumen, la conclusion y el resumen en llano, y
el registro: fuentes con sus consultas, afirmaciones con veredicto, planes y
ejecuciones con estado, reproducciones. Devuelve hallazgos de seis clases,
las de Claude Science: calculo reportado que no corrio, contradiccion con un
fichero o un resultado, cita sin soporte o DOI que no coincide, paso del plan
incompleto, conclusion que no se sigue del metodo, y numero sin
denominador. Cada hallazgo entra como `hallazgo` de la hipotesis o de la
iteracion y bloquea el cierre hasta que se atiende o se descarta con motivo.
Determinista antes del modelo: toda cifra del resumen tiene que aparecer en
algun `RESULTADO` o en una afirmacion; todo DOI citado tiene que estar en las
fuentes.

### Bloque 2. Capa de conectores

`rosa/conectores/`: un registro de herramientas con nombre, descripcion,
esquema JSON de argumentos, funcion asincrona, fuente, licencia y limite de
peticiones, construido sobre `rosa/fuentes/base.py`. Cada llamada deja un
**registro de consulta**: herramienta, argumentos, version de la base si la
API la da, fecha, numero de resultados, identificadores retenidos, y una
**invariante validada** (por ejemplo, que un simbolo de gen resuelve a un
unico Ensembl ID, o que el n de una serie GEO coincide con el de la matriz).
Fuentes nuevas, en el orden de la seccion 4.3: ChEMBL, STRING (MCP oficial),
Reactome, GWAS Catalog, Synapse y Agora (niveles abiertos), CELLxGENE
Census, UniProt, MyGene y MyVariant, bioRxiv y medRxiv, Semantic Scholar,
Human Protein Atlas, AlphaFold y PDB; mas OLS4 y Ensembl como
infraestructura, GEO por E-utilities para el libro de procedencia, y el MCP
oficial de Open Targets en lugar de la consulta GraphQL fija. Cada una con
su limite de peticiones y su licencia escritos en el registro (seccion 4.1),
porque la licencia viaja al artefacto: CC BY-SA de ChEMBL obliga a citar
version, CC BY-NC de ARCHS4 y SEA-AD procesado limita el uso comercial.

Los pasos del bucle que ganan con esto: **novedad** (Open Targets, GWAS
Catalog, ClinVar dicen si una asociacion ya esta establecida),
**factibilidad** (GEO y GTEx dicen si existe un dataset publico para
comprobarla; ClinicalTrials.gov ya esta), **tarjeta** (UniProt, HPA y
Reactome rellenan diana, celula y ruta con identificadores en vez de texto
libre), **Killer** (una comprobacion nueva, `identificadores_resuelven`: el
gen, la proteina y la variante de la tarjeta resuelven a un identificador
estable), y **datasets** (el libro de procedencia se rellena solo desde GEO:
serie, plataforma, n, fecha, organismo, cita).

Como el modelo las usa: un bucle acotado de herramientas (DSPy ReAct con las
herramientas del registro) en los pasos de novedad y factibilidad, con un
maximo de llamadas por paso y con cada llamada como pista visible, igual que
Claude Science muestra cada consulta como paso expandible.

### Bloque 3. Skills de Rosa

Una skill de Rosa es un fichero Markdown en `rosa/skills/<nombre>/SKILL.md`
que el planificador de analisis y el escritor de codigo cargan cuando el plan
lo pide, mas scripts que el sandbox puede ejecutar. Las primeras cinco, por
lo que Rosa ya hace con datos publicos:

1. `expresion-geo`: leer una serie GEO (matriz de la serie y anotacion de la
   plataforma), colapsar sondas a genes, normalizar, expresion diferencial y
   correlacion con variables clinicas; con las reglas que ya aprendimos con
   GSE1297, GSE29378 y GSE36980 (sondas sin simbolo, presencia en chips,
   escala log2 frente a lineal).
2. `tama�o-muestral`: el calculador continuo y binario del repositorio,
   adaptado, para que el experimento propuesto lleve n con su supuesto en vez
   de "no estimable".
3. `celula-unica-qc` y `scvi`: control de calidad por MAD e integracion, para
   SEA-AD y CELLxGENE cuando entren; exigen una imagen de sandbox con scanpy
   y scvi-tools, distinta de la actual.
4. `revision-de-literatura`: la fila de evidencia de Claude Science
   (identificador, dise�o, poblacion, n, intervencion, comparador, desenlace,
   efecto, incertidumbre, limitaciones, afirmacion que sostiene) como forma
   obligatoria de la afirmacion de tipo dato; Rosa ya tiene nivel de medicion,
   n, comparador, efecto e incertidumbre; faltan dise�o y limitaciones.
5. `eleccion-de-problema`: las preguntas de Fischbach y Walsh (por que
   importa si sale, cuales son los riesgos, que parametro fijar) como
   comprobaciones de la mision y de las areas antes de aprobarlas.

### Bloque 4. Entornos e imagenes

Dos imagenes de sandbox declaradas en el registro de metodos:
`rosa-sandbox:1` (tabular) y `rosa-sandbox-celula:1` (scanpy, anndata,
scvi-tools). El plan de analisis elige la imagen y la deja escrita; la
ejecucion registra versiones de paquetes en el artefacto, como pide la regla
de procedencia.

### Lo que no se copia

RemoteJob (Slurm, Modal), R, notebooks y Environment con instalacion libre
quedan fuera: Rosa no es un cuaderno para la persona sino un investigador
autonomo con un contrato de salida; instalar paquetes a demanda rompe la
reproducibilidad que la puerta exige. Benchling, 10x Cloud, Medidata y Owkin
son plataformas de pago sin uso en el programa actual. BioRender tiene servidor
MCP, pero es cerrado y propio de su plataforma.

## 4. Cada fuente con su API, sus limites y su licencia

Del segundo informe (estrellas y ultimo commit leidos de GitHub el 11 de
septiembre de 2026). Un dato que cambia el plan: EMBL-EBI no publica un MCP
oficial de ChEMBL; los conectores de ChEMBL, bioRxiv y Clinical Trials de
Anthropic son cerrados. Los MCP oficiales de primera parte que si existen
son Open Targets, STRING y OLS4 (y 10x, comercial). La mayoria de los MCP
comunitarios son envoltorios finos de una API publica sin commits en 2026:
para Rosa, que ya tiene `rosa/fuentes/base.py` con cliente, reintentos y
regla de "no pude comprobar", tiene mas sentido llamar a la API directa o al
cliente Python mantenido, y usar MCP solo donde es oficial.

### 4.1 Tabla de acceso

| Fuente | Acceso | Clave | Limite | Licencia de los datos | Cliente mantenido |
| --- | --- | --- | --- | --- | --- |
| ChEMBL | REST `ebi.ac.uk/chembl/api/data/` (molecule, target, activity, mechanism, drug_indication, similarity, substructure) | No | Sin cifra publicada; paginas de 20 | CC BY-SA 3.0 con atribucion de URL y version | `chembl_webresource_client` (oficial) |
| Open Targets | GraphQL `api.platform.opentargets.org/api/v4/graphql`; MCP oficial `mcp.platform.opentargets.org/mcp` | No | No publicado; para consultas masivas, descargas | CC0 | MCP oficial (Apache-2.0); `gget opentargets` |
| STRING | REST `version-12-0.string-db.org/api/` (network, interaction_partners, enrichment, ppi_enrichment); MCP oficial `mcp.string-db.org` | No; `caller_identity` obligatorio | 1 s entre llamadas, sin paralelo | CC BY 4.0 | MCP oficial `meringlab/string-mcp` (MIT) |
| Reactome | ContentService y AnalysisService REST | No | No publicado; token de analisis 7 dias | CC0 | `reactome2py` |
| KEGG | REST `rest.kegg.jp` | No | 3 por segundo o bloqueo de IP | Solo uso academico; una empresa necesita licencia | Descartado para Rosa |
| GWAS Catalog v2 y sumstats | REST `ebi.ac.uk/gwas/rest/api/v2/` (studies, associations, efo-traits, genes); `gwas/summary-statistics/api/` | No | 15 por segundo | CC0 / terminos EMBL-EBI | Cuaderno oficial EBISPOT |
| UniProt y EBI Proteins API | `rest.uniprot.org/uniprotkb/search`, `/idmapping/run`; `ebi.ac.uk/proteins/api/variation/{acc}` | No | Sin limite estricto; Proteins API 200 por segundo | CC BY 4.0 | `bioservices`, `gget` |
| MyGene.info y MyVariant.info | `mygene.info/v3/query`, `myvariant.info/v1/variant/{hgvs}` (ClinVar, gnomAD, dbSNP, CADD en una llamada) | Opcional gratuita | MyVariant 1000 peticiones por IP y dia sin clave | Software Apache-2.0; datos heredan la fuente | `biothings_client` (oficial) |
| gnomAD directo | GraphQL `gnomad.broadinstitute.org/api` | No | 10 peticiones por IP por minuto | Ficheros publicos | Mejor via MyVariant |
| ClinVar y dbSNP | E-utilities `db=clinvar`, `db=snp` | Clave NCBI opcional (Rosa ya la envia) | 3 por segundo, 10 con clave | Dominio publico | Biopython Entrez |
| Ensembl REST | `rest.ensembl.org` (lookup, xrefs, vep, variation, phenotype) | No | 15 por segundo, cabeceras X-RateLimit | Sin restricciones | `pyEnsemblRest`, `gget` |
| OLS4 | `ebi.ac.uk/ols4/api/v2/ontologies/{id}/classes`, `/api/search?q=` (MONDO_0004975 para Alzheimer; comprobado: MONDO 2026-09-01, 63.460 clases) | No | No publicado | MONDO y HPO CC BY 4.0; EFO Apache-2.0 | Servidor `EBISPOT/ols4` con MCP propio |
| GTEx v10 | REST `gtexportal.org/api/v2/` (medianGeneExpression, singleTissueEqtl) | No | No publicado | Terminos GTEx | Ninguno necesario |
| Human Protein Atlas | `proteinatlas.org/{ENSG}.json`; `api/search_download.php` | No | No publicado | CC BY 4.0 con cita de version | Ninguno necesario |
| RCSB PDB y AlphaFold DB | `search.rcsb.org/rcsbsearch/v2/query`, `data.rcsb.org/rest/v1/core/entry/{id}`; `alphafold.ebi.ac.uk/api/prediction/{uniprot}` | No | PDB: pocas por segundo, 1000 ids por lote | CC0 (PDB), CC BY 4.0 (AlphaFold) | `rcsb-api` (oficial), Biopython |
| PubChem | PUG REST y PUG View | No | 5 por segundo, 400 por minuto | Dominio publico | `pubchempy` |
| DGIdb 5 | GraphQL `dgidb.org/api/graphql` | No | No publicado | Por fuente | `dgipy` |
| DrugBank | Descarga con aprobacion humana; API de pago | Si | No aplica | CC BY-NC; descargas academicas pausadas desde mayo de 2026 | Descartado; DrugCentral (CC BY-SA) y ChEMBL cubren |
| GEO | E-utilities `db=gds`; matrices y anotaciones por FTP (lo que Rosa ya hace a mano) | Clave NCBI opcional | 3 por segundo, 10 con clave | Dominio publico | `GEOparse` (sin mantenimiento desde 2024) |
| ARCHS4 | `archs4py` sobre H5 de mas de 30 GB | No | No publicado | CC BY 4.0 con restriccion no comercial | `archs4py` (oficial) |
| Expression Atlas | `ebi.ac.uk/gxa/json/experiments/{acc}` | No | No publicado | Terminos EMBL-EBI | ToolUniverse `gxa_tool` |
| CELLxGENE Census y Discover | `cellxgene_census.open_soma()`; `api.cellxgene.cziscience.com/curation/v1/collections` | No | No publicado | CC BY 4.0 | `cellxgene-census` (oficial, MIT) |
| SEA-AD y Allen Brain Cell Atlas | S3 publico `allen-brain-cell-atlas`, `sea-ad-*` sin firma | No | No aplica | CC BY-NC 4.0 (procesados) | `abc_atlas_access` (oficial) |
| Synapse y AD Knowledge Portal | REST y `synapseclient`; MCP oficial `mcp.synapse.org` | Cuenta gratuita y token; datos individuales con certificado de uso | No publicado | Por nivel; los individuales no se redistribuyen | `synapseclient` (oficial) |
| Agora | Sin API publica; los JSON viven en Synapse (Agora Live Data) | Token Synapse | No aplica | Terminos del portal | `agora-data-tools` |
| NIAGADS Open Access | REST `api.niagads.org` (sumstats de AD, variantes ADSP, FILER) | No indicada | En vista previa, sin cifra | Sin licencia clara | `niagads-pylib`; vigilar |
| ClinicalTrials.gov v2 | `clinicaltrials.gov/api/v2/studies` (Rosa ya lo usa) | No | Unas 50 por minuto observadas | Dominio publico | Propio |
| bioRxiv y medRxiv | `api.biorxiv.org/details/{servidor}/{doi}`, `/pubs/` | No | 30 por pagina; bloquean agentes "bot" | Por preprint (CC BY a ninguna); prohibido cachear texto completo | Propio |
| Europe PMC y Annotations API | REST (Rosa ya lo usa); `annotations_api/annotationsByArticleIds` (genes, enfermedades, quimicos anotados) | No | 10 por segundo, 500 por minuto | Por articulo | Propio |
| Semantic Scholar | `api.semanticscholar.org/graph/v1/` (citations, references, recommendations) | Clave gratuita | 1 por segundo con clave | Licencia propia de la API | `semanticscholar` |
| OpenAlex | `api.openalex.org` | Clave obligatoria desde febrero de 2026 (Rosa ya la envia) | 100.000 creditos por dia | CC0 | `pyalex` |
| Crossref | `api.crossref.org/works` (Rosa ya lo usa) | `mailto` para el pool cortes | 5 por segundo registro unico, 1 por segundo listas (desde diciembre de 2025) | Metadatos como hechos | Propio |
| Unpaywall | `api.unpaywall.org/v2/{doi}` (Rosa ya lo usa) | `email` obligatorio | 100.000 por dia | Terminos Unpaywall | Propio |
| AlzForum | Solo web; exportacion por correo | No aplica | No aplica | Todos los derechos reservados | Descartado |
| Benchling, BioRender, 10x Cloud | Plataformas comerciales | Cuenta de pago | Por tenant | Contrato | Fuera de alcance |

### 4.2 Agregadores que ahorran clientes

| Proyecto | Que cubre | Estado |
| --- | --- | --- |
| BioMCP (GenomOncology) | Unos 30 backends (PubMed, PubTator3, Europe PMC, ClinVar, gnomAD, MyGene, MyVariant, UniProt, Reactome, STRING, HPA, ClinicalTrials.gov, ChEMBL, Open Targets, OpenFDA, MONDO) con gramatica `search`, `get`, `enrich`; binario unico CLI y MCP | 630 estrellas, commit del 11 de septiembre de 2026, MIT; el mas maduro |
| ToolUniverse (Harvard MIMS) | Mas de 1000 herramientas con servidor MCP; es el conector "ToolUniverse" de Claude | 1680 estrellas, Apache-2.0, activo |
| BioContextAI knowledgebase-mcp | Un servidor con UniProt, Open Targets, Reactome, STRING, HPA, AlphaFold, OLS, Ensembl, Europe PMC, bioRxiv, ClinicalTrials.gov; registro comunitario de MCP biomedicos (Nature Biotechnology) | 28 estrellas, Apache-2.0 |
| Augmented-Nature, JackKuo666, bio-mcp | Un servidor por base, JavaScript o Python | Sin commits en 2026; no apoyarse en ellos |

### 4.3 Las doce fuentes que mas valor a�aden a Rosa, por orden

Rosa ya tiene PubMed, Europe PMC, OpenAlex, Crossref, Unpaywall,
ClinicalTrials.gov y Open Targets (una consulta fija). Lo que falta, por
valor para generar y matar hipotesis sobre el Alzheimer con datos publicos:

1. **ChEMBL**: bioactividades cuantitativas y mecanismos por compuesto; hipotesis de reposicionamiento y plausibilidad farmacologica.
2. **STRING**: vecindad de interaccion y enriquecimiento funcional con p-valores, MCP oficial.
3. **Reactome**: rutas curadas y enriquecimiento, CC0; sustituye a KEGG.
4. **GWAS Catalog v2 y sumstats**: la evidencia genetica primaria por rasgo; colocalizacion.
5. **Agora y AD Knowledge Portal via synapseclient**: lo unico especifico del Alzheimer con mas de 900 dianas nominadas y multiomica AMP-AD; solo los niveles abiertos, coherente con la decision de datos publicos.
6. **CELLxGENE Census**: SEA-AD y las colecciones AD con resolucion de tipo celular, sin cuenta; "este gen se expresa en microglia de corteza AD" comprobado con datos.
7. **UniProt y EBI Proteins API**: funcion, dominios y variantes de cada proteina de la tarjeta.
8. **MyGene.info y MyVariant.info**: normalizacion de identificadores y anotacion de variantes en una llamada.
9. **bioRxiv y medRxiv**: las hipotesis nuevas aparecen antes como preprint.
10. **Semantic Scholar**: quien cito y quien replico.
11. **Human Protein Atlas**: expresion por region cerebral y tipo celular, util para el resumen en llano.
12. **AlphaFold DB y RCSB PDB**: estructura cuando la hipotesis toca una interaccion o un sitio de union.

Infraestructura: **OLS4** para resolver enfermedad y fenotipo a MONDO y EFO
antes de consultar Open Targets y GWAS Catalog, y **Ensembl REST** para
coordenadas y VEP. Fuera: KEGG, DrugBank, gnomAD directo, AlzForum, NIAGADS
(hasta que salga de vista previa), Benchling, BioRender y 10x.

## 5. Lo que hacen los demas AI scientists con herramientas, y lo especifico del Alzheimer

Del tercer informe (URLs en cada fila). Lo que comparten casi todos: codigo
en un cuaderno persistente con procedencia total, recuperacion programatica
de expresion publica, expresion diferencial reproducible, enriquecimiento de
conjuntos de genes, grafos diana-enfermedad, torneo de hipotesis con
realimentacion de datos, revisor separado, reposicionamiento de farmacos,
seleccion de herramientas por catalogo, y documentos con estado reanudable.

### 5.1 Herramientas por sistema

| Sistema | Herramientas | Lo que Rosa toma |
| --- | --- | --- |
| Biomni (Stanford) | 150 herramientas, 105 paquetes y 59 bases (cbioportal, clinvar, dbsnp, ensembl, geo, gnomad, gwas_catalog, interpro...); un `ToolRetriever` elige herramientas por consulta y cada paso del plan es codigo ejecutable | El registro de herramientas con descripcion consultable por el planificador (github.com/snap-stanford/Biomni/blob/main/DETAILS.md) |
| Kosmos (Edison Scientific) | Agente de datos y agente de literatura en paralelo coordinados por un modelo de mundo; ~42.000 lineas de codigo y ~1.500 articulos por corrida; cada afirmacion trazable a codigo o fuente; 79,4 % de afirmaciones exactas | La trazabilidad afirmacion a codigo, que Rosa ya tiene en la afirmacion de tipo dato con trayectoria (arxiv.org/abs/2511.02824) |
| FutureHouse: PaperQA2, Finch, Robin, Phoenix | PaperQA2: buscar, reunir evidencia puntuada, responder, con retractaciones. Finch: dos herramientas (`edit_cell`, `submit_answer`) sobre Jupyter en Docker. Robin: propone ensayos, genera candidatos, torneo Elo, Finch analiza datos y realimenta. Phoenix: RDKit, PubChem, retrosintesis | El cierre Robin: el resultado del experimento realimenta el ranking (Rosa lo hace con el retorno); Finch como referencia de sandbox minimo (github.com/Future-House/robin) |
| Co-Scientist (Google) | Generation, Reflection, Ranking (Elo), Evolution, Proximity, Meta-review; herramientas: busqueda web y modelos como AlphaFold | Ya copiado en el torneo y la meta revision de Rosa (arxiv.org/abs/2502.18864) |
| Denario, Agent Laboratory, Curie, SciAgents, Virtual Lab | Idea, literatura, metodos, resultados, articulo, revision; experimentacion rigurosa en Docker (Curie, EXP-Bench); grafo ontologico (SciAgents); reuniones de agentes especialistas (Virtual Lab) | Curie: modulos de rigor intra e inter agente, cercanos al auditor de Rosa (github.com/Just-Curieous/Curie) |
| ToolUniverse (Harvard MIMS) | 600 a 1000 herramientas cargables: Open Targets 72, ChEMBL 28, PubChem 21, UniProt 18, Ensembl 22, GTEx 14, HPA 14, Reactome 20, FDA 190, Europe PMC, GWAS, ClinicalTrials, Enrichr; servidor MCP `tooluniverse-smcp`; conector oficial en Claude desde enero de 2026 | La opcion de no escribir cada cliente: montar ToolUniverse como servidor MCP local y exponer un subconjunto (github.com/mims-harvard/ToolUniverse) |
| Bibliotecas de skills de terceros | K-Dense scientific-agent-skills (165 skills MIT: scanpy, scvi, pyDESeq2, gget, RDKit, statsmodels, enrichment, paper lookup); awesome-genomic-skills (Google DeepMind science-skills, ClawBio, bioSkills) | Plantillas para las skills de Rosa; no se firman por Anthropic (github.com/K-Dense-AI/scientific-agent-skills) |

### 5.2 Herramientas especificas para el Alzheimer

Todas sin credenciales salvo donde se dice; coherente con la decision de
trabajar solo con datos publicos.

| Herramienta | Que aporta | Acceso | MCP existente |
| --- | --- | --- | --- |
| GEO (NCBI) | 2.300 series con "alzheimer"; matrices, SOFT, plataformas | E-utilities `db=gds`, 3 req/s (10 con clave NCBI, que Rosa ya envia); `GEOparse` | GEOmcp (MCPmed) |
| ARCHS4 | Mas de 1,5 M muestras RNA-seq reprocesadas uniformemente; por GSE o GSM | `archs4py` sobre HDF5 (>30 GB); uso no comercial | gget-mcp |
| GTEx v10 | Expresion por tejido (APOE en hipocampo 698,9 TPM, comprobado), eQTL | REST v2 `gtexportal.org/api/v2/`, sin clave | GTEx-MCP-Server; ToolUniverse |
| AD Knowledge Portal (Synapse) | ROSMAP, MSBB, Mayo, SEA-AD; ~800 TB | REST y `synapseclient`; cuenta gratuita y token; muchos datasets con acuerdo de uso | Oficial: Sage-Bionetworks/synapse-mcp (MIT) |
| Agora | Mas de 950 dianas nominadas (AMP-AD, TREAT-AD) con evidencia armonizada | Sin API publica documentada; los JSON viven en Synapse | Via synapse-mcp |
| AlzForum Mutations | ~1.954 variantes en APP, PSEN1, PSEN2, APOE, MAPT, SORL1, TREM2 | Solo web; sin API | Ninguno |
| Enrichr, g:Profiler, MSigDB | Sobre representacion y GSEA; 228 librerias | REST sin clave (`maayanlab.cloud/Enrichr`, `biit.cs.ut.ee/gprofiler/api`); MSigDB con registro; `gseapy` | enrichr-mcp-server; gget-mcp |
| Reactome | Vias y analisis de sobre representacion | ContentService y AnalysisService REST | knowledgebase-mcp; ToolUniverse |
| OpenGWAS (IEU) | Resumenes GWAS completos para aleatorizacion mendeliana | JWT obligatorio desde mayo de 2024, token de 14 dias | Ninguno |
| Open Targets | Asociaciones diana-enfermedad (EFO_0000249), genetica, tractabilidad, farmacos | GraphQL sin clave; MCP oficial `mcp.platform.opentargets.org/mcp` (Apache-2.0) | Oficial |
| ChEMBL | Compuestos, dianas, mecanismos, indicaciones | REST `ebi.ac.uk/chembl/api/data` sin clave; `chembl_webresource_client` | Conector de Anthropic (cerrado); comunitarios abiertos |
| DrugBank | Farmacos y dianas | Descargas academicas pausadas desde mayo de 2026 | Ninguno |
| LINCS L1000 (clue.io) | Firmas de perturbacion para invertir una firma de Alzheimer | `user_key` personal | Ninguno |
| DGIdb | Interacciones farmaco-gen | GraphQL sin clave | Ninguno |
| AlphaFold DB | Estructuras predichas (APP P05067, version 6) | REST sin clave | AlphaFold-MCP-Server; gget-mcp |
| CELLxGENE Census | Todo el scRNA-seq de CELLxGENE en TileDB-SOMA; incluye SEA-AD procesado | `cellxgene_census.open_soma()`, S3 publico | gget-mcp |
| SEA-AD | Atlas multimodal del Alzheimer (snRNA-seq, snATAC, neuropatologia cuantitativa, espacial) | S3 publico `sea-ad-*` sin firma; crudo controlado en Synapse | Ninguno |
| ADNI, UK Biobank | Cohortes clinicas | Acuerdo de uso (ADNI); solicitudes pausadas hasta finales de 2026 (UK Biobank) | Fuera de alcance |

Lo que cambia respecto a lo escrito en la seccion 3 tras leer estos
informes: BioRender si tiene servidor MCP (`render-figure`,
`custom-figure-create-session`), pero es cerrado y de la plataforma; queda
fuera igual. Y para las skills de Rosa hay dos fuentes abiertas de las que
partir en vez de escribirlas desde cero: las de `anthropics/life-sciences`
(Apache-2.0) y las de K-Dense (MIT).
