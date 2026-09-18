"""Tanda 2, constructor "verificacion": S-05, la comparación literal contra el
texto de un PDF con sus artefactos reales.

Lo que la tanda 1 dejó hecho (una normalización compartida, comparación por
ventanas, números de línea fuera antes de guardar la página) recuperó 289 de
las 296 afirmaciones de página bloqueadas. Esta tanda cierra lo que quedaba
abierto y lo que se rompió al intentar romperlo:

- `normalizar_texto_pdf` es la función única con nombre canónico; el nombre
  antiguo `normalizar_texto` es la misma función.
- El pasaje nunca pierde información: números sueltos, marcas de cita entre
  paréntesis y superíndices se quitan solo en variantes de la FUENTE. Antes se
  quitaban en los dos lados y "169 (94)" casaba con "169 (95)".
- Todas las ventanas tienen que estar. La tolerancia de una ventana interior
  no salvaba erratas (una palabra cambiada rompe dos ventanas) y sí dejaba
  pasar una costura de dos frases reales con la primera mitad en 10, 15 o 20
  palabras.
- El número de línea que un resumen recortado deja tras una elisión
  ("were ... 311 significantly") es un artefacto de la fuente.

Los textos de página son los que devuelve PyMuPDF sobre los PDF reales de
`pdfs/` (Belder 2026 pág. 2, Biel 2025 págs. 5 y 10, plan estadístico de
donanemab pág. 25), copiados tal cual; los tests no abren la red ni el gateway.
"""

from __future__ import annotations

import pytest

from rosa import verificador as V
from rosa.fuentes import pdf

F = V.Fragmento

