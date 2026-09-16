// @vitest-environment jsdom
// La tarjeta "Aprendizaje" montada de verdad: sin cifras (registro antiguo o
// primera iteración sin cerrar), con las tres tasas en null (nunca "0 %"),
// con datos completos, y con un registro roto (detalle como texto, glosario
// en null, texto vacío). Mismo patrón que FranjaRanking.test.tsx: createRoot
// y act, sin testing-library.
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { CifrasAprendizaje as Cifras } from '../datos/tipos';
import { CifrasAprendizaje, GLOSARIO_CIFRAS, conGlosario, textoHoras, textoTasa } from './CifrasAprendizaje';

const SIN_TILDE = /\b(hipotesis|iteracion|todavia|decision|prerregistro con direccion|analisis|Todavia|Iteracion|Analisis|calculo|Calculo|priorizacion|auditoria)\b/;

let root: Root;
let nodo: HTMLDivElement;
beforeEach(() => {
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  nodo = document.createElement('div');
  document.body.append(nodo);
  root = createRoot(nodo);
});
afterEach(async () => {
  await act(async () => root.unmount());
  nodo.remove();
});

const titulos = () => [...nodo.querySelectorAll('[title]')].map((c) => c.getAttribute('title') ?? '');
const todoElTexto = () => [nodo.textContent ?? '', ...titulos()].join('\n');

const REGLA_A = 'Un caso es un plan congelado con ejecución válida e interpretada, o un experimento prerregistrado con resultado.';
const REGLA_T = 'Horas desde creadaEn de la hipótesis hasta la primera decisión registrada de cada etapa.';
const REGLA_R = 'Heredado: id con el sufijo de la investigación de destino.';

function vacias(): Cifras {
  const agregado = { casos: 0, conDireccion: 0, aciertos: 0, tasa: null, sinDireccion: 0, noEvaluables: 0 };
  return {
    investigacionId: 'inv-1',
    fecha: 1000,
    acierto: { ...agregado, porFuente: { analisis: { ...agregado }, laboratorio: { ...agregado } }, porNivel: {}, excluidos: { planesSinCongelar: 0, planesSinEjecucionValida: 0, planesReproduccion: 0, laboratorioSinPrerregistro: 0 }, detalle: [], regla: REGLA_A },
    tiempo: { casos: 0, hipotesis: 0, medianaHoras: null, p90Horas: null, porEtapa: {}, abiertasSinDecision: 0, abiertasSinDecisionHoras: null, sinFechaCreacion: 0, decisionesSinFecha: 0, fechasInvertidas: 0, detalle: [], regla: REGLA_T },
    reutilizacion: { hechosHeredados: 0, usados: 0, tasa: null, hipotesisConHerencia: 0, hipotesisVivas: 0, detalle: [], regla: REGLA_R },
    glosario: { prerregistro: 'lo que Rosa deja por escrito antes de mirar los datos', acierto: "el resultado cayó del lado que el prerregistro llamó 'confirma'", decision: 'cada juicio registrado', mediana: 'el valor del medio', p90: 'el valor por debajo del cual queda el 90 % de los casos', hecho_heredado: 'un hecho copiado de otra investigación' },
    texto: 'Todavía no hay predicciones prerregistradas (lo que Rosa dejó escrito que esperaba ver antes de mirar los datos) con dirección y resultado evaluable: el acierto no se puede medir.\nNinguna hipótesis tiene todavía una decisión registrada, así que el tiempo hasta decidir no se puede medir.\nEsta investigación no heredó hechos de otra, así que la reutilización no aplica.',
    iteracion: 1,
  };
}

