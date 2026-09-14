// El modo de la interfaz: "sencillo" ensena lo que decide una persona y pliega
// la ingenieria (hashes, tolerancias, kappa, entorno) tras una linea de
// resumen; "detalle" lo abre todo. Se recuerda en el navegador. Es la
// respuesta a "se me hace pesado": la profundidad sigue ahi, a un clic.

import { useSyncExternalStore } from 'react';

export type Modo = 'sencillo' | 'detalle';

const CLAVE = 'rosa.modo';
let modo: Modo = (() => {
  try {
    return localStorage.getItem(CLAVE) === 'detalle' ? 'detalle' : 'sencillo';
  } catch {
    return 'sencillo';
  }
})();
const oyentes = new Set<() => void>();

export function fijarModo(m: Modo): void {
  modo = m;
  try {
    localStorage.setItem(CLAVE, m);
  } catch {
    // Sin almacenamiento: dura lo que la pestana.
  }
  for (const o of oyentes) o();
}

export function useModo(): Modo {
  return useSyncExternalStore(
    (o) => {
      oyentes.add(o);
      return () => oyentes.delete(o);
    },
    () => modo,
    () => modo,
  );
}

/** La primera frase de una nota larga: lo que se ve en modo sencillo. */
export function primeraFrase(texto: string): string {
  const m = /^(.+?[.!?])(\s|$)/.exec(texto.trim());
  return m ? m[1]! : texto;
}
