import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { cabeceras, conectar } from '../datos/almacen';
import './acceso.css';

type Sesion = { correo: string | null; administrador: boolean; correoConfigurado: boolean; instalacionLocal: boolean; avisoInstalacion?: string | null };
const Cuenta = createContext<string | null>(null);

async function api(ruta: string, datos?: object) {
  const r = await fetch(`/api/acceso/${ruta}`, { method: datos ? 'POST' : 'GET', headers: cabeceras(), cache: 'no-store', ...(datos ? { body: JSON.stringify(datos) } : {}) });
  const json = await r.json();
  if (!r.ok) throw new Error(typeof json.detail === 'string' ? json.detail : 'No se pudo completar el acceso');
  return json;
}

export function CuentaActual() {
  const correo = useContext(Cuenta);
  const [error, setError] = useState('');
  return correo ? <div className="cuenta-actual"><small>{correo}</small><button className="btn btn-fantasma btn-s" onClick={async () => {
    try { await api('salir', {}); window.location.assign('/'); } catch { setError('No se pudo cerrar la sesión. Inténtalo de nuevo.'); }
  }}>Cerrar sesión</button>{error && <p role="alert">{error}</p>}</div> : null;
}

export function Acceso({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Sesion | null>(null);
  const [correo, setCorreo] = useState('');
  const [registro, setRegistro] = useState(false);
  const [mensaje, setMensaje] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [enlace, setEnlace] = useState(() => window.location.hash.startsWith('#acceso=') ? window.location.hash.slice(8) : '');
  const conectado = useRef(false);
  useEffect(() => {
    const recibir = () => {
      if (window.location.hash.startsWith('#acceso=')) setEnlace(window.location.hash.slice(8));
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
        if (conectado.current && !s.correo) { window.location.assign('/'); return; }
        if (s.correo && !conectado.current && !enlace) { await conectar(false); conectado.current = true; }
        if (vivo) setSesion(s);
      } catch { if (vivo) setMensaje('No se puede conectar con Rosa. Comprueba que el servidor está encendido y recarga esta página.'); }
    };
    void cargar();
    const intervalo = window.setInterval(() => void cargar(), 30000);
    return () => { vivo = false; window.clearInterval(intervalo); };
  }, [enlace]);

  async function solicitar() {
    setOcupado(true); setMensaje('');
    try { const r = await api('solicitar', { correo }); setMensaje(r.mensaje); }
    catch (e) { setMensaje(e instanceof Error ? e.message : 'No se pudo solicitar el acceso'); }
    finally { setOcupado(false); }
  }
  async function confirmar() {
    setOcupado(true); setMensaje('');
    try { await api('confirmar', { enlace }); window.location.assign('/'); }
    catch (e) { setMensaje(e instanceof Error ? e.message : 'No se pudo confirmar el acceso'); }
    finally { setOcupado(false); }
  }
  if (sesion?.correo && !enlace) return <Cuenta.Provider value={sesion.correo}>{children}</Cuenta.Provider>;
  return <main className="acceso">
    <section className="acceso-identidad" aria-label="Alzheimer Project">
      <img src="/arbol-marca.png" width={240} height={240} alt="Árbol de Alzheimer Project" />
      <p>Alzheimer Project</p>
      <h1>Una investigación.<br />Conocimiento que crece.</h1>
      <p className="acceso-descripcion">Rosa conecta la evidencia.<br />Tu equipo decide el siguiente paso.</p>
    </section>
    <section className="acceso-formulario" aria-label="Acceso a Rosa">
      <div className="acceso-marca">Rosa</div>
      {enlace ? <>
        <h2>Confirma tu acceso</h2><p>El enlace es personal y solo puede utilizarse una vez. Continúa únicamente si tú lo solicitaste.</p>
        <button className="btn acceso-continuar" disabled={ocupado} onClick={() => void confirmar()}>{ocupado ? 'Confirmando…' : 'Confirmar e iniciar sesión'}</button>
        <a href="/">Solicitar otro enlace</a>
      </> : <>
        <div className="acceso-opciones" role="group" aria-label="Tipo de acceso">
          <button aria-pressed={!registro} onClick={() => { setRegistro(false); setMensaje(''); }}>Iniciar sesión</button>
          <button aria-pressed={registro} onClick={() => { setRegistro(true); setMensaje(''); }}>Registrarse</button>
        </div>
        <h2>{registro ? 'Únete a tu equipo' : 'Continúa tu investigación'}</h2>
        <p>{registro ? 'La cuenta se crea después de confirmar tu correo corporativo.' : 'Recibe un enlace personal para entrar. No necesitas contraseña.'}</p>
        <form onSubmit={(e) => { e.preventDefault(); void solicitar(); }}>
          <label htmlFor="acceso-correo">Correo de Alzheimer Project</label>
          <input id="acceso-correo" type="email" autoComplete="email" required maxLength={200} pattern="[^@\s]+@[aA][lL][zZ][hH][eE][iI][mM][eE][rR][pP][rR][oO][jJ][eE][cC][tT]\.[cC][oO][mM]" title="Usa tu cuenta @alzheimerproject.com" placeholder="tu.nombre@alzheimerproject.com" value={correo} onChange={(e) => setCorreo(e.target.value)} />
          <button className="btn acceso-continuar" disabled={ocupado || !sesion?.correoConfigurado}>{ocupado ? 'Solicitando enlace…' : 'Continuar con mi correo'}</button>
        </form>
        {sesion && !sesion.correoConfigurado && <p className="acceso-aviso">Falta conectar el servicio de correo. No se puede crear una cuenta ni iniciar sesión sin verificarla.</p>}
        <p className="acceso-privacidad">Acceso exclusivo para @alzheimerproject.com. Los avisos de tus corridas llegarán a esta misma cuenta.</p>
      </>}
      <p role="status">{mensaje}</p>
      {sesion?.avisoInstalacion && <p role="status">{sesion.avisoInstalacion}</p>}
      {sesion?.instalacionLocal && !enlace && <Instalacion onGuardar={async () => setSesion(await api('estado'))} />}
    </section>
  </main>;
}

