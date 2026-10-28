"""Five-level, traceable Spanish rewrites with measured goals, never invented scores."""

import difflib
import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from functools import cached_property

from app.nlp.readability import measure
from app.nlp.refinement import fidelity_ok, refine
from app.nlp.segmentation import sentences, words
from app.nlp.syllables import count_syllables
from app.services.lexicon_es import CURATED
from app.services.local_plans import SIMPLE
from app.services.resources import choose_corpus, resources

VERSION = "pedagogical-es-v2.2.1"
GOALS = {
    1: (82, 100, 6, 9),
    2: (74, 84, 9, 12),
    3: (65, 74, 11, 15),
    4: (58, 66, 14, 18),
    5: (50, 65, 16, 24),
}
_FRACTIONS = {1: 0.0, 2: 0.2, 3: 0.45, 4: 0.65, 5: 0.85}
_PATTERN = re.compile(
    r"(?<!\w)(?:"
    + "|".join(re.escape(key) for key in sorted(CURATED, key=len, reverse=True))
    + r")(?!\w)",
    re.I,
)
_FINITE = r"(?:usa|usan|tiene|tienen|hace|hacen|gira|giran|refleja|reflejan|estudia|estudian|vive|viven|produce|producen|crea|crean|recibe|reciben|juega|juegan|necesita|necesitan|permite|permiten|puede|pueden|da|dan)"
_SUBJECT = re.compile(
    rf"^(?P<subject>(?:El|La|Los|Las|Un|Una)\s+(?:[^\W\d_]+\s+){{1,5}}?){_FINITE}\b"
)
_PASSIVE = {
    "fundado": "fundó",
    "fundada": "fundó",
    "construido": "construyó",
    "construida": "construyó",
    "publicado": "publicó",
    "publicada": "publicó",
    "creado": "creó",
    "creada": "creó",
    "descubierto": "descubrió",
    "descubierta": "descubrió",
    "inventado": "inventó",
    "inventada": "inventó",
}


@dataclass(frozen=True)
class Candidate:
    text: str
    method: str
    removed: tuple = ()

    @cached_property
    def metric(self):
        return measure(self.text)


def label(score):
    # INFLESZ interpretation; pedagogical target bands are a separate policy.
    return (
        "Muy fácil"
        if score > 80
        else "Bastante fácil"
        if score >= 65
        else "Normal"
        if score >= 55
        else "Algo difícil"
        if score >= 40
        else "Muy difícil"
    )


def source_hash(text):
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


def cleanup(text):
    removed = []

    def strip(match):
        body = match[0]
        # Parenthetical conditions, negation, equations and factual qualifiers stay.
        if re.search(r"\b(?:no|si|sin|excepto|aunque|cuando)\b", body, re.I):
            return body
        if re.search(r"AFI|IPA|pronunciaci[oó]n|[ˈˌ]|^\(/|del lat[ií]n|del griego", body, re.I) or (
            re.fullmatch(r"\(\s*\d{3,4}\s*[–—-]\s*\d{3,4}\s*\)", body)
            and re.search(
                r"autor|escritor|cient[ií]fic[oa]|persona",
                text[max(0, match.start() - 70) : match.start()],
                re.I,
            )
        ):
            removed.append(body)
            return ""
        return body

    cleaned = re.sub(r"\([^()]{0,240}\)", strip, text)

    def reference(match):
        removed.append(match[0])
        return ""

    cleaned = re.sub(r"\[(?:\d+(?:[,–-]\d+)*|cita requerida)\]", reference, cleaned, flags=re.I)
    return " ".join(cleaned.split()), tuple(removed)


def lexical(text, level):
    def replace(match):
        source = match[0]
        if source.casefold() in {"impide", "impiden", "impedir"} and re.search(
            r"\bno\s+$", text[: match.start()], re.I
        ):
            return source
        target = CURATED[source.casefold()]
        # Richer levels retain domain terms. Long academic locutions still simplify.
        syllables = sum(count_syllables(token) for token in words(source))
        threshold = {1: 0, 2: 3, 3: 4, 4: 7, 5: 10}[level]
        if syllables < threshold:
            return source
        return target.capitalize() if source[0].isupper() else target

    from ml_training.prepare_easier import normalized

    units = []
    for unit in sentences(text):
        rewritten = _PATTERN.sub(replace, unit)
        if level <= 3:
            decisions = {}
            context = frozenset(normalized(token) for token in words(unit))

            def corpus(match, decisions=decisions, unit=unit, context=context):
                token = match[0]
                if token[0].isupper():
                    return token
                if token not in decisions:
                    decisions[token] = (
                        choose_corpus(token, unit, level, context, training_only=True) or token
                    )
                return decisions[token]

            rewritten = re.sub(r"[^\W\d_]+", corpus, rewritten)
        units.append(rewritten)
    return " ".join(units)


