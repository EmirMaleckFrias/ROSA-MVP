# Pendiente para la siguiente sesion

Acordado el 10 de septiembre de 2026 a partir de la revision "Closing the
Loop in AI-Driven Biomedical Discovery" (Fang, Li, Noori, Fesser, Zitnik;
Preprints 2026, doi 10.20944/preprints202608.2107.v1).

## Hechos el 11 de septiembre de 2026

1. Prerregistro: al asignar un experimento a un laboratorio, congelar
   hipotesis, protocolo, criterio de exito y refutacion con fecha, como
   artefacto inmutable. Reportar despues que fraccion se sostuvo.
2. El plan de cada iteracion elige acciones por lo que discriminan entre las
   hipotesis vivas (ganancia de informacion), no solo por las preguntas
   abiertas. Cambio en la firma `ProponerPlan`.
3. Version del arnes en cada corrida: commit de git y hash de las firmas
   DSPy, para auditoria.

Los tres estan implementados: `asignar_experimento` congela el
prerregistro como artefacto (misma regla en `acciones.ts`); `ProponerPlan` y
`GenerarConsultas` reciben `hipotesis_vivas` con certeza, direccion, lo mas
fragil y que las subiria o bajaria; `rosa/version.py` guarda commit, hash de
firmas y programas optimizados en cada corrida nueva (`arnes`).

## Siguiente MVP

4. Cerrar el loop con el verificador duro: cuando llegan datos del
   laboratorio (`registrarDatosExperimento`), Rosa actualiza certeza y
   direccion de la hipotesis con esa evidencia.
5. Analisis de datos sobre datasets adjuntos, en entorno aislado, con la
   cifra ligada a su trayectoria.

## Evaluacion

6. Tres niveles: retrospectiva (redescubrir hallazgos posteriores al corte
   de los modelos ocultandolos en la busqueda), de loops (si Rosa revisa
   hipotesis cuando la evidencia la contradice; metrica: campo `cambio` de
   la conclusion) y prospectiva (prerregistrada).

## Tambien

- Adoptar el vocabulario del paper en la documentacion: loop, campana,
  verificador blando y duro, creencia sobre hipotesis en competencia.
- Revisor independiente del generador para la evaluacion de supuestos.
- Clasificar las citas de cada hecho del modelo de mundo en apoya, menciona,
  contrasta (campo `citas`, hoy vacio).
- Nada esta en git todavia; el escaneo de secretos esta limpio.
- Rotar el token de Convex que aparecio en el chat.
