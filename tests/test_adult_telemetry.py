import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import models
from tests.conftest import SOURCE


async def test_independent_adult_reading_full_flow_and_snapshot(client, db, make_user):
    adult, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    _, stranger, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    _, tutor, _ = await make_user()
    adapted = await client.post("/api/v1/adaptations/text", headers=headers, json={"text": SOURCE})
    assert adapted.status_code == 200
    document = adapted.json()["document"]
    response = await client.post(
        "/api/v1/readings", headers=headers, json={"document_id": document["id"]}
    )
    assert response.status_code == 201, response.text
    reading = response.json()
    reading_id = reading["id"]
    assert reading["reader_user_id"] == str(adult.id) and reading["child_id"] is None
    assert reading["original_szigriszt_score"] == document["original_szigriszt_score"]
    assert reading["adapted_szigriszt_score"] == document["adapted_szigriszt_score"]
    assert reading["score_delta"] >= 15 and reading["adapted_szigriszt_score"] >= 65
    assert await db.scalar(select(func.count()).select_from(models.ChildProfile)) == 0
    assert (await client.get("/api/v1/readings", headers=headers)).json()[0]["id"] == reading_id
    assert (await client.get("/api/v1/readings", headers=stranger)).json() == []
    for other in (stranger, tutor):
        assert (
            await client.get(f"/api/v1/readings/{reading_id}", headers=other)
        ).status_code == 404
        assert (
            await client.patch(
                f"/api/v1/readings/{reading_id}", headers=other, json={"completion_percent": 10}
            )
        ).status_code == 404
    finished = await client.patch(
        f"/api/v1/readings/{reading_id}",
        headers=headers,
        json={"reading_time_seconds": 0, "completion_percent": 100, "completed": True},
    )
    assert finished.status_code == 200 and finished.json()["ended_at"]
    assert (await client.get("/api/v1/users/me/progress", headers=headers)).json() == [
        {"sessionLabel": "Sesión 1", "accumulatedMinutes": 0.0, "completionPercent": 100}
    ]
    assert (
        await client.delete(f"/api/v1/documents/{document['id']}", headers=headers)
    ).status_code == 204
    history = (await client.get(f"/api/v1/readings/{reading_id}", headers=headers)).json()
    assert history["document_id"] is None
    assert history["score_delta"] == reading["score_delta"]
    assert history["original_word_count"] == reading["original_word_count"]


async def test_independent_reading_cannot_claim_other_owner_or_child(
    client, make_user, child_payload
):
    _, adult, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    _, tutor, _ = await make_user()
    doc = (
        await client.post("/api/v1/adaptations/text", headers=tutor, json={"text": SOURCE})
    ).json()["document"]
    assert (
        await client.post("/api/v1/readings", headers=adult, json={"document_id": doc["id"]})
    ).status_code == 404
    assert (
        await client.post("/api/v1/readings", headers=tutor, json={"document_id": doc["id"]})
    ).status_code == 403
    child = (await client.post("/api/v1/children", headers=tutor, json=child_payload)).json()
    assert (
        await client.post(
            f"/api/v1/children/{child['id']}/readings",
            headers=adult,
            json={"document_id": doc["id"]},
        )
    ).status_code == 403
    own_doc = (
        await client.post("/api/v1/adaptations/text", headers=adult, json={"text": SOURCE})
    ).json()["document"]
    for injection in (
        {"child_id": child["id"]},
        {"reader_user_id": str(uuid.uuid4())},
        {"score_delta": 99},
    ):
        assert (
            await client.post(
                "/api/v1/readings", headers=adult, json={"document_id": own_doc["id"], **injection}
            )
        ).status_code == 422


async def test_child_session_contract_and_snapshot_still_work(client, db, make_user, child_payload):
    _, headers, _ = await make_user()
    child = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()
    doc = (
        await client.post(
            "/api/v1/adaptations/text",
            headers=headers,
            json={"text": SOURCE, "child_id": child["id"]},
        )
    ).json()["document"]
    response = await client.post(
        f"/api/v1/children/{child['id']}/readings", headers=headers, json={"document_id": doc["id"]}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["child_id"] == child["id"] and data["reader_user_id"] is None
    assert data["score_delta"] == doc["score_delta"]
    # Simulate subsequent adaptation metadata refresh without changing session history.
    document = await db.get(models.Document, uuid.UUID(doc["id"]))
    document.adaptation_method = "hybrid"
    document.adapted_szigriszt_score += 1.0
    document.score_delta = document.adapted_szigriszt_score - document.original_szigriszt_score
    await db.commit()
    assert (await client.get(f"/api/v1/readings/{data['id']}", headers=headers)).json()[
        "score_delta"
    ] == data["score_delta"]


@pytest.mark.parametrize("both_owners", [True, False])
async def test_database_requires_exactly_one_reading_owner(
    db, make_user, child_payload, client, both_owners
):
    adult, _, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    _, tutor, _ = await make_user()
    child = (await client.post("/api/v1/children", headers=tutor, json=child_payload)).json()
    row = models.ReadingSession(
        child_id=uuid.UUID(child["id"]) if both_owners else None,
        reader_user_id=adult.id if both_owners else None,
    )
    db.add(row)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
