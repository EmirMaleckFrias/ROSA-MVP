# Lo que hacen los demas "AI Scientist" y lo que le falta a Rosa

Investigacion del 10 de septiembre de 2026, hecha despues de construir la
primera version del frontend de Rosa. Compara lo construido con Claude
Science (documentacion y changelog hasta la 0.1.43 del 31 de agosto), Kosmos
y la plataforma de Edison Scientific (antes FutureHouse: Crow, Falcon, Owl,
Robin, PaperQA), el AI co-scientist de Google DeepMind (Nature 2026 y su
suplemento de 115 paginas), Biomni de Stanford (Science 2026, mas el codigo
de su interfaz y la extension Biomni-AD para Alzheimer), las herramientas de
literatura (Elicit, Consensus, Undermind, Scite, SciSpace, Semantic Scholar y
Asta, Zotero, PubMed, Deep Research de OpenAI, Gemini y Perplexity), los AI
Scientist abiertos (Sakana v2, Agent Laboratory, Virtual Lab, Denario, Curie,
Robin, reimplementaciones abiertas del co-scientist) y las guias de 2025 y
2026 sobre agentes de larga duracion con humano en el bucle (Anthropic,
OpenAI, Magentic-UI, Temporal, LangGraph, Agentic UX).

Regla de lectura: donde una fuente no se pudo ver (paginas con 403, videos
sin transcripcion, producto de acceso restringido) se dice. No hay ninguna
captura publica de la interfaz del co-scientist de Google ni de la pantalla
de progreso de Kosmos; lo que se dice de ellos sale de sus articulos, prompts
y API, no de verlos.

## 1. Lo que la investigacion confirma de Rosa

Estas decisiones de Rosa coinciden con lo que hacen los mejores sistemas, y
conviene no tocarlas:

- **La aprobacion va antes del efecto** (tarjetas de permiso con alcance,
  cola de revision antes de entrar al modelo de mundo). Es el patron central
  de Claude Science, Magentic-UI y las guias de OpenAI y Anthropic. El
  estudio de Anthropic sobre autonomia (2026) anade un matiz: exigir aprobar
  todo crea friccion sin seguridad; lo que importa es poder intervenir
  cuando cuenta.
- **Verificacion por afirmacion con veredictos** y la distincion entre "no
  esta en las fuentes" y "no pude comprobar". PaperQA2 se abstiene en un
  22 % de los casos y FutureHouse eligio su modelo por decir claramente
  cuando la evidencia no basta; AbstentionBench muestra que los modelos
  razonadores se abstienen peor, asi que la abstencion tiene que ser un
  estado de la interfaz, no una esperanza sobre el modelo.
- **Ranking por torneo Elo con rivales**: es exactamente lo de Co-Scientist
  (Elo inicial 1200, debates por pares) y de Robin (Bradley-Terry sobre
  comparaciones pareadas).
- **Modelo de mundo con procedencia hasta la pagina y motivo de descarte**:
  Kosmos lo llama su innovacion central y el articulo "Agentic AI Scientists
  Are Not Built For Autonomous Scientific Discovery" (2026) pide modelos de
  mundo persistentes y prerregistro de hipotesis.
- **Revisor como tarjetas bajo el mensaje, tres visibles y "mostrar todo"**:
  es la forma que Claude Science adopto en la 0.1.41 (antes era una bandeja
  aparte, y la cambiaron).
- **Retractaciones marcadas y excluidas**: ninguna de las nueve herramientas
  del estudio JMIR 2026 lo hace de forma consistente, y en la prueba de MIT
  Technology Review Consensus cito 18 de 21 retractados sin avisar. Rosa ya
  hace algo que la mayoria no hace.

## 2. Lo que falta y valdria la pena, por prioridad

La prioridad se mide por lo que cambia para una investigadora que revisa una
corrida de dias unas horas al dia.

### 2.1 Imprescindible para una corrida de dias

