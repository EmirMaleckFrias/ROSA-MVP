import { describe, expect, it } from 'vitest';
import {
  formatearCompacto,
  formatearDuracion,
  formatearEntero,
  formatearPorcentaje,
  plural,
  tiempoRelativo,
} from './formato';

describe('formatearDuracion', () => {
  it('usa decimales solo por debajo de 10 s', () => {
    expect(formatearDuracion(800)).toBe('0,8 s');
    expect(formatearDuracion(4_260)).toBe('4,3 s');
    expect(formatearDuracion(41_000)).toBe('41 s');
  });
  it('sube a minutos, horas y dias', () => {
    expect(formatearDuracion(64_000)).toBe('1 min 4 s');
    expect(formatearDuracion(120_000)).toBe('2 min');
    expect(formatearDuracion(31 * 3_600_000)).toBe('31 h');
    expect(formatearDuracion(31 * 3_600_000 + 600_000)).toBe('31 h 10 min');
    expect(formatearDuracion(72 * 3_600_000)).toBe('3 d');
  });
  it('devuelve vacio para cero, negativos y NaN', () => {
    expect(formatearDuracion(0)).toBe('');
    expect(formatearDuracion(-5)).toBe('');
    expect(formatearDuracion(Number.NaN)).toBe('');
  });
});

describe('tiempoRelativo', () => {
  const ahora = 1_000_000_000;
  it('redondea a la unidad legible', () => {
    expect(tiempoRelativo(ahora - 10_000, ahora)).toBe('hace un momento');
    expect(tiempoRelativo(ahora - 6 * 60_000, ahora)).toBe('hace 6 min');
    expect(tiempoRelativo(ahora - 2 * 3_600_000, ahora)).toBe('hace 2 h');
    expect(tiempoRelativo(ahora - 3 * 86_400_000, ahora)).toBe('hace 3 d');
  });
  it('distingue el futuro, salvo el desfase del reloj de pantalla', () => {
    expect(tiempoRelativo(ahora + 5 * 60_000, ahora)).toBe('en 5 min');
    expect(tiempoRelativo(ahora + 10_000, ahora)).toBe('hace un momento');
  });
});

describe('numeros', () => {
  it('pone puntos de miles', () => {
    expect(formatearEntero(48_200_000)).toBe('48.200.000');
    expect(formatearEntero(999)).toBe('999');
    expect(formatearEntero(-1_234)).toBe('-1.234');
  });
  it('compacta con coma decimal', () => {
    expect(formatearCompacto(48_200_000)).toBe('48,2 M');
    expect(formatearCompacto(3_950_000)).toBe('4 M');
    expect(formatearCompacto(12_318)).toBe('12,3 k');
    expect(formatearCompacto(2_318)).toBe('2.318');
    expect(formatearCompacto(412)).toBe('412');
  });
  it('formatea porcentajes', () => {
    expect(formatearPorcentaje(0.891)).toBe('89 %');
    expect(formatearPorcentaje(0.891, 1)).toBe('89,1 %');
    expect(formatearPorcentaje(1)).toBe('100 %');
  });
  it('pluraliza', () => {
    expect(plural(1, 'hipotesis', 'hipotesis')).toBe('1 hipotesis');
    expect(plural(3, 'afirmacion', 'afirmaciones')).toBe('3 afirmaciones');
    expect(plural(2, 'articulo')).toBe('2 articulos');
  });
});
