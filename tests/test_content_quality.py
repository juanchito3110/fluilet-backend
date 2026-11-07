"""Product regressions: real facts, complete answers, short prose and account RBAC."""

import re
import uuid

import pytest
from sqlalchemy import func, select

from app import lesson_sources, models
from app.config import settings
from app.demo_accounts import PRESETS
from app.encyclopedia import ARTICLES
from app.lesson_sources import (
    _candidate_score,
    clean_extract,
    lesson_excerpt,
    resolve_lesson,
    resolve_topic,
)
from app.nlp.pipeline import pipeline
from app.nlp.readability import measure
from app.nlp.segmentation import sentences, words
from app.services.clear_spanish import LIMITS, rewrite
from app.services.comprehension import build_questions, norm
from app.services.lexicon_es import CURATED
from app.services.source_cleanup import sanitize

SUGGESTIONS = {
    "ciencia_espacio": (
        "Agujeros Negros",
        "Sistema Solar",
        "Volcanes",
        "Estrellas",
        "La NASA",
        "Marte",
    ),
    "animales_naturaleza": (
        "Biología Marina",
        "Tiburón Blanco",
        "Dinosaurios",
        "Selva Amazónica",
        "Animales Marinos",
    ),
    "historia_misterios": (
        "Pirámides de Egipto",
        "Piratas del Caribe",
        "Los Vikingos",
        "Castillos Medievales",
        "Antiguo Egipto",
    ),
    "deportes": ("Real Madrid", "Juegos Olímpicos", "Fútbol", "Natación", "Deportes"),
    "tecnologia": (
        "Robots",
        "Inteligencia Artificial",
        "Internet",
        "Videojuegos",
        "Inventos Increíbles",
        "Robótica",
    ),
    "cuentos_aventuras": ("Dragones", "Tesoros Piratas", "Viaje al Espacio", "Bosque Encantado"),
}


def assert_complete_questions(items):
    assert 3 <= len(items) <= 5
    assert len({q["question"] for q in items}) == len(items)
    for q in items:
        assert q["question"].startswith("¿") and q["question"].endswith("?")
        assert not re.search(r"___|\.\.\.|…", q["question"])
        assert len(q["options"]) == len(set(q["options"])) == 4
        assert 0 <= q["correct_option_index"] < 4
        assert all(3 <= len(words(option)) <= 12 and option[0].isupper() for option in q["options"])
        assert all(not re.search(r"___|\.\.\.|…", option) for option in q["options"])
        answer = q["options"][q["correct_option_index"]]
        assert answer in q["explanation"]
        assert q["hint"] and "La lectura explica:" in q["explanation"]


@pytest.mark.parametrize(
    "category,topic", [(c, t) for c, topics in SUGGESTIONS.items() for t in topics]
)
async def test_android_suggested_topics_resolve_to_child_safe_content(category, topic, monkeypatch):
    # Even if Wikipedia returns the known bad novel, curated story topics cannot
    # be diverted to it. No live network calls from tests.
    monkeypatch.setattr(settings, "WIKIPEDIA_ENABLED", True)
    calls = []

    async def unavailable(resolution):
        calls.append(resolution)
        return None

    monkeypatch.setattr(lesson_sources.wikipedia, "retrieve", unavailable)
    actual_category, article = await resolve_lesson(category, topic)
    assert actual_category == category
    assert resolve_topic(category, topic).local_key
    assert not any(
        bad in norm(article.text)
        for bad in ("the hazel wood", "titulo original", "editora y fundadora")
    )
    assert len(sentences(article.text)) >= 3
    if category == "cuentos_aventuras":
        assert not calls
        assert "cuento" in article.text.lower() and "ficción" in article.text


@pytest.mark.parametrize("key", sorted({key for preset in PRESETS for key in preset[7]}))
async def test_every_official_lesson_has_reviewed_questions_at_all_levels(key):
    result = await pipeline.run(ARTICLES[key].text, 1)
    for preview in result.level_previews:
        text = preview["adapted_text"]
        items = build_questions(text, 7, ARTICLES[key].text)
        assert_complete_questions(items)
        assert all("se escribe la palabra" not in item["question"] for item in items)
        assert all("___" not in item["hint"] for item in items)
        for item in items:
            evidence = re.search(r"La lectura explica: «(.+)»\.$", item["explanation"])[1]
            assert evidence in text


