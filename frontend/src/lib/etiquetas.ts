// Textos visibles de cada estado y tipo del dominio. Un solo sitio: un
// estado nuevo en tipos.ts obliga a darle etiqueta aqui (Record exhaustivo),
// y las pantallas nunca ensenan la clave interna.

import type {
  CertezaEvidencia,
  DireccionEvidencia,
  FactorCerteza,
  AccionEspera,
  AlcancePermiso,
  CategoriaCaso,
  ClaseAccion,
  ClasificacionCita,
  ClasificacionDatos,
  EstadoCaso,
  EstadoCorrida,
  EstadoHallazgo,
  EstadoHecho,
  EstadoHipotesis,
  EstadoInvestigacion,
  EstadoPaso,
  EstadoPista,
  EstadoSupuesto,
  NivelAutonomia,
  TipoAfirmacion,
  TipoArtefacto,
  TipoEstudio,
  TipoEvento,
  TipoFuente,
  TipoHallazgo,
  TipoHecho,
  TipoIncidencia,
  TipoPermiso,
  TipoPista,
  TipoRevisionAutomatica,
  Veredicto,
} from '../datos/tipos';

export const ESTADO_CORRIDA: Record<EstadoCorrida, string> = {
  en_marcha: 'En marcha',
  pausada: 'Pausada',
  pausada_por_presupuesto: 'Pausada: presupuesto agotado',
  esperando_aprobacion: 'Esperando tu aprobacion',
  esperando_plan: 'Esperando que apruebes el plan',
  detenida: 'Detenida',
  terminada: 'Terminada',
};

export const ESTADO_INVESTIGACION: Record<EstadoInvestigacion, string> = {
  activa: 'Activa',
  pausada: 'Pausada',
  cerrada: 'Cerrada',
};

export const ESTADO_PASO: Record<EstadoPaso, string> = {
  pendiente: 'Pendiente',
  en_curso: 'En curso',
  hecho: 'Hecho',
  fallido: 'Fallido',
  omitido: 'Omitido',
};

export const TIPO_PISTA: Record<TipoPista, string> = {
  literatura: 'Busqueda de literatura',
  ensayos: 'Ensayos clinicos',
  grafo: 'Grafo de conocimiento',
  extraccion: 'Extraccion de afirmaciones',
  verificacion: 'Verificacion',
  novedad: 'Comprobacion de novedad',
  modelo: 'Modelo de mundo',
  replicacion: 'Replicacion independiente',
};

export const ESTADO_PISTA: Record<EstadoPista, string> = {
  en_curso: 'en curso',
  hecha: 'hecha',
  fallida: 'no se pudo completar',
  detenida: 'detenida por ti',
};

export const TIPO_PERMISO: Record<TipoPermiso, string> = {
  aceptar_hipotesis: 'Aceptar una hipotesis en el modelo de mundo',
  presupuesto_grande: 'Gastar un presupuesto grande',
  fuente_externa: 'Consultar una fuente externa',
  trabajo_largo: 'Lanzar un trabajo largo',
  acceso_corpus: 'Acceder a un corpus',
};

export const ALCANCE: Record<AlcancePermiso, string> = {
  una_vez: 'Solo esta vez',
  esta_corrida: 'Durante esta corrida',
  esta_investigacion: 'En esta investigacion',
  siempre: 'Siempre',
};

export const TIPO_INCIDENCIA: Record<TipoIncidencia, string> = {
  modelo_bloqueado: 'El modelo se nego a responder',
  conector_caducado: 'Un conector caduco',
  fuente_sin_respuesta: 'Una fuente no responde',
};

export const CLASE_ACCION: Record<ClaseAccion, string> = {
  buscar_literatura: 'Buscar literatura y leer articulos',
  correr_analisis: 'Correr un analisis de datos',
  gastar_grande: 'Gastar mas que el presupuesto de una iteracion',
  escribir_modelo_mundo: 'Escribir un hecho en el modelo de mundo',
  descartar_hipotesis: 'Descartar una hipotesis',
  contactar_laboratorio: 'Proponer un experimento a un laboratorio',
};

export const NIVEL_AUTONOMIA: Record<NivelAutonomia, string> = {
  sugerir: 'Solo sugerir',
  preguntar: 'Preguntar antes',
  actuar: 'Actuar y avisar',
};

export const ACCION_ESPERA: Record<AccionEspera, string> = {
  recordar: 'Recordar por Slack o correo',
  escalar: 'Escalar a otra persona',
  detener: 'Detener la corrida con seguridad',
  continuar: 'Continuar y dejarlo registrado',
};

export const ESTADO_HIPOTESIS: Record<EstadoHipotesis, string> = {
  propuesta: 'Propuesta',
  en_revision: 'En revision',
  aceptada: 'Aceptada',
  descartada: 'Descartada',
  refinar: 'Por refinar',
  aclarando: 'Rosa la esta aclarando',
};

