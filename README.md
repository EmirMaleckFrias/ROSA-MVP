# Rosa

Rosa es la IA de investigacion del Alzheimer Project (AI Robotix e INTEC): un
bucle que busca literatura, extrae afirmaciones con cita a la pagina exacta,
las verifica, mantiene un modelo de mundo, propone hipotesis y las somete a un
torneo, siempre con una persona decidiendo en la cola. Este repositorio tiene
el backend (Python, DSPy, GEPA) y la interfaz (React).

## Arrancar Rosa

Con dos ventanas de terminal, o con el script que hace las dos cosas:

```bash
./rosa.sh
```

Eso arranca el servidor de Rosa (puerto 8765), la interfaz (puerto 5174) y abre
el navegador. A mano:

```bash
uv run python -m rosa.main          # el servidor y el bucle
cd frontend && npm run dev          # la interfaz en http://localhost:5174
```

Si el servidor no esta, la interfaz muestra datos de muestra con una corrida
simulada y lo avisa con una franja amarilla.

La clave del gateway va en `.env` (`ROSA_GATEWAY_KEY`), copiada del `.env` del
RAG. Nunca al codigo ni a un chat.

## Lo que trae ROSA2018 (septiembre de 2026)

El documento de concepto del programa y el plan completo del sistema (ver
`PLAN-ROSA2018.md`) a�aden a Rosa estas piezas. Todas estan en la interfaz;
nada de esto se opera desde la terminal.

- **Mision y areas.** Al arrancar la primera corrida Rosa propone la mision
  (poblacion, etapa, celula o tejido, mecanismo, tipo de intervencion,
  capacidades del laboratorio, presupuesto en llamadas, dolares y horas) y las
  areas de investigacion que comparo para elegir por donde empezar. Se
  aprueba con el primer plan o en Objetivo y datos. Cada corrida lleva su
  pregunta con plantilla (contexto, etapa, intervencion, comparador,
  desenlace, ventana, unidad biologica, mecanismos, decision, umbral).
- **Datasets con libro de procedencia.** En Objetivo y datos se sube un CSV,
  TSV o JSON: el servidor calcula el sha256, cuenta filas y columnas, detecta
  valores centinela y prepara el diccionario. Antes de aprobar el contrato hay
  que completar origen, licencia y si el uso con IA esta autorizado. Las filas
  individuales no salen hacia un modelo salvo que el libro lo permita (solo
  datos abiertos o sinteticos).
- **Puerta de reproduccion.** Rosa no descubre con datos hasta reproducir
  tres analisis publicados dentro de una tolerancia fijada antes (hay tres
  precargados: GSE1297, OASIS-1, SEA-AD). Se puede eximir con motivo: queda
  registrado como cambio de politica.
- **Analisis in silico.** Desde la ficha de una hipotesis, con un dataset
  aprobado: Rosa congela un plan de analisis sin ver las filas, escribe el
  codigo, lo corre en un sandbox sin red (Docker Desktop encendido, o Apple
  `container`), interpreta las cifras contra el umbral del plan y un auditor
  independiente dice si el analisis vale. Solo lo valido entra como evidencia.
  Con datasets sinteticos funciona sin Docker, con aislamiento blando.
- **Hypothesis Killer.** Cada hipotesis pasa una lista fija de catorce
  comprobaciones; la decision (avanzar, reformular, suspender, descartar en
  este contexto) se deriva por regla y cada comprobacion tiene una
  consecuencia declarada cuando falla (`rosa/killer.py`, tabla
  `CONSECUENCIA`): descartan citas, fidelidad y supuestos; reformulan
  causalidad, falsabilidad, factibilidad, redundancia, direccion de la
  evidencia, unidades y novedad; suspenden fuente primaria, riesgo de sesgo
  e identificadores que no resuelven; una sola cohorte avanza con la certeza
  limitada. Una comprobacion por regla que encontro algo (una cifra fuera
  del pasaje) no la puede borrar el juez. Reformular crea una version nueva
  (hasta dos por politica). Un tercio de los descartes lo audita otro modelo
  defendiendo la hipotesis. Todo queda en el registro de decisiones, y cada
  comprobacion se puede etiquetar a mano: es el conjunto dorado con el que se
  mide el acuerdo juez-humano (kappa por comprobacion, pantalla Calidad).
