// El ranking: hipotesis ordenadas por Elo (torneo, como Co-Scientist), con
// su historial en una grafica pequena, el numero de partidos (un Elo con
// pocos partidos es poco fiable), sus rivales, el coste y el origen (humana o
// de ROSA2018). Vista alternativa por cluster para ver diversidad: el mejor de
// cada cluster, como hace el agente de proximidad de Co-Scientist.

import { useMemo, useState } from 'react';
import { Contador, ElementoAnimado, ListaAnimada } from '../componentes/Animado';
import type { EstadoRosa, Hipotesis, Investigacion } from '../datos/tipos';
import { AvisoMuestra, Chip } from '../componentes/piezas';
import { Candidatas } from '../componentes/Rosa2018';
import { FranjaRanking } from '../componentes/FranjaRanking';
import { calibracion } from '../lib/calidad';
import { DECISION_KILLER, ESTADO_HIPOTESIS, killerPendienteDe } from '../lib/etiquetas';
import { formatearPorcentaje } from '../lib/formato';
import { ranking, variacionElo } from '../lib/hipotesis';
import { bloqueosDe, candidatos } from '../lib/priorizacion';
import { rutaDe } from '../lib/ruta';

function GraficaElo({ puntos }: { puntos: Hipotesis['historialElo'] }) {
  if (puntos.length < 2) return <svg className="grafica-elo" aria-hidden="true" />;
  const W = 120;
  const H = 34;
  const xs = puntos.map((p) => p.iteracion);
  const ys = puntos.map((p) => p.elo);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys) - 10;
  const maxY = Math.max(...ys) + 10;
  const x = (v: number) => (maxX === minX ? W / 2 : ((v - minX) / (maxX - minX)) * (W - 6) + 3);
  const y = (v: number) => H - 3 - ((v - minY) / (maxY - minY)) * (H - 6);
  const d = puntos.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.iteracion).toFixed(1)},${y(p.elo).toFixed(1)}`).join(' ');
  const ultimo = puntos[puntos.length - 1]!;
  return (
    <svg className="grafica-elo" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Elo de ${puntos[0]!.elo} a ${ultimo.elo}`}>
      <path d={d} />
      <circle cx={x(ultimo.iteracion)} cy={y(ultimo.elo)} r="2.2" />
    </svg>
  );
}

function Fila({ h, i, inv, estado }: { h: Hipotesis; i: number; inv: Investigacion; estado: EstadoRosa }) {
  const d = variacionElo(h);
  return (
    <a className="ranking-fila" href={rutaDe(inv.id, 'hipotesis', h.id)}>
      <span className="ranking-pos">{i + 1}</span>
      <div>
        <h3>{h.titulo}</h3>
        <div className="hip-meta">
          <Chip>{ESTADO_HIPOTESIS[h.estado]}</Chip>
          {h.origen === 'humana' && <Chip tono="acento">Humana</Chip>}
          <Chip tono="borde">{h.cluster}</Chip>
          {killerPendienteDe(h) && (
            <Chip tono="aviso" title="La última pasada del Killer no fue un juicio: el modelo no respondió o su respuesta no se pudo leer. La decisión que se ve es la anterior; ROSA2018 repite la revisión en el siguiente paso o cuando la pidas.">
              {killerPendienteDe(h)}
            </Chip>
          )}
          {(h.conflictoCon?.length ?? 0) > 0 && (
            <Chip tono="aviso" title={`No puede ser cierta a la vez que: ${h.conflictoCon!.map((id) => estado.hipotesis.find((x) => x.id === id)?.titulo ?? id).join('; ')}. ROSA2018 lo marca; decide la persona.`}>
              Se contradice con {h.conflictoCon!.length === 1 ? 'otra' : h.conflictoCon!.length}
            </Chip>
          )}
          <span>
            {h.rivales.length} {h.rivales.length === 1 ? 'rival' : 'rivales'}
          </span>
          <span>{(h.coste.literatura + h.coste.analisis).toFixed(1).replace('.', ',')} $ gastados</span>
        </div>
        <FranjaRanking estado={estado} h={h} />
      </div>
      <GraficaElo puntos={h.historialElo} />
      <div className="hip-elo">
        <strong>
          <Contador valor={h.elo} />
        </strong>
        <span className={d > 0 ? 'subida' : d < 0 ? 'bajada' : 'meta'}>{d > 0 ? `+${d}` : d}</span>
        {h.bt && (
          <span className="meta" title="Fuerza de Bradley-Terry sobre los partidos, con intervalo del 95 % por bootstrap. Es lo que ordena a las candidatas.">
            BT {h.bt.fuerza} ({h.bt.ic95[0]} a {h.bt.ic95[1]})
          </span>
        )}
      </div>
    </a>
  );
}

