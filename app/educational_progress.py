"""Owner-scoped educational metrics; recommendations are practice suggestions."""

from datetime import UTC, timedelta
from statistics import mean

from fastapi import HTTPException

from app import auth, schemas
from app.daily_missions import mission_summary
from app.gamification import progress_rewards

EDUCATIONAL_FIELDS = frozenset(
    {
        "category",
        "simplification_level",
        "comprehension_score",
        "questions_answered",
        "questions_correct",
        "tts_speed_used",
    }
)
BADGES = (
    ("primera_leccion", "Primera Lección", "Completaste tu primera lectura al 100 %."),
    ("mente_brillante", "Mente Brillante", "Obtuviste 100 % en un reto de comprensión."),
    ("habito_en_marcha", "Hábito en Marcha", "Completaste 3 o más lecciones de principio a fin."),
    (
        "explorador_curioso",
        "Explorador Curioso",
        "Practicaste lecturas de al menos 2 categorías distintas.",
    ),
    ("subiendo_nivel", "Subiendo de Nivel", "Completaste una lección en nivel 3 o superior."),
)


def update_practice(reading, data):
    """Validate the merged snapshot, not just fields in this PATCH/POST."""
    updates = {name: value for name, value in data.items() if name in EDUCATIONAL_FIELDS}
    answered = updates.get("questions_answered", reading.questions_answered or 0)
    correct = updates.get("questions_correct", reading.questions_correct or 0)
    if correct > answered:
        raise HTTPException(422, "Las respuestas correctas no pueden superar las contestadas.")
    if answered:
        computed = (200 * correct + answered) // (2 * answered)
        if "comprehension_score" in updates and updates["comprehension_score"] != computed:
            raise HTTPException(422, "El puntaje no coincide con las respuestas registradas.")
        updates["comprehension_score"] = computed
    elif "questions_answered" in updates or "questions_correct" in updates:
        # No answers means no measured score, rather than a fictitious zero.
        if updates.get("comprehension_score") is not None:
            raise HTTPException(422, "No hay respuestas para calcular ese puntaje.")
        updates["comprehension_score"] = None
    for name, value in updates.items():
        setattr(reading, name, value)
    return updates


def summarize(sessions, baseline=2, activity_days=None):
    missions = mission_summary(sessions, activity_days)
    finished = [session for session in sessions if session.completed]
    scores = [
        session.comprehension_score
        for session in sessions
        if session.comprehension_score is not None
    ]
    recent = finished[-3:]
    recommended = baseline
    if recent:
        recommended = recent[-1].simplification_level
        if all(
            (session.comprehension_score is not None and session.comprehension_score >= 50)
            or float(session.completion_percent) == 100
            for session in recent
        ):
            recommended = min(5, recommended + 1)
    practiced = {
        session.category
        for session in sessions
        if session.reading_time_seconds > 0
        or float(session.completion_percent) > 0
        or session.questions_answered > 0
    }
    unlocked = (
        bool(finished),
        any(score == 100 for score in scores),
        len(finished) >= 3,
        len(practiced) >= 2,
        any(session.simplification_level >= 3 for session in finished),
    )
    return schemas.EducationalProgress(
        current_streak_days=current_streak(sessions),
        demo_data=any(getattr(item, "demo_slot", None) for item in sessions),
        total_lessons=len(sessions),
        completed_lessons=len(finished),
        incomplete_lessons=len(sessions) - len(finished),
        completion_rate_percent=100.0 * len(finished) / len(sessions) if sessions else 0.0,
        total_reading_seconds=sum(session.reading_time_seconds for session in sessions),
        average_comprehension_score=mean(scores) if scores else 0.0,
        current_recommended_level=max(1, min(5, recommended)),
        level_progression=[
            schemas.LessonProgress(
                is_demo=bool(getattr(session, "demo_slot", None)),
                document_id=session.document_id,
                lesson_number=index,
                reading_id=str(session.id),
                recorded_at=auth.aware(session.started_at).astimezone(UTC).isoformat(),
                category=session.category,
                simplification_level=session.simplification_level,
                completed=session.completed,
                completion_percentage=int(session.completion_percent),
                comprehension_score=session.comprehension_score,
                duration_seconds=session.reading_time_seconds,
                original_readability_score=session.original_szigriszt_score,
                adapted_readability_score=session.adapted_szigriszt_score,
            )
            for index, session in enumerate(sessions, 1)
        ],
        badges=[
            schemas.EducationalBadge(
                code=code, title=title, description=description, unlocked=earned
            )
            for (code, title, description), earned in zip(BADGES, unlocked, strict=True)
        ],
        daily_missions=missions["daily_missions"],
        **progress_rewards(sessions, max(1, min(5, recommended)), missions["mission_bonus_gems"]),
    )


def current_streak(sessions):
    days = {
        auth.aware(item.ended_at or item.started_at).astimezone(UTC).date()
        for item in sessions
        if item.completed
    }
    day = auth.utcnow().date()
    if day not in days:
        day -= timedelta(days=1)
    result = 0
    while day in days:
        result += 1
        day -= timedelta(days=1)
    return result
