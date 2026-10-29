"""Retained original/adapted pairs, Android field names and repeatable demo history."""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app import auth, models
from app.academic_demo import DEMO_KEYS
from app.encyclopedia import ARTICLES
from app.lesson_sources import lesson_excerpt
from app.nlp.readability import measure
from tests.conftest import SOURCE


def assert_comparison(data):
    original, adapted = measure(data["original_text"]), measure(data["adapted_text"])
    assert data["original_readability_score"] == pytest.approx(original.score)
    assert data["readability_score"] == pytest.approx(adapted.score)
    metrics = data["metrics"]
    assert metrics["original_szigriszt_pazos"] == pytest.approx(original.score)
    assert metrics["adapted_szigriszt_pazos"] == pytest.approx(adapted.score)
    assert metrics["score_delta"] == pytest.approx(adapted.score - original.score)
    assert metrics["original_word_count"] == original.word_count
    assert metrics["adapted_word_count"] == adapted.word_count
    assert metrics["original_average_words_per_sentence"] == pytest.approx(
        original.word_count / original.sentence_count
    )
    assert metrics["adapted_average_words_per_sentence"] == pytest.approx(
        adapted.word_count / adapted.sentence_count
    )
    assert data["document"]["score_delta"] == pytest.approx(metrics["score_delta"])
    assert data["fun_fact"] and 3 <= len(data["key_vocabulary"]) <= 4
    assert len(data["comprehension_questions"]) == 2
    for term in data["key_vocabulary"]:
        assert term["word"] in data["adapted_text"] and term["definition"] and term["example"]


