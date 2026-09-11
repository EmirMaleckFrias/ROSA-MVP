// El resumen "mientras no estabas": que paso desde la ultima visita, para
// pintarlo al entrar y para mandarlo por Slack o correo. Es el patron mas
// repetido en agentes de larga duracion (el recap de Claude Code, el "Return
// Moment" del marco Agentic UX, los ficheros de estado de Codex).

import type { EstadoRosa, Evento, TipoEvento } from '../datos/tipos';
import { formatearDuracion, plural } from './formato';

export interface Digest {
  desde: number | null;
  eventos: Evento[];
  iteraciones: number;
  hipotesisNuevas: number;
  decisiones: number;
  incidencias: number;
  /** Decisiones que esperan a una persona, con la edad de la mas antigua. */
  esperan: { total: number; masAntiguaMs: number };
  lineas: string[];
}

function cuenta(eventos: Evento[], tipo: TipoEvento): number {
  return eventos.filter((e) => e.tipo === tipo).length;
}

/** Que espera a una persona ahora mismo en la investigacion. */
export function loQueEspera(estado: EstadoRosa, investigacionId: string, ahora: number): { total: number; masAntiguaMs: number } {
  const corridas = estado.corridas.filter((c) => c.investigacionId === investigacionId).map((c) => c.id);
  const fechas: number[] = [];
  for (const s of estado.solicitudes) if (corridas.includes(s.corridaId) && s.estado === 'pendiente') fechas.push(s.creadaEn);
  for (const i of estado.incidencias) if (corridas.includes(i.corridaId) && i.estado === 'pendiente') fechas.push(i.creadaEn);
  for (const h of estado.hipotesis) {
    if (h.investigacionId === investigacionId && (h.estado === 'propuesta' || h.estado === 'en_revision' || h.estado === 'refinar')) fechas.push(h.creadaEn);
  }
  for (const it of estado.iteraciones) {
    if (!it.planAprobado && corridas.includes(it.corridaId)) fechas.push(it.planPropuestoEn);
  }
  const masAntigua = fechas.length > 0 ? Math.min(...fechas) : ahora;
  return { total: fechas.length, masAntiguaMs: fechas.length > 0 ? ahora - masAntigua : 0 };
}

export function digest(estado: EstadoRosa, investigacionId: string, ahora: number): Digest {
  const desde = estado.ultimaVisita;
  const eventos = estado.eventos.filter((e) => e.investigacionId === investigacionId && (desde === null || e.t > desde)).sort((a, b) => b.t - a.t);
  const iteraciones = cuenta(eventos, 'iteracion_terminada');
  const hipotesisNuevas = cuenta(eventos, 'hipotesis_nueva');
  const decisiones = cuenta(eventos, 'hipotesis_decidida');
  const incidencias = cuenta(eventos, 'incidencia');
  const esperan = loQueEspera(estado, investigacionId, ahora);
  const corrida = estado.corridas.filter((c) => c.investigacionId === investigacionId).sort((a, b) => b.numero - a.numero)[0];

  const lineas: string[] = [];
  if (iteraciones > 0) lineas.push(plural(iteraciones, 'iteracion terminada', 'iteraciones terminadas'));
  if (hipotesisNuevas > 0) lineas.push(plural(hipotesisNuevas, 'hipotesis nueva en la cola', 'hipotesis nuevas en la cola'));
  const ranking = eventos.filter((e) => e.tipo === 'ranking_cambio');
  if (ranking.length > 0) lineas.push(ranking[0]!.texto);
  if (decisiones > 0) lineas.push(plural(decisiones, 'decision registrada', 'decisiones registradas'));
  if (incidencias > 0) lineas.push(plural(incidencias, 'incidencia que necesita respuesta', 'incidencias que necesitan respuesta'));
  if (esperan.total > 0) {
    const edad = esperan.masAntiguaMs > 60_000 ? ` (la mas antigua lleva ${formatearDuracion(esperan.masAntiguaMs)})` : '';
    lineas.push(`${plural(esperan.total, 'decision espera', 'decisiones esperan')} tu respuesta${edad}`);
  }
  if (corrida) {
    const pct = Math.round((corrida.gasto.llamadas / corrida.presupuesto.limiteLlamadas) * 100);
    lineas.push(`Gasto: ${corrida.gasto.llamadas} de ${corrida.presupuesto.limiteLlamadas} llamadas (${pct} %)`);
  }
  return { desde, eventos, iteraciones, hipotesisNuevas, decisiones, incidencias, esperan, lineas };
}

/** El mismo resumen como texto plano, para Slack o correo. */
export function digestComoTexto(d: Digest, tituloInvestigacion: string): string {
  const cabecera = `Rosa · ${tituloInvestigacion}`;
  const cuerpo = d.lineas.map((l) => `- ${l}`).join('\n');
  return `${cabecera}\n${cuerpo || '- Sin novedades'}`;
}
