// La corrida en vivo: lo que Claude Science no tiene. Iteracion actual con su
// plan (por aprobar o en marcha) y sus pistas; permisos pendientes con lotes;
// incidencias (modelo que se nego, conector caducado); presupuesto global con
// alarmas; gasto y ocupacion del contexto; procesos de computo; la busqueda
// (flujo PRISMA y consultas exactas); las iteraciones anteriores con
// "volver aqui" y "bifurcar desde aqui"; y detener con vigilancia de
// literatura.

import { useEffect, useMemo, useState } from 'react';
import { acciones } from '../datos/almacen';
import { iteracionActualDe } from '../datos/acciones';
import type { AlcancePermiso, Corrida as CorridaTipo, EstadoCorrida, EstadoRosa, Investigacion } from '../datos/tipos';
import { PlanEnVivo } from '../componentes/PlanEnVivo';
import { FormularioMision, PreguntaDeCampana, RevisionDeRegistro } from '../componentes/Rosa2018';
import { Presupuesto } from '../componentes/Presupuesto';
import { TarjetaIncidencia } from '../componentes/TarjetaIncidencia';
import { TarjetaPermiso } from '../componentes/TarjetaPermiso';
import { Trazabilidad } from '../componentes/Trazabilidad';
import { ResumenEnLlano } from '../componentes/EnLlano';
import { AvisoMuestra, Barra, Chip, Confirmar, Momento, Seccion, SoloDetalle, Vacio } from '../componentes/piezas';
import { IconPause, IconPlay } from '../componentes/icons';
import { ALCANCE, MODO_BUSQUEDA, etiquetaCorrida, proponiendoPlan } from '../lib/etiquetas';
import { formatearCompacto, formatearDuracion, formatearEntero, formatearPorcentaje } from '../lib/formato';
import { rutaDe } from '../lib/ruta';
import { BORRADOR_VACIO, NIVELES_OBJETIVO, borradorDe, normalizarParada, resumenParada, type ParadaBorrador } from '../lib/parada';
import { GraficaProgreso } from '../componentes/GraficaProgreso';
import { resumenMetrica } from '../lib/progreso';

type PropsCorrida = { inv: Investigacion; estado: EstadoRosa; ahora: number; irA: (hash: string) => void };

/** La pantalla de la corrida. Decide si hay corrida y monta un componente u
 *  otro: así los hooks de la corrida viva nunca son condicionales (una
 *  investigación que pasa de "sin corridas" a "corrida 1" cambiaba el número
 *  de hooks del mismo componente, y React fallaba al arrancar la primera
 *  corrida: "Rendered more hooks than during the previous render"). */
export function Corrida({ inv, estado, ahora, irA }: PropsCorrida) {
  const corrida = estado.corridas.filter((c) => c.investigacionId === inv.id).sort((a, b) => b.numero - a.numero)[0] ?? null;
  if (!corrida) {
    return (
      <div className="contenido">
        <AvisoMuestra conexion={estado.conexion} />
        <Vacio
          titulo="Esta investigación no tiene corridas"
          pasos={['Rosa lee el objetivo y los límites y propone el plan de la iteración 1.', 'Tu apruebas el plan (puedes reordenar, quitar o añadir pasos).', 'Cada paso se ejecuta con sus pistas en paralelo; aquí ves cada consulta a cada base.', 'Al cerrar la iteración, Rosa resume en llano lo que encontró y lo que te espera.']}
          accion={
            estado.conexion === 'muestra' ? undefined : (
              <button type="button" className="btn btn-primario" onClick={() => acciones.iniciarCorrida(inv.id)}>
                <IconPlay size={13} /> Arrancar la primera corrida
              </button>
            )
          }
        >
          {estado.conexion === 'muestra' ? 'Cuando Rosa este conectada, aquí se arranca la primera con el objetivo y los límites definidos.' : 'Rosa arranca la corrida con el objetivo y los límites definidos, propone el plan de la primera iteración y espera tu aprobación.'}
        </Vacio>
      </div>
    );
  }
  return <CorridaViva key={corrida.id} inv={inv} estado={estado} ahora={ahora} irA={irA} corrida={corrida} />;
}

/** El botón "Nueva corrida" con su parada: cuánto debe durar como mucho, en
 *  tiempo, iteraciones o certeza, o una condición en texto. Se detiene con lo
 *  que llegue primero; la condición de la investigación sigue valiendo. Los
 *  campos vienen rellenos con la parada de la corrida anterior. */
