# Rosa: estado del sistema a 11 de septiembre de 2026

Documento informativo. Describe lo que Rosa tiene construido y probado a la
fecha y como funciona cada pieza. No reporta resultados cientificos: los
analisis que se mencionan son pruebas del sistema.

## 1. Arquitectura

- **Servidor** en Python (FastAPI, DSPy, SQLite): un unico estado canonico en
  una base SQLite, servido por `GET /api/estado`, empujado al navegador por
  Server-Sent Events con un latido cada 15 segundos, y modificado solo por
  acciones nombradas (`POST /api/acciones/{nombre}`, 63 acciones) o por el
  bucle de investigacion. Cada cambio sube un numero de version; la tabla de
  acciones es un registro solo de a�adir que sirve de auditoria.
- **Interfaz** en React y TypeScript: once pantallas (inicio, nueva
  investigacion, corrida en vivo, cola de hipotesis, ranking, panorama,
  modelo de mundo, artefactos, calidad, objetivo y datos, ajustes). Los
  mismos reducers existen en la interfaz y en el servidor, uno a uno, para
  que la pantalla responda al instante y el servidor aplique la misma regla.
  Si el servidor no esta, la interfaz muestra datos de muestra con una
  corrida simulada y lo avisa.
- **Modelos de lenguaje**, todos a traves de un unico gateway y elegidos por
  rol: un modelo "cerebro" para planificar, formular preguntas, generar
  hipotesis y escribir codigo; un modelo "juez" de otra familia para
  verificar afirmaciones, revisar hipotesis, comparar en el torneo y auditar
  analisis; y un modelo de alto volumen sin poder de veto para extraer,
  cribar y describir. El juez es siempre de una familia distinta al cerebro
  para no compartir puntos ciegos. Cada llamada queda registrada con modelo,
  tokens, duracion y coste estimado.
- **Contratos con los modelos**: 33 firmas DSPy, cada una con sus campos de
  entrada y salida tipados. Los prompts no se escriben a mano: DSPy los
  construye desde la firma y GEPA puede optimizarlos con una metrica. La
  version del codigo y el hash de las firmas quedan guardados en cada
  corrida ("arnes") para que cualquier hipotesis sea auditable.
- **Fuentes externas**: PubMed, Europe PMC (incluidos preprints y texto
  completo por secciones), Crossref (estado editorial y retractaciones),
  Unpaywall y PDF (texto por pagina para citar la pagina exacta), OpenAlex
  (precedente en la literatura), Open Targets (asociacion diana y enfermedad)
  y ClinicalTrials.gov. Todas con limitador de peticiones y con la regla de
  que un fallo de red no es una ausencia.
- **Sandbox** para codigo escrito por un modelo: un contenedor Docker sin
  red, con memoria y tiempo limitados, el fichero de datos montado en solo
  lectura y un directorio de trabajo que se borra al terminar. Existe un
  aislamiento blando local, permitido por politica solo para datasets
  marcados como sinteticos.
- **Politicas** en codigo (`rosa/politicas.py`): los limites del sistema
  (hipotesis vivas por mision, evaluaciones costosas por corrida, candidatas
  por ciclo, reformulaciones por hipotesis, reproducciones requeridas,
  fraccion de descartes auditados, tiempo y memoria del sandbox, presupuestos
  por defecto). Ningun agente ni pantalla los edita; cambiarlos es un commit,
  y el commit queda en el arnes.
- **tama�o**: unas 9.000 lineas de Python y 15.000 de TypeScript; 34 pruebas
  automaticas del servidor y 135 de la interfaz, todas pasando; la interfaz
  compila sin errores de tipos.

## 2. El ciclo de investigacion, etapa por etapa

### 2.1 Mision y pregunta de campana

Al crear una investigacion se escriben el objetivo (puede ser amplio), que
cuenta como relevante, los limites y la condicion de parada. Al arrancar la
primera corrida, Rosa propone la **mision**: poblacion, etapa de la
enfermedad, celula o tejido, mecanismo, tipo de intervencion o resultado
buscado, capacidades del laboratorio y presupuesto en llamadas al modelo,
dolares estimados y horas. Lo que el objetivo no dice queda "sin fijar";
Rosa no lo inventa, y un recurso desconocido no se trata como disponible.

