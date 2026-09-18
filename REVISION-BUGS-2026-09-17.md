# Revisión de bugs de ROSA2018: síntesis de las once zonas

Fecha: 17 de septiembre de 2026. Repositorio: /Users/emirmalek/traspaso-alzheimer-agente (HEAD a2bf72e al cerrar la revisión). Estado analizado: copia estado_ahora.json (7 MB públicos, 15 a 18 MB con claves privadas), API local en solo lectura, copias de rosa.db y de datos/_gepa/rosa.db/trazas.db en el scratchpad, log del servidor. Ninguna zona tocó el repositorio ni el servidor vivo.

Cada zona produjo hallazgos y cada hallazgo grande pasó por dos lentes: "reproducir" (intentó refutarlo en el código y con datos) e "impacto" (juzgó la gravedad real y el arreglo). Los hallazgos que aparecen en varias zonas se han fundido en uno, conservando la evidencia de todas. Los identificadores originales (literatura-01, killer-03, ...) se citan entre corchetes para volver a las fichas de las zonas cuando haga falta.

Recuento tras fundir: 96 hallazgos distintos; 2 críticos, 26 altos, 40 medios, 28 bajos; 0 refutados por la lente "reproducir" (varios quedaron en "parcial" porque una parte de su premisa ya no se cumple; están en el apéndice). 26 de los bajos y medios no pasaron por verificación (las lentes solo revisaron críticos, altos y medios de cada zona) y están marcados "sin verificar".

## (a) Lo que hay que saber en un minuto

1. ROSA2018 tira dos de cada tres afirmaciones que extrae por una expresión regular: el verificador no reconoce el localizador "texto web, parte N" que crea la lectura por Exa (rosa/verificador.py:31 frente a rosa/bucle/pasos.py:470). Son 875 afirmaciones bloqueadas en la investigación viva, el 100 % de las que vienen de fuentes leídas por Exa, y la nota del TRASPASO que lo atribuye a "fuentes sin texto completo" está equivocada: esas fuentes sí tienen texto y el arreglo anotado allí no las salvaría. Esto explica en buena parte que ninguna hipótesis suba de certeza. Se arregla en horas.

2. Hay dos cosas que engañan a la persona con un dato falso hoy. La primera: 16 de 28 hipótesis llevan el chip verde "Sin precedente" porque la consulta a OpenAlex se manda en castellano y con las palabras cortadas en la tilde ("informaci", "reducci"), devuelve 0 obras, y el código traduce "0 obras" como "nadie lo publicó antes" (rosa/bucle/pasos.py:2421-2425, rosa/bucle/contexto.py:410); el Killer da esa comprobación crítica por superada. La segunda: el 15 de septiembre dos procesos de ROSA2018 escribieron a la vez sobre rosa.db al reiniciar con una revisión del Killer en vuelo; una decisión del Killer se perdió y fue sustituida por "El juez no respondió", la cadena de auditoría lleva rota desde la fila 6450 y nada impide que se repita en cada reinicio (rosa/estado/almacen.py:88 y :135).

3. Las hipótesis que Emir deja en la cola no se movían porque el Killer no volvía a juzgarlas. El arreglo (62b327b) ya está desplegado y funcionó hoy con dos hipótesis, pero quedan tres hipótesis con evidencia acumulada bajo el código viejo que nadie va a rejuzgar, un fallo del juez sigue convirtiéndose en suspensión permanente, y el torneo y la evaluación de supuestos juzgan con recortes que no contienen lo acumulado.

4. El Killer descarta mal: 4 de 5 descartes de la investigación viva salen de un "supuesto" que redactó el revisor inicial y que Sonnet dio por "contradicho" (en un caso porque ninguna afirmación lo mencionaba); la auditoría independiente discrepó en todos los casos auditados y no tuvo consecuencia. Y reformular una hipótesis por "ya publicado" es imposible por construcción porque la novedad no se recalcula: dos reformulaciones pagadas para una conclusión fijada de antemano.

5. El coste que ve Emir está al doble: la tabla de precios de rosa/config.py:69 infla Opus tres veces y Sonnet una vez y media, mientras el gateway devuelve el coste real en cada respuesta y ROSA2018 lo ignora (corrida 8: 26,79 USD mostrados, 12,71 facturados). El presupuesto de 60 USD de la misión funciona hoy como uno de 30. Además, cada cierre de iteración rehace 8 conclusiones con Opus y rejuega el torneo aunque solo una hipótesis tenga evidencia nueva: entre el 30 y el 47 % del coste estimado de la iteración.

6. El almacén está al límite de su diseño: cada mutación serializa y reescribe los 17 MB del estado (unas 800 veces por iteración, con el bucle de eventos parado unos 100 ms cada vez) y cada cambio empuja 10 MB por SSE a cada pestaña (medidos hasta 443 MB por minuto en fase activa). El contador de segundos y la espera humana disparan escrituras cada 2 a 10 s sin que pase nada científico.

7. La suite pasa (859 tests de backend, 446 de frontend) pero ninguna prueba recorre el bucle real: los nueve ejecutores de pasos y correr_corrida tienen cero líneas ejecutadas por los tests. Todos los fallos anotados en el TRASPASO se descubrieron en corridas de 20 a 30 dólares. No hay CI, ni hooks, ni logging (66 print, 0 logging), y un commit roto llegó a origin/main el 14 de septiembre sin que nada avisara.

8. Reglas del proyecto que hoy se incumplen con datos: "una fuente que no responde es no pude comprobar" (novedad con 0 obras, juez caído convertido en suspensión, auditor mudo contado como acuerdo, evaluación GEPA con acuerdo 0.0); "la certeza solo baja" (un CSV de laboratorio llamado sintético cuenta como evidencia directa y sube el techo a moderada); "misma regla en los dos lados" (cohortes distintas, enmendarLectura, recomprobarRetracciones, ampliarPresupuesto); "tildes en todo texto" ("Se cumplio" 10 veces en el estado, "pistas término" por "terminó" introducido por el propio script de tildes).

## (b) Tabla de hallazgos confirmados y parciales

Severidad: la ajustada por los verificadores; cuando las dos lentes discrepan se indica la elección en la ficha. Esfuerzo: estimación de las lentes. Confianza: del verificador, 0 a 1.

### Críticos

| id | título | severidad | tipo | zona | esfuerzo | confianza |
|---|---|---|---|---|---|---|
| S-01 | Dos procesos de ROSA2018 escriben en rosa.db sin cerrojo ni comprobación de versión: decisión del Killer perdida y sustituida por una falsa, cadena de auditoría rota desde la fila 6450 [estado-01, servidor-01, estado-09] | crítica | fallo | estado, servidor | un día | 0,95 |
| S-02 | El paso de novedad declara "sin precedente" (chip verde, Killer "pasa") cuando OpenAlex devuelve 0 obras por una consulta truncada en la tilde y en castellano, o cuando el modelo de relevancia falla en silencio: 16 de 28 hipótesis [tests-01, tests-08 en parte] | crítica | fallo | tests, bucle | horas | 0,95 |

### Altos

| id | título | severidad | tipo | zona | esfuerzo | confianza |
|---|---|---|---|---|---|---|
| S-03 | El verificador no reconoce el localizador "texto web, parte N": 875 de 875 afirmaciones de fuentes leídas por Exa bloqueadas (58 % de toda la evidencia extraída); la causa anotada en TRASPASO es otra [literatura-01, extraccion-01, modelos-01, rigor-01] | alta | fallo | verificación | horas | 0,98 |
| S-04 | La referencia corta no es única ("Sin autor" x3 por corrida, dos artículos distintos "Bhagunde et al., 2026"): la cita resuelve a la primera fuente homónima y bloquea o juzga contra el texto equivocado [literatura-02, extraccion-02] | alta | fallo | verificación | horas | 0,9 |
| S-05 | La comprobación literal contra el PDF tira 284 de 540 afirmaciones de página (53 %) por números de línea de preprints, guiones de fin de línea y comillas, con la página correcta en todos los casos [literatura-10, extraccion-03] | alta | fallo | verificación | medio día | 0,85 |
| S-06 | Las fuentes relevantes no se recuerdan entre corridas: el mismo DOI se recriba, redescarga, reextrae y rejuzga (517 de 1.532 afirmaciones); una fuente ya extraída con páginas nuevas nunca se vuelve a extraer; cohortes contadas dos veces [literatura-03, modelos-07, extraccion-09, literatura-09] | alta | riesgo, ineficiencia | literatura, evidencia | varios días (cortes quirúrgicos en horas) | 0,9 |
| S-07 | Las fuentes primarias de los ensayos nombrados (CLARITY AD, TRAILBLAZER-ALZ 2, evoke) llegaron 7 veces y se excluyeron siempre: la caché de exclusiones reutiliza cortes del reranker y juicios hechos contra preguntas heredadas; la red de seguridad por nombre está apagada por una subcadena [literatura-06, literatura-05] | alta | fallo | literatura | un día | 0,85 |
| S-08 | El bucle vuelve sobre la cola solo desde 62b327b (desplegado a las 12:07): quedan tres hipótesis con evidencia acumulada bajo el código viejo sin rejuzgar, la revisión se pierde si falla el juez, y torneo y supuestos juzgan con recortes sin lo acumulado [killer-01, corrida-01, modelos-04, evidencia-03] | alta | fallo | killer, corrida | un día | 0,9 |
| S-09 | Un fallo del juez (parse, tiempo agotado) se registra como decisión "suspender" permanente sin reintento: hip-mu2uqqzu-5871 lleva dos días y ocho corridas así [killer-02] | alta | fallo | killer | horas | 0,9 |
| S-10 | El Killer descarta por "supuesto contradicho" sobre supuestos que redacta el revisor inicial y que Sonnet da por contradichos (una vez por ausencia); 4 de 5 descartes de la investigación; la auditoría discrepa en los auditados y el juez Opus que lo negó fue ignorado por fusionar [killer-03] | alta | fallo | killer | medio día | 0,9 |
| S-11 | La novedad no se recalcula al reformular: la versión nueva hereda el precedente de la vieja y las dos reformulaciones de la política están condenadas [killer-04] | alta | fallo | killer | horas | 0,95 |
| S-12 | La auditoría por debate discrepa del Killer en 5 de 9 casos y no tiene consecuencia; audita el 69 % en vez del 34 %; y si el auditor no responde se guarda "de acuerdo" [killer-06, killer-10] | alta | deuda, fallo | killer | medio día | 0,85 |
| S-13 | El cierre rehace ocho conclusiones con Opus en serie y el torneo rejuega los mismos pares cada corrida aunque la evidencia no cambie: 4,4 USD y 9 minutos por cierre, dirección que oscila sin evidencia [evidencia-04, corrida-04, modelos-05, killer-05] | alta | ineficiencia | corrida, killer | un día | 0,9 |
| S-14 | Si el presupuesto se agota dentro del cierre la excepción tumba la tarea y el tick la relanza cada 2 s: corrida "en marcha" para siempre, pistas basura y escrituras de 17 MB en bucle [corrida-03, corrida-08] | alta | fallo | corrida | horas | 0,85 |
| S-15 | Cuando corta el tope por iteración (447) el aviso culpa al tope global (1500) y ampliar el presupuesto no lo levanta; en 3 de las últimas 4 corridas habría saltado si S-03 estuviera arreglado [corrida-05] | alta | fallo | corrida | horas | 0,85 |
| S-16 | hipotesisNuevas cuenta por número de iteración sin mirar la corrida (5 nuevas donde nacieron 0) y el resumen técnico y el llano dicen "quedan en cola dos hipótesis" cuando hay nueve, con motivos del Killer inventados [corrida-02, rigor-02] | alta | fallo | corrida, rigor | horas | 0,95 |
| S-17 | Cada mutación serializa y reescribe el estado entero (17 MB, ~100 ms, 800 veces por iteración) y cada cambio empuja 10 MB por SSE a cada pestaña (hasta 443 MB por minuto); el reloj y la espera humana disparan escrituras cada 2 a 10 s [estado-02, estado-03, estado-04, estado-05, servidor-02, frontend-02, frontend-07] | alta | ineficiencia | estado, servidor, frontend | varios días (primer corte en horas) | 0,95 |
| S-18 | Un CSV de laboratorio llamado sintético cuenta como observación original: el techo GRADE de hip-mtvulxbg-140 sale "moderada" por "análisis sobre datos reales" [evidencia-02, rigor-07] | alta | fallo | evidencia | horas | 0,9 |
| S-19 | ROSA2018 muestra el doble del coste real: tabla de precios equivocada (Opus x3, Sonnet x1,5, GPT-6 Astra a la mitad) e ignora el campo cost del gateway; el presupuesto de la misión corta a la mitad [modelos-02] | alta | fallo | modelos | horas | 0,9 |
| S-20 | La caché de DSPy está activa en todos los modelos: las trayectorias de replicación a temperatura 1,0 y las dos lecturas del examen de GEPA son la misma respuesta cacheada; los aciertos cuentan como llamadas gastadas [modelos-03, corrida-12] | alta | fallo | modelos | horas | 0,9 |
| S-21 | ROSA_TOKEN es inerte (la guardia de sesión va antes y tiene las mismas condiciones), la puerta entrar_sin_verificar abre sesión a cualquiera del dominio, el primer correo es administrador y no hay límite de tasa [servidor-03] | alta | riesgo | servidor | horas | 0,9 |
| S-22 | Sin roles: cualquier sesión inicia corridas, amplía presupuesto, sube 200 MB o sella; y el `quien` de cada decisión lo dicta el navegador (constante "la persona responsable") [servidor-08] | alta | deuda | servidor | horas (autoría) a días (roles) | 0,85 |
| S-23 | Una decisión humana diferida 6 s se deshace en pantalla con el siguiente SSE (mediana 1,2 s entre empujes en corrida), se pierde si se cierra la pestaña y puede registrarse dos veces [frontend-01] | alta | fallo | frontend | medio día | 0,9 |
| S-24 | La evaluación de criterios GEPA escribe "acuerdo 0.0 antes, 0.0 después" y revierte criterios cuando el juez no responde [tests-02] | alta | fallo | corrida | horas | 0,9 |
| S-25 | Ningún test recorre el bucle: los nueve ejecutores paso_*, verificar_afirmaciones, correr_corrida y _ejecutar_paso tienen cero líneas ejecutadas por la suite [tests-03] | alta | deuda | tests | medio día base, luego horas por caso | 0,95 |
| S-26 | Solo se extraen los 6 primeros fragmentos de cada fuente por posición: las páginas 7 a 14 (resultados, tablas) nunca se leen; 104 de 112 datos en hipótesis sin n, comparador o efecto [extraccion-05] | alta | fallo | extracción | medio día | 0,9 |
| S-27 | La réplica de una hipótesis nacida en otra corrida falla siempre (los fragmentos viven en la corrida actual) y "no pude comprobar" cuenta como "contradice": el botón daría un falso negativo hoy [extraccion-10] | alta | riesgo | extracción | horas | 0,8 |
| S-28 | Los artefactos guardan todas sus versiones con contenido completo (modelo de mundo 13 versiones, 1 MB): 15 % del estado, y Convex ya recorta la versión vigente al 15 % [estado-10] | alta | deuda | estado | un día | 0,85 |

### Medios

