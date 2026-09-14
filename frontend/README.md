# Frontend de Rosa

La interfaz web de Rosa: la vista de una corrida de dias, la cola de revision
de hipotesis con procedencia, el ranking, el explorador del modelo de mundo,
los artefactos versionados, el tablero de calidad y los ajustes. Sigue
`UI-ROSA.md` patron por patron.

## Arrancar

```
npm install
npm run dev        # http://localhost:5174
npm test           # vitest: logica pura y acciones
npm run typecheck  # tsc estricto
npm run build      # produccion en dist/
```

## Estado actual: datos de muestra

Rosa todavia no tiene bucle ni servidor. La interfaz arranca con datos de
muestra del dominio (`src/datos/muestra.ts`) y una corrida que avanza sola
(`src/datos/simulacion.ts`) para poder construirla y juzgarla en vivo. La
cabecera lo dice ("Datos de muestra") y cada pantalla lleva el aviso.

Para conectar Rosa de verdad se cambia un solo modulo, `src/datos/almacen.ts`:
`useRosa()` pasa a leer las suscripciones del servidor (Convex, o Postgres con
suscripciones; decision pendiente) y cada funcion de `acciones` pasa a llamar
a su mutacion, con las mismas firmas. Las pantallas no cambian. Los tipos del
contrato estan en `src/datos/tipos.ts`.

## Como esta organizado

- `src/datos/`: tipos del dominio, muestra, acciones puras (con tests),
  simulacion (con tests) y el almacen reactivo.
- `src/lib/`: logica pura sin React, cada modulo con su test: formato de
  numeros y tiempos, rutas, orden de la cola y del ranking, resumen de la
  verificacion, diff por lineas, etiquetas de cada estado.
- `src/componentes/`: piezas reutilizables: tarjeta de permiso, plan en vivo
  con pistas y transcripcion, verificacion plegable, tarjetas del revisor,
  comentarios anclados, cajon de procedencia de seis pesta�as.
- `src/pantallas/`: una por pantalla.
- `src/styles.css`: el sistema visual, heredado del RAG, con el morado del
  arbol del Alzheimer Project como acento. Claro y oscuro via `data-theme`.

## Reglas que la interfaz hace cumplir

- Una hipotesis no entra al modelo de mundo como aceptada sin pasar por la
  cola, y no se puede aceptar con afirmaciones bloqueantes ni hallazgos
  abiertos del revisor (`motivoNoAceptable`).
- Descartar exige motivo, y el motivo queda en el modelo de mundo.
- Las tarjetas de permiso llevan el nombre exacto del recurso y los alcances
  elegibles; lo concedido con alcance mayor que "una vez" se lista y se revoca
  en Ajustes.
- `sin_verificar` se pinta como aviso, nunca como aprobado. Arriba se resume
  el fallo, no el acierto.
- Los comentarios se anclan a una seleccion de texto, se acumulan como
  pendientes y salen juntos a Rosa con el siguiente mensaje.
- Nada de confirmaciones del navegador: las decisiones irreversibles se
  confirman inline, en dos pasos.


## Conexion con el servidor de Rosa

Al arrancar, `src/datos/almacen.ts` pide `/api/estado`. Si el servidor de Rosa
responde (`uv run python -m rosa.main`, puerto 8765; Vite reenvia `/api`), la
interfaz entra en modo servidor: el estado llega por Server-Sent Events
(`/api/eventos`, el estado completo en cada cambio) y cada accion se aplica al
instante con el reducer local y se envia por `POST /api/acciones/{nombre}`. Si
el servidor no responde, sigue con los datos de muestra y la simulacion, y lo
avisa en la franja amarilla. Las pantallas no distinguen un modo del otro.

## Rework del 14 de septiembre de 2026: movimiento con significado

La interfaz explica el proceso por si misma. Lo que cambio y donde tocar:

- **Hilo del proceso** (`src/componentes/HiloDelProceso.tsx`): las siete
  etapas (plan, literatura, verificar, modelo de mundo, hipotesis y Killer,
  candidatas, laboratorio) siempre visibles bajo la cabecera, con la activa
  latiendo, las hechas apagadas y lo que espera a una persona marcado. Se
  deriva del estado con `estadoDelHilo`, sin inventar nada.
