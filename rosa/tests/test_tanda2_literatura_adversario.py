"""Adversario del constructor "literatura" (tanda 2 de la revisión del 17 de
septiembre de 2026: S-07, S-06 c a g, S-26, M-08 en pasos.py).

Cada test de este fichero reproduce un fallo del cambio tal como quedó en el
árbol de trabajo el 18 de septiembre de 2026. Los que llevan "FALLA HOY" en el
docstring fallan a propósito con el código actual y describen el comportamiento
que debería tener; el que cierre el hallazgo los deja pasando. Sin red ni
modelos: bases, Crossref y programas simulados con dobles, como en los tests del
constructor."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

from rosa import cuestiones as CU
from rosa import ontologias as ONTO
from rosa import politicas
from rosa.bucle import contexto as T
from rosa.bucle import pasos as PASOS
from rosa.bucle.pasos import Ctx
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen

OBJETIVO = "Qué predice el beneficio clínico de lecanemab en Alzheimer temprano, con GFAP y NfL en plasma"


# ---------------------------------------------------------------------------
# Arnés (el mismo patrón que rosa/tests/test_tanda2_literatura.py)
# ---------------------------------------------------------------------------


def _almacen(excluidos_previos: list | None = None, fuentes_previas: dict | None = None, afirmaciones_previas: list | None = None, con_previa: bool = True):
    """Una investigación con una corrida anterior (número 1, terminada, con sus
    excluidos, sus `_fuentes` y sus `_afirmaciones` privadas) y la corrida en
    curso (número 2)."""
    al = Almacen(Path(tempfile.mkdtemp()) / "t.db")

    def fn(e):
        e["investigaciones"].append({"id": "inv", "titulo": "t", "objetivo": OBJETIVO, "limites": [], "condicionParada": "x", "configuracion": {"preferencias": "", "atributos": [], "restricciones": [], "amplitud": "enfocada"}, "vivero": []})
        if con_previa:
            c1 = P.nueva_corrida("inv", 1, 500)
            c1["id"] = "cor1"
            c1["estado"] = "terminada"
            c1["busqueda"]["excluidos"] = list(excluidos_previos or [])
            if fuentes_previas:
                c1["_fuentes"] = fuentes_previas
            if afirmaciones_previas:
                c1["_afirmaciones"] = list(afirmaciones_previas)
            e["corridas"].append(c1)
        c = P.nueva_corrida("inv", 2, 1000)
        c["id"] = "cor"
        c["estado"] = "en_marcha"
        e["corridas"].append(c)
        it = P.nueva_iteracion("cor", 1, 1000, [P.nuevo_paso("Buscar", "", 20)], 40)
        it["id"] = "it"
        e["iteraciones"].append(it)
        return True

    al.mutar(fn, "test")
    return al


def _ctx(al):
    programas = SimpleNamespace(relevancia="relevancia", relevancia_amplitud="relevancia_amplitud", extraer="extraer", consultas="consultas", mundo="mundo")
    return Ctx(al, programas, SimpleNamespace(cerebro=SimpleNamespace(model="sim"), juez=SimpleNamespace(model="sim"), volumen=SimpleNamespace(model="sim")), "cor", "inv", "it", 1)


def _paso(al, tipo="extraccion"):
    paso = {"id": f"paso-{tipo}", "tipo": tipo, "titulo": tipo, "estado": "en_curso", "detalle": "", "indicacionHumana": False, "motivoFallo": None}
    al.mutar(lambda e: next(i for i in e["iteraciones"] if i["id"] == "it")["plan"].append(paso) or True, "plan")
    return paso


def _articulo(referencia, titulo, doi, resumen="Plasma GFAP and NfL were measured in 402 participants."):
    return {"referencia": referencia, "titulo": titulo, "resumen": resumen, "doi": doi, "pmid": None, "anio": 2026, "tipos": [], "autores": []}


def _fuente_previa(fid, doi, referencia, titulo, fragmentos, relevancia=9, extraida=True, comprobada_en=123, marca_detalle="Sin retracción en Crossref"):
    for fr in fragmentos:
        fr.setdefault("extraido", extraida)
    return {"id": fid, "referencia": referencia, "titulo": titulo, "tipo": "articulo", "doi": doi, "pmid": None, "nct": None, "relevancia": relevancia, "extraida": extraida, "retraccion": None, "retraccionComprobadaEn": comprobada_en, "_marcaDetalle": marca_detalle, "textoCompleto": any(fr["localizador"] != "resumen" for fr in fragmentos), "_claves": sorted(PASOS.claves_de_fuente({"doi": doi, "titulo": titulo})), "fragmentos": fragmentos, "modo": "foco", "iteracion": 2, "consultas": ["q0"]}


def _sin_crossref(monkeypatch, registro: list):
    async def crossref_falso(doi):
        registro.append(doi)
        return None, "Sin retracción (simulado)"

    monkeypatch.setattr(PASOS.crossref, "marca_editorial", crossref_falso)


def _busqueda_fija(monkeypatch, articulos: list[dict], total: int | None = None):
    async def buscar_falso(consulta, maximo=10, solo_preprints=False):
        return [dict(a) for a in articulos], total if total is not None else len(articulos)

    monkeypatch.setattr(PASOS.europepmc, "buscar", buscar_falso)


def _modelo_relevancia(monkeypatch, puntuacion: int, vistos: list):
    async def llamar(self, rol, programa, **kw):
        vistos.append((programa, kw.get("titulo") or kw.get("localizador")))
        if programa == "extraer":
            return SimpleNamespace(afirmaciones=[SimpleNamespace(texto="GFAP bajó un 12,4 % con lecanemab", fragmento="Plasma GFAP decreased 12.4%", tipo="dato", tema="GFAP", cohorte="CLARITY AD", nivel_medicion="resultado_analisis", n="859", comparador="placebo", efecto="-12,4 %", incertidumbre="")])
        return SimpleNamespace(puntuacion=puntuacion, motivo="responde al objetivo")

    monkeypatch.setattr(Ctx, "llamar", llamar)  # simulación local; el módulo real llama por el gateway


CONSULTA = {"base": "europepmc", "consulta": "lecanemab AND gfap", "tema": "Lecanemab y GFAP", "modo": "foco"}
CRITERIO = "Objetivo: " + OBJETIVO + "\nPreguntas abiertas:\n1. ¿Baja GFAP con lecanemab?"


# ---------------------------------------------------------------------------
# S-06 e. La reutilización congela la fuente en lo que vio la corrida anterior
# ---------------------------------------------------------------------------


def test_la_fuente_reutilizada_con_solo_resumen_pierde_la_descarga_del_texto_completo(monkeypatch):
    """FALLA HOY. En la corrida 1 el artículo quedó 5º con relevancia 7 y solo se
    guardó su resumen (`con_texto = i < 4 and puntuacion >= 7`). En la corrida 2
    sale primero con relevancia 9: antes del cambio se descargaba el PDF o el
    XML; con `_reutilizar_fuente` se copia el resumen y nunca se llega al texto
    completo. Es S-26 por otra puerta: la evidencia directa (tablas de eficacia)
    no se lee jamás si una corrida anterior solo tuvo el resumen."""
    doi = "10.1056/nejmoa2212948"
    previa = _fuente_previa("f-vieja", doi, "van Dyck et al., 2023", "Lecanemab in Early Alzheimer's Disease", [{"localizador": "resumen", "texto": "Lecanemab reduced markers of amyloid " * 5, "encabezado": "T"}], relevancia=7)
    al = _almacen(fuentes_previas={"f-vieja": previa})
    try:
        _busqueda_fija(monkeypatch, [_articulo("van Dyck et al., 2023", "Lecanemab in Early Alzheimer's Disease", doi)])
        descargas = []

        async def fragmentos(ctx, datos, pista, con_texto):
            descargas.append((datos["doi"], con_texto))
            return [{"localizador": "resumen", "texto": "r", "encabezado": ""}, {"localizador": "pág. 9", "texto": "Table 2. CDR-SB 1.21 vs 1.66, difference -0.45 (95% CI -0.67 to -0.23) " * 4, "encabezado": "T"}]

        monkeypatch.setattr(PASOS, "_fragmentos_de", fragmentos)
        _sin_crossref(monkeypatch, [])
        _modelo_relevancia(monkeypatch, 9, [])
        ctx = _ctx(al)
        r = asyncio.run(PASOS._consulta_literatura(ctx, ctx.iteracion()["plan"][0], dict(CONSULTA), CRITERIO))
        copia = next(f for f in ctx.fuentes().values() if f["doi"] == doi)
        # Lo que se espera: la fuente reutilizada que no tenía texto completo y ahora
        # cumple la regla de descarga (primeras posiciones, relevancia alta) se completa.
        assert descargas, "una fuente reutilizada sin texto completo tiene que intentar la descarga cuando esta corrida la haría"
        assert any(fr["localizador"] != "resumen" for fr in copia["fragmentos"]) and r["textoCompleto"] == 1
    finally:
        al.cerrar()


def test_la_fuente_reutilizada_deja_a_la_corrida_sin_afirmaciones_de_esa_fuente(monkeypatch):
    """FALLA HOY. La corrida 1 extrajo la fuente (afirmaciones sostenidas con su
    cita). La corrida 2 la reutiliza con `extraida=True` y todos los fragmentos
    `extraido=True`: la extracción la salta, y `paso_hipotesis` y el Killer,
    que leen `ctx.afirmaciones()` (solo la corrida), no ven ninguna afirmación
    de ella. Antes del cambio se volvía a extraer (caro, pero la evidencia
    llegaba). Las hipótesis de la corrida 2 nacen con menos evidencia directa
    de la que ROSA2018 ya tiene guardada."""
    doi = "10.1056/nejmoa2212948"
    previa = _fuente_previa("f-vieja", doi, "van Dyck et al., 2023", "Lecanemab in Early Alzheimer's Disease", [{"localizador": "resumen", "texto": "r " * 50, "encabezado": "T"}, {"localizador": "pág. 9", "texto": "Plasma GFAP decreased 12.4% (95% CI 9.8 to 15.1). " * 4, "encabezado": "T"}])
    afirmacion_previa = {"id": "af-prev", "texto": "GFAP bajó un 12,4 % con lecanemab", "cita": "[van Dyck et al., 2023, pág. 9]", "fragmento": "Plasma GFAP decreased 12.4%", "veredicto": "sostenida", "motivo": "Literal", "tipo": "dato", "clase": "literatura", "fuenteId": "f-vieja", "localizador": "pág. 9", "iteracion": 2, "cohorte": "CLARITY AD"}
    al = _almacen(fuentes_previas={"f-vieja": previa}, afirmaciones_previas=[afirmacion_previa])
    try:
        _busqueda_fija(monkeypatch, [_articulo("van Dyck et al., 2023", "Lecanemab in Early Alzheimer's Disease", doi)])
        monkeypatch.setattr(PASOS, "_fragmentos_de", None)  # si se llama, revienta: no debe descargar
        _sin_crossref(monkeypatch, [])
        vistos: list = []
        _modelo_relevancia(monkeypatch, 9, vistos)
        ctx = _ctx(al)
        asyncio.run(PASOS._consulta_literatura(ctx, ctx.iteracion()["plan"][0], dict(CONSULTA), CRITERIO))
        copia = next(f for f in ctx.fuentes().values() if f["doi"] == doi)
        assert copia["_reutilizadaDe"] == 1 and vistos == [], "la reutilización en sí funciona: ni modelo ni descarga"
        asyncio.run(PASOS.paso_extraccion(ctx, _paso(al)))
        de_la_fuente = [a for a in ctx.afirmaciones() if a["fuenteId"] == copia["id"]]
        # Lo que se espera: la evidencia ya extraída y verificada en la corrida 1 llega a
        # esta corrida (copiada con el nuevo fuenteId y su veredicto, o reextraída), para
        # que las hipótesis y el Killer puedan usarla.
        assert de_la_fuente, "la corrida no tiene ninguna afirmación de una fuente que registra como relevante y leída"
        assert any(a["veredicto"] in ("sostenida", "parcial") for a in de_la_fuente)
    finally:
        al.cerrar()


def test_la_fuente_reutilizada_vuelve_a_crossref_si_la_comprobacion_anterior_no_llego(monkeypatch):
    """FALLA HOY. En la corrida 1 Crossref no respondió (`retraccionComprobadaEn`
    None, detalle "Crossref no respondió"). La corrida 2 reutiliza la fuente y
    copia ese "no pude comprobar" para siempre: un artículo retractado después
    (o retractado ya, con Crossref caído aquel día) no se marca nunca. La regla
    del proyecto es que "no pude comprobar" es transitorio, no una comprobación."""
    doi = "10.1/retractado"
    previa = _fuente_previa("f-vieja", doi, "Dudoso et al., 2024", "A retracted trial of plasma biomarkers in early Alzheimer disease", [{"localizador": "resumen", "texto": "r " * 50, "encabezado": "T"}], comprobada_en=None, marca_detalle="Crossref no respondió: timeout. No se afirma que este limpio.")
    al = _almacen(fuentes_previas={"f-vieja": previa})
    try:
        _busqueda_fija(monkeypatch, [_articulo("Dudoso et al., 2024", "A retracted trial of plasma biomarkers in early Alzheimer disease", doi)])

        async def fragmentos(ctx, datos, pista, con_texto):
            return [{"localizador": "resumen", "texto": "r", "encabezado": ""}]

        monkeypatch.setattr(PASOS, "_fragmentos_de", fragmentos)
        consultados = []

        async def crossref_retracta(doi_):
            consultados.append(doi_)
            return "retractado", "Retraction notice (simulado)"

        monkeypatch.setattr(PASOS.crossref, "marca_editorial", crossref_retracta)
        _modelo_relevancia(monkeypatch, 9, [])
        ctx = _ctx(al)
        asyncio.run(PASOS._consulta_literatura(ctx, ctx.iteracion()["plan"][0], dict(CONSULTA), CRITERIO))
        copia = next(f for f in ctx.fuentes().values() if f["doi"] == doi)
        assert consultados == [doi], "una comprobación que no llegó no es una comprobación: se repite"
        assert copia["retraccion"] == "retractado" and copia["retraccionComprobadaEn"] is not None
    finally:
        al.cerrar()


# ---------------------------------------------------------------------------
# S-07 (1). La huella del criterio cambia con cada pregunta abierta nueva
# ---------------------------------------------------------------------------


def test_la_huella_del_criterio_no_cambia_por_anadir_una_pregunta_abierta(monkeypatch):
    """FALLA HOY. `criterio = hash_criterio(preguntas)` con `preguntas` =
    `_criterio()`, que lleva las ocho preguntas abiertas del modelo de mundo. Cada
    iteración añade preguntas, así que la huella cambia casi siempre y una
    exclusión puntuada por un modelo hace una iteración deja de valer: el pez
    cebra vuelve a Sonnet en cada iteración de cada corrida. La caché "do not
    re-mine" queda muerta (el arreglo de S-07 pedía distinguir el criterio
    heredado del propio, no invalidar por cada pregunta nueva)."""
    doi = "10.1/zebra"
    zebra = _articulo("Lejano, 2026", "Zebrafish tau model of neurodegeneration", doi, "Zebrafish larvae expressing human tau.")
    criterio_anterior = "Objetivo: " + OBJETIVO + "\nPreguntas abiertas:\n1. ¿Baja GFAP con lecanemab?"
    criterio_ahora = criterio_anterior + "\n2. ¿Cambia NfL a los 18 meses?"
    excluido = dict(zebra, relevancia=1, modo="foco", motivo="otra especie, sin biomarcadores en sangre humana", iteracion=1, puntuadoPorModelo=True, criterio=PASOS.hash_criterio(criterio_anterior))
    al = _almacen(excluidos_previos=[excluido])
    try:
        _busqueda_fija(monkeypatch, [zebra])
        monkeypatch.setattr(PASOS, "_fragmentos_de", None)
        _sin_crossref(monkeypatch, [])
        vistos: list = []
        _modelo_relevancia(monkeypatch, 1, vistos)
        ctx = _ctx(al)
        asyncio.run(PASOS._consulta_literatura(ctx, ctx.iteracion()["plan"][0], dict(CONSULTA), criterio_ahora))
        # Lo que se espera: mismo objetivo y misma pregunta de la corrida, una pregunta
        # abierta más; la exclusión de hace una iteración se reutiliza sin gastar.
        assert vistos == [], f"el modelo volvió a puntuar un artículo excluido por un modelo hace una iteración: {vistos}"
        ex = ctx.corrida()["busqueda"]["excluidos"][-1]
        assert ex["motivo"].startswith("ya excluido en la corrida 1")
    finally:
        al.cerrar()


# ---------------------------------------------------------------------------
# S-07 (2). La red por nombre repite sin tope una consulta simple sin relevantes
# ---------------------------------------------------------------------------


def test_la_red_por_nombre_no_repite_sin_tope_una_consulta_simple_sin_relevantes():
    """FALLA HOY. `consultas_por_nombre` solo deja de insistir con dos consultas
    simples con CERO resultados. "lecanemab" en Europe PMC da miles de
    resultados; si el modelo no da por relevante ninguno (relevantes 0), la
    consulta se vuelve a añadir en cada iteración de cada corrida, sin tope:
    una búsqueda, un reranker y hasta 30 cribados por iteración, para siempre.
    Los artículos con "lecanemab" en el título además son forzados al modelo
    (saltan la caché de exclusiones), así que el gasto se repite entero."""
    registro = [{"consulta": '"lecanemab"', "resultados": 2901, "relevantes": 0, "corrida": 1, "iteracion": i} for i in range(1, 4)]
    salida = PASOS.consultas_por_nombre(["lecanemab"], [], [], registro=registro)
    assert salida == [], f"tres consultas simples con miles de resultados y ningún relevante: no se insiste una cuarta vez ({salida})"


# ---------------------------------------------------------------------------
# M-08. La fusión de una paráfrasis pierde lo que el cerebro dijo que resuelve
# ---------------------------------------------------------------------------


def test_fundir_una_parafrasis_conserva_lo_que_resuelve_sustituye_o_contradice(monkeypatch):
    """FALLA HOY. Cuando `hecho_duplicado` encuentra una paráfrasis, `aplicar`
    hace `continue` antes de procesar `resuelve`, `sustituye` y `contradice`.
    Antes del cambio la paráfrasis nacía como hecho nuevo y cerraba la cuestión
    que el cerebro señaló. Ahora la cuestión sigue abierta y nadie lo anota: el
    enlace que produjo el modelo se pierde en silencio."""
    al = _almacen(con_previa=False)
    try:
        ctx = _ctx(al)
        fid = PASOS._registrar_fuente(ctx, {"referencia": "Belder et al., 2026", "titulo": "Plasma biomarkers in autosomal dominant Alzheimer disease carriers", "doi": "10.1/belder", "tipos": [], "resumen": ""}, "articulo", [{"localizador": "pág. 2", "texto": "Four non-carriers were excluded before the GFAP analysis. " * 5, "encabezado": "T"}], 8, None, "limpio", 1, "q")
        existente = P.nuevo_hecho("inv", "hecho", "GFAP", "Se excluyeron cuatro participantes no portadores de la cohorte DIAN antes del análisis de GFAP", "sabido", "fuente", [{"fuenteId": fid, "referencia": "Belder et al., 2026", "pagina": 2}], 1000, 3, "test", afirmacion_ids=["af-0"], citas=[])
        existente["entidades"] = []
        cuestion = CU.nueva("inv", "¿Cuántos participantes no portadores se excluyeron antes del análisis de GFAP en DIAN?", {"tipo": "killer", "id": None}, "El recuento de exclusiones del artículo de Belder", 1000)
        afs = [{"id": "af-1", "texto": "Los autores excluyeron a cuatro no portadores antes del análisis de GFAP", "cita": "[Belder et al., 2026, pág. 2]", "fragmento": "Four non-carriers were excluded before the GFAP analysis.", "veredicto": "sostenida", "tipo": "dato", "fuenteId": fid, "localizador": "pág. 2", "iteracion": 1}]

        def fn(e):
            e["hechos"].append(existente)
            CU.registrar(e, cuestion)
            next(c for c in e["corridas"] if c["id"] == "cor")["_afirmaciones"] = afs
            return True

        al.mutar(fn, "prueba")
        assert CU.numeradas(al.estado, "inv")[1][0]["id"] == cuestion["id"]

        async def mundo_para(almacen, inv, consulta, maximo=60):
            return "Vacío"

        async def sin_ontologias(simbolos, terminos, cache):
            return []

        monkeypatch.setattr(T, "modelo_de_mundo_para", mundo_para)
        monkeypatch.setattr(ONTO, "normalizar", sin_ontologias)

        async def llamar(self, rol, programa, **kw):
            assert programa == "mundo"
            # Paráfrasis del hecho existente (misma fuente, mismos números) que además
            # responde a la cuestión 1.
            return SimpleNamespace(hechos=[SimpleNamespace(enunciado="Los autores excluyeron a cuatro participantes no portadores de la cohorte DIAN antes del análisis de GFAP", tema="GFAP", tipo="hecho", prioridad=2, afirmaciones=[1], resuelve=[1], sustituye=[], contradice=[], que_la_resolveria="")])

        monkeypatch.setattr(Ctx, "llamar", llamar)  # simulación local; el módulo real llama por el gateway
        resumen = asyncio.run(PASOS.paso_modelo(ctx, _paso(al, "modelo")))
        assert "1 fundidos" in resumen, resumen
        c = CU.buscar(al.estado, cuestion["id"])
        # Lo que se espera: el hecho fundido responde a la cuestión igual que lo habría
        # hecho el hecho nuevo (resolver con el id del existente).
        assert c["estado"] == "resuelta", f"la cuestión sigue {c['estado']}: la fusión perdió el `resuelve` del cerebro"
        assert existente["id"] in str(c.get("resolucion") or "") or c.get("resolucion")
    finally:
        al.cerrar()


# ---------------------------------------------------------------------------
# S-26. Patrones de resultado que casan con prosa corriente (baja)
# ---------------------------------------------------------------------------


def test_los_patrones_de_resultado_no_cuentan_la_conjuncion_inglesa_or():
    """FALLA HOY (baja). `_PATRONES_RESULTADO` lleva `or\\b` y `hr\\b` para OR y HR,
    pero sin exigir mayúsculas ni una cifra al lado: la conjunción inglesa "or"
    de cualquier introducción cuenta como patrón de resultado, y con ocho
    "or" una página de prosa se lleva el máximo (1,5) de esa parte. La
    densidad de cifras sigue separando, así que el daño es de precisión, no de
    orden; pero el detalle en la pista ("patrones de resultado 9") engaña."""
    prosa = "Amyloid or tau pathology may precede symptoms, or follow them, or both; whether astrocytes or glial cells respond first is debated, or unknown, or both, or neither. " * 2
    n = len(PASOS._PATRONES_RESULTADO.findall(prosa))
    assert n == 0, f"la prosa sin una sola cifra suma {n} patrones de resultado"
