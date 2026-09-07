import asyncio

from data_agent.utils.api_security import (
    APIKeyAuthenticator,
    ConcurrencyLimiter,
    SlidingWindowRateLimiter,
)


def run(awaitable):
    return asyncio.run(awaitable)


def test_authenticator_accepts_configured_key_and_returns_only_digest():
    key = "secret-key-that-is-at-least-32-characters"
    authenticator = APIKeyAuthenticator((key, "another-secret-key-that-is-32-chars"))

    client_id = authenticator.authenticate(key)

    assert client_id is not None
    assert len(client_id) == 64
    assert key not in client_id
    assert authenticator.authenticate("wrong") is None


def test_sliding_window_rate_limiter_recovers_after_window():
    current_time = [100.0]
    limiter = SlidingWindowRateLimiter(2, 10, clock=lambda: current_time[0])

    assert run(limiter.allow("client")) == (True, 0)
    assert run(limiter.allow("client")) == (True, 0)
    assert run(limiter.allow("client")) == (False, 10)
    assert run(limiter.allow("other-client")) == (True, 0)

    current_time[0] = 110.0
    assert run(limiter.allow("client")) == (True, 0)


def test_concurrency_limiter_rejects_and_releases_capacity():
    limiter = ConcurrencyLimiter(1)

    assert run(limiter.try_acquire()) is True
    assert run(limiter.try_acquire()) is False
    run(limiter.release())
    assert run(limiter.try_acquire()) is True
    run(limiter.release())
    run(limiter.release())


def test_concurrency_limiter_reports_idle_and_shutdown_timeout():
    limiter = ConcurrencyLimiter(1)
    assert run(limiter.wait_for_idle(0.01)) is True

    assert run(limiter.try_acquire()) is True
    assert run(limiter.wait_for_idle(0.01)) is False
    run(limiter.release())
    assert run(limiter.wait_for_idle(0.01)) is True
