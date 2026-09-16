"""Propagación de dependencias (rosa/dependencias.py): índice inverso,
dependientes por fuente, DOI, hecho e hipótesis, marcas de "pendiente de
revisar" idempotentes, atender, texto para el traspaso y la propagación de
retractaciones, sustituciones y contradicciones."""

from datetime import datetime, timezone

import pytest

from rosa import dependencias as D
from rosa.estado import acciones as A
from rosa.estado import plantilla as P

AHORA = int(datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)
INV = "inv-dep"


def _estado():
    e = P.estado_inicial()
    assert A.crear_investigacion(e, {"titulo": "T", "objetivo": "O", "condicionParada": "3 iteraciones"}, AHORA, INV) == INV
    return e


def _fuente(id_, doi=None, referencia=None):
    return P.nueva_fuente(id=id_, referencia=referencia or f"Ref {id_}, 2025", doi=doi, pagina=3)


def _af(af_id, fuente_id=None, **k):
    a = {"texto": "GFAP sube", "cita": "[Ref, pág. 3]", "veredicto": "sostenida", "motivo": "", "entidadDistinta": False, "tipo": "literatura", "clase": "literatura", "sintetico": False, "cohorte": "", "trayectoria": None, "fragmento": "GFAP sube", "afirmacionId": af_id}
    if fuente_id:
        a["fuenteId"] = fuente_id
    a.update(k)
    return a


def _hip(e, id_, fuentes=(), afirmaciones=(), derivada_de=None, titulo="GFAP sube antes que NfL", inv=INV):
    h = P.nueva_hipotesis(inv, 1, AHORA, id=id_, titulo=titulo, enunciado="Enunciado", derivadaDe=derivada_de)
    h["procedencia"]["fuentes"] = list(fuentes)
    h["afirmaciones"] = list(afirmaciones)
    e["hipotesis"].append(h)
    return h


def _hecho(e, id_, fuente_ids=(), afirmacion_ids=None, enunciado="Un hecho", inv=INV, **extra):
    x = P.nuevo_hecho(inv, "hecho", "Biomarcadores", enunciado, "sabido", "fuente", [{"fuenteId": f, "referencia": f"Ref {f}", "pagina": 3} for f in fuente_ids], AHORA)
    x["id"] = id_
    if afirmacion_ids is not None:
        x["afirmacionIds"] = list(afirmacion_ids)
    x.update(extra)
    e["hechos"].append(x)
    return x


def _plan(e, id_, hip_id, inv=INV):
    p = P.nuevo_plan_analisis(inv, hip_id, "gse1297", AHORA, id=id_, pregunta="¿Sube GFAP en el grupo AD?")
    e["planesAnalisis"].append(p)
    return p


def _ejecucion(e, id_, hip_id, plan_id, inv=INV):
    r = P.nueva_ejecucion(inv, hip_id, plan_id, "confirmatorio", "print(1)", 1, "h", AHORA)
    r["id"] = id_
    e["ejecuciones"].append(r)
    return r


def _escenario():
    """Dos hipótesis con fuentes, una derivada, hechos con y sin afirmacionIds,
    un plan, una ejecución y el hecho he-hip-a que nace al aceptar hip-a."""
    e = _estado()
    fa = _fuente("f-a", doi="10.1000/ABC.Def")
    fb = _fuente("f-b", doi="10.1000/otro")
    fc = _fuente("f-c")
    _hip(e, "hip-a", fuentes=[fa, fb], afirmaciones=[_af("af-1", "f-a"), _af("af-2", "f-b")])
    _hip(e, "hip-b", fuentes=[fc], afirmaciones=[_af("af-3", "f-c")], titulo="NfL sube antes que p-tau181")
    _hip(e, "hip-c", fuentes=[fc], afirmaciones=[], derivada_de="hip-a", titulo="Derivada de hip-a")
    _hecho(e, "he-1", fuente_ids=["f-a"], enunciado="GFAP sube en portadores de APOE4")  # sin afirmacionIds: enlaza por fuente
    _hecho(e, "he-2", fuente_ids=["f-z"], afirmacion_ids=["af-3"], enunciado="NfL sube en la cohorte")  # sin fuente común: enlaza por afirmación
    _hecho(e, "he-3", fuente_ids=[], enunciado="Sin procedencia ni afirmaciones")
    _plan(e, "plan-a", "hip-a")
    _plan(e, "plan-b", "hip-b")
    _ejecucion(e, "run-a", "hip-a", "plan-a")
    e["relaciones"].append({"id": "rel-hip-a", "investigacionId": INV, "de": "GFAP", "a": "NfL", "tipo": "inferencia", "contexto": "", "hipotesisId": "hip-a", "actualizadoEn": AHORA})
    assert A.revisar_hipotesis(e, "hip-a", "aceptar", "Vale", "Allegri", AHORA)
    assert any(x["id"] == "he-hip-a" for x in e["hechos"])
    return e


# -- Índice --------------------------------------------------------------------


def test_indice_inverso_por_fuente_doi_hecho_e_hipotesis():
    e = _escenario()
    idx = D.indice(e, INV)
    assert idx["porFuente"]["f-a"]["hipotesis"] == {"hip-a"}
    assert idx["porFuente"]["f-a"]["hechos"] == {"he-1", "he-hip-a"}  # el he-hip-a copia las fuentes de la hipótesis
    assert idx["porFuente"]["f-c"]["hipotesis"] == {"hip-b", "hip-c"}
    assert idx["porFuente"]["f-z"]["hechos"] == {"he-2"} and idx["porFuente"]["f-z"]["hipotesis"] == set()
    assert idx["porDoi"] == {"10.1000/abc.def": {"f-a"}, "10.1000/otro": {"f-b"}}
    assert idx["porHecho"]["he-1"]["hipotesis"] == {"hip-a"}  # por fuente
    assert idx["porHecho"]["he-2"]["hipotesis"] == {"hip-b"}  # por afirmacionId
    assert idx["porHecho"]["he-3"]["hipotesis"] == set()
    assert "hip-a" in idx["porHecho"]["he-hip-a"]["hipotesis"]
    a = idx["porHipotesis"]["hip-a"]
    assert a["derivadas"] == {"hip-c"} and a["planes"] == {"plan-a"} and a["ejecuciones"] == {"run-a"} and a["hechos"] == {"he-hip-a"} and a["relaciones"] == {"rel-hip-a"}
    assert idx["porHipotesis"]["hip-b"]["hechos"] == set() and idx["porHipotesis"]["hip-b"]["planes"] == {"plan-b"}


