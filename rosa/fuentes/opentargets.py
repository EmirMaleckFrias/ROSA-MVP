"""Open Targets Platform (GraphQL): si una diana ya esta asociada al
Alzheimer y con que puntuacion. Alzheimer es MONDO_0004975 (EFO_0000249 es
su equivalente antiguo). Sin clave.
"""

from __future__ import annotations

from typing import Any

from rosa.fuentes.base import Limitador, pedir

URL = "https://api.platform.opentargets.org/api/v4/graphql"
_limitador = Limitador(2.0)
ALZHEIMER = "MONDO_0004975"

_BUSCAR = """
query ($q: String!) { search(queryString: $q, entityNames: ["target"], page: {index: 0, size: 3}) { hits { id name entity } } }
"""
_ASOCIACION = """
query ($id: String!, $enf: [String!]) {
  target(ensemblId: $id) {
    id approvedSymbol approvedName
    associatedDiseases(Bs: $enf, page: {index: 0, size: 5}) { count rows { score disease { id name } datatypeScores { id score } } }
  }
}
"""


async def asociacion_alzheimer(simbolo: str) -> dict[str, Any]:
    """{simbolo, ensembl, puntuacion (0 a 1 o None), tipos: {datatype: score}}.
    puntuacion None con `encontrado` True significa "sin asociacion registrada"."""
    r = await pedir("POST", URL, _limitador, json={"query": _BUSCAR, "variables": {"q": simbolo}})
    hits = r.json().get("data", {}).get("search", {}).get("hits", [])
    hit = next((h for h in hits if h.get("name", "").upper() == simbolo.upper()), hits[0] if hits else None)
    if not hit:
        return {"simbolo": simbolo, "ensembl": None, "encontrado": False, "puntuacion": None, "tipos": {}}
    r2 = await pedir("POST", URL, _limitador, json={"query": _ASOCIACION, "variables": {"id": hit["id"], "enf": [ALZHEIMER, "EFO_0000249"]}})
    t = r2.json().get("data", {}).get("target") or {}
    filas = (t.get("associatedDiseases") or {}).get("rows") or []
    if not filas:
        return {"simbolo": t.get("approvedSymbol", simbolo), "ensembl": hit["id"], "encontrado": True, "puntuacion": None, "tipos": {}}
    mejor = max(filas, key=lambda f: f.get("score", 0))
    return {"simbolo": t.get("approvedSymbol", simbolo), "ensembl": hit["id"], "encontrado": True, "puntuacion": round(float(mejor.get("score", 0)), 3), "tipos": {d["id"]: round(float(d["score"]), 3) for d in mejor.get("datatypeScores", [])}, "enfermedad": mejor.get("disease", {}).get("name")}
