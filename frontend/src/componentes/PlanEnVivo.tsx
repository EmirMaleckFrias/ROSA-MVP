// El plan de la iteracion con sus pasos marcandose, y bajo cada paso los
// marcadores de sus pistas paralelas. Pulsar una pista abre su transcripcion
// con cada consulta a una fuente expandible (parametros exactos y lo que
// devolvio). Un paso fallido lleva su motivo. Una pista en curso se puede
// detener sin parar la corrida.
//
// Si el plan no esta aprobado, se ensena el editor: reordenar, quitar,
// anadir, fijar presupuesto por paso, y "Aprobar plan" (patron de
// Biomni-AD, Devin y Magentic-UI; Claude Science espera la aprobacion desde
// la 0.1.27).

import { useState } from 'react';
import type { Iteracion, PasoPlan, Pista } from '../datos/tipos';
import { ESTADO_PISTA, TIPO_PISTA } from '../lib/etiquetas';
import { formatearDuracion } from '../lib/formato';
import { IconAlert, IconCheck, IconChevronDown, IconMinus, IconSpinner, IconStop, IconTrash, IconUser } from './icons';
import { Chip, Momento } from './piezas';

function IconoPaso({ paso }: { paso: PasoPlan }) {
  if (paso.estado === 'en_curso') return <IconSpinner size={12} />;
  if (paso.estado === 'hecho') return <IconCheck size={12} />;
  if (paso.estado === 'fallido') return <IconAlert size={12} />;
  if (paso.indicacionHumana) return <IconUser size={12} />;
  if (paso.estado === 'omitido') return <IconMinus size={12} />;
  return <span className="mono" style={{ fontSize: 10 }} />;
}

function Consulta({ c }: { c: NonNullable<Pista['transcripcion'][number]['consulta']> }) {
  const [abierta, setAbierta] = useState(false);
  return (
    <div className="consulta">
      <button type="button" className="consulta-cabecera" aria-expanded={abierta} onClick={() => setAbierta((v) => !v)}>
        <span>Consulta a {c.base}</span>
        <span style={{ transform: abierta ? 'rotate(180deg)' : 'none', display: 'inline-flex' }}>
          <IconChevronDown size={11} />
        </span>
      </button>
      {abierta && (
        <dl className="consulta-detalle">
          <dt>Parametros</dt>
          <dd className="mono">{c.parametros}</dd>
          <dt>Devolvio</dt>
          <dd>{c.resultados}</dd>
        </dl>
      )}
    </div>
  );
}

export function Transcripcion({ pista, ahora, onDetener }: { pista: Pista; ahora: number; onDetener?: (indicacion: string) => void }) {
  const [indicacion, setIndicacion] = useState('');
  return (
    <div>
      <p className="meta" style={{ marginBottom: 6 }}>
        {TIPO_PISTA[pista.tipo]} · {pista.fuente} · {ESTADO_PISTA[pista.estado]}
        {pista.ms > 0 && ` · ${formatearDuracion(pista.ms)}`}
      </p>
      {pista.transcripcion.length === 0 ? (
        <p className="meta">Todavia sin actividad registrada.</p>
      ) : (
        <ol className="transcripcion" aria-label={`Transcripcion de ${pista.titulo}`}>
          {pista.transcripcion.map((e, i) => (
            <li key={i} className={`t-${e.tipo}`}>
              <time>{formatearDuracion(e.t) || '0 s'}</time>
              <div>
                <span>{e.texto}</span>
                {e.consulta && <Consulta c={e.consulta} />}
              </div>
            </li>
          ))}
        </ol>
      )}
      {pista.estado === 'en_curso' && onDetener && (
        <div className="dirigir" style={{ marginTop: 8 }}>
          <input className="entrada entrada-s" value={indicacion} placeholder="Indicacion para Rosa al detenerla (opcional)" onChange={(e) => setIndicacion(e.target.value)} aria-label="Indicacion al detener la pista" />
          <button type="button" className="btn btn-s btn-peligro" onClick={() => onDetener(indicacion)}>
            <IconStop size={11} /> Detener esta pista
          </button>
        </div>
      )}
      <span className="sr-only">{ahora}</span>
    </div>
  );
}

export function MarcadorPista({ pista, abierta, onClick }: { pista: Pista; abierta: boolean; onClick: () => void }) {
  return (
    <button type="button" className={`pista pista-${pista.estado}`} aria-expanded={abierta} onClick={onClick} title={`${TIPO_PISTA[pista.tipo]} · ${pista.fuente}`}>
      <i aria-hidden="true" />
      <span>{pista.titulo}</span>
      <span className="meta">{pista.estado === 'en_curso' ? 'en curso' : pista.resumen}</span>
    </button>
  );
}

interface Props {
  iteracion: Iteracion;
  ahora: number;
  onDetenerPista?: (pistaId: string, indicacion: string) => void;
  onEditarPlan?: (plan: PasoPlan[]) => void;
  onAprobarPlan?: () => void;
}

