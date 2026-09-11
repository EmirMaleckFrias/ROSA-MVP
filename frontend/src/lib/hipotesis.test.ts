import { describe, expect, it } from 'vitest';
import { HIPOTESIS } from '../datos/muestra';
import type { Afirmacion, HallazgoRevisor, Hipotesis } from '../datos/tipos';
import {
  fidelidad,
  hallazgosVisibles,
  motivoNoAceptable,
  ordenarCola,
  pendientesDeRevision,
  ranking,
  resumirVerificacion,
  variacionElo,
} from './hipotesis';

const af = (veredicto: Afirmacion['veredicto'], entidadDistinta = false): Afirmacion => ({
  texto: 'x',
  cita: '[f, pag. 1]',
  veredicto,
  motivo: '',
  entidadDistinta,
  tipo: 'literatura',
  trayectoria: null,
});

describe('ordenarCola', () => {
  it('pone lo pendiente arriba y ordena por Elo dentro de cada estado', () => {
    const ids = ordenarCola(HIPOTESIS).map((h) => h.id);
    expect(ids).toEqual(['hip-2', 'hip-1', 'hip-3', 'hip-4', 'hip-5']);
  });
  it('no muta la entrada', () => {
    const copia = [...HIPOTESIS];
    ordenarCola(HIPOTESIS);
    expect(HIPOTESIS).toEqual(copia);
  });
  it('cuenta las pendientes', () => {
    expect(pendientesDeRevision(HIPOTESIS)).toBe(3);
  });
});

describe('ranking', () => {
  it('ordena por Elo y manda las descartadas al final aunque tengan Elo alto', () => {
    const descartadaAlta: Hipotesis = { ...HIPOTESIS[0]!, id: 'x', estado: 'descartada', elo: 9_000 };
    const ids = ranking([...HIPOTESIS, descartadaAlta]).map((h) => h.id);
    expect(ids.slice(0, 4)).toEqual(['hip-2', 'hip-1', 'hip-4', 'hip-3']);
    // Dentro de las descartadas tambien manda el Elo.
    expect(ids.slice(-2)).toEqual(['x', 'hip-5']);
  });
  it('calcula la variacion desde el primer punto', () => {
    expect(variacionElo(HIPOTESIS[0]!)).toBe(142);
    expect(variacionElo({ elo: 1500, historialElo: [] })).toBe(0);
  });
});

describe('resumirVerificacion', () => {
  it('con todo sostenido da una linea sobria', () => {
    const r = resumirVerificacion([af('sostenida'), af('sostenida')]);
    expect(r).toMatchObject({ tono: 'ok', bloqueantes: 0, frase: '2 de 2 afirmaciones respaldadas por su fuente' });
  });
  it('resume el fallo, no el acierto, y separa la entidad distinta', () => {
    const r = resumirVerificacion([af('sostenida'), af('no_sostenida'), af('no_sostenida', true), af('parcial')]);
    expect(r.frase).toBe('1 dato de otra entidad · 1 no sostenida · 1 parcial');
    expect(r.tono).toBe('mal');
    expect(r.bloqueantes).toBe(2);
  });
  it('sin_verificar es aviso, nunca aprobado', () => {
    const r = resumirVerificacion([af('sostenida'), af('sin_verificar')]);
    expect(r.tono).toBe('aviso');
    expect(r.frase).toBe('1 sin comprobar');
  });
  it('lista vacia', () => {
    expect(resumirVerificacion([]).tono).toBe('vacio');
  });
});

describe('fidelidad', () => {
  it('solo cuenta lo juzgado por el juez', () => {
    expect(fidelidad([af('sostenida'), af('no_sostenida'), af('sin_cita'), af('sin_verificar')])).toBe(0.5);
    expect(fidelidad([af('sin_cita')])).toBeNull();
    expect(fidelidad([])).toBeNull();
  });
});

describe('hallazgosVisibles', () => {
  const h = (id: string, estado: HallazgoRevisor['estado']): HallazgoRevisor => ({
    id,
    tipo: 'cita_no_sostiene',
    resumen: id,
    razonamiento: '',
    estado,
    respuestaDeRosa: null,
  });
  it('ensena tres, los abiertos primero, y cuenta los ocultos', () => {
    const lista = [h('a', 'atendido'), h('b', 'abierto'), h('c', 'no_aplica'), h('d', 'abierto'), h('e', 'atendido')];
    const r = hallazgosVisibles(lista, false);
    expect(r.visibles.map((x) => x.id)).toEqual(['b', 'd', 'a']);
    expect(r.ocultos).toBe(2);
  });
  it('con tres o menos no oculta nada', () => {
    expect(hallazgosVisibles([h('a', 'abierto')], false).ocultos).toBe(0);
  });
  it('mostrar todo devuelve todos', () => {
    const lista = [h('a', 'atendido'), h('b', 'abierto'), h('c', 'no_aplica'), h('d', 'abierto')];
    expect(hallazgosVisibles(lista, true).visibles).toHaveLength(4);
  });
});

describe('motivoNoAceptable', () => {
  it('bloquea por afirmaciones no sostenidas', () => {
    expect(motivoNoAceptable(HIPOTESIS[1]!)).toMatch(/2 afirmaciones bloquean/);
  });
  it('bloquea por hallazgos abiertos aunque las afirmaciones esten bien', () => {
    const h = { ...HIPOTESIS[0]!, hallazgos: [{ id: 'z', tipo: 'conclusion_no_sigue' as const, resumen: '', razonamiento: '', estado: 'abierto' as const, respuestaDeRosa: null }] };
    expect(motivoNoAceptable(h)).toMatch(/1 hallazgo del revisor sigue abierto/);
  });
  it('exige biomarcador o cohorte', () => {
    const h = { ...HIPOTESIS[0]!, comprobacion: { biomarcador: '', cohorte: '', diseno: 'x' } };
    expect(motivoNoAceptable(h)).toMatch(/biomarcador/);
  });
  it('una hipotesis limpia se puede aceptar', () => {
    expect(motivoNoAceptable(HIPOTESIS[0]!)).toBeNull();
  });
});
