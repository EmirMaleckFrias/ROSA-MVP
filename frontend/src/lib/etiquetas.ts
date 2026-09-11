// Textos visibles de cada estado y tipo del dominio. Un solo sitio: un
// estado nuevo en tipos.ts obliga a darle etiqueta aqui (Record exhaustivo),
// y las pantallas nunca ensenan la clave interna.

import type {
  Afirmacion,
  Bloqueo,
  CambioAprendizaje,
  CertezaEvidencia,
  ClaseEvidencia,
  DecisionKiller,
  DimensionesResultado,
  DireccionEvidencia,
  Ejecucion,
  EtapaDecision,
  FactorCerteza,
  InterpretacionEjecucion,
  MetodoRegistrado,
  NivelAprendizaje,
  PasoRutaTerapeutica,
  ProcedenciaDataset,
  Reproduccion,
  ResultadoLaboratorio,
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
  dossier: 'Dossier para el laboratorio',
  prerregistro: 'Prerregistro',
};

/* ---------------------------------------------------------------------
   ROSA2018: Killer, decisiones, bloqueos, analisis, retorno, aprendizaje
   --------------------------------------------------------------------- */

export const DECISION_KILLER: Record<DecisionKiller, { etiqueta: string; tono: 'ok' | 'aviso' | 'mal' | 'borde'; nota: string }> = {
  avanzar: { etiqueta: 'Avanza', tono: 'ok', nota: 'Pasa las comprobaciones criticas y tiene prediccion falsable. Puede ser candidata al laboratorio.' },
  reformular: { etiqueta: 'Reformular', tono: 'aviso', nota: 'Falla algo arreglable (causalidad, falsabilidad, factibilidad o redundancia). Rosa escribe una version nueva y la vuelve a juzgar.' },
  suspender: { etiqueta: 'Suspendida (no evaluable)', tono: 'borde', nota: 'Una comprobacion critica no se pudo hacer: una fuente no respondio o falta el dato. No es un fallo de la hipotesis.' },
  descartar_en_contexto: { etiqueta: 'Descartar en este contexto', tono: 'mal', nota: 'La evidencia no la sostiene: citas que no resuelven, afirmaciones no sostenidas o un supuesto invalidante.' },
};

export const ETAPA_DECISION: Record<EtapaDecision, string> = {
  killer_1: 'Hypothesis Killer',
  killer_2: 'Auditor del analisis',
  priorizacion: 'Priorizacion',
  persona: 'Persona',
  retorno: 'Retorno del laboratorio',
};

export const COMPROBACION_KILLER: Record<string, string> = {
  citas_reales: 'Las citas resuelven a una fuente real',
  fidelidad_evidencia: 'La fuente dice lo que la afirmacion dice',
  supuestos: 'Ningun supuesto necesario esta contradicho',
  independencia_cohortes: 'Replicacion en cohortes distintas',
  direccion_evidencia: 'La evidencia va en la direccion del enunciado',
  identificadores_resuelven: 'La diana resuelve a identificadores estables (Ensembl, UniProt)',
  unidades: 'Las cifras comparadas estan en la misma unidad',
  fuente_primaria: 'Hay fuentes con datos propios, no solo citas',
  direccion_causal: 'La direccion causal tiene temporalidad y alternativa',
  falsabilidad: 'Hay una observacion medible que la refutaria',
  novedad: 'Novedad comprobada con busqueda',
  factibilidad: 'Existe cohorte, ensayo o tecnica para comprobarla',
  redundancia: 'No repite lo ya sabido ni otra hipotesis viva',
  sesgo_evidencia: 'La evidencia no tiene un riesgo de sesgo serio',
  semilla: 'El codigo fija la semilla',
  fuga_de_datos: 'Sin fuga entre entrenamiento y prueba',
  coincide_con_plan: 'El codigo hace lo que dice el plan',
  baseline_y_control: 'Hay baseline y control negativo',
  tamano_muestral: 'El n por grupo basta',
  multiplicidad: 'La multiplicidad se corrigio',
  relevancia_prueba: 'La prueba responde a la pregunta',
  confusores: 'Los confusores tratados son razonables',
  interpretacion_no_sobrepasa: 'La interpretacion no sobrepasa las cifras',
  unidades_y_escala: 'Unidades y escala plausibles',
};

