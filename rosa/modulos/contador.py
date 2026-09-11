"""Contador de llamadas a modelos: cuenta, registra y corta por presupuesto.

Es un `BaseCallback` de DSPy: DSPy lo llama antes y despues de cada llamada
al modelo. Antes, comprueba el presupuesto de la corrida y, si esta agotado,
lanza `PresupuestoAgotado` para que la pista pare limpia. Despues, lee
`lm.history[-1]` (donde DSPy deja `usage`) y suma tokens y llamadas al gasto
de la corrida, y registra la llamada en SQLite.

El contexto (que corrida y que iteracion estan llamando) va en una variable
de contexto, porque las pistas corren en paralelo.
"""

from __future__ import annotations

import contextvars
import threading
import time
from dataclasses import dataclass
from typing import Any

import dspy
from dspy.utils.callback import BaseCallback

from rosa import config


class PresupuestoAgotado(RuntimeError):
    pass


@dataclass
class ContextoLlamada:
    corrida_id: str
    iteracion: int
    rol: str = ""


contexto_actual: contextvars.ContextVar[ContextoLlamada | None] = contextvars.ContextVar("rosa_contexto_llamada", default=None)


class Contador(BaseCallback):
    def __init__(self, almacen) -> None:
        super().__init__()
        self.almacen = almacen
        self._inicio: dict[str, tuple[float, ContextoLlamada | None, str]] = {}
        self._lock = threading.Lock()

    def _presupuesto_ok(self, corrida_id: str) -> bool:
        e = self.almacen.estado
        c = next((x for x in e["corridas"] if x["id"] == corrida_id), None)
        if not c:
            return True
        return c["gasto"]["llamadas"] < c["presupuesto"]["limiteLlamadas"]

    def on_lm_start(self, call_id: str, instance: Any, inputs: dict[str, Any]) -> None:
        ctx = contexto_actual.get()
        modelo = getattr(instance, "model", "?")
        if ctx and not self._presupuesto_ok(ctx.corrida_id):
            raise PresupuestoAgotado(f"Presupuesto de la corrida {ctx.corrida_id} agotado")
        with self._lock:
            self._inicio[call_id] = (time.monotonic(), ctx, modelo)

    def on_lm_end(self, call_id: str, outputs: Any, exception: Exception | None = None) -> None:
        with self._lock:
            inicio, ctx, modelo = self._inicio.pop(call_id, (time.monotonic(), contexto_actual.get(), "?"))
        ms = int((time.monotonic() - inicio) * 1000)
        entrada = salida = 0
        historial = dspy.settings.lm.history if dspy.settings.lm is not None else []
        # La entrada mas reciente del historial global corresponde a esta llamada
        # salvo carrera; se toma el uso por aproximacion.
        try:
            from dspy.clients.base_lm import GLOBAL_HISTORY

            ultimo = GLOBAL_HISTORY[-1] if GLOBAL_HISTORY else (historial[-1] if historial else None)
        except Exception:
            ultimo = historial[-1] if historial else None
        if ultimo and exception is None:
            uso = ultimo.get("usage") or {}
            entrada = int(uso.get("prompt_tokens", 0) or 0)
            salida = int(uso.get("completion_tokens", 0) or 0)
            modelo = ultimo.get("model", modelo)

        def sumar(e: dict[str, Any]) -> bool:
            if not ctx:
                return False
            c = next((x for x in e["corridas"] if x["id"] == ctx.corrida_id), None)
            if not c:
                return False
            g = c["gasto"]
            g["llamadas"] += 1
            g["tokensEntrada"] += entrada
            g["tokensSalida"] += salida
            g["usd"] = round(g.get("usd", 0.0) + config.coste_usd(str(modelo), entrada, salida), 4)
            c["contexto"]["tokensUsados"] = min(c["contexto"]["tokensLimite"], c["contexto"]["tokensUsados"] + entrada // 8)
            for it in e["iteraciones"]:
                if it["corridaId"] == ctx.corrida_id and it["numero"] == ctx.iteracion:
                    it["presupuesto"]["usado"] = it["presupuesto"]["usado"] + 1
            return True

        self.almacen.mutar(sumar, "llamada_modelo")
        self.almacen.registrar_llamada(str(modelo), ctx.rol if ctx else None, ctx.corrida_id if ctx else None, ctx.iteracion if ctx else None, entrada, salida, ms, exception is None, str(exception)[:300] if exception else None)