| id | título | severidad | tipo | zona | esfuerzo | confianza |
|---|---|---|---|---|---|---|
| M-01 | La regla de riesgo de sesgo convierte "sin información" en "riesgo alto": 2 de 5 fuentes evaluadas son alto solo por falta de texto; el Killer suspende por ello [extraccion-04] | media | fallo | extracción | medio día | 0,85 |
| M-02 | El juez recibe el mismo fragmento una vez por afirmación (4 por fragmento) con ChainOfThought; agrupar bajaría de 111 a 29 llamadas en la corrida 8 [extraccion-06, modelos-09] | media | ineficiencia | verificación | un día | 0,8 |
| M-03 | El catálogo de cohortes no conoce los ensayos: TRAILBLAZER-ALZ y ALZ 2 se funden, ALZ 2 y ALZ2 se separan, el NCT se corta a 60 caracteres [extraccion-07, evidencia-09] | media | fallo | evidencia | un día | 0,85 |
| M-04 | Tres reglas de "cohortes distintas": la franja del ranking dice 7 donde el techo cuenta 6, en 5 de 28 hipótesis; el Killer y el dossier usan la cuenta sin filtrar [evidencia-05, frontend-03] | media | fallo | evidencia, frontend | horas | 0,95 |
| M-05 | La métrica de fidelidad guarda 0 cuando el juez no juzgó nada; sinVerificar se pinta como porcentaje siendo recuento [extraccion-08] | media | fallo | extracción | horas | 0,85 |
| M-06 | La descripción de `certeza` que lee el juez contradice la escala de certeza.py ("muy baja si no hay evidencia directa"); el juez no ve el techo; la escalera pide un peldaño genérico; 7 de 9 conclusiones dicen "no encontramos evidencia directa" con 6 a 14 afirmaciones sostenidas [evidencia-01] | media | fallo | evidencia | un día | 0,9 |
| M-07 | Dirección "mixta" y frase "La evidencia es contradictoria" con cero afirmaciones en contra: la dirección la fija el juez desde supuestos y ausencias [evidencia-06] | media | fallo | evidencia | horas | 0,85 |
| M-08 | La deduplicación de hechos falla con paráfrasis (exige 2 entidades canónicas, que el 64 % de los hechos no tiene) y copiar_hechos hereda duplicados; 333 de 381 hechos sin enlace a afirmación [evidencia-07, rigor-11] | media | fallo | evidencia | horas | 0,9 |
| M-09 | Las candidatas de evidencia saturan siempre el tope (72 = 9 x 8) porque el coseno 0,30 lo pasa el 99 % de los pares; 9 llamadas en serie por cierre para enlazar 3 [evidencia-08] | media | ineficiencia | evidencia | horas | 0,8 |
| M-10 | Frases de introducción (revisión de literatura ajena) pesan como apoyo pleno y aportan cohorte: 47 % del peso a favor en 11 hipótesis, 100 % en una; las interpretaciones tampoco se filtran [rigor-04, extraccion-11] | media | riesgo | certeza | medio día | 0,8 |
| M-11 | El revisor de registro juzga con un registro recortado a 9.000 caracteres (FUENTES y CONSULTAS no llegan), con reglas de recuento rotas (`_iteracion` que nadie escribe, verificadas no admitidas, negación no reconocida) y sin la certeza que el llano sí menciona; 95 hallazgos abiertos bloquean 14 hipótesis [rigor-03, rigor-05, rigor-06] | media | fallo | rigor | un día | 0,9 |
| M-12 | 11 hipótesis proponen "solicitar acceso a ADNI" sin bloqueo; dos listas de datos controlados distintas, ninguna con BIOCARD; el detector marca como uso los descargos [rigor-08] | media | riesgo | rigor | horas | 0,8 |
| M-13 | pasaje_en_texto tolera 1 a 5 palabras inventadas al final (o al principio) en cualquier longitud: la "cita literal" que ve la médica puede no serlo [rigor-09] | media | fallo | verificación | horas | 0,95 |
| M-14 | Conclusiones y techos GRADE obsoletos: 19 de 28 sin techo, una con certeza por encima del techo actual; las investigaciones sin corrida nunca se recalculan [rigor-10] | media | deuda | certeza | un día | 0,85 |
| M-15 | La consulta de "novedad reciente del campo" se lanzó una sola vez en toda la investigación porque su cadena no cambia con la fecha y cae en el filtro de consultas hechas [literatura-04] | media | fallo | literatura | horas | 0,95 |
| M-16 | El registro PRISMA declara duplicates 0 siempre, cuenta artículos varias veces y recorta los excluidos a 600 (y a 300 y 120 al exportar) [literatura-07] | media | fallo | literatura | horas | 0,95 |
| M-17 | Cribado repetido dentro del mismo paso (consultas en paralelo) y guarda de títulos cortos muerta por "título:" con tilde frente a "titulo:" sin ella [literatura-08] | media | ineficiencia | literatura | un día | 0,9 |
| M-18 | El generador de consultas solo ve las últimas 40 de 149 y la firma le dice que ve todas; las lecciones no acumulan por patrón [literatura-11] | media | riesgo | literatura | un día | 0,8 |
| M-19 | La marca de revisión sobrevive a una cadena de reformulaciones (doble juicio, hallazgos y "Decide tú" duplicados); cada hipótesis nueva pasa dos veces por el Killer por construcción; un "avanzar" posterior no saca a la hipótesis de en_revision [killer-07, killer-09, killer-08] | media | fallo | killer | horas | 0,9 |
| M-20 | La iteración se numera por corrida y el ciclo de vida la usa como global: la paciencia del vivero no puede cumplirse entre corridas y la gráfica de Elo retrocede en el eje [killer-11] | media | riesgo | killer, frontend | horas | 0,9 |
| M-21 | La comprobación de dirección trata las afirmaciones enlazadas "en contra" como apoyo de signo opuesto y pide reformular: se disparará en cuanto la amplitud traiga contra-evidencia [killer-13] | media | riesgo | killer | horas | 0,85 |
| M-22 | Los tres medidores de calidad del Killer están vacíos o caducos (dorado 0, reservado 0, panel del 11/09); caida_de_acuerdo no tiene llamador [killer-14] | media | deuda | killer | un día | 0,85 |
| M-23 | Pasos sin trabajo marcados "hecho" ("No hay fuentes nuevas", "Nada pendiente de verificar"); el análisis sin datasets desaparece del plan en silencio [corrida-09] | media | riesgo | corrida | horas | 0,8 |
| M-24 | Espejo Convex: reenvía la corrida (120 a 460 kB) cada ~9 s porque el reloj cambia su hash, escanea todo bajo el cerrojo, sin reintento tras fallo, y omite 14 claves del estado [estado-06, servidor-07] | media | ineficiencia | estado | horas | 0,85 |
| M-25 | GEPA continuo no puede cerrar un ciclo con una sola investigación (exige tres) y su retención de trazas no corre mientras haya corrida viva; trazas.db crece 40 MB al día y guarda cada prompt dos veces [estado-07, modelos-12] | media | riesgo | gepa | un día | 0,85 |
| M-26 | Apagado que puede no terminar: los hilos de to_thread (sandbox 210 s, ciclo GEPA) sobreviven al cierre y escriben en un almacén cerrado; el proceso vivo está huérfano (PPID 1) [estado-08] | media | riesgo | servidor | un día | 0,7 |
| M-27 | Respuestas del juez con finish_reason content-filter pasan como ok=1 sin traza (8 hoy); la causa del reintento en el torneo es que Opus escribe `Comparacion(...)` como constructor Python y el adaptador falla; una respuesta cortada por `length` sí puede decidir un partido [servidor-04, modelos-06] | media | riesgo | modelos | medio día | 0,8 |
| M-28 | Observabilidad casi nula: 0 logging, 66 print, log en el scratchpad de la sesión y truncado en cada reinicio; /api/salud exige sesión y no mira el bucle [servidor-05, tests-07] | media | deuda | servidor | un día | 0,9 |
| M-29 | Los límites de cuerpo se aplican tras leer todo (300 MB aceptados antes del 413); /preguntar sin tope, con autoría del cliente y contador diario en memoria [servidor-06] | media | riesgo | servidor | horas | 0,9 |
| M-30 | Un fallo de red del gateway se anota como paso "fallido: LMTransportError" y la iteración sigue cerrando sobre nada; el tope único de 600 s por llamada, con 7 conexiones de reintento por debajo, se cuenta como trabajo [servidor-09, modelos-08] | media | riesgo | modelos, corrida | un día | 0,8 |
| M-31 | El cribado en amplitud repite 11.000 caracteres de hipótesis en cada artículo (6.450 tokens frente a 3.000 en foco; 27 % de los tokens de entrada de la corrida 8) [modelos-10] | media | ineficiencia | modelos | horas | 0,8 |
| M-32 | enmendarLectura tiene regla del hash contraria en los dos lados y la etiqueta "hash congelado" enseña el hash nuevo tras una enmienda [frontend-04] | media | fallo | frontend, estado | horas | 0,85 |
| M-33 | Reducers espejo que simulan el resultado: recomprobarRetracciones afirma "sin cambios" antes de comprobar, aprobarPlan no aprueba la misión, revisarHipotesis no registra la decisión [frontend-05] | media | fallo | frontend | un día | 0,9 |
| M-34 | Tildes: los scripts reescriben el árbol por defecto y ya introdujeron errores de sentido ("pistas término", "reintentó"); textos del backend sin tilde llegan al estado ("Se cumplio" x10, "Apruebala" x4); 46 plantillas del frontend sin revisar [tests-05, tests-06, frontend-06] | media | fallo | tests, frontend | horas | 0,95 |
| M-35 | Bundle único de 974 KB sin partir y servido sin gzip ni caché desde el 8765 [frontend-08] | media | riesgo | frontend | horas | 0,95 |
| M-36 | VEREDICTO[...] y CERTEZA_EVIDENCIA[...] se indexan sin guarda en diez sitios: un veredicto nuevo tumba la Cola y el Ranking [frontend-09] | media | riesgo | frontend | horas | 0,8 |
| M-37 | Sin CI, sin hooks, sin escaneo de secretos automático: el commit 2190550 llegó a origin/main sin compilar [tests-04] | media | riesgo | operación | un día | 0,95 |
| M-38 | 14 `except Exception` seguidos solo de pass o continue en caminos que producen datos (novedad, gasto GEPA, acuerdo con personas) [tests-08] | media | riesgo | código | un día | 0,85 |
| M-39 | Operar ROSA2018 exige terminal: .env obligatorio para arrancar, sin recarga de código, sin versión visible, sin supervisor que relance [tests-09] | media | deuda | operación | varios días | 0,85 |
| M-40 | Funciones enormes (crear_app 620 líneas) y la regla del Killer duplicada en _evaluar_cambio con reglas ya divergentes [tests-11] | media | deuda | código | horas (Killer) a días | 0,85 |

### Bajos

| id | título | severidad | tipo | zona | esfuerzo | confianza |
|---|---|---|---|---|---|---|
| B-01 | El reloj de la corrida contaba tiempo de pared: resuelto en 8a4eb64; quedan pausada_por_presupuesto fuera de la espera humana y el frontend pintando tiempo de pared [corrida-06, tests-10] | baja | fallo | corrida | horas | 0,9 |
| B-02 | El tope se comprueba antes de proponer el plan pero no al aprobarlo: la iteración condenada nace igual (el cierre vacío ya no cuesta nada desde 8a4eb64) [corrida-07] | baja | fallo | corrida | horas | 0,9 |
| B-03 | El vivero nunca ha recibido una idea: el generador devuelve lista vacía porque la firma le pide dos cohortes y calla las de una [killer-12] | baja | ineficiencia | killer | horas | 0,75 |
| B-04 | Cobertura por tema como cadena libre que cambia en cada paso (sin verificar) [literatura-12] | baja | deuda | literatura | un día | 0,85 |
| B-05 | El índice semántico solo ve el título de cada fuente (lee f["resumen"], que no existe) (sin verificar) [literatura-13] | baja | fallo | literatura | horas | 0,95 |
| B-06 | Tope de 14 páginas de PDF sin registrar y PDF sin texto que no cae al XML (sin verificar) [literatura-14] | baja | fallo | literatura | horas | 0,9 |
| B-07 | Una pista detenida o un fragmento fallido repite o pierde la extracción de toda la fuente (sin verificar) [extraccion-12] | baja | ineficiencia | extracción | horas | 0,8 |
| B-08 | Lo sintético cuenta como sostenido en Killer y priorización aunque certeza lo excluya (sin verificar) [extraccion-13] | baja | riesgo | killer | horas | 0,7 |
| B-09 | El mismo artículo entra varias veces en la procedencia con ids distintos por corrida (sin verificar) [evidencia-10] | baja | deuda | evidencia | horas | 0,85 |
| B-10 | El registro de procedencia dice "Iteración 1" cinco veces sin la corrida (sin verificar) [evidencia-11] | baja | deuda | evidencia | horas | 0,95 |
| B-11 | tipoEstudio "otro" en 25 de 37 fuentes y sesgo sin evaluar en 33: el peso a favor frenado por metadatos ausentes (sin verificar) [evidencia-12] | baja | riesgo | evidencia | horas | 0,75 |
| B-12 | Meta-campaña, evaluación de criterios y vigilancia bloquean el tick y se cargan a corridas terminadas (sin verificar) [corrida-10] | baja | riesgo | corrida | un día | 0,7 |
| B-13 | La meta-revisión apila 128 criterios "propuestos" que nadie decide (sin verificar) [corrida-11] | baja | deuda | corrida | horas | 0,8 |
| B-14 | eventos y hechos crecen sin tope (sin verificar) [estado-11] | baja | riesgo | estado | horas | 0,8 |
| B-15 | Ficheros de base de datos con nombres que confunden (datos/rosa.db vacío, rosa.db.db) (sin verificar) [estado-12] | baja | deuda | estado | horas | 0,5 |
| B-16 | Tras un reducer que lanza, la siguiente fila del registro dice que cambiaron las 40 claves (sin verificar) [estado-13] | baja | fallo | estado | horas | 0,85 |
| B-17 | Cabecera x-rosa-interno no ASCII provoca 500 en el middleware (sin verificar) [servidor-10] | baja | fallo | servidor | horas | 1,0 |
| B-18 | Rutas /api desconocidas devuelven 200 con index.html; [::1] rechazado (sin verificar) [servidor-11] | baja | fallo | servidor | horas | 1,0 |
| B-19 | mlflow.db crece sin retención (376 MB) (sin verificar) [servidor-12] | baja | ineficiencia | servidor | horas | 0,8 |
| B-20 | bloqueosDe se recalcula por fila en cada render (sin verificar) [frontend-10] | baja | riesgo | frontend | horas | 0,7 |
| B-21 | Física del árbol O(n²) en el hilo principal (ya anotado) [frontend-11] | baja | deuda | frontend | varios días | 0,85 |
| B-22 | 30 botones sin type, un clicable sin role, 4 clases CSS sin uso (sin verificar) [frontend-12] | baja | deuda | frontend | horas | 0,7 |
| B-23 | El cerebro cae a Sonnet en silencio ante cualquier error con "parse" o "content" (sin verificar) [modelos-11] | baja | riesgo | modelos | horas | 0,65 |
| B-24 | El sesgo de publicación no se evalúa aunque la escalera lo exige; una expression of concern no pesa (sin verificar) [rigor-12] | baja | deuda | certeza | varios días | 0,8 |
| B-25 | Dos criterios opuestos sobre qué significa la decisión del Killer entre el llano y el revisor (sin verificar) [rigor-13] | baja | riesgo | rigor | horas | 0,7 |
| B-26 | Un test sale a la red (Crossref) y tres dependen del reloj (sin verificar) [tests-12] | baja | riesgo | tests | horas | 0,95 |
| B-27 | Aserción vacía en App.cliente.test.tsx: busca un texto que no existe (sin verificar) [tests-13] | baja | fallo | tests | horas | 0,95 |
| B-28 | Python sin tipado ni lint; dependencias solo con cota inferior (sin verificar) [tests-14] | baja | deuda | tests | un día | 0,85 |

## (c) Fichas de los hallazgos críticos y altos

### S-01. Dos procesos de ROSA2018 escriben en rosa.db sin cerrojo: decisión perdida y auditoría rota

Qué pasa. El almacén abre SQLite sin ningún cerrojo entre procesos y escribe la fila única del estado sin comprobar que la versión en disco sea la que el proceso cree tener. Cuando se reinicia ROSA2018 con una revisión del Killer en vuelo, el proceso viejo sigue vivo hasta que el juez responde (hasta 600 s) y después escribe su estado obsoleto encima del nuevo.

Evidencia. rosa/estado/almacen.py:88 `sqlite3.connect(str(self.ruta), timeout=30.0, check_same_thread=False, isolation_level=None)` sin flock ni PRAGMA de exclusividad; :135 `UPDATE estado SET version=?, json=? ... WHERE clave='rosa'` sin condición sobre la versión anterior; :99 `_ultimo_hash` se lee una sola vez al arrancar. rosa/bucle/corrida.py:119-131 `correr()` hace `recuperar_tras_reinicio()` (mutación) antes de mirar nada, y `_atender_peticiones` (:224-249) ejecuta `await PASOS._revisar_hipotesis(...)` dentro de la propia corrutina, fuera de `self.tareas`, así que `parar()` (:139) no la cancela. Registro real (tabla acciones): fila 6438 (15-09 12:05:02, v6432) es el último eslabón común; el proceso nuevo escribe 6439-6449 (12:05:22, v6433-v6443); el viejo escribe 6450-6454 a las 12:06:55 con v6433-v6437 y hash_anterior de 6438; la fila 6451 `killer` guarda la decisión dec-mu2v76du-6723 ("suspender: sesgo_evidencia, las tres afirmaciones comparten el mismo riesgo serio...", 112 s de Opus, 0,89 USD); esa decisión no existe en el estado; en su lugar quedó dec-mu2vas4j-54 (12:09:43) con motivo "El juez no respondió", que es falso. GET /api/registro/integridad hoy: ok:false, rotaEn 6450, motivo "fila borrada o insertada". Cinco retrocesos de versión en el registro (10-09 15:59 y 16:43, 11-09 11:21 dos veces, 15-09 12:06): el patrón se repite en cada reinicio con trabajo del modelo en vuelo. Reproducido en scratchpad/revision_bugs/verificacion/estado-01-reproducir/test_doble_arranque.py y servidor-01-reproducir/test_dos_procesos.py.

Escenario. Emir hace un commit, reinicia el servidor mientras el Killer está juzgando; el nuevo arranca sobre la misma base con `_revisionPedida` puesta y repite la revisión (2,16 USD más); el viejo termina, escribe y pisa; el nuevo vuelve a guardar y borra lo del viejo.

Impacto en llano. Una decisión científica pagada desapareció y fue sustituida por una peor y falsa; el registro que se presenta como prueba de que nadie tocó el historial (sellos RFC 3161, RO-Crate) dice "roto" desde hace dos días y no hay forma de volver a verde; en Integridad la persona lee una acusación de manipulación que no ocurrió.

Causa. El diseño "un solo escritor" (README 430-437) es una convención sin garantía; `verificar_cadena` (almacen.py:218-237) para en la primera rotura y solo conoce un tipo de rotura.

Arreglo propuesto. (1) Cerrojo de fichero `fcntl.flock` sobre rosa.db.lock en `Almacen.__init__`, bloqueante con aviso ("otra ROSA2018 sigue cerrando") hasta 600 s; no usar `PRAGMA locking_mode=EXCLUSIVE`, que en WAL impide a los scripts de análisis leer la base. (2) `UPDATE ... WHERE clave='rosa' AND version=?` y, si rowcount es 0, ROLLBACK, incidencia y parada del bucle, nunca pisar. (3) `parar()` rechaza llamadas nuevas al modelo pero deja terminar la que va en vuelo; tope al `gather` de main.py:91. (4) `verificar_cadena` distingue "bifurcación por reinicio" (hash_anterior apunta a una fila existente no inmediata) de "fila borrada" (hash inexistente), sigue verificando tras cada rotura, y admite una fila `corte_registrado` firmada que reancle la cadena con la causa documentada; la pantalla dice "1 corte documentado" en vez de "rota". (5) Añadir `al.cerrar()` a los tres tests que reabren un almacén (test_acciones.py:99, test_integracion_estado.py:93 y :398). Esfuerzo: un día.

