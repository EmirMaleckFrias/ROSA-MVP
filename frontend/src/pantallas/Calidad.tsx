// El tablero de calidad: metricas del juez, acierto por tipo de afirmacion
// (dato, literatura, interpretacion), calibracion del revisor frente a las
// decisiones humanas, agujeros de conejo (significativo pero irrelevante),
// coste por hipotesis, los casos de control (los 17 del RAG, sin aprobar) y
// las optimizaciones de GEPA con su enlace a MLflow.

import { PanelKiller } from '../componentes/Rosa2018';
import { useState } from 'react';
import { acciones } from '../datos/almacen';
import type { CasoControl, EstadoRosa, Investigacion } from '../datos/tipos';
import { IconExternal } from '../componentes/icons';
import { AvisoMuestra, Chip, Confirmar, Momento, Seccion } from '../componentes/piezas';
import { agujerosDeConejo, calibracion } from '../lib/calidad';
import { CATEGORIA_CASO, ESTADO_CASO, TIPO_AFIRMACION } from '../lib/etiquetas';
import { formatearPorcentaje } from '../lib/formato';
import { rutaDe } from '../lib/ruta';

function Caso({ c }: { c: CasoControl }) {
  const [respuesta, setRespuesta] = useState(c.respuestaEsperada);
  return (
    <article className="tarjeta caso">
      <div className="caso-cabecera">
        <Chip>{CATEGORIA_CASO[c.categoria]}</Chip>
        {c.critico && <Chip tono="aviso">Importante</Chip>}
        <Chip tono={c.estado === 'aprobado' ? 'ok' : c.estado === 'descartado' ? 'mal' : undefined}>{ESTADO_CASO[c.estado]}</Chip>
        <span className="meta" style={{ marginLeft: 'auto' }}>
          {c.origen === 'generado' ? 'Propuesto por el RAG' : 'Escrito a mano'}
        </span>
      </div>
      <p className="caso-pregunta">{c.pregunta}</p>
      <div className="campo">
        <label htmlFor={`resp-${c.clave}`}>Respuesta esperada</label>
        <textarea
          id={`resp-${c.clave}`}
          className="caso-respuesta"
          value={respuesta}
          onChange={(e) => setRespuesta(e.target.value)}
          onBlur={() => {
            if (respuesta.trim() === '') {
              setRespuesta(c.respuestaEsperada);
              return;
            }
            acciones.editarRespuestaCaso(c.clave, respuesta);
          }}
          disabled={c.estado === 'descartado'}
        />
        <small>Se guarda al salir del campo. Vaciarla no la borra: un caso sin respuesta no tiene criterio para juzgarse.</small>
      </div>
      <div className="acciones">
        {c.estado !== 'aprobado' && (
          <button type="button" className="btn btn-primario btn-s" onClick={() => acciones.cambiarEstadoCaso(c.clave, 'aprobado')}>
            Aprobar
          </button>
        )}
        {c.estado !== 'descartado' && (
          <button type="button" className="btn btn-s" onClick={() => acciones.cambiarEstadoCaso(c.clave, 'descartado')}>
            Descartar
          </button>
        )}
        {c.estado !== 'propuesto' && (
          <button type="button" className="btn btn-fantasma btn-s" onClick={() => acciones.cambiarEstadoCaso(c.clave, 'propuesto')}>
            Volver a por revisar
          </button>
        )}
      </div>
    </article>
  );
}

