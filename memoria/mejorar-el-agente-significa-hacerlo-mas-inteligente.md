---
name: mejorar-el-agente-significa-hacerlo-mas-inteligente
description: "Cuando Emir pide mejorar el pipeline o el agente del RAG, quiere que el agente razone y recupere mejor; el trabajo periférico de robustez le parece esquivar la petición."
metadata: 
  node_type: memory
  pinned: false
  originSessionId: ae861247-e51d-4381-bb02-daeae35a261b
  modified: 2026-09-04T15:36:35.727Z
---

# "Mejorar el agente" significa hacerlo más inteligente, no más robusto

Emir pidió "busca cómo podrías arreglar el pipeline y llevarlo al siguiente
nivel... mejora el agente de una forma que me deje sorprendido, que esté listo
para usar por la médica". Yo respondí lanzando, entre otras cosas, arreglos de
ingesta (parseo de PDF, tablas de Word, firmas Vancouver) y una vetación de
diseño, y su reacción fue: *"bro, yo te dije que quería mejorar era el
pipeline, que el agente sea lo más inteligente que puedas y cosas así, ahora
mismo es un tonto"*.

La lección: para él, "el pipeline" y "el agente" son la parte que **piensa y
recupera** (razonamiento del modelo, descomposición de la pregunta, qué
evidencia llega al redactor, cómo se estructura la respuesta para la médica).
La robustez periférica (parseo, evaluador, telemetría) puede ser correcta y
necesaria, pero si es lo primero que ve, lee que no le hice caso. Su vara de
medir es el comportamiento visible del agente ante una pregunta difícil: si
sigue respondiendo "como un tonto", el resto no cuenta.

En la práctica: cuando pida mejorar el agente, empezar por lo que cambia la
inteligencia observable (por ejemplo, ese día el agente llevaba semanas
corriendo con `reasoning_effort` apagado por una nota obsoleta: cero tokens de
razonamiento), medirlo, y dejar la periferia para después o en segundo plano
sin darle protagonismo en el informe. Contarle primero qué hace el agente
distinto, no cuántos ficheros se arreglaron.
