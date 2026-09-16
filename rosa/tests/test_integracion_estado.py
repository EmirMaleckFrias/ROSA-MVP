"""Integración de los siete módulos del 16 de septiembre de 2026 en la capa de
estado: claves nuevas en la plantilla, migración de estados antiguos en el
almacén, contrato del experimento en el prerregistro, registro del programa al
subir un dataset, enmienda de lecturas y cifras de aprendizaje en la métrica.
Cada test intenta también romper el cambio (None, listas vacías, textos donde
se esperan diccionarios, estados sin las claves)."""

import json
import tempfile
from pathlib import Path

import pytest

from rosa import experimento as XP
from rosa import progreso as PROG
from rosa.estado import acciones as A
from rosa.estado import almacen as AL
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen


@pytest.fixture
def al():
    return Almacen(Path(tempfile.mkdtemp()) / "t.db")


def _inv(al, id_="inv-t"):
    assert al.aplicar("crearInvestigacion", {"datos": {"titulo": "T", "objetivo": "O", "condicionParada": "3 iteraciones"}, "id_": id_}) == id_
    return id_


def _hip(al, inv):
    return al.aplicar("proponerHipotesis", {"investigacion_id": inv, "datos": {"titulo": "H", "enunciado": "E", "biomarcador": "GFAP"}, "quien": "Yo"})


LECTURAS = [
    {"nombre": "GFAP en plasma", "tipo": "biomarcador", "queConfirma": "sube más del 20 %", "queRefuta": "no cambia o baja", "control": "vehículo", "unidad": "pg/mL"},
    {"nombre": "TREM2 soluble", "tipo": "compromiso_diana", "queConfirma": "baja más del 30 %", "queRefuta": "no baja", "control": "isotipo", "unidad": "ng/mL"},
]


def _experimento_solo_lecturas():
    """Un experimento del contrato nuevo: sin confirma ni refuta antiguos, sin
    ensayo, solo lecturas separadas."""
    return {"protocolo": "1. cultivar", "ensayo": "", "confirma": "", "refuta": "", "costeEstimado": "bajo", "laboratorio": None, "estado": "propuesto", "ficheroDatos": None, "analisisPedido": "", "lecturas": [dict(l) for l in LECTURAS], "sistema": {"tipo": "ipsc", "quePrueba": "microglía humana", "queNoRepresenta": "la barrera hematoencefálica"}, "propositoBiomarcador": None, "nivelDesenlace": None, "puenteAlBeneficio": ""}


# -- 1. Estado nuevo -----------------------------------------------------------


def test_estado_nuevo_trae_las_claves_de_los_siete_modulos():
    e = P.estado_inicial()
    assert e["datasetsPrograma"] == []
    h = P.nueva_hipotesis("inv", 1, 0)
    assert h["ruta"] is None and h["perfilDiana"] is None and h["alternativas"] == []
    # Los campos nuevos se pueden sobreescribir al construir, como los demás.
    assert P.nueva_hipotesis("inv", 1, 0, alternativas=[{"texto": "x"}])["alternativas"] == [{"texto": "x"}]


def test_crear_y_bifurcar_investigacion_traen_mapas_y_cifras(al):
    inv = _inv(al)
    i = next(x for x in al.estado["investigaciones"] if x["id"] == inv)
    assert i["mapaEnfermedad"] is None and i["mapaRuta"] is None and i["cifrasAprendizaje"] is None
    # Si el bucle ya escribió un mapa en el origen, la rama no lo hereda: se recalcula con sus hechos.
    al.mutar(lambda e: e["investigaciones"][0].update(mapaEnfermedad={"celdas": [], "fecha": 1}) or True)
    rama = al.aplicar("bifurcarInvestigacion", {"investigacion_id": inv, "motivo": "rama"})
    r = next(x for x in al.estado["investigaciones"] if x["id"] == rama)
    assert r["mapaEnfermedad"] is None and r["mapaRuta"] is None and r["cifrasAprendizaje"] is None
    assert al.estado["investigaciones"][0]["mapaEnfermedad"] == {"celdas": [], "fecha": 1}