def syntax(text, level):
    result = []
    limit = GOALS[level][3]
    for sentence in sentences(text):
        relative_verbs = {
            "observan": "observar",
            "observa": "observar",
            "estudian": "estudiar",
            "estudia": "estudiar",
            "transmiten": "transmitir",
            "transmite": "transmitir",
        }
        sentence = re.sub(
            r"mediante el cual se (observan|observa|estudian|estudia|transmiten|transmite)\b",
            lambda match, relative_verbs=relative_verbs: (
                "que sirve para " + relative_verbs[match[1]]
            ),
            sentence,
        )
        # Fully bounded passive with an explicit actor, not an unscoped 'por' clause.
        match = re.fullmatch(
            r"(?P<object>(?:El|La) [^,.;]{1,65}?) fue (?P<part>"
            + "|".join(_PASSIVE)
            + r") por (?P<actor>(?:[A-ZÁÉÍÓÚÑ]|el |la |los |las |un |una )[^,.;]{1,65}?)(?P<time> en \d{4})?[.]?",
            sentence,
        )
        if (
            match
            and " y " not in match["actor"]
            and not re.search(r"\b(?:si|no|aunque|que)\b", match["actor"])
        ):
            actor = match["actor"]
            verb = _PASSIVE[match["part"]]
            if re.match(r"(?:Los|Las|Unos|Unas)\b", actor, re.I):
                verb = {
                    "fundó": "fundaron",
                    "construyó": "construyeron",
                    "publicó": "publicaron",
                    "creó": "crearon",
                    "descubrió": "descubrieron",
                    "inventó": "inventaron",
                }[verb]
            sentence = f"{actor[0].upper() + actor[1:]} {verb} {match['object'][0].lower() + match['object'][1:]}{match['time'] or ''}."
        sentence = re.sub(r",\s+por lo que\s+", ". Por eso, ", sentence)
        if len(words(sentence)) > limit:
            match = _SUBJECT.match(sentence)
            if match:
                subject = match["subject"].strip()
                sentence = re.sub(
                    rf"\s+y\s+(?=(?:no\s+)?{_FINITE}\b)", ". " + subject + " ", sentence
                )
            sentence = re.sub(r";\s+(?=(?:El|La|Los|Las|Un|Una)\s+)", ". ", sentence)
        result.extend(sentences(sentence))
    return " ".join(result)


def join_related(text, limit):
    """Join only adjacent full statements from one aligned fact, without new claims."""
    units = sentences(text)
    joined = []
    for unit in units:
        if joined and len(words(joined[-1])) + len(words(unit)) <= limit:
            joined[-1] = joined[-1].rstrip(".") + "; " + unit
        else:
            joined.append(unit)
    return " ".join(joined)


def _local_plan(text):
    # Lazy import avoids a catalog/services import cycle.
    from app.encyclopedia import ARTICLES

    identity = source_hash(text)
    for key, article in ARTICLES.items():
        if source_hash(article.text) == identity:
            originals = sentences(article.text)
            if len(originals) == len(SIMPLE[key]):
                return originals, SIMPLE[key]
    return None


def _local_candidates(text, level, plan):
    original, simple = plan
    n = len(original)
    desired = min(n - 1, round(n * _FRACTIONS[level]))
    # Prefer simplifying the hardest facts first; alternate fact selections allow
    # a measured progression without arbitrary cuts or score manipulation.
    hardness = sorted(range(n), key=lambda i: measure(original[i]).score)
    variants = []
    counts = {desired, max(0, desired - 1), min(n - 1, desired + 1)} if level > 1 else {0}
    for count in sorted(counts):
        for shift in range(min(n, 4)):
            keep = set((hardness[shift:] + hardness[:shift])[-count:]) if count else set()
            units = []
            for i in range(n):
                unit = original[i] if i in keep else simple[i]
                # Authored local paraphrases are already lexically reviewed.
                units.append(join_related(unit, GOALS[level][3]) if level > 1 else unit)
            variants.append(Candidate(" ".join(units), "reviewed_local_alignment"))
    return variants


def _general_candidates(text, level, legacy):
    cleaned, removed = cleanup(text)
    variants = [Candidate(text, "original")]
    value = syntax(lexical(cleaned, level), level)
    variants.append(Candidate(value, "pedagogical_rules", removed))
    # Re-use legacy rules only after their own fidelity guard passes.
    for attempt in range(3):
        candidate = refine(cleaned, attempt, level)
        if fidelity_ok(cleaned, candidate):
            variants.append(Candidate(syntax(candidate, level), "pedagogical_rules", removed))
    if legacy and fidelity_ok(text, legacy):
        variants.append(Candidate(legacy, "rules"))
    return variants