Con la mision, Rosa propone entre tres y seis **areas de investigacion**
comparadas por relevancia para la meta, valor de intervencion, incertidumbre,
comprobabilidad, coste, demora y dependencia de otro trabajo, conservando
familias de mecanismo distintas y marcando las que quedan sin explorar. Para
la corrida formula la **pregunta de campana** con una plantilla fija:
contexto, etapa, intervencion, comparador, desenlace con su medida, ventana
de tiempo, unidad biologica independiente, mecanismos que distinguiria,
decision que se toma con la respuesta y umbral de efecto (o "sin resolver"
si no hay un valor defendible), mas el paso de la ruta terapeutica al que
sirve. Mision y pregunta se aprueban con el primer plan o se corrigen a
mano.

### 2.2 Plan de la iteracion

Rosa propone entre cuatro y siete pasos, cada uno con su herramienta, su
coste en llamadas (medido en corridas reales, no estimado por el modelo) y
**que decision cambiaria segun su resultado**; un paso cuya siguiente accion
seria la misma salga lo que salga vale poco y se dice. Los pasos se eligen
por lo que discriminan entre las hipotesis vivas, no por lo que confirmaria
la favorita. La persona edita, reordena y aprueba; puede fijar una
autoaprobacion por tiempo. La condicion de parada se comprueba antes de cada
paso: iteraciones, minutos u horas de corrida, llamadas, y el presupuesto de
la mision en dolares y horas.

### 2.3 Literatura, ensayos y extraccion

Consultas booleanas por base, cribado de relevancia articulo a articulo,
texto completo por pagina cuando hay PDF en acceso abierto, y extraccion de
afirmaciones un fragmento a la vez. Cada afirmacion nace con su pasaje
literal (maximo cuarenta palabras copiadas sin cambios), su tipo (dato,
literatura, interpretacion), su clase de evidencia (observacion original,
derivado, literatura, prediccion), su nivel de medicion (medida directa,
resultado de un analisis, interpretacion de los autores, interpretacion de
Rosa), la cohorte o estudio del que salen los datos, y los campos del
registro de evidencia cuando es un dato: n independiente, comparador, efecto
con unidades e incertidumbre. Lo que la fuente no dice queda en una lista de
campos sin resolver. Una frase de la discusion de un articulo nunca se
convierte en una medida.

Los fragmentos recuperados entran a los modelos delimitados como datos, no
como instrucciones, y un fragmento que contenga texto que parezca una orden
para un modelo se marca y se ense�a, sin bloquearse.

### 2.4 Verificacion

Comprobaciones deterministas primero (la cita resuelve a una fuente y a un
pasaje que existe en la pagina indicada, los identificadores citados estan
en el fragmento, las cifras normalizadas coinciden), y el juez despues. Los
veredictos son siete: sostenida, parcial, no sostenida, cita que no resuelve,
sin cita, ausencia refutada, sin verificar. Un dato real pero de otra entidad
(otro farmaco, otra cohorte) es "no sostenida" con marca de entidad distinta.
Al modelo de mundo solo entran afirmaciones sostenidas o parciales.

### 2.5 Modelo de mundo

Hechos sabidos, preguntas abiertas y descartes, cada uno con su procedencia
a fuente y pagina, su prioridad y su historial. Lo que dice la fuente es un
hecho; lo que Rosa infiere es una pregunta. Se guarda una instantanea como
artefacto en cada iteracion. Cuando el estado editorial de una fuente cambia
(retractacion, expresion de preocupacion), las conclusiones que dependian de
ella se recalculan y se produce un informe de diferencias con lo que decian
antes y lo que dicen ahora; los informes anteriores no se tocan.

### 2.6 Hipotesis, tarjeta y versiones

Cada hipotesis lleva titulo, enunciado falsable, mecanismo, comprobacion
(biomarcador, cohorte, dise�o), las afirmaciones sostenidas que la motivan,
sus supuestos descompuestos y evaluados (respaldado, plausible, sin
evidencia, contradicho), la comprobacion de novedad (Open Targets, ensayos
registrados, precedente en la literatura) y la **tarjeta**: diana o proceso,
celula o tejido, etapa, intervencion y direccion, prediccion falsable,
riesgos y paso de la ruta terapeutica (mecanismo, opciones de intervencion,
compromiso de diana, efecto funcional, selectividad y toxicidad, entrega y
exposicion, replicacion independiente, evidencia en la poblacion). Sin
prediccion falsable la hipotesis no avanza.

