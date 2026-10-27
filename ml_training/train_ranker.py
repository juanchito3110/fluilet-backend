"""CPU SGD training of lexical and structural logistic rankers, no ML dependency.

This trains a candidate ranker, not mT5 and not a free-form generative transformer.
Each epoch records losses plus reference-based metrics on disjoint validation.
"""

import argparse
import hashlib
import json
import math
import random
import time
from collections import Counter
from pathlib import Path
from statistics import mean

from app.nlp.readability import measure
from app.services.ranker import (
    FEATURES,
    MODEL_VERSION,
    lexical_features,
    predict,
    structural_features,
)
from app.services.rewriting import candidates
from ml_training.metrics import sari


def loss(weights, samples):
    return mean(
        -y * math.log(max(1e-12, predict(weights, x)))
        - (1 - y) * math.log(max(1e-12, 1 - predict(weights, x)))
        for x, y in samples
    )


def examples(rows):
    lexical, structural = [], []
    for index, row in enumerate(rows):
        source, target = row["source"], row["target"]
        lexical.append((lexical_features(row["word"], row["replacement"], source), 1.0))
        lexical.append((lexical_features(row["word"], row["word"], source), 0.0))
        wrong = rows[(index + 17) % len(rows)]["replacement"]
        # No artificial negative equals its positive label.
        if wrong.casefold() not in {row["replacement"].casefold(), row["word"].casefold()}:
            lexical.append((lexical_features(row["word"], wrong, source), 0.0))
        level = row["level"]
        for candidate in (source, target):
            # Reference quality, not a score fabricated from a desired outcome.
            label = sari(source, candidate, target) / 100
            structural.append((structural_features(source, candidate, level), label))
    return lexical, structural


def update(weights, samples, rng, rate):
    indices = list(range(len(samples)))
    rng.shuffle(indices)
    for index in indices:
        x, y = samples[index]
        gradient = predict(weights, x) - y
        for j, value in enumerate(x):
            weights[j] -= rate * (gradient * value + 0.0001 * weights[j])


def accuracy(weights, samples):
    tp = fp = fn = correct = 0
    for x, y in samples:
        predicted = predict(weights, x) >= 0.5
        positive = y >= 0.5
        correct += predicted == positive
        tp += predicted and positive
        fp += predicted and not positive
        fn += not predicted and positive
    return dict(accuracy=correct / len(samples), f1=2 * tp / max(1, 2 * tp + fp + fn))


def reference_metrics(weights, rows):
    # Limited two-candidate ablation: original vs supplied reference. This is
    # explicitly NOT the end-to-end system benchmark (run separately).
    predictions = [
        max(
            (r["source"], r["target"]),
            key=lambda t: predict(weights, structural_features(r["source"], t, r["level"])),
        )
        for r in rows
    ]
    return dict(
        sari_score=mean(
            sari(r["source"], p, r["target"]) for r, p in zip(rows, predictions, strict=True)
        ),
        mean_readability_gain=mean(
            measure(p).score - measure(r["source"]).score
            for r, p in zip(rows, predictions, strict=True)
        ),
        protocol="two_candidate_reference_ranking; oracle reference available, not end-to-end generation",
    )


def end_to_end(lexical, structural, rows):
    values = []
    for row in rows:
        source, reference, level = row["source"], row["target"], row["level"]
        pool = candidates(source, lexical)

        # The supplied reference is NEVER inserted in this pool.
        def cost(text, source=source, level=level):
            score = measure(text).score
            return (
                abs(score - {1: 91, 2: 79, 3: 69.5, 4: 62, 5: 57.5}[level]) / 50
                + 1
                - predict(structural, structural_features(source, text, level))
            )

        prediction = min(pool, key=cost)
        values.append(
            (sari(source, prediction, reference), measure(prediction).score - measure(source).score)
        )
    return dict(
        sari_score=mean(x[0] for x in values),
        mean_readability_gain=mean(x[1] for x in values),
        samples=len(values),
        protocol="end_to_end_constrained_generation; references used only for scoring",
    )


