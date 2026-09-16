"""Propagación de dependencias entre fuentes, afirmaciones, hechos, hipótesis y planes.

Qué resuelve. En el estado de Rosa cada objeto guarda de qué depende, pero
cada uno a su manera y nadie recorre el camino inverso:

- una hipótesis se apoya en fuentes (`procedencia.fuentes[].id`, con su DOI) y
  en afirmaciones verificadas (`afirmaciones[].afirmacionId`, la clave del
  almacén compartido de la corrida);
- un hecho del modelo de mundo se apoya en fuentes (`procedencia[].fuenteId`)
  y, cuando el integrador lo rellena, en afirmaciones (`afirmacionIds`); puede
  además derivar de otro hecho (`derivadoDe`) o sustituir o contradecir a otro
  (`sustituyeA`, `sustituidoPor`, `contradiceA`);
- un plan de análisis, una ejecución y una relación causal pertenecen a una
  hipótesis (`hipotesisId`); una hipótesis puede derivar de otra (`derivadaDe`);
- al revisar una hipótesis, `rosa/estado/acciones.py` (revisar_hipotesis) crea
  el hecho `he-{hipotesisId}`; al bifurcar una investigación, `copiar_hechos`
  lo copia a la rama como `he-{hipotesisId}-{investigacionId}`.

La única propagación que existía era la de retractaciones en
`rosa/bucle/corrida.py` (_recomprobar_retracciones), que solo recalcula la
hipótesis cuya fuente cambió de marca editorial: no toca los hechos, los
planes ni las hipótesis derivadas. Este módulo junta todas las dependencias
en un índice inverso (`indice`), responde quién depende de una fuente (por id
o por DOI), de un hecho o de una hipótesis, y marca lo dependiente como
"pendiente de revisar" con su causa, para que una persona lo atienda y el
bucle vuelva a concluir la hipótesis.

Reglas del módulo:

- Todo es por regla y determinista: cada marca lleva causa, detalle, origen y
  fecha; las listas salen ordenadas y sin repetidos.
- Un registro antiguo sin las claves nuevas (`afirmacionIds`, `derivadoDe`,
  `cuestiones`...) se trata como si estuvieran vacías. Nunca rompe.
- Marcar un hecho como pendiente no toca su `actualizadoEn`: esa marca la usa
  la poda al volver a una iteración (acciones.volver_a_iteracion) y moverla
  haría que la poda borrase hechos que no son nuevos.
- Marcar es idempotente: la misma causa con el mismo origen no se duplica.
  Una causa distinta sobre un objeto ya pendiente pasa a ser la principal y
  la anterior se conserva en `anteriores`, con `desde` en la más antigua.
- El índice es lineal en el tamaño del estado (mapas inversos por afirmación y
  por fuente), no cuadrático en hipótesis por hechos.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator

from rosa import config
from rosa.estado import plantilla as P

Estado = dict[str, Any]

# Las causas por las que algo queda pendiente de revisar. Cerradas: una causa
# fuera de esta lista es un error de programación, no un dato.
CAUSAS = ("fuente_retractada", "hecho_sustituido", "hecho_contradicho", "hipotesis_reformulada", "fuente_corregida")

# Frase por causa para el texto del traspaso (por regla, sin modelo).
FRASES_CAUSA = {
    "fuente_retractada": "depende de una fuente retractada",
    "hecho_sustituido": "depende de un hecho sustituido",
    "hecho_contradicho": "depende de un hecho contradicho",
    "hipotesis_reformulada": "deriva de una hipótesis reformulada",
    "fuente_corregida": "depende de una fuente corregida",
}

# Los tres tipos de objeto que pueden quedar pendientes: nombre en castellano y
# lista del estado donde viven.
NOMBRE_TIPO = {"hipotesis": "la hipótesis", "hecho": "el hecho", "plan": "el plan de análisis"}
LISTA_TIPO = {"hipotesis": "hipotesis", "hecho": "hechos", "plan": "planesAnalisis"}

# Claves de `objetivos` que acepta `marcar_pendientes` para cada tipo (las que
# devuelven `dependientes_de_*` y su singular, por tolerancia).
CLAVES_OBJETIVO = {"hipotesis": ("hipotesis",), "hecho": ("hechos", "hecho"), "plan": ("planes", "plan")}

# Cómo se escribe el tipo al atender (con mayúsculas o en plural también vale).
_TIPO_CANONICO = {"hipotesis": "hipotesis", "hipótesis": "hipotesis", "hecho": "hecho", "hechos": "hecho", "plan": "plan", "planes": "plan", "planesanalisis": "plan"}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def normalizar_doi(doi: Any) -> str:
    """El DOI en minúsculas, sin espacios y sin el prefijo de URL ni `doi:`,
    para que `10.1000/ABC` y `https://doi.org/10.1000/abc` sean el mismo."""
    s = str(doi or "").strip().lower()
    cambio = True
    while cambio:
        cambio = False
        for prefijo in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi.org/", "doi:"):
            if s.startswith(prefijo):
                s = s[len(prefijo) :].strip()
                cambio = True
    return s


def _lista(valor: Any) -> list[Any]:
    """Una clave que puede venir como texto, lista o ausente, siempre como lista."""
    if valor is None or valor == "":
        return []
    if isinstance(valor, (list, tuple, set)):
        return [v for v in valor if v is not None and v != ""]
    return [valor]


def _de(e: Estado, investigacion_id: str | None, clave: str) -> Iterator[dict[str, Any]]:
    """Los objetos de una lista del estado que pertenecen a la investigación.
    Con `investigacion_id` None van todos. Un objeto sin `investigacionId` (o
    con None, un registro antiguo) se trata como si perteneciera."""
    for x in e.get(clave) or []:
        if not isinstance(x, dict):
            continue
        propia = x.get("investigacionId")
        if investigacion_id is None or propia is None or propia == investigacion_id:
            yield x


def _buscar(lista: Iterable[Any], id_: Any) -> dict[str, Any] | None:
    """El objeto con ese id, comparado como texto (`str(id_)`), igual que lo
    indexa `indice`: un id numérico en un registro raro se encuentra igual."""
    objetivo = str(id_)
    for x in lista or []:
        if isinstance(x, dict) and x.get("id") is not None and str(x.get("id")) == objetivo:
            return x
    return None


def _fuentes_de(h: dict[str, Any]) -> list[dict[str, Any]]:
    proc = h.get("procedencia")
    if not isinstance(proc, dict):
        return []
    return [f for f in (proc.get("fuentes") or []) if isinstance(f, dict)]


def _afirmaciones_de(h: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in (h.get("afirmaciones") or []) if isinstance(a, dict)]


def _ids(objetivos: dict[str, Any] | None, claves: tuple[str, ...]) -> list[str]:
    """Los ids de `objetivos` bajo cualquiera de las claves, ordenados y sin repetidos."""
    vistos: set[str] = set()
    for clave in claves:
        for v in _lista((objetivos or {}).get(clave)):
            vistos.add(str(v))
    return sorted(vistos)


def _entero(valor: Any, defecto: int = 0) -> int:
    """Un tiempo guardado como número o como texto numérico; si está corrupto,
    el valor por defecto. Un dato raro en un registro no tumba el listado."""
    try:
        return int(valor)
    except (TypeError, ValueError, OverflowError):
        return defecto


def _ahora(ahora: Any) -> int:
    """El instante de la operación en milisegundos; sin él, el reloj del servidor."""
    return int(ahora) if ahora is not None else P.ahora_ms()


def _iso(ahora: int) -> str:
    return datetime.fromtimestamp(int(ahora) / 1000, tz=timezone.utc).isoformat()


def _fecha_corta(t: Any) -> str:
    """Día y mes (16/09), en la hora local del servidor como el resto de Rosa."""
    try:
        return datetime.fromtimestamp(int(t) / 1000).strftime("%d/%m")
    except (TypeError, ValueError, OverflowError, OSError):
        return "fecha desconocida"


def _ids_investigaciones(e: Estado) -> list[str]:
    """Los ids de las investigaciones del estado, los más largos primero (para
    quitar sufijos heredados sin confundir `inv-a` con `inv-ab`)."""
    ids = {str(i["id"]) for i in (e.get("investigaciones") or []) if isinstance(i, dict) and i.get("id")}
    return sorted(ids, key=lambda s: (-len(s), s))


def _hipotesis_de_revision(xid: str, x: dict[str, Any], ids_inv: list[str]) -> list[str]:
    """Los ids de hipótesis que podría nombrar un hecho de revisión: `he-{id}`
    (acciones.revisar_hipotesis) o su copia heredada en una rama,
    `he-{id}-{investigacionId}` una o varias veces (acciones.copiar_hechos).
    Candidatos del más completo al más recortado; el índice se queda con el
    primero que exista."""
    if not xid.startswith("he-"):
        return []
    actual = xid[3:]
    candidatos = [actual]
    sufijos = list(ids_inv)
    propia = x.get("investigacionId")
    if propia and str(propia) not in sufijos:
        sufijos.insert(0, str(propia))
    cambio = True
    while cambio:
        cambio = False
        for iid in sufijos:
            if actual.endswith("-" + iid) and len(actual) > len(iid) + 1:
                actual = actual[: -len(iid) - 1]
                candidatos.append(actual)
                cambio = True
                break
    return candidatos


# ---------------------------------------------------------------------------
# 1. Índice inverso
# ---------------------------------------------------------------------------


def indice(e: Estado, investigacion_id: str | None = None) -> dict[str, Any]:
    """Los mapas inversos de una investigación (o de todo el estado si
    `investigacion_id` es None):

    - `porFuente`: {fuenteId: {"hipotesis": set, "hechos": set}}. Una hipótesis
      depende de una fuente si la lista en `procedencia.fuentes` o si alguna de
      sus afirmaciones trae `fuenteId`; un hecho, si la lista en `procedencia`.
    - `porDoi`: {doi normalizado: set[fuenteId]}, con las fuentes de las
      hipótesis y las privadas de la corrida (`_fuentes`), que tienen el DOI
      que la procedencia de un hecho no guarda.
    - `porHecho`: {hechoId: {"hipotesis": set}}: las hipótesis cuyas
      afirmaciones comparten `afirmacionId` con `afirmacionIds` del hecho, o
      cuyas fuentes comparten `fuenteId` con la procedencia del hecho, más la
      hipótesis de la que nació el hecho `he-{hipotesisId}` (o su copia
      heredada `he-{hipotesisId}-{investigacionId}`).
    - `porHipotesis`: {hipotesisId: {"derivadas", "planes", "ejecuciones",
      "hechos" (el `he-{id}` y sus copias heredadas, si existen), "relaciones"}}.

    Un registro sin alguna clave se trata como si estuviera vacía. Dos
    hipótesis con el mismo id (un registro roto) suman sus dependencias en vez
    de pisarse. Coste lineal en el tamaño del estado.
    """
    por_fuente: dict[str, dict[str, set[str]]] = {}
    por_doi: dict[str, set[str]] = {}
    por_hecho: dict[str, dict[str, set[str]]] = {}
    por_hipotesis: dict[str, dict[str, set[str]]] = {}
    hip_por_afirmacion: dict[str, set[str]] = {}

    def entrada_fuente(fid: str) -> dict[str, set[str]]:
        return por_fuente.setdefault(fid, {"hipotesis": set(), "hechos": set()})

    def entrada_hipotesis(hid: str) -> dict[str, set[str]]:
        return por_hipotesis.setdefault(hid, {"derivadas": set(), "planes": set(), "ejecuciones": set(), "hechos": set(), "relaciones": set()})

    hipotesis = [h for h in _de(e, investigacion_id, "hipotesis") if h.get("id")]
    for h in hipotesis:
        hid = str(h["id"])
        entrada_hipotesis(hid)
        for f in _fuentes_de(h):
            fid = f.get("id")
            if not fid:
                continue
            fid = str(fid)
            entrada_fuente(fid)["hipotesis"].add(hid)
            doi = normalizar_doi(f.get("doi"))
            if doi:
                por_doi.setdefault(doi, set()).add(fid)
        for a in _afirmaciones_de(h):
            if a.get("afirmacionId"):
                hip_por_afirmacion.setdefault(str(a["afirmacionId"]), set()).add(hid)
            if a.get("fuenteId"):
                entrada_fuente(str(a["fuenteId"]))["hipotesis"].add(hid)
    for h in hipotesis:
        padre = h.get("derivadaDe")
        if padre:
            entrada_hipotesis(str(padre))["derivadas"].add(str(h["id"]))

    # Las fuentes privadas de la corrida traen el DOI que la procedencia de un hecho no guarda.
    for c in _de(e, investigacion_id, "corridas"):
        privadas = c.get("_fuentes")
        pares: Iterable[tuple[Any, Any]]
        if isinstance(privadas, dict):
            pares = privadas.items()
        elif isinstance(privadas, list):
            pares = ((f.get("id"), f) for f in privadas if isinstance(f, dict))
        else:
            pares = ()
        for fid, f in pares:
            if not isinstance(f, dict):
                continue
            fid = fid or f.get("id")
            doi = normalizar_doi(f.get("doi"))
            if fid and doi:
                por_doi.setdefault(doi, set()).add(str(fid))

    ids_inv = _ids_investigaciones(e)
    for x in _de(e, investigacion_id, "hechos"):
        xid = x.get("id")
        if not xid:
            continue
        xid = str(xid)
        dependientes: set[str] = set()
        for p in x.get("procedencia") or []:
            if isinstance(p, dict) and p.get("fuenteId"):
                entrada = entrada_fuente(str(p["fuenteId"]))
                entrada["hechos"].add(xid)
                dependientes |= entrada["hipotesis"]
        for af in _lista(x.get("afirmacionIds")):
            dependientes |= hip_por_afirmacion.get(str(af), set())
        for hid in _hipotesis_de_revision(xid, x, ids_inv):
            if hid in por_hipotesis:
                # El hecho que nace al revisar la hipótesis (o su copia en una rama): se deben el uno al otro.
                dependientes.add(hid)
                por_hipotesis[hid]["hechos"].add(xid)
                break
        por_hecho[xid] = {"hipotesis": dependientes}

    for p in _de(e, investigacion_id, "planesAnalisis"):
        if p.get("hipotesisId") and p.get("id"):
            entrada_hipotesis(str(p["hipotesisId"]))["planes"].add(str(p["id"]))
    for r in _de(e, investigacion_id, "ejecuciones"):
        if r.get("hipotesisId") and r.get("id"):
            entrada_hipotesis(str(r["hipotesisId"]))["ejecuciones"].add(str(r["id"]))
    for r in _de(e, investigacion_id, "relaciones"):
        if r.get("hipotesisId") and r.get("id"):
            entrada_hipotesis(str(r["hipotesisId"]))["relaciones"].add(str(r["id"]))

    return {"porFuente": por_fuente, "porDoi": por_doi, "porHecho": por_hecho, "porHipotesis": por_hipotesis}


# ---------------------------------------------------------------------------
# 2. Dependientes
# ---------------------------------------------------------------------------


def _fuentes_equivalentes(idx: dict[str, Any], fuente_id: Any, doi: Any) -> set[str]:
    """Los ids de fuente que nombran la misma publicación: el id dado y todos
    los que el índice conoce con ese DOI."""
    fids: set[str] = set()
    if fuente_id:
        fids.add(str(fuente_id))
    doi_n = normalizar_doi(doi)
    if doi_n:
        fids |= idx["porDoi"].get(doi_n, set())
    return fids


def _dependientes_de_fuente(idx: dict[str, Any], fids: set[str]) -> dict[str, list[str]]:
    hip: set[str] = set()
    hechos: set[str] = set()
    for fid in fids:
        entrada = idx["porFuente"].get(fid)
        if entrada:
            hip |= entrada["hipotesis"]
            hechos |= entrada["hechos"]
    planes: set[str] = set()
    for hid in hip:
        planes |= idx["porHipotesis"].get(hid, {}).get("planes", set())
    return {"hipotesis": sorted(hip), "hechos": sorted(hechos), "planes": sorted(planes)}


def dependientes_de_fuente(e: Estado, investigacion_id: str | None, fuente_id: str | None = None, doi: str | None = None) -> dict[str, list[str]]:
    """Quién depende de una fuente, por su id o por su DOI (o por los dos): las
    hipótesis que la citan, los hechos cuya procedencia la lleva y los planes
    de análisis de esas hipótesis. Listas ordenadas y sin repetidos."""
    idx = indice(e, investigacion_id)
    return _dependientes_de_fuente(idx, _fuentes_equivalentes(idx, fuente_id, doi))


def _dependientes_de_hecho(e: Estado, idx: dict[str, Any], investigacion_id: str | None, hecho_id: str) -> dict[str, list[str]]:
    hecho_id = str(hecho_id)
    hip = set(idx["porHecho"].get(hecho_id, {}).get("hipotesis", set()))
    hechos = {str(x["id"]) for x in _de(e, investigacion_id, "hechos") if x.get("id") and str(x["id"]) != hecho_id and hecho_id in {str(v) for v in _lista(x.get("derivadoDe"))}}
    cuestiones = {str(q["id"]) for q in _de(e, investigacion_id, "cuestiones") if q.get("id") and hecho_id in {str(v) for v in _lista(q.get("hechoIds"))}}
    return {"hipotesis": sorted(hip), "hechos": sorted(hechos), "cuestiones": sorted(cuestiones)}


def dependientes_de_hecho(e: Estado, investigacion_id: str | None, hecho_id: str) -> dict[str, list[str]]:
    """Quién depende de un hecho: las hipótesis que comparten con él
    afirmaciones o fuentes, los hechos que lo llevan en `derivadoDe` (los que
    lo citan en `sustituyeA` o `contradiceA` dependen del nuevo, no de este) y
    las cuestiones cuyo `hechoIds` lo contiene."""
    return _dependientes_de_hecho(e, indice(e, investigacion_id), investigacion_id, str(hecho_id))


def dependientes_de_hipotesis(e: Estado, hipotesis_id: str) -> dict[str, list[str]]:
    """Quién depende de una hipótesis: las derivadas de ella, sus planes de
    análisis, sus ejecuciones, el hecho `he-{id}` que nació al revisarla (y sus
    copias heredadas en ramas), sus relaciones causales y las cuestiones cuyo
    `hipotesisIds` la contiene. Los ids de hipótesis son únicos en todo el
    estado, así que se mira el estado entero."""
    hipotesis_id = str(hipotesis_id)
    entrada = indice(e, None)["porHipotesis"].get(hipotesis_id, {})
    cuestiones = {str(q["id"]) for q in _de(e, None, "cuestiones") if q.get("id") and hipotesis_id in {str(v) for v in _lista(q.get("hipotesisIds"))}}
    return {
        "hipotesis": sorted(entrada.get("derivadas", set())),
        "planes": sorted(entrada.get("planes", set())),
        "ejecuciones": sorted(entrada.get("ejecuciones", set())),
        "hechos": sorted(entrada.get("hechos", set())),
        "relaciones": sorted(entrada.get("relaciones", set())),
        "cuestiones": sorted(cuestiones),
    }


# ---------------------------------------------------------------------------
# 3. Marcar pendientes
# ---------------------------------------------------------------------------


def _misma_marca(marca: Any, causa: str, origenes: set[str]) -> bool:
    """Si la marca (o alguna de sus anteriores) ya tiene esta causa con alguno
    de estos orígenes (el mismo cambio puede llegar nombrado por DOI o por id)."""
    if not isinstance(marca, dict):
        return False
    if marca.get("causa") == causa and str(marca.get("origenId") or "") in origenes:
        return True
    return any(isinstance(a, dict) and a.get("causa") == causa and str(a.get("origenId") or "") in origenes for a in marca.get("anteriores") or [])


def _poner_marca(objeto: dict[str, Any], causa: str, detalle: str, origen_id: str | None, ahora: int, extra: dict[str, Any] | None) -> dict[str, Any]:
    """Escribe `pendienteRevision`. Si ya había otra causa, la conserva en
    `anteriores` y deja `desde` en la más antigua: lo pendiente lo es desde la
    primera vez, no desde la última."""
    # `origenId` es texto siempre (PendienteRevision en tipos.ts): sin origen, cadena vacía.
    marca: dict[str, Any] = {"causa": causa, "detalle": detalle, "origenId": str(origen_id or ""), "desde": int(ahora)}
    for k, v in (extra or {}).items():
        # Copia por marca: una lista compartida entre dos marcas se mutaría a la vez.
        marca.setdefault(k, copy.deepcopy(v))
    previa = objeto.get("pendienteRevision")
    if isinstance(previa, dict) and previa.get("causa"):
        anteriores = [a for a in (previa.get("anteriores") or []) if isinstance(a, dict)]
        anteriores.append({k: v for k, v in previa.items() if k != "anteriores"})
        marca["anteriores"] = anteriores
        marca["desde"] = min([_entero(a.get("desde"), int(ahora)) or int(ahora) for a in anteriores] + [int(ahora)])
    objeto["pendienteRevision"] = marca
    return marca


def marcar_pendientes(e: Estado, objetivos: dict[str, list[str]] | None, causa: str, detalle: str, origen_id: str | None, ahora: int, extra: dict[str, Any] | None = None, origenes_equivalentes: Iterable[Any] | None = None) -> list[str]:
    """Marca como "pendiente de revisar" las hipótesis, hechos y planes de
    `objetivos` (las claves que devuelven `dependientes_de_*`).

    - Hipótesis: `pendienteRevision` y además `_evidenciaNueva = True` y se
      quita `_conclusionIntentada`, para que el bucle vuelva a concluirla.
    - Hecho: `pendienteRevision` y un movimiento en `historial` (mismo estado
      de salida y de llegada) SIN tocar `actualizadoEn`.
    - Plan de análisis: solo `pendienteRevision`.

    Idempotente: la misma causa con el mismo `origen_id` (o con cualquiera de
    `origenes_equivalentes`, otros nombres del mismo cambio) no se repite.
    `extra` son claves adicionales para la marca (por ejemplo `nuevoId` en una
    sustitución). Devuelve `["hipotesis:<id>", "hecho:<id>", "plan:<id>"]` de
    lo marcado nuevo, en ese orden de tipo y por id.
    """
    if causa not in CAUSAS:
        raise ValueError(f"causa desconocida: {causa!r}; las válidas son {', '.join(CAUSAS)}")
    ahora = _ahora(ahora)
    detalle = str(detalle or "").strip() or FRASES_CAUSA[causa]
    origenes = {str(origen_id or "")} | {str(o) for o in (origenes_equivalentes or []) if o is not None and o != ""}
    marcados: list[str] = []
    for hid in _ids(objetivos, CLAVES_OBJETIVO["hipotesis"]):
        h = _buscar(e.get("hipotesis"), hid)
        if not h or _misma_marca(h.get("pendienteRevision"), causa, origenes):
            continue
        _poner_marca(h, causa, detalle, origen_id, ahora, extra)
        h["_evidenciaNueva"] = True
        h.pop("_conclusionIntentada", None)
        marcados.append(f"hipotesis:{hid}")
    for xid in _ids(objetivos, CLAVES_OBJETIVO["hecho"]):
        x = _buscar(e.get("hechos"), xid)
        if not x or _misma_marca(x.get("pendienteRevision"), causa, origenes):
            continue
        _poner_marca(x, causa, detalle, origen_id, ahora, extra)
        estado = x.get("estado")
        historial = x.get("historial")
        if not isinstance(historial, list):
            historial = x["historial"] = []
        historial.append({"fecha": int(ahora), "de": estado, "a": estado, "quien": config.QUIEN_ROSA, "motivo": f"Pendiente de revisar: {detalle}"})
        marcados.append(f"hecho:{xid}")
    for pid in _ids(objetivos, CLAVES_OBJETIVO["plan"]):
        p = _buscar(e.get("planesAnalisis"), pid)
        if not p or _misma_marca(p.get("pendienteRevision"), causa, origenes):
            continue
        _poner_marca(p, causa, detalle, origen_id, ahora, extra)
        marcados.append(f"plan:{pid}")
    return marcados


# ---------------------------------------------------------------------------
# 4. Atender
# ---------------------------------------------------------------------------


def atender_pendiente(e: Estado, tipo: str, id_: str, quien: str, nota: str, ahora: int) -> bool:
    """Una persona (o Rosa) da por atendida la marca: `pendienteRevision` queda
    en None (con sus anteriores), que es como la deja la plantilla. En una
    hipótesis queda una línea en `procedencia.registro`; en un hecho, un
    movimiento en `historial` (sin tocar `actualizadoEn`); en un plan, nada
    más. El tipo se acepta en singular o plural y con mayúsculas. False si no
    había marca o el objeto no existe."""
    tipo = _TIPO_CANONICO.get(str(tipo or "").strip().lower(), "")
    lista = LISTA_TIPO.get(tipo)
    if not lista:
        return False
    objeto = _buscar(e.get(lista), str(id_))
    if not objeto or not objeto.get("pendienteRevision"):
        return False
    ahora = _ahora(ahora)
    quien = str(quien or "").strip() or "una persona"
    nota = str(nota or "").strip() or "sin nota"
    objeto["pendienteRevision"] = None
    if tipo == "hipotesis":
        proc = objeto.get("procedencia")
        if not isinstance(proc, dict):
            proc = objeto["procedencia"] = P.procedencia_vacia("Procedencia reconstruida al atender una pendiente de revisar.", ahora)
        registro = proc.get("registro")
        if not isinstance(registro, list):
            registro = proc["registro"] = []
        registro.append(f"{_iso(ahora)} pendiente de revisar atendida por {quien}: {nota}")
    elif tipo == "hecho":
        estado = objeto.get("estado")
        historial = objeto.get("historial")
        if not isinstance(historial, list):
            historial = objeto["historial"] = []
        historial.append({"fecha": int(ahora), "de": estado, "a": estado, "quien": quien, "motivo": f"Pendiente de revisar atendida: {nota}"})
    return True


# ---------------------------------------------------------------------------
# 5. Listar y contar para el traspaso
# ---------------------------------------------------------------------------


def _titulo(tipo: str, objeto: dict[str, Any]) -> str:
    if tipo == "hipotesis":
        return str(objeto.get("titulo") or objeto.get("enunciado") or objeto.get("id") or "")
    if tipo == "hecho":
        return str(objeto.get("enunciado") or objeto.get("tema") or objeto.get("id") or "")
    return str(objeto.get("pregunta") or objeto.get("prueba") or objeto.get("id") or "")


def pendientes(e: Estado, investigacion_id: str | None = None) -> list[dict[str, Any]]:
    """Todo lo pendiente de revisar en la investigación: `{"tipo", "id",
    "titulo", "pendienteRevision"}`, ordenado por `desde` (y por tipo e id
    para que el orden sea siempre el mismo)."""
    salida: list[dict[str, Any]] = []
    for tipo, lista in LISTA_TIPO.items():
        for objeto in _de(e, investigacion_id, lista):
            marca = objeto.get("pendienteRevision")
            if isinstance(marca, dict) and marca.get("causa") and objeto.get("id"):
                salida.append({"tipo": tipo, "id": str(objeto["id"]), "titulo": _titulo(tipo, objeto), "pendienteRevision": marca})
    orden_tipo = {"hipotesis": 0, "hecho": 1, "plan": 2}
    salida.sort(key=lambda p: (_entero(p["pendienteRevision"].get("desde")), orden_tipo[p["tipo"]], p["id"]))
    return salida


def texto_pendiente(p: dict[str, Any]) -> str:
    """Una pendiente en una frase: "Pendiente de revisar: la hipótesis «X»
    depende de una fuente retractada (desde el 16/09): detalle"."""
    marca = p.get("pendienteRevision") or {}
    causa = str(marca.get("causa") or "")
    frase = FRASES_CAUSA.get(causa) or f"está pendiente por {causa.replace('_', ' ') or 'una causa sin registrar'}"
    nombre = NOMBRE_TIPO.get(str(p.get("tipo")), "el objeto")
    titulo = str(p.get("titulo") or p.get("id") or "").strip()[:90]
    texto = f"Pendiente de revisar: {nombre} «{titulo}» {frase} (desde el {_fecha_corta(marca.get('desde'))})"
    detalle = str(marca.get("detalle") or "").strip()
    if detalle and detalle != FRASES_CAUSA.get(causa):
        texto += f": {detalle[:160]}"
    # Las causas anteriores distintas de la principal (la misma causa repetida no añade nada).
    otras = sorted({FRASES_CAUSA.get(str(a.get("causa")), str(a.get("causa")).replace("_", " ")) for a in (marca.get("anteriores") or []) if isinstance(a, dict) and a.get("causa")} - {frase})
    if otras:
        texto += "; también " + ", ".join(otras)
    return texto


