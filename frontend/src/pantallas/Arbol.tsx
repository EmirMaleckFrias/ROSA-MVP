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
  useEffect(() => {
    // Los nodos nuevos nacen junto a un vecino colocado; los que se van, se olvidan.
    for (const id of visibles) if (!posiciones.current.has(id)) posiciones.current.set(id, posicionInicial(grafo, posiciones.current, id, semilla.current++));
    for (const id of [...posiciones.current.keys()]) if (!visibles.has(id)) posiciones.current.delete(id);
    alfa.current = 1;
    if (quieto) {
      for (let i = 0; i < 240; i++) paso(grafo, visibles, posiciones.current, Math.max(0.05, 1 - i / 240));
      setTick((t) => t + 1);
      return;
    }
    let vivo = true;
    let marco = 0;
    const animar = () => {
      if (!vivo) return;
      for (let k = 0; k < 2; k++) paso(grafo, visibles, posiciones.current, alfa.current);
      alfa.current = Math.max(0.02, alfa.current * 0.975);
      setTick((t) => t + 1);
      marco++;
      if (alfa.current > 0.03 && marco < 400) requestAnimationFrame(animar);
    };
    const id = requestAnimationFrame(animar);
    return () => {
      vivo = false;
      cancelAnimationFrame(id);
    };
  }, [grafo, visibles, quieto]);
  return posiciones.current;
}

