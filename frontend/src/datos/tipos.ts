// Tipos del dominio de Rosa, tal como los consume la interfaz.
//
// Son el contrato entre las pantallas y el almacen (almacen.ts). Hoy el
// almacen sirve datos de muestra y una corrida simulada; cuando entre el
// almacen real (Convex o Postgres con suscripciones, decision pendiente de
// la persona responsable y su companero) estas formas son las que tiene que devolver, y las
// pantallas no cambian.
//
// Nombres en espanol y en camelCase, como en el esquema del RAG. Los estados
// son uniones cerradas: la interfaz pinta cada uno con su texto y su color, y
// un estado nuevo tiene que anadirse aqui y en su etiqueta, no colarse como
// cadena libre.
//
// La segunda tanda de campos (presupuesto global, incidencias, plan por
// aprobar, tipo de afirmacion, cobertura, partidos, supuestos, panorama,
// autonomia, datasets, procesos, experimentos) sale de
// INVESTIGACION-INTERFACES.md: lo que hacen Claude Science, Kosmos,
// Co-Scientist, Biomni y las herramientas de literatura y Rosa no tenia.

export type Id = string;

/* ---------------------------------------------------------------------
   Investigacion y corrida
   --------------------------------------------------------------------- */

export type EstadoInvestigacion = 'activa' | 'pausada' | 'cerrada';

/** El objetivo parseado, como la "research plan configuration" de
 *  Co-Scientist: alimenta los prompts de generacion, revision y debate. */
export interface ConfiguracionObjetivo {
  preferencias: string;
  atributos: string[];
  restricciones: string[];
}

export type ClasificacionDatos = 'publico' | 'interno' | 'personas';

/** Un conjunto de datos adjunto a la investigacion, con su contrato de
 *  datos: la comprobacion previa que evita que un p-valor guardado como 0
 *  contamine horas de corrida (fallo documentado en Kosmos). */
export interface Dataset {
  id: Id;
  nombre: string;
  descripcion: string;
  tamanoMb: number;
  columnas: number;
  columnasSinDiccionario: number;
  valoresCentinela: number;
  nombresDuplicados: number;
  clasificacion: ClasificacionDatos;
  estado: 'pendiente' | 'aprobado' | 'rechazado';
  origen: 'subida' | 'catalogo';
}

export interface Investigacion {
  id: Id;
  titulo: string;
  objetivo: string;
  /** Que cuenta como relevante para esta investigacion, en una frase. */
  relevancia: string;
  limites: string[];
  condicionParada: string;
  revisores: string[];
  estado: EstadoInvestigacion;
  creadaEn: number;
  /** Id de la investigacion de la que se bifurco, si es una rama. */
  ramaDe: Id | null;
  configuracion: ConfiguracionObjetivo;
  datasets: Dataset[];
  /** Hasta cuando vigilar la literatura tras cerrar la corrida. Null = no. */
  vigilarLiteraturaHasta: number | null;
}

export type EstadoCorrida =
  | 'en_marcha'
  | 'pausada'
  | 'pausada_por_presupuesto'
  | 'esperando_aprobacion'
  | 'esperando_plan'
  | 'detenida'
  | 'terminada';

export interface Gasto {
  tokensEntrada: number;
  tokensSalida: number;
  llamadas: number;
  /** Segundos de reloj desde que empezo la corrida. */
  segundos: number;
  /** Articulos leidos en toda la corrida. */
  articulosLeidos: number;
}

/** Tope duro de la corrida completa, con alarmas antes del tope. Al llegar
 *  la corrida se pausa, no muere; se reanuda ampliando el tope. Una pregunta
 *  pendiente tiene prioridad sobre el tope. */
export interface PresupuestoGlobal {
  limiteLlamadas: number;
  alertas: number[];
  /** Alertas ya avisadas (fracciones), para no repetir. */
  avisadas: number[];
}

/** Ocupacion del contexto del cerebro del bucle y compactaciones hechas. */
export interface Contexto {
  tokensUsados: number;
  tokensLimite: number;
  compactaciones: number;
  ultimaCompactacion: number | null;
}

export type TipoIncidencia = 'modelo_bloqueado' | 'conector_caducado' | 'fuente_sin_respuesta';

/** Algo que impide seguir y necesita a una persona: un modelo que devolvio
 *  vacio con content-filter, una clave de conector caducada. Se ensena como
 *  tarjeta con alternativa; nunca muere en silencio. */
