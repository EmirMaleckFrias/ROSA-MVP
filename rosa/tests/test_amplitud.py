"""Búsqueda en amplitud: una parte de las consultas explora fuera de la
pregunta (novedad del campo, temas adyacentes, sorpresa), se puntúa con otra
pregunta y un listón más bajo, y queda marcada en el registro y en las fuentes.
Sin red: bases y modelos simulados."""
import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

from rosa import politicas
from rosa.bucle import contexto as T
from rosa.bucle import pasos as PASOS
from rosa.bucle.pasos import Ctx
from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.estado.almacen import ACCIONES, Almacen
from rosa.fuentes import exa


def test_cuantas_de_amplitud_sigue_la_fraccion_elegida():
    assert PASOS.cuantas_de_amplitud(4, "enfocada") == 0
    assert PASOS.cuantas_de_amplitud(4, "equilibrada") == 2
    assert PASOS.cuantas_de_amplitud(4, "amplia") == 4
    assert PASOS.cuantas_de_amplitud(1, "equilibrada") == 1  # nunca cero si se pidió explorar
    assert PASOS.cuantas_de_amplitud(10, "amplia") == politicas.MAX_CONSULTAS_AMPLITUD
    assert PASOS.cuantas_de_amplitud(0, "amplia") == 0
    assert PASOS.amplitud_de({"configuracion": {}}) == "equilibrada"
    assert PASOS.amplitud_de({"configuracion": {"amplitud": "amplia"}}) == "amplia"
    assert PASOS.amplitud_de({"configuracion": {"amplitud": "todo"}}) == "equilibrada"


def test_la_novedad_del_campo_solo_con_exa_y_con_fecha(monkeypatch):
    inv = {"objetivo": "Qué distingue a un biomarcador que predice beneficio clínico"}
    monkeypatch.setattr(exa, "disponible", lambda: False)
    assert PASOS.consulta_novedad_del_campo(inv, 1_789_000_000_000) is None
    monkeypatch.setattr(exa, "disponible", lambda: True)
    q = PASOS.consulta_novedad_del_campo(inv, 1_789_000_000_000)
    assert q["base"] == "exa" and q["modo"] == "amplitud" and q["desde_fecha"] == "2026-03-14" and "beneficio clínico" in q["consulta"] and q["porque"]


def test_la_configuracion_lleva_amplitud_y_el_boton_la_cambia():
    e = {"investigaciones": [], "corridas": [], "hechos": [], "eventos": [], "hipotesis": []}
    iid = A.crear_investigacion(e, {"titulo": "t", "objetivo": "o", "condicionParada": "2 iteraciones", "configuracion": {"preferencias": "p", "amplitud": "cualquiera"}}, 1000)
    inv = e["investigaciones"][0]
    assert inv["id"] == iid and inv["configuracion"]["amplitud"] == "equilibrada"
    assert A.fijar_amplitud(e, iid, "amplia") is True and inv["configuracion"]["amplitud"] == "amplia"
    assert A.fijar_amplitud(e, iid, "todo") is False and inv["configuracion"]["amplitud"] == "amplia"
    # Guardar preferencias no borra la amplitud elegida; una amplitud inválida vuelve a la de por defecto.
    A.actualizar_configuracion(e, iid, {"preferencias": "x", "atributos": [], "restricciones": []})
    assert inv["configuracion"]["amplitud"] == "amplia"
    A.actualizar_configuracion(e, iid, {"preferencias": "x", "atributos": [], "restricciones": [], "amplitud": "rara"})
    assert inv["configuracion"]["amplitud"] == "equilibrada"
    assert "fijarAmplitud" in ACCIONES
    inv["limites"] = []
    assert "Amplitud de búsqueda: equilibrada (parte de las consultas que exploran fuera de la pregunta: 34 %)" in T.configuracion(inv)


class _Consulta:
    def __init__(self, **k):
        self.k = k

    def model_dump(self):
        return dict(self.k)


