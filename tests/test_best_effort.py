"""Regression: quality targets must never prevent opening a valid reading."""

import asyncio

import pytest
from sqlalchemy import func, select

from app import models
from app.config import settings
from app.nlp.pipeline import AdaptationPipeline
from app.nlp.readability import measure
from app.nlp.refinement import fidelity_ok, refine
from app.nlp.segmentation import sentences, words
from tests.test_pipeline import Offline
from tests.test_zero_retention import pdf_bytes

TEXT_A = (
    "La proliferación contemporánea de estímulos audiovisuales fragmentados obstaculiza "
    "considerablemente la consolidación de los procesos cognitivos vinculados con la comprensión "
    "lectora sostenida en infantes diagnosticados con sintomatología de inatención o dificultades "
    "fonológicas."
)
TEXT_B = (
    "Los estudiantes que presentan dificultades adicionales durante las actividades escolares "
    "necesitan subsecuentemente materiales pedagógicos accesibles. Asimismo, la implementación "
    "de herramientas tecnológicas contemporáneas facilita considerablemente la comprensión de "
    "los libros en la escuela."
)
TECHNICAL = "La espectrointerferometría analiza matrices hiperdimensionales extraordinariamente sofisticadas."


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
@pytest.mark.parametrize(
    "text",
    [TEXT_A, TEXT_B, "Hola", TECHNICAL, " ".join([TEXT_B] * 40), "neuropsicología " * 801],
    ids=["A", "B", "one-word", "technical", "long", "unsplittable"],
)
async def test_valid_text_opens_reading_at_every_level(client, make_user, text, level):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/text",
        headers=headers,
        json={"text": text, "nivel_simplificacion_nlp": level},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["adapted_text"]
    original, adapted = measure(text), measure(data["adapted_text"])
    assert data["document"]["original_szigriszt_score"] == original.score
    assert data["document"]["adapted_szigriszt_score"] == adapted.score
    assert data["document"]["score_delta"] == adapted.score - original.score
    assert adapted.score >= original.score
    assert data["quality_status"] == (
        "target_met" if data["meets_readability_target"] else "best_effort"
    )
    if text.strip() == TECHNICAL or text.startswith("neuropsicología"):
        assert not data["meets_readability_target"]
        assert "readability_target_not_met" in data["warnings"]


@pytest.mark.parametrize("text", [TEXT_A, TEXT_B])
def test_manual_examples_are_simplified_and_split_without_losing_scope(text):
    candidate = refine(text, attempt=2, level=1)
    assert fidelity_ok(text, candidate)
    assert len(sentences(candidate)) > len(sentences(text))
    assert max(len(words(s)) for s in sentences(candidate)) < len(words(text))
    assert measure(candidate).score > measure(text).score
    if text == TEXT_A:
        assert "diagnóstico" in candidate and " o " in candidate
        assert "sonidos del lenguaje" in candidate
    else:
        assert "estudiantes con más dificultades" in candidate
        assert "Poner en marcha estas herramientas" in candidate


@pytest.mark.parametrize("level", [1, 3, 5])
@pytest.mark.parametrize("media_type", ["text/plain", "application/pdf"])
async def test_file_endpoint_also_delivers_below_target_text(client, make_user, level, media_type):
    _, headers, _ = await make_user()
    content = (
        TECHNICAL.encode() if media_type == "text/plain" else pdf_bytes(TECHNICAL.replace("í", "i"))
    )
    response = await client.post(
        f"/api/v1/adaptations/file?nivel_simplificacion_nlp={level}",
        headers={**headers, "Content-Type": media_type},
        content=content,
    )
    assert response.status_code == 200, response.text
    assert response.json()["quality_status"] == "best_effort"


@pytest.mark.parametrize("adult", [True, False])
async def test_below_target_telemetry_persists_in_reading_sessions(
    client, db, make_user, child_payload, adult
):
    role = models.UserRole.ADULTO_INDEPENDIENTE if adult else models.UserRole.TUTOR
    _, headers, _ = await make_user(role)
    child_id = None
    if not adult:
        child_id = (
            await client.post("/api/v1/children", headers=headers, json=child_payload)
        ).json()["id"]
    data = (
        await client.post(
            "/api/v1/adaptations/text",
            headers=headers,
            json={"text": TECHNICAL, "child_id": child_id},
        )
    ).json()
    assert data["quality_status"] == "best_effort"
    endpoint = "/api/v1/readings" if adult else f"/api/v1/children/{child_id}/readings"
    response = await client.post(
        endpoint, headers=headers, json={"document_id": data["document"]["id"]}
    )
    assert response.status_code == 201, response.text
    reading = response.json()
    assert reading["score_delta"] == 0
    assert reading["meets_readability_target"] is False
    assert await db.scalar(select(func.count()).select_from(models.AdaptationChunk)) == 1
    update = await client.patch(
        f"/api/v1/readings/{reading['id']}",
        headers=headers,
        json={"completion_percent": 100, "completed": True, "reading_time_seconds": 0},
    )
    assert update.status_code == 200, update.text


async def test_processing_timeout_returns_original_without_leaking_error(
    client, make_user, monkeypatch
):
    from app.adaptations import pipeline

    async def stalled(*args):
        await asyncio.sleep(1)

    monkeypatch.setattr(pipeline, "run", stalled)
    monkeypatch.setattr(settings, "PROCESSING_TIMEOUT_SECONDS", 0.01)
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/text", headers=headers, json={"text": TECHNICAL}
    )
    assert response.status_code == 200
    assert response.json()["adapted_text"] == TECHNICAL
    assert "processing_budget_exceeded" in response.json()["warnings"]


async def test_model_preparation_timeout_keeps_precomputed_best_candidate(monkeypatch):
    class Slow(Offline):
        async def prepare(self):
            await asyncio.sleep(1)

    monkeypatch.setattr(settings, "PROCESSING_TIMEOUT_SECONDS", 0.02)
    result = await AdaptationPipeline(Slow()).run(TECHNICAL)
    assert result.adapted_text == TECHNICAL
    assert not result.meets_readability_target


@pytest.mark.parametrize(
    "text,status",
    [("   ", 422), ("...!?", 422), ("palabra " * 20001, 413)],
    ids=["blank", "punctuation-only", "word-limit"],
)
async def test_invalid_and_oversized_inputs_remain_rejected(client, make_user, text, status):
    _, headers, _ = await make_user()
    response = await client.post("/api/v1/adaptations/text", headers=headers, json={"text": text})
    assert response.status_code == status


async def test_chunk_boundaries_cannot_fabricate_sentence_score_improvement():
    source = "neuropsicología " * 500 + "y " + "neuropsicología " * 500
    result = await AdaptationPipeline(Offline()).run(source)
    assert result.adapted_text == source
    assert result.metrics["score_delta"] == 0
    assert not result.meets_readability_target
    assert len(result.chunks) == 2


async def test_maximum_word_count_is_valid_and_kept_without_truncation():
    source = "sol " * settings.MAX_DOCUMENT_WORDS
    result = await AdaptationPipeline(Offline()).run(source)
    assert result.adapted_text == source
    assert result.metrics["adapted_word_count"] == settings.MAX_DOCUMENT_WORDS
    assert result.metrics["score_delta"] == 0