- **Candidatas y dossier.** El ranking muestra las candidatas al laboratorio
  (hasta tres, sin repetir cluster) y por que las demas no lo son (bloqueos
  no compensables). El dossier en siete partes se genera desde la ficha y
  queda en Artefactos.
- **Retorno.** Los datos del laboratorio se clasifican en seis clases con
  definiciones operativas mas las dimensiones que coexisten; cada clase
  dispara una accion distinta (una correccion de contexto crea una hipotesis
  derivada; un fallo tecnico no toca la hipotesis).
- **Aprendizaje y metodos.** En Ajustes: el registro de aprendizaje en tres
  niveles (creencias; criterios y programas, que Rosa propone y una persona
  evalua y promueve; politicas), el registro de metodos con su estado, y las
  politicas tal como estan en el codigo.

- **Ranking por Bradley-Terry y evidencia acumulada.** Las candidatas se
  ordenan por la fuerza de Bradley-Terry sobre los partidos del torneo, con
  intervalo del 95 % por bootstrap; el Elo queda como vista. Cuando un plan
  de analisis tiene aleatoriedad (permutacion, bootstrap) el sandbox lo
  repite con dos semillas mas. Los p-valores de los analisis validos de una
  hipotesis se agregan con e-valores (producto de kappa p^(kappa-1)), que
  controlan el error aunque se sigan a�adiendo pruebas.
- **Misma cohorte sin nombre y comprobaciones de registro.** Dos fuentes
  primarias que comparten dos autores, o el centro y un autor, con pocos a�os
  de diferencia cuentan como una sola cohorte aunque no la nombren. El Killer
  comprueba ademas que la evidencia sostenida va en la direccion del enunciado
  (si va al reves, reformula) y que las cifras comparadas estan en la misma
  unidad (si no, avisa).
- **Protocolo real y enmiendas fechadas.** En la ficha del experimento, tras
  asignarlo, se registra lo que el laboratorio hizo de verdad (protocolo
  ejecutado, desviaciones, identidad de las muestras) y cualquier cambio del
  prerregistro queda como enmienda con fecha, autor, texto anterior y motivo.
  El juez lee las tres cosas al evaluar los datos.
- **Gobierno de areas y jerarquia.** Cada area del programa se puede elegir,
  pausar con la condicion que la reabriria, reabrir, dejar sin explorar o
  asignar a una campana (corrida); todo con historial. En Objetivo y datos se
  ve la jerarquia programa, areas, campanas y preguntas con sus huecos.
- **Comprobador heuristico de supuestos causales.** No es un motor causal
  (sin modelo estructural ni descubrimiento de estructura desde datos, que la
  literatura de 2026 no considera listo para biologia). Cada hipotesis
  juzgada lleva un grafo local con aristas tipadas (supuesto, inferencia con
  evidencia, base curada de quince relaciones del Alzheimer escritas a mano),
  las alternativas que planteo el Killer como nodos, y una identificacion por
  regla: identificable, acotado (con los supuestos que faltan) o sin
  resolver. El resultado entra al Killer como la comprobacion
  `direccion_causal` (no comprobable con los supuestos que faltan, hasta que
  el juez o un experimento los resuelvan). La base curada vive en
  `rosa/causal.py`.
- **Panel del Killer.** Un panel con fallos plantados en hipotesis reales
  (cifra alterada, prediccion no falsable, causalidad sin temporalidad, misma
  cohorte, supuesto contradicho) y un conjunto gris mide la tasa de deteccion,
  si lo vio el juez, la abstencion y cuanto mata de mas. Se corre con el
  servidor encendido (cuesta llamadas al juez) y el resultado queda en Calidad:

  ```
  uv run python -m rosa.evaluacion.panel_killer --hipotesis 5
  ```

## Lo que Rosa tomo de Claude Science (11 de septiembre de 2026)

La investigacion completa esta en `INVESTIGACION-HERRAMIENTAS-CLAUDE-SCIENCE.md`.
Lo aplicado:

