"""Tanda 2, constructor "verificacion": S-05 en `rosa/fuentes/pdf.py`.

`paginas()` quita la numeración de líneas de los preprints antes de guardar
el fragmento siguiendo la cadena de números a lo largo del documento: las
páginas que la heurística por página no detecta (una figura con pocas
líneas, una tabla) pierden solo los números que continúan la cadena, y una
cifra de tabla que no la sigue se queda. Con el Belder real (pdfs/), las
páginas 10 y 14 quedaban con sus números de línea; ahora no, y la 14
conserva sus "30".

Los tests con los PDF reales se saltan si `pdfs/` no los tiene; los
sintéticos se construyen con PyMuPDF en `tmp_path`. Nada abre la red.
"""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf
import pytest

from rosa import verificador as V
from rosa.fuentes import pdf

RAIZ = Path(__file__).resolve().parents[2]
PDF_BELDER = RAIZ / "pdfs" / "811c211df9fa75d57f25a5fa5820170aa9eee257.pdf"  # Belder et al., 2026 (medRxiv), líneas numeradas
PDF_BIEL = RAIZ / "pdfs" / "cd15a865e0d75932bb105fd1ff4d18af7c5d61ea.pdf"  # Biel et al., 2025 (Alzheimer's & Dementia)

_SOLO_NUMERO = re.compile(r"^\s*\d{1,4}\s*$")


def _lineas_numericas(texto: str) -> list[int]:
    return [int(l) for l in texto.split("\n") if _SOLO_NUMERO.match(l)]


def _pdf_con_paginas(ruta: Path, paginas: list[list[str]]) -> Path:
    doc = pymupdf.open()
    for lineas in paginas:
        p = doc.new_page()
        y = 60
        for l in lineas:
            p.insert_text((72, y), l, fontname="helv", fontsize=9)
            y += 12
    doc.save(str(ruta))
    return ruta


def _numerada(desde: int, hasta: int, prefijo: str = "line of text") -> list[str]:
    return [x for i in range(desde, hasta + 1) for x in (f"{prefijo} {i}", str(i))]


# --- Sintéticos ----------------------------------------------------------------------


def test_paginas_sigue_la_cadena_en_las_paginas_que_la_heuristica_no_ve(tmp_path):
    ruta = _pdf_con_paginas(tmp_path / "preprint.pdf", [
        _numerada(1, 12),                                                            # detectada
        ["Figure 2", "13", "Legend of the figure with its text", "14", "Placebo", "42", "Lecanemab", "30"],  # corta: 4 de 8 líneas son números, pero no es "numerada" (menos de 10 líneas)
        _numerada(15, 20) + ["Table 3", "73", "40"] + _numerada(21, 26),             # detectada, con dos cifras de tabla en medio
    ])
    pags = {p["pagina"]: p["texto"] for p in pdf.paginas(ruta)}
    assert sorted(pags) == [1, 2, 3]
    assert _lineas_numericas(pags[1]) == []
    assert _lineas_numericas(pags[2]) == [42, 30]  # 13 y 14 seguían la cadena; 42 y 30 son datos
    assert "Legend of the figure with its text" in pags[2] and "Placebo" in pags[2]
    assert _lineas_numericas(pags[3]) == [73, 40]


def test_paginas_no_toca_un_documento_sin_ninguna_pagina_numerada(tmp_path):
    ruta = _pdf_con_paginas(tmp_path / "articulo.pdf", [
        ["Introduction", "Plasma GFAP was higher in carriers.", "Methods follow here."],
        ["Figure 2", "13", "Legend of the figure with its text", "14", "Placebo", "42", "Lecanemab", "30"],
    ])
    pags = {p["pagina"]: p["texto"] for p in pdf.paginas(ruta)}
    assert _lineas_numericas(pags[2]) == [13, 14, 42, 30]  # sin cadena que seguir, nada se quita


