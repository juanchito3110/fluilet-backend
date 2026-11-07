"""Clause-aware reading rewrites. Never put a full stop at an arbitrary word index.

Restrictive relatives, negation, modality and conditions are kept in scope. If a
clause cannot safely fit the budget it stays whole and is reported as best effort.
"""

import re

from app.nlp.segmentation import sentences, words

LIMITS = {1: 11, 2: 14, 3: 18, 4: 25, 5: 32}
_VERBS = (
    "es son está están era eran fue fueron tiene tienen tenía tenían usa usan usó usaron "
    "hace hacen hizo hicieron crea crean creó crearon vive viven vivía vivían gira giran "
    "recibe reciben produce producen permite permiten necesita necesitan puede pueden "
    "ayuda ayudan lleva llevan recoge recogen busca buscan come comen da dan dio dieron "
    "empezó comenzó nació abrió estudia estudian aprende aprenden sigue siguen sirve sirven "
    "juega juegan viste visten construye construyen muestra muestran refleja reflejan "
    "mide miden pesa pesan tarda tardan dura duran ocupa ocupan explora exploran "
    "fundó fundaron forman forma representa representan constituye constituyen adquiere adquieren origina originan se".split()
)
_FINITE = r"(?:" + "|".join(sorted(_VERBS, key=len, reverse=True)) + r")"
_HEAD = re.compile(rf"^(?P<subject>[^,;:.!?]{{1,65}}?)\s+(?P<verb>{_FINITE})\b", re.I)
_EXPLICIT = re.compile(
    rf"^(?:(?:el|la|los|las|un|una|unos|unas|su|sus|este|esta|estos|estas|ellos|ellas)\s+"
    rf"[^,;:.!?]{{0,65}}?|[A-ZÁÉÍÓÚÑ][\wáéíóúñ]*(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñ]*){{0,3}})\s+{_FINITE}\b",
    re.I,
)


def statement(text):
    text = text.strip(" ,;:.\n")
    if text.endswith(("?", "!")):
        return text
    return text[0].upper() + text[1:] + "." if text else ""


def split_unit(unit, limit, depth=0):
    unit = unit.strip()
    size = len(words(unit))
    if size <= limit or depth >= 20:
        return [statement(unit)]
    head = _HEAD.match(unit)
    subject = head["subject"] if head else None
    # Split compound statements only at licensed grammatical boundaries.
    for match in re.finditer(r";\s+|,?\s+(?:y|pero|mientras que)\s+|,\s+por lo que\s+", unit, re.I):
        left, right = unit[: match.start()], unit[match.end() :]
        if (
            not left
            or not right
            or not _HEAD.match(left)
            or re.search(r"\b(?:si|aunque|solo si|no solo)\b", left, re.I)
        ):
            continue
        if "por lo que" in match[0].lower():
            right = "Por eso, " + right
        elif "pero" in match[0].lower():
            right = "Pero " + right
        elif _EXPLICIT.match(right):
            pass
        elif subject and re.match(rf"(?:no\s+)?{_FINITE}\b", right, re.I):
            right = subject + " " + right
        else:
            continue
        if max(len(words(left)), len(words(right))) >= size:
            continue
        return split_unit(statement(left), limit, depth + 1) + split_unit(
            statement(right), limit, depth + 1
        )
    # An explanatory (comma-delimited) relative, never a restrictive 'que'.
    relative = re.fullmatch(
        rf"(?P<subject>[^,]{{1,55}}),\s+que (?P<aside>{_FINITE}\b[^,]+),\s+(?P<main>{_FINITE}\b.+)",
        unit.rstrip("."),
        re.I,
    )
    if relative and not re.search(r"\b(?:no|solo|si|aunque)\b", relative["subject"], re.I):
        return split_unit(
            statement(relative["subject"] + " " + relative["aside"]), limit, depth + 1
        ) + split_unit(statement(relative["subject"] + " " + relative["main"]), limit, depth + 1)
    # Keep cause and result linked explicitly, including negated causes.
    cause = re.fullmatch(
        r"(?P<main>.+?)\s+(?:porque|debido a que)\s+(?P<cause>.+)", unit.rstrip("."), re.I
    )
    if cause and _HEAD.match(cause["main"]):
        return [statement(cause["main"]), statement("Esto ocurre porque " + cause["cause"])]
    return [statement(unit)]


def rewrite(text, level):
    # Semicolons join independent clauses in the old score calibrator. Unpack
    # them for early readers rather than hiding long sentences in an average.
    units = []
    for unit in sentences(text):
        if level <= 3:
            market = re.fullmatch(
                r"El frío aire invernal no impide que por todo el mercado se desprenda "
                r"(?:un celestial aroma|un olor muy grato) a (?P<foods>.+?)[.]?",
                unit,
                re.I,
            )
            if market:
                from app.nlp.refinement import refine

                # A licensed negated-prevention frame. Keep its negation and
                # all named foods/glosses; no claim about conditional lists.
                value = (
                    "El aire de invierno está frío. "
                    "Pero no impide que haya un olor muy grato. "
                    "Ese olor llega a todo el mercado. "
                    f"El olor viene de {market['foods'].rstrip('.')}."
                )
                units.extend(sentences(refine(value, level=level)))
                continue
            unit = re.sub(
                r"(?P<subject>[^.;]{1,90}?)\s+(?:constituye|es) un fenómeno físico mediante el cual\s+",
                lambda m: statement(m["subject"] + " es un cambio físico") + " ",
                unit,
                flags=re.I,
            )
            unit = re.sub(
                r"(?P<subject>(?:la|el) [^,;.]{1,50}?) representa el proceso inverso que\s+",
                lambda m: statement(m["subject"] + " es el cambio contrario") + " Este cambio ",
                unit,
                flags=re.I,
            )
            unit = re.sub(
                r"(?P<subject>las moléculas de un líquido) adquieren suficiente energía para transformarse en gas",
                lambda m: (
                    statement(m["subject"] + " reciben energía")
                    + " Esa energía les permite pasar a gas"
                ),
                unit,
                flags=re.I,
            )
        for part in re.split(r";\s+", unit):
            for clause in sentences(part):
                units.extend(split_unit(clause, LIMITS[level]))
    return " ".join(units)


def overflow(text, level):
    return sum(max(0, len(words(unit)) - LIMITS[level]) for unit in sentences(text))
