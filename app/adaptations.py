"""Authenticated adaptation; content lives only until this request/work completes."""

import asyncio
import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth, models, schemas
from app.activities import accessible_child
from app.config import settings
from app.database import get_db
from app.ingestion import IngestionError, clean_text, extract_safely, read_stream
from app.nlp.pipeline import AdaptationError, pipeline

router = APIRouter(prefix="/api/v1/adaptations", tags=["adaptations"])
_slots = asyncio.Semaphore(settings.PROCESSING_CONCURRENCY)
_adults = auth.require_roles(models.UserRole.TUTOR, models.UserRole.ADULTO_INDEPENDIENTE)


async def process(text: str | None, data: bytes | None, media_type: str, level: int):
    if _slots.locked():
        raise HTTPException(
            503, "Procesamiento ocupado. Intenta más tarde.", headers={"Retry-After": "5"}
        )
    async with _slots:
        try:
            async with asyncio.timeout(settings.PROCESSING_TIMEOUT_SECONDS):
                source = (
                    await asyncio.to_thread(clean_text, text)
                    if text is not None
                    else await extract_safely(data, media_type)
                )
                result = await pipeline.run(source, level)
                digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
                return result, digest
        except (AdaptationError, IngestionError, ValueError):
            raise HTTPException(
                422, "No fue posible obtener una adaptación válida para este documento."
            ) from None
        except TimeoutError:
            raise HTTPException(
                422, "No fue posible completar la adaptación dentro del límite de tiempo."
            ) from None


async def persist(result, digest, file_size, file_type, child_id, user, db):
    # Serialize metadata upserts per owner, independently of inference execution.
    locked_user = await db.scalar(
        select(models.User)
        .where(models.User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    await auth.validate_identity(locked_user, db)
    if child_id is not None:
        await accessible_child(child_id, user, db)
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
    await db.commit()
    await db.refresh(document)
    return schemas.AdaptationRead(
        document=schemas.DocumentRead.model_validate(document),
        adapted_text=result.adapted_text,
        chunks=result.chunks,
    )


@router.post("/text", response_model=schemas.AdaptationRead)
async def adapt_text(
    payload: schemas.AdaptTextRequest,
    user: models.User = Depends(_adults),
    db: AsyncSession = Depends(get_db),
):
    if payload.child_id:
        await accessible_child(payload.child_id, user, db)
    result, digest = await process(
        payload.text, None, "text/plain", payload.nivel_simplificacion_nlp
    )
    return await persist(
        result,
        digest,
        len(payload.text.encode("utf-8")),
        models.DocumentType.TXT,
        payload.child_id,
        user,
        db,
    )


@router.post(
    "/file",
    response_model=schemas.AdaptationRead,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                "text/plain": {"schema": {"type": "string", "format": "binary"}},
            },
        }
    },
)
async def adapt_file(
    request: Request,
    nivel_simplificacion_nlp: str = Query(default="INTERMEDIO"),
    child_id: uuid.UUID | None = None,
    user: models.User = Depends(_adults),
    db: AsyncSession = Depends(get_db),
):
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type not in {"text/plain", "application/pdf"}:
        raise HTTPException(415, "Solo se admite PDF o TXT UTF-8 como cuerpo binario.")
    try:
        level = schemas.AdaptTextRequest(
            text="placeholder",
            nivel_simplificacion_nlp=(
                int(nivel_simplificacion_nlp)
                if nivel_simplificacion_nlp.isascii() and nivel_simplificacion_nlp.isdigit()
                else nivel_simplificacion_nlp
            ),
        ).nivel_simplificacion_nlp
    except ValueError:
        raise HTTPException(422, "Nivel NLP inválido.") from None
    if child_id:
        await accessible_child(child_id, user, db)
    data = await read_stream(request)
    result, digest = await process(None, data, media_type, level)
    return await persist(
        result,
        digest,
        len(data),
        models.DocumentType.PDF if media_type == "application/pdf" else models.DocumentType.TXT,
        child_id,
        user,
        db,
    )
