"""FluiBot uses stored, owner-scoped reading evidence with repeatable rewards."""

import json
import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app import models
from app.education import CATEGORIES
from app.gamification import evolution

EXPECTED_SHOP = [
    ("antena_prisma", "Antena Prisma Neón", "antenna", 15),
    ("visor_holografico", "Visor Holográfico", "eyes", 25),
    ("corbatin_led", "Corbatín LED de Gala", "neck", 30),
    ("auriculares_sonicos", "Auriculares Sónicos", "ears", 40),
    ("emblema_estelar", "Emblema Estelar", "chest", 50),
    ("jetpack_plasma", "Jetpack de Plasma", "thrusters", 60),
    ("mini_dron", "Mini-Dron Satélite", "companion", 75),
    ("capa_fotonica", "Capa Fotónica", "back", 90),
    ("alas_cyber", "Alas Cyber-Halcón", "wings", 100),
    ("corona_cuantica", "Corona Cuántica Dorada", "crown", 120),
]


def row(
    owner, *, day=1, category="ciencia_espacio", correct=2, completed=True, ended=True, score=100
):
    started = datetime(2026, 1, day, 8, tzinfo=UTC)
    return models.ReadingSession(
        **owner,
        started_at=started,
        ended_at=started + timedelta(minutes=1) if ended and completed else None,
        reading_time_seconds=60 if completed else 10,
        completion_percent=100 if completed else 25,
        completed=completed,
        category=category,
        simplification_level=3,
        questions_answered=2,
        questions_correct=correct,
        comprehension_score=score,
        tts_speed_used=1.0,
    )


def assert_catalog(data):
    catalog = data["shop_catalog"]
    assert len(catalog) == len({item["item_id"] for item in catalog}) == 10
    assert [
        (item["item_id"], item["name"], item["slot"], item["cost_gems"]) for item in catalog
    ] == EXPECTED_SHOP
    for item in catalog:
        assert set(item) == {"item_id", "name", "slot", "description", "cost_gems", "unlocked"}
        assert item["description"].strip()
        assert item["unlocked"] == (data["total_gems"] >= item["cost_gems"])


@pytest.mark.parametrize(
    "xp,stage,rank,next_xp",
    [
        (0, 1, "Explorador Inicial", 150),
        (149, 1, "Explorador Inicial", 150),
        (150, 2, "Bot Explorador", 350),
        (349, 2, "Bot Explorador", 350),
        (350, 3, "Guardián Cyber-Lector", 700),
        (699, 3, "Guardián Cyber-Lector", 700),
        (700, 4, "Sabio Cuántico", 1200),
        (1200, 4, "Sabio Cuántico", 1200),
        (5000, 4, "Sabio Cuántico", 1200),
    ],
)
def test_all_evolution_boundaries(xp, stage, rank, next_xp):
    result = evolution(xp)
    assert result["current_rank_title"] == rank
    assert result["next_rank_stars"] == next_xp
    mascot = result["mascot"]
    assert mascot["name"] == "FluiBot" and mascot["species"] == "robot"
    assert mascot["stage"] == stage and mascot["current_xp"] == xp
    assert mascot["next_stage_xp"] == next_xp
    assert (
        mascot["stage_name"]
        == ["Núcleo de Energía", "Bot Explorador", "Guardián Cyber-Lector", "Sabio Cuántico"][
            stage - 1
        ]
    )
    lower = [0, 150, 350, 700][stage - 1]
    assert mascot["progress_percent"] == min(100.0, 100.0 * (xp - lower) / (next_xp - lower))
    assert mascot["stage_description"]


