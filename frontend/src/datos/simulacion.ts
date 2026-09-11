// Simulacion de la corrida en marcha. Hace avanzar la iteracion actual paso
// a paso para que la pantalla de corrida se pueda construir y juzgar en vivo
// antes de que exista el bucle real. Es una funcion pura sobre el estado
// (avanzar) mas un reloj (iniciarSimulacion) que la aplica cada pocos
// segundos mientras la corrida este en marcha.
//
// Ademas del plan, la simulacion hace lo que el bucle real hara y la
// interfaz necesita ver: gasta contra el presupuesto global y lo pausa al
// llegar al tope; espera a que se apruebe el plan de cada iteracion nueva
// (o lo autoaprueba si se pidio); completa replicaciones; aclara las
// hipotesis marcadas "no puedo juzgar"; cierra pistas detenidas; y deja
// eventos para el resumen "mientras no estabas".

import type { EstadoRosa, Hipotesis, Iteracion, PasoPlan, Pista, TipoPista } from './tipos';
import { FUENTES } from './muestra';
import { aclararHipotesis, conEvento, nuevoId } from './acciones';
import { estadoPresupuesto } from '../lib/calidad';

/** Cada cuanto avanza la simulacion. */
export const TICK_MS = 2_500;

interface PlantillaPista {
  tipo: TipoPista;
  titulo: string;
  fuente: string;
  lineas: { tipo: Pista['transcripcion'][number]['tipo']; texto: string; consulta?: Pista['transcripcion'][number]['consulta'] }[];
  resumenFinal: string;
  /** La pista falla en las iteraciones impares (para ver pasos fallidos). */
  fallaEnImpares?: boolean;
}

