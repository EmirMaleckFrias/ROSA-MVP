# GEPA automático en Rosa

El servicio arranca con el backend. Todas sus llamadas, incluidas reflexión
y evaluación, utilizan los modelos de `rosa.gateway`. Se rechaza cualquier
modelo cuyo destino no sea el AI Gateway configurado. No hay un límite monetario;
sí hay un límite de evaluaciones por ciclo para que termine.

## Qué registra

- Las llamadas que pasan por `Ctx.llamar`: programa, entradas, salida o tipo
  de error, modelo, duración, corrida, iteración y versión.
- Los callbacks DSPy: prompts renderizados, respuestas y llamadas a herramientas.
- Los conectores: argumentos, resultados e invariantes. En los pasos del bucle
  se vinculan a la corrida; fuera de ese contexto pueden quedar sin atribución.
- Uso de tokens comunicado por DSPy cuando el historial permite identificar
  inequívocamente la llamada. No es una conciliación de facturación.
- Evaluaciones y feedback de GEPA, identificados por ciclo y caso.

Las trazas se escriben continuamente en `datos/_gepa/<nombre de la BD>/trazas.db`,
con permisos privados. Se redactan claves y correos reconocibles. Esto **no es
un sistema completo de desidentificación clínica**. Los datos brutos no se envían
al frontend ni al espejo Convex. No se reconstruyen retroactivamente prompts
que no fueron capturados. Las consultas de fuentes fuera de los conectores
pueden aportar sus registros de `corrida.busqueda`, no una captura HTTP universal.

## Cuándo aprende y qué puede cambiar

Comprueba elegibilidad cada 30 segundos. Hay al menos seis horas entre ciclos
terminados durante una sesión; al reiniciar se conserva el último inicio como
referencia. Optimiza un programa por ciclo, priorizando los menos recientes:
consultas, relevancia, relevancia de amplitud, extracción, resumen y lenguaje llano.
No modifica el código, las herramientas, el Killer ni el verificador.

Necesita al menos 30 entradas nuevas, con al menos cinco en cada partición.
Solo usa corridas cerradas con el contrato actual del programa. Excluye las
investigaciones con datasets de personas o sin permiso de LLM terceros y vuelve
a comprobar el permiso al seleccionar los casos. Revisa las últimas 2000 trazas
de cada programa; conserva como máximo 120 casos por partición.

La separación es estable por corrida: entrenamiento, validación y examen final.
Las entradas idénticas compartidas entre corridas se excluyen. Esto reduce fugas,
pero no garantiza independencia científica entre artículos o cohortes relacionados.
Todos los casos seleccionados se consumen una sola vez, incluso si falla el ciclo.
GEPA ve entrenamiento y validación, nunca el examen final. El entrenamiento recibe
feedback acotado de consultas, revisiones, errores y trazas de su propia corrida;
las observaciones no se tratan como respuestas correctas.

El límite de GEPA es el mayor entre 120 evaluaciones y ocho veces el tamaño de
validación, más el examen pareado y las llamadas de reflexión. No representa
un límite de tokens ni de dinero. Las llamadas de optimización no se cargan al
presupuesto de la corrida de investigación.

## Promoción y límites de la medida

Un juez fijo evalúa fidelidad, cobertura y cumplimiento frente al contrato original.
La métrica es el mínimo de esas dimensiones; un fallo crítico da cero.
Se exige una mejora media de al menos 0,05, ningún caso final que empeore y ningún
caso candidato con cero. Si falla el evaluador del examen, no se promueve.

Estas puntuaciones son estimaciones de un modelo, **no validación científica ni
garantía de mejora en futuras investigaciones**. No sustituyen casos revisados por
personas. Las consultas se juzgan por su formulación, no por una nueva búsqueda
real durante el examen. La evidencia de calidad real debe revisarse periódicamente.

Cada versión se guarda en JSON, sin pickle, con hash de integridad y sin un LM
asociado. Se conservan las anteriores. Cada corrida fija sus versiones en la
primera llamada; las corridas existentes al instalar el servicio conservan la base.
Ninguna promoción altera los prompts a mitad de una corrida.

## Revisión y control

En Calidad aparecen el estado, recuentos, métricas y motivos de cada ciclo.
Administración puede pausar, reanudar o volver a los programas base para nuevas
corridas. Restablecer pausa la promoción y no borra las versiones guardadas.
La captura sigue activa. Una petición ya enviada al Gateway puede terminar tras
pausar, pero no se permite activar su candidato. Los controles están autenticados
y usan la misma protección contra escrituras externas que el resto de la API.

