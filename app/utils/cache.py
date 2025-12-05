"""Simple TTL cache used for memoizing tool responses."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


@dataclass
class CacheEntry:
    """Represents a cached value and its expiration."""

    value: Any
    expires_at: datetime

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        timestamp = now or datetime.now(timezone.utc)
        return timestamp >= self.expires_at


class TTLCache:
    """Lightweight TTL cache to avoid redundant tool calls."""

    def __init__(self, ttl_seconds: int = 900) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None

        if entry.is_expired():
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)
        self._store[key] = CacheEntry(value=value, expires_at=expires_at)

    def clear(self) -> None:
        self._store.clear()
