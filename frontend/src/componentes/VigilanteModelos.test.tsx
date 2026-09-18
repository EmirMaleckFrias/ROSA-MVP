// @vitest-environment jsdom
// La franja "Modelos" montada de verdad (createRoot y act, como los tests
// vecinos): los tres estados con su punto y su frase en llano, la franja sin
// llamadas, el aviso de esperando_modelo con el botón que llama a reintentar,
// las incidencias que ROSA2018 resuelve sola, un registro anterior al
// vigilante y el resumen "Mientras no estabas" con la línea de caídas. Nada de
// lo que se pinta lleva guiones largos ni palabras sin tilde.
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AHORA_MUESTRA, estadoDeMuestra } from '../datos/muestra';
import type { EsperaModelo, Evento, Incidencia, SaludModelo } from '../datos/tipos';
import { caidasDeModelo, digest, duracionDelTexto, duracionEnLlano, loQueEspera, modeloDelEvento, textoCaidas } from '../lib/digest';
import { ESTADO_CORRIDA, TIPO_EVENTO, TIPO_INCIDENCIA } from '../lib/etiquetas';
import { Resumen } from './Resumen';
import { AvisoEsperandoModelo, MAX_INTENTOS, VigilanteModelos, filasDeSalud, horaCorta, nombreDeModelo, resumenDeSalud, textoReintento, textoSalud } from './VigilanteModelos';

const SIN_TILDE = /\b(ultima|todavia|reintento de|sondeo del|proximo|respondio|volvio|caida|caidas|minuto de|resolviendose|retomara|rapido|replica|mas larga|Ambar|Ultima|Todavia|Proximo|Caida|Caidas|hipotesis|iteracion|corrida numero)\b/;

let root: Root;
let nodo: HTMLDivElement;
beforeEach(() => {
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  nodo = document.createElement('div');
  document.body.append(nodo);
  root = createRoot(nodo);
});
afterEach(async () => {
  await act(async () => root.unmount());
  nodo.remove();
});

const titulos = () => [...nodo.querySelectorAll('[title]')].map((c) => c.getAttribute('title') ?? '');
const todoElTexto = () => [nodo.textContent ?? '', ...titulos()].join('\n');

/** Hora local fija: así "12:34" sale igual en cualquier zona horaria. */
const a = (h: number, m: number, s = 0) => new Date(2026, 8, 18, h, m, s).getTime();
const AHORA = a(13, 0);

function salud(extra: Partial<SaludModelo>): SaludModelo {
  return { modelo: 'openai/gpt-6-astra', estado: 'ok', desde: null, intentos: 0, proximoIntentoEn: null, ultimaRespuestaEn: null, ultimaLatenciaMs: null, caidas: 0, recuperadoEn: null, ...extra };
}

const OK = salud({ modelo: 'openai/gpt-6-astra', estado: 'ok', ultimaRespuestaEn: AHORA - 40_000, ultimaLatenciaMs: 6_000 });
const CAIDO = salud({ modelo: 'anthropic/claude-opus-5', estado: 'sin_respuesta', desde: a(12, 34), intentos: 2, proximoIntentoEn: AHORA + 45_000, caidas: 1 });
const LENTO = salud({ modelo: 'anthropic/claude-sonnet-5', estado: 'lento', desde: a(12, 58), intentos: 1, proximoIntentoEn: AHORA + 12_000, caidas: 1 });

