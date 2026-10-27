"""Run the archived v1 code with the same public corpus, inputs and metric.

Isolated temporary checkout, no application DB, secrets, weights or web requests.
"""

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def evaluate(ref, output):
    root = Path(__file__).resolve().parents[1]
    revision = subprocess.check_output(
        ["git", "rev-parse", ref + "^{commit}"], cwd=root, text=True
    ).strip()
    with tempfile.TemporaryDirectory(prefix="fluilet-baseline-") as raw:
        target = Path(raw)
        archive = subprocess.check_output(["git", "archive", revision], cwd=root)
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            stream.extractall(target, filter="data")
        corpus = root / "datasets/EASIER/SGSS.csv"
        (target / "datasets/EASIER").mkdir(parents=True)
        shutil.copyfile(corpus, target / "datasets/EASIER/SGSS.csv")
        for name in ("easier_diagnostic", "unseen_v2"):
            shutil.copyfile(
                root / "ml_training/fixtures" / f"{name}.json",
                target / "ml_training/fixtures" / f"{name}.json",
            )
        for name in ("benchmark.py", "metrics.py"):
            shutil.copyfile(root / "ml_training" / name, target / "ml_training" / name)
        env = os.environ.copy()
        env.update(
            SECRET_KEY="evaluation-only-key-000000000000000000000000000",
            MT5_ENABLED="false",
            WIKIPEDIA_ENABLED="false",
            DEMO_ACCOUNTS_ENABLED="false",
        )
        script = """import asyncio,json
from pathlib import Path
from ml_training.benchmark import evaluate
async def run():
    return {name:await evaluate(Path('ml_training/fixtures')/(name+'.json')) for name in ('easier_diagnostic','unseen_v2')}
print(json.dumps(asyncio.run(run())))
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", script],
            cwd=target,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        values = json.loads(result.stdout)
        report = dict(
            revision=revision,
            corpus_sha256=hashlib.sha256(corpus.read_bytes()).hexdigest(),
            end_to_end=values,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="b342076")
    parser.add_argument("--output", type=Path, default=Path("docs/retraining-baseline-v1.json"))
    args = parser.parse_args()
    print(evaluate(args.ref, args.output)["revision"])


if __name__ == "__main__":
    main()
