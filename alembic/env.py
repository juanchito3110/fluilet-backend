"""Async migrations. Never print SQL or credentials from DATABASE_URL."""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from alembic import context
from app.config import settings
from app.models import Base


def offline():
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def online():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, hide_parameters=True)
    async with engine.connect() as connection:
        await connection.run_sync(migrate)
    await engine.dispose()


if context.is_offline_mode():
    offline()
else:
    asyncio.run(online())
