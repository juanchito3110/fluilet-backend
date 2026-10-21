"""Bounded hybrid inference with faithful best-effort delivery for valid text."""

import asyncio
from dataclasses import dataclass, field

from app.config import settings
from app.nlp.mt5 import ModelUnavailable, runtime
from app.nlp.readability import Readability, accepted, measure, telemetry
from app.nlp.refinement import fidelity_ok, refine
from app.nlp.validation import InvalidText, meets_target, reading_chunks

# Compatibility import for callers; only invalid inputs are adaptation errors.
AdaptationError = InvalidText


@dataclass
class ChunkResult:
    adapted_text: str
    original: Readability
    adapted: Readability
    method: str = "original"


@dataclass
class AdaptationResult:
    adapted_text: str
    metrics: dict
    chunks: list[dict]
    method: str
    warnings: list[str] = field(default_factory=list)

    @property
    def meets_readability_target(self) -> bool:
        return meets_target(self.metrics) and all(meets_target(chunk) for chunk in self.chunks)

    @property
    def quality_status(self) -> str:
        return "target_met" if self.meets_readability_target else "best_effort"


def original_result(text: str, warning: str | None = None) -> AdaptationResult:
    chunks = reading_chunks(text)
    metrics = telemetry(measure(text), measure(text))
    return AdaptationResult(
        text,
        metrics,
        [
            {"chunk_index": i, **telemetry(measure(chunk), measure(chunk))}
            for i, chunk in enumerate(chunks)
        ],
        "original",
        ["original_text_retained"] + ([warning] if warning else []),
    )


class AdaptationPipeline:
    def __init__(self, model=runtime):
        self.model = model

    def readiness(self) -> dict:
        """Content-free CPU probe; never load weights or run model generation."""
        sample = (
            "Los alumnos utilizan libros y posteriormente realizan actividades con sus amigos "
            "en la escuela. "
        ) * 2
        candidate = refine(sample)
        usable = fidelity_ok(sample, candidate) and accepted(measure(sample), measure(candidate))
        loaded = self.model.is_loaded
        return {
            "pipeline": "operational" if usable else "unavailable",
            "engine_mode": (
                "hybrid"
                if usable and loaded and settings.ALLOW_RULE_BASED_FALLBACK
                else "mt5_refinement"
                if usable and loaded
                else "deterministic"
                if usable
                else "unavailable"
            ),
            "model": self.model.state,
            "rules_fallback": True,
        }

    @staticmethod
    async def accept_candidate(source, original, candidate, method="rules"):
        if candidate != source and not await asyncio.to_thread(fidelity_ok, source, candidate):
            return None
        try:
            adapted = await asyncio.to_thread(measure, candidate)
        except ValueError:
            return None
        return ChunkResult(candidate, original, adapted, method)

    async def run(self, text: str, level: int = 3) -> AdaptationResult:
        chunks = await asyncio.to_thread(reading_chunks, text)
        results = []
        # First compute a complete safe result. Optional model loading/generation
        # may exhaust its budget, but cannot remove this reading from the user.
        for chunk in chunks:
            original = await asyncio.to_thread(measure, chunk)
            chosen = ChunkResult(chunk, original, original)
            if not accepted(original, original):
                for attempt in range(settings.MAX_GENERATION_ATTEMPTS):
                    candidate = await asyncio.to_thread(refine, chunk, attempt, level)
                    checked = await self.accept_candidate(chunk, original, candidate)
                    if checked and checked.adapted.score > chosen.adapted.score:
                        chosen = checked
            results.append(chosen)

        async def model_pass():
            await self.model.prepare()
            for i, chunk in enumerate(chunks):
                chosen = results[i]
                if accepted(chosen.original, chosen.adapted):
                    continue
                token_count = await asyncio.to_thread(self.model.count_tokens, chunk)
                if token_count > settings.MT5_MAX_INPUT_TOKENS:
                    continue
                for attempt in range(settings.MAX_GENERATION_ATTEMPTS):
                    generated = await self.model.generate(chunk, attempt)
                    refined = await asyncio.to_thread(refine, generated, attempt, level)
                    for candidate, method in [(generated, "mt5"), (refined, "hybrid")]:
                        checked = await self.accept_candidate(
                            chunk, chosen.original, candidate, method
                        )
                        if checked and checked.adapted.score > chosen.adapted.score:
                            chosen = checked
                            results[i] = chosen
                    if accepted(chosen.original, chosen.adapted):
                        break

        if any(not accepted(item.original, item.adapted) for item in results):
            try:
                async with asyncio.timeout(min(8.0, settings.PROCESSING_TIMEOUT_SECONDS / 2)):
                    await model_pass()
            except (ModelUnavailable, TimeoutError):
                pass
        if all(item.method == "original" for item in results):
            return await asyncio.to_thread(original_result, text)
        # Chunk boundaries are transport boundaries, not new linguistic sentences.
        combined = " ".join(item.adapted_text for item in results)
        original_total = await asyncio.to_thread(measure, text)
        adapted_total = await asyncio.to_thread(measure, combined)
        if adapted_total.score < original_total.score or (
            combined != text and not await asyncio.to_thread(fidelity_ok, text, combined)
        ):
            return await asyncio.to_thread(original_result, text)
        methods = {item.method for item in results}
        method = (
            "hybrid"
            if methods & {"mt5", "hybrid"}
            else "rules"
            if "rules" in methods
            else "original"
        )
        return AdaptationResult(
            combined,
            telemetry(original_total, adapted_total),
            [
                {"chunk_index": i, **telemetry(item.original, item.adapted)}
                for i, item in enumerate(results)
            ],
            method,
            ["original_text_retained"] if method == "original" else [],
        )


pipeline = AdaptationPipeline()
