// @vitest-environment jsdom
// Humo del rework: la aplicacion entera se renderiza con los datos de
// muestra sin lanzar (hilo del proceso, recorrido, deshacer, listas
// animadas). Un import roto o un tipo mal casado con Motion saldria aqui.

import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import App from './App';
import { HiloDelProceso, estadoDelHilo } from './componentes/HiloDelProceso';
import { estadoDeMuestra } from './datos/muestra';

describe('rework de la interfaz', () => {
  it('la aplicacion se renderiza con los datos de muestra', () => {
    const html = renderToString(<App />);
    expect(html).toContain('Rosa');
    expect(html.length).toBeGreaterThan(2000);
  });
  it('el hilo del proceso deriva etapas del estado sin inventar', () => {
    const e = estadoDeMuestra();
    const inv = e.investigaciones[0]!;
    const corrida = e.corridas.filter((c) => c.investigacionId === inv.id).sort((a, b) => b.numero - a.numero)[0] ?? null;
    const hilo = estadoDelHilo(e, inv, corrida);
    expect(hilo.hechas.size).toBeGreaterThan(0);
    expect(['plan', 'literatura', 'verificar', 'mundo', 'hipotesis', 'candidatas', 'laboratorio', null]).toContain(hilo.activa);
    const html = renderToString(<HiloDelProceso estado={e} inv={inv} pantalla="corrida" />);
    expect(html).toContain('Buscar literatura');
    expect(html).toContain('Hipótesis y Killer');
  });
});
