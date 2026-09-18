"""Método como nodo: cohortes, plataformas y muestras con identificador canónico."""

from pathlib import Path

from rosa import metodos as M


def _f(id_, cohorte=None, **resto):
    return {"id": id_, "cohorte": cohorte, **resto}


# -- Catálogo ----------------------------------------------------------------


def test_catalogo_plano_serializable_y_sin_ids_repetidos():
    ids = [e["id"] for e in M.CATALOGO]
    assert len(ids) == len(set(ids)) and len(M.CATALOGO) == len(M.COHORTES) + len(M.PLATAFORMAS) + len(M.MUESTRAS)
    for e in M.CATALOGO:
        assert set(e) >= {"id", "etiqueta", "alias", "tipo"} and e["id"].startswith(e["tipo"] + ":")
        assert e["tipo"] in ("cohorte", "plataforma", "muestra") and isinstance(e["alias"], list)
        assert e["etiqueta"] not in e["alias"]
    assert len(M.COHORTES) >= 34 and all("familia" in p for p in M.PLATAFORMAS)
    assert M.por_id("cohorte:adni")["etiqueta"] == "ADNI" and M.por_id("no:existe") is None and M.por_id("") is None


def test_cada_alias_del_catalogo_resuelve_a_su_propia_entrada():
    """Autoconsistencia: cada alias, escrito como está en el catálogo y metido
    en una frase, tiene que volver a su entrada y a ninguna otra."""
    for e in M.COHORTES:
        for nombre in [e["etiqueta"], *e["alias"]]:
            if nombre in ("Framingham", "HABS", "FINGER", "Betula", "RM", "imagen", "modelo animal o celular"):
                continue  # la etiqueta no se busca sola (etiqueta_busca False) o va con excepción probada aparte
            assert M.cohorte_en_texto(f"Plasma GFAP in the {nombre} participants") == e["etiqueta"], nombre
            assert M.canonizar_cohorte(nombre)["id"] == e["id"], nombre
    for e in M.PLATAFORMAS:
        for nombre in [e["etiqueta"], *e["alias"]]:
            if nombre == "RM":
                continue
            hallados = M.plataformas_en_texto(f"measured with {nombre} in 300 participants")
            assert hallados and hallados[0]["id"] == e["id"], nombre
    for e in M.MUESTRAS:
        for nombre in [e["etiqueta"], *e["alias"]]:
            if nombre in ("imagen", "modelo animal o celular"):
                continue
            hallados = M.muestras_en_texto(f"measured in {nombre} from 300 participants")
            assert hallados and hallados[0]["id"] == e["id"], nombre


# -- Cohortes: alias, nombres largos, NCT ----------------------------------------


def test_alias_y_nombres_largos():
    casos = {
        "Alzheimer's Disease Neuroimaging Initiative (ADNI)": "ADNI",
        "Alzheimer’s Disease Neuroimaging Initiative": "ADNI",
        "Alzheimer Disease Neuroimaging Initiative": "ADNI",
        "the Swedish BioFINDER-2 study": "BioFINDER",
        "BioFINDER2 participants": "BioFINDER",
        "ADNI-3 and ADNI-GO": "ADNI",
        "ADNI3 protocol": "ADNI",
        "Religious Orders Study and Rush Memory and Aging Project": "ROSMAP",
        "ROS/MAP donors": "ROSMAP",
        "Mayo Clinic Study of Aging": "MCSA",
        "the H70 birth cohort": "Gothenburg H70",
        "Dominantly Inherited Alzheimer Network (DIAN-TU)": "DIAN",
        "Wisconsin Registry for Alzheimer's Prevention": "WRAP",
        "UKB participants": "UK Biobank",
        "Australian Imaging, Biomarkers and Lifestyle": "AIBL",
        "Australian Imaging Biomarkers and Lifestyle": "AIBL",
        "Sydney Memory and Aging Study": "Sydney MAS",  # sin tildes
        "Sydney Memory and Ageing Study": "Sydney MAS",  # sin tildes
        "liquido cefalorraquideo y plasma en la cohorte ALFA": "ALFA",  # sin tildes
        "PSEN1 E280A kindred from Antioquia": "API Colombia",
        "Insight46 participants": "Insight 46",
        "Mount Sinai Brain Bank": "MSBB",
        "Knight Alzheimer Disease Research Center": "Knight ADRC",
        "the Whitehall II study": "Whitehall II",
        "Health and Aging Brain Study-Health Disparities": "HABS-HD",
        "Harvard Aging Brain Study": "HABS",
        "J-ADNI and ADNI": "J-ADNI",
        "Accelerating Medicines Partnership Alzheimer's Disease": "AMP-AD",
        "Cohorte ALFA+ de Barcelona": "ALFA",
    }
    for texto, esperado in casos.items():
        assert M.cohorte_en_texto(texto) == esperado, texto


