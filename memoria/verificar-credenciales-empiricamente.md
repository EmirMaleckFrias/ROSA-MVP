---
name: verificar-credenciales-empiricamente
description: Emir prefiere que se pruebe una credencial o configuración contra el servicio real antes de descartarla por su formato
metadata:
    pinned: false
---

Cuando una credencial, clave o configuración no coincide con el formato que yo
espero, Emir prefiere que la pruebe contra el servicio real antes de declararla
inválida. Su formulación fue directa: "no importa si es de OpenAI o no, lo
importante es que funcione".

El caso que originó la lección: en el proyecto FIREtech-RAG apareció una clave
con prefijo `vck_` donde el código esperaba una de OpenAI (`sk-…`). La descarté
como "no es una clave de OpenAI" y le pedí que buscara la correcta. Cuando él
insistió en probarla, resultó ser una clave válida de Vercel AI Gateway —un
endpoint compatible con OpenAI— que además ofrecía los tres modelos exactos que
el proyecto necesita. Descartarla por el prefijo habría costado una vuelta
entera de trabajo inútil y lo habría mandado a buscar algo que ya tenía.

La lección general: el formato de una credencial es una pista sobre quién la
emitió, no una prueba de que no sirva. Antes de decirle que algo no funciona,
hay que intentar el camino que sí podría funcionar (otro `base_url`, otro
endpoint, otro proveedor compatible) y reportar el resultado real de esa prueba,
no la conclusión sacada del prefijo.
