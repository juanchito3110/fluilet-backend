import uuid
from datetime import timedelta

import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app import auth, models, schemas
from app.config import Settings, settings
from tests.conftest import PASSWORD


def test_bcrypt_cost_and_configuration(password_hash):
    assert int(password_hash.split("$")[2]) >= 13
    assert auth.verify_password(PASSWORD, password_hash)
    with pytest.raises(ValidationError):
        Settings(BCRYPT_ROUNDS=12)
    with pytest.raises(ValidationError) as error:
        Settings(SECRET_KEY="private-short-key")
    assert "private-short-key" not in str(error.value)


def test_unicode_password_byte_limit():
    with pytest.raises(ValidationError):
        schemas.UserCreate(
            email="test@example.com",
            full_name="Valid User",
            role="tutor",
            password="Aa1!" + "á" * 35,
        )
    assert not auth.verify_password("x" * 73, "invalid")


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": None},
        {"sub": "invalid"},
        {"jti": "invalid"},
        {"role": "ADMIN"},
        {"ver": "0"},
        {"type": "refresh"},
        {"aud": "other"},
        {"iss": "other"},
    ],
)
def test_jwt_rejects_invalid_claims(changes):
    now = auth.utcnow()
    claims = {
        "sub": str(uuid.uuid4()),
        "role": "TUTOR",
        "type": "access",
        "ver": 0,
        "iat": now,
        "exp": now + timedelta(minutes=1),
        "jti": str(uuid.uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    claims.update(changes)
    if claims["exp"] is None:
        del claims["exp"]
    token = jwt.encode(claims, settings.SECRET_KEY.get_secret_value(), algorithm="HS256")
    with pytest.raises(HTTPException) as error:
        auth.decode_token(token)
    assert error.value.status_code == 401


async def test_no_demo_access(client):
    response = await client.post(
        "/api/v1/auth/login", data={"username": "profe@fluilet.com", "password": "123456"}
    )
    assert response.status_code == 401
    assert "access_token" not in response.json()


async def test_login_rotation_and_replay_revokes_session(client, make_user, db):
    user, _, _ = await make_user()
    login = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": PASSWORD}
    )
    assert login.status_code == 200
    first = login.json()
    assert set(first) == {"access_token", "refresh_token", "token_type", "role", "is_master_admin"}
    assert first["is_master_admin"] is False
    assert first["role"] == "TUTOR" and first["token_type"] == "bearer"
    refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert refresh.status_code == 200
    second = refresh.json()
    assert first["refresh_token"] != second["refresh_token"]
    replay = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert replay.status_code == 401
    assert (
        await client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer " + second["access_token"]}
        )
    ).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]})
    ).status_code == 401
    rows = (await db.scalars(select(models.RefreshToken))).all()
    assert rows and all(row.revoked for row in rows)
    assert all(
        row.token_hash not in {first["refresh_token"], second["refresh_token"]} for row in rows
    )


async def test_logout_revokes_access_and_refresh(client, make_user):
    _, headers, tokens = await make_user()
    assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 204
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens.refresh_token})
    ).status_code == 401


async def test_account_lockout_and_generic_errors(client, make_user):
    user, _, _ = await make_user()
    for _ in range(5):
        assert (
            await client.post(
                "/api/v1/auth/login", data={"username": user.email, "password": "wrong"}
            )
        ).status_code == 401
    assert (
        await client.post("/api/v1/auth/login", data={"username": user.email, "password": PASSWORD})
    ).status_code == 401


async def test_child_identity_and_owner_rbac(client, make_user, child_payload):
    _, tutor_headers, _ = await make_user()
    _, other_headers, _ = await make_user()
    created = await client.post("/api/v1/children", headers=tutor_headers, json=child_payload)
    assert created.status_code == 201
    child_id = created.json()["id"]
    assert created.json()["nivel_simplificacion_nlp"] == 1
    assert (
        await client.get(f"/api/v1/children/{child_id}", headers=other_headers)
    ).status_code == 404
    email = f"{uuid.uuid4().hex}@example.com"
    account = await client.post(
        f"/api/v1/children/{child_id}/account",
        headers=tutor_headers,
        json={"email": email, "password": PASSWORD},
    )
    assert account.status_code == 201 and account.json()["role"] == "NINO"
    login = await client.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD})
    assert login.status_code == 200 and login.json()["role"] == "NINO"
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    own_profile = await client.get("/api/v1/children/me", headers=headers)
    assert own_profile.status_code == 200 and own_profile.json()["id"] == child_id
    assert (await client.get("/api/v1/children", headers=headers)).status_code == 403
    assert (
        await client.post("/api/v1/adaptations/text", headers=headers, json={"text": "private"})
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/children/{child_id}", headers=tutor_headers, json={"is_active": False}
        )
    ).status_code == 200
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 401


async def test_child_cannot_self_register(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "full_name": "Test User",
            "password": PASSWORD,
            "role": "NINO",
        },
    )
    assert response.status_code == 422


@pytest.mark.postgres
async def test_concurrent_refresh_cannot_rotate_same_token_twice(db, make_user):
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker

    if db.bind.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock semantics required")
    user, _, token = await make_user()
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)

    async def rotate():
        async with sessions() as session:
            try:
                return await auth.rotate_refresh(token.refresh_token, session)
            except HTTPException as error:
                return error.status_code

    outcomes = await asyncio.gather(rotate(), rotate())
    assert sum(isinstance(value, schemas.Token) for value in outcomes) == 1
    assert outcomes.count(401) == 1
    await db.refresh(user)
    assert user.auth_version == 1


async def test_legacy_bcrypt_is_upgraded_and_password_change_revokes_tokens(client, make_user, db):
    import bcrypt

    user, headers, old = await make_user()
    user.hashed_password = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=12)).decode()
    await db.commit()
    response = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200
    await db.refresh(user)
    assert int(user.hashed_password.split("$")[2]) >= 13
    response = await client.post(
        "/api/v1/auth/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "NewValidPass123!"},
    )
    assert response.status_code == 204
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": old.refresh_token})
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login", data={"username": user.email, "password": "NewValidPass123!"}
        )
    ).status_code == 200
