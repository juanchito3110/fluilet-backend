"""Explicit, owner-authorized synthetic history backed by real NLP measurements."""

import uuid
from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth, education, models, schemas
from app.activities import accessible_child, progress, reading_snapshot
from app.adaptations import persist, process
from app.database import get_db
from app.encyclopedia import ARTICLES

router = APIRouter(prefix="/api/v1/profiles", tags=["academic-demo"])
DEMO_KEYS = (
    "real madrid",
    "biologia marina",
    "agujeros negros",
    "antiguo egipto",
    "robots inteligencia artificial",
    "pequeno faro",
)


@router.post("/{profile_id}/seed-demo", response_model=schemas.EducationalProgress)
async def seed_demo(
    profile_id: uuid.UUID,
    user: models.User = Depends(auth.require_roles(models.UserRole.TUTOR)),
    db: AsyncSession = Depends(get_db),
):
    child = await accessible_child(profile_id, user, db)
    age = education.teaching_age(child)
    # No external dependency or client-supplied text. These are authored public
    # lessons. All readability numbers come from the exact source/adapted pair.
    prepared = []
    levels = (1, 2, 3, 3, 4, 4)
    for key, level in zip(DEMO_KEYS, levels, strict=True):
        article = ARTICLES[key]
        result, digest = await process(article.text, None, "text/plain", level, child_age=age)
        prepared.append((article, result, digest, level))
    locked_user = await db.scalar(
        select(models.User)
        .where(models.User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    await auth.validate_identity(locked_user, db)
    await db.scalar(
        select(models.ChildProfile).where(models.ChildProfile.id == profile_id).with_for_update()
    )
    await accessible_child(profile_id, user, db)
    lessons = []
    for article, result, digest, level in prepared:
        lessons.append(
            await persist(
                result,
                digest,
                len(article.text.encode("utf-8")),
                models.DocumentType.TXT,
                profile_id,
                user,
                db,
                category=article.category,
                level=level,
                title=article.title,
                article=article,
                commit=False,
            )
        )
    existing = (
        await db.scalars(
            select(models.ReadingSession).where(
                models.ReadingSession.child_id == profile_id,
                models.ReadingSession.demo_slot.is_not(None),
            )
        )
    ).all()
    by_slot = {item.demo_slot: item for item in existing}
    today = auth.utcnow().date()
    # The first seed fixes the dates. Repeating the endpoint never rolls old
    # sessions forward, changes genuine progress or awards a second cohort.
    anchor = min(
        (auth.aware(item.started_at).date() for item in existing), default=today - timedelta(days=6)
    )
    scores = (65, 75, 80, 85, 90, 100, 100)
    for index, score in enumerate(scores):
        slot = f"academic-v1-{index}"
        if slot in by_slot:
            continue
        lesson = lessons[index % len(lessons)]
        document = await db.get(models.Document, lesson.document.id)
        reading = reading_snapshot(document, child_id=profile_id)
        # All UTC timestamps finish before the request time, including a seed
        # near midnight. The graph gets seven consecutive calendar dates.
        day = anchor + timedelta(days=index)
        end = min(datetime.combine(day, time(12), UTC), auth.utcnow())
        reading.started_at = max(datetime.combine(day, time(), UTC), end - timedelta(seconds=240))
        reading.ended_at = end
        reading.reading_time_seconds = int((end - reading.started_at).total_seconds())
        reading.completion_percent = 100
        reading.completed = True
        reading.comprehension_score = score
        reading.questions_answered = 2 if score == 100 else 0
        reading.questions_correct = 2 if score == 100 else 0
        reading.demo_slot = slot
        # Repeated football lesson on day seven is practiced at level 4.
        # Its snapshot must actually be computed at that level, not relabeled.
        if index == 6:
            article = ARTICLES[DEMO_KEYS[0]]
            actual, _ = await process(article.text, None, "text/plain", 4, child_age=age)
            reading.simplification_level = 4
            for name, value in actual.metrics.items():
                setattr(reading, name, value)
        db.add(reading)
        await db.flush()
        db.add(
            models.ReadingActivityDay(
                reading_id=reading.id,
                activity_date=day,
                lesson_key=document.content_sha256,
                completed=True,
                correct_answer=reading.questions_correct > 0,
                inferred=False,
            )
        )
    await db.commit()
    from app.services.demo_refresh import refresh_marked

    await refresh_marked(db, [profile_id])
    response = await progress(profile_id, user, db)
    response.demo_data = True
    response.demo_lessons = lessons
    return response
