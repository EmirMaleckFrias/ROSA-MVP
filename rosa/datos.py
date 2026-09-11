"""Los datos que llegan del laboratorio: donde se guardan y como se resumen.

El resumen es determinista (sin modelo): filas, columnas, y por columna
numerica cuenta, media, desviacion, minimo, maximo y faltantes. Es lo que el
juez recibe junto con las primeras filas para aplicar los criterios del
prerregistro. Formatos: CSV, TSV, JSON (lista de objetos), TXT/MD, PDF (texto
por pagina con PyMuPDF). Un fichero que no se entiende se resume como texto.
"""

from __future__ import annotations

import csv
import io
import json
import re
import statistics
from pathlib import Path

from rosa import config

DIR_DATOS = Path(config.RAIZ) / "datos"
MAX_BYTES = 50 * 1024 * 1024


def nombre_seguro(nombre: str) -> str:
    base = Path(nombre).name
    base = re.sub(r"[^\w.\-]+", "_", base)
    return base[:120] or "datos"


def ruta_de(hipotesis_id: str, fichero: str) -> Path | None:
    if not fichero:
        return None
    return DIR_DATOS / re.sub(r"[^\w\-]+", "_", hipotesis_id) / nombre_seguro(fichero)


def guardar(hipotesis_id: str, nombre: str, contenido: bytes) -> Path:
    if len(contenido) > MAX_BYTES:
        raise ValueError("El fichero supera los 50 MB")
    ruta = ruta_de(hipotesis_id, nombre)
    assert ruta is not None
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)
    return ruta


def _numero(v: str) -> float | None:
    t = v.strip().replace(",", ".")
    if not t or t.lower() in ("na", "nan", "null", "none", "n/a", "-", "."):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _ic_mediana(nums: list[float], remuestras: int = 2000) -> tuple[float, float]:
    """Intervalo percentil del 95 % para la mediana por bootstrap con semilla
    fija: mismo fichero, mismo intervalo. Es una aproximacion para orientar al
    juez, no sustituye el analisis prerregistrado."""
    import random

    if len(nums) < 4:
        return (min(nums), max(nums))
    rng = random.Random(12345)
    medianas = sorted(statistics.median(rng.choices(nums, k=len(nums))) for _ in range(remuestras))
    return (medianas[int(0.025 * remuestras)], medianas[int(0.975 * remuestras) - 1])


def _resumen_tabla(cabecera: list[str], filas: list[list[str]]) -> str:
    lineas = [f"Tabla: {len(filas)} filas, {len(cabecera)} columnas."]
    for i, col in enumerate(cabecera):
        valores = [f[i] if i < len(f) else "" for f in filas]
        nums = [n for n in (_numero(v) for v in valores) if n is not None]
        faltan = sum(1 for v in valores if not v.strip() or v.strip().lower() in ("na", "nan", "null", "none", "n/a"))
        if len(nums) >= max(3, len(valores) * 0.6):
            media = statistics.fmean(nums)
            sd = statistics.pstdev(nums) if len(nums) > 1 else 0.0
            ordenados = sorted(nums)
            q1, mediana, q3 = statistics.quantiles(ordenados, n=4) if len(nums) >= 4 else (ordenados[0], statistics.median(ordenados), ordenados[-1])
            positivos = sum(1 for x in nums if x > 0)
            negativos = sum(1 for x in nums if x < 0)
            ceros = len(nums) - positivos - negativos
            # Intervalo aproximado del 95 % para la mediana por remuestreo
            # determinista (semilla fija), util cuando el criterio pide la mediana.
            ic = _ic_mediana(nums)
            lineas.append(
                f"- {col} (numerica): n={len(nums)}, media={media:.4g}, sd={sd:.4g}, mediana={mediana:.4g} (IC95 aprox. {ic[0]:.4g} a {ic[1]:.4g}), Q1={q1:.4g}, Q3={q3:.4g}, min={min(nums):.4g}, max={max(nums):.4g}, positivos={positivos}, negativos={negativos}, ceros={ceros}, faltantes={faltan}"
            )
        else:
            distintos = {}
            for v in valores:
                k = v.strip() or "(vacio)"
                distintos[k] = distintos.get(k, 0) + 1
            top = sorted(distintos.items(), key=lambda kv: -kv[1])[:8]
            lineas.append(f"- {col} (categorica): {len(distintos)} valores distintos; mas frecuentes: " + ", ".join(f"{k}={n}" for k, n in top) + f"; faltantes={faltan}")
    return "\n".join(lineas)


def resumir(ruta: Path, filas_muestra: int = 40) -> tuple[str, str]:
    """(resumen determinista, muestra literal)."""
    suf = ruta.suffix.lower()
    if suf == ".pdf":
        import pymupdf

        textos = []
        with pymupdf.open(str(ruta)) as doc:
            for p in doc:
                t = p.get_text("text").strip()
                if t:
                    textos.append(f"[pag. {p.number + 1}]\n{t}")
        texto = "\n\n".join(textos)
        return f"PDF de {len(textos)} paginas con texto, {len(texto)} caracteres.", texto[:12000]
    raw = ruta.read_bytes()
    try:
        texto = raw.decode("utf-8")
    except UnicodeDecodeError:
        texto = raw.decode("latin-1", errors="replace")
    if suf == ".json":
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError:
            return f"JSON invalido, {len(texto)} caracteres.", texto[:8000]
        if isinstance(datos, list) and datos and isinstance(datos[0], dict):
            cabecera = sorted({k for d in datos for k in d})
            filas = [[str(d.get(k, "")) for k in cabecera] for d in datos]
            return _resumen_tabla(cabecera, filas), json.dumps(datos[:filas_muestra], ensure_ascii=False)[:8000]
        return f"JSON con {len(texto)} caracteres.", texto[:8000]
    if suf in (".csv", ".tsv", ".txt") and ("," in texto[:2000] or ";" in texto[:2000] or "\t" in texto[:2000]):
        try:
            dialecto = csv.Sniffer().sniff(texto[:5000], delimiters=",;\t|")
        except csv.Error:
            dialecto = csv.excel
        lector = list(csv.reader(io.StringIO(texto), dialecto))
        lector = [f for f in lector if any(c.strip() for c in f)]
        if len(lector) >= 2:
            cabecera, filas = lector[0], lector[1:]
            muestra = "\n".join(dialecto.delimiter.join(f) for f in lector[: filas_muestra + 1])
            return _resumen_tabla(cabecera, filas), muestra[:8000]
    return f"Texto de {len(texto)} caracteres y {texto.count(chr(10)) + 1} lineas.", texto[:8000]
