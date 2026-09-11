import { describe, expect, it } from 'vitest';
import { aprobarPlan, fijarAutoaprobacionPlan, pausarCorrida, replicarHipotesis, revisarHipotesis } from './acciones';
import { AHORA_MUESTRA, estadoDeMuestra } from './muestra';
import { avanzar, TICK_MS } from './simulacion';
import type { EstadoRosa } from './tipos';

/** Avanza n ticks aprobando cada plan nuevo al instante, para recorrer varias iteraciones. */
function correr(n: number, aprobar = true, inicial: EstadoRosa = estadoDeMuestra()) {
  let e = inicial;
  let t = AHORA_MUESTRA;
  for (let i = 0; i < n; i++) {
    t += TICK_MS;
    e = avanzar(e, t);
    if (aprobar) {
      const it = iteracionActual(e);
      if (!it.planAprobado) e = aprobarPlan(e, it.id, t);
    }
  }
  return e;
}

function iteracionActual(e: EstadoRosa) {
  return e.iteraciones.filter((i) => i.corridaId === 'cor-3').reduce((m, i) => (i.numero > m.numero ? i : m));
}

describe('avanzar', () => {
  it('con la corrida pausada devuelve el mismo objeto', () => {
    const e = pausarCorrida(estadoDeMuestra(), 'cor-3');
    expect(avanzar(e, AHORA_MUESTRA + 1)).toBe(e);
  });
  it('cada tick gasta y no muta el estado anterior', () => {
    const e0 = estadoDeMuestra();
    const antes = JSON.stringify(e0);
    const e1 = avanzar(e0, AHORA_MUESTRA + TICK_MS);
    expect(JSON.stringify(e0)).toBe(antes);
    expect(e1.corridas[0]!.gasto.llamadas).toBe(e0.corridas[0]!.gasto.llamadas + 1);
  });
  it('los pasos se marcan en orden y nunca hay dos en curso', () => {
    let e = estadoDeMuestra();
    let t = AHORA_MUESTRA;
    for (let i = 0; i < 60; i++) {
      t += TICK_MS;
      e = avanzar(e, t);
      const it = iteracionActual(e);
      if (!it.planAprobado) e = aprobarPlan(e, it.id, t);
      expect(it.plan.filter((p) => p.estado === 'en_curso').length).toBeLessThanOrEqual(1);
    }
  });
  it('al cerrar la iteracion 14 la 15 espera la aprobacion del plan y la corrida no avanza sin ella', () => {
    const e = correr(40, false);
    const cerrada = e.iteraciones.find((i) => i.id === 'it-14')!;
    expect(cerrada.terminadaEn).not.toBeNull();
    const actual = iteracionActual(e);
    expect(actual.numero).toBe(15);
    expect(actual.planAprobado).toBe(false);
    expect(e.corridas[0]!.estado).toBe('esperando_plan');
    // Sin aprobar, mas ticks no mueven el plan.
    const despues = avanzar(e, AHORA_MUESTRA + 100 * TICK_MS);
    expect(iteracionActual(despues).plan.every((p) => p.estado === 'pendiente')).toBe(true);
  });
  it('aprobar el plan arranca la 15 con sus pistas', () => {
    const e = correr(48, true);
    const actual = iteracionActual(e);
    expect(actual.numero).toBeGreaterThanOrEqual(15);
    expect(actual.planAprobado).toBe(true);
    expect(e.corridas[0]!.estado).toBe('en_marcha');
  });
  it('la autoaprobacion arranca el plan tras el tiempo fijado sin que nadie apruebe', () => {
    let e = fijarAutoaprobacionPlan(estadoDeMuestra(), 'cor-3', 5);
    e = correr(60, false, e);
    // Sin aprobacion humana la corrida siguio: el plan de la 15 se autoaprobo y hay pistas.
    expect(e.eventos.some((x) => x.texto.includes('autoaprobado tras 5 s'))).toBe(true);
    const it15 = e.iteraciones.find((i) => i.numero === 15)!;
    expect(it15.planAprobado).toBe(true);
    expect(it15.pistas.length).toBeGreaterThan(0);
  });
  it('al cerrar la primera iteracion anade una hipotesis y un hecho, una sola vez, con eventos', () => {
    const e = correr(120);
    const nuevas = e.hipotesis.filter((h) => h.titulo.startsWith('GFAP en plasma se altera'));
    expect(nuevas).toHaveLength(1);
    expect(nuevas[0]!.derivadaDe).toBe('hip-4');
    expect(e.hechos.filter((h) => h.enunciado.startsWith('GFAP en plasma es un marcador'))).toHaveLength(1);
    expect(e.eventos.filter((x) => x.tipo === 'iteracion_terminada').length).toBeGreaterThan(e.eventos.length - e.eventos.length + 1);
  });
  it('la pista de ensayos falla en iteraciones impares y su paso no queda fallido porque las otras terminan', () => {
    const e = correr(60);
    const it15 = e.iteraciones.find((i) => i.numero === 15)!;
    const aria = it15.pistas.find((p) => p.titulo.startsWith('ARIA'));
    expect(aria?.estado).toBe('fallida');
    const buscar = it15.plan.find((p) => p.titulo === 'Buscar literatura');
    expect(buscar?.estado === 'hecho' || buscar?.estado === 'en_curso').toBe(true);
  });
  it('el presupuesto global pausa la corrida al tope y avisa al 80 %', () => {
    let e = estadoDeMuestra();
    e = { ...e, corridas: e.corridas.map((c) => (c.id === 'cor-3' ? { ...c, presupuesto: { ...c.presupuesto, limiteLlamadas: 2_322 } } : c)) };
    e = correr(2, true, e);
    expect(e.eventos.some((x) => x.texto.includes('80 %'))).toBe(true);
    e = correr(3, true, e);
    expect(e.corridas[0]!.estado).toBe('esperando_aprobacion');
    // Sin preguntas pendientes seria pausada por presupuesto.
    let sinPendientes = estadoDeMuestra();
    sinPendientes = { ...sinPendientes, solicitudes: [], incidencias: [], corridas: sinPendientes.corridas.map((c) => (c.id === 'cor-3' ? { ...c, presupuesto: { ...c.presupuesto, limiteLlamadas: 2_320 } } : c)) };
    const p = correr(3, true, sinPendientes);
    expect(p.corridas[0]!.estado).toBe('pausada_por_presupuesto');
    expect(avanzar(p, AHORA_MUESTRA + 10 * TICK_MS)).toBe(p);
  });
  it('las replicaciones avanzan una trayectoria por tick con resultado determinista', () => {
    let e = replicarHipotesis(estadoDeMuestra(), 'hip-2', 5, AHORA_MUESTRA);
    e = correr(5, true, e);
    const h = e.hipotesis.find((x) => x.id === 'hip-2')!;
    expect(h.replicacion).toMatchObject({ estado: 'terminada', hechas: 5, sostienen: 4, contradicen: 1 });
  });
  it('una hipotesis marcada "no puedo juzgar" vuelve aclarada a la cola', () => {
    let e = revisarHipotesis(estadoDeMuestra(), 'hip-1', 'no_puedo_juzgar', 'Ambigua', 'la persona responsable', AHORA_MUESTRA);
    e = correr(2, true, e);
    const h = e.hipotesis.find((x) => x.id === 'hip-1')!;
    expect(h.estado).toBe('en_revision');
    expect(h.revisiones.at(-1)?.accion).toBe('aclarada');
  });
  it('el presupuesto de la iteracion no pasa del limite', () => {
    const e = correr(200);
    for (const it of e.iteraciones) expect(it.presupuesto.usado).toBeLessThanOrEqual(it.presupuesto.limite);
  });
});
