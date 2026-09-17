"""
Esquema de base de datos (SQLAlchemy 2.0 / PostgreSQL) para Fluilet.

Decisiones de diseño relevantes para el rubro de 'Base de datos' / 'Arquitectura':

1. RBAC — Tutor/Padre y Adulto independiente son los ÚNICOS roles que se
   autentican con email + contraseña (RF01). El "Niño" NO tiene credenciales
   propias: es un perfil (ChildProfile) creado y administrado por su Tutor
   (RF02), acorde a la LFPDPPP para datos de menores. El acceso del niño se
   resuelve como un cambio de perfil dentro de la sesión ya autenticada del
   Tutor (opcionalmente protegido con un PIN corto), nunca con un JWT propio
   de larga vida emitido a nombre del menor.

2. Cero retención de texto en la nube — la tabla `documents` almacena
   ÚNICAMENTE metadatos del archivo (nombre, tipo, tamaño, ruta de
   almacenamiento). Ni el texto original ni el texto simplificado por el
   motor NLP se persisten en la base de datos, conforme a la política de
   seguridad declarada en el Project Charter.

3. UUID como PK en todas las tablas para no filtrar conteos/orden de
   registros (relevante tratándose de datos de menores) y para facilitar
   claves distribuidas si el proyecto escala a múltiples backends.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums de dominio
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    TUTOR = "tutor"
    ADULTO_INDEPENDIENTE = "adulto_independiente"


class DifficultyType(str, enum.Enum):
    DISLEXIA = "dislexia"
    TDAH = "tdah"
    COMBINADO = "combinado"


class VisualPalette(str, enum.Enum):
    ALTO_CONTRASTE = "alto_contraste"
    SEPIA = "sepia"
    ESTANDAR = "estandar"


class DocumentType(str, enum.Enum):
    PDF = "pdf"
    TXT = "txt"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def _uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


# ---------------------------------------------------------------------------
# Usuarios — Tutor/Padre y Adulto independiente (los únicos que se autentican)
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=True), nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Mitigación de fuerza bruta (OWASP MSTG-AUTH-9 / ASVS V2.2)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    children: Mapped[list["ChildProfile"]] = relationship(
        back_populates="tutor", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Perfiles de niño (RF02) — vinculados a un Tutor, sin credenciales propias
# ---------------------------------------------------------------------------

class ChildProfile(Base):
    __tablename__ = "child_profiles"
    __table_args__ = (
        CheckConstraint("nivel_simplificacion_nlp BETWEEN 1 AND 5", name="ck_nivel_nlp_rango"),
        CheckConstraint("tamano_fuente BETWEEN 14 AND 28", name="ck_tamano_fuente_rango"),
        CheckConstraint("interlineado BETWEEN 1.5 AND 2.5", name="ck_interlineado_rango"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tutor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)

    # RF02: tipo de dificultad y nivel de simplificación NLP configurados por el tutor
    tipo_dificultad: Mapped[DifficultyType] = mapped_column(
        SAEnum(DifficultyType, name="difficulty_type", native_enum=True), nullable=False
    )
    nivel_simplificacion_nlp: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Preferencias de accesibilidad (RF05 / RF09)
    paleta_visual: Mapped[VisualPalette] = mapped_column(
        SAEnum(VisualPalette, name="visual_palette", native_enum=True),
        default=VisualPalette.ESTANDAR,
        nullable=False,
    )
    tamano_fuente: Mapped[int] = mapped_column(Integer, default=18, nullable=False)
    interlineado: Mapped[float] = mapped_column(Float, default=1.5, nullable=False)

    # PIN corto opcional para cambiar de perfil dentro de la app.
    # Se guarda hasheado con bcrypt; NO es un mecanismo de autenticación JWT.
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tutor: Mapped["User"] = relationship(back_populates="children")
    reading_sessions: Mapped[list["ReadingSession"]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    library: Mapped[list["ChildLibraryItem"]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Documentos (RF03) — SOLO METADATOS. Política de cero retención de texto.
# ---------------------------------------------------------------------------

class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 10485760", name="ck_tamano_max_10mb"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type", native_enum=True), nullable=False
    )
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status", native_enum=True),
        default=DocumentStatus.PENDING,
        nullable=False,
    )

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="documents")
    assigned_to: Mapped[list["ChildLibraryItem"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    reading_sessions: Mapped[list["ReadingSession"]] = relationship(back_populates="document")


class ChildLibraryItem(Base):
    """Vincula un documento a la biblioteca de un niño, curada por su Tutor."""

    __tablename__ = "child_library_items"
    __table_args__ = (UniqueConstraint("child_id", "document_id", name="uq_child_document"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    child_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    child: Mapped["ChildProfile"] = relationship(back_populates="library")
    document: Mapped["Document"] = relationship(back_populates="assigned_to")


# ---------------------------------------------------------------------------
# Sesiones de lectura (RF08)
# ---------------------------------------------------------------------------

class ReadingSession(Base):
    __tablename__ = "reading_sessions"
    __table_args__ = (
        CheckConstraint("progress_percentage BETWEEN 0 AND 100", name="ck_progreso_rango"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    child_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    child: Mapped["ChildProfile"] = relationship(back_populates="reading_sessions")
    document: Mapped["Document"] = relationship(back_populates="reading_sessions")


# ---------------------------------------------------------------------------
# Refresh tokens — permite revocación/rotación (OWASP ASVS 3.x)
# ---------------------------------------------------------------------------

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
