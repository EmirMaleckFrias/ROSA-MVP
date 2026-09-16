"""El contrato del experimento: vocabularios cerrados, normalización de
registros antiguos, validación por regla, hash canónico de las lecturas,
veredicto por lectura y la lectura del negativo en dos ramas."""

import copy
import re
from types import SimpleNamespace

from rosa import experimento as X

ANTIGUO = {
    "protocolo": "1. Medir GFAP en plasma\n2. Comparar con controles",
    "ensayo": "GFAP en plasma por Simoa",
    "confirma": "GFAP aumenta al menos 20 % frente al control",
    "refuta": "cambio menor del 5 % con potencia para detectar 20 %",
    "controles": "control positivo: muestras con astrogliosis conocida",
    "costeEstimado": "bajo",
    "laboratorio": None,
    "estado": "propuesto",
    "ficheroDatos": None,
    "analisisPedido": "regresión en ADNI y A4",
}

LECTURAS = [
    {"nombre": "Fosforilación de TREM2 (western)", "tipo": "compromiso_diana", "queConfirma": "aumento de al menos 50 % frente a vehículo", "queRefuta": "cambio menor del 10 %", "control": "agonista conocido como positivo; vehículo como negativo", "unidad": "%"},
    {"nombre": "Fagocitosis de amiloide", "tipo": "funcion_mecanismo", "queConfirma": "aumenta al menos 30 % frente a vehículo", "queRefuta": "cambio menor del 10 % con potencia para 30 %", "control": "citocalasina D como negativo", "unidad": "%"},
    {"nombre": "Viabilidad (LDH)", "tipo": "viabilidad", "queConfirma": "viabilidad al menos 80 %", "queRefuta": "viabilidad menor del 60 %", "control": "vehículo", "unidad": "%"},
]

COMPLETO = {
    "protocolo": "1. Tratar microglía iPSC con el compuesto",
    "ensayo": "",
    "confirma": "",
    "refuta": "",
    "costeEstimado": "medio",
    "laboratorio": None,
    "estado": "propuesto",
    "ficheroDatos": None,
    "analisisPedido": "",
    "lecturas": LECTURAS,
    "sistema": {"tipo": "ipsc", "quePrueba": "que activar TREM2 aumenta la fagocitosis en microglía humana", "queNoRepresenta": "la edad ni el entorno del cerebro envejecido"},
    "propositoBiomarcador": None,
    "nivelDesenlace": "celular",
    "puenteAlBeneficio": "haría falta ver menos placas en un modelo animal y después un marcador en personas",
}


def _cifras(**pares):
    return [{"nombre": n, "valor": v} for n, v in pares.items()]


# -- Vocabularios ---------------------------------------------------------------


def test_vocabularios_cerrados_con_definicion_en_una_frase():
    for vocab in (X.PROPOSITOS_BIOMARCADOR, X.NIVELES_DESENLACE, X.SISTEMAS_EXPERIMENTALES, X.TIPOS_LECTURA):
        for clave, v in vocab.items():
            assert re.fullmatch(r"[a-z_]+", clave), clave  # identificadores sin tilde
            assert v["etiqueta"] and v["definicion"].endswith(".") and len(v["definicion"]) > 30
    assert set(X.PROPOSITOS_BIOMARCADOR) == {"susceptibilidad_riesgo", "diagnostico", "monitorizacion", "pronostico", "prediccion_respuesta", "farmacodinamico_respuesta", "seguridad"}
    assert set(X.NIVELES_DESENLACE) == {"molecular", "celular", "fisiologico_imagen", "funcional_clinico"}
    assert set(X.SISTEMAS_EXPERIMENTALES) == {"observacional_humano", "datos_publicos_existentes", "celulas_humanas_donante", "ipsc", "organoide", "cocultivo", "animal", "in_silico"}
    assert set(X.TIPOS_LECTURA) == {"compromiso_diana", "viabilidad", "funcion_mecanismo", "biomarcador", "seguridad"}
    # Los Literal de los modelos pydantic y los vocabularios dicen lo mismo.
    assert set(X.Proposito.__args__) == set(X.PROPOSITOS_BIOMARCADOR) and set(X.TipoSistema.__args__) == set(X.SISTEMAS_EXPERIMENTALES)
    assert set(X.NivelDesenlace.__args__) == set(X.NIVELES_DESENLACE) and set(X.TipoLectura.__args__) == set(X.TIPOS_LECTURA)
    assert X.que_no_representa_por_defecto("animal") == "no reproduce la variación genética humana ni la edad; los ratones con amiloide no desarrollan tau ni neurodegeneración completa"
    assert X.que_no_representa_por_defecto("marciano") == "" and X.que_no_representa_por_defecto(None) == ""
    v = X.vocabularios()
    assert v["sistemasExperimentales"]["animal"]["queNoRepresenta"] and v["sistemasExperimentales"]["in_silico"]["intervencional"] is False
    assert X.etiqueta(X.TIPOS_LECTURA, "funcion_mecanismo") == "función o mecanismo" and X.etiqueta(X.TIPOS_LECTURA, "otra_cosa") == "otra cosa" and X.etiqueta(X.TIPOS_LECTURA, None) == ""


def test_modelos_pydantic_rechazan_valores_fuera_del_vocabulario():
    import pytest
    from pydantic import ValidationError

    l = X.LecturaPropuesta(nombre="GFAP", tipo="biomarcador", que_confirma="sube", que_refuta="no sube")
    assert l.control == "" and l.unidad == ""
    with pytest.raises(ValidationError):
        X.LecturaPropuesta(nombre="GFAP", tipo="cualquiera", que_confirma="sube", que_refuta="no sube")
    with pytest.raises(ValidationError):
        X.SistemaPropuesto(tipo="raton", que_prueba="x")
    c = X.ContratoPropuesto()
    assert c.lecturas == [] and c.sistema is None and c.proposito_biomarcador is None and c.nivel_desenlace is None and c.puente_al_beneficio == ""


# -- Normalizar -----------------------------------------------------------------


def test_normalizar_un_experimento_antiguo_deriva_una_lectura_sin_inventar():
    n, motivos = X.normalizar_contrato(ANTIGUO, con_motivos=True)
    assert n["lecturas"] == [{"nombre": "GFAP en plasma por Simoa", "tipo": "biomarcador", "queConfirma": ANTIGUO["confirma"], "queRefuta": ANTIGUO["refuta"], "control": ANTIGUO["controles"], "unidad": ""}]
    assert n["sistema"] is None and n["propositoBiomarcador"] is None and n["nivelDesenlace"] is None and n["puenteAlBeneficio"] == ""
    assert any("registro antiguo" in m and "con los controles" in m for m in motivos)
    # No toca el original ni pierde las claves antiguas.
    assert "lecturas" not in ANTIGUO and n["protocolo"] == ANTIGUO["protocolo"] and n["analisisPedido"] == ANTIGUO["analisisPedido"]
    # Es idempotente: normalizar lo normalizado no cambia nada.
    assert X.normalizar_contrato(n) == n