Lentes. Reproducir (estado): confirmado, crítica; refina que el escritor pisado fue el proceso viejo en apagado, no un choque de puerto. Reproducir (servidor): confirmado, crítica; cuatro episodios en seis días. Impacto (estado): confirmado, alta (ciencia intacta porque el superviviente rehízo el paso; auditoría irreversible). Impacto (servidor): confirmado, crítica (dato falso "el juez no respondió" y prueba ALCOA+ rota para siempre). Elección: crítica, por la vara "engaña a la persona con un dato falso" y por ser irreversible con el código actual.

### S-02. La novedad declara "sin precedente" con 0 obras: chip verde y Killer "pasa" sin haber comprobado nada

Qué pasa. El paso de novedad busca precedentes en OpenAlex con cuatro términos clave del título; si la búsqueda devuelve 0 obras, o si el modelo de relevancia falla en todas, la puntuación máxima queda en 0 y la regla escribe "sin precedente". La consulta se construye con una expresión que corta las palabras en la tilde y las manda en castellano a un índice en inglés, así que devuelve 0 casi siempre.

Evidencia. rosa/bucle/pasos.py:2411-2425: `except Exception: continue` en el bucle de cribado y después `novedad["precedente"] = {"estado": "sin_precedente", "detalle": f"Sin precedente claro entre {total} obras que casan con: {termino}"}` sin distinguir "no había obras" de "no se parecen". rosa/bucle/contexto.py:410 `terminos_clave` con `[A-Za-z][A-Za-z0-9\-]{2,}`: `terminos_clave("BACE1 aporta información pronóstica adicional a GFAP")` devuelve ['BACE1', 'informaci', 'adicional', 'GFAP']. Las 25 consultas a OpenAlex de precedente en la historia de ROSA2018 (pistas `novedad` del estado) devolvieron "0 obras". En vivo con rosa.fuentes.openalex.buscar: "Precedencia anormalidad GFAP APOE" da 0; "GFAP NfL APOE" da 328. Estado: 16 de 28 hipótesis con "Sin precedente claro entre 0 obras", entre ellas dos aceptadas por una persona (hip-mtvwqw1i-37, hip-mtvwqw1z-46); las 6 "entre 6 obras" de inv-mu2sz2ns-3 se deben solo a Exa. rosa/killer.py:161-170: ese estado da la comprobación crítica `novedad` como "pasa". frontend/src/pantallas/Hipotesis.tsx:459 chip tono ok "Sin precedente"; frontend/src/lib/ranking.ts:191 `nueva`. pasos.py:2338 y corrida.py:1204 solo repescan hipótesis cuyo detalle empieza por "No comprobado": las 16 no se vuelven a comprobar nunca. Lo mismo en `_novedad_exa_dominios` (pasos.py:816-831) para patentes y financiación. Tests: scratchpad/revision_bugs/verificacion/tests-01-reproducir/test_tests01_reproducir.py (5 casos) y tests-01-impacto/test_causa_raiz.py (3).

Escenario. Nace una hipótesis; su título en castellano se convierte en "reducci GFAP eliminaci cerebral"; OpenAlex devuelve 0; ROSA2018 escribe novedad, el Killer la da por superada, la persona ve el chip verde y prioriza una hipótesis que puede estar publicada.

Impacto en llano. ROSA2018 afirma "nadie lo publicó antes" sin haber buscado de verdad, en el 57 % de las hipótesis, y no se corrige solo. Incumple "una fuente que no responde es no pude comprobar" y la comprobación crítica del Killer queda hueca.

Causa. Dos capas: la consulta está rota de raíz (tilde y castellano) y la regla de novedad confunde "no evalué nada" con "evalué y no se parece"; el `except Exception: continue` esconde los fallos del modelo. El arnés de tests (test_integracion_corrida.py:89, `programas` sin `relevancia`) ejercita justo la rama del error tragado.

Arreglo propuesto. (1) Construir la consulta a OpenAlex con siglas, genes y tokens con cifra de `h["_entidades"]`, `tarjeta.diana` y `comprobacion.biomarcador`; aceptar acentos y ñ en `terminos_clave`; si quedan menos de 2 tokens, no consultar y anotar "no comprobado". (2) Contar `evaluadas` y `fallos`; con `total == 0` o `evaluadas == 0` escribir `no_comprobado` con el motivo; anotar cada excepción en la pista; lo mismo en `_novedad_exa_dominios`. (3) Migración al cargar: todo precedente con "entre 0 obras" vuelve a `no_comprobado` para que el bucle las retome. (4) En `killer.fusionar` impedir que el juez resuelva `novedad` con un "pasa" de memoria. (5) Añadir `relevancia` (y los 38 nombres reales de Programas) al arnés de tests. Esfuerzo: horas.

Lentes. Reproducir: confirmado, alta (no son 6 sino 16 hipótesis; encontró la truncación en la tilde). Impacto: confirmado, crítica (dato presentado como verificado en el 57 %, Killer lo da por pasado, sin camino de corrección). Elección: crítica, por la vara literal y porque afecta a hipótesis ya aceptadas por una persona.

### S-03. El verificador no reconoce "texto web, parte N": el 100 % de las afirmaciones de Exa se bloquea

Qué pasa. El tercer recurso de texto completo (Exa) crea fragmentos con localizador "texto web, parte N" y la cita determinista `[referencia, localizador]`; el patrón de citas del verificador solo admite pág., resumen y sección, así que `resolver_cita` devuelve None y toda afirmación nace `cita_no_resuelve` antes del juez. Además, con más de un fragmento, la extracción salta el resumen, que sí resolvería: leer por Exa rinde menos que no leer.

Evidencia. rosa/verificador.py:31 `PATRON_CITA = re.compile(r"\[(.+?),\s*(p[aá]g\.\s*\d+(?:-\d+)?|resumen|secci[oó]n\s+[^\]]+)\]...")`; :178-186 `resolver_cita`; :196-198 convierte el None en "no apunta a ninguna fuente ni localizador conocidos". rosa/bucle/pasos.py:470 `"localizador": f"texto web, parte {i}"`; :1044 `"cita": f"[{f['referencia']}, {fr['localizador']}]"`; :1004-1006 quita el resumen si hay más fragmentos; :371 y :398 marcan `textoCompleto=True`. Datos (GET /api/corridas/{id}/evidencia, 9 corridas de inv-mu2sz2ns-3): 875 afirmaciones "texto web" extraídas, 875 bloqueadas; corrida 7: 83 de 87 bloqueadas; corrida 8: 158 de 174; corrida 9: 134 de 142; en todo el estado 1.237 afirmaciones web, 100 % bloqueadas, ninguna llegó nunca al juez. Con resolución por fuenteId más localizador, 1.107 de 1.237 (89 %) pasarían la comprobación literal e irían al juez. El commit c4be6d9 (Exa, parte 4) tocó pasos.py y no verificador.py; ningún test menciona "texto web". Reproducido en cuatro carpetas de verificación (literatura-01, extraccion-01, modelos-01, rigor-01).

Escenario. Cummings et al., 2026 (PMID 41865758, `textoCompleto: true`, 7 fragmentos, relevancia 9) da la afirmación "En los ensayos evoke y evoke+, la semaglutida oral no mostró diferencia significativa..." con cita `[Cummings et al., 2026, texto web, parte 2]`: bloqueada; la interfaz la enseña como "Cita sin fuente" (frontend/src/lib/etiquetas.ts:196) cuando la fuente y el pasaje existen.

Impacto en llano. Más de la mitad de la evidencia que ROSA2018 lee y paga se tira antes de juzgarla, justo la de las fuentes primarias que no tienen PDF ni XML (literatura gris, registros, artículos recientes). Las hipótesis se quedan sin la segunda cohorte que necesitan para subir de certeza; el pendiente del TRASPASO ("extraer solo de fuentes con texto completo") no lo arreglaría, porque estas fuentes cuentan como texto completo. Al arreglarlo, las llamadas al juez por iteración subirán de unas 60 a unas 190.

Causa. Lista cerrada de localizadores en el verificador que no se amplió al añadir el conector; no hay test que cruce los localizadores de `_fragmentos_de` con `PATRON_CITA`.

Arreglo propuesto. (1) Resolver primero por `(fuenteId, localizador)`, que la afirmación ya trae, dejando la cita por texto como respaldo (esto también evita las colisiones de S-04). (2) Ampliar `PATRON_CITA` con `texto web,\s*parte\s+\d+` (cubre la replicación, corrida.py:930, que borra fuenteId). No usar "última coma": "texto web, parte N" lleva coma. (3) Constante única de localizadores en verificador.py importada por pasos.py y comprobación en la extracción de que la cita resuelve antes de guardar. (4) Test parametrizado con los cuatro localizadores. (5) Script de mantenimiento que ponga `sin_verificar` las 875 bloqueadas por este motivo, las pase por `verificar_afirmaciones` y por `paso_modelo` (el bucle no lo hará solo: pasos.py:1136 y :1197 filtran por corrida e iteración actuales); presupuestar hasta 875 llamadas a Opus. (6) Corregir la nota de TRASPASO.md:563-568 y hacer que el motivo diga "localizador no reconocido" en vez de "no apunta a ninguna fuente". Esfuerzo: horas más el script.

Lentes. Ocho verificaciones (dos por zona), todas confirmadas; severidad alta en siete, crítica en una (reproducir de literatura). Elección: alta, porque es un falso negativo (nada falso entra al modelo de mundo), aunque el mensaje "Cita sin fuente" sí engaña sobre la causa.

### S-04. La referencia corta no es única: citas correctas que resuelven a la fuente equivocada

Qué pasa. `resolver_cita` empareja por texto de referencia y localizador y devuelve el primer fragmento; `referencia_corta` devuelve "Sin autor" para toda fuente sin autores (Exa, registros) y dos artículos distintos del mismo primer autor y año comparten nombre.

Evidencia. rosa/verificador.py:178-186 (primer fragmento que coincide, sin mirar fuente_id); rosa/fuentes/base.py:111-114 ("Sin autor" o "Sin autor, {anio}"); rosa/bucle/pasos.py:1100 llama a `comprobar_determinista` sin pasar `a["fuenteId"]`, y en :1093 construye `por_id` que nunca usa. Datos: corridas 7, 8 y 9 con 3 fuentes "Sin autor" cada una; corrida 9 registró dos artículos distintos "Bhagunde et al., 2026" (PMC12823306 doi 10.1002/psp4.70173 y PMC13095857 doi 10.1002/trc2.70246) con 6 secciones homónimas (Introduction, Methods, Results...); en la corrida 8 el trc2 produjo tres hechos desde METHODS y RESULTS; en la corrida 9, registrado segundo, solo produjo uno desde BACKGROUND, la única sección que el otro no tiene. corrida.py:623 cuenta `base.fuentes` por referencia (dos artículos distintos cuentan como uno). Tests en verificacion/literatura-02-reproducir y extraccion-02-reproducir.

Escenario. Dos fuentes homónimas con localizador igual: la segunda pierde todas las afirmaciones de las secciones compartidas (bloqueo falso) o, si el pasaje está en las dos, el veredicto se calcula contra el texto de la otra.

Impacto en llano. Hoy el efecto está tapado por S-03 (los "Sin autor" son casi todos de Exa); en cuanto se arregle S-03, las 34 fuentes "Sin autor" y las parejas homónimas chocarán de verdad. Primer autor y año repetidos son habituales en Alzheimer (Bateman, Cummings, Mintun, Sims).

Causa. La cita, que es texto para personas, se usa como identificador; la afirmación ya guarda `fuenteId` y `localizador` y nadie los usa.

Arreglo propuesto. `resolver_cita(cita, fragmentos, fuente_id=None)`: si viene el id, buscar solo entre los fragmentos de esa fuente; `verificar_afirmaciones` pasa `a.get("fuenteId")`; `_replicar_paso` (corrida.py:924-930) no vacía `fuenteId`; las afirmaciones copiadas a la hipótesis (pasos.py:2003) llevan `fuenteId` y `localizador`; `base.fuentes` y la deduplicación de citas de un hecho (pasos.py:1246) por id, no por referencia. No añadir sufijos "2026a/b" (dependerían del orden de llegada). Para la persona, `referencia_corta` sin autores debe usar sitio o título ("ALZFORUM, 2023: ..."). Esfuerzo: horas.

Lentes. Reproducir (literatura): confirmado, alta. Impacto (literatura): parcial, media (hoy explica pocos bloqueos; sube a alta tras S-03). Reproducir e impacto (extraccion): confirmado y parcial, alta (los Bhagunde son dos artículos distintos, lo que hace el fallo peor, no menor). Elección: alta, porque es el siguiente cuello tras S-03 y su reproducción con datos reales ya perdió las secciones de resultados de un artículo.

### S-05. La comparación literal contra el PDF tira la mitad de las afirmaciones de página

Qué pasa. Dos normalizaciones distintas (pdf.py y verificador.py), ninguna trata los artefactos del texto de PyMuPDF: números de línea intercalados de los preprints (medRxiv), guiones de fin de línea, comillas tipográficas. Las afirmaciones de página son las únicas que cumplen la regla de la cita a la página exacta.

Evidencia. rosa/fuentes/pdf.py:66-80 `_normalizar` solo colapsa espacios; `fragmento_en_pagina` exige las 12 primeras palabras literales. rosa/verificador.py:131-147 `pasaje_en_texto` cambia "-" por espacio (así "imag-\ning" queda "imag ing") y tolera una ventana. rosa/bucle/pasos.py:1027-1030 marca `cita_no_resuelve` al nacer sin pasar por el juez. Sobre copia de rosa.db: 540 afirmaciones "pág. N", 284 bloqueadas (53 %): 188 por números de línea (Belder 2026, preprint), 61 por marcas de cita "(4, 5)" que el extractor quita, 11 por guion de corte, 3 por comillas, 21 no literales (bloqueo correcto), 0 con la página equivocada. Una normalización compartida (NFKC, quitar líneas que son solo un número, unir palabra partida, quitar marcas de cita) recupera 235 de 284 sin aceptar ninguna página equivocada; aplicada solo en un lado rompe 12 afirmaciones hoy sostenidas ("bi-weekly" copiado con guion). Belder pierde 56 % de sus afirmaciones en las corridas 1 y 2. Scripts en verificacion/literatura-10-reproducir y extraccion-03-impacto.

Escenario. Página 2 de Belder 2026: el PDF trae "Longitudinal analyses \n55 \nshowed Aβ42 levels..."; el extractor copia la frase limpia; la aguja falla y la afirmación nace bloqueada con motivo "no aparece literalmente en la página indicada".

Impacto en llano. Se pierde justo la evidencia con página exacta, que es la de más calidad, a una tasa siete veces mayor que la de sección o resumen, y el motivo hace creer que la página es incorrecta.

Causa. Normalizaciones hechas a mano en dos módulos; el extractor recibe el texto crudo y devuelve una copia limpia; la firma exige "copiada sin cambios" sobre un texto que no se puede copiar sin cambios.

Arreglo propuesto. Una sola función `normalizar_texto_pdf` en verificador.py aplicada a los dos lados (fragmento y página): NFKC, quitar líneas que sean solo un número de 1 a 4 cifras, borrar guiones interiores en ambos lados, quitar marcas de cita numéricas, comillas a ASCII, después el `normalizar` actual; comparar por secuencia compacta de palabras; mantener la comparación actual como primer intento. En pasos.py:1027 comparar contra `fr["texto"]` en vez de reabrir el PDF por afirmación. En `pdf.paginas()`, quitar la numeración de líneas de preprints antes de guardar el fragmento. Tests con las páginas reales de pdfs/ (Belder pág. 2 y 4, Biel pág. 3, Ma pág. 2) y el M2 existente. Esfuerzo: medio día.

Lentes. Cuatro verificaciones: parcial (causa dominante distinta a la del hallazgo) y confirmadas; severidad alta en las cuatro.

### S-06. Las fuentes no se recuerdan entre corridas y los fragmentos nuevos de una fuente ya extraída no se extraen

Qué pasa. `_fuentes` y `_afirmaciones` son privadas de la corrida; la única memoria entre corridas es `_excluidos_previos`, que recuerda excluidos con relevancia baja. Cada corrida nueva vuelve a cribar, consultar Crossref y Unpaywall, extraer y juzgar las mismas fuentes; la fusión dentro de la corrida llega después de gastar; y cuando una fuente ya extraída recibe páginas nuevas, `extraida` sigue True.

