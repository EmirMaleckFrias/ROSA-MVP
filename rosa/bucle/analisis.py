"""Analisis in silico y puerta de reproduccion (ROSA2018, etapas 2, 5, 6 y 7).

El orden es siempre el mismo y ningun paso ve lo que no le toca:

1. Plan congelado (`PlanificarAnalisis`, cerebro): solo con el esquema de los
   datos (diccionario y estadisticos), nunca las filas. Se guarda con su
   hash antes de escribir una linea de codigo.
2. Codigo (`EscribirCodigo`, cerebro) que ejecuta ese plan y nada mas, con
   el contrato de salida RESULTADO / BASELINE / CONTROL / NO_EVALUABLE.
3. Ejecucion en el sandbox (`rosa/ejecucion.py`): sin red, datos en solo
   lectura, tiempo y memoria limitados. Un error tecnico se intenta reparar
   dos veces sin cambiar el plan.
4. Interpretacion (`InterpretarEjecucion`, juez): que dicen las cifras
   contra el umbral del plan. Efecto detectado, sin efecto detectable, o no
   evaluable.
5. Auditoria (Killer II: comprobaciones deterministas mas `AuditarAnalisis`,
   juez): valido, no valido o no evaluable computacionalmente.
6. Solo un analisis valido entra como afirmacion de tipo dato (clase
   derivado) a la hipotesis, con su trayectoria, y la conclusion se rehace.

La puerta de reproduccion usa el mismo camino con planes de tipo
`reproduccion`: la cifra obtenida se compara con la publicada dentro de la
tolerancia fijada antes, y la puerta se abre al superar las requeridas.
"""

from __future__ import annotations

import asyncio
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rosa import config, ejecucion as X, politicas
from rosa import datos as D
from rosa import skills as SK
from rosa.bucle import contexto as T
from rosa.bucle.pista import Pista
from rosa.estado import acciones as A
from rosa.estado import plantilla as P
from rosa.modulos.contador import PresupuestoAgotado

MAX_REPARACIONES = 2


def _texto_plan(plan: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Tipo: {plan['tipo']}",
            f"Pregunta: {plan['pregunta']}",
            "Variables: " + "; ".join(plan["variables"]),
            f"Población: {plan['poblacion']}",
            "Preprocesado: " + " -> ".join(plan["preprocesado"]),
            f"Prueba: {plan['prueba']}",
            f"H0: {plan['hipotesisNula']}",
            f"H1: {plan['hipotesisAlternativa']}",
            f"Alfa: {plan['alpha']}",
            f"Dirección esperada: {plan['direccionEsperada']}",
            f"Efecto mínimo: {plan['tamanoEfectoMinimo']}",
            f"Baseline: {plan['baseline']}",
            f"Control negativo: {plan['controlNegativo']}",
            f"Multiplicidad: {plan['correccionMultiplicidad']}",
            f"Umbral de efecto: {plan['umbralEfecto']}",
            f"No evaluable si: {plan['criterioNoEvaluable']}",
            f"Semilla: {plan['semilla']}",
        ]
        + (["SALIDA OBLIGATORIA: la cifra comparada con la publicada se imprime como RESULTADO valor_reproducido=<numero>, con ese nombre exacto."] if plan.get("tipo") == "reproduccion" else [])
    )


def _dataset_de(e: dict[str, Any], investigacion_id: str, dataset_id: str) -> tuple[dict[str, Any] | None, Path | None]:
    inv = next((i for i in e["investigaciones"] if i["id"] == investigacion_id), None)
    ds = next((d for d in (inv or {}).get("datasets", []) if d["id"] == dataset_id), None)
    if not ds or not (ds.get("procedencia") or {}).get("fichero"):
        return ds, None
    ruta = D.ruta_dataset(investigacion_id, dataset_id, ds["procedencia"]["fichero"])
    return ds, (ruta if ruta.exists() else None)


def _puerta_permite(inv: dict[str, Any]) -> tuple[bool, str]:
    p = inv.get("puertaReproduccion") or P.puerta_reproduccion()
    if p["estado"] in ("abierta", "eximida"):
        return True, ""
    return False, f"Puerta de reproducción bloqueada: {p['superadas']} de {p['requeridas']} análisis publicados reproducidos. Registra y reproduce los que faltan, o exime la puerta con motivo."


