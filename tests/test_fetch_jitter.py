"""fetch-jitter 抖动间隔测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.fetcher import FetcherService


class TestJitteredWait:
    """_jittered_wait 方法测试。"""

    @pytest.fixture
    def fetcher_service(self) -> FetcherService:
        return FetcherService(
            MagicMock(), MagicMock(), MagicMock(),
        )

    @pytest.mark.asyncio
    async def test_wait_within_range(self, fetcher_service: FetcherService) -> None:
        """抖动等待应在 [base, base+jitter] 范围内。"""
        base = 5.0
        jitter = 3.0

        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("src.services.fetcher.asyncio.sleep", side_effect=mock_sleep):
            await fetcher_service._jittered_wait(base, jitter, "MP_TEST")

        assert len(sleep_calls) == 1
        assert sleep_calls[0] >= base
        assert sleep_calls[0] <= base + jitter

    @pytest.mark.asyncio
    async def test_wait_zero_jitter_equals_base(self, fetcher_service: FetcherService) -> None:
        """jitter=0 时等待时间应等于 base。"""
        base = 6.0
        jitter = 0.0

        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("src.services.fetcher.asyncio.sleep", side_effect=mock_sleep):
            await fetcher_service._jittered_wait(base, jitter, "MP_TEST")

        assert len(sleep_calls) == 1
        assert sleep_calls[0] == pytest.approx(base)

    @pytest.mark.asyncio
    async def test_wait_with_progress_callback(self, fetcher_service: FetcherService) -> None:
        """抖动等待应通过进度回调发送等待事件。"""
        events = []
        on_progress = lambda e: events.append(e)

        with patch("src.services.fetcher.asyncio.sleep", new=AsyncMock()):
            await fetcher_service._jittered_wait(2.0, 1.0, "MP_TEST", "测试", on_progress)

        assert len(events) == 1
        assert events[0].type == "waiting"
        assert events[0].mp_id == "MP_TEST"

    @pytest.mark.asyncio
    async def test_wait_distribution_has_variance(self, fetcher_service: FetcherService) -> None:
        """多次调用应产生不同的等待时间（随机性验证）。"""
        base = 4.0
        jitter = 5.0

        results: list[float] = []

        for _ in range(20):
            sleep_calls: list[float] = []

            async def mock_sleep(seconds: float) -> None:
                sleep_calls.append(seconds)

            with patch("src.services.fetcher.asyncio.sleep", side_effect=mock_sleep):
                await fetcher_service._jittered_wait(base, jitter, "MP_TEST")

            results.append(sleep_calls[0])

        # 至少应有两种不同的值（几乎不可能 20 次全相同）
        assert len(set(results)) > 1
        # 所有值都应在范围内
        for v in results:
            assert base <= v <= base + jitter


class TestJitterConfig:
    """抖动配置项测试。"""

    def test_default_jitter_values(self) -> None:
        """默认抖动配置应为 3.0。"""
        from config.settings import Settings

        s = Settings()
        assert s.fetch_page_jitter == 3.0
        assert s.fetch_article_jitter == 3.0

    def test_jitter_bounds(self) -> None:
        """jitter 应在 [0, 30] 范围内。"""
        from config.settings import Settings

        s = Settings(fetch_page_jitter=0.0, fetch_article_jitter=0.0)
        assert s.fetch_page_jitter == 0.0

        s = Settings(fetch_page_jitter=30.0, fetch_article_jitter=30.0)
        assert s.fetch_page_jitter == 30.0

    def test_jitter_read_in_init(self) -> None:
        """FetcherService.__init__ 应读取 jitter 配置。"""
        from config.settings import Settings

        s = Settings(fetch_page_jitter=5.0, fetch_article_jitter=7.0)
        with patch("src.services.fetcher.get_settings", return_value=s):
            svc = FetcherService(MagicMock(), MagicMock(), MagicMock())

        assert svc._page_jitter == 5.0
        assert svc._article_jitter == 7.0
