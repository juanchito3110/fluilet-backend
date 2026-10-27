"""Validated configuration. ML is optional and never imported at API startup."""

from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    DATABASE_URL: str = "postgresql+psycopg://fluilet:changeme@localhost:5432/fluilet"
    SECRET_KEY: SecretStr = Field(min_length=32)
    ALGORITHM: Literal["HS256"] = "HS256"
    JWT_ISSUER: str = "fluilet-api"
    JWT_AUDIENCE: str = "fluilet-android"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=30)
    BCRYPT_ROUNDS: int = Field(default=13, ge=13, le=16)
    CORS_ORIGINS: list[str] = ["http://localhost"]
    MAX_BODY_BYTES: int = Field(default=5 * 1024 * 1024, ge=1024, le=5 * 1024 * 1024)
    BODY_TIMEOUT_SECONDS: float = Field(default=15, gt=0, le=60)
    MAX_DOCUMENT_WORDS: int = Field(default=20000, ge=800, le=50000)
    MAX_PDF_PAGES: int = Field(default=100, ge=1, le=500)
    PROCESSING_CONCURRENCY: int = Field(default=2, ge=1, le=4)
    PROCESSING_TIMEOUT_SECONDS: float = Field(default=60, gt=0, le=180)
    DEMO_ACCOUNTS_ENABLED: bool = True
    DEPLOYMENT_ENV: Literal["development", "production"] = "development"
    DEMO_TUTOR_PASSWORD: SecretStr | None = Field(default=None, min_length=10, max_length=72)
    DEMO_MASTER_PASSWORD: SecretStr | None = Field(default=None, min_length=10, max_length=72)
    RANKER_CHECKPOINT: str | None = None
    RANKER_CHECKPOINT_SHA256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    WIKIPEDIA_ENABLED: bool = True
    WIKIPEDIA_TIMEOUT_SECONDS: float = Field(default=3.5, gt=0, le=3.5)
    MAX_GENERATION_ATTEMPTS: int = Field(default=3, ge=1, le=5)
    MT5_MODEL: Literal["google/mt5-small", "google/mt5-base"] = "google/mt5-small"
    MT5_CHECKPOINT: str | None = None
    MT5_LOCAL_FILES_ONLY: bool = True
    MT5_ENABLED: bool = True
    MT5_CONCURRENCY: int = Field(default=1, ge=1, le=2)
    MT5_TIMEOUT_SECONDS: float = Field(default=20, gt=0, le=120)
    MT5_MAX_INPUT_TOKENS: int = Field(default=4096, ge=128, le=8192)
    MT5_MAX_NEW_TOKENS: int = Field(default=2048, ge=32, le=4096)
    # Legacy configuration retained; faithful best-effort delivery is mandatory.
    ALLOW_RULE_BASED_FALLBACK: bool = True
    REQUESTS_PER_MINUTE: int = Field(default=120, ge=1)
    AUTH_REQUESTS_PER_MINUTE: int = Field(default=15, ge=1)

    @model_validator(mode="after")
    def production_secrets(self):
        if self.DEPLOYMENT_ENV == "production":
            required = [self.SECRET_KEY]
            if self.DEMO_ACCOUNTS_ENABLED:
                required.extend([self.DEMO_TUTOR_PASSWORD, self.DEMO_MASTER_PASSWORD])
            if any(
                value is None
                or value.get_secret_value() in {"Tutor2026!", "Master2026!"}
                or value.get_secret_value().lower().startswith(("replace", "change"))
                for value in required
            ):
                raise ValueError(
                    "Producción requiere secretos propios para JWT y las cuentas gestionadas."
                )
        return self


settings = Settings()
