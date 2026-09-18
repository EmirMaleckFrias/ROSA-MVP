"""Tildes y ñ en los textos en castellano del backend de ROSA2018.

Reutiliza el diccionario y las reglas de `frontend/scripts/acentuar.py`
(`acentuar_texto`) y los aplica a los literales de cadena de `rosa/` y
`tests/` que lee una persona: eventos, pistas, incidencias, dossier, frases
GRADE, mensajes del Killer, docstrings. Regla: una cadena se acentúa si tiene
un espacio y no parece código. Se deja tal cual si contiene `_ = { } $ / \\ < >`
o `palabra.palabra` (claves, rutas, plantillas, expresiones regulares), si
tiene pinta de SQL, o si está en inglés. En las f-strings y en las plantillas
de `format` solo se toca el texto fuera de las llaves. Uso:

    python3 scripts/acentuar_py.py            # aplica
    python3 scripts/acentuar_py.py --seco     # solo cuenta y muestra ejemplos
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "frontend" / "scripts"))
from acentuar import acentuar_texto  # noqa: E402

CODIGO = re.compile(r"[_$/\\<>|*^\[\]]|\w\.\w|%[sdrf(]")
SQL = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|WHERE|FROM|PRAGMA|ORDER BY|VALUES)\b")
LLAVES = re.compile(r"(\{[^{}]*\})")


def partir_llaves(cuerpo: str) -> list[str]:
    """Separa texto y expresiones {…} contando la profundidad de las llaves
    (una f-string puede llevar `{(inv or {}).get('titulo')}`); `{{` y `}}`
    son texto."""
    partes: list[str] = []
    actual = ""
    i = 0
    profundidad = 0
    while i < len(cuerpo):
        c = cuerpo[i]
        if profundidad == 0 and cuerpo.startswith(("{{", "}}"), i):
            actual += cuerpo[i : i + 2]
            i += 2
            continue
        if c == "{":
            if profundidad == 0:
                partes.append(actual)
                actual = ""
            profundidad += 1
            actual += c
        elif c == "}" and profundidad > 0:
            profundidad -= 1
            actual += c
            if profundidad == 0:
                partes.append(actual)
                actual = ""
        else:
            actual += c
        i += 1
    partes.append(actual)
    return partes


def acentuar_cuerpo(cuerpo: str, con_llaves: bool) -> str:
    if " " not in cuerpo:
        return cuerpo
    partes = partir_llaves(cuerpo) if con_llaves else [cuerpo]
    salida = []
    for parte in partes:
        if con_llaves and parte.startswith("{"):
            salida.append(parte)
            continue
        if CODIGO.search(parte) or SQL.search(parte):
            salida.append(parte)
            continue
        salida.append(acentuar_texto(parte))
    return "".join(salida)


PREFIJO = re.compile(r"^([fFrRbBuU]{0,2})(\"\"\"|'''|\"|')")


def acentuar_literal(literal: str) -> str:
    """Un token STRING completo (con prefijo y comillas)."""
    m = PREFIJO.match(literal)
    if not m:
        return literal
    prefijo, comillas = m.group(1), m.group(2)
    if "r" in prefijo.lower() or "b" in prefijo.lower():
        return literal
    cuerpo = literal[m.end() : len(literal) - len(comillas)]
    if "{" in cuerpo and "f" not in prefijo.lower() and re.search(r"\{\s*[\"']", cuerpo):
        return literal  # un JSON escrito a mano
    return f"{prefijo}{comillas}{acentuar_cuerpo(cuerpo, con_llaves='{' in cuerpo)}{comillas}"


def acentuar_python(codigo: str) -> str:
    """Recorre los tokens del fichero (tokenize sabe que es cadena y que es
    comentario o código, cosa que una expresión regular no) y reescribe solo
    los tokens STRING. Con Python 3.9 las f-strings son un solo token."""
    import io
    import tokenize

    lineas = codigo.split("\n")
    cambios: list[tuple[int, int, int, int, str]] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(codigo).readline):
            if tok.type != tokenize.STRING:
                continue
            # Una línea marcada con "# sin tildes" se respeta tal cual (por
            # ejemplo, el resultado esperado de una función que quita tildes).
            if "# sin tildes" in tok.line:
                continue
            nuevo = acentuar_literal(tok.string)
            if nuevo != tok.string:
                cambios.append((*tok.start, *tok.end, nuevo))
    except (tokenize.TokenError, SyntaxError):
        return codigo
    # De atrás hacia delante para que las posiciones sigan valiendo.
    for f0, c0, f1, c1, nuevo in reversed(cambios):
        if f0 == f1:
            l = lineas[f0 - 1]
            lineas[f0 - 1] = l[:c0] + nuevo + l[c1:]
        else:
            primera = lineas[f0 - 1][:c0]
            ultima = lineas[f1 - 1][c1:]
            lineas[f0 - 1 : f1] = (primera + nuevo + ultima).split("\n")
    return "\n".join(lineas)


def main() -> None:
    seco = "--seco" in sys.argv
    cambiados = 0
    ejemplos: list[str] = []
    for carpeta in ("rosa", "tests"):
        for f in sorted((RAIZ / carpeta).rglob("*.py")):
            antes = f.read_text(encoding="utf-8")
            despues = acentuar_python(antes)
            if despues == antes:
                continue
            cambiados += 1
            if seco and len(ejemplos) < 40:
                for a, d in zip(antes.split("\n"), despues.split("\n")):
                    if a != d and len(ejemplos) < 40:
                        ejemplos.append(f"{f.relative_to(RAIZ)}: {d.strip()[:150]}")
            if not seco:
                f.write_text(despues, encoding="utf-8")
    print(f"{cambiados} ficheros {'cambiarían' if seco else 'con tildes nuevas'}")
    for e in ejemplos:
        print(" ", e)


if __name__ == "__main__":
    main()
