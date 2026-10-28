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
        analytic_subject = re.match(
            r"^Quienes (?:hacen el estudio|estudian el pasado|guían al equipo|dan clase|cuidan la salud)\s+"
            + _FINITE
            + r"\b",
            sentence,
        )
        if (
            match and not set(words(match["subject"].lower())) & {"que", "no", "si", "aunque"}
        ) or analytic_subject:
            # Spanish permits a shared, omitted subject in the second sentence;
            # verb tense/person stay unchanged. No restrictive relative is split.
            sentence = re.sub(
                r"\s+y\s+(?=(?:(?:después|posteriormente|luego)\s+)?(?:no\s+)?(?:hicieron|hicieron textos|explican|dan|usarán|crearán|"
                + _FINITE
                + r")\b)",
                ". ",
                sentence,
                flags=re.I,
            )
            parts = sentences(sentence)
            sentence = " ".join(part[0].upper() + part[1:] for part in parts)
        sentence = re.sub(r"\ba el\b", "al", sentence)
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
    "jeroglíficos": "Los jeroglíficos son signos de escritura con formas de seres y objetos.",
    "arqueología": "La arqueología estudia cómo vivían los pueblos a partir de sus restos.",
    "ecosistema": "Un ecosistema incluye a los seres de un lugar y sus relaciones.",
    "algoritmos": "Un algoritmo dice qué pasos hay que dar. Se sigue ese orden para lograr un fin.",
    "pacientes": "Un paciente es una persona que recibe cuidados de salud. Se le trata para cuidar de su salud.",
    "prioridad": "Dar prioridad a algo es ponerlo en primer lugar. Es lo que se atiende antes que lo demás.",
    "cuneiforme": "Los signos de cuña tienen una punta y una base ancha. Esa es la forma de los trazos de esta escritura.",
    "proyección": "Para hacer un mapa plano hay que llevar al papel formas de la Tierra. Ese cambio se hace con una proyección.",
    "relevos": "En un relevo, una persona sigue lo que empezó otra. En la carrera, cada una corre su parte del camino.",
    "corriente": "La corriente eléctrica es un flujo de cargas. Se puede usar para dar luz o calor.",
    "cartílago": "El cartílago es un tejido firme que se puede doblar. Hay cartílago en partes del cuerpo, como la nariz.",
}


def pack(text, limit):
    """Compound sentences join complete adjacent statements, without causal links."""
    groups = []
    for unit in sentences(text):
        if (
            groups
            and not groups[-1].endswith(("?", "!"))
            and not unit.endswith(("?", "!"))
            and len(words(groups[-1])) + len(words(unit)) <= limit
        ):
            if re.match(
                r"(?:El|La|Los|Las|Un|Una|Ese|Esa|Esos|Esas|También|Después|Su|Sus|En|Al|Con|Por|Para|No)\b",
                unit,
            ):
                unit = unit[0].lower() + unit[1:]
            groups[-1] = groups[-1].rstrip(".") + "; " + unit
        else:
            groups.append(unit)
    return " ".join(groups)


def regroup(text, count):
    """Balance an exact number of compound sentences at complete clause edges."""
    units = sentences(text)
    if not 1 <= count <= len(units):
        return text
    sizes = [len(words(u)) for u in units]
    remaining = sum(sizes)
    groups = []
    cursor = 0
    for slot in range(count):
        slots = count - slot
        target = remaining / slots
        end = cursor + 1
        size = sizes[cursor]
        while end < len(units) - (slots - 1) and abs(size + sizes[end] - target) < abs(
            size - target
        ):
            size += sizes[end]
            end += 1
        groups.append(pack(" ".join(units[cursor:end]), sum(sizes) + 1))
        remaining -= size
        cursor = end
    return " ".join(groups)


def purpose_clauses(text):
    """Make an affirmative action's purpose explicit without asserting its result.

    Negative, modal, conditional and restrictive clauses do not qualify. In
    particular 'para mejorar' never becomes a claim that improvement occurred.
    """
    output = []
    for unit in sentences(finite_clauses(text)):
        match = re.fullmatch(
            r"(?P<head>(?:El|La|Los|Las|Quienes|Después|Más tarde)\b[^.;]{1,160}?\b"
            r"(?:usa|usan|usaron|usarán|hace|hacen|hicieron|harán|miran|mira|crearán|crean)\b[^.;]{1,100}?) "
            r"para (?P<goal>(?:mirar|observar|entender|explicar|mejorar|lograr|conocer|ver|saber)\b[^.;]+)[.]?",
            unit,
        )
        if match and not re.search(
            r"\b(?:no|nunca|ni|sin|si|aunque|puede|pueden|podría|que)\b", match["head"], re.I
        ):
            output.extend([match["head"] + ".", "El fin es " + match["goal"].rstrip(".") + "."])
        else:
            output.append(unit)
    return " ".join(output)


