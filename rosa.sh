#!/bin/zsh
# Arranca Rosa completa: el servidor con el bucle (8765) y la interfaz (5174),
# y abre el navegador. Ctrl+C para parar las dos cosas.
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "Falta .env con ROSA_GATEWAY_KEY (se copia del .env del RAG)."
  exit 1
fi
if [ ! -d frontend/node_modules ]; then
  echo "Instalando la interfaz por primera vez..."
  (cd frontend && npm install)
fi

export MLFLOW_DISABLE_AGENT_HINT=1
uv run python -m rosa.main &
SERVIDOR=$!
(cd frontend && npm run dev -- --host 127.0.0.1 >/dev/null 2>&1) &
INTERFAZ=$!

trap 'kill $SERVIDOR $INTERFAZ 2>/dev/null; wait $SERVIDOR $INTERFAZ 2>/dev/null; exit 0' INT TERM
sleep 4
open "http://localhost:5174" 2>/dev/null || true
echo "Rosa: servidor en http://127.0.0.1:8765, interfaz en http://localhost:5174. Ctrl+C para parar."
wait
