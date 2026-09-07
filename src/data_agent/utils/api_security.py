"""In-process API authentication, throttling, and concurrency controls."""

import asyncio
import hashlib
import hmac
import math
from collections import defaultdict, deque
from time import monotonic


def key_digest(value: str) -> bytes:
    """Hash a bearer key before comparison or use as an internal client identifier."""
    return hashlib.sha256(value.encode("utf-8")).digest()


class APIKeyAuthenticator:
    """Validate bearer keys using constant-time digest comparisons."""

    def __init__(self, keys: tuple[str, ...]):
        self._digests = tuple(key_digest(key) for key in keys)

    def authenticate(self, presented_key: str) -> str | None:
        presented_digest = key_digest(presented_key)
        matched = False
        for expected_digest in self._digests:
            matched |= hmac.compare_digest(presented_digest, expected_digest)
        return presented_digest.hex() if matched else None


class SlidingWindowRateLimiter:
    """Bound requests per client within a rolling in-process time window."""

    def __init__(self, limit: int, window_seconds: float, *, clock=monotonic):
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, client_id: str) -> tuple[bool, int]:
        now = self._clock()
        cutoff = now - self.window_seconds
        async with self._lock:
            requests = self._requests[client_id]
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= self.limit:
                retry_after = max(1, math.ceil(requests[0] + self.window_seconds - now))
                return False, retry_after
            requests.append(now)
            return True, 0


class ConcurrencyLimiter:
    """Reject excess work immediately instead of building an unbounded queue."""

    def __init__(self, limit: int):
        self.limit = limit
        self._active = 0
        self._lock = asyncio.Lock()
        self._idle = asyncio.Event()
        self._idle.set()

    async def try_acquire(self) -> bool:
        async with self._lock:
            if self._active >= self.limit:
                return False
            self._active += 1
            self._idle.clear()
            return True

    async def release(self) -> None:
        async with self._lock:
            if self._active > 0:
                self._active -= 1
            if self._active == 0:
                self._idle.set()

    async def wait_for_idle(self, timeout_seconds: float) -> bool:
        try:
            await asyncio.wait_for(self._idle.wait(), timeout=timeout_seconds)
        except TimeoutError:
            return False
        return True
