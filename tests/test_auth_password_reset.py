"""Public recovery, persisted abuse limits, mail MIME/TLS and token revocation."""

import asyncio
import logging
import smtplib
import ssl
import threading
from datetime import timedelta

import pytest
from fastapi import BackgroundTasks, HTTPException
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app import auth, models, schemas
from app.config import settings
from app.password_reset import code_digest, forgot_password, reset_password
from app.services import email_service
from tests.conftest import PASSWORD

NEW_PASSWORD = "NuevaClave2026!"


@pytest.fixture(autouse=True)
def isolated_smtp(monkeypatch):
    for name, value in dict(
        SMTP_HOST="smtp.gmail.com",
        SMTP_PORT=587,
        SMTP_USE_TLS=True,
        SMTP_USER="",
        SMTP_PASSWORD=SecretStr(""),
        SMTP_FROM_EMAIL="",
        SMTP_FROM_NAME="Fluilet Soporte",
        DEPLOYMENT_ENV="development",
    ).items():
        monkeypatch.setattr(settings, name, value)


@pytest.fixture
def mail(monkeypatch):
    sent = []

    async def capture(recipient, code):
        sent.append((recipient, code))

    monkeypatch.setattr(email_service, "send_reset_code", capture)
    return sent


async def latest(db, user):
    return await db.scalar(
        select(models.PasswordResetRequest)
        .where(models.PasswordResetRequest.user_id == user.id)
        .order_by(models.PasswordResetRequest.created_at.desc())
    )


async def test_recovery_end_to_end_and_revokes_all_sessions(client, make_user, db, mail):
    user, headers, old = await make_user()
    response = await client.post("/api/v1/auth/forgot-password", json={"email": user.email.upper()})
    assert response.status_code == 200 and response.json()["message"]
    assert len(mail) == 1 and mail[0][0] == user.email
    code = mail[0][1]
    assert len(code) == 6 and code.isascii() and code.isdigit()
    assert code not in response.text
    record = await latest(db, user)
    assert record.code_hash == code_digest(user, record.id, code) and len(record.code_hash) == 64
    assert record.code_hash != code and record.attempts == 0 and record.used_at is None
    assert auth.aware(record.expires_at) - auth.aware(record.created_at) == timedelta(minutes=10)
    body = {"email": user.email.upper(), "code": code}
    response = await client.post("/api/v1/auth/verify-reset-code", json=body)
    assert response.status_code == 200 and response.json()["valid"] is True
    await db.refresh(record)
    assert record.used_at is None
    response = await client.post(
        "/api/v1/auth/reset-password", json={**body, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 200 and response.json()["message"]
    await db.refresh(record)
    await db.refresh(user)
    assert record.used_at is not None and auth.verify_password(NEW_PASSWORD, user.hashed_password)
    assert not auth.verify_password(PASSWORD, user.hashed_password)
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": old.refresh_token})
    ).status_code == 401
    login = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": NEW_PASSWORD}
    )
    assert login.status_code == 200 and login.json()["role"] == "TUTOR"
    assert (
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": PASSWORD})
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/reset-password", json={**body, "new_password": "OtraClave2026!"}
        )
    ).status_code == 400
    assert (await client.post("/api/v1/auth/verify-reset-code", json=body)).status_code == 400


async def test_case_insensitive_legacy_address_and_leading_zero(
    client, make_user, db, mail, monkeypatch
):
    user, _, _ = await make_user()
    user.email = user.email.upper()
    await db.commit()
    monkeypatch.setattr("app.password_reset.secrets.randbelow", lambda limit: 7)
    assert (
        await client.post("/api/v1/auth/forgot-password", json={"email": user.email.lower()})
    ).status_code == 200
    assert mail[0][1] == "000007"
    body = {"email": user.email.lower(), "code": "000007", "new_password": NEW_PASSWORD}
    assert (await client.post("/api/v1/auth/reset-password", json=body)).status_code == 200
    assert (
        await client.post(
            "/api/v1/auth/login", data={"username": user.email.lower(), "password": NEW_PASSWORD}
        )
    ).status_code == 200


