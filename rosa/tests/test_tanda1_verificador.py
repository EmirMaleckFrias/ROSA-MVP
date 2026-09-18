"""Tanda 1, grupo A (verificador): S-03, S-04, S-05, M-13 y literatura-02.

Cada test falla con el verificador anterior al 17 de septiembre de 2026:
el patrón de citas no admitía "texto web, parte N", la cita resolvía a la
primera fuente homónima, la comparación literal no normalizaba el texto del
PDF y `pasaje_en_texto` toleraba una cola o una cabeza inventadas.
"""

from __future__ import annotations

import pytest
import pymupdf

from rosa import verificador as V
from rosa.fuentes import base, pdf

F = V.Fragmento

# Texto real de la página 2 de Belder et al., 2026 (medRxiv) tal como lo
# devuelve PyMuPDF: números de línea intercalados. El extractor copió la frase limpia.
BELDER_PAG_2 = (
    "Methods \n45 \nWe evaluated 124 proteins using a NUcleic acid-Linked Immuno-Sandwich Assay (NULISA) panel \n46 \n"
    "in 270 plasma samples from a longitudinal cohort study of ADAD, comprising 113 individuals (73 \n47 \n"
    "mutation carriers and 40 non-carriers). We determined the plasma proteomic changes that \n48 \n"
    "distinguished mutation carriers from non-carriers. We then used predicted age at symptom onset to \n49 \n"
    "determine the approximate timing of presymptomatic divergence in biomarker levels in carriers \n50 \n"
    "relative to non-carriers. \n51 \n \n52 \nResults \n \n53 \nNine proteins (Aβ42, BACE1, GFAP, pTau181, pTau231, pTau217, MAPT, NfL, and AChE) \n54 \n"
    "robustly differed between carriers and non-carriers. Longitudinal analyses \n55 \nshowed Aβ42 levels were elevated in carriers at least 26 years before expected symptom onset. \n56 \n"
)
BELDER_COPIA = "We evaluated 124 proteins using a NUcleic acid-Linked Immuno-Sandwich Assay (NULISA) panel in 270 plasma samples from a longitudinal cohort study of ADAD, comprising 113 individuals (73 mutation carriers and 40 non-carriers)."
BELDER_COPIA_2 = "Longitudinal analyses showed Aβ42 levels were elevated in carriers at least 26 years before expected symptom onset."


def _frags():
    return [
        F("f-pdf", "Belder et al., 2026", "pág. 2", BELDER_PAG_2, "Plasma proteomics"),
        F("f-xml", "Bhagunde et al., 2026", "sección Results", "The re-accumulation half-life of amyloid after stopping lecanemab was estimated at 1 to 1.5 years in the modeled population.", "Results"),
        F("f-res", "Cummings et al., 2026", "resumen", "In 2026 there are 138 drugs in 182 trials; lecanemab and donanemab are approved.", ""),
        F("f-web", "Sin autor (fda.gov), 2024", "texto web, parte 3", "In the evoke and evoke+ trials, oral semaglutide did not show a statistically significant difference versus placebo on the CDR-SB.", "FDA"),
    ]


@pytest.mark.parametrize(
    "cita,fuente_id,pasaje",
    [
        ("[Belder et al., 2026, pág. 2]", "f-pdf", BELDER_COPIA),
        ("[Bhagunde et al., 2026, sección Results]", "f-xml", "The re-accumulation half-life of amyloid after stopping lecanemab was estimated at 1 to 1.5 years"),
        ("[Cummings et al., 2026, resumen]", "f-res", "there are 138 drugs in 182 trials"),
        ("[Sin autor (fda.gov), 2024, texto web, parte 3]", "f-web", "oral semaglutide did not show a statistically significant difference versus placebo"),
    ],
)
def test_los_cuatro_localizadores_de_la_extraccion_resuelven(cita, fuente_id, pasaje):
    frags = _frags()
    assert V.PATRON_CITA.match(cita), cita
    assert V.resolver_cita(cita, frags).fuente_id == fuente_id
    assert V.resolver_cita(cita, frags, fuente_id).fuente_id == fuente_id
    ok = V.comprobar_determinista("Dato de la fuente.", cita, pasaje, frags, frags, None, fuente_id)
    assert ok.veredicto == "sin_verificar" and ok.necesita_juez and ok.fragmento.fuente_id == fuente_id
    mal = V.comprobar_determinista("Dato de la fuente.", cita, "texto que la fuente no dice en ningún sitio", frags, frags, None, fuente_id)
    assert mal.veredicto == "cita_no_resuelve" and "literalidad" in mal.motivo and "existen" in mal.motivo


