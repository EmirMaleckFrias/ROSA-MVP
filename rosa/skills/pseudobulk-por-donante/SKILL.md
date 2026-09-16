---
name: pseudobulk-por-donante
description: Comparar grupos (Alzheimer frente a control, estadio Braak alto frente a bajo) en datos de célula única públicos en h5ad (SEA-AD abierto en AWS, series GEO de snRNA-seq, colecciones de CELLxGENE) sumando las cuentas por donante y tipo celular (pseudobulk), con expresión diferencial entre donantes con pydeseq2 si está en la imagen, control de la composición celular y del efecto donante, y los límites de lo que un corte transversal permite afirmar. Se activa con pseudobulk, donante, h5ad, snRNA-seq, SEA-AD, célula única, expresión diferencial, pydeseq2, composición celular.
contexto: analisis
activa_si: pseudobulk, pseudo-bulk, donante, donantes, donor, h5ad, anndata, snrna, scrna, single-nucleus, single nucleus, single-cell, celula unica, sea-ad, cellxgene, pydeseq2, deseq2, expresion diferencial, differential expression, composicion celular, tipo celular, supertipo
paquetes: anndata, scanpy, numpy, pandas, scipy, statsmodels
entorno: celula_unica
---

# Pseudobulk por donante

Un h5ad es el fichero de AnnData: una matriz de células por genes con dos
tablas de anotación (`obs` por célula, `var` por gen). En un estudio de
célula única de Alzheimer las unidades que se comparan son los **donantes**
(las personas cuyo cerebro se secuenció), no las células: las miles de
células de un mismo donante comparten su edad, su sexo, su estadio y su
lote, así que tratarlas como observaciones independientes infla los
p-valores hasta hacer "significativo" cualquier ruido (el problema de la
pseudorreplicación, Squair et al. 2021, Nat Commun). **Pseudobulk** es la
solución estándar: sumar las cuentas de todas las células de un donante y un
tipo celular en una sola columna, y después analizar esa tabla como si fuera
una serie de expresión en tejido (bulk), con un donante por muestra.

La implementación de referencia está en `rosa/datasets_programa.py`
(`perfil_h5ad`, `pseudobulk_por_donante`, `parece_cuentas`); el sandbox no
importa `rosa`, así que el código del sandbox repite la receta de abajo.

## Cuándo se activa

- El plan o el dataset nombran un h5ad, snRNA-seq o scRNA-seq, SEA-AD,
  CELLxGENE o una serie GEO de célula única.
- La pregunta compara grupos de donantes (enfermedad frente a control,
  Braak alto frente a bajo, portadores de APOE4 frente a no portadores) por
  tipo celular, o pregunta si un tipo celular cambia de abundancia.
- Va detrás de la skill `celula-unica-qc` (control de calidad por célula) y
  antes de `expresion-geo` (que trata la tabla resultante como bulk).

## Fuentes públicas y cómo llegar a ellas

- **SEA-AD (Allen Institute)**: 84 donantes, giro temporal medio, 1,2
  millones de núcleos anotados en 139 supertipos. Los h5ad procesados están
  abiertos en AWS Open Data, bucket `s3://sea-ad-single-cell-profiling`,
  lectura sin cuenta (`aws s3 cp --no-sign-request`), unos 3 GB el conjunto
  principal, con la anotación de los autores (`Subclass`, `Supertype`,
  `Donor ID`, `Braak`, `CERAD score`, `Overall AD neuropathological Change`,
  `Cognitive Status`, `Continuous Pseudo-progression Score`, entre otras;
  comprobar los nombres con el perfil del h5ad antes de usarlos). Los crudos 10x
  son de acceso controlado vía AD Knowledge Portal y el proyecto no los pide.
  Cita: Gabitto et al. 2024, Nat Neurosci, y el dataset por su URL.
- **CELLxGENE Discover**: h5ad con el esquema de CZ: cuentas crudas en
  `raw.X`, tipo celular en `cell_type` (Cell Ontology), donante en
  `donor_id`, enfermedad en `disease`. Licencia CC BY 4.0. Se llega por el
  conector `cellxgene_colecciones` y la descarga es por dataset.
- **GEO (series GSE de célula única)**: los ficheros procesados varían
  (matrices 10x, h5ad, CSV); el resumen de GEO no da donantes y hay que
  buscarlos en las columnas de metadatos. Se llega por `geo_series` y
  `geo_serie`; el registro del programa (`e["datasetsPrograma"]`) guarda lo
  que ya se sabe de cada uno.

Solo datos públicos: si el h5ad o su documentación nombran ADNI, ROSMAP,
MSBB o "controlled access", el registro lo marca como controlado y el
análisis no sigue con datos individuales.

## Método

1. **Perfilar antes de cargar.** Abrir en modo `backed="r"` (sin cargar la
   matriz) y anotar: número de células, columnas de `obs`, columna de
   donante (`donor_id`, `Donor ID`, `individualID`...), columna de tipo
   celular (`cell_type`, `Subclass`, `Supertype`...), capas (`layers`,
   `raw.X`) y si `X` son cuentas crudas (enteros no negativos en una muestra
   de células). Si `X` está normalizada y hay `raw.X`, las cuentas están en
   `raw.X`. Nunca sumar valores normalizados o en log: el pseudobulk exige
   cuentas.
2. **Elegir el nivel de tipo celular.** Con SEA-AD, `Subclass` (unas 24
   clases: Sst, Pvalb, L2/3 IT, astrocitos, microglía, oligodendrocitos...)
   da grupos con células suficientes; `Supertype` (139) deja muchos grupos
   pequeños. Declarar el nivel en el plan y no cambiarlo después de ver los
   resultados.
