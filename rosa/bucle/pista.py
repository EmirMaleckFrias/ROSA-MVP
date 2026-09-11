"""Una pista: la transcripcion en vivo de una tarea del bucle.

Cada pista pertenece a un paso del plan y escribe lineas (accion, resultado,
nota, error) que la pantalla de corrida muestra al momento. Al cerrar, deja
un resumen de una linea y los milisegundos que tardo. Todo pasa por el
almacen para que cada linea llegue por SSE.
"""

from __future__ import annotations

import time
from typing import Any

from rosa.estado import plantilla as P
from rosa.estado.almacen import Almacen


class Pista:
    def __init__(self, almacen: Almacen, iteracion_id: str, paso_id: str | None, tipo: str, titulo: str, fuente: str):
        self.almacen = almacen
        self.iteracion_id = iteracion_id
        self.id = P.nuevo_id("pi")
        self._t0 = time.monotonic()
        pista = P.nueva_pista(iteracion_id, paso_id, tipo, titulo, fuente)
        pista["id"] = self.id

        def crear(e: dict[str, Any]) -> bool:
            for it in e["iteraciones"]:
                if it["id"] == iteracion_id:
                    it["pistas"].append(pista)
                    return True
            return False

        almacen.mutar(crear, "pista_nueva")

    def _ms(self) -> int:
        return int((time.monotonic() - self._t0) * 1000)

    def _editar(self, fn) -> None:
        def cambiar(e: dict[str, Any]) -> bool:
            for it in e["iteraciones"]:
                if it["id"] == self.iteracion_id:
                    for p in it["pistas"]:
                        if p["id"] == self.id:
                            fn(p)
                            return True
            return False

        self.almacen.mutar(cambiar, "pista")

    def detenida(self) -> bool:
        for it in self.almacen.estado["iteraciones"]:
            if it["id"] == self.iteracion_id:
                for p in it["pistas"]:
                    if p["id"] == self.id:
                        return p["estado"] == "detenida"
        return False

    def linea(self, tipo: str, texto: str, consulta: dict[str, str] | None = None) -> None:
        entrada: dict[str, Any] = {"t": self._ms(), "tipo": tipo, "texto": texto}
        if consulta:
            entrada["consulta"] = consulta

        def fn(p: dict[str, Any]) -> None:
            if p["estado"] != "en_curso":
                return
            p["transcripcion"].append(entrada)
            p["resumen"] = texto[:140]
            p["ms"] = entrada["t"]

        self._editar(fn)

    def accion(self, texto: str, consulta: dict[str, str] | None = None) -> None:
        self.linea("accion", texto, consulta)

    def resultado(self, texto: str) -> None:
        self.linea("resultado", texto)

    def nota(self, texto: str) -> None:
        self.linea("nota", texto)

    def error(self, texto: str) -> None:
        self.linea("error", texto)

    def cerrar(self, resumen: str, estado: str = "hecha") -> None:
        ms = self._ms()

        def fn(p: dict[str, Any]) -> None:
            if p["estado"] == "detenida":
                return
            p["estado"] = estado
            p["resumen"] = resumen[:200]
            p["ms"] = ms

        self._editar(fn)

    def fallar(self, motivo: str) -> None:
        self.error(motivo)
        self.cerrar(motivo, "fallida")
