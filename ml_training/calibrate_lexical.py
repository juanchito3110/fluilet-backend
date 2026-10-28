"""Calibrate independent lexical-head confidence against validation delta SARI."""

import hashlib
import json
from pathlib import Path
from statistics import mean

from app.services.residual import estimate, lexical_summary
from ml_training.joint_policy import frozen
from ml_training.train_joint import lexical_groups, top1
from ml_training.train_separated import grouped, lexical_accuracy, lexical_tasks


def run(data=Path("ml_training/data/enhanced-v2"), output=Path("checkpoints/context-ranker-v2.2")):
    selection = json.loads((output / "selection.json").read_text())
    info = json.loads((output / "training_manifest.json").read_text())
    rows = {}
    for split in ("validation", "test"):
        raw = (data / (split + ".jsonl")).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == selection["split_sha256"][split]
        rows[split] = [json.loads(line) for line in raw.splitlines()]
    model = selection["model"]
    model["lexical_weights"] = selection["lexical"]

    def prepared(records):
        values = grouped(records, model["priors"])
        for g in values:
            g["estimated"] = [estimate(model, x) for x in g["x"]]
            g["lexical"] = [
                lexical_summary(model, g["row"]["source"], text) for text in g["options"]
            ]
        return values

    validation = prepared(rows["validation"])

    def evaluate(values, alpha, cost, margin):
        actual = []
        for g in values:
            scores = [
                v + alpha * c - cost * n
                for v, (c, n) in zip(g["estimated"], g["lexical"], strict=True)
            ]
            selected = max(range(len(scores)), key=scores.__getitem__)
            identity = g["options"].index(g["row"]["source"])
            if scores[selected] <= scores[identity] + margin:
                selected = identity
            actual.append((g, selected))
        gold = [
            g["sari"][i]
            for g, i in actual
            if g["row"]["provenance"] == "EASIER_filtered_annotation"
        ]
        return dict(
            sari_score=mean(g["sari"][i] for g, i in actual),
            gold_sari=mean(gold),
            samples=len(actual),
        )

    trials = []
    for alpha in (
        0,
        0.01,
        0.025,
        0.05,
        0.1,
        0.2,
        0.4,
        0.5,
        0.6,
        0.7,
        0.8,
        0.9,
        1,
        1.1,
        1.2,
        1.4,
        1.6,
        3.2,
        6.4,
        12.8,
    ):
        for cost in (
            0,
            0.005,
            0.01,
            0.02,
            0.05,
            0.075,
            0.1,
            0.125,
            0.15,
            0.175,
            0.2,
            0.225,
            0.25,
            0.3,
            0.35,
            0.4,
            0.8,
            1.6,
        ):
            for margin in (0, 0.005, 0.01, 0.02, 0.04):
                trials.append(
                    dict(
                        alpha=alpha,
                        cost=cost,
                        margin=margin,
                        metrics=evaluate(validation, alpha, cost, margin),
                    )
                )
    best = max(trials, key=lambda r: r["metrics"]["sari_score"])
    model.update(lexical_blend=best["alpha"], edit_cost=best["cost"], margin=best["margin"])
    selection["model"] = model
    raw = json.dumps(selection, sort_keys=True).encode()
    (output / "selection.json").write_bytes(raw)
    # Scalar policy fully frozen above, then test. Preserve prior failure results.
    previous = info["retrained_metrics"]
    test = prepared(rows["test"])
    retrained = evaluate(test, best["alpha"], best["cost"], best["margin"])
    retrained["lexical_top1"] = lexical_accuracy(
        selection["lexical"], lexical_tasks(rows["test"], model["priors"])
    )
    baseline = frozen(rows["test"])
    baseline["lexical_top1"] = top1(None, lexical_groups(rows["test"]))
    info.update(
        baseline_metrics=baseline,
        retrained_metrics=retrained,
        baseline_sari=baseline["sari_score"],
        retrained_sari=retrained["sari_score"],
        lexical_calibration=dict(
            selected=best,
            trials=trials,
            selection_partition="validation",
            objective="aggregate validation SARI, with gold EASIER diagnostic reported separately",
        ),
        previous_separated_metrics=previous,
        frozen_selection_sha256=hashlib.sha256(raw).hexdigest(),
        weights_sha256_after=hashlib.sha256(raw).hexdigest(),
        sari_improved=retrained["sari_score"] > baseline["sari_score"],
        lexical_improved=retrained["lexical_top1"] > baseline["lexical_top1"],
        all_comparisons_improved=retrained["sari_score"] > baseline["sari_score"]
        and retrained["lexical_top1"] > baseline["lexical_top1"],
    )
    (output / "training_manifest.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(dict(selected=best, baseline=baseline, retrained=retrained)))


if __name__ == "__main__":
    run()
