// "Mientras no estabas": lo que paso desde la ultima visita, con cada linea
// enlazada a su pantalla. Se ensena al entrar y se cierra con "Visto", que
// marca la visita. El mismo texto es lo que se manda por Slack o correo.

import { useState } from 'react';
import type { Digest } from '../lib/digest';
import { digestComoTexto } from '../lib/digest';
import { TIPO_EVENTO } from '../lib/etiquetas';
import { formatearDuracion } from '../lib/formato';
import { IconCheck, IconCopy } from './icons';
import { Chip, Momento } from './piezas';

export function Resumen({ d, titulo, ahora, onVisto }: { d: Digest; titulo: string; ahora: number; onVisto: () => void }) {
  const [copiado, setCopiado] = useState(false);
  const [todos, setTodos] = useState(false);
  if (d.eventos.length === 0 && d.esperan.total === 0) return null;
  const desde = d.desde !== null ? formatearDuracion(ahora - d.desde) : null;
  const visibles = todos ? d.eventos : d.eventos.slice(0, 6);
  return (
    <section className="resumen" aria-label="Mientras no estabas">
      <div className="acciones" style={{ justifyContent: 'space-between' }}>
        <div>
          <h3 style={{ fontSize: 15, fontWeight: 600 }}>Mientras no estabas{desde ? ` (${desde})` : ''}</h3>
          <p className="meta">Lo que Rosa hizo y lo que te espera. Cada linea lleva a su sitio.</p>
        </div>
        <div className="acciones">
          <button
            type="button"
            className="btn btn-fantasma btn-s"
            onClick={() => {
              void navigator.clipboard?.writeText(digestComoTexto(d, titulo)).then(() => setCopiado(true));
              window.setTimeout(() => setCopiado(false), 2000);
            }}
            title="Copiar como texto (es lo que se manda por Slack o correo)"
          >
            {copiado ? <IconCheck size={13} /> : <IconCopy size={13} />} {copiado ? 'Copiado' : 'Copiar'}
          </button>
          <button type="button" className="btn btn-s" onClick={onVisto}>
            Visto
          </button>
        </div>
      </div>
      <ul className="resumen-lineas">
        {d.lineas.map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
      {d.eventos.length > 0 && (
        <ol className="resumen-eventos">
          {visibles.map((e) => (
            <li key={e.id}>
              <Chip tono={e.tipo === 'incidencia' ? 'mal' : e.tipo === 'permiso_pendiente' || e.tipo === 'presupuesto' ? 'aviso' : undefined}>{TIPO_EVENTO[e.tipo]}</Chip>
              {e.ruta ? (
                <a className="enlace" href={e.ruta}>
                  {e.texto}
                </a>
              ) : (
                <span>{e.texto}</span>
              )}
              <span className="meta">
                <Momento t={e.t} ahora={ahora} />
              </span>
            </li>
          ))}
        </ol>
      )}
      {d.eventos.length > 6 && (
        <button type="button" className="enlace" style={{ alignSelf: 'flex-start', fontSize: 13 }} onClick={() => setTodos((v) => !v)}>
          {todos ? 'Ver menos' : `Ver los ${d.eventos.length} eventos`}
        </button>
      )}
    </section>
  );
}
