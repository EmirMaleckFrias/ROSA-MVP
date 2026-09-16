// Priorizacion con bloqueos no compensables y diversidad (ROSA2018, etapa
// 8). Misma regla que `rosa/priorizacion.py`: una hipotesis con un bloqueo
// no es candidata al laboratorio aunque gane todos los debates; entre las
// que no tienen bloqueos y el Killer dejo avanzar, se eligen hasta N por
// Elo sin repetir cluster mientras haya otros. Sin React: lo prueba vitest.

import type { Bloqueo, EstadoRosa, Hipotesis } from '../datos/tipos';
import { VEREDICTO } from './etiquetas';

export const MAX_CANDIDATOS = 3;

export const ETIQUETA_BLOQUEO: Record<Bloqueo, string> = {
  trazabilidad_insuficiente: 'Trazabilidad insuficiente',
  datos_no_autorizados: 'Datos no autorizados',
  analisis_invalido: 'Análisis inválido según el auditor',
  sin_experimento_interpretable: 'Sin experimento interpretable',
  descartada_por_killer: 'Descartada en este contexto',
  fuente_retractada: 'Depende de una fuente retractada',
  revision_registro_abierta: 'Hallazgo grave del revisor sin atender',
  dependencia_pendiente: 'Depende de algo que cambió y no se revisó',
};

export const EXPLICACION_BLOQUEO: Record<Bloqueo, string> = {
  trazabilidad_insuficiente: 'No hay afirmaciones sostenidas por su fuente, o alguna afirmación está bloqueada (cita que no resuelve, dato de otra entidad, ausencia desmentida).',
  datos_no_autorizados: 'Algún análisis uso un dataset sin contrato aprobado o sin autorización de uso con IA.',
  analisis_invalido: 'El auditor independiente (Killer II) dio por no válido el último análisis con datos.',
  sin_experimento_interpretable: 'El experimento no dice que resultado la confirmaría y cual la refutaría.',
  descartada_por_killer: 'El Killer o una persona la descarto en este contexto.',
  fuente_retractada: 'Una de sus fuentes está retractada.',
  revision_registro_abierta: 'El revisor de registro encontró algo grave (un identificador que no está en el registro, una ejecución afirmada y no completada, un recuento que no cuadra) en el dossier o en la última iteración cerrada, y nadie lo atendió todavía.',
  dependencia_pendiente: 'Algo de lo que depende cambió (una fuente se retractó, un hecho del modelo de mundo fue sustituido o contradicho) y Rosa todavía no volvió a concluirla ni una persona la revisó.',
};

type Estado = Pick<EstadoRosa, 'investigaciones' | 'planesAnalisis' | 'ejecuciones' | 'hipotesis'> & Partial<Pick<EstadoRosa, 'artefactos' | 'corridas' | 'iteraciones'>>;

export function bloqueosDe(estado: Estado, h: Hipotesis): Bloqueo[] {
  const b: Bloqueo[] = [];
  const sostenidas = h.afirmaciones.filter((a) => a.veredicto === 'sostenida' || a.veredicto === 'parcial');
  if (sostenidas.length === 0 || h.afirmaciones.some((a) => VEREDICTO[a.veredicto].bloquea)) b.push('trazabilidad_insuficiente');
  const inv = estado.investigaciones.find((i) => i.id === h.investigacionId);
  const datasets = new Map((inv?.datasets ?? []).map((d) => [d.id, d]));
  const planes = new Map((estado.planesAnalisis ?? []).map((p) => [p.id, p]));
  const ejecuciones = (estado.ejecuciones ?? []).filter((x) => x.hipotesisId === h.id);
  for (const x of ejecuciones) {
    const plan = planes.get(x.planId);
    const ds = plan ? datasets.get(plan.datasetId) : undefined;
    if (!ds || ds.estado !== 'aprobado' || ds.procedencia?.usoIAAutorizado !== 'si') {
      b.push('datos_no_autorizados');
      break;
    }
  }
  const auditadas = ejecuciones.filter((x) => x.auditoria);
  const ultima = auditadas[auditadas.length - 1];
  if (ultima && ultima.auditoria?.veredicto === 'no_valido') b.push('analisis_invalido');
  const x = h.experimento;
  // Interpretable: criterios separados, o un prerregistro congelado con el esquema anterior.
  const criterios = !!x && (x.confirma ?? '').trim() !== '' && (x.refuta ?? '').trim() !== '';
  const prerregistradoAntiguo = !!x && !!x.prerregistradoEn && (x.ensayo ?? '').trim() !== '';
  if (!x || (!criterios && !prerregistradoAntiguo)) b.push('sin_experimento_interpretable');
  if (h.estado === 'descartada' || h.decisionKiller === 'descartar_en_contexto') b.push('descartada_por_killer');
  if (h.procedencia.fuentes.some((f) => f.retraccion === 'retractado')) b.push('fuente_retractada');
  if (revisionRegistroAbierta(estado, h)) b.push('revision_registro_abierta');
  // Propagación de dependencias: misma regla que rosa/priorizacion.py.
  if (h.pendienteRevision) b.push('dependencia_pendiente');
  return b;
}

