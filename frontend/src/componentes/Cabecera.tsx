import { IconMenu, IconSearch } from './icons';
import { fijarModo, useModo } from '../lib/modo';

interface Props {
  miga: string | null;
  titulo: string;
  /** Decisiones que esperan a una persona en la investigacion actual. */
  esperan: number;
  onMenu: () => void;
  onBuscar: () => void;
  onAyuda?: () => void;
}

export function Cabecera({ miga, titulo, esperan, onMenu, onBuscar, onAyuda }: Props) {
  const modo = useModo();
  return (
    <header className="cabecera">
      <button type="button" className="btn btn-fantasma btn-icono btn-menu" aria-label="Abrir el menú" onClick={onMenu}>
        <IconMenu />
      </button>
      {miga && <span className="cabecera-miga">{miga} /</span>}
      <h1>{titulo}</h1>
      <div className="cabecera-derecha">
        {esperan > 0 && (
          <span className="chip chip-aviso" title="Permisos, incidencias, planes e hipótesis que esperan tu decisión">
            {esperan} {esperan === 1 ? 'espera' : 'esperan'}
          </span>
        )}
        <button type="button" className="btn btn-fantasma btn-icono" aria-label="Buscar (Cmd+K)" onClick={onBuscar}>
          <IconSearch size={15} />
        </button>
        <div className="segmentos segmentos-modo" role="group" aria-label="Modo de la interfaz" title="Sencillo: lo que decides tú, con la ingeniería plegada. Detalle: todo abierto.">
          <button type="button" aria-pressed={modo === 'sencillo'} onClick={() => fijarModo('sencillo')}>
            Sencillo
          </button>
          <button type="button" aria-pressed={modo === 'detalle'} onClick={() => fijarModo('detalle')}>
            Detalle
          </button>
        </div>
        {onAyuda && (
          <button type="button" className="btn btn-fantasma btn-icono" aria-label="Ver el recorrido de ROSA2018" title="Cómo funciona ROSA2018, en cinco pasos" onClick={onAyuda}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>?</span>
          </button>
        )}
      </div>
    </header>
  );
}