def _limpiar_codigo(texto: str) -> str:
    t = texto.strip()
    m = re.search(r"```(?:python)?\s*\n(.*?)```", t, re.S)
    if m:
        t = m.group(1)
    return t.strip() + "\n"


def _cambiar_semilla(codigo: str, semilla: int, nueva: int) -> str:
    """Cambia la semilla solo en las lineas que fijan aleatoriedad (seed,
    random_state, default_rng, RandomState, ROSA_SEMILLA): un filtro como
    `edad > 42` no se toca."""
    lineas = []
    for linea in codigo.splitlines():
        if re.search(r"seed|random_state|default_rng|RandomState|SEMILLA|semilla|shuffle\(|permutation\(", linea, re.I):
            linea = re.sub(r"\b" + str(semilla) + r"\b", str(nueva), linea)
        lineas.append(linea)
    return "\n".join(lineas) + ("\n" if codigo.endswith("\n") else "")


def _actualizar_run(e: dict[str, Any], run_id: str, campos: dict[str, Any]) -> bool:
    r = next((x for x in e.get("ejecuciones", []) if x["id"] == run_id), None)
    if not r:
        return False
    r.update(campos)
    return True


async def _ensayo_en_seco(ctx, plan: dict[str, Any], codigo: str, ruta: Path, esquema: str, run_id: str, entorno: str, ficheros: dict[str, str] | None, pista: Pista) -> tuple[str, dict[str, Any]]:
    """Corre el codigo sobre datos sinteticos con la forma del dataset; si
    falla tecnicamente, intenta repararlo ahi (hasta MAX_REPARACIONES) antes
    de ir a los datos reales. Devuelve (codigo posiblemente reparado, registro)."""
    import tempfile

    from rosa import sintetico as SINT

    registro: dict[str, Any] = {"estado": "no_hecho", "intentos": 0, "error": "", "filas": 0}
    try:
        destino = Path(tempfile.mkdtemp(prefix="sintetico-")) / f"sintetico-{ruta.name}"
        perfil = await asyncio.to_thread(SINT.generar, ruta, destino, SINT.FILAS_POR_DEFECTO, plan["semilla"])
        registro["filas"] = perfil["filas"]
    except Exception as ex:  # noqa: BLE001
        registro.update(estado="no_hecho", error=f"No se pudo fabricar la tabla sintética: {str(ex)[:160]}")
        pista.nota(registro["error"])
        return codigo, registro
    for intento in range(MAX_REPARACIONES + 1):
        registro["intentos"] = intento + 1
        pista.accion(f"Ensayo en seco sobre {registro['filas']} filas sintéticas, intento {intento + 1}")
        r = await asyncio.to_thread(X.ejecutar, codigo, destino, plan["semilla"], True, f"{run_id}-seco{intento}", entorno, ficheros)
        if r.estado == "completado":
            registro.update(estado="completado", error="")
            pista.resultado("Ensayo en seco completado: el código corre sobre la forma del dataset (las cifras sintéticas no cuentan)")
            break
        if r.estado in ("no_ejecutado", "tiempo_agotado"):
            registro.update(estado=r.estado, error=r.error[-300:])
            pista.nota(f"Ensayo en seco {r.estado}: {r.error[-160:]}")
            break
        registro.update(estado="error_tecnico", error=(r.error or r.salida)[-300:])
        if intento < MAX_REPARACIONES:
            pista.error(f"El ensayo en seco fallo: {r.error[-200:]}. Se repara antes de tocar los datos reales")
            try:
                p2 = await ctx.llamar("cerebro", ctx.programas.reparar, plan=_texto_plan(plan), codigo=codigo, error=r.error[-1500:] or r.salida[-800:], esquema_datos=esquema)
                codigo = _limpiar_codigo(p2.codigo_corregido)
            except PresupuestoAgotado:
                raise
            except Exception as ex:  # noqa: BLE001
                pista.error(f"No se pudo reparar en seco: {str(ex)[:120]}")
                break
    return codigo, registro


def _verificar_congelado(plan: dict[str, Any], ruta: Path) -> str | None:
    """None si el plan y los datos son los congelados; si no, el motivo."""
    if plan.get("hashPlan") and P.hash_plan(plan) != plan["hashPlan"]:
        return f"El plan {plan['id']} no corresponde a su hash congelado ({plan['hashPlan']}): se alteró después de congelarlo. No se ejecuta."
    if plan.get("hashDatos"):
        try:
            actual = X.hash_fichero(ruta)
        except OSError as ex:
            return f"No se pudo leer el fichero de datos para comprobar su hash: {ex}"
        if actual != plan["hashDatos"]:
            return f"El fichero de datos cambio desde que se congeló el plan (sha256 {actual[:12]} frente a {plan['hashDatos'][:12]}). No se ejecuta."
    return None