def test_indice_filtra_por_investigacion_y_none_lo_ve_todo():
    e = _escenario()
    assert A.crear_investigacion(e, {"titulo": "Otra", "objetivo": "O", "condicionParada": "1"}, AHORA, "inv-otra") == "inv-otra"
    _hip(e, "hip-otra", fuentes=[_fuente("f-a", doi="10.1000/abc.def")], inv="inv-otra")
    assert D.indice(e, INV)["porFuente"]["f-a"]["hipotesis"] == {"hip-a"}
    assert D.indice(e, "inv-otra")["porFuente"]["f-a"]["hipotesis"] == {"hip-otra"}
    assert D.indice(e, None)["porFuente"]["f-a"]["hipotesis"] == {"hip-a", "hip-otra"}
    assert D.dependientes_de_fuente(e, INV, fuente_id="f-a")["hipotesis"] == ["hip-a"]


# -- Dependientes --------------------------------------------------------------


def test_dependientes_por_fuente_y_por_doi_con_mayusculas_distintas():
    e = _escenario()
    por_id = D.dependientes_de_fuente(e, INV, fuente_id="f-a")
    assert por_id == {"hipotesis": ["hip-a"], "hechos": ["he-1", "he-hip-a"], "planes": ["plan-a"]}
    assert D.dependientes_de_fuente(e, INV, doi="10.1000/abc.DEF") == por_id
    assert D.dependientes_de_fuente(e, INV, doi="https://doi.org/10.1000/ABC.def") == por_id
    assert D.dependientes_de_fuente(e, INV, doi="doi:10.1000/Abc.Def") == por_id
    # Id y DOI de fuentes distintas se suman.
    juntos = D.dependientes_de_fuente(e, INV, fuente_id="f-c", doi="10.1000/ABC.DEF")
    assert juntos["hipotesis"] == ["hip-a", "hip-b", "hip-c"] and juntos["planes"] == ["plan-a", "plan-b"]
    # Sin id ni DOI, o con un DOI desconocido: nada, no un error.
    assert D.dependientes_de_fuente(e, INV) == {"hipotesis": [], "hechos": [], "planes": []}
    assert D.dependientes_de_fuente(e, INV, doi="10.9999/no-existe")["hipotesis"] == []


def test_doi_de_las_fuentes_privadas_de_la_corrida_resuelve_hechos():
    e = _estado()
    A.iniciar_corrida(e, INV, AHORA)
    c = A.ultima_corrida_de(e, INV)
    c["_fuentes"] = {"f-priv": {"id": "f-priv", "doi": "10.5555/PRIV", "referencia": "Privada 2025"}}
    _hecho(e, "he-p", fuente_ids=["f-priv"], enunciado="Hecho con fuente solo en la corrida")
    assert D.dependientes_de_fuente(e, INV, doi="10.5555/priv") == {"hipotesis": [], "hechos": ["he-p"], "planes": []}


def test_hechos_con_y_sin_afirmacion_ids():
    e = _escenario()
    # he-1 no trae afirmacionIds (registro de hoy): enlaza por la fuente compartida.
    assert D.dependientes_de_hecho(e, INV, "he-1")["hipotesis"] == ["hip-a"]
    # he-2 trae afirmacionIds y su fuente no la cita nadie: enlaza por la afirmación.
    assert D.dependientes_de_hecho(e, INV, "he-2")["hipotesis"] == ["hip-b"]
    # he-3 no tiene nada: vacío.
    assert D.dependientes_de_hecho(e, INV, "he-3") == {"hipotesis": [], "hechos": [], "cuestiones": []}
    # Un hecho que no existe tampoco rompe.
    assert D.dependientes_de_hecho(e, INV, "he-fantasma") == {"hipotesis": [], "hechos": [], "cuestiones": []}


def test_dependientes_de_hecho_derivados_y_cuestiones_pero_no_sustitutos():
    e = _escenario()
    _hecho(e, "he-4", enunciado="Derivado de he-1", derivadoDe=["he-1"])
    _hecho(e, "he-5", enunciado="Derivado (texto)", derivadoDe="he-1")
    _hecho(e, "he-6", enunciado="Sustituye a he-1", sustituyeA="he-1", contradiceA=["he-1"])
    e.setdefault("cuestiones", []).extend([{"id": "cu-1", "investigacionId": INV, "hechoIds": ["he-1", "he-2"]}, {"id": "cu-2", "hechoIds": ["he-9"]}, {"id": "cu-3", "investigacionId": "inv-otra", "hechoIds": ["he-1"]}])
    d = D.dependientes_de_hecho(e, INV, "he-1")
    assert d["hechos"] == ["he-4", "he-5"]  # he-6 depende del nuevo, no del viejo
    assert d["cuestiones"] == ["cu-1"]


def test_dependientes_de_hipotesis():
    e = _escenario()
    e.setdefault("cuestiones", []).append({"id": "cu-a", "investigacionId": INV, "hipotesisIds": ["hip-a"], "hechoIds": []})
    assert D.dependientes_de_hipotesis(e, "hip-a") == {"hipotesis": ["hip-c"], "planes": ["plan-a"], "ejecuciones": ["run-a"], "hechos": ["he-hip-a"], "relaciones": ["rel-hip-a"], "cuestiones": ["cu-a"]}
    assert D.dependientes_de_hipotesis(e, "hip-c") == {"hipotesis": [], "planes": [], "ejecuciones": [], "hechos": [], "relaciones": [], "cuestiones": []}
    assert D.dependientes_de_hipotesis(e, "no-existe")["hipotesis"] == []


