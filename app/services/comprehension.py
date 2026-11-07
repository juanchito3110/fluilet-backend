"""Evidence-first Spanish comprehension tasks with typed, whole-answer options.

Reviewed questions cover the official teaching readings. The open-text extractor
only licenses full dates, quantities, definitions, actions and causal clauses;
it never slices a word window to pretend it is a grammatical fact.
"""

import hashlib
import math
import re
from dataclasses import dataclass

from app.nlp.segmentation import sentences, words


def norm(value):
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)
    )


@dataclass(frozen=True)
class Fact:
    stem: str
    answer: str
    distractors: tuple[str, str, str]
    evidence: str
    kind: str


# topic, evidence expressions (each required), question, four same-type answers,
# kind. Anchors are checked against BOTH the source excerpt and actual reading.
REVIEWED = (
    (
        "luna",
        ("refleja", "sol"),
        "¿De dónde viene la luz que refleja la Luna?",
        ("De la luz del Sol", "De la luz de Marte", "De la luz de Venus", "De la luz de Saturno"),
        "origin",
    ),
    (
        "luna",
        ("29,5",),
        "¿Cuánto dura un ciclo de fases de la Luna?",
        ("Cerca de 29,5 días", "Cerca de 7 días", "Cerca de 15 días", "Cerca de 60 días"),
        "quantity",
    ),
    (
        "luna",
        ("crater", "golpes|impactos"),
        "¿Qué causó muchos cráteres de la Luna?",
        (
            "Los impactos contra su superficie",
            "Los flujos de lava endurecida",
            "Los cambios de temperatura del suelo",
            "La acumulación de polvo en montículos",
        ),
        "cause",
    ),
    (
        "luna",
        ("mareas", "gravedad|fuerza"),
        "¿Qué relación tiene la Luna con las mareas?",
        (
            "Su gravedad influye en ellas",
            "Su luz reflejada calienta el agua",
            "Su órbita impide el movimiento del agua",
            "Sus fases cambian la presión del aire",
        ),
        "concept",
    ),
    (
        "madrid",
        ("1902",),
        "¿En qué año se fundó el Real Madrid?",
        ("En el año 1902", "En el año 1920", "En el año 1947", "En el año 1896"),
        "year",
    ),
    (
        "madrid",
        ("1920", "real"),
        "¿Cuándo recibió el club el título de Real?",
        ("En el año 1920", "En el año 1902", "En el año 1947", "En el año 1958"),
        "year",
    ),
    (
        "madrid",
        ("blanc",),
        "¿Qué color caracteriza la camiseta del Real Madrid?",
        (
            "Una camiseta de color blanco",
            "Una camiseta de color verde",
            "Una camiseta de color rojo",
            "Una camiseta de color azul",
        ),
        "attribute",
    ),
    (
        "madrid",
        ("santiago bernabeu",),
        "¿En qué estadio juega de local el Real Madrid?",
        (
            "En el estadio Santiago Bernabéu",
            "En el estadio de Mestalla",
            "En el estadio de Maracaná",
            "En el estadio de Wembley",
        ),
        "place",
    ),
    (
        "madrid",
        ("1947",),
        "¿En qué año abrió el estadio Santiago Bernabéu?",
        ("En el año 1947", "En el año 1902", "En el año 1920", "En el año 1969"),
        "year",
    ),
    (
        "madrid",
        ("fifa", "siglo xx"),
        "¿Qué reconocimiento otorgó la FIFA al Real Madrid?",
        (
            "Mejor club del siglo XX",
            "Mejor club del siglo XIX",
            "Mejor selección del siglo XX",
            "Mejor selección del siglo XIX",
        ),
        "concept",
    ),
    (
        "marina",
        ("estudia", "vida|seres vivos", "mar"),
        "¿Qué estudia la biología marina?",
        (
            "Los seres vivos del mar",
            "Los seres vivos de agua dulce",
            "Los animales de las zonas desérticas",
            "Las plantas de las zonas montañosas",
        ),
        "concept",
    ),
    (
        "marina",
        ("algas", "luz", "alimento|comida"),
        "¿Para qué aprovechan la luz las algas?",
        (
            "Para producir su propio alimento",
            "Para mantener constante su temperatura corporal",
            "Para transportar agua entre sus tejidos",
            "Para fijarse a las rocas del fondo",
        ),
        "purpose",
    ),
    (
        "marina",
        ("coral", "refugio"),
        "¿Qué proporcionan los arrecifes de coral a muchos animales?",
        (
            "Un refugio donde pueden vivir",
            "Un soporte para sostener equipos de pesca",
            "Una zona para acumular arena de playa",
            "Un lugar donde termina el agua dulce",
        ),
        "purpose",
    ),
    (
        "marina",
        ("bioluminiscencia", "luz"),
        "¿Qué significa bioluminiscencia en esta lectura?",
        (
            "Producir luz por uno mismo",
            "Cambiar de forma para evitar una captura",
            "Moverse siguiendo las corrientes del agua",
            "Detectar presas mediante señales del entorno",
        ),
        "vocabulary",
    ),
    (
        "futbol|fútbol",
        ("once", "jugadores"),
        "¿Cuántos jugadores tiene cada equipo de fútbol en el campo?",
        (
            "Un total de once jugadores",
            "Un total de cinco jugadores",
            "Un total de nueve jugadores",
            "Un total de siete jugadores",
        ),
        "quantity",
    ),
    (
        "futbol|fútbol",
        ("45",),
        "¿Cuánto dura cada parte reglamentaria del partido?",
        (
            "Un tiempo de 45 minutos",
            "Un tiempo de 20 minutos",
            "Un tiempo de 30 minutos",
            "Un tiempo de 60 minutos",
        ),
        "quantity",
    ),
    (
        "futbol|fútbol",
        ("balon", "porteria"),
        "¿Cuál es la meta de un equipo de fútbol?",
        (
            "Meter el balón en la portería rival",
            "Meter el balón en una canasta",
            "Llevar el balón fuera del estadio",
            "Guardar el balón en el vestuario",
        ),
        "purpose",
    ),
    (
        "robot",
        ("sensor", "entorno|cerca|informacion|datos"),
        "¿Para qué utiliza sensores un robot?",
        (
            "Para obtener datos de su entorno",
            "Para ejecutar los movimientos del robot",
            "Para almacenar las instrucciones del programa",
            "Para aportar energía a los motores",
        ),
        "purpose",
    ),
    (
        "robot",
        ("motor", "movimiento|mover"),
        "¿Qué permiten hacer los motores de un robot?",
        (
            "Mover partes de su cuerpo",
            "Procesar los datos obtenidos por sensores",
            "Guardar los pasos que sigue el programa",
            "Proporcionar energía eléctrica a los circuitos",
        ),
        "purpose",
    ),
    (
        "robot",
        ("instrucciones|pasos|programa",),
        "¿Qué guía las tareas que realiza un robot?",
        (
            "Las instrucciones de un programa",
            "La energía almacenada en la batería",
            "La estructura de sus piezas externas",
            "La posición de sus ruedas traseras",
        ),
        "concept",
    ),
    (
        "agujero",
        ("gravedad|fuerza", "luz", "impide|no.*sal"),
        "¿Por qué no sale la luz del interior de un agujero negro?",
        (
            "Porque su gravedad impide que escape",
            "Porque su horizonte refleja toda la luz",
            "Porque su materia absorbe solo la luz visible",
            "Porque gira más rápido que las estrellas",
        ),
        "cause",
    ),
    (
        "agujero",
        ("horizonte de sucesos",),
        "¿Cómo se llama el límite del agujero negro descrito?",
        (
            "El llamado horizonte de sucesos",
            "El llamado cinturón de asteroides",
            "La llamada corteza del planeta",
            "La llamada órbita de Marte",
        ),
        "concept",
    ),
    (
        "agujero",
        ("masa", "distancia"),
        "¿De qué depende el efecto gravitatorio del agujero negro?",
        (
            "De la masa y la distancia",
            "Del tamaño y del brillo de las estrellas",
            "De la temperatura y del color de la materia",
            "Del número de planetas y del sentido de giro",
        ),
        "inference",
    ),
    (
        "egipto",
        ("nilo",),
        "¿Junto a qué río se desarrolló el antiguo Egipto?",
        (
            "Junto al gran río Nilo",
            "Junto al gran río Amazonas",
            "Junto al gran río Tajo",
            "Junto al gran río Danubio",
        ),
        "place",
    ),
    (
        "egipto",
        ("rio|nilo", "cultivo|agricultura"),
        "¿Por qué ayudaban las crecidas del Nilo a los egipcios?",
        (
            "Porque favorecían los cultivos junto al río",
            "Porque ayudaban a transportar piedras para las pirámides",
            "Porque facilitaban la pesca lejos de las orillas",
            "Porque cubrían los caminos durante el invierno",
        ),
        "cause",
    ),
    (
        "egipto",
        ("papiro", "escribir|escritura"),
        "¿Para qué utilizaban el papiro en el antiguo Egipto?",
        (
            "Como un soporte para escribir",
            "Como una tela para confeccionar ropa",
            "Como una cuerda para sujetar barcos",
            "Como un ladrillo para levantar muros",
        ),
        "purpose",
    ),
    (
        "egipto",
        ("jeroglificos",),
        "¿Qué eran los jeroglíficos mencionados en la lectura?",
        (
            "Signos de un sistema de escritura",
            "Piezas de un barco de guerra",
            "Ruedas de un carro de transporte",
            "Partes de un reloj de agua",
        ),
        "vocabulary",
    ),
    (
        "inteligencia artificial",
        ("datos", "entrena|entrenamiento"),
        "¿Qué se utiliza para entrenar algunos modelos de inteligencia artificial?",
        (
            "Un conjunto de datos de aprendizaje",
            "Un conjunto de reglas escritas a mano",
            "Un conjunto de respuestas elegidas por sorteo",
            "Un conjunto de órdenes sin ejemplos de aprendizaje",
        ),
        "concept",
    ),
    (
        "inteligencia artificial",
        ("errores",),
        "¿Por qué conviene revisar las respuestas de la inteligencia artificial?",
        (
            "Porque sus resultados pueden tener errores",
            "Porque sus respuestas pueden tardar en aparecer",
            "Porque sus respuestas ocupan espacio en pantalla",
            "Porque sus respuestas se guardan como archivos",
        ),
        "cause",
    ),
    (
        "inteligencia artificial",
        ("patrones",),
        "¿Qué tarea puede realizar la inteligencia artificial descrita?",
        (
            "Reconocer patrones a partir de datos",
            "Enviar mensajes entre redes de ordenadores",
            "Medir el calor mediante un sensor",
            "Mover piezas con un motor eléctrico",
        ),
        "concept",
    ),
    (
        "faro",
        ("luz", "costa"),
        "¿Qué señala el pequeño faro con su luz?",
        (
            "La posición de la costa",
            "La posición de las estrellas",
            "La posición de las nubes",
            "La posición de los peces",
        ),
        "fact",
    ),
    (
        "faro",
        ("destellos",),
        "¿Para qué sirven las distintas secuencias de destellos de los faros?",
        (
            "Para distinguir un faro de otro",
            "Para indicar siempre la misma distancia a tierra",
            "Para señalar la profundidad exacta de cada puerto",
            "Para mostrar la velocidad exacta de cada barco",
        ),
        "purpose",
    ),
    (
        "faro",
        ("orilla|no navega|no viaja",),
        "¿En qué consiste el viaje del pequeño faro?",
        (
            "En entender su función desde la orilla",
            "En buscar un nuevo puerto donde vivir",
            "En seguir un barco hasta otra isla",
            "En llevar un mensaje a un capitán",
        ),
        "inference",
    ),
    (
        "nasa",
        ("1958",),
        "¿En qué año comenzó a trabajar la NASA?",
        ("En el año 1958", "En el año 1969", "En el año 1945", "En el año 1981"),
        "year",
    ),
    (
        "nasa",
        ("1969", "luna"),
        "¿Cuándo llegó Apolo 11 a la Luna?",
        ("En el año 1969", "En el año 1958", "En el año 1902", "En el año 1981"),
        "year",
    ),
    (
        "nasa",
        ("radio", "datos|informacion"),
        "¿Cómo envían información las sondas y los robots espaciales?",
        (
            "Mediante señales de radio al viajar",
            "Mediante cartas enviadas en barcos",
            "Mediante señales de humo en montañas",
            "Mediante cables por todo el espacio",
        ),
        "concept",
    ),
)


