"""Five measured score bands and three grounded tasks for generated excerpts."""

from dataclasses import replace

import pytest

from app import adaptations, education
from app.encyclopedia import ARTICLES
from app.lesson_sources import LESSON_WORD_LIMITS, lesson_excerpt, resolve_topic
from app.nlp.readability import measure
from app.nlp.segmentation import sentences, words
from app.services.pedagogy import choose_levels
from app.services.scaffolding import supports
from tests.question_assertions import assert_measured_level


def assert_bands(previews, source):
    assert [p["level"] for p in previews] == list(range(1, 6))
    scores = [p["readability_score"] for p in previews]
    assert all(a > b for a, b in zip(scores, scores[1:], strict=False))
    for item in previews:
        assert_measured_level(item, source)
        assert item["readability_score"] == measure(item["adapted_text"]).score


def assert_questions(items, source, adapted, group):
    from tests.question_assertions import assert_grounded_questions

    assert_grounded_questions(items, adapted)
    assert len({item["question"] for item in items}) == 3


@pytest.mark.parametrize("group", LESSON_WORD_LIMITS)
@pytest.mark.parametrize("key", ARTICLES)
def test_every_local_excerpt_has_five_measured_levels_and_grounded_questions(key, group):
    source = lesson_excerpt(ARTICLES[key].text, group)
    _, previews, progressive = choose_levels(source, allow_local_excerpt=True)
    assert progressive
    assert_bands(previews, source)
    assert len(words(source)) <= LESSON_WORD_LIMITS[group]
    age = {"6-8": 7, "9-11": 10, "12+": 12}[group]
    for preview in previews:
        # Independent release criteria from the requested policy, not inferred
        # from the engine's own target flag or historical Szigriszt score bands.
        average = len(words(preview["adapted_text"])) / len(sentences(preview["adapted_text"]))
        bounds = {1: (6, 9), 2: (9, 12), 3: (12, 15), 4: (15, 19)}
        if preview["level"] <= 4:
            low, high = bounds[preview["level"]]
            assert low <= average <= high
        else:
            if average <= 19:
                from difflib import SequenceMatcher

                assert len(sentences(preview["adapted_text"])) == len(sentences(source))
                assert (
                    SequenceMatcher(
                        None,
                        words(preview["adapted_text"].casefold()),
                        words(source.casefold()),
                        autojunk=False,
                    ).ratio()
                    >= 0.85
                )
        from app.vocabulary import key_vocabulary

        vocabulary = key_vocabulary(preview["adapted_text"])
        assert 4 <= len(vocabulary) <= 6
        for term in vocabulary:
            assert len("".join(words(term["word"]))) >= 4
            assert not any(c.isdigit() for c in term["word"])
            assert term["word"] in preview["adapted_text"]
            assert 10 <= len(words(term["definition"])) <= 22
            assert term["example"] in sentences(preview["adapted_text"])
        items = education.lesson_questions(preview["adapted_text"], age, source)
        assert_questions(items, source, preview["adapted_text"], group)


def test_prefix_supports_use_only_the_retained_sentences_and_are_opt_in():
    source = lesson_excerpt(ARTICLES["real madrid"].text, "6-8")
    assert not supports(source)
    facts = supports(source, allow_local_excerpt=True)
    assert facts and all(f.evidence in sentences(source) for f in facts)
    assert not any("FIFA" in f.evidence or "baloncesto" in f.evidence for f in facts)
    assert not supports(source.replace("1902", "2002"), allow_local_excerpt=True)


@pytest.mark.parametrize("topic", ["beisbol", "béisbol"])
@pytest.mark.parametrize("level", range(1, 6))
@pytest.mark.parametrize("group", LESSON_WORD_LIMITS)
async def test_baseball_generation_all_ages_and_levels(client, make_user, topic, level, group):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate",
        headers=headers,
        json={"category": "deportes", "custom_topic": topic, "age_group": group, "level": level},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["source"]["provider"] == "local" and "béisbol" in data["resolved_topic"]
    assert len(words(data["original_text"])) <= LESSON_WORD_LIMITS[group]
    assert len(words(data["adapted_text"])) <= 240
    assert_bands(data["level_previews"], data["original_text"])
    assert data["level_progression_met"]
    assert data["adapted_text"] == data["level_previews"][level - 1]["adapted_text"]
    assert data["readability_score"] == measure(data["adapted_text"]).score
    assert_questions(
        data["comprehension_questions"], data["original_text"], data["adapted_text"], group
    )
    assert data["fun_fact"] and 3 <= len(data["key_vocabulary"]) <= 4
    assert (await client.get("/api/v1/adaptations/" + data["id"], headers=headers)).json() == data


@pytest.mark.parametrize("level", [2, 5])
@pytest.mark.parametrize("group", LESSON_WORD_LIMITS)
async def test_dense_wikipedia_baseball_uses_verified_local_reference_for_all_bands(
    client, make_user, monkeypatch, level, group
):
    # Deliberately dense mock introduction, not a claim about Wikipedia wording.
    article = replace(
        ARTICLES["beisbol"],
        text=" ".join(
            [
                "La reglamentación beisbolística internacional especifica procedimientos organizativos y características competitivas de considerable complejidad."
            ]
            * 30
        ),
        provider="wikipedia",
        revision_id=123,
    )

    async def resolve(category, topic):
        return category, article

    monkeypatch.setattr(adaptations, "resolve_lesson", resolve)
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate",
        headers=headers,
        json={
            "category": "deportes",
            "custom_topic": "béisbol",
            "age_group": group,
            "level": level,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "pedagogical_local_reference" in data["warnings"]
    assert data["source"]["provider"] == "local" and data["source"]["revision_id"] is None
    assert data["original_text"] == lesson_excerpt(ARTICLES["beisbol"].text, group)
    assert_bands(data["level_previews"], data["original_text"])
    assert_questions(
        data["comprehension_questions"], data["original_text"], data["adapted_text"], group
    )


def test_baseball_accents_resolve_to_the_same_contextual_topic():
    assert resolve_topic("deportes", "beisbol") == resolve_topic("deportes", "béisbol")


def test_unseen_source_does_not_borrow_catalog_facts_or_fabricate_band_compliance():
    source = "El Sol da luz. La luz va por el cielo. El sol se ve de día."
    assert not supports(source, allow_local_excerpt=True)
    _, previews, _ = choose_levels(source, allow_local_excerpt=True)
    for preview in previews:
        assert preview["readability_score"] == measure(preview["adapted_text"]).score
        assert not preview.get("pedagogical_support")
        assert "béisbol" not in preview["adapted_text"]
    assert not all(p["target_met"] for p in previews)