export interface Incidencia {
  id: Id;
  corridaId: Id;
  tipo: TipoIncidencia;
  titulo: string;
  detalle: string;
  recurso: string;
  alternativa: string | null;
  estado: 'pendiente' | 'resuelta';
  creadaEn: number;
  resueltaEn: number | null;
  resolucion: string | null;
}

/** Una consulta exacta a una base, para la estrategia reproducible (PRISMA). */
export interface ConsultaBusqueda {
  base: string;
  consulta: string;
  fecha: number;
  resultados: number;
}

/** El flujo de la busqueda de la corrida: identificados, cribados, leidos a
 *  texto completo, usados en hipotesis. */
export interface FlujoBusqueda {
  identificados: number;
  cribados: number;
  textoCompleto: number;
  usados: number;
  consultas: ConsultaBusqueda[];
}

/** Estimacion de cobertura por tema (curva de descubrimiento, como Undermind):
 *  cuantos leidos y que fraccion de lo relevante se estima encontrada. */
export interface Cobertura {
  tema: string;
  leidos: number;
  fraccion: number;
  /** Escala de la curva 1 - e^(-n/tau). */
  tau: number;
}

/** Debilidad recurrente detectada por la meta-revision de una iteracion. */
export interface Debilidad {
  id: Id;
  texto: string;
  hipotesisAfectadas: Id[];
  inyectada: boolean;
}

export interface MetaRevision {
  iteracion: number;
  fecha: number;
  debilidades: Debilidad[];
}

/** Un proceso de computo vivo (kernel, trabajo remoto). */
export interface Proceso {
  id: Id;
  nombre: string;
  host: string;
  cpu: number;
  memoriaMb: number;
  estado: 'en_marcha' | 'detenido' | 'terminado';
  empezadoEn: number;
}

export interface Direccion {
  titulo: string;
  razon: string;
  hallazgosRecientes: string[];
  queInvestigar: string[];
  ideaEjemplo: string;
  inesperada: boolean;
  hipotesisIds: Id[];
}

export interface Corrida {
  id: Id;
  investigacionId: Id;
  numero: number;
  estado: EstadoCorrida;
  empezadaEn: number;
  terminadaEn: number | null;
  iteracionActual: number;
  gasto: Gasto;
  /** Motivo por el que se detuvo o termino, si aplica. */
  motivoCierre: string | null;
  presupuesto: PresupuestoGlobal;
  contexto: Contexto;
  busqueda: FlujoBusqueda;
  coberturas: Cobertura[];
  metaRevisiones: MetaRevision[];
  procesos: Proceso[];
  /** El panorama de investigacion: direcciones principales sintetizadas. */
  panorama: Direccion[];
  /** Si el plan de cada iteracion se autoaprueba tras N segundos sin respuesta. Null = espera siempre. */
  autoAprobarPlanSegundos: number | null;
  /** Que Rosa exacta corrio: commit del codigo, hash de las firmas DSPy y
   *  programas optimizados cargados. Para auditar cada hipotesis. */
  arnes?: { commit: string; firmas: string; optimizados: string };
}

export type EstadoPaso = 'pendiente' | 'en_curso' | 'hecho' | 'fallido' | 'omitido';

/** Un paso del plan de la iteracion. Se marca segun avanza. Un paso
 *  fallido lleva su motivo, como la lista de control de Biomni. */
export interface PasoPlan {
  id: Id;
  titulo: string;
  detalle: string;
  estado: EstadoPaso;
  /** Lo escribio la investigadora al dirigir la corrida o editar el plan. */
  indicacionHumana: boolean;
  motivoFallo: string | null;
  /** Presupuesto de llamadas para este paso, si se fijo. */
  presupuesto: number | null;
}

export type TipoPista = 'literatura' | 'ensayos' | 'grafo' | 'extraccion' | 'verificacion' | 'novedad' | 'modelo' | 'replicacion';
export type EstadoPista = 'en_curso' | 'hecha' | 'fallida' | 'detenida';

/** Una consulta a una fuente, con sus parametros exactos y lo que devolvio,
 *  como los pasos de conector expandibles de Claude Science. */
export interface DetalleConsulta {
  base: string;
  parametros: string;
  resultados: string;
}

