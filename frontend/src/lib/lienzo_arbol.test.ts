// El lienzo del árbol (17 de septiembre de 2026): la escena que se construye a
// partir de las posiciones y la cámara, el acierto del puntero, la paleta que
// resuelve tokens y el trazo sobre un contexto 2D falso que registra llamadas.
import { describe, expect, it } from 'vitest';
import type { EnlaceArbol, Grafo, NodoArbol } from './arbol';
import { camaraInicial, FOCAL, type Posicion3 } from './arbol3d';
import { ajusteLienzo, construirEscena, dibujar, huella, lineas, nodoBajoPuntero, opacidadEtiqueta, Paleta, radioBase, vaiven, type Contexto2D, type EntradaEscena, type EstiloNodo } from './lienzo_arbol';

function grafoEstrella(n: number): Grafo {
  const nodos: NodoArbol[] = [{ id: 'objetivo', tipo: 'objetivo', etiqueta: 'Objetivo de la investigación con un título largo', peso: 4, iteracion: 0 }];
  const enlaces: EnlaceArbol[] = [];
  for (let i = 0; i < n; i++) {
    nodos.push({ id: `h${i}`, tipo: i === 0 ? 'experimento' : 'hipotesis', etiqueta: `Hipótesis ${i}`, peso: 1.5, iteracion: 1, estado: i === 1 ? 'descartada' : undefined });
    enlaces.push({ de: 'objetivo', a: `h${i}`, tipo: 'rama' });
  }
  const vecinos = new Map<string, Set<string>>();
  for (const e of enlaces) {
    if (!vecinos.has(e.de)) vecinos.set(e.de, new Set());
    if (!vecinos.has(e.a)) vecinos.set(e.a, new Set());
    vecinos.get(e.de)!.add(e.a);
    vecinos.get(e.a)!.add(e.de);
  }
  return { nodos, enlaces, vecinos, porId: new Map(nodos.map((x) => [x.id, x])), iteracionMax: 1 };
}

const estilo = (n: NodoArbol): EstiloNodo => ({ relleno: n.tipo === 'objetivo' ? 'var(--accent)' : 'var(--grafo-cluster-0)', anillo: 'var(--surface)', anchoAnillo: 1.5, guion: n.estado === 'descartada' ? '3 2' : null });
const trazo = () => ({ color: 'var(--border-strong)', ancho: 1.6 });

function entrada(extra: Partial<EntradaEscena> = {}): EntradaEscena {
  const g = grafoEstrella(4);
  const pos2 = new Map([
    ['objetivo', { x: 0, y: 0, vx: 0, vy: 0, fijo: true }],
    ['h0', { x: 200, y: 0, vx: 0, vy: 0 }],
    ['h1', { x: -200, y: 0, vx: 0, vy: 0 }],
    ['h2', { x: 0, y: 150, vx: 0, vy: 0 }],
    ['h3', { x: 0, y: -150, vx: 0, vy: 0 }],
  ]);
  const pos3 = new Map<string, Posicion3>([
    ['objetivo', { x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0, fijo: true }],
    ['h0', { x: 200, y: 0, z: 0, vx: 0, vy: 0, vz: 0 }],
    ['h1', { x: 0, y: 0, z: 300, vx: 0, vy: 0, vz: 0 }], // lejos
    ['h2', { x: 0, y: 0, z: -300, vx: 0, vy: 0, vz: 0 }], // cerca
    ['h3', { x: 0, y: 0, z: -2000, vx: 0, vy: 0, vz: 0 }], // detrás de la cámara
  ]);
  return { modo: 'plana', grafo: g, ids: ['objetivo', 'h0', 'h1', 'h2', 'h3'], pos2, pos3, camara: { guinada: 0, cabeceo: 0, distancia: FOCAL }, vista: { x: 0, y: 0, k: 1 }, reloj: null, ancho: 900, alto: 560, estiloDe: estilo, trazoDe: trazo, foco: null, iluminados: new Set(), seleccion: null, ...extra };
}

