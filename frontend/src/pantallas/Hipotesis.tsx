// La cola de revision de hipotesis y el detalle de una. Aceptar, descartar,
// refinar, "no puedo juzgar", con la procedencia en un cajon lateral; los
// hallazgos del revisor como tarjetas; comentarios anclados; la revision
// escrita de la persona que entra al torneo; la relevancia votada aparte de
// la significancia; los supuestos; los tipos de revision; los partidos del
// torneo; replicar; el experimento propuesto; y la hipotesis humana.
// Regla: una hipotesis no entra al modelo de mundo como aceptada sin pasar
// por aqui, y no se puede aceptar con afirmaciones bloqueantes o hallazgos
// abiertos (motivoNoAceptable).

import { useEffect, useMemo, useRef, useState } from 'react';
import { Contador, ElementoAnimado, ListaAnimada } from '../componentes/Animado';
import type { TargetAndTransition } from 'motion/react';
import { salidaPorDecision } from '../lib/movimiento';
import { acciones } from '../datos/almacen';
import type { EstadoRosa, Hipotesis as Hip, Investigacion, Supuesto } from '../datos/tipos';
import { BandejaComentarios, NuevoComentario, useSeleccionComentable } from '../componentes/Comentarios';
import { Procedencia, type PestanaProcedencia } from '../componentes/Procedencia';
import { Revisor } from '../componentes/Revisor';
import { Verificacion } from '../componentes/Verificacion';
import { ConclusionDeRosa, HipotesisEnLlano } from '../componentes/EnLlano';
import { AvisoMuestra, Chip, Confirmar, Momento, Seccion, Vacio, descargar } from '../componentes/piezas';
import { Bloqueos, ConsultasABases, ContextoDeBases, DecisionesKiller, Dimensiones, EjecucionesInSilico, GrafoCausalDeHipotesis, ProtocoloYEnmiendas, TarjetaDeHipotesis } from '../componentes/Rosa2018';
import { dependeDeRetractada, resumenEvidencia, tramosFuertes } from '../lib/calidad';
import { ESTADO_HIPOTESIS, ESTADO_SUPUESTO, TIPO_REVISION, CERTEZA_EVIDENCIA, DECISION_KILLER, RESULTADO_LABORATORIO } from '../lib/etiquetas';
import { expediente } from '../lib/exportar';
import { formatearDuracion } from '../lib/formato';
import { motivoNoAceptable, ordenarCola, resumirVerificacion, variacionElo } from '../lib/hipotesis';
import { bloqueosDe } from '../lib/priorizacion';
import { rutaDe } from '../lib/ruta';

const TONO_ESTADO: Record<Hip['estado'], 'ok' | 'aviso' | 'mal' | 'acento' | undefined> = {
  propuesta: 'acento',
  en_revision: 'aviso',
  aceptada: 'ok',
  descartada: 'mal',
  refinar: 'aviso',
  aclarando: 'aviso',
};

/** Texto con los tramos que afirman de mas subrayados en ambar. */
function TextoConFuertes({ texto, campo, como = 'p' }: { texto: string; campo: 'enunciado' | 'mecanismo'; como?: 'p' | 'h2' }) {
  const Etiqueta = como;
  const tramos = tramosFuertes(texto);
  if (tramos.length === 0)
    return (
      <Etiqueta className="texto-comentable" data-campo={campo}>
        {texto}
      </Etiqueta>
    );
  const partes: React.ReactNode[] = [];
  let pos = 0;
  tramos.forEach((t, i) => {
    partes.push(texto.slice(pos, t.inicio));
    partes.push(
      <mark key={i} className="fuerte" title="Afirma con más seguridad de la que suele dar la evidencia. Considera un verbo más prudente.">
        {texto.slice(t.inicio, t.fin)}
      </mark>,
    );
    pos = t.fin;
  });
  partes.push(texto.slice(pos));
  return (
    <Etiqueta className="texto-comentable" data-campo={campo}>
      {partes}
    </Etiqueta>
  );
}

function FilaCola({ h, ahora, href, horasEspera, estado }: { h: Hip; ahora: number; href: string; horasEspera: number; estado: EstadoRosa }) {
  const r = resumirVerificacion(h.afirmaciones);
  const bloqueos = bloqueosDe(estado, h);
  const abiertos = h.hallazgos.filter((x) => x.estado === 'abierto').length;
  const d = variacionElo(h);
  const pendiente = h.estado === 'propuesta' || h.estado === 'en_revision' || h.estado === 'refinar';
  const espera = ahora - h.creadaEn;
  const tarde = pendiente && espera > horasEspera * 3_600_000;
  const retractadas = dependeDeRetractada(h);
  return (
    <a className={`tarjeta tarjeta-interactiva hip-fila ${tarde ? 'hip-tarde' : ''}`} href={href}>
      <div>
        <h3>{h.titulo}</h3>
        <div className="hip-meta">
          <Chip tono={TONO_ESTADO[h.estado]}>{ESTADO_HIPOTESIS[h.estado]}</Chip>
          {h.origen === 'humana' && <Chip tono="acento">Humana</Chip>}
          <span className={`tono-${r.tono === 'vacio' ? 'aviso' : r.tono}`}>{r.frase}</span>
          {h.conclusion && (
            <Chip tono={CERTEZA_EVIDENCIA[h.conclusion.certeza].tono} title={CERTEZA_EVIDENCIA[h.conclusion.certeza].nota}>
              {CERTEZA_EVIDENCIA[h.conclusion.certeza].etiqueta}
            </Chip>
          )}
          {h.decisionKiller && (
            <Chip tono={DECISION_KILLER[h.decisionKiller].tono} title={DECISION_KILLER[h.decisionKiller].nota}>
              Killer: {DECISION_KILLER[h.decisionKiller].etiqueta}
            </Chip>
          )}
          {(h.version ?? 1) > 1 && <Chip tono="borde">v{h.version}</Chip>}
          {h.candidata && bloqueos.length === 0 && <Chip tono="ok">Candidata</Chip>}
          {bloqueos.length > 0 && <span className="tono-mal">{bloqueos.length} {bloqueos.length === 1 ? 'bloqueo' : 'bloqueos'}</span>}
          {abiertos > 0 && <span className="tono-mal">{abiertos} {abiertos === 1 ? 'hallazgo abierto' : 'hallazgos abiertos'}</span>}
          {retractadas.length > 0 && <span className="tono-mal">depende de una fuente retractada</span>}
          <span>Iteracion {h.iteracion}</span>
          {pendiente && (
            <span className={tarde ? 'tono-mal' : ''} title={tarde ? `Supera las ${horasEspera} h de la política de esperas` : ''}>
              esperando {formatearDuracion(espera)}
            </span>
          )}
          <Momento t={h.creadaEn} ahora={ahora} />
        </div>
      </div>
      <div className="hip-elo">
        <strong>
          <Contador valor={h.elo} />
        </strong>
        <span className={d > 0 ? 'subida' : d < 0 ? 'bajada' : 'meta'}>{d > 0 ? `+${d}` : d}</span>
        <span className="meta">{h.partidos.length} {h.partidos.length === 1 ? 'partido' : 'partidos'}</span>
      </div>
    </a>
  );
}

