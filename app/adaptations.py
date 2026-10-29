"""Authenticated adaptation and owner-scoped, explicitly authorized lesson retrieval."""

import asyncio
import hashlib
import uuid
from dataclasses import replace
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth, education, models, schemas, vocabulary
from app.activities import accessible_child, accessible_document
from app.config import settings
from app.database import get_db
from app.ingestion import IngestionError, clean_text, extract_safely, read_stream
from app.lesson_sources import (
    SourceUnavailable,
    lesson_excerpt,
    local_article,
    resolve_lesson,
    resolve_topic,
)
from app.nlp.pipeline import original_result, pipeline
from app.nlp.validation import InvalidText, TextTooLarge, validate_text

router = APIRouter(prefix="/api/v1/adaptations", tags=["adaptations"])
_slots = asyncio.Semaphore(settings.PROCESSING_CONCURRENCY)
_adults = auth.require_roles(models.UserRole.TUTOR, models.UserRole.ADULTO_INDEPENDIENTE)


def request_group(payload):
    if payload.age_group is not None:
        return payload.age_group
    explicit = {"level", "target_level", "nivel_simplificacion_nlp", "simplification_level"}
    if payload.child_id is None and payload.model_fields_set & explicit:
        level = getattr(
            payload, "simplification_level", getattr(payload, "nivel_simplificacion_nlp", 3)
        )
        return {1: "6-8", 2: "6-8", 3: "9-11", 4: "9-11", 5: "12+"}[level]
    return None


@router.get("/model-info")
async def model_information(user: models.User = Depends(auth.get_current_user)):
    from app.services.ranker import model_info

    return await asyncio.to_thread(model_info)


_FILE_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/pdf": {"schema": {"type": "string", "format": "binary"}},
            "text/plain": {"schema": {"type": "string", "format": "binary"}},
        },
    }
}


async def process(
    text: str | None,
    data: bytes | None,
    media_type: str,
    level: int,
    *,
    child_age=None,
    allow_local_excerpt=False,
):
    if _slots.locked():
        raise HTTPException(
            503, "Procesamiento ocupado. Intenta más tarde.", headers={"Retry-After": "5"}
        )
    async with _slots:
        try:
            source = (
                await asyncio.to_thread(clean_text, text)
                if text is not None
                else await extract_safely(data, media_type)
            )
            await asyncio.to_thread(validate_text, source)
        except TextTooLarge:
            raise HTTPException(413, "El documento supera el límite permitido.") from None
        except (InvalidText, IngestionError):
            raise HTTPException(422, "El documento no contiene texto válido.") from None
        try:
            async with asyncio.timeout(settings.PROCESSING_TIMEOUT_SECONDS):
                options = {"child_age": child_age} if child_age is not None else {}
                if allow_local_excerpt:
                    options["allow_local_excerpt"] = True
                result = await pipeline.run(source, level, **options)
        except TimeoutError:
            result = await asyncio.to_thread(original_result, source, "processing_budget_exceeded")
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return result, digest


