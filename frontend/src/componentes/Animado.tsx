// Piezas de movimiento reutilizables: aparecer, listas con escalonado y
// salida, y el contador que corre hasta la cifra. Todo respeta el movimiento
// reducido: entonces solo hay fundidos y los numeros cambian de golpe.

import { AnimatePresence, animate, motion, useMotionValue, type TargetAndTransition } from 'motion/react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { aparecer, lista, RESORTE, useMovimientoReducido } from '../lib/movimiento';

/** Envuelve un bloque para que entre suavemente al montarse. */
export function Aparece({ children, className, retraso = 0, como = 'div' }: { children: ReactNode; className?: string; retraso?: number; como?: 'div' | 'section' | 'li' | 'article' }) {
  const reducido = useMovimientoReducido();
  const Tag = motion[como];
  return (
    <Tag className={className} initial={reducido ? { opacity: 0 } : 'oculto'} animate={reducido ? { opacity: 1 } : 'visible'} variants={reducido ? undefined : aparecer} transition={{ delay: retraso }}>
      {children}
    </Tag>
  );
}

/** Una lista cuyos elementos entran escalonados, se reordenan con un resorte
 *  y salen con la animacion que se les indique (por decision, por ejemplo). */
export function ListaAnimada({ children, className, como = 'div' }: { children: ReactNode; className?: string; como?: 'div' | 'ul' | 'ol' }) {
  const Tag = motion[como];
  return (
    <Tag className={className} variants={lista} initial="oculto" animate="visible">
      <AnimatePresence initial={false} mode="popLayout">
        {children}
      </AnimatePresence>
    </Tag>
  );
}

/** Un elemento de ListaAnimada. `salida` es lo que hace al desaparecer. */
export function ElementoAnimado({ children, className, salida, como = 'div', layout = true }: { children: ReactNode; className?: string; salida?: TargetAndTransition; como?: 'div' | 'li' | 'a' | 'article'; layout?: boolean }) {
  const reducido = useMovimientoReducido();
  const Tag = motion[como];
  return (
    <Tag className={className} layout={reducido ? false : layout} variants={reducido ? undefined : aparecer} initial={reducido ? { opacity: 0 } : undefined} animate={reducido ? { opacity: 1 } : undefined} exit={reducido ? { opacity: 0 } : (salida ?? { opacity: 0, y: -6, transition: { duration: 0.15 } })} transition={RESORTE}>
      {children}
    </Tag>
  );
}

/** Un numero que corre hasta su valor cuando cambia (el Elo, un recuento).
 *  El ojo sigue el cambio y entiende la direccion sin leer el signo. */
export function Contador({ valor, decimales = 0, className, sufijo = '' }: { valor: number; decimales?: number; className?: string; sufijo?: string }) {
  const reducido = useMovimientoReducido();
  const mv = useMotionValue(valor);
  const [texto, setTexto] = useState(valor.toFixed(decimales));
  const anterior = useRef(valor);
  useEffect(() => {
    if (reducido || !Number.isFinite(valor)) {
      setTexto(Number.isFinite(valor) ? valor.toFixed(decimales) : '');
      anterior.current = valor;
      return;
    }
    const controles = animate(mv, valor, {
      duration: Math.min(0.9, 0.3 + Math.abs(valor - anterior.current) / 400),
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setTexto(v.toFixed(decimales)),
    });
    anterior.current = valor;
    return () => controles.stop();
  }, [valor, decimales, reducido, mv]);
  return (
    <span className={className} style={{ fontVariantNumeric: 'tabular-nums' }}>
      {texto}
      {sufijo}
    </span>
  );
}

/** Marca un cambio de estado con un destello breve del fondo (cuando cambia
 *  `clave`). Sirve para que una fila que cambio de veredicto se note. */
export function Destello({ clave, children, className }: { clave: string | number; children: ReactNode; className?: string }) {
  const reducido = useMovimientoReducido();
  const [activo, setActivo] = useState(false);
  const primera = useRef(true);
  useEffect(() => {
    if (primera.current) {
      primera.current = false;
      return;
    }
    if (reducido) return;
    setActivo(true);
    const t = window.setTimeout(() => setActivo(false), 700);
    return () => window.clearTimeout(t);
  }, [clave, reducido]);
  return <div className={`${className ?? ''} ${activo ? 'destello' : ''}`.trim()}>{children}</div>;
}
