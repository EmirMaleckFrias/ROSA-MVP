"""Tanda 2, constructor "verificacion" (S-05), segunda pasada: lo que el
adversario encontró en la primera y cómo quedó cerrado.

1. Un número tras una elisión de la fuente es un dato, salvo que el texto
   entero demuestre que es numeración de líneas (una cadena ascendente en al
   menos tres elisiones exactas y en la mitad de ellas, como en el resumen
   recortado de un preprint). Antes se quitaba cualquier número tras "..." y
   "phosphorylated tau\\n...\\n181" (Bateman 2023) perdía el 181 en la variante
   limpia: "tau" pasaba por "p-tau181". Aunque haya cadena, el número que sigue
   a un identificador que espera cifra (tau, p-tau, Aβ, APOE) se queda.
2. Un tramo del pasaje que es solo una cifra ("999 ... 3.0 (1.6)") no se
   descarta como "no comprobable" ni se comprueba suelto (compacto casaría
   dentro de "1610"): bloquea con su motivo. Solo la marca de cita suelta
   ("(4) ... the discussion") sigue sin contar como tramo.
3. El orden de los tramos se mide en la coordenada de la fuente completa, no
   variante por variante: un pasaje al revés que la fuente no pasa aunque cada
   tramo case en una variante distinta, y uno en orden con marcas mezcladas
   sí (las dos aserciones del adversario).
4. Límite documentado: dentro de un tramo, todas las marcas o ninguna.
5. `pdf.quitar_numeracion_en_secuencia`: un salto en la cadena se acepta solo
   si el número siguiente continúa desde él (en test_tanda2_verificacion_pdf).
6. `_cuerpos` calcula las variantes de marcas pegadas solo sobre los textos
   legibles distintos; el resultado no cambia.

Los textos de fuente son copias de lo guardado en la base (Bateman, Jeremic,
Pontecorvo) o sintéticos. Sin red ni gateway.
"""

from __future__ import annotations

import pytest

from rosa import verificador as V

P = V.pasaje_en_texto

# Resumen de Bateman et al., 2023 (10.1056/nejmoa2304430) tal como quedó
# guardado: la elisión cae justo antes del 181 de p-tau181.
BATEMAN = (
    "At week 116, participants receiving gantenerumab had a lower geometric mean level of phosphorylated tau\n...\n"
    "181 and a higher geometric mean level of Aβ42 than those receiving placebo (Fig. S7 ).\n...\n"
    "Participants receiving gantenerumab had lower CSF levels of phosphorylated tau 181 and higher levels of Aβ42 than those receiving placebo."
)
# Resumen de Jeremic (preprint recortado): números de línea tras las elisiones, en cadena.
JEREMIC = (
    "and improved cognitive outcomes by small effect size\n...\n310 Frequentist NMA results showed that Donanemab, Lecanemab and Aducanumab were\n...\n"
    "311 significantly more effective than Placebo on ADAS-Cog (cognitive scale, Table 1A).\n...\n314 scale. In frequentist framework, Donanemab was significantly more effective than\n..."
)
JEREMIC_COPIA = "Frequentist NMA results showed that Donanemab, Lecanemab and Aducanumab were significantly more effective than Placebo on ADAS-Cog (cognitive scale, Table 1A)."
PONTECORVO = "Usefulness in assessing treatment response will require further evaluation.\n...\n76 weeks of the study (Figure 2B and eTable 2 in Supplement 2). Mean plasma GFAP levels decreased"
TABLA_MCDADE = "Placebo (N=45) 2.5 mg/kg biweekly (N=52) 5 mg/kg monthly 10 mg/kg biweekly (N=161) CDR-SB Mean (SD) 2.9 (1.5) 3.0 (1.6) 2.9 (1.4) 3.0 (1.3)"
DOS_FRASES = "Plasma GFAP rose early in carriers (4) before tau. Later, NfL increased in symptomatic carriers (5) after onset."


# --- 1. Cifra tras una elisión: dato salvo cadena ------------------------------------


