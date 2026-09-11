// El explorador del modelo de mundo: que se sabe (con procedencia hasta la
// pagina y las citas que apoyan, mencionan o contrastan cada hecho), que esta
// abierto y que se descarto (con su motivo). Con la cobertura de la busqueda
// por tema, la vista "que cambio", preguntar al modelo de mundo (responde
// solo con lo que hay dentro) y recomprobar retractaciones.

import { useMemo, useState } from 'react';
import { acciones } from '../datos/almacen';
import { preguntarAlModeloDeMundo } from '../datos/acciones';
import type { EstadoRosa, HechoMundo, Investigacion } from '../datos/tipos';
import { AvisoMuestra, Chip, Momento, Seccion } from '../componentes/piezas';
import { IconChevronDown } from '../componentes/icons';
import { PreguntarALasBases, RelacionesCausales } from '../componentes/Rosa2018';
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

function TarjetaHecho({ h, ahora }: { h: HechoMundo; ahora: number }) {
  return (
    <li className="hecho">
      <div className="hecho-cabecera">
        <Chip tono={h.tipo === 'hipotesis' ? 'acento' : undefined}>{TIPO_HECHO[h.tipo]}</Chip>
        {h.tema !== TIPO_HECHO[h.tipo] && <Chip tono="borde">{h.tema}</Chip>}
        <Chip tono={h.origen === 'fuente' ? undefined : 'aviso'} title={h.origen === 'fuente' ? 'Lo dice la fuente citada' : 'Lo infiere Rosa; no es una cita'}>
          {h.origen === 'fuente' ? 'Dice la fuente' : 'Inferencia de Rosa'}
        </Chip>
      </div>
      <p>{h.enunciado}</p>
      {h.procedencia.length > 0 && (
        <div className="hecho-procedencia">
          {h.procedencia.map((p, i) => (
            <code key={i}>
              [{p.referencia}
              {p.pagina !== null ? `, pag. ${p.pagina}` : ''}]
            </code>
          ))}
        </div>
      )}
      <CitasDelHecho h={h} />
      {h.motivoDescarte && <p className="hecho-motivo">{h.motivoDescarte}</p>}
      <span className="meta">
        <Momento t={h.actualizadoEn} ahora={ahora} />
        {h.historial.length > 1 && ` · ${h.historial.length} movimientos`}
      </span>
    </li>
  );
}

export function ModeloDeMundo({ inv, estado, ahora }: { inv: Investigacion; estado: EstadoRosa; ahora: number }) {
  const [busqueda, setBusqueda] = useState('');
  const [tema, setTema] = useState<string>('todos');
  const [vista, setVista] = useState<'columnas' | 'cambios'>('columnas');
  const [pregunta, setPregunta] = useState('');
  const [respuesta, setRespuesta] = useState<{ respuesta: string; nodos: HechoMundo[] } | null>(null);
  const propios = useMemo(() => estado.hechos.filter((h) => h.investigacionId === inv.id), [estado.hechos, inv.id]);
  const temas = useMemo(() => [...new Set(propios.map((h) => h.tema))].sort(), [propios]);
  const q = busqueda.trim().toLowerCase();
  const filtrados = propios.filter((h) => (tema === 'todos' || h.tema === tema) && (q === '' || h.enunciado.toLowerCase().includes(q) || h.procedencia.some((p) => p.referencia.toLowerCase().includes(q))));
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
        <Seccion titulo="Cobertura de la busqueda por tema" nota={`Cuanto de lo relevante se estima encontrado (curva de descubrimiento). Por debajo del ${Math.round(COBERTURA_MINIMA * 100)} % una "ausencia refutada" se degrada a "sin verificar".`}>
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
                    {Number.isFinite(faltan) && faltan > 0 && ` · unos ${faltan} mas para el 90 %`}
                  </span>
                  {baja && (
                    <button type="button" className="btn btn-s" onClick={() => corrida && acciones.dirigirCorrida(corrida.id, `Extender la busqueda del tema "${c.tema}" hasta el 90 % de cobertura (unos ${Number.isFinite(faltan) ? faltan : 'muchos'} articulos mas)`)} disabled={!corrida}>
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
              if (e.key === 'Enter') setRespuesta(preguntarAlModeloDeMundo(estado.hechos, inv.id, pregunta));
            }}
            aria-label="Pregunta al modelo de mundo"
          />
          <button type="button" className="btn" disabled={pregunta.trim() === ''} onClick={() => setRespuesta(preguntarAlModeloDeMundo(estado.hechos, inv.id, pregunta))}>
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
          </div>
        )}
      </Seccion>

      {vista === 'cambios' ? (
        <Seccion titulo="Que cambio desde tu ultima visita" nota="Movimientos entre sabido, abierto y descartado, con quien los decidio y por que.">
          {movimientos.length === 0 ? (
            <p className="meta">Nada se movio desde tu ultima visita.</p>
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
                  <ul className="mundo-columna">
                    {lista.map((h) => (
                      <TarjetaHecho key={h.id} h={h} ahora={ahora} />
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