export interface EntradaTranscripcion {
  /** Momento relativo al inicio de la pista, en ms. */
  t: number;
  tipo: 'accion' | 'resultado' | 'nota' | 'error';
  texto: string;
  consulta?: DetalleConsulta;
}

export interface Pista {
  id: Id;
  iteracionId: Id;
  /** Paso del plan al que sirve. Null en pistas antiguas sin esa marca. */
  pasoId: Id | null;
  tipo: TipoPista;
  titulo: string;
  fuente: string;
  estado: EstadoPista;
  resumen: string;
  ms: number;
  transcripcion: EntradaTranscripcion[];
}

export interface Iteracion {
  id: Id;
  corridaId: Id;
  numero: number;
  empezadaEn: number;
  terminadaEn: number | null;
  plan: PasoPlan[];
  /** El plan se aprueba antes de ejecutarse. */
  planAprobado: boolean;
  planPropuestoEn: number;
  pistas: Pista[];
  /** Presupuesto de la iteracion en llamadas al modelo, y lo usado. */
  presupuesto: { limite: number; usado: number };
  /** Resumen de una linea al cerrar. */
  resumen: string;
  /** El mismo cierre contado para quien no es cientifico. Lo escribe Rosa al
   *  cerrar; falta en iteraciones abiertas o si el modelo no respondio. */
  resumenLlano?: ResumenLlano | null;
}

/** Un termino tecnico con su explicacion en una frase. */
export interface TerminoLlano {
  termino: string;
  explicacion: string;
}

/** Lo que hizo Rosa en una iteracion, con la estructura de un resumen en
 *  lenguaje llano de Cochrane: pregunta, mensajes clave, que buscaba, que
 *  hizo, que encontro, limitaciones, que cambio, que propone, que falta, que
 *  toca, y hasta cuando esta al dia. */
export interface ResumenLlano {
  titulo: string;
  mensajesClave: string[];
  queBuscaba: string;
  queHizo: string;
  queEncontro: string[];
  limitaciones: string;
  cambios: string[];
  quePropone: string[];
  queFalta: string;
  queTeToca: string;
  alDia: { fechaBusqueda: number | null; fuentesSinRespuesta: string[] };
  terminos: TerminoLlano[];
}

/* ---------------------------------------------------------------------
   Permisos y autonomia
   --------------------------------------------------------------------- */

export type TipoPermiso =
  | 'aceptar_hipotesis'
  | 'presupuesto_grande'
  | 'fuente_externa'
  | 'trabajo_largo'
  | 'acceso_corpus';

export type AlcancePermiso = 'una_vez' | 'esta_corrida' | 'esta_investigacion' | 'siempre';

export type EstadoSolicitud = 'pendiente' | 'concedida' | 'denegada';

/** Un argumento editable de la accion propuesta (por ejemplo cuantas
 *  llamadas), para poder ajustarlo antes de permitir. */
export interface ArgumentoSolicitud {
  nombre: string;
  valor: string;
  editable: boolean;
}

export interface SolicitudPermiso {
  id: Id;
  corridaId: Id;
  tipo: TipoPermiso;
  titulo: string;
  detalle: string;
  /** Lo que pide, con nombre exacto ("api.clinicaltrials.gov"). */
  recurso: string;
  alcances: AlcancePermiso[];
  estado: EstadoSolicitud;
  alcanceConcedido: AlcancePermiso | null;
  creadaEn: number;
  resueltaEn: number | null;
  /** Hipotesis afectada, cuando el permiso es aceptarla. */
  hipotesisId: Id | null;
  argumentos: ArgumentoSolicitud[];
}

export interface PermisoConcedido {
  id: Id;
  tipo: TipoPermiso;
  recurso: string;
  alcance: AlcancePermiso;
  concedidoEn: number;
  investigacionId: Id | null;
}

/** Clases de accion del dial de autonomia. */
export type ClaseAccion =
  | 'buscar_literatura'
  | 'correr_analisis'
  | 'gastar_grande'
  | 'escribir_modelo_mundo'
  | 'descartar_hipotesis'
  | 'contactar_laboratorio';

export type NivelAutonomia = 'sugerir' | 'preguntar' | 'actuar';

/* ---------------------------------------------------------------------
   Hipotesis, verificacion y procedencia
   --------------------------------------------------------------------- */

export type EstadoHipotesis = 'propuesta' | 'en_revision' | 'aceptada' | 'descartada' | 'refinar' | 'aclarando';