# -- 2. Estado antiguo pasa por la migración -----------------------------------


def test_estado_antiguo_sale_de_la_migracion_con_las_claves(al):
    inv = _inv(al)
    h = _hip(al, inv)
    al.aplicar("anadirDataset", {"investigacion_id": inv, "dataset": {"nombre": "OASIS-1"}})

    def envejecer(e):
        for x in e["hipotesis"]:
            for k in ("ruta", "perfilDiana", "alternativas"):
                x.pop(k, None)
        for i in e["investigaciones"]:
            for k in ("mapaEnfermedad", "mapaRuta", "cifrasAprendizaje"):
                i.pop(k, None)
        e.pop("datasetsPrograma", None)
        return True

    al.mutar(envejecer)
    guardado = json.loads(al._con.execute("SELECT json FROM estado WHERE clave='rosa'").fetchone()[0])
    assert "datasetsPrograma" not in guardado and "ruta" not in guardado["hipotesis"][0]
    al2 = Almacen(al.ruta)
    hip = next(x for x in al2.estado["hipotesis"] if x["id"] == h)
    assert hip["ruta"] is None and hip["perfilDiana"] is None and hip["alternativas"] == []
    i = next(x for x in al2.estado["investigaciones"] if x["id"] == inv)
    assert i["mapaEnfermedad"] is None and i["mapaRuta"] is None and i["cifrasAprendizaje"] is None
    assert al2.estado["datasetsPrograma"] == []
    # Y la instantánea que viaja al navegador las lleva (ninguna empieza por '_').
    assert "datasetsPrograma" in al2.instantanea() and "ruta" in al2.instantanea()["hipotesis"][0]


def test_migracion_no_pisa_lo_escrito_y_tolera_formas_raras():
    e = {
        "hipotesis": [{"id": "h1", "ruta": {"coherente": True}, "alternativas": "texto suelto"}, None, "basura"],
        "investigaciones": [{"id": "inv", "cifrasAprendizaje": {"texto": "x"}}, 7],
        "datasetsPrograma": "no es lista",
    }
    AL._migrar_siete_modulos(e)
    assert e["hipotesis"][0]["ruta"] == {"coherente": True}  # idempotente: no se pisa
    assert e["hipotesis"][0]["alternativas"] == []  # un texto no es una lista de alternativas
    assert e["hipotesis"][0]["perfilDiana"] is None
    assert e["investigaciones"][0]["cifrasAprendizaje"] == {"texto": "x"} and e["investigaciones"][0]["mapaRuta"] is None
    assert e["datasetsPrograma"] == []
    AL._migrar_siete_modulos({})  # un estado vacío tampoco rompe


# -- 3. Prerregistro con el contrato del experimento ----------------------------


def _h_para_prerregistro(experimento):
    return {"id": "h1", "investigacionId": "inv", "titulo": "t", "enunciado": "e", "mecanismo": "m", "iteracion": 1, "version": 1, "creadaEn": 1000, "comprobacion": {"biomarcador": "GFAP", "cohorte": "c", "diseno": "d"}, "experimento": experimento, "procedencia": {"registro": []}}


def test_texto_prerregistro_incluye_las_lecturas_cuando_las_hay_y_no_rompe_sin_ellas():
    con = A.texto_prerregistro(_h_para_prerregistro(_experimento_solo_lecturas()), "Lab", 1000, None)
    assert "## Lecturas fijadas de antemano (contrato del experimento)" in con
    assert "GFAP en plasma [biomarcador, pg/mL]: confirma si sube más del 20 %; refuta si no cambia o baja; control: vehículo" in con
    assert "Hash SHA-256 de las lecturas en orden canónico:" in con
    assert "Sistema experimental: " in con and "Propósito del biomarcador (BEST): no declarado" in con
    # El bloque va después del ensayo y antes del coste, como en el enganche.
    assert con.index("## Ensayo y criterios fijados de antemano") < con.index("## Lecturas fijadas de antemano") < con.index("## Coste estimado")
    antiguo = {"protocolo": "p", "ensayo": "GFAP por ELISA", "confirma": "sube", "refuta": "baja", "costeEstimado": "bajo", "analisisPedido": ""}
    sin = A.texto_prerregistro(_h_para_prerregistro(antiguo), "Lab", 1000, None)
    # Un registro antiguo produce una sola lectura derivada del ensayo: el bloque también se escribe y lo dice.
    assert "GFAP por ELISA [biomarcador]: confirma si sube; refuta si baja" in sin
    vacio = {"protocolo": "p", "ensayo": "", "confirma": "", "refuta": "", "costeEstimado": "bajo", "analisisPedido": "", "lecturas": None, "sistema": "no es un dict"}
    texto = A.texto_prerregistro(_h_para_prerregistro(vacio), "Lab", 1000, None)
    assert "## Coste estimado" in texto  # no lanza con lecturas None ni sistema como texto


