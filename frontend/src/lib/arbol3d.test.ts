// La geometría de la vista 3D del árbol (16 de septiembre de 2026): la
// proyección en perspectiva, la cámara orbital, el orden de pintado y la
// disposición por fuerzas en tres ejes. Casos adversarios incluidos: grafo
// vacío, un solo nodo, doscientos nodos en el mismo punto, valores NaN y un
// punto detrás de la cámara.
import { describe, expect, it } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import { construirArbol, visiblesIniciales, type EnlaceArbol, type Grafo, type NodoArbol } from './arbol';
import { acotarCamara, CABECEO_MAXIMO, camaraInicial, direccionEsfera, DISTANCIA_INICIAL, DISTANCIA_MAXIMA, DISTANCIA_MINIMA, distanciaEncuadre, FOCAL, MARGEN_ENCUADRE, niebla, ordenarPorProfundidad, paso3d, PLANO_CERCANO, posicionInicial3d, proyectar, sinNaN, type Camara, type Posicion3 } from './arbol3d';
import type { TipoEnlace, TipoNodo } from './arbol';

const ANCHO = 900;
const ALTO = 560;
const camara = (extra: Partial<Camara> = {}): Camara => ({ guinada: 0, cabeceo: 0, distancia: FOCAL, ...extra });

