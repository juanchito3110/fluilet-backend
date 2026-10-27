"""Version-independent end-to-end metrics, also executable against archived v1."""

import json
import time
from statistics import mean

from app.nlp.mt5 import ModelUnavailable
from app.nlp.pipeline import AdaptationPipeline
from app.nlp.readability import measure
from ml_training.metrics import sari


class Offline:
    async def prepare(self):
        raise ModelUnavailable()


async def evaluate(path):
    rows = json.loads(path.read_text())
    results = []
    for row in rows:
        start = time.perf_counter()
        result = await AdaptationPipeline(Offline()).run(row["source"], 1)
        previews = result.level_previews
        results.append(
            dict(
                id=row["document_id"],
                progressive=result.level_progression_met,
                original_score=measure(row["source"]).score,
                scores=[p["readability_score"] for p in previews],
                gain=result.metrics["score_delta"],
                double_condition_met=result.meets_readability_target,
                sari_score=sari(row["source"], result.adapted_text, row["target"]),
                seconds=time.perf_counter() - start,
            )
        )
    return dict(
        samples=len(results),
        progressive_count=sum(r["progressive"] for r in results),
        double_condition_count=sum(r["double_condition_met"] for r in results),
        mean_gain=mean(r["gain"] for r in results),
        mean_sari_score=mean(r["sari_score"] for r in results),
        mean_inference_seconds=mean(r["seconds"] for r in results),
        results=results,
    )
