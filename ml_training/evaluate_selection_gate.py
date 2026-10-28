"""Evaluate the already frozen selective gate; never fit using test labels."""

import hashlib
import json
from pathlib import Path
from statistics import mean

from app.services.selection_gate import choose
from ml_training.joint_policy import frozen
from ml_training.metrics import sari
from ml_training.train_joint import lexical_groups, top1
from ml_training.train_separated import lexical_accuracy, lexical_tasks, pool


def run(directory=Path("checkpoints/context-ranker-v2.3")):
    raw = (directory / "selection.json").read_bytes()
    info = json.loads((directory / "training_manifest.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == info["frozen_selection_sha256"]
    selected = json.loads(raw)
    model = selected["model"]
    raw_test = Path("ml_training/data/enhanced-v2/test.jsonl").read_bytes()
    assert hashlib.sha256(raw_test).hexdigest() == selected["split_sha256"]["test"]
    rows = [json.loads(line) for line in raw_test.splitlines()]
    scores = []
    decisions = {}
    for row in rows:
        text, decision = choose(model, row["source"], pool(row["source"]), row["level"])
        decisions[decision] = decisions.get(decision, 0) + 1
        scores.append(sari(row["source"], text, row["target"]))
    baseline = frozen(rows)
    baseline["lexical_top1"] = top1(None, lexical_groups(rows))
    retrained = dict(
        sari_score=mean(scores),
        samples=len(rows),
        lexical_top1=lexical_accuracy(
            model["lexical_weights"], lexical_tasks(rows, model["priors"])
        ),
    )
    info.update(
        baseline_metrics=baseline,
        retrained_metrics=retrained,
        baseline_sari=baseline["sari_score"],
        retrained_sari=retrained["sari_score"],
        sari_improved=retrained["sari_score"] > baseline["sari_score"],
        lexical_improved=retrained["lexical_top1"] > baseline["lexical_top1"],
        all_comparisons_improved=retrained["sari_score"] > baseline["sari_score"]
        and retrained["lexical_top1"] > baseline["lexical_top1"],
        test_gate_decisions=decisions,
        test_selection_sha256=hashlib.sha256(raw).hexdigest(),
        test_protocol="test opened after frozen train/validation gate; legacy partition observed in earlier releases, not a blind external holdout",
    )
    (directory / "training_manifest.json").write_text(json.dumps(info, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                baseline=baseline,
                retrained=retrained,
                decisions=decisions,
                strictly_improved=info["sari_improved"],
            )
        )
    )


if __name__ == "__main__":
    run()
