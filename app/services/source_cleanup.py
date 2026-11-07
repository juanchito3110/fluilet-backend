"""Remove editorial noise without deleting scientific qualifiers or measurements."""

import html
import re


def sanitize(text):
    removed = []

    def drop(match):
        removed.append(match[0])
        return ""

    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    # Bounded OCR correction in animal enumerations. A scientific variable v
    # or a Roman numeral V is not a conjunction and must remain untouched.
    animals = r"(?:crustáceos|moluscos|peces|mamíferos|aves|reptiles)"

    def animal_conjunction(match):
        removed.append(match[0])
        return match[1] + " y "

    text = re.sub(rf"\b({animals})\s+v\s+(?={animals}\b)", animal_conjunction, text, flags=re.I)

    def dangling_ocr(match):
        removed.append(match[0])
        return match[1]

    text = re.sub(rf"\b({animals})\s+(v)(?=[.]?\s*$)", dangling_ocr, text)
    text = re.sub(r"\[(?:\d+(?:[,–-]\d+)*|[a-z]|cita requerida|nota \d+)\]", drop, text, flags=re.I)
    text = re.sub(
        r"\((?:[^()]*(?:AFI|IPA|pronunciaci[oó]n|[ˈˌ]|t[ií]tulo original|en ingl[eé]s)[^()]*|"
        r"\s*/[^()]*/\s*|\s*\d{3,4}\s*[–—-]\s*\d{3,4}\s*)\)",
        drop,
        text,
        flags=re.I,
    )

    def biographical_date(match):
        context = text[max(0, match.start() - 100) : match.start()]
        if re.search(
            r"\b(?:autor|autora|escritor|escritora|científico|científica|nacimiento|muerte)\b",
            context,
            re.I,
        ):
            return drop(match)
        return match[0]

    text = re.sub(r"\([^()]*\d{1,2} de \w+ de \d{4}[^()]*\)", biographical_date, text)
    text = re.sub(r"(?m)^\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*$", drop, text)
    # A dangling editorial marker is not a completed teaching statement.
    text = re.sub(r"\s*\[(?:editar|cita requerida)\]", drop, text, flags=re.I)
    return re.sub(r" +([,.;:])", r"\1", " ".join(text.split())), tuple(removed)
