"""Fluilet API: async persistence, scoped identities and authorized retained lessons."""

import uuid
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth, models, schemas
from app.academic_demo import router as academic_demo_router
from app.activities import router as activities_router
from app.adaptations import router as adaptations_router
from app.admin import router as admin_router
from app.config import settings
from app.database import SessionLocal, engine, get_db
from app.health import router as health_router
from app.nlp.mt5 import runtime
from app.password_reset import router as password_reset_router
from app.privacy import PrivacyMiddleware, validation_error
from app.services import email_service


@asynccontextmanager
async def lifespan(app):
    import asyncio

    from app.services.ranker import checkpoint
    from app.services.resources import resources

    await asyncio.to_thread(resources)
    await asyncio.to_thread(checkpoint)
    if settings.DEMO_ACCOUNTS_ENABLED:
        from app.demo_accounts import ensure_accounts

        async with SessionLocal() as db:
            try:
                await ensure_accounts(db)
            except Exception:
                await db.rollback()
                raise RuntimeError(
                    "No se pudieron preparar las cuentas de demostración. Verifica las migraciones y las identidades reservadas."
                ) from None
    yield
    await runtime.close()
    await auth.close()
    await email_service.close()
    await engine.dispose()


app = FastAPI(title="Fluilet API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(PrivacyMiddleware)
app.add_exception_handler(RequestValidationError, validation_error)
ADULTS = (models.UserRole.TUTOR, models.UserRole.ADULTO_INDEPENDIENTE)


async def commit(db):
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "No fue posible completar la operación.") from None