# -- Marcar --------------------------------------------------------------------


def test_marcar_pendientes_escribe_marcas_y_es_idempotente():
    e = _escenario()
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-a")
    he = next(x for x in e["hechos"] if x["id"] == "he-1")
    plan = next(x for x in e["planesAnalisis"] if x["id"] == "plan-a")
    h["_conclusionIntentada"] = 2
    antes = he["actualizadoEn"]
    n_hist = len(he["historial"])
    objetivos = {"hipotesis": ["hip-a"], "hechos": ["he-1"], "planes": ["plan-a"]}
    marcados = D.marcar_pendientes(e, objetivos, "fuente_retractada", "La fuente X fue retractada", "f-a", AHORA)
    assert marcados == ["hipotesis:hip-a", "hecho:he-1", "plan:plan-a"]
    assert h["pendienteRevision"] == {"causa": "fuente_retractada", "detalle": "La fuente X fue retractada", "origenId": "f-a", "desde": AHORA}
    assert h["_evidenciaNueva"] is True and "_conclusionIntentada" not in h
    assert he["pendienteRevision"]["causa"] == "fuente_retractada"
    assert he["actualizadoEn"] == antes  # la poda al volver a una iteración usa esta marca
    assert len(he["historial"]) == n_hist + 1
    mov = he["historial"][-1]
    assert mov == {"fecha": AHORA, "de": "sabido", "a": "sabido", "quien": "Rosa", "motivo": "Pendiente de revisar: La fuente X fue retractada"}
    assert plan["pendienteRevision"]["origenId"] == "f-a"
    # Misma causa y mismo origen: no se repite nada.
    assert D.marcar_pendientes(e, objetivos, "fuente_retractada", "Otra vez", "f-a", AHORA + 1000) == []
    assert h["pendienteRevision"]["desde"] == AHORA and len(he["historial"]) == n_hist + 1
    # Otra causa sobre lo ya pendiente: pasa a principal, la anterior se conserva y `desde` es la más antigua.
    assert D.marcar_pendientes(e, {"hipotesis": ["hip-a"]}, "hecho_sustituido", "El hecho Y fue sustituido", "he-y", AHORA + 5000) == ["hipotesis:hip-a"]
    assert h["pendienteRevision"]["causa"] == "hecho_sustituido" and h["pendienteRevision"]["desde"] == AHORA
    assert [a["causa"] for a in h["pendienteRevision"]["anteriores"]] == ["fuente_retractada"]
    # Y la primera causa sigue contando como ya marcada.
    assert D.marcar_pendientes(e, {"hipotesis": ["hip-a"]}, "fuente_retractada", "x", "f-a", AHORA + 9000) == []


def test_marcar_tolera_ids_repetidos_desconocidos_vacios_y_rechaza_causa_invalida():
    e = _escenario()
    marcados = D.marcar_pendientes(e, {"hipotesis": ["hip-b", "hip-b", "no-existe"], "hecho": ["he-2", "he-2"], "plan": ["plan-b"], "planes": ["plan-b"]}, "hecho_contradicho", "", "he-x", AHORA)
    assert marcados == ["hipotesis:hip-b", "hecho:he-2", "plan:plan-b"]
    he = next(x for x in e["hechos"] if x["id"] == "he-2")
    assert sum(1 for m in he["historial"] if m["motivo"].startswith("Pendiente de revisar")) == 1
    assert he["pendienteRevision"]["detalle"] == "depende de un hecho contradicho"  # detalle vacío: la frase de la causa
    assert D.marcar_pendientes(e, None, "fuente_retractada", "x", "f", AHORA) == []
    assert D.marcar_pendientes(e, {}, "fuente_retractada", "x", "f", AHORA) == []
    with pytest.raises(ValueError):
        D.marcar_pendientes(e, {"hipotesis": ["hip-a"]}, "porque_si", "x", "f", AHORA)


# -- Atender -------------------------------------------------------------------


def test_atender_pendiente_quita_la_marca_y_deja_rastro():
    e = _escenario()
    D.marcar_pendientes(e, {"hipotesis": ["hip-a"], "hechos": ["he-1"], "planes": ["plan-a"]}, "fuente_retractada", "La fuente X fue retractada", "f-a", AHORA)
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-a")
    he = next(x for x in e["hechos"] if x["id"] == "he-1")
    plan = next(x for x in e["planesAnalisis"] if x["id"] == "plan-a")
    antes = he["actualizadoEn"]
    assert D.atender_pendiente(e, "hipotesis", "hip-a", "Allegri", "Sustituida la cita por la versión corregida", AHORA + 60_000)
    assert h["pendienteRevision"] is None  # como la deja la plantilla, no ausente
    assert h["procedencia"]["registro"][-1] == "2026-09-16T12:01:00+00:00 pendiente de revisar atendida por Allegri: Sustituida la cita por la versión corregida"
    assert D.atender_pendiente(e, "hecho", "he-1", "Allegri", "Sigue en pie con otra fuente", AHORA + 60_000)
    assert he["pendienteRevision"] is None and he["actualizadoEn"] == antes
    assert he["historial"][-1] == {"fecha": AHORA + 60_000, "de": "sabido", "a": "sabido", "quien": "Allegri", "motivo": "Pendiente de revisar atendida: Sigue en pie con otra fuente"}
    assert D.atender_pendiente(e, "plan", "plan-a", "Allegri", "", AHORA)
    assert plan["pendienteRevision"] is None
    assert D.pendientes(e, INV) == []
    # Nada que atender, tipo desconocido u objeto inexistente: False.
    assert D.atender_pendiente(e, "hipotesis", "hip-a", "Allegri", "x", AHORA) is False
    assert D.atender_pendiente(e, "hecho", "he-fantasma", "Allegri", "x", AHORA) is False
    assert D.atender_pendiente(e, "cuestion", "cu-1", "Allegri", "x", AHORA) is False


