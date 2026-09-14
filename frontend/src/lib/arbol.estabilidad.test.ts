// Estabilidad de la disposición por fuerzas con muchos nodos y un arrastre.
// Emir (14 de septiembre de 2026): "en el árbol, cuando hay muchos nodos y
// jalas uno como que se empieza a volver loco". Se despliega todo, se
// arrastra un nodo 300 unidades en 60 fotogramas con la energía que usa la
// pantalla (0,35) y se mide la velocidad de los demás: ninguno puede salir
// disparado ni quedar temblando.
import { describe, expect, it } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import { construirArbol, paso, posicionInicial, type Grafo, type NodoArbol, type Posicion } from './arbol';

function montar() {
  const e = estadoDeMuestra();
  const inv = e.investigaciones[0]!;
  const g = construirArbol(e, inv);
  const visibles = new Set(g.nodos.map((n) => n.id));
  const pos = new Map<string, Posicion>();
  let semilla = 1;
  for (const n of g.nodos) pos.set(n.id, posicionInicial(g, pos, n.id, semilla++));
  // Se deja asentar como hace la pantalla (alfa cae 0,975 por fotograma, dos pasos por fotograma).
  let alfa = 1;
  while (alfa > 0.03) {
    for (let k = 0; k < 2; k++) paso(g, visibles, pos, alfa);
    alfa *= 0.975;
  }
  return { g, visibles, pos };
}

/** Un árbol sintético grande: tronco, 8 ramas, 12 hipótesis por rama con dos
 *  entidades y una fuente cada una (unos 250 nodos), como una investigación
 *  con varias iteraciones desplegada del todo. */
function montarGrande() {
  const nodos: NodoArbol[] = [{ id: 'objetivo', tipo: 'objetivo', etiqueta: 'Objetivo de la investigación', peso: 4, iteracion: 1 }];
  const enlaces: Grafo['enlaces'] = [];
  for (let r = 0; r < 8; r++) {
    nodos.push({ id: `rama-${r}`, tipo: 'rama', etiqueta: `Rama número ${r} del árbol`, peso: 3, iteracion: 1 });
    enlaces.push({ de: 'objetivo', a: `rama-${r}`, tipo: 'rama' });
    for (let h = 0; h < 12; h++) {
      const id = `hip-${r}-${h}`;
      nodos.push({ id, tipo: 'hipotesis', etiqueta: `Hipótesis ${h} de la rama ${r} con una etiqueta larga`, peso: 2, iteracion: 1 + (h % 3) });
      enlaces.push({ de: `rama-${r}`, a: id, tipo: 'rama' });
      for (let k = 0; k < 2; k++) {
        const ent = `ent-${r}-${(h + k) % 6}`;
        if (!nodos.some((n) => n.id === ent)) nodos.push({ id: ent, tipo: 'entidad', etiqueta: `GEN${r}${(h + k) % 6}`, peso: 1.5, iteracion: 1 });
        enlaces.push({ de: id, a: ent, tipo: 'entidad' });
      }
      nodos.push({ id: `fu-${r}-${h}`, tipo: 'fuente', etiqueta: `Autor et al., 202${h % 6}`, peso: 1, iteracion: 1 });
      enlaces.push({ de: id, a: `fu-${r}-${h}`, tipo: 'cita' });
    }
  }
  const porId = new Map(nodos.map((n) => [n.id, n]));
  const vecinos = new Map<string, Set<string>>();
  for (const e of enlaces) {
    (vecinos.get(e.de) ?? vecinos.set(e.de, new Set()).get(e.de)!).add(e.a);
    (vecinos.get(e.a) ?? vecinos.set(e.a, new Set()).get(e.a)!).add(e.de);
  }
  const g: Grafo = { nodos, enlaces, porId, vecinos, iteracionMax: 3 };
  const visibles = new Set(nodos.map((n) => n.id));
  const pos = new Map<string, Posicion>();
  let semilla = 1;
  for (const n of nodos) pos.set(n.id, posicionInicial(g, pos, n.id, semilla++));
  let alfa = 1;
  while (alfa > 0.03) {
    for (let k = 0; k < 2; k++) paso(g, visibles, pos, alfa);
    alfa *= 0.975;
  }
  return { g, visibles, pos };
}

const velocidadMax = (pos: Map<string, Posicion>, salvo?: string) => Math.max(...[...pos.entries()].filter(([id]) => id !== salvo).map(([, p]) => Math.hypot(p.vx, p.vy)));

describe('estabilidad del árbol', () => {
  it('con todo desplegado, arrastrar un nodo no dispara a los demás', () => {
    const { g, visibles, pos } = montar();
    expect(g.nodos.length).toBeGreaterThan(15);
    const id = g.nodos.find((n) => n.tipo === 'hipotesis')!.id;
    const p = pos.get(id)!;
    p.fijo = true;
    let pico = 0;
    for (let f = 0; f < 60; f++) {
      p.x += 5;
      p.vx = 0;
      p.vy = 0;
      for (let k = 0; k < 2; k++) paso(g, visibles, pos, 0.35);
      pico = Math.max(pico, velocidadMax(pos, id));
    }
    // Un nodo que se mueve más de 25 unidades por paso a esta energía se ve como un salto.
    expect(pico).toBeLessThan(25);
    for (const q of pos.values()) {
      expect(Number.isFinite(q.x) && Number.isFinite(q.y)).toBe(true);
      expect(Math.hypot(q.x, q.y)).toBeLessThan(2500);
    }
  });

  it('al soltar, el árbol se asienta: la velocidad cae por debajo de 0,5 en menos de 200 fotogramas', () => {
    const { g, visibles, pos } = montar();
    const id = g.nodos.find((n) => n.tipo === 'hipotesis')!.id;
    const p = pos.get(id)!;
    p.x += 300;
    let alfa = 0.35;
    let fotogramas = 0;
    while (fotogramas < 200) {
      for (let k = 0; k < 2; k++) paso(g, visibles, pos, alfa);
      alfa = Math.max(0.02, alfa * 0.975);
      fotogramas++;
      if (velocidadMax(pos) < 0.5) break;
    }
    expect(fotogramas).toBeLessThan(200);
  });

  it('con más de 200 nodos desplegados, arrastrar sigue siendo suave y el árbol se asienta', () => {
    const { g, visibles, pos } = montarGrande();
    expect(g.nodos.length).toBeGreaterThan(200);
    const id = 'hip-3-5';
    const p = pos.get(id)!;
    p.fijo = true;
    let pico = 0;
    for (let f = 0; f < 60; f++) {
      p.x += 5;
      p.vx = 0;
      p.vy = 0;
      for (let k = 0; k < 2; k++) paso(g, visibles, pos, 0.35);
      pico = Math.max(pico, velocidadMax(pos, id));
    }
    expect(pico).toBeLessThan(25);
    p.fijo = false;
    let alfa = 0.35;
    let fotogramas = 0;
    while (fotogramas < 300) {
      for (let k = 0; k < 2; k++) paso(g, visibles, pos, alfa);
      alfa = Math.max(0.02, alfa * 0.975);
      fotogramas++;
      if (velocidadMax(pos) < 0.5) break;
    }
    expect(fotogramas).toBeLessThan(300);
    for (const q of pos.values()) expect(Number.isFinite(q.x) && Number.isFinite(q.y)).toBe(true);
  });
});