def texto_pendientes(e: Estado, investigacion_id: str | None = None, maximo: int = 8) -> str:
    """Las pendientes de la investigación (con `investigacion_id` None, de todo
    el estado) en castellano para el traspaso, una por línea y las más antiguas
    primero; si hay más de `maximo`, dice cuántas quedan. Sin pendientes: "Sin
    pendientes de revisar."."""
    todas = pendientes(e, investigacion_id)
    if not todas:
        return "Sin pendientes de revisar."
    maximo = max(1, _entero(maximo, 1) or 1)
    lineas = [texto_pendiente(p) for p in todas[:maximo]]
    if len(todas) > maximo:
        resto = len(todas) - maximo
        lineas.append(f"Y {resto} pendiente{'s' if resto != 1 else ''} de revisar más.")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# 6. Azúcar: propagar
# ---------------------------------------------------------------------------


def _investigaciones_de_marcados(e: Estado, marcados: list[str]) -> dict[str, list[str]]:
    """Los marcados agrupados por la investigación del objeto marcado (para el
    evento cuando la propagación cruzó investigaciones)."""
    grupos: dict[str, list[str]] = {}
    for m in marcados:
        tipo, _, id_ = m.partition(":")
        objeto = _buscar(e.get(LISTA_TIPO.get(tipo, "")), id_)
        inv = str((objeto or {}).get("investigacionId") or "")
        if inv:
            grupos.setdefault(inv, []).append(m)
    return dict(sorted(grupos.items()))


