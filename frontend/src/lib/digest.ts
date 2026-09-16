// El resumen "mientras no estabas": qué cambió desde la última vez que la
// persona pulsó «Visto», para pintarlo al entrar y para mandarlo por Slack o
// correo. Es el patrón más repetido en agentes de larga duración (el recap de
// Claude Code, el "Return Moment" del marco Agentic UX, los ficheros de estado
// de Codex).
//
// Rehecho el 16 de septiembre de 2026: antes cada tarjeta decía lo mismo
// (cuántas decisiones esperan y el gasto) y no se cerraba con «Visto» porque
// las decisiones pendientes la mantenían viva. Ahora la tarjeta cuenta solo lo
// que pasó en la ventana (corridas cerradas, iteraciones con su hallazgo,
// hipótesis que subieron o bajaron de certeza, hipótesis nuevas, evidencia
// enlazada, vivero, Killer) y desaparece al pulsar «Visto»; lo que espera a la
// persona se ve en la tarjeta de cada investigación, que sí es permanente.

import type { EstadoRosa, Evento, TipoEvento } from '../datos/tipos';
import { CERTEZA_EVIDENCIA, DIRECCION_EVIDENCIA } from './etiquetas';
import { formatearDuracion, plural } from './formato';

/** Sin «Visto» previo, la ventana son los últimos siete días. */
export const VENTANA_SIN_VISITA_MS = 7 * 24 * 3_600_000;

/** Lo que merece una línea en el resumen. Los hechos nuevos no: en una
 *  iteración salen decenas y ahogan lo demás (se ven en el modelo de mundo). */
const TIPOS_QUE_IMPORTAN: ReadonlySet<TipoEvento> = new Set<TipoEvento>([
  'iteracion_terminada',
  'hipotesis_nueva',
  'hipotesis_decidida',
  'killer',
  'corrida_estado',
  'incidencia',
  'ranking_cambio',
  'vivero',
  'revision_automatica',
  'revision_registro',
  'analisis',
  'permiso_pendiente',
  'presupuesto',
  'retraccion',
  'vigilancia',
  'aprendizaje',
]);

const ORDEN_CERTEZA: Record<string, number> = { muy_baja: 0, baja: 1, moderada: 2, alta: 3 };

export interface Digest {
  /** La última visita marcada, o null si nunca se pulsó «Visto». */
  desde: number | null;
  /** Desde cuándo cuenta la ventana de verdad (la visita, o siete días). */
  ventanaDesde: number;
  /** Eventos que importan dentro de la ventana, del más reciente al más antiguo. */
  eventos: Evento[];
  iteraciones: number;
  hipotesisNuevas: number;
  decisiones: number;
  incidencias: number;
  /** Decisiones que esperan a una persona, con la edad de la más antigua. */
  esperan: { total: number; masAntiguaMs: number };
  lineas: string[];
  /** Si hay algo que contar: sin novedades la tarjeta no se pinta. */
  hayNovedades: boolean;
}

function cuenta(eventos: Evento[], tipo: TipoEvento): number {
  return eventos.filter((e) => e.tipo === tipo).length;
}

function recortar(t: string, n: number): string {
  const limpio = (t || '').replace(/\s+/g, ' ').trim();
  return limpio.length > n ? `${limpio.slice(0, n - 1).trimEnd()}…` : limpio;
}

function certeza(c: string): string {
  const g = CERTEZA_EVIDENCIA[c as keyof typeof CERTEZA_EVIDENCIA];
  return g ? g.etiqueta.replace('Certeza ', '') : c.replace('_', ' ');
}

