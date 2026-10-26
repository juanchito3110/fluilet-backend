"""Public API schemas. Legacy lowercase roles and Android NLP names are accepted."""

import re
import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.education import category_name
from app.models import DifficultyType, DocumentStatus, DocumentType, UserRole, VisualPalette


def nlp_level(value):
    if isinstance(value, str) and value.upper() in {"BASICO", "INTERMEDIO", "AVANZADO"}:
        return {"BASICO": 1, "INTERMEDIO": 3, "AVANZADO": 5}[value.upper()]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Nivel NLP inválido.")
    return value


NlpLevel = Annotated[int, BeforeValidator(nlp_level), Field(ge=1, le=5)]


def validar_password_fuerte(value: str) -> str:
    if not isinstance(value, str) or not 10 <= len(value) <= 72 or len(value.encode("utf-8")) > 72:
        raise ValueError("La contraseña requiere 10 caracteres y admite hasta 72 bytes UTF-8.")
    if any(c.isspace() for c in value) or not all(
        re.search(p, value) for p in (r"[A-Z]", r"[a-z]", r"\d", r"[^\w\s]")
    ):
        raise ValueError(
            "La contraseña requiere mayúscula, minúscula, número y símbolo, sin espacios."
        )
    return value


Password = Annotated[
    str, Field(min_length=10, max_length=72), BeforeValidator(validar_password_fuerte)
]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class UserBase(InputModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Nombre inválido.")
        return value


class UserCreate(UserBase):
    password: Password
    role: UserRole

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value):
        return value.upper() if isinstance(value, str) else value

    @field_validator("role")
    @classmethod
    def public_roles(cls, value):
        if value == UserRole.NINO:
            raise ValueError("Las cuentas infantiles solo puede crearlas su tutor.")
        return value


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime


class NoNullPatch(InputModel):
    @model_validator(mode="before")
    @classmethod
    def reject_null(cls, values):
        if isinstance(values, dict) and any(v is None for v in values.values()):
            raise ValueError("Omite los campos que no deseas modificar; no se admite null.")
        return values


class UserUpdate(NoNullPatch):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value):
        return UserBase.clean_name(value)


class PasswordChange(InputModel):
    current_password: str = Field(max_length=72)
    new_password: Password


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: UserRole


class TokenRefreshRequest(InputModel):
    refresh_token: str = Field(min_length=10, max_length=4096)


class ChildProfileBase(InputModel):
    name: str = Field(min_length=2, max_length=100)
    birth_date: date
    tipo_dificultad: DifficultyType
    nivel_simplificacion_nlp: NlpLevel = 3
    paleta_visual: VisualPalette = VisualPalette.ESTANDAR
    tamano_fuente: int = Field(default=18, ge=14, le=28)
    interlineado: float = Field(default=1.5, ge=1.5, le=2.5)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        return UserBase.clean_name(value)


class ChildProfileCreate(ChildProfileBase):
    pin: str | None = Field(default=None, pattern=r"^[0-9]{4,6}$")

    @field_validator("birth_date")
    @classmethod
    def valid_age(cls, value):
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if not 6 <= age <= 11:
            raise ValueError("Edad permitida: 6 a 11 años.")
        return value


class ChildProfileUpdate(NoNullPatch):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    tipo_dificultad: DifficultyType | None = None
    nivel_simplificacion_nlp: NlpLevel | None = None
    paleta_visual: VisualPalette | None = None
    tamano_fuente: int | None = Field(default=None, ge=14, le=28)
    interlineado: float | None = Field(default=None, ge=1.5, le=2.5)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        return UserBase.clean_name(value)