export function PlanEnVivo({ iteracion, ahora, onDetenerPista, onEditarPlan, onAprobarPlan }: Props) {
  const [abierta, setAbierta] = useState<string | null>(null);
  const [nuevoPaso, setNuevoPaso] = useState('');
  const pistaAbierta = iteracion.pistas.find((p) => p.id === abierta) ?? null;
  const editable = !iteracion.planAprobado && onEditarPlan !== undefined;

  const mover = (i: number, d: -1 | 1) => {
    const plan = [...iteracion.plan];
    const j = i + d;
    if (j < 0 || j >= plan.length) return;
    [plan[i], plan[j]] = [plan[j]!, plan[i]!];
    onEditarPlan?.(plan);
  };

  if (editable) {
    return (
      <div className="plan-editor">
        <div className="acciones" style={{ justifyContent: 'space-between' }}>
          <div>
            <strong style={{ fontSize: 13 }}>Plan propuesto para la iteracion {iteracion.numero}</strong>
            <p className="meta">
              Propuesto <Momento t={iteracion.planPropuestoEn} ahora={ahora} />. Rosa no ejecuta nada hasta que lo apruebes. Reordena, quita o añade pasos y fija el presupuesto de cada uno.
            </p>
          </div>
          <button type="button" className="btn btn-primario" onClick={onAprobarPlan}>
            Aprobar plan y ejecutar
          </button>
        </div>
        <ol className="plan plan-edicion">
          {iteracion.plan.map((paso, i) => (
            <li key={paso.id} className="paso paso-pendiente">
              <span className="paso-icono mono" aria-hidden="true" style={{ fontSize: 10 }}>
                {i + 1}
              </span>
              <div className="paso-cuerpo">
                <div className="paso-fila-edicion">
                  <input className="entrada entrada-s" value={paso.titulo} onChange={(e) => onEditarPlan?.(iteracion.plan.map((p) => (p.id === paso.id ? { ...p, titulo: e.target.value } : p)))} aria-label={`Titulo del paso ${i + 1}`} />
                  <input
                    className="entrada entrada-s"
                    type="number"
                    min={0}
                    value={paso.presupuesto ?? ''}
                    placeholder="llamadas"
                    style={{ maxWidth: 110 }}
                    onChange={(e) => onEditarPlan?.(iteracion.plan.map((p) => (p.id === paso.id ? { ...p, presupuesto: e.target.value === '' ? null : Number(e.target.value) } : p)))}
                    aria-label={`Presupuesto del paso ${i + 1}`}
                  />
                  <button type="button" className="btn btn-fantasma btn-icono btn-s" aria-label="Subir" disabled={i === 0} onClick={() => mover(i, -1)}>
                    <IconChevronDown size={12} style={{ transform: 'rotate(180deg)' }} />
                  </button>
                  <button type="button" className="btn btn-fantasma btn-icono btn-s" aria-label="Bajar" disabled={i === iteracion.plan.length - 1} onClick={() => mover(i, 1)}>
                    <IconChevronDown size={12} />
                  </button>
                  <button type="button" className="btn btn-fantasma btn-icono btn-s" aria-label="Quitar paso" disabled={iteracion.plan.length === 1} onClick={() => onEditarPlan?.(iteracion.plan.filter((p) => p.id !== paso.id))}>
                    <IconTrash size={12} />
                  </button>
                </div>
                {paso.detalle !== '' && <p className="paso-detalle">{paso.detalle}</p>}
                {paso.valorDecision ? <p className="paso-detalle paso-valor" title="Que decision cambia segun el resultado de este paso (valor de decision)">Decide: {paso.valorDecision}</p> : null}
              </div>
            </li>
          ))}
        </ol>
        <div className="dirigir">
          <input className="entrada entrada-s" value={nuevoPaso} placeholder="Añadir un paso" onChange={(e) => setNuevoPaso(e.target.value)} aria-label="Paso nuevo" />
          <button
            type="button"
            className="btn btn-s"
            disabled={nuevoPaso.trim() === ''}
            onClick={() => {
              onEditarPlan?.([...iteracion.plan, { id: `paso-h-${Date.now()}`, titulo: nuevoPaso.trim(), detalle: '', estado: 'pendiente', indicacionHumana: true, motivoFallo: null, presupuesto: null }]);
              setNuevoPaso('');
            }}
          >
            Añadir
          </button>
        </div>
      </div>
    );
  }

  return (
    <ol className="plan" aria-label={`Plan de la iteracion ${iteracion.numero}`}>
      {iteracion.plan.map((paso) => {
        const pistas = iteracion.pistas.filter((p) => p.pasoId === paso.id);
        return (
          <li key={paso.id} className={`paso paso-${paso.estado} ${paso.indicacionHumana ? 'paso-humano' : ''}`}>
            <span className="paso-icono" aria-hidden="true">
              <IconoPaso paso={paso} />
            </span>
            <div className="paso-cuerpo">
              <div className="paso-titulo">
                <span className={paso.estado === 'en_curso' ? 'shimmer-text' : ''}>{paso.titulo}</span>
                {paso.indicacionHumana && <Chip tono="acento">Indicacion tuya</Chip>}
                {paso.estado === 'fallido' && <Chip tono="mal">Fallido</Chip>}
                {paso.presupuesto !== null && <span className="meta">hasta {paso.presupuesto} llamadas</span>}
              </div>
              {paso.detalle !== '' && <p className="paso-detalle">{paso.detalle}</p>}
              {paso.motivoFallo && <p className="paso-fallo">{paso.motivoFallo}</p>}
              {pistas.length > 0 && (
                <div className="pistas">
                  {pistas.map((p) => (
                    <MarcadorPista key={p.id} pista={p} abierta={abierta === p.id} onClick={() => setAbierta(abierta === p.id ? null : p.id)} />
                  ))}
                </div>
              )}
              {pistaAbierta !== null && pistaAbierta.pasoId === paso.id && (
                <Transcripcion pista={pistaAbierta} ahora={ahora} onDetener={onDetenerPista ? (ind) => onDetenerPista(pistaAbierta.id, ind) : undefined} />
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
