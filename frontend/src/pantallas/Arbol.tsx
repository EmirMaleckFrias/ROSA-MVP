// El arbol de la investigacion: el grafo de lib/arbol.ts dibujado en SVG con
// una disposicion por fuerzas propia. Se explora: al abrir se ven el tronco,
// las ramas, las hipotesis vivas y los experimentos; pulsar un nodo
// despliega lo que lo sostiene (hechos, fuentes, entidades, rivales) y lo
// selecciona; pulsar dos veces abre su ficha. La busqueda ilumina todo lo
// que toca una palabra o un identificador (GFAP, HGNC:4235). El deslizador
// de iteraciones ensena como crecio el arbol. Se mueve con la rueda y
// arrastrando el fondo.

import { useEffect, useMemo, useRef, useState } from 'react';
import type { EstadoRosa, Investigacion } from '../datos/tipos';
import { AvisoMuestra, Chip, Vacio } from '../componentes/piezas';
import { alternar, buscar, construirArbol, NOMBRE_ENLACE, NOMBRE_TIPO, paso, posicionInicial, visiblesIniciales, type Grafo, type NodoArbol, type Posicion, type TipoEnlace, type TipoNodo } from '../lib/arbol';
import { useMovimientoReducido } from '../lib/movimiento';

const RADIO: Record<TipoNodo, number> = { objetivo: 22, rama: 13, area: 12, hipotesis: 11, hecho: 7, pregunta: 7, fuente: 5, entidad: 6, experimento: 12 };
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
};
const TRAZO: Record<TipoEnlace, { color: string; ancho: number; guion?: string }> = {
  rama: { color: 'var(--border-strong)', ancho: 1.6 },
  cita: { color: 'var(--text-3)', ancho: 0.8 },
  respalda: { color: 'var(--green)', ancho: 1 },
  entidad: { color: 'var(--blue)', ancho: 0.8, guion: '2 3' },
  causal: { color: '#ea580c', ancho: 1.4 },
  rival: { color: 'var(--red)', ancho: 1, guion: '4 4' },
  experimento: { color: '#0f766e', ancho: 1.8 },
};