def test_bateman_sin_el_181_no_es_literal_y_las_formas_honestas_si():
    sin_181 = "lower geometric mean level of phosphorylated tau and a higher geometric mean level of Aβ42"
    assert not P(sin_181, BATEMAN)
    assert "phosphorylated tau and a higher" in V.pasaje_faltante(sin_181, BATEMAN)
    assert P("lower geometric mean level of phosphorylated tau ... 181 and a higher geometric mean level", BATEMAN)
    assert P("lower CSF levels of phosphorylated tau 181 and higher levels", BATEMAN)
    # El 181 está en TODAS las variantes de la fuente: no hay ninguna limpia que lo pierda.
    assert all("tau181and" in c for c in V._cuerpos(BATEMAN))


@pytest.mark.parametrize("pasaje,fuente", [
    ("will require further evaluation weeks of the study", PONTECORVO),
    ("Mean age was 72 years % were women", "Mean age was 72 years ... 45 % were women and 30 % carried APOE4"),
    ("improved outcomes patients were enrolled", "improved outcomes\n...\n42 patients were enrolled in the open-label extension"),
    ("randomized phase study of efficacy", "TANGO: a placebo-controlled randomized phase\n...\n2 study of efficacy and\n...\nof safety"),
    ("phase study and phase trial", "in a phase\n...\n2 study and phase\n...\n3 trial"),  # dos números no hacen cadena
])
def test_un_dato_tras_una_elision_de_la_fuente_no_se_puede_saltar(pasaje, fuente):
    assert not P(pasaje, fuente), V.pasaje_faltante(pasaje, fuente)


def test_la_cadena_de_jeremic_sigue_siendo_artefacto():
    assert P(JEREMIC_COPIA, JEREMIC)
    assert P(JEREMIC_COPIA, JEREMIC.replace("\n...\n", " ... "))
    assert P(JEREMIC_COPIA, JEREMIC.replace("...", "…"))  # elipsis tipográfica: NFKC la convierte en tres puntos
    # En el texto legible se va el número y la elisión se queda; sin el interruptor, se queda todo.
    assert "aducanumab were ... significantly" in V.normalizar_texto_pdf(JEREMIC)
    assert "were ... 311 significantly" in V.normalizar_texto_pdf(JEREMIC, quitar_numeros_de_linea=False)
    # Una cifra que sí es dato no se confunde con el número de línea, y el número copiado tal cual también vale.
    assert not P("aducanumab were 300 significantly more effective", JEREMIC)
    assert P("aducanumab were ... 311 significantly more effective", JEREMIC)


def test_la_cadena_exige_tres_numeros_ascendentes_en_la_mitad_de_las_elisiones():
    assert P("a b c d", "a\n...\n1 b\n...\n2 c\n...\n3 d")  # tres en tres: cadena
    assert not P("a b c d", "a\n...\n9 b\n...\n5 c\n...\n7 d")  # tres, pero no suben
    assert not P("a b c d", "a\n...\n1 b\n...\n2 c\n...\n3 d\n...\nx\n...\ny\n...\nz\n...\nw\n...\nq")  # tres de ocho elisiones
    # Dentro de una cadena, un número que rompe el orden es un dato y se queda; el pasaje que lo copia pasa.
    fuente = "x\n...\n310 cognitive scale\n...\n2 phase study\n...\n311 more\n...\n314 end"
    assert not P("cognitive scale phase study", fuente)
    assert P("cognitive scale ... 2 phase study", fuente)
    assert P("more end", fuente)  # los que sí son de la cadena se van


def test_el_identificador_que_espera_cifra_conserva_su_numero_aunque_haya_cadena():
    fuente = "a\n...\n310 b\n...\n311 levels of phosphorylated tau\n...\n312 and higher\n...\n313 c"
    assert not P("levels of phosphorylated tau and higher", fuente)
    assert P("levels of phosphorylated tau ... 312 and higher", fuente)
    # "plateau" no es "tau": la cadena se quita con normalidad.
    assert P("reached a plateau and higher", fuente.replace("levels of phosphorylated tau", "reached a plateau"))
    for palabra in ("p-tau", "Aβ", "APOE", "abeta"):
        assert not P("marker " + palabra + " and higher", "a\n...\n310 b\n...\n311 marker " + palabra + "\n...\n312 and higher\n...\n313 c"), palabra


