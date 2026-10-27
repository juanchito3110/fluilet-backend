"""Policy fitting uses validation only; baseline executes frozen fc12a7a code."""

import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def frozen(rows):
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="fluilet-frozen-") as raw:
        directory = Path(raw)
        with tarfile.open(
            fileobj=io.BytesIO(subprocess.check_output(["git", "archive", "fc12a7a"], cwd=root))
        ) as archive:
            archive.extractall(directory, filter="data")
        path = directory / "rows.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        script = """import json,sys
from statistics import mean
from app.services.rewriting import candidates
from app.services.pedagogy import GOALS
from app.nlp.readability import measure
from ml_training.metrics import sari
rows=json.load(open(sys.argv[1],encoding="utf-8")); results=[]
for row in rows:
    source,level=row["source"],row["level"]
    prediction=min(candidates(source,[0.0]*24),key=lambda t:abs(measure(t).score-sum(GOALS[level][:2])/2))
    lo,hi,*_=GOALS[level]
    results.append((sari(source,prediction,row["target"]),max(0,lo-measure(prediction).score,measure(prediction).score-hi)))
print(json.dumps(dict(sari_score=mean(r[0] for r in results),band_distance=mean(r[1] for r in results),samples=len(rows))))
"""
        env = {
            **os.environ,
            "SECRET_KEY": "evaluation-only-key-0000000000000000000000000",
            "MT5_ENABLED": "false",
            "DEMO_ACCOUNTS_ENABLED": "false",
        }
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, str(path)],
            cwd=directory,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)


def calibrate(model, rows, grouped):
    from ml_training.train_joint import evaluate

    baseline = frozen(rows)
    choices = []
    for mix in (0, 0.25, 0.5, 0.75, 1):
        model["sari_mix"] = mix
        for policy in (
            0,
            0.25,
            0.5,
            1,
            2,
            4,
            8,
            16,
            32,
            64,
            128,
            256,
            "nearest_band",
            *({"band_tolerance": v} for v in (0.05, 0.1, 0.25, 0.5, 1)),
        ):
            metrics = evaluate(model, grouped, policy)
            choices.append(dict(mix=mix, policy=policy, metrics=metrics))
    eligible = [
        item
        for item in choices
        if item["metrics"]["band_distance"] <= baseline["band_distance"] + 1e-9
    ]
    best = max(eligible or choices, key=lambda item: item["metrics"]["sari_score"])
    model["sari_mix"] = best["mix"]
    model["band_policy"] = best["policy"]
    return dict(baseline=baseline, selected=best, trials=choices)