def test_normalizar_no_rompe_con_vacios_ni_basura_ni_valores_fuera_del_vocabulario():
    for vacio in (None, {}, "texto", 3, []):
        n = X.normalizar_contrato(vacio)
        assert n["lecturas"] == [] and n["sistema"] is None and n["puenteAlBeneficio"] == ""
    n, motivos = X.normalizar_contrato({"ensayo": "", "confirma": "", "refuta": "", "lecturas": "no es lista", "sistema": "ipsc", "propositoBiomarcador": "adivinar", "nivelDesenlace": 7, "puenteAlBeneficio": None}, con_motivos=True)
    assert n["lecturas"] == [] and n["propositoBiomarcador"] is None and n["nivelDesenlace"] is None and n["puenteAlBeneficio"] == ""
    # Un sistema que viene como cadena es su tipo: no se inventa lo que prueba ni lo que no representa.
    assert n["sistema"] == {"tipo": "ipsc", "quePrueba": "", "queNoRepresenta": ""} and any("venía como texto" in m for m in motivos)
    assert X.normalizar_contrato({"sistema": 3})["sistema"] is None and X.normalizar_contrato({"sistema": ["ipsc"]})["sistema"] is None
    assert any("fuera del vocabulario" in m for m in motivos) and any("no era una lista" in m for m in motivos)
    # Lecturas en snake_case (como salen del modelo) y entradas basura mezcladas.
    n = X.normalizar_contrato({"lecturas": [{"nombre": "GFAP", "tipo": "biomarcador", "que_confirma": "sube", "que_refuta": "baja"}, None, "x", {}]})
    assert n["lecturas"] == [{"nombre": "GFAP", "tipo": "biomarcador", "queConfirma": "sube", "queRefuta": "baja", "control": "", "unidad": ""}]
    # Solo criterios, sin ensayo: la lectura existe con nombre genérico.
    n = X.normalizar_contrato({"confirma": "sube", "refuta": "baja"})
    assert n["lecturas"][0]["nombre"] == "medida principal" and n["lecturas"][0]["control"] == ""


def test_contrato_desde_propuesta_acepta_el_modelo_nuevo_y_la_firma_antigua():
    propuesta = X.ContratoPropuesto(
        lecturas=[X.LecturaPropuesta(nombre="p-tau181 en medio", tipo="biomarcador", que_confirma="baja al menos 25 %", que_refuta="cambio menor del 5 %", control="vehículo", unidad="pg/mL")],
        sistema=X.SistemaPropuesto(tipo="ipsc", que_prueba="x", que_no_representa="la edad"),
        proposito_biomarcador="farmacodinamico_respuesta",
        nivel_desenlace="molecular",
        puente_al_beneficio="haría falta lo mismo en LCR de personas",
    )
    c = X.contrato_desde_propuesta(propuesta)
    assert c["lecturas"][0]["queConfirma"] == "baja al menos 25 %" and c["lecturas"][0]["unidad"] == "pg/mL"
    assert c["sistema"] == {"tipo": "ipsc", "quePrueba": "x", "queNoRepresenta": "la edad"} and c["propositoBiomarcador"] == "farmacodinamico_respuesta" and c["nivelDesenlace"] == "molecular"
    # Una firma antigua sin los atributos nuevos da los valores vacíos, no un error.
    antigua = SimpleNamespace(protocolo=["a"], ensayo="GFAP", resultado_que_confirma="sube", resultado_que_refuta="baja")
    assert X.contrato_desde_propuesta(antigua) == dict(X.CLAVES_CONTRATO)


# -- Validar --------------------------------------------------------------------


def test_validar_un_registro_antiguo_dice_lo_que_le_falta_y_los_datos_controlados():
    problemas = X.validar_contrato(ANTIGUO)
    assert any("no declara el sistema experimental" in p for p in problemas)
    assert any("acceso controlado (A4, ADNI)" in p and "solo con datos públicos" in p for p in problemas)
    assert any("biomarcador sin propósito BEST" in p for p in problemas)
    assert any("no declara el nivel del desenlace" in p for p in problemas)
    assert not any("falta el control" in p for p in problemas)  # los controles antiguos pasan a la lectura
    sin_control = dict(ANTIGUO, controles="", analisisPedido="")
    assert any(p.startswith("falta el control de la lectura «GFAP en plasma por Simoa»") for p in X.validar_contrato(sin_control))
    assert not any("acceso controlado" in p for p in X.validar_contrato(sin_control))


def test_validar_contratos_incompletos():
    assert X.validar_contrato(None) == ["no hay experimento propuesto"] and X.validar_contrato({}) == ["no hay experimento propuesto"]
    assert X.validar_contrato(COMPLETO) == []
    # Sistema sin lo que no representa: el problema trae el límite general del vocabulario.
    c = copy.deepcopy(COMPLETO)
    c["sistema"]["queNoRepresenta"] = ""
    [p] = X.validar_contrato(c)
    assert p.startswith("el sistema no dice qué no representa") and "madurez epigenética" in p
    # Sistema con intervención sin compromiso de diana ni viabilidad: las dos ramas no se distinguen.
    c = copy.deepcopy(COMPLETO)
    c["lecturas"] = [LECTURAS[1]]
    ps = X.validar_contrato(c)
    assert any("compromiso de diana" in p and "no se tocó" in p for p in ps) and any("viabilidad" in p and "toxicidad" in p for p in ps)
    # En animal no se exige viabilidad; en observacional no se exige compromiso de diana.
    c["sistema"] = {"tipo": "animal", "quePrueba": "x", "queNoRepresenta": "y"}
    assert not any("viabilidad" in p for p in X.validar_contrato(c)) and any("compromiso de diana" in p for p in X.validar_contrato(c))
    c["sistema"] = {"tipo": "observacional_humano", "quePrueba": "x", "queNoRepresenta": "y"}
    assert not any("compromiso de diana" in p for p in X.validar_contrato(c))
    # Desenlace molecular vendido como beneficio clínico sin puente.
    c = copy.deepcopy(COMPLETO)
    c["nivelDesenlace"], c["puenteAlBeneficio"] = "molecular", ""
    c["lecturas"][1]["queConfirma"] = "mejora cognitiva: aumenta al menos 30 %"
    [p] = X.validar_contrato(c)
    assert p.startswith("el desenlace molecular se presenta como beneficio clínico sin puente") and "«cognitiva»" in p
    c["lecturas"][1]["queConfirma"] = "aumenta al menos 30 %"
    [p] = X.validar_contrato(c)
    assert p.startswith("el desenlace es molecular y el experimento no declara el puente")
    # Con desenlace clínico no hace falta puente.
    c["nivelDesenlace"] = "funcional_clinico"
    assert X.validar_contrato(c) == []


