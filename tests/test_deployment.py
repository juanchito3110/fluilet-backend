"""Container migration startup, checksum loading and actual PostgreSQL chain."""

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app import bootstrap
from app.config import settings
from app.services import ranker
from app.services.joint import features, sari_vector


def test_bootstrap_serializes_migrations_then_executes_server(monkeypatch):
    connection = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = connection
    monkeypatch.setattr("psycopg.connect", lambda *a, **k: context)
    migrated = []
    monkeypatch.setattr(bootstrap.command, "upgrade", lambda cfg, target: migrated.append(target))
    executed = []
    monkeypatch.setattr(
        bootstrap.os, "execvp", lambda program, args: executed.append((program, args))
    )
    bootstrap.main()
    assert migrated == ["head"]
    assert connection.execute.call_args_list[0].args[0] == "SELECT pg_advisory_lock(417830722)"
    assert connection.execute.call_args_list[-1].args[0] == "SELECT pg_advisory_unlock(417830722)"
    assert executed[0][0] == sys.executable and "uvicorn" in executed[0][1]


def test_failed_migration_stops_startup_without_private_error(monkeypatch):
    def fail():
        raise RuntimeError("private-db-details")

    monkeypatch.setattr(bootstrap, "migrate", fail)
    with pytest.raises(SystemExit) as error:
        bootstrap.main()
    assert "private-db-details" not in str(error.value)


def test_explicit_checkpoint_missing_or_wrong_checksum_fails_closed(tmp_path, monkeypatch):
    previous = ranker.ASSET
    try:
        monkeypatch.setattr(settings, "RANKER_CHECKPOINT", str(tmp_path / "missing.json"))
        ranker.checkpoint.cache_clear()
        with pytest.raises(RuntimeError, match="missing"):
            ranker.checkpoint()
        monkeypatch.setattr(settings, "RANKER_CHECKPOINT", str(previous))
        monkeypatch.setattr(settings, "RANKER_CHECKPOINT_SHA256", "0" * 64)
        ranker.checkpoint.cache_clear()
        with pytest.raises(RuntimeError, match="checksum"):
            ranker.checkpoint()
    finally:
        ranker.checkpoint.cache_clear()


def test_sari_feature_projection_ignores_boundaries_and_requested_band():
    source = "Los niños leen libros. Los niños usan mapas."
    candidate = "Los niños leen libros; Los niños usan mapas."
    assert sari_vector(features(source, source, 1)) == sari_vector(features(source, candidate, 5))


def test_production_requires_private_demo_credentials():
    from app.config import Settings

    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            DEPLOYMENT_ENV="production",
            SECRET_KEY="a" * 48,
            DEMO_ACCOUNTS_ENABLED=True,
        )
    value = Settings(
        _env_file=None,
        DEPLOYMENT_ENV="production",
        DEMO_ACCOUNTS_ENABLED=True,
        SECRET_KEY="a" * 48,
        DEMO_TUTOR_PASSWORD="OwnTutorPass2026!",
        DEMO_MASTER_PASSWORD="OwnMasterPass2026!",
    )
    assert value.DEPLOYMENT_ENV == "production"


@pytest.mark.postgres
async def test_container_startup_applies_all_eight_revisions_idempotently():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Explicit PostgreSQL test database required")
    assert make_url(url).database.endswith("_test")
    schema = "bootstrap_" + uuid.uuid4().hex
    admin = create_async_engine(url, hide_parameters=True)
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = (
        make_url(url)
        .update_query_dict({"options": f"-csearch_path={schema}"})
        .render_as_string(hide_password=False)
    )
    env = {**os.environ, "DATABASE_URL": scoped, "DEMO_ACCOUNTS_ENABLED": "false"}
    try:
        for _ in range(2):
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-B", "-c", "from app.bootstrap import migrate; migrate()"],
                cwd=Path(__file__).parents[1],
                env=env,
                capture_output=True,
                text=True,
                timeout=40,
            )
            assert result.returncode == 0, result.stderr
        check = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-B", "-m", "alembic", "check"],
            cwd=Path(__file__).parents[1],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert check.returncode == 0, check.stderr
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(Config(str(Path(__file__).parents[1] / "alembic.ini")))
        assert len(list(script.walk_revisions())) == 8
    finally:
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()
