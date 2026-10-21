from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.nlp import pipeline as pipeline_module
from app.nlp.mt5 import runtime


@pytest.mark.parametrize("model_state", ["not_loaded", "unavailable"])
async def test_ready_with_operational_rules_without_loading_weights(
    client, monkeypatch, model_state
):
    monkeypatch.setattr(settings, "ALLOW_RULE_BASED_FALLBACK", True)
    monkeypatch.setattr(runtime, "state", model_state)
    monkeypatch.setattr(runtime, "_model", None)
    load = AsyncMock(side_effect=AssertionError("Probe must never load weights"))
    monkeypatch.setattr(runtime, "prepare", load)
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "operational",
        "pipeline": "operational",
        "engine_mode": "deterministic",
        "model": model_state,
        "rules_fallback": True,
    }
    load.assert_not_called()


@pytest.mark.parametrize("fallback,mode", [(True, "hybrid"), (False, "mt5_refinement")])
async def test_ready_reports_loaded_engine_mode(client, monkeypatch, fallback, mode):
    monkeypatch.setattr(settings, "ALLOW_RULE_BASED_FALLBACK", fallback)
    monkeypatch.setattr(runtime, "state", "loaded")
    monkeypatch.setattr(runtime, "_model", object())
    monkeypatch.setattr(runtime, "_tokenizer", object())
    response = await client.get("/health/ready")
    assert response.status_code == 200 and response.json()["engine_mode"] == mode


async def test_ready_keeps_mandatory_reading_fallback_when_legacy_flag_disabled(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "ALLOW_RULE_BASED_FALLBACK", False)
    monkeypatch.setattr(runtime, "state", "loaded")
    monkeypatch.setattr(runtime, "_model", None)
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "operational"
    assert response.json()["engine_mode"] == "deterministic"


async def test_ready_reports_database_failure_without_exception_details(client, db, monkeypatch):
    monkeypatch.setattr(
        db, "execute", AsyncMock(side_effect=RuntimeError("private-database-error"))
    )
    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    assert response.json()["pipeline"] == "unchecked"
    assert "private-database-error" not in response.text
    assert (await client.get("/health/live")).status_code == 200


async def test_ready_detects_broken_deterministic_pipeline(client, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("private-pipeline-error")

    monkeypatch.setattr(pipeline_module, "refine", broken)
    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["pipeline"] == "unavailable"
    assert "private-pipeline-error" not in response.text
