"""Async psycopg persistence; schema changes belong exclusively to Alembic."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    hide_parameters=True,
    pool_size=5,
    max_overflow=5,
    pool_timeout=5,
    connect_args={
        "connect_timeout": 5,
        "options": "-c statement_timeout=10000 -c idle_in_transaction_session_timeout=70000",
    },
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
