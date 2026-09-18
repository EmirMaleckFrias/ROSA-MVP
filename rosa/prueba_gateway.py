"""Comprueba que los tres modelos de ROSA2018 responden por el gateway con DSPy.

Una llamada minima a cada uno. Imprime el id del modelo, la palabra que
devolvio y el finish_reason, que es lo que hay que mirar para detectar un
filtro de contenido (TRASPASO.md 2.3). Nunca imprime la clave.
"""

from __future__ import annotations

import sys
import time

import dspy

from rosa.gateway import CEREBRO, JUEZ, VOLUMEN, lm


def probar(modelo: str) -> bool:
    inicio = time.time()
    try:
        m = lm(modelo, max_tokens=20, temperature=0)
        respuesta = m("Responde solo con la palabra: listo")
        texto = respuesta[0].strip() if respuesta else ""
        # El historial guarda la respuesta cruda; de ahi sale el finish_reason.
        ultimo = m.history[-1] if m.history else {}
        salida = ultimo.get("response")
        finish = None
        try:
            finish = salida.choices[0].finish_reason  # type: ignore[union-attr]
        except Exception:
            finish = ultimo.get("finish_reason")
        uso = ultimo.get("usage", {})
        ms = int((time.time() - inicio) * 1000)
        print(f"OK    {modelo:32} -> {texto!r:14} finish={finish} tokens={uso.get('total_tokens')} {ms} ms")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"FALLO {modelo:32} -> {type(e).__name__}: {str(e)[:200]}")
        return False


def main() -> int:
    print(f"dspy {dspy.__version__}")
    ok = [probar(m) for m in (CEREBRO, JUEZ, VOLUMEN)]
    print("TODOS RESPONDEN" if all(ok) else "ALGUNO FALLO")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
