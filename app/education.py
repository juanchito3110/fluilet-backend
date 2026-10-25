"""Spanish lesson bank and extractive practice questions, without user-content storage."""

import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.nlp.segmentation import WORD_RE, sentences, words

CATEGORIES = (
    "ciencia_espacio",
    "animales_naturaleza",
    "historia_misterios",
    "deportes",
    "tecnologia",
    "cuentos_aventuras",
)


@dataclass(frozen=True)
class Lesson:
    title: str
    text: str


# Authored educational material, independent of user uploads or model weights.
_STUDY = (
    "Los alumnos utilizan libros y posteriormente realizan actividades para comprender "
    "mejor estas ideas con sus compañeros."
)
LESSONS = {
    "ciencia_espacio": (
        Lesson(
            "El viaje de la Tierra",
            "La Tierra gira alrededor del Sol y tarda cerca de un año en completar su recorrido. La rotación terrestre produce la sucesión del día y la noche. La luz solar proporciona energía a nuestro planeta y permite que numerosas plantas crezcan. "
            + _STUDY,
        ),
        Lesson(
            "La Luna y sus formas",
            "La Luna es un satélite natural de la Tierra y refleja la luz del Sol. Sus fases muestran diferentes partes de su superficie iluminada durante el mes. La observación de estas formas permite comprender que la Luna no produce luz propia, aunque frecuentemente parece una lámpara en el cielo. "
            + _STUDY,
        ),
        Lesson(
            "Una ventana a las estrellas",
            "El telescopio es un instrumento que permite observar objetos lejanos del cielo con mayor detalle. Algunos telescopios utilizan lentes y otros poseen espejos para recoger la luz. Las estrellas son enormes esferas de gas que proporcionan luz y energía, aunque desde la Tierra parecen pequeños puntos. "
            + _STUDY,
        ),
    ),
    "animales_naturaleza": (
        Lesson(
            "El trabajo de las abejas",
            "Las abejas visitan las flores para obtener néctar y polen. Durante sus desplazamientos transportan polen de una flor a otra, lo que facilita la reproducción de numerosas plantas. La conservación de jardines con flores proporciona alimento a estos insectos y es fundamental para proteger la diversidad natural. "
            + _STUDY,
        ),
        Lesson(
            "Las raíces del bosque",
            "Los árboles poseen raíces que absorben agua del suelo y ayudan a mantenerlos sujetos. Sus hojas utilizan la luz del Sol para producir alimento mediante la fotosíntesis. Un bosque proporciona refugio a numerosos animales y conserva una gran diversidad de seres vivos que se relacionan entre sí. "
            + _STUDY,
        ),
        Lesson(
            "El viaje del agua",
            "El agua de los mares se evapora con el calor y asciende hacia la atmósfera. Posteriormente, el vapor se enfría y forma pequeñas gotas que constituyen las nubes. La lluvia devuelve agua a la superficie terrestre, donde numerosos seres vivos la utilizan para realizar sus funciones vitales. "
            + _STUDY,
        ),
    ),
    "historia_misterios": (
        Lesson(
            "Las pistas de la arqueología",
            "La arqueología estudia los objetos y construcciones que dejaron las sociedades del pasado. Una vasija proporciona información sobre la alimentación y las actividades de sus habitantes. Los investigadores observan dónde aparece cada objeto y comparan numerosas pistas antes de proponer una explicación sobre su utilización original. "
            + _STUDY,
        ),
        Lesson(
            "La invención de la escritura",
            "La escritura permite conservar mensajes y compartir ideas con personas que viven lejos. Las sociedades han utilizado diferentes signos y materiales para registrar información, como tablillas, papel o piedra. La comparación de documentos antiguos proporciona pistas sobre la organización de las ciudades y sus intercambios comerciales. "
            + _STUDY,
        ),
        Lesson(
            "Los mapas cuentan historias",
            "Los mapas representan lugares mediante símbolos y permiten comprender cómo se organizan los territorios. Un mapa antiguo muestra los conocimientos y decisiones de quienes lo elaboraron en una época determinada. Para interpretar sus señales, los investigadores comparan nombres, distancias y numerosas referencias con otros documentos del pasado. "
            + _STUDY,
        ),
    ),
    "deportes": (
        Lesson(
            "El valor del juego en equipo",
            "Un equipo de fútbol necesita cooperación para defender su portería y crear oportunidades de gol. Los jugadores observan la posición de sus compañeros antes de realizar un pase. La comunicación respetuosa proporciona información útil y permite comprender que cada integrante contribuye al esfuerzo del conjunto. "
            + _STUDY,
        ),
        Lesson(
            "La constancia en el atletismo",
            "Una carrera de relevos combina la velocidad de varios corredores con una entrega cuidadosa del testigo. Cada participante debe comprender cuándo iniciar su desplazamiento y cómo coordinarse con el siguiente compañero. La práctica frecuente permite disminuir errores y demuestra que la colaboración es fundamental para finalizar el recorrido. "
            + _STUDY,
        ),
        Lesson(
            "Aprender las reglas del baloncesto",
            "El baloncesto combina desplazamientos, pases y lanzamientos hacia una canasta. Los jugadores utilizan el bote para avanzar con el balón y buscan espacios para colaborar con sus compañeros. Las reglas permiten organizar el encuentro y proporcionan un marco común para resolver desacuerdos de manera respetuosa durante el juego. "
            + _STUDY,
        ),
    ),
    "tecnologia": (
        Lesson(
            "Instrucciones para un robot",
            "Un robot sigue instrucciones que determinan cómo debe actuar ante una situación. Los programadores organizan esas instrucciones en una secuencia y comprueban los resultados para detectar errores. Un sensor proporciona información sobre el entorno, mientras que un motor permite realizar movimientos que forman parte de una tarea. "
            + _STUDY,
        ),
        Lesson(
            "Los mensajes viajan por redes",
            "Internet conecta numerosas redes que intercambian información mediante reglas compartidas. Un mensaje puede dividirse en pequeñas partes que viajan hasta su destino y posteriormente se reúnen. Las contraseñas ayudan a proteger el acceso a las cuentas, por lo que es fundamental mantenerlas privadas y evitar compartirlas. "
            + _STUDY,
        ),
        Lesson(
            "La energía del panel solar",
            "Un panel solar transforma la luz del Sol en energía eléctrica que puede utilizarse para realizar distintas tareas. Su funcionamiento depende de la luz que recibe y de las características de sus materiales. Comparar diferentes fuentes de energía permite comprender sus posibilidades y la importancia de utilizarlas responsablemente. "
            + _STUDY,
        ),
    ),
    "cuentos_aventuras": (
        Lesson(
            "El puente del bosque",
            "En este cuento, Nora descubre un puente de madera junto a un bosque y desea encontrar el camino de regreso a su aldea. Antes de cruzarlo, observa las tablas y solicita ayuda a sus compañeros. El grupo utiliza un mapa para comprender el recorrido y decide avanzar únicamente por el sendero señalado. "
            + _STUDY,
        ),
        Lesson(
            "La biblioteca del faro",
            "En esta aventura imaginaria, Leo encuentra una biblioteca dentro de un faro abandonado y descubre un libro con dibujos del puerto. La protagonista del libro es una navegante que busca una isla. Leo comprende que debe ordenar las pistas antes de iniciar su búsqueda y comparte sus descubrimientos con una amiga. "
            + _STUDY,
        ),
        Lesson(
            "El misterio de la semilla",
            "En este relato, Ada recibe una semilla y una carta que propone observar su crecimiento durante varias semanas. La niña utiliza una maceta y proporciona agua a la planta sin inundar la tierra. Posteriormente descubre las primeras hojas y comprende que la paciencia permite encontrar cambios que inicialmente pasan inadvertidos. "
            + _STUDY,
        ),
    ),
}
TOPIC_LESSONS = {
    "agujeros negros": Lesson(
        "Agujeros negros",
        "Los agujeros negros son regiones del espacio con una gravedad tan intensa que la luz no puede escapar de ellas. Los astrónomos estudian sus efectos sobre la materia cercana para obtener información. Algunos se forman cuando ciertas estrellas muy masivas llegan al final de su evolución. "
        + _STUDY,
    ),
    "dinosaurios": Lesson(
        "Dinosaurios",
        "Los dinosaurios fueron un grupo diverso de animales que habitaron la Tierra durante millones de años. Los fósiles proporcionan pistas sobre sus huesos, sus huellas y los lugares donde vivieron. No todos tenían el mismo tamaño ni se alimentaban igual, por lo que comparar numerosos restos permite comprender su diversidad. "
        + _STUDY,
    ),
}


