import { useEffect, useState } from 'react';

/** Hora actual, releida cada `intervaloMs`. Para los "hace N min". */
export function useAhora(intervaloMs = 15_000): number {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setAhora(Date.now()), intervaloMs);
    return () => window.clearInterval(t);
  }, [intervaloMs]);
  return ahora;
}
