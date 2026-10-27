"""One bounded in-memory index of all locally supplied EASIER annotations."""

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.nlp.segmentation import words
from app.nlp.syllables import count_syllables
from app.services.lexicon_es import CURATED
from ml_training.prepare_easier import load_rows, normalized

ROOT = Path(__file__).resolve().parents[2]
_STOP = set(
    "el la los las un una unos unas de del y en por para que con al es son se su sus".split()
)


@dataclass(frozen=True)
class CorpusCandidate:
    target: str
    context: frozenset[str]
    frequency: int


@dataclass(frozen=True)
class LexicalResources:
    corpus: dict
    statistics: dict
    inventory: dict


def _inventory(root):
    manifests = []
    for path in sorted((root / "checkpoints").glob("*/training_manifest.json"))[:20]:
        try:
            if path.stat().st_size > 262144:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            merged = path.parent / "merged"
            manifests.append(
                {
                    "name": path.parent.name,
                    "steps": data.get("global_steps"),
                    "weights_available": any(merged.glob("*.safetensors")),
                    "auto_activated": False,
                }
            )
        except (OSError, ValueError, TypeError):
            continue
    return {
        "training_code_available": (root / "ml_training/prepare_easier.py").is_file(),
        "checkpoints": manifests,
        "activation_policy": "configured_checkpoint_only; no unvalidated automatic activation",
    }


def load_resources(path=None, root=ROOT):
    path = Path(path) if path else root / "datasets/EASIER/SGSS.csv"
    stats = {
        "rows_read": 0,
        "accepted_annotations": 0,
        "rejected_annotations": 0,
        "curated_pairs": len(CURATED),
        "corpus_present": path.is_file(),
        "corpus_sha256": None,
        "corpus_status": "missing",
    }
    collected = defaultdict(list)
    frequencies = Counter()
    if path.is_file():
        stats["corpus_status"] = (
            "empty"
            if path.stat().st_size == 0
            else "oversized"
            if path.stat().st_size > 8 * 1024 * 1024
            else "loaded"
        )
    if stats["corpus_status"] == "loaded":
        stats["corpus_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        for row in load_rows(path, stats):
            source, target, context = row["word"].casefold(), row["synonyms"], row["source"]
            if not source or len(words(source)) > 6 or not context:
                stats["rejected_annotations"] += 1
                continue
            tokens = frozenset(
                normalized(token) for token in words(context) if normalized(token) not in _STOP
            )
            for item in target.split(","):
                item = item.strip().strip("\"'[] ")
                if not item or not re.fullmatch(r"[^\W\d_]+(?:[ -][^\W\d_]+){0,5}", item):
                    stats["rejected_annotations"] += 1
                    continue
                if normalized(source) == normalized(item):
                    continue
                collected[source].append((item.casefold(), tokens))
                frequencies[item.casefold()] += 1
                stats["accepted_annotations"] += 1
    index = {
        key: tuple(
            CorpusCandidate(target, context, frequencies[target]) for target, context in values
        )
        for key, values in collected.items()
    }
    stats["corpus_terms"] = len(index)
    stats["indexed_candidates"] = sum(len(values) for values in index.values())
    return LexicalResources(index, stats, _inventory(root))


@lru_cache(maxsize=1)
def resources():
    return load_resources()


def choose_corpus(source, text, level, context_tokens=None):
    """Corpus synonyms are sense-dependent: require substantial sentence overlap.

    No arbitrary top-frequency synonym gets applied globally to technical terms.
    """
    if level > 3:
        return None
    values = resources().corpus.get(source.casefold(), ())
    if not values:
        return None
    occurrences = re.findall(r"(?<!\w)" + re.escape(source) + r"(?!\w)", text, flags=re.I)
    if len(occurrences) != 1:
        return None
    tokens = (
        context_tokens
        if context_tokens is not None
        else {normalized(token) for token in words(text) if normalized(token) not in _STOP}
    )
    candidates = []
    for candidate in values:
        context = set(candidate.context) - {normalized(source)}
        overlap = len(context & tokens) / max(1, len(context))
        if overlap < 0.65 or len(context & tokens) < 3:
            continue
        old = sum(count_syllables(word) for word in words(source))
        new = sum(count_syllables(word) for word in words(candidate.target))
        if new >= old or len(candidate.target) > len(source) + 4:
            continue
        candidates.append(
            (new, -math.log1p(candidate.frequency), len(candidate.target), candidate.target)
        )
    return min(candidates)[-1] if candidates else None
