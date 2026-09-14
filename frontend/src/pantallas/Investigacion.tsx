// Objetivo, limites, condicion de parada y revisores; la configuracion que
// Rosa lee (editable); los datos con su contrato (comprobacion previa,
// diccionario, clasificacion de sensibilidad) y el catalogo de datos del
// Alzheimer; bifurcar; y las corridas.

import { useState } from 'react';
import { acciones } from '../datos/almacen';
import type { Dataset, EstadoRosa, Investigacion as Inv } from '../datos/tipos';
import { Chip, Confirmar, Momento, Seccion } from '../componentes/piezas';
import { ConocimientoOperativoDelLaboratorio, FormularioMision, Jerarquia, LibroDeProcedencia, MemoriaDelProyecto, PuertaYReproducciones, SubirDataset } from '../componentes/Rosa2018';
import { CLASIFICACION_DATOS, ESTADO_CORRIDA, ESTADO_INVESTIGACION } from '../lib/etiquetas';
import { formatearDuracion } from '../lib/formato';
import { partesAutomatizadas, textoAutomatizacion } from '../lib/parada';
import { rutaDe } from '../lib/ruta';

/** Catalogo de datos del Alzheimer, como el de Biomni-AD. Acceso abierto o
 *  controlado; lo controlado pasa por acuerdo de uso y, si hay personas, por
 *  desidentificacion y comite. */
const CATALOGO: { nombre: string; descripcion: string; acceso: 'abierto' | 'controlado'; tamanoMb: number; columnas: number; clasificacion: Dataset['clasificacion'] }[] = [
  { nombre: 'NIAGADS GenomicsDB (GWAS)', descripcion: '69 conjuntos de estadísticas GWAS, 150 millones de variantes anotadas.', acceso: 'abierto', tamanoMb: 2_400, columnas: 12, clasificacion: 'publico' },
  { nombre: 'ADSP (WGS/WES)', descripcion: 'Secuenciacion completa del Alzheimer Disease Sequencing Project.', acceso: 'controlado', tamanoMb: 900_000, columnas: 40, clasificacion: 'personas' },
  { nombre: 'SEA-AD (Allen Institute)', descripcion: 'Single-nucleus de corteza en envejecimiento y Alzheimer.', acceso: 'abierto', tamanoMb: 18_000, columnas: 30, clasificacion: 'publico' },
  { nombre: 'ROSMAP (vía AD Knowledge Portal)', descripcion: 'Cohortes longitudinales con multiomica; acuerdo de uso en Synapse.', acceso: 'controlado', tamanoMb: 45_000, columnas: 120, clasificacion: 'personas' },
  { nombre: 'ssREAD', descripcion: 'Atlas de single-cell y espacial de Alzheimer.', acceso: 'abierto', tamanoMb: 12_000, columnas: 25, clasificacion: 'publico' },
  { nombre: 'OASIS-4', descripcion: 'Imagen y clínica longitudinal.', acceso: 'controlado', tamanoMb: 60_000, columnas: 80, clasificacion: 'personas' },
  { nombre: 'GEO (expresión, RNA-Seq)', descripcion: 'Conjuntos de expresión públicos, por accession.', acceso: 'abierto', tamanoMb: 500, columnas: 20, clasificacion: 'publico' },
];

