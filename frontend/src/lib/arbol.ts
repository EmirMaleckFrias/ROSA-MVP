// El arbol de la investigacion como grafo: el objetivo es el tronco, las
// ramas son los clusters de mecanismo (y las areas del programa), las hojas
// son las hipotesis, y alrededor lo que las sostiene: hechos del modelo de
// mundo, fuentes, entidades canonicas, relaciones causales, rivales del
// torneo y el experimento que llego al laboratorio. Todo sale del estado; no
// se inventa ningun enlace. Aqui va el modelo (puro y probado); el dibujo
// esta en pantallas/Arbol.tsx.

import type { EstadoRosa, Hipotesis, Investigacion } from '../datos/tipos';
import { rutaDe } from './ruta';

export type TipoNodo = 'objetivo' | 'rama' | 'area' | 'hipotesis' | 'hecho' | 'pregunta' | 'fuente' | 'entidad' | 'experimento';
export type TipoEnlace = 'rama' | 'cita' | 'respalda' | 'entidad' | 'causal' | 'rival' | 'experimento';

export interface NodoArbol {
  id: string;
  tipo: TipoNodo;
  etiqueta: string;
  sub?: string;
  /** Tamano relativo (el Elo en las hipotesis, el numero de conexiones en lo demas). */
  peso: number;
  /** Primera iteracion en la que existio: para ver crecer el arbol. */
  iteracion: number;
  href?: string;
  estado?: string;
  alerta?: string;
  alias?: string[];
}

export interface EnlaceArbol {
  de: string;
  a: string;
  tipo: TipoEnlace;
  etiqueta?: string;
}

export interface Grafo {
  nodos: NodoArbol[];
  enlaces: EnlaceArbol[];
  vecinos: Map<string, Set<string>>;
  porId: Map<string, NodoArbol>;
  iteracionMax: number;
}

export const NOMBRE_TIPO: Record<TipoNodo, string> = {
  objetivo: 'Objetivo',
  rama: 'Cluster de mecanismo',
  area: 'Área del programa',
  hipotesis: 'Hipotesis',
  hecho: 'Hecho del modelo de mundo',
  pregunta: 'Pregunta abierta',
  fuente: 'Fuente',
  entidad: 'Entidad canónica',
  experimento: 'Experimento en el laboratorio',
};

export const NOMBRE_ENLACE: Record<TipoEnlace, string> = {
  rama: 'pertenece a',
  cita: 'cita',
  respalda: 'respalda',
  entidad: 'nombra',
  causal: 'relación causal',
  rival: 'rival en el torneo',
  experimento: 'se prueba en',
};

const VIVA = (h: Hipotesis) => h.estado !== 'descartada';

