"""Tanda 2, constructor "certeza", M-03: el nombre de cohorte no pierde el NCT
al recortarse, los nombres que solo difieren en el sufijo numérico no se
funden, y los nombres del estado de muestra que no pueden ser cohorte
(evoke, FLENI) están en AMBIGUOS con su motivo. M-06: la descripción de
`certeza` que lee el juez es coherente con rosa/certeza.py.
"""

from __future__ import annotations

import re

from rosa import metodos as M

LARGO = "TRAILBLAZER-ALZ (NCT03367403) y TRAILBLAZER-ALZ 2 (NCT04437511)"


def test_recortar_nombre_cohorte_conserva_todos_los_nct():
    assert len(LARGO) > 60
    corto = M.recortar_nombre_cohorte(LARGO)
    # El corte cae justo antes del segundo NCT y ese NCT pasa al paréntesis final: nada se rompe.
    assert corto == LARGO and "NCT03367403" in corto and "NCT04437511" in corto and "(NCT044375 " not in corto + " "
    assert M.recortar_nombre_cohorte(LARGO, maximo=40) == "TRAILBLAZER-ALZ (NCT03367403) (TRAILBLAZER-ALZ 2, NCT04437511)"
    # Lo que canoniza el nombre recortado es lo mismo que canonizaba el entero (el primer NCT manda).
    assert M.canonizar_cohorte(corto)["id"] == M.canonizar_cohorte(LARGO)["id"] == "cohorte:trailblazer_alz"
    # Antes: el corte a 60 dejaba "(NCT044375" roto y el nombre libre se fundía con otro ensayo.
    roto = LARGO[:60]
    assert roto.endswith("(NCT044375") and "NCT04437511" not in roto
    # Un NCT al final de una descripción larga sobrevive aunque el texto se recorte.
    largo2 = "Participantes con Alzheimer temprano del ensayo de fase 3 de donanemab, brazo activo y placebo (NCT04437511)"
    r = M.recortar_nombre_cohorte(largo2)
    assert r.endswith("(NCT04437511)") and len(r) <= 60 + len(" (NCT04437511)") and M.canonizar_cohorte(r)["etiqueta"] == "TRAILBLAZER-ALZ 2"
    # NCT repetido se escribe una vez; minúsculas se normalizan.
    r2 = M.recortar_nombre_cohorte("x" * 50 + " nct01767311 y otra vez NCT01767311 al final del nombre")
    assert r2 == "x" * 50 + " (NCT01767311)" and r2.upper().count("NCT01767311") == 1
    # Nunca se corta por dentro de un identificador: el corte retrocede a su inicio.
    assert M.recortar_nombre_cohorte("y" * 55 + " NCT04437511 more") == "y" * 55 + " (NCT04437511)"


def test_recortar_nombre_cohorte_sin_nct_respeta_el_maximo_y_tolera_basura():
    assert M.recortar_nombre_cohorte("ADNI") == "ADNI"
    assert M.recortar_nombre_cohorte("  ADNI   y   BioFINDER ") == "ADNI y BioFINDER"
    assert len(M.recortar_nombre_cohorte("x" * 70)) == 60
    # Corta en un límite de palabra, quita la palabra suelta del final ("de") y conserva
    # los nombres del catálogo que el corte dejaba fuera (el estado de muestra).
    r = M.recortar_nombre_cohorte("Cohorte longitudinal con PET de amiloide positiva y PET de tau negativa al inicio (ADNI, A4)")
    assert r == "Cohorte longitudinal con PET de amiloide positiva y PET (ADNI, A4)" and M.canonizar_cohorte(r)["etiqueta"] == "ADNI"
    assert M.recortar_nombre_cohorte("Portadores de APOE4 genotipados para TREM2 R47H en ADNI y en la cohorte de FLENI") == "Portadores de APOE4 genotipados para TREM2 R47H en ADNI"
    assert M.recortar_nombre_cohorte(None) == "" and M.recortar_nombre_cohorte(7) == "7" and M.recortar_nombre_cohorte(b"ADNI") == "ADNI"
    assert M.recortar_nombre_cohorte("ADNI", maximo=0) == "" and M.recortar_nombre_cohorte("ADNI y BioFINDER", maximo=4) == "ADNI (BioFINDER)"
    assert M.recortar_nombre_cohorte("Cohorte Omega con seguimiento", maximo=13) == "Cohorte Omega"
    assert M.recortar_nombre_cohorte("(NCT04437511)") == "(NCT04437511)"
    assert M.recortar_nombre_cohorte("y" * 61 + " (NCT04437511)") == "y" * 60 + " (NCT04437511)"
    # Siete NCT seguidos: los que el corte deja fuera pasan al paréntesis, ninguno se pierde.
    siete = M.recortar_nombre_cohorte(" ".join(["NCT0000000%d" % i for i in range(7)]))
    assert all("NCT0000000%d" % i in siete for i in range(7)) and siete.endswith("(NCT00000005, NCT00000006)")


