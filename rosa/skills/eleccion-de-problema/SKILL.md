---
name: eleccion-de-problema
description: Las preguntas de eleccion de problema de Fischbach y Walsh (Cell, 2024), tal como las usa la skill scientific-problem-selection de Anthropic, aplicadas a la mision y a las areas antes de aprobarlas. Se activa al proponer o comparar mision, areas, campanas y preguntas.
contexto: mision
activa_si: mision, area, areas, campana, pregunta de campana, meta amplia, programa, eleccion
---

# Eleccion de problema

Idea central: elegir bien el problema pesa mas que ejecutarlo bien. Se
gasta dias en elegir y anos en resolver. Para cada area o pregunta,
responder por escrito:

1. Que exactamente se quiere hacer, en una frase.
2. Como se piensa hacer.
3. Si sale, por que sera importante (que decision cambia).
4. Cuales son los riesgos mayores y cuantos "milagros" hacen falta: uno es
   aceptable, varios encadenados no.
5. Ejes: probabilidad de exito frente a impacto si sale. Mover la idea a la
   derecha (mas factible) o hacia arriba (mas impacto), no abandonarla por
   estar en el medio.
6. Que un solo parametro quede fijo (la poblacion, el biomarcador, la
   etapa) y los demas floten: demasiados fijos vuelven la idea fragil,
   demasiado pocos la paralizan.
7. Que se haria si el primer resultado sale nulo (plan de adversidad) y
   como se invertiria el problema (que se aprende del fracaso).

Rosa lo usa como lista de comprobacion en `ProponerAreas`: un area sin
respuesta a 3 y 4 no se marca como elegida.
