# Privacidad y eliminación permanente de cuentas

## URLs para Google Play Console

* Política de privacidad: `http://67.205.150.186/privacy`.
* Eliminación de cuenta y datos: `http://67.205.150.186/delete-account`.
* Alias españoles: `/privacidad` y `/eliminar-cuenta`.

Las cuatro rutas responden HTML5 en español, sin autenticación, JavaScript,
cookies analíticas, recursos externos ni redirecciones a un inicio de sesión.
La página de eliminación incluye el recorrido existente de la app y una vía
visible por correo para quien ya la desinstaló. El correo requiere comprobación
manual de titularidad y no se presenta como un borrado automático confirmado.

La política identifica a Fluilet y su contacto, las preferencias lectoras,
fecha de nacimiento, credenciales protegidas, textos retenidos y progreso.
No promete ausencia de proveedores: explica el alojamiento en DigitalOcean,
correo transaccional en Brevo y consultas públicas de temas a Wikipedia.
No se venden datos ni se comparten con fines comerciales o publicitarios.

Referencia: [requisitos de eliminación de Google Play](https://support.google.com/googleplay/android-developer/answer/13327111?hl=es).
Las páginas y pruebas no sustituyen la revisión de la ficha ni garantizan una
decisión de aprobación de Google Play.

## Contrato y transacción

`DELETE /api/v1/users/me` conserva su respuesta **204 No Content**. Exige un
token válido de tutor o adulto independiente. El correo maestro
`admin@fluilet.com` está protegido, sin distinguir mayúsculas; recibe 403 con
un mensaje claro. Una cuenta infantil no puede borrar la familia.

El servicio bloquea la cuenta y usa DELETE SQL y las claves foráneas CASCADE
existentes, sin desactivación lógica ni nueva migración. En la misma transacción
elimina las identidades NINO vinculadas. Un error revierte toda la operación.
Se elimina la fila del usuario, no solo sus tokens; los tokens antiguos fallan
inmediatamente y una nueva cuenta con el mismo correo tiene otro UUID.

Se borran sus perfiles activos e inactivos, documentos, biblioteca,
adaptaciones originales y simplificadas, métricas de chunks, lecturas,
eventos diarios, ajustes de progreso, refresh tokens y códigos de recuperación.
Las cuentas y datos de otros titulares permanecen intactos. El administrador
usa el mismo servicio para borrar cuentas desde su ruta existente.

## Demostración pública

`POST /api/v1/admin/ensure-demo-accounts` sigue exigiendo el administrador
maestro. Si el tutor demo fue borrado, crea una nueva cuenta y cuatro perfiles,
con las 15 lecciones públicas iniciales, sus controles y progreso inicial.
Sofía vuelve a Nivel 1. No recupera textos privados ni actividad eliminada.
La restauración es idempotente y no modifica cuentas ajenas a la demostración.

## Respaldos y operación

Por decisión expresa del responsable del servicio, se eliminan los cuatro
respaldos PostgreSQL históricos de `/var/backups/fluilet`. Se conservan los
archivos de código. No se crean nuevos dumps de datos personales durante los
despliegues: el rollback conserva código, entorno privado y checkpoint, sin
volver a introducir cuentas borradas desde una copia de la base.

Los despliegues deben comprobar que no se hayan reintroducido dumps de
producción, volcados de tablas, archivado WAL externo ni tareas programadas
de copia de datos. No guardar `.env`, tokens, contraseñas, contenido privado
ni copias PostgreSQL en Git. La eliminación lógica SQL no equivale a una
garantía forense sobre los bloques físicos de un proveedor de infraestructura.

Para una solicitud recibida por correo: verificar al titular por un canal
seguro, identificar la cuenta, usar el servicio de borrado autorizado y
confirmar el resultado. No restaurar datos previos para tramitar la solicitud;
no solicitar contraseñas, PIN ni códigos por correo.

## Verificación

`tests/test_account_deletion.py` comprueba todas las tablas desde SQL, tokens
de tutor e hijo, adultos independientes, perfiles inactivos, aislamiento de
otras cuentas, rollback integral y restauración pública idempotente.
`tests/test_public_pages.py` comprueba los cuatro recursos públicos, sus alias,
HTML completo, enlaces de soporte y coherencia de la política.

Durante la verificación integral se detectó una carrera en la recepción del
PDF: el proceso podía enviar el texto y terminar entre la consulta del pipe y
la consulta de vida del proceso. Ahora se comprueba el resultado pendiente
antes de declarar un fallo; se mantienen los mismos límites de CPU, memoria
y tiempo. Dos pruebas reproducen la entrega completada y la salida sin datos.


## Resultado del cierre

* Suite completa sobre PostgreSQL: **959 pruebas aprobadas**.
* Pruebas afectadas de autenticación, borrado, demo y páginas: **67 aprobadas**
  sobre PostgreSQL; comprobación inicial de los 13 casos nuevos de privacidad
  y eliminación también aprobada sobre SQLite.
* Recepción de PDF: dos casos de carrera/crash y el caso PDF real aislado,
  **3 pruebas aprobadas** antes de la ejecución final completa.
* Ruff: sin incidencias; **147 archivos Python formateados**. `pip check`
  no detecta dependencias incompatibles.
* Se retiran los cuatro dumps autorizados y se verifica que no quedan dumps
  administrativos ni tareas cron de copia PostgreSQL. `archive_mode` está
  desactivado. Los despliegues conservan únicamente copias de código.

No cambian los modelos SQL ni el esquema de Alembic, los DTO JSON existentes,
el checkpoint, los archivos de entrenamiento ni el cliente Android.