def _eventos(e: Estado, investigacion_id: str | None, marcados: list[str], cabecera: str, cola: str, ahora: int) -> None:
    """Un evento tipo `dependencias` por investigación tocada: el de la
    investigación dada, o uno por cada una a la que pertenezca algo marcado si
    la propagación se lanzó sobre todo el estado. Solo si se marcó algo."""
    if not marcados or not isinstance(e.get("eventos"), list):
        return
    grupos = {str(investigacion_id): marcados} if investigacion_id else _investigaciones_de_marcados(e, marcados)
    for inv, propios in grupos.items():
        e["eventos"].append(P.nuevo_evento(inv, "dependencias", f"{cabecera}: {_resumen_marcados(propios)} ({cola})", f"#/investigaciones/{inv}/mundo", int(ahora)))


def _referencia_fuente(e: Estado, investigacion_id: str | None, fids: set[str], doi: str | None) -> str:
    """Cómo nombrar la fuente en el detalle: su referencia si alguna hipótesis
    la lista (por cualquiera de sus ids o por su DOI); si no, el DOI o el id."""
    doi_n = normalizar_doi(doi)
    for h in _de(e, investigacion_id, "hipotesis"):
        for f in _fuentes_de(h):
            if (f.get("id") is not None and str(f.get("id")) in fids) or (doi_n and normalizar_doi(f.get("doi")) == doi_n):
                if f.get("referencia"):
                    return str(f["referencia"])[:120]
    return str(doi_n or (sorted(fids)[0] if fids else "") or "sin identificar")


