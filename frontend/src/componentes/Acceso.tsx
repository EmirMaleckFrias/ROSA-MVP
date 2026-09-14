// La puerta de Rosa. A la izquierda, el árbol vivo cuenta qué hace Rosa
// mientras se ilumina etapa a etapa; a la derecha, una tarjeta tranquila con
// un solo campo: el correo corporativo. No hay contraseña: llega un enlace
// personal de un solo uso (15 minutos). La lógica (estado de sesión, solicitar,
// confirmar, salir, configuración de la instalación) es la de Codex; aquí se
// rehízo la presentación (14 de septiembre de 2026, a petición de Emir: "está
// súper feo y genérico").

import { motion } from 'motion/react';
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { cabeceras, conectar } from '../datos/almacen';
import { useMovimientoReducido } from '../lib/movimiento';
import { ArbolVivo } from './ArbolVivo';
import './acceso.css';

type Sesion = {
  correo: string | null;
  administrador: boolean;
  correoConfigurado: boolean;
  instalacionLocal: boolean;
  avisoInstalacion?: string | null;
};
const Cuenta = createContext<string | null>(null);

const DOMINIO = 'alzheimerproject.com';

async function api(ruta: string, datos?: object) {
  const r = await fetch(`/api/acceso/${ruta}`, {
    method: datos ? 'POST' : 'GET',
    headers: cabeceras(),
    cache: 'no-store',
    ...(datos ? { body: JSON.stringify(datos) } : {}),
  });
  const json = await r.json();
  if (!r.ok) throw new Error(typeof json.detail === 'string' ? json.detail : 'No se pudo completar el acceso');
  return json;
}

export function CuentaActual() {
  const correo = useContext(Cuenta);
  const [error, setError] = useState('');
  return correo ? (
    <div className="cuenta-actual">
      <small>{correo}</small>
      <button
        className="btn btn-fantasma btn-s"
        onClick={async () => {
          try {
            await api('salir', {});
            window.location.assign('/');
          } catch {
            setError('No se pudo cerrar la sesión. Inténtalo de nuevo.');
          }
        }}
      >
        Cerrar sesión
      </button>
      {error && <p role="alert">{error}</p>}
    </div>
  ) : null;
}

/* Iconos pequeños, en línea, para no depender de la hoja de iconos general. */
function IconoSobre() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="5" width="18" height="14" rx="2.5" />
      <path d="m3.5 7 8.5 6 8.5-6" />
    </svg>
  );
}

function IconoEscudo() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.1 7.5 9.5 4.3-1.4 7.5-4.9 7.5-9.5V6L12 3Z" />
      <path d="m9 12 2 2 4-4.5" />
    </svg>
  );
}

function IconoFlecha() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