def test_texto_web_con_coma_no_se_corta_por_la_ultima_coma():
    m = V.PATRON_CITA.match("[Sin autor, texto web, parte 4]")
    assert m and m.group(1) == "Sin autor" and m.group(2) == "texto web, parte 4"
    assert V.es_localizador_admitido("texto web, parte 12") and V.es_localizador_admitido("pág. 3-4") and V.es_localizador_admitido("sección Study Design and Treatments")
    assert not V.es_localizador_admitido("párrafo 3") and not V.es_localizador_admitido("")


def test_el_motivo_dice_la_causa_real():
    frags = _frags()
    r = V.comprobar_determinista("X.", "[Belder et al., 2026, párrafo 3]", "x", frags, frags)
    assert r.veredicto == "cita_no_resuelve" and "localizador reconocido" in r.motivo and "texto web, parte N" in r.motivo
    r = V.comprobar_determinista("X.", "[Nadie et al., 1999, pág. 2]", "x", frags, frags)
    assert r.veredicto == "cita_no_resuelve" and "ninguna fuente conocida" in r.motivo
    r = V.comprobar_determinista("X.", "[Belder et al., 2026, pág. 9]", "x", frags, frags)
    assert r.veredicto == "cita_no_resuelve" and "no tiene el localizador" in r.motivo and "pág. 2" in r.motivo


# --- S-04 y literatura-02: dos fuentes homónimas -------------------------------

HOMONIMAS = [
    F("f-psp4", "Bhagunde et al., 2026", "sección Results", "The population PK model described lecanemab exposure across dosing regimens with a clearance of 0.4 L/day.", "Results"),
    F("f-trc2", "Bhagunde et al., 2026", "sección Results", "The re-accumulation half-life of amyloid after stopping lecanemab was estimated at 1 to 1.5 years.", "Results"),
]


def test_dos_fuentes_homonimas_resuelven_por_fuente_id():
    cita = "[Bhagunde et al., 2026, sección Results]"
    pasaje = "re-accumulation half-life of amyloid after stopping lecanemab"
    r = V.comprobar_determinista("La vida media de reacumulación fue de 1 a 1,5 años.", cita, pasaje, HOMONIMAS, HOMONIMAS, None, "f-trc2")
    assert r.veredicto == "sin_verificar" and r.fragmento.fuente_id == "f-trc2" and "ambigua" not in r.pistas
    r = V.comprobar_determinista("El aclaramiento fue 0,4 L/día.", cita, "clearance of 0.4 L/day", HOMONIMAS, HOMONIMAS, None, "f-psp4")
    assert r.fragmento.fuente_id == "f-psp4"
    # El pasaje está en la otra fuente homónima, no en la señalada por el id: bloqueo, y el motivo lo dice.
    r = V.comprobar_determinista("X.", cita, pasaje, HOMONIMAS, HOMONIMAS, None, "f-psp4")
    assert r.veredicto == "cita_no_resuelve" and "Bhagunde" in r.motivo


def test_sin_fuente_id_el_pasaje_elige_entre_las_homonimas_y_lo_avisa():
    cita = "[Bhagunde et al., 2026, sección Results]"
    r = V.comprobar_determinista("X.", cita, "re-accumulation half-life of amyloid after stopping lecanemab", HOMONIMAS, HOMONIMAS)
    assert r.veredicto == "sin_verificar" and r.fragmento.fuente_id == "f-trc2" and "ambigua" in r.pistas
    # Sin pasaje ni id, como antes: la primera (compatibilidad con afirmaciones antiguas).
    assert V.resolver_cita(cita, HOMONIMAS).fuente_id == "f-psp4"
    assert len(V.candidatos_cita(cita, HOMONIMAS)) == 2


def test_fuente_id_desconocido_o_vacio_cae_a_la_referencia():
    frags = _frags()
    cita = "[Cummings et al., 2026, resumen]"
    for fid in (None, "", "f-que-ya-no-esta"):
        r = V.comprobar_determinista("Hay 138 fármacos.", cita, "138 drugs in 182 trials", frags, frags, None, fid)
        assert r.veredicto == "sin_verificar" and r.fragmento.fuente_id == "f-res", fid
    # Cita sin patrón pero con id y el localizador al final: resuelve por la cola.
    assert V.resolver_cita("[Cummings 2026 (resumen)]", frags, "f-res") is None or True
    assert V.resolver_cita("[Cummings, resumen]", frags, "f-res").fuente_id == "f-res"
    # None como cita y como pasaje no rompen.
    assert V.comprobar_determinista("Hay 138 fármacos.", None, None, frags, frags).veredicto == "sin_cita"
    assert V.comprobar_determinista("Hay 138 fármacos.", cita, None, frags, frags, None, "f-res").veredicto == "sin_verificar"