def evidence_for(text, expressions):
    units = sentences(text)
    for size in (1, 2, 3):
        for i in range(len(units) - size + 1):
            span = " ".join(units[i : i + size])
            if all(re.search(expr, norm(span), re.I) for expr in expressions):
                return span
    return None


def reviewed_facts(text, source):
    from app.services.pedagogy import _local_plan
    from app.services.question_bank import reviewed_rows

    # An arbitrary pasted text can mention NASA and somebody else's birth year.
    # Curated annotations are licensed only for their exact reference/excerpt.
    # Other documents use their own structured facts, never a topic-only lookup.
    if _local_plan(source, allow_excerpt=True) is None:
        return
    rows = [
        ([topic], anchors, stem, options, kind) for topic, anchors, stem, options, kind in REVIEWED
    ]
    rows.extend(reviewed_rows())
    for topics, anchors, stem, options, kind in rows:
        if not all(
            re.search(topic, norm(source)) and re.search(topic, norm(text)) for topic in topics
        ):
            continue
        evidence = evidence_for(text, anchors)
        if evidence and evidence_for(source, anchors):
            yield Fact(stem, options[0], tuple(options[1:]), evidence, kind)


def _options_from_values(values, formatter):
    return tuple(formatter(value) for value in values)


def extracted_facts(text):
    """Only whole grammatical constituents qualify; oversized facts are skipped."""
    for sentence in sentences(text):
        unit = sentence.strip(". !?\n")
        # A single leading subject and a finite verb, not an arbitrary regex cut.
        head = re.match(
            r"^(?P<subject>(?:(?:El|La|Los|Las|Un|Una|Su|Sus|Estos|Estas)\s+)?[\wÁÉÍÓÚÑáéíóúñ]+(?:\s+[\wáéíóúñ]+){0,7}?)\s+"
            r"(?P<predicate>(?:es|son|fue|fueron|tiene|tienen|usa|usan|utiliza|utilizan|"
            r"recibe|reciben|produce|producen|permite|permiten|ayuda|ayudan|vive|viven|"
            r"hace|hacen|necesita|necesitan|recorre|recorren|gira|giran|refleja|reflejan|busca|buscan|"
            r"come|comen|lleva|llevan|crea|crean|comienza|comenzo|comenzó|nació|abrió|"
            r"sigue|siguen|da|dan|se)\b.+)$",
            unit,
        )
        subject = head["subject"] if head else None
        if subject and (
            re.search(
                r"\b(?:que|para|porque|cuando|si|aunque|tambien|alli|como|quienes)\b", norm(subject)
            )
            or norm(subject)
            in {
                "otros",
                "otras",
                "estos",
                "estas",
                "ese",
                "esa",
                "le",
                "lo",
                "con ellos",
                "al excavar",
            }
        ):
            head = None
            subject = None
        affirmative = not re.search(
            r"\b(?:no|nunca|sin|excepto|si|aunque|quizá|tal vez)\b", unit, re.I
        )
        if (
            subject
            and affirmative
            and not re.search(r"\b(?:si|aunque|porque|que)\b", subject, re.I)
        ):
            for match in re.finditer(r"\b(1[5-9]\d{2}|20\d{2})\b", unit):
                year = int(match[0])
                # Do not choose another year already present in this sentence.
                wrong = [
                    v
                    for v in (year - 10, year + 10, year - 20, year + 20, year - 30)
                    if str(v) not in unit
                ][:3]
                event = re.search(
                    r"\b(?:comenzó a trabajar|comenzó sus operaciones|se fundó|fue fundada|fue fundado|nació|abrió)\b",
                    unit,
                    re.I,
                )
                named = (
                    subject[0].lower() + subject[1:]
                    if subject.split()[0] in {"El", "La", "Los", "Las"}
                    else subject
                )
                stem = (
                    f"¿En qué año {event[0].lower()} {named}?"
                    if event
                    else f"¿Qué año menciona la lectura al hablar de {subject}?"
                )
                yield Fact(
                    stem,
                    f"En el año {year}",
                    _options_from_values(wrong, lambda v: f"En el año {v}"),
                    sentence,
                    "year",
                )
        for match in re.finditer(
            r"\b(\d+(?:[.,]\d+)?)\s+(kilómetros|metros|centímetros|grados|minutos|días|horas|jugadores|entradas)\b",
            unit,
        ):
            if subject is None or not affirmative:
                continue
            value, unit_name = float(match[1].replace(",", ".")), match[2]
            if not math.isfinite(value) or len(match[1]) > 12:
                continue
            alternatives = (value * 2, value * 3, value * 4) if value else (1, 2, 3)

            def formatter(v, name=unit_name):
                return f"Un total de {v:g} {name}"

            yield Fact(
                f"¿Qué cantidad de {unit_name} se menciona al hablar de {subject}?",
                formatter(value),
                _options_from_values(alternatives, formatter),
                sentence,
                "quantity",
            )
        cause = re.fullmatch(
            r"(?P<main>.+?)\s+(?:porque|debido a que|gracias a que)\s+(?P<reason>.+)", unit, re.I
        )
        if (
            cause
            and 3 <= len(words(cause["main"])) <= 16
            and 2 <= len(words(cause["reason"])) <= 10
            and not re.search(r"\b(?:si|aunque|solo si)\b", cause["main"], re.I)
        ):
            reason = cause["reason"]
            yield Fact(
                f"¿Por qué {cause['main'][0].lower() + cause['main'][1:]}?",
                "Porque " + reason,
                (
                    "Porque recibe menos luz del Sol",
                    "Porque no tiene agua suficiente",
                    "Porque cambia su posición en el lugar",
                ),
                sentence,
                "cause",
            )
        purpose = re.fullmatch(
            r"(?P<main>.+?)\s+para\s+(?P<goal>(?:ver|conocer|observar|estudiar|crear|hacer|obtener|producir|respirar|aprender|enviar|medir|guardar|buscar|llegar|explorar|entender)\b.+)",
            unit,
            re.I,
        )
        if purpose and head and affirmative and 2 <= len(words(purpose["goal"])) <= 10:
            yield Fact(
                f"¿Para qué {purpose['main'][0].lower() + purpose['main'][1:]}?",
                "Para " + purpose["goal"],
                (
                    "Para medir el tiempo que transcurre",
                    "Para cambiar la forma de sus piezas",
                    "Para transportar objetos a otro lugar",
                ),
                sentence,
                "purpose",
            )
        if head and 3 <= len(words(head["predicate"])) <= 12:
            # Actions remain whole and are anchored to this named subject.
            predicate = head["predicate"]
            if re.search(r"\b(?:porque|si|aunque|cuando)\b", predicate, re.I):
                continue
            contrasts = contextual_distractors(predicate, text)
            if contrasts:
                yield Fact(
                    f"¿Qué explica la lectura sobre {subject}?",
                    predicate[0].upper() + predicate[1:],
                    contrasts,
                    sentence,
                    "statement",
                )


