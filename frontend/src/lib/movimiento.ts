// El sistema de movimiento de Rosa. Una sola regla: el movimiento explica
// algo (de donde viene una cosa, a donde va, que cambio); nunca decora. Las
// duraciones son cortas (150 a 400 ms) para que envejezcan bien, y todo
// respeta la preferencia de movimiento reducido del navegador.

import { useReducedMotion } from 'motion/react';
import type { TargetAndTransition, Transition, Variants } from 'motion/react';

/** Duraciones en segundos, alineadas con los tokens de styles.css. */
export const DUR = { rapida: 0.15, media: 0.24, lenta: 0.4 } as const;

/** Salida suave, la curva por defecto de todo lo que aparece o se mueve. */
export const SUAVE: Transition = { duration: DUR.media, ease: [0.22, 1, 0.36, 1] };

/** Un resorte contenido para lo que "aterriza" (tarjetas que cambian de sitio). */
export const RESORTE: Transition = { type: 'spring', stiffness: 380, damping: 32, mass: 0.9 };

/** Aparecer desde abajo: lo que entra en pantalla por primera vez. */
export const aparecer: Variants = {
  oculto: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: SUAVE },
  salida: { opacity: 0, y: -6, transition: { duration: DUR.rapida } },
};

/** Lista con escalonado: cada hijo entra 40 ms despues del anterior. */
export const lista: Variants = {
  oculto: {},
  visible: { transition: { staggerChildren: 0.04, delayChildren: 0.02 } },
};

/** Como sale una tarjeta segun la decision tomada: aprobar la desplaza a la
 *  derecha (sigue adelante), descartar la encoge y apaga, refinar la devuelve
 *  hacia arriba (vuelve a Rosa). El gesto ensena la regla sin leerla. */
export const salidaPorDecision: Record<'aprobar' | 'descartar' | 'refinar' | 'neutra', TargetAndTransition> = {
  aprobar: { opacity: 0, x: 56, transition: { duration: DUR.lenta, ease: [0.22, 1, 0.36, 1] } },
  descartar: { opacity: 0, scale: 0.92, filter: 'grayscale(1)', transition: { duration: DUR.lenta } },
  refinar: { opacity: 0, y: -28, transition: { duration: DUR.lenta } },
  neutra: { opacity: 0, transition: { duration: DUR.rapida } },
};

/** Cambio de pagina: fundido corto con un desplazamiento minimo. */
export const pagina: Variants = {
  oculto: { opacity: 0, y: 6 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.2, ease: [0.22, 1, 0.36, 1] } },
  salida: { opacity: 0, transition: { duration: 0.12 } },
};

/** Hook: true si la persona pidio movimiento reducido. Los componentes lo
 *  usan para sustituir desplazamientos por fundidos y quitar los pulsos. */
export function useMovimientoReducido(): boolean {
  return useReducedMotion() ?? false;
}