export function construirArbol(estado: EstadoRosa, inv: Investigacion): Grafo {
  const nodos: NodoArbol[] = [];
  const enlaces: EnlaceArbol[] = [];
  const vistos = new Set<string>();
  const enlacesVistos = new Set<string>();
  const anadir = (n: NodoArbol) => {
    if (vistos.has(n.id)) return;
    vistos.add(n.id);
    nodos.push(n);
  };
  const enlazar = (de: string, a: string, tipo: TipoEnlace, etiqueta?: string) => {
    if (de === a || !vistos.has(de) || !vistos.has(a)) return;
    const clave = [de, a, tipo].join('|');
    const inversa = [a, de, tipo].join('|');
    if (enlacesVistos.has(clave) || (tipo === 'rival' && enlacesVistos.has(inversa))) return;
    enlacesVistos.add(clave);
    enlaces.push({ de, a, tipo, etiqueta });
  };

  const hip = estado.hipotesis.filter((h) => h.investigacionId === inv.id);
  const hechos = estado.hechos.filter((h) => h.investigacionId === inv.id);
  const iteracionMax = Math.max(1, ...hip.map((h) => h.iteracion), ...estado.iteraciones.filter((i) => estado.corridas.some((c) => c.id === i.corridaId && c.investigacionId === inv.id)).map((i) => i.numero));

  anadir({ id: 'objetivo', tipo: 'objetivo', etiqueta: inv.titulo, sub: inv.objetivo, peso: 4, iteracion: 0, href: rutaDe(inv.id, 'investigacion') });
  for (const a of inv.mision?.areas ?? []) {
    anadir({ id: `area-${a.id}`, tipo: 'area', etiqueta: a.titulo, sub: a.familiaMecanismo, peso: 2, iteracion: 0, estado: a.estado, href: rutaDe(inv.id, 'investigacion') });
    enlazar('objetivo', `area-${a.id}`, 'rama');
  }
  // Una rama solo cuando agrupa dos o mas hipotesis: un cluster con una sola
  // hipotesis no aporta nada como nodo y llenaba el arbol de circulos con
  // texto pegado. Esas hipotesis cuelgan directamente del tronco.
  const clusters = [...new Set(hip.map((h) => h.cluster || 'Sin cluster'))];
  const conRama = new Set<string>();
  for (const c of clusters) {
    const n = hip.filter((h) => (h.cluster || 'Sin cluster') === c);
    if (n.length < 2) continue;
    conRama.add(c);
    anadir({ id: `rama-${c}`, tipo: 'rama', etiqueta: c, sub: `${n.length} hipotesis`, peso: 2 + Math.min(3, n.length) * 0.4, iteracion: Math.min(...n.map((h) => h.iteracion)), href: rutaDe(inv.id, 'ranking') });
    enlazar('objetivo', `rama-${c}`, 'rama');
    // Un area cuyo titulo o familia coincide con el cluster lo adopta.
    const area = (inv.mision?.areas ?? []).find((a) => a.titulo.toLowerCase() === c.toLowerCase() || a.familiaMecanismo.toLowerCase() === c.toLowerCase());
    if (area) enlazar(`area-${area.id}`, `rama-${c}`, 'rama');
  }
  for (const h of hip) {
    const bloqueos = h.bloqueos ?? [];
    const alerta = h.estado === 'descartada' ? 'descartada' : h.decisionKiller === 'descartar_en_contexto' ? 'el Killer propone descartar' : bloqueos.length ? `${bloqueos.length} ${bloqueos.length === 1 ? 'bloqueo' : 'bloqueos'}` : undefined;
    anadir({ id: h.id, tipo: 'hipotesis', etiqueta: h.titulo, sub: `${h.cluster || 'Sin cluster'} · Elo ${h.elo}${h.candidata ? ' · candidata' : ''}`, peso: 1.5 + Math.max(0, (h.elo - 1300) / 200), iteracion: h.iteracion, href: rutaDe(inv.id, 'hipotesis', h.id), estado: h.estado, alerta });
    enlazar(conRama.has(h.cluster || 'Sin cluster') ? `rama-${h.cluster || 'Sin cluster'}` : 'objetivo', h.id, 'rama');
    if (h.experimento && h.experimento.estado !== 'propuesto') {
      anadir({ id: `ex-${h.id}`, tipo: 'experimento', etiqueta: h.experimento.laboratorio ? `Experimento en ${h.experimento.laboratorio}` : 'Experimento', sub: h.experimento.estado.replace('_', ' ') + (h.experimento.prerregistradoEn ? ' · prerregistrado' : ''), peso: 2, iteracion: h.iteracion, href: rutaDe(inv.id, 'hipotesis', h.id), estado: h.experimento.estado });
      enlazar(h.id, `ex-${h.id}`, 'experimento');
    }
  }
  // Entidades canonicas: un nodo por identificador, con sus alias.
  const entidad = (x: { id: string; etiqueta: string; ontologia: string; tipo: string; alias: string[] }, iteracion: number) => {
    const id = `ent-${x.id}`;
    if (!vistos.has(id)) anadir({ id, tipo: 'entidad', etiqueta: x.etiqueta, sub: `${x.ontologia} ${x.id} · ${x.tipo}`, peso: 1, iteracion, alias: [x.id, ...x.alias] });
    else {
      const n = nodos.find((n) => n.id === id)!;
      n.iteracion = Math.min(n.iteracion, iteracion);
    }
    return id;
  };
  for (const h of hip) for (const x of h.entidades ?? []) enlazar(h.id, entidad(x, h.iteracion), 'entidad');
  // Hechos y preguntas del modelo de mundo, unidos a las hipotesis que comparten fuente o entidad.
  const fuentesDe = new Map(hip.map((h) => [h.id, new Set(h.procedencia.fuentes.map((f) => f.id))]));
  for (const he of hechos) {
    const tipo: TipoNodo = he.tipo === 'pregunta' || he.estado === 'abierto' ? 'pregunta' : 'hecho';
    const relacionadas = hip.filter((h) => he.id === `he-${h.id}` || he.procedencia.some((p) => fuentesDe.get(h.id)?.has(p.fuenteId)));
    const iteracion = relacionadas.length ? Math.min(...relacionadas.map((h) => h.iteracion)) : iteracionMax;
    anadir({ id: `he-${he.id}`, tipo, etiqueta: he.enunciado.length > 90 ? `${he.enunciado.slice(0, 87)}...` : he.enunciado, sub: `${he.tema} · ${he.estado}`, peso: 1 + Math.min(2, relacionadas.length * 0.3), iteracion, href: rutaDe(inv.id, 'mundo'), estado: he.estado });
    for (const h of relacionadas) enlazar(`he-${he.id}`, h.id, 'respalda');
    for (const x of he.entidades ?? []) enlazar(`he-${he.id}`, entidad(x, iteracion), 'entidad');
  }
  // Fuentes: un nodo por articulo, citado por las hipotesis (y respaldando hechos).
  for (const h of hip) {
    for (const f of h.procedencia.fuentes) {
      const id = `fu-${f.id}`;
      if (!vistos.has(id)) anadir({ id, tipo: 'fuente', etiqueta: f.referencia, sub: f.titulo, peso: 1, iteracion: h.iteracion, alerta: f.retraccion ? `marca editorial: ${f.retraccion}` : undefined, estado: f.retraccion ?? undefined });
      enlazar(h.id, id, 'cita');
    }
  }
  for (const he of hechos) for (const p of he.procedencia) if (vistos.has(`fu-${p.fuenteId}`)) enlazar(`fu-${p.fuenteId}`, `he-${he.id}`, 'respalda');
  // Relaciones causales de cada hipotesis, entre entidades canonicas.
  for (const h of hip) {
    const g = h.grafoCausal;
    if (!g) continue;
    const canon = new Map(g.nodos.map((n) => [n.id, (n as { idCanonico?: string }).idCanonico]));
    for (const a of g.aristas) {
      const de = canon.get(a.de);
      const hasta = canon.get(a.a);
      if (de && hasta && vistos.has(`ent-${de}`) && vistos.has(`ent-${hasta}`)) enlazar(`ent-${de}`, `ent-${hasta}`, 'causal', a.tipo.replace(/_/g, ' '));
    }
  }
  // Rivales del torneo.
  for (const h of hip) for (const p of h.partidos) if (vistos.has(p.rivalId)) enlazar(h.id, p.rivalId, 'rival', p.resultado);
  // Peso por conexiones para lo que no es hipotesis.
  const grado = new Map<string, number>();
  for (const e of enlaces) {
    grado.set(e.de, (grado.get(e.de) ?? 0) + 1);
    grado.set(e.a, (grado.get(e.a) ?? 0) + 1);
  }
  for (const n of nodos) if (n.tipo === 'entidad' || n.tipo === 'fuente') n.peso = 1 + Math.min(2.5, (grado.get(n.id) ?? 0) * 0.25);
  const vecinos = new Map<string, Set<string>>();
  for (const e of enlaces) {
    if (!vecinos.has(e.de)) vecinos.set(e.de, new Set());
    if (!vecinos.has(e.a)) vecinos.set(e.a, new Set());
    vecinos.get(e.de)!.add(e.a);
    vecinos.get(e.a)!.add(e.de);
  }
  return { nodos, enlaces, vecinos, porId: new Map(nodos.map((n) => [n.id, n])), iteracionMax };
}