- **Recorrido de primera vez** (`src/componentes/Recorrido.tsx`): cinco
  pasos; aparece una vez (clave `rosa.recorrido.v1` en el navegador) y vuelve
  desde el boton `?` de la cabecera o desde Ajustes.
- **Deshacer** (`src/componentes/Deshacer.tsx` y `programar` en
  `src/datos/almacen.ts`): aceptar, descartar o refinar una hipotesis se
  aplica al instante y viaja al servidor seis segundos despues; mientras, un
  aviso con barra de tiempo permite deshacer o enviar ya.
- **Sistema de movimiento** (`src/lib/movimiento.ts`,
  `src/componentes/Animado.tsx`, seccion 10 de `styles.css`): duraciones de
  150 a 400 ms, una sola curva, `Aparece`, `ListaAnimada` y
  `ElementoAnimado` (entrada escalonada, reordenacion con resorte, salida
  por decision: aceptar desplaza adelante, descartar apaga, refinar devuelve
  arriba), `Contador` (el Elo corre hasta su valor), `Destello`. Todo
  respeta `prefers-reduced-motion`. La libreria es Motion (`motion/react`).
- **Estados vacios que ensenan** (`Vacio` con `pasos` y `accion` en
  `piezas.tsx`) y **secciones que entran al aparecer** (`Seccion`).
- Cambio de pantalla con fundido (`App.tsx`), pistas con franja de actividad
  y pasos que se iluminan (`PlanEnVivo.tsx`), hechos que se mueven entre
  columnas (`ModeloDeMundo.tsx`), tarjetas de inicio escalonadas.

## Menos complicado: modo Sencillo y Detalle (14 de septiembre de 2026)

- **Interruptor en la cabecera** (`src/lib/modo.ts`): en Sencillo, las
  secciones marcadas `detalle` (ingenieria y auditoria: hashes, tolerancias,
  kappa, entorno, conectores, politicas) quedan plegadas tras una linea de
  resumen, y cada nota larga se reduce a su primera frase. En Detalle se abre
  todo. Se recuerda en el navegador.
- **Ayuda con glosario** (`src/lib/glosario.ts`): el boton `?` de cada
  seccion muestra la explicacion completa y define los terminos tecnicos que
  nombra (Elo, GRADE, kappa, prerregistro, puerta de reproduccion...).
- **Secciones plegables** (`Seccion` en `piezas.tsx`: `detalle`, `plegable`,
  `abierta`, `resumen`, `id`) y `SoloDetalle` para bloques que no son
  secciones (el gasto de la corrida).
- **"Que toca hacer aqui"** arriba de Objetivo y datos: mision sin aprobar,
  datasets pendientes, puerta bloqueada, sin corridas; cada cosa con su boton.
- **Formularios solo cuando hacen falta**: subir dataset y registrar una
  reproduccion viven tras un boton; el de reproduccion se abre solo si la
  puerta esta bloqueada.

## Auditoria visual (Playwright)

`npm run auditoria-visual` abre cada pantalla de Rosa en un Chromium real
(servida por el servidor de Rosa en el 8765) a cuatro anchos (1440, 1100,
800 y 420) y en los dos modos, despliega las secciones de detalle y busca lo
que las pruebas de DOM no ven: texto recortado por su caja o por un
antecesor, texto superpuesto (comparando las cajas de cada linea), texto
fuera de la ventana y scroll horizontal de la pagina. Deja capturas de
pagina completa y `informe.json` en `frontend/auditoria/` (fuera de git).
Correrla despues de cualquier cambio de estilos; el objetivo es cero.

## Tildes y ñ en los textos visibles