def test_nct_manda_y_los_conocidos_resuelven_a_su_cohorte():
    c = M.canonizar_cohorte("NCT01234567")
    assert c["id"] == "ensayo:NCT01234567" and c["etiqueta"] == "NCT01234567" and c["tipo"] == "ensayo"
    assert M.cohorte_en_texto("Trial NCT09999999 results") == "NCT09999999"
    assert M.cohorte_en_texto("ADNI data (nct09999999)") == "NCT09999999"  # el NCT manda sobre el nombre
    assert M.canonizar_cohorte("NCT02008357")["id"] == "cohorte:a4"
    assert M.cohorte_en_texto("the A4 study (NCT02008357)") == "A4"
    assert M.misma_cohorte("A4", "NCT02008357") is True
    assert M.misma_cohorte("NCT01234567", "NCT01234567") is True and M.misma_cohorte("NCT01234567", "NCT01234568") is False
    ids = [x["id"] for x in M.cohortes_en_texto("ADNI and NCT09999999 and BioFINDER")]
    assert ids == ["cohorte:adni", "ensayo:NCT09999999", "cohorte:biofinder"]


def test_sin_falsos_positivos():
    for texto in [
        "in May 2020 the trial began",
        "the mass of the sample",
        "adnexal mass",
        "reactive oxygen species (ROS) map the damage",
        "University of Gothenburg, Sahlgrenska Academy",
        "Erasmus MC, University Medical Center Rotterdam",
        "as shown in Fig. 3C and 3D",
        "wrap the finger tightly",
        "the triad of symptoms",
        "la alfa-sinucleína en plasma",
        "the Framingham risk score",
        "the Framingham Stroke Risk Profile",
        "apparent diffusion coefficient (ADC)",
        "Alzheimer's Disease Centers (ADCs) of the NACC",  # el NACC sí, pero por su nombre
        "interventions to prevent dementia",
        "an oasis of calm",
        "A40 and A42 levels",
        "the H700 series",
        "ADNIx is not a cohort",
        "the API returned JSON",
        "this may map onto the triad",
        "nothing here",
        "",
    ]:
        c = M.cohorte_en_texto(texto)
        assert c in ("", "NACC"), (texto, c)
    assert M.cohorte_en_texto("Alzheimer's Disease Centers (ADCs) of the NACC") == "NACC"
    assert M.cohorte_en_texto(None) == "" and M.cohortes_en_texto(None) == []
    # "HABS-HD" no es "HABS"; "FINGER-prick" no es el ensayo FINGER.
    assert M.cohorte_en_texto("HABS-HD participants") == "HABS-HD"
    assert M.cohorte_en_texto("HABS participants") == "HABS"
    assert M.cohorte_en_texto("FINGER-PRICK BLOOD SAMPLING") == ""
    assert M.cohorte_en_texto("the FINGER trial") == "FINGER"
    # Sin plataforma: TMT es el Trail Making Test, "Elisa" un nombre, "pet" un animal.
    assert M.plataformas_en_texto("Trail Making Test (TMT) and Elisa's pet") == []
    assert M.muestras_en_texto("her pet dog") == []
    for ambiguo in ("Mayo", "Gothenburg", "Rotterdam", "ROS", "MAP", "ADC", "MAS", "3C", "API", "PREVENT"):
        assert ambiguo in M.AMBIGUOS and M.cohorte_en_texto(f"in the {ambiguo} cohort") == "", ambiguo


def test_siglas_respetan_mayusculas_en_texto_libre_pero_no_en_un_campo():
    assert M.cohorte_en_texto("wrap") == "" and M.cohorte_en_texto("WRAP") == "WRAP"
    assert M.cohorte_en_texto("swedish biofinder") == "BioFINDER"  # nombre mixto: sin distinguir mayúsculas
    assert M.canonizar_cohorte("adni")["id"] == "cohorte:adni"
    assert M.canonizar_cohorte("alfa")["id"] == "cohorte:alfa"
    assert M.canonizar_cohorte("  biofinder-2 cohort ")["id"] == "cohorte:biofinder"
    assert M.canonizar_cohorte("(ADNI)")["id"] == "cohorte:adni"
    assert M.canonizar_cohorte("ADAD (Belder et al.)") is None
    assert M.canonizar_cohorte("") is None and M.canonizar_cohorte(None) is None and M.canonizar_cohorte("   ") is None
    for c in (M.canonizar_cohorte("adni"), M.canonizar_cohorte("biofinder-2 cohort")):
        assert set(c) == {"id", "etiqueta", "tipo", "texto", "motivo"} and c["motivo"]


# -- Misma cohorte -----------------------------------------------------------------


