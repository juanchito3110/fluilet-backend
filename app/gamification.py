"""Read-only FluiBot rewards derived from the authorized learner's sessions."""

from collections import Counter
from datetime import UTC
from statistics import mean

from app.education import CATEGORIES

# Thresholds refer to XP; legacy field names keep the existing client vocabulary.
_STAGES = (
    (
        0,
        150,
        "Explorador Inicial",
        "Núcleo de Energía",
        "Tu núcleo se enciende con cada lectura. ¡Descubre tu primera aventura!",
    ),
    (
        150,
        350,
        "Bot Explorador",
        "Bot Explorador",
        "FluiBot activa sus sensores para explorar nuevas palabras contigo.",
    ),
    (
        350,
        700,
        "Guardián Cyber-Lector",
        "Guardián Cyber-Lector",
        "Tu robot conecta ideas y protege todo lo que has aprendido leyendo.",
    ),
    (
        700,
        1200,
        "Sabio Cuántico",
        "Sabio Cuántico",
        "FluiBot ilumina nuevas rutas de aprendizaje. ¡Sigue compartiendo tus descubrimientos!",
    ),
)
_CARD_INFO = (
    ("Explorador del Cosmos", "La luz del Sol tarda unos ocho minutos en llegar a la Tierra."),
    (
        "Guardián de la Naturaleza",
        "Las abejas de la miel comunican con un baile dónde pueden encontrar alimento.",
    ),
    (
        "Detective del Pasado",
        "La piedra de Rosetta conserva un mismo mensaje en tres escrituras diferentes.",
    ),
    (
        "Campeón del Juego Limpio",
        "Las primeras canastas de baloncesto fueron cestas para melocotones.",
    ),
    ("Creador de Tecnología", "Un bit puede representar uno de dos valores: cero o uno."),
    (
        "Viajero de Aventuras",
        "Un cuento puede empezar por el final y revelar después cómo comenzó la aventura.",
    ),
)
_SHOP = (
    (
        "antena_prisma",
        "Antena Prisma Neón",
        "antenna",
        "Cristal multicolor que ilumina cada idea nueva",
        15,
    ),
    (
        "visor_holografico",
        "Visor Holográfico",
        "eyes",
        "Escanea cada renglón con precisión láser",
        25,
    ),
    (
        "corbatin_led",
        "Corbatín LED de Gala",
        "neck",
        "Toque elegante con luces digitales para grandes lectores",
        30,
    ),
    (
        "auriculares_sonicos",
        "Auriculares Sónicos",
        "ears",
        "Sintoniza el ritmo perfecto de la voz guía",
        40,
    ),
    (
        "emblema_estelar",
        "Emblema Estelar",
        "chest",
        "Insignia de energía dorada en el núcleo central",
        50,
    ),
    (
        "jetpack_plasma",
        "Jetpack de Plasma",
        "thrusters",
        "Propulsores dobles para impulsar tu fluidez lectora",
        60,
    ),
    (
        "mini_dron",
        "Mini-Dron Satélite",
        "companion",
        "Pequeño dron asistente que orbita junto a FluiBot",
        75,
    ),
    (
        "capa_fotonica",
        "Capa Fotónica",
        "back",
        "Manto de luz energética para máxima concentración",
        90,
    ),
    (
        "alas_cyber",
        "Alas Cyber-Halcón",
        "wings",
        "Alas tecnológicas desplegables de alta velocidad",
        100,
    ),
    (
        "corona_cuantica",
        "Corona Cuántica Dorada",
        "crown",
        "El máximo galardón holográfico para maestros de la lectura",
        120,
    ),
)


def _utc_day(session):
    recorded = session.ended_at or session.started_at
    if recorded.tzinfo is None:
        recorded = recorded.replace(tzinfo=UTC)
    return recorded.astimezone(UTC).date()


