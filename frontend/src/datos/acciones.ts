// Las acciones de la interfaz como funciones puras sobre el estado: cada
// boton de Rosa llama a una de estas. Devuelven un estado nuevo y no mutan el
// anterior, asi que vitest las prueba sin React y el almacen las aplica tal
// cual. Cuando el almacen real exista, cada una se convierte en una mutacion
// del servidor con la misma firma; las pantallas no cambian.
//
// Reglas del dominio que se hacen cumplir aqui y no en la pantalla:
// - La aprobacion va antes del efecto: aceptar una hipotesis la pasa al
//   modelo de mundo como abierta (para perseguir), nunca como sabida.
// - Descartar exige motivo y deja el rastro en el modelo de mundo.
// - Un permiso concedido con alcance mayor que "una vez" queda listado y se
//   puede revocar en Ajustes.
// - Los comentarios se acumulan como pendientes y salen juntos al enviar.
// - El plan de una iteracion no se ejecuta hasta que se aprueba.
// - El presupuesto global pausa la corrida, no la mata; una pregunta
//   pendiente tiene prioridad sobre el tope.
// - Toda accion relevante deja un evento, para el resumen "mientras no
//   estabas".

import type {
  AlcancePermiso,
  AnclaComentario,
  Avisos,
  ClaseAccion,
  ClasificacionDatos,
  Comentario,
  Corrida,
  Dataset,
  EstadoRosa,
  Evento,
  HechoMundo,
  Hipotesis,
  Investigacion,
  Iteracion,
  NivelAutonomia,
  PasoPlan,
  PoliticaEsperas,
  Revision,
  RevisionHumana,
  TipoArtefacto,
  TipoEvento,
} from './tipos';

let contador = 0;
/** Ids locales. El almacen real los asigna el servidor. */
export function nuevoId(prefijo: string): string {
  contador += 1;
  return `${prefijo}-${Date.now().toString(36)}-${contador}`;
}

function reemplazar<T extends { id: string }>(lista: T[], id: string, cambio: (x: T) => T): T[] {
  return lista.map((x) => (x.id === id ? cambio(x) : x));
}

export function conEvento(estado: EstadoRosa, investigacionId: string, tipo: TipoEvento, texto: string, ruta: string | null, t: number): EstadoRosa {
  const evento: Evento = { id: nuevoId('ev'), investigacionId, t, tipo, texto, ruta };
  return { ...estado, eventos: [...estado.eventos, evento] };
}

export function iteracionActualDe(estado: EstadoRosa, corrida: Corrida): Iteracion | null {
  const propias = estado.iteraciones.filter((i) => i.corridaId === corrida.id);
  if (propias.length === 0) return null;
  return propias.reduce((max, i) => (i.numero > max.numero ? i : max));
}

function corridaDe(estado: EstadoRosa, corridaId: string): Corrida | null {
  return estado.corridas.find((c) => c.id === corridaId) ?? null;
}

/* ---------------------------------------------------------------------
   Visita
   --------------------------------------------------------------------- */

/** Marca que la persona vio el resumen: lo siguiente que pase cuenta como
 *  "mientras no estabas". */
export function marcarVisita(estado: EstadoRosa, ahora: number): EstadoRosa {
  return { ...estado, ultimaVisita: ahora };
}

/* ---------------------------------------------------------------------
   Corrida
   --------------------------------------------------------------------- */

export function pausarCorrida(estado: EstadoRosa, corridaId: string): EstadoRosa {
  return {
    ...estado,
    corridas: reemplazar(estado.corridas, corridaId, (c) => (c.estado === 'en_marcha' ? { ...c, estado: 'pausada' } : c)),
  };
}

export function reanudarCorrida(estado: EstadoRosa, corridaId: string): EstadoRosa {
  return {
    ...estado,
    // Una solicitud pendiente no impide reanudar: Rosa sigue con lo demas y
    // la tarjeta se queda esperando.
    corridas: reemplazar(estado.corridas, corridaId, (c) => (c.estado === 'pausada' ? { ...c, estado: 'en_marcha' } : c)),
  };
}

export function detenerCorrida(estado: EstadoRosa, corridaId: string, motivo: string, ahora: number, vigilarLiteraturaDias: number | null = null): EstadoRosa {
  const texto = motivo.trim() === '' ? 'Detenida por la investigadora.' : motivo.trim();
  const corrida = corridaDe(estado, corridaId);
  if (!corrida || corrida.estado === 'detenida' || corrida.estado === 'terminada') return estado;
  let siguiente: EstadoRosa = {
    ...estado,
    corridas: reemplazar(estado.corridas, corridaId, (c) => ({ ...c, estado: 'detenida', terminadaEn: ahora, motivoCierre: texto })),
  };
  if (vigilarLiteraturaDias !== null && vigilarLiteraturaDias > 0) {
    siguiente = {
      ...siguiente,
      investigaciones: reemplazar(siguiente.investigaciones, corrida.investigacionId, (i) => ({ ...i, vigilarLiteraturaHasta: ahora + vigilarLiteraturaDias * 86_400_000 })),
    };
  }
  return conEvento(siguiente, corrida.investigacionId, 'corrida_estado', `Corrida ${corrida.numero} detenida: ${texto}`, null, ahora);
}

/** Ampliar el tope de llamadas de la corrida; si estaba pausada por
 *  presupuesto, vuelve a marchar. */
export function ampliarPresupuesto(estado: EstadoRosa, corridaId: string, nuevoLimite: number, ahora: number): EstadoRosa {
  const corrida = corridaDe(estado, corridaId);
  if (!corrida || !Number.isFinite(nuevoLimite) || nuevoLimite <= corrida.gasto.llamadas) return estado;
  const siguiente: EstadoRosa = {
    ...estado,
    corridas: reemplazar(estado.corridas, corridaId, (c) => ({
      ...c,
      presupuesto: { ...c.presupuesto, limiteLlamadas: Math.round(nuevoLimite), avisadas: c.presupuesto.avisadas.filter((a) => c.gasto.llamadas / nuevoLimite >= a) },
      estado: c.estado === 'pausada_por_presupuesto' ? 'en_marcha' : c.estado,
    })),
  };
  return conEvento(siguiente, corrida.investigacionId, 'presupuesto', `Presupuesto ampliado a ${Math.round(nuevoLimite)} llamadas`, null, ahora);
}

/** Una indicacion de la investigadora entra al plan de la iteracion en
 *  curso, justo despues del paso actual, marcada como humana. */