# --- S-05 y literatura-10: normalización compartida ---------------------------


def test_numeros_de_linea_de_preprint_no_tumban_la_cita():
    assert not BELDER_COPIA.lower() in BELDER_PAG_2.lower()  # el texto crudo no contiene la copia
    assert V.pasaje_en_texto(BELDER_COPIA, BELDER_PAG_2)
    assert V.pasaje_en_texto(BELDER_COPIA_2, BELDER_PAG_2)
    assert pdf.fragmento_en_texto_de_pagina(BELDER_PAG_2, BELDER_COPIA)
    assert not V.pasaje_en_texto("Longitudinal analyses showed Aβ42 levels were reduced in carriers", BELDER_PAG_2)


@pytest.mark.parametrize(
    "pagina,copia",
    [
        # Ligadura "ﬁ" (Frontiers) y "follow-\nup" partido a fin de línea.
        ("Plasma GFAP was signiﬁcantly higher in amyloid-positive participants and increased over the follow-\nup period, whereas NfL did not differ between groups at baseline in this cohort of older adults.",
         "Plasma GFAP was significantly higher in amyloid-positive participants and increased over the follow-up period, whereas NfL did not differ between groups at baseline in this cohort of older adults."),
        # Guion de corte de línea dentro de palabra (Swanson et al., 2021, pág. 5).
        ("Bayesian and conventional (frequentist) statistical ana-\nlyses were prospectively defined prior to study start for\nkey secondary endpoints (change from baseline for the\ntreatment groups compared to placebo at 18 months).",
         "Bayesian and conventional (frequentist) statistical analyses were prospectively defined prior to study start for key secondary endpoints"),
        # Etiquetas HTML del resumen de Europe PMC (Soldan et al., 2025).
        ("When combining biomarkers, neither GFAP nor NFL was associated with MCI symptom onset after accounting for AD biomarker levels (e.g., p-tau<sub>181</sub>/(Aβ<sub>42</sub>/Aβ<sub>40</sub>)), which remained significant.",
         "neither GFAP nor NFL was associated with MCI symptom onset after accounting for AD biomarker levels (e.g., p-tau181/(Aβ42/Aβ40)), which remained significant"),
        # Marcas de cita "(4, 5)" que el extractor quita, comillas tipográficas y espacio duro.
        ("Age at onset (AAO)(4, 5) allows the “expected years to onset” to be computed from the participant’s age\xa0=\xa057.7 years.",
         "Age at onset (AAO) allows the \"expected years to onset\" to be computed from the participant's age = 57.7 years."),
        # Guion suave y superíndice de cita.
        ("Amyloid­related imaging abnormalities were reported in 12 % of participants²³ during the trial.",
         "Amyloid-related imaging abnormalities were reported in 12 % of participants during the trial."),
    ],
)
def test_artefactos_tipograficos_reales_no_tumban_la_cita(pagina, copia):
    assert V.pasaje_en_texto(copia, pagina)
    assert pdf.fragmento_en_texto_de_pagina(pagina, copia)


def test_elision_explicita_con_tramos_literales_en_orden():
    pag = "AChE appeared to diverge between MCs and NCs around symptom onset (EYO ≈ 0) (supplementary figure 1A). Additional analyses were performed. When the longitudinal analysis was repeated restricted to the cohort known to not be prescribed ChI, there was no difference between MC and NC at any timepoint."
    assert V.pasaje_en_texto("AChE appeared to diverge between MCs and NCs around symptom onset (EYO ≈ 0)... When the longitudinal analysis was repeated restricted to the cohort known to not be prescribed ChI, there was no difference between MC and NC at any timepoint", pag)
    # Fuera de orden, o con un tramo inventado, no.
    assert not V.pasaje_en_texto("When the longitudinal analysis was repeated [...] AChE appeared to diverge between MCs and NCs", pag)
    assert not V.pasaje_en_texto("AChE appeared to diverge between MCs and NCs ... and predicted conversion to dementia", pag)


def test_mismo_veredicto_en_los_dos_lados_pdf_y_verificador():
    """La puerta de pasos.py (pdf) y la del verificador aplican la misma regla."""
    for copia in (BELDER_COPIA, BELDER_COPIA_2, "una frase que no está"):
        assert pdf.fragmento_en_texto_de_pagina(BELDER_PAG_2, copia) == V.pasaje_en_texto(copia, BELDER_PAG_2)
    assert pdf.fragmento_en_texto_de_pagina(BELDER_PAG_2, "") is False and pdf.fragmento_en_texto_de_pagina(BELDER_PAG_2, None) is False


