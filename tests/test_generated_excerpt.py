"""Age budgets apply only to generated sources and all derived lesson content."""

import hashlib
import uuid
from dataclasses import replace

import pytest
from sqlalchemy import select

from app import adaptations, education, models, vocabulary
from app.encyclopedia import ARTICLES, Article
from app.lesson_sources import clean_extract, lesson_excerpt
from app.nlp.pipeline import original_result
from app.nlp.readability import measure
from app.nlp.segmentation import sentences, words

UNIT = "Los científicos utilizan instrumentos modernos para observar estrellas lejanas y conocer los cambios de luz durante las noches del año."
TAIL = "La palabra ColaDescartada y la cifra 987654 están únicamente en este final del artículo."
LONG_SOURCE = " ".join([UNIT] * 70 + [TAIL])
CASES = [("6-8", 120, 6), ("9-11", 180, 9), ("12+", 240, 12)]


def article(provider="local", text=LONG_SOURCE):
    return Article(
        "Observación de las estrellas",
        text,
        "ciencia_espacio",
        "https://es.wikipedia.org/wiki/Astronom%C3%ADa",
        "987654",
        provider=provider,
        revision_id=42 if provider == "wikipedia" else None,
    )


def resolve_to(monkeypatch, entry):
    async def resolve(category, topic):
        return category, entry

    monkeypatch.setattr(adaptations, "resolve_lesson", resolve)


@pytest.mark.parametrize("group,budget,count", CASES)
def test_excerpt_keeps_a_complete_prefix_with_exact_age_budget(group, budget, count):
    result = lesson_excerpt(LONG_SOURCE, group)
    assert result == " ".join([UNIT] * count)
    assert len(words(result)) == budget
    assert len(sentences(result)) == count >= 3
    assert "ColaDescartada" not in result
    assert lesson_excerpt(result, group) == result


@pytest.mark.parametrize("group,budget,count", CASES)
def test_clean_extract_uses_same_age_budget_instead_of_1200_words(group, budget, count):
    result = clean_extract("<p>" + LONG_SOURCE + "</p>", group)
    assert result == " ".join([UNIT] * count)
    assert len(words(result)) == budget


def test_excerpt_does_not_cut_the_sentence_at_the_boundary():
    units = [" ".join([UNIT.rstrip(".")] * 2) + "."] * 4  # forty words each
    source = " ".join(units) + " " + TAIL
    result = lesson_excerpt(source, "6-8")
    assert result == " ".join(units[:3])
    assert len(words(result)) == 120
    assert len(sentences(result)) == 3


def test_minimum_three_complete_sentences_precedes_budget_for_long_sentences():
    long_unit = " ".join([UNIT.rstrip(".")] * 3) + "."  # sixty words
    result = lesson_excerpt(" ".join([long_unit] * 4), "6-8")
    assert result == " ".join([long_unit] * 3)
    assert len(words(result)) == 180 and len(sentences(result)) == 3


@pytest.mark.parametrize(
    "text", [UNIT, UNIT + " " + UNIT, "El Sol da luz. La Luna refleja luz. La Tierra gira."]
)
def test_short_sources_are_preserved_without_padding_or_invented_sentences(text):
    assert lesson_excerpt(text, "6-8") == text


def test_abbreviations_decimals_and_terminal_quotes_stay_in_their_sentences():
    source = "El Dr. García observa la Luna. El ciclo tarda 29,5 días. La explicación dice «La Luna refleja luz». "
    prefix = source.strip()
    assert sentences(lesson_excerpt(source + LONG_SOURCE, "6-8"))[:3] == sentences(prefix)
    assert "Dr. García" in prefix and "29,5" in prefix


def test_paragraph_boundaries_and_original_spacing_are_preserved():
    unit = " ".join([UNIT.rstrip(".")] * 2)
    prefix = "\n\n".join([unit] * 3)
    result = lesson_excerpt(prefix + "\n\n" + TAIL, "6-8")
    assert result == prefix
    assert len(words(result)) == 120 and len(sentences(result)) == 3


