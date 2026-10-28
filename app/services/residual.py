"""Lexical/SARI selection independent of readability bands and requested age.

All corpus priors come from the training partition, including when selecting on
validation/test. No reference, label, age or band is available to this module.
"""

import hashlib
import math
from difflib import SequenceMatcher

from app.nlp.segmentation import words
from app.services.joint import FEATURE_NAMES, features, morphology, sari_vector

NAMES = (
    *FEATURE_NAMES,
    "corpus_rank",
    "train_frequency",
    "root_overlap",
    "gender",
    "number",
    "word_frequency_gain",
)


def digest(value):
    return hashlib.sha256(value.casefold().encode()).hexdigest()


def vector(source, target, priors, *, span=None, base=None):
    result = (
        list(base[: len(FEATURE_NAMES)])
        if base is not None
        else sari_vector(features(source, target, 3))
    )
    if span:
        spans = [span]
        result[13:16] = morphology(*span)
    else:
        before, after = words(source.casefold()), words(target.casefold())
        edits = (
            []
            if before == after
            else [
                op
                for op in SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes()
                if op[0] != "equal"
            ]
        )
        spans = [(" ".join(before[a:b]), " ".join(after[c:d])) for _, a, b, c, d in edits]
    ranks, frequencies, roots, genders, numbers, gains = [], [], [], [], [], []
    for old, new in spans:
        options = priors.get("pairs", {}).get(digest(old), {})
        count = options.get(digest(new), 0)
        ranks.append(1 / (1 + sum(n > count for n in options.values())) if count else 0)
        frequencies.append(math.log1p(priors.get("counts", {}).get(digest(new), 0)) / 10)
        roots.append(SequenceMatcher(a=old, b=new, autojunk=False).ratio())
        genders.append(float(old.endswith("a") == new.endswith("a")))
        numbers.append(float(old.endswith("s") == new.endswith("s")))

        def frequency(text):
            tokens = words(text)
            return sum(
                math.log1p(priors.get("word_counts", {}).get(digest(w), 0)) for w in tokens
            ) / max(1, len(tokens))

        gains.append((frequency(new) - frequency(old)) / 10)

    def average(values):
        return sum(values) / len(values) if values else 0

    return result + [
        average(values) for values in (ranks, frequencies, roots, genders, numbers, gains)
    ]


def estimate(model, x):
    value = sum(a * b for a, b in zip(model["weights"], x, strict=True))
    for tree in model.get("trees", []):
        node = tree
        while "value" not in node:
            node = node["left"] if x[node["feature"]] <= node["threshold"] else node["right"]
        value += model["rate"] * node["value"][0]
    return value


def quality(model, source, target):
    x = vector(source, target, model["priors"])
    value = estimate(model, x)
    if model.get("lexical_weights"):
        confidence, edits = lexical_summary(model, source, target, base=x)
        value += model.get("lexical_blend", 0) * confidence - model.get("edit_cost", 0) * edits
    return value


def lexical_summary(model, source, target, *, base=None):
    before, after = words(source.casefold()), words(target.casefold())
    if before == after:
        return 0.0, 0.0
    spans = [
        (" ".join(before[a:b]), " ".join(after[c:d]))
        for tag, a, b, c, d in SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes()
        if tag != "equal"
    ]
    values = []
    for old, new in spans:
        x = vector(source, target, model["priors"], span=(old, new), base=base)
        logit = sum(a * b for a, b in zip(model["lexical_weights"], x, strict=True))
        values.append(2 / (1 + math.exp(-max(-30, min(30, logit)))) - 1)
    return (sum(values) / len(values) if values else 0, math.log1p(len(values)))


def select(model, source, options):
    """Validation-fitted minimum predicted SARI gain over identity, no band term."""
    identity = quality(model, source, source)
    selected = max(options, key=lambda text: quality(model, source, text))
    return selected if quality(model, source, selected) > identity + model["margin"] else source
