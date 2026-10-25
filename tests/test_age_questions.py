"""Birthday boundaries and age-aware questions from authorized PostgreSQL profiles."""

import re
import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import event

from app import education, models
from app.nlp.segmentation import words
from tests.conftest import SOURCE
from tests.test_zero_retention import pdf_bytes


@pytest.mark.parametrize(
    "birthday,today,expected",
    [
        (date(2017, 10, 25), date(2026, 10, 24), 8),
        (date(2017, 10, 24), date(2026, 10, 24), 9),
        (date(2014, 10, 25), date(2026, 10, 24), 11),
        (date(2014, 10, 24), date(2026, 10, 24), 12),
        (date(2016, 2, 29), date(2024, 2, 28), 7),
        (date(2016, 2, 29), date(2024, 2, 29), 8),
        (date(2016, 2, 29), date(2025, 2, 28), 8),
        (date(2016, 2, 29), date(2025, 3, 1), 9),
    ],
    ids=[
        "before-nine",
        "ninth-birthday",
        "before-twelve",
        "twelfth-birthday",
        "before-leap-birthday",
        "leap-birthday",
        "nonleap-february",
        "nonleap-march",
    ],
)
def test_calendar_age_boundaries(birthday, today, expected):
    assert education.age_years(birthday, today) == expected


def assert_age_questions(data, age):
    group = "12+" if age is None or age >= 12 else "6-8" if age <= 8 else "9-11"
    assert data["child_age_years"] == age
    assert data["question_age_group"] == group
    assert len(data["comprehension_questions"]) == 2
    source = " ".join(data["adapted_text"].split())
    for item in data["comprehension_questions"]:
        assert set(item) == {
            "id",
            "question",
            "options",
            "correct_option_index",
            "hint",
            "explanation",
        }
        assert len(item["options"]) == 3
        assert len(set(item["options"])) == 3
        answer = item["options"][item["correct_option_index"]]
        assert item["hint"].strip() and item["explanation"].strip()
        if group == "6-8":
            assert 5 <= len(words(item["question"])) <= 9
            assert all(2 <= len(words(option)) <= 4 for option in item["options"])
            answer = re.fullmatch(r"Dice «(.+)»", answer)[1]
        elif group == "9-11":
            assert len(words(item["question"])) <= 12
        assert answer in source
        assert answer in item["explanation"]


@pytest.mark.parametrize("endpoint", ["generate", "text", "document", "file"])
@pytest.mark.parametrize(
    "age",
    [6, 8, 9, 11, 12, None],
    ids=["six", "eight", "nine", "eleven", "grown-profile", "no-child"],
)
async def test_age_groups_on_all_adaptation_routes(
    client, db, make_user, child_payload, endpoint, age
):
    _, headers, _ = await make_user()
    child_id = None
    if age is not None:
        child_id = (
            await client.post("/api/v1/children", headers=headers, json=child_payload)
        ).json()["id"]
        profile = await db.get(models.ChildProfile, uuid.UUID(child_id))
        # An existing profile can grow beyond the original registration age range.
        profile.birth_date = date(datetime.now(UTC).year - age, 1, 1)
        await db.commit()
    if endpoint == "generate":
        response = await client.post(
            "/api/v1/adaptations/generate",
            headers=headers,
            json={"category": "ciencia_espacio", "child_id": child_id},
        )
    elif endpoint == "text":
        response = await client.post(
            "/api/v1/adaptations/text", headers=headers, json={"text": SOURCE, "child_id": child_id}
        )
    else:
        suffix = f"?child_id={child_id}" if child_id else ""
        response = await client.post(
            f"/api/v1/adaptations/{endpoint}{suffix}",
            headers={**headers, "Content-Type": "application/pdf"},
            content=pdf_bytes(SOURCE),
        )
    assert response.status_code == 200, response.text
    assert_age_questions(response.json(), age)
    assert response.headers["cache-control"] == "no-store"