def _pedagogical_summary(sessions, finished, days, recommended_level):
    scores = [
        session.comprehension_score
        for session in sessions
        if session.comprehension_score is not None
    ]
    average = mean(scores) if scores else None
    completion_rate = len(finished) / len(sessions) if sessions else 0.0
    if average is not None and average >= 85:
        headline = "¡Tus ideas brillan con FluiBot!"
        strength = "Comprensión sobresaliente"
    elif days >= 3:
        headline = "¡Tu hábito lector sigue creciendo!"
        strength = "Constancia lectora"
    elif finished:
        headline = "¡Cada lectura completada abre una nueva aventura!"
        strength = "Finalización de lecturas"
    elif sessions:
        headline = "¡Cada intento te ayuda a aprender!"
        strength = "Participación en las actividades"
    else:
        headline = "¡Tu aventura con FluiBot comienza hoy!"
        strength = "Curiosidad por aprender"
    if average is not None and average < 50:
        focus = "Releer las ideas principales con calma"
    elif sessions and completion_rate < 1:
        focus = "Continuar las lecturas que has empezado"
    elif len({session.category for session in finished}) < 2:
        focus = "Explorar nuevas categorías de lectura"
    else:
        focus = "Relacionar ideas y explicar lo aprendido"
    speed = (
        "0.8x"
        if (average is not None and average < 50) or (sessions and completion_rate < 0.5)
        else "1.2x"
        if average is not None and average >= 85 and len(finished) >= 3 and completion_rate >= 0.75
        else "1.0x"
    )
    return {
        "headline": headline,
        "strength_area": strength,
        "focus_area": focus,
        "recommendation": f"Para la próxima sesión, usa el nivel {recommended_level} y la voz a {speed}. Lee con calma y vuelve a las ideas que quieras explorar.",
    }


def evolution(xp: int):
    if xp < 0:
        raise ValueError("XP must be nonnegative")
    index = max(index for index, stage in enumerate(_STAGES) if xp >= stage[0])
    lower, upper, rank, stage_name, description = _STAGES[index]
    return {
        "current_rank_title": rank,
        "next_rank_stars": upper,
        "mascot": {
            "name": "FluiBot",
            "species": "robot",
            "stage": index + 1,
            "stage_name": stage_name,
            "stage_description": description,
            "current_xp": xp,
            "next_stage_xp": upper,
            "progress_percent": min(100.0, 100.0 * (xp - lower) / (upper - lower)),
        },
    }


def progress_rewards(sessions, recommended_level, mission_bonus_gems=0):
    finished = [
        session
        for session in sessions
        if session.completed and float(session.completion_percent) == 100
    ]
    correct = sum(session.questions_correct for session in sessions)
    gems = 30 + 50 * len(finished) + 25 * correct + mission_bonus_gems
    xp = 100 * len(finished) + 50 * correct
    days = len({_utc_day(session) for session in finished})
    counts = Counter(session.category for session in finished)
    return {
        "streak_days": days,
        "total_gems": gems,
        "total_xp": xp,
        "total_stars": gems,
        **evolution(xp),
        "collectible_cards": [
            {
                "category": category,
                "title": title,
                "fun_fact": fact,
                "rarity": "Bloqueada"
                if counts[category] == 0
                else "Bronce"
                if counts[category] == 1
                else "Plata"
                if counts[category] == 2
                else "Oro",
                "unlocked": counts[category] >= 1,
                "lessons_completed_in_category": counts[category],
            }
            for category, (title, fact) in zip(CATEGORIES, _CARD_INFO, strict=True)
        ],
        "shop_catalog": [
            {
                "item_id": identifier,
                "name": name,
                "slot": slot,
                "description": description,
                "cost_gems": cost,
                "unlocked": gems >= cost,
            }
            for identifier, name, slot, description, cost in _SHOP
        ],
        "pedagogical_summary": _pedagogical_summary(sessions, finished, days, recommended_level),
    }
