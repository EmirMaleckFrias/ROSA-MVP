import { describe, expect, it } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import type { Ejecucion, Hipotesis, PlanAnalisis } from '../datos/tipos';
import { bloqueosDe, candidatos, cohortesDe } from './priorizacion';

function conKiller(h: Hipotesis, extra: Partial<Hipotesis> = {}): Hipotesis {
  return { ...h, decisionKiller: 'avanzar', experimento: { protocolo: '1. x', ensayo: 'e', costeEstimado: '', laboratorio: null, estado: 'propuesto', ficheroDatos: null, analisisPedido: '', confirma: 'sube', refuta: 'baja' }, ...extra };
}

describe('bloqueos no compensables', () => {
  const estado = estadoDeMuestra();
  const base = estado.hipotesis.find((h) => h.afirmaciones.some((a) => a.veredicto === 'sostenida'))!;

  it('sin experimento con criterios, bloquea aunque tenga evidencia', () => {
    const h = { ...base, experimento: null, decisionKiller: 'avanzar' as const };
    expect(bloqueosDe(estado, h)).toContain('sin_experimento_interpretable');
  });

  it('una afirmacion bloqueante es trazabilidad insuficiente', () => {
    const h = conKiller(base, { afirmaciones: [{ ...base.afirmaciones[0]!, veredicto: 'cita_no_resuelve' }] });
    expect(bloqueosDe(estado, h)).toContain('trazabilidad_insuficiente');
  });

  it('una fuente retractada bloquea', () => {
    const h = conKiller(base, { procedencia: { ...base.procedencia, fuentes: base.procedencia.fuentes.map((f, i) => (i === 0 ? { ...f, retraccion: 'retractado' as const } : f)) } });
    expect(bloqueosDe(estado, h)).toContain('fuente_retractada');
  });

  it('un analisis dado por no valido por el auditor bloquea', () => {
    const h = conKiller(base);
    const plan: PlanAnalisis = { id: 'plan-1', investigacionId: h.investigacionId, hipotesisId: h.id, datasetId: 'ds-x', tipo: 'confirmatorio', pregunta: '', variables: [], poblacion: '', preprocesado: [], prueba: '', hipotesisNula: '', hipotesisAlternativa: '', alpha: 0.05, direccionEsperada: '', tamanoEfectoMinimo: '', baseline: '', controlNegativo: '', correccionMultiplicidad: '', umbralEfecto: '', criterioNoEvaluable: '', semilla: 1, hashDatos: 'abc', hashPlan: 'p', congeladoEn: 0, autor: 'Rosa', reproduccionId: null };
    const run: Ejecucion = { id: 'run-1', investigacionId: h.investigacionId, hipotesisId: h.id, planId: 'plan-1', tipo: 'hipotesis', codigo: '', entorno: { python: '3.12', paquetes: [] }, semilla: 1, hashDatos: 'abc', hashPlan: 'p', inicio: 0, fin: 1, estado: 'completado', runtime: 'docker', red: 'deshabilitada', codigoSalida: 0, duracionS: 1, salida: '', error: '', resultados: {}, baseline: {}, controlNegativo: {}, repeticiones: [], interpretacion: null, plausibilidadVerificada: null, auditoria: { veredicto: 'no_valido', comprobaciones: [], motivo: 'fuga', quien: 'juez', fecha: 1 } };
    const e = { ...estado, planesAnalisis: [plan], ejecuciones: [run] };
    const b = bloqueosDe(e, h);
    expect(b).toContain('analisis_invalido');
    // El dataset ds-x no existe en la investigacion: datos no autorizados.
    expect(b).toContain('datos_no_autorizados');
  });
});

describe('candidatos con diversidad', () => {
  const estado = estadoDeMuestra();
  const inv = estado.investigaciones[0]!.id;
  const limpias = estado.hipotesis.filter((h) => h.investigacionId === inv && h.afirmaciones.some((a) => a.veredicto === 'sostenida') && !h.afirmaciones.some((a) => a.veredicto === 'cita_no_resuelve' || a.veredicto === 'no_sostenida' || a.veredicto === 'sin_cita' || a.veredicto === 'ausencia_refutada') && !h.procedencia.fuentes.some((f) => f.retraccion === 'retractado'));

  it('no repite cluster mientras haya otros y respeta el maximo', () => {
    const base = limpias[0]!;
    const hs = [0, 1, 2].map((i) => conKiller(base, { id: `${base.id}-${i}`, cluster: i < 2 ? 'Mismo' : 'Otro', elo: 1600 - i, estado: 'propuesta' }));
    const e = { ...estado, hipotesis: hs };
    const c = candidatos(e, inv, 2);
    expect(c.map((h) => h.cluster)).toEqual(['Mismo', 'Otro']);
  });

  it('ordena por Bradley-Terry cuando existe y por Elo si no', () => {
    const base = limpias[0]!;
    const hs = [
      conKiller(base, { id: 'bt-a', cluster: 'A', elo: 1700, estado: 'propuesta', bt: { fuerza: 1520, ic95: [1480, 1560] as [number, number], partidos: 4 } }),
      conKiller(base, { id: 'bt-b', cluster: 'B', elo: 1500, estado: 'propuesta', bt: { fuerza: 1610, ic95: [1550, 1670] as [number, number], partidos: 4 } }),
      conKiller(base, { id: 'bt-c', cluster: 'C', elo: 1580, estado: 'propuesta' }),
    ];
    // b tiene menos Elo pero mas fuerza BT; c no tiene BT y usa su Elo.
    expect(candidatos({ ...estado, hipotesis: hs }, inv, 3).map((h) => h.id)).toEqual(['bt-b', 'bt-c', 'bt-a']);
  });

  it('sin decision del Killer no hay candidatas: cero es un resultado valido', () => {
    const hs = [0, 1].map((i) => ({ ...conKiller(limpias[0]!, { id: `x-${i}` }), decisionKiller: null }));
    expect(candidatos({ ...estado, hipotesis: hs }, inv)).toEqual([]);
  });
});

describe('cohortes', () => {
  it('cuenta cohortes distintas, no articulos', () => {
    const estado = estadoDeMuestra();
    const h = estado.hipotesis[0]!;
    const fuentes = h.procedencia.fuentes.map((f, i) => ({ ...f, cohorte: i % 2 === 0 ? 'ADNI' : 'adni ' }));
    expect(cohortesDe({ procedencia: { ...h.procedencia, fuentes } })).toEqual(['adni']);
  });
});
