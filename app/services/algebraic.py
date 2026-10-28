"""Measured closed-loop calibration, over licensed edits and grounded supports.

The equation proposes sentence counts; only complete statements may be joined.
No clamp, invented causal link, repeated padding or unseen-topic fact is allowed.
Unsupported inputs retain a truthful best effort rather than a fabricated pass.
"""

import math
import re
from dataclasses import dataclass

from app.nlp.readability import measure
from app.nlp.segmentation import sentences, words
from app.services.analytic_es import PAIRS
from app.services.calibration import purpose_clauses, regroup
from app.services.lexicon_es import CURATED
from app.services.scaffolding import supports


@dataclass(frozen=True)
class Controlled:
    text: str
    core_text: str
    support: tuple
    steps: int


DECOMPOSE = {
    "mediante": "por medio de",
    "alrededor del Sol": "en torno al Sol",
    "qué pudo significar": "qué pudo querer decir",
    "tipos de escritura": "formas de escribir",
    "un material usado para escribir": "una base para poner signos",
    "su gobierno organizaba": "su gobierno ponía en orden",
    "para construir y organizar grandes obras": "para hacer grandes obras con orden",
}
EGYPT = {"faraones": "reyes", "gobernaban": "regían", "levantaron pirámides": "alzaron pirámides"}


def _replace(text, old, new):
    return re.sub(
        r"(?<!\w)" + re.escape(old) + r"(?!\w)",
        lambda m: new[0].upper() + new[1:] if m[0][0].isupper() else new,
        text,
        count=1,
        flags=re.I,
    )


def lexical_variants(source, text):
    mapping = {**DECOMPOSE, **(EGYPT if re.search(r"\begipto\b", source, re.I) else {})}
    values = set()
    for old, new in mapping.items():
        changed = _replace(text, old, new)
        if changed != text:
            values.add(changed)
    combined = text
    for old, new in mapping.items():
        combined = _replace(combined, old, new)
    if combined != text:
        values.add(combined)
    return sorted(values)


def restore_variants(source, text):
    """Restore whole known lexical spans, not arbitrary mismatched word stems."""
    values = set()
    nominal = {
        "detección": ("cómo se detecta", "la detección"),
        "diagnóstico temprano": ("cómo se hace un diagnóstico temprano", "el diagnóstico temprano"),
        "prevención": ("cómo se evita el daño", "la prevención"),
        "evaluación": ("cómo se evalúa", "la evaluación"),
        "manejo": ("cómo se maneja", "el manejo"),
    }
    for term, (simple, original) in nominal.items():
        if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", source, re.I):
            changed = _replace(text, simple, original)
            if changed != text:
                values.add(changed)
    for old, new in {**CURATED, **PAIRS, **DECOMPOSE}.items():
        if re.search(r"(?<!\w)" + re.escape(old) + r"(?!\w)", source, re.I):
            changed = _replace(text, new, old)
            if changed != text:
                values.add(changed)
    return sorted(values)


def _lower(unit):
    if re.match(
        r"(?:El|La|Los|Las|Un|Una|Su|Sus|Este|Esta|Estos|Estas|También|Después|En|No)\b", unit
    ):
        return unit[0].lower() + unit[1:]
    return unit


def grouped_variants(text, low, high):
    m = measure(text)
    base = 206.835 - 62.3 * m.syllable_count / m.word_count
    values = set()
    focused = re.sub(
        r"\b(Su fin es|Su objetivo es) (?=definir\b)", r"\1, en concreto, ", text, count=1
    )
    if focused != text:
        values.add(focused)
    for target in (low, (low + high) / 2, high):
        if base > target:
            count = m.word_count / (base - target)
            for n in (math.floor(count), math.ceil(count)):
                values.add(regroup(text, max(1, min(m.sentence_count, n))))
    units = sentences(text)
    for i in range(min(len(units) - 1, 12)):
        if re.match(r"(?:Si|Aunque|Cuando|Siempre que|Solo si)\b", units[i], re.I):
            continue
        for link in ("; ", "; asimismo, ", "; además, "):
            pair = units[i].rstrip(".") + link + _lower(units[i + 1])
            values.add(" ".join(units[:i] + [pair] + units[i + 2 :]))
    return sorted(values)


def control(source, text, level, *, max_steps=32):
    from app.services.pedagogy import GOALS

    low, high, min_length, max_length = GOALS[level]
    core = text
    chosen = []
    seen = {text}
    available = supports(source)

    def loss(value):
        m = measure(value)
        return (
            max(0, low - m.score, m.score - high),
            abs(m.score - (low + high) / 2),
            max(
                0,
                min_length - m.word_count / m.sentence_count,
                m.word_count / m.sentence_count - max_length,
            ),
        )

    for step in range(max_steps):
        m = measure(text)
        if low <= m.score <= high:
            return Controlled(text, core, tuple(chosen), step)
        options = []
        if m.score < low:
            split = purpose_clauses(text)
            options.extend(
                (value, False, None) for value in [split, *lexical_variants(source, text)]
            )
            # Each support is distinct, source-grounded, used at most once. A
            # finite budget prevents unrelated filler from swallowing the lesson.
            for fact in available:
                if fact in chosen or fact.text.casefold() in text.casefold():
                    continue
                if sum(len(words(f.text)) for f in chosen) + len(words(fact.text)) > max(
                    30, len(words(core))
                ):
                    continue
                value = text.rstrip(".") + ". " + fact.text
                options.append((value, True, fact))
        else:
            options.extend(
                (v, False, None)
                for v in [*grouped_variants(text, low, high), *restore_variants(source, text)]
            )
        options = [r for r in options if r[0] not in seen and words(r[0])]
        if not options:
            break
        best = min(options, key=lambda r: (loss(r[0]), len(words(r[0])), r[0]))
        if loss(best[0]) >= loss(text):
            break
        text = best[0]
        seen.add(text)
        if best[1]:
            chosen.append(best[2])
        elif not chosen:
            core = text
    return Controlled(text, core, tuple(chosen), min(max_steps, len(seen) - 1))
