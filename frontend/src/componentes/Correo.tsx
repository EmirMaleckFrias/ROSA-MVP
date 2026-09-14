import { useEffect, useState } from 'react';
import { cabeceras } from '../datos/almacen';

type Configuracion = { remitente: string; url: string; hora: number; zona: string };
type EstadoCorreo = Configuracion & {
  claveGuardada: boolean; configurado: boolean; administrador: boolean; error: string | null;
  historial: { id: string; tipo: string; destinatario: string; estado: string; creado: number; intentos: number; error: string | null }[];
};
const ETIQUETAS: Record<string, string> = { pendiente: 'En cola / reintentó', aceptado: 'Aceptado por Resend', fallido: 'No confirmado', cancelado: 'Cancelado' };

async function pedir(ruta = '', cuerpo?: object) {
  const r = await fetch(`/api/correo${ruta}`, { method: cuerpo ? 'POST' : 'GET', headers: cabeceras(), cache: 'no-store', ...(cuerpo ? { body: JSON.stringify(cuerpo) } : {}) });
  const datos = await r.json();
  if (!r.ok) throw new Error(typeof datos.detail === 'string' ? datos.detail : 'No se pudo conectar el correo');
  return datos;
}

export function Correo({ servidor }: { servidor: boolean }) {
  const [estado, setEstado] = useState<EstadoCorreo | null>(null);
  const [form, setForm] = useState<Configuracion | null>(null);
  const [clave, setClave] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [mensaje, setMensaje] = useState('');
  useEffect(() => {
    if (!servidor) return;
    let vivo = true;
    const cargar = async () => {
      try {
        const datos: EstadoCorreo = await pedir();
        if (vivo) {
          setEstado(datos);
          setForm((anterior) => anterior ?? { remitente: datos.remitente, url: datos.url, hora: datos.hora, zona: datos.zona });
        }
      } catch { if (vivo) setMensaje('No se pudo cargar el servicio de correo. Comprueba que el backend está actualizado.'); }
    };
    void cargar();
    const intervalo = window.setInterval(() => void cargar(), 5000);
    return () => { vivo = false; window.clearInterval(intervalo); };
  }, [servidor]);
  async function ejecutar(ruta: string, datos: object, texto: string) {
    setOcupado(true); setMensaje('');
    try {
      await pedir(ruta, datos);
      setClave('');
      setEstado(await pedir());
      setMensaje(texto);
    } catch (e) { setMensaje(e instanceof Error ? e.message : 'No se pudo completar la operación'); }
    finally { setOcupado(false); }
  }
  if (!servidor) return <p>El correo real solo está disponible con el servidor conectado, no en el modo de muestra.</p>;
  return <div className="tarjeta seccion">
    <h3>Envío real por correo</h3>
    <p>Los avisos llegan a la cuenta que inició la corrida. El administrador conecta Resend una vez; la clave queda en el servidor, no en Convex.</p>
    <p><a href="https://resend.com/domains" target="_blank" rel="noreferrer">Verificar dominio remitente</a> · <a href="https://resend.com/api-keys" target="_blank" rel="noreferrer">Crear clave de envío</a></p>
    {form && estado && <>
      {estado.administrador && <form onSubmit={(e) => { e.preventDefault(); void ejecutar('/configuracion', { ...form, clave }, 'Configuración guardada. Puedes enviar una prueba.'); }}>
        <fieldset disabled={ocupado} style={{ border: 0, padding: 0 }}>
          <div className="campo"><label htmlFor="correo-remitente">Correo remitente (dominio verificado en Resend)</label><input id="correo-remitente" type="email" required value={form.remitente} onChange={(e) => setForm({ ...form, remitente: e.target.value })} placeholder="rosa@tu-dominio.com" /></div>
          <div className="campo"><label htmlFor="correo-clave">Clave de Resend {estado.claveGuardada ? '(guardada; deja vacío para conservarla)' : ''}</label><input id="correo-clave" type="password" autoComplete="new-password" value={clave} onChange={(e) => setClave(e.target.value)} /></div>
          <div className="campo"><label htmlFor="correo-url">Dirección web para abrir Rosa desde el correo</label><input id="correo-url" type="url" required value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} /><small>Localhost solo funciona en el equipo que ejecuta Rosa. No incluyas tokens de acceso en esta URL.</small></div>
          <div className="campo"><label htmlFor="correo-hora">Hora del resumen diario (0 a 23)</label><input id="correo-hora" type="number" min={0} max={23} required value={form.hora} onChange={(e) => setForm({ ...form, hora: Number(e.target.value) })} /></div>
          <div className="campo"><label htmlFor="correo-zona">Zona horaria</label><input id="correo-zona" required value={form.zona} onChange={(e) => setForm({ ...form, zona: e.target.value })} /></div>
          <button className="btn" type="submit">Guardar conexión</button>
        </fieldset>
      </form>}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
        <button className="btn" disabled={ocupado || !estado.configurado} onClick={() => void ejecutar('/prueba', {}, 'Prueba en cola. El historial mostrará si el proveedor la acepta.')}>Enviar correo de prueba</button>
        {estado.administrador && <button className="btn btn-fantasma" disabled={ocupado || !estado.claveGuardada} onClick={() => void ejecutar('/configuracion', { borrarClave: true }, 'Conexión eliminada y correos pendientes cancelados.')}>Desconectar correo</button>}
      </div>
      <p>La prueba envía un correo aunque los avisos automáticos estén apagados. No consume tokens; el proveedor de correo puede cobrar por los envíos. Rosa debe permanecer encendida.</p>
      <p>Solo se envían contadores y un enlace, sin títulos, documentos ni datos clínicos. Los avisos empiezan con las novedades, sin reenviar todo el historial.</p>
      <h4>Últimos envíos</h4>
      <p>Aceptado por Resend no confirma llegada al buzón. Consulta entregas o rebotes en el panel del proveedor.</p>
      {estado.historial.length === 0 ? <p>Todavía no hay envíos.</p> : <ul>{estado.historial.map((x) => <li key={x.id}>
        {new Date(x.creado * 1000).toLocaleString()} · {x.destinatario} · {ETIQUETAS[x.estado] ?? x.estado} · {x.intentos} intento(s){x.error && <p>{x.error}</p>}
      </li>)}</ul>}
      {estado.error && <p role="alert">{estado.error}</p>}
    </>}
    <p role="status">{mensaje}</p>
  </div>;
}
