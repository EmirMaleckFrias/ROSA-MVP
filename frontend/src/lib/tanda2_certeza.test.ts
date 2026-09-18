// Tanda 2 del 17 de septiembre de 2026, constructor "certeza" (M-04): el
// ranking lee la lista de cohortes que el techo por regla dejó en la
// conclusión (`conclusion.techo.cohortesDistintas`, rosa/certeza.py `acotar`)
// antes de recalcular con la regla espejada. La fusión de dos entradas del
// mismo artículo (S-06) vive solo en el servidor y llega en esa lista; la
// regla espejada de priorizacion.ts no la hace (ver su comentario).
import { describe, expect, it } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import type { Hipotesis } from '../datos/tipos';
import { componentesDe } from './ranking';

describe('el ranking lee las cohortes que el techo dejó en la conclusión (M-04)', () => {
  it('conclusion.techo.cohortesDistintas es la tercera fuente del servidor, antes de recalcular', () => {
    const estado = estadoDeMuestra();
    const base = estado.hipotesis.find((x) => x.procedencia.fuentes.length > 0)!;
    const fuentes = base.procedencia.fuentes.map((f) => ({ ...f, cohorte: 'ADNI' }));
    const sinLista = { ...base, cohortesDistintas: undefined, procedencia: { ...base.procedencia, fuentes }, afirmaciones: [] } as unknown as Hipotesis;
    const conclusion = { ...(base.conclusion ?? ({} as NonNullable<Hipotesis['conclusion']>)), cohortesDistintas: undefined, techo: { nivel: 'baja', motivo: 'x', acotada: false, certezaDelJuez: 'baja', cohortesDistintas: ['TRAILBLAZER-ALZ 2', 'Study 201', 'Study 201'] } } as unknown as NonNullable<Hipotesis['conclusion']>;
    const c = componentesDe(estado, { ...sinLista, conclusion });
    expect(c.cohortesOrigen).toBe('servidor');
    expect(c.cohortesDistintas).toEqual(['TRAILBLAZER-ALZ 2', 'Study 201']);
    // La de la hipótesis y la de la conclusión siguen mandando por delante del techo.
    expect(componentesDe(estado, { ...sinLista, conclusion: { ...conclusion, cohortesDistintas: ['BioFINDER'] } }).cohortesDistintas).toEqual(['BioFINDER']);
    expect(componentesDe(estado, { ...sinLista, cohortesDistintas: ['A4'], conclusion }).cohortesDistintas).toEqual(['A4']);
    // Un techo sin lista, o con una lista que no es lista, cae a la regla espejada.
    const sinTecho = componentesDe(estado, { ...sinLista, conclusion: { ...conclusion, techo: { ...conclusion.techo!, cohortesDistintas: 'ADNI' } as never } });
    expect(sinTecho.cohortesOrigen).toBe('regla');
    expect(sinTecho.cohortesDistintas).toEqual(['ADNI']);
    expect(componentesDe(estado, { ...sinLista, conclusion: { ...conclusion, techo: null } }).cohortesOrigen).toBe('regla');
  });
});
