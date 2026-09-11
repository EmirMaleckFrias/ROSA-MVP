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