def test_nombres_que_solo_difieren_en_el_sufijo_numerico_no_se_funden():
    # En el catálogo: ALZ y ALZ 2 son ensayos distintos; ALZ 2, ALZ2 y ALZ-2 el mismo.
    assert M.cohortes_distintas([{"id": "a", "cohorte": "TRAILBLAZER-ALZ"}, {"id": "b", "cohorte": "TRAILBLAZER-ALZ-2"}, {"id": "c", "cohorte": "trailblazer-alz2"}, {"id": "d", "cohorte": "TRAILBLAZER-ALZ 2"}]) == ["TRAILBLAZER-ALZ", "TRAILBLAZER-ALZ 2"]
    # Fuera del catálogo: la regla de tokens pega el número a la palabra.
    assert M.misma_cohorte("Ensayo Omega", "Ensayo Omega 2") is False
    assert M.misma_cohorte("Ensayo Omega 2", "Ensayo Omega2") is True and M.misma_cohorte("Ensayo Omega 2", "Ensayo Omega-2") is True
    assert M.misma_cohorte("Cohorte Zeta 1", "Cohorte Zeta 10") is False
    assert M.cohortes_distintas([{"id": "a", "cohorte": "Cohorte Zeta 1"}, {"id": "b", "cohorte": "Cohorte Zeta 10"}, {"id": "c", "cohorte": "cohorte zeta1"}]) == ["Cohorte Zeta 1", "Cohorte Zeta 10"]
    # El número se pega a la palabra que lo precede ("fase2"), así que dos ensayos de fases
    # distintas del mismo fármaco siguen compartiendo el token del fármaco y se funden.
    assert {"fase2", "donanemab"} <= M._tokens_cohorte("ensayo de fase 2 de donanemab")
    assert M.misma_cohorte("ensayo de fase 2 de donanemab", "ensayo de fase 3 de donanemab") is True


def test_los_nombres_del_estado_de_muestra_que_no_son_cohorte_estan_en_ambiguos():
    for nombre in ("evoke", "evoke+", "FLENI"):
        assert nombre in M.AMBIGUOS and M.AMBIGUOS[nombre]
    assert M.cohorte_en_texto("these findings evoke a response in the FLENI cohort") == ""
    assert M.cohorte_en_texto("Fleni, Buenos Aires, Argentina") == ""
    # Los ensayos evoke se reconocen por su NCT, que es lo que dice el motivo.
    assert M.canonizar_cohorte("evoke+ (NCT04777409)")["etiqueta"] == "NCT04777409"
    assert M.canonizar_cohorte("evoke") is None
    # Las cohortes que sí nombra el estado de muestra resuelven a la primera del catálogo.
    assert M.canonizar_cohorte("Portadores de APOE4 genotipados para TREM2 R47H en ADNI y en la cohorte de FLENI")["etiqueta"] == "ADNI"
    assert M.canonizar_cohorte("Portadores de PSEN1 E280A (Antioquia) y cohorte de Alzheimer familiar de FLENI")["etiqueta"] == "API Colombia"
    assert M.canonizar_cohorte("Participantes de los ensayos evoke y evoke+ (semaglutida oral, fase 3)") is None
    # Los dos nombres libres del centro se funden por tokens (conservador: una cohorte, no dos).
    assert M.cohortes_distintas([{"id": "a", "cohorte": "cohorte de FLENI"}, {"id": "b", "cohorte": "cohorte de Alzheimer familiar de FLENI"}]) == ["cohorte de FLENI"]


def test_la_descripcion_de_certeza_que_lee_el_juez_es_coherente_con_la_regla():
    from rosa.modulos import firmas as F

    d = F.ConclusionHipotesis.model_fields["certeza"].description
    for pieza in ("techo_por_regla", "una sola cohorte", "dos o más cohortes distintas", "efecto grande", "1,0", "revisiones narrativas", "frases de introducción", "nunca sintéticos", "replicada en dos o más cohortes", "baja un nivel", "nunca por encima del techo", "no manda a muy_baja por sí sola"):
        assert pieza in d, pieza
    assert "muy baja si no hay evidencia directa" not in d and "muy_baja solo si no hay ningún apoyo" not in d
    f = F.ConclusionHipotesis.model_fields["factores"].description
    assert "Por qué" in f and "bajó" in f and "evidencia_indirecta" in f
    t = F.ConcluirHipotesis.model_fields["techo_por_regla"].json_schema_extra["desc"]
    assert "cohortes distintas que contó" in t and "todos los apoyos son indirectos" in t
    for texto in (d, f, t):
        assert "\u2014" not in texto
        assert not re.search(r"\b(por que|bajo|subio|imprecision|publicacion|replica|hipotesis)\b", texto), texto


def test_el_modulo_y_las_entradas_nuevas_no_llevan_guiones_largos_ni_palabras_sin_tilde():
    import inspect

    fuente = inspect.getsource(M)
    assert "\u2014" not in fuente
    for clave in ("evoke", "evoke+", "FLENI"):
        assert "\u2014" not in M.AMBIGUOS[clave] and not re.search(r"\b(ingles|medica|afiliacion|articulos|esporadico|semaglutida corriente)\b", M.AMBIGUOS[clave])
