# Como presentan sus conclusiones los AI scientists, y que hace ROSA2018

Fecha: 10 de septiembre de 2026. Tres investigaciones sobre fuentes primarias
(papers, documentacion oficial, codigo, PDFs de las guias): los sistemas de IA
para ciencia, las herramientas de literatura para medicos, y las convenciones
de la medicina basada en evidencia para comunicar conclusiones e
incertidumbre. Al final, lo que se fusiono en ROSA2018 y donde esta en el codigo.

## 1. Los sistemas de IA

| Sistema | Que entrega | Como expresa la certeza | Enlace frase a fuente | Critica publicada |
|---|---|---|---|---|
| Kosmos (Edison) | 3 o 4 "narrativas de descubrimiento", 25 afirmaciones cada una | Ninguna por afirmacion; 79,4 % de acierto global medido fuera (85 % datos, 82 % literatura, 58 % interpretacion) | `[[Trajectory rN]]` a un notebook con UUID, o un paper | "Afirmaciones excesivamente fuertes"; confunde significativo con relevante; la fluidez enmascara la incertidumbre |
| PaperQA2 / Crow / Falcon | Respuesta de 200 palabras o informe | Relevancia 1 a 10 por fragmento; "I cannot answer" como salida de primera clase | `(clave pages 3-4)` al final de la frase | Sobreconfianza de ContraCrow |
| Robin | Hipotesis rankeadas (Bradley-Terry) y notebooks de analisis | Ranking relativo, sin intervalos | Sin cita formal en la hipotesis | Lenguaje definitivo |
| Claude Science | Panel de artefactos con codigo, entorno y conversacion por figura | Sin puntuacion; un revisor marca "numeros no trazables" | Codigo y entorno por figura | El revisor no siempre corre solo |
| Co-Scientist | Research overview (formato NIH) e hipotesis con supuestos, alternativas y protocolo | Elo relativo mas seis revisiones cualitativas | Citas clicables | Recicla lo conocido; calibracion "unsolved" segun DeepMind |
| Sakana / Agent Laboratory | Paper LaTeX con revisor NeurIPS (1 a 4 por criterio, 1 a 10 global) | Puntuaciones del revisor automatico | Referencias, sin fragmento | El revisor se infla (6,1 frente a 3,8 humano); 57 % con cifras alucinadas |
| Elicit | Informe con PRISMA y tablas | Sin grado; cribado auditable | Cada frase a la cita exacta | Precision 43 % en cribado |
| Consensus | Consensus Meter (Si/No/Quiza) y Snapshot | Porcentaje de votos sobre 20 papers | Al paper | "Cuenta votos sin pesar evidencia": n=50 vale igual que n=5000 |
| OpenEvidence | Respuesta clinica citada frase a frase | EvidenceGrade A a D (sobre GRADE) con la justificacion abierta al pulsar | Numeros inline a texto completo | Errores de metadatos |
| Scite | Texto o tabla | supporting / contrasting / mentioning por cita | Hover con el statement y la seccion | Referencias irrelevantes |
| Undermind | Lista explicada | Relevancia por paper y porcentaje de completitud de la busqueda | Al paper | |

Patrones de los mejores: cada frase con un asidero concreto (pasaje, pagina,
notebook); la abstencion como salida visible y medida aparte; la fuerza de la
evidencia por tipo de estudio con la justificacion abierta; separar dato,
literatura e interpretacion; un revisor distinto del generador; ranking
relativo en vez de una probabilidad inventada; estimar lo que falta, no solo
lo que hay; la persona interviene en la cola.

Errores que se repiten: sobreafirmacion con fluidez; el revisor automatico se
infla; citas inventadas cuando la cita no resuelve a fragmento; contar votos;
reciclar lo conocido como novedad; el indicador de confianza existe en el
paper pero no en el producto; el modelo de mundo es interno y opaco.

## 2. Las convenciones de la medicina basada en evidencia

- **GRADE**: cuatro niveles de certeza (alta, moderada, baja, muy baja) que
  se aplican al cuerpo de evidencia, no a cada estudio. Bajan por riesgo de
  sesgo, inconsistencia, evidencia indirecta, imprecision y sesgo de
  publicacion; suben por efecto grande, gradiente dosis-respuesta y confusion
  que iria en contra. Separa certeza de fuerza de recomendacion. La tabla
  "Summary of Findings" trae por desenlace: numero de participantes y
  estudios, certeza con su simbolo y notas al pie que explican cada bajada.
