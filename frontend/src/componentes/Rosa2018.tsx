// Las piezas de la interfaz que trae el documento de concepto ROSA2018
// (septiembre de 2026): la mision estructurada, la tarjeta de la hipotesis
// con sus versiones, las decisiones del Hypothesis Killer con sus
// comprobaciones y su auditoria, los bloqueos no compensables, las
// ejecuciones in silico con plan congelado y auditoria, la puerta de
// reproduccion, el libro de procedencia de un dataset y el registro de
// aprendizaje en tres niveles. Cada pieza dice que es y por que esta, para
// que quien no vivio el documento la entienda igual.

import { useState } from 'react';
import { acciones } from '../datos/almacen';
import { CAMPOS_ENMENDABLES } from '../datos/acciones';
import type { CambioAprendizaje, Comprobacion, Corrida, Dataset, Decision, DimensionesResultado, Ejecucion, EstadoRosa, Hipotesis, Investigacion, MetodoRegistrado, PasoRutaTerapeutica, PlanAnalisis, PreguntaCampana, ProcedenciaDataset, Reproduccion, Responsables, CampoEnmendable, AreaInvestigacion, ConectorCatalogo, RevisionRegistro, ProcedenciaArtefacto, ConsultaBase, NivelPermisoConector, SkillCatalogo } from '../datos/tipos';
import {
  ACCESO_DATASET,
  BLOQUEO,
  CLASE_EVIDENCIA,
  COMPROBACION_KILLER,
  DECISION_KILLER,
  DIMENSION_RESULTADO,
  ESTADO_APRENDIZAJE,
  ESTADO_EJECUCION,
  ESTADO_METODO,
  ESTADO_REPRODUCCION,
  ETAPA_DECISION,
  INTERPRETACION_EJECUCION,
  NIVEL_APRENDIZAJE,
  PASO_RUTA,
  RESULTADO_COMPROBACION,
  RUNTIME_EJECUCION,
  TIPO_APRENDIZAJE,
  TIPO_METODO,
  USO_IA,
  VEREDICTO_AUDITORIA, IDENTIFICACION_CAUSAL, TIPO_ARISTA, GRUPO_CONECTOR, ESTADO_CONECTOR, CLASE_HALLAZGO_REGISTRO } from '../lib/etiquetas';
import { EXPLICACION_BLOQUEO } from '../lib/priorizacion';
import { rutaDe } from '../lib/ruta';
import { Chip, Confirmar, Momento, Seccion } from './piezas';

/* ---------------------------------------------------------------------
   Mision
   --------------------------------------------------------------------- */