describe('la escena del lienzo', () => {
  it('en la vista plana coloca el tronco en el centro, aplica la vista (desplazamiento y zoom) y lleva colores como tokens', () => {
    const e = construirEscena(entrada());
    const tronco = e.nodos.find((n) => n.id === 'objetivo')!;
    expect(tronco.x).toBe(450);
    expect(tronco.y).toBe(280);
    expect(tronco.r).toBeCloseTo(radioBase(e.nodos.length ? entrada().grafo.porId.get('objetivo')! : ({} as NodoArbol)), 9);
    expect(tronco.estilo.relleno).toBe('var(--accent)');
    expect(tronco.etiqueta.lineas.length).toBe(2);
    expect(tronco.etiqueta.negrita).toBe(true);
    expect(e.nodos.find((n) => n.id === 'h1')!.estilo.guion).toBe('3 2');
    expect(e.enlaces.length).toBe(4);
    const h0 = e.nodos.find((n) => n.id === 'h0')!;
    expect(h0.x).toBe(650);
    // Con zoom 2 y desplazamiento (30, -10): todo se escala desde el centro.
    const z = construirEscena(entrada({ vista: { x: 30, y: -10, k: 2 } }));
    expect(z.nodos.find((n) => n.id === 'objetivo')!.x).toBe(480);
    expect(z.nodos.find((n) => n.id === 'h0')!.x).toBe(480 + 400);
    expect(z.nodos.find((n) => n.id === 'h0')!.r).toBeCloseTo(h0.r * 2);
    expect(z.nodos.find((n) => n.id === 'h0')!.etiqueta.tamano).toBeCloseTo(h0.etiqueta.tamano * 2);
    expect(z.enlaces[0]!.ancho).toBeCloseTo(3.2);
    // El vaivén mueve cada nodo un poco y de forma distinta, nunca el tronco (fijo o no, es dibujo).
    const v = vaiven('h0', 1.5, 12.3);
    expect(Math.hypot(v.x, v.y)).toBeGreaterThan(0);
    expect(vaiven('h0', 1.5, null)).toEqual({ x: 0, y: 0 });
    expect(huella(construirEscena(entrada()))).toBe(huella(construirEscena(entrada())));
  });

  it('en 3D ordena de lejos a cerca, aplica niebla y escala, y deja invisible lo que queda detrás de la cámara', () => {
    const e = construirEscena(entrada({ modo: '3d' }));
    const ids = e.nodos.map((n) => n.id);
    expect(ids.indexOf('h1')).toBeLessThan(ids.indexOf('objetivo'));
    expect(ids.indexOf('objetivo')).toBeLessThan(ids.indexOf('h2'));
    const lejos = e.nodos.find((n) => n.id === 'h1')!;
    const cerca = e.nodos.find((n) => n.id === 'h2')!;
    const detras = e.nodos.find((n) => n.id === 'h3')!;
    expect(lejos.r).toBeLessThan(cerca.r);
    expect(lejos.opacidad).toBeLessThan(1);
    expect(cerca.opacidad).toBe(1);
    expect(detras.visible).toBe(false);
    expect(detras.opacidad).toBe(0);
    expect(e.nodos.find((n) => n.id === 'objetivo')).toMatchObject({ x: 450, y: 280 });
    // El enlace hacia el nodo de detrás queda invisible; el que va al lejano lleva su niebla.
    expect(e.enlaces.find((l) => l.a === 'h3')!.opacidad).toBe(0);
    expect(e.enlaces.find((l) => l.a === 'h1')!.opacidad).toBeCloseTo(0.75 * lejos.opacidad);
    // La etiqueta encoge con la profundidad, acotada.
    expect(lejos.etiqueta.tamano).toBeLessThan(cerca.etiqueta.tamano);
    // La misma entrada da la misma huella; girar la cámara la cambia.
    expect(huella(e)).toBe(huella(construirEscena(entrada({ modo: '3d' }))));
    expect(huella(construirEscena(entrada({ modo: '3d', camara: { ...camaraInicial(), guinada: 1 } })))).not.toBe(huella(e));
  });

  it('atenúa con la búsqueda y con el ratón encima, y marca la selección', () => {
    const sinFoco = construirEscena(entrada());
    expect(sinFoco.nodos.every((n) => n.vivo)).toBe(true);
    const conFoco = construirEscena(entrada({ foco: 'h0' }));
    expect(conFoco.nodos.find((n) => n.id === 'h0')).toMatchObject({ vivo: true, hover: true });
    expect(conFoco.nodos.find((n) => n.id === 'objetivo')!.vivo).toBe(true); // vecino
    expect(conFoco.nodos.find((n) => n.id === 'h2')!.vivo).toBe(false);
    expect(conFoco.enlaces.find((l) => l.a === 'h2')!.opacidad).toBe(0.12);
    const buscados = construirEscena(entrada({ iluminados: new Set(['h2']) }));
    expect(buscados.nodos.filter((n) => !n.vivo).length).toBe(4);
    expect(buscados.nodos.find((n) => n.id === 'h2')!.etiqueta.opacidad).toBe(1); // iluminado: la etiqueta se ve
    expect(construirEscena(entrada({ seleccion: 'h1' })).nodos.find((n) => n.id === 'h1')!.sel).toBe(true);
  });

  it('el puntero acierta el nodo más cercano dentro de su radio más el margen, y el de arriba si se solapan', () => {
    const e = construirEscena(entrada());
    const h0 = e.nodos.find((n) => n.id === 'h0')!;
    expect(nodoBajoPuntero(e, h0.x, h0.y)).toBe('h0');
    expect(nodoBajoPuntero(e, h0.x + h0.r + 3, h0.y)).toBe('h0');
    expect(nodoBajoPuntero(e, h0.x + h0.r + 5, h0.y)).toBeNull();
    expect(nodoBajoPuntero(e, -1000, -1000)).toBeNull();
    // Dos nodos en el mismo punto: gana el que se pinta encima (el último).
    const e3 = construirEscena(entrada({ modo: '3d', pos3: new Map([['objetivo', { x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0 }], ['h0', { x: 0, y: 0, z: -100, vx: 0, vy: 0, vz: 0 }]]), ids: ['objetivo', 'h0'] }));
    expect(nodoBajoPuntero(e3, 450, 280)).toBe('h0');
    // Lo que está detrás de la cámara no se puede pulsar.
    const eDetras = construirEscena(entrada({ modo: '3d' }));
    const detras = eDetras.nodos.find((n) => n.id === 'h3')!;
    expect(nodoBajoPuntero({ ...eDetras, nodos: [detras] }, detras.x, detras.y)).toBeNull();
  });

  it('la paleta resuelve tokens una vez, respeta literales y se refresca', () => {
    let lecturas = 0;
    const raiz = { } as Element;
    const original = globalThis.getComputedStyle;
    (globalThis as { getComputedStyle: unknown }).getComputedStyle = () => ({ getPropertyValue: (t: string) => { lecturas++; return t === '--accent' ? ' #5b2aa8 ' : ''; } });
    try {
      const p = new Paleta(raiz, { '--text': '#111111' });
      expect(p.color('var(--accent)')).toBe('#5b2aa8');
      expect(p.color('var(--accent)')).toBe('#5b2aa8');
      expect(lecturas).toBe(1); // caché
      expect(p.color('var(--text)')).toBe('#111111'); // respaldo si el token no existe
      expect(p.color('#7c3aed')).toBe('#7c3aed'); // literal
      expect(p.color('var(--no-existe)')).toBe('#888888');
      p.refrescar();
      p.color('var(--accent)');
      expect(lecturas).toBe(4); // accent, text (sin valor), no-existe y accent otra vez tras refrescar
    } finally {
      (globalThis as { getComputedStyle: unknown }).getComputedStyle = original;
    }
    expect(new Paleta(null).color('var(--accent)')).toBe('#888888');
  });

  it('dibuja enlaces y después nodos con sus rayas, halo del tronco y etiquetas, saltando lo invisible', () => {
    const llamadas: string[] = [];
    const estado = { globalAlpha: 1, lineWidth: 1, strokeStyle: '', fillStyle: '', font: '', textAlign: 'start', textBaseline: 'alphabetic', lineCap: 'butt', lineJoin: 'miter' } as unknown as Contexto2D;
    const registrar = (nombre: string) => (...args: unknown[]) => { llamadas.push(`${nombre}(${args.map((a) => (typeof a === 'number' ? a.toFixed(1) : String(a))).join(',')})`); };
    Object.assign(estado, { setTransform: registrar('setTransform'), clearRect: registrar('clearRect'), beginPath: registrar('beginPath'), moveTo: registrar('moveTo'), lineTo: registrar('lineTo'), stroke: registrar('stroke'), fill: registrar('fill'), arc: registrar('arc'), setLineDash: registrar('setLineDash'), save: registrar('save'), restore: registrar('restore'), translate: registrar('translate'), scale: registrar('scale'), fillText: registrar('fillText'), strokeText: registrar('strokeText') });
    const e = construirEscena(entrada({ modo: '3d', seleccion: 'h0' }));
    const paleta = new Paleta(null, { '--accent': '#5b2aa8', '--text': '#111', '--bg': '#fff', '--text-2': '#777', '--surface': '#fff', '--border-strong': '#ccc', '--grafo-cluster-0': '#7c3aed' });
    dibujar(estado, e, { paleta, fuente: 'Inter, sans-serif', escala: 2, dx: 10, dy: 5, anchoPx: 1800, altoPx: 1120 });
    expect(llamadas[0]).toBe('setTransform(1.0,0.0,0.0,1.0,0.0,0.0)');
    expect(llamadas[1]).toBe('clearRect(0.0,0.0,1800.0,1120.0)');
    expect(llamadas[2]).toBe('setTransform(2.0,0.0,0.0,2.0,10.0,5.0)');
    // Tres enlaces visibles (el cuarto va al nodo de detrás y no se traza), y después los nodos.
    const lineas_ = llamadas.filter((l) => l.startsWith('lineTo')).length;
    expect(lineas_).toBe(3);
    const arcos = llamadas.filter((l) => l.startsWith('arc')).length;
    expect(arcos).toBe(4 + 1); // cuatro nodos visibles más el halo del tronco
    expect(llamadas.some((l) => l === 'setLineDash(3,2)')).toBe(true); // la descartada, a rayas
    expect(llamadas.some((l) => l.startsWith('strokeText') && l.includes('Objetivo'))).toBe(true);
    expect(llamadas.some((l) => l.startsWith('fillText') && l.includes('Objetivo'))).toBe(true);
    expect(llamadas.filter((l) => l.startsWith('lineTo')).length).toBeLessThan(llamadas.findIndex((l) => l.startsWith('arc'))); // enlaces antes que nodos
    expect(estado.globalAlpha).toBe(1);
  });

  it('el ajuste encaja el lienzo lógico centrado y sin deformar, y con un canvas sin tamaño no toca nada', () => {
    expect(ajusteLienzo(900, 560, 0, 0)).toEqual({ escala: 1, dx: 0, dy: 0 });
    const a = ajusteLienzo(900, 560, 1800, 1400);
    expect(a.escala).toBe(2);
    expect(a.dx).toBe(0);
    expect(a.dy).toBe(140);
    const b = ajusteLienzo(900, 560, 900, 280);
    expect(b.escala).toBe(0.5);
    expect(b.dx).toBe(225);
    expect(b.dy).toBe(0);
    // Y las piezas puras heredadas del SVG siguen igual.
    expect(lineas('corto')).toEqual(['corto']);
    expect(lineas('una etiqueta bastante más larga que veintidós caracteres seguidos').length).toBe(2);
    expect(opacidadEtiqueta({ tipo: 'objetivo' } as NodoArbol, 0.3, false, false)).toBe(1);
    expect(opacidadEtiqueta({ tipo: 'fuente' } as NodoArbol, 1, false, false)).toBe(0);
    expect(opacidadEtiqueta({ tipo: 'fuente' } as NodoArbol, 1, true, false)).toBe(0.9);
  });
});