/** Un grafo mínimo con un tronco y `n` hojas colgando de él, sin pasar por el estado. */
function grafoEstrella(n: number): Grafo {
  const nodos: NodoArbol[] = [{ id: 'objetivo', tipo: 'objetivo', etiqueta: 'Objetivo', peso: 4, iteracion: 0 }];
  const enlaces: EnlaceArbol[] = [];
  for (let i = 0; i < n; i++) {
    nodos.push({ id: `h${i}`, tipo: 'hipotesis', etiqueta: `Hipótesis ${i}`, peso: 1.5, iteracion: 1 });
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

const finita = (p: Posicion3) => [p.x, p.y, p.z, p.vx, p.vy, p.vz].every((v) => Number.isFinite(v));

/** Un árbol grande y ramificado (para medir): `ramas` ramas del tronco y el resto
 *  de nodos repartidos por tipos, colgando de una rama cada uno. */
function grafoGrande(total: number, ramas = 20): Grafo {
  const tipos: TipoNodo[] = ['hipotesis', 'fuente', 'hecho', 'entidad', 'afirmacion', 'experimento'];
  const nodos: NodoArbol[] = [{ id: 'objetivo', tipo: 'objetivo', etiqueta: 'Objetivo', peso: 4, iteracion: 0 }];
  const enlaces: EnlaceArbol[] = [];
  for (let i = 0; i < total - 1; i++) {
    const esRama = i < ramas;
    nodos.push({ id: `n${i}`, tipo: esRama ? 'rama' : tipos[i % tipos.length]!, etiqueta: `Nodo ${i}`, peso: 1 + (i % 3) * 0.5, iteracion: 1 });
    enlaces.push({ de: esRama ? 'objetivo' : `n${i % ramas}`, a: `n${i}`, tipo: esRama ? 'rama' : 'cita' });
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

/** Coloca y asienta un grafo con la misma semilla: para comparar dos corridas. */
function asentar(g: Grafo, pasos = 300): Map<string, Posicion3> {
  const visibles = new Set(g.nodos.map((n) => n.id));
  const pos = new Map<string, Posicion3>();
  let s = 1;
  for (const id of visibles) pos.set(id, posicionInicial3d(g, pos, id, s++));
  for (let i = 0; i < pasos; i++) paso3d(g, visibles, pos, Math.max(0.05, 1 - i / pasos));
  return pos;
}
const radio = (p: Posicion3) => Math.hypot(p.x, p.y, p.z);

describe('la proyección en perspectiva', () => {
  it('un punto en el origen cae en el centro del lienzo con escala 1 a la distancia focal', () => {
    const p = proyectar({ x: 0, y: 0, z: 0 }, camara(), ANCHO, ALTO);
    expect(p.visible).toBe(true);
    expect(p.x).toBeCloseTo(ANCHO / 2);
    expect(p.y).toBeCloseTo(ALTO / 2);
    expect(p.escala).toBeCloseTo(1);
    expect(p.profundidad).toBeCloseTo(FOCAL);
    // Y con cualquier giro de la cámara sigue en el centro: el tronco es el eje.
    for (const c of [camara({ guinada: 1.3 }), camara({ cabeceo: -0.9 }), camara({ guinada: 2.7, cabeceo: 0.6, distancia: 1500 })]) {
      const q = proyectar({ x: 0, y: 0, z: 0 }, c, ANCHO, ALTO);
      expect(q.x).toBeCloseTo(ANCHO / 2);
      expect(q.y).toBeCloseTo(ALTO / 2);
    }
  });

  it('lo lejano se ve más pequeño y lo cercano más grande, y un punto detrás de la cámara no es visible', () => {
    const lejos = proyectar({ x: 100, y: 0, z: 400 }, camara(), ANCHO, ALTO);
    const cerca = proyectar({ x: 100, y: 0, z: -400 }, camara(), ANCHO, ALTO);
    expect(lejos.escala).toBeLessThan(1);
    expect(cerca.escala).toBeGreaterThan(1);
    expect(lejos.profundidad).toBeGreaterThan(cerca.profundidad);
    // Más cerca del centro cuanto más lejos: es la perspectiva.
    expect(lejos.x - ANCHO / 2).toBeLessThan(cerca.x - ANCHO / 2);
    // Detrás de la cámara (z rotada menor que -distancia) y en el plano cercano: invisible, sin infinitos.
    const detras = proyectar({ x: 50, y: 50, z: -FOCAL - 10 }, camara(), ANCHO, ALTO);
    expect(detras.visible).toBe(false);
    expect(Number.isFinite(detras.x) && Number.isFinite(detras.y)).toBe(true);
    const enElPlano = proyectar({ x: 0, y: 0, z: -FOCAL + PLANO_CERCANO }, camara(), ANCHO, ALTO);
    expect(enElPlano.visible).toBe(false);
    // Justo delante del plano cercano: visible y con la escala acotada.
    const pegado = proyectar({ x: 0, y: 0, z: -FOCAL + PLANO_CERCANO + 1 }, camara(), ANCHO, ALTO);
    expect(pegado.visible).toBe(true);
    expect(pegado.escala).toBeLessThanOrEqual(4);
  });

  it('girar 360 grados devuelve la misma proyección, y media vuelta la refleja', () => {
    const p = { x: 120, y: -40, z: 80 };
    for (const base of [camara(), camara({ cabeceo: 0.5 }), camara({ guinada: -1.1, cabeceo: -0.3 })]) {
      const a = proyectar(p, base, ANCHO, ALTO);
      const b = proyectar(p, { ...base, guinada: base.guinada + Math.PI * 2 }, ANCHO, ALTO);
      expect(b.x).toBeCloseTo(a.x, 6);
      expect(b.y).toBeCloseTo(a.y, 6);
      expect(b.escala).toBeCloseTo(a.escala, 6);
      expect(b.profundidad).toBeCloseTo(a.profundidad, 6);
    }
    // Media vuelta sin cabeceo: la x se refleja respecto al centro y la z cambia de signo.
    const a = proyectar({ x: 120, y: 0, z: 0 }, camara(), ANCHO, ALTO);
    const b = proyectar({ x: 120, y: 0, z: 0 }, camara({ guinada: Math.PI }), ANCHO, ALTO);
    expect(b.x - ANCHO / 2).toBeCloseTo(-(a.x - ANCHO / 2), 6);
    expect(b.escala).toBeCloseTo(a.escala, 6);
  });

  it('blinda los NaN: un punto o una cámara rotos no producen coordenadas rotas', () => {
    const p = proyectar({ x: NaN, y: 0, z: Infinity }, camara(), ANCHO, ALTO);
    expect(Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.escala)).toBe(true);
    const q = proyectar({ x: 10, y: 10, z: 10 }, { guinada: NaN, cabeceo: NaN, distancia: NaN }, ANCHO, ALTO);
    expect(Number.isFinite(q.x) && Number.isFinite(q.y)).toBe(true);
    expect(sinNaN(NaN, 7)).toBe(7);
    expect(sinNaN(-Infinity)).toBe(0);
    expect(sinNaN(3.5)).toBe(3.5);
    const c = acotarCamara({ guinada: NaN, cabeceo: 9, distancia: -5 });
    expect(c.guinada).toBe(0);
    expect(c.cabeceo).toBeCloseTo(CABECEO_MAXIMO);
    expect(c.distancia).toBe(DISTANCIA_MINIMA);
    expect(acotarCamara({ guinada: 0, cabeceo: -9, distancia: 1e9 })).toMatchObject({ cabeceo: -CABECEO_MAXIMO, distancia: DISTANCIA_MAXIMA });
    // La guiñada se pliega a [-pi, pi] para que no crezca sin fin con el giro automático.
    expect(Math.abs(acotarCamara({ guinada: 7 * Math.PI + 0.1, cabeceo: 0, distancia: FOCAL }).guinada)).toBeLessThanOrEqual(Math.PI);
    expect(acotarCamara(camaraInicial())).toEqual(camaraInicial());
  });

  it('la niebla baja con la profundidad y nunca pasa de 1 ni cae a cero', () => {
    const c = camara();
    expect(niebla(c.distancia - 300, c)).toBe(1);
    expect(niebla(c.distancia, c)).toBe(1);
    const media = niebla(c.distancia + 400, c);
    const lejana = niebla(c.distancia + 5000, c);
    expect(media).toBeLessThan(1);
    expect(lejana).toBeLessThan(media);
    expect(lejana).toBeGreaterThan(0);
    expect(niebla(NaN, c)).toBeGreaterThan(0);
  });
});

describe('el encuadre automático', () => {
  it('aleja la cámara justo lo necesario para que todos los puntos quepan con margen, y nunca la acerca más que la inicial', () => {
    // Nube determinista de 300 puntos hasta 800 unidades del tronco, con varias cámaras.
    const puntos: { x: number; y: number; z: number }[] = [];
    for (let k = 0; k < 300; k++) {
      const d = direccionEsfera(k);
      const r = 100 + ((k * 7919) % 701);
      puntos.push({ x: d.x * r, y: d.y * r, z: d.z * r });
    }
    for (const c of [camaraInicial(), camara(), camara({ guinada: 2.2, cabeceo: -0.7 }), camara({ guinada: -1, cabeceo: CABECEO_MAXIMO })]) {
      const distancia = distanciaEncuadre(puntos, c, ANCHO, ALTO);
      expect(distancia).toBeGreaterThan(DISTANCIA_INICIAL);
      expect(distancia).toBeLessThanOrEqual(DISTANCIA_MAXIMA);
      const con = { ...c, distancia };
      let maxX = 0;
      let maxY = 0;
      for (const p of puntos) {
        const q = proyectar(p, con, ANCHO, ALTO);
        expect(q.visible).toBe(true);
        expect(q.x).toBeGreaterThanOrEqual(MARGEN_ENCUADRE - 1e-6);
        expect(q.x).toBeLessThanOrEqual(ANCHO - MARGEN_ENCUADRE + 1e-6);
        expect(q.y).toBeGreaterThanOrEqual(MARGEN_ENCUADRE - 1e-6);
        expect(q.y).toBeLessThanOrEqual(ALTO - MARGEN_ENCUADRE + 1e-6);
        maxX = Math.max(maxX, Math.abs(q.x - ANCHO / 2));
        maxY = Math.max(maxY, Math.abs(q.y - ALTO / 2));
      }
      // Justo lo necesario: algún punto toca el margen (no sobra distancia).
      expect(Math.max(maxX - (ANCHO / 2 - MARGEN_ENCUADRE), maxY - (ALTO / 2 - MARGEN_ENCUADRE))).toBeGreaterThan(-1e-6);
    }
    // Un árbol pequeño no se agranda: se queda en la distancia inicial. Sin puntos, igual.
    expect(distanciaEncuadre([{ x: 50, y: 20, z: -30 }, { x: 0, y: 0, z: 0 }], camaraInicial(), ANCHO, ALTO)).toBe(DISTANCIA_INICIAL);
    expect(distanciaEncuadre([], camaraInicial(), ANCHO, ALTO)).toBe(DISTANCIA_INICIAL);
    // Puntos rotos no rompen; uno disparado a lo lejos topa con la distancia máxima.
    expect(Number.isFinite(distanciaEncuadre([{ x: NaN, y: Infinity, z: 3 }], camaraInicial(), ANCHO, ALTO))).toBe(true);
    expect(distanciaEncuadre([{ x: 1e6, y: 0, z: 0 }], camaraInicial(), ANCHO, ALTO)).toBe(DISTANCIA_MAXIMA);
    // Un punto pegado a la cámara (z muy negativo en el sistema de la cámara) obliga a retroceder tras el plano cercano.
    expect(distanciaEncuadre([{ x: 0, y: 0, z: -1500 }], camara(), ANCHO, ALTO)).toBeGreaterThanOrEqual(1500 + PLANO_CERCANO);
    // Con un lienzo roto (NaN) no devuelve NaN.
    expect(Number.isFinite(distanciaEncuadre(puntos, camaraInicial(), NaN, NaN))).toBe(true);
  });
});

describe('el orden de pintado', () => {
  it('ordena de lejos a cerca según la cámara y deja fuera lo que no tiene posición', () => {
    const pos = new Map<string, Posicion3>([
      ['cerca', { x: 0, y: 0, z: -200, vx: 0, vy: 0, vz: 0 }],
      ['medio', { x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0 }],
      ['lejos', { x: 0, y: 0, z: 200, vx: 0, vy: 0, vz: 0 }],
    ]);
    expect(ordenarPorProfundidad(['cerca', 'medio', 'lejos', 'fantasma'], pos, camara())).toEqual(['lejos', 'medio', 'cerca']);
    // Con media vuelta de guiñada, lo que estaba lejos queda cerca.
    expect(ordenarPorProfundidad(['cerca', 'medio', 'lejos'], pos, camara({ guinada: Math.PI }))).toEqual(['cerca', 'medio', 'lejos']);
    // Todos a la misma profundidad: orden estable por identificador, sin NaN.
    const iguales = new Map<string, Posicion3>([['b', pos.get('medio')!], ['a', pos.get('medio')!], ['c', pos.get('medio')!]]);
    expect(ordenarPorProfundidad(['b', 'a', 'c'], iguales, camara())).toEqual(['a', 'b', 'c']);
    expect(ordenarPorProfundidad([], pos, camara())).toEqual([]);
  });
});

describe('la disposición por fuerzas en tres ejes', () => {
  it('posicionInicial3d reparte en la esfera sin apilar y deja el tronco fijo en el origen', () => {
    const g = grafoEstrella(40);
    const pos = new Map<string, Posicion3>();
    let s = 1;
    pos.set('objetivo', posicionInicial3d(g, pos, 'objetivo', s++));
    expect(pos.get('objetivo')).toMatchObject({ x: 0, y: 0, z: 0, fijo: true });
    for (let i = 0; i < 40; i++) pos.set(`h${i}`, posicionInicial3d(g, pos, `h${i}`, s++));
    const hojas = [...pos.entries()].filter(([id]) => id !== 'objetivo').map(([, p]) => p);
    // Todas a la misma distancia del tronco (sobre la esfera), y usando los tres ejes.
    const radios = hojas.map((p) => Math.hypot(p.x, p.y, p.z));
    expect(Math.max(...radios) - Math.min(...radios)).toBeLessThan(1e-6);
    expect(hojas.some((p) => Math.abs(p.z) > 50)).toBe(true);
    expect(hojas.some((p) => Math.abs(p.y) > 50)).toBe(true);
    let minimo = Infinity;
    for (let i = 0; i < hojas.length; i++) for (let j = i + 1; j < hojas.length; j++) minimo = Math.min(minimo, Math.hypot(hojas[i]!.x - hojas[j]!.x, hojas[i]!.y - hojas[j]!.y, hojas[i]!.z - hojas[j]!.z));
    expect(minimo).toBeGreaterThan(25);
    // Las direcciones de la espiral son unitarias y consecutivas lejanas.
    for (let k = 0; k < 200; k++) {
      const d = direccionEsfera(k);
      expect(Math.hypot(d.x, d.y, d.z)).toBeCloseTo(1, 9);
      const e = direccionEsfera(k + 1);
      expect(Math.hypot(d.x - e.x, d.y - e.y, d.z - e.z)).toBeGreaterThan(0.1);
    }
    // Una hoja con vecino colocado nace junto a él, no en la esfera.
    const g2 = construirArbol(estadoDeMuestra(), estadoDeMuestra().investigaciones[0]!);
    const hip = g2.nodos.find((n) => n.tipo === 'hipotesis')!;
    const fuente = [...(g2.vecinos.get(hip.id) ?? [])].find((v) => g2.porId.get(v)?.tipo === 'fuente');
    if (fuente) {
      const pos2 = new Map<string, Posicion3>([[hip.id, { x: 100, y: 50, z: -30, vx: 0, vy: 0, vz: 0 }]]);
      const p = posicionInicial3d(g2, pos2, fuente, 5);
      expect(Math.hypot(p.x - 100, p.y - 50, p.z + 30)).toBeCloseTo(28, 6);
    }
    // Un identificador que no está en el grafo tampoco rompe.
    expect(finita(posicionInicial3d(g, pos, 'desconocido', NaN))).toBe(true);
  });

  it('paso3d no produce NaN con un grafo vacío, un solo nodo ni doscientos nodos en el mismo punto', () => {
    // Vacío.
    const vacio: Grafo = { nodos: [], enlaces: [], vecinos: new Map(), porId: new Map(), iteracionMax: 1 };
    expect(() => paso3d(vacio, new Set(), new Map(), 1)).not.toThrow();
    // Un solo nodo (el tronco, fijo): se queda en el origen.
    const uno = grafoEstrella(0);
    const posUno = new Map<string, Posicion3>([['objetivo', posicionInicial3d(uno, new Map(), 'objetivo', 1)]]);
    for (let i = 0; i < 50; i++) paso3d(uno, new Set(['objetivo']), posUno, 1);
    expect(posUno.get('objetivo')).toMatchObject({ x: 0, y: 0, z: 0 });
    // Un solo nodo libre sin enlaces: la gravedad lo lleva hacia el origen sin dispararlo.
    const posLibre = new Map<string, Posicion3>([['h0', { x: 300, y: 300, z: 300, vx: 0, vy: 0, vz: 0 }]]);
    for (let i = 0; i < 300; i++) paso3d(grafoEstrella(1), new Set(['h0']), posLibre, 0.5);
    expect(finita(posLibre.get('h0')!)).toBe(true);
    expect(Math.hypot(posLibre.get('h0')!.x, posLibre.get('h0')!.y, posLibre.get('h0')!.z)).toBeLessThan(Math.hypot(300, 300, 300));
    // Doscientos nodos en el mismo punto: se separan de forma determinista y sin NaN.
    const g = grafoEstrella(200);
    const visibles = new Set(g.nodos.map((n) => n.id));
    const pos = new Map<string, Posicion3>();
    for (const id of visibles) pos.set(id, id === 'objetivo' ? { x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0, fijo: true } : { x: 10, y: 10, z: 10, vx: 0, vy: 0, vz: 0 });
    for (let i = 0; i < 120; i++) paso3d(g, visibles, pos, Math.max(0.05, 1 - i / 120));
    for (const p of pos.values()) expect(finita(p)).toBe(true);
    const puntos = new Set([...pos.values()].map((p) => `${p.x.toFixed(1)}|${p.y.toFixed(1)}|${p.z.toFixed(1)}`));
    expect(puntos.size).toBeGreaterThan(190);
    expect(pos.get('objetivo')).toMatchObject({ x: 0, y: 0, z: 0 });
    // Y nadie salió disparado: todo queda a una distancia razonable del tronco.
    for (const p of pos.values()) expect(Math.hypot(p.x, p.y, p.z)).toBeLessThan(5000);
    // Determinista: la misma entrada da la misma salida.
    const pos2 = new Map<string, Posicion3>();
    for (const id of visibles) pos2.set(id, id === 'objetivo' ? { x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0, fijo: true } : { x: 10, y: 10, z: 10, vx: 0, vy: 0, vz: 0 });
    for (let i = 0; i < 120; i++) paso3d(g, visibles, pos2, Math.max(0.05, 1 - i / 120));
    expect(pos2.get('h7')).toEqual(pos.get('h7'));
  });

  it('con NaN en una posición o en alfa, el paso los repara en vez de propagarlos', () => {
    const g = grafoEstrella(3);
    const visibles = new Set(g.nodos.map((n) => n.id));
    const pos = new Map<string, Posicion3>();
    let s = 1;
    for (const id of visibles) pos.set(id, posicionInicial3d(g, pos, id, s++));
    pos.get('h1')!.x = NaN;
    pos.get('h2')!.vz = Infinity;
    for (let i = 0; i < 30; i++) paso3d(g, visibles, pos, i === 0 ? NaN : 0.8);
    for (const p of pos.values()) expect(finita(p)).toBe(true);
  });

  it('un peso NaN o cero en un nodo no colapsa el árbol hacia el tronco', () => {
    // Antes del arreglo, un solo peso NaN hacía NaN la repulsión de todos sus pares;
    // al repararla a cero quedaba solo la gravedad y las hojas caían de 226 a 134 en
    // 300 pasos, todas al mismo radio. Con el peso saneado, igual que el control sano.
    const sano = asentar(grafoEstrella(6));
    const conNaN = grafoEstrella(6);
    conNaN.porId.get('h0')!.peso = NaN;
    const pos = asentar(conNaN);
    for (const [id, p] of pos) {
      if (id === 'objetivo') continue;
      expect(finita(p)).toBe(true);
      expect(radio(p)).toBeGreaterThan(radio(sano.get(id)!) - 15);
    }
    // Peso cero en dos nodos que nacen en el mismo punto: aun así se separan.
    const ceros = grafoEstrella(2);
    for (const n of ceros.nodos) if (n.tipo !== 'objetivo') n.peso = 0;
    const visibles = new Set(ceros.nodos.map((n) => n.id));
    const pos0 = new Map<string, Posicion3>([
      ['objetivo', { x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0, fijo: true }],
      ['h0', { x: 40, y: 0, z: 0, vx: 0, vy: 0, vz: 0 }],
      ['h1', { x: 40, y: 0, z: 0, vx: 0, vy: 0, vz: 0 }],
    ]);
    for (let i = 0; i < 200; i++) paso3d(ceros, visibles, pos0, Math.max(0.05, 1 - i / 200));
    const a = pos0.get('h0')!;
    const b = pos0.get('h1')!;
    expect(finita(a) && finita(b)).toBe(true);
    expect(Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z)).toBeGreaterThan(10);
  });

  it('un tipo de enlace desconocido se comporta como uno de longitud 150, no pierde el resorte', () => {
    const conocido = grafoEstrella(3);
    conocido.enlaces[0]!.tipo = 'experimento'; // LARGO 150
    const desconocido = grafoEstrella(3);
    desconocido.enlaces[0]!.tipo = 'desconocido' as TipoEnlace;
    const a = asentar(conocido).get('h0')!;
    const b = asentar(desconocido).get('h0')!;
    expect(finita(b)).toBe(true);
    expect(radio(b)).toBeCloseTo(radio(a), 6);
  });

  it('paso3d con 400 nodos tarda menos de 8 ms por paso (el mejor de 30 pasos, para medir el algoritmo y no la carga de la máquina)', () => {
    const g = grafoGrande(400);
    const visibles = new Set(g.nodos.map((n) => n.id));
    const pos = new Map<string, Posicion3>();
    let s = 1;
    for (const id of visibles) pos.set(id, posicionInicial3d(g, pos, id, s++));
    for (let i = 0; i < 10; i++) paso3d(g, visibles, pos, 1); // calentar
    const tiempos: number[] = [];
    for (let i = 0; i < 30; i++) {
      const t0 = performance.now();
      paso3d(g, visibles, pos, 0.5);
      tiempos.push(performance.now() - t0);
    }
    tiempos.sort((x, y) => x - y);
    // En esta máquina la mediana ronda los 3 ms; con la suite entera en paralelo puede
    // doblarse, por eso el umbral se aplica al mínimo (una regresión del algoritmo lo sube igual).
    expect(tiempos[0]!, `mínimo ${tiempos[0]!.toFixed(2)} ms, mediana ${tiempos[15]!.toFixed(2)} ms`).toBeLessThan(8);
    for (const p of pos.values()) expect(finita(p)).toBe(true);
    // Y el orden de pintado de esos 400 también es barato y completo.
    const t0 = performance.now();
    const orden = ordenarPorProfundidad(visibles, pos, camaraInicial());
    expect(performance.now() - t0).toBeLessThan(8);
    expect(orden.length).toBe(400);
  });

  it('separa el árbol de muestra en tres dimensiones con el tronco fijo', () => {
    const e = estadoDeMuestra();
    const inv = e.investigaciones[0]!;
    const g = construirArbol(e, inv);
    const visibles = visiblesIniciales(g, e.hipotesis.filter((h) => h.investigacionId === inv.id));
    const pos = new Map<string, Posicion3>();
    let s = 1;
    for (const id of visibles) pos.set(id, posicionInicial3d(g, pos, id, s++));
    for (let i = 0; i < 240; i++) paso3d(g, visibles, pos, Math.max(0.05, 1 - i / 240));
    expect(pos.get('objetivo')).toMatchObject({ x: 0, y: 0, z: 0 });
    const ids = [...visibles];
    let minimo = Infinity;
    for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
      const a = pos.get(ids[i]!)!;
      const b = pos.get(ids[j]!)!;
      minimo = Math.min(minimo, Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z));
    }
    expect(minimo).toBeGreaterThan(8);
    for (const p of pos.values()) expect(finita(p)).toBe(true);
    // Usa la tercera dimensión: no todo queda en un plano.
    expect([...pos.values()].some((p) => Math.abs(p.z) > 20)).toBe(true);
    // Todo lo visible se proyecta con una cámara razonable, ordenado de lejos a cerca.
    const c = camaraInicial();
    const orden = ordenarPorProfundidad(ids, pos, c);
    expect(orden.length).toBe(ids.length);
    const profundidades = orden.map((id) => proyectar(pos.get(id)!, c, ANCHO, ALTO).profundidad);
    for (let i = 1; i < profundidades.length; i++) expect(profundidades[i]!).toBeLessThanOrEqual(profundidades[i - 1]! + 1e-9);
  });
});
