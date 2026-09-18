/** Hallazgo M-08, parte de estado, lado del navegador: los hechos repetidos se
 *  funden al heredar el modelo de mundo (`copiarHechos`, que usan crear con
 *  herencia y bifurcar). Los pares de `PARES_ESPEJO` son los mismos que prueba
 *  rosa/tests/test_tanda2_hechos.py: la regla da lo mismo en los dos lados. */
import { describe, expect, it } from 'vitest';
import { bifurcarInvestigacion, comparteReferencia, copiarHechos, crearInvestigacion, equivalenciaTextos, fundirHechos, fundirHechosRepetidos, guardasDeParafrasis, mismoHecho, negacionesDe, normalizarEnunciado, numerosDe, siglasDe } from './acciones';
import { AHORA_MUESTRA, estadoDeMuestra } from './muestra';
import type { HechoMundo, ProcedenciaHecho } from './tipos';

const T = AHORA_MUESTRA + 1000;
const INV = 'inv-1';

// [a, b, esperado]: 'identico', 'solape' (equivalentes por solape de tokens) o null.
const PARES_ESPEJO: [string, string, 'identico' | 'solape' | null][] = [
  ['GFAP sube antes que NfL en portadores', 'GFAP sube antes que NfL en portadores', 'identico'],
  ['El GFAP plasmático sube antes que el NfL en portadores de mutación.', 'GFAP plasmático sube antes que NfL en portadores de mutación', 'solape'],
  ['El GFAP plasmático sube antes que el NfL.', 'el gfap plasmático sube antes que el nfl', 'identico'],
  ['Aβ42 baja en LCR 15 años antes del inicio', 'Abeta42 baja en LCR 15 años antes del inicio', 'identico'],
  ['Sube GFAP antes que NfL en la cohorte', 'Sube NfL antes que GFAP en la cohorte', null],
  ['Chatterjee et al. señalan que el inicio joven implica poca copatología relacionada con la edad', 'Chatterjee et al. señalan que el inicio joven implica poca copatología relacionada con la edad en comparación', 'solape'],
  ['En Belder et al., el MMSE estuvo disponible en 231 de 270 visitas', 'En Belder et al., el MMSE estuvo disponible en 214 de 270 visitas', null],
  ['Johansson et al. señalan que el orden de las patologías medido mediante biomarcadores concuerda con la secuencia', 'Johansson et al. señalan que el orden de las patologías definido mediante biomarcadores concuerda con la secuencia', 'solape'],
  ['', 'algo que decir', null],
  ['GFAP y NfL suben en portadores', 'TREM2 y APOE4 actúan en sinergia en microglía', null],
];

type Proc = [string, string, number | null][];
const F1: Proc = [['f-1', 'Belder et al., 2026', 4]];
const F1_P7: Proc = [['f-1', 'Belder et al., 2026', 7]];
const F2_MISMA_OBRA: Proc = [['f-2', 'Belder et al., 2026', null]];
const F2_OTRA_OBRA: Proc = [['f-2', 'Johansson et al., 2023', 2]];
const GFAP_ELEVA = 'GFAP plasmático se eleva en portadores presintomáticos de mutación antes del inicio clínico estimado';
const GFAP_ELEVA_PARAFRASIS = 'El GFAP plasmático se eleva en los portadores presintomáticos de mutación antes del inicio clínico estimado';