def test_validar_lecturas_mal_formadas_y_vocabulario_roto():
    c = copy.deepcopy(COMPLETO)
    c["lecturas"] = [
        {"nombre": "", "tipo": "olfato", "queConfirma": "sube", "queRefuta": "sube", "control": ""},
        {"nombre": "GFAP", "tipo": "biomarcador", "queConfirma": "", "queRefuta": "", "control": "x"},
        {"nombre": "gfap ", "tipo": "biomarcador", "queConfirma": "a", "queRefuta": "b", "control": "x"},
        LECTURAS[0],
        LECTURAS[2],
    ]
    c["propositoBiomarcador"], c["nivelDesenlace"] = "adivinar", "cuantico"
    ps = X.validar_contrato(c)
    assert "la lectura 1 no tiene nombre (qué se mide y con qué técnica)" in ps
    assert any("tipo fuera del vocabulario: «olfato»" in p for p in ps)
    assert any("confirma y refuta con el mismo criterio" in p for p in ps)
    assert "falta el control de la lectura «lectura 1»: sin control positivo y negativo un negativo no se interpreta" in ps
    assert "la lectura «GFAP» no dice qué resultado confirma la hipótesis" in ps and "la lectura «GFAP» no dice qué resultado la refuta" in ps
    assert "la lectura «gfap» aparece dos veces" in ps
    assert "el propósito del biomarcador «adivinar» está fuera del vocabulario BEST" in ps and "el nivel del desenlace «cuantico» está fuera del vocabulario" in ps
    assert any("sin propósito BEST" in p for p in ps)  # el valor roto cuenta como no declarado
    # Sistema con tipo desconocido y sin textos.
    c["sistema"] = {"tipo": "raton_transgenico", "quePrueba": "", "queNoRepresenta": ""}
    ps = X.validar_contrato(c)
    assert "el sistema experimental «raton_transgenico» no está en el vocabulario" in ps and "el sistema no dice qué prueba de la hipótesis" in ps and "el sistema no dice qué no representa" in ps


# -- Hash -----------------------------------------------------------------------


def test_hash_estable_e_independiente_del_orden_y_de_las_claves_de_mas():
    a = copy.deepcopy(COMPLETO)
    b = copy.deepcopy(COMPLETO)
    b["lecturas"] = list(reversed(b["lecturas"]))
    b["lecturas"][0]["id"] = "lec-1-inv-9"  # id heredado con sufijo -inv-
    b["lecturas"][1]["id"] = "lec-1-inv-9"  # repetido, y da igual
    b["lecturas"][2]["marcaInterfaz"] = True
    b["lecturas"][2]["nombre"] = "  Fosforilación de TREM2   (western) "
    assert X.lecturas_para_hash(a) == X.lecturas_para_hash(b)
    assert X.hash_lecturas(a) == X.hash_lecturas(b) and re.fullmatch(r"[0-9a-f]{64}", X.hash_lecturas(a))
    assert all(set(l) == {"nombre", "tipo", "queConfirma", "queRefuta", "control", "unidad"} for l in X.lecturas_para_hash(b))
    # Cambiar un criterio cambia el hash; un registro antiguo y su forma normalizada dan el mismo.
    c = copy.deepcopy(COMPLETO)
    c["lecturas"][1]["queRefuta"] = "cambio menor del 15 %"
    assert X.hash_lecturas(c) != X.hash_lecturas(a)
    assert X.hash_lecturas(ANTIGUO) == X.hash_lecturas(X.normalizar_contrato(ANTIGUO))
    assert X.lecturas_para_hash(None) == [] and X.lecturas_para_hash({}) == []
    # Mismo hash canónico que rosa/sello.py, así el sello externo puede cubrirlo.
    from rosa.sello import hash_canonico

    assert X.hash_lecturas(a) == hash_canonico(X.lecturas_para_hash(a))


def test_bloque_prerregistro_lleva_lecturas_hash_sistema_y_puente():
    L = X.bloque_prerregistro(COMPLETO)
    texto = "\n".join(L)
    assert "## Lecturas fijadas de antemano" in texto and X.hash_lecturas(COMPLETO) in texto and "orden canónico" in texto
    assert "Sistema experimental: células iPSC" in texto and "Nivel del desenlace: celular." in texto and "Puente al beneficio: haría falta" in texto
    assert X.bloque_prerregistro({}) == [] and X.bloque_prerregistro(None) == []
    # Un registro antiguo también se congela con su lectura derivada.
    assert "GFAP en plasma por Simoa [biomarcador]" in "\n".join(X.bloque_prerregistro(ANTIGUO))


# -- Criterios y veredictos por lectura -----------------------------------------


def test_evaluar_criterio_por_regla_en_castellano_e_ingles():
    assert X.evaluar_criterio("GFAP aumenta al menos 20 % frente al control", "+35 %")[0] is True
    ok, motivo = X.evaluar_criterio("GFAP aumenta al menos 20 % frente al control", "-12 %")
    assert ok is False and "dirección contraria" in motivo
    assert X.evaluar_criterio("cambio menor del 5 %", "+3 %")[0] is True
    ok, motivo = X.evaluar_criterio("cambio menor del 5 %", "-12 %")
    assert ok is False and "valor absoluto" in motivo
    assert X.evaluar_criterio("p < 0,05", "0,03")[0] is True and X.evaluar_criterio("p < 0,05", "0.2")[0] is False
    assert X.evaluar_criterio("p < 0,05 y aumento ≥ 20 %", "+35 %")[0] is True  # elige el umbral compatible con la cifra
    assert X.evaluar_criterio("phagocytosis increases by more than 30 % vs vehicle", "increase of 40 %")[0] is True
    assert X.evaluar_criterio("phagocytosis increases by more than 30 % vs vehicle", "decrease of 40 %")[0] is False
    assert X.evaluar_criterio("reduce más de un 30 %", "35 %")[0] is True and X.evaluar_criterio("reducción de al menos 30 %", "reducción del 12 %")[0] is False
    assert X.evaluar_criterio("viabilidad al menos 80 %", "91 %")[0] is True
    # Lo que la regla no entiende lo dice y devuelve None, nunca adivina.
    ok, motivo = X.evaluar_criterio("GFAP se altera antes que NfL", "GFAP primero")
    assert ok is None and "no trae un número" in motivo
    ok, motivo = X.evaluar_criterio("sin cambio frente al control", "12")
    assert ok is None and "no tiene umbral ni dirección" in motivo
    ok, motivo = X.evaluar_criterio("aumento de al menos 20 %", "0,35")
    assert ok is None and "porcentaje" in motivo
    assert X.evaluar_criterio("", "3")[0] is None and X.evaluar_criterio("sube", "")[0] is None and X.evaluar_criterio(None, None)[0] is None
    ok, motivo = X.evaluar_criterio("aumenta al menos 20 %", "sin cambio")
    assert ok is False


