"""Tanda 2 de la revisión del 17 de septiembre de 2026, constructor "literatura":
S-26 (de cada fuente se leen los seis fragmentos que más prometen, no los seis
primeros; las secciones largas se leen en partes; la pista dice qué se leyó) y
la parte de M-08 que vive en pasos.py (un hecho que dice lo mismo con otras
palabras se funde con el existente sumando procedencia, en vez de nacer dos
veces). Sin red ni modelos: todo simulado."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

from rosa import ontologias as ONTO
from rosa import politicas
from rosa import reranker
from rosa.bucle import contexto as T
from rosa.bucle import pasos as PASOS
from rosa.bucle.pasos import Ctx
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen
from rosa.fuentes.base import FuenteNoDisponible

# ---------------------------------------------------------------------------
# Una fuente falsa de 14 páginas con las cifras en la 9 y las referencias en la 14
# ---------------------------------------------------------------------------

PROSA = ("Alzheimer's disease is a progressive neurodegenerative disorder characterised by the accumulation of amyloid plaques "
         "and neurofibrillary tangles. Astrocytes respond to injury with reactive changes that can be tracked in plasma. "
         "This background motivates the study of glial markers as early indicators of disease. ") * 4
METODOS = ("Participants were recruited consecutively from memory clinics and provided written informed consent. "
           "Plasma samples were processed within two hours and stored at minus eighty degrees. Assays were run in duplicate "
           "on a single-molecule array platform following the manufacturer's protocol. Analyses used mixed models. ") * 3
RESULTADOS_PAG_9 = ("Table 2. Primary outcome. Change from baseline in CDR-SB at 18 months was 1.21 with lecanemab versus 1.66 with placebo, "
                    "difference -0.45 (95% CI -0.67 to -0.23; p < 0.001), a 27% slowing. n = 859 versus 875. "
                    "Plasma GFAP decreased 12.4% (95% CI 9.8 to 15.1) and NfL did not differ (mean difference 0.3 pg/mL, p = 0.41). "
                    "Amyloid PET fell 59.1 centiloids (SD 20.3) versus 0.2 in placebo. HR for progression 0.69 (95% CI 0.54 to 0.88). ")
REFERENCIAS = "".join(f"{i}. Author{i} A, Author{i} B, et al. A paper about biomarkers. J Neurol 2019;{i}:{100 + i}-{110 + i}. doi:10.1000/ref.{i}\n" for i in range(1, 30))


def _paginas_falsas() -> list[dict]:
    frs = []
    for n in range(1, 15):
        if n == 9:
            texto = RESULTADOS_PAG_9
        elif n == 14:
            texto = REFERENCIAS
        elif n <= 3:
            texto = PROSA
        else:
            texto = METODOS
        frs.append({"localizador": f"pág. {n}", "texto": texto, "encabezado": "Lecanemab in Early Alzheimer's Disease"})
    return frs


def _almacen():
    al = Almacen(Path(tempfile.mkdtemp()) / "t.db")

    def fn(e):
        e["investigaciones"].append({"id": "inv", "titulo": "t", "objetivo": "Qué biomarcador predice el beneficio clínico de lecanemab", "limites": [], "condicionParada": "x", "configuracion": {"preferencias": "", "atributos": [], "restricciones": [], "amplitud": "enfocada"}, "vivero": []})
        c = P.nueva_corrida("inv", 1, 1000)
        c["id"] = "cor"
        c["estado"] = "en_marcha"
        e["corridas"].append(c)
        it = P.nueva_iteracion("cor", 1, 1000, [P.nuevo_paso("Extraer", "", 20)], 40)
        it["id"] = "it"
        e["iteraciones"].append(it)
        return True

    al.mutar(fn, "test")
    return al


def _ctx(al):
    programas = SimpleNamespace(extraer="extraer", mundo="mundo", relevancia="relevancia")
    return Ctx(al, programas, SimpleNamespace(cerebro=SimpleNamespace(model="sim"), juez=SimpleNamespace(model="sim"), volumen=SimpleNamespace(model="sim")), "cor", "inv", "it", 1)


def _paso(al, tipo="extraccion"):
    paso = {"id": f"paso-{tipo}", "tipo": tipo, "titulo": tipo, "estado": "en_curso", "detalle": "", "indicacionHumana": False, "motivoFallo": None}
    al.mutar(lambda e: next(i for i in e["iteraciones"] if i["id"] == "it")["plan"].append(paso) or True, "plan")
    return paso


def _pista_textos(ctx) -> str:
    textos = []
    for p in ctx.iteracion()["pistas"]:
        textos.append(p.get("titulo", ""))
        textos.extend(str(l.get("texto") or "") for l in (p.get("transcripcion") or []))
        textos.append(p.get("resumen") or "")
    return "\n".join(textos)


# ---------------------------------------------------------------------------
# S-26: puntuación y elección de fragmentos
# ---------------------------------------------------------------------------


def test_puntuar_fragmento_prefiere_resultados_y_cifras_y_relega_fondo_y_referencias():
    p = PASOS.puntuar_fragmento
    resultados = p({"localizador": "sección Results", "encabezado": "Results", "texto": RESULTADOS_PAG_9})
    metodos = p({"localizador": "sección Methods", "encabezado": "Methods", "texto": METODOS})
    intro = p({"localizador": "sección Introduction", "encabezado": "Introduction", "texto": PROSA})
    discusion = p({"localizador": "sección Discussion", "encabezado": "Discussion", "texto": RESULTADOS_PAG_9})
    referencias = p({"localizador": "sección References", "encabezado": "References", "texto": REFERENCIAS})
    mixta = p({"localizador": "sección Results and discussion", "encabezado": "Results and discussion", "texto": PROSA})
    assert resultados[0] > mixta[0] > metodos[0] > intro[0] and referencias[0] == 0.0, (resultados, mixta, metodos, intro, referencias)
    assert resultados[0] > discusion[0], "las mismas cifras en la discusión valen menos que en resultados"
    assert "sección de resultados" in resultados[1] and "sección de fondo" in intro[1] and "referencias" in referencias[1]
    # Páginas de PDF: las cifras mandan; la lista de referencias vale casi nada.
    pag9 = p({"localizador": "pág. 9", "texto": RESULTADOS_PAG_9})
    pag1 = p({"localizador": "pág. 1", "texto": PROSA})
    pag14 = p({"localizador": "pág. 14", "texto": REFERENCIAS})
    assert pag9[0] > pag1[0] > pag14[0] and "parece la lista de referencias" in pag14[1] and "cifras" in pag9[1]
    # Un fragmento roto no tumba nada.
    assert p({}) == (1.0, "cifras 0, patrones de resultado 0") and p({"localizador": None, "texto": None}) == (1.0, "cifras 0, patrones de resultado 0")
    assert p({"localizador": "resumen", "texto": ""})[1].startswith("resumen")


def test_elegir_fragmentos_lee_la_pagina_con_las_cifras_y_no_las_referencias(monkeypatch):
    monkeypatch.setattr(reranker, "disponible", lambda: False)
    frs = _paginas_falsas()
    elegidos, descripcion = asyncio.run(PASOS.elegir_fragmentos(frs, politicas.MAX_FRAGMENTOS_POR_FUENTE, "Objetivo: x"))
    locs = [fr["localizador"] for fr in elegidos]
    assert len(locs) == 6 and locs[0] == "pág. 9" and "pág. 14" not in locs, locs
    assert descripcion.startswith("se leen 6 de 14 fragmentos por regla") and "pág. 9 (" in descripcion and "sin leer:" in descripcion and "pág. 14" in descripcion.split("sin leer:")[1]
    # Con seis o menos, todos y en su orden.
    pocos = frs[:6]
    assert asyncio.run(PASOS.elegir_fragmentos(pocos, 6)) == (pocos, "se leen los 6 fragmentos disponibles")
    assert asyncio.run(PASOS.elegir_fragmentos([], 6)) == ([], "se leen los 0 fragmentos disponibles")


def test_elegir_fragmentos_suma_el_reranker_y_sigue_por_regla_si_falla(monkeypatch):
    frs = _paginas_falsas()
    monkeypatch.setattr(reranker, "disponible", lambda: True)
    vistas = []

    async def reordenar(pregunta, documentos, top_n=None):
        vistas.append((pregunta, len(documentos)))
        # El reranker pone la página 12 (métodos) como la más pertinente a la pregunta.
        return sorted([(i, 1.0 if i == 11 else 0.05) for i in range(len(documentos))], key=lambda x: -x[1])

    monkeypatch.setattr(reranker, "reordenar", reordenar)
    elegidos, descripcion = asyncio.run(PASOS.elegir_fragmentos(frs, 6, "Objetivo: qué predice el beneficio"))
    locs = [fr["localizador"] for fr in elegidos]
    assert vistas == [("Objetivo: qué predice el beneficio", 14)]
    assert "pág. 12" in locs and "pág. 9" in locs and "pág. 14" not in locs, locs
    assert "por regla y reranker contra las preguntas abiertas" in descripcion and "reranker 1.00" in descripcion
    # Sin preguntas no se llama al reranker.
    vistas.clear()
    asyncio.run(PASOS.elegir_fragmentos(frs, 6, ""))
    assert vistas == []

    async def caido(pregunta, documentos, top_n=None):
        raise FuenteNoDisponible("simulado: reranker sin respuesta")

    monkeypatch.setattr(reranker, "reordenar", caido)
    elegidos, descripcion = asyncio.run(PASOS.elegir_fragmentos(frs, 6, "Objetivo: x"))
    assert elegidos[0]["localizador"] == "pág. 9" and "el reranker no respondió" in descripcion


def test_partes_de_fragmento_trocea_en_parrafos_en_vez_de_cortar():
    tope = politicas.MAX_CARACTERES_POR_LLAMADA_EXTRACTOR
    corto = "x" * tope
    assert PASOS.partes_de_fragmento(corto) == [corto] and PASOS.partes_de_fragmento("") == [""]
    parrafos = "\n\n".join(f"Párrafo {i}. " + ("La frase sigue aquí con cifras 12,3 y 45. " * 30) for i in range(12))
    assert len(parrafos) > 2 * tope
    partes = PASOS.partes_de_fragmento(parrafos)
    assert 2 <= len(partes) <= politicas.MAX_PARTES_POR_FRAGMENTO and all(len(p) <= tope for p in partes)
    assert partes[0].startswith("Párrafo 0.") and all(p.strip() for p in partes)
    # Cada corte cae en un límite de párrafo, no a media palabra.
    assert all(p.rstrip().endswith(".") for p in partes)
    # Más de tres partes: se leen las tres primeras (y la pista lo dirá).
    enorme = "\n\n".join(f"P{i}. " + "palabra " * 800 for i in range(20))
    assert len(PASOS.partes_de_fragmento(enorme)) == politicas.MAX_PARTES_POR_FRAGMENTO
    # Un párrafo único sin puntos ni saltos se corta al tope, no se pierde.
    solido = "a" * (tope + 500)
    partes = PASOS.partes_de_fragmento(solido)
    assert len(partes) == 2 and len(partes[0]) == tope and len(partes[1]) == 500


def test_paso_extraccion_lee_los_seis_mejores_y_lo_anota_en_la_pista(monkeypatch):
    monkeypatch.setattr(reranker, "disponible", lambda: False)
    al = _almacen()
    try:
        ctx = _ctx(al)
        frs = [{"localizador": "resumen", "texto": "Lecanemab slowed decline in early Alzheimer's disease " * 3, "encabezado": "T"}] + _paginas_falsas()
        fid = PASOS._registrar_fuente(ctx, {"referencia": "van Dyck et al., 2023", "titulo": "Lecanemab in Early Alzheimer's Disease", "doi": "10.1056/nejmoa2212948", "tipos": [], "resumen": "r"}, "articulo", frs, 9, None, "limpio", 1, "q")
        leidos = []

        async def llamar(self, rol, programa, **kw):
            assert programa == "extraer"
            leidos.append(kw["localizador"])
            if kw["localizador"] == "pág. 9":
                return SimpleNamespace(afirmaciones=[SimpleNamespace(texto="El cambio en CDR-SB fue 1,21 con lecanemab frente a 1,66 con placebo", fragmento="Change from baseline in CDR-SB at 18 months was 1.21 with lecanemab versus 1.66 with placebo", tipo="dato", tema="eficacia", cohorte="CLARITY AD", nivel_medicion="resultado_analisis", n="859 vs 875", comparador="placebo", efecto="-0,45", incertidumbre="95% CI -0.67 to -0.23")])
            return SimpleNamespace(afirmaciones=[])

        monkeypatch.setattr(Ctx, "llamar", llamar)  # simulación local; el módulo real llama por el gateway
        resumen = asyncio.run(PASOS.paso_extraccion(ctx, _paso(al)))
        assert resumen == "1 afirmaciones extraídas de 1 fuentes"
        assert len(leidos) == politicas.MAX_FRAGMENTOS_POR_FUENTE and leidos[0] == "pág. 9" and "pág. 14" not in leidos and "resumen" not in leidos, leidos
        f = ctx.fuentes()[fid]
        assert f["extraida"] is True
        marcados = {fr["localizador"] for fr in f["fragmentos"] if fr.get("extraido")}
        assert marcados == set(leidos) and len(marcados) == 6
        af = ctx.afirmaciones()[0]
        assert af["localizador"] == "pág. 9" and af["veredicto"] == "sin_verificar" and af["cita"] == "[van Dyck et al., 2023, pág. 9]"
        textos = _pista_textos(ctx)
        assert "se leen 6 de 14 fragmentos" in textos and "pág. 9 (" in textos and "sin leer:" in textos
        assert "los que más prometen" in textos
        # Nada nuevo: no vuelve a la cola, y los ocho no leídos no se releen solos.
        assert asyncio.run(PASOS.paso_extraccion(ctx, _paso(al))) == "No hay fuentes nuevas de las que extraer"
        # Llega otra página: la fuente se reabre y la elección es entre lo no leído (la 15 nueva y las 8 de antes).
        PASOS._registrar_fuente(ctx, {"referencia": "van Dyck et al., 2023", "titulo": "Lecanemab in Early Alzheimer's Disease", "doi": "10.1056/nejmoa2212948", "tipos": [], "resumen": "r"}, "articulo", [{"localizador": "pág. 15", "texto": RESULTADOS_PAG_9.replace("Table 2", "Table 3"), "encabezado": "T"}], 9, None, "limpio", 1, "q2")
        leidos.clear()
        asyncio.run(PASOS.paso_extraccion(ctx, _paso(al)))
        assert len(leidos) == 6 and leidos[0] == "pág. 15" and "pág. 9" not in leidos and "pág. 14" not in leidos, leidos
    finally:
        al.cerrar()


def test_paso_extraccion_lee_una_seccion_larga_en_partes_con_el_mismo_localizador(monkeypatch):
    monkeypatch.setattr(reranker, "disponible", lambda: False)
    al = _almacen()
    try:
        ctx = _ctx(al)
        larga = "\n\n".join(f"Paragraph {i}. " + RESULTADOS_PAG_9 for i in range(30))
        assert len(larga) > 2 * politicas.MAX_CARACTERES_POR_LLAMADA_EXTRACTOR
        fid = PASOS._registrar_fuente(ctx, {"referencia": "Kim et al., 2025", "titulo": "Plasma GFAP precedes NfL in APOE4 carriers", "doi": "10.1/k", "tipos": [], "resumen": ""}, "articulo", [{"localizador": "sección Results", "texto": larga, "encabezado": "Results"}], 8, None, "limpio", 1, "q")
        fragmentos_vistos = []

        async def llamar(self, rol, programa, **kw):
            fragmentos_vistos.append((kw["localizador"], len(kw["fragmento"])))
            return SimpleNamespace(afirmaciones=[SimpleNamespace(texto=f"Afirmación {len(fragmentos_vistos)}", fragmento="Paragraph 0. Table 2. Primary outcome.", tipo="literatura", tema="t", cohorte="", nivel_medicion="resultado_analisis", n="", comparador="", efecto="", incertidumbre="")])

        monkeypatch.setattr(Ctx, "llamar", llamar)
        asyncio.run(PASOS.paso_extraccion(ctx, _paso(al)))
        assert len(fragmentos_vistos) == politicas.MAX_PARTES_POR_FRAGMENTO and all(loc == "sección Results" for loc, _ in fragmentos_vistos)
        assert all(n <= politicas.MAX_CARACTERES_POR_LLAMADA_EXTRACTOR + 100 for _, n in fragmentos_vistos), fragmentos_vistos  # más las marcas de dato
        assert len(ctx.afirmaciones()) == 3 and all(a["cita"] == "[Kim et al., 2025, sección Results]" for a in ctx.afirmaciones())
        assert ctx.fuentes()[fid]["extraida"] is True and ctx.fuentes()[fid]["fragmentos"][0]["extraido"] is True
        textos = _pista_textos(ctx)
        assert "se lee en 3 partes" in textos and "en vez de cortar a 6000" in textos and "las 3 primeras" in textos
    finally:
        al.cerrar()


def test_un_fallo_del_extractor_en_una_parte_deja_la_fuente_pendiente(monkeypatch):
    monkeypatch.setattr(reranker, "disponible", lambda: False)
    al = _almacen()
    try:
        ctx = _ctx(al)
        fid = PASOS._registrar_fuente(ctx, {"referencia": "Kim et al., 2025", "titulo": "Plasma GFAP precedes NfL in APOE4 carriers", "doi": "10.1/k", "tipos": [], "resumen": ""}, "articulo", [{"localizador": "pág. 2", "texto": PROSA, "encabezado": "T"}, {"localizador": "pág. 3", "texto": RESULTADOS_PAG_9, "encabezado": "T"}], 8, None, "limpio", 1, "q")

        async def llamar(self, rol, programa, **kw):
            if kw["localizador"] == "pág. 2":
                raise RuntimeError("modelo caído (simulado)")
            return SimpleNamespace(afirmaciones=[])

        monkeypatch.setattr(Ctx, "llamar", llamar)
        asyncio.run(PASOS.paso_extraccion(ctx, _paso(al)))
        f = ctx.fuentes()[fid]
        assert f["extraida"] is False, "un fragmento sin leer por fallo del modelo deja la fuente pendiente"
        assert {fr["localizador"]: fr.get("extraido") for fr in f["fragmentos"]} == {"pág. 2": False, "pág. 3": True}
        assert [fr["localizador"] for fr in PASOS.fragmentos_pendientes(f)] == ["pág. 2"], "al reintentar solo se lee lo que falló"
        assert "el extractor falló" in _pista_textos(ctx)
    finally:
        al.cerrar()


def test_fragmentos_pendientes_tolera_fuentes_antiguas_y_rotas():
    assert PASOS.fragmentos_pendientes({}) == [] and PASOS.fragmentos_pendientes({"fragmentos": None}) == []
    frs = [{"localizador": "resumen", "texto": "r"}, {"localizador": "pág. 1", "texto": "a"}, "roto", {"texto": "sin localizador"}]
    assert [fr["localizador"] for fr in PASOS.fragmentos_pendientes({"fragmentos": frs})] == ["pág. 1"]
    assert [fr["localizador"] for fr in PASOS.fragmentos_pendientes({"fragmentos": [{"localizador": "resumen", "texto": "r"}]})] == ["resumen"], "con solo el resumen, se lee el resumen"
    assert PASOS.fragmentos_pendientes({"fragmentos": [{"localizador": "resumen", "texto": "r"}, {"localizador": "pág. 1", "texto": "a", "extraido": True}]}) == []


# ---------------------------------------------------------------------------
# M-08: hechos que dicen lo mismo con otras palabras
# ---------------------------------------------------------------------------


def _hecho(enunciado, referencia="Belder et al., 2026", fuente_id="f-1", estado="sabido", tipo="hecho", afirmaciones=("af-1",)):
    h = P.nuevo_hecho("inv", tipo, "GFAP", enunciado, estado, "fuente", [{"fuenteId": fuente_id, "referencia": referencia, "pagina": 2}], 1000, 3, "test", afirmacion_ids=list(afirmaciones), citas=[{"referencia": referencia, "seccion": "pág. 2", "clasificacion": "apoya", "fragmento": "x"}])
    h["entidades"] = []
    return h


def test_hecho_duplicado_detecta_parafrasis_de_la_misma_fuente_y_respeta_las_replicaciones():
    existente = _hecho("Se excluyeron cuatro participantes no portadores de la cohorte DIAN antes del análisis de GFAP")
    misma_fuente = [{"fuenteId": "f-1", "referencia": "Belder et al., 2026", "pagina": 4}]
    otra_fuente = [{"fuenteId": "f-9", "referencia": "Raket et al., 2026", "pagina": 1}]
    parafrasis = "Los autores excluyeron a cuatro participantes no portadores de la cohorte DIAN antes del análisis de GFAP"
    dup, motivo = PASOS.hecho_duplicado([existente], parafrasis, misma_fuente)
    assert dup is existente and "misma afirmación con otras palabras" in motivo and "misma fuente" in motivo
    # La regla de cuestiones es conservadora a propósito: con una palabra de orden ("antes")
    # en común, reordenar los tokens ya no es la misma frase. Eso se hereda tal cual.
    assert PASOS.hecho_duplicado([existente], "Antes del análisis de GFAP se excluyeron de la cohorte DIAN cuatro participantes no portadores", misma_fuente) == (None, "")
    # La misma paráfrasis desde otra fuente es una replicación: nace aparte.
    assert PASOS.hecho_duplicado([existente], parafrasis, otra_fuente) == (None, "")
    # Texto idéntico: duplicado con cualquier fuente (y también si el existente está descartado: quien llama lo omite).
    assert PASOS.hecho_duplicado([existente], existente["enunciado"].upper(), otra_fuente)[1] == "texto idéntico"
    descartado = _hecho("Un hecho descartado por la persona sobre NfL en plasma", estado="descartado")
    assert PASOS.hecho_duplicado([descartado], "Un hecho descartado por la persona sobre NfL en plasma", misma_fuente)[0] is descartado
    assert PASOS.hecho_duplicado([descartado], "Sobre NfL en plasma, un hecho descartado por la persona", misma_fuente) == (None, ""), "una paráfrasis de un descartado no se funde con él"
    # Cifras (con letra o con dígitos) o siglas distintas no son la misma afirmación aunque el resto coincida.
    assert PASOS.hecho_duplicado([existente], parafrasis.replace("cuatro", "seis"), misma_fuente) == (None, "")
    assert PASOS.hecho_duplicado([existente], parafrasis.replace("cuatro", "4"), misma_fuente) == (None, "")
    assert PASOS.hecho_duplicado([existente], parafrasis.replace("GFAP", "NfL"), misma_fuente) == (None, "")
    assert PASOS._numeros_de("Se excluyeron cuatro de 312 participantes, un 27 % del total") == {"cuatro", "312", "27"}
    # Una pregunta no absorbe un hecho parafraseado, ni al revés.
    pregunta = _hecho("¿Se excluyeron participantes no portadores de la cohorte DIAN antes del análisis de GFAP?", tipo="pregunta", estado="abierto")
    assert PASOS.hecho_duplicado([pregunta], parafrasis, misma_fuente) == (None, "")
    # La regla anterior (dos entidades canónicas y mismo comienzo) sigue valiendo, ahora fundiendo.
    con_entidades = _hecho("El GFAP en plasma sube antes que el NfL en portadores de APOE4 con amiloide positivo")
    con_entidades["entidades"] = [{"id": "HGNC:4235", "etiqueta": "GFAP"}, {"id": "HGNC:7827", "etiqueta": "NfL"}]
    dup, motivo = PASOS.hecho_duplicado([con_entidades], "El GFAP en plasma sube antes que el NfL en portadores de APOE4 con amiloide positivo según dos cohortes distintas y un metaanálisis", otra_fuente, {"HGNC:4235", "HGNC:7827"})
    assert dup is con_entidades and motivo == "mismas entidades canónicas y mismo comienzo"
    assert PASOS.hecho_duplicado([], "x", []) == (None, "") and PASOS.hecho_duplicado([existente], "", misma_fuente) == (None, "")
    assert PASOS.comparte_referencia([{"referencia": "Belder et al., 2026"}], [{"fuenteId": "otro", "referencia": "belder et al., 2026"}]) and not PASOS.comparte_referencia(None, [{"fuenteId": "f"}])


def test_fundir_hecho_suma_procedencia_citas_y_afirmaciones_una_sola_vez():
    h = _hecho("Se excluyeron cuatro participantes no portadores")
    nueva_proc = [{"fuenteId": "f-1", "referencia": "Belder et al., 2026", "pagina": 2}, {"fuenteId": "f-1", "referencia": "Belder et al., 2026", "pagina": 4}]
    nuevas_citas = [{"referencia": "Belder et al., 2026", "seccion": "pág. 4", "clasificacion": "apoya", "fragmento": "y"}, {"referencia": "Belder et al., 2026", "seccion": "pág. 2", "clasificacion": "apoya", "fragmento": "repetida"}]
    assert PASOS.fundir_hecho(h, nueva_proc, nuevas_citas, ["af-1", "af-7", ""], 2000, "Fundido con una paráfrasis") is True
    assert [p["pagina"] for p in h["procedencia"]] == [2, 4] and [c["seccion"] for c in h["citas"]] == ["pág. 2", "pág. 4"]
    assert h["afirmacionIds"] == ["af-1", "af-7"] and h["actualizadoEn"] == 2000
    assert h["historial"][-1]["motivo"] == "Fundido con una paráfrasis" and h["historial"][-1]["de"] == h["historial"][-1]["a"] == "sabido"
    # Nada nuevo: no toca ni el historial ni la fecha.
    n = len(h["historial"])
    assert PASOS.fundir_hecho(h, nueva_proc, nuevas_citas, ["af-7"], 3000, "otra vez") is False
    assert len(h["historial"]) == n and h["actualizadoEn"] == 2000
    # Un hecho antiguo sin las listas no rompe.
    viejo = {"enunciado": "x", "estado": "sabido"}
    assert PASOS.fundir_hecho(viejo, [{"fuenteId": "f"}], [], ["af-2"], 1, "m") is True and viejo["afirmacionIds"] == ["af-2"]


def test_paso_modelo_funde_la_parafrasis_con_el_hecho_existente_en_vez_de_crear_otro(monkeypatch):
    al = _almacen()
    try:
        ctx = _ctx(al)
        fid = PASOS._registrar_fuente(ctx, {"referencia": "Belder et al., 2026", "titulo": "Plasma biomarkers in autosomal dominant Alzheimer disease carriers", "doi": "10.1/belder", "tipos": [], "resumen": ""}, "articulo", [{"localizador": "pág. 2", "texto": "Four non-carriers were excluded before the GFAP analysis. " * 5, "encabezado": "T"}, {"localizador": "pág. 4", "texto": "The GFAP analysis excluded four non-carriers. " * 5, "encabezado": "T"}], 8, None, "limpio", 1, "q")
        existente = _hecho("Se excluyeron cuatro participantes no portadores de la cohorte DIAN antes del análisis de GFAP", fuente_id=fid, afirmaciones=("af-1",))
        descartado = _hecho("El NfL en plasma no cambia en portadores presintomáticos", fuente_id=fid, estado="descartado", afirmaciones=("af-0",))
        afs = [
            {"id": "af-1", "texto": "Se excluyeron cuatro no portadores antes del análisis", "cita": "[Belder et al., 2026, pág. 2]", "fragmento": "Four non-carriers were excluded before the GFAP analysis.", "veredicto": "sostenida", "tipo": "dato", "fuenteId": fid, "localizador": "pág. 2", "iteracion": 1},
            {"id": "af-2", "texto": "El análisis de GFAP excluyó a cuatro no portadores", "cita": "[Belder et al., 2026, pág. 4]", "fragmento": "The GFAP analysis excluded four non-carriers.", "veredicto": "sostenida", "tipo": "dato", "fuenteId": fid, "localizador": "pág. 4", "iteracion": 1},
            {"id": "af-3", "texto": "GFAP sube antes que NfL", "cita": "[Belder et al., 2026, pág. 4]", "fragmento": "x", "veredicto": "sostenida", "tipo": "dato", "fuenteId": fid, "localizador": "pág. 4", "iteracion": 1},
        ]

        def fn(e):
            e["hechos"].extend([existente, descartado])
            next(c for c in e["corridas"] if c["id"] == "cor")["_afirmaciones"] = afs
            return True

        al.mutar(fn, "prueba")

        async def mundo_para(almacen, inv, consulta, maximo=60):
            return "Vacío"

        async def sin_ontologias(simbolos, terminos, cache):
            return []

        monkeypatch.setattr(T, "modelo_de_mundo_para", mundo_para)
        monkeypatch.setattr(ONTO, "normalizar", sin_ontologias)

        def _hp(enunciado, tipo="hecho", afirmaciones=()):
            return SimpleNamespace(enunciado=enunciado, tema="GFAP", tipo=tipo, prioridad=2, afirmaciones=list(afirmaciones), resuelve=[], sustituye=[], contradice=[], que_la_resolveria="")

        async def llamar(self, rol, programa, **kw):
            assert programa == "mundo"
            return SimpleNamespace(hechos=[
                _hp("Los autores excluyeron a cuatro participantes no portadores de la cohorte DIAN antes del análisis de GFAP", afirmaciones=[1, 2]),  # paráfrasis, misma fuente: se funde
                _hp("El NfL en plasma no cambia en portadores presintomáticos", afirmaciones=[3]),  # idéntico a un descartado: se omite
                _hp("El GFAP en plasma sube antes que el NfL en portadores", afirmaciones=[3]),  # nuevo de verdad
            ])

        monkeypatch.setattr(Ctx, "llamar", llamar)  # simulación local; el módulo real llama por el gateway
        resumen = asyncio.run(PASOS.paso_modelo(ctx, _paso(al, "modelo")))
        hechos = [h for h in al.estado["hechos"] if h["investigacionId"] == "inv"]
        assert [h["enunciado"] for h in hechos if h["tipo"] == "hecho" and h["estado"] == "sabido"] == [existente["enunciado"], "El GFAP en plasma sube antes que el NfL en portadores"], [h["enunciado"] for h in hechos]
        fundido = next(h for h in hechos if h["id"] == existente["id"])
        assert sorted(fundido["afirmacionIds"]) == ["af-1", "af-2"], fundido["afirmacionIds"]
        assert sorted(p["pagina"] for p in fundido["procedencia"]) == [2, 4] and all(p["fuenteId"] == fid for p in fundido["procedencia"])
        assert {c["seccion"] for c in fundido["citas"]} == {"pág. 2", "pág. 4"}
        assert "Fundido en la iteración 1" in fundido["historial"][-1]["motivo"] and "misma fuente" in fundido["historial"][-1]["motivo"]
        assert "1 fundidos con hechos existentes" in resumen and resumen.startswith("1 hechos y 0 preguntas nuevas")
        textos = _pista_textos(ctx)
        assert "1 fundidos con hechos que ya decían lo mismo" in textos and "1 omitidos por repetir un hecho descartado" in textos
        eventos = [ev["texto"] for ev in al.estado["eventos"] if ev["tipo"] == "hecho_nuevo"]
        assert eventos == ["Hecho nuevo: El GFAP en plasma sube antes que el NfL en portadores"], "la fusión no anuncia un hecho nuevo"
    finally:
        al.cerrar()
