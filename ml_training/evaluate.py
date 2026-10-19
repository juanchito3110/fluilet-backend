"""Evaluate local checkpoint/predictions. Print aggregate numeric metrics only."""

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from app.nlp.readability import accepted, measure
from app.nlp.refinement import fidelity_ok
from app.nlp.segmentation import words


def evaluate_rows(rows):
    values = []
    for row in rows:
        source, prediction, target = row["source"], row["prediction"], row["target"]
        original = measure(source)
        try:
            adapted = measure(prediction)
        except ValueError:
            adapted = None
        ref, pred = Counter(words(target.lower())), Counter(words(prediction.lower()))
        common = sum((ref & pred).values())
        f1 = 2 * common / (sum(ref.values()) + sum(pred.values()))
        values.append(
            {
                "score_delta": adapted.score - original.score if adapted else None,
                "adapted_score": adapted.score if adapted else None,
                "acceptance_rate": float(adapted is not None and accepted(original, adapted)),
                "lexical_fidelity_guard_rate": float(fidelity_ok(source, prediction)),
                "reference_unigram_f1": f1,
            }
        )
    if not values:
        raise ValueError("No evaluation rows.")
    return {
        "examples": len(values),
        **{
            key: (
                mean(item[key] for item in values if item[key] is not None)
                if any(item[key] is not None for item in values)
                else None
            )
            for key in values[0]
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--checkpoint", type=Path)
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for line in args.data.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.checkpoint:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            args.checkpoint, local_files_only=True, trust_remote_code=False
        )
        model = AutoModelForSeq2SeqLM.from_pretrained(
            args.checkpoint,
            local_files_only=True,
            trust_remote_code=False,
            use_safetensors=None,
            weights_only=True,
        ).eval()
        for row in rows:
            inputs = tokenizer(
                "simplificar español: " + row["source"], return_tensors="pt", truncation=False
            )
            if inputs["input_ids"].shape[-1] > 512:
                raise ValueError("Evaluation sentence exceeds configured training token budget.")
            with torch.inference_mode():
                output = model.generate(**inputs, max_new_tokens=512, num_beams=4, do_sample=False)
            row["prediction"] = tokenizer.decode(output[0], skip_special_tokens=True)
    print(json.dumps(evaluate_rows(rows), indent=2))


if __name__ == "__main__":
    main()
