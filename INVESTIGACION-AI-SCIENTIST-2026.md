# Lo que le falta a un AI scientist profesional, verificado, y lo que ROSA2018 tomo

Investigacion del 14 de septiembre de 2026. Punto de partida: un informe
externo (elaborado con Codex) con quince huecos entre el MVP de ROSA2018 y "un
sistema de investigacion asistida por IA en operacion profesional", cuatro
cosas que no conviene hacer y un orden de ataque. Antes de aplicar nada se
verificaron sus afirmaciones contra las fuentes primarias con cuatro
busquedas independientes (PRISMA y riesgo de sesgo; sellado externo y
RO-Crate; ontologias, context rot, laboratorios autonomos, descubrimiento
causal, ALCOA+, MLE-bench, diseno experimental bayesiano; y el mapa del
codigo de ROSA2018 hueco por hueco). Cada afirmacion de este documento lleva su
fuente. Lo que el informe decia y no se sostiene esta marcado como tal.

## 1. Correcciones al informe externo

1. **PRISMA 2026 no existe como declaracion publicada.** La unica fuente que
   describe un "item 8b" con salida JSON del diagrama es una pagina de CASRAI
   sin DOI ni revista. PubMed devuelve cero resultados para "PRISMA 2026";
   prisma-statement.org sigue con PRISMA 2020 como guia vigente y lista la
   actualizacion sobre IA como "en desarrollo"
   (https://www.prisma-statement.org/extensions). Lo que si existe: PRISMA
   2020 (Page y otros, BMJ 2021;372:n71), las variables oficiales del
   diagrama de flujo en el paquete R PRISMA2020
   (https://github.com/prisma-flowdiagram/PRISMA2020), la extension PRISMA-LSR
   para revisiones vivas (Akl y otros, BMJ 2024;387:e079183) y la propuesta
   PRISMA-trAIce para declarar la IA usada (Holst y otros, JMIR AI
   2025;4:e80247), no endosada por el ejecutivo PRISMA.
2. **HGNC tiene limite documentado** de 10 peticiones por segundo y bloquea
   la IP al excederlo (https://www.genenames.org/help/rest/); `search` no
   devuelve el registro completo, hay que encadenar `fetch`.
3. **OxO ya es OxO2** (SSSOM y Datalog); la via principal para cruzar
   identificadores de enfermedad son las xrefs de MONDO con predicado
   `equivalentTo` (https://www.ebi.ac.uk/ols4/api/ontologies/mondo/terms).
4. **DrugBank no es una opcion abierta**: API comercial y descargas
   academicas pausadas (go.drugbank.com/releases/latest). Alternativas
   abiertas: ChEMBL y PubChem (ya en ROSA2018), ChEBI por OLS4 y RxNav.
5. **Laboratorios autonomos**: la revision de Tobias y Wahab (Royal Society
   Open Science 2025, PMC12368842) dice que la mayoria esta en el nivel 3 de
   la escala de Beal y Rogers (Mol Syst Biol 2020, PMC7744957) y que ninguno
   pasa del 4; "la mayoria en 2 y 3" viene de blogs. "El middleware es el
   cuello de botella" es de blogs; la literatura revisada habla de
   interoperabilidad y estandares (Lee y otros, Materials Horizons 2026;
   Canty y Abolhasani, Nature Reviews Chemistry 2026).
6. **MLE-bench**: el "orden de magnitud entre andamiajes" se cumple entre
   AIDE y MLAB (8,7 % frente a 0,8 % de medallas con GPT-4o), no frente a
   OpenHands (4,4 %) (Chan y otros, ICLR 2025, arXiv:2410.07095).
7. **Context rot**: el informe de Chroma (2025) no formula "presupuesto por
   rol" ni "seleccion hibrida"; mide degradacion con la longitud, el efecto de
   distractores y la mejora al barajar el pajar. Lo mas cercano al presupuesto
   es el "attention budget" de Anthropic (2025). Continuaciones de 2026: Xia
   y otros (arXiv:2606.29718) y Martin y Roger (arXiv:2605.12366).
8. **Riesgo de sesgo con LLM**: los estudios de 2025 y 2026 (Nyrhi, eBioMedicine
   2026; Cochrane ESM 2025; PLoS One 2026; Forero, JAMIA 2025) dan acuerdo
   bajo cuando se pide el juicio directo (kappa de 0,06 a 0,5). Huang y otros
   (JMIR 2025;27:e70450) encuentran 83 % de exactitud a nivel de pregunta de
   senalizacion y una subida de 55 a 95 % en un dominio al derivar el juicio
   por algoritmo. Eso cambia el diseno: preguntas cerradas y veredicto por
   regla, no juicio global.

Lo que si se sostiene: los instrumentos RoB 2, ROBINS-I (ya en V2, seis
dominios, noviembre de 2025), QUADAS-2 (y QUADAS-3 en 2026), ROBIS y AMSTAR
2; RFC 3161 con autoridades publicas gratuitas; OSF inmutable tras registrar;
RO-Crate 1.2 con los perfiles Workflow Run (Leo y otros, PLOS One 2024) y la
fusion de procedencia computacional y experimental (Ott y otros, J Integr
Bioinform 2025); las cifras del descubrimiento causal en biologia (Yeo y
Selvarajoo, Briefings in Bioinformatics 2026: ROCAUC 0,65 a 0,73 en CRISPR
humano, recomendacion de embeber la estructura conocida como restriccion);
ALCOA+ segun PIC/S PI 041-1; y la advertencia de que ganancia de informacion
no es utilidad de decision (Rainforth y otros, Statistical Science 2024;
Huang y otros, arXiv:2411.02064; Action-BED, arXiv:2606.23662).

## 2. Lo que se implemento, hueco por hueco

| Hueco | Estado antes | Lo que hay ahora | Donde |
|---|---|---|---|
| H01 Normalizacion a ontologias | Nodos de texto; conectores a OLS4, UniProt, GO, CL sin usar en el modelo de mundo | Diccionario curado del dominio sin red (MONDO, CL, UBERON, GO, ChEBI, HGNC) mas HGNC REST para genes con cache en el estado; cada hecho e hipotesis lleva `entidades`; dos hipotesis con dos identificadores en comun generan una pista de redundancia; los nodos causales llevan `idCanonico`; el modelo de mundo se busca por identificador o alias | `rosa/ontologias.py`, `rosa/bucle/pasos.py`, `rosa/causal.py` |
| H02 Conjunto dorado y calibracion | Panel con fallos plantados, sin kappa, sin etiquetas humanas | Kappa de Cohen, ponderado y AC1 de Gwet; conjunto dorado etiquetable desde cada comprobacion del Killer; kappa por comprobacion en Calidad; el panel reporta kappa por decision y por comprobacion; incidencia si cambia el modelo del juez o cae el acuerdo | `rosa/acuerdo.py`, `rosa/acuerdo_dorado.py`, `rosa/evaluacion/panel_killer.py` |
| H03 Politica de contexto | Sin presupuesto por rol; tokens estimados como entrada/8 | Presupuesto de tokens de entrada por rol (`TOKENS_MAX_POR_ROL`) con recorte registrado como compactacion; tokens reales de la ultima llamada y maximo de la corrida; cada decision del Killer guarda cuantos hechos habia; Calidad muestra el acuerdo por tramo de tamano del modelo de mundo | `rosa/politicas.py`, `rosa/bucle/pasos.py`, `rosa/modulos/contador.py` |
| H04 Concurrencia | Un escritor, sello de version en hipotesis; sin documentar | Documentado en README (reglas de aislamiento y conflicto); transaccion unica estado mas registro; rollback en el mismo diccionario | `rosa/estado/almacen.py`, README |
| H05 Riesgo de sesgo | Juicio libre del juez, sin consecuencia | RoB 2, ROBINS-I V2, QUADAS-2, ROBIS y SYRCLE con preguntas de senalizacion; el juez responde con cita y la regla del instrumento pone el veredicto; `sesgo_evidencia` sale de ahi y suspende si toda la evidencia primaria es de riesgo alto; GRADE recibe el recuento | `rosa/sesgo.py`, `rosa/killer.py` |
| H06 PRISMA | Contadores sin motivos de exclusion ni exportacion | Excluidos con motivo en el cribado; exportacion PRISMA 2020 con las variables oficiales del diagrama, items 6, 7, 8, 16a y 16b, PRISMA-LSR y declaracion trAIce (modelos, hash de prompts, umbral, revision humana, kappa) | `rosa/prisma.py`, `GET /api/corridas/{id}/prisma` |
| H07 Prerregistro externo | Inmutable pero interno | Sello RFC 3161 con freeTSA, DigiCert y Sectigo al asignar el experimento, verificable con OpenSSL; boton para repetirlo; va en el dossier y en el RO-Crate | `rosa/sello.py` |
| H08 Valor de la informacion | `decisionQueCambia` en texto libre | Sin cambio: se deja para despues del primer ciclo real, como pide el informe; la advertencia de que informacion no es utilidad queda documentada | PENDIENTE.md |
| H09 Conocimiento tacito | Memoria del proyecto generica | Clase de evidencia `conocimiento_operativo` con formulario propio; ROSA2018 lo lee al planificar experimentos y lo cita aparte en el dossier | `rosa/estado/acciones.py`, Objetivo y datos |
| H10 ELN y LIMS | Fichero subido, identidad de muestras en texto | Sin integracion (el informe pide definir el contrato con el laboratorio concreto antes); el RO-Crate tipa el experimento como LabProcess para cuando exista | PENDIENTE.md |
| H11 Ensayo en seco | No existia | Tabla sintetica con la forma del dataset; el plan congelado corre y se repara ahi antes de tocar los datos reales | `rosa/sintetico.py`, `rosa/bucle/analisis.py` |
| H12 Nivel de autonomia | Dial por clase de accion, sin etiqueta hacia fuera | Nivel 2 de 5 declarado con la escala de Beal y Rogers, en Ajustes y en cada dossier | `rosa/politicas.py`, `rosa/dossier.py` |
| H13 Coste por decision | Coste por llamada y por corrida | Coste total (modelo mas horas de revision a tarifa declarada) por dossier, por candidata y por decision humana, con tendencia por iteracion | `rosa/costes.py`, Calidad |
| H14 Procedencia estandar | Libro propio de ROSA2018 | RO-Crate 1.2 (perfil Process Run Crate 0.6) con PROV-JSON, sellos RFC 3161 dentro y README de verificacion; datasets referenciados por sha256 | `rosa/rocrate.py`, `GET /api/hipotesis/{id}/rocrate` |
| H15 ALCOA+ | Registro solo de anadir sin cadena | Cadena de hashes en el registro de acciones, en la misma transaccion que el estado, verificable en Ajustes; firma electronica y validacion del sistema quedan para un destino regulado | `rosa/estado/almacen.py` |

## 3. Lo que no se hizo, a proposito

- Descubrimiento causal desde datos: la revision de 2026 lo descarta para
  biologia; ROSA2018 embebe la estructura conocida como restriccion (base curada)
  y llama a su modulo por lo que es, un comprobador heuristico de supuestos.
- Entrenar un modelo propio: el valor esta en el andamiaje.
- Autonomia total: ROSA2018 declara el nivel 2 y no pretende pasar del 3.
- Microservicios: un almacen autoritativo y una aplicacion modular.

## 4. Fuentes

- Page y otros, PRISMA 2020, BMJ 2021;372:n71 (PMC8005924).
- Akl y otros, PRISMA-LSR, BMJ 2024;387:e079183 (PMC12036629).
- Holst y otros, PRISMA-trAIce, JMIR AI 2025;4:e80247 (PMC12694947).
- Sterne y otros, RoB 2, 2019 (riskofbias.info); ROBINS-I V2, noviembre de 2025 (riskofbias.info/welcome/robins-i-v2); QUADAS-2 (Bristol); ROBIS 1.2 (Bristol); Shea y otros, AMSTAR 2, BMJ 2017;358:j4008; Hooijmans y otros, SYRCLE, BMC Med Res Methodol 2014;14:43.
- Nyrhi y otros, eBioMedicine 2026 (PubMed 41905260); Huang y otros, JMIR 2025;27:e70450; Cochrane ESM 2025 (PubMed 40908961); PLoS One 2026 (PMC13349098); Forero y otros, JAMIA 2025 (PubMed 40680299).
- Cohen 1960 y 1968; Landis y Koch 1977; Gwet 2008.
- RFC 3161 (rfc-editor.org/rfc/rfc3161); freeTSA (freetsa.org); DigiCert (timestamp.digicert.com); Sectigo (timestamp.sectigo.com). OSF API v2 (developer.osf.io). OpenTimestamps (opentimestamps.org).
- RO-Crate 1.2 (researchobject.org/ro-crate/specification/1.2); Leo y otros, PLOS One 2024, doi 10.1371/journal.pone.0309210; Ott y otros, J Integr Bioinform 2025, doi 10.1515/jib-2025-0050; W3C PROV-O y PROV-JSON.
- HGNC REST (genenames.org/help/rest); UniProt REST (rest.uniprot.org); OLS4 (ebi.ac.uk/ols4); QuickGO; RxNav. Dobbins, Research Synthesis Methods 2025, doi 10.1017/rsm.2025.9; OntologyAligner, arXiv:2609.10055; The Gene Ontology knowledgebase in 2026, NAR 54(D1).
- Chroma, Context Rot, 2025 (trychroma.com/research/context-rot); Anthropic, Effective context engineering, 2025.
- Beal y Rogers, Mol Syst Biol 2020 (PMC7744957); Tobias y Wahab, R Soc Open Sci 2025 (PMC12368842); Tom y otros, Chem Rev 2024, doi 10.1021/acs.chemrev.4c00055.
- Yeo y Selvarajoo, Briefings in Bioinformatics 27(2):bbag127, 2026.
- PIC/S PI 041-1 (2021), seccion 7.5 (ALCOA+).
- Chan y otros, MLE-bench, ICLR 2025, arXiv:2410.07095.
- Rainforth y otros, Modern Bayesian Experimental Design, Statistical Science 2024; Huang y otros, arXiv:2411.02064; Rossa, Phillips y Rainforth, Action-BED, arXiv:2606.23662.