function NuevaCorrida({ inv, anterior }: { inv: Investigacion; anterior: CorridaTipo['parada'] }) {
  const [abierto, setAbierto] = useState(false);
  const [b, setB] = useState<ParadaBorrador>(() => borradorDe(anterior));
  // El límite de llamadas de una corrida anterior no debe heredarse oculto.
  const parada = normalizarParada({ ...b, llamadas: '' });
  const campo = (clave: keyof ParadaBorrador) => (e: React.ChangeEvent<HTMLInputElement>) => setB((x) => ({ ...x, [clave]: e.target.value }));
  if (!abierto) {
    return (
      <div className="acciones">
        <button type="button" className="btn btn-primario" onClick={() => setAbierto(true)} title="Elige cuánto debe durar la corrida y Rosa propone el plan de la iteración 1 sobre el modelo de mundo actual">
          <IconPlay size={13} /> Nueva corrida
        </button>
      </div>
    );
  }
  return (
    <form
      className="tarjeta nueva-corrida"
      onSubmit={(e) => {
        e.preventDefault();
        acciones.iniciarCorrida(inv.id, parada);
        setAbierto(false);
      }}
    >
      <p className="meta">
        Cuánto debe durar esta corrida como mucho. Se detiene con lo que llegue primero. Deja todo vacío para que solo mande la condición de la investigación: «{inv.condicionParada || 'sin condición declarada'}».
      </p>
      <div className="nueva-corrida-campos">
        <div className="campo">
          <label className="campo-etiqueta" htmlFor="nueva-corrida-tiempo">Tiempo</label>
          <div className="nueva-corrida-duracion">
            <input id="nueva-corrida-tiempo" type="number" inputMode="decimal" min={b.unidadTiempo === 'minutos' ? 1 : b.unidadTiempo === 'dias' ? 1 / 1440 : 1 / 60} max={b.unidadTiempo === 'minutos' ? 20160 : b.unidadTiempo === 'dias' ? 14 : 336} step="any" placeholder="por ejemplo 2" value={b.horas} onChange={campo('horas')} />
            <select aria-label="Unidad de tiempo" value={b.unidadTiempo ?? 'horas'} onChange={(e) => setB((x) => ({ ...x, unidadTiempo: e.target.value as ParadaBorrador['unidadTiempo'] }))}>
              <option value="minutos">Minutos</option>
              <option value="horas">Horas</option>
              <option value="dias">Días</option>
            </select>
          </div>
        </div>
        <label className="campo">
          <span className="campo-etiqueta">Iteraciones</span>
          <input type="number" inputMode="numeric" min={1} step={1} placeholder="por ejemplo 6" value={b.iteraciones} onChange={campo('iteraciones')} />
        </label>
        <label className="campo nueva-corrida-certeza">
          <span className="campo-etiqueta">Parar al llegar a certeza</span>
          <select aria-label="Parar al llegar a certeza" value={b.certeza} onChange={(e) => setB((x) => ({ ...x, certeza: e.target.value as ParadaBorrador['certeza'] }))}>
            <option value="">Sin objetivo de certeza</option>
            {NIVELES_OBJETIVO.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
        <label className="campo">
          <span className="campo-etiqueta">Cuántas hipótesis</span>
          <input type="number" inputMode="numeric" min={1} step={1} placeholder="1" value={b.cuantas} onChange={campo('cuantas')} disabled={!b.certeza} />
        </label>
        <label className="campo">
          <span className="campo-etiqueta">Iteraciones sin avance</span>
          <input type="number" inputMode="numeric" min={1} step={1} placeholder="por ejemplo 3" value={b.sinCambio} onChange={campo('sinCambio')} />
          <small>Para si N iteraciones seguidas no suben ninguna hipótesis de certeza ni añaden hechos.</small>
        </label>
        <label className="campo nueva-corrida-texto">
          <span className="campo-etiqueta">Otra condición, en palabras</span>
          <input type="text" maxLength={300} placeholder="por ejemplo: hasta que una hipótesis llegue a certeza baja" value={b.texto} onChange={campo('texto')} />
          <small>Rosa comprueba el tiempo, las iteraciones, la certeza y la falta de avance; las demás condiciones las decides tú con el botón de detener.</small>
        </label>
      </div>
      <div className="acciones">
        <button type="submit" className="btn btn-primario">
          <IconPlay size={13} /> {parada ? `Empezar: se detiene con ${resumenParada(parada)}` : 'Empezar sin parada propia'}
        </button>
        <button type="button" className="btn" onClick={() => { setAbierto(false); setB(borradorDe(anterior) ?? BORRADOR_VACIO); }}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

function CorridaViva({ inv, estado, ahora, irA, corrida }: PropsCorrida & { corrida: CorridaTipo }) {
  const [indicacion, setIndicacion] = useState('');
  const [verResueltas, setVerResueltas] = useState(false);
  const [verBusqueda, setVerBusqueda] = useState(false);
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set());
  const [vigilar, setVigilar] = useState(true);
  const [indicacionProceso, setIndicacionProceso] = useState<Record<string, string>>({});
  const viva = corrida.estado !== 'detenida' && corrida.estado !== 'terminada';
  // El reloj de la corrida es tiempo de trabajo (misma regla que
  // rosa/bucle/corrida.py tiempo_trabajo_ms: reloj de pared menos la espera a
  // una persona y menos las pausas del proceso), avanza cada segundo en
  // pantalla mientras Rosa trabaja y se queda quieto mientras espera a alguien.
  const segundosDeCorrida = useSegundosDeCorrida(corrida);
  const enEspera = esperandoPersona(corrida.estado);


  const iteracion = iteracionActualDe(estado, corrida);
  const anteriores = estado.iteraciones.filter((i) => i.corridaId === corrida.id && i.id !== iteracion?.id).sort((a, b) => b.numero - a.numero);
  const solicitudes = estado.solicitudes.filter((s) => s.corridaId === corrida.id).sort((a, b) => b.creadaEn - a.creadaEn);
  const pendientes = solicitudes.filter((s) => s.estado === 'pendiente');
  const resueltas = solicitudes.filter((s) => s.estado !== 'pendiente');
  const incidencias = estado.incidencias.filter((i) => i.corridaId === corrida.id).sort((a, b) => b.creadaEn - a.creadaEn);
  const incidenciasPendientes = incidencias.filter((i) => i.estado === 'pendiente');
  const tono = corrida.estado === 'en_marcha' ? 'acento' : corrida.estado === 'detenida' || corrida.estado === 'terminada' ? undefined : 'aviso';
  const alcancesComunes = useMemo(() => {
    const sel = pendientes.filter((s) => seleccion.has(s.id));
    if (sel.length === 0) return [] as AlcancePermiso[];
    return (['una_vez', 'esta_corrida', 'esta_investigacion', 'siempre'] as AlcancePermiso[]).filter((a) => sel.every((s) => s.alcances.includes(a)));
  }, [pendientes, seleccion]);
  const procesosVivos = corrida.procesos.filter((p) => p.estado === 'en_marcha');
  const contextoPct = corrida.contexto.tokensUsados / corrida.contexto.tokensLimite;

  return (
    <div className="contenido">
      <AvisoMuestra conexion={estado.conexion} />
      <div className="pantalla-cabecera" style={{ marginTop: 16 }}>
        <div>
          <h2>Corrida {corrida.numero}</h2>
          <div className="corrida-estado">
            <Chip tono={tono}>{etiquetaCorrida(corrida, iteracion)}</Chip>
            <span className="meta">Iteración {corrida.iteracionActual}</span>
            <span className="meta">
              Empezó <Momento t={corrida.empezadaEn} ahora={ahora} />
            </span>
            {corrida.terminadaEn !== null && (
              <span className="meta">
                Terminó <Momento t={corrida.terminadaEn} ahora={ahora} />
              </span>
            )}
            <span className="meta" title="Tiempo de trabajo: el reloj de pared menos lo que la corrida pasó esperando a una persona (plan sin aprobar, permiso, pausa) y menos las pausas del proceso. Es lo que se compara con el tope en horas.">
              {formatearDuracion(segundosDeCorrida * 1000) || '0 s'} de trabajo{viva && enEspera ? ' · en espera de una persona: el reloj no corre' : ''}
            </span>
            {(corrida.gasto.usdReal !== undefined && corrida.gasto.usdReal !== null) || (corrida.gasto.usd ?? 0) > 0 ? (
              <span className="meta" title={textoCoste(corrida.gasto).title}>
                {textoCoste(corrida.gasto).corto}
              </span>
            ) : null}
            {corrida.motivoCierre && <span className="meta">{corrida.motivoCierre}</span>}
            {corrida.metrica && resumenMetrica(corrida.metrica) && (
              <span className="meta" title="Balance de la corrida: peldaños de certeza GRADE subidos por las hipótesis, netos de los bajados, y por dólar gastado">
                Balance: {resumenMetrica(corrida.metrica)}
              </span>
            )}
            {corrida.parada && resumenParada(corrida.parada) && (
              <span className="meta" title="Parada fijada al crear esta corrida; además sigue valiendo la condición de parada de la investigación">
                Se detiene con {resumenParada(corrida.parada)}
              </span>
            )}
            {corrida.arnes && (
              <span className="meta" title={`Firmas ${corrida.arnes.firmas} · programas optimizados: ${corrida.arnes.optimizados}`}>
                Rosa {corrida.arnes.commit}
              </span>
            )}
          </div>
        </div>
        {!viva && estado.conexion !== 'muestra' && <NuevaCorrida inv={inv} anterior={corrida.parada ?? null} />}
        {viva && (
          <div className="acciones">
            {corrida.estado === 'en_marcha' ? (
              <button type="button" className="btn" onClick={() => acciones.pausarCorrida(corrida.id)}>
                <IconPause size={13} /> Pausar
              </button>
            ) : corrida.estado === 'pausada' ? (
              <button type="button" className="btn btn-primario" onClick={() => acciones.reanudarCorrida(corrida.id)}>
                <IconPlay size={13} /> Reanudar
              </button>
            ) : null}
            <Confirmar
              etiqueta="Detener"
              peligro
              pregunta="La corrida se detiene y no se reanuda: lo que hay en el modelo de mundo y en la cola se conserva. Para seguir habría que arrancar una corrida nueva."
              pedirTexto={{ etiqueta: 'Por qué se detiene', marcador: 'Hay que revisar la cola antes de seguir gastando' }}
              extra={
                <label className="interruptor">
                  <input type="checkbox" checked={vigilar} onChange={(e) => setVigilar(e.target.checked)} />
                  Vigilar la literatura 30 días: Rosa avisa de artículos nuevos que toquen una hipótesis aceptada
                </label>
              }
              onConfirmar={(motivo) => acciones.detenerCorrida(corrida.id, motivo, vigilar ? 30 : null)}
            />
          </div>
        )}
      </div>

      {(() => {
        // La última iteración cerrada con resumen: lo primero que se lee.
        const cerrada = [iteracion, ...anteriores].filter((i): i is NonNullable<typeof i> => i !== null && i.terminadaEn !== null && i.resumen !== '').sort((a, b) => b.numero - a.numero)[0];
        return cerrada ? (
          <>
            <ResumenEnLlano resumen={cerrada.resumenLlano} numero={cerrada.numero} />
            <RevisionDeRegistro r={cerrada.revisionRegistro} iteracionId={cerrada.id} />
          </>
        ) : null;
      })()}

      {incidenciasPendientes.length > 0 && (
        <Seccion titulo={incidenciasPendientes.length === 1 ? 'Algo impide seguir' : `${incidenciasPendientes.length} cosas impiden seguir`} nota="Un modelo que se negó o un conector caducado no matan la corrida en silencio: aparecen aquí con la alternativa que Rosa propone.">
          {incidenciasPendientes.map((i) => (
            <TarjetaIncidencia key={i.id} incidencia={i} ahora={ahora} onResolver={(r) => acciones.resolverIncidencia(i.id, r)} />
          ))}
        </Seccion>
      )}

      {pendientes.length > 0 && (
        <Seccion
          titulo={pendientes.length === 1 ? 'Rosa necesita tu permiso' : `Rosa necesita tu permiso (${pendientes.length})`}
          nota={`La aprobación va antes del efecto: nada de esto ocurre hasta que respondas. Si nadie decide en ${estado.politicaEsperas.horas} h: ${estado.politicaEsperas.accion === 'recordar' ? 'se recuerda' : estado.politicaEsperas.accion === 'escalar' ? `se escala a ${estado.politicaEsperas.escalarA}` : estado.politicaEsperas.accion === 'detener' ? 'la corrida se detiene con seguridad' : 'la corrida continúa y queda registrado'} (se cambia en Ajustes).`}
          acciones={
            seleccion.size > 1 ? (
              <div className="acciones">
                <span className="meta">{seleccion.size} seleccionadas:</span>
                {alcancesComunes.map((a) => (
                  <button
                    key={a}
                    type="button"
                    className="btn btn-s"
                    onClick={() => {
                      acciones.resolverSolicitudes([...seleccion], 'conceder', a);
                      setSeleccion(new Set());
                    }}
                  >
                    Permitir {ALCANCE[a].toLowerCase()}
                  </button>
                ))}
                {alcancesComunes.length === 0 && <span className="meta">sin un alcance común; resuélvelas una a una</span>}
                <button
                  type="button"
                  className="btn btn-s btn-peligro"
                  onClick={() => {
                    acciones.resolverSolicitudes([...seleccion], 'denegar', null);
                    setSeleccion(new Set());
                  }}
                >
                  Denegar seleccionadas
                </button>
              </div>
            ) : undefined
          }
        >
          {pendientes.map((s) => (
            <TarjetaPermiso
              key={s.id}
              solicitud={s}
              ahora={ahora}
              horasEspera={estado.politicaEsperas.horas}
              seleccionada={seleccion.has(s.id)}
              onSeleccionar={(v) => {
                const n = new Set(seleccion);
                if (v) n.add(s.id);
                else n.delete(s.id);
                setSeleccion(n);
              }}
              onResolver={(d, a, args) => acciones.resolverSolicitud(s.id, d, a, args)}
            />
          ))}
        </Seccion>
      )}

      <div className="rejilla-2" style={{ marginTop: 28, alignItems: 'start' }}>
        <div className="seccion" style={{ gridColumn: '1 / -1' }}>
          <SoloDetalle resumen={`Gasto: ${formatearEntero(corrida.gasto.llamadas)} llamadas al modelo, ${formatearEntero(corrida.gasto.articulosLeidos)} artículos leídos, ${formatearDuracion(segundosDeCorrida * 1000) || '0 s'} de trabajo${viva && enEspera ? ' (en espera de una persona)' : ''}${textoCoste(corrida.gasto).corto ? `, ${textoCoste(corrida.gasto).corto}` : ''}.`}>
          <div className="gasto">
            <div className="gasto-item" title="Tiempo de trabajo: reloj de pared menos la espera a una persona y las pausas del proceso; es lo que se compara con el tope en horas.">
              <strong>{formatearDuracion(segundosDeCorrida * 1000) || '0 s'}</strong>
              <span>{viva && enEspera ? 'de trabajo · en espera de una persona' : 'de trabajo'}</span>
            </div>
            {textoCoste(corrida.gasto).corto && (
              <div className="gasto-item" title={textoCoste(corrida.gasto).title}>
                <strong>{textoCoste(corrida.gasto).principal}</strong>
                <span>{textoCoste(corrida.gasto).etiqueta}</span>
              </div>
            )}
            <div className="gasto-item">
              <strong>{formatearEntero(corrida.gasto.articulosLeidos)}</strong>
              <span>artículos leídos</span>
            </div>
            <div className="gasto-item">
              <strong>{formatearEntero(corrida.gasto.llamadas)}</strong>
              <span>llamadas al modelo</span>
            </div>
            <div className="gasto-item">
              <strong>{formatearCompacto(corrida.gasto.tokensEntrada)}</strong>
              <span>tokens de entrada</span>
            </div>
            <div className="gasto-item">
              <strong>{formatearCompacto(corrida.gasto.tokensSalida)}</strong>
              <span>tokens de salida</span>
            </div>
            {(corrida.gasto.exaUsd ?? 0) > 0 && (
              <div className="gasto-item" title="Búsquedas semánticas en Exa: 7 USD por mil búsquedas y 1 USD por mil páginas. Se suma al coste por decisión.">
                <strong>{(corrida.gasto.exaUsd ?? 0).toFixed(3)} USD</strong>
                <span>en Exa</span>
              </div>
            )}
            <div className="gasto-item" title="Cuánto del contexto del cerebro está ocupado y cuántas veces se ha resumido el historial. Explica por qué Rosa puede 'olvidar' tras días.">
              <strong>{formatearPorcentaje(contextoPct)}</strong>
              <span>
                contexto ocupado · {corrida.contexto.compactaciones} {corrida.contexto.compactaciones === 1 ? 'compactación' : 'compactaciones'}
              </span>
              <Barra fraccion={contextoPct} tono={contextoPct > 0.8 ? 'aviso' : undefined} />
            </div>
          </div>
          </SoloDetalle>
        </div>
        <div style={{ gridColumn: '1 / -1' }}>
          <Presupuesto corrida={corrida} onAmpliar={(l) => acciones.ampliarPresupuesto(corrida.id, l)} />
        </div>
      </div>

      {inv.mision && !inv.mision.aprobadaEn && viva && (
        <Seccion titulo="La misión espera tu aprobación" nota="Rosa propuso el marco de la investigación a partir de tu objetivo (población, etapa, célula o tejido, mecanismo, tipo de intervención, capacidades del laboratorio y presupuesto). Aprobar el primer plan la aprueba tal como está; si quieres corregirla, hazlo aquí o en Objetivo y datos.">
          <FormularioMision inv={inv} compacto />
        </Seccion>
      )}

      <GraficaProgreso corridas={estado.corridas.filter((c) => c.investigacionId === inv.id)} />

      <PreguntaDeCampana corrida={corrida} />

      {corrida.traspasoRecibido && (
        <Seccion detalle titulo="Lo que hereda de la corrida anterior" nota="El traspaso ejecutable: cómo terminó la corrida anterior, su balance, la pregunta que trabajó, las hipótesis que el Killer cerró y por qué, las consultas hechas y las debilidades no atendidas. El planificador lo lee antes de proponer el primer plan.">
          <pre className="traspaso">{corrida.traspasoRecibido}</pre>
        </Seccion>
      )}

      {viva && proponiendoPlan(corrida, iteracion) && (
        <Seccion titulo={`Iteración ${iteracion ? iteracion.numero + 1 : corrida.iteracionActual}`} nota="Rosa escribe el plan">
          <div className="tarjeta">
            <p>
              <span className="shimmer-text">Rosa está proponiendo el plan de esta iteración</span>
            </p>
            <p className="meta">
              Primero fija la misión de la investigación, después la pregunta de esta corrida y por último los pasos con su presupuesto. Son dos o tres llamadas al cerebro y suelen tardar uno o dos minutos. Cuando el plan esté listo aparecerá aquí para que lo apruebes, lo edites o lo dejes autoaprobar. Todavía no hay nada que aprobar.
            </p>
          </div>
        </Seccion>
      )}

      {iteracion && (
        <Seccion
          titulo={`Iteración ${iteracion.numero}`}
          nota={
            iteracion.terminadaEn
              ? `Terminada`
              : iteracion.planAprobado
                ? `Empezó`
                : `Plan propuesto, sin aprobar`
          }
          acciones={
            <span className="meta" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              {iteracion.terminadaEn ? <Momento t={iteracion.terminadaEn} ahora={ahora} /> : <Momento t={iteracion.planAprobado ? iteracion.empezadaEn : iteracion.planPropuestoEn} ahora={ahora} />}
              <span className="sep" />
              Pasos: {iteracion.presupuesto.usado} de {iteracion.presupuesto.limite} llamadas
              <span style={{ width: 90, display: 'inline-block' }}>
                <Barra fraccion={iteracion.presupuesto.usado / iteracion.presupuesto.limite} />
              </span>
            </span>
          }
        >
          <div className="tarjeta">
            <PlanEnVivo
              iteracion={iteracion}
              ahora={ahora}
              onDetenerPista={(id, ind) => acciones.detenerPista(id, ind)}
              onEditarPlan={viva ? (plan) => acciones.editarPlan(iteracion.id, plan) : undefined}
              onAprobarPlan={viva ? () => acciones.aprobarPlan(iteracion.id) : undefined}
            />
          </div>
          {viva && (
            // Visible durante toda la corrida, no solo mientras un plan espera: dos
            // corridas perdieron su tiempo porque la casilla solo aparecía en ese
            // momento y nadie la vio (Emir, 17 de septiembre de 2026). Desde hoy la
            // corrida nace con la autoaprobación encendida; aquí se apaga o se enciende.
            <label className="interruptor">
              <input type="checkbox" checked={corrida.autoAprobarPlanSegundos !== null} onChange={(e) => acciones.fijarAutoaprobacionPlan(corrida.id, e.target.checked ? 60 : null)} />
              Autoaprobar cada plan si no respondo en 60 segundos. Si está apagado, Rosa espera lo que haga falta y ese tiempo de espera no cuenta contra el tope de la corrida.
            </label>
          )}
          {viva && iteracion.planAprobado && (
            <div className="dirigir">
              <textarea
                className="entrada"
                value={indicacion}
                rows={1}
                placeholder="Dirigir la corrida: una indicación que entra al plan tras el paso actual"
                onChange={(e) => setIndicacion(e.target.value)}
                aria-label="Indicación para Rosa"
              />
              <button
                type="button"
                className="btn"
                disabled={indicacion.trim() === ''}
                onClick={() => {
                  acciones.dirigirCorrida(corrida.id, indicacion);
                  setIndicacion('');
                }}
              >
                Dirigir
              </button>
            </div>
          )}
        </Seccion>
      )}

      {procesosVivos.length > 0 && (
        <Seccion detalle titulo="Cómputo en marcha" nota="Cada proceso vivo. Detenerlo con una indicación se la pasa a Rosa como paso del plan (por ejemplo: rehazlo con menos memoria).">
          <table className="tabla">
            <thead>
              <tr>
                <th>Proceso</th>
                <th>Dónde</th>
                <th className="num">CPU</th>
                <th className="num">Memoria</th>
                <th>Desde</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {procesosVivos.map((p) => (
                <tr key={p.id}>
                  <td>{p.nombre}</td>
                  <td className="mono">{p.host}</td>
                  <td className="num">{p.cpu} %</td>
                  <td className="num">{p.memoriaMb > 0 ? `${(p.memoriaMb / 1000).toFixed(1).replace('.', ',')} GB` : ''}</td>
                  <td>
                    <Momento t={p.empezadoEn} ahora={ahora} soloRelativo />
                  </td>
                  <td>
                    <div className="dirigir">
                      <input className="entrada entrada-s" value={indicacionProceso[p.id] ?? ''} placeholder="Indicación (opcional)" onChange={(e) => setIndicacionProceso({ ...indicacionProceso, [p.id]: e.target.value })} aria-label={`Indicación al detener ${p.nombre}`} />
                      <button type="button" className="btn btn-s btn-peligro" onClick={() => acciones.detenerProceso(corrida.id, p.id, indicacionProceso[p.id] ?? '')}>
                        Detener
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Seccion>
      )}

      <Trazabilidad corrida={corrida} activa={estado.conexion !== 'muestra'} />

      <Seccion
        detalle titulo="Búsqueda de la corrida"
        nota="El flujo de la búsqueda (identificados, cribados, leídos a texto completo, usados) y las consultas exactas con fecha: la estrategia reproducible que pide cualquier revisor."
        acciones={
          <div className="acciones">
            <button type="button" className="btn btn-s" title="Descarga el flujo en PRISMA 2020 (variables oficiales del diagrama, ítems 6, 7, 8, 16a y 16b), la extensión para revisiones vivas y la declaración de la IA usada, en JSON y en Markdown. Sin ningún modelo: sale del registro." onClick={() => void acciones.exportarPrisma(corrida.id)}>
              Exportar PRISMA 2020
            </button>
            <button type="button" className="btn btn-fantasma btn-s" onClick={() => setVerBusqueda((v) => !v)}>
              {verBusqueda ? 'Ocultar' : 'Ver'}
            </button>
          </div>
        }
      >
        <div className="prisma">
          {[
            ['Identificados', corrida.busqueda.identificados],
            ['Cribados', corrida.busqueda.cribados],
            ['Texto completo', corrida.busqueda.textoCompleto],
            ['Usados en hipótesis', corrida.busqueda.usados],
          ].map(([et, n], i) => (
            <div key={et} className="prisma-caja">
              <strong>{formatearEntero(Number(n))}</strong>
              <span>{et}</span>
              {i < 3 && <i aria-hidden="true" />}
            </div>
          ))}
        </div>
        {verBusqueda && (
          <table className="tabla">
            <thead>
              <tr>
                <th>Modo</th>
                <th>Base</th>
                <th>Consulta exacta</th>
                <th>Fecha</th>
                <th className="num">Resultados</th>
                <th className="num">Relevantes</th>
              </tr>
            </thead>
            <tbody>
              {corrida.busqueda.consultas.map((c, i) => (
                <tr key={i}>
                  <td>
                    <Chip tono={c.modo === 'amplitud' ? 'acento' : 'borde'} title={c.modo === 'amplitud' && c.porque ? `Amplitud. Por qué: ${c.porque}` : MODO_BUSQUEDA[c.modo ?? 'foco'].nota}>
                      {MODO_BUSQUEDA[c.modo ?? 'foco'].etiqueta}
                    </Chip>
                  </td>
                  <td>{c.base}</td>
                  <td className="mono" style={{ overflowWrap: 'anywhere' }}>
                    {c.consulta}
                  </td>
                  <td>
                    <Momento t={c.fecha} ahora={ahora} />
                  </td>
                  <td className="num">{c.resultados}</td>
                  <td className="num">{c.relevantes ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Seccion>

      {anteriores.length > 0 && (
        <Seccion titulo="Iteraciones anteriores" nota="Volver a un punto abre una iteración nueva con el plan de esa (y, si quieres, el modelo de mundo como estaba). Bifurcar crea una investigación hermana desde ahí.">
          <div className="iteraciones-lista">
            {anteriores.map((it) => (
              <div key={it.id} className="iteracion-fila iteracion-fila-acciones">
                <strong>#{it.numero}</strong>
                <div>
                  <span>{it.resumen || 'Sin resumen'}</span>
                  <RevisionDeRegistro r={it.revisionRegistro} compacto />
                  {it.plan.some((p) => p.estado === 'fallido') && (
                    <>
                      {' '}
                      <Chip tono="mal">
                        {it.plan.filter((p) => p.estado === 'fallido').length} {it.plan.filter((p) => p.estado === 'fallido').length === 1 ? 'paso fallido' : 'pasos fallidos'}
                      </Chip>
                    </>
                  )}
                </div>
                <span className="meta">{it.terminadaEn ? <Momento t={it.terminadaEn} ahora={ahora} /> : ''}</span>
                <div className="acciones">
                  {viva && it.terminadaEn !== null && (
                    <Confirmar
                      etiqueta="Volver aquí"
                      clase="btn-s"
                      pregunta={`Se abre una iteración nueva con el plan de la ${it.numero} y se cierra la actual. Elige que restaurar.`}
                      extra={<VolverOpciones onElegir={(que) => acciones.volverAIteracion(it.id, que)} />}
                      onConfirmar={() => acciones.volverAIteracion(it.id, 'plan')}
                    />
                  )}
                  <Confirmar
                    etiqueta="Bifurcar desde aquí"
                    clase="btn-s"
                    pregunta={`Se crea una investigación hermana partiendo del estado de la iteración ${it.numero}. La original sigue igual.`}
                    pedirTexto={{ etiqueta: 'Nombre de la rama (di para qué es)', marcador: 'Hipótesis rival desde este punto' }}
                    onConfirmar={(motivo) => {
                      const id = acciones.bifurcarInvestigacion(inv.id, `${motivo} (desde la iteración ${it.numero})`);
                      if (id) irA(rutaDe(id, 'corrida'));
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Seccion>
      )}

      {(resueltas.length > 0 || incidencias.some((i) => i.estado === 'resuelta')) && (
        <Seccion
          detalle titulo="Permisos e incidencias ya respondidos"
          acciones={
            <button type="button" className="btn btn-fantasma btn-s" onClick={() => setVerResueltas((v) => !v)}>
              {verResueltas ? 'Ocultar' : `Ver ${resueltas.length + incidencias.filter((i) => i.estado === 'resuelta').length}`}
            </button>
          }
        >
          {verResueltas && resueltas.map((s) => <TarjetaPermiso key={s.id} solicitud={s} ahora={ahora} horasEspera={estado.politicaEsperas.horas} onResolver={() => undefined} />)}
          {verResueltas && incidencias.filter((i) => i.estado === 'resuelta').map((i) => <TarjetaIncidencia key={i.id} incidencia={i} ahora={ahora} onResolver={() => undefined} />)}
        </Seccion>
      )}
    </div>
  );
}

function VolverOpciones({ onElegir }: { onElegir: (que: 'plan' | 'mundo' | 'ambos') => void }) {
  return (
    <div className="acciones">
      <button type="button" className="btn btn-s" onClick={() => onElegir('plan')}>
        Solo el plan
      </button>
      <button type="button" className="btn btn-s" onClick={() => onElegir('mundo')}>
        Solo el modelo de mundo
      </button>
      <button type="button" className="btn btn-s" onClick={() => onElegir('ambos')}>
        Ambos
      </button>
    </div>
  );
}

/** Estados en que la corrida espera a una persona (plan sin aprobar, permiso
 *  de gasto, pausa, presupuesto agotado): el reloj de trabajo no corre. Misma
 *  lista que ESTADOS_DE_ESPERA_HUMANA en rosa/bucle/corrida.py, más la pausa
 *  por presupuesto, que también espera a que alguien lo amplíe. */
export const ESTADOS_DE_ESPERA_HUMANA: ReadonlySet<EstadoCorrida> = new Set<EstadoCorrida>(['esperando_plan', 'esperando_aprobacion', 'pausada', 'pausada_por_presupuesto']);

export function esperandoPersona(estado: EstadoCorrida): boolean {
  return ESTADOS_DE_ESPERA_HUMANA.has(estado);
}

type CorridaConReloj = Pick<CorridaTipo, 'estado' | 'empezadaEn' | 'gasto'> & Partial<Pick<CorridaTipo, 'esperaHumanaMs' | 'pausaMs' | 'terminadaEn'>>;

function ms(x: unknown): number {
  const n = Number(x);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

/** Segundos de trabajo de la corrida en un instante dado: lo que guardó el
 *  servidor (`gasto.segundos`, que ya es tiempo de trabajo) y, solo mientras
 *  la corrida trabaja, el reloj de pared desde `empezadaEn` menos la espera a
 *  una persona (`esperaHumanaMs`) y las pausas del proceso (`pausaMs`), como
 *  hace rosa/bucle/corrida.py tiempo_trabajo_ms. Mientras espera a alguien o
 *  ya terminó, se enseña el valor guardado: el reloj no corre. Un registro
 *  antiguo sin los contadores cae al reloj de pared, como antes. */
export function segundosDeTrabajo(c: CorridaConReloj, ahora: number): number {
  const guardados = Math.max(0, Math.round(ms(c.gasto?.segundos)));
  const viva = c.estado !== 'detenida' && c.estado !== 'terminada';
  if (!viva || esperandoPersona(c.estado)) return guardados;
  // Sin fecha de arranque no hay reloj de pared que restar: enseñar
  // `ahora / 1000` sería medio siglo de trabajo.
  const empezada = ms(c.empezadaEn);
  if (empezada === 0) return guardados;
  const porReloj = Math.round((ahora - empezada - ms(c.esperaHumanaMs) - ms(c.pausaMs)) / 1000);
  return Math.max(guardados, Number.isFinite(porReloj) ? porReloj : 0);
}

/** El coste de la corrida para enseñarlo: el facturado por el AI Gateway
 *  cuando el servidor lo guardó (`gasto.usdReal`, la cifra real) con el
 *  estimado por tokens al lado; si no hay factura, solo el estimado y dicho
 *  como tal. Vacío si no hay ninguna cifra. */
export function textoCoste(g: Pick<CorridaTipo['gasto'], 'usd' | 'usdReal' | 'usdEsEstimado'>): { corto: string; principal: string; etiqueta: string; title: string } {
  const usd = (v: number) => `${v.toFixed(2).replace('.', ',')} USD`;
  const real = typeof g.usdReal === 'number' && Number.isFinite(g.usdReal) ? g.usdReal : null;
  const estimado = typeof g.usd === 'number' && Number.isFinite(g.usd) ? g.usd : null;
  if (real !== null) {
    const nota = g.usdEsEstimado ? ' (alguna llamada llegó sin coste del gateway y se estimó por tokens)' : '';
    return {
      corto: `${usd(real)} facturados por el gateway${estimado !== null ? ` (estimado por tokens: ${usd(estimado)})` : ''}`,
      principal: usd(real),
      etiqueta: `facturado por el gateway${estimado !== null ? ` · estimado por tokens: ${usd(estimado)}` : ''}`,
      title: `Lo que el AI Gateway de Vercel facturó por las llamadas de esta corrida (campo cost de cada llamada, sumado por el servidor)${nota}. La estimación por tokens usa la tabla de precios de Rosa y puede diferir.`,
    };
  }
  if (estimado !== null && estimado > 0) {
    return { corto: `${usd(estimado)} estimados por tokens`, principal: usd(estimado), etiqueta: 'estimados por tokens (el servidor no guardó la factura del gateway)', title: 'Estimación con la tabla de precios de Rosa a partir de los tokens; la factura real la da el AI Gateway y esta corrida no la trae guardada.' };
  }
  return { corto: '', principal: '', etiqueta: '', title: '' };
}

/** Segundos de trabajo, actualizados cada segundo mientras la corrida trabaja
 *  (no mientras espera a una persona ni cuando terminó). */
function useSegundosDeCorrida(corrida: CorridaConReloj): number {
  const [ahora, setAhora] = useState(() => Date.now());
  const corre = corrida.estado === 'en_marcha';
  useEffect(() => {
    if (!corre) return;
    const t = window.setInterval(() => setAhora(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [corre]);
  return segundosDeTrabajo(corrida, ahora);
}
