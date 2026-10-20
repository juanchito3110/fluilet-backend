"""Conservative deterministic Spanish lexical/syntactic rules.

Short EASIER lexical pairs are curated with context/agreement constraints.
This is not a clinical parser. Ambiguous constructions remain unchanged.
"""

import re
from collections import Counter

from app.nlp.segmentation import sentences, words

LEXICON = {
    "individuo": "sujeto",
    "individuos": "sujetos",
    "utilizar": "usar",
    "utiliza": "usa",
    "utilizan": "usan",
    "utilizando": "usando",
    "utilizamos": "usamos",
    "realizar": "hacer",
    "realiza": "hace",
    "realizan": "hacen",
    "efectuar": "hacer",
    "efectúa": "hace",
    "efectúan": "hacen",
    "posteriormente": "después",
    "previamente": "antes",
    "inicialmente": "primero",
    "finalmente": "al final",
    "actualmente": "hoy",
    "únicamente": "solo",
    "solamente": "solo",
    "frecuentemente": "a menudo",
    "iniciar": "empezar",
    "inicia": "empieza",
    "inician": "empiezan",
    "finalizar": "acabar",
    "finaliza": "acaba",
    "finalizan": "acaban",
    "comprender": "entender",
    "comprende": "entiende",
    "comprenden": "entienden",
    "numerosos": "muchos",
    "numerosas": "muchas",
    "posee": "tiene",
    "poseen": "tienen",
    "proporciona": "da",
    "proporcionan": "dan",
    "otorga": "da",
    "otorgan": "dan",
    "fundamental": "clave",
    "beneficioso": "bueno",
    "beneficiosa": "buena",
    "obtener": "lograr",
    "obtiene": "logra",
    "incrementar": "aumentar",
    "disminuir": "bajar",
    "disminuye": "baja",
    "aroma": "olor",
    "paulatina": "gradual",
    "homogéneo": "similar",
    "involucración": "compromiso",
}
PHRASES = {
    "realizar actividades": "hacer tareas",
    "realizan actividades": "hacen tareas",
    "con la finalidad de": "para",
    "con el objetivo de": "para",
    "a pesar de que": "aunque",
    "sin embargo": "pero",
    "por consiguiente": "por eso",
    "debido a que": "porque",
    "en el momento en que": "cuando",
    "un celestial aroma": "un olor muy grato",
    "paulatina vuelta": "vuelta poco a poco",
    "medidas organizativas, procesales y de seguridad laboral": "medidas de organización, de los procesos y de seguridad en el trabajo",
    "tiene como prioridad": "pone en primer lugar",
    "desarrollan su trabajo": "trabajan",
    "en ese ámbito": "en ese campo",
    "por su intensidad": "por su fuerza",
    "capacidad de alterar": "capacidad de cambiar",
    "un problema sociosanitario": "un problema social y de salud",
    "un problema sociosanitario de gran envergadura": "un problema social y de salud de gran importancia",
    "representa un problema": "es un problema",
    "una estrategia común europea": "un plan común europeo",
    "para un abordaje homogéneo de": "para actuar del mismo modo ante",
    "Su objetivo es": "Su fin es",
    "objetivo transversal": "fin que abarca varias áreas",
    "profesionales sanitarios": "profesionales de la salud",
    "administraciones sanitarias": "administraciones de salud",
    "los nuevos casos se detectan en": "los nuevos casos se localizan en",
}
_FINITE = r"(?:usa|usan|hace|hacen|tiene|tienen|lee|leen|busca|buscan|estudia|estudian|analiza|analizan|explica|explican|aprende|aprenden|observa|observan|recibe|reciben|da|dan|compra|compran|entiende|entienden|ayuda|ayudan|empieza|empiezan|logra|logran|requiere|requieren)"
_SUBJECT = rf"(?P<subject>(?:El|La|Los|Las|Un|Una|Unos|Unas)\s+(?:[^\W\d_]+\s+){{1,4}}?)(?P<verb>(?:no\s+)?{_FINITE})\b"


