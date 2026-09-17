// La vista 3D del árbol de la investigación (petición de Emir, 16 de
// septiembre de 2026: "me encanta la sección del árbol, ¿podrías hacer una
// vista 3D?"). Este módulo es puro y probado; el dibujo está en
// pantallas/Arbol.tsx, que reutiliza los mismos colores, anillos y alertas de
// la vista plana. Sin dependencias nuevas: la geometría cabe en cien líneas.
//
// Cómo funciona, con los conceptos por su nombre:
//
// 1. DISPOSICIÓN POR FUERZAS EN TRES EJES (paso3d). Las mismas fuerzas que
//    `paso` en lib/arbol.ts, pero con una coordenada z además de x e y:
//    repulsión entre todos los nodos (como cargas eléctricas del mismo signo),
//    un resorte por cada enlace (tira hacia su longitud de reposo), gravedad
//    suave hacia el tronco, que está fijo en el origen (0, 0, 0), y un
//    rozamiento que enfría el movimiento. Lo que en la vista plana nacía en un
//    anillo alrededor del tronco aquí nace en una ESFERA, repartido con una
//    espiral de Fibonacci (ángulo dorado para el giro, alturas espaciadas por
//    igual): así las ramas no se apilan ni caen todas en el mismo plano.
//
// 2. CÁMARA ORBITAL (Camara). La cámara gira alrededor del tronco, no se
//    desplaza. Tres números la describen: la GUIÑADA (giro alrededor del eje
//    vertical, como girar la cabeza a izquierda y derecha), el CABECEO
//    (inclinación arriba y abajo, acotada a más o menos 80 grados para no
//    pasar por encima del polo y ver el árbol boca abajo) y la DISTANCIA al
//    tronco (la rueda la cambia: acercarse es reducirla). Los ángulos van en
//    radianes.
//
// 3. PROYECCIÓN EN PERSPECTIVA (proyectar). Primero se rota el punto con la
//    guiñada y el cabeceo, de modo que la cámara quede siempre mirando al
//    tronco por el eje z. Después se aplica la perspectiva de una cámara
//    estenopeica (un agujero por el que pasan los rayos): las coordenadas x e y
//    se dividen por la profundidad, que es la distancia del punto a la cámara.
//    La escala resultante es DISTANCIA FOCAL / profundidad: un nodo al doble
//    de distancia se ve a la mitad. El radio de cada círculo se multiplica por
//    esa escala y la pantalla le baja la opacidad con la profundidad (niebla),
//    así el ojo lee la tercera dimensión sin gafas. Un punto que queda detrás
//    de la cámara, o más cerca que el plano cercano, no se dibuja
//    (visible = false): su proyección daría un número gigante o invertido.
//
// 4. ORDEN DE PINTADO (ordenarPorProfundidad). Un SVG pinta en el orden del
//    documento: lo último tapa a lo primero. Los nodos se ordenan de lejos a
//    cerca (el "algoritmo del pintor") para que los cercanos queden encima.
//    Ese orden cambia al girar y React mueve los elementos en el DOM; el
//    navegador trata cada movimiento como una inserción nueva y reinicia la
//    animación de entrada y las transiciones CSS de los nodos, lo que se veía
//    como un parpadeo (Emir, 17 de septiembre de 2026). Por eso la pantalla
//    apaga en línea esas animaciones en la vista 3D y no desmonta los nodos
//    que quedan detrás de la cámara: los pinta con opacidad cero.
//
// 5. ENCUADRE AUTOMÁTICO (distanciaEncuadre). Al cambiar lo visible (desplegar,
//    plegar, el deslizador) la cámara se aleja o se acerca sola hasta que el
//    árbol entero cabe en el lienzo con margen; la rueda apaga ese ajuste.
//
// Nota sobre la fórmula: el diseño hablaba de escala = focal / (focal + z +
// distancia). Esa forma es la misma cámara estenopeica con el agujero
// desplazado una focal hacia atrás; aquí la constante se pliega en la
// distancia para que `distancia` sea de verdad la separación entre la cámara
// y el tronco y la escala valga 1 cuando distancia = FOCAL.

import { type Grafo, type TipoEnlace } from './arbol';

export interface Posicion3 {
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  fijo?: boolean;
}