def _loss(candidate, level, estimate=0.0):
    score = candidate.metric
    low, high, min_length, max_length = GOALS[level]
    target = (low + high) / 2
    length = score.word_count / score.sentence_count
    distance = max(0, low - score.score, score.score - high)
    length_distance = max(0, min_length - length, length - max_length)
    return (
        distance * 1000
        + abs(score.score - target) * 0.01
        + length_distance * 0.002
        - estimate * 0.01
    )


def _safe_numbers(source, candidate):
    def numbers(value):
        return Counter(re.findall(r"\d+(?:[.,]\d+)*", value))

    # Only explicitly reported noise spans can remove dates/reference numbers.
    cleaned = source
    for fragment in candidate.removed:
        cleaned = cleaned.replace(fragment, "", 1)
    return numbers(cleaned) == numbers(candidate.text)


def choose_levels(text, legacy=None):
    from app.nlp.readability import measurement_session

    with measurement_session():
        original = measure(text)
        if original.score > 128.535:
            item = Candidate(text, "original")
            return (
                [item] * 5,
                [
                    dict(
                        level=level,
                        adapted_text=text,
                        readability_score=original.score,
                        readability_level=label(original.score),
                        avg_sentence_length=original.word_count / original.sentence_count,
                        target_met=False,
                        method="original",
                    )
                    for level in range(1, 6)
                ],
                False,
            )
        units = sentences(text)
        if len(words(text)) > 250 and len(units) > 1:
            return _compose_levels(text, units)
        return _choose_levels(text, legacy)


def _compose_levels(text, units):
    """Analyze complete source clauses once, then measure the whole output.

    Long readings often repeat the same teaching statements. This request-local
    memo avoids quadratic full-document diffs for every repeated occurrence;
    it never stores input text beyond the chunk or truncates any source clause.
    """
    import math

    from app.services.calibration import regroup

    memo = {unit: _choose_levels(unit)[0] for unit in dict.fromkeys(units)}
    seeds = [" ".join(memo[unit][level].text for unit in units) for level in range(5)]
    groups = []
    for level in range(1, 6):
        removed = tuple(fragment for unit in units for fragment in memo[unit][level - 1].removed)
        variants = {text, *seeds}
        lo, hi, *_ = GOALS[level]
        for seed in seeds:
            m = measure(seed)
            base = 206.835 - 62.3 * m.syllable_count / m.word_count
            for target in (lo, (lo + hi) / 2, hi):
                if base > target:
                    n = m.word_count / (base - target)
                    for count in (math.floor(n), math.ceil(n)):
                        variants.add(regroup(seed, max(1, min(m.sentence_count, count))))
        candidates = [
            Candidate(value, "composed_clause_calibration", removed) for value in sorted(variants)
        ]
        source_score = measure(text).score
        candidates = [
            c
            for c in candidates
            if _safe_numbers(text, c) and (level > 1 or c.metric.score >= source_score)
        ]
        groups.append(
            sorted(
                candidates or [Candidate(text, "original")], key=lambda c: (_loss(c, level), c.text)
            )[:20]
        )
    paths = [(_loss(c, 1), [c]) for c in groups[0]]
    for level in range(2, 6):
        following = []
        for item in groups[level - 1]:
            options = [
                (loss + _loss(item, level), path + [item])
                for loss, path in paths
                if path[-1].metric.score > item.metric.score + 0.001
            ]
            if options:
                following.append(min(options, key=lambda pair: pair[0]))
        paths = following
    progressive = bool(paths)
    selected = min(paths, key=lambda pair: pair[0])[1] if progressive else [g[0] for g in groups]
    previews = []
    for level, item in enumerate(selected, 1):
        m = item.metric
        lo, hi, min_words, max_words = GOALS[level]
        average = m.word_count / m.sentence_count
        previews.append(
            dict(
                level=level,
                adapted_text=item.text,
                readability_score=m.score,
                readability_level=label(m.score),
                avg_sentence_length=average,
                target_met=lo <= m.score <= hi and min_words <= average <= max_words,
                method=item.method,
            )
        )
    return selected, previews, progressive


