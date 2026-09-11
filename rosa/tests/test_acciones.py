"""Las reglas del dominio en el servidor, las mismas que prueba vitest en el
frontend. Se prueban sobre un almacen con base temporal."""

import tempfile
from pathlib import Path

import pytest

from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen


@pytest.fixture
def al():
    return Almacen(Path(tempfile.mkdtemp()) / "t.db")


def _inv(al, id_="inv-t"):
    assert al.aplicar("crearInvestigacion", {"datos": {"titulo": "T", "objetivo": "O", "condicionParada": "3 iteraciones"}, "id_": id_}) == id_
    return id_


def test_crear_investigacion_exige_titulo_objetivo_y_parada(al):
    assert al.aplicar("crearInvestigacion", {"datos": {"titulo": "T", "objetivo": "", "condicionParada": "x"}}) is False
    assert al.aplicar("crearInvestigacion", {"datos": {"titulo": "T", "objetivo": "O", "condicionParada": ""}}) is False


def test_iniciar_corrida_una_sola_viva(al):
    inv = _inv(al)
    c = al.aplicar("iniciarCorrida", {"investigacion_id": inv})
    assert c and al.estado["corridas"][0]["estado"] == "esperando_plan"
    assert al.aplicar("iniciarCorrida", {"investigacion_id": inv}) is False
    al.aplicar("detenerCorrida", {"corrida_id": c, "motivo": "fin"})
    assert al.aplicar("iniciarCorrida", {"investigacion_id": inv})
    assert al.estado["corridas"][1]["numero"] == 2


def test_descartar_exige_motivo_y_aceptar_entra_como_abierto(al):
    inv = _inv(al)
    h = al.aplicar("proponerHipotesis", {"investigacion_id": inv, "datos": {"titulo": "H", "enunciado": "E", "biomarcador": "GFAP"}, "quien": "la persona responsable"})
    assert al.aplicar("revisarHipotesis", {"hipotesis_id": h, "accion": "descartar", "nota": "  ", "quien": "la persona responsable"}) is False
    assert al.aplicar("revisarHipotesis", {"hipotesis_id": h, "accion": "aceptar", "nota": "ok", "quien": "la persona responsable"}) is True
    hecho = next(x for x in al.estado["hechos"] if x["id"] == f"he-{h}")
    assert hecho["estado"] == "abierto" and hecho["tipo"] == "hipotesis"
    assert al.aplicar("revisarHipotesis", {"hipotesis_id": h, "accion": "descartar", "nota": "no", "quien": "la persona responsable"}) is True
    hecho = next(x for x in al.estado["hechos"] if x["id"] == f"he-{h}")
    assert hecho["estado"] == "descartado" and "no (la persona responsable)" == hecho["motivoDescarte"]


def test_plan_no_se_edita_tras_aprobar(al):
    inv = _inv(al)
    c = al.aplicar("iniciarCorrida", {"investigacion_id": inv})
    it = P.nueva_iteracion(c, 1, P.ahora_ms(), [P.nuevo_paso("a", "", 5)])
    al.mutar(lambda e: e["iteraciones"].append(it) or True)
    assert al.aplicar("editarPlan", {"iteracion_id": it["id"], "plan": [P.nuevo_paso("b", "", 5)]}) is True
    assert al.aplicar("aprobarPlan", {"iteracion_id": it["id"]}) is True
    assert al.estado["corridas"][0]["estado"] == "en_marcha"
    assert al.aplicar("editarPlan", {"iteracion_id": it["id"], "plan": [P.nuevo_paso("c", "", 5)]}) is False
    assert al.aplicar("aprobarPlan", {"iteracion_id": it["id"]}) is False


def test_permiso_con_alcance_amplio_queda_listado_y_se_revoca(al):
    inv = _inv(al)
    c = al.aplicar("iniciarCorrida", {"investigacion_id": inv})
    s = {"id": "sol-1", "corridaId": c, "tipo": "fuente_externa", "titulo": "t", "detalle": "", "recurso": "PubMed", "alcances": ["una_vez", "siempre"], "estado": "pendiente", "alcanceConcedido": None, "creadaEn": 0, "resueltaEn": None, "hipotesisId": None, "argumentos": []}
    al.mutar(lambda e: e["solicitudes"].append(s) or True)
    assert al.aplicar("resolverSolicitud", {"solicitud_id": "sol-1", "decision": "conceder", "alcance": "esta_corrida"}) is False
    assert al.aplicar("resolverSolicitud", {"solicitud_id": "sol-1", "decision": "conceder", "alcance": "siempre"}) is True
    assert len(al.estado["permisos"]) == 1 and al.estado["permisos"][0]["investigacionId"] is None
    assert al.aplicar("revocarPermiso", {"permiso_id": al.estado["permisos"][0]["id"]}) is True
    assert al.estado["permisos"] == []


