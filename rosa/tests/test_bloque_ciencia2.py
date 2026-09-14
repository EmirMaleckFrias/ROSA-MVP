"""Ontologias, coste por decision, RO-Crate, politica de contexto y nivel de autonomia."""

import json
import zipfile
import io

from rosa import causal as CAUSAL
from rosa import costes as C
from rosa import ontologias as ONTO
from rosa import politicas
from rosa import rocrate as RC
from rosa.estado import acciones as A
from rosa.estado import plantilla as P


def test_diccionario_curado_resuelve_sin_red_y_fusiona_alias():
    ents = ONTO.anotar_curadas("Plasma GFAP rises in astrocytes of Alzheimer disease before NfL; p-tau181 follows in the hippocampus")
    ids = ONTO.ids_de(ents)
    assert {"HGNC:4235", "CL:0000127", "MONDO:0004975", "HGNC:7739", "HGNC:6893", "UBERON:0002421", "UBERON:0001969"} <= ids
    tipos = {x["id"]: x["tipo"] for x in ents}
    assert tipos["HGNC:4235"] == "gen" and tipos["CL:0000127"] == "celula" and tipos["UBERON:0002421"] == "tejido"
    fus = ONTO.fusionar(ents, [{"texto": "GFAP", "id": "HGNC:4235", "simbolo": "GFAP", "nombre": "glial fibrillary acidic protein", "uniprot": "P14136", "ensembl": "ENSG00000131095", "alias": ["FLJ45472"], "ontologia": "HGNC", "tipo": "gen"}])
    gfap = next(x for x in fus if x["id"] == "HGNC:4235")
    assert gfap["uniprot"] == "P14136" and "FLJ45472" in gfap["alias"] and len([x for x in fus if x["id"] == "HGNC:4235"]) == 1
    # Dos hipotesis que comparten dos identificadores hablan quiza de lo mismo.
    a = ONTO.anotar_curadas("GFAP en astrocitos")
    b = ONTO.anotar_curadas("glial fibrillary acidic protein and astrocyte activation")
    assert ONTO.comparten(a, b) == ["CL:0000127", "HGNC:4235"]
    assert ONTO.comparten(a, ONTO.anotar_curadas("solo tau")) == []


def test_nodos_causales_llevan_identificador_canonico():
    h = {"tarjeta": {"diana": "GFAP", "intervencion": "GFAP", "direccion": "sin_intervencion"}, "comprobacion": {"biomarcador": "NfL"}, "afirmaciones": [], "titulo": "GFAP precede a NfL", "enunciado": "GFAP precede a NfL"}
    g = CAUSAL.grafo_local(h, [], None, 1)
    por_id = {n["id"]: n for n in g["nodos"]}
    assert por_id["X"].get("idCanonico") == "HGNC:4235" and por_id["Y"].get("idCanonico") == "HGNC:7739"


def test_costes_por_decision_incluyen_revision_humana():
    e = P.estado_inicial()
    A.crear_investigacion(e, {"titulo": "T", "objetivo": "O", "condicionParada": "1 iteraciones"}, 1)
    inv = e["investigaciones"][0]
    c = P.nueva_corrida(inv["id"], 1, 1)
    c["gasto"]["usd"] = 12.0
    c["gasto"]["llamadas"] = 40
    e["corridas"].append(c)
    h = P.nueva_hipotesis(inv["id"], 1, 1, titulo="H", enunciado="E", mecanismo="M")
    h["candidata"] = True
    e["hipotesis"].append(h)
    d = A.registrar_decision(e, h, "persona", "aprobar", "ok", "Dra. X", 2, [])
    d["segundosRevision"] = 1800
    A.guardar_artefacto(e, inv["id"], "Dossier: H", "dossier", "texto", "d", 1, 3, procedencia={"mensajes": {"hipotesis": h["id"]}})
    llamadas = {c["id"]: [{"modelo": "anthropic/claude-opus-5", "rol": "juez", "iteracion": 1, "tokensEntrada": 1000, "tokensSalida": 100, "ms": 10}] * 2}
    r = C.costes_de_investigacion(e, inv["id"], llamadas)
    assert r["usdModelo"] == 12.0 and r["horasRevision"] == 0.5 and r["usdRevision"] == 0.5 * politicas.TARIFA_HORA_REVISION_USD
    assert r["usdTotal"] == round(12.0 + 0.5 * politicas.TARIFA_HORA_REVISION_USD, 2)
    assert r["hipotesisConDossier"] == 1 and r["usdPorDossier"] == r["usdTotal"] and r["usdPorDecisionHumana"] == r["usdTotal"] and r["usdPorCandidata"] == r["usdTotal"]
    assert r["porIteracion"][0]["llamadas"] == 2 and r["porIteracion"][0]["usd"] > 0
    assert d["contexto"]["hechos"] == 0 and d["contexto"]["hipotesisVivas"] == 1


