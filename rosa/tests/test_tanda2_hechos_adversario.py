"""Adversario del hallazgo M-08, parte de estado (rosa/hechos.py, copiar_hechos
y la migración del almacén), 18 de septiembre de 2026. Cada test describe lo
que la regla de "mismo hecho" y la de "afirmación que sostiene un hecho"
deberían hacer y hoy no hacen; fallan a propósito sobre el árbol actual y
pasan cuando se cierre el hueco. Sin red ni gateway: todo son diccionarios en
memoria.

Lo que se ataca, con lo medido sobre una copia del estado real (611 hechos,
2825 afirmaciones, versión 20379):

- `mismo_hecho` trata todos los tokens largos por igual. Dos hechos que solo
  se distinguen en el nombre del marcador (GFAP frente a sTREM2 sin referencia
  común, solape 0,82; GFAP frente a YKL40 o PSEN1 frente a APOE4 con la misma
  fuente y página, solape 0,67), en una negación larga ("nunca", "never",
  solape 0,89) o en una cifra escrita con letra ("cuatro" frente a "seis",
  0,78) pasan y se funden: el repetido desaparece del modelo de mundo y el
  superviviente hereda la procedencia y las afirmaciones de otra cosa. La
  regla del bucle para el mismo hallazgo (`pasos.hecho_duplicado`) exige
  referencia compartida y mismos números en letra y deja esos pares aparte;
  la migración los funde al siguiente reinicio. Las 8 fusiones reales
  comparten referencia normalizada y números, así que endurecer la regla no
  pierde ninguna.
- `cobertura` solo mira qué parte del hecho aparece en la afirmación, no lo
  que la afirmación añade: una afirmación de la misma fuente y página que
  dice lo contrario ("no sube", "nunca redujo") o que habla de otro marcador
  (NfL, p-tau217) cubre el 89 % o el 100 % de los tokens del hecho y queda
  enlazada como cita "apoya". En los 146 enlaces reales no hay ninguno falso;
  el hueco es de la regla, no de los datos de hoy.
- Un hecho con `afirmacionIds`, `citas`, `procedencia` o `historial` en null
  (en vez de lista vacía) tumba `fundir` y `enlazar`: `setdefault` devuelve el
  None y se itera. Con crear con herencia o bifurcar el servidor responde 400;
  en la migración se pierde toda la pasada. En el estado real hoy no hay
  ninguno en null.
- Al fundir, `remapear_enlaces` no toca `mapaEnfermedad.celdas[].hechos` y
  `.preguntas` (6 ids colgando en el estado real) ni
  `cifrasAprendizaje.reutilizacion.detalle[].hechoId` (1): las cuentas del
  mapa quedan una arriba hasta el siguiente cierre de iteración.
"""

from rosa import hechos as H
from rosa.bucle import pasos as PS
from rosa.estado import acciones as A
from rosa.estado import plantilla as P

INV = "inv-adv"
T0 = 1_000_000


def _e():
    e = P.estado_inicial()
    assert A.crear_investigacion(e, {"titulo": "T", "objetivo": "GFAP y NfL en sangre", "condicionParada": "3 iteraciones"}, T0, INV) == INV
    return e


def _h(e, id_, enunciado, inv=INV, tipo="hecho", estado="sabido", fuente="f-1", pagina=4, referencia="Belder et al., 2026", afirmaciones=(), t=T0, **extra):
    h = P.nuevo_hecho(inv, tipo, "Biomarcadores", enunciado, estado, "fuente", [{"fuenteId": fuente, "referencia": referencia, "pagina": pagina}] if fuente else [], t, afirmacion_ids=list(afirmaciones))
    h["id"] = id_
    h.update(extra)
    e["hechos"].append(h)
    return h


def _af(id_, texto, fuente="f-1", localizador="pág. 4", veredicto="sostenida"):
    return {"id": id_, "texto": texto, "fuenteId": fuente, "localizador": localizador, "veredicto": veredicto, "fragmento": "fragmento literal"}


# -- 1. Mismo hecho: el marcador, la negación y la cifra con letra distinguen --


def test_dos_hechos_sobre_marcadores_distintos_no_son_el_mismo_hecho():
    """GFAP frente a sTREM2 (sin referencia común, solape 0,80) y GFAP frente
    a YKL40 o PSEN1 frente a APOE4 (misma fuente y página, solape 0,67): son
    hechos distintos y hoy se funden."""
    e = _e()
    a = _h(e, "he-a", "GFAP plasmático se eleva en portadores presintomáticos de mutación antes del inicio clínico estimado", fuente="f-1")
    b = _h(e, "he-b", "sTREM2 plasmático se eleva en portadores presintomáticos de mutación antes del inicio clínico estimado", fuente="f-2", referencia="Otro et al., 2024")
    assert H.mismo_hecho(a, b) is None
    c = _h(e, "he-c", "GFAP sube en portadores en fase preclínica", fuente="f-1")
    d = _h(e, "he-d", "YKL40 sube en portadores en fase preclínica", fuente="f-1")
    assert H.mismo_hecho(c, d) is None
    c2 = _h(e, "he-c2", "La cohorte incluyó portadores de PSEN1 con EYO negativo", fuente="f-1")
    d2 = _h(e, "he-d2", "La cohorte incluyó portadores de APOE4 con EYO negativo", fuente="f-1")
    assert H.mismo_hecho(c2, d2) is None
    supervivientes, mapa, _ = H.fundir_duplicados([a, b, c, d, c2, d2], T0)
    assert [x["id"] for x in supervivientes] == ["he-a", "he-b", "he-c", "he-d", "he-c2", "he-d2"] and mapa == {}