async def test_unknown_inactive_and_cooldown_are_indistinguishable(client, make_user, db, mail):
    user, _, _ = await make_user()
    first = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    cooldown = await client.post("/api/v1/auth/forgot-password", json={"email": user.email.upper()})
    absent = await client.post("/api/v1/auth/forgot-password", json={"email": "absent@example.com"})
    user.is_active = False
    await db.commit()
    inactive = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert [r.status_code for r in (first, cooldown, absent, inactive)] == [200] * 4
    assert first.json() == cooldown.json() == absent.json() == inactive.json()
    assert len(mail) == 1
    assert await db.scalar(select(func.count()).select_from(models.PasswordResetRequest)) == 1
    for address in (user.email, "absent@example.com"):
        assert (
            await client.post(
                "/api/v1/auth/verify-reset-code", json={"email": address, "code": mail[0][1]}
            )
        ).status_code == 400


@pytest.mark.parametrize("endpoint", ["verify-reset-code", "reset-password"])
async def test_expired_code_cannot_validate_or_change_password(
    client, make_user, db, mail, endpoint
):
    user, _, _ = await make_user()
    await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    record = await latest(db, user)
    record.created_at = auth.utcnow() - timedelta(minutes=11)
    record.expires_at = auth.utcnow() - timedelta(seconds=1)
    await db.commit()
    body = {"email": user.email, "code": mail[0][1]}
    if endpoint == "reset-password":
        body["new_password"] = NEW_PASSWORD
    response = await client.post("/api/v1/auth/" + endpoint, json=body)
    assert response.status_code == 400 and "venció" in response.json()["detail"]
    await db.refresh(user)
    assert auth.verify_password(PASSWORD, user.hashed_password)


async def test_five_wrong_attempts_persist_and_block_correct_code(client, make_user, db, mail):
    user, _, _ = await make_user()
    await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    code = mail[0][1]
    wrong = "000000" if code != "000000" else "999999"
    for count in range(1, 6):
        endpoint = "verify-reset-code" if count % 2 else "reset-password"
        body = {"email": user.email, "code": wrong}
        if endpoint == "reset-password":
            body["new_password"] = NEW_PASSWORD
        assert (await client.post("/api/v1/auth/" + endpoint, json=body)).status_code == 400
        record = await latest(db, user)
        await db.refresh(record)
        assert record.attempts == count
    assert record.used_at is not None
    assert (
        await client.post(
            "/api/v1/auth/reset-password",
            json={"email": user.email, "code": code, "new_password": NEW_PASSWORD},
        )
    ).status_code == 400
    await db.refresh(user)
    assert auth.verify_password(PASSWORD, user.hashed_password)


async def test_resend_invalidates_previous_and_hourly_budget(
    client, make_user, db, mail, monkeypatch
):
    user, _, _ = await make_user()
    digits = iter((111111, 222222, 333333, 444444, 555555))
    monkeypatch.setattr("app.password_reset.secrets.randbelow", lambda limit: next(digits))
    for count in range(5):
        response = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        assert response.status_code == 200 and len(mail) == count + 1
        record = await latest(db, user)
        if count == 1:
            old = await db.scalar(
                select(models.PasswordResetRequest).where(
                    models.PasswordResetRequest.id != record.id
                )
            )
            assert old.used_at is not None
            assert (
                await client.post(
                    "/api/v1/auth/verify-reset-code", json={"email": user.email, "code": "111111"}
                )
            ).status_code == 400
        record.created_at = auth.utcnow() - timedelta(seconds=61)
        await db.commit()
    assert (
        await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    ).status_code == 200
    assert len(mail) == 5
    records = (await db.scalars(select(models.PasswordResetRequest))).all()
    assert len(records) == 5 and sum(row.used_at is None for row in records) == 1


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", "１２３４５６", 123456, None])
async def test_code_input_is_strict_and_errors_do_not_echo_secrets(client, code):
    response = await client.post(
        "/api/v1/auth/verify-reset-code", json={"email": "private@example.com", "code": code}
    )
    assert response.status_code == 422
    assert "private@example.com" not in response.text and "6 dígitos" in response.text


async def test_password_rules_are_preserved_without_consuming_code(client, make_user, db, mail):
    user, _, _ = await make_user()
    await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    for password in ("short", "NoNumberOrSymbol", "Aa1!" + "á" * 35):
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"email": user.email, "code": mail[0][1], "new_password": password},
        )
        assert response.status_code == 422 and "mayúscula" in response.text
        assert password not in response.text and mail[0][1] not in response.text
    assert (await latest(db, user)).used_at is None