def test_nasa_year_is_a_specific_fact_with_four_temporal_options():
    text = "La NASA comenzó a trabajar en 1958. Sus equipos estudian el espacio. Apolo 11 llegó a la Luna en 1969."
    questions = build_questions(text, 7)
    target = next(q for q in questions if "comenzó a trabajar la NASA" in q["question"])
    assert target["options"][target["correct_option_index"]] == "En el año 1958"
    assert all(re.fullmatch(r"En el año \d{4}", option) for option in target["options"])
    assert "1958" in target["explanation"]
    assert_complete_questions(questions)


def test_unrelated_year_or_negated_event_is_never_assigned_to_nasa():
    text = "La NASA estudia el espacio. La abuela de Luis nació en 1958. El Sol da luz."
    questions = build_questions(text, 10)
    assert not any("año" in q["question"] and "NASA" in q["question"] for q in questions)
    assert any("abuela de Luis" in q["question"] and "1958" in q["explanation"] for q in questions)
    negated = build_questions(
        "La NASA no fue fundada en 1969. La agencia usa naves para estudiar el cielo.", 10
    )
    assert not any("año" in q["question"] for q in negated)


def test_sentence_analysis_terminates_for_a_coordinated_subject():
    source = (
        "La Tierra y la Luna reciben luz del Sol y reflejan parte de esa luz hacia otros lugares."
    )
    result = rewrite(source, 1)
    assert len(words(result)) < len(words(source)) * 3
    assert "La Tierra" in result and "Luna" in result and "Sol" in result


def test_cleanup_keeps_an_event_date_in_parentheses():
    text = "La agencia abrió sus puertas (1 de octubre de 1958)."
    assert "1 de octubre de 1958" in sanitize(text)[0]


def test_extractor_preserves_units_causes_and_negation_on_unseen_reading():
    text = "El vehículo Lince recorre 30 kilómetros. El motor no arranca porque no recibe energía. El equipo usa sensores para medir el calor."
    questions = build_questions(text, 10)
    assert_complete_questions(questions)
    quantity = next(q for q in questions if "kilómetros" in q["question"])
    assert all(option.endswith("kilómetros") for option in quantity["options"])
    cause = next(q for q in questions if "Por qué" in q["question"])
    assert cause["options"][cause["correct_option_index"]] == "Porque no recibe energía"


def test_cleanup_removes_metadata_but_preserves_qualified_scientific_facts():
    text = "La exploradora (cuyo título original en inglés es The Hazel Wood) usa un mapa.[1] El autor (1900–1980) nació lejos. La Luna (/ˈluna/) refleja luz. La medida (θ = 25) se conserva. El hielo (si recibe calor) puede fundirse."
    cleaned, removed = sanitize(text)
    assert all(term not in cleaned for term in ("Hazel", "1900", "1980", "ˈ", "[1]"))
    assert removed and "θ = 25" in cleaned and "si recibe calor" in cleaned
    assert clean_extract(text) == lesson_excerpt(cleaned, "12+")


@pytest.mark.parametrize(
    "title,body",
    [
        (
            "La NASA (novela)",
            "La NASA es una novela sobre el espacio y los planetas escrita por una editora.",
        ),
        (
            "Bosque Encantado",
            "Bosque Encantado es una película sobre naturaleza y animales del bosque.",
        ),
        (
            "Marina",
            "Marina es una cantante conocida por sus canciones sobre el océano y los animales.",
        ),
    ],
)
def test_wikipedia_rejects_media_even_with_matching_category_words(title, body):
    assert _candidate_score(resolve_topic("ciencia_espacio", "La NASA"), title, body) is None


@pytest.mark.parametrize("level", (1, 2, 3))
def test_structural_split_repeats_subject_and_keeps_negated_cause(level):
    text = "La nave recibe datos de la Tierra y usa sensores para medir la temperatura del suelo. El motor no arranca porque no recibe energía del panel solar."
    adapted = rewrite(text, level)
    assert "La nave usa sensores" in adapted if level <= 2 else "usa sensores" in adapted
    assert "no recibe energía" in adapted
    assert not any(fragment in adapted for fragment in ("Datos de.", "Para medir.", "Porque no."))


