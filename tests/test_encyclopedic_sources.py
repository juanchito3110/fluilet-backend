"""Offline factual coverage and deterministic, bounded Wikipedia protocol tests."""

import asyncio
import logging
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy import func, select

from app import lesson_sources, models
from app.config import settings
from app.encyclopedia import ARTICLES
from app.lesson_sources import (
    SourceUnavailable,
    WikipediaSource,
    clean_extract,
    resolve_lesson,
    resolve_topic,
)
from app.nlp.segmentation import words


@pytest.mark.parametrize(
    "category,topic,fragment",
    [
        ("deportes", "Real Madrid", "Real Madrid Club de Fútbol"),
        ("animales_naturaleza", "marina", "Biología marina"),
        ("ciencia_espacio", "marina", "Biología marina"),
        ("historia_misterios", "egipcia", "Antiguo Egipto"),
        ("deportes", "olímpicos", "Juegos Olímpicos"),
        ("tecnologia", "artificial", "Inteligencia artificial"),
    ],
)
def test_contextual_resolution(category, topic, fragment):
    result = resolve_topic(category, topic)
    assert fragment.casefold() in result.title.casefold()
    assert result.local_key in ARTICLES
    assert result.category == category


@pytest.mark.parametrize(
    "topic,key",
    [
        ("Real Madrid", "real madrid"),
        ("fútbol", "futbol"),
        ("marina", "biologia marina"),
        ("tiburón", "tiburon"),
        ("dinosaurios", "dinosaurios"),
        ("sistema solar", "sistema solar"),
        ("agujeros negros", "agujeros negros"),
        ("volcanes", "volcanes"),
        ("egipcia", "antiguo egipto"),
        ("robots", "robots"),
        ("inteligencia artificial", "inteligencia artificial"),
    ],
    ids=[
        "club",
        "football",
        "marine",
        "shark",
        "dinosaurs",
        "solar-system",
        "black-holes",
        "volcanoes",
        "egypt",
        "robots",
        "ai",
    ],
)
async def test_rich_local_encyclopedia_is_available_without_network(topic, key):
    category = ARTICLES[key].category
    result_category, article = await resolve_lesson(category, topic)
    assert result_category == category and article.provider == "local"
    assert len(words(article.text)) >= 60
    assert article.url.startswith("https://")
    assert not any(
        term in article.text.casefold()
        for term in (
            "buscan en libros",
            "para conocerlo",
            "el tema de esta investigación",
            "los alumnos utilizan libros",
        )
    )


@pytest.mark.parametrize(
    "category,topic,fragments",
    [
        ("deportes", "Real Madrid", ["1902", "FIFA", "Santiago Bernabéu"]),
        ("animales_naturaleza", "marina", ["biología", "mar", "animales"]),
        ("historia_misterios", "egipcia", ["Nilo", "jeroglíficos", "papiro"]),
        ("deportes", "olímpicos", ["1896", "Atenas", "1924"]),
    ],
)
@pytest.mark.parametrize("level", [1, 3, 5])
async def test_custom_topic_returns_subject_facts_glossary_and_questions(
    client, make_user, category, topic, fragments, level
):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate",
        headers=headers,
        json={"category": category, "custom_topic": topic, "target_level": level},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["category"] == category and data["simplification_level"] == level
    assert data["source"]["provider"] == "local"
    assert data["resolved_topic"] == data["title"]
    for fragment in fragments:
        assert fragment.casefold() in data["adapted_text"].casefold()
    assert not any(
        marker in data["adapted_text"].casefold()
        for marker in (
            "buscan en libros",
            "en la biblioteca aprendemos",
            "interesante para investigar",
            "los alumnos utilizan libros",
        )
    )
    assert data["fun_fact"] and "«" in data["fun_fact"]
    assert 3 <= len(data["key_vocabulary"]) <= 4
    for item in data["key_vocabulary"]:
        assert set(item) == {"word", "definition", "example"}
        assert item["word"] in data["adapted_text"] and item["word"] in item["example"]
        assert item["definition"].strip()
    for question in data["comprehension_questions"]:
        answer = question["options"][question["correct_option_index"]]
        if data["question_age_group"] == "6-8":
            assert answer.startswith("Dice «") and answer.endswith("»")
            answer = answer[len("Dice «") : -1]
        assert answer in data["adapted_text"]
        assert question["hint"] and question["explanation"]


async def test_unknown_offline_topic_fails_without_filler_or_retention(
    client, db, make_user, caplog
):
    _, headers, _ = await make_user()
    private = "tema privado que no figura en la enciclopedia"
    response = await client.post(
        "/api/v1/adaptations/generate",
        headers=headers,
        json={"category": "tecnologia", "custom_topic": private},
    )
    assert response.status_code == 503
    assert private not in response.text and private not in caplog.text
    assert await db.scalar(select(func.count()).select_from(models.Document)) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"topic": "robots", "custom_topic": "dinosaurios"},
        {"simplification_level": 1, "target_level": 5},
        {"target_level": 6},
        {"target_level": True},
    ],
    ids=["topic-conflict", "level-conflict", "invalid-level", "boolean-level"],
)
async def test_aliases_are_retrocompatible_and_conflicts_are_controlled(client, make_user, payload):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate", headers=headers, json={"category": "tecnologia", **payload}
    )
    assert response.status_code == 422