export function Arbol({ inv, estado }: { inv: Investigacion; estado: EstadoRosa }) {
  const hip = useMemo(() => estado.hipotesis.filter((h) => h.investigacionId === inv.id), [estado.hipotesis, inv.id]);
  const grafo = useMemo(() => construirArbol(estado, inv), [estado, inv]);
  const [visibles, setVisibles] = useState<Set<string>>(() => visiblesIniciales(grafo, hip));
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [texto, setTexto] = useState('');
  const [hasta, setHasta] = useState<number>(grafo.iteracionMax);
  const [vista, setVista] = useState({ x: 0, y: 0, k: 1 });
  const arrastre = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);
  const reducido = useMovimientoReducido();
  const svgRef = useRef<SVGSVGElement>(null);
  const ancho = 900;
  const alto = 560;

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
  const posiciones = useSimulacion(grafo, enTiempo, reducido);
  const nodoSel = seleccion ? grafo.porId.get(seleccion) ?? null : null;
  const vecinosSel = useMemo(() => (seleccion ? new Set(grafo.vecinos.get(seleccion) ?? []) : null), [grafo, seleccion]);
  const atenuar = iluminados.size > 0 || seleccion !== null;
  const destacado = (id: string) => (iluminados.size > 0 ? iluminados.has(id) : seleccion === null || seleccion === id || (vecinosSel?.has(id) ?? false));

  const alRueda = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
    setVista((v) => ({ ...v, k: Math.max(0.3, Math.min(3, v.k * factor)) }));
  };
  const empezarArrastre = (e: React.PointerEvent) => {
    if ((e.target as Element).closest('.arbol-nodo')) return;
    arrastre.current = { x: e.clientX, y: e.clientY, vx: vista.x, vy: vista.y };
  };
  const mover = (e: React.PointerEvent) => {
    if (!arrastre.current) return;
    const a = arrastre.current;
    setVista((v) => ({ ...v, x: a.vx + (e.clientX - a.x), y: a.vy + (e.clientY - a.y) }));
  };
  const soltar = () => {
    arrastre.current = null;
  };

  if (hip.length === 0 && estado.hechos.filter((h) => h.investigacionId === inv.id).length === 0) {
    return (
      <div className="contenido">
        <AvisoMuestra conexion={estado.conexion} />
        <Vacio titulo="El arbol todavia no tiene ramas" pasos={['El tronco es el objetivo; ya esta.', 'Cuando Rosa busque literatura y verifique afirmaciones, apareceran los hechos y las fuentes.', 'Cada hipotesis sera una hoja en la rama de su cluster de mecanismo, unida a lo que la sostiene.', 'El experimento que llegue al laboratorio sera el fruto.']}>
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
          <h2>Arbol de la investigacion</h2>
          <p>El objetivo es el tronco; las ramas son los clusters de mecanismo; las hojas, las hipotesis; alrededor, lo que las sostiene. Pulsa un nodo para desplegar lo que toca; dos veces para abrir su ficha. Escribe una palabra o un identificador (GFAP, HGNC:4235) para iluminar todo lo que lo nombra.</p>
        </div>
        <div className="acciones">
          <input className="entrada entrada-s" style={{ width: 220 }} value={texto} placeholder="Buscar en el arbol" onChange={(e) => setTexto(e.target.value)} aria-label="Buscar en el arbol" />
          <button type="button" className="btn btn-s" onClick={() => { setVisibles(visiblesIniciales(grafo, hip)); setSeleccion(null); setVista({ x: 0, y: 0, k: 1 }); }}>
            Plegar todo
          </button>
          <button type="button" className="btn btn-s" onClick={() => { setVisibles(new Set(grafo.nodos.map((n) => n.id))); }} title="Despliega hasta las fuentes: puede ser mucho">
            Desplegar todo
          </button>
        </div>
      </div>

      <div className="arbol-marco">
        <svg ref={svgRef} className="arbol" viewBox={`${-ancho / 2} ${-alto / 2} ${ancho} ${alto}`} role="img" aria-label={`Arbol de ${inv.titulo}: ${nodosVisibles.length} nodos y ${enlacesVisibles.length} enlaces visibles`} onWheel={alRueda} onPointerDown={empezarArrastre} onPointerMove={mover} onPointerUp={soltar} onPointerLeave={soltar}>
          <g transform={`translate(${vista.x} ${vista.y}) scale(${vista.k})`}>
            {enlacesVisibles.map((e) => {
              const a = posiciones.get(e.de)!;
              const b = posiciones.get(e.a)!;
              const t = TRAZO[e.tipo];
              const vivo = !atenuar || (destacado(e.de) && destacado(e.a));
              return <line key={`${e.de}|${e.a}|${e.tipo}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={t.color} strokeWidth={t.ancho} strokeDasharray={t.guion} opacity={vivo ? 0.75 : 0.12} className="arbol-enlace" />;
            })}
            {nodosVisibles.map((n) => {
              const p = posiciones.get(n.id)!;
              const r = RADIO[n.tipo] * (0.8 + Math.min(1.4, n.peso) * 0.3);
              const vivo = destacado(n.id);
              const sel = seleccion === n.id;
              return (
                <g key={n.id} className={`arbol-nodo arbol-${n.tipo} ${vivo ? '' : 'arbol-atenuado'} ${sel ? 'arbol-seleccionado' : ''}`} transform={`translate(${p.x} ${p.y})`} onClick={() => { setSeleccion(n.id); setVisibles((v) => alternar(grafo, v, n.id)); }} onDoubleClick={() => { if (n.href) window.location.hash = n.href; }} role="button" tabIndex={0} aria-label={`${NOMBRE_TIPO[n.tipo]}: ${n.etiqueta}`} onKeyDown={(e) => { if (e.key === 'Enter') { setSeleccion(n.id); setVisibles((v) => alternar(grafo, v, n.id)); } }}>
                  {n.tipo === 'objetivo' && <circle r={r + 6} fill="none" stroke="var(--accent)" strokeOpacity={0.25} strokeWidth={6} />}
                  <circle r={r} fill={COLOR[n.tipo]} stroke={n.alerta ? 'var(--red)' : n.tipo === 'rama' || n.tipo === 'area' ? 'var(--accent)' : 'var(--surface)'} strokeWidth={n.alerta ? 2 : 1.5} strokeDasharray={n.estado === 'descartada' ? '3 2' : undefined} />
                  {n.tipo === 'experimento' && <path d="M-4 -5 h8 v3 l3 6 a2 2 0 0 1 -2 3 h-10 a2 2 0 0 1 -2 -3 l3 -6 z" fill="none" stroke="#fff" strokeWidth={1.2} transform="scale(0.9)" />}
                  {(n.tipo !== 'fuente' && n.tipo !== 'entidad') || vivo ? (
                    <text y={r + 12} textAnchor="middle" className="arbol-etiqueta" style={{ fontSize: n.tipo === 'objetivo' ? 13 : n.tipo === 'rama' || n.tipo === 'hipotesis' || n.tipo === 'experimento' ? 11 : 9.5 }}>
                      {n.etiqueta.length > 34 ? `${n.etiqueta.slice(0, 32)}...` : n.etiqueta}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </g>
        </svg>
        <aside className="arbol-panel">
          {nodoSel ? (
            <>
              <Chip tono="acento">{NOMBRE_TIPO[nodoSel.tipo]}</Chip>
              <h3>{nodoSel.etiqueta}</h3>
              {nodoSel.sub && <p className="meta">{nodoSel.sub}</p>}
              {nodoSel.alerta && <p className="tono-mal" style={{ fontSize: 13 }}>{nodoSel.alerta}</p>}
              {nodoSel.alias && nodoSel.alias.length > 1 && <p className="meta">Alias: {nodoSel.alias.slice(0, 8).join(', ')}</p>}
              <p className="meta">Aparece desde la iteracion {nodoSel.iteracion || 1}.</p>
              <h4>Conectado con</h4>
              <ul className="arbol-vecinos">
                {grafo.enlaces
                  .filter((e) => e.de === nodoSel.id || e.a === nodoSel.id)
                  .slice(0, 40)
                  .map((e) => {
                    const otro = grafo.porId.get(e.de === nodoSel.id ? e.a : e.de);
                    if (!otro) return null;
                    return (
                      <li key={`${e.de}|${e.a}|${e.tipo}`}>
                        <button type="button" className="enlace" onClick={() => { setSeleccion(otro.id); setVisibles((v) => new Set([...v, otro.id])); }}>
                          <span className="arbol-punto" style={{ background: COLOR[otro.tipo] }} aria-hidden="true" /> {otro.etiqueta.length > 60 ? `${otro.etiqueta.slice(0, 58)}...` : otro.etiqueta}
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
              <ul className="arbol-leyenda">
                {(Object.keys(NOMBRE_TIPO) as TipoNodo[]).map((t) => (
                  <li key={t}>
                    <span className="arbol-punto" style={{ background: COLOR[t] }} aria-hidden="true" /> {NOMBRE_TIPO[t]} <span className="meta">{cuentas[t] ?? 0}</span>
                  </li>
                ))}
              </ul>
              <h4>Enlaces</h4>
              <ul className="arbol-leyenda">
                {(Object.keys(NOMBRE_ENLACE) as TipoEnlace[]).map((t) => (
                  <li key={t}>
                    <span className="arbol-linea" style={{ borderColor: TRAZO[t].color, borderStyle: TRAZO[t].guion ? 'dashed' : 'solid' }} aria-hidden="true" /> {NOMBRE_ENLACE[t]}
                  </li>
                ))}
              </ul>
              <p className="meta">Borde rojo: descartada, bloqueada o con marca editorial. Punteada: descartada.</p>
            </>
          )}
        </aside>
      </div>
      <div className="arbol-tiempo">
        <label htmlFor="arbol-iteracion">
          Como crecio: hasta la iteracion <strong>{hasta}</strong> de {grafo.iteracionMax}
        </label>
        <input id="arbol-iteracion" type="range" min={1} max={Math.max(1, grafo.iteracionMax)} value={Math.min(hasta, Math.max(1, grafo.iteracionMax))} onChange={(e) => setHasta(Number(e.target.value))} />
        <span className="meta">
          {nodosVisibles.length} nodos · {enlacesVisibles.length} enlaces
        </span>
      </div>
    </div>
  );
}