export function dirigirCorrida(estado: EstadoRosa, corridaId: string, texto: string): EstadoRosa {
  const limpio = texto.trim();
  if (limpio === '') return estado;
  const corrida = corridaDe(estado, corridaId);
  if (!corrida) return estado;
  const iteracion = iteracionActualDe(estado, corrida);
  if (!iteracion) return estado;
  const paso: PasoPlan = { id: nuevoId('paso'), titulo: 'Indicacion de la investigadora', detalle: limpio, estado: 'pendiente', indicacionHumana: true, motivoFallo: null, presupuesto: null };
  const idx = iteracion.plan.findIndex((p) => p.estado === 'en_curso');
  const plan = [...iteracion.plan];
  plan.splice(idx === -1 ? plan.length : idx + 1, 0, paso);
  return { ...estado, iteraciones: reemplazar(estado.iteraciones, iteracion.id, (it) => ({ ...it, plan })) };
}

/** Editar el plan de una iteracion que aun no se aprobo: reordenar, quitar,
 *  anadir o cambiar el presupuesto de un paso. Un plan aprobado no se edita:
 *  se dirige. */
export function editarPlan(estado: EstadoRosa, iteracionId: string, plan: PasoPlan[]): EstadoRosa {
  const it = estado.iteraciones.find((i) => i.id === iteracionId);
  if (!it || it.planAprobado) return estado;
  const limpio = plan.filter((p) => p.titulo.trim() !== '');
  if (limpio.length === 0) return estado;
  return { ...estado, iteraciones: reemplazar(estado.iteraciones, iteracionId, (i) => ({ ...i, plan: limpio })) };
}

export function aprobarPlan(estado: EstadoRosa, iteracionId: string, ahora: number): EstadoRosa {
  const it = estado.iteraciones.find((i) => i.id === iteracionId);
  if (!it || it.planAprobado) return estado;
  const corrida = corridaDe(estado, it.corridaId);
  const siguiente: EstadoRosa = {
    ...estado,
    iteraciones: reemplazar(estado.iteraciones, iteracionId, (i) => ({ ...i, planAprobado: true, empezadaEn: ahora })),
    corridas: reemplazar(estado.corridas, it.corridaId, (c) => (c.estado === 'esperando_plan' ? { ...c, estado: 'en_marcha' } : c)),
  };
  return corrida ? conEvento(siguiente, corrida.investigacionId, 'corrida_estado', `Plan de la iteracion ${it.numero} aprobado`, null, ahora) : siguiente;
}

export function fijarAutoaprobacionPlan(estado: EstadoRosa, corridaId: string, segundos: number | null): EstadoRosa {
  return { ...estado, corridas: reemplazar(estado.corridas, corridaId, (c) => ({ ...c, autoAprobarPlanSegundos: segundos })) };
}

/** Parar una pista sin parar la corrida (Claude Science no lo permite). */
export function detenerPista(estado: EstadoRosa, pistaId: string, indicacion: string): EstadoRosa {
  const nota = indicacion.trim();
  return {
    ...estado,
    iteraciones: estado.iteraciones.map((it) => ({
      ...it,
      pistas: it.pistas.map((p) =>
        p.id === pistaId && p.estado === 'en_curso'
          ? {
              ...p,
              estado: 'detenida',
              resumen: nota === '' ? 'Detenida por la investigadora' : `Detenida: ${nota}`,
              transcripcion: [...p.transcripcion, { t: p.transcripcion.length * 2_500, tipo: 'nota' as const, texto: nota === '' ? 'Detenida por la investigadora.' : `Detenida por la investigadora: ${nota}` }],
            }
          : p,
      ),
    })),
  };
}

/** Parar un proceso de computo con una indicacion que vuelve a Rosa. */
export function detenerProceso(estado: EstadoRosa, corridaId: string, procesoId: string, indicacion: string): EstadoRosa {
  const corrida = corridaDe(estado, corridaId);
  if (!corrida) return estado;
  let siguiente: EstadoRosa = {
    ...estado,
    corridas: reemplazar(estado.corridas, corridaId, (c) => ({ ...c, procesos: c.procesos.map((p) => (p.id === procesoId ? { ...p, estado: 'detenido' as const, cpu: 0, memoriaMb: 0 } : p)) })),
  };
  if (indicacion.trim() !== '') siguiente = dirigirCorrida(siguiente, corridaId, `Proceso detenido por la investigadora: ${indicacion.trim()}`);
  return siguiente;
}

/** Volver a un punto: una iteracion nueva que retoma el plan de una anterior
 *  (pasos a pendiente) y, si se pide, quita del modelo de mundo lo que Rosa
 *  anadio despues. La corrida original se conserva en el historial. */
export function volverAIteracion(estado: EstadoRosa, iteracionId: string, que: 'plan' | 'mundo' | 'ambos', ahora: number): EstadoRosa {
  const origen = estado.iteraciones.find((i) => i.id === iteracionId);
  if (!origen || origen.terminadaEn === null) return estado;
  const corrida = corridaDe(estado, origen.corridaId);
  if (!corrida) return estado;
  const actual = iteracionActualDe(estado, corrida);
  const numero = (actual?.numero ?? origen.numero) + 1;
  const base = que === 'mundo' ? actual?.plan ?? origen.plan : origen.plan;
  const plan: PasoPlan[] = base.map((p) => ({ ...p, id: nuevoId('paso'), estado: 'pendiente' as const, motivoFallo: null }));
  const nueva: Iteracion = {
    id: nuevoId('it'),
    corridaId: corrida.id,
    numero,
    empezadaEn: ahora,
    terminadaEn: null,
    plan,
    planAprobado: false,
    planPropuestoEn: ahora,
    pistas: [],
    presupuesto: { limite: origen.presupuesto.limite, usado: 0 },
    resumen: '',
  };
  const iteraciones = [
    ...estado.iteraciones.map((i) => (i.id === actual?.id && i.terminadaEn === null ? { ...i, terminadaEn: ahora, resumen: i.resumen || `Cerrada al volver a la iteracion ${origen.numero}` } : i)),
    nueva,
  ];
  let hechos = estado.hechos;
  if (que === 'mundo' || que === 'ambos') {
    const limite = origen.terminadaEn;
    hechos = estado.hechos.filter((h) => !(h.investigacionId === corrida.investigacionId && h.actualizadoEn > limite && h.historial.every((m) => m.quien === 'Rosa')));
  }
  const siguiente: EstadoRosa = {
    ...estado,
    iteraciones,
    hechos,
    corridas: reemplazar(estado.corridas, corrida.id, (c) => ({ ...c, iteracionActual: numero, estado: c.estado === 'en_marcha' || c.estado === 'esperando_plan' ? 'esperando_plan' : c.estado })),
  };
  return conEvento(siguiente, corrida.investigacionId, 'corrida_estado', `Se volvio a la iteracion ${origen.numero} (${que}); la ${numero} espera tu aprobacion del plan`, null, ahora);
}