# Página 2 de Belder et al., 2026 (medRxiv, 10.64898/2026.03.30.26349682) tal
# como la devuelve PyMuPDF: cada número de línea va en su propia línea.
BELDER_PAG_2_CRUDA = (
    "Abstract \n37 \n \n38 \nBackground \n39 \nAutosomal dominant Alzheimer’s disease (ADAD) serves as a model for presymptomatic \n40 \n"
    "biomarker discovery. Characterising the temporal profile of plasma biomarker levels in \n41 \n"
    "presymptomatic individuals may enhance understanding of disease pathogenesis, inform future \n42 \n"
    "clinical trials, and guide clinical interpretation. \n43 \n \n44 \nMethods \n45 \n"
    "We evaluated 124 proteins using a NUcleic acid-Linked Immuno-Sandwich Assay (NULISA) panel \n46 \n"
    "in 270 plasma samples from a longitudinal cohort study of ADAD, comprising 113 individuals (73 \n47 \n"
    "mutation carriers and 40 non-carriers). We determined the plasma proteomic changes that \n48 \n"
    "distinguished mutation carriers from non-carriers. We then used predicted age at symptom onset to \n49 \n"
    "determine the approximate timing of presymptomatic divergence in biomarker levels in carriers \n50 \n"
    "relative to non-carriers. \n51 \n \n52 \nResults \n \n53 \n"
    "Nine proteins (Aβ42, BACE1, GFAP, pTau181, pTau231, pTau217, MAPT, NfL, and AChE) \n54 \n"
    "robustly differed between carriers and non-carriers, cross-sectionally. Longitudinal analyses \n55 \n"
    "showed Aβ42 levels were elevated in carriers at least 26 years before expected symptom onset. \n56 \n"
    "Carriers diverged from non-carriers in phosphorylated tau markers at 21-24 years before expected \n57 \n"
    "symptoms, total-tau at 19 years, GFAP and BACE1 at 14 years, and NfL at 6 years. Differences in \n58 \n"
    "AChE were seen in symptomatic individuals, likely reflecting cholinesterase inhibitor use. \n59 \n \n60 \n"
    "Conclusion \n61 \nMultiple plasma proteins are elevated in presymptomatic and symptomatic autosomal dominant AD \n62 \n"
    "mutation carriers relative to non-carriers. Changes in eight biomarkers occur sequentially from 26 to \n63 \n"
    "6 years prior to symptom onset. Combining biomarkers may help in staging presymptomatic AD \n64 \n"
    "and optimise clinical trial inclusion. Further work is needed to assess how these findings generalise \n65 \n"
    "to non-monogenic AD. \n66 \n \n67 \n"
    "What is already known on this topic \n68 \n"
    "The molecular pathology of Alzheimer’s disease develops many years before the onset of \n69 \n"
    "symptoms, and multiple plasma biomarkers of Alzheimer’s pathology have been identified. \n70 \n"
    "Understanding the timing of biomarker abnormality is important to guide trial design for the \n71 \n"
    "timing of interventions to prevent the onset of dementia. \n72 \n \n73 \n"
    "What this study adds  \n74 \n"
    "Using an autosomal dominant Alzheimer’s disease cohort, we identify multiple plasma \n75 \n"
    "biomarkers that distinguish mutation carriers from non-carrier familial controls and \n76 \n"
    "characterise the timing of these changes relative to symptom onset. We demonstrate that \n77 \n"
    "biomarkers show change many years before symptom onset: markers of abnormal tau \n78 \n"
    "phosphorylation more than 20 years prior, followed by markers of reactive astrocytosis and \n79 \n"
    "synaptic dysfunction approximately 15 years prior, and neurodegenerative markers within \n80 \n"
    "10 years of symptoms. \n81 \n \n82 \n"
    "How this study might affect research, practice or policy  \n83 \n"
    "Plasma biomarkers could be used in pre-clinical autosomal dominant Alzheimer’s disease to \n84 \n"
    "chart disease trajectories and predict symptom onset, allowing targeted disease-modifying \n85 \n"
    "therapy implementation and optimised clinical trial design. \n86 \n \n87 \n \n88 \n89 \n . \n"
    "CC-BY 4.0 International license\nIt is made available under a \n is the author/funder, who has granted medRxiv a license to display the preprint in perpetuity. \n"
    "(which was not certified by peer review)\nThe copyright holder for this preprint \nthis version posted March 31, 2026. \n; \n"
    "https://doi.org/10.64898/2026.03.30.26349682\ndoi: \nmedRxiv preprint \n"
)
BELDER_COPIAS = [
    "Longitudinal analyses showed Aβ42 levels were elevated in carriers at least 26 years before expected symptom onset.",
    "Carriers diverged from non-carriers in phosphorylated tau markers at 21-24 years before expected symptoms, total-tau at 19 years, GFAP and BACE1 at 14 years, and NfL at 6 years.",
    "We evaluated 124 proteins using a NUcleic acid-Linked Immuno-Sandwich Assay (NULISA) panel in 270 plasma samples from a longitudinal cohort study of ADAD, comprising 113 individuals (73 mutation carriers and 40 non-carriers).",
    "Changes in eight biomarkers occur sequentially from 26 to 6 years prior to symptom onset.",
]

# Biel et al., 2025 (Alzheimer's & Dementia, 10.1002/alz.70783), pág. 5: "imag-\ning".
BIEL_PAG_5 = (
    "Mean follow-up times\nper biomarker and biomarker-matched cognitive follow-up data are\nshown in Table 1. "
    "Surface renderings of annual change rates in imag-\ning biomarker data (i.e., amyloid-PET, tau-PET, and MRI) are shown in\nFigure 1.\n3.2\nChanges in tau-PET, p"
)
BIEL_COPIA_5 = "Surface renderings of annual change rates in imaging biomarker data (i.e., amyloid-PET, tau-PET, and MRI) are shown in Figure 1."

