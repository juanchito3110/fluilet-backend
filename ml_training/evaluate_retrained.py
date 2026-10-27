"""End-to-end, five-level diagnostics; all scores measured, no benchmark assertions."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from app.services.ranker import model_info
from ml_training.benchmark import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("checkpoints/retraining_metrics.json"))
    parser.add_argument("--baseline", type=Path, default=Path("docs/retraining-baseline-v1.json"))
    args = parser.parse_args()

    async def run():
        return {
            name: await evaluate(Path("ml_training/fixtures") / (name + ".json"))
            for name in ("easier_diagnostic", "unseen_v2")
        }

    info = model_info()
    report = {**info, "end_to_end": asyncio.run(run())}
    # Keep the zero-weight ablation distinct from the actual archived v1 system.
    report["initial_weight_ablation"] = info.get(
        "initial_weight_ablation", info["baseline_metrics"]
    )
    report["baseline_metrics"] = json.loads(args.baseline.read_text())
    easier = report["end_to_end"]["easier_diagnostic"]
    previous = report["baseline_metrics"]["end_to_end"]["easier_diagnostic"]
    report["easier_benchmark_before"] = f"{previous['progressive_count']}/{previous['samples']}"
    report["easier_benchmark_after"] = f"{easier['progressive_count']}/{easier['samples']}"
    report["benchmark_definition"] = (
        "strict five-level score progression, not exact pedagogical bands or clinical accuracy"
    )
    report["benchmark_status"] = (
        "legacy six-case diagnostic informed v1 rules; excluded from v2 fitting; not independent generalization"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # One packaged artifact, byte-identical to the offline checkpoint, usable by CI/Docker.
    artifact_path = Path("checkpoints/context-ranker-v2/model.json")
    artifact = json.loads(artifact_path.read_text())
    artifact["metrics"] = {
        key: value
        for key, value in report.items()
        if key not in ("artifact_sha256", "active", "model_version", "checkpoint_name")
    }
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    Path("app/services/assets/context-ranker-v2.json").write_bytes(artifact_path.read_bytes())
    report["artifact_sha256"] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: {k: v for k, v in value.items() if k != "results"}
                for key, value in report["end_to_end"].items()
            }
        )
    )


if __name__ == "__main__":
    main()
