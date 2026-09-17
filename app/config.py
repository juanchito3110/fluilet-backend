"""
Configuración centralizada de Fluilet API.

Todos los valores sensibles (SECRET_KEY, credenciales de BD) se leen desde
variables de entorno / archivo .env — NUNCA se hardcodean en el código
(OWASP MSTG-STORAGE-1 / ASVS 6.4).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base de datos (PostgreSQL en DigitalOcean según Project Charter)
    DATABASE_URL: str = "postgresql+psycopg://fluilet:changeme@localhost:5432/fluilet"

    # JWT
    SECRET_KEY: str  # obligatorio — generar con: openssl rand -hex 32
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # RF07: hashing bcrypt con factor de coste >= 12
    BCRYPT_ROUNDS: int = 12

    # CORS — restringir en producción al dominio real de la app / panel tutor
    CORS_ORIGINS: list[str] = ["http://localhost"]


settings = Settings()
