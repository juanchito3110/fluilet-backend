import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.nlp.mt5 import runtime

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live():
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    try:
        async with asyncio.timeout(2):
            await db.execute(text("SELECT 1"))
        usable = settings.ALLOW_RULE_BASED_FALLBACK or runtime.state == "loaded"
        return JSONResponse(
            {
                "status": "ready" if usable else "not_ready",
                "model": runtime.state,
                "rules_fallback": settings.ALLOW_RULE_BASED_FALLBACK,
            },
            status_code=200 if usable else 503,
        )
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)
