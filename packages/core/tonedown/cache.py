"""Verdict caches keyed by backend, rubric version and text hash. Danmaku repeat a lot; this is where the money is."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections import OrderedDict
from typing import Protocol

from tonedown.schema import RUBRIC_VERSION, RawVerdict


def cache_key(backend_name: str, text_hash: str) -> str:
    return f"{backend_name}|{RUBRIC_VERSION}|{text_hash}"


class Cache(Protocol):
    def get(self, key: str) -> RawVerdict | None: ...
    def set(self, key: str, value: RawVerdict) -> None: ...


class MemoryCache:
    """Thread-safe LRU cache."""

    def __init__(self, max_size: int = 50_000) -> None:
        self._data: OrderedDict[str, RawVerdict] = OrderedDict()
        self._max = max_size
        self._lock = threading.Lock()

    def get(self, key: str) -> RawVerdict | None:
        with self._lock:
            value = self._data.get(key)
            if value is not None:
                self._data.move_to_end(key)
            return value

    def set(self, key: str, value: RawVerdict) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def __len__(self) -> int:
        return len(self._data)


class SqliteCache:
    """Persistent cache in a single sqlite file; fine for one server process."""

    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS verdicts (key TEXT PRIMARY KEY, value TEXT NOT NULL, created REAL NOT NULL)"
        )
        self._conn.commit()
        self._lock = threading.Lock()

    def get(self, key: str) -> RawVerdict | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM verdicts WHERE key = ?", (key,)).fetchone()
        return RawVerdict.model_validate_json(row[0]) if row else None

    def set(self, key: str, value: RawVerdict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO verdicts (key, value, created) VALUES (?, ?, ?)",
                (key, value.model_dump_json(), time.time()),
            )
            self._conn.commit()

    def __len__(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM verdicts").fetchone()[0]

    def dump(self) -> str:
        return json.dumps({"entries": len(self)})
