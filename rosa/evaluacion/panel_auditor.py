"""Panel de fallos plantados para el auditor de análisis, sin llamadas a modelos.

La capa determinista del auditor (rosa/ejecucion.py: semilla, fuga de datos,
variables del plan, baseline y control, tamaño muestral, multiplicidad,
estabilidad entre semillas) se puede medir a coste cero: se toma un análisis
limpio, se planta un fallo conocido y se comprueba que la comprobación que
debía saltar salta. Cada cambio en las expresiones regulares del auditor queda
medido antes de que deje pasar una fuga o una cifra inestable. Uso:
`python -m rosa.evaluacion.panel_auditor` imprime el panel; `correr()` lo
devuelve para Ajustes. 16 de septiembre de 2026.
"""

from __future__ import annotations

import json
from typing import Any

from rosa import ejecucion as X

CODIGO_LIMPIO = '''import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from statsmodels.stats.multitest import multipletests
np.random.seed(ROSA_SEMILLA)
df = pd.read_csv(RUTA)
X_train, X_test = train_test_split(df[["edad", "gfap"]], random_state=ROSA_SEMILLA)
m = Modelo().fit(X_train)
print("RESULTADO p_valor=0.03")
print("RESULTADO n_a=40")
print("RESULTADO n_b=38")
'''
PLAN_LIMPIO = {"variables": ["edad (independiente)", "gfap (dependiente)"], "correccionMultiplicidad": "una sola prueba", "alpha": 0.05}
RES_LIMPIO = dict(estado="completado", runtime="docker", resultados={"p_valor": "0.03", "n_a": "40", "n_b": "38"}, baseline={"m": "1"}, control={"p_valor": "0.4"})
REPETICIONES_LIMPIAS = [{"semilla": 12346, "estado": "completado", "resultados": {"p_valor": "0.02"}}, {"semilla": 12347, "estado": "completado", "resultados": {"p_valor": "0.04"}}]

# Cada caso: qué se planta, qué comprobación debe saltar y con qué resultado.
CASOS: dict[str, dict[str, Any]] = {
    "ajuste_antes_de_partir": {"comprobacion": "fuga_de_datos", "esperado": "falla", "descripcion": "Un .fit( antes del train_test_split"},
    "sin_semilla": {"comprobacion": "semilla", "esperado": "falla", "descripcion": "Se quita la semilla del código"},
    "variable_del_plan_ausente": {"comprobacion": "coincide_con_plan", "esperado": "falla", "descripcion": "El código no usa una variable del plan"},
    "dos_p_sin_correccion": {"comprobacion": "multiplicidad", "esperado": "falla", "descripcion": "Dos p-valores impresos sin corrección"},
    "n_pequeno": {"comprobacion": "tamano_muestral", "esperado": "falla", "descripcion": "Un grupo con n menor que 5"},
    "sin_control_negativo": {"comprobacion": "baseline_y_control", "esperado": "falla", "descripcion": "El código no imprime el control negativo"},
    "p_cruza_alfa_con_otra_semilla": {"comprobacion": "estabilidad_semillas", "esperado": "falla", "descripcion": "Con otra semilla el p pasa de 0,03 a 0,2"},
    "control_negativo_con_senal": {"comprobacion": "interpretacion", "esperado": "no_evaluable", "descripcion": "El control negativo da p menor que alfa: la interpretación por regla debe ser no evaluable"},
}


def plantar(caso: str) -> tuple[str, dict[str, Any], X.Resultado, list[dict[str, Any]]]:
    codigo, plan, res_d, rep = CODIGO_LIMPIO, dict(PLAN_LIMPIO), dict(RES_LIMPIO), [dict(r, resultados=dict(r["resultados"])) for r in REPETICIONES_LIMPIAS]
    res_d = {**res_d, "resultados": dict(res_d["resultados"]), "control": dict(res_d["control"]), "baseline": dict(res_d["baseline"])}
    if caso == "ajuste_antes_de_partir":
        codigo = codigo.replace('X_train, X_test = train_test_split(df[["edad", "gfap"]], random_state=ROSA_SEMILLA)\nm = Modelo().fit(X_train)', 'm = Modelo().fit(df)\nX_train, X_test = train_test_split(df[["edad", "gfap"]], random_state=ROSA_SEMILLA)')
    elif caso == "sin_semilla":
        codigo = codigo.replace("np.random.seed(ROSA_SEMILLA)\n", "").replace("random_state=ROSA_SEMILLA", "shuffle=True")
    elif caso == "variable_del_plan_ausente":
        plan["variables"] = ["edad (independiente)", "ptau217 (dependiente)"]
    elif caso == "dos_p_sin_correccion":
        codigo = codigo.replace("from statsmodels.stats.multitest import multipletests\n", "")
        plan["correccionMultiplicidad"] = ""
        res_d["resultados"] = {**res_d["resultados"], "p_valor_2": "0.04"}
    elif caso == "n_pequeno":
        res_d["resultados"] = {**res_d["resultados"], "n_b": "3"}
    elif caso == "sin_control_negativo":
        res_d["control"] = {}
    elif caso == "p_cruza_alfa_con_otra_semilla":
        rep[1]["resultados"] = {"p_valor": "0.2"}
    elif caso == "control_negativo_con_senal":
        res_d["control"] = {"p_valor": "0.01"}
    res = X.Resultado(**res_d)
    return codigo, plan, res, rep


def correr() -> dict[str, Any]:
    """Corre todos los casos y devuelve la tasa de detección y el detalle."""
    from rosa.bucle.analisis import interpretacion_por_regla

    resultados = []
    for caso, esperado in CASOS.items():
        codigo, plan, res, rep = plantar(caso)
        if esperado["comprobacion"] == "interpretacion":
            regla = interpretacion_por_regla(plan, res, rep) or {}
            real = regla.get("estado")
        else:
            comprobaciones = {c["comprobacion"]: c["resultado"] for c in X.comprobaciones_deterministas(codigo, plan, res, rep)}
            real = comprobaciones.get(esperado["comprobacion"])
        resultados.append({"caso": caso, "descripcion": esperado["descripcion"], "comprobacion": esperado["comprobacion"], "esperado": esperado["esperado"], "real": real, "detectado": real == esperado["esperado"]})
    # El análisis limpio no debe disparar ninguna comprobación crítica.
    codigo, plan, res, rep = CODIGO_LIMPIO, dict(PLAN_LIMPIO), X.Resultado(**RES_LIMPIO), REPETICIONES_LIMPIAS
    limpio = {c["comprobacion"]: c["resultado"] for c in X.comprobaciones_deterministas(codigo, plan, res, rep)}
    falsos_positivos = [k for k, v in limpio.items() if v == "falla"]
    detectados = sum(1 for r in resultados if r["detectado"])
    return {"casos": resultados, "detectados": detectados, "total": len(resultados), "deteccion": round(detectados / len(resultados), 3), "falsosPositivosEnLimpio": falsos_positivos, "limpio": limpio}


def main() -> None:
    print(json.dumps(correr(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
