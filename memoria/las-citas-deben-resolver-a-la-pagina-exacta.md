---
name: las-citas-deben-resolver-a-la-pagina-exacta
description: En FIREtech-RAG una cita con la página desfasada aunque sea en uno se considera un fallo grave; Emir verifica las citas contra el PDF real (también con herramientas externas) y espera que el localizador sea exacto.
metadata: 
  node_type: memory
  pinned: false
  originSessionId: ae861247-e51d-4381-bb02-daeae35a261b
  modified: 2026-09-08T20:38:44.965Z
---

# Las citas tienen que resolver a la página exacta del dato

Emir lo pidió tras probar el asistente con otra herramienta de IA (Manus) que
juzgó buenas las respuestas pero detectó que las páginas citadas iban una o
dos por delante o por detrás de donde estaba el dato: *"cuando un humano
quiera verificar la página del pdf real y vea que el agente se adelantó o
atrasó de páginas se sentirá decepcionado"*.

La regla que se sigue de ahí: en este proyecto el localizador de una cita no
es decorativo, es la promesa de que abriendo el PDF en esa página se encuentra
el dato. Un desfase de una página, que en otros productos pasaría por detalle,
aquí destruye la confianza en todas las citas, porque la usuaria (una médica)
las comprueba. Por eso un fragmento de PDF no puede cruzar de página (se
empaqueta por sección y por página, y el solape no arrastra la página
anterior), y cualquier función nueva que produzca localizadores (tablas, filas,
secciones, futuros formatos) debe garantizar que el localizador señala el
sitio exacto del dato, no el inicio del fragmento que lo contiene.

Dos matices que conviene recordar al hablar con él de esto: la página citada es
la del visor de PDF (el índice de página), no el número impreso al pie, que en
un artículo paginado por la revista o en un informe con portada difiere; y el
verificador obliga al modelo a citar exactamente la cita que recibió, así que
el arreglo de un desfase está en la ingesta (qué página lleva el fragmento), no
en el prompt.
