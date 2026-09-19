"""Backend contract: turn a batch of texts into RawVerdicts. Everything else is layered on top."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence

from tonedown.schema import RawVerdict


class Backend(ABC):
    name: str = "base"
    """Stable identifier; part of every cache key."""

    @abstractmethod
    def grade(self, texts: Sequence[str]) -> list[RawVerdict]:
        """One RawVerdict per text, in order."""

    async def agrade(self, texts: Sequence[str]) -> list[RawVerdict]:
        return await asyncio.to_thread(self.grade, list(texts))

    def close(self) -> None:
        return None


def chunked(seq: Sequence[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(seq), max(1, size)):
        yield list(seq[i : i + size])
