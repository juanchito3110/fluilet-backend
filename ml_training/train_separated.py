"""Train SARI deltas on train; choose trees/margin on validation; freeze then test."""

import argparse
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

import numpy as np

from app.nlp.readability import measure
from app.nlp.segmentation import words
from app.services.residual import NAMES, digest, estimate, vector
from app.services.rewriting import apply, candidates, operations
from ml_training.boosting import fit_tree, tree_outputs
from ml_training.joint_policy import frozen
from ml_training.metrics import sari
from ml_training.train_joint import lexical_groups, top1


def pool(source):
    # Generator sees source only. Single edits are essential for lexical SGSS;
    # its references contain one substitution, not a full structural rewrite.
    values = set(candidates(source, [0.0] * 24))
    values.update(apply(source, [op]) for op in operations(source, [0.0] * 24))
    return sorted(values)


def priors_for(rows):
    counts, pairs = Counter(), defaultdict(Counter)
    for row in rows:
        counts[digest(row["replacement"])] += 1
        pairs[digest(row["word"])][digest(row["replacement"])] += 1
    word_counts = Counter(
        digest(word) for source in {r["source"] for r in rows} for word in words(source.casefold())
    )
    return dict(
        counts=dict(counts),
        pairs={k: dict(v) for k, v in pairs.items()},
        word_counts=dict(word_counts),
    )


def lexical_tasks(rows, priors):
    grouped = []
    for i, row in enumerate(rows):
        choices = list(
            dict.fromkeys(
                (row["word"], rows[(i + 17) % len(rows)]["replacement"], row["replacement"])
            )
        )
        options = []
        for text in choices:
            context = re.sub(
                r"(?<!\w)" + re.escape(row["word"]) + r"(?!\w)",
                lambda m, text=text: text,
                row["source"],
                count=1,
                flags=re.I,
            )
            options.append((vector(row["source"], context, priors, span=(row["word"], text)), text))
        grouped.append((options, row["replacement"]))
    return grouped


def lexical_accuracy(weights, grouped):
    return mean(
        max(options, key=lambda p: sum(a * b for a, b in zip(weights, p[0], strict=True)))[1]
        == reference
        for options, reference in grouped
    )


def grouped(rows, priors):
    result = []
    for row in rows:
        source, reference = row["source"], row["target"]
        options = pool(source)
        identity = sari(source, source, reference) / 100
        result.append(
            dict(
                row=row,
                options=options,
                x=[vector(source, text, priors) for text in options],
                y=[sari(source, text, reference) / 100 - identity for text in options],
                sari=[sari(source, text, reference) for text in options],
            )
        )
    return result


def evaluate(model, groups, margin):
    picks = []
    for group in groups:
        scores = [estimate(model, x) for x in group["x"]]
        identity = group["options"].index(group["row"]["source"])
        selected = max(range(len(scores)), key=scores.__getitem__)
        if scores[selected] <= scores[identity] + margin:
            selected = identity
        picks.append((group, selected))

    def distance(group, index):
        from app.services.pedagogy import GOALS

        lo, hi, *_ = GOALS[group["row"]["level"]]
        score = measure(group["options"][index]).score
        return max(0, lo - score, score - hi)

    return dict(
        sari_score=mean(g["sari"][i] for g, i in picks),
        band_distance=mean(distance(g, i) for g, i in picks),
        samples=len(picks),
    )


