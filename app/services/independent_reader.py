"""Account-backed reader controls share admin contracts, not child identities."""

from types import SimpleNamespace

from sqlalchemy import select

from app import models
from app.daily_missions import authorized_activity
from app.educational_progress import summarize
from app.profile_controls import apply_control


def reader_view(user, control=None):
    return SimpleNamespace(
        id=user.id,
        tutor_id=user.id,
        user_id=user.id,
        name=user.full_name,
        is_active=user.is_active,
        is_account_reader=True,
        age_group_override=(control.age_group_override if control else None) or "12+",
        nivel_simplificacion_nlp=(control.level_override if control else None) or 2,
    )


async def reader_summary(user_id, db, *, apply_adjustments=True):
    sessions = (
        await db.scalars(
            select(models.ReadingSession)
            .where(
                models.ReadingSession.reader_user_id == user_id,
                models.ReadingSession.child_id.is_(None),
            )
            .order_by(models.ReadingSession.started_at, models.ReadingSession.id)
        )
    ).all()
    control = await db.get(models.ReaderControl, user_id)
    activity = await authorized_activity(db, reader_user_id=user_id)
    level = (control.level_override if control else None) or 2
    result = summarize(sessions, level, activity_days=activity)
    result.age_group = (control.age_group_override if control else None) or "12+"
    result.current_level = level
    return apply_control(result, control) if apply_adjustments else result
