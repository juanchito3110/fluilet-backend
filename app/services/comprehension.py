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
        "¿De dónde viene la luz que refleja la Luna según la lectura?",
        ("De la luz del Sol", "De la luz de Marte", "De la luz de Venus", "De la luz de Saturno"),
        "origin",
    ),
    (
        "luna",
        ("29,5",),
        "¿Cuánto dura un ciclo de fases de la Luna según la lectura?",
        ("Cerca de 29,5 días", "Cerca de 7 días", "Cerca de 15 días", "Cerca de 60 días"),
        "quantity",
    ),
    (
        "luna",
        ("crater", "golpes|impactos"),
        "¿Qué causó muchos cráteres de la Luna según la lectura?",
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
        "¿Qué relación tiene la Luna con las mareas según la lectura?",
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
        "¿En qué año se fundó el Real Madrid según la lectura?",
        ("En el año 1902", "En el año 1920", "En el año 1947", "En el año 1896"),
        "year",
    ),
    (
        "madrid",
        ("1920", "real"),
        "¿Cuándo recibió el club el título de Real según la lectura?",
        ("En el año 1920", "En el año 1902", "En el año 1947", "En el año 1958"),
        "year",
    ),
    (
        "madrid",
        ("blanc",),
        "¿Qué color caracteriza la camiseta del Real Madrid según la lectura?",
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
        "¿En qué estadio juega de local el Real Madrid según la lectura?",
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
        "¿En qué año abrió el estadio Santiago Bernabéu según la lectura?",
        ("En el año 1947", "En el año 1902", "En el año 1920", "En el año 1969"),
        "year",
    ),
    (
        "madrid",
        ("fifa", "siglo xx"),
        "¿Qué reconocimiento otorgó la FIFA al Real Madrid según la lectura?",
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
        "¿Qué estudia la biología marina según la lectura?",
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
        "¿Para qué aprovechan la luz las algas según la lectura?",
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
        "¿Qué proporcionan los arrecifes de coral a muchos animales según la lectura?",
        (
            "Un refugio donde pueden vivir",
            "Una fuente de calor para mantener su temperatura",
            "Una zona sin corrientes donde siempre encuentran alimento",
            "Un límite entre las aguas dulces y saladas",
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
        "¿Cuántos jugadores tiene cada equipo de fútbol en el campo según la lectura?",
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
        "¿Cuánto dura cada parte reglamentaria del partido según la lectura?",
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
        "¿Cuál es la meta de un equipo de fútbol según la lectura?",
        (
            "Meter el balón en la portería rival",
            "Mantener el balón más tiempo que el rival",
            "Completar más pases que el equipo rival",
            "Recorrer más distancia que el otro equipo",
        ),
        "purpose",
    ),
    (
        "robot",
        ("sensor", "entorno|cerca|informacion|datos"),
        "¿Para qué utiliza sensores un robot según la lectura?",
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
        "¿Qué permiten hacer los motores de un robot según la lectura?",
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
        "¿Qué guía las tareas que realiza un robot según la lectura?",
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
        "¿Por qué no sale la luz del interior de un agujero negro según la lectura?",
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
        "¿Cómo se llama el límite del agujero negro descrito según la lectura?",
        (
            "El llamado horizonte de sucesos",
            "La llamada esfera de fotones",
            "El llamado disco de acreción",
            "La llamada órbita más estable",
        ),
        "concept",
    ),
    (
        "agujero",
        ("masa", "distancia"),
        "¿De qué depende el efecto gravitatorio del agujero negro según la lectura?",
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
        "¿Junto a qué río se desarrolló el antiguo Egipto según la lectura?",
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
        "¿Por qué ayudaban las crecidas del Nilo a los egipcios según la lectura?",
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
        "¿Para qué utilizaban el papiro en el antiguo Egipto según la lectura?",
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
            "Dibujos para decorar sin comunicar mensajes",
            "Señales usadas solo para contar cosechas",
            "Símbolos que indicaban únicamente las rutas",
        ),
        "vocabulary",
    ),
    (
        "inteligencia artificial",
        ("datos", "entrena|entrenamiento"),
        "¿Qué se utiliza para entrenar algunos modelos de inteligencia artificial según la lectura?",
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
        "¿Por qué conviene revisar las respuestas de la inteligencia artificial según la lectura?",
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
        "¿Qué tarea puede realizar la inteligencia artificial descrita según la lectura?",
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
        "¿Qué señala el pequeño faro con su luz según la lectura?",
        (
            "La posición de la costa",
            "La posición de otros barcos",
            "La posición de bancos de arena",
            "La entrada de cada río",
        ),
        "fact",
    ),
    (
        "faro",
        ("destellos",),
        "¿Para qué sirven las distintas secuencias de destellos de los faros según la lectura?",
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
        "¿En qué consiste el viaje del pequeño faro según la lectura?",
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
        "¿En qué año comenzó a trabajar la NASA según la lectura?",
        ("En el año 1958", "En el año 1969", "En el año 1945", "En el año 1981"),
        "year",
    ),
    (
        "nasa",
        ("1969", "luna"),
        "¿Cuándo llegó Apolo 11 a la Luna según la lectura?",
        ("En el año 1969", "En el año 1958", "En el año 1902", "En el año 1981"),
        "year",
    ),
    (
        "nasa",
        ("radio", "datos|informacion"),
        "¿Cómo envían información las sondas y los robots espaciales según la lectura?",
        (
            "Mediante señales de radio al viajar",
            "Mediante pulsos de luz láser",
            "Mediante ondas de sonido a distancia",
            "Mediante señales por un cable continuo",
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
    # An arbitrary pasted text can mention NASA and somebody else's birth year.
    # Curated annotations are licensed only for their exact reference/excerpt.
    # Other documents use their own structured facts, never a topic-only lookup.
    from app.services.clinical_frames import question_rows
    from app.services.pedagogy import _local_plan
    from app.services.question_bank import reviewed_rows

    clinical = question_rows(source)
    if _local_plan(source, allow_excerpt=True) is None and not clinical:
        return
    rows = [
        ([topic], anchors, stem, options, kind) for topic, anchors, stem, options, kind in REVIEWED
    ]
    rows.extend(reviewed_rows())
    if clinical:
        rows = [
            (topics, [norm(a) for a in anchors], stem, options, kind)
            for topics, anchors, stem, options, kind in clinical
        ]
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


def clause_contrasts(clause, text, *, purpose=False):
    """Preserve the grammatical arguments and domain of an unobserved cause.

    These are hypotheses for a reading quiz, never assertions added to the
    lesson. Unsupported verb frames are skipped instead of using random water,
    sunshine or transport answers for every topic.
    """
    choices = {
        "recibe": ("pierde", "almacena", "produce"),
        "reciben": ("pierden", "almacenan", "producen"),
        "tiene": ("pierde", "busca", "produce"),
        "tienen": ("pierden", "buscan", "producen"),
        "quiere": ("evita", "olvida", "necesita"),
        "quieren": ("evitan", "olvidan", "necesitan"),
        "necesita": ("evita", "rechaza", "pierde"),
        "necesitan": ("evitan", "rechazan", "pierden"),
        "medir": ("almacenar", "producir", "transportar"),
        "conocer": ("recorrer", "proteger", "dibujar"),
        "observar": ("dibujar", "contar", "clasificar"),
        "crear": ("guardar", "mover", "revisar"),
        "producir": ("almacenar", "transportar", "consumir"),
        "respirar": ("almacenar", "transportar", "producir"),
        "guardar": ("crear", "mover", "comparar"),
        "transportar": ("almacenar", "producir", "consumir"),
        "conservar": ("distribuir", "borrar", "traducir"),
        "estudiar": ("dibujar", "recorrer", "proteger"),
        "realizar": ("detener", "reducir", "cambiar"),
    }
    for verb, alternatives in choices.items():
        match = re.search(r"\b" + verb + r"\b", clause, re.I)
        if match is None or (purpose and match.start() != 0):
            continue
        values = tuple(
            clause[: match.start()] + other + clause[match.end() :] for other in alternatives
        )
        if all(norm(value) not in norm(text) for value in values):
            return values
    return contextual_distractors(clause, text)


def extracted_facts(text):
    """Only whole grammatical constituents qualify; oversized facts are skipped."""
    # A semicolon joins whole statements at richer levels. Analyze each clause
    # as well as the full sentence; evidence remains an exact delivered span.
    units = [part.strip() for unit in sentences(text) for part in re.split(r";\s+", unit)]
    for sentence in units:
        unit = sentence.strip(". !?\n")
        temporal_unit = unit
        unit = re.sub(r"^En \d{4},?\s+", "", unit)
        # A single leading subject and a finite verb, not an arbitrary regex cut.
        head = re.match(
            r"^(?P<subject>(?:(?:El|La|Los|Las|Un|Una|Su|Sus|Estos|Estas)\s+)?[\wÁÉÍÓÚÑáéíóúñ]+(?:\s+[\wáéíóúñ]+){0,7}?)\s+"
            r"(?P<predicate>(?:no\s+)?(?:es|son|fue|fueron|tiene|tienen|usa|usan|utiliza|utilizan|"
            r"recibe|reciben|produce|producen|permite|permiten|prepara|preparan|transforma|transforman|contiene|contienen|absorbe|absorben|ayuda|ayudan|vive|viven|"
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
                "eso",
                "esto",
                "muchos",
                "muchas",
                "ese día",
                "esta fecha",
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
            for match in re.finditer(r"\b(1[5-9]\d{2}|20\d{2})\b", temporal_unit):
                if re.search(
                    r"\by\s+(?:mi|tu|su|el|la|los|las|un|una)\b.+\b(?:nació|nacio|fue|comenzó|comenzo|fundó|fundo)\b",
                    norm(temporal_unit[: match.start()]),
                ):
                    continue
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
            alternatives = clause_contrasts(reason, text)
            if alternatives:
                yield Fact(
                    f"¿Por qué {cause['main'][0].lower() + cause['main'][1:]}?",
                    "Porque " + reason,
                    tuple(
                        "Porque " + (value[0].lower() + value[1:] if reason[0].islower() else value)
                        for value in alternatives
                    ),
                    sentence,
                    "cause",
                )
        purpose = re.fullmatch(
            r"(?P<main>.+?)\s+para\s+(?P<goal>(?:ver|conocer|observar|estudiar|crear|hacer|obtener|producir|respirar|aprender|enviar|medir|guardar|conservar|realizar|buscar|llegar|explorar|entender)\b.+)",
            unit,
            re.I,
        )
        if purpose and head and affirmative and 2 <= len(words(purpose["goal"])) <= 10:
            alternatives = clause_contrasts(purpose["goal"], text, purpose=True)
            if alternatives:
                yield Fact(
                    f"¿Para qué {purpose['main'][0].lower() + purpose['main'][1:]}?",
                    "Para " + purpose["goal"],
                    tuple("Para " + value[0].lower() + value[1:] for value in alternatives),
                    sentence,
                    "purpose",
                )
        function = re.fullmatch(
            r"(?P<subject>.+?)\s+(?:permite|permiten|sirve para|sirven para)\s+(?P<goal>(?:transportar|observar|conocer|recibir|medir|guardar|producir)\b.+)",
            unit,
            re.I,
        )
        if function and head and affirmative and 2 <= len(words(function["goal"])) <= 10:
            alternatives = clause_contrasts(function["goal"], text, purpose=True)
            if alternatives:
                yield Fact(
                    f"¿Para qué {'sirven' if function['subject'].split()[0].lower() in {'los', 'las', 'sus', 'estos', 'estas'} else 'sirve'} {function['subject'][0].lower() + function['subject'][1:]} según la lectura?",
                    "Para " + function["goal"],
                    tuple("Para " + v[0].lower() + v[1:] for v in alternatives),
                    sentence,
                    "purpose",
                )
        movement = re.fullmatch(
            r".+?\bpermiten? que (?P<result>.+? se )(?P<verb>mueva|muevan)", unit
        )
        if movement and head and affirmative:
            plural = movement["verb"] == "muevan"
            alternatives = (
                ("detengan", "calienten", "iluminen")
                if plural
                else ("detenga", "caliente", "ilumine")
            )
            yield Fact(
                f"¿Qué {'permiten' if plural else 'permite'} {subject[0].lower() + subject[1:]} según la lectura?",
                "Que " + movement["result"] + movement["verb"],
                tuple("Que " + movement["result"] + v for v in alternatives),
                sentence,
                "purpose",
            )
        title = re.fullmatch(
            r"(?P<actor>.+?) recibió el título de (?P<title>[\wáéíóúñ]+) en \d{4} y lo incorporó a su nombre",
            unit,
        )
        if title:
            yield Fact(
                f"¿Por qué cambió el nombre {'del ' + title['actor'][3:].lower() if title['actor'].startswith('El ') else 'de ' + title['actor'].lower()} según la lectura?",
                "Porque recibió el título de " + title["title"],
                (
                    "Porque eligió un lugar distinto para trabajar",
                    "Porque cambió el grupo de personas a cargo",
                    "Porque empezó una actividad completamente diferente",
                ),
                sentence,
                "cause",
            )
        if head and 3 <= len(words(head["predicate"])) <= 12:
            # Actions remain whole and are anchored to this named subject.
            predicate = head["predicate"]
            if re.search(r"\b(?:porque|si|aunque|cuando)\b", predicate, re.I):
                continue
            contrasts = contextual_distractors(predicate, text)
            if contrasts:
                yield Fact(
                    f"¿Qué explica la lectura sobre {subject[0].lower() + subject[1:] if subject.split()[0].casefold() in {'el', 'la', 'los', 'las', 'un', 'una', 'su', 'sus', 'estos', 'estas'} else subject}?",
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
        ("instrucciones", "imágenes", "señales", "sonidos"),
        ("evaporación", "condensación", "precipitación", "infiltración"),
        ("una planta", "una roca", "una tabla de arcilla", "una lámina de metal"),
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


def aligned_source_facts(source, text):
    """Carry grammar-bound source facts across explicit clause rewrites.

    This is not a topic lookup: the fact is extracted from this source, then
    requires its actor and answer in a nearby complete span of this delivery.
    Dates cannot be borrowed from another actor, and negative scopes cannot
    disappear. Private text lives only in request-local variables.
    """
    if source == text:
        return
    from app.services.clear_spanish import _HEAD

    stop = set(
        "el la los las un una unos unas su sus ese esa esos esas este esta estos estas esto eso del para porque como donde según lectura total año años por que con sin son fue tiene puede pueden".split()
    )
    available = {norm(t) for t in words(text)}
    for fact in extracted_facts(source):
        if fact.evidence in text:
            yield fact
            continue
        head = _HEAD.match(fact.evidence)
        if head is None:
            continue
        actors = [
            norm(t)
            for t in words(head["subject"])
            if len(t) >= 4 and norm(t) not in stop and norm(t) in available
        ]
        values = [
            norm(t)
            for t in words(fact.answer)
            if (len(t) >= 4 or t.isdigit()) and norm(t) not in stop and norm(t) in available
        ]
        if not actors or not values:
            continue
        # Every numeric value in the answer is required, not just a word like
        # 'año'. For causes/purposes at least one content argument must survive.
        numbers = re.findall(r"\d+(?:[.,]\d+)*", fact.answer)
        anchors = list(dict.fromkeys([*actors[:2], *(numbers or values[:2])]))
        evidence = evidence_for(text, [r"\b" + re.escape(t) + r"\b" for t in anchors])
        if evidence is None:
            continue

        def negative(value):
            return len(re.findall(r"\b(?:no|nunca|sin)\b", value, re.I))

        if negative(fact.evidence) and negative(evidence) < negative(fact.evidence):
            continue
        yield Fact(fact.stem, fact.answer, fact.distractors, evidence, fact.kind)


def build_questions(text, age=None, source=None, count=3):
    source = text if source is None else source
    facts, used_answers, used_stems = [], set(), set()
    reviewed = list(reviewed_facts(text, source))
    pools = [
        reviewed,
        extracted_facts(text),
        aligned_source_facts(source, text),
        vocabulary_facts(text),
    ]
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
    first = next(
        (
            f
            for f in facts
            if f.kind in {"year", "quantity", "place", "fact", "origin", "attribute"}
        ),
        None,
    )
    selected = [
        first
        or next((f for f in facts if f.kind not in {"cause", "purpose", "recognition"}), facts[0])
    ]
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
                following = next((f for f in facts if f not in selected and f.kind in kinds), None)
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