# Biel et al., 2025, pág. 10: comillas tipográficas, marcas de cita pegadas y tres guiones de corte.
BIEL_PAG_10 = (
    "decline\nthan tau biomarkers,11,12,28,55 our findings go further by demonstrat-\ning that longitudinal increases in fibrillar Aβ do not track concurrent\n"
    "cognitive deterioration in AD. Since amyloid-PET lowering is consid-\nered by the FDA a “reasonably likely surrogate endpoint” for clinical\n"
    "treatment efficacy, our findings challenge this view. Here, future stud-\nies should investigate whether Aβ removal is a reliable marker for\ntracking cognitive changes in "
)
BIEL_COPIA_10 = 'Since amyloid-PET lowering is considered by the FDA a "reasonably likely surrogate endpoint" for clinical treatment efficacy, our findings challenge this view.'

# Plan de análisis estadístico de donanemab (I5T-MC-AACI, NCT04437511), pág. 25.
SAP_PAG_25 = (
    "The probability of “non progressing” by treatment groups will be compared at each of the \nscheduled follow up visits. "
    "The treatment group contrast in LS mean estimates and its associated \np-value and 95% CI will be calcu"
)
SAP_COPIA_25 = 'The probability of "non progressing" by treatment groups will be compared at each of the scheduled follow up visits.'

PAGINAS_REALES = [(BELDER_PAG_2_CRUDA, c) for c in BELDER_COPIAS] + [(BIEL_PAG_5, BIEL_COPIA_5), (BIEL_PAG_10, BIEL_COPIA_10), (SAP_PAG_25, SAP_COPIA_25)]


# --- Artefactos reales de PyMuPDF ------------------------------------------------


@pytest.mark.parametrize("pagina,copia", PAGINAS_REALES)
def test_la_copia_limpia_del_extractor_es_literal_en_la_pagina_real(pagina, copia):
    assert copia.lower() not in pagina.lower()  # el texto crudo no la contiene: los artefactos están en medio
    assert V.pasaje_en_texto(copia, pagina)
    assert pdf.fragmento_en_texto_de_pagina(pagina, copia)  # la puerta de pasos.py aplica la misma regla


def test_belder_pag_2_numero_de_linea_en_medio_de_la_frase():
    """"Longitudinal analyses \\n55 \\nshowed": el número de línea partía la
    frase en dos y la afirmación nacía bloqueada con la página correcta."""
    assert "analyses \n55 \nshowed" in BELDER_PAG_2_CRUDA
    limpio = V.normalizar_texto_pdf(BELDER_PAG_2_CRUDA)
    assert "longitudinal analyses showed aβ42 levels" in limpio
    assert " 55 " not in limpio and " 37 " not in limpio and " 89 " not in limpio
    # Las cifras del texto que van dentro de una línea con letras se quedan.
    assert "124 proteins" in limpio and "at least 26 years" in limpio and "(73 mutation carriers and 40 non-carriers)" in limpio
    # Con el interruptor apagado, los números de línea siguen ahí (para una fila de tabla copiada con sus cifras).
    assert "analyses 55 showed" in V.normalizar_texto_pdf(BELDER_PAG_2_CRUDA, quitar_numeros_de_linea=False)
    # La misma frase con una palabra cambiada no pasa, y una página equivocada tampoco.
    assert not V.pasaje_en_texto("Longitudinal analyses showed Aβ42 levels were reduced in carriers at least 26 years before expected symptom onset.", BELDER_PAG_2_CRUDA)
    assert not V.pasaje_en_texto(BELDER_COPIAS[0], BIEL_PAG_5)


def test_guion_de_fin_de_linea_real_imag_ing():
    assert "imag-\ning" in BIEL_PAG_5
    assert "annual change rates in imaging biomarker data" in V.normalizar_texto_pdf(BIEL_PAG_5)
    # El extractor puede copiar la palabra unida, con el guion o con guion y espacio: las tres son la misma palabra.
    for copia in (BIEL_COPIA_5, BIEL_COPIA_5.replace("imaging", "imag-ing"), BIEL_COPIA_5.replace("imaging", "imag- ing")):
        assert V.pasaje_en_texto(copia, BIEL_PAG_5), copia
    assert not V.pasaje_en_texto(BIEL_COPIA_5.replace("imaging", "plasma"), BIEL_PAG_5)
    # Un guion suelto entre espacios no es un corte de palabra y se conserva en el texto legible.
    assert V.normalizar_texto_pdf("18 months -\nplacebo") == "18 months - placebo"


