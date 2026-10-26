"""Only metadata and numeric reading telemetry. Every access is owner-scoped."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth, models, schemas
from app.daily_missions import authorized_activity, record_activity, snapshot
from app.database import get_db
from app.educational_progress import EDUCATIONAL_FIELDS, summarize, update_practice

router = APIRouter(prefix="/api/v1", tags=["activities"])


async def accessible_child(child_id, user, db):
    if user.role == models.UserRole.NINO:
        child = await auth.child_for_user(user, db)
        if child.id != child_id:
            raise HTTPException(404, "Perfil no encontrado.")
    elif user.role == models.UserRole.TUTOR:
        child = await db.scalar(
            select(models.ChildProfile).where(
                models.ChildProfile.id == child_id,
                models.ChildProfile.tutor_id == user.id,
                models.ChildProfile.is_active.is_(True),
            )
        )
        if child is None:
            raise HTTPException(404, "Perfil no encontrado.")
    else:
        raise HTTPException(403, "Acceso no permitido.")
    return child


async def accessible_document(document_id, user, db):
    statement = select(models.Document).where(models.Document.id == document_id)
    if user.role == models.UserRole.NINO:
        child = await auth.child_for_user(user, db)
        statement = statement.join(
            models.ChildLibraryItem, models.ChildLibraryItem.document_id == models.Document.id
        ).where(
            models.ChildLibraryItem.child_id == child.id, models.Document.owner_id == child.tutor_id
        )
    else:
        statement = statement.where(models.Document.owner_id == user.id)
    document = await db.scalar(statement)
    if document is None:
        raise HTTPException(404, "Actividad no encontrada.")
    return document


@router.get("/documents", response_model=list[schemas.DocumentRead])
async def documents(
    user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
    offset: int = 0,
):
    if offset < 0:
        raise HTTPException(422, "Paginación inválida.")
    statement = select(models.Document)
    if user.role == models.UserRole.NINO:
        child = await auth.child_for_user(user, db)
        statement = statement.join(
            models.ChildLibraryItem, models.ChildLibraryItem.document_id == models.Document.id
        ).where(
            models.ChildLibraryItem.child_id == child.id, models.Document.owner_id == child.tutor_id
        )
    else:
        statement = statement.where(models.Document.owner_id == user.id)
    return (
        await db.scalars(
            statement.order_by(models.Document.uploaded_at, models.Document.id)
            .offset(offset)
            .limit(100)
        )
    ).all()


@router.get("/documents/{document_id}", response_model=schemas.DocumentRead)
async def document(
    document_id: uuid.UUID,
    user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await accessible_document(document_id, user, db)


@router.post("/children/{child_id}/library", status_code=204)
async def assign_document(
    child_id: uuid.UUID,
    payload: schemas.AssignmentRequest,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    await accessible_child(child_id, user, db)
    await accessible_document(payload.document_id, user, db)
    existing = await db.scalar(
        select(models.ChildLibraryItem).where(
            models.ChildLibraryItem.child_id == child_id,
            models.ChildLibraryItem.document_id == payload.document_id,
        )
    )
    if existing is None:
        db.add(models.ChildLibraryItem(child_id=child_id, document_id=payload.document_id))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, "La asignación ya existe.") from None


@router.delete("/children/{child_id}/library/{document_id}", status_code=204)
async def unassign_document(
    child_id: uuid.UUID,
    document_id: uuid.UUID,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    await accessible_child(child_id, user, db)
    item = await db.scalar(
        select(models.ChildLibraryItem).where(
            models.ChildLibraryItem.child_id == child_id,
            models.ChildLibraryItem.document_id == document_id,
        )
    )
    if item is None:
        raise HTTPException(404, "Asignación no encontrada.")
    await db.delete(item)
    await db.commit()


@router.post("/children/{child_id}/readings", response_model=schemas.ReadingRead, status_code=201)
async def start_reading(
    child_id: uuid.UUID,
    payload: schemas.ReadingCreate,
    user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await accessible_child(child_id, user, db)
    document = await accessible_document(payload.document_id, user, db)
    assigned = await db.scalar(
        select(models.ChildLibraryItem).where(
            models.ChildLibraryItem.child_id == child_id,
            models.ChildLibraryItem.document_id == payload.document_id,
        )
    )
    if assigned is None:
        raise HTTPException(404, "Asignación no encontrada.")
    reading = reading_snapshot(document, child_id=child_id)
    update_practice(reading, payload.model_dump(exclude_unset=True))
    db.add(reading)
    await record_activity(reading, db)
    await db.commit()
    await db.refresh(reading)
    return reading


def reading_snapshot(document, *, child_id=None, reader_user_id=None):
    # Capture scores at the start of the reading, independently of subsequent
    # re-adaptations/deletion of the metadata document. Never copy any content.
    metrics = {name: getattr(document, name) for name in models.AdaptationTelemetry.__annotations__}
    return models.ReadingSession(
        child_id=child_id,
        reader_user_id=reader_user_id,
        document_id=document.id,
        category=document.category,
        simplification_level=document.simplification_level,
        questions_answered=0,
        questions_correct=0,
        tts_speed_used=1.0,
        **metrics,
    )


async def authorize_reading(reading, user, db):
    if reading.child_id is None:
        if user.role != models.UserRole.ADULTO_INDEPENDIENTE or reading.reader_user_id != user.id:
            raise HTTPException(404, "Sesión no encontrada.")
    else:
        if user.role == models.UserRole.ADULTO_INDEPENDIENTE:
            raise HTTPException(404, "Sesión no encontrada.")
        await accessible_child(reading.child_id, user, db)


@router.post("/readings", response_model=schemas.ReadingRead, status_code=201)
async def start_independent_reading(
    payload: schemas.ReadingCreate,
    user: models.User = Depends(auth.require_roles(models.UserRole.ADULTO_INDEPENDIENTE)),
    db: AsyncSession = Depends(get_db),
):
    document = await accessible_document(payload.document_id, user, db)
    reading = reading_snapshot(document, reader_user_id=user.id)
    update_practice(reading, payload.model_dump(exclude_unset=True))
    db.add(reading)
    await record_activity(reading, db)
    await db.commit()
    await db.refresh(reading)
    return reading


@router.get("/readings", response_model=list[schemas.ReadingRead])
async def independent_readings(
    user: models.User = Depends(auth.require_roles(models.UserRole.ADULTO_INDEPENDIENTE)),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return (
        await db.scalars(
            select(models.ReadingSession)
            .where(
                models.ReadingSession.reader_user_id == user.id,
                models.ReadingSession.child_id.is_(None),
            )
            .order_by(models.ReadingSession.started_at, models.ReadingSession.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()


@router.get("/users/me/progress", response_model=list[schemas.SessionProgress])
async def independent_progress(
    user: models.User = Depends(auth.require_roles(models.UserRole.ADULTO_INDEPENDIENTE)),
    db: AsyncSession = Depends(get_db),
):
    sessions = await independent_readings(user, db, 0, 500)
    return summarize_progress(sessions)


@router.get("/readings/progress", response_model=schemas.EducationalProgress)
async def independent_educational_progress(
    user: models.User = Depends(auth.require_roles(models.UserRole.ADULTO_INDEPENDIENTE)),
    db: AsyncSession = Depends(get_db),
):
    sessions = (
        await db.scalars(
            select(models.ReadingSession)
            .where(
                models.ReadingSession.reader_user_id == user.id,
                models.ReadingSession.child_id.is_(None),
            )
            .order_by(models.ReadingSession.started_at, models.ReadingSession.id)
        )
    ).all()
    activity = await authorized_activity(db, reader_user_id=user.id)
    return summarize(sessions, activity_days=activity)


@router.get("/readings/{reading_id}", response_model=schemas.ReadingRead)
async def get_reading(
    reading_id: uuid.UUID,
    user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    reading = await db.get(models.ReadingSession, reading_id)
    if reading is None:
        raise HTTPException(404, "Sesión no encontrada.")
    await authorize_reading(reading, user, db)
    return reading


@router.patch("/readings/{reading_id}", response_model=schemas.ReadingRead)
async def update_reading(
    reading_id: uuid.UUID,
    payload: schemas.ReadingUpdate,
    user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    reading = await db.get(models.ReadingSession, reading_id, with_for_update=True)
    if reading is None:
        raise HTTPException(404, "Sesión no encontrada.")
    await authorize_reading(reading, user, db)
    if reading.document_id:
        await accessible_document(reading.document_id, user, db)
    before = snapshot(reading)
    data = payload.model_dump(exclude_unset=True)
    if reading.completed and (not data or set(data) - EDUCATIONAL_FIELDS):
        raise HTTPException(409, "La sesión ya está finalizada.")
    elapsed = max(0, (auth.utcnow() - auth.aware(reading.started_at)).total_seconds())
    if "reading_time_seconds" in data and (
        data["reading_time_seconds"] < reading.reading_time_seconds
        or data["reading_time_seconds"] > elapsed + 5
    ):
        raise HTTPException(422, "Tiempo de lectura inválido.")
    if "completion_percent" in data and data["completion_percent"] < float(
        reading.completion_percent
    ):
        raise HTTPException(422, "El progreso no puede retroceder.")
    if data.get("completed") is True:
        if data.get("completion_percent", float(reading.completion_percent)) != 100:
            raise HTTPException(422, "La finalización requiere 100 por ciento de avance.")
        reading.ended_at = auth.utcnow()
    update_practice(reading, data)
    for key, value in data.items():
        if key not in EDUCATIONAL_FIELDS:
            setattr(reading, key, value)
    await record_activity(reading, db, before)
    await db.commit()
    await db.refresh(reading)
    return reading


@router.patch("/children/{child_id}/readings/{reading_id}", response_model=schemas.ReadingRead)
async def update_child_reading(
    child_id: uuid.UUID,
    reading_id: uuid.UUID,
    payload: schemas.ReadingUpdate,
    user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await accessible_child(child_id, user, db)
    reading = await db.scalar(
        select(models.ReadingSession).where(
            models.ReadingSession.id == reading_id,
            models.ReadingSession.child_id == child_id,
        )
    )
    if reading is None:
        raise HTTPException(404, "Sesión no encontrada.")
    return await update_reading(reading_id, payload, user, db)


@router.get("/children/{child_id}/readings", response_model=list[schemas.ReadingRead])
async def readings(
    child_id: uuid.UUID,
    user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await accessible_child(child_id, user, db)
    return (
        await db.scalars(
            select(models.ReadingSession)
            .where(models.ReadingSession.child_id == child_id)
            .order_by(models.ReadingSession.started_at)
            .limit(500)
        )
    ).all()


@router.get(
    "/children/{child_id}/progress",
    response_model=schemas.EducationalProgress,
)
async def progress(
    child_id: uuid.UUID,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    child = await accessible_child(child_id, user, db)
    sessions = (
        await db.scalars(
            select(models.ReadingSession)
            .where(models.ReadingSession.child_id == child_id)
            .order_by(models.ReadingSession.started_at, models.ReadingSession.id)
        )
    ).all()
    activity = await authorized_activity(db, child_id=child_id)
    return summarize(sessions, child.nivel_simplificacion_nlp, activity_days=activity)


@router.get(
    "/profiles/{profile_id}/educational-progress", response_model=schemas.EducationalProgress
)
async def profile_educational_progress(
    profile_id: uuid.UUID,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    return await progress(profile_id, user, db)


@router.get("/children/{child_id}/progress/legacy", response_model=list[schemas.SessionProgress])
async def legacy_progress(
    child_id: uuid.UUID,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    sessions = await readings(child_id, user, db)
    return summarize_progress(sessions)


def summarize_progress(sessions):
    accumulated = 0
    result = []
    for index, session in enumerate(sessions, 1):
        accumulated += session.reading_time_seconds
        result.append(
            schemas.SessionProgress(
                sessionLabel=f"Sesión {index}",
                accumulatedMinutes=accumulated / 60,
                completionPercent=int(session.completion_percent),
            )
        )
    return result


@router.get("/children/{child_id}/library", response_model=list[schemas.DocumentRead])
async def child_library(
    child_id: uuid.UUID,
    user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    child = await accessible_child(child_id, user, db)
    return (
        await db.scalars(
            select(models.Document)
            .join(
                models.ChildLibraryItem, models.ChildLibraryItem.document_id == models.Document.id
            )
            .where(
                models.ChildLibraryItem.child_id == child.id,
                models.Document.owner_id == child.tutor_id,
            )
            .order_by(models.Document.uploaded_at, models.Document.id)
            .limit(500)
        )
    ).all()


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    user: models.User = Depends(
        auth.require_roles(models.UserRole.TUTOR, models.UserRole.ADULTO_INDEPENDIENTE)
    ),
    db: AsyncSession = Depends(get_db),
):
    document = await accessible_document(document_id, user, db)
    await db.delete(document)
    await db.commit()


@router.post(
    "/profiles/{profile_id}/daily-missions/{mission_id}/claim",
    response_model=schemas.EducationalProgress,
)
async def claim_daily_mission(
    profile_id: uuid.UUID,
    mission_id: str,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    result = await progress(profile_id, user, db)
    mission = next((item for item in result.daily_missions if item.id == mission_id), None)
    if mission is None:
        raise HTTPException(404, "Misión no encontrada.")
    if not mission.completed:
        raise HTTPException(409, "La misión aún no está completada.")
    # Rewards are already derived once per mission/day. Claim is an acknowledgement,
    # never a second credit on top of automatic completion rewards.
    return result
