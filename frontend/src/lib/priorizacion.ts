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
  analisis_invalido: 'Analisis invalido segun el auditor',
  sin_experimento_interpretable: 'Sin experimento interpretable',
  descartada_por_killer: 'Descartada en este contexto',
  fuente_retractada: 'Depende de una fuente retractada',
};

export const EXPLICACION_BLOQUEO: Record<Bloqueo, string> = {
  trazabilidad_insuficiente: 'No hay afirmaciones sostenidas por su fuente, o alguna afirmacion esta bloqueada (cita que no resuelve, dato de otra entidad, ausencia desmentida).',
  datos_no_autorizados: 'Algun analisis uso un dataset sin contrato aprobado o sin autorizacion de uso con IA.',
  analisis_invalido: 'El auditor independiente (Killer II) dio por no valido el ultimo analisis con datos.',
  sin_experimento_interpretable: 'El experimento no dice que resultado la confirmaria y cual la refutaria.',
  descartada_por_killer: 'El Killer o una persona la descarto en este contexto.',
  fuente_retractada: 'Una de sus fuentes esta retractada.',
};

type Estado = Pick<EstadoRosa, 'investigaciones' | 'planesAnalisis' | 'ejecuciones' | 'hipotesis'>;

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
  return b;
}

/** Las que hoy irian al laboratorio, en orden: sin bloqueos, con el Killer
 *  en "avanzar", por Elo, sin repetir cluster mientras haya otros. */
export function candidatos(estado: Estado, investigacionId: string, maximo = MAX_CANDIDATOS): Hipotesis[] {
  const vivas = estado.hipotesis
    .filter((h) => h.investigacionId === investigacionId && h.estado !== 'descartada' && h.decisionKiller === 'avanzar' && bloqueosDe(estado, h).length === 0)
    .sort((a, b) => b.elo - a.elo || a.creadaEn - b.creadaEn);
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