def test_comillas_tipograficas_reales_en_los_dos_sentidos():
    for pagina, copia in ((BIEL_PAG_10, BIEL_COPIA_10), (SAP_PAG_25, SAP_COPIA_25)):
        assert "“" in pagina and '"' in copia
        assert V.pasaje_en_texto(copia, pagina)  # el extractor escribió comillas rectas
        assert V.pasaje_en_texto(copia.replace('"', "“", 1).replace('"', "”", 1), pagina)  # o las copió tipográficas
    # Lo que va dentro de las comillas sí se comprueba.
    assert not V.pasaje_en_texto(BIEL_COPIA_10.replace("reasonably likely", "validated"), BIEL_PAG_10)
    assert not V.pasaje_en_texto(SAP_COPIA_25.replace("non progressing", "not progressing"), SAP_PAG_25)
    # Las marcas de cita pegadas ("biomarkers,11,12,28,55") y el corte "demonstrat-\ning" tampoco tumban la frase anterior.
    assert V.pasaje_en_texto("our findings go further by demonstrating that longitudinal increases in fibrillar Aβ do not track concurrent cognitive deterioration in AD", BIEL_PAG_10)


# --- Lo que se rompió al intentar romper la tanda 1 --------------------------------

FUENTE_TRES_FRASES = (
    "AChE appeared to diverge between MCs and NCs around symptom onset in the pooled cohort of carriers studied here. "
    "Plasma GFAP increased progressively in mutation carriers over the follow up period and was associated with amyloid burden. "
    "When the longitudinal analysis was repeated restricted to the cohort not prescribed ChI there was no difference between MC and NC at any timepoint."
)


def test_una_costura_de_dos_frases_reales_no_pasa_caiga_donde_caiga():
    """Con la tolerancia de una ventana interior, una primera mitad real de 10,
    15 o 20 palabras seguida de otra frase real de la misma página pasaba
    como literal: la costura caía en una sola ventana. Ahora todas las
    ventanas tienen que estar, sea cual sea la longitud de las mitades."""
    palabras = FUENTE_TRES_FRASES.split()
    cola_real = "there was no difference between MC and NC at any timepoint".split()
    for n in range(6, 24):
        costura = " ".join(palabras[:n] + cola_real)
        assert not V.pasaje_en_texto(costura, FUENTE_TRES_FRASES), (n, costura)
    # Los pasajes reales de cualquier longitud siguen pasando.
    for n in range(1, len(palabras) + 1):
        assert V.pasaje_en_texto(" ".join(palabras[:n]), FUENTE_TRES_FRASES), n
        assert V.pasaje_en_texto(" ".join(palabras[-n:]), FUENTE_TRES_FRASES), n
    # Una errata sigue tumbando el pasaje, como ya hacía (y como el juez no la necesita: juzga contra la fuente).
    con_errata = palabras[:25]
    con_errata[12] = "asociated"
    assert not V.pasaje_en_texto(" ".join(con_errata), FUENTE_TRES_FRASES)


