// Ajustes: permisos concedidos (revocables), dial de autonomia por clase de
// accion, politica de esperas (que pasa con una decision que nadie toma),
// memoria de Rosa sobre la investigadora, criterios propios de revision,
// planes guardados, avisos por Slack o correo con el resumen diario, y
// apariencia.

import { useState } from 'react';
import { acciones } from '../datos/almacen';
import { sugerenciasDeAutonomia } from '../datos/acciones';
import type { ClaseAccion, EstadoRosa, NivelAutonomia, PoliticaEsperas } from '../datos/tipos';
import { IconTrash } from '../componentes/icons';
import { Chip, Confirmar, Momento, Seccion } from '../componentes/piezas';
import { Conectores, Politicas, RegistroAprendizaje, RegistroMetodos } from '../componentes/Rosa2018';
import { digest, digestComoTexto } from '../lib/digest';
import { ACCION_ESPERA, ALCANCE, CLASE_ACCION, NIVEL_AUTONOMIA, TIPO_PERMISO } from '../lib/etiquetas';
import { useTema, type Tema } from '../lib/theme';

const CRITERIOS_INTEGRADOS = [
  'Toda afirmacion lleva una cita que resuelve a la pagina exacta del dato.',
  'Un identificador (NCT, DOI, PMID) que no aparece en el fragmento citado no se sostiene.',
  'Un dato de otra entidad (otro farmaco, cohorte, estudio) se marca aunque la cifra sea real.',
  'Una declaracion de ausencia desmentida por el corpus se bloquea.',
  'Nada se aprueba por omision: sin veredicto es "sin verificar".',
  'Una "ausencia refutada" solo vale si la busqueda del tema ha convergido.',
];

function Recuerdo({ id, texto }: { id: string; texto: string }) {
  const [valor, setValor] = useState(texto);
  return (
    <li>
      <textarea
        className="entrada"
        value={valor}
        rows={2}
        onChange={(e) => setValor(e.target.value)}
        onBlur={() => {
          if (valor.trim() === '') setValor(texto);
          else acciones.editarRecuerdo(id, valor);
        }}
        aria-label="Recuerdo"
      />
      <button type="button" className="btn btn-fantasma btn-icono" aria-label="Borrar recuerdo" onClick={() => acciones.borrarRecuerdo(id)}>
        <IconTrash size={14} />
      </button>
    </li>
  );
}