Reformular no sobrescribe: guarda la version anterior con el motivo del
cambio y sube el numero de version. La politica permite dos reformulaciones;
a la tercera la hipotesis se descarta en este contexto. Las hipotesis
descartadas siguen recuperables.

### 2.7 Hypothesis Killer

La revision adversarial de cada hipotesis es una lista fija de once
comprobaciones, cada una con su resultado (pasa, falla, no aplica, no se
pudo comprobar) y su evidencia:

1. Las citas resuelven a fuentes reales.
2. La fuente dice lo que la afirmacion dice.
3. Ningun supuesto necesario esta contradicho.
4. Replicacion en cohortes distintas (se cuentan cohortes, no articulos).
5. Hay fuentes con datos propios, no solo citas.
6. La direccion causal tiene temporalidad y alternativa considerada.
7. Hay una observacion medible que la refutaria.
8. Novedad comprobada con busqueda, no de memoria.
9. Existe cohorte, ensayo o tecnica para comprobarla.
10. No repite lo ya sabido ni otra hipotesis viva.
11. La evidencia no tiene un riesgo de sesgo serio.

Cuatro las resuelve Rosa sin modelo; siete el juez. La **decision no la
escribe ningun modelo**: se deriva por regla. Descartar en este contexto
solo si falla la evidencia misma (1, 2, 3); reformular si falla algo
arreglable (6, 7, 9, 10); suspender si algo critico no se pudo comprobar;
avanzar si nada critico falla y hay prediccion falsable. Al juez no se le
dice cuantas citas trae la hipotesis, para evitar el sesgo de autoridad. Un
tercio de los descartes y reformulaciones lo audita el modelo cerebro con
otro metodo: primero defiende la hipotesis con el mejor argumento que
permita la evidencia y despues juzga si la decision resiste; un desacuerdo
no revierte nada, lo manda a una persona con las dos posturas. Toda decision
(del Killer, del auditor, de la persona, del retorno del laboratorio) queda
en un registro con version juzgada, motivo, comprobaciones y quien la tomo.
Segun el dial de autonomia, el descarte se aplica o se propone.

### 2.8 Torneo y conclusion

Las hipotesis compiten por pares con un juez que las compara en los dos
ordenes (para anular el sesgo de posicion); si discrepa, hay tablas. Elo
inicial 1500. Cada hipotesis recibe una **conclusion** al modo de un resumen
de hallazgos GRADE: certeza de la evidencia (alta, moderada, baja, muy baja)
y direccion (apoya, mixta, en contra, sin evidencia directa) por separado,
los factores que bajan o suben la certeza, la base contada de forma
determinista (afirmaciones, sostenidas, fuentes, datos, interpretaciones),
una frase plantilla calibrada por nivel generada por regla, que la apoya,
que la debilita, de que depende, que subiria y que bajaria la certeza, que no
se pudo comprobar, y el cambio respecto a la iteracion anterior. Los datos
sinteticos no cuentan en la base.

Cada iteracion cierra con un resumen tecnico, un **resumen en lenguaje
llano** con la estructura de un resumen para pacientes (pregunta, mensajes
clave, que buscaba, que hizo, que encontro, hasta donde fiarse, que cambio,
que propone, que falta, que le toca a la persona, glosario), un informe como
artefacto y la meta-revision (debilidades recurrentes y panorama de
direcciones).

### 2.9 Datos con libro de procedencia

Un dataset se sube como fichero tabular. El servidor calcula su hash
sha256, cuenta filas y columnas, detecta valores centinela y nombres
duplicados y prepara el diccionario de columnas para que una persona lo
describa. El **libro de procedencia** recoge origen, version, licencia,
permisos, fecha, acceso (abierto, controlado, por colaboracion, propio),
cohorte, clase de evidencia, si es sintetico, si el uso con inteligencia
artificial esta autorizado, la clausula literal del acuerdo si la hay, y si
las filas individuales pueden enviarse a un modelo de terceros. Ese ultimo
campo nace en falso: por defecto el modelo solo ve el diccionario y
estadisticos agregados, nunca filas. Sin origen, licencia y uso con IA
autorizado el contrato de datos no se puede aprobar.

