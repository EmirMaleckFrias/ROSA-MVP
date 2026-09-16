import { describe, expect, it } from 'vitest';
import { estadoDeMuestra } from './muestra';
import { actualizarConfiguracion, fijarAmplitud } from './acciones';

describe('amplitud de búsqueda', () => {
  it('se fija con un botón y solo admite los tres valores', () => {
    const e = estadoDeMuestra();
    const inv = e.investigaciones[0]!;
    const e2 = fijarAmplitud(e, inv.id, 'amplia');
    expect(e2.investigaciones.find((i) => i.id === inv.id)?.configuracion.amplitud).toBe('amplia');
    // @ts-expect-error valor fuera del tipo: el reducer lo ignora
    expect(fijarAmplitud(e2, inv.id, 'todo')).toBe(e2);
  });
  it('guardar preferencias no borra la amplitud elegida', () => {
    const e = fijarAmplitud(estadoDeMuestra(), estadoDeMuestra().investigaciones[0]!.id, 'enfocada');
    const inv = e.investigaciones[0]!;
    const e2 = actualizarConfiguracion(e, inv.id, { preferencias: 'x', atributos: [], restricciones: [] });
    expect(e2.investigaciones.find((i) => i.id === inv.id)?.configuracion.amplitud).toBe('enfocada');
    const e3 = actualizarConfiguracion(estadoDeMuestra(), inv.id, { preferencias: 'x', atributos: [], restricciones: [] });
    expect(e3.investigaciones.find((i) => i.id === inv.id)?.configuracion.amplitud).toBe('equilibrada');
  });
});