// [a, procedencia de a, b, procedencia de b, esperado]: 'identico', 'solape', 'referencia' (vía del umbral 0,6) o null.
// Los mismos pares que rosa/tests/test_tanda2_hechos.py PARES_ESPEJO_HECHOS.
const PARES_ESPEJO_HECHOS: [string, Proc, string, Proc, 'identico' | 'solape' | 'referencia' | null][] = [
  [GFAP_ELEVA, F1, 'sTREM2 plasmático se eleva en portadores presintomáticos de mutación antes del inicio clínico estimado', [['f-2', 'Otro et al., 2024', 4]], null],
  ['GFAP sube en portadores en fase preclínica', F1, 'YKL40 sube en portadores en fase preclínica', F1, null],
  ['La cohorte incluyó portadores de PSEN1 con EYO negativo', F1, 'La cohorte incluyó portadores de APOE4 con EYO negativo', F1, null],
  ['El tratamiento redujo la carga amiloide en la cohorte tratada frente a placebo', F1, 'El tratamiento nunca redujo la carga amiloide en la cohorte tratada frente a placebo', F1, null],
  ['Treatment reduced amyloid burden in the treated cohort compared with placebo', F1, 'Treatment never reduced amyloid burden in the treated cohort compared with placebo', F1, null],
  ['Belder et al. excluyeron cuatro no portadores con EYO superior a los veinte años del análisis', F1, 'Belder et al. excluyeron seis no portadores con EYO superior a los veinte años del análisis', F1, null],
  [GFAP_ELEVA, F1, GFAP_ELEVA_PARAFRASIS, F2_OTRA_OBRA, null], // otra obra sin referencia común: una replicación vive aparte
  [GFAP_ELEVA, F1, GFAP_ELEVA_PARAFRASIS, F2_MISMA_OBRA, 'solape'], // la misma obra traída en otra corrida
  [GFAP_ELEVA, F1, GFAP_ELEVA_PARAFRASIS, F1_P7, 'solape'], // misma fuente, otra página
  ['GFAP sube antes que NfL en portadores', F1, 'GFAP sube antes que NfL en portadores', [['f-9', 'Chatterjee et al., 2025', 1]], 'identico'], // texto idéntico: venga de donde venga
  ['Qué orden siguen NfL y GFAP en la fase preclínica', [], '¿Qué orden siguen NfL y GFAP en fase preclínica?', [], 'solape'], // sin procedencia ninguno: no hay fuente que distinguir
  ['Qué orden siguen NfL y GFAP en la fase preclínica', F1, '¿Qué orden siguen NfL y GFAP en fase preclínica?', [], null], // uno con fuente y otro sin ella
  ['Belder et al. excluyeron cuatro no portadores con EYO superior a 20 años', F1, 'Belder et al. excluyeron cuatro no portadores con EYO superior a 20 años por falta de comparables', F1, 'referencia'],
  ['En Belder et al., el MMSE estuvo disponible en 231 de 270 visitas', F1, 'La cohorte de Belder et al. representó 38 variantes causantes de Alzheimer autosómico dominante', F1, null],
  ['Según Belder, el GFAP plasmático se eleva antes del inicio clínico en portadores de mutación', F1, 'Según los autores, el GFAP plasmático se eleva antes del inicio clínico en portadores de mutación', F1, 'solape'], // la mayúscula inicial no es una sigla
  [GFAP_ELEVA, [['f-1', 'Sin autor, 2023', 1]], GFAP_ELEVA_PARAFRASIS, [['f-2', 'Sin autor, 2023', 1]], null], // dos obras sin autor no son la misma obra
  [GFAP_ELEVA, [['f-1', 'Sin autor', 1]], GFAP_ELEVA_PARAFRASIS, [['f-1', 'Sin autor (alzforum.org)', 3]], 'solape'], // el mismo id de fuente sí
];

function procedencia(proc: Proc): ProcedenciaHecho[] {
  return proc.map(([fuenteId, referencia, pagina]) => ({ fuenteId, referencia, pagina }));
}

function hecho(id: string, enunciado: string, extra: Partial<HechoMundo> = {}): HechoMundo {
  return {
    id,
    investigacionId: INV,
    tipo: 'hecho',
    tema: 'Biomarcadores',
    enunciado,
    estado: 'sabido',
    origen: 'fuente',
    procedencia: [{ fuenteId: 'f-1', referencia: 'Belder et al., 2026', pagina: 4 }],
    motivoDescarte: null,
    actualizadoEn: T,
    prioridad: 5,
    citas: [],
    historial: [{ fecha: T, de: null, a: 'sabido', quien: 'Rosa', motivo: 'Añadido por ROSA2018' }],
    afirmacionIds: [],
    sustituyeA: [],
    sustituidoPor: null,
    resuelveA: [],
    contradiceA: [],
    cerradoEn: null,
    ...extra,
  };
}

