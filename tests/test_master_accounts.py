"""Real login, startup provisioning, master RBAC, adjustments and physical cascades."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app import auth, models
from app.demo_accounts import (
    MASTER_EMAIL,
    MASTER_PASSWORD,
    TUTOR_EMAIL,
    TUTOR_PASSWORD,
    ensure_accounts,
)
from app.nlp.readability import measure


@pytest_asyncio.fixture
async def demo(db, client):
    await ensure_accounts(db)
    tokens = {}
    for email, password in ((MASTER_EMAIL, MASTER_PASSWORD), (TUTOR_EMAIL, TUTOR_PASSWORD)):
        result = await client.post(
            "/api/v1/auth/login", data={"username": email, "password": password}
        )
        assert result.status_code == 200, result.text
        tokens[email] = (
            {"Authorization": "Bearer " + result.json()["access_token"]},
            result.json(),
        )
    return tokens


async def test_accounts_phases_real_lesson_payloads_and_regular_registration(client, db, demo):
    headers, token = demo[TUTOR_EMAIL]
    assert token["role"] == "TUTOR" and token["is_master_admin"] is False
    children = (await client.get("/api/v1/children", headers=headers)).json()
    assert {child["name"] for child in children} == {"Sofía", "Mateo", "Diego", "Valentina"}
    expected = {
        "Sofía": (1, 45, 40, 1, 1),
        "Mateo": (2, 160, 190, 3, 3),
        "Diego": (3, 340, 460, 6, 5),
        "Valentina": (4, 900, 980, 12, 6),
    }
    for child in children:
        data = (
            await client.get(
                f"/api/v1/profiles/{child['id']}/educational-progress", headers=headers
            )
        ).json()
        stage, gems, xp, streak, completed = expected[child["name"]]
        assert data["mascot"]["stage"] == stage
        assert (
            data["total_gems"],
            data["total_xp"],
            data["current_streak_days"],
            data["completed_lessons"],
        ) == (gems, xp, streak, completed)
        assert data["has_admin_adjustments"] and data["demo_data"]
        assert data["current_recommended_level"] == child["nivel_simplificacion_nlp"]
        if child["name"] == "Diego":
            assert sum(m["completed"] for m in data["daily_missions"]) == 2
        if child["name"] == "Valentina":
            assert all(
                card["unlocked"] and card["rarity"] == "Oro" for card in data["collectible_cards"]
            )
            assert all(badge["unlocked"] for badge in data["badges"])
            assert all(m["completed"] for m in data["daily_missions"])
            assert data["average_comprehension_score"] == 95
        contents = (
            await db.scalars(
                select(models.AdaptationContent).where(
                    models.AdaptationContent.child_id == uuid.UUID(child["id"])
                )
            )
        ).all()
        assert len(contents) == completed
        for content in contents:
            response = await client.get("/api/v1/adaptations/" + str(content.id), headers=headers)
            assert response.status_code == 200, response.text
            lesson = response.json()
            assert lesson["original_text"] != lesson["adapted_text"]
            assert lesson["original_readability_score"] == pytest.approx(
                measure(lesson["original_text"]).score
            )
            assert lesson["readability_score"] == pytest.approx(
                measure(lesson["adapted_text"]).score
            )
            assert lesson["fun_fact"] and len(lesson["key_vocabulary"]) in (3, 4)
            assert len(lesson["comprehension_questions"]) == 2
    assert (
        await client.post("/api/v1/auth/verify-parental-pin", headers=headers, json={"pin": "1234"})
    ).json() == {"valid": True}
    assert (
        await client.post("/api/v1/auth/verify-parental-pin", headers=headers, json={"pin": "9999"})
    ).json() == {"valid": False}
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "new.family@example.com",
            "password": "NewFamily2026!",
            "full_name": "Nueva familia",
            "role": "TUTOR",
        },
    )
    assert registration.status_code == 201, registration.text
    assert registration.json()["is_master_admin"] is False
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "new.family@example.com", "password": "NewFamily2026!"},
    )
    assert login.status_code == 200 and login.json()["is_master_admin"] is False


async def test_master_identity_overview_grant_and_idempotent_unlock(client, db, demo):
    master, token = demo[MASTER_EMAIL]
    tutor, _ = demo[TUTOR_EMAIL]
    assert token["role"] == "master_admin" and token["is_master_admin"] is True
    assert (await client.get("/api/v1/auth/me", headers=master)).json()["is_master_admin"] is True
    data = (await client.get("/api/v1/admin/overview", headers=master)).json()
    assert data["model_info"]["model_version"] == "context-ranker-es-v2.2"
    assert data["model_info"]["easier_benchmark_after"] == "6/6"
    assert (data["total_tutors"], data["total_profiles"], data["total_reading_sessions"]) == (
        1,
        4,
        15,
    )
    assert data["total_adaptations"] == 15
    assert len(data["users"]) == 2 and len(data["profiles"]) == 4
    child = next(item for item in data["profiles"] if item["name"] == "Sofía")
    path = f"/api/v1/admin/profiles/{child['profile_id']}/grant"
    response = await client.post(
        path,
        headers=master,
        json={
            "add_gems": 100,
            "set_evolution_stage": 3,
            "set_level": 4,
            "set_age_group": "12+",
            "set_streak_days": 9,
        },
    )
    assert response.status_code == 200, response.text
    changed = response.json()
    assert (
        changed["total_gems"] == 145
        and changed["mascot"]["stage"] == 3
        and changed["total_xp"] == 350
    )
    assert changed["current_recommended_level"] == 4 and changed["current_streak_days"] == 9
    assert (
        await client.get(
            f"/api/v1/profiles/{child['profile_id']}/educational-progress", headers=tutor
        )
    ).json() == changed
    generated = await client.post(
        "/api/v1/adaptations/generate",
        headers=tutor,
        json={
            "category": "deportes",
            "custom_topic": "Real Madrid",
            "child_id": child["profile_id"],
        },
    )
    assert generated.status_code == 200 and generated.json()["age_group"] == "12+"
    assert generated.json()["child_age_years"] == 7
    unlocked = await client.post(path, headers=master, json={"unlock_all_rewards": True})
    assert unlocked.status_code == 200 and unlocked.json()["mascot"]["stage"] == 4
    again = await client.post(path, headers=master, json={"unlock_all_rewards": True})
    assert again.status_code == 200 and again.json()["total_gems"] == unlocked.json()["total_gems"]
    zero = await client.post(path, headers=master, json={"set_gems": 0})
    assert zero.status_code == 200 and zero.json()["total_gems"] == 0
    assert not any(item["unlocked"] for item in zero.json()["shop_catalog"])
    assert (await client.post(path, headers=master, json={"add_gems": -1})).status_code == 422
    assert (
        await client.post(path, headers=master, json={"set_gems": 22, "add_gems": 5})
    ).status_code == 422
    assert (
        await client.post(path, headers=master, json={"set_evolution_stage": 5})
    ).status_code == 422
    assert (await client.post(path, headers=master, json={"add_gems": True})).status_code == 422
    assert (await client.post(path, headers=master, json={})).status_code == 422


async def test_deletion_cascades_and_restore_preserves_real_accounts_and_grants(
    client, db, demo, make_user, child_payload
):
    master, _ = demo[MASTER_EMAIL]
    tutor, _ = demo[TUTOR_EMAIL]
    extra, extra_headers, _ = await make_user()
    normal = (
        await client.post("/api/v1/children", headers=extra_headers, json=child_payload)
    ).json()
    normal_id = uuid.UUID(normal["id"])
    extra_hash = extra.hashed_password
    children = (await client.get("/api/v1/children", headers=tutor)).json()
    victim = next(row for row in children if row["name"] == "Diego")
    victim_id = uuid.UUID(victim["id"])
    contents = (
        await db.scalars(
            select(models.AdaptationContent.id).where(
                models.AdaptationContent.child_id == victim_id
            )
        )
    ).all()
    assert (
        await client.delete("/api/v1/admin/profiles/" + victim["id"], headers=master)
    ).status_code == 204
    assert await db.get(models.ChildProfile, victim_id) is None
    assert await db.get(models.ProfileControl, victim_id) is None
    assert (
        await db.scalar(
            select(func.count())
            .select_from(models.ReadingSession)
            .where(models.ReadingSession.child_id == victim_id)
        )
        == 0
    )
    assert (
        await db.scalar(
            select(func.count())
            .select_from(models.AdaptationContent)
            .where(models.AdaptationContent.id.in_(contents))
        )
        == 0
    )
    restored = await client.post("/api/v1/admin/ensure-demo-accounts", headers=master)
    assert restored.status_code == 200, restored.text
    assert len([p for p in restored.json()["profiles"] if p["tutor_email"] == TUTOR_EMAIL]) == 4
    assert await db.get(models.ChildProfile, normal_id) is not None
    assert (await db.get(models.User, extra.id)).hashed_password == extra_hash
    sofia = next(p for p in restored.json()["profiles"] if p["name"] == "Sofía")
    await client.post(
        f"/api/v1/admin/profiles/{sofia['profile_id']}/grant", headers=master, json={"add_gems": 20}
    )
    repeated = (await client.post("/api/v1/admin/ensure-demo-accounts", headers=master)).json()
    assert next(p for p in repeated["profiles"] if p["name"] == "Sofía")["total_gems"] == 65
    master_user = next(u for u in repeated["users"] if u["is_master_admin"])
    tutor_user = next(u for u in repeated["users"] if u["email"] == TUTOR_EMAIL)
    assert (
        await client.delete("/api/v1/admin/tutors/" + master_user["user_id"], headers=master)
    ).status_code == 400
    assert (
        await client.delete("/api/v1/admin/tutors/" + tutor_user["user_id"], headers=master)
    ).status_code == 204
    assert (
        await db.scalar(
            select(func.count())
            .select_from(models.ChildProfile)
            .where(models.ChildProfile.tutor_id == uuid.UUID(tutor_user["user_id"]))
        )
        == 0
    )
    assert (await client.get("/api/v1/users/me", headers=tutor)).status_code == 401
    after = await client.post("/api/v1/admin/ensure-demo-accounts", headers=master)
    assert after.status_code == 200, after.text
    assert (
        next(u for u in after.json()["users"] if u["email"] == TUTOR_EMAIL)["profiles_count"] == 4
    )
    assert await db.get(models.ChildProfile, normal_id) is not None
    assert (
        await client.delete("/api/v1/admin/tutors/" + str(extra.id), headers=master)
    ).status_code == 204
    assert await db.get(models.ChildProfile, normal_id) is None


async def test_master_rbac_reserved_registration_and_pin_reset(client, db, demo, make_user):
    master, _ = demo[MASTER_EMAIL]
    tutor, _ = demo[TUTOR_EMAIL]
    _, adult, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    overview = (await client.get("/api/v1/admin/overview", headers=master)).json()
    child = overview["profiles"][0]["profile_id"]
    tutor_id = next(u["user_id"] for u in overview["users"] if u["email"] == TUTOR_EMAIL)
    routes = [
        ("get", "/overview", None),
        ("post", "/ensure-demo-accounts", None),
        ("post", f"/profiles/{child}/grant", {"set_gems": 100}),
        ("delete", f"/profiles/{child}", None),
        ("delete", f"/tutors/{tutor_id}", None),
        ("post", f"/tutors/{tutor_id}/reset-pin", None),
    ]
    for method, path, payload in routes:
        for headers, status in (({}, 401), (tutor, 403), (adult, 403)):
            kwargs = {"headers": headers}
            if payload is not None:
                kwargs["json"] = payload
            assert (
                await client.request(method, "/api/v1/admin" + path, **kwargs)
            ).status_code == status
    for role in ("master_admin", "MASTER_ADMIN", "NINO"):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "attacker@example.com",
                "password": "ValidPass123!",
                "full_name": "Test User",
                "role": role,
            },
        )
        assert response.status_code == 422
    for email in ("ADMIN@FLUILET.COM", "tutor@fluilet.com"):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "ValidPass123!",
                "full_name": "Test User",
                "role": "TUTOR",
            },
        )
        assert response.status_code == 409
    response = await client.post(
        f"/api/v1/admin/tutors/{tutor_id}/reset-pin", headers=master, json={"pin": "5678"}
    )
    assert response.status_code == 200 and "5678" not in response.text
    assert (
        await client.post("/api/v1/auth/verify-parental-pin", headers=tutor, json={"pin": "5678"})
    ).json()["valid"]
    assert (
        await client.post(f"/api/v1/admin/tutors/{tutor_id}/reset-pin", headers=master)
    ).status_code == 200
    assert (
        await client.post("/api/v1/auth/verify-parental-pin", headers=tutor, json={"pin": "1234"})
    ).json()["valid"]
    user = await db.get(models.User, uuid.UUID(tutor_id))
    assert user.parental_pin_hash != "1234" and auth.verify_password("1234", user.parental_pin_hash)
    assert "parental_pin_hash" not in (await client.get("/api/v1/users/me", headers=tutor)).text


async def test_startup_seeds_once_without_weights_and_keeps_manual_demo_tutor_children(
    db, client, monkeypatch, child_payload
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import main
    from app.config import settings

    monkeypatch.setattr(settings, "DEMO_ACCOUNTS_ENABLED", True)
    monkeypatch.setattr(
        main, "SessionLocal", async_sessionmaker(db.bind, expire_on_commit=False, autoflush=False)
    )
    # Dispose only the application's unused engine; the test's private engine lives
    # until its own fixture ends. No configured application DB connection is made.
    for _ in range(2):
        async with main.lifespan(main.app):
            assert await db.scalar(select(func.count()).select_from(models.User)) == 2
            assert await db.scalar(select(func.count()).select_from(models.ChildProfile)) == 4
            assert await db.scalar(select(func.count()).select_from(models.ReadingSession)) == 15
    response = await client.post(
        "/api/v1/auth/login", data={"username": TUTOR_EMAIL, "password": TUTOR_PASSWORD}
    )
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    created = (
        await client.post(
            "/api/v1/children", headers=headers, json={**child_payload, "name": "Sofía"}
        )
    ).json()
    await ensure_accounts(db)
    assert await db.get(models.ChildProfile, uuid.UUID(created["id"])) is not None
    assert await db.scalar(select(func.count()).select_from(models.ChildProfile)) == 5


async def test_email_alone_cannot_bootstrap_master(db, make_user, client):
    attacker, headers, _ = await make_user()
    attacker_id = attacker.id
    attacker.email = MASTER_EMAIL
    await db.commit()
    assert (await client.get("/api/v1/admin/overview", headers=headers)).status_code == 403
    with pytest.raises(RuntimeError, match="conflicts"):
        await ensure_accounts(db)
    await db.rollback()
    assert (await db.get(models.User, attacker_id)).role == models.UserRole.TUTOR
    assert not (await db.get(models.User, attacker_id)).is_master_admin


@pytest.mark.postgres
async def test_parallel_restore_is_one_cohort(db, client, demo):
    import asyncio
    import os

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.database import get_db
    from app.main import app

    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("Cross-session locking requires PostgreSQL")
    master, _ = demo[MASTER_EMAIL]
    original = app.dependency_overrides[get_db]
    sessions = async_sessionmaker(db.bind, expire_on_commit=False, autoflush=False)

    async def separate_db():
        async with sessions() as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = separate_db
    try:
        responses = await asyncio.gather(
            *(client.post("/api/v1/admin/ensure-demo-accounts", headers=master) for _ in range(2))
        )
        assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
        assert await db.scalar(select(func.count()).select_from(models.User)) == 2
        assert await db.scalar(select(func.count()).select_from(models.ChildProfile)) == 4
        assert await db.scalar(select(func.count()).select_from(models.ReadingSession)) == 15
        assert responses[0].json() == responses[1].json()
    finally:
        app.dependency_overrides[get_db] = original


async def test_grants_cover_each_stage_and_future_earned_resources(db, client, demo):
    master, token = demo[MASTER_EMAIL]
    tutor, _ = demo[TUTOR_EMAIL]
    refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": token["refresh_token"]}
    )
    assert refresh.status_code == 200 and refresh.json()["is_master_admin"] is True
    assert refresh.json()["role"] == "master_admin"
    overview = (await client.get("/api/v1/admin/overview", headers=master)).json()
    child = next(p for p in overview["profiles"] if p["name"] == "Sofía")
    path = f"/api/v1/admin/profiles/{child['profile_id']}/grant"
    for stage in (4, 3, 2, 1):
        response = await client.post(path, headers=master, json={"set_evolution_stage": stage})
        assert response.status_code == 200, response.text
        assert response.json()["mascot"]["stage"] == stage
        assert response.json()["total_xp"] == (0, 150, 350, 700)[stage - 1]
    xp = await client.post(path, headers=master, json={"add_xp": 40, "set_gems": 45})
    assert xp.status_code == 200 and xp.json()["total_xp"] == 40
    from tests.conftest import SOURCE

    lesson = (
        await client.post(
            "/api/v1/adaptations/text",
            headers=tutor,
            json={"text": SOURCE, "child_id": child["profile_id"]},
        )
    ).json()
    reading = (
        await client.post(
            f"/api/v1/children/{child['profile_id']}/readings",
            headers=tutor,
            json={"document_id": lesson["document"]["id"]},
        )
    ).json()
    assert (
        await client.patch(
            "/api/v1/readings/" + reading["id"],
            headers=tutor,
            json={"completed": True, "completion_percent": 100},
        )
    ).status_code == 200
    result = (
        await client.get(
            f"/api/v1/profiles/{child['profile_id']}/educational-progress", headers=tutor
        )
    ).json()
    assert (
        result["total_xp"] == 140 and result["total_gems"] == 135
    )  # +50 completion, +40 distinct-lesson mission.
    changed = await client.post(
        path, headers=master, json={"set_age_group": "9-11", "set_level": 2}
    )
    assert changed.status_code == 200 and changed.json()["age_group"] == "9-11"
    assert changed.json()["current_level"] == changed.json()["current_recommended_level"] == 2


async def test_hard_deletion_removes_linked_child_identity_and_refresh_tokens(
    db, client, demo, make_user, child_payload
):
    master, _ = demo[MASTER_EMAIL]
    owner, headers, _ = await make_user()
    profile = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    account = await client.post(
        f"/api/v1/children/{profile}/account",
        headers=headers,
        json={"email": "linked.child@example.com", "password": "ChildPass2026!"},
    )
    assert account.status_code == 201, account.text
    child_id = uuid.UUID(account.json()["id"])
    token = (
        await client.post(f"/api/v1/children/{profile}/session", headers=headers, json={})
    ).json()["access_token"]
    assert (
        await client.delete("/api/v1/admin/tutors/" + str(owner.id), headers=master)
    ).status_code == 204
    assert await db.get(models.User, child_id) is None
    assert (
        await db.scalar(
            select(func.count())
            .select_from(models.RefreshToken)
            .where(models.RefreshToken.user_id == child_id)
        )
        == 0
    )
    assert (
        await client.get("/api/v1/children/me", headers={"Authorization": "Bearer " + token})
    ).status_code == 401