async def lock_user(user, db):
    return await db.scalar(
        select(models.User)
        .where(models.User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


@app.post("/api/v1/auth/register", response_model=schemas.UserRead, status_code=201, tags=["auth"])
async def register(payload: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    from app.demo_accounts import RESERVED_EMAILS

    if str(payload.email).lower() in RESERVED_EMAILS:
        raise HTTPException(409, "La dirección está reservada para la demostración.")
    user = models.User(
        email=str(payload.email).lower(),
        full_name=payload.full_name,
        hashed_password=await auth.hash_async(payload.password),
        role=payload.role,
    )
    db.add(user)
    await commit(db)
    await db.refresh(user)
    return user


@app.post("/api/v1/auth/login", response_model=schemas.Token, tags=["auth"])
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    if len(form.username) > 254 or len(form.password.encode("utf-8")) > 72:
        raise auth.unauthorized()
    user = await db.scalar(
        select(models.User)
        .where(func.lower(models.User.email) == form.username.lower())
        .with_for_update()
    )
    correct = await auth.verify_async(form.password, user.hashed_password if user else None)
    if user is None:
        raise auth.unauthorized()
    if user.locked_until and auth.aware(user.locked_until) > auth.utcnow():
        raise auth.unauthorized()
    if not correct:
        if user.locked_until and auth.aware(user.locked_until) <= auth.utcnow():
            user.failed_login_attempts = 0
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = auth.utcnow() + timedelta(minutes=15)
        await db.commit()
        raise auth.unauthorized()
    await auth.validate_identity(user, db)
    user.failed_login_attempts, user.locked_until = 0, None
    if int(user.hashed_password.split("$")[2]) < settings.BCRYPT_ROUNDS:
        user.hashed_password = await auth.hash_async(form.password)
    result = await auth.issue_pair(user, db)
    await db.commit()
    return result


@app.post("/api/v1/auth/refresh", response_model=schemas.Token, tags=["auth"])
async def refresh_token(payload: schemas.TokenRefreshRequest, db: AsyncSession = Depends(get_db)):
    return await auth.rotate_refresh(payload.refresh_token, db)


@app.post("/api/v1/auth/logout", status_code=204, tags=["auth"])
async def logout(
    user: models.User = Depends(auth.get_current_user), db: AsyncSession = Depends(get_db)
):
    user = await lock_user(user, db)
    await auth.revoke_all(user, db)
    await db.commit()
    return Response(status_code=204)


@app.post("/api/v1/auth/password", status_code=204, tags=["auth"])
async def change_password(
    payload: schemas.PasswordChange,
    user: models.User = Depends(auth.require_roles(*ADULTS)),
    db: AsyncSession = Depends(get_db),
):
    user = await lock_user(user, db)
    if not await auth.verify_async(payload.current_password, user.hashed_password):
        raise auth.unauthorized()
    user.hashed_password = await auth.hash_async(payload.new_password)
    await auth.revoke_all(user, db)
    await db.commit()
    return Response(status_code=204)


@app.get("/api/v1/auth/me", response_model=schemas.UserRead, tags=["auth"])
@app.get("/api/v1/users/me", response_model=schemas.UserRead, tags=["users"])
async def read_current_user(user: models.User = Depends(auth.get_current_user)):
    return user


@app.patch("/api/v1/users/me", response_model=schemas.UserRead, tags=["users"])
async def update_current_user(
    payload: schemas.UserUpdate,
    user: models.User = Depends(auth.require_roles(*ADULTS)),
    db: AsyncSession = Depends(get_db),
):
    if payload.full_name is not None:
        user.full_name = payload.full_name
    await commit(db)
    await db.refresh(user)
    return user


@app.delete("/api/v1/users/me", status_code=204, tags=["users"])
async def deactivate_current_user(
    user: models.User = Depends(auth.require_roles(*ADULTS)), db: AsyncSession = Depends(get_db)
):
    user = await lock_user(user, db)
    user.is_active = False
    await auth.revoke_all(user, db)
    await db.commit()
    return Response(status_code=204)


async def owned_child(child_id: uuid.UUID, user: models.User, db: AsyncSession, *, lock=False):
    statement = select(models.ChildProfile).where(
        models.ChildProfile.id == child_id, models.ChildProfile.tutor_id == user.id
    )
    if lock:
        statement = statement.with_for_update()
    child = await db.scalar(statement)
    if child is None:
        raise HTTPException(404, "Perfil no encontrado.")
    return child


@app.post(
    "/api/v1/children", response_model=schemas.ChildProfileRead, status_code=201, tags=["children"]
)
async def create_child_profile(
    payload: schemas.ChildProfileCreate,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    child = models.ChildProfile(
        **payload.model_dump(exclude={"pin"}),
        tutor_id=user.id,
        pin_hash=await auth.hash_async(payload.pin) if payload.pin else None,
    )
    db.add(child)
    await commit(db)
    await db.refresh(child)
    return child


@app.get("/api/v1/children", response_model=list[schemas.ChildProfileRead], tags=["children"])
async def list_child_profiles(
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    return (
        await db.scalars(
            select(models.ChildProfile)
            .where(models.ChildProfile.tutor_id == user.id, models.ChildProfile.is_active.is_(True))
            .order_by(models.ChildProfile.created_at)
            .limit(500)
        )
    ).all()


@app.get("/api/v1/children/me", response_model=schemas.ChildProfileRead, tags=["children"])
async def my_child_profile(
    user: models.User = Depends(auth.require_roles(models.UserRole.NINO)),
    db: AsyncSession = Depends(get_db),
):
    return await auth.child_for_user(user, db)


@app.get("/api/v1/children/{child_id}", response_model=schemas.ChildProfileRead, tags=["children"])
async def get_child_profile(
    child_id: uuid.UUID,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    return await owned_child(child_id, user, db)


@app.patch(
    "/api/v1/children/{child_id}", response_model=schemas.ChildProfileRead, tags=["children"]
)
async def update_child_profile(
    child_id: uuid.UUID,
    payload: schemas.ChildProfileUpdate,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    child = await owned_child(child_id, user, db, lock=True)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(child, field, value)
    if "is_active" in payload.model_fields_set and child.user_id:
        account = await db.get(models.User, child.user_id, with_for_update=True)
        account.is_active = child.is_active
        await auth.revoke_all(account, db)
    await commit(db)
    await db.refresh(child)
    return child


@app.delete("/api/v1/children/{child_id}", status_code=204, tags=["children"])
async def delete_child_profile(
    child_id: uuid.UUID,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    child = await owned_child(child_id, user, db, lock=True)
    child.is_active = False
    if child.user_id:
        account = await db.get(models.User, child.user_id, with_for_update=True)
        account.is_active = False
        await auth.revoke_all(account, db)
    await db.commit()
    return Response(status_code=204)


@app.post(
    "/api/v1/children/{child_id}/account",
    response_model=schemas.UserRead,
    status_code=201,
    tags=["children"],
)
async def create_child_account(
    child_id: uuid.UUID,
    payload: schemas.ChildAccountCreate,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    child = await owned_child(child_id, user, db, lock=True)
    if child.user_id or not child.is_active:
        raise HTTPException(409, "No fue posible crear la cuenta infantil.")
    account = models.User(
        email=str(payload.email).lower(),
        full_name=child.name,
        hashed_password=await auth.hash_async(payload.password),
        role=models.UserRole.NINO,
    )
    db.add(account)
    try:
        await db.flush()
        child.user_id = account.id
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "No fue posible crear la cuenta infantil.") from None
    await db.refresh(account)
    return account


@app.post("/api/v1/children/{child_id}/session", response_model=schemas.Token, tags=["children"])
async def open_child_session(
    child_id: uuid.UUID,
    payload: schemas.ChildSessionRequest,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    child = await owned_child(child_id, user, db, lock=True)
    if child.pin_hash and not await auth.verify_async(payload.pin or "", child.pin_hash):
        raise auth.unauthorized()
    if not child.user_id or not child.is_active:
        raise HTTPException(409, "El perfil requiere una cuenta infantil activa.")
    account = await db.get(models.User, child.user_id, with_for_update=True)
    await auth.validate_identity(account, db)
    result = await auth.issue_pair(account, db)
    await db.commit()
    return result


app.include_router(activities_router)
app.include_router(adaptations_router)
app.include_router(academic_demo_router)
app.include_router(admin_router)
app.include_router(health_router)
app.include_router(password_reset_router)


@app.post("/api/v1/auth/verify-parental-pin", tags=["auth"])
async def verify_parental_pin(
    payload: schemas.VerifyParentalPin,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
):
    return {"valid": await auth.verify_async(payload.pin, user.parental_pin_hash)}
