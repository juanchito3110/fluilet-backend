"""Small genuinely trained two-head ranker; dependency-free, bounded JSON loading."""

import hashlib
import json
import math
import re
from functools import lru_cache
from pathlib import Path

from app.nlp.readability import measure
from app.nlp.segmentation import words
from app.nlp.syllables import count_syllables

ASSET = Path(__file__).parent / "assets/context-ranker-v2.json"
MODEL_VERSION = "context-ranker-es-v2"
FEATURES = (
    "bias",
    "word_ratio",
    "syllable_ratio",
    "sentence_ratio",
    "unigram_overlap",
    "number_match",
    "negation_match",
    "gain",
    "target_distance",
    "sentence_length",
    "level",
    "character_ratio",
) + tuple(f"context_{i}" for i in range(16))


def sigmoid(value):
    return 1 / (1 + math.exp(-max(-30, min(30, value))))


def lexical_features(source, target, context):
    a, b = words(source.lower()), words(target.lower())
    old = sum(count_syllables(w) for w in a) or 1
    new = sum(count_syllables(w) for w in b)
    features = [
        1,
        len(b) / max(1, len(a)),
        new / old,
        (old - new) / old,
        len(target) / max(1, len(source)),
        float(source.lower() == target.lower()),
        float(bool(re.search(r"\d", target))),
        float(source[:1].isupper()),
    ]
    context_words = set(words(context.lower())) - set(a)
    features.extend([0.0] * 16)
    for token in context_words:
        index = (
            int(hashlib.sha256((token + ":" + target.lower()).encode()).hexdigest()[:8], 16) % 16
        )
        features[8 + index] += 1 / max(1, len(context_words))
    return features


def structural_features(source, target, level):
    a, b = measure(source), measure(target)
    aw, bw = set(words(source.lower())), set(words(target.lower()))
    target_score = {1: 91, 2: 79, 3: 69.5, 4: 62, 5: 57.5}[level]

    def numbers(s):
        return re.findall(r"\d+(?:[.,]\d+)*", s)

    def negations(s):
        return [w for w in words(s.lower()) if w in {"no", "nunca", "sin", "jamás", "ni"}]

    result = [
        1,
        b.word_count / a.word_count,
        (b.syllable_count / b.word_count) / (a.syllable_count / a.word_count),
        b.sentence_count / a.sentence_count,
        len(aw & bw) / max(1, len(aw | bw)),
        float(numbers(source) == numbers(target)),
        float(negations(source) == negations(target)),
        (b.score - a.score) / 50,
        abs(b.score - target_score) / 100,
        b.word_count / b.sentence_count / 30,
        level / 5,
        len(target) / max(1, len(source)),
    ]
    result.extend([0.0] * 16)
    for token in aw:
        index = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % 16
        result[12 + index] += 1 / max(1, len(aw))
    return [max(-5, min(5, x)) for x in result]


def predict(weights, features):
    return sigmoid(sum(a * b for a, b in zip(weights, features, strict=True)))


@lru_cache(maxsize=1)
def checkpoint():
    if not ASSET.is_file():
        return None
    if ASSET.stat().st_size > 262144:
        raise RuntimeError("Invalid ranker artifact size")
    data = json.loads(ASSET.read_text())
    if data.get("model_version") != MODEL_VERSION or data.get("structural_features") != list(
        FEATURES
    ):
        raise RuntimeError("Incompatible ranker artifact")
    for key, size in (("lexical_weights", 24), ("structural_weights", len(FEATURES))):
        if len(data[key]) != size or not all(
            isinstance(v, (int, float)) and math.isfinite(v) for v in data[key]
        ):
            raise RuntimeError("Invalid ranker weights")
    return data


def lexical_probability(source, target, context):
    model = checkpoint()
    return (
        predict(model["lexical_weights"], lexical_features(source, target, context))
        if model
        else 0.0
    )


def quality(source, target, level):
    model = checkpoint()
    return (
        predict(model["structural_weights"], structural_features(source, target, level))
        if model
        else 0.0
    )


def model_info():
    model = checkpoint()
    if not model:
        return {"model_version": "unavailable", "checkpoint_name": None, "active": False}
    return {
        **model["metrics"],
        "model_version": MODEL_VERSION,
        "checkpoint_name": model["checkpoint_name"],
        "active": True,
        "artifact_sha256": hashlib.sha256(ASSET.read_bytes()).hexdigest(),
    }