def _almacen(amplitud="equilibrada"):
    al = Almacen(Path(tempfile.mkdtemp()) / "t.db")

    def fn(e):
        e["investigaciones"].append({"id": "inv", "titulo": "t", "objetivo": "Qué distingue a un biomarcador que predice beneficio clínico", "limites": [], "condicionParada": "x", "configuracion": {"preferencias": "", "atributos": [], "restricciones": [], "amplitud": amplitud}, "vivero": []})
        c = P.nueva_corrida("inv", 1, 1000)
        c["id"] = "cor"
        e["corridas"].append(c)
        it = P.nueva_iteracion("cor", 1, 1000, [P.nuevo_paso("Buscar", "", 20)], 40)
        it["id"] = "it"
        e["iteraciones"].append(it)
        return True

    al.mutar(fn, "test")
    return al


def test_consultas_de_amplitud_mezclan_novedad_y_lo_que_escribe_el_cerebro(monkeypatch):
    al = _almacen()
    try:
        monkeypatch.setattr(exa, "disponible", lambda: True)
        llamadas = []

        async def llamar(self, rol, programa, **kw):
            assert rol == "cerebro" and programa == "explorar" and kw["cuantas"] == 2
            assert "Mapa del modelo de mundo" in kw["mapa_del_arbol"] or kw["mapa_del_arbol"].startswith("Modelo de mundo vacío")
            assert kw["pregunta_y_preguntas_abiertas"].startswith("Objetivo: Qué distingue")
            llamadas.append(kw)
            return SimpleNamespace(consultas=[
                _Consulta(base="pubmed", consulta="(neuroinflammation[tiab]) AND Alzheimer*[tiab]", tema="Inflamación, tema adyacente", modo="amplitud", porque="Podría tocar la hipótesis de GFAP"),
                _Consulta(base="pubmed", consulta="(neuroinflammation[tiab]) AND Alzheimer*[tiab]", tema="Repetida", modo="amplitud", porque=""),
                _Consulta(base="europepmc", consulta="\"ya hecha\"", tema="Ya hecha", modo="amplitud", porque=""),
                _Consulta(base="europepmc", consulta="synaptic loss AND Alzheimer", tema="Sinapsis", modo="foco", porque=""),
            ])

        monkeypatch.setattr(Ctx, "llamar", llamar)
        ctx = Ctx(al, SimpleNamespace(explorar="explorar"), None, "cor", "inv", "it", 1)
        inv = ctx.inv()
        salida = asyncio.run(PASOS._consultas_amplitud(ctx, inv, 3, ['"ya hecha"']))
        assert [q["tema"] for q in salida] == ["Novedad reciente del campo", "Inflamación, tema adyacente", "Sinapsis"]
        assert all(q["modo"] == "amplitud" for q in salida) and salida[2]["porque"] == "Explorar alrededor del objetivo"
        assert len(llamadas) == 1
        assert asyncio.run(PASOS._consultas_amplitud(ctx, inv, 0, [])) == []
    finally:
        al.cerrar()


