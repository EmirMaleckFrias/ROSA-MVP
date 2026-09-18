"""Tanda 2, adversario del constructor "verificacion" (S-05).

Estos tests demuestran tres huecos que abre el cambio en `rosa/verificador.py`
respecto a HEAD; FALLAN a propósito hasta que se cierren. Las guardas del
final recogen lo que el constructor recuperó y no debe volver a romperse al
arreglar los huecos (Jeremic, "(4) ... the discussion").

1. `_NUMERO_TRAS_ELISION` quita de la FUENTE cualquier número que siga a una
   elisión, no solo los números de línea de un preprint. En el resumen real
   de Bateman et al., 2023 (NEJM, gantenerumab) la elisión cae justo antes
   del "181" de p-tau181, y un pasaje que cruza la elisión sin el 181 (deja
   "phosphorylated tau" a secas) pasa como literal. HEAD lo bloqueaba.
2. Un tramo que es solo una cifra junto a una elisión ("999 ... 3.0 (1.6)")
   se descarta como "no comprobable" y el resto del pasaje se da por literal,
   con la cifra inventada dentro. HEAD comparaba el pasaje entero y lo
   bloqueaba. La intención del constructor era descartar solo las marcas de
   cita "(4)", no los datos.
3. Con varios tramos, el orden se comprueba por variante de la fuente: si el
   primer tramo casa solo en las variantes sin marcas y el segundo solo en
   las que las conservan, un pasaje con los tramos en orden inverso al de la
   fuente pasa.

Sin red ni gateway; los textos de fuente son copias de lo guardado en la
base (Bateman, Jeremic) o sintéticos.
"""

from __future__ import annotations

import pytest

from rosa import verificador as V

# Resumen de Bateman et al., 2023 (10.1056/nejmoa2304430) tal como quedó
# guardado en la corrida (recortado con elisiones): el número de p-tau181 cae
# tras la elisión, en su propia línea.
BATEMAN_RESUMEN = (
    "At week 116, participants receiving gantenerumab had a lower geometric mean level of phosphorylated tau\n...\n"
    "181 and a higher geometric mean level of Aβ42 than those receiving placebo (Fig. S7 ).\n...\n"
    "Participants receiving gantenerumab had lower CSF levels of phosphorylated tau 181 and higher levels of Aβ42 than those receiving placebo."
)

# Resumen de Jeremic (preprint) con los números de línea tras las elisiones:
# lo que el constructor recuperó y tiene que seguir pasando.
JEREMIC_RESUMEN = (
    "and improved cognitive outcomes by small effect size\n...\n310 Frequentist NMA results showed that Donanemab, Lecanemab and Aducanumab were\n...\n"
    "311 significantly more effective than Placebo on ADAS-Cog (cognitive scale, Table 1A).\n...\n314 scale. In frequentist framework, Donanemab was significantly more effective than\n..."
)
JEREMIC_COPIA = "Frequentist NMA results showed that Donanemab, Lecanemab and Aducanumab were significantly more effective than Placebo on ADAS-Cog (cognitive scale, Table 1A)."

TABLA_MCDADE = "Placebo (N=45) 2.5 mg/kg biweekly (N=52) 5 mg/kg monthly 10 mg/kg biweekly (N=161) CDR-SB Mean (SD) 2.9 (1.5) 3.0 (1.6) 2.9 (1.4) 3.0 (1.3)"


# --- 1. Un dato real tras una elisión de la fuente se pierde en una variante ---------


def test_un_pasaje_que_cruza_la_elision_sin_el_numero_del_isoformo_no_es_literal():
    """"phosphorylated tau ... 181": el pasaje sin el 181 dice "tau" donde la
    fuente dice p-tau181. El verificador protege a propósito la cifra de los
    identificadores (p-tau181 frente a p-tau217); aquí la pierde porque
    `_NUMERO_TRAS_ELISION` borra el 181 de la variante limpia de la fuente."""
    sin_181 = "lower geometric mean level of phosphorylated tau and a higher geometric mean level of Aβ42"
    assert not V.pasaje_en_texto(sin_181, BATEMAN_RESUMEN), V.pasaje_faltante(sin_181, BATEMAN_RESUMEN)
    # Las formas honestas siguen valiendo: con la elisión y el 181, o el 181 pegado.
    assert V.pasaje_en_texto("lower geometric mean level of phosphorylated tau ... 181 and a higher geometric mean level", BATEMAN_RESUMEN)
    assert V.pasaje_en_texto("lower CSF levels of phosphorylated tau 181 and higher levels", BATEMAN_RESUMEN)