describe('mismo hecho: la regla espejo de rosa/hechos.py', () => {
  it.each(PARES_ESPEJO)('equivalenciaTextos(%j, %j)', (a, b, esperado) => {
    const motivo = equivalenciaTextos(a, b);
    if (esperado === null) expect(motivo).toBeNull();
    else if (esperado === 'identico') expect(motivo).toBe('texto normalizado idéntico');
    else expect(motivo?.startsWith('solape de tokens')).toBe(true);
  });
  it('las tildes y la eñe no distinguen dos textos (la variante sin tildes se calcula aquí, no se escribe)', () => {
    const con = 'El GFAP plasmático sube antes que el NfL en portadores de mutación; 15 años después baja.';
    const sin = con.normalize('NFD').replace(/\p{M}/gu, '');
    expect(sin).not.toBe(con);
    expect(sin).toContain('mutacion');
    expect(equivalenciaTextos(con, sin)).toBe('texto normalizado idéntico');
  });
  it('normaliza como el servidor: minúsculas, sin tildes ni signos, letras griegas por su nombre', () => {
    expect(normalizarEnunciado('  El Aβ42 y la α-sinucleína, ¡en LCR!  ')).toBe('el abeta42 y la alfa sinucleina en lcr');
    expect(normalizarEnunciado('')).toBe('');
  });
  it('exige mismo tipo, estado e investigación, nunca funde entradas de hipótesis ni parejas enlazadas', () => {
    const a = hecho('he-a', 'GFAP sube antes que NfL en portadores');
    const b = hecho('he-b', 'GFAP sube antes que NfL en portadores');
    expect(mismoHecho(a, b)).toBe('texto normalizado idéntico');
    expect(mismoHecho(a, a)).toBeNull();
    expect(mismoHecho(a, { ...b, estado: 'descartado' })).toBeNull();
    expect(mismoHecho(a, { ...b, tipo: 'pregunta' })).toBeNull();
    expect(mismoHecho(a, { ...b, investigacionId: 'otra' })).toBeNull();
    expect(mismoHecho({ ...a, tipo: 'hipotesis' }, { ...b, tipo: 'hipotesis' })).toBeNull();
    expect(mismoHecho({ ...a, tipo: 'pregunta', estado: 'abierto' }, { ...b, tipo: 'pregunta', estado: 'abierto' })).toBe('texto normalizado idéntico');
    expect(mismoHecho({ ...a, sustituidoPor: 'he-b' }, { ...b, sustituyeA: ['he-a'] })).toBeNull();
    expect(mismoHecho(a, { ...b, contradiceA: ['he-a'] })).toBeNull();
  });
  it('una referencia común baja el umbral de solape a 0,6 pero sola no funde', () => {
    const a = hecho('he-a', 'Belder et al. excluyeron cuatro no portadores con EYO superior a 20 años');
    const b = hecho('he-b', 'Belder et al. excluyeron cuatro no portadores con EYO superior a 20 años por falta de comparables', { procedencia: [{ fuenteId: 'f-2', referencia: 'Belder', pagina: 4 }] });
    expect(mismoHecho(a, b)).toBeNull();
    const b2 = { ...b, procedencia: [{ fuenteId: 'f-1', referencia: 'Belder', pagina: 4 }] };
    expect(mismoHecho(a, b2)?.startsWith('misma referencia y solape de tokens')).toBe(true);
    // Misma fuente y página, hechos distintos: el n y el efecto de un mismo artículo.
    const c = hecho('he-c', 'En Belder et al., el MMSE estuvo disponible en 231 de 270 visitas');
    const d = hecho('he-d', 'La cohorte de Belder et al. representó 38 variantes causantes de Alzheimer autosómico dominante');
    expect(mismoHecho(c, d)).toBeNull();
    expect(mismoHecho({ ...c, afirmacionIds: ['af-1'] }, { ...d, afirmacionIds: ['af-1'] })).toBeNull();
    expect(mismoHecho(c, hecho('he-c2', 'En Belder et al., el MMSE estuvo disponible en 214 de 270 visitas'))).toBeNull();
  });
  it.each(PARES_ESPEJO_HECHOS)('mismoHecho con procedencia (%j, %j, %j, %j)', (a, pa, b, pb, esperado) => {
    const ha = hecho('he-a', a, { procedencia: procedencia(pa) });
    const hb = hecho('he-b', b, { procedencia: procedencia(pb), actualizadoEn: T + 1 });
    const motivo = mismoHecho(ha, hb);
    if (esperado === null) expect(motivo).toBeNull();
    else if (esperado === 'identico') expect(motivo).toBe('texto normalizado idéntico');
    else if (esperado === 'solape') expect(motivo?.startsWith('solape de tokens')).toBe(true);
    else expect(motivo?.startsWith('misma referencia y solape de tokens')).toBe(true);
    expect(mismoHecho(hb, ha) === null).toBe(motivo === null);
  });
  it('las guardas de paráfrasis nombran lo que distingue (la misma regla que rosa/hechos.py guardas_de_parafrasis)', () => {
    const a = hecho('he-a', GFAP_ELEVA, { procedencia: procedencia(F1) });
    expect(guardasDeParafrasis(a, hecho('he-b', GFAP_ELEVA_PARAFRASIS, { procedencia: procedencia(F2_OTRA_OBRA) }))).toBe('otra fuente sin referencia común: una replicación vive aparte');
    expect(guardasDeParafrasis(a, hecho('he-c', GFAP_ELEVA.replace('GFAP', 'sTREM2'), { procedencia: procedencia(F1) }))).toBe('siglas distintas');
    expect(guardasDeParafrasis(a, hecho('he-d', GFAP_ELEVA.replace('se eleva', 'nunca se eleva'), { procedencia: procedencia(F1) }))).toBe('una negación que el otro no tiene');
    expect(guardasDeParafrasis(a, hecho('he-e', `${GFAP_ELEVA} en dos cohortes`, { procedencia: procedencia(F1) }))).toBe('números distintos');
    expect(guardasDeParafrasis(a, hecho('he-f', GFAP_ELEVA_PARAFRASIS, { procedencia: procedencia(F2_MISMA_OBRA) }))).toBeNull();
    expect(guardasDeParafrasis(a, hecho('he-g', `${GFAP_ELEVA_PARAFRASIS} [Belder et al., 2026, pág. 4]`, { procedencia: procedencia(F1) }))).toBeNull();
  });
  it('números, siglas, negaciones y referencia compartida como en el servidor', () => {
    expect(numerosDe('Se excluyeron cuatro de 1.234,5 participantes, un 27 % del total en 2026')).toEqual(new Set(['cuatro', '1234.5', '27', '2026']));
    expect(numerosDe('')).toEqual(new Set());
    expect(siglasDe('La p-tau217 plasmática y el pTau217, Aβ42, NfL, sTREM2, APOE4, ApoE, CDR-SB, 18F-florbetapir, tau, MMSE')).toEqual(new Set(['ptau217', 'abeta42', 'nfl', 'strem2', 'apoe4', 'apoe', 'cdrsb', '18fflorbetapir', 'mmse']));
    expect(siglasDe('Belder et al. 2026 señalan que Los autores y Treatment')).toEqual(new Set());
    expect(siglasDe('GFAP en LCR según DIAN-OBS', new Set(['dian', 'obs']))).toEqual(new Set(['gfap', 'lcr']));
    expect(siglasDe('GFAP in CSF')).toEqual(new Set(['gfap', 'lcr']));
    expect(negacionesDe('El tratamiento nunca redujo, jamás, la carga; never neither')).toEqual(new Set(['nunca', 'jamas', 'never', 'neither']));
    expect(negacionesDe('no sube sin cambios')).toEqual(new Set());
    expect(comparteReferencia([{ fuenteId: 'f-1', referencia: 'Belder et al., 2026', pagina: 4 }], [{ fuenteId: 'f-2', referencia: 'belder et al. 2026', pagina: null }])).toBe(true);
    expect(comparteReferencia([{ fuenteId: 'f-1', referencia: 'A', pagina: 1 }], [{ fuenteId: 'f-2', referencia: 'B', pagina: 1 }])).toBe(false);
    expect(comparteReferencia([], [])).toBe(false);
    expect(comparteReferencia(null, [{ fuenteId: 'f', referencia: '', pagina: null }])).toBe(false);
    expect(comparteReferencia([{ fuenteId: 'f-1', referencia: 'Sin autor, 2023', pagina: 1 }], [{ fuenteId: 'f-2', referencia: 'Sin autor, 2023', pagina: 1 }])).toBe(false);
    expect(comparteReferencia([{ fuenteId: 'f-1', referencia: 'Sin autor', pagina: 1 }], [{ fuenteId: 'f-1', referencia: 'Sin autor (alzforum.org)', pagina: 3 }])).toBe(true);
  });
});

