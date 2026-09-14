---
name: revision-de-literatura
description: Como buscar y registrar literatura: traducir la pregunta a conceptos, sinonimos e identificadores; sintaxis por fuente; registrar cada consulta con base, filtros, fecha y numero de resultados; comprobar retractaciones y versiones; texto completo solo por vias legales. Se activa en los pasos de literatura y novedad.
contexto: literatura
activa_si: literatura, buscar, busqueda, pubmed, europe pmc, openalex, preprint, novedad, precedente
---

# Revision de literatura

Del fragmento "Literature and retrieval" de la skill general de Claude
Science, adaptado a las fuentes de Rosa.

- Traducir la pregunta a: conceptos, sinonimos, identificadores (gen,
  MONDO), poblacion, exposicion, comparador, desenlace, metodo, fechas.
- Usar la sintaxis de cada fuente (MeSH en PubMed; `SRC:PPR` en Europe PMC
  para preprints; filtros de OpenAlex).
- Registrar cada consulta material: base, consulta exacta, filtros, fecha y
  numero de resultados (Rosa lo hace en `fuente.consultas` y en los
  registros de consulta de los conectores).
- Revisiones sistematicas para mapear el campo; estudios primarios y
  registros oficiales para sostener afirmaciones concretas.
- Comprobar retractaciones (Crossref) y si un preprint ya se publico
  (conector `biorxiv_preprint`).
- Texto completo solo por vias legales: Unpaywall, Europe PMC, PDF que
  aporte la persona. Si solo hay resumen, decirlo y limitar la afirmacion.
- Para cada fuente retenida, la fila de evidencia (skill
  `fila-de-evidencia`).
