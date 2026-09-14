// El almacen de Rosa: un solo estado, suscripciones, y las acciones que lo
// cambian. Las pantallas leen con `useRosa()` y escriben con `acciones`.
//
// Dos modos:
// - Servidor: al arrancar, `conectar()` pide `/api/estado`. Si responde, el
//   estado viene del servidor y se mantiene al dia por Server-Sent Events
//   (`/api/eventos`), que manda el estado completo en cada cambio. Cada
//   accion se aplica al instante en local con el reducer (acciones.ts) para
//   que la interfaz responda, y se envia al servidor por POST; el servidor
//   aplica la misma regla y su estado sustituye al local en cuanto llega.
// - Muestra: si el servidor no responde, el estado nace de la muestra
//   (muestra.ts) y avanza con la simulacion (simulacion.ts). Las pantallas
//   no distinguen un modo del otro salvo por `estado.conexion`.

import { useSyncExternalStore } from 'react';
import * as A from './acciones';
import { descargar } from '../componentes/piezas';
import type { CostesInvestigacion } from '../componentes/Rosa2018';
import { estadoDeMuestra } from './muestra';
import { iniciarSimulacion } from './simulacion';
import type {
  AlcancePermiso,
  AnclaComentario,
  Avisos,
  ClaseAccion,
  ClasificacionDatos,
  Dataset,
  EstadoRosa,
  Investigacion,
  MetodoRegistrado,
  NivelAutonomia,
  PasoPlan,
  PoliticaEsperas,
  PreguntaCampana,
  ProcedenciaDataset,
  RevisionHumana,
  TipoArtefacto, CampoEnmendable, EstadoArea, NivelPermisoConector, EstadoEspejo, ConocimientoOperativo } from './tipos';

const CLAVE_VISITA = 'rosa-ultima-visita';
const API = '/api';

/** Token de acceso opcional (solo cuando el servidor escucha fuera de la
 *  maquina). Llega en la URL (?token=...) una vez y se guarda en el navegador. */
function tokenAcceso(): string | null {
  try {
    const enUrl = new URLSearchParams(window.location.search).get('token');
    if (enUrl) {
      localStorage.setItem('rosaToken', enUrl);
      return enUrl;
    }
    return localStorage.getItem('rosaToken');
  } catch {
    return null;
  }
}

/** Cabeceras de toda escritura: X-Rosa marca que viene de la interfaz (una
 *  pagina ajena no puede mandarla sin que el navegador la bloquee) y el token
 *  si existe. */
function cabeceras(json = true): Record<string, string> {
  const h: Record<string, string> = { 'X-Rosa': '1' };
  if (json) h['Content-Type'] = 'application/json';
  const t = tokenAcceso();
  if (t) h['X-Rosa-Token'] = t;
  return h;
}

function conToken(url: string): string {
  const t = tokenAcceso();
  return t ? `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(t)}` : url;
}

function leerVisita(): number | null {
  try {
    const v = localStorage.getItem(CLAVE_VISITA);
    return v ? Number(v) : null;
  } catch {
    return null;
  }
}

let estado: EstadoRosa = (() => {
  const base = estadoDeMuestra();
  const visita = leerVisita();
  return visita !== null ? { ...base, ultimaVisita: visita } : base;
})();
const oyentes = new Set<() => void>();
let modo: 'muestra' | 'servidor' = 'muestra';

function leer(): EstadoRosa {
  return estado;
}

function suscribir(oyente: () => void): () => void {
  oyentes.add(oyente);
  return () => oyentes.delete(oyente);
}

function notificar(): void {
  for (const o of oyentes) o();
}

/** Aplica un cambio puro. Si devuelve el mismo objeto, nadie se entera. */
export function aplicar(fn: (e: EstadoRosa) => EstadoRosa): void {
  const siguiente = fn(estado);
  if (siguiente === estado) return;
  estado = siguiente;
  notificar();
}

/** El estado completo, reactivo. Las pantallas derivan de aqui con useMemo. */
export function useRosa(): EstadoRosa {
  return useSyncExternalStore(suscribir, leer, leer);
}

/** Quien firma las revisiones. Cuando haya cuentas, sale de la sesion. */
export const QUIEN = 'la persona responsable';

export function modoActual(): 'muestra' | 'servidor' {
  return modo;
}

/* ---------------------------------------------------------------------
   Conexion con el servidor
   --------------------------------------------------------------------- */

/** Version del estado del servidor que ya se pinto (llega como `id` del
 *  evento SSE y como cabecera X-Rosa-Version en /estado). Sirve para no
 *  pisar un estado nuevo con la respuesta tardia de una peticion vieja. */
let versionRemota = -1;

function recibirRemoto(remoto: EstadoRosa, version: number | null = null): void {
  const visita = leerVisita();
  estado = { ...remoto, conexion: 'en_linea', ultimaVisita: visita ?? remoto.ultimaVisita };
  if (version !== null) versionRemota = version;
  notificar();
}

function versionDe(texto: string | null | undefined): number | null {
  if (texto === null || texto === undefined || texto === '') return null;
  const n = Number(texto);
  return Number.isFinite(n) ? n : null;
}

/* ---------------------------------------------------------------------
   Acciones diferidas con deshacer. Una decision con peso (aceptar, descartar,
   refinar una hipotesis) se aplica al instante en pantalla y viaja al
   servidor unos segundos despues; mientras, se puede deshacer. Si el estado
   cambio entre medias (llego algo por SSE), deshacer recarga del servidor en
   vez de restaurar una copia vieja.
   --------------------------------------------------------------------- */