async def _correr_plan(ctx, plan: dict[str, Any], ds: dict[str, Any], ruta: Path, esquema: str, hipotesis_id: str | None, tipo: str, pista: Pista) -> dict[str, Any]:
    """Código, ejecución (con reparaciones), interpretación y auditoría.
    Devuelve el registro de ejecución ya guardado en el estado."""
    proc = ds["procedencia"]
    sintetico = bool(proc.get("sintetico"))
    ruta_en_sandbox = f"/datos/{ruta.name}"
    runtime, _ = X.runtime_disponible(sintetico)
    if runtime == "local_sintetico":
        ruta_en_sandbox = str(ruta.resolve())
    skills = SK.para_texto(_texto_plan(plan) + " " + esquema[:1500] + " " + ds.get("nombre", ""))
    entorno = plan.get("entorno") or SK.entorno_de(skills)
    ficheros = SK.scripts_de(skills)
    pista.accion(f"Escribiendo el código del plan {plan['hashPlan']} (semilla {plan['semilla']})" + (f"; skills: {', '.join(s_['nombre'] for s_ in skills)}" if skills else "") + f"; entorno {entorno}")
    pred = await ctx.llamar("cerebro", ctx.programas.codigo, plan=_texto_plan(plan), esquema_datos=esquema, ruta_datos=ruta_en_sandbox, semilla=plan["semilla"], skills=SK.texto_para_prompt(skills))
    codigo = _limpiar_codigo(pred.codigo)
    run = P.nueva_ejecucion(ctx.investigacion_id, hipotesis_id, plan["id"], tipo, codigo, plan["semilla"], plan["hashDatos"], P.ahora_ms())
    run["hashPlan"] = plan["hashPlan"]
    run["estado"] = "en_curso"
    run["skills"] = [s_["nombre"] for s_ in skills]
    run["entorno"] = {"python": run.get("entorno", {}).get("python", ""), "paquetes": X.versiones_imagen(runtime, entorno) if runtime in ("docker", "container") else X._paquetes(runtime), "imagen": entorno}
    ctx.mutar(lambda e: e.setdefault("ejecuciones", []).append(run) or True, "ejecucion")
    res = None
    # El sello de congelacion se comprueba, no se cree: el plan tiene que seguir
    # correspondiendo a su hash y el fichero de datos al hash con el que se planifico.
    bloqueo = _verificar_congelado(plan, ruta)
    if bloqueo:
        pista.error(bloqueo)
        res = X.Resultado(estado="no_ejecutado", runtime=runtime, error=bloqueo)
    # Ensayo en seco: el mismo codigo sobre una tabla sintetica con la forma del
    # dataset (columnas, tipos, rangos) antes de tocar los datos reales. Detecta
    # variables mal nombradas o pruebas inaplicables sin gastar la ejecucion real
    # ni el presupuesto de reparacion sobre ella. Sus cifras no cuentan.
    if not bloqueo and not sintetico:
        codigo, run["ensayoSeco"] = await _ensayo_en_seco(ctx, plan, codigo, ruta, esquema, run["id"], entorno, ficheros, pista)
        ctx.mutar(lambda e: _actualizar_run(e, run["id"], {"ensayoSeco": run["ensayoSeco"], "codigo": codigo}), "ensayo_seco")
    for intento in range(0 if bloqueo else MAX_REPARACIONES + 1):
        pista.accion(f"Ejecutando en el sandbox ({runtime}), intento {intento + 1}")
        res = await asyncio.to_thread(X.ejecutar, codigo, ruta, plan["semilla"], sintetico, run["id"], entorno, ficheros)
        if res.estado in ("completado", "no_ejecutado", "tiempo_agotado"):
            break
        if intento < MAX_REPARACIONES:
            pista.error(f"Error técnico: {res.error[-200:]}. Se intenta reparar sin cambiar el plan")
            try:
                p2 = await ctx.llamar("cerebro", ctx.programas.reparar, plan=_texto_plan(plan), codigo=codigo, error=res.error[-1500:] or res.salida[-800:], esquema_datos=esquema)
                codigo = _limpiar_codigo(p2.codigo_corregido)
            except PresupuestoAgotado:
                raise
            except Exception as ex:  # noqa: BLE001
                pista.error(f"No se pudo reparar: {str(ex)[:120]}")
                break
    assert res is not None
    # Repeticiones con otras semillas si el plan tiene aleatoriedad (permutacion,
    # bootstrap, barajado): tres corridas, como pide CORE-Bench, para ver si la
    # cifra se mueve. Se cambia la semilla en el codigo y en el entorno.
    repeticiones: list[dict[str, Any]] = []
    aleatorio = bool(re.search(r"permut|bootstrap|remuestr|aleator|baraj|shuffle", (plan.get("prueba", "") + " " + plan.get("baseline", "") + " " + plan.get("controlNegativo", "")).lower()))
    if res.estado == "completado" and not res.no_evaluable and aleatorio:
        for extra in (1, 2):
            semilla2 = plan["semilla"] + extra
            codigo2 = _cambiar_semilla(codigo, plan["semilla"], semilla2)
            pista.accion(f"Repetición con semilla {semilla2}")
            r2 = await asyncio.to_thread(X.ejecutar, codigo2, ruta, semilla2, sintetico, run["id"] + f"-s{extra}", entorno, ficheros)
            repeticiones.append({"semilla": semilla2, "estado": r2.estado, "resultados": r2.resultados if r2.estado == "completado" else {}})
    interpretacion = None
    if res.estado == "completado":
        if res.no_evaluable:
            interpretacion = {"estado": "no_evaluable", "resumen": f"El análisis no se pudo evaluar con estos datos: {res.no_evaluable}"}
        else:
            texto_rep = ""
            if repeticiones:
                texto_rep = "\n\nRepeticiones con otras semillas (mismo plan y codigo):\n" + "\n".join(f"- semilla {r['semilla']} ({r['estado']}): " + ("; ".join(f"{k}={v}" for k, v in r["resultados"].items()) or "sin cifras") for r in repeticiones)
            try:
                pi = await ctx.llamar("juez", ctx.programas.interpretar, plan=_texto_plan(plan), resultados=("\n".join(f"{k}={v}" for k, v in res.resultados.items()) or "ninguna") + texto_rep, baseline="\n".join(f"{k}={v}" for k, v in res.baseline.items()) or "ninguna", control_negativo="\n".join(f"{k}={v}" for k, v in res.control.items()) or "ninguna")
                interpretacion = {"estado": pi.interpretacion.estado, "resumen": pi.interpretacion.resumen.strip(), "cifras": [{"nombre": c.nombre, "valor": c.valor} for c in pi.interpretacion.cifras_clave][:10]}
            except PresupuestoAgotado:
                raise
            except Exception as ex:  # noqa: BLE001
                interpretacion = {"estado": "no_evaluable", "resumen": f"El juez no pudo interpretar las cifras: {str(ex)[:120]}"}
    auditoria = None
    deterministas = X.comprobaciones_deterministas(codigo, plan, res) if res.estado == "completado" else []
    if res.estado == "completado" and interpretacion and interpretacion["estado"] != "no_evaluable":
        try:
            pa = await ctx.llamar(
                "juez",
                ctx.programas.auditar_analisis,
                plan=_texto_plan(plan),
                codigo=codigo[:12000],
                salida=res.salida[-6000:],
                interpretacion=f"{interpretacion['estado']}: {interpretacion['resumen']}",
                comprobaciones_deterministas="\n".join(f"- {c['comprobacion']}: {c['resultado']}. {c['detalle']}" for c in deterministas),
            )
            au = pa.auditoria
            comprobaciones = deterministas + [{"comprobacion": c.comprobacion, "resultado": c.resultado, "detalle": c.detalle.strip()[:300]} for c in au.comprobaciones]
            veredicto = au.veredicto
            # Las deterministas criticas mandan: una fuga o un plan no cumplido invalidan aunque el juez dude.
            if any(c["comprobacion"] in ("fuga_de_datos", "coincide_con_plan") and c["resultado"] == "falla" for c in deterministas):
                veredicto = "no_valido"
            auditoria = {"veredicto": veredicto, "comprobaciones": comprobaciones, "motivo": au.motivo.strip(), "quien": ctx.modelos.juez.model, "fecha": P.ahora_ms()}
            run_plausible = bool(au.plausibilidad_verificada)
        except PresupuestoAgotado:
            raise
        except Exception as ex:  # noqa: BLE001
            auditoria = {"veredicto": "no_evaluable_computacionalmente", "comprobaciones": deterministas, "motivo": f"El auditor no respondió: {str(ex)[:120]}", "quien": ctx.modelos.juez.model, "fecha": P.ahora_ms()}
            run_plausible = None
    else:
        run_plausible = None
    ahora = P.ahora_ms()

    def guardar(e: dict[str, Any]) -> bool:
        x = next((r for r in e.get("ejecuciones", []) if r["id"] == run["id"]), None)
        if not x:
            return False
        x.update(
            codigo=codigo,
            estado=res.estado,
            runtime=res.runtime,
            codigoSalida=res.codigo_salida,
            duracionS=res.duracion_s,
            salida=res.salida[-8000:],
            error=res.error[-3000:],
            resultados=res.resultados,
            baseline=res.baseline,
            controlNegativo=res.control,
            interpretacion=interpretacion,
            auditoria=auditoria,
            plausibilidadVerificada=run_plausible,
            repeticiones=repeticiones,
            fin=ahora,
        )
        x["entorno"]["paquetes"] = res.paquetes
        return True

    ctx.mutar(guardar, "ejecucion")
    estado_txt = res.estado if res.estado != "completado" else (interpretacion or {}).get("estado", "completado")
    pista.resultado(f"Ejecución {run['id']}: {estado_txt}" + (f"; auditoría {auditoria['veredicto']}" if auditoria else "") + (f". {res.error[-160:]}" if res.estado != "completado" else ""))
    run.update(estado=res.estado, resultados=res.resultados, baseline=res.baseline, controlNegativo=res.control, interpretacion=interpretacion, auditoria=auditoria, error=res.error, runtime=res.runtime)
    return run


