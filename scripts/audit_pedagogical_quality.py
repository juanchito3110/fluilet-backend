"""Public regression diagnostics; never a held-out or clinical validation.

python -m scripts.audit_pedagogical_quality --output docs/pedagogical-v3-evaluation.json --check
"""

import argparse
import json
from pathlib import Path

from app.encyclopedia import ARTICLES
from app.lesson_sources import LESSON_WORD_LIMITS, lesson_excerpt
from app.nlp.readability import measure
from app.nlp.segmentation import sentences, words
from app.nlp.validation import reading_chunks
from app.services.clear_spanish import LIMITS
from app.services.comprehension import (
    aligned_source_facts,
    build_questions,
    extracted_facts,
    recognition_facts,
    reviewed_facts,
    vocabulary_facts,
)
from app.services.pedagogy import GOALS, VERSION, choose_levels
from app.services.ranker import model_info
from app.services.sentence_bands import meets_band
from app.vocabulary import key_vocabulary


def inspect_level(source, preview, age):
    text, level = preview["adapted_text"], preview["level"]
    m = measure(text)
    q = build_questions(text, age, source)
    glossary = key_vocabulary(text)
    facts = [
        *reviewed_facts(text, source),
        *extracted_facts(text),
        *aligned_source_facts(source, text),
        *vocabulary_facts(text),
        *recognition_facts(text),
    ]
    kinds = {f.stem: f.kind for f in facts}
    selected = [kinds.get(item["question"], "unclassified") for item in q]
    maximum = max(len(words(s)) for s in sentences(text))
    low, high, *_ = GOALS[level]
    chunks = reading_chunks(text)
    return dict(
        level=level,
        score=m.score,
        word_count=m.word_count,
        average_words_per_sentence=m.word_count / m.sentence_count,
        max_words_per_sentence=maximum,
        syllables_per_word=m.syllable_count / m.word_count,
        short_sentence_limit_met=maximum <= LIMITS[level],
        score_band_met=low <= m.score <= high,
        sentence_band_met=meets_band(text, level, source),
        complete_reading_spans=" ".join(chunks) == text
        and all(c.endswith((".", "?", "!", "»")) for c in chunks),
        glossary_count=len(glossary),
        glossary_valid=all(
            len("".join(words(g["word"]))) >= 4
            and not any(c.isdigit() for c in g["word"])
            and g["word"] in text
            and 10 <= len(words(g["definition"])) <= 22
            and g["example"] in sentences(text)
            for g in glossary
        ),
        question_kinds=selected,
        question_mix_met=len(selected) == 3
        and selected[0] not in {"cause", "purpose", "recognition", "unclassified"}
        and selected[1] in {"cause", "purpose"}
        and selected[2] in {"concept", "inference", "vocabulary", "statement"},
        question_count=len(q),
        four_options=all(len(i["options"]) == len(set(i["options"])) == 4 for i in q),
        literal_recognition_fallback="recognition" in selected,
    )


def inspect_source(source, age, *, excerpt=False):
    original = measure(source)
    _, previews, ordered = choose_levels(source, allow_local_excerpt=excerpt)
    return dict(
        original_score=original.score,
        original_word_count=original.word_count,
        original_average_words_per_sentence=original.word_count / original.sentence_count,
        original_syllables_per_word=original.syllable_count / original.word_count,
        strict_progression=ordered,
        lexical_variation_levels_1_3=all(
            set(words(previews[i]["adapted_text"].casefold()))
            != set(words(previews[i + 1]["adapted_text"].casefold()))
            for i in range(2)
        ),
        levels=[inspect_level(source, p, age) for p in previews],
    )


def summary(rows):
    return dict(
        excerpts=len(rows),
        variants=sum(len(r["levels"]) for r in rows),
        strict_progression=sum(r["strict_progression"] for r in rows),
        short_levels_1_3=sum(
            all(p["short_sentence_limit_met"] for p in r["levels"][:3]) for r in rows
        ),
        lexical_variation_levels_1_3=sum(r["lexical_variation_levels_1_3"] for r in rows),
        all_five_score_bands=sum(all(p["score_band_met"] for p in r["levels"]) for r in rows),
        all_five_sentence_bands=sum(all(p["sentence_band_met"] for p in r["levels"]) for r in rows),
        complete_glossaries=sum(
            all(4 <= p["glossary_count"] <= 6 and p["glossary_valid"] for p in r["levels"])
            for r in rows
        ),
        varied_quizzes=sum(all(p["question_mix_met"] for p in r["levels"]) for r in rows),
        complete_reading_spans=sum(
            all(p["complete_reading_spans"] for p in r["levels"]) for r in rows
        ),
        complete_quizzes=sum(
            all(
                p["question_count"] == 3
                and p["four_options"]
                and not p["literal_recognition_fallback"]
                for p in r["levels"]
            )
            for r in rows
        ),
    )


def audit(topics=None):
    rows = []
    for key, article in ARTICLES.items():
        if topics is not None and key not in topics:
            continue
        cache = {}
        for group in LESSON_WORD_LIMITS:
            source = lesson_excerpt(article.text, group)
            if source not in cache:
                cache[source] = inspect_source(
                    source, {"6-8": 7, "9-11": 10, "12+": 12}[group], excerpt=True
                )
            rows.append(dict(topic=key, age_group=group, **cache[source]))
    model = model_info()
    result = dict(
        engine_version=VERSION,
        model_version=model["model_version"],
        artifact_sha256=model["artifact_sha256"],
        scope="authored_public_catalog_diagnostic_not_heldout_or_clinical_validation",
        articles=len({r["topic"] for r in rows}),
        **summary(rows),
        rows=rows,
    )
    if topics is None:
        from app.demo_accounts import PRESETS
        from tests.open_readings import READINGS
        from tests.test_best_effort import TEXT_A, TEXT_B

        official = []
        for code, _, age, *rest in PRESETS:
            for index, key in enumerate(rest[4]):
                official.append(
                    dict(
                        slot=f"{code}-{index}", topic=key, **inspect_source(ARTICLES[key].text, age)
                    )
                )
        free = [
            dict(case=i, **inspect_source(source, 10))
            for i, source in enumerate((*READINGS, TEXT_A, TEXT_B), 1)
        ]
        result["official_lessons"] = dict(**summary(official), rows=official)
        result["open_readings"] = dict(**summary(free), rows=free)
    return result


def release_ok(result):
    criteria = (
        "strict_progression",
        "all_five_sentence_bands",
        "complete_glossaries",
        "varied_quizzes",
        "complete_reading_spans",
        "complete_quizzes",
    )
    groups = [result, *[result[k] for k in ("official_lessons", "open_readings") if k in result]]
    return all(all(group[k] == group["excerpts"] for k in criteria) for group in groups)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--topic", action="append")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = audit(set(args.topic) if args.topic else None)
    result["release_criteria_met"] = release_ok(result)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: ({a: b for a, b in v.items() if a != "rows"} if isinstance(v, dict) else v)
                for k, v in result.items()
                if k != "rows"
            }
        )
    )
    if args.check and not result["release_criteria_met"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