export interface AccionPendiente {
  id: string;
  etiqueta: string;
  hasta: number;
  ms: number;
  enviar: () => void;
  deshacer: () => void;
}

let pendientes: AccionPendiente[] = [];
const oyentesPendientes = new Set<() => void>();

function avisarPendientes(): void {
  for (const o of oyentesPendientes) o();
}

export function useAccionesPendientes(): AccionPendiente[] {
  return useSyncExternalStore(
    (o) => {
      oyentesPendientes.add(o);
      return () => oyentesPendientes.delete(o);
    },
    () => pendientes,
    () => pendientes,
  );
}

export const MS_DESHACER = 6000;

function programar(etiqueta: string, aplicarLocal: () => void, enviarServidor: () => void, ms = MS_DESHACER): void {
  const antes = estado;
  aplicarLocal();
  const despues = estado;
  const id = `pend-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e6).toString(36)}`;
  const quitar = () => {
    pendientes = pendientes.filter((p) => p.id !== id);
    avisarPendientes();
  };
  const timer = window.setTimeout(() => {
    enviarServidor();
    quitar();
  }, ms);
  pendientes = [
    ...pendientes,
    {
      id,
      etiqueta,
      hasta: Date.now() + ms,
      ms,
      enviar: () => {
        window.clearTimeout(timer);
        enviarServidor();
        quitar();
      },
      deshacer: () => {
        window.clearTimeout(timer);
        if (estado === despues) {
          estado = antes;
          notificar();
        } else {
          void resincronizar();
        }
        quitar();
      },
    },
  ];
  avisarPendientes();
}

/* ---------------------------------------------------------------------
   Aviso de conflicto: una accion que el servidor rechazo o un dato que
   cambio mientras se revisaba. Se muestra en la cabecera hasta que se cierra.
   --------------------------------------------------------------------- */

export interface AvisoConflicto {
  texto: string;
  en: number;
  /** 'aviso' es un conflicto o rechazo; 'info' confirma algo que paso (una rama creada). */
  tono?: 'aviso' | 'info';
}

let avisoConflicto: AvisoConflicto | null = null;
const oyentesAviso = new Set<() => void>();

function fijarAviso(texto: string, tono: 'aviso' | 'info' = 'aviso'): void {
  avisoConflicto = { texto, en: Date.now(), tono };
  for (const o of oyentesAviso) o();
}

/** Un aviso informativo para la cabecera: confirma que algo paso y donde estas. */
export function avisar(texto: string): void {
  fijarAviso(texto, 'info');
}

export function cerrarAvisoConflicto(): void {
  if (avisoConflicto === null) return;
  avisoConflicto = null;
  for (const o of oyentesAviso) o();
}

export function useAvisoConflicto(): AvisoConflicto | null {
  return useSyncExternalStore(
    (o) => {
      oyentesAviso.add(o);
      return () => oyentesAviso.delete(o);
    },
    () => avisoConflicto,
    () => avisoConflicto,
  );
}

let fuenteEventos: EventSource | null = null;
let ultimaSenal = 0;
let vigilante: number | null = null;

/** El servidor manda un latido cada 15 s. Si pasan 45 s sin nada (ni estado
 *  ni latido), el flujo esta muerto aunque el navegador no lo sepa: pasa
 *  cuando el servidor se reinicia detras del proxy de Vite. Se reabre y se
 *  vuelve a pedir el estado completo, para no quedarse con uno viejo. */
function vigilarFlujo(): void {
  if (vigilante !== null) return;
  vigilante = window.setInterval(() => {
    if (modo !== 'servidor') return;
    if (Date.now() - ultimaSenal > 45_000) {
      void resincronizar();
    }
  }, 15_000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && modo === 'servidor' && Date.now() - ultimaSenal > 20_000) void resincronizar();
  });
}

async function resincronizar(): Promise<void> {
  try {
    const r = await fetch(conToken(`${API}/estado`), { cache: 'no-store', headers: cabeceras(false) });
    if (r.ok) {
      const cuerpo = (await r.json()) as EstadoRosa;
      const version = versionDe(r.headers.get('X-Rosa-Version'));
      // Una respuesta que llega despues de que el flujo ya trajo algo mas nuevo
      // no se pinta: el flujo va en orden, la peticion suelta no.
      if (version === null || version >= versionRemota) recibirRemoto(cuerpo, version);
    }
  } catch {
    if (estado.conexion !== 'sin_conexion') aplicar((e) => ({ ...e, conexion: 'sin_conexion' }));
  }
  abrirEventos();
}

function abrirEventos(): void {
  if (fuenteEventos) fuenteEventos.close();
  const es = new EventSource(conToken(`${API}/eventos`));
  fuenteEventos = es;
  ultimaSenal = Date.now();
  es.addEventListener('latido', () => {
    ultimaSenal = Date.now();
    if (estado.conexion !== 'en_linea') aplicar((e) => ({ ...e, conexion: 'en_linea' }));
  });
  es.addEventListener('estado', (ev) => {
    ultimaSenal = Date.now();
    try {
      const m = ev as MessageEvent;
      recibirRemoto(JSON.parse(m.data) as EstadoRosa, versionDe(m.lastEventId));
    } catch {
      // Un mensaje corrupto no tumba la interfaz; el siguiente lo arregla.
    }
  });
  es.onopen = () => {
    if (estado.conexion !== 'en_linea') aplicar((e) => ({ ...e, conexion: 'en_linea' }));
  };
  es.onerror = () => {
    // EventSource reintenta solo. Mientras, se avisa.
    if (estado.conexion !== 'sin_conexion') aplicar((e) => ({ ...e, conexion: 'sin_conexion' }));
  };
}

