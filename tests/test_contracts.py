import uuid

import pytest
from pydantic import ValidationError

from app import models, schemas
from tests.conftest import PASSWORD, SOURCE


@pytest.mark.parametrize(
    "value,expected",
    [("BASICO", 1), ("INTERMEDIO", 3), ("AVANZADO", 5), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)],
)
def test_nlp_mapping(value, expected):
    assert (
        schemas.AdaptTextRequest(
            text="test", nivel_simplificacion_nlp=value
        ).nivel_simplificacion_nlp
        == expected
    )


@pytest.mark.parametrize("value", [True, 0, 6, "unknown", 1.2])
def test_bad_nlp_levels(value):
    with pytest.raises(ValidationError):
        schemas.AdaptTextRequest(text="test", nivel_simplificacion_nlp=value)


async def test_null_patch_and_invalid_password_never_500(client, make_user, child_payload):
    _, headers, _ = await make_user()
    child = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()
    response = await client.patch(
        f"/api/v1/children/{child['id']}", headers=headers, json={"name": None}
    )
    assert response.status_code == 422
    invalid = "Aa1!" + "á" * 35
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "audit@example.com",
            "full_name": "Test User",
            "role": "tutor",
            "password": invalid,
        },
    )
    assert response.status_code == 422 and invalid not in response.text


async def test_activity_assignment_reading_and_android_progress(client, make_user, child_payload):
    _, headers, _ = await make_user()
    _, stranger_headers, _ = await make_user()
    child = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()
    child_id = child["id"]
    email = f"{uuid.uuid4().hex}@example.com"
    account = await client.post(
        f"/api/v1/children/{child_id}/account",
        headers=headers,
        json={"email": email, "password": PASSWORD},
    )
    assert account.status_code == 201
    opened = await client.post(f"/api/v1/children/{child_id}/session", headers=headers, json={})
    assert opened.status_code == 200
    child_headers = {"Authorization": "Bearer " + opened.json()["access_token"]}
    adapted = await client.post(
        "/api/v1/adaptations/text", headers=headers, json={"text": SOURCE, "child_id": child_id}
    )
    assert adapted.status_code == 200, adapted.text
    doc_id = adapted.json()["document"]["id"]
    assert (
        await client.get(f"/api/v1/documents/{doc_id}", headers=stranger_headers)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/documents/{doc_id}", headers=child_headers)
    ).status_code == 200
    started = await client.post(
        f"/api/v1/children/{child_id}/readings", headers=child_headers, json={"document_id": doc_id}
    )
    assert started.status_code == 201, started.text
    reading_id = started.json()["id"]
    assert (
        await client.patch(
            f"/api/v1/readings/{reading_id}",
            headers=stranger_headers,
            json={"completion_percent": 10},
        )
    ).status_code == 404
    invalid_time = await client.patch(
        f"/api/v1/readings/{reading_id}", headers=child_headers, json={"reading_time_seconds": 9999}
    )
    assert invalid_time.status_code == 422
    finished = await client.patch(
        f"/api/v1/readings/{reading_id}",
        headers=child_headers,
        json={"reading_time_seconds": 0, "completion_percent": 100, "completed": True},
    )
    assert finished.status_code == 200 and finished.json()["ended_at"]
    progress = await client.get(f"/api/v1/children/{child_id}/progress", headers=headers)
    assert progress.status_code == 200
    assert progress.json() == [
        {"sessionLabel": "Sesión 1", "accumulatedMinutes": 0.0, "completionPercent": 100}
    ]
    assert (
        await client.get(f"/api/v1/children/{child_id}/progress", headers=child_headers)
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/children/{child_id}/readings", headers=child_headers)
    ).status_code == 200
    assert (
        await client.delete(f"/api/v1/children/{child_id}/library/{doc_id}", headers=headers)
    ).status_code == 204
    assert (
        await client.get(f"/api/v1/documents/{doc_id}", headers=child_headers)
    ).status_code == 404


async def test_adult_role_is_preserved_but_cannot_manage_children(client, make_user, child_payload):
    _, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    me = await client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200 and me.json()["role"] == "ADULTO_INDEPENDIENTE"
    assert (
        await client.post("/api/v1/children", headers=headers, json=child_payload)
    ).status_code == 403
    assert (
        await client.post("/api/v1/adaptations/text", headers=headers, json={"text": SOURCE})
    ).status_code == 200


async def test_library_and_metadata_delete_are_owner_scoped(client, make_user, child_payload):
    _, headers, _ = await make_user()
    _, outsider, _ = await make_user()
    child = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()
    child_id = child["id"]
    adapted = await client.post(
        "/api/v1/adaptations/text", headers=headers, json={"text": SOURCE, "child_id": child_id}
    )
    document_id = adapted.json()["document"]["id"]
    library = await client.get(f"/api/v1/children/{child_id}/library", headers=headers)
    assert library.status_code == 200 and library.json()[0]["id"] == document_id
    assert (
        await client.get(f"/api/v1/children/{child_id}/library", headers=outsider)
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/documents/{document_id}", headers=outsider)
    ).status_code == 404
    reading = await client.post(
        f"/api/v1/children/{child_id}/readings", headers=headers, json={"document_id": document_id}
    )
    assert reading.status_code == 201
    assert (
        await client.delete(f"/api/v1/documents/{document_id}", headers=headers)
    ).status_code == 204
    assert (
        await client.get(f"/api/v1/documents/{document_id}", headers=headers)
    ).status_code == 404
    history = await client.get(f"/api/v1/children/{child_id}/readings", headers=headers)
    assert history.status_code == 200 and history.json()[0]["document_id"] is None
