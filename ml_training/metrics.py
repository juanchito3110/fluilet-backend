"""Single-reference SARI (1..4 grams), tokenization declared as Unicode words.

Implements add-F1, keep-F1, delete precision; empty/empty operations score 1.
See https://github.com/huggingface/evaluate/tree/main/metrics/sari .
"""

from app.nlp.segmentation import words


def sari(source, prediction, reference):
    tokens = [words(value.casefold()) for value in (source, prediction, reference)]
    scores = []
    for n in range(1, 5):
        sets = [set(tuple(row[i : i + n]) for i in range(len(row) - n + 1)) for row in tokens]
        original, output, target = sets

        def precision(proposed, desired):
            return len(proposed & desired) / len(proposed) if proposed else float(not desired)

        def f1(proposed, desired):
            p, r = precision(proposed, desired), precision(desired, proposed)
            return 2 * p * r / (p + r) if p + r else 0.0

        scores.append(
            (
                f1(output - original, target - original)
                + f1(output & original, target & original)
                + precision(original - output, original - target)
            )
            / 3
        )
    return 100 * sum(scores) / 4