function TarjetaDataset({ d, inv }: { d: Dataset; inv: Inv }) {
  const limpio = d.columnasSinDiccionario === 0 && d.valoresCentinela === 0 && d.nombresDuplicados === 0;
  return (
    <article className="tarjeta dataset">
      <div className="acciones" style={{ justifyContent: 'space-between' }}>
        <div>
          <strong className="mono" style={{ fontSize: 13 }}>
            {d.nombre}
          </strong>
          <p className="meta">
            {d.descripcion} · {d.tamanoMb >= 1000 ? `${(d.tamanoMb / 1000).toFixed(1).replace('.', ',')} GB` : `${d.tamanoMb} MB`} · {d.columnas} columnas
          </p>
        </div>
        <Chip tono={d.estado === 'aprobado' ? 'ok' : d.estado === 'rechazado' ? 'mal' : 'aviso'}>{d.estado === 'aprobado' ? 'Contrato aprobado' : d.estado === 'rechazado' ? 'Rechazado' : 'Comprobación pendiente'}</Chip>
      </div>
      <div className="comprobacion-datos">
        <div className={d.columnasSinDiccionario > 0 ? 'mal' : 'ok'}>
          <strong>{d.columnasSinDiccionario}</strong>
          <span>columnas sin diccionario</span>
          {d.columnasSinDiccionario > 0 && (
            <button type="button" className="btn btn-s" onClick={() => acciones.aprobarDiccionario(inv.id, d.id)}>
              Aprobar el diccionario que propone Rosa
            </button>
          )}
        </div>
        <div className={d.valoresCentinela > 0 ? 'mal' : 'ok'}>
          <strong>{d.valoresCentinela}</strong>
          <span>columnas con valores centinela (0, -1, "NA" como texto)</span>
        </div>
        <div className={d.nombresDuplicados > 0 ? 'mal' : 'ok'}>
          <strong>{d.nombresDuplicados}</strong>
          <span>nombres de columna duplicados entre ficheros</span>
        </div>
        {(d.valoresCentinela > 0 || d.nombresDuplicados > 0) && (
          <button type="button" className="btn btn-s" onClick={() => acciones.corregirDataset(inv.id, d.id)}>
            Marcar centinelas y duplicados como corregidos en el fichero
          </button>
        )}
      </div>
      <div className="acciones" style={{ justifyContent: 'space-between' }}>
        <label className="interruptor" style={{ gap: 6 }}>
          <span className="meta">Clasificación</span>
          <select className="entrada entrada-s" style={{ width: 'auto' }} value={d.clasificacion} onChange={(e) => acciones.clasificarDataset(inv.id, d.id, e.target.value as Dataset['clasificacion'])} aria-label="Clasificación de los datos">
            {(Object.keys(CLASIFICACION_DATOS) as Dataset['clasificacion'][]).map((c) => (
              <option key={c} value={c}>
                {CLASIFICACION_DATOS[c]}
              </option>
            ))}
          </select>
        </label>
        {d.estado === 'pendiente' && (
          <div className="acciones">
            <button type="button" className="btn btn-primario btn-s" disabled={!limpio} title={limpio ? '' : 'Primero corrige o documenta lo que falta'} onClick={() => acciones.decidirDataset(inv.id, d.id, 'aprobado')}>
              Aprobar contrato de datos
            </button>
            <button type="button" className="btn btn-s" onClick={() => acciones.decidirDataset(inv.id, d.id, 'rechazado')}>
              Rechazar
            </button>
          </div>
        )}
      </div>
      {d.clasificacion === 'personas' && (
        <p className="aviso-muestra" style={{ marginTop: 4 }}>
          Datos de personas: antes de que Rosa los toque hay que desidentificarlos (la skill deidentify corre en local, sin red) y la fase pasa por un comite certificado y por CONABIOS (Ley 172-13). Las herramientas que envian texto al gateway quedan bloqueadas para este fichero.
        </p>
      )}
      <LibroDeProcedencia inv={inv} d={d} />
    </article>
  );
}

/** Lo primero de la pantalla: que espera aqui una decision tuya, y un boton
 *  que te lleva a cada cosa. Si no hay nada, lo dice. */