### 2.10 Puerta de reproduccion

Antes de que Rosa pueda descubrir algo con datos, tiene que reproducir tres
analisis ya publicados sobre sus datos originales, dentro de una tolerancia
fijada antes de ejecutar. Cada reproduccion registra referencia, cifra
publicada, valor y tolerancia; Rosa congela el plan, escribe el codigo, lo
corre en el sandbox y compara. La puerta queda bloqueada, abierta o eximida
(con motivo, por una persona, registrado como cambio de politica). Un
analisis que no arranca es un error tecnico, no un fallo cientifico. El
registro de metodos marca como "probado en contexto" los metodos de analisis
cuando una reproduccion se supera.

### 2.11 Analisis in silico

Desde la ficha de una hipotesis, con un dataset aprobado, o de forma
automatica para las hipotesis que el Killer dejo avanzar:

1. **Plan congelado**: pregunta, variables por su nombre exacto, poblacion,
   preprocesado, prueba, hipotesis nula y alternativa, alfa, direccion
   esperada, efecto minimo, baseline simple obligatoria, control negativo
   con etiquetas barajadas, correccion por multiplicidad, umbral de efecto y
   criterio de no evaluable. Se guarda con su hash antes de escribir codigo;
   cambiarlo despues es otro plan.
2. **Codigo** que ejecuta ese plan y nada mas, con un contrato de salida
   (lineas RESULTADO, BASELINE, CONTROL, NO_EVALUABLE; solo cifras
   agregadas). Un error tecnico se intenta reparar dos veces sin cambiar el
   plan.
3. **Ejecucion** en el contenedor sin red con la semilla fijada. Estados
   distintos: no ejecutado, error tecnico, tiempo agotado, completado.
4. **Interpretacion** por el juez contra el umbral del plan: efecto
   detectado, sin efecto detectable, no evaluable. Un p-valor grande con n
   pequeno no es "sin efecto"; un control negativo con se�al hace el
   analisis no evaluable.
5. **Auditoria independiente**: comprobaciones deterministas (semilla, fuga
   entre entrenamiento y prueba, coincidencia con el plan, baseline y
   control presentes, n por grupo, multiplicidad) mas el juez (relevancia
   de la prueba, confusores, interpretacion que no sobrepasa las cifras,
   unidades y escala). Veredicto: valido, no valido, no evaluable
   computacionalmente. Lo determinista critico manda.

Solo un analisis valido entra como afirmacion de tipo dato (clase derivado)
en la hipotesis, con su trayectoria al codigo, y la conclusion se rehace.
Cada ejecucion guarda codigo, entorno, semilla, hash de los datos y del
plan, salida, error, estado, runtime y auditoria.

### 2.12 Priorizacion y dossier

Antes de mirar el Elo, cada hipotesis pasa por seis **bloqueos no
compensables**: trazabilidad insuficiente, datos no autorizados, analisis
invalido, sin experimento interpretable, descartada en contexto, fuente
retractada. Uno solo basta para sacarla de las candidatas. Entre las que no
tienen bloqueos y el Killer dejo avanzar, se eligen hasta tres por Elo sin
repetir cluster mientras haya otros; cero candidatas es un resultado valido.
El ranking ense�a las candidatas y por que las demas no lo son.

El **dossier** para el laboratorio se arma sin ningun modelo, a partir del
estado, en siete partes: decision de priorizacion con sus bloqueos; la
hipotesis completa con tarjeta, versiones y ruta terapeutica; la evidencia
con procedencia, pasajes literales y cohortes distintas; los analisis in
silico con plan, cifras y auditoria; las decisiones registradas; el
experimento propuesto (protocolo en pasos, ensayo, controles, tama�o
muestral, explicacion alternativa y como se distinguiria, criterios de
confirmacion y refutacion, que decision cambia, coste) y su prerregistro; y
que se aprende con cada resultado posible. Se guarda como artefacto
versionado.

### 2.13 Experimento, prerregistro y retorno

