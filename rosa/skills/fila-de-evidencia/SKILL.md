---
name: fila-de-evidencia
description: La forma obligatoria de una afirmacion de tipo dato (la "fila de evidencia" de Claude Science): identificador estable, diseno, poblacion, n, intervencion o exposicion, comparador, desenlace, efecto con unidad, incertidumbre, limitaciones y la afirmacion exacta que sostiene. Se activa al extraer o verificar afirmaciones y al escribir el dossier.
activa_si: afirmacion, extraer, extraccion, verificar, cita, pasaje, dossier, evidencia
---

# Fila de evidencia

Cada afirmacion de tipo dato lleva:

| Campo | Que es | En Rosa |
| --- | --- | --- |
| Identificador | DOI, PMID, NCT o accession | fuente.doi, pmid, nct |
| Diseno | cohorte, casos y controles, ensayo, transversal, preclinico, revision | fuente.tipoEstudio |
| Poblacion | quien se midio (portadores APOE4, edad, estadio) | afirmacion.cohorte y texto |
| n | tamano muestral del dato | afirmacion.n |
| Exposicion o intervencion | que se comparo | texto |
| Comparador | contra que | afirmacion.comparador |
| Desenlace | que se midio y en que unidad | texto, nivelMedicion |
| Efecto | la cifra con su unidad tal como aparece | afirmacion.efecto |
| Incertidumbre | intervalo, desviacion o p | afirmacion.incertidumbre |
| Limitaciones | lo que el propio articulo o el diseno no permiten | sinResolver |
| Afirmacion que sostiene | la frase exacta de la hipotesis que apoya | texto y cita con pagina |

Reglas: la cifra del texto tiene que estar en el pasaje citado con la misma
unidad (la regla `cifras_fuera_del_pasaje` lo comprueba); una frase de la
discusion es interpretacion del autor, no una medida; no citar por parecido
de titulo; separar el texto de la fuente de la sintesis de Rosa.
