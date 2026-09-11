"""Ejemplo minimo de GEPA sobre un programa de Rosa: extraer afirmaciones con cita.

Es el punto 4 del plan del primer dia (TRASPASO.md 6): un programa DSPy que
extrae afirmaciones a partir de un fragmento con su localizador, con una
metrica que devuelve puntuacion y feedback textual (lo que GEPA lee), y una
compilacion con presupuesto pequeno para comprobar que el ciclo funciona de
punta a punta contra el gateway.

La metrica es deliberadamente determinista: comprueba el contrato de citas
del RAG (cada afirmacion lleva una cita ``[fuente, pag. N]`` con la fuente y
la pagina correctas, y no inventa cifras que no esten en el fragmento). Es la
parte determinista del verificador; el juez con modelo se anade despues.

Ejecutar: ``uv run python -m rosa.ejemplo_gepa``. Registra la compilacion en
MLflow (sqlite local mlflow.db, se abre con ``uv run mlflow ui --backend-store-uri sqlite:///mlflow.db``) con ``mlflow.dspy.autolog()``.
"""

from __future__ import annotations

import re
import sys

import dspy
import mlflow

from rosa.gateway import modelos

# Acepta "pag." y "pág.": el modelo escribe espanol natural con acento; el contrato
# del RAG exige la fuente y la pagina exactas, no la ortografia de la abreviatura.
# La fuente puede llevar comas ("FDA, 2025"): se captura de forma perezosa
# hasta la ultima ", pag. N]".
PATRON_CITA = re.compile(r"\[(.+?), p[aá]g\. (\d+)\]\s*\.?\s*$")
PATRON_CIFRA = re.compile(r"\d+(?:[.,]\d+)?")


class ExtraerAfirmaciones(dspy.Signature):
    """Extrae las afirmaciones factuales del fragmento, una por linea, cada una
    terminada con la cita exacta [fuente, pag. N] usando la fuente y la pagina
    dadas. No anadas nada que el fragmento no diga. No inventes cifras."""

    fragmento: str = dspy.InputField()
    fuente: str = dspy.InputField(desc="referencia corta, por ejemplo 'Cohorte clinica, 2025'")
    pagina: int = dspy.InputField()
    afirmaciones: list[str] = dspy.OutputField(desc="una afirmacion por elemento, cada una con su cita al final")


def ejemplos() -> tuple[list[dspy.Example], list[dspy.Example]]:
    datos = [
        {
            "fragmento": "El cociente p-tau217/Abeta42 en plasma alcanzo una precision comparable a la PET de tau. En el subgrupo autosomico dominante la señal se anticipo varios años a los sintomas.",
            "fuente": "Cohorte clinica, 2025",
            "pagina": 7,
        },
        {
            "fragmento": "Se identificaron 158 agentes en 192 ensayos activos: 36 en fase 3, 84 en fase 2 y 45 en fase 1. Las dianas de inflamacion pasaron del 6 % al 20 % del pipeline.",
            "fuente": "Cummings et al., 2026",
            "pagina": 4,
        },
        {
            "fragmento": "La variante R47H de TREM2 reduce la union a ligandos lipidicos y atenua la respuesta microglial ante las placas. En portadores de APOE4 el efecto se acumula.",
            "fuente": "Revision TREM2 y APOE, 2025",
            "pagina": 12,
        },
        {
            "fragmento": "La activacion de NLRP3 en microglia induce la liberacion de IL-1beta y motas de ASC. La inhibicion de NLRP3 en modelos murinos redujo la patologia de tau.",
            "fuente": "Revision neuroinflamacion, 2024",
            "pagina": 5,
        },
        {
            "fragmento": "En mayo de 2025 la FDA autorizo el primer test de Alzheimer en sangre, basado en el cociente p-tau217/Abeta42, para adultos de 55 años o mas con deterioro cognitivo.",
            "fuente": "FDA, 2025",
            "pagina": 1,
        },
        {
            "fragmento": "Ensayo de fase 3, aleatorizado y controlado con placebo, de semaglutida oral en Alzheimer temprano; desenlace primario CDR-SB a las 104 semanas.",
            "fuente": "ClinicalTrials.gov, evoke",
            "pagina": 1,
        },
    ]
    todos = [dspy.Example(**d).with_inputs("fragmento", "fuente", "pagina") for d in datos]
    return todos[:4], todos[4:]


