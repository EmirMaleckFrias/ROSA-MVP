// Artefactos versionados: informes, tablas y el estado del modelo de mundo
// por iteracion. Selector de versiones y diff contra cualquier anterior; las
// versiones viejas son de solo lectura. Exportacion de todas las fuentes de
// la investigacion en BibTeX, RIS y CSV.

import { useState } from 'react';
import { acciones } from '../datos/almacen';
import type { Artefacto, EstadoRosa, Fuente, Investigacion } from '../datos/tipos';
import { IconStar } from '../componentes/icons';
import { AvisoMuestra, Chip, Momento, Vacio, descargar } from '../componentes/piezas';
import { diferenciarLineas, resumenDiff } from '../lib/diff';
import { TIPO_ARTEFACTO } from '../lib/etiquetas';
import { aBibtex, aCsv, aRis } from '../lib/exportar';
import { rutaDe } from '../lib/ruta';

function DetalleArtefacto({ a, inv, ahora }: { a: Artefacto; inv: Investigacion; ahora: number }) {
  const ultima = a.versiones[a.versiones.length - 1]!;
  const [n, setN] = useState(ultima.n);
  const [contra, setContra] = useState<number | null>(null);
  const version = a.versiones.find((v) => v.n === n) ?? ultima;
  const base = contra !== null ? a.versiones.find((v) => v.n === contra) ?? null : null;
  const diff = base ? diferenciarLineas(base.contenido, version.contenido) : null;
  const resumen = diff ? resumenDiff(diff) : null;
  return (
    <div className="contenido">
      <p style={{ marginBottom: 14 }}>
        <a className="enlace" href={rutaDe(inv.id, 'artefactos')}>
          Volver a los artefactos
        </a>
      </p>
      <div className="pantalla-cabecera">
        <div>
          <h2 className="mono" style={{ fontSize: 18 }}>
            {a.nombre}
          </h2>
          <p>
            {TIPO_ARTEFACTO[a.tipo]} · {a.versiones.length} {a.versiones.length === 1 ? 'version' : 'versiones'}
          </p>
        </div>
        <div className="acciones">
          <button type="button" className="btn" onClick={() => descargar(a.nombre, version.contenido)}>
            Descargar v{version.n}
          </button>
          <button type="button" className={`btn ${a.destacado ? 'btn-primario' : ''}`} onClick={() => acciones.destacarArtefacto(a.id)}>
            <IconStar size={13} /> {a.destacado ? 'Destacado' : 'Destacar'}
          </button>
        </div>
      </div>
      <div className="acciones" style={{ marginBottom: 14 }}>
        <span className="meta">Version</span>
        <div className="segmentos" role="group" aria-label="Version">
          {a.versiones.map((v) => (
            <button key={v.n} type="button" aria-pressed={v.n === n} onClick={() => setN(v.n)} title={`${v.resumen} · ${new Date(v.creadaEn).toLocaleString('es')}`}>
              v{v.n}
            </button>
          ))}
        </div>
        {a.versiones.length > 1 && (
          <>
            <span className="meta">Comparar con</span>
            <select className="entrada" style={{ width: 'auto', minHeight: 30 }} value={contra ?? ''} onChange={(e) => setContra(e.target.value === '' ? null : Number(e.target.value))} aria-label="Comparar con">
              <option value="">Sin comparar</option>
              {a.versiones
                .filter((v) => v.n !== n)
                .map((v) => (
                  <option key={v.n} value={v.n}>
                    v{v.n} · {v.resumen}
                  </option>
                ))}
            </select>
          </>
        )}
        {n !== ultima.n && <Chip tono="aviso">Version anterior, solo lectura</Chip>}
      </div>
      <p className="meta" style={{ marginBottom: 10 }}>
        v{version.n} · iteracion {version.iteracion} · <Momento t={version.creadaEn} ahora={ahora} /> · {version.resumen}
        {resumen && (
          <>
            {' · '}
            <span className="subida">+{resumen.anadidas}</span> <span className="bajada">-{resumen.quitadas}</span> frente a v{contra}
          </>
        )}
      </p>
      {diff ? (
        <pre className="diff">
          {diff.map((l, i) => (
            <div key={i} className={l.tipo}>
              {l.tipo === 'anadida' ? '+ ' : l.tipo === 'quitada' ? '- ' : '  '}
              {l.texto}
            </div>
          ))}
        </pre>
      ) : (
        <pre className="contenido-artefacto">{version.contenido}</pre>
      )}
    </div>
  );
}

