# Plan ROSA2018: los dos documentos del programa, mapeados a Rosa

Escrito el 11 de septiembre de 2026. Dos documentos mandan sobre este plan:

1. **ROSA2018 Proyecto Concepto End to End v1.0** (AI Robotics, septiembre
   de 2026): el MVP con demostracion el 31 de octubre de 2026. Diez etapas,
   contratos de datos, criterios de aceptacion, limites (20 hipotesis, 5
   evaluaciones costosas, 0 a 3 candidatos, 2 reformulaciones).
2. **ROSA2018 complete system plan** (10 de septiembre de 2026): la
   arquitectura completa del programa, en etapas A a G, sin fecha de cierre.
   El MVP es su primer demostrador, no la sustituye. Rosa elige el alcance
   desde una meta amplia; los resultados actualizan todo lo compatible; las
   hipotesis rechazadas siguen recuperables.

Los dos son propuestas: ninguno reporta software implementado ni rendimiento
cientifico validado. Este fichero dice que hay hecho en Rosa a fecha de hoy,
que falta, y en que etapa cae cada cosa. Los nombres de los registros son los
del anexo del documento de concepto y de la seccion 10 del plan completo,
traducidos: Programme y DiseaseMission son `mision`; Campaign es la corrida
con su `pregunta`; HypothesisVersion son `version` y `versiones`; EvidenceClaim
son las afirmaciones con `clase`, `nivelMedicion` y registro; Run es
`ejecuciones`; ActionPlan y AnalysisPlan son `planesAnalisis`; LabOutcome es
`experimento.resultado`; Decision es `decisiones`; MethodVersion es `metodos`;
ChangeProposal y LearningChange son `aprendizaje`.

La investigacion que sostiene las decisiones de dise�o (revision adversarial,
procedencia, ejecucion in silico, priorizacion y aprendizaje) esta en
`INVESTIGACION-ROSA2018.md`.

## 1. Las diez etapas del documento de concepto

| Etapa | Que pide | Estado en Rosa (11 de septiembre) | Donde |
|---|---|---|---|
| 0. Mision cientifica | Poblacion, etapa, celula o tejido, mecanismo, tipo de intervencion, capacidades del laboratorio; Rosa propone, una persona aprueba | Hecho. Rosa propone la mision al arrancar la primera corrida y ademas las areas de investigacion comparadas (plan completo, seccion 1). Se aprueba con el primer plan o en Objetivo y datos. Presupuesto en llamadas, dolares estimados y horas | `ProponerMision`, `ProponerAreas`, `aprobar_mision`, pantalla Objetivo y datos, tarjeta en Corrida |
| 1. Datos y evidencia (Provenance Ledger) | Origen, version, licencia, permisos, fecha, hash, diccionario, uso de IA autorizado; cuatro clases de evidencia; etiqueta de sintetico; misma cohorte | Hecho. Subida de datasets con sha256 y perfil; libro de procedencia editable; `permiteLlmTerceros` nace en falso (NIH NOT-OD-25-081); clase por afirmacion; cohorte por afirmacion y por fuente; registro de evidencia (nivel de medicion, n, comparador, efecto, incertidumbre, campos sin resolver). Falta: deteccion de misma cohorte por autores, centro y periodo (hoy solo por nombre y NCT) | `POST /api/investigaciones/{id}/datasets`, `rosa/datos.py`, `LibroDeProcedencia`, `AfirmacionExtraida` |
| 2. Mapa y puerta de reproduccion | Tres analisis publicados reproducidos con tolerancias fijas; si no, el modulo no descubre | Hecho el mecanismo: registro de reproducciones con tolerancia congelada, ejecucion en el sandbox, comparacion, puerta bloqueada, abierta o eximida con motivo (nivel 3). Tres candidatos precargados (GSE1297, OASIS-1, SEA-AD). Falta: subir los datasets publicos y correrlos | `anadir_reproduccion`, `rosa/bucle/analisis.py::reproducir`, `PuertaYReproducciones` |
| 3. Generador (Hypothesis Cards) | Diana, celula, etapa, intervencion y direccion, prediccion falsable, riesgos; versionado | Hecho. Tarjeta al generar y al completar las antiguas; version y versiones con motivo; paso de la ruta terapeutica | `tarjeta`, `reformular_hipotesis`, `TarjetaDeHipotesis` |
| 4. Hypothesis Killer I | Lista de comprobacion; avanzar, reformular, suspender, descartar en contexto; el generador no aprueba lo suyo; auditar una muestra de descartes | Hecho. Once comprobaciones (cuatro deterministas, siete del juez Opus 5); decision derivada por regla; reformulacion automatica con limite de politica; auditoria de un tercio de descartes y reformulaciones con otro metodo (debate) y otra familia (Astra); descarte directo o propuesto segun el dial de autonomia. Falta: el panel de prueba con fallos plantados | `rosa/killer.py`, `MatarHipotesis`, `AuditarDescarte`, `DecisionesKiller` |
| 5 y 6. Plan de analisis y ejecucion in silico | Plan congelado antes de los resultados; Run Records con codigo, entorno, semilla, logs, estado real | Hecho. Plan con hash (pregunta, variables, prueba, H0 y H1, alfa, baseline, control barajado, multiplicidad, umbral, no evaluable); codigo con contrato de salida; sandbox Docker o Apple container sin red, o aislamiento blando solo con sinteticos; reparacion sin cambiar el plan; estados no ejecutado, error tecnico, tiempo agotado, completado, y aparte la interpretacion. Falta: Docker encendido en la maquina de demostracion; repeticiones con semillas distintas | `rosa/ejecucion.py`, `rosa/bucle/analisis.py`, `rosa/sandbox/` |
| 7. Auditor (Killer II) | Auditor independiente de cada analisis | Hecho. Comprobaciones deterministas (semilla, fuga, plan, baseline y control, n, multiplicidad) mas juez; valido, no valido, no evaluable computacionalmente; lo determinista critico manda | `AuditarAnalisis`, `comprobaciones_deterministas` |
| 8. Priorizacion y dossier | Bloqueos no compensables; diversidad; Wet-Lab Dossier | Hecho. Seis bloqueos, candidatas (hasta tres, sin repetir cluster), cero candidatas es valido; dossier en siete partes sin modelo. Falta: Bradley-Terry con intervalos en vez de Elo; valor esperado de la informacion como desempate | `rosa/priorizacion.py`, `rosa/dossier.py`, `Candidatas` |
| 9. Retorno y aprendizaje | Seis resultados; tres niveles de aprendizaje; promocion con conjunto reservado | Hecho. Clase principal con definiciones operativas mas dimensiones que coexisten (plan completo); accion por clase (derivada por correccion de contexto, suspension por toxicidad, repeticion tras fallo tecnico); registro de aprendizaje en tres niveles; evaluacion de criterios sobre las hipotesis con decision humana; promocion y reversion por persona | `EvaluarResultado`, `_evaluar_resultado`, `RegistroAprendizaje`, `_evaluar_cambio` |
| Transversal | Politicas que los agentes no editan; presupuesto en dinero y tiempo; documentos recuperados como datos | Hecho. `rosa/politicas.py` (solo por commit); dolares estimados por tokens y horas en la mision; delimitadores de dato en extractor, juez y cribado, y marca de sospecha de inyeccion | `rosa/politicas.py`, `config.coste_usd`, `killer.como_dato` |

