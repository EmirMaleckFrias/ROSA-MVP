import { describe, expect, it } from 'vitest';
import { diferenciarLineas, resumenDiff } from './diff';

describe('diferenciarLineas', () => {
  it('textos iguales: todo igual', () => {
    const r = diferenciarLineas('a\nb', 'a\nb');
    expect(r.every((l) => l.tipo === 'igual')).toBe(true);
    expect(r).toHaveLength(2);
  });
  it('detecta una linea anadida en medio', () => {
    const r = diferenciarLineas('a\nc', 'a\nb\nc');
    expect(r).toEqual([
      { tipo: 'igual', texto: 'a' },
      { tipo: 'anadida', texto: 'b' },
      { tipo: 'igual', texto: 'c' },
    ]);
  });
  it('detecta una linea quitada y una cambiada', () => {
    const r = diferenciarLineas('a\nb\nc', 'a\nx');
    expect(r.filter((l) => l.tipo === 'quitada').map((l) => l.texto)).toEqual(['b', 'c']);
    expect(r.filter((l) => l.tipo === 'anadida').map((l) => l.texto)).toEqual(['x']);
  });
  it('vacio contra algo: todo anadido; algo contra vacio: todo quitado', () => {
    expect(diferenciarLineas('', 'a\nb').map((l) => l.tipo)).toEqual(['anadida', 'anadida']);
    expect(diferenciarLineas('a', '').map((l) => l.tipo)).toEqual(['quitada']);
    expect(diferenciarLineas('', '')).toEqual([]);
  });
  it('conserva las lineas en blanco como lineas', () => {
    const r = diferenciarLineas('a\n\nb', 'a\n\nb');
    expect(r).toHaveLength(3);
  });
  it('resume el recuento', () => {
    expect(resumenDiff(diferenciarLineas('a\nb\nc', 'a\nx'))).toEqual({ anadidas: 1, quitadas: 2 });
  });
});