def test_asignar_experimento_acepta_solo_lecturas_separadas_y_congela_su_hash():
    h = _h_para_prerregistro(_experimento_solo_lecturas())
    e = {"hipotesis": [h], "corridas": [], "artefactos": [], "eventos": [], "investigaciones": [{"id": "inv"}], "decisiones": []}
    assert A.asignar_experimento(e, "h1", "Lab X", 2000) is True
    x = h["experimento"]
    assert x["prerregistradoEn"] == 2000 and x["hashLecturas"] == XP.hash_lecturas(x) and len(x["hashLecturas"]) == 64
    contenido = e["artefactos"][0]["versiones"][0]["contenido"]
    assert x["hashLecturas"] in contenido
    # Lecturas sin el par completo (falta el criterio de refutación) no bastan.
    x2 = _experimento_solo_lecturas()
    for l in x2["lecturas"]:
        l["queRefuta"] = ""
    h2 = _h_para_prerregistro(x2)
    e2 = {"hipotesis": [h2], "corridas": [], "artefactos": [], "eventos": [], "investigaciones": [{"id": "inv"}]}
    assert A.asignar_experimento(e2, "h1", "Lab X", 2000) is False
    assert e2["eventos"][-1]["tipo"] == "incidencia"
    # Un registro antiguo con criterios antiguos sigue prerregistrándose y no lleva hashLecturas si no hay lecturas.
    x3 = {"protocolo": "p", "ensayo": "", "confirma": "sube", "refuta": "baja", "costeEstimado": "bajo", "analisisPedido": "", "estado": "propuesto"}
    h3 = _h_para_prerregistro(x3)
    e3 = {"hipotesis": [h3], "corridas": [], "artefactos": [], "eventos": [], "investigaciones": [{"id": "inv"}]}
    assert A.asignar_experimento(e3, "h1", "Lab X", 2000) is True
    # Con confirma/refuta antiguos normalizar_contrato deriva una lectura, así que hay hash: sirve para detectar enmiendas.
    assert h3["experimento"]["hashLecturas"] == XP.hash_lecturas(h3["experimento"])
    x4 = {"protocolo": "p", "ensayo": "", "confirma": "", "refuta": "", "costeEstimado": "bajo", "analisisPedido": "", "estado": "propuesto", "lecturas": "texto suelto"}
    e4 = {"hipotesis": [_h_para_prerregistro(x4)], "corridas": [], "artefactos": [], "eventos": [], "investigaciones": [{"id": "inv"}]}
    assert A.asignar_experimento(e4, "h1", "Lab X", 2000) is False  # lecturas como texto no son lecturas


# -- 4. Registro del programa al subir un dataset --------------------------------


