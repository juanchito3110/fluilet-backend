"""Master-only, authenticated administration. No email-only privilege escalation."""

import uuid
from collections import Counter, defaultdict
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth, education, models, schemas
from app.database import get_db
from app.educational_progress import summarize
from app.profile_controls import apply_control, profile_summary

router = APIRouter(prefix="/api/v1/admin", tags=["master-admin"])


async def require_master(user: models.User = Depends(auth.get_current_user)):
    if not user.is_master_admin:
        raise HTTPException(403, "Acceso exclusivo del administrador maestro.")
    return user


async def admin_lock(db):
    # Serializes startup/restore/admin mutations across workers. Normal account
    # creation is unaffected. SQLite test databases need no PostgreSQL advisory lock.
    if db.bind.dialect.name == "postgresql":
        await db.execute(select(func.pg_advisory_xact_lock(417830721)))


@router.get("/overview", response_model=schemas.AdminOverview)
async def overview(
    user: models.User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    from app.services.ranker import model_info

    users = (
        await db.scalars(select(models.User).order_by(models.User.created_at, models.User.id))
    ).all()
    children = (
        await db.scalars(
            select(models.ChildProfile).order_by(
                models.ChildProfile.created_at, models.ChildProfile.id
            )
        )
    ).all()
    sessions = (
        await db.scalars(
            select(models.ReadingSession).order_by(
                models.ReadingSession.started_at, models.ReadingSession.id
            )
        )
    ).all()
    events = (await db.scalars(select(models.ReadingActivityDay))).all()
    controls = {
        row.child_id: row for row in (await db.scalars(select(models.ProfileControl))).all()
    }
    owners = {item.id: item for item in users}
    counts = Counter(child.tutor_id for child in children)
    by_child, by_reading = defaultdict(list), defaultdict(list)
    for session in sessions:
        by_child[session.child_id].append(session)
    for event in events:
        by_reading[event.reading_id].append(event)
    profiles = []
    for child in children:
        history = by_child[child.id]
        activity = [event for session in history for event in by_reading[session.id]]
        result = apply_control(
            summarize(history, child.nivel_simplificacion_nlp, activity), controls.get(child.id)
        )
        profiles.append(
            schemas.AdminProfile(
                profile_id=child.id,
                name=child.name,
                tutor_id=child.tutor_id,
                tutor_email=owners[child.tutor_id].email,
                is_active=child.is_active,
                age_group=education.profile_age_group(child),
                current_level=child.nivel_simplificacion_nlp,
                total_gems=result.total_gems,
                total_xp=result.total_xp,
                evolution_stage=result.mascot.stage,
                evolution_title=result.mascot.stage_name,
                current_streak_days=result.current_streak_days,
                completed_lessons_count=result.completed_lessons,
                unlocked_badges_count=sum(item.unlocked for item in result.badges),
            )
        )
    scores = [row.comprehension_score for row in sessions if row.comprehension_score is not None]
    return schemas.AdminOverview(
        model_info=model_info(),
        total_tutors=sum(item.role == models.UserRole.TUTOR for item in users),
        total_profiles=len(children),
        total_adaptations=await db.scalar(
            select(func.count()).select_from(models.AdaptationContent)
        ),
        total_reading_sessions=len(sessions),
        average_comprehension=mean(scores) if scores else 0.0,
        users=[
            schemas.AdminUser(
                user_id=row.id,
                email=row.email,
                role=row.role,
                is_master_admin=row.is_master_admin,
                is_active=row.is_active,
                profiles_count=counts[row.id],
                created_at=row.created_at,
            )
            for row in users
        ],
        profiles=profiles,
    )


async def lock_profile(profile_id, db):
    child = await db.get(models.ChildProfile, profile_id)
    if child is None:
        raise HTTPException(404, "Perfil no encontrado.")
    await db.scalar(select(models.User).where(models.User.id == child.tutor_id).with_for_update())
    return await db.scalar(
        select(models.ChildProfile)
        .where(models.ChildProfile.id == profile_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


@router.post("/profiles/{profile_id}/grant", response_model=schemas.EducationalProgress)
async def grant(
    profile_id: uuid.UUID,
    payload: schemas.MasterGrant,
    user: models.User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    await admin_lock(db)
    child = await lock_profile(profile_id, db)
    current = await profile_summary(child, db)
    base = await profile_summary(child, db, apply_adjustments=False)
    control = await db.get(models.ProfileControl, child.id)
    if control is None:
        control = models.ProfileControl(
            child_id=child.id, gems_offset=0, xp_offset=0, unlock_all_rewards=False
        )
        db.add(control)
    gems = (
        payload.set_gems if payload.set_gems is not None else current.total_gems + payload.add_gems
    )
    xp = current.total_xp + payload.add_xp
    if payload.set_evolution_stage is not None:
        xp = (0, 150, 350, 700)[payload.set_evolution_stage - 1]
        if payload.set_gems is None and not payload.add_gems:
            gems = max(gems, (0, 150, 300, 700)[payload.set_evolution_stage - 1])
    if payload.unlock_all_rewards and not control.unlock_all_rewards:
        if payload.set_gems is None:
            gems += 95
        xp = max(700, xp)
        control.unlock_all_rewards = True
    if not (0 <= gems <= 1000000000 and 0 <= xp <= 1000000000):
        raise HTTPException(422, "El saldo resultante debe estar entre 0 y 1000000000.")
    control.gems_offset = gems - base.total_gems
    control.xp_offset = xp - base.total_xp
    if payload.set_level is not None:
        control.level_override = child.nivel_simplificacion_nlp = payload.set_level
    if payload.set_age_group is not None:
        child.age_group_override = payload.set_age_group
    if payload.set_streak_days is not None:
        control.streak_override = payload.set_streak_days
    await db.commit()
    return await profile_summary(child, db)


async def delete_profile(child, db):
    linked_account = child.user_id
    doc_ids = select(models.ChildLibraryItem.document_id).where(
        models.ChildLibraryItem.child_id == child.id
    )
    candidates = list((await db.scalars(doc_ids)).all())
    await db.execute(delete(models.ChildProfile).where(models.ChildProfile.id == child.id))
    if linked_account:
        await db.execute(
            delete(models.User).where(
                models.User.id == linked_account, models.User.role == models.UserRole.NINO
            )
        )
    if candidates:
        await db.execute(
            delete(models.Document).where(
                models.Document.id.in_(candidates),
                ~select(models.ChildLibraryItem.id)
                .where(models.ChildLibraryItem.document_id == models.Document.id)
                .exists(),
                ~select(models.AdaptationContent.id)
                .where(models.AdaptationContent.document_id == models.Document.id)
                .exists(),
                ~select(models.ReadingSession.id)
                .where(models.ReadingSession.document_id == models.Document.id)
                .exists(),
            )
        )


@router.delete("/profiles/{profile_id}", status_code=204)
async def remove_profile(
    profile_id: uuid.UUID,
    user: models.User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    await admin_lock(db)
    child = await lock_profile(profile_id, db)
    await delete_profile(child, db)
    await db.commit()
    return Response(status_code=204)


@router.delete("/tutors/{user_id}", status_code=204)
async def remove_user(
    user_id: uuid.UUID,
    user: models.User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    await admin_lock(db)
    target = await db.scalar(select(models.User).where(models.User.id == user_id).with_for_update())
    if target is None:
        raise HTTPException(404, "Usuario no encontrado.")
    if target.is_master_admin:
        raise HTTPException(400, "La cuenta maestra no puede eliminarse.")
    linked = (
        await db.scalars(
            select(models.ChildProfile.user_id).where(
                models.ChildProfile.tutor_id == user_id, models.ChildProfile.user_id.is_not(None)
            )
        )
    ).all()
    await db.execute(delete(models.User).where(models.User.id == user_id))
    if linked:
        await db.execute(
            delete(models.User).where(
                models.User.id.in_(linked), models.User.role == models.UserRole.NINO
            )
        )
    await db.commit()
    return Response(status_code=204)


@router.post("/tutors/{user_id}/reset-pin")
async def reset_pin(
    user_id: uuid.UUID,
    payload: schemas.ResetParentalPin | None = None,
    user: models.User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    await admin_lock(db)
    target = await db.scalar(select(models.User).where(models.User.id == user_id).with_for_update())
    if target is None:
        raise HTTPException(404, "Usuario no encontrado.")
    target.parental_pin_hash = await auth.hash_async(payload.pin if payload else "1234")
    await db.commit()
    return {"user_id": str(target.id), "pin_reset": True}


@router.post("/ensure-demo-accounts", response_model=schemas.AdminOverview)
async def ensure_demo_accounts(
    user: models.User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    from app.demo_accounts import ensure_accounts

    await ensure_accounts(db)
    return await overview(user, db)