@pytest.mark.parametrize(
    "topic,category,key",
    [
        ("Real Madrid", "deportes", "real madrid"),
        ("marina", "animales_naturaleza", "biologia marina"),
    ],
)
@pytest.mark.parametrize("level", [1, 3, 5])
@pytest.mark.parametrize("group", ["6-8", "9-11", "12+"])
async def test_generated_comparison_is_real_nonempty_and_retrievable(
    client,
    make_user,
    topic,
    category,
    key,
    level,
    group,
):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate",
        headers=headers,
        json={
            "category": category,
            "custom_topic": topic,
            "target_level": level,
            "age_group": group,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["original_text"] == lesson_excerpt(ARTICLES[key].text, group)
    assert data["original_text"] != data["adapted_text"]
    assert data["readability_score"] > data["original_readability_score"]
    assert data["target_level"] == level and data["age_group"] == group
    assert data["question_age_group"] == group
    assert_comparison(data)
    assert (await client.get(f"/api/v1/adaptations/{data['id']}", headers=headers)).json() == data


async def test_manual_alias_retains_content_and_versions_without_touching_legacy_contract(
    client,
    db,
    make_user,
):
    _, headers, _ = await make_user()
    _, stranger, _ = await make_user()
    versions = []
    for level in (1, 3, 5):
        response = await client.post(
            "/api/v1/adaptations", headers=headers, json={"text": SOURCE, "target_level": level}
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["original_text"] == SOURCE
        assert_comparison(data)
        versions.append(data)
    assert len({item["id"] for item in versions}) == 3
    assert len({item["document"]["id"] for item in versions}) == 1
    assert await db.scalar(select(func.count()).select_from(models.AdaptationContent)) == 3
    # All retrieval is DB-backed; no request-local object or process cache is needed.
    db.expunge_all()
    for data in versions:
        path = f"/api/v1/adaptations/{data['id']}"
        assert (await client.get(path, headers=headers)).json() == data
        assert (await client.get(path, headers=stranger)).status_code == 404
        assert (await client.get(path)).status_code == 401
    assert (
        await client.get("/api/v1/adaptations/" + str(uuid.uuid4()), headers=headers)
    ).status_code == 404
    docid = versions[0]["document"]["id"]
    assert (await client.get("/api/v1/adaptations/" + docid, headers=headers)).status_code == 200
    refreshed = await client.post(
        "/api/v1/adaptations", headers=headers, json={"text": SOURCE, "target_level": 1}
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["id"] == versions[0]["id"]
    assert (await client.get("/api/v1/adaptations/" + docid, headers=headers)).json()[
        "target_level"
    ] == 1
    assert (await client.delete("/api/v1/documents/" + docid, headers=headers)).status_code == 204
    assert await db.scalar(select(func.count()).select_from(models.AdaptationContent)) == 0
    assert (
        await client.get("/api/v1/adaptations/" + versions[0]["id"], headers=headers)
    ).status_code == 404


async def test_seed_demo_has_six_lessons_seven_days_real_metrics_and_no_duplicate_rewards(
    client,
    db,
    make_user,
    child_payload,
):
    _, headers, _ = await make_user()
    profile = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    endpoint = f"/api/v1/profiles/{profile}/seed-demo"
    first = await client.post(endpoint, headers=headers)
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["demo_data"] and data["current_streak_days"] >= 5
    assert data["total_lessons"] == data["completed_lessons"] == 7
    assert data["total_gems"] >= 260 and data["mascot"]["stage"] == 4
    assert data["total_xp"] >= 700
    lessons = data["demo_lessons"]
    assert len(lessons) == 6
    assert {item["title"] for item in lessons} == {ARTICLES[key].title for key in DEMO_KEYS}
    for item in lessons:
        assert item["original_text"] != item["adapted_text"]
        assert item["readability_score"] > item["original_readability_score"]
        assert_comparison(item)
        assert (
            await client.get("/api/v1/adaptations/" + item["id"], headers=headers)
        ).json() == item
    history = data["level_progression"]
    assert all(item["is_demo"] for item in history)
    assert {item["simplification_level"] for item in history} == {1, 2, 3, 4}
    assert [item["comprehension_score"] for item in history] == [65, 75, 80, 85, 90, 100, 100]
    assert {datetime.fromisoformat(item["recorded_at"]).date() for item in history} == {
        auth.utcnow().date() - timedelta(days=i) for i in range(7)
    }
    assert all(
        item["adapted_readability_score"] > item["original_readability_score"] for item in history
    )
    counts = []
    for model in (
        models.Document,
        models.ReadingSession,
        models.ReadingActivityDay,
        models.AdaptationContent,
        models.ChildLibraryItem,
    ):
        counts.append(await db.scalar(select(func.count()).select_from(model)))
    second = await client.post(endpoint, headers=headers)
    assert second.status_code == 200, second.text
    repeated = second.json()
    assert repeated["total_gems"] == data["total_gems"]
    assert repeated["total_xp"] == data["total_xp"]
    assert repeated["level_progression"] == history
    after = []
    for model in (
        models.Document,
        models.ReadingSession,
        models.ReadingActivityDay,
        models.AdaptationContent,
        models.ChildLibraryItem,
    ):
        after.append(await db.scalar(select(func.count()).select_from(model)))
    assert counts == after == [6, 7, 7, 6, 6]
    progress = (
        await client.get(f"/api/v1/profiles/{profile}/educational-progress", headers=headers)
    ).json()
    assert progress["total_gems"] == data["total_gems"] and progress["current_streak_days"] == 7
    assert progress["demo_data"]


async def test_demo_and_claim_require_owner_and_claim_never_double_credits(
    client,
    db,
    make_user,
    child_payload,
):
    _, headers, _ = await make_user()
    _, stranger, _ = await make_user()
    _, adult, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    profile = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    base = f"/api/v1/profiles/{profile}"
    for route in ("/seed-demo", "/daily-missions/mission_read_lesson/claim"):
        assert (await client.post(base + route)).status_code == 401
        assert (await client.post(base + route, headers=stranger)).status_code == 404
        assert (await client.post(base + route, headers=adult)).status_code == 403
    assert (
        await client.post(base + "/daily-missions/unknown/claim", headers=headers)
    ).status_code == 404
    assert (
        await client.post(base + "/daily-missions/mission_read_lesson/claim", headers=headers)
    ).status_code == 409
    data = (await client.post(base + "/seed-demo", headers=headers)).json()
    for mission in data["daily_missions"]:
        assert {
            "id",
            "title",
            "description",
            "reward_gems",
            "progress",
            "target",
            "completed",
            "claimed",
        } == set(mission)
        assert mission["claimed"] == mission["completed"]
        if mission["completed"]:
            for _ in range(2):
                response = await client.post(
                    base + f"/daily-missions/{mission['id']}/claim", headers=headers
                )
                assert response.status_code == 200, response.text
                assert response.json()["total_gems"] == data["total_gems"]
    assert await db.scalar(select(func.count()).select_from(models.ReadingSession)) == 7


async def test_seeding_preserves_real_readings_and_profile_preferences(
    client, db, make_user, child_payload
):
    _, headers, _ = await make_user()
    profile = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    doc = (
        await client.post(
            "/api/v1/adaptations/text", headers=headers, json={"text": SOURCE, "child_id": profile}
        )
    ).json()["document"]["id"]
    normal = (
        await client.post(
            f"/api/v1/children/{profile}/readings", headers=headers, json={"document_id": doc}
        )
    ).json()
    response = await client.post(f"/api/v1/profiles/{profile}/seed-demo", headers=headers)
    assert response.status_code == 200, response.text
    history = response.json()["level_progression"]
    assert len(history) == 8 and sum(item["is_demo"] for item in history) == 7
    after = (await client.get("/api/v1/readings/" + normal["id"], headers=headers)).json()
    assert after == normal and not after["is_demo"]
    child = await db.get(models.ChildProfile, uuid.UUID(profile))
    assert child.nivel_simplificacion_nlp == 1


@pytest.mark.postgres
async def test_parallel_demo_requests_seed_one_cohort(client, db, make_user, child_payload):
    import asyncio
    import os

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.database import get_db
    from app.main import app

    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("Concurrent row-lock verification requires PostgreSQL")
    _, headers, _ = await make_user()
    profile = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    original = app.dependency_overrides[get_db]
    sessions = async_sessionmaker(db.bind, expire_on_commit=False, autoflush=False)

    async def independent_session():
        async with sessions() as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = independent_session
    try:
        responses = await asyncio.gather(
            *(
                client.post(f"/api/v1/profiles/{profile}/seed-demo", headers=headers)
                for _ in range(2)
            )
        )
        assert all(response.status_code == 200 for response in responses), [
            r.text for r in responses
        ]
        assert responses[0].json()["total_gems"] == responses[1].json()["total_gems"]
        assert await db.scalar(select(func.count()).select_from(models.ReadingSession)) == 7
        assert await db.scalar(select(func.count()).select_from(models.Document)) == 6
        assert await db.scalar(select(func.count()).select_from(models.AdaptationContent)) == 6
    finally:
        app.dependency_overrides[get_db] = original


async def test_retained_child_lesson_still_requires_active_profile_and_library(
    client, make_user, child_payload
):
    _, headers, _ = await make_user()
    profile = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    data = (
        await client.post(
            "/api/v1/adaptations/generate",
            headers=headers,
            json={
                "category": "deportes",
                "custom_topic": "Real Madrid",
                "child_id": profile,
                "age_group": "12+",
            },
        )
    ).json()
    # Explicit teaching group affects this lesson; the real birthday stays intact.
    assert data["age_group"] == "12+" and data["child_age_years"] == 8
    account = await client.post(
        f"/api/v1/children/{profile}/account",
        headers=headers,
        json={"email": f"{uuid.uuid4().hex}@example.com", "password": "ValidPass123!"},
    )
    assert account.status_code == 201, account.text
    token = (
        await client.post(f"/api/v1/children/{profile}/session", headers=headers, json={})
    ).json()["access_token"]
    child_headers = {"Authorization": "Bearer " + token}
    path = "/api/v1/adaptations/" + data["id"]
    assert (await client.get(path, headers=child_headers)).status_code == 200
    assert (
        await client.delete(
            f"/api/v1/children/{profile}/library/{data['document']['id']}", headers=headers
        )
    ).status_code == 204
    assert (await client.get(path, headers=child_headers)).status_code == 404
    assert (await client.get(path, headers=headers)).status_code == 200
    assert (await client.delete("/api/v1/children/" + profile, headers=headers)).status_code == 204
    assert (await client.get(path, headers=headers)).status_code == 404
    assert (
        await client.post(f"/api/v1/profiles/{profile}/seed-demo", headers=headers)
    ).status_code == 404
