"""El revisor de registro (lo que Claude Science llama RequestReview): al
cerrar una iteracion y al generar un dossier, se compara lo que Rosa dice
con lo que el registro prueba. Seis clases de hallazgo, las mismas que el
revisor de Claude Science detecta:

- calculo_no_ejecutado: se afirma un resultado o una ejecucion que no consta.
- contradiccion_con_registro: una cifra o un hecho contradice un fichero,
  una ejecucion o una afirmacion verificada.
- cita_sin_soporte: se cita una fuente que no esta en el registro o que no
  dice eso.
- identificador_no_coincide: un DOI, PMID, NCT o GSE que no aparece en las
  fuentes ni en las consultas.
- paso_incompleto: el plan tiene pasos sin terminar y el resumen no lo dice.
- conclusion_no_sigue: la conclusion afirma mas de lo que el metodo permite.

Primero las comprobaciones por regla (cifras e identificadores contra el
registro, verbos de ejecucion contra las ejecuciones, pasos del plan);
despues el juez lee resumen y registro y anade lo que la regla no ve. Un
hallazgo no borra nada: queda a la vista con su clase y su gravedad, y la
iteracion se marca "con hallazgos" hasta que alguien los atienda.
"""

from __future__ import annotations

import re
from typing import Any

CLASES = ("calculo_no_ejecutado", "contradiccion_con_registro", "cita_sin_soporte", "identificador_no_coincide", "paso_incompleto", "conclusion_no_sigue")

_NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{2,}(?:[.,]\d+)?|\d[.,]\d+|[.,]\d+)(?![\w])")
_DOI = re.compile(r"10\.\d{4,9}/[^\s\]\)>,;]+", re.I)
_NCT = re.compile(r"NCT\d{8}")
_GSE = re.compile(r"GSE\d{3,7}")
_PMID = re.compile(r"PMID[:\s]*(\d{6,9})", re.I)
_EJECUCION = re.compile(r"\b(se ejecut\w*|se reprodu\w*|se calcul\w*|corri[oó]|se analiz\w*|analisis in silico|sandbox|reproducci[oó]n superada|valor reproducido)\b", re.I)
_RESERVA = re.compile(r"\b(pendiente|fall[oó]|fallid[oa]s?|sin terminar|incomplet[oa]s?|no pudo|no se pudo|no respondi[oó]|interrumpid[oa]|quedo sin|queda sin|omitid[oa]s?)\b", re.I)


def _norm(n: str) -> str:
    n = n.replace("\u00b7", ".")
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", n):
        n = n.replace(",", "")
    else:
        n = n.replace(",", ".")
    if n.startswith("."):
        n = "0" + n
    try:
        return f"{float(n):g}"
    except ValueError:
        return n


def _numeros(texto: str) -> set[str]:
    out = set()
    for m in _NUM.findall((texto or "").replace("\u00b7", ".")):
        n = _norm(m)
        try:
            v = float(n)
        except ValueError:
            continue
        if 1900 <= v <= 2099 and "." not in n:
            continue
        out.add(n)
    return out