def test_anadir_dataset_deja_registro_manual_en_el_programa(al):
    inv = _inv(al)
    ds = al.aplicar("anadirDataset", {"investigacion_id": inv, "dataset": {"nombre": "OASIS-1 volúmenes", "descripcion": "nWBV por CDR", "procedencia": {"origen": "OASIS-1", "hash": "abcdef0123456789", "fichero": "oasis1.csv", "filas": 416, "acceso": "abierto", "cohorte": "OASIS"}}})
    assert ds
    reg = al.estado["datasetsPrograma"]
    assert len(reg) == 1 and reg[0]["fuente"] == "manual" and reg[0]["accession"] == "OASIS-1" and inv in reg[0]["usadoEn"]
    # Completar la procedencia funde con el mismo registro (misma fuente y accession), no crea otro.
    assert al.aplicar("actualizarProcedenciaDataset", {"investigacion_id": inv, "dataset_id": ds, "procedencia": {"origen": "OASIS-1", "licencia": "OASIS Data Use Terms", "acceso": "colaboracion"}}) is True
    reg = al.estado["datasetsPrograma"]
    assert len(reg) == 1 and reg[0]["acceso"] == "controlado" and reg[0]["licencia"] == "OASIS Data Use Terms"
    # Un dataset sin procedencia también se registra (accession derivada del título) y el estado viaja al navegador.
    assert al.aplicar("anadirDataset", {"investigacion_id": inv, "dataset": {"nombre": "Datos del laboratorio", "procedencia": None}})
    assert len(al.estado["datasetsPrograma"]) == 2 and len(al.instantanea()["datasetsPrograma"]) == 2


def test_el_registro_del_programa_nunca_rompe_la_accion(al, monkeypatch):
    inv = _inv(al)

    def explota(*a, **k):
        raise RuntimeError("registro roto")

    monkeypatch.setattr(A.DP, "desde_dataset_subido", explota)
    ds = al.aplicar("anadirDataset", {"investigacion_id": inv, "dataset": {"nombre": "Propio"}})
    assert ds and al.estado["investigaciones"][0]["datasets"][0]["id"] == ds
    assert al.estado["datasetsPrograma"] == []
    assert any(ev["tipo"] == "incidencia" and "registro del programa" in ev["texto"] for ev in al.estado["eventos"])
    assert al.aplicar("actualizarProcedenciaDataset", {"investigacion_id": inv, "dataset_id": ds, "procedencia": {"origen": "x"}}) is True
    # Un estado mínimo sin 'eventos' tampoco rompe: el aviso se traga y la acción vale.
    e = {"investigaciones": [{"id": "inv", "datasets": []}]}
    assert A.anadir_dataset(e, "inv", {"nombre": "n"}, id_="ds-1") == "ds-1"


# -- 5. Enmienda de lecturas ------------------------------------------------------


def test_enmendar_lectura_respeta_la_regla_del_prerregistro(al):
    inv = _inv(al)
    h = _hip(al, inv)
    al.mutar(lambda e: next(x for x in e["hipotesis"] if x["id"] == h).update(experimento=_experimento_solo_lecturas()) or True)
    args = {"hipotesis_id": h, "indice": 0, "campo": "queConfirma", "despues": "sube más del 25 %", "motivo": "el ELISA nuevo tiene otro rango", "quien": "Allegri"}
    # Sin prerregistro no hay nada que enmendar: se edita.
    assert al.aplicar("enmendarLectura", args) is False
    assert al.aplicar("asignarExperimento", {"hipotesis_id": h, "laboratorio": "Lab"}) is True
    hip = lambda: next(x for x in al.estado["hipotesis"] if x["id"] == h)  # noqa: E731
    hash_congelado = hip()["experimento"]["hashLecturas"]
    assert al.aplicar("enmendarLectura", args) is True
    x = hip()["experimento"]
    assert x["lecturas"][0]["queConfirma"] == "sube más del 25 %"
    en = x["enmiendas"][-1]
    assert en["campo"] == "lecturas[0].queConfirma" and en["lectura"] == "GFAP en plasma" and en["antes"] == "sube más del 20 %" and en["despues"] == "sube más del 25 %"
    assert en["hashAntes"] == hash_congelado and en["hashDespues"] == x["hashLecturas"] != hash_congelado
    assert any("enmienda 1 del prerregistro por Allegri: lectura «GFAP en plasma», queConfirma" in r for r in hip()["procedencia"]["registro"])
    # Misma cosa otra vez: sin cambio, no cuenta. Sin motivo, tampoco.
    assert al.aplicar("enmendarLectura", args) is False
    assert al.aplicar("enmendarLectura", {**args, "despues": "otra", "motivo": "  "}) is False
    # Campo fuera de la lista (nombre, tipo, inventado), índice fuera, índice bool, índice como texto.
    for malo in ({"campo": "nombre"}, {"campo": "tipo"}, {"campo": "queNoExiste"}, {"indice": 2}, {"indice": -1}, {"indice": True}, {"indice": "0"}):
        assert al.aplicar("enmendarLectura", {**args, "despues": "otra", **malo}) is False, malo
    # Otros campos sí: unidad y control.
    assert al.aplicar("enmendarLectura", {**args, "indice": 1, "campo": "unidad", "despues": "pg/mL"}) is True
    assert al.aplicar("enmendarLectura", {**args, "indice": 1, "campo": "control", "despues": "IgG isotipo"}) is True
    assert len(hip()["experimento"]["enmiendas"]) == 3
    # Con resultado evaluado los criterios ya se aplicaron: no se enmienda.
    al.mutar(lambda e: hip()["experimento"].update(resultado={"veredicto": "confirma"}) or True)
    assert al.aplicar("enmendarLectura", {**args, "despues": "otra cosa"}) is False


