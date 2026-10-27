"""Joint v2.1 fit, validation-only compression policy, one frozen test comparison."""

import argparse
import hashlib
import json
import math
import random
import time
from pathlib import Path
from statistics import mean

from app.nlp.readability import measure
from app.services.calibration import alternatives, minimal_edits
from app.services.joint import (
    FEATURE_NAMES,
    features,
    lexical_features,
    prediction,
    sari_vector,
    score,
)
from app.services.pedagogy import GOALS
from app.services.rewriting import candidates
from ml_training.metrics import sari, sari_components


def band_distance(text, level):
    value = measure(text).score
    lo, hi, *_ = GOALS[level]
    return max(0, lo - value, value - hi)


def pool(source):
    base = candidates(source, [0.0] * 24)
    # Multiple passes are reference-free. Training references are not inserted
    # into validation/test generation pools.
    seeds = sorted(base, key=lambda t: -measure(t).score)[:2]
    return sorted(
        set(base) | set(minimal_edits(source)) | set(alternatives(source, seeds, glosses=False))
    )


def groups(rows):
    values = []
    for row in rows:
        source, reference, level = row["source"], row["target"], row["level"]
        before = measure(source)
        generated = [t for t in pool(source) if measure(t).score >= before.score]
        generated = generated or [source]
        values.append(
            dict(
                row=row,
                base_pool=set(candidates(source, [0.0] * 24)),
                pool=[
                    dict(
                        text=t,
                        x=features(source, t, level),
                        sari=sari(source, t, reference),
                        distance=band_distance(t, level),
                    )
                    for t in generated
                ],
            )
        )
    return values


def regression_samples(rows):
    samples = []
    for item in groups(rows):
        row = item["row"]
        source, reference, level = row["source"], row["target"], row["level"]
        options = {r["text"] for r in item["pool"]} | {reference}
        for text in sorted(options):
            vector = features(source, text, level)
            parts = sari_components(source, text, reference)
            parts["utility"] = (
                0.7 * sum(parts.values()) / 3
                + 0.15 * math.exp(-band_distance(text, level) / 20)
                + 0.1 * vector[13]
                + 0.05 * max(0, 1 - vector[3])
            )
            samples.append((vector, parts))
    return samples


def lexical_groups(rows):
    values = []
    for index, row in enumerate(rows):
        # Distractors stay in their own partition. Top-1 is a lexical selection
        # task with a provided annotation span, distinct from free generation.
        negative = rows[(index + 17) % len(rows)]["replacement"]
        options = list(dict.fromkeys((row["word"], negative, row["replacement"])))
        values.append(
            (
                [(lexical_features(row["word"], t, row["source"]), t) for t in options],
                row["replacement"],
            )
        )
    return values


def evaluate(model, grouped, policy):
    chosen = []
    for group in grouped:
        row = group["row"]
        level = row["level"]
        if model is None:
            center = sum(GOALS[level][:2]) / 2
            pick = min(
                (r for r in group["pool"] if r["text"] in group["base_pool"]),
                key=lambda r: abs(measure(r["text"]).score - center),
            )
        elif policy == "nearest_band":
            pick = min(
                group["pool"],
                key=lambda r: (r["distance"], -prediction(model, row["source"], r["text"], level)),
            )
        elif isinstance(policy, dict):
            nearest = min(r["distance"] for r in group["pool"])
            pick = max(
                (r for r in group["pool"] if r["distance"] <= nearest + policy["band_tolerance"]),
                key=lambda r: prediction(model, row["source"], r["text"], level),
            )
        else:
            pick = min(
                group["pool"],
                key=lambda r: (
                    policy * r["distance"] / 100
                    - prediction(model, row["source"], r["text"], level)
                ),
            )
        chosen.append(pick)
    return dict(
        sari_score=mean(r["sari"] for r in chosen),
        band_distance=mean(r["distance"] for r in chosen),
        samples=len(chosen),
    )


def top1(weights, grouped):
    correct = 0
    for options, reference in grouped:
        # Frozen heuristic: prefer fewer syllables, preserving plural agreement.
        if weights is None:
            selected = max(options, key=lambda pair: (pair[0][15], 1 - pair[0][3], pair[0][8]))[1]
        else:
            selected = max(options, key=lambda pair: score(weights, pair[0]))[1]
        correct += selected == reference
    return correct / len(grouped)


