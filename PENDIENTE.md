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
- Puerta: dos reproducciones mas, superadas, con criterios congelados de los
  metodos publicados (GSE29378 Miller 2013: NRIP3 CA3 frente a CA1 en
  controles, 2,14 veces, tolerancia 20 %; GSE36980 Hokama 2014: media de
  diez marcadores neuronales en hipocampo, 64,87 %, tolerancia 15 %).
- Investigacion de las herramientas de Claude Science
  (`INVESTIGACION-HERRAMIENTAS-CLAUDE-SCIENCE.md`) y su aplicacion: 80
  conectores con registro de consultas, novedad por genetica, farmacos y
  datos publicos, contexto de la diana, preguntar a las bases (ReAct),
  permisos por conector, memoria del proyecto, revisor de registro,
  artefactos con cinco pestanas de procedencia, siete skills, imagen de
  celula unica. Ver README, seccion "Lo que Rosa tomo de Claude Science".

## Inmediato

1. Puerta de reproduccion: 3 de 3 superadas con datos publicos (Blalock
   2004 en GSE1297, 418 frente a 431; Miller 2013 en GSE29378, 2,1391
   frente a 2,14; Hokama 2014 en GSE36980, 65,11 frente a 64,87). Las dos
   ultimas fallaron a la primera porque el escritor de codigo declaro "no
   evaluable" por una duda del texto del metodo; se corrigio el texto y las
   firmas (NO_EVALUABLE solo por condiciones de los datos). Los registros
   fallidos quedan a la vista.
2. Panel del Killer (11 de septiembre, 35 casos, 8 USD): deteccion 16 %,
   abstencion 0 %, sobre-matanza en gris 80 %. Las cinco hipotesis originales
   salieron "descartar" por `supuestos`: el juez trataba un supuesto "sin
   evidencia" como invalidante. Corregido: `supuestos` es ahora por regla
   (solo un supuesto contradicho tumba), el supuesto invalidante del juez
   solo cuenta si hay contradiccion real, y cuando juez y regla discrepan en
   fidelidad, citas o supuestos la hipotesis se suspende en vez de morir.
   Lo que el juez si detecto: supuesto contradicho (4 de 5), causalidad sin
   temporalidad (5 de 5), prediccion vaga (2 de 3 sin error). Lo que no
   detecto: cifra alterada frente al pasaje (0 de 5); se le a�adi� la
   instruccion explicita de comparar texto y pasaje. Tres casos fallaron por
   JSON truncado; el juez pasa a 8000 tokens de salida. Queda un segundo
   panel reducido para medir el efecto; repetir el panel completo tras cada
   cambio del prompt del Killer.
3. SEA-AD procesado: agregar por donante (los ficheros pesan de 1 a 33 GB;
   Rosa admite 200 MB) antes de subirlo.
4. Alinear con la persona responsable del documento de concepto los nombres
   de los registros (ver `PLAN-ROSA2018.md`, introduccion) y los responsables
   de la mision.

## De Claude Science, lo que queda

- Probar la imagen `rosa-sandbox-celula:1` (construida, 1,28 GB) con un h5ad real
  (SEA-AD por CELLxGENE) y una reproduccion de celula unica en la puerta.
- Lector de ficheros del eQTL Catalogue (la API REST se retiro) y de ARCHS4
  (H5 de 30 GB), si se decide descargarlos al servidor.
- Un segundo panel del Killer completo (35 casos) tras las correcciones,
  con hipotesis cuyo veredicto real sea avanzar, y un panel del revisor de
  registro con resumenes con errores plantados.
- El bucle de herramientas dentro de los pasos de novedad y factibilidad
  (hoy la novedad usa una secuencia fija de conectores; el ReAct solo
  responde a preguntas de personas).
- Kernels persistentes, R, notebooks y trabajos remotos: no se copian;
  revisar si el laboratorio los pide.

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
- Rotar en el panel de Convex la clave de despliegue que paso por el chat el
  14 de septiembre (y la anterior), y poner la nueva en `.env`. Despues,
  decidir si la interfaz lee del espejo cuando el servidor no responde.
- Las corridas anteriores a septiembre no tienen `arnes` ni `pregunta`.