Todo texto en castellano de la interfaz lleva tilde y ñ (regla de Emir del
14 de septiembre de 2026: "acostúmbrate desde ahora a poner tilde y ñ a
todas las palabras que lo tengan"). Los textos nuevos se escriben ya
acentuados; `python3 scripts/acentuar.py` (desde `frontend/`) es la revisión.

Qué hace el script. Recorre `src/` con un diccionario cerrado de palabras
(`PALABRAS`, conservando mayúsculas) más cuatro reglas: toda palabra en
-ción singular lleva tilde; tras "¿" los interrogativos (qué, cómo, dónde,
cuándo, cuál, quién, cuánto) la llevan, y también "Qué" y "Cómo" al empezar
una cadena salvo que siga un artículo, un demostrativo o una mayúscula ("Que
el efecto sea independiente" es completivo); "esta" pasa a "está" solo cuando
le sigue un participio conocido, un gerundio o una palabra de estado (en,
por, ya, listo, pausada...), nunca un sustantivo ("esta corrida" se queda);
"aun" pasa a "aún" salvo en "aun así". Un texto que parece inglés (the, of,
and, with) no se toca: los títulos de artículos de la muestra siguen como
están.

Dónde mira. Texto JSX entre etiquetas, atributos de texto (`titulo`, `nota`,
`placeholder`, `aria-label`, `title`...), plantillas con texto (nunca las de
`className`, `id`, `key`, rutas), cadenas largas que empiezan por mayúscula
y, en todos los `.ts` de `lib/` y `datos/` salvo `tipos.ts`, cualquier cadena
con un espacio y sin pinta de código (una clave, una ruta o un valor que se
compara con el servidor nunca llevan espacio). No toca identificadores,
clases CSS ni valores literales de tipo (`'sistematica'`, `'vacio'`: `tsc`
avisa si los acentuara).

Qué queda fuera a propósito. Las palabras que cambian de sentido con la
tilde y no se resuelven por contexto simple: como/cómo y que/qué en medio de
una frase, solo, si/sí, paso/pasó, cambio/cambió, valido/validó,
critico/criticó, publico/publicó, cortes/cortés, este/esté. Esas se escriben
a mano (y una pasada temprana las estropeó: "se le crítico", "los cortés").
Los textos que genera el backend en Python (eventos, dossier, pistas,
frases GRADE) no pasan por este script: allí las mismas palabras viven en
claves, expresiones regulares y textos, y necesitan una pasada aparte.

Cómo se completó el diccionario. Cada palabra visible se pasó por un
diccionario de frecuencias del castellano (`pyspellchecker`, en el venv del
backend): las que solo existen con tilde entraron directamente y las que
existen de las dos formas se revisaron por contexto. El diccionario va en
líneas cortas a propósito: Python 3.9 falla con "Non-UTF-8 code" en líneas de
miles de caracteres con tildes.

Guardas. `src/clases.test.ts` falla si una clase del JSX lleva caracteres
fuera de ASCII o no existe en `styles.css` (la primera pasada convirtió
`seccion` en `sección` y los estilos desaparecieron). La auditoría visual
revisa cualquier título, no solo los que están dentro de una sección.

## Si una pantalla falla al pintarse

`componentes/Limite.tsx` es un limite de error de React. Sin el, un fallo al
pintar cualquier pantalla desmonta el arbol entero y se ve la pagina vacia
(negra en tema oscuro). Con el, la barra y la cabecera siguen en su sitio y
en el hueco de la pagina aparece el mensaje del fallo con tres salidas:
volver a intentar, ir al inicio o recargar. Hay uno alrededor de cada
pantalla (`App.tsx`) y otro en la raiz (`main.tsx`).

La transicion entre pantallas es un fundido cruzado (`AnimatePresence` en
modo `popLayout`) y su clave es la pantalla, no el detalle: abrir una
hipotesis en su cajon o un artefacto no vuelve a montar la pagina. Antes la
clave incluia el detalle y el modo era `wait`, asi que al abrir una hipotesis
la pagina entera salia con fundido y volvia a entrar; medido con Playwright
(`auditoria/hueco.mjs`, fuera de git) el hueco sin pagina era de unos 105 ms
en un navegador ocioso y se alargaba cuando el navegador estaba ocupado con
el flujo de eventos del final de una corrida. Ahora es 0 ms.
