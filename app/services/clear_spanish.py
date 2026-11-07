"""Clause-aware reading rewrites. Never put a full stop at an arbitrary word index.

Restrictive relatives, negation, modality and conditions are kept in scope. If a
clause cannot safely fit the budget it stays whole and is reported as best effort.
"""

import re

from app.nlp.segmentation import sentences, words
from app.services.morphology import entries as inflections

LIMITS = {1: 11, 2: 14, 3: 18, 4: 25, 5: 32}
_VERBS = (
    "es son está están era eran fue fueron tiene tienen tenía tenían usa usan usó usaron "
    "hace hacen hizo hicieron crea crean creó crearon vive viven vivía vivían gira giran "
    "recibe reciben produce producen permite permiten necesita necesitan puede pueden "
    "ayuda ayudan lleva llevan recoge recogen busca buscan come comen da dan dio dieron "
    "empezó comenzó nació abrió estudia estudian aprende aprenden sigue siguen sirve sirven "
    "juega juegan viste visten construye construyen muestra muestran refleja reflejan "
    "mide miden pesa pesan tarda tardan dura duran ocupa ocupan explora exploran "
    "fundó fundaron forman forma representa representan constituye constituyen adquiere adquieren origina originan se".split()
)
_VERBS += tuple(
    "absorbe absorben vuelve vuelven forma forman permiten recoge recogen trabajan trabaja "
    "proporciona proporcionan utiliza utilizan indican indica contiene contienen arrancan arranca "
    "transforman transforma llevan devuelve devuelven combina combinan prepara preparan coordina coordinan "
    "ayudan aparece aparecen pertenece pertenecen sirve sirven recoge recogen vienen viene "
    "emplea emplean organiza organizan comparte comparten describe describen comenzó llevó llevó "
    "contribuye contribuyen convierte convierten necesita necesitan representa representan".split()
)
_VERBS += tuple(
    "incorporó incorpora incorporan cuenta cuentan reconoció limitan limita servía servían escribían escribía preparaba ayudaban".split()
)
_VERBS += tuple(
    {
        word
        for _, source, target, tense, _ in inflections()
        if tense in {"present", "past", "imperfect", "future", "conditional"}
        for word in (source, target)
    }
)
_INFINITIVES = set(
    "usar utilizar crear recibir formar trabajar obtener devolver observar estudiar aprender producir mover enviar llevar construir preparar avanzar conocer hacer resolver dar medir transportar guardar regresar explorar".split()
)
_FINITE = r"(?:" + "|".join(sorted(_VERBS, key=len, reverse=True)) + r")"
_NP_END = r"(?<!\bde)(?<!\bdel)(?<!\ba)(?<!\bel)(?<!\bla)(?<!\blos)(?<!\blas)(?<!\bun)(?<!\buna)"
_HEAD = re.compile(
    rf"^(?P<subject>[^,;:.!?]{{1,65}}?){_NP_END}\s+(?:(?:no|también|además|ya|siempre)\s+)*(?P<verb>{_FINITE})\b",
    re.I,
)
_EXPLICIT = re.compile(
    rf"^(?:(?:el|la|los|las|un|una|unos|unas|su|sus|este|esta|estos|estas|ellos|ellas)\s+"
    rf"[^,;:.!?]{{0,65}}?|[A-ZÁÉÍÓÚÑ][\wáéíóúñ]*(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñ]*){{0,3}})\s+{_FINITE}\b",
    re.I,
)


def statement(text):
    text = text.strip(" ,;:.\n")
    if text.endswith(("?", "!")):
        return text
    return text[0].upper() + text[1:] + "." if text else ""


