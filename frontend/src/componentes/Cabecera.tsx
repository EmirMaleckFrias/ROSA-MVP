import type { EstadoConexion } from '../datos/tipos';
import { IconMenu, IconSearch } from './icons';

const CONEXION: Record<EstadoConexion, string> = {
  conectando: 'Conectando',
  en_linea: 'En linea',
  sin_conexion: 'Sin conexion',
  muestra: 'Datos de muestra',
};

interface Props {
  miga: string | null;
  titulo: string;
  conexion: EstadoConexion;
  /** Decisiones que esperan a una persona en la investigacion actual. */
  esperan: number;
  onMenu: () => void;
  onBuscar: () => void;
}

export function Cabecera({ miga, titulo, conexion, esperan, onMenu, onBuscar }: Props) {
  return (
    <header className="cabecera">
      <button type="button" className="btn btn-fantasma btn-icono btn-menu" aria-label="Abrir el menu" onClick={onMenu}>
        <IconMenu />
      </button>
      {miga && <span className="cabecera-miga">{miga} /</span>}
      <h1>{titulo}</h1>
      <div className="cabecera-derecha">
        {esperan > 0 && (
          <span className="chip chip-aviso" title="Permisos, incidencias, planes e hipotesis que esperan tu decision">
            {esperan} {esperan === 1 ? 'espera' : 'esperan'}
          </span>
        )}
        <button type="button" className="btn btn-fantasma btn-icono" aria-label="Buscar (Cmd+K)" onClick={onBuscar}>
          <IconSearch size={15} />
        </button>
        <span className={`estado-conexion ${conexion}`} title={CONEXION[conexion]}>
          <i aria-hidden="true" />
          {CONEXION[conexion]}
        </span>
      </div>
    </header>
  );
}