def test_consulta_en_amplitud_puntua_con_otra_pregunta_y_marca_consulta_y_fuente(monkeypatch):
    al = _almacen()
    try:
        articulos = [
            {"referencia": "Diamante, 2026", "titulo": "Retinal vascular changes track amyloid burden", "resumen": "Retina and amyloid in a longitudinal cohort", "doi": None, "pmid": "1", "anio": 2026, "tipos": [], "autores": []},
            {"referencia": "Lejano, 2026", "titulo": "Zebrafish tau model", "resumen": "Zebrafish", "doi": None, "pmid": "2", "anio": 2026, "tipos": [], "autores": []},
        ]

        async def buscar_falso(consulta, maximo=10, solo_preprints=False):
            return articulos, 2

        async def fragmentos_falsos(ctx, datos, pista, con_texto):
            return [{"localizador": "resumen", "texto": datos.get("resumen", ""), "encabezado": ""}]

        monkeypatch.setattr(PASOS.europepmc, "buscar", buscar_falso)
        monkeypatch.setattr(PASOS, "_fragmentos_de", fragmentos_falsos)
        usados = []

        async def llamar(self, rol, programa, **kw):
            usados.append(programa)
            if programa == "relevancia_amplitud":
                assert "beneficio clínico" in kw["objetivo"] and "hipotesis_y_vivero" in kw
                return SimpleNamespace(puntuacion=4 if "Retinal" in kw["titulo"] else 2, motivo="por su relación con el objetivo", podria_cambiar="línea nueva sobre la retina")
            assert programa == "relevancia" and "preguntas_abiertas" in kw
            return SimpleNamespace(puntuacion=4, motivo="roza la pregunta")

        monkeypatch.setattr(Ctx, "llamar", llamar)
        ctx = Ctx(al, SimpleNamespace(relevancia_amplitud="relevancia_amplitud", relevancia="relevancia"), None, "cor", "inv", "it", 1)
        paso = ctx.iteracion()["plan"][0]
        q = {"base": "europepmc", "consulta": "retina AND Alzheimer", "tema": "Retina, tema adyacente", "modo": "amplitud", "porque": "Podría abrir una línea"}
        r = asyncio.run(PASOS._consulta_literatura(ctx, paso, q, "Objetivo: x"))
        assert r["identificados"] == 2 and r["cribados"] == 1 and r["leidos"] == 1
        c = ctx.corrida()
        reg = c["busqueda"]["consultas"][-1]
        assert reg["modo"] == "amplitud" and reg["porque"] == "Podría abrir una línea"
        fuentes = list(c["_fuentes"].values())
        assert len(fuentes) == 1 and fuentes[0]["modo"] == "amplitud" and fuentes[0]["relevancia"] == 4 and fuentes[0]["porque"] == "línea nueva sobre la retina"
        ex = c["busqueda"]["excluidos"][-1]
        assert ex["titulo"] == "Zebrafish tau model" and "Podría cambiar" in ex["motivo"] and ex["modo"] == "amplitud"
        assert set(usados) == {"relevancia_amplitud"}
        pista = [p for p in ctx.iteracion()["pistas"] if p["titulo"].startswith("Amplitud:")]
        assert pista and any("Búsqueda en amplitud. Por qué" in l.get("texto", "") for l in pista[0]["transcripcion"])
        # La exportación de la trazabilidad lleva el modo y el porqué de la fuente.
        ev = al.evidencia_de("cor")
        assert ev["fuentes"][0]["modo"] == "amplitud" and ev["fuentes"][0]["porque"] == "línea nueva sobre la retina"
        # Caso adversario: la misma fuente con puntuación 4 en foco no pasa el listón (5)...
        q_foco = {"base": "europepmc", "consulta": "retina AND Alzheimer 2", "tema": "Retina", "modo": "foco"}
        r2 = asyncio.run(PASOS._consulta_literatura(ctx, paso, q_foco, "Objetivo: x"))
        assert r2["cribados"] == 0 and "relevancia" in usados and fuentes[0]["modo"] == "amplitud"
        # ...pero si el foco la trae con 5 o más, la fuente deja de contar como hallazgo de amplitud.
        async def llamar_alto(self, rol, programa, **kw):
            return SimpleNamespace(puntuacion=6, motivo="responde a la pregunta")
        monkeypatch.setattr(Ctx, "llamar", llamar_alto)
        r3 = asyncio.run(PASOS._consulta_literatura(ctx, paso, dict(q_foco, consulta="retina AND Alzheimer 3"), "Objetivo: x"))
        assert r3["cribados"] == 2 and ctx.corrida()["_fuentes"][fuentes[0]["id"]]["modo"] == "foco"
        # El extractor ordena por margen sobre el listón de cada modo y recibe el porqué de las de amplitud.
        f_amp = {"modo": "amplitud", "relevancia": 4, "porque": "una segunda cohorte"}
        assert PASOS._liston_de(f_amp) == 4 and PASOS._liston_de({"relevancia": 5}) == 5
        assert "se conservó porque podría cambiar: una segunda cohorte" in PASOS._criterio_para_fuente("Objetivo: x", f_amp)
        assert PASOS._criterio_para_fuente("Objetivo: x", {"modo": "foco"}) == "Objetivo: x"
    finally:
        al.cerrar()
