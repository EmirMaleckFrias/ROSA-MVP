// Busqueda global (Cmd+K o Ctrl+K): hipotesis, hechos, fuentes, artefactos,
// iteraciones y eventos de la investigacion actual. Overlay con lista y
// teclado: flechas para moverse, Enter para ir, Escape para cerrar.

import { useEffect, useMemo, useRef, useState } from 'react';
import type { EstadoRosa } from '../datos/tipos';
import { buscar, type Resultado } from '../lib/buscar';
import { cabeceras } from '../datos/almacen';
import { IconSearch, IconX } from './icons';
import { Chip } from './piezas';

const TIPO: Record<Resultado['tipo'], string> = {
  hipotesis: 'Hipótesis',
  hecho: 'Modelo de mundo',
  fuente: 'Fuente',
  artefacto: 'Artefacto',
  iteracion: 'Iteración',
  evento: 'Evento',
};

export function BusquedaGlobal({ estado, investigacionId, abierta, onCerrar }: { estado: EstadoRosa; investigacionId: string | null; abierta: boolean; onCerrar: () => void }) {
  const [q, setQ] = useState('');
  const [indice, setIndice] = useState(0);
  const entrada = useRef<HTMLInputElement>(null);
  const resultados = useMemo(() => (investigacionId ? buscar(estado, investigacionId, q) : []), [estado, investigacionId, q]);
  // Por significado (índice semántico del servidor): se pide con retardo, solo
  // con servidor conectado y a partir de cuatro letras; nunca bloquea la lista
  // por palabras, que sale al instante.
  const [semanticos, setSemanticos] = useState<{ id: string; tipo: string; texto: string; similitud: number }[]>([]);
  useEffect(() => {
    if (!abierta || estado.conexion === 'muestra' || q.trim().length < 4) {
      setSemanticos([]);
      return;
    }
    let vivo = true;
    const t = window.setTimeout(async () => {
      try {
        const r = await fetch(`/api/buscar?q=${encodeURIComponent(q.trim())}${investigacionId ? `&investigacion=${encodeURIComponent(investigacionId)}` : ''}&k=6`, { headers: cabeceras(false), cache: 'no-store' });
        if (!r.ok) throw new Error(String(r.status));
        const d = (await r.json()) as { disponible: boolean; resultados: { id: string; tipo: string; texto: string; similitud: number }[] };
        if (vivo) setSemanticos(d.disponible ? d.resultados : []);
      } catch {
        if (vivo) setSemanticos([]);
      }
    }, 350);
    return () => {
      vivo = false;
      window.clearTimeout(t);
    };
  }, [q, abierta, estado.conexion, investigacionId]);
  const rutaSemantica = (r: { id: string; tipo: string }): string | null => {
    const [tipo, id] = r.id.split(':', 2);
    if (!investigacionId || !id) return null;
    if (tipo === 'hipotesis') return `#/investigaciones/${investigacionId}/hipotesis/${id}`;
    if (tipo === 'hecho') return `#/investigaciones/${investigacionId}/mundo`;
    if (tipo === 'fuente') return `#/investigaciones/${investigacionId}/panorama`;
    return null;
  };

  useEffect(() => {
    if (abierta) {
      setQ('');
      setIndice(0);
      window.setTimeout(() => entrada.current?.focus(), 0);
    }
  }, [abierta]);

  if (!abierta) return null;
  const ir = (r: Resultado) => {
    window.location.hash = r.ruta;
    onCerrar();
  };
  return (
    <div className="scrim scrim-visible" onClick={onCerrar} role="presentation">
      <div className="busqueda" role="dialog" aria-label="Buscar en la investigación" onClick={(e) => e.stopPropagation()}>
        <div className="busqueda-entrada">
          <IconSearch size={15} />
          <input
            ref={entrada}
            value={q}
            placeholder={investigacionId ? 'Buscar hipótesis, hechos, fuentes, artefactos, iteraciones' : 'Abre una investigación para buscar dentro'}
            disabled={investigacionId === null}
            onChange={(e) => {
              setQ(e.target.value);
              setIndice(0);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Escape') onCerrar();
              if (e.key === 'ArrowDown') {
                e.preventDefault();
                setIndice((i) => Math.min(resultados.length - 1, i + 1));
              }
              if (e.key === 'ArrowUp') {
                e.preventDefault();
                setIndice((i) => Math.max(0, i - 1));
              }
              if (e.key === 'Enter' && resultados[indice]) ir(resultados[indice]!);
            }}
            aria-label="Buscar"
          />
          <button type="button" className="btn btn-fantasma btn-icono" aria-label="Cerrar" onClick={onCerrar}>
            <IconX size={14} />
          </button>
        </div>
        {q.trim().length >= 2 && (
          <ul className="busqueda-resultados">
            {resultados.length === 0 && <li className="meta">Nada en esta investigación coincide con «{q}».</li>}
            {resultados.map((r, i) => (
              <li key={`${r.tipo}-${r.titulo}-${i}`}>
                <button type="button" className={`busqueda-item ${i === indice ? 'busqueda-activo' : ''}`} onMouseEnter={() => setIndice(i)} onClick={() => ir(r)}>
                  <Chip>{TIPO[r.tipo]}</Chip>
                  <span className="busqueda-titulo">{r.titulo}</span>
                  {r.detalle !== '' && <span className="meta">{r.detalle}</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
        {semanticos.length > 0 && (
          <div className="busqueda-semantica">
            <p className="meta" style={{ margin: '8px 0 4px' }}>Por significado (índice semántico)</p>
            <ul className="busqueda-resultados">
              {semanticos.map((r) => {
                const ruta = rutaSemantica(r);
                return (
                  <li key={r.id}>
                    <button
                      type="button"
                      className="busqueda-item"
                      onClick={() => {
                        if (ruta) {
                          window.location.hash = ruta;
                          onCerrar();
                        }
                      }}
                    >
                      <Chip>{r.tipo === 'hecho' ? 'Hecho' : r.tipo === 'hipotesis' ? 'Hipótesis' : 'Fuente'}</Chip>
                      <span className="busqueda-titulo">{r.texto.slice(0, 120)}</span>
                      <span className="meta">similitud {r.similitud.toFixed(2)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
        <p className="meta busqueda-pie">Flechas para moverte, Enter para abrir, Escape para cerrar.</p>
      </div>
    </div>
  );
}
