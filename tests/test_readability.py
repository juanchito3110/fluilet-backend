import pytest

from app.nlp.readability import Readability, accepted, measure
from app.nlp.segmentation import sentences, words
from app.nlp.syllables import count_syllables


@pytest.mark.parametrize(
    "word,count",
    [
        ("país", 2),
        ("río", 2),
        ("poeta", 3),
        ("leer", 2),
        ("ciudad", 2),
        ("buey", 1),
        ("miau", 1),
        ("Uruguay", 3),
        ("limpiáis", 2),
        ("estudiáis", 3),
        ("vergüenza", 3),
        ("pingüino", 3),
        ("guitarra", 3),
        ("queso", 2),
        ("guerra", 2),
        ("huevo", 2),
        ("ahí", 2),
        ("psicología", 5),
        ("ley", 1),
    ],
)
def test_spanish_syllables(word, count):
    assert count_syllables(word) == count


def test_segmentation_abbreviations_decimals_and_paragraphs():
    text = "La Dra. Ruiz lee 3.5 páginas. ¿Qué sigue? ¡Otra lectura!\n\nUn párrafo sin punto"
    assert len(sentences(text)) == 4
    assert "3.5" in words(text)
    assert len(words("niño, árbol; río.")) == 3


def test_formula_raw_unclamped():
    result = measure("El sol da luz.")
    assert (result.word_count, result.syllable_count, result.sentence_count) == (4, 4, 1)
    assert result.score == pytest.approx(140.535)
    with pytest.raises(ValueError):
        measure("... !")


def score(value):
    return Readability(value, 20, 25, 3)


@pytest.mark.parametrize(
    "original,adapted,expected",
    [
        (50, 65, True),
        (50, 64.999999, False),
        (60, 74.999999, False),
        (60, 75, True),
        (128.535, 85, False),
        (128.5350001, 85, True),
        (129, 84.999999, False),
    ],
)
def test_unrounded_double_condition_and_strict_exception(original, adapted, expected):
    assert accepted(score(original), score(adapted)) is expected
