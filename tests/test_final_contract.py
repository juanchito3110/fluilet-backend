"""Principal output must match requested level, age and its retained version."""

import uuid

import pytest

from app import models
from app.nlp.readability import measure
from app.services.pedagogy import label
from app.services.ranker import model_info
from tests.test_retrained_model import UNSEEN, pdf_bytes


@pytest.mark.parametrize("path", ["", "/text", "/generate", "/file", "/document"])
@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
async def test_requested_level_is_actual_primary_and_persisted(client, make_user, path, level):
    _, headers, _ = await make_user()
    if path in ("/file", "/document"):
        source = UNSEEN[0]["source"]
        response = await client.post(
            "/api/v1/adaptations" + path + f"?level={level}",
            headers={**headers, "Content-Type": "application/pdf"},
            content=pdf_bytes(source),
        )
    else:
        body = (
            {"category": "deportes", "custom_topic": "Real Madrid", "level": level}
            if path == "/generate"
            else {"text": UNSEEN[0]["source"], "level": level}
        )
        response = await client.post("/api/v1/adaptations" + path, headers=headers, json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    preview = data["level_previews"][level - 1]
    assert data["target_level"] == data["simplification_level"] == level
    assert data["adapted_text"] == preview["adapted_text"]
    assert (
        data["readability_score"]
        == preview["readability_score"]
        == measure(data["adapted_text"]).score
    )
    assert (
        data["readability_level"]
        == preview["readability_level"]
        == label(data["readability_score"])
    )
    assert data["questions"] == data["comprehension_questions"]
    assert len(data["questions"]) == (3 if path == "/generate" else 2)
    assert data["model_version"] == "context-ranker-es-v2.3"
    assert data["checkpoint_name"] == "context-ranker-v2.3"
    assert (await client.get("/api/v1/adaptations/" + data["id"], headers=headers)).json() == data


@pytest.mark.parametrize("group,level", [("6-8", 1), ("9-11", 3), ("12+", 5)])
@pytest.mark.parametrize("path", ["/text", "/generate", "/file"])
async def test_age_only_selects_level_and_questions(client, make_user, path, group, level):
    _, headers, _ = await make_user()
    if path == "/file":
        response = await client.post(
            "/api/v1/adaptations/file?age_group=" + group.replace("+", "%2B"),
            headers={**headers, "Content-Type": "text/plain"},
            content=UNSEEN[0]["source"].encode(),
        )
    else:
        body = {
            "age_group": group,
            **({"category": "deportes"} if path == "/generate" else {"text": UNSEEN[0]["source"]}),
        }
        response = await client.post("/api/v1/adaptations" + path, headers=headers, json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["target_level"] == level
    assert data["age_group"] == data["question_age_group"] == group
    assert data["adapted_text"] == data["level_previews"][level - 1]["adapted_text"]


async def test_explicit_age_wins_over_profile_and_level_wins_over_age(
    client, db, make_user, child_payload
):
    _, headers, _ = await make_user()
    child = (await client.post("/api/v1/children", headers=headers, json=child_payload)).json()[
        "id"
    ]
    profile = await db.get(models.ChildProfile, uuid.UUID(child))
    profile.age_group_override = "12+"
    await db.commit()
    data = (
        await client.post(
            "/api/v1/adaptations/generate",
            headers=headers,
            json={"category": "deportes", "child_id": child, "age_group": "6-8", "level": 5},
        )
    ).json()
    assert data["target_level"] == 5 and data["question_age_group"] == "6-8"
    assert data["adapted_text"] == data["level_previews"][4]["adapted_text"]


async def test_versions_do_not_return_latest_level_in_place_of_requested_level(client, make_user):
    _, headers, _ = await make_user()
    responses = []
    for level in (1, 5):
        response = await client.post(
            "/api/v1/adaptations/generate",
            headers=headers,
            json={
                "category": "deportes",
                "custom_topic": "Real Madrid",
                "level": level,
                "age_group": "9-11",
            },
        )
        assert response.status_code == 200
        responses.append(response.json())
    first, last = responses
    assert first["id"] != last["id"] and first["adapted_text"] != last["adapted_text"]
    assert first["readability_score"] > last["readability_score"]
    for record in responses:
        assert (
            await client.get("/api/v1/adaptations/" + record["id"], headers=headers)
        ).json() == record


async def test_conflicting_aliases_fail_without_echoing_text(client, make_user):
    _, headers, _ = await make_user()
    response = await client.post(
        "/api/v1/adaptations/text",
        headers=headers,
        json={"text": "PRIVATE CONTENT", "level": 1, "target_level": 5},
    )
    assert response.status_code == 422 and "PRIVATE" not in response.text


def test_benchmark_and_band_success_are_not_fabricated():
    info = model_info()
    before, after = info["baseline_metrics"], info["retrained_metrics"]
    expected = (
        after["sari_score"] > before["sari_score"]
        and after["band_distance"] < before["band_distance"]
        and after["lexical_top1"] > before["lexical_top1"]
    )
    assert info["all_comparisons_improved"] == expected
    assert info["baseline_sari"] == before["sari_score"]
    assert info["retrained_sari"] == after["sari_score"]
    expected_bands = all(
        group["all_five_bands_met"] == group["samples"] and group["progressive"] == group["samples"]
        for group in info["band_compliance"].values()
    )
    assert info["all_bands_met"] == expected_bands
    assert info["acceptance_criteria_met"] == (expected and expected_bands)
    assert info["acceptance_criteria_met"] is True
    assert info["band_compliance"]["local_bank"]["samples"] == 31
    assert info["easier_benchmark_after"] == "6/6"
