"""El Wet-Lab Dossier: el expediente con el que una hipotesis sale al
laboratorio (ROSA2018, etapa 8).

Se arma sin ningun modelo, a partir del estado, en siete partes en el orden
en que las lee quien va a ejecutar el experimento: primero si va o no va y
por que; despues la hipotesis exacta con su version; la evidencia con
procedencia; los analisis con datos; las decisiones que la trajeron hasta
aqui; el protocolo prerregistrado; y que se aprende con cada resultado
posible. Lo que falta se dice ("sin analisis con datos"), no se rellena.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rosa import politicas
from rosa.priorizacion import cohortes_de

ETIQUETA_BLOQUEO = {
    "trazabilidad_insuficiente": "Trazabilidad insuficiente: no hay afirmaciones sostenidas o alguna esta bloqueada",
    "datos_no_autorizados": "Datos no autorizados: algun analisis uso un dataset sin aprobar o sin permiso de uso con IA",
    "analisis_invalido": "Analisis invalido segun el auditor",
    "sin_experimento_interpretable": "Sin experimento interpretable: faltan los criterios de confirmacion o refutacion",
    "descartada_por_killer": "Descartada en este contexto",
    "fuente_retractada": "Depende de una fuente retractada",
}

APRENDIZAJE_POR_RESULTADO = {
    "apoyo_reproducido": "Sube la certeza de la hipotesis; la conclusion se rehace con el dato como evidencia directa; se propone replicar en una cohorte distinta.",
    "negativo_interpretable": "Baja la certeza o cambia la direccion; la hipotesis se marca para descartar en este contexto o reformular; el negativo entra al modelo de mundo como hecho.",
    "inconcluso": "No cambia la creencia; se anota que el ensayo no tuvo potencia o los datos no alcanzaron el criterio; se propone repetir con mas muestra.",
    "fallo_tecnico": "No toca la hipotesis: el experimento no se ejecuto como se prerregistro. Se registra el fallo y se puede repetir.",
    "toxicidad_inviabilidad": "Cierra la via de intervencion en este contexto; la hipotesis puede seguir viva como mecanismo, no como intervencion.",
    "correccion_contexto": "El resultado dice que la hipotesis aplica a otro contexto (otra celula, etapa o poblacion): se crea una hipotesis derivada con el contexto corregido y la original se suspende.",
}


def _fecha(t: int | None) -> str:
    return datetime.fromtimestamp(t / 1000).strftime("%d/%m/%Y %H:%M") if t else "sin fecha"


def texto_dossier(e: dict[str, Any], h: dict[str, Any], inv: dict[str, Any] | None, corrida: dict[str, Any] | None, ahora: int) -> str:
    L: list[str] = []
    bloqueos = h.get("bloqueos", [])
    tarjeta = h.get("tarjeta") or {}
    k = h.get("conclusion") or {}
    mision = (inv or {}).get("mision") or {}
    decisiones = [d for d in e.get("decisiones", []) if d["hipotesisId"] == h["id"]]
    planes = {p["id"]: p for p in e.get("planesAnalisis", [])}
    ejecuciones = [x for x in e.get("ejecuciones", []) if x.get("hipotesisId") == h["id"]]
    x = h.get("experimento") or {}

    L += [f"# Dossier para el laboratorio: {h['titulo']}", "", f"Generado el {_fecha(ahora)}. Hipotesis {h['id']}, version {h.get('version', 1)}. Investigacion: {(inv or {}).get('titulo', '')}."]
    if corrida and corrida.get("arnes"):
        a = corrida["arnes"]
        L.append(f"Rosa: commit {a.get('commit')}, firmas {a.get('firmas')}, programas optimizados {a.get('optimizados')}.")

    # 1. Decision
    L += ["", "## 1. Decision de priorizacion"]
    if bloqueos:
        L.append("NO es candidata al laboratorio. Bloqueos no compensables:")
        L += [f"- {ETIQUETA_BLOQUEO.get(b, b)}" for b in bloqueos]
    elif h.get("candidata"):
        L.append(f"Candidata al laboratorio en este ciclo (maximo {politicas.MAX_CANDIDATOS_LABORATORIO} por ciclo, con diversidad entre clusters).")
    else:
        L.append("Sin bloqueos, pero hoy no esta entre las candidatas (otras puntuan mas o el Killer no la dejo avanzar todavia).")
    L.append(f"Estado: {h['estado']}. Elo {h['elo']} tras {len(h.get('partidos', []))} partidos. Decision del Killer sobre esta version: {h.get('decisionKiller') or 'pendiente'}.")
    if k:
        L.append(f"Conclusion de Rosa: certeza {k.get('certeza')}, direccion {k.get('direccion')}. {k.get('enunciado', '')}")

    # 2. Hipotesis
    L += ["", "## 2. La hipotesis (contrato completo)", f"Titulo: {h['titulo']}", f"Enunciado: {h['enunciado']}", f"Mecanismo: {h['mecanismo']}"]
    if tarjeta:
        L += [
            f"Diana o proceso: {tarjeta.get('diana') or 'sin especificar'}",
            f"Celula o tejido: {tarjeta.get('celula') or 'sin especificar'}",
            f"Etapa: {tarjeta.get('etapa') or 'sin especificar'}",
            f"Intervencion: {tarjeta.get('intervencion') or 'ninguna'} ({tarjeta.get('direccion', 'sin_intervencion')})",
            f"Prediccion falsable: {tarjeta.get('prediccionFalsable') or 'SIN PREDICCION FALSABLE'}",
            "Riesgos: " + ("; ".join(tarjeta.get("riesgos", [])) or "ninguno declarado"),
            f"Paso de la ruta terapeutica: {tarjeta.get('pasoRuta', 'mecanismo').replace('_', ' ')}. Completar este paso no completa la ruta (mecanismo, opciones de intervencion, compromiso de diana, efecto funcional, selectividad y toxicidad, exposicion, replicacion independiente, evidencia en la poblacion).",
        ]
    else:
        L.append("Sin tarjeta de hipotesis: falta el contrato minimo (diana, celula, etapa, intervencion, prediccion falsable).")
    c = h["comprobacion"]
    L.append(f"Comprobacion propuesta: biomarcador {c['biomarcador']}; cohorte {c['cohorte']}; diseño {c['diseno']}.")
    if mision:
        L.append(f"Encaje con la mision: poblacion {mision.get('poblacion') or '?'}; etapa {mision.get('etapa') or '?'}; celula o tejido {mision.get('celulaTejido') or '?'}; mecanismo {mision.get('mecanismo') or '?'}; intervencion {mision.get('tipoIntervencion') or '?'}.")
    if h.get("versiones"):
        L.append("Versiones anteriores:")
        for v in h["versiones"]:
            L.append(f"- v{v['n']} ({_fecha(v['fecha'])}, {v['quien']}): {v['titulo']}. Motivo del cambio: {v['motivo']}")
    if h.get("derivadaDe"):
        L.append(f"Derivada de: {h['derivadaDe']}")

    # 3. Evidencia
    sostenidas = [a for a in h["afirmaciones"] if a["veredicto"] in ("sostenida", "parcial")]
    otras = [a for a in h["afirmaciones"] if a["veredicto"] not in ("sostenida", "parcial")]
    cohortes = cohortes_de(h)
    L += ["", "## 3. Evidencia con procedencia", f"{len(sostenidas)} afirmaciones sostenidas o parciales de {len(h['afirmaciones'])}; {len(h['procedencia']['fuentes'])} fuentes; {len(cohortes)} cohortes distintas identificadas" + (f" ({', '.join(cohortes)})" if cohortes else "") + "."]
    for a in sostenidas:
        clase = a.get("clase") or ("dato" if a["tipo"] == "dato" else "literatura")
        L.append(f"- [{a['veredicto']}, {a['tipo']}, clase {clase}{', SINTETICO' if a.get('sintetico') else ''}] {a['texto']} {a['cita']}")
        if a.get("fragmento"):
            L.append(f"    Pasaje literal: \"{a['fragmento'][:300]}\"")
    if otras:
        L.append("Afirmaciones que no se sostienen o no se pudieron comprobar (no cuentan como evidencia):")
        L += [f"- [{a['veredicto']}] {a['texto']} {a['cita']} ({a['motivo']})" for a in otras]
    retractadas = [f for f in h["procedencia"]["fuentes"] if f.get("retraccion")]
    if retractadas:
        L.append("Fuentes con marca editorial: " + "; ".join(f"{f['referencia']} ({f['retraccion']})" for f in retractadas))
    if h.get("supuestos"):
        L.append("Supuestos evaluados:")
        L += [f"- [{s['estado']}] {s['texto']} ({s['evidencia']})" for s in h["supuestos"]]
    n = h.get("novedad", {})
    if n:
        L.append("Novedad: " + "; ".join(f"{clave} {v['estado']}: {v['detalle'][:120]}" for clave, v in n.items()))

    # 4. Analisis con datos
    L += ["", "## 4. Analisis in silico"]
    if not ejecuciones:
        L.append("Sin analisis con datos. La hipotesis se apoya solo en literatura.")
    for run in ejecuciones:
        plan = planes.get(run["planId"], {})
        L.append(f"- Ejecucion {run['id']} ({_fecha(run['inicio'])}): estado {run['estado']}; plan congelado el {_fecha(plan.get('congeladoEn'))}; pregunta: {plan.get('pregunta', '')}; prueba: {plan.get('prueba', '')}; baseline: {plan.get('baseline', '')}; semilla {run['semilla']}; datos sha256 {run['hashDatos'][:12]}.")
        if run.get("resultados"):
            L.append("    Resultados: " + "; ".join(f"{k2}={v}" for k2, v in run["resultados"].items()))
        if run.get("baseline"):
            L.append("    Baseline: " + "; ".join(f"{k2}={v}" for k2, v in run["baseline"].items()))
        if run.get("interpretacion"):
            L.append(f"    Interpretacion: {run['interpretacion']['estado']}. {run['interpretacion']['resumen']}")
        if run.get("auditoria"):
            au = run["auditoria"]
            L.append(f"    Auditoria (Killer II, {au['quien']}): {au['veredicto']}. {au['motivo']}")
            L += [f"      - {cmp['comprobacion']}: {cmp['resultado']}. {cmp['detalle']}" for cmp in au.get("comprobaciones", [])]
        if run.get("error"):
            L.append(f"    Error tecnico: {run['error'][:300]}")

    # 5. Decisiones
    L += ["", "## 5. Decisiones registradas"]
    if not decisiones:
        L.append("Ninguna decision registrada todavia.")
    for d in decisiones:
        L.append(f"- {_fecha(d['fecha'])} · {d['etapa']} · v{d['version']} · {d['decision']} · {d['quien']}: {d['motivo']}")
        for cmp in d.get("comprobaciones", []):
            if cmp["resultado"] in ("falla", "no_comprobable"):
                L.append(f"    - {cmp['comprobacion']}: {cmp['resultado']}. {cmp['detalle'][:200]}")
        if d.get("auditoria"):
            L.append(f"    Auditoria ({d['auditoria']['quien']}): {'de acuerdo' if d['auditoria']['acuerdo'] else 'EN DESACUERDO'}. {d['auditoria']['motivo'][:200]}")
    if h.get("revisionesHumanas"):
        L.append("Revisiones escritas por personas:")
        for r in h["revisionesHumanas"]:
            L.append(f"- {r['quien']} ({_fecha(r['fecha'])}): supuestos cuestionados: {r['supuestosCuestionados']}; literatura que falta: {r['literaturaQueFalta']}; problema experimental: {r['problemaExperimental']}")

    # 6. Experimento
    L += ["", "## 6. Experimento propuesto y prerregistro"]
    if not x:
        L.append("Sin experimento propuesto.")
    else:
        L += ["Protocolo:", x.get("protocolo", ""), f"Ensayo: {x.get('ensayo', '')}", f"Controles: {x.get('controles') or 'no declarados'}", f"Tamaño muestral: {x.get('tamanoMuestral') or 'no declarado'}", f"Alternativa y como se distingue: {x.get('alternativa') or 'no declarada'}", f"La CONFIRMA si: {x.get('confirma') or 'sin criterio'}", f"La REFUTA si: {x.get('refuta') or 'sin criterio'}", f"Que decision cambia con el resultado: {x.get('decisionQueCambia') or 'no declarado'}", f"Coste estimado: {x.get('costeEstimado', '')}"]
        if x.get("analisisPedido"):
            L.append(f"Con datos existentes: {x['analisisPedido']}")
        if x.get("prerregistradoEn"):
            L.append(f"Prerregistrado el {_fecha(x['prerregistradoEn'])} (artefacto {x.get('prerregistroArtefactoId')}). Asignado a: {x.get('laboratorio')}.")
        else:
            L.append("Todavia no prerregistrado: al asignarlo a un laboratorio se congela.")
        if x.get("resultado"):
            r = x["resultado"]
            L.append(f"Resultado recibido ({_fecha(r['fecha'])}): {r['veredicto']} / {r.get('clasificacion', 'sin clasificar')}. {r['resultado']}")
            if r.get("dimensiones"):
                d = r["dimensiones"]
                activas = [k for k, v in d.items() if k != "nota" and v]
                L.append("Dimensiones que coexisten: " + (", ".join(activas) or "ninguna") + (f". {d.get('nota', '')}" if d.get("nota") else ""))
            if r.get("versionProbada"):
                L.append(f"Probo la version {r['versionProbada']} de la hipotesis" + ("" if r.get("compatibleConActual", True) else f" (la actual es la {h.get('version', 1)}: comprobar compatibilidad)") + ".")
    if mision.get("capacidadesLaboratorio"):
        L.append("Capacidades declaradas del laboratorio: " + "; ".join(mision["capacidadesLaboratorio"]))

    # 7. Riesgos y aprendizaje
    L += ["", "## 7. Riesgos, alternativas y que se aprende con cada resultado"]
    if tarjeta.get("riesgos"):
        L += [f"- Riesgo: {r}" for r in tarjeta["riesgos"]]
    if k:
        L += [f"De que depende mas: {k.get('loMasFragil', '')}", f"Subiria la certeza si: {k.get('subiria', '')}", f"Bajaria si: {k.get('bajaria', '')}"]
        if k.get("enContra"):
            L.append("En contra: " + " | ".join(k["enContra"]))
    L.append("Que hace Rosa con cada resultado posible del laboratorio:")
    L += [f"- {nombre.replace('_', ' ')}: {texto}" for nombre, texto in APRENDIZAJE_POR_RESULTADO.items()]
    L += ["", "Lo que se analice fuera del prerregistro se reporta como exploratorio. Este dossier describe el estado de la evidencia en la fecha indicada; no es una recomendacion clinica."]
    return "\n".join(L)
