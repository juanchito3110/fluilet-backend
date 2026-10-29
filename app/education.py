"""Spanish lesson bank and extractive practice questions, without user-content storage."""

import re
import secrets
import unicodedata
from datetime import UTC, date, datetime

from app.encyclopedia import ARTICLES, BANK, Article
from app.nlp.segmentation import WORD_RE, sentences, words

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


# Same-field alternatives keep extractive cloze options grammatical and plausible.
_GROUPS = (
    ("Sol", "cielo", "horizonte", "firmamento"),
    ("Tierra", "Luna", "atmósfera", "superficie"),
    ("agua", "aire", "hielo", "vapor"),
    ("flores", "hojas", "raíces", "ramas"),
    ("luz", "electricidad", "gravedad", "temperatura"),
    ("libros", "mapas", "dibujos", "cuadernos"),
    ("pasado", "presente", "futuro", "invierno"),
    ("información", "energía", "velocidad", "distancia"),
    ("balón", "testigo", "mapa", "libro"),
    ("compañeros", "jugadores", "corredores", "investigadores"),
    ("telescopio", "microscopio", "termómetro", "periscopio"),
    ("arqueología", "geografía", "astronomía", "botánica"),
    ("escritura", "pintura", "escultura", "música"),
    ("fútbol", "baloncesto", "voleibol", "balonmano"),
    ("robot", "ordenador", "vehículo", "ascensor"),
    ("bosque", "desierto", "océano", "valle"),
    ("biblioteca", "escuela", "estación", "tienda"),
    ("semilla", "piedra", "pluma", "moneda"),
)


def title_for(text: str) -> str:
    return " ".join(words(text)[:10])[:160] or "Lectura para aprender"


def _standard_questions(text: str) -> list[dict]:
    """Two literal cloze tasks, grounded in the actual delivered text.

    Never invent an answer. Tiny inputs use two explicit recognition prompts;
    long inputs use bounded source spans so response size stays predictable.
    """
    units = sentences(text)
    vocabulary = {token.casefold() for token in words(text)}
    lower_text = text.casefold()
    selected = sorted(
        enumerate(units), key=lambda pair: (not 5 <= len(words(pair[1])) <= 35, pair[0])
    )
    chosen = [unit for _, unit in selected[:2]]
    if len(chosen) == 1:
        chosen *= 2
    result = []
    for index, sentence in enumerate(chosen):
        normalized_sentence = " ".join(sentence.split())
        span = normalized_sentence[:480]
        if not words(span):
            first_word = WORD_RE.search(normalized_sentence)
            span = normalized_sentence[first_word.start() : first_word.start() + 480]
        if len(words(span)) > 35:
            span = " ".join(span.split()[:30])
        choices = []
        for group in _GROUPS:
            for term in group:
                matches = list(re.finditer(r"\b" + re.escape(term) + r"\b", span, flags=re.I))
                alternatives = [other for other in group if other.casefold() not in vocabulary]
                if matches and len(alternatives) >= 2:
                    choices.append((matches[-1], alternatives))
        if choices:
            match, alternatives = choices[index % len(choices)]
            correct = match[0]
            prompt = span[: match.start()] + "___" + span[match.end() :]
            distractors = alternatives[:2]
        else:
            tokens = list(re.finditer(r"[^\W\d_]+|\d+(?:[.,]\d+)*", span))
            match = tokens[-1]
            correct = match[0]
            prompt = span[: match.start()] + "___" + span[match.end() :]
            distractors = [
                value
                for value in ("montaña", "océano", "bosque", "ciudad")
                if value.casefold() not in vocabulary
            ][:2]
            # An arbitrary valid document can contain every standard alternative.
            # Distinct invented references remain recognizably Spanish, not tokens.
            number = 1
            while len(distractors) < 2:
                alternative = f"lugar {number}"
                if alternative not in lower_text and alternative != correct.casefold():
                    distractors.append(alternative)
                number += 1
        question = (
            f"Según la lectura, ¿qué completa {'esta idea' if index == 0 else 'este fragmento'}: «{prompt}»?"
            if choices
            else (
                "Según la lectura, ¿cuál de estos fragmentos aparece en el texto?"
                if index == 0
                else "¿Qué palabra o fragmento coincide con la lectura?"
            )
        )
        options = [correct, *distractors]
        correct_index = secrets.randbelow(3)
        options[0], options[correct_index] = options[correct_index], options[0]
        result.append(
            {
                "id": f"q{index + 1}",
                "question": question,
                "options": options,
                "correct_option_index": correct_index,
                "hint": "Pista: Relee esa parte y busca la idea que falta. ¡Tú puedes!",
                "explanation": f"¡Bien! El texto menciona «{correct}» en esa parte de la lectura.",
            }
        )
    return result


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


