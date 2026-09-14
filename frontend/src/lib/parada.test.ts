import { describe, expect, it } from 'vitest';
import { partesAutomatizadas, textoAutomatizacion } from './parada';

describe('partesAutomatizadas', () => {
  it('separa lo medible de lo que decide una persona', () => {
    const p = partesAutomatizadas('3 iteraciones o cuando el modelo de mundo deje de cambiar');
    expect(p.iteraciones).toBe(3);
    expect(p.automatizada).toBe(true);
    expect(p.resto).toContain('modelo');
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
