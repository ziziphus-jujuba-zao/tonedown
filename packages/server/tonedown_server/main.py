"""FastAPI application. Create with `create_app()`; run with `tonedown-server` or uvicorn --factory."""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from tonedown import Guard, Item, Verdict, builtin_policies, load_policy
from tonedown.backends.base import Backend
from tonedown.cache import MemoryCache, SqliteCache
from tonedown.env import load_dotenv
from tonedown.schema import Action

from tonedown_server import __version__
from tonedown_server.auth import make_auth_dependency
from tonedown_server.ratelimit import RateLimiter
from tonedown_server.settings import Settings, Tenant


class ItemIn(BaseModel):
    id: str | None = None
    text: str = Field(min_length=1)
    lang: str | None = None
    context: dict[str, Any] | None = None


class GradeRequest(BaseModel):
    items: list[ItemIn] = Field(min_length=1)
    policy: str | dict[str, Any] | None = None
    """Built-in policy name, or a full policy object for one-off rules."""


class Usage(BaseModel):
    items: int
    cached: int
    backend_input_tokens: float


class GradeResponse(BaseModel):
    results: list[Verdict]
    policy: str
    backend: str
    usage: Usage


class FeedbackIn(BaseModel):
    text_hash: str
    human_action: Action
    id: str | None = None
    lang: str | None = None
    expected_level: int | None = Field(default=None, ge=0, le=4)
    note: str | None = None


def build_backend(settings: Settings) -> Backend:
    if settings.backend == "lexicon":
        from tonedown.backends.lexicon import LexiconBackend

        return LexiconBackend()
    if settings.backend == "qwen3guard":
        from tonedown.backends.qwen3guard import Qwen3GuardBackend

        return Qwen3GuardBackend()
    from tonedown.backends.jev import JevBackend

    return JevBackend()


def create_app(settings: Settings | None = None) -> FastAPI:
    load_dotenv()
    settings = settings or Settings.from_env()
    cache = SqliteCache(settings.cache_path) if settings.cache_path else MemoryCache()
    guard = Guard(build_backend(settings), policy=settings.default_policy, cache=cache)
    limiter = RateLimiter(settings.rate_limit_per_minute)
    auth = make_auth_dependency(settings)

    app = FastAPI(
        title="ToneDown",
        version=__version__,
        description="Grade comments, danmaku and posts from safe (0) to dangerous (4) and map them to pass / review / block.",  # noqa: E501
    )
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
    app.state.settings = settings
    app.state.guard = guard

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "backend": guard.backend.name,
            "policy": settings.default_policy,
            "version": __version__,
        }

    @app.get("/v1/policies")
    async def policies() -> dict[str, Any]:
        return {"policies": [load_policy(name).model_dump(mode="json") for name in builtin_policies()]}

    @app.post("/v1/grade", response_model=GradeResponse)
    async def grade(req: GradeRequest, request: Request, tenant: Tenant = Depends(auth)) -> GradeResponse:
        limiter.check(tenant.name, tenant.rate_limit)
        if len(req.items) > settings.max_items:
            raise HTTPException(status_code=413, detail=f"At most {settings.max_items} items per request")
        for it in req.items:
            if len(it.text) > settings.max_text_chars:
                raise HTTPException(
                    status_code=413, detail=f"Texts are limited to {settings.max_text_chars} characters"
                )
        spec = req.policy or tenant.policy or settings.default_policy
        try:
            policy = load_policy(spec)
        except (FileNotFoundError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        items = [
            Item(id=it.id or str(i), text=it.text, lang=it.lang, context=it.context) for i, it in enumerate(req.items)
        ]
        try:
            verdicts = await guard.agrade(items, policy=policy)
        except Exception as error:  # backend failure: surface it, do not fake a verdict
            raise HTTPException(status_code=502, detail=f"Backend error: {type(error).__name__}: {error}") from error
        return GradeResponse(
            results=verdicts,
            policy=policy.name,
            backend=guard.backend.name,
            usage=Usage(
                items=len(verdicts),
                cached=sum(v.cached for v in verdicts),
                backend_input_tokens=round(sum(v.input_tokens for v in verdicts), 1),
            ),
        )

    @app.post("/v1/feedback", status_code=202)
    async def feedback(fb: FeedbackIn, tenant: Tenant = Depends(auth)) -> dict[str, str]:
        record = {"ts": time.time(), "tenant": tenant.name, **fb.model_dump(mode="json")}
        with open(settings.feedback_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"status": "recorded"}

    return app


def run() -> None:
    import uvicorn

    load_dotenv()
    settings = Settings.from_env()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
