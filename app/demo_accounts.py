"""Idempotent academic identities; never reset manually created users or profiles."""

import hashlib
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select

from app import auth, education, models
from app.activities import reading_snapshot
from app.adaptations import persist
from app.admin import admin_lock
from app.encyclopedia import ARTICLES
from app.nlp.mt5 import ModelUnavailable
from app.nlp.pipeline import AdaptationPipeline
from app.profile_controls import profile_summary

TUTOR_EMAIL = "tutor@fluilet.com"
MASTER_EMAIL = "admin@fluilet.com"
RESERVED_EMAILS = frozenset({TUTOR_EMAIL, MASTER_EMAIL})
# Intentionally public academic credentials requested by the owner, not production secrets.
TUTOR_PASSWORD = "Tutor2026!"
MASTER_PASSWORD = "Master2026!"
DEMO_PIN = "1234"
PRESETS = (
    ("sofia", "Sofía", 7, 1, 45, 40, 1, ("luna",), (0,), False),
    (
        "mateo",
        "Mateo",
        10,
        2,
        160,
        190,
        3,
        ("biologia marina", "futbol", "robots"),
        (2, 1, 0),
        False,
    ),
    (
        "diego",
        "Diego",
        11,
        4,
        340,
        460,
        6,
        ("real madrid", "agujeros negros", "antiguo egipto", "robots", "biologia marina"),
        (5, 4, 3, 1, 0),
        False,
    ),
    (
        "valentina",
        "Valentina",
        13,
        5,
        900,
        980,
        12,
        (
            "real madrid",
            "biologia marina",
            "agujeros negros",
            "antiguo egipto",
            "robots inteligencia artificial",
            "pequeno faro",
        ),
        (6, 5, 4, 2, 1, 0),
        True,
    ),
)


class RulesOnly:
    async def prepare(self):
        raise ModelUnavailable()


async def _identity(db, email, password, marker, name, role):
    user = await db.scalar(select(models.User).where(models.User.email == email).with_for_update())
    if user is not None and (user.demo_identity != marker or user.role != role):
        # An existing unmarked account must never be silently converted to master.
        raise RuntimeError("Reserved demo identity conflicts with an existing account")
    if user is None:
        user = models.User(
            email=email,
            hashed_password=await auth.hash_async(password),
            full_name=name,
            role=role,
            demo_identity=marker,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()
    else:
        changed = not await auth.verify_async(password, user.hashed_password)
        if changed:
            user.hashed_password = await auth.hash_async(password)
        if changed or not user.is_active:
            await auth.revoke_all(user, db)
        user.is_active, user.failed_login_attempts, user.locked_until = True, 0, None
    return user


async def ensure_accounts(db):
    await admin_lock(db)
    await _identity(
        db,
        MASTER_EMAIL,
        MASTER_PASSWORD,
        "master_admin",
        "Administrador Maestro",
        models.UserRole.MASTER_ADMIN,
    )
    tutor = await _identity(
        db,
        TUTOR_EMAIL,
        TUTOR_PASSWORD,
        "multi_phase_tutor",
        "Tutor de Demostración",
        models.UserRole.TUTOR,
    )
    if not tutor.parental_pin_hash or not await auth.verify_async(
        DEMO_PIN, tutor.parental_pin_hash
    ):
        tutor.parental_pin_hash = await auth.hash_async(DEMO_PIN)
    pipeline = AdaptationPipeline(RulesOnly())
    today = auth.utcnow().date()
    managed_ids = []
    for code, name, age, level, gems, xp, streak, keys, days, unlock in PRESETS:
        child = await db.scalar(
            select(models.ChildProfile)
            .where(
                models.ChildProfile.tutor_id == tutor.id,
                models.ChildProfile.demo_identity == code,
            )
            .with_for_update()
        )
        if child is None:
            birthday = date(today.year - age, 1, 1)
            child = models.ChildProfile(
                tutor_id=tutor.id,
                name=name,
                birth_date=birthday,
                tipo_dificultad=models.DifficultyType.DISLEXIA,
                nivel_simplificacion_nlp=level,
                demo_identity=code,
                is_active=True,
            )
            db.add(child)
            await db.flush()
        child.is_active = True
        managed_ids.append(child.id)
        control = await db.get(models.ProfileControl, child.id)
        existing = (
            await db.scalars(
                select(models.ReadingSession).where(models.ReadingSession.child_id == child.id)
            )
        ).all()
        slots = {item.demo_slot for item in existing}
        anchor = max(
            (
                auth.aware(item.ended_at or item.started_at).date()
                for item in existing
                if item.demo_slot and item.demo_slot.startswith("accounts-v1-")
            ),
            default=today,
        )
        for index, (key, offset) in enumerate(zip(keys, days, strict=True)):
            slot = f"accounts-v1-{code}-{index}"
            if slot in slots:
                continue
            article = ARTICLES[key]
            result = await pipeline.run(
                article.text,
                child.nivel_simplificacion_nlp,
                child_age=education.teaching_age(child),
            )
            digest = hashlib.sha256(result.original_text.encode()).hexdigest()
            lesson = await persist(
                result,
                digest,
                len(article.text.encode()),
                models.DocumentType.TXT,
                child.id,
                tutor,
                db,
                category=article.category,
                level=child.nivel_simplificacion_nlp,
                title=article.title,
                article=article,
                commit=False,
            )
            document = await db.get(models.Document, lesson.document.id)
            reading = reading_snapshot(document, child_id=child.id)
            day = anchor - timedelta(days=offset)
            end = min(datetime.combine(day, time(12), UTC), auth.utcnow())
            start = max(datetime.combine(day, time(), UTC), end - timedelta(seconds=180))
            reading.started_at, reading.ended_at = start, end
            reading.reading_time_seconds = int((end - start).total_seconds())
            reading.completed, reading.completion_percent, reading.demo_slot = True, 100, slot
            reading.comprehension_score = (
                95
                if code == "valentina"
                else (100 if code == "diego" and offset == 0 else min(95, 65 + index * 10))
            )
            if code == "diego" and offset == 0:
                reading.questions_answered = reading.questions_correct = 2
            db.add(reading)
            await db.flush()
            db.add(
                models.ReadingActivityDay(
                    reading_id=reading.id,
                    activity_date=day,
                    lesson_key=digest,
                    completed=True,
                    correct_answer=reading.questions_correct > 0,
                    inferred=False,
                )
            )
        await db.flush()
        if control is None:
            base = await profile_summary(child, db)
            # Requested phases conflict with normal per-completion XP/streak math.
            # Store a transparent resource adjustment, never forge text metrics.
            control = models.ProfileControl(
                child_id=child.id,
                gems_offset=gems - base.total_gems,
                xp_offset=xp - base.total_xp,
                level_override=level,
                streak_override=streak,
                unlock_all_rewards=unlock,
            )
            db.add(control)
    await db.commit()
    from app.services.demo_refresh import refresh_marked

    await refresh_marked(db, managed_ids)
