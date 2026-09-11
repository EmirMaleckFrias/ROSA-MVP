# Pendiente para la siguiente sesion

Actualizado el 11 de septiembre de 2026. El plan completo por etapas esta en
`PLAN-ROSA2018.md`; esto es la lista corta de lo inmediato.

## Hecho el 11 de septiembre (ROSA2018)

- Mision con areas de investigacion y pregunta de campana; politicas en
  codigo; tarjeta y versiones de hipotesis; Hypothesis Killer con decision
  por regla, reformulacion y auditoria de descartes; registro de decisiones;
  datasets con libro de procedencia y hash; puerta de reproduccion; analisis
  in silico con plan congelado, sandbox, interpretacion y auditor; bloqueos
  no compensables, candidatas y dossier; retorno con seis clases y
  dimensiones; registro de aprendizaje en tres niveles con evaluacion sobre
  conjunto reservado; registro de metodos; recalculo con informe de
  diferencias al cambiar el estado editorial de una fuente; presupuesto en
  dolares y horas; documentos recuperados como datos.
- Los puntos 1 a 5 de la lista anterior (prerregistro, plan por ganancia de
  informacion, version del arnes, cierre del loop con datos, analisis en
  entorno aislado) estan cubiertos.

## Datos: solo publicos por ahora

Decision de la persona responsable del programa (11 de septiembre): no se
piden accesos controlados (ADNI, AD Knowledge Portal, dbGaP). Rosa trabaja
con datos publicos: GEO, SEA-AD procesado (abierto) y OASIS (registro
gratuito). El libro de procedencia y la regla de no enviar filas al modelo
siguen activos para cuando entren datos controlados.

## Inmediato

1. Puerta de reproduccion con datos publicos: 1 de 3 superada. GSE1297
   (Blalock 2004) esta cargado con llamadas de deteccion y libro de
   procedencia; el algoritmo completo del articulo (leido del PDF) reproduce
   la cifra publicada (418 frente a 431, tolerancia 20 %). Faltan dos:
   OASIS-1 (volumen cerebral por CDR, un p-valor; registro gratuito) y otro
   GEO del Alzheimer (GSE5281, GSE48350, GSE44770). Ver
   `ESTADO-ROSA-2026-09-11.md`, seccion 6.
2. SEA-AD procesado: agregar por donante (los ficheros pesan de 1 a 33 GB;
   Rosa admite 50 MB) antes de subirlo.
3. Asignar responsables en la mision (patrocinador, lider cientifico,
   metodos, datos, ingenieria, laboratorio, evaluacion).
4. Alinear con la persona responsable del documento de concepto los nombres
   de los registros (ver `PLAN-ROSA2018.md`, introduccion).

## Codigo (orden del plan, seccion 4)

6. Panel de prueba del Killer: 20 hipotesis buenas, 20 con fallo plantado, 20
   grises con veredicto humano; metricas de deteccion por tipo de fallo y de
   abstencion. Rechazar todo no puede puntuar bien.
7. Misma cohorte por autores, centro, periodo y n (hoy solo por nombre y
   NCT); comprobaciones automaticas de unidades y direccion invertida.
8. Bradley-Terry con intervalos por bootstrap en el ranking; Elo solo como
   vista. Valor esperado de la informacion como desempate.
9. Jerarquia programa, areas, campanas, preguntas en la interfaz; reasignacion
   entre areas; reapertura de areas pausadas con condicion.
10. Motor causal minimo: aristas del modelo de mundo tipadas como supuesto o
    inferencia con evidencia, con contexto; consultas que devuelven cantidad,
    supuestos, evidencia, metodo, incertidumbre y limites, o "sin resolver".
11. Importar el protocolo real y las desviaciones; identidad de experimento y
    muestra; enmiendas fechadas.
12. Las cuatro condiciones de comparacion y los cinco niveles de prueba del
    plan completo (seccion 7); replay historico con evidencia fechada.
13. Repeticiones con semillas distintas en el sandbox cuando el plan tenga
    aleatoriedad; e-valores para agregar pruebas por hipotesis (Popper).

## Tambien

- Clasificar las citas de cada hecho del modelo de mundo en apoya, menciona,
  contrasta (campo `citas`, hoy vacio).
- Rotar el token de Convex que aparecio en el chat.
- Las corridas anteriores a septiembre no tienen `arnes` ni `pregunta`.