- **Conectores a bases publicas** (`rosa/conectores/`): 80 conectores en 21
  grupos, 57 activos sin clave (OLS, MyGene, MyVariant, Ensembl, UniProt,
  GTEx, Human Protein Atlas, STRING, Reactome, GWAS Catalog, ClinVar,
  ClinGen, CIViC, Open Targets por GraphQL, ChEMBL, PubChem, BindingDB,
  DGIdb, openFDA, GEO, ArrayExpress, PRIDE, MetaboLights, Expression Atlas,
  CELLxGENE, Synapse, PDB, AlphaFold, EMDB, IntAct, Complex Portal, InterPro,
  QuickGO, ENCODE, JASPAR, UniBind, cBioPortal, UCSC, Enrichr, g:Profiler,
  NIAGADS, bioRxiv, Semantic Scholar, Europe PMC Annotations, arXiv,
  Grants.gov, Antibody Registry, CellGuide, FinnGen) y 23 inertes con su
  motivo (Benchling, BioRender, 10x, Owkin, Medidata, Wiley, Consensus,
  KEGG por licencia, DrugBank, AlzForum sin API, ADNI y UK Biobank por acceso
  controlado, ARCHS4 por fichero de 30 GB). Cada llamada deja un registro de
  consulta (herramienta, argumentos, fecha, resultados, identificadores,
  invariante comprobada) en la hipotesis; el catalogo con licencias, limites
  y permisos esta en Ajustes.
- **Novedad ampliada**: ademas de Open Targets, ClinicalTrials.gov y el
  precedente en la literatura, cada hipotesis comprueba la genetica humana
  (GWAS Catalog, ClinVar), los farmacos contra la diana (ChEMBL, DGIdb) y si
  hay datos publicos para comprobarla (GEO, CELLxGENE).
- **La diana en las bases**: identificadores estables (MyGene), funcion
  (UniProt), expresion en cerebro (Human Protein Atlas), interactores
  (STRING) y rutas (Reactome) debajo de la tarjeta; el Killer comprueba
  `identificadores_resuelven`.
- **Preguntar a las bases** (en Modelo de mundo): un bucle acotado de
  herramientas (ReAct, hasta seis pasos) con los conectores, la busqueda en el
  proyecto y el modelo de mundo; la respuesta llega con sus consultas.
- **Permisos por conector** (permitir, solo si pregunta una persona,
  bloquear) y **memoria del proyecto** (hechos cortos que Rosa lee en cada
  mision), en Ajustes y en Objetivo y datos.
- **Revisor de registro**: al cerrar cada iteracion y en el dossier, lo que
  Rosa dice se compara con lo que el registro prueba (seis clases de
  hallazgo, por regla y con el juez); los hallazgos se ven como tarjetas en
  la corrida.
- **Artefactos con cinco pestanas de procedencia** (mensajes, codigo,
  registro de ejecucion, entorno, revision) y versiones por nombre.
- **Skills de metodo** (`rosa/skills/`): expresion GEO, tamano muestral (con
  modulo importable en el sandbox), control de calidad de celula unica,
  fila de evidencia, eleccion de problema, reproduccion publicada, revision
  de literatura. El planificador, el escritor de codigo y el proponente de
  areas las cargan por palabras de activacion.
- **Dos entornos de sandbox**: `rosa-sandbox:1` (tabular) y
  `rosa-sandbox-celula:1` (scanpy, anndata); el plan declara el entorno y la
  ejecucion registra la imagen y las versiones de paquetes.
- **Panel del Killer** en Calidad, con dos corridas registradas (deteccion
  del 16 % al 67 % tras hacer `supuestos` una regla y suspender cuando juez y
  regla discrepan).

Lo que Claude Science tiene y Rosa no copia, y por que: kernels persistentes
de Python y R, notebooks y entornos con instalacion libre (Rosa es un
investigador autonomo con contrato de salida y reproducibilidad exigida;
instalar a demanda la rompe), trabajos remotos en Slurm o Modal (sin
infraestructura ni necesidad hoy), y las plataformas de pago sin datos
publicos. scvi-tools no entra en la imagen de celula unica porque arrastra
PyTorch y no hay GPU.

