---
name: la-usuaria-final-es-una-medica-no-programadora
description: "Toda configuración que deba hacer la usuaria del RAG (una médica) tiene que resolverse con botones en el frontend, nunca con variables de entorno, tokens o terminal."
metadata: 
  node_type: memory
  pinned: true
  originSessionId: ae861247-e51d-4381-bb02-daeae35a261b
  modified: 2026-09-04T20:21:26.395Z
---

# La usuaria final es una médica, no una programadora

Emir lo dijo al ver la primera versión de la integración con Notion, que
mostraba "Notion no configurado, falta NOTION_TOKEN" y esperaba que alguien
pusiera un secreto con la CLI de Convex: *"me gustaría que lo hagas que se
pueda vincular de la manera más fácil, no así. y que también se vea dinámico en
el frontend, recuerda que es una médica que tendrá que hacer eso, no una
programadora"*.

La regla que se sigue de ahí, y que aplica a cualquier función nueva del RAG:
si un paso lo tiene que dar la usuaria, tiene que ser un botón o un formulario
en la interfaz, con el estado visible y actualizándose solo (las suscripciones
reactivas de Convex lo hacen gratis), y con textos en su idioma, no en el de
las APIs. Las variables de entorno, los tokens, los ids de bases de datos y la
terminal son cosas que puede hacer Emir una sola vez como dueño de la
aplicación (por ejemplo registrar la aplicación OAuth de Notion), pero nunca
parte del uso diario. Un mensaje del tipo "falta NOTION_TOKEN" en pantalla es
un error de diseño, no una configuración pendiente.

Aplicación concreta en la integración con Notion: en vez de un token de
integración interna pegado como variable, un botón "Conectar con Notion" que
abre el consentimiento OAuth de Notion (donde ella elige qué páginas
compartir), vuelve a la app conectada, y un desplegable para elegir la base
de datos a sincronizar, con el progreso de la sincronización en vivo.
