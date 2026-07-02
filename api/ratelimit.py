"""
In-memory per-client-IP sliding-window rate limiting for funnel routes.

Process-local by design: the engine runs as a single Uvicorn process and
these limits exist to stop accidental hammering of the LLM-backed funnel
routes (character drafting, campaign generation), not to be a distributed
quota system. Stdlib only — no middleware framework, no external store.
"""

import os
import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """Allow at most `limit` hits per key inside a rolling window.

    A limit of 0 (or negative) disables the limiter — allow() always
    returns True and records nothing.
    """

    def __init__(self, limit: int, window_seconds: float = 3600.0):
        self.limit = int(limit)
        self.window_seconds = float(window_seconds)
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a hit for `key`; return False when over the limit."""
        if self.limit <= 0:
            return True
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


def limit_from_env(env_var: str, default: int) -> int:
    """Read an integer limit override from the environment.

    Empty/unset/malformed values fall back to the default; 0 disables.
    """
    raw = (os.getenv(env_var) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def client_key(request) -> str:
    """Per-client key for a FastAPI Request — the client IP."""
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client else None
    return host or "unknown"
