// Inicio: "ahora" en cada investigacion (que hace Rosa, que espera), y el
// resumen "mientras no estabas" de la que tiene actividad. Es la pantalla
// del que vuelve tras horas, como el dashboard con tarjetas "Now" de Claude
// Science y el recap de la vista de agentes de Claude Code.

import { acciones } from '../datos/almacen';
import type { EstadoRosa } from '../datos/tipos';
import { iteracionActualDe } from '../datos/acciones';
import { Resumen } from '../componentes/Resumen';
import { Aparece } from '../componentes/Animado';
import { Chip, Momento, Vacio } from '../componentes/piezas';
import { digest, loQueEspera } from '../lib/digest';
import { ESTADO_CORRIDA, etiquetaCorrida, proponiendoPlan } from '../lib/etiquetas';
import { formatearDuracion } from '../lib/formato';
import { rutaDe } from '../lib/ruta';

export function Inicio({ estado, ahora }: { estado: EstadoRosa; ahora: number }) {
  return (
    <div className="contenido">
      <div className="pantalla-cabecera">
        <div>
          <h2>Investigaciones</h2>
          <p>Cada investigación tiene su objetivo, sus límites y su condición de parada. Rosa corre dentro de ellos y tu revisas lo que propone.</p>
        </div>
        <a className="btn btn-primario" href="#/nueva">
          Nueva investigacion
        </a>
      </div>

      {estado.investigaciones.map((inv) => {
        const d = digest(estado, inv.id, ahora);
        if (d.eventos.length === 0 && d.esperan.total === 0) return null;
        return <Resumen key={inv.id} d={d} titulo={inv.titulo} ahora={ahora} onVisto={() => acciones.marcarVisita()} />;
      })}

      {estado.investigaciones.length === 0 ? (
        <Vacio
          titulo="Todavía no hay investigaciones"
          pasos={['Escribes el objetivo, los límites y la condición de parada.', 'Rosa propone la misión y el plan de la primera iteración; tu lo apruebas.', 'Busca literatura, verifica, actualiza el modelo de mundo y genera hipótesis.', 'Tu decides sobre las hipótesis; las candidatas van al laboratorio con prerregistro.']}
          accion={
            <a className="btn btn-primario" href="#/nueva">
              Crear la primera investigacion
            </a>
          }
        >
          Una investigacion es un objetivo con sus limites y su condicion de parada. Rosa corre dentro de ellos.
        </Vacio>
      ) : (
        <div className="inicio-rejilla" style={{ marginTop: 20 }}>
          {estado.investigaciones.map((inv, idx) => {
            const corrida = estado.corridas.filter((c) => c.investigacionId === inv.id).sort((a, b) => b.numero - a.numero)[0];
            const it = corrida ? iteracionActualDe(estado, corrida) : null;
            const enCurso = it?.plan.find((p) => p.estado === 'en_curso');
            const espera = loQueEspera(estado, inv.id, ahora);
            const pistasVivas = it?.pistas.filter((p) => p.estado === 'en_curso').length ?? 0;
            return (
              <Aparece key={inv.id} retraso={idx * 0.05}>
              <a className="tarjeta tarjeta-interactiva inicio-tarjeta" href={rutaDe(inv.id, 'corrida')}>
                <h3>{inv.titulo}</h3>
                {corrida ? (
                  <div className="ahora">
                    <Chip tono={corrida.estado === 'en_marcha' ? 'acento' : corrida.estado === 'esperando_plan' || corrida.estado === 'esperando_aprobacion' || corrida.estado === 'pausada_por_presupuesto' ? 'aviso' : undefined}>
                      Corrida {corrida.numero} · {etiquetaCorrida(corrida, it)}
                    </Chip>
                    <p>
                      {corrida.estado === 'en_marcha' && enCurso ? (
                        <>
                          Iteración {corrida.iteracionActual}: <span className="shimmer-text">{enCurso.titulo.toLowerCase()}</span>
                          {pistasVivas > 0 && ` (${pistasVivas} ${pistasVivas === 1 ? 'pista' : 'pistas'} en paralelo)`}
                        </>
                      ) : corrida.estado === 'esperando_plan' ? (
                        proponiendoPlan(corrida, it) ? `Rosa está escribiendo el plan de la iteración ${corrida.iteracionActual}; en uno o dos minutos te lo enseña` : `El plan de la iteración ${corrida.iteracionActual} espera tu aprobación`
                      ) : corrida.motivoCierre ? (
                        corrida.motivoCierre
                      ) : (
                        ESTADO_CORRIDA[corrida.estado]
                      )}
                    </p>
                  </div>
                ) : (
                  <p>{inv.objetivo}</p>
                )}
                <footer>
                  {espera.total > 0 ? (
                    <Chip tono={espera.masAntiguaMs > estado.politicaEsperas.horas * 3_600_000 ? 'mal' : 'aviso'}>
                      {espera.total} {espera.total === 1 ? 'decision espera' : 'decisiones esperan'}
                      {espera.masAntiguaMs > 60_000 && ` · la más antigua ${formatearDuracion(espera.masAntiguaMs)}`}
                    </Chip>
                  ) : (
                    <Chip tono="ok">Nada espera</Chip>
                  )}
                  {inv.ramaDe && <Chip tono="borde">Rama</Chip>}
                  {inv.vigilarLiteraturaHasta && inv.vigilarLiteraturaHasta > ahora && <Chip tono="borde">Vigilando literatura</Chip>}
                  <span>
                    Creada <Momento t={inv.creadaEn} ahora={ahora} soloRelativo />
                  </span>
                </footer>
              </a>
              </Aparece>
            );
          })}
        </div>
      )}
    </div>
  );
}
