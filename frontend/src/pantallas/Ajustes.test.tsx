// @vitest-environment jsdom
// La pantalla de Ajustes montada de verdad (createRoot y act, como
// Ranking.test.tsx) dentro de la puerta de acceso, con el servidor simulado.
// El bloque de sesión (correo, si la cuenta administra la instalación y el
// botón "Cerrar sesión") vive aquí, en la sección "Sesión", y ya no en la
// barra lateral (18 de septiembre de 2026). Cerrar sesión sigue llamando a
// /api/acceso/salir y volviendo a la raíz, igual que antes del traslado.
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { Acceso } from '../componentes/Acceso';
import { BarraLateral } from '../componentes/BarraLateral';
import { estadoDeMuestra } from '../datos/muestra';
import { Ajustes } from './Ajustes';

vi.mock('../datos/almacen', () => ({
  // Cada acción devuelve una promesa que no resuelve: los bloques que piden
  // datos al servidor (integridad, espejo) se quedan en "cargando" y no
  // estorban a la sección Sesión, que no depende de ellos.
  acciones: new Proxy({}, { get: () => () => new Promise(() => undefined) }),
  aplicar: () => undefined,
  cabeceras: () => ({ 'X-Rosa': '1', 'Content-Type': 'application/json' }),
  modoActual: () => 'muestra',
  QUIEN: 'la persona responsable',
  avisar: () => undefined,
  conectar: vi.fn().mockResolvedValue('servidor'),
}));

beforeAll(() => {
  (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
  };
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  window.matchMedia = (q: string) => ({ matches: q.includes('reduce'), media: q, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false }) as MediaQueryList;
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => undefined;
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
  vi.unstubAllGlobals();
});

const CORREO = 'emir.malek@alzheimerproject.com';

/** Un servidor de mentira: /api/acceso/estado devuelve la sesión indicada y
 *  todo lo demás responde vacío y bien. Devuelve el espía para inspeccionarlo. */
type Respuesta = { ok: boolean; json: () => Promise<unknown> };
function servidorFalso(administrador: boolean) {
  const fetch = vi.fn<(url: string, init?: RequestInit) => Promise<Respuesta>>(async (url) => {
    const u = String(url);
    if (u.endsWith('/api/acceso/estado')) return { ok: true, json: async () => ({ correo: CORREO, administrador, correoConfigurado: false, instalacionLocal: false }) };
    return { ok: true, json: async () => ({}) };
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

async function montarConSesion(administrador: boolean) {
  const fetch = servidorFalso(administrador);
  const asignar = vi.fn();
  vi.stubGlobal('location', { ...window.location, assign: asignar, hash: '', pathname: '/', search: '' });
  await act(async () => root.render(<Acceso><Ajustes estado={estadoDeMuestra()} ahora={Date.now()} /></Acceso>));
  return { fetch, asignar };
}

const titulos = () => [...nodo.querySelectorAll('.seccion-titulo h3')].map((h) => h.textContent?.trim() ?? '');
const botonSalir = () => [...nodo.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Cerrar sesión') ?? null;

describe('la sección Sesión de Ajustes', () => {
  it('muestra el correo, que la cuenta administra la instalación y el botón de cerrar sesión', async () => {
    await montarConSesion(true);
    expect(titulos().some((t) => t.startsWith('Sesión'))).toBe(true);
    expect(nodo.textContent).toContain(CORREO);
    expect(nodo.textContent).toContain('Cuenta administradora');
    expect(nodo.textContent).not.toContain('sin permisos de administración');
    expect(botonSalir()).not.toBeNull();
  });

  it('dice cuando la cuenta no administra la instalación', async () => {
    await montarConSesion(false);
    expect(nodo.textContent).toContain(CORREO);
    expect(nodo.textContent).toContain('sin permisos de administración');
    expect(nodo.textContent).not.toContain('Cuenta administradora');
  });

  it('va antes que el resto de secciones, para que se encuentre sin bajar', async () => {
    await montarConSesion(true);
    const t = titulos();
    const sesion = t.findIndex((x) => x.startsWith('Sesión'));
    const autonomia = t.findIndex((x) => x.startsWith('Autonomía'));
    expect(sesion).toBeGreaterThanOrEqual(0);
    expect(autonomia).toBeGreaterThan(sesion);
  });

  it('cerrar sesión llama a /api/acceso/salir por POST y vuelve a la raíz', async () => {
    const { fetch, asignar } = await montarConSesion(true);
    const boton = botonSalir();
    expect(boton).not.toBeNull();
    await act(async () => {
      boton!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((r) => setTimeout(r, 20));
    });
    const salida = fetch.mock.calls.find((c) => String(c[0]).endsWith('/api/acceso/salir'));
    expect(salida).toBeDefined();
    expect(salida![1]?.method).toBe('POST');
    expect(asignar).toHaveBeenCalledWith('/');
  });

  it('si el servidor no deja salir, avisa y no recarga', async () => {
    const fetch = servidorFalso(true);
    fetch.mockImplementation(async (url) => {
      const u = String(url);
      if (u.endsWith('/api/acceso/estado')) return { ok: true, json: async () => ({ correo: CORREO, administrador: true, correoConfigurado: false, instalacionLocal: false }) };
      if (u.endsWith('/api/acceso/salir')) return { ok: false, json: async () => ({ detail: 'Sin conexión' }) };
      return { ok: true, json: async () => ({}) };
    });
    const asignar = vi.fn();
    vi.stubGlobal('location', { ...window.location, assign: asignar, hash: '', pathname: '/', search: '' });
    await act(async () => root.render(<Acceso><Ajustes estado={estadoDeMuestra()} ahora={Date.now()} /></Acceso>));
    await act(async () => {
      botonSalir()!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(nodo.querySelector('[role="alert"]')?.textContent).toContain('No se pudo cerrar la sesión');
    expect(asignar).not.toHaveBeenCalled();
  });

  it('sin sesión no pinta la sección ni el botón', async () => {
    servidorFalso(true);
    await act(async () => root.render(<Ajustes estado={estadoDeMuestra()} ahora={Date.now()} />));
    expect(titulos().some((t) => t.startsWith('Sesión'))).toBe(false);
    expect(botonSalir()).toBeNull();
    expect(nodo.textContent).not.toContain(CORREO);
  });
});

describe('la barra lateral tras el traslado', () => {
  it('conserva el enlace a Ajustes y la frase de pie, y ya no lleva el bloque de sesión', async () => {
    await act(async () => root.render(<BarraLateral estado={estadoDeMuestra()} ruta={{ tipo: 'ajustes' }} abierta={false} onCerrar={() => undefined} onBuscar={() => undefined} />));
    expect(nodo.textContent).toContain('Ajustes');
    expect(nodo.textContent).toContain('ROSA2018 investiga; la persona decide.');
    expect(nodo.textContent).not.toContain('Cerrar sesión');
    expect(nodo.querySelector('.cuenta-actual')).toBeNull();
    expect(nodo.querySelector('a[href="#/ajustes"]')?.getAttribute('aria-current')).toBe('page');
  });
});
