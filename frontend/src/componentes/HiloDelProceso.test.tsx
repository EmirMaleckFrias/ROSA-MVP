import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import type { EstadoCorrida } from '../datos/tipos';
import { HiloDelProceso } from './HiloDelProceso';

vi.mock('../lib/movimiento', () => ({ useMovimientoReducido: () => true }));

describe('visibilidad de las etapas de investigación', () => {
  for (const situacion of ['en_marcha', 'esperando_plan', 'esperando_aprobacion', 'pausada', 'pausada_por_presupuesto', 'detenida', 'terminada'] as EstadoCorrida[]) {
    it(`respeta el estado ${situacion}`, () => {
      const estado = estadoDeMuestra();
      const inv = estado.investigaciones[0]!;
      estado.corridas = estado.corridas.filter(c => c.investigacionId === inv.id).slice(0, 1);
      estado.corridas[0]!.estado = situacion;
      const html = renderToStaticMarkup(<HiloDelProceso estado={estado} inv={inv} pantalla="mundo" />);
      expect(html.includes('Etapas de la investigación')).toBe(['en_marcha', 'esperando_plan', 'esperando_aprobacion'].includes(situacion));
    });
  }
  it('no muestra etapas por una corrida activa de otra investigación', () => {
    const estado = estadoDeMuestra();
    const inv = estado.investigaciones[0]!;
    estado.corridas = estado.corridas.map(c => ({...c, investigacionId: 'otra', estado: 'en_marcha'}));
    expect(renderToStaticMarkup(<HiloDelProceso estado={estado} inv={inv} pantalla="mundo" />)).toBe('');
  });
});
