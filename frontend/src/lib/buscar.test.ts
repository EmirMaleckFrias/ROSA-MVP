import { describe, expect, it } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import { buscar } from './buscar';

describe('buscar', () => {
  const e = estadoDeMuestra();
  it('encuentra hipotesis, hechos y fuentes sin importar acentos ni mayusculas', () => {
    const r = buscar(e, 'inv-1', 'NLRP3');
    expect(r.some((x) => x.tipo === 'hipotesis')).toBe(true);
    expect(r.some((x) => x.tipo === 'hecho')).toBe(true);
    expect(r.some((x) => x.tipo === 'fuente')).toBe(true);
    expect(buscar(e, 'inv-1', 'nlrp3').length).toBe(r.length);
  });
  it('encuentra por DOI y por NCT', () => {
    expect(buscar(e, 'inv-1', '10.1002/trc2').some((x) => x.tipo === 'fuente')).toBe(true);
    expect(buscar(e, 'inv-1', 'NCT04777396').some((x) => x.tipo === 'fuente')).toBe(true);
  });
  it('encuentra iteraciones por el titulo de una pista y artefactos por contenido', () => {
    expect(buscar(e, 'inv-1', 'ARIA en portadores').some((x) => x.tipo === 'iteracion')).toBe(true);
    expect(buscar(e, 'inv-1', 'Preguntas cerradas').some((x) => x.tipo === 'artefacto')).toBe(true);
  });
  it('menos de dos caracteres no busca y respeta el maximo', () => {
    expect(buscar(e, 'inv-1', 'a')).toEqual([]);
    expect(buscar(e, 'inv-1', 'a ', 3).length).toBeLessThanOrEqual(3);
  });
  it('no devuelve duplicados', () => {
    const r = buscar(e, 'inv-1', 'tau');
    const claves = r.map((x) => `${x.tipo}|${x.titulo}|${x.ruta}`);
    expect(new Set(claves).size).toBe(claves.length);
  });
});
