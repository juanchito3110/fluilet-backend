"""Spanish lesson bank and evidence-backed, age-aware comprehension tasks."""

import re
import unicodedata
from datetime import UTC, date, datetime

from app.encyclopedia import ARTICLES, BANK, Article
from app.nlp.segmentation import words

CATEGORIES = (
    "ciencia_espacio",
    "animales_naturaleza",
    "historia_misterios",
    "deportes",
    "tecnologia",
    "cuentos_aventuras",
)


# Public bank aliases retained for callers of the original educational API.
Lesson = Article
LESSONS = {category: tuple(ARTICLES[key] for key in keys) for category, keys in BANK.items()}
TOPIC_LESSONS = {key: ARTICLES[key] for key in ("agujeros negros", "dinosaurios")}


def normalized(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)
    )


def category_name(value: str) -> str:
    slug = re.sub(r"[\s-]+", "_", normalized(value.strip()))
    return slug if slug in CATEGORIES or slug == "lectura_libre" else CATEGORIES[0]


def lesson(category: str, topic: str | None = None) -> tuple[str, Lesson]:
    # Synchronous, strictly local compatibility helper. Serving uses the async
    # contextual resolver, which can query Wikipedia before this fallback.
    from app.lesson_sources import local_article, resolve_topic

    resolution = resolve_topic(category, topic)
    article = local_article(resolution)
    if article is None:
        raise ValueError("source_unavailable")
    return resolution.category, article


def title_for(text: str) -> str:
    return " ".join(words(text)[:10])[:160] or "Lectura para aprender"


def age_years(birth_date: date, on_date: date | None = None) -> int:
    today = on_date or datetime.now(UTC).date()
    return (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


def question_age_group(child_age_years: int | None) -> str:
    if child_age_years is None or child_age_years >= 12:
        return "12+"
    return "6-8" if child_age_years <= 8 else "9-11"


def questions(
    text: str, child_age_years: int | None = None, source: str | None = None
) -> list[dict]:
    from app.services.comprehension import build_questions

    return build_questions(text, child_age_years, source)


def lesson_questions(text: str, child_age_years: int | None, source: str) -> list[dict]:
    from app.services.comprehension import build_questions

    return build_questions(text, child_age_years, source)


def profile_age_group(profile):
    return profile.age_group_override or question_age_group(age_years(profile.birth_date))


def teaching_age(profile):
    return {"6-8": 7, "9-11": 10, "12+": 12}.get(
        profile.age_group_override, age_years(profile.birth_date)
    )