async def analizar_hipotesis(ctx, h: dict[str, Any], dataset_id: str, pregunta: str, pista: Pista) -> dict[str, Any] | None:
    """Un análisis in silico completo sobre una hipótesis. Respeta la puerta
    de reproducción, el tope de evaluaciones costosas y el libro de
    procedencia. Devuelve la ejecución o None si no se pudo ni empezar."""
    e = ctx.e
    inv = ctx.inv()
    ds, ruta = _dataset_de(e, ctx.investigacion_id, dataset_id)
    ahora = P.ahora_ms()
    motivo_bloqueo = None
    if not ds or ruta is None:
        motivo_bloqueo = "El dataset no tiene fichero en el servidor: subelo desde Objetivo y datos."
    elif ds["estado"] != "aprobado":
        motivo_bloqueo = "El contrato de datos no está aprobado."
    elif (ds.get("procedencia") or {}).get("usoIAAutorizado") != "si":
        motivo_bloqueo = "El libro de procedencia no marca el uso con IA como autorizado."
    else:
        ok, motivo = _puerta_permite(inv)
        if not ok:
            motivo_bloqueo = motivo
        else:
            corrida = ctx.corrida()
            usadas = corrida.get("_evaluacionesCostosas", 0)
            if usadas >= politicas.MAX_EVALUACIONES_COSTOSAS:
                motivo_bloqueo = f"Se alcanzó el tope de {politicas.MAX_EVALUACIONES_COSTOSAS} evaluaciones costosas por corrida (política)."
    if motivo_bloqueo:
        run = P.nueva_ejecucion(ctx.investigacion_id, h["id"], "sin-plan", "hipotesis", "", 0, (ds or {}).get("procedencia", {}).get("hash", "") if ds else "", ahora)
        run["error"] = motivo_bloqueo
        run["fin"] = ahora

        def anotar(e2: dict[str, Any]) -> bool:
            e2.setdefault("ejecuciones", []).append(run)
            y = next((z for z in e2["hipotesis"] if z["id"] == h["id"]), None)
            if y:
                y.setdefault("ejecuciones", []).append(run["id"])
                y.pop("_analisisPedido", None)
                y["procedencia"]["mensajes"].append({"id": P.nuevo_id("m"), "de": "rosa", "texto": f"No pude ejecutar el análisis: {motivo_bloqueo}", "creadoEn": ahora})
            A.con_evento(e2, ctx.investigacion_id, "analisis", f"Análisis no ejecutado: {motivo_bloqueo[:120]}", f"#/investigaciones/{ctx.investigacion_id}/hipotesis/{h['id']}", ahora)
            return True

        ctx.mutar(anotar, "ejecucion")
        pista.error(motivo_bloqueo)
        return None
    proc = ds["procedencia"]
    esquema = await asyncio.to_thread(D.esquema_para_modelo, ruta, proc, bool(proc.get("permiteLlmTerceros")))
    prediccion = (h.get("tarjeta") or {}).get("prediccionFalsable") or h["enunciado"]
    pista.accion(f"Congelando el plan de análisis sobre {ds['nombre']} (solo esquema, sin filas)")
    skills_plan = SK.para_texto(T.hipotesis_texto(h) + " " + (pregunta or "") + " " + esquema[:1500] + " " + ds.get("nombre", ""))
    pp = await ctx.llamar("cerebro", ctx.programas.planificar, hipotesis=T.hipotesis_texto(h), prediccion_falsable=prediccion, pregunta_pedida=pregunta or "", esquema_datos=esquema, limites="; ".join(inv["limites"]) or "Ninguno", skills=SK.texto_para_prompt(skills_plan))
    p = pp.plan
    plan = P.nuevo_plan_analisis(
        ctx.investigacion_id,
        h["id"],
        dataset_id,
        P.ahora_ms(),
        tipo=p.tipo if p.tipo != "reproduccion" else "confirmatorio",
        pregunta=p.pregunta.strip(),
        variables=list(p.variables)[:12],
        poblacion=p.poblacion.strip(),
        preprocesado=list(p.preprocesado)[:10],
        prueba=p.prueba.strip(),
        hipotesisNula=p.hipotesis_nula.strip(),
        hipotesisAlternativa=p.hipotesis_alternativa.strip(),
        alpha=float(p.alpha),
        direccionEsperada=p.direccion_esperada.strip(),
        tamanoEfectoMinimo=p.tamano_efecto_minimo.strip(),
        baseline=p.baseline.strip(),
        controlNegativo=p.control_negativo.strip(),
        correccionMultiplicidad=p.correccion_multiplicidad.strip(),
        umbralEfecto=p.umbral_efecto.strip(),
        criterioNoEvaluable=p.criterio_no_evaluable.strip(),
        entorno=getattr(p, "entorno", "tabular") or "tabular",
        semilla=12345,
        hashDatos=proc["hash"],
        autor=ctx.modelos.cerebro.model,
    )

    def congelar(e2: dict[str, Any]) -> bool:
        e2.setdefault("planesAnalisis", []).append(plan)
        c = next(x for x in e2["corridas"] if x["id"] == ctx.corrida_id)
        c["_evaluacionesCostosas"] = c.get("_evaluacionesCostosas", 0) + 1
        return True

    ctx.mutar(congelar, "plan_analisis")
    pista.resultado(f"Plan congelado {plan['hashPlan']}: {plan['prueba'][:80]}")
    run = await _correr_plan(ctx, plan, ds, ruta, esquema, h["id"], "hipotesis", pista)
    ahora = P.ahora_ms()
    valido = run.get("auditoria") and run["auditoria"]["veredicto"] == "valido" and run.get("interpretacion") and run["interpretacion"]["estado"] in ("efecto_detectado", "sin_efecto_detectable")

    def aplicar(e2: dict[str, Any]) -> bool:
        y = next((z for z in e2["hipotesis"] if z["id"] == h["id"]), None)
        if not y:
            return False
        y.setdefault("ejecuciones", []).append(run["id"])
        y.pop("_analisisPedido", None)
        y["coste"]["analisis"] = round(y["coste"]["analisis"] + 1.5, 2)
        y["procedencia"]["registro"].append(f"{datetime.fromtimestamp(ahora / 1000, tz=timezone.utc).isoformat()} análisis in silico {run['id']}: {run['estado']}" + (f", {run['interpretacion']['estado']}" if run.get("interpretacion") else "") + (f", auditoría {run['auditoria']['veredicto']}" if run.get("auditoria") else ""))
        if valido:
            from rosa import secuencial

            cifras = "; ".join(f"{k}={v}" for k, v in run["resultados"].items())
            y["evidenciaSecuencial"] = secuencial.agregar([r for r in e2.get("ejecuciones", []) if r.get("hipotesisId") == y["id"]] + ([run] if run["id"] not in {r["id"] for r in e2.get("ejecuciones", [])} else []))
            y["afirmaciones"].append(
                {
                    "texto": run["interpretacion"]["resumen"],
                    "cita": f"[Análisis in silico {run['id']}, plan {plan['hashPlan']}, datos {proc['hash'][:12]}]",
                    "veredicto": "sostenida",
                    "motivo": f"Cifra calculada por código auditado ({run['auditoria']['veredicto']}); {run['interpretacion']['estado'].replace('_', ' ')}.",
                    "entidadDistinta": False,
                    "tipo": "dato",
                    "clase": "derivado",
                    "sintetico": bool(proc.get("sintetico")),
                    "trayectoria": {"id": run["id"], "celda": 0},
                    "fragmento": cifras[:600],
                }
            )
            y["procedencia"]["codigo"] = run["codigo"][:20000]
            y["evidenciaEstadistica"] = "no_aplica" if proc.get("sintetico") else ("fuerte" if run["interpretacion"]["estado"] == "efecto_detectado" else "debil")
            y.pop("_conclusionIntentada", None)
        A.recalcular_bloqueos(e2, y)
        estado_txt = run["estado"] if run["estado"] != "completado" else (run.get("interpretacion") or {}).get("estado", "completado")
        A.con_evento(e2, ctx.investigacion_id, "analisis", f"Análisis in silico de '{h['titulo'][:60]}': {estado_txt}" + (f", auditoría {run['auditoria']['veredicto']}" if run.get("auditoria") else ""), f"#/investigaciones/{ctx.investigacion_id}/hipotesis/{h['id']}", ahora)
        return True

    ctx.mutar(aplicar, "analisis_hipotesis")
    return run


