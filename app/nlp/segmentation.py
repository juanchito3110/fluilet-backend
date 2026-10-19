"""Deterministic tokenization; paragraphs and punctuation preserve source spans."""

import re
import unicodedata

WORD_RE = re.compile(r"\d+(?:[.,]\d+)*|[^\W\d_]+(?:[’'][^\W\d_]+)*", re.UNICODE)
_END = re.compile(r"""[.!?…]+["»”')\]]*(?=\s|$)|\n[ \t]*\n""")
_ABBREVIATION = re.compile(
    r"\b(?:Sr|Sra|Srta|Dr|Dra|Ud|Uds|Prof|Profa|núm|pág|págs|aprox|ej|EE|UU)\.", re.I
)
_INITIAL = re.compile(r"\b[A-ZÁÉÍÓÚÑ]\.(?=\s+[A-ZÁÉÍÓÚÑ])")


def words(text: str) -> list[str]:
    return WORD_RE.findall(unicodedata.normalize("NFC", text))


def sentences(text: str) -> list[str]:
    protected = {
        m.end() - 1 for pattern in (_ABBREVIATION, _INITIAL) for m in pattern.finditer(text)
    }
    result = []
    start = 0
    for match in _END.finditer(text):
        if match.start() in protected:
            continue
        part = text[start : match.end()].strip()
        if words(part):
            result.append(part)
        start = match.end()
    part = text[start:].strip()
    if words(part):
        result.append(part)
    return result


def secondary_segments(sentence: str) -> list[str]:
    """Only used for pathological input; no arbitrary word-position cuts."""
    parts = re.split(r"(?<=[;:])\s+|\s+(?=(?:y|e|o|u|pero|sino)\s+)", sentence, flags=re.I)
    return [p.strip() for p in parts if words(p)]
