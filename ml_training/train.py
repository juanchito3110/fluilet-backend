"""Offline reproducible mT5 supervised fine-tuning. Run from repository root."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("ml_training/configs/mt5_small.yaml"))
    parser.add_argument("--data", type=Path, default=Path("ml_training/data"))
    parser.add_argument("--output", type=Path, default=Path("checkpoints/mt5-fluilet"))
    args = parser.parse_args()
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

    config = yaml.safe_load(args.config.read_text())
    set_seed(config["seed"])
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
    tokenizer = AutoTokenizer.from_pretrained(config["model_name"], trust_remote_code=False)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        config["model_name"], trust_remote_code=False, use_safetensors=None, weights_only=True
    )

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
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        save_total_limit=config["save_total_limit"],
        report_to=[],
        logging_steps=25,
        dataloader_num_workers=0,
        predict_with_generate=True,
    )
    trainer = Seq2SeqTrainer(
        model=model,
        args=train_args,
        train_dataset=encoded["train"],
        eval_dataset=encoded["validation"],
        processing_class=tokenizer,
        data_collator=DataCollatorForSeq2Seq(tokenizer, model=model),
    )
    trainer.train()
    trainer.save_model(str(args.output))
    tokenizer.save_pretrained(args.output)
    manifest = {
        "config": config,
        "source_manifest": json.loads((args.data / "manifest.json").read_text()),
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "package_versions": {
            name: importlib.metadata.version(name)
            for name in ("torch", "transformers", "datasets", "accelerate")
        },
        "base_model_revision": getattr(model.config, "_commit_hash", None),
        "evaluation": trainer.evaluate(encoded["test"], metric_key_prefix="test"),
    }
    (args.output / "training_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
