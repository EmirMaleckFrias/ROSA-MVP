// @vitest-environment jsdom
// El mapa de la enfermedad montado de verdad: sin mapa (registro antiguo),
// con el mapa vacío que devuelve el servidor antes de reunir evidencia (un
// hueco por la fase de la misión), con celdas, huecos y avisos, y con un mapa
// roto. La rejilla va plegada en modo sencillo (SoloDetalle) y se abre con
// "Ver detalle" o en modo detalle. Mismo patrón que FranjaRanking.test.tsx.
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { MapaEnfermedad as Mapa } from '../datos/tipos';
import { fijarModo } from '../lib/modo';
import { ETIQUETAS_MAPA, MapaEnfermedad, etiquetaEje } from './MapaEnfermedad';

const SIN_TILDE = /\b(hipotesis|iteracion|todavia|Todavia|Iteracion|region|Region|celula|mision|preclinica|prodromica|microglia|hipocampo sin|liquido|cefalorraquideo|biologico|raton)\b/;

let root: Root;
let nodo: HTMLDivElement;
beforeEach(() => {
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  fijarModo('sencillo');
  nodo = document.createElement('div');
  document.body.append(nodo);
  root = createRoot(nodo);
});
afterEach(async () => {
  await act(async () => root.unmount());
  nodo.remove();
  fijarModo('sencillo');
});

const titulos = () => [...nodo.querySelectorAll('[title]')].map((c) => c.getAttribute('title') ?? '');
const todoElTexto = () => [nodo.textContent ?? '', ...titulos()].join('\n');

/** Lo que devuelve rosa/mapa_enfermedad.py mapa con una misión en fase
 *  preclínica y sin hechos ni hipótesis (copiado de una ejecución real). */
function vacio(): Mapa {
  return {
    ejes: { estadio: {}, region: {}, tipoCelular: {}, nivel: {} },
    celdas: [],
    huecos: [{ estadio: 'preclinica', region: null, tipoCelular: null, motivo: 'La misión nombra «preclínica» y ningún hecho ni hipótesis lo sitúa por su propio contenido.', heredanDeMision: 0 }],
    sinEjes: 0,
    hipotesisSinEjes: 0,
    heredados: 0,
    mision: { estadio: 'preclinica', estadios: ['preclinica'], region: [], tipoCelular: [], motivos: { estadio: 'misión (etapa): palabra de fase preclínica: «preclínica»', estadios: { preclinica: 'misión (etapa)' }, region: {}, tipoCelular: {} } },
    resumen: 'Todavía no hay hechos ni hipótesis que situar en el mapa de la enfermedad. Huecos de la misión sin cubrir: 1 (preclínica).',
  };
}