def test_extract_cleanup_preserves_factual_years_figures_and_parenthetical_data():
    text = "25/10/2026\nEl club (/ˈklub/) fue fundado en 1902.[1] Su estadio abrió en 1947 (capacidad: 80000). La medida (θ = 25) se conserva."
    cleaned = clean_extract(text)
    assert "ˈ" not in cleaned and "[1]" not in cleaned and "25/10/2026" not in cleaned
    assert all(value in cleaned for value in ("1902", "1947", "80000", "θ = 25"))


async def test_wikipedia_scores_all_five_candidates_and_rejects_disambiguation(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    calls = []
    entries = [
        {
            "pageid": 1,
            "title": "Marina",
            "extract": "Marina es una cantante que interpreta canciones y trabaja en discos musicales. Su carrera comenzó en varios escenarios de Europa y sus actuaciones reúnen público.",
        },
        {
            "pageid": 2,
            "title": "Marina (desambiguación)",
            "extract": "Marina puede referirse a una cantante, una fuerza naval o diferentes localidades. La palabra tiene usos en muchos países y en la cultura.",
            "pageprops": {"disambiguation": ""},
        },
        {
            "pageid": 3,
            "title": "Biología marina",
            "extract": ARTICLES["biologia marina"].text + "[1]",
            "lastrevid": 9876,
        },
        {
            "pageid": 4,
            "title": "Marina de guerra",
            "extract": "La marina de guerra es una fuerza militar que organiza barcos. Sus operaciones incluyen el transporte y la navegación en diferentes regiones del mundo.",
        },
        {
            "pageid": 5,
            "title": "Biología",
            "extract": "La biología estudia los seres vivos, su ambiente y su evolución. Los animales y las plantas forman parte de sus temas de estudio en la naturaleza.",
        },
    ]

    async def handler(request):
        assert str(request.url) == lesson_sources.WIKIPEDIA_API
        assert request.method == "POST" and request.headers["User-Agent"] == "FluiletEdTech/1.0"
        params = parse_qs(request.content.decode())
        calls.append(params)
        if "list" in params:
            assert params["srlimit"] == ["5"]
            assert "Biología marina" in params["srsearch"][0]
            return httpx.Response(
                200,
                json={
                    "query": {
                        "search": [
                            {"pageid": item["pageid"], "title": item["title"]} for item in entries
                        ]
                    }
                },
            )
        assert params["exintro"] == ["1"] and params["explaintext"] == ["1"]
        assert params["pageids"][0] == "1|2|3|4|5"
        return httpx.Response(200, json={"query": {"pages": entries}})

    source = WikipediaSource(httpx.MockTransport(handler))
    article = await source.retrieve(resolve_topic("animales_naturaleza", "marina"))
    assert article.title == "Biología marina" and article.provider == "wikipedia"
    assert article.revision_id == 9876
    assert len(calls) == 2
    assert "Biología marina" not in caplog.text


async def test_wikipedia_budget_and_unavailability_use_local_facts(monkeypatch):
    monkeypatch.setattr(settings, "WIKIPEDIA_ENABLED", True)
    monkeypatch.setattr(settings, "WIKIPEDIA_TIMEOUT_SECONDS", 0.01)

    async def slow(request):
        await asyncio.sleep(1)
        raise AssertionError("Cancelled before completion")

    source = WikipediaSource(httpx.MockTransport(slow))
    monkeypatch.setattr(lesson_sources, "wikipedia", source)
    _, article = await resolve_lesson("deportes", "Real Madrid")
    assert article.provider == "local" and "1902" in article.text
    assert not source.slots.locked()


@pytest.mark.parametrize(
    "failure", ["rate-limit", "server-error", "invalid-json", "oversize", "api-error"]
)
async def test_remote_failures_never_become_invented_lessons(monkeypatch, failure):
    monkeypatch.setattr(settings, "WIKIPEDIA_ENABLED", True)

    def handler(request):
        if failure == "rate-limit":
            return httpx.Response(429)
        if failure == "server-error":
            return httpx.Response(503)
        if failure == "invalid-json":
            return httpx.Response(200, content=b"not-json")
        if failure == "oversize":
            return httpx.Response(200, content=b"x" * 262145)
        return httpx.Response(200, json={"error": {"info": "private query details"}})

    monkeypatch.setattr(lesson_sources, "wikipedia", WikipediaSource(httpx.MockTransport(handler)))
    _, article = await resolve_lesson("animales_naturaleza", "marina")
    assert article.provider == "local" and "océanos" in article.text
    with pytest.raises(SourceUnavailable):
        await resolve_lesson("tecnologia", "un tema inexistente")


async def test_wikipedia_generated_response_retains_attribution_and_original_facts(
    client, make_user, monkeypatch
):
    monkeypatch.setattr(settings, "WIKIPEDIA_ENABLED", True)
    article = ARTICLES["real madrid"]

    def handler(request):
        params = parse_qs(request.content.decode())
        if "list" in params:
            return httpx.Response(
                200, json={"query": {"search": [{"pageid": 42, "title": article.title}]}}
            )
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "pageid": 42,
                            "title": article.title,
                            "extract": article.text,
                            "lastrevid": 123,
                        }
                    ]
                }
            },
        )

    monkeypatch.setattr(lesson_sources, "wikipedia", WikipediaSource(httpx.MockTransport(handler)))
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate",
        headers=headers,
        json={"category": "deportes", "custom_topic": "Real Madrid"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"]["provider"] == "wikipedia" and data["source"]["revision_id"] == 123
    assert data["source"]["license"] == "CC BY-SA 4.0"
    assert data["source"]["license_url"].startswith("https://creativecommons.org/")
    assert "1902" in data["adapted_text"] and data["source"]["url"].startswith(
        "https://es.wikipedia.org/wiki/"
    )
