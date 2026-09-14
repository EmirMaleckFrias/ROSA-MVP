// Que parte de una condicion de parada mide Rosa sola. Espejo de rosa/parada.py:
// misma regla en los dos lados, para que la interfaz lo muestre al escribirla.

import type { CondicionAutomatizada } from '../datos/tipos';

export function partesAutomatizadas(texto: string): CondicionAutomatizada {
  const t = (texto ?? '').toLowerCase();
  const salida: CondicionAutomatizada = { iteraciones: null, tiempo: null, llamadas: null, resto: '', automatizada: false };
  let resto = t;
  let m = /(\d+)\s*iteraci/.exec(t);
  if (m) {
    salida.iteraciones = Number(m[1]);
    resto = resto.replace(m[0], ' ');
  }
  m = /(\d+(?:[.,]\d+)?)\s*(min\b|minuto|hora|h\b|dia|día)/.exec(t);
  if (m) {
    const u = m[2]!;
    salida.tiempo = `${m[1]} ${u.startsWith('min') ? 'min' : u === 'h' || u.startsWith('hora') ? 'h' : 'd'}`;
    resto = resto.replace(m[0], ' ');
  }
  m = /(\d+)\s*llamadas/.exec(t);
  if (m) {
    salida.llamadas = Number(m[1]);
    resto = resto.replace(m[0], ' ');
  }
  resto = resto.replace(/\b(o|y|u|e|cuando|hasta|tras|despues|después|de|la|el|los|las|corrida|iteraciones|al|llegar|a|se|cumplan)\b/g, ' ');
  resto = resto.replace(/[^\wáéíóúñ]+/g, ' ').trim();
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
