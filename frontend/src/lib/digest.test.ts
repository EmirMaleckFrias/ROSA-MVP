import { describe, expect, it } from 'vitest';
import { AHORA_MUESTRA, estadoDeMuestra } from '../datos/muestra';
import { digest, digestComoTexto, loQueEspera } from './digest';

describe('digest', () => {
  it('solo cuenta lo posterior a la ultima visita', () => {
    const e = estadoDeMuestra();
    const d = digest(e, 'inv-1', AHORA_MUESTRA);
    // La visita fue hace 10 h: el evento de hace 14 h queda fuera.
    expect(d.eventos.some((x) => x.id === 'ev-1')).toBe(false);
    expect(d.eventos.some((x) => x.id === 'ev-2')).toBe(true);
    expect(d.iteraciones).toBe(2);
    expect(d.hipotesisNuevas).toBe(2);
    expect(d.incidencias).toBe(2);
  });
  it('sin ultima visita, todo cuenta', () => {
    const e = { ...estadoDeMuestra(), ultimaVisita: null };
    expect(digest(e, 'inv-1', AHORA_MUESTRA).eventos).toHaveLength(e.eventos.length);
  });
  it('lo que espera incluye permisos, incidencias e hipotesis pendientes, con la edad de la mas antigua', () => {
    const e = estadoDeMuestra();
    const w = loQueEspera(e, 'inv-1', AHORA_MUESTRA);
    // 3 solicitudes + 2 incidencias + 3 hipotesis pendientes (propuesta, en revision, refinar)
    expect(w.total).toBe(8);
    expect(w.masAntiguaMs).toBe(9 * 3_600_000);
  });
  it('las lineas se leen y el texto plano lleva cabecera', () => {
    const e = estadoDeMuestra();
    const d = digest(e, 'inv-1', AHORA_MUESTRA);
    expect(d.lineas.some((l) => l.includes('la mas antigua lleva 9 h'))).toBe(true);
    expect(d.lineas.some((l) => l.startsWith('Gasto: 2318 de 3000'))).toBe(true);
    const texto = digestComoTexto(d, 'Prueba');
    expect(texto.startsWith('Rosa · Prueba\n- ')).toBe(true);
  });
  it('sin eventos ni pendientes, dice sin novedades', () => {
    const e = { ...estadoDeMuestra(), eventos: [], solicitudes: [], incidencias: [], hipotesis: [], corridas: [] };
    const d = digest(e, 'inv-1', AHORA_MUESTRA);
    expect(digestComoTexto(d, 'X')).toBe('Rosa · X\n- Sin novedades');
  });
});