## Lo que Rosa tomo de la revision de un AI scientist profesional (14 de septiembre de 2026)

Un informe externo listo quince huecos entre el MVP y un sistema en operacion
profesional; se verifico cada afirmacion contra las fuentes (ver
`INVESTIGACION-AI-SCIENTIST-2026.md`, con las correcciones: PRISMA 2026 no
existe, la mayoria de los laboratorios autonomos esta en el nivel 3, DrugBank
no es abierto) y se aplico lo que aportaba:

- **Riesgo de sesgo por instrumento** (`rosa/sesgo.py`): RoB 2, ROBINS-I V2,
  QUADAS-2, ROBIS y SYRCLE. El juez responde las preguntas de senalizacion
  con cita y la regla del instrumento pone el veredicto; la comprobacion
  `sesgo_evidencia` del Killer y el factor GRADE salen de ahi.
- **Conjunto dorado y calibracion** (`rosa/acuerdo.py`,
  `rosa/acuerdo_dorado.py`): cada comprobacion del Killer se etiqueta a mano
  desde la ficha; Calidad muestra el kappa de Cohen por comprobacion (y AC1
  de Gwet); el panel de fallos plantados reporta kappa; si cambia el modelo
  del juez o cae el acuerdo, queda una incidencia.
- **Sello externo del prerregistro** (`rosa/sello.py`): RFC 3161 con freeTSA,
  DigiCert y Sectigo al asignar un experimento; verificable con `openssl ts
  -verify` sin Rosa. **Registro encadenado por hashes** (Ajustes, Integridad
  del registro).
- **PRISMA 2020** (`rosa/prisma.py`): el cribado registra cada excluido con
  su motivo; la corrida exporta el flujo con las variables oficiales del
  diagrama, los items 6, 7, 8, 16a y 16b, la extension PRISMA-LSR y la
  declaracion de la IA (PRISMA-trAIce).
- **Ensayo en seco** (`rosa/sintetico.py`): el plan congelado corre sobre una
  tabla sintetica con la forma del dataset antes de tocar los datos reales.
- **Entidades canonicas** (`rosa/ontologias.py`): HGNC, MONDO, CL, UBERON,
  GO y ChEBI en hechos, hipotesis y nodos causales; el modelo de mundo se
  busca por identificador o alias; redundancia por identificador.
- **Politica de contexto**: presupuesto de tokens por rol
  (`politicas.TOKENS_MAX_POR_ROL`), recortes registrados como compactacion y
  el acuerdo juez-humano por tamano del modelo de mundo en Calidad.
- **Nivel de autonomia declarado**: 2 de 5 en la escala de Beal y Rogers, en
  Ajustes y en cada dossier. **Coste por decision** (`rosa/costes.py`):
  modelo mas horas de revision a tarifa declarada, por dossier, candidata y
  decision. **Conocimiento operativo del laboratorio** como clase de
  evidencia propia. **RO-Crate con PROV** (`rosa/rocrate.py`) desde la ficha.

Reglas de concurrencia (lo que antes no estaba escrito): un solo escritor
(el proceso de Rosa, con cerrojo reentrante); cada mutacion es atomica y se
persiste con su fila del registro en la misma transaccion; una lectura ve
siempre una version completa (la instantanea se toma bajo el cerrojo); una
decision humana lleva la version de la hipotesis que veia y el servidor la
rechaza si cambio (la interfaz recarga y avisa); el espejo de Convex y las
exportaciones leen bajo el cerrojo en un hilo. Si algun dia hay varios
procesos escribiendo, esta seccion es lo que hay que revisar primero.

## Espejo del estado en Convex

Con `CONVEX_URL` y `CONVEX_DEPLOY_KEY` en el `.env` del servidor, Rosa copia
cada entidad publica del estado a una tabla de Convex (`frontend/convex/`:
esquema y funciones `espejo:sincronizar`, `espejo:meta`, `espejo:coleccion`,
`espejo:entidad`, `espejo:hashes`), actualizando solo lo que cambio pocos
segundos despues de cada mutacion. SQLite sigue siendo la fuente de verdad y
el unico que escribe; el espejo sirve para leer el estado desde cualquier
sitio y para que varias personas lo vean a la vez. Estado en Ajustes y en
`GET /api/espejo`. Despliegue de las funciones: `cd frontend && npx convex
deploy` con la clave en el entorno. La clave nunca va al estado, al
navegador ni al repositorio.

