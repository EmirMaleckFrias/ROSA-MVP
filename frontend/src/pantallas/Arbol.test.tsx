// @vitest-environment jsdom
// La pantalla del árbol montada de verdad (16 de septiembre de 2026): el
// conmutador "Color por distancia al dato" cambia la leyenda y el relleno de
// los nodos, las entidades canónicas conservan su color (no son literatura),
// el panel de selección dice la distancia con sus tildes y nada de lo que se
// pinta lleva guiones largos. Se monta con movimiento reducido para que la
// disposición por fuerzas corra en el efecto, sin fotogramas, y el test sea
// determinista.
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import type { Afirmacion, Ejecucion, EstadoRosa, PlanAnalisis } from '../datos/tipos';
import { Arbol } from './Arbol';

vi.mock('../datos/almacen', () => ({ acciones: new Proxy({}, { get: () => () => undefined }) }));

beforeAll(() => {
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  // Movimiento reducido: la simulación se asienta en el efecto y no hay vaivén.
  window.matchMedia = (q: string) => ({ matches: q.includes('reduce'), media: q, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false }) as MediaQueryList;
});

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

function ejecucionValida(id: string, hipotesisId: string, planId: string): Ejecucion {
  return { id, investigacionId: 'inv-1', hipotesisId, planId, tipo: 'hipotesis', codigo: '', entorno: { python: '3.12', paquetes: [] }, semilla: 1, hashDatos: '', hashPlan: '', inicio: 1, fin: 2, estado: 'completado', runtime: 'docker', red: 'deshabilitada', codigoSalida: 0, duracionS: 1, salida: '', error: '', resultados: {}, baseline: {}, controlNegativo: {}, repeticiones: [], interpretacion: null, plausibilidadVerificada: true, auditoria: { veredicto: 'valido', comprobaciones: [], motivo: '', quien: 'Killer II', fecha: 2 } };
}

function planDe(id: string, hipotesisId: string, datasetId: string): PlanAnalisis {
  return { id, investigacionId: 'inv-1', hipotesisId, datasetId, tipo: 'confirmatorio', pregunta: '', variables: [], poblacion: '', preprocesado: [], prueba: '', hipotesisNula: '', hipotesisAlternativa: '', alpha: 0.05, direccionEsperada: '', tamanoEfectoMinimo: '', baseline: '', controlNegativo: '', correccionMultiplicidad: '', umbralEfecto: '', criterioNoEvaluable: '', semilla: 1, hashDatos: '', hashPlan: '', congeladoEn: 1, autor: 'rosa', reproduccionId: null };
}

/** Estado de muestra más un análisis válido y su observación sobre hip-1. */
function estadoConDato(): EstadoRosa {
  const e = structuredClone(estadoDeMuestra());
  const inv = e.investigaciones[0]!;
  const h = e.hipotesis.find((x) => x.id === 'hip-1')!;
  e.ejecuciones = [ejecucionValida('run-1', h.id, 'plan-1')];
  e.planesAnalisis = [planDe('plan-1', h.id, inv.datasets[0]!.id)];
  const obs: Afirmacion = { texto: 'La correlación entre GFAP y NfL fue de 0,41 (n = 212).', cita: '[Análisis in silico run-1]', veredicto: 'sostenida', motivo: '', entidadDistinta: false, tipo: 'dato', clase: 'observacion_original', trayectoria: { id: 'run-1', celda: 0 }, afirmacionId: 'obs-1' };
  h.afirmaciones = [...h.afirmaciones, obs];
  // La muestra no trae entidades canónicas: se pone una en hip-3 para comprobar su color.
  e.hipotesis.find((x) => x.id === 'hip-3')!.entidades = [{ id: 'HGNC:4235', etiqueta: 'GFAP', ontologia: 'HGNC', tipo: 'gen', alias: ['GFAP'] }];
  return e;
}

const boton = (texto: string) => [...nodo.querySelectorAll('button')].find((b) => b.textContent?.trim() === texto)!;
const pulsar = async (el: Element) => act(async () => el.dispatchEvent(new MouseEvent('click', { bubbles: true })));