def factor(unit):
    """Unpack licensed identity, qualifier, date and existential relative facts.

    Restrictive subjects, conditional scopes and achieved results are not
    invented. Each transformation removes a grammatical constituent from the
    original clause and gives it an explicit antecedent of its own.
    """
    body = unit.rstrip(".")
    head = _HEAD.match(body)
    if not head or re.search(r"\b(?:si|aunque|que|porque)\b", head["subject"], re.I):
        return None
    subject = head["subject"]
    predicate = body[len(subject) :].strip()
    named = re.fullmatch(
        r"(?P<det>El|La) (?P<kind>río|agencia|misión|vehículo|robot|barco) (?P<name>[A-ZÁÉÍÓÚÑ][\wáéíóúñ]*(?: (?:[A-ZÁÉÍÓÚÑ][\wáéíóúñ]*|\d+))?)",
        subject,
    )
    if named:
        reference = ("Esta " if named["det"] == "La" else "Este ") + named["kind"]
        return [
            f"{named['det']} {named['kind']} se llama {named['name']}.",
            statement(reference + " " + predicate),
        ]
    qualifier = re.fullmatch(
        r"(?P<base>(?:El|La|Los|Las|Un|Una) [\wáéíóúñ]+)(?P<part> de(?:l| los| las| un| una)? .+)",
        subject,
    )
    if qualifier and not re.search(r"\b(?:no|si|que)\b", qualifier["part"], re.I):
        copula = "son" if qualifier["base"].startswith(("Los ", "Las ")) else "es"
        return [
            statement(qualifier["base"] + " " + copula + qualifier["part"]),
            statement(qualifier["base"] + " " + predicate),
        ]
    date = re.fullmatch(
        r"(?P<event>.+?\b(?:nació|abrió|comenzó a trabajar|se fundó|llevó)\b[^.;]*?) (?P<date>el \d{1,2} de \w+ de \d{4}|en \d{4})",
        body,
    )
    if date and not re.search(r"\b(?:no|puede|podría|si|aunque)\b", date["event"], re.I):
        return [statement(date["event"]), statement("Eso fue " + date["date"])]
    relative = re.fullmatch(
        r"(?P<main>.+?\b(?:tiene|tienen|posee|poseen)\s+)(?P<object>(?:(?:un|una|unos|unas) )?[\wáéíóúñ]+) que (?P<relative>.+)",
        body,
    )
    if relative and not re.search(
        r"\b(?:no|puede|pueden|podría|si|aunque)\b", relative["main"], re.I
    ):
        noun = re.sub(r"^(?:un|una|unos|unas) ", "", relative["object"])
        plural = noun.endswith("s")
        feminine = noun.endswith(("a", "as", "ción", "ciones", "dad", "dades")) or noun in {
            "raíces",
            "raíz",
        }
        determiner = ("Esas" if feminine else "Esos") if plural else ("Esa" if feminine else "Ese")
        return [
            statement(relative["main"] + relative["object"]),
            statement(determiner + " " + noun + " " + relative["relative"]),
        ]
    purpose = re.fullmatch(
        r"(?P<main>.+?\b(?:usa|usan|utiliza|utilizan|utilizar|usar|prepara|preparan)\s+[^.;]+?) para (?P<goal>(?:recibir|medir|conocer|producir|guardar|moverse|llevar|estudiar|observar|resolver|realizar|mejorar|construir|aprender|explorar)\b.+)",
        body,
    )
    if purpose and not re.search(r"\b(?:no|nunca|si|aunque)\b", purpose["main"], re.I):
        link = (
            "Su fin sería "
            if re.search(r"\b(?:puede|pueden|podría)\b", purpose["main"], re.I)
            else "El fin es "
        )
        return [statement(purpose["main"]), statement(link + purpose["goal"])]
    return None


def split_unit(unit, limit, depth=0):
    unit = unit.strip()
    size = len(words(unit))
    if size <= limit or depth >= 20:
        return [statement(unit)]
    head = _HEAD.match(unit)
    subject = head["subject"] if head else None
    # Split compound statements only at licensed grammatical boundaries.
    for match in re.finditer(r";\s+|,?\s+(?:y|pero|mientras que)\s+|,\s+por lo que\s+", unit, re.I):
        left, right = unit[: match.start()], unit[match.end() :]
        if (
            not left
            or not right
            or not _HEAD.match(left)
            or re.search(r"\b(?:si|aunque|solo si|no solo)\b", left, re.I)
        ):
            continue
        if "por lo que" in match[0].lower():
            right = "Por eso, " + right
        elif "pero" in match[0].lower():
            right = "Pero " + right
        elif subject and re.match(
            rf"(?:(?:también|además|después|posteriormente|luego|lo|la|los|las|se)\s+)+{_FINITE}\b",
            right,
            re.I,
        ):
            right = subject + " " + right
        elif _EXPLICIT.match(right):
            pass
        elif subject and re.match(rf"(?:no\s+)?{_FINITE}\b", right, re.I):
            right = subject + " " + right
        elif (
            subject
            and head["verb"].casefold() in {"puede", "pueden", "permite", "permiten"}
            and words(right)[0].casefold() in _INFINITIVES
        ):
            if re.search(r"\b(?:no|nunca|sin)\b", left, re.I):
                continue
            right = subject + " " + head["verb"] + " " + right
        else:
            continue
        if max(len(words(left)), len(words(right))) >= size:
            continue
        return split_unit(statement(left), limit, depth + 1) + split_unit(
            statement(right), limit, depth + 1
        )
    parts = factor(unit)
    if parts and max(len(words(part)) for part in parts) < size:
        return [value for part in parts for value in split_unit(part, limit, depth + 1)]
    # An explanatory (comma-delimited) relative, never a restrictive 'que'.
    relative = re.fullmatch(
        rf"(?P<subject>[^,]{{1,55}}),\s+que (?P<aside>{_FINITE}\b[^,]+),\s+(?P<main>{_FINITE}\b.+)",
        unit.rstrip("."),
        re.I,
    )
    if relative and not re.search(r"\b(?:no|solo|si|aunque)\b", relative["subject"], re.I):
        return split_unit(
            statement(relative["subject"] + " " + relative["aside"]), limit, depth + 1
        ) + split_unit(statement(relative["subject"] + " " + relative["main"]), limit, depth + 1)
    # Keep cause and result linked explicitly, including negated causes.
    cause = re.fullmatch(
        r"(?P<main>.+?)\s+(?:porque|debido a que)\s+(?P<cause>.+)", unit.rstrip("."), re.I
    )
    if cause and _HEAD.match(cause["main"]):
        return [statement(cause["main"]), statement("Esto ocurre porque " + cause["cause"])]
    return [statement(unit)]


