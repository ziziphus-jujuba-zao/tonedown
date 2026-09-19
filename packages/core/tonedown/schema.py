"""Shared data types: what every backend produces and every surface consumes."""

from __future__ import annotations

import hashlib
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, Field

RUBRIC_VERSION = "2026.09.19"
"""Bump whenever rubric wording changes; it is part of every cache key."""


class Level(IntEnum):
    SAFE = 0
    MILD = 1
    MODERATE = 2
    SEVERE = 3
    DANGEROUS = 4


class Category(StrEnum):
    SPAM = "spam"
    HARASSMENT = "harassment"
    HATE = "hate"
    SEXUAL = "sexual"
    VIOLENCE = "violence"
    SELF_HARM = "self_harm"
    ILLEGAL = "illegal"


CRITICAL_CATEGORIES: tuple[Category, ...] = (Category.SELF_HARM, Category.VIOLENCE)
"""Categories that take the label whenever present: under-labelling a threat or a cry for help is the costly mistake."""


class Action(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    BLOCK = "block"


_ACTION_RANK = {Action.PASS: 0, Action.REVIEW: 1, Action.BLOCK: 2}


def stronger(a: Action, b: Action) -> Action:
    return a if _ACTION_RANK[a] >= _ACTION_RANK[b] else b


def weaker(a: Action, b: Action) -> Action:
    return a if _ACTION_RANK[a] <= _ACTION_RANK[b] else b


class Item(BaseModel):
    """One text to grade. `lang` is BCP-47-ish (zh, en, ja...); None means detect it."""

    id: str
    text: str
    lang: str | None = None
    context: dict[str, Any] | None = None


class RawVerdict(BaseModel):
    """What a backend knows about one text, before language, lexicon, cache and policy are layered on."""

    level_probs: list[float] = Field(min_length=5, max_length=5)
    categories: dict[Category, float]
    targeted: float
    confidence: float
    backend: str
    input_tokens: float = 0.0
    """This item's share of the batch's billable input tokens, for cost accounting."""

    @property
    def level(self) -> float:
        return sum(i * p for i, p in enumerate(self.level_probs))

    @property
    def level_argmax(self) -> int:
        return max(range(5), key=lambda i: self.level_probs[i])


class Verdict(BaseModel):
    """The engine's output for one item. Probabilities come from the backend, `action` from the policy."""

    id: str
    text_hash: str
    lang: str
    level: float
    level_argmax: int
    level_probs: list[float]
    categories: dict[Category, float]
    targeted: float
    confidence: float
    backend: str
    cached: bool = False
    input_tokens: float = 0.0
    """Billable input tokens this item cost (0 when served from cache)."""
    reasons: list[str] = Field(default_factory=list)
    action: Action | None = None

    @property
    def present(self) -> list[Category]:
        """Categories at or above 0.5, most probable first. A threat is often both harassment and violence."""
        found = [c for c, p in self.categories.items() if p >= 0.5]
        return sorted(found, key=lambda c: -self.categories[c])

    @property
    def top_category(self) -> Category | None:
        """The label to show: self-harm or violence when present, otherwise the most probable category."""
        present = self.present
        critical = [c for c in present if c in CRITICAL_CATEGORIES]
        if critical:
            return critical[0]
        return present[0] if present else None


def text_hash(normalized_text: str) -> str:
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()[:16]
