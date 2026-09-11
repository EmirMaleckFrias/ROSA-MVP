# La interfaz de Rosa: lo que se toma de Claude Science y lo que Rosa añade

Escrito el 10 de septiembre de 2026 a partir de la documentación oficial de
Claude Science (claude.com/docs/claude-science) y de sus reseñas. Claude
Science es la referencia comercial más cercana a la mitad de Rosa que analiza
con procedencia y revisor; su interfaz está pensada por gente que ya se
enfrentó a los mismos problemas, así que conviene copiar la forma y no
reinventarla. Lo que Claude Science no tiene, el bucle autónomo de días con
memoria estructurada y ranking de hipótesis, es lo que Rosa añade.

## 1. El modelo conceptual de Claude Science, tal como lo documenta Anthropic

- **Proyecto**: agrupa sesiones y los artefactos que producen; guarda
  instrucciones personalizadas que Claude lee al empezar cada sesión; los
  permisos de carpeta concedidos persisten dentro del proyecto.
- **Sesión**: un hilo de conversación, con su carpeta de trabajo y varios
  kernels en marcha (Python y R persistentes: variables, dataframes y modelos
  cargados se quedan en memoria).
- **Artefacto**: un fichero que Claude guarda en el proyecto (figura, dataset
  procesado, informe, cuaderno). Persiste hasta que se borra; lo demás que
  escribe en una sesión es temporal y se limpia a las pocas horas.
- **Versiones**: guardar el mismo nombre de fichero crea una versión nueva;
  hay un selector de versiones y un modo diff contra cualquier versión
  anterior; las versiones viejas son de solo lectura; los enlaces de la
  conversación apuntan a la versión que existía en ese momento.
- **Procedencia**: cada versión de artefacto tiene cinco pestañas:
  **Mensajes** (la conversación alrededor del guardado), **Código** (script
  reproducible, descargable como script o cuaderno), **Registro de ejecución**
  (cada comando que corrió; es la fuente autoritativa: si el código y el
  registro discrepan, manda el registro), **Entorno** (lenguaje, versiones,
  cada paquete instalado con su versión) y **Revisión** (hallazgos del
  revisor).
- **Plan aprobado**: ante trabajo de varios pasos Claude propone un plan; el
  usuario lo aprueba o lo refina conversando (el texto del plan no se edita
  a mano); los pasos aprobados aparecen en la conversación y se marcan como
  completados según avanza el trabajo.
- **Tarjetas de permiso**: aparecen en la conversación cada vez que Claude
  necesita un tipo de acceso nuevo, con el nombre exacto de lo que pide y
  alcance elegible. Acceso a carpeta (solo lectura o lectura y escritura,
  persiste hasta revocar); ejecutar código, comando de shell o instalar
  paquetes (una vez o siempre); conectar a un host de red (persiste); usar
  una herramienta de conector (una vez, esta conversación, este proyecto,
  global); lanzar un trabajo remoto (idem). Todo lo concedido se lista en
  Ajustes > Permisos y se revoca ahí.
- **Sandbox**: todo el código corre en un sandbox del sistema operativo que
  solo ve la carpeta de trabajo y las concedidas; red denegada por defecto,
  con un proxy local que solo deja pasar gestores de paquetes, las bases de
  datos de los conectores destacados y los hosts aprobados.
- **Delegación**: Claude divide una petición en pistas independientes que
  corren en paralelo; por cada pista aparece un marcador en la conversación
  con indicador de estado; al pulsarlo se abre la transcripción de esa pista;
  Parar detiene toda la sesión.
- **El revisor**: paso de verificación integrado que relee las respuestas
  recientes, el plan aprobado, los artefactos guardados y el registro de
  ejecución, y comprueba que las afirmaciones casan con lo que corrió. Corre
  solo tras cada respuesta y periódicamente en trabajos largos, y a petición
  con **Solicitar revisión**. Ejemplos de lo que caza: un resultado dado como
  calculado cuando nada corrió; un valor que contradice el fichero de donde
  sale; una cita que no sostiene la afirmación; un DOI que resuelve a otro
  artículo; un paso del plan aprobado sin completar; una conclusión que no se
  sigue del método. No re-ejecuta análisis ni juzga si el método era el
  adecuado. Cada hallazgo aparece como **tarjeta debajo del mensaje** al que
  se refiere, con su estado; más de tres hallazgos muestran los tres primeros
  y un "mostrar todo"; al pulsar se ve el razonamiento completo. Claude lee
  los hallazgos y los atiende en su siguiente mensaje, corrigiendo o
  explicando por qué no aplica. En Ajustes > Especialistas se añaden criterios
  propios de revisión, que se suman a los integrados y no pueden debilitarlos.
