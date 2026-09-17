"""
Motor y sesión de SQLAlchemy para PostgreSQL.

En producción, el esquema se gestiona con Alembic (migraciones versionadas),
no con `init_db()` — esa función es solo para arranque rápido en desarrollo.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings
from app.models import Base

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependencia de FastAPI: una sesión por request, cerrada al finalizar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea las tablas directamente desde los modelos. Solo para desarrollo local."""
    Base.metadata.create_all(bind=engine)