def test_misma_cohorte_por_id_canonico_y_por_tokens():
    assert M.misma_cohorte("ADNI", "adni") is True
    assert M.misma_cohorte("ADNI", "Alzheimer's Disease Neuroimaging Initiative") is True
    assert M.misma_cohorte("DIAN", "DIAN-TU") is True
    assert M.misma_cohorte("ADNI", "BioFINDER") is False
    assert M.misma_cohorte("", "ADNI") is None and M.misma_cohorte(None, None) is None and M.misma_cohorte("ADNI", "   ") is None
    # Regla de tokens de certeza.py para nombres fuera del catálogo.
    assert M.misma_cohorte("ADAD (Belder et al.)", "ADAD") is True
    assert M.misma_cohorte("Belder et al., cohorte ADAD", "ADAD") is True
    assert M.misma_cohorte("COHORTE-UNICA", "COHORTE-UNICA") is True
    assert M.misma_cohorte("cohorte de Madrid", "cohorte de Barcelona") is False  # solo comparten genéricas
    assert M.misma_cohorte("ADNI", "Belder et al.") is False
    # Acepta fuentes (diccionarios) y usa el nct si falta la cohorte.
    assert M.misma_cohorte(_f("f1", "ADNI"), _f("f2", "adni")) is True
    assert M.misma_cohorte(_f("f1", "A4"), _f("f2", None, nct="NCT02008357")) is True
    assert M.misma_cohorte({"id": "viejo"}, _f("f2", "ADNI")) is None
    for a, b in (("ADNI", "adni"), ("ADNI", "BioFINDER"), ("", "x"), ("ADAD (Belder et al.)", "ADAD"), ("ADNI", "Belder et al.")):
        veredicto, motivo = M.misma_cohorte_motivo(a, b)
        assert veredicto is M.misma_cohorte(a, b) and isinstance(motivo, str) and motivo


def test_grupos_y_cohortes_distintas():
    fs = [
        _f("f1", "ADNI"), _f("f2", "adni"), _f("f3", "Alzheimer's Disease Neuroimaging Initiative"),
        _f("f4", "BioFINDER"), _f("f5", ""), _f("f6", "ADAD (Belder et al.)"), _f("f7", "ADAD"),
        {"id": "f8"},  # registro antiguo sin la clave
        {"cohorte": "ADNI"},  # sin id
        _f("f1", "ADNI"),  # id repetido
    ]
    assert M.grupos_de_cohorte(fs) == [["f1", "f2", "f3", "fuente-9"], ["f4"], ["f6", "f7"]]
    assert M.cohortes_distintas(fs) == ["ADNI", "BioFINDER", "ADAD (Belder et al.)"]
    assert M.fuentes_sin_cohorte(fs) == 2
    # Acepta la hipótesis entera, como hacen certeza.cohortes_distintas y priorizacion.cohortes_de.
    assert M.cohortes_distintas({"procedencia": {"fuentes": fs}}) == ["ADNI", "BioFINDER", "ADAD (Belder et al.)"]
    assert M.cohortes_distintas({"procedencia": {}}) == [] and M.cohortes_distintas(None) == [] and M.grupos_de_cohorte([]) == []
    grupos = M.agrupar_cohortes(fs)
    assert grupos[0]["id"] == "cohorte:adni" and grupos[2]["id"] is None and grupos[2]["nombres"] == ["ADAD (Belder et al.)", "ADAD"]
    assert all(g["motivos"] for g in grupos if len(g["ids"]) > 1)
    # El caso del test de killer: "ADNI" y "adni" son una sola evidencia.
    assert len(M.cohortes_distintas([_f("f1", "ADNI"), _f("f2", "adni")])) == 1


# -- Plataformas y muestras ----------------------------------------------------------


def test_plataforma_y_muestra():
    t = "Plasma p-tau217 measured on the Simoa HD-X (Quanterix) and Lumipulse G platforms; CSF Aβ42/40 by Elecsys"
    assert [x["id"] for x in M.plataformas_en_texto(t)] == ["plataforma:simoa", "plataforma:lumipulse", "plataforma:elecsys"]
    assert M.plataforma_en_texto(t)["id"] == "plataforma:simoa" and M.plataforma_en_texto("sin nada") is None and M.plataforma_en_texto(None) is None
    assert [x["id"] for x in M.muestras_en_texto(t)] == ["muestra:plasma", "muestra:lcr"]
    assert [x["id"] for x in M.plataformas_en_texto("Pittsburgh compound-B PET and [18F]flortaucipir; immunoprecipitation-mass spectrometry (PrecivityAD)")] == ["plataforma:pet_amiloide", "plataforma:pet_tau", "plataforma:espectrometria"]
    assert [x["id"] for x in M.plataformas_en_texto("Olink Explore proteomics and SomaScan aptamers; snRNA-seq of frontal cortex")] == ["plataforma:olink", "plataforma:somascan", "plataforma:rnaseq"]
    assert [x["id"] for x in M.muestras_en_texto("post-mortem brain tissue; plasma y líquido cefalorraquídeo por espectrometría de masas en ratones 5xFAD")] == ["muestra:tejido", "muestra:plasma", "muestra:lcr", "muestra:modelo"]
    assert [x["id"] for x in M.plataformas_en_texto("por espectrometría de masas y resonancia magnética")] == ["plataforma:espectrometria", "plataforma:rm"]
    # Sin tildes, como sale de algunos PDF, resuelve igual.
    assert [x["id"] for x in M.plataformas_en_texto("por espectrometria de masas y resonancia magnetica")] == ["plataforma:espectrometria", "plataforma:rm"]  # sin tildes
    assert [x["id"] for x in M.muestras_en_texto("liquido cefalorraquideo de ratones transgenicos")] == ["muestra:lcr", "muestra:modelo"]  # sin tildes
    assert M.muestras_en_texto("suero, saliva y orina; imagen por PET") and [x["id"] for x in M.muestras_en_texto("suero, saliva y orina; neuroimagen por PET")] == ["muestra:suero", "muestra:saliva", "muestra:orina", "muestra:imagen"]
    assert M.muestras_en_texto("") == [] and M.plataformas_en_texto(None) == []
    for h in M.plataformas_en_texto(t):
        assert set(h) == {"id", "etiqueta", "tipo", "texto", "posicion", "motivo"} and h["tipo"] == "plataforma"