El servicio se aloja en el único proceso escritor de Rosa, no es un planificador
distribuido. Un reinicio interrumpe el ciclo en curso; queda auditado y no se reusa
su examen. La retención de trazas es local y por ahora no tiene borrado automático:
conviene vigilar el espacio de disco. Los ficheros de GEPA pueden contener contexto
de investigación y deben tratarse como privados, incluso tras la redacción.

## Pruebas

`rosa/tests/test_gepa_continuo.py` prueba separación, promoción, no regresión,
fallos del juez, pausa, Gateway obligatorio, integridad, privacidad y versiones
congeladas con modelos simulados. Las pruebas no demuestran calidad científica;
esta requiere observar los primeros ciclos reales y revisar sus resultados.

## Arreglos del 16 de septiembre de 2026 (revisión posterior al commit)

Tras revisar el servicio contra el código y el estado real se cambiaron estas
cosas (rosa/tests/test_gepa_arreglos.py las fija):

- Las trazas se escriben desde un hilo propio: el bucle solo encola. La redacción
  de secretos ya no tiene retroceso cuadrático (una cadena de 32 000 caracteres
  sin espacios tardaba 3 segundos en el hilo del bucle) y los textos se recortan
  a 20 000 caracteres. Retención: 30 días para prompts y herramientas, 180 para
  los casos de programa.
- La elegibilidad se comprueba cada 10 minutos (no cada 30 segundos) y primero
  cuenta las trazas nuevas por programa antes de cargar nada. Nunca se optimiza
  con una corrida en marcha. El resumen público solo se escribe cuando cambia el
  estado o cada media hora, no en cada tic.
- La regla de permisos solo excluye investigaciones con datasets de personas:
  los programas que se optimizan leen literatura, nunca filas de un dataset.
  Antes, un dataset real sin la marca de LLM de terceros excluía la
  investigación entera (la de GFAP y NfL quedaba fuera para siempre).
- Los casos se consumen al terminar el ciclo, no al empezar; un fallo transitorio
  (gateway, juez, pausa, apagado) no los quema. El examen visto sí se consume.
- La separación entrenamiento, validación y examen es por investigación, no por
  corrida: dos corridas de la misma investigación comparten hipótesis y artículos.
- Puerta de promoción: al menos 8 casos de examen (tope 24), dos lecturas del juez
  por caso, mejora media de 0,05, ningún caso a cero y ningún caso peor por más
  de 0,15 (una lectura ruidosa una décima peor no tira la promoción).
- Comprobaciones por regla antes del juez: salida vacía, consulta sin base, cita
  que no nombra la fuente dada, texto redactado: cero sin gastar una llamada.
- El rol del modelo se lee de las trazas reales del programa (el lenguaje llano
  corre con el cerebro, no con el modelo de volumen).
- El gasto de cada ciclo (llamadas, tokens, dólares) queda en la tabla de Calidad
  y en el resumen del servicio.
- Una promoción queda en el registro de aprendizaje como cambio de nivel 2 ya
  promovido (con su evaluación del examen) y se revierte desde Ajustes, que
  devuelve la versión anterior a las corridas nuevas.
- Las versiones se fijan al crear la corrida y el arnés público las nombra
  (`arnes.optimizados`), así que el prerregistro y el RO-Crate dicen con qué
  programa corrió.
- El apagado espera 15 segundos al ciclo en curso y sigue; el ciclo queda
  auditado como interrumpido.
- Segunda pasada (misma tarde), tras la verificación adversaria de la revisión:
  el modelo del gateway va envuelto en `LMConParada` y se niega a llamar en
  cuanto hay pausa, apagado o el juez falló tres veces seguidas (GEPA traga las
  excepciones de la métrica, así que esta es la única forma de dejar de gastar);
  un juez caído aborta el ciclo sin consumir casos en vez de entrenar con ceros;
  una versión fijada cuyo fichero falta o no supera la integridad no deja la
  corrida muerta: vuelve al programa base, lo anota y deja una incidencia; el
  reparto entrenamiento, validación y examen es por rango del hash de cada
  investigación (con tres o más siempre hay examen y validación; antes un cubo
  vacío dejaba a GEPA sin examen para siempre); el feedback de experiencia se
  acota a 4 000 caracteres; `firma()` tolera módulos sin signature; y Rosa
  arranca aunque el servicio no pueda construirse.
