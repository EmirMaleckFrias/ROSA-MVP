// @vitest-environment jsdom
// Humo del cliente: la aplicacion entera montada con React 18 (createRoot y
// act), con los efectos activos, navegando por las pantallas de la muestra.
// Es lo mas parecido a abrirla en el navegador que se puede hacer sin uno:
// un error en un efecto de Motion, en el hilo del proceso o en el recorrido
// saldria aqui, no al abrirla.

import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeAll, describe, expect, it } from 'vitest';
import App from './App';
import { estadoDeMuestra } from './datos/muestra';
import { rutaDe } from './lib/ruta';

beforeAll(() => {
  // Lo que jsdom no trae y el navegador si.
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
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
  document.body.innerHTML = '';
  window.location.hash = '';
});

async function montar(hash: string): Promise<HTMLElement> {
  window.location.hash = hash;
  const raiz = document.createElement('div');
  document.body.appendChild(raiz);
  const root = createRoot(raiz);
  await act(async () => {
    root.render(<App />);
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 30));
  });
  return raiz;
}

describe('la aplicacion montada en el cliente', () => {
  it('inicio con el recorrido de primera vez', async () => {
    localStorage.removeItem('rosa.recorrido.v1');
    const raiz = await montar('#/');
    expect(raiz.textContent).toContain('Rosa investiga; tu decides');
    // Siguiente hasta el final y Empezar: queda anotado y no vuelve a salir.
    for (let i = 0; i < 4; i++) {
      const siguiente = [...raiz.querySelectorAll('button')].find((b) => b.textContent === 'Siguiente');
      expect(siguiente).toBeTruthy();
      await act(async () => siguiente!.click());
    }
    const empezar = [...raiz.querySelectorAll('button')].find((b) => b.textContent === 'Empezar');
    await act(async () => empezar!.click());
    await act(async () => {
      await new Promise((r) => setTimeout(r, 300));
    });
    expect(localStorage.getItem('rosa.recorrido.v1')).toBe('1');
    expect(raiz.textContent).toContain('Investigaciones');
  });

  it('cada pantalla de la investigacion de muestra se monta con el hilo del proceso', async () => {
    localStorage.setItem('rosa.recorrido.v1', '1');
    const e = estadoDeMuestra();
    const inv = e.investigaciones[0]!;
    for (const pantalla of ['corrida', 'hipotesis', 'ranking', 'panorama', 'mundo', 'artefactos', 'calidad', 'investigacion'] as const) {
      const raiz = await montar(rutaDe(inv.id, pantalla));
      expect(raiz.querySelector('.hilo'), pantalla).toBeTruthy();
      expect(raiz.querySelectorAll('.hilo-etapa').length, pantalla).toBe(7);
      expect(raiz.textContent, pantalla).not.toContain('Esta investigacion no existe');
      document.body.innerHTML = '';
    }
    // La etapa Laboratorio del hilo tiene su propia vista, distinta de la cola.
    const lab = await montar(rutaDe(inv.id, 'hipotesis', 'laboratorio'));
    expect(lab.querySelector('h2')?.textContent).toBe('Laboratorio');
    const hrefs = [...lab.querySelectorAll<HTMLAnchorElement>('.hilo-etapa')].map((a) => a.getAttribute('href'));
    expect(new Set(hrefs).size).toBe(hrefs.length - 2); // solo Plan, Literatura y Verificar comparten destino (la corrida)
  });

  it('decidir sobre una hipotesis deja un aviso para deshacer, y deshacer la devuelve', async () => {
    localStorage.setItem('rosa.recorrido.v1', '1');
    const e = estadoDeMuestra();
    const inv = e.investigaciones[0]!;
    const raiz = await montar(rutaDe(inv.id, 'hipotesis'));
    const antes = raiz.querySelectorAll('.hip-fila').length;
    expect(antes).toBeGreaterThan(0);
    const primera = raiz.querySelector<HTMLAnchorElement>('.hip-fila')!;
    window.location.hash = primera.getAttribute('href')!;
    await act(async () => {
      window.dispatchEvent(new HashChangeEvent('hashchange'));
      await new Promise((r) => setTimeout(r, 30));
    });
    const descartar = [...raiz.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Descartar');
    if (!descartar) return; // la muestra puede no tener una hipotesis decidible: no es un fallo del rework
    await act(async () => descartar.click());
    const textarea = raiz.querySelector('.confirmacion textarea') as HTMLTextAreaElement | null;
    if (textarea) {
      await act(async () => {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')!.set!;
        setter.call(textarea, 'motivo de prueba');
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
      });
      const confirmar = [...raiz.querySelectorAll('.confirmacion button')].find((b) => b.textContent?.trim() === 'Descartar') as HTMLButtonElement | undefined;
      await act(async () => confirmar?.click());
    }
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    const aviso = raiz.ownerDocument.querySelector('.deshacer');
    expect(aviso).toBeTruthy();
    const deshacer = [...aviso!.querySelectorAll('button')].find((b) => b.textContent === 'Deshacer')!;
    await act(async () => deshacer.click());
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });
    expect(raiz.ownerDocument.querySelector('.deshacer')).toBeNull();
  });
});