def test_metodo_de_fuente_y_su_origen():
    m = M.metodo_de_fuente(_f("f1", "ADNI", titulo="Plasma GFAP in BioFINDER", fragmento="Simoa HD-X"))
    assert m["cohorte"]["id"] == "cohorte:adni" and m["origen"] == "campo"  # el campo manda sobre el título
    assert m["plataforma"]["id"] == "plataforma:simoa" and m["muestra"]["id"] == "muestra:plasma"
    m = M.metodo_de_fuente({"id": "f1", "titulo": "Plasma p-tau217 in ADNI measured with Simoa", "fragmento": "Simoa HD-X in plasma."})
    assert m["cohorte"]["etiqueta"] == "ADNI" and m["origen"] == "titulo" and set(m) == {"cohorte", "plataforma", "plataformas", "muestra", "muestras", "origen"}
    assert M.metodo_de_fuente({"id": "f1", "fragmento": "participants from the Knight ADRC"})["origen"] == "fragmento"
    assert M.metodo_de_fuente({"id": "f1", "fragmentos": [{"texto": "participants from the Knight ADRC"}]})["origen"] == "fragmento"
    m = M.metodo_de_fuente({"id": "f1"}, [{"texto": "GFAP rose in the AIBL cohort", "cita": "[x]"}])
    assert m["cohorte"]["id"] == "cohorte:aibl" and m["origen"] == "afirmaciones"
    m = M.metodo_de_fuente({"id": "f1"}, [{"texto": "GFAP rose", "cohorte": "wrap"}])
    assert m["cohorte"]["id"] == "cohorte:wrap" and m["origen"] == "afirmaciones"
    m = M.metodo_de_fuente({"id": "f1", "nct": "NCT02008357"})
    assert m["cohorte"]["id"] == "cohorte:a4" and m["origen"] == "campo"
    # Un nombre libre en el campo se conserva con id None, salvo que el título dé uno canónico.
    m = M.metodo_de_fuente(_f("f1", "Belder et al."))
    assert m["cohorte"] == {"id": None, "etiqueta": "Belder et al.", "tipo": "cohorte", "texto": "Belder et al.", "motivo": "nombre libre: no resuelve a una cohorte del catálogo"} and m["origen"] == "campo"
    m = M.metodo_de_fuente(_f("f1", "Belder et al.", titulo="Tau in the DIAN cohort"))
    assert m["cohorte"]["id"] == "cohorte:dian" and m["origen"] == "titulo"
    # Registros antiguos sin claves, None, claves con None.
    for viejo in ({}, None, {"id": "x"}, {"id": "x", "cohorte": None, "titulo": None, "fragmento": None, "fragmentos": None, "nct": None}):
        assert M.metodo_de_fuente(viejo) == {"cohorte": None, "plataforma": None, "plataformas": [], "muestra": None, "muestras": [], "origen": None}
    assert M.metodo_de_fuente({"id": "x"}, None)["origen"] is None and M.metodo_de_fuente({"id": "x"}, [None, "texto suelto"])["origen"] is None


# -- Resumen y texto -----------------------------------------------------------------

F1 = {"id": "f1", "titulo": "Plasma p-tau217 in ADNI measured with Simoa", "fragmento": "We measured plasma p-tau217 with the Simoa HD-X."}
F2 = {"id": "f2", "cohorte": "BioFINDER", "titulo": "Plasma p-tau217 in Swedish BioFINDER", "fragmento": "Simoa assays in plasma; CSF Aβ42 by Elecsys"}


