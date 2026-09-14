// Legibilidad del árbol: al asentarse, las etiquetas de los nodos con texto
// (todo menos las fuentes) no deben montarse unas sobre otras. Emir, 14 de
// septiembre de 2026, ante una captura: "¿no consideras que están DEMASIADO
// pegados?". Se mide el número de pares de etiquetas cuyas cajas se solapan.
import { describe, expect, it } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import { anchoEtiqueta, construirArbol, paso, posicionInicial, type Grafo, type NodoArbol, type Posicion } from './arbol';

function asentar(g: Grafo, visibles: Set<string>) {
  const pos = new Map<string, Posicion>();
  let semilla = 1;
  for (const n of g.nodos) if (visibles.has(n.id)) pos.set(n.id, posicionInicial(g, pos, n.id, semilla++));
  let alfa = 1;
  while (alfa > 0.03) {
    for (let k = 0; k < 2; k++) paso(g, visibles, pos, alfa);
    alfa *= 0.975;
  }
  // Un rato en reposo, como en pantalla (la simulación se apaga a 0,03 pero
  // las restricciones de posición deben haber hecho ya su trabajo).
  for (let k = 0; k < 60; k++) paso(g, visibles, pos, 0.02);
  return pos;
}

/** Caja de la etiqueta: bajo el círculo, centrada, dos líneas como mucho. */
function caja(n: NodoArbol, p: Posicion) {
  const w = Math.min(anchoEtiqueta(n), 180);
  return { x0: p.x - w / 2, x1: p.x + w / 2, y0: p.y - 14, y1: p.y + 34 };
}

export function paresSolapados(g: Grafo, pos: Map<string, Posicion>): number {
  const nodos = g.nodos.filter((n) => pos.has(n.id) && n.tipo !== 'fuente');
  let solapes = 0;
  for (let i = 0; i < nodos.length; i++) {
    for (let j = i + 1; j < nodos.length; j++) {
      const a = caja(nodos[i]!, pos.get(nodos[i]!.id)!);
      const b = caja(nodos[j]!, pos.get(nodos[j]!.id)!);
      if (a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1) solapes++;
    }
  }
  return solapes;
}

describe('legibilidad del árbol', () => {
  it('en el árbol de muestra desplegado del todo, ninguna etiqueta se monta sobre otra', () => {
    const e = estadoDeMuestra();
    const inv = e.investigaciones[0]!;
    const g = construirArbol(e, inv);
    const visibles = new Set(g.nodos.map((n) => n.id));
    const pos = asentar(g, visibles);
    const solapes = paresSolapados(g, pos);
    console.log(`muestra: ${solapes} pares de etiquetas solapados entre ${g.nodos.filter((n) => n.tipo !== 'fuente').length} nodos con etiqueta`);
    expect(solapes).toBe(0);
  });
});
