"""Reference-free features and joint v2.1 inference. No labels at request time."""

import math
import re
from difflib import SequenceMatcher

from app.nlp.readability import measure
from app.nlp.segmentation import words
from app.services.morphology import entries

SIGNATURES = {source: (tense, person) for _, source, _, tense, person in entries()}
SIGNATURES.update({target: (tense, person) for _, _, target, tense, person in entries()})
FEATURE_NAMES = (
    "bias",
    "identity",
    "word_ratio",
    "syllable_ratio",
    "sentence_ratio",
    "gain",
    "band_distance",
    "length_distance",
    "overlap",
    "edit_fraction",
    "edit_groups",
    "number_match",
    "negation_match",
    "morphology",
    "verb_signature_known",
    "plural_match",
    "source_syllables",
    "target_syllables",
    "level",
    "is_phrase",
    "character_ratio",
    "one_edit",
    "many_edits",
    "gain_squared",
    "band_squared",
    "edit_squared",
    "edit_position",
    "old_span_syllables",
    "new_span_syllables",
    "old_span_length",
    "new_span_length",
)


def morphology(source, target):
    a, b = source.casefold(), target.casefold()
    first, second = SIGNATURES.get(a), SIGNATURES.get(b)
    known = first is not None and second is not None
    return (
        float(first == second) if known else 0.5,
        float(known),
        float(a.endswith("s") == b.endswith("s")),
    )


def features(source, target, level, original=None, adapted=None):
    from app.services.pedagogy import GOALS

    a, b = original or measure(source), adapted or measure(target)
    before, after = words(source.lower()), words(target.lower())
    matcher = SequenceMatcher(a=before, b=after, autojunk=len(before) > 2000)
    edits = [op for op in matcher.get_opcodes() if op[0] != "equal"]
    fraction = sum(max(j - i, end - k) for _, i, j, k, end in edits) / max(1, len(before))
    morph, known, plural = morphology(source, target)
    if len(edits) == 1:
        _, i, j, k, end = edits[0]
        morph, known, plural = morphology(" ".join(before[i:j]), " ".join(after[k:end]))
    lower, upper, min_words, max_words = GOALS[level]
    distance = max(0, lower - b.score, b.score - upper) / 100
    length = b.word_count / b.sentence_count
    gap = max(0, min_words - length, length - max_words) / 30
    gain = (b.score - a.score) / 100

    def number(text):
        return re.findall(r"\d+(?:[.,]\d+)*", text)

    def neg(text):
        return [w for w in words(text.casefold()) if w in {"no", "nunca", "jamás", "ni"}]

    ratio = b.word_count / a.word_count
    vector = [
        1,
        float(before == after),
        ratio,
        (b.syllable_count / b.word_count) / (a.syllable_count / a.word_count),
        b.sentence_count / a.sentence_count,
        gain,
        distance,
        gap,
        len(set(before) & set(after)) / max(1, len(set(before) | set(after))),
        fraction,
        len(edits) / 10,
        float(number(source) == number(target)),
        float(neg(source) == neg(target)),
        morph,
        known,
        plural,
        a.syllable_count / a.word_count / 5,
        b.syllable_count / b.word_count / 5,
        level / 5,
        float(len(before) > 1),
        len(target) / max(1, len(source)),
        float(len(edits) == 1),
        float(len(edits) > 2),
        gain * gain,
        distance * distance,
        fraction * fraction,
    ]
    from app.nlp.syllables import count_syllables

    old_span = [w for _, i, j, _, _ in edits for w in before[i:j]]
    new_span = [w for _, _, _, start, end in edits for w in after[start:end]]
    vector.extend(
        [
            edits[0][1] / max(1, len(before)) if edits else 0,
            sum(count_syllables(w) for w in old_span) / max(1, len(old_span)) / 5,
            sum(count_syllables(w) for w in new_span) / max(1, len(new_span)) / 5,
            len(old_span) / max(1, len(before)),
            len(new_span) / max(1, len(after)),
        ]
    )
    return [max(-5, min(5, float(x))) for x in vector]


def score(weights, vector):
    return sum(w * x for w, x in zip(weights, vector, strict=True))


def sari_vector(vector):
    # SARI tokenization ignores punctuation: predicted keep/add/delete must not
    # depend on sentence boundaries, age/level, or the target readability band.
    excluded = {4, 5, 6, 7, 18, 20, 23, 24}
    return [0.0 if i in excluded else value for i, value in enumerate(vector)]


def prediction(model, source, target, level, original=None, adapted=None):
    vector = features(source, target, level, original, adapted)
    heads = model["heads"]
    invariant = sari_vector(vector)
    # Directly estimated SARI components plus learned compression utility.
    values = [
        score(heads[name], invariant if name != "utility" else vector)
        for name in ("keep", "add", "delete", "utility")
    ]
    for tree in model.get("trees", []):
        node = tree
        while "value" not in node:
            node = (
                node["left"] if invariant[node["feature"]] <= node["threshold"] else node["right"]
            )
        values = [a + model["tree_rate"] * b for a, b in zip(values, node["value"], strict=True)]
    sari = sum(max(0, min(1, v)) for v in values[:3]) / 3
    utility = values[3]
    mix = model.get("sari_mix", 0.5)
    return mix * sari + (1 - mix) * utility


def lexical_features(source, target, context):
    # Context determines edit fraction and sentence structure. No reference target.
    match = re.search(r"(?<!\w)" + re.escape(source) + r"(?!\w)", context, re.I)
    if match:
        candidate = context[: match.start()] + target + context[match.end() :]
        vector = features(context, candidate, 3)
    else:
        vector = features(source, target, 3)
    morph, known, plural = morphology(source, target)
    vector[13:16] = morph, known, plural
    return vector


def probability(model, source, target, context):
    value = score(model["lexical"], lexical_features(source, target, context))
    return 1 / (1 + math.exp(-max(-30, min(30, value))))
