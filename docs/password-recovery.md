# Recuperación de contraseña por correo

Los tres endpoints públicos reciben JSON bajo `/api/v1/auth/` y conservan el
login OAuth2 por formulario existente:

1. `POST /forgot-password`: `{"email":"persona@example.com"}`. Devuelve 200 con
   el mismo mensaje para cuentas existentes, desconocidas, inactivas o limitadas.
   Envía solo para cuentas activas. El lookup no distingue mayúsculas.
2. `POST /verify-reset-code`: `{"email":"persona@example.com","code":"000123"}`.
   Devuelve `{"valid":true,"message":"Código válido. Ya puedes establecer tu nueva contraseña."}`;
   no consume el código necesario en el paso siguiente.
3. `POST /reset-password`: `{"email":"persona@example.com","code":"000123","new_password":"UnaClaveNueva2026!"}`.
   Devuelve 200 con confirmación. El usuario debe iniciar sesión otra vez.

Código inválido, vencido, usado o bloqueado: **400**, con un mensaje común en
español. JSON/código/contraseña inválidos: **422**, sin repetir datos sensibles.
El código debe ser un string de seis dígitos ASCII, incluidos ceros iniciales.
La contraseña conserva las reglas existentes: 10–72 caracteres y hasta 72 bytes
UTF-8, mayúscula, minúscula, número y símbolo, sin espacios.

## Persistencia y límites

`0009_password_reset` añade únicamente `password_reset_requests`, enlazada al
usuario con borrado en cascada: UUID, `user_id`, `code_hash`, `expires_at`,
`attempts`, `used_at`, `created_at`. No se guarda el código ni se duplica el email.
Es la novena revisión real, posterior a `0007_master_accounts`; no hace falta
crear una revisión 0008 vacía. El rollback descarta solo solicitudes efímeras.

Los códigos usan `secrets.randbelow(1_000_000)`, vencen a diez minutos y se guardan
como HMAC-SHA256 con la clave del servidor, contexto de solicitud/usuario y versión
de autenticación. Una copia de la BD sola no permite probar un millón de hashes
sin conocer esa clave. La comparación es constante. Los fallos se confirman en
BD antes del HTTP 400: cinco fallos bloquean el código, compartidos entre verify y
reset. Un reenvío permitido invalida los anteriores; máximo uno por minuto y cinco
por hora por cuenta. Se conserva además el límite de autenticación por IP.

PostgreSQL serializa las solicitudes sobre la fila del usuario, incluyendo
reenvíos y resets concurrentes. Un reset consume la solicitud, invalida las otras,
restablece el contador de login y revoca los JWT/refresh anteriores. El hash de
contraseña sigue siendo bcrypt con el costo configurado. Un cambio de versión de
autenticación también invalida códigos pendientes. Las cuentas demo gestionadas
conservan su restauración de credenciales al arrancar; ese comportamiento no cambia.

## SMTP y plantilla

Configurar en `.env` (o el archivo privado de Compose):

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=tu-cuenta@gmail.com
SMTP_PASSWORD=tu-password-de-aplicacion
SMTP_FROM_EMAIL=tu-cuenta@gmail.com
SMTP_FROM_NAME="Fluilet Soporte"
```

Para Gmail, utiliza una contraseña de aplicación habilitada para la cuenta; no
pongas su contraseña de inicio de sesión en el repositorio. El remitente debe
estar permitido por el proveedor. No hay una lista de dominios de destinatarios:
Gmail, Hotmail, Outlook u otros se entregan por el mismo relay. El proveedor debe
permitir la autenticación y el envío; el código no garantiza ubicación en inbox.

`smtplib` con timeout de diez segundos, EHLO/STARTTLS con validación de certificado
y autenticación. El envío se programa después del commit/respuesta y corre fuera
del event loop, con dos trabajos como máximo y cierre controlado. Los fallos de
SMTP conservan la respuesta genérica y registran un mensaje saneado, nunca la
excepción del servidor, contraseñas ni direcciones. Si el proceso termina antes
de enviar un correo pendiente, hay que solicitar otro; no hay una cola persistente.

Si falta usuario o contraseña SMTP, **desarrollo** registra el código claramente,
sin el destinatario, como excepción solicitada a la política general de logs.
No usar esos logs con cuentas reales. **Producción** registra solo el error de
configuración, sin códigos. La API no expone códigos en ninguna respuesta.

Correo `multipart/alternative` con texto plano y HTML en español. Usa el violeta
primario Android estándar `#5B3E8C`, icono amigable de FluiBot, tablas, CSS inline,
fuentes del sistema, ancho fluido y fallback para Outlook. El código tiene
`letter-spacing: 8px`. No hay imágenes remotas, scripts, enlaces de seguimiento
ni contenido HTML controlado por el destinatario. Incluye vencimiento, explicación
para ignorar una solicitud ajena y sello de acceso protegido.
