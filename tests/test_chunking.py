import pytest

from app.nlp.chunking import ChunkingError, chunk_text
from app.nlp.segmentation import words


def sentence(count):
    return " ".join(["sol"] * count) + "."


def budget(text):
    return len(words(text)) + 1


def test_short_text_and_minimum():
    assert len(chunk_text(sentence(20), budget, 1000)) == 1
    assert len(chunk_text(sentence(499), budget, 1000)) == 1
    with pytest.raises(ChunkingError):
        chunk_text(sentence(19), budget, 1000)


def test_long_document_preserves_words_and_normal_bounds():
    text = "\n\n".join(sentence(100) for _ in range(21))
    chunks = chunk_text(text, budget, 1000)
    assert words(text) == [word for chunk in chunks for word in words(chunk)]
    assert all(500 <= len(words(chunk)) <= 800 for chunk in chunks[:-1])
    assert len(words(chunks[-1])) <= 800


def test_tiny_tail_merges_only_within_token_limit():
    text = sentence(790) + " " + sentence(100)
    assert [len(words(c)) for c in chunk_text(text, budget, 1000)] == [890]
    assert [len(words(c)) for c in chunk_text(text, budget, 801)] == [790, 100]


def test_secondary_segmentation_and_unsplittable_sentences():
    pathological = "; ".join(" ".join(["sol"] * 300) for _ in range(3))
    chunks = chunk_text(pathological, budget, 1000)
    assert [len(words(c)) for c in chunks] == [600, 300]
    with pytest.raises(ChunkingError):
        chunk_text(sentence(801), budget, 1000)
    with pytest.raises(ChunkingError):
        chunk_text(sentence(450) + " " + sentence(450), budget, 1000)


def test_no_silent_token_truncation():
    with pytest.raises(ChunkingError):
        chunk_text(sentence(30), lambda _: 5000, 4096)


def test_original_paragraph_structure_survives_short_chunk():
    text = "El sol da luz. El sol da luz.\n\nEl sol da luz. El sol da luz. El sol da luz."
    assert chunk_text(text, budget, 1000) == [text]