function salidaDe(h: Hip): TargetAndTransition {
  if (h.estado === 'aceptada') return salidaPorDecision.aprobar;
  if (h.estado === 'descartada') return salidaPorDecision.descartar;
  if (h.estado === 'refinar' || h.estado === 'aclarando') return salidaPorDecision.refinar;
  return salidaPorDecision.neutra;
}

function ArbolSupuestos({ supuestos, nivel = 0 }: { supuestos: Supuesto[]; nivel?: number }) {
  return (
    <ul className="supuestos" style={{ paddingLeft: nivel * 18 }}>
      {supuestos.map((s) => {
        const e = ESTADO_SUPUESTO[s.estado];
        return (
          <li key={s.id} className={`supuesto supuesto-${e.tono}`}>
            <div className="acciones" style={{ gap: 8 }}>
              <Chip tono={e.tono === 'neutro' ? 'borde' : e.tono}>{e.etiqueta}</Chip>
              <span style={{ fontSize: 13.5 }}>{s.texto}</span>
            </div>
            {s.evidencia !== '' && <p className="meta">{s.evidencia}</p>}
            {s.hijos.length > 0 && <ArbolSupuestos supuestos={s.hijos} nivel={nivel + 1} />}
          </li>
        );
      })}
    </ul>
  );
}