def test_resumen_metodos():
    r = M.resumen_metodos([F1, F2])
    assert [c["etiqueta"] for c in r["cohortes"]] == ["ADNI", "BioFINDER"] and r["cohortes"][0]["fuentes"] == ["f1"]
    assert {p["id"]: p["fuentes"] for p in r["plataformas"]} == {"plataforma:simoa": ["f1", "f2"], "plataforma:elecsys": ["f2"]}
    assert r["compartenPlataforma"] is True and r["compartenMuestra"] is True and r["muestraComun"]["id"] == "muestra:plasma"
    assert r["fuentesSinCohorte"] == 0 and r["fuentesSinPlataforma"] == 0 and r["totalFuentes"] == 2
    r2 = M.resumen_metodos([F1, dict(F2, titulo="CSF p-tau217 in Swedish BioFINDER", fragmento="Lumipulse assays in CSF")])
    assert r2["compartenPlataforma"] is False and r2["compartenMuestra"] is False and r2["muestraComun"] is None
    # La muestra principal la fija el título: una mención de fondo al LCR no quita que la matriz medida sea plasma.
    r2b = M.resumen_metodos([F1, dict(F2, fragmento="Lumipulse assays; compared with CSF")])
    assert r2b["compartenMuestra"] is True and r2b["muestraComun"]["id"] == "muestra:plasma"
    # Una sola fuente con plataforma no "comparte" nada; una sin nada cuenta como no identificada.
    r3 = M.resumen_metodos([F1, {"id": "f3", "cohorte": "AIBL"}])
    assert r3["compartenPlataforma"] is False and r3["fuentesSinPlataforma"] == 1 and r3["fuentesSinMuestra"] == 1
    # Afirmaciones por fuente: como diccionario o como lista plana con fuenteId.
    afs = {"f3": [{"texto": "measured by Lumipulse in plasma", "fuenteId": "f3"}]}
    assert M.resumen_metodos([F1, {"id": "f3", "cohorte": "AIBL"}], afs)["fuentesSinPlataforma"] == 0
    assert M.resumen_metodos([F1, {"id": "f3", "cohorte": "AIBL"}], afs["f3"])["fuentesSinPlataforma"] == 0
    # La hipótesis entera también vale; vacío y registros antiguos no rompen.
    assert M.resumen_metodos({"procedencia": {"fuentes": [F1, F2]}})["totalFuentes"] == 2
    assert M.resumen_metodos([])["totalFuentes"] == 0 and M.resumen_metodos(None)["cohortes"] == []
    assert M.resumen_metodos([{"id": "a"}, {"id": "b", "titulo": None}])["fuentesSinCohorte"] == 2


def test_texto_metodos_en_castellano():
    t = M.texto_metodos([F1, F2])
    assert t.startswith("Cohortes: ADNI y BioFINDER (2 distintas).")
    assert "Plataforma: Simoa en todas las fuentes" in t and "no es independiente del instrumento" in t
    assert "la principal es plasma" in t
    t2 = M.texto_metodos([F1, dict(F2, fragmento="Lumipulse assays in plasma")])
    assert "Plataformas: Simoa (1 fuente) y Lumipulse (1 fuente) (2 distintas)" in t2 and t2.endswith("Muestra: plasma.")
    assert M.texto_metodos([]) == "Sin fuentes: no hay métodos que resumir."
    t3 = M.texto_metodos([{"id": "a"}, {"id": "b"}])
    assert "ninguna de las 2 fuentes la nombra" in t3 and "Plataforma: no identificada" in t3 and "Muestra: no identificada." in t3
    t4 = M.texto_metodos([F1])
    assert t4.startswith("Cohorte: ADNI (una sola fuente).") and "una sola fuente la indica" in t4
    t5 = M.texto_metodos([_f("a", "ADNI"), _f("b", "adni"), {"id": "c"}])
    assert "Cohorte: ADNI en todas las fuentes que la nombran (2 de 3)" in t5 and "una sola evidencia" in t5
    t6 = M.texto_metodos([_f("a", "ADNI", titulo="Plasma GFAP"), _f("b", "BioFINDER", titulo="CSF GFAP"), {"id": "c", "titulo": "Imaging of amyloid PET"}])
    assert "1 fuente sin cohorte identificada" in t6 and "Muestras mencionadas: plasma, LCR e imagen." in t6
    assert "cabeza a cabeza" in M.texto_metodos([_f("a", "ADNI", titulo="Simoa vs Lumipulse head-to-head")])
    for texto in (t, t2, t3, t4, t5, t6):
        assert "\u2014" not in texto and "asi que" not in texto and "unica" not in texto  # sin tildes


def test_enumerar_en_castellano():
    assert M._enumerar([]) == "" and M._enumerar(["A"]) == "A" and M._enumerar(["A", "B"]) == "A y B"
    assert M._enumerar(["plasma", "LCR", "imagen"]) == "plasma, LCR e imagen" and M._enumerar(["a", "hielo"]) == "a y hielo"


# -- Compatibilidad con killer.cohorte_en_texto ----------------------------------------


def test_coincide_con_killer_en_los_treinta_nombres():
    """Para cada nombre de killer.COHORTES_CONOCIDAS, o damos el mismo nombre,
    o damos la etiqueta canónica de la entrada que tiene ese nombre como alias
    (H70 es Gothenburg H70, Whitehall es Whitehall II, Sydney Memory es
    Sydney MAS), o el nombre está en AMBIGUOS y no se reconoce a solas, con su
    motivo (Mayo, Gothenburg, Rotterdam)."""
    from rosa import killer as K

    # killer.cohorte_en_texto delega en este catálogo: paridad exacta en todas las etiquetas,
    # y los nombres ambiguos a solas (mes, afiliación) no cuentan en ninguno de los dos.
    assert K.COHORTES_CONOCIDAS == [c["etiqueta"] for c in M.COHORTES]
    for nombre in K.COHORTES_CONOCIDAS:
        texto = f"Plasma GFAP in the {nombre} cohort"
        assert K.cohorte_en_texto(texto) == M.cohorte_en_texto(texto) == nombre, nombre
    for ambiguo in ("Mayo", "Gothenburg", "Rotterdam"):
        assert K.cohorte_en_texto(f"Plasma GFAP in the {ambiguo} cohort") == "" and M.AMBIGUOS[ambiguo]
    # Los casos del test de killer siguen dando lo mismo.
    assert M.cohorte_en_texto("Plasma GFAP in the BioFINDER-2 cohort") == "BioFINDER" == K.cohorte_en_texto("Plasma GFAP in the BioFINDER-2 cohort")
    assert M.cohorte_en_texto("Trial NCT09999999 results") == "NCT09999999" and M.cohorte_en_texto("nothing here") == ""


