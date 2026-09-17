// El árbol de la investigación: el grafo de lib/arbol.ts dibujado en SVG con
// una disposición por fuerzas propia. Se explora: al abrir se ven el tronco,
// las ramas, las hipótesis vivas y los experimentos; pulsar un nodo
// despliega lo que lo sostiene (hechos, fuentes, entidades, rivales) y lo
// selecciona; pulsar dos veces abre su ficha. La búsqueda ilumina todo lo
// que toca una palabra o un identificador (GFAP, HGNC:4235). El deslizador
// de iteraciones enseña cómo creció el árbol. Se mueve con la rueda y
// arrastrando el fondo. Por defecto (petición de Emir, 16 de septiembre de 2026)
// el relleno dice qué es cada nodo (las hipótesis y su rama, el color de su
// familia de mecanismo; el resto, el de su tipo) y el anillo cuánto lo sostiene
// (verde a un paso de una medición propia, ámbar solo literatura, gris nada;
// lib/arbol.ts calcula las distancias). El conmutador "Por distancia al dato"
// pasa esa distancia al relleno con una escala secuencial.
//
// Vista 3D (petición de Emir, 16 de septiembre de 2026): el mismo árbol, con la
// misma información (colores, anillos, alertas, rayas, leyenda, búsqueda,
// desplegar al pulsar, ficha con doble clic), pero dispuesto en tres ejes y
// mirado por una CÁMARA ORBITAL que gira alrededor del tronco. La geometría
// vive en lib/arbol3d.ts: una disposición por fuerzas con coordenada z, una
// PROYECCIÓN EN PERSPECTIVA (cámara estenopeica: cada punto se divide por su
// distancia a la cámara, así lo lejano sale pequeño) y tres números de cámara,
// la GUIÑADA (giro alrededor del eje vertical: arrastrar el fondo en
// horizontal), el CABECEO (inclinación arriba y abajo: arrastrar en vertical,
// acotado a más o menos 80 grados) y la DISTANCIA (la rueda). Aquí solo se
// dibuja lo proyectado: el radio de cada círculo se multiplica por la escala,
// la opacidad baja con la profundidad (niebla) y los nodos se pintan de lejos a
// cerca para que los cercanos tapen a los lejanos. Cuando nadie toca el árbol
// durante unos segundos gira solo, despacio, salvo con movimiento reducido. En
// 3D no se arrastran nodos (el fondo gira el árbol) ni hay vaivén (el giro ya
// le da vida). La elección de vista se recuerda en el navegador; por defecto
// sigue la vista plana, para no cambiarle el árbol a quien ya lo conoce.

import { useEffect, useMemo, useRef, useState } from 'react';
import type { EstadoRosa, Investigacion } from '../datos/tipos';
import { AvisoMuestra, Chip, Vacio } from '../componentes/piezas';
import { alternar, buscar, construirArbol, fraseProfundidad, incorporarNovedades, NOMBRE_ENLACE, NOMBRE_TIPO, paso, posicionInicial, SIN_DISTANCIA, visiblesIniciales, type Grafo, type NodoArbol, type Posicion, type TipoEnlace, type TipoNodo } from '../lib/arbol';
import { acotarCamara, camaraInicial, distanciaEncuadre, ESPERA_GIRO_MS, niebla, ordenarPorProfundidad, paso3d, posicionInicial3d, proyectar, SENSIBILIDAD_GIRO, VELOCIDAD_GIRO, type Camara, type Posicion3, type Proyeccion } from '../lib/arbol3d';
import { useMovimientoReducido } from '../lib/movimiento';

const RADIO: Record<TipoNodo, number> = { objetivo: 22, rama: 13, area: 12, hipotesis: 11, hecho: 7, pregunta: 7, fuente: 5, entidad: 6, experimento: 12, afirmacion: 6, ejecucion: 9, dataset: 8, laboratorio: 12 };
const COLOR: Record<TipoNodo, string> = {
  objetivo: 'var(--accent)',
  rama: 'var(--accent-soft-2)',
  area: 'var(--accent-soft-2)',
  hipotesis: '#7c3aed',
  hecho: 'var(--green)',
  pregunta: 'var(--amber)',
  fuente: 'var(--text-3)',
  entidad: 'var(--blue)',
  experimento: '#0f766e',
  afirmacion: 'var(--grafo-afirmacion)',
  ejecucion: 'var(--grafo-ejecucion)',
  dataset: 'var(--grafo-dataset)',
  laboratorio: 'var(--grafo-laboratorio)',
};
const TRAZO: Record<TipoEnlace, { color: string; ancho: number; guion?: string }> = {
  rama: { color: 'var(--border-strong)', ancho: 1.6 },
  cita: { color: 'var(--text-3)', ancho: 0.8 },
  respalda: { color: 'var(--green)', ancho: 1 },
  entidad: { color: 'var(--blue)', ancho: 0.8, guion: '2 3' },
  causal: { color: '#ea580c', ancho: 1.4 },
  rival: { color: 'var(--red)', ancho: 1, guion: '4 4' },
  experimento: { color: '#0f766e', ancho: 1.8 },
  dato: { color: 'var(--grafo-dato-1)', ancho: 1.3 },
};

/** En 3D los nodos cambian de orden en el DOM cada cuadro (se pintan de lejos a
 *  cerca) y el navegador trata cada movimiento como una inserción: reiniciaba la
 *  animación de entrada `brotar` y las transiciones de opacidad de styles.css, y
 *  las esferas parpadeaban. En esta vista todo se pinta sin transición. */
const ESTILO_3D = { transition: 'none', animation: 'none' } as const;
type ModoColor = 'tipo' | 'dato';
type Vista = 'plana' | '3d';
/** Clave del navegador donde se recuerda la vista elegida (sin tilde: es un identificador). */
const CLAVE_VISTA = 'rosa-arbol-vista';
function leerVista(): Vista {
  try {
    return localStorage.getItem(CLAVE_VISTA) === '3d' ? '3d' : 'plana';
  } catch {
    return 'plana';
  }
}
function guardarVista(v: Vista): void {
  try {
    localStorage.setItem(CLAVE_VISTA, v);
  } catch {
    // Sin almacenamiento (modo privado, cuota llena): la elección dura lo que la pestaña.
  }
}
/** Qué es cada tipo de nodo, dicho en llano para la leyenda (petición de Emir, 16 de
 *  septiembre de 2026: la leyenda tiene que explicar los colores como se explican en
 *  una conversación, no listar nombres y recuentos). */