def test_veredictos_por_lectura_con_cifras_nombradas():
    res = {"veredicto": "refuta", "resultado": "La fagocitosis no cambió.", "motivo": "TREM2 se fosforiló pero la fagocitosis quedó igual.", "limitaciones": "", "cifras": _cifras(**{"Fosforilación de TREM2": "+70 %", "Fagocitosis de amiloide": "+2 %", "Viabilidad (LDH)": "91 %", "n": "24"})}
    vs = X.veredicto_por_lecturas(LECTURAS, res)
    assert [(v["lectura"], v["tipo"], v["veredicto"]) for v in vs] == [("Fosforilación de TREM2 (western)", "compromiso_diana", "confirma"), ("Fagocitosis de amiloide", "funcion_mecanismo", "refuta"), ("Viabilidad (LDH)", "viabilidad", "confirma")]
    assert "cumple el criterio de confirmación" in vs[0]["motivo"] and vs[0]["cifras"] == ["Fosforilación de TREM2 = +70 %"]
    assert "cumple el criterio de refutación" in vs[1]["motivo"]
    # La cifra «n» no se cuela en ninguna lectura.
    assert all("n = 24" not in v["cifras"] for v in vs)
    # Entre los dos criterios: inconcluso, con el motivo.
    vs = X.veredicto_por_lecturas([LECTURAS[1]], _cifras(**{"Fagocitosis de amiloide": "+20 %"}))
    assert vs[0]["veredicto"] == "inconcluso" and "no cumple el criterio de confirmación ni el de refutación" in vs[0]["motivo"]
    # Sin cifra que la nombre: no pude comprobar, nunca "no hay efecto".
    vs = X.veredicto_por_lecturas(LECTURAS, {"veredicto": "refuta", "cifras": [], "motivo": "", "resultado": ""})
    assert all(v["veredicto"] == "no_evaluable" and "no pude comprobar" in v["motivo"] for v in vs)
    vs = X.veredicto_por_lecturas(LECTURAS, _cifras(**{"NfL plasma": "+40 %"}))
    assert all(v["veredicto"] == "no_evaluable" for v in vs) and "el resultado no trae cifras" not in vs[0]["motivo"]
    # Acepta las lecturas dentro del experimento entero (también uno antiguo) y cifras como objetos.
    vs = X.veredicto_por_lecturas(ANTIGUO, [SimpleNamespace(nombre="GFAP en plasma", valor="+35 %")])
    assert vs[0]["veredicto"] == "confirma" and vs[0]["tipo"] == "biomarcador"
    # Un resultado pydantic (objeto con .cifras y .veredicto) también vale.
    vs = X.veredicto_por_lecturas(ANTIGUO, SimpleNamespace(veredicto="refuta", cifras=[SimpleNamespace(nombre="GFAP plasma", valor="+1 %")], motivo="", resultado="", limitaciones=""))
    assert vs[0]["veredicto"] == "refuta"


def test_veredictos_cruzan_idiomas_por_simbolo_y_usan_al_juez_como_respaldo():
    # Lectura en castellano, cifra en inglés: emparejan por el símbolo TREM2; la fagocitosis, sin símbolo, no.
    vs = X.veredicto_por_lecturas(LECTURAS[:2], _cifras(**{"TREM2 phosphorylation": "+70 %", "Amyloid phagocytosis": "+1 %"}))
    assert vs[0]["veredicto"] == "confirma" and "símbolo compartido (trem2)" in vs[0]["motivo"]
    assert vs[1]["veredicto"] == "no_evaluable"
    # Dos lecturas del mismo símbolo en matrices distintas: el símbolo no las mezcla si el nombre ya reclamó la cifra.
    dos = [{"nombre": "GFAP en plasma", "tipo": "biomarcador", "queConfirma": "aumenta al menos 20 %", "queRefuta": "cambio menor del 5 %", "control": "x"}, {"nombre": "GFAP en LCR", "tipo": "biomarcador", "queConfirma": "aumenta al menos 20 %", "queRefuta": "cambio menor del 5 %", "control": "x"}]
    vs = X.veredicto_por_lecturas(dos, _cifras(**{"GFAP plasma": "+30 %"}))
    assert [v["veredicto"] for v in vs] == ["confirma", "no_evaluable"]
    # Criterio sin número: la regla no decide y busca la frase del juez sobre esa lectura.
    orden = [{"nombre": "Orden GFAP/NfL", "tipo": "biomarcador", "queConfirma": "GFAP se altera antes que NfL", "queRefuta": "NfL antes o a la vez", "control": "x"}]
    res = {"veredicto": "confirma", "cifras": _cifras(**{"Orden GFAP/NfL": "GFAP 2,1 años antes"}), "motivo": "El orden GFAP/NfL confirma la predicción. La muestra es pequeña.", "resultado": "", "limitaciones": ""}
    [v] = X.veredicto_por_lecturas(orden, res)
    assert v["veredicto"] == "confirma" and "el juez dice de esta lectura" in v["motivo"] and "la regla no pudo aplicar" in v["motivo"]
    [v] = X.veredicto_por_lecturas(orden, res["cifras"], texto_juez="The GFAP/NfL order was refuted: NfL changed first.")
    assert v["veredicto"] == "refuta"
    [v] = X.veredicto_por_lecturas(orden, res["cifras"], texto_juez="El orden GFAP/NfL no permite concluir nada.")
    assert v["veredicto"] == "inconcluso"
    [v] = X.veredicto_por_lecturas(orden, res["cifras"], texto_juez="El orden GFAP/NfL no confirma la predicción.")
    assert v["veredicto"] == "inconcluso"
    # Sin frase del juez: una sola lectura hereda el veredicto global; con varias, inconcluso y pide lectura humana.
    [v] = X.veredicto_por_lecturas(orden, dict(res, motivo="", veredicto="inconcluso"))
    assert v["veredicto"] == "inconcluso" and "hereda el veredicto global" in v["motivo"]
    vs = X.veredicto_por_lecturas(orden + [LECTURAS[2]], dict(res, motivo="", cifras=res["cifras"] + _cifras(**{"Viabilidad (LDH)": "90 %"})))
    assert vs[0]["veredicto"] == "inconcluso" and "hace falta lectura humana" in vs[0]["motivo"] and vs[1]["veredicto"] == "confirma"