class ChildProfileRead(ChildProfileBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tutor_id: uuid.UUID
    user_id: uuid.UUID | None
    is_active: bool
    created_at: datetime


class ChildAccountCreate(InputModel):
    email: EmailStr
    password: Password


class ChildSessionRequest(InputModel):
    pin: str | None = Field(default=None, pattern=r"^[0-9]{4,6}$")


class TelemetryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    original_szigriszt_score: float | None
    adapted_szigriszt_score: float | None
    score_delta: float | None
    original_word_count: int | None
    adapted_word_count: int | None
    original_syllable_count: int | None
    original_sentence_count: int | None
    syllable_count: int | None
    sentence_count: int | None
    maintenance_exception: bool

    @computed_field
    @property
    def meets_readability_target(self) -> bool | None:
        original, adapted = self.original_szigriszt_score, self.adapted_szigriszt_score
        if original is None or adapted is None:
            return None
        return (
            adapted >= 85.0
            if original > 128.535
            else adapted >= 65.0 and adapted - original >= 15.0
        )


class LessonGenerate(InputModel):
    category: str = Field(max_length=128)
    topic: str | None = Field(default=None, max_length=120)
    simplification_level: NlpLevel = 2
    child_id: uuid.UUID | None = None
    custom_topic: str | None = Field(default=None, max_length=120)
    target_level: NlpLevel | None = None

    @model_validator(mode="after")
    def aliases_agree(self):
        if self.custom_topic is not None:
            if self.topic is not None and self.topic.casefold() != self.custom_topic.casefold():
                raise ValueError("Los temas no coinciden.")
            self.topic = self.custom_topic
        if self.target_level is not None:
            if (
                "simplification_level" in self.model_fields_set
                and self.simplification_level != self.target_level
            ):
                raise ValueError("Los niveles no coinciden.")
            self.simplification_level = self.target_level
        return self

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value):
        value = category_name(value)
        return "ciencia_espacio" if value == "lectura_libre" else value

    @field_validator("topic", "custom_topic")
    @classmethod
    def clean_topic(cls, value):
        if value is None:
            return None
        value = " ".join("".join(c for c in value if c.isprintable() or c.isspace()).split())
        return value or None


class ComprehensionQuestion(BaseModel):
    id: Literal["q1", "q2"]
    question: str
    options: list[str] = Field(min_length=3, max_length=3)
    correct_option_index: int = Field(ge=0, le=2)
    hint: str
    explanation: str


class DocumentRead(TelemetryRead):
    id: uuid.UUID
    content_sha256: str | None
    file_type: DocumentType
    file_size_bytes: int
    word_count: int
    chunk_count: int
    status: DocumentStatus
    adaptation_method: str | None
    category: str
    simplification_level: int
    uploaded_at: datetime


class AdaptTextRequest(InputModel):
    text: str = Field(min_length=1, max_length=5 * 1024 * 1024)
    nivel_simplificacion_nlp: NlpLevel = 3
    child_id: uuid.UUID | None = None


class ChunkRead(TelemetryRead):
    chunk_index: int


class VocabularyEntry(BaseModel):
    word: str
    definition: str
    example: str


class LessonSource(BaseModel):
    provider: Literal["local", "wikipedia"]
    title: str
    url: str
    license: str | None = None
    license_url: str | None = None
    revision_id: int | None = None


class AdaptationRead(BaseModel):
    document: DocumentRead
    adapted_text: str
    chunks: list[ChunkRead]
    meets_readability_target: bool
    quality_status: Literal["target_met", "best_effort"]
    warnings: list[str]
    title: str
    category: str
    simplification_level: int
    comprehension_questions: list[ComprehensionQuestion] = Field(min_length=2, max_length=2)
    question_age_group: Literal["6-8", "9-11", "12+"]
    child_age_years: int | None
    fun_fact: str
    key_vocabulary: list[VocabularyEntry] = Field(max_length=4)
    source: LessonSource | None = None
    resolved_topic: str | None = None


class AssignmentRequest(InputModel):
    document_id: uuid.UUID


