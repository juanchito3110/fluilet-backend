"""Fit train-only SARI-gain heads and calibrate dual margins on validation only.

This command does not open test.jsonl. Evaluation is a separate command after
the chosen policy/checksum have been written to disk.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from app.services.residual import quality, select
from app.services.selection_gate import NAMES, base_candidate, pair_features
from ml_training.metrics import sari
from ml_training.train_separated import pool


def prepare(rows, model, *, augment=False):
    result = []
    for row in rows:
        source = row["source"]
        options = pool(source)
        top = select(model, source, options)
        base = base_candidate(source, row["level"])
        choices = [top]
        if augment and row["provenance"] == "EASIER_filtered_annotation":
            # Alternatives are generated from source only; only train references
            # label their gain. No validation/test reference enters generation.
            choices = list(
                dict.fromkeys(
                    [top, source, *sorted(options, key=lambda t: -quality(model, source, t))[:4]]
                )
            )
        bs = sari(source, base, row["target"])
        for candidate in choices:
            result.append(
                dict(
                    x=pair_features(model, source, candidate, base),
                    top=sari(source, candidate, row["target"]),
                    base=bs,
                    same=candidate == base,
                    document=row["document_id"],
                )
            )
    return result


def calibrate(prediction, x, top, base, disagreement):
    trials = []
    for gm in (
        -1,
        -0.2,
        -0.1,
        -0.04,
        -0.02,
        -0.01,
        -0.005,
        0,
        0.0025,
        0.005,
        0.01,
        0.02,
        0.04,
        0.1,
    ):
        for rm in (-1, -0.1, -0.02, 0, 0.01, 0.04, 0.08, 0.16):
            for floor in (-1, -0.1, -0.05, -0.025, -0.01, -0.005, 0, 0.005, 0.01, 0.02):
                mask = (prediction > gm) & (x[:, 1] > rm) & (x[:, 2] > floor)
                trials.append(
                    dict(
                        gain_margin=gm,
                        ranker_margin=rm,
                        syllable_floor=floor,
                        positive_threshold=0,
                        validation_sari=float(np.where(mask, top, base).mean()),
                        override_count=int((mask & disagreement).sum()),
                    )
                )
    return max(trials, key=lambda r: (r["validation_sari"], r["override_count"]))


def run(data=Path("ml_training/data/enhanced-v2"), output=Path("checkpoints/context-ranker-v2.3")):
    artifact = json.loads(Path("app/services/assets/context-ranker-v2.2.json").read_text())
    model = artifact["sari_ranker"]
    manifest = artifact["metrics"]["dataset_manifest"]
    rows = {}
    for split in ("train", "validation"):
        raw = (data / (split + ".jsonl")).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest["split_sha256"][split]
        rows[split] = [json.loads(line) for line in raw.splitlines()]
    for key in ("document_id", "family", "source"):
        assert not {r[key] for r in rows["train"]} & {r[key] for r in rows["validation"]}
    prepared = {
        name: prepare(values, model, augment=name == "train") for name, values in rows.items()
    }
    print(
        json.dumps(
            {
                "stage": "train_validation_candidates",
                "sizes": {n: len(v) for n, v in prepared.items()},
            }
        ),
        flush=True,
    )
    train = [r for r in prepared["train"] if not r["same"]]
    x = np.array([r["x"] for r in train])
    y = np.array([(r["top"] - r["base"]) / 100 for r in train])
    validation = prepared["validation"]
    vx = np.array([r["x"] for r in validation])
    ts = np.array([r["top"] for r in validation])
    bs = np.array([r["base"] for r in validation])
    vy = (ts - bs) / 100
    disagreement = np.array([not r["same"] for r in validation])
    counts = Counter(r["document"] for r in train)
    trials = []
    best = None
    for power in (0, 0.5, 1):
        sw = np.array([counts[r["document"]] ** (-power) for r in train], dtype=float)
        sw /= sw.mean()
        for ridge in (0.0001, 0.001, 0.01, 0.1, 1, 10):
            weights = np.linalg.solve(
                x.T @ (sw[:, None] * x) + ridge * np.eye(len(NAMES)), x.T @ (sw * y)
            )
            gain = vx @ weights
            policy = calibrate(gain, vx, ts, bs, disagreement)
            loss = float(np.mean((gain - vy) ** 2))
            trial = dict(**policy, ridge=ridge, document_power=power, validation_gain_mse=loss)
            trials.append(trial)
            if best is None or (policy["validation_sari"], -loss) > (
                best["validation_sari"],
                -best["validation_gain_mse"],
            ):
                best = trial
                selected_weights = weights
                selected_sw = sw
    weights = selected_weights
    sw = selected_sw
    predictions = x @ weights
    vp = vx @ weights
    # Weighted source-document bootstrap balances repeated paradigms. Tree
    # gradients still see train only; every stage is selected by validation.
    from ml_training.boosting import fit_tree, tree_outputs

    rng = np.random.default_rng(20261028)
    indices = rng.choice(len(x), size=len(x), replace=True, p=sw / sw.sum())
    trees = []
    selected_trees = []
    residual_history = []
    best_loss = best["validation_gain_mse"]
    for iteration in range(1, 81):
        tree = fit_tree(
            x[indices], np.repeat((y - predictions)[indices, None], 4, axis=1), depth=3, minimum=10
        )
        trees.append(tree)
        predictions += 0.12 * tree_outputs(tree, x)[:, 0]
        vp += 0.12 * tree_outputs(tree, vx)[:, 0]
        loss = float(np.mean((vp - vy) ** 2))
        residual_history.append(
            dict(
                epoch=iteration,
                train_loss=float(np.average((predictions - y) ** 2, weights=sw)),
                validation_loss=loss,
            )
        )
        policy = calibrate(vp, vx, ts, bs, disagreement)
        if (policy["validation_sari"], -loss) > (best["validation_sari"], -best_loss):
            best = {**best, **policy, "trees": iteration, "validation_gain_mse": loss}
            best_loss = loss
            selected_trees = list(trees)
    # Auxiliary calibrated-probability head; threshold zero is an explicitly
    # validation-selected inactive probability guard, not an efficacy claim.
    positive = np.zeros(len(NAMES))
    target = (y > 0).astype(float)
    history = []
    for epoch in range(1, 36):
        for i in rng.permutation(len(x)):
            prob = 1 / (1 + np.exp(-np.clip(x[i] @ positive, -30, 30)))
            positive -= (
                0.015 / (1 + epoch / 10) * ((prob - target[i]) * x[i] * sw[i] + 0.001 * positive)
            )
        loss = float(
            np.average(np.logaddexp(0, x @ positive) - target * (x @ positive), weights=sw)
        )
        history.append(dict(epoch=epoch, train_loss=loss))
    gate = dict(
        features=NAMES,
        gain_weights=weights.tolist(),
        positive_weights=positive.tolist(),
        trees=selected_trees,
        tree_rate=0.12,
        **{
            k: best[k]
            for k in ("gain_margin", "ranker_margin", "positive_threshold", "syllable_floor")
        },
    )
    model["selective_gate"] = gate
    selection = dict(
        model=model, lexical=model["lexical_weights"], split_sha256=manifest["split_sha256"]
    )
    output.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(selection, sort_keys=True).encode()
    (output / "selection.json").write_bytes(raw)
    info = artifact["metrics"]
    info.update(
        model_version="context-ranker-es-v2.3",
        gate_fit=dict(
            training_samples=len(x),
            training_source_rows=len(rows["train"]),
            tie_policy="retain contextual parent on validation-equivalent disagreement decisions; agreements never count as overrides",
            comparison_augmentation="source-only train alternatives; document-balanced regression and bootstrap",
            validation_samples=len(vx),
            features=NAMES,
            seed=20261028,
            history=history,
            residual_history=residual_history,
            selected_trees=len(selected_trees),
            selected=best,
            validation_base_sari=float(bs.mean()),
            validation_parent_sari=float(ts.mean()),
            trial_count=len(trials) * 1120 + 80 * 1120,
            top_trials=sorted(
                trials,
                key=lambda r: (r["validation_sari"], -r["validation_gain_mse"]),
                reverse=True,
            )[:20],
            candidate_summary={
                name: dict(
                    samples=len(values),
                    disagreement=sum(not r["same"] for r in values),
                    top_better=sum(r["top"] > r["base"] for r in values),
                    base_better=sum(r["base"] > r["top"] for r in values),
                    oracle_sari=sum(max(r["base"], r["top"]) for r in values) / len(values),
                )
                for name, values in prepared.items()
            },
            test_opened_for_fitting=False,
            gain_mse=float(np.mean((x @ weights - y) ** 2)),
        ),
        frozen_selection_sha256=hashlib.sha256(raw).hexdigest(),
        parent_model_sha256=hashlib.sha256(
            Path("app/services/assets/context-ranker-v2.2.json").read_bytes()
        ).hexdigest(),
    )
    (output / "training_manifest.json").write_text(json.dumps(info, indent=2) + "\n")
    print(
        json.dumps(
            {
                "selected": best,
                "base_sari": float(bs.mean()),
                "parent_sari": float(ts.mean()),
                "test_opened": False,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    run()