Evidencia. rosa/bucle/pasos.py:208-212 (`fuentes()` y `afirmaciones()` por corrida), :356-360 (fusión solo en `c["_fuentes"]`), :130-147 y :700-706 (`_excluidos_previos`), :775-781 (descarga antes de registrar), :362-380 (rama existente no toca `extraida`), :988 (pendientes = no extraídas). Datos: 253 fuentes registradas, 179 claves distintas, 53 en más de una corrida; 19 fuentes reextraídas 22 veces, de las que salieron 517 de las 1.532 afirmaciones (34 %); Bateman 2023 descargado por Exa 6 veces en las corridas 7 a 9; trazas de GEPA: 41 de 163 extracciones (25 %) sobre texto ya extraído en otra corrida. Riesgo GRADE: hip-mu2tskgf-2920 con Raket 2026 dos veces (dos fuenteId) y el techo diciendo "3 cohortes distintas" cuando son 2; `_fuentes_de_hipotesis` (pasos.py:1397-1401) solo mira la corrida actual, así que 36 de 40 fuentes de la investigación viva no tienen sesgo evaluado. Fallo menor: `_clave_articulo` (pasos.py:128) escribe "título:" con tilde y `_excluidos_previos` (:141) compara "titulo:" sin tilde, guarda muerta. Tests en verificacion/literatura-03, literatura-09, extraccion-09, modelos-07.

Escenario. Corrida 9: Gueorguieva 2023 vuelve a salir; Sonnet la puntúa, Crossref, Exa (12 partes), 6 extracciones, y sus afirmaciones nuevas (paráfrasis) pasan al juez y generan hechos casi duplicados (Belder "excluyeron cuatro no portadores" x2).

Impacto en llano. Trabajo repetido en cada corrida (un 5 a 15 % del gasto, no la causa principal), pero sobre todo cohortes contadas dos veces (puede subir el techo de muy baja a baja al releer un artículo), sesgo nunca evaluado para fuentes de corridas anteriores, y hechos duplicados que la persona ve como conocimiento distinto.

Causa. Almacén de evidencia por corrida, no por investigación; la fusión llega tras gastar; `extraida` es un booleano por fuente.

Arreglo propuesto. Hoy, en horas: (a) en certeza.py `_Vista.cohortes()` fusionar fuentes con la misma `claves_de_fuente` antes de contar; (b) en evidencia.py comprobar claves compartidas al añadir a procedencia; (c) `_fuentes_de_hipotesis` busca en las `_fuentes` de todas las corridas de la investigación; (d) marcar `extraido` por fragmento y extraer solo los nuevos; (e) comprobar existencia con `claves_de_fuente` en `_consulta_literatura` antes del reranker y de Sonnet; (f) caché en disco para `europepmc.texto_completo` y `exa.contenidos` como ya tiene `pdf.descargar`; (g) unificar `_clave_articulo` con `claves_de_fuente`. Después, en días: registro de fuentes por investigación con fragmentos, afirmaciones y veredictos reutilizables, repuntuando la relevancia solo si cambia la pregunta. Esfuerzo: varios días el registro; horas los cortes.

Lentes. literatura-03 confirmado y parcial (alta las dos; el impacto refuta que sea la causa principal del coste y sube el peso a lo científico); literatura-09 confirmado media; extraccion-09 confirmado media; modelos-07 parcial media. Elección: alta por las consecuencias GRADE.

### S-07. Las primarias de los ensayos nombrados se excluyen para siempre y la red de seguridad por nombre está apagada

Qué pasa. La red de seguridad que debía añadir una consulta simple por cada nombre propio del objetivo ("lecanemab", "evoke") se salta si cualquier consulta previa contiene la palabra, aunque sea una consulta estrecha con cinco cláusulas AND; no hay relajación de consultas; y la caché de exclusiones reutiliza para siempre un corte del reranker que ningún modelo miró o un juicio hecho contra preguntas heredadas de otra investigación.

Evidencia. rosa/bucle/pasos.py:523 `if any(n.lower() in h for h in hechas): continue`; :130-146 `_excluidos_previos` con umbral `minimo - 2`; :713-717 asigna al corte del reranker `min(minimo - 1, round(s*10))`, y con pertinencia 0,33 da 3, que se reutiliza como "excluido con claridad". El artículo primario de EVOKE/EVOKE+ (Cummings 2026, Lancet, 10.1016/s0140-6736(26)00459-9) se recuperó 7 veces en 3 bases y se excluyó las 7: una vez por Sonnet con criterio heredado ("sin relación con GFAP/NfL en Alzheimer autosómico dominante", 25 de 58 preguntas abiertas son heredadas, contexto.py:215-235), tres por el reranker sin llamada al modelo, y desde la corrida 5 como "ya excluido en la corrida 5: fuera del corte del reranker (pertinencia 0.33)". CLARITY AD (10.1056/nejmoa2212948) y TRAILBLAZER-ALZ 2 (10.1001/jama.2023.13239) excluidas con relevancia 0 a 1 desde la corrida 1 y reutilizadas hasta la 8. Corrida 7: 10 de 20 temas con 0 leídos; consultas de foco de 2 a 7 resultados y 0 relevantes. El "+" de "evoke+" se ignora en Europe PMC (hitCount idéntico con y sin él, 2.901), pero eso no explica los ceros: el primario iba en la posición 1 de los 30 traídos. Tests en verificacion/literatura-05-reproducir y literatura-06-reproducir.

Escenario. El cerebro escribe `"lecanemab"[tiab] AND ("tau PET"...) AND (mediat*...)`: 3 resultados, 0 relevantes; la red no añade `"lecanemab"` porque la palabra ya aparece; si la añadiera, el primario volvería a caer en la caché de exclusiones con el motivo de la corrida 1.

Impacto en llano. Los ensayos que la persona escribió en el objetivo siguen sin fuente primaria tras nueve corridas, y las hipótesis en cola no reciben la evidencia directa (misma población, mismo marcador) que es la única que subiría su certeza.

Causa. Comparación por subcadena; ausencia de relajación; caché de exclusiones sin caducidad ni distinción entre "un modelo lo puntuó" y "el reranker lo cortó".

Arreglo propuesto. (1) En `anotar_cribado` guardar `puntuadoPorModelo`; `_excluidos_previos` no reutiliza cortes del reranker ni exclusiones hechas con un hash de criterio distinto; un artículo cuyo título contiene un nombre propio del objetivo nunca se descarta por caché. (2) `consultas_por_nombre` compara por palabra completa y considera "buscado" solo si hubo una consulta simple con al menos un relevante. (3) Relajación acotada: consulta de foco con menos de 5 resultados y 3 o más cláusulas AND se relanza sin la última, una vez, anotada. (4) Tope de tres cláusulas en `GenerarConsultas`. (5) Traducir `nombre+` a `TITLE_ABS:"nombre"` en Europe PMC y marcar consultas con hitCount > 1.000 y 0 relevantes. (6) Poner las preguntas propias por delante de las heredadas en `preguntas_abiertas`. Esfuerzo: un día.

Lentes. literatura-06 parcial, alta (la caché de exclusiones es la causa real, el reparto foco/amplitud se cumple); literatura-05 parcial, media (el "+" es real pero no explica los ceros). Elección: alta, con la caché como pieza principal.

### S-08. El bucle vuelve sobre la cola solo desde hoy a las 12:07 y le quedan tres huecos

Qué pasa. Hasta el commit 62b327b nada pedía revisión al Killer cuando llegaba evidencia nueva; el servidor vivo (pid 88032) arrancó a las 12:07 con ese código y hoy ya rejuzgó dos hipótesis (hip-mu2tgh7o-1740 pasó de "descartar en contexto" a "avanzar"). Pero: (a) las tres hipótesis que acumularon evidencia con el código viejo (hip-mu2uajpx-4553, hip-mu2zz5y8-2440, hip-mu30n7o9-4025) no tienen marca y no se rejuzgan; (b) si falla la revisión inicial, `_revisar_hipotesis` devuelve sin Killer y el `finally` borra la marca; (c) el torneo ve solo `afirmaciones[:8]` (28 acumuladas fuera) y la evaluación de supuestos recibe las afirmaciones de la corrida, no las de la hipótesis; (d) `_fuentes_de_hipotesis` no encuentra las fuentes de corridas anteriores, así que el sesgo nunca se evalúa en lo acumulado.

Evidencia. rosa/bucle/evidencia.py:233-234 (marca desde 62b327b); rosa/bucle/pasos.py:2057 (`a_revisar`), :1839-1840 (`return` sin Killer si falla revisar_inicial), :2062-2068 y rosa/bucle/corrida.py:250 (quitan la marca aunque no se juzgara); rosa/bucle/contexto.py:324 `h["afirmaciones"][:8]`; pasos.py:1848 `evaluar_supuesto(..., afirmaciones_sostenidas=texto_afirmaciones)` con `texto_af[:8000]` de la corrida; pasos.py:1397-1401. Estado vivo: hip-mu2tgh7o-1740 revisada 12:46 con 17 afirmaciones y supuestos evaluados contra "afirmaciones 20 y 22" que no existen en la hipótesis; las tres rezagadas con `ultimaRevisionAutomatica` del 15/09 y 10 a 14 afirmaciones. `version.arnes()` lleva `lru_cache`: la corrida registra el commit del arranque del proceso, no el del código. Tests en verificacion/corrida-01-reproducir, evidencia-03-reproducir, killer-01-impacto.

Escenario. hip-mu2zz5y8-2440 pasó de 3 afirmaciones de 1 fuente a 14 de 7; su Killer sigue diciendo "las tres afirmaciones provienen de una única publicación" (15/09 14:37) y nada la volverá a juzgar salvo que llegue otra fuente nueva.

Impacto en llano. Es la prueba del bucle que Emir dejó a propósito; funciona desde hoy para lo nuevo, pero la evidencia ya acumulada no mueve nada y el ranking y la revisión profunda se deciden viendo un tercio menos de lo que hay.

Causa. Marca puntual en vez de comparación de huella de evidencia; consumidores escritos cuando una hipótesis nacía con todas sus afirmaciones.

Arreglo propuesto. (1) Saneamiento único: marcar `_revisionPedida` en toda hipótesis viva con líneas "afirmaciones nuevas enlazadas" posteriores a su último Killer, o guardar en cada decisión la huella (afirmaciones, fuentes por DOI, supuestos) y rejuzgar cuando difiera. (2) `_revisar_hipotesis` sigue al Killer aunque falle la revisión inicial; la marca se quita solo si se juzgó; contador de intentos con tope. (3) `hipotesis_para_torneo` ordena por relación y recorta por caracteres; `_revisar_hipotesis` pasa primero las afirmaciones propias de la hipótesis. (4) `_fuentes_de_hipotesis` cae a la copia pública o busca en todas las corridas. (5) `arnes()` sin caché; `/api/salud` con commit y hora de arranque. Esfuerzo: un día.

Lentes. killer-01 confirmado alta/alta (escrito antes del reinicio); corrida-01 parcial media/alta; modelos-04 parcial media/media; evidencia-03 parcial media/media. Elección: alta, porque los residuos (rezago, hueco del juez, recortes) siguen impidiendo que la cola se mueva con lo ya acumulado.

### S-09. Un fallo del juez se convierte en suspensión permanente

Qué pasa. Si el juez del Killer lanza (parse, tiempo agotado), la rama de excepción fabrica una decisión válida "suspender: El juez no respondió" y nada la reintenta.

Evidencia. rosa/bucle/pasos.py:1644-1649 (`except Exception` -> `del_juez=[]`, resumen "El juez no respondió"), :1658-1660 (si la regla da avanzar, suspender), :1668-1730 (registra la decisión, marca la revisión como hecha, no pone `_revisionPedida`). hip-mu2uqqzu-5871 (Elo 1573, segunda del ranking): decisión 15/09 12:09:43 por fallo del adaptador JSON (incidencia inc-mu2varxh-52), sin decisión posterior en ocho corridas; el motivo científico anterior (sesgo) quedó enterrado. rosa/lecciones.py:27 y :102 y rosa/bucle/contexto.py:634 tratan esa suspensión como cierre del Killer y la pasan al planificador como "no reproponer". test_integracion_pasos.py:361 fija este comportamiento. Test en verificacion/killer-02-reproducir.

Impacto en llano. Una avería técnica se presenta como juicio científico, bloquea la candidatura y hasta genera una lección; incumple "no pude comprobar no es no hay".

Arreglo propuesto. En la rama except no registrar decisión: dejar `_revisionPedida` con contador (tope 2 o 3), conservar la decisión anterior, no marcar la revisión como hecha; al agotar el tope, decisión explícita "pendiente de que una persona pida la revisión"; excluir esas suspensiones de lecciones y del contexto del planificador; actualizar el test que fija lo contrario. Esfuerzo: horas.

Lentes. Confirmado y confirmado, alta las dos.

### S-10. El Killer descarta por supuestos que redacta el revisor y que Sonnet da por contradichos

Qué pasa. Los supuestos del generador se sustituyen por los que descompone el juez en la revisión inicial; cada uno se evalúa con Sonnet; cualquier "contradicho" pone la comprobación `supuestos` en falla, y `supuestos` está en DESCARTAN; `fusionar` ignora al juez Opus cuando la determinista ya dice falla.

Evidencia. rosa/bucle/pasos.py:1841 `supuestos_texto = list(rev.supuestos)[:8] or [...]`; :1848; :1862 sustituye la lista entera; rosa/killer.py:50 DESCARTAN, :108-111, :185-217 `fusionar`. rosa/modulos/firmas.py:349-352 pide "contradicho si alguna lo niega" sin índice ni distinción de ausencia. hip-mu2zedte-898: supuesto "El ensayo INVOKE-2 publica mediciones de P-tau181 en plasma y LCR" contradicho con evidencia "Ninguna afirmación menciona ese ensayo"; el juez Opus escribió que la premisa está "sin comprobar (no refutada, sin evidencia)" y el motivo registrado dice "1 supuestos contradichos"; auditoría en desacuerdo. Cuatro hipótesis descartadas así (1740, 4553, 898, 5575), todas con citas y fidelidad en pasa; hip-mu2tgh7o-1740 nació 11:18 y fue propuesta para descarte a las 11:21. En los otros tres casos Sonnet cita afirmaciones que sí niegan una premisa fuerte que la hipótesis no afirma (comparabilidad analítica, especificidad de NfL). Sin `supuestos` las cuatro habrían quedado "suspender", que es lo que el bucle rejuzga. rosa/evaluacion/panel_killer.py:106-108 planta el supuesto ya "contradicho" y no puede ver este fallo. Tests en verificacion/killer-03-reproducir.

Impacto en llano. Casi la mitad de la investigación viva quedó fuera del bucle por el eslabón más barato y menos vigilado, con un motivo que el propio juez negó.

Arreglo propuesto. (1) killer.py:50: mover `supuestos` de DESCARTAN a SUSPENDEN (una línea; actualizar README.md:64 y panel_killer.py:48). (2) `SupuestoEvaluado` con `afirmaciones_que_lo_niegan` validado por regla: "contradicho" sin índice válido o con "ninguna afirmación menciona" pasa a sin_evidencia. (3) `fusionar`: si la determinista de supuestos dice falla y el juez dice pasa, no_comprobable. (4) Conservar supuestos del generador con `origen` y mostrar la lista en la ficha. (5) Caso real en panel_killer que pase por RevisarInicial y EvaluarSupuesto. Esfuerzo: medio día.

Lentes. Confirmado y parcial (cifras corregidas: 4 de 5 hipótesis, 2 de 2 auditadas en desacuerdo), alta las dos.

### S-11. La novedad no se recalcula al reformular

Qué pasa. `reformular_hipotesis` cambia título y enunciado pero no toca `novedad`; `paso_novedad` solo procesa precedentes "No comprobado"; `_killer` se llama a sí mismo tras reformular y vuelve a fallar con el precedente de la versión anterior; a la tercera descarta por agotar reformulaciones.

Evidencia. rosa/estado/acciones.py:733-779; rosa/killer.py:161-166; rosa/bucle/pasos.py:2338 y :1747-1751. hip-mu35joen-2494: reformular 07:11 (v1, Willis 2024), reformular 08:27 (v2, mismo texto), descartar 08:30 (v3, "sigue fallando: novedad: Willis"), descartar otra vez 09:09; una sola línea "novedad ->" en el registro; enunciados distintos en las tres versiones; la auditoría de la v1 discrepó y no frenó nada. Las 2 reformulaciones que existen en el estado son las 2 por novedad. `fusionar` deja que el juez sustituya una novedad `no_comprobable` por "pasa" de memoria. Tests en verificacion/killer-04-reproducir.

Impacto en llano. Reformular para responder a "ya publicado" es imposible; se pagan dos reescrituras del cerebro y cuatro pasadas de Opus para una conclusión fijada, y la ficha dice "sigue fallando" cuando nunca se volvió a comprobar.

Arreglo propuesto. En `reformular_hipotesis`, si cambia título o enunciado, reiniciar precedente, patentes y financiación a "No comprobado" guardando la novedad vieja en la versión; en `_killer` no recurrir si la reformulación se pidió por novedad (dejar la marca; el plan ya ejecuta novedad después de hipótesis); en `fusionar` impedir que el juez resuelva novedad no comprobable. Esfuerzo: horas.

Lentes. Confirmado y confirmado, alta las dos.

### S-12. La auditoría por debate no tiene consecuencia y un auditor mudo cuenta como acuerdo

Qué pasa. En desacuerdo solo se añade un hallazgo y un evento; nada rejuzga; el muestreo se reinicia por corrida (índice 0 siempre auditado); si el auditor no responde se guarda `acuerdo: True`.

Evidencia. rosa/bucle/pasos.py:1743-1746 (`_descartesVistos` de la corrida), :1763-1766 (`acuerdo: True` con "El auditor no respondió"), :1773-1777; rosa/killer.py:257-261 (`k=3`, `indice % k == 0`). 13 decisiones descartar/reformular, 9 auditadas (69 %), 5 en desacuerdo, 4 siguen bloqueadas; la única que se rejuzgó fue por un "reabrir" humano. `fusionar` ya tiene la regla "se abstiene, no mata" para DISCREPABLES y la auditoría no la aplica. Ninguna métrica agrega `auditoria.acuerdo`. Tests en verificacion/killer-06-reproducir.