describe('los textos en llano de la franja', () => {
  it('nombra los modelos por su tabla y deja tal cual los que no conoce', () => {
    expect(nombreDeModelo('openai/gpt-6-astra')).toBe('GPT-6 Astra');
    expect(nombreDeModelo('anthropic/claude-opus-5')).toBe('Claude Opus 5');
    expect(nombreDeModelo('anthropic/claude-sonnet-5')).toBe('Claude Sonnet 5');
    // LiteLLM antepone "openai/" al id del gateway.
    expect(nombreDeModelo('openai/anthropic/claude-opus-5')).toBe('Claude Opus 5');
    expect(nombreDeModelo('openai/openai/gpt-6-astra')).toBe('GPT-6 Astra');
    expect(nombreDeModelo('mistral/mistral-large-3')).toBe('mistral/mistral-large-3');
    expect(nombreDeModelo('')).toBe('el modelo');
    expect(nombreDeModelo(null)).toBe('el modelo');
    expect(nombreDeModelo(42)).toBe('el modelo');
  });

  it('responde, tarda y sin respuesta, con la hora, el reintento y la espera', () => {
    expect(textoSalud('cerebro', OK, AHORA)).toBe('GPT-6 Astra (cerebro): responde, última respuesta hace 40 s (6 s)');
    expect(textoSalud('juez', CAIDO, AHORA)).toBe('Claude Opus 5 (juez): sin respuesta desde las 12:34 · reintento 3 de 4 en 45 s');
    expect(textoSalud('volumen', LENTO, AHORA)).toBe('Claude Sonnet 5 (volumen): tarda en responder desde las 12:58 · reintento 2 de 4 en 12 s');
    expect(textoSalud('replica', salud({ modelo: 'anthropic/claude-opus-5' }), AHORA)).toBe('Claude Opus 5 (réplica): responde');
  });

  it('con los intentos agotados dice que sondea, y un próximo intento ya vencido es "ahora"', () => {
    expect(textoReintento(4, AHORA + 50_000, AHORA)).toBe('4 intentos sin respuesta · próximo sondeo en 50 s');
    // A partir del tope la cifra es la real: en esperando_modelo el supervisor
    // suma un intento por sondeo y el aviso de debajo dice los mismos.
    expect(textoReintento(9, null, AHORA)).toBe('9 intentos sin respuesta · próximo sondeo');
    expect(textoReintento(34, AHORA + 50_000, AHORA)).toBe('34 intentos sin respuesta · próximo sondeo en 50 s');
    expect(MAX_INTENTOS).toBe(4);
    expect(textoReintento(1, AHORA - 5_000, AHORA)).toBe('reintento 2 de 4 ahora');
    expect(textoReintento(undefined, undefined, AHORA)).toBe('reintento 1 de 4');
    expect(textoReintento(Number.NaN, 'x', AHORA)).toBe('reintento 1 de 4');
  });

  it('una respuesta de hace menos de un segundo es "hace un momento" y una marca corrupta no rompe la hora', () => {
    expect(textoSalud('cerebro', salud({ ultimaRespuestaEn: AHORA - 200 }), AHORA)).toBe('GPT-6 Astra (cerebro): responde, última respuesta hace un momento');
    expect(textoSalud('cerebro', salud({ ultimaRespuestaEn: AHORA + 60_000 }), AHORA)).toBe('GPT-6 Astra (cerebro): responde, última respuesta hace un momento');
    expect(horaCorta(null)).toBe('?');
    expect(horaCorta(Number.NaN)).toBe('?');
    expect(horaCorta(a(9, 5))).toBe('09:05');
    expect(textoSalud('juez', salud({ estado: 'sin_respuesta', desde: 'ayer' as never, intentos: 3 }), AHORA)).toBe('GPT-6 Astra (juez): sin respuesta · reintento 4 de 4');
  });

  it('ordena los roles conocidos y deja detrás los que no conoce; ignora lo que no es un registro', () => {
    const filas = filasDeSalud({ volumen: LENTO, extra: OK, cerebro: OK, basura: 'x', otro: null });
    expect(filas.map((f) => f.rol)).toEqual(['cerebro', 'volumen', 'extra']);
    expect(filasDeSalud(undefined)).toEqual([]);
    expect(filasDeSalud({})).toEqual([]);
    expect(filasDeSalud('no')).toEqual([]);
  });

  it('las etiquetas nuevas existen y están en castellano', () => {
    expect(ESTADO_CORRIDA.esperando_modelo).toBe('Esperando al modelo');
    expect(TIPO_EVENTO.modelo_sin_respuesta).toBe('Modelo sin respuesta');
    expect(TIPO_EVENTO.modelo_recuperado).toBe('Modelo recuperado');
    expect(TIPO_INCIDENCIA.modelo_sin_respuesta).toContain('reintenta sola');
    // Las demás no cambian.
    expect(ESTADO_CORRIDA.pausada).toBe('Pausada');
    expect(TIPO_EVENTO.killer).toBe('Hypothesis Killer');
  });
});