async def persist(
    result,
    digest,
    file_size,
    file_type,
    child_id,
    user,
    db,
    *,
    category="lectura_libre",
    level=3,
    title=None,
    article=None,
    age_group=None,
    commit=True,
):
    # Serialize metadata upserts per owner, independently of inference execution.
    locked_user = await db.scalar(
        select(models.User)
        .where(models.User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    await auth.validate_identity(locked_user, db)
    child_age = None
    profile_age = None
    if child_id is not None:
        child = await accessible_child(child_id, user, db)
        child_age = education.age_years(child.birth_date)
        profile_age = education.teaching_age(child)
    effective_age = {"6-8": 7, "9-11": 10, "12+": 12}.get(age_group, profile_age)
    practice = await asyncio.to_thread(education.questions, result.adapted_text, effective_age)
    fact, terms = await asyncio.to_thread(
        vocabulary.enrich, result.adapted_text, article.fact_hint if article else ""
    )
    document = await db.scalar(
        select(models.Document).where(
            models.Document.owner_id == user.id, models.Document.content_sha256 == digest
        )
    )
    if document is None:
        document = models.Document(
            owner_id=user.id,
            content_sha256=digest,
            file_type=file_type,
            file_size_bytes=file_size,
            status=models.DocumentStatus.COMPLETED,
        )
        db.add(document)
        await db.flush()
    else:
        await db.execute(
            delete(models.AdaptationChunk).where(models.AdaptationChunk.document_id == document.id)
        )
    document.word_count = result.metrics["original_word_count"]
    document.chunk_count = len(result.chunks)
    document.adaptation_method = result.method
    document.category = category
    document.simplification_level = level
    for key, value in result.metrics.items():
        setattr(document, key, value)
    for chunk in result.chunks:
        db.add(models.AdaptationChunk(document_id=document.id, **chunk))
    if child_id:
        existing = await db.scalar(
            select(models.ChildLibraryItem).where(
                models.ChildLibraryItem.child_id == child_id,
                models.ChildLibraryItem.document_id == document.id,
            )
        )
        if existing is None:
            db.add(models.ChildLibraryItem(child_id=child_id, document_id=document.id))
    await db.flush()
    await db.refresh(document)
    metrics = result.metrics
    group = education.question_age_group(effective_age)
    context = hashlib.sha256(f"{document.id}:{child_id}:{level}:{group}".encode()).hexdigest()
    content = await db.scalar(
        select(models.AdaptationContent).where(models.AdaptationContent.context_key == context)
    )
    if content is None:
        content = models.AdaptationContent(
            id=uuid.uuid4(),
            document_id=document.id,
            child_id=child_id,
            context_key=context,
            target_level=level,
            age_group=group,
        )
        db.add(content)
    response = schemas.AdaptationRead(
        readability_gain=metrics["score_delta"],
        original_avg_sentence_length=metrics["original_word_count"]
        / metrics["original_sentence_count"],
        adapted_avg_sentence_length=metrics["adapted_word_count"] / metrics["sentence_count"],
        original_syllables_per_word=metrics["original_syllable_count"]
        / metrics["original_word_count"],
        adapted_syllables_per_word=metrics["syllable_count"] / metrics["adapted_word_count"],
        lexical_replacements=result.lexical_replacements,
        level_previews=result.level_previews,
        level_progression_met=result.level_progression_met,
        removed_fragments=result.removed_fragments,
        engine_version=result.engine_version,
        model_version=result.model_version,
        checkpoint_name=result.checkpoint_name,
        id=content.id,
        original_text=result.original_text,
        original_readability_score=metrics["original_szigriszt_score"],
        readability_score=metrics["adapted_szigriszt_score"],
        metrics=schemas.ComparisonMetrics(
            original_szigriszt_pazos=metrics["original_szigriszt_score"],
            adapted_szigriszt_pazos=metrics["adapted_szigriszt_score"],
            score_delta=metrics["score_delta"],
            original_word_count=metrics["original_word_count"],
            adapted_word_count=metrics["adapted_word_count"],
            original_sentence_count=metrics["original_sentence_count"],
            adapted_sentence_count=metrics["sentence_count"],
            original_average_words_per_sentence=metrics["original_word_count"]
            / metrics["original_sentence_count"],
            adapted_average_words_per_sentence=metrics["adapted_word_count"]
            / metrics["sentence_count"],
        ),
        target_level=level,
        age_group=education.question_age_group(effective_age),
        document=schemas.DocumentRead.model_validate(document),
        adapted_text=result.adapted_text,
        chunks=result.chunks,
        meets_readability_target=result.meets_readability_target,
        quality_status=result.quality_status,
        warnings=result.warnings
        + ([] if result.meets_readability_target else ["readability_target_not_met"]),
        title=title or education.title_for(result.adapted_text),
        category=category,
        simplification_level=level,
        comprehension_questions=practice,
        question_age_group=education.question_age_group(effective_age),
        child_age_years=child_age,
        fun_fact=fact,
        key_vocabulary=terms,
        resolved_topic=article.title if article else None,
        source=schemas.LessonSource(
            provider=article.provider,
            title=article.title,
            url=article.url,
            license="CC BY-SA 4.0" if article.provider == "wikipedia" else None,
            license_url="https://creativecommons.org/licenses/by-sa/4.0/"
            if article.provider == "wikipedia"
            else None,
            revision_id=article.revision_id,
        )
        if article
        else None,
    )
    content.updated_at = auth.utcnow()
    content.original_text = response.original_text
    content.adapted_text = response.adapted_text
    content.response_payload = response.model_dump(
        mode="json", exclude={"original_text", "adapted_text"}
    )
    if commit:
        await db.commit()
    else:
        await db.flush()
    return response


@router.post("", response_model=schemas.AdaptationRead)
@router.post("/text", response_model=schemas.AdaptationRead)
async def adapt_text(
    payload: schemas.AdaptTextRequest,
    user: models.User = Depends(_adults),
    db: AsyncSession = Depends(get_db),
):
    group = request_group(payload)
    child_age = {"6-8": 7, "9-11": 10, "12+": 12}.get(group)
    if payload.child_id:
        child = await accessible_child(payload.child_id, user, db)
        if payload.age_group is None:
            child_age = education.teaching_age(child)
    result, digest = await process(
        payload.text, None, "text/plain", payload.nivel_simplificacion_nlp, child_age=child_age
    )
    return await persist(
        result,
        digest,
        len(payload.text.encode("utf-8")),
        models.DocumentType.TXT,
        payload.child_id,
        user,
        db,
        level=payload.nivel_simplificacion_nlp,
        age_group=group,
    )


@router.post("/document", response_model=schemas.AdaptationRead, openapi_extra=_FILE_BODY)
@router.post(
    "/file",
    response_model=schemas.AdaptationRead,
    openapi_extra=_FILE_BODY,
)
async def adapt_file(
    request: Request,
    nivel_simplificacion_nlp: str | None = Query(default=None),
    target_level: str | None = None,
    level: str | None = None,
    age_group: Literal["6-8", "9-11", "12+"] | None = None,
    child_id: uuid.UUID | None = None,
    user: models.User = Depends(_adults),
    db: AsyncSession = Depends(get_db),
):
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type not in {"text/plain", "application/pdf"}:
        raise HTTPException(415, "Solo se admite PDF o TXT UTF-8 como cuerpo binario.")
    try:
        fields = {
            key: int(value) if value.isascii() and value.isdigit() else value
            for key, value in {
                "nivel_simplificacion_nlp": nivel_simplificacion_nlp,
                "target_level": target_level,
                "level": level,
            }.items()
            if value is not None
        }
        selected_level = schemas.AdaptTextRequest(
            text="placeholder", age_group=age_group, **fields
        ).nivel_simplificacion_nlp
    except ValueError:
        raise HTTPException(
            422, "El nivel debe ser un entero entre 1 y 5 o BASICO, INTERMEDIO o AVANZADO."
        ) from None
    if age_group is None and child_id is None and fields:
        age_group = {1: "6-8", 2: "6-8", 3: "9-11", 4: "9-11", 5: "12+"}[selected_level]
    child_age = {"6-8": 7, "9-11": 10, "12+": 12}.get(age_group)
    if child_id:
        child = await accessible_child(child_id, user, db)
        if age_group is None:
            child_age = education.teaching_age(child)
    data = await read_stream(request)
    result, digest = await process(None, data, media_type, selected_level, child_age=child_age)
    return await persist(
        result,
        digest,
        len(data),
        models.DocumentType.PDF if media_type == "application/pdf" else models.DocumentType.TXT,
        child_id,
        user,
        db,
        level=selected_level,
        age_group=age_group,
    )


@router.post("/generate", response_model=schemas.AdaptationRead)
async def generate_lesson(
    payload: schemas.LessonGenerate,
    user: models.User = Depends(_adults),
    db: AsyncSession = Depends(get_db),
):
    group = request_group(payload)
    child_age = {"6-8": 7, "9-11": 10, "12+": 12}.get(group)
    if payload.child_id:
        child = await accessible_child(payload.child_id, user, db)
        if payload.age_group is None:
            child_age = education.teaching_age(child)
    group = education.question_age_group(child_age)
    try:
        category, entry = await resolve_lesson(payload.category, payload.topic)
    except SourceUnavailable:
        raise HTTPException(
            503, "No hay un artículo disponible para ese tema. Prueba un tema más específico."
        ) from None
    entry = replace(entry, text=lesson_excerpt(entry.text, group))
    result, digest = await process(
        entry.text,
        None,
        "text/plain",
        payload.simplification_level,
        child_age=child_age,
        allow_local_excerpt=True,
    )
    needs_local_reference = entry.provider == "wikipedia" and (
        not result.level_progression_met
        or (payload.simplification_level == 1 and result.metrics["score_delta"] < 15)
    )
    if result.adapted_text == result.original_text or needs_local_reference:
        fallback = local_article(resolve_topic(payload.category, payload.topic))
        if fallback is not None:
            fallback = replace(fallback, text=lesson_excerpt(fallback.text, group))
        if fallback is not None and fallback.text != entry.text:
            entry = fallback
            result, digest = await process(
                entry.text,
                None,
                "text/plain",
                payload.simplification_level,
                child_age=child_age,
                allow_local_excerpt=True,
            )
            result.warnings.append("pedagogical_local_reference")
        if result.adapted_text == result.original_text:
            raise HTTPException(
                503, "La fuente disponible no permite una simplificación fiel. Prueba otro tema."
            )
    return await persist(
        result,
        digest,
        len(entry.text.encode("utf-8")),
        models.DocumentType.TXT,
        payload.child_id,
        user,
        db,
        category=category,
        level=payload.simplification_level,
        title=entry.title,
        article=entry,
        age_group=group,
    )


@router.get("/{adaptation_id}", response_model=schemas.AdaptationRead)
async def get_adaptation(
    adaptation_id: uuid.UUID,
    user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await db.get(models.AdaptationContent, adaptation_id)
    if content is None:
        # Android already knows document.id; support it as a latest-version alias.
        await accessible_document(adaptation_id, user, db)
        content = await db.scalar(
            select(models.AdaptationContent)
            .where(models.AdaptationContent.document_id == adaptation_id)
            .order_by(
                models.AdaptationContent.updated_at.desc(), models.AdaptationContent.id.desc()
            )
            .limit(1)
        )
    if content is None:
        raise HTTPException(404, "Adaptación no encontrada.")
    await accessible_document(content.document_id, user, db)
    if content.child_id is not None:
        await accessible_child(content.child_id, user, db)
    payload = {
        **content.response_payload,
        "original_text": content.original_text,
        "adapted_text": content.adapted_text,
    }
    if not payload.get("level_previews"):
        # Old retained versions get truthful comparisons of their stored pair.
        # GET enriches in RAM; it never silently rewrites their historical content.
        from app.nlp.readability import measure
        from app.services.pedagogy import choose_levels, replacements

        _, previews, progressive = await asyncio.to_thread(choose_levels, content.original_text)
        original = await asyncio.to_thread(measure, content.original_text)
        adapted = await asyncio.to_thread(measure, content.adapted_text)
        payload.update(
            readability_gain=adapted.score - original.score,
            original_avg_sentence_length=original.word_count / original.sentence_count,
            adapted_avg_sentence_length=adapted.word_count / adapted.sentence_count,
            original_syllables_per_word=original.syllable_count / original.word_count,
            adapted_syllables_per_word=adapted.syllable_count / adapted.word_count,
            lexical_replacements=await asyncio.to_thread(
                replacements, content.original_text, content.adapted_text
            ),
            level_previews=previews,
            level_progression_met=progressive,
            engine_version="legacy_enriched",
            model_version="legacy_not_retrained",
            checkpoint_name=None,
        )
    return schemas.AdaptationRead.model_validate(payload)