/** Lo que se ve al abrir: el tronco, las ramas, las hipotesis vivas y los
 *  experimentos. Lo demas se despliega al pulsar. */
export function visiblesIniciales(g: Grafo, hip: Hipotesis[]): Set<string> {
  const v = new Set<string>();
  for (const n of g.nodos) {
    if (n.tipo === 'objetivo' || n.tipo === 'rama' || n.tipo === 'area' || n.tipo === 'experimento') v.add(n.id);
    if (n.tipo === 'hipotesis' && hip.some((h) => h.id === n.id && VIVA(h))) v.add(n.id);
  }
  return v;
}

/** Despliega los vecinos de un nodo (o los pliega si ya estaban todos). */
export function alternar(g: Grafo, visibles: Set<string>, id: string): Set<string> {
  const vecinos = [...(g.vecinos.get(id) ?? [])];
  const nuevo = new Set(visibles);
  const ocultos = vecinos.filter((v) => !nuevo.has(v));
  if (ocultos.length > 0) for (const v of ocultos) nuevo.add(v);
  else {
    // Plegar: quitar los vecinos que solo se sostienen por este nodo.
    for (const v of vecinos) {
      const n = g.porId.get(v);
      if (!n || n.tipo === 'objetivo' || n.tipo === 'rama' || n.tipo === 'area' || n.tipo === 'hipotesis') continue;
      const otros = [...(g.vecinos.get(v) ?? [])].filter((o) => o !== id && nuevo.has(o));
      if (otros.length === 0) nuevo.delete(v);
    }
  }
  return nuevo;
}