/** Qué espera a una persona ahora mismo en la investigación. */
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
  const ventanaDesde = desde ?? ahora - VENTANA_SIN_VISITA_MS;
  const eventos = estado.eventos
    .filter((e) => e.investigacionId === investigacionId && e.t > ventanaDesde && TIPOS_QUE_IMPORTAN.has(e.tipo))
    .sort((a, b) => b.t - a.t);
  const corridas = estado.corridas.filter((c) => c.investigacionId === investigacionId).sort((a, b) => b.numero - a.numero);
  const idsCorridas = new Set(corridas.map((c) => c.id));
  const corrida = corridas[0];
  const hips = estado.hipotesis.filter((h) => h.investigacionId === investigacionId);
  const esperan = loQueEspera(estado, investigacionId, ahora);
  const lineas: string[] = [];

  // 1. Corridas que se cerraron en la ventana, con su motivo.
  for (const c of corridas) {
    if (c.terminadaEn !== null && c.terminadaEn > ventanaDesde) {
      lineas.push(`La corrida ${c.numero} ${c.estado === 'detenida' ? 'se detuvo' : 'terminó'}: ${recortar(c.motivoCierre ?? 'sin motivo registrado', 120)}`);
    }
  }
  // 2. Iteraciones terminadas, con el mensaje clave de la última.
  const its = estado.iteraciones.filter((it) => idsCorridas.has(it.corridaId) && it.terminadaEn !== null && it.terminadaEn > ventanaDesde).sort((a, b) => (b.terminadaEn ?? 0) - (a.terminadaEn ?? 0));
  if (its.length > 0) {
    const ult = its[0]!;
    const clave = ult.resumenLlano?.mensajesClave?.[0] ?? ult.resumenLlano?.queEncontro?.[0] ?? ult.resumen;
    lineas.push(`${plural(its.length, 'iteración terminada', 'iteraciones terminadas')}${clave ? `. La última: ${recortar(clave, 160)}` : ''}`);
  }
  // 3. Hipótesis que subieron o bajaron de certeza, o cambiaron de dirección.
  const conCambio = hips.filter((h) => h.conclusion?.cambio && h.conclusion.fecha > ventanaDesde);
  const deCerteza = conCambio.filter((h) => h.conclusion!.cambio!.de.certeza && h.conclusion!.cambio!.de.certeza !== h.conclusion!.certeza);
  for (const h of deCerteza.slice(0, 3)) {
    const de = h.conclusion!.cambio!.de.certeza!;
    const a = h.conclusion!.certeza;
    lineas.push(`«${recortar(h.titulo, 70)}» ${(ORDEN_CERTEZA[a] ?? 0) > (ORDEN_CERTEZA[de] ?? 0) ? 'subió' : 'bajó'} de certeza ${certeza(de)} a ${certeza(a)}`);
  }
  if (deCerteza.length > 3) lineas.push(`${deCerteza.length - 3} hipótesis más cambiaron de certeza`);
  const deDireccion = conCambio.filter((h) => h.conclusion!.cambio!.de.direccion && h.conclusion!.cambio!.de.direccion !== h.conclusion!.direccion && !deCerteza.includes(h));
  for (const h of deDireccion.slice(0, 2)) {
    const de = h.conclusion!.cambio!.de.direccion!;
    lineas.push(`«${recortar(h.titulo, 70)}» cambió de dirección: de «${DIRECCION_EVIDENCIA[de].etiqueta.toLowerCase()}» a «${DIRECCION_EVIDENCIA[h.conclusion!.direccion].etiqueta.toLowerCase()}»`);
  }
  // 4. Hipótesis nuevas, por título.
  const nuevas = hips.filter((h) => h.creadaEn > ventanaDesde && h.origen === 'rosa').sort((a, b) => b.creadaEn - a.creadaEn);
  if (nuevas.length > 0) {
    const titulos = nuevas.slice(0, 2).map((h) => `«${recortar(h.titulo, 60)}»`).join('; ');
    lineas.push(`${plural(nuevas.length, 'hipótesis nueva', 'hipótesis nuevas')}: ${titulos}${nuevas.length > 2 ? ` y ${nuevas.length - 2} más` : ''}`);
  }
  // 5. Evidencia enlazada a hipótesis que ya existían.
  const evidencia = eventos.filter((e) => e.tipo === 'revision_automatica' && e.texto.startsWith('Evidencia nueva'));
  if (evidencia.length > 0) {
    const enContra = evidencia.reduce((n, e) => n + Number(/(\d+) en contra/.exec(e.texto)?.[1] ?? 0), 0);
    lineas.push(`${plural(evidencia.length, 'hipótesis recibió evidencia nueva', 'hipótesis recibieron evidencia nueva')}${enContra > 0 ? ` (${plural(enContra, 'afirmación en contra', 'afirmaciones en contra')})` : ''}`);
  }
  // 6. Vivero: ideas que entran, nacen o salen.
  const entran = eventos.filter((e) => e.tipo === 'vivero' && e.texto.startsWith('Idea al vivero')).length;
  const salen = eventos.filter((e) => e.tipo === 'vivero' && e.texto.startsWith('Sale del vivero')).length;
  const nacen = eventos.filter((e) => e.tipo === 'hipotesis_nueva' && e.texto.startsWith('Nace del vivero')).length;
  const vivero = [entran > 0 ? plural(entran, 'idea entró al vivero', 'ideas entraron al vivero') : '', nacen > 0 ? plural(nacen, 'idea nació como hipótesis', 'ideas nacieron como hipótesis') : '', salen > 0 ? plural(salen, 'idea salió del vivero sin nacer', 'ideas salieron del vivero sin nacer') : ''].filter(Boolean);
  if (vivero.length > 0) lineas.push(vivero.join(', '));
  // 7. Killer, decisiones e incidencias.
  const killer = cuenta(eventos, 'killer');
  if (killer > 0) lineas.push(`El Killer emitió ${plural(killer, 'veredicto', 'veredictos')}`);
  const decisiones = cuenta(eventos, 'hipotesis_decidida');
  if (decisiones > 0) lineas.push(plural(decisiones, 'decisión registrada', 'decisiones registradas'));
  // 8. Incidencias sin resolver, lo que espera y el gasto: solo si hubo actividad
  // en la ventana (lo pendiente se ve siempre en la tarjeta de la investigación).
  const iteraciones = cuenta(eventos, 'iteracion_terminada');
  const hayNovedades = eventos.length > 0 || its.length > 0 || conCambio.length > 0 || nuevas.length > 0;
  const incidenciasPendientes = estado.incidencias.filter((i) => idsCorridas.has(i.corridaId) && i.estado === 'pendiente').length;
  if (hayNovedades && incidenciasPendientes > 0) lineas.push(plural(incidenciasPendientes, 'incidencia sin resolver', 'incidencias sin resolver'));
  if (hayNovedades && esperan.total > 0) {
    const edad = esperan.masAntiguaMs > 60_000 ? ` (la más antigua lleva ${formatearDuracion(esperan.masAntiguaMs)})` : '';
    lineas.push(`${plural(esperan.total, 'decisión espera', 'decisiones esperan')} tu respuesta${edad}`);
  }
  if (hayNovedades && corrida) {
    const pct = Math.round((corrida.gasto.llamadas / corrida.presupuesto.limiteLlamadas) * 100);
    const usd = (corrida.gasto as { usd?: number }).usd;
    lineas.push(`Gasto de la corrida ${corrida.numero}: ${corrida.gasto.llamadas} llamadas (${pct} % del tope)${typeof usd === 'number' && usd > 0 ? `, ${usd.toFixed(2)} USD` : ''}`);
  }
  return {
    desde,
    ventanaDesde,
    eventos,
    iteraciones,
    hipotesisNuevas: cuenta(eventos, 'hipotesis_nueva'),
    decisiones,
    incidencias: cuenta(eventos, 'incidencia'),
    esperan,
    lineas: lineas.slice(0, 8),
    hayNovedades,
  };
}

/** El mismo resumen como texto plano, para Slack o correo. */
export function digestComoTexto(d: Digest, tituloInvestigacion: string): string {
  const cabecera = `Rosa · ${tituloInvestigacion}`;
  const cuerpo = d.lineas.map((l) => `- ${l}`).join('\n');
  return `${cabecera}\n${cuerpo || '- Sin novedades'}`;
}