function conDatos(): Mapa {
  return {
    ejes: { estadio: { preclinica: 5, prodromica_dcl: 2 }, region: { plasma: 4, hipocampo: 3 }, tipoCelular: { astrocito: 4 }, nivel: { molecular: 6, clinico: 1 } },
    celdas: [
      { estadio: 'preclinica', region: 'plasma', tipoCelular: 'astrocito', hechos: ['he-1', 'he-2', 'he-3'], hipotesis: ['hip-1', 'hip-2'], preguntas: ['pr-1'], certezaMax: 'baja', certezaMotivo: 'la mayor entre hip-1 (baja) y hip-2 (muy baja)', cohortes: ['BioFINDER', 'ALFA+'], porMision: 1 },
      { estadio: 'preclinica', region: 'hipocampo', tipoCelular: null, hechos: ['he-4'], hipotesis: [], preguntas: [], certezaMax: null, certezaMotivo: 'sin hipótesis con conclusión', cohortes: [], porMision: 0 },
      { estadio: 'prodromica_dcl', region: 'hipocampo', tipoCelular: 'microglia', hechos: ['he-5', 'he-6'], hipotesis: ['hip-3'], preguntas: [], certezaMax: 'moderada', certezaMotivo: 'hip-3', cohortes: ['BioFINDER-2'], porMision: 0 },
      { estadio: null, region: null, tipoCelular: 'neurona', hechos: ['he-7'], hipotesis: [], preguntas: [], certezaMax: null, certezaMotivo: '', cohortes: [], porMision: 0 },
    ],
    huecos: [
      { estadio: 'preclinica', region: 'corteza_entorrinal', tipoCelular: null, motivo: 'La misión nombra «corteza entorrinal» y nada lo cubre.', heredanDeMision: 2 },
      { estadio: 'preclinica', region: 'plasma', tipoCelular: 'microglia', motivo: 'La misión nombra «microglía» y nada la sitúa en plasma.', heredanDeMision: 0 },
    ],
    sinEjes: 3,
    hipotesisSinEjes: 1,
    heredados: 2,
    mision: { estadio: 'preclinica', estadios: ['preclinica'], region: ['corteza_entorrinal', 'plasma'], tipoCelular: ['astrocito', 'microglia'], motivos: { estadio: 'misión', estadios: {}, region: {}, tipoCelular: {} } },
    resumen: 'La evidencia se concentra en la fase preclínica y en sangre (astrocitos). Huecos de la misión sin cubrir: 2.',
    fecha: 10,
    iteracion: 4,
    etiquetas: { ...ETIQUETAS_MAPA, region: { ...ETIQUETAS_MAPA.region, plasma: 'sangre (plasma y suero)' } },
    definiciones: { estadio: { preclinica: 'biomarcadores alterados sin síntomas cognitivos', prodromica_dcl: 'deterioro cognitivo leve, síntomas sin demencia' }, nivel: { molecular: 'genes, proteínas, biomarcadores y metabolitos', clinico: 'pacientes, cognición, escalas, diagnóstico y ensayos' } },
  };
}

const verDetalle = async () => {
  const boton = [...nodo.querySelectorAll('button')].find((b) => b.textContent === 'Ver detalle');
  expect(boton).toBeDefined();
  await act(async () => boton!.click());
};