export interface Camara {
  /** Giro alrededor del eje vertical, en radianes. */
  guinada: number;
  /** Inclinación arriba y abajo, en radianes, acotada a más o menos CABECEO_MAXIMO. */
  cabeceo: number;
  /** Separación entre la cámara y el tronco, en unidades del lienzo. */
  distancia: number;
}

export interface Proyeccion {
  /** Coordenadas en el lienzo, con el tronco en el centro (ancho/2, alto/2). */
  x: number;
  y: number;
  /** Factor por el que se multiplica el radio: 1 a la distancia focal, menor más lejos. */
  escala: number;
  /** Distancia del punto a la cámara; mayor es más lejos. */
  profundidad: number;
  /** false si el punto está detrás de la cámara o más cerca que el plano cercano. */
  visible: boolean;
}

/** Distancia focal de la cámara estenopeica: a esa distancia la escala es 1. */
export const FOCAL = 900;
/** La cámara no se acerca más que esto al tronco (escala máxima en el tronco: FOCAL / DISTANCIA_MINIMA). */
export const DISTANCIA_MINIMA = 350;
/** Ni se aleja más que esto (escala mínima en el tronco: 0,25). */
export const DISTANCIA_MAXIMA = 3600;
/** Distancia con la que se abre la vista: el árbol entero cabe en el lienzo. */
export const DISTANCIA_INICIAL = 1000;
/** Plano cercano: lo que está a menos de esta distancia de la cámara no se dibuja. */
export const PLANO_CERCANO = 40;
/** Un nodo pegado a la cámara no puede crecer sin límite: tope de la escala. */
export const ESCALA_MAXIMA = 4;
/** Cabeceo máximo (80 grados): impide pasar por encima del polo y ver el árbol invertido. */
export const CABECEO_MAXIMO = (80 * Math.PI) / 180;
/** Giro automático en reposo, en radianes por segundo: una vuelta entera cada 42 segundos. */
export const VELOCIDAD_GIRO = 0.15;
/** Segundos sin tocar el árbol antes de que empiece a girar solo. */
export const ESPERA_GIRO_MS = 3000;
/** Radianes de giro por píxel arrastrado: unos 400 píxeles dan media vuelta. */
export const SENSIBILIDAD_GIRO = 0.008;
/** A esta distancia por detrás del tronco la niebla llega a su opacidad mínima. */
export const ALCANCE_NIEBLA = 900;
export const OPACIDAD_MINIMA_NIEBLA = 0.22;
/** Margen, en unidades del lienzo, que el encuadre automático deja entre el
 *  centro del nodo más externo y el borde: cabe el círculo y su etiqueta. */
export const MARGEN_ENCUADRE = 40;

/** Ángulo dorado en radianes: el giro entre dos puntos consecutivos de la espiral. */
const ANGULO_DORADO = (137.508 * Math.PI) / 180;
/** Alturas distintas de la espiral de Fibonacci antes de repetir altura (con otro giro). */
const PUNTOS_ESPIRAL = 64;

/** Un número finito o, si no lo es (NaN, infinito), el valor por defecto. */
export const sinNaN = (v: number, porDefecto = 0): number => (Number.isFinite(v) ? v : porDefecto);

export function camaraInicial(): Camara {
  // Un poco de lado y desde arriba: con la cámara de frente el árbol parece plano.
  return { guinada: 0.55, cabeceo: 0.35, distancia: DISTANCIA_INICIAL };
}

/** La cámara dentro de sus límites y sin NaN: guiñada en [-pi, pi], cabeceo
 *  acotado, distancia entre la mínima y la máxima. */
export function acotarCamara(c: Camara): Camara {
  const dosPi = Math.PI * 2;
  let guinada = sinNaN(c.guinada) % dosPi;
  if (guinada > Math.PI) guinada -= dosPi;
  if (guinada < -Math.PI) guinada += dosPi;
  return {
    guinada,
    cabeceo: Math.max(-CABECEO_MAXIMO, Math.min(CABECEO_MAXIMO, sinNaN(c.cabeceo))),
    distancia: Math.max(DISTANCIA_MINIMA, Math.min(DISTANCIA_MAXIMA, sinNaN(c.distancia, DISTANCIA_INICIAL))),
  };
}

