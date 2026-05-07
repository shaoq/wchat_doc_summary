"""滑动窗口速率限制器。"""

import asyncio
import time


class RateLimiter:
    """基于滑动窗口的异步速率限制器。

    在给定时间窗口内限制最大请求数，超出时自动等待。
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._timestamps: list[float] = []

    async def acquire(self) -> None:
        """获取一个请求许可，必要时等待。

        清理过期时间戳后检查窗口内请求数，超出则等待最早请求退出窗口。
        """
        now = time.monotonic()
        self._timestamps = [ts for ts in self._timestamps if now - ts < self._window_seconds]

        if len(self._timestamps) >= self._max_requests:
            oldest = self._timestamps[0]
            wait = self._window_seconds - (now - oldest)
            if wait > 0:
                await asyncio.sleep(wait)
            # 重新清理
            now = time.monotonic()
            self._timestamps = [ts for ts in self._timestamps if now - ts < self._window_seconds]

        self._timestamps.append(time.monotonic())