def contextual_distractors(predicate, text):
    """Swap a whole same-type constituent; never use random mountains/cities."""
    groups = (
        ("alrededor del Sol", "alrededor de la Tierra", "alrededor de Marte", "alrededor de Venus"),
        ("del Sol", "de la Luna", "de Sirio", "de Vega"),
        ("la Tierra", "la Luna", "Venus", "Marte", "Mercurio"),
        ("el agua", "el aire", "el hielo", "el vapor"),
        ("un planeta", "una estrella", "un cometa", "un satélite", "una galaxia"),
        ("las estrellas", "los planetas", "los cometas", "los asteroides", "los satélites"),
        ("libros", "mapas", "cuadernos", "periódicos", "dibujos"),
        ("raíces", "hojas", "ramas", "flores", "semillas"),
        ("la luz", "el calor", "el sonido", "la energía", "el movimiento"),
        ("las lentes", "los espejos", "las ruedas", "los motores", "los sensores"),
    )
    for family in groups:
        for token in family:
            match = re.search(r"\b" + re.escape(token) + r"\b", predicate, re.I)
            if not match:
                continue
            alternatives = []
            for other in family:
                if norm(other) == norm(token):
                    continue
                value = predicate[: match.start()] + other + predicate[match.end() :]
                value = value[0].upper() + value[1:]
                if norm(value) not in norm(text):
                    alternatives.append(value)
            if len(alternatives) >= 3:
                return tuple(alternatives[:3])
    return None


