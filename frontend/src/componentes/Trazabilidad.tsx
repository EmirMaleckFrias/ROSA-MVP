// La cadena de evidencia de una corrida como arbol plegable: cada consulta,
// las fuentes que trajo, y las afirmaciones que salieron de cada fuente con
// su veredicto. Es lo que un revisor pide para seguir una cifra hasta su
// origen sin abrir una hipotesis. Lee GET /api/corridas/{id}/evidencia y se
// refresca cuando la corrida cambia (el estado llega por SSE; aqui solo se
// vuelve a pedir la evidencia, que pesa poco). En modo muestra no hay
// servidor y la seccion no se pinta.

import { useEffect, useMemo, useState } from 'react';
import type { Corrida, TipoAfirmacion } from '../datos/tipos';
import { RIESGO_SESGO, TIPO_AFIRMACION, tipoAfirmacion, TIPO_ESTUDIO, TIPO_FUENTE, VEREDICTO } from '../lib/etiquetas';
import { construirArbol, enlaceDe, iteracionesDe, type Evidencia, type FiltroVeredicto, type NodoFuente } from '../lib/evidencia';
import { formatearEntero } from '../lib/formato';
import { Chip, Seccion } from './piezas';

const FILTROS: { clave: FiltroVeredicto; etiqueta: string }[] = [
  { clave: 'todas', etiqueta: 'Todas' },
  { clave: 'sostenidas', etiqueta: 'Sostenidas y parciales' },
  { clave: 'bloqueadas', etiqueta: 'Bloqueadas' },
  { clave: 'sin_verificar', etiqueta: 'Sin comprobar' },
];

