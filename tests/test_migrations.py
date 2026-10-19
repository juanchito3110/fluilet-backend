"""Exercise migration of the actual unmanaged legacy schema, not just create_all."""

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.postgres
async def test_legacy_migration_preflight_and_metadata_preservation():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Explicit PostgreSQL test database required")
    parsed = make_url(url)
    assert (parsed.database or "").endswith("_test")
    schema = "migration_" + uuid.uuid4().hex
    admin = create_async_engine(url, hide_parameters=True)
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped_url = parsed.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(
        hide_password=False
    )
    engine = create_async_engine(scoped_url, hide_parameters=True)

    async def migrate(*args):
        env = {**os.environ, "DATABASE_URL": scoped_url}
        return await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-B", "-m", "alembic", *args],
            env=env,
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=30,
        )

    try:
        baseline = await migrate("upgrade", "0001_baseline")
        assert baseline.returncode == 0, baseline.stderr
        owner_id, document_id = uuid.uuid4(), uuid.uuid4()
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO users (id,email,hashed_password,full_name,role,is_active,is_verified,failed_login_attempts) VALUES (:id,'synthetic@example.com','synthetic-hash','Synthetic User','TUTOR',true,false,0)"
                ),
                {"id": owner_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO documents (id,owner_id,file_name,file_type,file_size_bytes,storage_path,status) VALUES (:id,:owner,'synthetic.txt','TXT',6000000,'synthetic-location','PENDING')"
                ),
                {"id": document_id, "owner": owner_id},
            )
        preflight = await migrate("upgrade", "head")
        assert preflight.returncode != 0
        assert "Resolve legacy document sizes" in preflight.stderr
        async with engine.begin() as connection:
            version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert version == "0001_baseline"
            await connection.execute(text("UPDATE documents SET file_size_bytes=20"))
        upgraded = await migrate("upgrade", "head")
        assert upgraded.returncode == 0, upgraded.stderr
        async with engine.connect() as connection:
            record = (
                await connection.execute(
                    text(
                        "SELECT owner_id,content_sha256,original_szigriszt_score,word_count FROM documents"
                    )
                )
            ).one()
            assert record.owner_id == owner_id
            assert record.content_sha256 is None and record.original_szigriszt_score is None
            assert record.word_count == 0
            columns = (
                (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns WHERE table_schema=:schema AND table_name='documents'"
                        ),
                        {"schema": schema},
                    )
                )
                .scalars()
                .all()
            )
            assert "storage_path" not in columns and "file_name" not in columns
        drift = await migrate("check")
        assert drift.returncode == 0, drift.stdout + drift.stderr
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()