def _valor_reproducido(res_resultados: dict[str, str]) -> float | None:
    """Solo la cifra que el contrato exige. Tomar "la primera que haya"
    convertiria un script que imprimio otra cosa en una reproduccion fallida
    con un numero sin sentido; sin `valor_reproducido` es un error tecnico."""
    for clave in ("valor_reproducido", "valor"):
        if clave in res_resultados:
            try:
                return float(str(res_resultados[clave]).replace(",", "."))
            except ValueError:
                return None
    return None


async def reproducir(ctx, rep: dict[str, Any], pista: Pista) -> None:
    """Una reproducción de la puerta: plan de tipo reproducción, ejecución y
    comparación con la cifra publicada dentro de la tolerancia congelada."""
    e = ctx.e
    ds, ruta = _dataset_de(e, ctx.investigacion_id, rep["datasetId"])
    ahora = P.ahora_ms()
    if not ds or ruta is None or ds["estado"] != "aprobado":
        ctx.mutar(lambda e2: _estado_rep(e2, rep["id"], "error_tecnico", None, None, "El dataset no tiene fichero aprobado en el servidor"), "reproduccion")
        pista.error("El dataset de la reproducción no está aprobado o no tiene fichero")
        return
    proc = ds["procedencia"]
    esquema = await asyncio.to_thread(D.esquema_para_modelo, ruta, proc, bool(proc.get("permiteLlmTerceros")))
    ctx.mutar(lambda e2: _estado_rep(e2, rep["id"], "en_curso", None, None, None), "reproduccion")
    pista.accion(f"Plan de reproducción de {rep['referencia']}: {rep['descripcion'][:100]}")
    pp = await ctx.llamar(
        "cerebro",
        ctx.programas.planificar,
        hipotesis=f"Reproducir el análisis publicado: {rep['referencia']} ({rep['doi'] or 'sin DOI'}). {rep['descripcion']}",
        prediccion_falsable=f"La cifra publicada es {rep['cifraPublicada']} = {rep['valorPublicado']}. El script debe imprimir RESULTADO valor_reproducido=<numero> con la misma definicion.",
        pregunta_pedida=f"Calcular exactamente: {rep['cifraPublicada']}",
        esquema_datos=esquema,
        limites="Reproducción: mismos criterios que la publicación; ninguna variante nueva",
        skills=SK.texto_para_prompt(SK.para_texto("reproducción cifra publicada " + rep["descripcion"] + " " + esquema[:1500] + " " + ds.get("nombre", ""))),
    )
    p = pp.plan
    plan = P.nuevo_plan_analisis(ctx.investigacion_id, None, rep["datasetId"], P.ahora_ms(), tipo="reproduccion", pregunta=p.pregunta.strip(), variables=list(p.variables)[:12], poblacion=p.poblacion.strip(), preprocesado=list(p.preprocesado)[:10], prueba=p.prueba.strip(), hipotesisNula=p.hipotesis_nula.strip(), hipotesisAlternativa=p.hipotesis_alternativa.strip(), alpha=float(p.alpha), direccionEsperada=p.direccion_esperada.strip(), tamanoEfectoMinimo=p.tamano_efecto_minimo.strip(), baseline=p.baseline.strip(), controlNegativo=p.control_negativo.strip(), correccionMultiplicidad=p.correccion_multiplicidad.strip(), umbralEfecto=f"|valor_reproducido - {rep['valorPublicado']}| <= {rep['tolerancia']} * |{rep['valorPublicado']}|", criterioNoEvaluable=p.criterio_no_evaluable.strip(), semilla=12345, hashDatos=proc["hash"], autor=ctx.modelos.cerebro.model, reproduccionId=rep["id"], entorno=getattr(p, "entorno", "tabular") or "tabular")
    ctx.mutar(lambda e2: e2.setdefault("planesAnalisis", []).append(plan) or True, "plan_analisis")
    run = await _correr_plan(ctx, plan, ds, ruta, esquema, None, "reproduccion", pista)
    valor = _valor_reproducido(run.get("resultados", {})) if run["estado"] == "completado" else None
    if run["estado"] != "completado":
        estado = "error_tecnico"
    elif valor is None:
        estado = "error_tecnico"
    else:
        dentro = abs(valor - rep["valorPublicado"]) <= rep["tolerancia"] * max(abs(rep["valorPublicado"]), 1e-12)
        estado = "superada" if dentro else "fallida"
    ctx.mutar(lambda e2: _estado_rep(e2, rep["id"], estado, plan["id"], run["id"], None if estado != "error_tecnico" else (run.get("error") or "El script no imprimio RESULTADO valor_reproducido=<numero>: no se puede comparar con la cifra publicada"), valor), "reproduccion")
    pista.resultado(f"Reproducción {rep['referencia']}: {estado}" + (f" (obtenido {valor:g}, publicado {rep['valorPublicado']:g}, tolerancia {rep['tolerancia']:.0%})" if valor is not None else ""))