/* ---------------------------------------------------------------------
   Permisos, incidencias y autonomia
   --------------------------------------------------------------------- */

export function resolverSolicitud(
  estado: EstadoRosa,
  solicitudId: string,
  decision: 'conceder' | 'denegar',
  alcance: AlcancePermiso | null,
  ahora: number,
  argumentos?: Record<string, string>,
): EstadoRosa {
  const solicitud = estado.solicitudes.find((s) => s.id === solicitudId);
  if (!solicitud || solicitud.estado !== 'pendiente') return estado;
  if (decision === 'conceder' && (alcance === null || !solicitud.alcances.includes(alcance))) return estado;
  const corrida = corridaDe(estado, solicitud.corridaId);

  let siguiente: EstadoRosa = {
    ...estado,
    solicitudes: reemplazar(estado.solicitudes, solicitudId, (s) => ({
      ...s,
      estado: decision === 'conceder' ? 'concedida' : 'denegada',
      alcanceConcedido: decision === 'conceder' ? alcance : null,
      resueltaEn: ahora,
      argumentos: argumentos ? s.argumentos.map((a) => (a.editable && argumentos[a.nombre] !== undefined ? { ...a, valor: argumentos[a.nombre]!.trim() || a.valor } : a)) : s.argumentos,
    })),
  };

  if (decision === 'conceder' && alcance !== null && alcance !== 'una_vez') {
    siguiente = {
      ...siguiente,
      permisos: [
        ...siguiente.permisos,
        {
          id: nuevoId('per'),
          tipo: solicitud.tipo,
          recurso: solicitud.recurso,
          alcance,
          concedidoEn: ahora,
          investigacionId: alcance === 'siempre' ? null : corrida?.investigacionId ?? null,
        },
      ],
    };
  }

  if (solicitud.tipo === 'aceptar_hipotesis' && solicitud.hipotesisId && decision === 'conceder') {
    siguiente = revisarHipotesis(siguiente, solicitud.hipotesisId, 'aceptar', 'Aceptada desde la tarjeta de permiso', 'Investigadora', ahora, false);
  }

  const quedan = siguiente.solicitudes.some((s) => s.corridaId === solicitud.corridaId && s.estado === 'pendiente');
  siguiente = {
    ...siguiente,
    corridas: reemplazar(siguiente.corridas, solicitud.corridaId, (c) => (c.estado === 'esperando_aprobacion' && !quedan ? { ...c, estado: 'en_marcha' } : c)),
  };
  return corrida ? conEvento(siguiente, corrida.investigacionId, 'permiso_resuelto', `${decision === 'conceder' ? 'Permitido' : 'Denegado'}: ${solicitud.recurso}`, null, ahora) : siguiente;
}

/** Varias solicitudes a la vez con el mismo alcance. Las que no lo ofrecen se saltan. */
export function resolverSolicitudes(estado: EstadoRosa, ids: string[], decision: 'conceder' | 'denegar', alcance: AlcancePermiso | null, ahora: number): EstadoRosa {
  let e = estado;
  for (const id of ids) {
    const s = e.solicitudes.find((x) => x.id === id);
    if (!s) continue;
    if (decision === 'conceder' && alcance !== null && !s.alcances.includes(alcance)) continue;
    e = resolverSolicitud(e, id, decision, alcance, ahora);
  }
  return e;
}

export function revocarPermiso(estado: EstadoRosa, permisoId: string): EstadoRosa {
  return { ...estado, permisos: estado.permisos.filter((p) => p.id !== permisoId) };
}

export function resolverIncidencia(estado: EstadoRosa, incidenciaId: string, resolucion: string, ahora: number): EstadoRosa {
  const inc = estado.incidencias.find((i) => i.id === incidenciaId);
  if (!inc || inc.estado !== 'pendiente') return estado;
  const texto = resolucion.trim() === '' ? inc.alternativa ?? 'Resuelta por la investigadora' : resolucion.trim();
  const corrida = corridaDe(estado, inc.corridaId);
  const siguiente: EstadoRosa = {
    ...estado,
    incidencias: reemplazar(estado.incidencias, incidenciaId, (i) => ({ ...i, estado: 'resuelta', resueltaEn: ahora, resolucion: texto })),
  };
  return corrida ? conEvento(siguiente, corrida.investigacionId, 'incidencia', `Incidencia resuelta: ${inc.titulo} (${texto})`, null, ahora) : siguiente;
}

export function fijarAutonomia(estado: EstadoRosa, clase: ClaseAccion, nivel: NivelAutonomia): EstadoRosa {
  return { ...estado, autonomia: { ...estado.autonomia, [clase]: nivel } };
}

/** Si se han concedido tres o mas permisos del mismo tipo con alcance amplio,
 *  Rosa puede proponer una regla. Devuelve las sugerencias. */
export function sugerenciasDeAutonomia(estado: EstadoRosa): { tipo: string; veces: number }[] {
  const cuenta = new Map<string, number>();
  for (const p of estado.permisos) if (p.alcance === 'siempre' || p.alcance === 'esta_investigacion') cuenta.set(p.tipo, (cuenta.get(p.tipo) ?? 0) + 1);
  return [...cuenta.entries()].filter(([, n]) => n >= 3).map(([tipo, veces]) => ({ tipo, veces }));
}

/* ---------------------------------------------------------------------
   Hipotesis
   --------------------------------------------------------------------- */

export type AccionRevision = 'aceptar' | 'descartar' | 'refinar' | 'reabrir' | 'no_puedo_juzgar';

const ESTADO_TRAS_ACCION: Record<AccionRevision, Hipotesis['estado']> = {
  aceptar: 'aceptada',
  descartar: 'descartada',
  refinar: 'refinar',
  reabrir: 'en_revision',
  no_puedo_juzgar: 'aclarando',
};

const ACCION_REVISION: Record<AccionRevision, Revision['accion']> = {
  aceptar: 'aceptada',
  descartar: 'descartada',
  refinar: 'refinar',
  reabrir: 'reabierta',
  no_puedo_juzgar: 'no_puedo_juzgar',
};

