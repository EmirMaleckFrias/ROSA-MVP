"""Skills de Rosa: ficheros `SKILL.md` con instrucciones de metodo que el
planificador de analisis, el escritor de codigo y el proponente de areas
cargan cuando la tarea lo pide. El formato es el de las Agent Skills de
Anthropic (frontmatter con `name` y `description`, cuerpo en Markdown),
mas tres campos propios: `activa_si` (palabras que la activan), `paquetes`
(lo que el sandbox necesita) y `entorno` (imagen del sandbox). Los scripts
en `scripts/` se copian al directorio de trabajo del sandbox para que el
codigo pueda importarlos.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).parent
MAX_TEXTO_PROMPT = 6000


def _frontmatter(texto: str) -> tuple[dict[str, str], str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", texto, re.S)
    if not m:
        return {}, texto
    meta: dict[str, str] = {}
    for linea in m.group(1).splitlines():
        if ":" in linea:
            k, v = linea.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def cargar() -> list[dict[str, Any]]:
    """Todas las skills, en orden alfabetico."""
    skills = []
    for d in sorted(p for p in RAIZ.iterdir() if p.is_dir() and (p / "SKILL.md").exists()):
        meta, cuerpo = _frontmatter((d / "SKILL.md").read_text(encoding="utf-8"))
        scripts = {p.name: p.read_text(encoding="utf-8") for p in sorted((d / "scripts").glob("*.py"))} if (d / "scripts").exists() else {}
        skills.append({
            "nombre": meta.get("name", d.name),
            "descripcion": meta.get("description", ""),
            "activaSi": [x.strip().lower() for x in meta.get("activa_si", "").split(",") if x.strip()],
            "paquetes": [x.strip() for x in meta.get("paquetes", "").split(",") if x.strip()],
            "entorno": meta.get("entorno", "tabular"),
            "scripts": list(scripts),
            "_scripts": scripts,
            "ruta": str(d.relative_to(RAIZ.parent.parent)),
            "texto": cuerpo.strip(),
        })
    return skills


_CACHE: list[dict[str, Any]] | None = None


def todas() -> list[dict[str, Any]]:
    global _CACHE
    if _CACHE is None:
        _CACHE = cargar()
    return _CACHE


def para_texto(texto: str, maximo: int = 3) -> list[dict[str, Any]]:
    """Las skills cuyas palabras de activacion aparecen en el texto, las mas
    coincidentes primero."""
    t = (texto or "").lower()
    puntuadas = []
    for s in todas():
        p = sum(1 for k in s["activaSi"] if k in t)
        if p:
            puntuadas.append((p, s))
    puntuadas.sort(key=lambda x: -x[0])
    return [s for _, s in puntuadas[:maximo]]


def texto_para_prompt(skills: list[dict[str, Any]], maximo: int = MAX_TEXTO_PROMPT) -> str:
    if not skills:
        return "Ninguna skill aplica"
    partes = [f"## Skill {s['nombre']}\n{s['texto']}" + (f"\nModulos importables en el sandbox: {', '.join(s['scripts'])}" if s["scripts"] else "") for s in skills]
    return "\n\n".join(partes)[:maximo]


def scripts_de(skills: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for s in skills:
        out.update(s.get("_scripts", {}))
    return out


def entorno_de(skills: list[dict[str, Any]]) -> str:
    return "celula_unica" if any(s.get("entorno") == "celula_unica" for s in skills) else "tabular"


def catalogo() -> list[dict[str, Any]]:
    return [{k: v for k, v in s.items() if not k.startswith("_") and k != "texto"} | {"lineas": s["texto"].count("\n") + 1} for s in todas()]
