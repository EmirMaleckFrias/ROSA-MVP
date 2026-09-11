---
name: expresion-geo
description: Analizar una serie de expresion de GEO en formato largo (una fila por sonda y muestra): colapsar sondas a genes, normalizar, comparar grupos, correlacionar con variables clinicas. Se activa cuando el dataset o el plan mencionan GEO, GSE, sondas, microarray, expresion, RNA-seq, Illumina o Affymetrix.
activa_si: gse, geo, sonda, probe, microarray, expresion, rna-seq, illumina, affymetrix, transcrit, gpl
paquetes: pandas, numpy, scipy, statsmodels
---

# Expresion GEO en formato largo

Lo aprendido con GSE1297 (Blalock 2004), GSE29378 (Miller 2013) y GSE36980
(Hokama 2014), las tres reproducciones superadas de la puerta.

## Antes de calcular

1. Leer la cabecera y una muestra de filas; comprobar las columnas que el
   plan nombra. Un dataset largo trae al menos: muestra, grupo, sonda o
   cluster, gen, expresion.
2. Saber en que escala esta la expresion. Illumina y Affymetrix 3' (GEO
   "series matrix") suelen venir en escala lineal ya normalizada por
   cuantiles; Affymetrix Gene 1.0 ST viene en log2 (RMA). Las razones
   AD frente a control se calculan en escala lineal (2 elevado al valor si
   esta en log2). No transformar dos veces.
3. Sondas sin simbolo de gen se descartan (como hacen los articulos).
4. Varias sondas por gen: elegir la de mayor expresion media sobre TODAS las
   muestras (collapseRows), salvo que el plan diga otra cosa. Escribir en un
   comentario que regla se uso.

## Comparaciones

- Dos grupos: t de Welch para independientes; t pareada si CA1 y CA3 (u
  otras dos regiones) vienen del mismo sujeto (columna sujeto).
- Correlacion con variable clinica (MMSE, Braak, NFT): Pearson por gen, y
  el numero de genes que pasan un umbral se compara con lo publicado.
- Expresion relativa (% del grupo control): 100 por media(AD) entre
  media(control) en escala lineal, por gen; la media de varios marcadores es
  la media aritmetica de los porcentajes.
- Cambio de expresion ("fold change"): media(grupo A) entre media(grupo B)
  en escala lineal; un valor negativo publicado (-1,44) significa B mayor
  que A (1/1,44 = 0,69).

## Salida

`RESULTADO valor_reproducido=<numero>` cuando es una reproduccion, mas las
cifras agregadas (n por grupo, estadistico, p). `BASELINE` con un gen de
referencia o un contraste publicado secundario; `CONTROL` con las etiquetas
de grupo barajadas con la semilla fija. `NO_EVALUABLE` solo si faltan
columnas o filas, nunca por dudas del metodo.