def vocabulary_facts(text):
    from app.vocabulary import _ENTRIES

    definitions = [meaning.rstrip(".") for _, meaning in _ENTRIES if 3 <= len(words(meaning)) <= 12]
    for variants, meaning in _ENTRIES:
        if not 3 <= len(words(meaning)) <= 12:
            continue
        match = re.search(r"\b(?:" + variants + r")\b", text, re.I)
        if not match:
            continue
        evidence = next(
            (unit for unit in sentences(text) if match[0] in unit and len(words(unit)) <= 80), None
        )
        if evidence is None:
            continue
        answer = meaning.rstrip(".")
        # Definitions are all noun phrases, rather than arbitrary one-word gaps.
        alternatives = tuple(
            value for value in definitions if value != answer and norm(value) not in norm(text)
        )[:3]
        if len(alternatives) == 3:
            yield Fact(
                f"¿Qué significa «{match[0]}» en esta lectura?",
                answer,
                alternatives,
                evidence,
                "vocabulary",
            )


def recognition_facts(text):
    """Totality for tiny/non-propositional valid inputs; never invent a fact."""
    tokens = list(dict.fromkeys(words(text))) or ["texto"]
    stop = set(
        "el la los las un una unos unas su sus de del al y e o a en por para que con es son se no estos estas ese esa este esta".split()
    )
    meaningful = [token for token in tokens if token.casefold() not in stop]
    tokens = meaningful or tokens
    for token in tokens[:3]:
        numerical = bool(re.fullmatch(r"\d+(?:[.,]\d+)*", token))
        if numerical:
            value = (
                int(float(token.replace(",", ".")))
                if len(token) < 16 and token.count(",") + token.count(".") <= 1
                else 0
            )
            yield Fact(
                "¿Qué número aparece escrito en el texto?",
                f"El número es {token}",
                tuple(f"El número es {value + i}" for i in (1, 2, 3)),
                text,
                "quantity",
            )
        else:
            yield Fact(
                f"¿Cómo se escribe la palabra «{token}» que aparece en el texto?",
                f"La palabra es «{token}»",
                tuple(f"La palabra es «{token}{suffix}»" for suffix in ("s", "ar", "ito")),
                text,
                "recognition",
            )