function conDatos(): Cifras {
  const c = vacias();
  c.acierto = {
    ...c.acierto,
    casos: 5,
    conDireccion: 4,
    aciertos: 3,
    tasa: 0.75,
    sinDireccion: 1,
    noEvaluables: 0,
    porFuente: { analisis: { casos: 3, conDireccion: 3, aciertos: 2, tasa: 0.667, sinDireccion: 0, noEvaluables: 0 }, laboratorio: { casos: 2, conDireccion: 1, aciertos: 1, tasa: 1, sinDireccion: 1, noEvaluables: 0 } },
    porNivel: { muy_baja: { casos: 3, aciertos: 2 }, baja: { casos: 1, aciertos: 1 } },
    excluidos: { planesSinCongelar: 2, planesSinEjecucionValida: 0, planesReproduccion: 1, laboratorioSinPrerregistro: 0 },
    detalle: [
      { fuente: 'analisis', hipotesisId: 'hip-1', planId: 'plan-1', ejecucionId: 'ej-1', hashPlan: 'abc', direccionEsperada: 'GFAP mayor en amiloide positivos', resultado: 'efecto_detectado', nivel: 'muy_baja', prerregistradoEn: 1, resultadoEn: 2, clase: 'acierto', motivo: 'efecto detectado con dirección declarada' },
      { fuente: 'laboratorio', hipotesisId: 'hip-2', planId: null, ejecucionId: null, hashPlan: null, direccionEsperada: 'sin diferencia entre grupos', resultado: 'confirma', nivel: 'baja', prerregistradoEn: 1, resultadoEn: 2, clase: 'fallo', motivo: 'predecía ausencia de efecto y se detectó uno' },
    ],
  };
  c.tiempo = { ...c.tiempo, casos: 6, hipotesis: 4, medianaHoras: 30.4, p90Horas: 120, porEtapa: { killer_1: { casos: 4, medianaHoras: 0.5 }, priorizacion: { casos: 2, medianaHoras: 72 } }, abiertasSinDecision: 1, abiertasSinDecisionHoras: 200, fechasInvertidas: 1, detalle: [{ hipotesisId: 'hip-1', etapa: 'killer_1', horas: 0.5, creadaEn: 1, decididaEn: 2 } as unknown as Cifras['tiempo']['detalle'][number]] };
  c.reutilizacion = { ...c.reutilizacion, hechosHeredados: 4, usados: 1, tasa: 0.25, hipotesisConHerencia: 1, hipotesisVivas: 3, detalle: [{ hechoId: 'he-1-inv-1', estado: 'sabido', tema: 'GFAP sube antes que NfL', usadoPor: ['hip-1'], motivo: 'comparte la afirmación af-3 con hip-1' }, { hechoId: 'he-2-inv-1', estado: 'sabido', tema: null, usadoPor: [], motivo: 'ninguna hipótesis viva lo nombra' }] };
  c.texto = 'De 4 predicciones prerregistradas con dirección, 3 acertaron (75 %).\nDesde que nace una hipótesis hasta su primera decisión pasan 30 h de mediana y 120 h en el 90 % de los casos.\nDe 4 hechos heredados, 1 se usó (25 %).';
  c.iteracion = 7;
  return c;
}

