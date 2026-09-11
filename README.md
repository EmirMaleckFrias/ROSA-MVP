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
`PLAN-ROSA2018.md`) anaden a Rosa estas piezas. Todas estan en la interfaz;
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
- **Hypothesis Killer.** Cada hipotesis pasa una lista fija de once
  comprobaciones; la decision (avanzar, reformular, suspender, descartar en
  este contexto) se deriva por regla. Reformular crea una version nueva (hasta
  dos por politica). Un tercio de los descartes lo audita otro modelo
  defendiendo la hipotesis. Todo queda en el registro de decisiones.
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
  controlan el error aunque se sigan anadiendo pruebas.
- **Misma cohorte sin nombre y comprobaciones de registro.** Dos fuentes
  primarias que comparten dos autores, o el centro y un autor, con pocos anos
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
- **Motor causal minimo.** Cada hipotesis juzgada lleva un grafo local con
  aristas tipadas (supuesto, inferencia con evidencia, base curada), las
  alternativas que planteo el Killer como nodos, y una identificacion por
  regla: identificable, acotado (con los supuestos que faltan) o sin
  resolver. Las relaciones entran al modelo de mundo con su tipo; la base
  curada vive en `rosa/causal.py`.
- **Panel del Killer.** Un panel con fallos plantados en hipotesis reales
  (cifra alterada, prediccion no falsable, causalidad sin temporalidad, misma
  cohorte, supuesto contradicho) y un conjunto gris mide la tasa de deteccion,
  si lo vio el juez, la abstencion y cuanto mata de mas. Se corre con el
  servidor encendido (cuesta llamadas al juez) y el resultado queda en Calidad:

  ```
  uv run python -m rosa.evaluacion.panel_killer --hipotesis 5
  ```

Los datasets admiten hasta 200 MB (una matriz de expresion de GEO en formato
largo ronda los 100 MB). Arrancar Docker Desktop antes de una demostracion con
datos reales: sin runtime de aislamiento, los analisis quedan en "no ejecutado"
con el motivo.

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
