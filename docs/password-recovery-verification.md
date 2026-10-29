# Verificación del módulo de recuperación

Sobre `42482e0`, con el checkpoint y todos los datos educativos conservados.

| Comprobación | Resultado |
|---|---|
| Desarrollo: únicamente el nuevo archivo `test_auth_password_reset.py` | 27 pruebas aprobadas en PostgreSQL, 10.92 s |
| Única ejecución completa local al final | **600 aprobadas**, PostgreSQL, 271.26 s |
| Ruff / formato | Sin errores, 98 archivos de app/tests/migraciones/scripts |
| pip check | Sin dependencias incompatibles; SMTP usa biblioteca estándar |
| Migración real local | `0009_password_reset`, `alembic check` sin diferencias |
| Portabilidad de migración | Upgrade desde 0007, preservación de contraseña, rollback de códigos efímeros, upgrade y check aprobados |
| Concurrencia PostgreSQL | Dos solicitudes simultáneas envían un código; dos resets dejan un éxito y un rechazo |
| Servidor reiniciado mediante bootstrap | `/health/ready`: **200** |
| OpenAPI en servidor activo | Tres POST públicos publicados |
| Prueba HTTP sin cuenta existente | Forgot 200; verify/reset 400; sin crear ni enviar solicitudes |
| Model-info autenticado | **acceptance_criteria_met=true**, mismo SHA de artefacto |
| Integridad educativa | Mismas huellas de todas las filas de contenido, perfiles, sesiones, telemetría y recursos antes/después |
| Configuración Compose | Renderizado válido con el ejemplo de despliegue |

Las pruebas cubren códigos incorrectos/expirados/usados, cinco fallos persistidos,
resend cooldown/cupo horario, ceros iniciales, comparación case-insensitive,
contraseña débil/UTF-8, sesiones revocadas, borrado en cascada y SMTP fuera del
loop con MIME/STARTTLS. Gmail/Hotmail/Outlook se prueban como destinatarios con un
doble SMTP, sin enviar mensajes externos. Se comprueba fallback de desarrollo,
ausencia de secretos en errores de producción y retención del slot mientras sigue
un thread cancelado por el llamador.

No había credenciales SMTP locales: **no se afirma entrega externa real**. El envío
real se activa al configurar `SMTP_USER`/`SMTP_PASSWORD` y el remitente autorizado.
No se ha probado visualmente en clientes de correo reales; la plantilla usa HTML
conservador y CSS inline, con fallback de texto y Outlook. Véase el
[contrato y configuración](password-recovery.md).

No se modificó `ml_training/`, `checkpoints/`, el motor NLP/Szigriszt-Pazos,
los assets del modelo ni el generador de demos. Las huellas privadas contienen
solo conteos/hashes, no exportaciones de contenido o credenciales. `.env`, entornos,
corpus y pesos grandes continúan excluidos del repositorio.
