from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.nlp import pipeline as pipeline_module
from app.nlp.mt5 import runtime
from app.services import ranker


@pytest.fixture(autouse=True)
def isolate_resident_ranker(monkeypatch):
    resident = ranker.loaded_checkpoint
    monkeypatch.setattr(ranker, "loaded_checkpoint", lambda: None)
    return resident


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
        "ranker_model": "not_loaded",
        "mt5_model": model_state,
        "active_model_type": None,
        "rules_fallback_available": True,
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
    assert response.json()["rules_fallback"] is False
    assert response.json()["active_model_type"] == "mt5"


async def test_ready_identifies_the_actual_resident_final_ranker(
    client, monkeypatch, isolate_resident_ranker
):
    monkeypatch.setattr(ranker, "loaded_checkpoint", isolate_resident_ranker)
    monkeypatch.setattr(settings, "RANKER_CHECKPOINT", str(ranker.ASSET))
    monkeypatch.setattr(
        settings,
        "RANKER_CHECKPOINT_SHA256",
        "67e79bf3c13381cc8d000575e6e57b4f9787f895cbfb8cfc4569fb9ae3ba2507",
    )
    monkeypatch.setattr(runtime, "state", "not_loaded")
    monkeypatch.setattr(runtime, "_model", None)
    monkeypatch.setattr(runtime, "_tokenizer", None)
    load = AsyncMock(side_effect=AssertionError("Readiness must not load mT5"))
    monkeypatch.setattr(runtime, "prepare", load)
    ranker.checkpoint.cache_clear()
    try:
        assert ranker.loaded_checkpoint() is None
        cold = await client.get("/health/ready")
        assert cold.status_code == 200 and cold.json()["rules_fallback"] is True
        assert ranker.checkpoint.cache_info().currsize == 0
        resident = ranker.checkpoint()  # same explicit preload used by lifespan
        assert ranker.loaded_checkpoint() is resident
        assert resident["model_version"] == "context-ranker-es-v2.3"
        assert resident["metrics"]["acceptance_criteria_met"] is True
        response = await client.get("/health/ready")
        data = response.json()
        assert response.status_code == 200
        assert data["engine_mode"] == "context_ranker_refinement"
        assert data["model"] == data["ranker_model"] == "loaded"
        assert data["rules_fallback"] is False
        assert data["active_model_type"] == "context_ranker"
        assert data["mt5_model"] == "not_loaded"
        assert ranker.loaded_checkpoint() is resident
        load.assert_not_called()
    finally:
        ranker.checkpoint.cache_clear()


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
    assert response.json()["model"] == "not_loaded"
    assert response.json()["rules_fallback"] is True


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