function QueToca({ inv, corridas, irA }: { inv: Inv; corridas: EstadoRosa['corridas']; irA: (hash: string) => void }) {
  const ir = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  const puerta = inv.puertaReproduccion;
  const pendientes = inv.datasets.filter((d) => d.estado === 'pendiente').length;
  const tareas: { texto: string; accion: () => void; etiqueta: string }[] = [];
  if (inv.mision && !inv.mision.aprobadaEn) tareas.push({ texto: 'Rosa propuso la misión (población, etapa, mecanismo, presupuesto). Falta que la apruebes o la corrijas.', accion: () => ir('mision'), etiqueta: 'Ver la misión' });
  if (pendientes > 0) tareas.push({ texto: `${pendientes} ${pendientes === 1 ? 'dataset espera' : 'datasets esperan'} que completes su libro de procedencia y lo apruebes.`, accion: () => ir('datos'), etiqueta: 'Ver los datos' });
  if (puerta && puerta.estado === 'bloqueada') tareas.push({ texto: `La puerta de reproducción esta bloqueada (${puerta.superadas} de ${puerta.requeridas}): hasta abrirla, ningun análisis con datos cuenta como descubrimiento.`, accion: () => ir('puerta'), etiqueta: 'Ver la puerta' });
  if (corridas.length === 0) tareas.push({ texto: 'Esta investigación no tiene corridas: Rosa todavía no ha empezado a trabajar en ella.', accion: () => irA(rutaDe(inv.id, 'corrida')), etiqueta: 'Arrancar la primera corrida' });
  return (
    <div className={`quetoca ${tareas.length === 0 ? 'quetoca-vacio' : ''}`} role="status">
      <strong>{tareas.length === 0 ? 'Nada te espera aquí.' : tareas.length === 1 ? 'Te espera una cosa:' : `Te esperan ${tareas.length} cosas:`}</strong>
      {tareas.length === 0 ? (
        <span className="meta"> El objetivo, la misión y los datos están en orden. Lo demas de esta pantalla es consulta.</span>
      ) : (
        <ul>
          {tareas.map((t) => (
            <li key={t.etiqueta}>
              <span>{t.texto}</span>
              <button type="button" className="btn btn-s" onClick={t.accion}>
                {t.etiqueta}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Investigacion({ inv, estado, ahora, irA }: { inv: Inv; estado: EstadoRosa; ahora: number; irA: (hash: string) => void }) {
  const corridas = estado.corridas.filter((c) => c.investigacionId === inv.id).sort((a, b) => b.numero - a.numero);
  const origen = inv.ramaDe ? estado.investigaciones.find((i) => i.id === inv.ramaDe) : null;
  const [editando, setEditando] = useState(false);
  const [pref, setPref] = useState(inv.configuracion.preferencias);
  const [atr, setAtr] = useState(inv.configuracion.atributos.join('\n'));
  const [res, setRes] = useState(inv.configuracion.restricciones.join('\n'));
  const [verCatalogo, setVerCatalogo] = useState(false);

  return (
    <div className="contenido">
      <div className="pantalla-cabecera">
        <div>
          <h2>{inv.titulo}</h2>
          <p>
            <Chip>{ESTADO_INVESTIGACION[inv.estado]}</Chip>{' '}
            {origen && (
              <>
                Rama de <a className="enlace" href={rutaDe(origen.id, 'investigacion')}>{origen.titulo}</a>
              </>
            )}
            {inv.vigilarLiteraturaHasta && inv.vigilarLiteraturaHasta > ahora && (
              <>
                {' '}
                <Chip tono="borde">Vigilando literatura hasta <Momento t={inv.vigilarLiteraturaHasta} ahora={ahora} soloRelativo /></Chip>
              </>
            )}
          </p>
        </div>
        <Confirmar
          etiqueta="Bifurcar"
          pregunta="Se crea una investigacion nueva con el mismo objetivo y una copia del modelo de mundo. La original sigue igual."
          pedirTexto={{ etiqueta: 'Nombre de la rama (di para que es)', marcador: 'Secuencia GFAP-NfL solo en Alzheimer familiar' }}
          onConfirmar={(motivo) => {
            const id = acciones.bifurcarInvestigacion(inv.id, motivo);
            if (id) irA(rutaDe(id, 'corrida'));
          }}
        />
      </div>

      <QueToca inv={inv} corridas={corridas} irA={irA} />

      <div className="rejilla-2">
        <div className="tarjeta seccion">
          <h3 style={{ fontSize: 13, fontWeight: 600 }}>Objetivo</h3>
          <p style={{ whiteSpace: 'pre-wrap' }}>{inv.objetivo}</p>
        </div>
        <div className="tarjeta seccion">
          <h3 style={{ fontSize: 13, fontWeight: 600 }}>Que cuenta como relevante</h3>
          <p>{inv.relevancia || 'Sin definir. Rosa perseguira todo lo que parezca significativo.'}</p>
        </div>
        <div className="tarjeta seccion">
          <h3 style={{ fontSize: 13, fontWeight: 600 }}>Límites</h3>
          <ul className="lista-limpia">
            {inv.limites.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </div>
        <div className="tarjeta seccion">
          <h3 style={{ fontSize: 13, fontWeight: 600 }}>Condición de parada</h3>
          <p>{inv.condicionParada}</p>
          <p className="meta">{textoAutomatizacion(inv.condicionParadaAutomatizada ?? partesAutomatizadas(inv.condicionParada))}</p>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginTop: 8 }}>Quien revisa</h3>
          <div className="acciones">
            {inv.revisores.map((r) => (
              <Chip key={r} tono="borde">
                {r}
              </Chip>
            ))}
          </div>
        </div>
      </div>

      <Seccion id="mision" titulo="Misión" nota="El marco que fija el programa antes de la primera corrida (etapa 0 de ROSA2018): a quién aplica, en qué etapa, en qué célula o tejido, qué mecanismo, qué tipo de resultado se busca, qué puede hacer el laboratorio y con qué presupuesto. Rosa propone; una persona aprueba. Debajo, las áreas de investigación que Rosa comparó para elegir por dónde empezar.">
        {inv.mision === undefined || inv.mision === null ? <p className="meta">Rosa propondra la misión al arrancar la primera corrida. También puedes escribirla tu: arriba a la derecha, "Editar".</p> : null}
        <FormularioMision inv={inv} corridas={corridas} />
      </Seccion>

      <Jerarquia inv={inv} corridas={corridas} />

      <MemoriaDelProyecto inv={inv} />
      <ConocimientoOperativoDelLaboratorio inv={inv} />

      <Seccion
        titulo="Configuración que Rosa lee"
        nota="Preferencias, atributos deseables y restricciones: alimentan la generación, cada revisión y cada debate del torneo. Se versiona con la investigación."
        acciones={
          editando ? (
            <>
              <button
                type="button"
                className="btn btn-primario btn-s"
                onClick={() => {
                  acciones.actualizarConfiguracion(inv.id, { preferencias: pref, atributos: atr.split('\n'), restricciones: res.split('\n') });
                  setEditando(false);
                }}
              >
                Guardar
              </button>
              <button type="button" className="btn btn-fantasma btn-s" onClick={() => setEditando(false)}>
                Cancelar
              </button>
            </>
          ) : (
            <button type="button" className="btn btn-s" onClick={() => setEditando(true)}>
              Editar
            </button>
          )
        }
      >
        {editando ? (
          <div className="seccion">
            <div className="campo">
              <label htmlFor="c-pref">Preferencias</label>
              <textarea id="c-pref" value={pref} rows={2} onChange={(e) => setPref(e.target.value)} />
            </div>
            <div className="rejilla-2">
              <div className="campo">
                <label htmlFor="c-atr">Atributos (uno por linea)</label>
                <textarea id="c-atr" value={atr} rows={4} onChange={(e) => setAtr(e.target.value)} />
              </div>
              <div className="campo">
                <label htmlFor="c-res">Restricciones (una por linea)</label>
                <textarea id="c-res" value={res} rows={4} onChange={(e) => setRes(e.target.value)} />
              </div>
            </div>
          </div>
        ) : (
          <div className="rejilla-3">
            <div className="tarjeta">
              <p className="campo-etiqueta">Preferencias</p>
              <p style={{ fontSize: 13, marginTop: 6 }}>{inv.configuracion.preferencias || 'Sin definir'}</p>
            </div>
            <div className="tarjeta">
              <p className="campo-etiqueta">Atributos deseables</p>
              <ul className="lista-limpia" style={{ marginTop: 6, fontSize: 13 }}>
                {inv.configuracion.atributos.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
            <div className="tarjeta">
              <p className="campo-etiqueta">Restricciones</p>
              <ul className="lista-limpia" style={{ marginTop: 6, fontSize: 13 }}>
                {inv.configuracion.restricciones.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </Seccion>

      <Seccion id="datos"
        titulo="Datos"
        nota="Antes de una corrida larga, la comprobación de datos: columnas sin diccionario, valores centinela y nombres duplicados contaminaron horas de una corrida de Kosmos. Nada se aprueba con esos contadores en rojo."
        acciones={
          <button type="button" className="btn btn-s" onClick={() => setVerCatalogo((v) => !v)}>
            {verCatalogo ? 'Ocultar catalogo' : 'Catalogo de datos del Alzheimer'}
          </button>
        }
      >
        {inv.datasets.length === 0 && <p className="meta">Sin datos adjuntos: Rosa trabaja solo con literatura y bases curadas.</p>}
        {inv.datasets.map((d) => (
          <TarjetaDataset key={d.id} d={d} inv={inv} />
        ))}
        {estado.conexion !== 'muestra' && <SubirDataset inv={inv} />}
        {verCatalogo && (
          <table className="tabla">
            <thead>
              <tr>
                <th>Conjunto</th>
                <th>Que es</th>
                <th>Acceso</th>
                <th className="num">Tamaño</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {CATALOGO.map((c) => (
                <tr key={c.nombre}>
                  <td>{c.nombre}</td>
                  <td className="meta">{c.descripcion}</td>
                  <td>
                    <Chip tono={c.acceso === 'abierto' ? 'ok' : 'aviso'}>{c.acceso === 'abierto' ? 'Abierto' : 'Controlado'}</Chip>
                  </td>
                  <td className="num">{c.tamanoMb >= 1000 ? `${Math.round(c.tamanoMb / 1000)} GB` : `${c.tamanoMb} MB`}</td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-s"
                      disabled={inv.datasets.some((d) => d.nombre === c.nombre)}
                      onClick={() =>
                        acciones.anadirDataset(inv.id, {
                          nombre: c.nombre,
                          descripcion: c.descripcion,
                          tamanoMb: c.tamanoMb,
                          columnas: c.columnas,
                          columnasSinDiccionario: 0,
                          valoresCentinela: 0,
                          nombresDuplicados: 0,
                          clasificacion: c.clasificacion,
                          origen: 'catalogo',
                        })
                      }
                    >
                      Usar en esta investigacion
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Seccion>

      <PuertaYReproducciones inv={inv} estado={estado} ahora={ahora} />

      <Seccion detalle titulo="Corridas" nota="Cada corrida es un arranque del bucle con estas instrucciones.">
        {corridas.length === 0 ? (
          <p className="meta">Sin corridas todavía.</p>
        ) : (
          <table className="tabla">
            <thead>
              <tr>
                <th>Corrida</th>
                <th>Estado</th>
                <th>Empezó</th>
                <th className="num">Iteraciones</th>
                <th className="num">Duracion</th>
                <th className="num">Llamadas</th>
                <th>Cierre</th>
              </tr>
            </thead>
            <tbody>
              {corridas.map((c) => (
                <tr key={c.id}>
                  <td>
                    <a className="enlace" href={rutaDe(inv.id, 'corrida')}>
                      Corrida {c.numero}
                    </a>
                  </td>
                  <td>{ESTADO_CORRIDA[c.estado]}</td>
                  <td>
                    <Momento t={c.empezadaEn} ahora={ahora} />
                  </td>
                  <td className="num">{c.iteracionActual}</td>
                  <td className="num">{formatearDuracion(c.gasto.segundos * 1000)}</td>
                  <td className="num">
                    {c.gasto.llamadas} / {c.presupuesto.limiteLlamadas}
                  </td>
                  <td className="meta">{c.motivoCierre ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Seccion>
    </div>
  );
}