export function Acceso({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Sesion | null>(null);
  const [correo, setCorreo] = useState('');
  const [registro, setRegistro] = useState(false);
  const [mensaje, setMensaje] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [enviadoA, setEnviadoA] = useState<string | null>(null);
  // El tono del mensaje lo decide quien lo escribe, no una expresión sobre el texto.
  const [tono, setTono] = useState<'ok' | 'error'>('error');
  const [enlace, setEnlace] = useState(() => (window.location.hash.startsWith('#acceso=') ? window.location.hash.slice(8) : ''));
  const conectado = useRef(false);
  const reducido = useMovimientoReducido();
  useEffect(() => {
    const recibir = () => {
      if (window.location.hash.startsWith('#acceso=')) {
        setEnlace(window.location.hash.slice(8));
        // Un enlace nuevo abre la confirmación limpia: sin el mensaje del paso anterior.
        setMensaje('');
      }
    };
    window.addEventListener('hashchange', recibir);
    return () => window.removeEventListener('hashchange', recibir);
  }, []);
  useEffect(() => {
    // El token no queda en el historial de navegación ni en un referer.
    if (enlace) window.history.replaceState(null, '', window.location.pathname);
    let vivo = true;
    const cargar = async () => {
      try {
        const s: Sesion = await api('estado');
        if (!vivo) return;
        if (conectado.current && !s.correo) {
          window.location.assign('/');
          return;
        }
        if (s.correo && !conectado.current && !enlace) {
          await conectar(false);
          conectado.current = true;
        }
        if (vivo) setSesion(s);
      } catch {
        if (vivo) setMensaje('No se puede conectar con Rosa. Comprueba que el servidor está encendido y recarga esta página.');
      }
    };
    void cargar();
    const intervalo = window.setInterval(() => void cargar(), 30000);
    return () => {
      vivo = false;
      window.clearInterval(intervalo);
    };
  }, [enlace]);

  async function solicitar() {
    setOcupado(true);
    setMensaje('');
    try {
      const r = await api('solicitar', { correo });
      setEnviadoA(correo);
      setTono('ok');
      setMensaje(r.mensaje);
    } catch (e) {
      setTono('error');
      setMensaje(e instanceof Error ? e.message : 'No se pudo solicitar el acceso');
    } finally {
      setOcupado(false);
    }
  }
  async function confirmar() {
    setOcupado(true);
    setMensaje('');
    try {
      await api('confirmar', { enlace });
      window.location.assign('/');
    } catch (e) {
      setTono('error');
      setMensaje(e instanceof Error ? e.message : 'No se pudo confirmar el acceso');
    } finally {
      setOcupado(false);
    }
  }
  if (sesion?.correo && !enlace) return <Cuenta.Provider value={sesion.correo}>{children}</Cuenta.Provider>;

  const transicion = {
    duration: reducido ? 0.12 : 0.26,
    ease: [0.22, 1, 0.36, 1] as [number, number, number, number],
  };
  const entrada = reducido ? { opacity: 0 } : { opacity: 0, y: 10 };

  return (
    <main className="acceso">
      <section className="acceso-identidad" aria-label="Alzheimer Project">
        <div className="acceso-identidad-marca">
          <img src="/arbol-marca.png" width={56} height={56} alt="Árbol de Alzheimer Project" />
          <p>Alzheimer Project</p>
        </div>
        <h1>
          Una investigación.
          <br />
          Conocimiento que crece.
        </h1>
        <p className="acceso-descripcion">Rosa lee, verifica y propone. Tu equipo decide el siguiente paso, y cada decisión queda con su procedencia.</p>
        <ArbolVivo />
      </section>

      <section className="acceso-lado" aria-label="Acceso a Rosa">
        <motion.div className="acceso-tarjeta" initial={entrada} animate={{ opacity: 1, y: 0 }} transition={transicion}>
          <div className="acceso-marca">
            <span className="acceso-marca-punto" aria-hidden="true" />
            Rosa
          </div>

          {enlace ? (
            <motion.div key="confirmar" initial={entrada} animate={{ opacity: 1, y: 0 }} transition={transicion}>
              <div className="acceso-sello">
                <IconoEscudo />
              </div>
              <h2>Confirma tu acceso</h2>
              <p>El enlace es personal y solo puede utilizarse una vez. Continúa únicamente si tú lo solicitaste.</p>
              <button className="btn acceso-continuar" disabled={ocupado} onClick={() => void confirmar()}>
                {ocupado ? 'Confirmando…' : 'Confirmar e iniciar sesión'}
                {!ocupado && <IconoFlecha />}
              </button>
              <a className="acceso-enlace-secundario" href="/">
                Solicitar otro enlace
              </a>
            </motion.div>
          ) : enviadoA ? (
            <motion.div key="enviado" initial={entrada} animate={{ opacity: 1, y: 0 }} transition={transicion}>
              <div className="acceso-sello acceso-sello-correo">
                <IconoSobre />
              </div>
              <h2>Revisa tu correo</h2>
              <p>
                Hemos enviado un enlace personal a <strong className="acceso-correo-destino">{enviadoA}</strong>. Caduca en 15 minutos y solo sirve una vez.
              </p>
              <p className="acceso-pista">Si no llega, mira la carpeta de correo no deseado o pide otro enlace.</p>
              <button
                type="button"
                className="btn acceso-secundario"
                onClick={() => {
                  setEnviadoA(null);
                  setMensaje('');
                }}
              >
                Usar otro correo
              </button>
            </motion.div>
          ) : (
            <motion.div key="formulario" initial={entrada} animate={{ opacity: 1, y: 0 }} transition={transicion}>
              <div className="acceso-opciones" role="group" aria-label="Tipo de acceso">
                {(['entrar', 'registro'] as const).map((op) => {
                  const activa = op === 'registro' ? registro : !registro;
                  return (
                    <button
                      key={op}
                      type="button"
                      aria-pressed={activa}
                      onClick={() => {
                        setRegistro(op === 'registro');
                        setMensaje('');
                      }}
                    >
                      {activa && <motion.span className="acceso-opcion-fondo" layoutId="acceso-opcion" transition={reducido ? { duration: 0 } : { type: 'spring', stiffness: 420, damping: 34 }} />}
                      <span>{op === 'registro' ? 'Registrarse' : 'Iniciar sesión'}</span>
                    </button>
                  );
                })}
              </div>
              <h2>{registro ? 'Únete a tu equipo' : 'Continúa tu investigación'}</h2>
              <p>{registro ? 'La cuenta se crea después de confirmar tu correo corporativo.' : 'Recibe un enlace personal para entrar. No necesitas contraseña.'}</p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void solicitar();
                }}
              >
                <label htmlFor="acceso-correo">Correo de Alzheimer Project</label>
                <div className={`acceso-campo ${correo && !correo.toLowerCase().endsWith(`@${DOMINIO}`) ? 'acceso-campo-fuera' : ''}`}>
                  <span className="acceso-campo-icono" aria-hidden="true">
                    <IconoSobre />
                  </span>
                  <input
                    id="acceso-correo"
                    type="email"
                    autoComplete="email"
                    required
                    maxLength={200}
                    pattern="[^@\s]+@[aA][lL][zZ][hH][eE][iI][mM][eE][rR][pP][rR][oO][jJ][eE][cC][tT]\.[cC][oO][mM]"
                    title="Usa tu cuenta @alzheimerproject.com"
                    placeholder={`tu.nombre@${DOMINIO}`}
                    value={correo}
                    onChange={(e) => setCorreo(e.target.value)}
                  />
                </div>
                <button className="btn acceso-continuar" disabled={ocupado || !sesion?.correoConfigurado}>
                  {ocupado ? 'Solicitando enlace…' : 'Continuar con mi correo'}
                  {!ocupado && <IconoFlecha />}
                </button>
              </form>
              {sesion && !sesion.correoConfigurado && <p className="acceso-aviso">Falta conectar el servicio de correo. No se puede crear una cuenta ni iniciar sesión sin verificarla.</p>}
              {sesion === null && mensaje === '' && <p className="acceso-pista acceso-conectando">Conectando con Rosa…</p>}
              <p className="acceso-privacidad">
                Acceso exclusivo para <span className="acceso-dominio">@{DOMINIO}</span>. Los avisos de tus corridas llegarán a esta misma cuenta.
              </p>
            </motion.div>
          )}

          <p role="status" className={`acceso-mensaje ${mensaje ? (tono === 'error' ? 'acceso-mensaje-error' : 'acceso-mensaje-ok') : 'acceso-mensaje-vacio'}`}>
            {mensaje}
          </p>
          {sesion?.avisoInstalacion && (
            <p role="status" className="acceso-mensaje acceso-mensaje-aviso">
              {sesion.avisoInstalacion}
            </p>
          )}
          {sesion?.instalacionLocal && !enlace && <Instalacion onGuardar={async () => setSesion(await api('estado'))} />}
        </motion.div>
        <p className="acceso-pie">Rosa investiga; la persona decide.</p>
      </section>
    </main>
  );
}