export const RESULTADO_COMPROBACION: Record<'pasa' | 'falla' | 'no_aplica' | 'no_comprobable', { etiqueta: string; tono: 'ok' | 'aviso' | 'mal' | 'borde' }> = {
  pasa: { etiqueta: 'Pasa', tono: 'ok' },
  falla: { etiqueta: 'Falla', tono: 'mal' },
  no_aplica: { etiqueta: 'No aplica', tono: 'borde' },
  no_comprobable: { etiqueta: 'No se pudo comprobar', tono: 'aviso' },
};

export const BLOQUEO: Record<Bloqueo, string> = {
  trazabilidad_insuficiente: 'Trazabilidad insuficiente',
  datos_no_autorizados: 'Datos no autorizados',
  analisis_invalido: 'Analisis invalido',
  sin_experimento_interpretable: 'Sin experimento interpretable',
  descartada_por_killer: 'Descartada en este contexto',
  fuente_retractada: 'Fuente retractada',
};

export const CLASE_EVIDENCIA: Record<ClaseEvidencia, { etiqueta: string; nota: string }> = {
  observacion_original: { etiqueta: 'Observacion', nota: 'Medida directa: un dato de laboratorio o de un dataset con procedencia.' },
  derivado: { etiqueta: 'Derivado', nota: 'Calculado a partir de otros datos por codigo auditado.' },
  literatura: { etiqueta: 'Literatura', nota: 'Lo que afirma una fuente publicada.' },
  prediccion: { etiqueta: 'Prediccion', nota: 'Salida de un modelo o dato sintetico. Nunca cuenta como observacion.' },
};

export const ESTADO_EJECUCION: Record<Ejecucion['estado'], { etiqueta: string; tono: 'ok' | 'aviso' | 'mal' | 'borde' | 'acento' }> = {
  no_ejecutado: { etiqueta: 'No ejecutado', tono: 'borde' },
  en_curso: { etiqueta: 'En curso', tono: 'acento' },
  error_tecnico: { etiqueta: 'Error tecnico', tono: 'mal' },
  tiempo_agotado: { etiqueta: 'Tiempo agotado (error tecnico)', tono: 'mal' },
  completado: { etiqueta: 'Ejecutado', tono: 'ok' },
};

export const INTERPRETACION_EJECUCION: Record<InterpretacionEjecucion, { etiqueta: string; tono: 'ok' | 'aviso' | 'borde' }> = {
  efecto_detectado: { etiqueta: 'Efecto detectado', tono: 'ok' },
  sin_efecto_detectable: { etiqueta: 'Sin efecto detectable', tono: 'aviso' },
  no_evaluable: { etiqueta: 'No evaluable con estos datos', tono: 'borde' },
};

export const VEREDICTO_AUDITORIA: Record<'valido' | 'no_valido' | 'no_evaluable_computacionalmente', { etiqueta: string; tono: 'ok' | 'mal' | 'borde' }> = {
  valido: { etiqueta: 'Analisis valido', tono: 'ok' },
  no_valido: { etiqueta: 'Analisis no valido', tono: 'mal' },
  no_evaluable_computacionalmente: { etiqueta: 'No evaluable computacionalmente', tono: 'borde' },
};

export const RUNTIME_EJECUCION: Record<Ejecucion['runtime'], string> = {
  docker: 'Contenedor Docker sin red',
  container: 'Micro-VM de Apple container sin red',
  local_sintetico: 'Aislamiento blando local (solo datos sinteticos)',
  ninguno: 'Sin runtime de aislamiento',
};

export const ESTADO_REPRODUCCION: Record<Reproduccion['estado'], { etiqueta: string; tono: 'ok' | 'aviso' | 'mal' | 'borde' | 'acento' }> = {
  pendiente: { etiqueta: 'Pendiente', tono: 'borde' },
  en_curso: { etiqueta: 'En curso', tono: 'acento' },
  superada: { etiqueta: 'Reproducida dentro de tolerancia', tono: 'ok' },
  fallida: { etiqueta: 'Fuera de tolerancia', tono: 'mal' },
  error_tecnico: { etiqueta: 'Error tecnico (no cuenta como fallo cientifico)', tono: 'aviso' },
};