def test_el_pasaje_conserva_sus_cifras_marcas_y_superindices():
    """Quitar las marcas de cita y los superíndices en los DOS lados hacía
    iguales dos pasajes distintos: "169 (94)" casaba con "169 (95)" y "10³"
    con "10²". Ahora se quitan solo en variantes de la fuente."""
    assert not V.pasaje_en_texto("APOE4 carrier 169 (94)", "APOE4 carrier 169 (95)")
    assert V.pasaje_en_texto("APOE4 carrier 169 (94)", "APOE4 carrier 169 (94)")
    assert not V.pasaje_en_texto("Age at onset (AAO)(4, 6) allows", "Age at onset (AAO)(4, 5) allows")
    assert V.pasaje_en_texto("Age at onset (AAO) allows", "Age at onset (AAO)(4, 5) allows")  # el extractor quitó la marca
    assert V.pasaje_en_texto("Age at onset (AAO)(4, 5) allows", "Age at onset (AAO)(4, 5) allows")  # o la copió
    assert not V.pasaje_en_texto("10³ cells per well", "10² cells per well")
    assert V.pasaje_en_texto("10³ cells per well", "10³ cells per well")
    assert V.pasaje_en_texto("in 12 % of participants during the trial", "in 12 % of participants²³ during the trial")
    assert V.pasaje_en_texto("in 12 % of participants²³ during the trial", "in 12 % of participants²³ during the trial")
    # Una fila de tabla copiada con saltos de línea conserva sus cifras: 181 no casa con 180.
    tabla = "Group\nPlacebo\n42\nLecanemab\n180\nMean CDR-SB\n"
    assert not V.pasaje_en_texto("Placebo\n42\nLecanemab\n181", tabla)
    assert V.pasaje_en_texto("Placebo\n42\nLecanemab\n180", tabla)
    assert V.pasaje_en_texto("Placebo 42 Lecanemab 180", tabla)
    assert V.pasaje_en_texto("Placebo Lecanemab Mean CDR-SB", tabla)  # y la frase sin las cifras sigue valiendo


def test_numero_de_linea_tras_una_elision_en_un_resumen_recortado():
    """Tres afirmaciones reales (Jeremic, resumen) pasaban solo por la
    tolerancia: la fuente traía los números de línea del preprint en medio
    del texto, tras una elisión ("were ... 311 significantly")."""
    # Tal como llegó: la elisión en su línea y el número de línea abriendo la siguiente.
    fuente = (
        "and improved cognitive outcomes by small effect size\n...\n310 Frequentist NMA results showed that Donanemab, Lecanemab and Aducanumab were\n...\n"
        "311 significantly more effective than Placebo on ADAS-Cog (cognitive scale, Table 1A).\n...\n314 scale. In frequentist framework, Donanemab was significantly more effective than\n..."
    )
    copia = "Frequentist NMA results showed that Donanemab, Lecanemab and Aducanumab were significantly more effective than Placebo on ADAS-Cog (cognitive scale, Table 1A)."
    assert V.pasaje_en_texto(copia, fuente)
    assert V.pasaje_en_texto(copia, fuente.replace("\n...\n", " ... "))  # y con la elisión en la misma línea
    # En el texto legible se va solo el número de línea; la elisión, que es real, se queda.
    assert "aducanumab were ... significantly" in V.normalizar_texto_pdf(fuente)
    assert "were ... 311 significantly" in V.normalizar_texto_pdf(fuente, quitar_numeros_de_linea=False)
    # Una cifra que sí es dato no se confunde con el número de línea: el pasaje la conserva.
    assert not V.pasaje_en_texto("aducanumab were 300 significantly more effective", fuente)
    assert V.pasaje_en_texto("aducanumab were ... 311 significantly more effective", fuente)  # copiada tal cual, con su elisión


def test_elision_cuyo_primer_tramo_es_solo_una_marca_de_cita():
    pag = "intro (4) and the discussion text here follows"
    assert V.pasaje_en_texto("(4) ... the discussion text here", pag)
    assert not V.pasaje_en_texto("(4) ... the discussion text here is fake", pag)
    # Con dos tramos comprobables, cada uno tiene que estar y en orden, como antes.
    assert V.pasaje_en_texto("intro (4) ... text here follows", pag)
    assert not V.pasaje_en_texto("text here follows ... intro (4)", pag)


# --- Nombre canónico, alias y entradas raras -----------------------------------------


