"""Prepare derived lexical pairs from official EASIER SG/SS annotations.

Handles the repository's semicolon CSV (including CP1252) and documented TSV.
Only supplied, licensed research data is read. No network/download/API text.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
from pathlib import Path


def normalized(value):
    return "".join(
        c for c in unicodedata.normalize("NFD", value.casefold()) if not unicodedata.combining(c)
    ).strip()


def load_rows(path: Path):
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    delimiter = "\t" if "\t" in text.splitlines()[0] else ";"
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)
    for row in reader:
        row = {normalized(k): (v or "").strip() for k, v in row.items() if k is not None}
        yield {
            "document_id": row.get("document_id", row.get("doc_id", "")),
            "source": row.get("sentence", ""),
            "word": row.get("word", ""),
            "synonyms": row.get("sinonimos", row.get("synonyms", "")),
        }


def split_for(document_id, seed):
    value = int(hashlib.sha256(f"{seed}:{document_id}".encode()).hexdigest(), 16) % 100
    return "train" if value < 80 else "validation" if value < 90 else "test"


def prepare(path: Path, seed=42):
    partitions = {name: [] for name in ("train", "validation", "test")}
    owners = {}
    seen = set()
    for row in load_rows(path):
        source, target_word, document_id = row["source"], row["word"], row["document_id"]
        if not source or not target_word or not document_id:
            continue
        key = " ".join(source.casefold().split())
        # Repeated source sentences in different documents belong to one owner.
        owner = owners.setdefault(key, document_id)
        pattern = re.compile(r"(?<!\w)" + re.escape(target_word) + r"(?!\w)", re.I)
        matches = list(pattern.finditer(source))
        if len(matches) != 1:
            continue
        match = matches[0]
        for synonym in row["synonyms"].split(","):
            synonym = synonym.strip().strip("\"'[] ")
            if not synonym or normalized(synonym) == normalized(target_word):
                continue
            if source[match.start()].isupper():
                synonym = synonym[0].upper() + synonym[1:]
            target = source[: match.start()] + synonym + source[match.end() :]
            pair = (source, target)
            if pair in seen:
                continue
            seen.add(pair)
            partitions[split_for(owner, seed)].append(
                {
                    "source": source,
                    "target": target,
                    "document_id": owner,
                    "annotation": "derived_lexical_substitution",
                }
            )
    return partitions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sgss", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("ml_training/data"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    partitions = prepare(args.sgss, args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    for split, rows in partitions.items():
        with (args.output / f"{split}.jsonl").open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "source_sha256": hashlib.sha256(args.sgss.read_bytes()).hexdigest(),
        "seed": args.seed,
        "counts": {split: len(rows) for split, rows in partitions.items()},
        "license_declared_by_source": "CC BY-NC-ND 4.0",
        "pair_type": "derived_lexical_substitution",
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest["counts"]))


if __name__ == "__main__":
    main()