def test_quitar_numeros_de_linea_conserva_una_cifra_de_tabla_en_una_pagina_numerada():
    texto = "\n".join(_numerada(45, 52) + ["Table 1", "73", "40"] + _numerada(53, 60))
    assert pdf.tiene_lineas_numeradas(texto)
    limpio = pdf.quitar_numeros_de_linea(texto)
    assert _lineas_numericas(limpio) == [73, 40]
    assert "line of text 45" in limpio and "line of text 60" in limpio
    # Un número perdido por PyMuPDF no rompe la cadena (hasta tres seguidos).
    con_hueco = "\n".join(x for i in range(45, 60) for x in (f"line of text {i}", str(i)) if x != "50")
    assert _lineas_numericas(pdf.quitar_numeros_de_linea(con_hueco)) == []
    # Una numeración que reinicia (dos columnas, suplemento) también se va.
    dos = "\n".join(_numerada(45, 59) + _numerada(1, 11, "second column"))
    assert _lineas_numericas(pdf.quitar_numeros_de_linea(dos)) == []
    # Sin numeración detectada, tal cual (contratos de la tanda 1).
    assert pdf.quitar_numeros_de_linea("7\n8\n9") == "7\n8\n9" and pdf.quitar_numeros_de_linea("") == ""
    tabla = "Table 2\nGroup\nn\nPlacebo\n42\nLecanemab\n180\nMean CDR-SB\n4.7\n3.0\nSD\n1.5\n1.4\n"
    assert pdf.quitar_numeros_de_linea(tabla) == tabla


def test_quitar_numeracion_en_secuencia_sin_inicio_solo_continua():
    texto = "Figure 2\n13\nLegend\n14\nPlacebo\n42\nLecanemab\n30\n1\n2\n3\n"
    sin_cadena, sig = pdf.quitar_numeracion_en_secuencia(texto, None, permitir_inicio=False)
    assert sin_cadena == texto and sig is None  # sin cadena que seguir y sin permiso de abrir una: nada
    limpio, sig = pdf.quitar_numeracion_en_secuencia(texto, 13, permitir_inicio=False)
    assert _lineas_numericas(limpio) == [42, 30, 1, 2, 3] and sig == 15
    # Con permiso de inicio, la terna 1, 2, 3 abre una cadena nueva.
    limpio, sig = pdf.quitar_numeracion_en_secuencia(texto, 13, permitir_inicio=True)
    assert _lineas_numericas(limpio) == [42, 30] and sig == 4
    # Dos números seguidos no bastan para abrir cadena (edades 42, 43 en una tabla).
    limpio, _ = pdf.quitar_numeracion_en_secuencia("A\n42\nB\n43\nC\n", None, permitir_inicio=True)
    assert _lineas_numericas(limpio) == [42, 43]
    assert pdf.quitar_numeracion_en_secuencia("", 5, permitir_inicio=True) == ("", 5)
    assert pdf.quitar_numeracion_en_secuencia(None, None, permitir_inicio=True) == ("", None)


def test_un_salto_en_la_cadena_no_se_lleva_la_cifra_de_tabla_que_compite_por_el_hueco():
    """Adversario, hallazgo 5: con la línea 51 quitada y una cifra de tabla
    "53" antes del número de línea 52, el salto se aceptaba, la cifra se iba
    y el 52 real quedaba como residuo. Ahora un salto se acepta solo si el
    número siguiente continúa desde él."""
    pagina = "line 51\n51\nTable\n53\nline 52\n52\n40\nline 53\n53\nline 54\n54\nline 55\n55"
    limpio, siguiente = pdf.quitar_numeracion_en_secuencia(pagina, 51, permitir_inicio=True)
    assert limpio == "line 51\nTable\n53\nline 52\n40\nline 53\nline 54\nline 55" and siguiente == 56
    assert _lineas_numericas(limpio) == [53, 40]  # las dos cifras de tabla se quedan; ningún número de línea
    # Un número perdido de verdad por PyMuPDF sigue saltándose cuando el siguiente continúa.
    assert pdf.quitar_numeracion_en_secuencia("l\n51\nl\n53\nl\n54\nl\n55", 51, permitir_inicio=False) == ("l\nl\nl\nl", 56)
    # Y un salto al final de la página se acepta (no hay siguiente con el que comparar).
    assert pdf.quitar_numeracion_en_secuencia("l\n51\nl\n53", 51, permitir_inicio=False) == ("l\nl", 54)
    # Límite: si detrás del salto viene una cifra de tabla, el número de línea real se queda (el verificador lo tolera).
    limpio, _ = pdf.quitar_numeracion_en_secuencia("alpha beta\n51\ngamma delta\n53\nTable\n40\nepsilon zeta\n54\neta theta\n55", 51, permitir_inicio=False)
    assert _lineas_numericas(limpio) == [53, 40]
    assert V.pasaje_en_texto("alpha beta gamma delta", limpio)  # la copia limpia del extractor pasa contra ese residuo
    assert V.pasaje_en_texto("alpha beta gamma delta 53 Table", limpio)  # y si copió el residuo, también