@pytest.mark.parametrize(
    "topic,key",
    [
        ("Real Madrid", "real madrid"),
        ("marina", "biologia marina"),
        ("Bosque Encantado", "bosque encantado"),
        ("La NASA", "nasa"),
    ],
)
async def test_real_generation_has_measurable_short_levels_and_grounded_challenge(
    client, make_user, topic, key
):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate",
        headers=headers,
        json={
            "category": ARTICLES[key].category,
            "custom_topic": topic,
            "target_level": 1,
            "age_group": "6-8",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert_complete_questions(data["comprehension_questions"])
    assert len(data["level_previews"]) == 5
    for preview in data["level_previews"][:3]:
        assert (
            max(len(words(unit)) for unit in sentences(preview["adapted_text"]))
            <= LIMITS[preview["level"]]
        )
        assert preview["readability_score"] == measure(preview["adapted_text"]).score
    assert data["adapted_avg_sentence_length"] < data["original_avg_sentence_length"]
    assert len({p["adapted_text"] for p in data["level_previews"]}) == 5
    assert (await client.get("/api/v1/adaptations/" + data["id"], headers=headers)).json() == data


async def test_zero_child_registration_is_visible_and_adult_reader_is_administrable(
    client, db, make_user
):
    master, admin_headers, _ = await make_user(models.UserRole.MASTER_ADMIN)
    master.email, master.demo_identity = "admin@fluilet.com", "master_admin"
    await db.commit()
    created = []
    for role in ("TUTOR", "ADULTO_INDEPENDIENTE"):
        email = f"new.{role.lower()}@example.com"
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "full_name": "Cuenta Nueva",
                "password": "TestAccount2026!",
                "role": role,
            },
        )
        assert response.status_code == 201, response.text
        created.append(response.json())
    assert await db.scalar(select(func.count()).select_from(models.ChildProfile)) == 0
    overview = (await client.get("/api/v1/admin/overview", headers=admin_headers)).json()
    assert {u["id"] for u in created} <= {u["user_id"] for u in overview["users"]}
    adult = created[1]
    profile = next(p for p in overview["profiles"] if p["profile_id"] == adult["id"])
    assert profile["tutor_email"] == adult["email"]
    initial_gems = profile["total_gems"]
    grant = await client.post(
        f"/api/v1/admin/profiles/{adult['id']}/grant",
        headers=admin_headers,
        json={"add_gems": 50, "set_level": 2},
    )
    assert grant.status_code == 200, grant.text
    assert (
        grant.json()["total_gems"] == initial_gems + 50
        and grant.json()["current_recommended_level"] == 2
    )
    login = await client.post(
        "/api/v1/auth/login", data={"username": adult["email"], "password": "TestAccount2026!"}
    )
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    own = await client.get("/api/v1/readings/progress", headers=headers)
    assert (
        own.json()["total_gems"] == initial_gems + 50
        and own.json()["current_recommended_level"] == 2
    )
    assert (await client.get("/api/v1/admin/overview", headers=headers)).status_code == 403
    assert (
        await client.post(f"/api/v1/admin/tutors/{adult['id']}/reset-pin", headers=admin_headers)
    ).status_code == 200
    assert (
        await client.delete(f"/api/v1/admin/profiles/{adult['id']}", headers=admin_headers)
    ).status_code == 204
    assert await db.get(models.User, uuid.UUID(adult["id"])) is None


def test_reviewed_dictionary_is_large_and_agreement_scoped():
    assert len(CURATED) >= 500
    assert CURATED["los dispositivos electrónicos"] == "los aparatos electrónicos"
    assert "mamíferos" not in CURATED


def test_public_cache_reuses_catalog_only_and_returns_isolated_previews():
    from app.services.pedagogy import _public_levels, choose_levels

    _public_levels.cache_clear()
    source = lesson_excerpt(ARTICLES["nasa"].text, "6-8")
    _, first, _ = choose_levels(source, allow_local_excerpt=True)
    expected = first[0]["adapted_text"]
    first[0]["adapted_text"] = "A consumer changed its own response."
    _, second, _ = choose_levels(source, allow_local_excerpt=True)
    assert second[0]["adapted_text"] == expected
    assert _public_levels.cache_info().hits == 1
    before = _public_levels.cache_info().currsize
    choose_levels("La astrónoma Lucía utiliza un mapa para observar una estrella desde su casa.")
    assert _public_levels.cache_info().currsize == before