def _resumen_marcados(marcados: list[str]) -> str:
    """«1 hipótesis, 2 hechos, 1 plan de análisis quedan pendientes de revisar»,
    con el verbo concordado con el total."""
    n = {"hipotesis": 0, "hecho": 0, "plan": 0}
    for m in marcados:
        n[m.split(":", 1)[0]] = n.get(m.split(":", 1)[0], 0) + 1
    partes = []
    if n["hipotesis"]:
        partes.append(f"{n['hipotesis']} hipótesis")
    if n["hecho"]:
        partes.append(f"{n['hecho']} hecho{'s' if n['hecho'] != 1 else ''}")
    if n["plan"]:
        partes.append(f"{n['plan']} plan{'es' if n['plan'] != 1 else ''} de análisis")
    total = sum(n.values())
    return ", ".join(partes) + (" queda pendiente de revisar" if total == 1 else " quedan pendientes de revisar")


def _doi_de_fuente(idx: dict[str, Any], fuente_id: str | None) -> str:
    """El DOI que el índice conoce para una fuente (cadena vacía si ninguno)."""
    if not fuente_id:
        return ""
    for doi, fids in sorted(idx["porDoi"].items()):
        if str(fuente_id) in fids:
            return doi
    return ""


def propagar_retraccion(e: Estado, investigacion_id: str | None, fuente_id: str | None, doi: str | None, ahora: int, causa: str = "fuente_retractada") -> list[str]:
    """Una fuente quedó retractada (o corregida, con `causa='fuente_corregida'`):
    marca pendientes las hipótesis que la citan, los hechos cuya procedencia la
    lleva y los planes de esas hipótesis. Deja un evento si marcó algo.

    El origen de la marca es canónico: el DOI normalizado si se conoce (dado, o
    resuelto desde el id de la fuente), y el id solo cuando no hay DOI. Además,
    el id dado y todos los ids que comparten ese DOI cuentan como el mismo
    origen: la misma retractación notificada por DOI, por id o por los dos, o
    primero por id y después por DOI, no se marca dos veces."""
    ahora = _ahora(ahora)
    doi_n = normalizar_doi(doi)
    if not fuente_id and not doi_n:
        return []
    idx = indice(e, investigacion_id)
    if not doi_n:
        doi_n = _doi_de_fuente(idx, fuente_id)
    fids = _fuentes_equivalentes(idx, fuente_id, doi_n)
    objetivos = _dependientes_de_fuente(idx, fids)
    referencia = _referencia_fuente(e, investigacion_id, fids, doi_n or None)
    verbo = "corregida" if causa == "fuente_corregida" else "retractada"
    detalle = f"La fuente «{referencia}» fue {verbo}" + (f" (DOI {doi_n})" if doi_n and doi_n not in referencia.lower() else "")
    origen = doi_n or str(fuente_id)
    marcados = marcar_pendientes(e, objetivos, causa, detalle, origen, ahora, extra={"doi": doi_n or None}, origenes_equivalentes=fids | {origen})
    _eventos(e, investigacion_id, marcados, f"Fuente {verbo}", referencia[:80], ahora)
    return marcados