const PLANTILLA: { titulo: string; detalle: string; presupuesto: number | null; pistas: PlantillaPista[] }[] = [
  {
    titulo: 'Reordenar preguntas abiertas',
    detalle: 'Por prioridad y por lo aprendido en la iteracion anterior',
    presupuesto: 5,
    pistas: [
      {
        tipo: 'modelo',
        titulo: 'Reordenar las preguntas abiertas',
        fuente: 'GPT-6 Astra',
        lineas: [
          { tipo: 'accion', texto: 'Leyendo el modelo de mundo: hechos, preguntas abiertas, descartes' },
          { tipo: 'resultado', texto: '3 preguntas abiertas reordenadas; la de NfL y GFAP sigue primera' },
        ],
        resumenFinal: '3 preguntas priorizadas',
      },
    ],
  },
  {
    titulo: 'Buscar literatura',
    detalle: 'PubMed, Europe PMC y bioRxiv',
    presupuesto: 30,
    pistas: [
      {
        tipo: 'literatura',
        titulo: 'GFAP antes que NfL en portadores de APOE4',
        fuente: 'PubMed',
        lineas: [
          {
            tipo: 'accion',
            texto: 'esearch: GFAP AND neurofilament AND APOE4 AND plasma AND longitudinal',
            consulta: { base: 'PubMed E-utilities', parametros: 'db=pubmed&term=GFAP AND neurofilament AND APOE4 AND plasma AND longitudinal&retmax=100', resultados: '19 PMID' },
          },
          { tipo: 'resultado', texto: '19 PMID; 6 con texto completo en PMC' },
          { tipo: 'accion', texto: 'Comprobando retractaciones en Crossref', consulta: { base: 'Crossref', parametros: 'GET /works/{doi} x6, campo updated-by', resultados: '0 retractados' } },
          { tipo: 'resultado', texto: 'Ninguno retractado' },
        ],
        resumenFinal: '19 resultados, 6 con texto completo',
      },
      {
        tipo: 'literatura',
        titulo: 'Preprints sobre GFAP y microglia',
        fuente: 'bioRxiv y medRxiv',
        lineas: [
          { tipo: 'accion', texto: 'API de bioRxiv: GFAP microglia Alzheimer, ultimos 12 meses', consulta: { base: 'bioRxiv API', parametros: '/details/biorxiv/2025-09-01/2026-09-10 + filtro GFAP microglia', resultados: '4 preprints' } },
          { tipo: 'resultado', texto: '4 preprints; 1 ya publicado, se toma la version publicada' },
        ],
        resumenFinal: '4 preprints',
      },
      {
        tipo: 'ensayos',
        titulo: 'ARIA en portadores de APOE4 (reintento)',
        fuente: 'ClinicalTrials.gov v2',
        lineas: [
          { tipo: 'accion', texto: 'GET /api/v2/studies?query.cond=Alzheimer&query.term=ARIA APOE4', consulta: { base: 'ClinicalTrials.gov v2', parametros: 'query.cond=Alzheimer&query.term=ARIA APOE4&pageSize=100', resultados: '7 estudios' } },
          { tipo: 'resultado', texto: '7 estudios con ARIA como desenlace de seguridad y estratificacion por APOE4' },
        ],
        resumenFinal: '7 estudios',
        fallaEnImpares: true,
      },
    ],
  },
  {
    titulo: 'Extraer afirmaciones con procedencia',
    detalle: 'Fragmentos por pagina',
    presupuesto: 40,
    pistas: [
      {
        tipo: 'extraccion',
        titulo: 'Extraer afirmaciones de los articulos nuevos',
        fuente: 'Sonnet 5',
        lineas: [
          { tipo: 'accion', texto: 'Fragmentos por pagina (GROBID + Docling), sin cruzar de pagina' },
          { tipo: 'resultado', texto: 'Articulo 4 de 12: 51 afirmaciones acumuladas' },
          { tipo: 'resultado', texto: 'Articulo 8 de 12: 102 afirmaciones acumuladas' },
          { tipo: 'resultado', texto: 'Articulo 12 de 12: 148 afirmaciones con cita' },
        ],
        resumenFinal: '12 articulos, 148 afirmaciones con cita',
      },
    ],
  },
  {
    titulo: 'Verificar cada afirmacion',
    detalle: 'Deterministas, triaje de Sonnet 5, juez Opus 5',
    presupuesto: 30,
    pistas: [
      {
        tipo: 'verificacion',
        titulo: 'Verificar 148 afirmaciones',
        fuente: 'Opus 5 (juez)',
        lineas: [
          { tipo: 'accion', texto: 'Comprobaciones deterministas: citas que resuelven, identificadores, cifras normalizadas' },
          { tipo: 'resultado', texto: '3 citas no resuelven; 1 NCT ausente del fragmento' },
          { tipo: 'accion', texto: 'Triaje (Sonnet 5): 121 claramente sostenidas pasan; 23 dudosas y 12 de muestra al juez' },
          { tipo: 'resultado', texto: 'Juez: 29 sostenidas, 4 parciales, 2 no sostenidas (1 de otra entidad)' },
        ],
        resumenFinal: '148 afirmaciones: 141 sostenidas, 4 parciales, 6 bloqueadas',
      },
    ],
  },
  {
    titulo: 'Comprobar novedad',
    detalle: 'Open Targets, ClinicalTrials.gov, Agora y precedente en literatura',
    presupuesto: 10,
    pistas: [
      {
        tipo: 'novedad',
        titulo: 'Novedad de la hipotesis sobre GFAP y NfL',
        fuente: 'Open Targets, ClinicalTrials.gov, Agora',
        lineas: [
          { tipo: 'accion', texto: 'GraphQL Open Targets: GFAP, NEFL x Alzheimer', consulta: { base: 'Open Targets GraphQL', parametros: 'target(GFAP, NEFL) associatedDiseases(EFO_0000249)', resultados: 'GFAP 0,18; NEFL 0,22' } },
          { tipo: 'resultado', texto: 'GFAP asociacion 0,18 (biomarcador, no diana); NEFL 0,22' },
          { tipo: 'accion', texto: 'ClinicalTrials.gov: GFAP AND NfL AND APOE4 como desenlace' },
          { tipo: 'resultado', texto: 'Ningun ensayo con ese orden temporal como desenlace: novedad plausible' },
        ],
        resumenFinal: 'Sin ensayo ni diana previa: novedad plausible',
      },
    ],
  },
  {
    titulo: 'Actualizar el modelo de mundo',
    detalle: '',
    presupuesto: 5,
    pistas: [
      {
        tipo: 'modelo',
        titulo: 'Actualizar hechos y preguntas',
        fuente: 'GPT-6 Astra',
        lineas: [
          { tipo: 'accion', texto: 'Anadiendo hechos sostenidos con su procedencia' },
          { tipo: 'resultado', texto: '1 hecho anadido, 1 hipotesis a la cola de revision' },
        ],
        resumenFinal: '1 hecho, 1 hipotesis nueva',
      },
    ],
  },
];

