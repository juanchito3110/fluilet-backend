"""Public contract assertions independent of question construction rules."""

import re

from app.nlp.segmentation import words


def assert_grounded_questions(items, text, count=3):
    assert len(items) == count
    assert [q["id"] for q in items] == [f"q{i}" for i in range(1, count + 1)]
    for item in items:
        assert set(item) == {
            "id",
            "question",
            "options",
            "correct_option_index",
            "hint",
            "explanation",
        }
        assert item["question"].startswith("¿") and item["question"].endswith("?")
        assert len(item["options"]) == len(set(item["options"])) == 4
        assert all(3 <= len(words(option)) <= 12 for option in item["options"])
        assert all(
            option[0].isupper() and not re.search(r"___|\.\.\.|…", option)
            for option in item["options"]
        )
        answer = item["options"][item["correct_option_index"]]
        assert answer in item["explanation"]
        evidence = re.search(r"La lectura explica: «(.+)»\.$", item["explanation"], re.S)[1]
        assert evidence in text
        assert item["hint"] and "___" not in item["question"]


def assert_measured_level(preview, original=None):
    from app.nlp.readability import measure
    from app.services.sentence_bands import meets_band

    actual = measure(preview["adapted_text"])
    assert preview["readability_score"] == actual.score
    # Tests using this helper exercise rewritten catalog versions. v3.1 targets
    # are the explicit sentence-length policy, not the historic numeric score.
    assert preview["target_met"] == meets_band(preview["adapted_text"], preview["level"], original)
