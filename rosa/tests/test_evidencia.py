"""Acumulación de evidencia: lo leído después de nacer una hipótesis se le
suma (a favor, indirecto o en contra), su procedencia gana la fuente y la
cohorte, y el techo de certeza puede subir. Sin red: el modelo se simula."""
import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

from rosa import certeza as C
from rosa import indice_semantico
from rosa import priorizacion as PR
from rosa.bucle import evidencia as EV
from rosa.bucle.pasos import Ctx
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen


def _af(id_, texto, fuente, cohorte, iteracion=2, **k):
    return {"id": id_, "texto": texto, "cita": f"[{fuente}, resumen]", "fragmento": texto, "veredicto": "sostenida", "motivo": "", "entidadDistinta": False, "tipo": "dato", "clase": "literatura", "sintetico": False, "cohorte": cohorte, "sospechosoInyeccion": False, "nivelMedicion": "resultado_analisis", "fuenteId": fuente, "localizador": "resumen", "iteracion": iteracion, **k}


def _preparar():
    al = Almacen(Path(tempfile.mkdtemp()) / "t.db")

    def fn(e):
        e["investigaciones"].append({"id": "inv", "titulo": "t", "objetivo": "GFAP y NfL en portadores de APOE ε4"})
        e["corridas"].append({"id": "cor", "investigacionId": "inv", "estado": "en_marcha", "busqueda": {"consultas": []}, "gasto": {},
                              "_fuentes": {"xie": {"id": "xie", "referencia": "Xie et al., 2026", "titulo": "Plasma biomarkers in BIOCARD", "cohorte": "BIOCARD", "fragmentos": [], "relevancia": 8},
                                           "kim": {"id": "kim", "referencia": "Kim et al., 2025", "titulo": "Plasma GFAP in ADNI", "cohorte": "ADNI", "fragmentos": [], "relevancia": 7},
                                           "otro": {"id": "otro", "referencia": "Otro, 2024", "titulo": "Glioma GFAP", "cohorte": "", "fragmentos": []}},
                              "_afirmaciones": [
                                  _af("af-1", "En ADNI, GFAP en plasma se altera antes que NfL en portadores de APOE ε4 amiloide positivos", "kim", "ADNI"),
                                  _af("af-2", "En ADNI, NfL se altera antes que GFAP en portadores de APOE ε4", "kim", "ADNI"),
                                  _af("af-3", "GFAP sérica sube en glioma de alto grado", "otro", ""),
                                  _af("af-4", "GFAP precede a NfL en BIOCARD", "xie", "BIOCARD", iteracion=1),
                                  _af("af-5", "GFAP y NfL: otra entidad", "kim", "ADNI", entidadDistinta=True),
                              ]})
        h = P.nueva_hipotesis("inv", 1, 1000, titulo="Precedencia de GFAP sobre NfL en portadores de APOE ε4", enunciado="En portadores de APOE ε4 amiloide positivos, GFAP en plasma se altera antes que NfL",
                              mecanismo="astrocitos antes que axones", comprobacion={"biomarcador": "GFAP, NfL", "cohorte": "APOE ε4 A+", "diseno": "longitudinal"}, cluster="glia", relevancia={"justificacion": "", "votoHumano": None},
                              afirmaciones=[dict(_af("af-4", "GFAP precede a NfL en BIOCARD", "xie", "BIOCARD", iteracion=1), afirmacionId="af-4")], supuestos=[])
        h["procedencia"] = P.procedencia_vacia("nacida en la iteración 1", 1000)
        h["procedencia"]["fuentes"] = [{"id": "xie", "referencia": "Xie et al., 2026", "titulo": "Plasma biomarkers in BIOCARD", "cohorte": "BIOCARD"}]
        h["conclusion"] = {"certeza": "muy_baja"}
        h["_conclusionIntentada"] = 2
        e["hipotesis"].append(h)
        return True

    al.mutar(fn, "test")
    return al


class Rel:
    def __init__(self, indice, relacion, motivo="por población y sentido"):
        self.indice, self.relacion, self.motivo = indice, relacion, motivo


def _ctx(al, relaciones, llamadas, monkeypatch):
    async def llamar(self, rol, programa, **kw):
        assert rol == "volumen" and programa == "asignar_evidencia"
        llamadas.append(kw["afirmaciones"])
        return SimpleNamespace(relaciones=relaciones)

    monkeypatch.setattr(Ctx, "llamar", llamar)  # simulación local; el módulo real hace la llamada por el gateway
    return Ctx(al, SimpleNamespace(asignar_evidencia="asignar_evidencia"), None, "cor", "inv", "", 2)