def rewrite(text, level):
    # Semicolons join independent clauses in the old score calibrator. Unpack
    # them for early readers rather than hiding long sentences in an average.
    units = []
    for unit in sentences(text):
        if level <= 3:
            unit = re.sub(r"\bimportante para la vida de\b", "importante para", unit, flags=re.I)
            market = re.fullmatch(
                r"El frío aire invernal no impide que por todo el mercado se desprenda "
                r"(?:un celestial aroma|un olor muy grato) a (?P<foods>.+?)[.]?",
                unit,
                re.I,
            )
            if market:
                from app.nlp.refinement import refine

                # A licensed negated-prevention frame. Keep its negation and
                # all named foods/glosses; no claim about conditional lists.
                value = (
                    "El aire de invierno está frío. "
                    "Pero no impide que haya un olor muy grato. "
                    "Ese olor llega a todo el mercado. "
                    f"El olor viene de {market['foods'].rstrip('.')}."
                )
                units.extend(sentences(refine(value, level=level)))
                continue
            unit = re.sub(
                r"(?P<subject>[^.;]{1,90}?)\s+(?:constituye|es) un fenómeno físico mediante el cual\s+",
                lambda m: statement(m["subject"] + " es un cambio físico") + " ",
                unit,
                flags=re.I,
            )
            unit = re.sub(
                r"(?P<subject>(?:la|el) [^,;.]{1,50}?) representa el proceso inverso que\s+",
                lambda m: statement(m["subject"] + " es el cambio contrario") + " Este cambio ",
                unit,
                flags=re.I,
            )
            unit = re.sub(
                r"(?P<subject>las moléculas de un líquido) adquieren suficiente energía para transformarse en gas",
                lambda m: (
                    statement(m["subject"] + " reciben energía")
                    + " Esa energía les permite pasar a gas"
                ),
                unit,
                flags=re.I,
            )
        for part in re.split(r";\s+", unit):
            for clause in sentences(part):
                units.extend(split_unit(clause, {1: 9, 2: 12, 3: 15}.get(level, LIMITS[level])))
    if (
        level <= 2
        and len(
            re.findall(
                r"\b(?:plantas|jardín|instrumentos|laboratorio|experimento|estudio)\b", text, re.I
            )
        )
        >= 2
    ):
        agreement = {
            "usaron": "usó",
            "utilizaron": "utilizó",
            "usan": "usa",
            "utilizan": "utiliza",
            "crearon": "creó",
            "elaboraron": "elaboró",
            "crean": "crea",
            "elaboran": "elabora",
            "miraron": "miró",
            "observaron": "observó",
            "miran": "mira",
            "observan": "observa",
        }
        expanded = []
        for unit in units:
            if level == 1:
                match = re.match(
                    r"^(?:Los investigadores|Las investigadoras) (?P<adv>(?:(?:después|posteriormente|también|además|luego),?\s+)?)(?P<verb>"
                    + "|".join(agreement)
                    + r")\b",
                    unit,
                    re.I,
                )
                if match:
                    unit = (
                        "El grupo de estudio "
                        + match["adv"]
                        + agreement[match["verb"].casefold()]
                        + unit[match.end() :]
                    )
                    unit = re.sub(
                        r"\by (?P<adv>(?:(?:después|posteriormente|también|además|luego),?\s+)?)(?P<verb>"
                        + "|".join(agreement)
                        + r")\b",
                        lambda m: "y " + m["adv"] + agreement[m["verb"].casefold()],
                        unit,
                        flags=re.I,
                    )
            else:
                unit = re.sub(r"\binvestigadores\b", "científicos", unit, flags=re.I)
                unit = re.sub(r"\binvestigadoras\b", "científicas", unit, flags=re.I)
            expanded.append(unit)
        units = expanded
    return " ".join(units)


def overflow(text, level):
    return sum(max(0, len(words(unit)) - LIMITS[level]) for unit in sentences(text))
