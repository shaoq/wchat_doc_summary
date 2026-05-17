"""抓取回填去重测试 - 验证批量抓取中回填最多执行一次。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.schema import Article, Feed
from src.services.fetcher import FetcherService


def _make_mock_provider(get_articles_side_effect=None, get_articles_return_value=None):
    """创建模拟 ArticleListProvider。"""
    provider = MagicMock()
    provider.supports_narrow_retry = False
    if get_articles_side_effect is not None:
        mock_page = MagicMock()
        articles_list = []
        for raw in get_articles_side_effect:
            arts = []
            for a in raw.get("articles", []):
                art = MagicMock()
                art.to_article_info.return_value = a
                arts.append(art)
            p = MagicMock()
            p.articles = arts
            p.page_size = raw.get("page_size", 50)
            articles_list.append(p)
        provider.get_articles = AsyncMock(side_effect=articles_list)
    elif get_articles_return_value is not None:
        arts = []
        for a in get_articles_return_value.get("articles", []):
            art = MagicMock()
            art.to_article_info.return_value = a
            arts.append(art)
        p = MagicMock()
        p.articles = arts
        p.page_size = get_articles_return_value.get("page_size", 50)
        provider.get_articles = AsyncMock(return_value=p)
    return provider


class TestFetchBackfillDeduplication:
    """抓取回填去重测试。

    验证 fetch_all 中每个订阅的 backfill_publish_time 最多执行一次。
    """

    @pytest.fixture
    def mock_weread_client(self) -> MagicMock:
        """创建模拟微信读书客户端。"""
        client = MagicMock()
        client.get_articles = AsyncMock(
            return_value={"articles": [], "page_size": 50}
        )
        return client

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        """创建模拟数据库实例。"""
        return MagicMock()

    @pytest.fixture
    def mock_subscription_service(self) -> MagicMock:
        """创建模拟订阅服务。"""
        return MagicMock()

    @pytest.fixture
    def fetcher_service(
        self,
        mock_weread_client: MagicMock,
        mock_db: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> FetcherService:
        """创建抓取服务实例。"""
        return FetcherService(
            mock_weread_client, mock_db, mock_subscription_service
        )

    @pytest.mark.asyncio
    async def test_backfill_called_once_per_subscription_in_fetch_all(
        self,
        fetcher_service: FetcherService,
        mock_subscription_service: MagicMock,
        mock_weread_client: MagicMock,
    ) -> None:
        """测试 fetch_all 中每个订阅的回填最多执行一次。

        fetch_feed 内部已经调用了 backfill_publish_time，
        fetch_all 不应再重复调用。
        """
        # 准备两个订阅
        feeds = [
            Feed(id=1, mp_id="MP_1", name="公众号1", status=1),
            Feed(id=2, mp_id="MP_2", name="公众号2", status=1),
        ]
        mock_subscription_service.list_subscriptions = AsyncMock(return_value=feeds)
        mock_subscription_service.list_subscriptions_for_fetch = AsyncMock(return_value=feeds)
        mock_subscription_service.get_subscription = AsyncMock(
            side_effect=lambda mp_id: next(
                (f for f in feeds if f.mp_id == mp_id), None
            )
        )
        mock_subscription_service.update_sync_time = AsyncMock()

        # 模拟返回文章
        article1 = Article(id=1, feed_id=1, article_id="a1", title="文章1")
        article2 = Article(id=2, feed_id=2, article_id="a2", title="文章2")

        mock_provider = _make_mock_provider(get_articles_side_effect=[
            {"articles": [{"id": "a1", "title": "文章1"}], "page_size": 50},
            {"articles": [{"id": "a2", "title": "文章2"}], "page_size": 50},
        ])
        fetcher_service._get_provider = MagicMock(return_value=mock_provider)

        fetcher_service._fetch_and_save_article = AsyncMock(
            side_effect=[("inserted", article1), ("inserted", article2)]
        )

        # 追踪 backfill_publish_time 调用次数
        fetcher_service.backfill_publish_time = AsyncMock(return_value=0)

        with patch.object(fetcher_service, "_ensure_batch", new_callable=AsyncMock), \
             patch.object(fetcher_service, "_get_pending_feeds", new_callable=AsyncMock, return_value=feeds), \
             patch.object(fetcher_service, "_mark_batch_done", new_callable=AsyncMock):
            results = await fetcher_service.fetch_all(days=5)

        # 验证结果
        assert "MP_1" in results
        assert "MP_2" in results

        # 关键断言：backfill_publish_time 总调用次数应等于订阅数（每个恰好一次）
        assert fetcher_service.backfill_publish_time.await_count == 2

        # 验证每个 mp_id 恰好被调用一次
        called_mp_ids = [
            call.args[0]
            for call in fetcher_service.backfill_publish_time.call_args_list
        ]
        assert called_mp_ids.count("MP_1") == 1
        assert called_mp_ids.count("MP_2") == 1

    @pytest.mark.asyncio
    async def test_fetch_feed_calls_backfill_once(
        self,
        fetcher_service: FetcherService,
        mock_subscription_service: MagicMock,
        mock_weread_client: MagicMock,
    ) -> None:
        """测试单个订阅抓取中 backfill 只调用一次。"""
        mock_subscription_service.get_subscription = AsyncMock(
            return_value=Feed(id=1, mp_id="MP_1", name="公众号1", status=1)
        )
        mock_subscription_service.update_sync_time = AsyncMock()

        article1 = Article(id=1, feed_id=1, article_id="a1", title="文章1")
        mock_provider = _make_mock_provider(get_articles_return_value={
            "articles": [{"id": "a1", "title": "文章1"}], "page_size": 50
        })
        fetcher_service._get_provider = MagicMock(return_value=mock_provider)

        fetcher_service._fetch_and_save_article = AsyncMock(
            return_value=("inserted", article1)
        )

        fetcher_service.backfill_publish_time = AsyncMock(return_value=0)

        await fetcher_service.fetch_feed("MP_1", days=5)

        # backfill_publish_time 应只调用一次
        assert fetcher_service.backfill_publish_time.await_count == 1
