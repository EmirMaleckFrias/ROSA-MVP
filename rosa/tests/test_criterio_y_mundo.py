"""Conocimiento y criterio separados (15 de septiembre de 2026): las preguntas
heredadas de otra investigación no deciden qué se lee; el modelo de mundo se
elige por parecido con el paso y etiqueta lo heredado con su origen."""
import asyncio
import tempfile
from pathlib import Path

from rosa import indice_semantico
from rosa.bucle import contexto as T
from rosa.bucle import pasos as PASOS
from rosa.bucle.pasos import Ctx
from rosa.estado.almacen import Almacen

OBJETIVO = "Determinar qué propiedad distingue a un biomarcador cuyo cambio bajo tratamiento predice beneficio clínico, comparando semaglutida en evoke/evoke+, posdinemab, AL002 en INVOKE-2, lecanemab y donanemab."


def _hecho(id_, inv, enunciado, estado="abierto", prioridad=1, tema="biomarcadores"):
    return {"id": id_, "investigacionId": inv, "enunciado": enunciado, "estado": estado, "prioridad": prioridad, "tipo": "pregunta" if estado == "abierto" else "dato", "tema": tema, "procedencia": [], "motivoDescarte": "Contradicho por Belder et al." if estado == "descartado" else None, "citas": [], "historial": [], "actualizadoEn": 0, "origen": "rosa"}


def _hechos():
    # he-1 nació en inv-A ("progresión en alzheimer"), se heredó a inv-B y de ahí a inv-C.
    return [
        _hecho("he-1", "inv-A", "¿Se mantiene la precedencia de GFAP sobre NfL en portadores de APOE ε4 amiloide positivos?"),
        _hecho("he-1-inv-B", "inv-B", "¿Se mantiene la precedencia de GFAP sobre NfL en portadores de APOE ε4 amiloide positivos?"),
        _hecho("he-1-inv-B-inv-C", "inv-C", "¿Se mantiene la precedencia de GFAP sobre NfL en portadores de APOE ε4 amiloide positivos?"),
        _hecho("he-2-inv-B-inv-C", "inv-C", "¿Qué predijo el cambio de amiloide bajo lecanemab en Clarity AD sobre el beneficio clínico?", prioridad=1),
        _hecho("he-3", "inv-C", "¿Qué desenlace clínico usó cada ensayo de posdinemab y AL002?", prioridad=2),
        _hecho("he-4", "inv-C", "En TRAILBLAZER-ALZ 2 la reducción de amiloide acompañó un menor declive en CDR-SB", estado="sabido", prioridad=2, tema="ensayos"),
        _hecho("he-5", "inv-C", "GFAP baja tras eliminar amiloide en toda cohorte", estado="descartado", prioridad=3, tema="biomarcadores"),
        _hecho("he-6-inv-B-inv-C", "inv-C", "Belder et al. midieron BACE1 en 113 portadores de mutaciones", estado="sabido", prioridad=1, tema="ADAD"),
    ]


INVESTIGACIONES = [{"id": "inv-A", "titulo": "progresión en alzheimer"}, {"id": "inv-B", "titulo": "La disociación entre biomarcador y clínica"}, {"id": "inv-C", "titulo": "Qué distingue a un biomarcador"}]


def test_el_criterio_empieza_por_el_objetivo_y_no_hereda_preguntas_ajenas():
    texto = T.preguntas_abiertas(_hechos(), "inv-C", OBJETIVO, pregunta="¿La caída de tau-PET anticipa el beneficio en CDR-SB?")
    lineas = texto.splitlines()
    assert lineas[0].startswith("Objetivo: Determinar qué propiedad") and lineas[1].startswith("Pregunta de esta corrida: ¿La caída de tau-PET")
    # Las propias van primero, por prioridad; la heredada de GFAP/APOE no entra porque no nombra nada del objetivo.
    assert "1. ¿Qué desenlace clínico usó cada ensayo de posdinemab y AL002?" in texto
    assert "precedencia de GFAP" not in texto
    # La heredada que nombra lecanemab (nombre propio del objetivo) sí entra, marcada.
    assert "lecanemab en Clarity AD sobre el beneficio clínico? (heredada)" in texto
    # Sin preguntas propias ni heredadas pertinentes, la cabecera sigue siendo el criterio.
    solo = T.preguntas_abiertas([_hechos()[2]], "inv-C", OBJETIVO)
    assert solo.startswith("Objetivo:") and solo.endswith("Sin preguntas abiertas propias todavía.")


def test_es_heredado_y_origen_siguen_la_cadena_de_copias():
    hs = _hechos()
    por_id = {h["id"]: h for h in hs}
    assert T.es_heredado(por_id["he-1-inv-B-inv-C"]) and not T.es_heredado(por_id["he-3"])
    assert T.origen_de_heredado(por_id["he-1-inv-B-inv-C"], por_id, INVESTIGACIONES) == "progresión en alzheimer"
    # Si la copia original ya no existe, no se inventa el origen.
    assert T.origen_de_heredado(por_id["he-2-inv-B-inv-C"], por_id, INVESTIGACIONES) is None


def test_modelo_de_mundo_por_prioridad_lleva_mapa_y_etiqueta_de_origen():
    texto = T.modelo_de_mundo(_hechos(), "inv-C", maximo=3, investigaciones=INVESTIGACIONES)
    assert texto.startswith("Mapa del modelo de mundo: 6 hechos (2 sabidos, 3 preguntas abiertas, 1 descartados).")
    assert "Heredados: 3 hechos vienen de" in texto and "«progresión en alzheimer» (1)" in texto and "«otra investigación» (2)" in texto
    assert "Hechos (3 de 6, por prioridad):" in texto
    assert "[heredado de «progresión en alzheimer»]" in texto
    assert texto.count("\n- ") == 3