def _estado_rep(e: dict[str, Any], rep_id: str, estado: str, plan_id: str | None, run_id: str | None, error: str | None, valor: float | None = None) -> bool:
    r = next((x for x in e.get("reproducciones", []) if x["id"] == rep_id), None)
    if not r:
        return False
    r["estado"] = estado
    if plan_id:
        r["planId"] = plan_id
    if run_id:
        r["ejecucionId"] = run_id
    if valor is not None:
        r["valorObtenido"] = valor
    if error:
        r["_error"] = error[:300]
    inv = next((i for i in e["investigaciones"] if i["id"] == r["investigacionId"]), None)
    if estado in ("superada", "fallida"):
        # El registro de metodos aprende de la puerta: una reproduccion superada
        # marca los metodos de analisis como probados en ese contexto; una
        # fallida los deja en implementado con el fallo anotado.
        for m in e.get("metodos", []):
            if m["tipo"] == "analisis" and "Reproduccion" not in m["nombre"]:
                contexto = f"{r['referencia']}: {r['descripcion'][:60]}"
                if estado == "superada":
                    if contexto not in m["probadoEn"]:
                        m["probadoEn"].append(contexto)
                    if m["estado"] == "implementado":
                        m["estado"] = "probado_en_contexto"
                else:
                    m["fallosConocidos"] = (m["fallosConocidos"] + f" | Reproducción fallida: {contexto}")[:600]
                m["actualizadoEn"] = P.ahora_ms()
    if inv and estado in ("superada", "fallida", "error_tecnico"):
        puerta = inv.setdefault("puertaReproduccion", P.puerta_reproduccion())
        puerta["superadas"] = sum(1 for x in e.get("reproducciones", []) if x["investigacionId"] == inv["id"] and x["estado"] == "superada")
        if puerta["estado"] != "eximida":
            puerta["estado"] = "abierta" if puerta["superadas"] >= puerta["requeridas"] else "bloqueada"
            puerta["fecha"] = P.ahora_ms()
        A.con_evento(e, inv["id"], "analisis", f"Reproducción {r['referencia']}: {estado}. Puerta: {puerta['superadas']} de {puerta['requeridas']} ({puerta['estado']})", f"#/investigaciones/{inv['id']}/investigacion", P.ahora_ms())
    return True
