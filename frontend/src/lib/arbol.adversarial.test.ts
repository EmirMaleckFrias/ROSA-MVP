// Tests adversariales de la profundidad hasta el dato (16 de septiembre de
// 2026): registros antiguos sin claves, ids que chocan, planes sin conjunto de
// datos, fechas de los análisis en el deslizador de iteraciones, entradas que
// no deben mutarse, determinismo y coste con miles de afirmaciones.
import { describe, expect, it } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import type { Afirmacion, Ejecucion, EstadoRosa, Hipotesis, PlanAnalisis } from '../datos/tipos';
import { construirArbol, ESTRUCTURA, SIN_DISTANCIA, visiblesIniciales } from './arbol';

const clon = <T,>(x: T): T => structuredClone(x);

function ejecucion(id: string, hipotesisId: string | null, planId: string, extra: Partial<Ejecucion> = {}): Ejecucion {
  return {
    id,
    investigacionId: 'inv-1',
    hipotesisId,
    planId,
    tipo: 'hipotesis',
    codigo: '',
    entorno: { python: '3.12', paquetes: [] },
    semilla: 1,
    hashDatos: '',
    hashPlan: '',
    inicio: 1,
    fin: 2,
    estado: 'completado',
    runtime: 'docker',
    red: 'deshabilitada',
    codigoSalida: 0,
    duracionS: 1,
    salida: '',
    error: '',
    resultados: {},
    baseline: {},
    controlNegativo: {},
    repeticiones: [],
    interpretacion: null,
    plausibilidadVerificada: true,
    auditoria: { veredicto: 'valido', comprobaciones: [], motivo: '', quien: 'Killer II', fecha: 2 },
    ...extra,
  };
}

function plan(id: string, hipotesisId: string, datasetId: string): PlanAnalisis {
  return {
    id,
    investigacionId: 'inv-1',
    hipotesisId,
    datasetId,
    tipo: 'confirmatorio',
    pregunta: '',
    variables: [],
    poblacion: '',
    preprocesado: [],
    prueba: '',
    hipotesisNula: '',
    hipotesisAlternativa: '',
    alpha: 0.05,
    direccionEsperada: '',
    tamanoEfectoMinimo: '',
    baseline: '',
    controlNegativo: '',
    correccionMultiplicidad: '',
    umbralEfecto: '',
    criterioNoEvaluable: '',
    semilla: 1,
    hashDatos: '',
    hashPlan: '',
    congeladoEn: 1,
    autor: 'rosa',
    reproduccionId: null,
  };
}

/** La afirmación derivada tal como la escribe hoy rosa/bucle/analisis.py: sin
 *  `iteracion` ni `afirmacionId`, con la trayectoria apuntando a la ejecución. */
function derivada(runId: string, extra: Partial<Afirmacion> = {}): Afirmacion {
  return { texto: 'Correlación moderada, baseline y control negativo en orden.', cita: `[Análisis in silico ${runId}]`, veredicto: 'sostenida', motivo: '', entidadDistinta: false, tipo: 'dato', clase: 'derivado', sintetico: false, trayectoria: { id: runId, celda: 0 }, ...extra };
}

function base() {
  const e = clon(estadoDeMuestra());
  const inv = e.investigaciones[0]!;
  const h1 = e.hipotesis.find((x) => x.id === 'hip-1')!;
  return { e, inv, h1 };
}