def valid_fact(fact, text):
    choices = [fact.answer, *fact.distractors]
    return (
        len(choices) == len(set(norm(value) for value in choices)) == 4
        and all(
            3 <= len(words(value)) <= 12
            and value[0].isupper()
            and not re.search(r"\.\.\.|…|___", value)
            for value in choices
        )
        and fact.stem.startswith("¿")
        and fact.stem.endswith("?")
        and "..." not in fact.stem
        and "___" not in fact.stem
        and fact.evidence in text
        and (
            fact.kind in {"year", "quantity"}
            or not any(norm(value) in norm(text) for value in fact.distractors)
        )
    )


def build_questions(text, age=None, source=None, count=3):
    source = text if source is None else source
    facts, used_answers, used_stems = [], set(), set()
    reviewed = list(reviewed_facts(text, source))
    pools = [reviewed, extracted_facts(text), vocabulary_facts(text)]
    for pool in pools:
        for fact in pool:
            if (
                valid_fact(fact, text)
                and norm(fact.answer) not in used_answers
                and fact.stem not in used_stems
            ):
                facts.append(fact)
                used_answers.add(norm(fact.answer))
                used_stems.add(fact.stem)
    # A valid string such as "Hola" or "42" has no three distinct propositions.
    # Keep reading available with explicitly literal recognition, never fake a
    # date, a cause or a story. Normal lessons never enter this branch.
    if len(facts) < count:
        for fact in recognition_facts(text):
            if valid_fact(fact, text) and fact.stem not in used_stems:
                facts.append(fact)
                used_stems.add(fact.stem)
            if len(facts) >= count:
                break
    if not facts:
        raise ValueError("reading_has_no_evidence")
    # Reviewed facts win; choose a cause/purpose and a concept when available.
    selected = facts[:1]
    for slot, kinds in enumerate(
        ({"cause", "purpose"}, {"concept", "vocabulary", "inference", "statement"})
    ):
        following = next(
            (f for f in reviewed if f in facts and f not in selected and f.kind in kinds), None
        )
        if following is None:
            if slot == 0:
                following = next((f for f in facts if f not in selected and f.kind in kinds), None)
            else:
                following = next((f for f in reviewed if f in facts and f not in selected), None)
        if following is None:
            following = next((f for f in reviewed if f in facts and f not in selected), None)
        if following:
            selected.append(following)
    selected.extend(f for f in facts if f not in selected)
    result = []
    # Non-propositional one-token input gets two practice prompts to retain the
    # historical minimum array length. Both visibly identify their literal task.
    if len(selected) == 1:
        selected.append(
            Fact(
                "¿Cuál es la escritura que coincide con el texto?",
                selected[0].answer,
                selected[0].distractors,
                selected[0].evidence,
                "recognition",
            )
        )
    for i, fact in enumerate(selected[:count], 1):
        options = [fact.answer, *fact.distractors]
        index = hashlib.sha256((text + fact.stem).encode()).digest()[0] % 4
        options[0], options[index] = options[index], options[0]
        result.append(
            dict(
                id=f"q{i}",
                question=fact.stem,
                options=options,
                correct_option_index=index,
                hint=(
                    "Busca esta pista en la lectura: "
                    if age is not None and age <= 8
                    else "Relee el hecho que apoya tu respuesta: "
                )
                + fact.evidence,
                explanation=f"¡Correcto! {fact.answer}. La lectura explica: «{fact.evidence}».",
            )
        )
    return result