/** Nodos cuya etiqueta, subtitulo, alias o identificador contienen el texto. */
export function buscar(g: Grafo, texto: string): Set<string> {
  const q = texto.trim().toLowerCase();
  const r = new Set<string>();
  if (q.length < 2) return r;
  for (const n of g.nodos) {
    if (n.etiqueta.toLowerCase().includes(q) || (n.sub ?? '').toLowerCase().includes(q) || (n.alias ?? []).some((a) => a.toLowerCase() === q || a.toLowerCase().includes(q))) r.add(n.id);
  }
  return r;
}

/* ---------------------------------------------------------------------
   Disposicion por fuerzas: repulsion entre todos, resorte por enlace, el
   tronco fijo en el centro y una gravedad suave. Determinista con la misma
   semilla; se para sola al enfriarse.
   --------------------------------------------------------------------- */

export interface Posicion {
  x: number;
  y: number;
  vx: number;
  vy: number;
  fijo?: boolean;
}

// Longitudes de reposo de los enlaces. Más largas que el ancho de una
// etiqueta media (unas 120 unidades) para que dos nodos unidos no se monten.
const LARGO: Record<TipoEnlace, number> = { rama: 230, cita: 110, respalda: 140, entidad: 130, causal: 170, rival: 240, experimento: 150 };

/** Anchura aproximada de la etiqueta de un nodo (en unidades del lienzo), para
 *  que las fuerzas dejen sitio al texto y no solo al circulo. */
export function anchoEtiqueta(n: NodoArbol): number {
  const chars = Math.min(n.etiqueta.length, 30);
  const tam = n.tipo === 'objetivo' ? 7 : n.tipo === 'rama' || n.tipo === 'hipotesis' || n.tipo === 'experimento' ? 5.8 : 5;
  return chars * tam;
}

export function posicionInicial(g: Grafo, posiciones: Map<string, Posicion>, id: string, semilla: number): Posicion {
  // Nace junto a un vecino ya colocado (el arbol crece desde la rama), o en un anillo.
  const n = g.porId.get(id);
  if (n?.tipo === 'objetivo') return { x: 0, y: 0, vx: 0, vy: 0, fijo: true };
  const vecinos = [...(g.vecinos.get(id) ?? [])];
  const colocado = vecinos.find((v) => v !== 'objetivo' && posiciones.has(v));
  const vecino = colocado ? posiciones.get(colocado) : undefined;
  const ang = ((semilla * 137.508) % 360) * (Math.PI / 180);
  if (vecino) return { x: vecino.x + Math.cos(ang) * 28, y: vecino.y + Math.sin(ang) * 28, vx: 0, vy: 0 };
  // Cuelga del tronco (o no tiene vecino colocado): nace en un anillo, en el
  // angulo dorado, para que las hojas no se apilen en el centro.
  if (vecinos.includes('objetivo')) {
    const r = n?.tipo === 'rama' || n?.tipo === 'area' ? 150 : 200;
    return { x: Math.cos(ang) * r, y: Math.sin(ang) * r, vx: 0, vy: 0 };
  }
  const r = n?.tipo === 'rama' || n?.tipo === 'area' ? 140 : 260;
  return { x: Math.cos(ang) * r, y: Math.sin(ang) * r, vx: 0, vy: 0 };
}

