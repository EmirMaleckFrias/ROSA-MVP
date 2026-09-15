// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAhora } from './useAhora';

function Reloj({ intervalo }: { intervalo?: number }) {
  return <output>{useAhora(intervalo)}</output>;
}

describe('reloj en vivo', () => {
  let nodo: HTMLDivElement;
  let root: Root;
  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    vi.useFakeTimers();
    vi.setSystemTime(100_000);
    nodo = document.createElement('div');
    root = createRoot(nodo);
  });
  afterEach(() => {
    act(() => root.unmount());
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
  it('avanza cada segundo sin recibir datos del servidor', () => {
    act(() => root.render(<Reloj />));
    for (let segundo = 1; segundo <= 10; segundo++) {
      act(() => vi.advanceTimersByTime(1000));
      expect(nodo.textContent).toBe(String(100_000 + segundo * 1000));
    }
  });
  it('recupera la hora real al volver a la pestaña sin sumar ticks perdidos', () => {
    act(() => root.render(<Reloj />));
    vi.setSystemTime(900_000);
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    expect(nodo.textContent).toBe('900000');
    vi.setSystemTime(950_000);
    act(() => window.dispatchEvent(new Event('focus')));
    expect(nodo.textContent).toBe('950000');
  });
  it('respeta intervalos específicos y retira el temporizador al desmontar', () => {
    act(() => root.render(<Reloj intervalo={250} />));
    act(() => vi.advanceTimersByTime(250));
    expect(nodo.textContent).toBe('100250');
    act(() => root.render(<Reloj intervalo={1000} />));
    expect(vi.getTimerCount()).toBe(1);
    act(() => root.render(null));
    expect(vi.getTimerCount()).toBe(0);
  });
});
