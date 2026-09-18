/** El estado `esperando_modelo` en los reducers de la interfaz (vigilante de
 *  modelos, 18 de septiembre de 2026). Espejo de los tests de
 *  rosa/tests/test_vigilante_corrida.py sobre `reanudar_corrida` y
 *  `pausar_corrida`: la misma regla en los dos lados. */
import { describe, expect, it } from 'vitest';
import { ampliarPresupuesto, detenerCorrida, pausarCorrida, reanudarCorrida } from './acciones';
import { estadoDeMuestra } from './muestra';
import type { Corrida, EsperaModelo, EstadoRosa, Incidencia, SaludModelo } from './tipos';

const ESPERA: EsperaModelo = { rol: 'cerebro', modelo: 'openai/gpt-6-astra', desde: 1, ultimoSondeo: null, proximoSondeo: 2, pasoId: null, intentos: 4 };

function conCorrida(estado: EstadoRosa, id: string, cambios: Partial<Corrida>): EstadoRosa {
  return { ...estado, corridas: estado.corridas.map((c) => (c.id === id ? { ...c, ...cambios } : c)) };
}

function corrida(estado: EstadoRosa, id: string): Corrida {
  return estado.corridas.find((c) => c.id === id)!;
}

describe('esperando_modelo en los reducers', () => {
  it('reanudar es el "Reintentar ahora": saca de esperando_modelo y borra la espera', () => {
    const e0 = conCorrida(estadoDeMuestra(), 'cor-3', { estado: 'esperando_modelo', esperandoModelo: ESPERA });
    const e1 = reanudarCorrida(e0, 'cor-3');
    expect(corrida(e1, 'cor-3').estado).toBe('en_marcha');
    expect(corrida(e1, 'cor-3').esperandoModelo).toBeNull();
    // Las demás corridas no se tocan.
    expect(corrida(e1, 'cor-2').estado).toBe('terminada');
  });

  it('pausar no toca una corrida que espera a un modelo', () => {
    const e0 = conCorrida(estadoDeMuestra(), 'cor-3', { estado: 'esperando_modelo', esperandoModelo: ESPERA });
    const e1 = pausarCorrida(e0, 'cor-3');
    expect(corrida(e1, 'cor-3').estado).toBe('esperando_modelo');
    expect(corrida(e1, 'cor-3').esperandoModelo).toEqual(ESPERA);
  });

  it('reanudar desde la pausa a mano sigue igual y deja la espera en null', () => {
    const e1 = pausarCorrida(estadoDeMuestra(), 'cor-3');
    expect(corrida(e1, 'cor-3').estado).toBe('pausada');
    const e2 = reanudarCorrida(e1, 'cor-3');
    expect(corrida(e2, 'cor-3').estado).toBe('en_marcha');
    expect(corrida(e2, 'cor-3').esperandoModelo).toBeNull();
  });

  it('reanudar una corrida en marcha o terminada no cambia nada', () => {
    const e0 = estadoDeMuestra();
    expect(reanudarCorrida(e0, 'cor-3').corridas).toEqual(e0.corridas);
    expect(corrida(reanudarCorrida(e0, 'cor-2'), 'cor-2').estado).toBe('terminada');
  });

  it('una corrida antigua sin esperandoModelo ni saludModelos en la raíz se maneja igual', () => {
    const base = estadoDeMuestra();
    // Los registros anteriores al vigilante no traen las claves: el tipo las deja opcionales.
    const sinClaves: EstadoRosa = { ...base, saludModelos: undefined, corridas: base.corridas.map((c) => ({ ...c, esperandoModelo: undefined })) };
    const e0 = conCorrida(sinClaves, 'cor-3', { estado: 'esperando_modelo' });
    const e1 = reanudarCorrida(e0, 'cor-3');
    expect(corrida(e1, 'cor-3').estado).toBe('en_marcha');
    expect(corrida(e1, 'cor-3').esperandoModelo).toBeNull();
    expect(e1.saludModelos ?? {}).toEqual({});
  });

  it('detener una corrida que espera a un modelo borra el registro de espera (espejo de detener_corrida)', () => {
    // Sin esto la franja de modelos seguía diciendo "esperando a GPT-6 Astra" sobre una corrida parada.
    const e0 = conCorrida(estadoDeMuestra(), 'cor-3', { estado: 'esperando_modelo', esperandoModelo: ESPERA });
    const e1 = detenerCorrida(e0, 'cor-3', 'Basta por hoy', 5000);
    expect(corrida(e1, 'cor-3').estado).toBe('detenida');
    expect(corrida(e1, 'cor-3').esperandoModelo).toBeNull();
    // Una corrida ya detenida o terminada no se toca.
    expect(detenerCorrida(e1, 'cor-3', 'otra vez', 6000)).toBe(e1);
  });

  it('detener resuelve la incidencia automática pendiente de esa corrida y deja las demás (espejo de detener_corrida)', () => {
    const base = conCorrida(estadoDeMuestra(), 'cor-3', { estado: 'esperando_modelo', esperandoModelo: ESPERA });
    const inc = (id: string, corridaId: string, tipo: Incidencia['tipo'], estado: Incidencia['estado']): Incidencia => ({ id, corridaId, tipo, titulo: 'GPT-6 Astra no responde', detalle: '', recurso: 'openai/gpt-6-astra', alternativa: null, estado, creadaEn: 1, resueltaEn: null, resolucion: null });
    const e0: EstadoRosa = { ...base, incidencias: [inc('a', 'cor-3', 'modelo_sin_respuesta', 'pendiente'), inc('b', 'cor-3', 'fuente_sin_respuesta', 'pendiente'), inc('c', 'cor-2', 'modelo_sin_respuesta', 'pendiente'), inc('d', 'cor-3', 'modelo_sin_respuesta', 'resuelta')] };
    const e1 = detenerCorrida(e0, 'cor-3', 'Basta', 5000);
    const porId = (id: string): Incidencia => e1.incidencias.find((i) => i.id === id)!;
    expect(porId('a').estado).toBe('resuelta');
    expect(porId('a').resueltaEn).toBe(5000);
    expect(porId('a').resolucion).toContain('ya no espera a ese modelo');
    expect(porId('b').estado).toBe('pendiente');
    expect(porId('c').estado).toBe('pendiente');
    expect(porId('d').resueltaEn).toBeNull();
  });

  it('ampliar el presupuesto desde la pausa borra un registro de espera rancio y desde otro estado no lo toca', () => {
    const pausada = conCorrida(estadoDeMuestra(), 'cor-3', { estado: 'pausada_por_presupuesto', esperandoModelo: ESPERA });
    const e1 = ampliarPresupuesto(pausada, 'cor-3', 1_000_000, 5000);
    expect(corrida(e1, 'cor-3').estado).toBe('en_marcha');
    expect(corrida(e1, 'cor-3').esperandoModelo).toBeNull();
    const esperando = conCorrida(estadoDeMuestra(), 'cor-3', { estado: 'esperando_modelo', esperandoModelo: ESPERA });
    const e2 = ampliarPresupuesto(esperando, 'cor-3', 1_000_000, 5000);
    expect(corrida(e2, 'cor-3').estado).toBe('esperando_modelo');
    expect(corrida(e2, 'cor-3').esperandoModelo).toEqual(ESPERA);
  });

  it('la forma de SaludModelo admite un registro por rol y un estado vacío', () => {
    const salud: SaludModelo = { modelo: 'openai/gpt-6-astra', estado: 'sin_respuesta', desde: 1, intentos: 4, proximoIntentoEn: 2, ultimaRespuestaEn: null, ultimaLatenciaMs: null, caidas: 1, recuperadoEn: null };
    const e0: EstadoRosa = { ...estadoDeMuestra(), saludModelos: { cerebro: salud } };
    expect(e0.saludModelos?.cerebro?.estado).toBe('sin_respuesta');
    expect(e0.saludModelos?.juez).toBeUndefined();
    const vacio: EstadoRosa = { ...estadoDeMuestra(), saludModelos: {} };
    expect(Object.keys(vacio.saludModelos ?? {})).toHaveLength(0);
  });
});
