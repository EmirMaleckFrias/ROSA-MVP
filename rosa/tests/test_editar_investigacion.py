"""Editar el título o el objetivo de una investigación ya creada (misma regla en
frontend/src/datos/acciones.ts). Nació el 18 de septiembre de 2026 para corregir
dos títulos sin tilde que se veían en la pantalla de Investigaciones."""
from rosa.estado import acciones as A
from rosa.estado import plantilla as P


def _estado():
    e = P.estado_inicial()
    A.crear_investigacion(e, {"titulo": "progresion en alzheimer", "objetivo": "Objetivo", "condicionParada": "1 hora"}, 1000, id_="inv-1")
    return e


def test_edita_titulo_y_objetivo_y_deja_evento():
    e = _estado()
    assert A.editar_investigacion(e, "inv-1", 2000, titulo="Progresión en Alzheimer", quien="Emir") is True
    inv = e["investigaciones"][0]
    assert inv["titulo"] == "Progresión en Alzheimer" and inv["objetivo"] == "Objetivo"
    ev = [x for x in e["eventos"] if x["tipo"] == "investigacion_editada"]
    assert len(ev) == 1 and "Emir editó" in ev[0]["texto"] and "Progresión en Alzheimer" in ev[0]["texto"]
    assert A.editar_investigacion(e, "inv-1", 3000, objetivo="  Objetivo nuevo  ") is True
    assert e["investigaciones"][0]["objetivo"] == "Objetivo nuevo"


def test_vacio_igual_o_inexistente_no_cambia_nada():
    e = _estado()
    assert A.editar_investigacion(e, "inv-1", 2000, titulo="   ") is False
    assert A.editar_investigacion(e, "inv-1", 2000, titulo="progresion en alzheimer") is False
    assert A.editar_investigacion(e, "inv-x", 2000, titulo="Otro") is False
    assert e["investigaciones"][0]["titulo"] == "progresion en alzheimer"
    assert not [x for x in e["eventos"] if x["tipo"] == "investigacion_editada"]
