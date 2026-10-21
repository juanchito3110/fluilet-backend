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
        upgraded = await migrate("upgrade", "0002_zero_retention")
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
        # Exercise the new migration with an existing child's reading, not just
        # an empty table, and verify exact numerical snapshot backfill.
        from app.nlp.readability import measure, telemetry
        from app.nlp.refinement import refine
        from tests.conftest import SOURCE

        metrics = telemetry(measure(SOURCE), measure(refine(SOURCE)))
        child_id, reading_id = uuid.uuid4(), uuid.uuid4()
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO child_profiles (id,tutor_id,name,birth_date,tipo_dificultad,nivel_simplificacion_nlp,paleta_visual,tamano_fuente,interlineado,is_active) VALUES (:id,:owner,'Synthetic Child',DATE '2018-01-01','DISLEXIA',3,'ESTANDAR',18,1.5,true)"
                ),
                {"id": child_id, "owner": owner_id},
            )
            assignments = ", ".join(f"{name} = :{name}" for name in metrics)
            await connection.execute(text("UPDATE documents SET " + assignments), metrics)
            await connection.execute(
                text(
                    "INSERT INTO reading_sessions (id,child_id,document_id,reading_time_seconds,completion_percent,completed) VALUES (:id,:child,:document,0,0,false)"
                ),
                {"id": reading_id, "child": child_id, "document": document_id},
            )
        final = await migrate("upgrade", "head")
        assert final.returncode == 0, final.stderr
        async with engine.connect() as connection:
            reading = (
                await connection.execute(
                    text(
                        "SELECT child_id,reader_user_id,score_delta,original_szigriszt_score,adapted_szigriszt_score FROM reading_sessions WHERE id=:id"
                    ),
                    {"id": reading_id},
                )
            ).one()
            assert reading.child_id == child_id and reading.reader_user_id is None
            assert reading.score_delta == metrics["score_delta"]
            assert reading.original_szigriszt_score == metrics["original_szigriszt_score"]
            assert reading.adapted_szigriszt_score == metrics["adapted_szigriszt_score"]
        # A clean downgrade/upgrade must preserve existing, qualifying snapshots.
        rollback = await migrate("downgrade", "0003_adult_telemetry")
        assert rollback.returncode == 0, rollback.stderr
        restored = await migrate("upgrade", "head")
        assert restored.returncode == 0, restored.stderr
        # All three constraints must allow below-target but internally consistent
        # telemetry. A rollback must refuse to erase or invalidate that history.
        below_target = telemetry(measure(SOURCE), measure(SOURCE))
        assignments = ", ".join(f"{name} = :{name}" for name in below_target)
        async with engine.begin() as connection:
            for table in ("documents", "reading_sessions"):
                await connection.execute(text(f"UPDATE {table} SET " + assignments), below_target)
            fields = ", ".join(below_target)
            values = ", ".join(f":{name}" for name in below_target)
            await connection.execute(
                text(
                    f"INSERT INTO adaptation_chunks (id,document_id,chunk_index,{fields}) VALUES (:id,:document,0,{values})"
                ),
                {"id": uuid.uuid4(), "document": document_id, **below_target},
            )
        refused = await migrate("downgrade", "0003_adult_telemetry")
        assert refused.returncode != 0
        assert "best-effort telemetry requires the current schema" in refused.stderr
        async with engine.connect() as connection:
            assert (
                await connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0004_best_effort"
            )
            assert await connection.scalar(text("SELECT score_delta FROM reading_sessions")) == 0
        drift = await migrate("check")
        assert drift.returncode == 0, drift.stdout + drift.stderr
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()
