# Acceso y correo de Rosa

Rosa requiere una cuenta verificada de `@alzheimerproject.com`. Las opciones
Iniciar sesión y Registrarse comparten un acceso sin contraseña: la cuenta
solo se crea cuando se confirma el enlace enviado al buzón corporativo.
La pantalla para introducir un código queda pendiente del diseño del usuario;
por ahora se confirma con un enlace de un solo uso, válido durante 15 minutos.

## Entrada sin verificación mientras no hay correo

Pedida por Emir el 15 de septiembre de 2026 ("abre el login para que puedan
entrar personas sin configurar el proveedor"). Mientras el correo de Rosa no
esté configurado, la puerta muestra «Entrar sin verificación»: quien escriba
una dirección `@alzheimerproject.com` entra con una sesión normal de 12 horas
(`POST /api/acceso/entrar_sin_verificar`, que exige la cabecera `X-Rosa` como
toda escritura). No hay más comprobación de identidad que la dirección
escrita: es acceso abierto al dominio, y así se le dice a quien entra. En
cuanto se configura un proveedor (SMTP o Resend), esa puerta devuelve 403
para todos y solo vale el enlace verificado; las sesiones ya abiertas duran
hasta caducar. La primera cuenta creada, verificada o no, administra el
correo.

## Dos transportes: Google Workspace por SMTP o Resend

Desde el 15 de septiembre de 2026 el correo de Rosa sale por uno de dos
caminos, a elegir en «Configurar correo de esta instalación» (la puerta) o en
Ajustes:

- **Google Workspace u otro servidor SMTP** (por defecto). Envía desde el
  buzón corporativo que ya existe (`smtp.gmail.com`, puerto 587 con STARTTLS
  o 465 con TLS), con el usuario de esa cuenta y una **contraseña de
  aplicación** (Cuenta de Google, Seguridad, Verificación en dos pasos,
  Contraseñas de aplicaciones), nunca la contraseña normal. No hay que
  registrar nada en un tercero ni verificar un dominio, y el correo llega a
  cualquier persona del equipo desde el primer día. El remitente debe ser la
  misma cuenta o un alias suyo; Google rechaza otros.
- **Resend**, como estaba: clave de API y dominio verificado.

`rosa/correo.py` guarda `proveedor`, `smtpServidor`, `smtpPuerto` y
`smtpUsuario` junto al remitente y la clave; `_enviar_smtp` corre en un hilo
(smtplib es bloqueante) y pone el id de la cola en el `Message-ID`. Política
de reintentos: usuario o contraseña rechazados y destinatario o remitente
rechazados no se reintentan; una respuesta 4xx del servidor o la red caída
sí, con el mismo mensaje. Pruebas en `rosa/tests/test_correo_smtp.py` con
un servidor falso, sin red ni contraseñas reales.

## Primera instalación

1. Con Google Workspace: generar una contraseña de aplicación de la cuenta
   corporativa que enviará los correos. Con Resend: crear la cuenta,
   verificar el dominio y generar una clave con permiso de envío.
2. Arrancar el backend actualizado y abrir Rosa **en el equipo del servidor**.
   La pantalla de acceso muestra «Configurar correo de esta instalación».
3. Elegir el proveedor y guardar los datos (con SMTP: cuenta, contraseña de
   aplicación, servidor y puerto; con Resend: remitente y clave) y la URL de
   Rosa. La URL local solo funciona en ese equipo. Para otros equipos hace falta un despliegue
   HTTPS accesible, con los hosts admitidos configurados en el servidor.
4. Solicitar el enlace usando la cuenta corporativa y confirmarlo. La primera
   cuenta verificada administra la conexión de correo. Completar este paso
   antes de publicar el servidor para el resto del equipo.
5. En Ajustes, revisar los avisos y usar «Enviar correo de prueba». La prueba
   se envía exclusivamente a la cuenta de la sesión.

La configuración inicial se permite solo desde loopback, antes de crear una
cuenta, sin cabeceras de proxy y con origen local. Después solo la primera
cuenta verificada puede cambiar o desconectar el proveedor. No hay un acceso
de demostración que permita saltarse la verificación si falta el proveedor.
El arranque en una dirección distinta de loopback conserva además los
requisitos existentes de configuración del servidor.

## A quién llegan los avisos

- El backend toma la identidad de la sesión, no de un campo editable del
  navegador, y la guarda al crear una investigación o iniciar una corrida.
- Los avisos de una corrida llegan a quien la inició. Iniciar sesión desde
  otra cuenta no cambia el destinatario de corridas anteriores.
- Las hipótesis que genera el bucle conservan la referencia a su corrida de
  origen; los permisos y las incidencias se resuelven por su corrida.
- Las investigaciones y corridas antiguas no se asignan por suposición a la
  primera persona que entre. Una nueva corrida sí tendrá responsable.
- Cada cuenta tiene sus propias preferencias. Los avisos inmediatos están
  activados por defecto para cuentas verificadas; el resumen diario se activa
  expresamente en Ajustes. La preferencia antigua de dirección global no se usa.
- El equipo comparte el espacio de investigaciones: este cambio identifica
  autores y destinatarios, **no crea espacios privados separados por cuenta**.

Se avisa de nuevas hipótesis, planes/decisiones pendientes, incidencias y
corridas pausadas o finalizadas. El resumen diario contiene contadores propios
y un enlace, no conclusiones científicas ni datos clínicos. Por defecto se
programa a las 08:00 de `America/Santo_Domingo`, configurable por administrador.
Al habilitar o arrancar por primera vez no se envía todo el historial antiguo.
El trabajador comprueba el estado cada cinco segundos; no es un registro de
transiciones instantáneas que desaparezcan entre dos comprobaciones.

## Persistencia y seguridad

`datos/_correo/<nombre de la base>.db` guarda proveedor, preferencias, cuentas,
enlaces, sesiones y cola de correo. Está fuera de Git y de Convex, con permiso
de archivo `0600`. La clave se almacena localmente **sin cifrado de aplicación**:
proteger el equipo y las copias de seguridad; el permiso no sustituye al cifrado
de disco. Ni el API de configuración ni el estado compartido devuelven la clave.

Las sesiones duran 12 horas, se almacenan por hash, se revocan al salir y viajan
en una cookie HttpOnly, SameSite=Strict y Secure cuando la URL configurada es
HTTPS. Los enlaces se guardan por hash en autenticación; la cola necesita el
enlace mientras espera el envío y elimina su cuerpo al concluir. Se limita la
solicitud por dirección, IP y volumen total. Todas las rutas de investigación
requieren sesión; se conserva la credencial interna existente para procesos
de confianza del servidor. El flujo SSE también comprueba la vigencia de sesión.

La cola reintenta fallos de red, HTTP 429 y 5xx hasta cinco intentos, manteniendo
el mismo contenido y clave de idempotencia. No reintenta después de 23 horas
desde el primer intento, dentro de las 24 horas que documenta Resend. Los
enlaces de acceso no se envían después de caducar. Un fallo que no permite
confirmar el resultado queda visible, no se convierte en éxito.

«Aceptado por Resend» **no confirma entrega al buzón**: los rebotes y la entrega
se consultan en el panel del proveedor; todavía no hay webhook de entregas.
Desactivar avisos cancela lo pendiente, pero no puede retirar un correo que
ya se está enviando. Rosa debe permanecer en ejecución para enviar avisos.
Los mensajes no llaman a modelos de IA; el proveedor puede cobrar por envío.

## Verificación

- Backend: `uv run python -m pytest rosa/tests -q`.
- Frontend: `cd frontend && npm test -- --silent` y `npm run build`.
- Transporte y autenticación se prueban con datos temporales y HTTP simulado,
  sin gastar tokens y sin enviar correos externos.
- `scripts/probar_acceso_visual.py` comprueba escritorio, móvil, dominio,
  configuración local y rechazo de un enlace inválido con una base temporal.

Documentación utilizada: [envío de Resend](https://resend.com/docs/api-reference/emails/send-email),
[idempotencia](https://resend.com/docs/dashboard/emails/idempotency-keys),
[sesiones de OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
y [tokens de un solo uso](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html).