def test_enmendar_lectura_con_formas_rotas_devuelve_false_sin_lanzar():
    base = {"prerregistradoEn": 1, "lecturas": [dict(LECTURAS[0])]}
    casos = [
        {"id": "h1", "investigacionId": "inv", "titulo": "t", "experimento": None},
        {"id": "h1", "investigacionId": "inv", "titulo": "t", "experimento": "texto"},
        {"id": "h1", "investigacionId": "inv", "titulo": "t", "experimento": {"prerregistradoEn": 1, "lecturas": None}},
        {"id": "h1", "investigacionId": "inv", "titulo": "t", "experimento": {"prerregistradoEn": 1, "lecturas": "texto"}},
        {"id": "h1", "investigacionId": "inv", "titulo": "t", "experimento": {"prerregistradoEn": 1, "lecturas": []}},
        {"id": "h1", "investigacionId": "inv", "titulo": "t", "experimento": {"prerregistradoEn": 1, "lecturas": ["no es dict"]}},
        {"id": "h1", "investigacionId": "inv", "titulo": "t", "experimento": {"prerregistradoEn": None, "lecturas": [dict(LECTURAS[0])]}},
    ]
    for h in casos:
        e = {"hipotesis": [h], "eventos": []}
        assert A.enmendar_lectura(e, "h1", 0, "queConfirma", "x", "m", "q", 5) is False, h
    assert A.enmendar_lectura({"hipotesis": [], "eventos": []}, "h1", 0, "queConfirma", "x", "m", "q", 5) is False
    # Procedencia como texto: la enmienda vale, y el registro de procedencia se salta sin lanzar.
    h = {"id": "h1", "investigacionId": "inv", "titulo": "t", "experimento": dict(base, lecturas=[dict(LECTURAS[0])]), "procedencia": "texto"}
    e = {"hipotesis": [h], "eventos": []}
    assert A.enmendar_lectura(e, "h1", 0, "queRefuta", "no sube", "motivo", "", 5) is True
    assert h["experimento"]["enmiendas"][0]["quien"] == "persona" and h["procedencia"] == "texto"
    # despues y motivo None no lanzan.
    assert A.enmendar_lectura(e, "h1", 0, "queRefuta", None, None, "q", 5) is False


def test_enmendar_lectura_esta_en_la_tabla_de_acciones_con_ahora_del_servidor():
    fn, con_ahora = AL.ACCIONES["enmendarLectura"]
    assert fn is A.enmendar_lectura and con_ahora is True


# -- 6. Cifras de aprendizaje en la métrica de progreso ---------------------------