- **Comentarios**: se anclan a partes concretas de un artefacto en vez de
  describir el sitio en prosa: selección de texto en Markdown, texto plano,
  LaTeX o código; selección en un PDF; un punto en una imagen o figura; un
  elemento de un informe HTML; también sobre la transcripción de la sesión.
  Aparecen como insignia resaltada (texto) o pin numerado (imagen). Guardar
  no envía: los pendientes se acumulan sobre el cuadro de escritura y salen
  con el siguiente mensaje, para poder agrupar varios. Claude recibe cada uno
  con el fichero, la selección citada y la nota. No hay hilos ni estado de
  resuelto; para revisar de nuevo se comenta sobre la versión nueva. Tope de
  1.000 caracteres.
- **Anotar una figura**: se marca la figura y se pide el cambio en lenguaje
  natural; Claude lee el código que la produjo y lo edita directamente.
- **Bifurcar**: se puede bifurcar una sesión en cualquier punto para comparar
  dos enfoques sin perder el hilo original.
- **Panel Files**: rejilla con buscador de todos los artefactos del proyecto;
  menú por artefacto: abrir, abrir junto a la sesión, **ver en contexto**,
  **procedencia**, versiones, copiar enlace, destacar, renombrar, descargar,
  borrar; los ficheros subidos van bajo "Tus subidas".
- **Atajos del cuadro de escritura**: `@` inserta un artefacto o fichero por
  nombre, `#` inserta una sesión pasada por título, `/` inserta una skill.
- **Memoria**: hechos cortos sobre la persona, sus proyectos y sus ficheros,
  guardados en la base local; se activa en la configuración inicial y se
  gestiona en Ajustes > Memoria (listar, editar, borrar); hay un interruptor
  por sesión; el administrador puede apagarla para la organización.
- **Datos**: aplicación local (abre en una pestaña del navegador pero no es un
  sitio web); historial y artefactos en `~/.claude-science`; los ficheros se
  leen y escriben en su sitio; lo que se envía a Anthropic es el prompt y la
  respuesta de cada llamada, bajo su política estándar de retención; el
  cómputo remoto (SSH, HPC, Modal) recibe código y datos directamente sin
  pasar por Anthropic. En Enterprise con Compliance API, Anthropic guarda las
  transcripciones seis años por defecto, salvo periodo personalizado.
- **Render científico nativo**: estructuras 3D de proteínas, pistas de
  navegador genómico, dibujos de estructuras químicas, tablas y figuras.

## 2. Qué se toma tal cual para Rosa