const DEFINICION_TIPO: Record<TipoNodo, string> = {
  objetivo: 'Objetivo (el tronco): la pregunta de la investigación. Es estructura, no evidencia.',
  rama: 'Rama: una familia de mecanismo; agrupa las hipótesis que hablan del mismo mecanismo biológico.',
  area: 'Área del programa: una línea de trabajo que agrupa investigaciones. Estructura, no evidencia.',
  hipotesis: 'Hipótesis: cada una lleva el color de su familia de mecanismo. Si dos hojas comparten color, comparten mecanismo.',
  hecho: 'Hecho: algo que el modelo de mundo ya da por sostenido.',
  pregunta: 'Pregunta abierta: algo que Rosa todavía no ha podido resolver.',
  fuente: 'Fuente: un artículo o una base de datos que Rosa leyó.',
  entidad: 'Entidad: un gen, una proteína o un tipo de célula con su nombre canónico.',
  experimento: 'Experimento propuesto para el laboratorio.',
  afirmacion: 'Afirmación con dato: una frase de un artículo con su cifra, verificada por el juez.',
  ejecucion: 'Análisis in silico: un análisis que Rosa corrió sobre datos públicos y pasó la auditoría.',
  dataset: 'Conjunto de datos público usado en un análisis.',
  laboratorio: 'Resultado del laboratorio: lo que devolvió el experimento.',
};
/** Paleta por familia de mecanismo (el cluster de cada hipótesis): en el modo por
 *  tipo, las hipótesis y su rama comparten el color de su familia, así el árbol
 *  enseña de un vistazo qué mecanismos compiten. Diez tonos distinguibles en tema
 *  claro y oscuro (tokens en styles.css); con más de diez familias se repiten. */
const PALETA_CLUSTER = ['var(--grafo-cluster-0)', 'var(--grafo-cluster-1)', 'var(--grafo-cluster-2)', 'var(--grafo-cluster-3)', 'var(--grafo-cluster-4)', 'var(--grafo-cluster-5)', 'var(--grafo-cluster-6)', 'var(--grafo-cluster-7)', 'var(--grafo-cluster-8)', 'var(--grafo-cluster-9)'];
/** Escala secuencial por distancia al dato: un solo tono, más intenso cuanto
 *  más cerca de la medición (0 = la medición misma) y más claro a cada salto.
 *  Los tokens viven en styles.css con pasos propios para el tema oscuro. */
const ESCALA_DATO = ['var(--grafo-dato-0)', 'var(--grafo-dato-1)', 'var(--grafo-dato-2)', 'var(--grafo-dato-3)'];
const NOMBRE_ESCALA = ['La medición misma (0 saltos)', 'A 1 salto de una medición', 'A 2 saltos', 'A 3 saltos o más'];
/** Segunda escala, en ámbar, para lo que no tiene medición propia pero sí literatura
 *  leída detrás (una fuente con su texto, no solo citada): más intenso cuanto más cerca
 *  de la fuente. Sin ella, una investigación solo de literatura salía toda gris. */
const ESCALA_LIT = ['var(--grafo-lit-1)', 'var(--grafo-lit-2)', 'var(--grafo-lit-3)'];
const NOMBRE_ESCALA_LIT = ['Solo literatura, a 1 salto de una fuente leída', 'Solo literatura, a 2 saltos', 'Solo literatura, a 3 saltos o más'];
const COLOR_SIN_DATO = 'var(--grafo-dato-nulo)';
/** Escalón de la escala para un nodo: 0 a 3, o 'nulo' si no hay camino al dato. */
function escalonDato(n: NodoArbol): number | 'nulo' {
  const d = n.profundidadDato ?? null;
  return d === null ? 'nulo' : Math.min(d, ESCALA_DATO.length - 1);
}
/** Escalón de la escala de literatura: 0 a 2 (1, 2, 3 o más saltos hasta una fuente leída), o 'nulo'. */
function escalonLiteratura(n: NodoArbol): number | 'nulo' {
  const d = n.profundidadLiteratura ?? null;
  return d === null ? 'nulo' : Math.min(Math.max(d, 1), ESCALA_LIT.length) - 1;
}
/** Clave de leyenda del nodo en el modo por distancia: 'd0'..'d3', 'l0'..'l2' o 'nulo'. */
function claveDistancia(n: NodoArbol): string {
  const d = escalonDato(n);
  if (d !== 'nulo') return `d${d}`;
  const l = escalonLiteratura(n);
  return l === 'nulo' ? 'nulo' : `l${l}`;
}
function colorPorDato(n: NodoArbol): string {
  if (SIN_DISTANCIA.has(n.tipo)) return COLOR[n.tipo];
  const d = escalonDato(n);
  if (d !== 'nulo') return ESCALA_DATO[d]!;
  const l = escalonLiteratura(n);
  return l === 'nulo' ? COLOR_SIN_DATO : ESCALA_LIT[l]!;
}

/** Un motor de disposición: cómo nace un nodo y cómo avanza un paso de la física.
 *  Hay dos, el plano (lib/arbol.ts) y el de tres ejes (lib/arbol3d.ts). */
interface Motor<P extends { fijo?: boolean }> {
  inicial: (g: Grafo, posiciones: Map<string, P>, id: string, semilla: number) => P;
  paso: (g: Grafo, visibles: Set<string>, posiciones: Map<string, P>, alfa: number) => void;
}
const MOTOR_PLANO: Motor<Posicion> = { inicial: posicionInicial, paso };
const MOTOR_3D: Motor<Posicion3> = { inicial: posicionInicial3d, paso: paso3d };

/** La simulación por fuerzas, común a las dos vistas. `activo` en false la
 *  congela (la vista que no se ve no gasta fotogramas) conservando las
 *  posiciones: al volver a ella retoma donde estaba y solo coloca lo nuevo. */
