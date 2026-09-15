// Que parte de una condicion de parada mide Rosa sola. Espejo de rosa/parada.py:
// misma regla en los dos lados, para que la interfaz lo muestre al escribirla.

import type { ParadaCorrida } from '../datos/tipos';
import type { CondicionAutomatizada } from '../datos/tipos';

export function partesAutomatizadas(texto: string): CondicionAutomatizada {
  const t = (texto ?? '').toLowerCase();
  const salida: CondicionAutomatizada = { iteraciones: null, tiempo: null, llamadas: null, resto: '', automatizada: false };
  let resto = t;
  let m = /(\d+)\s*iteraci\w*/.exec(t);
  if (m) {
    salida.iteraciones = Number(m[1]);
    resto = resto.replace(m[0], ' ');
  }
  m = /(\d+(?:[.,]\d+)?)\s*(min\b|minutos?|horas?|h\b|dias?|días?)/.exec(t);
  if (m) {
    const u = m[2]!;
    salida.tiempo = `${m[1]} ${u.startsWith('min') ? 'min' : u === 'h' || u.startsWith('hora') ? 'h' : 'd'}`;
    resto = resto.replace(m[0], ' ');
  }
  m = /(\d+)\s*llamadas?/.exec(t);
  if (m) {
    salida.llamadas = Number(m[1]);
    resto = resto.replace(m[0], ' ');
  }
  // El resto se conserva tal como lo escribio la persona: solo se limpian los
  // conectores sueltos de los bordes y los espacios dobles.
  resto = resto.replace(/\s+/g, ' ').replace(/^[\s,;.]+|[\s,;.]+$/g, '');
  resto = resto.replace(/^(o|y|u|e|,|;)\s+/, '').replace(/\s+(o|y|u|e)$/, '').replace(/^[\s,;.]+|[\s,;.]+$/g, '');
  salida.resto = resto.length >= 4 ? resto : '';
  salida.automatizada = salida.iteraciones !== null || salida.tiempo !== null || salida.llamadas !== null;
  return salida;
}

export function textoAutomatizacion(p: CondicionAutomatizada): string {
  const medibles: string[] = [];
  if (p.iteraciones !== null) medibles.push(`${p.iteraciones} iteraciones`);
  if (p.tiempo) medibles.push(`${p.tiempo} de corrida`);
  if (p.llamadas !== null) medibles.push(`${p.llamadas} llamadas`);
  if (medibles.length === 0) return 'Rosa no puede medir esta condición: la corrida sigue hasta que la detengas o hasta agotar el presupuesto de la misión.';
  let frase = `Rosa para sola al llegar a ${medibles.join(' o ')} (y al agotar el presupuesto de la mision)`;
  if (p.resto) frase += `. El resto ("${p.resto.slice(0, 80)}") lo decides tu con el boton de detener`;
  return `${frase}.`;
}


// ---------------------------------------------------------------------------
// La parada propia de una corrida (15 de septiembre de 2026): lo que la
// persona fija al crearla (horas, iteraciones, llamadas, texto) y que la
// detiene con lo que llegue primero, además de la condición de parada de la
// investigación. Espejo de rosa/parada.py (normalizar_parada, resumen_parada).
// ---------------------------------------------------------------------------

const LIMITES_PARADA: Record<'horas' | 'iteraciones' | 'llamadas', [number, number]> = { horas: [0.05, 24 * 14], iteraciones: [1, 200], llamadas: [10, 100_000] };

export interface ParadaBorrador {
  horas: string;
  iteraciones: string;
  llamadas: string;
  texto: string;
}

export const BORRADOR_VACIO: ParadaBorrador = { horas: '', iteraciones: '', llamadas: '', texto: '' };

function numeroParada(v: string, clave: 'horas' | 'iteraciones' | 'llamadas'): number | null {
  const n = Number(v.replace(',', '.'));
  if (!v.trim() || !Number.isFinite(n) || n <= 0) return null;
  const [minimo, maximo] = LIMITES_PARADA[clave];
  const acotado = Math.max(minimo, Math.min(maximo, n));
  return clave === 'horas' ? Math.round(acotado * 100) / 100 : Math.floor(acotado);
}

/** Del formulario a la parada que viaja al servidor; null si no se fijó nada. */
export function normalizarParada(b: ParadaBorrador): ParadaCorrida | null {
  const p: ParadaCorrida = { horas: numeroParada(b.horas, 'horas'), iteraciones: numeroParada(b.iteraciones, 'iteraciones'), llamadas: numeroParada(b.llamadas, 'llamadas'), texto: b.texto.trim().slice(0, 300) };
  if (p.horas === null && p.iteraciones === null && p.llamadas === null && !p.texto) return null;
  return p;
}

export function borradorDe(p: ParadaCorrida | null | undefined): ParadaBorrador {
  if (!p) return { ...BORRADOR_VACIO };
  return { horas: p.horas === null ? '' : String(p.horas), iteraciones: p.iteraciones === null ? '' : String(p.iteraciones), llamadas: p.llamadas === null ? '' : String(p.llamadas), texto: p.texto ?? '' };
}

function horasTexto(h: number): string {
  if (h < 1) {
    const m = Math.round(h * 60);
    return m === 1 ? '1 minuto' : `${m} minutos`;
  }
  return `${h} ${h === 1 ? 'hora' : 'horas'}`;
}

/** "2 horas o 6 iteraciones, lo que llegue primero". Vacío sin parada. */
export function resumenParada(p: ParadaCorrida | null | undefined): string {
  if (!p) return '';
  const partes: string[] = [];
  if (p.horas) partes.push(horasTexto(p.horas));
  if (p.iteraciones) partes.push(`${p.iteraciones} ${p.iteraciones === 1 ? 'iteración' : 'iteraciones'}`);
  if (p.llamadas) partes.push(`${p.llamadas} llamadas al modelo`);
  if (p.texto) partes.push(`«${p.texto}»`);
  if (partes.length === 0) return '';
  if (partes.length === 1) return partes[0] ?? '';
  const ultima = partes[partes.length - 1] ?? '';
  return `${partes.slice(0, -1).join(', ')} o ${ultima}, lo que llegue primero`;
}