def corpus_del_registro(e: dict[str, Any], inv_id: str, it: dict[str, Any] | None, corrida: dict[str, Any] | None, hipotesis: dict[str, Any] | None = None) -> dict[str, Any]:
    """Todo lo que el registro sabe: números, identificadores y textos, para
    contrastar un resumen o un dossier."""
    textos: list[str] = []
    numeros: set[str] = set()
    ids: set[str] = set()
    hips = [hipotesis] if hipotesis else [h for h in e.get("hipotesis", []) if h["investigacionId"] == inv_id]
    afs = list((corrida or {}).get("_afirmaciones", [])) + [a for h in hips for a in h.get("afirmaciones", [])]
    for a in afs:
        textos += [a.get("texto", ""), a.get("fragmento", ""), a.get("cita", ""), a.get("efecto", ""), a.get("incertidumbre", ""), a.get("n", "")]
    for h in hips:
        textos += [h.get("titulo", ""), h.get("enunciado", ""), h.get("mecanismo", "")]
        for f in h.get("procedencia", {}).get("fuentes", []):
            ids.update(x for x in (f.get("doi"), f.get("pmid"), f.get("nct")) if x)
            textos.append(f.get("referencia", ""))
        for q in h.get("consultas", []):
            ids.update(q.get("ids", []))
            ids.update(str(v) for v in q.get("argumentos", {}).values())
        for pr in (h.get("procedencia", {}).get("registro") or []):
            textos.append(pr)
    for hch in e.get("hechos", []):
        if hch["investigacionId"] == inv_id:
            textos.append(hch.get("enunciado", ""))
            for p in hch.get("procedencia", []):
                ids.update(x for x in (p.get("doi"), p.get("pmid")) if x)
    for r in e.get("ejecuciones", []):
        if r.get("investigacionId") == inv_id or any(r.get("hipotesisId") == h["id"] for h in hips):
            for d in (r.get("resultados"), r.get("baseline"), r.get("controlNegativo")):
                for k, v in (d or {}).items():
                    textos.append(f"{k}={v}")
            textos.append(r.get("salida", "")[-2000:])
    for rep in e.get("reproducciones", []):
        if rep.get("investigacionId") == inv_id:
            textos += [str(rep.get("valorPublicado")), str(rep.get("valorObtenido")), rep.get("referencia", ""), rep.get("doi", "")]
            if rep.get("doi"):
                ids.add(rep["doi"])
    for inv in e.get("investigaciones", []):
        if inv["id"] == inv_id:
            for ds in inv.get("datasets", []):
                textos += [ds.get("nombre", ""), ds.get("descripcion", ""), str((ds.get("procedencia") or {}).get("filas", ""))]
                ids.update(_GSE.findall(ds.get("nombre", "") + " " + ds.get("descripcion", "")))
    if it:
        for p in it.get("plan", []):
            textos += [p.get("titulo", ""), p.get("detalle", ""), p.get("motivoFallo") or ""]
        for pi in it.get("pistas", []):
            textos += [pi.get("titulo", ""), pi.get("resumen", "") or ""]
            for ev in pi.get("transcripcion", []) or []:
                textos.append(str(ev.get("texto", "")) + " " + str((ev.get("consulta") or {}).get("resultados", "")))
    for q in (corrida or {}).get("busqueda", {}).get("consultas", []) or []:
        textos.append(f"{q.get('base', '')} {q.get('consulta', '')} {q.get('resultados', '')}")
    if it:
        textos += [str(len(it.get("plan", []))), str(sum(1 for p in it.get("pistas", []) if p.get("estado") == "hecha")), str(len(it.get("pistas", [])))]
    for t in textos:
        numeros |= _numeros(t)
        ids.update(_DOI.findall(t)); ids.update(_NCT.findall(t)); ids.update(_GSE.findall(t))
    return {"numeros": numeros, "ids": {str(i).lower().rstrip(".") for i in ids}, "textos": textos, "recuentos": recuentos_del_registro(e, inv_id, it, corrida)}


_RECUENTO = re.compile(r"(\d{1,5})(?:\s+de\s+(\d{1,5}))?\s+(hechos?|afirmaci(?:ó|o)n(?:es)?|fuentes?|art(?:í|i)culos?|publicaciones?|b(?:ú|u)squedas?|consultas?|hip(?:ó|o)tesis|ejecuci(?:ó|o)n(?:es)?|pasos?|pistas?)\b", re.IGNORECASE)
_CLAVE_RECUENTO = {"hecho": "hechos", "afirmaci": "afirmaciones", "fuente": "fuentes", "art": "fuentes", "publicaci": "fuentes", "b": "consultas", "consulta": "consultas", "hip": "hipotesis", "ejecuci": "ejecuciones", "paso": "pasos", "pista": "pistas"}
_KILLER_CERRADA = {"descartar", "descartar_en_contexto", "suspender"}


def _clave_recuento(sustantivo: str) -> str:
    s_ = sustantivo.lower()
    for prefijo, clave in _CLAVE_RECUENTO.items():
        if s_.startswith(prefijo):
            return clave
    return s_


