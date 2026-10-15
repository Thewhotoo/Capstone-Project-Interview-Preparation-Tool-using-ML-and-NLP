"""
Live interview state: where interviews in progress are kept between requests.

Each live interview is one small JSON record under a string key. Two backends:

    memory  (default)          a dict in this process -- one server process only;
                               live interviews end if the server restarts
    redis   CAP_LIVE_STORE=redis, CAP_REDIS_URL=redis://host:6379/0
                               shared by every worker and server, and kept across
                               restarts: any worker can continue any interview

Records are plain JSON in both backends, so the memory backend runs exactly
the code path production uses. What a record holds is up to the module that
owns it (app.py: profile sessions; conversation_engine: Round 1;
session_history: links to the database rows and the technical interview).
Every record expires TTL_SECONDS after it was last written, which matches
session_history.STALE_AFTER: an interview idle that long is abandoned anyway.

`lock(key)` serialises requests for the same interview (two quick requests
must not both read version n and both write version n+1). Across processes
only the Redis backend can do that, so it uses a Redis lock.

Answered turns are NOT kept here: they are written to the database as they
happen (session_history). Losing this store loses only the ability to
continue interviews in progress.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

TTL_SECONDS = 2 * 60 * 60
KEY_PREFIX = "cap:"
LOCK_TIMEOUT_SECONDS = 60          # a lock is released after this even if its holder died


class MemoryLiveStore:
    name = "memory"

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, str]] = {}   # key -> (expires at, JSON)
        self._guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    def get(self, key: str) -> Optional[dict]:
        with self._guard:
            item = self._data.get(key)
            if item is None:
                return None
            if item[0] < time.monotonic():
                del self._data[key]
                return None
            return json.loads(item[1])

    def put(self, key: str, value: dict, ttl: int = TTL_SECONDS) -> None:
        encoded = json.dumps(value)
        with self._guard:
            self._data[key] = (time.monotonic() + ttl, encoded)

    def delete(self, key: str) -> None:
        with self._guard:
            self._data.pop(key, None)

    @contextmanager
    def lock(self, key: str) -> Iterator[None]:
        with self._guard:
            lock = self._locks.setdefault(key, threading.RLock())
        with lock:
            yield

    def clear(self) -> None:
        with self._guard:
            self._data.clear()


class RedisLiveStore:
    name = "redis"

    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(url)
        self._client.ping()          # fail at startup, not on the first interview
        self._held = threading.local()

    def get(self, key: str) -> Optional[dict]:
        raw = self._client.get(KEY_PREFIX + key)
        return None if raw is None else json.loads(raw)

    def put(self, key: str, value: dict, ttl: int = TTL_SECONDS) -> None:
        self._client.set(KEY_PREFIX + key, json.dumps(value), ex=ttl)

    def delete(self, key: str) -> None:
        self._client.delete(KEY_PREFIX + key)

    @contextmanager
    def lock(self, key: str) -> Iterator[None]:
        # Re-entrant within one thread (a route may call two functions that
        # both lock the same interview); a Redis lock alone is not.
        held = self._held.__dict__.setdefault("keys", {})
        if held.get(key):
            held[key] += 1
            try:
                yield
            finally:
                held[key] -= 1
            return
        lock = self._client.lock(KEY_PREFIX + "lock:" + key, timeout=LOCK_TIMEOUT_SECONDS,
                                 blocking_timeout=LOCK_TIMEOUT_SECONDS)
        if not lock.acquire():
            raise TimeoutError(f"Could not lock live interview state {key!r}")
        held[key] = 1
        try:
            yield
        finally:
            held.pop(key, None)
            try:
                lock.release()
            except Exception:  # expired while held; the next writer already owns it
                logger.warning("Live-state lock for %s expired before release", key)

    def clear(self) -> None:
        for key in self._client.scan_iter(KEY_PREFIX + "*"):
            self._client.delete(key)


_store: Any = None
_store_guard = threading.Lock()


def get_store():
    """The process-wide store, chosen once from CAP_LIVE_STORE."""
    global _store
    if _store is None:
        with _store_guard:
            if _store is None:
                kind = os.environ.get("CAP_LIVE_STORE", "memory").strip().lower() or "memory"
                if kind == "redis":
                    url = os.environ.get("CAP_REDIS_URL", "redis://localhost:6379/0")
                    _store = RedisLiveStore(url)
                    logger.info("Live interview state: Redis (%s)", url.rsplit("@", 1)[-1])
                elif kind == "memory":
                    _store = MemoryLiveStore()
                else:
                    raise ValueError(f"Unknown CAP_LIVE_STORE {kind!r} (use 'memory' or 'redis')")
    return _store


def is_shared() -> bool:
    """True when live state outlives this process (Redis): then a restart must
    not abandon interviews in progress, because they can still be continued."""
    return get_store().name != "memory"


def set_store(store) -> None:
    """Tests: swap the backend."""
    global _store
    _store = store


class LocalCache:
    """Per-process cache of objects rebuilt from records, keyed by record
    version. The store stays the source of truth: a cached object is reused
    only while the stored record still has the version it was built from, so
    a write by another worker is always picked up."""

    def __init__(self, max_items: int = 512) -> None:
        self._items: dict[str, tuple[int, Any]] = {}
        self._max = max_items
        self._guard = threading.Lock()

    def get(self, key: str, version: int) -> Any:
        with self._guard:
            item = self._items.get(key)
        return item[1] if item is not None and item[0] == version else None

    def put(self, key: str, version: int, value: Any) -> None:
        with self._guard:
            if len(self._items) >= self._max and key not in self._items:
                self._items.pop(next(iter(self._items)))
            self._items[key] = (version, value)

    def drop(self, key: str) -> None:
        with self._guard:
            self._items.pop(key, None)
