"""RateLimiter 单元测试。"""

import asyncio
import time

import pytest

from src.utils.rate_limiter import RateLimiter


@pytest.fixture
def limiter() -> RateLimiter:
    return RateLimiter(max_requests=3, window_seconds=0.5)


class TestRateLimiter:
    async def test_acquire_under_limit_returns_immediately(self, limiter: RateLimiter) -> None:
        start = time.monotonic()
        for _ in range(3):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    async def test_acquire_over_limit_waits(self, limiter: RateLimiter) -> None:
        for _ in range(3):
            await limiter.acquire()
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.3

    async def test_expired_timestamps_cleaned(self) -> None:
        limiter = RateLimiter(max_requests=2, window_seconds=0.2)
        await limiter.acquire()
        await limiter.acquire()
        await asyncio.sleep(0.25)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.05

    async def test_single_request_never_waits(self) -> None:
        limiter = RateLimiter(max_requests=1, window_seconds=10.0)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.05