def test_un_hecho_y_su_negacion_con_palabra_larga_no_son_el_mismo():
    """"no" y "sin" son marcas cortas y distinguen; "nunca" y "never" son
    tokens largos y hoy pasan como paráfrasis con solape 0,89."""
    e = _e()
    a = _h(e, "he-a", "El tratamiento redujo la carga amiloide en la cohorte tratada frente a placebo")
    b = _h(e, "he-b", "El tratamiento nunca redujo la carga amiloide en la cohorte tratada frente a placebo", fuente="f-2")
    assert H.mismo_hecho(a, b) is None
    c = _h(e, "he-c", "Treatment reduced amyloid burden in the treated cohort compared with placebo")
    d = _h(e, "he-d", "Treatment never reduced amyloid burden in the treated cohort compared with placebo", fuente="f-2")
    assert H.mismo_hecho(c, d) is None


def test_las_cifras_escritas_con_letra_distinguen_dos_hechos_de_la_misma_fuente():
    """El bucle (`pasos.hecho_duplicado`) compara los números escritos con
    letra porque "cuatro" y "seis" son la misma frase para el solape; la regla
    de hechos.py no lo hace y con referencia común funde a 0,78. El estado
    real ya tiene hechos con "excluyeron cuatro no portadores"."""
    e = _e()
    a = _h(e, "he-a", "Belder et al. excluyeron cuatro no portadores con EYO superior a los veinte años del análisis", fuente="f-1")
    b = _h(e, "he-b", "Belder et al. excluyeron seis no portadores con EYO superior a los veinte años del análisis", fuente="f-1")
    assert PS.hecho_duplicado([a], b["enunciado"], b["procedencia"]) == (None, "")
    assert H.mismo_hecho(a, b) is None


def test_lo_que_el_bucle_deja_aparte_a_proposito_no_se_funde_al_cargar():
    """`pasos.hecho_duplicado` deja aparte una paráfrasis de otra fuente sin
    referencia común ("una replicación nace aparte"); la migración del almacén
    los funde al siguiente reinicio con `mismo_hecho`, que no mira la
    referencia. Las dos mitades del mismo hallazgo M-08 tienen que dar lo
    mismo: las 8 fusiones reales comparten referencia normalizada, así que
    exigirla no pierde ninguna."""
    e = _e()
    a = _h(e, "he-a", "GFAP plasmático se eleva en portadores presintomáticos de mutación antes del inicio clínico estimado", fuente="f-1", referencia="Belder et al., 2026")
    b = _h(e, "he-b", "El GFAP plasmático se eleva en los portadores presintomáticos de mutación antes del inicio clínico estimado", fuente="f-2", referencia="Johansson et al., 2023", t=T0 + 1)
    assert PS.hecho_duplicado([a], b["enunciado"], b["procedencia"]) == (None, "")
    r = H.migrar(e, T0 + 999)
    assert r["fundidos"] == 0 and [h["id"] for h in e["hechos"]] == ["he-a", "he-b"]


# -- 2. Enlace con afirmaciones: lo que la afirmación añade también cuenta -----


def test_una_afirmacion_que_niega_el_hecho_no_lo_sostiene():
    """Misma fuente, misma página, mismas palabras y un "no" (o un "nunca") en
    la afirmación: dice lo contrario del hecho. Hoy `cobertura` da 1,0 y
    `enlazar` la anota como cita "apoya"."""
    e = _e()
    h = _h(e, "he-a", "GFAP sube en portadores en fase preclínica de la enfermedad de Alzheimer autosómica dominante")
    negada = _af("af-no", "GFAP no sube en portadores en fase preclínica de la enfermedad de Alzheimer autosómica dominante")
    assert not H.sostiene(h, negada)
    assert H.enlazar(h, [negada]) == 0 and h["afirmacionIds"] == [] and h["citas"] == []
    h2 = _h(e, "he-b", "El tratamiento redujo la carga amiloide en la cohorte tratada frente a placebo en las 18 semanas")
    nunca = _af("af-nunca", "El tratamiento nunca redujo la carga amiloide en la cohorte tratada frente a placebo en las 18 semanas")
    assert not H.sostiene(h2, nunca)