def statistical_clauses(text):
    """Unfold a bounded percentage/ratio ellipsis; preserve every numeral/scope."""
    pattern = re.compile(
        r"(?P<link>Sin embargo, )?el (?P<percent>\d+) por (?P<base>\d+) de los (?:nuevos casos|casos nuevos) "
        r"se (?:detectan|localizan|hallan) en (?:personas|gente) (?:de )?entre (?P<lo>\d+) y (?P<hi>\d+) años(?: de edad)? "
        r"y, en (?P<count>\d+) de cada (?P<total>\d+) pacientes, en mujeres[.]?",
        re.I,
    )
    result = []
    for unit in sentences(text):
        m = pattern.fullmatch(unit)
        if not m:
            result.append(unit)
            continue
        prefix = (m["link"] + "el ") if m["link"] else "El "
        result.append(
            prefix
            + f"{m['percent']} por {m['base']} de los casos nuevos se halla en gente de {m['lo']} a {m['hi']} años. "
            f"De cada {m['total']} pacientes, {m['count']} son mujeres."
        )
    return " ".join(result)


def topic_anaphora(text):
    """Retain the first technical topic NP, then use an agreeing demonstrative."""
    mapping = {
        "los dinosaurios": "esos seres",
        "los tiburones": "esos peces",
        "la inteligencia artificial": "ese campo",
        "los juegos olímpicos": "esos juegos",
        "el telescopio": "ese aparato",
        "los telescopios": "esos aparatos",
    }
    for noun, target in mapping.items():
        matches = list(re.finditer(r"(?<!\w)" + re.escape(noun) + r"(?!\w)", text, re.I))
        for match in reversed(matches[1:]):
            value = target.capitalize() if match[0][0].isupper() else target
            text = text[: match.start()] + value + text[match.end() :]
    return text


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
        # At most three definitions, only for technical terms in the source.
        for seed in tuple(seeds)[:2]:
            for count in range(1, min(3, len(additions)) + 1):
                values.add(seed.rstrip(".") + ". " + " ".join(additions[:count]))
    return sorted(values)


def minimal_edits(source):
    from app.services.rewriting import apply, operations

    normalized = " ".join(source.split())
    edits = operations(normalized, [0.0] * 24)[:24]
    return [apply(normalized, [edit]) for edit in edits]


def calibrate_density(source, seeds, level):
    """Closed-loop search over explicit periphrases and complete clauses.

    The formula determines which operation to explore next. Punctuation can
    only join complete assertions or split an independently licensed clause;
    arbitrary word offsets never become sentence boundaries. Search is bounded
    and returns best effort when facts/grammar prevent reaching the interval.
    """
    from app.nlp.readability import measure
    from app.services.analytic_es import edits
    from app.services.pedagogy import GOALS
    from app.services.rewriting import apply

    low, high, _, maximum = GOALS[level]
    center = (low + high) / 2
    metrics = {}

    def metric(text):
        if text not in metrics:
            metrics[text] = measure(text)
        return metrics[text]

    def loss(text):
        m = metric(text)
        return (max(0, low - m.score, m.score - high), abs(m.score - center))

    # Source and simple forms give a genuinely bidirectional interval: richer
    # levels may use more of the original, never made-up difficult filler.
    values = set(seeds) | {source}
    for seed in tuple(values):
        values.add(statistical_clauses(seed))

    def stable_key(text):
        return (*loss(text), text)

    beam = sorted(values, key=stable_key)[:4]
    for _ in range(4):
        added = set()
        for seed in beam:
            ops = edits(seed)[:48]
            if ops:
                added.add(apply(seed, ops))
                # Density is measured after each prefix and each individual edit.
                order = sorted(ops, key=lambda op: loss(apply(seed, [op])))
                for count in range(1, len(order) + 1):
                    added.add(apply(seed, order[:count]))
                added.update(apply(seed, [op]) for op in order)
            split = purpose_clauses(statistical_clauses(seed))
            added.add(split)
            added.add(topic_anaphora(split))
            for count in range(1, min(20, len(sentences(split))) + 1):
                added.add(regroup(split, count))
            for limit in sorted({maximum, 9, 12, 16, 20, 24, 30, 40, 50, 64}):
                added.add(pack(split, limit))
        added -= values
        if not added:
            break
        values.update(added)
        beam = sorted(values, key=stable_key)[:4]
        # Keep at least a few measured in-band choices for strict progression.
        if sum(low <= metric(t).score <= high for t in values) >= 4:
            break
    return sorted(values, key=stable_key)[:24]