def test_fragmento_en_pagina_sintetico_con_la_cadena_por_documento(tmp_path):
    ruta = _pdf_con_paginas(tmp_path / "preprint.pdf", [
        _numerada(1, 12),
        ["Longitudinal analyses", "13", "showed Abeta42 levels were elevated in carriers", "14", "at least 26 years before expected symptom onset."],
    ])
    copia = "Longitudinal analyses showed Abeta42 levels were elevated in carriers at least 26 years before expected symptom onset."
    pags = {p["pagina"]: p["texto"] for p in pdf.paginas(ruta)}
    assert _lineas_numericas(pags[2]) == []
    assert pdf.fragmento_en_texto_de_pagina(pags[2], copia)
    assert pdf.fragmento_en_pagina(ruta, copia, 2) and not pdf.fragmento_en_pagina(ruta, copia, 1)
    assert not pdf.fragmento_en_pagina(ruta, copia, 3) and not pdf.fragmento_en_pagina(ruta, "", 2)


# --- Los PDF reales, si están ----------------------------------------------------------


@pytest.mark.skipif(not PDF_BELDER.exists(), reason="el PDF de Belder 2026 no está en pdfs/")
def test_belder_real_sin_numeros_de_linea_en_ninguna_pagina_y_la_cita_a_la_pagina_exacta():
    pags = {p["pagina"]: p["texto"] for p in pdf.paginas(PDF_BELDER)}
    for numero, texto in pags.items():
        nums = _lineas_numericas(texto)
        seguidos = sum(1 for a, b in zip(nums, nums[1:]) if b == a + 1)
        assert seguidos < 2, (numero, nums)  # ninguna página conserva una cadena de numeración
    assert _lineas_numericas(pags[10]) == []  # la figura con pocas líneas, que la heurística por página no veía
    assert 30 in _lineas_numericas(pags[14])  # la tabla conserva sus cifras
    copia = "Longitudinal analyses showed Aβ42 levels were elevated in carriers at least 26 years before expected symptom onset."
    assert [n for n, t in pags.items() if pdf.fragmento_en_texto_de_pagina(t, copia)] == [2]
    assert pdf.fragmento_en_pagina(PDF_BELDER, copia, 2)
    assert not pdf.fragmento_en_pagina(PDF_BELDER, copia, 1) and not pdf.fragmento_en_pagina(PDF_BELDER, copia, 3)
    with pymupdf.open(str(PDF_BELDER)) as doc:
        cruda = doc[1].get_text("text")
    assert "analyses \n55 \nshowed" in cruda and V.pasaje_en_texto(copia, cruda)  # también contra el texto crudo (registros antiguos)


@pytest.mark.skipif(not PDF_BIEL.exists(), reason="el PDF de Biel 2025 no está en pdfs/")
def test_biel_real_guion_de_corte_y_comillas_tipograficas():
    copia_5 = "Surface renderings of annual change rates in imaging biomarker data (i.e., amyloid-PET, tau-PET, and MRI) are shown in Figure 1."
    copia_10 = 'Since amyloid-PET lowering is considered by the FDA a "reasonably likely surrogate endpoint" for clinical treatment efficacy, our findings challenge this view.'
    with pymupdf.open(str(PDF_BIEL)) as doc:
        assert "imag-\ning" in doc[4].get_text("text") and "“reasonably likely surrogate endpoint”" in doc[9].get_text("text")
    assert pdf.fragmento_en_pagina(PDF_BIEL, copia_5, 5) and not pdf.fragmento_en_pagina(PDF_BIEL, copia_5, 4) and not pdf.fragmento_en_pagina(PDF_BIEL, copia_5, 6)
    assert pdf.fragmento_en_pagina(PDF_BIEL, copia_10, 10) and not pdf.fragmento_en_pagina(PDF_BIEL, copia_10, 9)
    pags = {p["pagina"]: p["texto"] for p in pdf.paginas(PDF_BIEL)}
    assert [n for n, t in pags.items() if pdf.fragmento_en_texto_de_pagina(t, copia_5)] == [5]
    assert [n for n, t in pags.items() if pdf.fragmento_en_texto_de_pagina(t, copia_10)] == [10]
