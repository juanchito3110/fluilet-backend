"""Idempotent daily mission evidence and cumulative historical bonuses."""

import hashlib
from collections import defaultdict
from datetime import UTC
from types import SimpleNamespace

from sqlalchemy import select

from app import auth, models

MISSIONS = (
    ("mission_read_lesson", "Explorador del Día: Completa 1 lectura", 25, 1),
    (
        "mission_quiz_master",
        "Mente Brillante: Logra al menos 1 respuesta correcta en un Mini-Reto",
        30,
        1,
    ),
    ("mission_category_variety", "Curiosidad Total: Explora 2 lecturas o temas distintos", 40, 2),
)


def current_day():
    return auth.utcnow().date()


def lesson_key(document_id, category, content_hash=None):
    if content_hash:
        return content_hash
    identity = f"document:{document_id}" if document_id else f"category:{category}"
    return hashlib.sha256(identity.encode()).hexdigest()


def utc_day(value):
    return auth.aware(value).astimezone(UTC).date()


def snapshot(reading):
    return {
        name: getattr(reading, name)
        for name in (
            "completed",
            "reading_time_seconds",
            "completion_percent",
            "questions_correct",
            "questions_answered",
            "comprehension_score",
            "ended_at",
            "started_at",
            "document_id",
            "category",
        )
    }


def _practiced(state):
    return bool(
        state["completed"]
        or state["reading_time_seconds"]
        or state["completion_percent"]
        or state["questions_answered"]
        or state["comprehension_score"] is not None
    )


def inferred_activity(reading, state=None):
    state = state or snapshot(reading)
    if not _practiced(state):
        return None
    return SimpleNamespace(
        reading_id=reading.id,
        activity_date=utc_day(state["ended_at"] or state["started_at"]),
        lesson_key=lesson_key(state["document_id"], state["category"]),
        completed=bool(state["completed"]),
        correct_answer=state["questions_correct"] > 0,
        inferred=True,
    )


async def record_activity(reading, db, before=None):
    current = snapshot(reading)
    if before is None:
        if not _practiced(current):
            return
        completed, correct = reading.completed, reading.questions_correct > 0
    else:
        completed = reading.completed and not before["completed"]
        correct = reading.questions_correct > before["questions_correct"]
        changed = (
            completed
            or correct
            or any(
                current[name] > before[name]
                for name in ("reading_time_seconds", "completion_percent", "questions_answered")
            )
            or (
                current["comprehension_score"] is not None
                and current["comprehension_score"] != before["comprehension_score"]
            )
        )
        if not changed:
            return
    await db.flush()
    content_hash = (
        await db.scalar(
            select(models.Document.content_sha256).where(models.Document.id == reading.document_id)
        )
        if reading.document_id
        else None
    )
    previous = (
        await db.scalars(
            select(models.ReadingActivityDay)
            .where(models.ReadingActivityDay.reading_id == reading.id)
            .order_by(models.ReadingActivityDay.activity_date)
        )
    ).all()
    if before is not None and not previous:
        legacy = inferred_activity(reading, before)
        if legacy:
            legacy.lesson_key = lesson_key(before["document_id"], before["category"], content_hash)
            historical = models.ReadingActivityDay(**vars(legacy))
            db.add(historical)
            previous.append(historical)
    today = current_day()
    event = next((item for item in previous if item.activity_date == today), None)
    key = (
        previous[0].lesson_key
        if previous
        else lesson_key(reading.document_id, reading.category, content_hash)
    )
    if event is None:
        db.add(
            models.ReadingActivityDay(
                reading_id=reading.id,
                activity_date=today,
                lesson_key=key,
                completed=bool(completed),
                correct_answer=correct,
                inferred=False,
            )
        )
    else:
        event.completed |= bool(completed)
        event.correct_answer |= correct
        event.inferred = False


async def authorized_activity(db, *, child_id=None, reader_user_id=None):
    statement = select(models.ReadingActivityDay).join(models.ReadingSession)
    if child_id is not None:
        statement = statement.where(models.ReadingSession.child_id == child_id)
    else:
        statement = statement.where(
            models.ReadingSession.reader_user_id == reader_user_id,
            models.ReadingSession.child_id.is_(None),
        )
    return (await db.scalars(statement)).all()


def mission_summary(sessions, activity_days=None, today=None):
    events = list(activity_days or [])
    recorded = {event.reading_id for event in events}
    for session in sessions:
        if session.id not in recorded:
            legacy = inferred_activity(session)
            if legacy:
                events.append(legacy)
    by_day = defaultdict(list)
    for event in events:
        by_day[event.activity_date].append(event)
    today = today or current_day()

    def progress(day):
        entries = by_day[day]
        return (
            min(1, sum(item.completed for item in entries)),
            min(1, sum(item.correct_answer for item in entries)),
            min(2, len({item.lesson_key for item in entries})),
        )

    # Each mission/day is counted once. GET never writes, and an older day's
    # earned bonus remains part of the total when a new day starts.
    bonus = sum(
        reward
        for day in list(by_day)
        for value, (_, _, reward, target) in zip(progress(day), MISSIONS, strict=True)
        if value >= target
    )
    missions = [
        {
            "id": code,
            "title": title,
            "description": title,
            "reward_gems": reward,
            "progress": value,
            "target": target,
            "completed": value >= target,
            "claimed": value >= target,
        }
        for value, (code, title, reward, target) in zip(progress(today), MISSIONS, strict=True)
    ]
    return {"daily_missions": missions, "mission_bonus_gems": bonus}
