"""Bounded multi-pass alternatives: complete clauses and explicit technical glosses."""

import re

from app.nlp.refinement import refine
from app.nlp.segmentation import sentences, words
from app.services.morphology import entries, inflect_text

_FORMS = sorted(
    {
        word
        for _, source, target, tense, _ in entries()
        if tense in {"present", "past", "imperfect", "future", "conditional"}
        for word in (source, target)
    },
    key=len,
    reverse=True,
)
_FINITE = "(?:" + "|".join(map(re.escape, _FORMS)) + ")"


def finite_clauses(text):
    result = []
    for sentence in sentences(text):
        match = re.match(
            r"^(?P<subject>(?:El|La|Los|Las|Un|Una)\s+(?:[^\W\d_]+\s+){1,5}?)(?P<verb>"
            + _FINITE
            + r")\b",
            sentence,
        )
        if match and not set(words(match["subject"].lower())) & {"que", "no", "si", "aunque"}:
            # Spanish permits a shared, omitted subject in the second sentence;
            # verb tense/person stay unchanged. No restrictive relative is split.
            sentence = re.sub(
                r"\s+y\s+(?=(?:(?:después|posteriormente|luego)\s+)?(?:no\s+)?" + _FINITE + r"\b)",
                ". ",
                sentence,
                flags=re.I,
            )
            parts = sentences(sentence)
            sentence = " ".join(part[0].upper() + part[1:] for part in parts)
        result.append(sentence)
    return " ".join(result)


# Explicit, independently authored definitions. Never add generic topic filler.
GLOSSES = {
    "atmósfera": "La atmósfera es la capa de gases que rodea un planeta.",
    "fotosíntesis": "La fotosíntesis es el proceso que usa luz para crear alimento.",
    "salinidad": "La salinidad indica la cantidad de sal que hay en el agua.",
    "temperatura": "La temperatura indica si algo está frío o caliente.",
    "bioluminiscencia": "La bioluminiscencia es la luz que crean algunos seres vivos.",
    "fitoplancton": "El fitoplancton son seres muy pequeños que flotan en el agua y usan la luz.",
    "algoritmo": "Un algoritmo es una serie de pasos para resolver una tarea.",
    "algoritmos": "Los algoritmos son series de pasos para resolver tareas.",
    "jeroglíficos": "Los jeroglíficos son signos de escritura con formas de seres y objetos.",
    "arqueología": "La arqueología estudia cómo vivían los pueblos a partir de sus restos.",
    "ecosistema": "Un ecosistema incluye a los seres de un lugar y sus relaciones.",
    "cartílago": "El cartílago es un tejido firme y flexible del cuerpo.",
}


def pack(text, limit):
    """Compound sentences join complete adjacent statements, without causal links."""
    groups = []
    for unit in sentences(text):
        if groups and len(words(groups[-1])) + len(words(unit)) <= limit:
            groups[-1] = groups[-1].rstrip(".") + "; " + unit
        else:
            groups.append(unit)
    return " ".join(groups)


def alternatives(source, seeds, *, glosses=True):
    values = set(seeds)
    # Bounded passes: lexical/syntax first; sentence grouping second. Limits are
    # genuine pedagogical compound lengths, never arbitrary mid-clause cuts.
    for seed in tuple(seeds)[:4]:
        for attempt in (0, 1, 2):
            simple = finite_clauses(refine(inflect_text(seed), attempt, 1))
            values.add(simple)
            for limit in (9, 12, 15, 18, 24, 30):
                values.add(pack(simple, limit))
    if glosses:
        additions = [
            definition
            for term, definition in GLOSSES.items()
            if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", source, re.I)
        ]
        # At most two definitions, only for technical terms actually in the source.
        for seed in tuple(seeds)[:2]:
            for count in range(1, min(2, len(additions)) + 1):
                values.add(seed.rstrip(".") + ". " + " ".join(additions[:count]))
    return sorted(values)


def minimal_edits(source):
    from app.services.rewriting import apply, operations

    normalized = " ".join(source.split())
    edits = operations(normalized, [0.0] * 24)[:24]
    return [apply(normalized, [edit]) for edit in edits]
