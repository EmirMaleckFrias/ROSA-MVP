// Espejo del estado de Rosa en Convex. SQLite en el servidor de Rosa sigue
// siendo la fuente de verdad (un solo escritor); aqui se copia cada entidad
// publica (hipotesis, hechos, iteraciones, artefactos, decisiones...) para
// leerla en tiempo real desde cualquier sitio. Una fila por entidad, con la
// coleccion y el id de Rosa; `datos` es el JSON tal como lo ve la interfaz.
import { defineSchema, defineTable } from 'convex/server';
import { v } from 'convex/values';

export default defineSchema({
  entidades: defineTable({
    coleccion: v.string(),
    id: v.string(),
    investigacionId: v.union(v.string(), v.null()),
    version: v.number(),
    hash: v.string(),
    bytes: v.number(),
    truncado: v.boolean(),
    datos: v.any(),
  })
    .index('por_coleccion_id', ['coleccion', 'id'])
    .index('por_coleccion', ['coleccion'])
    .index('por_investigacion', ['investigacionId']),
  meta: defineTable({
    clave: v.string(),
    version: v.number(),
    sincronizadoEn: v.number(),
    origen: v.string(),
    entidades: v.number(),
  }).index('por_clave', ['clave']),
});