def test_los_puntos_de_guia_de_un_indice_no_son_elisiones():
    """Un índice ("Executive Summary ........ 8") trae tiradas largas de
    puntos con el número de página detrás. No es la elisión de un recorte y
    el número se queda en todas las variantes."""
    indice = "1. \nExecutive Summary ........................ 8 \n \nProduct Introduction ..................... 9 \nConclusions ................ 12 \n"
    assert not P("Executive Summary Product Introduction", indice)
    assert P("Executive Summary ... 8 Product Introduction", indice)
    assert V._ELISION_EXACTA.findall(indice) == [] and V._NUMERO_TRAS_ELISION.search(indice) is None


def test_la_normalizacion_nueva_es_idempotente_y_aguanta_entradas_raras():
    for t in (JEREMIC, BATEMAN, PONTECORVO):
        una = V.normalizar_texto_pdf(t)
        assert V.normalizar_texto_pdf(una) == una
    for raro in ("", "...", "... 5", "\n...\n", "... 1 ... 2", "a\n...\n1\n...\n2\n...\n3"):
        assert isinstance(V._quitar_numeros_de_linea_tras_elisiones(raro), str)
    assert V._quitar_numeros_de_linea_tras_elisiones("... 5") == "... 5"
    assert V.normalizar_texto_pdf(None) == ""


# --- 2. Un tramo de solo cifra bloquea con motivo --------------------------------------


@pytest.mark.parametrize("pasaje", ["999 ... 3.0 (1.6)", "161 ... CDR-SB Mean (SD) 2.9 (1.5)", "CDR-SB Mean (SD) ... 777", "2024 ... CDR-SB Mean (SD)", "999 ... 888"])
def test_un_tramo_de_solo_cifra_bloquea_y_lo_dice(pasaje):
    assert not P(pasaje, TABLA_MCDADE), pasaje
    motivo = V.pasaje_faltante(pasaje, TABLA_MCDADE)
    assert "solo una cifra" in motivo and "comprobable" in motivo, motivo


def test_una_cifra_suelta_no_se_comprueba_dentro_de_un_numero_mas_largo():
    assert not P("161 ... CDR-SB", "n=1610 CDR-SB Mean")
    assert P("N = 161 ... CDR-SB Mean", "biweekly (N = 161) CDR-SB Mean (SD)")  # con texto sí es un tramo


def test_la_marca_de_cita_suelta_sigue_sin_contar_y_la_cifra_real_con_texto_sigue_valiendo():
    pag = "intro (4) and the discussion text here follows"
    assert P("(4) ... the discussion text here", pag)
    assert not P("(4) ... the discussion text here is fake", pag)
    assert not P("(4) ... 999", "intro (4) and 999 follows")  # marca suelta fuera, cifra suelta bloquea
    assert P("(N=45) ... 2.9 (1.5)", TABLA_MCDADE)
    assert P("CDR-SB Mean (SD) 2.9 (1.5) ... 3.0 (1.3)", TABLA_MCDADE)
    assert V._es_solo_marca_de_cita("(4)") and V._es_solo_marca_de_cita("[12]") and V._es_solo_marca_de_cita("²³")
    assert not V._es_solo_marca_de_cita("999") and V._es_solo_cifra("999") and V._es_solo_cifra("2024")
    assert not V._es_solo_cifra("(4)") and not V._es_solo_cifra("n = 42") and not V._es_solo_cifra("12345")


# --- 3. El orden se mide en la fuente completa ---------------------------------------


def test_el_orden_de_los_tramos_no_se_cruza_entre_variantes():
    desordenado = "NfL increased in symptomatic carriers after onset ... Plasma GFAP rose early in carriers (4) before tau"
    assert not P(desordenado, DOS_FRASES)
    assert "fuera de orden" in V.pasaje_faltante(desordenado, DOS_FRASES)
    assert P("Plasma GFAP rose early in carriers before tau ... NfL increased in symptomatic carriers (5) after onset", DOS_FRASES)
    assert P("Plasma GFAP rose early in carriers (4) before tau ... NfL increased in symptomatic carriers after onset", DOS_FRASES)
    assert not P("NfL increased in symptomatic carriers after onset ... Plasma GFAP rose early in carriers before tau", DOS_FRASES)
    # Lo mismo con números de línea mezclados.
    assert not P("significantly more effective ... aducanumab were", JEREMIC)
    assert P("aducanumab were significantly ... 314 scale. In frequentist framework", JEREMIC)