/** Dirección k de una espiral de Fibonacci sobre la esfera unidad: la altura
 *  baja por escalones iguales (PUNTOS_ESPIRAL alturas, después vuelve a empezar)
 *  y el giro avanza un ángulo dorado por punto, que nunca se repite. Dos puntos
 *  consecutivos quedan siempre lejos, y los de una misma altura, en giros distintos. */
export function direccionEsfera(k: number): { x: number; y: number; z: number } {
  const i = Math.abs(Math.trunc(sinNaN(k)));
  const y = 1 - (2 * ((i % PUNTOS_ESPIRAL) + 0.5)) / PUNTOS_ESPIRAL;
  const radio = Math.sqrt(Math.max(0, 1 - y * y));
  const ang = i * ANGULO_DORADO;
  return { x: Math.cos(ang) * radio, y, z: Math.sin(ang) * radio };
}

/** Un punto en el sistema de la cámara: primero la guiñada (giro alrededor del
 *  eje vertical y), después el cabeceo (giro alrededor del eje horizontal x).
 *  Tras rotar, la cámara está en el eje z negativo mirando hacia el origen. */
export function rotar(p: { x: number; y: number; z: number }, camara: Camara): { x: number; y: number; z: number } {
  const x = sinNaN(p.x);
  const y = sinNaN(p.y);
  const z = sinNaN(p.z);
  const cg = Math.cos(camara.guinada);
  const sg = Math.sin(camara.guinada);
  const x1 = x * cg + z * sg;
  const z1 = -x * sg + z * cg;
  const cc = Math.cos(camara.cabeceo);
  const sc = Math.sin(camara.cabeceo);
  return { x: x1, y: y * cc - z1 * sc, z: y * sc + z1 * cc };
}

/** Perspectiva de cámara estenopeica: la cámara está a `distancia` del tronco
 *  por el eje z negativo; la profundidad de un punto es z rotada + distancia y
 *  la escala, FOCAL / profundidad. El resultado va centrado en (ancho/2, alto/2). */
export function proyectar(p: { x: number; y: number; z: number }, camara: Camara, ancho: number, alto: number): Proyeccion {
  const r = rotar(p, camara);
  const profundidad = r.z + sinNaN(camara.distancia, DISTANCIA_INICIAL);
  const cx = sinNaN(ancho) / 2;
  const cy = sinNaN(alto) / 2;
  if (!(profundidad > PLANO_CERCANO)) return { x: cx, y: cy, escala: 0, profundidad: sinNaN(profundidad), visible: false };
  const escala = Math.min(ESCALA_MAXIMA, FOCAL / profundidad);
  return { x: cx + r.x * escala, y: cy + r.y * escala, escala, profundidad, visible: true };
}

/** Distancia de cámara con la que todos los puntos caben en el lienzo con un
 *  margen (ENCUADRE AUTOMÁTICO). Para cada punto rotado r, que quede dentro
 *  exige |r.x| · FOCAL / (r.z + D) <= px, es decir D >= |r.x| · FOCAL / px - r.z
 *  (y lo mismo en y), además de quedar delante del plano cercano; la distancia
 *  necesaria es el mayor de esos mínimos. Nunca baja de DISTANCIA_INICIAL (un
 *  árbol pequeño no se agranda hasta llenar la pantalla) y siempre queda entre
 *  la mínima y la máxima. Sin puntos, la inicial. Depende de la orientación de
 *  la cámara: al girar, el árbol que cabía puede asomar un poco por el margen. */
export function distanciaEncuadre(puntos: Iterable<{ x: number; y: number; z: number }>, camara: Camara, ancho: number, alto: number): number {
  const px = Math.max(1, sinNaN(ancho) / 2 - MARGEN_ENCUADRE);
  const py = Math.max(1, sinNaN(alto) / 2 - MARGEN_ENCUADRE);
  let necesaria = DISTANCIA_INICIAL;
  for (const p of puntos) {
    const r = rotar(p, camara);
    necesaria = Math.max(necesaria, (Math.abs(r.x) * FOCAL) / px - r.z, (Math.abs(r.y) * FOCAL) / py - r.z, PLANO_CERCANO + 1 - r.z);
  }
  return Math.max(DISTANCIA_MINIMA, Math.min(DISTANCIA_MAXIMA, sinNaN(necesaria, DISTANCIA_INICIAL)));
}

/** Opacidad por profundidad: 1 hasta la distancia del tronco, y de ahí baja en
 *  línea recta hasta OPACIDAD_MINIMA_NIEBLA a ALCANCE_NIEBLA unidades por detrás. */
