# Rosa

Este repositorio es Rosa, la IA del proyecto Alzheimer de AI Robotix y el
INTEC. Antes de tocar nada, leer en este orden:

1. `TRASPASO.md`: decisiones tomadas, reglas de trabajo de la persona responsable, modelos
   elegidos y por que, contratos del verificador que hay que conservar, plan.
2. `GUIA-ROSA.md`: el conocimiento de fondo (Alzheimer a nivel de ingeniero,
   fuentes de datos y sus APIs, DSPy y GEPA con la API exacta, evaluacion,
   marco legal dominicano).
3. `UI-ROSA.md`: la interfaz, patron por patron, tomando Claude Science como
   referencia y anadiendo lo que Rosa necesita y aquella no tiene.
4. `INVESTIGACION-INTERFACES.md`: lo que hacen Claude Science, Kosmos,
   Co-Scientist, Biomni y las herramientas de literatura, y la lista
   priorizada de lo que le falta al frontend de Rosa.
5. `INVESTIGACION-BACKEND.md`: los AI scientists estudiados a nivel de codigo
   (Kosmos, Co-Scientist, PaperQA, Robin, Agent Laboratory, Denario, Curie,
   SciAgents, ResearchAgent, HypoGeniC, Biomni), las APIs de las fuentes con
   sus limites reales, y la arquitectura del backend que se construyo.
6. `INVESTIGACION-CONCLUSIONES.md`: como presentan sus conclusiones los AI
   scientists y las herramientas de literatura, las convenciones de la
   medicina basada en evidencia (GRADE, Cochrane, AAN, IPCC, ICD 203) y lo que
   se fusiono en la "Conclusion de Rosa" y el resumen de cada iteracion.
7. `README.md`: como arrancar Rosa y como se investiga con ella.

`casos_evaluacion.jsonl` son los 17 casos de control del RAG anterior, todos
sin aprobar por un humano.

## Estructura

- `rosa/`: el backend en Python (DSPy, GEPA, FastAPI, SQLite). El estado
  canonico tiene la misma forma que `frontend/src/datos/tipos.ts`; los
  reducers de la interfaz estan portados uno a uno en
  `rosa/estado/acciones.py` (misma regla en los dos lados). El bucle
  (`rosa/bucle/`) escribe en ese estado; el servidor (`rosa/servidor.py`) lo
  sirve por `/api/estado`, lo empuja por SSE en `/api/eventos` y recibe las
  acciones en `POST /api/acciones/{nombre}`. Arranque: `uv run python -m
  rosa.main` o `./rosa.sh` (servidor mas interfaz).
- `frontend/`: la interfaz web de Rosa (React, Vite, TypeScript). Ver su
  `README.md`. `frontend/src/datos/almacen.ts` prueba el servidor al arrancar
  y, si no responde, cae a los datos de muestra con la corrida simulada.
- Los datos de trabajo de una corrida (fuentes con fragmentos, afirmaciones
  con veredicto) viven en claves privadas de la corrida que empiezan por `_`
  y no viajan al navegador.

## Reglas que no se negocian

- Modelos solo por el AI Gateway de Vercel, nunca por APIs directas. El
  coste por token no es criterio. Claude Fable 5.1 queda fuera de Rosa
  (filtros de doble uso en biologia; ver `TRASPASO.md` 2.3).
- La persona usuaria es medica, no programadora: botones y estado visible,
  en espanol, nunca variables de entorno ni terminal.
- Las citas resuelven a la pagina exacta. Un desfase de una pagina es un
  fallo grave.
- Sin guiones largos (U+2014) en codigo, comentarios ni interfaz.
- Antes de cada commit, escanear `sk-proj-`, `sb_secret_`, `vcp_`, `vck_`,
  `github_pat_`, `ghp_`, `eyJhbGci`, `eyJ2MiI6`, `ntn_`, `secret_`, `GOCSPX-`.
- La marca grafica de Rosa es el arbol del Alzheimer Project; no se usa el
  logo de AI Robotix.
- Intentar romper el propio cambio antes de cerrarlo: test adversarial,
  camino de punta a punta, y preguntarse que asume el cambio que antes no.
- Una fuente que no responde es "no pude comprobar", nunca "no hay". Un
  tiempo agotado no es "sin ensayos".
- Al modelo de mundo solo entran afirmaciones sostenidas o parciales; las
  hipotesis nuevas entran a la cola como propuestas y las decide una persona.
- Mientras se construye algo, se explica como funciona: quien opera Rosa es
  el ingeniero de IA que la construye, no la medica; necesita entender la
  ingenieria y el dominio, con los conceptos por su nombre y su definicion.
- Las conclusiones de Rosa siguen GRADE: certeza y direccion por separado,
  factores que bajan o suben la certeza a la vista, frases plantilla por nivel
  generadas por regla, sin porcentajes de confianza inventados, sin
  "demostrado" ni "confirmado", sin recomendaciones clinicas.