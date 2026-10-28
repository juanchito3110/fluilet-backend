"""Evaluate all five real outputs without storing user text or loading ML weights."""

import argparse
import asyncio
import json
import time
from pathlib import Path
from statistics import mean, median

from app.encyclopedia import ARTICLES
from app.nlp.mt5 import ModelUnavailable
from app.nlp.pipeline import AdaptationPipeline
from app.nlp.readability import measure
from app.services.pedagogy import GOALS, VERSION
from app.services.resources import resources


class RulesOnly:
    async def prepare(self):
        raise ModelUnavailable()


async def evaluate(rows):
    engine = AdaptationPipeline(RulesOnly())
    results = []
    for key, source in rows:
        start = time.perf_counter()
        result = await engine.run(source, 1)
        elapsed = time.perf_counter() - start
        original = measure(source)
        results.append(
            {
                "id": key,
                "original_score": original.score,
                "original_avg_sentence_length": original.word_count / original.sentence_count,
                "inference_seconds_all_levels": elapsed,
                "progressive": result.level_progression_met,
                "levels": [
                    {
                        "level": item["level"],
                        "score": item["readability_score"],
                        "gain": item["readability_score"] - original.score,
                        "avg_sentence_length": item["avg_sentence_length"],
                        "target_met": item["target_met"],
                        "support_count": len(item.get("pedagogical_support", [])),
                        "support_word_count": sum(
                            measure(f["text"]).word_count
                            for f in item.get("pedagogical_support", [])
                        ),
                        "pre_support_score": item.get(
                            "pre_support_readability_score", item["readability_score"]
                        ),
                        "double_condition_met": item["readability_score"] >= 65
                        and item["readability_score"] - original.score >= 15,
                    }
                    for item in result.level_previews
                ],
            }
        )
    count = len(results)
    return {
        "engine_version": VERSION,
        "samples": count,
        "corpus": resources().statistics,
        "resource_inventory": resources().inventory,
        "dataset_status": "authored_local_alignment_calibration"
        if all(key in ARTICLES for key, _ in rows)
        else "supplied_material; corpus index may include evaluation annotations; not a held-out claim",
        "mean_original_score": mean(row["original_score"] for row in results),
        "median_original_score": median(row["original_score"] for row in results),
        "progressive_count": sum(row["progressive"] for row in results),
        "mean_inference_seconds_all_levels": mean(
            row["inference_seconds_all_levels"] for row in results
        ),
        "levels": [
            {
                "level": level,
                "goal": GOALS[level],
                "mean_score": mean(row["levels"][level - 1]["score"] for row in results),
                "mean_gain": mean(row["levels"][level - 1]["gain"] for row in results),
                "mean_sentence_length": mean(
                    row["levels"][level - 1]["avg_sentence_length"] for row in results
                ),
                "gain_15_count": sum(row["levels"][level - 1]["gain"] >= 15 for row in results),
                "goal_met_count": sum(row["levels"][level - 1]["target_met"] for row in results),
                "double_condition_count": sum(
                    row["levels"][level - 1]["double_condition_met"] for row in results
                ),
            }
            for level in range(1, 6)
        ],
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        help="Optional existing evaluation JSON/JSONL (source fields); never training on traffic",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.data:
        raw = args.data.read_text(encoding="utf-8")
        records = (
            json.loads(raw)
            if raw.lstrip().startswith("[")
            else [json.loads(line) for line in raw.splitlines() if line.strip()]
        )
        rows = [
            (str(row.get("document_id", index)), row["source"]) for index, row in enumerate(records)
        ]
    else:
        rows = [(key, article.text) for key, article in ARTICLES.items()]
    report = asyncio.run(evaluate(rows))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "samples",
                    "progressive_count",
                    "mean_original_score",
                    "mean_inference_seconds_all_levels",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
