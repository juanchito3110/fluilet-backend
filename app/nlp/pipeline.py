"""Bounded hybrid inference. Failed documents never return partial adaptations."""

import asyncio
from dataclasses import dataclass

from app.config import settings
from app.nlp.chunking import ChunkingError, chunk_text, conservative_tokens
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

    def readiness(self) -> dict:
        """Content-free CPU probe; never load weights or run model generation."""
        sample = (
            "Los alumnos utilizan libros y posteriormente realizan actividades con sus amigos "
            "en la escuela. "
        ) * 2
        chunks = chunk_text(sample, conservative_tokens)
        candidate = refine(chunks[0])
        rules_operational = fidelity_ok(sample, candidate) and accepted(
            measure(sample), measure(candidate)
        )
        model_loaded = self.model.is_loaded
        usable = rules_operational and (settings.ALLOW_RULE_BASED_FALLBACK or model_loaded)
        mode = (
            "hybrid"
            if usable and model_loaded and settings.ALLOW_RULE_BASED_FALLBACK
            else "mt5_refinement"
            if usable and model_loaded
            else "deterministic"
            if usable
            else "unavailable"
        )
        return {
            "pipeline": "operational" if usable else "unavailable",
            "engine_mode": mode,
            "model": self.model.state,
            "rules_fallback": settings.ALLOW_RULE_BASED_FALLBACK,
        }

    @staticmethod
    async def accept_candidate(source, original, candidate):
        if not await asyncio.to_thread(fidelity_ok, source, candidate):
            return None
        try:
            adapted = await asyncio.to_thread(measure, candidate)
        except ValueError:
            return None
        return ChunkResult(candidate, original, adapted) if accepted(original, adapted) else None

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
                # A passing deterministic candidate is sufficient: do not spend
                # model inference or let an invalid generation hide this expert.
                if settings.ALLOW_RULE_BASED_FALLBACK:
                    candidate = await asyncio.to_thread(refine, chunk, attempt, level)
                    chosen = await self.accept_candidate(chunk, original, candidate)
                    if chosen:
                        break
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
                for candidate, method in candidates:
                    chosen = await self.accept_candidate(chunk, original, candidate)
                    if chosen:
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