describe('CifrasAprendizaje', () => {
  it('sin cifras dice cuándo se calculan, sin inventar números', async () => {
    await act(async () => root.render(<CifrasAprendizaje cifras={null} />));
    expect(nodo.textContent).toContain('Aprendizaje');
    expect(nodo.textContent).toContain('Se calcula al cerrar la primera iteración');
    expect(nodo.textContent).not.toContain('%');
    await act(async () => root.render(<CifrasAprendizaje cifras={undefined} />));
    expect(nodo.textContent).toContain('Se calcula al cerrar la primera iteración');
    expect(todoElTexto()).not.toContain('\u2014');
    expect(todoElTexto()).not.toMatch(SIN_TILDE);
  });

  it('con las tres tasas en null dice "todavía no se puede medir" y nunca 0 %', async () => {
    await act(async () => root.render(<CifrasAprendizaje cifras={vacias()} />));
    const texto = nodo.textContent ?? '';
    // El texto en llano va primero, antes que las cifras.
    expect(texto.indexOf('Todavía no hay predicciones prerregistradas')).toBeLessThan(texto.indexOf('Acierto prerregistrado'));
    expect(texto).toContain('Calculado al cerrar la iteración 1');
    const valores = [...nodo.querySelectorAll('.cifra-ap-valor')].map((e) => e.textContent);
    expect(valores).toEqual(['todavía no se puede medir', 'todavía no se puede medir', 'no aplica']);
    expect(texto).not.toMatch(/0\s?%/);
    expect(texto).not.toContain('NaN');
    // La regla queda plegada dentro de un details y está.
    expect(nodo.querySelectorAll('details.cifra-ap-detalle').length).toBe(3);
    expect(texto).toContain(REGLA_A);
    // El glosario explica en tooltip los términos del texto, una vez cada uno.
    const t = titulos();
    expect(t.some((x) => x.includes('lo que Rosa deja por escrito antes de mirar los datos'))).toBe(true);
    expect(nodo.querySelectorAll('.termino-glosario').length).toBeGreaterThanOrEqual(2);
    expect(todoElTexto()).not.toContain('\u2014');
    expect(todoElTexto()).not.toMatch(SIN_TILDE);
  });

  it('con datos pinta las tres cifras con su detalle, los casos y las etapas', async () => {
    await act(async () => root.render(<CifrasAprendizaje cifras={conDatos()} />));
    const texto = nodo.textContent ?? '';
    const valores = [...nodo.querySelectorAll('.cifra-ap-valor')].map((e) => e.textContent);
    expect(valores).toEqual(['75 %', '30,4 h de mediana', '25 %']);
    expect(texto).toContain('Calculado al cerrar la iteración 7');
    expect(texto).toContain('3 aciertos de 4 predicciones con dirección');
    expect(texto).toContain('1 sin dirección declarada');
    expect(texto).toContain('p90 5 días');
    expect(texto).toContain('Killer 1 (antes de gastar)');
    expect(texto).toContain('análisis in silico 67 % (3 casos); laboratorio 100 % (2 casos)');
    expect(texto).toContain('certeza muy baja 2 de 3');
    expect(texto).toContain('2 planes sin congelar');
    expect(texto).toContain('1 decisiones anteriores a la creación');
    // Casos: acierto y fallo con su motivo; reutilización: usado y sin usar.
    const chips = [...nodo.querySelectorAll('.cifra-ap-casos .chip')].map((c) => c.textContent);
    expect(chips).toEqual(['Acierto', 'Fallo', 'Usado', 'Sin usar']);
    expect(texto).toContain('predecía ausencia de efecto y se detectó uno');
    expect(texto).toContain('GFAP sube antes que NfL');
    expect(texto).toContain('1 hecho heredado usado de 4');
    expect(todoElTexto()).not.toContain('\u2014');
    expect(todoElTexto()).not.toMatch(SIN_TILDE);
  });

  it('con un registro roto no lanza: detalle como texto, glosario null, texto vacío, cifras a medias', async () => {
    const roto = {
      investigacionId: 'inv-1',
      fecha: 'ayer',
      acierto: { casos: 2, conDireccion: 1, aciertos: 1, tasa: 1, sinDireccion: 1, noEvaluables: 0, detalle: 'no es una lista', porNivel: null, porFuente: null, excluidos: null, regla: null },
      tiempo: { casos: 1, hipotesis: 1, medianaHoras: -5, p90Horas: 'x', porEtapa: 'nada', abiertasSinDecision: 0, detalle: null },
      reutilizacion: null,
      glosario: null,
      texto: '',
    } as unknown as Cifras;
    await act(async () => root.render(<CifrasAprendizaje cifras={roto} />));
    const texto = nodo.textContent ?? '';
    expect(texto).toContain('El servidor no escribió el texto en llano');
    const valores = [...nodo.querySelectorAll('.cifra-ap-valor')].map((e) => e.textContent);
    // Reutilización en null no se pinta; la mediana negativa no se cree.
    expect(valores).toEqual(['100 %', 'todavía no se puede medir']);
    expect(texto).not.toContain('NaN');
    expect(texto).not.toContain('undefined');
    // Un objeto que no es un objeto se trata como ausencia.
    await act(async () => root.render(<CifrasAprendizaje cifras={'texto' as unknown as Cifras} />));
    expect(nodo.textContent).toContain('Se calcula al cerrar la primera iteración');
  });
});

describe('ayudas de las cifras', () => {
  it('textoTasa nunca devuelve 0 % para null, undefined ni NaN', () => {
    expect(textoTasa(null)).toBe('todavía no se puede medir');
    expect(textoTasa(undefined)).toBe('todavía no se puede medir');
    expect(textoTasa(Number.NaN)).toBe('todavía no se puede medir');
    expect(textoTasa(0)).toBe('0 %');
    expect(textoTasa(0.333)).toBe('33 %');
  });

  it('textoHoras pasa de minutos a horas y a días con coma decimal', () => {
    expect(textoHoras(0.25)).toBe('15 min');
    expect(textoHoras(1)).toBe('1 h');
    expect(textoHoras(30.44)).toBe('30,4 h');
    expect(textoHoras(48)).toBe('2 días');
    expect(textoHoras(120)).toBe('5 días');
    expect(textoHoras(null)).toBe('todavía no se puede medir');
    expect(textoHoras(-1)).toBe('todavía no se puede medir');
  });

  it('conGlosario envuelve cada término una sola vez y respeta el resto del texto', () => {
    const partes = conGlosario('El prerregistro y otro prerregistro; la mediana.', { prerregistro: 'A', mediana: 'B' });
    const cadenas = partes.filter((p) => typeof p === 'string');
    const spans = partes.filter((p) => typeof p !== 'string');
    expect(spans.length).toBe(2);
    expect(cadenas.join('|')).toBe('El | y otro prerregistro; la |.');
    expect(conGlosario('', {})).toEqual([]);
    expect(conGlosario('sin términos', {})).toEqual(['sin términos']);
  });
});