def test_rocrate_con_prov_y_sello():
    e = P.estado_inicial()
    A.crear_investigacion(e, {"titulo": "T", "objetivo": "O", "condicionParada": "1 iteraciones"}, 1)
    inv = e["investigaciones"][0]
    e["corridas"].append(P.nueva_corrida(inv["id"], 1, 1))
    h = P.nueva_hipotesis(inv["id"], 1, 1, titulo="H", enunciado="E", mecanismo="M")
    h["experimento"] = {"protocolo": "p", "ensayo": "e", "costeEstimado": "c", "laboratorio": None, "estado": "propuesto", "ficheroDatos": None, "analisisPedido": ""}
    e["hipotesis"].append(h)
    A.registrar_decision(e, h, "killer_1", "avanzar", "ok", "Rosa", 2, [{"comprobacion": "novedad", "resultado": "pasa", "detalle": ""}])
    A.asignar_experimento(e, h["id"], "FLENI", 3)
    A.registrar_sello_externo(e, h["id"], {"algoritmo": "sha256", "hash": "ab" * 32, "ok": True, "testigos": ["freeTSA"], "primeraHora": "2026-09-14T14:01:59Z", "pedidoEn": 3, "error": None, "sellos": [{"tsa": "freeTSA", "url": "https://freetsa.org/tsr", "ok": True, "genTime": "2026-09-14T14:01:59Z", "serial": "1", "tsrBase64": "AAEC"}]}, 4)
    run = P.nueva_ejecucion(inv["id"], h["id"], "plan-1", "hipotesis", "print('RESULTADO x=1')", 7, "cafe" * 16, 5)
    run["estado"] = "completado"
    e.setdefault("ejecuciones", []).append(run)
    crate = RC.armar(e, h, 10)
    nombres = set(crate["ficheros"])
    assert {"ro-crate-metadata.json", "prov.json", "hipotesis.json", "dossier.md", "prerregistro.md", "fuentes.csv", "decisiones.json", "README.md", "sello/freeTSA.tsr", f"ejecuciones/{run['id']}.py", f"ejecuciones/{run['id']}.json"} <= nombres
    meta = crate["metadata"]
    raiz = next(g for g in meta["@graph"] if g["@id"] == "./")
    assert raiz["conformsTo"]["@id"] == RC.PERFIL and {p["@id"] for p in raiz["hasPart"]} >= {"prerregistro.md", "dossier.md"}
    acciones = [g for g in meta["@graph"] if g.get("@type") in ("CreateAction", "AssessAction") or (isinstance(g.get("@type"), list) and "LabProcess" in g["@type"])]
    assert any(g["@id"].startswith("#ejecucion-") and g["instrument"]["@id"].startswith("#sandbox") for g in acciones)
    assert any("LabProcess" in (g.get("@type") or []) for g in acciones)
    ds = next(g for g in meta["@graph"] if g["@id"].startswith("#dataset-"))
    assert ds["sha256"] == "cafe" * 16 and "no incluido" in ds["name"]
    prov = crate["prov"]
    assert "rosa:Rosa" in prov["agent"] and any(k.startswith("rosa:ejecucion-") for k in prov["activity"]) and prov["wasAttributedTo"]
    z = zipfile.ZipFile(io.BytesIO(RC.zip_bytes(crate)))
    assert json.loads(z.read("ro-crate-metadata.json"))["@context"] == RC.CONTEXTO
    assert z.read("sello/freeTSA.tsr") == b"\x00\x01\x02"


def test_nivel_de_autonomia_declarado_y_politicas():
    assert politicas.NIVEL_AUTONOMIA_DECLARADO == 2
    t = politicas.nivel_autonomia_texto()
    assert "Nivel 2 de 5" in t and "Autonomia parcial" in t
    r = politicas.resumen()
    assert r["nivelAutonomiaDeclarado"] == 2 and len(r["nivelesAutonomia"]) == 6 and r["tarifaHoraRevisionUsd"] > 0
