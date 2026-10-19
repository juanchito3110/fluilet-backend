"""Raw, unclamped Szigriszt-Pazos scores. Never round acceptance decisions."""

from dataclasses import dataclass

from app.nlp.segmentation import sentences, words
from app.nlp.syllables import count_syllables


@dataclass(frozen=True)
class Readability:
    score: float
    word_count: int
    syllable_count: int
    sentence_count: int


def measure(text: str) -> Readability:
    tokens = words(text)
    sentence_count = len(sentences(text))
    if not tokens or not sentence_count:
        raise ValueError("empty_text")
    syllables = sum(count_syllables(token) for token in tokens)
    return Readability(
        206.835 - 62.3 * (syllables / len(tokens)) - len(tokens) / sentence_count,
        len(tokens),
        syllables,
        sentence_count,
    )


def accepted(original: Readability, adapted: Readability) -> bool:
    if original.score > 128.535:
        return adapted.score >= 85.0
    return adapted.score - original.score >= 15.0 and adapted.score >= 65.0


def telemetry(original: Readability, adapted: Readability) -> dict:
    return {
        "original_szigriszt_score": original.score,
        "adapted_szigriszt_score": adapted.score,
        "score_delta": adapted.score - original.score,
        "original_word_count": original.word_count,
        "adapted_word_count": adapted.word_count,
        "original_syllable_count": original.syllable_count,
        "original_sentence_count": original.sentence_count,
        "syllable_count": adapted.syllable_count,
        "sentence_count": adapted.sentence_count,
        "maintenance_exception": original.score > 128.535,
    }
