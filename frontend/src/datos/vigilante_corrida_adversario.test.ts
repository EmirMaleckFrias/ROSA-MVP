/** Adversario del constructor "corrida" (vigilante de modelos, 18 de septiembre
 *  de 2026): lo que la interfaz hace con el estado `esperando_modelo` que el
 *  backend ya escribe. Los tests afirman el comportamiento correcto; el que
 *  falla señala un hueco. */
import { describe, expect, it } from 'vitest';
import { segundosDeTrabajo } from '../pantallas/Corrida';
import type { Corrida } from './tipos';

const GASTO = { llamadas: 0, tokensEntrada: 0, tokensSalida: 0, usd: 0, segundos: 10 } as unknown as Corrida['gasto'];

describe('el reloj de trabajo mientras la corrida espera a un modelo', () => {
  it('esperando_modelo no cuenta como trabajo: espejo de ESTADOS_DE_PAUSA_DEL_PROCESO en rosa/bucle/corrida.py', () => {
    // El servidor lleva 10 s de trabajo guardados; la corrida arrancó en 0 y lleva
    // 100 s de pared, todos ellos esperando a GPT-6 Astra. Ese tiempo va a pausaMs
    // en el servidor, pero el servidor lo vuelca cada 30 s: entre volcados la
    // pantalla no debe rellenar el hueco con reloj de pared.
    const c = { estado: 'esperando_modelo' as const, empezadaEn: 0, gasto: GASTO, esperaHumanaMs: 0, pausaMs: 0 };
    expect(segundosDeTrabajo(c, 100_000)).toBe(10);
  });

  it('las esperas humanas siguen congelando el reloj (control)', () => {
    const c = { estado: 'pausada' as const, empezadaEn: 0, gasto: GASTO, esperaHumanaMs: 0, pausaMs: 0 };
    expect(segundosDeTrabajo(c, 100_000)).toBe(10);
  });
});