- **Santesso 2020 y Cochrane Iberoamerica**: frases plantilla por nivel. Alta
  "X reduce Z"; moderada "X probablemente reduce Z"; baja "X podria reducir
  Z" o "la evidencia sugiere"; muy baja "la evidencia es muy incierta sobre
  el efecto de X en Z". Nunca "estadisticamente significativo"; nunca "no
  hay efecto" con certeza baja.
- **Plain Language Summary de Cochrane (2022)**: titulo como pregunta,
  mensajes clave (2 o 3, el primero responde a la pregunta), que queriamos
  saber, que hicimos, que encontramos, limitaciones de la evidencia, hasta
  cuando esta al dia; 400 a 850 palabras; frases de 20 palabras; sin
  intervalos de confianza ni jerga GRADE; cifras como frecuencias naturales
  ("de cada 100 personas, 10").
- **AAN (neurologia)**: clases I a IV y frases fijas ("highly likely",
  "likely", "possibly", "insufficient evidence to support or refute"); evita
  "proven" y "established" porque "evidence is never definitive".
- **IPCC e ICD 203 (inteligencia)**: dos ejes distintos, probabilidad del
  hecho y confianza en el juicio, que no se mezclan en una frase; explicar
  las causas de la incertidumbre y "que indicadores la cambiarian".
- **Evidencia empirica** (Budescu, van der Bles, Spiegelhalter, Gigerenzer):
  las palabras solas se leen todas "cerca del 50 %"; el numero junto a la
  palabra corrige; la incertidumbre numerica apenas reduce la confianza del
  lector, la verbal si; riesgos absolutos con denominador fijo.
- **Estado de una hipotesis**: Open Targets y Agora advierten que sus scores
  miden disponibilidad de datos, no probabilidad de que la hipotesis sea
  cierta; los preregistros (OSF, AsPredicted) exigen hipotesis con variable,
  direccion, poblacion y el resultado que la refutaria; Nosek separa
  prediccion de postdiccion.

## 3. Lo que se fusiono en ROSA2018

Por hipotesis, la **Conclusion de ROSA2018** (`ConcluirHipotesis` en
`rosa/modulos/firmas.py`; `_concluir_hipotesis` en `rosa/bucle/corrida.py`;
`ConclusionDeRosa` en `frontend/src/componentes/EnLlano.tsx`):

1. Dos ejes separados: **certeza** (alta, moderada, baja, muy baja, GRADE) y
   **direccion** (apoya, mixta, en contra, sin evidencia directa).
2. **Enunciado calibrado** generado por regla, no por el modelo
   (`frase_plantilla`): "La evidencia reunida probablemente sostiene que...".
3. **Por que esta certeza**: los factores GRADE que la bajaron o subieron,
   cada uno con su evidencia (como el rationale de EvidenceGrade).
4. **Base contada de forma determinista**: afirmaciones sostenidas, fuentes,
   cuantas son datos y cuantas interpretaciones.
5. A favor y en contra con cita; lo mas fragil; **subiria si** y **bajaria
   si** (los "indicadores que cambiarian la incertidumbre" de ICD 203).
6. **Que no pudimos comprobar**: fuentes que no respondieron. Nunca "no hay".
7. **Cambio respecto a la conclusion anterior**, y hasta cuando se busco.
8. Cada afirmacion ense�a el **pasaje literal** de la fuente (Elicit,
   NotebookLM). La conclusion se rehace al cerrar cada iteracion. El juez
   (Opus 5) la redacta; es un revisor distinto del generador.

Por iteracion, el **resumen en lenguaje llano** (`ExplicarEnLlano`) con la
estructura del Plain Language Summary: pregunta, mensajes clave, que buscaba,
que hizo, que encontro, hasta donde fiarse, que cambio, que propone, que
falta, que te toca, hasta cuando esta al dia, glosario.

Lo que ROSA2018 no hace a proposito: porcentajes de confianza por hipotesis
(nadie los calibra), recomendaciones clinicas (Cochrane no las hace), "no hay
ensayos" cuando la fuente no respondio, y "demostrado" o "confirmado" en
ninguna conclusion.

Lo que queda pendiente de esta comparativa: un revisor independiente del
generador para las hipotesis (hoy el juez revisa afirmaciones y concluye,
pero la revision "profunda" de supuestos la hace el mismo modelo que
genera), y la clasificacion de citas en apoya / menciona / contrasta (Scite)
para los hechos del modelo de mundo, cuyo campo `citas` existe y esta vacio.
