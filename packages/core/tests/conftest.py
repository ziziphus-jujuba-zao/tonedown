from collections.abc import Sequence

import pytest
from tonedown.backends.base import Backend
from tonedown.schema import Category, RawVerdict


class FakeBackend(Backend):
    """Level 2 harassment for anything containing 'idiot', safe otherwise. Counts calls."""

    name = "fake"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def grade(self, texts: Sequence[str]) -> list[RawVerdict]:
        self.calls.append(list(texts))
        out = []
        for t in texts:
            bad = "idiot" in t.lower()
            cats = {c: 0.02 for c in Category}
            if bad:
                cats[Category.HARASSMENT] = 0.95
            out.append(
                RawVerdict(
                    level_probs=[0.0, 0.0, 1.0, 0.0, 0.0] if bad else [0.97, 0.03, 0.0, 0.0, 0.0],
                    categories=cats,
                    targeted=0.9 if bad else 0.02,
                    confidence=0.95,
                    backend="fake",
                    input_tokens=100.0,
                )
            )
        return out


@pytest.fixture
def fake_backend() -> FakeBackend:
    return FakeBackend()
