"""Los tests no salen a la red: el reranker y el índice semántico del gateway
quedan apagados salvo que un test los encienda con monkeypatch sobre el
módulo (rosa.reranker.MODELO, rosa.indice_semantico.MODELO)."""
import os

os.environ["ROSA_RERANK_MODELO"] = ""
os.environ["ROSA_EMBEDDINGS_MODELO"] = ""