# -- Listar y texto ------------------------------------------------------------


def test_pendientes_y_texto_para_el_traspaso():
    e = _escenario()
    assert D.pendientes(e, INV) == []
    assert D.texto_pendientes(e, INV) == "Sin pendientes de revisar."
    D.marcar_pendientes(e, {"hechos": ["he-1"]}, "hecho_sustituido", "El hecho «GFAP sube» fue sustituido por «GFAP sube en APOE4»", "he-9", AHORA + 86_400_000)
    D.marcar_pendientes(e, {"hipotesis": ["hip-a"], "planes": ["plan-a"]}, "fuente_retractada", "La fuente «Ref f-a, 2025» fue retractada", "f-a", AHORA)
    lista = D.pendientes(e, INV)
    assert [(p["tipo"], p["id"]) for p in lista] == [("hipotesis", "hip-a"), ("plan", "plan-a"), ("hecho", "he-1")]  # por desde, luego tipo
    assert lista[0]["titulo"] == "GFAP sube antes que NfL" and lista[1]["titulo"] == "¿Sube GFAP en el grupo AD?" and lista[2]["titulo"] == "GFAP sube en portadores de APOE4"
    texto = D.texto_pendientes(e, INV)
    lineas = texto.split("\n")
    assert lineas[0] == "Pendiente de revisar: la hipótesis «GFAP sube antes que NfL» depende de una fuente retractada (desde el 16/09): La fuente «Ref f-a, 2025» fue retractada"
    assert lineas[1].startswith("Pendiente de revisar: el plan de análisis «¿Sube GFAP en el grupo AD?» depende de una fuente retractada (desde el 16/09)")
    assert lineas[2].startswith("Pendiente de revisar: el hecho «GFAP sube en portadores de APOE4» depende de un hecho sustituido (desde el 17/09)")
    # Con máximo, dice cuántas quedan.
    corto = D.texto_pendientes(e, INV, maximo=1)
    assert corto.split("\n") == [lineas[0], "Y 2 pendientes de revisar más."]
    # Textos en inglés en el título no cambian la frase.
    D.marcar_pendientes(e, {"hipotesis": ["hip-b"]}, "hipotesis_reformulada", "", "hip-z@v2", AHORA)
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-b")
    h["titulo"] = "Plasma GFAP rises before NfL in APOE4 carriers"
    assert "la hipótesis «Plasma GFAP rises before NfL in APOE4 carriers» deriva de una hipótesis reformulada (desde el 16/09)" in D.texto_pendientes(e, INV)


def test_texto_con_causa_desconocida_en_un_registro_antiguo_no_rompe():
    e = _escenario()
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-a")
    h["pendienteRevision"] = {"causa": "causa_vieja", "detalle": "", "origenId": None, "desde": None}
    texto = D.texto_pendientes(e, INV)
    assert "está pendiente por causa vieja" in texto and "fecha desconocida" in texto


# -- Propagar ------------------------------------------------------------------


def test_propagar_retraccion_alcanza_hipotesis_hechos_y_planes_sin_tocar_actualizado_en():
    e = _escenario()
    he1 = next(x for x in e["hechos"] if x["id"] == "he-1")
    he_hip = next(x for x in e["hechos"] if x["id"] == "he-hip-a")
    marcas = {x["id"]: x["actualizadoEn"] for x in e["hechos"]}
    n_eventos = len(e["eventos"])
    marcados = D.propagar_retraccion(e, INV, None, "10.1000/ABC.DEF", AHORA)
    assert marcados == ["hipotesis:hip-a", "hecho:he-1", "hecho:he-hip-a", "plan:plan-a"]
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-a")
    assert h["pendienteRevision"]["causa"] == "fuente_retractada" and h["pendienteRevision"]["doi"] == "10.1000/abc.def"
    assert h["pendienteRevision"]["detalle"] == "La fuente «Ref f-a, 2025» fue retractada (DOI 10.1000/abc.def)"
    assert h["_evidenciaNueva"] is True
    assert he1["pendienteRevision"]["origenId"] == "10.1000/abc.def" and he_hip["pendienteRevision"]["causa"] == "fuente_retractada"
    assert {x["id"]: x["actualizadoEn"] for x in e["hechos"]} == marcas
    assert next(x for x in e["planesAnalisis"] if x["id"] == "plan-a")["pendienteRevision"]["causa"] == "fuente_retractada"
    # Lo que no depende de f-a queda intacto (la plantilla trae la clave en None).
    assert not next(x for x in e["hipotesis"] if x["id"] == "hip-b").get("pendienteRevision")
    assert not next(x for x in e["planesAnalisis"] if x["id"] == "plan-b").get("pendienteRevision")
    assert not next(x for x in e["hechos"] if x["id"] == "he-2").get("pendienteRevision")
    # Deja un evento del tipo que conoce la interfaz, y solo uno.
    assert len(e["eventos"]) == n_eventos + 1
    ev = e["eventos"][-1]
    assert ev["tipo"] == "dependencias" and ev["investigacionId"] == INV and "1 hipótesis, 2 hechos, 1 plan de análisis" in ev["texto"]
    # Repetir la misma retractación (por DOI, por id, o por los dos) no marca ni avisa otra vez.
    assert D.propagar_retraccion(e, INV, "f-a", "10.1000/abc.def", AHORA + 1) == []
    assert D.propagar_retraccion(e, INV, "f-a", None, AHORA + 2) == []
    assert D.propagar_retraccion(e, INV, None, "HTTPS://DOI.ORG/10.1000/ABC.DEF", AHORA + 3) == []
    assert len(e["eventos"]) == n_eventos + 1
    assert h["pendienteRevision"]["desde"] == AHORA and "anteriores" not in h["pendienteRevision"]
    # Sin fuente ni DOI: nada.
    assert D.propagar_retraccion(e, INV, None, None, AHORA) == []
    assert D.propagar_retraccion(e, INV, None, "   ", AHORA) == []


