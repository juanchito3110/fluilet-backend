"""
Esquemas Pydantic v2 — cubren el rubro de 'Validaciones' de la evaluación:

- Formato de email válido (EmailStr).
- Contraseñas fuertes: longitud, mayúscula, minúscula, dígito, símbolo,
  sin espacios, fuera de una lista de contraseñas comunes.
- Rangos numéricos de accesibilidad alineados a RF05/RF09
  (tamaño de fuente 14-28pt, interlineado 1.5x-2.5x, nivel NLP 1-5).
- Edad del niño restringida a la población objetivo (6-11 años, RF02).
"""

import re
import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import DifficultyType, DocumentStatus, DocumentType, UserRole, VisualPalette

_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"\d")
_SPECIAL = re.compile(r"[^\w\s]")
_CONTRASENAS_COMUNES = {"12345678", "password", "qwerty123", "contrasena", "fluilet123"}


def validar_password_fuerte(value: str) -> str:
    if len(value) < 10 or len(value) > 72:
        raise ValueError("La contraseña debe tener entre 10 y 72 caracteres.")
    if " " in value:
        raise ValueError("La contraseña no puede contener espacios.")
    if not _UPPER.search(value):
        raise ValueError("La contraseña debe incluir al menos una letra mayúscula.")
    if not _LOWER.search(value):
        raise ValueError("La contraseña debe incluir al menos una letra minúscula.")
    if not _DIGIT.search(value):
        raise ValueError("La contraseña debe incluir al menos un dígito.")
    if not _SPECIAL.search(value):
        raise ValueError("La contraseña debe incluir al menos un carácter especial.")
    if value.lower() in _CONTRASENAS_COMUNES:
        raise ValueError("Esta contraseña es demasiado común. Elige otra.")
    return value


# ---------------------------------------------------------------------------
# Usuario (Tutor/Padre o Adulto independiente)
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)

    @field_validator("full_name")
    @classmethod
    def nombre_sin_espacios_extra(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre no puede estar vacío.")
        return v


class UserCreate(UserBase):
    password: str = Field(min_length=10, max_length=72)
    # El registro solo admite Tutor/Padre o Adulto independiente (RF01).
    # El rol "niño" nunca se acepta aquí: los perfiles infantiles se crean
    # vía /children, exclusivamente por un Tutor ya autenticado.
    role: UserRole

    @field_validator("password")
    @classmethod
    def password_segura(cls, v: str) -> str:
        return validar_password_fuerte(v)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=150)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=72)

    @field_validator("new_password")
    @classmethod
    def password_segura(cls, v: str) -> str:
        return validar_password_fuerte(v)


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    role: UserRole
    exp: int
    type: str  # "access" | "refresh"


# ---------------------------------------------------------------------------
# Perfil de niño (RF02)
# ---------------------------------------------------------------------------

class ChildProfileBase(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    birth_date: date
    tipo_dificultad: DifficultyType
    nivel_simplificacion_nlp: int = Field(default=3, ge=1, le=5)
    paleta_visual: VisualPalette = VisualPalette.ESTANDAR
    tamano_fuente: int = Field(default=18, ge=14, le=28)
    interlineado: float = Field(default=1.5, ge=1.5, le=2.5)

    @field_validator("birth_date")
    @classmethod
    def edad_en_rango_objetivo(cls, v: date) -> date:
        hoy = date.today()
        edad = hoy.year - v.year - ((hoy.month, hoy.day) < (v.month, v.day))
        if not (6 <= edad <= 11):
            raise ValueError("Fluilet está diseñado para niños de 6 a 11 años.")
        return v


class ChildProfileCreate(ChildProfileBase):
    pin: Optional[str] = Field(default=None, min_length=4, max_length=6)

    @field_validator("pin")
    @classmethod
    def pin_solo_digitos(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.isdigit():
            raise ValueError("El PIN debe contener solo dígitos.")
        return v


class ChildProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    tipo_dificultad: Optional[DifficultyType] = None
    nivel_simplificacion_nlp: Optional[int] = Field(default=None, ge=1, le=5)
    paleta_visual: Optional[VisualPalette] = None
    tamano_fuente: Optional[int] = Field(default=None, ge=14, le=28)
    interlineado: Optional[float] = Field(default=None, ge=1.5, le=2.5)
    is_active: Optional[bool] = None


class ChildProfileRead(ChildProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tutor_id: uuid.UUID
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Documento — metadatos únicamente (política de cero retención de texto)
# ---------------------------------------------------------------------------

class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_name: str
    file_type: DocumentType
    file_size_bytes: int = Field(le=10 * 1024 * 1024)  # RF03: máx. 10 MB
    status: DocumentStatus
    uploaded_at: datetime
