"""Integración del perfil de diana, la ruta, las alternativas, el contrato del
experimento y el registro de datasets en las firmas, el Killer y los pasos
del bucle. Sin red y sin modelos: los conectores se sustituyen por un
`consultar` falso y `Ctx.llamar` por una función que devuelve una revisión
del Killer escrita a mano.

Lo que se comprueba:
- `ExperimentoPropuesto` acepta lecturas y sistema (hereda del contrato) y
  sigue aceptando la forma antigua.
- `contexto_humano` aparece entre las comprobaciones deterministas del Killer;
  con un perfil de una diana que HPA no detecta en cerebro y una tarjeta que
  pone el mecanismo en astrocitos, falla y la decisión por regla es reformular.
- La regla de alternativas clasifica y no duplica; los registros antiguos sin
  la clave o con basura no rompen.
- `desde_geo` y `desde_cellxgene` registran las filas del paso de novedad,
  toleran filas raras y no duplican.
- El texto que recibe el juez incluye la tabla del perfil; en la misma
  mutación quedan `ruta`, `alternativas` y `perfilDiana` con su versión.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rosa import conectores as CON
from rosa import dianas as DI
from rosa import experimento as XP
from rosa import killer as K
from rosa.bucle import pasos as PASOS
from rosa.bucle.pasos import Ctx
from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen
from rosa.modulos import firmas as F

FALLO = object()

# Ficha inventada de un gen hepático ficticio (GENHEP): HPA no lo detecta en
# cerebro y lo enriquece en hígado. No se usa un gen real para no atribuirle un
# dato que la base no dice.
HPA_GENHEP = {"Gene": "GENHEP", "RNA tissue specificity": "Tissue enriched", "RNA tissue specific nTPM": {"liver": "198523.8"}, "RNA brain regional distribution": "Not detected", "RNA single cell type specific nCPM": {"Hepatocytes": "81391.2"}}
IDS_GENHEP = {"simbolo": "GENHEP", "nombre": "gen hepático ficticio", "ensembl": "ENSG00000999999", "uniprot": "P99999", "entrez": "999999"}
RESPUESTAS_GENHEP: dict[str, Any] = {
    "mygene_gen": IDS_GENHEP,
    "gtex_gen": {"simbolo": "GENHEP", "gencode": "ENSG00000999999.7", "tipo": "protein coding", "version_gencode": "v39"},
    "gtex_expresion": [{"gen": "GENHEP", "tejido": "Brain_Hippocampus", "mediana": 0.0, "unidad": "TPM"}],
    "uniprot_proteina": {"accession": "P99999", "nombre": "Proteína hepática ficticia", "longitud": 300, "funcion": "Transporte en plasma."},
    "reactome_rutas": [],
    "hpa_expresion": HPA_GENHEP,
    "string_interactores": [],
    "gwas_asociaciones_gen": {"total_asociaciones": 2, "en_esta_pagina": 2, "n_alzheimer": 0, "alzheimer": []},
    "clinvar_gen": {"variantes_gen": 3, "con_enfermedad": 0, "ids": []},
    "opentargets_graphql": {"target": None},
    "chembl_diana": {"diana": None, "mecanismos": []},
    "dgidb_gen": {"total": 0, "interacciones": []},
    "pubtator_relaciones": FALLO,
}


def consultar_falso(respuestas: dict[str, Any]):
    """Imita a rosa.conectores.consultar: (registro, datos). Lo que no figura
    en `respuestas` falla como si la fuente no respondiera."""
    llamadas: list[tuple[str, dict[str, Any]]] = []

    async def consultar(nombre: str, /, resumen: str = "", origen: str = "bucle", **argumentos: Any):
        llamadas.append((nombre, argumentos))
        r = respuestas.get(nombre, FALLO)
        reg: dict[str, Any] = {"id": f"con-{len(llamadas)}", "herramienta": nombre, "fuente": nombre, "argumentos": argumentos, "fecha": 1, "n": None, "ids": [], "version": None, "invariante": None, "error": None, "ms": 1, "resumen": resumen}
        if r is FALLO:
            reg["error"] = "No pude comprobar: tiempo agotado (timeout)"
            return reg, None
        reg["n"] = len(r) if isinstance(r, (list, dict)) else 1
        return reg, r

    consultar.llamadas = llamadas  # type: ignore[attr-defined]
    return consultar


def _ctx() -> tuple[Almacen, Ctx]:
    al = Almacen(Path(tempfile.mkdtemp()) / "t.db")
    al.aplicar("crearInvestigacion", {"datos": {"titulo": "T", "objetivo": "Astrocitos y GENHEP en la enfermedad de Alzheimer", "condicionParada": "1 iteración"}, "id_": "inv"})
    cid = al.aplicar("iniciarCorrida", {"investigacion_id": "inv"})
    modelos = SimpleNamespace(juez=SimpleNamespace(model="juez-simulado"), cerebro=SimpleNamespace(model="cerebro-simulado"), volumen=SimpleNamespace(model="volumen-simulado"))
    return al, Ctx(al, F.Programas(), modelos, cid, "inv", "", 1)


def _afirmacion(**k: Any) -> dict[str, Any]:
    base = {"afirmacionId": "af-1", "texto": "GENHEP increases in reactive astrocytes of the hippocampus", "cita": "[A et al., 2025, pág. 3]", "veredicto": "sostenida", "motivo": "", "entidadDistinta": False, "tipo": "dato", "clase": "literatura", "sintetico": False, "cohorte": "", "sospechosoInyeccion": False, "nivelMedicion": "resultado_analisis", "n": "", "comparador": "", "efecto": "", "incertidumbre": "", "sinResolver": [], "trayectoria": None, "fragmento": "GENHEP increases in reactive astrocytes of the hippocampus"}
    base.update(k)
    return base


def _hipotesis(**campos: Any) -> dict[str, Any]:
    datos = dict(
        titulo="GENHEP en astrocitos reactivos",
        enunciado="GENHEP sube en astrocitos reactivos del hipocampo en la fase preclínica",
        mecanismo="Los astrocitos reactivos del hipocampo liberan GENHEP",
        comprobacion={"biomarcador": "GENHEP", "cohorte": "", "diseno": "transversal"},
        cluster="Astrocitos",
        relevancia={"justificacion": "prueba", "votoHumano": None},
        afirmaciones=[_afirmacion()],
        supuestos=[],
        tarjeta={"diana": "GENHEP", "celula": "astrocitos reactivos", "etapa": "preclínica", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "GENHEP en LCR es mayor en amiloide positivos que en negativos", "riesgos": [], "pasoRuta": "mecanismo"},
    )
    datos.update(campos)
    h = P.nueva_hipotesis("inv", 1, 1, **datos)
    h["procedencia"]["fuentes"] = [{"id": "f1", "referencia": "A et al., 2025", "titulo": "GENHEP in astrocytes", "anio": 2025, "tipoEstudio": None, "cohorte": "", "autores": [], "centro": ""}]
    return h


def _perfil_genhep(version: int | None = 1) -> dict[str, Any]:
    p = asyncio.run(DI.perfil_de_diana("GENHEP", IDS_GENHEP, consultar=consultar_falso(RESPUESTAS_GENHEP), contexto={"celula": "astrocitos reactivos"}))
    if version is not None:
        p["version"] = version
    return p


# ---------------------------------------------------------------------------
# 1. Firmas: el contrato del experimento
# ---------------------------------------------------------------------------


def test_experimento_propuesto_acepta_lecturas_y_sistema():
    x = F.ExperimentoPropuesto(
        protocolo=["Cultivar astrocitos humanos de donante", "Medir GENHEP en el medio"],
        ensayo="Simoa de GENHEP en medio de cultivo",
        resultado_que_confirma="sube al menos 20 %",
        resultado_que_refuta="cambio menor del 5 %",
        coste_estimado="semanas",
        analisis_pedido="",
        lecturas=[
            {"nombre": "GENHEP intracelular por western", "tipo": "compromiso_diana", "que_confirma": "baja al menos 50 %", "que_refuta": "cambio menor del 10 %", "control": "siRNA control", "unidad": "%"},
            {"nombre": "GENHEP en medio por Simoa", "tipo": "biomarcador", "que_confirma": "sube al menos 20 %", "que_refuta": "cambio menor del 5 %", "unidad": "pg/mL"},
        ],
        sistema={"tipo": "celulas_humanas_donante", "que_prueba": "la liberación por el astrocito", "que_no_representa": "la interacción con microglía ni la edad"},
        proposito_biomarcador="monitorizacion",
        nivel_desenlace="molecular",
        puente_al_beneficio="que la cifra en LCR siga a la del cultivo",
    )
    assert issubclass(F.ExperimentoPropuesto, XP.ContratoPropuesto)
    assert [l.tipo for l in x.lecturas] == ["compromiso_diana", "biomarcador"] and x.sistema.tipo == "celulas_humanas_donante"
    contrato = XP.contrato_desde_propuesta(x)
    assert [l["nombre"] for l in contrato["lecturas"]] == ["GENHEP intracelular por western", "GENHEP en medio por Simoa"]
    assert contrato["lecturas"][0]["queConfirma"] == "baja al menos 50 %" and contrato["sistema"]["queNoRepresenta"].startswith("la interacción")
    assert contrato["propositoBiomarcador"] == "monitorizacion" and contrato["nivelDesenlace"] == "molecular"
    assert isinstance(XP.validar_contrato({**contrato, "ensayo": x.ensayo}), list)
    # La forma antigua (sin lecturas ni sistema) sigue valiendo: son opcionales.
    viejo = F.ExperimentoPropuesto(protocolo=["p"], ensayo="e", resultado_que_confirma="c", resultado_que_refuta="r", coste_estimado="x", analisis_pedido="")
    assert viejo.lecturas == [] and viejo.sistema is None and viejo.proposito_biomarcador is None
    assert XP.contrato_desde_propuesta(viejo)["lecturas"] == []
    # Un tipo de lectura fuera del vocabulario cerrado no entra.
    with pytest.raises(Exception):
        F.ExperimentoPropuesto(protocolo=["p"], ensayo="e", resultado_que_confirma="c", resultado_que_refuta="r", coste_estimado="x", analisis_pedido="", lecturas=[{"nombre": "x", "tipo": "otra_cosa", "que_confirma": "a", "que_refuta": "b"}])
    # La firma pide una cifra por lectura con su nombre exacto y el Killer conoce la comprobación nueva.
    assert "NOMBRE EXACTO" in F.ResultadoExperimento.model_fields["cifras"].description
    assert "contexto_humano" in F.NOMBRES_COMPROBACION.__args__
    assert "datasets_disponibles" in F.ProponerPlan.input_fields
    assert F.RevisionKiller.model_fields["alternativas"].annotation == list[F.AlternativaPropuesta]
    assert F.RevisionKiller(comprobaciones=[], supuesto_invalidante="", reformulacion_sugerida="", que_haria_falta="", resumen="r").alternativas == []


# ---------------------------------------------------------------------------
# 2. Killer: contexto humano entre las deterministas
# ---------------------------------------------------------------------------


def test_contexto_humano_entre_las_deterministas_y_falla_con_perfil_hepatico():
    al, _ = _ctx()
    e = al.estado
    h = _hipotesis()
    # Sin perfil: no comprobable, nunca falla por falta de dato.
    c = {x["comprobacion"]: x for x in K.comprobaciones_deterministas(h, e)}
    assert c["contexto_humano"]["resultado"] == "no_comprobable" and "no se han consultado" in c["contexto_humano"]["detalle"]
    # Perfil hepático (HPA: no detectado en cerebro) y mecanismo en astrocitos: falla.
    h["perfilDiana"] = _perfil_genhep()
    c = {x["comprobacion"]: x for x in K.comprobaciones_deterministas(h, e)}
    assert c["contexto_humano"]["resultado"] == "falla" and "no detecta GENHEP en cerebro humano" in c["contexto_humano"]["detalle"]
    decision, motivo = K.decidir(list(c.values()), True, 1)
    assert decision == "reformular" and "contexto_humano" in motivo
    assert "contexto_humano" in K.REFORMULAN and K.CONSECUENCIA["contexto_humano"] == "reformular"
    # Un perfil de otra versión de la hipótesis no sirve para juzgar esta.
    h["perfilDiana"] = _perfil_genhep(version=2)
    c = {x["comprobacion"]: x for x in K.comprobaciones_deterministas(h, e)}
    assert c["contexto_humano"]["resultado"] == "no_comprobable" and "versión 2" in c["contexto_humano"]["detalle"]
    # Mecanismo periférico con la misma diana: HPA la expresa en hepatocitos y pasa.
    h2 = _hipotesis(tarjeta={"diana": "GENHEP", "celula": "hepatocitos", "etapa": "", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "x", "riesgos": [], "pasoRuta": "mecanismo"}, mecanismo="GENHEP hepático", enunciado="GENHEP sube en hígado")
    h2["perfilDiana"] = _perfil_genhep()
    c2 = {x["comprobacion"]: x for x in K.comprobaciones_deterministas(h2, e)}
    assert c2["contexto_humano"]["resultado"] == "pasa"
    # Registros raros: perfil como texto, lista o entero; hipótesis sin tarjeta.
    for raro in ("texto", 3, ["a"], {"capas": 7}):
        h["perfilDiana"] = raro
        c = {x["comprobacion"]: x for x in K.comprobaciones_deterministas(h, e)}
        assert c["contexto_humano"]["resultado"] == "no_comprobable"
    h3 = _hipotesis()
    h3["tarjeta"] = None
    h3.pop("perfilDiana", None)
    assert any(x["comprobacion"] == "contexto_humano" for x in K.comprobaciones_deterministas(h3, e))


# ---------------------------------------------------------------------------
# 3. Alternativas: clasificación y escritura sin duplicados
# ---------------------------------------------------------------------------


def test_regla_de_alternativas_clasifica_y_no_duplica():
    cl = PASOS.clasificar_alternativa
    assert cl("Causa inversa: el daño astrocitario eleva GENHEP y no al revés") == "causa_inversa"
    assert cl("La edad explica ambas cosas a la vez") == "confusor"
    assert cl("Sesgo de selección: solo se estudiaron supervivientes") == "seleccion"
    assert cl("Artefacto de medida: la plataforma cambió entre lotes") == "artefacto"
    assert cl("Otra cosa sin palabras clave") == "otra"
    assert cl("") == "otra" and cl(None) == "otra"
    # Lo que devuelve el juez: objetos de la firma, diccionarios, cadenas antiguas y basura.
    rev = [F.AlternativaPropuesta(texto="La edad explica ambas cosas", que_la_distinguiria="Ajustar por edad borra la asociación"), {"texto": "Causa inversa", "que_la_distinguiria": "La temporalidad lo separa"}, "cadena antigua", "", None, 7, F.AlternativaPropuesta(texto="la edad explica ambas cosas", que_la_distinguiria="repetida con otras mayúsculas")]
    normalizadas = PASOS.alternativas_de_revision(rev)
    assert [a["texto"] for a in normalizadas] == ["La edad explica ambas cosas", "Causa inversa", "cadena antigua"]
    assert normalizadas[0]["queLaDistinguiria"].startswith("Ajustar") and normalizadas[2]["queLaDistinguiria"] == ""
    assert PASOS.alternativas_de_revision(None) == [] and PASOS.alternativas_de_revision("texto") == []
    # Escritura: registro antiguo sin la clave, después con basura, sin repetir.
    x: dict[str, Any] = {}
    assert PASOS.anadir_alternativas(x, normalizadas, 3) == 3
    assert [a["clase"] for a in x["alternativas"]] == ["confusor", "causa_inversa", "otra"] and all(a["iteracion"] == 3 for a in x["alternativas"])
    assert PASOS.anadir_alternativas(x, normalizadas, 4) == 0 and len(x["alternativas"]) == 3
    x["alternativas"] = "basura"
    assert PASOS.anadir_alternativas(x, [{"texto": "Nueva", "queLaDistinguiria": ""}], None) == 1 and x["alternativas"][0]["iteracion"] is None
    x["alternativas"] = [None, {"sin_texto": 1}, {"texto": "Nueva"}]
    assert PASOS.anadir_alternativas(x, [{"texto": "nueva", "queLaDistinguiria": ""}], 5) == 0 and len(x["alternativas"]) == 1


# ---------------------------------------------------------------------------
# 4. Registro de datasets del programa desde el paso de novedad
# ---------------------------------------------------------------------------


def test_desde_geo_registra_filas_del_paso_de_novedad():
    al, ctx = _ctx()
    series = [
        {"accession": "GSE5281", "titulo": "Alzheimer's disease and the normal aged brain, six regions", "n_muestras": "161", "plataforma": "GPL570", "organismo": "Homo sapiens", "tipo": "Expression profiling by array"},
        {"accession": "GSE174367", "titulo": "Single-nucleus chromatin accessibility and transcriptomic characterization of Alzheimer's disease", "n_muestras": "40", "plataforma": "GPL24676", "tipo": "Expression profiling by high throughput sequencing"},
        {"accession": None, "titulo": None},  # fila rara
        {},  # fila vacía
        "no soy un diccionario",
        None,
    ]
    colecciones = [{"id": "col-1", "nombre": "Seattle Alzheimer's Disease Brain Cell Atlas (SEA-AD)", "url": "https://cellxgene.cziscience.com/collections/col-1", "datasets": 3, "celulas": 1200000, "doi": "10.1/x"}, {"nombre": "sin id"}, None]
    n = PASOS.registrar_datasets_programa(ctx, series, colecciones, None)
    reg = al.estado["datasetsPrograma"]
    assert n == 3 and len(reg) == 3
    por_acc = {r["accession"]: r for r in reg}
    assert set(por_acc) == {"GSE5281", "GSE174367", "col-1"}
    assert por_acc["GSE5281"]["fuente"] == "geo" and por_acc["GSE5281"]["acceso"] == "abierto" and "inv" in por_acc["GSE5281"]["usadoEn"]
    assert por_acc["GSE174367"]["tipo"] == "celula_unica" and por_acc["col-1"]["fuente"] == "cellxgene" and por_acc["col-1"]["tipo"] == "celula_unica"
    # Segunda pasada con las mismas filas: no duplica.
    assert PASOS.registrar_datasets_programa(ctx, series, colecciones, None) >= 0 and len(al.estado["datasetsPrograma"]) == 3
    # Conector caído o formas raras: nada que registrar y nada que romper.
    assert PASOS.registrar_datasets_programa(ctx, None, None, None) == 0
    assert PASOS.registrar_datasets_programa(ctx, "texto", {"id": "x"}, None) == 0
    assert len(al.estado["datasetsPrograma"]) == 3
    # El texto para el planificador nombra los datasets y los que coinciden con la pregunta.
    texto = PASOS.datasets_para_plan(al.estado, "inv", "expresión en hipocampo de célula única en Alzheimer")
    assert texto.startswith("Datasets registrados en el programa: 3") and "GSE5281" in texto
    assert "Coinciden con la pregunta" in texto and "GSE174367" in texto
    assert "\u2014" not in texto
    # Sin pregunta y con un estado vacío también responde.
    assert "Ningún dataset registrado" in PASOS.datasets_para_plan({}, "inv", None)
    assert "Ningún dataset del registro coincide" in PASOS.datasets_para_plan({}, "inv", "hipocampo")


def test_dataset_de_acceso_controlado_lleva_su_aviso_en_el_plan():
    al, ctx = _ctx()
    # Una serie cuyo título nombra un conjunto de acceso controlado: entra al
    # registro marcada como controlada (el proyecto no la pide), nunca como
    # dato para analizar.
    series = [{"accession": "GSE999001", "titulo": "Bulk RNA-seq of ROSMAP dorsolateral prefrontal cortex, hippocampus", "n_muestras": "600", "plataforma": "GPL16791", "tipo": "Expression profiling by high throughput sequencing"}]
    assert PASOS.registrar_datasets_programa(ctx, series, [], None) == 1
    r = al.estado["datasetsPrograma"][0]
    assert r["acceso"] == "controlado"
    texto = PASOS.datasets_para_plan(al.estado, "inv", "expresión en hipocampo en Alzheimer")
    assert "acceso controlado" in texto and "AVISO" in texto


# ---------------------------------------------------------------------------
# 5. El Killer de punta a punta con modelos simulados
# ---------------------------------------------------------------------------


def test_killer_recibe_la_tabla_del_perfil_y_escribe_ruta_alternativas_y_perfil(monkeypatch):
    al, ctx = _ctx()
    h = _hipotesis()
    al.mutar(lambda e: e["hipotesis"].append(h) or True, "prueba")
    consultar = consultar_falso(RESPUESTAS_GENHEP)
    monkeypatch.setattr(CON, "consultar", consultar)

    async def sin_ontologias(simbolos, terminos, cache):
        return []

    monkeypatch.setattr(PASOS.ONTO, "normalizar", sin_ontologias)
    recibido: dict[str, Any] = {}

    async def llamar_falso(self, rol, programa, **kwargs):
        if programa is self.programas.killer:
            recibido.update(kwargs)
            revision = F.RevisionKiller(
                comprobaciones=[F.ComprobacionKiller(comprobacion="falsabilidad", resultado="pasa", detalle="Hay predicción medible")],
                supuesto_invalidante="",
                alternativas=[F.AlternativaPropuesta(texto="La edad de los donantes explica a la vez la reactividad y el GENHEP", que_la_distinguiria="Ajustar por edad borraría la asociación")],
                reformulacion_sugerida="Cambiar la diana o explicar cómo llega GENHEP al cerebro",
                que_haria_falta="",
                contradice_a=[],
                resumen="Pasa las citas; falla el contexto humano; lo más frágil es la diana.",
            )
            return SimpleNamespace(revision=revision)
        raise RuntimeError(f"modelo simulado sin respuesta para {type(programa).__name__}")

    monkeypatch.setattr(Ctx, "llamar", llamar_falso)
    decision = asyncio.run(PASOS._killer(ctx, h, "", None))
    x = next(y for y in al.estado["hipotesis"] if y["id"] == h["id"])
    # El juez recibió la tabla del perfil junto a la hipótesis y la tarjeta.
    assert "Perfil de evidencia por diana: GENHEP" in recibido["hipotesis"] and "Tarjeta: diana o proceso GENHEP" in recibido["hipotesis"]
    assert "Expresión en tejido" in recibido["hipotesis"] and "Leyenda: presente" in recibido["hipotesis"]
    assert "contexto_humano: falla" in recibido["comprobaciones_deterministas"]
    # El perfil quedó con la versión de la hipótesis y el GENCODE de GTEx en los identificadores.
    assert x["perfilDiana"]["version"] == 1 and x["perfilDiana"]["identificadores"]["gencode"] == "ENSG00000999999.7"
    assert x["contextoBases"]["identificadores"]["gencode"] == "ENSG00000999999.7"
    assert any(n == "gtex_gen" for n, _ in consultar.llamadas) and any(n == "gtex_expresion" for n, _ in consultar.llamadas)
    assert any(c["herramienta"] == "gtex_gen" for c in x["consultas"])
    # El contexto humano falló y la decisión por regla fue reformular (el reformulador simulado no respondió, así que sigue en la versión 1).
    assert decision == "reformular" and x["decisionKiller"] == "reformular"
    d = x["decisiones"][-1] if x.get("decisiones") else next(d for d in reversed(al.estado["decisiones"]) if d["hipotesisId"] == h["id"])
    assert any(c["comprobacion"] == "contexto_humano" and c["resultado"] == "falla" for c in d["comprobaciones"])
    # Ruta terapéutica por regla y alternativas con su clase, escritas en la misma mutación.
    assert isinstance(x["ruta"], dict) and x["ruta"]["hipotesisId"] == h["id"] and len(x["ruta"]["pasos"]) == 8
    assert x["alternativas"] == [{"texto": "La edad de los donantes explica a la vez la reactividad y el GENHEP", "clase": "confusor", "queLaDistinguiria": "Ajustar por edad borraría la asociación", "iteracion": 1}]
    assert any("Alternativas a considerar" in m["texto"] for m in x["procedencia"]["mensajes"])
    # El grafo causal sigue recibiendo los textos, como antes.
    assert any(n["rol"] == "alternativa_confusor" for n in x["grafoCausal"]["nodos"])


def test_killer_sin_diana_ni_juez_no_rompe(monkeypatch):
    al, ctx = _ctx()
    h = _hipotesis(titulo="Sueño y memoria", tarjeta={"diana": "", "celula": "", "etapa": "", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "x", "riesgos": [], "pasoRuta": "mecanismo"}, comprobacion={"biomarcador": "", "cohorte": "", "diseno": ""})
    al.mutar(lambda e: e["hipotesis"].append(h) or True, "prueba")
    monkeypatch.setattr(CON, "consultar", consultar_falso({}))

    async def sin_ontologias(simbolos, terminos, cache):
        return []

    async def llamar_roto(self, rol, programa, **kwargs):
        raise RuntimeError("sin modelo")

    monkeypatch.setattr(PASOS.ONTO, "normalizar", sin_ontologias)
    monkeypatch.setattr(Ctx, "llamar", llamar_roto)
    decision = asyncio.run(PASOS._killer(ctx, h, "", None))
    x = next(y for y in al.estado["hipotesis"] if y["id"] == h["id"])
    # S-09 (17 de septiembre de 2026): sin juez no hay decisión. La hipótesis queda
    # pendiente de juicio (marca de revisión y un intento contado), no suspendida.
    assert decision == "pendiente" and x["perfilDiana"] is None and x["alternativas"] == []
    assert x["decisionKiller"] is None and x["_revisionPedida"] is True and x["_killerIntentos"] == 1
    assert not [d for d in al.estado["decisiones"] if d["hipotesisId"] == h["id"]]
    assert DI.texto_perfil(x["perfilDiana"]).startswith("Perfil de evidencia por diana: sin consultar")


# ---------------------------------------------------------------------------
# 6. Hechos que motivan una hipótesis nueva
# ---------------------------------------------------------------------------


def test_hechos_que_motivan_por_afirmacion_y_por_fuente():
    hechos = [
        {"id": "he-1", "investigacionId": "inv", "estado": "sabido", "afirmacionIds": ["af-1"], "procedencia": []},
        {"id": "he-2", "investigacionId": "inv", "estado": "abierto", "afirmacionIds": [], "procedencia": [{"fuenteId": "f-9", "referencia": "B", "pagina": None}]},
        {"id": "he-3", "investigacionId": "inv", "estado": "descartado", "afirmacionIds": ["af-1"], "procedencia": []},
        {"id": "he-4", "investigacionId": "otra", "estado": "sabido", "afirmacionIds": ["af-1"], "procedencia": []},
        {"id": "he-5", "investigacionId": "inv", "estado": "sabido", "afirmacionIds": "af-1", "procedencia": "texto"},
        None,
        "basura",
    ]
    respaldo = [{"id": "af-1", "fuenteId": "f-1"}, {"id": "af-2", "fuenteId": "f-9"}, None]
    assert PASOS.hechos_que_motivan(hechos, "inv", respaldo) == ["he-1", "he-2"]
    assert PASOS.hechos_que_motivan(hechos, "inv", []) == [] and PASOS.hechos_que_motivan(None, "inv", respaldo) == []
    assert PASOS.hechos_que_motivan(hechos, "inv", respaldo, maximo=1) == ["he-1"]


# ---------------------------------------------------------------------------
# 7. Conectores: gtex_gen y las claves de HPA, sin red
# ---------------------------------------------------------------------------


class _Respuesta:
    def __init__(self, cuerpo: Any) -> None:
        self._cuerpo = cuerpo
        self.status_code = 200
        self.text = "x"

    def json(self) -> Any:
        return self._cuerpo


def test_gtex_gen_y_hpa_expresion_sin_red(monkeypatch):
    from rosa.conectores import bases as B

    assert CON.REGISTRO["gtex_gen"].grupo == "expresion" and CON.REGISTRO["gtex_gen"].estado == "disponible"
    pedidas: list[dict[str, Any]] = []

    async def pedir_falso(metodo, url, limitador, **kwargs):
        pedidas.append({"url": url, **kwargs})
        if "reference/gene" in url:
            return _Respuesta({"data": [{"gencodeId": "ENSG00000131095.14", "geneSymbol": "GFAP", "geneType": "protein coding", "chromosome": "chr17", "start": 44903000, "end": 44916000, "strand": "-"}, {"gencodeId": "ENSG00000000001.1", "geneSymbol": "GFAP-AS1"}]})
        return _Respuesta({"Gene": "GFAP", "RNA tissue distribution": "Detected in many", "RNA brain regional distribution": "Detected in all", "RNA single nuclei brain specific nCPM": {"astrocyte": "9000.1"}, "RNA single cell type specific nCPM": {"Astrocytes": "5000"}, "Brain expression cluster": "Cluster 1: Astrocytes", "RNA tissue cell type enrichment": "brain - astrocytes", "Clave que no interesa": 1})

    monkeypatch.setattr(B, "pedir", pedir_falso)
    reg, datos = asyncio.run(CON.consultar("gtex_gen", resumen="GTEx GENCODE: GFAP", simbolo="GFAP"))
    assert reg["error"] is None and datos["gencode"] == "ENSG00000131095.14" and datos["simbolo"] == "GFAP" and reg["ids"] == ["ENSG00000131095.14"]
    assert reg["invariante"]["ok"] and pedidas[0]["params"] == {"geneId": "GFAP", "gencodeVersion": "v39", "genomeBuild": "GRCh38/hg38"}
    reg_h, hpa = asyncio.run(CON.consultar("hpa_expresion", resumen="HPA", ensembl="ENSG00000131095"))
    assert reg_h["error"] is None
    for clave in ("RNA tissue distribution", "RNA brain regional distribution", "RNA single nuclei brain specific nCPM", "RNA single cell type specific nCPM", "Brain expression cluster", "RNA tissue cell type enrichment"):
        assert clave in hpa
    assert "Clave que no interesa" not in hpa

    async def pedir_vacio(metodo, url, limitador, **kwargs):
        return _Respuesta({"data": []})

    monkeypatch.setattr(B, "pedir", pedir_vacio)
    reg2, datos2 = asyncio.run(CON.consultar("gtex_gen", resumen="x", simbolo="NOEXISTE"))
    assert datos2 is None and reg2["n"] == 0 and reg2["invariante"]["ok"] is False and reg2["error"] is None


# ---------------------------------------------------------------------------
# 8. Textos en castellano con tildes y sin guiones largos
# ---------------------------------------------------------------------------


def test_textos_nuevos_con_tildes_y_sin_guiones_largos():
    import inspect
    import re

    from rosa.conectores import bases as B

    fuentes = "\n".join(inspect.getsource(m) for m in (PASOS, K, F, B))
    assert "\u2014" not in fuentes
    sin_tilde = re.compile(r"\b(hipotesis|investigacion|version|codigo|ambito|explicacion|informacion|celula|tejido humano no comprobado|genetica humana|farmacologia|clasificacion)\b")
    nuevos = [PASOS.datasets_para_plan.__doc__, PASOS.clasificar_alternativa.__doc__, PASOS.anadir_alternativas.__doc__, PASOS.registrar_datasets_programa.__doc__, PASOS.hechos_que_motivan.__doc__, F.ProponerExperimento.__doc__, F.ExperimentoPropuesto.__doc__, F.AlternativaPropuesta.model_fields["texto"].description, F.ProponerPlan.model_fields["datasets_disponibles"].json_schema_extra["desc"]]
    for t in nuevos:
        assert t and not sin_tilde.search(t), t


# ---------------------------------------------------------------------------
# 9. Adversario: lo que se intentó romper después de la integración
# ---------------------------------------------------------------------------


def test_gtex_gen_no_toma_el_gencode_de_otro_gen_ni_rompe_con_respuestas_raras(monkeypatch):
    """GTEx busca por prefijo: al pedir GFAP devuelve también GFAP-AS1. Si no
    hay coincidencia exacta, no vale la primera fila (sería el GENCODE de OTRO
    gen y el perfil leería la expresión equivocada). Una respuesta con otra
    forma es 'no pude comprobar', no 'no resuelve'."""
    from rosa.conectores import bases as B

    async def solo_antisentido(metodo, url, limitador, **kwargs):
        return _Respuesta({"data": [{"gencodeId": "ENSG00000000001.1", "geneSymbol": "GFAP-AS1"}, {"gencodeId": "ENSG00000000002.1", "geneSymbol": "GFAPL"}]})

    monkeypatch.setattr(B, "pedir", solo_antisentido)
    reg, datos = asyncio.run(CON.consultar("gtex_gen", resumen="x", simbolo="GFAP"))
    assert datos is None and reg["error"] is None and reg["invariante"]["ok"] is False and "2 filas" in reg["invariante"]["detalle"]

    async def minusculas(metodo, url, limitador, **kwargs):
        return _Respuesta({"data": [{"gencodeId": "ENSG00000000001.1", "geneSymbol": "GFAP-AS1"}, {"gencodeId": "ENSG00000131095.14", "geneSymbol": "GFAP"}]})

    monkeypatch.setattr(B, "pedir", minusculas)
    reg, datos = asyncio.run(CON.consultar("gtex_gen", resumen="x", simbolo="gfap"))
    assert datos["gencode"] == "ENSG00000131095.14" and reg["invariante"]["ok"]

    async def sin_gencode(metodo, url, limitador, **kwargs):
        return _Respuesta({"data": [{"geneSymbol": "GFAP"}]})

    monkeypatch.setattr(B, "pedir", sin_gencode)
    reg, datos = asyncio.run(CON.consultar("gtex_gen", resumen="x", simbolo="GFAP"))
    assert datos is None and reg["error"] is None

    for cuerpo in ([1, 2], {"data": "texto"}, {"data": None}, "texto", {}):
        async def rara(metodo, url, limitador, **kwargs):
            return _Respuesta(cuerpo)

        monkeypatch.setattr(B, "pedir", rara)
        reg, datos = asyncio.run(CON.consultar("gtex_gen", resumen="x", simbolo="GFAP"))
        assert datos is None and reg["error"] and "No pude comprobar" in reg["error"], cuerpo


def test_datasets_para_plan_tolera_pregunta_id_y_estado_raros():
    for e in (None, {}, {"datasetsPrograma": "basura"}, {"datasetsPrograma": [None, "x", 7]}, "texto", []):
        for pregunta in (None, "", 5, ["hipocampo"], "hipocampo", "  "):
            for inv in ("inv", None, 3, ""):
                texto = PASOS.datasets_para_plan(e, inv, pregunta)  # type: ignore[arg-type]
                assert isinstance(texto, str) and texto
                assert "\u2014" not in texto
    # Una pregunta que no es texto no rompe y no inventa coincidencias.
    assert "coincide" not in PASOS.datasets_para_plan({}, "inv", 5).lower() or "Ningún dataset" in PASOS.datasets_para_plan({}, "inv", 5)


def test_contexto_de_bases_calcula_el_perfil_de_una_hipotesis_antigua_y_no_repite_si_esta_al_dia(monkeypatch):
    """Un registro anterior a la integración tiene `contextoBases` de su versión
    y ningún `perfilDiana`: sin este arreglo la comprobación contexto_humano se
    quedaba en 'no comprobable' para siempre (hasta reformular)."""
    al, ctx = _ctx()
    h = _hipotesis()
    h["contextoBases"] = {"diana": "GENHEP", "identificadores": {"simbolo": "GENHEP", "ensembl": "ENSG00000999999", "uniprot": "P99999"}, "funcion": "", "expresionCerebro": "", "interactores": [], "rutas": [], "version": 1, "consultadoEn": 1, "candidatos": ["GENHEP"]}
    h.pop("perfilDiana", None)
    al.mutar(lambda e: e["hipotesis"].append(h) or True, "prueba")
    consultar = consultar_falso(RESPUESTAS_GENHEP)
    monkeypatch.setattr(CON, "consultar", consultar)
    assert PASOS.contexto_al_dia(h) is False
    asyncio.run(PASOS.contexto_de_bases(ctx, h, None))
    x = next(y for y in al.estado["hipotesis"] if y["id"] == h["id"])
    assert isinstance(x["perfilDiana"], dict) and x["perfilDiana"]["version"] == 1 and x["contextoBases"]["identificadores"]["gencode"] == "ENSG00000999999.7"
    assert any(n == "hpa_expresion" for n, _ in consultar.llamadas)
    # Con el perfil de la versión actual ya calculado, no se vuelve a las bases.
    consultar.llamadas.clear()
    assert PASOS.contexto_al_dia(x) is True
    asyncio.run(PASOS.contexto_de_bases(ctx, x, None))
    assert consultar.llamadas == []
    # Registro roto: contextoBases como texto, tarjeta como texto. No rompe y se recalcula.
    h2 = _hipotesis(titulo="GENHEP y astrocitos")
    h2["contextoBases"] = "texto"
    h2["tarjeta"] = "texto"
    h2.pop("perfilDiana", None)
    al.mutar(lambda e: e["hipotesis"].append(h2) or True, "prueba")
    asyncio.run(PASOS.contexto_de_bases(ctx, h2, None))
    x2 = next(y for y in al.estado["hipotesis"] if y["id"] == h2["id"])
    assert isinstance(x2["contextoBases"], dict) and isinstance(x2["perfilDiana"], dict)
    # Diana que no resolvió a un gen: contexto al día sin perfil, no se vuelve a preguntar.
    h3 = _hipotesis(titulo="Sueño y memoria", tarjeta={"diana": "sueño", "celula": "", "etapa": "", "intervencion": "", "direccion": "sin_intervencion", "prediccionFalsable": "x", "riesgos": [], "pasoRuta": "mecanismo"}, comprobacion={"biomarcador": "", "cohorte": "", "diseno": ""})
    h3["contextoBases"] = {"diana": "sueño", "identificadores": {}, "funcion": "", "expresionCerebro": "", "interactores": [], "rutas": [], "version": 1, "consultadoEn": 1, "candidatos": []}
    h3["perfilDiana"] = None
    assert PASOS.contexto_al_dia(h3) is True
    # Perfil de otra versión: hay que recalcular.
    h4 = dict(x)
    h4["perfilDiana"] = {**x["perfilDiana"], "version": 0}
    assert PASOS.contexto_al_dia(h4) is False


def test_registrar_datasets_programa_con_mutacion_rota_o_fila_que_lanza(monkeypatch):
    al, ctx = _ctx()
    series = [{"accession": "GSE5281", "titulo": "Alzheimer brain", "n_muestras": "161"}, {"accession": "GSE174367", "titulo": "Single-nucleus Alzheimer", "n_muestras": "40"}]
    from rosa import datasets_programa as DP

    original = DP.desde_geo

    def desde_geo_roto(e, accession, datos, inv, ahora):
        if accession == "GSE5281":
            raise ValueError("fila envenenada")
        return original(e, accession, datos, inv, ahora)

    monkeypatch.setattr(DP, "desde_geo", desde_geo_roto)
    assert PASOS.registrar_datasets_programa(ctx, series, [], None) == 1
    assert [r["accession"] for r in al.estado["datasetsPrograma"]] == ["GSE174367"]
    monkeypatch.setattr(DP, "desde_geo", original)

    def mutar_roto(fn, nombre="bucle"):
        raise RuntimeError("cerrojo roto")

    monkeypatch.setattr(ctx, "mutar", mutar_roto)
    assert PASOS.registrar_datasets_programa(ctx, series, [], None) == 0


def test_killer_con_registro_antiguo_sin_claves_nuevas_y_juez_con_alternativas_como_cadenas(monkeypatch):
    """Una hipótesis guardada antes de la integración: sin perfilDiana, sin ruta,
    con alternativas como basura y contextoBases ya de su versión. Un programa
    antiguo del juez devuelve las alternativas como cadenas. Nada rompe y las
    claves nuevas quedan con su forma."""
    al, ctx = _ctx()
    h = _hipotesis()
    h["contextoBases"] = {"diana": "GENHEP", "identificadores": {"simbolo": "GENHEP", "ensembl": "ENSG00000999999", "uniprot": "P99999"}, "funcion": "", "expresionCerebro": "", "interactores": [], "rutas": [], "version": 1, "consultadoEn": 1, "candidatos": ["GENHEP"]}
    for clave in ("perfilDiana", "ruta"):
        h.pop(clave, None)
    h["alternativas"] = "basura"
    al.mutar(lambda e: e["hipotesis"].append(h) or True, "prueba")
    monkeypatch.setattr(CON, "consultar", consultar_falso(RESPUESTAS_GENHEP))

    async def sin_ontologias(simbolos, terminos, cache):
        return []

    monkeypatch.setattr(PASOS.ONTO, "normalizar", sin_ontologias)

    async def llamar_antiguo(self, rol, programa, **kwargs):
        if programa is self.programas.killer:
            revision = SimpleNamespace(comprobaciones=[F.ComprobacionKiller(comprobacion="falsabilidad", resultado="pasa", detalle="ok")], supuesto_invalidante="", alternativas=["Causa inversa: el daño eleva GENHEP", "", None, "Causa inversa: el daño eleva GENHEP"], reformulacion_sugerida="", que_haria_falta="", contradice_a=[], resumen="r")
            return SimpleNamespace(revision=revision)
        raise RuntimeError("sin modelo")

    monkeypatch.setattr(Ctx, "llamar", llamar_antiguo)
    asyncio.run(PASOS._killer(ctx, h, "", None))
    x = next(y for y in al.estado["hipotesis"] if y["id"] == h["id"])
    assert isinstance(x["perfilDiana"], dict) and x["perfilDiana"]["version"] == 1
    assert isinstance(x["ruta"], dict) and x["ruta"]["hipotesisId"] == h["id"]
    assert x["alternativas"] == [{"texto": "Causa inversa: el daño eleva GENHEP", "clase": "causa_inversa", "queLaDistinguiria": "", "iteracion": 1}]
    d = next(d for d in reversed(al.estado["decisiones"]) if d["hipotesisId"] == h["id"])
    assert any(c["comprobacion"] == "contexto_humano" and c["resultado"] == "falla" for c in d["comprobaciones"])


def test_la_linea_del_registro_con_hechos_la_lee_la_regla_de_cifras():
    from rosa import cifras_aprendizaje as CA

    ids = PASOS.hechos_que_motivan([{"id": "he-1", "investigacionId": "inv", "estado": "sabido", "afirmacionIds": ["af-1"], "procedencia": []}, {"id": "he-10", "investigacionId": "inv", "estado": "sabido", "afirmacionIds": ["af-2"], "procedencia": []}], "inv", [{"id": "af-2", "fuenteId": "f"}])
    assert ids == ["he-10"]
    linea = "iteración 2: generar -> Título a partir de los hechos " + ", ".join(ids)
    huella = CA._huellas_hipotesis({"id": "hip-1", "afirmaciones": [], "procedencia": {"fuentes": [], "mensajes": [], "registro": [linea]}})
    assert CA._nombrado_en(huella["texto"], "he-10") and not CA._nombrado_en(huella["texto"], "he-1")


def test_las_alternativas_del_juez_con_forma_rara_no_tumban_al_killer():
    for raro in (None, "texto", 7, {"texto": "x"}, [7, {"sin_texto": 1}, {"texto": 5}], [{"texto": None, "que_la_distinguiria": None}]):
        salida = PASOS.alternativas_de_revision(raro)
        assert isinstance(salida, list) and all(isinstance(a["texto"], str) and a["texto"] for a in salida)
    assert PASOS.alternativas_de_revision([{"texto": 5}]) == [{"texto": "5", "queLaDistinguiria": ""}]
    x: dict[str, Any] = {"alternativas": [{"texto": 5}, {"texto": "a", "clase": "otra"}]}
    assert PASOS.anadir_alternativas(x, [{"texto": "A", "queLaDistinguiria": ""}], 2) == 0
