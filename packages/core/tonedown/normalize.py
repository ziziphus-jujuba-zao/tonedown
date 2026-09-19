"""Text normalization: the same string is used for hashing, caching and lexicon matching.

The model receives the original text; normalization exists to defeat cheap evasion (zero-width
characters, full-width letters, look-alike alphabets, s p a c e d letters) and to make caching stable.
"""

from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u2028-\u202e\u2060-\u2064\ufeff\u00ad]")
_REPEATS = re.compile(r"(.)\1{3,}", re.DOTALL)
_SPACES = re.compile(r"\s+")

# Look-alike letters people paste into Latin text to dodge word lists (lowercase only; applied after lower()).
_CYRILLIC_LOOKALIKES = str.maketrans("аеорсухкнвтмі", "aeopcyxkhbtmi")
_GREEK_LOOKALIKES = str.maketrans("αβεορτυνκχι", "abeoptyvkxi")


def script_of(ch: str) -> str:
    """Coarse Unicode script name for one character: LATIN, CYRILLIC, HAN, HIRAGANA, HANGUL..."""
    name = unicodedata.name(ch, "")
    if not name:
        return "OTHER"
    first = name.split(" ", 1)[0]
    if first == "CJK":
        return "HAN"
    return first


def script_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ch in text:
        if ch.isalpha():
            s = script_of(ch)
            counts[s] = counts.get(s, 0) + 1
    return counts


def normalize(text: str) -> str:
    """Canonical form used for hashing and Latin-script lexicon matching."""
    t = unicodedata.normalize("NFKC", text)
    t = _ZERO_WIDTH.sub("", t)
    t = t.lower()
    counts = script_counts(t)
    letters = sum(counts.values()) or 1
    # Only translate look-alikes when that alphabet is a minority, so real Russian or Greek stays intact.
    if 0 < counts.get("CYRILLIC", 0) < 0.3 * letters:
        t = t.translate(_CYRILLIC_LOOKALIKES)
    if 0 < counts.get("GREEK", 0) < 0.3 * letters:
        t = t.translate(_GREEK_LOOKALIKES)
    t = _REPEATS.sub(lambda m: m.group(1) * 3, t)
    return _SPACES.sub(" ", t).strip()


def for_matching(text: str) -> str:
    """Letters and digits only, no spaces or punctuation: what CJK substring matching runs on."""
    return "".join(ch for ch in normalize(text) if ch.isalnum())
