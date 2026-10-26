"""All tests use RAM SQLite or a private schema in an explicit *_test PostgreSQL DB."""

import os
import uuid
from datetime import date

os.environ["SECRET_KEY"] = "test-key-0000000000000000000000000000000000000000000"
os.environ["DATABASE_URL"] = "postgresql+psycopg://test:test@127.0.0.1:1/unused"
os.environ["MT5_ENABLED"] = "false"
os.environ["WIKIPEDIA_ENABLED"] = "false"

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import auth, models
from app.database import get_db
from app.main import app

PASSWORD = "ValidPass123!"
SOURCE = (
    "Los alumnos utilizan libros y posteriormente realizan actividades con sus amigos en la escuela. "
    * 3
).strip()


@pytest.fixture(scope="session")
def password_hash():
    return auth.hash_password(PASSWORD)


@pytest_asyncio.fixture
async def db():
    url = os.environ.get("TEST_DATABASE_URL")
    admin = None
    schema = None
    if url:
        assert (make_url(url).database or "").endswith("_test"), (
            "Use an explicitly dedicated *_test database"
        )
        schema = "test_" + uuid.uuid4().hex
        admin = create_async_engine(url, hide_parameters=True)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(
            url, connect_args={"options": f"-csearch_path={schema}"}, hide_parameters=True
        )
    else:
        engine = create_async_engine("sqlite+aiosqlite://", hide_parameters=True)

        @event.listens_for(engine.sync_engine, "connect")
        def foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

    try:
        async with engine.begin() as connection:
            await connection.run_sync(models.Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False, autoflush=False)() as session:
            yield session
    finally:
        await engine.dispose()
        if admin:
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()


@pytest_asyncio.fixture
async def client(db):
    async def override():
        try:
            yield db
        except BaseException:
            await db.rollback()
            raise

    app.dependency_overrides[get_db] = override
    # Reset only rate buckets between tests, preserving all real middleware logic.
    middleware = app.middleware_stack
    while middleware is not None:
        if hasattr(middleware, "buckets"):
            middleware.buckets.clear()
        middleware = getattr(middleware, "app", None)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as instance:
        yield instance
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def make_user(db, password_hash):
    async def factory(role=models.UserRole.TUTOR):
        user = models.User(
            email=f"{uuid.uuid4().hex}@example.com",
            full_name="Test User",
            role=role,
            hashed_password=password_hash,
        )
        db.add(user)
        await db.flush()
        tokens = await auth.issue_pair(user, db)
        await db.commit()
        return user, {"Authorization": "Bearer " + tokens.access_token}, tokens

    return factory


@pytest.fixture
def child_payload():
    today = date.today()
    return {
        "name": "Test Child",
        "birth_date": today.replace(year=today.year - 8).isoformat(),
        "tipo_dificultad": "dislexia",
        "nivel_simplificacion_nlp": "BASICO",
    }