def test_el_modulo_no_lleva_guiones_largos():
    assert "\u2014" not in Path(M.__file__).read_text(encoding="utf-8")


# -- Adversariales (16 de septiembre de 2026) ---------------------------------------------


def test_contexto_anula_un_nombre_tabla_negacion_y_homonimos():
    """Las reglas de contexto documentadas en la cabecera tienen que aplicarse
    de verdad: `no_tras` (una tabla), la negación con "non-", `excepto` (lo que
    sigue) y `salvo_si` (cualquier parte del texto)."""
    assert M.cohorte_en_texto("as shown in Table A4 and Fig. A4") == ""
    assert M.cohorte_en_texto("see eTable A4 and Panel A4") == ""
    assert M.cohorte_en_texto("printed on A4 paper") == ""
    assert M.cohorte_en_texto("the A4 study participants") == "A4"
    assert M.cohorte_en_texto("non-ADNI cohorts were excluded") == ""
    assert M.cohorte_en_texto("non ADNI cohorts") == ""
    assert M.cohorte_en_texto("non-ADNI and ADNI participants") == "ADNI"
    assert M.plataformas_en_texto("PEA (palmitoylethanolamide) levels were measured") == []
    assert [x["id"] for x in M.plataformas_en_texto("proteomics by PEA (Olink)")] == ["plataforma:olink"]
    assert M.plataformas_en_texto("funded by MSD (Merck Sharp & Dohme)") == []
    assert [x["id"] for x in M.plataformas_en_texto("measured by MSD S-PLEX")] == ["plataforma:msd"]
    assert M.plataformas_en_texto("el PIB del país") == []
    assert [x["id"] for x in M.plataformas_en_texto("[11C]PiB PET")] == ["plataforma:pet_amiloide"]
    assert M.muestras_en_texto("blood-brain barrier dysfunction and blood pressure and cerebral blood flow") == []
    assert [x["id"] for x in M.muestras_en_texto("blood-based biomarkers")] == ["muestra:sangre"]


def test_el_nombre_de_una_cohorte_no_mancha_la_muestra_ni_la_plataforma():
    assert [x["id"] for x in M.muestras_en_texto("Alzheimer's Disease Neuroimaging Initiative plasma")] == ["muestra:plasma"]
    assert [x["id"] for x in M.muestras_en_texto("Australian Imaging, Biomarkers and Lifestyle CSF study")] == ["muestra:lcr"]
    assert [x["id"] for x in M.muestras_en_texto("Open Access Series of Imaging Studies")] == []
    assert [x["id"] for x in M.muestras_en_texto("ADNI neuroimaging")] == ["muestra:imagen"]
    m = M.metodo_de_fuente({"id": "f", "titulo": "Alzheimer's Disease Neuroimaging Initiative: plasma p-tau217 by Simoa"})
    assert m["cohorte"]["id"] == "cohorte:adni" and m["muestra"]["id"] == "muestra:plasma" and m["plataforma"]["id"] == "plataforma:simoa"


def test_campo_cohorte_como_nodo_lista_identificador_o_basura():
    """El campo `cohorte` puede venir ya como nodo ({"id", "etiqueta"}), como
    identificador del catálogo, como lista, o con basura (un número, un
    booleano): nada rompe y dos nodos libres distintos no son "la misma"
    por compartir las palabras 'id' o 'etiqueta' de su representación."""
    nodo = {"id": "cohorte:adni", "etiqueta": "ADNI"}
    assert M.misma_cohorte({"cohorte": nodo}, {"cohorte": "adni"}) is True
    assert M.misma_cohorte(nodo, "ADNI-3") is True
    assert M.misma_cohorte({"cohorte": {"id": None, "etiqueta": "Madrid"}}, {"cohorte": {"id": None, "etiqueta": "Barcelona"}}) is False
    assert M.misma_cohorte({"cohorte": {"id": None, "etiqueta": "ADAD (Belder et al.)"}}, {"cohorte": "ADAD"}) is True
    m = M.metodo_de_fuente({"id": "f", "cohorte": nodo})
    assert m["cohorte"]["id"] == "cohorte:adni" and m["cohorte"]["texto"] == "ADNI" and m["origen"] == "campo"
    assert M.canonizar_cohorte("cohorte:biofinder")["etiqueta"] == "BioFINDER"
    assert M.canonizar_cohorte(["ADNI"])["id"] == "cohorte:adni" and M.canonizar_cohorte(b"adni")["id"] == "cohorte:adni"
    assert M.canonizar_cohorte(42) is None and M.canonizar_cohorte(True) is None and M.canonizar_cohorte({"id": "x"}) is None
    assert M.metodo_de_fuente({"id": "f", "cohorte": 42})["cohorte"] is None
    assert M.metodo_de_fuente({"id": "f", "cohorte": True})["cohorte"] is None
    assert M.misma_cohorte({"cohorte": 42}, {"cohorte": 42}) is None
    assert M.resumen_metodos([{"id": "a", "cohorte": nodo}, {"id": "b", "cohorte": "ADNI"}])["cohortes"] == [{"id": "cohorte:adni", "etiqueta": "ADNI", "fuentes": ["a", "b"]}]
    assert M.metodo_de_fuente({"id": "f"}, [{"texto": "x", "cohorte": {"id": "cohorte:wrap", "etiqueta": "WRAP"}}])["cohorte"]["id"] == "cohorte:wrap"