def train(data, output, epochs=20):
    started = time.perf_counter()
    rows = {
        name: [json.loads(line) for line in (data / (name + ".jsonl")).read_text().splitlines()]
        for name in ("train", "validation", "test")
    }
    manifest = json.loads((data / "manifest.json").read_text())
    for name, expected in manifest["split_sha256"].items():
        if hashlib.sha256((data / (name + ".jsonl")).read_bytes()).hexdigest() != expected:
            raise ValueError("Dataset hash mismatch")
    for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
        for key in ("source", "family", "document_id"):
            if {r[key] for r in rows[a]} & {r[key] for r in rows[b]}:
                raise ValueError("Dataset leakage")
    samples = {name: examples(value) for name, value in rows.items()}
    lexical, structural = [0.0] * 24, [0.0] * len(FEATURES)
    before = hashlib.sha256(json.dumps([lexical, structural]).encode()).hexdigest()
    rng = random.Random(20261027)
    history = []
    best = None
    baseline = end_to_end(lexical, structural, rows["test"])
    for epoch in range(1, epochs + 1):
        rate = 0.06 / (1 + epoch / 5)
        update(lexical, samples["train"][0], rng, rate)
        update(structural, samples["train"][1], rng, rate)
        train_loss = (
            loss(lexical, samples["train"][0]) + loss(structural, samples["train"][1])
        ) / 2
        val_loss = (
            loss(lexical, samples["validation"][0]) + loss(structural, samples["validation"][1])
        ) / 2
        metrics = dict(
            epoch=epoch,
            train_loss=train_loss,
            val_loss=val_loss,
            lexical_selection=accuracy(lexical, samples["validation"][0]),
            reference_ranking=reference_metrics(structural, rows["validation"]),
            **end_to_end(lexical, structural, rows["validation"][:24]),
        )
        history.append(metrics)
        print(json.dumps(metrics), flush=True)
        if best is None or val_loss < best[0]:
            best = (val_loss, list(lexical), list(structural), epoch)
    _, lexical, structural, best_epoch = best
    after = hashlib.sha256(json.dumps([lexical, structural]).encode()).hexdigest()
    assert before != after and all(math.isfinite(w) for w in lexical + structural)
    metrics = dict(
        dataset_v1_size=manifest["v1"]["full_unfiltered_derived_pairs"],
        dataset_v2_size=manifest["v2"]["total_pairs"],
        baseline_metrics=baseline,
        retrained_metrics={
            **end_to_end(lexical, structural, rows["test"]),
            "lexical_selection": accuracy(lexical, samples["test"][0]),
        },
        epochs=epochs,
        selected_epoch=best_epoch,
        train_loss=history[best_epoch - 1]["train_loss"],
        val_loss=best[0],
        sari_score=end_to_end(lexical, structural, rows["test"])["sari_score"],
        metric_protocol="end_to_end_constrained_generation; Unicode word set ngrams 1..4; single reference",
        history=history,
        weights_sha256_before=before,
        weights_sha256_after=after,
        training_seconds=time.perf_counter() - started,
        dataset_manifest=manifest,
        architecture="two linear logistic heads; 52 fitted coefficients; CPU SGD; constrained candidate generation",
    )
    artifact = dict(
        model_version=MODEL_VERSION,
        checkpoint_name="context-ranker-v2",
        structural_features=FEATURES,
        lexical_weights=lexical,
        structural_weights=structural,
        metrics=metrics,
        training_document_hashes=sorted(
            {hashlib.sha256(r["document_id"].encode()).hexdigest() for r in rows["train"]}
        ),
        training_family_hashes=sorted(
            {hashlib.sha256(r["family"].encode()).hexdigest() for r in rows["train"]}
        ),
        training_target_counts=dict(
            Counter(
                hashlib.sha256(r["replacement"].casefold().encode()).hexdigest()
                for r in rows["train"]
            )
        ),
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "model.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    (output / "training_manifest.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"
    )
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("ml_training/data/enhanced-v2"))
    parser.add_argument("--output", type=Path, default=Path("checkpoints/context-ranker-v2"))
    parser.add_argument("--epochs", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.epochs <= 100:
        parser.error("epochs must be 1..100")
    train(args.data, args.output, args.epochs)


if __name__ == "__main__":
    main()
