"""Measured local inference and numerical evaluation; never a clinical certification."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import platform
import time
from collections import Counter
from pathlib import Path
from statistics import mean, median

from app.nlp.readability import accepted, measure
from app.nlp.refinement import fidelity_ok, valid_model_output
from app.nlp.segmentation import words


def valid_prediction(prediction):
    # Some mT5 tokenizers leave sentinel strings after skip_special_tokens=True.
    # These are model control markers, not Spanish words or readable adaptations.
    return valid_model_output(prediction)


def strict_condition(original, adapted):
    return adapted is not None and adapted.score - original.score >= 15.0 and adapted.score >= 65.0


def timing_summary(seconds):
    if not seconds:
        return None
    ordered = sorted(seconds)
    return {
        "count": len(seconds),
        "mean_seconds": mean(seconds),
        "median_seconds": median(seconds),
        "min_seconds": min(seconds),
        "max_seconds": max(seconds),
        "p95_seconds": ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))],
        "first_seconds": seconds[0],
        "total_seconds": sum(seconds),
    }


def evaluate_rows(rows):
    values = []
    valid = 0
    for row in rows:
        source, prediction, target = row["source"], row["prediction"], row["target"]
        original = measure(source)
        try:
            if not valid_prediction(prediction):
                raise ValueError("invalid_model_output")
            adapted = measure(prediction)
            valid += 1
        except ValueError:
            adapted = None
        ref, pred = Counter(words(target.lower())), Counter(words(prediction.lower()))
        common = sum((ref & pred).values())
        denominator = sum(ref.values()) + sum(pred.values())
        f1 = 2 * common / denominator if denominator else 0.0
        strict = strict_condition(original, adapted)
        fidelity = adapted is not None and fidelity_ok(source, prediction)
        values.append(
            {
                "original_score": original.score,
                "score_delta": adapted.score - original.score if adapted else None,
                "adapted_score": adapted.score if adapted else None,
                "acceptance_rate": float(adapted is not None and accepted(original, adapted)),
                "strict_double_condition_rate": float(strict),
                "maintenance_eligible_rate": float(original.score > 128.535),
                "lexical_fidelity_guard_rate": float(fidelity),
                "strict_and_fidelity_rate": float(strict and fidelity),
                "reference_unigram_f1": f1,
            }
        )
    if not values:
        raise ValueError("No evaluation rows.")
    return {
        "examples": len(values),
        "valid_predictions": valid,
        **{
            key: (
                mean(item[key] for item in values if item[key] is not None)
                if any(item[key] is not None for item in values)
                else None
            )
            for key in values[0]
        },
    }


async def evaluate_hybrid(rows, model, tokenizer, args):
    from app.config import settings
    from app.nlp.mt5 import MT5Runtime
    from app.nlp.pipeline import AdaptationError, AdaptationPipeline

    overrides = {
        "MT5_MAX_NEW_TOKENS": args.max_new_tokens,
        "MT5_MAX_INPUT_TOKENS": args.max_input_tokens,
        "MT5_TIMEOUT_SECONDS": 60,
        "ALLOW_RULE_BASED_FALLBACK": True,
    }
    previous = {key: getattr(settings, key) for key in overrides}
    for key, value in overrides.items():
        setattr(settings, key, value)

    class MeteredRuntime(MT5Runtime):
        calls = 0

        async def generate(self, text, attempt):
            self.calls += 1
            return await super().generate(text, attempt)

    runtime = MeteredRuntime()
    runtime._model, runtime._tokenizer, runtime.state = model, tokenizer, "loaded"
    pipeline = AdaptationPipeline(runtime)
    durations, outputs, outcomes = [], [], []
    try:
        for row in rows:
            started, calls_before = time.perf_counter(), runtime.calls
            outcome = {"document_id": row.get("document_id"), "category": row.get("category")}
            try:
                result = await pipeline.run(row["source"])
                outcome.update(
                    {
                        "delivered": True,
                        "accepted": result.meets_readability_target,
                        "quality_status": result.quality_status,
                        "method": result.method,
                        **result.metrics,
                    }
                )
                if result.meets_readability_target:
                    outputs.append({**row, "prediction": result.adapted_text})
            except AdaptationError as error:
                outcome.update({"accepted": False, "reason": str(error)})
            duration = time.perf_counter() - started
            outcome.update(
                {
                    "inference_seconds": duration,
                    "model_generation_calls": runtime.calls - calls_before,
                }
            )
            outcomes.append(outcome)
            durations.append(duration)
    finally:
        await runtime.close()
        for key, value in previous.items():
            setattr(settings, key, value)
    return summarize_hybrid(rows, outputs, outcomes, durations, runtime.calls)


def summarize_hybrid(rows, outputs, outcomes, durations, model_calls):
    """Separate coverage (all inputs) from gate compliance (accepted outputs)."""
    metrics = evaluate_rows(outputs) if outputs else None
    ordinary = [item for item in outcomes if item["accepted"] and not item["maintenance_exception"]]
    strict = sum(
        item["score_delta"] >= 15.0 and item["adapted_szigriszt_score"] >= 65.0 for item in ordinary
    )
    gate_passes = sum(
        accepted(measure(row["source"]), measure(row["prediction"]))
        and fidelity_ok(row["source"], row["prediction"])
        for row in outputs
    )
    return {
        "examples": len(rows),
        "original_score_all_inputs": mean(measure(row["source"]).score for row in rows),
        "accepted_examples": len(outputs),
        "acceptance_rate": len(outputs) / len(rows),
        "below_target_rate": 1 - len(outputs) / len(rows),
        "delivery_rate": sum(item.get("delivered", item["accepted"]) for item in outcomes)
        / len(rows),
        "strict_double_condition_rate_all_inputs": strict / len(rows),
        "strict_compliance_nonmaintenance_accepted": strict / len(ordinary) if ordinary else None,
        "maintenance_accepted_examples": len(outputs) - len(ordinary),
        "gate_and_lexical_guard_compliance_accepted": gate_passes / len(outputs)
        if outputs
        else None,
        "model_generation_calls": model_calls,
        "engine_policy": "deterministic candidate first; bounded mT5 refinement; faithful best effort; advisory quality targets",
        "timing": timing_summary(durations),
        "accepted_only_metrics": metrics,
        "method_counts": dict(Counter(item.get("method", "rejected") for item in outcomes)),
        "outcomes": outcomes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--predictions-output", type=Path)
    parser.add_argument("--max-input-tokens", type=int, default=512)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--num-beams", type=int, default=4)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--hybrid", action="store_true")
    args = parser.parse_args()
    if args.hybrid and not args.checkpoint:
        parser.error("--hybrid requires a local checkpoint")
    if min(args.max_input_tokens, args.max_new_tokens, args.num_beams, args.threads) <= 0:
        parser.error("Generation limits must be positive")
    content = args.data.read_text(encoding="utf-8")
    rows = (
        json.loads(content)
        if args.data.suffix == ".json"
        else [json.loads(line) for line in content.splitlines() if line.strip()]
    )
    if not rows:
        parser.error("Evaluation dataset must be nonempty")
    durations = []
    load_seconds = None
    if args.checkpoint:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        torch.set_num_threads(args.threads)
        started = time.perf_counter()
        tokenizer = AutoTokenizer.from_pretrained(
            args.checkpoint, local_files_only=True, trust_remote_code=False, use_fast=False
        )
        model = AutoModelForSeq2SeqLM.from_pretrained(
            args.checkpoint,
            local_files_only=True,
            trust_remote_code=False,
            use_safetensors=None,
            weights_only=True,
        ).eval()
        load_seconds = time.perf_counter() - started
        for row in rows:
            started = time.perf_counter()
            inputs = tokenizer(
                "simplificar español: " + row["source"], return_tensors="pt", truncation=False
            )
            if inputs["input_ids"].shape[-1] > args.max_input_tokens:
                raise ValueError("Evaluation sentence exceeds configured token budget")
            with torch.inference_mode():
                output = model.generate(
                    **inputs,
                    max_new_tokens=args.max_new_tokens,
                    num_beams=args.num_beams,
                    do_sample=False,
                    no_repeat_ngram_size=4,
                    early_stopping=True,
                )
            row["prediction"] = tokenizer.decode(output[0], skip_special_tokens=True)
            durations.append(time.perf_counter() - started)
    result = evaluate_rows(rows)
    result["timing"] = timing_summary(durations)
    result["model_loading_seconds"] = load_seconds
    result["metadata"] = {
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "device": "cpu",
        "threads": args.threads,
        "max_input_tokens": args.max_input_tokens,
        "max_new_tokens": args.max_new_tokens,
        "num_beams": args.num_beams,
        "data_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
        "timing_scope": "tokenization + generation + decoding; no warmup excluded",
    }
    result["per_example"] = [
        {
            "document_id": row.get("document_id"),
            "category": row.get("category"),
            "original_score": measure(row["source"]).score,
            "adapted_score": measure(row["prediction"]).score
            if valid_prediction(row["prediction"])
            else None,
            "fidelity_guard": fidelity_ok(row["source"], row["prediction"]),
            "inference_seconds": durations[i] if durations else None,
        }
        for i, row in enumerate(rows)
    ]
    if args.hybrid:
        result["hybrid"] = asyncio.run(evaluate_hybrid(rows, model, tokenizer, args))
    if args.predictions_output:
        args.predictions_output.parent.mkdir(parents=True, exist_ok=True)
        args.predictions_output.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
        )
    if args.checkpoint:
        result["metadata"]["package_versions"] = {
            name: importlib.metadata.version(name) for name in ("torch", "transformers")
        }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
