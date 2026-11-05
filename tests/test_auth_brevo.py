"""HTTPS recovery delivery, transport preference and provider failure privacy."""

import json
import logging
import re

import httpx
import pytest
from pydantic import SecretStr

from app.config import settings
from app.services import email_service

FAKE_KEY = "unit-test-only-brevo-key"


@pytest.fixture(autouse=True)
def brevo_settings(monkeypatch):
    monkeypatch.setattr(settings, "BREVO_API_KEY", SecretStr(FAKE_KEY))
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "fluilet123@gmail.com")
    monkeypatch.setattr(settings, "SMTP_USER", "smtp-user@example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", SecretStr("unit-test-smtp-secret"))

    def forbidden_smtp(*args, **kwargs):
        raise AssertionError("Configured Brevo must never fall through to SMTP")

    monkeypatch.setattr(email_service.smtplib, "SMTP", forbidden_smtp)


def transport(monkeypatch, handler):
    client_class = httpx.Client

    def client(**options):
        assert options["trust_env"] is False
        assert options["follow_redirects"] is False
        assert options["timeout"].connect == 5 and options["timeout"].read == 10
        return client_class(transport=httpx.MockTransport(handler), **options)

    monkeypatch.setattr(email_service.httpx, "Client", client)


async def test_brevo_uses_https_and_the_existing_html_without_attachments(monkeypatch):
    requests = []

    def accept(request):
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://api.brevo.com/v3/smtp/email"
        assert request.headers["api-key"] == FAKE_KEY
        assert request.headers["content-type"] == "application/json"
        payload = json.loads(request.content)
        assert payload["sender"] == {"name": "Fluilet", "email": "fluilet123@gmail.com"}
        assert payload["to"] == [{"email": "reader@hotmail.com"}]
        message = email_service.recovery_message("reader@hotmail.com", "000123")
        assert payload["subject"] == str(message["Subject"])
        assert payload["htmlContent"] == message.get_body(preferencelist=("html",)).get_content()
        assert payload["textContent"] == message.get_body(preferencelist=("plain",)).get_content()
        assert "000123" in payload["htmlContent"] and "10 minutos" in payload["textContent"]
        assert 'aria-label="Fluilet' in payload["htmlContent"]
        assert "<img" not in payload["htmlContent"] and "attachment" not in payload
        return httpx.Response(201, json={"messageId": "<test-message@brevo.invalid>"})

    transport(monkeypatch, accept)
    result = await email_service.send_reset_code("reader@hotmail.com", "000123")
    assert result == email_service.DeliveryReceipt("brevo", 201, "<test-message@brevo.invalid>")
    assert len(requests) == 1


async def test_brevo_does_not_require_smtp_login_credentials(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", SecretStr(""))
    transport(monkeypatch, lambda request: httpx.Response(201, json={}))
    assert (await email_service.send_reset_code("reader@example.com", "000123")).status_code == 201


@pytest.mark.parametrize("status", [202, 302, 400, 401, 403, 429, 500])
async def test_brevo_failure_never_logs_private_response_or_falls_back(monkeypatch, caplog, status):
    calls = []

    def reject(request):
        calls.append(request)
        return httpx.Response(
            status,
            json={"message": f"private@example.com 000123 {FAKE_KEY}"},
            headers={"Location": "https://untrusted.invalid/"},
        )

    transport(monkeypatch, reject)
    with caplog.at_level(logging.ERROR, logger="fluilet.email"):
        assert await email_service.send_reset_code("private@example.com", "000123") is None
    assert len(calls) == 1 and f"HTTP {status}" in caplog.text
    assert all(value not in caplog.text for value in (FAKE_KEY, "000123", "private@example.com"))


async def test_brevo_network_error_is_redacted_and_does_not_log_the_code(monkeypatch, caplog):
    def fail(request):
        raise httpx.ReadTimeout(f"{FAKE_KEY} private@example.com 000123", request=request)

    transport(monkeypatch, fail)
    with caplog.at_level(logging.ERROR, logger="fluilet.email"):
        assert await email_service.send_reset_code("private@example.com", "000123") is None
    assert "no se pudo enviar" in caplog.text
    assert all(value not in caplog.text for value in (FAKE_KEY, "000123", "private@example.com"))


async def test_real_recovery_contract_works_through_brevo(client, make_user, monkeypatch):
    sent = []

    def accept(request):
        sent.append(json.loads(request.content))
        return httpx.Response(201, json={"messageId": "<recovery-test@brevo.invalid>"})

    transport(monkeypatch, accept)
    user, _, _ = await make_user()
    response = await client.post("/api/v1/auth/forgot-password", json={"email": user.email.upper()})
    assert response.status_code == 200 and len(sent) == 1
    assert sent[0]["to"] == [{"email": user.email}]
    code = re.search(r"Tu código de seguridad es: ([0-9]{6})", sent[0]["textContent"])[1]
    assert code not in response.text
    verified = await client.post(
        "/api/v1/auth/verify-reset-code", json={"email": user.email, "code": code}
    )
    assert verified.status_code == 200 and verified.json()["valid"] is True


def test_settings_never_reveal_brevo_key_in_representations():
    assert FAKE_KEY not in repr(settings) and FAKE_KEY not in settings.model_dump_json()