describe('MapaEnfermedad', () => {
  it('sin mapa dice cuándo se calcula', async () => {
    await act(async () => root.render(<MapaEnfermedad mapa={null} />));
    expect(nodo.textContent).toContain('Mapa de la enfermedad');
    expect(nodo.textContent).toContain('Se calcula al cerrar la primera iteración');
    await act(async () => root.render(<MapaEnfermedad mapa={undefined} />));
    expect(nodo.textContent).toContain('Se calcula al cerrar la primera iteración');
    expect(todoElTexto()).not.toContain('\u2014');
    expect(todoElTexto()).not.toMatch(SIN_TILDE);
  });

  it('con el mapa vacío del servidor muestra el resumen, el hueco de la misión con su motivo y no inventa rejilla', async () => {
    await act(async () => root.render(<MapaEnfermedad mapa={vacio()} />));
    const texto = nodo.textContent ?? '';
    expect(texto).toContain('Todavía no hay hechos ni hipótesis que situar');
    expect(texto).toContain('Huecos de la misión sin cubrir (1)');
    expect(texto).toContain('La misión nombra «preclínica»');
    // El chip del hueco usa la etiqueta de reserva con tilde, no la clave.
    expect(nodo.querySelector('.mapa-enf-hueco .chip')?.textContent).toBe('preclínica');
    expect(texto).not.toContain('preclinica');
    // Plegado: en modo sencillo la rejilla no está; con la fase de la misión y el hueco sí hay rejilla al abrir.
    expect(nodo.querySelector('table')).toBeNull();
    await verDetalle();
    const tabla = nodo.querySelector('table.mapa-enf-rejilla');
    expect(tabla).not.toBeNull();
    expect(tabla!.querySelector('tbody th')?.textContent).toBe('preclínica');
    expect(tabla!.querySelector('tbody th')?.getAttribute('title')).toBe('biomarcadores alterados sin síntomas cognitivos');
    expect(tabla!.querySelector('td.mapa-enf-celda-hueco')).not.toBeNull();
    expect(nodo.querySelector('.mapa-enf-aviso')).toBeNull();
    expect(todoElTexto()).not.toContain('\u2014');
    expect(todoElTexto()).not.toMatch(SIN_TILDE);
  });

  it('con celdas pinta el resumen primero, el aviso de lo no situado, los huecos y la rejilla con fichas y color GRADE', async () => {
    fijarModo('detalle');
    await act(async () => root.render(<MapaEnfermedad mapa={conDatos()} />));
    const texto = nodo.textContent ?? '';
    expect(texto.indexOf('La evidencia se concentra')).toBeLessThan(texto.indexOf('Huecos de la misión'));
    expect(texto).toContain('Calculado al cerrar la iteración 4');
    expect(nodo.querySelector('.mapa-enf-aviso')?.textContent).toContain('3 hechos y 1 hipótesis no se pudieron situar');
    // Con uno solo, el aviso concuerda en singular.
    await act(async () => root.render(<MapaEnfermedad mapa={{ ...conDatos(), sinEjes: 1, hipotesisSinEjes: 0 }} />));
    expect(nodo.querySelector('.mapa-enf-aviso')?.textContent).toContain('1 hecho no se pudo situar en ningún eje');
    await act(async () => root.render(<MapaEnfermedad mapa={conDatos()} />));
    // Huecos: etiqueta visible (la que trae el mapa manda) y motivo, con los que heredan de la misión.
    const huecos = [...nodo.querySelectorAll('.mapa-enf-hueco')];
    expect(huecos.length).toBe(2);
    expect(huecos[0]!.querySelector('.chip')?.textContent).toBe('preclínica · corteza entorrinal');
    expect(huecos[0]!.textContent).toContain('2 registros la heredan de la misión');
    expect(huecos[1]!.querySelector('.chip')?.textContent).toBe('preclínica · sangre (plasma y suero) · microglía');
    // Niveles con su definición en tooltip.
    expect(nodo.querySelector('.mapa-enf-niveles')?.textContent).toContain('molecular 6');
    expect(titulos()).toContain('genes, proteínas, biomarcadores y metabolitos');
    // Rejilla en modo detalle sin pulsar nada: filas por fase en orden y la fila "sin situar" al final; columnas por región y "sin situar" al final.
    const tabla = nodo.querySelector('table.mapa-enf-rejilla')!;
    expect(tabla).not.toBeNull();
    const filas = [...tabla.querySelectorAll('tbody th')].map((t) => t.textContent);
    expect(filas).toEqual(['preclínica', 'prodrómica o DCL', 'sin situar']);
    const columnas = [...tabla.querySelectorAll('thead th')].slice(1).map((t) => t.textContent);
    expect(columnas).toEqual(['sangre (plasma y suero)', 'hipocampo', 'corteza entorrinal', 'sin situar']);
    // Celda preclínica x plasma: ficha de astrocito con 3 hechos, 2 hipótesis y certeza baja (tono aviso), más el hueco de microglía.
    const celdaPlasma = tabla.querySelectorAll('tbody tr')[0]!.querySelectorAll('td')[0]!;
    const ficha = celdaPlasma.querySelector('.mapa-enf-ficha')!;
    expect(ficha.textContent).toContain('astrocito');
    expect(ficha.textContent).toContain('3 h · 2 hip');
    expect(ficha.querySelector('.chip')?.textContent).toBe('baja');
    expect(ficha.className).toContain('mapa-enf-certeza-aviso');
    expect(ficha.getAttribute('title')).toContain('3 hechos, 2 hipótesis, 1 pregunta abierta');
    expect(ficha.getAttribute('title')).toContain('Cohortes: BioFINDER, ALFA+');
    expect(ficha.getAttribute('title')).toContain('1 situados aquí solo por heredar los ejes de la misión');
    expect(celdaPlasma.className).toContain('mapa-enf-celda-hueco');
    expect(celdaPlasma.querySelector('.mapa-enf-ficha-hueco')?.textContent).toBe('hueco: microglía');
    // Celda preclínica x hipocampo: ficha sin tipo celular y sin certeza.
    const celdaHipocampo = tabla.querySelectorAll('tbody tr')[0]!.querySelectorAll('td')[1]!;
    expect(celdaHipocampo.querySelector('.mapa-enf-ficha-tipo')?.textContent).toBe('sin tipo celular');
    expect(celdaHipocampo.querySelector('.chip')).toBeNull();
    // Celda prodrómica x hipocampo: microglía con certeza moderada.
    const celdaMicroglia = tabla.querySelectorAll('tbody tr')[1]!.querySelectorAll('td')[1]!;
    expect(celdaMicroglia.querySelector('.chip')?.textContent).toBe('moderada');
    // Fila "sin situar": la neurona sin fase ni región cae en la última celda.
    const filaSin = tabla.querySelectorAll('tbody tr')[2]!;
    expect(filaSin.querySelectorAll('td')[3]!.textContent).toContain('neurona');
    // Celda vacía sin hueco: un punto, sin números inventados.
    expect(filaSin.querySelectorAll('td')[0]!.className).toContain('mapa-enf-celda-vacia');
    expect(todoElTexto()).not.toContain('\u2014');
    expect(todoElTexto()).not.toMatch(SIN_TILDE);
  });

  it('con un mapa roto no lanza: celdas y huecos que no son objetos, ejes en null, etiquetas de otro tipo', async () => {
    fijarModo('detalle');
    const roto = {
      ejes: null,
      celdas: [null, 'texto', { estadio: 'fase_x', region: 42, tipoCelular: 'astrocito', hechos: 'he-1', hipotesis: null, preguntas: undefined, certezaMax: 'altisima', cohortes: 'BioFINDER', porMision: 'no' }],
      huecos: [null, { estadio: null, region: null, tipoCelular: null, motivo: 'sin motivo', heredanDeMision: null }],
      sinEjes: 'tres',
      hipotesisSinEjes: null,
      mision: null,
      resumen: null,
      etiquetas: 'no es un objeto',
      definiciones: { estadio: null },
    } as unknown as Mapa;
    await act(async () => root.render(<MapaEnfermedad mapa={roto} />));
    const texto = nodo.textContent ?? '';
    expect(nodo.querySelector('.mapa-enf-aviso')).toBeNull();
    expect(nodo.querySelector('.mapa-enf-hueco .chip')?.textContent).toBe('sin ejes');
    const tabla = nodo.querySelector('table.mapa-enf-rejilla')!;
    expect(tabla).not.toBeNull();
    // La fase desconocida se pinta con su clave; 42 no es una región y cae en "sin situar".
    expect([...tabla.querySelectorAll('tbody th')].map((t) => t.textContent)).toEqual(['fase_x', 'sin situar']);
    expect(tabla.querySelector('.mapa-enf-ficha')?.textContent).toContain('0 h · 0 hip');
    expect(tabla.querySelector('.mapa-enf-ficha .chip')).toBeNull();
    expect(texto).not.toContain('NaN');
    expect(texto).not.toContain('undefined');
    expect(texto).not.toContain('[object');
  });
});

