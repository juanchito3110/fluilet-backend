"""Orthographic Spanish syllables, including silent u, hiatus and triphthongs.

Not a pronunciation oracle: proper names, loanwords and dialect variants need
curated exceptions. Numerals use a documented digit-by-digit reading.
"""

import re
import unicodedata

_VOWELS = set("aeiouáéíóúü")
_STRONG = set("aeoáéó")
_ACCENTED_WEAK = set("íú")
_DIGITS = {
    "0": "cero",
    "1": "uno",
    "2": "dos",
    "3": "tres",
    "4": "cuatro",
    "5": "cinco",
    "6": "seis",
    "7": "siete",
    "8": "ocho",
    "9": "nueve",
}
_EXCEPTIONS = {"guion": 1, "truhan": 1, "wifi": 2, "software": 2, "hardware": 2}


def count_syllables(word: str) -> int:
    word = unicodedata.normalize("NFC", word.lower())
    if any(c.isdigit() for c in word):
        return sum(count_syllables(_DIGITS[c]) for c in word if c in _DIGITS) or 1
    if word in _EXCEPTIONS:
        return _EXCEPTIONS[word]
    word = re.sub(r"([qg])u(?=[eéií])", r"\1", word)
    if word.endswith("y"):
        word = word[:-1] + "i"
    # An h between vowels does not break a diphthong/hiatus sequence.
    word = re.sub(r"(?<=[aeiouáéíóúü])h(?=[aeiouáéíóúü])", "", word)
    count = 0
    nucleus = []
    for c in word:
        if c not in _VOWELS:
            nucleus = []
            continue
        if not nucleus:
            count += 1
            nucleus = [c]
            continue
        previous = nucleus[-1]
        strongs = sum(v in _STRONG for v in nucleus)
        hiatus = (
            c in _ACCENTED_WEAK
            or previous in _ACCENTED_WEAK
            or (c in _STRONG and strongs > 0)
            or c == previous
            or len(nucleus) >= 3
        )
        if hiatus:
            count += 1
            nucleus = [c]
        else:
            nucleus.append(c)
    return max(count, 1)
