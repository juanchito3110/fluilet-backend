"""Input validity and advisory quality, separate from reading availability."""

from app.config import settings
from app.nlp.segmentation import WORD_RE, secondary_segments, sentences, words


class InvalidText(ValueError):
    pass


class TextTooLarge(InvalidText):
    pass


def validate_text(text: str) -> None:
    if len(text.encode("utf-8")) > settings.MAX_BODY_BYTES:
        raise TextTooLarge("byte_limit")
    count = 0
    for _ in WORD_RE.finditer(text):
        count += 1
        if count > settings.MAX_DOCUMENT_WORDS:
            raise TextTooLarge("word_limit")
    if not count:
        raise InvalidText("empty_text")


def reading_chunks(text: str) -> list[str]:
    """Linear sentence grouping, without making model limits input rejections.

    A sentence that cannot safely be split remains intact for rules/original
    fallback. Such a chunk is never sent to a model beyond its token budget.
    Short documents and uneven sentence lengths are valid reading material.
    """
    validate_text(text)
    chunks, pending = [], []
    size, cursor = 0, 0
    for sentence in sentences(text):
        units = secondary_segments(sentence) if len(words(sentence)) > 800 else [sentence]
        for unit in units:
            position = text.find(unit, cursor)
            span = text[cursor : position + len(unit)]
            cursor = position + len(unit)
            count = len(words(unit))
            if pending and size + count > 800:
                chunks.append("".join(pending).strip())
                pending, size = [], 0
            pending.append(span)
            size += count
    if pending:
        pending.append(text[cursor:])
        chunks.append("".join(pending).strip())
    if len(chunks) > 1 and len(words(chunks[-1])) < 120:
        chunks[-2:] = [chunks[-2] + " " + chunks[-1]]
    return chunks


def meets_target(metrics: dict) -> bool:
    original = metrics["original_szigriszt_score"]
    adapted = metrics["adapted_szigriszt_score"]
    if original > 128.535:
        return adapted >= 85.0
    return adapted - original >= 15.0 and adapted >= 65.0