describe('la franja montada', () => {
  it('pinta un punto por rol con su color, su explicación al pasar el ratón y la frase en llano', async () => {
    await act(async () => root.render(<VigilanteModelos salud={{ cerebro: OK, juez: CAIDO, volumen: LENTO }} estadoCorrida="en_marcha" ahora={AHORA} />));
    const franja = nodo.querySelector('section[aria-label="Modelos"]')!;
    expect(franja).not.toBeNull();
    const puntos = [...franja.querySelectorAll('.vigilante-punto')];
    expect(puntos.map((p) => p.className)).toEqual(['vigilante-punto vigilante-punto-ok', 'vigilante-punto vigilante-punto-mal', 'vigilante-punto vigilante-punto-aviso']);
    expect(puntos[0]!.getAttribute('title')).toContain('Verde');
    expect(puntos[1]!.getAttribute('title')).toContain('nunca cambia de modelo');
    expect(puntos[2]!.getAttribute('title')).toContain('reintenta con el mismo modelo');
    expect(puntos.map((p) => p.getAttribute('aria-label'))).toEqual(['cerebro: responde', 'juez: sin respuesta', 'volumen: tarda en responder']);
    const texto = nodo.textContent ?? '';
    expect(texto).toContain('GPT-6 Astra (cerebro): responde, última respuesta hace 40 s (6 s)');
    expect(texto).toContain('Claude Opus 5 (juez): sin respuesta desde las 12:34 · reintento 3 de 4 en 45 s');
    expect(texto).toContain('Claude Sonnet 5 (volumen): tarda en responder desde las 12:58 · reintento 2 de 4 en 12 s');
    // El resumen separa el rojo (no responde) del ámbar (tarda): uno y uno.
    expect(nodo.querySelector('.vigilante-cabecera .meta')!.textContent).toBe('uno no responde y uno tarda; ROSA2018 reintenta sola');
    // Sin espera de la corrida, no hay aviso ni botón.
    expect(texto).not.toContain('Reintentar ahora');
    expect(todoElTexto()).not.toContain('\u2014');
    expect(todoElTexto()).not.toMatch(SIN_TILDE);
  });

  it('con la corrida viva y sin salud dice "Sin llamadas todavía"; sin salud y terminada no se pinta', async () => {
    await act(async () => root.render(<VigilanteModelos salud={undefined} estadoCorrida="en_marcha" ahora={AHORA} />));
    expect(nodo.textContent).toContain('Sin llamadas todavía');
    expect(nodo.textContent).toContain('todavía sin medir');
    await act(async () => root.render(<VigilanteModelos salud={{}} estadoCorrida="esperando_plan" ahora={AHORA} />));
    expect(nodo.textContent).toContain('Sin llamadas todavía');
    await act(async () => root.render(<VigilanteModelos salud={{}} estadoCorrida="terminada" ahora={AHORA} />));
    expect(nodo.innerHTML).toBe('');
    await act(async () => root.render(<VigilanteModelos salud={null} estadoCorrida="detenida" ahora={AHORA} />));
    expect(nodo.innerHTML).toBe('');
    // Terminada o detenida con salud registrada: no se pinta. La salud es de
    // ahora y común a todas las corridas, no de esa corrida cerrada; bajo su
    // cabecera diría "el juez no responde" como si fuera de ella.
    await act(async () => root.render(<VigilanteModelos salud={{ cerebro: OK, juez: CAIDO }} estadoCorrida="terminada" ahora={AHORA} />));
    expect(nodo.innerHTML).toBe('');
    await act(async () => root.render(<VigilanteModelos salud={{ juez: CAIDO }} estadoCorrida="detenida" ahora={AHORA} />));
    expect(nodo.innerHTML).toBe('');
  });

  it('un rol o un estado que esta versión no conoce se enseñan como aviso, sin romper', async () => {
    const raro = { ...OK, estado: 'degradado' as never, modelo: 'acme/modelo-x' };
    await act(async () => root.render(<VigilanteModelos salud={{ cerebro: OK, traductor: raro }} estadoCorrida="en_marcha" ahora={AHORA} />));
    expect(nodo.textContent).toContain('acme/modelo-x (traductor): degradado');
    expect(nodo.querySelectorAll('.vigilante-punto-aviso')).toHaveLength(1);
    expect(titulos().join('\n')).toContain('no conoce');
  });

  it('en esperando_modelo pinta el aviso con la última comprobación y el botón "Reintentar ahora" llama a reintentar', async () => {
    const espera: EsperaModelo = { rol: 'juez', modelo: 'anthropic/claude-opus-5', desde: a(12, 34), ultimoSondeo: a(12, 59), proximoSondeo: AHORA + 30_000, pasoId: 'paso-1', intentos: 4 };
    const llamadas: number[] = [];
    await act(async () => root.render(<VigilanteModelos salud={{ juez: CAIDO }} estadoCorrida="esperando_modelo" espera={espera} ahora={AHORA} onReintentar={() => llamadas.push(1)} />));
    expect(nodo.textContent).toContain('ROSA2018 espera a que Claude Opus 5 vuelva a responder. Sondea cada minuto y retomará sola; última comprobación 12:59.');
    expect(nodo.textContent).toContain('sin respuesta desde las 12:34 (26 min)');
    expect(nodo.textContent).toContain('4 intentos con Claude Opus 5');
    expect(nodo.textContent).toContain('el reloj de trabajo no corre');
    expect(nodo.querySelector('section')!.className).toContain('vigilante-esperando');
    const boton = [...nodo.querySelectorAll('button')].find((b) => b.textContent?.includes('Reintentar ahora'))!;
    expect(boton).toBeDefined();
    expect(boton.getAttribute('title')).toContain('No cambia de modelo');
    await act(async () => boton.click());
    await act(async () => boton.click());
    expect(llamadas).toEqual([1, 1]);
    expect(todoElTexto()).not.toContain('\u2014');
    expect(todoElTexto()).not.toMatch(SIN_TILDE);
  });

  it('el aviso tolera una espera sin sondeo, sin registro o con una corrida antigua', async () => {
    await act(async () => root.render(<AvisoEsperandoModelo espera={{ rol: 'cerebro', modelo: 'openai/gpt-6-astra', desde: a(12, 34), ultimoSondeo: null, proximoSondeo: a(13, 1), pasoId: null, intentos: 1 }} ahora={AHORA} />));
    expect(nodo.textContent).toContain('ROSA2018 espera a que GPT-6 Astra vuelva a responder. Sondea cada minuto y retomará sola; primera comprobación a las 13:01.');
    expect(nodo.textContent).toContain('1 intento con GPT-6 Astra');
    await act(async () => root.render(<AvisoEsperandoModelo espera={null} ahora={AHORA} />));
    expect(nodo.textContent).toContain('ROSA2018 espera a que el modelo vuelva a responder. Sondea cada minuto y retomará sola; todavía sin comprobación registrada.');
    await act(async () => root.render(<AvisoEsperandoModelo espera={undefined} ahora={AHORA} />));
    expect(nodo.textContent).toContain('el modelo vuelva a responder');
    // Corrida en esperando_modelo con el registro perdido: la franja igual se pinta y ofrece reintentar.
    await act(async () => root.render(<VigilanteModelos salud={undefined} estadoCorrida="esperando_modelo" espera={undefined} ahora={AHORA} />));
    expect(nodo.textContent).toContain('Sin llamadas todavía');
    expect(nodo.textContent).toContain('Reintentar ahora');
  });

  it('las incidencias modelo_sin_respuesta pendientes se listan como "resolviéndose solo" con su tiempo; las resueltas y las de otro tipo no', async () => {
    const base: Incidencia = { id: 'inc-a', corridaId: 'cor-3', tipo: 'modelo_sin_respuesta', titulo: 'Claude Opus 5 no responde', detalle: 'El juez (Claude Opus 5) no respondió en 300 s (intento 2 de 4).', recurso: 'anthropic/claude-opus-5', alternativa: 'ROSA2018 lo está resolviendo sola: reintenta con Claude Opus 5 cada pocos segundos', estado: 'pendiente', creadaEn: AHORA - 26 * 60_000, resueltaEn: null, resolucion: null };
    const incidencias: Incidencia[] = [
      base,
      { ...base, id: 'inc-b', titulo: 'GPT-6 Astra no responde', estado: 'resuelta', resueltaEn: AHORA, resolucion: 'Se resolvió sola' },
      { ...base, id: 'inc-c', tipo: 'conector_caducado', titulo: 'La clave de Semantic Scholar caducó' },
    ];
    await act(async () => root.render(<VigilanteModelos salud={{ juez: CAIDO }} incidencias={incidencias} estadoCorrida="en_marcha" ahora={AHORA} />));
    const lista = nodo.querySelector('ul[aria-label="Incidencias que ROSA2018 resuelve sola"]')!;
    expect(lista).not.toBeNull();
    expect(lista.querySelectorAll('li')).toHaveLength(1);
    expect(lista.textContent).toContain('resolviéndose solo');
    expect(lista.textContent).toContain('Claude Opus 5 no responde · desde hace 26 min');
    expect(lista.querySelector('li')!.getAttribute('title')).toContain('intento 2 de 4');
    expect(nodo.textContent).not.toContain('GPT-6 Astra no responde');
    expect(nodo.textContent).not.toContain('Semantic Scholar');
    // No hay botón de resolver: lo resuelve ROSA2018.
    expect([...nodo.querySelectorAll('button')].map((b) => b.textContent)).toEqual([]);
  });
});