def test_propagar_retraccion_por_id_y_fuente_corregida():
    e = _escenario()
    assert D.propagar_retraccion(e, INV, "f-c", None, AHORA, causa="fuente_corregida") == ["hipotesis:hip-b", "hipotesis:hip-c", "plan:plan-b"]
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-c")
    assert h["pendienteRevision"]["causa"] == "fuente_corregida" and h["pendienteRevision"]["detalle"] == "La fuente «Ref f-c, 2025» fue corregida"
    assert "Fuente corregida" in e["eventos"][-1]["texto"]


def test_propagar_sustitucion_y_contradiccion_no_marcan_al_hecho_nuevo():
    e = _escenario()
    nuevo = _hecho(e, "he-nuevo", fuente_ids=["f-a"], enunciado="GFAP sube en APOE4 (medida en plasma)", derivadoDe=["he-1"], sustituyeA="he-1")
    _hecho(e, "he-4", enunciado="Derivado de he-1", derivadoDe=["he-1"])
    viejo = next(x for x in e["hechos"] if x["id"] == "he-1")
    marcas = {x["id"]: x["actualizadoEn"] for x in e["hechos"]}
    marcados = D.propagar_sustitucion(e, INV, "he-1", "he-nuevo", AHORA)
    assert marcados == ["hipotesis:hip-a", "hecho:he-4", "plan:plan-a"]
    assert not nuevo.get("pendienteRevision") and not viejo.get("pendienteRevision")  # el viejo es la causa, el nuevo el sustituto
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-a")
    assert h["pendienteRevision"] == {"causa": "hecho_sustituido", "detalle": "El hecho «GFAP sube en portadores de APOE4» fue sustituido por «GFAP sube en APOE4 (medida en plasma)»", "origenId": "he-1", "desde": AHORA, "nuevoId": "he-nuevo"}
    assert {x["id"]: x["actualizadoEn"] for x in e["hechos"]} == marcas
    assert e["eventos"][-1]["tipo"] == "dependencias" and e["eventos"][-1]["texto"].startswith("Hecho sustituido")
    # Contradicción sobre otro hecho: causa distinta, mismo mecanismo; sin hecho nuevo conocido tampoco rompe.
    assert D.propagar_contradiccion(e, INV, "he-2", None, AHORA + 1) == ["hipotesis:hip-b", "plan:plan-b"]
    hb = next(x for x in e["hipotesis"] if x["id"] == "hip-b")
    assert hb["pendienteRevision"]["causa"] == "hecho_contradicho" and hb["pendienteRevision"]["nuevoId"] is None
    assert hb["pendienteRevision"]["detalle"] == "El hecho «NfL sube en la cohorte» quedó contradicho"
    # Un hecho viejo que no existe: nada.
    assert D.propagar_sustitucion(e, INV, "he-fantasma", "he-nuevo", AHORA) == []


def test_propagar_reformulacion_alcanza_derivadas_planes_y_hecho_de_revision():
    e = _escenario()
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-a")
    h["version"] = 2
    assert D.propagar_reformulacion(e, "hip-a", AHORA, "cambió la cohorte") == ["hipotesis:hip-c", "hecho:he-hip-a", "plan:plan-a"]
    hc = next(x for x in e["hipotesis"] if x["id"] == "hip-c")
    assert hc["pendienteRevision"]["causa"] == "hipotesis_reformulada" and hc["pendienteRevision"]["origenId"] == "hip-a@v2"
    assert hc["pendienteRevision"]["detalle"] == "La hipótesis «GFAP sube antes que NfL» se reformuló (versión 2): cambió la cohorte"
    # La misma versión no se propaga dos veces; una versión nueva sí.
    assert D.propagar_reformulacion(e, "hip-a", AHORA + 1) == []
    h["version"] = 3
    assert D.propagar_reformulacion(e, "hip-a", AHORA + 2) == ["hipotesis:hip-c", "hecho:he-hip-a", "plan:plan-a"]
    assert D.propagar_reformulacion(e, "no-existe", AHORA) == []


# -- Registros antiguos y entradas raras ---------------------------------------


def test_registros_antiguos_sin_claves_nuevas_no_rompen():
    e = _estado()
    # Una hipótesis vieja sin procedencia ni afirmaciones, un hecho sin procedencia ni historial,
    # y un estado sin las listas de ROSA2018 ni cuestiones.
    e["hipotesis"].append({"id": "hip-vieja", "investigacionId": INV, "titulo": "Vieja"})
    e["hechos"].append({"id": "he-viejo", "investigacionId": INV, "enunciado": "Viejo", "estado": "sabido"})
    e["hechos"].append({"id": "he-hip-vieja", "investigacionId": INV, "tipo": "hipotesis", "enunciado": "Revisión de la vieja", "estado": "abierto"})
    for clave in ("planesAnalisis", "ejecuciones", "relaciones", "cuestiones", "corridas"):
        e.pop(clave, None)
    idx = D.indice(e, INV)
    assert idx["porHipotesis"]["hip-vieja"]["hechos"] == {"he-hip-vieja"} and idx["porHecho"]["he-viejo"]["hipotesis"] == set()
    assert D.dependientes_de_fuente(e, INV, fuente_id="f-x") == {"hipotesis": [], "hechos": [], "planes": []}
    assert D.dependientes_de_hecho(e, INV, "he-viejo") == {"hipotesis": [], "hechos": [], "cuestiones": []}
    assert D.dependientes_de_hipotesis(e, "hip-vieja") == {"hipotesis": [], "planes": [], "ejecuciones": [], "hechos": ["he-hip-vieja"], "relaciones": [], "cuestiones": []}
    marcados = D.marcar_pendientes(e, {"hipotesis": ["hip-vieja"], "hechos": ["he-viejo"], "planes": ["plan-x"]}, "fuente_retractada", "x", "f-x", AHORA)
    assert marcados == ["hipotesis:hip-vieja", "hecho:he-viejo"]  # el plan no existe: no se inventa
    he = e["hechos"][0]
    assert he["historial"] == [{"fecha": AHORA, "de": "sabido", "a": "sabido", "quien": "Rosa", "motivo": "Pendiente de revisar: x"}]
    assert "actualizadoEn" not in he  # no se inventa una fecha que la poda usaría
    assert D.atender_pendiente(e, "hipotesis", "hip-vieja", "Allegri", "vista", AHORA)
    assert e["hipotesis"][0]["procedencia"]["registro"][-1].endswith("pendiente de revisar atendida por Allegri: vista")
    assert D.texto_pendientes(e, INV).startswith("Pendiente de revisar: el hecho «Viejo» depende de una fuente retractada")


