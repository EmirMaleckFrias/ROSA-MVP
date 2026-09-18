// @vitest-environment jsdom
// Adversario del frontend del vigilante de modelos (18 de septiembre de 2026).
// Cada test afirma lo que el contrato compartido o el propio informe del
// constructor dicen que pasa; los que fallan en HEAD son la reproducción del
// fallo y deben pasar cuando se arregle. Nada aquí toca el servidor ni la red.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import type { EsperaModelo, Evento, Incidencia, SaludModelo } from '../datos/tipos';
import { caidasDeModelo, duracionEnLlano, textoCaidas } from '../lib/digest';
import type { Ruta } from '../lib/ruta';
import { BarraLateral } from './BarraLateral';
import { HiloDelProceso } from './HiloDelProceso';
import { AvisoEsperandoModelo, VigilanteModelos, textoSalud } from './VigilanteModelos';

vi.mock('../lib/movimiento', () => ({ useMovimientoReducido: () => true }));

/** Hora local fija para que "12:34" salga igual en cualquier zona horaria. */
const a = (h: number, m: number) => new Date(2026, 8, 18, h, m, 0).getTime();
const AHORA = a(13, 0);
const MIN = 60_000;

const ev = (id: string, tipo: Evento['tipo'], t: number, texto: string): Evento => ({ id, investigacionId: 'inv-1', t, tipo, texto, ruta: '#/investigaciones/inv-1/corrida' });

/** Los textos exactos que escribe el backend (rosa/vigilante_modelos.py
 *  texto_evento_sin_respuesta y texto_evento_recuperado, y
 *  rosa/bucle/corrida.py _modelo_recuperado). */
const CAIDA = (modelo: string, hora: string) => `${modelo} no responde desde las ${hora}; ROSA2018 reintenta sola`;
const VUELTA = (modelo: string, intentos: string, duracion: string) => `${modelo} volvió tras ${intentos} y ${duracion}`;

describe('digest: el emparejamiento de caídas y recuperaciones por modelo', () => {
  // La expresión /^(.*?)\s+(?:no responde|volvió)\b/ de modeloDelEvento lleva
  // un \b detrás de "volvió". En JavaScript sin la bandera u, "ó" no es un
  // carácter de palabra, así que \b entre "ó" y el espacio nunca casa: toda
  // recuperación queda sin modelo y se empareja con cualquier caída. El
  // informe del constructor dice "empareja caída y recuperación por modelo";
  // con las frases reales del backend eso no ocurre nunca.
  it('una recuperación de GPT-6 Astra no cierra la caída abierta de Claude Opus 5', () => {
    const t0 = AHORA - 10 * MIN;
    const eventos = [
      ev('c-opus', 'modelo_sin_respuesta', t0, CAIDA('Claude Opus 5', '12:50')),
      // Astra cayó antes de la ventana y vuelve dentro de ella.
      ev('r-astra', 'modelo_recuperado', t0 + 3 * MIN, VUELTA('GPT-6 Astra', '2 intentos', '7 minutos')),
      // Astra vuelve a caer después de su recuperación y sigue caído.
      ev('c-astra', 'modelo_sin_respuesta', t0 + 5 * MIN, CAIDA('GPT-6 Astra', '12:55')),
    ];
    const c = caidasDeModelo(eventos, AHORA);
    // Por modelo y orden: Opus sigue abierto (10 min), Astra cayó otra vez y
    // sigue abierto (5 min), y la recuperación de Astra sin caída en la
    // ventana cuenta por su texto (7 min).
    expect(c).toEqual({ total: 3, recuperadas: 1, abiertas: 2, masLargaMs: 10 * MIN });
    expect(textoCaidas(c)).toBe('Hubo 3 caídas de modelo, la más larga de 10 minutos; 1 se recuperó sola y 2 siguen sin respuesta (ROSA2018 reintenta sola)');
  });

  it('la caída más larga se mide entre la caída y la recuperación del mismo modelo', () => {
    const t0 = AHORA - 60 * MIN;
    const eventos = [
      ev('c-opus', 'modelo_sin_respuesta', t0, CAIDA('Claude Opus 5', '12:00')),
      ev('c-astra', 'modelo_sin_respuesta', t0 + 1 * MIN, CAIDA('GPT-6 Astra', '12:01')),
      ev('r-astra', 'modelo_recuperado', t0 + 2 * MIN, VUELTA('GPT-6 Astra', '1 intento', '1 minuto')),
      ev('r-opus', 'modelo_recuperado', t0 + 60 * MIN, VUELTA('Claude Opus 5', '4 intentos', '59 minutos')),
    ];
    const c = caidasDeModelo(eventos, AHORA);
    // Opus: de t0 a t0 + 60 min. Cruzando los modelos sale 59 min.
    expect(c.masLargaMs).toBe(60 * MIN);
    expect(duracionEnLlano(c.masLargaMs)).toBe('1 hora');
    expect(textoCaidas(c)).toBe('Hubo 2 caídas de modelo, la más larga de 1 hora; se recuperaron solas');
  });
});