Impacto en llano. La señal más cara del sistema (dos modelos en desacuerdo) se archiva; el patrón "el Killer mata ideas buenas" que el diseño quería medir no se mide.

Arreglo propuesto. En desacuerdo, rebajar la comprobación discutida a no_comprobable y recalcular `K.decidir` por regla como etapa `killer_2` (suele dar suspender, que el bucle rejuzga); si el auditor no responde, `acuerdo: None`; muestreo por total de decisiones de la investigación; `corridaId` en las decisiones; porcentaje de desacuerdo por comprobación en Calidad. Esfuerzo: medio día.

Lentes. killer-06 confirmado alta/alta; killer-10 confirmado media.

### S-13. El cierre reconcluye ocho hipótesis y rejuega el torneo sin evidencia nueva

Qué pasa. Al cerrar cada iteración se rehacen hasta 8 conclusiones con Opus en serie (la marca `_conclusionIntentada` se compara con el número de iteración, que se reinicia por corrida) y el torneo empareja 4 a 6 pares aunque nada haya cambiado; la caché de DSPy cubre el caso idéntico, pero cada torneo cambia el campo `partidos` del prompt y la invalida.

Evidencia. rosa/bucle/corrida.py:1409-1414; :604-606 (docstring "se rehace al cerrar cada iteración"); :683 registra "cambio de creencia" por cambio de dirección sin evidencia; rosa/torneo.py:37-38 y :68 (revancha si Elo <= 100); rosa/bucle/pasos.py:1890-1901; rosa/bucle/evidencia.py:158-230 (`acumular` en serie). Corrida 9 iteración 1: 8 conclusiones de 60 a 79 s (10:18 a 10:26, 4,36 USD) con evidencia nueva en 1 hipótesis; 7 de 8 con la misma entrada `afirmaciones` que la corrida 8; 8 comparaciones de 20.000 tokens; hip-mu2tskgf-2920 cambió de dirección tres veces sin evidencia nueva; 44 partidos sobre 25 pares, uno jugado 5 veces, 30 con una hipótesis descartada; hip-mu2zedte-898 (novena) conserva la conclusión de la corrida 7. Cuota de la iteración: 31 a 47 % del coste estimado; el cierre de la corrida 8 duró 15 minutos y dejó la iteración 2 sin margen. Tests en verificacion/evidencia-04, corrida-04, modelos-05, killer-05.

Impacto en llano. Un tercio del reloj y del coste de cada iteración se gasta en reescribir lo que no cambió; la dirección de las conclusiones oscila y se registra como "aprendizaje"; la iteración siguiente se omite por tiempo.

Arreglo propuesto. Huella de la evidencia (afirmaciones, veredictos, relaciones, supuestos, decisionKiller, retractaciones, resultado experimental) excluyendo partidos; reconcluir solo si cambia; quitar el tope `[:8]`; `asyncio.Semaphore(3)` para concluir y comparar; no rematch salvo evidencia nueva o tablas y agotar antes los pares no jugados; Bradley-Terry sin duplicados; emitir `ranking_cambio` solo si cambió el orden; el `terminadaEn` después del revisor. Esfuerzo: un día.

Lentes. evidencia-04 parcial media / parcial alta; corrida-04 confirmado alta/alta; modelos-05 confirmado alta; killer-05 parcial media/media. Elección: alta.

### S-14. Presupuesto agotado dentro del cierre: la tarea muere y el tick la relanza cada 2 segundos

Qué pasa. `_concluir_hipotesis` y la acumulación relanzan `PresupuestoAgotado`; `_cerrar_iteracion` y `correr_corrida` no lo capturan (solo `_ejecutar_paso` y `_proponer_plan` pausan); `_tick` relanza la tarea muerta sin espera ni incidencia.

Evidencia. rosa/bucle/corrida.py:656-657, :1405-1406, :1068 y :1077 sin try, :184-187 (`if t.done(): ... create_task`), :1248-1250 (`_permiso_presupuesto` no mira el tope de la iteración). Test: corrida con 366/1500 global y 447/447 de iteración: la corrida sigue "en_marcha", sin evento presupuesto, tres `_tick()` crean tres tareas que mueren, y cada vuelta añade 2 pistas y 2 escrituras de 17 MB al estado. Iteración 1 de la corrida 8: 350 de 447 antes del cierre, que necesitó 21 llamadas; con S-03 arreglado la verificación pasaría de 447. Tests en verificacion/corrida-03-reproducir y corrida-03-impacto.

Impacto en llano. La corrida se cuelga diciendo "en marcha", sin aviso de presupuesto, engordando el estado unas 1.800 pistas por hora y escribiendo 25 GB; el mismo relanzamiento ciego aplica a cualquier excepción no capturada del cierre.

Arreglo propuesto. `except PresupuestoAgotado` alrededor de las dos llamadas a `_cerrar_iteracion` con `_pausar_por_presupuesto`; precálculo del coste del cierre antes de entrar; en `_tick`, incidencia y retroceso (30 s, 60 s, 5 min) cuando la tarea murió por excepción; marca `_cierre` con lo ya calculado para no repetir resumen y llano al retomar. Esfuerzo: horas.

Lentes. corrida-03 confirmado alta/alta; corrida-08 confirmado media.

### S-15. Trampa del tope por iteración: el aviso culpa al tope global y ampliar no lo levanta

Evidencia. rosa/modulos/contador.py:52-58 corta por `it["presupuesto"]["limite"]` sin decir cuál; rosa/bucle/corrida.py:1789-1796 siempre escribe "Presupuesto global agotado ({limiteLlamadas} llamadas)"; rosa/estado/acciones.py:116-129 y frontend/src/datos/acciones.ts:146-158 `ampliar_presupuesto` solo tocan `limiteLlamadas`; `reanudar_corrida` (:92-97) solo acepta "pausada". Test: pausada con "global agotado (1500)" llevando 400; ampliar a 2000 -> en_marcha -> primera llamada corta -> pausada otra vez con el mismo texto. Uso real 350/447 y 321/447; con las 174 y 142 afirmaciones bloqueadas por S-03 pasando al juez, 3 de las últimas 4 corridas habrían saltado. Caso borde: denegar el permiso deja `limite = usado`; si `usado == 0`, `limite` 0 no corta. Tests en verificacion/corrida-05.

Impacto en llano. Un aviso falso y un botón que promete y no cumple; la única salida es detener la corrida y perder la iteración. Está acoplado a S-03: arreglar el patrón de citas hace aflorar este fallo.

Arreglo propuesto. `presupuesto_ok` devuelve qué tope cortó; el mensaje dice "la iteración N gastó sus 447 llamadas"; `ampliar_presupuesto` sube también el límite de la iteración abierta (misma regla en acciones.py y acciones.ts, con el espejo mapeando `iteraciones`); `pres.get("limite") is not None` en el contador; quitar "o reanuda" del mensaje de denegación. Esfuerzo: horas.

Lentes. Confirmado y parcial, alta las dos.

### S-16. hipotesisNuevas cuenta por número de iteración y el resumen en llano confunde nuevas con cola

Qué pasa. `hip_nuevas` filtra por `h["iteracion"] == it["numero"]` sin mirar la corrida; ese filtro alimenta la métrica, el resumen técnico, el llano, el informe y el registro que lee el revisor. Las firmas del resumen y del llano solo reciben las nuevas y se les pide "qué hay en la cola"; `estado_hipotesis` lleva solo la etiqueta del Killer, y el modelo inventa el motivo.

Evidencia. rosa/bucle/corrida.py:1378, :867, :1339, :1382, :1395; rosa/revisor_registro.py:180 y :250; rosa/modulos/firmas.py:439-447 y :488. Estado: las 9 hipótesis nacieron el 15/09; las corridas 4 a 10 dan hipotesisNuevas 3 y 2 (métrica 5) con 0 nacimientos reales; 27 de 35 iteraciones escriben "Quedan en cola N" con N igual a las "nuevas"; it-mu5kkbc2-11205 dice "las dos hipótesis suspendidas ... porque se agotó el tiempo" cuando el motivo real del Killer es sesgo o fuente primaria; 26 hallazgos del revisor repiten esta contradicción, todos abiertos. Frontend/src/componentes/Rosa2018.tsx:2605 tiene incluso el texto de descarte "El revisor confundio hipotesis en cola con hipotesis nuevas". Tests en verificacion/corrida-02, rigor-02.

Impacto en llano. El texto pensado para que la persona entienda sin leer el detalle le da un recuento falso de la cola, un motivo inventado y hipótesis viejas como nuevas, en cada iteración de las corridas 7 a 9; y el juez gasta una llamada por iteración en señalarlo.

Arreglo propuesto. Una función `hipotesis_nacidas_en(e, inv_id, it, hasta)` por ventana `creadaEn` usada en los seis sitios; entrada `cola` por regla (título, estado, decisión y motivo real del Killer desde `decisiones`) para ResumirIteracion y ExplicarEnLlano; frase de recuento generada por regla que el modelo no toque; comprobación determinista en el revisor que compare "en cola N" (número en cifra o letra) con el estado; recalcular `progreso` y `metrica` de las corridas 7 a 9; retirar las 6 lecciones fantasma. Esfuerzo: horas.

Lentes. corrida-02 confirmado alta/alta; rigor-02 confirmado alta/alta.

### S-17. El estado entero por mutación y por SSE

Qué pasa. Cada `mutar` serializa las 40 claves del estado (17 MB con privadas), escribe la fila entera en SQLite y lo hace en el hilo del bucle de eventos bajo el mismo cerrojo que usa la instantánea; cada versión empuja por SSE la instantánea completa (10 MB) a cada suscriptor, serializada una vez por cliente; el reloj (cada 10 s en marcha, cada 2 s en espera humana desde 8a4eb64) y el contador de llamadas (una mutación por llamada al modelo) son la mitad de las mutaciones; las claves privadas de corridas terminadas (7,4 MB, 39 %) se reserializan en cada mutación aunque no cambien; `resincronizar` cierra y reabre el flujo aunque esté sano.

Evidencia. rosa/estado/almacen.py:124-135, :151-192, :139-144 (instantánea bajo `_lock`); rosa/modulos/contador.py:138; rosa/bucle/corrida.py:199-220, :1830-1845; rosa/servidor.py:291 y :306 (`json.dumps(estado_de(request))` por cliente, `ensure_ascii` por defecto, sin GZip); frontend/src/datos/almacen.ts:122-129 (sustituye el estado entero), :278-292 (`resincronizar` termina con `abrirEventos()`), :397-405 (GET más primer SSE: 20 MB al abrir). Medidas: `_serializar` 71 a 92 ms, mutación completa 100 a 180 ms, instantánea 26 ms bajo cerrojo, `json.dumps` 25 a 35 ms; 776 a 996 mutaciones por iteración (llamada_modelo 37 %, tick 21 a 47 %, pista 18 %); un tick que solo cambia `segundos` escribe 20 KB al WAL, pero cualquier mutación que cambie la longitud reescribe 17 a 18 MB (unos 12 GB por hora en marcha); SSE en fase activa: 41 empujes y 443 MB en un minuto para una pestaña; GET /api/estado 0,09 s en reposo y 3,4 s bajo carga; `busqueda.excluidos` 2,1 MB (22 % del estado) sin ningún lector en la interfaz; versiones de artefactos 1,5 MB. Scripts en verificacion/estado-02, estado-03, estado-04, estado-05, servidor-02, frontend-02, frontend-07.

Impacto en llano. ROSA2018 gasta del orden del 5 % del tiempo del proceso (37 % en los minutos pico) serializando el mismo estado, escribe unos 100 GB al SSD por jornada, y una pestaña abierta recibe 4 a 7 MB por segundo. Es el techo duro para que la médica vea ROSA2018 desde fuera del Mac y el motivo de que la interfaz se sienta pesada. Crece con el estado (17 MB hoy, +3 MB en dos horas de corrida).

Causa. Persistencia y difusión de instantánea completa por mutación; reloj y contador modelados como mutaciones normales.

Arreglo propuesto, por orden de coste. Horas: (a) no mutar por reloj ni por espera humana (marcas `esperaDesde` en las transiciones; `gasto.segundos` solo al cerrar iteración; el frontend ya interpola); (b) el contador acumula en memoria y vuelca con la siguiente mutación real, manteniendo `presupuesto_ok` sobre el valor en memoria (la tabla `llamadas` ya guarda cada llamada); (c) caché de la instantánea pública por versión compartida entre clientes, calculada en `to_thread`, con `ensure_ascii=False`; no reenviar el estado al abrir el SSE si el cliente trae la versión; no repetir la misma versión; `resincronizar` separado de "reabrir flujo"; (d) GZip para /api/estado y assets. Días: sacar `_fuentes`/`_afirmaciones` a una tabla por corrida escrita solo cuando cambia; persistir por clave de primer nivel; SSE con `{version, cambiaron}` y fusión por clave en el cliente, resincronización completa al perder una versión. Esfuerzo: varios días; los cortes de horas quitan el 70 % de las mutaciones.

Lentes. Siete verificaciones: alta en estado-02 (reproducir; impacto media), estado-03 (reproducir alta; impacto media), estado-04 (reproducir alta; impacto media), servidor-02 (alta/alta), frontend-02 (alta/alta); media en estado-05 y frontend-07. Elección: alta, por el techo para varias personas y el crecimiento sin freno.

### S-18. Un CSV de laboratorio llamado sintético cuenta como evidencia directa

Evidencia. rosa/bucle/corrida.py:756-758 `"clase": "observacion_original", "sintetico": False` fijos; el endpoint POST /api/hipotesis/{id}/datos (rosa/servidor.py:545-561) y `subirDatosExperimento` (frontend/src/datos/almacen.ts:552-565) no admiten la bandera que sí tiene `subir_dataset` (servidor.py:565 y :594); rosa/certeza.py:89 CLASES_DIRECTAS, :428, :540-556. hip-mtvulxbg-140: afirmación con cita "[Datos del laboratorio: datos_gfap_nfl_sintetico.csv, 11/09/2026]", `sintetico: false`; `certeza.techo(h)` devuelve ("moderada", "hay evidencia directa (análisis sobre datos reales)..."); con la bandera correcta, "baja" o "muy_baja". La conclusión guardada aún no tiene techo (anterior a la regla), así que el texto falso aparecerá al reconcluir. Con el código actual, un CSV de humo clasificado como apoyo_reproducido crearía además un hecho "sabido" de origen laboratorio en el modelo de mundo (corrida.py:760-766). Tests en verificacion/evidencia-02, rigor-07.

Impacto en llano. La regla "nunca sintéticos" se salta por la vía del laboratorio; en una demo con datos de prueba una hipótesis parece un nivel GRADE más sólida y la escalera pide algo que no existe.

Arreglo propuesto. Casilla obligatoria "datos reales / de prueba" en la ficha y `sintetico` en el endpoint y en los dos reducers; regla defensiva por nombre (/sint[eé]tic/); en `_evaluar_resultado`, sintético implica `sintetico: True`, `evidenciaEstadistica no_aplica`, sin hecho en el modelo de mundo; migración para la afirmación existente y reconclusión de hip-mtvulxbg-140 por regla. Esfuerzo: horas.

Lentes. evidencia-02 confirmado alta/alta; rigor-07 confirmado media. Elección: alta.

### S-19. ROSA2018 muestra el doble del coste real

Evidencia. rosa/config.py:69-73 `{"openai/gpt-6-astra": (5.0, 20.0), "anthropic/claude-opus-5": (15.0, 75.0), "anthropic/claude-sonnet-5": (3.0, 15.0)}`; rosa/modulos/contador.py:114-130 lee solo prompt_tokens y completion_tokens aunque el mismo `usage` trae `cost`, `market_cost` y `gateway_cost` (1.980 de 2.075 trazas de GEPA lo traen). Ajuste por mínimos cuadrados sobre las trazas: Sonnet exactamente 2/10 USD por millón, Opus exactamente 5/25, GPT-6 Astra 11,8/52 (no lineal, caché de entrada). Corrida 8: 26,79 USD en el estado, 12,71 facturados; corrida 7: 19,16 frente a 10,75; corrida 12 en marcha: 55,83 estimados frente a unos 26 reales, con presupuesto de misión 60 (rosa/bucle/corrida.py:1891-1893 compara por corrida, no por investigación). Análisis en verificacion/modelos-02.

Impacto en llano. Todas las cifras de coste (corrida, dossier, decisión, peldaños por dólar, GEPA) están infladas en torno a 2x; el tope de 60 USD corta a los 30; y el diagnóstico de dónde ahorrar sale invertido (por token real, GPT-6 Astra es el caro y Opus el barato).

Arreglo propuesto. Usar `float(uso["cost"])` cuando venga y caer a la tabla solo si falta; columnas `usd` y `usd_es_real` en `llamadas`; tabla de respaldo actualizada con fecha y nota; marcar `gasto.usdEsEstimado` en corridas viejas y rellenar desde trazas.db las 6 a 12 de inv-mu2sz2ns-3; distinguir "facturado" de "estimado" en la interfaz; decidir si el presupuesto de la misión es por corrida o acumulado. Esfuerzo: horas.

Lentes. Confirmado y confirmado, alta las dos.

### S-20. La caché de DSPy está activa: réplicas y examen de GEPA devuelven la misma respuesta