export const VEREDICTO: Record<Veredicto, { etiqueta: string; tono: 'ok' | 'aviso' | 'mal'; bloquea: boolean }> = {
  sostenida: { etiqueta: 'Sostenida', tono: 'ok', bloquea: false },
  parcial: { etiqueta: 'Parcial', tono: 'aviso', bloquea: false },
  no_sostenida: { etiqueta: 'No sostenida', tono: 'mal', bloquea: true },
  cita_no_resuelve: { etiqueta: 'Cita sin fuente', tono: 'mal', bloquea: true },
  sin_cita: { etiqueta: 'Sin ninguna cita', tono: 'mal', bloquea: true },
  ausencia_refutada: { etiqueta: 'Dice que no esta, y si esta', tono: 'mal', bloquea: true },
  sin_verificar: { etiqueta: 'Sin comprobar', tono: 'aviso', bloquea: false },
};

export const CERTEZA_EVIDENCIA: Record<CertezaEvidencia, { etiqueta: string; tono: 'ok' | 'aviso' | 'mal' | 'borde'; nota: string; verbo: string }> = {
  alta: { etiqueta: 'Certeza alta', tono: 'ok', nota: 'Varios estudios independientes y directos coinciden. Es muy poco probable que mas investigacion cambie la conclusion.', verbo: 'la evidencia indica que' },
  moderada: { etiqueta: 'Certeza moderada', tono: 'aviso', nota: 'Evidencia consistente pero de una sola cohorte, indirecta o imprecisa. Mas investigacion podria cambiarla.', verbo: 'probablemente' },
  baja: { etiqueta: 'Certeza baja', tono: 'aviso', nota: 'Solo indicios, inferencias o estudios con limitaciones serias. Es probable que mas investigacion la cambie.', verbo: 'puede que' },
  muy_baja: { etiqueta: 'Certeza muy baja', tono: 'mal', nota: 'No hay evidencia directa o es contradictoria. Cualquier estimacion es muy incierta.', verbo: 'no esta claro si' },
};

export const DIRECCION_EVIDENCIA: Record<DireccionEvidencia, { etiqueta: string; tono: 'ok' | 'aviso' | 'mal' | 'borde' }> = {
  apoya: { etiqueta: 'La evidencia apoya la hipotesis', tono: 'ok' },
  mixta: { etiqueta: 'Evidencia mixta', tono: 'aviso' },
  en_contra: { etiqueta: 'La evidencia va en contra', tono: 'mal' },
  sin_evidencia_directa: { etiqueta: 'Sin evidencia directa', tono: 'borde' },
};

export const FACTOR_CERTEZA: Record<FactorCerteza, string> = {
  riesgo_de_sesgo: 'Riesgo de sesgo en los estudios',
  inconsistencia: 'Los estudios no coinciden',
  evidencia_indirecta: 'Evidencia de otra poblacion, medida o contexto',
  imprecision: 'Pocos participantes o pocos estudios',
  sesgo_de_publicacion: 'Posible sesgo de publicacion',
  efecto_grande: 'Efecto grande y consistente',
  gradiente: 'Relacion dosis o tiempo con respuesta',
  replicacion_independiente: 'Replicado en cohortes independientes',
};

export const TIPO_AFIRMACION: Record<TipoAfirmacion, { etiqueta: string; nota: string }> = {
  dato: { etiqueta: 'Dato', nota: 'Sale de un analisis de datos (una celda de codigo).' },
  literatura: { etiqueta: 'Literatura', nota: 'Sale de una fuente publicada.' },
  interpretacion: { etiqueta: 'Interpretacion', nota: 'Es una inferencia de Rosa sobre datos o literatura. Es el tipo que mas falla.' },
};

export const TIPO_HALLAZGO: Record<TipoHallazgo, string> = {
  cita_no_sostiene: 'La cita no sostiene la afirmacion',
  doi_otro_articulo: 'El DOI resuelve a otro articulo',
  valor_contradice_fuente: 'Un valor contradice la fuente',
  resultado_sin_ejecutar: 'Resultado dado por calculado sin ejecutar nada',
  paso_sin_completar: 'Paso del plan sin completar',
  conclusion_no_sigue: 'La conclusion no se sigue del metodo',
  entidad_distinta: 'Dato de otra entidad',
  ausencia_refutada: 'Ausencia desmentida por las fuentes',
  sobreafirmacion: 'Afirma con mas seguridad de la que da la evidencia',
  metrica_inventada: 'Metrica definida por Rosa sin definicion clara',
};

export const ESTADO_HALLAZGO: Record<EstadoHallazgo, string> = {
  abierto: 'Abierto',
  atendido: 'Atendido',
  no_aplica: 'No aplica',
};

