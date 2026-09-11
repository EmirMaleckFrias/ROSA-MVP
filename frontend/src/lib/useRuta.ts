// La ruta actual como estado de React, leida del hash y actualizada al
// navegar. Las pantallas navegan con enlaces normales (href="#/...") o con
// `irA`, que escribe el hash; el navegador guarda el historial gratis.

import { useCallback, useEffect, useState } from 'react';
import { formatearRuta, parsearRuta, type Ruta } from './ruta';

export function useRuta(): [Ruta, (ruta: Ruta) => void] {
  const [ruta, setRuta] = useState<Ruta>(() => parsearRuta(window.location.hash));
  useEffect(() => {
    const alCambiar = () => setRuta(parsearRuta(window.location.hash));
    window.addEventListener('hashchange', alCambiar);
    return () => window.removeEventListener('hashchange', alCambiar);
  }, []);
  const irA = useCallback((destino: Ruta) => {
    window.location.hash = formatearRuta(destino);
  }, []);
  return [ruta, irA];
}