Evidencia. rosa/gateway.py:41-44 `dspy.LM(...)` sin `cache=False` ni `rollout_id` (DSPy 3.3.1, `cache=True` por defecto; ~/.dspy_cache 101 MB); :63 `replica=lm(JUEZ, temperature=1.0)` con docstring "lecturas distintas"; rosa/bucle/corrida.py:920-955 `_replicar_paso` con entradas idénticas por trayectoria; rosa/gepa_continuo.py:761-765 "dos lecturas" con el mismo juez y la misma entrada; rosa/modulos/contador.py:119-149 suma los aciertos de caché a `gasto.llamadas` y `presupuesto.usado`. Test: tres trayectorias a temperatura 1,0 producen una llamada real y tres veredictos idénticos con `cache_hit`; `lm.copy(rollout_id=k)` sí produce lecturas distintas. En la tabla `llamadas`, 487 de 5.505 con 0 tokens y 0 a 3 ms (aciertos). Además `_replicar_paso` cuenta "juez no respondió" como "contradice" (corrida.py:938-949). Ninguna hipótesis tiene replicación ni GEPA ha cerrado ciclo: es latente pero el botón existe con 5 trayectorias. Tests en verificacion/modelos-03.

Impacto en llano. La ficha diría "5 de 5 trayectorias sostienen" con una única lectura real; la tolerancia al ruido que GEPA-CONTINUO.md promete no existe; y el presupuesto cuenta llamadas que no salieron.

Arreglo propuesto. `Ctx.llamar` acepta `rollout_id` y usa `lm.copy(rollout_id=n)`; `_replicar_paso` pasa el número de trayectoria; el examen de GEPA usa dos jueces con rollout_id 0 y 1 (y `temperature` explícita); el contador detecta `cache_hit` y lo registra aparte sin sumarlo al presupuesto; una trayectoria con juez caído cuenta como "no comprobable", no como "contradice". No desactivar la caché globalmente (ahorra los repetidos legítimos). Esfuerzo: horas.

Lentes. Confirmado y confirmado, alta las dos.

### S-21. ROSA_TOKEN inerte, puerta sin verificar abierta y administrador por orden de llegada

Evidencia. rosa/servidor.py:140 incluye '/api/acceso/entrar_sin_verificar' en `publico`; :145 y :149 tienen las mismas condiciones, así que la guardia del token nunca se alcanza (probado: token correcto sin cookie da 401; puerta sin token da 200 con cookie de 12 h; con cookie, /api/estado sin token da 200); :121-123 `es_admin` = primera fila de `cuentas`; rosa/acceso.py:81-92 sin límite de tasa ni purga (300 POST crean 300 cuentas). Hoy escucha en 127.0.0.1 sin ROSA_TOKEN y `correoConfigurado:false`. frontend/src/datos/almacen.ts:44-54 ya manda el token. Tests en verificacion/servidor-03.

Impacto en llano. Sin daño hoy; el día que se exponga a la red del laboratorio confiando en el aviso de main.py:41-43, cualquiera del dominio inicia corridas, aprueba planes y, si entra primero, controla GEPA y el correo.

Arreglo propuesto. Mover la guardia del token delante de la de sesión y sin excepciones para rutas públicas ni cookie; administrador por marca explícita (primera cuenta creada desde el propio equipo o ROSA_ADMIN), nunca una sin verificar; compartir límite de tasa y purga entre `solicitar` y `entrar_sin_verificar`; corregir main.py:42 y PENDIENTE.md:33. Esfuerzo: horas.

Lentes. Confirmado y confirmado, alta las dos.

### S-22. Sin roles y con la autoría dictada por el navegador

Evidencia. rosa/servidor.py:329-357 `accion()` acepta ~75 nombres para cualquier sesión; solo GEPA y correo comprueban `es_admin`; :374-377 sellar sin límite; :548-599 subidas de 200 MB. 32 reducers reciben `quien` del cliente (aprobar_plan, revisar_hipotesis, registrar_decision, eximir_puerta...); `accion()` nunca lo sobrescribe con `request.state.usuario`; frontend/src/datos/almacen.ts:107-108 `QUIEN = 'la persona responsable'` con el comentario "Cuando haya cuentas, sale de la sesion". La tabla `acciones` (almacen.py:42-51) no tiene actor; `_correoResponsable` solo se pone al crear entidades. Test: una segunda cuenta exime la puerta de reproducción firmando como "Dra. Suplantada" y el registro no contiene su correo. Test en verificacion/servidor-08.

Impacto en llano. Toda decisión de auditoría (aceptar, descartar, enmendar prerregistro, eximir puerta) queda firmada por un texto libre del navegador; con curl cualquiera del dominio firma con cualquier nombre. El registro encadenado prueba que la fila no se alteró, no quién la produjo.

Arreglo propuesto. En horas: en `accion()` sobrescribir `args["quien"]` con `request.state.usuario` para los reducers que lo aceptan (detectable con `inspect.signature`) y dejar de mandar `QUIEN`; columna `actor` en `acciones` dentro del hash. En días: roles lectura/decisión/administración por cuenta desde Ajustes; `es_admin` para iniciar corrida, presupuesto, autonomía, conectores y subidas; límite de tasa en sellar. Esfuerzo: horas más días.

Lentes. Reproducir confirmado alta (subida desde media por la autoría dictada por el cliente).

### S-23. Una decisión humana diferida 6 s se deshace en pantalla y puede perderse o duplicarse

Evidencia. frontend/src/datos/almacen.ts:122-129 (`recibirRemoto` sustituye el estado sin reaplicar pendientes), :172-212 (`MS_DESHACER = 6000`, envío en `setTimeout`), :372-383 (`ok === null` sin aviso ni reintento); sin `pagehide`/`beforeunload`/`keepalive` en src. SSE en corrida: mediana 1,2 s entre empujes (89 % de intervalos <= 6 s). Test con el almacén real: Aceptar -> "aceptada"; SSE a los 3 s -> "propuesta" con el aviso "Se envía en 3 s" todavía visible; POST a los 6,2 s. Segundo Aceptar produce dos POST y el servidor (rosa/estado/acciones.py:375-420) registra dos revisiones y dos DecisionRecord porque `version` no cambia al decidir. Tests en verificacion/frontend-01.

Impacto en llano. La médica ve deshacerse su decisión sin haber tocado Deshacer, puede decidir dos veces, y si cierra la pestaña en esos 6 s la decisión no llega jamás: es la pieza que gobierna el avance de las hipótesis.

Arreglo propuesto. Guardar en cada pendiente su reductor y reaplicarlas en `recibirRemoto`; oyente `pagehide` que envíe con `fetch(..., {keepalive: true})` y la cabecera X-ROSA2018 (sendBeacon no vale); aviso y reintento cuando `ok === null`; rechazar en los dos reducers una acción cuyo estado destino ya es el actual; o bien enviar al instante y hacer de Deshacer una acción compensatoria registrada. Esfuerzo: medio día.

Lentes. Confirmado y confirmado, alta las dos.

### S-24. La evaluación de criterios GEPA escribe acuerdo 0.0 cuando el juez no responde

Evidencia. rosa/bucle/corrida.py:406-420 `acuerdo_con`: `except Exception: continue` (traga también PresupuestoAgotado) y divide por `len(reservado)`; :1659-1676 `_fijar_evaluacion` pasa a "evaluado" si `casos` es truthy y a "revertido" (terminal) si empeora. Tests: juez caído en todo -> {'casos': 2, 'antes': 0.0, 'despues': 0.0}, estado evaluado, sin incidencia; juez caído solo en la segunda pasada -> criterio de la meta-campaña "revertido" con antes 1.0, después 0.5. Hoy latente (0 decisiones humanas registradas, las 3 evaluaciones con casos 0); aparecerá con la primera aceptación humana; cada evaluación son hasta 12 llamadas a Opus. Tests en verificacion/tests-02.

Impacto en llano. El registro que decide qué criterios del Killer se promueven o revierten acumula cifras que miden cuántas veces se cayó el gateway, y la reversión es irreversible.

Arreglo propuesto. Comparar solo sobre hipótesis juzgadas en las dos pasadas; si falta alguna, `antes`/`despues` None, `casos` 0 y nota "El juez no respondió en N de M"; relanzar PresupuestoAgotado; cortar la segunda pasada si la primera falló; "La evaluación falló" con tilde. Esfuerzo: horas.

Lentes. Confirmado y confirmado, alta las dos.

### S-25. El camino real del bucle no tiene ningún test

Evidencia. Trazado con `sys.settrace` sobre los 23 ficheros de test que importan el bucle: paso_literatura 0/37 líneas, paso_extraccion 0/10, verificar_afirmaciones 0/17, paso_verificacion 0/16, paso_modelo 0/23, paso_hipotesis 0/87, paso_novedad 0/99, paso_meta 0/10, correr_corrida 0/32, _permiso_presupuesto 0/41, _ejecutar_paso 0/36; `Supervisor` se instancia una vez en tests y nunca corre `correr_corrida`. El arnés de `_supervisor` (test_integracion_corrida.py:88) construye `programas` con 11 nombres frente a 38 reales, así que un paso que use un programa ausente lanza AttributeError que el propio paso traga y el test pasa sin probar nada (es lo que ocurrió con `relevancia` en S-02). Prueba de que el arnés sirve: un test de 110 líneas reutilizando `_preparar` y `Llamadas` corre literatura, extracción, verificación, modelo y cierre en 0,8 s (verificacion/tests-03-impacto/test_iteracion_completa_simulada.py) y habría cazado el filtro de S-16. 48 commits desde el 1 de septiembre tocan pasos.py o corrida.py sin un test de camino.

Impacto en llano. Cada cambio del bucle se valida gastando una corrida de 20 a 30 dólares y horas; las regresiones llegan por observación de Emir, no por la suite.

Arreglo propuesto. Mover el test simulado a rosa/tests/test_bucle_iteracion.py; `programas` con los 38 nombres reales para que un programa sin respuesta falle en voz alta; un caso por pendiente anotado (hipotesisNuevas 0, hecho duplicado, cita no resuelve solo sin texto, reloj con espera, iteración vacía sin llamadas, presupuesto en cierre); medir cobertura de pasos.py y corrida.py en cada commit. Esfuerzo: medio día el arnés, una o dos horas por caso.

Lentes. Confirmado y confirmado, alta las dos.

### S-26. Solo se extraen los 6 primeros fragmentos de cada fuente

Evidencia. rosa/bucle/pasos.py:1006 `for fr in frags[:MAX_FRAGMENTOS_POR_FUENTE]` (6, rosa/politicas.py:96) por posición; :440 guarda 14 páginas; :451/:469 12 secciones o trozos; :1008 recorta cada fragmento a 6.000 caracteres sin nota; :368-369 añade fragmentos a una fuente existente sin reabrir `extraida`. Estado: páginas citadas en todo el estado {1: 49, 2: 248, 3: 406, 4: 305, 5: 237, 6: 240} y ninguna 7 o mayor; 28 PDF con "14 páginas leídas"; en las secciones citadas de las hipótesis, 24 "Introduction" frente a 4 "RESULTS"; 104 de 112 datos en hipótesis sin n, comparador o efecto completos. Análisis en verificacion/extraccion-05.

Impacto en llano. La investigación, cuya pregunta es qué biomarcador predice beneficio clínico, se alimenta de introducciones y métodos y no llega a las tablas de eficacia.

Arreglo propuesto. Mantener 6 pero elegir cuáles: ordenar secciones JATS con Results/Findings/Outcomes primero, puntuar páginas de PDF por densidad de cifras y patrones de resultados, y si `reranker.disponible()` reordenar los 14 fragmentos contra las preguntas abiertas; trocear secciones largas en vez de cortar a 6.000; anotar en la pista qué fragmentos se leyeron; reabrir la extracción por fragmento al fusionar. Test con una fuente falsa de 14 páginas y las cifras en la 9. Esfuerzo: medio día.

Lentes. Confirmado y confirmado, alta las dos.

### S-27. La réplica de una hipótesis nacida en otra corrida falla siempre

Evidencia. rosa/bucle/corrida.py:226-235 construye el ctx con la última corrida; :920-938 borra `fragmento`, `localizador` y `fuenteId` de las copias y resuelve la cita en `ctx.fragmentos_verificador()` (solo `_fuentes` de esa corrida); `fid is None` cuenta como "contradice" (:938-948). Con las 6 fuentes reales de la corrida viva, las 11 citas de hip-mu35joen-2494 dan None, 0 llamadas al juez y "0 de 3 trayectorias sostienen". El botón (frontend/src/pantallas/Hipotesis.tsx:221 y 590) se habilita sobre esa corrida. Ninguna hipótesis tiene replicación todavía. Test en verificacion/extraccion-10.

Impacto en llano. Pulsar "replicar" hoy escribiría en el historial un resultado negativo sin haber leído nada, sobre las hipótesis que Emir deja en la cola.

Arreglo propuesto. Fragmentos de todas las corridas de la investigación; conservar el pasaje guardado y usarlo marcado como "no releído" con veredicto máximo parcial; contador `noComprobables` en los dos lados en vez de sumar a `contradicen`; mostrar antes de lanzar cuántas citas resuelven. Esfuerzo: horas.

Lentes. Reproducir confirmado, alta (subida desde media).

### S-28. Los artefactos guardan todas sus versiones con contenido completo

Evidencia. rosa/estado/acciones.py:1768-1778 y frontend/src/datos/acciones.ts:1774-1782 (`versiones.append` con `contenido`); el modelo de mundo art-mu2tf97x-1676 tiene 13 versiones de 37.593 a 129.712 caracteres (1 MB) porque diez corridas sobre la misma investigación reutilizan el mismo artefacto; `artefactos` pesa 2 MB (15 % del estado); rosa/espejo_convex.py:36 `MAX_BYTES_DOC = 900_000` ya recorta la versión vigente de 129.712 a 20.031 caracteres. Artefactos.tsx:21-22 y buscar.ts:39 sí usan el historial (diff, búsqueda). Análisis en verificacion/estado-10.

Impacto en llano. Historial que viaja en cada empuje SSE y se reescribe en cada mutación, y un espejo que hoy enseña un modelo de mundo al 15 %.

Arreglo propuesto. Contenido solo en la última versión y metadatos en las anteriores, con `GET /api/artefactos/{id}/versiones/{n}` para diff y búsqueda; misma regla en acciones.py y acciones.ts; no crear versión si el contenido es idéntico; en el espejo, recorte específico que conserve la vigente. Esfuerzo: un día.

Lentes. Reproducir confirmado, alta (subida desde media porque Convex ya trunca hoy).

## (d) Medios y bajos en lista compacta

Cada línea: id, qué pasa, dónde, arreglo en una frase.

Medios:

