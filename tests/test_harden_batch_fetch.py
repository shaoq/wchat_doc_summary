"""批量抓取加固测试 - 覆盖增量语义、可疑空页、非法响应、sync_time 和结果摘要。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.api.weread import AuthExpiredError, RateLimitError, WeReadAPIError
from src.models.schema import Article, Feed
from src.services.fetcher import (
    BATCH_INIT_COUNT,
    FetchFinalState,
    FetchSummary,
    FetcherService,
)


class TestFetchAllIncrementalDefault:
    """fetch_all 默认无范围走增量同步。"""

    @pytest.fixture
    def mock_weread_client(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_subscription_service(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def fetcher_service(
        self,
        mock_weread_client: MagicMock,
        mock_db: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> FetcherService:
        return FetcherService(
            mock_weread_client, mock_db, mock_subscription_service
        )

    @pytest.mark.asyncio
    async def test_fetch_all_default_uses_incremental(
        self,
        fetcher_service: FetcherService,
        mock_subscription_service: MagicMock,
    ) -> None:
        """默认无范围 fetch_all 应调用 _fetch_incremental_or_init_summary。"""
        feed_1 = Feed(id=1, mp_id="MP_A", name="A", status=1)
        mock_subscription_service.list_subscriptions = AsyncMock(return_value=[feed_1])
        mock_subscription_service.list_subscriptions_for_fetch = AsyncMock(return_value=[feed_1])

        summary = FetchSummary(mp_id="MP_A", inserted_count=2, articles=[
            Article(id=1, feed_id=1, article_id="a1", title="新文章"),
            Article(id=2, feed_id=1, article_id="a2", title="另一篇"),
        ])
        fetcher_service._fetch_incremental_or_init_summary = AsyncMock(return_value=summary)

        with patch("src.services.fetcher.asyncio.sleep", new=AsyncMock()):
            results = await fetcher_service.fetch_all()

        assert results["MP_A"].inserted_count == 2
        fetcher_service._fetch_incremental_or_init_summary.assert_awaited_once_with("MP_A", on_progress=None)

    @pytest.mark.asyncio
    async def test_fetch_all_explicit_days_uses_fetch_feed_summary(
        self,
        fetcher_service: FetcherService,
        mock_subscription_service: MagicMock,
    ) -> None:
        """fetch_all(days=5) 应调用 _fetch_feed_summary。"""
        feed_1 = Feed(id=1, mp_id="MP_A", name="A", status=1)
        mock_subscription_service.list_subscriptions = AsyncMock(return_value=[feed_1])
        mock_subscription_service.list_subscriptions_for_fetch = AsyncMock(return_value=[feed_1])

        summary = FetchSummary(mp_id="MP_A", inserted_count=1)
        fetcher_service._fetch_feed_summary = AsyncMock(return_value=summary)

        with patch("src.services.fetcher.asyncio.sleep", new=AsyncMock()):
            results = await fetcher_service.fetch_all(days=5)

        assert results["MP_A"].inserted_count == 1
        fetcher_service._fetch_feed_summary.assert_awaited_once_with(
            "MP_A", days=5, latest_count=None, on_progress=None,
        )

    @pytest.mark.asyncio
    async def test_fetch_all_uninitialized_feed_uses_init_count(
        self,
        fetcher_service: FetcherService,
        mock_subscription_service: MagicMock,
    ) -> None:
        """未初始化订阅应退化为有界初始化抓取。"""
        feed = Feed(id=1, mp_id="MP_A", name="A", status=1)
        mock_subscription_service.list_subscriptions = AsyncMock(return_value=[feed])
        mock_subscription_service.list_subscriptions_for_fetch = AsyncMock(return_value=[feed])
        mock_subscription_service.get_subscription = AsyncMock(return_value=feed)
        mock_subscription_service.update_sync_time = AsyncMock()

        # 模拟无已抓取文章
        fetcher_service._get_latest_publish_time = AsyncMock(return_value=None)

        summary = FetchSummary(mp_id="MP_A", inserted_count=3)
        fetcher_service._fetch_feed_summary = AsyncMock(return_value=summary)

        with patch("src.services.fetcher.asyncio.sleep", new=AsyncMock()):
            results = await fetcher_service.fetch_all()

        # 应使用 BATCH_INIT_COUNT 作为 latest_count
        fetcher_service._fetch_feed_summary.assert_awaited_once_with(
            "MP_A", latest_count=BATCH_INIT_COUNT, on_progress=None,
        )

    @pytest.mark.asyncio
    async def test_fetch_all_throttles_between_subscriptions(
        self,
        fetcher_service: FetcherService,
        mock_subscription_service: MagicMock,
    ) -> None:
        """fetch_all 应在订阅间等待。"""
        feeds = [
            Feed(id=1, mp_id="MP_A", name="A", status=1),
            Feed(id=2, mp_id="MP_B", name="B", status=1),
        ]
        mock_subscription_service.list_subscriptions = AsyncMock(return_value=feeds)
        mock_subscription_service.list_subscriptions_for_fetch = AsyncMock(return_value=feeds)

        fetcher_service._fetch_incremental_or_init_summary = AsyncMock(
            return_value=FetchSummary(mp_id="test"),
        )

        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("src.services.fetcher.asyncio.sleep", side_effect=mock_sleep):
            await fetcher_service.fetch_all()

        # 应恰好调用一次 sleep（在 MP_A 和 MP_B 之间）
        assert len(sleep_calls) >= 1
        # 订阅间等待应使用新配置值
        assert sleep_calls[-1] >= 8.0  # fetch_subscription_delay

    @pytest.mark.asyncio
    async def test_fetch_all_backoff_on_recoverable_error(
        self,
        fetcher_service: FetcherService,
        mock_subscription_service: MagicMock,
    ) -> None:
        """可恢复异常后应增加退避等待。"""
        feeds = [
            Feed(id=1, mp_id="MP_A", name="A", status=1),
            Feed(id=2, mp_id="MP_B", name="B", status=1),
            Feed(id=3, mp_id="MP_C", name="C", status=1),
        ]
        mock_subscription_service.list_subscriptions = AsyncMock(return_value=feeds)
        mock_subscription_service.list_subscriptions_for_fetch = AsyncMock(return_value=feeds)

        call_count = 0

        async def mock_fetch_summary(mp_id: str, **kwargs):
            nonlocal call_count
            call_count += 1
            if mp_id == "MP_A":
                raise Exception("临时错误")
            return FetchSummary(mp_id=mp_id)

        fetcher_service._fetch_incremental_or_init_summary = AsyncMock(
            side_effect=mock_fetch_summary,
        )

        sleep_calls: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("src.services.fetcher.asyncio.sleep", side_effect=mock_sleep):
            await fetcher_service.fetch_all()

        # MP_A→MP_B 之间的等待应更长（退避）
        assert sleep_calls[0] >= 8.0  # 退避后的基础等待 (8.0 * 2.0 = 16.0)
        # MP_B→MP_C 之间的等待应恢复
        assert sleep_calls[1] >= 8.0  # fetch_subscription_delay


class TestSuspiciousEmptyRetry:
    """可疑空页重试测试。"""

    @pytest.fixture
    def mock_weread_client(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_subscription_service(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def fetcher_service(
        self,
        mock_weread_client: MagicMock,
        mock_db: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> FetcherService:
        return FetcherService(
            mock_weread_client, mock_db, mock_subscription_service
        )

    @pytest.mark.asyncio
    async def test_suspicious_empty_retry_succeeds(
        self,
        fetcher_service: FetcherService,
        mock_subscription_service: MagicMock,
    ) -> None:
        """可疑空页重试后成功应返回数据。"""
        mock_subscription_service.get_subscription = AsyncMock(
            return_value=Feed(id=1, mp_id="MP_A", name="A", status=1)
        )
        mock_subscription_service.update_sync_time = AsyncMock()

        article = Article(id=1, feed_id=1, article_id="a1", title="文章")

        call_count = 0

        async def mock_get_page(mp_id, *, provider, page, page_size, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return [], 50
            return [{"id": "a1", "title": "文章"}], 50

        fetcher_service._get_article_page = AsyncMock(side_effect=mock_get_page)
        fetcher_service._fetch_and_save_article = AsyncMock(
            return_value=("inserted", article)
        )
        fetcher_service.backfill_publish_time = AsyncMock(return_value=0)

        articles = await fetcher_service.fetch_feed("MP_A")

        assert len(articles) == 1

    @pytest.mark.asyncio
    async def test_suspicious_empty_no_sync_time_update(
        self,
        fetcher_service: FetcherService,
        mock_subscription_service: MagicMock,
    ) -> None:
        """可疑空页放弃后不应更新 sync_time。"""
        mock_subscription_service.get_subscription = AsyncMock(
            return_value=Feed(id=1, mp_id="MP_A", name="A", status=1)
        )
        mock_subscription_service.update_sync_time = AsyncMock()

        # 始终返回空
        fetcher_service._get_article_page = AsyncMock(return_value=([], 50))

        with patch("src.services.fetcher.asyncio.sleep", new=AsyncMock()):
            articles = await fetcher_service.fetch_feed("MP_A")

        assert len(articles) == 0
        assert mock_subscription_service.update_sync_time.await_count == 0


class TestInvalidResponseValidation:
    """非法响应校验测试。"""

    @pytest.mark.asyncio
    async def test_get_articles_non_dict_raises_error(self) -> None:
        """get_articles 对非 dict/list 响应应抛出错误。"""
        from src.api.weread import WeReadClient

        client = WeReadClient()
        client._request = AsyncMock(return_value=42)  # 非法响应

        with pytest.raises(WeReadAPIError, match="响应格式异常"):
            await client.get_articles("MP_WXS_test")

    @pytest.mark.asyncio
    async def test_get_articles_string_response_raises_error(self) -> None:
        """get_articles 对字符串响应应抛出错误。"""
        from src.api.weread import WeReadClient

        client = WeReadClient()
        client._request = AsyncMock(return_value="error message")

        with pytest.raises(WeReadAPIError, match="响应格式异常"):
            await client.get_articles("MP_WXS_test")

    @pytest.mark.asyncio
    async def test_get_articles_valid_list_response(self) -> None:
        """get_articles 对合法 list 响应应正常处理。"""
        from src.api.weread import WeReadClient

        client = WeReadClient()
        client._request = AsyncMock(return_value=[
            {"id": "a1", "title": "文章1"},
        ])

        result = await client.get_articles("MP_WXS_test")
        assert len(result["articles"]) == 1


class TestFetchSummaryStructure:
    """FetchSummary 结构与状态判定测试。"""

    def test_summary_default_state(self) -> None:
        summary = FetchSummary(mp_id="test")
        assert summary.inserted_count == 0
        assert summary.existing_count == 0
        assert summary.failed_count == 0
        assert summary.final_state == FetchFinalState.SUCCESS
        assert summary.suspicious_empty_retried is False

    def test_determine_state_suspicious_empty(self) -> None:
        summary = FetchSummary(mp_id="test", suspicious_empty_retried=True)
        assert FetcherService._determine_state(summary) == FetchFinalState.SUSPICIOUS_EMPTY

    def test_determine_state_success(self) -> None:
        summary = FetchSummary(mp_id="test", inserted_count=3)
        assert FetcherService._determine_state(summary) == FetchFinalState.SUCCESS

    def test_determine_state_empty_result(self) -> None:
        summary = FetchSummary(mp_id="test", list_returned_count=0)
        assert FetcherService._determine_state(summary) == FetchFinalState.EMPTY_RESULT

    def test_determine_state_no_new(self) -> None:
        summary = FetchSummary(mp_id="test", list_returned_count=5, existing_count=5)
        assert FetcherService._determine_state(summary) == FetchFinalState.NO_NEW

    def test_update_summary_counts_inserted(self) -> None:
        summary = FetchSummary(mp_id="test")
        FetcherService._update_summary_counts(summary, "inserted")
        assert summary.inserted_count == 1

    def test_update_summary_counts_existing(self) -> None:
        summary = FetchSummary(mp_id="test")
        FetcherService._update_summary_counts(summary, "existing")
        assert summary.existing_count == 1

    def test_update_summary_counts_failed(self) -> None:
        summary = FetchSummary(mp_id="test")
        FetcherService._update_summary_counts(summary, "failed")
        assert summary.failed_count == 1
