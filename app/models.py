"""Accounts, relationships and numerical telemetry only. Never document content."""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums de dominio
# ---------------------------------------------------------------------------


class UserRole(enum.StrEnum):
    TUTOR = "TUTOR"
    NINO = "NINO"
    ADULTO_INDEPENDIENTE = "ADULTO_INDEPENDIENTE"


class DifficultyType(enum.StrEnum):
    DISLEXIA = "dislexia"
    TDAH = "tdah"
    COMBINADO = "combinado"


class VisualPalette(enum.StrEnum):
    ALTO_CONTRASTE = "alto_contraste"
    SEPIA = "sepia"
    ESTANDAR = "estandar"


class DocumentType(enum.StrEnum):
    PDF = "pdf"
    TXT = "txt"


class DocumentStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def _uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


# ---------------------------------------------------------------------------
# Cuentas autenticables — Tutor, Niño y Adulto independiente
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
    auth_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Mitigación de fuerza bruta (OWASP MSTG-AUTH-9 / ASVS V2.2)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    children: Mapped[list["ChildProfile"]] = relationship(
        back_populates="tutor", cascade="all, delete-orphan", foreign_keys="ChildProfile.tutor_id"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Perfiles vinculados a un Tutor y, opcionalmente, a una cuenta NINO
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

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
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

    # PIN adicional para abrir una sesión infantil desde la sesión del tutor.
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tutor: Mapped["User"] = relationship(back_populates="children", foreign_keys=[tutor_id])
    reading_sessions: Mapped[list["ReadingSession"]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    library: Mapped[list["ChildLibraryItem"]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Documentos (RF03) — SOLO METADATOS. Política de cero retención de texto.
# ---------------------------------------------------------------------------


class AdaptationTelemetry:
    # Nullable only for legacy records whose content must never be reconstructed.
    original_szigriszt_score: Mapped[float | None] = mapped_column(Float)
    adapted_szigriszt_score: Mapped[float | None] = mapped_column(Float)
    score_delta: Mapped[float | None] = mapped_column(Float)
    original_word_count: Mapped[int | None] = mapped_column(Integer)
    adapted_word_count: Mapped[int | None] = mapped_column(Integer)
    original_syllable_count: Mapped[int | None] = mapped_column(Integer)
    original_sentence_count: Mapped[int | None] = mapped_column(Integer)
    syllable_count: Mapped[int | None] = mapped_column(Integer)
    sentence_count: Mapped[int | None] = mapped_column(Integer)
    maintenance_exception: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )


TELEMETRY_CHECK = "(original_szigriszt_score IS NULL AND adapted_szigriszt_score IS NULL AND score_delta IS NULL AND original_word_count IS NULL AND adapted_word_count IS NULL AND original_syllable_count IS NULL AND original_sentence_count IS NULL AND syllable_count IS NULL AND sentence_count IS NULL AND maintenance_exception = false) OR (original_szigriszt_score IS NOT NULL AND adapted_szigriszt_score IS NOT NULL AND score_delta IS NOT NULL AND original_word_count IS NOT NULL AND adapted_word_count IS NOT NULL AND original_syllable_count IS NOT NULL AND original_sentence_count IS NOT NULL AND syllable_count IS NOT NULL AND sentence_count IS NOT NULL AND original_word_count > 0 AND adapted_word_count > 0 AND original_syllable_count > 0 AND original_sentence_count > 0 AND syllable_count > 0 AND sentence_count > 0 AND abs(original_szigriszt_score) < 1000000000000 AND abs(adapted_szigriszt_score) < 1000000000000 AND score_delta = adapted_szigriszt_score - original_szigriszt_score AND ((original_szigriszt_score > 128.535 AND maintenance_exception = true) OR (original_szigriszt_score <= 128.535 AND maintenance_exception = false)))"


class Document(AdaptationTelemetry, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 5242880", name="ck_tamano_max_5mb"
        ),
        UniqueConstraint("owner_id", "content_sha256", name="uq_owner_content_sha256"),
        CheckConstraint("word_count >= 0 AND chunk_count >= 0", name="ck_document_counts"),
        CheckConstraint(TELEMETRY_CHECK, name="ck_document_acceptance"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    file_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type", native_enum=True), nullable=False
    )
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    adaptation_method: Mapped[str | None] = mapped_column(String(32))

    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status", native_enum=True),
        default=DocumentStatus.PENDING,
        nullable=False,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

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
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    child: Mapped["ChildProfile"] = relationship(back_populates="library")
    document: Mapped["Document"] = relationship(back_populates="assigned_to")


# ---------------------------------------------------------------------------
# Sesiones de lectura (RF08)
# ---------------------------------------------------------------------------


class ReadingSession(AdaptationTelemetry, Base):
    __tablename__ = "reading_sessions"
    __table_args__ = (
        CheckConstraint("completion_percent BETWEEN 0 AND 100", name="ck_progreso_rango"),
        CheckConstraint("reading_time_seconds >= 0", name="ck_reading_time"),
        CheckConstraint("NOT completed OR completion_percent = 100", name="ck_completed_progress"),
        CheckConstraint(
            "(child_id IS NOT NULL AND reader_user_id IS NULL) OR (child_id IS NULL AND reader_user_id IS NOT NULL)",
            name="ck_reading_single_owner",
        ),
        CheckConstraint(TELEMETRY_CHECK, name="ck_reading_acceptance"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    child_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("child_profiles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    reader_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reading_time_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    child: Mapped["ChildProfile | None"] = relationship(back_populates="reading_sessions")
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
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class AdaptationChunk(AdaptationTelemetry, Base):
    __tablename__ = "adaptation_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk"),
        CheckConstraint("chunk_index >= 0", name="ck_chunk_index"),
        CheckConstraint(TELEMETRY_CHECK, name="ck_chunk_acceptance"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
