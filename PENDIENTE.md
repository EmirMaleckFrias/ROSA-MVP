# Pendiente para la siguiente sesion

Actualizado el 11 de septiembre de 2026. El plan completo por etapas esta en
`PLAN-ROSA2018.md`; esto es la lista corta de lo inmediato.

## Hecho el 11 de septiembre (ROSA2018)

- Mision con areas de investigacion y pregunta de campana; politicas en
  codigo; tarjeta y versiones de hipotesis; Hypothesis Killer con decision
  por regla, reformulacion y auditoria de descartes; registro de decisiones;
  datasets con libro de procedencia y hash; puerta de reproduccion; analisis
  in silico con plan congelado, sandbox, interpretacion y auditor; bloqueos
  no compensables, candidatas y dossier; retorno con seis clases y
  dimensiones; registro de aprendizaje en tres niveles con evaluacion sobre
  conjunto reservado; registro de metodos; recalculo con informe de
  diferencias al cambiar el estado editorial de una fuente; presupuesto en
  dolares y horas; documentos recuperados como datos.
- Los puntos 1 a 5 de la lista anterior (prerregistro, plan por ganancia de
  informacion, version del arnes, cierre del loop con datos, analisis en
  entorno aislado) estan cubiertos.

## Datos: solo publicos por ahora

Decision de la persona responsable del programa (11 de septiembre): no se
piden accesos controlados (ADNI, AD Knowledge Portal, dbGaP). Rosa trabaja
con datos publicos: GEO, SEA-AD procesado (abierto) y OASIS (registro
gratuito). El libro de procedencia y la regla de no enviar filas al modelo
siguen activos para cuando entren datos controlados.

## Hecho tambien el 11 de septiembre (tarde)

- Concurrencia y carga de revision: sello de version en el Killer y en las
  decisiones humanas; segundos de revision por decision; responsables en la
  mision.
- Bradley-Terry con intervalos por bootstrap en el ranking; repeticiones con
  semillas en el sandbox; e-valores por hipotesis.
- Misma cohorte por autores, centro y periodo; comprobaciones automaticas de
  direccion de la evidencia y de unidades.
- Protocolo real, desviaciones, identidad de muestras y enmiendas fechadas.
- Gobierno de areas (elegir, pausar con condicion, reabrir, sin explorar,
  asignar a campana) y jerarquia programa, areas, campanas, preguntas.
- Motor causal minimo con aristas tipadas e identificacion por regla.
- Panel del Killer con fallos plantados y registro de evaluaciones.
- Puerta: dos reproducciones mas registradas con criterios congelados de los
  metodos publicados (GSE29378 Miller 2013: NRIP3 CA3 frente a CA1 en
  controles, 2,14 veces, tolerancia 20 %; GSE36980 Hokama 2014: media de
  diez marcadores neuronales en hipocampo, 64,87 %, tolerancia 15 %). Se
  ejecutan en el paso de analisis de la corrida en marcha o cuando esta se
  detiene.

## Inmediato

1. Ver el resultado de las dos reproducciones nuevas (Miller 2013, Hokama
   2014). Si alguna falla, leer el error en Objetivo y datos: el criterio
   esta congelado y no se cambia; lo que se corrige es el codigo o el
   preprocesado que Rosa eligio.
2. Leer el panel del Killer en Calidad. Lo que mide: si el juez detecta las
   cifras alteradas y las predicciones vagas cuando la comprobacion
   determinista no puede. Si la deteccion del juez es baja en un tipo de
   fallo, ese es el prompt que hay que tocar (`MatarHipotesis` en
   `rosa/modulos/firmas.py`) y volver a correr el panel.
3. SEA-AD procesado: agregar por donante (los ficheros pesan de 1 a 33 GB;
   Rosa admite 200 MB) antes de subirlo.
4. Alinear con la persona responsable del documento de concepto los nombres
   de los registros (ver `PLAN-ROSA2018.md`, introduccion) y los responsables
   de la mision.

## Codigo (lo que queda del plan, seccion 4)

- Las cuatro condiciones de comparacion y los cinco niveles de prueba del
  plan completo (seccion 7); replay historico con evidencia fechada.
- Valor esperado de la informacion como desempate entre candidatas.
- Motor causal: consultas al modelo de mundo que devuelvan cantidad,
  supuestos, evidencia, metodo, incertidumbre y limites, o "sin resolver"
  (hoy el grafo es por hipotesis y las relaciones tipadas se ven; falta la
  consulta).
- Panel del Killer con hipotesis buenas y grises con veredicto humano (hoy
  las grises se generan recortando pasajes; falta la version juzgada por una
  persona) y con mas hipotesis cuyo veredicto real sea avanzar.
- Al fusionar comprobaciones, hoy la determinista manda: si el juez detecta
  una cifra alterada pero el veredicto guardado de la afirmacion es
  "sostenida", la deteccion del juez se pierde. Decidir si fidelidad y citas
  deben bajar a "no comprobable" cuando juez y determinista discrepan.

## Tambien

- Clasificar las citas de cada hecho del modelo de mundo en apoya, menciona,
  contrasta (campo `citas`, hoy vacio).
- Rotar el token de Convex que aparecio en el chat.
- Las corridas anteriores a septiembre no tienen `arnes` ni `pregunta`.