export function revisarHipotesis(
  estado: EstadoRosa,
  hipotesisId: string,
  accion: AccionRevision,
  nota: string,
  quien: string,
  ahora: number,
  aCiegas = false,
  revisionHumana: Omit<RevisionHumana, 'fecha' | 'quien'> | null = null,
): EstadoRosa {
  const h = estado.hipotesis.find((x) => x.id === hipotesisId);
  if (!h) return estado;
  const notaLimpia = nota.trim();
  // Descartar y "no puedo juzgar" exigen motivo: es lo que queda para que
  // nadie vuelva a proponer lo mismo, o lo que Rosa tiene que aclarar.
  if ((accion === 'descartar' || accion === 'no_puedo_juzgar') && notaLimpia === '') return estado;

  const revision: Revision = { fecha: ahora, quien, accion: ACCION_REVISION[accion], nota: notaLimpia, aCiegas };
  const mensajes = notaLimpia === '' ? h.procedencia.mensajes : [...h.procedencia.mensajes, { id: nuevoId('m'), de: 'investigadora' as const, texto: notaLimpia, creadoEn: ahora }];
  const tieneRevision = revisionHumana !== null && (revisionHumana.supuestosCuestionados.trim() !== '' || revisionHumana.literaturaQueFalta.trim() !== '' || revisionHumana.problemaExperimental.trim() !== '');
  const revisionesHumanas = tieneRevision && revisionHumana ? [...h.revisionesHumanas, { ...revisionHumana, fecha: ahora, quien }] : h.revisionesHumanas;

  const hipotesis = reemplazar(estado.hipotesis, hipotesisId, (x) => ({
    ...x,
    estado: ESTADO_TRAS_ACCION[accion],
    revisiones: [...x.revisiones, revision],
    revisionesHumanas,
    procedencia: { ...x.procedencia, mensajes },
  }));

  const sinEntrada = estado.hechos.filter((e) => !(e.tipo === 'hipotesis' && e.id === `he-${hipotesisId}`));
  let hechos = sinEntrada;
  if (accion === 'aceptar' || accion === 'descartar') {
    const entrada: HechoMundo = {
      id: `he-${hipotesisId}`,
      investigacionId: h.investigacionId,
      tipo: 'hipotesis',
      tema: 'Revision humana',
      enunciado: accion === 'aceptar' ? `Hipotesis aceptada para perseguir: ${h.titulo}` : h.titulo,
      estado: accion === 'aceptar' ? 'abierto' : 'descartado',
      origen: 'inferencia',
      procedencia: h.procedencia.fuentes.map((f) => ({ fuenteId: f.id, referencia: f.referencia, pagina: f.pagina })),
      motivoDescarte: accion === 'descartar' ? `${notaLimpia} (${quien})` : null,
      actualizadoEn: ahora,
      prioridad: accion === 'aceptar' ? 1 : 9,
      citas: [],
      historial: [{ fecha: ahora, de: null, a: accion === 'aceptar' ? 'abierto' : 'descartado', quien, motivo: notaLimpia || (accion === 'aceptar' ? 'Aceptada' : 'Descartada') }],
    };
    hechos = [...sinEntrada, entrada];
  }
  const siguiente = { ...estado, hipotesis, hechos };
  const textos: Record<AccionRevision, string> = {
    aceptar: `Aceptada: ${h.titulo}`,
    descartar: `Descartada: ${h.titulo}`,
    refinar: `Pedida refinacion: ${h.titulo}`,
    reabrir: `Reabierta: ${h.titulo}`,
    no_puedo_juzgar: `Marcada como "no puedo juzgar": ${h.titulo}`,
  };
  return conEvento(siguiente, h.investigacionId, 'hipotesis_decidida', textos[accion], `#/investigaciones/${h.investigacionId}/hipotesis/${h.id}`, ahora);
}

/** Rosa responde a un "no puedo juzgar": aclara y la devuelve a revision.
 *  Lo dispara la simulacion; en produccion, el bucle. */
export function aclararHipotesis(estado: EstadoRosa, hipotesisId: string, aclaracion: string, ahora: number): EstadoRosa {
  const h = estado.hipotesis.find((x) => x.id === hipotesisId);
  if (!h || h.estado !== 'aclarando') return estado;
  return {
    ...estado,
    hipotesis: reemplazar(estado.hipotesis, hipotesisId, (x) => ({
      ...x,
      estado: 'en_revision',
      revisiones: [...x.revisiones, { fecha: ahora, quien: 'Rosa', accion: 'aclarada', nota: aclaracion, aCiegas: false }],
      procedencia: { ...x.procedencia, mensajes: [...x.procedencia.mensajes, { id: nuevoId('m'), de: 'rosa' as const, texto: aclaracion, creadoEn: ahora }] },
    })),
  };
}

export function votarRelevancia(estado: EstadoRosa, hipotesisId: string, voto: 'alta' | 'media' | 'baja'): EstadoRosa {
  return { ...estado, hipotesis: reemplazar(estado.hipotesis, hipotesisId, (h) => ({ ...h, relevancia: { ...h.relevancia, votoHumano: voto } })) };
}

/** Pedir una revision automatica ahora. Deja el rastro; en produccion la
 *  hace el revisor del bucle. */
export function solicitarRevision(estado: EstadoRosa, hipotesisId: string, ahora: number): EstadoRosa {
  const h = estado.hipotesis.find((x) => x.id === hipotesisId);
  if (!h) return estado;
  const siguiente: EstadoRosa = {
    ...estado,
    hipotesis: reemplazar(estado.hipotesis, hipotesisId, (x) => ({
      ...x,
      ultimaRevisionAutomatica: ahora,
      revisionesAutomaticas: x.revisionesAutomaticas.map((r) => (r.estado === 'pendiente' ? { ...r, estado: 'hecha' as const, fecha: ahora, resumen: 'Revisada a peticion de la investigadora: sin hallazgos nuevos.' } : r)),
      procedencia: { ...x.procedencia, mensajes: [...x.procedencia.mensajes, { id: nuevoId('m'), de: 'revisor' as const, texto: 'Revision pedida por la investigadora: releidas las afirmaciones, el plan y el registro. Sin hallazgos nuevos.', creadoEn: ahora }] },
    })),
  };
  return conEvento(siguiente, h.investigacionId, 'revision_automatica', `Revision pedida sobre: ${h.titulo}`, `#/investigaciones/${h.investigacionId}/hipotesis/${h.id}`, ahora);
}

/** Replicar la hipotesis con N trayectorias independientes. Gasta presupuesto;
 *  la simulacion avanza las trayectorias. */
