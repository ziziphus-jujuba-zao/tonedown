"""Dependency-free language detection, good enough to pick a lexicon and a routing rule.

Scripts are decisive (kana means Japanese, Hangul means Korean...). Latin-script text is separated
with small stop-word lists. Short danmaku are often undecidable: callers should fall back to the
page language or a user setting when confidence is low. Swap in `lingua` or fastText later if needed.
"""

from __future__ import annotations

import re

from tonedown.normalize import script_counts

_SCRIPT_LANG = {
    "HIRAGANA": "ja",
    "KATAKANA": "ja",
    "HANGUL": "ko",
    "HAN": "zh",
    "CYRILLIC": "ru",
    "ARABIC": "ar",
    "DEVANAGARI": "hi",
    "THAI": "th",
    "HEBREW": "he",
    "GREEK": "el",
    "BENGALI": "bn",
}

_VIETNAMESE = re.compile("[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]")

_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset("the and you your is are this that to of it for with was not have they what just".split()),
    "es": frozenset("el la los las que de es un una por con para muy este esta y no te tu se lo".split()),
    "fr": frozenset("le la les des est une un que qui pas vous pour sur avec tu je ne ce et".split()),
    "de": frozenset("der die das und ist nicht ein eine ich du sie mit wird auch nur wenn".split()),
    "pt": frozenset("o a os as que de é um uma não com para você muito mas isso".split()),
    "it": frozenset("il la che di è un una non per con sei questo ma anche".split()),
    "id": frozenset("yang dan di ini itu tidak dengan untuk kamu aku dari ada".split()),
}

_WORD = re.compile(r"[a-zà-ÿ]+")


def detect(text: str) -> tuple[str, float]:
    """Return (language code, confidence in 0..1). Unknown scripts give ("und", 0)."""
    counts = script_counts(text)
    letters = sum(counts.values())
    if letters == 0:
        return "und", 0.0
    kana = counts.get("HIRAGANA", 0) + counts.get("KATAKANA", 0)
    if kana:
        return "ja", min(1.0, 0.6 + kana / letters)
    for script, lang in _SCRIPT_LANG.items():
        share = counts.get(script, 0) / letters
        if share >= 0.3:
            return lang, min(1.0, 0.5 + share / 2)
    latin = counts.get("LATIN", 0) / letters
    if latin < 0.5:
        return "und", 0.0
    lowered = text.lower()
    if _VIETNAMESE.search(lowered):
        return "vi", 0.9
    words = _WORD.findall(lowered)
    if not words:
        return "und", 0.0
    best, hits = "en", 0
    for lang, stop in _STOPWORDS.items():
        n = sum(1 for w in words if w in stop)
        if n > hits:
            best, hits = lang, n
    if hits == 0:
        return "en", 0.2
    return best, min(1.0, 0.4 + hits / len(words))
