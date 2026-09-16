// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import { Calidad } from './Calidad';
import { fijarModo } from '../lib/modo';

afterEach(() => vi.unstubAllGlobals());

it('controla GEPA mediante el servidor y comunica errores sin fingir éxito', async () => {
  fijarModo('detalle');
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.stubGlobal('IntersectionObserver', class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
  const estado = estadoDeMuestra();
  estado.gepa = [];
  const fetch = vi.fn().mockResolvedValue({ ok: false, status: 403 });
  vi.stubGlobal('fetch', fetch);
  const contenedor = document.createElement('div');
  const root = createRoot(contenedor);
  try {
    await act(async () => root.render(<Calidad inv={estado.investigaciones[0]!} estado={estado} ahora={Date.now()} />));
    const boton = [...contenedor.querySelectorAll('button')].find(b => b.textContent === 'Pausar promociones')!;
    expect(boton).toBeDefined();
    await act(async () => boton.click());
    expect(fetch).toHaveBeenCalledWith('/api/gepa/pausar', expect.objectContaining({ method: 'POST', headers: expect.objectContaining({ 'X-Rosa': '1' }) }));
    expect(contenedor.textContent).toContain('Solo administración');
    expect(contenedor.textContent).not.toContain('Cambio confirmado');
    fetch.mockResolvedValue({ ok: true });
    await act(async () => boton.click());
    expect(contenedor.textContent).toContain('Cambio confirmado');
  } finally {
    await act(async () => root.unmount());
    fijarModo('sencillo');
  }
});
