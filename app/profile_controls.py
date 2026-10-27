"""Persisted, explicit master adjustments layered over truthful reading history."""

from sqlalchemy import select

from app import education, models
from app.daily_missions import authorized_activity
from app.educational_progress import summarize
from app.gamification import evolution


def apply_control(result, control):
    if control is None:
        return result
    result.has_admin_adjustments = True
    result.total_gems = max(0, result.total_gems + control.gems_offset)
    result.total_stars = result.total_gems
    result.total_xp = max(0, result.total_xp + control.xp_offset)
    state = evolution(result.total_xp)
    result.current_rank_title = state["current_rank_title"]
    result.next_rank_stars = state["next_rank_stars"]
    result.mascot = type(result.mascot).model_validate(state["mascot"])
    if control.level_override is not None:
        result.current_recommended_level = control.level_override
        result.pedagogical_summary.recommendation = f"Para la próxima sesión, usa el nivel {control.level_override} indicado por el tutor o administrador. Lee con calma."
    if control.streak_override is not None:
        result.current_streak_days = result.streak_days = control.streak_override
    for item in result.shop_catalog:
        item.unlocked = result.total_gems >= item.cost_gems
    if control.unlock_all_rewards:
        for card in result.collectible_cards:
            card.unlocked, card.rarity = True, "Oro"
        for badge in result.badges:
            badge.unlocked = True
        for mission in result.daily_missions:
            mission.progress = mission.target
            mission.completed = mission.claimed = True
    return result


async def profile_summary(child, db, *, apply_adjustments=True):
    sessions = (
        await db.scalars(
            select(models.ReadingSession)
            .where(models.ReadingSession.child_id == child.id)
            .order_by(models.ReadingSession.started_at, models.ReadingSession.id)
        )
    ).all()
    activity = await authorized_activity(db, child_id=child.id)
    control = await db.get(models.ProfileControl, child.id)
    result = summarize(sessions, child.nivel_simplificacion_nlp, activity_days=activity)
    result.age_group = education.profile_age_group(child)
    result.current_level = child.nivel_simplificacion_nlp
    return apply_control(result, control) if apply_adjustments else result