function Instalacion({ onGuardar }: { onGuardar: () => Promise<void> }) {
  const [remitente, setRemitente] = useState('');
  const [clave, setClave] = useState('');
  const [url, setUrl] = useState(window.location.origin);
  const [ocupado, setOcupado] = useState(false);
  const [mensaje, setMensaje] = useState('');
  return <details className="acceso-instalacion"><summary>Configurar correo de esta instalación</summary>
    <p>Disponible solo en el equipo de Rosa, antes de registrar la primera cuenta. Esa primera cuenta verificada administrará la conexión de correo.</p>
    <p>Crea una cuenta en <a href="https://resend.com" target="_blank" rel="noreferrer">Resend</a>, verifica tu dominio y genera una clave con permiso de envío. No pegues la clave en el chat.</p>
    <form onSubmit={async (e) => {
      e.preventDefault(); setOcupado(true); setMensaje('');
      try { await api('configuracion', { remitente, clave, url }); setClave(''); await onGuardar(); setMensaje('Conexión guardada. Solicita tu enlace con el formulario de arriba.'); }
      catch (error) { setMensaje(error instanceof Error ? error.message : 'No se pudo guardar'); }
      finally { setOcupado(false); }
    }}>
      <label htmlFor="instalacion-remitente">Remitente verificado en Resend</label><input id="instalacion-remitente" type="email" required value={remitente} onChange={(e) => setRemitente(e.target.value)} />
      <label htmlFor="instalacion-clave">Clave privada de envío</label><input id="instalacion-clave" type="password" autoComplete="new-password" required value={clave} onChange={(e) => setClave(e.target.value)} />
      <label htmlFor="instalacion-url">Dirección web de Rosa</label><input id="instalacion-url" type="url" required value={url} onChange={(e) => setUrl(e.target.value)} />
      <small>Localhost sirve solo en este equipo. Para acceso desde otros equipos necesitas un despliegue HTTPS.</small>
      <button className="btn" disabled={ocupado}>Guardar conexión</button>
    </form><p role="status">{mensaje}</p>
  </details>;
}