def recuentos_del_texto(texto: str) -> list[tuple[int, str, str]]:
    """Los "N cosas" del texto: (n, clave, tal como aparece). "40 de 59 hechos"
    da los dos números con la misma clave."""
    salida = []
    for m in _RECUENTO.finditer(texto or ""):
        clave = _clave_recuento(m.group(3))
        salida.append((int(m.group(1)), clave, m.group(0)))
        if m.group(2):
            salida.append((int(m.group(2)), clave, m.group(0)))
    return salida


def recuentos_del_registro(e: dict[str, Any], inv_id: str, it: dict[str, Any] | None, corrida: dict[str, Any] | None) -> dict[str, set[int]]:
    """Los recuentos que el registro admite para cada palabra: total de la
    investigación, lo de esta iteración y los desgloses (por veredicto, por
    base). Un resumen que dice "59 hechos" cuando el registro tiene 40 en
    total y 11 nuevos se contradice con el registro, y eso se ve sin juez."""
    c = corrida or {}
    desde = int((it or {}).get("empezadaEn") or 0)
    numero = (it or {}).get("numero")
    hechos = [h for h in e.get("hechos", []) if h.get("investigacionId") == inv_id]
    hips = [h for h in e.get("hipotesis", []) if h.get("investigacionId") == inv_id]
    afs = list(c.get("_afirmaciones", []))
    afs_it = [a for a in afs if a.get("iteracion") == numero]
    consultas = list((c.get("busqueda") or {}).get("consultas") or [])
    consultas_it = [q for q in consultas if q.get("iteracion") == numero]
    por_base: dict[str, int] = {}
    for q in consultas_it:
        por_base[q.get("base", "")] = por_base.get(q.get("base", ""), 0) + 1
    por_veredicto: dict[str, int] = {}
    for a in afs_it:
        por_veredicto[a.get("veredicto", "")] = por_veredicto.get(a.get("veredicto", ""), 0) + 1
    fuentes = c.get("_fuentes") or {}
    b = c.get("busqueda") or {}
    ejecuciones = [r for r in e.get("ejecuciones", []) if r.get("investigacionId") == inv_id]
    plan = (it or {}).get("plan", []) or []
    pistas = (it or {}).get("pistas", []) or []
    return {
        "hechos": {len(hechos), sum(1 for h in hechos if int(h.get("actualizadoEn") or 0) >= desde and desde)},
        "afirmaciones": {len(afs), len(afs_it), *por_veredicto.values()},
        "fuentes": {len(fuentes), int(b.get("identificados") or 0), int(b.get("cribados") or 0), int(b.get("textoCompleto") or 0), int(b.get("traidos") or 0), sum(1 for f in fuentes.values() if f.get("relevancia", 0) and int(f.get("_iteracion") or 0) == numero) if numero else 0},
        "consultas": {len(consultas), len(consultas_it), *por_base.values()},
        "hipotesis": {len(hips), sum(1 for h in hips if h.get("iteracion") == numero)},
        "ejecuciones": {len(ejecuciones), sum(1 for r in ejecuciones if r.get("estado") == "completado")},
        "pasos": {len(plan), sum(1 for p_ in plan if p_.get("estado") == "hecho")},
        "pistas": {len(pistas), sum(1 for p_ in pistas if p_.get("estado") == "hecha")},
    }


