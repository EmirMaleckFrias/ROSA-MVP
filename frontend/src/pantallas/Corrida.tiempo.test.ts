// B-01 y S-19 (17 de septiembre de 2026). El reloj de la corrida en pantalla
// contaba tiempo de pared desde empezadaEn (Math.max con el guardado), así que
// una espera de 40 minutos a que alguien aprobara el plan aparecía como 40
// minutos de corrida y no cuadraba con el tope en horas del servidor, que ya
// cuenta tiempo de trabajo. Y el coste solo existía como estimación por
// tokens (el doble de la factura): ahora se enseña lo facturado por el gateway
// cuando el servidor lo guardó, con el estimado al lado y dicho como tal.
import { describe, expect, it } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import type { Corrida } from '../datos/tipos';
import { ESTADOS_DE_ESPERA_HUMANA, esperandoPersona, segundosDeTrabajo, textoCoste } from './Corrida';

const base = (): Corrida => ({ ...estadoDeMuestra().corridas[0]!, empezadaEn: 1_000_000, terminadaEn: null, estado: 'en_marcha', gasto: { ...estadoDeMuestra().corridas[0]!.gasto, segundos: 100 }, esperaHumanaMs: 0, pausaMs: 0 });

describe('segundosDeTrabajo', () => {
  it('mientras trabaja: reloj de pared menos la espera humana y las pausas, misma regla que rosa/bucle/corrida.py tiempo_trabajo_ms', () => {
    const c = base();
    // 10 minutos de pared, 4 esperando el plan, 1 con el Mac dormido: 5 de trabajo.
    expect(segundosDeTrabajo({ ...c, esperaHumanaMs: 4 * 60_000, pausaMs: 60_000 }, c.empezadaEn + 10 * 60_000)).toBe(300);
    // Nunca menos que lo que el servidor guardó (llega cada 5 s).
    expect(segundosDeTrabajo({ ...c, gasto: { ...c.gasto, segundos: 400 }, esperaHumanaMs: 9 * 60_000 }, c.empezadaEn + 10 * 60_000)).toBe(400);
  });

  it('mientras espera a una persona el reloj no corre: se enseña el valor guardado', () => {
    const c = base();
    for (const estado of ['esperando_plan', 'esperando_aprobacion', 'pausada', 'pausada_por_presupuesto'] as const) {
      expect(esperandoPersona(estado)).toBe(true);
      expect(segundosDeTrabajo({ ...c, estado }, c.empezadaEn + 3_600_000)).toBe(100);
    }
    expect(esperandoPersona('en_marcha')).toBe(false);
    expect(ESTADOS_DE_ESPERA_HUMANA.has('en_marcha')).toBe(false);
  });

  it('terminada o detenida: el valor guardado, aunque el reloj de pared siga', () => {
    const c = base();
    expect(segundosDeTrabajo({ ...c, estado: 'terminada', terminadaEn: c.empezadaEn + 1 }, c.empezadaEn + 99_999_999)).toBe(100);
    expect(segundosDeTrabajo({ ...c, estado: 'detenida' }, c.empezadaEn + 99_999_999)).toBe(100);
  });

  it('un registro antiguo sin contadores cae al reloj de pared y nunca da negativo ni NaN', () => {
    const c = base();
    const antiguo = { estado: 'en_marcha' as const, empezadaEn: c.empezadaEn, gasto: { ...c.gasto, segundos: 0 } };
    expect(segundosDeTrabajo(antiguo, c.empezadaEn + 20_000)).toBe(20);
    expect(segundosDeTrabajo({ ...antiguo, esperaHumanaMs: Number.NaN, pausaMs: -5 } as never, c.empezadaEn + 20_000)).toBe(20);
    expect(segundosDeTrabajo({ ...antiguo, gasto: { segundos: 'x' } as never }, c.empezadaEn - 5000)).toBe(0);
    expect(segundosDeTrabajo({ ...antiguo, empezadaEn: undefined as never }, 0)).toBe(0);
  });

  it('adversario: sin fecha de arranque (0, null, texto) no enseña medio siglo de trabajo con el reloj real, sino lo guardado', () => {
    const c = base();
    const ahora = 1_789_700_000_000;
    for (const empezadaEn of [0, null, undefined, 'x', Number.NaN] as never[]) {
      expect(segundosDeTrabajo({ ...c, empezadaEn, gasto: { ...c.gasto, segundos: 42 } }, ahora)).toBe(42);
    }
    // Con fecha válida el reloj sí corre.
    expect(segundosDeTrabajo({ ...c, empezadaEn: ahora - 30_000, gasto: { ...c.gasto, segundos: 0 } }, ahora)).toBe(30);
  });
});

describe('textoCoste', () => {
  it('con factura del gateway: la cifra real manda y el estimado va al lado, con la etiqueta "facturado por el gateway"', () => {
    const t = textoCoste({ usd: 26.79, usdReal: 12.71 });
    expect(t.principal).toBe('12,71 USD');
    expect(t.etiqueta).toContain('facturado por el gateway');
    expect(t.etiqueta).toContain('estimado por tokens: 26,79 USD');
    expect(t.corto).toBe('12,71 USD facturados por el gateway (estimado por tokens: 26,79 USD)');
    expect(textoCoste({ usd: 26.79, usdReal: 12.71, usdEsEstimado: true }).title).toContain('se estimó por tokens');
  });
  it('sin factura: solo el estimado, dicho como estimado; sin nada, vacío', () => {
    const t = textoCoste({ usd: 26.79 });
    expect(t.principal).toBe('26,79 USD');
    expect(t.etiqueta).toContain('estimados por tokens');
    expect(t.etiqueta).not.toContain('facturado');
    expect(textoCoste({})).toEqual({ corto: '', principal: '', etiqueta: '', title: '' });
    expect(textoCoste({ usd: 0 }).corto).toBe('');
    expect(textoCoste({ usdReal: 0 }).principal).toBe('0,00 USD');
    expect(textoCoste({ usd: Number.NaN, usdReal: 'x' as never }).corto).toBe('');
  });
});