export function replicarHipotesis(estado: EstadoRosa, hipotesisId: string, total: number, ahora: number): EstadoRosa {
  const h = estado.hipotesis.find((x) => x.id === hipotesisId);
  if (!h || (h.replicacion && h.replicacion.estado === 'en_curso') || total < 2) return estado;
  const siguiente: EstadoRosa = {
    ...estado,
    hipotesis: reemplazar(estado.hipotesis, hipotesisId, (x) => ({
      ...x,
      replicacion: { total, hechas: 0, sostienen: 0, contradicen: 0, estado: 'en_curso', empezadaEn: ahora },
      revisiones: [...x.revisiones, { fecha: ahora, quien: 'Investigadora', accion: 'replicada', nota: `${total} trayectorias independientes`, aCiegas: false }],
      coste: { ...x.coste, analisis: x.coste.analisis + total * 1.2 },
    })),
  };
  return conEvento(siguiente, h.investigacionId, 'revision_automatica', `Replicacion x${total} lanzada sobre: ${h.titulo}`, `#/investigaciones/${h.investigacionId}/hipotesis/${h.id}`, ahora);
}

export interface DatosHipotesisHumana {
  titulo: string;
  enunciado: string;
  mecanismo: string;
  biomarcador: string;
  cohorte: string;
  diseno: string;
  cluster: string;
}

/** La investigadora mete su propia hipotesis al torneo. Entra con Elo
 *  inicial, marcada como humana, y Rosa la trata como a las demas. */
export function proponerHipotesis(estado: EstadoRosa, investigacionId: string, datos: DatosHipotesisHumana, quien: string, ahora: number): { estado: EstadoRosa; id: string | null } {
  if (datos.titulo.trim() === '' || datos.enunciado.trim() === '' || (datos.biomarcador.trim() === '' && datos.cohorte.trim() === '')) return { estado, id: null };
  const corrida = estado.corridas.filter((c) => c.investigacionId === investigacionId).sort((a, b) => b.numero - a.numero)[0];
  const iteracion = corrida?.iteracionActual ?? 0;
  const id = nuevoId('hip');
  const h: Hipotesis = {
    id,
    investigacionId,
    titulo: datos.titulo.trim(),
    enunciado: datos.enunciado.trim(),
    mecanismo: datos.mecanismo.trim(),
    comprobacion: { biomarcador: datos.biomarcador.trim(), cohorte: datos.cohorte.trim(), diseno: datos.diseno.trim() },
    estado: 'propuesta',
    elo: 1_500,
    historialElo: [{ iteracion, elo: 1_500 }],
    rivales: [],
    novedad: {
      openTargets: { estado: 'sin_evidencia', detalle: 'Pendiente de comprobar en la siguiente iteracion' },
      ensayos: { estado: 'sin_ensayo', detalle: 'Pendiente de comprobar', nct: null },
      agora: { estado: 'no_nominada', detalle: 'Pendiente de comprobar' },
      precedente: { estado: 'sin_precedente', detalle: 'Pendiente de comprobar' },
    },
    afirmaciones: [],
    procedencia: {
      mensajes: [{ id: nuevoId('m'), de: 'investigadora', texto: `Hipotesis propuesta por ${quien}. Rosa la revisara y la metera al torneo en la siguiente iteracion.`, creadoEn: ahora }],
      codigo: '',
      registro: [`${new Date(ahora).toISOString()} hipotesis humana anadida por ${quien}`],
      entorno: { lenguaje: 'Python', version: '3.12.14', paquetes: [], modelos: [] },
      fuentes: [],
    },
    hallazgos: [],
    revisiones: [{ fecha: ahora, quien, accion: 'propuesta', nota: 'Propuesta por una persona', aCiegas: false }],
    creadaEn: ahora,
    iteracion,
    origen: 'humana',
    derivadaDe: null,
    cluster: datos.cluster.trim() || 'Sin cluster',
    evidenciaEstadistica: 'no_aplica',
    relevancia: { justificacion: 'Propuesta por la investigadora; Rosa la justificara al revisarla.', votoHumano: 'alta' },
    partidos: [],
    revisionesAutomaticas: (['inicial', 'completa', 'profunda', 'observacion', 'simulacion', 'torneo'] as const).map((tipo) => ({ tipo, estado: 'pendiente' as const, resumen: '', fecha: null })),
    supuestos: [],
    revisionesHumanas: [],
    replicacion: null,
    ultimaRevisionAutomatica: null,
    coste: { literatura: 0, analisis: 0 },
    experimento: null,
    prerregistradaEn: ahora,
  };
  const siguiente = conEvento({ ...estado, hipotesis: [...estado.hipotesis, h] }, investigacionId, 'hipotesis_nueva', `Hipotesis propuesta por ${quien}: ${h.titulo}`, `#/investigaciones/${investigacionId}/hipotesis/${id}`, ahora);
  return { estado: siguiente, id };
}

/* ---------------------------------------------------------------------
   Experimentos (traspaso al laboratorio)
   --------------------------------------------------------------------- */

/** Asignar el experimento a un laboratorio lo prerregistra: la hipotesis, el
 *  protocolo y los criterios quedan congelados con fecha en un artefacto,
 *  antes de que exista ningun dato. Misma regla en el servidor. */
export function asignarExperimento(estado: EstadoRosa, hipotesisId: string, laboratorio: string, ahora: number = Date.now()): EstadoRosa {
  const lab = laboratorio.trim();
  const h = estado.hipotesis.find((x) => x.id === hipotesisId);
  if (lab === '' || !h || !h.experimento) return estado;
  let siguiente: EstadoRosa = {
    ...estado,
    hipotesis: reemplazar(estado.hipotesis, hipotesisId, (x) => ({ ...x, experimento: { ...x.experimento!, laboratorio: lab, estado: 'asignado' } })),
  };
  if (!h.experimento.prerregistradoEn) {
    const corrida = estado.corridas.filter((c) => c.investigacionId === h.investigacionId).sort((a, b) => b.numero - a.numero)[0];
    const r = guardarArtefacto(siguiente, h.investigacionId, `Prerregistro: ${h.titulo.slice(0, 80)}`, 'informe', textoPrerregistro(h, lab, ahora, corrida?.arnes), `Congelado al asignarlo a ${lab}`, corrida?.iteracionActual ?? h.iteracion, ahora);
    siguiente = {
      ...r.estado,
      hipotesis: reemplazar(r.estado.hipotesis, hipotesisId, (x) => ({ ...x, experimento: { ...x.experimento!, prerregistradoEn: ahora, prerregistroArtefactoId: r.id } })),
    };
    siguiente = conEvento(siguiente, h.investigacionId, 'hipotesis_decidida', `Experimento prerregistrado y asignado a ${lab}: ${h.titulo}`, `#/investigaciones/${h.investigacionId}/artefactos/${r.id}`, ahora);
  }
  return siguiente;
}