- M-01 Sesgo: NI cuenta como "algunas dudas" y tres dudas dan "alto" (rosa/sesgo.py:176-191); 2 de 5 fuentes son alto solo por falta de texto y el Killer suspende (rosa/killer.py:52). Arreglo: quitar la escalada por tres, no evaluar fuentes sin texto completo, quitar el bono "seguro" a preguntas de paso (1.1), mostrar cuántas preguntas fueron NI. No toca certeza (el techo estructural es lo que frena hoy).
- M-02 Juez por afirmación: 111 llamadas sobre 28 fragmentos en la corrida 8 (rosa/bucle/pasos.py:1116, firmas.py:1164). Arreglo: firma por fragmento con lista numerada, tope 8, "sin_verificar" para índices no devueltos; medir Predict frente a ChainOfThought con un conjunto etiquetado de afirmaciones (no existe hoy).
- M-03 Cohortes de ensayos: rosa/metodos.py:107-226 sin TRAILBLAZER, CLARITY AD, EMERGE, GRADUATE, Study 201; regla de tokens funde ALZ y ALZ 2 y separa ALZ 2 de ALZ2; pasos.py:1033 corta el NCT a 60 caracteres. Arreglo: catálogo de ensayos con NCT y alias, extraer NCT antes de recortar, no unir nombres que difieren solo en sufijo numérico.
- M-04 Cohortes en dos lados: frontend/src/lib/priorizacion.ts:105 (texto en minúsculas) frente a rosa/priorizacion.py:141 (catálogo) y rosa/certeza.py:389 (filtrada); Killer y dossier usan la no filtrada. Arreglo: el servidor escribe `cohortesDistintas` en la hipótesis y la interfaz la lee; una sola función canónica.
- M-05 Métrica fidelidad: pasos.py:1163 convierte None en 0 (métrica 1789487589339 con 10 cita_no_resuelve y "0 %"); `sinVerificar` es recuento y Calidad.tsx:134 lo pinta como porcentaje. Arreglo: null y "sin juzgar", campo `juzgadas`.
- M-06 Escala del juez: firmas.py:597 "muy baja si no hay evidencia directa" frente a certeza.py; el juez no ve el techo; 7 de 9 conclusiones "sin evidencia directa" con 6 a 14 sostenidas (todas indirectas). Arreglo: reescribir la descripción en términos GRADE, techo consciente de la indirectez, peldaño que nombre los factores reales, frase plantilla que distinga "nada" de "solo indirecta".
- M-07 Dirección mixta: corrida.py:627-641 guarda la dirección del juez sin cotejarla con los recuentos; 3 hipótesis "contradictoria" con 0 en contra; las afirmaciones de origen nunca pasan por AsignarEvidencia. Arreglo: dirección por regla con supuestos contradichos incluidos, `direccionDelJuez` aparte, variante de frase para "supuesto contradicho".
- M-08 Hechos duplicados: pasos.py:1233 (texto exacto) y :1255 (dos entidades más 40 caracteres); 9 grupos de casi duplicados; copiar_hechos (acciones.py:1502, acciones.ts:1689) hereda sin fundir; 333 de 381 hechos sin `afirmacionIds`. Arreglo: `cuestiones.equivalencia` más misma referencia, fundir sumando procedencia, fundir al heredar, migración de enlaces donde queden afirmaciones.
- M-09 Candidatas 72: evidencia.py:44-45 y :121; el coseno 0,30 lo pasa el 98,9 % de los pares; el filtro por términos perdería 34 de 38 aceptadas. Arreglo: llamadas en paralelo, anotar `no_pertinente` por hipótesis, memoria de candidatas ya juzgadas, usar el `Indice` con hash.
- M-10 Introducciones: certeza.py:305-364 no mira sección ni `nivelMedicion`; 47 % del peso a favor en 11 hipótesis; en 2920 y 5871 descontarlas baja el techo de baja a muy_baja. Arreglo: factor `seccion` 0,3 para Introduction/Background detectado en la cita (el localizador no viaja a la hipótesis), sin aportar cohorte; no penalizar `interpretacion_autor` a ciegas (etiqueta ruidosa); recalcular por regla sin juez.
- M-11 Revisor de registro: revisor_registro.py:230-268 recorta a 9.000 por el final (FUENTES, CONSULTAS y EJECUCIONES no llegan en iteraciones con más de ~10 afirmaciones), :178 lee `_iteracion` que nadie escribe, :177 no admite las verificadas, :33 `_EJECUCION` casa negaciones, :264-267 mezcla ámbitos, :248 sin certeza. 95 hallazgos abiertos; hoy el bloqueo `revision_registro_abierta` no cambia la candidatura (ninguna tiene Killer avanzar), pero enseña "hallazgo grave sin atender" en 14. Arreglo: presupuesto por sección, filtrar por iteración, negación en la regla, certeza en el registro, subir `maximo` a 30.000 de inmediato, descartar desde la pantalla los tres "alta" falsos de it-mu5mk7f5-4326.
- M-12 Datos controlados: experimento.py:202 y datasets_programa.py:68 son listas distintas sin BIOCARD; experimento.py:598 solo avisa y ninguna hipótesis tiene `problemasContrato` (el validador es posterior a todas); 11 hipótesis piden acceso a ADNI; el detector marca los descargos. Arreglo: lista única en politicas.py, detector de "pide" frente a "menciona" con negación hacia delante, bloqueo levantable por la persona, reformulación con datos públicos, migración sobre las 28.
- M-13 Pasaje: verificador.py:143-147 tolera la ventana que falla, incluida la última; cola o cabeza de hasta 5 palabras inventadas pasan a cualquier longitud; el fragmento del extractor viaja al Killer, a hechos y a la ficha como "literal". Arreglo: exigir primera y última ventana, normalizar puntuación, guardar el tramo real de la fuente, misma regla en `fragmento_en_pagina`.
- M-14 Conclusiones obsoletas: corrida.py:604 es el único sitio que calcula el techo; 19 de 28 sin techo; hip-mu1k00ml-52 con "baja" sobre un techo actual "muy_baja"; `_migrar_conclusiones` no las toca. Arreglo: recálculo por regla de techo, escalera y `min(juez, techo)` al arrancar y al cerrar, reutilizando los factores guardados, con evento cuando baje.
- M-15 Novedad del campo: pasos.py:551 sin fecha en la cadena y :573 filtra por cadena exacta de toda la investigación; una vez en 149 consultas. Arreglo: clave (tema, desde_fecha) por corrida, ventana desde la última novedad, nota cuando se omite.
- M-16 PRISMA: prisma.py:60 espera `traidos` por consulta que nadie escribe (duplicates 0), pasos.py:757 borra excluidos por encima de 600, prisma.py:145 y :183 recortan a 300 y 120 con encabezado engañoso; repetidos contados como cribados. Arreglo: duplicados por clave, compactar en vez de borrar, encabezado honesto, un test de prisma (no hay ninguno).
- M-17 Cribado repetido: pasos.py:898 lanza las consultas en paralelo y cada una consulta `_excluidos_previos` al empezar; 22 recribados por paralelismo con el código vigente; "título:" con tilde frente a "titulo:" (:128 y :143) deja pasar títulos genéricos como "official title:" y excluye documentos distintos. Arreglo: diccionario compartido por paso antes del reranker, mirar `_fuentes`, corregir la constante, semáforo global.
- M-18 Ventana de 40: contexto.py:546 y firmas.py:236 dice "todas las corridas"; `relevantes` es None en las corridas 1 a 5; las lecciones no acumulan por patrón. Arreglo: resumen agregado por nombre propio y base, "no medido" distinto de 0, lección por patrón.
- M-19 Marcas del Killer: pasos.py:2062-2066 quita la marca solo si la versión no cambió (cualquier reformulación deja la petición viva: doble juicio, hallazgos y "Decide tú" duplicados en 2494); novedad "no comprobado" suspende y al comprobarse pide otra revisión (doble pasada por construcción en 4 hipótesis); un "avanzar" posterior no devuelve la hipótesis a propuesta ni cierra el hallazgo de descarte; "Decide tu." sin tilde. Arreglo: el Killer quita la marca al juzgar la versión actual, novedad dentro del paso de hipótesis, rama avanzar restaura estado y atiende hallazgos, no duplicar hallazgos abiertos.
- M-20 Iteración por corrida: evidencia.py:310 resta números locales (una semilla del vivero nunca se retira entre corridas), torneo.py:95 y Ranking.tsx:24 dibujan el Elo con x que retrocede, Hipotesis.tsx:559 "Iteración" sin corrida, semillas de emparejamiento repetidas. Arreglo: `corridaNumero` junto a `iteracion`, contador de paciencia en la semilla, gráfica por índice de punto.
- M-21 Dirección con contras: killer.py:371 y :85 no miran `relacion`; una afirmación "contradice" enlazada por la amplitud pone `direccion_evidencia` en falla y REFORMULA; hoy 0 contras, se disparará al buscar en contra. Arreglo: predicado compartido con `apoyos_existentes` (evidencia.py:75), contras informadas aparte, inconsistencia para GRADE. Hacerlo antes de activar el rejuicio automático.
- M-22 Medidores: conjuntoDorado 0 casos, 0 decisiones etapa persona (los criterios de GEPA quedan "sin conjunto reservado", ya ocurrió dos veces hoy), panel del 11/09 anterior a 25 commits del Killer, `caida_de_acuerdo` sin llamador, 126 criterios de nivel 2 sin evaluación posible. Arreglo: migrar las revisiones humanas, mínimo de casos con aceptadas y descartadas antes de evaluar, conectar `caida_de_acuerdo`, panel con el caso "supuesto ajeno".
- M-23 Pasos sin trabajo: corrida.py:1311-1316 marca hecho con "No hay fuentes nuevas" (6), "Nada pendiente de verificar" (6), "0 ensayos" (5); el análisis sin datasets se borra del plan (corrida.py:1189). Arreglo: excepción `SinTrabajo` y estado `sin_trabajo` en los dos lados, que entre al traspaso.
- M-24 Espejo Convex: espejo_convex.py:87-94 hash sobre la corrida completa incluido el reloj (233 kB cada ~9 s), :131-133 escaneo bajo el cerrojo (85 ms), :189-194 sin reintento, 14 claves omitidas (solicitudes, cuestiones, lecciones...). Arreglo: excluir campos volátiles del hash con fila `reloj` aparte, reintento exponencial, instantánea cacheada, test de cobertura de claves.
- M-25 GEPA continuo: gepa_continuo.py:330-332 exige tres investigaciones (todas las trazas son de una), :641-647 no retiene mientras haya corrida viva; trazas.db 46 MB y creciendo 40 MB al día, prompt guardado dos veces; GEPA-CONTINUO.md:40 y :81 contradicen el código. Arreglo: nota "faltan N investigaciones", retención con temporizador propio, prompt renderizado solo una vez, ciclo manual con aviso de fuga.
- M-26 Apagado: main.py:91 sin tope; `asyncio.run` espera 300 s y el intérprete une los hilos sin límite; el sandbox (ejecucion.py:351, hasta 210 s) y el ciclo GEPA escriben en un almacén cerrado; uvicorn entrega la señal al supervisor después de soltar el puerto; el proceso vivo tiene PPID 1. Arreglo: `abortar_todo()` de contenedores en `parar()`, comprobar parada en la métrica de GEPA, `Almacen.cerrar` marca cerrado, cerrojo de S-01, `kill -9` con espera acotada en rosa.sh.
- M-27 content-filter: LiteLLM mapea 'content-filter' a 'stop' (core_helpers.py:201-206) y ROSA2018 no mira `native_finish_reason`; 8 filtros del juez hoy, cada uno con un reintento de ~21k tokens; el disparador real del reintento en `comparar` es que Opus escribe `Comparacion(eje=...)` como constructor Python (ChatAdapter falla, cae a JSON, el gateway filtra la salida estructurada); una respuesta cortada por `length` sí puede decidir un partido; pasos.py:262 convierte un error de parse en "modelo_bloqueado". Arreglo: leer `provider_specific_fields.native_finish_reason` en el contador, columna `finish_reason`, `RespuestaIncompleta` para `length`, aplanar `Comparacion` en campos escalares, clasificar por tipo de excepción.
- M-28 Observabilidad: 0 logging, 66 print, log en el scratchpad truncado en cada reinicio, `/api/salud` con sesión y sin bucle; MLflow (376 MB) traza modelos pero no excepciones ni corrida. Arreglo: logging rotado con hora, corrida e iteración desde `contexto_actual`; incidencias en el estado cuando muere una tarea; `/api/salud` pública con edad de la última mutación y estado del supervisor; etiquetar trazas MLflow; poda.
- M-29 Cuerpos: servidor.py:336 lee todo antes del 413 (300 MB aceptados, RSS de 63 a 348 MB); `/preguntar` (:618) sin tope (RSS a 914 MB), con `quien` del cliente y contador diario en memoria. Arreglo: lector acotado por trozos y por Content-Length en todas las rutas, `quien` de la sesión, contador desde `preguntasABases`.
- M-30 Red caída: corrida.py:1311-1324 marca "fallido: LMTransportError" y la iteración sigue (resumen, revisor y lecciones sobre pasos que no ocurrieron; lecciones.py:76 aprende de una caída de red); pasos.py:100 tope único de 600 s con 7 conexiones de reintento por debajo (num_retries 3 x max_retries 2) y contado como trabajo. Arreglo: capturar `LMTransportError`/`LMTimeoutError`/`LMServerError` como `GatewayNoDisponible`, estado `pausada_por_red` en los dos lados con sonda, topes por programa (Killer legítimo de 314 s), `num_retries=0` y `max_retries=0` en gateway.lm, descontar el tiempo colgado, no generar lección por infraestructura.
- M-31 Amplitud: pasos.py:644-645 manda `hipotesis_vivas` (11.188 caracteres, 5 líneas GRADE por hipótesis) en las 72 llamadas por artículo, sin caché de prefijo en el gateway (precio lineal). Arreglo: `hipotesis_para_cribado` compacto (~1.300 caracteres) sin tocar la firma; lo mismo con `preguntas_abiertas` en foco.
- M-32 enmendarLectura: acciones.ts:1013-1043 no toca `hashLecturas` (test lo fija) y acciones.py:1294-1296 lo sobrescribe (test lo fija al revés); forma de la enmienda distinta; Rosa2018.tsx:2485 enseña como "congelado" el hash nuevo; camino muerto en Rosa2018.tsx:2274-2298. Arreglo: elegir la regla del frontend (hash congelado intacto, `hashLecturasActual` aparte), igualar la forma, test de paridad, borrar el camino muerto.
- M-33 Reducers espejo: acciones.ts:1222-1230 sella `retraccionComprobadaEn` y escribe "recomprobadas contra Crossref: sin cambios" sin consultar nada (en modo muestra queda para siempre); :187-197 no aprueba misión ni pregunta; :402-466 no registra decisión ni recalcula bloqueos; :488-497 inventa "revisada sin hallazgos nuevos"; progreso.ts omite `frase_acierto`. Arreglo: los reducers optimistas registran la petición, no el resultado; la simulación del modo muestra vive en simulacion.ts; test de eventos en los dos lados.
- M-34 Tildes: los dos scripts escriben por defecto (acentuar.py:457-463, acentuar_py.py:132-147); el diccionario acentúa sustantivos con forma verbal (termino, reintento, reparo, recargo...) y ya introdujo "pistas término" (corrida.py:1311, simulacion.ts:429) y "reintentó" (Correo.tsx:9, simulacion.ts:83); la regla `_ESTA` con "list" propone "de está lista" en firmas.py:214 (un prompt); acentuar_py.py corrió sin `--seco` durante la verificación y modificó cuatro ficheros (revertidos; identificadores PROV y de afirmación acentuados); textos del backend sin tilde llegan al estado ("Se cumplio" 10, "Apruebala" 4, "extraidas de" 22, "(1 horas)"); el script del frontend no ve backticks en datos/ ni lib/ (46 plantillas pendientes) ni comillas dobles. Arreglo: defecto solo comprobar, lista de ambiguas con test, quitar "list" de `_ESTA`, corregir a mano los errores de sentido y las líneas del backend (con "falló"/"fallo" decidido a mano), plantilla de backticks en .ts, test AST de literales prohibidos, excluir identificadores con guion o dos puntos, corregir la orden de CLAUDE.md y de la memoria.
- M-35 Bundle: App.tsx:20-31 importa las doce pantallas; 974 KB en un chunk (react-dom 13 %, motion 14 %, Rosa2018 11 %, muestra y simulación 8 % cargados siempre); servidor.py:693-703 sirve assets sin gzip ni Cache-Control (974 KB en el cable). Arreglo: GZipMiddleware y `immutable` en assets; `import()` para muestra y simulación; lazy solo para Arbol y Calidad; manualChunks para react y motion.
- M-36 Veredicto desconocido: priorizacion.ts:39 y otros nueve sitios (hipotesis.ts:77, calidad.ts:25, evidencia.ts:106, exportar.ts:80, Trazabilidad.tsx:182, Verificacion.tsx:51...) indexan `VEREDICTO[...]` sin guarda; `CERTEZA_EVIDENCIA[...]` en Hipotesis.tsx:82 y EnLlano.tsx:140-187 igual; un veredicto nuevo tumba Cola, Ranking, Trazabilidad y exportación (Limite.tsx). Arreglo: accesores `veredictoDe`/`certezaDe` con respaldo bloqueante-no-comprobado, test adversarial, test en Python que compare el conjunto de veredictos con las claves de etiquetas.ts.
- M-37 CI: sin .github, hooks, pre-commit, mypy ni ruff; el commit 2190550 (14/09, 15:33) no compilaba (`Cannot find module '../componentes/Correo'`) y estuvo 7 minutos en origin/main; el árbol de trabajo sí compilaba (fichero en disco, no en el índice), así que un hook sobre el árbol no lo habría visto. Arreglo: GitHub Actions en clon limpio (pytest, vitest, tsc, eslint, secretos, tildes en modo comprobar); hook pre-commit que exporte el índice (`git write-tree`) y escanee `git diff --cached` con la regex `_SECRETOS` de gepa_continuo.py:53 movida a scripts/.
- M-38 Excepciones tragadas: 138 `except Exception`, 14 con solo pass o continue (contexto.py:605, corrida.py:415, pasos.py:830/1065/1472/2174/2180/2418, conectores/base.py:106, datasets_programa.py:1201, acciones.py:1627, gepa_continuo.py:298/646, lecciones.py:157); un `usage` con otras claves da coste 0 sin entrar al except (`.get(..., 0)`). Arreglo: `logger.warning(exc_info=True)` en los 11 que no son respaldo de respaldo, contadores de fallos donde se deriva un dato (novedad, acuerdo, gasto), lint AST con lista blanca.
- M-39 Operación: rosa.sh:7 exige .env, gateway.py:34-37 mata el proceso sin clave, config.py lee 12 variables del entorno, sin recarga ni versión visible, `/api/salud` con sesión, procesos huérfanos de Vite de días anteriores; frontend/dist sí se sirve desde el 8765 (servidor.py:692-703), pero rosa.sh:24 abre el dev server. Arreglo: `/api/version` público (commit, arranque, hash de dist), acción "reiniciar cuando no haya corridas vivas" con launchd que relance, claves opcionales desde Ajustes, arranque perezoso de modelos que pida la clave por pantalla, rosa.sh abriendo el 8765.
- M-40 Código: crear_app 620 líneas (servidor.py:86-705) con endpoints como closures; corrida.py:402-413 rehace el Killer con reglas YA divergentes de pasos._killer (sin filtro "no falsable", versión fija a 1, sin sesgo, sin "juez no respondió", traga PresupuestoAgotado); el mismo bucle de relevancia en pasos.py:824 y :2412 ("demostro" sin tilde); imports perezosos de un símbolo privado sin ciclo real. Arreglo: `decidir_hipotesis` compartida (horas), `puntuar_relevancia`, exportar `fuente_publica`, routers al final.

Bajos:

