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
import { DISTANCIA_MAXIMA, DISTANCIA_MINIMA, FOCAL } from '../lib/arbol3d';
import { Arbol } from './Arbol';

vi.mock('../datos/almacen', () => ({ acciones: new Proxy({}, { get: () => () => undefined }) }));
// La preferencia de movimiento se lee una sola vez por módulo en motion/react, así
// que se intercepta para poder encender la animación en un test (la fuga de fotogramas)
// y dejar el resto con movimiento reducido, determinista.
const movimiento = vi.hoisted(() => ({ reducido: true }));
vi.mock('motion/react', async (original) => ({ ...(await original<typeof import('motion/react')>()), useReducedMotion: () => movimiento.reducido }));

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
  // La vista elegida se recuerda en el navegador: se limpia para que un test no herede la de otro.
  localStorage.removeItem('rosa-arbol-vista');
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

  /** Cambia el valor de un control de React desde fuera: hay que pasar por el setter
   *  nativo y disparar el evento, porque React escucha 'input' y compara con su valor guardado. */
  const escribir = async (el: HTMLInputElement, valor: string) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
    await act(async () => {
      setter.call(el, valor);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
  };
  const numero = (texto: string | null) => Number(texto);
  const finito = (texto: string | null) => Number.isFinite(numero(texto));

  it('pasa a la vista 3D y vuelve a la plana conservando colores, anillos, búsqueda, deslizador y plegado', async () => {
    const e = estadoConDato();
    const inv = e.investigaciones[0]!;
    await act(async () => root.render(<Arbol inv={inv} estado={e} />));
    // Por defecto, la vista plana: no se le cambia el árbol a quien ya lo conoce.
    expect(boton('Vista plana').getAttribute('aria-pressed')).toBe('true');
    expect(boton('Vista 3D').getAttribute('aria-pressed')).toBe('false');
    const svg = () => nodo.querySelector('svg.grafo')!;
    expect(svg().getAttribute('viewBox')).toBe('-450 -280 900 560');
    await pulsar(boton('Vista 3D'));
    expect(boton('Vista 3D').getAttribute('aria-pressed')).toBe('true');
    expect(boton('Vista plana').getAttribute('aria-pressed')).toBe('false');
    expect(localStorage.getItem('rosa-arbol-vista')).toBe('3d');
    expect(svg().getAttribute('viewBox')).toBe('0 0 900 560');
    expect(svg().getAttribute('aria-label')).toContain('en tres dimensiones');
    // El tronco se proyecta en el centro del lienzo; todo nodo tiene posición y radio finitos y una niebla entre 0 y 1.
    const grupo = (id: string) => nodo.querySelector(`g[data-id="${id}"]`)!;
    const circulo = (id: string) => nodo.querySelector(`g[data-id="${id}"] circle:last-of-type`)!;
    expect(grupo('objetivo').getAttribute('transform')).toBe('translate(450 280)');
    const grupos = [...nodo.querySelectorAll('g.grafo-nodo')];
    expect(grupos.length).toBeGreaterThan(3);
    for (const g of grupos) {
      const m = /translate\(([-\d.e]+) ([-\d.e]+)\)/.exec(g.getAttribute('transform') ?? '');
      expect(m, g.getAttribute('data-id') ?? '').toBeTruthy();
      expect(finito(m![1]!) && finito(m![2]!)).toBe(true);
      const op = numero(g.getAttribute('opacity'));
      expect(op).toBeGreaterThan(0);
      expect(op).toBeLessThanOrEqual(1);
      const r = numero(g.querySelector('circle:last-of-type')!.getAttribute('r'));
      expect(r).toBeGreaterThan(0);
    }
    // Relleno por familia y anillo de evidencia, idénticos a la vista plana.
    expect(circulo('hip-1').getAttribute('fill')).toMatch(/var\(--grafo-cluster-\d\)/);
    expect(circulo('hip-1').getAttribute('stroke')).toMatch(/var\(--grafo-(dato|lit)-\d\)|var\(--text-3\)/);
    expect(circulo('objetivo').getAttribute('fill')).toBe('var(--accent)');
    // Desplegar todo en 3D: aparecen el análisis, la observación, la entidad y la
    // descartada (que sigue a rayas), con sus colores.
    await pulsar(boton('Desplegar todo'));
    expect(circulo('hip-5').getAttribute('stroke-dasharray')).toBe('3 2');
    expect(circulo('run-1')).toBeTruthy();
    expect(circulo('af-obs-1')).toBeTruthy();
    const entidad = nodo.querySelector('g[data-id^="ent-"] circle:last-of-type')!;
    expect(entidad.getAttribute('fill')).toBe('var(--blue)');
    const conTodo = nodo.querySelectorAll('g.grafo-nodo').length;
    // El modo por distancia también funciona en 3D.
    await pulsar(boton('Por distancia al dato'));
    expect(circulo('run-1').getAttribute('fill')).toBe('var(--grafo-dato-0)');
    expect(circulo('hip-1').getAttribute('fill')).toBe('var(--grafo-dato-1)');
    await pulsar(boton('Por tipo y mecanismo'));
    // La búsqueda ilumina en 3D: lo que no nombra GFAP queda atenuado, lo que sí, no.
    const buscador = nodo.querySelector('input[aria-label="Buscar en el árbol"]') as HTMLInputElement;
    await escribir(buscador, 'GFAP');
    const atenuados = () => [...nodo.querySelectorAll('g.grafo-nodo')].filter((g) => (g.getAttribute('class') ?? '').includes('grafo-atenuado')).length;
    expect(atenuados()).toBeGreaterThan(0);
    expect(atenuados()).toBeLessThan(nodo.querySelectorAll('g.grafo-nodo').length);
    expect(nodo.querySelector('g[data-id^="ent-"]')!.getAttribute('class')).not.toContain('grafo-atenuado');
    await escribir(buscador, '');
    expect(atenuados()).toBe(0);
    // Pulsar un nodo en 3D lo selecciona (el panel dice qué es) y despliega o pliega sus vecinos.
    await pulsar(grupo('hip-1'));
    expect(nodo.querySelector('.grafo-panel')!.textContent).toContain('Hipótesis');
    expect(nodo.querySelector('.grafo-panel')!.textContent).toContain('A 1 salto de una medición propia.');
    // El deslizador de iteraciones filtra también en 3D.
    const deslizador = nodo.querySelector('#grafo-iteracion') as HTMLInputElement;
    await escribir(deslizador, '1');
    expect(nodo.textContent).toContain('hasta la iteración 1');
    expect(nodo.querySelectorAll('g.grafo-nodo').length).toBeLessThan(conTodo);
    await pulsar(boton('Volver al presente'));
    // Plegar todo en 3D vuelve a lo inicial y a la cámara de salida.
    await pulsar(boton('Plegar todo'));
    expect(nodo.querySelectorAll('g.grafo-nodo').length).toBeLessThan(conTodo);
    expect(nodo.querySelector('.grafo-panel')!.textContent).toContain('Leyenda');
    expect(grupo('objetivo').getAttribute('transform')).toBe('translate(450 280)');
    // Cambiar de investigación con la vista 3D abierta: el grafo se reconstruye entero sin romper.
    const e2 = structuredClone(e);
    const inv2 = { ...e2.investigaciones[0]!, id: 'inv-2', titulo: 'Otra investigación distinta' };
    e2.investigaciones = [inv2];
    for (const h of e2.hipotesis) h.investigacionId = 'inv-2';
    for (const h of e2.hechos) h.investigacionId = 'inv-2';
    for (const c of e2.corridas) c.investigacionId = 'inv-2';
    for (const r of e2.ejecuciones ?? []) r.investigacionId = 'inv-2';
    await act(async () => root.render(<Arbol inv={inv2} estado={e2} />));
    expect(svg().getAttribute('aria-label')).toContain('Otra investigación distinta');
    expect(nodo.querySelectorAll('g.grafo-nodo').length).toBeGreaterThan(3);
    for (const g of nodo.querySelectorAll('g.grafo-nodo')) expect(/translate\([-\d.e]+ [-\d.e]+\)/.test(g.getAttribute('transform') ?? '')).toBe(true);
    // Vuelta a la vista plana: todo sigue.
    await pulsar(boton('Vista plana'));
    expect(boton('Vista plana').getAttribute('aria-pressed')).toBe('true');
    expect(localStorage.getItem('rosa-arbol-vista')).toBe('plana');
    expect(svg().getAttribute('viewBox')).toBe('-450 -280 900 560');
    expect(circulo('hip-1').getAttribute('fill')).toMatch(/var\(--grafo-cluster-\d\)/);
    expect(grupo('objetivo').getAttribute('transform')).toBe('translate(0 0)');
    expect(grupo('objetivo').getAttribute('opacity')).toBeNull();
    // Ayuda y leyenda en castellano, sin guiones largos ni palabras sin tilde.
    expect(nodo.textContent).toContain('Con «Vista 3D» el mismo árbol se despliega en tres dimensiones');
    expect(nodo.textContent).not.toContain('\u2014');
    expect(nodo.textContent).not.toMatch(/\b(hipotesis|investigacion|medicion|analisis|arbol|iteracion|camara|giralo)\b/);
  });

  it('recuerda la vista 3D elegida al volver a abrir el árbol', async () => {
    localStorage.setItem('rosa-arbol-vista', '3d');
    const e = estadoConDato();
    await act(async () => root.render(<Arbol inv={e.investigaciones[0]!} estado={e} />));
    expect(boton('Vista 3D').getAttribute('aria-pressed')).toBe('true');
    expect(nodo.querySelector('svg.grafo')!.getAttribute('viewBox')).toBe('0 0 900 560');
    expect(nodo.querySelectorAll('g.grafo-nodo').length).toBeGreaterThan(3);
  });

  /** Radio proyectado del tronco: RADIO.objetivo (22) por el factor de peso (0,8 + 1,2 · 0,3) por FOCAL / distancia. */
  const radioTronco = (distancia: number) => 22 * (0.8 + Math.min(1.4, 4) * 0.3) * Math.min(4, FOCAL / distancia);
  const rTronco = () => numero(nodo.querySelector('g[data-id="objetivo"] circle:last-of-type')!.getAttribute('r'));
  /** Orden de los nodos en el DOM con su posición, su opacidad y su radio: la huella de un cuadro. */
  const transformes = () => [...nodo.querySelectorAll('g.grafo-nodo')].map((g) => `${g.getAttribute('data-id')}=${g.getAttribute('transform')}|${g.getAttribute('opacity')}|${g.querySelector('circle:last-of-type')?.getAttribute('r')}`).join(';');
  const dentroDelMarco = () => {
    for (const g of nodo.querySelectorAll('g.grafo-nodo')) {
      const m = /translate\(([-\d.e]+) ([-\d.e]+)\)/.exec(g.getAttribute('transform') ?? '');
      if (!m) return `${g.getAttribute('data-id')}: sin posición`;
      const x = numero(m[1]!);
      const y = numero(m[2]!);
      if (!(x >= 0 && x <= 900 && y >= 0 && y <= 560)) return `${g.getAttribute('data-id')}: fuera (${x}, ${y})`;
    }
    return 'todos dentro';
  };
  const puntero = async (el: Element, tipo: string, x: number, y: number) => act(async () => el.dispatchEvent(new MouseEvent(tipo, { bubbles: true, clientX: x, clientY: y })));
  const rueda = async (el: Element, deltaY: number, veces = 1) => {
    for (let i = 0; i < veces; i++) await act(async () => el.dispatchEvent(new WheelEvent('wheel', { deltaY, bubbles: true, cancelable: true })));
  };

  it('la rueda y el arrastre no sacan la cámara de sus límites, el arrastre es incremental y el almacenamiento roto no tumba la vista', async () => {
    // Modo privado o cuota llena: localStorage lanza. La vista arranca plana y aun así se puede pasar a 3D.
    const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('almacenamiento no disponible'); });
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('almacenamiento no disponible'); });
    const e = estadoConDato();
    try {
      await act(async () => root.render(<Arbol inv={e.investigaciones[0]!} estado={e} />));
      expect(boton('Vista plana').getAttribute('aria-pressed')).toBe('true');
      await pulsar(boton('Vista 3D'));
      expect(boton('Vista 3D').getAttribute('aria-pressed')).toBe('true');
      expect(nodo.querySelector('svg.grafo')!.getAttribute('viewBox')).toBe('0 0 900 560');
    } finally {
      getItem.mockRestore();
      setItem.mockRestore();
    }
    const svg = nodo.querySelector('svg.grafo')!;
    // Cámara de salida encuadrada: nunca más cerca que la distancia inicial, y todo dentro del lienzo.
    expect(rTronco()).toBeLessThanOrEqual(radioTronco(1000) + 1e-6);
    expect(dentroDelMarco()).toBe('todos dentro');
    // Sin animación: en 3D cada nodo, enlace y etiqueta se pinta sin la animación de
    // entrada ni las transiciones de styles.css, porque el orden en el DOM cambia con
    // la profundidad y cada movimiento las reiniciaría (el parpadeo que vio Emir).
    for (const el of nodo.querySelectorAll('g.grafo-nodo, line.grafo-enlace, text.grafo-etiqueta')) {
      const estilo = el.getAttribute('style') ?? '';
      expect(estilo, `${el.tagName} ${el.getAttribute('data-id') ?? ''}`).toContain('transition: none');
      expect(estilo, `${el.tagName} ${el.getAttribute('data-id') ?? ''}`).toContain('animation: none');
    }
    // Desplegar todo: el árbol crece y la cámara se aleja sola hasta abarcarlo entero.
    const antesDesplegar = rTronco();
    await pulsar(boton('Desplegar todo'));
    expect(rTronco()).toBeLessThan(antesDesplegar);
    expect(dentroDelMarco()).toBe('todos dentro');
    const conTodo = nodo.querySelectorAll('g.grafo-nodo').length;
    // Sesenta pasos de rueda hacia dentro: la distancia se para en la mínima. La rueda
    // manda sobre el encuadre y ningún nodo se desmonta aunque quede detrás de la cámara.
    await rueda(svg, -100, 60);
    expect(rTronco()).toBeCloseTo(radioTronco(DISTANCIA_MINIMA), 3);
    expect(nodo.querySelectorAll('g.grafo-nodo').length).toBe(conTodo);
    // Cien hacia fuera: en la máxima. Ningún nodo pierde su posición finita.
    await rueda(svg, 100, 100);
    expect(rTronco()).toBeCloseTo(radioTronco(DISTANCIA_MAXIMA), 3);
    expect(nodo.querySelectorAll('g.grafo-nodo').length).toBe(conTodo);
    for (const g of nodo.querySelectorAll('g.grafo-nodo')) {
      const m = /translate\(([-\d.e]+) ([-\d.e]+)\)/.exec(g.getAttribute('transform') ?? '');
      expect(m && finito(m[1]!) && finito(m[2]!), g.getAttribute('data-id') ?? '').toBe(true);
    }
    await rueda(svg, -100, 20);
    // Arrastrar el fondo en horizontal gira el árbol: los nodos cambian de sitio, el tronco no.
    const antesGiro = transformes();
    await puntero(svg, 'pointerdown', 300, 300);
    await puntero(svg, 'pointermove', 550, 300);
    expect(transformes()).not.toBe(antesGiro);
    expect(nodo.querySelector('g[data-id="objetivo"]')!.getAttribute('transform')).toBe('translate(450 280)');
    // Arrastrar 3000 píxeles hacia abajo pide un cabeceo de unos 24 radianes: se acota a 80 grados.
    await puntero(svg, 'pointermove', 550, 3300);
    const enElTope = transformes();
    await puntero(svg, 'pointermove', 550, 6300);
    expect(transformes()).toBe(enElTope); // más allá del tope, nada cambia
    // Diez píxeles de vuelta: la cámara responde en seguida, sin desandar los 3000 de exceso.
    await puntero(svg, 'pointermove', 550, 6290);
    expect(transformes()).not.toBe(enElTope);
    await puntero(svg, 'pointerup', 550, 6290);
    for (const g of nodo.querySelectorAll('g.grafo-nodo')) expect(/translate\([-\d.e]+ [-\d.e]+\)/.test(g.getAttribute('transform') ?? ''), g.getAttribute('data-id') ?? '').toBe(true);
    // Un nodo en 3D no se arrastra: pulsar sobre él no abre un arrastre de cámara.
    const hip = nodo.querySelector('g[data-id="hip-1"]')!;
    const antes = transformes();
    await puntero(hip, 'pointerdown', 400, 400);
    await puntero(svg, 'pointermove', 700, 400);
    expect(transformes()).toBe(antes);
    await puntero(svg, 'pointerup', 700, 400);
  });

  it('la rueda funciona aunque el árbol naciera vacío, y un árbol vacío con la vista 3D guardada explica qué pasará', async () => {
    localStorage.setItem('rosa-arbol-vista', '3d');
    const e = estadoConDato();
    const inv = e.investigaciones[0]!;
    const vacio: EstadoRosa = { ...e, hipotesis: [], hechos: [] };
    await act(async () => root.render(<Arbol inv={inv} estado={vacio} />));
    expect(nodo.querySelector('svg.grafo')).toBeNull();
    expect(nodo.textContent).toContain('El árbol todavía no tiene ramas');
    // Llegan las hipótesis por SSE: aparece el SVG y la rueda tiene que estar enganchada.
    await act(async () => root.render(<Arbol inv={inv} estado={e} />));
    const svg = nodo.querySelector('svg.grafo')!;
    const antes = rTronco();
    await rueda(svg, -100, 1);
    expect(rTronco()).toBeCloseTo(antes * 1.12, 3); // un paso de rueda acerca la cámara un 12 %
  });

  it('en 3D el árbol gira solo tras unos segundos sin tocarlo, se para con el ratón encima y al desmontar no queda ningún fotograma pendiente', async () => {
    // Animación encendida: los fotogramas van a una cola manual para contarlos y vaciarlos.
    movimiento.reducido = false;
    const pendientes = new Map<number, FrameRequestCallback>();
    let siguiente = 0;
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      pendientes.set(++siguiente, cb);
      return siguiente;
    });
    vi.stubGlobal('cancelAnimationFrame', (id: number) => {
      pendientes.delete(id);
    });
    const base = performance.now();
    let reloj = 0;
    const fotogramas = async (n: number, ms = 16) => {
      for (let i = 0; i < n; i++) {
        reloj += ms;
        const t = base + reloj;
        const lote = [...pendientes.entries()];
        pendientes.clear();
        await act(async () => {
          for (const [, cb] of lote) cb(t);
        });
      }
    };
    try {
      localStorage.setItem('rosa-arbol-vista', '3d');
      const e = estadoConDato();
      await act(async () => root.render(<Arbol inv={e.investigaciones[0]!} estado={e} />));
      expect(pendientes.size).toBeGreaterThan(0); // la simulación y el vigía del giro
      // La simulación se enfría en unos 140 fotogramas y el encuadre encaja detrás; a los 3 s empieza el giro.
      await fotogramas(200, 10);
      expect(dentroDelMarco()).toBe('todos dentro');
      const quieto = transformes();
      await fotogramas(3, 10);
      // Antes de los 3 s, con la cámara quieta y la simulación enfriada, dos cuadros
      // seguidos dan el mismo orden de ids, la misma opacidad y el mismo radio por nodo.
      expect(transformes()).toBe(quieto);
      await fotogramas(110, 10); // pasa de los 3 s
      const girando = transformes();
      await fotogramas(5);
      expect(transformes()).not.toBe(girando);
      expect(nodo.querySelector('g[data-id="objetivo"]')!.getAttribute('transform')).toBe('translate(450 280)');
      // Con el ratón sobre un nodo, el giro se para; al salir del lienzo, sigue.
      const hip = nodo.querySelector('g[data-id="hip-1"]')!;
      await act(async () => hip.dispatchEvent(new MouseEvent('pointerover', { bubbles: true })));
      const parado = transformes();
      await fotogramas(5);
      expect(transformes()).toBe(parado);
      await act(async () => hip.dispatchEvent(new MouseEvent('pointerout', { bubbles: true, relatedTarget: document.body })));
      await fotogramas(5);
      expect(transformes()).not.toBe(parado);
      // El nodo bajo el ratón desaparece sin pointerleave (Plegar todo lo quita): el giro no puede quedarse pausado.
      await pulsar(boton('Desplegar todo'));
      await fotogramas(200); // la simulación se asienta con lo nuevo y el encuadre la sigue cuadro a cuadro
      expect(rTronco()).toBeLessThan(radioTronco(1000)); // la cámara se alejó sola para abarcar el árbol desplegado
      expect(dentroDelMarco()).toBe('todos dentro');
      const run = nodo.querySelector('g[data-id="run-1"]')!;
      await act(async () => run.dispatchEvent(new MouseEvent('pointerover', { bubbles: true })));
      const conRaton = transformes();
      await fotogramas(5);
      expect(transformes()).toBe(conRaton);
      await pulsar(boton('Plegar todo'));
      expect(nodo.querySelector('g[data-id="run-1"]')).toBeNull();
      await fotogramas(200); // cámara de salida y simulación asentada de nuevo
      const trasPlegar = transformes();
      await fotogramas(5);
      expect(transformes()).not.toBe(trasPlegar);
      expect([...nodo.querySelectorAll('g.grafo-nodo')].some((g) => (g.getAttribute('class') ?? '').includes('grafo-atenuado'))).toBe(false);
      // Al volver a la vista plana, el giro se cancela: tras enfriarse la simulación solo queda el vaivén.
      await pulsar(boton('Vista plana'));
      await fotogramas(250); // la simulación plana se enfría en unos 140 fotogramas
      expect(pendientes.size).toBe(1);
      // Y de vuelta a 3D: solo el vigía del giro (la simulación ya estaba asentada).
      await pulsar(boton('Vista 3D'));
      await fotogramas(250);
      expect(pendientes.size).toBe(1);
      // Al desmontar no queda nada en la cola, ni nada que se vuelva a encolar.
      await act(async () => root.unmount());
      await fotogramas(3);
      expect(pendientes.size).toBe(0);
      root = createRoot(nodo); // para que el afterEach desmonte algo
    } finally {
      movimiento.reducido = true;
      vi.unstubAllGlobals();
    }
  }, 30000); // unos mil cuadros con render cada uno: con la suite entera en paralelo supera los 5 s por defecto

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
