"""Multipart recovery mail, bounded SMTP off the loop, development-only codes."""

import asyncio
import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from html import escape

from app.config import settings

logger = logging.getLogger("fluilet.email")
_smtp_slots = asyncio.Semaphore(2)
_smtp_jobs: set[asyncio.Task] = set()


def recovery_message(recipient: str, code: str) -> EmailMessage:
    if not re.fullmatch(r"[0-9]{6}", code):
        raise ValueError("El código debe tener seis dígitos.")
    message = EmailMessage()
    message["Subject"] = "Tu código para recuperar la contraseña · Fluilet"
    message["From"] = formataddr(
        (
            settings.SMTP_FROM_NAME,
            settings.SMTP_FROM_EMAIL or settings.SMTP_USER or "soporte@fluilet.com",
        )
    )
    message["To"] = recipient
    message.set_content(
        "Fluilet · Lectura adaptativa inteligente\n\n"
        "Recibimos una solicitud para restablecer tu contraseña.\n\n"
        f"Tu código de seguridad es: {code}\n\n"
        "Introduce estos seis dígitos en la aplicación. El código vence en 10 minutos.\n"
        "No compartas este código con nadie. Si no solicitaste este cambio, puedes ignorar "
        "este mensaje con tranquilidad: tu contraseña no cambiará.\n\n"
        "Fluilet Soporte · Acceso protegido\n"
    )
    # Tables + inline CSS + system fonts degrade safely in Outlook's Word engine.
    # No remote image, web font, script, link or recipient-controlled HTML.
    safe_code = escape(code)
    message.add_alternative(
        f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#F5F7FB;color:#243247;font-family:Arial,Helvetica,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">Tu código de seguridad de Fluilet vence en 10 minutos.</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#F5F7FB;"><tr><td align="center" style="padding:32px 12px;">
<!--[if mso]><table role="presentation" width="560" cellspacing="0" cellpadding="0" border="0"><tr><td><![endif]-->
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;">
<tr><td align="center" bgcolor="#5B3E8C" style="padding:28px 20px;background-color:#5B3E8C;border-radius:20px 20px 0 0;">
<div role="img" aria-label="FluiBot, tu compañero de lectura" style="font-size:36px;line-height:46px;">&#129302;</div>
<div style="font-size:28px;line-height:36px;font-weight:bold;color:#FFFFFF;">Fluilet</div>
<div style="font-size:13px;line-height:22px;color:#FFFFFF;">Fluilet · Lectura adaptativa inteligente</div>
</td></tr>
<tr><td bgcolor="#FFFFFF" style="padding:32px 24px;background-color:#FFFFFF;border-radius:0 0 20px 20px;">
<h1 style="margin:0 0 18px;font-size:24px;line-height:32px;color:#243247;">Recupera tu contraseña</h1>
<p style="margin:0 0 18px;font-size:16px;line-height:25px;">Recibimos una solicitud para restablecer la contraseña de tu cuenta. Usa este código de seguridad en la aplicación:</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr><td align="center" bgcolor="#F3EFF9" style="padding:24px 8px;background-color:#F3EFF9;border:1px solid #DDD3EB;border-radius:12px;">
<span style="font-family:Consolas,'Courier New',monospace;font-size:32px;line-height:42px;font-weight:bold;letter-spacing: 8px;color:#4B3274;">{safe_code}</span>
</td></tr></table>
<p style="margin:20px 0 12px;font-size:15px;line-height:24px;">Este código vence en <strong>10 minutos</strong>. Por tu seguridad, no lo compartas con nadie.</p>
<p style="margin:0;font-size:14px;line-height:23px;color:#58677C;">Si no solicitaste este cambio, puedes ignorar el mensaje con tranquilidad. Tu contraseña seguirá siendo la misma.</p>
</td></tr>
<tr><td align="center" style="padding:24px 16px;font-size:12px;line-height:20px;color:#637086;">
<strong>Fluilet · Acceso protegido</strong><br>Un espacio seguro para seguir aprendiendo.<br>Este correo es automático; no necesitas responder.
</td></tr></table>
<!--[if mso]></td></tr></table><![endif]-->
</td></tr></table></body></html>""",
        subtype="html",
    )
    return message


def _send(recipient: str, code: str):
    password = settings.SMTP_PASSWORD.get_secret_value()
    if not settings.SMTP_USER or not password:
        if settings.DEPLOYMENT_ENV == "development":
            # Explicitly requested local fallback: no recipient/account in logs.
            logger.warning(
                "Fluilet [DESARROLLO] Código de recuperación: %s (vence en 10 minutos).", code
            )
        else:
            logger.error("Fluilet: SMTP no configurado; no se envió el correo de recuperación.")
        return
    message = recovery_message(recipient, code)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
        smtp.ehlo()
        if settings.SMTP_USE_TLS:
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        smtp.login(settings.SMTP_USER, password)
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPException()


async def send_reset_code(recipient: str, code: str):
    if _smtp_slots.locked():
        logger.error("Fluilet: envío de recuperación ocupado. Intenta de nuevo más tarde.")
        return
    await _smtp_slots.acquire()

    async def deliver():
        try:
            await asyncio.to_thread(_send, recipient, code)
        except Exception:
            # SMTP exceptions may include credentials/addresses/server replies.
            logger.error("Fluilet: no se pudo enviar el correo de recuperación. Revisa SMTP.")
        finally:
            _smtp_slots.release()

    task = asyncio.create_task(deliver())
    _smtp_jobs.add(task)
    task.add_done_callback(_smtp_jobs.discard)
    # A disconnected request must not release a slot while its thread still runs.
    await asyncio.shield(task)


async def close():
    if _smtp_jobs:
        await asyncio.gather(*_smtp_jobs, return_exceptions=True)
