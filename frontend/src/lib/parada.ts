// Que parte de una condicion de parada mide Rosa sola. Espejo de rosa/parada.py:
// misma regla en los dos lados, para que la interfaz lo muestre al escribirla.

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
  if (medibles.length === 0) return 'Rosa no puede medir esta condicion: la corrida sigue hasta que la detengas o hasta agotar el presupuesto de la mision.';
  let frase = `Rosa para sola al llegar a ${medibles.join(' o ')} (y al agotar el presupuesto de la mision)`;
  if (p.resto) frase += `. El resto ("${p.resto.slice(0, 80)}") lo decides tu con el boton de detener`;
  return `${frase}.`;
}