def test_metrica_lee_las_cifras_de_aprendizaje_de_la_investigacion_sin_calcularlas():
    c = {"id": "cor", "investigacionId": "inv", "gasto": {"usd": 1.0, "llamadas": 4}, "progreso": [{"peldanosSubidos": 2, "peldanosBajados": 0, "hechosNuevos": 1, "hipotesisNuevas": 0, "fallidos": {}, "certezas": []}]}
    e = {"corridas": [c], "investigaciones": [{"id": "inv"}], "hipotesis": [], "iteraciones": []}
    m = PROG.metrica_de_corrida(e, "cor")
    assert m["aprendizaje"] is None  # sin cifras todavía
    assert "acierto" not in PROG.resumen_metrica(m)
    cifras = {"investigacionId": "inv", "fecha": 1, "acierto": {"casos": 3, "conDireccion": 2, "aciertos": 1, "tasa": 0.5, "sinDireccion": 1, "noEvaluables": 0}, "tiempo": {"casos": 1, "medianaHoras": 12.0}, "reutilizacion": {"heredados": 4, "reutilizados": 1}, "glosario": {}, "texto": "..."}
    e["investigaciones"][0]["cifrasAprendizaje"] = cifras
    m = PROG.metrica_de_corrida(e, "cor")
    assert m["aprendizaje"] == {"acierto": cifras["acierto"], "tiempo": cifras["tiempo"], "reutilizacion": cifras["reutilizacion"]}
    assert PROG.resumen_metrica(m).endswith("acertó 1 de 2 predicciones prerregistradas (50 %)")
    # Sin tasa (ninguna predicción con dirección evaluada) la línea se calla: nunca '0 %'.
    e["investigaciones"][0]["cifrasAprendizaje"]["acierto"]["tasa"] = None
    assert "acierto" not in PROG.resumen_metrica(PROG.metrica_de_corrida(e, "cor"))
    # Formas rotas: cifras como texto, acierto como texto, investigación ausente, estado sin 'investigaciones'.
    e["investigaciones"][0]["cifrasAprendizaje"] = "texto"
    assert PROG.metrica_de_corrida(e, "cor")["aprendizaje"] is None
    e["investigaciones"][0]["cifrasAprendizaje"] = {"acierto": "texto", "tiempo": None}
    assert PROG.metrica_de_corrida(e, "cor")["aprendizaje"] == {"acierto": None, "tiempo": None, "reutilizacion": None}
    assert PROG.aprendizaje_de({"investigaciones": [None, 3]}, "inv") is None and PROG.aprendizaje_de({}, "inv") is None
    assert PROG.resumen_metrica({"peldanosNetos": 0, "iteraciones": 1, "aprendizaje": "texto"}) == "subió 0 peldaños netos de certeza en 1 iteración"


# -- 7. Adversario: lo que el informe del integrador no cubría -------------------


def test_migracion_tolera_listas_que_no_son_listas():
    """Un rosa.db corrupto con 'hipotesis': None o 'investigaciones' como texto
    no debe tumbar el arranque del servidor por esta migración."""
    e = {"hipotesis": None, "investigaciones": "texto", "datasetsPrograma": None}
    AL._migrar_siete_modulos(e)
    assert e["datasetsPrograma"] == [] and e["hipotesis"] is None and e["investigaciones"] == "texto"


def test_frase_de_acierto_no_lanza_con_cifras_rotas_y_se_lee_en_llano():
    base = {"peldanosNetos": 0, "iteraciones": 1}
    # NaN e infinito no se pueden redondear: antes lanzaban ValueError y OverflowError.
    for tasa in (float("nan"), float("inf"), float("-inf"), "0.5", True, None):
        assert "predic" not in PROG.resumen_metrica({**base, "aprendizaje": {"acierto": {"tasa": tasa, "aciertos": 1, "conDireccion": 2}}}), tasa
    # Recuentos ausentes: se da el porcentaje sin inventar "None de None".
    frase = PROG.resumen_metrica({**base, "aprendizaje": {"acierto": {"tasa": 0.5, "aciertos": None, "conDireccion": None}}})
    assert frase.endswith("acierto de las predicciones prerregistradas: 50 %") and "None" not in frase
    # Singular y plural correctos, y el término explicado en la docstring de frase_acierto.
    assert PROG.frase_acierto({"acierto": {"tasa": 1.0, "aciertos": 1, "conDireccion": 1}}) == "acertó 1 de 1 predicción prerregistrada (100 %)"
    assert PROG.frase_acierto({"acierto": {"tasa": 0.0, "aciertos": 0, "conDireccion": 3}}) == "acertó 0 de 3 predicciones prerregistradas (0 %)"
    assert PROG.frase_acierto("texto") == "" and PROG.frase_acierto({"acierto": None}) == "" and PROG.frase_acierto(None) == ""


