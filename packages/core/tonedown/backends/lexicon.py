"""Word lists: a zero-cost fast path, an offline fallback, and a source of explanations.

Entries live in `tonedown/lexicon/<lang>.yaml`. They are seeds, not a moderation system: the model
does the real work, the lexicon adds reasons and floors the level for known slurs and slang.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from tonedown.backends.base import Backend
from tonedown.normalize import for_matching, normalize
from tonedown.schema import Category, RawVerdict

_BUILTIN_DIR = Path(__file__).resolve().parent.parent / "lexicon"
_LATIN = re.compile(r"^[a-z0-9 '._-]+$")


@dataclass(frozen=True)
class LexiconEntry:
    term: str
    level: int
    lang: str
    category: Category | None = None
    targeted: bool = False

    @property
    def is_latin(self) -> bool:
        return bool(_LATIN.match(self.term))

    def pattern(self) -> re.Pattern[str]:
        # CJK neighbours count as boundaries, so `楼主nmsl` still matches `nmsl`.
        return re.compile(rf"(?<![a-z0-9]){re.escape(self.term)}(?![a-z0-9])")


class Lexicon:
    def __init__(self, entries: Iterable[LexiconEntry]) -> None:
        self.entries = list(entries)
        self._patterns = {e: e.pattern() for e in self.entries if e.is_latin}

    @classmethod
    def load(cls, paths: Sequence[str | Path] | None = None) -> Lexicon:
        files = [Path(p) for p in paths] if paths else sorted(_BUILTIN_DIR.glob("*.yaml"))
        entries: list[LexiconEntry] = []
        for file in files:
            with file.open(encoding="utf-8") as fh:
                doc = yaml.safe_load(fh) or {}
            lang = doc.get("lang", file.stem)
            for raw in doc.get("entries", []):
                cat = raw.get("category")
                entries.append(
                    LexiconEntry(
                        term=normalize(str(raw["term"])),
                        level=int(raw.get("level", 2)),
                        lang=lang,
                        category=Category(cat) if cat else None,
                        targeted=bool(raw.get("targeted", False)),
                    )
                )
        return cls(entries)

    def match(self, text: str, lang: str | None = None) -> list[LexiconEntry]:
        norm = normalize(text)
        compact = for_matching(text)
        hits: list[LexiconEntry] = []
        for entry in self.entries:
            if lang and lang != "und" and entry.lang not in (lang, "any"):
                continue
            if entry.is_latin:
                pattern = self._patterns[entry]
                if pattern.search(norm) or (len(entry.term) >= 3 and pattern.search(compact)):
                    hits.append(entry)
            elif for_matching(entry.term) in compact:
                hits.append(entry)
        return hits


class LexiconBackend(Backend):
    """Offline grading from word lists alone. Low confidence by design."""

    name = "lexicon"

    def __init__(self, lexicon: Lexicon | None = None) -> None:
        self.lexicon = lexicon or Lexicon.load()

    def grade(self, texts: Sequence[str]) -> list[RawVerdict]:
        out: list[RawVerdict] = []
        for text in texts:
            hits = self.lexicon.match(text)
            categories = {cat: 0.05 for cat in Category}
            if not hits:
                out.append(
                    RawVerdict(
                        level_probs=[0.7, 0.2, 0.07, 0.02, 0.01],
                        categories=categories,
                        targeted=0.05,
                        confidence=0.3,
                        backend=self.name,
                    )
                )
                continue
            level = max(e.level for e in hits)
            probs = [0.03] * 5
            probs[level] = 0.88
            for e in hits:
                if e.category:
                    categories[e.category] = 0.9
            out.append(
                RawVerdict(
                    level_probs=probs,
                    categories=categories,
                    targeted=0.85 if any(e.targeted for e in hits) else 0.1,
                    confidence=0.6,
                    backend=self.name,
                )
            )
        return out
