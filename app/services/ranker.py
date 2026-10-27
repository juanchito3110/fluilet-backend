"""Versioned fitted rankers; dependency-free inference and bounded JSON loading."""

import hashlib
import json
import math
import re
from functools import lru_cache
from pathlib import Path

from app.nlp.readability import measure
from app.nlp.segmentation import words
from app.nlp.syllables import count_syllables

ASSET = Path(__file__).parent / "assets/context-ranker-v2.1.json"
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
    from app.config import settings

    path = Path(settings.RANKER_CHECKPOINT) if settings.RANKER_CHECKPOINT else ASSET
    if not path.is_file():
        if settings.RANKER_CHECKPOINT:
            raise RuntimeError("Configured ranker checkpoint missing")
        return None
    if path.stat().st_size > 1024 * 1024:
        raise RuntimeError("Invalid ranker artifact size")
    raw = path.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    if settings.RANKER_CHECKPOINT_SHA256 and checksum != settings.RANKER_CHECKPOINT_SHA256:
        raise RuntimeError("Ranker checksum mismatch")
    data = json.loads(raw)
    if data.get("model_version") not in {MODEL_VERSION, "context-ranker-es-v2.1"}:
        raise RuntimeError("Incompatible ranker artifact")
    if "joint_model" in data:
        from app.services.joint import FEATURE_NAMES

        joint = data["joint_model"]
        if joint["features"] != list(FEATURE_NAMES):
            raise RuntimeError("Incompatible joint features")
        for weights in [joint["lexical"], *joint["heads"].values()]:
            if len(weights) != len(FEATURE_NAMES) or not all(math.isfinite(v) for v in weights):
                raise RuntimeError("Invalid joint weights")

        def validate_tree(node, depth=0):
            if depth > 8:
                raise RuntimeError("Invalid tree depth")
            if "value" in node:
                if len(node["value"]) != 4 or not all(math.isfinite(v) for v in node["value"]):
                    raise RuntimeError("Invalid tree leaf")
            else:
                if (
                    not isinstance(node["feature"], int)
                    or not 0 <= node["feature"] < len(FEATURE_NAMES)
                    or not math.isfinite(node["threshold"])
                ):
                    raise RuntimeError("Invalid tree split")
                validate_tree(node["left"], depth + 1)
                validate_tree(node["right"], depth + 1)

        if len(joint.get("trees", [])) > 100:
            raise RuntimeError("Invalid tree count")
        for tree in joint.get("trees", []):
            validate_tree(tree)
        data["_artifact_sha256"] = checksum
        return data
    if data.get("structural_features") != list(FEATURES):
        raise RuntimeError("Incompatible legacy features")
    for key, size in (("lexical_weights", 24), ("structural_weights", len(FEATURES))):
        if len(data[key]) != size or not all(
            isinstance(v, (int, float)) and math.isfinite(v) for v in data[key]
        ):
            raise RuntimeError("Invalid ranker weights")
    data["_artifact_sha256"] = checksum
    return data


def lexical_probability(source, target, context):
    model = checkpoint()
    if model and "joint_model" in model:
        from app.services.joint import probability

        return probability(model["joint_model"], source, target, context)
    return (
        predict(model["lexical_weights"], lexical_features(source, target, context))
        if model
        else 0.0
    )


def quality(source, target, level, original=None, adapted=None):
    model = checkpoint()
    if model and "joint_model" in model:
        from app.services.joint import prediction

        return prediction(model["joint_model"], source, target, level, original, adapted)
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
        "model_version": model["model_version"],
        "checkpoint_name": model["checkpoint_name"],
        "active": True,
        "artifact_sha256": model["_artifact_sha256"],
    }
