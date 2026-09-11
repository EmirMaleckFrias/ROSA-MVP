"""Conectores a las fuentes de literatura, ensayos y bases curadas.

Cada conector devuelve datos ya en la forma que el bucle usa y nunca
inventa: si la fuente no responde, lanza `FuenteNoDisponible`, que el bucle
convierte en "no pude comprobar", no en "no hay".
"""

from rosa.fuentes.base import FuenteNoDisponible  # noqa: F401
