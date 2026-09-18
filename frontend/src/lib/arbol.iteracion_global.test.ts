import { describe, expect, it } from 'vitest';
import { iteracionObjEn, ordinalesDeIteraciones } from './arbol';

const iter = (id: string, corridaId: string, numero: number, empezadaEn: number, terminadaEn: number | null = empezadaEn + 1000) => ({ id, corridaId, numero, empezadaEn, terminadaEn });

describe('numeración seguida de las iteraciones entre corridas (M-20)', () => {
  it('con una sola corrida el ordinal es el número, aunque falten iteraciones intermedias', () => {
    const o = ordinalesDeIteraciones([iter('a', 'c1', 13, 100), iter('b', 'c1', 14, 200)], [{ id: 'c1', empezadaEn: 50 }]);
    expect(o.deIteracion.get('a')).toBe(13);
    expect(o.deIteracion.get('b')).toBe(14);
    expect(o.deCorrida.get('c1')).toBe(0);
    expect(o.total).toBe(14);
  });

  it('cada corrida empieza donde acabó la anterior: trece corridas de 1 a 4 no son "4 de 4"', () => {
    const iteraciones = [iter('a1', 'c1', 1, 100), iter('a2', 'c1', 2, 200), iter('a3', 'c1', 3, 300), iter('b1', 'c2', 1, 1000), iter('b2', 'c2', 2, 1100), iter('d1', 'c3', 1, 2000)];
    const o = ordinalesDeIteraciones(iteraciones, [{ id: 'c1', empezadaEn: 90 }, { id: 'c2', empezadaEn: 990 }, { id: 'c3', empezadaEn: 1990 }]);
    expect([...o.deIteracion.entries()]).toEqual([['a1', 1], ['a2', 2], ['a3', 3], ['b1', 4], ['b2', 5], ['d1', 6]]);
    expect(o.deCorrida.get('c2')).toBe(3);
    expect(o.deCorrida.get('c3')).toBe(5);
    expect(o.total).toBe(6);
  });

  it('ordena las corridas por su fecha aunque lleguen desordenadas y sin ficha de corrida', () => {
    const o = ordinalesDeIteraciones([iter('b1', 'c2', 1, 1000), iter('a1', 'c1', 1, 100), iter('a2', 'c1', 2, 200)], []);
    expect(o.deIteracion.get('a1')).toBe(1);
    expect(o.deIteracion.get('a2')).toBe(2);
    expect(o.deIteracion.get('b1')).toBe(3);
  });

  it('sin iteraciones no rompe: total 0 y mapas vacíos', () => {
    const o = ordinalesDeIteraciones([], []);
    expect(o.total).toBe(0);
    expect(o.deIteracion.size).toBe(0);
  });

  it('iteracionObjEn devuelve la iteración que contiene el instante o la anterior', () => {
    const iteraciones = [iter('a1', 'c1', 1, 100, 200), iter('a2', 'c1', 2, 300, 400)];
    expect(iteracionObjEn(iteraciones, 150)?.id).toBe('a1');
    expect(iteracionObjEn(iteraciones, 250)?.id).toBe('a1');
    expect(iteracionObjEn(iteraciones, 350)?.id).toBe('a2');
    expect(iteracionObjEn(iteraciones, 50)).toBeUndefined();
    expect(iteracionObjEn(iteraciones, null)).toBeUndefined();
  });
});
