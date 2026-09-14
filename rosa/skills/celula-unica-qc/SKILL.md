---
name: celula-unica-qc
description: Control de calidad de datos de celula unica (scRNA-seq, snRNA-seq) en formato h5ad con las practicas de scverse: metricas por celula, filtrado por desviacion absoluta mediana (MAD), filtrado de genes, y resumen por tipo celular. Se activa con h5ad, anndata, celula unica, single-cell, snRNA, SEA-AD, CELLxGENE, scanpy.
contexto: analisis
activa_si: h5ad, anndata, celula unica, single-cell, single cell, snrna, scrna, sea-ad, cellxgene, scanpy, tipo celular
paquetes: scanpy, anndata, numpy, pandas, scipy
entorno: celula_unica
---

# Control de calidad de celula unica

Basado en la skill `single-cell-rna-qc` de Anthropic (Apache-2.0) y en las
guias de scverse. Exige la imagen del sandbox `celula_unica` (scanpy,
anndata); el plan debe declararlo en `entorno`.

1. Cargar con `anndata.read_h5ad`; comprobar que `adata.X` son cuentas
   crudas (enteros) o, si esta normalizado, decirlo y no volver a normalizar.
2. Metricas por celula con `scanpy.pp.calculate_qc_metrics`: cuentas
   totales, genes detectados, fraccion mitocondrial (genes `MT-`),
   ribosomal (`RPS`, `RPL`), hemoglobina (`HB[^P]`).
3. Filtrado por MAD: una celula es atipica si esta a mas de 5 MAD en log1p
   de cuentas o de genes, o a mas de 3 MAD en fraccion mitocondrial; corte
   duro de mitocondrial al 8 % para tejido nervioso (snRNA-seq: mas bajo,
   los nucleos casi no tienen ARN mitocondrial).
4. Filtrar genes presentes en menos de 20 celulas.
5. Informar antes y despues: numero de celulas, genes, medianas.
6. Para comparar grupos (AD frente a control) por tipo celular: pseudobulk
   por donante y tipo celular (sumar cuentas), despues la prueba entre
   donantes, nunca entre celulas (las celulas de un donante no son
   independientes).

Salida: `RESULTADO` con celulas antes y despues, genes, mediana de cuentas,
fraccion mitocondrial mediana, y la cifra del plan.
