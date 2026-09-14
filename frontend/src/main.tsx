import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource-variable/inter';
import App from './App';
import { Limite } from './componentes/Limite';
import { conectar } from './datos/almacen';
import { observarSistema } from './lib/theme';
import './styles.css';

// El tema ya lo aplico el script inline de index.html. Esto solo engancha los
// cambios del sistema para que la opcion 'sistema' siga al SO en vivo.
observarSistema();

// Primero el servidor de Rosa (/api); si no responde, la muestra simulada.
void conectar();

const raiz = document.getElementById('root');
if (!raiz) throw new Error('No se encontró el elemento #root');

createRoot(raiz).render(
  <StrictMode>
    <Limite ambito="Rosa">
      <App />
    </Limite>
  </StrictMode>,
);