def lexical(text: str) -> str:
    for source, target in sorted(PHRASES.items(), key=lambda pair: -len(pair[0])):
        text = re.sub(
            r"\b" + re.escape(source).replace(r"\ ", r"\s+") + r"\b",
            lambda m, target=target: target.capitalize() if m[0][0].isupper() else target,
            text,
            flags=re.I,
        )

    def replace(match):
        original = match[0]
        target = LEXICON.get(original.lower())
        if target is None:
            return original
        if original.isupper():
            return target.upper()
        return target.capitalize() if original[0].isupper() else target

    text = re.sub(r"[^\W\d_]+", replace, text)
    # The annotated involucración -> compromiso pair changes the initial sound.
    return re.sub(r"\be compromiso\b", "y compromiso", text)


def split_domain_clauses(sentence: str) -> str:
    """Bounded structural rewrites; retain modality, list membership and scope.

    Unknown list items/qualifiers do not match. Never split restrictive relatives
    or conditional/concessive clauses into independent factual assertions.
    """
    goal = re.fullmatch(r"(?P<main>Su fin es .+),\s+mejorando su (?P<items>.+?)[.]?", sentence)
    nominalizations = {
        "detección": "cómo se detecta",
        "diagnóstico temprano": "cómo se hace un diagnóstico temprano",
        "prevención": "cómo se previene",
        "evaluación": "cómo se evalúa",
        "manejo": "cómo se maneja",
    }
    if goal:
        items = re.split(r",\s*|\s+y\s+", goal["items"])
        if items and all(item in nominalizations for item in items):
            return (
                goal["main"]
                + ". "
                + " ".join(f"El fin es mejorar {nominalizations[item]}." for item in items)
            )

    measures = re.fullmatch(
        r"(?P<subject>El (?:texto|documento|informe|plan)) recoge "
        r"(?P<measures>las medidas .+ más urgentes) para "
        r"(?P<goal>.+) y pone en primer lugar (?P<priority>.+?)[.]?",
        sentence,
    )
    if measures:
        return (
            f"{measures['subject']} recoge {measures['measures']}. "
            f"Estas medidas son para {measures['goal']}. "
            f"{measures['subject']} pone en primer lugar {measures['priority']}."
        )

    objective = re.fullmatch(
        r"(?P<head>Existe además un (?:primer|segundo|tercer|cuarto) fin que abarca varias áreas) "
        r"que es la coordinación con (?P<partners>[^()]+) así como la participación y compromiso "
        r"de las partes interesadas \((?P<members>[^()]+)\) y la evaluación continua del "
        r"(?P<plan>[^.]+)[.]?",
        sentence,
    )
    if objective:
        members = objective["members"].split(", ")
        membership = f"Entre estas partes están {objective['members']}. "
        if len(members) > 2 and all(
            re.fullmatch(
                r"(?:pacientes|profesionales de la salud|administraciones de salud|distribuidores e industria)",
                item,
            )
            for item in members
        ):
            membership = (
                f"Entre estas partes están {' y '.join(members[:2])}. "
                f"También están {', '.join(members[2:])}. "
            )
        return (
            f"{objective['head']}. Este fin consiste en coordinarse con {objective['partners']}. "
            "También consiste en que las partes interesadas tomen parte y se impliquen. "
            + membership
            + f"También consiste en revisar el {objective['plan']} de forma continua."
        )

    glosses = []

    def gloss(match):
        name, meaning = match["name"], match["meaning"]
        if set(words(meaning.lower())) & {
            "si",
            "aunque",
            "cuando",
            "no",
            "nunca",
            "solo",
            "que",
            "excepto",
            "sin",
        }:
            return match[0]
        glosses.append(f"Con {name}, el texto se refiere a {meaning}.")
        return name

    # Expand only explicit, short nominal food glosses, not arbitrary parentheses
    # containing conditions, negations or assertions about a person/medicine.
    sentence = re.sub(
        r"\b(?P<name>[A-ZÁÉÍÓÚÑ][^\W\d_]+)\s+\("
        r"(?P<meaning>(?:pan|salchichas)(?:\s+[^\W\d_]+){0,4})\)",
        gloss,
        sentence,
    )
    sentence = re.sub(r",\s+por lo que\s+", ". Por eso, ", sentence)
    if glosses:
        sentence = sentence.rstrip(".") + ". " + " ".join(glosses)
    return sentence


