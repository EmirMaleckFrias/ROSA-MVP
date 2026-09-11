---
name: las-referencias-a-documentos-suelen-ser-genericas
description: "Quien pregunta al RAG se refiere a sus documentos sin nombrarlos (\"el PDF indexado\", \"el PDF de sistemas eléctricos\"); toda función que resuelva una referencia a un documento tiene que contemplar la pista genérica y la descriptiva, no solo el nombre del fichero."
metadata: 
  node_type: memory
  pinned: false
  originSessionId: ae861247-e51d-4381-bb02-daeae35a261b
  modified: 2026-09-09T14:21:21.650Z
---

# Las referencias a documentos casi nunca son el nombre del fichero

Al implementar que una pregunta pueda limitarse a un documento concreto
("únicamente el PDF X"), diseñé la resolución alrededor de un nombre o título
que buscar entre los ficheros. la persona responsable me corrigió a mitad de camino: *"quiero
que tengas en cuenta que Manus nunca le dijo cuál era el documento, solo le
dijo esto: Usando únicamente el PDF indexado, analiza este escenario
hipotético"*. Poco después me trajo una pregunta real que decía "usando
únicamente el PDF de sistemas eléctricos y electrónicos de aeronaves", y
tampoco encajaba: el fichero se llama `--M6U1_PDF.pdf` y no tiene título.

La lección, que va más allá de esos dos casos: quien usa el asistente (una
médica, o un evaluador externo que se comporta como ella) nombra sus
documentos como se hace en una conversación. Hay al menos tres formas y todas
tienen que funcionar: **por nombre** ("el PDF M6U1", "el de el investigador clinico principal"), **de
forma genérica** ("el PDF", "el documento que subí") y **por su tema** ("el
PDF de sistemas eléctricos"). El nombre del fichero es la forma menos
frecuente, y encima suele ser un código sin significado. Cualquier función que
interprete una referencia a un documento (acotar la búsqueda, comparar dos
documentos, resumir "el último") tiene que resolver las tres, y nunca fallar
en silencio ni exigir que se escriba el nombre exacto.

Cómo quedó resuelto en el alcance por documento (`convex/agente/alcance.ts`):
las palabras genéricas y los nombres de formato no identifican, así que una
pista sin palabras identificadoras se resuelve al único documento de ese
formato; una pista con palabras se busca en el nombre y el título; y si nada
encaja por nombre, se cuentan los aciertos de la pista en el índice léxico de
los fragmentos y se acota al documento que domina la muestra. En los tres
caminos, cuando la pista no identifica un documento con claridad se busca en
todos y la respuesta tiene que decir de cuál sale cada dato, porque acotar al
documento equivocado produce una abstención que quien pregunta no puede
distinguir de "ese documento no lo dice".