function FormularioHipotesis({ inv, onCerrar, irA }: { inv: Investigacion; onCerrar: () => void; irA: (hash: string) => void }) {
  const [d, setD] = useState({ titulo: '', enunciado: '', mecanismo: '', biomarcador: '', cohorte: '', diseno: '', cluster: '' });
  const [error, setError] = useState<string | null>(null);
  const campo = (k: keyof typeof d, label: string, filas = 1, marcador = '') => (
    <div className="campo" key={k}>
      <label htmlFor={`hh-${k}`}>{label}</label>
      {filas > 1 ? <textarea id={`hh-${k}`} value={d[k]} rows={filas} placeholder={marcador} onChange={(e) => setD({ ...d, [k]: e.target.value })} /> : <input id={`hh-${k}`} value={d[k]} placeholder={marcador} onChange={(e) => setD({ ...d, [k]: e.target.value })} />}
    </div>
  );
  return (
    <form
      className="tarjeta seccion"
      onSubmit={(e) => {
        e.preventDefault();
        const id = acciones.proponerHipotesis(inv.id, d);
        if (id === null) {
          setError('Faltan el título, el enunciado, o el biomarcador o la cohorte con que se comprobaría. Sin comprobación no entra al torneo.');
          return;
        }
        irA(rutaDe(inv.id, 'hipotesis', id));
      }}
    >
      <div>
        <h3 style={{ fontSize: 15, fontWeight: 600 }}>Proponer una hipótesis</h3>
        <p className="meta">Entra al torneo con el mismo Elo inicial que las de Rosa, marcada como tuya. En Co-Scientist la conjetura del experto acabo superando a las generadas.</p>
      </div>
      {campo('titulo', 'Titulo', 1, 'La función renal sesga los umbrales de p-tau217 en cohortes latinoamericanas')}
      {campo('enunciado', 'Enunciado', 3)}
      {campo('mecanismo', 'Mecanismo propuesto', 2)}
      <div className="rejilla-3">
        {campo('biomarcador', 'Biomarcador', 1)}
        {campo('cohorte', 'Cohorte', 1)}
        {campo('diseno', 'Diseño', 1)}
      </div>
      {campo('cluster', 'Cluster (tema)', 1, 'Biomarcadores sanguineos')}
      {error && (
        <p role="alert" style={{ color: 'var(--red)', fontSize: 13 }}>
          {error}
        </p>
      )}
      <div className="acciones">
        <button type="submit" className="btn btn-primario">
          Meter al torneo
        </button>
        <button type="button" className="btn btn-fantasma" onClick={onCerrar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

function Detalle({ h, estado, ahora, onAbrirProcedencia }: { h: Hip; estado: EstadoRosa; ahora: number; onAbrirProcedencia: (pestana: PestanaProcedencia, celda?: number) => void }) {
  const contenedor = useRef<HTMLDivElement>(null);
  const [ancla, limpiarAncla] = useSeleccionComentable(contenedor);
  const [nota, setNota] = useState('');
  const [aCiegas, setACiegas] = useState(false);
  const [revisionAbierta, setRevisionAbierta] = useState(false);
  const [rev, setRev] = useState({ supuestosCuestionados: '', literaturaQueFalta: '', problemaExperimental: '' });
  const [lab, setLab] = useState('');
  const [ficheroDatos, setFicheroDatos] = useState<File | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [errorSubida, setErrorSubida] = useState<string | null>(null);
  const [analisis, setAnalisis] = useState('');
  const [aplicableA, setAplicableA] = useState('');
  const pendientes = estado.comentarios.filter((c) => c.hipotesisId === h.id && c.estado === 'pendiente');
  const motivo = motivoNoAceptable(h);
  const rivales = h.rivales.map((id) => estado.hipotesis.find((x) => x.id === id)).filter((x): x is Hip => x !== undefined);
  const cerrada = h.estado === 'aceptada' || h.estado === 'descartada';
  const aclarando = h.estado === 'aclarando';
  const corrida = estado.corridas.filter((c) => c.investigacionId === h.investigacionId).sort((a, b) => b.numero - a.numero)[0];
  const cobertura = corrida?.coberturas.find((c) => c.tema.toLowerCase() === h.cluster.toLowerCase() || h.cluster.toLowerCase().includes(c.tema.toLowerCase())) ?? null;
  const retractadas = dependeDeRetractada(h);
  const revisionHumana = revisionAbierta && (rev.supuestosCuestionados || rev.literaturaQueFalta || rev.problemaExperimental) ? rev : null;
  const abiertoEn = useRef(Date.now());
  const segundosRevision = () => Math.round((Date.now() - abiertoEn.current) / 1000);
  const decidir = (accion: 'aceptar' | 'refinar' | 'no_puedo_juzgar' | 'reabrir', n: string) => {
    acciones.revisarHipotesis(h.id, accion, n, aCiegas, revisionHumana, h.version ?? 1, segundosRevision());
    setNota('');
    setRev({ supuestosCuestionados: '', literaturaQueFalta: '', problemaExperimental: '' });
  };

  return (
    <div className="detalle-hip" ref={contenedor}>
      <div>
        <div className="acciones" style={{ marginBottom: 8 }}>
          <Chip tono={TONO_ESTADO[h.estado]}>{ESTADO_HIPOTESIS[h.estado]}</Chip>
          {h.origen === 'humana' && <Chip tono="acento">Propuesta por una persona</Chip>}
          {h.derivadaDe && (
            <a className="chip chip-borde" href={rutaDe(h.investigacionId, 'hipotesis', h.derivadaDe)}>
              Derivada de otra hipotesis
            </a>
          )}
          <span className="meta">Elo {h.elo} · {h.partidos.length} {h.partidos.length === 1 ? 'partido' : 'partidos'}</span>
          <span className="meta">Iteracion {h.iteracion}</span>
          <span className="meta">Version {h.version ?? 1}</span>
          {h.decisionKiller && (
            <Chip tono={DECISION_KILLER[h.decisionKiller].tono} title={DECISION_KILLER[h.decisionKiller].nota}>
              Killer: {DECISION_KILLER[h.decisionKiller].etiqueta}
            </Chip>
          )}
          <Bloqueos bloqueos={bloqueosDe(estado, h)} candidata={h.candidata} />
          <span className="meta">
            Prerregistrada <Momento t={h.prerregistradaEn} ahora={ahora} />
          </span>
          <button type="button" className="enlace" style={{ marginLeft: 'auto', fontSize: 13 }} onClick={() => onAbrirProcedencia('fuentes')}>
            Ver procedencia
          </button>
        </div>
        <TextoConFuertes texto={h.titulo} campo="enunciado" como="h2" />
      </div>

      {retractadas.length > 0 && (
        <div className="aviso-retractada" role="alert">
          Depende de {retractadas.length === 1 ? 'una fuente retractada' : `${retractadas.length} fuentes retractadas`}: {retractadas.map((f) => f.referencia).join(', ')}. No vale como evidencia y la hipotesis baja en el ranking.
        </div>
      )}

      <div className="acciones">
        <span className="meta">
          Ultima revision automatica: {h.ultimaRevisionAutomatica ? <Momento t={h.ultimaRevisionAutomatica} ahora={ahora} /> : 'nunca'}. El silencio del revisor no es aprobacion.
        </span>
        <button type="button" className="btn btn-s" onClick={() => acciones.solicitarRevision(h.id)}>
          Solicitar revision ahora
        </button>
        <label className="interruptor" style={{ marginLeft: 'auto' }}>
          <input type="checkbox" checked={aCiegas} onChange={(e) => setACiegas(e.target.checked)} />
          Revisar a ciegas (ocultar citas y codigo hasta decidir)
        </label>
      </div>

      <p className="meta">Selecciona un tramo del texto para comentarlo. Los comentarios se agrupan y salen juntos a Rosa. Los verbos en ámbar afirman más de lo que la evidencia suele dar.</p>

      {ancla && (
        <NuevoComentario
          ancla={ancla}
          onGuardar={(n) => {
            acciones.anadirComentario(h.id, ancla, n);
            limpiarAncla();
            window.getSelection()?.removeAllRanges();
          }}
          onCancelar={limpiarAncla}
        />
      )}

      <HipotesisEnLlano texto={h.enLlano} />

      <ConclusionDeRosa conclusion={h.conclusion} ahora={ahora} />

      <TarjetaDeHipotesis h={h} />
        <ContextoDeBases h={h} />
        <GrafoCausalDeHipotesis h={h} />
        <ConsultasABases h={h} ahora={ahora} />

      <DecisionesKiller h={h} decisiones={estado.decisiones ?? []} ahora={ahora} conjuntoDorado={estado.conjuntoDorado ?? []} />

      <Seccion titulo="Enunciado">
        <TextoConFuertes texto={h.enunciado} campo="enunciado" />
      </Seccion>

      <Seccion titulo="Mecanismo propuesto">
        <TextoConFuertes texto={h.mecanismo} campo="mecanismo" />
      </Seccion>

      <Seccion titulo="Cómo se comprobaría" nota="Siempre con biomarcador, cohorte y diseño: es lo que el investigador clínico principal necesita para juzgarla.">
        <dl className="comprobacion texto-comentable" data-campo="comprobacion">
          <dt>Biomarcador</dt>
          <dd>{h.comprobacion.biomarcador}</dd>
          <dt>Cohorte</dt>
          <dd>{h.comprobacion.cohorte}</dd>
          <dt>Diseño</dt>
          <dd>{h.comprobacion.diseno}</dd>
        </dl>
      </Seccion>

      <Seccion titulo="Relevancia frente a significancia" nota="Kosmos confunde lo estadísticamente significativo con lo científicamente valioso. Aquí son dos escalas: Rosa justifica la relevancia para el objetivo y tu la votas.">
        <div className="rejilla-2">
          <div className="tarjeta">
            <p className="campo-etiqueta">Evidencia estadística</p>
            <Chip tono={h.evidenciaEstadistica === 'fuerte' ? 'ok' : h.evidenciaEstadistica === 'debil' ? 'mal' : h.evidenciaEstadistica === 'moderada' ? 'aviso' : 'borde'}>
              {h.evidenciaEstadistica === 'no_aplica' ? 'No aplica' : h.evidenciaEstadistica.charAt(0).toUpperCase() + h.evidenciaEstadistica.slice(1)}
            </Chip>
            <p className="meta" style={{ marginTop: 6 }}>
              {resumenEvidencia(h.procedencia.fuentes)}
            </p>
          </div>
          <div className="tarjeta">
            <p className="campo-etiqueta">Relevancia para el objetivo</p>
            <p style={{ fontSize: 13, margin: '6px 0' }}>{h.relevancia.justificacion}</p>
            <div className="segmentos" role="group" aria-label="Tu voto de relevancia">
              {(['alta', 'media', 'baja'] as const).map((v) => (
                <button key={v} type="button" aria-pressed={h.relevancia.votoHumano === v} onClick={() => acciones.votarRelevancia(h.id, v)}>
                  {v.charAt(0).toUpperCase() + v.slice(1)}
                </button>
              ))}
            </div>
            {h.evidenciaEstadistica === 'fuerte' && h.relevancia.votoHumano === 'baja' && <p className="tono-aviso" style={{ fontSize: 12.5, marginTop: 6 }}>Significativa pero irrelevante: un agujero de conejo. Cuenta en Calidad.</p>}
          </div>
        </div>
      </Seccion>

      <Seccion detalle titulo="Novedad" nota="Consultas baratas antes de gastar una corrida: Open Targets, ClinicalTrials.gov, Agora, la genética humana (GWAS Catalog, ClinVar), los fármacos contra la diana (ChEMBL, DGIdb), los datos públicos para comprobarla (GEO, CELLxGENE) y si alguien ya lo propuso en la literatura.">
        <div className="novedad novedad-4">
          <div className="novedad-item">
            <strong>Open Targets</strong>
            <Chip tono={h.novedad.openTargets.estado === 'no_comprobado' ? 'borde' : h.novedad.openTargets.estado === 'sin_evidencia' ? 'ok' : 'aviso'}>{h.novedad.openTargets.estado === 'no_comprobado' ? 'No comprobado' : h.novedad.openTargets.estado === 'sin_evidencia' ? 'Sin evidencia previa' : 'Evidencia previa'}</Chip>
            <p>{h.novedad.openTargets.detalle}</p>
          </div>
          <div className="novedad-item">
            <strong>ClinicalTrials.gov</strong>
            <Chip tono={h.novedad.ensayos.estado === 'no_comprobado' ? 'borde' : h.novedad.ensayos.estado === 'sin_ensayo' ? 'ok' : 'aviso'}>{h.novedad.ensayos.estado === 'no_comprobado' ? 'No comprobado' : h.novedad.ensayos.estado === 'sin_ensayo' ? 'Sin ensayo' : 'Ya hay ensayo'}</Chip>
            <p>
              {h.novedad.ensayos.detalle}
              {h.novedad.ensayos.nct && (
                <>
                  {' '}
                  <a className="enlace" href={`https://clinicaltrials.gov/study/${h.novedad.ensayos.nct}`} target="_blank" rel="noopener noreferrer">
                    {h.novedad.ensayos.nct}
                  </a>
                </>
              )}
            </p>
          </div>
          <div className="novedad-item">
            <strong>Agora</strong>
            <Chip tono={h.novedad.agora.estado === 'no_nominada' ? 'ok' : 'aviso'}>{h.novedad.agora.estado === 'no_nominada' ? 'No nominada' : 'Diana nominada'}</Chip>
            <p>{h.novedad.agora.detalle}</p>
          </div>
          {h.novedad.genetica && (
            <div className="novedad-item">
              <strong>Genetica humana (GWAS Catalog, ClinVar)</strong>
              <Chip tono={h.novedad.genetica.estado === 'sin_vinculo' ? 'ok' : h.novedad.genetica.estado === 'vinculo_conocido' ? 'aviso' : 'borde'}>{h.novedad.genetica.estado === 'sin_vinculo' ? 'Sin vínculo genético' : h.novedad.genetica.estado === 'vinculo_conocido' ? 'Vínculo conocido' : 'No comprobado'}</Chip>
              <p>{h.novedad.genetica.detalle}</p>
            </div>
          )}
          {h.novedad.farmacos && (
            <div className="novedad-item">
              <strong>Farmacos (ChEMBL, DGIdb)</strong>
              <Chip tono={h.novedad.farmacos.estado === 'farmacos_existentes' ? 'aviso' : h.novedad.farmacos.estado === 'sin_farmacos' ? 'ok' : 'borde'}>{h.novedad.farmacos.estado === 'farmacos_existentes' ? 'Diana abordable' : h.novedad.farmacos.estado === 'sin_farmacos' ? 'Sin fármacos' : 'No comprobado'}</Chip>
              <p>{h.novedad.farmacos.detalle}</p>
            </div>
          )}
          {h.novedad.datosPublicos && (
            <div className="novedad-item">
              <strong>Datos publicos (GEO, CELLxGENE)</strong>
              <Chip tono={h.novedad.datosPublicos.estado === 'hay_datos' ? 'ok' : h.novedad.datosPublicos.estado === 'sin_datos' ? 'aviso' : 'borde'}>{h.novedad.datosPublicos.estado === 'hay_datos' ? 'Hay datos' : h.novedad.datosPublicos.estado === 'sin_datos' ? 'Sin datos públicos' : 'No comprobado'}</Chip>
              <p>{h.novedad.datosPublicos.detalle}</p>
              {h.novedad.datosPublicos.series.length > 0 && (
                <ul className="lista-limpia">
                  {h.novedad.datosPublicos.series.map((s) => (
                    <li key={s.accession} className="meta">
                      <a className="enlace" href={`https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${s.accession}`} target="_blank" rel="noopener noreferrer">
                        {s.accession}
                      </a>{' '}
                      {s.titulo} {s.n ? `(${s.n} muestras${s.plataforma ? `, ${s.plataforma}` : ''})` : ''}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <div className="novedad-item">
            <strong>Precedente en la literatura</strong>
            <Chip tono={h.novedad.precedente.estado === 'no_comprobado' ? 'borde' : h.novedad.precedente.estado === 'sin_precedente' ? 'ok' : h.novedad.precedente.estado === 'parcial' ? 'aviso' : 'mal'}>
              {h.novedad.precedente.estado === 'no_comprobado' ? 'No comprobado' : h.novedad.precedente.estado === 'sin_precedente' ? 'Sin precedente' : h.novedad.precedente.estado === 'parcial' ? 'Precedente parcial' : 'Ya publicado'}
            </Chip>
            <p>{h.novedad.precedente.detalle}</p>
          </div>
        </div>
      </Seccion>

      <Seccion titulo="Verificación" nota="Cada afirmación contrastada con su fuente, con su tipo (dato, literatura, interpretación). Lo bloqueante impide aceptar.">
        <Verificacion afirmaciones={h.afirmaciones} cobertura={cobertura} ocultarCitas={aCiegas} onVerTrayectoria={(_, celda) => onAbrirProcedencia('codigo', celda)} />
      </Seccion>

      <EjecucionesInSilico h={h} estado={estado} ahora={ahora} />

      {h.supuestos.length > 0 && (
        <Seccion detalle titulo="Supuestos" nota="La hipótesis descompuesta en lo que da por cierto, independiente de las citas (la verificación profunda de Co-Scientist).">
          <ArbolSupuestos supuestos={h.supuestos} />
        </Seccion>
      )}

      <Seccion detalle titulo="Revisiones del agente" nota="Seis tipos de revisión, separados, para saber que se hizo y que falta.">
        <ul className="revisiones-auto">
          {h.revisionesAutomaticas.map((r) => (
            <li key={r.tipo} className={`revision-auto revision-${r.estado}`}>
              <div className="acciones" style={{ gap: 8 }}>
                <Chip tono={r.estado === 'pendiente' ? 'borde' : r.estado === 'rehecha' ? 'acento' : 'ok'}>{r.estado === 'pendiente' ? 'Pendiente' : r.estado === 'rehecha' ? 'Rehecha' : 'Hecha'}</Chip>
                <strong style={{ fontSize: 13 }} title={TIPO_REVISION[r.tipo].nota}>
                  {TIPO_REVISION[r.tipo].etiqueta}
                </strong>
                {r.fecha !== null && (
                  <span className="meta">
                    <Momento t={r.fecha} ahora={ahora} />
                  </span>
                )}
              </div>
              <p className="meta">{r.resumen || TIPO_REVISION[r.tipo].nota}</p>
            </li>
          ))}
        </ul>
      </Seccion>

      <Seccion detalle titulo="Revisor" nota="Rosa atiende cada hallazgo en su siguiente mensaje: corrige o explica por que no aplica.">
        <Revisor hallazgos={h.hallazgos} />
      </Seccion>

      {h.partidos.length > 0 && (
        <Seccion detalle titulo="Partidos del torneo" nota="Contra quien, quien ganó y por que. Un Elo con pocos partidos dice poco.">
          <table className="tabla">
            <thead>
              <tr>
                <th>Iteración</th>
                <th>Rival</th>
                <th>Resultado</th>
                <th>Eje decisivo</th>
                <th>Por que</th>
              </tr>
            </thead>
            <tbody>
              {h.partidos.map((p, i) => {
                const rival = estado.hipotesis.find((x) => x.id === p.rivalId);
                return (
                  <tr key={i}>
                    <td className="num">{p.iteracion}</td>
                    <td>{rival ? <a className="enlace" href={rutaDe(h.investigacionId, 'hipotesis', rival.id)}>{rival.titulo.length > 50 ? `${rival.titulo.slice(0, 47)}...` : rival.titulo}</a> : p.rivalId}</td>
                    <td>
                      <Chip tono={p.resultado === 'gano' ? 'ok' : p.resultado === 'tablas' ? 'borde' : 'mal'}>{p.resultado === 'gano' ? 'Gano' : p.resultado === 'tablas' ? 'Tablas' : 'Perdio'}</Chip>
                    </td>
                    <td>{p.ejeDecisivo}</td>
                    <td className="meta">{p.resumenDebate}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Seccion>
      )}

      <Seccion
        detalle titulo="Replicación independiente"
        nota="Kosmos confirmo sus hallazgos clave con cinco trayectorias independientes. Gasta presupuesto de la iteración."
        acciones={
          <button type="button" className="btn btn-s" disabled={h.replicacion?.estado === 'en_curso' || !corrida || corrida.estado !== 'en_marcha'} onClick={() => acciones.replicarHipotesis(h.id, 5)}>
            Replicar x5
          </button>
        }
      >
        {h.replicacion ? (
          <div className="acciones">
            <Chip tono={h.replicacion.estado === 'en_curso' ? 'acento' : h.replicacion.contradicen === 0 ? 'ok' : 'aviso'}>
              {h.replicacion.hechas} de {h.replicacion.total} trayectorias · {h.replicacion.sostienen} sostienen · {h.replicacion.contradicen} contradicen
            </Chip>
            <span className="meta">
              Lanzada <Momento t={h.replicacion.empezadaEn} ahora={ahora} />
            </span>
          </div>
        ) : (
          <p className="meta">Sin replicar todavía.</p>
        )}
      </Seccion>

      {rivales.length > 0 && (
        <Seccion detalle titulo="Rivales" nota="Hipótesis que compiten por la misma pregunta.">
          <div className="rivales">
            {rivales.map((r) => (
              <a key={r.id} className="chip chip-borde" href={rutaDe(h.investigacionId, 'hipotesis', r.id)} title={r.titulo}>
                {r.titulo.length > 60 ? `${r.titulo.slice(0, 57)}...` : r.titulo} · {r.elo}
              </a>
            ))}
          </div>
        </Seccion>
      )}

      {h.experimento && (
        <Seccion titulo="Experimento propuesto" nota="El traspaso al laboratorio: protocolo, ensayo y criterios de éxito y refutación fijados de antemano. Al asignarlo a un laboratorio queda prerregistrado: la hipótesis y el protocolo se congelan con fecha en un artefacto, antes de que exista ningún dato. Los datos vuelven para que Rosa actualice su conclusión.">
          <div className="tarjeta seccion">
            <div className="experimento-bloque">
              <h4>Protocolo</h4>
              <ol className="protocolo">
                {h.experimento.protocolo
                  .split('\n')
                  .map((l) => l.replace(/^\s*\d+[.)]\s*/, '').trim())
                  .filter((l) => l !== '')
                  .map((l, i) => (
                    <li key={i}>{l}</li>
                  ))}
              </ol>
            </div>
            <div className="experimento-bloque">
              <h4>Ensayo</h4>
              <p>{h.experimento.ensayo}</p>
            </div>
            {(h.experimento.confirma || h.experimento.refuta) && (
              <div className="conclusion-columnas">
                <div className="experimento-bloque criterio-ok">
                  <h4>La confirmaría</h4>
                  <p>{h.experimento.confirma}</p>
                </div>
                <div className="experimento-bloque criterio-mal">
                  <h4>La refutaría</h4>
                  <p>{h.experimento.refuta}</p>
                </div>
              </div>
            )}
            {(h.experimento.controles || h.experimento.tamanoMuestral || h.experimento.alternativa) && (
              <div className="conclusion-columnas">
                {h.experimento.controles && (
                  <div className="experimento-bloque">
                    <h4>Controles</h4>
                    <p>{h.experimento.controles}</p>
                  </div>
                )}
                {h.experimento.tamanoMuestral && (
                  <div className="experimento-bloque">
                    <h4>Tamaño muestral</h4>
                    <p>{h.experimento.tamanoMuestral}</p>
                  </div>
                )}
                {h.experimento.alternativa && (
                  <div className="experimento-bloque">
                    <h4>Explicación alternativa y como se distingue</h4>
                    <p>{h.experimento.alternativa}</p>
                  </div>
                )}
              </div>
            )}
            {h.experimento.decisionQueCambia && (
              <div className="experimento-bloque">
                <h4>Qué decisión cambia con el resultado</h4>
                <p>{h.experimento.decisionQueCambia}</p>
              </div>
            )}
            <div className="experimento-bloque">
              <h4>Coste estimado</h4>
              <p>{h.experimento.costeEstimado}</p>
            </div>
            {h.experimento.analisisPedido && h.experimento.estado === 'propuesto' && (
              <div className="experimento-bloque">
                <h4>Con datos ya existentes</h4>
                <p>{h.experimento.analisisPedido}</p>
              </div>
            )}
            {h.experimento.resultado && (
              <div className={`experimento-bloque resultado resultado-${h.experimento.resultado.veredicto}`}>
                <h4>Resultado contra el prerregistro</h4>
                <div className="acciones">
                  <Chip tono={h.experimento.resultado.veredicto === 'confirma' ? 'ok' : h.experimento.resultado.veredicto === 'refuta' ? 'mal' : 'aviso'}>
                    {h.experimento.resultado.veredicto === 'confirma' ? 'Confirma la hipótesis' : h.experimento.resultado.veredicto === 'refuta' ? 'Refuta la hipótesis' : h.experimento.resultado.veredicto === 'inconcluso' ? 'Inconcluso' : 'No evaluable con estos datos'}
                  </Chip>
                  {h.experimento.resultado.clasificacion && (
                    <Chip tono={RESULTADO_LABORATORIO[h.experimento.resultado.clasificacion].tono} title={RESULTADO_LABORATORIO[h.experimento.resultado.clasificacion].nota}>
                      {RESULTADO_LABORATORIO[h.experimento.resultado.clasificacion].etiqueta}
                    </Chip>
                  )}
                  {h.experimento.resultado.versionProbada !== undefined && h.experimento.resultado.compatibleConActual === false && <Chip tono="aviso" title="El resultado probo una versión anterior de la hipótesis">Probo la v{h.experimento.resultado.versionProbada}</Chip>}
                  <span className="meta">
                    {h.experimento.resultado.fichero} · <Momento t={h.experimento.resultado.fecha} ahora={ahora} />
                  </span>
                </div>
                <Dimensiones d={h.experimento.resultado.dimensiones} />
                <p>{h.experimento.resultado.resultado}</p>
                {h.experimento.resultado.accionTomada && <p className="meta">Que hizo Rosa: {h.experimento.resultado.accionTomada}</p>}
                {h.experimento.resultado.hipotesisDerivadaId && (
                  <p className="meta">
                    Hipotesis derivada:{' '}
                    <a className="enlace" href={rutaDe(h.investigacionId, 'hipotesis', h.experimento.resultado.hipotesisDerivadaId)}>
                      abrir
                    </a>
                  </p>
                )}
                <p className="meta">{h.experimento.resultado.motivo}</p>
                {h.experimento.resultado.cifras.length > 0 && (
                  <ul className="cifras">
                    {h.experimento.resultado.cifras.map((c, i) => (
                      <li key={i}>
                        <strong>{c.nombre}:</strong> {c.valor}
                      </li>
                    ))}
                  </ul>
                )}
                {h.experimento.resultado.limitaciones && <p className="meta">Limitaciones: {h.experimento.resultado.limitaciones}</p>}
                {h.experimento.resultado.exploratorio && <p className="meta">Exploratorio, fuera del prerregistro: {h.experimento.resultado.exploratorio}</p>}
              </div>
            )}
            <div className="acciones">
              <Chip tono={h.experimento.estado === 'datos_recibidos' ? 'ok' : h.experimento.estado === 'propuesto' ? 'borde' : 'aviso'}>
                {h.experimento.estado === 'propuesto' ? 'Propuesto' : h.experimento.estado === 'asignado' ? `Asignado a ${h.experimento.laboratorio}` : h.experimento.estado === 'en_curso' ? 'En curso' : `Datos recibidos: ${h.experimento.ficheroDatos}`}
              </Chip>
              {h.experimento.prerregistradoEn && h.experimento.prerregistroArtefactoId && (
                <a className="chip chip-ok" href={rutaDe(h.investigacionId, 'artefactos', h.experimento.prerregistroArtefactoId)} title="Hipótesis, protocolo y criterios congelados antes de los datos">
                  Prerregistrado <Momento t={h.experimento.prerregistradoEn} ahora={ahora} />
                </a>
              )}
              {h.experimento.prerregistradoEn && h.experimento.selloExterno?.ok && (
                <Chip tono="ok" title={`sha256 ${h.experimento.selloExterno.hash}. Hora firmada por ${h.experimento.selloExterno.testigos.join(' y ')}: ${h.experimento.selloExterno.primeraHora}. Se verifica sin Rosa con openssl ts -verify sobre el token guardado.`}>
                  Sellado por {h.experimento.selloExterno.testigos.join(' y ')} ({h.experimento.selloExterno.primeraHora?.slice(0, 16).replace('T', ' ')} UTC)
                </Chip>
              )}
              {h.experimento.prerregistradoEn && !h.experimento.selloExterno?.ok && (
                <button type="button" className="btn btn-s" title={h.experimento.selloExterno?.error ? `Último intento: ${h.experimento.selloExterno.error}` : 'Pide a dos autoridades de sellado de tiempo (RFC 3161) que firmen la hora del prerregistro: un tercero atestigua que se congelo antes de los datos'} onClick={() => void acciones.sellarPrerregistro(h.id)}>
                  {h.experimento.selloExterno ? 'Reintentar el sello externo' : 'Sellar con un tercero'}
                </button>
              )}
            </div>
            {h.experimento.estado === 'propuesto' && (
              <div className="dirigir">
                <input className="entrada" value={lab} placeholder="Laboratorio (por ejemplo FLENI, Buenos Aires)" onChange={(e) => setLab(e.target.value)} aria-label="Laboratorio" />
                <button type="button" className="btn" disabled={lab.trim() === ''} onClick={() => acciones.asignarExperimento(h.id, lab)}>
                  Asignar a laboratorio
                </button>
              </div>
            )}
            {(h.experimento.estado === 'asignado' || h.experimento.estado === 'datos_recibidos') && (
              <div className="seccion">
                <p className="meta">
                  Cuando lleguen los datos del laboratorio, subelos aqui (CSV, TSV, JSON, texto o PDF, hasta 50 MB). Rosa los resume sin ningun modelo, el juez los compara con los criterios congelados en el prerregistro y la conclusion se rehace con esa evidencia.
                </p>
                <div className="campo">
                  <label htmlFor="exp-fichero">Fichero de datos</label>
                  <input id="exp-fichero" type="file" accept=".csv,.tsv,.txt,.json,.pdf,.md" onChange={(e) => setFicheroDatos(e.target.files?.[0] ?? null)} />
                </div>
                <div className="campo">
                  <label htmlFor="exp-analisis">Que analisis quieres (ademas de los criterios prerregistrados)</label>
                  <input id="exp-analisis" className="entrada" value={analisis} placeholder="Tiempo hasta la primera alteración, por grupo genético" onChange={(e) => setAnalisis(e.target.value)} />
                </div>
                <div className="acciones">
                  <button
                    type="button"
                    className="btn btn-primario"
                    disabled={ficheroDatos === null || subiendo}
                    onClick={async () => {
                      if (!ficheroDatos) return;
                      setSubiendo(true);
                      const error = await acciones.subirDatosExperimento(h.id, ficheroDatos, analisis);
                      setSubiendo(false);
                      setErrorSubida(error);
                      if (!error) setFicheroDatos(null);
                    }}
                  >
                    {subiendo ? 'Subiendo...' : 'Subir datos y evaluar contra el prerregistro'}
                  </button>
                  {errorSubida && <span className="tono-mal">{errorSubida}</span>}
                  {h.experimento.estado === 'datos_recibidos' && !h.experimento.resultado && <span className="meta">Datos recibidos; Rosa los esta evaluando.</span>}
                </div>
              </div>
            )}
            <ProtocoloYEnmiendas h={h} ahora={ahora} />
          </div>
        </Seccion>
      )}

      <Seccion detalle titulo="Historial">
        <ul className="lista-limpia">
          {h.revisiones.map((r, i) => (
            <li key={i}>
              <span>
                <strong style={{ fontWeight: 550 }}>{r.quien}</strong> · {r.accion.replace(/_/g, ' ')}
                {r.aCiegas && <Chip tono="borde">a ciegas</Chip>}
                {r.nota !== '' && <span className="meta"> · {r.nota}</span>}
              </span>
              <span className="meta">
                <Momento t={r.fecha} ahora={ahora} />
              </span>
            </li>
          ))}
        </ul>
        {h.revisionesHumanas.length > 0 && (
          <div className="seccion">
            <p className="campo-etiqueta">Revisiones escritas por personas (entran al siguiente debate del torneo)</p>
            {h.revisionesHumanas.map((r, i) => (
              <div key={i} className="mensaje mensaje-investigadora">
                <header>
                  <span>{r.quien}</span>
                  <span>
                    <Momento t={r.fecha} ahora={ahora} />
                  </span>
                </header>
                {r.supuestosCuestionados && <p>Supuestos cuestionados: {r.supuestosCuestionados}</p>}
                {r.literaturaQueFalta && <p>Literatura que falta: {r.literaturaQueFalta}</p>}
                {r.problemaExperimental && <p>Problema experimental: {r.problemaExperimental}</p>}
              </div>
            ))}
          </div>
        )}
      </Seccion>

      <Seccion titulo="Decisión" nota={cerrada ? 'Esta hipótesis ya se decidió. Se puede reabrir.' : aclarando ? 'Rosa está aclarando lo que marcaste. Volverá a la cola.' : motivo ?? 'Nada impide aceptarla. Tu lectura decide.'}>
        <div className="campo">
          <label htmlFor="nota-decision">Nota para Rosa y para el historial</label>
          <textarea id="nota-decision" value={nota} rows={2} onChange={(e) => setNota(e.target.value)} placeholder="Comprobable en FLENI; pedir a el investigador clínico principal si la cohorte tiene genotipo de TREM2" />
        </div>
        <button type="button" className="enlace" style={{ alignSelf: 'flex-start', fontSize: 13 }} onClick={() => setRevisionAbierta((v) => !v)}>
          {revisionAbierta ? 'Ocultar la revisión estructurada' : 'Escribir una revisión estructurada (entra al torneo como revisión, no solo como veredicto)'}
        </button>
        {revisionAbierta && (
          <div className="rejilla-3">
            <div className="campo">
              <label htmlFor="rev-sup">Supuestos que cuestionas</label>
              <textarea id="rev-sup" rows={3} value={rev.supuestosCuestionados} onChange={(e) => setRev({ ...rev, supuestosCuestionados: e.target.value })} />
            </div>
            <div className="campo">
              <label htmlFor="rev-lit">Literatura que falta</label>
              <textarea id="rev-lit" rows={3} value={rev.literaturaQueFalta} onChange={(e) => setRev({ ...rev, literaturaQueFalta: e.target.value })} />
            </div>
            <div className="campo">
              <label htmlFor="rev-exp">Problema experimental</label>
              <textarea id="rev-exp" rows={3} value={rev.problemaExperimental} onChange={(e) => setRev({ ...rev, problemaExperimental: e.target.value })} />
            </div>
          </div>
        )}
        <div className="acciones">
          {!cerrada && !aclarando && (
            <>
              <button type="button" className="btn btn-primario" disabled={motivo !== null} title={motivo ?? 'Aceptar y pasarla al modelo de mundo como hipótesis a perseguir'} onClick={() => decidir('aceptar', nota)}>
                Aceptar
              </button>
              <button type="button" className="btn" onClick={() => decidir('refinar', nota)}>
                Pedir que la refine
              </button>
              <Confirmar
                etiqueta="No puedo juzgar"
                pregunta="Di que te impide juzgarla (ambigua, falta contexto, no reproducible). Rosa la aclara y vuelve a la cola marcada como aclarada."
                pedirTexto={{ etiqueta: 'Qué falta', marcador: 'No queda claro si habla de PSEN1 o de todo el Alzheimer familiar' }}
                onConfirmar={(m) => decidir('no_puedo_juzgar', m)}
              />
              <Confirmar
                etiqueta="Descartar"
                peligro
                pregunta="El motivo queda en el modelo de mundo para que Rosa no vuelva a proponer lo mismo."
                pedirTexto={{ etiqueta: 'Motivo', marcador: 'Se apoya en un articulo retractado' }}
                onConfirmar={(m) => {
                  acciones.revisarHipotesis(h.id, 'descartar', m, aCiegas, revisionHumana, h.version ?? 1, segundosRevision());
                  setNota('');
                }}
              />
            </>
          )}
          {cerrada && (
            <button type="button" className="btn" onClick={() => decidir('reabrir', nota)}>
              Reabrir
            </button>
          )}
        </div>
      </Seccion>

      <Seccion
        titulo="Dossier para el laboratorio"
        nota="El expediente con el que la hipótesis sale al laboratorio, en siete partes: si va o no y por que (bloqueos), la hipótesis completa con su versión, la evidencia con procedencia, los análisis con datos, las decisiones, el protocolo prerregistrado y que se aprende con cada resultado. Se arma sin ningún modelo, con lo que hay en el estado."
        acciones={
          <button type="button" className="btn btn-s" disabled={estado.conexion === 'muestra'} onClick={() => acciones.generarDossier(h.id)}>
            {h.dossierArtefactoId ? 'Regenerar dossier' : 'Generar dossier'}
          </button>
        }
      >
        {h.dossierArtefactoId ? (
          <p className="meta">
            Ultimo dossier:{' '}
            <a className="enlace" href={rutaDe(h.investigacionId, 'artefactos', h.dossierArtefactoId)}>
              abrir en Artefactos
            </a>
            . Cada generacion es una version nueva; las anteriores se conservan.
          </p>
        ) : (
          <p className="meta">Sin dossier todavía.</p>
        )}
      </Seccion>

      <Seccion detalle titulo="Exportar expediente" nota="Todo lo que hace falta para auditar la hipótesis fuera de Rosa: versiones, decisiones con fecha, trazas, cuadernos, fuentes.">
        <div className="dirigir">
          <input className="entrada" value={aplicableA} placeholder="Aplicable a (cohorte, modelo, condición): por ejemplo portadores de APOE4 con genotipo de TREM2" onChange={(e) => setAplicableA(e.target.value)} aria-label="Aplicable a" />
          <a className="btn" href={`/api/hipotesis/${encodeURIComponent(h.id)}/rocrate`} download={`rosa-${h.id}.crate.zip`} title="RO-Crate 1.2 (perfil Process Run Crate) con procedencia W3C PROV: la hipótesis, el dossier, las decisiones, las fuentes con su riesgo de sesgo, el código y resultado de cada análisis, el prerregistro y sus sellos RFC 3161. Se verifica con herramientas de terceros, sin Rosa.">
            Exportar RO-Crate (PROV)
          </a>
          <button type="button" className="btn" onClick={() => descargar(`${h.id}-expediente.json`, expediente(h, estado.hechos, aplicableA.trim() || 'sin limite declarado'), 'application/json')}>
            Descargar expediente
          </button>
        </div>
      </Seccion>

      <BandejaComentarios pendientes={pendientes} onQuitar={(id) => acciones.quitarComentario(id)} onEditar={(id, n) => acciones.editarComentario(id, n)} onEnviar={(m) => acciones.enviarComentarios(h.id, m)} />
    </div>
  );
}

export function Hipotesis({
  inv,
  estado,
  ahora,
  detalleId,
  cajonAbierto,
  setCajonAbierto,
  irA,
}: {
  inv: Investigacion;
  estado: EstadoRosa;
  ahora: number;
  detalleId: string | null;
  cajonAbierto: boolean;
  setCajonAbierto: (v: boolean) => void;
  irA: (hash: string) => void;
}) {
  const propias = useMemo(() => ordenarCola(estado.hipotesis.filter((h) => h.investigacionId === inv.id)), [estado.hipotesis, inv.id]);
  // "laboratorio" en el sitio del id es la vista del tramo final (la etapa
  // Laboratorio del hilo): lo asignado, en curso o con datos, y las candidatas
  // con experimento propuesto que esperan un laboratorio.
  const vistaLab = detalleId === 'laboratorio';
  const [filtro, setFiltro] = useState<'pendientes' | 'todas' | 'laboratorio'>(vistaLab ? 'laboratorio' : 'pendientes');
  useEffect(() => {
    if (vistaLab) setFiltro('laboratorio');
    else if (detalleId === null) setFiltro((f) => (f === 'laboratorio' ? 'pendientes' : f));
  }, [vistaLab, detalleId]);
  const [proponiendo, setProponiendo] = useState(false);
  const [pestana, setPestana] = useState<PestanaProcedencia>('fuentes');
  const [celda, setCelda] = useState<number | null>(null);
  const seleccionada = vistaLab ? null : propias.find((h) => h.id === detalleId) ?? null;
  const enLaboratorio = (h: Hip) => Boolean(h.experimento && (h.experimento.estado !== 'propuesto' || h.candidata));
  const visibles = filtro === 'todas' ? propias : filtro === 'laboratorio' ? propias.filter(enLaboratorio) : propias.filter((h) => h.estado === 'propuesta' || h.estado === 'en_revision' || h.estado === 'refinar' || h.estado === 'aclarando');

  if (seleccionada) {
    return (
      <>
        <div className="contenido">
          <p style={{ marginBottom: 14 }}>
            <a className="enlace" href={rutaDe(inv.id, 'hipotesis')}>
              Volver a la cola
            </a>
          </p>
          <Detalle
            key={seleccionada.id}
            h={seleccionada}
            estado={estado}
            ahora={ahora}
            onAbrirProcedencia={(p, c) => {
              setPestana(p);
              setCelda(c ?? null);
              setCajonAbierto(true);
            }}
          />
        </div>
        {cajonAbierto && <Procedencia hipotesis={seleccionada} ahora={ahora} onCerrar={() => setCajonAbierto(false)} pestanaInicial={pestana} celdaDestacada={celda} />}
      </>
    );
  }

  return (
    <div className="contenido">
      <AvisoMuestra conexion={estado.conexion} />
      <div className="pantalla-cabecera" style={{ marginTop: 16 }}>
        <div>
          <h2>{filtro === 'laboratorio' ? 'Laboratorio' : 'Cola de hipótesis'}</h2>
          <p>{filtro === 'laboratorio' ? 'El tramo final: hipótesis con experimento asignado (prerregistrado y sellado), en curso o con datos recibidos, y las candidatas que esperan un laboratorio. Cuando vuelven los datos, Rosa los juzga contra el prerregistro.' : 'Lo que Rosa propone y espera tu lectura. Arriba lo pendiente, ordenado por Elo. Nada entra al modelo de mundo sin pasar por aquí.'}</p>
        </div>
        <div className="acciones">
          <div className="segmentos" role="group" aria-label="Filtro">
            <button type="button" aria-pressed={filtro === 'pendientes'} onClick={() => setFiltro('pendientes')}>
              Pendientes
            </button>
            <button type="button" aria-pressed={filtro === 'todas'} onClick={() => setFiltro('todas')}>
              Todas
            </button>
            <button type="button" aria-pressed={filtro === 'laboratorio'} onClick={() => setFiltro('laboratorio')} title="Hipótesis con experimento asignado, en curso o con datos, y candidatas que esperan laboratorio">
              Laboratorio
            </button>
          </div>
          <button type="button" className="btn btn-primario" onClick={() => setProponiendo((v) => !v)}>
            Proponer hipotesis
          </button>
        </div>
      </div>
      {proponiendo && <FormularioHipotesis inv={inv} onCerrar={() => setProponiendo(false)} irA={irA} />}
      {visibles.length === 0 ? (
        filtro === 'laboratorio' ? (
          <Vacio titulo="Nada en el laboratorio todavía" pasos={['El Killer deja avanzar una hipótesis y el torneo la coloca entre las candidatas (etapa Candidatas del hilo, en Ranking).', 'Rosa le propone un experimento: protocolo, ensayo, controles y criterios de éxito y refutación.', 'Tu lo asignas a un laboratorio desde la ficha: el prerregistro se congela y se sella con un tercero.', 'El laboratorio devuelve los datos y Rosa los juzga contra lo prerregistrado.']}>
            Aqui apareceran las hipotesis que lleguen a ese tramo.
          </Vacio>
        ) : (
        <Vacio titulo={filtro === 'pendientes' && propias.length > 0 ? 'Nada pendiente' : 'Todavía no hay hipótesis'} pasos={propias.length === 0 ? ['Rosa busca literatura y verifica afirmaciones (etapas 2 y 3 del hilo).', 'Lo sostenido entra al modelo de mundo.', 'Con eso, Rosa genera hipótesis y el Killer las juzga; las que quedan aparecen aquí, ordenadas por Elo.', 'Tu decides sobre cada una: aceptar, descartar o pedir que la refine.'] : undefined}>
          {propias.length > 0 ? 'Rosa no tiene hipótesis esperando tu revisión en esta investigación. Con "Todas" ves las ya decididas.' : 'También puedes proponer una tu con el botón de arriba: pasa por el mismo Killer.'}
        </Vacio>
        )
      ) : (
        <ListaAnimada className="cola" como="div">
          {visibles.map((h) => (
            <ElementoAnimado key={h.id} salida={salidaDe(estado.hipotesis.find((x) => x.id === h.id) ?? h)}>
              <FilaCola h={h} ahora={ahora} href={rutaDe(inv.id, 'hipotesis', h.id)} horasEspera={estado.politicaEsperas.horas} estado={estado} />
            </ElementoAnimado>
          ))}
        </ListaAnimada>
      )}
    </div>
  );
}