/** Veredictos del verificador. Mismos que en el RAG (TRASPASO 4.1). */
export type Veredicto =
  | 'sostenida'
  | 'parcial'
  | 'no_sostenida'
  | 'cita_no_resuelve'
  | 'sin_cita'
  | 'ausencia_refutada'
  | 'sin_verificar';

/** De donde sale la afirmacion. Kosmos midio 85 % de acierto en datos,
 *  82 % en literatura y 58 % en interpretaciones: no se tratan igual. */
export type TipoAfirmacion = 'dato' | 'literatura' | 'interpretacion';

export interface Afirmacion {
  texto: string;
  cita: string;
  veredicto: Veredicto;
  motivo: string;
  /** Dato real pero de otra entidad (otro farmaco, cohorte, estudio). */
  entidadDistinta: boolean;
  tipo: TipoAfirmacion;
  /** Trayectoria y celda de codigo que produjeron la cifra, si es un dato. */
  trayectoria: { id: string; celda: number } | null;
  /** El pasaje literal de la fuente en que se apoya, tal como lo copio el
   *  extractor. Es lo que se ensena al lado de la cita para que la persona
   *  compruebe sin abrir el PDF. */
  fragmento?: string;
}

export type TipoFuente = 'articulo' | 'preprint' | 'ensayo' | 'grafo' | 'base_curada';

export type TipoEstudio =
  | 'revision_sistematica'
  | 'ensayo_aleatorizado'
  | 'cohorte'
  | 'caso_control'
  | 'transversal'
  | 'serie_de_casos'
  | 'preclinico'
  | 'in_vitro'
  | 'revision_narrativa'
  | 'registro'
  | 'otro';

export type MarcaEditorial = 'retractado' | 'preocupacion' | 'erratum' | null;

export interface Fuente {
  id: Id;
  /** Referencia corta: "Cohorte clinica, 2023". */
  referencia: string;
  titulo: string;
  tipo: TipoFuente;
  doi: string | null;
  pmid: string | null;
  nct: string | null;
  /** Pagina del visor de PDF. La cita resuelve a esta pagina exacta. */
  pagina: number | null;
  fragmento: string;
  retraccion: MarcaEditorial;
  /** Cuando se comprobo por ultima vez contra Crossref y Retraction Watch. */
  retraccionComprobadaEn: number | null;
  anio: number | null;
  tipoEstudio: TipoEstudio;
  /** Nivel potencial de evidencia, 1 (mas bajo) a 5 (mas alto). No es calidad real. */
  nivelEvidencia: 1 | 2 | 3 | 4 | 5;
  /** Se leyo el texto completo o solo el resumen. */
  textoCompleto: boolean;
  citas: number | null;
}

export interface MensajeProcedencia {
  id: Id;
  de: 'rosa' | 'investigadora' | 'revisor';
  texto: string;
  creadoEn: number;
}

export interface Paquete {
  nombre: string;
  version: string;
}

export interface Procedencia {
  mensajes: MensajeProcedencia[];
  codigo: string;
  registro: string[];
  entorno: { lenguaje: string; version: string; paquetes: Paquete[]; modelos: Paquete[] };
  fuentes: Fuente[];
}

export type TipoHallazgo =
  | 'cita_no_sostiene'
  | 'doi_otro_articulo'
  | 'valor_contradice_fuente'
  | 'resultado_sin_ejecutar'
  | 'paso_sin_completar'
  | 'conclusion_no_sigue'
  | 'entidad_distinta'
  | 'ausencia_refutada'
  | 'sobreafirmacion'
  | 'metrica_inventada';

export type EstadoHallazgo = 'abierto' | 'atendido' | 'no_aplica';

export interface HallazgoRevisor {
  id: Id;
  tipo: TipoHallazgo;
  resumen: string;
  razonamiento: string;
  estado: EstadoHallazgo;
  respuestaDeRosa: string | null;
}

/** Los tipos de revision del agente, separados, como en Co-Scientist. */
export type TipoRevisionAutomatica = 'inicial' | 'completa' | 'profunda' | 'observacion' | 'simulacion' | 'torneo';

export interface RevisionAutomatica {
  tipo: TipoRevisionAutomatica;
  estado: 'pendiente' | 'hecha' | 'rehecha';
  resumen: string;
  fecha: number | null;
}