def test_entradas_que_no_son_listas_ni_diccionarios_no_rompen():
    for raro in (5, 3.5, "ADNI", b"ADNI", True, object()):
        assert M.metodo_de_fuente({"id": "x"}, raro)["origen"] is None
        assert M.grupos_de_cohorte(raro) == [] and M.cohortes_distintas(raro) == [] and M.fuentes_sin_cohorte(raro) == 0
        assert M.resumen_metodos([{"id": "f1"}], raro)["totalFuentes"] == 1
        assert M.texto_metodos(raro) == "Sin fuentes: no hay métodos que resumir."
    # Un número, un booleano o un objeto cualquiera no son un nombre de cohorte: "no se puede comprobar".
    for raro in (5, 3.5, True, object()):
        assert M.misma_cohorte(raro, "ADNI") is None and M.misma_cohorte({"cohorte": raro}, "ADNI") is None
    assert M.misma_cohorte(b"ADNI", "ADNI") is True
    # Un diccionario suelto donde se esperaba una lista se toma como un elemento.
    assert M.metodo_de_fuente({"id": "x"}, {"texto": "in the AIBL cohort"})["origen"] == "afirmaciones"
    assert M.metodo_de_fuente({"id": "x", "fragmentos": {"texto": "Knight ADRC"}})["origen"] == "fragmento"
    assert M.resumen_metodos([{"id": "f1"}], {"f1": {"texto": "Simoa"}})["fuentesSinPlataforma"] == 0
    assert M.resumen_metodos([{"id": "f1"}], {"f1": 7})["fuentesSinPlataforma"] == 1


def test_regla_mixta_entre_un_nombre_libre_y_el_catalogo():
    """El killer antiguo escribía 'Rotterdam' y 'Gothenburg'; el extractor
    escribe 'Rotterdam cohort'. Esos nombres son la misma cohorte que su
    entrada del catálogo si contienen su nombre palabra a palabra; lo que
    solo comparte una palabra genérica o una parte del nombre, no."""
    assert M.misma_cohorte("Rotterdam", "Rotterdam Study") is True
    assert M.misma_cohorte("Rotterdam cohort", "ERGO") is True
    assert M.misma_cohorte("Rush cohort", "ROSMAP") is True
    assert M.misma_cohorte("Gothenburg", "H70") is True
    veredicto, motivo = M.misma_cohorte_motivo("Rotterdam", "Rotterdam Study")
    assert veredicto is True and "Rotterdam Study" in motivo and "palabra a palabra" in motivo
    for libre, canonica in (("PSEN1 carriers", "API Colombia"), ("Mayo", "MCSA"), ("Mayo Clinic ADRC", "MCSA"), ("European cohort", "EPAD"), ("neuroimaging cohort", "ADNI"), ("Belder et al.", "DIAN"), ("ADAD", "API ADAD"), ("Memory clinic cohort", "ROSMAP"), ("Wisconsin cohort", "WRAP"), ("Wisconsin cohort", "Wisconsin ADRC"), ("Japanese cohort", "J-ADNI"), ("families at risk", "ALFA"), ("biomarkers for controls", "BIOCARD"), ("translational cohort", "TRIAD")):
        assert M.misma_cohorte(libre, canonica) is False, (libre, canonica)
    # Ningún nombre del catálogo se reduce a una palabra genérica ni a una compartida con otra entrada.
    for id_c, conjuntos in M._TOKENS_ENTRADA.items():
        for toks in conjuntos:
            assert toks and not (toks & M._GENERICOS_MIXTA) and not (toks & M._REPETIDOS), (id_c, toks)
    # En los grupos: 'Rotterdam' entra en el grupo de Rotterdam Study y un nombre libre nunca funde dos cohortes del catálogo.
    fs = [_f("a", "Rotterdam Study"), _f("b", "Gothenburg H70"), _f("c", "Rotterdam"), _f("d", "Rotterdam foo"), _f("e", "Gothenburg bar"), _f("f", "foo bar")]
    assert M.grupos_de_cohorte(fs) == [["a", "c", "d", "f"], ["b", "e"]]
    assert M.cohortes_distintas(fs) == ["Rotterdam Study", "Gothenburg H70"]
    grupos = M.agrupar_cohortes(fs)
    assert grupos[0]["id"] == "cohorte:rotterdam" and grupos[1]["id"] == "cohorte:h70" and all(g["motivos"] for g in grupos)
    # Cada nombre entró en su grupo por una cadena de veredictos "misma" (cierre transitivo, no todos los pares).
    assert grupos[0]["nombres"] == ["Rotterdam Study", "Rotterdam", "Rotterdam foo", "foo bar"]
    for g in grupos:
        for anterior, n in zip(g["nombres"], g["nombres"][1:]):
            assert M.misma_cohorte(anterior, n) is True, (anterior, n)
    assert M.misma_cohorte("Rotterdam Study", "foo bar") is False  # el par lejano no lo es por sí solo
    # Dos fuentes con el mismo nombre libre y distinto id llevan motivo.
    g = M.agrupar_cohortes([_f("a", "COHORTE-UNICA"), _f("b", "COHORTE-UNICA")])
    assert g[0]["ids"] == ["a", "b"] and g[0]["motivos"] == ["el mismo nombre ('COHORTE-UNICA')"]  # sin tildes


