// El explorador del modelo de mundo: que se sabe (con procedencia hasta la
// pagina y las citas que apoyan, mencionan o contrastan cada hecho), que esta
// abierto y que se descarto (con su motivo). Con la cobertura de la busqueda
// por tema, la vista "que cambio", preguntar al modelo de mundo (responde
// solo con lo que hay dentro) y recomprobar retractaciones.

import { useMemo, useState } from 'react';
import { acciones } from '../datos/almacen';
import { preguntarAlModeloDeMundo, type CitaComprobable } from '../datos/acciones';
import type { EstadoRosa, Fuente, HechoMundo, Investigacion } from '../datos/tipos';
import { AvisoMuestra, Chip, Momento, Seccion } from '../componentes/piezas';
import { IconChevronDown } from '../componentes/icons';
import { Entidades, PreguntarALasBases, RelacionesCausales } from '../componentes/Rosa2018';
import { ElementoAnimado, ListaAnimada } from '../componentes/Animado';
import { COBERTURA_MINIMA, faltanParaCobertura } from '../lib/cobertura';
import { CLASIFICACION_CITA, ESTADO_HECHO, TIPO_HECHO } from '../lib/etiquetas';
import { formatearPorcentaje } from '../lib/formato';

function CitasDelHecho({ h }: { h: HechoMundo }) {
  const [abierto, setAbierto] = useState(false);
  if (h.citas.length === 0) return null;
  const n = { apoya: 0, menciona: 0, contrasta: 0 };
  for (const c of h.citas) n[c.clasificacion]++;
  return (
    <div>
      <button type="button" className="citas-badge" aria-expanded={abierto} onClick={() => setAbierto((v) => !v)} title="Otras fuentes sobre este hecho: apoyan, mencionan, contrastan">
        <span className="tono-ok">{n.apoya} apoyan</span>
        <span className="meta">{n.menciona} mencionan</span>
        <span className={n.contrasta > 0 ? 'tono-mal' : 'meta'}>{n.contrasta} contrastan</span>
        <IconChevronDown size={11} style={{ transform: abierto ? 'rotate(180deg)' : 'none' }} />
      </button>
      {abierto && (
        <ul className="citas-lista">
          {h.citas.map((c, i) => (
            <li key={i} className={`cita-${c.clasificacion}`}>
              <div className="acciones" style={{ gap: 6 }}>
                <Chip tono={c.clasificacion === 'apoya' ? 'ok' : c.clasificacion === 'contrasta' ? 'mal' : undefined}>{CLASIFICACION_CITA[c.clasificacion]}</Chip>
                <strong style={{ fontSize: 12.5 }}>{c.referencia}</strong>
                <span className="meta">{c.seccion}</span>
              </div>
              <p style={{ fontSize: 13, marginTop: 4 }}>{c.fragmento}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TarjetaHecho({ h, ahora, fuentes }: { h: HechoMundo; ahora: number; fuentes?: Map<string, Fuente> }) {
  return (
    <div className="hecho">
      <div className="hecho-cabecera">
        <Chip tono={h.tipo === 'hipotesis' ? 'acento' : undefined}>{TIPO_HECHO[h.tipo]}</Chip>
        {h.tema !== TIPO_HECHO[h.tipo] && <Chip tono="borde">{h.tema}</Chip>}
        <Chip tono={h.origen === 'fuente' ? undefined : 'aviso'} title={h.origen === 'fuente' ? 'Lo dice la fuente citada' : 'Lo infiere Rosa; no es una cita'}>
          {h.origen === 'fuente' ? 'Dice la fuente' : 'Inferencia de Rosa'}
        </Chip>
      </div>
      <p>{h.enunciado}</p>
      <Entidades entidades={h.entidades} maximo={6} />
      {h.procedencia.length > 0 && (
        <div className="hecho-procedencia">
          {h.procedencia.map((p, i) => {
            const f = fuentes?.get(p.fuenteId);
            const texto = `[${p.referencia}${p.pagina !== null ? `, pag. ${p.pagina}` : ''}]`;
            const href = f?.pmid ? `https://pubmed.ncbi.nlm.nih.gov/${f.pmid}/` : f?.doi ? `https://doi.org/${f.doi}` : null;
            return href ? (
              <a key={i} className="enlace" href={href} target="_blank" rel="noreferrer" title={`${f?.titulo ?? ''}${f?.pmid ? ` · PMID ${f.pmid}` : ''}${f?.doi ? ` · doi:${f.doi}` : ''}. Se abre en PubMed o en el DOI: comprobable fuera de Rosa.`}>
                <code>{texto}</code>
              </a>
            ) : (
              <code key={i} title="Fuente sin identificador registrado">
                {texto}
              </code>
            );
          })}
        </div>
      )}
      <CitasDelHecho h={h} />
      {h.motivoDescarte && <p className="hecho-motivo">{h.motivoDescarte}</p>}
      <span className="meta">
        <Momento t={h.actualizadoEn} ahora={ahora} />
        {h.historial.length > 1 && ` · ${h.historial.length} movimientos`}
      </span>
    </div>
  );
}

export function ModeloDeMundo({ inv, estado, ahora }: { inv: Investigacion; estado: EstadoRosa; ahora: number }) {
  const [busqueda, setBusqueda] = useState('');
  const [tema, setTema] = useState<string>('todos');
  const [vista, setVista] = useState<'columnas' | 'cambios'>('columnas');
  const [pregunta, setPregunta] = useState('');
  const [respuesta, setRespuesta] = useState<{ respuesta: string; nodos: HechoMundo[]; citas: CitaComprobable[] } | null>(null);
  // Las fuentes con su PMID y DOI, por id, para que cada cita se pueda comprobar fuera de Rosa.
  const fuentesPorId = useMemo(() => {
    const m = new Map<string, Fuente>();
    for (const h of estado.hipotesis) if (h.investigacionId === inv.id) for (const f of h.procedencia.fuentes) if (!m.has(f.id)) m.set(f.id, f);
    return m;
  }, [estado.hipotesis, inv.id]);
  const propios = useMemo(() => estado.hechos.filter((h) => h.investigacionId === inv.id), [estado.hechos, inv.id]);
  const temas = useMemo(() => [...new Set(propios.map((h) => h.tema))].sort(), [propios]);
  const q = busqueda.trim().toLowerCase();
  // Se busca tambien por identificador canonico y por alias (GFAP, P14136, HGNC:4235
  // encuentran el mismo hecho): el modelo de mundo como grafo consultable.
  const filtrados = propios.filter((h) => (tema === 'todos' || h.tema === tema) && (q === '' || h.enunciado.toLowerCase().includes(q) || h.procedencia.some((p) => p.referencia.toLowerCase().includes(q)) || (h.entidades ?? []).some((x) => x.id.toLowerCase() === q || x.etiqueta.toLowerCase().includes(q) || x.alias.some((a) => a.toLowerCase() === q) || (x.uniprot ?? '').toLowerCase() === q)));
  const columnas: HechoMundo['estado'][] = ['sabido', 'abierto', 'descartado'];
  const orden = (a: HechoMundo, b: HechoMundo) => a.prioridad - b.prioridad || b.actualizadoEn - a.actualizadoEn;
  const corrida = estado.corridas.filter((c) => c.investigacionId === inv.id).sort((a, b) => b.numero - a.numero)[0];
  const coberturas = corrida?.coberturas ?? [];
  const desde = estado.ultimaVisita;
  const movimientos = propios
    .flatMap((h) => h.historial.map((m) => ({ h, m })))
    .filter((x) => desde === null || x.m.fecha > desde)
    .sort((a, b) => b.m.fecha - a.m.fecha);
  const contrastados = propios.filter((h) => h.citas.some((c) => c.clasificacion === 'contrasta')).length;

  return (
    <div className="contenido contenido-ancho">
      <AvisoMuestra conexion={estado.conexion} />
      <div className="pantalla-cabecera" style={{ marginTop: 16 }}>
        <div>
          <h2>Modelo de mundo</h2>
          <p>La memoria estructurada de la investigacion. Cada hecho lleva su procedencia hasta la pagina y las fuentes que lo apoyan o contradicen; cada descarte, su motivo.</p>
        </div>
        <div className="filtros">
          <div className="segmentos" role="group" aria-label="Vista">
            <button type="button" aria-pressed={vista === 'columnas'} onClick={() => setVista('columnas')}>
              Estado
            </button>
            <button type="button" aria-pressed={vista === 'cambios'} onClick={() => setVista('cambios')}>
              Que cambio {movimientos.length > 0 && <span className="nav-cuenta">{movimientos.length}</span>}
            </button>
          </div>
          <input className="entrada" value={busqueda} placeholder="Buscar en el modelo de mundo" onChange={(e) => setBusqueda(e.target.value)} aria-label="Buscar" />
          <select className="entrada" value={tema} onChange={(e) => setTema(e.target.value)} aria-label="Tema" style={{ width: 'auto' }}>
            <option value="todos">Todos los temas</option>
            {temas.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="acciones" style={{ marginBottom: 16 }}>
        {contrastados > 0 && (
          <Chip tono="aviso">
            {contrastados} {contrastados === 1 ? 'hecho con citas que lo contrastan' : 'hechos con citas que los contrastan'}
          </Chip>
        )}
        <button type="button" className="btn btn-s" onClick={() => acciones.recomprobarRetracciones(inv.id)}>
          Recomprobar retractaciones ahora
        </button>
        <span className="meta">Contra Crossref y Retraction Watch. Se hace solo cada 24 h; esto lo adelanta.</span>
      </div>

      {coberturas.length > 0 && (
        <Seccion detalle titulo="Cobertura de la busqueda por tema" nota={`Cuanto de lo relevante se estima encontrado (curva de descubrimiento). Por debajo del ${Math.round(COBERTURA_MINIMA * 100)} % una "ausencia refutada" se degrada a "sin verificar".`}>
          <div className="coberturas">
            {coberturas.map((c) => {
              const faltan = faltanParaCobertura(c, 0.9);
              const baja = c.fraccion < COBERTURA_MINIMA;
              return (
                <div key={c.tema} className="cobertura">
                  <div className="acciones" style={{ justifyContent: 'space-between' }}>
                    <strong style={{ fontSize: 13 }}>{c.tema}</strong>
                    <span className={baja ? 'tono-aviso' : 'tono-ok'} style={{ fontSize: 12.5 }}>
                      {formatearPorcentaje(c.fraccion)}
                    </span>
                  </div>
                  <div className="presupuesto-barra">
                    <i style={{ width: `${c.fraccion * 100}%`, background: baja ? 'var(--amber)' : 'var(--green)' }} />
                  </div>
                  <span className="meta">
                    {c.leidos} leidos
                    {Number.isFinite(faltan) && faltan > 0 && ` · unos ${faltan} más para el 90 %`}
                  </span>
                  {baja && (
                    <button type="button" className="btn btn-s" onClick={() => corrida && acciones.dirigirCorrida(corrida.id, `Extender la busqueda del tema "${c.tema}" hasta el 90 % de cobertura (unos ${Number.isFinite(faltan) ? faltan : 'muchos'} artículos más)`)} disabled={!corrida}>
                      Extender busqueda
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </Seccion>
      )}

      <RelacionesCausales estado={estado} inv={inv} />

      <PreguntarALasBases inv={inv} ahora={ahora} />

      <Seccion titulo="Preguntar al modelo de mundo" nota="Responde solo con lo que hay dentro, citando los nodos. Si no hay nada, lo dice y no lo inventa.">
        <div className="dirigir">
          <input
            className="entrada"
            value={pregunta}
            placeholder="Que se sabe del cociente p-tau217/Abeta42"
            onChange={(e) => setPregunta(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') setRespuesta(preguntarAlModeloDeMundo(estado.hechos, inv.id, pregunta, fuentesPorId));
            }}
            aria-label="Pregunta al modelo de mundo"
          />
          <button type="button" className="btn" disabled={pregunta.trim() === ''} onClick={() => setRespuesta(preguntarAlModeloDeMundo(estado.hechos, inv.id, pregunta, fuentesPorId))}>
            Preguntar
          </button>
        </div>
        {respuesta && (
          <div className="mensaje" style={{ whiteSpace: 'pre-wrap' }}>
            <header>
              <span>Modelo de mundo</span>
              <span>{respuesta.nodos.length} {respuesta.nodos.length === 1 ? 'nodo' : 'nodos'}</span>
            </header>
            {respuesta.respuesta}
            {respuesta.citas.length > 0 && (
              <ul className="citas-comprobables" aria-label="Fuentes citadas">
                {respuesta.citas.map((c) => (
                  <li key={c.fuenteId}>
                    <strong>{c.referencia}</strong>
                    {c.titulo && <span className="meta"> {c.titulo.length > 110 ? `${c.titulo.slice(0, 108)}...` : c.titulo}</span>}{' '}
                    {c.pmid && (
                      <a className="enlace" href={`https://pubmed.ncbi.nlm.nih.gov/${c.pmid}/`} target="_blank" rel="noreferrer">
                        PubMed {c.pmid}
                      </a>
                    )}{' '}
                    {c.doi && (
                      <a className="enlace" href={`https://doi.org/${c.doi}`} target="_blank" rel="noreferrer">
                        doi:{c.doi}
                      </a>
                    )}
                    {!c.pmid && !c.doi && <span className="meta">sin identificador registrado</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Seccion>

      {vista === 'cambios' ? (
        <Seccion titulo="Que cambio desde tu última visita" nota="Movimientos entre sabido, abierto y descartado, con quien los decidió y por que.">
          {movimientos.length === 0 ? (
            <p className="meta">Nada se movio desde tu última visita.</p>
          ) : (
            <ul className="lista-limpia">
              {movimientos.map((x, i) => (
                <li key={`${x.h.id}-${i}`} className="movimiento">
                  <div>
                    <div className="acciones" style={{ gap: 6 }}>
                      {x.m.de !== null && <Chip>{ESTADO_HECHO[x.m.de]}</Chip>}
                      <span className="meta">{x.m.de !== null ? 'a' : 'nuevo en'}</span>
                      <Chip tono={x.m.a === 'sabido' ? 'ok' : x.m.a === 'descartado' ? 'mal' : 'acento'}>{ESTADO_HECHO[x.m.a]}</Chip>
                      <Chip tono={x.m.quien === 'Rosa' ? undefined : 'borde'}>{x.m.quien}</Chip>
                    </div>
                    <p style={{ fontSize: 13.5, marginTop: 4 }}>{x.h.enunciado}</p>
                    <p className="meta">{x.m.motivo}</p>
                  </div>
                  <span className="meta">
                    <Momento t={x.m.fecha} ahora={ahora} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Seccion>
      ) : (
        <div className="mundo-columnas" style={{ marginTop: 28 }}>
          {columnas.map((col) => {
            const lista = filtrados.filter((h) => h.estado === col).sort(orden);
            return (
              <section key={col} className="mundo-columna" aria-label={ESTADO_HECHO[col]}>
                <h3>
                  {ESTADO_HECHO[col]} <span className="nav-cuenta">{lista.length}</span>
                </h3>
                {lista.length === 0 ? (
                  <p className="meta">Nada aqui{q !== '' || tema !== 'todos' ? ' con este filtro' : ''}.</p>
                ) : (
                  <ListaAnimada className="mundo-columna" como="ul">
                    {lista.map((h) => (
                      <ElementoAnimado key={h.id} como="li">
                        <TarjetaHecho h={h} ahora={ahora} fuentes={fuentesPorId} />
                      </ElementoAnimado>
                    ))}
                  </ListaAnimada>
                )}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