def test_normalizar_texto_pdf_es_la_funcion_unica_y_el_nombre_antiguo_es_la_misma():
    assert V.normalizar_texto is V.normalizar_texto_pdf
    assert V.normalizar_texto_pdf(None) == "" and V.normalizar_texto_pdf("") == "" and V.normalizar_texto_pdf("   \n  ") == ""
    for pagina, _ in PAGINAS_REALES:
        una = V.normalizar_texto_pdf(pagina)
        assert V.normalizar_texto_pdf(una) == una  # idempotente: normalizar lo normalizado no cambia nada
        assert "\n" not in una and "“" not in una and "”" not in una and "\u00ad" not in una
    assert V.normalizar_texto_pdf("signiﬁcantly “higher”") == 'significantly "higher"'


def test_un_pasaje_sin_texto_comprobable_no_es_literal():
    for raro in ("42", "(4, 5)", "[12]", "2024", "²³", "<sub></sub>", " ... "):
        assert not V._comprobable(raro), raro
        assert not V.pasaje_en_texto(raro, "texto con 42 y (4, 5) y [12] y 2024 dentro"), raro
        assert "comprobable" in V.pasaje_faltante(raro, "x"), raro
    assert V._comprobable("Placebo 42") and V._comprobable("n = 42")
    assert V.pasaje_en_texto("", "x") and V.pasaje_en_texto(None, "x") and V.pasaje_en_texto("  ", "x")  # sin pasaje, quien llama decide


def test_registros_antiguos_y_fuentes_sin_texto_no_rompen_ni_aprueban():
    """Una corrida antigua puede traer fragmentos con `texto` None o vacío, y
    una fuente que no respondió no tiene página: nada de eso es literal y
    nada rompe."""
    for texto in (None, "", "   "):
        assert not V.pasaje_en_texto(BELDER_COPIAS[0], texto)
        assert V.pasaje_faltante(BELDER_COPIAS[0], texto) is not None
        assert not pdf.fragmento_en_texto_de_pagina(texto, BELDER_COPIAS[0])
    frags = [F("f-b", "Belder et al., 2026", "pág. 2", None), F("f-b", "Belder et al., 2026", "pág. 3", "")]
    r = V.comprobar_determinista("X.", "[Belder et al., 2026, pág. 2]", BELDER_COPIAS[0], frags, frags, None, "f-b")
    assert r.veredicto == "cita_no_resuelve" and "no aparece entero" in r.motivo
    # Un fragmento guardado antes de la limpieza de paginas() (con los números de línea) sigue resolviendo.
    assert V.pasaje_en_texto(BELDER_COPIAS[0], BELDER_PAG_2_CRUDA)
    assert V.pasaje_en_texto(BELDER_COPIAS[0], pdf.quitar_numeros_de_linea(BELDER_PAG_2_CRUDA))


def test_comprobar_determinista_con_la_pagina_real_del_preprint():
    frags = [
        F("f-belder", "Belder et al., 2026", "pág. 2", BELDER_PAG_2_CRUDA, "Abstract"),
        F("f-belder", "Belder et al., 2026", "pág. 3", "Introduction \n90 \nAutosomal dominant Alzheimer's disease is rare. \n91 \n", "Introduction"),
    ]
    r = V.comprobar_determinista("Los niveles de Aβ42 estaban elevados 26 años antes del inicio esperado.", "[Belder et al., 2026, pág. 2]", BELDER_COPIAS[0], frags, frags, None, "f-belder")
    assert r.veredicto == "sin_verificar" and r.necesita_juez and r.fragmento.localizador == "pág. 2"
    assert "26" in r.pistas
    # La misma frase citada en la página 3: la fuente y el localizador existen, la literalidad falla y el motivo lo dice.
    r = V.comprobar_determinista("X.", "[Belder et al., 2026, pág. 3]", BELDER_COPIAS[0], frags, frags, None, "f-belder")
    assert r.veredicto == "cita_no_resuelve" and "pág. 3" in r.motivo and "no aparece entero" in r.motivo and "longitudinal analyses" in r.motivo.lower()
    # Sin fuenteId (afirmación antigua) también resuelve por la referencia.
    assert V.comprobar_determinista("X.", "[Belder et al., 2026, pág. 2]", BELDER_COPIAS[1], frags, frags).veredicto == "sin_verificar"
    # La firma pública no cambia.
    assert V.resolver_cita("[Belder et al., 2026, pág. 2]", frags, fuente_id="f-belder").localizador == "pág. 2"
    assert V.resolver_cita("[Belder et al., 2026, pág. 2]", frags).localizador == "pág. 2"
    assert V.LOCALIZADORES_ADMITIDOS.fullmatch("pág. 2") and V.LOCALIZADORES_ADMITIDOS.fullmatch("pág. 2-3")


