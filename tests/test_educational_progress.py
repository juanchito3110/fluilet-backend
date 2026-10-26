"""Practice telemetry and educational summaries against the real database fixture."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import auth, models
from app.educational_progress import BADGES
from tests.conftest import SOURCE


async def owned_document(client, headers, child_id=None):
    response = await client.post(
        "/api/v1/adaptations/text", headers=headers, json={"text": SOURCE, "child_id": child_id}
    )
    assert response.status_code == 200
    return response.json()["document"]["id"]


@pytest.mark.parametrize("adult", [True, False])
async def test_complete_educational_flow_and_exact_progress_contract(
    client, db, make_user, child_payload, adult
):
    role = models.UserRole.ADULTO_INDEPENDIENTE if adult else models.UserRole.TUTOR
    _, headers, _ = await make_user(role)
    child_id = None
    if not adult:
        child_id = (
            await client.post("/api/v1/children", headers=headers, json=child_payload)
        ).json()["id"]
    document_id = await owned_document(client, headers, child_id)
    endpoint = "/api/v1/readings" if adult else f"/api/v1/children/{child_id}/readings"
    progress_url = "/api/v1/readings/progress" if adult else f"/api/v1/children/{child_id}/progress"
    reading_ids = []
    for index in range(4):
        created = await client.post(
            endpoint,
            headers=headers,
            json={
                "document_id": document_id,
                "category": "deportes" if index % 2 else "ciencia_espacio",
                "simplification_level": min(index + 2, 5),
                "tts_speed_used": 1.25,
            },
        )
        assert created.status_code == 201, created.text
        data = created.json()
        reading_ids.append(data["id"])
        stored = await db.get(models.ReadingSession, uuid.UUID(data["id"]))
        stored.started_at = auth.utcnow() - timedelta(minutes=10 - index)
        await db.commit()
        patch = {
            "completion_percent": 100 if index < 3 else 25,
            "reading_time_seconds": (index + 1) * 10 if index < 3 else 5,
        }
        if index < 3:
            patch.update(
                {"completed": True, "questions_answered": 2, "questions_correct": 2 - index}
            )
        updated = await client.patch(f"{endpoint}/{data['id']}", headers=headers, json=patch)
        assert updated.status_code == 200, updated.text
        assert updated.json()["tts_speed_used"] == 1.25
    response = await client.get(progress_url, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data) == {
        "total_lessons",
        "completed_lessons",
        "incomplete_lessons",
        "completion_rate_percent",
        "total_reading_seconds",
        "average_comprehension_score",
        "current_recommended_level",
        "level_progression",
        "badges",
        "streak_days",
        "total_gems",
        "total_xp",
        "total_stars",
        "current_rank_title",
        "next_rank_stars",
        "mascot",
        "collectible_cards",
        "shop_catalog",
        "pedagogical_summary",
        "daily_missions",
        "current_streak_days",
        "demo_data",
        "demo_lessons",
    }
    assert data["total_lessons"] == 4
    assert data["completed_lessons"] == 3 and data["incomplete_lessons"] == 1
    assert data["completion_rate_percent"] == 75.0
    assert data["total_reading_seconds"] == 65
    assert data["average_comprehension_score"] == 50.0
    # Product policy: either comprehension >=50 or full completion qualifies.
    assert data["current_recommended_level"] == 5
    assert [item["reading_id"] for item in data["level_progression"]] == reading_ids
    assert [item["lesson_number"] for item in data["level_progression"]] == [1, 2, 3, 4]
    for item in data["level_progression"]:
        assert set(item) == {
            "lesson_number",
            "document_id",
            "is_demo",
            "reading_id",
            "recorded_at",
            "category",
            "simplification_level",
            "completed",
            "completion_percentage",
            "comprehension_score",
            "duration_seconds",
            "original_readability_score",
            "adapted_readability_score",
        }
        assert item["original_readability_score"] is not None
        assert item["adapted_readability_score"] is not None
        assert item["recorded_at"].endswith("+00:00")
    assert data["badges"] == [
        {"code": code, "title": title, "description": description, "unlocked": True}
        for code, title, description in BADGES
    ]
    history = (await client.get(endpoint, headers=headers)).json()
    assert len(history) == 4 and all(
        row["category"] in {"deportes", "ciencia_espacio"} for row in history
    )
    if not adult:
        legacy = (
            await client.get(f"/api/v1/children/{child_id}/progress/legacy", headers=headers)
        ).json()
        assert isinstance(legacy, list) and legacy[-1]["completionPercent"] == 25


async def test_quiz_after_completed_reading_and_metadata_inheritance(client, make_user):
    _, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    generated = (
        await client.post(
            "/api/v1/adaptations/generate",
            headers=headers,
            json={"category": "tecnologia", "simplification_level": 5},
        )
    ).json()
    reading = (
        await client.post(
            "/api/v1/readings", headers=headers, json={"document_id": generated["document"]["id"]}
        )
    ).json()
    assert reading["category"] == "tecnologia" and reading["simplification_level"] == 5
    reading_url = f"/api/v1/readings/{reading['id']}"
    assert (
        await client.patch(
            reading_url, headers=headers, json={"completed": True, "completion_percent": 100}
        )
    ).status_code == 200
    response = await client.patch(
        reading_url,
        headers=headers,
        json={"questions_answered": 2, "questions_correct": 2, "tts_speed_used": 0.9},
    )
    assert response.status_code == 200 and response.json()["comprehension_score"] == 100
    assert (
        await client.patch(reading_url, headers=headers, json={"completion_percent": 20})
    ).status_code == 409
    assert (await client.get("/api/v1/readings/progress", headers=headers)).json()[
        "current_recommended_level"
    ] == 5
    # Deleting content metadata must not delete the educational snapshot.
    assert (
        await client.delete(f"/api/v1/documents/{generated['document']['id']}", headers=headers)
    ).status_code == 204
    progress = (await client.get("/api/v1/readings/progress", headers=headers)).json()
    assert progress["total_lessons"] == 1
    assert progress["level_progression"][0]["category"] == "tecnologia"


@pytest.mark.parametrize(
    "payload",
    [
        {"comprehension_score": -1},
        {"comprehension_score": 101},
        {"comprehension_score": True},
        {"questions_answered": -1},
        {"questions_answered": 1, "questions_correct": 2},
        {"questions_answered": 2, "questions_correct": 1, "comprehension_score": 100},
        {"simplification_level": 0},
        {"simplification_level": 6},
        {"tts_speed_used": 0},
        {"tts_speed_used": -1},
        {"questions_correct": None},
    ],
    ids=[
        "negative-score",
        "over-score",
        "bool-score",
        "negative-count",
        "too-many-correct",
        "inconsistent-score",
        "low-level",
        "high-level",
        "zero-speed",
        "negative-speed",
        "null-count",
    ],
)
async def test_practice_validation_on_both_create_and_update(client, db, make_user, payload):
    _, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    doc = await owned_document(client, headers)
    response = await client.post(
        "/api/v1/readings", headers=headers, json={"document_id": doc, **payload}
    )
    assert response.status_code == 422
    assert await db.scalar(select(func.count()).select_from(models.ReadingSession)) == 0
    created = (
        await client.post("/api/v1/readings", headers=headers, json={"document_id": doc})
    ).json()
    response = await client.patch(
        f"/api/v1/readings/{created['id']}", headers=headers, json=payload
    )
    assert response.status_code == 422


async def test_partial_question_updates_validate_merged_counts_and_rounding(client, make_user):
    _, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    doc = await owned_document(client, headers)
    reading = (
        await client.post(
            "/api/v1/readings",
            headers=headers,
            json={"document_id": doc, "questions_answered": 3, "questions_correct": 2},
        )
    ).json()
    assert reading["comprehension_score"] == 67
    url = f"/api/v1/readings/{reading['id']}"
    assert (
        await client.patch(url, headers=headers, json={"questions_answered": 1})
    ).status_code == 422
    reset = await client.patch(
        url,
        headers=headers,
        json={"questions_answered": 0, "questions_correct": 0, "comprehension_score": None},
    )
    assert reset.status_code == 200 and reset.json()["comprehension_score"] is None


async def test_empty_progress_and_ownership(client, db, make_user, child_payload):
    _, adult, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    _, tutor, _ = await make_user()
    _, outsider, _ = await make_user()
    child = (await client.post("/api/v1/children", headers=tutor, json=child_payload)).json()
    url = f"/api/v1/children/{child['id']}/progress"
    another_adult, _, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    db.add(
        models.ReadingSession(
            reader_user_id=another_adult.id,
            completed=True,
            completion_percent=100,
            category="tecnologia",
            simplification_level=5,
            comprehension_score=100,
            questions_answered=2,
            questions_correct=2,
        )
    )
    await db.commit()
    result = (await client.get("/api/v1/readings/progress", headers=adult)).json()
    assert result["total_lessons"] == 0 and result["current_recommended_level"] == 2
    assert result["average_comprehension_score"] == 0
    assert result["level_progression"] == [] and all(
        not badge["unlocked"] for badge in result["badges"]
    )
    assert (await client.get(url, headers=tutor)).json()["current_recommended_level"] == child[
        "nivel_simplificacion_nlp"
    ]
    assert (await client.get(url, headers=outsider)).status_code == 404
    assert (await client.get(url, headers=adult)).status_code == 403
    legacy_url = url + "/legacy"
    assert (await client.get(legacy_url, headers=tutor)).json() == []
    assert (await client.get(legacy_url, headers=outsider)).status_code == 404
    assert (await client.get(legacy_url, headers=adult)).status_code == 403
    assert (await client.get(legacy_url)).status_code == 401
    assert (await client.get("/api/v1/readings/progress", headers=tutor)).status_code == 403
    assert (await client.get("/api/v1/readings/progress")).status_code == 401


async def test_summary_does_not_silently_truncate_at_history_pagination(client, db, make_user):
    adult, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    rows = [models.ReadingSession(reader_user_id=adult.id) for _ in range(501)]
    db.add_all(rows)
    await db.commit()
    response = await client.get("/api/v1/readings/progress", headers=headers)
    assert response.status_code == 200
    assert response.json()["total_lessons"] == len(response.json()["level_progression"]) == 501


@pytest.mark.parametrize(
    "changes",
    [
        {"simplification_level": 6},
        {"comprehension_score": 101},
        {"questions_answered": 1, "questions_correct": 2},
        {"tts_speed_used": 0},
    ],
    ids=["level", "score", "counters", "speed"],
)
async def test_database_enforces_practice_bounds(db, make_user, changes):
    adult, _, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    db.add(models.ReadingSession(reader_user_id=adult.id, **changes))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.parametrize(
    "score,completed,level,expected",
    [(None, True, 2, 3), (50, True, 3, 4), (0, True, 2, 3), (100, False, 2, 2), (100, True, 5, 5)],
    ids=[
        "completion-only",
        "good-comprehension",
        "completion-alternative",
        "unfinished",
        "level-cap",
    ],
)
async def test_level_recommendation_is_gradual_and_idempotent(
    client, make_user, score, completed, level, expected
):
    _, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    doc = await owned_document(client, headers)
    reading = (
        await client.post(
            "/api/v1/readings",
            headers=headers,
            json={"document_id": doc, "simplification_level": level, "comprehension_score": score},
        )
    ).json()
    if completed:
        response = await client.patch(
            f"/api/v1/readings/{reading['id']}",
            headers=headers,
            json={"completed": True, "completion_percent": 100},
        )
        assert response.status_code == 200
    first = (await client.get("/api/v1/readings/progress", headers=headers)).json()
    second = (await client.get("/api/v1/readings/progress", headers=headers)).json()
    assert first["current_recommended_level"] == second["current_recommended_level"] == expected


async def test_child_patch_alias_checks_both_profile_and_reading_owner(
    client, make_user, child_payload
):
    _, headers, _ = await make_user()
    _, stranger, _ = await make_user()
    first = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    second = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    doc = await owned_document(client, headers, first)
    response = await client.post(
        f"/api/v1/children/{first}/readings",
        headers=headers,
        json={
            "document_id": doc,
            "category": "deportes",
            "simplification_level": 4,
            "comprehension_score": 50,
            "questions_answered": 2,
            "questions_correct": 1,
            "tts_speed_used": 1.2,
        },
    )
    assert response.status_code == 201 and response.json()["comprehension_score"] == 50
    reading_id = response.json()["id"]
    other_profile = await client.get(
        f"/api/v1/children/{second}/progress",
        headers=headers,
    )
    assert other_profile.json()["total_lessons"] == 0
    assert (
        await client.patch(
            f"/api/v1/children/{second}/readings/{reading_id}",
            headers=headers,
            json={"tts_speed_used": 0.9},
        )
    ).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/children/{first}/readings/{reading_id}",
            headers=stranger,
            json={"tts_speed_used": 0.9},
        )
    ).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/children/{first}/readings/{reading_id}",
            headers=headers,
            json={"tts_speed_used": 0.9},
        )
    ).status_code == 200


async def test_child_progress_openapi_exposes_separate_object_and_legacy_list(client):
    paths = (await client.get("/openapi.json")).json()["paths"]
    current = paths["/api/v1/children/{child_id}/progress"]["get"]
    legacy = paths["/api/v1/children/{child_id}/progress/legacy"]["get"]
    assert current["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/EducationalProgress"
    }
    assert legacy["responses"]["200"]["content"]["application/json"]["schema"]["type"] == "array"
    assert all(parameter["name"] != "view" for parameter in current["parameters"])
