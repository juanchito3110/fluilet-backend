"""Conservative deterministic Spanish lexical/syntactic rules.

This hand-curated vocabulary is EASIER-style, NOT extracted EASIER data or a
clinical SVO parser. Ambiguous relatives are left unchanged, never invented.
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
}
_FINITE = r"(?:usa|usan|hace|hacen|tiene|tienen|lee|leen|busca|buscan|estudia|estudian|analiza|analizan|explica|explican|aprende|aprenden|observa|observan|recibe|reciben|da|dan|compra|compran|entiende|entienden|ayuda|ayudan|empieza|empiezan|logra|logran|requiere|requieren)"
_SUBJECT = rf"(?P<subject>(?:El|La|Los|Las|Un|Una|Unos|Unas)\s+(?:[^\W\d_]+\s+){{1,4}}?)(?P<verb>{_FINITE})\b"


def lexical(text: str) -> str:
    for source, target in sorted(PHRASES.items(), key=lambda pair: -len(pair[0])):
        text = re.sub(
            r"\b" + re.escape(source) + r"\b",
            lambda m, target=target: target.capitalize() if m[0][0].isupper() else target,
            text,
            flags=re.I,
        )

    def replace(match):
        original = match[0]
        target = LEXICON.get(original.lower(), original)
        return target.capitalize() if original[0].isupper() else target

    return re.sub(r"[^\W\d_]+", replace, text)


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
        sentence = split_explanatory_relative(sentence)
        # Split independent coordinated predicates, repeating the explicit subject
        # so that each new clause remains Subject-Verb-Object.
        match = re.match(_SUBJECT, sentence)
        if match and len(words(sentence)) > (24 if level >= 3 else 16):
            subject = match["subject"].strip()
            sentence = re.sub(
                rf"\s+y\s+(?={_FINITE}\b)", ". " + subject + " ", sentence, flags=re.I
            )
        if attempt > 0:
            # Only punctuation between independent clauses with an explicit subject.
            sentence = re.sub(r"[;:]\s+(?=(?:el|la|los|las|un|una)\s+)", ". ", sentence, flags=re.I)
        parts = sentences(sentence)
        for part in parts:
            part = part.strip()
            if part:
                result.append(part[0].upper() + part[1:])
    return " ".join(result)


def fidelity_ok(original: str, candidate: str) -> bool:
    """Conservative lexical coverage guard, not a proof of semantic equivalence.

    Numbers and negations must survive; canonical lexical content must be covered
    in both directions. Deterministic changes preserve the original token order
    except explicit subject repetition. ML results also need human evaluation.
    """
    if not candidate.strip():
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