def normalized(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)
    )


def category_name(value: str) -> str:
    slug = re.sub(r"[\s-]+", "_", normalized(value.strip()))
    return slug if slug in CATEGORIES or slug == "lectura_libre" else CATEGORIES[0]


def lesson(category: str, topic: str | None = None) -> tuple[str, Lesson]:
    category = category_name(category)
    if category == "lectura_libre":
        category = CATEGORIES[0]
    if topic:
        topic = " ".join(topic.split()).strip()
        key = normalized(topic)
        if key in TOPIC_LESSONS:
            selected = TOPIC_LESSONS[key]
            return category, Lesson(f"Exploramos: {topic}", selected.text)
        for entry in LESSONS[category]:
            if key in normalized(entry.title):
                return category, Lesson(f"{topic}: {entry.title}", entry.text)
        # Unknown topics receive an honest guided inquiry, without invented facts.
        return category, Lesson(
            f"Investigar: {topic}",
            f"El tema de esta investigación es {topic}. Para conocerlo, los alumnos utilizan "
            "libros y fuentes que identifican a sus autores. Posteriormente comparan la información "
            "y anotan las ideas que pueden comprobar. Una pregunta clara permite organizar la búsqueda. "
            "Finalmente, el grupo comparte sus hallazgos y distingue los hechos de las opiniones.",
        )
    return category, secrets.choice(LESSONS[category])


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
