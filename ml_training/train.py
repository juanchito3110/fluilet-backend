"""Offline reproducible mT5 supervised fine-tuning. Run from repository root."""

import argparse
import hashlib
import importlib.metadata
import json
import math
import sys
import time
from pathlib import Path


def peak_rss_bytes():
    try:
        import resource
    except ImportError:
        return None
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (
        1 if sys.platform == "darwin" else 1024
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("ml_training/configs/mt5_small.yaml"))
    parser.add_argument("--data", type=Path, default=Path("ml_training/data"))
    parser.add_argument("--output", type=Path, default=Path("checkpoints/mt5-fluilet"))
    args = parser.parse_args()
    import torch
    import yaml
    from datasets import load_dataset
    from transformers import (
        AutoModelForSeq2SeqLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
        set_seed,
    )

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    set_seed(config["seed"])
    torch.set_num_threads(config.get("torch_threads", 2))
    load_started = time.perf_counter()
    data = load_dataset(
        "json",
        data_files={
            split: str(args.data / f"{split}.jsonl") for split in ("train", "validation", "test")
        },
    )
    if any(not len(data[split]) for split in data):
        raise ValueError("All three document-separated partitions must be nonempty.")
    # Fail if a prepared dataset was edited in a way that leaks source sentences.
    for first, second in (("train", "validation"), ("train", "test"), ("validation", "test")):
        for key in ("document_id", "source"):
            if set(data[first][key]) & set(data[second][key]):
                raise ValueError("Dataset split leakage detected.")
    load_options = {
        "trust_remote_code": False,
        "local_files_only": config.get("local_files_only", False),
    }
    if config.get("model_revision"):
        load_options["revision"] = config["model_revision"]
    tokenizer = AutoTokenizer.from_pretrained(config["model_name"], use_fast=False, **load_options)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        config["model_name"], use_safetensors=None, weights_only=True, **load_options
    )

    if config.get("lora_rank"):
        from peft import LoraConfig, TaskType, get_peft_model

        model = get_peft_model(
            model,
            LoraConfig(
                task_type=TaskType.SEQ_2_SEQ_LM,
                r=config["lora_rank"],
                lora_alpha=config.get("lora_alpha", 8),
                lora_dropout=0.0,
                target_modules=config.get("lora_target_modules", ["q", "v"]),
                bias="none",
            ),
        )
    trainable = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    total = sum(parameter.numel() for parameter in model.parameters())

    def trainable_digest():
        digest = hashlib.sha256()
        for name, parameter in model.named_parameters():
            if parameter.requires_grad:
                digest.update(name.encode())
                digest.update(parameter.detach().cpu().contiguous().numpy().tobytes())
        return digest.hexdigest()

    initial_digest = trainable_digest()
    loading_seconds = time.perf_counter() - load_started

    def tokenize(batch):
        inputs = tokenizer(
            ["simplificar español: " + text for text in batch["source"]], truncation=False
        )
        labels = tokenizer(text_target=batch["target"], truncation=False)
        # Explicitly filter long examples rather than silently train on cut sentences.
        return {**inputs, "labels": labels["input_ids"]}

    encoded = data.map(tokenize, batched=True, remove_columns=data["train"].column_names)
    encoded = encoded.filter(
        lambda row: (
            len(row["input_ids"]) <= config["max_input_tokens"]
            and len(row["labels"]) <= config["max_target_tokens"]
        )
    )
    if any(not len(encoded[split]) for split in encoded):
        raise ValueError("A partition is empty after token-budget filtering.")
    train_args = Seq2SeqTrainingArguments(
        output_dir=str(args.output),
        seed=config["seed"],
        data_seed=config["seed"],
        learning_rate=config["learning_rate"],
        num_train_epochs=config["num_train_epochs"],
        per_device_train_batch_size=config["per_device_train_batch_size"],
        per_device_eval_batch_size=config["per_device_eval_batch_size"],
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        weight_decay=config["weight_decay"],
        max_steps=config.get("max_steps", -1),
        use_cpu=config.get("use_cpu", False),
        eval_strategy="steps" if config.get("max_steps", -1) > 0 else "epoch",
        eval_steps=config.get("eval_steps", config.get("max_steps", 500)),
        save_strategy="no" if config.get("max_steps", -1) > 0 else "epoch",
        load_best_model_at_end=config.get("max_steps", -1) <= 0,
        save_total_limit=config["save_total_limit"],
        report_to=[],
        logging_steps=1 if config.get("max_steps", -1) > 0 else 25,
        disable_tqdm=True,
        dataloader_pin_memory=not config.get("use_cpu", False),
        optim="adamw_torch",
        dataloader_num_workers=0,
        predict_with_generate=False,
    )
    trainer = Seq2SeqTrainer(
        model=model,
        args=train_args,
        train_dataset=encoded["train"],
        eval_dataset=encoded["validation"],
        processing_class=tokenizer,
        data_collator=DataCollatorForSeq2Seq(tokenizer, model=model),
    )
    training_started = time.perf_counter()
    training_result = trainer.train()
    training_seconds = time.perf_counter() - training_started
    if not math.isfinite(training_result.training_loss) or any(
        not torch.isfinite(parameter).all()
        for parameter in model.parameters()
        if parameter.requires_grad
    ):
        raise RuntimeError("Nonfinite training result; refusing checkpoint")
    final_digest = trainable_digest()
    if final_digest == initial_digest:
        raise RuntimeError("No trainable weights changed; refusing to label run as fine-tuning")
    if config.get("lora_rank"):
        model.save_pretrained(args.output, safe_serialization=True, save_embedding_layers=False)
    else:
        trainer.save_model(str(args.output))
    tokenizer.save_pretrained(args.output)
    manifest = {
        "config": config,
        "global_steps": trainer.state.global_step,
        "device": str(trainer.args.device),
        "peak_process_rss_bytes": peak_rss_bytes(),
        "trainable_parameters": trainable,
        "total_parameters": total,
        "trainable_sha256_before": initial_digest,
        "trainable_sha256_after": final_digest,
        "model_loading_seconds": loading_seconds,
        "training_seconds": training_seconds,
        "training_metrics": training_result.metrics,
        "final_validation_metrics": next(
            metrics for metrics in reversed(trainer.state.log_history) if "eval_loss" in metrics
        ),
        "source_manifest": json.loads((args.data / "manifest.json").read_text(encoding="utf-8")),
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "package_versions": {
            name: importlib.metadata.version(name)
            for name in ("torch", "transformers", "datasets", "accelerate", "peft")
        },
        "base_model_revision": getattr(model.config, "_commit_hash", None),
        "evaluation": trainer.evaluate(encoded["test"], metric_key_prefix="test"),
    }
    if config.get("lora_rank") and config.get("merge_lora"):
        merged = model.merge_and_unload()
        merged.config.use_cache = True
        merged.save_pretrained(args.output / "merged", safe_serialization=True)
        tokenizer.save_pretrained(args.output / "merged")
        manifest["merged_checkpoint"] = "merged"
    manifest["peak_process_rss_bytes"] = peak_rss_bytes()
    (args.output / "training_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