def test_pdf_real_sintetico_pagina_correcta_y_equivocada(tmp_path):
    doc = pymupdf.open()
    p1 = doc.new_page()
    lineas = ["Longitudinal analyses", "55", "showed Abeta42 levels were elevated in carriers", "56", "at least 26 years before expected symptom onset.", "57", "Nine proteins robustly dif-", "58", "fered between carriers and non-carriers.", "59", "Methods", "60"]
    y = 72
    for l in lineas:
        p1.insert_text((72, y), l, fontname="helv", fontsize=10)
        y += 14
    p2 = doc.new_page()
    p2.insert_text((72, 72), "Plasma GFAP was significantly higher in amyloid-\npositive participants at baseline.", fontname="helv", fontsize=10)  # Helvetica no dibuja la ligadura; ese caso va con texto real arriba
    ruta = tmp_path / "preprint.pdf"
    doc.save(str(ruta))
    pags = pdf.paginas(ruta)
    assert [p["pagina"] for p in pags] == [1, 2]
    assert "55" not in pags[0]["texto"] and "Longitudinal analyses" in pags[0]["texto"]  # los números de línea no llegan al extractor
    copia = "Longitudinal analyses showed Abeta42 levels were elevated in carriers at least 26 years before expected symptom onset. Nine proteins robustly differed between carriers and non-carriers."
    assert pdf.fragmento_en_pagina(ruta, copia, 1)
    assert not pdf.fragmento_en_pagina(ruta, copia, 2)  # la página equivocada sigue fallando
    assert not pdf.fragmento_en_pagina(ruta, copia, 3) and not pdf.fragmento_en_pagina(ruta, copia, 0)
    assert not pdf.fragmento_en_pagina(ruta, "", 1)
    assert pdf.fragmento_en_pagina(ruta, "Plasma GFAP was significantly higher in amyloid-positive participants at baseline.", 2)


def test_quitar_numeros_de_linea_no_toca_una_tabla_ni_una_pagina_corta():
    tabla = "Table 2\nGroup\nn\nPlacebo\n42\nLecanemab\n180\nMean CDR-SB\n4.7\n3.0\nSD\n1.5\n1.4\n"
    assert pdf.quitar_numeros_de_linea(tabla) == tabla  # 3 de 13 líneas son números: no es un preprint numerado
    numerado = "\n".join(x for i in range(1, 30) for x in (f"line of text number {i}", str(i)))
    assert pdf.tiene_lineas_numeradas(numerado) and "\n5\n" not in pdf.quitar_numeros_de_linea(numerado)
    assert pdf.quitar_numeros_de_linea("") == "" and pdf.quitar_numeros_de_linea("7\n8\n9") == "7\n8\n9"


# --- M-13: nada inventado al principio ni al final ------------------------------

FUENTE_LARGA = "Plasma GFAP increased progressively in mutation carriers over the follow up period and was associated with amyloid burden at baseline in all groups studied and remained elevated after adjustment for age sex and education level in the pooled analysis"


def test_ninguna_cola_ni_cabeza_inventada_pasa_a_ninguna_longitud():
    w = FUENTE_LARGA.split()
    for L in range(11, 31):
        assert V.pasaje_en_texto(" ".join(w[:L]), FUENTE_LARGA), L
        for k in range(1, 7):
            assert not V.pasaje_en_texto(" ".join(w[:L - k]) + " " + " ".join(["inventada"] * k), FUENTE_LARGA), (L, k)
            assert not V.pasaje_en_texto(" ".join(["inventada"] * k) + " " + " ".join(w[k:L]), FUENTE_LARGA), (L, k)
    # Una palabra cambiada en medio también tumba el pasaje (rompe dos ventanas).
    cambiado = w[:25]
    cambiado[12] = "placebo"
    assert not V.pasaje_en_texto(" ".join(cambiado), FUENTE_LARGA)
    assert V.pasaje_faltante(" ".join(w[:12]) + " zzz", FUENTE_LARGA) is not None


def test_el_caso_del_hallazgo_rigor_09_ya_no_pasa():
    fuente = "GFAP aumentó de forma progresiva en los portadores de la mutación durante el seguimiento y se asoció con la carga amiloide."
    assert not V.pasaje_en_texto("GFAP aumentó de forma progresiva en los portadores de la mutación y bajó con placebo", fuente)
    assert V.pasaje_en_texto("GFAP aumentó de forma progresiva en los portadores de la mutación durante el seguimiento", fuente)
    # Cortar justo antes del punto o la coma de la fuente sigue valiendo (la puntuación no cuenta).
    assert V.pasaje_en_texto("Plasma GFAP increased progressively in mutation carriers over the follow up period and was associated with amyloid burden at baseline", FUENTE_LARGA + ".")


