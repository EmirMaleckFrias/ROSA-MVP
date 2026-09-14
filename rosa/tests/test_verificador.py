from rosa import verificador as V

F = V.Fragmento
FRAGS = [
    F("f1", "Cohorte clínica, 2025", "pág. 7", "El cociente alcanzó una precisión de 0,91 (IC 95 % 0,86-0,95) en la cohorte FLENI, con el ensayo NCT01234567 como referencia.", "Resultados"),
    F("f2", "Cummings et al., 2026", "resumen", "En 2026 hay 138 fármacos en 182 ensayos; lecanemab y donanemab están aprobados.", ""),
]


def c(texto, cita, frag=None):
    return V.comprobar_determinista(texto, cita, frag, FRAGS, FRAGS)


def test_cifras_normalizadas_van_al_juez_como_pista():
    r = c("La precision fue 0.91.", "[Cohorte clinica, 2025, pág. 7]")
    assert r.necesita_juez and "0.91" in r.pistas
    assert c("La precision fue 0.91.", "[Cohorte clinica, 2025, pag. 7]").necesita_juez


def test_identificador_ausente_es_no_sostenida_sin_juez():
    r = c("El ensayo NCT99999999 sirvio de referencia.", "[Cohorte clinica, 2025, pág. 7]")
    assert r.veredicto == "no_sostenida" and not r.necesita_juez


def test_cita_que_no_resuelve_y_sin_cita():
    assert c("Hay 138 fármacos.", "[Cummings et al., 2026, pág. 3]").veredicto == "cita_no_resuelve"
    assert c("Hay 138 fármacos.", "").veredicto == "sin_cita"
    assert c("Hay 138 fármacos.", "[Cummings et al., 2026, resumen]", "texto que no esta").veredicto == "cita_no_resuelve"


def test_ausencia_refutada_y_honesta():
    assert c("No encuentro información sobre lecanemab en los documentos.", "").veredicto == "ausencia_refutada"
    assert c("No encuentro información sobre aducanumab en los documentos.", "").veredicto == "sostenida"
    assert c("No pude comprobar lo de lecanemab.", "").veredicto == "sostenida"
    assert c("No hay datos sobre GEN 1 pero la precisión fue 0,91.", "").veredicto == "sin_cita"


def test_normalizacion_y_fidelidad():
    assert V.normalizar_cifra("1.234,5") == V.normalizar_cifra("1,234.5") == "1234.5"
    assert V.fidelidad(["sostenida", "parcial", "sin_cita", "sostenida"]) == 2 / 3
    assert V.fidelidad(["sin_cita"]) is None
    assert V.bloquea("ausencia_refutada") and not V.bloquea("parcial")