def test_veredictos_no_rompen_con_entradas_raras():
    assert X.veredicto_por_lecturas(None, None) == [] and X.veredicto_por_lecturas([], _cifras(a="1")) == [] and X.veredicto_por_lecturas("x", 3) == []
    vs = X.veredicto_por_lecturas([None, "x", {}, LECTURAS[2]], [None, {"nombre": "", "valor": "9"}, {"valor": "1"}, {"nombre": "Viabilidad (LDH)", "valor": None}])
    assert len(vs) == 1 and vs[0]["veredicto"] == "inconcluso"  # hay cifra pero vacía: la regla no la aplica y el juez no habló
    # Criterios que se solapan: las dos ramas se cumplen y el veredicto es inconcluso con el motivo.
    solapa = [{"nombre": "GFAP", "tipo": "biomarcador", "queConfirma": "sube al menos 10 %", "queRefuta": "sube al menos 5 %", "control": "x"}]
    [v] = X.veredicto_por_lecturas(solapa, _cifras(GFAP="+20 %"))
    assert v["veredicto"] == "inconcluso" and "se solapan" in v["motivo"]
    # Dos cifras de la misma lectura que deciden distinto.
    [v] = X.veredicto_por_lecturas([LECTURAS[2]], [{"nombre": "Viabilidad LDH día 1", "valor": "91 %"}, {"nombre": "Viabilidad LDH día 3", "valor": "40 %"}])
    assert v["veredicto"] == "inconcluso" and "deciden distinto" in v["motivo"]


# -- Las dos ramas del negativo ---------------------------------------------------


def _v(lectura, tipo, veredicto):
    return {"lectura": lectura, "tipo": tipo, "veredicto": veredicto, "motivo": ""}


def test_lectura_del_negativo_en_dos_ramas():
    r = X.lectura_del_negativo([_v("Fosforilación de TREM2", "compromiso_diana", "confirma"), _v("Fagocitosis", "funcion_mecanismo", "refuta"), _v("Viabilidad", "viabilidad", "confirma")])
    assert r["rama"] == "diana_comprometida_sin_efecto" and "cuestiona el mecanismo" in r["explicacion"] and "Fagocitosis refuta" in r["explicacion"]
    r = X.lectura_del_negativo([_v("Fosforilación de TREM2", "compromiso_diana", "refuta"), _v("Fagocitosis", "funcion_mecanismo", "refuta")])
    assert r["rama"] == "diana_no_comprometida" and "actividad del compuesto, de la exposición o del ensayo" in r["explicacion"] and "queda sin probar" in r["explicacion"]
    # Sin lectura de compromiso de diana, las ramas no se distinguen.
    r = X.lectura_del_negativo([_v("GFAP", "biomarcador", "refuta")])
    assert r["rama"] == "sin_lecturas_separadas" and "no se tocó" in r["explicacion"]
    # Compromiso refutado aunque el efecto quede inconcluso: sigue siendo la rama del ensayo.
    assert X.lectura_del_negativo([_v("a", "compromiso_diana", "refuta"), _v("b", "biomarcador", "inconcluso")])["rama"] == "diana_no_comprometida"


def test_lectura_del_negativo_devuelve_none_cuando_no_es_negativo_o_no_pudo_comprobar():
    assert X.lectura_del_negativo([]) == {"rama": None, "explicacion": "sin veredictos por lectura: no hay nada que leer"}
    assert X.lectura_del_negativo(None)["rama"] is None and X.lectura_del_negativo("x")["rama"] is None
    r = X.lectura_del_negativo([_v("a", "compromiso_diana", "confirma"), _v("b", "funcion_mecanismo", "confirma")])
    assert r["rama"] is None and "no es un negativo" in r["explicacion"]
    r = X.lectura_del_negativo([_v("a", "compromiso_diana", "no_evaluable"), _v("b", "funcion_mecanismo", "refuta")])
    assert r["rama"] is None and "no pude comprobar" in r["explicacion"]
    r = X.lectura_del_negativo([_v("a", "compromiso_diana", "confirma"), _v("b", "funcion_mecanismo", "inconcluso")])
    assert r["rama"] is None and "no es un negativo interpretable" in r["explicacion"]
    r = X.lectura_del_negativo([_v("a", "compromiso_diana", "confirma"), _v("b", "funcion_mecanismo", "refuta"), _v("c", "biomarcador", "no_evaluable")])
    assert r["rama"] is None and "negativo es parcial" in r["explicacion"]
    r = X.lectura_del_negativo([_v("a", "compromiso_diana", "confirma"), _v("a2", "compromiso_diana", "refuta"), _v("b", "funcion_mecanismo", "refuta")])
    assert r["rama"] is None and "se contradicen" in r["explicacion"]
    r = X.lectura_del_negativo([_v("a", "compromiso_diana", "confirma")])
    assert r["rama"] is None and "no hay lectura de efecto" in r["explicacion"]
    # La viabilidad fallida se dice siempre: parte de lo observado puede ser toxicidad.
    r = X.lectura_del_negativo([_v("a", "compromiso_diana", "confirma"), _v("b", "funcion_mecanismo", "refuta"), _v("LDH", "viabilidad", "refuta")])
    assert r["rama"] == "diana_comprometida_sin_efecto" and "toxicidad" in r["explicacion"]
    # Entradas basura entre los veredictos no rompen.
    assert X.lectura_del_negativo([None, "x", {"tipo": "compromiso_diana"}, _v("b", "funcion_mecanismo", "refuta")])["rama"] is None


def test_de_los_veredictos_a_la_rama_de_punta_a_punta():
    res = {"veredicto": "refuta", "cifras": _cifras(**{"Fosforilación de TREM2": "+70 %", "Fagocitosis de amiloide": "+2 %", "Viabilidad (LDH)": "91 %"}), "motivo": "", "resultado": "", "limitaciones": ""}
    assert X.lectura_del_negativo(X.veredicto_por_lecturas(COMPLETO, res))["rama"] == "diana_comprometida_sin_efecto"
    res["cifras"][0]["valor"] = "+3 %"
    assert X.lectura_del_negativo(X.veredicto_por_lecturas(COMPLETO, res))["rama"] == "diana_no_comprometida"
    assert X.texto_lectura_del_negativo(X.veredicto_por_lecturas(COMPLETO, res)).startswith("Diana no comprometida (actividad, exposición o ensayo): ")
    # El registro antiguo, con una sola lectura, no separa las ramas.
    assert X.lectura_del_negativo(X.veredicto_por_lecturas(ANTIGUO, _cifras(**{"GFAP en plasma": "+1 %"})))["rama"] == "sin_lecturas_separadas"