Los datasets admiten hasta 200 MB (una matriz de expresion de GEO en formato
largo ronda los 100 MB). Arrancar Docker Desktop antes de una demostracion con
datos reales: sin runtime de aislamiento, los analisis quedan en "no ejecutado"
con el motivo.

## Exa: búsqueda semántica de publicaciones (15 de septiembre de 2026)

Exa (exa.ai) recupera por significado, con embeddings, sobre un índice de
unos 350 millones de publicaciones (`category="publication"`). Rosa lo usa
como complemento de PubMed, Europe PMC y OpenAlex, no en su lugar:

- **Búsqueda de literatura.** El planificador (`GenerarConsultas`) recibe las
  bases disponibles y, si Exa está, escribe al menos una consulta en lenguaje
  natural para ella; las demás siguen siendo booleanas. Los resultados pasan
  por el mismo cribado, la misma fusión por DOI, PMID o título y el mismo
  registro que los de las otras bases (`rosa/fuentes/exa.py` los devuelve con
  la misma forma). Si el plan elige Exa y no hay clave, la consulta se desvía
  a Europe PMC con una nota: nunca se pierde por falta de clave.
- **Novedad del Killer.** Además de OpenAlex por términos clave, Exa busca el
  enunciado entero de la hipótesis: es la herramienta para "¿alguien ya
  propuso esto con otras palabras?". Los candidatos de las dos bases se
  puntúan juntos con el mismo programa de relevancia.
- **Conectores** `exa_publicaciones` y `exa_similares` (documentos parecidos
  a una URL) en el catálogo, con registro de consulta e invariante (cuántos
  resultados traen DOI resuelto). Sin clave quedan como "requiere cuenta"
  con el motivo.

Solo se usan los endpoints de recuperación (`search`, `contents`,
`findSimilar`); nunca `answer`, `research` ni los tipos `deep`, que razonan
con modelos de Exa fuera del AI Gateway. La clave va en `ROSA_EXA_KEY` en el
`.env` del servidor (se crea en dashboard.exa.ai; 20 USD de crédito inicial y
10 al mes gratis) y viaja solo en la cabecera `x-api-key`. Exa devuelve URL:
Rosa extrae el DOI de la URL cuando lo lleva y el PMID de las de PubMed; lo
demás queda como URL. Coste: 7 USD por mil búsquedas y 1 USD por mil páginas;
Rosa anota `costDollars` en la pista. Lo que se envía a Exa es la consulta o
el enunciado de la hipótesis: es texto del equipo que sale a un proveedor
externo; la retención cero de datos solo está en su plan Enterprise. Pruebas
sin red en `rosa/tests/test_exa.py`.

## Despliegue: Vercel para la interfaz, un proceso persistente para Rosa

El proyecto `rosa-mvp` de Vercel está hoy configurado con el preset FastAPI
y raíz `.`, es decir, para desplegar el backend como funciones sin servidor.
Eso no puede funcionar para Rosa: el backend es un proceso que vive (el
bucle de investigación con tareas asyncio de horas, el flujo SSE, el
trabajador de correo cada cinco segundos, el espejo de Convex) y escribe en
un SQLite local que es la fuente de verdad. Una función sin servidor es
efímera, pierde el disco entre llamadas y corta la ejecución a los pocos
minutos. La división correcta:

- **Vercel sirve la interfaz.** `vercel.json` en la raíz fija el preset Vite,
  la instalación y la construcción dentro de `frontend/` y la salida
  `frontend/dist`, por encima del preset FastAPI del proyecto. Cuando exista
  el backend público, se añade una regla `rewrites` que mande `/api/(.*)` a
  su URL: así la interfaz y la API comparten origen y la cookie de sesión
  (SameSite=Strict) sigue valiendo. Hasta entonces la interfaz desplegada
  muestra la puerta con «No se puede conectar con Rosa», que es la verdad.