export function niebla(profundidad: number, camara: Camara): number {
  const detras = sinNaN(profundidad) - sinNaN(camara.distancia, DISTANCIA_INICIAL);
  if (detras <= 0) return 1;
  return Math.max(OPACIDAD_MINIMA_NIEBLA, 1 - (detras / ALCANCE_NIEBLA) * (1 - OPACIDAD_MINIMA_NIEBLA));
}

/** Los identificadores con posición, de lejos a cerca (algoritmo del pintor):
 *  lo que se pinta después queda encima, así que los cercanos van al final. */
export function ordenarPorProfundidad(ids: Iterable<string>, posiciones: Map<string, Posicion3>, camara: Camara): string[] {
  const conZ: { id: string; z: number }[] = [];
  for (const id of ids) {
    const p = posiciones.get(id);
    if (p) conZ.push({ id, z: rotar(p, camara).z });
  }
  // Orden estable por identificador cuando dos nodos están a la misma profundidad.
  conZ.sort((a, b) => b.z - a.z || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  return conZ.map((c) => c.id);
}

/* ---------------------------------------------------------------------
   Disposición por fuerzas en tres ejes. Mismas constantes que lib/arbol.ts
   (LARGO no está exportado allí y se copia con sus valores: si cambian los de
   la vista plana, cambiar estos).
   --------------------------------------------------------------------- */

const LARGO: Record<TipoEnlace, number> = { rama: 230, cita: 110, respalda: 140, entidad: 130, causal: 170, rival: 240, experimento: 150, dato: 120 };
/** Longitud de reposo para un tipo de enlace que este mapa no conoce (un dato
 *  nuevo del servidor antes de que la interfaz lo aprenda): sin ella la fuerza
 *  saldría NaN y el nodo perdería su resorte. */
const LARGO_POR_DEFECTO = 150;
/** El peso de un nodo saneado: finito y positivo. Un peso NaN (un Elo roto en el
 *  estado) haría NaN la repulsión de todos los pares en los que entra; al
 *  repararla a cero, el árbol se quedaría solo con la gravedad y colapsaría
 *  despacio hacia el tronco. Con peso cero dos nodos coincidentes nunca se
 *  separarían: por eso el mínimo es 0,1. */
const pesoDe = (n: { peso?: number } | undefined): number => Math.max(0.1, sinNaN(n?.peso ?? 1, 1));
const VELOCIDAD_BASE = 2;
const VELOCIDAD_POR_ALFA = 28;
/** Radio de la esfera donde nacen las ramas y las hojas que cuelgan del tronco. */
const RADIO_RAMA = 160;
const RADIO_HOJA = 220;
/** Un nodo nuevo nace a esta distancia de su vecino ya colocado. */
const SALTO_VECINO = 28;

export function posicionInicial3d(g: Grafo, posiciones: Map<string, Posicion3>, id: string, semilla: number): Posicion3 {
  const n = g.porId.get(id);
  if (n?.tipo === 'objetivo') return { x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0, fijo: true };
  const vecinos = [...(g.vecinos.get(id) ?? [])];
  const dir = direccionEsfera(semilla);
  // Nace junto a un vecino ya colocado (el árbol crece desde la rama), en una
  // dirección de la espiral para que dos hojas de la misma rama no coincidan.
  const colocado = vecinos.find((v) => v !== 'objetivo' && posiciones.has(v));
  const vecino = colocado ? posiciones.get(colocado) : undefined;
  if (vecino) return { x: vecino.x + dir.x * SALTO_VECINO, y: vecino.y + dir.y * SALTO_VECINO, z: vecino.z + dir.z * SALTO_VECINO, vx: 0, vy: 0, vz: 0 };
  // Cuelga del tronco o no tiene vecino colocado: nace sobre la esfera.
  const esRama = n?.tipo === 'rama' || n?.tipo === 'area';
  const r = vecinos.includes('objetivo') ? (esRama ? RADIO_RAMA : RADIO_HOJA) : esRama ? RADIO_RAMA - 20 : RADIO_HOJA + 50;
  return { x: dir.x * r, y: dir.y * r, z: dir.z * r, vx: 0, vy: 0, vz: 0 };
}

export function paso3d(g: Grafo, visibles: Set<string>, posiciones: Map<string, Posicion3>, alfa: number): void {
  const a_ = sinNaN(alfa);
  const ids = [...visibles].filter((id) => posiciones.has(id));
  // Lo que no cambia dentro del doble bucle se calcula una vez por nodo (y no
  // una vez por par): la posición, el peso saneado y si tiene etiqueta que leer.
  // Con 400 nodos son 80.000 pares por paso; esto no cambia el resultado.
  const cuerpos = ids.map((id) => posiciones.get(id)!);
  const pesos = ids.map((id) => pesoDe(g.porId.get(id)));
  const conEtiqueta = ids.map((id) => {
    const n = g.porId.get(id);
    return n !== undefined && n.tipo !== 'fuente' && n.tipo !== 'entidad';
  });
  // Repulsión entre todos los pares. Dos nodos exactamente en el mismo punto se
  // separan por una dirección de la espiral que depende del par, no del azar:
  // así la disposición es determinista y los tests, reproducibles.
  for (let i = 0; i < ids.length; i++) {
    const a = cuerpos[i]!;
    const pa = pesos[i]!;
    for (let j = i + 1; j < ids.length; j++) {
      const b = cuerpos[j]!;
      const pb = pesos[j]!;
      let dx = a.x - b.x;
      let dy = a.y - b.y;
      let dz = a.z - b.z;
      let d2 = dx * dx + dy * dy + dz * dz;
      if (!(d2 >= 1)) {
        const dir = direccionEsfera(i * 1009 + j);
        dx = dir.x;
        dy = dir.y;
        dz = dir.z;
        d2 = 1;
      }
      // Saturada por debajo de 12 unidades (como en la vista plana) y mayor
      // entre dos nodos con etiqueta, que son los que tienen texto que leer.
      const conTexto = conEtiqueta[i] && conEtiqueta[j] ? 1.8 : 1;
      const f = (3400 * conTexto * (pa + pb) * 0.5 * a_) / Math.max(d2, 144);
      const d = Math.sqrt(d2);
      const fx = (dx / d) * f;
      const fy = (dy / d) * f;
      const fz = (dz / d) * f;
      if (!a.fijo) {
        a.vx += fx;
        a.vy += fy;
        a.vz += fz;
      }
      if (!b.fijo) {
        b.vx -= fx;
        b.vy -= fy;
        b.vz -= fz;
      }
    }
  }
  // Resortes: cada enlace tira hacia su longitud de reposo.
  for (const e of g.enlaces) {
    if (!visibles.has(e.de) || !visibles.has(e.a)) continue;
    const a = posiciones.get(e.de);
    const b = posiciones.get(e.a);
    if (!a || !b) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dz = b.z - a.z;
    const d = Math.max(1, Math.sqrt(dx * dx + dy * dy + dz * dz));
    const f = ((d - (LARGO[e.tipo] ?? LARGO_POR_DEFECTO)) / d) * 0.06 * a_;
    if (!a.fijo) {
      a.vx += dx * f;
      a.vy += dy * f;
      a.vz += dz * f;
    }
    if (!b.fijo) {
      b.vx -= dx * f;
      b.vy -= dy * f;
      b.vz -= dz * f;
    }
  }
  // Gravedad hacia el tronco, rozamiento, tope de velocidad y movimiento.
  for (const id of ids) {
    const p = posiciones.get(id)!;
    if (p.fijo) continue;
    p.vx = sinNaN(p.vx) - sinNaN(p.x) * 0.004 * a_;
    p.vy = sinNaN(p.vy) - sinNaN(p.y) * 0.004 * a_;
    p.vz = sinNaN(p.vz) - sinNaN(p.z) * 0.004 * a_;
    p.vx *= 0.82;
    p.vy *= 0.82;
    p.vz *= 0.82;
    const tope = VELOCIDAD_BASE + VELOCIDAD_POR_ALFA * a_;
    const v = Math.hypot(p.vx, p.vy, p.vz);
    if (v > tope) {
      p.vx *= tope / v;
      p.vy *= tope / v;
      p.vz *= tope / v;
    }
    p.x = sinNaN(sinNaN(p.x) + p.vx);
    p.y = sinNaN(sinNaN(p.y) + p.vy);
    p.z = sinNaN(sinNaN(p.z) + p.vz);
  }
}
