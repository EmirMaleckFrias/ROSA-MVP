"""Compara corridas de una misma investigación con las mismas cifras.

Sirve para saber si un bloque de cambios funcionó: se lanza una corrida de
referencia antes del cambio y otra después, sobre la misma investigación y con
el mismo tope, y se comparan columna a columna. Lee `rosa.db` en modo solo
lectura, así que se puede correr con el servidor vivo y con una corrida en
marcha (la corrida viva sale con sus cifras hasta el momento).

Uso:
    python -m scripts.comparar_corridas                      # últimas 3 corridas de la investigación más reciente
    python -m scripts.comparar_corridas --investigacion inv-mu2sz2ns-3 --ultimas 4
    python -m scripts.comparar_corridas --corridas cor-a cor-b
    python -m scripts.comparar_corridas --json               # salida para máquinas

Qué mide, por corrida: tope y duración; coste real y por iteración; embudo de
la búsqueda (identificados, cribados, texto completo, usados); consultas de
foco que no dejaron ninguna fuente relevante; fuentes nuevas frente a
repetidas respecto a las corridas anteriores de la misma investigación;
afirmaciones sostenidas, parciales, no sostenidas y bloqueadas, con la tasa de
resolución por clase de localizador (página, sección, resumen, texto web);
hechos nuevos; hipótesis nuevas; peldaños de certeza ganados e hipótesis que
subieron de nivel; conclusiones rehechas y revisiones del registro.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
NIVELES = ("muy_baja", "baja", "moderada", "alta")


def cargar_estado(ruta: Path) -> dict[str, Any]:
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        fila = con.execute("select json from estado order by version desc limit 1").fetchone()
    finally:
        con.close()
    if not fila:
        raise SystemExit(f"No hay estado en {ruta}")
    return json.loads(fila[0])


def _lista(x: Any) -> list[dict[str, Any]]:
    if isinstance(x, dict):
        return [v for v in x.values() if isinstance(v, dict)]
    if isinstance(x, list):
        return [v for v in x if isinstance(v, dict)]
    return []


def _fecha(ms: Any) -> str:
    if not ms:
        return "sin fecha"
    return datetime.fromtimestamp(int(ms) / 1000).strftime("%d/%m %H:%M")


def clase_localizador(loc: Any) -> str:
    if isinstance(loc, dict):
        loc = loc.get("tipo") or loc.get("texto") or ""
    t = str(loc or "").strip().lower()
    if t.startswith(("pág", "pag", "p.")):
        return "página"
    if t.startswith("texto web"):
        return "texto web"
    if t.startswith("resumen") or t == "abstract":
        return "resumen"
    if t.startswith(("secc", "sección", "seccion", "tabla", "figura")):
        return "sección"
    if not t:
        return "sin localizador"
    return "otro"


def claves_fuente(f: dict[str, Any]) -> set[str]:
    claves: set[str] = set()
    for c in f.get("_claves") or []:
        if isinstance(c, str) and c:
            claves.add(c)
    if f.get("_clave"):
        claves.add(str(f["_clave"]))
    if f.get("doi"):
        claves.add("doi:" + str(f["doi"]).lower())
    if f.get("pmid"):
        claves.add("pmid:" + str(f["pmid"]))
    return claves


def medir(e: dict[str, Any], c: dict[str, Any], anteriores: list[dict[str, Any]]) -> dict[str, Any]:
    ahora = int(time.time() * 1000)
    inicio = int(c.get("empezadaEn") or 0)
    fin = int(c.get("terminadaEn") or ahora)
    inv = c.get("investigacionId")
    its = [i for i in e.get("iteraciones", []) if i.get("corridaId") == c["id"]]
    its.sort(key=lambda i: int(i.get("numero") or 0))
    gasto = c.get("gasto") or {}
    parada = c.get("parada") or {}
    busqueda = c.get("busqueda") or {}
    consultas = [q for q in busqueda.get("consultas") or [] if isinstance(q, dict)]
    fuentes = _lista(c.get("_fuentes"))
    afirmaciones = _lista(c.get("_afirmaciones"))

    # Fuentes repetidas: cualquier clave compartida con una corrida anterior de la misma investigación.
    vistas: set[str] = set()
    for ant in anteriores:
        for f in _lista(ant.get("_fuentes")):
            vistas |= claves_fuente(f)
    repetidas = sum(1 for f in fuentes if claves_fuente(f) & vistas)

    veredictos = Counter(a.get("veredicto") for a in afirmaciones)
    por_clase: dict[str, Counter] = {}
    for a in afirmaciones:
        k = clase_localizador(a.get("localizador"))
        por_clase.setdefault(k, Counter())
        por_clase[k]["total"] += 1
        if a.get("veredicto") in ("sostenida", "parcial"):
            por_clase[k]["resueltas"] += 1

    hechos = [h for h in e.get("hechos", []) if h.get("investigacionId") == inv]

    def nacido_en(h: dict[str, Any]) -> int:
        hist = h.get("historial") or []
        if hist and isinstance(hist[0], dict) and hist[0].get("fecha"):
            return int(hist[0]["fecha"])
        return int(h.get("actualizadoEn") or 0)

    hechos_nuevos = sum(1 for h in hechos if inicio <= nacido_en(h) <= fin)
    hechos_sin_afirmacion = sum(1 for h in hechos if inicio <= nacido_en(h) <= fin and not h.get("afirmacionIds"))

    hips = [h for h in e.get("hipotesis", []) if h.get("investigacionId") == inv]
    hips_nuevas = sum(1 for h in hips if inicio <= int(h.get("creadaEn") or 0) <= fin)
    conclusiones_rehechas = sum(1 for h in hips if inicio <= int((h.get("conclusion") or {}).get("fecha") or 0) <= fin)

    eventos = [x for x in e.get("eventos", []) if x.get("investigacionId") == inv and inicio <= int(x.get("t") or 0) <= fin]
    tipos_evento = Counter(x.get("tipo") for x in eventos)

    progreso = [p for p in c.get("progreso") or [] if isinstance(p, dict)]
    peldanos = sum(int(x.get("peldano") or 0) for p in progreso for x in p.get("certezas") or [])
    subieron = 0
    certezas_final: Counter = Counter()
    if progreso:
        primera = {x.get("hipotesisId"): x.get("certeza") for x in progreso[0].get("certezas") or []}
        ultima = {x.get("hipotesisId"): x.get("certeza") for x in progreso[-1].get("certezas") or []}
        for hid, cert in ultima.items():
            certezas_final[cert] += 1
            antes = primera.get(hid)
            if antes in NIVELES and cert in NIVELES and NIVELES.index(cert) > NIVELES.index(antes):
                subieron += 1

    foco_sin_relevantes = sum(1 for q in consultas if q.get("modo") == "foco" and not q.get("relevantes"))
    anchas_sin_relevantes = sum(1 for q in consultas if (q.get("resultados") or 0) > 1000 and not q.get("relevantes"))
    pistas = sum(len(i.get("pistas") or []) for i in its)
    hallazgos_registro = sum(len((i.get("revisionRegistro") or {}).get("hallazgos") or []) for i in its)
    duracion_h = max(0.0, (fin - inicio) / 3_600_000) if inicio else 0.0
    n_it = len(its)
    usd_real = float(gasto.get("usdReal") or 0.0)

    return {
        "id": c["id"],
        "numero": c.get("numero"),
        "estado": c.get("estado"),
        "inicio": _fecha(inicio),
        "fin": _fecha(c.get("terminadaEn")) if c.get("terminadaEn") else "en marcha",
        "tope": f"{parada.get('horas') or '-'} h / {parada.get('iteraciones') or '-'} it / certeza {parada.get('certeza') or '-'}",
        "duracion_h": round(duracion_h, 2),
        "iteraciones": n_it,
        "usd_real": round(usd_real, 2),
        "usd_real_por_iteracion": round(usd_real / n_it, 2) if n_it else 0.0,
        "usd_tabla": round(float(gasto.get("usd") or 0.0), 2),
        "llamadas": int(gasto.get("llamadas") or 0),
        "articulos_leidos": int(gasto.get("articulosLeidos") or 0),
        "identificados": int(busqueda.get("identificados") or 0),
        "cribados": int(busqueda.get("cribados") or 0),
        "texto_completo": int(busqueda.get("textoCompleto") or 0),
        "usados": int(busqueda.get("usados") or 0),
        "consultas": len(consultas),
        "consultas_foco": sum(1 for q in consultas if q.get("modo") == "foco"),
        "foco_sin_relevantes": foco_sin_relevantes,
        "anchas_sin_relevantes": anchas_sin_relevantes,
        "fuentes": len(fuentes),
        "fuentes_extraidas": sum(1 for f in fuentes if f.get("extraida")),
        "fuentes_repetidas": repetidas,
        "fuentes_nuevas": len(fuentes) - repetidas,
        "afirmaciones": len(afirmaciones),
        "sostenidas": veredictos.get("sostenida", 0),
        "parciales": veredictos.get("parcial", 0),
        "no_sostenidas": veredictos.get("no_sostenida", 0),
        "bloqueadas": veredictos.get("cita_no_resuelve", 0) + veredictos.get("sin_cita", 0),
        "tasa_resueltas": round(100 * (veredictos.get("sostenida", 0) + veredictos.get("parcial", 0)) / len(afirmaciones), 1) if afirmaciones else 0.0,
        "por_localizador": {k: f"{v['resueltas']}/{v['total']}" for k, v in sorted(por_clase.items())},
        "hechos_nuevos": hechos_nuevos,
        "hechos_nuevos_sin_afirmacion": hechos_sin_afirmacion,
        "hipotesis_nuevas": hips_nuevas,
        "conclusiones_rehechas": conclusiones_rehechas,
        "peldanos": peldanos,
        "hipotesis_que_subieron": subieron,
        "certezas_al_final": dict(certezas_final),
        "eventos_killer": tipos_evento.get("killer", 0),
        "eventos_ranking": tipos_evento.get("ranking_cambio", 0),
        "incidencias": tipos_evento.get("incidencia", 0),
        "pistas": pistas,
        "hallazgos_registro": hallazgos_registro,
    }


FILAS: list[tuple[str, str]] = [
    ("estado", "Estado"),
    ("inicio", "Empezó"),
    ("fin", "Terminó"),
    ("tope", "Tope"),
    ("duracion_h", "Duración (h)"),
    ("iteraciones", "Iteraciones"),
    ("usd_real", "Coste real (USD)"),
    ("usd_real_por_iteracion", "Coste real por iteración"),
    ("llamadas", "Llamadas al modelo"),
    ("identificados", "Identificados"),
    ("cribados", "Cribados"),
    ("texto_completo", "Con texto completo"),
    ("usados", "Usados en hipótesis"),
    ("consultas", "Consultas"),
    ("consultas_foco", "Consultas de foco"),
    ("foco_sin_relevantes", "Foco sin ningún relevante"),
    ("anchas_sin_relevantes", "Consultas anchas (>1000) sin relevante"),
    ("fuentes", "Fuentes"),
    ("fuentes_extraidas", "Fuentes extraídas"),
    ("fuentes_nuevas", "Fuentes nuevas"),
    ("fuentes_repetidas", "Fuentes repetidas de corridas previas"),
    ("afirmaciones", "Afirmaciones"),
    ("sostenidas", "Sostenidas"),
    ("parciales", "Parciales"),
    ("no_sostenidas", "No sostenidas"),
    ("bloqueadas", "Bloqueadas (cita no resuelve)"),
    ("tasa_resueltas", "Tasa de resueltas (%)"),
    ("por_localizador", "Resueltas por localizador"),
    ("hechos_nuevos", "Hechos nuevos"),
    ("hechos_nuevos_sin_afirmacion", "Hechos nuevos sin afirmación enlazada"),
    ("hipotesis_nuevas", "Hipótesis nuevas"),
    ("conclusiones_rehechas", "Conclusiones rehechas"),
    ("peldanos", "Peldaños de certeza"),
    ("hipotesis_que_subieron", "Hipótesis que subieron de nivel"),
    ("certezas_al_final", "Certezas al final"),
    ("eventos_killer", "Veredictos del Killer"),
    ("eventos_ranking", "Cambios de ranking"),
    ("incidencias", "Incidencias"),
    ("pistas", "Pistas registradas"),
    ("hallazgos_registro", "Hallazgos del revisor de registro"),
]


def _celda(v: Any) -> str:
    if isinstance(v, dict):
        return ", ".join(f"{k} {val}" for k, val in v.items()) or "-"
    return str(v)


def imprimir(medidas: list[dict[str, Any]], titulo: str) -> None:
    ancho_etiqueta = max(len(et) for _, et in FILAS) + 1
    cabeceras = [f"corrida {m['numero']}" for m in medidas]
    anchos = [max(len(h), 14) for h in cabeceras]
    for m, i in zip(medidas, range(len(medidas))):
        for clave, _ in FILAS:
            anchos[i] = min(60, max(anchos[i], len(_celda(m[clave]))))
    print(titulo)
    print("=" * (ancho_etiqueta + sum(a + 3 for a in anchos)))
    print(" " * ancho_etiqueta + "".join(f" | {h:<{a}}" for h, a in zip(cabeceras, anchos)))
    print("-" * (ancho_etiqueta + sum(a + 3 for a in anchos)))
    for clave, etiqueta in FILAS:
        fila = f"{etiqueta:<{ancho_etiqueta}}"
        for m, a in zip(medidas, anchos):
            fila += f" | {_celda(m[clave])[:60]:<{a}}"
        print(fila)
    if len(medidas) >= 2:
        a, b = medidas[0], medidas[-1]
        print()
        print(f"Diferencia entre la corrida {a['numero']} y la corrida {b['numero']} (positivo = más en la última):")
        for clave, etiqueta in FILAS:
            if isinstance(a[clave], (int, float)) and isinstance(b[clave], (int, float)) and not isinstance(a[clave], bool):
                d = b[clave] - a[clave]
                if d:
                    print(f"  {etiqueta:<{ancho_etiqueta}} {d:+g}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=str(RAIZ / "rosa.db"), help="ruta a rosa.db (por defecto la de la raíz)")
    ap.add_argument("--investigacion", help="id de la investigación; por defecto la de la corrida más reciente")
    ap.add_argument("--corridas", nargs="*", help="ids de corridas a comparar, en orden")
    ap.add_argument("--ultimas", type=int, default=3, help="cuántas corridas recientes de la investigación (por defecto 3)")
    ap.add_argument("--json", action="store_true", help="salida JSON")
    args = ap.parse_args(argv)

    e = cargar_estado(Path(args.base))
    corridas = sorted((c for c in e.get("corridas", []) if c.get("empezadaEn")), key=lambda c: int(c["empezadaEn"]))
    if args.corridas:
        elegidas = [c for cid in args.corridas for c in corridas if c["id"] == cid]
        if len(elegidas) != len(args.corridas):
            faltan = set(args.corridas) - {c["id"] for c in elegidas}
            raise SystemExit(f"No encuentro estas corridas: {', '.join(sorted(faltan))}")
    else:
        inv = args.investigacion or (corridas[-1]["investigacionId"] if corridas else None)
        if not inv:
            raise SystemExit("No hay corridas en la base")
        de_inv = [c for c in corridas if c.get("investigacionId") == inv]
        elegidas = de_inv[-args.ultimas:]
    if not elegidas:
        raise SystemExit("Ninguna corrida que comparar")

    medidas = []
    for c in elegidas:
        anteriores = [x for x in corridas if x.get("investigacionId") == c.get("investigacionId") and int(x["empezadaEn"]) < int(c["empezadaEn"])]
        medidas.append(medir(e, c, anteriores))

    titulos = {i["id"]: i.get("titulo") for i in e.get("investigaciones", [])}
    inv_titulo = titulos.get(elegidas[0].get("investigacionId"), elegidas[0].get("investigacionId"))
    if args.json:
        json.dump({"investigacion": inv_titulo, "corridas": medidas}, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        imprimir(medidas, f"Investigación: {inv_titulo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
