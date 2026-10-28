"""Compositional candidate generation, ranked by learned weights.

Every operation is bounded to an explicit phrase or independent clause. No
document-id/topic lookup, arbitrary word cutting or deletion of clinical scope.
"""

import re

from app.nlp.segmentation import sentences
from app.services.frozen_v2.lexicon_es import CURATED
from app.services.frozen_v2.morphology import FORMS, VERBS, family
from app.services.frozen_v2.refinement import LEXICON, PHRASES, refine
from app.services.ranker import lexical_features, lexical_probability, predict


def operations(text, weights=None):
    mapping = {key.casefold(): value for key, value in {**LEXICON, **PHRASES, **CURATED}.items()}
    mapping.update({s: t for s, t in FORMS.items() if family(s) in VERBS})
    # Grammatical locutions, with number/gender and scope unchanged.
    mapping.update(
        {
            "años de edad": "años",
            "personas de entre": "personas entre",
            "participación e involucración": "participación y compromiso",
        }
    )
    pattern = re.compile(
        r"(?<!\w)(?:"
        + "|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True))
        + r")(?!\w)",
        re.I,
    )
    result = []
    for match in pattern.finditer(text):
        source = match[0]
        target = mapping[source.lower()]
        if source[0].isupper():
            target = target.capitalize()
        confidence = (
            predict(weights, lexical_features(source, target, text))
            if weights is not None
            else lexical_probability(source, target, text)
        )
        # This dictionary is an allow-list; learned confidence orders its edits.
        # A poorly calibrated probability must not turn a reviewed pair into an
        # unsupported synonym. Unknown synonyms are never invented here.
        if confidence > 0:
            result.append((match.start(), match.end(), target, confidence))
    return result


def apply(text, ops):
    for start, end, target, _ in sorted(ops, reverse=True):
        text = text[:start] + target + text[end:]
    return text


def split_clauses(text):
    result = []
    for sentence in sentences(text):
        # A modal concessive remains modal, then retains its contrast.
        match = re.match(
            r"^(?:Y )?[Aa]unque (?P<scope>(?:también )?puede [^,;]+),\s+(?P<main>.+)$", sentence
        )
        if match:
            sentence = match["scope"].capitalize() + ". Sin embargo, " + match["main"]
        # Coordinated independent clauses with an explicit article/pronoun.
        sentence = re.sub(
            r";\s+(?=(?:el|la|los|las|un|una|él|ella|ellos|ellas)\b)", ". ", sentence, flags=re.I
        )
        sentence = re.sub(r",\s+por lo que\s+", ". Por eso, ", sentence)
        result.append(sentence)
    return " ".join(result)


def candidates(text, weights=None):
    original = text
    text = " ".join(text.split())
    ops = operations(text, weights)
    ranked = sorted(ops, key=lambda op: -op[3])[:24]
    values = {original, text}
    # Prefixes of learned confidence, and source-order prefixes/suffixes, permit
    # gradual lexical difficulty without inventing punctuation-only variants.
    for order in (ranked, sorted(ranked), list(reversed(sorted(ranked)))):
        for n in range(1, len(order) + 1):
            values.add(apply(text, order[:n]))
    # Legacy structural rules are already checked and disclosed as v1 components.
    for seed in (text, apply(text, ranked)):
        for attempt in range(3):
            values.add(split_clauses(refine(seed, attempt, 1)))
    values.update(split_clauses(value) for value in tuple(values))
    # Independent explicit nominal definitions can move to their own statements.
    # Enumerate which glosses to unfold, preserving all original facts and scope.
    pattern = re.compile(
        r"\b(?P<name>[A-ZÁÉÍÓÚÑ][^\W\d_]+)\s+\((?P<meaning>(?:pan|salchichas|ave|pez|aparato|instrumento)(?:\s+[^\W\d_]+){0,4})\)"
    )
    for seed in (text, apply(text, ranked)):
        matches = list(pattern.finditer(seed))[:4]
        for mask in range(1, 1 << len(matches)):
            edits = []
            glosses = []
            for index, match in enumerate(matches):
                if mask & (1 << index):
                    edits.append((match.start(), match.end(), match["name"], 1))
                    glosses.append(
                        f"Con {match['name']}, el texto se refiere a {match['meaning']}."
                    )
            values.add(apply(seed, edits).rstrip(".") + ". " + " ".join(glosses))
    return sorted(values)
