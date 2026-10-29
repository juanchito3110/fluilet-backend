"""Measured five-level rewrites, contextual resources and honest failure boundaries."""

import hashlib
import re
from collections import Counter

import pytest
from sqlalchemy import select

from app import models
from app.encyclopedia import ARTICLES
from app.lesson_sources import lesson_excerpt
from app.nlp.pipeline import pipeline
from app.nlp.readability import measure
from app.services import resources as lexical_resources
from app.services.demo_refresh import refresh_marked
from app.services.lexicon_es import CURATED
from app.services.pedagogy import GOALS, VERSION, cleanup, lexical, syntax


@pytest.mark.parametrize("key", list(ARTICLES))
async def test_reviewed_bank_has_five_measured_progressive_versions(key):
    original = ARTICLES[key].text
    result = await pipeline.run(original, 1)
    assert result.original_text == original
    assert len(result.level_previews) == 5 and result.level_progression_met
    assert [item["level"] for item in result.level_previews] == [1, 2, 3, 4, 5]
    scores = []

    def numbers(text):
        return Counter(re.findall(r"\d+(?:[.,]\d+)*", text))

    for item in result.level_previews:
        metric = measure(item["adapted_text"])
        low, high, *_ = GOALS[item["level"]]
        assert low <= metric.score <= high
        for support in item.get("pedagogical_support", []):
            assert support["evidence"] in original
        assert len({f["text"] for f in item.get("pedagogical_support", [])}) == len(
            item.get("pedagogical_support", [])
        )
        assert item["readability_score"] == pytest.approx(metric.score)
        assert item["avg_sentence_length"] == pytest.approx(
            metric.word_count / metric.sentence_count
        )
        assert numbers(item["adapted_text"]) == numbers(original)
        scores.append(metric.score)
    assert all(left > right for left, right in zip(scores, scores[1:], strict=False))
    assert len({item["adapted_text"] for item in result.level_previews}) == 5
    # Bidirectional advanced calibration is explicitly requested: an easy
    # original may have a richer level 5. Level 1 still never degrades it.
    assert scores[0] >= measure(original).score
    advanced = await pipeline.run(original, 5)
    assert ("advanced_level_harder_than_source" in advanced.warnings) == (
        scores[-1] < measure(original).score
    )


