"""Measured sentence-length policy, independent of the historical INFLESZ bands.

Only complete clauses may be regrouped. No word-window cuts, added facts,
causal links, or repetition are used to reach a numerical target.
"""

import math
import re
from collections import Counter
from difflib import SequenceMatcher
from functools import lru_cache

from app.nlp.segmentation import sentences, words
from app.services.clear_spanish import LIMITS

BANDS = {1: (6, 9), 2: (9, 12), 3: (12, 15), 4: (15, 19), 5: (19, math.inf)}
CENTRES = {1: 7.5, 2: 10.5, 3: 13.5, 4: 17, 5: 23}


def average(text):
    return len(words(text)) / max(1, len(sentences(text)))


def original_structure(text, source):
    """A lightly cleaned original keeps clause count, order and scope markers."""
    if source is None or len(words(source)) < 20:
        return False
    if len(sentences(text)) != len(sentences(source)):
        return False
    if Counter(re.findall(r"\d+(?:[.,]\d+)*", text)) != Counter(
        re.findall(r"\d+(?:[.,]\d+)*", source)
    ):
        return False
    scopes = r"\b(?:no|nunca|sin|excepto|si|aunque|puede|pueden|podría)\b"
    if re.findall(scopes, text, re.I) != re.findall(scopes, source, re.I):
        return False
    return (
        SequenceMatcher(
            None, words(text.casefold()), words(source.casefold()), autojunk=False
        ).ratio()
        >= 0.85
    )


def meets_band(text, level, source=None):
    value = average(text)
    low, high = BANDS[level]
    if level == 5:
        # The approved alternative is the complete, cleaned original structure.
        return value > low or original_structure(text, source)
    return low <= value <= high


def distance(text, level, source=None):
    if meets_band(text, level, source):
        return 0.0
    value = average(text)
    low, high = BANDS[level]
    return max(0, low + (0.001 if level == 5 else 0) - value, value - high)


@lru_cache(maxsize=1)
def _lowerable():
    from app.services.calibration import _FORMS
    from app.services.clear_spanish import _VERBS

    return (
        set(_FORMS)
        | set(_VERBS)
        | set(
            "desde también además después así allí antes luego dentro fuera en con por para hay conviene".split()
        )
    )


def _join(units, level):
    result = units[0].rstrip(".")
    for unit in units[1:]:
        # Independent clauses are separated by a semicolon; articles may be
        # lowercased but proper names, acronyms and quoted speech stay intact.
        first = words(unit)[0].casefold()
        if first in _lowerable() or re.match(
            r"(?:El|La|Los|Las|Un|Una|Su|Sus|Este|Esta|Estos|Estas|No)\s", unit
        ):
            unit = unit[0].lower() + unit[1:]
        result += (" y " if level == 2 else "; ") + unit.rstrip(".")
    return result + "."


def basic_links(text):
    """An explicit additive connection between already present statements."""
    result = [text]
    units = sentences(text)
    for connector in ("También", "Además"):
        if connector.casefold() in text.casefold():
            continue
        for index, unit in enumerate(units[1:], 1):
            if len(words(unit)) >= 14 or re.match(r"(?:Si|Aunque|Cuando|Pero|Por eso)\b", unit):
                continue
            linked = units.copy()
            start = (
                unit[0].lower() + unit[1:]
                if words(unit)[0].casefold() in _lowerable()
                or re.match(r"(?:El|La|Los|Las|Un|Una|Su|Sus)\b", unit)
                else unit
            )
            linked[index] = connector + ", " + start
            value = " ".join(linked)
            if meets_band(value, 2):
                result.append(value)
                break
    return result


def regroup(text, level, *, relaxed=False):
    """Globally partition adjacent whole clauses, not greedy word-size slices."""
    units = []
    for sentence in sentences(text):
        if sentence.endswith(("?", "!")) or "«" in sentence or '"' in sentence:
            units.append(sentence)
        else:
            units.extend(part.strip() for part in re.split(r";\s+", sentence) if part.strip())
    n = len(units)
    if n < 2 or n > 300:
        return [text]
    sizes = [len(words(unit)) for unit in units]
    cap = (
        {1: 14, 2: 18, 3: 24, 4: 32, 5: 48}[level]
        if relaxed
        else (48 if level == 5 else LIMITS[level])
    )
    total = sum(sizes)
    link_words = 1 if level == 2 else 0
    effective_total = total + link_words * n
    centre = CENTRES[level]
    low, high = BANDS[level]
    counts = {
        max(1, round(effective_total / (centre + link_words))),
        max(1, math.ceil(effective_total / (centre + link_words))),
    }
    if level < 5:
        counts.update(
            range(
                max(1, math.ceil(effective_total / (high + link_words))),
                min(n, math.floor(effective_total / (low + link_words))) + 1,
            )
        )
    if level == 5:
        counts.add(max(1, round(total / 35)))
    results = {text}
    for count in sorted(counts):
        if count > n:
            continue
        paths = {(0, 0): (0.0, [])}
        for start in range(n):
            for used in range(min(count, start + 1)):
                previous = paths.get((start, used))
                if previous is None:
                    continue
                size = 0
                for end in range(start + 1, min(n, start + 8) + 1):
                    size += sizes[end - 1] + (link_words if end > start + 1 else 0)
                    if size > cap and end > start + 1:
                        break
                    if n - end < count - used - 1:
                        continue
                    if end > start + 1 and any(u.endswith(("?", "!")) for u in units[start:end]):
                        continue
                    penalty = (size - centre) ** 2
                    if size > cap:
                        penalty += 100000
                    candidate = (previous[0] + penalty, previous[1] + [(start, end)])
                    key = (end, used + 1)
                    if key not in paths or candidate[0] < paths[key][0]:
                        paths[key] = candidate
        final = paths.get((n, count))
        if final:
            result = []
            for start, end in final[1]:
                parts = units[start:end]
                result.append(parts[0] if len(parts) == 1 else _join(parts, level))
            results.add(" ".join(result))
    return sorted(results)