def test_modelo_de_mundo_para_elige_por_parecido_y_cae_a_prioridad_sin_indice(monkeypatch):
    al = Almacen(Path(tempfile.mkdtemp()) / "t.db")
    try:
        def fn(e):
            e["hechos"] = _hechos()
            e["investigaciones"] = list(INVESTIGACIONES)
            return True
        al.mutar(fn, "test")
        # Sin índice (conftest apaga los embeddings): núcleo y después prioridad.
        texto = asyncio.run(T.modelo_de_mundo_para(al, "inv-C", "tau-PET y CDR-SB", maximo=4))
        assert "(4 de 6, por prioridad)" in texto
        assert "GFAP baja tras eliminar amiloide" in texto  # el descartado entra siempre (núcleo)
        # Con índice falso: lo parecido entra aunque tenga prioridad baja; el núcleo sigue.
        class IndiceFalso:
            async def buscar(self, texto, k, investigacion_id=None, tipos=None, **kw):
                assert investigacion_id == "inv-C" and tipos == ("hecho",)
                return [{"id": "hecho:he-4", "similitud": 0.9}, {"id": "hecho:he-6-inv-B-inv-C", "similitud": 0.5}, {"id": "hecho:he-1", "similitud": 0.4}]
        monkeypatch.setattr(indice_semantico, "disponible", lambda: True)
        monkeypatch.setattr(indice_semantico, "de_almacen", lambda a: IndiceFalso())
        texto = asyncio.run(T.modelo_de_mundo_para(al, "inv-C", "tau-PET y CDR-SB", maximo=5))
        assert "por parecido con este paso" in texto
        assert "TRAILBLAZER-ALZ 2" in texto and "Belder et al. midieron BACE1" in texto and "[heredado de" in texto
        assert "he-1" not in [l for l in texto.splitlines() if l.startswith("- ") and "inv-A" in l]  # un hecho de otra investigación nunca entra
        # Si el índice revienta, el paso sigue por prioridad.
        class IndiceRoto:
            async def buscar(self, *a, **kw):
                raise RuntimeError("sin red")
        monkeypatch.setattr(indice_semantico, "de_almacen", lambda a: IndiceRoto())
        texto = asyncio.run(T.modelo_de_mundo_para(al, "inv-C", "tau-PET", maximo=5))
        assert "por prioridad; el índice semántico no respondió (RuntimeError)" in texto
    finally:
        al.cerrar()


def test_terminos_registro_solo_nombres_y_siglas_en_ingles():
    terminos = T.terminos_registro("Comparar semaglutida en evoke/evoke+ con lecanemab", "¿Se mantiene la precedencia de GFAP sobre NfL en portadores?", "Ensayos de posdinemab", maximo=3)
    assert terminos and all(t.lower() not in ("mantiene", "precedencia", "portadores", "comparar") for t in terminos)
    assert any(t.lower().startswith("evoke") for t in terminos) and "lecanemab" in [t.lower() for t in terminos]
    assert T.terminos_registro("Determinar si mantiene la precedencia del marcador") == []


def test_los_pasos_usan_la_pregunta_de_la_corrida_en_el_criterio():
    al = Almacen(Path(tempfile.mkdtemp()) / "t.db")
    try:
        def fn(e):
            e["investigaciones"].append({"id": "inv-C", "titulo": "t", "objetivo": OBJETIVO})
            e["corridas"].append({"id": "cor-1", "investigacionId": "inv-C", "pregunta": {"enunciado": "¿La caída de tau-PET anticipa el beneficio?"}})
            e["hechos"] = _hechos()
            return True
        al.mutar(fn, "test")
        ctx = Ctx(al, None, None, "cor-1", "inv-C", "", 1)
        inv = ctx.inv()
        criterio = PASOS._criterio(ctx, inv)
        assert "Pregunta de esta corrida: ¿La caída de tau-PET" in criterio and "precedencia de GFAP" not in criterio
        assert PASOS._consulta_del_paso(ctx, inv, "extra").endswith("¿La caída de tau-PET anticipa el beneficio? extra")
    finally:
        al.cerrar()


def test_leer_modelo_de_mundo_usa_el_indice_si_lo_hay(monkeypatch):
    from rosa import herramientas as H

    estado = {"hechos": _hechos()}
    registro = []

    class IndiceFalso:
        async def buscar(self, texto, k, investigacion_id=None, tipos=None, **kw):
            return [{"id": "hecho:he-4", "similitud": 0.8}]

    monkeypatch.setattr(indice_semantico, "disponible", lambda: True)
    monkeypatch.setattr(indice_semantico, "de_almacen", lambda a: IndiceFalso())
    tools = {t.name: t for t in H.herramientas(estado, "inv-C", registro, almacen=object())}
    salida = asyncio.run(tools["leer_modelo_de_mundo"].func("qué pasó con el declive clínico al quitar amiloide"))
    assert "TRAILBLAZER-ALZ 2" in salida
    # Sin almacén: por texto, como antes.
    tools = {t.name: t for t in H.herramientas(estado, "inv-C", registro)}
    salida = asyncio.run(tools["leer_modelo_de_mundo"].func("BACE1"))
    assert "Belder et al." in salida
