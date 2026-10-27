"""Explicit Spanish inflections: no guessed conjugation of unknown/irregular verbs."""

import re

# Both sides are regular -ar verbs, apart from the documented z/c spelling change.
VERBS = {
    "utilizar": "usar",
    "finalizar": "acabar",
    "incrementar": "aumentar",
    "observar": "mirar",
    "retornar": "regresar",
    "colaborar": "ayudar",
    "adicionar": "sumar",
    "aminorar": "bajar",
    "dialogar": "hablar",
    "ejemplificar": "ilustrar",
    "obstaculizar": "frenar",
    "elaborar": "crear",
    "examinar": "mirar",
    "modificar": "cambiar",
    "transformar": "cambiar",
    "investigar": "estudiar",
    "conservar": "guardar",
    "completar": "acabar",
    "emplear": "usar",
    "ocasionar": "causar",
    "enfatizar": "resaltar",
}
ENDINGS = {
    "present": ("o", "as", "a", "amos", "áis", "an"),
    "past": ("é", "aste", "ó", "amos", "asteis", "aron"),
    "imperfect": ("aba", "abas", "aba", "ábamos", "abais", "aban"),
    "future": ("aré", "arás", "ará", "aremos", "aréis", "arán"),
    "conditional": ("aría", "arías", "aría", "aríamos", "aríais", "arían"),
    "participle": ("ado", "ada", "ados", "adas"),
    "gerund": ("ando",),
    "infinitive": ("ar",),
}


def form(lemma, ending):
    stem = lemma[:-2]
    if ending == "é":
        if stem.endswith("z"):
            stem = stem[:-1] + "c"
        elif stem.endswith("c"):
            stem = stem[:-1] + "qu"
        elif stem.endswith("g"):
            stem += "u"
    return stem + ending


def entries():
    for source, target in VERBS.items():
        for tense, endings in ENDINGS.items():
            for person, ending in enumerate(endings):
                yield source, form(source, ending), form(target, ending), tense, person
    for source, target in {"beneficioso": "bueno", "numeroso": "mucho"}.items():
        for ending in ("o", "a", "os", "as"):
            yield source, source[:-1] + ending, target[:-1] + ending, "gender_number", 0
    # Gender is unchanged in these noun pairs; examples are context-limited.
    for source, target in {
        "utilización": "uso",
        "finalización": "fin",
        "incremento": "aumento",
        "funcionamiento": "uso",
        "padecimiento": "dolor",
        "proximidad": "cercanía",
    }.items():
        yield source, source, target, "nominalization", 0


FORMS = {source: target for _, source, target, _, _ in entries()}
FAMILIES = {source: family for family, source, _, _, _ in entries()}


def family(word):
    value = word.casefold().strip()
    return FAMILIES.get(value, value)


def inflect_text(text):
    def replace(match):
        token = match[0]
        # Noun sense changes are not unconditional runtime substitutions.
        target = FORMS.get(token.casefold()) if family(token) in VERBS else None
        if not target:
            return token
        return target.capitalize() if token[0].isupper() else target

    return re.sub(r"[^\W\d_]+", replace, text)