/** Puerta de publicación: un hallazgo grave y abierto del revisor de registro,
 *  en el dossier de la hipótesis o en la última iteración cerrada de su
 *  investigación, retiene la candidatura. Misma regla que rosa/priorizacion.py. */
export function revisionRegistroAbierta(estado: Estado, h: Hipotesis): boolean {
  const graveAbierto = (hallazgos: { estado?: string; gravedad?: string }[] | undefined | null) => (hallazgos ?? []).some((x) => x.estado === 'abierto' && x.gravedad === 'alta');
  if (h.dossierArtefactoId) {
    const art = (estado.artefactos ?? []).find((a) => a.id === h.dossierArtefactoId);
    const revision = art?.versiones[art.versiones.length - 1]?.procedencia?.revision;
    if (art && graveAbierto(revision?.hallazgos)) return true;
  }
  const corridas = new Set((estado.corridas ?? []).filter((c) => c.investigacionId === h.investigacionId).map((c) => c.id));
  const cerradas = (estado.iteraciones ?? []).filter((it) => corridas.has(it.corridaId) && it.terminadaEn !== null);
  if (cerradas.length === 0) return false;
  const ultima = cerradas.reduce((m, it) => ((it.terminadaEn ?? 0) > (m.terminadaEn ?? 0) ? it : m));
  return graveAbierto(ultima.revisionRegistro?.hallazgos as { estado?: string; gravedad?: string }[] | undefined);
}

/** Las que hoy irian al laboratorio, en orden: sin bloqueos, con el Killer
 *  en "avanzar", por Elo, sin repetir cluster mientras haya otros. */
export function candidatos(estado: Estado, investigacionId: string, maximo = MAX_CANDIDATOS): Hipotesis[] {
  const vivas = estado.hipotesis
    .filter((h) => h.investigacionId === investigacionId && h.estado !== 'descartada' && h.decisionKiller === 'avanzar' && bloqueosDe(estado, h).length === 0)
    .sort((a, b) => (b.bt?.fuerza ?? b.elo) - (a.bt?.fuerza ?? a.elo) || a.creadaEn - b.creadaEn);
  const elegidas: Hipotesis[] = [];
  const clusters = new Set<string>();
  const pendientes = [...vivas];
  while (pendientes.length > 0 && elegidas.length < maximo) {
    const idx = pendientes.findIndex((h) => !clusters.has(h.cluster.toLowerCase()));
    const siguiente = pendientes.splice(idx === -1 ? 0 : idx, 1)[0]!;
    elegidas.push(siguiente);
    clusters.add(siguiente.cluster.toLowerCase());
  }
  return elegidas;
}

/** Cohortes distintas entre las fuentes: dos articulos de la misma cohorte
 *  son una sola evidencia, no dos. */
export function cohortesDe(h: Pick<Hipotesis, 'procedencia'>): string[] {
  const vistas: string[] = [];
  for (const f of h.procedencia.fuentes) {
    const c = (f.cohorte ?? '').trim().toLowerCase();
    if (c && !vistas.includes(c)) vistas.push(c);
  }
  return vistas;
}