const VELOCIDAD_BASE = 2;
const VELOCIDAD_POR_ALFA = 28;

export function paso(g: Grafo, visibles: Set<string>, posiciones: Map<string, Posicion>, alfa: number): void {
  const ids = [...visibles].filter((id) => posiciones.has(id));
  // Repulsion.
  for (let i = 0; i < ids.length; i++) {
    const a = posiciones.get(ids[i]!)!;
    const pa = g.porId.get(ids[i]!)?.peso ?? 1;
    for (let j = i + 1; j < ids.length; j++) {
      const b = posiciones.get(ids[j]!)!;
      const pb = g.porId.get(ids[j]!)?.peso ?? 1;
      let dx = a.x - b.x;
      let dy = a.y - b.y;
      let d2 = dx * dx + dy * dy;
      if (d2 < 1) {
        dx = (Math.random() - 0.5) * 2;
        dy = (Math.random() - 0.5) * 2;
        d2 = 1;
      }
      // La repulsión se satura por debajo de 12 unidades: dos nodos que caen
      // casi encima no salen disparados (con muchos nodos, un solo par así
      // bastaba para que todo el árbol temblara).
      // Entre dos nodos con etiqueta (hipótesis, ramas, hechos) la repulsión es
      // mayor: son los que tienen texto que leer.
      const na0 = g.porId.get(ids[i]!);
      const nb0 = g.porId.get(ids[j]!);
      const conTexto = na0 && nb0 && na0.tipo !== 'fuente' && nb0.tipo !== 'fuente' && na0.tipo !== 'entidad' && nb0.tipo !== 'entidad' ? 1.8 : 1;
      const f = (3400 * conTexto * (pa + pb) * 0.5 * alfa) / Math.max(d2, 144);
      const d = Math.sqrt(d2);
      let fx = (dx / d) * f;
      let fy = (dy / d) * f;
      // Colision de etiquetas: si las cajas de texto (bajo cada circulo) se
      // solapan, se empujan aparte, mas en horizontal que en vertical.
      const na = g.porId.get(ids[i]!);
      const nb = g.porId.get(ids[j]!);
      if (na && nb && na.tipo !== 'fuente' && nb.tipo !== 'fuente') {
        const sx = (anchoEtiqueta(na) + anchoEtiqueta(nb)) / 2 + 8;
        const sy = 30;
        const ox = sx - Math.abs(dx);
        const oy = sy - Math.abs(dy);
        if (ox > 0 && oy > 0) {
          // El empuje por solape de etiquetas se acota: un solape de 150
          // unidades no puede convertirse en un salto de 50 por paso.
          const k = 0.35 * alfa;
          fx += Math.sign(dx || 1) * Math.min(ox, 24) * k;
          fy += Math.sign(dy || 1) * Math.min(oy, 24) * k * 0.6;
        }
      }
      if (!a.fijo) {
        a.vx += fx;
        a.vy += fy;
      }
      if (!b.fijo) {
        b.vx -= fx;
        b.vy -= fy;
      }
    }
  }
  // Resortes.
  for (const e of g.enlaces) {
    if (!visibles.has(e.de) || !visibles.has(e.a)) continue;
    const a = posiciones.get(e.de);
    const b = posiciones.get(e.a);
    if (!a || !b) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const d = Math.max(1, Math.sqrt(dx * dx + dy * dy));
    const f = ((d - LARGO[e.tipo]) / d) * 0.06 * alfa;
    if (!a.fijo) {
      a.vx += dx * f;
      a.vy += dy * f;
    }
    if (!b.fijo) {
      b.vx -= dx * f;
      b.vy -= dy * f;
    }
  }
  // Separación de etiquetas por posición (restricción, no fuerza): si dos
  // cajas de texto se solapan, ambos nodos se desplazan una fracción del
  // solape por el eje donde el solape es menor. Actúa aunque la energía sea
  // casi cero, así que las etiquetas acaban legibles también en reposo, y al
  // ser un desplazamiento acotado no puede disparar el árbol.
  separarEtiquetas(g, ids, posiciones, alfa);
  // Gravedad y movimiento.
  for (const id of ids) {
    const p = posiciones.get(id)!;
    if (p.fijo) continue;
    p.vx -= p.x * 0.004 * alfa;
    p.vy -= p.y * 0.004 * alfa;
    p.vx *= 0.82;
    p.vy *= 0.82;
    // Tope de velocidad proporcional a la energía: al arrastrar (alfa 0,35)
    // nadie se mueve más de unas 12 unidades por paso; al asentarse, menos.
    const tope = VELOCIDAD_BASE + VELOCIDAD_POR_ALFA * alfa;
    const v = Math.hypot(p.vx, p.vy);
    if (v > tope) {
      p.vx *= tope / v;
      p.vy *= tope / v;
    }
    p.x += p.vx;
    p.y += p.vy;
  }
}