def _brief_span(sentence):
    sentence = " ".join(sentence.split())
    first_word = WORD_RE.search(sentence)
    start = first_word.start() if not words(sentence[:480]) else 0
    span = sentence[start : start + 480]
    return " ".join(span.split()[:30]).rstrip(".!?…")


_VERB = re.compile(
    r"\b(?:es|son|está|están|tiene|tienen|produce|producen|recibe|reciben|permite|permiten|"
    r"ayuda|ayudan|usa|usan|vive|viven|hace|hacen|lee|leen|necesita|necesitan|"
    r"puede|pueden|gira|giran|llueve|crece|crecen|busca|buscan|ocurre|sucede)\b",
    re.I,
)


def _idea_options(answer, text):
    vocabulary = {token.casefold() for token in words(text)}
    candidates = []
    for group in _GROUPS:
        for term in group:
            match = re.search(r"\b" + re.escape(term) + r"\b", answer, flags=re.I)
            if match:
                candidates.extend(
                    answer[: match.start()] + other + answer[match.end() :]
                    for other in group
                    if other.casefold() not in vocabulary
                )
    verb = _VERB.search(answer)
    if verb:
        prefix = answer[: verb.start()]
        candidates.append(
            prefix[:-3] + answer[verb.start() :]
            if prefix.casefold().endswith("no ")
            else prefix + "no " + answer[verb.start() :]
        )
        candidates.append(prefix + "solo " + answer[verb.start() :])
    for topic in ("una montaña", "un barco", "un jardín", "una estación"):
        candidates.append(f"La lectura describe {topic}")
    options, seen = [answer], {answer.casefold()}
    normalized_text = " ".join(text.casefold().split())
    for candidate in candidates:
        if candidate.casefold() not in seen and candidate.casefold() not in normalized_text:
            options.append(candidate)
            seen.add(candidate.casefold())
        if len(options) == 3:
            break
    # A valid input may contain every generic alternative. Keep these distractors
    # explicit practice statements rather than inventing an answer about the text.
    number = 1
    while len(options) < 3:
        candidate = f"La lectura presenta el lugar {number}"
        if candidate.casefold() not in normalized_text:
            options.append(candidate)
        number += 1
    index = secrets.randbelow(3)
    options[0], options[index] = options[index], options[0]
    return options, index


def _intermediate_questions(text):
    spans = [_brief_span(unit) for unit in sentences(text)]
    answers = [spans[0], spans[1] if len(spans) > 1 else spans[0]]
    prompts = [
        "¿Qué idea aparece en esta lectura?",
        "¿Qué otra idea puedes reconocer en la lectura?",
    ]
    hints = [
        "Pista: Busca la idea de la primera oración. ¡Tú puedes!",
        "Pista: Relee esa parte y busca qué cuenta el texto.",
    ]
    explanations = ["La lectura presenta esta idea", "El texto también incluye esta idea"]
    for span in spans:
        cause = re.search(r"\b(?:porque|debido a que)\s+(.+)", span, flags=re.I)
        result = re.search(r"\b(?:por eso|por lo que)[, ]+(.+)", span, flags=re.I)
        if cause:
            answers[1] = cause[1]
            prompts[1] = "¿Qué causa explica el resultado mencionado en la lectura?"
            hints[1] = "Pista: Busca la causa después de «porque» o «debido a que»."
            explanations[1] = "El texto explica que esta es la causa"
            break
        if result:
            answers[1] = result[1]
            prompts[1] = "¿Qué ocurre como resultado, según la lectura?"
            hints[1] = "Pista: Busca el resultado junto a «por eso» o «por lo que»."
            explanations[1] = "La lectura señala este resultado"
            break
    else:
        for span in spans:
            purpose = re.search(r"\b(?:para|el fin es)\s+(.+)", span, flags=re.I)
            if purpose:
                answers[1] = purpose[1]
                prompts[1] = "¿Qué propósito se explica en la lectura?"
                hints[1] = "Pista: Busca «para» o «el fin es». ¡Lo encontrarás!"
                explanations[1] = "El texto explica este propósito"
                break
    result = []
    for index, answer in enumerate(answers):
        options, correct_index = _idea_options(answer, text)
        result.append(
            {
                "id": f"q{index + 1}",
                "question": prompts[index],
                "options": options,
                "correct_option_index": correct_index,
                "hint": hints[index],
                "explanation": f"¡Buen trabajo! {explanations[index]}: «{answer}».",
            }
        )
    return result