## 2. El plan completo: etapas A a G

| Etapa | Que entrega | Que hay | Que falta | Evidencia de salida que pide |
|---|---|---|---|---|
| A. Contrato del sistema | Jerarquia del programa, formatos de registro, limites de inferencia, permisos, protocolo de evaluacion | Mision con areas; pregunta de campana con plantilla; registros de decision, ejecucion, plan, aprendizaje y metodos; politicas; dial de autonomia | Jerarquia explicita programa, areas, campanas, preguntas (hoy: investigacion, corrida con pregunta); protocolo de evaluacion escrito y con responsable | Ejemplos revisados con decisiones esperadas y responsables asignados |
| B. Nucleo de evidencia y causalidad | Comprobacion de fuentes, afirmaciones tipadas, metodos causales limitados, ejecucion numerica, seguimiento de dependencias | Verificador con contratos, registro de evidencia, sandbox con auditor, recalculo y informe de diferencias al cambiar el estado editorial de una fuente, registro de metodos | El motor causal (reglas tipadas con desconocidos explicitos, modelo causal estructural con supuestos declarados, componentes estadisticos jerarquicos); aristas del modelo de mundo como supuesto o inferencia con evidencia; comprobaciones automaticas de unidades y direccion invertida | Pruebas de extraccion, reproducciones, pruebas de inferencia y de correccion |
| C. Primer ciclo completo | Rosa elige una pregunta estrecha desde una meta amplia, actua, importa resultados, elige la siguiente accion | Hecho de punta a punta con literatura: mision y areas, pregunta, plan con valor de decision, Killer, conclusion GRADE, experimento prerregistrado con version, retorno con dimensiones, siguiente iteracion | Etiquetar la retroalimentacion simulada o de repeticion como tal en la interfaz | Un ciclo reconstruible con evidencia real |
| D. Programa adaptativo | Varias campanas, revision del alcance, evidencia compartida, seleccion de metodos, resultados pendientes, asignacion de presupuesto | Corridas multiples por investigacion; afirmaciones compartidas por id; registro de metodos con estado; presupuesto por mision | Reasignacion entre areas al cambiar resultados o costes; reapertura de areas pausadas con condicion; seleccion de metodo desde el registro con filtros | Comparaciones con presupuesto fijo y recuperacion ante evidencia inesperada |
| E. Operacion con laboratorio | Peticiones acordadas, protocolo real ejecutado, identidad de muestras, controles de calidad, revision de decisiones con consecuencia | Prerregistro con version, subida de datos, dimensiones del resultado, fallo tecnico que no toca la hipotesis | Importar el protocolo real y las desviaciones; identidad de experimento y muestra; enmiendas fechadas para trabajo adaptativo | Campanas prospectivas con predicciones registradas y reporte completo |
| F. Evaluacion cientifica | Comparaciones independientes contra procesos mas simples | Acuerdo del juez con decisiones humanas (Calidad); evaluacion de criterios sobre conjunto reservado | Las cuatro condiciones (cientifico solo, cientifico con LLM y recuperacion, Rosa con componentes apagados, Rosa completa) y los cinco niveles de prueba; panel del Killer con fallos plantados; casos que exigen abstenerse | Efectos, incertidumbre, costes, fallos y limites de generalizacion |
| G. Expansion | Mas metodos, contextos, clases de intervencion, aprendizaje controlado, operacion sostenida | Registro de metodos preparado para a�adir | Cada extension con sus propias pruebas | Cada extension pasa sus comprobaciones |

