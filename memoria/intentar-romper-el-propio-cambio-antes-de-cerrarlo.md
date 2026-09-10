---
name: intentar-romper-el-propio-cambio-antes-de-cerrarlo
description: "Emir exige que antes de dar por bueno un cambio se intente romperlo activamente, no basta con que pase la suite existente."
metadata: 
  node_type: memory
  pinned: true
  originSessionId: ae861247-e51d-4381-bb02-daeae35a261b
  modified: 2026-09-04T14:15:16.402Z
---

# Intentar romper el propio cambio antes de darlo por bueno

Emir me lo dijo tras una jornada en la que introduje varios fallos seguidos:
*"necesito que verifiques lo que estas haciendo, cada vez dejas mas errores"*.
La crítica era exacta y el patrón estaba medido: cada defecto que introduje lo
cazó **un test adversarial o una revisión externa, no yo**. Escribía el cambio,
corría la suite, pasaba, y seguía adelante — pero la suite existente no cubría
el modo de fallo nuevo, porque el modo de fallo nuevo lo acababa de crear yo.

Lo que hay que hacer antes de cerrar un cambio, y en este orden:

1. **Escribir el test que intenta romperlo**, no el que confirma que funciona.
   El test adversarial "que esto no sirva de comodín para blanquear otra cosa"
   destapó un defecto real que el test positivo no veía.
2. **Ejecutar el camino modificado de punta a punta**, no solo su función. Al
   relajar una barrera de aprobación quedó un hueco por el que, si el
   verificador se caía, la respuesta salía sin auditar: pasaba todos los tests
   unitarios y lo detectó un test de integración ajeno.
3. **Preguntarse qué asume el cambio que antes no se asumía.** Casi todos mis
   fallos fueron una suposición nueva no comprobada: que una cita identifica un
   solo fragmento, que la última frase de un tramo es la única afirmación, que
   ausencia de bloqueantes significa que no hay problemas.

Dos errores de método concretos que conviene no repetir. Uno: escribir
aserciones autorreferenciales, del tipo `assert "texto" not in contenido`
cuando el comentario que acabo de insertar menciona ese mismo texto — falla
sola y, peor, aborta el script antes de escribir el fichero, dejando el cambio
sin aplicar y aparentando que se aplicó. Hay que afirmar sobre la
**declaración o el uso** (una regex de `^\s*--variable:` o `var(--x)`), nunca
sobre la aparición de la cadena en el fichero. Y dos: no concluir con muestras
de tamaño 5; midiendo determinismo, n=5 dio el resultado contrario que n=10.