describe('fundir', () => {
  it('suma procedencia, afirmaciones, citas, entidades y enlaces, anota el historial y no toca los originales', () => {
    const a = hecho('he-a', 'GFAP sube antes que NfL', {
      afirmacionIds: ['af-1'],
      citas: [{ referencia: 'Belder et al., 2026', seccion: 'pág. 4', clasificacion: 'apoya', fragmento: 'x' }],
      entidades: [{ id: 'HGNC:4235', etiqueta: 'GFAP', ontologia: 'HGNC', tipo: 'gen', alias: [] }],
    });
    const b = hecho('he-b', 'GFAP sube antes que NfL', {
      procedencia: [{ fuenteId: 'f-2', referencia: 'Chatterjee et al., 2025', pagina: null }],
      afirmacionIds: ['af-1', 'af-2'],
      citas: [
        { referencia: 'Chatterjee et al., 2025', seccion: 'resumen', clasificacion: 'apoya', fragmento: 'y' },
        { referencia: 'Belder et al., 2026', seccion: 'pág. 4', clasificacion: 'apoya', fragmento: 'x repetido' },
      ],
      entidades: [
        { id: 'HGNC:4235', etiqueta: 'GFAP', ontologia: 'HGNC', tipo: 'gen', alias: ['gfap'] },
        { id: 'HGNC:7752', etiqueta: 'NEFL', ontologia: 'HGNC', tipo: 'gen', alias: [] },
      ],
      prioridad: 8,
      resuelveA: ['cu-1'],
      contradiceA: ['he-z', 'he-a'],
      actualizadoEn: T + 500,
    });
    const copiaA = JSON.parse(JSON.stringify(a));
    const copiaB = JSON.parse(JSON.stringify(b));
    const f = fundirHechos(a, b, T + 900, 'texto normalizado idéntico');
    expect(f.procedencia.map((p) => [p.fuenteId, p.pagina])).toEqual([['f-1', 4], ['f-2', null]]);
    expect(f.afirmacionIds).toEqual(['af-1', 'af-2']);
    expect(f.citas.map((c) => c.seccion)).toEqual(['pág. 4', 'resumen']);
    expect(f.entidades?.map((x) => x.id)).toEqual(['HGNC:4235', 'HGNC:7752']);
    expect(f.resuelveA).toEqual(['cu-1']);
    expect(f.contradiceA).toEqual(['he-z']);
    expect(f.prioridad).toBe(8);
    expect(f.actualizadoEn).toBe(T);
    const ultimo = f.historial.at(-1)!;
    expect(ultimo).toEqual({ fecha: T + 900, de: 'sabido', a: 'sabido', quien: 'Rosa', motivo: 'Fundido con he-b: «GFAP sube antes que NfL» (texto normalizado idéntico); se suman su procedencia y sus afirmaciones' });
    expect(a).toEqual(copiaA);
    expect(b).toEqual(copiaB);
  });
  it('fundirHechosRepetidos deja el más antiguo, remapea los enlaces y devuelve el mapa', () => {
    const a = hecho('he-a', 'GFAP sube antes que NfL en portadores');
    const b = hecho('he-b', 'El GFAP sube antes que el NfL en portadores', { procedencia: [{ fuenteId: 'f-2', referencia: 'Belder et al., 2026', pagina: null }] });
    const c = hecho('he-c', 'TREM2 R47H atenúa la respuesta microglial', { sustituyeA: ['he-b', 'he-fuera'], contradiceA: ['he-a'] });
    const d = hecho('he-d', 'GFAP sube antes que NfL en portadores', { procedencia: [{ fuenteId: 'f-3', referencia: 'Otra obra, 2020', pagina: 1 }], sustituidoPor: 'he-b' }); // texto idéntico: se funde venga de donde venga
    const r = fundirHechosRepetidos([a, b, c, d], T + 10);
    expect(r.hechos.map((h) => h.id)).toEqual(['he-a', 'he-c']);
    expect([...r.mapa.entries()]).toEqual([['he-b', 'he-a'], ['he-d', 'he-a']]);
    expect(r.hechos[0]!.procedencia.map((p) => p.fuenteId)).toEqual(['f-1', 'f-2', 'f-3']);
    expect(r.hechos[0]!.sustituidoPor).toBeNull();
    expect(r.hechos[1]!.sustituyeA).toEqual(['he-a', 'he-fuera']);
    expect(r.hechos[1]!.contradiceA).toEqual(['he-a']);
    expect(fundirHechosRepetidos([], T)).toEqual({ hechos: [], mapa: new Map() });
    // Una paráfrasis de otra obra, sin referencia común, no se funde: una replicación vive aparte.
    const e = hecho('he-e', 'El GFAP sube antes que el NfL en portadores', { procedencia: [{ fuenteId: 'f-7', referencia: 'Johansson et al., 2023', pagina: 2 }] });
    expect(fundirHechosRepetidos([a, e], T).hechos.map((h) => h.id)).toEqual(['he-a', 'he-e']);
  });
  it('un hecho antiguo con listas en null se funde como si estuvieran vacías', () => {
    const a = hecho('he-a', 'GFAP sube antes que NfL', { historial: null as unknown as HechoMundo['historial'], afirmacionIds: null as unknown as string[], citas: null as unknown as HechoMundo['citas'], procedencia: null as unknown as HechoMundo['procedencia'] });
    const b = hecho('he-b', 'GFAP sube antes que NfL', { procedencia: [{ fuenteId: 'f-2', referencia: 'Belder et al., 2026', pagina: null }], afirmacionIds: ['af-2'] });
    const f = fundirHechos(a, b, T + 9, 'texto normalizado idéntico');
    expect(f.procedencia.map((p) => p.fuenteId)).toEqual(['f-2']);
    expect(f.afirmacionIds).toEqual(['af-2']);
    expect(f.citas).toEqual([]);
    expect(f.historial).toHaveLength(1);
    expect(f.historial[0]!.fecha).toBe(T + 9);
    expect(fundirHechosRepetidos([a, b], T + 9).hechos.map((h) => h.id)).toEqual(['he-a']);
  });
});

