"""Source-only selective override of a documented untrained fallback.

The fallback is the frozen fc12a7a implementation of the historical heuristic:
untrained candidate generation, then closest score to the supplied level. The
gate never sees a reference or a band penalty; its two margins concern predicted
SARI gain and contextual-ranker confidence. This is not a corpus annotation #0.
"""

import math
import re
from collections import Counter
from difflib import SequenceMatcher

from app.nlp.readability import measure
from app.nlp.segmentation import words
from app.services.residual import quality, select, vector

NAMES = (
    "bias",
    "ranker_margin",
    "top_syllable_reduction",
    "base_syllable_reduction",
    "length_ratio",
    "top_morphology",
    "base_morphology",
    "morphology_delta",
    "top_plural",
    "base_plural",
    "pair_overlap",
    "top_edits",
    "base_edits",
    "top_identity",
    "base_identity",
    "root_delta",
    "frequency_delta",
    "inverse_source_words",
    "top_corpus_rank",
    "base_corpus_rank",
    "top_train_frequency",
    "base_train_frequency",
    "top_root",
    "base_root",
    "top_word_frequency",
    "base_word_frequency",
    "top_edit_fraction",
    "base_edit_fraction",
    "top_character_ratio",
    "base_character_ratio",
)


def base_candidate(source, level, options=None):
    from app.services.frozen_v2.rewriting import candidates
    from app.services.pedagogy import GOALS

    options = options if options is not None else candidates(source, [0.0] * 24)
    center = sum(GOALS[level][:2]) / 2
    chosen = min(options, key=lambda text: (abs(measure(text).score - center), text))

    def numbers(text):
        return Counter(re.findall(r"\d+(?:[.,]\d+)*", text))

    if re.search(r"\bno\s+no\b", chosen, re.I) or numbers(source) != numbers(chosen):
        return source
    return chosen


def pair_features(model, source, top, base):
    tx, bx = vector(source, top, model["priors"]), vector(source, base, model["priors"])
    tw, bw = words(top.casefold()), words(base.casefold())
    overlap = SequenceMatcher(a=tw, b=bw, autojunk=len(tw) > 2000).ratio()
    return [
        float(value)
        for value in (
            1,
            quality(model, source, top) - quality(model, source, base),
            1 - tx[3],
            1 - bx[3],
            len(tw) / max(1, len(bw)),
            tx[13],
            bx[13],
            tx[13] - bx[13],
            tx[15],
            bx[15],
            overlap,
            tx[10],
            bx[10],
            tx[1],
            bx[1],
            tx[33] - bx[33],
            tx[36] - bx[36],
            1 / max(1, len(words(source))),
            tx[31],
            bx[31],
            tx[32],
            bx[32],
            tx[33],
            bx[33],
            tx[36],
            bx[36],
            tx[9],
            bx[9],
            tx[20],
            bx[20],
        )
    ]


def predict(weights, features):
    return sum(w * x for w, x in zip(weights, features, strict=True))


def decision(gate, features):
    gain = predict(gate["gain_weights"], features)
    for tree in gate.get("trees", []):
        node = tree
        while "value" not in node:
            node = node["left" if features[node["feature"]] <= node["threshold"] else "right"]
        gain += gate["tree_rate"] * node["value"][0]
    logit = predict(gate["positive_weights"], features)
    probability = 1 / (1 + math.exp(-max(-30, min(30, logit))))
    return (
        gain > gate["gain_margin"]
        and features[1] > gate["ranker_margin"]
        and features[2] > gate["syllable_floor"]
        and probability >= gate["positive_threshold"]
    )


def choose(model, source, options, level, baseline_options=None):
    top = select(model, source, options)
    base = base_candidate(source, level, baseline_options)
    if top == base:
        return top, "agreement"
    x = pair_features(model, source, top, base)
    override = decision(model["selective_gate"], x)
    return (top, "contextual_override") if override else (base, "base_retained")


def candidate_pool(source):
    """Exactly the source-only pool used for the separated ranker's evaluation."""
    from app.services.rewriting import apply, candidates, operations

    values = set(candidates(source, [0.0] * 24))
    values.update(apply(source, [op]) for op in operations(source, [0.0] * 24))
    return sorted(values)
