// @vitest-environment jsdom
// El registro de datasets del programa montado de verdad: sin registro
// (estado antiguo sin la clave), con registro pero ninguno usado en la
// investigación (botón para ver todos), con datasets usados (etiquetas con
// tilde, n, registro plegado), con acceso controlado y su nota, y con un
// registro roto (usadoEn como texto, n en null, registro como texto, fuente
// desconocida). Mismo patrón que FranjaRanking.test.tsx: createRoot y act.
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { DatasetPrograma } from '../datos/tipos';
import { DatasetsPrograma, ETIQUETA_ACCESO, ETIQUETA_FUENTE, ETIQUETA_TIPO, usadoEnInvestigacion } from './DatasetsPrograma';

const SIN_TILDE = /\b(investigacion|expresion|celula unica|proteomica|genetica|titulo|Titulo|celulas|publicos|analisis|informacion|Ningun|ningun|fichero subido por una persona sin|sin titulo|comite|acceso controlado exige)\b/;

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
const chips = (raiz: Element = nodo) => [...raiz.querySelectorAll('.chip')].map((c) => c.textContent ?? '');

function dataset(extra: Partial<DatasetPrograma>): DatasetPrograma {
  return {
    id: 'dsp-1',
    fuente: 'geo',
    accession: 'GSE1297',
    titulo: 'Alzheimer disease hippocampus: incipient, moderate and severe',
    organismo: 'Homo sapiens',
    tejido: 'cerebro',
    region: 'hipocampo',
    estadio: 'demencia leve, moderada o grave',
    tipo: 'bulk',
    n: { muestras: 31, donantes: null, celulas: null },
    plataforma: 'GPL96',
    procesado: 'matriz de expresión',
    acceso: 'abierto',
    licencia: '',
    url: 'https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE1297',
    fichero: null,
    muestrasCompartidasCon: [],
    usadoEn: ['inv-1'],
    registradoEn: 100,
    actualizadoEn: 200,
    registro: ['fuente GEO, serie GSE1297', "tipo bulk: la ficha dice 'expression profiling by array'", "región hipocampo: la ficha dice 'hippocampus'", 'acceso abierto: GEO no pide registro'],
    ...extra,
  };
}

const controlado = (): DatasetPrograma =>
  dataset({
    id: 'dsp-2',
    fuente: 'synapse',
    accession: 'syn3219045',
    titulo: 'ROSMAP RNA-seq de corteza prefrontal dorsolateral',
    region: 'corteza prefrontal',
    tipo: 'bulk',
    n: { muestras: 640, donantes: 638, celulas: null },
    acceso: 'controlado',
    url: '',
    usadoEn: [],
    registro: ["acceso controlado: la ficha dice 'data use agreement' y nombra ROSMAP"],
    actualizadoEn: 300,
  });

const celulaUnica = (): DatasetPrograma =>
  dataset({
    id: 'dsp-3',
    fuente: 'cellxgene',
    accession: 'sea-ad-mtg',
    titulo: 'SEA-AD: corteza temporal media, célula única',
    region: 'corteza temporal',
    estadio: 'todo el espectro',
    tipo: 'celula_unica',
    n: { muestras: null, donantes: 84, celulas: 1_378_211 },
    acceso: 'registro',
    muestrasCompartidasCon: ['GSE999'],
    usadoEn: ['inv-2'],
    registro: [],
    actualizadoEn: 250,
  });