1. **"Mientras no estabas" al entrar, y avisos fuera de la pantalla.** Es el
   patron mas repetido para agentes de larga duracion: el recap de la vista
   de agentes de Claude Code, el "Return Moment" del marco Agentic UX, los
   ficheros de estado de Codex, y las notificaciones de Claude Science
   (0.1.27: sesion terminada o necesita tu input, in-app, sonido y
   escritorio). Rosa no tiene nada de esto. En pantalla: al abrir, una
   tarjeta "Desde tu ultima visita (14 h): 3 iteraciones, 2 hipotesis
   nuevas, 1 subio al primer puesto, 4 decisiones esperan (la mas antigua
   lleva 9 h), gasto 63 de 120 llamadas en la iteracion actual", con cada
   linea enlazada. La misma tarjeta es el resumen que se manda a Slack o
   correo, que hoy en Ajustes es solo un interruptor sin nada detras.

2. **Presupuesto global de la corrida con alarmas y pausa, no muerte.** Rosa
   tiene presupuesto por iteracion; falta el tope de la corrida completa.
   Claude Science (0.1.18) pausa la sesion y pide confirmacion antes de
   gastar mas; los Managed Agents de Anthropic lo hacen con tope duro,
   alertas al 50 y 80 %, estado "pausada por presupuesto" reanudable
   subiendo el tope, y una regla de diseno que vale copiar: **una pregunta
   pendiente tiene prioridad sobre el tope** (la sesion queda en "requiere
   accion", no en "pausada"). En pantalla: barra con marcas 50/80/100,
   proyeccion "al ritmo actual llegas al tope en 6 h", boton "Ampliar y
   reanudar".

3. **Marcas de tiempo absolutas en todo** (mensajes, pasos, hallazgos,
   permisos). Claude Science las anadio en la 0.1.41. Rosa solo dice "hace
   31 min". Barato e indispensable para auditar dias.

4. **Cola de revision con envejecimiento, prioridad y accion por defecto.**
   Ningun AI Scientist lo tiene; lo tienen las herramientas de flujo
   (Temporal: recordatorios a las 24 h, escalado a un suplente, autorechazo
   o parada segura si nadie responde, registro de cada paso; Vercel: caida
   a los 48 h). En pantalla: cada tarjeta con "esperando 9 h", fecha limite,
   y en Ajustes "si nadie decide en 24 h: recordar / escalar a X / detener
   con seguridad / continuar y registrar". Que nunca lo decida la interfaz
   por accidente.

5. **Tarjeta cuando el modelo se niega o el conector caduca.** Claude
   Science (0.1.41) muestra un aviso corto con cambio de modelo en un clic
   cuando las salvaguardas del modelo bloquean biologia, y una tarjeta
   "Sign-in expired, Reconnect" cuando un conector caduca, avisando dentro
   de la sesion. Para Rosa es directo: ya se midio que Fable devuelve vacio
   con `finish_reason: content-filter` en hipotesis mecanisticas; cualquier
   respuesta bloqueada tiene que aparecer como tarjeta con alternativa, no
   como una pista que muere en silencio. Igual con las claves de PubMed,
   OpenAlex o Semantic Scholar en una corrida de dias.

6. **Aprobar o editar el plan antes de que arranque la iteracion.** Rosa
   ensena el plan y permite dirigir, pero la iteracion arranca sola.
   Claude Science (desde 0.1.27) no ejecuta ni marca pasos hasta que
   apruebas; Biomni-AD (la extension para Alzheimer) muestra "Aprobar y
   ejecutar / Revisar plan / Cancelar"; Devin espera 30 s y sigue si no
   respondes; Magentic-UI deja editar el plan en la propia lista. Tambien:
   el plan como lista de control con tres estados, hecho, pendiente y
   **fallido con explicacion** (Biomni obliga a marcar [x] y decir por que).

### 2.2 Lo que hace mas fiable lo que Rosa afirma

7. **Tipo de afirmacion con fiabilidad historica por tipo.** El articulo de
   Kosmos midio 85,5 % de acierto en afirmaciones de datos, 82,1 % en las de
   literatura y **57,9 % en las de interpretacion o sintesis**. Rosa trata
   todas igual. En pantalla: marcador de tipo (dato, literatura,
   interpretacion) en cada afirmacion, y la tasa historica de Rosa para ese
   tipo en el tablero de calidad; las interpretaciones en gris hasta que las
   juzgue una persona.

8. **"Significativo" no es "valioso", y detector de sobreafirmacion.** Kosmos
   reconoce que persigue "agujeros de conejo" estadisticamente
   significativos pero irrelevantes, que hace afirmaciones "excesivamente
   fuertes" y que inventa metricas compuestas "conceptualmente oscuras". En
   pantalla: dos escalas separadas por hallazgo (evidencia estadistica y
   relevancia para el objetivo, esta ultima justificada en dos lineas por
   Rosa y votada por la revisora); subrayado ambar en verbos fuertes
   ("demuestra", "establece"); cualquier puntuacion nueva definida por Rosa
   exige definicion en una frase. El tablero cuenta los "alta significancia,
   baja relevancia".

9. **Tres rubricas de revision segun el tipo, y el estado "no puedo
   juzgar".** En la evaluacion de Kosmos, un dato se revisa reproduciendolo,
   una cita se revisa en la literatura y una interpretacion se juzga solo
   con el contexto dado; y existia el veredicto UNSURE, que devolvia la
   afirmacion aclarada al evaluador. Rosa tiene aceptar, refinar y
   descartar. En pantalla: cuarto boton "No puedo juzgar" con motivo
   (ambigua, falta contexto, no reproducible) que hace que Rosa reescriba o
   anada contexto y la tarjeta vuelva marcada "aclarada". Opcion de revision
   a ciegas (ocultar las citas y el codigo hasta emitir veredicto), que es
   como lo hizo Kosmos para evitar el sesgo de confirmacion.

10. **Citas de apoyo y contradictorias por hecho del modelo de mundo.**
    Rosa verifica una afirmacion contra su cita, pero no ensena si otras
    fuentes la contradicen. Scite lo resuelve con tres numeros por
    afirmacion (apoya, menciona, contrasta) y el contexto de cada cita con
    la seccion del articulo; Consensus tiene una tabla "Claims & Evidence"
    con papers a favor y en contra; ContraCrow (FutureHouse) busca
    contradicciones a proposito. En pantalla: junto a cada hecho sabido,
    tres numeros con iconos; al abrir, los fragmentos citantes con su
    clasificacion; aviso "nueva cita contrastante" cuando Rosa lea algo que
    contradiga un hecho.

11. **Tipo de estudio y nivel de evidencia por fuente, y texto completo
    frente a resumen.** Hoy en Rosa un caso clinico y un metaanalisis se ven
    igual. Consensus etiqueta el tipo (ECA, revision sistematica, cohorte,
    animal, in vitro) y la calidad de la revista; OpenEvidence anadio en
    julio de 2026 un grado A a D por cita basado en GRADE; Trip usa una
    piramide de cinco peldanos; Consensus marca si el analisis uso solo el
    resumen o el texto completo. En pantalla: chip de tipo por fuente, una
    escalera de cinco peldanos, un icono "texto completo / solo resumen", y
    por hipotesis un resumen "sostenida por 2 ECA, 6 observacionales, 4
    preclinicos". Marcar que es nivel potencial, no calidad real.

12. **Cobertura de la busqueda, y una "ausencia refutada" honesta.**
    Undermind estima cuanto de lo relevante ha encontrado (una curva de
    descubrimiento; "93 % de lo relevante tras 144 articulos") y ofrece
    extender la busqueda. Elicit entrega el diagrama de flujo PRISMA con
    cuantos se identificaron, cribaron, leyeron y usaron, y la estrategia de
    busqueda reproducible con fecha. En pantalla: por tema del modelo de
    mundo, barra "144 leidos, cobertura estimada 93 %"; si la curva no ha
    convergido, el veredicto "ausencia refutada" se degrada solo a "sin
    verificar (cobertura 61 %)"; pestana "Metodos" en cada informe con las
    cajas PRISMA y las consultas exactas.

13. **Retractaciones vivas.** Rosa marca la retraccion al indexar; falta
    recomprobar periodicamente contra Crossref y Retraction Watch con fecha
    de ultima comprobacion, propagar la marca a todo hecho e hipotesis que
    dependa de esa fuente (banner "depende de 1 fuente retractada el 4 de
    marzo" y bajada en el ranking), distinguir erratum y expresion de
    preocupacion, y usar siempre la palabra "retractado" (el estudio JMIR
    puntua como error decir "controvertido"). Zotero avisa incluso al citar
    en Word un item que ya no esta en la biblioteca.

14. **Procedencia hasta la celda de codigo, no solo hasta la pagina.** Kosmos
    enlaza cada cifra a un cuaderno con id de trayectoria ([Trajectory r7])
    y deja descargar el .ipynb; Claude Science ensena cada consulta a un
    conector como paso expandible con parametros y resultado; Biomni pinta
    la traza en dos columnas (respuesta limpia a la izquierda, ejecutor con
    razonamiento, codigo con lenguaje y duracion, observacion plegada y
    ficheros generados a la derecha). En pantalla: junto a cada cifra, un
    chip "r7, celda 14" que abre codigo, salida y "Descargar cuaderno"; cada
    consulta a PubMed, Open Targets o ClinicalTrials.gov como paso
    expandible con la consulta exacta y lo que devolvio.

15. **Ultima revision hace X.** Una resena de Claude Science documenta un
    caso en que la narrativa atribuyo mal un resultado y el revisor no lo
    marco; otra, que el revisor no corrio en el plan Pro y hubo que pedirlo.
    Rosa debe decir cuando reviso por ultima vez para que el silencio no se
    lea como aprobacion, y ofrecer "Solicitar revision".

### 2.3 Lo que hace mejor la ciencia que sale

16. **La investigadora mete su propia hipotesis al torneo.** Es el resultado
    mas citado del articulo de Co-Scientist: la "mejor conjetura" del
    experto entra al torneo, mejora con las iteraciones y acaba superando a
    las generadas. En pantalla: boton "Proponer hipotesis" con el mismo
    formulario (enunciado, mecanismo, comprobacion), insignia "Humana", su
    curva Elo junto a las demas, y las versiones que Rosa derive de ella
    enlazadas como "derivada de tu hipotesis".

17. **La revision escrita entra como revision, no solo como veredicto.**
    Co-Scientist usa las revisiones manuales para el ranking y la mejora. En
    pantalla: al refinar o descartar, un campo estructurado (supuestos
    cuestionados, literatura que falta, problema experimental) marcado
    "Revision humana" y visible en el siguiente debate del torneo.

18. **Partidos visibles y confianza del Elo.** Un Elo sin "por que A gano a
    B" ni numero de partidos es opaco. Co-Scientist decide cada partido con
    un debate de tres expertos simulados sobre cinco ejes (correccion,
    utilidad, especificidad, novedad, deseabilidad) y termina "Mejor idea:
    1, porque..."; en 2026 paso a TrueSkill con incertidumbre. En pantalla:
    pestana "Partidos" por hipotesis (rival, resultado, resumen del debate),
    "n = 12 partidos" junto al Elo con aviso cuando son pocos, y la nota fija
    "Elo inicial 1200; funciona como el ranking de ajedrez".

19. **Meta-revision: debilidades recurrentes de la corrida.** El agente de
    meta-revision de Co-Scientist sintetiza lo que se repite en todas las
    revisiones (por ejemplo "5 de 9 hipotesis asumen X sin control") y lo
    inyecta en la siguiente generacion. En pantalla: tarjeta por iteracion
    con las debilidades recurrentes y un boton "Inyectar como criterio de
    revision" (Rosa ya tiene criterios en Ajustes).

20. **Arbol de supuestos y tipos de revision separados.** La "verificacion
    profunda" de Co-Scientist descompone la hipotesis en supuestos y
    sub-supuestos con estado (respaldado, plausible, sin evidencia,
    contradicho), independientes de las citas; la revision "de observacion"
    da un veredicto de cinco niveles (ya explicado, otras explicaciones mas
    probables, pieza que faltaba, neutral, refutada). En pantalla: columna
    "Supuestos" en cada hipotesis con nodos anidados y un boton "cuestionar"
    que genera la pregunta de sondeo.

21. **Grafo de proximidad de hipotesis y arbol de exploracion.** Co-Scientist
    agrupa hipotesis parecidas para deduplicar y ensenar diversidad; Kosmos
    dibuja el camino de hipotesis generadas, probadas y refutadas hasta el
    hallazgo (su figura 8d); Sakana y ShinkaEvolve dibujan el arbol de
    experimentos con ramas muertas y el nodo que sembro la etapa siguiente.
    En pantalla: vista alternativa a la lista con nodos por cluster
    mecanistico (microglia y TREM2, tau, vascular), tamano por Elo, y
    "mostrar solo el mejor de cada cluster"; por informe, el arbol de
    hipotesis con nodos verdes, rojos y grises enlazados a su trayectoria.

22. **Objetivo parseado en preferencias, atributos y restricciones, con
    chat previo y linter.** Co-Scientist convierte el objetivo en una
    configuracion (Preferences, Attributes: novedad y factibilidad,
    Constraints) que alimenta todos los prompts, y el producto de Google
    Labs abre un chat para refinar el reto antes de lanzar; Edison publica
    reglas de que es un buen objetivo (uno solo, escala de semanas a meses,
    contexto experimental) y admite que "las direcciones son sensibles a la
    redaccion", asi que lanzan varias corridas por objetivo. En pantalla: al
    crear la investigacion, Rosa propone la tarjeta de preferencias,
    atributos y restricciones para editar; avisos en linea ("objetivo con
    respuesta obvia", "faltan supuestos del campo"); boton "Probar tres
    parafrasis en una iteracion corta" que ensena que primeras tareas
    propondria con cada redaccion antes de gastar.

23. **Contrato de datos y prueba de humo antes de la corrida larga.** El
    Descubrimiento 4 de Kosmos se contamino por p-valores guardados como 0
    y colisiones de nombres de columna, y siguio horas. Aplica cuando entren
    RNA-Seq o cohortes: paso previo "Comprobacion de datos" con valores
    centinela, columnas sin diccionario y duplicados, y un diccionario de
    columnas que la investigadora aprueba y queda adjunto al dataset.

24. **Replicacion independiente como indicador de confianza.** Kosmos
    confirmo sus hallazgos clave con cinco trayectorias independientes;
    Robin lanza diez analisis y sintetiza el consenso. En pantalla: boton
    "Replicar x5" en una hipotesis, que gasta presupuesto y devuelve "5 de 5
    sostienen", con acceso a cada trayectoria.

25. **Panorama de investigacion y exportacion.** El "research overview" de
    Co-Scientist (direcciones principales, y por cada una razon, hallazgos
    recientes, areas, "por que investigar", "que investigar", idea ejemplo,
    mas "areas inesperadas") es la salida principal que se le ensena al
    cientifico, y se exporta como pagina de Specific Aims del NIH. Rosa no
    tiene una vista de sintesis por encima de las hipotesis. En pantalla:
    pestana "Panorama" y boton "Exportar como Specific Aims" como artefacto
    versionado; mas exportacion BibTeX, RIS y CSV de las fuentes con DOI,
    PMID, NCT, pagina y veredicto; y "Exportar expediente" por hipotesis
    (versiones, decisiones humanas con fecha, trazas, cuadernos, fuentes,
    "aplicable a").

### 2.4 Lo que vendra con el analisis de datos y la fase preclinica

26. **Dial de autonomia por clase de accion.** Magentic-UI distingue
    acciones siempre irreversibles (piden aprobacion), nunca irreversibles
    (pasan) y dudosas (las juzga un modelo); Claude Science da tres estados
    por herramienta de conector (preguntar, permitir siempre, bloquear). En
    pantalla: tabla en Ajustes con filas (buscar literatura, correr
    analisis, gastar mas de N, escribir en el modelo de mundo, descartar
    hipotesis) y columnas "solo sugerir / preguntar / actuar y avisar", con
    aprobacion por lotes y edicion de los argumentos de una accion antes de
    permitirla.

27. **Checkpoints con "volver aqui" y bifurcar desde una iteracion.** Rosa
    bifurca investigaciones completas; falta volver a un punto (LangGraph
    reproduce o bifurca desde un checkpoint con estado editado; Claude Code
    tiene `/rewind` con "restaurar conversacion, codigo o ambos"). En
    pantalla: en cada iteracion anterior, "Volver a este punto" (estado del
    mundo, plan o ambos) y "Bifurcar desde aqui".

28. **Diff del modelo de mundo entre visitas, y conversar con el.** Edison
    expone el modelo de mundo como objeto reutilizable (`world_model_id`) y
    su plan publico es "conversar con el modelo de mundo". En pantalla:
    vista "Que cambio" con los movimientos entre sabido, abierto y
    descartado y quien los decidio; boton "Preguntar al modelo de mundo"
    que responde solo con lo que hay dentro, citando nodos; y al crear una
    corrida, "Partir del modelo de mundo de la corrida X, version N".

29. **Monitor de computo y traspaso al laboratorio.** Claude Science tiene
    una pestana Compute con cada kernel, su memoria y CPU, y un "detener con
    indicacion al agente" ("rehazlo con menos memoria"). Robin y Virtual Lab
    dependen de que una persona ejecute el experimento y suba los datos. En
    pantalla, cuando toque: procesos vivos con parada e indicacion; tarjeta
    "Experimento propuesto" con protocolo, coste, "Asignar a laboratorio",
    estado y zona de carga de datos que arranca los analisis.

30. **Datos sensibles y catalogo de datos de Alzheimer.** Biomni avisa "no
    para informacion de salud protegida"; Biomni-AD trae catalogos de
    NIAGADS, ADSP, SEA-AD, ssREAD, OASIS y el ABC Atlas con acceso abierto o
    controlado. Encaja con la Ley 172-13 y con CONABIOS: al subir un
    fichero, clasificacion (publico, interno, datos de personas) que
    condiciona que herramientas pueden tocarlo y obliga a desidentificar.

31. **Calibracion del juez y del revisor frente a las decisiones humanas,
    y coste por hipotesis.** Robin publica la concordancia de su juez con
    los expertos (7,25 de las 10 mejores); Sakana reporta 69 % de acuerdo de
    su revisor; Andrew White (Edison) cuenta que el acuerdo humano-modelo en
    "gusto cientifico" era del 52 % y que el RLHF sobre hipotesis no
    funciono, asi que usan los clics y descargas de los cientificos como
    senal. En pantalla: en Calidad, matriz "el revisor recomendo / la
    persona decidio" por mes y criterio con los desacuerdos enlazados (es el
    conjunto de entrenamiento de GEPA para el juez); en el ranking, columna
    de coste por hipotesis para ver las caras con Elo bajo.

32. **Vigilancia bibliografica tras la corrida.** Kosmos manda por correo
    los articulos nuevos relevantes un dia despues; Scite y Litmaps avisan
    de nuevas citas contrastantes o retractaciones. En pantalla: al cerrar
    una corrida, "Vigilar literatura 30 dias" que crea tarjetas en el
    modelo de mundo por cada articulo nuevo que toque una hipotesis
    aceptada, con el aviso por Slack o correo que Rosa ya tiene.

## 3. Matices de lo que Rosa ya copio de Claude Science

- La tarjeta de permiso **sustituye la caja de mensaje**: mientras hay una
  pendiente no se escribe. Rosa la pone como bloque aparte; conviene
  probar si bloquear la entrada de "Dirigir" mientras haya permisos
  pendientes hace la decision mas visible.
- Los alcances **varian por tipo de accion**: carpeta (solo lectura o
  lectura y escritura, persiste), codigo (una vez o siempre), red (persiste
  hasta revocar), conector y trabajo remoto (una vez, esta conversacion,
  este proyecto, global). Rosa ya varia los alcances por solicitud; falta
  fijar el juego por tipo en el contrato con el backend.
- La tarjeta de trabajo remoto ensena **el comando y el script completos**;
  la de Modal, la maquina, la facturacion por segundo y el tiempo maximo.
  Rosa ensena el recurso; cuando haya analisis, ensenar el codigo exacto.
- Que pasa al **denegar** no esta documentado en ningun sitio publico. Rosa
  lo define: la solicitud queda denegada, la corrida sigue y Rosa se entera
  en su siguiente paso.
- El plan **no se edita a mano** en Claude Science (se itera conversando).
  Los sistemas para Alzheimer (Biomni-AD) y los de agentes generales
  (Magentic-UI) si dejan editarlo. Para una medica, editar la lista es mas
  directo que negociar en prosa.
- El revisor corre **periodicamente durante el trabajo largo**, no solo tras
  cada mensaje, y se puede pedir con "Request review".
- Las pistas paralelas **no se paran una a una** en Claude Science (Stop
  mata la sesion). Rosa puede mejorarlo con parada por pista.
- Los comentarios se anclan tambien a **imagenes (pines numerados
  arrastrables)** y a la **transcripcion de la sesion**; una vez enviados
  desaparecen del artefacto y quedan como tarjetas en el mensaje; se pueden
  editar y borrar antes de enviar. Rosa ancla solo texto y no edita.
- Hay atajos: `@` artefacto, `#` sesion pasada, `/` skill, y `Cmd+K` como
  busqueda global de sesiones y proyectos. Rosa no tiene busqueda global.
- Claude Science muestra la **ocupacion del contexto** (a donde van los
  tokens) y marca cuando compacto el historial. Para dias de corrida explica
  por que el agente "olvida".

## 4. Referencias de implementacion utiles para el backend de Rosa

- **Kaimen-Inc/Co-Scientist** (abierto): `co-scientist serve` levanta un
  panel FastAPI, htmx y SSE con actualizacion en vivo, y comandos `status`,
  `pause`, `resume`, `abort` y `feedback <id> --kind directive`. Guarda un
  JSON por hipotesis y por partido de torneo. Es el bucle de Co-Scientist
  con exactamente los controles que Rosa pinta.
- **Kaimen-Inc/Biomni-AD** (abierto, premio Alzheimer's Insights AI Prize
  2026): plan-luego-aprobar en Chainlit, traza plegable por paso, y
  catalogos de datos de Alzheimer.
- **llnl/open-ai-co-scientist** y **jataware/open-coscientist**:
  reimplementaciones del torneo con generacion, revision de seis criterios,
  ranking, meta-revision, evolucion y deduplicacion por proximidad.
- **LangChain Agent Inbox**: cola de acciones interrumpidas con cuatro
  respuestas (aceptar, editar, responder, ignorar).
- **API de Deep Research de OpenAI**: cada paso como item tipado y cada
  cita con `start_index` y `end_index` para resaltar el tramo exacto del
  texto que respalda; replicable en el verificador de Rosa.
- **Kosmos no esta disponible por API** (lo dice su documentacion); el
  co-scientist de Google es de acceso restringido por cuenta comercial.

## 5. Lo que no se pudo ver

- Ninguna captura de la interfaz del co-scientist de Google, ni como ensena
  el Elo o el grafo de proximidad.
- La pantalla de progreso de Kosmos y cualquier visor de su modelo de
  mundo; sus paginas de precios y preguntas frecuentes dan 404.
- La pagina de Especialistas de Claude Science (como se crea uno), los
  valores del estado de una tarjeta del revisor y de un marcador de pista,
  y el texto exacto al denegar un permiso.
- Los centros de ayuda de Consensus, OpenAI, Perplexity y Scite (403);
  cubiertos con fuentes secundarias.
- Las interfaces de Lila Sciences, Periodic Labs y el "research intern" de
  OpenAI: solo descripciones de prensa.

## 6. Fuentes principales

Claude Science: https://claude.com/docs/claude-science/core-concepts ,
https://claude.com/docs/claude-science/artifacts ,
https://claude.com/docs/claude-science/the-reviewer ,
https://claude.com/docs/claude-science/comments ,
https://claude.com/docs/claude-science/changelog ,
https://claude.com/docs/claude-science/remote-compute-clusters ,
https://claude.com/docs/claude-science/glossary ,
https://www.anthropic.com/research/long-running-Claude ,
https://www.anthropic.com/research/measuring-agent-autonomy ,
https://platform.claude.com/docs/en/managed-agents/budgets ,
https://code.claude.com/docs/en/agent-view ,
https://code.claude.com/docs/en/checkpointing ,
https://www.the-scientist.com/early-verdicts-on-claude-science-faster-workflows-but-gaps-remain-74745 ,
https://optimizewithsanwal.com/claude-science-review/

Kosmos y Edison: https://arxiv.org/abs/2511.02824 ,
https://advances.edisonscientific.com/research/announcing-kosmos/ ,
https://advances.edisonscientific.com/research/how-we-built-kosmos/ ,
https://docs.edisonscientific.com/edison-client/docs/kosmos_guidelines ,
https://docs.edisonscientific.com/edison-client/agent-configurations ,
https://docs.edisonscientific.com/edison-client/methods/chat-sessions ,
https://advances.edisonscientific.com/research/edison-literature-agent/ ,
https://arxiv.org/html/2505.13400 (Robin) ,
https://arxiv.org/html/2409.13740v1 (PaperQA2) ,
https://www.latent.space/p/edison ,
https://www.alzforum.org/news/research-news/introducing-kosmos-ai-scientist-makes-discoveries-overnight

Co-Scientist y Biomni: https://www.nature.com/articles/s41586-026-10644-y ,
https://arxiv.org/abs/2502.18864 ,
https://labs.google/science/ ,
https://www.biorxiv.org/content/10.1101/2025.02.19.639094v1.full (Imperial) ,
https://arxiv.org/abs/2608.26701 ,
https://www.science.org/doi/10.1126/science.adz4351 ,
https://github.com/snap-stanford/Biomni ,
https://github.com/Kaimen-Inc/Biomni-AD ,
https://github.com/Kaimen-Inc/Co-Scientist ,
https://github.com/llnl/open-ai-co-scientist ,
https://www.biorxiv.org/content/10.64898/2026.05.12.724604v1.full (BiomniBench)

Literatura: https://elicit.com/blog/systematic-review-for-prisma-2020 ,
https://consensus.app/home/blog/new-consensus-meter/ ,
https://consensus.app/home/blog/deep-search/ ,
https://www.undermind.ai/whitepaper.pdf ,
https://scite.ai/features ,
https://scite.ai/blog/how-do-i-use-the-scite-reference-check ,
https://www.zotero.org/blog/retracted-item-notifications/ ,
https://www.semanticscholar.org/product/semantic-reader ,
https://arxiv.org/html/2602.23335v1 (Asta ScholarQA) ,
https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt ,
https://developers.openai.com/cookbook/examples/deep_research_api/introduction_to_deep_research_api ,
https://support.google.com/gemini/answer/15719111 ,
https://www.jmir.org/2026/1/e88766 (retractaciones) ,
https://www.technologyreview.com/2025/09/23/1123897/ai-models-are-using-material-from-retracted-scientific-papers/ ,
https://www.techtarget.com/healthtechanalytics/news/366645822/OpenEvidence-adds-real-time-evidence-quality-grading-to-AI ,
https://pubmed.ncbi.nlm.nih.gov/42212591/ (estabilidad de citas de Elicit)

AI Scientist abiertos y humano en el bucle:
https://github.com/SakanaAI/AI-Scientist-v2 , https://arxiv.org/html/2504.08066 ,
https://arxiv.org/html/2509.08713v1 (fallos ocultos de los AI Scientist) ,
https://github.com/SamuelSchmidgall/AgentLaboratory ,
https://github.com/zou-group/virtual-lab ,
https://arxiv.org/html/2510.26887v1 (Denario) ,
https://arxiv.org/html/2507.22358 (Magentic-UI) ,
https://arxiv.org/abs/2605.08956 ,
https://arxiv.org/abs/2606.12848 ,
https://arxiv.org/abs/2605.20025 ,
https://arxiv.org/html/2506.09038v1 (AbstentionBench) ,
https://docs.langchain.com/oss/python/langgraph/use-time-travel ,
https://github.com/langchain-ai/agent-inbox ,
https://docs.temporal.io/guides/reliable-document-approvals ,
https://developers.openai.com/api/docs/guides/agents/guardrails-approvals ,
https://www.agentic-ux.com/framework ,
https://azure.microsoft.com/en-us/blog/announcing-microsoft-discovery-general-availability-and-microsoft-discovery-app-preview/