def test_acumula_por_terminos_sin_embeddings_y_sube_el_techo(monkeypatch):
    al = _preparar()
    try:
        llamadas = []
        ctx = _ctx(al, [Rel(1, "apoya"), Rel(2, "contradice", "sentido contrario"), Rel(3, "no_pertinente")], llamadas, monkeypatch)
        r = asyncio.run(EV.acumular(ctx, 2))
        assert r["hipotesis"] == 1 and r["anadidas"] == 2 and r["enContra"] == 1 and len(r["ids"]) == 1
        # Las candidatas: af-1 y af-2 (nombran GFAP, NfL, APOE); af-3 (glioma, un solo término) y la de otra entidad no llegan al modelo; af-4 ya la tenía.
        assert "af-1" not in llamadas[0] and "glioma" not in llamadas[0] and "otra entidad" not in llamadas[0] and "1. [sostenida" in llamadas[0]
        h = al.estado["hipotesis"][0]
        nuevas = [a for a in h["afirmaciones"] if a.get("relacion")]
        assert {a["afirmacionId"] for a in nuevas} == {"af-1", "af-2"} and {a["relacion"] for a in nuevas} == {"apoya", "contradice"}
        assert all(a["iteracion"] == 2 and a["cita"] == "[kim, resumen]" and a["cohorte"] == "ADNI" for a in nuevas)
        # La fuente entra en la procedencia con su cohorte: dos cohortes distintas, techo baja.
        assert [f["id"] for f in h["procedencia"]["fuentes"]] == ["xie", "kim"] and PR.cohortes_de(h) == ["biocard", "adni"]
        assert C.techo(h)[0] == "baja"
        assert "_conclusionIntentada" not in h and h["_evidenciaNueva"] == 2
        assert any("2 afirmaciones nuevas enlazadas (1 a favor, 0 indirectas, 1 en contra), 1 fuentes nuevas" in x for x in h["procedencia"]["registro"])
        assert any(ev["tipo"] == "revision_automatica" and "1 en contra" in ev["texto"] for ev in al.estado["eventos"])
        # Segunda pasada: nada nuevo que enlazar (ya las tiene), ninguna llamada más.
        r2 = asyncio.run(EV.acumular(ctx, 2))
        assert r2["anadidas"] == 0 and len(llamadas) == 1
    finally:
        al.cerrar()


def test_con_embeddings_elige_por_parecido_y_sin_pertinentes_no_toca_nada(monkeypatch):
    al = _preparar()
    try:
        vectores = {"hip": [1.0, 0.0], "af-1": [0.9, 0.1], "af-2": [0.8, 0.2], "af-3": [0.0, 1.0], "af-5": [0.9, 0.1]}

        async def incrustar(textos):
            salida = []
            for t in textos:
                clave = "hip" if "Precedencia de GFAP" in t else "af-1" if "se altera antes que NfL" in t else "af-2" if "NfL se altera antes" in t else "af-3" if "glioma" in t else "af-5"
                salida.append(vectores[clave])
            return salida, 10

        monkeypatch.setattr(indice_semantico, "disponible", lambda: True)
        monkeypatch.setattr(indice_semantico, "incrustar", incrustar)
        llamadas = []
        ctx = _ctx(al, [Rel(1, "no_pertinente"), Rel(2, "no_pertinente")], llamadas, monkeypatch)
        r = asyncio.run(EV.acumular(ctx, 2))
        assert r["candidatas"] == 2 and r["anadidas"] == 0 and r["ids"] == []
        assert "glioma" not in llamadas[0]  # coseno 0 con la hipótesis: fuera del umbral
        h = al.estado["hipotesis"][0]
        assert len(h["afirmaciones"]) == 1 and h.get("_conclusionIntentada") == 2  # nada cambió, la conclusión no se rehace
    finally:
        al.cerrar()


def test_afirmaciones_nuevas_filtra_lo_que_no_es_evidencia():
    c = {"_afirmaciones": [_af("a", "x", "f", ""), _af("b", "x", "f", "", veredicto="cita_no_resuelve"), _af("c", "x", "f", "", entidadDistinta=True), _af("d", "x", "f", "", sospechosoInyeccion=True), _af("e", "x", "f", "", iteracion=1), _af("g", "x", "f", "", sintetico=True)]}
    assert [a["id"] for a in EV.afirmaciones_nuevas(c, 2)] == ["a"]