function pistasDePaso(iteracionId: string, paso: PasoPlan, indice: number): Pista[] {
  const plantilla = PLANTILLA[indice];
  if (!plantilla || paso.indicacionHumana) return [];
  return plantilla.pistas.map((p) => ({
    id: nuevoId('pi'),
    iteracionId,
    pasoId: paso.id,
    tipo: p.tipo,
    titulo: p.titulo,
    fuente: p.fuente,
    estado: 'en_curso',
    resumen: 'empezando',
    ms: 0,
    transcripcion: [],
  }));
}

function plantillaDe(pista: Pista): PlantillaPista | null {
  for (const paso of PLANTILLA) {
    const p = paso.pistas.find((x) => x.titulo === pista.titulo);
    if (p) return p;
  }
  return null;
}

function indiceDePlantilla(paso: PasoPlan): number {
  return PLANTILLA.findIndex((p) => p.titulo === paso.titulo);
}

export function nuevaIteracion(corridaId: string, numero: number, ahora: number): Iteracion {
  return {
    id: nuevoId('it'),
    corridaId,
    numero,
    empezadaEn: ahora,
    terminadaEn: null,
    planAprobado: false,
    planPropuestoEn: ahora,
    presupuesto: { limite: 120, usado: 0 },
    resumen: '',
    plan: PLANTILLA.map((p) => ({ id: nuevoId('paso'), titulo: p.titulo, detalle: p.detalle, estado: 'pendiente' as const, indicacionHumana: false, motivoFallo: null, presupuesto: p.presupuesto })),
    pistas: [],
  };
}

