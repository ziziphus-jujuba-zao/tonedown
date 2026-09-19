"""Jev (TypeSafe System One) backend: many texts per call, one Score plus several Nouls per text."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence
from typing import Any

from typesafe_sdk import AsyncTypeSafeClient, Question, SystemOneResponse, TypeSafeClient
from typesafe_sdk.constants import DEFAULT_MODEL, DEFAULT_MODEL_ENV

from tonedown.backends.base import Backend, chunked
from tonedown.rubric import CONTEXT, questions
from tonedown.schema import Category, RawVerdict


def build_request(texts: Sequence[str]) -> tuple[dict[str, str], dict[str, Question]]:
    """State entries context, c0..cN and the merged question set for one API call."""
    state = {"context": CONTEXT, **{f"c{i}": text for i, text in enumerate(texts)}}
    qs: dict[str, Question] = {}
    for i in range(len(texts)):
        qs.update(questions(f"c{i}"))
    return state, qs


def parse_batch(response: SystemOneResponse, n: int, backend_name: str) -> list[RawVerdict]:
    per_item_tokens = (response.usage.input_tokens or 0) / max(n, 1)
    out: list[RawVerdict] = []
    for i in range(n):
        key = f"c{i}"
        score = response.scores[f"{key}_risk"]
        probs = [float(score.probabilities.get(level, 0.0)) for level in range(5)]
        total = sum(probs) or 1.0
        probs = [p / total for p in probs]
        categories = {cat: float(response.nouls[f"{key}_cat_{cat.value}"].noul) for cat in Category}
        out.append(
            RawVerdict(
                level_probs=probs,
                categories=categories,
                targeted=float(response.nouls[f"{key}_targeted"].noul),
                confidence=float(score.confidence),
                backend=backend_name,
                input_tokens=per_item_tokens,
            )
        )
    return out


class JevBackend(Backend):
    def __init__(
        self,
        *,
        model: str | None = None,
        batch_size: int = 16,
        api_key: str | None = None,
        timeout: float = 30.0,
        transport: Any | None = None,
    ) -> None:
        self.model = model or os.environ.get(DEFAULT_MODEL_ENV) or DEFAULT_MODEL
        self.name = f"jev:{self.model}"
        self.batch_size = batch_size
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport
        self._client: TypeSafeClient | None = None
        self._aclient: AsyncTypeSafeClient | None = None

    def _sync(self) -> TypeSafeClient:
        if self._client is None:
            kwargs: dict[str, Any] = {"model": self.model, "timeout": self._timeout}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._transport is not None:
                kwargs["transport"] = self._transport
            self._client = TypeSafeClient(**kwargs)
        return self._client

    def _async(self) -> AsyncTypeSafeClient:
        if self._aclient is None:
            kwargs: dict[str, Any] = {"model": self.model, "timeout": self._timeout}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            self._aclient = AsyncTypeSafeClient(**kwargs)
        return self._aclient

    def grade(self, texts: Sequence[str]) -> list[RawVerdict]:
        out: list[RawVerdict] = []
        client = self._sync()
        for chunk in chunked(texts, self.batch_size):
            state, qs = build_request(chunk)
            response = client.system_one(state=state, questions=qs)
            out.extend(parse_batch(response, len(chunk), self.name))
        return out

    async def agrade(self, texts: Sequence[str]) -> list[RawVerdict]:
        if self._transport is not None:  # a sync mock transport was supplied; stay on the sync path
            return await asyncio.to_thread(self.grade, list(texts))
        client = self._async()
        chunks = list(chunked(texts, self.batch_size))
        requests = [build_request(chunk) for chunk in chunks]
        responses = await asyncio.gather(*(client.system_one(state=s, questions=q) for s, q in requests))
        out: list[RawVerdict] = []
        for chunk, response in zip(chunks, responses, strict=True):
            out.extend(parse_batch(response, len(chunk), self.name))
        return out

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