def test_estado_vacio_y_objetos_que_no_son_diccionarios():
    e = P.estado_inicial()
    assert D.indice(e, "inv-x") == {"porFuente": {}, "porDoi": {}, "porHecho": {}, "porHipotesis": {}}
    assert D.pendientes(e, None) == [] and D.texto_pendientes(e, None) == "Sin pendientes de revisar."
    e["hipotesis"].append(None)
    e["hechos"].append("basura")
    assert D.dependientes_de_fuente(e, None, fuente_id="f") == {"hipotesis": [], "hechos": [], "planes": []}
    assert D.marcar_pendientes(e, {"hipotesis": ["x"]}, "fuente_retractada", "x", "f", AHORA) == []


def test_ids_numericos_y_desde_corrupto_no_rompen():
    e = _estado()
    h = P.nueva_hipotesis(INV, 1, AHORA, id=7, titulo="Con id numérico")
    h["procedencia"]["fuentes"] = [P.nueva_fuente(id=99, doi="10.1/X")]
    e["hipotesis"].append(h)
    x = P.nuevo_hecho(INV, "hecho", "t", "Hecho con id numérico", "sabido", "fuente", [{"fuenteId": 99, "referencia": "r", "pagina": None}, {"fuenteId": None}, "basura"], AHORA)
    x["id"] = 3
    x["historial"] = None
    x["afirmacionIds"] = 5  # ni siquiera es una lista
    e["hechos"].append(x)
    # El índice trabaja con los ids como texto y marcar los encuentra igual.
    assert D.dependientes_de_fuente(e, INV, fuente_id=99) == {"hipotesis": ["7"], "hechos": ["3"], "planes": []}
    assert D.propagar_retraccion(e, INV, 99, None, AHORA) == ["hipotesis:7", "hecho:3"]
    assert h["pendienteRevision"]["origenId"] == "10.1/x"  # el DOI se resolvió desde el id
    assert x["historial"][-1]["motivo"].startswith("Pendiente de revisar: La fuente")
    assert D.propagar_retraccion(e, INV, None, " 10.1/x ", AHORA + 1) == []
    # Un `desde` corrupto en un registro guardado no tumba el listado ni el texto.
    h["pendienteRevision"]["desde"] = "no es un número"
    assert [p["id"] for p in D.pendientes(e, INV)] == ["7", "3"]
    assert "fecha desconocida" in D.texto_pendientes(e, INV, maximo=0).split("\n")[0]
    # Otra causa encima de un `desde` corrupto: la nueva marca queda con la fecha de ahora.
    assert D.marcar_pendientes(e, {"hipotesis": [7]}, "hecho_sustituido", "x", "he-z", AHORA + 5) == ["hipotesis:7"]
    assert h["pendienteRevision"]["desde"] == AHORA + 5 and [a["causa"] for a in h["pendienteRevision"]["anteriores"]] == ["fuente_retractada"]
    # Atender una hipótesis sin procedencia reconstruye el registro en vez de fallar.
    h["procedencia"] = None
    assert D.atender_pendiente(e, "hipotesis", 7, "", "", AHORA)
    assert h["procedencia"]["registro"][-1].endswith("pendiente de revisar atendida por una persona: sin nota")
    # Una hipótesis que dice derivar de sí misma no cuelga nada.
    h["derivadaDe"] = 7
    assert D.dependientes_de_hipotesis(e, 7)["hipotesis"] == ["7"]


def test_normalizar_doi():
    assert D.normalizar_doi(" HTTPS://DOI.ORG/10.1000/AbC ") == "10.1000/abc"
    assert D.normalizar_doi("doi:https://dx.doi.org/10.1000/abc") == "10.1000/abc"
    assert D.normalizar_doi(None) == "" and D.normalizar_doi("") == "" and D.normalizar_doi(12) == "12"


# -- Adversariales (segunda pasada) ---------------------------------------------


def test_ids_repetidos_de_hipotesis_suman_dependencias_en_vez_de_pisarse():
    """Dos hipótesis con el mismo id (registro roto): el hecho que comparte
    fuente con la primera la encuentra igual; antes la segunda pisaba a la
    primera en el índice y el hecho quedaba sin dependientes."""
    e = _estado()
    for fid in ("f-1", "f-2"):
        _hip(e, "hip-dup", fuentes=[_fuente(fid)], titulo="Duplicada")
    _hecho(e, "he-x", fuente_ids=["f-1"])
    _hecho(e, "he-y", fuente_ids=["f-2"])
    idx = D.indice(e, INV)
    assert idx["porHecho"]["he-x"]["hipotesis"] == {"hip-dup"} and idx["porHecho"]["he-y"]["hipotesis"] == {"hip-dup"}
    assert D.dependientes_de_fuente(e, INV, fuente_id="f-1")["hipotesis"] == ["hip-dup"]