# -- Textos ---------------------------------------------------------------------

SIN_TILDE = re.compile(r"\b(hipotesis|direccion|confirmacion|refutacion|proposito|clinico|farmacodinamico|diagnostico|pronostico|monitorizacion|fisiologico|funcion|canonico|exposicion|tecnica|numero|regresion|celulas|vehiculo|senal|tendria|habria|estara|mas|limite|genetica|epigenetica|toxico|linea)\b")


def _sin_tildes_ni_guiones(texto: str) -> None:
    assert "\u2014" not in texto  # guion largo (U+2014)
    m = SIN_TILDE.search(texto)
    assert not m, f"palabra sin tilde en un texto: «{m.group(0)}»"


def test_textos_con_tildes_y_sin_guiones_largos():
    t = X.texto_contrato(COMPLETO)
    assert t.startswith("Contrato del experimento (qué se mide, en qué sistema y qué significa cada resultado):")
    assert "Sistema experimental: células iPSC" in t and "función o mecanismo" in t and "Propósito del biomarcador (BEST): no declarado" in t and "Problemas del contrato por regla: ninguno." in t
    _sin_tildes_ni_guiones(t)
    t = X.texto_contrato(ANTIGUO)
    assert "Lecturas (1):" in t and "GFAP en plasma por Simoa [biomarcador]" in t and "Sistema experimental: no declarado" in t and "no declara el sistema experimental" in t
    assert "Puente al beneficio: no declarado; el resultado, por sí solo, no habla de beneficio para una persona" in t
    _sin_tildes_ni_guiones(t)
    assert X.texto_contrato(None) == "Sin contrato de experimento." and X.texto_contrato({}) == "Sin contrato de experimento."
    # Sistema sin lo que no representa: el texto enseña el límite general y dice que no está declarado.
    c = copy.deepcopy(COMPLETO)
    c["sistema"]["queNoRepresenta"] = ""
    assert "No representa: no declarado; límite general de este sistema: no reproduce la edad" in X.texto_contrato(c)
    for texto in ("\n".join(X.bloque_prerregistro(COMPLETO)), X.texto_lectura_del_negativo([_v("a", "compromiso_diana", "refuta"), _v("b", "biomarcador", "refuta")]), " ".join(X.validar_contrato(ANTIGUO)), " ".join(X.validar_contrato({"lecturas": [{"nombre": "x", "tipo": "raro"}]}))):
        _sin_tildes_ni_guiones(texto)
    for vocab in (X.PROPOSITOS_BIOMARCADOR, X.NIVELES_DESENLACE, X.SISTEMAS_EXPERIMENTALES, X.TIPOS_LECTURA):
        for v in vocab.values():
            _sin_tildes_ni_guiones(v["etiqueta"] + " " + v["definicion"] + " " + str(v.get("que_no_representa", "")))
    # Y las explicaciones de los veredictos y de las ramas.
    for v in X.veredicto_por_lecturas(COMPLETO, {"veredicto": "refuta", "cifras": _cifras(**{"Fosforilación de TREM2": "+3 %"}), "motivo": "", "resultado": ""}):
        _sin_tildes_ni_guiones(v["motivo"])
    _sin_tildes_ni_guiones(X.lectura_del_negativo([_v("a", "compromiso_diana", "confirma")])["explicacion"])


# -- Adversariales (16 de septiembre de 2026): lo que se rompió y se arregló ------


def test_vocabulario_escrito_de_otra_forma_se_normaliza_sin_interpretar():
    # Mayúsculas, tildes, espacios y etiquetas legibles se llevan a la clave; lo que no corresponde se queda tal cual.
    n, motivos = X.normalizar_contrato({
        "lecturas": [{"nombre": "GFAP", "tipo": "Biomarcador", "queConfirma": "a", "queRefuta": "b"}, {"nombre": "TREM2", "tipo": "compromiso de diana", "queConfirma": "a", "queRefuta": "b"}, {"nombre": "LDH", "tipo": "VIABILIDAD ", "queConfirma": "a", "queRefuta": "b"}],
        "sistema": {"tipo": "iPSC", "quePrueba": "x", "queNoRepresenta": "y"},
        "propositoBiomarcador": "Diagnóstico", "nivelDesenlace": "fisiológico o de imagen", "puenteAlBeneficio": "z",
    }, con_motivos=True)
    assert [l["tipo"] for l in n["lecturas"]] == ["biomarcador", "compromiso_diana", "viabilidad"]
    assert n["sistema"]["tipo"] == "ipsc" and n["propositoBiomarcador"] == "diagnostico" and n["nivelDesenlace"] == "fisiologico_imagen"
    assert any("escrito de otra forma" in m for m in motivos)
    assert not any("fuera del vocabulario" in p for p in X.validar_contrato({"lecturas": n["lecturas"], "sistema": {"tipo": "In Silico", "quePrueba": "x", "queNoRepresenta": "y"}, "propositoBiomarcador": "Diagnóstico", "nivelDesenlace": "Molecular", "puenteAlBeneficio": "z"}))
    # «ratón» no se convierte en «animal»: eso sería interpretar.
    assert X._clave_vocabulario("ratón", X.SISTEMAS_EXPERIMENTALES) == ("ratón", False)
    assert X.normalizar_contrato({"sistema": "ratón"})["sistema"]["tipo"] == "ratón"
    assert any("«ratón» no está en el vocabulario" in p for p in X.validar_contrato({"ensayo": "x", "confirma": "a", "refuta": "b", "sistema": "ratón"}))


def test_normalizar_conserva_las_claves_de_mas_de_una_lectura_y_une_listas():
    # El id que ponga la interfaz (incluido uno heredado con «-inv-») no se pierde, y el hash lo ignora.
    n = X.normalizar_contrato({"lecturas": [{"id": "lec-1-inv-2", "marca": True, "nombre": "GFAP", "tipo": "biomarcador", "que_confirma": "a", "que_refuta": "b"}]})
    assert n["lecturas"][0]["id"] == "lec-1-inv-2" and n["lecturas"][0]["marca"] is True and "que_confirma" not in n["lecturas"][0]
    assert n["lecturas"][0]["queConfirma"] == "a" and X.normalizar_contrato(n) == n
    assert set(X.lecturas_para_hash(n)[0]) == set(X._CLAVES_LECTURA)
    # Un protocolo en lista (como sale del modelo) se une con espacios, no se vuelca como repr.
    assert X._texto(["1. Medir", "2. Comparar"]) == "1. Medir 2. Comparar" and X._texto(None) == "" and X._texto(("a", None, 3)) == "a 3"
    ps = X.validar_contrato({"ensayo": "x", "confirma": "a", "refuta": "b", "protocolo": ["descargar ROSMAP", "ajustar"], "sistema": {"tipo": "datos_publicos_existentes", "quePrueba": "x", "queNoRepresenta": "y"}})
    assert any("(ROSMAP)" in p for p in ps)