export function Trazabilidad({ corrida, activa }: { corrida: Corrida; activa: boolean }) {
  const [evidencia, setEvidencia] = useState<Evidencia | null>(null);
  const [iteracion, setIteracion] = useState<number | null>(null);
  const [filtro, setFiltro] = useState<FiltroVeredicto>('todas');
  const [tipo, setTipo] = useState<TipoAfirmacion | 'todos'>('todos');
  const [abiertas, setAbiertas] = useState<Set<string>>(new Set());

  // Se vuelve a pedir cuando cambia el gasto (cada llamada al modelo lo mueve)
  // o el numero de consultas: es la senal barata de que hay evidencia nueva.
  const clave = `${corrida.id}:${corrida.gasto.llamadas}:${corrida.busqueda.consultas.length}:${corrida.estado}`;
  useEffect(() => {
    if (!activa) return;
    let vivo = true;
    fetch(`/api/corridas/${encodeURIComponent(corrida.id)}/evidencia`, { cache: 'no-store' })
      .then((r) => (r.ok ? (r.json() as Promise<Evidencia>) : null))
      .then((d) => {
        if (vivo && d) setEvidencia(d);
      })
      .catch(() => {
        // Sin servidor no hay evidencia que ensenar; la seccion queda vacia.
      });
    return () => {
      vivo = false;
    };
  }, [clave, activa, corrida.id]);

  const iteraciones = useMemo(() => (evidencia ? iteracionesDe(evidencia) : []), [evidencia]);
  const actual = iteracion ?? iteraciones[iteraciones.length - 1] ?? null;
  const arbol = useMemo(() => (evidencia && actual !== null ? construirArbol(evidencia, actual, filtro, tipo) : null), [evidencia, actual, filtro, tipo]);

  if (!activa || !evidencia || arbol === null || actual === null) return null;

  const alternar = (id: string) => {
    setAbiertas((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  };
  const e = arbol.embudo;

  return (
    <Seccion
      detalle titulo="De la consulta a la afirmación"
      nota="Cada consulta, las fuentes que trajo y las afirmaciones que salieron de cada fuente con su veredicto. Una afirmación nace sin comprobar y cambia de color cuando el juez dictamina."
      acciones={
        iteraciones.length > 1 ? (
          <div className="pestanas pestanas-s" role="tablist">
            {iteraciones.map((n) => (
              <button key={n} type="button" role="tab" aria-selected={n === actual} className={n === actual ? 'activa' : ''} onClick={() => setIteracion(n)}>
                Iteracion {n}
              </button>
            ))}
          </div>
        ) : undefined
      }
    >
      <div className="embudo embudo-compacto">
        <div className="embudo-paso">
          <strong>{formatearEntero(e.consultas)}</strong>
          <span>consultas</span>
        </div>
        <div className="embudo-paso">
          <strong>{formatearEntero(e.identificados)}</strong>
          <span>identificados</span>
        </div>
        <div className="embudo-paso">
          <strong>{formatearEntero(e.fuentes)}</strong>
          <span>fuentes leídas · {e.textoCompleto} a texto completo</span>
        </div>
        <div className="embudo-paso">
          <strong>{formatearEntero(e.afirmaciones)}</strong>
          <span>afirmaciones</span>
        </div>
        <div className="embudo-paso">
          <strong>
            <span className="tono-ok">{e.sostenidas}</span> · <span className="tono-aviso">{e.parciales + e.sinVerificar}</span> · <span className="tono-mal">{e.bloqueadas}</span>
          </strong>
          <span>sostenidas · parciales o sin comprobar · bloqueadas</span>
        </div>
      </div>

      <div className="filtros-arbol">
        <div className="pestanas pestanas-s" role="tablist" aria-label="Filtrar por veredicto">
          {FILTROS.map((f) => (
            <button key={f.clave} type="button" role="tab" aria-selected={filtro === f.clave} className={filtro === f.clave ? 'activa' : ''} onClick={() => setFiltro(f.clave)}>
              {f.etiqueta}
            </button>
          ))}
        </div>
        <label className="campo-inline">
          Tipo
          <select value={tipo} onChange={(ev) => setTipo(ev.target.value as TipoAfirmacion | 'todos')}>
            <option value="todos">Todos</option>
            {(Object.keys(TIPO_AFIRMACION) as TipoAfirmacion[]).map((t) => (
              <option key={t} value={t}>
                {TIPO_AFIRMACION[t].etiqueta}
              </option>
            ))}
          </select>
        </label>
      </div>

      {arbol.nodos.length === 0 && <p className="meta">Esta iteración todavía no tiene consultas ni fuentes.</p>}

      <ul className="arbol" role="tree">
        {arbol.nodos.map((n) => {
          const idNodo = `c-${actual}-${n.numero}`;
          const abierta = !abiertas.has(idNodo);
          const nAf = n.fuentes.reduce((s, f) => s + f.afirmaciones.length, 0);
          return (
            <li key={idNodo} className="arbol-nodo" role="treeitem" aria-expanded={abierta}>
              <button type="button" className="arbol-fila" onClick={() => alternar(idNodo)}>
                <span className="arbol-flecha" aria-hidden="true">
                  {abierta ? '▾' : '▸'}
                </span>
                <span className="arbol-icono" aria-hidden="true">
                  ⌕
                </span>
                <span className="arbol-texto">
                  {n.consulta ? (
                    <>
                      <strong>Consulta {n.numero}</strong> <span className="meta">{n.consulta.base}</span>
                      {n.consulta.tema && <span className="arbol-detalle">{n.consulta.tema}</span>}
                    </>
                  ) : (
                    <>
                      <strong>Otras fuentes</strong>
                      <span className="arbol-detalle">Ensayos registrados y fuentes sin consulta anotada</span>
                    </>
                  )}
                </span>
                <span className="arbol-cuentas">
                  {n.consulta && <span className="meta">{formatearEntero(n.consulta.resultados)} resultados</span>}
                  <Chip tono="borde">{n.fuentes.length} fuentes</Chip>
                  <Chip tono="borde">{nAf} afirmaciones</Chip>
                </span>
              </button>
              {abierta && n.consulta && <code className="arbol-consulta">{n.consulta.consulta}</code>}
              {abierta && (
                <ul className="arbol-hijos" role="group">
                  {n.fuentes.length === 0 && <li className="meta arbol-vacio">Ninguna fuente paso el cribado de relevancia.</li>}
                  {n.fuentes.map((f) => (
                    <Fuente key={f.fuente.id} nodo={f} abierta={abiertas.has(`f-${f.fuente.id}`)} onAlternar={() => alternar(`f-${f.fuente.id}`)} />
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </Seccion>
  );
}

function Fuente({ nodo, abierta, onAlternar }: { nodo: NodoFuente; abierta: boolean; onAlternar: () => void }) {
  const f = nodo.fuente;
  const enlace = enlaceDe(f);
  const bloqueadas = nodo.afirmaciones.filter((a) => VEREDICTO[a.veredicto].bloquea).length;
  return (
    <li className="arbol-nodo" role="treeitem" aria-expanded={abierta}>
      <button type="button" className="arbol-fila" onClick={onAlternar}>
        <span className="arbol-flecha" aria-hidden="true">
          {abierta ? '▾' : '▸'}
        </span>
        <span className="arbol-icono" aria-hidden="true">
          ▤
        </span>
        <span className="arbol-texto">
          <strong>{f.referencia}</strong> <span className="meta">{TIPO_FUENTE[f.tipo]}{f.tipoEstudio && f.tipoEstudio in TIPO_ESTUDIO ? ` · ${TIPO_ESTUDIO[f.tipoEstudio as keyof typeof TIPO_ESTUDIO]}` : ''}</span>
          <span className="arbol-detalle">{f.titulo}</span>
        </span>
        <span className="arbol-cuentas">
          {f.riesgoSesgo && f.riesgoSesgo.global !== 'no_aplica' && (
            <Chip tono={RIESGO_SESGO[f.riesgoSesgo.global]?.tono ?? 'borde'} title={`${f.riesgoSesgo.instrumento}: ${f.riesgoSesgo.dominios.map((d) => `${d.id} ${d.nombre}: ${d.juicio.replace('_', ' ')}`).join('; ')}. Veredicto por regla desde las preguntas de senalizacion.`}>
              {f.riesgoSesgo.instrumento} {RIESGO_SESGO[f.riesgoSesgo.global]?.etiqueta ?? f.riesgoSesgo.global}
            </Chip>
          )}
          {f.retraccion === 'retractado' && <Chip tono="mal">Retractado</Chip>}
          {f.retraccion === 'preocupacion' && <Chip tono="aviso">Expresión de preocupación</Chip>}
          {f.retraccion === 'erratum' && <Chip tono="aviso">Erratum</Chip>}
          <Chip tono="borde" title="Puntuación de relevancia del cribado, 0 a 10">
            relevancia {f.relevancia}
          </Chip>
          <Chip tono={f.textoCompleto ? 'acento' : 'borde'}>{f.textoCompleto ? `texto completo · ${f.fragmentos} fragmentos` : 'solo resumen'}</Chip>
          <Chip tono={bloqueadas > 0 ? 'mal' : 'borde'}>
            {nodo.afirmaciones.length} afirmaciones{bloqueadas > 0 ? ` · ${bloqueadas} bloqueadas` : ''}
          </Chip>
        </span>
      </button>
      {abierta && (
        <div className="arbol-hijos">
          <div className="arbol-meta meta">
            {enlace && (
              <a className="enlace" href={enlace} target="_blank" rel="noreferrer">
                {f.doi ? `DOI ${f.doi}` : f.pmid ? `PMID ${f.pmid}` : f.nct}
              </a>
            )}
            {f.anio && <span>{f.anio}</span>}
            {nodo.tambienEn.length > 0 && <span>También la trajo la consulta {nodo.tambienEn.join(', ')}</span>}
            {f.retraccionDetalle && <span>Crossref: {f.retraccionDetalle}</span>}
            {!f.extraida && <span>Todavía sin extraer</span>}
          </div>
          <ul className="arbol-afirmaciones" role="group">
            {nodo.afirmaciones.length === 0 && <li className="meta arbol-vacio">Sin afirmaciones que pasen el filtro.</li>}
            {nodo.afirmaciones.map((a) => {
              const v = VEREDICTO[a.veredicto];
              return (
                <li key={a.id} className={`arbol-afirmacion tono-borde-${v.tono}`}>
                  <span className="arbol-icono" aria-hidden="true">
                    {v.tono === 'ok' ? '✓' : v.tono === 'mal' ? '✗' : '⚠'}
                  </span>
                  <div className="arbol-texto">
                    <span>{a.texto}</span>
                    <span className="arbol-detalle">
                      <Chip tono={v.tono}>{v.etiqueta}</Chip> <Chip tono="borde">{tipoAfirmacion(a.tipo).etiqueta}</Chip> <span className="meta">{a.cita}</span>
                      {a.entidadDistinta && <Chip tono="mal">otra entidad</Chip>}
                    </span>
                    {a.motivo && a.veredicto !== 'sostenida' && <span className="arbol-motivo meta">{a.motivo}</span>}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </li>
  );
}
