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
  it('no muestra el login durante una comprobación lenta de sesión', async () => {
    let resolver!: (valor: unknown) => void;
    vi.stubGlobal('fetch', vi.fn(() => new Promise(r => { resolver = r; })));
    await montar();
    expect(nodo.textContent).toContain('Cargando ROSA2018');
    expect(nodo.querySelector('form')).toBeNull();
    expect(nodo.textContent).not.toContain('Investigaciones privadas');
    await act(async () => resolver({ ok: true, json: async () => ({ ...estado, correo: 'equipo@alzheimerproject.com' }) }));
    expect(nodo.textContent).toContain('Investigaciones privadas');
    expect(nodo.querySelector('form')).toBeNull();
  });
  it('no monta investigaciones ni conecta al almacén antes de verificar la sesión', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => estado }));
    await montar();
    expect(nodo.textContent).not.toContain('Investigaciones privadas');
    expect(conectar).not.toHaveBeenCalled();
    expect(nodo.querySelector('img')?.getAttribute('src')).toBe('/arbol-marca.png');
    expect((nodo.querySelector('.acceso-continuar') as HTMLButtonElement).disabled).toBe(false);
    expect(nodo.textContent).toContain('Contraseña');
    expect(nodo.textContent).not.toContain('ROSA2018 aún no está conectado');
    expect(nodo.textContent).not.toContain('Entrar sin verificación');
    expect(nodo.textContent).not.toContain('Registrarse');
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
  it('elimina un enlace antiguo de la URL sin presentarlo como opción de acceso', async () => {
    window.location.hash = '#acceso=enlace-de-prueba';
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => estado });
    vi.stubGlobal('fetch', fetch);
    await montar();
    expect(window.location.hash).toBe('');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]?.[0]).toBe('/api/acceso/estado');
    expect(nodo.textContent).toContain('Iniciar sesión');
    expect(nodo.textContent).not.toContain('Confirmar e iniciar sesión');
  });
  it('envía correo y contraseña al único endpoint de inicio de sesión', async () => {
    const fetch = vi.fn(async (url: string) => ({ ok: true, json: async () => (String(url).endsWith('/entrar') ? { ok: true } : estado) }));
    vi.stubGlobal('fetch', fetch);
    const asignar = vi.fn();
    vi.stubGlobal('location', { ...window.location, assign: asignar, hash: '', pathname: '/', search: '' });
    await montar();
    const correo = nodo.querySelector('#acceso-correo') as HTMLInputElement;
    const contrasena = nodo.querySelector('#acceso-contrasena') as HTMLInputElement;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!;
      setter.call(correo, 'ana@alzheimerproject.com');
      correo.dispatchEvent(new Event('input', { bubbles: true }));
      setter.call(contrasena, 'secreto de prueba');
      contrasena.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => {
      nodo.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(fetch.mock.calls.some((c) => String(c[0]).endsWith('/api/acceso/entrar'))).toBe(true);
    expect(fetch.mock.calls.some((c) => String(c[0]).endsWith('/api/acceso/entrar_sin_verificar'))).toBe(false);
    expect(asignar).toHaveBeenCalledWith('/');
  });
  it('muestra un error de autenticación sin abrir ninguna puerta alternativa', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => ({ ok: !String(url).endsWith('/entrar'), json: async () => (String(url).endsWith('/entrar') ? { detail: 'Correo o contraseña incorrectos' } : estado) })));
    await montar();
    const correo = nodo.querySelector('#acceso-correo') as HTMLInputElement;
    const contrasena = nodo.querySelector('#acceso-contrasena') as HTMLInputElement;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!;
      setter.call(correo, 'ana@alzheimerproject.com');
      correo.dispatchEvent(new Event('input', { bubbles: true }));
      setter.call(contrasena, 'incorrecta');
      contrasena.dispatchEvent(new Event('input', { bubbles: true }));
      nodo.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(nodo.textContent).toContain('Correo o contraseña incorrectos');
    expect(nodo.textContent).not.toContain('Entrar sin verificación');
  });
});