def test_una_afirmacion_sobre_otro_marcador_no_sostiene_el_hecho():
    """Las frases paralelas de una sección de resultados ("GFAP sube...",
    "NfL sube...", "p-tau217 sube...") comparten fuente, página y el 89 % de
    los tokens del hecho; la sigla que cambia es justo lo que el hecho afirma.
    Hoy las tres quedan enlazadas al hecho de GFAP."""
    e = _e()
    h = _h(e, "he-a", "GFAP sube en portadores en fase preclínica de la enfermedad de Alzheimer autosómica dominante")
    otra_sigla = _af("af-nfl", "NfL sube en portadores en fase preclínica de la enfermedad de Alzheimer autosómica dominante")
    otro_largo = _af("af-ptau", "La p-tau217 plasmática sube en portadores en fase preclínica de la enfermedad de Alzheimer autosómica dominante")
    la_buena = _af("af-gfap", "GFAP plasmático sube en portadores en fase preclínica de la enfermedad de Alzheimer autosómica dominante")
    ids = [a["id"] for a in H.afirmaciones_que_sostienen(h, [otra_sigla, otro_largo, la_buena])]
    assert ids == ["af-gfap"]


# -- 3. Robustez: registros con null y los ids que quedan colgando ------------


def test_copiar_hechos_tolera_un_hecho_antiguo_con_listas_nulas():
    """`_migrar_grafo` solo rellena claves ausentes; un hecho guardado con
    `afirmacionIds: null` (o `citas`, `historial`, `procedencia`) hace que
    `fundir` itere sobre None y crear con herencia o bifurcar fallen entero
    (el servidor responde 400 "Argumentos inválidos")."""
    e = _e()
    _h(e, "he-a", "GFAP sube antes que NfL en portadores", afirmacionIds=None, citas=None, historial=None)
    _h(e, "he-b", "GFAP sube antes que NfL en portadores", fuente="f-2", t=T0 + 1)
    _h(e, "he-c", "NfL sube en la cohorte de Belder", procedencia=None, afirmacionIds=None)
    _h(e, "he-d", "NfL sube en la cohorte de Belder", fuente="f-3", t=T0 + 2)
    assert A.crear_investigacion(e, {"titulo": "D", "objetivo": "O", "condicionParada": "1", "heredarModeloDe": INV}, T0 + 100, id_="inv-d") == "inv-d"
    heredados = [h for h in e["hechos"] if h["investigacionId"] == "inv-d"]
    assert [h["id"] for h in heredados] == ["he-a-inv-d", "he-c-inv-d"]
    assert [p["fuenteId"] for p in heredados[0]["procedencia"]] == ["f-1", "f-2"]
    viejo = {"id": "he-v", "investigacionId": INV, "tipo": "hecho", "estado": "sabido", "enunciado": "GFAP sube antes que NfL en portadores de mutación en fase preclínica", "procedencia": [{"fuenteId": "f-1", "referencia": "R", "pagina": 4}], "afirmacionIds": None, "citas": None}
    assert H.enlazar(viejo, [_af("af-1", "GFAP sube antes que NfL en portadores de mutación en fase preclínica")]) == 1
    assert viejo["afirmacionIds"] == ["af-1"]


def test_migrar_no_deja_ids_fundidos_en_el_mapa_ni_en_las_cifras():
    """`inv.mapaEnfermedad.celdas[].hechos` y `.preguntas` y
    `inv.cifrasAprendizaje.reutilizacion.detalle[].hechoId` guardan ids de
    hechos; `remapear_enlaces` no los toca y tras fundir apuntan a hechos que
    ya no existen (6 y 1 en el estado real) hasta el siguiente cierre de
    iteración. Vale remapear o recalcular; lo que no vale es dejar el id
    colgando."""
    e = _e()
    _h(e, "he-a", "GFAP sube antes que NfL en portadores", fuente="f-1")
    _h(e, "he-b", "El GFAP sube antes que el NfL en portadores", fuente="f-2", t=T0 + 1)
    _h(e, "he-c", "TREM2 R47H atenúa la respuesta microglial", fuente="f-3")
    inv = next(i for i in e["investigaciones"] if i["id"] == INV)
    inv["mapaEnfermedad"] = {"celdas": [{"estadio": "preclinico", "region": None, "tipoCelular": "astrocito", "hechos": ["he-a", "he-b"], "hipotesis": [], "preguntas": ["he-b"]}, {"estadio": None, "region": None, "tipoCelular": "microglia", "hechos": ["he-c"], "hipotesis": [], "preguntas": []}], "huecos": [], "sinEjes": 0, "hipotesisSinEjes": 0, "resumen": "x"}
    inv["cifrasAprendizaje"] = {"reutilizacion": {"detalle": [{"hechoId": "he-b", "estado": "sabido", "tema": "Biomarcadores", "usadoPor": [], "motivo": "m"}]}}
    r = H.migrar(e, T0 + 999)
    assert r["fundidos"] == 1
    ids = {h["id"] for h in e["hechos"]}
    colgando = [x for c in inv["mapaEnfermedad"]["celdas"] for x in c["hechos"] + c["preguntas"] if x not in ids]
    assert colgando == []
    assert inv["cifrasAprendizaje"]["reutilizacion"]["detalle"][0]["hechoId"] in ids