export function textoPrerregistro(h: Hipotesis, laboratorio: string, ahora: number, arnes?: { commit: string; firmas: string; optimizados: string }): string {
  const x = h.experimento!;
  const c = h.comprobacion;
  const k = h.conclusion;
  const fecha = new Date(ahora).toLocaleString('es');
  const lineas = [
    `# Prerregistro: ${h.titulo}`,
    '',
    `Congelado el ${fecha}. Asignado a: ${laboratorio}. Hipotesis ${h.id}, iteracion ${h.iteracion}.`,
    '',
    '## Hipotesis (no se modifica despues de esta fecha)',
    h.enunciado,
    '',
    '## Mecanismo propuesto',
    h.mecanismo,
    '',
    '## Como se comprobara',
    `Biomarcador: ${c.biomarcador}`,
    `Cohorte: ${c.cohorte}`,
    `Diseno: ${c.diseno}`,
    '',
    '## Protocolo',
    x.protocolo,
    '',
    '## Ensayo y criterios fijados de antemano',
    x.ensayo,
    '',
    `## Coste estimado
${x.costeEstimado}`,
  ];
  if (x.analisisPedido) lineas.push('', '## Analisis sobre datos existentes', x.analisisPedido);
  if (k) lineas.push('', '## Estado de la evidencia al prerregistrar', `Certeza: ${k.certeza}. Direccion: ${k.direccion}.`, k.enunciado, `Subiria la certeza si: ${k.subiria}`, `Bajaria si: ${k.bajaria}`);
  if (arnes) lineas.push('', '## Version de Rosa', `Commit ${arnes.commit}, firmas ${arnes.firmas}, programas optimizados: ${arnes.optimizados}.`);
  lineas.push('', 'Lo que se analice fuera de este registro se reporta como exploratorio, separado de lo prerregistrado.');
  return lineas.join('\n');
}

export function registrarDatosExperimento(estado: EstadoRosa, hipotesisId: string, fichero: string, analisis: string): EstadoRosa {
  if (fichero.trim() === '') return estado;
  return {
    ...estado,
    hipotesis: reemplazar(estado.hipotesis, hipotesisId, (h) =>
      h.experimento ? { ...h, experimento: { ...h.experimento, ficheroDatos: fichero.trim(), analisisPedido: analisis.trim(), estado: 'datos_recibidos' } } : h,
    ),
  };
}

/* ---------------------------------------------------------------------
   Comentarios anclados
   --------------------------------------------------------------------- */

export function anadirComentario(estado: EstadoRosa, hipotesisId: string, ancla: AnclaComentario, nota: string, ahora: number): EstadoRosa {
  const notaLimpia = nota.trim();
  if (notaLimpia === '' || ancla.cita.trim() === '') return estado;
  if (notaLimpia.length > 1000) return estado;
  const comentario: Comentario = { id: nuevoId('com'), hipotesisId, ancla, nota: notaLimpia, estado: 'pendiente', creadoEn: ahora };
  return { ...estado, comentarios: [...estado.comentarios, comentario] };
}

export function editarComentario(estado: EstadoRosa, comentarioId: string, nota: string): EstadoRosa {
  const limpia = nota.trim();
  if (limpia === '' || limpia.length > 1000) return estado;
  return { ...estado, comentarios: estado.comentarios.map((c) => (c.id === comentarioId && c.estado === 'pendiente' ? { ...c, nota: limpia } : c)) };
}

export function quitarComentario(estado: EstadoRosa, comentarioId: string): EstadoRosa {
  return { ...estado, comentarios: estado.comentarios.filter((c) => !(c.id === comentarioId && c.estado === 'pendiente')) };
}

export function enviarComentarios(estado: EstadoRosa, hipotesisId: string, mensaje: string, quien: string, ahora: number): EstadoRosa {
  const pendientes = estado.comentarios.filter((c) => c.hipotesisId === hipotesisId && c.estado === 'pendiente');
  const texto = mensaje.trim();
  if (pendientes.length === 0 && texto === '') return estado;
  const lineas = pendientes.map((c) => `Sobre «${c.ancla.cita}»: ${c.nota}`);
  const cuerpo = [texto, ...lineas].filter((l) => l !== '').join('\n');
  const revision: Revision = { fecha: ahora, quien, accion: 'comentada', nota: pendientes.length > 0 ? `${pendientes.length} ${pendientes.length === 1 ? 'comentario' : 'comentarios'}` : 'Mensaje', aCiegas: false };
  return {
    ...estado,
    comentarios: estado.comentarios.map((c) => (c.hipotesisId === hipotesisId && c.estado === 'pendiente' ? { ...c, estado: 'enviado' as const } : c)),
    hipotesis: reemplazar(estado.hipotesis, hipotesisId, (h) => ({
      ...h,
      estado: h.estado === 'propuesta' ? 'en_revision' : h.estado,
      revisiones: [...h.revisiones, revision],
      procedencia: { ...h.procedencia, mensajes: [...h.procedencia.mensajes, { id: nuevoId('m'), de: 'investigadora' as const, texto: cuerpo, creadoEn: ahora }] },
    })),
  };
}

/* ---------------------------------------------------------------------
   Meta-revision y modelo de mundo
   --------------------------------------------------------------------- */

/** Inyectar una debilidad recurrente como criterio de revision. */
export function inyectarDebilidad(estado: EstadoRosa, corridaId: string, debilidadId: string): EstadoRosa {
  const corrida = corridaDe(estado, corridaId);
  const deb = corrida?.metaRevisiones.flatMap((m) => m.debilidades).find((d) => d.id === debilidadId);
  if (!corrida || !deb || deb.inyectada) return estado;
  const criterios = estado.criteriosRevision.includes(deb.texto) ? estado.criteriosRevision : [...estado.criteriosRevision, deb.texto];
  return {
    ...estado,
    criteriosRevision: criterios,
    corridas: reemplazar(estado.corridas, corridaId, (c) => ({
      ...c,
      metaRevisiones: c.metaRevisiones.map((m) => ({ ...m, debilidades: m.debilidades.map((d) => (d.id === debilidadId ? { ...d, inyectada: true } : d)) })),
    })),
  };
}