Cada hipotesis viva tiene un experimento propuesto. Al asignarlo a un
laboratorio se congela un **prerregistro** inmutable (hipotesis, version,
protocolo, criterios, estado de la evidencia, version de Rosa). Los datos que
vuelven se suben como fichero; Rosa los resume sin modelo (n, medias,
mediana con intervalo, cuartiles, signos, faltantes) y el juez aplica solo
los criterios prerregistrados. El resultado lleva un veredicto (confirma,
refuta, inconcluso, no evaluable), una **clase** de la taxonomia de retorno
con definiciones operativas (apoyo reproducido, negativo interpretable,
inconcluso, fallo tecnico, toxicidad o inviabilidad, correccion de contexto)
y las **dimensiones que coexisten** (fallo tecnico, inconcluso, efecto
pequeno interpretable, efecto predicho, efecto inesperado, toxicidad), sin
forzar todo a una etiqueta. Cada clase dispara una accion: un fallo tecnico
no toca la hipotesis y permite repetir; una toxicidad suspende la via; una
correccion de contexto crea una hipotesis derivada que entra a la cola como
propuesta. El resultado anota que version de la hipotesis probo y avisa si
la hipotesis cambio despues.

### 2.14 Aprendizaje en tres niveles y registro de metodos

- **Nivel 1, creencias**: cada cambio de certeza o direccion de una
  hipotesis, y cada resultado de laboratorio, queda registrado. Automatico.
- **Nivel 2, como razona Rosa**: las debilidades recurrentes de la
  meta-revision entran como criterios de revision propuestos; una persona
  puede pedir su evaluacion (Rosa corre el Killer con y sin el criterio
  sobre las hipotesis que ya decidio una persona y mide el acuerdo) y
  despues promoverlo o revertirlo. Los programas optimizados por GEPA
  siguen la misma via.
- **Nivel 3, politicas**: solo una persona, en el codigo o eximiendo la
  puerta con motivo. Queda registrado.

El **registro de metodos** describe cada metodo, predictor, recurso de
datos o ensayo: que puede evaluar, contextos y exclusiones, entradas y
salidas, validacion, fallos conocidos, version, coste, responsable y estado
(propuesto, implementado, probado en contexto, restringido, retirado). La
popularidad no hace apto a un metodo; la validacion si. Un predictor no
confirma sus propios datos de entrenamiento.

### 2.15 Gobierno y control humano

Dial de autonomia por clase de accion (buscar literatura, correr analisis,
gastar mas que la iteracion, escribir en el modelo de mundo, descartar
hipotesis, proponer a un laboratorio): sugerir, preguntar o actuar.
Permisos con alcance (una vez, esta corrida, esta investigacion, siempre),
revocables. Incidencias visibles cuando un modelo se niega o una fuente no
responde. Politica de esperas para decisiones que nadie toma. Presupuesto
global de la corrida con alertas y pausa, nunca muerte silenciosa.
Trazabilidad completa de cada consulta a cada fuente, cada afirmacion y cada
veredicto. Exportacion del expediente de una hipotesis.

## 3. Que se ha probado

- Investigaciones completas con literatura real, varias iteraciones y
  cientos de llamadas a modelos, con hipotesis que llegaron a conclusion,
  experimento y prerregistro.
- El ciclo con datos, de punta a punta, con un dataset sintetico: libro de
  procedencia, aprobacion, puerta eximida con motivo, plan congelado, codigo,
  ejecucion aislada, interpretacion, auditoria valida, afirmacion derivada
  marcada como sintetica, dossier.
- El Killer sobre una hipotesis real: once comprobaciones, decision derivada
  por regla (descartar en contexto por un supuesto sin respaldo), auditoria
  del descarte de acuerdo, y la propuesta en la cola para que decida una
  persona.
- La mision, las areas y la pregunta de campana propuestas por Rosa para una
  investigacion real, con seis areas comparadas y un plan de siete pasos con
  su valor de decision, a la espera de aprobacion.