def test_datos_controlados_con_oleada_negados_y_con_grafia_distinta():
    base = {"ensayo": "x", "confirma": "a", "refuta": "b"}
    contr = lambda texto: [p for p in X.validar_contrato(dict(base, analisisPedido=texto)) if "acceso controlado" in p]  # noqa: E731
    assert "(ADNI)" in contr("regresión en ADNI-3 y ADNI2 y ADNI-GO")[0]
    assert contr("Aβ42 y A42 en plasma; hoja A4") and "(A4)" in contr("hoja A4")[0]  # A4 solo como palabra entera
    assert not any("A42" in p for p in contr("A42 en plasma"))
    assert contr("uk biobank y UK Biobank") and "(UK Biobank)" in contr("uk biobank y UK Biobank")[0]  # una sola vez, con su nombre
    assert "(AMP-AD, NIAGADS)" in contr("AMP-AD y NIAGADS")[0]
    # Una mención negada no es un uso: el proponente repite la regla que se le dio.
    for negado in ("solo GEO, nunca ADNI", "GEO y SEA-AD, no ADNI", "sin acceso a ROSMAP", "en lugar de MSBB se usa GEO", "excluye NACC", "instead of ADNI use GEO", "OASIS, not ADNI"):
        assert contr(negado) == [], negado
    assert contr("GEO y también ADNI") and contr("no solo GEO sino también ADNI")  # la negación lejana no cuenta
    # La negación no cruza de un campo al siguiente.
    ps = X.validar_contrato(dict(base, analisisPedido="nunca", sistema={"tipo": "in_silico", "quePrueba": "ADNI", "queNoRepresenta": "y"}))
    assert any("(ADNI)" in p for p in ps)


def test_beneficio_clinico_no_salta_con_ensayo_funcional_ni_con_la_decision():
    c = copy.deepcopy(COMPLETO)
    c["nivelDesenlace"], c["puenteAlBeneficio"] = "celular", ""
    c["lecturas"][1]["queConfirma"] = "ensayo funcional de fagocitosis: aumenta al menos 30 %; deterioro de la membrana descartado"
    c["decisionQueCambia"] = "si confirma, se propone medir cognición en una cohorte"
    [p] = X.validar_contrato(c)
    assert p.startswith("el desenlace es celular y el experimento no declara el puente")
    c["lecturas"][1]["queConfirma"] = "aumenta al menos 30 % y mejora la memoria espacial"
    [p] = X.validar_contrato(c)
    assert "se presenta como beneficio clínico sin puente" in p and "«memoria espacial»" in p
    c["lecturas"][1]["queConfirma"] = "improves cognitive performance by 30 %"
    assert "«cognitive»" in X.validar_contrato(c)[0]


def test_una_cifra_que_nombra_a_varias_lecturas_es_ambigua_y_no_se_asigna():
    dos = [{"nombre": "GFAP en plasma", "tipo": "biomarcador", "queConfirma": "aumenta al menos 20 %", "queRefuta": "cambio menor del 5 %", "control": "x"}, {"nombre": "GFAP en LCR", "tipo": "biomarcador", "queConfirma": "aumenta al menos 20 %", "queRefuta": "cambio menor del 5 %", "control": "x"}]
    vs = X.veredicto_por_lecturas(dos, _cifras(GFAP="+30 %"))
    assert [v["veredicto"] for v in vs] == ["no_evaluable", "no_evaluable"] and all(v["cifras"] == [] for v in vs)
    assert "podría corresponder a esta lectura o a «GFAP en LCR»" in vs[0]["motivo"] and "no pude comprobar" in vs[0]["motivo"]
    # Tampoco por símbolo: «GFAP CSF» comparte GFAP con las dos.
    vs = X.veredicto_por_lecturas(dos, _cifras(**{"GFAP CSF": "+30 %"}))
    assert [v["veredicto"] for v in vs] == ["no_evaluable", "no_evaluable"] and "podría corresponder" in vs[1]["motivo"]
    # Con una coincidencia exacta y otra por contención, gana la exacta.
    vs = X.veredicto_por_lecturas(dos, _cifras(**{"GFAP en plasma": "+30 %"}))
    assert [v["veredicto"] for v in vs] == ["confirma", "no_evaluable"]
    # Una cifra de una letra («p», «n») no se cuela en «p-tau181» por contención, ni arrastra frases del juez.
    p = [{"nombre": "p-tau181 en plasma", "tipo": "biomarcador", "queConfirma": "baja al menos 25 %", "queRefuta": "cambio menor del 5 %", "control": "x"}]
    [v] = X.veredicto_por_lecturas(p, _cifras(p="0,03", **{"p-tau181 plasma": "-30 %"}))
    assert v["veredicto"] == "confirma" and v["cifras"] == ["p-tau181 plasma = -30 %"]
    assert X._frases_sobre("El valor p fue 0,03. GFAP no cambió.", ["p"]) == []
    # Una sola lectura sin cifra con veredicto global: no lo hereda, pero el motivo lo dice.
    [v] = X.veredicto_por_lecturas(ANTIGUO, {"veredicto": "refuta", "cifras": _cifras(media="12"), "motivo": "", "resultado": ""})
    assert v["veredicto"] == "no_evaluable" and "veredicto global (refuta)" in v["motivo"]


def test_el_juez_que_dice_no_cumple_no_confirma():
    assert X._veredicto_en_frase("La fagocitosis no cumple el criterio de confirmación.") == "inconcluso"
    assert X._veredicto_en_frase("Phagocytosis did not meet the confirmation criterion.") == "inconcluso"
    assert X._veredicto_en_frase("The result failed to confirm the prediction.") == "inconcluso"
    assert X._veredicto_en_frase("La fagocitosis cumple el criterio de refutación.") == "refuta"
    assert X._veredicto_en_frase("La fagocitosis cumple el criterio de confirmación.") == "confirma"
    orden = [{"nombre": "Orden GFAP/NfL", "tipo": "biomarcador", "queConfirma": "GFAP se altera antes que NfL", "queRefuta": "NfL antes o a la vez", "control": "x"}]
    [v] = X.veredicto_por_lecturas(orden, _cifras(**{"Orden GFAP/NfL": "GFAP 2,1 años antes"}), texto_juez="El orden GFAP/NfL no cumple el criterio de confirmación.")
    assert v["veredicto"] == "inconcluso"


