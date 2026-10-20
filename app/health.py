import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.nlp.pipeline import pipeline

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live():
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    state = {
        "status": "not_ready",
        "database": "unavailable",
        "pipeline": "unchecked",
        "engine_mode": "unavailable",
    }
    try:
        async with asyncio.timeout(2):
            await db.execute(text("SELECT 1"))
        state["database"] = "operational"
    except Exception:
        return JSONResponse(state, status_code=503)
    try:
        async with asyncio.timeout(2):
            state.update(await asyncio.to_thread(pipeline.readiness))
    except Exception:
        # Never expose exception details or download/load a model in a probe.
        state["pipeline"] = "unavailable"
    usable = state["pipeline"] == "operational"
    state["status"] = "ready" if usable else "not_ready"
    return JSONResponse(state, status_code=200 if usable else 503)