def test_copia_heredada_del_hecho_de_revision_en_una_rama_sigue_dependiendo_de_la_hipotesis():
    """Al bifurcar, copiar_hechos deja `he-hip-a-inv-rama` en la rama (y
    `he-hip-a-inv-rama-inv-rama-2` en una rama de la rama). Esas copias
    dependen de hip-a igual que el original: una reformulación las alcanza."""
    e = _escenario()
    assert A.bifurcar_investigacion(e, INV, "rama", AHORA, "inv-rama") == "inv-rama"
    assert A.bifurcar_investigacion(e, "inv-rama", "rama de la rama", AHORA, "inv-rama-2") == "inv-rama-2"
    copias = ["he-hip-a", "he-hip-a-inv-rama", "he-hip-a-inv-rama-inv-rama-2"]
    assert [x["id"] for x in e["hechos"] if x["tipo"] == "hipotesis"] == copias
    assert D.dependientes_de_hipotesis(e, "hip-a")["hechos"] == copias
    assert D.indice(e, None)["porHecho"]["he-hip-a-inv-rama-inv-rama-2"]["hipotesis"] == {"hip-a"}
    # El índice de la rama sola no conoce hip-a (vive en la investigación madre): no inventa el enlace.
    assert D.indice(e, "inv-rama")["porHecho"]["he-hip-a-inv-rama"]["hipotesis"] == set()
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-a")
    h["version"] = 2
    assert D.propagar_reformulacion(e, "hip-a", AHORA) == ["hipotesis:hip-c", "hecho:he-hip-a", "hecho:he-hip-a-inv-rama", "hecho:he-hip-a-inv-rama-inv-rama-2", "plan:plan-a"]
    # El índice de la investigación madre solo ve sus propios hechos; el de todo el estado ve las copias.
    assert D.indice(e, INV)["porHipotesis"]["hip-a"]["hechos"] == {"he-hip-a"}
    assert D.indice(e, None)["porHipotesis"]["hip-a"]["hechos"] == set(copias)
    # Un hecho corriente cuyo id empieza por he- no se confunde con uno de revisión.
    assert "he-1" not in D.dependientes_de_hipotesis(e, "1")["hechos"]


def test_extra_no_se_comparte_entre_marcas():
    e = _escenario()
    D.marcar_pendientes(e, {"hipotesis": ["hip-a", "hip-b"]}, "fuente_retractada", "d", "o", AHORA, extra={"etiquetas": ["a"]})
    ha = next(x for x in e["hipotesis"] if x["id"] == "hip-a")
    hb = next(x for x in e["hipotesis"] if x["id"] == "hip-b")
    ha["pendienteRevision"]["etiquetas"].append("b")
    assert hb["pendienteRevision"]["etiquetas"] == ["a"]


def test_retraccion_por_id_y_despues_por_doi_no_marca_dos_veces():
    """La fuente no tenía DOI cuando llegó la primera retractación (origen: el
    id). Después gana DOI y la retractación vuelve por DOI, por id y DOI, o por
    otro id de la misma publicación: sigue siendo el mismo origen."""
    e = _estado()
    _hip(e, "hip-a", fuentes=[_fuente("f-a", referencia="Ref A")])
    _hip(e, "hip-b", fuentes=[_fuente("f-b", doi="10.1/a", referencia="Ref A (otra corrida)")])
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-a")
    assert D.propagar_retraccion(e, INV, "f-a", None, AHORA) == ["hipotesis:hip-a"]
    assert h["pendienteRevision"]["origenId"] == "f-a"
    h["procedencia"]["fuentes"][0]["doi"] = "10.1/A"
    # Ahora f-a y f-b comparten DOI: hip-b es nueva (no estaba marcada), hip-a no se repite.
    assert D.propagar_retraccion(e, INV, "f-a", "10.1/a", AHORA + 1) == ["hipotesis:hip-b"]
    assert D.propagar_retraccion(e, INV, None, "10.1/a", AHORA + 2) == []
    assert D.propagar_retraccion(e, INV, "f-b", None, AHORA + 3) == []
    assert "anteriores" not in h["pendienteRevision"] and h["pendienteRevision"]["desde"] == AHORA


def test_referencia_de_una_fuente_con_id_numerico_pedida_como_texto():
    e = _estado()
    h = P.nueva_hipotesis(INV, 1, AHORA, id="hip-a", titulo="A")
    h["procedencia"]["fuentes"] = [P.nueva_fuente(id=99, referencia="Ref 99, 2025")]
    e["hipotesis"].append(h)
    assert D.propagar_retraccion(e, INV, "99", None, AHORA) == ["hipotesis:hip-a"]
    assert h["pendienteRevision"]["detalle"] == "La fuente «Ref 99, 2025» fue retractada"


def test_reformulacion_con_version_none_o_corrupta_usa_la_version_1():
    e = _escenario()
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-a")
    h["version"] = None
    assert D.propagar_reformulacion(e, "hip-a", AHORA) == ["hipotesis:hip-c", "hecho:he-hip-a", "plan:plan-a"]
    hc = next(x for x in e["hipotesis"] if x["id"] == "hip-c")
    assert hc["pendienteRevision"]["origenId"] == "hip-a@v1" and "(versión 1)" in hc["pendienteRevision"]["detalle"]
    h["version"] = "dos"
    assert D.propagar_reformulacion(e, "hip-a", AHORA + 1) == []  # sigue siendo la versión 1: no se repite


