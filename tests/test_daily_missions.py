"""Daily evidence, content deduplication, historical bonuses and scoped aliases."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app import daily_missions, models
from tests.conftest import SOURCE

OTHER_SOURCE = "El Sol es una estrella. La Tierra es un planeta. La Luna es un satélite natural. El agua forma parte de los océanos."
DAY_ONE = datetime(2026, 10, 20, 12, tzinfo=UTC)


async def reader_context(client, make_user, child_payload, adult):
    user, headers, _ = await make_user(
        models.UserRole.ADULTO_INDEPENDIENTE if adult else models.UserRole.TUTOR
    )
    child_id = None
    if not adult:
        child_id = (
            await client.post("/api/v1/children", headers=headers, json=child_payload)
        ).json()["id"]
    endpoint = "/api/v1/readings" if adult else f"/api/v1/children/{child_id}/readings"
    progress = (
        "/api/v1/readings/progress"
        if adult
        else f"/api/v1/profiles/{child_id}/educational-progress"
    )
    return headers, child_id, endpoint, progress


async def document(client, headers, child_id, text):
    response = await client.post(
        "/api/v1/adaptations/text", headers=headers, json={"text": text, "child_id": child_id}
    )
    assert response.status_code == 200
    return response.json()["document"]["id"]


async def start(client, db, headers, endpoint, document_id, now):
    response = await client.post(endpoint, headers=headers, json={"document_id": document_id})
    assert response.status_code == 201, response.text
    reading_id = response.json()["id"]
    reading = await db.get(models.ReadingSession, uuid.UUID(reading_id))
    reading.started_at = now - timedelta(minutes=1)
    await db.commit()
    return reading_id


def missions(data):
    return {item["id"]: item for item in data["daily_missions"]}


@pytest.mark.parametrize("adult", [True, False])
async def test_daily_missions_progress_rewards_and_distinct_readings(
    client, db, make_user, child_payload, monkeypatch, adult
):
    headers, child_id, endpoint, url = await reader_context(client, make_user, child_payload, adult)
    monkeypatch.setattr(daily_missions, "current_day", lambda: DAY_ONE.date())
    first_doc = await document(client, headers, child_id, SOURCE)
    second_doc = await document(client, headers, child_id, OTHER_SOURCE)
    first = await start(client, db, headers, endpoint, first_doc, DAY_ONE)
    second = await start(client, db, headers, endpoint, second_doc, DAY_ONE)
    before = (await client.get(url, headers=headers)).json()
    assert before["total_gems"] == 30
    assert all(item["progress"] == 0 for item in before["daily_missions"])
    response = await client.patch(
        f"{endpoint}/{first}",
        headers=headers,
        json={
            "completed": True,
            "completion_percent": 100,
            "questions_answered": 2,
            "questions_correct": 2,
        },
    )
    assert response.status_code == 200, response.text
    one = (await client.get(url, headers=headers)).json()
    assert one["total_gems"] == 185  # 30 + 50 + 2*25 + daily(25+30).
    assert one["total_xp"] == 200
    items = missions(one)
    assert items["mission_read_lesson"]["completed"]
    assert items["mission_quiz_master"]["completed"]
    assert items["mission_category_variety"]["progress"] == 1
    assert not items["mission_category_variety"]["completed"]
    assert (
        await client.patch(f"{endpoint}/{second}", headers=headers, json={"completion_percent": 10})
    ).status_code == 200
    two = (await client.get(url, headers=headers)).json()
    assert two["total_gems"] == two["total_stars"] == 225
    assert [item["reward_gems"] for item in two["daily_missions"]] == [25, 30, 40]
    assert [item["target"] for item in two["daily_missions"]] == [1, 1, 2]
    assert all(item["completed"] for item in two["daily_missions"])
    count = await db.scalar(select(func.count()).select_from(models.ReadingActivityDay))
    assert (await client.get(url, headers=headers)).json() == two
    assert (
        await db.scalar(select(func.count()).select_from(models.ReadingActivityDay)) == count == 2
    )
    assert (
        await client.patch(
            f"{endpoint}/{second}",
            headers=headers,
            json={"completion_percent": 100, "completed": True},
        )
    ).status_code == 200
    assert (await client.get(url, headers=headers)).json()["total_gems"] == 275
    if child_id:
        assert (
            await client.get(f"/api/v1/children/{child_id}/progress", headers=headers)
        ).json() == (await client.get(url, headers=headers)).json()


async def test_previous_day_bonuses_survive_reset_without_duplicate_awards(
    client, db, make_user, child_payload, monkeypatch
):
    headers, child_id, endpoint, url = await reader_context(client, make_user, child_payload, False)
    clock = [DAY_ONE]
    monkeypatch.setattr(daily_missions, "current_day", lambda: clock[0].date())
    doc = await document(client, headers, child_id, SOURCE)
    first = await start(client, db, headers, endpoint, doc, clock[0])
    assert (
        await client.patch(
            f"{endpoint}/{first}",
            headers=headers,
            json={
                "completed": True,
                "completion_percent": 100,
                "questions_answered": 2,
                "questions_correct": 2,
            },
        )
    ).status_code == 200
    assert (await client.get(url, headers=headers)).json()["total_gems"] == 185
    clock[0] += timedelta(days=1)
    next_day = (await client.get(url, headers=headers)).json()
    assert next_day["total_gems"] == 185
    assert all(
        item["progress"] == 0 and not item["completed"] for item in next_day["daily_missions"]
    )
    second = await start(client, db, headers, endpoint, doc, clock[0])
    assert (
        await client.patch(
            f"{endpoint}/{second}",
            headers=headers,
            json={
                "completed": True,
                "completion_percent": 100,
                "questions_answered": 2,
                "questions_correct": 2,
            },
        )
    ).status_code == 200
    result = (await client.get(url, headers=headers)).json()
    assert result["total_gems"] == 340  # Base 230 + two days of 55 gems.
    assert result["total_xp"] == 400
    assert missions(result)["mission_category_variety"]["progress"] == 1
    assert (await client.get(url, headers=headers)).json() == result


async def test_late_quiz_counts_today_without_completing_yesterdays_read_again(
    client, db, make_user, child_payload, monkeypatch
):
    headers, child_id, endpoint, url = await reader_context(client, make_user, child_payload, True)
    clock = [DAY_ONE]
    monkeypatch.setattr(daily_missions, "current_day", lambda: clock[0].date())
    doc = await document(client, headers, child_id, SOURCE)
    reading = await start(client, db, headers, endpoint, doc, clock[0])
    assert (
        await client.patch(
            f"{endpoint}/{reading}",
            headers=headers,
            json={"completed": True, "completion_percent": 100},
        )
    ).status_code == 200
    assert (await client.get(url, headers=headers)).json()["total_gems"] == 105
    clock[0] += timedelta(days=1)
    payload = {"questions_answered": 2, "questions_correct": 1}
    assert (
        await client.patch(f"{endpoint}/{reading}", headers=headers, json=payload)
    ).status_code == 200
    data = (await client.get(url, headers=headers)).json()
    assert data["total_gems"] == 160
    assert not missions(data)["mission_read_lesson"]["completed"]
    assert missions(data)["mission_quiz_master"]["completed"]
    assert data["completed_lessons"] == 1 and data["streak_days"] == 1
    clock[0] += timedelta(days=1)
    # Repeating exactly the same telemetry is not a new correct answer.
    assert (
        await client.patch(f"{endpoint}/{reading}", headers=headers, json=payload)
    ).status_code == 200
    repeated = (await client.get(url, headers=headers)).json()
    assert repeated["total_gems"] == 160
    assert all(not item["completed"] for item in repeated["daily_missions"])


async def test_reopening_and_reuploading_the_same_text_does_not_unlock_variety(
    client, db, make_user, child_payload, monkeypatch
):
    headers, child_id, endpoint, url = await reader_context(client, make_user, child_payload, False)
    monkeypatch.setattr(daily_missions, "current_day", lambda: DAY_ONE.date())
    doc = await document(client, headers, child_id, SOURCE)
    for _ in range(2):
        reading = await start(client, db, headers, endpoint, doc, DAY_ONE)
        assert (
            await client.patch(
                f"{endpoint}/{reading}", headers=headers, json={"completion_percent": 10}
            )
        ).status_code == 200
    before = (await client.get(url, headers=headers)).json()
    assert missions(before)["mission_category_variety"]["progress"] == 1
    assert (await client.delete(f"/api/v1/documents/{doc}", headers=headers)).status_code == 204
    replacement = await document(client, headers, child_id, SOURCE)
    assert replacement != doc
    reading = await start(client, db, headers, endpoint, replacement, DAY_ONE)
    assert (
        await client.patch(
            f"{endpoint}/{reading}", headers=headers, json={"completion_percent": 10}
        )
    ).status_code == 200
    after = (await client.get(url, headers=headers)).json()
    assert missions(after)["mission_category_variety"]["progress"] == 1
    events = (await db.scalars(select(models.ReadingActivityDay))).all()
    assert len({event.lesson_key for event in events}) == 1


async def test_profiles_progress_alias_preserves_tutor_ownership(
    client, db, make_user, child_payload
):
    _, headers, _ = await make_user()
    _, stranger, _ = await make_user()
    _, adult, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    first = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    second = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    url = f"/api/v1/profiles/{first}/educational-progress"
    assert (await client.get(url, headers=stranger)).status_code == 404
    assert (await client.get(url, headers=adult)).status_code == 403
    assert (await client.get(url)).status_code == 401
    doc = await document(client, headers, first, SOURCE)
    reading = (
        await client.post(
            f"/api/v1/children/{first}/readings", headers=headers, json={"document_id": doc}
        )
    ).json()["id"]
    assert (
        await client.patch(
            f"/api/v1/readings/{reading}",
            headers=headers,
            json={"completed": True, "completion_percent": 100},
        )
    ).status_code == 200
    own = (await client.get(url, headers=headers)).json()
    other = (
        await client.get(f"/api/v1/profiles/{second}/educational-progress", headers=headers)
    ).json()
    assert missions(own)["mission_read_lesson"]["completed"]
    assert other["total_gems"] == 30 and all(
        not mission["completed"] for mission in other["daily_missions"]
    )
    assert (
        "/api/v1/profiles/{profile_id}/educational-progress"
        in (await client.get("/openapi.json")).json()["paths"]
    )
