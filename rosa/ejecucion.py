"""Ejecucion aislada de analisis in silico (ROSA2018, etapas 5 y 6).

Que hace: toma un script escrito por el modelo y lo corre contra un fichero
de datos, sin red, con los datos en solo lectura, con limite de tiempo y de
memoria, y devuelve un registro de ejecucion (RunRecord) con el codigo, el
entorno, la semilla, la salida y el estado real. "No ejecutado", "error
tecnico" y "sin efecto detectable" son estados distintos; un tiempo agotado
es un error tecnico, nunca un resultado nulo.

Donde corre, por orden de preferencia:
1. Docker (`docker run --network none --memory ... -v datos:ro`): un
   contenedor por ejecucion con la imagen `rosa-sandbox` (pandas, numpy,
   scipy, statsmodels). Requiere Docker Desktop encendido.
2. Apple `container` (macOS 15.5 o superior, Apple Silicon): una micro-VM
   por ejecucion, mismas banderas.
3. Aislamiento blando local: solo si el dataset esta marcado como sintetico
   y la politica lo permite. Un subproceso `python -I` con el entorno
   vaciado, limite de CPU, y un preambulo que bloquea red, subprocesos y
   escritura fuera del directorio de trabajo. No protege de un adversario;
   protege de un error del modelo. Con datos reales no se usa nunca.

Si no hay runtime valido, el registro queda en `no_ejecutado` con el motivo
y la interfaz dice que hay que encender Docker. Nunca se cae a ejecutar en
la maquina sin aislamiento con datos reales.

Contrato de salida del script: lineas `RESULTADO nombre=valor`,
`BASELINE nombre=valor`, `CONTROL nombre=valor` y, si aplica,
`NO_EVALUABLE motivo`. Aqui se parsean; el modelo no vuelve a tocar las
cifras.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rosa import config, politicas

IMAGEN = os.environ.get("ROSA_SANDBOX_IMAGEN", "rosa-sandbox:1")
DIR_TRABAJO = Path(config.RAIZ) / "datos" / "_ejecuciones"
PAQUETES_SANDBOX = ["pandas", "numpy", "scipy", "statsmodels"]

# Permitir el aislamiento blando local con datos sinteticos. Es una politica:
# se cambia aqui, con commit, no desde la interfaz.
PERMITIR_LOCAL_SINTETICO = True


@dataclass
class Resultado:
    estado: str  # no_ejecutado | error_tecnico | completado | tiempo_agotado
    runtime: str  # docker | container | local_sintetico | ninguno
    salida: str = ""
    error: str = ""
    codigo_salida: int | None = None
    duracion_s: float | None = None
    resultados: dict[str, str] = field(default_factory=dict)
    baseline: dict[str, str] = field(default_factory=dict)
    control: dict[str, str] = field(default_factory=dict)
    no_evaluable: str | None = None
    paquetes: list[dict[str, str]] = field(default_factory=list)


def hash_fichero(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Deteccion del runtime
# ---------------------------------------------------------------------------


def _docker_disponible() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        r = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=8)
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:  # noqa: BLE001
        return False


def _container_disponible() -> bool:
    if not shutil.which("container"):
        return False
    try:
        r = subprocess.run(["container", "system", "status"], capture_output=True, text=True, timeout=8)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def runtime_disponible(sintetico: bool) -> tuple[str, str]:
    """(runtime, motivo). `ninguno` con el motivo si no hay forma segura."""
    if _docker_disponible():
        return "docker", ""
    if _container_disponible():
        return "container", ""
    if sintetico and PERMITIR_LOCAL_SINTETICO:
        return "local_sintetico", "Sin Docker ni Apple container: aislamiento blando local, permitido solo porque el dataset es sintetico"
    motivo = "Sin runtime de aislamiento: enciende Docker Desktop (o instala Apple container) para ejecutar analisis con datos reales."
    if sintetico:
        motivo = "Sin runtime de aislamiento y la politica no permite ejecucion local."
    return "ninguno", motivo


def _asegurar_imagen(runtime: str) -> str | None:
    """Construye la imagen del sandbox si no existe. Devuelve un error o None."""
    cli = runtime
    try:
        r = subprocess.run([cli, "image", "inspect", IMAGEN], capture_output=True, text=True, timeout=20)
        if r.returncode == 0:
            return None
        dockerfile = Path(config.RAIZ) / "rosa" / "sandbox"
        r = subprocess.run([cli, "build", "-t", IMAGEN, str(dockerfile)], capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            return f"No se pudo construir la imagen del sandbox: {r.stderr[-800:]}"
        return None
    except subprocess.TimeoutExpired:
        return "La construccion de la imagen del sandbox tardo mas de 15 minutos"
    except Exception as ex:  # noqa: BLE001
        return f"No se pudo preparar la imagen del sandbox: {ex}"


# ---------------------------------------------------------------------------
# Ejecucion
# ---------------------------------------------------------------------------

PREAMBULO_LOCAL = r'''
# Preambulo de aislamiento blando de Rosa (solo datos sinteticos).
import builtins as _b, os as _os, sys as _sys, resource as _res
_TRABAJO = _os.path.realpath(_os.getcwd())
_DATOS = _os.path.realpath(_os.environ.get("ROSA_DATOS", ""))
_res.setrlimit(_res.RLIMIT_CPU, (__CPU__, __CPU__))
_open = _b.open
def _open_vigilado(f, mode="r", *a, **k):
    p = _os.path.realpath(str(f)) if not isinstance(f, int) else None
    if p is not None and ("w" in mode or "a" in mode or "+" in mode or "x" in mode) and not p.startswith(_TRABAJO):
        raise PermissionError("Rosa: escritura fuera del directorio de trabajo")
    return _open(f, mode, *a, **k)
_b.open = _open_vigilado
import socket as _sock
def _sin_red(*a, **k):
    raise PermissionError("Rosa: red deshabilitada en el sandbox")
_sock.socket = _sin_red
_sock.create_connection = _sin_red
import subprocess as _sp
_sp.Popen = _sin_red
_sp.run = _sin_red
_os.system = _sin_red
_os.popen = _sin_red
_os.remove = _sin_red
_os.unlink = _sin_red
_os.rmdir = _sin_red
import shutil as _sh
_sh.rmtree = _sin_red
_sh.move = _sin_red
del _b, _sock, _sp, _sh
# Fin del preambulo.
'''


MAX_CIFRAS = 60
CLAVES_PRIORITARIAS = ("valor_reproducido", "p_valor", "p", "estadistico", "n", "diferencia", "ic95_inferior", "ic95_superior", "numerador", "denominador")


def _parsear(salida: str) -> tuple[dict[str, str], dict[str, str], dict[str, str], str | None]:
    """Las lineas del contrato. Si un script imprime una cifra por gen, se
    guardan las prioritarias y las primeras hasta MAX_CIFRAS: el registro no
    debe pesar megas, y `valor_reproducido` nunca se pierde."""
    resultados: dict[str, str] = {}
    baseline: dict[str, str] = {}
    control: dict[str, str] = {}
    no_evaluable: str | None = None
    for linea in salida.splitlines():
        l = linea.strip()
        m = re.match(r"^(RESULTADO|BASELINE|CONTROL)\s+([^\s=]+)\s*=\s*(.+)$", l)
        if m:
            destino = {"RESULTADO": resultados, "BASELINE": baseline, "CONTROL": control}[m.group(1)]
            clave = m.group(2)
            if len(destino) >= MAX_CIFRAS and clave not in destino and not any(clave.startswith(c) for c in CLAVES_PRIORITARIAS):
                destino.setdefault("_omitidas", "0")
                destino["_omitidas"] = str(int(destino["_omitidas"]) + 1)
                continue
            destino[clave] = m.group(3).strip()[:120]
            continue
        m = re.match(r"^NO_EVALUABLE\s*(.*)$", l)
        if m and no_evaluable is None:
            no_evaluable = m.group(1).strip() or "El script marco el analisis como no evaluable"
    return resultados, baseline, control, no_evaluable


def _paquetes(runtime: str) -> list[dict[str, str]]:
    if runtime == "local_sintetico":
        salida = []
        for p in PAQUETES_SANDBOX:
            try:
                mod = __import__(p)
                salida.append({"nombre": p, "version": getattr(mod, "__version__", "?")})
            except Exception:  # noqa: BLE001
                salida.append({"nombre": p, "version": "no instalado"})
        return salida
    return [{"nombre": "imagen", "version": IMAGEN}]


def ejecutar(codigo: str, ruta_datos: Path, semilla: int, sintetico: bool, id_ejecucion: str) -> Resultado:
    """Corre el script contra el fichero. Bloqueante: llamarlo desde un hilo."""
    runtime, motivo = runtime_disponible(sintetico)
    if runtime == "ninguno":
        return Resultado(estado="no_ejecutado", runtime="ninguno", error=motivo)
    DIR_TRABAJO.mkdir(parents=True, exist_ok=True)
    trabajo = Path(tempfile.mkdtemp(prefix=f"{id_ejecucion}-", dir=DIR_TRABAJO))
    inicio = time.monotonic()
    tiempo = politicas.SEGUNDOS_MAX_EJECUCION
    try:
        if runtime in ("docker", "container"):
            err = _asegurar_imagen(runtime)
            if err:
                return Resultado(estado="no_ejecutado", runtime=runtime, error=err)
            (trabajo / "analisis.py").write_text(codigo, encoding="utf-8")
            cmd = [
                runtime, "run", "--rm",
                "--network", "none",
                "--memory", f"{politicas.MEMORIA_MAX_EJECUCION_MB}m",
                "--cpus", "2",
                "-v", f"{ruta_datos.resolve()}:/datos/{ruta_datos.name}:ro",
                "-v", f"{trabajo}:/trabajo",
                "-w", "/trabajo",
                "-e", f"ROSA_SEMILLA={semilla}",
                IMAGEN, "python", "-I", "/trabajo/analisis.py",
            ]
            entorno = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
            if runtime == "docker" and os.environ.get("DOCKER_HOST"):
                entorno["DOCKER_HOST"] = os.environ["DOCKER_HOST"]
            cwd = None
        else:
            preambulo = PREAMBULO_LOCAL.replace("__CPU__", str(tiempo))
            (trabajo / "analisis.py").write_text(preambulo + "\n" + codigo, encoding="utf-8")
            cmd = [sys.executable, "-I", str(trabajo / "analisis.py")]
            entorno = {"ROSA_DATOS": str(ruta_datos.resolve()), "ROSA_SEMILLA": str(semilla), "PATH": "/usr/bin:/bin", "HOME": str(trabajo), "PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "Agg"}
            cwd = str(trabajo)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=tiempo + 30, env=entorno, cwd=cwd)
        except subprocess.TimeoutExpired as ex:
            return Resultado(estado="tiempo_agotado", runtime=runtime, salida=(ex.stdout or "")[-4000:] if isinstance(ex.stdout, str) else "", error=f"Tiempo agotado tras {tiempo} s. Es un error tecnico, no un resultado nulo.", duracion_s=round(time.monotonic() - inicio, 1))
        duracion = round(time.monotonic() - inicio, 1)
        # Se parsea la salida completa (un script puede imprimir mucho antes de la
        # cifra final) y se guarda recortada.
        resultados, baseline, control, no_evaluable = _parsear(r.stdout)
        salida = r.stdout[-12000:]
        error = r.stderr[-4000:]
        if r.returncode != 0:
            return Resultado(estado="error_tecnico", runtime=runtime, salida=salida, error=error or f"Codigo de salida {r.returncode}", codigo_salida=r.returncode, duracion_s=duracion, resultados=resultados, baseline=baseline, control=control, no_evaluable=no_evaluable, paquetes=_paquetes(runtime))
        if not resultados and not no_evaluable:
            return Resultado(estado="error_tecnico", runtime=runtime, salida=salida, error="El script termino sin imprimir ninguna linea RESULTADO ni NO_EVALUABLE: no cumplio el contrato de salida.", codigo_salida=0, duracion_s=duracion, paquetes=_paquetes(runtime))
        return Resultado(estado="completado", runtime=runtime, salida=salida, error=error, codigo_salida=0, duracion_s=duracion, resultados=resultados, baseline=baseline, control=control, no_evaluable=no_evaluable, paquetes=_paquetes(runtime))
    finally:
        shutil.rmtree(trabajo, ignore_errors=True)


# ---------------------------------------------------------------------------
# Comprobaciones deterministas del auditor (Killer II sin modelo)
# ---------------------------------------------------------------------------


def comprobaciones_deterministas(codigo: str, plan: dict[str, Any], res: Resultado) -> list[dict[str, str]]:
    """Lo que se puede comprobar sin juez: semilla, fuga por ajuste antes de
    partir, variables del plan presentes en el codigo, baseline y control
    presentes, n por grupo, multiplicidad."""
    c: list[dict[str, str]] = []
    tiene_semilla = bool(re.search(r"random_state|\.seed\(|default_rng\(|ROSA_SEMILLA", codigo))
    c.append({"comprobacion": "semilla", "resultado": "pasa" if tiene_semilla else "falla", "detalle": "El codigo fija la semilla" if tiene_semilla else "El codigo no fija ninguna semilla: no es repetible"})
    pos_fit = codigo.find(".fit(")
    pos_split = codigo.find("train_test_split(")
    if pos_split != -1 and pos_fit != -1 and pos_fit < pos_split:
        c.append({"comprobacion": "fuga_de_datos", "resultado": "falla", "detalle": "Hay un ajuste (.fit) antes de partir en entrenamiento y prueba: posible fuga"})
    elif re.search(r"(StandardScaler|MinMaxScaler|SimpleImputer)\(\)\.fit_transform\(", codigo) and pos_split != -1:
        c.append({"comprobacion": "fuga_de_datos", "resultado": "no_comprobable", "detalle": "Hay un escalado o imputacion global; revisar si se ajusto solo con el entrenamiento"})
    else:
        c.append({"comprobacion": "fuga_de_datos", "resultado": "pasa" if pos_split != -1 else "no_aplica", "detalle": "Sin ajuste antes de partir" if pos_split != -1 else "No hay particion entrenamiento y prueba en este analisis"})
    variables = [re.sub(r"\s*\(.*\)$", "", v).strip() for v in plan.get("variables", [])]
    faltan = [v for v in variables if v and v.split()[0] not in codigo]
    c.append({"comprobacion": "coincide_con_plan", "resultado": "pasa" if not faltan else "falla", "detalle": "Todas las variables del plan aparecen en el codigo" if not faltan else "Variables del plan que no aparecen en el codigo: " + ", ".join(faltan[:6])})
    tiene_base = bool(res.baseline)
    tiene_control = bool(res.control)
    c.append({"comprobacion": "baseline_y_control", "resultado": "pasa" if (tiene_base and tiene_control) else ("no_aplica" if res.no_evaluable else "falla"), "detalle": f"Baseline: {'si' if tiene_base else 'no'}. Control negativo: {'si' if tiene_control else 'no'}"})
    ns = []
    for k, v in res.resultados.items():
        if re.match(r"^n(_|$)", k, re.I):
            try:
                ns.append(float(v))
            except ValueError:
                pass
    if ns:
        c.append({"comprobacion": "tamano_muestral", "resultado": "falla" if min(ns) < 5 else "pasa", "detalle": f"n minimo por grupo {min(ns):g}" + (" (menos de 5)" if min(ns) < 5 else "")})
    else:
        c.append({"comprobacion": "tamano_muestral", "resultado": "no_comprobable", "detalle": "El codigo no imprimio n por grupo (RESULTADO n_...)"})
    pvalores = [k for k in res.resultados if re.search(r"^p(_|val|$)", k, re.I)]
    corrige = bool(re.search(r"bonferroni|holm|fdr|multipletests|benjamini", codigo, re.I)) or "una sola" in (plan.get("correccionMultiplicidad") or "").lower()
    c.append({"comprobacion": "multiplicidad", "resultado": "pasa" if (len(pvalores) <= 1 or corrige) else "falla", "detalle": f"{len(pvalores)} p-valores impresos; correccion en el codigo: {'si' if corrige else 'no'}"})
    return c