@pytest.mark.parametrize("adult", [True, False])
async def test_welcome_gems_make_first_three_accessories_available(
    client, make_user, child_payload, adult
):
    role = models.UserRole.ADULTO_INDEPENDIENTE if adult else models.UserRole.TUTOR
    _, headers, _ = await make_user(role)
    if adult:
        url = "/api/v1/readings/progress"
    else:
        child_id = (
            await client.post("/api/v1/children", headers=headers, json=child_payload)
        ).json()["id"]
        url = f"/api/v1/children/{child_id}/progress"
    first = (await client.get(url, headers=headers)).json()
    second = (await client.get(url, headers=headers)).json()
    assert first == second
    assert first["total_gems"] == first["total_stars"] == 30
    assert first["total_xp"] == first["streak_days"] == 0
    assert first["mascot"]["stage"] == 1
    assert first["current_rank_title"] == "Explorador Inicial"
    assert all(
        card["rarity"] == "Bloqueada" and not card["unlocked"]
        for card in first["collectible_cards"]
    )
    assert_catalog(first)
    assert [item["item_id"] for item in first["shop_catalog"] if item["unlocked"]] == [
        item[0] for item in EXPECTED_SHOP[:3]
    ]
    assert "1.0x" in first["pedagogical_summary"]["recommendation"]


@pytest.mark.parametrize("adult", [True, False])
async def test_complete_progress_rewards_cards_and_days_are_owner_scoped(
    client, db, make_user, child_payload, adult
):
    role = models.UserRole.ADULTO_INDEPENDIENTE if adult else models.UserRole.TUTOR
    user, headers, _ = await make_user(role)
    if adult:
        owner, url = {"reader_user_id": user.id}, "/api/v1/readings/progress"
    else:
        child_id = (
            await client.post("/api/v1/children", headers=headers, json=child_payload)
        ).json()["id"]
        owner, url = {"child_id": uuid.UUID(child_id)}, f"/api/v1/children/{child_id}/progress"
    readings = [
        row(owner, day=1),
        row(owner, day=1),
        row(owner, day=1),
        row(owner, day=3, category="animales_naturaleza"),
        row(owner, day=3, category="animales_naturaleza"),
        row(owner, day=6, category="historia_misterios", ended=False),
        row(owner, day=7, category="deportes", correct=1, completed=False, score=50),
    ]
    stranger, _, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    db.add_all([*readings, row({"reader_user_id": stranger.id}, day=8, category="tecnologia")])
    await db.commit()
    count = await db.scalar(select(func.count()).select_from(models.ReadingSession))
    data = (await client.get(url, headers=headers)).json()
    assert data["completed_lessons"] == 6 and data["total_lessons"] == 7
    assert (
        data["streak_days"] == 3
    )  # Distinct practice dates, including gaps and a legacy end time.
    assert data["total_gems"] == data["total_stars"] == 30 + 50 * 6 + 25 * 13
    assert data["total_xp"] == 100 * 6 + 50 * 13
    assert data["mascot"]["stage"] == 4 and data["mascot"]["progress_percent"] == 100
    assert data["current_rank_title"] == "Sabio Cuántico"
    cards = data["collectible_cards"]
    assert [card["category"] for card in cards] == list(CATEGORIES)
    assert [
        (card["lessons_completed_in_category"], card["rarity"], card["unlocked"]) for card in cards
    ] == [
        (3, "Oro", True),
        (2, "Plata", True),
        (1, "Bronce", True),
        (0, "Bloqueada", False),
        (0, "Bloqueada", False),
        (0, "Bloqueada", False),
    ]
    assert cards[0]["title"] == "Explorador del Cosmos"
    assert all(card["fun_fact"] and card["title"] for card in cards)
    assert_catalog(data)
    advice = data["pedagogical_summary"]
    assert set(advice) == {"headline", "strength_area", "focus_area", "recommendation"}
    assert advice["strength_area"] == "Comprensión sobresaliente"
    assert "1.2x" in advice["recommendation"]
    assert f"nivel {data['current_recommended_level']}" in advice["recommendation"]
    assert (await client.get(url, headers=headers)).json() == data
    assert await db.scalar(select(func.count()).select_from(models.ReadingSession)) == count
    if not adult:
        legacy = (await client.get(url + "/legacy", headers=headers)).json()
        assert isinstance(legacy, list) and set(legacy[0]) == {
            "sessionLabel",
            "accumulatedMinutes",
            "completionPercent",
        }
    wording = json.dumps(
        {
            key: data[key]
            for key in ("mascot", "shop_catalog", "collectible_cards", "pedagogical_summary")
        },
        ensure_ascii=False,
    ).casefold()
    assert not any(
        term in wording for term in ("clínic", "diagnóst", "paciente", "tratamiento", "síntoma")
    )


