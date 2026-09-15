import { describe, expect, it } from 'vitest';
import { etiquetaCorrida, proponiendoPlan } from './etiquetas';

// La captura del 15 de septiembre: la corrida recién creada decía "Esperando que
// apruebes el plan" durante los 93 segundos en que Rosa aún escribía el plan y
// no había nada que aprobar.
describe('proponiendoPlan y etiquetaCorrida', () => {
  it('sin iteración, esperando_plan significa que Rosa escribe el plan', () => {
    expect(proponiendoPlan({ estado: 'esperando_plan' }, null)).toBe(true);
    expect(etiquetaCorrida({ estado: 'esperando_plan' }, null)).toBe('Rosa está proponiendo el plan');
  });
  it('con un plan propuesto y sin aprobar, sí hay algo que aprobar', () => {
    const it = { planAprobado: false, terminadaEn: null };
    expect(proponiendoPlan({ estado: 'esperando_plan' }, it)).toBe(false);
    expect(etiquetaCorrida({ estado: 'esperando_plan' }, it)).toBe('Esperando que apruebes el plan');
  });
  it('entre iteraciones (la última cerrada) vuelve a ser Rosa escribiendo', () => {
    expect(proponiendoPlan({ estado: 'esperando_plan' }, { planAprobado: true, terminadaEn: 1 })).toBe(true);
  });
  it('en otros estados no cambia la etiqueta', () => {
    expect(proponiendoPlan({ estado: 'en_marcha' }, null)).toBe(false);
    expect(etiquetaCorrida({ estado: 'terminada' }, null)).toBe('Terminada');
  });
});