export function Artefactos({ inv, estado, ahora, detalleId }: { inv: Investigacion; estado: EstadoRosa; ahora: number; detalleId: string | null }) {
  const [busqueda, setBusqueda] = useState('');
  const propios = estado.artefactos.filter((a) => a.investigacionId === inv.id);
  const seleccionado = propios.find((a) => a.id === detalleId);
  if (seleccionado) return <DetalleArtefacto a={seleccionado} inv={inv} ahora={ahora} />;
  const q = busqueda.trim().toLowerCase();
  const visibles = propios.filter((a) => q === '' || a.nombre.toLowerCase().includes(q) || TIPO_ARTEFACTO[a.tipo].toLowerCase().includes(q)).sort((a, b) => Number(b.destacado) - Number(a.destacado));
  const fuentes: Fuente[] = [];
  const vistas = new Set<string>();
  for (const h of estado.hipotesis) {
    if (h.investigacionId !== inv.id) continue;
    for (const f of h.procedencia.fuentes) {
      if (!vistas.has(f.id)) {
        vistas.add(f.id);
        fuentes.push(f);
      }
    }
  }
  const fecha = new Date(ahora).toISOString().slice(0, 10);
  return (
    <div className="contenido">
      <AvisoMuestra conexion={estado.conexion} />
      <div className="pantalla-cabecera" style={{ marginTop: 16 }}>
        <div>
          <h2>Artefactos</h2>
          <p>Lo que Rosa guarda en cada iteracion: informes, tablas, el estado del modelo de mundo. Cada guardado con el mismo nombre es una version nueva.</p>
        </div>
        <input className="entrada" style={{ maxWidth: 300 }} value={busqueda} placeholder="Buscar artefactos" onChange={(e) => setBusqueda(e.target.value)} aria-label="Buscar artefactos" />
      </div>
      <div className="acciones" style={{ marginBottom: 16 }}>
        <span className="meta">
          {fuentes.length} {fuentes.length === 1 ? 'fuente citada' : 'fuentes citadas'} en la investigacion. Exportar:
        </span>
        <button type="button" className="btn btn-s" disabled={fuentes.length === 0} onClick={() => descargar(`rosa-${inv.id}-fuentes-${fecha}.bib`, aBibtex(fuentes))}>
          BibTeX
        </button>
        <button type="button" className="btn btn-s" disabled={fuentes.length === 0} onClick={() => descargar(`rosa-${inv.id}-fuentes-${fecha}.ris`, aRis(fuentes))}>
          RIS
        </button>
        <button type="button" className="btn btn-s" disabled={fuentes.length === 0} onClick={() => descargar(`rosa-${inv.id}-fuentes-${fecha}.csv`, aCsv(fuentes), 'text/csv;charset=utf-8')}>
          CSV
        </button>
      </div>
      {visibles.length === 0 ? (
        <Vacio titulo="Sin artefactos">Nada coincide con la busqueda.</Vacio>
      ) : (
        <div className="artefactos-rejilla">
          {visibles.map((a) => {
            const ultima = a.versiones[a.versiones.length - 1]!;
            return (
              <a key={a.id} className="tarjeta tarjeta-interactiva artefacto" href={rutaDe(inv.id, 'artefactos', a.id)}>
                <div className="artefacto-tipo">
                  <span>{TIPO_ARTEFACTO[a.tipo]}</span>
                  {a.destacado && <IconStar size={13} />}
                </div>
                <h3>{a.nombre}</h3>
                <p className="meta">{ultima.resumen}</p>
                <div className="versiones">
                  <Chip>v{ultima.n}</Chip>
                  <span className="meta">
                    <Momento t={ultima.creadaEn} ahora={ahora} soloRelativo />
                  </span>
                </div>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
