"""Async authentication, bcrypt >=13, scoped child identities and refresh rotation."""

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError as JWTError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import ChildProfile, RefreshToken, User, UserRole
from app.schemas import Token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")
_hash_slots = asyncio.Semaphore(2)
_dummy_hash: str | None = None
_hash_jobs: set[asyncio.Task] = set()


def utcnow():
    return datetime.now(UTC)


def aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def unauthorized():
    return HTTPException(401, "Credenciales inválidas.", headers={"WWW-Authenticate": "Bearer"})


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if not raw or len(raw) > 72:
        raise ValueError("Longitud de contraseña inválida.")
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), encoded.encode())
    except (ValueError, TypeError):
        return False


async def _hash_work(function, *args):
    if _hash_slots.locked():
        raise HTTPException(
            503, "Autenticación ocupada. Intenta más tarde.", headers={"Retry-After": "5"}
        )
    # Acquire before task creation: no unbounded queue between the check/acquire.
    await _hash_slots.acquire()

    async def work():
        try:
            return await asyncio.to_thread(function, *args)
        finally:
            _hash_slots.release()

    task = asyncio.create_task(work())
    _hash_jobs.add(task)

    def finished(job):
        _hash_jobs.discard(job)
        if not job.cancelled():
            job.exception()

    task.add_done_callback(finished)
    return await asyncio.shield(task)


async def hash_async(password: str) -> str:
    return await _hash_work(hash_password, password)


async def verify_async(password: str, encoded: str | None) -> bool:
    global _dummy_hash
    if encoded is None:
        if _dummy_hash is None:
            _dummy_hash = await _hash_work(hash_password, uuid.uuid4().hex)
        await _hash_work(verify_password, password, _dummy_hash)
        return False
    return await _hash_work(verify_password, password, encoded)


async def close():
    if _hash_jobs:
        await asyncio.gather(*_hash_jobs, return_exceptions=True)


def encode_token(user: User, kind: str) -> str:
    now = utcnow()
    ttl = (
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        if kind == "access"
        else timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    return jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role.value,
            "type": kind,
            "iat": now,
            "exp": now + ttl,
            "jti": str(uuid.uuid4()),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "ver": user.auth_version,
        },
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.ALGORITHM,
    )


def decode_token(token: str, kind: str = "access") -> dict:
    try:
        data = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={"require": ["exp", "iat", "sub", "jti", "aud", "iss", "role", "type", "ver"]},
        )
        uuid.UUID(data["sub"])
        uuid.UUID(data["jti"])
        UserRole(data["role"])
        if (
            data["type"] != kind
            or type(data["ver"]) is not int
            or data["iat"] > utcnow().timestamp() + 30
        ):
            raise ValueError()
        return data
    except (JWTError, ValueError, KeyError, TypeError, AttributeError):
        raise unauthorized() from None


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def child_for_user(user: User, db: AsyncSession) -> ChildProfile:
    child = await db.scalar(
        select(ChildProfile).where(
            ChildProfile.user_id == user.id, ChildProfile.is_active.is_(True)
        )
    )
    tutor = await db.get(User, child.tutor_id) if child else None
    if child is None or tutor is None or not tutor.is_active or tutor.role != UserRole.TUTOR:
        raise unauthorized()
    return child


async def validate_identity(user: User | None, db: AsyncSession):
    if user is None or not user.is_active:
        raise unauthorized()
    if user.role == UserRole.NINO:
        await child_for_user(user, db)
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    data = decode_token(token)
    user = await validate_identity(await db.get(User, uuid.UUID(data["sub"])), db)
    if user.auth_version != data["ver"] or user.role.value != data["role"]:
        raise unauthorized()
    return user


def require_roles(*roles: UserRole):
    async def dependency(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(403, "Acceso no permitido.")
        return user

    return dependency


async def issue_pair(user: User, db: AsyncSession, family_id: uuid.UUID | None = None) -> Token:
    access = encode_token(user, "access")
    refresh = encode_token(user, "refresh")
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_digest(refresh),
            family_id=family_id or uuid.uuid4(),
            expires_at=utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return Token(
        access_token=access,
        refresh_token=refresh,
        role=user.role,
        is_master_admin=user.is_master_admin,
    )


async def revoke_all(user: User, db: AsyncSession):
    user.auth_version += 1
    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True)
    )


async def rotate_refresh(token: str, db: AsyncSession) -> Token:
    data = decode_token(token, "refresh")
    # Every issuance/revocation serializes on the user row (also across API workers).
    user = await db.scalar(select(User).where(User.id == uuid.UUID(data["sub"])).with_for_update())
    user = await validate_identity(user, db)
    record = await db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_digest(token), RefreshToken.user_id == user.id)
        .with_for_update()
    )
    if record is None:
        raise unauthorized()
    if record.revoked:
        await revoke_all(user, db)
        await db.commit()
        raise unauthorized()
    if (
        aware(record.expires_at) <= utcnow()
        or user.auth_version != data["ver"]
        or user.role.value != data["role"]
    ):
        raise unauthorized()
    record.revoked = True
    result = await issue_pair(user, db, record.family_id)
    await db.commit()
    return result