function useSimulacionDe<P extends { fijo?: boolean }>(grafo: Grafo, visibles: Set<string>, quieto: boolean, activo: boolean, motor: Motor<P>) {
  const posiciones = useRef(new Map<string, P>());
  const [, setTick] = useState(0);
  const alfa = useRef(1);
  const semilla = useRef(1);
  const marco = useRef<number | null>(null);
  // Un bucle de animación que se enfría solo y se puede reavivar (al
  // arrastrar un nodo, al desplegar): como el "animate" del grafo de Obsidian.
  const arrancar = (energia = 1) => {
    alfa.current = Math.max(alfa.current, energia);
    if (marco.current !== null) return;
    const animar = () => {
      for (let k = 0; k < 2; k++) motor.paso(grafo, visibles, posiciones.current, alfa.current);
      alfa.current = Math.max(0.02, alfa.current * 0.975);
      setTick((t) => t + 1);
      if (alfa.current > 0.03) marco.current = requestAnimationFrame(animar);
      else marco.current = null;
    };
    marco.current = requestAnimationFrame(animar);
  };
  const firmaAnterior = useRef('');
  useEffect(() => {
    if (!activo) return;
    // Los nodos nuevos nacen junto a un vecino colocado; los que se van, se olvidan.
    let cambio = false;
    for (const id of visibles) {
      if (!posiciones.current.has(id)) {
        posiciones.current.set(id, motor.inicial(grafo, posiciones.current, id, semilla.current++));
        cambio = true;
      }
    }
    for (const id of [...posiciones.current.keys()]) {
      if (!visibles.has(id)) {
        posiciones.current.delete(id);
        cambio = true;
      }
    }
    // El estado de Rosa cambia cada pocos segundos por SSE y reconstruye el grafo:
    // si el conjunto de nodos no cambió, no se vuelve a agitar el árbol.
    const firma = [...visibles].sort().join('|');
    const primera = firmaAnterior.current === '';
    firmaAnterior.current = firma;
    if (quieto) {
      if (cambio || primera) {
        for (let i = 0; i < 240; i++) motor.paso(grafo, visibles, posiciones.current, Math.max(0.05, 1 - i / 240));
        setTick((t) => t + 1);
      }
      return;
    }
    if (cambio || primera) {
      alfa.current = 0;
      arrancar(primera ? 1 : 0.6);
    } else if (alfa.current > 0.03) {
      // La limpieza del efecto anterior canceló el fotograma en marcha (otro
      // efecto reasignó los visibles al montar, o se cambió de vista): se
      // retoma donde estaba.
      arrancar(alfa.current);
    }
    return () => {
      if (marco.current !== null) cancelAnimationFrame(marco.current);
      marco.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [grafo, visibles, quieto, activo]);
  return { posiciones: posiciones.current, reavivar: (energia = 0.4) => (quieto ? setTick((t) => t + 1) : arrancar(energia)), asentada: () => marco.current === null };
}

function useSimulacion(grafo: Grafo, visibles: Set<string>, quieto: boolean, activo: boolean) {
  return useSimulacionDe(grafo, visibles, quieto, activo, MOTOR_PLANO);
}

/** La misma simulación con la física de tres ejes (lib/arbol3d.ts): mismo
 *  enfriamiento, mismo reavivar, otra estructura de posición (x, y, z). */
function useSimulacion3d(grafo: Grafo, visibles: Set<string>, quieto: boolean, activo: boolean) {
  return useSimulacionDe(grafo, visibles, quieto, activo, MOTOR_3D);
}

/** Cuánto se ve la etiqueta de un nodo según el zoom y su importancia (el
 *  "text fade threshold" del grafo de Obsidian): el tronco siempre; ramas,
 *  hipótesis y experimentos desde un zoom normal; lo pequeño solo al acercar,
 *  o si está iluminado o seleccionado. En 3D el "zoom" de cada nodo es su
 *  escala proyectada, así que las etiquetas pequeñas solo salen en los nodos
 *  cercanos a la cámara y las de peso alto se leen desde más lejos. */
function opacidadEtiqueta(n: NodoArbol, k: number, vivo: boolean, sel: boolean): number {
  if (sel) return 1;
  const umbral = n.tipo === 'objetivo' ? 0 : n.tipo === 'rama' || n.tipo === 'area' || n.tipo === 'hipotesis' || n.tipo === 'experimento' || n.tipo === 'laboratorio' || n.tipo === 'ejecucion' ? 0.75 : 1.5;
  const base = Math.max(0, Math.min(1, (k - umbral) / 0.35 + 1));
  return vivo ? Math.max(base, n.tipo === 'fuente' || n.tipo === 'entidad' || n.tipo === 'hecho' || n.tipo === 'pregunta' || n.tipo === 'afirmacion' || n.tipo === 'dataset' ? 0.9 : 1) : base;
}

/** Parte una etiqueta en hasta dos líneas de unos 22 caracteres. */
function lineas(texto: string, maximo = 22): string[] {
  if (texto.length <= maximo) return [texto];
  const palabras = texto.split(' ');
  const salida: string[] = [];
  let actual = '';
  for (const p of palabras) {
    if ((actual + ' ' + p).trim().length > maximo && actual) {
      salida.push(actual);
      actual = p;
      if (salida.length === 2) break;
    } else actual = (actual + ' ' + p).trim();
  }
  if (salida.length < 2 && actual) salida.push(actual);
  if (salida.length === 2 && salida.join(' ').length < texto.length) salida[1] = `${salida[1]!.slice(0, maximo - 3)}...`;
  return salida;
}

export function Arbol({ inv, estado }: { inv: Investigacion; estado: EstadoRosa }) {
  const hip = useMemo(() => estado.hipotesis.filter((h) => h.investigacionId === inv.id), [estado.hipotesis, inv.id]);
  const grafo = useMemo(() => construirArbol(estado, inv), [estado, inv]);
  // Sin hipótesis ni hechos no hay árbol que dibujar (se enseña qué pasará). Se
  // calcula aquí, antes de los efectos, porque el de la rueda tiene que volver a
  // engancharse cuando el SVG aparece por primera vez.
  const vacio = hip.length === 0 && estado.hechos.filter((h) => h.investigacionId === inv.id).length === 0;
  const [visibles, setVisibles] = useState<Set<string>>(() => visiblesIniciales(grafo, hip));
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [texto, setTexto] = useState('');
  const [hasta, setHasta] = useState<number>(grafo.iteracionMax);
  const anterior = useRef({ ids: new Set(grafo.nodos.map((n) => n.id)), iteracionMax: grafo.iteracionMax });
  const [vista, setVista] = useState({ x: 0, y: 0, k: 1 });
  const [hover, setHover] = useState<string | null>(null);
  const [modoColor, setModoColor] = useState<ModoColor>('tipo'); // Por defecto: relleno por tipo y familia de mecanismo, anillo por distancia al dato (petición de Emir, 16 de septiembre de 2026)
  const [tipoVista, setTipoVista] = useState<Vista>(leerVista);
  const vista3d = tipoVista === '3d';
  /** Último instante en que alguien tocó el árbol en 3D: el giro automático espera unos segundos desde entonces. */
  const ultimoToque = useRef(0);
  const cambiarVista = (v: Vista) => {
    setTipoVista(v);
    guardarVista(v);
    ultimoToque.current = performance.now();
  };
  // La cámara orbital de la vista 3D (guiñada, cabeceo, distancia), siempre acotada.
  const [camara, setCamara] = useState<Camara>(camaraInicial);
  const arrastre = useRef<{ x: number; y: number; vx: number; vy: number; ux?: number; uy?: number } | null>(null);
  const arrastreNodo = useRef<{ id: string; x0: number; y0: number; movido: boolean } | null>(null);
  // Último punto del puntero mientras se gira la cámara. El giro es incremental
  // (cada movimiento suma su diferencia a la cámara actual) y no absoluto desde
  // el punto de agarre: así, al topar con el cabeceo máximo, la cámara responde
  // en cuanto el puntero vuelve, sin tener que desandar el exceso.
  const arrastreCamara = useRef<{ x: number; y: number } | null>(null);
  const hoverRef = useRef<string | null>(null);
  const reducido = useMovimientoReducido();
  const svgRef = useRef<SVGSVGElement>(null);
  const ancho = 900;
  const alto = 560;
  // Coordenadas del lienzo a partir de un evento del puntero (para el zoom al
  // cursor y para arrastrar nodos con la vista movida).
  const enLienzo = (clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const caja = svg.getBoundingClientRect();
    const escala = ancho / caja.width;
    return { x: (clientX - caja.left) * escala - ancho / 2, y: (clientY - caja.top) * escala - alto / 2 };
  };

  // Sigue las novedades del servidor, sin restablecer la exploración de la persona.
  useEffect(() => {
    const previo = anterior.current;
    setVisibles((v) => incorporarNovedades(grafo, previo.ids, v));
    setHasta((h) => h >= previo.iteracionMax ? grafo.iteracionMax : h);
    anterior.current = { ids: new Set(grafo.nodos.map((n) => n.id)), iteracionMax: grafo.iteracionMax };
  }, [grafo]);

  const iluminados = useMemo(() => buscar(grafo, texto), [grafo, texto]);
  const enTiempo = useMemo(() => new Set([...visibles].filter((id) => (grafo.porId.get(id)?.iteracion ?? 0) <= hasta)), [visibles, hasta, grafo]);
  // El nodo bajo el ratón solo cuenta mientras se dibuja: si desaparece (Plegar
  // todo, el deslizador de iteraciones) nunca dispara pointerleave y, sin esto,
  // el giro automático quedaría pausado para siempre y el árbol atenuado.
  const foco = hover !== null && enTiempo.has(hover) ? hover : null;
  hoverRef.current = foco;
  // Las dos simulaciones existen siempre (regla de los hooks) pero solo corre la de la vista activa.
  const { posiciones, reavivar } = useSimulacion(grafo, enTiempo, reducido, !vista3d);
  const { posiciones: posiciones3, asentada: asentada3 } = useSimulacion3d(grafo, enTiempo, reducido, vista3d);
  // Encuadre automático de la cámara 3D: mientras `encuadrar` está encendido, la
  // distancia se ajusta sola para que todo lo visible quepa en el lienzo. Se
  // enciende al cambiar lo visible o de vista y lo apaga la rueda (la persona
  // manda). Con animación, el ajuste avanza un 15 % por cuadro hasta encajar;
  // con movimiento reducido se aplica de una vez, porque la simulación ya se
  // asentó en su efecto.
  const encuadrar = useRef(true);
  const enTiempoRef = useRef(enTiempo);
  enTiempoRef.current = enTiempo;
  const camaraRef = useRef(camara);
  camaraRef.current = camara;
  const puntosVisibles = () => [...enTiempoRef.current].map((id) => posiciones3.get(id)).filter((p): p is Posicion3 => Boolean(p));
  useEffect(() => {
    encuadrar.current = true;
    if (!vista3d || !reducido) return;
    setCamara((c) => {
      const distancia = distanciaEncuadre(puntosVisibles(), c, ancho, alto);
      return distancia === c.distancia ? c : acotarCamara({ ...c, distancia });
    });
    encuadrar.current = false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enTiempo, vista3d, reducido]);
  // Balanceo en reposo: un vaivén lento y distinto por nodo (solo al dibujar,
  // no en la física) para que el árbol nunca parezca una foto. Con movimiento
  // reducido no hay balanceo; en 3D tampoco, el giro ya da vida.
  const [reloj, setReloj] = useState(0);
  useEffect(() => {
    if (reducido || vista3d) return;
    let id = 0;
    const paso_ = (t: number) => {
      setReloj(t / 1000);
      id = requestAnimationFrame(paso_);
    };
    id = requestAnimationFrame(paso_);
    return () => cancelAnimationFrame(id);
  }, [reducido, vista3d]);
  const vaiven = (id: string, peso: number) => {
    if (reducido || vista3d) return { x: 0, y: 0 };
    let h = 0;
    for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
    const fase = (h % 628) / 100;
    const amp = 1.6 + Math.min(2.5, peso) * 0.5;
    return { x: Math.sin(reloj * 0.7 + fase) * amp, y: Math.cos(reloj * 0.55 + fase * 1.3) * amp * 0.8 };
  };
  // Giro automático en 3D: cuando nadie toca el árbol durante ESPERA_GIRO_MS
  // (ni arrastra, ni tiene el ratón sobre un nodo) la guiñada avanza despacio.
  // Con movimiento reducido, el árbol no gira solo.
  useEffect(() => {
    if (!vista3d || reducido) return;
    let id = 0;
    let previo = performance.now();
    ultimoToque.current = previo;
    const girar = (t: number) => {
      const dt = Math.min(0.1, Math.max(0, (t - previo) / 1000));
      previo = t;
      if (encuadrar.current) {
        const objetivo = distanciaEncuadre(puntosVisibles(), camaraRef.current, ancho, alto);
        const delta = objetivo - camaraRef.current.distancia;
        if (Math.abs(delta) < 0.5) {
          // Encajado: se fija el valor exacto y, si la simulación ya se asentó, se deja de ajustar.
          if (asentada3()) encuadrar.current = false;
          if (delta !== 0) setCamara((c) => acotarCamara({ ...c, distancia: objetivo }));
        } else setCamara((c) => acotarCamara({ ...c, distancia: c.distancia + delta * 0.15 }));
      }
      if (t - ultimoToque.current > ESPERA_GIRO_MS && !hoverRef.current && !arrastreCamara.current) {
        setCamara((c) => acotarCamara({ ...c, guinada: c.guinada + VELOCIDAD_GIRO * dt }));
      }
      id = requestAnimationFrame(girar);
    };
    id = requestAnimationFrame(girar);
    return () => cancelAnimationFrame(id);
  }, [vista3d, reducido]);
  const nodoSel = seleccion ? grafo.porId.get(seleccion) ?? null : null;
  // Familias de mecanismo: orden estable por primera aparición entre las hipótesis visibles.
  const clusterDe = useMemo(() => new Map(estado.hipotesis.filter((x) => x.investigacionId === inv.id).map((x) => [x.id, x.cluster || 'Sin cluster'])), [estado.hipotesis, inv.id]);
  const familias = useMemo(() => {
    const vistas: string[] = [];
    for (const x of estado.hipotesis) if (x.investigacionId === inv.id && x.estado !== 'descartada' && !vistas.includes(x.cluster || 'Sin cluster')) vistas.push(x.cluster || 'Sin cluster');
    for (const x of estado.hipotesis) if (x.investigacionId === inv.id && !vistas.includes(x.cluster || 'Sin cluster')) vistas.push(x.cluster || 'Sin cluster');
    return vistas;
  }, [estado.hipotesis, inv.id]);
  const colorFamilia = (nombre: string) => PALETA_CLUSTER[Math.max(0, familias.indexOf(nombre)) % PALETA_CLUSTER.length]!;
  const colorPorTipo = (n: NodoArbol) => {
    if (n.tipo === 'hipotesis') return colorFamilia(clusterDe.get(n.id) ?? 'Sin cluster');
    if (n.tipo === 'rama') return colorFamilia(n.id.slice('rama-'.length));
    return COLOR[n.tipo];
  };
  const colorDe = (n: NodoArbol) => (modoColor === 'dato' ? colorPorDato(n) : colorPorTipo(n));
  // Anillo de evidencia en el modo por tipo: el borde lleva la distancia al dato
  // (verde medición propia, ámbar literatura leída, gris nada), así el relleno dice
  // qué es el nodo y el anillo cuánto lo sostiene.
  const anilloDe = (n: NodoArbol): string | null => (modoColor === 'tipo' && !SIN_DISTANCIA.has(n.tipo) && !n.alerta ? colorPorDato(n) : null);
  // Sin camino al dato: relleno gris y borde punteado (solo en el modo por distancia).
  // Punteado solo para lo que no tiene ni medición ni literatura leída detrás.
  const sinDato = (n: NodoArbol) => modoColor === 'dato' && !SIN_DISTANCIA.has(n.tipo) && claveDistancia(n) === 'nulo';
  // Resaltar solo al pasar el ratón (como Obsidian): el nodo y sus vecinos vivos, el
  // resto atenuado. La selección (el último nodo abierto) conserva su anillo y su
  // panel, pero no atenúa a los demás: sin ratón encima se ve el árbol entero
  // (petición de Emir, 16 de septiembre de 2026).
  const vecinosFoco = useMemo(() => (foco ? new Set(grafo.vecinos.get(foco) ?? []) : null), [grafo, foco]);
  const atenuar = iluminados.size > 0 || foco !== null;
  const destacado = (id: string) => (iluminados.size > 0 ? iluminados.has(id) : foco === null || foco === id || (vecinosFoco?.has(id) ?? false));

  // La rueda va con un oyente nativo no pasivo: React registra onWheel como
  // pasivo y preventDefault no haría nada (la página haría scroll). En la vista
  // plana acerca alrededor del cursor; en 3D cambia la distancia de la cámara.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const alRueda = (e: WheelEvent) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      if (vista3d) {
        ultimoToque.current = performance.now();
        encuadrar.current = false;
        setCamara((c) => acotarCamara({ ...c, distancia: c.distancia / factor }));
        return;
      }
      const p = enLienzo(e.clientX, e.clientY);
      setVista((v) => {
        const k = Math.max(0.25, Math.min(4, v.k * factor));
        // Zoom alrededor del cursor: el punto bajo el ratón no se mueve.
        return { k, x: p.x - ((p.x - v.x) * k) / v.k, y: p.y - ((p.y - v.y) * k) / v.k };
      });
    };
    svg.addEventListener('wheel', alRueda, { passive: false });
    return () => svg.removeEventListener('wheel', alRueda);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vista3d, vacio]);
  const empezarArrastre = (e: React.PointerEvent) => {
    const nodo = (e.target as Element).closest('.grafo-nodo') as SVGGElement | null;
    if (vista3d) {
      ultimoToque.current = performance.now();
      // En 3D los nodos no se arrastran (el clic llega entero a pulsar); el fondo gira la cámara.
      if (nodo) return;
      (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
      arrastreCamara.current = { x: e.clientX, y: e.clientY };
      return;
    }
    if (nodo) {
      // Sin capturar el puntero: si el SVG lo captura, el navegador manda el
      // clic al SVG y la esfera nunca recibe onClick (no se abría el panel).
      const id = nodo.getAttribute('data-id');
      const p = id ? posiciones.get(id) : undefined;
      if (id && p) {
        arrastreNodo.current = { id, x0: e.clientX, y0: e.clientY, movido: false };
        p.fijo = true;
      }
      return;
    }
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    arrastre.current = { x: e.clientX, y: e.clientY, vx: vista.x, vy: vista.y };
  };
  const mover = (e: React.PointerEvent) => {
    if (arrastreCamara.current) {
      // Girar la cámara: el movimiento horizontal es guiñada y el vertical, cabeceo.
      // Los signos hacen que el frente del árbol siga al puntero.
      const a = arrastreCamara.current;
      const dx = e.clientX - a.x;
      const dy = e.clientY - a.y;
      a.x = e.clientX;
      a.y = e.clientY;
      ultimoToque.current = performance.now();
      setCamara((c) => acotarCamara({ ...c, guinada: c.guinada - dx * SENSIBILIDAD_GIRO, cabeceo: c.cabeceo + dy * SENSIBILIDAD_GIRO }));
      return;
    }
    if (arrastreNodo.current) {
      const a = arrastreNodo.current;
      const p = posiciones.get(a.id);
      if (!p) return;
      if (Math.hypot(e.clientX - a.x0, e.clientY - a.y0) > 4) a.movido = true;
      const l = enLienzo(e.clientX, e.clientY);
      // Del lienzo a las coordenadas del grafo (deshaciendo la vista).
      p.x = (l.x - vista.x) / vista.k;
      p.y = (l.y - vista.y) / vista.k;
      p.vx = 0;
      p.vy = 0;
      reavivar(0.35); // los vecinos siguen al que se arrastra
      return;
    }
    if (!arrastre.current) return;
    const a = arrastre.current;
    // Al agarrar el árbol, las esferas no van pegadas al fondo: reciben un
    // impulso contrario, se columpian y vuelven a su sitio tiradas por los
    // enlaces (el tronco está fijo). Es la sacudida de un árbol de verdad.
    const dx = e.clientX - (a.ux ?? a.x);
    const dy = e.clientY - (a.uy ?? a.y);
    a.ux = e.clientX;
    a.uy = e.clientY;
    if (!reducido) {
      for (const p of posiciones.values()) {
        if (p.fijo) continue;
        p.vx -= (dx * 0.12) / vista.k;
        p.vy -= (dy * 0.12) / vista.k;
      }
      reavivar(0.25);
    }
    setVista((v) => ({ ...v, x: a.vx + (e.clientX - a.x), y: a.vy + (e.clientY - a.y) }));
  };
  const soltar = () => {
    if (arrastreCamara.current) {
      arrastreCamara.current = null;
      ultimoToque.current = performance.now();
    }
    if (arrastreNodo.current) {
      const p = posiciones.get(arrastreNodo.current.id);
      if (p && arrastreNodo.current.id !== 'objetivo') p.fijo = false;
      // Un arrastre no es un clic: si se movió, no se despliega ni se selecciona.
      const movido = arrastreNodo.current.movido;
      arrastreNodo.current = null;
      if (movido) {
        reavivar(0.3);
        ultimoArrastreMovido.current = true;
        return;
      }
    }
    arrastre.current = null;
  };
  const ultimoArrastreMovido = useRef(false);
  const pulsar = (n: NodoArbol, detalle: number) => {
    if (ultimoArrastreMovido.current) {
      ultimoArrastreMovido.current = false;
      return;
    }
    if (detalle > 1) return; // la segunda pulsación de un doble clic no vuelve a plegar
    ultimoToque.current = performance.now();
    setSeleccion(n.id);
    setVisibles((v) => alternar(grafo, v, n.id));
  };

  if (vacio) {
    return (
      <div className="contenido">
        <AvisoMuestra conexion={estado.conexion} />
        <Vacio titulo="El árbol todavía no tiene ramas" pasos={['El tronco es el objetivo; ya está.', 'Cuando Rosa busque literatura y verifique afirmaciones, aparecerán los hechos y las fuentes.', 'Cada hipótesis será una hoja en la rama de su cluster de mecanismo, unida a lo que la sostiene.', 'El experimento que llegue al laboratorio será el fruto.']}>
          Aquí se ve toda la investigación conectada: qué sostiene a qué, qué comparte una entidad con qué, y qué rivaliza con qué.
        </Vacio>
      </div>
    );
  }

  const colocado = (id: string) => (vista3d ? posiciones3.has(id) : posiciones.has(id));
  const enlacesVisibles = grafo.enlaces.filter((e) => enTiempo.has(e.de) && enTiempo.has(e.a) && colocado(e.de) && colocado(e.a));
  const nodosVisibles = [...enTiempo].map((id) => grafo.porId.get(id)).filter((n): n is NodoArbol => Boolean(n) && colocado(n!.id));
  // La leyenda explica solo los tipos de nodo que existen en este árbol (visibles o plegados).
  const tiposPresentes = new Set(grafo.nodos.map((n) => n.tipo));
  // Vista 3D: cada nodo visible se proyecta una vez por fotograma y se pinta de
  // lejos a cerca; lo que queda detrás de la cámara no se dibuja.
  const proyecciones = new Map<string, Proyeccion>();
  let ordenados: NodoArbol[] = nodosVisibles;
  if (vista3d) {
    for (const n of nodosVisibles) proyecciones.set(n.id, proyectar(posiciones3.get(n.id)!, camara, ancho, alto));
    // Los que quedan detrás de la cámara siguen montados con opacidad cero: desmontarlos y volverlos a montar reiniciaría su animación de entrada.
    ordenados = ordenarPorProfundidad(nodosVisibles.map((n) => n.id), posiciones3, camara).map((id) => grafo.porId.get(id)!);
  }

  /** El círculo de un nodo con su relleno, su anillo y sus rayas: idéntico en las dos vistas. */
  const circulo = (n: NodoArbol, r: number, sinTransicion: boolean) => (
    <circle r={r} fill={colorDe(n)} stroke={n.alerta ? 'var(--red)' : anilloDe(n) ?? (sinDato(n) ? 'var(--text-3)' : n.tipo === 'rama' || n.tipo === 'area' ? 'var(--accent)' : 'var(--surface)')} strokeWidth={n.alerta ? 2 : anilloDe(n) ? 3 : 1.5} strokeDasharray={n.estado === 'descartada' ? '3 2' : sinDato(n) || (anilloDe(n) && claveDistancia(n) === 'nulo') ? '2 2' : undefined} style={sinTransicion ? ESTILO_3D : undefined} />
  );
  const etiqueta = (n: NodoArbol, y: number, opEt: number, sinTransicion = false) => (
    <text y={y} textAnchor="middle" className="grafo-etiqueta" opacity={opEt} style={{ fontSize: n.tipo === 'objetivo' ? 13 : n.tipo === 'rama' || n.tipo === 'hipotesis' || n.tipo === 'experimento' || n.tipo === 'laboratorio' ? 10.5 : 9, ...(sinTransicion ? ESTILO_3D : undefined) }}>
      {lineas(n.etiqueta).map((f, i) => (
        <tspan key={i} x={0} dy={i === 0 ? 0 : 12}>
          {f}
        </tspan>
      ))}
    </text>
  );
  const iconos = (n: NodoArbol) => (
    <>
      {n.tipo === 'experimento' && <path d="M-4 -5 h8 v3 l3 6 a2 2 0 0 1 -2 3 h-10 a2 2 0 0 1 -2 -3 l3 -6 z" fill="none" stroke="#fff" strokeWidth={1.2} transform="scale(0.9)" />}
      {n.tipo === 'laboratorio' && <path d="M-4.5 0.5 l3 3 l6 -7" fill="none" stroke="#fff" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />}
    </>
  );
  const claseNodo = (n: NodoArbol, vivo: boolean, sel: boolean) => `grafo-nodo grafo-${n.tipo} ${vivo ? '' : 'grafo-atenuado'} ${sel ? 'grafo-seleccionado' : ''} ${hover === n.id ? 'grafo-hover' : ''}`;
  const propsNodo = (n: NodoArbol) => ({
    onClick: (e: React.MouseEvent) => pulsar(n, e.detail),
    onDoubleClick: () => {
      if (n.href) window.location.hash = n.href;
    },
    onPointerEnter: () => setHover(n.id),
    onPointerLeave: () => setHover((h) => (h === n.id ? null : h)),
    role: 'button',
    tabIndex: 0,
    'aria-label': `${NOMBRE_TIPO[n.tipo]}: ${n.etiqueta}`,
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') pulsar(n, 1);
    },
  });

  return (
    <div className="contenido contenido-ancho">
      <AvisoMuestra conexion={estado.conexion} />
      <div className="pantalla-cabecera" style={{ marginTop: 16 }}>
        <div>
          <h2>Árbol de la investigación</h2>
          <p>El objetivo es el tronco; las ramas, los clusters con varias hipótesis; las hojas, las hipótesis; alrededor, lo que las sostiene. Pasa el ratón por un nodo para ver sus conexiones; pulsa para desplegar lo que toca; dos veces para abrir su ficha; arrastra un nodo para moverlo (los demás lo siguen). Las etiquetas pequeñas aparecen al acercar con la rueda. Escribe una palabra o un identificador (GFAP, HGNC:4235) para iluminar todo lo que lo nombra. Por defecto el relleno de cada nodo dice qué es (las hipótesis, el color de su familia de mecanismo) y el anillo cuánto lo sostiene: verde si está a un paso de una medición propia de Rosa (un análisis in silico validado, un resultado del laboratorio o una observación original), ámbar si solo hay literatura leída detrás, gris punteado si nada todavía. Con «Por distancia al dato» esa distancia pasa al relleno con una escala secuencial. Con «Vista 3D» el mismo árbol se despliega en tres dimensiones: arrastra el fondo para girarlo (en horizontal gira, en vertical se inclina), usa la rueda para acercar la cámara, y los nodos lejanos se ven más pequeños y tenues; si nadie lo toca durante unos segundos, gira solo. En 3D los nodos no se arrastran: el fondo gira el árbol.</p>
        </div>
        <div className="acciones">
          <div className="segmentos" role="group" aria-label="Vista del árbol">
            <button type="button" aria-pressed={!vista3d} onClick={() => cambiarVista('plana')} title="El árbol en el plano: arrastra el fondo para desplazarlo y los nodos para moverlos">
              Vista plana
            </button>
            <button type="button" aria-pressed={vista3d} onClick={() => cambiarVista('3d')} title="El árbol en tres dimensiones: arrastra el fondo para girarlo, rueda para acercar; lo lejano se ve pequeño y tenue">
              Vista 3D
            </button>
          </div>
          <div className="segmentos" role="group" aria-label="Color de los nodos">
            <button type="button" aria-pressed={modoColor === 'tipo'} onClick={() => setModoColor('tipo')} title="Relleno por tipo de nodo y por familia de mecanismo en las hipótesis; anillo por distancia al dato">
              Por tipo y mecanismo
            </button>
            <button type="button" aria-pressed={modoColor === 'dato'} onClick={() => setModoColor('dato')} title="Cuanto más intenso, más cerca de una medición propia de Rosa; ámbar, solo literatura leída; gris punteado, nada">
              Por distancia al dato
            </button>
          </div>
          <input className="entrada entrada-s" style={{ width: 220 }} value={texto} placeholder="Buscar en el árbol" onChange={(e) => setTexto(e.target.value)} aria-label="Buscar en el árbol" />
          <button type="button" className="btn btn-s" onClick={() => { setVisibles(visiblesIniciales(grafo, hip)); setSeleccion(null); setVista({ x: 0, y: 0, k: 1 }); setCamara(camaraInicial()); }}>
            Plegar todo
          </button>
          <button type="button" className="btn btn-s" onClick={() => { setVisibles(new Set(grafo.nodos.map((n) => n.id))); }} title="Despliega hasta las fuentes: puede ser mucho">
            Desplegar todo
          </button>
        </div>
      </div>

      <div className="grafo-marco">
        <svg ref={svgRef} className="grafo" viewBox={vista3d ? `0 0 ${ancho} ${alto}` : `${-ancho / 2} ${-alto / 2} ${ancho} ${alto}`} role="img" aria-label={`Árbol de ${inv.titulo}${vista3d ? ' en tres dimensiones' : ''}: ${nodosVisibles.length} nodos y ${enlacesVisibles.length} enlaces visibles`} onPointerDown={empezarArrastre} onPointerMove={mover} onPointerUp={soltar} onPointerCancel={soltar} onPointerLeave={() => setHover(null)}>
          {vista3d ? (
            <g>
              {enlacesVisibles.map((e) => {
                const a = proyecciones.get(e.de);
                const b = proyecciones.get(e.a);
                if (!a || !b) return null;
                const t = TRAZO[e.tipo];
                const vivo = !atenuar || (destacado(e.de) && destacado(e.a));
                // La niebla del enlace es la del extremo más lejano; el grosor sigue a la escala media.
                // Un extremo detrás de la cámara deja el enlace montado pero invisible.
                const op = a.visible && b.visible ? (vivo ? 0.75 : 0.12) * Math.min(niebla(a.profundidad, camara), niebla(b.profundidad, camara)) : 0;
                return <line key={`${e.de}|${e.a}|${e.tipo}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={t.color} strokeWidth={Math.max(0.4, t.ancho * ((a.escala + b.escala) / 2))} strokeDasharray={t.guion} opacity={op} className="grafo-enlace" style={ESTILO_3D} />;
              })}
              {ordenados.map((n) => {
                const p = proyecciones.get(n.id)!;
                const r = RADIO[n.tipo] * (0.8 + Math.min(1.4, n.peso) * 0.3) * p.escala;
                const vivo = destacado(n.id);
                const sel = seleccion === n.id;
                // La escala proyectada hace de zoom: las etiquetas pequeñas solo en los nodos cercanos.
                const opEt = p.visible ? opacidadEtiqueta(n, p.escala, vivo && atenuar, sel || hover === n.id) : 0;
                // La etiqueta encoge o crece con la profundidad (acotado para que siga leyéndose): otra pista de la tercera dimensión.
                const kEtiqueta = Math.max(0.6, Math.min(1.25, p.escala));
                return (
                  <g key={n.id} data-id={n.id} className={claseNodo(n, vivo, sel)} transform={`translate(${p.x} ${p.y})`} opacity={p.visible ? niebla(p.profundidad, camara) : 0} style={ESTILO_3D} {...propsNodo(n)} tabIndex={p.visible ? 0 : -1} pointerEvents={p.visible ? undefined : 'none'} aria-hidden={p.visible ? undefined : true}>
                    {n.tipo === 'objetivo' && <circle r={r + 6 * p.escala} fill="none" stroke="var(--accent)" strokeOpacity={0.25} strokeWidth={6 * p.escala} style={ESTILO_3D} />}
                    {circulo(n, r, true)}
                    <g transform={`scale(${p.escala})`}>{iconos(n)}</g>
                    {opEt > 0.02 && (
                      <g transform={`translate(0 ${r + 11}) scale(${kEtiqueta})`} style={ESTILO_3D}>
                        {etiqueta(n, 0, opEt, true)}
                      </g>
                    )}
                  </g>
                );
              })}
            </g>
          ) : (
            <g transform={`translate(${vista.x} ${vista.y}) scale(${vista.k})`}>
              {enlacesVisibles.map((e) => {
                const a = posiciones.get(e.de)!;
                const b = posiciones.get(e.a)!;
                const va = vaiven(e.de, grafo.porId.get(e.de)?.peso ?? 1);
                const vb = vaiven(e.a, grafo.porId.get(e.a)?.peso ?? 1);
                const t = TRAZO[e.tipo];
                const vivo = !atenuar || (destacado(e.de) && destacado(e.a));
                return <line key={`${e.de}|${e.a}|${e.tipo}`} x1={a.x + va.x} y1={a.y + va.y} x2={b.x + vb.x} y2={b.y + vb.y} stroke={t.color} strokeWidth={t.ancho} strokeDasharray={t.guion} opacity={vivo ? 0.75 : 0.12} className="grafo-enlace" />;
              })}
              {nodosVisibles.map((n) => {
                const p = posiciones.get(n.id)!;
                const r = RADIO[n.tipo] * (0.8 + Math.min(1.4, n.peso) * 0.3);
                const vivo = destacado(n.id);
                const sel = seleccion === n.id;
                const opEt = opacidadEtiqueta(n, vista.k, vivo && atenuar, sel || hover === n.id);
                const v = vaiven(n.id, n.peso);
                return (
                  <g key={n.id} data-id={n.id} className={claseNodo(n, vivo, sel)} transform={`translate(${p.x + v.x} ${p.y + v.y})`} {...propsNodo(n)}>
                    {n.tipo === 'objetivo' && <circle r={r + 6} fill="none" stroke="var(--accent)" strokeOpacity={0.25} strokeWidth={6} />}
                    {circulo(n, r, false)}
                    {iconos(n)}
                    {opEt > 0.02 && etiqueta(n, r + 11, opEt)}
                  </g>
                );
              })}
            </g>
          )}
        </svg>
        <aside className="grafo-panel">
          {nodoSel ? (
            <>
              <Chip tono="acento">{NOMBRE_TIPO[nodoSel.tipo]}</Chip>
              <h3>{nodoSel.etiqueta}</h3>
              {nodoSel.sub && <p className="meta">{nodoSel.sub}</p>}
              {nodoSel.alerta && <p className="tono-mal" style={{ fontSize: 13 }}>{nodoSel.alerta}</p>}
              {nodoSel.alias && nodoSel.alias.length > 1 && <p className="meta">Alias: {nodoSel.alias.slice(0, 8).join(', ')}</p>}
              <p className="meta">Aparece desde la iteración {nodoSel.iteracion || 1}.</p>
              {!SIN_DISTANCIA.has(nodoSel.tipo) && <p className="meta">{fraseProfundidad(nodoSel)}</p>}
              <h4>Conectado con</h4>
              <ul className="grafo-vecinos">
                {grafo.enlaces
                  .filter((e) => e.de === nodoSel.id || e.a === nodoSel.id)
                  .slice(0, 40)
                  .map((e) => {
                    const otro = grafo.porId.get(e.de === nodoSel.id ? e.a : e.de);
                    if (!otro) return null;
                    return (
                      <li key={`${e.de}|${e.a}|${e.tipo}`}>
                        <button type="button" className="enlace" onClick={() => { setSeleccion(otro.id); setVisibles((v) => new Set([...v, otro.id])); }}>
                          <span className="grafo-punto" style={{ background: colorDe(otro) }} aria-hidden="true" /> {otro.etiqueta.length > 60 ? `${otro.etiqueta.slice(0, 58)}...` : otro.etiqueta}
                        </button>
                        <span className="meta"> · {NOMBRE_ENLACE[e.tipo]}{e.etiqueta ? ` (${e.etiqueta})` : ''}</span>
                      </li>
                    );
                  })}
              </ul>
              {nodoSel.href && (
                <a className="btn btn-s" href={nodoSel.href}>
                  Abrir
                </a>
              )}
            </>
          ) : (
            <>
              <h3>Leyenda</h3>
              <p className="meta">Cada nodo tiene dos colores con dos mensajes: el de dentro dice qué es; el borde dice cuánta evidencia lo sostiene.</p>
              {modoColor === 'dato' ? (
                <>
                  <h4 className="grafo-leyenda-titulo">El color de dentro: a qué distancia está del dato</h4>
                  <p className="meta">En este modo el relleno cuenta los saltos que separan cada nodo de una medición propia de Rosa. Medición propia es un análisis in silico que pasó la auditoría, un resultado del laboratorio o una observación original sostenida.</p>
                  <ul className="grafo-leyenda">
                    {ESCALA_DATO.map((c, i) => (
                      <li key={`d${i}`}>
                        <span className="grafo-punto" style={{ background: c }} aria-hidden="true" /> {NOMBRE_ESCALA[i]}{i === 0 ? ': verde azulado intenso. Cuanto más claro, más lejos del dato.' : '.'}
                      </li>
                    ))}
                    {ESCALA_LIT.map((c, i) => (
                      <li key={`l${i}`}>
                        <span className="grafo-punto" style={{ background: c }} aria-hidden="true" /> {NOMBRE_ESCALA_LIT[i]}{i === 0 ? ': ámbar. Rosa lo sostiene con artículos, nunca lo ha medido; cuanto más intenso, más cerca de una fuente leída.' : '.'}
                      </li>
                    ))}
                    <li>
                      <span className="grafo-punto grafo-punto-nulo" aria-hidden="true" /> Sin medición propia ni literatura leída: gris punteado. Nada lo sostiene todavía.
                    </li>
                  </ul>
                  <p className="meta">El tronco, las áreas, las ramas y las entidades conservan su color: son estructura o nombres, no evidencia. Borde rojo: hay una alerta. Punteada: descartada o sin medición propia.</p>
                </>
              ) : (
                <>
                  <h4 className="grafo-leyenda-titulo">El color de dentro: qué es cada nodo</h4>
                  <ul className="grafo-leyenda">
                    <li>
                      <span className="grafo-punto" style={{ background: `conic-gradient(${PALETA_CLUSTER.slice(0, 6).join(', ')})` }} aria-hidden="true" /> {DEFINICION_TIPO.hipotesis} La rama que las agrupa lleva el mismo color.
                      {familias.length > 0 && (
                        <ul className="grafo-leyenda grafo-leyenda-sub">
                          {familias.map((f) => (
                            <li key={f}>
                              <span className="grafo-punto" style={{ background: colorFamilia(f) }} aria-hidden="true" /> {f}
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                    {(Object.keys(NOMBRE_TIPO) as TipoNodo[]).filter((t) => t !== 'hipotesis' && t !== 'rama' && tiposPresentes.has(t)).map((t) => (
                      <li key={t}>
                        <span className="grafo-punto" style={{ background: COLOR[t] }} aria-hidden="true" /> {DEFINICION_TIPO[t]}
                      </li>
                    ))}
                  </ul>
                  <h4 className="grafo-leyenda-titulo">El borde: cuánta evidencia lo sostiene</h4>
                  <ul className="grafo-leyenda">
                    <li><span className="grafo-punto grafo-anillo" style={{ borderColor: 'var(--grafo-dato-1)' }} aria-hidden="true" /> Anillo verde: a un paso de una medición propia de Rosa (un análisis in silico que pasó la auditoría, un resultado del laboratorio o una observación original). Es lo más sólido.</li>
                    <li><span className="grafo-punto grafo-anillo" style={{ borderColor: 'var(--grafo-lit-1)' }} aria-hidden="true" /> Anillo ámbar: solo literatura leída detrás. Rosa lo sostiene con artículos, pero nunca lo ha medido ella.</li>
                    <li><span className="grafo-punto grafo-anillo grafo-anillo-nulo" aria-hidden="true" /> Anillo gris punteado: nada lo sostiene todavía.</li>
                    <li><span className="grafo-punto grafo-anillo" style={{ borderColor: 'var(--red)' }} aria-hidden="true" /> Anillo rojo: hay una alerta (una contradicción, un bloqueo o una marca editorial). Manda sobre los demás.</li>
                    <li><span className="grafo-punto grafo-anillo grafo-anillo-rayas" aria-hidden="true" /> A rayas: hipótesis descartada.</li>
                  </ul>
                  <p className="meta">En resumen: dentro, qué es y a qué mecanismo pertenece; el borde, si Rosa lo midió (verde), solo lo leyó (ámbar) o aún no tiene nada (gris).</p>
                </>
              )}
              <h4 className="grafo-leyenda-titulo">Las líneas: cómo se conectan</h4>
              <ul className="grafo-leyenda">
                {(Object.keys(NOMBRE_ENLACE) as TipoEnlace[]).map((t) => (
                  <li key={t}>
                    <span className="grafo-linea" style={{ borderColor: TRAZO[t].color, borderStyle: TRAZO[t].guion ? 'dashed' : 'solid' }} aria-hidden="true" /> {NOMBRE_ENLACE[t]}
                  </li>
                ))}
              </ul>
            </>
          )}
        </aside>
      </div>
      <div className="grafo-tiempo">
        <button type="button" className="btn btn-s" aria-pressed={hasta === grafo.iteracionMax} onClick={() => setHasta(grafo.iteracionMax)}>
          {hasta === grafo.iteracionMax ? 'En vivo' : 'Volver al presente'}
        </button>
        <label htmlFor="grafo-iteracion">
          Cómo creció: hasta la iteración <strong>{hasta}</strong> de {grafo.iteracionMax}
        </label>
        <input id="grafo-iteracion" type="range" min={1} max={Math.max(1, grafo.iteracionMax)} value={Math.min(hasta, Math.max(1, grafo.iteracionMax))} onChange={(e) => setHasta(Number(e.target.value))} />
        <span className="meta">
          {nodosVisibles.length} nodos · {enlacesVisibles.length} enlaces
        </span>
      </div>
    </div>
  );
}