def questions(text: str, child_age_years: int | None = None) -> list[dict]:
    group = question_age_group(child_age_years)
    if group == "9-11":
        return _intermediate_questions(text)
    result = _standard_questions(text)
    if group == "6-8":
        for index, item in enumerate(result):
            correct = item["options"][item["correct_option_index"]]
            item["question"] = (
                "Vamos, ¿qué palabra aparece en la lectura?"
                if index == 0
                else "Ahora, ¿qué palabra encuentras en el texto?"
            )
            item["options"] = [f"Dice «{option}»" for option in item["options"]]
            item["hint"] = "¡Tú puedes! Busca esa palabra en la lectura."
            item["explanation"] = (
                f"¡Muy bien! El texto dice «{correct}». Por eso esa opción es correcta."
            )
    return result


def lesson_questions(text: str, child_age_years: int | None, source: str) -> list[dict]:
    """Three literal tasks whose answers occur in both the excerpt and reading.

    Manual adaptations and historical seed payloads keep their two-question
    contract. Only new generated lessons use this source-bounded mini-challenge.
    """
    source_words = {word.casefold() for word in words(source)}
    vocabulary = {word.casefold() for word in words(text)}
    stop = set(
        "el la los las un una unos unas de del y e o a en por para que con al es son "
        "su sus lo se como más muy hay cada este esta estos estas ese esa esos esas "
        "tiene tienen puede pueden también del sin entre sobre desde hasta pero "
        "donde cuando quien quienes tras durante así luego otra otro otros otras".split()
    )
    group = question_age_group(child_age_years)
    pool = []
    used = set()
    for unit in sentences(text):
        span = _brief_span(unit)
        for match in WORD_RE.finditer(span):
            term = match[0].casefold()
            if term not in source_words or term in stop or term in used or len(term) < 3:
                continue
            pool.append((span, match))
            used.add(term)
            break
    # Short source sentences can share most of their vocabulary. Still select
    # distinct grounded words before reusing a literal evidence span.
    if len(pool) < 3:
        for unit in sentences(text):
            span = _brief_span(unit)
            for match in WORD_RE.finditer(span):
                term = match[0].casefold()
                if term in source_words and term not in stop and term not in used:
                    pool.append((span, match))
                    used.add(term)
    if not pool:
        raise ValueError("generated_lesson_has_no_shared_evidence")
    result = []
    for index in range(3):
        span, match = pool[index % len(pool)]
        answer = match[0]
        alternatives = next(
            (
                [value for value in family if value.casefold() not in vocabulary | source_words]
                for family in _GROUPS
                if answer.casefold() in {value.casefold() for value in family}
                and len([v for v in family if v.casefold() not in vocabulary | source_words]) >= 2
            ),
            [],
        )
        for value in ("montaña", "océano", "bosque", "ciudad", "planeta", "jardín"):
            if value not in vocabulary | source_words and value not in alternatives:
                alternatives.append(value)
        number = 1
        while len(alternatives) < 2:
            value = f"lugar {number}"
            if value not in text.casefold() and value not in source.casefold():
                alternatives.append(value)
            number += 1
        options = [answer, *alternatives[:2]]
        correct_index = secrets.randbelow(3)
        options[0], options[correct_index] = options[correct_index], options[0]
        cloze = span[: match.start()] + "___" + span[match.end() :]
        prompt = f"Según la lectura, ¿qué completa esta idea: «{cloze}»?"
        if group == "6-8":
            prompt = "Vamos, ¿qué palabra aparece en la lectura?"
            options = [f"Dice «{option}»" for option in options]
        elif group == "9-11":
            prompt = "¿Qué palabra completa esta idea de la lectura?"
        result.append(
            {
                "id": f"q{index + 1}",
                "question": prompt,
                "options": options,
                "correct_option_index": correct_index,
                "hint": f"Pista: Completa esta idea de la lectura: «{cloze}».",
                "explanation": f"¡Muy bien! La lectura dice: «{span}».",
            }
        )
    return result


def profile_age_group(profile):
    return profile.age_group_override or question_age_group(age_years(profile.birth_date))


def teaching_age(profile):
    return {"6-8": 7, "9-11": 10, "12+": 12}.get(
        profile.age_group_override, age_years(profile.birth_date)
    )