describe('caídas de modelo en "Mientras no estabas"', () => {
  const ev = (id: string, tipo: Evento['tipo'], t: number, texto: string): Evento => ({ id, investigacionId: 'inv-1', t, tipo, texto, ruta: '#/investigaciones/inv-1/corrida' });

  it('empareja cada caída con su recuperación por modelo y orden, y mide la más larga', () => {
    const t0 = AHORA_MUESTRA - 3 * 3_600_000;
    const eventos = [
      ev('c1', 'modelo_sin_respuesta', t0, 'Claude Opus 5 no responde desde las 12:34; ROSA2018 reintenta sola'),
      ev('c2', 'modelo_sin_respuesta', t0 + 5 * 60_000, 'GPT-6 Astra no responde desde las 12:39; ROSA2018 reintenta sola'),
      ev('r2', 'modelo_recuperado', t0 + 12 * 60_000, 'GPT-6 Astra volvió tras 2 intentos y 7 minutos'),
      ev('r1', 'modelo_recuperado', t0 + 59 * 60_000, 'Claude Opus 5 volvió tras 4 intentos y 59 minutos'),
    ];
    const c = caidasDeModelo(eventos, AHORA_MUESTRA);
    expect(c).toEqual({ total: 2, recuperadas: 2, abiertas: 0, masLargaMs: 59 * 60_000 });
    expect(textoCaidas(c)).toBe('Hubo 2 caídas de modelo, la más larga de 59 minutos; se recuperaron solas');
    // Una sola caída recuperada.
    expect(textoCaidas(caidasDeModelo(eventos.slice(1, 3), AHORA_MUESTRA))).toBe('Hubo 1 caída de modelo, de 7 minutos; se recuperó sola');
  });

  it('una caída sin recuperación sigue abierta y se mide hasta ahora; una recuperación sin caída en la ventana lee la duración del texto', () => {
    const t0 = AHORA_MUESTRA - 40 * 60_000;
    const abierta = caidasDeModelo([ev('c1', 'modelo_sin_respuesta', t0, 'GPT-6 Astra no responde desde las 12:34; ROSA2018 reintenta sola')], AHORA_MUESTRA);
    expect(abierta).toEqual({ total: 1, recuperadas: 0, abiertas: 1, masLargaMs: 40 * 60_000 });
    expect(textoCaidas(abierta)).toBe('Hubo 1 caída de modelo, desde hace 40 minutos; sigue sin respuesta y ROSA2018 reintenta sola');
    const soloRecuperada = caidasDeModelo([ev('r1', 'modelo_recuperado', t0, 'Claude Opus 5 volvió tras 4 intentos y 1 hora y 5 minutos')], AHORA_MUESTRA);
    expect(soloRecuperada).toEqual({ total: 1, recuperadas: 1, abiertas: 0, masLargaMs: 65 * 60_000 });
    const mixta = caidasDeModelo(
      [ev('c1', 'modelo_sin_respuesta', t0, 'GPT-6 Astra no responde desde las 12:34; ROSA2018 reintenta sola'), ev('r0', 'modelo_recuperado', t0 - 60_000, 'Claude Opus 5 volvió tras 3 intentos y 12 minutos'), ev('c2', 'modelo_sin_respuesta', t0 + 60_000, 'Claude Opus 5 no responde desde las 12:35; ROSA2018 reintenta sola')],
      AHORA_MUESTRA,
    );
    expect(mixta.total).toBe(3);
    expect(mixta.abiertas).toBe(2);
    expect(textoCaidas(mixta)).toBe('Hubo 3 caídas de modelo, la más larga de 40 minutos; 1 se recuperó sola y 2 siguen sin respuesta (ROSA2018 reintenta sola)');
    // Textos que no nombran el modelo también se emparejan (por orden).
    const anonimos = caidasDeModelo([ev('c', 'modelo_sin_respuesta', t0, 'algo raro'), ev('r', 'modelo_recuperado', t0 + 90_000, 'otra cosa')], AHORA_MUESTRA);
    expect(anonimos).toEqual({ total: 1, recuperadas: 1, abiertas: 0, masLargaMs: 90_000 });
    expect(caidasDeModelo([], AHORA_MUESTRA).total).toBe(0);
  });

  it('las duraciones siguen la misma regla que duracion_texto del backend', () => {
    expect(duracionEnLlano(0)).toBe('menos de un minuto');
    expect(duracionEnLlano(59_000)).toBe('menos de un minuto');
    expect(duracionEnLlano(60_000)).toBe('1 minuto');
    expect(duracionEnLlano(12 * 60_000 + 30_000)).toBe('12 minutos');
    expect(duracionEnLlano(60 * 60_000)).toBe('1 hora');
    expect(duracionEnLlano(65 * 60_000)).toBe('1 hora y 5 minutos');
    expect(duracionEnLlano(121 * 60_000)).toBe('2 horas y 1 minuto');
    expect(duracionEnLlano(Number.NaN)).toBe('menos de un minuto');
    expect(duracionDelTexto('GPT-6 Astra volvió tras 4 intentos y menos de un minuto')).toBe(30_000);
    expect(duracionDelTexto('volvió tras 1 intento y 2 horas')).toBe(2 * 3_600_000);
    expect(duracionDelTexto('sin duración')).toBe(0);
  });

  it('el resumen enseña la línea de caídas y los chips de los eventos, y una incidencia automática no espera a nadie', async () => {
    const base = estadoDeMuestra();
    const t0 = AHORA_MUESTRA - 3 * 3_600_000;
    const estado = {
      ...base,
      ultimaVisita: AHORA_MUESTRA - 4 * 3_600_000,
      eventos: [
        ...base.eventos,
        ev('c1', 'modelo_sin_respuesta', t0, 'Claude Opus 5 no responde desde las 12:34; ROSA2018 reintenta sola'),
        ev('r1', 'modelo_recuperado', t0 + 59 * 60_000, 'Claude Opus 5 volvió tras 4 intentos y 59 minutos'),
        ev('c2', 'modelo_sin_respuesta', t0 + 3_600_000, 'GPT-6 Astra no responde desde las 13:34; ROSA2018 reintenta sola'),
        ev('r2', 'modelo_recuperado', t0 + 3_600_000 + 4 * 60_000, 'GPT-6 Astra volvió tras 2 intentos y 4 minutos'),
      ],
      incidencias: [...base.incidencias, { id: 'inc-auto', corridaId: 'cor-3', tipo: 'modelo_sin_respuesta' as const, titulo: 'GPT-6 Astra no responde', detalle: '', recurso: 'openai/gpt-6-astra', alternativa: null, estado: 'pendiente' as const, creadaEn: AHORA_MUESTRA - 60_000, resueltaEn: null, resolucion: null }],
    };
    const d = digest(estado, 'inv-1', AHORA_MUESTRA);
    expect(d.lineas).toContain('Hubo 2 caídas de modelo, la más larga de 59 minutos; se recuperaron solas');
    // La incidencia automática no cuenta como "sin resolver" ni como decisión que espera.
    expect(d.lineas.some((l) => l.includes('3 incidencias sin resolver'))).toBe(false);
    expect(d.lineas.some((l) => l.includes('2 incidencias sin resolver'))).toBe(true);
    expect(loQueEspera(estado, 'inv-1', AHORA_MUESTRA).total).toBe(loQueEspera(base, 'inv-1', AHORA_MUESTRA).total);
    await act(async () => root.render(<Resumen d={d} titulo="Prueba" ahora={AHORA_MUESTRA} onVisto={() => undefined} />));
    expect(nodo.textContent).toContain('Hubo 2 caídas de modelo');
    const boton = [...nodo.querySelectorAll('button')].find((b) => b.textContent?.startsWith('Ver los'));
    if (boton) await act(async () => boton.click());
    const chips = [...nodo.querySelectorAll('.resumen-eventos .chip')];
    const sinRespuesta = chips.find((c) => c.textContent === 'Modelo sin respuesta')!;
    const recuperado = chips.find((c) => c.textContent === 'Modelo recuperado')!;
    expect(sinRespuesta.className).toContain('chip-aviso');
    expect(recuperado.className).toContain('chip-ok');
    expect(todoElTexto()).not.toContain('\u2014');
    expect(todoElTexto()).not.toMatch(SIN_TILDE);
  });

  it('solo una caída recuperada ya es novedad: la tarjeta se pinta', () => {
    const base = estadoDeMuestra();
    const estado = { ...base, ultimaVisita: AHORA_MUESTRA - 60_000, eventos: [ev('c1', 'modelo_sin_respuesta', AHORA_MUESTRA - 50_000, 'GPT-6 Astra no responde desde las 14:29; ROSA2018 reintenta sola'), ev('r1', 'modelo_recuperado', AHORA_MUESTRA - 10_000, 'GPT-6 Astra volvió tras 1 intento y menos de un minuto')] };
    const d = digest(estado, 'inv-1', AHORA_MUESTRA);
    expect(d.hayNovedades).toBe(true);
    expect(d.lineas[0]).toBe('Hubo 1 caída de modelo, de menos de un minuto; se recuperó sola');
  });
});

