"""Tiny .env loader so the CLI and eval scripts work without extra dependencies."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    """Read KEY=VALUE lines without overriding variables already set in the shell."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        key = key.strip()
        value = value.split(" #", 1)[0].strip().strip("\"'")
        if sep and value and not key.startswith("#"):
            os.environ.setdefault(key, value)
