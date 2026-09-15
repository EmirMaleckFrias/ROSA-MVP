import { describe, expect, it } from 'vitest';
import { borradorDe, normalizarParada, partesAutomatizadas, resumenParada, textoAutomatizacion } from './parada';

describe('partesAutomatizadas', () => {
  it('separa lo medible de lo que decide una persona', () => {
    const p = partesAutomatizadas('3 iteraciones o cuando el modelo de mundo deje de cambiar');
    expect(p.iteraciones).toBe(3);
    expect(p.automatizada).toBe(true);
    expect(p.resto).toBe('cuando el modelo de mundo deje de cambiar');
    expect(textoAutomatizacion(p)).toContain('3 iteraciones');
    expect(textoAutomatizacion(p)).toContain('lo decides tu');
  });
  it('sin cifra no automatiza nada y lo dice', () => {
    const p = partesAutomatizadas('cuando el modelo de mundo deje de cambiar');
    expect(p.automatizada).toBe(false);
    expect(textoAutomatizacion(p)).toContain('no puede medir');
  });
  it('tiempo y llamadas', () => {
    const p = partesAutomatizadas('48 horas o 400 llamadas');
    expect(p.tiempo).toBe('48 h');
    expect(p.llamadas).toBe(400);
    expect(p.resto).toBe('');
  });
});

describe('parada propia de la corrida', () => {
  it('normaliza el formulario: números acotados, texto recortado, null si no hay nada', () => {
    expect(normalizarParada({ horas: '', iteraciones: '', llamadas: '', texto: '  ' })).toBeNull();
    expect(normalizarParada({ horas: '2,5', iteraciones: '6.9', llamadas: '3', texto: ' hasta que cambie ' })).toEqual({ horas: 2.5, iteraciones: 6, llamadas: 10, texto: 'hasta que cambie' });
    expect(normalizarParada({ horas: '-1', iteraciones: 'abc', llamadas: '', texto: '' })).toBeNull();
    expect(normalizarParada({ horas: '9999', iteraciones: '', llamadas: '', texto: '' })?.horas).toBe(336);
  });
  it('resume en una frase, lo que llegue primero', () => {
    expect(resumenParada(null)).toBe('');
    expect(resumenParada({ horas: 2, iteraciones: null, llamadas: null, texto: '' })).toBe('2 horas');
    expect(resumenParada({ horas: 0.5, iteraciones: 6, llamadas: null, texto: '' })).toBe('30 minutos o 6 iteraciones, lo que llegue primero');
    expect(resumenParada({ horas: 1, iteraciones: 3, llamadas: 500, texto: 'sin cambios' })).toBe('1 hora, 3 iteraciones, 500 llamadas al modelo o «sin cambios», lo que llegue primero');
  });
  it('vuelve al borrador para reutilizar la parada de la corrida anterior', () => {
    expect(borradorDe({ horas: 2, iteraciones: null, llamadas: 300, texto: 'x' })).toEqual({ horas: '2', iteraciones: '', llamadas: '300', texto: 'x' });
    expect(borradorDe(null)).toEqual({ horas: '', iteraciones: '', llamadas: '', texto: '' });
  });
});