/** Recomprobar retractaciones: en produccion consulta Crossref y Retraction
 *  Watch; aqui sella la fecha en todas las fuentes de la investigacion. */
export function recomprobarRetracciones(estado: EstadoRosa, investigacionId: string, ahora: number): EstadoRosa {
  const siguiente: EstadoRosa = {
    ...estado,
    hipotesis: estado.hipotesis.map((h) =>
      h.investigacionId === investigacionId ? { ...h, procedencia: { ...h.procedencia, fuentes: h.procedencia.fuentes.map((f) => ({ ...f, retraccionComprobadaEn: ahora })) } } : h,
    ),
  };
  return conEvento(siguiente, investigacionId, 'retraccion', 'Retractaciones recomprobadas contra Crossref y Retraction Watch: sin cambios', null, ahora);
}

function normalizar(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

/** Responder con lo que hay dentro del modelo de mundo, citando nodos. Sin
 *  modelo de lenguaje: busca por palabras y devuelve los nodos que casan. */
export function preguntarAlModeloDeMundo(hechos: HechoMundo[], investigacionId: string, pregunta: string): { respuesta: string; nodos: HechoMundo[] } {
  const palabras = normalizar(pregunta)
    .split(/[^a-z0-9]+/)
    .filter((p) => p.length > 3);
  if (palabras.length === 0) return { respuesta: 'Escribe una pregunta con alguna palabra del dominio.', nodos: [] };
  const puntuados = hechos
    .filter((h) => h.investigacionId === investigacionId)
    .map((h) => {
      const texto = normalizar(`${h.enunciado} ${h.tema} ${h.motivoDescarte ?? ''}`);
      const aciertos = palabras.filter((p) => texto.includes(p)).length;
      return { h, aciertos };
    })
    .filter((x) => x.aciertos > 0)
    .sort((a, b) => b.aciertos - a.aciertos)
    .slice(0, 5);
  if (puntuados.length === 0) return { respuesta: 'El modelo de mundo no tiene nada sobre eso. No lo invento: queda como pregunta abierta si quieres anadirla.', nodos: [] };
  const sabidos = puntuados.filter((x) => x.h.estado === 'sabido');
  const abiertos = puntuados.filter((x) => x.h.estado === 'abierto');
  const descartados = puntuados.filter((x) => x.h.estado === 'descartado');
  const partes: string[] = [];
  if (sabidos.length > 0) partes.push(`Se sabe: ${sabidos.map((x) => `${x.h.enunciado} [${x.h.procedencia.map((p) => `${p.referencia}${p.pagina !== null ? `, pag. ${p.pagina}` : ''}`).join('; ') || 'inferencia de Rosa'}]`).join(' ')}`);
  if (abiertos.length > 0) partes.push(`Esta abierto: ${abiertos.map((x) => x.h.enunciado).join(' ')}`);
  if (descartados.length > 0) partes.push(`Se descarto: ${descartados.map((x) => `${x.h.enunciado} (${x.h.motivoDescarte ?? 'sin motivo registrado'})`).join(' ')}`);
  return { respuesta: partes.join('\n'), nodos: puntuados.map((x) => x.h) };
}

/* ---------------------------------------------------------------------
   Investigaciones y datos
   --------------------------------------------------------------------- */

export interface DatosInvestigacion {
  titulo: string;
  objetivo: string;
  relevancia: string;
  limites: string[];
  condicionParada: string;
  revisores: string[];
  configuracion?: Investigacion['configuracion'];
  /** Investigacion cuyo modelo de mundo se hereda, si se pide. */
  heredarModeloDe?: string | null;
}

export function crearInvestigacion(estado: EstadoRosa, datos: DatosInvestigacion, ahora: number): { estado: EstadoRosa; id: string | null } {
  if (datos.titulo.trim() === '' || datos.objetivo.trim() === '' || datos.condicionParada.trim() === '') return { estado, id: null };
  const id = nuevoId('inv');
  const inv: Investigacion = {
    id,
    titulo: datos.titulo.trim(),
    objetivo: datos.objetivo.trim(),
    relevancia: datos.relevancia.trim(),
    limites: datos.limites.map((l) => l.trim()).filter((l) => l !== ''),
    condicionParada: datos.condicionParada.trim(),
    revisores: datos.revisores.map((r) => r.trim()).filter((r) => r !== ''),
    estado: 'activa',
    creadaEn: ahora,
    ramaDe: null,
    configuracion: datos.configuracion ?? { preferencias: '', atributos: [], restricciones: [] },
    datasets: [],
    vigilarLiteraturaHasta: null,
  };
  let hechos = estado.hechos;
  if (datos.heredarModeloDe) {
    const heredados = estado.hechos.filter((h) => h.investigacionId === datos.heredarModeloDe).map((h) => ({ ...h, id: `${h.id}-${id}`, investigacionId: id }));
    hechos = [...estado.hechos, ...heredados];
  }
  return { estado: { ...estado, investigaciones: [...estado.investigaciones, inv], hechos }, id };
}

export function bifurcarInvestigacion(estado: EstadoRosa, investigacionId: string, motivo: string, ahora: number): { estado: EstadoRosa; id: string | null } {
  const origen = estado.investigaciones.find((i) => i.id === investigacionId);
  if (!origen) return { estado, id: null };
  const id = nuevoId('inv');
  const rama: Investigacion = {
    ...origen,
    id,
    titulo: `${origen.titulo} (rama)`,
    objetivo: motivo.trim() === '' ? origen.objetivo : `${origen.objetivo}\n\nRama: ${motivo.trim()}`,
    creadaEn: ahora,
    ramaDe: origen.id,
    vigilarLiteraturaHasta: null,
  };
  const hechos = estado.hechos
    .filter((h) => h.investigacionId === investigacionId)
    .map((h) => ({ ...h, id: `${h.id}-${id}`, investigacionId: id }));
  return { estado: { ...estado, investigaciones: [...estado.investigaciones, rama], hechos: [...estado.hechos, ...hechos] }, id };
}

export function actualizarConfiguracion(estado: EstadoRosa, investigacionId: string, configuracion: Investigacion['configuracion']): EstadoRosa {
  return {
    ...estado,
    investigaciones: reemplazar(estado.investigaciones, investigacionId, (i) => ({
      ...i,
      configuracion: {
        preferencias: configuracion.preferencias.trim(),
        atributos: configuracion.atributos.map((a) => a.trim()).filter((a) => a !== ''),
        restricciones: configuracion.restricciones.map((r) => r.trim()).filter((r) => r !== ''),
      },
    })),
  };
}

export function anadirDataset(estado: EstadoRosa, investigacionId: string, dataset: Omit<Dataset, 'id' | 'estado'>): EstadoRosa {
  if (dataset.nombre.trim() === '') return estado;
  const d: Dataset = { ...dataset, id: nuevoId('ds'), estado: 'pendiente' };
  return { ...estado, investigaciones: reemplazar(estado.investigaciones, investigacionId, (i) => ({ ...i, datasets: [...i.datasets, d] })) };
}

/** Aprobar el contrato de datos. No se aprueba si quedan columnas sin
 *  diccionario, valores centinela o nombres duplicados: primero se corrigen. */
export function decidirDataset(estado: EstadoRosa, investigacionId: string, datasetId: string, decision: 'aprobado' | 'rechazado'): EstadoRosa {
  const inv = estado.investigaciones.find((i) => i.id === investigacionId);
  const ds = inv?.datasets.find((d) => d.id === datasetId);
  if (!inv || !ds) return estado;
  if (decision === 'aprobado' && (ds.columnasSinDiccionario > 0 || ds.valoresCentinela > 0 || ds.nombresDuplicados > 0)) return estado;
  return { ...estado, investigaciones: reemplazar(estado.investigaciones, investigacionId, (i) => ({ ...i, datasets: i.datasets.map((d) => (d.id === datasetId ? { ...d, estado: decision } : d)) })) };
}

/** Rosa propone un diccionario de columnas y la persona lo aprueba: deja las
 *  columnas sin diccionario en cero. */
export function aprobarDiccionario(estado: EstadoRosa, investigacionId: string, datasetId: string): EstadoRosa {
  return { ...estado, investigaciones: reemplazar(estado.investigaciones, investigacionId, (i) => ({ ...i, datasets: i.datasets.map((d) => (d.id === datasetId ? { ...d, columnasSinDiccionario: 0 } : d)) })) };
}

/** Marcar los centinelas y duplicados como corregidos en el fichero. */
export function corregirDataset(estado: EstadoRosa, investigacionId: string, datasetId: string): EstadoRosa {
  return { ...estado, investigaciones: reemplazar(estado.investigaciones, investigacionId, (i) => ({ ...i, datasets: i.datasets.map((d) => (d.id === datasetId ? { ...d, valoresCentinela: 0, nombresDuplicados: 0 } : d)) })) };
}

export function clasificarDataset(estado: EstadoRosa, investigacionId: string, datasetId: string, clasificacion: ClasificacionDatos): EstadoRosa {
  return { ...estado, investigaciones: reemplazar(estado.investigaciones, investigacionId, (i) => ({ ...i, datasets: i.datasets.map((d) => (d.id === datasetId ? { ...d, clasificacion } : d)) })) };
}

/* ---------------------------------------------------------------------
   Artefactos
   --------------------------------------------------------------------- */

export function destacarArtefacto(estado: EstadoRosa, artefactoId: string): EstadoRosa {
  return { ...estado, artefactos: reemplazar(estado.artefactos, artefactoId, (a) => ({ ...a, destacado: !a.destacado })) };
}

/** Guardar un artefacto nuevo o una version nueva del mismo nombre. */
export function guardarArtefacto(estado: EstadoRosa, investigacionId: string, nombre: string, tipo: TipoArtefacto, contenido: string, resumen: string, iteracion: number, ahora: number): { estado: EstadoRosa; id: string } {
  const existente = estado.artefactos.find((a) => a.investigacionId === investigacionId && a.nombre === nombre);
  if (existente) {
    const n = existente.versiones.length + 1;
    return {
      estado: { ...estado, artefactos: reemplazar(estado.artefactos, existente.id, (a) => ({ ...a, versiones: [...a.versiones, { n, creadaEn: ahora, resumen, contenido, iteracion }] })) },
      id: existente.id,
    };
  }
  const id = nuevoId('art');
  return {
    estado: { ...estado, artefactos: [...estado.artefactos, { id, investigacionId, nombre, tipo, destacado: false, versiones: [{ n: 1, creadaEn: ahora, resumen, contenido, iteracion }] }] },
    id,
  };
}

/* ---------------------------------------------------------------------
   Calidad
   --------------------------------------------------------------------- */

export function cambiarEstadoCaso(estado: EstadoRosa, clave: string, nuevo: 'aprobado' | 'descartado' | 'propuesto'): EstadoRosa {
  return { ...estado, casos: estado.casos.map((c) => (c.clave === clave ? { ...c, estado: nuevo } : c)) };
}

export function editarRespuestaCaso(estado: EstadoRosa, clave: string, respuesta: string): EstadoRosa {
  const limpia = respuesta.trim();
  if (limpia === '' || limpia.length > 2000) return estado;
  return { ...estado, casos: estado.casos.map((c) => (c.clave === clave ? { ...c, respuestaEsperada: limpia } : c)) };
}

/* ---------------------------------------------------------------------
   Ajustes
   --------------------------------------------------------------------- */

export function editarRecuerdo(estado: EstadoRosa, id: string, texto: string): EstadoRosa {
  const limpio = texto.trim();
  if (limpio === '') return estado;
  return { ...estado, memoria: reemplazar(estado.memoria, id, (r) => ({ ...r, texto: limpio })) };
}

export function borrarRecuerdo(estado: EstadoRosa, id: string): EstadoRosa {
  return { ...estado, memoria: estado.memoria.filter((r) => r.id !== id) };
}

export function anadirCriterio(estado: EstadoRosa, texto: string): EstadoRosa {
  const limpio = texto.trim();
  if (limpio === '' || estado.criteriosRevision.includes(limpio)) return estado;
  return { ...estado, criteriosRevision: [...estado.criteriosRevision, limpio] };
}

export function borrarCriterio(estado: EstadoRosa, indice: number): EstadoRosa {
  return { ...estado, criteriosRevision: estado.criteriosRevision.filter((_, i) => i !== indice) };
}

export function actualizarAvisos(estado: EstadoRosa, avisos: Avisos): EstadoRosa {
  return { ...estado, avisos };
}

export function actualizarPoliticaEsperas(estado: EstadoRosa, politica: PoliticaEsperas): EstadoRosa {
  if (!Number.isFinite(politica.horas) || politica.horas <= 0) return estado;
  return { ...estado, politicaEsperas: { ...politica, escalarA: politica.escalarA.trim() } };
}

export function borrarPlanGuardado(estado: EstadoRosa, id: string): EstadoRosa {
  return { ...estado, planesGuardados: estado.planesGuardados.filter((p) => p.id !== id) };
}
