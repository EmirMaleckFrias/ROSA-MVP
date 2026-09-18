import { describe, expect, it } from 'vitest';
import { terminosEn } from './glosario';
import { primeraFrase } from './modo';

describe('modo sencillo', () => {
  it('la primera frase de una nota larga', () => {
    expect(primeraFrase('ROSA2018 propone; una persona aprueba. Debajo, las areas que comparo.')).toBe('ROSA2018 propone; una persona aprueba.');
    expect(primeraFrase('Sin punto final')).toBe('Sin punto final');
    expect(primeraFrase('Se aprueba con el primer plan. Despues se corrige.')).toBe('Se aprueba con el primer plan.');
  });
  it('el glosario encuentra los terminos de un texto sin repetir', () => {
    const t = terminosEn('Puntuacion Elo por torneo, con Bradley-Terry y kappa. Elo otra vez.');
    expect(t.map((x) => x.termino)).toEqual(['Elo', 'Bradley-Terry', 'Kappa', 'Torneo']);
    expect(terminosEn('nada tecnico aqui')).toEqual([]);
  });
});
