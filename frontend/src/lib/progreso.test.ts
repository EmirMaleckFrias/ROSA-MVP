import { describe, expect, it } from 'vitest';
import type { Corrida, ProgresoIteracion } from '../datos/tipos';
import { resumenMetrica, serieDeProgreso } from './progreso';

function punto(iteracion: number, extra: Partial<ProgresoIteracion> = {}): ProgresoIteracion {
  return {
    iteracion,
    fecha: iteracion * 1000,
    certezas: [{ hipotesisId: 'h1', certeza: 'muy_baja', direccion: 'apoya', peldano: 0, techo: 'muy_baja' }],
    peldanosTotales: 0,
    peldanosSubidos: 0,
    peldanosBajados: 0,
    hipotesisVivas: 1,
    hechosNuevos: 2,
    hipotesisNuevas: 0,
    fallidos: { pasos: 0, pistas: 0, killer: 0, afirmacionesBloqueadas: 0 },
    usdAcumulado: 1,
    llamadasAcumuladas: 10,
    arnes: 'aaa',
    ...extra,
  };
}

describe('serie de progreso', () => {
  it('encadena las corridas en orden, acumula hechos y marca el cambio de arnés y de corrida', () => {
    const c1 = { numero: 1, progreso: [punto(1), punto(2, { peldanosSubidos: 1, peldanosTotales: 1, certezas: [{ hipotesisId: 'h1', certeza: 'baja', direccion: 'apoya', peldano: 1, techo: 'baja' }], fallidos: { pasos: 1, pistas: 0, killer: 1, afirmacionesBloqueadas: 3 } })] } as unknown as Corrida;
    const c2 = { numero: 2, progreso: [punto(1, { arnes: 'bbb', hechosNuevos: 0 })] } as unknown as Corrida;
    const s = serieDeProgreso([c2, c1]);
    expect(s.map((p) => [p.corrida, p.iteracion, p.indice])).toEqual([[1, 1, 0], [1, 2, 1], [2, 1, 2]]);
    expect(s.map((p) => p.hechosAcumulados)).toEqual([2, 4, 4]);
    expect(s[1]!.fallidos).toBe(5);
    expect(s[1]!.maxPeldano).toBe(1);
    expect(s.map((p) => p.cambioDeArnes)).toEqual([false, false, true]);
    expect(s.map((p) => p.nuevaCorrida)).toEqual([true, false, true]);
    expect(serieDeProgreso([{ numero: 1 } as unknown as Corrida])).toEqual([]);
  });
  it('resume la métrica en una frase', () => {
    expect(resumenMetrica(null)).toBe('');
    expect(resumenMetrica({ iteraciones: 4, peldanosSubidos: 3, peldanosBajados: 1, peldanosNetos: 2, usd: 10, peldanosPorDolar: 0.2, hipotesisEnBajaOMas: 1, hechosNuevos: 9, hipotesisNuevas: 1, fallidos: { pasos: 0, pistas: 0, killer: 0, afirmacionesBloqueadas: 0 }, banco: null })).toBe('subió 2 peldaños netos de certeza en 4 iteraciones; 0.2 por dólar; 1 hipótesis en certeza baja o más');
  });
});