describe('la franja de modelos: cifras coherentes entre la fila y el aviso', () => {
  const salud = (extra: Partial<SaludModelo>): SaludModelo => ({ modelo: 'anthropic/claude-opus-5', estado: 'sin_respuesta', desde: a(12, 34), intentos: 4, proximoIntentoEn: AHORA + 50_000, ultimaRespuestaEn: null, ultimaLatenciaMs: null, caidas: 1, recuperadoEn: null, ...extra });

  // En esperando_modelo el supervisor (rosa/bucle/corrida.py _sondeo_fallido)
  // suma un intento por sondeo a `esperandoModelo.intentos` y a
  // `saludModelos[rol].intentos`. Tras media hora van 34. El aviso los dice;
  // la fila los capa en MAX_INTENTOS y dice "4 intentos sin respuesta".
  it('tras 34 sondeos fallidos la fila y el aviso dicen los mismos intentos', () => {
    const espera: EsperaModelo = { rol: 'juez', modelo: 'anthropic/claude-opus-5', desde: a(12, 34), ultimoSondeo: AHORA - 10_000, proximoSondeo: AHORA + 50_000, pasoId: null, intentos: 34 };
    const aviso = renderToStaticMarkup(<AvisoEsperandoModelo espera={espera} ahora={AHORA} />);
    expect(aviso).toContain('34 intentos con Claude Opus 5');
    const fila = textoSalud('juez', salud({ intentos: 34 }), AHORA);
    expect(fila).toContain('34 intentos sin respuesta');
    expect(fila).not.toMatch(/(^|[^\d])4 intentos sin respuesta/);
  });

  // El resumen de la cabecera cuenta como "no responde" cualquier rol que no
  // esté en ok, también el que solo está en `lento` ("tarda en responder").
  it('un modelo que solo tarda no se resume como "no responde"', () => {
    const lento = salud({ modelo: 'anthropic/claude-sonnet-5', estado: 'lento', desde: a(12, 58), intentos: 1, proximoIntentoEn: AHORA + 12_000 });
    const div = document.createElement('div');
    div.innerHTML = renderToStaticMarkup(<VigilanteModelos salud={{ volumen: lento }} estadoCorrida="en_marcha" ahora={AHORA} />);
    const resumen = div.querySelector('.vigilante-cabecera .meta')?.textContent ?? '';
    expect(div.textContent).toContain('tarda en responder');
    expect(resumen).not.toContain('no responde');
  });
});

describe('lo que rodea a la franja mientras ROSA2018 espera al modelo', () => {
  function conEstado(estado: 'esperando_modelo' | 'en_marcha') {
    const e = estadoDeMuestra();
    const inv = e.investigaciones[0]!;
    e.corridas = e.corridas.filter((c) => c.investigacionId === inv.id).slice(0, 1);
    e.corridas[0]!.estado = estado;
    return { e, inv };
  }

  // frontend/src/componentes/HiloDelProceso.tsx línea 108: la lista de
  // estados vivos no incluye esperando_modelo, así que el hilo de etapas
  // desaparece justo mientras la corrida espera (puede ser una hora). El
  // constructor lo declaró en pendientes; este test lo fija.
  it('el hilo de etapas sigue pintado en esperando_modelo, como en en_marcha', () => {
    const viva = conEstado('en_marcha');
    expect(renderToStaticMarkup(<HiloDelProceso estado={viva.e} inv={viva.inv} pantalla="corrida" />)).toContain('Etapas de la investigación');
    const esperando = conEstado('esperando_modelo');
    expect(renderToStaticMarkup(<HiloDelProceso estado={esperando.e} inv={esperando.inv} pantalla="corrida" />)).toContain('Etapas de la investigación');
  });

  // frontend/src/componentes/BarraLateral.tsx línea 70: la cuenta de "Corrida
  // en vivo" suma toda incidencia pendiente, también la modelo_sin_respuesta
  // que ROSA2018 resuelve sola; la cabecera (loQueEspera) ya la excluye, así
  // que la misma pantalla enseña dos cifras distintas.
  it('la incidencia que ROSA2018 resuelve sola no suma en la cuenta de "Corrida en vivo"', () => {
    const base = estadoDeMuestra();
    const inv = base.investigaciones[0]!;
    const corrida = base.corridas.filter((c) => c.investigacionId === inv.id).sort((x, y) => y.numero - x.numero)[0]!;
    const ruta: Ruta = { tipo: 'investigacion', investigacionId: inv.id, pantalla: 'corrida', detalleId: null };
    const cuenta = (estado: typeof base) => {
      const div = document.createElement('div');
      div.innerHTML = renderToStaticMarkup(<BarraLateral estado={estado} ruta={ruta} abierta={false} onCerrar={() => undefined} onBuscar={() => undefined} />);
      const item = [...div.querySelectorAll('a.nav-item')].find((x) => x.textContent?.includes('Corrida en vivo'));
      expect(item).toBeDefined();
      return Number(item?.querySelector('.nav-cuenta')?.textContent ?? '0');
    };
    const automatica: Incidencia = { id: 'inc-auto', corridaId: corrida.id, tipo: 'modelo_sin_respuesta', titulo: 'Claude Opus 5 no responde', detalle: '', recurso: 'anthropic/claude-opus-5', alternativa: 'ROSA2018 lo está resolviendo sola: reintenta con Claude Opus 5 cada pocos segundos', estado: 'pendiente', creadaEn: AHORA - 5 * MIN, resueltaEn: null, resolucion: null };
    const sinAutomatica = cuenta(base);
    const conAutomatica = cuenta({ ...base, incidencias: [...base.incidencias, automatica] });
    expect(conAutomatica).toBe(sinAutomatica);
  });
});