@pytest.mark.parametrize(
    "topic,category", [("Real Madrid", "deportes"), ("marina", "animales_naturaleza")]
)
@pytest.mark.parametrize(
    "path", ["/api/v1/adaptations", "/api/v1/adaptations/text", "/api/v1/adaptations/generate"]
)
async def test_http_comparison_and_previews_are_real_and_persisted(
    client, make_user, topic, category, path
):
    _, headers, _ = await make_user()
    key = "real madrid" if topic == "Real Madrid" else "biologia marina"
    source = ARTICLES[key].text
    body = (
        {"category": category, "custom_topic": topic, "target_level": 1}
        if path.endswith("generate")
        else {"text": source, "target_level": 1}
    )
    response = await client.post(path, headers=headers, json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    original, adapted = measure(data["original_text"]), measure(data["adapted_text"])
    assert data["original_text"] == (
        lesson_excerpt(source, data["age_group"]) if path.endswith("generate") else source
    )
    assert data["readability_gain"] == pytest.approx(adapted.score - original.score)
    assert data["readability_gain"] >= 15
    assert data["original_avg_sentence_length"] == pytest.approx(
        original.word_count / original.sentence_count
    )
    assert data["adapted_avg_sentence_length"] == pytest.approx(
        adapted.word_count / adapted.sentence_count
    )
    assert data["adapted_avg_sentence_length"] < data["original_avg_sentence_length"] * 0.7
    assert data["original_syllables_per_word"] == pytest.approx(
        original.syllable_count / original.word_count
    )
    assert data["adapted_syllables_per_word"] == pytest.approx(
        adapted.syllable_count / adapted.word_count
    )
    assert data["adapted_syllables_per_word"] < data["original_syllables_per_word"]
    assert data["lexical_replacements"] and len(data["level_previews"]) == 5
    assert data["engine_version"] == VERSION and data["level_progression_met"]
    assert data["model_version"] == "context-ranker-es-v2.3"
    assert data["checkpoint_name"] == "context-ranker-v2.3"
    assert data["adapted_text"] == data["level_previews"][0]["adapted_text"]
    assert (await client.get("/api/v1/adaptations/" + data["id"], headers=headers)).json() == data


def test_resource_index_reads_all_supplied_rows_and_keeps_context(tmp_path, monkeypatch):
    assert len(CURATED) >= 300
    header = "document_id;word_id;word;sentence;Sinónimos\n"
    first = "1;1;instrumentos;Los alumnos utilizan instrumentos para observar las plantas en el aula.;aparatos, útiles\n"
    second = "2;2;ubicación;La ubicación de los planetas cambia con el tiempo.;lugar, sitio\n"
    path = tmp_path / "SGSS.csv"
    path.write_bytes(header.encode("cp1252") + first.encode("utf-8") + second.encode("cp1252"))
    resources = lexical_resources.load_resources(path, root=tmp_path)
    assert resources.statistics["rows_read"] == 2
    assert resources.statistics["accepted_annotations"] == 4
    assert resources.statistics["corpus_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(lexical_resources, "resources", lambda: resources)
    assert (
        lexical_resources.choose_corpus(
            "instrumentos",
            "Los alumnos utilizan instrumentos para observar las plantas en el aula.",
            1,
        )
        == "útiles"
    )
    assert (
        lexical_resources.choose_corpus(
            "instrumentos", "Los músicos tocan instrumentos de cuerda.", 1
        )
        is None
    )
    assert lexical_resources.choose_corpus("instrumentos", first, 5) is None
    assert (
        lexical_resources.choose_corpus(
            "instrumentos", first + " Los instrumentos son distintos.", 1
        )
        is None
    )


def test_missing_corpus_remains_portable_and_does_not_activate_smoke_weights(tmp_path):
    r = lexical_resources.load_resources(tmp_path / "missing.csv", root=tmp_path)
    assert not r.statistics["corpus_present"] and r.statistics["curated_pairs"] >= 300
    assert r.corpus == {}
    empty = tmp_path / "empty.csv"
    empty.write_bytes(b"")
    assert (
        lexical_resources.load_resources(empty, root=tmp_path).statistics["corpus_status"]
        == "empty"
    )
    actual = lexical_resources.resources()
    assert all(item["auto_activated"] is False for item in actual.inventory["checkpoints"])
    if actual.statistics["corpus_present"]:
        assert (
            actual.statistics["rows_read"] >= 5000
            and actual.statistics["indexed_candidates"] >= 7000
        )


def test_noise_cleanup_is_reported_and_conditions_facts_equations_stay():
    source = "El autor (1828-1905) escribió una novela [1]. El agua (solo si está fría) cambia. El ángulo (θ=25) se mide. La palabra (AFI: /ˈsol/) se pronuncia."
    cleaned, removed = cleanup(source)
    assert "(1828-1905)" in removed and "[1]" in removed
    assert "(solo si está fría)" in cleaned and "(θ=25)" in cleaned
    assert "AFI" not in cleaned
    assert source.startswith("El autor (1828-1905)")


def test_active_voice_keeps_actor_object_date_and_academic_hedge():
    assert syntax("El club fue fundado por Pedro en 1902.", 1) == "Pedro fundó el club en 1902."
    assert (
        syntax("La casa fue construida por Los vecinos en 1902.", 1)
        == "Los vecinos construyeron la casa en 1902."
    )
    assert "se considera" in lexical("El equipo es considerado como un gran club.", 1)
    assert "grupo de huesos" not in lexical("El tiburón posee un esqueleto de cartílago.", 1)


async def test_intrinsically_simple_input_does_not_fabricate_five_difficulty_levels():
    result = await pipeline.run("Hola", 1)
    assert result.original_text == result.adapted_text == "Hola"
    assert not result.level_progression_met
    assert len(result.level_previews) == 5
    assert all(item["readability_score"] == measure("Hola").score for item in result.level_previews)
    assert "level_progression_not_available" in result.warnings


async def test_legacy_get_adds_truthful_comparison_without_rewriting_retained_pair(
    client, db, make_user
):
    _, headers, _ = await make_user()
    data = (
        await client.post(
            "/api/v1/adaptations/text", headers=headers, json={"text": ARTICLES["luna"].text}
        )
    ).json()
    import uuid

    content = await db.get(models.AdaptationContent, uuid.UUID(data["id"]))
    payload = dict(content.response_payload)
    for field in ("level_previews", "engine_version", "readability_gain", "lexical_replacements"):
        payload.pop(field, None)
    content.response_payload = payload
    await db.commit()
    returned = await client.get("/api/v1/adaptations/" + data["id"], headers=headers)
    assert returned.status_code == 200
    assert (
        returned.json()["original_text"] == data["original_text"]
        and returned.json()["adapted_text"] == data["adapted_text"]
    )
    assert len(returned.json()["level_previews"]) == 5
    await db.refresh(content)
    assert "engine_version" not in content.response_payload  # GET performs no write.


async def test_refresh_marked_preserves_activity_scores_resources_and_ids(
    db, client, make_user, child_payload
):
    _, headers, _ = await make_user()
    profile = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    seeded = (await client.post(f"/api/v1/profiles/{profile}/seed-demo", headers=headers)).json()
    readings = (await db.scalars(select(models.ReadingSession))).all()
    old = {
        row.id: (row.started_at, row.ended_at, row.comprehension_score, row.questions_correct)
        for row in readings
    }
    contents = (await db.scalars(select(models.AdaptationContent))).all()
    identities = {row.id for row in contents}
    for content in contents:
        content.response_payload = {**content.response_payload, "engine_version": "old-engine"}
    await db.commit()
    await refresh_marked(db)
    assert await refresh_marked(db, force=True) == 0
    refreshed = (
        await client.get(f"/api/v1/profiles/{profile}/educational-progress", headers=headers)
    ).json()
    assert (
        refreshed["total_gems"] == seeded["total_gems"]
        and refreshed["total_xp"] == seeded["total_xp"]
    )
    assert {
        row.id for row in (await db.scalars(select(models.AdaptationContent))).all()
    } == identities
    for row in (await db.scalars(select(models.ReadingSession))).all():
        assert (
            row.started_at,
            row.ended_at,
            row.comprehension_score,
            row.questions_correct,
        ) == old[row.id]
    assert await refresh_marked(db) == 0


async def test_ungraded_remote_known_topic_uses_honestly_attributed_local_reference(
    client, make_user, monkeypatch
):
    from app.encyclopedia import Article

    async def remote(category, topic):
        return category, Article(
            "Real Madrid Club de Fútbol",
            "El Real Madrid es un club de fútbol de España. Su equipo juega al fútbol en el estadio Santiago Bernabéu de la ciudad de Madrid.",
            category,
            "https://es.wikipedia.org/wiki/Real_Madrid_Club_de_F%C3%BAtbol",
            provider="wikipedia",
        )

    monkeypatch.setattr("app.adaptations.resolve_lesson", remote)
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/generate",
        headers=headers,
        json={"category": "deportes", "custom_topic": "Real Madrid", "target_level": 1},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["source"]["provider"] == "local"
    assert data["original_text"] == lesson_excerpt(ARTICLES["real madrid"].text, "6-8")
    assert data["level_progression_met"] and data["readability_gain"] >= 15
    assert "pedagogical_local_reference" in data["warnings"]