async def test_independent_adult_uses_standard_questions(client, make_user):
    _, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    response = await client.post(
        "/api/v1/adaptations/generate", headers=headers, json={"category": "deportes"}
    )
    assert response.status_code == 200
    assert_age_questions(response.json(), None)


@pytest.mark.parametrize(
    "source,answer,question_kind",
    [
        ("El hielo se derrite porque recibe calor. El Sol da luz.", "recibe calor", "causa"),
        (
            "El niño lee debido a que quiere conocer el bosque. El bosque tiene árboles.",
            "quiere conocer el bosque",
            "causa",
        ),
        ("Las semillas reciben agua, por lo que crecen. El Sol da luz.", "crecen", "resultado"),
        ("Las semillas reciben agua. Por eso, crecen.", "crecen", "resultado"),
        (
            "Los alumnos usan libros para conocer el bosque. El Sol da luz.",
            "conocer el bosque",
            "propósito",
        ),
        ("El niño no juega porque no tiene balón. Su amigo lee.", "no tiene balón", "causa"),
    ],
    ids=["cause", "because", "result", "linked-result", "purpose", "negated-cause"],
)
def test_intermediate_causal_answers_are_actual_evidence(source, answer, question_kind):
    questions = education.questions(source, 10)
    assert question_kind in questions[1]["question"]
    assert questions[1]["options"][questions[1]["correct_option_index"]] == answer
    assert answer in questions[1]["explanation"]
    assert all(len(words(item["question"])) <= 12 for item in questions)


@pytest.mark.parametrize("age", [6, 9, None], ids=["early", "intermediate", "standard"])
def test_tiny_and_symbol_prefixed_readings_stay_grounded(age):
    for source in ("Hola", "42", "=" * 1000 + "Hola", "sol " * 1000):
        data = {
            "adapted_text": source,
            "child_age_years": age,
            "question_age_group": education.question_age_group(age),
            "comprehension_questions": education.questions(source, age),
        }
        assert_age_questions(data, age)


def test_intermediate_questions_do_not_invent_causality():
    questions = education.questions("El Sol es una estrella. La Luna refleja luz.", 9)
    assert "causa" not in questions[1]["question"] and "resultado" not in questions[1]["question"]
    assert questions[1]["options"][questions[1]["correct_option_index"]] == "La Luna refleja luz"


@pytest.mark.parametrize("endpoint", ["generate", "text", "document"])
async def test_foreign_child_cannot_disclose_age(client, make_user, child_payload, endpoint):
    _, owner, _ = await make_user()
    _, stranger, _ = await make_user()
    child_id = (await client.post("/api/v1/children", headers=owner, json=child_payload)).json()[
        "id"
    ]
    if endpoint == "document":
        response = await client.post(
            f"/api/v1/adaptations/document?child_id={child_id}",
            headers={**stranger, "Content-Type": "text/plain"},
            content=SOURCE,
        )
    else:
        payload = {"category": "deportes"} if endpoint == "generate" else {"text": SOURCE}
        response = await client.post(
            f"/api/v1/adaptations/{endpoint}",
            headers=stranger,
            json={**payload, "child_id": child_id},
        )
    assert response.status_code == 404
    assert "child_age_years" not in response.text and "question_age_group" not in response.text


async def test_hints_and_age_are_not_persisted_as_document_content(
    client, db, make_user, child_payload
):
    _, headers, _ = await make_user()
    child_id = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    captured = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE")):
            captured.append(repr(parameters))

    event.listen(db.bind.sync_engine, "before_cursor_execute", capture)
    try:
        response = await client.post(
            "/api/v1/adaptations/text", headers=headers, json={"text": SOURCE, "child_id": child_id}
        )
        assert response.status_code == 200
        writes = "\n".join(captured)
        for question in response.json()["comprehension_questions"]:
            assert question["hint"] not in writes and question["explanation"] not in writes
        for table in (models.Document.__table__, models.ReadingSession.__table__):
            assert not {"question_age_group", "child_age_years", "hint", "explanation"} & set(
                table.columns.keys()
            )
    finally:
        event.remove(db.bind.sync_engine, "before_cursor_execute", capture)
