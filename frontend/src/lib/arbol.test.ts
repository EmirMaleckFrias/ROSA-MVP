import { describe, expect, it } from 'vitest';
import { estadoDeMuestra } from '../datos/muestra';
import { alternar, buscar, construirArbol, incorporarNovedades, paso, posicionInicial, visiblesIniciales, type Posicion } from './arbol';

describe('el arbol de la investigacion', () => {
  const e = estadoDeMuestra();
  const inv = e.investigaciones[0]!;
  const g = construirArbol(e, inv);
  const hip = e.hipotesis.filter((h) => h.investigacionId === inv.id);

  it('muestra cualquier tipo de nodo nuevo con sus conexiones', () => {
    for (const nodo of g.nodos) {
      const anteriores = new Set(g.nodos.filter((n) => n.id !== nodo.id).map((n) => n.id));
      const visibles = incorporarNovedades(g, anteriores, new Set(['objetivo']));
      expect(visibles.has(nodo.id)).toBe(true);
      for (const vecino of g.vecinos.get(nodo.id) ?? []) expect(visibles.has(vecino)).toBe(true);
    }
  });

  it('no despliega nodos plegados al recibir el mismo grafo y elimina los borrados', () => {
    const anteriores = new Set(g.nodos.map((n) => n.id));
    expect(incorporarNovedades(g, anteriores, new Set(['objetivo', 'borrado']))).toEqual(new Set(['objetivo']));
  });

  it('tiene tronco, ramas y hojas, y ningun enlace suelto', () => {
    expect(g.porId.get('objetivo')?.tipo).toBe('objetivo');
    const clustersConVarias = new Set(hip.map((h) => h.cluster || 'Sin cluster').filter((c, _, arr) => arr.filter((x) => x === c).length >= 2));
    expect(g.nodos.filter((n) => n.tipo === 'rama').length).toBe(clustersConVarias.size);
    expect(g.nodos.filter((n) => n.tipo === 'hipotesis').length).toBe(hip.length);
    for (const en of g.enlaces) {
      expect(g.porId.has(en.de), en.de).toBe(true);
      expect(g.porId.has(en.a), en.a).toBe(true);
    }
    // Cada hipotesis cuelga de su rama; cada fuente citada existe una sola vez.
    for (const h of hip) expect(g.enlaces.some((en) => en.tipo === 'rama' && en.a === h.id && (en.de === 'objetivo' || en.de.startsWith('rama-')))).toBe(true);
    // Una rama existe solo si agrupa dos o mas hipotesis.
    for (const r of g.nodos.filter((n) => n.tipo === 'rama')) expect(g.enlaces.filter((en) => en.de === r.id && en.tipo === 'rama').length).toBeGreaterThanOrEqual(2);
    const fuentes = g.nodos.filter((n) => n.tipo === 'fuente').map((n) => n.id);
    expect(new Set(fuentes).size).toBe(fuentes.length);
  });

  it('al abrir se ven pocas cosas y al pulsar se despliegan y se pliegan', () => {
    const v0 = visiblesIniciales(g, hip);
    expect(v0.has('objetivo')).toBe(true);
    expect([...v0].every((id) => ['objetivo', 'rama', 'area', 'hipotesis', 'experimento'].includes(g.porId.get(id)!.tipo))).toBe(true);
    const h = hip[0]!;
    const v1 = alternar(g, v0, h.id);
    expect(v1.size).toBeGreaterThan(v0.size);
    // Plegar quita lo que solo se sostenia por esta hipotesis; lo compartido con
    // otras visibles se queda (es la regla, no un fallo).
    const v2 = alternar(g, v1, h.id);
    expect(v2.size).toBeLessThanOrEqual(v1.size);
    for (const id of g.vecinos.get(h.id) ?? []) {
      const n = g.porId.get(id)!;
      if (['objetivo', 'rama', 'area', 'hipotesis'].includes(n.tipo)) continue;
      const otros = [...(g.vecinos.get(id) ?? [])].filter((o) => o !== h.id && v2.has(o));
      expect(v2.has(id), id).toBe(otros.length > 0);
    }
  });

  it('busca por etiqueta y por identificador o alias', () => {
    const conEntidad = g.nodos.find((n) => n.tipo === 'entidad');
    if (conEntidad) expect(buscar(g, conEntidad.alias![0]!).has(conEntidad.id)).toBe(true);
    expect(buscar(g, hip[0]!.titulo.slice(0, 12)).has(hip[0]!.id)).toBe(true);
    expect(buscar(g, 'x').size).toBe(0);
  });

  it('la disposicion por fuerzas separa los nodos y deja el tronco fijo', () => {
    const visibles = visiblesIniciales(g, hip);
    const pos = new Map<string, Posicion>();
    let s = 1;
    for (const id of visibles) pos.set(id, posicionInicial(g, pos, id, s++));
    for (let i = 0; i < 200; i++) paso(g, visibles, pos, Math.max(0.05, 1 - i / 200));
    expect(pos.get('objetivo')).toMatchObject({ x: 0, y: 0 });
    const ids = [...visibles];
    let minimo = Infinity;
    for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
      const a = pos.get(ids[i]!)!;
      const b = pos.get(ids[j]!)!;
      minimo = Math.min(minimo, Math.hypot(a.x - b.x, a.y - b.y));
    }
    expect(minimo).toBeGreaterThan(8);
    for (const p of pos.values()) expect(Number.isFinite(p.x) && Number.isFinite(p.y)).toBe(true);
  });
});