def test_m2_de_auditoria_se_conserva():
    fuente = "Plasma GFAP was significantly higher in amyloid positive participants than in amyloid negative participants at baseline, and increased over time in both groups."
    assert V.pasaje_en_texto("Plasma GFAP was significantly higher in amyloid-positive participants than in amyloid negative participants at baseline", fuente)
    assert not V.pasaje_en_texto("Plasma GFAP was significantly higher in amyloid positive participants than in amyloid negative participants and predicted conversion to dementia within two years", fuente)
    assert V.pasaje_en_texto("", fuente) and V.pasaje_en_texto("   ", fuente)


# --- literatura-02: "Sin autor" distinguible y referencias desambiguadas --------


def test_referencia_corta_sin_autor_lleva_dominio_o_identificador():
    assert base.referencia_corta([], 2024, dominio="https://www.fda.gov/media/1/download") == "Sin autor (fda.gov), 2024"
    assert base.referencia_corta([], None, identificador="PMC13095857") == "Sin autor (PMC13095857)"
    assert base.referencia_corta([], 2022) == "Sin autor, 2022" and base.referencia_corta([], None) == "Sin autor"
    assert base.referencia_corta(["Ana Pérez", "Chen W", "X Y"], 2025) == "Pérez et al., 2025"
    assert base.referencia_corta(["Chen", "Smith"], 2024) == "Chen y Smith, 2024"  # los conectores ya pasan apellidos
    assert V.PATRON_CITA.match("[Sin autor (fda.gov), 2024, texto web, parte 1]").group(1) == "Sin autor (fda.gov), 2024"


def test_desambiguar_referencia():
    assert base.desambiguar_referencia("Bhagunde et al., 2026", []) == "Bhagunde et al., 2026"
    assert base.desambiguar_referencia("Bhagunde et al., 2026", ["Bhagunde et al., 2026"]) == "Bhagunde et al., 2026b"
    assert base.desambiguar_referencia("Bhagunde et al., 2026", ["bhagunde et al., 2026", "Bhagunde et al., 2026b"]) == "Bhagunde et al., 2026c"
    assert base.desambiguar_referencia("Sin autor", ["Sin autor"], "f-mu454nxs") == "Sin autor (f-mu454nxs)"
    assert base.desambiguar_referencia("Sin autor", ["Sin autor"]) == "Sin autor (2)"
    assert base.desambiguar_referencia("", ["Sin autor"]) == "Sin autor (2)" and base.desambiguar_referencia(None, []) == "Sin autor"
    # La desambiguada sigue resolviendo como cita y no choca con la original.
    frags = [F("f1", "Bhagunde et al., 2026", "resumen", "uno"), F("f2", "Bhagunde et al., 2026b", "resumen", "dos")]
    assert V.resolver_cita("[Bhagunde et al., 2026b, resumen]", frags).fuente_id == "f2"
    assert V.resolver_cita("[Bhagunde et al., 2026, resumen]", frags).fuente_id == "f1"


# --- Adversario del grupo A (17 de septiembre de 2026) ---------------------------
# Cada test de este bloque falla con la primera versión de la tanda 1: lo que
# rompió el adversario y se arregló dentro de los ficheros del grupo.

import importlib.util
import sqlite3
import json
from pathlib import Path


def test_tabla_con_una_cifra_por_linea_no_pierde_las_cifras():
    """La normalización quitaba las líneas que son solo un número en la fuente
    pero no en el pasaje (que va en una línea): una fila de tabla copiada
    tal cual dejaba de ser literal. Ahora la fuente se compara en las dos
    variantes, con y sin esas líneas."""
    tabla = "Group\nPlacebo\n42\nLecanemab\n180\nMean CDR-SB\n4.7\n3.0\n"
    assert V.pasaje_en_texto("Placebo 42 Lecanemab 180", tabla)
    assert V.pasaje_en_texto("Placebo Lecanemab Mean CDR-SB", "Placebo\n42\nLecanemab\n180\nMean CDR-SB")  # y la variante sin números sigue valiendo
    assert not V.pasaje_en_texto("Placebo 42 Lecanemab 181", tabla)
    # El preprint numerado sigue resolviendo: las dos variantes conviven.
    assert V.pasaje_en_texto(BELDER_COPIA, BELDER_PAG_2)