function hipotesisSimulada(investigacionId: string, iteracion: number, ahora: number): Hipotesis {
  const f = FUENTES.trem2apoe!;
  return {
    id: nuevoId('hip'),
    investigacionId,
    titulo: 'GFAP en plasma se altera antes que NfL en portadores de APOE4 con amiloide positivo',
    enunciado:
      'En portadores de APOE4 con PET de amiloide positiva y sin deterioro, GFAP en plasma sube antes que NfL, y la diferencia de tiempo entre ambos predice la velocidad de progresion a MCI.',
    mecanismo: 'Reaccion astroglial temprana ante las placas, previa al dano axonal que NfL refleja.',
    comprobacion: {
      biomarcador: 'GFAP y NfL en plasma, seriados cada 6 meses',
      cohorte: 'A4 y ADNI, portadores de APOE4 amiloide positivos sin deterioro',
      diseno: 'Modelos de tiempo hasta el primer cambio significativo de cada marcador; asociar la brecha con la conversion a MCI',
    },
    estado: 'propuesta',
    elo: 1_500,
    historialElo: [{ iteracion, elo: 1_500 }],
    rivales: ['hip-4'],
    novedad: {
      openTargets: { estado: 'evidencia_previa', detalle: 'GFAP y NEFL con asociacion debil como biomarcadores' },
      ensayos: { estado: 'sin_ensayo', detalle: 'Ningun ensayo usa la brecha GFAP-NfL como desenlace', nct: null },
      agora: { estado: 'no_nominada', detalle: 'No aplica: no es una diana' },
      precedente: { estado: 'parcial', detalle: 'Dos cohortes describen GFAP temprano; ninguna mide la brecha con NfL como predictor.' },
    },
    afirmaciones: [
      { texto: 'La microglia atenuada en R47H y APOE4 deja a la astroglia como respuesta compensatoria.', cita: `[${f.referencia}, pag. ${f.pagina}]`, veredicto: 'parcial', motivo: 'La fuente sugiere la compensacion; no la mide.', entidadDistinta: false, tipo: 'interpretacion', trayectoria: null },
    ],
    procedencia: {
      mensajes: [{ id: nuevoId('m'), de: 'rosa', texto: 'Hipotesis generada por la simulacion de la interfaz a partir de la pregunta abierta sobre NfL y GFAP.', creadoEn: ahora }],
      codigo: 'salida = generar(hechos=hechos_iteracion, pregunta_abierta="orden de NfL y GFAP")',
      registro: ['(simulacion) generar -> 1 hipotesis', '(simulacion) juez -> parcial', '(simulacion) novedad -> sin ensayo'],
      entorno: { lenguaje: 'Python', version: '3.12.14', paquetes: [{ nombre: 'dspy', version: '3.3.1' }], modelos: [{ nombre: 'openai/gpt-6-astra', version: 'gateway' }] },
      fuentes: [f],
    },
    hallazgos: [],
    revisiones: [{ fecha: ahora, quien: 'Rosa', accion: 'propuesta', nota: `Iteracion ${iteracion} (simulacion)`, aCiegas: false }],
    creadaEn: ahora,
    iteracion,
    origen: 'rosa',
    derivadaDe: 'hip-4',
    cluster: 'Biomarcadores sanguineos',
    evidenciaEstadistica: 'moderada',
    relevancia: { justificacion: 'Responde a la pregunta abierta con mas prioridad del modelo de mundo (orden de NfL y GFAP).', votoHumano: null },
    partidos: [],
    revisionesAutomaticas: [
      { tipo: 'inicial', estado: 'hecha', resumen: 'Plausible; deriva de una hipotesis aceptada.', fecha: ahora },
      { tipo: 'completa', estado: 'pendiente', resumen: '', fecha: null },
      { tipo: 'profunda', estado: 'pendiente', resumen: '', fecha: null },
      { tipo: 'observacion', estado: 'pendiente', resumen: '', fecha: null },
      { tipo: 'simulacion', estado: 'pendiente', resumen: '', fecha: null },
      { tipo: 'torneo', estado: 'pendiente', resumen: '', fecha: null },
    ],
    supuestos: [],
    revisionesHumanas: [],
    replicacion: null,
    ultimaRevisionAutomatica: ahora,
    coste: { literatura: 1.1, analisis: 0 },
    experimento: null,
    prerregistradaEn: ahora,
  };
}

/** Resultado fijo de la replicacion, por hipotesis, para que la muestra sea determinista. */
function resultadoReplicacion(h: Hipotesis, indice: number): 'sostiene' | 'contradice' {
  if (h.id === 'hip-2') return indice === 3 ? 'contradice' : 'sostiene';
  if (h.estado === 'descartada') return 'contradice';
  return 'sostiene';
}

/**
 * Un paso de la simulacion. Devuelve el mismo objeto si no hay nada que
 * avanzar, para que el almacen no avise a nadie.
 */
