---
name: probar-el-rag-con-preguntas-humanas-y-ambiguas
description: "Al atacar el RAG de FIREtech, Emir quiere preguntas descuidadas y ambiguas como las de una persona real, no prompts perfectos ni abusos de volumen; los fallos que le importan son los realistas."
metadata: 
  node_type: memory
  pinned: false
  originSessionId: ae861247-e51d-4381-bb02-daeae35a261b
  modified: 2026-09-09T17:55:41.058Z
---

# Atacar el RAG como lo usaría una persona, no con prompts perfectos

Mientras yo diseñaba ataques adversariales contra el asistente, Emir me
corrigió el enfoque: *"trata de meter ambigüedades también, que puedan hacer
pensar al agente dos cosas distintas a la vez, muchas veces ahí fallan los LLM
con los humanos, en vez de con un prompt perfecto que explique todo
detalladamente al pie de la letra"*. Y cuando le presenté el informe con dos
fallos, uno por volumen (una pregunta que exigía 150 afirmaciones numeradas y
dejó al sistema sin poder responder) y otro por ambigüedad (una pregunta
descuidada de varias partes que produjo una declaración de ausencia falsa),
eligió sin dudar: *"el fallo que vale la pena arreglar es el de la ambigüedad,
porque en el de la primera pregunta creo que era obvio que no iba a poder dar
en un mensaje 150 afirmaciones numeradas"*.

La regla que se sigue, y que aplica a cualquier prueba adversarial futura de
este proyecto: las preguntas de ataque más valiosas son las que escribiría una
médica con prisa. Varias cosas mezcladas en una frase, referentes vagos ("el
generador ese", "la otra", "cuando se cae todo"), un término que en el
documento nombra dos cosas parecidas, dudas sobre si algo es general o
específico, y una exigencia de brevedad. Esas preguntas destapan fallos que un
prompt exhaustivo nunca enseña, porque el prompt exhaustivo le hace al modelo
el trabajo de desambiguar. Y al priorizar arreglos, un fallo que aparece con
una pregunta realista vale más que una rotura conseguida con una petición que
ningún usuario haría.

Lo que salió de aplicarlo la primera vez, para no volver a descubrirlo: en
modo normal hay una sola búsqueda, y cuando la pregunta trae cuatro
subpreguntas la evidencia se reparte y alguna parte se queda sin sus páginas;
el modelo entonces confunde "no está en lo que me dieron" con "no está en el
documento", y esa ausencia falsa era invisible para la barrera porque no
tiene cita contra la que auditarse. Se arregló comprobando las declaraciones
de ausencia contra el índice (`convex/agente/ausencias.ts`).