@pytest.mark.parametrize("provider", ["wikipedia", "local"])
@pytest.mark.parametrize("group,budget,count", CASES)
async def test_generated_comparator_previews_questions_and_fact_use_the_excerpt(
    client, make_user, db, monkeypatch, provider, group, budget, count
):
    entry = article(provider)
    resolve_to(monkeypatch, entry)
    inputs, question_inputs, enrichment_inputs = [], [], []
    actual_run, actual_questions, actual_enrich = (
        adaptations.pipeline.run,
        education.lesson_questions,
        vocabulary.enrich,
    )

    async def capture(text, level, *, child_age=None, allow_local_excerpt=False):
        inputs.append(text)
        return await actual_run(
            text, level, child_age=child_age, allow_local_excerpt=allow_local_excerpt
        )

    def questions(text, age, source):
        question_inputs.append(text)
        assert source == lesson_excerpt(entry.text, group)
        return actual_questions(text, age, source)

    def enrich(text, hint):
        enrichment_inputs.append(text)
        return actual_enrich(text, hint)

    monkeypatch.setattr(adaptations.pipeline, "run", capture)
    monkeypatch.setattr(education, "lesson_questions", questions)
    monkeypatch.setattr(vocabulary, "enrich", enrich)
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate",
        headers=headers,
        json={
            "category": "ciencia_espacio",
            "custom_topic": "Observación de las estrellas",
            "age_group": group,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    expected = " ".join([UNIT] * count)
    assert inputs == [expected]
    assert data["original_text"] == expected and len(words(expected)) == budget
    assert data["age_group"] == data["question_age_group"] == group
    assert data["source"]["provider"] == provider
    assert data["source"]["revision_id"] == entry.revision_id
    assert entry.text == LONG_SOURCE  # frozen catalog/source is never mutated
    assert data["document"]["content_sha256"] == hashlib.sha256(expected.encode()).hexdigest()
    assert data["document"]["word_count"] == data["metrics"]["original_word_count"] == budget
    assert data["document"]["file_size_bytes"] == len(expected.encode())
    original, adapted = measure(expected), measure(data["adapted_text"])
    assert (
        data["original_readability_score"]
        == data["metrics"]["original_szigriszt_pazos"]
        == original.score
    )
    assert data["readability_score"] == data["metrics"]["adapted_szigriszt_pazos"] == adapted.score
    assert data["readability_gain"] == pytest.approx(adapted.score - original.score)
    assert data["original_avg_sentence_length"] == pytest.approx(
        original.word_count / original.sentence_count
    )
    assert data["original_syllables_per_word"] == pytest.approx(
        original.syllable_count / original.word_count
    )
    assert len(data["level_previews"]) == 5
    for preview in data["level_previews"]:
        assert preview["readability_score"] == measure(preview["adapted_text"]).score
    assert data["adapted_text"] == data["level_previews"][data["target_level"] - 1]["adapted_text"]
    assert question_inputs == enrichment_inputs == [data["adapted_text"]]
    assert len(data["comprehension_questions"]) == 3
    for item in data["comprehension_questions"]:
        answer = item["options"][item["correct_option_index"]]
        if group == "6-8":
            answer = answer[len("Dice «") : -1]
        assert answer in data["adapted_text"]
    fact = data["fun_fact"].split("«", 1)[1].rsplit("»", 1)[0]
    assert fact in data["adapted_text"]
    visible = [data["original_text"], data["adapted_text"], data["fun_fact"]]
    visible += [p["adapted_text"] for p in data["level_previews"]]
    visible += [str(q) for q in data["comprehension_questions"]]
    assert all("ColaDescartada" not in value and "987654" not in value for value in visible)
    content = await db.get(models.AdaptationContent, uuid.UUID(data["id"]))
    assert content.original_text == expected
    assert (
        await db.scalar(
            select(models.Document).where(
                models.Document.content_sha256 == hashlib.sha256(LONG_SOURCE.encode()).hexdigest()
            )
        )
        is None
    )
    assert (await client.get("/api/v1/adaptations/" + data["id"], headers=headers)).json() == data


@pytest.mark.parametrize(
    "profile_group,explicit_group,budget,count",
    [
        ("6-8", None, 120, 6),
        ("9-11", None, 180, 9),
        ("12+", None, 240, 12),
        ("12+", "6-8", 120, 6),
        ("6-8", "12+", 240, 12),
    ],
)
async def test_effective_profile_age_and_explicit_override_control_budget_not_level(
    client, make_user, child_payload, db, monkeypatch, profile_group, explicit_group, budget, count
):
    resolve_to(monkeypatch, article())
    _, headers, _ = await make_user()
    child = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()
    profile = await db.get(models.ChildProfile, uuid.UUID(child["id"]))
    profile.age_group_override = profile_group
    await db.commit()
    body = {
        "category": "ciencia_espacio",
        "custom_topic": "Observación de las estrellas",
        "child_id": child["id"],
        "level": 5,
    }
    if explicit_group is not None:
        body["age_group"] = explicit_group
    response = await client.post("/api/v1/adaptations/generate", headers=headers, json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["target_level"] == 5
    assert data["age_group"] == (explicit_group or profile_group)
    assert data["original_text"] == " ".join([UNIT] * count)
    assert data["metrics"]["original_word_count"] == budget


@pytest.mark.parametrize("group,budget,count", CASES)
async def test_wikipedia_to_local_fallback_is_also_trimmed_before_adaptation(
    client, make_user, monkeypatch, group, budget, count
):
    remote = article("wikipedia")
    local = replace(article(), text=LONG_SOURCE.replace("modernos", "ópticos"))
    resolve_to(monkeypatch, remote)
    monkeypatch.setattr(adaptations, "local_article", lambda resolution: local)
    process = adaptations.process
    inputs = []

    async def capture(text, data, media_type, level, *, child_age=None, allow_local_excerpt=False):
        inputs.append(text)
        if len(inputs) == 1:
            return original_result(text), hashlib.sha256(text.encode()).hexdigest()
        return await process(
            text,
            data,
            media_type,
            level,
            child_age=child_age,
            allow_local_excerpt=allow_local_excerpt,
        )

    monkeypatch.setattr(adaptations, "process", capture)
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate",
        headers=headers,
        json={
            "category": "ciencia_espacio",
            "custom_topic": "Observación de las estrellas",
            "age_group": group,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    expected = " ".join([UNIT.replace("modernos", "ópticos")] * count)
    assert inputs == [" ".join([UNIT] * count), expected]
    assert data["original_text"] == expected
    assert (
        data["source"]["provider"] == "local" and "pedagogical_local_reference" in data["warnings"]
    )
    assert len(words(data["original_text"])) == budget


@pytest.mark.parametrize("path", ["/text", "/file", "/document"])
async def test_manual_text_and_upload_aliases_preserve_complete_input(
    client, make_user, monkeypatch, path
):
    inputs = []

    async def retain(text, level, *, child_age=None):
        inputs.append(text)
        return original_result(text)

    monkeypatch.setattr(adaptations.pipeline, "run", retain)
    _, headers, _ = await make_user()
    if path == "/text":
        response = await client.post(
            "/api/v1/adaptations/text",
            headers=headers,
            json={"text": LONG_SOURCE, "age_group": "6-8"},
        )
    else:
        response = await client.post(
            "/api/v1/adaptations" + path + "?age_group=6-8",
            headers={**headers, "Content-Type": "text/plain"},
            content=LONG_SOURCE.encode(),
        )
    assert response.status_code == 200, response.text
    assert inputs == [LONG_SOURCE]
    assert response.json()["original_text"] == LONG_SOURCE
    assert response.json()["metrics"]["original_word_count"] == len(words(LONG_SOURCE)) > 1200


def test_reviewed_alignment_is_opt_in_exact_prefix_and_never_includes_omitted_facts():
    from app.services.local_plans import SIMPLE
    from app.services.pedagogy import _local_plan

    source = lesson_excerpt(ARTICLES["real madrid"].text, "6-8")
    assert _local_plan(source) is None
    original, simple = _local_plan(source, allow_excerpt=True)
    assert original == sentences(source) and tuple(simple) == SIMPLE["real madrid"][: len(original)]
    assert "FIFA" not in " ".join(simple) and "baloncesto" not in " ".join(simple)
    assert _local_plan(source.replace("1902", "2002"), allow_excerpt=True) is None
    assert _local_plan(" ".join(sentences(source)[1:]), allow_excerpt=True) is None
    assert _local_plan(" ".join(sentences(source)[:2]), allow_excerpt=True) is None