export function avanzar(estado: EstadoRosa, ahora: number): EstadoRosa {
  let e = estado;

  // Hipotesis marcadas "no puedo juzgar": Rosa las aclara.
  for (const h of e.hipotesis) {
    if (h.estado === 'aclarando') {
      const ultima = h.revisiones[h.revisiones.length - 1];
      if (ultima && ultima.accion === 'no_puedo_juzgar' && ahora - ultima.fecha >= TICK_MS) {
        e = aclararHipotesis(e, h.id, `Aclaracion a "${ultima.nota}": reescribo el enunciado con el contexto que faltaba y marco lo que es inferencia mia. Vuelve a la cola como aclarada.`, ahora);
      }
    }
  }

  // Replicaciones en curso: una trayectoria por tick.
  if (e.hipotesis.some((h) => h.replicacion?.estado === 'en_curso')) e = {
    ...e,
    hipotesis: e.hipotesis.map((h) => {
      if (!h.replicacion || h.replicacion.estado !== 'en_curso') return h;
      const i = h.replicacion.hechas;
      const r = resultadoReplicacion(h, i);
      const hechas = i + 1;
      return {
        ...h,
        replicacion: {
          ...h.replicacion,
          hechas,
          sostienen: h.replicacion.sostienen + (r === 'sostiene' ? 1 : 0),
          contradicen: h.replicacion.contradicen + (r === 'contradice' ? 1 : 0),
          estado: hechas >= h.replicacion.total ? 'terminada' : 'en_curso',
        },
      };
    }),
  };

  // Planes que esperan aprobacion: autoaprobar si se pidio.
  for (const c of e.corridas) {
    if (c.estado !== 'esperando_plan' || c.autoAprobarPlanSegundos === null) continue;
    const it = e.iteraciones.filter((i) => i.corridaId === c.id).reduce<Iteracion | null>((m, i) => (m === null || i.numero > m.numero ? i : m), null);
    if (it && !it.planAprobado && ahora - it.planPropuestoEn >= c.autoAprobarPlanSegundos * 1000) {
      e = {
        ...e,
        iteraciones: e.iteraciones.map((i) => (i.id === it.id ? { ...i, planAprobado: true, empezadaEn: ahora } : i)),
        corridas: e.corridas.map((x) => (x.id === c.id ? { ...x, estado: 'en_marcha' as const } : x)),
      };
      e = conEvento(e, c.investigacionId, 'corrida_estado', `Plan de la iteracion ${it.numero} autoaprobado tras ${c.autoAprobarPlanSegundos} s sin respuesta`, null, ahora);
    }
  }

  const corrida = e.corridas.find((c) => c.estado === 'en_marcha');
  if (!corrida) return e;
  const iteraciones = e.iteraciones.filter((i) => i.corridaId === corrida.id);
  const actual = iteraciones.reduce<Iteracion | null>((max, i) => (max === null || i.numero > max.numero ? i : max), null);
  if (!actual) return e;
  if (!actual.planAprobado) {
    // Sin plan aprobado la corrida no avanza: queda esperando.
    return { ...e, corridas: e.corridas.map((c) => (c.id === corrida.id ? { ...c, estado: 'esperando_plan' as const } : c)) };
  }

  // Gasto: cada tick cuesta algo, siempre.
  const gasto = {
    ...corrida.gasto,
    llamadas: corrida.gasto.llamadas + 1,
    tokensEntrada: corrida.gasto.tokensEntrada + 18_000,
    tokensSalida: corrida.gasto.tokensSalida + 1_400,
    segundos: Math.round((ahora - corrida.empezadaEn) / 1000),
  };
  const contexto = {
    ...corrida.contexto,
    tokensUsados: corrida.contexto.tokensUsados + 6_000 > corrida.contexto.tokensLimite * 0.9 ? Math.round(corrida.contexto.tokensLimite * 0.35) : corrida.contexto.tokensUsados + 6_000,
    compactaciones: corrida.contexto.tokensUsados + 6_000 > corrida.contexto.tokensLimite * 0.9 ? corrida.contexto.compactaciones + 1 : corrida.contexto.compactaciones,
    ultimaCompactacion: corrida.contexto.tokensUsados + 6_000 > corrida.contexto.tokensLimite * 0.9 ? ahora : corrida.contexto.ultimaCompactacion,
  };
  let corridaNueva = { ...corrida, gasto, contexto };

  // Presupuesto global: alertas y pausa al tope. Una pregunta pendiente
  // (permiso o incidencia) tiene prioridad: la corrida queda en
  // "esperando aprobacion", no en "pausada por presupuesto".
  const pres = estadoPresupuesto(corridaNueva);
  if (pres.nuevasAlertas.length > 0) {
    corridaNueva = { ...corridaNueva, presupuesto: { ...corridaNueva.presupuesto, avisadas: [...corridaNueva.presupuesto.avisadas, ...pres.nuevasAlertas] } };
    for (const a of pres.nuevasAlertas) {
      e = conEvento(e, corrida.investigacionId, 'presupuesto', `La corrida paso del ${Math.round(a * 100)} % del presupuesto global (${gasto.llamadas} de ${corridaNueva.presupuesto.limiteLlamadas} llamadas)`, null, ahora);
    }
  }
  if (pres.agotado) {
    const pendientes = e.solicitudes.some((s) => s.corridaId === corrida.id && s.estado === 'pendiente') || e.incidencias.some((i) => i.corridaId === corrida.id && i.estado === 'pendiente');
    corridaNueva = { ...corridaNueva, estado: pendientes ? 'esperando_aprobacion' : 'pausada_por_presupuesto' };
    e = conEvento(e, corrida.investigacionId, 'presupuesto', `Presupuesto global agotado (${corridaNueva.presupuesto.limiteLlamadas} llamadas): la corrida se pauso. Amplia el tope para seguir.`, null, ahora);
    return { ...e, corridas: e.corridas.map((c) => (c.id === corrida.id ? corridaNueva : c)) };
  }

  let corridas = e.corridas.map((c) => (c.id === corrida.id ? corridaNueva : c));
  let hipotesis = e.hipotesis;
  let hechos = e.hechos;
  let nuevasIteraciones = e.iteraciones;

  let plan = actual.plan;
  let pistas = actual.pistas;
  const presupuesto = { ...actual.presupuesto, usado: Math.min(actual.presupuesto.limite, actual.presupuesto.usado + 1) };
  let terminadaEn = actual.terminadaEn;
  let resumen = actual.resumen;

  const enCurso = plan.find((p) => p.estado === 'en_curso');
  if (enCurso) {
    const propias = pistas.filter((p) => p.pasoId === enCurso.id);
    const abiertas = propias.filter((p) => p.estado === 'en_curso');
    if (abiertas.length === 0 && propias.length === 0 && !enCurso.indicacionHumana && indiceDePlantilla(enCurso) !== -1) {
      pistas = [...pistas, ...pistasDePaso(actual.id, enCurso, indiceDePlantilla(enCurso))];
    } else if (abiertas.length > 0) {
      pistas = pistas.map((p) => {
        if (p.pasoId !== enCurso.id || p.estado !== 'en_curso') return p;
        const plantilla = plantillaDe(p);
        if (!plantilla) return { ...p, estado: 'hecha', ms: p.ms > 0 ? p.ms : TICK_MS * Math.max(1, p.transcripcion.length) };
        // Fallo deterministico en iteraciones impares para las pistas marcadas.
        if (plantilla.fallaEnImpares && actual.numero % 2 === 1 && p.transcripcion.length >= 1) {
          return {
            ...p,
            estado: 'fallida',
            resumen: 'Sin respuesta en 30 s: se reintenta en la siguiente iteracion',
            ms: 30_000,
            transcripcion: [...p.transcripcion, { t: 30_000, tipo: 'error' as const, texto: 'Tiempo limite agotado (30 s). No es "sin ensayos": la consulta no llego.' }],
          };
        }
        const siguiente = plantilla.lineas[p.transcripcion.length];
        const transcripcion = siguiente ? [...p.transcripcion, { t: p.transcripcion.length * TICK_MS, ...siguiente }] : p.transcripcion;
        const acabada = transcripcion.length >= plantilla.lineas.length;
        return {
          ...p,
          transcripcion,
          estado: acabada ? 'hecha' : 'en_curso',
          resumen: acabada ? plantilla.resumenFinal : transcripcion.at(-1)?.texto ?? p.resumen,
          ms: acabada ? transcripcion.length * TICK_MS : p.ms,
        };
      });
    } else {
      // Sin pistas abiertas: el paso termina. Fallido si todas sus pistas fallaron.
      const fallidas = propias.filter((p) => p.estado === 'fallida').length;
      const todasFallaron = propias.length > 0 && fallidas === propias.length;
      const detalle = propias.length > 0 ? propias.map((p) => p.resumen).join(' · ') : enCurso.detalle;
      plan = plan.map((p) =>
        p.id === enCurso.id
          ? { ...p, estado: todasFallaron ? 'fallido' : 'hecho', detalle, motivoFallo: todasFallaron ? 'Ninguna de sus pistas termino: ' + propias.map((x) => x.resumen).join('; ') : null }
          : p,
      );
    }
  } else {
    const pendiente = plan.find((p) => p.estado === 'pendiente');
    if (pendiente) {
      plan = plan.map((p) => (p.id === pendiente.id ? { ...p, estado: 'en_curso' } : p));
      const indice = indiceDePlantilla(pendiente);
      if (!pendiente.indicacionHumana && indice !== -1) pistas = [...pistas, ...pistasDePaso(actual.id, pendiente, indice)];
    } else {
      // Iteracion cerrada: resumen, evento, y la siguiente espera su plan.
      const hechas = pistas.filter((p) => p.estado === 'hecha').length;
      const fallidas = pistas.filter((p) => p.estado === 'fallida' || p.estado === 'detenida').length;
      resumen = `${plan.length} pasos, ${hechas} pistas completadas${fallidas > 0 ? `, ${fallidas} sin completar` : ''}`;
      terminadaEn = ahora;
      const siguiente = nuevaIteracion(corrida.id, actual.numero + 1, ahora);
      nuevasIteraciones = [...e.iteraciones, siguiente];
      corridas = corridas.map((c) => (c.id === corrida.id ? { ...c, iteracionActual: siguiente.numero, estado: 'esperando_plan' as const, gasto: { ...c.gasto, articulosLeidos: c.gasto.articulosLeidos + 12 } } : c));
      e = conEvento(e, corrida.investigacionId, 'iteracion_terminada', `Iteracion ${actual.numero} terminada: ${resumen}`, `#/investigaciones/${corrida.investigacionId}/corrida`, ahora);
      const yaAnadida = hipotesis.some((h) => h.titulo.startsWith('GFAP en plasma se altera antes que NfL'));
      if (!yaAnadida) {
        const nueva = hipotesisSimulada(corrida.investigacionId, actual.numero, ahora);
        hipotesis = [...hipotesis, nueva];
        e = conEvento(e, corrida.investigacionId, 'hipotesis_nueva', `Hipotesis nueva en la cola: ${nueva.titulo}`, `#/investigaciones/${corrida.investigacionId}/hipotesis/${nueva.id}`, ahora);
        const f = FUENTES.trem2apoe!;
        hechos = [
          ...hechos,
          {
            id: nuevoId('he'),
            investigacionId: corrida.investigacionId,
            tipo: 'hecho',
            tema: 'Biomarcadores',
            estado: 'sabido',
            origen: 'fuente',
            enunciado: 'GFAP en plasma es un marcador de reaccion astroglial; NfL, de dano axonal, no especifico de Alzheimer.',
            procedencia: [{ fuenteId: f.id, referencia: f.referencia, pagina: f.pagina }],
            motivoDescarte: null,
            actualizadoEn: ahora,
            prioridad: 5,
            citas: [],
            historial: [{ fecha: ahora, de: null, a: 'sabido', quien: 'Rosa', motivo: `Anadido en la iteracion ${actual.numero}` }],
          },
        ];
        e = conEvento(e, corrida.investigacionId, 'hecho_nuevo', 'Hecho nuevo en el modelo de mundo: GFAP como marcador astroglial, NfL como axonal', `#/investigaciones/${corrida.investigacionId}/mundo`, ahora);
      }
    }
  }

  nuevasIteraciones = nuevasIteraciones.map((i) => (i.id === actual.id ? { ...i, plan, pistas, presupuesto, terminadaEn, resumen } : i));
  return { ...e, corridas, iteraciones: nuevasIteraciones, hipotesis, hechos };
}

/** Arranca el reloj. Devuelve la funcion que lo para. */
export function iniciarSimulacion(aplicar: (fn: (estado: EstadoRosa) => EstadoRosa) => void, tickMs = TICK_MS): () => void {
  const id = window.setInterval(() => aplicar((e) => avanzar(e, Date.now())), tickMs);
  return () => window.clearInterval(id);
}
