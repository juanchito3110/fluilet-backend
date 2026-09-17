"""
Seguridad de Fluilet API:
- Hashing de contraseñas con bcrypt, factor de coste >= 12 (RF07).
- Emisión y validación de JWT (access + refresh, con rotación).
- Dependencias de FastAPI para autenticación y autorización basada en roles (RBAC).
- Mitigación básica de fuerza bruta (bloqueo temporal por intentos fallidos).
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


# ---------------------------------------------------------------------------
# Hashing de contraseñas (RF07: bcrypt, factor de coste >= 12)
# ---------------------------------------------------------------------------

def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def _create_token(subject: str, role: UserRole, expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role.value,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user: User) -> str:
    return _create_token(
        str(user.id), user.role, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access"
    )


def create_refresh_token(user: User) -> str:
    return _create_token(
        str(user.id), user.role, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh"
    )


def decode_token(token: str) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la credencial.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise credentials_exception
    if "sub" not in payload or "type" not in payload:
        raise credentials_exception
    return payload


# ---------------------------------------------------------------------------
# Dependencias de autenticación / autorización (RBAC)
# ---------------------------------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tipo de token inválido.")

    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido.")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no encontrado o inactivo.")
    return user


def require_roles(*allowed_roles: UserRole):
    """Dependencia de fábrica: protege un endpoint restringiéndolo a ciertos roles (RBAC)."""

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "No tienes permisos para realizar esta acción."
            )
        return current_user

    return _dependency


# ---------------------------------------------------------------------------
# Control de fuerza bruta (OWASP MSTG-AUTH-9 / ASVS V2.2)
# ---------------------------------------------------------------------------

def is_locked_out(user: User) -> bool:
    return bool(user.locked_until and user.locked_until > datetime.now(timezone.utc))


def register_failed_attempt(user: User, db: Session) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
    db.commit()


def reset_failed_attempts(user: User, db: Session) -> None:
    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
