"""Reproducible public-catalog diagnostics, not a new held-out model benchmark.

Run: python -m scripts.audit_pedagogical_quality --output docs/pedagogical-v3-evaluation.json
Only independently authored public articles are inspected; never user content.
"""

import argparse
import json
from pathlib import Path

from app.encyclopedia import ARTICLES
from app.lesson_sources import LESSON_WORD_LIMITS, lesson_excerpt
from app.nlp.readability import measure
from app.nlp.segmentation import sentences, words
from app.services.clear_spanish import LIMITS
from app.services.comprehension import build_questions
from app.services.pedagogy import GOALS, VERSION, choose_levels
from app.services.ranker import model_info


def audit():
    rows = []
    for key, article in ARTICLES.items():
        # Equal excerpts across age groups are measured once, then attributed to
        # each group. This is a local variable, not a private-content cache.
        cache = {}
        for group in LESSON_WORD_LIMITS:
            source = lesson_excerpt(article.text, group)
            if source not in cache:
                original = measure(source)
                _, previews, ordered = choose_levels(source, allow_local_excerpt=True)
                levels = []
                for p in previews:
                    m = measure(p["adapted_text"])
                    q = build_questions(
                        p["adapted_text"], {"6-8": 7, "9-11": 10, "12+": 12}[group], source
                    )
                    maximum = max(len(words(s)) for s in sentences(p["adapted_text"]))
                    low, high, *_ = GOALS[p["level"]]
                    levels.append(
                        dict(
                            level=p["level"],
                            score=m.score,
                            word_count=m.word_count,
                            average_words_per_sentence=m.word_count / m.sentence_count,
                            max_words_per_sentence=maximum,
                            syllables_per_word=m.syllable_count / m.word_count,
                            short_sentence_limit_met=maximum <= LIMITS[p["level"]],
                            score_band_met=low <= m.score <= high,
                            question_count=len(q),
                            four_options=all(len(i["options"]) == 4 for i in q),
                            literal_recognition_fallback=any(
                                "se escribe la palabra" in i["question"] for i in q
                            ),
                        )
                    )
                cache[source] = dict(
                    original_score=original.score,
                    original_word_count=original.word_count,
                    original_average_words_per_sentence=original.word_count
                    / original.sentence_count,
                    original_syllables_per_word=original.syllable_count / original.word_count,
                    strict_progression=ordered,
                    lexical_variation_levels_1_3=all(
                        set(words(previews[i]["adapted_text"].casefold()))
                        != set(words(previews[i + 1]["adapted_text"].casefold()))
                        for i in range(2)
                    ),
                    levels=levels,
                )
            rows.append(dict(topic=key, age_group=group, **cache[source]))
    model = model_info()
    return dict(
        engine_version=VERSION,
        model_version=model["model_version"],
        artifact_sha256=model["artifact_sha256"],
        scope="authored_public_catalog_diagnostic_not_heldout_or_clinical_validation",
        articles=len(ARTICLES),
        excerpts=len(rows),
        strict_progression=sum(row["strict_progression"] for row in rows),
        short_levels_1_3=sum(
            all(p["short_sentence_limit_met"] for p in row["levels"][:3]) for row in rows
        ),
        lexical_variation_levels_1_3=sum(row["lexical_variation_levels_1_3"] for row in rows),
        all_five_score_bands=sum(all(p["score_band_met"] for p in row["levels"]) for row in rows),
        complete_quizzes=sum(
            all(
                p["question_count"] >= 3
                and p["four_options"]
                and not p["literal_recognition_fallback"]
                for p in row["levels"]
            )
            for row in rows
        ),
        rows=rows,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}))


if __name__ == "__main__":
    main()