def _choose_levels(text, legacy=None):
    resources()  # no-op after startup warm-up
    plan = _local_plan(text)
    source = measure(text)
    from app.services.ranker import checkpoint
    from app.services.rewriting import candidates as learned_candidates

    learned = learned_candidates(text) if checkpoint() and not plan else []
    from app.services.calibration import alternatives, calibrate_density, minimal_edits

    if not plan:
        learned = sorted(set(learned) | set(minimal_edits(text)))
    costs = {}
    qualities = {}
    candidates_by_text = {}

    def cost(item, level):
        key = (item.text, level)
        if key not in costs:
            from app.services.ranker import quality

            if item.text not in qualities:
                qualities[item.text] = quality(text, item.text, level, source, item.metric)
            costs[key] = _loss(item, level, qualities[item.text])
        return costs[key]

    groups = []
    for level in range(1, 6):
        raw = (
            _local_candidates(text, level, plan)
            if plan
            else _general_candidates(text, level, legacy)
        )
        raw.extend(Candidate(value, "trained_context_ranker") for value in learned)
        raw = list({item.text: item for item in raw}.values())
        # Candidate expansion uses source-complete clauses; no tail truncation.
        seeds = sorted(raw, key=lambda item: -item.metric.score)[:3]
        expanded = alternatives(text, [item.text for item in seeds], glosses=level <= 2)
        raw.extend(Candidate(value, "joint_calibrated") for value in expanded)
        density_seeds = sorted(raw, key=lambda item: -item.metric.score)[:3]
        density = calibrate_density(text, [item.text for item in density_seeds], level)
        raw.extend(Candidate(value, "analytic_closed_loop") for value in density)
        raw = [candidates_by_text.setdefault((item.text, item.removed), item) for item in raw]
        unique = {
            item.text: item
            for item in raw
            if item.text
            and words(item.text)
            and _safe_numbers(text, item)
            and not re.search(r"\b(no no|el el|la la|que están que)\b", item.text, re.I)
        }
        if plan and len(unique) > 1:
            # Catalog lessons have authored alternatives at every level. Keep
            # the selected reading distinct from its retained source, including
            # when the original already happens to lie near a band's centre.
            unique = {
                key: item
                for key, item in unique.items()
                if source_hash(key.casefold()) != source_hash(text.casefold())
            }
        # Bidirectional calibration is explicit for richer levels. An already
        # easy source may yield a lower (truthfully reported) advanced score;
        # no fabricated complexity/filler is introduced to reach that band.
        candidates = [
            item for item in unique.values() if level > 1 or item.metric.score >= source.score
        ]
        ranked = sorted(
            candidates or [Candidate(text, "original")],
            key=lambda item: (_loss(item, level), item.text),
        )
        # Structural search needs measurements, not a learned call per variant.
        # Keep interval-centred choices and score extremes for the monotone DP.
        shortlist = list(
            {
                item.text: item
                for item in ranked[:16]
                + sorted(ranked, key=lambda c: (c.metric.score, c.text))[:2]
                + sorted(ranked, key=lambda c: (-c.metric.score, c.text))[:2]
            }.values()
        )
        groups.append(sorted(shortlist, key=lambda item: (cost(item, level), item.text)))
    paths = [(cost(item, 1), [item]) for item in groups[0]]
    for level in range(2, 6):
        next_paths = []
        for item in groups[level - 1]:
            options = [
                (loss + cost(item, level), path + [item])
                for loss, path in paths
                if path[-1].metric.score > item.metric.score + 0.001
            ]
            if options:
                next_paths.append(min(options, key=lambda pair: pair[0]))
        paths = next_paths
        if not paths:
            break
    progressive = bool(paths and len(paths[0][1]) == 5)
    selected = (
        min(paths, key=lambda pair: pair[0])[1] if progressive else [group[0] for group in groups]
    )
    previews = []
    for level, item in enumerate(selected, 1):
        metric = item.metric
        low, high, minimum, maximum = GOALS[level]
        previews.append(
            {
                "level": level,
                "adapted_text": item.text,
                "readability_score": metric.score,
                "readability_level": label(metric.score),
                "avg_sentence_length": metric.word_count / metric.sentence_count,
                "target_met": low <= metric.score <= high
                and minimum <= metric.word_count / metric.sentence_count <= maximum,
                "method": item.method,
            }
        )
    return selected, previews, progressive


def replacements(source, target):
    before, after = words(source), words(target)
    result = []
    for tag, a, b, c, d in difflib.SequenceMatcher(
        a=before, b=after, autojunk=len(before) > 2000
    ).get_opcodes():
        if tag == "replace" and b - a <= 12 and d - c <= 16:
            original, adapted = " ".join(before[a:b]), " ".join(after[c:d])
            if original.casefold() != adapted.casefold():
                result.append({"original": original, "adapted": adapted})
    return result[:80]
