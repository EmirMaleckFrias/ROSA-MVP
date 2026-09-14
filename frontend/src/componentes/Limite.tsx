// Limite de error: si una pantalla falla al pintarse, React desmonta todo el
// arbol y la persona ve la pagina vacia (negra en tema oscuro) sin ninguna
// pista. Este componente atrapa el fallo, deja la barra y la cabecera en su
// sitio y muestra que paso, con dos salidas: volver a intentar o ir al inicio.
// El mensaje tecnico se ensena tal cual para poder reportarlo.

import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** Cambiar esta clave (por ejemplo, la ruta) reinicia el limite. */
  clave?: string;
  ambito?: string;
}

interface Estado {
  error: Error | null;
}

export class Limite extends Component<Props, Estado> {
  state: Estado = { error: null };

  static getDerivedStateFromError(error: Error): Estado {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Queda en la consola del navegador con la pila de componentes.
    console.error(`[Rosa] fallo al pintar ${this.props.ambito ?? 'la interfaz'}:`, error, info.componentStack);
  }

  componentDidUpdate(anterior: Props): void {
    if (this.state.error && anterior.clave !== this.props.clave) this.setState({ error: null });
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children;
    const mensaje = this.state.error.message || String(this.state.error);
    return (
      <div className="limite-error" role="alert">
        <h3>Esta parte de Rosa falló al pintarse</h3>
        <p>
          Los datos están a salvo: el fallo es de la pantalla, no del registro. Puedes volver a intentarlo o ir al inicio. Si se repite, copia el mensaje de abajo y pásaselo a quien mantiene Rosa.
        </p>
        <pre className="limite-detalle">{mensaje}</pre>
        <div className="acciones">
          <button type="button" className="btn btn-primario" onClick={() => this.setState({ error: null })}>
            Volver a intentar
          </button>
          <a className="btn" href="#/">
            Ir al inicio
          </a>
          <button type="button" className="btn btn-fantasma" onClick={() => window.location.reload()}>
            Recargar Rosa
          </button>
        </div>
      </div>
    );
  }
}