3. **Sumar por (donante, tipo celular).** Con una matriz indicadora
   dispersa de grupos por células multiplicada por la matriz de cuentas, sin
   densificar:

   ```python
   import numpy as np, pandas as pd
   from scipy import sparse
   validas = (obs[donante].notna() & obs[tipo].notna()).to_numpy()   # sin donante o sin tipo: fuera, no un donante "nan"
   grupos = pd.MultiIndex.from_arrays([obs[donante].astype(str)[validas], obs[tipo].astype(str)[validas]], names=["donante", "tipoCelular"])
   codigos, unicos = grupos.factorize()
   ind = sparse.csr_matrix((np.ones(len(codigos)), (codigos, np.flatnonzero(validas))), shape=(len(unicos), len(validas)))
   suma = ind @ X                      # X: cuentas crudas, células por genes (dispersa o densa)
   suma = suma.toarray() if sparse.issparse(suma) else np.asarray(suma)
   pseudobulk = pd.DataFrame(np.rint(suma).astype(np.int64), index=unicos.set_names(["donante", "tipoCelular"]), columns=genes)
   ```

   Contar cuántas células quedaron fuera por no tener donante o tipo celular y
   decirlo en el resultado.

   Excluir los grupos con menos de 10 células (la suma de pocas células es
   ruido) y decir cuántos se excluyeron y por qué. Guardar también el número
   de células por grupo: sirve de covariable y de aviso.
4. **Diseño entre donantes.** Una fila por donante y tipo celular; el
   análisis se hace **por tipo celular**, cada uno con su propio modelo. El
   grupo (enfermedad frente a control, o Braak alto frente a bajo) es la
   variable de interés; sexo, edad al morir, intervalo post mortem (PMI) y
   tecnología o lote van como covariables cuando el n lo permite (regla
   práctica: una covariable por cada 10 donantes). En SEA-AD el estadio
   continuo (CPS) permite un modelo de tendencia en vez de dos grupos.
5. **Expresión diferencial.** Con `pydeseq2` (`DeseqDataSet` con
   `counts=pseudobulk` de ese tipo celular, `metadata` por donante,
   `design="~ grupo + sexo + edad"`, después `DeseqStats`): devuelve log2 del
   cambio, p y FDR (Benjamini-Hochberg). Filtrar antes los genes con menos
   de 10 cuentas en total. Si `pydeseq2` no está en la imagen (la imagen
   `celula_unica` de hoy trae anndata, scanpy y statsmodels, no pydeseq2),
   decirlo y usar el camino de reserva: log2 de cuentas por millón con
   pseudocuenta 1, y por gen un modelo lineal de `statsmodels` con las mismas
   covariables (o t de Welch si solo hay grupo), FDR por Benjamini-Hochberg,
   declarando que el modelo de reserva no modela la sobredispersión de las
   cuentas y tiende a más falsos positivos. No mezclar los dos caminos en la
   misma conclusión.
6. **Composición celular.** Antes de leer la expresión, mirar si el grupo
   cambia la **proporción** de cada tipo celular por donante (por ejemplo,
   menos neuronas Sst en Braak alto). Calcular la fracción de cada tipo
   sobre las células del donante y comparar entre grupos con un modelo sobre
   proporciones (regresión beta o logística por donante; scCODA si está
   disponible). Un gen que "baja" en el pseudobulk de una clase que pierde
   células puede ser un artefacto de composición: decirlo cuando el tipo
   celular cambie de abundancia.
7. **Efecto donante.** Comprobar que ningún donante domina un grupo (un
   donante con el 40 % de las células de una clase arrastra la suma).
   Repetir el contraste quitando uno a uno los donantes con más células
   (leave-one-out) y informar si el signo se sostiene. Comprobar que el
   número de células por grupo no difiere entre grupos; si difiere, entra
   como covariable en log.
8. **Salida.** `RESULTADO` con: n de donantes por grupo, tipos celulares
   analizados y excluidos, genes probados, genes con FDR < 0,05 por tipo
   celular con su log2 del cambio, y la cifra que el plan pidió
   (`valor_reproducido=` si es una reproducción, por ejemplo la dirección
   en los supertipos Sst de SEA-AD). `BASELINE` con un gen de referencia sin
   cambio esperado; `CONTROL` con las etiquetas de grupo barajadas por
   donante con la semilla fija (barajar por célula anularía la prueba).

## Qué no se puede afirmar

- **Es transversal, no longitudinal.** Cada donante se mide una vez, al
  morir. "Los genes de la microglía suben con la progresión" es una lectura
  de una ordenación entre personas distintas, no de un cambio en el tiempo
  dentro de una persona; en GRADE, la dirección es "asociación", la certeza
  arranca baja por ser observacional y no sube por tamaño de efecto sin
  replicación en otra cohorte.
- **Una región.** SEA-AD es giro temporal medio; una serie GEO suele ser una
  región. No generalizar a "el cerebro".
- **Nada de causa.** Que un gen difiera entre grupos no dice si es causa,
  consecuencia o composición celular; la propuesta de experimento lo tiene
  que separar.
- **Célula por célula no vale.** Un p-valor calculado entre células (test de
  Wilcoxon de scanpy entre grupos de enfermedad) no se informa como
  evidencia entre donantes; se puede citar como exploración.
- **Muestras compartidas.** Si dos datasets vienen de los mismos donantes
  (el registro del programa lo anota en `muestrasCompartidasCon`), su
  coincidencia no es replicación independiente.
- Los núcleos casi no tienen ARN mitocondrial y pierden ARN citoplasmático:
  un gen ausente en snRNA-seq no está "apagado" en la célula.
