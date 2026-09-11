// Diferencia por lineas entre dos versiones de un artefacto. Subsecuencia
// comun mas larga sobre lineas: para informes y tablas de unas decenas o
// cientos de lineas es instantaneo y da el resultado que una persona espera
// (lineas anadidas y quitadas, no caracteres sueltos).

export interface LineaDiff {
  tipo: 'igual' | 'anadida' | 'quitada';
  texto: string;
}

export function diferenciarLineas(antes: string, despues: string): LineaDiff[] {
  const a = antes === '' ? [] : antes.split('\n');
  const b = despues === '' ? [] : despues.split('\n');
  const n = a.length;
  const m = b.length;
  // lcs[i][j] = longitud de la subsecuencia comun de a[i..] y b[j..]
  const lcs: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i]![j] = a[i] === b[j] ? lcs[i + 1]![j + 1]! + 1 : Math.max(lcs[i + 1]![j]!, lcs[i]![j + 1]!);
    }
  }
  const salida: LineaDiff[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      salida.push({ tipo: 'igual', texto: a[i]! });
      i++;
      j++;
    } else if (lcs[i + 1]![j]! >= lcs[i]![j + 1]!) {
      salida.push({ tipo: 'quitada', texto: a[i]! });
      i++;
    } else {
      salida.push({ tipo: 'anadida', texto: b[j]! });
      j++;
    }
  }
  while (i < n) salida.push({ tipo: 'quitada', texto: a[i++]! });
  while (j < m) salida.push({ tipo: 'anadida', texto: b[j++]! });
  return salida;
}

/** Cuantas lineas cambiaron, para el resumen de una version. */
export function resumenDiff(lineas: LineaDiff[]): { anadidas: number; quitadas: number } {
  let anadidas = 0;
  let quitadas = 0;
  for (const l of lineas) {
    if (l.tipo === 'anadida') anadidas++;
    else if (l.tipo === 'quitada') quitadas++;
  }
  return { anadidas, quitadas };
}
