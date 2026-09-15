import { useEffect, useState } from 'react';

/** Reloj local para duraciones en vivo, independiente del flujo del servidor. */
export function useAhora(intervaloMs = 1_000): number {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    const actualizar = () => setAhora(Date.now());
    const alVolver = () => {
      if (document.visibilityState === 'visible') actualizar();
    };
    const t = window.setInterval(actualizar, intervaloMs);
    document.addEventListener('visibilitychange', alVolver);
    window.addEventListener('focus', actualizar);
    return () => {
      window.clearInterval(t);
      document.removeEventListener('visibilitychange', alVolver);
      window.removeEventListener('focus', actualizar);
    };
  }, [intervaloMs]);
  return ahora;
}
