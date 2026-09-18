// @vitest-environment jsdom
// Prueba de punta a punta del vigilante de modelos en la interfaz (18 de
// septiembre de 2026): lo que rodea a la franja de modelos mientras la corrida
// está en `esperando_modelo`. Guardias de los pendientes cruzados que quedaron
// fuera de los ficheros del bloque: el hilo de etapas sigue pintado y la
// tarjeta de inicio enseña la espera en ámbar, como las demás esperas.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import type { EstadoCorrida } from '../datos/tipos';
import { Inicio } from '../pantallas/Inicio';
import { HiloDelProceso } from './HiloDelProceso';

vi.mock('../lib/movimiento', () => ({ useMovimientoReducido: () => true }));

function conEstado(estado: EstadoCorrida) {
  const e = estadoDeMuestra();
  const inv = e.investigaciones[0]!;
  e.corridas = e.corridas.filter((c) => c.investigacionId === inv.id).slice(0, 1);
  e.corridas[0]!.estado = estado;
  e.corridas[0]!.esperandoModelo = estado === 'esperando_modelo' ? { rol: 'juez', modelo: 'anthropic/claude-opus-5', desde: Date.now() - 600_000, ultimoSondeo: null, proximoSondeo: Date.now() + 50_000, pasoId: null, intentos: 4 } : null;
  return { e, inv };
}

describe('el hilo de etapas mientras ROSA2018 espera a un modelo', () => {
  it('sigue pintado en esperando_modelo, como en las demás esperas de la corrida viva', () => {
    for (const estado of ['en_marcha', 'esperando_plan', 'esperando_aprobacion', 'esperando_modelo'] as EstadoCorrida[]) {
      const { e, inv } = conEstado(estado);
      expect(renderToStaticMarkup(<HiloDelProceso estado={e} inv={inv} pantalla="corrida" />), estado).toContain('Etapas de la investigación');
    }
  });

  it('no aparece por una corrida cerrada o pausada por la persona (control)', () => {
    for (const estado of ['pausada', 'pausada_por_presupuesto', 'detenida', 'terminada'] as EstadoCorrida[]) {
      const { e, inv } = conEstado(estado);
      expect(renderToStaticMarkup(<HiloDelProceso estado={e} inv={inv} pantalla="corrida" />), estado).toBe('');
    }
  });
});

describe('la tarjeta de inicio mientras ROSA2018 espera a un modelo', () => {
  function chipDeLaCorrida(estado: EstadoCorrida): Element {
    const { e } = conEstado(estado);
    const div = document.createElement('div');
    div.innerHTML = renderToStaticMarkup(<Inicio estado={e} ahora={Date.now()} />);
    const chip = [...div.querySelectorAll('.chip')].find((x) => /^Corrida \d+/.test(x.textContent ?? ''));
    expect(chip, `chip de la corrida en ${estado}`).toBeDefined();
    return chip!;
  }

  it('enseña la espera al modelo en ámbar, como las esperas de plan, aprobación y presupuesto', () => {
    const chip = chipDeLaCorrida('esperando_modelo');
    expect(chip.className.split(/\s+/)).toContain('chip-aviso');
    expect(chip.textContent).toContain('Esperando al modelo');
  });

  it('en marcha va en acento y cerrada sin tono (control)', () => {
    expect(chipDeLaCorrida('en_marcha').className.split(/\s+/)).toContain('chip-acento');
    expect(chipDeLaCorrida('terminada').className.split(/\s+/)).not.toContain('chip-aviso');
  });
});
