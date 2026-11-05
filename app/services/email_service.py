"""Recovery mail through Brevo HTTPS or SMTP, bounded off the event loop."""

import asyncio
import logging
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from html import escape

import httpx

from app.config import settings

logger = logging.getLogger("fluilet.email")
_smtp_slots = asyncio.Semaphore(2)
_smtp_jobs: set[asyncio.Task] = set()
BREVO_EMAIL_URL = "https://api.brevo.com/v3/smtp/email"


@dataclass(frozen=True)
class DeliveryReceipt:
    provider: str
    status_code: int
    message_id: str | None = None


class DeliveryError(Exception):
    def __init__(self, status_code: int):
        super().__init__("Brevo no aceptó el correo de recuperación.")
        self.status_code = status_code


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
    # The brand is live HTML typography, without image files or attachments.
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
<div role="img" aria-label="Fluilet · Tu ritmo, tus palabras" style="font-family:'Trebuchet MS',Arial,Helvetica,sans-serif;font-size:48px;line-height:56px;font-weight:bold;letter-spacing:-1px;color:#FFFFFF;">Fluilet</div>
<div style="padding-top:4px;font-size:14px;line-height:22px;letter-spacing:1px;color:#E5DDF3;">Tu ritmo, tus palabras</div>
<table role="presentation" align="center" width="180" cellspacing="0" cellpadding="0" border="0" style="margin-top:12px;"><tr><td height="3" bgcolor="#45C6A2" style="background-color:#45C6A2;font-size:1px;line-height:3px;border-radius:3px;">&nbsp;</td></tr></table>
<div style="padding-top:16px;font-size:13px;line-height:22px;color:#FFFFFF;">Fluilet · Lectura adaptativa inteligente</div>
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


def _send_brevo(recipient: str, message: EmailMessage) -> DeliveryReceipt:
    payload = {
        "sender": {
            "name": "Fluilet",
            "email": settings.SMTP_FROM_EMAIL or settings.SMTP_USER or "fluilet123@gmail.com",
        },
        "to": [{"email": recipient}],
        "subject": str(message["Subject"]),
        "htmlContent": message.get_body(preferencelist=("html",)).get_content(),
        "textContent": message.get_body(preferencelist=("plain",)).get_content(),
    }
    with httpx.Client(
        timeout=httpx.Timeout(10, connect=5), trust_env=False, follow_redirects=False
    ) as client:
        response = client.post(
            BREVO_EMAIL_URL,
            headers={
                "api-key": settings.BREVO_API_KEY.get_secret_value(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
        )
    if response.status_code != 201:
        # Provider bodies and HTTP exceptions may contain credentials or codes.
        raise DeliveryError(response.status_code)
    try:
        message_id = response.json().get("messageId")
    except (ValueError, AttributeError):
        message_id = None
    return DeliveryReceipt("brevo", 201, message_id if isinstance(message_id, str) else None)


def _send(recipient: str, code: str):
    if settings.BREVO_API_KEY.get_secret_value():
        return _send_brevo(recipient, recovery_message(recipient, code))
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
            return await asyncio.to_thread(_send, recipient, code)
        except DeliveryError as error:
            logger.error(
                "Fluilet: Brevo rechazó el correo de recuperación (HTTP %d).", error.status_code
            )
        except Exception:
            # Never log provider replies, HTTP headers, recipients or codes.
            logger.error("Fluilet: no se pudo enviar el correo de recuperación. Revisa el correo.")
        finally:
            _smtp_slots.release()

    task = asyncio.create_task(deliver())
    _smtp_jobs.add(task)
    task.add_done_callback(_smtp_jobs.discard)
    # A disconnected request must not release a slot while its thread still runs.
    return await asyncio.shield(task)


async def close():
    if _smtp_jobs:
        await asyncio.gather(*_smtp_jobs, return_exceptions=True)