describe('DatasetsPrograma', () => {
  it('sin registro (estado antiguo, undefined o null) dice que está vacío y no rompe', async () => {
    await act(async () => root.render(<DatasetsPrograma datasets={undefined} investigacionId="inv-1" />));
    expect(nodo.textContent).toContain('Datasets del programa');
    expect(nodo.textContent).toContain('El registro está vacío');
    expect(nodo.querySelector('button')).toBeNull();
    await act(async () => root.render(<DatasetsPrograma datasets={null} investigacionId="inv-1" />));
    expect(nodo.textContent).toContain('El registro está vacío');
    await act(async () => root.render(<DatasetsPrograma datasets={[]} investigacionId="inv-1" />));
    expect(nodo.textContent).toContain('El registro está vacío');
    expect(todoElTexto()).not.toContain('\u2014');
    expect(todoElTexto()).not.toMatch(SIN_TILDE);
  });

  it('filtra por la investigación y deja ver todo el registro con un botón', async () => {
    await act(async () => root.render(<DatasetsPrograma datasets={[dataset({}), controlado(), celulaUnica()]} investigacionId="inv-1" />));
    expect(nodo.querySelectorAll('.dsp-fila').length).toBe(1);
    expect(nodo.textContent).toContain('1 dataset usados en esta investigación');
    const boton = nodo.querySelector('button')!;
    expect(boton.textContent).toBe('Ver todo el registro (3)');
    await act(async () => boton.click());
    expect(nodo.querySelectorAll('.dsp-fila').length).toBe(3);
    expect(nodo.textContent).toContain('3 datasets en todo el programa; 1 de acceso controlado (el proyecto no lo pide)');
    expect(nodo.querySelector('button')!.textContent).toBe('Solo los de esta investigación (1)');
    // Orden: el más reciente primero.
    expect([...nodo.querySelectorAll('.dsp-accession')].map((a) => a.textContent)).toEqual(['syn3219045', 'sea-ad-mtg', 'GSE1297']);
    // Ninguno usado aquí: lo dice y ofrece el botón.
    await act(async () => root.render(<DatasetsPrograma key="otro" datasets={[controlado(), celulaUnica()]} investigacionId="inv-1" />));
    expect(nodo.textContent).toContain('Ninguna corrida de esta investigación ha usado todavía un dataset del registro');
    expect(nodo.querySelector('button')!.textContent).toBe('Ver todo el registro (2)');
  });

  it('cada fila lleva fuente, accession, título, tipo, tejido, fase, n y acceso con las etiquetas con tilde, y el registro plegado', async () => {
    await act(async () => root.render(<DatasetsPrograma datasets={[dataset({}), celulaUnica()]} investigacionId="inv-1" />));
    await act(async () => nodo.querySelector('button')!.click());
    const filas = [...nodo.querySelectorAll('.dsp-fila')];
    const geo = filas.find((f) => f.textContent?.includes('GSE1297'))!;
    expect(chips(geo)).toEqual(['GEO', 'abierto', 'usado aquí']);
    expect(geo.querySelector('a.dsp-accession')?.getAttribute('href')).toContain('GSE1297');
    expect(geo.textContent).toContain('Alzheimer disease hippocampus');
    expect(geo.textContent).toContain('expresión en tejido (bulk)');
    expect(geo.textContent).toContain('cerebro · hipocampo');
    expect(geo.textContent).toContain('demencia leve, moderada o grave');
    expect(geo.textContent).toContain('31 muestras');
    expect(geo.textContent).toContain('GPL96');
    expect(geo.className).toContain('dsp-usado');
    const registro = geo.querySelector('details.dsp-registro')!;
    expect(registro.querySelector('summary')?.textContent).toBe('Cómo se dedujo cada dato (4)');
    expect(registro.textContent).toContain("la ficha dice 'hippocampus'");
    // Célula única: etiquetas del tipo y del acceso con tilde, n con donantes y células con separador de miles, muestras compartidas, sin registro que plegar.
    const sc = filas.find((f) => f.textContent?.includes('sea-ad-mtg'))!;
    expect(chips(sc)).toEqual(['CELLxGENE', 'con registro', 'usado en 1 investigación']);
    expect(sc.textContent).toContain('célula única');
    expect(sc.textContent).toContain('84 donantes · 1.378.211 células');
    expect(sc.textContent).toContain('Comparte muestras con GSE999');
    expect(sc.querySelector('details')).toBeNull();
    expect(sc.querySelector('a.dsp-accession')).not.toBeNull();
    // Las definiciones van en title: fuente, acceso, tipo, n.
    const t = titulos().join('\n');
    expect(t).toContain('Gene Expression Omnibus');
    expect(t).toContain('Hace falta una cuenta gratuita');
    expect(todoElTexto()).not.toContain('\u2014');
    expect(todoElTexto()).not.toMatch(SIN_TILDE);
  });

  it('un dataset de acceso controlado lleva la nota "el proyecto no lo pide" y se marca en rojo', async () => {
    await act(async () => root.render(<DatasetsPrograma datasets={[controlado()]} investigacionId="inv-1" />));
    await act(async () => nodo.querySelector('button')!.click());
    const fila = nodo.querySelector('.dsp-fila')!;
    expect(fila.className).toContain('dsp-controlado');
    expect(chips(fila)).toEqual(['Synapse', 'controlado (el proyecto no lo pide)']);
    expect(fila.querySelector('.chip-mal')?.textContent).toBe('controlado (el proyecto no lo pide)');
    expect(fila.querySelector('.dsp-nota')?.textContent).toContain('Acceso controlado: el proyecto no lo pide');
    expect(fila.querySelector('.dsp-nota')?.textContent).toContain('no se propone para análisis con datos individuales');
    // Sin url no hay enlace, solo el accession en mono.
    expect(fila.querySelector('a.dsp-accession')).toBeNull();
    expect(fila.querySelector('span.dsp-accession')?.textContent).toBe('syn3219045');
    expect(fila.textContent).toContain('640 muestras · 638 donantes');
    expect(todoElTexto()).not.toContain('\u2014');
    expect(todoElTexto()).not.toMatch(SIN_TILDE);
  });

  it('con registros rotos no lanza: usadoEn como texto, n en null, registro como texto, fuente y tipo desconocidos, filas nulas', async () => {
    const rotos = [
      { id: 'r1', fuente: 'GEO', accession: 7, titulo: null, tipo: 'single_cell', acceso: 'publico', n: null, usadoEn: 'inv-1', registro: 'una sola línea de registro', muestrasCompartidasCon: null, actualizadoEn: 'ayer' },
      null,
      'texto',
      { id: null, fuente: 'geo', accession: '', titulo: '', tipo: 'bulk', acceso: 'abierto', n: { muestras: 'muchas', donantes: -3, celulas: 12 }, usadoEn: null, registro: [null, 3, 'línea válida'], url: 42 },
    ] as unknown as DatasetPrograma[];
    await act(async () => root.render(<DatasetsPrograma datasets={rotos} investigacionId="inv-1" />));
    // Solo el primero cuenta como usado aquí (usadoEn en texto).
    expect(nodo.querySelectorAll('.dsp-fila').length).toBe(1);
    const fila = nodo.querySelector('.dsp-fila')!;
    // "GEO" en mayúsculas es la misma clave que geo (como hace rosa/datasets_programa.py al completar registros
    // antiguos); un tipo fuera del vocabulario cae a otro y un acceso fuera del vocabulario dice "sin comprobar".
    expect(chips(fila)).toEqual([ETIQUETA_FUENTE.geo, ETIQUETA_ACCESO.desconocido, 'usado aquí']);
    expect(fila.textContent).toContain(ETIQUETA_TIPO.otro);
    expect(fila.textContent).toContain('sin título');
    expect(fila.querySelector('.dsp-accession')?.textContent).toBe('7');
    expect(fila.textContent).toContain('sin comprobar');
    expect(fila.querySelector('details summary')?.textContent).toBe('Cómo se dedujo cada dato (1)');
    // Ver todos: la segunda fila válida se pinta con n saneado y registro filtrado.
    await act(async () => nodo.querySelector('button')!.click());
    const filas = [...nodo.querySelectorAll('.dsp-fila')];
    expect(filas.length).toBe(2);
    const segunda = filas.find((f) => f.textContent?.includes('sin accession'))!;
    expect(segunda.textContent).toContain('12 células');
    expect(segunda.textContent).not.toContain('muchas');
    expect(segunda.querySelector('details summary')?.textContent).toBe('Cómo se dedujo cada dato (1)');
    expect(segunda.querySelector('a.dsp-accession')).toBeNull();
    expect(nodo.textContent).not.toContain('NaN');
    expect(nodo.textContent).not.toContain('undefined');
    expect(nodo.textContent).not.toContain('null');
  });
});

