"""Educational delivery, question grounding and backwards compatible contracts."""

import re
import uuid

import pytest
from sqlalchemy import event

from app import education, models
from app.nlp.pipeline import AdaptationPipeline
from app.nlp.segmentation import words
from tests.conftest import SOURCE
from tests.test_pipeline import Offline
from tests.test_zero_retention import pdf_bytes


def assert_questions(data, count=2):
    questions = data["comprehension_questions"]
    assert [question["id"] for question in questions] == [f"q{i}" for i in range(1, count + 1)]
    text = " ".join(data["adapted_text"].split())
    for question in questions:
        options = question["options"]
        assert len(options) == len(set(option.casefold() for option in options)) == 3
        correct = options[question["correct_option_index"]]
        if data.get("question_age_group") == "6-8":
            correct = re.fullmatch(r"Dice «(.+)»", correct)[1]
        stem = re.search(r"«(.+)»", question["question"])
        if stem:
            assert stem[1].replace("___", correct) in text
        else:
            assert correct in text
        assert all(option.strip() for option in options)


async def test_bank_has_three_distinct_rich_texts_per_category():
    assert len(education.LESSONS) == 6
    deltas = []
    for entries in education.LESSONS.values():
        assert len(entries) >= 3
        assert len({entry.text for entry in entries}) == len(entries)
        for entry in entries:
            assert 45 <= len(words(entry.text)) <= 90
            result = await AdaptationPipeline(Offline()).run(entry.text, 2)
            deltas.append(result.metrics["score_delta"])
            assert_questions(
                {
                    "adapted_text": result.adapted_text,
                    "comprehension_questions": education.questions(result.adapted_text),
                }
            )
    # Factual source material replaces the old study filler. Best effort may
    # preserve already clear facts instead of inflating the numerical delta.
    assert min(deltas) >= 0


@pytest.mark.parametrize("category", education.CATEGORIES)
@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
async def test_generate_all_categories_and_levels(client, make_user, category, level):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate",
        headers=headers,
        json={
            "category": category,
            "simplification_level": level,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["category"] == data["document"]["category"] == category
    assert data["simplification_level"] == data["document"]["simplification_level"] == level
    assert data["title"]
    assert data["document"]["original_word_count"] >= 45
    assert_questions(data, 3)


@pytest.mark.parametrize(
    "category,expected",
    [
        ("desconocida", "ciencia_espacio"),
        ("", "ciencia_espacio"),
        (" Tecnología ", "tecnologia"),
        ("animales-naturaleza", "animales_naturaleza"),
    ],
)
async def test_category_normalization_and_default_level(client, make_user, category, expected):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate", headers=headers, json={"category": category}
    )
    assert response.status_code == 200
    assert response.json()["category"] == expected
    assert response.json()["simplification_level"] == 2


@pytest.mark.parametrize(
    "category,topic",
    [
        ("ciencia_espacio", "Agujeros negros"),
        ("animales_naturaleza", "Dinosaurios"),
        ("tecnologia", "Robots del océano"),
    ],
)
async def test_topic_is_integrated_in_title_and_body(client, make_user, category, topic):
    _, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    response = await client.post(
        "/api/v1/adaptations/generate", headers=headers, json={"category": category, "topic": topic}
    )
    assert response.status_code == 200
    data = response.json()
    assert topic.casefold() in data["title"].casefold()
    assert topic.casefold() in data["adapted_text"].casefold()
    assert_questions(data, 3)


async def test_generated_lesson_assignment_rbac_and_authorized_retention(
    client, db, make_user, child_payload, caplog
):
    _, tutor, _ = await make_user()
    _, stranger, _ = await make_user()
    child = (await client.post("/api/v1/children", headers=tutor, json=child_payload)).json()
    captured = []

    def record(connection, cursor, statement, parameters, context, executemany):
        if "adaptation_contents" not in statement:
            captured.append(repr(parameters))

    event.listen(db.bind.sync_engine, "before_cursor_execute", record)
    try:
        response = await client.post(
            "/api/v1/adaptations/generate",
            headers=tutor,
            json={
                "category": "tecnologia",
                "topic": "Robots del océano",
                "child_id": child["id"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "Robots del océano" not in "\n".join(captured)
        assert data["adapted_text"] not in "\n".join(captured) + caplog.text
        assert data["title"] not in "\n".join(captured)
        stored = await db.get(models.Document, uuid.UUID(data["document"]["id"]))
        assert stored.category == "tecnologia"
        assert (await client.get(f"/api/v1/children/{child['id']}/library", headers=tutor)).json()[
            0
        ]["id"] == data["document"]["id"]
        assert (
            await client.post(
                "/api/v1/adaptations/generate",
                headers=stranger,
                json={"category": "deportes", "child_id": child["id"]},
            )
        ).status_code == 404
        assert (
            await client.post("/api/v1/adaptations/generate", json={"category": "deportes"})
        ).status_code == 401
    finally:
        event.remove(db.bind.sync_engine, "before_cursor_execute", record)


@pytest.mark.parametrize("endpoint", ["text", "file", "document"])
async def test_free_adaptation_fields_are_additive(client, make_user, endpoint):
    _, headers, _ = await make_user()
    if endpoint == "text":
        response = await client.post(
            "/api/v1/adaptations/text",
            headers=headers,
            json={"text": SOURCE, "nivel_simplificacion_nlp": 5},
        )
    else:
        response = await client.post(
            f"/api/v1/adaptations/{endpoint}?nivel_simplificacion_nlp=AVANZADO",
            headers={**headers, "Content-Type": "application/pdf"},
            content=pdf_bytes(SOURCE),
        )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "lectura_libre"
    assert data["simplification_level"] == 5
    assert data["title"]
    assert_questions(data)


@pytest.mark.parametrize(
    "text",
    [
        "Hola",
        "42",
        "sol " * 1000,
        " ".join(term for group in education._GROUPS for term in group)
        + " montaña océano bosque ciudad",
    ],
    ids=["tiny", "numeric", "long", "all-options-mentioned"],
)
def test_questions_never_prevent_valid_readings(text):
    assert_questions({"adapted_text": text, "comprehension_questions": education.questions(text)})


@pytest.mark.parametrize("level", [0, 6, True, 1.5])
async def test_invalid_generation_levels_rejected(client, make_user, level):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate",
        headers=headers,
        json={"category": "deportes", "simplification_level": level},
    )
    assert response.status_code == 422


async def test_question_generation_preserves_delivery_with_long_symbol_prefix(client, make_user):
    _, headers, _ = await make_user()
    source = "=" * 1000 + "Hola"
    response = await client.post("/api/v1/adaptations/text", headers=headers, json={"text": source})
    assert response.status_code == 200
    assert_questions(response.json())


async def test_document_alias_advertises_the_binary_request_contract(client):
    schema = (await client.get("/openapi.json")).json()
    body = schema["paths"]["/api/v1/adaptations/document"]["post"]["requestBody"]
    assert set(body["content"]) == {"application/pdf", "text/plain"}