- **Rosa corre en una máquina persistente**: una VPS o un servicio de
  procesos largos (Fly.io, Railway, Render), o el equipo del servidor
  expuesto con un túnel HTTPS (Cloudflare Tunnel, Tailscale). Con HTTPS
  público, esa dirección va en «Dirección web de Rosa» de la configuración de
  correo, porque es la que viaja en los enlaces de acceso.

Vercel además bloquea un despliegue si el correo del autor del commit no
pertenece a la cuenta de GitHub conectada (`EmirMaleckFrias`). Ojo:
`emir.malek@alzheimerproject.com` está asociado a otra cuenta de GitHub
(`emirmalek50`), así que en este repositorio el autor se fija con
`git config user.email EmirMaleckFrias@users.noreply.github.com`, la
dirección sin correo real que GitHub reconoce siempre como propia de la
cuenta.

## Como se investiga

1. **Nueva investigacion**: titulo, objetivo, que cuenta como relevante,
   limites, condicion de parada (si dice "N iteraciones", Rosa para sola al
   llegar). Al crearla arranca la corrida 1.
2. **Plan**: Rosa propone el plan de la iteracion (4 a 7 pasos con su tipo y
   su coste en llamadas) y espera. Se puede editar, reordenar o aprobar. Con
   "autoaprobar tras N segundos" no espera.
3. **Pasos**: cada paso lanza pistas en paralelo con su transcripcion en vivo.
   Literatura (PubMed, Europe PMC, preprints), ensayos (ClinicalTrials.gov),
   extraccion (Sonnet 5), verificacion (deterministas y juez Opus 5), modelo de
   mundo (GPT-6 Astra), hipotesis (generar, revisar, torneo), novedad (Open
   Targets, ClinicalTrials.gov, OpenAlex), meta-revision.
4. **Cola de hipotesis**: cada hipotesis llega con sus afirmaciones y
   veredictos, sus fuentes con pagina, sus supuestos, sus revisiones y su
   novedad. Aceptar la mete al modelo de mundo como abierta; descartar exige
   motivo; "no puedo juzgar" hace que Rosa la aclare.
5. **Presupuesto**: la corrida tiene un tope de llamadas al modelo (1500 por
   defecto). Al llegar se pausa y pide ampliarlo; nunca muere en silencio.

## Estructura

```
rosa/                 backend (ver INVESTIGACION-BACKEND.md, seccion 7)
  estado/             estado canonico (misma forma que tipos.ts), reducers, SQLite
  fuentes/            PubMed, Europe PMC, Crossref, OpenAlex, Unpaywall,
                      ClinicalTrials.gov, Open Targets, PDF por pagina
  modulos/            firmas DSPy y contador de llamadas
  bucle/              supervisor, ejecutores de paso, pistas
  verificador.py      contratos de TRASPASO 4.1
  torneo.py           Elo por pares con debias
  servidor.py         FastAPI: /api/estado, /api/eventos (SSE), /api/acciones
  main.py             arranque
  tests/              pytest
frontend/             interfaz (ver frontend/README.md)
rosa.db               estado (SQLite, ignorado por git)
mlflow.db, mlruns/    trazas de cada llamada y corridas de GEPA
```

## Comprobar que todo funciona

```bash
uv run python -m pytest rosa/tests -q      # reglas del dominio y verificador
cd frontend && npm run typecheck && npm test
uv run python rosa/prueba_gateway.py       # los tres modelos responden
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db   # trazas en :5000
```

## Documentos

- `TRASPASO.md`: decisiones, reglas de trabajo, modelos, contratos.
- `GUIA-ROSA.md`: Alzheimer, fuentes, DSPy y GEPA, evaluacion, marco legal.
- `UI-ROSA.md` e `INVESTIGACION-INTERFACES.md`: la interfaz y lo que se copio
  de otros sistemas.
- `INVESTIGACION-BACKEND.md`: los AI scientists estudiados, las APIs de las
  fuentes y la arquitectura del backend.
- `INVESTIGACION-AI-SCIENTIST-2026.md`: los quince huecos de un AI scientist
  profesional verificados contra las fuentes, con las correcciones al informe
  externo y lo que Rosa tomo de cada uno.
