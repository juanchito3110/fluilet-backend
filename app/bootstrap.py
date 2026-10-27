"""Container startup: serialize/apply the actual Alembic chain before HTTP."""

import os
import sys
from pathlib import Path

from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from app.config import settings


def migrate():
    import psycopg

    root = Path(__file__).resolve().parents[1]
    configuration = Config(str(root / "alembic.ini"))
    configuration.set_main_option("script_location", str(root / "alembic"))
    url = make_url(settings.DATABASE_URL).set(drivername="postgresql")
    # A session advisory lock covers all eight revisions across concurrent starts.
    with psycopg.connect(
        url.render_as_string(hide_password=False), autocommit=True, connect_timeout=15
    ) as lock:
        lock.execute("SELECT pg_advisory_lock(417830722)")
        try:
            command.upgrade(configuration, "head")
        finally:
            lock.execute("SELECT pg_advisory_unlock(417830722)")


def main():
    # An error stops startup; no credentials or user content in process output.
    try:
        migrate()
    except Exception:
        raise SystemExit("No se pudo aplicar el esquema de la base de datos.") from None
    os.execvp(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--workers",
            "1",
            "--loop",
            "asyncio",
            "--no-access-log",
            "--log-level",
            "critical",
            "--no-proxy-headers",
            "--limit-concurrency",
            "32",
        ],
    )


if __name__ == "__main__":
    main()
