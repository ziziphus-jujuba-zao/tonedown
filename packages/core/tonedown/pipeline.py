"""The Guard: normalize, detect language, match the lexicon, consult the cache, call the backend, apply the policy."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field

from tonedown.backends.base import Backend
from tonedown.backends.lexicon import Lexicon, LexiconBackend, LexiconEntry
from tonedown.cache import Cache, MemoryCache, cache_key
from tonedown.langdetect import detect
from tonedown.normalize import normalize
from tonedown.policy import Policy, load_policy
from tonedown.schema import Item, RawVerdict, Verdict, text_hash


def default_backend() -> Backend:
    """Jev when a key is available (or TONEDOWN_BACKEND says so), otherwise the offline lexicon."""
    choice = os.environ.get("TONEDOWN_BACKEND", "").strip().lower()
    if choice == "lexicon":
        return LexiconBackend()
    if choice == "qwen3guard":
        from tonedown.backends.qwen3guard import Qwen3GuardBackend

        return Qwen3GuardBackend()
    if choice == "jev" or os.environ.get("TYPESAFE_API_KEY"):
        from tonedown.backends.jev import JevBackend

        return JevBackend()
    return LexiconBackend()


@dataclass
class _Prepared:
    item: Item
    hash: str
    lang: str
    matches: list[LexiconEntry] = field(default_factory=list)
    raw: RawVerdict | None = None
    cached: bool = False


class Guard:
    def __init__(
        self,
        backend: Backend | None = None,
        *,
        policy: str | Policy | dict | None = "balanced",
        cache: Cache | None = None,
        lexicon: Lexicon | None = None,
        detect_language: bool = True,
    ) -> None:
        self.backend = backend or default_backend()
        self.policy = load_policy(policy) if policy is not None else None
        self.cache: Cache = cache if cache is not None else MemoryCache()
        self.lexicon = lexicon or Lexicon.load()
        self.detect_language = detect_language

    # -- public API -------------------------------------------------------------------------------

    def grade(self, inputs: Sequence[str | Item], *, policy: str | Policy | dict | None = None) -> list[Verdict]:
        prepared, texts = self._prepare(inputs)
        raws = self.backend.grade(texts) if texts else []
        return self._assemble(prepared, texts, raws, policy)

    async def agrade(self, inputs: Sequence[str | Item], *, policy: str | Policy | dict | None = None) -> list[Verdict]:
        prepared, texts = self._prepare(inputs)
        raws = await self.backend.agrade(texts) if texts else []
        return self._assemble(prepared, texts, raws, policy)

    # -- steps ------------------------------------------------------------------------------------

    def _prepare(self, inputs: Sequence[str | Item]) -> tuple[list[_Prepared], list[str]]:
        prepared: list[_Prepared] = []
        misses: dict[str, str] = {}
        for i, x in enumerate(inputs):
            item = Item(id=str(i), text=x) if isinstance(x, str) else x
            norm = normalize(item.text)
            h = text_hash(norm)
            lang = item.lang or (detect(item.text)[0] if self.detect_language else "und")
            p = _Prepared(item=item, hash=h, lang=lang, matches=self.lexicon.match(item.text, lang))
            cached = self.cache.get(cache_key(self.backend.name, h))
            if cached is not None:
                p.raw, p.cached = cached, True
            elif h not in misses:
                misses[h] = item.text
            prepared.append(p)
        return prepared, list(misses.values())

    def _assemble(
        self,
        prepared: list[_Prepared],
        texts: list[str],
        raws: list[RawVerdict],
        policy: str | Policy | dict | None,
    ) -> list[Verdict]:
        by_hash = {text_hash(normalize(t)): r for t, r in zip(texts, raws, strict=True)}
        for h, raw in by_hash.items():
            self.cache.set(cache_key(self.backend.name, h), raw)
        active = load_policy(policy) if policy is not None else self.policy
        out: list[Verdict] = []
        for p in prepared:
            raw = p.raw if p.raw is not None else by_hash[p.hash]
            out.append(self._verdict(p, raw, active))
        return out

    def _verdict(self, p: _Prepared, raw: RawVerdict, policy: Policy | None) -> Verdict:
        probs = list(raw.level_probs)
        categories = dict(raw.categories)
        targeted = raw.targeted
        reasons = [f"lexicon:{e.lang}:{e.term}" for e in p.matches]
        if p.matches:
            floor = max(e.level for e in p.matches)
            if raw.level_argmax < floor:
                probs = [0.5 * x for x in probs]
                probs[floor] += 0.5
            for e in p.matches:
                if e.category:
                    categories[e.category] = max(categories.get(e.category, 0.0), 0.9)
                if e.targeted:
                    targeted = max(targeted, 0.8)
        level = sum(i * x for i, x in enumerate(probs))
        argmax = max(range(5), key=lambda i: probs[i])
        verdict = Verdict(
            id=p.item.id,
            text_hash=p.hash,
            lang=p.lang,
            level=round(level, 4),
            level_argmax=argmax,
            level_probs=[round(x, 4) for x in probs],
            categories={k: round(v, 4) for k, v in categories.items()},
            targeted=round(targeted, 4),
            confidence=round(raw.confidence, 4),
            backend=raw.backend,
            cached=p.cached,
            input_tokens=0.0 if p.cached else raw.input_tokens,
            reasons=reasons,
        )
        if policy is not None:
            verdict.action = policy.decide(verdict.level, verdict.confidence, verdict.categories)
        return verdict

    def close(self) -> None:
        self.backend.close()
