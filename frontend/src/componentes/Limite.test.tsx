// @vitest-environment jsdom
import { renderToString } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { Limite } from './Limite';

function Rompe(): never {
  throw new Error('falta el campo dosis');
}

describe('limite de error', () => {
  it('muestra el mensaje del fallo en vez de una pagina vacia', () => {
    const silencio = vi.spyOn(console, 'error').mockImplementation(() => {});
    // renderToString no monta limites de error, asi que se comprueba el estado
    // derivado y el render del componente con ese estado.
    const estado = Limite.getDerivedStateFromError(new Error('falta el campo dosis'));
    expect(estado.error?.message).toBe('falta el campo dosis');
    const limite = new Limite({ children: null, ambito: 'la pantalla Cola' });
    limite.state = estado;
    const html = renderToString(<>{limite.render()}</>);
    expect(html).toContain('falló al pintarse');
    expect(html).toContain('falta el campo dosis');
    expect(html).toContain('Volver a intentar');
    silencio.mockRestore();
  });

  it('sin fallo pinta a los hijos tal cual', () => {
    const html = renderToString(
      <Limite>
        <span>hola</span>
      </Limite>,
    );
    expect(html).toBe('<span>hola</span>');
    expect(typeof Rompe).toBe('function');
  });
});