async def test_password_change_invalidates_outstanding_code(client, make_user, mail):
    user, headers, _ = await make_user()
    await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert (
        await client.post(
            "/api/v1/auth/password",
            headers=headers,
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        )
    ).status_code == 204
    assert (
        await client.post(
            "/api/v1/auth/verify-reset-code", json={"email": user.email, "code": mail[0][1]}
        )
    ).status_code == 400


def test_professional_mail_has_plain_and_inline_html_and_no_remote_resources():
    message = email_service.recovery_message("reader@hotmail.com", "000123")
    assert message.get_content_type() == "multipart/alternative"
    assert [p.get_content_type() for p in message.iter_parts()] == ["text/plain", "text/html"]
    plain = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    for text in (plain, html):
        assert "000123" in text and "10 minutos" in text
        assert "Fluilet · Lectura adaptativa inteligente" in text
    assert "letter-spacing: 8px" in html and "FluiBot" in html
    assert "<!--[if mso]>" in html and 'name="viewport"' in html
    assert 'role="presentation"' in html and "#5B3E8C" in html
    assert "https://" not in html and "<script" not in html
    assert "reader@hotmail.com" not in html
    with pytest.raises(ValueError):
        email_service.recovery_message("reader@gmail.com", "<code>")


@pytest.mark.parametrize(
    "recipient", ["reader@gmail.com", "reader@hotmail.com", "reader@outlook.com"]
)
async def test_real_smtp_path_tls_mime_and_off_event_loop(monkeypatch, recipient):
    monkeypatch.setattr(settings, "SMTP_USER", "sender@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", SecretStr("smtp-private-app-password"))
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "support@fluilet.com")
    monkeypatch.setattr(settings, "SMTP_USE_TLS", True)
    events = []
    event_thread = threading.get_ident()

    class SMTP:
        def __init__(self, host, port, timeout):
            assert host == "smtp.gmail.com" and port == 587 and timeout == 10
            assert threading.get_ident() != event_thread

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def ehlo(self):
            events.append("ehlo")

        def starttls(self, *, context):
            assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
            events.append("tls")

        def login(self, user, password):
            assert user == "sender@gmail.com" and password == "smtp-private-app-password"
            events.append("login")

        def send_message(self, message):
            assert message["To"] == recipient and "support@fluilet.com" in message["From"]
            assert "456789" in message.get_body(preferencelist=("html",)).get_content()
            events.append("sent")
            return {}

    monkeypatch.setattr(email_service.smtplib, "SMTP", SMTP)
    await email_service.send_reset_code(recipient, "456789")
    assert events == ["ehlo", "tls", "ehlo", "login", "sent"]


@pytest.mark.parametrize("missing", ["user", "password"])
async def test_unconfigured_local_smtp_logs_code_without_recipient(monkeypatch, caplog, missing):
    monkeypatch.setattr(settings, "DEPLOYMENT_ENV", "development")
    monkeypatch.setattr(settings, "SMTP_USER", "sender@gmail.com" if missing == "password" else "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", SecretStr("secret" if missing == "user" else ""))
    caplog.set_level(logging.WARNING, logger="fluilet.email")
    await email_service.send_reset_code("private@hotmail.com", "000123")
    assert "000123" in caplog.text and "DESARROLLO" in caplog.text
    assert "private@hotmail.com" not in caplog.text and "secret" not in caplog.text


async def test_production_never_logs_missing_smtp_code_or_server_exception(monkeypatch, caplog):
    monkeypatch.setattr(settings, "DEPLOYMENT_ENV", "production")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", SecretStr(""))
    await email_service.send_reset_code("private@gmail.com", "000123")
    monkeypatch.setattr(settings, "SMTP_USER", "sender@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", SecretStr("smtp-private-secret"))

    def fail(*args, **kwargs):
        raise smtplib.SMTPException("private@gmail.com smtp-private-secret 000123")

    monkeypatch.setattr(email_service.smtplib, "SMTP", fail)
    await email_service.send_reset_code("private@gmail.com", "000123")
    assert (
        "000123" not in caplog.text
        and "private@gmail.com" not in caplog.text
        and "smtp-private-secret" not in caplog.text
    )
    assert "SMTP" in caplog.text