/** Caja de la etiqueta de un nodo en unidades del lienzo: centrada en x, del
 *  borde superior del círculo al final de la segunda línea de texto. */
export function cajaEtiqueta(n: NodoArbol, p: { x: number; y: number }): { x0: number; x1: number; y0: number; y1: number } {
  // Margen generoso: la etiqueta real puede ser algo más ancha que la
  // estimación y dos textos a un píxel de distancia siguen leyéndose mal.
  const w = Math.min(anchoEtiqueta(n), 180) + 26;
  return { x0: p.x - w / 2, x1: p.x + w / 2, y0: p.y - 18, y1: p.y + 42 };
}

const FRACCION_SEPARACION = 0.3;

function separarEtiquetas(g: Grafo, ids: string[], posiciones: Map<string, Posicion>, alfa: number): void {
  // Con el árbol caliente se separa deprisa; casi en reposo, despacio, para
  // que un árbol denso sin sitio para todas las etiquetas no tiemble.
  const fraccion = FRACCION_SEPARACION * Math.min(1, Math.max(0.25, alfa / 0.12));
  const conTexto = ids.filter((id) => g.porId.get(id)?.tipo !== 'fuente');
  for (let i = 0; i < conTexto.length; i++) {
    const na = g.porId.get(conTexto[i]!)!;
    const a = posiciones.get(conTexto[i]!)!;
    for (let j = i + 1; j < conTexto.length; j++) {
      const nb = g.porId.get(conTexto[j]!)!;
      const b = posiciones.get(conTexto[j]!)!;
      const ca = cajaEtiqueta(na, a);
      const cb = cajaEtiqueta(nb, b);
      const ox = Math.min(ca.x1, cb.x1) - Math.max(ca.x0, cb.x0);
      const oy = Math.min(ca.y1, cb.y1) - Math.max(ca.y0, cb.y0);
      if (ox <= 0 || oy <= 0) continue;
      const libres = (a.fijo ? 0 : 1) + (b.fijo ? 0 : 1);
      if (libres === 0) continue;
      // Por el eje de menor solape; en horizontal las etiquetas son anchas,
      // así que ante la duda se separan en vertical.
      const horizontal = ox < oy * 0.6;
      const paso = (horizontal ? ox : oy) * fraccion;
      const dir = horizontal ? Math.sign(a.x - b.x || 1) : Math.sign(a.y - b.y || 1);
      const cada = paso / libres;
      if (!a.fijo) {
        if (horizontal) a.x += dir * cada;
        else a.y += dir * cada;
      }
      if (!b.fijo) {
        if (horizontal) b.x -= dir * cada;
        else b.y -= dir * cada;
      }
    }
  }
}