describe('lo que el adversario rompió el 18 de septiembre de 2026', () => {
  const ev = (id: string, tipo: Evento['tipo'], t: number, texto: string): Evento => ({ id, investigacionId: 'inv-1', t, tipo, texto, ruta: '#/investigaciones/inv-1/corrida' });
  const MIN = 60_000;

  it('modeloDelEvento distingue los modelos con las frases exactas del backend (texto_evento_sin_respuesta y texto_evento_recuperado)', () => {
    // Antes la expresión cerraba con \b detrás de "volvió": en JavaScript \b
    // solo conoce letras ASCII, así que toda recuperación quedaba sin modelo.
    expect(modeloDelEvento(ev('r', 'modelo_recuperado', 0, 'Claude Opus 5 volvió tras 4 intentos y 59 minutos'))).toBe('claude opus 5');
    expect(modeloDelEvento(ev('r', 'modelo_recuperado', 0, 'GPT-6 Astra volvió tras 1 intento y menos de un minuto'))).toBe('gpt-6 astra');
    expect(modeloDelEvento(ev('c', 'modelo_sin_respuesta', 0, 'Claude Opus 5 no responde desde las 12:34; ROSA2018 reintenta sola'))).toBe('claude opus 5');
    expect(modeloDelEvento(ev('c', 'modelo_sin_respuesta', 0, 'GPT-6 Astra no responde desde las 12:34; ROSA2018 reintenta sola'))).toBe('gpt-6 astra');
    // Con el texto entero, sin más detrás.
    expect(modeloDelEvento(ev('r', 'modelo_recuperado', 0, 'Claude Sonnet 5 volvió'))).toBe('claude sonnet 5');
    // Un texto que no sigue la frase no inventa un modelo.
    expect(modeloDelEvento(ev('r', 'modelo_recuperado', 0, 'volvióse la calma'))).toBe('');
    expect(modeloDelEvento(ev('r', 'modelo_recuperado', 0, 'otra cosa'))).toBe('');
  });

  it('una recuperación de un modelo no cierra la caída abierta de otro, y la más larga se mide dentro del mismo modelo', () => {
    // Una caída del gateway tumba a Astra y a Opus a la vez (el caso real de la corrida 13).
    const t0 = AHORA - 60 * MIN;
    const c = caidasDeModelo(
      [
        ev('c-opus', 'modelo_sin_respuesta', t0, 'Claude Opus 5 no responde desde las 12:00; ROSA2018 reintenta sola'),
        ev('c-astra', 'modelo_sin_respuesta', t0 + 1 * MIN, 'GPT-6 Astra no responde desde las 12:01; ROSA2018 reintenta sola'),
        ev('r-astra', 'modelo_recuperado', t0 + 2 * MIN, 'GPT-6 Astra volvió tras 1 intento y 1 minuto'),
      ],
      AHORA,
    );
    // Cruzando los modelos, la vuelta de Astra habría cerrado la caída de Opus.
    expect(c).toEqual({ total: 2, recuperadas: 1, abiertas: 1, masLargaMs: 60 * MIN });
    expect(textoCaidas(c)).toBe('Hubo 2 caídas de modelo, la más larga de 1 hora; 1 se recuperó sola y 1 sigue sin respuesta (ROSA2018 reintenta sola)');
  });

  it('el resumen de la cabecera separa los que no responden de los que solo tardan', () => {
    const fila = (rol: string, s: SaludModelo) => ({ rol, s });
    const RARO = { ...OK, estado: 'degradado' as never };
    expect(resumenDeSalud([])).toBe('todavía sin medir');
    expect(resumenDeSalud([fila('cerebro', OK), fila('juez', OK)])).toBe('todos responden');
    expect(resumenDeSalud([fila('volumen', LENTO)])).toBe('uno tarda en responder');
    expect(resumenDeSalud([fila('volumen', LENTO), fila('traductor', RARO)])).toBe('2 tardan en responder');
    expect(resumenDeSalud([fila('juez', CAIDO)])).toBe('uno no responde; ROSA2018 reintenta sola');
    expect(resumenDeSalud([fila('juez', CAIDO), fila('cerebro', { ...CAIDO, modelo: 'openai/gpt-6-astra' })])).toBe('2 no responden; ROSA2018 reintenta sola');
    expect(resumenDeSalud([fila('juez', CAIDO), fila('volumen', LENTO)])).toBe('uno no responde y uno tarda; ROSA2018 reintenta sola');
    expect(resumenDeSalud([fila('juez', CAIDO), fila('cerebro', CAIDO), fila('volumen', LENTO), fila('traductor', RARO)])).toBe('2 no responden y 2 tardan; ROSA2018 reintenta sola');
  });

  it('con solo Sonnet en lento la franja no dice "no responde" en ningún sitio', async () => {
    await act(async () => root.render(<VigilanteModelos salud={{ volumen: LENTO }} estadoCorrida="en_marcha" ahora={AHORA} />));
    expect(nodo.querySelector('.vigilante-cabecera .meta')!.textContent).toBe('uno tarda en responder');
    expect(nodo.textContent).toContain('Claude Sonnet 5 (volumen): tarda en responder');
    expect(nodo.textContent).not.toContain('no responde');
  });

  it('tras 34 sondeos fallidos la fila y el aviso dicen los mismos intentos', async () => {
    const espera: EsperaModelo = { rol: 'juez', modelo: 'anthropic/claude-opus-5', desde: a(12, 34), ultimoSondeo: AHORA - 10_000, proximoSondeo: AHORA + 50_000, pasoId: null, intentos: 34 };
    await act(async () => root.render(<VigilanteModelos salud={{ juez: { ...CAIDO, intentos: 34, proximoIntentoEn: AHORA + 50_000 } }} estadoCorrida="esperando_modelo" espera={espera} ahora={AHORA} />));
    expect(nodo.textContent).toContain('Claude Opus 5 (juez): sin respuesta desde las 12:34 · 34 intentos sin respuesta · próximo sondeo en 50 s');
    expect(nodo.textContent).toContain('34 intentos con Claude Opus 5');
    // Ni la fila ni el aviso dicen el tope ("4 intentos") como cifra suelta;
    // `not.toContain('4 intentos')` no sirve porque "34 intentos" lo contiene.
    expect(nodo.textContent).not.toMatch(/(^|[^\d])4 intentos/);
  });

  it('bajo una corrida cerrada no se pinta la salud de ahora; una incidencia automática que quedó pendiente sí, como suya', async () => {
    // saludModelos es la salud actual y común: bajo la corrida 9, cerrada hace
    // días, diría "el juez no responde" como si fuera de ella.
    await act(async () => root.render(<VigilanteModelos salud={{ cerebro: OK, juez: CAIDO }} estadoCorrida="terminada" ahora={AHORA} />));
    expect(nodo.innerHTML).toBe('');
    const pendiente: Incidencia = { id: 'inc-z', corridaId: 'cor-9', tipo: 'modelo_sin_respuesta', titulo: 'Claude Opus 5 no responde', detalle: '', recurso: 'anthropic/claude-opus-5', alternativa: null, estado: 'pendiente', creadaEn: AHORA - 3 * 60_000, resueltaEn: null, resolucion: null };
    await act(async () => root.render(<VigilanteModelos salud={{ cerebro: OK, juez: CAIDO }} incidencias={[pendiente]} estadoCorrida="detenida" ahora={AHORA} />));
    expect(nodo.querySelectorAll('.vigilante-punto')).toHaveLength(0);
    expect(nodo.textContent).not.toContain('Claude Opus 5 (juez)');
    expect(nodo.textContent).not.toContain('todos responden');
    expect(nodo.textContent).toContain('la corrida está cerrada');
    expect(nodo.textContent).toContain('quedó abierta al cerrar la corrida');
    expect(nodo.textContent).not.toContain('resolviéndose solo');
    expect(nodo.textContent).toContain('Claude Opus 5 no responde · desde hace 3 min');
    // Con la misma incidencia ya resuelta, nada que pintar.
    await act(async () => root.render(<VigilanteModelos salud={{ juez: CAIDO }} incidencias={[{ ...pendiente, estado: 'resuelta', resueltaEn: AHORA }]} estadoCorrida="detenida" ahora={AHORA} />));
    expect(nodo.innerHTML).toBe('');
    expect(todoElTexto()).not.toContain('\u2014');
  });
});
