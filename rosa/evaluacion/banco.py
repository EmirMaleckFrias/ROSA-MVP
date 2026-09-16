"""Banco de objetivos con respuesta conocida: la cifra que dice si un cambio
en Rosa mejora o empeora.

Antes de tocar el bucle o añadir una herramienta hay que poder medir. El
banco son objetivos de investigación escritos como los escribe una persona,
cada uno con lo que una corrida honesta tiene que conseguir: nombres propios
que deben aparecer en alguna consulta, títulos que deben estar entre las
fuentes, temas que no deberían dominar, y lo que no debe pasar (una
hipótesis descartada por el Killer contada como viva en el resumen).
`puntuar` compara una corrida real con esas expectativas y da una puntuación
de 0 a 1 por criterio, más el coste. No usa modelos: es aritmética sobre el
registro, así que se puede correr después de cada cambio sin gastar nada.

Uso: `python -m rosa.evaluacion.banco <corrida_id> [<clave del objetivo>]`
sobre la misma base de datos; o `puntuar(estado, corrida_id, objetivo)` en
código. Los objetivos viven en `banco_objetivos.jsonl`, uno por línea.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

RUTA_OBJETIVOS = Path(__file__).with_name("banco_objetivos.jsonl")
DECISIONES_QUE_CIERRAN = ("descartar", "descartar_en_contexto", "suspender")


def cargar_objetivos(ruta: Path | None = None) -> list[dict[str, Any]]:
    salida = []
    for linea in (ruta or RUTA_OBJETIVOS).read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#"):
            salida.append(json.loads(linea))
    return salida


def _norm(t: Any) -> str:
    return re.sub(r"\s+", " ", str(t or "").lower()).strip()


def _texto_de_iteracion(it: dict[str, Any]) -> str:
    llano = it.get("resumenLlano") or {}
    trozos = [str(v) for v in (llano.values() if isinstance(llano, dict) else [llano]) if isinstance(v, str)]
    trozos.append(str(it.get("resumen") or ""))
    return _norm(" ".join(trozos))


def puntuar(e: dict[str, Any], corrida_id: str, objetivo: dict[str, Any]) -> dict[str, Any]:
    """Puntuación de una corrida frente a un objetivo del banco."""
    c = next((x for x in e.get("corridas", []) if x["id"] == corrida_id), None)
    if not c:
        raise KeyError(f"corrida {corrida_id} no está en el estado")
    consultas = [_norm(q.get("consulta")) for q in (c.get("busqueda") or {}).get("consultas", [])]
    fuentes = list((c.get("_fuentes") or {}).values())
    titulos = [_norm(f.get("titulo")) for f in fuentes]
    hips = [h for h in e.get("hipotesis", []) if h.get("investigacionId") == c.get("investigacionId")]
    iteraciones = [i for i in e.get("iteraciones", []) if i.get("corridaId") == corrida_id]

    nombres = objetivo.get("nombres_que_deben_buscarse", [])
    buscados = [n for n in nombres if any(_norm(n) in q for q in consultas)]
    esperados = objetivo.get("titulos_que_deben_aparecer", [])
    encontrados = [t for t in esperados if any(all(_norm(p) in tit for p in t.split("&")) for tit in titulos)]
    prohibidos = objetivo.get("temas_fuera_de_objetivo", [])
    # "Fuera de objetivo" se mide sobre las fuentes de foco: la búsqueda en amplitud
    # explora a propósito, y su medida es otra (cuántas de sus fuentes se enlazaron).
    fuentes_foco = [f for f in fuentes if f.get("modo") != "amplitud"]
    fuentes_amplitud = [f for f in fuentes if f.get("modo") == "amplitud"]
    fuentes_fuera = [f for f in fuentes_foco if any(_norm(p) in _norm(f.get("titulo")) for p in prohibidos)]
    ids_amplitud = {f.get("id") for f in fuentes_amplitud}
    fuente_de_afirmacion = {a.get("id"): a.get("fuenteId") for a in (c.get("_afirmaciones") or [])}
    amplitud_enlazadas = {fuente_de_afirmacion.get(a.get("afirmacionId")) for h in hips for a in h.get("afirmaciones", []) if fuente_de_afirmacion.get(a.get("afirmacionId")) in ids_amplitud}

    # Una hipótesis que el Killer cerró y que el resumen de la iteración nombra
    # sin decir que quedó descartada o suspendida cuenta como "descartada como viva".
    descartadas_como_vivas = 0
    for it in iteraciones:
        texto = _texto_de_iteracion(it)
        for h in hips:
            if h.get("decisionKiller") in DECISIONES_QUE_CIERRAN and _norm(h.get("titulo"))[:40] in texto and not re.search(r"descart|suspend", texto):
                descartadas_como_vivas += 1

    hallazgos_regla = sum(int((it.get("revisionRegistro") or {}).get("porRegla") or 0) for it in iteraciones)
    hallazgos_total = sum(len((it.get("revisionRegistro") or {}).get("hallazgos") or []) for it in iteraciones)
    gasto = c.get("gasto") or {}
    criterios = {
        "nombres_buscados": len(buscados) / len(nombres) if nombres else None,
        "titulos_encontrados": len(encontrados) / len(esperados) if esperados else None,
        "fuera_de_objetivo": 1.0 - (len(fuentes_fuera) / len(fuentes_foco)) if fuentes_foco and prohibidos else None,
        "estado_honesto": 1.0 if descartadas_como_vivas == 0 else 0.0,
    }
    validos = [v for v in criterios.values() if v is not None]
    return {
        "corridaId": corrida_id,
        "objetivo": objetivo.get("clave"),
        "criterios": criterios,
        "puntuacion": round(sum(validos) / len(validos), 3) if validos else None,
        "detalle": {
            "nombresBuscados": buscados,
            "nombresQueFaltan": [n for n in nombres if n not in buscados],
            "titulosEncontrados": encontrados,
            "titulosQueFaltan": [t for t in esperados if t not in encontrados],
            "fuentesFueraDeObjetivo": [str(f.get("titulo") or "")[:80] for f in fuentes_fuera[:5]],
            "descartadasComoVivas": descartadas_como_vivas,
        },
        "registro": {"consultas": len(consultas), "fuentes": len(fuentes), "hipotesis": len(hips), "iteraciones": len(iteraciones), "hallazgosPorRegla": hallazgos_regla, "hallazgosTotal": hallazgos_total},
        # La amplitud se mide por lo que rinde: cuántas de sus fuentes acabaron enlazadas a una hipótesis.
        "amplitud": {"consultas": sum(1 for q in (c.get("busqueda") or {}).get("consultas", []) if q.get("modo") == "amplitud"), "fuentes": len(fuentes_amplitud), "enlazadas": len(amplitud_enlazadas)},
        "coste": {"llamadas": gasto.get("llamadas"), "usd": gasto.get("usd"), "exaUsd": gasto.get("exaUsd"), "segundos": gasto.get("segundos")},
    }


def elegir_objetivo(e: dict[str, Any], corrida_id: str, objetivos: list[dict[str, Any]]) -> dict[str, Any] | None:
    """El objetivo del banco cuyo texto más se parece al de la investigación
    de la corrida (por nombres propios compartidos)."""
    c = next((x for x in e.get("corridas", []) if x["id"] == corrida_id), None)
    inv = next((i for i in e.get("investigaciones", []) if c and i["id"] == c.get("investigacionId")), None)
    texto = _norm((inv or {}).get("objetivo"))
    if not texto or not objetivos:
        return None
    mejor = max(objetivos, key=lambda o: sum(_norm(n) in texto for n in o.get("nombres_que_deben_buscarse", [])))
    return mejor if any(_norm(n) in texto for n in mejor.get("nombres_que_deben_buscarse", [])) else None


def main(argv: list[str]) -> int:
    from rosa.estado.almacen import Almacen

    if len(argv) < 2:
        print("uso: python -m rosa.evaluacion.banco <corrida_id> [clave_objetivo]")
        return 2
    al = Almacen()
    try:
        e = al.estado
        objetivos = cargar_objetivos()
        elegido = next((o for o in objetivos if o["clave"] == argv[2]), None) if len(argv) > 2 else elegir_objetivo(e, argv[1], objetivos)
        if elegido is None:
            print("ningún objetivo del banco encaja con esa corrida; indica la clave")
            return 2
        print(json.dumps(puntuar(e, argv[1], elegido), ensure_ascii=False, indent=1))
        return 0
    finally:
        al.cerrar()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