/** Envia una accion al servidor. El estado local ya se aplico de forma
 *  optimista; el servidor manda el suyo por SSE en cuanto la procesa. */
function enviar(nombre: string, args: Record<string, unknown>): void {
  if (modo !== 'servidor') return;
  void fetch(`${API}/acciones/${nombre}`, { method: 'POST', headers: cabeceras(), body: JSON.stringify(args) })
    .then(async (r) => {
      if (r.status >= 500) {
        if (estado.conexion !== 'sin_conexion') aplicar((e) => ({ ...e, conexion: 'sin_conexion' }));
        return;
      }
      if (!r.ok) {
        // 4xx: el servidor rechazo la accion (argumentos, permiso). No es un corte de
        // conexion: se deshace el cambio optimista volviendo a pedir el estado.
        fijarAviso(`El servidor no acepto la accion "${nombre}" (${r.status}). Se recargo el estado del servidor; lo que veias como aplicado no lo estaba.`);
        void resincronizar();
        return;
      }
      const d = (await r.json().catch(() => null)) as { ok?: boolean } | null;
      if (d && d.ok === false) {
        fijarAviso(`El servidor no aplico la accion "${nombre}": la regla no se cumplia (otro cambio llego antes). Se recargo el estado.`);
        void resincronizar();
      }
    })
    .catch(() => {
      if (estado.conexion !== 'sin_conexion') aplicar((e) => ({ ...e, conexion: 'sin_conexion' }));
    });
}

/** Como `enviar`, pero devuelve si el servidor aplico la accion (ok), la
 *  rechazo (false) o no se pudo saber (null). */
async function enviarYComprobar(nombre: string, args: Record<string, unknown>): Promise<boolean | null> {
  if (modo !== 'servidor') return null;
  try {
    const r = await fetch(`${API}/acciones/${nombre}`, { method: 'POST', headers: cabeceras(), body: JSON.stringify(args) });
    if (r.status >= 500) return null;
    if (!r.ok) return false;
    const cuerpo = (await r.json()) as { ok: boolean };
    return cuerpo.ok;
  } catch {
    return null;
  }
}

/** Intenta el servidor; si no esta, arranca la muestra. Idempotente. */
export async function conectar(): Promise<'muestra' | 'servidor'> {
  try {
    const r = await fetch(conToken(`${API}/estado`), { cache: 'no-store', headers: cabeceras(false) });
    if (!r.ok) throw new Error(String(r.status));
    const remoto = (await r.json()) as EstadoRosa;
    if (!Array.isArray(remoto.investigaciones)) throw new Error('respuesta sin forma de EstadoRosa');
    modo = 'servidor';
    if (pararSimulacion) {
      pararSimulacion();
      pararSimulacion = null;
    }
    recibirRemoto(remoto);
    abrirEventos();
    vigilarFlujo();
  } catch {
    modo = 'muestra';
    arrancarMuestra();
  }
  return modo;
}

/* ---------------------------------------------------------------------
   Acciones
   --------------------------------------------------------------------- */