def comprobaciones_deterministas(texto: str, corpus: dict[str, Any], it: dict[str, Any] | None, ejecuciones_ok: int, hipotesis: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Los hallazgos que se pueden derivar sin modelo."""
    hallazgos: list[dict[str, Any]] = []
    # Recuentos ("59 hechos", "2 búsquedas") frente a lo que el registro admite.
    recuentos = corpus.get("recuentos") or {}
    malos = []
    for n, clave, tal_cual in recuentos_del_texto(texto):
        admitidos = recuentos.get(clave)
        if admitidos and n not in admitidos:
            malos.append(f"«{tal_cual.strip()}» (el registro admite {', '.join(str(x) for x in sorted(admitidos))})")
    if malos:
        hallazgos.append({"clase": "contradiccion_con_registro", "gravedad": "media", "detalle": "Recuentos del texto que no cuadran con el registro: " + "; ".join(malos[:6]), "origen": "regla"})
    # Una hipótesis que el Killer descartó o suspendió no puede aparecer como pendiente o viva.
    t_bajo = (texto or "").lower()
    for h in hipotesis or []:
        decision = h.get("decisionKiller")
        titulo = (h.get("titulo") or "").strip()
        if decision in _KILLER_CERRADA and titulo and titulo[:40].lower() in t_bajo and not re.search(r"descart|suspend", t_bajo):
            hallazgos.append({"clase": "contradiccion_con_registro", "gravedad": "alta", "detalle": f"El texto habla de «{titulo[:80]}» y el Killer la dejó en «{decision}»; el texto no lo dice", "origen": "regla"})
    sueltas = sorted(n for n in _numeros(texto) if n not in corpus["numeros"] and not any(abs(float(n) - float(x)) < 1e-9 for x in corpus["numeros"] if _es_num(x)))
    if sueltas:
        hallazgos.append({"clase": "contradiccion_con_registro", "gravedad": "media", "detalle": f"Cifras del texto que no aparecen en ninguna afirmación, ejecución, hecho ni pista del registro: {', '.join(sueltas[:8])}" + (" ..." if len(sueltas) > 8 else ""), "origen": "regla"})
    ident = {i.lower().rstrip(".") for i in _DOI.findall(texto) + _NCT.findall(texto) + _GSE.findall(texto) + _PMID.findall(texto)}
    faltan = sorted(i for i in ident if i not in corpus["ids"])
    if faltan:
        hallazgos.append({"clase": "identificador_no_coincide", "gravedad": "alta", "detalle": "Identificadores citados que no están en las fuentes, datasets ni consultas: " + ", ".join(faltan[:6]), "origen": "regla"})
    if _EJECUCION.search(texto or "") and ejecuciones_ok == 0:
        hallazgos.append({"clase": "calculo_no_ejecutado", "gravedad": "alta", "detalle": "El texto habla de ejecuciones, cálculos o reproducciones y no hay ninguna ejecución completada en el registro", "origen": "regla"})
    if it:
        sin_terminar = [p for p in it.get("plan", []) if p.get("estado") not in ("hecho", "omitido")]
        if sin_terminar and not _RESERVA.search(texto or ""):
            hallazgos.append({"clase": "paso_incompleto", "gravedad": "media", "detalle": f"{len(sin_terminar)} pasos del plan sin terminar ({'; '.join(p.get('titulo', '')[:40] for p in sin_terminar[:3])}) y el resumen no lo dice", "origen": "regla"})
    return hallazgos


def _es_num(x: str) -> bool:
    try:
        float(x)
        return True
    except ValueError:
        return False


def texto_registro(e: dict[str, Any], inv_id: str, it: dict[str, Any] | None, corrida: dict[str, Any] | None, hipotesis: dict[str, Any] | None = None, maximo: int = 9000) -> str:
    """El registro en texto para el juez: plan con estados, pistas, afirmaciones
    con veredicto, ejecuciones con cifras, reproducciones, consultas."""
    lineas: list[str] = ["Nota: 'CONSULTAS A BASES ESTRUCTURADAS' son solo las llamadas a bases de genes, fármacos y datos (conectores). Las búsquedas de literatura (PubMed, Europe PMC, OpenAlex) están en 'BÚSQUEDAS DE LITERATURA' con su base y su recuento."]
    if it:
        lineas.append("PLAN: " + "; ".join(f"{p.get('titulo', '')[:50]} [{p.get('estado')}]" for p in it.get("plan", [])))
        lineas.append("PISTAS (una pista fallida seguida de otra hecha con el mismo título significa que el paso se retomó y terminó): " + "; ".join(f"{p.get('titulo', '')[:40]} [{p.get('estado')}] {(p.get('resumen') or '')[:80]}" for p in it.get("pistas", [])[:20]))
        busq = []
        for p in it.get("pistas", []):
            for ev in p.get("transcripcion", []) or []:
                q = ev.get("consulta") or {}
                if q.get("base"):
                    busq.append(f"{q.get('base')}: {str(q.get('parametros', ''))[:60]} -> {q.get('resultados', '?')} resultados")
        for q in (corrida or {}).get("busqueda", {}).get("consultas", []) or []:
            if not it or q.get("iteracion") == it.get("numero"):
                busq.append(f"{q.get('base')}: {str(q.get('consulta', ''))[:60]} -> {q.get('resultados', '?')} resultados")
        lineas.append("BÚSQUEDAS DE LITERATURA: " + ("; ".join(busq[:30]) or "ninguna registrada en las pistas"))
    hips = [hipotesis] if hipotesis else [h for h in e.get("hipotesis", []) if h["investigacionId"] == inv_id]
    lineas.append("HIPÓTESIS DE LA INVESTIGACIÓN (título [estado, decisión del Killer, iteración en que nació]): " + ("; ".join(f"{h.get('titulo', '')[:90]} [{h.get('estado')}, {h.get('decisionKiller')}, it {h.get('iteracion')}]" for h in hips[:20]) or "ninguna"))
    if it and not hipotesis:
        nuevas = [h for h in hips if h.get("iteracion") == it.get("numero")]
        lineas.append(f"HIPÓTESIS NUEVAS EN ESTA ITERACIÓN: {len(nuevas)} (" + "; ".join(h.get("titulo", "")[:60] for h in nuevas) + "); en cola (propuestas o en revisión) al cerrar: " + str(sum(1 for h in hips if h.get("estado") in ("propuesta", "en_revision"))))
        hechos_it = [x for x in e.get("hechos", []) if x["investigacionId"] == inv_id and x.get("actualizadoEn", 0) >= it.get("empezadaEn", 0)]
        lineas.append(f"HECHOS NUEVOS O ACTUALIZADOS EN ESTA ITERACIÓN: {len(hechos_it)}")
    afs = list((corrida or {}).get("_afirmaciones", [])) if not hipotesis else list(hipotesis.get("afirmaciones", []))
    if it and not hipotesis:
        afs = [a for a in afs if a.get("iteracion") == it.get("numero")]
    lineas.append("AFIRMACIONES:")
    lineas += [f"- [{a.get('veredicto')}] {a.get('texto', '')[:160]} {a.get('cita', '')}" for a in afs[:60]]
    runs = [r for r in e.get("ejecuciones", []) if any(r.get("hipotesisId") == h["id"] for h in hips) or r.get("investigacionId") == inv_id]
    lineas.append("EJECUCIONES:")
    lineas += [f"- {r['id']} [{r.get('estado')}] auditoria={((r.get('auditoria') or {}).get('veredicto'))} " + "; ".join(f"{k}={v}" for k, v in (r.get("resultados") or {}).items()) for r in runs[-12:]] or ["- ninguna"]
    reps = [r for r in e.get("reproducciones", []) if r.get("investigacionId") == inv_id]
    lineas.append("REPRODUCCIONES: " + ("; ".join(f"{r.get('referencia', '')[:40]} [{r.get('estado')}] obtenido={r.get('valorObtenido')} publicado={r.get('valorPublicado')}" for r in reps) or "ninguna"))
    cons = [q for h in hips for q in h.get("consultas", [])]
    lineas.append("CONSULTAS A BASES ESTRUCTURADAS (conectores): " + ("; ".join(f"{q.get('herramienta')}({', '.join(str(v) for v in q.get('argumentos', {}).values())}) n={q.get('n')}{' ERROR' if q.get('error') else ''}" for q in cons[-25:]) or "ninguna"))
    fuentes = {f.get("referencia"): f for h in hips for f in h.get("procedencia", {}).get("fuentes", [])}
    lineas.append("FUENTES: " + ("; ".join(f"{r} (doi {f.get('doi') or 'no'})" for r, f in list(fuentes.items())[:40]) or "ninguna"))
    return "\n".join(lineas)[:maximo]


def resumen_revision(hallazgos: list[dict[str, Any]]) -> str:
    if not hallazgos:
        return "El revisor no encontró discrepancias entre lo dicho y el registro"
    por = {}
    for h in hallazgos:
        por[h["clase"]] = por.get(h["clase"], 0) + 1
    return f"{len(hallazgos)} hallazgos: " + ", ".join(f"{k.replace('_', ' ')} ({v})" for k, v in por.items())