# --- Bloqueos que tienen que seguir siéndolo -----------------------------------------


def test_los_bloqueos_correctos_del_corpus_real_se_mantienen():
    """De las 296 afirmaciones de página bloqueadas, 7 no son literales de
    verdad: filas de tabla compuestas con celdas de filas distintas y una
    palabra añadida entre corchetes. Tienen que seguir bloqueadas."""
    # McDade et al., 2022, pág. 5: la cabecera "10 mg/kg biweekly" está en otra fila que el dato.
    tabla_mcdade = "Placebo (N=45) 2.5 mg/kg biweekly (N=52) 5 mg/kg monthly 10 mg/kg biweekly (N=161) CDR-SB Mean (SD) 2.9 (1.5) 3.0 (1.6) 2.9 (1.4) 3.0 (1.3) 2.9 (1.3) 3.0 (1.4) 4.7 (3.2)"
    assert not V.pasaje_en_texto("CDR-SB Mean (SD) 2.9 (1.5) ... 10 mg/kg biweekly 3.0 (1.4)", tabla_mcdade)
    assert V.pasaje_en_texto("CDR-SB Mean (SD) 2.9 (1.5) 3.0 (1.6)", tabla_mcdade)
    # Biel et al., 2025, pág. 5: el extractor saltó una columna.
    assert not V.pasaje_en_texto("P-tau217 0.24 ± 0.13", "MRI-matched PACC ROC -0.31 ± 0.88 p-tau217 0.17 ± 0.18 0.24 ± 0.13 p-tau217 ROC 0.02 ± 0.02")
    assert V.pasaje_en_texto("P-tau217 0.17 ± 0.18 0.24 ± 0.13", "MRI-matched PACC ROC -0.31 ± 0.88 p-tau217 0.17 ± 0.18 0.24 ± 0.13 p-tau217 ROC 0.02 ± 0.02")
    # Brown et al., 2025, pág. 4: la frase sigue en la página 5 y el extractor la completó entre corchetes.
    brown = "Therefore, we hypothesized that T-C mismatch will identify individuals on different \nclinical trajectories, reflecting underlying differences in co-pathology burden and cognitive \n . \nCC-BY-NC-ND 4.0 International license\n"
    assert V.pasaje_en_texto("we hypothesized that T-C mismatch will identify individuals on different clinical trajectories, reflecting underlying differences in co-pathology burden and cognitive", brown)
    assert not V.pasaje_en_texto("we hypothesized that T-C mismatch will identify individuals on different clinical trajectories, reflecting underlying differences in co-pathology burden and cognitive [reserve]", brown)


def test_las_variantes_de_la_fuente_estan_acotadas_y_la_puerta_del_pdf_coincide():
    for pagina, copia in PAGINAS_REALES:
        assert 1 <= len(V._cuerpos(pagina)) <= 12
        for pasaje in (copia, copia.replace("the", "teh", 1), "una frase que no está en la página"):
            assert pdf.fragmento_en_texto_de_pagina(pagina, pasaje) == V.pasaje_en_texto(pasaje, pagina), pasaje
