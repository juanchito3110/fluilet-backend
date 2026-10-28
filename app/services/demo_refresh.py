"""Upgrade only explicitly marked academic readings, preserving practice/rewards."""

import hashlib

from sqlalchemy import delete, select

from app import education, models
from app.adaptations import persist
from app.encyclopedia import ARTICLES
from app.nlp.mt5 import ModelUnavailable
from app.nlp.pipeline import AdaptationPipeline
from app.services.pedagogy import VERSION


class Offline:
    async def prepare(self):
        raise ModelUnavailable()


async def refreshed_lesson(db, tutor, child, key, level, previous=None):
    article = ARTICLES[key]
    result = await AdaptationPipeline(Offline()).run(
        article.text, level, child_age=education.teaching_age(child)
    )
    response = await persist(
        result,
        hashlib.sha256(result.original_text.encode()).hexdigest(),
        len(article.text.encode()),
        models.DocumentType.TXT,
        child.id,
        tutor,
        db,
        category=article.category,
        level=level,
        title=article.title,
        article=article,
        commit=False,
    )
    if previous is not None and previous.id != response.id:
        # Keep stable adaptation UUIDs when a public reference revision changes hash.
        new = await db.get(models.AdaptationContent, response.id)
        values = {
            name: getattr(new, name)
            for name in (
                "document_id",
                "context_key",
                "target_level",
                "age_group",
                "original_text",
                "adapted_text",
                "response_payload",
                "updated_at",
            )
        }
        await db.delete(new)
        await db.flush()
        response.id = previous.id
        values["response_payload"] = response.model_dump(
            mode="json", exclude={"original_text", "adapted_text"}
        )
        for name, value in values.items():
            setattr(previous, name, value)
        await db.flush()
    return response, result


async def refresh_marked(db, profile_ids=None, *, force=False):
    """Only marked public demo readings; practice, dates and rewards stay intact."""
    import asyncio

    from app.academic_demo import DEMO_KEYS
    from app.admin import admin_lock
    from app.demo_accounts import PRESETS
    from app.nlp.readability import measure, telemetry
    from app.services.ranker import checkpoint

    await admin_lock(db)
    by_code = {row[0]: row[7] for row in PRESETS}
    artifact = checkpoint()
    model_version = artifact["model_version"] if artifact else "unavailable"
    statement = select(models.ReadingSession).where(models.ReadingSession.demo_slot.is_not(None))
    if profile_ids is not None:
        statement = statement.where(models.ReadingSession.child_id.in_(profile_ids))
    readings = (
        await db.scalars(
            statement.order_by(models.ReadingSession.child_id, models.ReadingSession.started_at)
        )
    ).all()
    changed = 0
    for reading in readings:
        child = await db.get(models.ChildProfile, reading.child_id)
        tutor = await db.get(models.User, child.tutor_id)
        if not child.is_active or not tutor.is_active:
            continue
        slot = reading.demo_slot
        if slot.startswith("academic-v1-"):
            index = int(slot.rsplit("-", 1)[-1])
            key = DEMO_KEYS[index % len(DEMO_KEYS)]
        elif slot.startswith("accounts-v1-") and child.demo_identity in by_code:
            index = int(slot.rsplit("-", 1)[-1])
            key = by_code[child.demo_identity][index]
        else:
            continue
        old_doc = reading.document_id
        source = ARTICLES[key].text
        digest = hashlib.sha256(source.encode()).hexdigest()
        candidates = (
            await db.scalars(
                select(models.AdaptationContent)
                .join(models.Document)
                .where(
                    models.AdaptationContent.child_id == child.id,
                    models.Document.content_sha256 == digest,
                )
            )
        ).all()
        current = next(
            (
                row
                for row in candidates
                if row.response_payload.get("engine_version") == VERSION
                and row.response_payload.get("model_version") == model_version
            ),
            None,
        )
        if current is None or force:
            previous = await db.scalar(
                select(models.AdaptationContent).where(
                    models.AdaptationContent.document_id == old_doc,
                    models.AdaptationContent.child_id == child.id,
                    models.AdaptationContent.target_level == reading.simplification_level,
                )
            )
            # A second practice day may use level 4 of the same stored lesson
            # whose main reading is level 1. Refresh its existing five previews
            # without inventing a seventh lesson/version in the demo library.
            previous = previous or current
            lesson_level = (
                previous.target_level if previous is not None else reading.simplification_level
            )
            response, _ = await refreshed_lesson(db, tutor, child, key, lesson_level, previous)
            current = await db.get(models.AdaptationContent, response.id)
        preview = next(
            row
            for row in current.response_payload["level_previews"]
            if row["level"] == reading.simplification_level
        )
        original = await asyncio.to_thread(measure, current.original_text)
        adapted = await asyncio.to_thread(measure, preview["adapted_text"])
        metrics = telemetry(original, adapted)
        needs_update = reading.document_id != current.document_id or any(
            getattr(reading, name) != value for name, value in metrics.items()
        )
        if not needs_update:
            continue
        reading.document_id = current.document_id
        for name, value in metrics.items():
            setattr(reading, name, value)
        changed += 1
        await db.flush()
        if old_doc and old_doc != reading.document_id:
            other = await db.scalar(
                select(models.ReadingSession.id).where(
                    models.ReadingSession.child_id == child.id,
                    models.ReadingSession.document_id == old_doc,
                )
            )
            if other is None:
                await db.execute(
                    delete(models.ChildLibraryItem).where(
                        models.ChildLibraryItem.child_id == child.id,
                        models.ChildLibraryItem.document_id == old_doc,
                    )
                )
    await db.commit()
    return changed