export type EstadoSupuesto = 'respaldado' | 'plausible' | 'sin_evidencia' | 'contradicho';

/** Un supuesto de la hipotesis, descompuesto e independiente de las citas
 *  (la "verificacion profunda" de Co-Scientist). */
export interface Supuesto {
  id: Id;
  texto: string;
  estado: EstadoSupuesto;
  evidencia: string;
  hijos: Supuesto[];
}

export interface AnclaComentario {
  cita: string;
  campo: 'enunciado' | 'mecanismo' | 'afirmacion' | 'comprobacion' | 'fuente';
}

export interface Comentario {
  id: Id;
  hipotesisId: Id;
  ancla: AnclaComentario;
  nota: string;
  estado: 'pendiente' | 'enviado';
  creadoEn: number;
}

export interface Revision {
  fecha: number;
  quien: string;
  accion: 'propuesta' | 'aceptada' | 'descartada' | 'refinar' | 'reabierta' | 'comentada' | 'no_puedo_juzgar' | 'aclarada' | 'replicada';
  nota: string;
  /** La decision se tomo sin ver las citas ni el codigo. */
  aCiegas: boolean;
}

/** Revision escrita por una persona, estructurada como la del agente, para
 *  que entre al siguiente debate del torneo. */
export interface RevisionHumana {
  fecha: number;
  quien: string;
  supuestosCuestionados: string;
  literaturaQueFalta: string;
  problemaExperimental: string;
}

export interface Novedad {
  openTargets: { estado: 'sin_evidencia' | 'evidencia_previa'; detalle: string };
  ensayos: { estado: 'sin_ensayo' | 'ensayo_existente'; detalle: string; nct: string | null };
  agora: { estado: 'no_nominada' | 'nominada'; detalle: string };
  /** Si alguien ya lo propuso en la literatura (comprobacion tipo Owl). */
  precedente: { estado: 'sin_precedente' | 'parcial' | 'ya_publicado'; detalle: string };
}

export interface PuntoElo {
  iteracion: number;
  elo: number;
}

/** Un partido del torneo: contra quien, quien gano y por que. */
export interface Partido {
  iteracion: number;
  rivalId: Id;
  resultado: 'gano' | 'perdio';
  resumenDebate: string;
  ejeDecisivo: 'correccion' | 'utilidad' | 'especificidad' | 'novedad' | 'deseabilidad';
}

export interface Replicacion {
  total: number;
  hechas: number;
  sostienen: number;
  contradicen: number;
  estado: 'en_curso' | 'terminada';
  empezadaEn: number;
}

export interface Experimento {
  protocolo: string;
  ensayo: string;
  costeEstimado: string;
  laboratorio: string | null;
  estado: 'propuesto' | 'asignado' | 'en_curso' | 'datos_recibidos';
  ficheroDatos: string | null;
  analisisPedido: string;
  /** Al asignarlo a un laboratorio se congela un prerregistro (hipotesis,
   *  protocolo, criterios) como artefacto inmutable. */
  prerregistradoEn?: number | null;
  prerregistroArtefactoId?: string | null;
}

export interface Hipotesis {
  id: Id;
  investigacionId: Id;
  titulo: string;
  enunciado: string;
  mecanismo: string;
  /** Que biomarcador o que cohorte permitiria comprobarla. Siempre va. */
  comprobacion: { biomarcador: string; cohorte: string; diseno: string };
  estado: EstadoHipotesis;
  elo: number;
  historialElo: PuntoElo[];
  rivales: Id[];
  novedad: Novedad;
  afirmaciones: Afirmacion[];
  procedencia: Procedencia;
  hallazgos: HallazgoRevisor[];
  revisiones: Revision[];
  creadaEn: number;
  iteracion: number;
  origen: 'rosa' | 'humana';
  derivadaDe: Id | null;
  cluster: string;
  evidenciaEstadistica: 'fuerte' | 'moderada' | 'debil' | 'no_aplica';
  /** Por que importa para el objetivo, en dos lineas, escrito por Rosa. */
  relevancia: { justificacion: string; votoHumano: 'alta' | 'media' | 'baja' | null };
  partidos: Partido[];
  revisionesAutomaticas: RevisionAutomatica[];
  supuestos: Supuesto[];
  revisionesHumanas: RevisionHumana[];
  replicacion: Replicacion | null;
  ultimaRevisionAutomatica: number | null;
  coste: { literatura: number; analisis: number };
  experimento: Experimento | null;
  /** Fecha de la version inmutable (prerregistro) del enunciado. */
  prerregistradaEn: number;
  /** La hipotesis en tres o cuatro frases para quien no es cientifico. */
  enLlano?: string | null;
  /** La conclusion provisional de Rosa con la evidencia reunida. Se rehace
   *  al cerrar cada iteracion. No dice si es cierta: dice cuanto la apoya lo
   *  que hay. */
  conclusion?: ConclusionHipotesis | null;
}

