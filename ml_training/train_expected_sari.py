"""Train expected SARI directly on candidate groups; no band or test feedback."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from app.services.residual import estimate, lexical_summary
from ml_training.train_separated import grouped


def run(parent, output, epochs=40):
    info = json.loads((parent / "training_manifest.json").read_text())
    selection = json.loads((parent / "selection.json").read_text())
    model = selection["model"]
    data = Path("ml_training/data/enhanced-v2")
    rows = {}
    for split in ("train", "validation"):
        raw = (data / (split + ".jsonl")).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == selection["split_sha256"][split]
        rows[split] = [json.loads(line) for line in raw.splitlines()]
    groups = {name: grouped(values, model["priors"]) for name, values in rows.items()}
    weights = np.array(model["weights"])
    initial = weights.copy()
    prepared = {}
    for name, values in groups.items():
        prepared[name] = []
        for g in values:
            x = np.array(g["x"])
            summaries = [lexical_summary(model, g["row"]["source"], text) for text in g["options"]]
            offset = np.array(
                [
                    estimate(model, vec)
                    - weights @ vec
                    + model["lexical_blend"] * c
                    - model["edit_cost"] * n
                    for vec, (c, n) in zip(x, summaries, strict=True)
                ]
            )
            prepared[name].append((g, x, offset))
    rng = np.random.default_rng(20261027)
    best = None
    history = []
    for epoch in range(epochs + 1):
        if epoch:
            for index in rng.permutation(len(prepared["train"])):
                g, x, offset = prepared["train"][index]
                logits = x @ weights + offset
                probs = np.exp(np.clip(logits - logits.max(), -30, 0) * 4)
                probs /= probs.sum()
                rewards = np.array(g["sari"]) / 100
                advantages = rewards - probs @ rewards
                gradient = x.T @ (probs * advantages) * 4
                weights += 0.04 / (1 + epoch / 10) * (gradient - 0.002 * (weights - initial))
        trials = []
        for margin in (0, 0.005, 0.01, 0.02, 0.04, 0.08, 0.16):
            scores = []
            for g, x, offset in prepared["validation"]:
                values = x @ weights + offset
                i = int(values.argmax())
                identity = g["options"].index(g["row"]["source"])
                if values[i] <= values[identity] + margin:
                    i = identity
                scores.append(g["sari"][i])
            trials.append((float(np.mean(scores)), margin))
        score, margin = max(trials)
        record = dict(epoch=epoch, validation_sari=score, margin=margin)
        history.append(record)
        print(json.dumps(record), flush=True)
        if best is None or score > best[0]:
            best = score, weights.copy(), margin, epoch
    model.update(weights=best[1].tolist(), margin=best[2])
    selection["model"] = model
    output.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(selection, sort_keys=True).encode()
    (output / "selection.json").write_bytes(raw)
    (output / "fit_manifest.json").write_text(
        json.dumps(
            dict(
                history=history,
                selected_epoch=best[3],
                validation_sari=best[0],
                parent_validation_sari=info["lexical_calibration"]["selected"]["metrics"][
                    "sari_score"
                ],
                frozen_selection_sha256=hashlib.sha256(raw).hexdigest(),
                test_evaluated=False,
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, default=Path("checkpoints/context-ranker-v2.2"))
    parser.add_argument("--output", type=Path, default=Path("checkpoints/expected-sari-validation"))
    args = parser.parse_args()
    run(args.parent, args.output)
