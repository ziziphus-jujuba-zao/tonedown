"""Settings from environment variables (and an optional tenants yaml)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def _truthy(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Tenant:
    name: str
    policy: str | None = None
    rate_limit: int | None = None
    anonymous: bool = False


@dataclass
class Settings:
    backend: str = "jev"
    api_keys: dict[str, str] = field(default_factory=dict)
    """api key -> tenant name"""
    open_access: bool = True
    default_policy: str = "balanced"
    cache_path: str | None = None
    rate_limit_per_minute: int = 600
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    feedback_path: str = "feedback.jsonl"
    tenants: dict[str, dict] = field(default_factory=dict)
    max_items: int = 100
    max_text_chars: int = 5000
    host: str = "127.0.0.1"
    port: int = 8080

    @classmethod
    def from_env(cls) -> Settings:
        keys: dict[str, str] = {}
        for pair in os.environ.get("TONEDOWN_API_KEYS", "").split(","):
            if ":" in pair:
                key, tenant = pair.split(":", 1)
                keys[key.strip()] = tenant.strip()
        tenants: dict[str, dict] = {}
        tenants_file = os.environ.get("TONEDOWN_TENANTS_FILE")
        if tenants_file and Path(tenants_file).exists():
            with open(tenants_file, encoding="utf-8") as fh:
                tenants = (yaml.safe_load(fh) or {}).get("tenants", {})
        origins = [o.strip() for o in os.environ.get("TONEDOWN_CORS_ORIGINS", "*").split(",") if o.strip()]
        return cls(
            backend=os.environ.get("TONEDOWN_BACKEND", "jev").strip().lower() or "jev",
            api_keys=keys,
            open_access=_truthy(os.environ.get("TONEDOWN_OPEN_ACCESS"), default=not keys),
            default_policy=os.environ.get("TONEDOWN_DEFAULT_POLICY", "balanced").strip() or "balanced",
            cache_path=os.environ.get("TONEDOWN_CACHE_PATH", "").strip() or None,
            rate_limit_per_minute=int(os.environ.get("TONEDOWN_RATE_LIMIT", "600") or 600),
            cors_origins=origins or ["*"],
            feedback_path=os.environ.get("TONEDOWN_FEEDBACK_PATH", "feedback.jsonl").strip() or "feedback.jsonl",
            tenants=tenants,
            max_items=int(os.environ.get("TONEDOWN_MAX_ITEMS", "100") or 100),
            max_text_chars=int(os.environ.get("TONEDOWN_MAX_TEXT_CHARS", "5000") or 5000),
            host=os.environ.get("TONEDOWN_HOST", "127.0.0.1"),
            port=int(os.environ.get("TONEDOWN_PORT", "8080") or 8080),
        )

    def tenant_for(self, api_key: str) -> Tenant | None:
        name = self.api_keys.get(api_key)
        if name is None:
            return None
        extra = self.tenants.get(name, {})
        return Tenant(name=name, policy=extra.get("policy"), rate_limit=extra.get("rate_limit"))
