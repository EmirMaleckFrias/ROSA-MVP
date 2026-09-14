// Glosario vivo: cada termino tecnico de Rosa con su definicion en una frase,
// para que la ayuda de cada seccion lo explique donde aparece (en vez de
// obligar a buscarlo). Las claves son expresiones regulares sobre el texto
// del titulo y la nota de la seccion.

export const GLOSARIO: { patron: RegExp; termino: string; definicion: string }[] = [
  { patron: /\bElo\b/, termino: 'Elo', definicion: 'Puntuacion del ranking, como en ajedrez: sube cuando una hipotesis gana un partido del torneo contra otra y baja cuando pierde. Empieza en 1500.' },
  { patron: /Bradley-?Terry|\bBT\b/, termino: 'Bradley-Terry', definicion: 'Otra forma de ordenar por partidos, con un intervalo de confianza: dice cuanta seguridad hay en el orden, no solo el orden.' },
  { patron: /\bkappa\b/i, termino: 'Kappa', definicion: 'Medida de acuerdo entre dos evaluadores (el juez y una persona) corregida por el acuerdo que se daria por azar. 0,6 o mas es sustancial.' },
  { patron: /\bGRADE\b/, termino: 'GRADE', definicion: 'Marco de la medicina basada en evidencia para decir cuanta certeza hay (alta, moderada, baja, muy baja) y por que sube o baja.' },
  { patron: /prerregistr/i, termino: 'Prerregistro', definicion: 'Congelar por escrito, con fecha, la hipotesis, el protocolo y los criterios de exito antes de tener datos, para que nadie cambie las reglas despues.' },
  { patron: /puerta de reproducci/i, termino: 'Puerta de reproduccion', definicion: 'Antes de descubrir nada, Rosa tiene que reproducir tres analisis ya publicados dentro de una tolerancia. Si no puede, un resultado nuevo no se distingue de un error.' },
  { patron: /\bKiller\b/, termino: 'Killer', definicion: 'El revisor que somete cada hipotesis a catorce comprobaciones fijas (citas reales, fidelidad a la fuente, supuestos, novedad...) y del que sale, por regla, si avanza, se reformula, se suspende o se descarta.' },
  { patron: /modelo de mundo/i, termino: 'Modelo de mundo', definicion: 'Lo que Rosa da por sabido en esta investigacion, hecho a hecho, cada uno con su fuente y su pagina. Nada entra sin pasar por la verificacion.' },
  { patron: /procedencia/i, termino: 'Procedencia', definicion: 'De donde salio cada cosa: que fuente, que pagina, que codigo, que ejecucion. Es lo que permite comprobar a Rosa desde fuera.' },
  { patron: /\bhash\b|sha256/i, termino: 'Hash (sha256)', definicion: 'Una huella digital corta de un fichero o un texto: si cambia una coma, cambia la huella. Sirve para demostrar que algo no se toco.' },
  { patron: /sandbox/i, termino: 'Sandbox', definicion: 'El contenedor aislado y sin red donde Rosa ejecuta el codigo de analisis: no puede tocar el ordenador ni salir a internet.' },
  { patron: /in silico/i, termino: 'In silico', definicion: 'Analisis hecho con codigo sobre datos ya existentes, en vez de en el laboratorio.' },
  { patron: /torneo/i, termino: 'Torneo', definicion: 'Comparaciones de dos en dos entre hipotesis rivales, juzgadas por un modelo, que alimentan el Elo.' },
  { patron: /riesgo de sesgo/i, termino: 'Riesgo de sesgo', definicion: 'Cuanto puede estar distorsionado el resultado de un estudio por su diseno. Se evalua con instrumentos validados (RoB 2, ROBINS-I...), pregunta a pregunta.' },
  { patron: /entidad(es)? canonica/i, termino: 'Entidad canonica', definicion: 'Un gen, una celula o una enfermedad enlazados a su identificador oficial (HGNC, Cell Ontology, MONDO), para que GFAP y "glial fibrillary acidic protein" sean lo mismo.' },
  { patron: /libro de procedencia/i, termino: 'Libro de procedencia', definicion: 'La ficha de un dataset: de donde viene, con que licencia, si se puede usar con IA, su hash y que significa cada columna.' },
  { patron: /\bmision\b|\bmisión\b/i, termino: 'Mision', definicion: 'El marco de la investigacion que Rosa propone y tu apruebas: poblacion, etapa, tejido, mecanismo, tipo de intervencion, capacidades del laboratorio y presupuesto.' },
  { patron: /autonomia/i, termino: 'Autonomia', definicion: 'Cuanto hace Rosa sola en cada clase de accion: sugerir, preguntar antes o actuar. Nunca toma sola una decision que toque el mundo real.' },
  { patron: /\bskill/i, termino: 'Skill', definicion: 'Un metodo de analisis empaquetado (instrucciones y codigo) que Rosa carga cuando el plan lo pide, como una plantilla de laboratorio.' },
  { patron: /conector/i, termino: 'Conector', definicion: 'La conexion a una base publica (PubMed, Open Targets, GEO...). Cada consulta queda registrada con lo que devolvio.' },
  { patron: /e-?valor/i, termino: 'E-valor', definicion: 'Una medida de evidencia acumulable prueba a prueba, alternativa al valor p, que permite seguir mirando sin inflar los falsos positivos.' },
  { patron: /\bRO-?Crate\b|\bPROV\b/, termino: 'RO-Crate y PROV', definicion: 'Formatos estandar para empaquetar un expediente con su procedencia de modo que cualquier herramienta de terceros lo verifique sin Rosa.' },
  { patron: /PRISMA/, termino: 'PRISMA', definicion: 'La guia con la que se reporta una revision de la literatura: cuantos articulos se encontraron, se cribaron, se leyeron y se usaron, y por que se excluyo el resto.' },
  { patron: /cobertura/i, termino: 'Cobertura', definicion: 'Cuanto de lo relevante estima Rosa haber encontrado ya en la literatura sobre un tema.' },
];

export function terminosEn(texto: string): { termino: string; definicion: string }[] {
  const vistos = new Set<string>();
  const salida: { termino: string; definicion: string }[] = [];
  for (const g of GLOSARIO) {
    if (g.patron.test(texto) && !vistos.has(g.termino)) {
      vistos.add(g.termino);
      salida.push({ termino: g.termino, definicion: g.definicion });
    }
  }
  return salida;
}
