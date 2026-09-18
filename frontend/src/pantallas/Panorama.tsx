// El panorama de investigacion: la sintesis por encima de las hipotesis,
// como el "research overview" de Co-Scientist (direcciones principales, por
// que investigar, que investigar, idea ejemplo, y areas inesperadas), la
// meta-revision con las debilidades recurrentes de la corrida, y la
// exportacion como pagina de Specific Aims.

import { acciones } from '../datos/almacen';
import type { EstadoRosa, Investigacion } from '../datos/tipos';
import { AvisoMuestra, Chip, Momento, Seccion, Vacio, descargar } from '../componentes/piezas';
import { specificAims } from '../lib/exportar';
import { rutaDe } from '../lib/ruta';

export function Panorama({ inv, estado, ahora }: { inv: Investigacion; estado: EstadoRosa; ahora: number }) {
  const corrida = estado.corridas.filter((c) => c.investigacionId === inv.id).sort((a, b) => b.numero - a.numero)[0] ?? null;
  const hipotesis = estado.hipotesis.filter((h) => h.investigacionId === inv.id);
  const direcciones = corrida?.panorama ?? [];
  const meta = corrida?.metaRevisiones.slice().sort((a, b) => b.iteracion - a.iteracion) ?? [];
  const exportarAims = () => {
    const texto = specificAims(inv, hipotesis);
    acciones.guardarArtefacto(inv.id, 'specific-aims.md', 'specific_aims', texto, 'Generado desde el panorama', corrida?.iteracionActual ?? 0);
    descargar('specific-aims.md', texto, 'text/markdown;charset=utf-8');
  };
  return (
    <div className="contenido">
      <AvisoMuestra conexion={estado.conexion} />
      <div className="pantalla-cabecera" style={{ marginTop: 16 }}>
        <div>
          <h2>Panorama de la investigación</h2>
          <p>La síntesis por encima de las hipótesis: direcciones principales, por que y que investigar en cada una, y lo inesperado. Es lo que ROSA2018 le enseñaría a el investigador clínico principal primero.</p>
        </div>
        <button type="button" className="btn" onClick={exportarAims} disabled={hipotesis.length === 0}>
          Exportar como Specific Aims
        </button>
      </div>

      {direcciones.length === 0 ? (
        <Vacio titulo="Sin panorama todavía">ROSA2018 lo sintetiza al cerrar cada iteración a partir de las hipótesis, las revisiones y el modelo de mundo.</Vacio>
      ) : (
        <div className="seccion">
          {direcciones.map((d, i) => (
            <article key={i} className={`tarjeta direccion ${d.inesperada ? 'direccion-inesperada' : ''}`}>
              <div className="acciones" style={{ justifyContent: 'space-between' }}>
                <h3 style={{ fontSize: 15, fontWeight: 600 }}>
                  {i + 1}. {d.titulo}
                </h3>
                {d.inesperada && <Chip tono="acento">Área inesperada</Chip>}
              </div>
              <p style={{ marginTop: 6 }}>{d.razon}</p>
              <div className="rejilla-3" style={{ marginTop: 12 }}>
                <div>
                  <p className="campo-etiqueta">Hallazgos recientes</p>
                  <ul className="lista-limpia" style={{ fontSize: 13, marginTop: 6 }}>
                    {d.hallazgosRecientes.map((h) => (
                      <li key={h}>{h}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="campo-etiqueta">Qué investigar</p>
                  <ul className="lista-limpia" style={{ fontSize: 13, marginTop: 6 }}>
                    {d.queInvestigar.map((h) => (
                      <li key={h}>{h}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="campo-etiqueta">Idea ejemplo</p>
                  <p style={{ fontSize: 13, marginTop: 6 }}>{d.ideaEjemplo}</p>
                </div>
              </div>
              {d.hipotesisIds.length > 0 && (
                <div className="rivales" style={{ marginTop: 12 }}>
                  {d.hipotesisIds.map((id) => {
                    const h = hipotesis.find((x) => x.id === id);
                    return h ? (
                      <a key={id} className="chip chip-borde" href={rutaDe(inv.id, 'hipotesis', id)}>
                        {h.titulo.length > 70 ? `${h.titulo.slice(0, 67)}...` : h.titulo} · {h.elo}
                      </a>
                    ) : null;
                  })}
                </div>
              )}
            </article>
          ))}
        </div>
      )}

      <Seccion titulo="Meta-revisión: debilidades recurrentes" nota="Lo que se repite en las revisiones de todas las hipótesis de la corrida. Inyectarlo como criterio hace que la siguiente generación lo tenga en cuenta.">
        {meta.length === 0 ? (
          <p className="meta">Sin meta-revisión todavía.</p>
        ) : (
          meta.map((m) => (
            <div key={m.iteracion} className="tarjeta seccion">
              <p className="meta">
                Iteración {m.iteracion} · <Momento t={m.fecha} ahora={ahora} />
              </p>
              <ul className="lista-limpia">
                {m.debilidades.map((d) => (
                  <li key={d.id}>
                    <div>
                      <p style={{ fontSize: 13.5 }}>{d.texto}</p>
                      <div className="rivales" style={{ marginTop: 6 }}>
                        {d.hipotesisAfectadas.map((id) => {
                          const h = hipotesis.find((x) => x.id === id);
                          return h ? (
                            <a key={id} className="chip chip-borde" href={rutaDe(inv.id, 'hipotesis', id)}>
                              {h.titulo.length > 40 ? `${h.titulo.slice(0, 37)}...` : h.titulo}
                            </a>
                          ) : null;
                        })}
                      </div>
                    </div>
                    {d.inyectada ? (
                      <Chip tono="ok">Ya es criterio</Chip>
                    ) : (
                      <button type="button" className="btn btn-s" onClick={() => corrida && acciones.inyectarDebilidad(corrida.id, d.id)}>
                        Inyectar como criterio
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
      </Seccion>
    </div>
  );
}