def test_propagacion_sobre_todo_el_estado_deja_un_evento_por_investigacion():
    e = _escenario()
    assert A.crear_investigacion(e, {"titulo": "Otra", "objetivo": "O", "condicionParada": "1"}, AHORA, "inv-otra") == "inv-otra"
    _hip(e, "hip-otra", fuentes=[_fuente("f-otra", doi="HTTPS://DOI.ORG/10.1000/ABC.DEF")], inv="inv-otra")
    n = len(e["eventos"])
    marcados = D.propagar_retraccion(e, None, None, "10.1000/abc.def", AHORA)
    assert marcados == ["hipotesis:hip-a", "hipotesis:hip-otra", "hecho:he-1", "hecho:he-hip-a", "plan:plan-a"]
    nuevos = e["eventos"][n:]
    assert [(ev["investigacionId"], ev["tipo"]) for ev in nuevos] == [(INV, "dependencias"), ("inv-otra", "dependencias")]
    assert "1 hipótesis, 2 hechos, 1 plan de análisis quedan" in nuevos[0]["texto"] and "1 hipótesis queda pendiente" in nuevos[1]["texto"]
    assert nuevos[1]["ruta"] == "#/investigaciones/inv-otra/mundo"
    # Repetida sobre todo el estado: nada nuevo y ningún evento.
    assert D.propagar_retraccion(e, None, "f-a", None, AHORA + 1) == [] and len(e["eventos"]) == n + 2


def test_ahora_none_usa_el_reloj_del_servidor_en_vez_de_romper():
    e = _escenario()
    antes = P.ahora_ms()
    assert D.marcar_pendientes(e, {"hipotesis": ["hip-a"], "hechos": ["he-1"]}, "fuente_retractada", "x", "f", None) == ["hipotesis:hip-a", "hecho:he-1"]
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-a")
    assert isinstance(h["pendienteRevision"]["desde"], int) and h["pendienteRevision"]["desde"] >= antes
    assert D.atender_pendiente(e, "hipotesis", "hip-a", "Allegri", "vista", None)
    assert D.propagar_sustitucion(e, INV, "he-1", None, None) == ["hipotesis:hip-a", "plan:plan-a"]


def test_atender_acepta_el_tipo_en_plural_y_con_mayusculas():
    e = _escenario()
    D.marcar_pendientes(e, {"hipotesis": ["hip-a"], "hechos": ["he-1"], "planes": ["plan-a"]}, "fuente_retractada", "x", "f", AHORA)
    assert D.atender_pendiente(e, "Hipótesis", "hip-a", "Allegri", "vista", AHORA)
    assert D.atender_pendiente(e, "hechos", "he-1", "Allegri", "vista", AHORA)
    assert D.atender_pendiente(e, " PLANES ", "plan-a", "Allegri", "vista", AHORA)
    assert D.pendientes(e, INV) == []
    assert D.atender_pendiente(e, None, "hip-a", "Allegri", "vista", AHORA) is False


def test_registro_con_investigacion_id_none_cuenta_como_propio():
    e = _escenario()
    e["hechos"].append({"id": "he-nulo", "investigacionId": None, "enunciado": "Sin investigación", "estado": "sabido", "procedencia": [{"fuenteId": "f-a"}]})
    assert "he-nulo" in D.dependientes_de_fuente(e, INV, fuente_id="f-a")["hechos"]
    assert "he-nulo" in D.dependientes_de_fuente(e, "inv-otra", fuente_id="f-a")["hechos"]


def test_objetivos_como_texto_y_titulos_en_ingles_o_sin_tildes_pasan_tal_cual():
    e = _escenario()
    assert D.marcar_pendientes(e, {"hipotesis": "hip-a", "hechos": "he-1"}, "hecho_contradicho", "The old fact was contradicted by a new one", "he-9", AHORA) == ["hipotesis:hip-a", "hecho:he-1"]
    h = next(x for x in e["hipotesis"] if x["id"] == "hip-a")
    h["titulo"] = "Hipotesis sin tildes en el titulo"  # sin tildes: entrada a propósito sin acentos
    lineas = D.texto_pendientes(e, INV).split("\n")
    assert lineas[0] == "Pendiente de revisar: la hipótesis «Hipotesis sin tildes en el titulo» depende de un hecho contradicho (desde el 16/09): The old fact was contradicted by a new one"
    # Lo que genera Rosa va acentuado aunque lo que recibe no lo esté.
    assert "hipótesis" in lineas[0] and "análisis" in D.NOMBRE_TIPO["plan"]


def test_indice_es_lineal_con_miles_de_hechos_y_afirmaciones():
    """1.500 hipótesis con 8 afirmaciones y 6.000 hechos con 2 afirmaciones: el
    índice inverso por afirmación y por fuente lo resuelve en una fracción de
    segundo; el recorrido hipótesis por hecho tardaba varios segundos."""
    import time

    e = _estado()
    for i in range(1500):
        h = P.nueva_hipotesis(INV, 1, AHORA, id=f"hip-{i}", titulo=f"H {i}")
        h["procedencia"]["fuentes"] = [P.nueva_fuente(id=f"f-{(i * 3 + k) % 900}", doi=f"10.1/{(i * 3 + k) % 900}") for k in range(3)]
        h["afirmaciones"] = [{"afirmacionId": f"af-{(i * 8 + k) % 4000}", "fuenteId": f"f-{(i * 3 + k) % 900}"} for k in range(8)]
        e["hipotesis"].append(h)
    for j in range(6000):
        x = P.nuevo_hecho(INV, "hecho", "t", f"Hecho {j}", "sabido", "fuente", [{"fuenteId": f"f-{j % 900}", "referencia": "r", "pagina": 1}], AHORA, afirmacion_ids=[f"af-{j % 4000}", f"af-{(j * 7) % 4000}"])
        x["id"] = f"he-{j}"
        e["hechos"].append(x)
    t = time.perf_counter()
    idx = D.indice(e, INV)
    marcados = D.propagar_retraccion(e, INV, None, "10.1/7", AHORA)
    assert time.perf_counter() - t < 2.0
    assert idx["porHecho"]["he-7"]["hipotesis"] and marcados and all(m.split(":")[0] in ("hipotesis", "hecho") for m in marcados)