function Instalacion({ onGuardar }: { onGuardar: () => Promise<void> }) {
  const [remitente, setRemitente] = useState('');
  const [clave, setClave] = useState('');
  const [url, setUrl] = useState(window.location.origin);
  const [ocupado, setOcupado] = useState(false);
  const [mensaje, setMensaje] = useState('');
  return (
    <details className="acceso-instalacion">
      <summary>Configurar correo de esta instalación</summary>
      <p>Disponible solo en el equipo de Rosa, antes de registrar la primera cuenta. Esa primera cuenta verificada administrará la conexión de correo.</p>
      <p>
        Crea una cuenta en{' '}
        <a href="https://resend.com" target="_blank" rel="noreferrer">
          Resend
        </a>
        , verifica tu dominio y genera una clave con permiso de envío. No pegues la clave en el chat.
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setOcupado(true);
          setMensaje('');
          try {
            await api('configuracion', { remitente, clave, url });
            setClave('');
            await onGuardar();
            setMensaje('Conexión guardada. Solicita tu enlace con el formulario de arriba.');
          } catch (error) {
            setMensaje(error instanceof Error ? error.message : 'No se pudo guardar');
          } finally {
            setOcupado(false);
          }
        }}
      >
        <label htmlFor="instalacion-remitente">Remitente verificado en Resend</label>
        <input id="instalacion-remitente" type="email" required value={remitente} onChange={(e) => setRemitente(e.target.value)} />
        <label htmlFor="instalacion-clave">Clave privada de envío</label>
        <input id="instalacion-clave" type="password" autoComplete="new-password" required value={clave} onChange={(e) => setClave(e.target.value)} />
        <label htmlFor="instalacion-url">Dirección web de Rosa</label>
        <input id="instalacion-url" type="url" required value={url} onChange={(e) => setUrl(e.target.value)} />
        <small>Localhost sirve solo en este equipo. Para acceso desde otros equipos necesitas un despliegue HTTPS.</small>
        <button className="btn" disabled={ocupado}>
          Guardar conexión
        </button>
      </form>
      <p role="status">{mensaje}</p>
    </details>
  );
}
