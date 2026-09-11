// Piezas pequenas compartidas por las pantallas: chips, botones, secciones,
// vacios, confirmacion en dos pasos inline (nunca window.confirm), el aviso
// de datos de muestra y el momento (hora absoluta y relativa).

import { useState, type ReactNode } from 'react';
import type { EstadoConexion } from '../datos/tipos';
import { fechaCorta, tiempoRelativo } from '../lib/formato';
import { IconAlert } from './icons';

export function Chip({ tono, children, title }: { tono?: 'ok' | 'aviso' | 'mal' | 'acento' | 'borde' | 'neutro'; children: ReactNode; title?: string }) {
  return (
    <span className={`chip${tono && tono !== 'neutro' ? ` chip-${tono}` : ''}`} title={title}>
      {children}
    </span>
  );
}

/** Hora absoluta y relativa a la vez: "10 sep, 14:30 · hace 5 min". En una
 *  corrida de dias, "hace 31 min" no basta para auditar. */
export function Momento({ t, ahora, soloRelativo = false }: { t: number; ahora: number; soloRelativo?: boolean }) {
  const abs = fechaCorta(t);
  const rel = tiempoRelativo(t, ahora);
  return (
    <time className="momento" dateTime={new Date(t).toISOString()} title={new Date(t).toLocaleString('es')}>
      {soloRelativo ? rel : `${abs} · ${rel}`}
    </time>
  );
}

export function Seccion({ titulo, nota, acciones, children }: { titulo: string; nota?: string; acciones?: ReactNode; children: ReactNode }) {
  return (
    <section className="seccion">
      <div className="seccion-titulo">
        <div>
          <h3>{titulo}</h3>
          {nota && <p>{nota}</p>}
        </div>
        {acciones && <div className="acciones">{acciones}</div>}
      </div>
      {children}
    </section>
  );
}

export function Vacio({ titulo, children }: { titulo: string; children?: ReactNode }) {
  return (
    <div className="vacio">
      <h3>{titulo}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}

interface ConfirmarProps {
  etiqueta: string;
  pregunta: string;
  pedirTexto?: { etiqueta: string; marcador: string };
  /** Contenido extra dentro de la confirmacion (por ejemplo un interruptor). */
  extra?: ReactNode;
  peligro?: boolean;
  primario?: boolean;
  disabled?: boolean;
  clase?: string;
  onConfirmar: (texto: string) => void;
}

/** Boton con confirmacion inline en dos pasos. Con `pedirTexto`, ademas exige
 *  un motivo: es lo que se usa para descartar una hipotesis o detener una
 *  corrida, donde el motivo queda en el rastro. */
export function Confirmar({ etiqueta, pregunta, pedirTexto, extra, peligro, primario, disabled, clase, onConfirmar }: ConfirmarProps) {
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState('');
  if (!abierto) {
    return (
      <button type="button" className={`btn ${peligro ? 'btn-peligro' : ''} ${primario ? 'btn-primario' : ''} ${clase ?? ''}`} disabled={disabled} onClick={() => setAbierto(true)}>
        {etiqueta}
      </button>
    );
  }
  const falta = pedirTexto !== undefined && texto.trim() === '';
  return (
    <div className="confirmacion" role="group" aria-label={pregunta}>
      <p>{pregunta}</p>
      {pedirTexto && (
        <div className="campo">
          <label htmlFor={`conf-${etiqueta}`}>{pedirTexto.etiqueta}</label>
          <textarea id={`conf-${etiqueta}`} value={texto} placeholder={pedirTexto.marcador} onChange={(e) => setTexto(e.target.value)} autoFocus />
        </div>
      )}
      {extra}
      <div className="acciones">
        <button
          type="button"
          className={`btn ${peligro ? 'btn-peligro' : 'btn-primario'}`}
          disabled={falta}
          onClick={() => {
            onConfirmar(texto);
            setAbierto(false);
            setTexto('');
          }}
        >
          {etiqueta}
        </button>
        <button type="button" className="btn btn-fantasma" onClick={() => setAbierto(false)}>
          Cancelar
        </button>
      </div>
    </div>
  );
}

export function AvisoMuestra({ conexion }: { conexion: EstadoConexion }) {
  if (conexion !== 'muestra') return null;
  return (
    <div className="aviso-muestra" role="status">
      <IconAlert size={14} />
      <span>
        Datos de muestra: Rosa todavia no esta conectada. La corrida que ves avanza con una simulacion para poder juzgar la interfaz. Nada de lo
        que hagas aqui llega a un servidor.
      </span>
    </div>
  );
}

/** Barra de progreso fina con su fraccion y marcas opcionales. */
export function Barra({ fraccion, marcas = [], tono }: { fraccion: number; marcas?: number[]; tono?: 'ok' | 'aviso' | 'mal' }) {
  const pct = Math.max(0, Math.min(1, fraccion)) * 100;
  return (
    <div className={`presupuesto-barra ${tono ? `barra-${tono}` : ''}`} aria-hidden="true">
      <i style={{ width: `${pct}%` }} />
      {marcas.map((m) => (
        <b key={m} style={{ left: `${m * 100}%` }} />
      ))}
    </div>
  );
}

/** Descarga un texto como fichero. Rosa es una app propia: las descargas
 *  funcionan; el nombre lleva la fecha para no pisar versiones. */
export function descargar(nombre: string, contenido: string, tipo = 'text/plain;charset=utf-8'): void {
  const blob = new Blob([contenido], { type: tipo });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
