"""ClinicalTrials.gov API v2. Sin clave. Sin cifra oficial de limite: 1 por
segundo es prudente. `query.cond` y `query.intr` en sintaxis Essie;
`fields` con nombres de pieza; `countTotal=true` para el total.
"""

from __future__ import annotations

from typing import Any

from rosa.fuentes.base import Limitador, pedir

BASE = "https://clinicaltrials.gov/api/v2/studies"
_limitador = Limitador(1.0)

CAMPOS = "NCTId,BriefTitle,OverallStatus,Phase,Condition,InterventionName,PrimaryOutcomeMeasure,StartDate,LeadSponsorName,StudyType"


async def buscar(condicion: str, termino: str = "", intervencion: str = "", maximo: int = 50) -> tuple[list[dict[str, Any]], int]:
    params: dict[str, Any] = {"query.cond": condicion, "pageSize": min(maximo, 1000), "countTotal": "true", "fields": CAMPOS}
    if termino:
        params["query.term"] = termino
    if intervencion:
        params["query.intr"] = intervencion
    r = await pedir("GET", BASE, _limitador, params=params)
    d = r.json()
    estudios = []
    for s in d.get("studies", []):
        p = s.get("protocolSection", {})
        estudios.append(
            {
                "nct": p.get("identificationModule", {}).get("nctId"),
                "titulo": p.get("identificationModule", {}).get("briefTitle", ""),
                "estado": p.get("statusModule", {}).get("overallStatus"),
                "fases": p.get("designModule", {}).get("phases", []),
                "tipo": p.get("designModule", {}).get("studyType"),
                "condiciones": p.get("conditionsModule", {}).get("conditions", []),
                "intervenciones": [i.get("name") for i in p.get("armsInterventionsModule", {}).get("interventions", [])],
                "desenlaces": [o.get("measure") for o in p.get("outcomesModule", {}).get("primaryOutcomes", [])],
                "inicio": p.get("statusModule", {}).get("startDateStruct", {}).get("date"),
                "patrocinador": p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name"),
            }
        )
    return estudios, int(d.get("totalCount", len(estudios)) or 0)


async def por_nct(nct: str) -> dict[str, Any] | None:
    r = await pedir("GET", f"{BASE}/{nct}", _limitador, params={"fields": CAMPOS})
    s = r.json()
    p = s.get("protocolSection", {})
    if not p:
        return None
    return {"nct": p.get("identificationModule", {}).get("nctId"), "titulo": p.get("identificationModule", {}).get("briefTitle", ""), "estado": p.get("statusModule", {}).get("overallStatus"), "fases": p.get("designModule", {}).get("phases", [])}