export const RESULTADO_LABORATORIO: Record<ResultadoLaboratorio, { etiqueta: string; tono: 'ok' | 'aviso' | 'mal' | 'borde'; nota: string }> = {
  apoyo_reproducido: { etiqueta: 'Apoyo reproducido', tono: 'ok', nota: 'Efecto en la direccion predicha, controles validos, criterio cumplido.' },
  negativo_interpretable: { etiqueta: 'Negativo interpretable', tono: 'mal', nota: 'Controles validos y potencia suficiente: el resultado va en contra.' },
  inconcluso: { etiqueta: 'Inconcluso', tono: 'aviso', nota: 'Controles validos pero potencia insuficiente o intervalo que cruza el efecto minimo.' },
  fallo_tecnico: { etiqueta: 'Fallo tecnico', tono: 'borde', nota: 'El ensayo no se ejecuto como se prerregistro o un control fallo. No toca la hipotesis.' },
  toxicidad_inviabilidad: { etiqueta: 'Toxicidad o inviabilidad', tono: 'mal', nota: 'El modelo no tolero la intervencion o no hubo exposicion en el tejido.' },
  correccion_contexto: { etiqueta: 'Correccion de contexto', tono: 'aviso', nota: 'El efecto existe pero en otra variable, tejido, etapa o poblacion: nace una hipotesis derivada.' },
};

export const NIVEL_APRENDIZAJE: Record<NivelAprendizaje, { etiqueta: string; nota: string }> = {
  1: { etiqueta: 'Nivel 1: creencias', nota: 'Que cree Rosa de cada hipotesis. Automatico y registrado; reversible reabriendo la hipotesis.' },
  2: { etiqueta: 'Nivel 2: como razona', nota: 'Criterios de revision y programas optimizados. Rosa propone, se evalua sobre el conjunto reservado y una persona promueve o revierte.' },
  3: { etiqueta: 'Nivel 3: politicas', nota: 'Los limites del sistema. Solo los cambia una persona, en el codigo o eximiendo una puerta con motivo.' },
};

export const ESTADO_APRENDIZAJE: Record<CambioAprendizaje['estado'], { etiqueta: string; tono: 'ok' | 'aviso' | 'mal' | 'borde' | 'acento' }> = {
  aplicado: { etiqueta: 'Aplicado', tono: 'ok' },
  propuesto: { etiqueta: 'Propuesto', tono: 'acento' },
  evaluado: { etiqueta: 'Evaluado', tono: 'aviso' },
  promovido: { etiqueta: 'Promovido', tono: 'ok' },
  revertido: { etiqueta: 'Revertido', tono: 'mal' },
};

export const TIPO_APRENDIZAJE: Record<CambioAprendizaje['tipo'], string> = {
  creencia: 'Creencia sobre una hipotesis',
  criterio: 'Criterio de revision',
  programa: 'Programa optimizado (GEPA)',
  politica: 'Politica',
  modelo_de_mundo: 'Modelo de mundo',
  hipotesis_derivada: 'Hipotesis derivada',
};

export const ACCESO_DATASET: Record<ProcedenciaDataset['acceso'], string> = {
  abierto: 'Abierto',
  controlado: 'Controlado (acuerdo de uso)',
  colaboracion: 'Por colaboracion',
  propio: 'Propio del laboratorio',
};

export const USO_IA: Record<ProcedenciaDataset['usoIAAutorizado'], { etiqueta: string; tono: 'ok' | 'mal' | 'aviso' }> = {
  si: { etiqueta: 'Uso con IA autorizado', tono: 'ok' },
  no: { etiqueta: 'Uso con IA no autorizado', tono: 'mal' },
  desconocido: { etiqueta: 'Uso con IA sin confirmar', tono: 'aviso' },
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
  killer: 'Hypothesis Killer',
  analisis: 'Analisis con datos',
  aprendizaje: 'Aprendizaje',
  mision: 'Mision',
  dependencias: 'Recalculo por cambio de fuente',
};

export const PASO_RUTA: Record<PasoRutaTerapeutica, { etiqueta: string; orden: number }> = {
  mecanismo: { etiqueta: 'Mecanismo', orden: 1 },
  opciones_intervencion: { etiqueta: 'Opciones de intervencion', orden: 2 },
  compromiso_diana: { etiqueta: 'Compromiso de diana', orden: 3 },
  efecto_funcional: { etiqueta: 'Efecto funcional', orden: 4 },
  selectividad_toxicidad: { etiqueta: 'Selectividad y toxicidad', orden: 5 },
  exposicion: { etiqueta: 'Entrega y exposicion', orden: 6 },
  replicacion_independiente: { etiqueta: 'Replicacion independiente', orden: 7 },
  evidencia_poblacion: { etiqueta: 'Evidencia en la poblacion', orden: 8 },
};

