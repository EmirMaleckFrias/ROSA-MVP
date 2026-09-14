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

## Tildes en los textos visibles

Los textos de la interfaz llevan tilde. `python3 scripts/acentuar.py`
(desde `frontend/`) recorre `src/` con un diccionario cerrado de palabras
(`PALABRAS`, conservando mayusculas) y acentua solo lo que se ve: texto JSX
entre etiquetas, atributos de texto (`titulo`, `nota`, `placeholder`,
`aria-label`, `title`...), cadenas largas que empiezan por mayuscula y los
valores de los diccionarios de etiquetas (`lib/etiquetas.ts`,
`lib/glosario.ts`...). No toca identificadores, claves, rutas, clases ni
valores que se comparan con el servidor (`'sistematica'`, `'vacio'`: si el
script los acentuara, `tsc` lo avisa porque son tipos literales). Las palabras
que cambian de significado con la tilde (esta/está, como/cómo, que/qué,
solo/sólo, paso/pasó) quedan fuera a proposito, y tambien las que son
sustantivo o verbo segun la tilde (valido/validó, critico/criticó,
publico/publicó, cortes/cortés): la primera pasada convirtio "se le critico"
en "se le crítico" y "cambian los cortes" en "cambian los cortés", asi que
esas se escriben a mano. Las palabras con ñ van en el mismo diccionario
(campaña, pestaña, añadir, señal, diseño, compañero...). En `datos/muestra.ts`,
`datos/simulacion.ts`, `datos/acciones.ts` y `datos/almacen.ts` se acentua
cualquier cadena con un espacio y sin pinta de codigo (eventos, avisos, datos
de muestra); una clave o una ruta nunca llevan espacio. Los textos que genera
el backend en Python (eventos, dossier, pistas) no pasan por este script: alli
las mismas palabras viven en claves, expresiones regulares y textos, y hace
falta una pasada aparte con mas cuidado.

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