export function FormularioMision({ inv, compacto = false, corridas = [] }: { inv: Investigacion; compacto?: boolean; corridas?: Corrida[] }) {
  const m = inv.mision;
  const [editando, setEditando] = useState(m === null || m === undefined);
  const [d, setD] = useState(() => ({
    poblacion: m?.poblacion ?? '',
    etapa: m?.etapa ?? '',
    celulaTejido: m?.celulaTejido ?? '',
    mecanismo: m?.mecanismo ?? '',
    tipoIntervencion: m?.tipoIntervencion ?? '',
    capacidades: (m?.capacidadesLaboratorio ?? []).join('\n'),
    llamadas: String(m?.presupuesto.llamadas ?? 1500),
    usd: String(m?.presupuesto.usd ?? 60),
    horas: String(m?.presupuesto.horas ?? 72),
  }));
  const [resp, setResp] = useState<Responsables>(() => ({ patrocinador: '', liderCientifico: '', metodos: '', datos: '', ingenieria: '', laboratorio: '', evaluacion: '', ...(m?.responsables ?? {}) }));
  const ROLES: { k: keyof Responsables; label: string; nota: string }[] = [
    { k: 'patrocinador', label: 'Patrocinador', nota: 'Fija prioridades y autoriza recursos' },
    { k: 'liderCientifico', label: 'Lider cientifico', nota: 'Aprueba criterios cientificos e interpretaciones mayores' },
    { k: 'metodos', label: 'Metodos', nota: 'Valida los metodos causales y estadisticos' },
    { k: 'datos', label: 'Datos', nota: 'Bioinformatica y libro de procedencia' },
    { k: 'ingenieria', label: 'Ingenieria', nota: 'Ejecucion e integridad de los registros' },
    { k: 'laboratorio', label: 'Laboratorio', nota: 'Protocolos fisicos y calidad' },
    { k: 'evaluacion', label: 'Evaluacion', nota: 'Conjuntos reservados y comparaciones; no es quien escribe la conclusion' },
  ];
  const campo = (k: keyof typeof d, label: string, marcador: string, filas = 1) => (
    <div className="campo" key={k}>
      <label htmlFor={`mis-${k}`}>{label}</label>
      {filas > 1 ? <textarea id={`mis-${k}`} rows={filas} value={d[k]} placeholder={marcador} onChange={(e) => setD({ ...d, [k]: e.target.value })} /> : <input id={`mis-${k}`} value={d[k]} placeholder={marcador} onChange={(e) => setD({ ...d, [k]: e.target.value })} />}
    </div>
  );
  const guardar = () => {
    acciones.aprobarMision(inv.id, {
      poblacion: d.poblacion,
      etapa: d.etapa,
      celulaTejido: d.celulaTejido,
      mecanismo: d.mecanismo,
      tipoIntervencion: d.tipoIntervencion,
      capacidadesLaboratorio: d.capacidades.split('\n'),
      presupuesto: { llamadas: Number(d.llamadas), usd: Number(d.usd), horas: Number(d.horas) },
      responsables: resp,
    });
    setEditando(false);
  };
  if (!m && !editando) return null;
  if (!editando && m) {
    return (
      <div className="tarjeta seccion mision">
        <div className="acciones" style={{ justifyContent: 'space-between' }}>
          <div className="acciones">
            {m.aprobadaEn ? (
              <Chip tono="ok" title={`Aprobada por ${m.aprobadaPor ?? 'una persona'}`}>
                Aprobada <Momento t={m.aprobadaEn} ahora={Date.now()} soloRelativo />
              </Chip>
            ) : (
              <Chip tono="aviso">Propuesta por Rosa: falta tu aprobacion</Chip>
            )}
            {m.propuestaPorRosa && <Chip tono="borde">Valores propuestos por Rosa</Chip>}
          </div>
          <div className="acciones">
            {!m.aprobadaEn && (
              <button type="button" className="btn btn-primario btn-s" onClick={() => acciones.aprobarMision(inv.id, {})}>
                Aprobar tal cual
              </button>
            )}
            <button type="button" className="btn btn-s" onClick={() => setEditando(true)}>
              {m.aprobadaEn ? 'Editar' : 'Corregir y aprobar'}
            </button>
          </div>
        </div>
        <dl className={`comprobacion ${compacto ? 'mision-compacta' : ''}`}>
          <dt>Poblacion</dt>
          <dd>{m.poblacion || 'sin fijar'}</dd>
          <dt>Etapa</dt>
          <dd>{m.etapa || 'sin fijar'}</dd>
          <dt>Celula o tejido</dt>
          <dd>{m.celulaTejido || 'sin fijar'}</dd>
          <dt>Mecanismo</dt>
          <dd>{m.mecanismo || 'sin fijar'}</dd>
          <dt>Tipo de intervencion</dt>
          <dd>{m.tipoIntervencion || 'sin fijar'}</dd>
          <dt>Capacidades del laboratorio</dt>
          <dd>{m.capacidadesLaboratorio.length ? m.capacidadesLaboratorio.join('; ') : 'sin declarar'}</dd>
          <dt>Presupuesto</dt>
          <dd>
            {m.presupuesto.llamadas} llamadas · {m.presupuesto.usd.toFixed(0)} USD estimados · {m.presupuesto.horas} h
          </dd>
          <dt>Responsables</dt>
          <dd>
            {m.responsables && Object.values(m.responsables).some((v) => v) ? (
              ROLES.filter((r) => m.responsables?.[r.k]).map((r) => `${r.label}: ${m.responsables?.[r.k]}`).join(' · ')
            ) : (
              <span className="tono-aviso">sin asignar: quien escribe una conclusion no puede ser su unico evaluador</span>
            )}
          </dd>
        </dl>
        {(m.areas?.length ?? 0) > 0 && !compacto && (
          <details className="versiones" open>
            <summary>Areas de investigacion que Rosa comparo ({m.areas!.length}); empieza por las elegidas</summary>
            <p className="meta">Se comparan por relevancia para la meta, valor de intervencion, incertidumbre, comprobabilidad, coste, demora y dependencia, conservando familias de mecanismo distintas. La disponibilidad de datos no sustituye a la relevancia. Un mecanismo desconocido sigue siendo una explicacion permitida.</p>
            <table className="tabla">
              <thead>
                <tr>
                  <th>Area</th>
                  <th>Familia</th>
                  <th>Relevancia</th>
                  <th>Comprobabilidad</th>
                  <th>Coste y demora</th>
                  <th>Estado</th>
                  <th>Gobierno</th>
                </tr>
              </thead>
              <tbody>
                {m.areas!.map((a) => (
                  <FilaArea key={a.id} inv={inv} a={a} corridas={corridas} />
                ))}
              </tbody>
            </table>
          </details>
        )}
      </div>
    );
  }
  return (
    <div className="tarjeta seccion mision">
      <p className="meta">La mision fija el marco antes de la primera corrida: a quien aplica, en que etapa, en que celula o tejido, que mecanismo, que tipo de resultado se busca y que puede hacer el laboratorio. Lo que se deje en blanco queda "sin fijar" y Rosa no lo inventa.</p>
      <div className="rejilla-2">
        {campo('poblacion', 'Poblacion', 'Adultos con deterioro cognitivo leve, amiloide positivos')}
        {campo('etapa', 'Etapa de la enfermedad', 'Prodromica')}
        {campo('celulaTejido', 'Celula o tejido', 'Astrocitos; plasma')}
        {campo('mecanismo', 'Mecanismo', 'Reactividad astrocitaria')}
        {campo('tipoIntervencion', 'Tipo de intervencion o resultado', 'Biomarcador de progresion')}
        {campo('capacidades', 'Capacidades del laboratorio (una por linea)', 'Inmunoensayo Simoa en plasma\nPET de amiloide', 3)}
      </div>
      <div className="rejilla-3">
        {campo('llamadas', 'Presupuesto en llamadas al modelo', '1500')}
        {campo('usd', 'Presupuesto en dolares (estimado por tokens)', '60')}
        {campo('horas', 'Presupuesto en horas de reloj', '72')}
      </div>
      <p className="campo-etiqueta">Responsables (se pueden combinar, pero quien escribe una conclusion no es su unico evaluador)</p>
      <div className="rejilla-3">
        {ROLES.map((r) => (
          <div className="campo" key={r.k}>
            <label htmlFor={`resp-${r.k}`} title={r.nota}>
              {r.label}
            </label>
            <input id={`resp-${r.k}`} value={resp[r.k]} placeholder={r.nota} onChange={(e) => setResp({ ...resp, [r.k]: e.target.value })} />
          </div>
        ))}
      </div>
      <div className="acciones">
        <button type="button" className="btn btn-primario" onClick={guardar}>
          Aprobar la mision
        </button>
        {m && (
          <button type="button" className="btn btn-fantasma" onClick={() => setEditando(false)}>
            Cancelar
          </button>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------
   Tarjeta, versiones, bloqueos
   --------------------------------------------------------------------- */

export function TarjetaDeHipotesis({ h }: { h: Hipotesis }) {
  const t = h.tarjeta;
  return (
    <Seccion titulo="Tarjeta de la hipotesis" nota="El contrato minimo para que el Killer la juzgue y un laboratorio la ejecute: diana, celula, etapa, intervencion, la prediccion que la refutaria y sus riesgos. Sin prediccion falsable no avanza.">
      {t === null || t === undefined ? (
        <p className="meta">{t === null ? 'Rosa no pudo rellenar la tarjeta.' : 'Rosa todavia no rellena la tarjeta de esta hipotesis.'}</p>
      ) : (
        <dl className="comprobacion tarjeta-hip">
          <dt>Diana o proceso</dt>
          <dd>{t.diana || 'sin especificar'}</dd>
          <dt>Celula o tejido</dt>
          <dd>{t.celula || 'sin especificar'}</dd>
          <dt>Etapa</dt>
          <dd>{t.etapa || 'sin especificar'}</dd>
          <dt>Intervencion</dt>
          <dd>
            {t.intervencion || 'ninguna'} <Chip tono="borde">{t.direccion.replace('_', ' ')}</Chip>
          </dd>
          <dt>Prediccion falsable</dt>
          <dd className={t.prediccionFalsable ? '' : 'tono-mal'}>{t.prediccionFalsable || 'NINGUNA: asi no es evaluable'}</dd>
          <dt>Riesgos</dt>
          <dd>{t.riesgos.length ? <ul className="lista-limpia">{t.riesgos.map((r, i) => <li key={i}>{r}</li>)}</ul> : 'ninguno declarado'}</dd>
          <dt>Ruta terapeutica</dt>
          <dd>
            <RutaTerapeutica paso={t.pasoRuta ?? 'mecanismo'} />
          </dd>
        </dl>
      )}
      {(h.versiones?.length ?? 0) > 0 && (
        <details className="versiones">
          <summary>
            Version {h.version ?? 1} · {h.versiones!.length} {h.versiones!.length === 1 ? 'version anterior' : 'versiones anteriores'} (reformular no sobrescribe)
          </summary>
          <ul className="lista-limpia">
            {h.versiones!.map((v) => (
              <li key={v.n}>
                <div>
                  <strong style={{ fontSize: 13 }}>
                    v{v.n} · {v.quien} · <Momento t={v.fecha} ahora={Date.now()} />
                  </strong>
                  <p style={{ fontSize: 13 }}>{v.titulo}</p>
                  <p className="meta">{v.enunciado}</p>
                  <p className="meta">Por que cambio: {v.motivo}</p>
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}
    </Seccion>
  );
}

/** La ruta terapeutica del plan completo, con el paso actual marcado. Una
 *  campana celular completada no completa la ruta. */
export function RutaTerapeutica({ paso }: { paso: PasoRutaTerapeutica }) {
  const pasos = (Object.keys(PASO_RUTA) as PasoRutaTerapeutica[]).sort((a, b) => PASO_RUTA[a].orden - PASO_RUTA[b].orden);
  return (
    <ol className="ruta-terapeutica" aria-label="Ruta terapeutica">
      {pasos.map((p) => (
        <li key={p} className={p === paso ? 'actual' : PASO_RUTA[p].orden < PASO_RUTA[paso].orden ? 'previo' : ''} title={PASO_RUTA[p].etiqueta}>
          {PASO_RUTA[p].etiqueta}
        </li>
      ))}
    </ol>
  );
}

/** Las dimensiones de un resultado de laboratorio que coexisten. */
export function Dimensiones({ d }: { d: DimensionesResultado | undefined }) {
  if (!d) return null;
  const activas = (Object.keys(DIMENSION_RESULTADO) as (keyof typeof DIMENSION_RESULTADO)[]).filter((k) => d[k]);
  return (
    <div className="acciones" style={{ gap: 4 }}>
      <span className="meta">Dimensiones:</span>
      {activas.length === 0 ? <span className="meta">ninguna marcada</span> : activas.map((k) => <Chip key={k} tono={k === 'efectoPredicho' ? 'ok' : k === 'falloTecnico' || k === 'toxicidad' ? 'mal' : 'aviso'}>{DIMENSION_RESULTADO[k]}</Chip>)}
      {d.nota && <span className="meta">{d.nota}</span>}
    </div>
  );
}

/** La pregunta concreta de la campana, con la plantilla del plan completo. */
export function PreguntaDeCampana({ corrida }: { corrida: Corrida }) {
  const q = corrida.pregunta;
  const [editando, setEditando] = useState(false);
  const [f, setF] = useState<PreguntaCampana>(() => q ?? { contexto: '', etapa: '', intervencion: '', comparador: '', desenlace: '', ventana: '', unidadBiologica: '', mecanismos: '', decision: '', umbralEfecto: '', umbralResuelto: false, pasoRuta: 'mecanismo', propuestaPorRosa: false, aprobadaEn: null });
  if (q === undefined || q === null) return null;
  const campo = (k: keyof PreguntaCampana, label: string) => (
    <div className="campo" key={k}>
      <label htmlFor={`pq-${k}`}>{label}</label>
      <input id={`pq-${k}`} value={String(f[k] ?? '')} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
    </div>
  );
  return (
    <Seccion
      titulo="Pregunta de esta campana"
      nota="Rosa la formula desde la meta y el area elegida con una plantilla fija: contexto, etapa, intervencion, comparador, desenlace, ventana, unidad biologica independiente, mecanismos que distingue, decision que se toma con la respuesta y umbral de efecto. Un umbral sin base queda 'sin resolver'. Se aprueba con el primer plan."
      acciones={
        <div className="acciones">
          {q.aprobadaEn ? <Chip tono="ok">Aprobada</Chip> : <Chip tono="aviso">Propuesta por Rosa</Chip>}
          {!q.umbralResuelto && <Chip tono="aviso" title="No hay un valor defendible del efecto minimo que importaria">Umbral sin resolver</Chip>}
          <button type="button" className="btn btn-s" onClick={() => setEditando((v) => !v)}>
            {editando ? 'Cancelar' : 'Corregir'}
          </button>
        </div>
      }
    >
      {!editando ? (
        <div className="seccion">
          {(q as PreguntaCampana & { enunciado?: string }).enunciado && <p className="llano-pregunta">{(q as PreguntaCampana & { enunciado?: string }).enunciado}</p>}
          <dl className="comprobacion">
            <dt>Contexto (C)</dt>
            <dd>{q.contexto || 'sin fijar'}</dd>
            <dt>Etapa (S)</dt>
            <dd>{q.etapa || 'sin fijar'}</dd>
            <dt>Intervencion (A)</dt>
            <dd>{q.intervencion || 'sin fijar'}</dd>
            <dt>Comparador (B)</dt>
            <dd>{q.comparador || 'sin fijar'}</dd>
            <dt>Desenlace (P)</dt>
            <dd>{q.desenlace || 'sin fijar'}</dd>
            <dt>Ventana (T)</dt>
            <dd>{q.ventana || 'sin fijar'}</dd>
            <dt>Unidad biologica</dt>
            <dd>{q.unidadBiologica || 'sin fijar'}</dd>
            <dt>Mecanismos que distingue</dt>
            <dd>{q.mecanismos || 'sin fijar'}</dd>
            <dt>Decision que se toma</dt>
            <dd>{q.decision || 'sin fijar'}</dd>
            <dt>Umbral de efecto</dt>
            <dd className={q.umbralResuelto ? '' : 'tono-aviso'}>{q.umbralEfecto || 'sin resolver'}</dd>
          </dl>
          <RutaTerapeutica paso={q.pasoRuta} />
        </div>
      ) : (
        <div className="seccion">
          <div className="rejilla-2">
            {campo('contexto', 'Contexto (C)')}
            {campo('etapa', 'Etapa (S)')}
            {campo('intervencion', 'Intervencion (A)')}
            {campo('comparador', 'Comparador (B)')}
            {campo('desenlace', 'Desenlace (P), con medida y unidad')}
            {campo('ventana', 'Ventana de tiempo (T)')}
            {campo('unidadBiologica', 'Unidad biologica independiente')}
            {campo('mecanismos', 'Mecanismos que distingue (M1 frente a M2)')}
            {campo('decision', 'Decision que se toma con la respuesta')}
            {campo('umbralEfecto', 'Umbral de efecto (o "sin resolver")')}
          </div>
          <div className="campo">
            <label htmlFor="pq-ruta">Paso de la ruta terapeutica</label>
            <select id="pq-ruta" value={f.pasoRuta} onChange={(e) => setF({ ...f, pasoRuta: e.target.value as PasoRutaTerapeutica })}>
              {(Object.keys(PASO_RUTA) as PasoRutaTerapeutica[]).map((p) => (
                <option key={p} value={p}>
                  {PASO_RUTA[p].etiqueta}
                </option>
              ))}
            </select>
          </div>
          <div className="acciones">
            <button
              type="button"
              className="btn btn-primario btn-s"
              onClick={() => {
                acciones.actualizarPregunta(corrida.id, f);
                setEditando(false);
              }}
            >
              Guardar y aprobar
            </button>
          </div>
        </div>
      )}
    </Seccion>
  );
}

/** El registro de metodos, predictores, recursos y ensayos (plan completo, seccion 5). */
export function RegistroMetodos({ metodos, ahora }: { metodos: MetodoRegistrado[] | undefined; ahora: number }) {
  const lista = metodos ?? [];
  return (
    <Seccion titulo="Registro de metodos y ensayos" nota="Cada metodo dice que puede evaluar, donde aplica, que necesita, como se valido y en que estado esta. La popularidad no lo hace apto; la validacion si. La puerta de reproduccion marca los metodos de analisis como probados en contexto. Un predictor no confirma sus propios datos de entrenamiento.">
      {lista.length === 0 ? (
        <p className="meta">Sin servidor no hay registro que leer.</p>
      ) : (
        <ul className="lista-limpia metodos">
          {lista.map((m) => (
            <FilaMetodo key={m.id} m={m} ahora={ahora} />
          ))}
        </ul>
      )}
    </Seccion>
  );
}

function FilaMetodo({ m, ahora }: { m: MetodoRegistrado; ahora: number }) {
  const e = ESTADO_METODO[m.estado];
  return (
    <li>
      <div style={{ flex: 1 }}>
        <div className="acciones" style={{ gap: 6 }}>
          <strong style={{ fontSize: 13.5 }}>{m.nombre}</strong>
          <Chip tono="borde">{TIPO_METODO[m.tipo]}</Chip>
          <Chip tono={e.tono}>{e.etiqueta}</Chip>
          <span className="meta">
            <Momento t={m.actualizadoEn} ahora={ahora} />
          </span>
        </div>
        <p className="meta" style={{ marginTop: 4 }}>
          Evalua: {m.evalua}. {m.contextos.length ? `Contextos: ${m.contextos.join('; ')}. ` : ''}
          {m.exclusiones.length ? `Excluye: ${m.exclusiones.join('; ')}. ` : ''}
          Validacion: {m.validacion || 'sin declarar'}. {m.fallosConocidos ? `Fallos conocidos: ${m.fallosConocidos}. ` : ''}
          {m.probadoEn.length ? `Probado en: ${m.probadoEn.join('; ')}. ` : ''}
          {m.version ? `Version: ${m.version}. ` : ''}
          {m.responsable ? `Responsable: ${m.responsable}.` : ''}
        </p>
      </div>
      <select className="entrada entrada-s" style={{ width: 'auto' }} value={m.estado} onChange={(ev) => acciones.actualizarMetodo(m.id, { estado: ev.target.value as MetodoRegistrado['estado'] })} aria-label={`Estado de ${m.nombre}`}>
        {(Object.keys(ESTADO_METODO) as MetodoRegistrado['estado'][]).map((s) => (
          <option key={s} value={s}>
            {ESTADO_METODO[s].etiqueta}
          </option>
        ))}
      </select>
    </li>
  );
}

export function Bloqueos({ bloqueos, candidata }: { bloqueos: Hipotesis['bloqueos']; candidata: boolean | undefined }) {
  const b = bloqueos ?? [];
  if (b.length === 0) {
    return candidata ? <Chip tono="ok" title="Sin bloqueos, el Killer la dejo avanzar y esta entre las mejores con diversidad de cluster">Candidata al laboratorio</Chip> : <Chip tono="borde" title="Sin bloqueos no compensables">Sin bloqueos</Chip>;
  }
  return (
    <span className="acciones" style={{ gap: 4 }}>
      {b.map((x) => (
        <Chip key={x} tono="mal" title={EXPLICACION_BLOQUEO[x]}>
          {BLOQUEO[x]}
        </Chip>
      ))}
    </span>
  );
}

/* ---------------------------------------------------------------------
   Decisiones del Killer
   --------------------------------------------------------------------- */

function ListaComprobaciones({ comprobaciones }: { comprobaciones: Comprobacion[] }) {
  if (comprobaciones.length === 0) return null;
  const orden = { falla: 0, no_comprobable: 1, pasa: 2, no_aplica: 3 };
  const ordenadas = [...comprobaciones].sort((a, b) => orden[a.resultado] - orden[b.resultado]);
  return (
    <ul className="comprobaciones">
      {ordenadas.map((c, i) => {
        const r = RESULTADO_COMPROBACION[c.resultado];
        return (
          <li key={i}>
            <Chip tono={r.tono}>{r.etiqueta}</Chip>
            <span>
              <strong>{COMPROBACION_KILLER[c.comprobacion] ?? c.comprobacion}.</strong> {c.detalle}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function DecisionesKiller({ h, decisiones, ahora }: { h: Hipotesis; decisiones: Decision[]; ahora: number }) {
  const propias = decisiones.filter((d) => d.hipotesisId === h.id).sort((a, b) => b.fecha - a.fecha);
  const ultima = propias.find((d) => d.etapa === 'killer_1');
  return (
    <Seccion titulo="Hypothesis Killer y registro de decisiones" nota="El Killer (Opus 5, otra familia que el generador) pasa una lista fija de comprobaciones; la decision no la escribe el modelo: Rosa la deriva por regla. Descartar solo si falla la evidencia; reformular si falla algo arreglable; suspender si algo critico no se pudo comprobar. Una muestra de los descartes la audita otro modelo defendiendo la hipotesis.">
      {h.decisionKiller && (
        <div className="acciones" style={{ marginBottom: 8 }}>
          <Chip tono={DECISION_KILLER[h.decisionKiller].tono}>{DECISION_KILLER[h.decisionKiller].etiqueta}</Chip>
          <span className="meta">{DECISION_KILLER[h.decisionKiller].nota}</span>
        </div>
      )}
      {!h.decisionKiller && <p className="meta">El Killer todavia no juzgo esta version. Pasa por el en el paso de hipotesis de la siguiente iteracion, o al pedir una revision.</p>}
      {ultima && <ListaComprobaciones comprobaciones={ultima.comprobaciones} />}
      {ultima?.queHariaFalta && <p className="meta">Que haria falta para evaluarla: {ultima.queHariaFalta}</p>}
      {propias.length > 0 && (
        <details className="versiones">
          <summary>Historial de decisiones ({propias.length})</summary>
          <table className="tabla">
            <thead>
              <tr>
                <th>Cuando</th>
                <th>Etapa</th>
                <th>Version</th>
                <th>Decision</th>
                <th>Quien</th>
                <th>Motivo</th>
                <th>Auditoria</th>
              </tr>
            </thead>
            <tbody>
              {propias.map((d) => (
                <tr key={d.id}>
                  <td>
                    <Momento t={d.fecha} ahora={ahora} />
                  </td>
                  <td>{ETAPA_DECISION[d.etapa]}</td>
                  <td className="num">v{d.version}</td>
                  <td>{d.decision in DECISION_KILLER ? <Chip tono={DECISION_KILLER[d.decision as keyof typeof DECISION_KILLER].tono}>{DECISION_KILLER[d.decision as keyof typeof DECISION_KILLER].etiqueta}</Chip> : <Chip>{d.decision.replace(/_/g, ' ')}</Chip>}</td>
                  <td className="mono" style={{ fontSize: 12 }}>
                    {d.quien}
                  </td>
                  <td className="meta">{d.motivo}</td>
                  <td>{d.auditoria ? <Chip tono={d.auditoria.acuerdo ? 'ok' : 'mal'} title={d.auditoria.motivo}>{d.auditoria.acuerdo ? 'De acuerdo' : 'En desacuerdo'}</Chip> : <span className="meta">sin auditar</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </Seccion>
  );
}

/* ---------------------------------------------------------------------
   Analisis in silico
   --------------------------------------------------------------------- */

function Cifras({ titulo, cifras }: { titulo: string; cifras: Record<string, string> }) {
  const entradas = Object.entries(cifras);
  if (entradas.length === 0) return null;
  return (
    <div className="experimento-bloque">
      <h4>{titulo}</h4>
      <ul className="cifras">
        {entradas.map(([k, v]) => (
          <li key={k}>
            <strong>{k}:</strong> {v}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function EjecucionesInSilico({ h, estado, ahora }: { h: Hipotesis; estado: EstadoRosa; ahora: number }) {
  const runs = (estado.ejecuciones ?? []).filter((x) => x.hipotesisId === h.id).sort((a, b) => b.inicio - a.inicio);
  const planes = new Map((estado.planesAnalisis ?? []).map((p) => [p.id, p]));
  const inv = estado.investigaciones.find((i) => i.id === h.investigacionId);
  const datasets = (inv?.datasets ?? []).filter((d) => d.estado === 'aprobado' && d.procedencia?.hash);
  const [ds, setDs] = useState(datasets[0]?.id ?? '');
  const [pregunta, setPregunta] = useState('');
  const puerta = inv?.puertaReproduccion;
  const puertaOk = puerta ? puerta.estado === 'abierta' || puerta.estado === 'eximida' : false;
  return (
    <Seccion titulo="Analisis in silico" nota="Rosa congela un plan de analisis (sin ver las filas), escribe el codigo, lo ejecuta en un sandbox sin red con los datos en solo lectura, interpreta las cifras contra el umbral del plan y un auditor independiente (Killer II) dice si el analisis vale. Solo un analisis valido entra como evidencia.">
      {runs.length === 0 && <p className="meta">Sin analisis con datos todavia.</p>}
      {h.evidenciaSecuencial && (
        <div className="acciones">
          <Chip tono={h.evidenciaSecuencial.rechazaNula ? 'ok' : 'borde'} title="Producto de los e-valores (kappa p^(kappa-1)) de los analisis validos. Controla el error de tipo I aunque se sigan anadiendo pruebas (Popper, 2025).">
            Evidencia acumulada e = {h.evidenciaSecuencial.eAcumulado} sobre {h.evidenciaSecuencial.pruebas.length} {h.evidenciaSecuencial.pruebas.length === 1 ? 'prueba' : 'pruebas'}
          </Chip>
          <span className="meta">{h.evidenciaSecuencial.rechazaNula ? `Alcanza 1/alfa = ${Math.round(1 / h.evidenciaSecuencial.alfa)}: rechaza la hipotesis nula al ${Math.round(h.evidenciaSecuencial.alfa * 100)} %.` : `No alcanza 1/alfa = ${Math.round(1 / h.evidenciaSecuencial.alfa)}: la evidencia acumulada aun no rechaza la nula.`}</span>
        </div>
      )}
      {runs.map((run) => (
        <FichaEjecucion key={run.id} run={run} plan={planes.get(run.planId)} ahora={ahora} />
      ))}
      {datasets.length === 0 ? (
        <p className="meta">Para pedir un analisis hace falta un dataset aprobado con fichero y libro de procedencia (Objetivo y datos).</p>
      ) : (
        <div className="seccion">
          {!puertaOk && <p className="tono-aviso" style={{ fontSize: 13 }}>La puerta de reproduccion esta bloqueada ({puerta?.superadas ?? 0} de {puerta?.requeridas ?? 3}): el analisis quedara en "no ejecutado" hasta reproducir los analisis publicados o eximir la puerta con motivo.</p>}
          <div className="rejilla-2">
            <div className="campo">
              <label htmlFor="an-ds">Dataset</label>
              <select id="an-ds" value={ds} onChange={(e) => setDs(e.target.value)}>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.nombre}
                    {d.procedencia?.sintetico ? ' (sintetico)' : ''}
                  </option>
                ))}
              </select>
            </div>
            <div className="campo">
              <label htmlFor="an-preg">Que quieres que pruebe (vacio: la prediccion falsable)</label>
              <input id="an-preg" className="entrada" value={pregunta} placeholder="Diferencia de GFAP entre portadores y no portadores" onChange={(e) => setPregunta(e.target.value)} />
            </div>
          </div>
          <div className="acciones">
            <button type="button" className="btn" disabled={ds === ''} onClick={() => acciones.pedirAnalisis(h.id, ds, pregunta)}>
              Pedir analisis in silico
            </button>
            <span className="meta">Cuenta como evaluacion costosa (maximo {estado.politicas?.maxEvaluacionesCostosas ?? 5} por corrida).</span>
          </div>
        </div>
      )}
    </Seccion>
  );
}

export function FichaEjecucion({ run, plan, ahora }: { run: Ejecucion; plan: PlanAnalisis | undefined; ahora: number }) {
  const e = ESTADO_EJECUCION[run.estado];
  return (
    <div className={`tarjeta seccion ejecucion ejecucion-${run.estado}`}>
      <div className="acciones">
        <Chip tono={e.tono}>{e.etiqueta}</Chip>
        {run.interpretacion && <Chip tono={INTERPRETACION_EJECUCION[run.interpretacion.estado].tono}>{INTERPRETACION_EJECUCION[run.interpretacion.estado].etiqueta}</Chip>}
        {run.auditoria && (
          <Chip tono={VEREDICTO_AUDITORIA[run.auditoria.veredicto].tono} title={run.auditoria.motivo}>
            Auditor: {VEREDICTO_AUDITORIA[run.auditoria.veredicto].etiqueta}
          </Chip>
        )}
        <span className="meta">
          <Momento t={run.inicio} ahora={ahora} /> · {RUNTIME_EJECUCION[run.runtime]} · semilla {run.semilla} · datos {run.hashDatos.slice(0, 12) || 'sin hash'}
          {run.duracionS !== null ? ` · ${run.duracionS} s` : ''}
        </span>
      </div>
      {run.error && (run.estado === 'no_ejecutado' || run.estado === 'error_tecnico' || run.estado === 'tiempo_agotado') && <p className="tono-mal" style={{ fontSize: 13 }}>{run.error.split('\n').slice(-3).join(' ')}</p>}
      {plan && (
        <details className="versiones">
          <summary>Plan congelado {plan.hashPlan} ({plan.tipo}) el {new Date(plan.congeladoEn).toLocaleString('es')}</summary>
          <dl className="comprobacion">
            <dt>Pregunta</dt>
            <dd>{plan.pregunta}</dd>
            <dt>Variables</dt>
            <dd>{plan.variables.join('; ')}</dd>
            <dt>Poblacion</dt>
            <dd>{plan.poblacion}</dd>
            <dt>Prueba</dt>
            <dd>{plan.prueba}</dd>
            <dt>H0 / H1</dt>
            <dd>
              {plan.hipotesisNula} / {plan.hipotesisAlternativa} (alfa {plan.alpha})
            </dd>
            <dt>Efecto minimo y umbral</dt>
            <dd>
              {plan.tamanoEfectoMinimo}. Cuenta como efecto si: {plan.umbralEfecto}
            </dd>
            <dt>Baseline</dt>
            <dd>{plan.baseline}</dd>
            <dt>Control negativo</dt>
            <dd>{plan.controlNegativo}</dd>
            <dt>Multiplicidad</dt>
            <dd>{plan.correccionMultiplicidad}</dd>
            <dt>No evaluable si</dt>
            <dd>{plan.criterioNoEvaluable}</dd>
          </dl>
        </details>
      )}
      {run.interpretacion && <p style={{ fontSize: 13.5 }}>{run.interpretacion.resumen}</p>}
      {(run.skills?.length || run.entorno?.imagen) && (
        <p className="meta">
          {run.entorno?.imagen ? `Entorno ${run.entorno.imagen}` : ''}
          {run.skills?.length ? `${run.entorno?.imagen ? '; ' : ''}skills: ${run.skills.join(', ')}` : ''}
          {run.entorno?.paquetes?.length ? `; ${run.entorno.paquetes.slice(0, 6).map((p) => `${p.nombre} ${p.version}`).join(', ')}` : ''}
        </p>
      )}
      {run.repeticiones && run.repeticiones.length > 0 && (
        <p className="meta">
          Repeticiones con otras semillas: {run.repeticiones.map((r) => `semilla ${r.semilla}: ${Object.entries(r.resultados).slice(0, 3).map(([k, v]) => `${k}=${v}`).join(', ') || 'sin cifras'}`).join(' | ')}
        </p>
      )}
      <div className="conclusion-columnas">
        <Cifras titulo="Resultados" cifras={run.resultados} />
        <Cifras titulo="Baseline" cifras={run.baseline} />
        <Cifras titulo="Control negativo (etiquetas barajadas)" cifras={run.controlNegativo} />
      </div>
      {run.auditoria && (
        <div className="experimento-bloque">
          <h4>Auditoria independiente (Killer II)</h4>
          <p className="meta">{run.auditoria.motivo}</p>
          <ListaComprobaciones comprobaciones={run.auditoria.comprobaciones} />
        </div>
      )}
      {run.codigo && (
        <details className="versiones">
          <summary>Codigo ejecutado</summary>
          <pre className="registro">{run.codigo}</pre>
        </details>
      )}
      {run.salida && (
        <details className="versiones">
          <summary>Salida del sandbox</summary>
          <pre className="registro">{run.salida}</pre>
        </details>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------------
   Puerta de reproduccion y reproducciones
   --------------------------------------------------------------------- */

/** Tres analisis publicos y reproducibles del Alzheimer, del mas barato al
 *  mas caro, con la cifra publicada y una tolerancia razonable. Salen de la
 *  investigacion del 11 de septiembre de 2026 (INVESTIGACION-ROSA2018.md). */
export const REPRODUCCIONES_SUGERIDAS: { referencia: string; doi: string; descripcion: string; cifraPublicada: string; valorPublicado: number; tolerancia: number; dataset: string }[] = [
  { referencia: 'Blalock et al., 2004 (PNAS)', doi: '10.1073/pnas.0308512100', descripcion: 'GEO GSE1297, hipocampo, 31 arrays: correlacion de la expresion de cada gen con MMSE; recall del conjunto MSigDB BLALOCK_ALZHEIMERS_DISEASE_INCIPIENT_UP al mismo umbral', cifraPublicada: 'recall del conjunto UP (fraccion recuperada)', valorPublicado: 1.0, tolerancia: 0.4, dataset: 'GSE1297' },
  { referencia: 'Marcus et al., 2007 (OASIS-1)', doi: '10.1162/jocn.2007.19.9.1498', descripcion: 'OASIS-1, 416 sujetos: diferencia de volumen cerebral normalizado (nWBV) entre CDR 0 y CDR 0,5 o mayor; misma direccion y p < 0,01', cifraPublicada: 'p-valor de la diferencia de nWBV por CDR (menor que 0,01)', valorPublicado: 0.005, tolerancia: 1.0, dataset: 'OASIS-1' },
  { referencia: 'Gabitto et al., 2024 (SEA-AD, Nat Neurosci)', doi: '10.1038/s41593-024-01774-5', descripcion: 'SEA-AD MTG, proporciones por donante con anotaciones de los autores: numero de supertipos con cambio credible frente al CPS (scCODA, probabilidad de inclusion > 0,8)', cifraPublicada: 'supertipos con cambio credible (36 de 139)', valorPublicado: 36, tolerancia: 0.2, dataset: 'SEA-AD' },
];

export function PuertaYReproducciones({ inv, estado, ahora }: { inv: Investigacion; estado: EstadoRosa; ahora: number }) {
  const puerta = inv.puertaReproduccion ?? { requeridas: 3, superadas: 0, estado: 'bloqueada' as const, eximidaPor: null, motivo: '', fecha: null };
  const reps = (estado.reproducciones ?? []).filter((r) => r.investigacionId === inv.id);
  const datasets = inv.datasets.filter((d) => d.procedencia?.hash);
  const [ds, setDs] = useState(datasets[0]?.id ?? '');
  const [d, setD] = useState({ referencia: '', doi: '', descripcion: '', cifraPublicada: '', valorPublicado: '', tolerancia: '0.1' });
  const [error, setError] = useState<string | null>(null);
  const tono = puerta.estado === 'abierta' ? 'ok' : puerta.estado === 'eximida' ? 'aviso' : 'mal';
  return (
    <Seccion
      titulo="Puerta de reproduccion"
      nota="Antes de descubrir nada con datos, Rosa tiene que reproducir analisis ya publicados dentro de una tolerancia fijada de antemano. Si no lo consigue, un resultado nuevo no se distingue de un error del pipeline. Una persona puede eximirla dejando el motivo; queda como cambio de politica."
      acciones={
        puerta.estado === 'eximida' ? (
          <button type="button" className="btn btn-s" onClick={() => acciones.cerrarPuerta(inv.id)}>
            Volver a exigirla
          </button>
        ) : (
          <Confirmar etiqueta="Eximir la puerta" pregunta="Es una excepcion de politica (nivel 3). Queda en el registro de aprendizaje con tu nombre y el motivo." pedirTexto={{ etiqueta: 'Motivo', marcador: 'Demostracion con datos sinteticos; no se afirma nada cientifico' }} onConfirmar={(m) => acciones.eximirPuerta(inv.id, m)} />
        )
      }
    >
      <div className="acciones">
        <Chip tono={tono}>
          {puerta.estado === 'abierta' ? 'Abierta' : puerta.estado === 'eximida' ? `Eximida por ${puerta.eximidaPor}` : 'Bloqueada'} · {puerta.superadas} de {puerta.requeridas} reproducidas
        </Chip>
        {puerta.estado === 'eximida' && <span className="meta">Motivo: {puerta.motivo}</span>}
      </div>
      {reps.length > 0 && (
        <table className="tabla">
          <thead>
            <tr>
              <th>Referencia</th>
              <th>Que se reproduce</th>
              <th className="num">Publicado</th>
              <th className="num">Obtenido</th>
              <th className="num">Tolerancia</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {reps.map((r) => (
              <FilaReproduccion key={r.id} r={r} />
            ))}
          </tbody>
        </table>
      )}
      {datasets.length === 0 ? (
        <p className="meta">Sube primero el dataset publico del analisis que quieres reproducir (por ejemplo GSE1297, OASIS-1 o SEA-AD).</p>
      ) : (
        <div className="seccion">
          <p className="campo-etiqueta">Registrar un analisis publicado para reproducir</p>
          <div className="acciones">
            {REPRODUCCIONES_SUGERIDAS.map((s) => (
              <button key={s.doi} type="button" className="btn btn-s" title={s.descripcion} onClick={() => setD({ referencia: s.referencia, doi: s.doi, descripcion: s.descripcion, cifraPublicada: s.cifraPublicada, valorPublicado: String(s.valorPublicado), tolerancia: String(s.tolerancia) })}>
                {s.dataset}: {s.referencia}
              </button>
            ))}
          </div>
          <div className="rejilla-2">
            <div className="campo">
              <label htmlFor="rep-ds">Dataset</label>
              <select id="rep-ds" value={ds} onChange={(e) => setDs(e.target.value)}>
                {datasets.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.nombre}
                  </option>
                ))}
              </select>
            </div>
            <div className="campo">
              <label htmlFor="rep-ref">Referencia</label>
              <input id="rep-ref" value={d.referencia} onChange={(e) => setD({ ...d, referencia: e.target.value })} placeholder="Blalock et al., 2004" />
            </div>
          </div>
          <div className="campo">
            <label htmlFor="rep-desc">Que se reproduce exactamente</label>
            <textarea id="rep-desc" rows={2} value={d.descripcion} onChange={(e) => setD({ ...d, descripcion: e.target.value })} />
          </div>
          <div className="rejilla-3">
            <div className="campo">
              <label htmlFor="rep-cifra">Cifra publicada (nombre)</label>
              <input id="rep-cifra" value={d.cifraPublicada} onChange={(e) => setD({ ...d, cifraPublicada: e.target.value })} />
            </div>
            <div className="campo">
              <label htmlFor="rep-valor">Valor publicado</label>
              <input id="rep-valor" value={d.valorPublicado} onChange={(e) => setD({ ...d, valorPublicado: e.target.value })} />
            </div>
            <div className="campo">
              <label htmlFor="rep-tol">Tolerancia relativa (0,1 = 10 %)</label>
              <input id="rep-tol" value={d.tolerancia} onChange={(e) => setD({ ...d, tolerancia: e.target.value })} />
            </div>
          </div>
          <div className="acciones">
            <button
              type="button"
              className="btn btn-primario btn-s"
              disabled={ds === ''}
              onClick={() => {
                const id = acciones.anadirReproduccion(inv.id, ds, { referencia: d.referencia, doi: d.doi, descripcion: d.descripcion, cifraPublicada: d.cifraPublicada, valorPublicado: Number(d.valorPublicado.replace(',', '.')), tolerancia: Number(d.tolerancia.replace(',', '.')) });
                setError(id ? null : 'Faltan la referencia, la descripcion, un valor numerico o una tolerancia entre 0 y 1.');
                if (id) setD({ referencia: '', doi: '', descripcion: '', cifraPublicada: '', valorPublicado: '', tolerancia: '0.1' });
              }}
            >
              Registrar y reproducir
            </button>
            {error && <span className="tono-mal">{error}</span>}
          </div>
        </div>
      )}
      <p className="meta">Ultimo cambio de la puerta: {puerta.fecha ? <Momento t={puerta.fecha} ahora={ahora} /> : 'nunca'}.</p>
    </Seccion>
  );
}

function FilaReproduccion({ r }: { r: Reproduccion }) {
  const e = ESTADO_REPRODUCCION[r.estado];
  return (
    <tr>
      <td>
        {r.referencia}
        {r.doi && (
          <>
            {' '}
            <a className="enlace" href={`https://doi.org/${r.doi}`} target="_blank" rel="noopener noreferrer">
              doi
            </a>
          </>
        )}
      </td>
      <td className="meta">{r.descripcion}</td>
      <td className="num">{r.valorPublicado}</td>
      <td className="num">{r.valorObtenido ?? ''}</td>
      <td className="num">{Math.round(r.tolerancia * 100)} %</td>
      <td>
        <Chip tono={e.tono}>{e.etiqueta}</Chip>
      </td>
    </tr>
  );
}

/* ---------------------------------------------------------------------
   Libro de procedencia de un dataset
   --------------------------------------------------------------------- */

export function LibroDeProcedencia({ inv, d }: { inv: Investigacion; d: Dataset }) {
  const p = d.procedencia;
  const [editando, setEditando] = useState(false);
  const [f, setF] = useState(() => ({ origen: p?.origen ?? '', version: p?.version ?? '', licencia: p?.licencia ?? '', permisos: p?.permisos ?? '', cohorte: p?.cohorte ?? '', restriccionIA: p?.restriccionIA ?? '', acceso: p?.acceso ?? 'propio', usoIAAutorizado: p?.usoIAAutorizado ?? 'desconocido', sintetico: p?.sintetico ?? false, permiteLlmTerceros: p?.permiteLlmTerceros ?? false, clase: p?.clase ?? 'observacion_original', diccionario: (p?.diccionario ?? []).map((c) => ({ ...c })) }));
  if (!p) return <p className="meta">Sin fichero: los datasets del catalogo no tienen libro de procedencia hasta que se sube el fichero.</p>;
  if (!editando) {
    return (
      <div className="procedencia-ds">
        <div className="acciones">
          <Chip tono={USO_IA[p.usoIAAutorizado].tono}>{USO_IA[p.usoIAAutorizado].etiqueta}</Chip>
          <Chip tono={p.permiteLlmTerceros ? 'aviso' : 'ok'} title="Si las filas individuales pueden salir hacia el AI Gateway. Con datos controlados esta prohibido (NIH NOT-OD-25-081).">
            {p.permiteLlmTerceros ? 'Filas pueden ir al modelo' : 'Al modelo solo agregados'}
          </Chip>
          {p.sintetico && <Chip tono="aviso">Sintetico: no cuenta como evidencia</Chip>}
          <Chip tono="borde">{CLASE_EVIDENCIA[p.clase].etiqueta}</Chip>
          <Chip tono="borde">{ACCESO_DATASET[p.acceso]}</Chip>
          <button type="button" className="btn btn-s" style={{ marginLeft: 'auto' }} onClick={() => setEditando(true)}>
            Completar el libro de procedencia
          </button>
        </div>
        <dl className="comprobacion">
          <dt>Origen</dt>
          <dd>{p.origen || <span className="tono-mal">sin declarar</span>}</dd>
          <dt>Version</dt>
          <dd>{p.version || 'sin declarar'}</dd>
          <dt>Licencia</dt>
          <dd>{p.licencia || <span className="tono-mal">sin declarar</span>}</dd>
          <dt>Permisos</dt>
          <dd>{p.permisos || 'sin declarar'}</dd>
          <dt>Cohorte</dt>
          <dd>{p.cohorte || 'sin declarar'}</dd>
          <dt>Fichero</dt>
          <dd className="mono" style={{ fontSize: 12 }}>
            {p.fichero} · {p.filas} filas · sha256 {p.hash.slice(0, 16)}
          </dd>
          {p.restriccionIA && (
            <>
              <dt>Clausula de IA del acuerdo</dt>
              <dd className="meta">{p.restriccionIA}</dd>
            </>
          )}
        </dl>
        {p.diccionario.length > 0 && (
          <details className="versiones">
            <summary>Diccionario de columnas ({p.diccionario.length}; {p.diccionario.filter((c) => c.descripcion.trim() === '').length} sin descripcion)</summary>
            <table className="tabla">
              <tbody>
                {p.diccionario.map((c) => (
                  <tr key={c.columna}>
                    <td className="mono">{c.columna}</td>
                    <td>{c.tipo}</td>
                    <td>{c.unidad}</td>
                    <td className={c.descripcion ? 'meta' : 'tono-mal'}>{c.descripcion || 'sin descripcion'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        )}
      </div>
    );
  }
  const campo = (k: 'origen' | 'version' | 'licencia' | 'permisos' | 'cohorte' | 'restriccionIA', label: string, marcador: string) => (
    <div className="campo" key={k}>
      <label htmlFor={`pd-${k}`}>{label}</label>
      <input id={`pd-${k}`} value={f[k]} placeholder={marcador} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
    </div>
  );
  return (
    <div className="procedencia-ds seccion">
      <p className="meta">Sin origen, licencia y uso con IA autorizado el contrato no se puede aprobar. El hash y las filas los fija el servidor y no se editan.</p>
      <div className="rejilla-2">
        {campo('origen', 'Origen (portal, laboratorio, publicacion)', 'GEO GSE1297')}
        {campo('version', 'Version del dataset', 'v1, 2004')}
        {campo('licencia', 'Licencia o condiciones de uso', 'CC-BY 4.0; Allen Terms of Use')}
        {campo('permisos', 'Permisos y acuerdo de uso (id, fecha)', 'DUC Synapse v8.2, aprobado 2026-09-01')}
        {campo('cohorte', 'Cohorte de origen', 'ADNI')}
        {campo('restriccionIA', 'Clausula de IA del acuerdo (literal)', 'Use of AI tools must be described in your IDU')}
      </div>
      <div className="rejilla-3">
        <div className="campo">
          <label htmlFor="pd-acceso">Acceso</label>
          <select id="pd-acceso" value={f.acceso} onChange={(e) => setF({ ...f, acceso: e.target.value as ProcedenciaDataset['acceso'] })}>
            {(Object.keys(ACCESO_DATASET) as ProcedenciaDataset['acceso'][]).map((a) => (
              <option key={a} value={a}>
                {ACCESO_DATASET[a]}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="pd-ia">Uso con IA autorizado</label>
          <select id="pd-ia" value={f.usoIAAutorizado} onChange={(e) => setF({ ...f, usoIAAutorizado: e.target.value as ProcedenciaDataset['usoIAAutorizado'] })}>
            <option value="si">Si, el acuerdo lo permite</option>
            <option value="no">No</option>
            <option value="desconocido">Sin confirmar</option>
          </select>
        </div>
        <div className="campo">
          <label htmlFor="pd-clase">Clase de evidencia</label>
          <select id="pd-clase" value={f.clase} onChange={(e) => setF({ ...f, clase: e.target.value as ProcedenciaDataset['clase'] })}>
            {(Object.keys(CLASE_EVIDENCIA) as ProcedenciaDataset['clase'][]).map((c) => (
              <option key={c} value={c}>
                {CLASE_EVIDENCIA[c].etiqueta}
              </option>
            ))}
          </select>
        </div>
      </div>
      <label className="interruptor">
        <input type="checkbox" checked={f.sintetico} onChange={(e) => setF({ ...f, sintetico: e.target.checked, clase: e.target.checked ? 'prediccion' : f.clase })} />
        Es sintetico (no cuenta como evidencia; se etiqueta siempre)
      </label>
      <label className="interruptor">
        <input type="checkbox" checked={f.permiteLlmTerceros} onChange={(e) => setF({ ...f, permiteLlmTerceros: e.target.checked })} />
        Las filas individuales pueden enviarse a un modelo de terceros (solo datos abiertos o sinteticos; con datos controlados esta prohibido)
      </label>
      {f.diccionario.length > 0 && (
        <div>
          <p className="campo-etiqueta">Diccionario: describe cada columna</p>
          <table className="tabla">
            <tbody>
              {f.diccionario.map((c, i) => (
                <tr key={c.columna}>
                  <td className="mono">{c.columna}</td>
                  <td>
                    <select className="entrada entrada-s" value={c.tipo} onChange={(e) => setF({ ...f, diccionario: f.diccionario.map((x, j) => (j === i ? { ...x, tipo: e.target.value as typeof x.tipo } : x)) })} aria-label={`Tipo de ${c.columna}`}>
                      {(['numerica', 'categorica', 'fecha', 'texto', 'identificador'] as const).map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input className="entrada entrada-s" value={c.unidad} placeholder="unidad" onChange={(e) => setF({ ...f, diccionario: f.diccionario.map((x, j) => (j === i ? { ...x, unidad: e.target.value } : x)) })} aria-label={`Unidad de ${c.columna}`} />
                  </td>
                  <td>
                    <input className="entrada entrada-s" value={c.descripcion} placeholder="que mide" onChange={(e) => setF({ ...f, diccionario: f.diccionario.map((x, j) => (j === i ? { ...x, descripcion: e.target.value } : x)) })} aria-label={`Descripcion de ${c.columna}`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="acciones">
        <button
          type="button"
          className="btn btn-primario btn-s"
          onClick={() => {
            acciones.actualizarProcedenciaDataset(inv.id, d.id, f);
            setEditando(false);
          }}
        >
          Guardar el libro de procedencia
        </button>
        <button type="button" className="btn btn-fantasma btn-s" onClick={() => setEditando(false)}>
          Cancelar
        </button>
      </div>
    </div>
  );
}

export function SubirDataset({ inv }: { inv: Investigacion }) {
  const [fichero, setFichero] = useState<File | null>(null);
  const [nombre, setNombre] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [sintetico, setSintetico] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="tarjeta seccion">
      <p className="campo-etiqueta">Subir un dataset con fichero</p>
      <p className="meta">CSV, TSV o JSON (lista de objetos), hasta 200 MB. El servidor calcula el hash, cuenta filas y columnas, detecta valores centinela y prepara el diccionario para que lo completes. Ninguna fila pasa por un modelo al subir.</p>
      <div className="rejilla-2">
        <div className="campo">
          <label htmlFor="ds-fich">Fichero</label>
          <input id="ds-fich" type="file" accept=".csv,.tsv,.txt,.json" onChange={(e) => setFichero(e.target.files?.[0] ?? null)} />
        </div>
        <div className="campo">
          <label htmlFor="ds-nom">Nombre</label>
          <input id="ds-nom" value={nombre} placeholder="GSE1297 hipocampo" onChange={(e) => setNombre(e.target.value)} />
        </div>
      </div>
      <div className="campo">
        <label htmlFor="ds-desc">Descripcion</label>
        <input id="ds-desc" value={descripcion} placeholder="Expresion por gen y sujeto, con MMSE y NFT" onChange={(e) => setDescripcion(e.target.value)} />
      </div>
      <label className="interruptor">
        <input type="checkbox" checked={sintetico} onChange={(e) => setSintetico(e.target.checked)} />
        Es sintetico (para probar el pipeline; nunca cuenta como evidencia)
      </label>
      <div className="acciones">
        <button
          type="button"
          className="btn btn-primario"
          disabled={!fichero || subiendo}
          onClick={async () => {
            if (!fichero) return;
            setSubiendo(true);
            const err = await acciones.subirDataset(inv.id, fichero, nombre || fichero.name, descripcion, sintetico);
            setSubiendo(false);
            setError(err);
            if (!err) {
              setFichero(null);
              setNombre('');
              setDescripcion('');
            }
          }}
        >
          {subiendo ? 'Subiendo...' : 'Subir y perfilar'}
        </button>
        {error && <span className="tono-mal">{error}</span>}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------
   Registro de aprendizaje
   --------------------------------------------------------------------- */

export function RegistroAprendizaje({ estado, ahora }: { estado: EstadoRosa; ahora: number }) {
  const cambios = [...(estado.aprendizaje ?? [])].sort((a, b) => b.fecha - a.fecha);
  const [nivel, setNivel] = useState<1 | 2 | 3>(2);
  const visibles = cambios.filter((c) => c.nivel === nivel);
  return (
    <Seccion titulo="Registro de aprendizaje" nota="Todo lo que Rosa cambia al aprender, en tres niveles. El nivel 1 es automatico; el nivel 2 lo propone Rosa y lo promueve una persona tras evaluarlo sobre el conjunto reservado; el nivel 3 solo lo cambia una persona.">
      <div className="segmentos" role="group" aria-label="Nivel">
        {([1, 2, 3] as const).map((n) => (
          <button key={n} type="button" aria-pressed={nivel === n} onClick={() => setNivel(n)} title={NIVEL_APRENDIZAJE[n].nota}>
            {NIVEL_APRENDIZAJE[n].etiqueta} ({cambios.filter((c) => c.nivel === n).length})
          </button>
        ))}
      </div>
      <p className="meta">{NIVEL_APRENDIZAJE[nivel].nota}</p>
      {visibles.length === 0 ? (
        <p className="meta">Nada registrado en este nivel.</p>
      ) : (
        <ul className="lista-limpia aprendizaje">
          {visibles.slice(0, 40).map((c) => (
            <FilaAprendizaje key={c.id} c={c} ahora={ahora} />
          ))}
        </ul>
      )}
    </Seccion>
  );
}

function FilaAprendizaje({ c, ahora }: { c: CambioAprendizaje; ahora: number }) {
  const e = ESTADO_APRENDIZAJE[c.estado];
  const ev = c.evaluacion;
  return (
    <li>
      <div style={{ flex: 1 }}>
        <div className="acciones" style={{ gap: 6 }}>
          <Chip tono={e.tono}>{e.etiqueta}</Chip>
          <Chip tono="borde">{TIPO_APRENDIZAJE[c.tipo]}</Chip>
          <span className="meta">
            {c.quien} · <Momento t={c.fecha} ahora={ahora} />
            {c.resueltoPor && c.resueltoPor !== c.quien ? ` · resuelto por ${c.resueltoPor}` : ''}
          </span>
        </div>
        <p style={{ fontSize: 13.5, marginTop: 4 }}>{c.descripcion}</p>
        {ev && (
          <p className="meta">
            {ev.casos > 0 ? `Evaluado sobre ${ev.casos} casos (${ev.conjunto}): acuerdo con las personas ${ev.antes ?? '?'} antes, ${ev.despues ?? '?'} despues. ` : ''}
            {ev.nota}
          </p>
        )}
      </div>
      {c.nivel === 2 && (c.estado === 'propuesto' || c.estado === 'evaluado') && (
        <div className="acciones">
          {c.tipo === 'criterio' && (
            <button type="button" className="btn btn-s" onClick={() => acciones.evaluarAprendizaje(c.id)} title="Corre el Killer con y sin este criterio sobre las hipotesis que ya decidio una persona y mide el acuerdo. Gasta llamadas al juez.">
              Evaluar
            </button>
          )}
          <button type="button" className="btn btn-primario btn-s" onClick={() => acciones.promoverAprendizaje(c.id)}>
            Promover
          </button>
          <Confirmar etiqueta="Revertir" pregunta="El cambio no se aplica y queda registrado como revertido." pedirTexto={{ etiqueta: 'Motivo', marcador: 'Empeora el acuerdo con las decisiones humanas' }} onConfirmar={(m) => acciones.revertirAprendizaje(c.id, m)} />
        </div>
      )}
      {c.nivel === 2 && c.estado === 'promovido' && <Confirmar etiqueta="Revertir" pregunta="Se quita el criterio y queda registrado." pedirTexto={{ etiqueta: 'Motivo', marcador: 'Sesga al Killer contra hipotesis de una cohorte' }} onConfirmar={(m) => acciones.revertirAprendizaje(c.id, m)} />}
    </li>
  );
}

export function Politicas({ politicas }: { politicas: Record<string, number> | undefined }) {
  const filas: { clave: string; etiqueta: string; nota: string }[] = [
    { clave: 'maxHipotesisVivas', etiqueta: 'Hipotesis vivas por mision', nota: 'Al llegar, Rosa deja de generar hasta que se decidan algunas.' },
    { clave: 'maxEvaluacionesCostosas', etiqueta: 'Evaluaciones costosas (analisis con datos) por corrida', nota: 'Cada una gasta codigo, sandbox y auditoria.' },
    { clave: 'maxCandidatos', etiqueta: 'Candidatas al laboratorio por ciclo', nota: 'Entre cero y esto. Cero es un resultado valido.' },
    { clave: 'maxReformulaciones', etiqueta: 'Reformulaciones por hipotesis', nota: 'Despues, se descarta en este contexto.' },
    { clave: 'reproduccionesRequeridas', etiqueta: 'Analisis publicados a reproducir antes de descubrir', nota: 'La puerta de reproduccion.' },
    { clave: 'fraccionDescartesAuditados', etiqueta: 'Fraccion de descartes del Killer auditados', nota: 'Con otro metodo y otra familia de modelo.' },
    { clave: 'segundosMaxEjecucion', etiqueta: 'Segundos maximos por ejecucion en el sandbox', nota: 'Pasado el tiempo es un error tecnico, no un resultado nulo.' },
    { clave: 'memoriaMaxEjecucionMb', etiqueta: 'Memoria maxima del sandbox (MB)', nota: '' },
    { clave: 'presupuestoUsd', etiqueta: 'Presupuesto por defecto de una mision (USD estimados)', nota: 'Se fija por mision al aprobarla.' },
    { clave: 'presupuestoHoras', etiqueta: 'Presupuesto por defecto de una mision (horas)', nota: '' },
  ];
  return (
    <Seccion titulo="Politicas" nota="Los limites del sistema viven en el codigo del servidor (rosa/politicas.py), no en este estado: ningun agente puede editarlos y cada cambio es un commit que queda en la version de Rosa de cada corrida. Aqui solo se leen.">
      {!politicas ? (
        <p className="meta">Sin servidor no hay politicas que leer.</p>
      ) : (
        <table className="tabla">
          <tbody>
            {filas.map((f) => (
              <tr key={f.clave}>
                <td>{f.etiqueta}</td>
                <td className="num">{politicas[f.clave] ?? ''}</td>
                <td className="meta">{f.nota}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Seccion>
  );
}

/** Las candidatas al laboratorio y por que las demas no lo son. */
export function Candidatas({ inv, estado, candidatas, noCandidatas }: { inv: Investigacion; estado: EstadoRosa; candidatas: Hipotesis[]; noCandidatas: { h: Hipotesis; bloqueos: NonNullable<Hipotesis['bloqueos']>; motivo: string }[] }) {
  return (
    <Seccion titulo="Candidatas al laboratorio" nota={`Hasta ${estado.politicas?.maxCandidatos ?? 3} por ciclo, elegidas entre las que el Killer dejo avanzar y no tienen bloqueos no compensables, por Elo y sin repetir cluster mientras haya otros. Cero candidatas es un resultado legitimo: significa abstenerse.`}>
      {candidatas.length === 0 ? <p className="meta">Hoy ninguna hipotesis cumple: Rosa se abstiene de proponer nada al laboratorio.</p> : (
        <ol className="lista-limpia">
          {candidatas.map((h) => (
            <li key={h.id}>
              <a className="enlace" href={rutaDe(inv.id, 'hipotesis', h.id)}>
                {h.titulo}
              </a>
              <span className="meta">
                {h.cluster} · Elo {h.elo}
              </span>
            </li>
          ))}
        </ol>
      )}
      {noCandidatas.length > 0 && (
        <details className="versiones">
          <summary>Por que las demas no son candidatas ({noCandidatas.length})</summary>
          <ul className="lista-limpia">
            {noCandidatas.map(({ h, bloqueos, motivo }) => (
              <li key={h.id}>
                <div>
                  <a className="enlace" href={rutaDe(inv.id, 'hipotesis', h.id)}>
                    {h.titulo}
                  </a>
                  <div className="acciones" style={{ gap: 4, marginTop: 4 }}>
                    {bloqueos.map((b) => (
                      <Chip key={b} tono="mal" title={EXPLICACION_BLOQUEO[b]}>
                        {BLOQUEO[b]}
                      </Chip>
                    ))}
                    {motivo && <span className="meta">{motivo}</span>}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}
    </Seccion>
  );
}


// ---------------------------------------------------------------------------
// Protocolo real, desviaciones, identidad de muestras y enmiendas fechadas
// ---------------------------------------------------------------------------

const ETIQUETA_CAMPO: Record<CampoEnmendable, string> = {
  protocolo: 'Protocolo',
  ensayo: 'Ensayo',
  controles: 'Controles',
  tamanoMuestral: 'Tamaño muestral',
  confirma: 'Criterio de confirmacion',
  refuta: 'Criterio de refutacion',
  analisisPedido: 'Analisis pedido',
};

/** Lo que se planeo frente a lo que se hizo. El prerregistro queda congelado;
 *  cambiarlo despues es una enmienda con fecha, autor y motivo, y lo que el
 *  laboratorio ejecuto de verdad se registra aparte con sus desviaciones y la
 *  identidad de las muestras. El juez lee las tres cosas al evaluar los datos. */
export function ProtocoloYEnmiendas({ h, ahora }: { h: Hipotesis; ahora: number }) {
  const x = h.experimento;
  const [texto, setTexto] = useState(x?.protocoloReal?.texto ?? '');
  const [desviaciones, setDesviaciones] = useState(x?.protocoloReal?.desviaciones ?? '');
  const [muestras, setMuestras] = useState(x?.protocoloReal?.identidadMuestras ?? '');
  const [campo, setCampo] = useState<CampoEnmendable>('confirma');
  const [despues, setDespues] = useState('');
  const [motivo, setMotivo] = useState('');
  if (!x || x.estado === 'propuesto') return null;
  const puedeEnmendar = Boolean(x.prerregistradoEn) && !x.resultado;
  return (
    <div className="seccion">
      <h4>Protocolo real y enmiendas</h4>
      {(x.enmiendas ?? []).length > 0 && (
        <ul className="lista-plana">
          {(x.enmiendas ?? []).map((en, i) => (
            <li key={i}>
              <strong>Enmienda {i + 1}</strong> <Momento t={en.fecha} ahora={ahora} /> por {en.quien}, {ETIQUETA_CAMPO[en.campo].toLowerCase()}: <span className="meta">"{en.antes.slice(0, 160) || 'vacio'}"</span> pasa a "{en.despues.slice(0, 160)}". Motivo: {en.motivo}
            </li>
          ))}
        </ul>
      )}
      {puedeEnmendar ? (
        <div className="campo-fila">
          <select className="entrada" value={campo} onChange={(e) => setCampo(e.target.value as CampoEnmendable)} aria-label="Campo a enmendar">
            {CAMPOS_ENMENDABLES.map((c) => (
              <option key={c} value={c}>
                {ETIQUETA_CAMPO[c]}
              </option>
            ))}
          </select>
          <input className="entrada" value={despues} placeholder={`Texto nuevo (ahora: ${(x[campo] ?? '').slice(0, 60) || 'vacio'})`} onChange={(e) => setDespues(e.target.value)} aria-label="Texto nuevo" />
          <input className="entrada" value={motivo} placeholder="Motivo de la enmienda" onChange={(e) => setMotivo(e.target.value)} aria-label="Motivo" />
          <button
            type="button"
            className="btn"
            disabled={despues.trim() === '' || motivo.trim() === ''}
            onClick={() => {
              acciones.enmendarExperimento(h.id, campo, despues, motivo);
              setDespues('');
              setMotivo('');
            }}
          >
            Registrar enmienda fechada
          </button>
        </div>
      ) : (
        <p className="meta">{x.resultado ? 'Con datos ya evaluados el prerregistro no se enmienda: los criterios ya se aplicaron.' : 'Las enmiendas se registran despues de congelar el prerregistro.'}</p>
      )}
      {x.protocoloReal && (
        <p className="meta">
          Protocolo real registrado <Momento t={x.protocoloReal.registradoEn} ahora={ahora} /> por {x.protocoloReal.quien}. Desviaciones: {x.protocoloReal.desviaciones || 'ninguna declarada'}. Muestras: {x.protocoloReal.identidadMuestras || 'no declaradas'}.
        </p>
      )}
      <div className="campo">
        <label htmlFor={`pr-texto-${h.id}`}>Protocolo realmente ejecutado</label>
        <textarea id={`pr-texto-${h.id}`} className="entrada" rows={3} value={texto} placeholder="Lo que el laboratorio hizo, paso a paso, aunque coincida con lo planeado" onChange={(e) => setTexto(e.target.value)} />
      </div>
      <div className="campo">
        <label htmlFor={`pr-desv-${h.id}`}>Desviaciones respecto al prerregistro</label>
        <input id={`pr-desv-${h.id}`} className="entrada" value={desviaciones} placeholder="Ninguna, o que cambio y por que (n menor, otro reactivo, otro tiempo)" onChange={(e) => setDesviaciones(e.target.value)} />
      </div>
      <div className="campo">
        <label htmlFor={`pr-mu-${h.id}`}>Identidad de las muestras</label>
        <input id={`pr-mu-${h.id}`} className="entrada" value={muestras} placeholder="Lote, linea celular, cohorte y fechas de recogida" onChange={(e) => setMuestras(e.target.value)} />
      </div>
      <div className="acciones">
        <button type="button" className="btn" disabled={texto.trim() === ''} onClick={() => acciones.registrarProtocoloReal(h.id, { texto, desviaciones, identidadMuestras: muestras })}>
          {x.protocoloReal ? 'Actualizar protocolo real' : 'Registrar protocolo real'}
        </button>
        {x.resultado && <span className="meta">Si lo registras ahora, Rosa vuelve a evaluar los datos con esta informacion.</span>}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Gobierno de las areas y jerarquia programa / areas / campanas / preguntas
// ---------------------------------------------------------------------------

function FilaArea({ inv, a, corridas }: { inv: Investigacion; a: AreaInvestigacion; corridas: Corrida[] }) {
  const [condicion, setCondicion] = useState(a.condicionReapertura ?? '');
  const campana = corridas.find((c) => c.id === a.corridaId);
  return (
    <tr>
      <td>
        <strong style={{ fontSize: 13 }}>{a.titulo}</strong>
        <p className="meta">{a.valorIntervencion}</p>
        {a.estado === 'pausada' && a.condicionReapertura && <p className="meta">Se reabre si: {a.condicionReapertura}</p>}
        {(a.historial?.length ?? 0) > 0 && (
          <details className="versiones">
            <summary>Historial ({a.historial!.length})</summary>
            <ul className="lista-plana">
              {a.historial!.map((hi, i) => (
                <li key={i} className="meta">
                  {new Date(hi.fecha).toLocaleDateString('es')} {hi.quien}: {hi.de === hi.a ? hi.motivo : `${hi.de.replace('_', ' ')} a ${hi.a.replace('_', ' ')}${hi.motivo ? ` (${hi.motivo})` : ''}`}
                </li>
              ))}
            </ul>
          </details>
        )}
      </td>
      <td>{a.familiaMecanismo}</td>
      <td className="meta">{a.relevancia}</td>
      <td className="meta">{a.comprobabilidad}</td>
      <td className="meta">
        {a.coste}; {a.demora}
        {a.dependeDe ? `; depende de ${a.dependeDe}` : ''}
      </td>
      <td>
        <Chip tono={a.estado === 'elegida' ? 'ok' : a.estado === 'sin_explorar' ? 'aviso' : 'borde'}>{a.estado.replace('_', ' ')}</Chip>
        {campana && <p className="meta">Campana {campana.numero}</p>}
      </td>
      <td>
        <div className="acciones" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 6 }}>
          {a.estado !== 'elegida' && (
            <button type="button" className="btn btn-pequeno" onClick={() => acciones.cambiarEstadoArea(inv.id, a.id, 'elegida', '', undefined, a.estado === 'pausada' ? 'reabierta' : 'elegida')}>
              {a.estado === 'pausada' ? 'Reabrir' : 'Elegir'}
            </button>
          )}
          {a.estado !== 'pausada' && (
            <>
              <input className="entrada" value={condicion} placeholder="Condicion para reabrirla" onChange={(e) => setCondicion(e.target.value)} aria-label={`Condicion de reapertura de ${a.titulo}`} />
              <button type="button" className="btn btn-pequeno" disabled={condicion.trim() === ''} onClick={() => acciones.cambiarEstadoArea(inv.id, a.id, 'pausada', condicion)}>
                Pausar con condicion
              </button>
            </>
          )}
          {a.estado !== 'sin_explorar' && (
            <button type="button" className="btn btn-pequeno" onClick={() => acciones.cambiarEstadoArea(inv.id, a.id, 'sin_explorar', '', undefined, 'se deja sin explorar')}>
              Dejar sin explorar
            </button>
          )}
          {corridas.length > 0 && (
            <select className="entrada" value={a.corridaId ?? ''} onChange={(e) => acciones.cambiarEstadoArea(inv.id, a.id, null, '', e.target.value)} aria-label={`Campana de ${a.titulo}`}>
              <option value="">Sin campana</option>
              {corridas.map((c) => (
                <option key={c.id} value={c.id}>
                  Campana {c.numero} ({c.estado.replace('_', ' ')})
                </option>
              ))}
            </select>
          )}
        </div>
      </td>
    </tr>
  );
}

/** El programa en cuatro niveles (plan completo, etapas A a D): la meta amplia,
 *  las areas que se compararon y su estado, las campanas (corridas) que
 *  trabajan cada area, y la pregunta concreta de cada campana. Lo que no tiene
 *  campana o pregunta se ve como hueco, no se rellena. */
export function Jerarquia({ inv, corridas }: { inv: Investigacion; corridas: Corrida[] }) {
  const m = inv.mision;
  if (!m) return null;
  const areas = m.areas ?? [];
  const sinArea = corridas.filter((c) => !areas.some((a) => a.corridaId === c.id));
  const pregunta = (c: Corrida) => {
    const q = c.pregunta;
    if (!q) return <span className="meta">sin pregunta de campana todavia</span>;
    return (
      <span>
        {q.intervencion || 'la intervencion'} frente a {q.comparador || 'el comparador'} sobre {q.desenlace || 'el desenlace'} en {q.contexto || 'el contexto'}
        {q.umbralResuelto ? '' : ' (umbral de efecto sin resolver)'}
      </span>
    );
  };
  return (
    <Seccion titulo="Programa, areas, campanas y preguntas" nota="La jerarquia del plan completo: una meta amplia se reparte en areas comparables; cada area se trabaja en campanas (corridas) con una pregunta concreta y comprobable. Aqui se ve que area tiene campana, cual esta pausada y con que condicion, y que campana todavia no tiene pregunta.">
      <ul className="arbol">
        <li>
          <strong>Programa:</strong> {m.metaAmplia || inv.objetivo}
          <ul>
            {areas.length === 0 && <li className="meta">Sin areas comparadas todavia.</li>}
            {areas.map((a) => {
              const cs = corridas.filter((c) => c.id === a.corridaId);
              return (
                <li key={a.id}>
                  <Chip tono={a.estado === 'elegida' ? 'ok' : a.estado === 'pausada' ? 'aviso' : 'borde'}>{a.estado.replace('_', ' ')}</Chip> <strong>{a.titulo}</strong>
                  {a.estado === 'pausada' && a.condicionReapertura ? <span className="meta"> (se reabre si: {a.condicionReapertura})</span> : null}
                  <ul>
                    {cs.length === 0 && <li className="meta">{a.estado === 'elegida' ? 'Elegida sin campana asignada.' : 'Sin campana.'}</li>}
                    {cs.map((c) => (
                      <li key={c.id}>
                        <a className="enlace" href={rutaDe(inv.id, 'corrida', c.id)}>
                          Campana {c.numero}
                        </a>{' '}
                        <span className="meta">({c.estado.replace('_', ' ')})</span>
                        <ul>
                          <li>{pregunta(c)}</li>
                        </ul>
                      </li>
                    ))}
                  </ul>
                </li>
              );
            })}
            {sinArea.length > 0 && (
              <li>
                <span className="meta">Campanas sin area asignada:</span>
                <ul>
                  {sinArea.map((c) => (
                    <li key={c.id}>
                      <a className="enlace" href={rutaDe(inv.id, 'corrida', c.id)}>
                        Campana {c.numero}
                      </a>{' '}
                      <span className="meta">({c.estado.replace('_', ' ')})</span>
                      <ul>
                        <li>{pregunta(c)}</li>
                      </ul>
                    </li>
                  ))}
                </ul>
              </li>
            )}
          </ul>
        </li>
      </ul>
    </Seccion>
  );
}


// ---------------------------------------------------------------------------
// Motor causal minimo: grafo local e identificacion
// ---------------------------------------------------------------------------

export function GrafoCausalDeHipotesis({ h }: { h: Hipotesis }) {
  const g = h.grafoCausal;
  if (!g) return null;
  const etiqueta = (id: string) => g.nodos.find((n) => n.id === id)?.etiqueta ?? id;
  const tono = g.identificacion === 'identificable' ? 'ok' : g.identificacion === 'acotado' ? 'aviso' : 'mal';
  return (
    <Seccion titulo="Grafo causal y supuestos" nota="Lo minimo para no confundir asociacion con causa: la exposicion X, el desenlace Y, las alternativas que planteo el Killer y las relaciones de consenso del campo, cada arista con su tipo. La identificacion sale por regla: un ensayo aleatorizado la cierra; sin el, hacen falta temporalidad, ajuste por confusores y replicacion independiente. Lo que falta es lo que un experimento tendria que aportar.">
      <div className="acciones">
        <Chip tono={tono}>{IDENTIFICACION_CAUSAL[g.identificacion] ?? g.identificacion}</Chip>
        <span className="meta">{g.resumen}</span>
      </div>
      {g.supuestosFaltantes.length > 0 && (
        <ul className="lista-limpia">
          {g.supuestosFaltantes.map((s, i) => (
            <li key={i} className="tono-aviso">
              Falta: {s}
            </li>
          ))}
        </ul>
      )}
      {g.supuestosCumplidos.length > 0 && (
        <ul className="lista-limpia">
          {g.supuestosCumplidos.map((s, i) => (
            <li key={i} className="meta">
              Cumplido: {s}
            </li>
          ))}
        </ul>
      )}
      <details className="versiones">
        <summary>
          {g.nodos.length} nodos y {g.aristas.length} aristas tipadas
        </summary>
        <ul className="lista-plana">
          {g.aristas.map((a, i) => (
            <li key={i}>
              <strong style={{ fontSize: 13 }}>{etiqueta(a.de)}</strong> causa <strong style={{ fontSize: 13 }}>{etiqueta(a.a)}</strong> <Chip tono={a.tipo === 'inferencia_con_evidencia' ? 'ok' : 'borde'}>{TIPO_ARISTA[a.tipo] ?? a.tipo}</Chip>
              <p className="meta">{a.contexto}</p>
            </li>
          ))}
        </ul>
      </details>
    </Seccion>
  );
}

/** Las aristas tipadas del modelo de mundo de una investigacion: la base
 *  curada y lo que cada hipotesis juzgada afirma, con su tipo. */
export function RelacionesCausales({ estado, inv }: { estado: EstadoRosa; inv: Investigacion }) {
  const rels = (estado.relaciones ?? []).filter((r) => r.investigacionId === null || r.investigacionId === inv.id);
  if (rels.length === 0) return null;
  const propias = rels.filter((r) => r.hipotesisId);
  const base = rels.filter((r) => !r.hipotesisId);
  return (
    <Seccion titulo="Relaciones causales tipadas" nota="Cada arista dice de donde sale. Las de las hipotesis entran cuando el Killer las juzga, como supuesto o como inferencia con evidencia, y se actualizan con cada version. La base curada es consenso del campo escrito a mano en el codigo (rosa/causal.py): se puede discutir y cambiar ahi.">
      {propias.length === 0 ? <p className="meta">Ninguna hipotesis juzgada todavia: solo la base curada.</p> : null}
      <ul className="lista-plana">
        {propias.map((r) => (
          <li key={r.id}>
            <strong style={{ fontSize: 13 }}>{r.de}</strong> causa <strong style={{ fontSize: 13 }}>{r.a}</strong> <Chip tono={r.tipo === 'inferencia_con_evidencia' ? 'ok' : 'borde'}>{TIPO_ARISTA[r.tipo] ?? r.tipo}</Chip>{' '}
            {r.hipotesisId && (
              <a className="enlace" href={rutaDe(inv.id, 'hipotesis', r.hipotesisId)}>
                abrir hipotesis
              </a>
            )}
            <p className="meta">{r.contexto}</p>
          </li>
        ))}
      </ul>
      <details className="versiones">
        <summary>Base curada ({base.length} relaciones de consenso)</summary>
        <ul className="lista-plana">
          {base.map((r) => (
            <li key={r.id} className="meta">
              {r.de} causa {r.a}: {r.contexto}
            </li>
          ))}
        </ul>
      </details>
    </Seccion>
  );
}


// ---------------------------------------------------------------------------
// Panel del Killer: fallos plantados y tasa de deteccion
// ---------------------------------------------------------------------------

const ETIQUETA_FALLO: Record<string, string> = {
  original: 'Original (acuerdo con la decision real)',
  cifra_alterada: 'Cifra alterada',
  prediccion_vaga: 'Prediccion no falsable',
  causal_sin_temporalidad: 'Causalidad sin temporalidad',
  misma_cohorte: 'Misma cohorte (debe avanzar con aviso)',
  supuesto_contradicho: 'Supuesto contradicho',
  gris_parcial: 'Gris: pasaje parcial (no debe descartar)',
};

export function PanelKiller({ estado }: { estado: EstadoRosa }) {
  const evs = [...(estado.evaluaciones ?? [])].filter((e) => e.tipo === 'panel_killer').sort((a, b) => b.fecha - a.fecha);
  return (
    <Seccion titulo="Panel del Killer" nota="Hipotesis reales con un fallo plantado a proposito (cifra alterada, prediccion vaga, causalidad sin temporalidad, misma cohorte, supuesto contradicho) y un conjunto gris que no debe descartarse. Mide que fraccion detecta el Killer, si lo detecta la comprobacion correcta, cuanto se abstiene y cuanto mata de mas. Se repite con cada version del prompt o del modelo: si baja, se sabe antes de que llegue a una hipotesis real.">
      {evs.length === 0 ? (
        <p className="meta">Sin paneles todavia. Se corre desde el servidor con el comando del README (cuesta llamadas al juez).</p>
      ) : (
        evs.slice(0, 3).map((ev) => (
          <div key={ev.id} className="tarjeta">
            <div className="acciones">
              <Chip tono={ev.resumen.tasaDeteccion !== null && ev.resumen.tasaDeteccion >= 0.8 ? 'ok' : 'aviso'}>Deteccion {ev.resumen.tasaDeteccion === null ? 'n/a' : `${Math.round(ev.resumen.tasaDeteccion * 100)} %`}</Chip>
              <Chip tono="borde">Juez detecta {ev.resumen.tasaJuezDetecta === null ? 'n/a' : `${Math.round(ev.resumen.tasaJuezDetecta * 100)} %`}</Chip>
              <Chip tono="borde">Abstencion {Math.round(ev.resumen.abstencion * 100)} %</Chip>
              <Chip tono={ev.resumen.sobreMatanzaGris !== null && ev.resumen.sobreMatanzaGris > 0 ? 'mal' : 'ok'}>Mata de mas en gris {ev.resumen.sobreMatanzaGris === null ? 'n/a' : `${Math.round(ev.resumen.sobreMatanzaGris * 100)} %`}</Chip>
              <span className="meta">
                {ev.resumen.casos} casos sobre {ev.resumen.hipotesis} hipotesis, juez {ev.resumen.juez}, {ev.resumen.usd} USD, {new Date(ev.fecha).toLocaleString('es')}
              </span>
            </div>
            <table className="tabla">
              <thead>
                <tr>
                  <th>Fallo plantado</th>
                  <th>Casos</th>
                  <th>Detectados</th>
                  <th>Lo vio el juez</th>
                  <th>Suspendidas</th>
                  <th>Descartadas</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(ev.porFallo).map(([f, r]) => (
                  <tr key={f}>
                    <td title={ev.fallos[f]}>{ETIQUETA_FALLO[f] ?? f}</td>
                    <td>{r.casos}</td>
                    <td>{f === 'original' ? `${r.acuerdoConReal ?? 0} de acuerdo con la real` : `${r.detectados ?? 0}`}</td>
                    <td>{f === 'original' ? '' : (r.juezFalla ?? 0)}</td>
                    <td>{r.suspendidas ?? 0}</td>
                    <td>{r.descartadas ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))
      )}
    </Seccion>
  );
}


// ---------------------------------------------------------------------------
// Conectores: catalogo y registro de consultas
// ---------------------------------------------------------------------------

/** El catalogo de conectores tal como esta en el codigo (rosa/conectores/):
 *  que base, que aporta, limite, licencia, si necesita clave y si esta
 *  disponible. Lo que no esta disponible se lista con su motivo, para que se
 *  vea que existe en Claude Science y por que Rosa no lo usa. */
export function Conectores({ conectores }: { conectores: ConectorCatalogo[] | undefined }) {
  const lista = conectores ?? [];
  const grupos = Array.from(new Set(lista.map((c) => c.grupo)));
  const disponibles = lista.filter((c) => c.estado === 'disponible').length;
  return (
    <Seccion titulo="Conectores a bases publicas" nota={`Cada conector envuelve una API publica con su limite de peticiones y su licencia. Cada llamada deja un registro de consulta (herramienta, argumentos, fecha, resultados, identificadores, invariante comprobada) en la hipotesis que la pidio. ${disponibles} de ${lista.length} disponibles; el resto se lista con el motivo. Una fuente que no responde es "no pude comprobar", nunca "no hay".`}>
      {lista.length === 0 ? (
        <p className="meta">El catalogo llega del servidor al arrancar.</p>
      ) : (
        grupos.map((g) => (
          <details key={g} className="versiones" open={g === 'alzheimer' || g === 'directorio'}>
            <summary>
              {GRUPO_CONECTOR[g] ?? g} ({lista.filter((c) => c.grupo === g).length})
            </summary>
            <table className="tabla">
              <thead>
                <tr>
                  <th>Fuente</th>
                  <th>Que aporta</th>
                  <th>Limite y licencia</th>
                  <th>Estado</th>
                  <th>Usos</th>
                </tr>
              </thead>
              <tbody>
                {lista
                  .filter((c) => c.grupo === g)
                  .map((c) => (
                    <tr key={c.nombre}>
                      <td>
                        <strong style={{ fontSize: 13 }}>{c.fuente}</strong>
                        <p className="meta">
                          {c.descripcion}{' '}
                          <a className="enlace" href={c.urlDoc} target="_blank" rel="noopener noreferrer">
                            doc
                          </a>
                        </p>
                      </td>
                      <td className="meta">{c.aporta}</td>
                      <td className="meta">
                        {c.limite}
                        {c.licencia ? `. ${c.licencia}` : ''}
                        {c.clave !== 'no' ? `. Clave: ${c.clave}` : ''}
                      </td>
                      <td>
                        <Chip tono={ESTADO_CONECTOR[c.estado]?.tono ?? 'neutro'}>{ESTADO_CONECTOR[c.estado]?.etiqueta ?? c.estado}</Chip>
                        {c.motivo && <p className="meta">{c.motivo}</p>}
                      </td>
                      <td className="meta">
                        {c.usos}
                        {c.errores ? ` (${c.errores} sin respuesta)` : ''}
                        {c.estado === 'disponible' && (
                          <select className="entrada" value={c.permiso ?? 'permitir'} onChange={(e) => acciones.fijarPermisoConector(c.nombre, e.target.value as NivelPermisoConector)} aria-label={`Permiso de ${c.fuente}`} title="Permitir: el bucle y las personas lo usan. Solo persona: solo cuando alguien pregunta desde aqui. Bloquear: nadie.">
                            <option value="permitir">Permitir</option>
                            <option value="solo_persona">Solo si pregunta una persona</option>
                            <option value="bloquear">Bloquear</option>
                          </select>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </details>
        ))
      )}
    </Seccion>
  );
}

/** Las consultas a bases que esta hipotesis provoco, con lo que Claude
 *  Science exige registrar: herramienta, argumentos, fecha, numero de
 *  resultados, identificadores retenidos e invariante comprobada. */
export function TablaConsultas({ consultas, ahora }: { consultas: ConsultaBase[]; ahora: number }) {
  const cs = [...consultas].sort((a, b) => b.fecha - a.fecha);
  return (
    <table className="tabla">
      <thead>
        <tr>
          <th>Base</th>
          <th>Argumentos</th>
          <th>Resultados</th>
          <th>Invariante</th>
          <th>Cuando</th>
        </tr>
      </thead>
      <tbody>
        {cs.slice(0, 40).map((c) => (
          <tr key={c.id}>
            <td>
              <strong style={{ fontSize: 13 }}>{c.fuente || c.herramienta}</strong>
              <p className="meta">{c.herramienta}</p>
            </td>
            <td className="meta">
              {Object.entries(c.argumentos)
                .map(([k, v]) => `${k}=${String(v).slice(0, 60)}`)
                .join(', ')}
            </td>
            <td className="meta">
              {c.error ? <span className="tono-aviso">{c.error}</span> : `${c.n ?? '?'} resultados${c.ids.length ? `; ids: ${c.ids.slice(0, 4).join(', ')}${c.ids.length > 4 ? '...' : ''}` : ''}${c.version ? `; version ${c.version}` : ''}`}
            </td>
            <td>{c.invariante ? <Chip tono={c.invariante.ok ? 'ok' : 'aviso'}>{c.invariante.detalle.slice(0, 80)}</Chip> : <span className="meta">sin invariante</span>}</td>
            <td className="meta">
              <Momento t={c.fecha} ahora={ahora} /> ({c.ms} ms)
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Las consultas a bases que esta hipotesis provoco. */
export function ConsultasABases({ h, ahora }: { h: Hipotesis; ahora: number }) {
  const cs = h.consultas ?? [];
  if (cs.length === 0) return null;
  const fallidas = cs.filter((c) => c.error).length;
  return (
    <Seccion titulo="Consultas a bases" nota="Cada fila es una llamada a una base publica hecha para esta hipotesis. La invariante es una comprobacion independiente de que la respuesta es la que se esperaba (un simbolo resuelve a un unico gen, el accession coincide). Sin respuesta significa que no se pudo comprobar, no que no exista.">
      <p className="meta">
        {cs.length} {cs.length === 1 ? 'consulta' : 'consultas'}
        {fallidas ? `, ${fallidas} sin respuesta` : ''}
      </p>
      <TablaConsultas consultas={cs} ahora={ahora} />
    </Seccion>
  );
}

/** Memoria del proyecto: hechos cortos que Rosa lee en cada mision. Los
 *  escribe y borra una persona. */
export function MemoriaDelProyecto({ inv }: { inv: Investigacion }) {
  const [texto, setTexto] = useState('');
  const memoria = inv.memoria ?? [];
  return (
    <Seccion titulo="Memoria del proyecto" nota="Hechos cortos y estables que Rosa lee en cada mision, plan y revision: una preferencia ('solo datos publicos'), una restriccion ('no proponer ensayos con farmacos retirados'), una decision confirmada. No es para resultados ni para copiar literatura: para eso estan los hechos y los artefactos.">
      {memoria.length === 0 ? <p className="meta">Sin memoria todavia.</p> : null}
      <ul className="lista-plana">
        {memoria.map((m) => (
          <li key={m.id} className="acciones">
            <span style={{ fontSize: 13 }}>{m.texto}</span>
            <span className="meta">
              {m.quien}, {new Date(m.fecha).toLocaleDateString('es')}
            </span>
            <button type="button" className="btn btn-pequeno" onClick={() => acciones.quitarMemoria(inv.id, m.id)}>
              Quitar
            </button>
          </li>
        ))}
      </ul>
      <div className="dirigir">
        <input className="entrada" value={texto} maxLength={400} placeholder="Un hecho estable que Rosa deba recordar" onChange={(e) => setTexto(e.target.value)} aria-label="Nuevo hecho de memoria" />
        <button
          type="button"
          className="btn"
          disabled={texto.trim() === ''}
          onClick={() => {
            acciones.anadirMemoria(inv.id, texto);
            setTexto('');
          }}
        >
          Recordar
        </button>
      </div>
    </Seccion>
  );
}

/** Preguntar a las bases con herramientas: Rosa elige que conectores llamar,
 *  responde en llano y deja cada consulta registrada. */
export function PreguntarALasBases({ inv, ahora }: { inv: Investigacion; ahora: number }) {
  const [pregunta, setPregunta] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const preguntas = [...(inv.preguntasABases ?? [])].sort((a, b) => b.fecha - a.fecha);
  return (
    <Seccion titulo="Preguntar a las bases" nota="Rosa responde consultando las bases publicas del catalogo, el propio proyecto y el modelo de mundo, con un bucle acotado de herramientas (elige una, lee el resultado, repite hasta seis veces). Cada dato lleva detras la herramienta y el identificador; lo que ninguna base devolvio no se afirma. Cuesta llamadas al cerebro.">
      <div className="dirigir">
        <input className="entrada" value={pregunta} placeholder="Que farmacos aprobados tocan TREM2 y en que tejidos se expresa" onChange={(e) => setPregunta(e.target.value)} aria-label="Pregunta a las bases" />
        <button
          type="button"
          className="btn btn-primario"
          disabled={pregunta.trim() === '' || enviando}
          onClick={async () => {
            setEnviando(true);
            setError(null);
            const err = await acciones.preguntarALasBases(inv.id, pregunta);
            setEnviando(false);
            setError(err);
            if (!err) setPregunta('');
          }}
        >
          {enviando ? 'Consultando bases...' : 'Preguntar con herramientas'}
        </button>
        {error && <span className="tono-mal">{error}</span>}
      </div>
      {preguntas.slice(0, 5).map((q) => (
        <div key={q.id} className="tarjeta" style={{ marginTop: 8 }}>
          <p>
            <strong style={{ fontSize: 13 }}>{q.pregunta}</strong>{' '}
            <span className="meta">
              {q.quien}, <Momento t={q.fecha} ahora={ahora} />, {q.iteraciones} {q.iteraciones === 1 ? 'paso' : 'pasos'}, {q.herramientas.length} {q.herramientas.length === 1 ? 'herramienta' : 'herramientas'}
            </span>
          </p>
          {q.error ? <p className="tono-mal">{q.error}</p> : <p style={{ whiteSpace: 'pre-wrap' }}>{q.respuesta}</p>}
          {q.limites && <p className="meta">Limites: {q.limites}</p>}
          {q.consultas.length > 0 && (
            <details className="versiones">
              <summary>{q.consultas.length} consultas registradas</summary>
              <TablaConsultas consultas={q.consultas} ahora={ahora} />
            </details>
          )}
        </div>
      ))}
    </Seccion>
  );
}

/** El contexto de la diana desde las bases, debajo de la tarjeta. */
export function ContextoDeBases({ h }: { h: Hipotesis }) {
  const c = h.contextoBases;
  if (!c) return null;
  const ids = c.identificadores ?? {};
  return (
    <div className="tarjeta" style={{ marginTop: 8 }}>
      <div className="acciones">
        <strong style={{ fontSize: 13 }}>La diana en las bases</strong>
        {ids.ensembl ? (
          <>
            <Chip tono="ok">{ids.simbolo ?? c.diana}</Chip>
            <span className="meta">
              Ensembl {ids.ensembl}
              {ids.uniprot ? ` · UniProt ${ids.uniprot}` : ' · sin entrada UniProt revisada'}
              {ids.entrez ? ` · Entrez ${ids.entrez}` : ''}
            </span>
          </>
        ) : (
          <Chip tono="aviso">"{c.diana}" no resuelve a un gen humano en MyGene</Chip>
        )}
      </div>
      {c.funcion && <p className="meta">Funcion (UniProt): {c.funcion}</p>}
      {c.expresionCerebro && <p className="meta">Expresion (Human Protein Atlas): {c.expresionCerebro}</p>}
      {c.interactores.length > 0 && <p className="meta">Interactores (STRING): {c.interactores.map((i) => `${i.simbolo} (${i.puntuacion})`).join(', ')}</p>}
      {c.rutas.length > 0 && <p className="meta">Rutas (Reactome): {c.rutas.map((r) => r.nombre).join('; ')}</p>}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Revisor de registro y procedencia de artefactos
// ---------------------------------------------------------------------------

/** Los hallazgos del revisor de registro como tarjetas, igual que Claude
 *  Science los ensena bajo el mensaje revisado. */
export function RevisionDeRegistro({ r, compacto = false }: { r: RevisionRegistro | null | undefined; compacto?: boolean }) {
  if (!r) return null;
  if (r.hallazgos.length === 0) {
    return (
      <div className="acciones">
        <Chip tono="ok">Revisor de registro: sin discrepancias</Chip>
        {!compacto && <span className="meta">{r.resumen}</span>}
      </div>
    );
  }
  return (
    <div className="revision-registro">
      <div className="acciones">
        <Chip tono={r.hallazgos.some((h) => h.gravedad === 'alta') ? 'mal' : 'aviso'}>
          Revisor de registro: {r.hallazgos.length} {r.hallazgos.length === 1 ? 'hallazgo' : 'hallazgos'}
        </Chip>
        <span className="meta">
          {r.porRegla} por regla{r.juez ? `, ${r.hallazgos.length - r.porRegla} del juez` : ', sin juez'}
        </span>
      </div>
      <ul className="lista-plana">
        {r.hallazgos.slice(0, compacto ? 3 : 20).map((h, i) => (
          <li key={h.id ?? i} className={`tarjeta hallazgo-registro gravedad-${h.gravedad}`}>
            <strong style={{ fontSize: 13 }}>{CLASE_HALLAZGO_REGISTRO[h.clase] ?? h.clase}</strong> <Chip tono={h.gravedad === 'alta' ? 'mal' : h.gravedad === 'media' ? 'aviso' : 'borde'}>{h.gravedad}</Chip> <span className="meta">({h.origen})</span>
            <p className="meta">{h.detalle}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Las cinco pestanas de procedencia de una version de artefacto. */
export function ProcedenciaDeArtefacto({ p }: { p: ProcedenciaArtefacto | undefined }) {
  const [pestana, setPestana] = useState<'mensajes' | 'codigo' | 'registroEjecucion' | 'entorno' | 'revision'>('mensajes');
  if (!p) return <p className="meta">Esta version no tiene procedencia registrada (anterior al 11 de septiembre de 2026).</p>;
  const etiquetas: Record<string, string> = { mensajes: 'Mensajes', codigo: 'Codigo', registroEjecucion: 'Registro de ejecucion', entorno: 'Entorno', revision: 'Revision' };
  const vacio = (k: keyof ProcedenciaArtefacto) => p[k] === null || p[k] === undefined || (Array.isArray(p[k]) && (p[k] as unknown[]).length === 0);
  return (
    <div className="procedencia-artefacto">
      <div className="pestanas">
        {(Object.keys(etiquetas) as (keyof ProcedenciaArtefacto)[]).map((k) => (
          <button key={k} type="button" className={`pestana ${pestana === k ? 'activa' : ''}`} onClick={() => setPestana(k)} disabled={vacio(k)} title={vacio(k) ? 'No aplica a esta version' : ''}>
            {etiquetas[k]}
          </button>
        ))}
      </div>
      {pestana === 'revision' ? (
        <RevisionDeRegistro r={p.revision} />
      ) : pestana === 'codigo' ? (
        <pre className="contenido-artefacto">{p.codigo ?? ''}</pre>
      ) : (
        <pre className="contenido-artefacto">{JSON.stringify(p[pestana], null, 1)}</pre>
      )}
      <p className="meta">El registro de ejecucion manda sobre el codigo: si discrepan, lo que corrio es lo que vale.</p>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Skills de Rosa
// ---------------------------------------------------------------------------

/** Las skills: instrucciones de metodo que el planificador de analisis, el
 *  escritor de codigo y el proponente de areas cargan cuando la tarea las
 *  pide (por palabras de activacion). Mismo formato que las Agent Skills de
 *  Anthropic; viven en rosa/skills/<nombre>/SKILL.md y se editan ahi. */
export function Skills({ skills }: { skills: SkillCatalogo[] | undefined }) {
  const lista = skills ?? [];
  return (
    <Seccion titulo="Skills de metodo" nota="Un fichero de instrucciones por metodo (como correr una reproduccion de GEO, como calcular un tamano muestral, como hacer control de calidad de celula unica). Rosa carga las que casan con el plan y las pasa al modelo junto con los modulos que el sandbox puede importar. Se anaden o cambian editando rosa/skills/; el catalogo se lee al arrancar.">
      {lista.length === 0 ? (
        <p className="meta">El catalogo de skills llega del servidor al arrancar.</p>
      ) : (
        <table className="tabla">
          <thead>
            <tr>
              <th>Skill</th>
              <th>Que hace</th>
              <th>Se activa con</th>
              <th>Entorno y modulos</th>
            </tr>
          </thead>
          <tbody>
            {lista.map((s) => (
              <tr key={s.nombre}>
                <td>
                  <strong style={{ fontSize: 13 }}>{s.nombre}</strong>
                  <p className="meta">
                    {s.ruta}/SKILL.md, {s.lineas} lineas
                  </p>
                </td>
                <td className="meta">{s.descripcion}</td>
                <td className="meta">{s.activaSi.join(', ')}</td>
                <td className="meta">
                  <Chip tono={s.entorno === 'celula_unica' ? 'aviso' : 'borde'}>{s.entorno === 'celula_unica' ? 'celula unica' : 'tabular'}</Chip>
                  {s.paquetes.length > 0 && <p className="meta">Paquetes: {s.paquetes.join(', ')}</p>}
                  {s.scripts.length > 0 && <p className="meta">Modulos: {s.scripts.join(', ')}</p>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Seccion>
  );
}