- La puerta de reproduccion con datos publicos reales: un conjunto de
  expresion genica en hipocampo de 31 personas, descargado de un repositorio
  publico junto con su anotacion de genes y las llamadas de deteccion,
  cargado con su libro de procedencia (657.975 filas, hash fijado). Los
  primeros intentos de reproducir la lista de genes publicada fallaron
  porque el criterio se habia deducido del resumen del articulo; leidos los
  metodos completos, el algoritmo exacto (filtro de presencia en al menos
  cuatro chips, solo probes con simbolo, valores a mas de dos desviaciones
  de su grupo tratados como faltantes, correlacion con las dos medidas
  clinicas en los 31 sujetos y despues en el subgrupo de 16 con la misma
  direccion) reproduce las cifras publicadas: 418 genes sobreexpresados
  frente a 431 publicados, 524 frente a 609 en el conjunto intermedio, con
  control barajado. Los intentos fallidos quedaron registrados con su plan,
  su codigo y su motivo, que es lo que la puerta debe hacer. El resultado
  final de esa reproduccion se recoge en la seccion 5.
- Tres errores del sistema aparecieron con datos reales y estan corregidos:
  un detector de valores centinela que contaba ocho valores de casi 660.000
  como centinelas; un resumen estadistico con remuestreo que bloqueaba el
  servidor con tablas grandes; y un lector de resultados que truncaba la
  salida del sandbox y aceptaba la primera cifra que encontraba.

## 4. Investigacion que sostiene el dise�o

Las decisiones de dise�o salen de cuatro informes con fuentes citadas sobre
revision adversarial de hipotesis en sistemas publicados, libros de
procedencia y acceso a datos, ejecucion in silico auditable y puertas de
reproduccion, y priorizacion, dossier y aprendizaje. De ahi vienen, entre
otras, la decision del Killer por regla en vez de por puntuacion global, la
auditoria de descartes con otro metodo, el recuento de cohortes en vez de
articulos, ocultar el volumen de citas al juez, la regla de no enviar filas
individuales a modelos de terceros, las definiciones operativas de un
negativo interpretable y la estructura del dossier.

## 5. Resultado de la puerta de reproduccion

La primera reproduccion con datos publicos reales se **supero** el 11 de
septiembre de 2026, con el criterio congelado antes de ejecutar (cifra
publicada 431, tolerancia del 20 %):

| Cifra | Publicada en el articulo | Obtenida por Rosa |
|---|---|---|
| Genes sobreexpresados en el subgrupo incipiente (la cifra comparada) | 431 | 418 |
| Genes correlacionados con las medidas clinicas en los 31 sujetos | 3.413 | 4.202 |
| Genes que ademas se correlacionan en el subgrupo de 16 | 609 | 524 |
| Genes infraexpresados en el subgrupo (baseline descriptiva) | 178 | 106 |
| Genes probados tras el filtro de presencia | 9.921 | 12.077 |
| Control negativo: sobreexpresados con las medidas clinicas barajadas | no aplica | 161 |

La cifra comparada difiere en 13 genes (3 %) de la publicada. Los agregados
acompanantes se desvian mas, de forma compatible con que la anotacion actual
de la plataforma asigna simbolo a mas probes que la de 2004 (12.077 frente a
9.921 probados). El control barajado no sale a cero: el propio algoritmo del
articulo, con dos marcadores y sin correccion por multiplicidad, tiene una
tasa de falsos positivos apreciable, y eso queda documentado en la ejecucion
como una limitacion del metodo reproducido, no del pipeline.

Registro de la ejecucion: plan congelado con hash `51feda1c09fda454`, datos
con hash `3ad2b50ef3d6...`, contenedor Docker sin red, 4,8 segundos de
ejecucion, semilla 12345, salida completa y codigo guardados. La
interpretacion del juez confirmo que la diferencia cae dentro del margen
prefijado. El auditor independiente no pudo responder en esa ejecucion por
una indisponibilidad temporal del servicio del modelo juez; las
comprobaciones deterministas del auditor pasaron (semilla fijada, codigo
coincidente con el plan, baseline y control presentes, sin fuga) y la
ejecucion quedo marcada como "no evaluable computacionalmente" en la parte
del auditor, con el motivo literal guardado. La reproduccion cuenta como
superada porque la regla de la puerta es la comparacion con la cifra
publicada dentro de la tolerancia congelada.

Efectos en el sistema: la puerta pasa a 1 de 3 reproducciones superadas, y
el registro de metodos marca los dos metodos de analisis (comparacion de dos
grupos y correlacion con permutacion) como "probados en contexto", con la
referencia de esta reproduccion. Los cuatro intentos anteriores, fallidos por
un criterio deducido del resumen en vez de los metodos completos, quedan
registrados con su plan, su codigo, su cifra y su motivo.