## 3. Lo que hay que hacer fuera del codigo, ya

- **Datos: solo publicos por ahora** (decision de la persona responsable del
  programa, 11 de septiembre). No se piden accesos controlados (ADNI, AD
  Knowledge Portal, dbGaP). La puerta de reproduccion se abre con GEO, SEA-AD
  procesado y OASIS. El libro de procedencia y la regla de no enviar filas al
  modelo (`permiteLlmTerceros` en falso) siguen activos para cuando entren
  datos controlados; la clausula de IA del NIH (NOT-OD-25-081) queda
  documentada en `INVESTIGACION-ROSA2018.md` para ese momento.
- **Docker Desktop** ya esta construido (`rosa-sandbox:1`) y probado con
  GSE1297 en la maquina de Emir: hay que tenerlo abierto en la demostracion.
- **GSE1297 esta cargado** con su libro de procedencia. Tres reproducciones
  de Blalock 2004 corrieron limpias en Docker y fallaron por criterio mal
  especificado (el resumen no describe como se construyo la lista publicada):
  leer los metodos completos y congelar el criterio exacto, o usar OASIS-1 y
  otros GEO (GSE5281, GSE48350, GSE44770) como analisis de la puerta.
- **Asignar responsables** (patrocinador, lider cientifico, metodos, datos,
  ingenieria, laboratorio, evaluacion) en la mision. Quien escribe una
  conclusion no es su unico evaluador: en Rosa el generador es Astra, el
  Killer y el auditor son Opus 5, y la auditoria de descartes vuelve a Astra
  con otro metodo.

## 4. Orden de trabajo hasta el 31 de octubre

1. Semana del 15 de septiembre: criterio exacto de Blalock 2004 desde los
   metodos completos, OASIS-1 y un segundo GEO subidos, tres reproducciones
   corridas con Docker, puerta abierta o con sus fallos anotados; panel de
   prueba del Killer (20 buenas, 20 con fallo plantado, 20 grises).
2. Semana del 22: deteccion de misma cohorte por autores, centro y periodo;
   comprobaciones automaticas de unidades y direccion; Bradley-Terry con
   intervalos en el ranking; jerarquia programa, areas, campanas en la
   interfaz.
3. Semana del 29: motor causal minimo (aristas del modelo de mundo tipadas
   como supuesto o inferencia, con contexto; consultas que devuelven cantidad,
   supuestos, evidencia, metodo, incertidumbre y limites, o "sin resolver").
4. Semana del 6 de octubre: importacion del protocolo real y desviaciones;
   enmiendas fechadas; identidad de muestras.
5. Semana del 13: las cuatro condiciones de comparacion sobre el panel, con
   casos de abstencion; manual de la investigadora.
6. Semanas del 20 y 27: ensayo de la demostracion, respaldo y recuperacion,
   cierre.

El plan completo dice que no se asigne una fecha al sistema completo a partir
de la fecha del demostrador. Este calendario cubre el MVP; las etapas D a G se
estiman cuando esten confirmados el acceso a datos, las personas, los metodos
soportados y los tiempos del laboratorio.

## 5. Lo que Rosa hace mejor que lo que piden los documentos

Sale de la investigacion del 11 de septiembre (`INVESTIGACION-ROSA2018.md`):

- La decision del Killer no la escribe el modelo: se deriva por regla desde
  comprobaciones separadas. Evita el fallo documentado en revisores LLM que
  senalan el problema y aprueban igual (BadScientist, 2025).
- Los descartes se auditan con otro metodo, no con otro prompt: nueve jueces
  de siete familias equivalen a poco mas de dos votos efectivos.
- La replicacion se cuenta por cohortes, no por articulos (Cochrane 7.2.2,
  Greenberg 2009 sobre el propio dominio del Alzheimer).
- Al juez no se le dice cuantas citas trae la hipotesis (sesgo de autoridad).
- Ningun dato individual controlado pasa por un modelo de terceros, por
  politica del libro de procedencia y no por buena voluntad.
- Los negativos solo son "interpretables" con controles validos y potencia;
  si falla el control positivo es fallo tecnico, no refutacion.
- Un resultado tardio actualiza la version que probo y avisa si la hipotesis
  cambio despues.