export const TIPO_REVISION: Record<TipoRevisionAutomatica, { etiqueta: string; nota: string }> = {
  inicial: { etiqueta: 'Inicial', nota: 'Rapida, sin herramientas: correccion, calidad, novedad y seguridad a primera vista.' },
  completa: { etiqueta: 'Completa', nota: 'Con literatura: supuestos de la idea y su respaldo.' },
  profunda: { etiqueta: 'Verificacion profunda', nota: 'Descompone la hipotesis en supuestos y sub-supuestos y evalua cada uno.' },
  observacion: { etiqueta: 'Observacion', nota: 'Si explica observaciones previas mejor que las explicaciones existentes.' },
  simulacion: { etiqueta: 'Simulacion', nota: 'Simula el mecanismo o el experimento paso a paso para encontrar donde fallaria.' },
  torneo: { etiqueta: 'Torneo', nota: 'Que se le critico en los debates con sus rivales.' },
};

export const ESTADO_SUPUESTO: Record<EstadoSupuesto, { etiqueta: string; tono: 'ok' | 'aviso' | 'mal' | 'neutro' }> = {
  respaldado: { etiqueta: 'Respaldado', tono: 'ok' },
  plausible: { etiqueta: 'Plausible', tono: 'aviso' },
  sin_evidencia: { etiqueta: 'Sin evidencia', tono: 'neutro' },
  contradicho: { etiqueta: 'Contradicho', tono: 'mal' },
};

export const TIPO_FUENTE: Record<TipoFuente, string> = {
  articulo: 'Articulo',
  preprint: 'Preprint',
  ensayo: 'Ensayo clinico',
  grafo: 'Grafo de conocimiento',
  base_curada: 'Base curada',
};

export const TIPO_ESTUDIO: Record<TipoEstudio, string> = {
  revision_sistematica: 'Revision sistematica o metaanalisis',
  ensayo_aleatorizado: 'Ensayo aleatorizado',
  cohorte: 'Cohorte',
  caso_control: 'Casos y controles',
  transversal: 'Transversal',
  serie_de_casos: 'Serie de casos',
  preclinico: 'Preclinico (animal)',
  in_vitro: 'In vitro',
  revision_narrativa: 'Revision narrativa',
  registro: 'Registro o informe institucional',
  otro: 'Otro',
};

export const NIVEL_EVIDENCIA: Record<1 | 2 | 3 | 4 | 5, string> = {
  1: 'Nivel 1: preclinico o in vitro',
  2: 'Nivel 2: opinion, revision narrativa o serie de casos',
  3: 'Nivel 3: observacional (cohorte, casos y controles)',
  4: 'Nivel 4: ensayo aleatorizado o registro regulatorio',
  5: 'Nivel 5: revision sistematica o metaanalisis',
};

export const CLASIFICACION_CITA: Record<ClasificacionCita, string> = {
  apoya: 'Apoya',
  menciona: 'Menciona',
  contrasta: 'Contrasta',
};

export const ESTADO_HECHO: Record<EstadoHecho, string> = {
  sabido: 'Lo que se sabe',
  abierto: 'Lo que esta abierto',
  descartado: 'Lo que se descarto',
};

export const TIPO_HECHO: Record<TipoHecho, string> = {
  hecho: 'Hecho',
  hipotesis: 'Hipotesis',
  pregunta: 'Pregunta',
};

export const TIPO_ARTEFACTO: Record<TipoArtefacto, string> = {
  informe: 'Informe',
  tabla: 'Tabla',
  modelo_mundo: 'Modelo de mundo',
  figura: 'Figura',
  cuaderno: 'Cuaderno',
  specific_aims: 'Specific Aims (NIH)',
};

export const CATEGORIA_CASO: Record<CategoriaCaso, string> = {
  single_hop: 'Un dato',
  multi_hop: 'Varios documentos',
  tabla: 'Tabla',
  abstencion: 'Debe abstenerse',
  entidad: 'Trampa de entidad',
};

export const ESTADO_CASO: Record<EstadoCaso, string> = {
  propuesto: 'Por revisar',
  aprobado: 'Aprobado',
  descartado: 'Descartado',
};

export const CLASIFICACION_DATOS: Record<ClasificacionDatos, string> = {
  publico: 'Publico',
  interno: 'Interno',
  personas: 'Datos de personas',
};

export const TIPO_EVENTO: Record<TipoEvento, string> = {
  iteracion_terminada: 'Iteracion',
  hipotesis_nueva: 'Hipotesis nueva',
  hipotesis_decidida: 'Decision',
  ranking_cambio: 'Ranking',
  permiso_pendiente: 'Permiso',
  permiso_resuelto: 'Permiso',
  incidencia: 'Incidencia',
  presupuesto: 'Presupuesto',
  corrida_estado: 'Corrida',
  hecho_nuevo: 'Modelo de mundo',
  retraccion: 'Retractacion',
  literatura_nueva: 'Literatura nueva',
  revision_automatica: 'Revisor',
};