/** Certeza de la evidencia, escala GRADE. */
export type CertezaEvidencia = 'alta' | 'moderada' | 'baja' | 'muy_baja';
/** Hacia donde apunta la evidencia reunida, independiente de la certeza. */
export type DireccionEvidencia = 'apoya' | 'mixta' | 'en_contra' | 'sin_evidencia_directa';

export type FactorCerteza = 'riesgo_de_sesgo' | 'inconsistencia' | 'evidencia_indirecta' | 'imprecision' | 'sesgo_de_publicacion' | 'efecto_grande' | 'gradiente' | 'replicacion_independiente';

export interface ConclusionHipotesis {
  certeza: CertezaEvidencia;
  direccion: DireccionEvidencia;
  conclusion: string;
  /** Por que este grado: los factores GRADE que lo bajaron o subieron. */
  factores: { factor: FactorCerteza; efecto: 'baja' | 'sube' | 'neutro'; explicacion: string }[];
  /** La base contada de forma determinista, no estimada por el modelo. */
  base: { afirmaciones: number; sostenidas: number; fuentes: number; datos: number; interpretaciones: number };
  /** La frase calibrada de (direccion, certeza), generada por regla, no por el modelo. */
  enunciado: string;
  aFavor: string[];
  enContra: string[];
  loMasFragil: string;
  subiria: string;
  bajaria: string;
  /** Fuentes que no respondieron al comprobar la novedad: "no pude comprobar", no "no hay". */
  noComprobado: string[];
  /** Si la certeza o la direccion cambiaron respecto a la conclusion anterior. */
  cambio: { de: { certeza: CertezaEvidencia | null; direccion: DireccionEvidencia | null; iteracion: number | null }; motivo: string } | null;
  fechaBusqueda: number | null;
  fecha: number;
  iteracion: number;
}

/* ---------------------------------------------------------------------
   Modelo de mundo
   --------------------------------------------------------------------- */

export type EstadoHecho = 'sabido' | 'abierto' | 'descartado';
export type TipoHecho = 'hecho' | 'hipotesis' | 'pregunta';

export interface ProcedenciaHecho {
  fuenteId: Id;
  referencia: string;
  pagina: number | null;
}

export type ClasificacionCita = 'apoya' | 'menciona' | 'contrasta';

/** Una cita de otra fuente sobre este hecho, con su clasificacion y la
 *  seccion del articulo donde aparece (patron de Scite). */
export interface CitaSobreHecho {
  referencia: string;
  seccion: string;
  clasificacion: ClasificacionCita;
  fragmento: string;
}

export interface MovimientoHecho {
  fecha: number;
  de: EstadoHecho | null;
  a: EstadoHecho;
  quien: string;
  motivo: string;
}

export interface HechoMundo {
  id: Id;
  investigacionId: Id;
  tipo: TipoHecho;
  tema: string;
  enunciado: string;
  estado: EstadoHecho;
  /** Lo que dice la fuente, separado de lo que infiere Rosa. */
  origen: 'fuente' | 'inferencia';
  procedencia: ProcedenciaHecho[];
  motivoDescarte: string | null;
  actualizadoEn: number;
  prioridad: number;
  citas: CitaSobreHecho[];
  historial: MovimientoHecho[];
}

/* ---------------------------------------------------------------------
   Artefactos
   --------------------------------------------------------------------- */

export type TipoArtefacto = 'informe' | 'tabla' | 'modelo_mundo' | 'figura' | 'cuaderno' | 'specific_aims';

export interface VersionArtefacto {
  n: number;
  creadaEn: number;
  resumen: string;
  contenido: string;
  iteracion: number;
}

export interface Artefacto {
  id: Id;
  investigacionId: Id;
  nombre: string;
  tipo: TipoArtefacto;
  versiones: VersionArtefacto[];
  destacado: boolean;
}

