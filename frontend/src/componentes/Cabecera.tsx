import type { EstadoConexion } from '../datos/tipos';
import { IconMenu, IconSearch } from './icons';
import { fijarModo, useModo } from '../lib/modo';

const CONEXION: Record<EstadoConexion, string> = {
  conectando: 'Conectando',
  en_linea: 'En linea',
  sin_conexion: 'Sin conexión',
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
  onAyuda?: () => void;
}

export function Cabecera({ miga, titulo, conexion, esperan, onMenu, onBuscar, onAyuda }: Props) {
  const modo = useModo();
  return (
    <header className="cabecera">
      <button type="button" className="btn btn-fantasma btn-icono btn-menu" aria-label="Abrir el menu" onClick={onMenu}>
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
        <div className="segmentos segmentos-modo" role="group" aria-label="Modo de la interfaz" title="Sencillo: lo que decides tu, con la ingenieria plegada. Detalle: todo abierto.">
          <button type="button" aria-pressed={modo === 'sencillo'} onClick={() => fijarModo('sencillo')}>
            Sencillo
          </button>
          <button type="button" aria-pressed={modo === 'detalle'} onClick={() => fijarModo('detalle')}>
            Detalle
          </button>
        </div>
        {onAyuda && (
          <button type="button" className="btn btn-fantasma btn-icono" aria-label="Ver el recorrido de Rosa" title="Como funciona Rosa, en cinco pasos" onClick={onAyuda}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>?</span>
          </button>
        )}
        <span className={`estado-conexion ${conexion}`} title={CONEXION[conexion]}>
          <i aria-hidden="true" />
          {CONEXION[conexion]}
        </span>
      </div>
    </header>
  );
}