export const ESTADO_METODO: Record<MetodoRegistrado['estado'], { etiqueta: string; tono: 'ok' | 'aviso' | 'mal' | 'borde' | 'acento' }> = {
  propuesto: { etiqueta: 'Propuesto', tono: 'borde' },
  implementado: { etiqueta: 'Implementado, sin probar en contexto', tono: 'aviso' },
  probado_en_contexto: { etiqueta: 'Probado en contexto', tono: 'ok' },
  restringido: { etiqueta: 'Restringido', tono: 'mal' },
  retirado: { etiqueta: 'Retirado', tono: 'mal' },
};

export const TIPO_METODO: Record<MetodoRegistrado['tipo'], string> = {
  analisis: 'Metodo de analisis',
  predictor: 'Predictor',
  recurso_datos: 'Recurso de datos',
  ensayo_laboratorio: 'Ensayo de laboratorio',
  busqueda: 'Busqueda y recuperacion',
  revision: 'Revision y verificacion',
};

export const NIVEL_MEDICION: Record<NonNullable<Afirmacion['nivelMedicion']>, string> = {
  medida: 'Medida directa',
  resultado_analisis: 'Resultado de un analisis',
  interpretacion_autor: 'Interpretacion de los autores',
  interpretacion_rosa: 'Interpretacion de Rosa',
};

export const DIMENSION_RESULTADO: Record<keyof Omit<DimensionesResultado, 'nota'>, string> = {
  falloTecnico: 'Fallo tecnico',
  inconcluso: 'Inconcluso',
  efectoPequenoInterpretable: 'Efecto pequeno interpretable',
  efectoPredicho: 'Efecto predicho',
  efectoInesperado: 'Efecto inesperado',
  toxicidad: 'Toxicidad',
};

export const IDENTIFICACION_CAUSAL: Record<string, string> = {
  identificable: 'Identificable',
  acotado: 'Acotado: faltan supuestos',
  sin_resolver: 'Sin resolver',
};

export const TIPO_ARISTA: Record<string, string> = {
  supuesto: 'supuesto',
  inferencia_con_evidencia: 'inferencia con evidencia',
  base_curada: 'base curada',
};

export const GRUPO_CONECTOR: Record<string, string> = {
  genomas: 'Genomas',
  genes_ontologias: 'Genes y ontologias',
  variantes: 'Variantes',
  genetica_humana: 'Genetica humana',
  genomica_clinica: 'Genomica clinica',
  expresion: 'Expresion',
  regulacion: 'Regulacion',
  proteinas: 'Anotacion de proteinas',
  estructuras: 'Estructuras e interacciones',
  rna: 'RNA',
  omicas: 'Archivos omicos',
  cancer: 'Modelos de cancer',
  quimica: 'Quimica',
  regulatorio: 'Regulacion de farmacos',
  farmacos: 'Farmacos y dianas',
  enriquecimiento: 'Enriquecimiento de conjuntos de genes',
  literatura: 'Literatura',
  recursos: 'Recursos de investigacion',
  directorio: 'Conectores del directorio',
  socios: 'Socios y plataformas',
  alzheimer: 'Especificos del Alzheimer',
  otros: 'Otros',
};

export const ESTADO_CONECTOR: Record<string, { etiqueta: string; tono: 'ok' | 'aviso' | 'mal' | 'neutro' }> = {
  disponible: { etiqueta: 'Disponible', tono: 'ok' },
  requiere_cuenta: { etiqueta: 'Requiere cuenta', tono: 'aviso' },
  sin_api: { etiqueta: 'Sin API', tono: 'neutro' },
  licencia: { etiqueta: 'Licencia', tono: 'mal' },
  fichero_local: { etiqueta: 'Fichero local', tono: 'neutro' },
};

export const CLASE_HALLAZGO_REGISTRO: Record<string, string> = {
  calculo_no_ejecutado: 'Calculo que no se ejecuto',
  contradiccion_con_registro: 'Contradice el registro',
  cita_sin_soporte: 'Cita sin soporte',
  identificador_no_coincide: 'Identificador que no coincide',
  paso_incompleto: 'Paso del plan incompleto',
  conclusion_no_sigue: 'La conclusion no se sigue del metodo',
};
