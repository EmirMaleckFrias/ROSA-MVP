# Imagen del sandbox de Rosa para analisis in silico. Sin red al ejecutar
# (docker run --network none). Solo las bibliotecas de analisis que el
# contrato de EscribirCodigo permite.
FROM python:3.12-slim
RUN pip install --no-cache-dir pandas==2.2.3 numpy==2.1.3 scipy==1.14.1 statsmodels==0.14.4
RUN useradd -m rosa
USER rosa
WORKDIR /trabajo