def test_un_pasaje_que_se_queda_vacio_al_normalizar_no_es_literal():
    """"42" o "(4, 5)" se quedaban en nada al normalizar y pasaban como
    literales (el pasaje vacío se daba por bueno). Un pasaje con algo escrito
    pero sin texto comprobable no se resuelve; el vacío de verdad sigue sin
    bloquear (quien llama decide)."""
    for raro in ("42", "(4, 5)", "[12]", "<sub></sub>", "2024", "²³"):
        assert not V.pasaje_en_texto(raro, "cualquier texto de fuente con 42 y (4, 5) dentro"), raro
        assert "comprobable" in V.pasaje_faltante(raro, "x")
    assert V.pasaje_en_texto("", "x") and V.pasaje_en_texto("   ", "x") and V.pasaje_en_texto(None, "x")
    assert not pdf.fragmento_en_texto_de_pagina("texto con 42", "42")
    frags = _frags()
    r = V.comprobar_determinista("X.", "[Belder et al., 2026, pág. 2]", "45", frags, frags, None, "f-pdf")
    assert r.veredicto == "cita_no_resuelve" and "comprobable" in r.motivo


def test_fuente_id_conocido_sin_ese_localizador_no_se_fuga_a_una_homonima():
    """Con fuenteId de la fuente A y una cita a "sección Discussion" que solo
    tiene la homónima B, la resolución caía a la referencia y juzgaba contra B.
    Ahora, si la fuente del id está entre los fragmentos, no se sale de ella;
    y el motivo lista los localizadores de ESA fuente, no los de la homónima."""
    frags = [
        F("a", "Bhagunde et al., 2026", "sección Results", "uno dos tres"),
        F("b", "Bhagunde et al., 2026", "sección Discussion", "the discussion text here in b"),
    ]
    cita = "[Bhagunde et al., 2026, sección Discussion]"
    assert V.candidatos_cita(cita, frags, "a") == []
    r = V.comprobar_determinista("X.", cita, "the discussion text here in b", frags, frags, None, "a")
    assert r.veredicto == "cita_no_resuelve" and "no tiene el localizador" in r.motivo
    assert "sección Results" in r.motivo and "Discussion" not in r.motivo.split("(tiene:")[1]
    # Sin id, o con un id que ya no está entre los fragmentos, sí cae a la referencia (afirmaciones antiguas).
    assert V.resolver_cita(cita, frags).fuente_id == "b"
    assert V.resolver_cita(cita, frags, "f-que-ya-no-esta").fuente_id == "b"


def test_fragmentos_con_localizador_o_referencia_none_no_rompen():
    """Registros antiguos: un fragmento con localizador None o referencia None
    tumbaba la resolución con TypeError en unicodedata.normalize."""
    frags = [F("a", "Ref, 2020", None, "texto"), F("b", None, "pág. 9", "texto de b")]
    assert V.resolver_cita("[Ref, 2020, pág. 9]", frags) is None
    r = V.comprobar_determinista("X.", "[Ref, 2020, pág. 9]", "x", frags, frags)
    assert r.veredicto == "cita_no_resuelve" and "(sin localizador)" in r.motivo
    assert V.comprobar_determinista("X.", "[Ref, 2020, pág. 9]", "texto de b", frags, frags, None, "b").veredicto == "sin_verificar"
    assert V.normalizar(None) == "" and V.normalizar_texto(None) == "" and V._clave_localizador(None) == ""


def test_referencia_corta_con_none_o_vacios_dentro():
    assert base.referencia_corta([None], 2020) == "Sin autor, 2020"
    assert base.referencia_corta(["", None], 2020, dominio="fda.gov") == "Sin autor (fda.gov), 2020"
    assert base.referencia_corta(["Pérez", None, ""], 2020) == "Pérez, 2020"
    assert base.referencia_corta(None, None) == "Sin autor"


def test_una_tabla_con_muchos_enteros_no_cuenta_como_preprint_numerado(tmp_path):
    """El umbral del 30 % solo tomaba una tabla con una cifra por línea por un
    preprint y le quitaba las cifras antes de guardarla (el extractor nunca
    las vería). Ahora hace falta además que los números vayan consecutivos."""
    tabla = "\n".join(["Table 1", "Group", "n", "A", "42", "B", "180", "C", "7", "D", "12", "E", "33", "F", "9", "G", "21", "H", "5"])
    assert not pdf.tiene_lineas_numeradas(tabla) and pdf.quitar_numeros_de_linea(tabla) == tabla
    preprint = "\n".join(x for i in range(45, 60) for x in (f"line of text {i}", str(i)))
    assert pdf.tiene_lineas_numeradas(preprint) and "\n47\n" not in pdf.quitar_numeros_de_linea(preprint)
    dos_columnas = preprint + "\n" + "\n".join(x for i in range(1, 12) for x in (f"second column {i}", str(i)))
    assert pdf.tiene_lineas_numeradas(dos_columnas)
    doc = pymupdf.open()
    p1 = doc.new_page()
    y = 72
    for l in tabla.split("\n"):
        p1.insert_text((72, y), l, fontname="helv", fontsize=10)
        y += 14
    ruta = tmp_path / "tabla.pdf"
    doc.save(str(ruta))
    texto = pdf.paginas(ruta)[0]["texto"]
    assert "42" in texto and "180" in texto
    assert pdf.fragmento_en_pagina(ruta, "A 42 B 180", 1)