class EducationalReadingInput(InputModel):
    category: str | None = Field(default=None, min_length=1, max_length=64)
    simplification_level: NlpLevel | None = None
    comprehension_score: int | None = Field(default=None, ge=0, le=100, strict=True)
    questions_answered: int | None = Field(default=None, ge=0, le=10000, strict=True)
    questions_correct: int | None = Field(default=None, ge=0, le=10000, strict=True)
    tts_speed_used: float | None = Field(default=None, gt=0, le=4, allow_inf_nan=False, strict=True)

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value):
        return category_name(value) if value is not None else value

    @model_validator(mode="before")
    @classmethod
    def reject_nonnullable_fields(cls, values):
        if isinstance(values, dict) and any(
            value is None for key, value in values.items() if key != "comprehension_score"
        ):
            raise ValueError("Omite los campos que no deseas modificar.")
        return values


class ReadingCreate(EducationalReadingInput):
    document_id: uuid.UUID


class ReadingUpdate(EducationalReadingInput):
    reading_time_seconds: int | None = Field(default=None, ge=0, le=86400 * 30)
    completion_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    completed: bool | None = None


class ReadingRead(TelemetryRead):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    child_id: uuid.UUID | None
    reader_user_id: uuid.UUID | None = None
    document_id: uuid.UUID | None
    started_at: datetime
    ended_at: datetime | None
    reading_time_seconds: int
    completion_percent: float
    completed: bool
    category: str
    simplification_level: int
    comprehension_score: int | None
    questions_answered: int
    questions_correct: int
    tts_speed_used: float


class LessonProgress(BaseModel):
    lesson_number: int
    reading_id: str
    recorded_at: str
    category: str
    simplification_level: int
    completed: bool
    completion_percentage: int
    comprehension_score: int | None
    duration_seconds: int
    original_readability_score: float | None
    adapted_readability_score: float | None


class EducationalBadge(BaseModel):
    code: str
    title: str
    description: str
    unlocked: bool


class FluiBotState(BaseModel):
    name: Literal["FluiBot"]
    species: Literal["robot"]
    stage: int = Field(ge=1, le=4)
    stage_name: str
    stage_description: str
    current_xp: int = Field(ge=0)
    next_stage_xp: int
    progress_percent: float = Field(ge=0, le=100)


class CollectibleCard(BaseModel):
    category: str
    title: str
    fun_fact: str
    rarity: Literal["Bloqueada", "Bronce", "Plata", "Oro"]
    unlocked: bool
    lessons_completed_in_category: int = Field(ge=0)


class ShopAccessory(BaseModel):
    item_id: str
    name: str
    slot: str
    description: str
    cost_gems: int = Field(ge=15, le=120)
    unlocked: bool


class PedagogicalSummary(BaseModel):
    headline: str
    strength_area: str
    focus_area: str
    recommendation: str


class DailyMission(BaseModel):
    id: str
    title: str
    description: str
    reward_gems: int
    progress: int = Field(ge=0)
    target: int = Field(ge=1)
    completed: bool


class EducationalProgress(BaseModel):
    total_lessons: int
    completed_lessons: int
    incomplete_lessons: int
    completion_rate_percent: float
    total_reading_seconds: int
    average_comprehension_score: float
    current_recommended_level: int
    level_progression: list[LessonProgress]
    badges: list[EducationalBadge]
    streak_days: int = Field(ge=0)
    total_gems: int = Field(ge=30)
    total_xp: int = Field(ge=0)
    total_stars: int = Field(ge=30)
    current_rank_title: str
    next_rank_stars: int
    mascot: FluiBotState
    collectible_cards: list[CollectibleCard] = Field(min_length=6, max_length=6)
    shop_catalog: list[ShopAccessory] = Field(min_length=10, max_length=10)
    pedagogical_summary: PedagogicalSummary
    daily_missions: list[DailyMission] = Field(min_length=3, max_length=3)


class SessionProgress(BaseModel):
    sessionLabel: str
    accumulatedMinutes: float
    completionPercent: int
