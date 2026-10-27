"""Publish actual fitted weights and measured compliance; never manufacture a pass."""

import asyncio
import hashlib
import json
import platform
from collections import Counter
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def release_context(path):
    from app.config import settings
    from app.services.ranker import checkpoint

    previous = (settings.RANKER_CHECKPOINT, settings.RANKER_CHECKPOINT_SHA256)
    try:
        settings.RANKER_CHECKPOINT = str(path.resolve())
        settings.RANKER_CHECKPOINT_SHA256 = None
        checkpoint.cache_clear()
        yield
    finally:
        settings.RANKER_CHECKPOINT, settings.RANKER_CHECKPOINT_SHA256 = previous
        checkpoint.cache_clear()


def package():
    directory = Path("checkpoints/context-ranker-v2.1")
    info = json.loads((directory / "training_manifest.json").read_text())
    joint = json.loads((directory / "joint.json").read_text())
    path = Path("ml_training/data/enhanced-v2/train.jsonl")
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == info["dataset_manifest"]["split_sha256"]["train"]
    )
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    info.update(
        sari_score=info["retrained_sari"],
        easier_benchmark_before="0/6",
        easier_benchmark_after=None,
        benchmark_definition="strict five-level score progression; independent of exact band/length compliance",
        benchmark_status="known diagnostic used during development; not an independent blind validation",
        environment={"python": platform.python_version(), "seed": 20261028},
        architecture="5 linear heads (155 coefficients) and shared depth-3 residual trees; validation-fitted compression policy; constrained candidates",
    )
    artifact = dict(
        model_version="context-ranker-es-v2.1",
        checkpoint_name="context-ranker-v2.1",
        joint_model=joint,
        metrics=info,
        training_document_hashes=sorted(
            {hashlib.sha256(r["document_id"].encode()).hexdigest() for r in rows}
        ),
        training_family_hashes=sorted(
            {hashlib.sha256(r["family"].encode()).hexdigest() for r in rows}
        ),
        training_target_counts=dict(
            Counter(hashlib.sha256(r["replacement"].casefold().encode()).hexdigest() for r in rows)
        ),
    )

    def write():
        raw = json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"
        (directory / "model.json").write_text(raw, encoding="utf-8")
        Path("app/services/assets/context-ranker-v2.1.json").write_text(raw, encoding="utf-8")

    write()
    from app.services.ranker import checkpoint

    checkpoint.cache_clear()
    from app.encyclopedia import ARTICLES
    from app.services.pedagogy import GOALS
    from ml_training.evaluate_levels import evaluate

    async def run():
        values = {
            "local_bank": await evaluate([(key, article.text) for key, article in ARTICLES.items()])
        }
        for name in ("easier_diagnostic", "unseen_v2"):
            records = json.loads(Path("ml_training/fixtures", name + ".json").read_text())
            values[name] = await evaluate([(row["document_id"], row["source"]) for row in records])
        return values

    with release_context(directory / "model.json"):
        results = asyncio.run(run())
    compliance = {}
    for name, result in results.items():
        compliance[name] = dict(
            samples=result["samples"],
            progressive=result["progressive_count"],
            all_five_bands_met=sum(
                all(
                    GOALS[level][0] <= row["levels"][level - 1]["score"] <= GOALS[level][1]
                    for level in range(1, 6)
                )
                for row in result["results"]
            ),
            levels={
                str(level): dict(
                    score_band_met=sum(
                        GOALS[level][0] <= row["levels"][level - 1]["score"] <= GOALS[level][1]
                        for row in result["results"]
                    ),
                    full_target_met=result["levels"][level - 1]["goal_met_count"],
                )
                for level in range(1, 6)
            },
        )
    from app.demo_accounts import PRESETS, RulesOnly
    from app.nlp.pipeline import AdaptationPipeline

    async def demos():
        rows = []
        for _code, _, age, level, *rest in PRESETS:
            for key in rest[3]:
                response = await AdaptationPipeline(RulesOnly()).run(
                    ARTICLES[key].text, level, child_age=age
                )
                rows.append(
                    (
                        level,
                        response.metrics["adapted_szigriszt_score"],
                        response.level_progression_met,
                    )
                )
        return rows

    with release_context(directory / "model.json"):
        demo = asyncio.run(demos())
    compliance["managed_demos"] = dict(
        samples=len(demo),
        progressive=sum(row[2] for row in demo),
        levels={
            str(level): dict(
                sample_count=sum(row[0] == level for row in demo),
                score_band_met=sum(
                    row[0] == level and GOALS[level][0] <= row[1] <= GOALS[level][1] for row in demo
                ),
            )
            for level in sorted({row[0] for row in demo})
        },
    )
    info["easier_benchmark_after"] = f"{results['easier_diagnostic']['progressive_count']}/6"
    info["band_compliance"] = compliance
    info["all_bands_met"] = all(
        row["score_band_met"] == row.get("sample_count", group["samples"])
        for group in compliance.values()
        for row in group["levels"].values()
    )
    info["acceptance_criteria_met"] = bool(
        info["all_comparisons_improved"] and info["all_bands_met"]
    )
    info["end_to_end"] = {
        name: {
            key: result[key]
            for key in (
                "samples",
                "progressive_count",
                "mean_original_score",
                "levels",
                "results",
                "mean_inference_seconds_all_levels",
            )
        }
        for name, result in results.items()
    }
    artifact["metrics"] = info
    write()
    report = {
        **info,
        "artifact_sha256": hashlib.sha256((directory / "model.json").read_bytes()).hexdigest(),
    }
    Path("checkpoints/retraining_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "baseline_sari": info["baseline_sari"],
                "retrained_sari": info["retrained_sari"],
                "band_compliance": compliance,
                "acceptance_criteria_met": info["acceptance_criteria_met"],
            }
        )
    )


if __name__ == "__main__":
    package()