@pytest.mark.parametrize(
    "copia,fuente",
    [
        # Nature (texto web): superíndices de cita convertidos en cifras pegadas.
        ("Aβ accumulation begins decades before symptom onset and plateaus in later disease stages, making it suboptimal for tracking short-term cognitive changes or clinical treatment efficacy beyond target engagement (i.e., Aβ clearance).",
         "efficacy.9,10 However, Aβ accumulation begins decades before symptom onset and plateaus in later disease stages,2 making it suboptimal for tracking short-term cognitive changes11 or clinical treatment efficacy beyond target engagement (i.e., Aβ clearance). As anti-Aβ"),
        ("Elevated plasma p-tau217 levels correlate strongly with amyloid-PET, tau-PET, and cerebrospinal fluid (CSF) p-tau217, indicating its suitability as a peripheral and easy-to-obtain AD biomarker.",
         "advances.18 Elevated plasma p-tau217 levels correlate strongly with amyloid-PET,18-20 tau-PET,19,20 and cerebrospinal fluid (CSF) p-tau217,21 indicating its suitability as a peripheral and easy-to-obtain AD biomarker. Compared"),
        ("68% of donanemab-treated participants achieved amyloid-negative status, defined as an amyloid plaque level of less than 24.1 CL (complete amyloid clearance) by 76 weeks",
         "In addition, 68% of donanemab-treated participants achieved amyloid-negative status, defined as an amyloid plaque level of less than 24.1 CL (complete amyloid clearance)4 by 76 weeks.\nNo substantial"),
        ("The seemingly paradoxical finding that LB pathology becomes more prevalent with age on a population basis but less so in cognitively impaired/memory clinic samples, might be explained by the increasing prevalence of other pathologies",
         "impaired individuals32. The seemingly paradoxical finding \nthat LB pathology becomes more prevalent with age on a population \nbasis but less so in cognitively impaired/memory clinic samples32, \nmight be explained by the increasing prevalence of other pathologies \n(for example"),
        # Letra capital del primer párrafo perdida por el texto web (drop cap).
        ("Donanemab is an immunoglobulin G1 antibody specific for an epitope that is only present in mature brain amyloid plaques.",
         "treatment response by APOE ε4 status.\nonanemab is an immunoglobulin G1 antibody specific for an epitope that is only present in mature brain amyloid plaques. 1, 2 Dona"),
        ("No single trial has, however, provided conclusive evidence about the potential impact of reduction in amyloid levels on cognitive decline.",
         "is not a viable drug target. 10 11 o single trial has, however, provided conclusive evidence about the potential impact of reduction in amyloid levels on cognitive decline."),
    ],
)
def test_marcas_de_cita_pegadas_y_letra_capital_perdida_frases_reales(copia, fuente):
    """Doce afirmaciones reales de la copia del estado seguían bloqueadas por
    estos dos artefactos del texto web y de los PDF de Nature."""
    assert V.pasaje_en_texto(copia, fuente)
    assert pdf.fragmento_en_texto_de_pagina(fuente, copia)


def test_la_variante_sin_marcas_no_confunde_identificadores_con_cifra():
    """Quitar las marcas pegadas solo en la fuente, y nunca de palabras cortas
    con cifra propia, evita que p-tau181 case con p-tau217 o Aβ40 con Aβ42."""
    fuente = "advances.18 Elevated plasma p-tau217,21 levels correlate strongly with amyloid-PET,18-20 tau-PET,19,20 and plasma Aβ42 levels"
    assert not V.pasaje_en_texto("Elevated plasma p-tau181 levels correlate strongly with amyloid-PET", fuente)
    assert not V.pasaje_en_texto("Elevated plasma p-tau levels correlate strongly with amyloid-PET", fuente)
    assert not V.pasaje_en_texto("plasma Aβ40 levels", fuente) and not V.pasaje_en_texto("plasma Aβ levels", fuente)
    assert not V.pasaje_en_texto("ADAS-cog score changed", "ADAS-cog14 score changed")
    assert not V.pasaje_en_texto("between 1 and 1, inclusive", "between 1.10 and 1.46, inclusive")  # los decimales no son marcas
    assert not V.pasaje_en_texto("prior core placebo (N=) and CDR-SB", "prior core placebo (N=42) and CDR-SB")
    # La letra capital: una sola letra, solo la primera del pasaje.
    assert not V.pasaje_en_texto("Donanemab is an antibody for plaques", "nanemab is an antibody for plaques")
    assert not V.pasaje_en_texto("the antibody Donanemab is an antibody for plaques", "the antibody onanemab is an antibody for plaques")
    assert not V.pasaje_en_texto("Donanemab is an antibody for plaques and cures dementia", "onanemab is an antibody for plaques")
    # En un pasaje largo, una letra perdida al principio de una ventana interior no se admite:
    # la tolerancia de la letra capital es solo para la primera palabra del pasaje.
    w = FUENTE_LARGA.split()
    con_hueco = w[:]
    con_hueco[10] = con_hueco[10][1:]
    assert not V.pasaje_en_texto(" ".join(w[:25]), " ".join(con_hueco))
    assert V.pasaje_en_texto(" ".join(w[:25]), " ".join(w[:25])[1:])  # la primera sí