def _prerregistrado_antiguo():
    """Un experimento antiguo (solo ensayo y par confirma/refuta) ya prerregistrado
    por asignar_experimento, con el hash de la lectura derivada congelado."""
    x = {"protocolo": "p", "ensayo": "GFAP por ELISA", "confirma": "sube más del 20 %", "refuta": "no cambia", "costeEstimado": "bajo", "analisisPedido": "", "estado": "propuesto"}
    h = _h_para_prerregistro(x)
    e = {"hipotesis": [h], "corridas": [], "artefactos": [], "eventos": [], "investigaciones": [{"id": "inv"}]}
    assert A.asignar_experimento(e, "h1", "Lab", 2000) is True
    return e, h, x


def test_enmendar_experimento_recalcula_el_hash_de_la_lectura_derivada():
    """El hash congelado se calcula sobre la lectura derivada de confirma/refuta:
    enmendar 'confirma' con la acción antigua la cambia y el hash quedaba viejo
    en silencio. Ahora se recalcula y la enmienda guarda el anterior y el nuevo."""
    e, h, x = _prerregistrado_antiguo()
    congelado = x["hashLecturas"]
    assert A.enmendar_experimento(e, "h1", "confirma", "sube más del 30 %", "otro rango del ELISA", "Allegri", 3000) is True
    assert x["hashLecturas"] == XP.hash_lecturas(x) != congelado
    en = x["enmiendas"][-1]
    assert en["hashAntes"] == congelado and en["hashDespues"] == x["hashLecturas"] and en["quien"] == "Allegri"
    # Un campo que no entra en la lectura (protocolo) no toca el hash ni anota hashes.
    assert A.enmendar_experimento(e, "h1", "protocolo", "2. incubar", "paso que faltaba", "Allegri", 3100) is True
    assert "hashAntes" not in x["enmiendas"][-1] and x["hashLecturas"] == XP.hash_lecturas(x)
    # Un prerregistro anterior a los hashes no lo inventa: el artefacto congelado no lo lleva.
    x.pop("hashLecturas")
    assert A.enmendar_experimento(e, "h1", "refuta", "baja", "criterio invertido", "Allegri", 3200) is True
    assert "hashLecturas" not in x and "hashAntes" not in x["enmiendas"][-1]


def test_enmendar_con_quien_none_titulo_none_y_procedencia_rota_no_lanza():
    e, h, x = _prerregistrado_antiguo()
    h["titulo"] = None
    h["procedencia"] = "texto"
    assert A.enmendar_experimento(e, "h1", "confirma", "sube", "motivo", None, 3000) is True
    assert x["enmiendas"][-1]["quien"] == "persona" and h["procedencia"] == "texto"
    assert e["eventos"][-1]["tipo"] == "hipotesis_decidida"
    # despues o motivo None: no se enmienda, no se lanza.
    assert A.enmendar_experimento(e, "h1", "confirma", None, "motivo", "q", 3000) is False
    assert A.enmendar_experimento(e, "h1", "confirma", "otro", None, "q", 3000) is False
    # Lo mismo en enmendar_lectura: 'por None' no aparece en el registro.
    h2 = _h_para_prerregistro(_experimento_solo_lecturas())
    h2["titulo"] = None
    e2 = {"hipotesis": [h2], "corridas": [], "artefactos": [], "eventos": [], "investigaciones": [{"id": "inv"}]}
    assert A.asignar_experimento(e2, "h1", "Lab", 2000) is True
    assert A.enmendar_lectura(e2, "h1", 0, "unidad", "ng/mL", "unidad corregida", None, 3000) is True
    assert h2["experimento"]["enmiendas"][-1]["quien"] == "persona"
    assert all("por None" not in r for r in h2["procedencia"]["registro"]) and any("por persona" in r for r in h2["procedencia"]["registro"])


