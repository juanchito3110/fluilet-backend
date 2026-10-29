"""Public recovery flow: keyed digests, account locks, expiry and resend budget."""

import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth, models, schemas
from app.config import settings
from app.database import get_db
from app.services import email_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
GENERIC_MESSAGE = "Si el correo está registrado, recibirás un código de recuperación. Revisa tu bandeja de entrada y spam. Puedes solicitar otro después de un minuto."
INVALID_MESSAGE = (
    "El código es incorrecto, venció o ya no está disponible. Solicita uno nuevo si es necesario."
)


def code_digest(user, identity, code):
    # Six-digit SHA alone is vulnerable to offline enumeration. Key the digest
    # and bind it to this request/account/auth-version, with constant-time check.
    value = f"password-reset:{user.id}:{user.auth_version}:{identity}:{code}"
    return hmac.new(
        settings.SECRET_KEY.get_secret_value().encode(), value.encode(), hashlib.sha256
    ).hexdigest()


async def account(email, db):
    return await db.scalar(
        select(models.User)
        .where(func.lower(models.User.email) == str(email).lower())
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def invalidate(user_id, db, now):
    await db.execute(
        update(models.PasswordResetRequest)
        .where(
            models.PasswordResetRequest.user_id == user_id,
            models.PasswordResetRequest.used_at.is_(None),
        )
        .values(used_at=now)
    )


@router.post("/forgot-password", response_model=schemas.AuthMessage)
async def forgot_password(
    payload: schemas.ForgotPasswordRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    user = await account(payload.email, db)
    result = schemas.AuthMessage(message=GENERIC_MESSAGE)
    if user is None or not user.is_active:
        return result
    now = auth.utcnow()
    recent = (
        await db.scalars(
            select(models.PasswordResetRequest)
            .where(
                models.PasswordResetRequest.user_id == user.id,
                models.PasswordResetRequest.created_at > now - timedelta(hours=1),
            )
            .order_by(
                models.PasswordResetRequest.created_at.desc(), models.PasswordResetRequest.id.desc()
            )
            .limit(5)
        )
    ).all()
    # Same generic 200 for cooldown/hourly budget, unknown and inactive accounts.
    if len(recent) >= 5 or (
        recent and auth.aware(recent[0].created_at) > now - timedelta(seconds=60)
    ):
        return result
    await invalidate(user.id, db, now)
    identity = uuid.uuid4()
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        models.PasswordResetRequest(
            id=identity,
            user_id=user.id,
            code_hash=code_digest(user, identity, code),
            expires_at=now + timedelta(minutes=10),
            created_at=now,
            attempts=0,
        )
    )
    await db.commit()
    # Deliver after the response; neither SMTP nor bcrypt block the event loop.
    background.add_task(email_service.send_reset_code, user.email, code)
    return result


async def validate_code(payload, db):
    user = await account(payload.email, db)
    if user is None or not user.is_active:
        raise HTTPException(400, INVALID_MESSAGE)
    request = await db.scalar(
        select(models.PasswordResetRequest)
        .where(models.PasswordResetRequest.user_id == user.id)
        .order_by(
            models.PasswordResetRequest.created_at.desc(), models.PasswordResetRequest.id.desc()
        )
        .limit(1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = auth.utcnow()
    if (
        request is None
        or request.used_at is not None
        or request.attempts >= 5
        or auth.aware(request.expires_at) <= now
    ):
        raise HTTPException(400, INVALID_MESSAGE)
    if not hmac.compare_digest(request.code_hash, code_digest(user, request.id, payload.code)):
        request.attempts += 1
        if request.attempts >= 5:
            request.used_at = now
        # The dependency rolls back raised errors: commit failed attempts first.
        await db.commit()
        raise HTTPException(400, INVALID_MESSAGE)
    return user, request


@router.post("/verify-reset-code", response_model=schemas.ResetCodeVerification)
async def verify_reset_code(
    payload: schemas.VerifyResetCodeRequest, db: AsyncSession = Depends(get_db)
):
    await validate_code(payload, db)
    await db.commit()  # verification does not consume the code needed for reset
    return schemas.ResetCodeVerification(
        valid=True, message="Código válido. Ya puedes establecer tu nueva contraseña."
    )


@router.post("/reset-password", response_model=schemas.AuthMessage)
async def reset_password(payload: schemas.ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    user, _ = await validate_code(payload, db)
    user.hashed_password = await auth.hash_async(payload.new_password)
    user.failed_login_attempts, user.locked_until = 0, None
    await auth.revoke_all(user, db)
    await invalidate(user.id, db, auth.utcnow())
    await db.commit()
    return schemas.AuthMessage(
        message="Tu contraseña se actualizó. Inicia sesión con tu nueva contraseña."
    )
