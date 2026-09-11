import { describe, expect, it } from 'vitest';
import { CORRIDA, FUENTES, HIPOTESIS } from '../datos/muestra';
import { agujerosDeConejo, calibracion, dependeDeRetractada, estadoPresupuesto, recomendacionDelRevisor, resumenEvidencia, tramosFuertes } from './calidad';

describe('calibracion', () => {
  it('el revisor recomienda bloquear con hallazgos abiertos o afirmaciones bloqueantes', () => {
    expect(recomendacionDelRevisor(HIPOTESIS[1]!)).toBe('bloquear');
    expect(recomendacionDelRevisor(HIPOTESIS[0]!)).toBe('pasar');
  });
  it('solo cuenta las decididas y calcula el acuerdo', () => {
    const c = calibracion(HIPOTESIS);
    // hip-4 aceptada con recomendacion pasar; hip-5 descartada con recomendacion bloquear.
    expect(c.pasarYAceptada).toBe(1);
    expect(c.bloquearYDescartada).toBe(1);
    expect(c.acuerdo).toBe(1);
    expect(c.desacuerdos).toEqual([]);
  });
  it('registra los desacuerdos', () => {
    const forzada = { ...HIPOTESIS[1]!, estado: 'aceptada' as const };
    const c = calibracion([forzada]);
    expect(c.bloquearYAceptada).toBe(1);
    expect(c.desacuerdos[0]?.id).toBe('hip-2');
    expect(c.acuerdo).toBe(0);
  });
  it('sin decididas el acuerdo es null', () => {
    expect(calibracion([HIPOTESIS[0]!]).acuerdo).toBeNull();
  });
});

describe('estadoPresupuesto', () => {
  it('calcula fraccion, alertas nuevas y proyeccion', () => {
    const p = estadoPresupuesto(CORRIDA);
    expect(p.fraccion).toBeCloseTo(0.773, 3);
    expect(p.nuevasAlertas).toEqual([]);
    expect(p.agotado).toBe(false);
    expect(p.msHastaTope).toBeGreaterThan(0);
  });
  it('avisa al cruzar el 80 % una sola vez y marca agotado en el tope', () => {
    const c = { ...CORRIDA, gasto: { ...CORRIDA.gasto, llamadas: 2_500 } };
    expect(estadoPresupuesto(c).nuevasAlertas).toEqual([0.8]);
    const yaAvisada = { ...c, presupuesto: { ...c.presupuesto, avisadas: [0.5, 0.8] } };
    expect(estadoPresupuesto(yaAvisada).nuevasAlertas).toEqual([]);
    const tope = { ...CORRIDA, gasto: { ...CORRIDA.gasto, llamadas: 3_000 } };
    expect(estadoPresupuesto(tope).agotado).toBe(true);
    expect(estadoPresupuesto(tope).msHastaTope).toBeNull();
  });
});

describe('sobreafirmacion', () => {
  it('encuentra los verbos fuertes con su posicion', () => {
    const t = 'Esto demuestra que X; inhibir NLRP3 frenaria la progresion.';
    const tramos = tramosFuertes(t);
    expect(tramos.map((x) => x.texto)).toEqual(['demuestra', 'frenaria']);
    expect(t.slice(tramos[0]!.inicio, tramos[0]!.fin)).toBe('demuestra');
  });
  it('no marca frases prudentes', () => {
    expect(tramosFuertes('Podria asociarse con la progresion, si se comprueba en cohortes.')).toEqual([]);
  });
});

describe('evidencia', () => {
  it('resume por tipo de estudio', () => {
    expect(resumenEvidencia([FUENTES.glp1!, FUENTES.allegri2025!, FUENTES.nlrp3!, FUENTES.nlrp3!])).toBe('sostenida por 1 ensayo aleatorizado, 1 observacional, 2 preclinicos');
    expect(resumenEvidencia([])).toBe('sin fuentes');
  });
  it('detecta agujeros de conejo y dependencia de retractadas', () => {
    const conejo = { ...HIPOTESIS[1]!, relevancia: { justificacion: '', votoHumano: 'baja' as const } };
    expect(agujerosDeConejo([conejo, HIPOTESIS[0]!]).map((h) => h.id)).toEqual(['hip-2']);
    expect(dependeDeRetractada(HIPOTESIS[4]!).map((f) => f.id)).toEqual(['f-retractado']);
    expect(dependeDeRetractada(HIPOTESIS[0]!)).toEqual([]);
  });
});
