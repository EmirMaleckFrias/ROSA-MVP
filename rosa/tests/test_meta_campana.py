"""Meta-campaña (bloque 4 sin GEPA): al terminar una corrida queda la marca para
revisar el arnés; las propuestas se convierten en cambios de aprendizaje con
evaluación pendiente; lo que empeora se revierte solo; lo demás lo decide una
persona con la puerta "solo mejor o igual"."""
from rosa.bucle import corrida as CO
from rosa.estado import acciones as A
from rosa.estado import plantilla as P


def _estado():
    e = P.estado_inicial()
    inv = A.crear_investigacion(e, {"titulo": "t", "objetivo": "GFAP y NfL", "condicionParada": "3 iteraciones"}, 1000)
    c = P.nueva_corrida(inv, 1, 1000)
    c["estado"] = "en_marcha"
    e["corridas"].append(c)
    return e, inv, c


def test_terminar_corrida_deja_la_marca_de_la_meta_campana():
    e, inv, c = _estado()
    assert CO._terminar_corrida(e, c["id"], "presupuesto agotado") is True
    assert c["estado"] == "terminada" and c["_revisarArnes"] is True
    # La marca es privada: no viaja al navegador (empieza por guion bajo) y se quita sin romper.
    assert CO._quitar_marca_arnes(e, c["id"], "prueba") is True and "_revisarArnes" not in c
    assert e["eventos"][-1]["tipo"] == "incidencia" and "meta-campaña" in e["eventos"][-1]["texto"]


def test_las_propuestas_se_vuelven_cambios_con_evaluacion_pendiente_y_sin_repetir():
    e, inv, c = _estado()
    e["criteriosRevision"].append("Una cohorte no es replicación")
    propuestas = [
        {"tipo": "criterio", "descripcion": "Exigir dos cohortes distintas antes de dar por sostenida una precedencia temporal", "motivo": "3 hipótesis cayeron por misma cohorte", "riesgo": "menos hipótesis vivas"},
        {"tipo": "criterio", "descripcion": "una cohorte no es replicación", "motivo": "ya vigente", "riesgo": ""},
        {"tipo": "politica", "descripcion": "Subir la amplitud a equilibrada en la segunda corrida", "motivo": "0 consultas de amplitud rindieron", "riesgo": "más coste"},
        {"tipo": "programa", "descripcion": "Cambiar el prompt del extractor", "motivo": "", "riesgo": ""},
        {"tipo": "criterio", "descripcion": "   ", "motivo": "", "riesgo": ""},
        {"tipo": "criterio", "descripcion": "Exigir dos cohortes distintas antes de dar por sostenida una precedencia temporal", "motivo": "repetida", "riesgo": ""},
    ]
    creados = CO.cambios_desde_propuestas(e, c, propuestas, 2000)
    assert [x["tipo"] for x in creados] == ["criterio", "politica"]
    criterio, politica = creados
    assert criterio["nivel"] == 2 and criterio["estado"] == "propuesto" and criterio["_evaluar"] == 2000 and criterio["origen"] == f"arnes:{c['id']}"
    assert criterio["descripcion"] == "Exigir dos cohortes distintas antes de dar por sostenida una precedencia temporal" and "Motivo: 3 hipótesis" in criterio["nota"]
    assert politica["nivel"] == 3 and "_evaluar" not in politica and "Motivo:" in politica["descripcion"]
    assert len(e["aprendizaje"]) == 2
    # Tope de tres.
    muchas = [{"tipo": "politica", "descripcion": f"Política {i}", "motivo": "m", "riesgo": ""} for i in range(6)]
    assert len(CO.cambios_desde_propuestas(e, c, muchas, 3000)) == CO.MAX_PROPUESTAS_ARNES


def test_la_evaluacion_revierte_sola_lo_de_la_meta_campana_que_empeora_y_no_lo_de_una_persona():
    e, inv, c = _estado()
    rosa = P.nuevo_cambio_aprendizaje(inv, 2, "criterio", "Criterio de la meta-campaña", f"arnes:{c['id']}", "propuesto", "Rosa", 1)
    persona = P.nuevo_cambio_aprendizaje(inv, 2, "criterio", "Criterio de una persona", "debilidad:x", "propuesto", "Allegri", 1)
    e["aprendizaje"] += [rosa, persona]
    peor = {"conjunto": "reservado", "casos": 6, "antes": 0.8, "despues": 0.5, "nota": "Empeora el acuerdo"}
    assert CO._fijar_evaluacion(e, rosa["id"], dict(peor), 2000) is True
    assert rosa["estado"] == "revertido" and rosa["resueltoPor"] == "Rosa" and "Revertido por ROSA2018" in rosa["evaluacion"]["nota"]
    assert CO._fijar_evaluacion(e, persona["id"], dict(peor), 2000) is True
    assert persona["estado"] == "evaluado"  # la decide la persona; la puerta impedirá promoverla
    assert A.promover_aprendizaje(e, persona["id"], "Allegri", 3000) is False
    mejor = P.nuevo_cambio_aprendizaje(inv, 2, "criterio", "Criterio que mejora", f"arnes:{c['id']}", "propuesto", "Rosa", 1)
    e["aprendizaje"].append(mejor)
    assert CO._fijar_evaluacion(e, mejor["id"], {"conjunto": "reservado", "casos": 6, "antes": 0.5, "despues": 0.8, "nota": "Mejora"}, 2000) is True
    assert mejor["estado"] == "evaluado"
    assert A.promover_aprendizaje(e, mejor["id"], "Allegri", 3000) is True and "Criterio que mejora" in e["criteriosRevision"]