def _propagar_hecho(e: Estado, investigacion_id: str | None, hecho_viejo_id: str, hecho_nuevo_id: str | None, ahora: int, causa: str) -> list[str]:
    ahora = _ahora(ahora)
    viejo = _buscar(e.get("hechos"), str(hecho_viejo_id))
    nuevo = _buscar(e.get("hechos"), str(hecho_nuevo_id)) if hecho_nuevo_id else None
    if not viejo:
        return []
    idx = indice(e, investigacion_id)
    deps = _dependientes_de_hecho(e, idx, investigacion_id, str(hecho_viejo_id))
    planes: set[str] = set()
    for hid in deps["hipotesis"]:
        planes |= idx["porHipotesis"].get(hid, {}).get("planes", set())
    # El hecho nuevo es la causa, no un dependiente: no se marca a sí mismo.
    hechos = [x for x in deps["hechos"] if x != str(hecho_nuevo_id or "")]
    objetivos = {"hipotesis": deps["hipotesis"], "hechos": hechos, "planes": sorted(planes)}
    enunciado_viejo = str(viejo.get("enunciado") or viejo.get("id"))[:80]
    por_quien = f" por «{str(nuevo.get('enunciado') or nuevo.get('id'))[:80]}»" if nuevo else (f" por {hecho_nuevo_id}" if hecho_nuevo_id else "")
    if causa == "hecho_sustituido":
        detalle = f"El hecho «{enunciado_viejo}» fue sustituido{por_quien}"
        cabecera = "Hecho sustituido"
    else:
        detalle = f"El hecho «{enunciado_viejo}» quedó contradicho{por_quien}"
        cabecera = "Hecho contradicho"
    marcados = marcar_pendientes(e, objetivos, causa, detalle, str(hecho_viejo_id), ahora, extra={"nuevoId": str(hecho_nuevo_id) if hecho_nuevo_id else None})
    _eventos(e, investigacion_id or viejo.get("investigacionId"), marcados, cabecera, enunciado_viejo, ahora)
    return marcados