def train(data, output, epochs=35):
    started = time.perf_counter()
    rows = {
        name: [json.loads(line) for line in (data / (name + ".jsonl")).read_text().splitlines()]
        for name in ("train", "validation", "test")
    }
    manifest = json.loads((data / "manifest.json").read_text())
    for name in rows:
        assert (
            hashlib.sha256((data / (name + ".jsonl")).read_bytes()).hexdigest()
            == manifest["split_sha256"][name]
        )
    for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
        for key in ("source", "family", "document_id"):
            assert not {r[key] for r in rows[a]} & {r[key] for r in rows[b]}, "Split leakage"
    samples = {name: regression_samples(rows[name]) for name in ("train", "validation")}
    lexical = {name: lexical_groups(rows[name]) for name in rows}
    model = {
        "features": FEATURE_NAMES,
        "heads": {
            name: [0.0] * len(FEATURE_NAMES) for name in ("keep", "add", "delete", "utility")
        },
        "lexical": [0.0] * len(FEATURE_NAMES),
    }
    before = hashlib.sha256(json.dumps(model, sort_keys=True).encode()).hexdigest()
    rng = random.Random(20261028)
    history = []
    best = None

    def mse(partition):
        return mean(
            (score(model["heads"][name], sari_vector(x) if name != "utility" else x) - y[name]) ** 2
            for x, y in samples[partition]
            for name in model["heads"]
        )

    for epoch in range(1, epochs + 1):
        order = list(range(len(samples["train"])))
        rng.shuffle(order)
        rate = 0.008 / (1 + epoch / 10)
        for i in order:
            x, y = samples["train"][i]
            for name, weights in model["heads"].items():
                vector = sari_vector(x) if name != "utility" else x
                error = max(-2, min(2, score(weights, vector) - y[name]))
                for j, value in enumerate(vector):
                    weights[j] -= rate * (error * value + 0.001 * weights[j])
        order = list(range(len(lexical["train"])))
        rng.shuffle(order)
        for i in order:
            options, reference = lexical["train"][i]
            positive = next(x for x, t in options if t == reference)
            for negative, t in options:
                if t == reference:
                    continue
                delta = [a - b for a, b in zip(positive, negative, strict=True)]
                error = -1 / (1 + math.exp(max(-30, min(30, score(model["lexical"], delta)))))
                for j, value in enumerate(delta):
                    model["lexical"][j] -= rate * (error * value + 0.001 * model["lexical"][j])
        record = dict(
            epoch=epoch,
            train_loss=mse("train"),
            val_loss=mse("validation"),
            lexical_top1=top1(model["lexical"], lexical["validation"]),
        )
        history.append(record)
        print(json.dumps(record), flush=True)
        if best is None or record["val_loss"] < best[0]:
            best = (record["val_loss"], json.loads(json.dumps(model)), epoch)
    _, model, selected = best
    from ml_training.boosting import fit

    boost = fit(model, samples, history)
    validation = groups(rows["validation"])
    from ml_training.joint_policy import calibrate, frozen

    calibration = calibrate(model, rows["validation"], validation)
    base_validation = calibration["baseline"]
    policy = model["band_policy"]
    validation_metrics = calibration["selected"]["metrics"]
    policies = calibration["trials"]
    # Test touched only after epoch/policy selection. Report failures, never force
    # the requested inequality or select a checkpoint using test measurements.
    test = groups(rows["test"])
    baseline = frozen(rows["test"])
    baseline["lexical_top1"] = top1(None, lexical["test"])
    retrained = evaluate(model, test, policy)
    retrained["lexical_top1"] = top1(model["lexical"], lexical["test"])
    metrics = dict(
        model_version="context-ranker-es-v2.1",
        dataset_v1_size=manifest["v1"]["full_unfiltered_derived_pairs"],
        dataset_v2_size=manifest["v2"]["total_pairs"],
        epochs=epochs + boost["rounds_executed"],
        sgd_epochs=epochs,
        selected_epoch=epochs + boost["selected_trees"],
        selected_base_epoch=selected,
        history=history,
        residual_training=boost,
        train_loss=history[epochs + boost["selected_trees"] - 1]["train_loss"],
        val_loss=boost["val_loss"],
        baseline_metrics=baseline,
        retrained_metrics=retrained,
        baseline_sari=baseline["sari_score"],
        retrained_sari=retrained["sari_score"],
        all_comparisons_improved=retrained["sari_score"] > baseline["sari_score"]
        and retrained["lexical_top1"] > baseline["lexical_top1"]
        and retrained["band_distance"] < baseline["band_distance"],
        validation_baseline=base_validation,
        validation_policy=validation_metrics,
        policy_candidates=policies,
        weights_sha256_before=before,
        weights_sha256_after=hashlib.sha256(json.dumps(model, sort_keys=True).encode()).hexdigest(),
        training_seconds=time.perf_counter() - started,
        dataset_manifest=manifest,
        protocol="v2 reference-free baseline pool; v2.1 expands minimal edits and complete clauses; lexical span-selection separate",
        limitations=[
            "test partition was inspected during v2 development; no fitting or policy selection on its labels",
            "not an independent blind or clinical evaluation; no universal band guarantee",
        ],
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "joint.json").write_text(json.dumps(model, indent=2) + "\n")
    (output / "training_manifest.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(
        json.dumps(
            {
                "baseline": baseline,
                "retrained": retrained,
                "policy": policy,
                "all_improved": metrics["all_comparisons_improved"],
            }
        ),
        flush=True,
    )
    return model, metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("ml_training/data/enhanced-v2"))
    parser.add_argument("--output", type=Path, default=Path("checkpoints/context-ranker-v2.1"))
    parser.add_argument("--epochs", type=int, default=35)
    args = parser.parse_args()
    if not 1 <= args.epochs <= 100:
        parser.error("epochs must be 1..100")
    train(args.data, args.output, args.epochs)


if __name__ == "__main__":
    main()
