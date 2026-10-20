"""Select a reproducible, document-disjoint EASIER research subset by token budget."""

import argparse
import hashlib
import json
from pathlib import Path

from app.nlp.segmentation import words


def select_rows(rows, tokenizer, count, seed=42, max_tokens=96):
    if count <= 0 or max_tokens <= 0:
        raise ValueError("Subset size and token budget must be positive")
    selected = []
    documents = set()
    sources = set()
    for row in sorted(
        rows,
        key=lambda value: hashlib.sha256(
            f"{seed}:{value['document_id']}:{value['source']}:{value['target']}".encode()
        ).hexdigest(),
    ):
        if row["document_id"] in documents or row["source"] in sources:
            continue
        if not 20 <= len(words(row["source"])) <= 45:
            continue
        if (
            len(tokenizer.encode("simplificar español: " + row["source"])) > max_tokens
            or len(tokenizer.encode(row["target"])) > max_tokens
        ):
            continue
        selected.append(row)
        documents.add(row["document_id"])
        sources.add(row["source"])
        if len(selected) == count:
            break
    if len(selected) != count:
        raise ValueError("Insufficient document-disjoint examples within token budget")
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--train", type=int, default=24)
    parser.add_argument("--validation", type=int, default=4)
    parser.add_argument("--test", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-tokens", type=int, default=96)
    args = parser.parse_args()
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        args.tokenizer, local_files_only=True, trust_remote_code=False, use_fast=False
    )
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.data / "manifest.json").read_text(encoding="utf-8"))
    manifest["subset"] = {
        "seed": args.seed,
        "max_tokens": args.max_tokens,
        "min_words": 20,
        "max_words": 45,
    }
    manifest["selected_documents"] = {}
    for split in ("train", "validation", "test"):
        rows = [
            json.loads(line)
            for line in (args.data / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        selected = select_rows(rows, tokenizer, getattr(args, split), args.seed, args.max_tokens)
        content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected)
        (args.output / f"{split}.jsonl").write_text(content, encoding="utf-8")
        manifest["counts"][split] = len(selected)
        manifest["selected_documents"][split] = sorted(row["document_id"] for row in selected)
        manifest.setdefault("split_sha256", {})[split] = hashlib.sha256(
            content.encode()
        ).hexdigest()
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest["counts"]))


if __name__ == "__main__":
    main()
