"""Physical erasure, transactional rollback and clean public-demo restoration."""

import hashlib
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app import auth, models
from app.demo_accounts import (
    MASTER_EMAIL,
    MASTER_PASSWORD,
    TUTOR_EMAIL,
    TUTOR_PASSWORD,
    ensure_accounts,
)
from tests.conftest import PASSWORD


async def counts(db):
    # Read every table from SQL, rather than relying on the ORM identity map.
    return {
        table.name: await db.scalar(select(func.count()).select_from(table))
        for table in models.Base.metadata.sorted_tables
    }


async def retained_data(db, owner, *, child=None):
    document = models.Document(
        owner_id=owner.id,
        file_type=models.DocumentType.TXT,
        file_size_bytes=100,
        content_sha256=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        word_count=30,
        chunk_count=1,
    )
    db.add(document)
    await db.flush()
    db.add(models.AdaptationChunk(document_id=document.id, chunk_index=0))
    db.add(
        models.AdaptationContent(
            document_id=document.id,
            child_id=child.id if child else None,
            context_key=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            target_level=1,
            age_group="6-8" if child else "12+",
            original_text="Contenido personal que debe desaparecer definitivamente.",
            adapted_text="Mi lectura privada que debe desaparecer.",
            response_payload={"private": "Contenido personal eliminado"},
        )
    )
    reading = models.ReadingSession(
        document_id=document.id,
        child_id=child.id if child else None,
        reader_user_id=None if child else owner.id,
        completed=True,
        completion_percent=100,
        reading_time_seconds=60,
        questions_answered=3,
        questions_correct=2,
    )
    db.add(reading)
    await db.flush()
    db.add(
        models.ReadingActivityDay(
            reading_id=reading.id,
            activity_date=auth.utcnow().date(),
            lesson_key=document.content_sha256,
            completed=True,
            correct_answer=True,
        )
    )
    if child:
        db.add(models.ChildLibraryItem(child_id=child.id, document_id=document.id))


async def family(db, client, make_user, child_payload, role):
    user, headers, tokens = await make_user(role)
    linked_tokens = None
    related_users = [user]
    if role == models.UserRole.TUTOR:
        children = []
        for _ in range(2):
            response = await client.post("/api/v1/children", headers=headers, json=child_payload)
            assert response.status_code == 201
            children.append(await db.get(models.ChildProfile, uuid.UUID(response.json()["id"])))
        child, inactive = children
        inactive.is_active = False
        linked = models.User(
            email=f"{uuid.uuid4().hex}@example.com",
            full_name="Cuenta infantil vinculada",
            role=models.UserRole.NINO,
            hashed_password=user.hashed_password,
        )
        db.add(linked)
        await db.flush()
        child.user_id = linked.id
        linked_tokens = await auth.issue_pair(linked, db)
        related_users.append(linked)
        for profile in children:
            db.add(models.ProfileControl(child_id=profile.id, gems_offset=50, xp_offset=80))
            await retained_data(db, user, child=profile)
    else:
        db.add(models.ReaderControl(user_id=user.id, gems_offset=50, xp_offset=80))
        await retained_data(db, user)
    for account in related_users:
        db.add(
            models.PasswordResetRequest(
                user_id=account.id,
                code_hash="a" * 64,
                expires_at=auth.utcnow() + timedelta(minutes=10),
            )
        )
    await db.commit()
    return user, headers, tokens, linked_tokens


@pytest.mark.parametrize("role", [models.UserRole.TUTOR, models.UserRole.ADULTO_INDEPENDIENTE])
async def test_self_deletion_removes_all_owned_rows_and_keeps_other_accounts(
    db, client, make_user, child_payload, role
):
    other, other_headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    db.add(models.ReaderControl(user_id=other.id, gems_offset=70))
    await retained_data(db, other)
    await db.commit()
    baseline = await counts(db)
    user, headers, tokens, child_tokens = await family(db, client, make_user, child_payload, role)
    email, old_id = user.email, user.id
    populated = await counts(db)
    assert populated["documents"] > baseline["documents"]
    assert populated["reading_activity_days"] > baseline["reading_activity_days"]
    assert populated["adaptation_contents"] > baseline["adaptation_contents"]
    assert populated["password_reset_requests"] > baseline["password_reset_requests"]
    response = await client.delete("/api/v1/users/me", headers=headers)
    assert response.status_code == 204 and not response.content
    assert await counts(db) == baseline
    assert await db.scalar(select(models.User.id).where(models.User.id == old_id)) is None
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 401
    assert (await client.get("/api/v1/users/me", headers=other_headers)).status_code == 200
    assert await db.get(models.User, other.id) is not None
    for pair in (tokens, child_tokens):
        if pair is not None:
            assert (
                await client.get(
                    "/api/v1/users/me", headers={"Authorization": "Bearer " + pair.access_token}
                )
            ).status_code == 401
            assert (
                await client.post(
                    "/api/v1/auth/refresh", json={"refresh_token": pair.refresh_token}
                )
            ).status_code == 401
    assert (
        await client.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD})
    ).status_code == 401
    assert (await client.delete("/api/v1/users/me", headers=headers)).status_code == 401
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Cuenta nueva", "role": role},
    )
    assert registered.status_code == 201 and registered.json()["id"] != str(old_id)