| Patrón de Claude Science | En Rosa |
|---|---|
| Proyecto con sesiones e instrucciones propias | **Investigación** con corridas; las instrucciones del proyecto son el objetivo, los límites y la condición de parada |
| Plan propuesto, aprobado, con pasos que se marcan | Cada iteración del bucle propone su plan; los pasos se marcan según avanzan. El RAG ya lo hace con las partes de una pregunta que se ponen en verde |
| Tarjetas de permiso con alcance (una vez, esta conversación, este proyecto, global) | Idéntico para: acceder a un corpus, gastar un presupuesto grande, lanzar un trabajo largo, llamar a una fuente externa, y sobre todo **aceptar una hipótesis en el modelo de mundo** |
| Marcadores de pistas paralelas con estado, pulsables para ver la transcripción | Las búsquedas y extracciones paralelas de cada iteración |
| Artefactos versionados con diff | Informes, tablas de hipótesis, el estado del modelo de mundo por iteración |
| Procedencia en cinco pestañas, con el registro de ejecución como fuente autoritativa | Idéntico: mensajes, código, registro, entorno, revisión. Rosa añade una sexta: **Fuentes**, los fragmentos citados con su página |
| Revisor como tarjetas bajo el mensaje, tres visibles y "mostrar todo", con razonamiento al pulsar, y el agente respondiendo a los hallazgos | Es exactamente la barrera de verificación del RAG: una tarjeta por afirmación bloqueada, y la corrección del redactor como respuesta. Se copia la forma |
| Criterios propios de revisión que se suman y no debilitan los integrados | Las reglas del proyecto (qué cuenta como relevante, qué cita es aceptable) se añaden al verificador sin poder relajar las deterministas |
| Comentarios anclados, agrupados y enviados con el siguiente mensaje | La revisión humana de hipótesis: la investigadora marca la frase o la cifra y escribe una línea; se envían juntas |
| Anotar una figura y pedir el cambio en lenguaje natural | Lo mismo sobre tablas de hipótesis e informes |
| Bifurcar una sesión para comparar enfoques | Bifurcar una investigación para perseguir dos hipótesis rivales |
| `@` artefacto, `#` sesión pasada, `/` skill | Idéntico; `#` para citar una iteración anterior |
| Memoria local, listada, editable, con interruptor | La memoria de Rosa sobre la investigadora y sus preferencias, aparte del modelo de mundo, que es del proyecto |
| Files con buscador, "ver en contexto", "procedencia", destacar | Idéntico |

## 3. Qué Rosa necesita y Claude Science no tiene

1. **Una investigación que corre sin nadie delante.** Claude Science es una
   sesión con una persona al otro lado. Rosa necesita la vista de una corrida
   de días: iteración actual, qué está leyendo, qué encontró, gasto, botones
   de pausar, reanudar, dirigir y parar, y **avisos por correo o Slack** cuando
   haya hallazgos que revisar, como hace Kosmos.
2. **La cola de revisión de hipótesis.** Aceptar, descartar, refinar, con la
   procedencia en un cajón lateral. Los comentarios de Claude Science son la
   mecánica; la cola con estados es lo nuevo. Regla: una hipótesis no entra al
   modelo de mundo como aceptada sin pasar por aquí.
3. **El ranking.** Una lista ordenada de hipótesis con su puntuación (Elo o
   equivalente), su historial de revisiones y sus rivales, como el torneo de
   Co-Scientist.
4. **El explorador del modelo de mundo.** Qué se sabe, con qué procedencia; qué
   está abierto; qué se descartó y por qué. Claude Science tiene memoria de
   hechos cortos sobre el usuario; Rosa necesita memoria estructurada sobre la
   enfermedad.
5. **El tablero de calidad.** Métricas del juez, casos aprobados, resultados de
   las optimizaciones de GEPA (MLflow presta su interfaz para esto último).
6. **Español**, y la regla del RAG: todo lo que haga la investigadora va con
   botones y estado visible, sin variables de entorno ni terminal.

## 4. Sobre el sustrato

Claude Science es una aplicación de escritorio local. Rosa corre en servidores
propios (y en las Mac) y la usan dos personas hoy y un equipo clínico mañana,
así que es web. El frontend del RAG (React, Vite, suscripciones reactivas de
Convex) ya trae los pasos en vivo, el panel de fuentes con página exacta, la
insignia de verificación por afirmación y la pestaña de Calidad; con la
reactividad de Convex, una fila que cambia refresca la pantalla sola, que es
justo lo que pide mirar una corrida de días. Decisión pendiente (de la persona responsable y su
compañero): si el frontend de Rosa nace del del RAG o de cero. Inferencia mía:
nacer del del RAG ahorra semanas y ya encarna estas reglas.

## 5. Fuentes

- https://claude.com/docs/claude-science/core-concepts
- https://claude.com/docs/claude-science/artifacts
- https://claude.com/docs/claude-science/the-reviewer
- https://claude.com/docs/claude-science/comments
- https://claude.com/docs/claude-science/how-claude-science-works-with-your-data
- https://claude.com/docs/claude-science/get-started
- https://claude.com/product/claude-science
- https://www.anthropic.com/news/claude-science-ai-workbench
- https://mer.vin/2026/07/claude-science-explained-anthropics-ai-workbench-for-reproducible-research/