describe('profundidad hasta el dato: adversarios', () => {
  it('no muta el estado que recibe y da el mismo grafo dos veces', () => {
    const { e, inv, h1 } = base();
    e.ejecuciones = [ejecucion('run-1', h1.id, 'plan-1')];
    e.planesAnalisis = [plan('plan-1', h1.id, inv.datasets[0]!.id)];
    h1.afirmaciones = [...h1.afirmaciones, derivada('run-1')];
    const antes = clon(e);
    const g1 = construirArbol(e, inv);
    expect(e).toEqual(antes);
    const g2 = construirArbol(e, inv);
    const foto = (g: ReturnType<typeof construirArbol>) => JSON.stringify({ nodos: g.nodos, enlaces: g.enlaces, d: [...g.profundidadDato!], l: [...g.profundidadLiteratura!] });
    expect(foto(g1)).toBe(foto(g2));
  });

  it('un registro antiguo sin partidos, procedencia, afirmaciones, hechos ni iteraciones no rompe', () => {
    const { e, inv } = base();
    const desnuda = { id: 'hip-vieja', investigacionId: inv.id, titulo: 'Hipótesis de un registro antiguo', estado: 'propuesta', elo: 1500, iteracion: 1, cluster: '' } as unknown as Hipotesis;
    const viejo = { ...e, hipotesis: [desnuda], hechos: undefined, iteraciones: undefined, corridas: undefined, ejecuciones: undefined, planesAnalisis: undefined } as unknown as EstadoRosa;
    const g = construirArbol(viejo, inv);
    expect(g.porId.get('hip-vieja')?.tipo).toBe('hipotesis');
    expect(g.porId.get('hip-vieja')?.profundidadDato).toBeNull();
    expect(g.porId.get('hip-vieja')?.profundidadLiteratura).toBeNull();
    expect(visiblesIniciales(g, [desnuda]).has('hip-vieja')).toBe(true);
    for (const en of g.enlaces) {
      expect(g.porId.has(en.de), en.de).toBe(true);
      expect(g.porId.has(en.a), en.a).toBe(true);
    }
  });

  it('una ejecución cuyo id choca con una hipótesis no la pisa: el análisis recibe otro id y los enlaces lo siguen', () => {
    const { e, inv, h1 } = base();
    const h2 = e.hipotesis.find((x) => x.id === 'hip-2')!;
    // Un id de ejecución igual al de otra hipótesis viva de la misma investigación.
    e.ejecuciones = [ejecucion(h2.id, h1.id, 'plan-1')];
    e.planesAnalisis = [plan('plan-1', h1.id, inv.datasets[0]!.id)];
    h1.afirmaciones = [...h1.afirmaciones, derivada(h2.id)];
    const g = construirArbol(e, inv);
    expect(g.porId.get(h2.id)?.tipo).toBe('hipotesis');
    expect(g.porId.get(h2.id)?.iteracion).toBe(h2.iteracion);
    const analisis = g.nodos.filter((n) => n.tipo === 'ejecucion');
    expect(analisis.length).toBe(1);
    expect(analisis[0]!.id).not.toBe(h2.id);
    expect(g.enlaces.some((en) => en.tipo === 'dato' && en.de === h1.id && en.a === analisis[0]!.id)).toBe(true);
    expect(g.enlaces.some((en) => en.tipo === 'dato' && en.de.startsWith('af-') && en.a === analisis[0]!.id)).toBe(true);
    expect(g.enlaces.some((en) => en.tipo === 'dato' && en.a === h2.id)).toBe(false);
    expect(g.porId.get(h1.id)?.profundidadDato).toBe(1);
  });

  it('un plan sin conjunto de datos o una ejecución con planId "sin-plan" no crean nodos vacíos ni aristas sueltas', () => {
    const { e, inv, h1 } = base();
    e.ejecuciones = [ejecucion('run-a', h1.id, 'sin-plan'), ejecucion('run-b', h1.id, 'plan-vacio')];
    e.planesAnalisis = [plan('plan-vacio', h1.id, '')];
    const g = construirArbol(e, inv);
    expect(g.nodos.filter((n) => n.tipo === 'dataset')).toEqual([]);
    expect(g.porId.has('ds-')).toBe(false);
    expect(g.porId.get('run-a')?.profundidadDato).toBe(0);
    expect(g.porId.get(h1.id)?.profundidadDato).toBe(1);
    for (const en of g.enlaces) {
      expect(g.porId.has(en.de), en.de).toBe(true);
      expect(g.porId.has(en.a), en.a).toBe(true);
    }
    // Una ejecución listada en la hipótesis pero ausente del estado no es "sin análisis": simplemente no se dibuja.
    h1.ejecuciones = ['run-fantasma'];
    e.ejecuciones = [];
    const g2 = construirArbol(e, inv);
    expect(g2.porId.has('run-fantasma')).toBe(false);
    expect(g2.porId.get(h1.id)?.profundidadDato).toBeNull();
  });

  it('el análisis, su afirmación derivada y su conjunto de datos aparecen en la iteración en que corrieron, no en la que nació la hipótesis', () => {
    const { e, inv, h1 } = base();
    const it14 = e.iteraciones.find((i) => i.numero === 14)!;
    const it13 = e.iteraciones.find((i) => i.numero === 13)!;
    expect(h1.iteracion).toBe(13);
    const ds = inv.datasets[0]!.id;
    e.planesAnalisis = [plan('plan-1', h1.id, ds)];
    e.ejecuciones = [
      ejecucion('run-14', h1.id, 'plan-1', { inicio: it14.empezadaEn + 60_000 }),
      // Entre dos iteraciones (esperando la aprobación del plan): cuenta para la anterior.
      ejecucion('run-hueco', h1.id, 'plan-1', { inicio: it13.terminadaEn! + 1000 }),
      // Antes de que la hipótesis existiera (registro raro): nunca antes que ella.
      ejecucion('run-antes', h1.id, 'plan-1', { inicio: 0 }),
    ];
    h1.afirmaciones = [...h1.afirmaciones, derivada('run-14')];
    const g = construirArbol(e, inv);
    expect(g.porId.get('run-14')?.iteracion).toBe(14);
    expect(g.porId.get('run-hueco')?.iteracion).toBe(13);
    expect(g.porId.get('run-antes')?.iteracion).toBe(13);
    const af = g.nodos.find((n) => n.tipo === 'afirmacion' && g.enlaces.some((en) => en.de === n.id && en.a === 'run-14'));
    expect(af?.iteracion).toBe(14);
    // El conjunto de datos existe desde su primer análisis.
    expect(g.porId.get(`ds-${ds}`)?.iteracion).toBe(13);
    // Una afirmación con su propia iteración la conserva.
    h1.afirmaciones = [...h1.afirmaciones, derivada('run-14', { iteracion: 12, afirmacionId: 'af-propia' })];
    expect(construirArbol(e, inv).porId.get('af-af-propia')?.iteracion).toBe(12);
    // Sin iteraciones en el estado (registro antiguo): la de la hipótesis.
    const sinIteraciones = { ...e, iteraciones: [] };
    expect(construirArbol(sinIteraciones, inv).porId.get('run-14')?.iteracion).toBe(13);
    expect(g.iteracionMax).toBeGreaterThanOrEqual(14);
    // El resultado del laboratorio también se fecha por su llegada (hip-4 nació en la 3).
    const h4 = e.hipotesis.find((x) => x.id === 'hip-4')!;
    h4.experimento = { ...h4.experimento!, estado: 'datos_recibidos', resultado: { veredicto: 'refuta', resultado: '', motivo: '', limitaciones: '', cifras: [], exploratorio: '', fecha: it14.empezadaEn + 1000, fichero: null } };
    expect(construirArbol(e, inv).porId.get('lab-hip-4')?.iteracion).toBe(14);
    h4.experimento = { ...h4.experimento, resultado: { ...h4.experimento.resultado!, fecha: 0 } };
    expect(construirArbol(e, inv).porId.get('lab-hip-4')?.iteracion).toBe(h4.iteracion);
  });

  it('las entidades canónicas no tienen distancia al dato: no son evidencia ni literatura', () => {
    for (const t of ESTRUCTURA) expect(SIN_DISTANCIA.has(t)).toBe(true);
    expect(SIN_DISTANCIA.has('entidad')).toBe(true);
    expect(SIN_DISTANCIA.has('hipotesis') || SIN_DISTANCIA.has('fuente') || SIN_DISTANCIA.has('hecho')).toBe(false);
  });

  it('textos generados en castellano con tildes: la rama dice "hipótesis"', () => {
    const { e, inv, h1 } = base();
    // La muestra no tiene dos hipótesis en el mismo cluster: se fuerza una rama.
    e.hipotesis.find((x) => x.id === 'hip-2')!.cluster = h1.cluster;
    const g = construirArbol(e, inv);
    const ramas = g.nodos.filter((n) => n.tipo === 'rama');
    expect(ramas.length).toBeGreaterThan(0);
    for (const r of ramas) expect(r.sub).toMatch(/^\d+ hipótesis$/);
  });

  it('una fuente leída por una hipótesis cuenta como leída para las demás que la citan', () => {
    const { e, inv, h1 } = base();
    const h3 = e.hipotesis.find((x) => x.id === 'hip-3')!;
    const f = h1.procedencia.fuentes[0]!;
    h1.procedencia.fuentes = h1.procedencia.fuentes.map((x) => ({ ...x, textoCompleto: false, fragmento: '' }));
    h3.procedencia.fuentes = [...h3.procedencia.fuentes, { ...f, textoCompleto: false, fragmento: 'Un pasaje leído.' }];
    const g = construirArbol(e, inv);
    expect(g.porId.get(`fu-${f.id}`)?.profundidadLiteratura).toBe(0);
    expect(g.porId.get(h1.id)?.profundidadLiteratura).toBe(1);
  });

  it('un veredicto desconocido y un texto en inglés se enseñan tal cual, sin contar como medición', () => {
    const { e, inv, h1 } = base();
    h1.afirmaciones = [...h1.afirmaciones, derivada('run-x', { texto: 'Plasma GFAP rose before NfL in 31 of 40 APOE4 carriers of the open cohort.', veredicto: 'Supported' as Afirmacion['veredicto'], afirmacionId: 'obs-en' })];
    const g = construirArbol(e, inv);
    const n = g.porId.get('af-obs-en')!;
    expect(n.sub).toBe('dato · Supported');
    expect(n.medicion).toBeUndefined();
    expect(n.etiqueta.length).toBeLessThanOrEqual(60);
    expect(n.profundidadDato).toBeNull();
  });

  it('miles de afirmaciones y de análisis se construyen en tiempo lineal', () => {
    const { e, inv, h1 } = base();
    const H = 1500;
    const ds = inv.datasets.map((d) => d.id);
    const hip: Hipotesis[] = [];
    const runs: Ejecucion[] = [];
    const planes: PlanAnalisis[] = [];
    for (let i = 0; i < H; i++) {
      const id = `hip-m-${i}`;
      const afirmaciones: Afirmacion[] = [];
      const ids: string[] = [];
      for (let k = 0; k < 3; k++) {
        const runId = `run-m-${i}-${k}`;
        const planId = `plan-m-${i}-${k}`;
        runs.push(ejecucion(runId, id, planId, { inicio: 1 + i }));
        planes.push(plan(planId, id, ds[(i + k) % ds.length]!));
        ids.push(runId);
        afirmaciones.push(derivada(runId, { afirmacionId: `obs-${i}-${k}` }), derivada(runId, { afirmacionId: `obs-${i}-${k}-b`, clase: 'observacion_original' }));
      }
      hip.push({ ...clon(h1), id, titulo: `Hipótesis masiva ${i}`, cluster: `Cluster ${i % 12}`, partidos: [], entidades: [], grafoCausal: null, ejecuciones: ids, afirmaciones });
    }
    const grande = { ...e, hipotesis: hip, ejecuciones: runs, planesAnalisis: planes };
    const t0 = performance.now();
    const g = construirArbol(grande, inv);
    const ms = performance.now() - t0;
    console.log(`árbol con ${g.nodos.length} nodos y ${g.enlaces.length} enlaces en ${ms.toFixed(0)} ms`);
    expect(g.nodos.filter((n) => n.tipo === 'afirmacion').length).toBe(H * 6);
    expect(g.nodos.filter((n) => n.tipo === 'ejecucion').length).toBe(H * 3);
    expect(g.nodos.filter((n) => n.tipo === 'dataset').length).toBe(ds.length);
    for (const h of hip) expect(g.porId.get(h.id)?.profundidadDato).toBe(1);
    expect(ms).toBeLessThan(2500);
  });
});