def test_el_orden_admite_la_letra_capital_perdida_y_tres_tramos():
    fuente = "onanemab is an antibody for plaques. It also reduced tau."
    assert P("Donanemab is an antibody for plaques ... it also reduced tau", fuente)
    assert not P("It also reduced tau ... Donanemab is an antibody for plaques", fuente)
    assert P("a b ... c d ... e f", "a b x c d y e f")
    assert not P("a b ... e f ... c d", "a b x c d y e f")
    assert not P("c d ... a b", "a b x c d")


def test_posicion_del_tramo_ancla_por_el_prefijo_mas_largo_que_exista():
    completo = V._cuerpo_completo(DOS_FRASES)
    assert V._posicion_del_tramo(V._palabras("Plasma GFAP rose early in carriers before tau"), completo, 0) == 0
    assert V._posicion_del_tramo(V._palabras("NfL increased in symptomatic carriers after onset"), completo, 0) > 0
    assert V._posicion_del_tramo(V._palabras("Plasma GFAP rose early in carriers"), completo, 5) == -1
    # Un tramo que la fuente completa parte con una marca se ancla por su prefijo (5 palabras aquí), no por el todo.
    assert "plasmagfaproseearlyincarriersbeforetau" not in completo and "plasmagfaproseearlyin" in completo


# --- 4. Límite documentado --------------------------------------------------------------


def test_dentro_de_un_tramo_las_marcas_son_todas_o_ninguna_y_esta_escrito():
    assert not P("(AAO) allows prediction (6) in", "(AAO)(4, 5) allows prediction (6) in")
    assert P("(AAO) allows prediction in", "(AAO)(4, 5) allows prediction (6) in")
    assert P("(AAO)(4, 5) allows prediction (6) in", "(AAO)(4, 5) allows prediction (6) in")
    assert "Límite conocido" in V.__doc__ and "todas las marcas" in V.__doc__


# --- 6. Las variantes de la fuente no cambian por el ahorro ----------------------------


def test_cuerpos_da_las_mismas_variantes_que_el_calculo_directo():
    for texto in (JEREMIC, BATEMAN, TABLA_MCDADE, DOS_FRASES, "sin marcas ni números de línea"):
        esperado: list[str] = []
        for qn in (True, False):
            for qm in (True, False):
                legible = V.normalizar_texto_pdf(texto, quitar_numeros_de_linea=qn, quitar_marcas=qm)
                for v in (legible, V._MARCA_PEGADA.sub("", legible), V._COLA_TRAS_IDENTIFICADOR.sub(r"\1", V._MARCA_TRAS_SIGNO.sub("", legible))):
                    c = V._compacto(v.split())
                    if c not in esperado:
                        esperado.append(c)
        assert list(V._cuerpos(texto)) == esperado
        assert 1 <= len(V._cuerpos(texto)) <= 12
    assert V._cuerpos("sin marcas ni números de línea") == ("sinmarcasninumerosdelinea",)


# --- Contratos que no se mueven ---------------------------------------------------------


def test_los_contratos_publicos_siguen_iguales():
    assert V.normalizar_texto is V.normalizar_texto_pdf
    assert V.LOCALIZADORES_ADMITIDOS.fullmatch("pág. 2") and V.LOCALIZADORES_ADMITIDOS.fullmatch("resumen")
    frags = [V.Fragmento("f-b", "Bateman et al., 2023", "resumen", BATEMAN)]
    r = V.comprobar_determinista("X.", "[Bateman et al., 2023, resumen]", "lower geometric mean level of phosphorylated tau and a higher geometric mean level", frags, frags, None, "f-b")
    assert r.veredicto == "cita_no_resuelve" and "no aparece entero" in r.motivo
    r = V.comprobar_determinista("X.", "[Bateman et al., 2023, resumen]", "lower CSF levels of phosphorylated tau 181 and higher levels", frags, frags, None, "f-b")
    assert r.veredicto == "sin_verificar" and r.necesita_juez
    assert V.resolver_cita("[Bateman et al., 2023, resumen]", frags, fuente_id="f-b").localizador == "resumen"
    assert P("", "x") and P(None, "x") and not P("a b", "") and not P("a b", None)
