"""
Simple TTL cache utilities for tool calls.
"""
from __future__ import annotations
import time
import threading
from typing import Any, Optional, Tuple


class TTLCache:
    def __init__(self, maxsize: int = 256, ttl_seconds: int = 1800):
        self._data: dict[str, Tuple[float, Any]] = {}
        self._lock = threading.RLock()
        self._ttl = ttl_seconds
        self._max = maxsize

    def _evict_if_needed(self) -> None:
        if len(self._data) <= self._max:
            return
        items = sorted(self._data.items(), key=lambda kv: kv[1][0])
        for k, _ in items[: max(1, len(items) - self._max)]:
            self._data.pop(k, None)

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        with self._lock:
            v = self._data.get(key)
            if not v:
                return None
            ts, payload = v
            if now - ts > self._ttl:
                self._data.pop(key, None)
                return None
            return payload

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = (time.time(), value)
            self._evict_if_needed()


def cache_key(*parts: Any) -> str:
    safe_parts = [str(p).strip().lower() for p in parts if p is not None]
    return "|".join(safe_parts)