describe('CifrasAprendizaje, adversario', () => {
  it('con detalles que traen null, texto o números dentro de la lista no lanza ni pinta undefined', async () => {
    const c = conDatos();
    c.acierto = { ...c.acierto, detalle: [null, 'texto', 7, c.acierto.detalle[0]!, { clase: 'acierto' }] as unknown as Cifras['acierto']['detalle'] };
    c.reutilizacion = { ...c.reutilizacion, detalle: [null, 'x', c.reutilizacion.detalle[0]!, { usadoPor: 'hip-1' }] as unknown as Cifras['reutilizacion']['detalle'] };
    c.tiempo = { ...c.tiempo, porEtapa: { killer_1: null, rara: 'texto', priorizacion: { casos: 2, medianaHoras: 72 } } as unknown as Cifras['tiempo']['porEtapa'] };
    await act(async () => root.render(<CifrasAprendizaje cifras={c} />));
    const texto = nodo.textContent ?? '';
    // Solo los casos con forma de objeto se pintan; los demás se saltan sin romper.
    expect([...nodo.querySelectorAll('.cifra-ap-casos .chip')].map((x) => x.textContent)).toEqual(['Acierto', 'Acierto', 'Usado', 'Sin usar']);
    expect(texto).toContain('predecía ausencia de efecto y se detectó uno'.slice(0, 0) + 'efecto detectado con dirección declarada');
    expect(texto).not.toContain('undefined');
    expect(texto).not.toContain('null');
    expect(texto).not.toContain('NaN');
    expect(texto).not.toContain('[object');
  });

  it('con un registro antiguo al que le faltan campos numéricos no escribe undefined ni cifras vacías', async () => {
    const c = vacias();
    c.acierto = { casos: 3, tasa: 0.5, detalle: [], regla: REGLA_A } as unknown as Cifras['acierto'];
    c.tiempo = { casos: 2, medianaHoras: 3, detalle: [], regla: REGLA_T } as unknown as Cifras['tiempo'];
    c.reutilizacion = { hechosHeredados: 3, tasa: null, detalle: [], regla: REGLA_R } as unknown as Cifras['reutilizacion'];
    await act(async () => root.render(<CifrasAprendizaje cifras={c} />));
    const texto = nodo.textContent ?? '';
    expect(texto).not.toContain('undefined');
    expect(texto).not.toContain('NaN');
    // Lo que falta se cuenta como 0, no como hueco en la frase.
    expect(texto).toContain('0 aciertos de 0 predicciones con dirección');
    expect(texto).toContain('0 hechos heredados usados de 3; 0 hipótesis vivas de 0 se apoyan en alguno');
    expect(texto).toContain('2 decisiones sobre 0 hipótesis');
    expect(texto).not.toMatch(/\s{2,}hipótesis|de\s+se apoyan|\s,\s/);
  });

  it('con acierto, tiempo y glosario de otro tipo no lanza y no pinta [object', async () => {
    const c = { ...vacias(), acierto: 'texto', tiempo: 5, reutilizacion: [], glosario: { prerregistro: { a: 1 }, mediana: 4 }, texto: 'El prerregistro y la mediana.\n\n\n' } as unknown as Cifras;
    await act(async () => root.render(<CifrasAprendizaje cifras={c} />));
    const todo = todoElTexto();
    expect(todo).not.toContain('[object');
    expect(todo).not.toContain('undefined');
    // El texto en llano sigue saliendo (una frase, sin párrafos vacíos).
    expect(nodo.querySelectorAll('.cifras-ap-texto p').length).toBe(1);
    // Un glosario con valores que no son texto no produce tooltips vacíos ni rotos.
    for (const t of titulos()) expect(t).not.toContain('[object');
  });

  it('conGlosario no se cuelga con texto largo y repetido y explica cada término una sola vez', () => {
    const largo = Array.from({ length: 400 }, () => 'prerregistro acierto decisión mediana p90 hecho heredado').join(' ');
    const partes = conGlosario(largo, GLOSARIO_CIFRAS);
    expect(partes.filter((p) => typeof p !== 'string').length).toBe(6);
    // Lo envuelto son exactamente los seis términos, una vez cada uno: 12 + 7 + 8 + 7 + 3 + 14 = 51 caracteres.
    expect(partes.filter((p) => typeof p === 'string').join('').length + 51).toBe(largo.length);
  });
});
