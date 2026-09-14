// Funciones del espejo, todas internas: solo se invocan con la clave de
// despliegue (el servidor de Rosa). Una funcion publica de Convex la podria
// llamar cualquiera que conozca la URL del deployment, sin clave; por eso
// ninguna lo es. Cuando la interfaz lea del espejo, lo hara con auth propia.
import { internalMutation, internalQuery } from './_generated/server';
import { v } from 'convex/values';

const LIMITE_LOTE = 400;

export const sincronizar = internalMutation({
  args: {
    version: v.number(),
    origen: v.string(),
    cambios: v.array(
      v.object({
        coleccion: v.string(),
        id: v.string(),
        investigacionId: v.union(v.string(), v.null()),
        hash: v.string(),
        bytes: v.number(),
        truncado: v.boolean(),
        datos: v.any(),
      }),
    ),
    borrados: v.array(v.object({ coleccion: v.string(), id: v.string() })),
    ultimoLote: v.boolean(),
  },
  handler: async (ctx, args) => {
    if (args.cambios.length > LIMITE_LOTE) throw new Error(`Lote de ${args.cambios.length} entidades; el maximo es ${LIMITE_LOTE}`);
    let escritas = 0;
    for (const c of args.cambios) {
      const existente = await ctx.db
        .query('entidades')
        .withIndex('por_coleccion_id', (q) => q.eq('coleccion', c.coleccion).eq('id', c.id))
        .unique();
      if (existente) {
        if (existente.hash !== c.hash) {
          await ctx.db.patch(existente._id, { ...c, version: args.version });
          escritas += 1;
        }
      } else {
        await ctx.db.insert('entidades', { ...c, version: args.version });
        escritas += 1;
      }
    }
    for (const b of args.borrados) {
      const existente = await ctx.db
        .query('entidades')
        .withIndex('por_coleccion_id', (q) => q.eq('coleccion', b.coleccion).eq('id', b.id))
        .unique();
      if (existente) await ctx.db.delete(existente._id);
    }
    if (args.ultimoLote) {
      const total = (await ctx.db.query('entidades').collect()).length;
      const meta = await ctx.db
        .query('meta')
        .withIndex('por_clave', (q) => q.eq('clave', 'estado'))
        .unique();
      const fila = { clave: 'estado', version: args.version, sincronizadoEn: Date.now(), origen: args.origen, entidades: total };
      if (meta) await ctx.db.patch(meta._id, fila);
      else await ctx.db.insert('meta', fila);
    }
    return { escritas, borradas: args.borrados.length };
  },
});

export const meta = internalQuery({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query('meta')
      .withIndex('por_clave', (q) => q.eq('clave', 'estado'))
      .unique();
  },
});

export const coleccion = internalQuery({
  args: { coleccion: v.string(), investigacionId: v.optional(v.string()) },
  handler: async (ctx, args) => {
    const filas = await ctx.db
      .query('entidades')
      .withIndex('por_coleccion', (q) => q.eq('coleccion', args.coleccion))
      .collect();
    return filas.filter((f) => !args.investigacionId || f.investigacionId === args.investigacionId).map((f) => f.datos);
  },
});

export const entidad = internalQuery({
  args: { coleccion: v.string(), id: v.string() },
  handler: async (ctx, args) => {
    const f = await ctx.db
      .query('entidades')
      .withIndex('por_coleccion_id', (q) => q.eq('coleccion', args.coleccion).eq('id', args.id))
      .unique();
    return f ? f.datos : null;
  },
});

export const hashes = internalQuery({
  args: {},
  handler: async (ctx) => {
    const filas = await ctx.db.query('entidades').collect();
    return filas.map((f) => ({ coleccion: f.coleccion, id: f.id, hash: f.hash }));
  },
});