describe('etiquetaEje', () => {
  it('prefiere la etiqueta del mapa, después la de reserva, después la clave; null es "sin situar"', () => {
    const m = { etiquetas: { estadio: { preclinica: 'fase silenciosa' }, region: {}, tipoCelular: {}, nivel: {} } } as unknown as Mapa;
    expect(etiquetaEje(m, 'estadio', 'preclinica')).toBe('fase silenciosa');
    expect(etiquetaEje(m, 'region', 'lcr')).toBe('líquido cefalorraquídeo (LCR)');
    expect(etiquetaEje(m, 'tipoCelular', 'tanicito')).toBe('tanicito');
    expect(etiquetaEje(null, 'estadio', null)).toBe('sin situar');
    expect(etiquetaEje(undefined, 'region', '')).toBe('sin situar');
  });
});

describe('MapaEnfermedad, adversario', () => {
  it('con motivos, certezaMotivo, porMision y heredanDeMision que no son texto ni número no pinta [object ni frases sin sentido', async () => {
    fijarModo('detalle');
    const m = conDatos();
    m.celdas[0] = { ...m.celdas[0]!, certezaMotivo: { a: 1 } as unknown as string, porMision: 'no' as unknown as number, cohortes: [null, 3, 'BioFINDER'] as unknown as string[] };
    m.huecos[0] = { ...m.huecos[0]!, motivo: { x: 1 } as unknown as string, heredanDeMision: { y: 2 } as unknown as number };
    m.huecos[1] = { ...m.huecos[1]!, motivo: null as unknown as string };
    (m as unknown as { resumen: unknown }).resumen = ['no', 'es', 'texto'];
    (m as unknown as { ejes: unknown }).ejes = { estadio: ['preclinica'], region: 'plasma', tipoCelular: null, nivel: { molecular: 'seis', celular: 2 } };
    await act(async () => root.render(<MapaEnfermedad mapa={m} />));
    const todo = todoElTexto();
    expect(todo).not.toContain('[object');
    expect(todo).not.toContain('undefined');
    expect(todo).not.toContain('NaN');
    expect(todo).not.toContain('no situados aquí');
    expect(todo).not.toMatch(/\bnull\b/);
    // El resumen que no es texto no se pinta como lista de letras.
    expect(nodo.querySelector('.mapa-enf-resumen')).toBeNull();
    // Niveles: solo los recuentos numéricos.
    expect(nodo.querySelector('.mapa-enf-niveles')?.textContent).toContain('celular 2');
    expect(nodo.querySelector('.mapa-enf-niveles')?.textContent).not.toContain('seis');
    // La rejilla sigue: dos fases con evidencia más "sin situar".
    expect([...nodo.querySelectorAll('table.mapa-enf-rejilla tbody th')].map((t) => t.textContent)).toEqual(['preclínica', 'prodrómica o DCL', 'sin situar']);
  });

  it('con miles de celdas se monta en un tiempo razonable y sitúa cada ficha en su celda', async () => {
    fijarModo('detalle');
    const estadios = ['preclinica', 'prodromica_dcl', 'demencia_leve', 'demencia_moderada_grave', 'autosomico_dominante', null];
    const regiones = Object.keys(ETIQUETAS_MAPA.region).concat([null as unknown as string]);
    const tipos = Object.keys(ETIQUETAS_MAPA.tipoCelular).concat([null as unknown as string]);
    const celdas: Mapa['celdas'] = [];
    for (const e of estadios) for (const r of regiones) for (const t of tipos) celdas.push({ estadio: e as Mapa['celdas'][number]['estadio'], region: r, tipoCelular: t, hechos: ['he-1'], hipotesis: [], preguntas: [], certezaMax: null, certezaMotivo: '', cohortes: [], porMision: 0 });
    // Y unas cuantas repetidas que caen en la misma celda.
    for (let i = 0; i < 2000; i++) celdas.push({ ...celdas[i % celdas.length]!, hechos: [`he-${i}`] });
    const m: Mapa = { ...vacio(), celdas, huecos: [], resumen: 'grande' };
    const inicio = performance.now();
    await act(async () => root.render(<MapaEnfermedad mapa={m} />));
    const ms = performance.now() - inicio;
    expect(nodo.querySelectorAll('.mapa-enf-ficha').length).toBe(celdas.length);
    expect(nodo.querySelectorAll('table.mapa-enf-rejilla tbody tr').length).toBe(6);
    expect(ms).toBeLessThan(4000);
  });

  it('en modo sencillo la rejilla queda plegada y se abre con "Ver detalle"; el resumen y los huecos se ven siempre', async () => {
    fijarModo('sencillo');
    await act(async () => root.render(<MapaEnfermedad mapa={conDatos()} />));
    expect(nodo.querySelector('table.mapa-enf-rejilla')).toBeNull();
    expect(nodo.textContent).toContain('La evidencia se concentra');
    expect(nodo.querySelectorAll('.mapa-enf-hueco').length).toBe(2);
    expect(nodo.textContent).toContain('4 celdas con evidencia en 3 fases y 4 regiones');
    await verDetalle();
    expect(nodo.querySelector('table.mapa-enf-rejilla')).not.toBeNull();
  });
});
