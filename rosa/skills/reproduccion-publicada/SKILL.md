---
name: reproduccion-publicada
description: Como reproducir una cifra publicada dentro de la puerta de reproduccion: leer los metodos completos, congelar la definicion exacta de la cifra, no cambiar el criterio despues, imprimir valor_reproducido. Se activa con reproduccion, reproducir, cifra publicada, tolerancia, puerta.
contexto: analisis
activa_si: reproduccion, reproducir, cifra publicada, valor_reproducido, tolerancia, puerta
---

# Reproducir una cifra publicada

1. La cifra a reproducir, su definicion y la tolerancia se congelan antes
   de ejecutar. Si el codigo no las alcanza, se corrige el codigo o el
   preprocesado, nunca el criterio.
2. Leer los metodos, no el resumen: el resumen de Blalock 2004 daba un
   metodo que no reproducia la cifra; el algoritmo de la figura 1 y los
   metodos si.
3. Ambiguedades del texto (que arrays para elegir la sonda, que escala): se
   elige la opcion mas fiel al articulo, se deja en un comentario y se
   calcula. `NO_EVALUABLE` solo por condiciones de los datos.
4. Imprimir siempre `RESULTADO valor_reproducido=<numero>` con la misma
   definicion que la cifra publicada, mas las cifras intermedias que
   permitan ver donde diverge si falla (n por grupo, sondas elegidas).
5. Superada o fallida, la reproduccion queda a la vista con su valor; los
   intentos fallidos no se borran.