def train(data, output, rounds, evaluate_test=True):
    started = time.perf_counter()
    manifest = json.loads((data / "manifest.json").read_text())
    rows = {}
    for name in ("train", "validation", "test"):
        raw = (data / (name + ".jsonl")).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest["split_sha256"][name]
        rows[name] = [json.loads(line) for line in raw.splitlines()]
    for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
        for key in ("source", "family", "document_id"):
            assert not {r[key] for r in rows[a]} & {r[key] for r in rows[b]}
    priors = priors_for(rows["train"])
    groups = {name: grouped(rows[name], priors) for name in ("train", "validation")}
    print(
        json.dumps(
            {"stage": "generated_train_validation", "rows": {k: len(v) for k, v in groups.items()}}
        ),
        flush=True,
    )
    matrices = {
        name: (
            np.array([x for g in values for x in g["x"]]),
            np.array([y for g in values for y in g["y"]]),
        )
        for name, values in groups.items()
    }
    x, y = matrices["train"]
    # Equal source weight within each provenance, with real lexical supervision
    # weighted above synthetic augmentation. Candidate-rich documents cannot
    # dominate the objective just because they produce many alternatives.
    importance = np.array(
        [
            (4 if g["row"]["provenance"] == "EASIER_filtered_annotation" else 1) / len(g["x"])
            for g in groups["train"]
            for _ in g["x"]
        ]
    )
    importance *= len(importance) / importance.sum()
    weights = np.linalg.solve(
        x.T @ (importance[:, None] * x) + 0.1 * np.eye(len(NAMES)), x.T @ (importance * y)
    )
    model = dict(
        features=NAMES, weights=weights.tolist(), trees=[], rate=0.15, priors=priors, margin=0
    )
    initial = hashlib.sha256(
        json.dumps(dict(weights=[0.0] * len(NAMES), trees=[])).encode()
    ).hexdigest()
    predictions = {name: a @ weights for name, (a, _) in matrices.items()}
    history, best = [], None
    for iteration in range(rounds + 1):
        if iteration:
            # Deterministic weighted bootstrap from train only for tree fitting.
            sampled = np.random.default_rng(20261027 + iteration).choice(
                len(x), len(x), p=importance / importance.sum()
            )
            residual = np.repeat((y - predictions["train"])[:, None], 4, axis=1)
            tree = fit_tree(x[sampled], residual[sampled], depth=3, minimum=30)
            model["trees"].append(tree)
            for name, (a, _) in matrices.items():
                predictions[name] += model["rate"] * tree_outputs(tree, a)[:, 0]
        losses = {
            name + "_loss": float(((predictions[name] - b) ** 2).mean())
            for name, (_, b) in matrices.items()
        }
        # Tree count/margin selected solely by held-out validation SARI, not bands.
        gold = [
            g
            for g in groups["validation"]
            if g["row"]["provenance"] == "EASIER_filtered_annotation"
        ]
        trials = [
            (margin, evaluate(model, gold or groups["validation"], margin))
            for margin in (0, 0.0025, 0.005, 0.01, 0.02, 0.04, 0.08)
        ]
        margin, metrics = max(trials, key=lambda item: item[1]["sari_score"])
        record = dict(
            epoch=iteration + 1,
            **losses,
            validation_sari=metrics["sari_score"],
            validation_all_sari=evaluate(model, groups["validation"], margin)["sari_score"],
            margin=margin,
        )
        history.append(record)
        print(json.dumps(record), flush=True)
        key = (metrics["sari_score"], -losses["validation_loss"])
        if best is None or key > best[0]:
            best = key, json.loads(json.dumps(model)), margin, metrics, iteration + 1
    _, model, margin, validation, selected = best
    model["margin"] = margin
    # Fit a separate lexical top-1 head on train. Age/band never occur in its
    # vector; corpus rank and frequency are frozen from train above.
    lexical = {name: lexical_tasks(rows[name], priors) for name in ("train", "validation")}
    lexical_weights = np.zeros(len(NAMES))
    rng = np.random.default_rng(20261027)
    lexical_history, lex_best = [], None
    for epoch in range(1, 36):
        for index in rng.permutation(len(lexical["train"])):
            options, reference = lexical["train"][index]
            positive = next(a for a, t in options if t == reference)
            for negative, text in options:
                if text != reference:
                    delta = np.array([a - b for a, b in zip(positive, negative, strict=True)])
                    error = -1 / (1 + np.exp(np.clip(lexical_weights @ delta, -30, 30)))
                    lexical_weights -= (
                        0.005 / (1 + epoch / 10) * (error * delta + 0.001 * lexical_weights)
                    )
        accuracy = lexical_accuracy(lexical_weights.tolist(), lexical["validation"])
        lexical_history.append(dict(epoch=epoch, validation_top1=accuracy))
        if lex_best is None or accuracy > lex_best[0]:
            lex_best = accuracy, lexical_weights.tolist(), epoch
    output.mkdir(parents=True, exist_ok=True)
    selection = dict(
        model=model,
        lexical=lex_best[1],
        selected=selected,
        lexical_epoch=lex_best[2],
        split_sha256=manifest["split_sha256"],
    )
    raw_selection = json.dumps(selection, sort_keys=True).encode()
    (output / "selection.json").write_bytes(raw_selection)
    if not evaluate_test:
        print(
            json.dumps(
                {
                    "validation": validation,
                    "selected": selected,
                    "margin": margin,
                    "test_evaluated": False,
                }
            ),
            flush=True,
        )
        return
    # First/only test inference follows frozen selection persisted above.
    test = grouped(rows["test"], priors)
    baseline = frozen(rows["test"])
    baseline["lexical_top1"] = top1(None, lexical_groups(rows["test"]))
    retrained = evaluate(model, test, margin)
    retrained["lexical_top1"] = lexical_accuracy(lex_best[1], lexical_tasks(rows["test"], priors))
    metrics = dict(
        model_version="context-ranker-es-v2.2",
        dataset_v1_size=manifest["v1"]["full_unfiltered_derived_pairs"],
        dataset_v2_size=manifest["v2"]["total_pairs"],
        dataset_manifest=manifest,
        epochs=len(history),
        history=history,
        selected_epoch=selected,
        lexical_epochs=35,
        lexical_history=lexical_history,
        train_loss=history[selected - 1]["train_loss"],
        val_loss=history[selected - 1]["validation_loss"],
        baseline_metrics=baseline,
        retrained_metrics=retrained,
        baseline_sari=baseline["sari_score"],
        retrained_sari=retrained["sari_score"],
        sari_improved=retrained["sari_score"] > baseline["sari_score"],
        lexical_improved=retrained["lexical_top1"] > baseline["lexical_top1"],
        all_comparisons_improved=retrained["sari_score"] > baseline["sari_score"]
        and retrained["lexical_top1"] > baseline["lexical_top1"],
        validation_policy=validation,
        weights_sha256_before=initial,
        weights_sha256_after=hashlib.sha256(raw_selection).hexdigest(),
        frozen_selection_sha256=hashlib.sha256(raw_selection).hexdigest(),
        training_seconds=time.perf_counter() - started,
        protocol="SARI delta over identity; train-only regression and lexical head; validation-only trees and margin; structural calibration measured separately",
        limitations=[
            "test inspected in prior v2 development; not a blind external evaluation",
            "training-corpus annotation frequency is not a general Spanish frequency norm",
            "no universal semantic or band guarantee",
        ],
    )
    (output / "training_manifest.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(
        json.dumps(
            {"baseline": baseline, "retrained": retrained, "selected": selected, "margin": margin}
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("ml_training/data/enhanced-v2"))
    parser.add_argument("--output", type=Path, default=Path("checkpoints/context-ranker-v2.2"))
    parser.add_argument("--rounds", type=int, default=35)
    parser.add_argument("--validation-only", action="store_true")
    args = parser.parse_args()
    train(args.data, args.output, args.rounds, not args.validation_only)
