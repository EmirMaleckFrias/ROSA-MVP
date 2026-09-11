import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// En desarrollo, Vite sirve la interfaz en el 5174 y reenvia /api al servidor
// de Rosa (FastAPI en el 8765, `uv run python -m rosa.main`). Si el servidor
// no esta, la interfaz cae a los datos de muestra con la corrida simulada.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true },
    },
  },
});