def test_comparadores_por_palabra_entera_postfijos_y_varios_umbrales():
    # «over» dentro de «recovery» y «o más» dentro de «cambio más» no son comparadores.
    assert X._comparadores("recovery over 30 %") == [("gt", 30.0, True, 9)]
    assert [c[:3] for c in X._comparadores(X._sin_tildes("cambio más de 5 %").lower())] == [("gt", 5.0, True)]
    # El comparador va detrás del número.
    ok, motivo = X.evaluar_criterio("aumento de 20 % o más", "+5 %")
    assert ok is False and ">= 20%" in motivo
    assert X.evaluar_criterio("aumento de 20 % o más", "+25 %")[0] is True
    assert X.evaluar_criterio("20 pg/mL or more", "25 pg/mL")[0] is True and X.evaluar_criterio("aumento de 2,5 veces o más", "3 veces")[0] is True
    assert X.evaluar_criterio("viabilidad del 60 % o menos", "70 %")[0] is False
    # Relleno entre comparador y número, y comparadores que se solapan («=<» y «<», «no más del» y «más del», «igual o mayor que» y «mayor que»).
    assert X.evaluar_criterio("igual o mayor que 20 %", "20 %")[0] is True and X.evaluar_criterio("mayor que 20 %", "20 %")[0] is False
    assert X.evaluar_criterio("viabilidad =< 60 %", "60 %")[0] is True and X.evaluar_criterio("no más del 5 %", "5 %")[0] is True
    assert X.evaluar_criterio("al menos un 20 %", "20 %")[0] is True and X.evaluar_criterio("supera los 20 %", "20 %")[0] is False
    # Dos umbrales compatibles son un rango salvo que vayan con «o».
    ok, motivo = X.evaluar_criterio("aumento ≥ 20 % y < 50 %", "+60 %")
    assert ok is False and "pide los dos" in motivo
    assert X.evaluar_criterio("aumento ≥ 20 % y < 50 %", "+30 %")[0] is True
    ok, motivo = X.evaluar_criterio("aumento de al menos 20 % o de más de 30 % en APOE4", "+25 %")
    assert ok is True and "alternativos" in motivo
    # La nota de dirección no afirma lo que la cifra no dice.
    ok, motivo = X.evaluar_criterio("p < 0,05 y aumento ≥ 20 %", "0.03")
    assert ok is True and "en la dirección pedida" not in motivo and "no trae signo ni dirección" in motivo
    # Criterio de ausencia de cambio frente a una cifra que dice lo mismo.
    assert X.evaluar_criterio("sin cambio significativo frente al control", "n.s.")[0] is True
    assert X.evaluar_criterio("sin cambio significativo frente al control", "+18 % (no significativo)")[0] is None
    # Mayúsculas y tildes en el criterio y en la cifra dan igual.
    assert X.evaluar_criterio("AUMENTA AL MENOS 20 %", "REDUCCIÓN DEL 30 %")[0] is False


def test_lectura_del_negativo_solo_lee_negativos():
    # Sin compromiso de diana pero con el efecto presente: no es un negativo, no «sin lecturas separadas».
    r = X.lectura_del_negativo([_v("GFAP", "biomarcador", "confirma")])
    assert r["rama"] is None and "no es un negativo" in r["explicacion"]
    r = X.lectura_del_negativo([_v("GFAP", "biomarcador", "no_evaluable")])
    assert r["rama"] is None and "no pude comprobar" in r["explicacion"]
    r = X.lectura_del_negativo([_v("LDH", "viabilidad", "confirma"), _v("ARIA", "seguridad", "refuta")])
    assert r["rama"] is None and "no hay lectura de efecto ni de compromiso de diana" in r["explicacion"]
    # Negativo parcial sin lectura separada: la rama se da y el parcial se dice.
    r = X.lectura_del_negativo([_v("GFAP", "biomarcador", "refuta"), _v("NfL", "biomarcador", "inconcluso")])
    assert r["rama"] == "sin_lecturas_separadas" and "parcial" in r["explicacion"] and "NfL inconcluso" in r["explicacion"]
    # Veredictos y tipos con mayúsculas o etiqueta legible no rompen la lectura.
    r = X.lectura_del_negativo([_v("a", "Compromiso de diana", "Confirma"), _v("b", "función o mecanismo", "REFUTA")])
    assert r["rama"] == "diana_comprometida_sin_efecto"
    _sin_tildes_ni_guiones(" ".join(X.lectura_del_negativo(x)["explicacion"] for x in ([_v("GFAP", "biomarcador", "confirma")], [_v("GFAP", "biomarcador", "no_evaluable")], [_v("LDH", "viabilidad", "confirma")])))


def test_es_interpretable_y_bloque_con_solo_nivel_o_puente():
    assert X.es_interpretable(COMPLETO)[0] is True and X.es_interpretable(ANTIGUO)[0] is True
    assert X.es_interpretable({"ensayo": "GFAP en plasma"}) == (True, "solo hay un ensayo declarado, sin criterios por lectura (registro antiguo)")
    ok, motivo = X.es_interpretable({"lecturas": [{"nombre": "a", "tipo": "biomarcador", "queConfirma": "x"}]})
    assert ok is False and "refutación" in motivo
    assert X.es_interpretable({}) == (False, "no hay experimento propuesto") and X.es_interpretable(None)[0] is False
    # Un contrato con solo el nivel y el puente también se congela, sin hash de una lista vacía.
    L = X.bloque_prerregistro({"nivelDesenlace": "molecular", "puenteAlBeneficio": "haría falta lo mismo en LCR"})
    assert any("ninguna declarada" in l for l in L) and not any("Hash SHA-256" in l for l in L) and any("Nivel del desenlace: molecular." in l for l in L)
    _sin_tildes_ni_guiones("\n".join(L))


def test_muchas_lecturas_y_cifras_en_tiempo_razonable():
    import time

    lect = [{"nombre": f"Marcador M{i} en plasma por Simoa", "tipo": "biomarcador", "queConfirma": "aumenta al menos 20 %", "queRefuta": "cambio menor del 5 %", "control": "x"} for i in range(300)]
    cif = [{"nombre": f"Marcador M{i} plasma", "valor": f"+{i % 40} %"} for i in range(300)]
    t = time.perf_counter()
    vs = X.veredicto_por_lecturas(lect, cif)
    assert time.perf_counter() - t < 5 and len(vs) == 300 and vs[30]["veredicto"] == "confirma" and vs[3]["veredicto"] == "refuta"
    # Determinista: dos llamadas, el mismo resultado; y el hash no depende del orden.
    assert vs == X.veredicto_por_lecturas(lect, cif)
    assert X.hash_lecturas({"lecturas": lect}) == X.hash_lecturas({"lecturas": list(reversed(lect))})