def test_ampliar_presupuesto_reanuda(al):
    inv = _inv(al)
    c = al.aplicar("iniciarCorrida", {"investigacion_id": inv})
    al.mutar(lambda e: (e["corridas"][0].update(estado="pausada_por_presupuesto"), e["corridas"][0]["gasto"].update(llamadas=400)) and True)
    assert al.aplicar("ampliarPresupuesto", {"corrida_id": c, "nuevo_limite": 300}) is False
    assert al.aplicar("ampliarPresupuesto", {"corrida_id": c, "nuevo_limite": 800}) is True
    assert al.estado["corridas"][0]["estado"] == "en_marcha"


def test_comentarios_pendientes_salen_juntos(al):
    inv = _inv(al)
    h = al.aplicar("proponerHipotesis", {"investigacion_id": inv, "datos": {"titulo": "H", "enunciado": "E", "cohorte": "ADNI"}, "quien": "la persona responsable"})
    assert al.aplicar("anadirComentario", {"hipotesis_id": h, "ancla": {"cita": "E", "campo": "enunciado"}, "nota": "dudo"}) is True
    assert al.aplicar("anadirComentario", {"hipotesis_id": h, "ancla": {"cita": "", "campo": "enunciado"}, "nota": "x"}) is False
    assert al.aplicar("enviarComentarios", {"hipotesis_id": h, "mensaje": "", "quien": "la persona responsable"}) is True
    assert all(c["estado"] == "enviado" for c in al.estado["comentarios"])
    hip = al.estado["hipotesis"][0]
    assert hip["estado"] == "en_revision" and hip.get("_comentariosNuevos") is True
    assert "_comentariosNuevos" not in al.instantanea()["hipotesis"][0]


def test_persistencia_y_version(al):
    _inv(al)
    v = al.version
    al2 = Almacen(al.ruta)
    assert al2.version == v and len(al2.estado["investigaciones"]) == 1
    assert len(al2.estado["casos"]) == 17


def test_asignar_experimento_prerregistra_una_sola_vez(al):
    inv = _inv(al)
    al.aplicar("iniciarCorrida", {"investigacion_id": inv})
    h = al.aplicar("proponerHipotesis", {"investigacion_id": inv, "datos": {"titulo": "H", "enunciado": "E", "biomarcador": "GFAP"}, "quien": "Yo"})
    assert al.aplicar("asignarExperimento", {"hipotesis_id": h, "laboratorio": "Lab"}) is False  # sin experimento propuesto
    al.mutar(lambda e: next(x for x in e["hipotesis"] if x["id"] == h).update(experimento={"protocolo": "1. medir", "ensayo": "GFAP", "costeEstimado": "bajo", "laboratorio": None, "estado": "propuesto", "ficheroDatos": None, "analisisPedido": ""}) or True)
    assert al.aplicar("asignarExperimento", {"hipotesis_id": h, "laboratorio": "Lab"}) is True
    hip = next(x for x in al.estado["hipotesis"] if x["id"] == h)
    assert hip["experimento"]["estado"] == "asignado" and hip["experimento"]["prerregistradoEn"]
    arts = [a for a in al.estado["artefactos"] if a["nombre"].startswith("Prerregistro")]
    assert len(arts) == 1 and "no se modifica" in arts[0]["versiones"][0]["contenido"]
    assert "Commit" in arts[0]["versiones"][0]["contenido"]
    # Reasignar a otro laboratorio no crea otro prerregistro
    assert al.aplicar("asignarExperimento", {"hipotesis_id": h, "laboratorio": "Otro"}) is True
    assert len([a for a in al.estado["artefactos"] if a["nombre"].startswith("Prerregistro")]) == 1
    assert al.estado["corridas"][0]["arnes"]["commit"]