export const acciones = {
  marcarVisita: () => {
    const ahora = Date.now();
    try {
      localStorage.setItem(CLAVE_VISITA, String(ahora));
    } catch {
      // Sin almacenamiento: la visita dura lo que la pestana.
    }
    aplicar((e) => A.marcarVisita(e, ahora));
    enviar('marcarVisita', { ahora });
  },
  pausarCorrida: (id: string) => {
    aplicar((e) => A.pausarCorrida(e, id));
    enviar('pausarCorrida', { corrida_id: id });
  },
  reanudarCorrida: (id: string) => {
    aplicar((e) => A.reanudarCorrida(e, id));
    enviar('reanudarCorrida', { corrida_id: id });
  },
  detenerCorrida: (id: string, motivo: string, vigilarDias: number | null) => {
    aplicar((e) => A.detenerCorrida(e, id, motivo, Date.now(), vigilarDias));
    enviar('detenerCorrida', { corrida_id: id, motivo, vigilar_literatura_dias: vigilarDias });
  },
  /** Arranca una corrida nueva (solo con servidor: el bucle propone el plan). */
  iniciarCorrida: (investigacionId: string) => {
    enviar('iniciarCorrida', { investigacion_id: investigacionId });
  },
  ampliarPresupuesto: (id: string, limite: number) => {
    aplicar((e) => A.ampliarPresupuesto(e, id, limite, Date.now()));
    enviar('ampliarPresupuesto', { corrida_id: id, nuevo_limite: limite });
  },
  dirigirCorrida: (id: string, texto: string) => {
    aplicar((e) => A.dirigirCorrida(e, id, texto));
    enviar('dirigirCorrida', { corrida_id: id, texto });
  },
  editarPlan: (iteracionId: string, plan: PasoPlan[]) => {
    aplicar((e) => A.editarPlan(e, iteracionId, plan));
    enviar('editarPlan', { iteracion_id: iteracionId, plan });
  },
  aprobarPlan: (iteracionId: string) => {
    aplicar((e) => A.aprobarPlan(e, iteracionId, Date.now()));
    enviar('aprobarPlan', { iteracion_id: iteracionId });
  },
  fijarAutoaprobacionPlan: (corridaId: string, segundos: number | null) => {
    aplicar((e) => A.fijarAutoaprobacionPlan(e, corridaId, segundos));
    enviar('fijarAutoaprobacionPlan', { corrida_id: corridaId, segundos });
  },
  detenerPista: (pistaId: string, indicacion: string) => {
    aplicar((e) => A.detenerPista(e, pistaId, indicacion));
    enviar('detenerPista', { pista_id: pistaId, indicacion });
  },
  detenerProceso: (corridaId: string, procesoId: string, indicacion: string) => {
    aplicar((e) => A.detenerProceso(e, corridaId, procesoId, indicacion));
    enviar('detenerProceso', { corrida_id: corridaId, proceso_id: procesoId, indicacion });
  },
  volverAIteracion: (iteracionId: string, que: 'plan' | 'mundo' | 'ambos') => {
    aplicar((e) => A.volverAIteracion(e, iteracionId, que, Date.now()));
    enviar('volverAIteracion', { iteracion_id: iteracionId, que });
  },
  resolverSolicitud: (id: string, decision: 'conceder' | 'denegar', alcance: AlcancePermiso | null, argumentos?: Record<string, string>) => {
    aplicar((e) => A.resolverSolicitud(e, id, decision, alcance, Date.now(), argumentos));
    enviar('resolverSolicitud', { solicitud_id: id, decision, alcance, argumentos: argumentos ?? null });
  },
  resolverSolicitudes: (ids: string[], decision: 'conceder' | 'denegar', alcance: AlcancePermiso | null) => {
    aplicar((e) => A.resolverSolicitudes(e, ids, decision, alcance, Date.now()));
    enviar('resolverSolicitudes', { ids, decision, alcance });
  },
  revocarPermiso: (id: string) => {
    aplicar((e) => A.revocarPermiso(e, id));
    enviar('revocarPermiso', { permiso_id: id });
  },
  resolverIncidencia: (id: string, resolucion: string) => {
    aplicar((e) => A.resolverIncidencia(e, id, resolucion, Date.now()));
    enviar('resolverIncidencia', { incidencia_id: id, resolucion });
  },
  fijarAutonomia: (clase: ClaseAccion, nivel: NivelAutonomia) => {
    aplicar((e) => A.fijarAutonomia(e, clase, nivel));
    enviar('fijarAutonomia', { clase, nivel });
  },
  /** Decidir sobre una hipotesis. Va con la version que la persona veia y los
   *  segundos que tardo en decidir; si el servidor la rechaza (la hipotesis
   *  cambio entre medias), se resincroniza el estado y se avisa. */
  revisarHipotesis: (id: string, accion: A.AccionRevision, nota: string, aCiegas = false, revisionHumana: Omit<RevisionHumana, 'fecha' | 'quien'> | null = null, versionEsperada: number | null = null, segundosRevision: number | null = null) => {
    const titulo = estado.hipotesis.find((h) => h.id === id)?.titulo ?? 'la hipotesis';
    const verbo = accion === 'aceptar' ? 'Aceptada' : accion === 'descartar' ? 'Descartada' : accion === 'refinar' ? 'Devuelta a Rosa para refinar' : 'Decision registrada';
    programar(
      `${verbo}: ${titulo.length > 60 ? `${titulo.slice(0, 57)}...` : titulo}`,
      () => aplicar((e) => A.revisarHipotesis(e, id, accion, nota, QUIEN, Date.now(), aCiegas, revisionHumana, versionEsperada)),
      () => {
        void enviarYComprobar('revisarHipotesis', { hipotesis_id: id, accion, nota, quien: QUIEN, a_ciegas: aCiegas, revision_humana: revisionHumana, version_esperada: versionEsperada, segundos_revision: segundosRevision }).then((ok) => {
          if (ok === false) {
            fijarAviso('La hipotesis cambio mientras la revisabas (Rosa la reformulo). Se recargo la version nueva; vuelve a mirarla antes de decidir.');
            void resincronizar();
          }
        });
      },
    );
  },
  votarRelevancia: (id: string, voto: 'alta' | 'media' | 'baja') => {
    aplicar((e) => A.votarRelevancia(e, id, voto));
    enviar('votarRelevancia', { hipotesis_id: id, voto });
  },
  solicitarRevision: (id: string) => {
    aplicar((e) => A.solicitarRevision(e, id, Date.now()));
    enviar('solicitarRevision', { hipotesis_id: id });
  },
  replicarHipotesis: (id: string, total: number) => {
    aplicar((e) => A.replicarHipotesis(e, id, total, Date.now()));
    enviar('replicarHipotesis', { hipotesis_id: id, total });
  },
  proponerHipotesis: (investigacionId: string, datos: A.DatosHipotesisHumana): string | null => {
    let id: string | null = null;
    aplicar((e) => {
      const r = A.proponerHipotesis(e, investigacionId, datos, QUIEN, Date.now());
      id = r.id;
      return r.estado;
    });
    if (id !== null) enviar('proponerHipotesis', { investigacion_id: investigacionId, datos, quien: QUIEN, id_: id });
    return id;
  },
  asignarExperimento: (id: string, laboratorio: string) => {
    aplicar((e) => A.asignarExperimento(e, id, laboratorio));
    enviar('asignarExperimento', { hipotesis_id: id, laboratorio });
  },
  registrarDatosExperimento: (id: string, fichero: string, analisis: string) => {
    aplicar((e) => A.registrarDatosExperimento(e, id, fichero, analisis));
    enviar('registrarDatosExperimento', { hipotesis_id: id, fichero, analisis });
  },
  /** Sube el fichero de datos del laboratorio. Con servidor, va por multipart
   *  y Rosa lo evalua contra el prerregistro; en modo muestra solo se registra
   *  el nombre. Devuelve un mensaje de error o null. */
  subirDatosExperimento: async (id: string, fichero: File, analisis: string): Promise<string | null> => {
    if (modo !== 'servidor') {
      aplicar((e) => A.registrarDatosExperimento(e, id, fichero.name, analisis));
      return null;
    }
    const cuerpo = new FormData();
    cuerpo.append('fichero', fichero, fichero.name);
    cuerpo.append('analisis', analisis);
    try {
      const r = await fetch(`${API}/hipotesis/${encodeURIComponent(id)}/datos`, { method: 'POST', headers: cabeceras(false), body: cuerpo });
      if (!r.ok) return `El servidor rechazo el fichero (${r.status}).`;
      return null;
    } catch {
      return 'No se pudo subir el fichero: sin conexion con el servidor.';
    }
  },
  anadirComentario: (hipotesisId: string, ancla: AnclaComentario, nota: string) => {
    aplicar((e) => A.anadirComentario(e, hipotesisId, ancla, nota, Date.now()));
    enviar('anadirComentario', { hipotesis_id: hipotesisId, ancla, nota });
  },
  editarComentario: (id: string, nota: string) => {
    aplicar((e) => A.editarComentario(e, id, nota));
    enviar('editarComentario', { comentario_id: id, nota });
  },
  quitarComentario: (id: string) => {
    aplicar((e) => A.quitarComentario(e, id));
    enviar('quitarComentario', { comentario_id: id });
  },
  enviarComentarios: (hipotesisId: string, mensaje: string) => {
    aplicar((e) => A.enviarComentarios(e, hipotesisId, mensaje, QUIEN, Date.now()));
    enviar('enviarComentarios', { hipotesis_id: hipotesisId, mensaje, quien: QUIEN });
  },
  inyectarDebilidad: (corridaId: string, debilidadId: string) => {
    aplicar((e) => A.inyectarDebilidad(e, corridaId, debilidadId));
    enviar('inyectarDebilidad', { corrida_id: corridaId, debilidad_id: debilidadId });
  },
  recomprobarRetracciones: (investigacionId: string) => {
    aplicar((e) => A.recomprobarRetracciones(e, investigacionId, Date.now()));
    enviar('recomprobarRetracciones', { investigacion_id: investigacionId });
  },
  crearInvestigacion: (datos: A.DatosInvestigacion): string | null => {
    let id: string | null = null;
    const conQuien = { ...datos, quien: QUIEN };
    aplicar((e) => {
      const r = A.crearInvestigacion(e, conQuien, Date.now());
      id = r.id;
      return r.estado;
    });
    if (id !== null) {
      // Con servidor, la primera corrida arranca sola: Rosa propone el plan y
      // lo deja esperando aprobacion. Se encadena tras la respuesta de crear:
      // dos peticiones sueltas pueden llegar al servidor en orden cambiado.
      const invId = id;
      void enviarYComprobar('crearInvestigacion', { datos: conQuien, id_: invId }).then((ok) => {
        if (ok === false) {
          fijarAviso('El servidor no creo la investigacion. Se recargo el estado.');
          void resincronizar();
          return;
        }
        enviar('iniciarCorrida', { investigacion_id: invId });
      });
    }
    return id;
  },
  bifurcarInvestigacion: (investigacionId: string, motivo: string): string | null => {
    let id: string | null = null;
    aplicar((e) => {
      const r = A.bifurcarInvestigacion(e, investigacionId, motivo, Date.now());
      id = r.id;
      return r.estado;
    });
    if (id !== null) {
      enviar('bifurcarInvestigacion', { investigacion_id: investigacionId, motivo, id_: id });
      const rama = estado.investigaciones.find((i) => i.id === id);
      avisar(`Rama creada: "${rama?.titulo ?? 'rama'}". Estas dentro de la rama; la original sigue igual y esta en la barra lateral. Arranca su primera corrida cuando quieras.`);
    }
    return id;
  },
  actualizarConfiguracion: (investigacionId: string, configuracion: Investigacion['configuracion']) => {
    aplicar((e) => A.actualizarConfiguracion(e, investigacionId, configuracion));
    enviar('actualizarConfiguracion', { investigacion_id: investigacionId, configuracion });
  },
  anadirDataset: (investigacionId: string, dataset: Omit<Dataset, 'id' | 'estado'>) => {
    aplicar((e) => A.anadirDataset(e, investigacionId, dataset));
    enviar('anadirDataset', { investigacion_id: investigacionId, dataset });
  },
  decidirDataset: (investigacionId: string, datasetId: string, decision: 'aprobado' | 'rechazado') => {
    aplicar((e) => A.decidirDataset(e, investigacionId, datasetId, decision));
    enviar('decidirDataset', { investigacion_id: investigacionId, dataset_id: datasetId, decision });
  },
  aprobarDiccionario: (investigacionId: string, datasetId: string) => {
    aplicar((e) => A.aprobarDiccionario(e, investigacionId, datasetId));
    enviar('aprobarDiccionario', { investigacion_id: investigacionId, dataset_id: datasetId });
  },
  corregirDataset: (investigacionId: string, datasetId: string) => {
    aplicar((e) => A.corregirDataset(e, investigacionId, datasetId));
    enviar('corregirDataset', { investigacion_id: investigacionId, dataset_id: datasetId });
  },
  clasificarDataset: (investigacionId: string, datasetId: string, c: ClasificacionDatos) => {
    aplicar((e) => A.clasificarDataset(e, investigacionId, datasetId, c));
    enviar('clasificarDataset', { investigacion_id: investigacionId, dataset_id: datasetId, clasificacion: c });
  },
  destacarArtefacto: (id: string) => {
    aplicar((e) => A.destacarArtefacto(e, id));
    enviar('destacarArtefacto', { artefacto_id: id });
  },
  guardarArtefacto: (investigacionId: string, nombre: string, tipo: TipoArtefacto, contenido: string, resumen: string, iteracion: number): string => {
    let id = '';
    aplicar((e) => {
      const r = A.guardarArtefacto(e, investigacionId, nombre, tipo, contenido, resumen, iteracion, Date.now());
      id = r.id;
      return r.estado;
    });
    enviar('guardarArtefacto', { investigacion_id: investigacionId, nombre, tipo, contenido, resumen, iteracion, id_: id });
    return id;
  },
  cambiarEstadoCaso: (clave: string, nuevo: 'aprobado' | 'descartado' | 'propuesto') => {
    aplicar((e) => A.cambiarEstadoCaso(e, clave, nuevo));
    enviar('cambiarEstadoCaso', { clave, nuevo });
  },
  editarRespuestaCaso: (clave: string, respuesta: string) => {
    aplicar((e) => A.editarRespuestaCaso(e, clave, respuesta));
    enviar('editarRespuestaCaso', { clave, respuesta });
  },
  editarRecuerdo: (id: string, texto: string) => {
    aplicar((e) => A.editarRecuerdo(e, id, texto));
    enviar('editarRecuerdo', { id_: id, texto });
  },
  borrarRecuerdo: (id: string) => {
    aplicar((e) => A.borrarRecuerdo(e, id));
    enviar('borrarRecuerdo', { id_: id });
  },
  anadirCriterio: (texto: string) => {
    aplicar((e) => A.anadirCriterio(e, texto));
    enviar('anadirCriterio', { texto });
  },
  /** Se borra por texto, no por posicion: si la lista cambio en el servidor
   *  mientras se miraba, la posicion apuntaria a otro criterio. */
  borrarCriterio: (indice: number, texto: string) => {
    aplicar((e) => A.borrarCriterio(e, indice, texto));
    enviar('borrarCriterio', { indice, texto });
  },
  actualizarAvisos: (avisos: Avisos) => {
    aplicar((e) => A.actualizarAvisos(e, avisos));
    enviar('actualizarAvisos', { avisos });
  },
  actualizarPoliticaEsperas: (p: PoliticaEsperas) => {
    aplicar((e) => A.actualizarPoliticaEsperas(e, p));
    enviar('actualizarPoliticaEsperas', { politica: p });
  },
  borrarPlanGuardado: (id: string) => {
    aplicar((e) => A.borrarPlanGuardado(e, id));
    enviar('borrarPlanGuardado', { id_: id });
  },
  /* ---- ROSA2018 ---- */
  aprobarMision: (investigacionId: string, mision: A.DatosInvestigacion['mision']) => {
    aplicar((e) => A.aprobarMision(e, investigacionId, mision, QUIEN, Date.now()));
    enviar('aprobarMision', { investigacion_id: investigacionId, mision, quien: QUIEN });
  },
  eximirPuerta: (investigacionId: string, motivo: string) => {
    aplicar((e) => A.eximirPuerta(e, investigacionId, motivo, QUIEN, Date.now()));
    enviar('eximirPuerta', { investigacion_id: investigacionId, motivo, quien: QUIEN });
  },
  cerrarPuerta: (investigacionId: string) => {
    aplicar((e) => A.cerrarPuerta(e, investigacionId, QUIEN, Date.now()));
    enviar('cerrarPuerta', { investigacion_id: investigacionId, quien: QUIEN });
  },
  anadirReproduccion: (investigacionId: string, datasetId: string, datos: A.DatosReproduccion): string | null => {
    let id: string | null = null;
    aplicar((e) => {
      const r = A.anadirReproduccion(e, investigacionId, datasetId, datos, Date.now());
      id = r.id;
      return r.estado;
    });
    if (id !== null) enviar('anadirReproduccion', { investigacion_id: investigacionId, dataset_id: datasetId, datos });
    return id;
  },
  pedirAnalisis: (hipotesisId: string, datasetId: string, pregunta: string) => {
    aplicar((e) => A.pedirAnalisis(e, hipotesisId, datasetId, pregunta, Date.now()));
    enviar('pedirAnalisis', { hipotesis_id: hipotesisId, dataset_id: datasetId, pregunta });
  },
  promoverAprendizaje: (cambioId: string) => {
    aplicar((e) => A.promoverAprendizaje(e, cambioId, QUIEN, Date.now()));
    enviar('promoverAprendizaje', { cambio_id: cambioId, quien: QUIEN });
  },
  revertirAprendizaje: (cambioId: string, motivo: string) => {
    aplicar((e) => A.revertirAprendizaje(e, cambioId, QUIEN, motivo, Date.now()));
    enviar('revertirAprendizaje', { cambio_id: cambioId, quien: QUIEN, motivo });
  },
  /** Evaluar un criterio propuesto sobre el conjunto reservado. Solo con servidor: gasta llamadas al juez. */
  evaluarAprendizaje: (cambioId: string) => {
    enviar('evaluarAprendizaje', { cambio_id: cambioId });
  },
  actualizarPregunta: (corridaId: string, pregunta: Partial<PreguntaCampana>) => {
    aplicar((e) => A.actualizarPregunta(e, corridaId, pregunta, Date.now()));
    enviar('actualizarPregunta', { corrida_id: corridaId, pregunta, quien: QUIEN });
  },
  resolverHallazgoRegistro: (iteracionId: string, hallazgoId: string, estado: 'atendido' | 'descartado' | 'abierto', respuesta: string) => {
    aplicar((e) => A.resolverHallazgoRegistro(e, iteracionId, hallazgoId, estado, respuesta, QUIEN, Date.now()));
    enviar('resolverHallazgoRegistro', { iteracion_id: iteracionId, hallazgo_id: hallazgoId, estado, respuesta, quien: QUIEN });
  },
  /** Estado del espejo del estado en Convex (solo lectura). */
  estadoEspejo: async (): Promise<EstadoEspejo | null> => {
    if (modo !== 'servidor') return null;
    try {
      const r = await fetch(`${API}/espejo`, { cache: 'no-store', headers: cabeceras(false) });
      return r.ok ? ((await r.json()) as EstadoEspejo) : null;
    } catch {
      return null;
    }
  },
  fijarPermisoConector: (nombre: string, nivel: NivelPermisoConector) => {
    aplicar((e) => A.fijarPermisoConector(e, nombre, nivel, QUIEN, Date.now()));
    enviar('fijarPermisoConector', { nombre, nivel, quien: QUIEN });
  },
  anadirMemoria: (investigacionId: string, texto: string) => {
    aplicar((e) => A.anadirMemoria(e, investigacionId, texto, QUIEN, Date.now()));
    enviar('anadirMemoria', { investigacion_id: investigacionId, texto, quien: QUIEN });
  },
  quitarMemoria: (investigacionId: string, memoriaId: string) => {
    aplicar((e) => A.quitarMemoria(e, investigacionId, memoriaId));
    enviar('quitarMemoria', { investigacion_id: investigacionId, memoria_id: memoriaId });
  },
  /** Una pregunta con herramientas (conectores, busqueda en el proyecto, modelo
   *  de mundo): la corre el servidor con el cerebro y la respuesta llega al
   *  estado por SSE con sus consultas. Devuelve un error legible o null. */
  preguntarALasBases: async (investigacionId: string, pregunta: string): Promise<string | null> => {
    if (modo !== 'servidor') return 'Preguntar a las bases requiere el servidor de Rosa.';
    try {
      const r = await fetch(`${API}/investigaciones/${encodeURIComponent(investigacionId)}/preguntar`, { method: 'POST', headers: cabeceras(), body: JSON.stringify({ pregunta, quien: QUIEN }) });
      if (!r.ok) return `El servidor no pudo responder (${r.status}).`;
      const d = (await r.json()) as { ok: boolean; resultado?: { error?: string | null } };
      return d.ok ? null : d.resultado?.error ?? 'La pregunta fallo.';
    } catch {
      return 'Sin conexion con el servidor.';
    }
  },
  cambiarEstadoArea: (investigacionId: string, areaId: string, estado: EstadoArea | null, condicionReapertura = '', corridaId: string | null | undefined = undefined, motivo = '') => {
    aplicar((e) => A.cambiarEstadoArea(e, investigacionId, areaId, estado, QUIEN, Date.now(), condicionReapertura, corridaId, motivo));
    enviar('cambiarEstadoArea', { investigacion_id: investigacionId, area_id: areaId, estado, quien: QUIEN, condicion_reapertura: condicionReapertura, corrida_id: corridaId === undefined ? null : corridaId || '', motivo });
  },
  enmendarExperimento: (hipotesisId: string, campo: CampoEnmendable, despues: string, motivo: string) => {
    aplicar((e) => A.enmendarExperimento(e, hipotesisId, campo, despues, motivo, QUIEN, Date.now()));
    enviar('enmendarExperimento', { hipotesis_id: hipotesisId, campo, despues, motivo, quien: QUIEN });
  },
  /** Etiqueta humana sobre una comprobacion del Killer (conjunto dorado, calibracion de jueces). */
  etiquetarComprobacion: (hipotesisId: string, comprobacion: string, veredictoHumano: 'pasa' | 'falla' | 'no_comprobable', nota = '') => {
    aplicar((e) => A.etiquetarComprobacion(e, hipotesisId, comprobacion, veredictoHumano, QUIEN, Date.now(), nota));
    enviar('etiquetarComprobacion', { hipotesis_id: hipotesisId, comprobacion, veredicto_humano: veredictoHumano, quien: QUIEN, nota });
  },
  /** Pide (o repite) el sello de tiempo de un tercero sobre el prerregistro. El servidor lo registra por SSE. */
  sellarPrerregistro: async (hipotesisId: string): Promise<boolean> => {
    if (modo !== 'servidor') return false;
    try {
      const r = await fetch(`${API}/hipotesis/${encodeURIComponent(hipotesisId)}/sellar`, { method: 'POST', headers: cabeceras() });
      if (!r.ok) return false;
      const d = (await r.json()) as { ok?: boolean };
      return Boolean(d.ok);
    } catch {
      return false;
    }
  },
  anadirConocimientoOperativo: (investigacionId: string, texto: string, tipo: ConocimientoOperativo['tipo']) => {
    aplicar((e) => A.anadirConocimientoOperativo(e, investigacionId, texto, tipo, QUIEN, Date.now()));
    enviar('anadirConocimientoOperativo', { investigacion_id: investigacionId, texto, tipo, quien: QUIEN });
  },
  quitarConocimientoOperativo: (investigacionId: string, id: string) => {
    aplicar((e) => A.quitarConocimientoOperativo(e, investigacionId, id));
    enviar('quitarConocimientoOperativo', { investigacion_id: investigacionId, id_: id });
  },
  /** Descarga el flujo PRISMA 2020 de una corrida (JSON y Markdown). */
  exportarPrisma: async (corridaId: string): Promise<boolean> => {
    if (modo !== 'servidor') return false;
    try {
      const r = await fetch(`${API}/corridas/${encodeURIComponent(corridaId)}/prisma`, { cache: 'no-store', headers: cabeceras(false) });
      if (!r.ok) return false;
      const d = (await r.json()) as { markdown: string };
      const fecha = new Date().toISOString().slice(0, 10);
      descargar(`rosa-prisma2020-${corridaId}-${fecha}.md`, d.markdown, 'text/markdown;charset=utf-8');
      descargar(`rosa-prisma2020-${corridaId}-${fecha}.json`, JSON.stringify({ ...d, markdown: undefined }, null, 1), 'application/json');
      return true;
    } catch {
      return false;
    }
  },
  /** Coste por decision de una investigacion (modelo mas revision humana). */
  costesDe: async (investigacionId: string): Promise<CostesInvestigacion | null> => {
    if (modo !== 'servidor') return null;
    try {
      const r = await fetch(`${API}/investigaciones/${encodeURIComponent(investigacionId)}/costes`, { cache: 'no-store', headers: cabeceras(false) });
      return r.ok ? ((await r.json()) as CostesInvestigacion) : null;
    } catch {
      return null;
    }
  },
  /** Integridad del registro de acciones (cadena de hashes). */
  integridadRegistro: async (): Promise<{ ok: boolean; filas: number; encadenadas: number; sinHash: number; rotaEn: number | null; motivo?: string } | null> => {
    if (modo !== 'servidor') return null;
    try {
      const r = await fetch(`${API}/registro/integridad`, { cache: 'no-store', headers: cabeceras(false) });
      return r.ok ? ((await r.json()) as { ok: boolean; filas: number; encadenadas: number; sinHash: number; rotaEn: number | null; motivo?: string }) : null;
    } catch {
      return null;
    }
  },
  registrarProtocoloReal: (hipotesisId: string, protocoloReal: { texto: string; desviaciones: string; identidadMuestras: string }) => {
    aplicar((e) => A.registrarProtocoloReal(e, hipotesisId, protocoloReal, QUIEN, Date.now()));
    enviar('registrarProtocoloReal', { hipotesis_id: hipotesisId, protocolo_real: protocoloReal, quien: QUIEN });
  },
  actualizarMetodo: (metodoId: string, cambios: Partial<MetodoRegistrado>) => {
    aplicar((e) => A.actualizarMetodo(e, metodoId, cambios, QUIEN, Date.now()));
    enviar('actualizarMetodo', { metodo_id: metodoId, cambios, quien: QUIEN });
  },
  actualizarProcedenciaDataset: (investigacionId: string, datasetId: string, procedencia: Partial<ProcedenciaDataset>) => {
    aplicar((e) => A.actualizarProcedenciaDataset(e, investigacionId, datasetId, procedencia));
    enviar('actualizarProcedenciaDataset', { investigacion_id: investigacionId, dataset_id: datasetId, procedencia });
  },
  /** El dossier se arma en el servidor con todo el estado; llega como artefacto por SSE. */
  generarDossier: (hipotesisId: string) => {
    enviar('generarDossier', { hipotesis_id: hipotesisId, quien: QUIEN });
  },
  /** Sube un dataset con su fichero. El servidor calcula el hash, perfila las
   *  columnas y lo deja pendiente hasta completar el libro de procedencia. */
  subirDataset: async (investigacionId: string, fichero: File, nombre: string, descripcion: string, sintetico: boolean): Promise<string | null> => {
    if (modo !== 'servidor') return 'Subir datasets requiere el servidor de Rosa.';
    const cuerpo = new FormData();
    cuerpo.append('fichero', fichero, fichero.name);
    cuerpo.append('nombre', nombre);
    cuerpo.append('descripcion', descripcion);
    cuerpo.append('sintetico', sintetico ? 'si' : 'no');
    try {
      const r = await fetch(`${API}/investigaciones/${encodeURIComponent(investigacionId)}/datasets`, { method: 'POST', headers: cabeceras(false), body: cuerpo });
      if (!r.ok) return `El servidor rechazo el fichero (${r.status}).`;
      return null;
    } catch {
      return 'No se pudo subir el fichero: sin conexion con el servidor.';
    }
  },
};

let pararSimulacion: (() => void) | null = null;

/** Arranca la corrida simulada. Idempotente. */
export function arrancarMuestra(): void {
  if (pararSimulacion !== null || modo === 'servidor') return;
  pararSimulacion = iniciarSimulacion(aplicar);
}
