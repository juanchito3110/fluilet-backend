"""Bounded hybrid inference. Failed documents never return partial adaptations."""

import asyncio
from dataclasses import dataclass

from app.config import settings
from app.nlp.chunking import ChunkingError, chunk_text
from app.nlp.mt5 import ModelUnavailable, runtime
from app.nlp.readability import Readability, accepted, measure, telemetry
from app.nlp.refinement import fidelity_ok, refine


class AdaptationError(ValueError):
    pass


@dataclass
class ChunkResult:
    adapted_text: str
    original: Readability
    adapted: Readability


@dataclass
class AdaptationResult:
    adapted_text: str
    metrics: dict
    chunks: list[dict]
    method: str


class AdaptationPipeline:
    def __init__(self, model=runtime):
        self.model = model

    async def run(self, text: str, level: int = 3) -> AdaptationResult:
        model_available = True
        try:
            await self.model.prepare()
        except ModelUnavailable:
            model_available = False
        if not model_available and not settings.ALLOW_RULE_BASED_FALLBACK:
            raise AdaptationError("model_unavailable")
        try:
            chunks = await asyncio.to_thread(
                chunk_text,
                text,
                self.model.count_tokens,
                settings.MT5_MAX_INPUT_TOKENS,
                settings.MAX_DOCUMENT_WORDS,
            )
        except ChunkingError:
            raise AdaptationError("chunking_failed") from None
        results = []
        used_model = False
        for chunk in chunks:
            original = await asyncio.to_thread(measure, chunk)
            if original.score > 128.535:
                # Explicit CTO exception: unchanged text is the most faithful
                # maintenance candidate, not a fictitious 15-point improvement.
                results.append(ChunkResult(chunk, original, original))
                continue
            chosen = None
            for attempt in range(settings.MAX_GENERATION_ATTEMPTS):
                candidates = []
                if model_available:
                    try:
                        generated = await self.model.generate(chunk, attempt)
                        candidates.extend(
                            [
                                (generated, "mt5"),
                                (
                                    await asyncio.to_thread(refine, generated, attempt, level),
                                    "hybrid",
                                ),
                            ]
                        )
                    except ModelUnavailable:
                        model_available = False
                if settings.ALLOW_RULE_BASED_FALLBACK:
                    candidates.append(
                        (await asyncio.to_thread(refine, chunk, attempt, level), "rules")
                    )
                for candidate, method in candidates:
                    if not await asyncio.to_thread(fidelity_ok, chunk, candidate):
                        continue
                    try:
                        adapted = await asyncio.to_thread(measure, candidate)
                    except ValueError:
                        continue
                    if accepted(original, adapted):
                        chosen = ChunkResult(candidate, original, adapted)
                        used_model |= method in {"mt5", "hybrid"}
                        break
                if chosen:
                    break
            if chosen is None:
                raise AdaptationError("acceptance_failed")
            results.append(chosen)
        combined = "\n\n".join(item.adapted_text for item in results)
        original_total = await asyncio.to_thread(measure, text)
        adapted_total = await asyncio.to_thread(measure, combined)
        if not accepted(original_total, adapted_total) or not await asyncio.to_thread(
            fidelity_ok, text, combined
        ):
            raise AdaptationError("document_acceptance_failed")
        return AdaptationResult(
            combined,
            telemetry(original_total, adapted_total),
            [
                {"chunk_index": i, **telemetry(item.original, item.adapted)}
                for i, item in enumerate(results)
            ],
            "hybrid" if used_model else "rules",
        )


pipeline = AdaptationPipeline()