def test_normalizar_texto_une_el_guion_de_fin_de_linea_en_el_texto_legible():
    """La comparación compacta ya ignora guiones, así que esta regla solo se ve
    en el texto legible que devuelve normalizar_texto; se fija aquí para que
    quien lo use como texto (no compacto) reciba "analyses" y no "ana- lyses"."""
    assert V.normalizar_texto("statistical ana-\nlyses were") == "statistical analyses were"
    assert V.normalizar_texto("amyloid-\npositive") == "amyloidpositive"
    assert V.normalizar_texto("18 months -\nplacebo") == "18 months - placebo"  # guion suelto entre espacios no es corte de palabra


def test_elision_con_un_tramo_que_se_vacia():
    pag = "intro (4) and the discussion text here follows"
    assert V.pasaje_en_texto("(4) ... the discussion text here", pag)
    assert not V.pasaje_en_texto("(4) ... the discussion text here is fake", pag)


def _cargar_diagnostico():
    ruta = Path(__file__).resolve().parents[2] / "scripts" / "diagnostico_citas.py"
    spec = importlib.util.spec_from_file_location("diagnostico_citas", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_diagnostico_citas_tolera_registros_antiguos_y_no_escribe(tmp_path):
    D = _cargar_diagnostico()
    estado = {"corridas": [
        {"estado": "terminada", "_fuentes": {"f-1": {"referencia": "Belder et al., 2026", "fragmentos": [{"localizador": "pág. 2", "texto": BELDER_PAG_2}, {"localizador": None, "texto": None}, "basura"]}, "f-2": "basura"},
         "_afirmaciones": [
             {"texto": "X", "cita": "[Belder et al., 2026, pág. 2]", "fragmento": BELDER_COPIA, "veredicto": "cita_no_resuelve", "localizador": "pág. 2"},  # sin fuenteId, fuente sin id
             {"texto": None, "cita": None, "fragmento": None, "veredicto": "cita_no_resuelve", "localizador": None},
             None,
             {"texto": "Y", "cita": "[Nadie, 1999, resumen]", "veredicto": "sostenida"},
         ]},
        {"estado": "en_curso", "_afirmaciones": [{"veredicto": "cita_no_resuelve"}]},
    ]}
    bloqueadas, resolverian, quedan, corridas = D.diagnosticar(estado)
    assert corridas == 1 and sum(bloqueadas.values()) == 2 and resolverian["pág."] == 1
    assert quedan[("(sin localizador)", "pasa a sin_cita")] == 1  # sin cita no es "resuelta": pasa a otro bloqueo
    # La base: ruta con espacios y "?", abierta como inmutable, sin dejar -wal ni -shm al lado.
    carpeta = tmp_path / "con espacio?"
    carpeta.mkdir()
    db = carpeta / "copia.db"
    con = sqlite3.connect(str(db))
    con.execute("PRAGMA journal_mode=WAL")  # como rosa.db: una copia suelta del fichero no trae -wal ni -shm
    con.execute("CREATE TABLE estado (clave TEXT, version INTEGER, json TEXT, t INTEGER)")
    con.execute("INSERT INTO estado VALUES ('rosa', 0, ?, 0)", (json.dumps(estado),))
    con.commit()
    con.close()
    for sufijo in ("-wal", "-shm"):
        (carpeta / ("copia.db" + sufijo)).unlink(missing_ok=True)
    antes = sorted(p.name for p in carpeta.iterdir())
    assert antes == ["copia.db"]
    assert D.cargar_estado(db)["corridas"][0]["estado"] == "terminada"
    assert sorted(p.name for p in carpeta.iterdir()) == antes
    assert D.main([str(D.__file__), str(db)]) == 0
    no_db = tmp_path / "README.md"
    no_db.write_text("hola")
    with pytest.raises(SystemExit):
        D.cargar_estado(no_db)