@pytest.mark.parametrize("category", CATEGORIES)
@pytest.mark.parametrize(
    "completed,rarity", [(0, "Bloqueada"), (1, "Bronce"), (2, "Plata"), (3, "Oro")]
)
async def test_each_card_rarity_follows_completed_category_count(
    client, db, make_user, category, completed, rarity
):
    user, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    db.add_all(row({"reader_user_id": user.id}, category=category) for _ in range(completed))
    await db.commit()
    data = (await client.get("/api/v1/readings/progress", headers=headers)).json()
    card = next(card for card in data["collectible_cards"] if card["category"] == category)
    assert card["rarity"] == rarity
    assert card["unlocked"] == bool(completed)
    assert card["lessons_completed_in_category"] == completed


@pytest.mark.parametrize(
    "correct,gems,available", [(0, 30, 3), (1, 55, 5), (2, 80, 7), (3, 105, 9), (4, 130, 10)]
)
async def test_economical_shop_thresholds(client, db, make_user, correct, gems, available):
    user, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    db.add(
        models.ReadingSession(
            reader_user_id=user.id,
            questions_answered=4,
            questions_correct=correct,
            comprehension_score=25 * correct,
        )
    )
    await db.commit()
    data = (await client.get("/api/v1/readings/progress", headers=headers)).json()
    assert data["total_gems"] == gems and data["total_xp"] == 50 * correct
    assert sum(item["unlocked"] for item in data["shop_catalog"]) == available
    assert_catalog(data)


async def test_finishing_first_lesson_rewards_once_and_makes_full_catalog_affordable(
    client, make_user
):
    _, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    lesson = (
        await client.post(
            "/api/v1/adaptations/generate", headers=headers, json={"category": "tecnologia"}
        )
    ).json()
    reading = (
        await client.post(
            "/api/v1/readings", headers=headers, json={"document_id": lesson["document"]["id"]}
        )
    ).json()
    response = await client.patch(
        f"/api/v1/readings/{reading['id']}",
        headers=headers,
        json={
            "completion_percent": 100,
            "completed": True,
            "questions_answered": 2,
            "questions_correct": 2,
        },
    )
    assert response.status_code == 200
    data = (await client.get("/api/v1/readings/progress", headers=headers)).json()
    assert data["total_gems"] == 130 and data["total_xp"] == 200
    assert data["streak_days"] == 1 and data["mascot"]["stage"] == 2
    assert_catalog(data)
    assert all(item["unlocked"] for item in data["shop_catalog"])
    assert (await client.get("/api/v1/readings/progress", headers=headers)).json() == data


@pytest.mark.parametrize(
    "score,finished,speed", [(20, True, "0.8x"), (90, True, "1.0x"), (None, False, "0.8x")]
)
async def test_pedagogical_feedback_responds_to_actual_practice(
    client, db, make_user, score, finished, speed
):
    user, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    record = models.ReadingSession(
        reader_user_id=user.id,
        completed=finished,
        completion_percent=100 if finished else 25,
        comprehension_score=score,
        simplification_level=2,
    )
    db.add(record)
    await db.commit()
    data = (await client.get("/api/v1/readings/progress", headers=headers)).json()
    advice = data["pedagogical_summary"]
    assert speed in advice["recommendation"]
    assert f"nivel {data['current_recommended_level']}" in advice["recommendation"]
    if score == 20:
        assert advice["focus_area"] == "Releer las ideas principales con calma"
    if score == 90:
        assert advice["strength_area"] == "Comprensión sobresaliente"


async def test_distinct_days_use_completion_date_and_one_utc_calendar(client, db, make_user):
    user, headers, _ = await make_user(models.UserRole.ADULTO_INDEPENDIENTE)
    owner = {"reader_user_id": user.id}
    first, second, third = row(owner), row(owner), row(owner)
    first.ended_at = datetime(2026, 1, 2, 0, 30, tzinfo=timezone(timedelta(hours=2)))
    second.ended_at = datetime(2026, 1, 1, 23, tzinfo=UTC)
    third.ended_at = datetime(2026, 1, 5, 10, tzinfo=UTC)
    db.add_all([first, second, third])
    await db.commit()
    data = (await client.get("/api/v1/readings/progress", headers=headers)).json()
    assert data["streak_days"] == 2