function useSimulacion(grafo: Grafo, visibles: Set<string>, quieto: boolean) {
  const posiciones = useRef(new Map<string, Posicion>());
  const [, setTick] = useState(0);
  const alfa = useRef(1);
  const semilla = useRef(1);
  const marco = useRef<number | null>(null);
  // Un bucle de animacion que se enfria solo y se puede reavivar (al
  // arrastrar un nodo, al desplegar): como el "animate" del grafo de Obsidian.
  const arrancar = (energia = 1) => {
    alfa.current = Math.max(alfa.current, energia);
    if (marco.current !== null) return;
    const animar = () => {
      for (let k = 0; k < 2; k++) paso(grafo, visibles, posiciones.current, alfa.current);
      alfa.current = Math.max(0.02, alfa.current * 0.975);
      setTick((t) => t + 1);
      if (alfa.current > 0.03) marco.current = requestAnimationFrame(animar);
      else marco.current = null;
    };
    marco.current = requestAnimationFrame(animar);
  };
  const firmaAnterior = useRef('');
  useEffect(() => {
    // Los nodos nuevos nacen junto a un vecino colocado; los que se van, se olvidan.
    let cambio = false;
    for (const id of visibles) {
      if (!posiciones.current.has(id)) {
        posiciones.current.set(id, posicionInicial(grafo, posiciones.current, id, semilla.current++));
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
    // si el conjunto de nodos no cambio, no se vuelve a agitar el arbol.
    const firma = [...visibles].sort().join('|');
    const primera = firmaAnterior.current === '';
    firmaAnterior.current = firma;
    if (quieto) {
      if (cambio || primera) {
        for (let i = 0; i < 240; i++) paso(grafo, visibles, posiciones.current, Math.max(0.05, 1 - i / 240));
        setTick((t) => t + 1);
      }
      return;
    }
    if (cambio || primera) {
      alfa.current = 0;
      arrancar(primera ? 1 : 0.6);
    } else if (alfa.current > 0.03) {
      // La limpieza del efecto anterior cancelo el fotograma en marcha (otro
      // efecto reasigno los visibles al montar): se retoma donde estaba.
      arrancar(alfa.current);
    }
    return () => {
      if (marco.current !== null) cancelAnimationFrame(marco.current);
      marco.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [grafo, visibles, quieto]);
  return { posiciones: posiciones.current, reavivar: (energia = 0.4) => (quieto ? setTick((t) => t + 1) : arrancar(energia)) };
}

/** Cuanto se ve la etiqueta de un nodo segun el zoom y su importancia (el
 *  "text fade threshold" del grafo de Obsidian): el tronco siempre; ramas,
 *  hipotesis y experimentos desde un zoom normal; lo pequeno solo al acercar,
 *  o si esta iluminado o seleccionado. */
function opacidadEtiqueta(n: NodoArbol, k: number, vivo: boolean, sel: boolean): number {
  if (sel) return 1;
  const umbral = n.tipo === 'objetivo' ? 0 : n.tipo === 'rama' || n.tipo === 'area' || n.tipo === 'hipotesis' || n.tipo === 'experimento' ? 0.75 : 1.5;
  const base = Math.max(0, Math.min(1, (k - umbral) / 0.35 + 1));
  return vivo ? Math.max(base, n.tipo === 'fuente' || n.tipo === 'entidad' || n.tipo === 'hecho' || n.tipo === 'pregunta' ? 0.9 : 1) : base;
}

/** Parte una etiqueta en hasta dos lineas de unos 22 caracteres. */
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
  const [visibles, setVisibles] = useState<Set<string>>(() => visiblesIniciales(grafo, hip));
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [texto, setTexto] = useState('');
  const [hasta, setHasta] = useState<number>(grafo.iteracionMax);
  const [vista, setVista] = useState({ x: 0, y: 0, k: 1 });
  const [hover, setHover] = useState<string | null>(null);
  const arrastre = useRef<{ x: number; y: number; vx: number; vy: number; ux?: number; uy?: number } | null>(null);
  const arrastreNodo = useRef<{ id: string; x0: number; y0: number; movido: boolean } | null>(null);
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

  // Si el estado trae nodos nuevos (una hipotesis nueva), entran solos al arbol.
  useEffect(() => {
    setVisibles((v) => {
      const base = visiblesIniciales(grafo, hip);
      const nuevo = new Set(v);
      for (const id of base) nuevo.add(id);
      for (const id of v) if (!grafo.porId.has(id)) nuevo.delete(id);
      return nuevo;
    });
    setHasta((h) => Math.max(h, grafo.iteracionMax));
  }, [grafo, hip]);

  const iluminados = useMemo(() => buscar(grafo, texto), [grafo, texto]);
  const enTiempo = useMemo(() => new Set([...visibles].filter((id) => (grafo.porId.get(id)?.iteracion ?? 0) <= hasta)), [visibles, hasta, grafo]);
  const { posiciones, reavivar } = useSimulacion(grafo, enTiempo, reducido);
  // Balanceo en reposo: un vaiven lento y distinto por nodo (solo al dibujar,
  // no en la fisica) para que el arbol nunca parezca una foto. Con movimiento
  // reducido no hay balanceo.
  const [reloj, setReloj] = useState(0);
  useEffect(() => {
    if (reducido) return;
    let id = 0;
    const paso_ = (t: number) => {
      setReloj(t / 1000);
      id = requestAnimationFrame(paso_);
    };
    id = requestAnimationFrame(paso_);
    return () => cancelAnimationFrame(id);
  }, [reducido]);
  const vaiven = (id: string, peso: number) => {
    if (reducido) return { x: 0, y: 0 };
    let h = 0;
    for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
    const fase = (h % 628) / 100;
    const amp = 1.6 + Math.min(2.5, peso) * 0.5;
    return { x: Math.sin(reloj * 0.7 + fase) * amp, y: Math.cos(reloj * 0.55 + fase * 1.3) * amp * 0.8 };
  };
  const nodoSel = seleccion ? grafo.porId.get(seleccion) ?? null : null;
  // Resaltar al pasar el raton (como Obsidian): el nodo y sus vecinos vivos, el resto atenuado.
  const foco = hover ?? seleccion;
  const vecinosFoco = useMemo(() => (foco ? new Set(grafo.vecinos.get(foco) ?? []) : null), [grafo, foco]);
  const atenuar = iluminados.size > 0 || foco !== null;
  const destacado = (id: string) => (iluminados.size > 0 ? iluminados.has(id) : foco === null || foco === id || (vecinosFoco?.has(id) ?? false));

  // La rueda va con un oyente nativo no pasivo: React registra onWheel como
  // pasivo y preventDefault no haria nada (la pagina haria scroll).
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const alRueda = (e: WheelEvent) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      const p = enLienzo(e.clientX, e.clientY);
      setVista((v) => {
        const k = Math.max(0.25, Math.min(4, v.k * factor));
        // Zoom alrededor del cursor: el punto bajo el raton no se mueve.
        return { k, x: p.x - ((p.x - v.x) * k) / v.k, y: p.y - ((p.y - v.y) * k) / v.k };
      });
    };
    svg.addEventListener('wheel', alRueda, { passive: false });
    return () => svg.removeEventListener('wheel', alRueda);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const empezarArrastre = (e: React.PointerEvent) => {
    const nodo = (e.target as Element).closest('.grafo-nodo') as SVGGElement | null;
    if (nodo) {
      // Sin capturar el puntero: si el SVG lo captura, el navegador manda el
      // clic al SVG y la esfera nunca recibe onClick (no se abria el panel).
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
    // Al agarrar el arbol, las esferas no van pegadas al fondo: reciben un
    // impulso contrario, se columpian y vuelven a su sitio tiradas por los
    // enlaces (el tronco esta fijo). Es la sacudida de un arbol de verdad.
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
    if (arrastreNodo.current) {
      const p = posiciones.get(arrastreNodo.current.id);
      if (p && arrastreNodo.current.id !== 'objetivo') p.fijo = false;
      // Un arrastre no es un clic: si se movio, no se despliega ni se selecciona.
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
    setSeleccion(n.id);
    setVisibles((v) => alternar(grafo, v, n.id));
  };

  if (hip.length === 0 && estado.hechos.filter((h) => h.investigacionId === inv.id).length === 0) {
    return (
      <div className="contenido">
        <AvisoMuestra conexion={estado.conexion} />
        <Vacio titulo="El árbol todavía no tiene ramas" pasos={['El tronco es el objetivo; ya esta.', 'Cuando Rosa busque literatura y verifique afirmaciones, apareceran los hechos y las fuentes.', 'Cada hipótesis será una hoja en la rama de su cluster de mecanismo, unida a lo que la sostiene.', 'El experimento que llegue al laboratorio será el fruto.']}>
          Aqui se ve toda la investigacion conectada: que sostiene a que, que comparte una entidad con que, y que rivaliza con que.
        </Vacio>
      </div>
    );
  }

  const enlacesVisibles = grafo.enlaces.filter((e) => enTiempo.has(e.de) && enTiempo.has(e.a) && posiciones.has(e.de) && posiciones.has(e.a));
  const nodosVisibles = [...enTiempo].map((id) => grafo.porId.get(id)).filter((n): n is NodoArbol => Boolean(n) && posiciones.has(n!.id));
  const cuentas = nodosVisibles.reduce<Partial<Record<TipoNodo, number>>>((acc, n) => ({ ...acc, [n.tipo]: (acc[n.tipo] ?? 0) + 1 }), {});

  return (
    <div className="contenido contenido-ancho">
      <AvisoMuestra conexion={estado.conexion} />
      <div className="pantalla-cabecera" style={{ marginTop: 16 }}>
        <div>
          <h2>Árbol de la investigación</h2>
          <p>El objetivo es el tronco; las ramas, los clusters con varias hipótesis; las hojas, las hipótesis; alrededor, lo que las sostiene. Pasa el ratón por un nodo para ver sus conexiones; pulsa para desplegar lo que toca; dos veces para abrir su ficha; arrastra un nodo para moverlo (los demás lo siguen). Las etiquetas pequeñas aparecen al acercar con la rueda. Escribe una palabra o un identificador (GFAP, HGNC:4235) para iluminar todo lo que lo nombra.</p>
        </div>
        <div className="acciones">
          <input className="entrada entrada-s" style={{ width: 220 }} value={texto} placeholder="Buscar en el árbol" onChange={(e) => setTexto(e.target.value)} aria-label="Buscar en el árbol" />
          <button type="button" className="btn btn-s" onClick={() => { setVisibles(visiblesIniciales(grafo, hip)); setSeleccion(null); setVista({ x: 0, y: 0, k: 1 }); }}>
            Plegar todo
          </button>
          <button type="button" className="btn btn-s" onClick={() => { setVisibles(new Set(grafo.nodos.map((n) => n.id))); }} title="Despliega hasta las fuentes: puede ser mucho">
            Desplegar todo
          </button>
        </div>
      </div>

      <div className="grafo-marco">
        <svg ref={svgRef} className="grafo" viewBox={`${-ancho / 2} ${-alto / 2} ${ancho} ${alto}`} role="img" aria-label={`Árbol de ${inv.titulo}: ${nodosVisibles.length} nodos y ${enlacesVisibles.length} enlaces visibles`} onPointerDown={empezarArrastre} onPointerMove={mover} onPointerUp={soltar} onPointerCancel={soltar}>
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
              const filas = lineas(n.etiqueta);
              const v = vaiven(n.id, n.peso);
              return (
                <g key={n.id} data-id={n.id} className={`grafo-nodo grafo-${n.tipo} ${vivo ? '' : 'grafo-atenuado'} ${sel ? 'grafo-seleccionado' : ''} ${hover === n.id ? 'grafo-hover' : ''}`} transform={`translate(${p.x + v.x} ${p.y + v.y})`} onClick={(e) => pulsar(n, e.detail)} onDoubleClick={() => { if (n.href) window.location.hash = n.href; }} onPointerEnter={() => setHover(n.id)} onPointerLeave={() => setHover((h) => (h === n.id ? null : h))} role="button" tabIndex={0} aria-label={`${NOMBRE_TIPO[n.tipo]}: ${n.etiqueta}`} onKeyDown={(e) => { if (e.key === 'Enter') pulsar(n, 1); }}>
                  {n.tipo === 'objetivo' && <circle r={r + 6} fill="none" stroke="var(--accent)" strokeOpacity={0.25} strokeWidth={6} />}
                  <circle r={r} fill={COLOR[n.tipo]} stroke={n.alerta ? 'var(--red)' : n.tipo === 'rama' || n.tipo === 'area' ? 'var(--accent)' : 'var(--surface)'} strokeWidth={n.alerta ? 2 : 1.5} strokeDasharray={n.estado === 'descartada' ? '3 2' : undefined} />
                  {n.tipo === 'experimento' && <path d="M-4 -5 h8 v3 l3 6 a2 2 0 0 1 -2 3 h-10 a2 2 0 0 1 -2 -3 l3 -6 z" fill="none" stroke="#fff" strokeWidth={1.2} transform="scale(0.9)" />}
                  {opEt > 0.02 && (
                    <text y={r + 11} textAnchor="middle" className="grafo-etiqueta" opacity={opEt} style={{ fontSize: n.tipo === 'objetivo' ? 13 : n.tipo === 'rama' || n.tipo === 'hipotesis' || n.tipo === 'experimento' ? 10.5 : 9 }}>
                      {filas.map((f, i) => (
                        <tspan key={i} x={0} dy={i === 0 ? 0 : 12}>
                          {f}
                        </tspan>
                      ))}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
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
                          <span className="grafo-punto" style={{ background: COLOR[otro.tipo] }} aria-hidden="true" /> {otro.etiqueta.length > 60 ? `${otro.etiqueta.slice(0, 58)}...` : otro.etiqueta}
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
              <ul className="grafo-leyenda">
                {(Object.keys(NOMBRE_TIPO) as TipoNodo[]).map((t) => (
                  <li key={t}>
                    <span className="grafo-punto" style={{ background: COLOR[t] }} aria-hidden="true" /> {NOMBRE_TIPO[t]} <span className="meta">{cuentas[t] ?? 0}</span>
                  </li>
                ))}
              </ul>
              <h4>Enlaces</h4>
              <ul className="grafo-leyenda">
                {(Object.keys(NOMBRE_ENLACE) as TipoEnlace[]).map((t) => (
                  <li key={t}>
                    <span className="grafo-linea" style={{ borderColor: TRAZO[t].color, borderStyle: TRAZO[t].guion ? 'dashed' : 'solid' }} aria-hidden="true" /> {NOMBRE_ENLACE[t]}
                  </li>
                ))}
              </ul>
              <p className="meta">Borde rojo: descartada, bloqueada o con marca editorial. Punteada: descartada.</p>
            </>
          )}
        </aside>
      </div>
      <div className="grafo-tiempo">
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