export function Ajustes({ estado, ahora }: { estado: EstadoRosa; ahora: number }) {
  const [tema, setTema] = useTema();
  const [criterio, setCriterio] = useState('');
  const [politica, setPolitica] = useState<PoliticaEsperas>(estado.politicaEsperas);
  const avisos = estado.avisos;
  const sugerencias = sugerenciasDeAutonomia(estado);
  const inv = estado.investigaciones[0];
  const ejemploDigest = inv ? digestComoTexto(digest(estado, inv.id, ahora), inv.titulo) : '';

  return (
    <div className="contenido" style={{ maxWidth: 860 }}>
      <div className="pantalla-cabecera">
        <div>
          <h2>Ajustes</h2>
          <p>Todo lo que Rosa tiene concedido o recuerda, en un sitio, y revocable.</p>
        </div>
      </div>

      <Seccion titulo="Autonomia por clase de accion" nota="Que puede hacer Rosa sola, que pregunta antes y que solo sugiere. Es mas fino que un permiso por recurso: el estudio de Anthropic de 2026 muestra que aprobar todo crea friccion sin seguridad.">
        <table className="tabla">
          <thead>
            <tr>
              <th>Accion</th>
              {(['sugerir', 'preguntar', 'actuar'] as NivelAutonomia[]).map((n) => (
                <th key={n}>{NIVEL_AUTONOMIA[n]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(Object.keys(CLASE_ACCION) as ClaseAccion[]).map((c) => (
              <tr key={c}>
                <td>{CLASE_ACCION[c]}</td>
                {(['sugerir', 'preguntar', 'actuar'] as NivelAutonomia[]).map((n) => (
                  <td key={n}>
                    <input type="radio" name={`aut-${c}`} checked={estado.autonomia[c] === n} onChange={() => acciones.fijarAutonomia(c, n)} aria-label={`${CLASE_ACCION[c]}: ${NIVEL_AUTONOMIA[n]}`} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {sugerencias.length > 0 && (
          <div className="aviso-muestra">
            Rosa ha visto que has concedido {sugerencias.map((s) => `${s.veces} permisos de "${TIPO_PERMISO[s.tipo as keyof typeof TIPO_PERMISO] ?? s.tipo}"`).join(' y ')} con alcance amplio. Si quieres, sube esa clase a "actuar y avisar" en la tabla.
          </div>
        )}
      </Seccion>

      <Seccion titulo="Que pasa con una decision que nadie toma" nota="En una corrida de dias la cola envejece. Esto lo decide una persona, nunca la interfaz por accidente.">
        <div className="tarjeta seccion">
          <div className="rejilla-3">
            <div className="campo">
              <label htmlFor="pe-horas">Horas de espera</label>
              <input id="pe-horas" type="number" min={1} value={politica.horas} onChange={(e) => setPolitica({ ...politica, horas: Number(e.target.value) })} />
            </div>
            <div className="campo">
              <label htmlFor="pe-accion">Entonces</label>
              <select id="pe-accion" value={politica.accion} onChange={(e) => setPolitica({ ...politica, accion: e.target.value as PoliticaEsperas['accion'] })}>
                {(Object.keys(ACCION_ESPERA) as PoliticaEsperas['accion'][]).map((a) => (
                  <option key={a} value={a}>
                    {ACCION_ESPERA[a]}
                  </option>
                ))}
              </select>
            </div>
            <div className="campo">
              <label htmlFor="pe-escalar">Escalar a</label>
              <input id="pe-escalar" value={politica.escalarA} disabled={politica.accion !== 'escalar'} onChange={(e) => setPolitica({ ...politica, escalarA: e.target.value })} />
            </div>
          </div>
          <div className="acciones">
            <button type="button" className="btn btn-primario btn-s" disabled={JSON.stringify(politica) === JSON.stringify(estado.politicaEsperas)} onClick={() => acciones.actualizarPoliticaEsperas(politica)}>
              Guardar
            </button>
            <span className="meta">
              Hoy: si nadie decide en {estado.politicaEsperas.horas} h, {ACCION_ESPERA[estado.politicaEsperas.accion].toLowerCase()}
              {estado.politicaEsperas.accion === 'escalar' ? ` (${estado.politicaEsperas.escalarA})` : ''}.
            </span>
          </div>
        </div>
      </Seccion>

      <Seccion titulo="Permisos concedidos" nota="Lo que has permitido con alcance mayor que una vez. Revocar hace que Rosa vuelva a pedirlo con una tarjeta.">
        {estado.permisos.length === 0 ? (
          <p className="meta">Sin permisos concedidos.</p>
        ) : (
          <div>
            {estado.permisos.map((p) => {
              const i = p.investigacionId ? estado.investigaciones.find((x) => x.id === p.investigacionId) : null;
              return (
                <div key={p.id} className="ajuste-fila">
                  <div>
                    <span className="mono">{p.recurso}</span>
                    <small>
                      {TIPO_PERMISO[p.tipo]} · {ALCANCE[p.alcance]}
                      {i ? ` · ${i.titulo}` : ''} · <Momento t={p.concedidoEn} ahora={ahora} />
                    </small>
                  </div>
                  <Confirmar etiqueta="Revocar" pregunta="Rosa dejara de tener este acceso y lo pedira de nuevo si lo necesita." onConfirmar={() => acciones.revocarPermiso(p.id)} />
                </div>
              );
            })}
          </div>
        )}
      </Seccion>

      <Seccion titulo="Memoria de Rosa sobre ti" nota="Hechos cortos sobre la investigadora y sus preferencias. Aparte del modelo de mundo, que es de la investigacion.">
        {estado.memoria.length === 0 ? (
          <p className="meta">Rosa no recuerda nada todavia.</p>
        ) : (
          <ul className="lista-limpia">
            {estado.memoria.map((r) => (
              <Recuerdo key={r.id} id={r.id} texto={r.texto} />
            ))}
          </ul>
        )}
      </Seccion>

      <Seccion titulo="Planes guardados" nota="Flujos que funcionaron, reutilizables. Rosa propone usarlos cuando la tarea se parece (memoria de planes, como Magentic-UI).">
        {estado.planesGuardados.length === 0 ? (
          <p className="meta">Sin planes guardados.</p>
        ) : (
          <ul className="lista-limpia">
            {estado.planesGuardados.map((p) => (
              <li key={p.id}>
                <div>
                  <strong style={{ fontSize: 13.5 }}>{p.nombre}</strong>
                  <p className="meta">
                    {p.pasos.join(' → ')} · usado {p.vecesUsado} {p.vecesUsado === 1 ? 'vez' : 'veces'}, {p.exitos} con exito
                  </p>
                </div>
                <button type="button" className="btn btn-fantasma btn-icono" aria-label="Borrar plan guardado" onClick={() => acciones.borrarPlanGuardado(p.id)}>
                  <IconTrash size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Seccion>

      <Seccion titulo="Criterios de revision" nota="Los tuyos se suman a los integrados y no pueden debilitarlos. Las debilidades de la meta-revision se inyectan aqui.">
        <div className="tarjeta">
          <p className="campo-etiqueta" style={{ marginBottom: 8 }}>
            Integrados (no se pueden quitar)
          </p>
          <ul className="lista-limpia">
            {CRITERIOS_INTEGRADOS.map((c) => (
              <li key={c}>
                <span className="meta">{c}</span>
              </li>
            ))}
          </ul>
        </div>
        <ul className="lista-limpia">
          {estado.criteriosRevision.map((c, i) => (
            <li key={c}>
              <span>{c}</span>
              <button type="button" className="btn btn-fantasma btn-icono" aria-label="Quitar criterio" onClick={() => acciones.borrarCriterio(i)}>
                <IconTrash size={14} />
              </button>
            </li>
          ))}
        </ul>
        <div className="dirigir">
          <textarea className="entrada" value={criterio} rows={1} placeholder="Un criterio nuevo: 'Toda cifra de eficacia lleva el nombre del ensayo'" onChange={(e) => setCriterio(e.target.value)} aria-label="Criterio nuevo" />
          <button
            type="button"
            className="btn"
            disabled={criterio.trim() === ''}
            onClick={() => {
              acciones.anadirCriterio(criterio);
              setCriterio('');
            }}
          >
            Anadir
          </button>
        </div>
      </Seccion>

      <RegistroAprendizaje estado={estado} ahora={ahora} />

      <RegistroMetodos metodos={estado.metodos} ahora={ahora} />

      <Politicas politicas={estado.politicas} />

      <Conectores conectores={estado.conectores} />

      <Seccion titulo="Avisos" nota="El bucle trabaja cuando nadie mira. Aqui se decide como te enteras, y el resumen diario es el mismo 'mientras no estabas' que ves al entrar.">
        <div className="tarjeta seccion">
          <label className="interruptor">
            <input type="checkbox" checked={avisos.slack.activo} onChange={(e) => acciones.actualizarAvisos({ ...avisos, slack: { ...avisos.slack, activo: e.target.checked } })} />
            Slack
          </label>
          {avisos.slack.activo && (
            <div className="campo">
              <label htmlFor="slack-canal">Canal</label>
              <input id="slack-canal" value={avisos.slack.canal} onChange={(e) => acciones.actualizarAvisos({ ...avisos, slack: { ...avisos.slack, canal: e.target.value } })} />
              <small>La conexion con Slack se hara con un boton "Conectar con Slack" cuando Rosa este en su servidor; aqui solo se elige el canal.</small>
            </div>
          )}
          <label className="interruptor">
            <input type="checkbox" checked={avisos.correo.activo} onChange={(e) => acciones.actualizarAvisos({ ...avisos, correo: { ...avisos.correo, activo: e.target.checked } })} />
            Correo
          </label>
          {avisos.correo.activo && (
            <div className="campo">
              <label htmlFor="correo-dir">Direccion</label>
              <input id="correo-dir" type="email" value={avisos.correo.direccion} onChange={(e) => acciones.actualizarAvisos({ ...avisos, correo: { ...avisos.correo, direccion: e.target.value } })} />
            </div>
          )}
          <p className="campo-etiqueta">Avisar cuando</p>
          <label className="interruptor">
            <input type="checkbox" checked={avisos.cuando.hipotesisNueva} onChange={(e) => acciones.actualizarAvisos({ ...avisos, cuando: { ...avisos.cuando, hipotesisNueva: e.target.checked } })} />
            Hay una hipotesis nueva en la cola
          </label>
          <label className="interruptor">
            <input type="checkbox" checked={avisos.cuando.permisoPendiente} onChange={(e) => acciones.actualizarAvisos({ ...avisos, cuando: { ...avisos.cuando, permisoPendiente: e.target.checked } })} />
            Rosa espera un permiso o tiene una incidencia
          </label>
          <label className="interruptor">
            <input type="checkbox" checked={avisos.cuando.corridaDetenida} onChange={(e) => acciones.actualizarAvisos({ ...avisos, cuando: { ...avisos.cuando, corridaDetenida: e.target.checked } })} />
            Una corrida se detiene, se pausa por presupuesto o termina
          </label>
          <label className="interruptor">
            <input type="checkbox" checked={avisos.cuando.resumenDiario} onChange={(e) => acciones.actualizarAvisos({ ...avisos, cuando: { ...avisos.cuando, resumenDiario: e.target.checked } })} />
            Resumen diario "mientras no estabas"
          </label>
          {avisos.cuando.resumenDiario && ejemploDigest !== '' && (
            <div>
              <p className="campo-etiqueta">Asi se veria hoy</p>
              <pre className="registro">{ejemploDigest}</pre>
            </div>
          )}
        </div>
      </Seccion>

      <Seccion titulo="Apariencia">
        <div className="segmentos" role="group" aria-label="Tema">
          {(['sistema', 'claro', 'oscuro'] as Tema[]).map((t) => (
            <button key={t} type="button" aria-pressed={tema === t} onClick={() => setTema(t)}>
              {t === 'sistema' ? 'Como el sistema' : t === 'claro' ? 'Claro' : 'Oscuro'}
            </button>
          ))}
        </div>
      </Seccion>

      <Seccion titulo="Modelos de Rosa" nota="Piezas intercambiables dentro de Rosa, todas por el AI Gateway de Vercel. Se cambian por la metrica, no por el precio. Cuando un modelo se niega (content-filter), aparece una incidencia en la corrida con la alternativa.">
        <table className="tabla">
          <tbody>
            <tr>
              <td>Cerebro del bucle</td>
              <td className="mono">openai/gpt-6-astra</td>
              <td>
                <Chip tono="ok">Elegido</Chip>
              </td>
            </tr>
            <tr>
              <td>Juez del verificador</td>
              <td className="mono">anthropic/claude-opus-5</td>
              <td>
                <Chip tono="aviso">A confirmar frente a Astra con casos aprobados</Chip>
              </td>
            </tr>
            <tr>
              <td>Alto volumen sin veto</td>
              <td className="mono">anthropic/claude-sonnet-5</td>
              <td>
                <Chip tono="ok">Elegido</Chip>
              </td>
            </tr>
            <tr>
              <td>Reserva</td>
              <td className="mono">anthropic/claude-fable-5.1</td>
              <td>
                <Chip tono="mal">Fuera: filtros de doble uso en biologia</Chip>
              </td>
            </tr>
          </tbody>
        </table>
      </Seccion>
    </div>
  );
}