def test_grupos_con_nct_en_el_campo_o_en_nct():
    fs = [_f("a", "NCT01234567"), {"id": "b", "nct": "nct01234567"}, _f("c", "NCT02008357"), _f("d", "A4"), {"id": "e", "nct": None, "cohorte": None}]
    assert M.grupos_de_cohorte(fs) == [["a", "b"], ["c", "d"]]
    assert M.cohortes_distintas(fs) == ["NCT01234567", "A4"] and M.fuentes_sin_cohorte(fs) == 1
    assert M.agrupar_cohortes(fs)[0]["id"] == "ensayo:NCT01234567"


def test_la_cache_devuelve_copias_y_acelera():
    h = M.cohortes_en_texto("ADNI cohort")
    h[0]["etiqueta"] = "X"
    h[0]["extra"] = 1
    assert M.cohortes_en_texto("ADNI cohort")[0] == {"id": "cohorte:adni", "etiqueta": "ADNI", "tipo": "cohorte", "texto": "ADNI", "posicion": 0, "motivo": "el texto nombra 'ADNI'"}
    antes = M._tramos.cache_info().hits
    M.plataformas_en_texto("Simoa HD-X plasma " * 50)
    M.plataformas_en_texto("Simoa HD-X plasma " * 50)
    assert M._tramos.cache_info().hits > antes and M._tramos.cache_info().maxsize == 2048
    # El catálogo no se puede corromper desde fuera a través de lo que devuelven las funciones.
    c = M.canonizar_cohorte("ADNI")
    c["etiqueta"] = "roto"
    assert M.por_id("cohorte:adni")["etiqueta"] == "ADNI" and M.canonizar_cohorte("ADNI")["etiqueta"] == "ADNI"


def test_castellano_con_y_sin_tildes():
    assert M.cohorte_en_texto("en el Estudio de Rotterdam") == "Rotterdam Study"
    assert M.cohorte_en_texto("la cohorte ALFA de Barcelona") == "ALFA"
    assert [x["id"] for x in M.muestras_en_texto("estudio de necropsia y de tejido cerebral")] == ["muestra:tejido"]
    assert [x["id"] for x in M.plataformas_en_texto("secuenciación de ARN de núcleo único")] == ["plataforma:rnaseq"]
    assert [x["id"] for x in M.plataformas_en_texto("secuenciacion de ARN")] == ["plataforma:rnaseq"]  # sin tildes
    assert [x["id"] for x in M.muestras_en_texto("muestras de sangre, orina y saliva; punción lumbar")] == ["muestra:sangre", "muestra:orina", "muestra:saliva", "muestra:lcr"]
    assert [x["id"] for x in M.muestras_en_texto("puncion lumbar")] == ["muestra:lcr"]  # sin tildes


def test_coste_lineal_en_fuentes_y_en_nombres_libres():
    import time

    fs = [{"id": f"f{i}", "titulo": f"Plasma p-tau217 in ADNI measured with Simoa ({i})", "fragmento": "We measured plasma p-tau217 with the Simoa HD-X in participants of the Swedish BioFINDER-2 study; CSF was collected by lumbar puncture. " * 4 + str(i)} for i in range(300)]
    t = time.time()
    r = M.resumen_metodos(fs)
    assert time.time() - t < 15 and r["totalFuentes"] == 300 and r["compartenPlataforma"] is True
    libres = [{"id": f"f{i}", "cohorte": f"nombre{i} et al."} for i in range(1500)]  # sin ninguna palabra en común
    t = time.time()
    assert len(M.grupos_de_cohorte(libres)) == 1500 and time.time() - t < 10
    iguales = [{"id": f"f{i}", "cohorte": f"Belder {i} ADAD"} for i in range(1500)]
    t = time.time()
    assert len(M.grupos_de_cohorte(iguales)) == 1 and time.time() - t < 10


def test_ids_repetidos_heredados_y_registros_antiguos_en_grupos():
    fs = [_f("h-1-inv-2", "ADNI"), _f("h-1", "ADNI"), _f("h-1-inv-2", "ADNI"), {"id": "viejo"}, {"id": "sin-plan", "tipoEstudio": None, "cohorte": None, "relacion": None}]
    assert M.grupos_de_cohorte(fs) == [["h-1-inv-2", "h-1"]] and M.fuentes_sin_cohorte(fs) == 2
    assert M.texto_metodos(fs).startswith("Cohorte: ADNI en todas las fuentes que la nombran (2 de 4)")
