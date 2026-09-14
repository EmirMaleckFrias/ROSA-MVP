// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Acceso } from './Acceso';
import { conectar } from '../datos/almacen';

vi.mock('../datos/almacen', () => ({ conectar: vi.fn().mockResolvedValue('servidor'), cabeceras: () => ({ 'X-Rosa': '1', 'Content-Type': 'application/json' }) }));
let root: Root;
let nodo: HTMLDivElement;
const estado = { correo: null, administrador: false, correoConfigurado: false, instalacionLocal: false };
beforeEach(() => {
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.clearAllMocks();
  window.history.replaceState(null, '', '/');
  nodo = document.createElement('div');
  document.body.append(nodo);
  root = createRoot(nodo);
});
afterEach(async () => { await act(async () => root.unmount()); nodo.remove(); vi.unstubAllGlobals(); });
async function montar() { await act(async () => root.render(<Acceso><div>Investigaciones privadas</div></Acceso>)); }

describe('acceso corporativo', () => {
  it('no monta investigaciones ni conecta al almacén antes de verificar la sesión', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => estado }));
    await montar();
    expect(nodo.textContent).not.toContain('Investigaciones privadas');
    expect(conectar).not.toHaveBeenCalled();
    expect(nodo.querySelector('img')?.getAttribute('src')).toBe('/arbol-marca.png');
    expect((nodo.querySelector('.acceso-continuar') as HTMLButtonElement).disabled).toBe(true);
    const registro = [...nodo.querySelectorAll('button')].find((b) => b.textContent === 'Registrarse')!;
    await act(async () => registro.click());
    expect(nodo.textContent).toContain('La cuenta se crea después de confirmar');
  });
  it('solo carga las investigaciones cuando existe una sesión verificada', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ...estado, correo: 'equipo@alzheimerproject.com' }) }));
    await montar();
    expect(conectar).toHaveBeenCalledWith(false);
    expect(nodo.textContent).toContain('Investigaciones privadas');
  });
  it('no cae a la muestra ni muestra datos si falla el estado', async () => {
    vi.mocked(conectar).mockRejectedValueOnce(new Error('sin servidor'));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ...estado, correo: 'equipo@alzheimerproject.com' }) }));
    await montar();
    expect(nodo.textContent).not.toContain('Investigaciones privadas');
    expect(nodo.textContent).toContain('No se puede conectar');
  });
  it('el enlace se quita de la URL y no se consume automáticamente', async () => {
    window.location.hash = '#acceso=enlace-de-prueba';
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => estado });
    vi.stubGlobal('fetch', fetch);
    await montar();
    expect(window.location.hash).toBe('');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]?.[0]).toBe('/api/acceso/estado');
    expect(nodo.textContent).toContain('Confirmar e iniciar sesión');
  });
  it('reconoce un enlace abierto en la misma pestaña sin recargar', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => estado }));
    await montar();
    await act(async () => {
      window.location.hash = '#acceso=otro-enlace';
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    expect(nodo.textContent).toContain('Confirmar e iniciar sesión');
    expect(window.location.hash).toBe('');
  });
  it('tras solicitar el enlace muestra el estado "Revisa tu correo" con el mensaje en tono de éxito', async () => {
    const fetch = vi.fn(async (url: string) => {
      if (String(url).endsWith('/solicitar')) return { ok: true, json: async () => ({ mensaje: 'Enlace enviado. Caduca en 15 minutos.' }) };
      return { ok: true, json: async () => ({ ...estado, correoConfigurado: true }) };
    });
    vi.stubGlobal('fetch', fetch);
    await montar();
    const campo = nodo.querySelector('#acceso-correo') as HTMLInputElement;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!;
      setter.call(campo, 'ana@alzheimerproject.com');
      campo.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => {
      nodo.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(nodo.textContent).toContain('Revisa tu correo');
    expect(nodo.textContent).toContain('ana@alzheimerproject.com');
    expect(nodo.querySelector('.acceso-mensaje-ok')?.textContent).toContain('Enlace enviado');
    expect(nodo.querySelector('.acceso-mensaje-error')).toBeNull();
    const otro = [...nodo.querySelectorAll('button')].find((b) => b.textContent === 'Usar otro correo')!;
    await act(async () => otro.click());
    expect(nodo.textContent).toContain('Continúa tu investigación');
  });
});