export function Ranking({ inv, estado }: { inv: Investigacion; estado: EstadoRosa }) {
  const propias = useMemo(() => estado.hipotesis.filter((h) => h.investigacionId === inv.id), [estado.hipotesis, inv.id]);
  const lista = ranking(propias);
  const [vista, setVista] = useState<'lista' | 'clusters'>('lista');
  const [soloMejor, setSoloMejor] = useState(false);
  const cal = calibracion(propias);
  const clusters = useMemo(() => {
    const m = new Map<string, Hipotesis[]>();
    for (const h of lista) m.set(h.cluster, [...(m.get(h.cluster) ?? []), h]);
    return [...m.entries()].sort((a, b) => (b[1][0]?.elo ?? 0) - (a[1][0]?.elo ?? 0));
  }, [lista]);
  const cands = useMemo(() => candidatos(estado, inv.id), [estado, inv.id]);
  const noCands = useMemo(
    () =>
      propias
        .filter((h) => h.estado !== 'descartada' && !cands.some((c) => c.id === h.id))
        .map((h) => {
          const b = bloqueosDe(estado, h);
          const pendiente = killerPendienteDe(h);
          const motivo = b.length > 0 ? '' : pendiente ? `${pendiente}: la decisión que consta no es un juicio nuevo` : h.decisionKiller !== 'avanzar' ? (h.decisionKiller ? `El Killer decidió: ${(DECISION_KILLER[h.decisionKiller]?.etiqueta ?? String(h.decisionKiller)).toLowerCase()}` : 'El Killer todavía no la juzgó') : 'Sin bloqueos, pero otras puntúan más o repiten su cluster';
          return { h, bloqueos: b, motivo };
        }),
    [propias, cands, estado],
  );

  return (
    <div className="contenido">
      <AvisoMuestra conexion={estado.conexion} />
      <div className="pantalla-cabecera" style={{ marginTop: 16 }}>
        <div>
          <h2>Ranking de hipótesis</h2>
          <p>
            Puntuación Elo por torneo entre rivales, revisada en cada iteración. Elo inicial 1500; funciona como el ranking de ajedrez: mayor Elo, más probable que sea correcta y útil. Las descartadas van al final aunque puntuaran alto.
          </p>
        </div>
        <div className="acciones">
          <div className="segmentos" role="group" aria-label="Vista">
            <button type="button" aria-pressed={vista === 'lista'} onClick={() => setVista('lista')}>
              Lista
            </button>
            <button type="button" aria-pressed={vista === 'clusters'} onClick={() => setVista('clusters')}>
              Por cluster
            </button>
          </div>
        </div>
      </div>

      <Candidatas inv={inv} estado={estado} candidatas={cands} noCandidatas={noCands} />

      <div className="acciones" style={{ marginBottom: 14 }}>
        <Chip tono={cal.acuerdo === null ? undefined : cal.acuerdo >= 0.7 ? 'ok' : 'aviso'} title="Cuántas veces la recomendación del revisor coincidió con lo que decidió una persona">
          Acuerdo revisor y personas: {cal.acuerdo === null ? 'sin decisiones todavía' : formatearPorcentaje(cal.acuerdo)}
        </Chip>
        <span className="meta">Las decisiones humanas de aceptar y descartar son la señal que calibra al juez del torneo.</span>
      </div>

      {vista === 'lista' ? (
        <ListaAnimada className="cola" como="div">
          {lista.map((h, i) => (
            <ElementoAnimado key={h.id}>
              <Fila h={h} i={i} inv={inv} estado={estado} />
            </ElementoAnimado>
          ))}
        </ListaAnimada>
      ) : (
        <div className="seccion">
          <label className="interruptor">
            <input type="checkbox" checked={soloMejor} onChange={(e) => setSoloMejor(e.target.checked)} />
            Mostrar solo la mejor de cada cluster (para ver la diversidad, no la repetición)
          </label>
          {clusters.map(([nombre, hs]) => (
            <div key={nombre} className="cluster">
              <div className="acciones" style={{ justifyContent: 'space-between' }}>
                <h3 style={{ fontSize: 14, fontWeight: 600 }}>{nombre}</h3>
                <span className="meta">
                  {hs.length} {hs.length === 1 ? 'hipótesis' : 'hipótesis'} · mejor Elo {hs[0]?.elo}
                </span>
              </div>
              <div className="cola">
                {(soloMejor ? hs.slice(0, 1) : hs).map((h) => (
                  <Fila key={h.id} h={h} i={lista.indexOf(h)} inv={inv} estado={estado} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
