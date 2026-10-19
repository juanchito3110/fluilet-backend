"""Sentence-boundary partitioning with explicit short-text and residual rules."""

from collections.abc import Callable
from itertools import islice

from app.nlp.segmentation import WORD_RE, secondary_segments, sentences, words


class ChunkingError(ValueError):
    pass


def conservative_tokens(text: str) -> int:
    # SentencePiece byte fallback cannot exceed the UTF-8 byte count plus specials.
    # With no tokenizer installed, overestimate instead of silently truncating.
    return len(text.encode("utf-8")) + 32


def chunk_text(
    text: str,
    token_count: Callable[[str], int] = conservative_tokens,
    max_tokens: int = 4096,
    max_words: int = 20000,
) -> list[str]:
    count = sum(1 for _ in islice(WORD_RE.finditer(text), max_words + 1))
    if count < 20 or count > max_words:
        raise ChunkingError("word_limit")
    units = []
    cursor = 0
    for sentence in sentences(text):
        segments = secondary_segments(sentence) if len(words(sentence)) > 800 else [sentence]
        for segment in segments:
            position = text.find(segment, cursor)
            if position < 0:
                raise ChunkingError("source_span_mismatch")
            units.append(text[cursor:position] + segment)
            cursor = position + len(segment)
    if units:
        units[-1] += text[cursor:]
    counts = [len(words(unit)) for unit in units]
    total = sum(counts)
    if total < 20 or total > max_words:
        raise ChunkingError("word_limit")
    if any(count > 800 for count in counts):
        raise ChunkingError("unsplittable_sentence")
    if total <= 800:
        whole = "".join(units).strip()
        if token_count(whole) > max_tokens:
            raise ChunkingError("token_limit")
        return [whole]

    # Find a valid prefix partition rather than greedy cuts that create short
    # intermediate chunks even when a valid sentence partition exists.
    n = len(units)
    previous = {0: None}
    for start in range(n):
        if start not in previous:
            continue
        size = 0
        for end in range(start + 1, n + 1):
            size += counts[end - 1]
            if size > 800:
                break
            if size >= 500 and end not in previous:
                candidate = "".join(units[start:end]).strip()
                if token_count(candidate) <= max_tokens:
                    previous[end] = start
    prefix = [0]
    for count in counts:
        prefix.append(prefix[-1] + count)
    tails = [
        start
        for start in previous
        if start < n
        and total - prefix[start] <= 800
        and token_count("".join(units[start:]).strip()) <= max_tokens
    ]
    if n in previous:
        boundary = n
    elif tails:
        # Prefer a substantial tail when a choice exists.
        boundary = min(tails, key=lambda start: (total - prefix[start] < 120, start))
    else:
        raise ChunkingError("no_sentence_partition")
    spans = [(boundary, n)] if boundary < n else []
    while boundary:
        start = previous[boundary]
        spans.append((start, boundary))
        boundary = start
    spans.sort()
    chunks = ["".join(units[start:end]).strip() for start, end in spans]
    if len(chunks) > 1 and len(words(chunks[-1])) < 120:
        merged = chunks[-2] + "\n\n" + chunks[-1]
        if token_count(merged) <= max_tokens:
            chunks[-2:] = [merged]
    return chunks