- B-01 Reloj de pared: resuelto en 8a4eb64 (corrida.py:1820-1845 `tiempo_trabajo_ms`, `contabilizar_tiempo`); restos: "pausada_por_presupuesto" fuera de `ESTADOS_DE_ESPERA_HUMANA` (:1817, una espera humana de 61 min cierra la corrida "por tiempo"), el supervisor puede cargar a `pausaMs` un await largo suyo, y Corrida.tsx:638-646 pinta tiempo de pared (`Math.max`). TRASPASO.md:589-594 sigue marcándolo pendiente.
- B-02 Hueco del plan: corrida.py:1151 comprueba la parada antes de las llamadas del plan (110 a 136 s), pero la iteración se crea igual si el tope vence durante la llamada y `_permiso_presupuesto` puede abrir una solicitud antes de mirarla; el cierre vacío ya no llama a nada (8a4eb64). Arreglo: reevaluar la parada dentro de la mutación que crea la iteración y antes de `_permiso_presupuesto`.
- B-03 Vivero vacío: el generador devolvió `hipotesis: []` en las tres corridas con traza porque la firma (firmas.py:313-326) le dice "si encajan, no proponer nada" y "preferir dos cohortes"; el razonamiento identifica ideas de una cohorte (Spurrier, protofibrillas) y las calla; la deduplicación silenciosa de pasos.py:1997 nunca ha actuado. Arreglo: anotar el razonamiento cuando la lista sale vacía, pedir en la firma que las ideas de una cohorte sí se devuelvan para el vivero, test de integración.
- B-04 a B-28: ver la tabla; sin verificar salvo B-01 a B-03 y B-21 (ya anotado).

## (e) Plan sugerido (nada ejecutado)

Dependencias marcadas con "requiere". Todo lo de la primera tanda cabe en horas cada pieza y no toca reglas del proyecto.

Tanda 1, esta semana (lo que engaña o tira evidencia):

1. S-03 patrón de citas más resolución por fuenteId (cubre S-04) y test cruzado de localizadores. Después el script de reverificación de las 875 bloqueadas, presupuestando el juez. Requiere hacer antes S-15 (trampa del tope por iteración), porque las afirmaciones recuperadas empujan la verificación por encima de 447; y conviene M-02 (juez por fragmento) en la misma pasada para que el coste no se triplique.
2. S-02 novedad: consulta en inglés con entidades, `no_comprobado` con 0 obras o modelo caído, migración de las 16 hipótesis, `fusionar` sin "pasa" de memoria para novedad; arnés de tests con los 38 programas. S-11 (novedad al reformular) va en el mismo cambio.
3. S-01 cerrojo de fichero, UPDATE condicional por versión, apagado que deja terminar la llamada en vuelo, reanclaje documentado de la cadena y verificación que distingue bifurcación de manipulación. Requiere `al.cerrar()` en tres tests.
4. S-19 coste real desde `usage.cost`; S-20 `rollout_id` en réplica y examen de GEPA, aciertos de caché fuera del presupuesto. Ambos independientes.
5. S-09, S-10, S-12 en el Killer: fallo del juez sin decisión, `supuestos` de DESCARTAN a SUSPENDEN con índice validado, auditoría en desacuerdo que rebaja a no_comprobable y auditor mudo como None. S-08 saneamiento único de las tres hipótesis rezagadas y hueco del juez. Antes de activar cualquier rejuicio automático más amplio, M-21 (contras como apoyo).
6. S-16 hipótesis nuevas por `creadaEn` y entrada `cola` por regla en resumen y llano; recalcular progreso de las corridas 7 a 9.
7. S-18 bandera sintético en el laboratorio; S-23 decisión diferida (reaplicar pendientes, pagehide, idempotencia); S-24 evaluación GEPA con juez caído.
8. S-17 primer corte: no mutar por reloj ni espera humana, contador en memoria, instantánea cacheada por versión, no repetir la misma versión por SSE, GZip. Quita el 70 % de las mutaciones y la mayor parte del tráfico sin cambiar la forma del estado.
9. M-34 tildes: defecto solo comprobar, corregir los errores de sentido y las líneas del backend, CLAUDE.md.

Tanda 2, siguientes dos semanas (resultado científico y coste):

1. S-05 normalización compartida PDF (medir con las 284 reales, 0 regresiones). Independiente.
2. S-06 cortes quirúrgicos: cohortes por `claves_de_fuente` en certeza, procedencia y sesgo en todas las corridas, `extraido` por fragmento, comprobar existencia antes del cribado, caché de Europe PMC y Exa. Después el registro de fuentes por investigación (días).
3. S-07 caché de exclusiones con `puntuadoPorModelo` y hash de criterio, red de seguridad por palabra completa, relajación acotada, preguntas propias por delante. Requiere S-06 (c) para que las primarias recuperadas se lean una vez.
4. S-13 huella de la evidencia para reconcluir, torneo sin revanchas sin evidencia, paralelismo con semáforo. Requiere S-08 (huella de decisión) para compartir la definición.
5. S-14 y B-02 presupuesto y parada en el cierre y al abrir la iteración; retroceso del tick.
6. S-26 fragmentos por relevancia; M-10 factor de sección; M-06 y M-07 escala del juez y dirección por regla; M-14 recálculo de techos por regla; M-03 y M-04 cohortes (catálogo de ensayos y campo servido). M-04 requiere M-03.
7. S-27 replicación con fragmentos de toda la investigación y `noComprobables`.
8. S-25 test de iteración completa y un caso por pendiente (hipotesisNuevas, hecho duplicado, cita no resuelve, reloj, presupuesto en cierre). Debe entrar antes que los cambios grandes de S-06 y S-17 para tener red.
9. M-11 revisor (presupuesto por sección, ámbito de iteración, negación, certeza en el registro), M-05, M-08, M-09, M-13, M-19, M-27, M-30, M-31, M-33, M-36.

Tanda 3, para dejar de ser un MVP (estado, operación, seguridad):

1. S-17 estructural: claves privadas de corridas terminadas en tabla propia, persistencia por clave o por entidad, SSE con diferencias por versión y fusión por clave en el cliente. Requiere S-25 (arnés) y S-28 (versiones de artefactos fuera del estado) para no romper el diff ni la búsqueda.
2. S-21 y S-22: token como llave de red, administrador explícito, autoría desde la sesión y actor en la cadena de hashes, roles lectura/decisión/administración desde Ajustes, límites en sellar y subidas (M-29).
3. M-28 logging y `/api/salud` informativa; M-37 CI en clon limpio y hook sobre el índice; M-39 versión visible, reinicio por botón con launchd, claves desde Ajustes; M-26 apagado acotado; M-40 endpoints en routers y Killer sin duplicar.
4. M-25 GEPA continuo con retención propia y nota de "faltan investigaciones"; M-24 espejo con hash sin reloj y reintento; M-22 medidores del Killer poblados; M-12 datos controlados como puerta; M-16 PRISMA correcto; M-20 numeración global de iteraciones; M-35 bundle; M-23 estado `sin_trabajo`.
5. Bajos según toque el fichero.

## (f) Mediciones agregadas

Estado y persistencia. Fila `estado` en rosa.db: 15,2 MB (versión 14455) a 18,2 MB (versión 16387) en el día; instantánea pública 8,65 a 10,07 MB; claves privadas 6,4 a 7,9 MB (39 a 42 %), de las que 5,8 a 6,75 MB son de corridas terminadas; `corridas` 10 a 11 MB con privadas (2,6 sin), `artefactos` 1,9 a 2,2, `hipotesis` 1,8 a 1,9, `iteraciones` 1,1 a 1,2. Mutaciones por iteración 776 a 996 (llamada_modelo 316 a 465, tick 224 a 251, pista 112 a 210); coste de una mutación 97 a 180 ms; `_serializar` 71 a 92 ms; escritura al WAL 20 KB si no cambia la longitud, 17 a 18 MB si cambia (unos 12 GB por hora en marcha). Registro de acciones 14.327 a 16.300 filas; 2 roturas de cadena (6450, 6455), 5 retrocesos de versión, 11 versiones duplicadas.

SSE y red. Empuje 9,2 a 10,8 MB por evento (`ensure_ascii` añade 4 a 7 %); en reposo 46 a 83 MB por minuto por pestaña; en fase activa 30 a 41 empujes y 324 a 443 MB por minuto; mediana entre empujes 1,2 s en corrida, 7,5 a 10 s en espera; GET /api/estado 0,07 a 0,09 s en reposo, 2,6 a 3,4 s bajo carga; la carga inicial descarga el estado dos veces (20 MB). Espejo Convex: un envío cada ~9 s de 120 a 460 kB por el reloj; 1.378 a 1.408 entidades; 14 claves sin espejar.

Verificación y evidencia. 1.532 afirmaciones en 9 corridas de inv-mu2sz2ns-3: 469 sostenidas, 7 parciales, 7 no sostenidas, 1.049 cita_no_resuelve (1.193 con la corrida 9). Por localizador: texto web 875/875 bloqueadas, pág. 284/540 (53 %), sección 8/175, resumen 25/272. 253 fuentes registradas, 179 claves distintas, 53 en más de una corrida; 34 "Sin autor"; 19 fuentes reextraídas 22 veces (517 afirmaciones). 190 afirmaciones en las 28 hipótesis (188 sostenidas, 2 parciales), 93 fuentes; 35 de 38 afirmaciones acumuladas son apoya_indirecta; páginas citadas nunca mayores de 6; 47 % del peso a favor desde introducciones en 11 hipótesis; 25 de 37 fuentes con tipoEstudio "otro"; sesgo evaluado en 4 de 37 (todas "alto").

Hipótesis, Killer y torneo. 28 hipótesis (16 propuesta, 10 en_revision, 2 aceptada), 31 decisiones del Killer (16 suspender, 11 descartar_en_contexto, 2 avanzar, 2 reformular), 0 decisiones humanas registradas, conjunto dorado vacío, vivero vacío. En inv-mu2sz2ns-3: 9 hipótesis, 44 partidos sobre 25 pares (uno jugado 5 veces, 30 con una descartada), 88 llamadas de comparación de ~20.000 tokens; 4 de 5 descartes por "supuesto contradicho"; 9 de 13 descartes o reformulaciones auditados, 5 en desacuerdo; 16 de 28 con "Sin precedente claro entre 0 obras"; 9 de 9 conclusiones en muy_baja con 7 techos por regla en baja; 0 hipótesis candidatas.

Coste y modelos. Corrida 7: 19,16 USD mostrados, 10,75 facturados, 386 llamadas; corrida 8: 26,79 frente a 12,71, 366 llamadas; corrida 9: 20,34 frente a 10,13, 324 a 337 llamadas. Precios reales por millón: Sonnet 2/10, Opus 5/25, GPT-6 Astra ~12/52. En la corrida 8 por programa (coste real): juzgar 22 % (111 llamadas, 28 fragmentos), comparar 14 % (11 llamadas de 20.240 tokens), extraer 12 %, concluir 11 %, relevancia_amplitud 10 % (72 llamadas de 6.450 tokens). Cierre de iteración: 8 conclusiones de 60 a 79 s en serie (4,4 USD estimados, 1,4 reales) más 8 comparaciones; 15 minutos en la corrida 8. Aciertos de caché contados como llamadas: 487 de 5.505. Filtros de contenido del juez hoy: 8, con un reintento de ~21k tokens cada uno. Llamadas colgadas de 600 s: 2 en la historia. GEPA continuo: 0 ciclos; trazas.db 32 a 46 MB en un día; ~/.dspy_cache 96 a 102 MB; mlflow.db 322 a 376 MB.

Corrida y reloj. Tope por iteración 447; uso 248 a 350; el cierre necesita 19 a 21 llamadas. Espera humana en la corrida 8: 26,7 de 64,6 min (41 %), ya descontada desde 8a4eb64; corrida 7 con 57.930 s de gasto por el sueño del Mac. Servidor vivo reiniciado a las 12:07 (pid 88032) con 62b327b; corrida 10 detenida para ello, corrida 11 "Duplicada", corrida 12 en marcha con 58 USD estimados.

Tests y código. Backend 854 a 861 tests en 15,8 s; frontend 446 en 8,7 s; tsc y eslint limpios. 41 funciones del bucle sin referencia en tests; 0 líneas ejecutadas en los nueve ejecutores y en correr_corrida. 138 `except Exception`, 14 mudos; 66 print, 0 logging; funciones de más de 150 líneas: 6 (crear_app 620). Bundle 974 KB (301 gzip) en un chunk. 46 plantillas del frontend y 9 líneas del backend con texto sin tilde; "Se cumplio" 10 veces en el estado. Tests adversariales escritos por las zonas y las lentes: más de 60 ficheros en scratchpad/revision_bugs/ y scratchpad/revision_bugs/verificacion/, todos pasando en el sentido de reproducir el fallo.

## (g) Apéndices

### Refutados

Ninguno de los hallazgos verificados fue refutado por la lente "reproducir". Sí quedaron en "parcial" por premisas que ya no se cumplen o cifras corregidas:

- corrida-06 y tests-10 (reloj de pared): el arreglo 8a4eb64 (17/09 12:03) ya cuenta tiempo de trabajo; el hallazgo describe el código anterior. Quedan tres restos (B-01).
- corrida-07 (iteración vacía): el cierre vacío sin llamadas ya está en 8a4eb64 con test; queda el hueco al aprobar el plan (B-02).
- corrida-01, killer-01, modelos-04, evidencia-03 (el servidor corre código anterior a 62b327b): falso desde las 12:07; el proceso 88032 lleva el arreglo y ya rejuzgó dos hipótesis. Quedan los residuos descritos en S-08.
- literatura-05: el "+" de "evoke+" se ignora en Europe PMC, pero no explica los cero relevantes ni la falta de fuente primaria (los primarios llegaron y los excluyó la caché). Fundido en S-07.
- literatura-03 (impacto): "es la fuente principal del coste" refutado (5 a 15 % del gasto); la gravedad pasa a lo científico. Fundido en S-06.
- evidencia-01: "hace imposible salir de muy baja" refutado (acotar acepta baja y el juez la dio en 2 hipótesis); la escala escrita sí contradice a certeza.py. M-06.
- evidencia-02 y rigor-07: hoy la ficha no enseña "moderada" (la conclusión es anterior al techo); lo enseñará al reconcluir. S-18 se mantiene.
- extraccion-04: la penalización de sesgo no cambia hoy ninguna certeza (el techo estructural frena antes); sí suspende tres hipótesis. M-01.
- extraccion-06 / modelos-09: el coste del juez estaba inflado por mezclar Killer y torneo (8,4 USD de verificación, no 19). M-02.
- killer-05: "sobre evidencia sin cambios" refutado en parte (9 de 44 revanchas con evidencia nueva); el juez no ve la evidencia acumulada. Fundido en S-13.
- killer-12: el generador no repite títulos, devuelve listas vacías a propósito por la firma; baja a B-03.
- servidor-04 y modelos-06: los filtros no decidieron ningún partido (el reintento recupera una respuesta completa); el riesgo real es `length`. M-27.
- rigor-03: los "alta" que bloquean no son artefactos del recorte (9 de 11 son fallos reales del resumidor, hoy S-16); el recorte existe y debilita al juez. M-11.
- tests-06: el script sí trata f-strings; el hueco es el diccionario y la heurística de dominios (ClinicalTrials.gov). M-34.
- tests-11: el escenario "cambiar la regla en un sitio y no en otro" ya ocurrió: las dos copias del Killer divergen hoy. M-40.

### Lo que ya estaba anotado en TRASPASO.md y cómo cambia

- "174 afirmaciones bloqueadas por cita no resuelve, fuentes sin texto completo, extraer solo de fuentes con texto completo" (TRASPASO.md:563-568): diagnóstico equivocado. La causa es el patrón de citas (S-03) más la comparación literal del PDF (S-05); las fuentes bloqueadas sí tienen texto completo y el arreglo anotado no cambiaría nada. Reescribir la nota.
- "Comprobar que el bucle vuelve sobre las hipótesis en cola" (TRASPASO.md:569-575): comprobado; funciona desde 62b327b para lo nuevo; quedan los residuos de S-08 y la suspensión permanente de S-09.
- "hipotesisNuevas: 5, revisar qué cuenta progreso.py" (TRASPASO.md:606): la causa no está en progreso.py sino en el filtro por número de iteración de corrida.py:1378 y revisor_registro.py:250 (S-16).
- "Doble evento 'hecho nuevo', buscar la doble llamada a con_evento" (TRASPASO.md:576-578): no hay doble emisión; hay hechos duplicados por paráfrasis (M-08).
- "Hechos repetidos de Belder y Chatterjee que el paso de modelo no fundió" (TRASPASO.md:586): confirmado; causa en la deduplicación y en la reextracción entre corridas (M-08, S-06).
- "Reloj de pared, espera humana y sueño del Mac" (TRASPASO.md:589-594): resuelto en 8a4eb64; marcar como tal y dejar los tres restos de B-01.
- "Comprobar el tope antes de proponer el plan, iteración vacía corriendo lecciones y revisor" (TRASPASO.md:597-605): la comprobación existe (corrida.py:1151) y el cierre vacío ya no llama a nada; queda el hueco durante la llamada del plan (B-02).
- "Umbral de hitCount para consultas demasiado anchas" (TRASPASO.md:595): confirmado, forma parte de S-07.
- "Reparto foco/amplitud como causa de los temas con 0 leídos" (TRASPASO.md:579-583): el reparto se cumple; la causa es la especificidad de las consultas, la red de seguridad muerta y la caché de exclusiones (S-07).
- "No reiniciar con una corrida viva; el arreglo entra en el próximo reinicio" (TRASPASO.md:584-585): el patrón "reinicio con trabajo en vuelo" es justo el que produjo la pérdida de S-01; el cerrojo lo convierte en seguro.
- Física del árbol con rejilla espacial o Web Worker: anotado, B-21.
- Referencia corta (TRASPASO.md:289): mención sobre otro asunto; la colisión de S-04 no estaba anotada.

Los hallazgos que no estaban anotados y pesan más: S-01, S-02, S-04, S-05, S-09 a S-12, S-14, S-15, S-17 a S-24, S-26 a S-28.