def test_flujo_real_de_subida_no_duplica_el_registro_del_programa(al):
    """El servidor sube el fichero con hash y sin origen (accession sha256:...);
    la persona escribe el origen después. Antes eso abría un segundo registro
    del mismo fichero; ahora el registro existente pasa a la accession nueva."""
    inv = _inv(al)
    proc = {**P.procedencia_dataset_vacia(), "hash": "abc123def4567890abcdef", "fichero": "oasis.csv", "filas": 100}
    ds = al.aplicar("anadirDataset", {"investigacion_id": inv, "dataset": {"nombre": "OASIS volúmenes", "procedencia": proc}})
    reg = al.estado["datasetsPrograma"]
    assert len(reg) == 1 and reg[0]["accession"] == "sha256:abc123def456"
    id_registro = reg[0]["id"]
    assert al.estado["investigaciones"][0]["datasets"][0]["registroProgramaId"] == id_registro
    assert al.aplicar("actualizarProcedenciaDataset", {"investigacion_id": inv, "dataset_id": ds, "procedencia": {"origen": "OASIS-1", "acceso": "abierto"}}) is True
    reg = al.estado["datasetsPrograma"]
    # El acceso lo decide rosa/datasets_programa.py: el texto nombra OASIS (registro
    # gratuito) y el más restrictivo gana sobre el 'abierto' declarado.
    assert len(reg) == 1 and reg[0]["accession"] == "OASIS-1" and reg[0]["id"] == id_registro and reg[0]["acceso"] == "registro"
    assert any("la accession pasa de sha256:abc123def456 a OASIS-1" in l for l in reg[0]["registro"])
    # Corregir el origen otra vez sigue siendo el mismo registro.
    assert al.aplicar("actualizarProcedenciaDataset", {"investigacion_id": inv, "dataset_id": ds, "procedencia": {"origen": "OASIS-2"}}) is True
    assert len(al.estado["datasetsPrograma"]) == 1 and al.estado["datasetsPrograma"][0]["accession"] == "OASIS-2"
    # Otro fichero distinto es otro registro; si después declara el mismo origen, se funden en uno.
    ds2 = al.aplicar("anadirDataset", {"investigacion_id": inv, "dataset": {"nombre": "OASIS otra tabla", "procedencia": {**P.procedencia_dataset_vacia(), "hash": "ffff0000ffff0000ffff"}}})
    assert len(al.estado["datasetsPrograma"]) == 2
    assert al.aplicar("actualizarProcedenciaDataset", {"investigacion_id": inv, "dataset_id": ds2, "procedencia": {"origen": "oasis-2"}}) is True
    assert len(al.estado["datasetsPrograma"]) == 1
    # Un dataset antiguo sin registroProgramaId (subido antes de este cambio) no rompe: se anota como pueda.
    al.mutar(lambda e: e["investigaciones"][0]["datasets"][0].pop("registroProgramaId") or True)
    assert al.aplicar("actualizarProcedenciaDataset", {"investigacion_id": inv, "dataset_id": ds, "procedencia": {"licencia": "libre"}}) is True
    # El id viaja al navegador con el dataset y sobrevive a la recarga del almacén.
    al2 = Almacen(al.ruta)
    assert al2.estado["investigaciones"][0]["datasets"][1]["registroProgramaId"] == al2.estado["datasetsPrograma"][0]["id"]


def test_realinear_tolera_registro_borrado_y_datasets_programa_roto():
    ds = {"registroProgramaId": "dsp-x", "procedencia": {"origen": "GSE1"}}
    A._realinear_registro_programa({"datasetsPrograma": "texto"}, ds)
    A._realinear_registro_programa({"datasetsPrograma": [None, {"id": "otro", "fuente": "manual", "accession": "a"}]}, ds)
    A._realinear_registro_programa({}, {"registroProgramaId": "dsp-x", "procedencia": "texto"})
    # Un registro de GEO con el mismo id no se toca: solo los manuales cambian de accession.
    e = {"datasetsPrograma": [{"id": "dsp-x", "fuente": "geo", "accession": "GSE9", "registro": []}]}
    A._realinear_registro_programa(e, ds)
    assert e["datasetsPrograma"][0]["accession"] == "GSE9"