@pytest.mark.postgres
async def test_concurrent_requests_send_once_and_reset_is_single_use(
    db, make_user, monkeypatch, mail
):
    if db.bind.dialect.name != "postgresql":
        pytest.skip("PostgreSQL account locks required")
    user, _, _ = await make_user()
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)

    async def request():
        async with sessions() as session:
            background = BackgroundTasks()
            await forgot_password(
                schemas.ForgotPasswordRequest(email=user.email), background, session
            )
            await background()

    await asyncio.gather(request(), request())
    assert len(mail) == 1
    code = mail[0][1]
    payload = schemas.ResetPasswordRequest(email=user.email, code=code, new_password=NEW_PASSWORD)

    async def change():
        async with sessions() as session:
            try:
                await reset_password(payload, session)
                return 200
            except HTTPException as error:
                return error.status_code

    assert sorted(await asyncio.gather(change(), change())) == [200, 400]
    assert await db.scalar(select(func.count()).select_from(models.PasswordResetRequest)) == 1


async def test_smtp_failure_keeps_same_public_response(client, make_user, monkeypatch):
    user, _, _ = await make_user()
    monkeypatch.setattr(settings, "SMTP_USER", "sender@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", SecretStr("smtp-private-secret"))

    def unavailable(*args, **kwargs):
        raise smtplib.SMTPException("provider-private-error")

    monkeypatch.setattr(email_service.smtplib, "SMTP", unavailable)
    first = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    unknown = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "absent@example.com"}
    )
    assert first.status_code == unknown.status_code == 200
    assert first.json() == unknown.json() and "provider-private-error" not in first.text


async def test_smtp_cancellation_does_not_release_running_thread_slot(monkeypatch):
    started = threading.Event()
    finish = threading.Event()
    monkeypatch.setattr(email_service, "_smtp_slots", asyncio.Semaphore(1))

    def blocking(*args):
        started.set()
        assert finish.wait(5)

    monkeypatch.setattr(email_service, "_send", blocking)
    job = asyncio.create_task(email_service.send_reset_code("reader@example.com", "000123"))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        job.cancel()
        with pytest.raises(asyncio.CancelledError):
            await job
        assert email_service._smtp_slots.locked()
        await email_service.send_reset_code("other@example.com", "000456")
        assert len(email_service._smtp_jobs) == 1
    finally:
        finish.set()
        await email_service.close()
    assert not email_service._smtp_slots.locked()


async def test_account_deletion_cascades_recovery_requests(client, make_user, db, mail):
    user, _, _ = await make_user()
    await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert await latest(db, user) is not None
    await db.delete(user)
    await db.commit()
    assert await db.scalar(select(func.count()).select_from(models.PasswordResetRequest)) == 0


@pytest.mark.postgres
async def test_password_reset_migration_upgrades_and_rolls_back_only_ephemeral_codes(password_hash):
    import os
    import subprocess
    import sys
    import uuid
    from pathlib import Path

    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Dedicated PostgreSQL test database required")
    assert make_url(url).database.endswith("_test")
    name = "reset_migration_" + uuid.uuid4().hex
    admin = create_async_engine(url, hide_parameters=True)
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{name}"'))
    scoped = (
        make_url(url)
        .update_query_dict({"options": f"-csearch_path={name}"})
        .render_as_string(hide_password=False)
    )
    engine = create_async_engine(scoped, hide_parameters=True)
    env = {**os.environ, "DATABASE_URL": scoped, "DEMO_ACCOUNTS_ENABLED": "false"}

    async def migrate(*args):
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-B", "-m", "alembic", *args],
            cwd=Path(__file__).parents[1],
            env=env,
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert result.returncode == 0, result.stderr

    try:
        await migrate("upgrade", "0007_master_accounts")
        identity = uuid.uuid4()
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO users (id,email,hashed_password,full_name,role,is_active,is_verified,failed_login_attempts) VALUES (:id,'migration@example.com',:password,'Migration user','TUTOR',true,false,0)"
                ),
                {"id": identity, "password": password_hash},
            )
        await migrate("upgrade", "head")
        await migrate("check")
        async with engine.begin() as connection:
            assert (
                await connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0009_password_reset"
            )
            assert (
                await connection.scalar(text("SELECT hashed_password FROM users")) == password_hash
            )
            await connection.execute(
                text(
                    "INSERT INTO password_reset_requests (id,user_id,code_hash,expires_at) VALUES (:id,:user,:digest,CURRENT_TIMESTAMP+INTERVAL '10 minutes')"
                ),
                {"id": uuid.uuid4(), "user": identity, "digest": "a" * 64},
            )
        await migrate("downgrade", "0007_master_accounts")
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT count(*) FROM users")) == 1
        await migrate("upgrade", "head")
        await migrate("check")
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
        await admin.dispose()