async def test_self_deletion_rolls_back_the_entire_family_on_failure(
    db, client, make_user, child_payload, monkeypatch
):
    _, headers, _, _ = await family(db, client, make_user, child_payload, models.UserRole.TUTOR)
    before = await counts(db)
    execute = db.execute
    deletions = 0

    async def fail_second_delete(statement, *args, **kwargs):
        nonlocal deletions
        if getattr(statement, "is_delete", False):
            deletions += 1
            if deletions == 2:
                raise RuntimeError("Simulated failure; do not expose database contents")
        return await execute(statement, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(db, "execute", fail_second_delete)
        response = await client.delete("/api/v1/users/me", headers=headers)
    assert deletions == 2 and response.status_code == 500
    assert "Simulated" not in response.text
    assert await counts(db) == before
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 200


@pytest.mark.parametrize("email", ["admin@fluilet.com", "ADMIN@FLUILET.COM"])
async def test_master_email_is_protected_even_if_its_role_metadata_changes(
    db, client, make_user, email
):
    user, headers, _ = await make_user()
    user.email = email
    await db.commit()
    before = await counts(db)
    response = await client.delete("/api/v1/users/me", headers=headers)
    assert response.status_code == 403
    assert "cuenta maestra" in response.json()["detail"]
    assert await counts(db) == before


async def test_child_cannot_delete_its_family_and_anonymous_request_is_rejected(
    db, client, make_user, child_payload
):
    _, _, _, pair = await family(db, client, make_user, child_payload, models.UserRole.TUTOR)
    before = await counts(db)
    assert (await client.delete("/api/v1/users/me")).status_code == 401
    response = await client.delete(
        "/api/v1/users/me", headers={"Authorization": "Bearer " + pair.access_token}
    )
    assert response.status_code == 403 and "tutor" in response.json()["detail"]
    assert await counts(db) == before


async def test_deleted_demo_is_recreated_with_initial_public_data_only(db, client, make_user):
    await ensure_accounts(db)

    async def login(email, password):
        response = await client.post(
            "/api/v1/auth/login", data={"username": email, "password": password}
        )
        assert response.status_code == 200
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    master = await login(MASTER_EMAIL, MASTER_PASSWORD)
    tutor = await login(TUTOR_EMAIL, TUTOR_PASSWORD)
    assert (await client.delete("/api/v1/users/me", headers=master)).status_code == 403
    other, other_headers, _ = await make_user()
    unrelated_hash = other.hashed_password
    owner = await db.scalar(select(models.User).where(models.User.email == TUTOR_EMAIL))
    old_id = owner.id
    old_profiles = set((await db.scalars(select(models.ChildProfile.id))).all())
    old_lessons = set((await db.scalars(select(models.AdaptationContent.id))).all())
    await retained_data(db, owner)
    await db.commit()
    assert (await client.delete("/api/v1/users/me", headers=tutor)).status_code == 204
    for table in (
        models.ChildProfile,
        models.Document,
        models.AdaptationContent,
        models.ReadingSession,
        models.ReadingActivityDay,
        models.ProfileControl,
    ):
        assert await db.scalar(select(func.count()).select_from(table)) == 0
    response = await client.post("/api/v1/admin/ensure-demo-accounts", headers=master)
    assert response.status_code == 200
    restored = await db.scalar(select(models.User).where(models.User.email == TUTOR_EMAIL))
    assert restored.id != old_id
    profiles = (await db.scalars(select(models.ChildProfile))).all()
    assert len(profiles) == 4 and not old_profiles.intersection(p.id for p in profiles)
    assert next(p for p in profiles if p.name == "Sofía").current_level == 1
    lessons = (await db.scalars(select(models.AdaptationContent))).all()
    assert len(lessons) == 15 and not old_lessons.intersection(lesson.id for lesson in lessons)
    assert not any("Contenido personal" in lesson.original_text for lesson in lessons)
    assert await db.scalar(select(func.count()).select_from(models.ReadingSession)) == 15
    assert (await client.get("/api/v1/users/me", headers=tutor)).status_code == 401
    tutor = await login(TUTOR_EMAIL, TUTOR_PASSWORD)
    assert (await client.get("/api/v1/users/me", headers=tutor)).status_code == 200
    assert (await client.get("/api/v1/users/me", headers=other_headers)).status_code == 200
    assert (await db.get(models.User, other.id)).hashed_password == unrelated_hash
    again = await client.post("/api/v1/admin/ensure-demo-accounts", headers=master)
    assert again.status_code == 200
    assert set((await db.scalars(select(models.ChildProfile.id))).all()) == {
        profile.id for profile in profiles
    }
    assert set((await db.scalars(select(models.AdaptationContent.id))).all()) == {
        lesson.id for lesson in lessons
    }
