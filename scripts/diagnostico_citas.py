"""Diagnóstico de solo lectura: cuántas afirmaciones bloqueadas por
`cita_no_resuelve` en las corridas terminadas de una base resolverían ya por
regla con el verificador actual, por tipo de localizador.

Uso: uv run python scripts/diagnostico_citas.py ruta/a/rosa.db

Abre la base en modo solo lectura (URI `mode=ro`), no escribe nada y no toca
el servidor. Sirve para decidir si merece la pena una pasada de
reverificación (que sí gasta llamadas al juez) y para ver de qué causa
vienen los bloqueos que quedan.
"""

from __future__ import annotations

import collections
import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rosa import verificador as V  # noqa: E402

TIPOS = ("pág.", "sección", "resumen", "texto web")


def tipo_localizador(loc: str | None) -> str:
    loc = loc or ""
    for t in TIPOS:
        if loc.startswith(t):
            return t
    return loc[:14] or "(sin localizador)"


def clase_de_motivo(motivo: str) -> str:
    m = motivo or ""
    if "localizador reconocido" in m:
        return "localizador no reconocido"
    if "ninguna fuente conocida" in m:
        return "fuente desconocida"
    if "no tiene el localizador" in m:
        return "fuente sin ese localizador"
    if "literalidad" in m or "no aparece" in m:
        return "pasaje no literal"
    return "otro"


def cargar_estado(ruta: Path) -> dict:
    # La ruta va citada en la URI: con espacios, "?" o "#" en el nombre, sin
    # citar sqlite abriría (o crearía) otro fichero. Una copia suelta (sin su
    # fichero -wal al lado) se abre como inmutable: así sqlite no crea los
    # ficheros -wal y -shm junto a la copia, que es lo único que "mode=ro"
    # llega a escribir. Con -wal presente (una base viva) se usa mode=ro, que
    # lee una instantánea coherente con lo que el servidor aún no volcó.
    modo = "mode=ro" if ruta.with_name(ruta.name + "-wal").exists() else "mode=ro&immutable=1"
    uri = f"file:{quote(str(ruta.resolve()))}?{modo}"
    try:
        con = sqlite3.connect(uri, uri=True)
    except sqlite3.DatabaseError as ex:
        raise SystemExit(f"No pude abrir {ruta} en solo lectura ({ex}). Si es la base viva del servidor, copia el fichero y pasa la copia.")
    try:
        fila = con.execute("select json from estado where clave = 'rosa'").fetchone()
    except sqlite3.DatabaseError as ex:
        raise SystemExit(f"{ruta} no es una base de ROSA2018 con la tabla 'estado' ({ex}).")
    finally:
        con.close()
    if not fila:
        raise SystemExit(f"La base {ruta} no tiene la clave 'rosa' en la tabla estado.")
    return json.loads(fila[0])


def diagnosticar(estado: dict) -> tuple[collections.Counter, collections.Counter, collections.Counter, int]:
    bloqueadas: collections.Counter = collections.Counter()
    resolverian: collections.Counter = collections.Counter()
    quedan: collections.Counter = collections.Counter()
    corridas = 0
    for c in estado.get("corridas", []):
        if c.get("estado") != "terminada":
            continue
        corridas += 1
        fuentes = c.get("_fuentes") or {}
        # Registros antiguos: una fuente sin "id" se identifica por su clave, y un
        # fragmento sin localizador o sin texto no rompe el recuento.
        frags = [V.Fragmento(f.get("id") or clave, f.get("referencia") or "", fr.get("localizador") or "", fr.get("texto") or "", fr.get("encabezado") or "") for clave, f in fuentes.items() if isinstance(f, dict) for fr in (f.get("fragmentos") or []) if isinstance(fr, dict)]
        for a in c.get("_afirmaciones") or []:
            if not isinstance(a, dict):
                continue
            if a.get("veredicto") != "cita_no_resuelve":
                continue
            t = tipo_localizador(a.get("localizador"))
            bloqueadas[t] += 1
            r = V.comprobar_determinista(a.get("texto") or "", a.get("cita") or "", a.get("fragmento"), frags, frags, None, a.get("fuenteId"))
            if r.veredicto == "cita_no_resuelve":
                quedan[(t, clase_de_motivo(r.motivo))] += 1
            elif r.veredicto in V.BLOQUEAN:
                # Otro veredicto por regla que también bloquea (sin_cita, ausencia_refutada):
                # no cuenta como resuelta.
                quedan[(t, f"pasa a {r.veredicto}")] += 1
            else:
                resolverian[t] += 1
    return bloqueadas, resolverian, quedan, corridas


def imprimir(bloqueadas: collections.Counter, resolverian: collections.Counter, quedan: collections.Counter, corridas: int) -> None:
    print(f"Corridas terminadas revisadas: {corridas}")
    if not bloqueadas:
        print("No hay afirmaciones bloqueadas por cita_no_resuelve (o la base no guarda las claves privadas _afirmaciones y _fuentes).")
        return
    print()
    print(f"{'Localizador':<20}{'Bloqueadas hoy':>16}{'Resolverían ya':>16}{'Siguen bloqueadas':>20}")
    for t in sorted(bloqueadas, key=lambda x: -bloqueadas[x]):
        print(f"{t:<20}{bloqueadas[t]:>16}{resolverian[t]:>16}{bloqueadas[t] - resolverian[t]:>20}")
    total_b, total_r = sum(bloqueadas.values()), sum(resolverian.values())
    print(f"{'Total':<20}{total_b:>16}{total_r:>16}{total_b - total_r:>20}")
    if quedan:
        print()
        print("Las que siguen bloqueadas, por causa (veredicto del verificador actual):")
        for (t, clase), n in sorted(quedan.items(), key=lambda kv: -kv[1]):
            print(f"  {t:<18}{clase:<28}{n:>6}")
    print()
    print("Nota: 'resolverían' significa que la comprobación determinista las dejaría pasar al juez (sin_verificar); el juez aún tiene que dictaminar. Las que por regla pasarían a otro veredicto bloqueante (sin_cita, ausencia_refutada) cuentan como 'siguen bloqueadas'. Este script no escribe nada.")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    ruta = Path(argv[1])
    if not ruta.exists():
        print(f"No existe {ruta}")
        return 2
    imprimir(*diagnosticar(cargar_estado(ruta)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
