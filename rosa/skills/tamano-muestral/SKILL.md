---
name: tamano-muestral
description: Calcular el tamano muestral de un experimento (dos grupos, desenlace continuo o binario) con potencia y alfa declarados, para que el experimento propuesto lleve n con su supuesto en vez de "no estimable". Se activa al proponer experimentos, protocolos, ensayos o cuando se pide potencia o n.
activa_si: tamano muestral, potencia, sample size, n por grupo, protocolo, ensayo, experimento, power
paquetes: scipy
scripts: tamano_muestral.py
---

# Tamano muestral

Adaptado del calculador de la skill `clinical-trial-protocol` de Anthropic
(Apache-2.0). Formulas clasicas de dos grupos:

- Continuo: n por grupo = 2 (z_alfa/2 + z_potencia)^2 (sigma / delta)^2,
  con delta el efecto minimo que importa y sigma la desviacion estandar
  esperada. Con desviaciones distintas por grupo se usa la suma de
  varianzas.
- Binario: n por grupo = (z_alfa/2 raiz(2 p q) + z_potencia raiz(p1 q1 + p2
  q2))^2 / (p1 - p2)^2, con p la media de las proporciones.
- Ajuste por abandono: n / (1 - abandono).

Reglas: declarar de donde sale sigma o p1 (una publicacion con su cita, o
un supuesto marcado como tal); dar el n para 80 % y 90 % de potencia; si no
hay base para sigma o delta, decir "no estimable" y que dato haria falta.

Uso en el sandbox: `from tamano_muestral import continuo, binario`.