describe('heredar y bifurcar funden los repetidos', () => {
  it('copiarHechos funde al copiar, remapea hacia el superviviente y no toca el origen', () => {
    const a = hecho('he-a', 'GFAP sube antes que NfL en portadores', { afirmacionIds: ['af-1'] });
    const b = hecho('he-b', 'El GFAP sube antes que el NfL en portadores', { procedencia: [{ fuenteId: 'f-2', referencia: 'Belder et al., 2026', pagina: null }], afirmacionIds: ['af-2'], actualizadoEn: T + 1 });
    const c = hecho('he-c', 'TREM2 R47H atenúa la respuesta microglial', { sustituyeA: ['he-b'] });
    const origen = [a, b, c];
    const antes = JSON.parse(JSON.stringify(origen));
    const copias = copiarHechos(origen, INV, 'inv-d', T + 100);
    expect(copias.map((h) => h.id)).toEqual(['he-a-inv-d', 'he-c-inv-d']);
    expect(copias[0]!.procedencia.map((p) => p.fuenteId)).toEqual(['f-1', 'f-2']);
    expect(copias[0]!.afirmacionIds).toEqual(['af-1', 'af-2']);
    expect(copias[0]!.historial.at(-1)!.fecha).toBe(T + 100);
    expect(copias[0]!.historial.at(-1)!.motivo).toContain('Fundido con he-b-inv-d');
    expect(copias[1]!.sustituyeA).toEqual(['he-a-inv-d']);
    expect(origen).toEqual(antes);
    // Sin `ahora`, la nota se fecha con el `actualizadoEn` más reciente de las copias.
    expect(copiarHechos(origen, INV, 'inv-e')[0]!.historial.at(-1)!.fecha).toBe(T + 1);
    expect(copiarHechos(origen, 'inv-vacia', 'inv-e')).toEqual([]);
  });
  it('crear con herencia y bifurcar pasan por la misma fusión', () => {
    const e0 = estadoDeMuestra();
    const repetido = hecho('he-rep', e0.hechos[0]!.enunciado, { procedencia: [{ fuenteId: 'f-9', referencia: 'Otra descarga', pagina: 2 }] });
    const e = { ...e0, hechos: [...e0.hechos, repetido] };
    const r = crearInvestigacion(e, { titulo: 'T', objetivo: 'O', relevancia: '', limites: [], condicionParada: 'P', revisores: [], heredarModeloDe: INV }, T);
    const heredados = r.estado.hechos.filter((h) => h.investigacionId === r.id);
    expect(heredados).toHaveLength(e0.hechos.length);
    const primero = heredados.find((h) => h.id === `${e0.hechos[0]!.id}-${r.id}`)!;
    expect(primero.procedencia.some((p) => p.fuenteId === 'f-9')).toBe(true);
    expect(primero.historial.at(-1)!.fecha).toBe(T);
    const rama = bifurcarInvestigacion(e, INV, 'rama', T + 5);
    const enRama = rama.estado.hechos.filter((h) => h.investigacionId === rama.id);
    expect(enRama).toHaveLength(e0.hechos.length);
    expect(new Set(rama.estado.hechos.map((h) => h.id)).size).toBe(rama.estado.hechos.length);
    // El origen conserva sus hechos, el repetido incluido.
    expect(rama.estado.hechos.filter((h) => h.investigacionId === INV)).toHaveLength(e.hechos.length);
  });
});