describe('usadoEnInvestigacion', () => {
  it('acepta lista o texto y rechaza lo demás', () => {
    expect(usadoEnInvestigacion(dataset({ usadoEn: ['inv-1', 'inv-2'] }), 'inv-2')).toBe(true);
    expect(usadoEnInvestigacion(dataset({ usadoEn: 'inv-1' as unknown as string[] }), 'inv-1')).toBe(true);
    expect(usadoEnInvestigacion(dataset({ usadoEn: null as unknown as string[] }), 'inv-1')).toBe(false);
    expect(usadoEnInvestigacion(dataset({ usadoEn: [] }), 'inv-1')).toBe(false);
  });
});

describe('DatasetsPrograma, adversario', () => {
  it('acceso, fuente y tipo con mayúsculas o espacios se reconocen: un controlado nunca pasa por "sin comprobar"', async () => {
    const d = { ...controlado(), acceso: ' CONTROLADO ' as unknown as DatasetPrograma['acceso'], fuente: 'Synapse' as unknown as DatasetPrograma['fuente'], tipo: 'Bulk ' as unknown as DatasetPrograma['tipo'], usadoEn: ['inv-1'] };
    await act(async () => root.render(<DatasetsPrograma datasets={[d]} investigacionId="inv-1" />));
    const fila = nodo.querySelector('.dsp-fila')!;
    expect(fila.className).toContain('dsp-controlado');
    expect(chips(fila)).toEqual(['Synapse', 'controlado (el proyecto no lo pide)', 'usado aquí']);
    expect(fila.textContent).toContain(ETIQUETA_TIPO.bulk);
    expect(fila.querySelector('.dsp-nota')?.textContent).toContain('el proyecto no lo pide');
    expect(nodo.querySelector('.dsp-resumen')?.textContent).toContain('1 de acceso controlado (el proyecto no lo pide)');
  });

  it('un registro antiguo con n como número o como texto numérico no pierde el dato', async () => {
    const rotos = [
      dataset({ id: 'a', n: 7 as unknown as DatasetPrograma['n'] }),
      dataset({ id: 'b', accession: 'GSE2', n: { muestras: '31', donantes: ' 12 ', celulas: 'muchas' } as unknown as DatasetPrograma['n'] }),
      dataset({ id: 'c', accession: 'GSE3', n: { muestras: 0, donantes: null, celulas: null } }),
    ];
    await act(async () => root.render(<DatasetsPrograma datasets={rotos} investigacionId="inv-1" />));
    const filas = [...nodo.querySelectorAll('.dsp-fila')].map((f) => f.textContent ?? '');
    expect(filas.find((t) => t.includes('GSE1297'))).toContain('7 muestras');
    expect(filas.find((t) => t.includes('GSE2'))).toContain('31 muestras · 12 donantes');
    expect(filas.find((t) => t.includes('GSE2'))).not.toContain('muchas');
    expect(filas.find((t) => t.includes('GSE3'))).toContain('0 muestras');
    expect(nodo.textContent).not.toContain('NaN');
  });

  it('con títulos, registro y compartidas de otro tipo no lanza ni pinta [object', async () => {
    const d = dataset({ titulo: { x: 1 } as unknown as string, registro: { a: 'b' } as unknown as string[], muestrasCompartidasCon: 'GSE9' as unknown as string[], tejido: 5 as unknown as string, estadio: null as unknown as string, organismo: ['x'] as unknown as string });
    await act(async () => root.render(<DatasetsPrograma datasets={[d]} investigacionId="inv-1" />));
    const todo = todoElTexto();
    expect(todo).not.toContain('[object');
    expect(todo).not.toContain('undefined');
    expect(nodo.textContent).toContain('sin título');
    expect(nodo.querySelector('details')).toBeNull();
  });

  it('un dataset con ids repetidos y sin id se pinta una vez por entrada sin romper', async () => {
    const lista = [dataset({}), dataset({}), dataset({ id: undefined as unknown as string, accession: 'GSE77' })];
    await act(async () => root.render(<DatasetsPrograma datasets={lista} investigacionId="inv-1" />));
    expect(nodo.querySelectorAll('.dsp-fila').length).toBe(3);
  });
});
