# Sandbox de ROSA2018

Imagen Docker (o Apple `container`) donde corren los analisis in silico.
Se construye sola la primera vez que hace falta (`docker build -t
rosa-sandbox:1 rosa/sandbox`). Cada ejecucion arranca un contenedor nuevo
con `--network none`, memoria y CPU limitadas, el fichero de datos montado
en solo lectura y un directorio de trabajo temporal que se borra al
terminar. Ver `rosa/ejecucion.py`.