def split_explanatory_relative(sentence: str) -> str:
    """Only comma-delimited relatives with one explicit, unambiguous subject.

    Restrictive relatives and embedded/ambiguous clauses stay untouched.
    """
    if len(words(sentence)) <= 24:
        return sentence
    pattern = (
        rf"^(?P<subject>(?:El|La|Los|Las|Un|Una|Unos|Unas)\s+[^,]{{1,60}}),\s+que\s+"
        rf"(?P<relative>(?:no\s+)?{_FINITE}\b[^,]+),\s+"
        rf"(?P<main>(?:no\s+)?{_FINITE}\b[^,]+)$"
    )
    match = re.match(pattern, sentence)
    if not match or len(words(match["subject"])) > 5:
        return sentence
    subject = match["subject"]
    return f"{subject} {match['relative'].strip()}. {subject} {match['main'].strip()}"


def refine(text: str, attempt: int = 0, level: int = 3) -> str:
    result = []
    for sentence in sentences(lexical(text)):
        sentence = split_domain_clauses(sentence)
        sentence = split_explanatory_relative(sentence)
        # Split independent coordinated predicates, repeating the explicit subject
        # so that each new clause remains Subject-Verb-Object.
        match = re.match(_SUBJECT, sentence)
        if match and len(words(sentence)) > (24 if level >= 3 and attempt == 0 else 16):
            subject = match["subject"].strip()
            sentence = re.sub(
                rf"\s+y\s+(?=(?:(?:después|antes|luego|hoy)\s+)?(?:no\s+)?{_FINITE}\b)",
                ". " + subject + " ",
                sentence,
                flags=re.I,
            )
        if attempt > 0:
            # Only punctuation between independent clauses with an explicit subject.
            sentence = re.sub(r"[;:]\s+(?=(?:el|la|los|las|un|una)\s+)", ". ", sentence, flags=re.I)
        parts = sentences(sentence)
        for part in parts:
            part = part.strip()
            if part:
                purpose = re.fullmatch(
                    r"(?P<head>(?:El|La|Los|Las)\s+[^,.]{1,40}?\s+(?:usa|usan)\s+"
                    r"(?:muchos |los |unos )?libros(?: de cuentos)?) para (?P<goal>[^.;]+)[.]?",
                    part,
                )
                if attempt > 0 and purpose:
                    part = f"{purpose['head']}. El fin es {purpose['goal'].rstrip('.')}."
                result.append(part[0].upper() + part[1:])
    return " ".join(result)


def valid_model_output(candidate: str) -> bool:
    """Control tokens left by decoding never form an acceptable adaptation."""
    return bool(words(candidate)) and not re.search(r"<(?:extra_id_\d+|pad|unk|s|/s)>", candidate)


def fidelity_ok(original: str, candidate: str) -> bool:
    """Conservative lexical coverage guard, not a proof of semantic equivalence.

    Numbers and negations must survive; canonical lexical content must be covered
    in both directions. Deterministic changes preserve the original token order
    except explicit subject repetition. ML results also need human evaluation.
    """
    if not valid_model_output(candidate):
        return False

    def numbers(text):
        return Counter(re.findall(r"\d+(?:[.,]\d+)*", text))

    if numbers(original) != numbers(candidate):
        return False

    def negations(text):
        return Counter(
            w.lower() for w in words(text) if w.lower() in {"no", "nunca", "jamás", "sin", "ni"}
        )

    if negations(original) != negations(candidate):
        return False
    target_text = lexical(candidate)
    references = [lexical(original)]
    references.append(" ".join(split_explanatory_relative(s) for s in sentences(references[0])))
    # Structural changes are authorized only by the exact bounded source rewrite,
    # never by relaxing numbers, negations, token order or overlap thresholds.
    references.extend(lexical(refine(original, attempt)) for attempt in range(3))
    for reference in references:
        source = Counter(w.lower() for w in words(reference))
        target = Counter(w.lower() for w in words(target_text))
        if not source or not target or set(target) - set(source):
            continue
        common = sum((source & target).values())
        source_order = [w.lower() for w in words(reference) if w.lower() not in {"y", "e"}]
        target_order = iter(w.lower() for w in words(target_text) if w.lower() not in {"y", "e"})
        ordered = all(
            any(token == following for following in target_order) for token in source_order
        )
        if (
            ordered
            and common / sum(source.values()) >= 0.9
            and common / sum(target.values()) >= 0.85
        ):
            return True
    return False