export function Calidad({ inv, estado, ahora }: { inv: Investigacion; estado: EstadoRosa; ahora: number }) {
  const [filtro, setFiltro] = useState<CasoControl['estado'] | 'todos'>('propuesto');
  const casos = estado.casos.filter((c) => filtro === 'todos' || c.estado === filtro);
  const aprobados = estado.casos.filter((c) => c.estado === 'aprobado').length;
  const ultima = [...estado.metricas].sort((a, b) => b.fecha - a.fecha)[0];
  const propias = estado.hipotesis.filter((h) => h.investigacionId === inv.id);
  const cal = calibracion(propias);
  const conejos = agujerosDeConejo(propias);
  const tiposCuenta = { dato: 0, literatura: 0, interpretacion: 0 };
  for (const h of propias) for (const a of h.afirmaciones) tiposCuenta[a.tipo]++;
  const costeTotal = propias.reduce((n, h) => n + h.coste.literatura + h.coste.analisis, 0);

  return (
    <div className="contenido">
      <AvisoMuestra conexion={estado.conexion} />
      <div className="pantalla-cabecera" style={{ marginTop: 16 }}>
        <div>
          <h2>Calidad</h2>
          <p>
            El juez se calibra con casos aprobados por personas antes de fijarlo. Hoy hay {aprobados} de {estado.casos.length} aprobados: con cero, las metricas de acuerdo no significan nada.
          </p>
        </div>
      </div>

      <Seccion titulo="Metricas del juez" nota={ultima ? `Ultima medicion con ${ultima.juez}` : 'Sin mediciones'} acciones={ultima ? <Momento t={ultima.fecha} ahora={ahora} /> : undefined}>
        {ultima && (
          <div className="metricas">
            <div className="gasto-item">
              <strong>{aprobados === 0 ? 'Sin casos' : formatearPorcentaje(ultima.acuerdoConHumanos)}</strong>
              <span>acuerdo con la etiqueta humana</span>
            </div>
            <div className="gasto-item">
              <strong>{formatearPorcentaje(ultima.sostenidas)}</strong>
              <span>afirmaciones sostenidas</span>
            </div>
            <div className="gasto-item">
              <strong>{formatearPorcentaje(ultima.cobertura)}</strong>
              <span>cobertura de los puntos</span>
            </div>
            <div className="gasto-item">
              <strong>{ultima.ausenciasRefutadas}</strong>
              <span>ausencias refutadas</span>
            </div>
            <div className="gasto-item">
              <strong>{ultima.entidadDistinta}</strong>
              <span>datos de otra entidad</span>
            </div>
            <div className="gasto-item">
              <strong>{formatearPorcentaje(ultima.sinVerificar)}</strong>
              <span>"sin verificar" cuando no sabe</span>
            </div>
          </div>
        )}
      </Seccion>

      <Seccion titulo="Acierto por tipo de afirmacion" nota="Kosmos midio 85 % en datos, 82 % en literatura y 58 % en interpretaciones. Rosa lo mide igual, con las afirmaciones verificadas por personas, y enseña la fiabilidad de cada tipo.">
        <div className="rejilla-3">
          {(['dato', 'literatura', 'interpretacion'] as const).map((t) => {
            const v = ultima?.aciertoPorTipo[t] ?? null;
            return (
              <div key={t} className="tarjeta">
                <div className="acciones" style={{ justifyContent: 'space-between' }}>
                  <strong style={{ fontSize: 13 }}>{TIPO_AFIRMACION[t].etiqueta}</strong>
                  <Chip tono={v === null ? 'borde' : v >= 0.8 ? 'ok' : v >= 0.65 ? 'aviso' : 'mal'}>{v === null ? 'sin medir' : formatearPorcentaje(v)}</Chip>
                </div>
                <p className="meta" style={{ marginTop: 6 }}>
                  {TIPO_AFIRMACION[t].nota} {tiposCuenta[t]} en esta investigacion.
                </p>
                {v !== null && (
                  <div className="presupuesto-barra" style={{ marginTop: 8 }}>
                    <i style={{ width: `${v * 100}%`, background: v >= 0.8 ? 'var(--green)' : v >= 0.65 ? 'var(--amber)' : 'var(--red)' }} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Seccion>

      <PanelKiller estado={estado} />

      {(() => {
        const propias = (estado.decisiones ?? []).filter((d) => d.etapa === 'persona' && typeof d.segundosRevision === 'number' && estado.hipotesis.some((h) => h.id === d.hipotesisId && h.investigacionId === inv.id));
        const media = propias.length ? propias.reduce((a, d) => a + (d.segundosRevision ?? 0), 0) / propias.length : null;
        return (
          <Seccion titulo="Carga de revision" nota="Segundos entre abrir la ficha de una hipotesis y decidir sobre ella. Es la cifra con la que se compara Rosa contra investigar sin ella: si revisar cuesta mas que hacerlo a mano, pierde.">
            <p className="meta">
              {media === null ? 'Sin decisiones humanas con tiempo medido todavia.' : `${propias.length} ${propias.length === 1 ? 'decision' : 'decisiones'} medidas; media ${Math.round(media)} s por decision (${(media / 60).toFixed(1)} min).`}
            </p>
          </Seccion>
        );
      })()}

      <Seccion titulo="Calibracion del revisor frente a las personas" nota="Que recomendaba el revisor (bloquear o pasar) frente a lo que decidio una persona. Los desacuerdos son el conjunto de entrenamiento de GEPA para el juez.">
        <div className="rejilla-2">
          <table className="tabla matriz">
            <thead>
              <tr>
                <th></th>
                <th>Persona descarto</th>
                <th>Persona acepto</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th>Revisor: bloquear</th>
                <td className="num tono-ok">{cal.bloquearYDescartada}</td>
                <td className="num tono-mal">{cal.bloquearYAceptada}</td>
              </tr>
              <tr>
                <th>Revisor: pasar</th>
                <td className="num tono-mal">{cal.pasarYDescartada}</td>
                <td className="num tono-ok">{cal.pasarYAceptada}</td>
              </tr>
            </tbody>
          </table>
          <div className="tarjeta">
            <p className="campo-etiqueta">Acuerdo</p>
            <p style={{ fontSize: 22, fontWeight: 600, marginTop: 4 }}>{cal.acuerdo === null ? 'Sin decisiones' : formatearPorcentaje(cal.acuerdo)}</p>
            {cal.desacuerdos.length > 0 ? (
              <ul className="lista-limpia" style={{ marginTop: 8 }}>
                {cal.desacuerdos.map((d) => (
                  <li key={d.id}>
                    <a className="enlace" href={rutaDe(inv.id, 'hipotesis', d.id)}>
                      {d.titulo.length > 60 ? `${d.titulo.slice(0, 57)}...` : d.titulo}
                    </a>
                    <span className="meta">
                      revisor {d.revisor}, persona {d.humano}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="meta" style={{ marginTop: 6 }}>
                Sin desacuerdos registrados.
              </p>
            )}
          </div>
        </div>
      </Seccion>

      <Seccion titulo="Agujeros de conejo y coste" nota="Hipótesis con evidencia estadística fuerte que una persona votó poco relevantes: lo que Kosmos reconoce como su fallo. Y cuánto costó cada una.">
        <div className="rejilla-2">
          <div className="tarjeta">
            <p className="campo-etiqueta">Significativas pero irrelevantes</p>
            <p style={{ fontSize: 22, fontWeight: 600, marginTop: 4 }}>{conejos.length}</p>
            {conejos.map((h) => (
              <a key={h.id} className="enlace" href={rutaDe(inv.id, 'hipotesis', h.id)} style={{ display: 'block', fontSize: 13 }}>
                {h.titulo}
              </a>
            ))}
          </div>
          <div className="tarjeta">
            <p className="campo-etiqueta">Coste por hipotesis</p>
            <p style={{ fontSize: 22, fontWeight: 600, marginTop: 4 }}>{costeTotal.toFixed(1).replace('.', ',')} $ en total</p>
            <table className="tabla" style={{ marginTop: 6 }}>
              <tbody>
                {[...propias]
                  .sort((a, b) => b.coste.literatura + b.coste.analisis - (a.coste.literatura + a.coste.analisis))
                  .map((h) => (
                    <tr key={h.id}>
                      <td>
                        <a className="enlace" href={rutaDe(inv.id, 'hipotesis', h.id)}>
                          {h.titulo.length > 50 ? `${h.titulo.slice(0, 47)}...` : h.titulo}
                        </a>
                      </td>
                      <td className="num">{(h.coste.literatura + h.coste.analisis).toFixed(1).replace('.', ',')} $</td>
                      <td className="num meta">Elo {h.elo}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      </Seccion>

      <Seccion
        titulo="Casos de control"
        nota="Los 17 los propuso el RAG sobre otro corpus y ninguno esta aprobado. Sirven para probar el ciclo; los del dominio del Alzheimer hay que escribirlos con el compañero."
        acciones={
          <div className="segmentos" role="group" aria-label="Filtro de casos">
            {(['propuesto', 'aprobado', 'descartado', 'todos'] as const).map((f) => (
              <button key={f} type="button" aria-pressed={filtro === f} onClick={() => setFiltro(f)}>
                {f === 'todos' ? 'Todos' : ESTADO_CASO[f]}
              </button>
            ))}
          </div>
        }
      >
        {casos.length === 0 ? <p className="meta">Ningun caso en este estado.</p> : casos.map((c) => <Caso key={c.clave} c={c} />)}
      </Seccion>

      <Seccion titulo="Optimizaciones con GEPA" nota="Cada compilacion queda registrada en MLflow con sus evaluaciones anidadas; el detalle se abre alli.">
        <table className="tabla">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Programa</th>
              <th>Presupuesto</th>
              <th className="num">Metrica inicial</th>
              <th className="num">Metrica final</th>
              <th className="num">Candidatos</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {[...estado.gepa]
              .sort((a, b) => b.fecha - a.fecha)
              .map((g) => (
                <tr key={g.id}>
                  <td>
                    <Momento t={g.fecha} ahora={ahora} />
                  </td>
                  <td className="mono">{g.programa}</td>
                  <td>{g.presupuesto}</td>
                  <td className="num">{formatearPorcentaje(g.metricaInicial)}</td>
                  <td className={`num ${g.metricaFinal > g.metricaInicial ? 'subida' : ''}`}>{formatearPorcentaje(g.metricaFinal)}</td>
                  <td className="num">{g.candidatos}</td>
                  <td>{g.estado === 'en_marcha' ? <Chip tono="acento">En marcha</Chip> : g.estado === 'terminada' ? <Chip tono="ok">Terminada</Chip> : <Chip tono="mal">Fallida</Chip>}</td>
                  <td>
                    <a className="enlace" href={g.enlaceMlflow} target="_blank" rel="noopener noreferrer">
                      MLflow <IconExternal />
                    </a>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
        <div>
          <Confirmar
            etiqueta="Lanzar una optimizacion"
            pregunta="Cuando Rosa este conectada, esto compila el programa elegido con GEPA contra los casos aprobados. Hoy no hay casos aprobados ni bucle conectado."
            disabled={estado.conexion === 'muestra'}
            onConfirmar={() => undefined}
          />
          {estado.conexion === 'muestra' && (
            <p className="meta" style={{ marginTop: 6 }}>
              Disponible cuando Rosa este conectada y haya casos aprobados. El ejemplo `rosa/ejemplo_gepa.py` ya compila un extractor de afirmaciones contra el gateway.
            </p>
          )}
        </div>
      </Seccion>
    </div>
  );
}