/* ---------------------------------------------------------------------
   Calidad
   --------------------------------------------------------------------- */

export type CategoriaCaso = 'single_hop' | 'multi_hop' | 'tabla' | 'abstencion' | 'entidad';
export type EstadoCaso = 'propuesto' | 'aprobado' | 'descartado';

export interface CasoControl {
  clave: string;
  categoria: CategoriaCaso;
  pregunta: string;
  respuestaEsperada: string;
  estado: EstadoCaso;
  critico: boolean;
  origen: 'generado' | 'humano';
}

export interface MetricasJuez {
  fecha: number;
  juez: string;
  casos: number;
  acuerdoConHumanos: number;
  sostenidas: number;
  cobertura: number;
  ausenciasRefutadas: number;
  entidadDistinta: number;
  /** Cuantas veces dijo "sin verificar" cuando no sabia. Se mide aparte. */
  sinVerificar: number;
  /** Acierto por tipo de afirmacion, verificado por humanos. */
  aciertoPorTipo: Record<TipoAfirmacion, number | null>;
}

export interface CorridaGepa {
  id: Id;
  fecha: number;
  programa: string;
  presupuesto: 'light' | 'medium' | 'heavy';
  metricaInicial: number;
  metricaFinal: number;
  candidatos: number;
  enlaceMlflow: string;
  estado: 'en_marcha' | 'terminada' | 'fallida';
}

/* ---------------------------------------------------------------------
   Ajustes
   --------------------------------------------------------------------- */

export interface Recuerdo {
  id: Id;
  texto: string;
  creadoEn: number;
}

export interface Avisos {
  correo: { activo: boolean; direccion: string };
  slack: { activo: boolean; canal: string };
  cuando: { hipotesisNueva: boolean; permisoPendiente: boolean; corridaDetenida: boolean; resumenDiario: boolean };
}

export type AccionEspera = 'recordar' | 'escalar' | 'detener' | 'continuar';

/** Que pasa con una decision que nadie toma: recordar, escalar a alguien,
 *  detener con seguridad o continuar registrando. Nunca lo decide la
 *  interfaz por accidente. */
export interface PoliticaEsperas {
  horas: number;
  accion: AccionEspera;
  escalarA: string;
}

export interface PlanGuardado {
  id: Id;
  nombre: string;
  pasos: string[];
  vecesUsado: number;
  exitos: number;
}

export type EstadoConexion = 'conectando' | 'en_linea' | 'sin_conexion' | 'muestra';

/* ---------------------------------------------------------------------
   Eventos (para el resumen "mientras no estabas")
   --------------------------------------------------------------------- */

export type TipoEvento =
  | 'iteracion_terminada'
  | 'hipotesis_nueva'
  | 'hipotesis_decidida'
  | 'ranking_cambio'
  | 'permiso_pendiente'
  | 'permiso_resuelto'
  | 'incidencia'
  | 'presupuesto'
  | 'corrida_estado'
  | 'hecho_nuevo'
  | 'retraccion'
  | 'literatura_nueva'
  | 'revision_automatica';

export interface Evento {
  id: Id;
  investigacionId: Id;
  t: number;
  tipo: TipoEvento;
  texto: string;
  /** Hash de la ruta a la que lleva. */
  ruta: string | null;
}

/* ---------------------------------------------------------------------
   Estado completo
   --------------------------------------------------------------------- */

export interface EstadoRosa {
  conexion: EstadoConexion;
  investigaciones: Investigacion[];
  corridas: Corrida[];
  iteraciones: Iteracion[];
  solicitudes: SolicitudPermiso[];
  incidencias: Incidencia[];
  permisos: PermisoConcedido[];
  autonomia: Record<ClaseAccion, NivelAutonomia>;
  hipotesis: Hipotesis[];
  comentarios: Comentario[];
  hechos: HechoMundo[];
  artefactos: Artefacto[];
  casos: CasoControl[];
  metricas: MetricasJuez[];
  gepa: CorridaGepa[];
  memoria: Recuerdo[];
  planesGuardados: PlanGuardado[];
  criteriosRevision: string[];
  avisos: Avisos;
  politicaEsperas: PoliticaEsperas;
  eventos: Evento[];
  /** Ultima vez que la persona abrio Rosa (para "mientras no estabas"). */
  ultimaVisita: number | null;
}
