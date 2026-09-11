---
name: usar-siempre-el-ai-gateway-de-vercel
description: "En FIREtech-RAG todas las llamadas a modelos van por el AI Gateway de Vercel, nunca por la API de OpenAI, y el coste por token no es criterio de decisión."
metadata: 
  node_type: memory
  pinned: true
  originSessionId: ae861247-e51d-4381-bb02-daeae35a261b
  modified: 2026-09-04T12:52:43.255Z
---

# En FIREtech-RAG el proveedor es el AI Gateway de Vercel, no OpenAI

la persona responsable lo dijo como norma explícita: *"siempre usa la api de vercel bro, nunca la
de open ai, es mas, elimina la de open ai"*. El motivo es que **la empresa le
proporciona el AI Gateway de Vercel**, así que las llamadas por ahí las cubre
la empresa y las que van directas a OpenAI las paga alguien más. No es solo
una preferencia de configuración: pidió expresamente eliminar la clave de
OpenAI del proyecto, no dejarla como respaldo.

En la práctica esto significa que `backend/.env` y las variables de entorno del
proyecto en Vercel deben llevar una clave `vck_…` del gateway junto a
`OPENAI_BASE_URL=https://ai-gateway.vercel.sh/v1`, y que los tres modelos van
prefijados con el proveedor: `openai/gpt-5.4`, `openai/gpt-5.4-mini`,
`openai/text-embedding-3-large`. El código ya lo soporta:
`Settings.openai_base_url` existe en `backend/app/config.py` y
`app/services/openai_client.py` lo pasa al cliente.

De aquí se sigue algo que ya me corrigió antes por separado: **el coste por
token no es un criterio de decisión en este proyecto**. Hay que argumentar por
calidad, latencia y capacidad. A veces la conclusión se invierte respecto a lo
razonable en otros proyectos: `config.py` deja `rerank_model` en el modelo
pequeño porque el grande era "unas 5 veces más caro por token", pero aquí lo
correcto es rerankear con el grande. El límite real que queda es el presupuesto
de tiempo del agente, porque la función serverless de Vercel muere a los 300 s.

Un aviso para no repetir un error ya cometido: al recuperar credenciales de las
variables de entorno de Vercel aparecerá una clave `sk-proj-…` de OpenAI, y es
tentador usarla porque "es la que está en producción y funciona". No hay que
hacerlo. En septiembre de 2026 esa cuenta de OpenAI se quedó sin saldo
(`429 credit_balance_exhausted`) y tumbó el chat y los embeddings a la vez, en
local y en producción, precisamente por estar usando la vía equivocada.