def propagar_sustitucion(e: Estado, investigacion_id: str | None, hecho_viejo_id: str, hecho_nuevo_id: str | None, ahora: int) -> list[str]:
    """Un hecho fue sustituido por otro: marca pendientes las hipótesis que se
    apoyaban en el viejo, los hechos derivados de él y los planes de esas
    hipótesis. El nuevo no se marca. Deja un evento si marcó algo."""
    return _propagar_hecho(e, investigacion_id, hecho_viejo_id, hecho_nuevo_id, ahora, "hecho_sustituido")


def propagar_contradiccion(e: Estado, investigacion_id: str | None, hecho_viejo_id: str, hecho_nuevo_id: str | None, ahora: int) -> list[str]:
    """Un hecho nuevo contradice a otro: igual que la sustitución, con causa
    `hecho_contradicho`. Quien contradice no se marca."""
    return _propagar_hecho(e, investigacion_id, hecho_viejo_id, hecho_nuevo_id, ahora, "hecho_contradicho")


def propagar_reformulacion(e: Estado, hipotesis_id: str, ahora: int, motivo: str = "") -> list[str]:
    """Una hipótesis se reformuló (versión nueva): sus derivadas, sus planes y
    el hecho `he-{id}` (con sus copias heredadas) quedan pendientes con causa
    `hipotesis_reformulada`. Las ejecuciones y relaciones no se marcan (no
    tienen pendienteRevision), pero se devuelven en `dependientes_de_hipotesis`.
    Llamarla después de subir `version`: el origen es `<id>@v<version>`, así la
    misma versión no se propaga dos veces y una versión nueva sí."""
    ahora = _ahora(ahora)
    h = _buscar(e.get("hipotesis"), str(hipotesis_id))
    if not h:
        return []
    version = _entero(h.get("version"), 1) or 1
    deps = dependientes_de_hipotesis(e, str(hipotesis_id))
    titulo = str(h.get("titulo") or h["id"])[:80]
    detalle = f"La hipótesis «{titulo}» se reformuló (versión {version})" + (f": {str(motivo).strip()[:120]}" if str(motivo or '').strip() else "")
    marcados = marcar_pendientes(e, {"hipotesis": deps["hipotesis"], "hechos": deps["hechos"], "planes": deps["planes"]}, "hipotesis_reformulada", detalle, f"{h['id']}@v{version}", ahora)
    _eventos(e, h.get("investigacionId"), marcados, "Hipótesis reformulada", titulo, ahora)
    return marcados