def test_un_numero_que_es_dato_tras_una_elision_no_se_puede_saltar():
    fuente = "Mean age was 72 years ... 45 % were women and 30 % carried APOE4"
    assert not V.pasaje_en_texto("Mean age was 72 years % were women", fuente)
    assert V.pasaje_en_texto("Mean age was 72 years ... 45 % were women", fuente)
    fuente_web = "improved outcomes\n...\n42 patients were enrolled in the open-label extension"
    assert not V.pasaje_en_texto("improved outcomes patients were enrolled", fuente_web)
    # Pontecorvo et al., 2022 (resumen guardado): "further evaluation.\n...\n76 weeks of the study".
    pontecorvo = "Usefulness in assessing treatment response will require further evaluation.\n...\n76 weeks of the study (Figure 2B and eTable 2 in Supplement 2). Mean plasma GFAP levels decreased"
    assert not V.pasaje_en_texto("will require further evaluation weeks of the study", pontecorvo)


# --- 2. Un tramo de solo cifra junto a una elisión se traga --------------------------


@pytest.mark.parametrize("pasaje", [
    "999 ... 3.0 (1.6)",
    "161 ... CDR-SB Mean (SD) 2.9 (1.5)",
    "CDR-SB Mean (SD) ... 777",
    "2024 ... CDR-SB Mean (SD)",
])
def test_una_cifra_inventada_junto_a_una_elision_tumba_el_pasaje(pasaje):
    """La cifra no está en la fuente; el pasaje no puede darse por literal.
    El tramo "999" no es una marca de cita: es un dato que el extractor dice
    haber copiado."""
    assert not V.pasaje_en_texto(pasaje, TABLA_MCDADE), pasaje


def test_una_cifra_real_junto_a_una_elision_sigue_valiendo():
    """Lo contrario también: una fila de tabla copiada con su N real y una
    elisión entre celdas no se bloquea por llevar la cifra."""
    assert V.pasaje_en_texto("(N=45) ... 2.9 (1.5)", TABLA_MCDADE)
    assert V.pasaje_en_texto("CDR-SB Mean (SD) 2.9 (1.5) ... 3.0 (1.3)", TABLA_MCDADE)


# --- 3. El orden entre tramos no se cruza entre variantes -----------------------------


def test_el_orden_de_los_tramos_se_exige_aunque_cada_uno_case_en_otra_variante():
    fuente = "Plasma GFAP rose early in carriers (4) before tau. Later, NfL increased in symptomatic carriers (5) after onset."
    # Primer tramo sin su marca (casa solo en las variantes sin marcas), segundo con la suya (solo en las que las conservan).
    desordenado = "NfL increased in symptomatic carriers after onset ... Plasma GFAP rose early in carriers (4) before tau"
    assert not V.pasaje_en_texto(desordenado, fuente), V.pasaje_faltante(desordenado, fuente)
    # El mismo pasaje en el orden de la fuente sí vale.
    assert V.pasaje_en_texto("Plasma GFAP rose early in carriers before tau ... NfL increased in symptomatic carriers (5) after onset", fuente)
    # Y con las marcas coherentes (todas o ninguna) el desorden ya se bloqueaba.
    assert not V.pasaje_en_texto("NfL increased in symptomatic carriers after onset ... Plasma GFAP rose early in carriers before tau", fuente)


# --- Guardas: lo que el constructor recuperó no debe volver a romperse ----------------


def test_guarda_los_numeros_de_linea_de_jeremic_siguen_siendo_artefacto():
    assert V.pasaje_en_texto(JEREMIC_COPIA, JEREMIC_RESUMEN)
    assert V.pasaje_en_texto(JEREMIC_COPIA, JEREMIC_RESUMEN.replace("\n...\n", " ... "))
    assert not V.pasaje_en_texto("aducanumab were 300 significantly more effective", JEREMIC_RESUMEN)


def test_guarda_una_marca_de_cita_suelta_junto_a_la_elision_no_cuenta_como_tramo():
    pag = "intro (4) and the discussion text here follows"
    assert V.pasaje_en_texto("(4) ... the discussion text here", pag)
    assert not V.pasaje_en_texto("(4) ... the discussion text here is fake", pag)