describe('la pantalla del árbol', () => {
  it('cambia de color por tipo a color por distancia al dato, con la leyenda y el panel en castellano', async () => {
    const e = estadoConDato();
    const inv = e.investigaciones[0]!;
    await act(async () => root.render(<Arbol inv={inv} estado={e} />));
    // Abre en el modo por tipo y mecanismo (por defecto desde el 16 de septiembre de 2026):
    // relleno por familia y tipo, anillo por distancia al dato.
    expect(boton('Por tipo y mecanismo').getAttribute('aria-pressed')).toBe('true');
    expect(nodo.textContent).toContain('Anillo verde');
    expect(nodo.textContent).toContain('Afirmación con dato');
    expect(nodo.textContent).toContain('Análisis in silico');
    expect(nodo.textContent).toContain('Conjunto de datos');
    expect(nodo.textContent).not.toContain('Sin medición propia ni literatura leída');
    // Se despliega todo para que haya entidades, fuentes y el análisis en pantalla.
    await pulsar(boton('Desplegar todo'));
    const circulo = (id: string) => nodo.querySelector(`g[data-id="${id}"] circle:last-of-type`)!;
    expect(circulo('run-1')).toBeTruthy();
    expect(circulo('hip-1').getAttribute('fill')).toMatch(/var\(--grafo-cluster-\d\)/);
    expect(circulo('hip-1').getAttribute('stroke')).toMatch(/var\(--grafo-(dato|lit)-\d\)|var\(--text-3\)/);
    // Vuelta al modo por distancia.
    await pulsar(boton('Por distancia al dato'));
    expect(boton('Por distancia al dato').getAttribute('aria-pressed')).toBe('true');
    expect(nodo.textContent).toContain('Sin medición propia ni literatura leída');
    expect(nodo.textContent).toContain('La medición misma (0 saltos)');
    expect(circulo('run-1').getAttribute('fill')).toBe('var(--grafo-dato-0)');
    expect(circulo('af-obs-1').getAttribute('fill')).toBe('var(--grafo-dato-0)');
    expect(circulo('hip-1').getAttribute('fill')).toBe('var(--grafo-dato-1)');
    // Una hipótesis viva sin medición propia: ámbar si tiene literatura leída detrás
    // (segunda escala), gris punteado si no tiene nada. La descartada (hip-5) conserva
    // su punteado propio y la leyenda lo dice.
    expect(circulo('hip-3').getAttribute('fill')).toMatch(/var\(--grafo-(lit-[123]|dato-nulo)\)/);
    if (circulo('hip-3').getAttribute('fill') === 'var(--grafo-dato-nulo)') expect(circulo('hip-3').getAttribute('stroke-dasharray')).toBe('2 2');
    expect(circulo('hip-5').getAttribute('fill')).toMatch(/var\(--grafo-(lit-[123]|dato-nulo)\)/);
    expect(circulo('hip-5').getAttribute('stroke-dasharray')).toBe('3 2');
    expect(nodo.textContent).toContain('Punteada: descartada o sin medición propia.');
    // El tronco y las entidades conservan su color: no son evidencia.
    expect(circulo('objetivo').getAttribute('fill')).toBe('var(--accent)');
    const entidad = nodo.querySelector('g[data-id^="ent-"] circle:last-of-type')!;
    expect(entidad.getAttribute('fill')).toBe('var(--blue)');
    expect(entidad.getAttribute('stroke-dasharray')).toBeNull();
    // Panel de selección: una entidad no lleva frase de distancia (se pulsa
    // antes que hip-3, que al plegarse se la llevaría).
    await pulsar(nodo.querySelector('g[data-id^="ent-"]')!);
    const panel = nodo.querySelector('.grafo-panel')!;
    expect(panel.textContent).toContain('Entidad canónica');
    expect(panel.textContent).not.toContain('medición propia');
    // La distancia en una frase.
    await pulsar(nodo.querySelector('g[data-id="hip-1"]')!);
    expect(panel.textContent).toContain('A 1 salto de una medición propia.');
    await pulsar(nodo.querySelector('g[data-id="run-1"]')!);
    expect(panel.textContent).toContain('Es una medición propia: análisis in silico completado y auditado como válido.');
    await pulsar(nodo.querySelector('g[data-id="hip-3"]')!);
    expect(panel.textContent).toMatch(/Sin medición propia detrás; literatura a \d+ saltos?\./);
    // Nada de lo pintado lleva guiones largos (U+2014, escapado para que el
    // carácter no aparezca en el código) ni palabras visibles sin tilde.
    expect(nodo.textContent).not.toContain('\u2014');
    expect(nodo.textContent).not.toMatch(/\b(hipotesis|investigacion|medicion|analisis|arbol|iteracion)\b/);
  });

  it('con una investigación vacía explica qué pasará, con tildes', async () => {
    const e = structuredClone(estadoDeMuestra());
    const inv = e.investigaciones[0]!;
    const vacio: EstadoRosa = { ...e, hipotesis: [], hechos: [] };
    await act(async () => root.render(<Arbol inv={inv} estado={vacio} />));
    expect(nodo.textContent).toContain('ya está.');
    expect(nodo.textContent).toContain('aparecerán');
    expect(nodo.textContent).toContain('Aquí se ve toda la investigación conectada: qué sostiene a qué');
  });
});
