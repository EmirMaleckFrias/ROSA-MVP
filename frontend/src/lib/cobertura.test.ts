import { describe, expect, it } from 'vitest';
import { curvaDescubrimiento, faltanParaCobertura, fraccionCubierta, veredictoConCobertura } from './cobertura';

describe('cobertura', () => {
  it('la fraccion crece con lo leido y satura', () => {
    expect(fraccionCubierta(0, 50)).toBe(0);
    expect(fraccionCubierta(50, 50)).toBeCloseTo(0.632, 3);
    expect(fraccionCubierta(150, 50)).toBeCloseTo(0.95, 2);
    expect(fraccionCubierta(10, 0)).toBe(0);
  });
  it('dice cuantos faltan para un objetivo', () => {
    const c = { tema: 'x', leidos: 82, fraccion: 0.61, tau: 90 };
    expect(faltanParaCobertura(c, 0.5)).toBe(0);
    expect(faltanParaCobertura(c, 0.9)).toBe(126);
    expect(faltanParaCobertura(c, 1)).toBe(Number.POSITIVE_INFINITY);
  });
  it('degrada la ausencia refutada cuando la busqueda no converge', () => {
    const baja = { tema: 'Seguridad', leidos: 28, fraccion: 0.42, tau: 50 };
    const r = veredictoConCobertura('ausencia_refutada', baja);
    expect(r.veredicto).toBe('sin_verificar');
    expect(r.nota).toMatch(/42 %/);
  });
  it('no toca la ausencia refutada con cobertura alta ni los otros veredictos', () => {
    const alta = { tema: 'Biomarcadores', leidos: 144, fraccion: 0.93, tau: 55 };
    expect(veredictoConCobertura('ausencia_refutada', alta)).toEqual({ veredicto: 'ausencia_refutada', nota: null });
    expect(veredictoConCobertura('no_sostenida', { tema: 'x', leidos: 1, fraccion: 0.1, tau: 50 }).veredicto).toBe('no_sostenida');
    expect(veredictoConCobertura('ausencia_refutada', null).veredicto).toBe('ausencia_refutada');
  });
  it('la curva es monotona y empieza en cero', () => {
    const pts = curvaDescubrimiento({ tema: 'x', leidos: 80, fraccion: 0.6, tau: 90 }, 10);
    expect(pts[0]!.f).toBe(0);
    for (let i = 1; i < pts.length; i++) expect(pts[i]!.f).toBeGreaterThan(pts[i - 1]!.f);
  });
});