def metrica(gold, pred, trace=None, pred_name=None, pred_trace=None, program_trace=None):
    """Puntuacion 0..1 y feedback textual: el contrato de citas del RAG.

    Es la firma que GEPA espera. El feedback es lo que el reflexivo lee para
    proponer prompts mejores; por eso dice exactamente que fallo.
    """
    afirmaciones = [a.strip() for a in (pred.afirmaciones or []) if a and a.strip()]
    problemas: list[str] = []
    if not afirmaciones:
        return dspy.Prediction(score=0.0, feedback="No devolvio ninguna afirmacion. Debe devolver al menos una por frase factual del fragmento.")

    cifras_fragmento = set(PATRON_CIFRA.findall(gold.fragmento))
    correctas = 0
    for a in afirmaciones:
        m = PATRON_CITA.search(a)
        if not m:
            problemas.append(f"Sin cita con el formato [fuente, pag. N] al final: {a!r}")
            continue
        fuente, pagina = m.group(1).strip(), int(m.group(2))
        if fuente != gold.fuente:
            problemas.append(f"La fuente de la cita es {fuente!r} y debia ser {gold.fuente!r}: {a!r}")
            continue
        if pagina != gold.pagina:
            problemas.append(f"La pagina de la cita es {pagina} y debia ser {gold.pagina}: {a!r}")
            continue
        inventadas = set(PATRON_CIFRA.findall(a[: m.start()])) - cifras_fragmento
        if inventadas:
            problemas.append(f"Cifras que no estan en el fragmento ({', '.join(sorted(inventadas))}): {a!r}")
            continue
        correctas += 1

    frases = max(1, len([f for f in re.split(r"(?<=[.;])\s+", gold.fragmento) if f.strip()]))
    cobertura = min(1.0, len(afirmaciones) / frases)
    score = (correctas / len(afirmaciones)) * (0.7 + 0.3 * cobertura)
    if not problemas:
        feedback = f"Todas las {correctas} afirmaciones llevan la cita correcta y ninguna cifra inventada. Cobertura {len(afirmaciones)}/{frases} frases."
    else:
        feedback = "Fallos: " + " | ".join(problemas[:5])
    return dspy.Prediction(score=score, feedback=feedback)


def main() -> int:
    # MLflow 3.16 exige base de datos: sqlite local, ignorada por git.
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("rosa-ejemplo-gepa")
    mlflow.dspy.autolog()

    m = modelos()
    dspy.configure(lm=m.volumen)

    programa = dspy.Predict(ExtraerAfirmaciones)
    trainset, valset = ejemplos()

    print("Evaluando el programa sin optimizar...")
    evaluar = dspy.Evaluate(devset=valset, metric=metrica, num_threads=2, display_progress=False)
    antes = evaluar(programa)
    print(f"Antes: {antes}")

    print("Compilando con GEPA (presupuesto pequeno, max_metric_calls=16)...")
    optimizador = dspy.GEPA(
        metric=metrica,
        max_metric_calls=16,
        reflection_lm=m.reflexion,
        reflection_minibatch_size=2,
        candidate_selection_strategy="pareto",
        track_stats=True,
        log_dir="./mlruns/gepa-logs",
    )
    optimizado = optimizador.compile(programa, trainset=trainset, valset=valset)
    despues = evaluar(optimizado)
    print(f"Despues: {despues}")

    instruccion = optimizado.signature.instructions
    print("\nInstruccion optimizada por GEPA:\n" + instruccion[:800])
    optimizado.save("mlruns/extractor_gepa.json")
    print("\nGuardado en mlruns/extractor_gepa.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
