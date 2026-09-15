// @vitest-environment jsdom
// Arrancar la primera corrida de una investigación pasaba la pantalla de
// "sin corridas" a "corrida 1" en el mismo componente, con más hooks que en
// el render anterior, y React fallaba ("Rendered more hooks than during the
// previous render"). Emir lo vio al lanzar una corrida real, 15 de septiembre
// de 2026. Este test hace esa transición sobre la misma raíz y exige que no
// se lance nada.
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import type { EstadoRosa } from '../datos/tipos';
import { Corrida } from './Corrida';

vi.mock('../datos/almacen', () => ({ acciones: new Proxy({}, { get: () => () => undefined }) }));

beforeAll(() => {
  // Lo que jsdom no trae y el navegador sí (igual que en App.cliente.test.tsx).
  class IO {
    constructor(private cb: IntersectionObserverCallback) {}
    observe(el: Element) {
      this.cb([{ isIntersecting: true, target: el, intersectionRatio: 1 } as IntersectionObserverEntry], this as unknown as IntersectionObserver);
    }
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
  }
  (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IO;
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  if (!window.matchMedia) {
    window.matchMedia = (q: string) => ({ matches: false, media: q, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false }) as MediaQueryList;
  }
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

describe('la pantalla de la corrida', () => {
  it('pasa de "sin corridas" a "corrida 1" sin romper las reglas de los hooks', async () => {
    const base = estadoDeMuestra();
    const inv = base.investigaciones[0]!;
    const sinCorridas: EstadoRosa = { ...base, corridas: base.corridas.filter((c) => c.investigacionId !== inv.id) };
    const errores: unknown[] = [];
    const original = console.error;
    console.error = (...args: unknown[]) => errores.push(args);
    try {
      await act(async () => root.render(<Corrida inv={inv} estado={sinCorridas} ahora={Date.now()} irA={() => undefined} />));
      expect(nodo.textContent).toContain('no tiene corridas');
      await act(async () => root.render(<Corrida inv={inv} estado={base} ahora={Date.now()} irA={() => undefined} />));
      expect(nodo.textContent).not.toContain('no tiene corridas');
      expect(nodo.textContent).toContain('Corrida');
      await act(async () => root.render(<Corrida inv={inv} estado={sinCorridas} ahora={Date.now()} irA={() => undefined} />));
      expect(nodo.textContent).toContain('no tiene corridas');
    } finally {
      console.error = original;
    }
    const conHooks = errores.filter((e) => JSON.stringify(e).includes('hooks'));
    expect(conHooks).toEqual([]);
  });
});
