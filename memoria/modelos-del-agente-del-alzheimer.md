---
name: modelos-del-agente-del-alzheimer
description: Rosa usa GPT-6 Astra como cerebro, Claude Opus 5 como juez y Claude Sonnet 5 en alto volumen, por el AI Gateway de Vercel; Claude Fable 5.1 queda fuera porque sus filtros de doble uso en biología devuelven vacío por la API en hipótesis mecanísticas y dianas terapéuticas.
metadata:
  pinned: true
---

# Modelos de Rosa: Astra de cerebro, Opus 5 de juez, Sonnet 5 en volumen

Entre el 9 y el 10 de septiembre de 2026 la persona responsable decidió los modelos de Rosa,
todos por el endpoint compatible con OpenAI del AI Gateway de Vercel y nunca
por las APIs directas: `openai/gpt-6-astra` como cerebro (planificar, generar
hipótesis, meta-revisar, contexto largo), `anthropic/claude-opus-5` como juez
del verificador (la métrica que GEPA optimiza y el veto final) y
`anthropic/claude-sonnet-5` en las piezas de alto volumen sin poder de veto
(extractor, calificador, triaje previo del juez). El RAG anterior no cambia.
El coste por token no fue criterio.

Tres correcciones suyas dieron forma a esto. Primero objetó que el juez fuera
un modelo rápido (*"¿no debería ser al revés si de él depende una muy buena
parte del proyecto?"*): el juez es siempre el modelo más fuerte disponible y
de otra familia que el cerebro, para no compartir puntos ciegos. Después
eligió a Claude Fable 5.1 de juez por intuición de que "acierta más que GPT",
y los datos lo sostenían en conocimiento. Por último preguntó si era cierto
que Fable "no responde nada científico", y la comprobación empírica le dio la
razón en lo que importa: **Fable 5.1 lleva filtros de doble uso en biología
(virología, toxicología, diseño de fármacos y molecular) y por la API una
consulta bloqueada vuelve vacía con `finish_reason: content-filter`, sin
desvío automático**. De diez preguntas del dominio del Alzheimer devolvió
vacío en cinéticas de agregación del beta amiloide, en hipótesis mecanísticas
sobre NLRP3 y tau, y en TREM2 como diana; Opus 5, Astra y Sonnet 5
respondieron las tres. Anthropic lo dice en su propia nota: Fable "isn't yet
usable for professional biology research and drug development". Por eso Fable
no entra en ninguna pieza de Rosa salvo que la empresa obtenga acceso
verificado para ciencias de la vida, y entonces se reevalúa con la misma
prueba.

Regla general que queda de esto: antes de fijar un modelo en una pieza de
Rosa, lanzarle las preguntas reales del dominio (hipótesis mecanísticas y
dianas terapéuticas incluidas) y mirar `finish_reason` y el campo `model` de
cada respuesta. Un modelo que calla justo en lo difícil no sirve de juez ni de
cerebro aunque gane en los rankings.
