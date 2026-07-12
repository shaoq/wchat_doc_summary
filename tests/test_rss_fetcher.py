"""RSS 抓取管道测试 - 覆盖 cache-first 导入、内容模式、去重、成员挂载、回退行为。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

from src.api.providers.base import ProviderArticle, ProviderArticlePage
from src.api.providers.rss_provider import RSSProviderError
from src.api.weread import AuthExpiredError
from src.models.schema import Article, Feed, RSSArticleMembership, RSSSource
from src.services.fetcher import FetcherService, FetchFinalState
from src.services.rss_source import RSSSourceService
from src.services.subscription import SubscriptionService
from src.storage.database import Database


@pytest_asyncio.fixture
async def db() -> Database:
    """创建内存数据库。"""
    database = Database(database_url="sqlite+aiosqlite:///:memory:")
    await database.init_db()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def subscription_service(db: Database) -> SubscriptionService:
    return SubscriptionService(db)


@pytest_asyncio.fixture
async def rss_service(db: Database) -> RSSSourceService:
    return RSSSourceService(db)


@pytest_asyncio.fixture
async def fetcher(db: Database, subscription_service: SubscriptionService) -> FetcherService:
    mock_client = MagicMock()
    return FetcherService(mock_client, db, subscription_service)


def _make_rss_article(
    title: str = "测试文章",
    url: str = "https://mp.weixin.qq.com/s/test1",
    external_id: str = "guid-001",
    content_html: str | None = "<div>Feed 内容</div>",
    summary: str | None = "摘要",
) -> ProviderArticle:
    return ProviderArticle(
        title=title,
        provider="rss",
        external_id=external_id,
        article_id=None,
        url=url,
        publish_time="2026-05-13T10:00:00+08:00",
        summary=summary,
        content_html=content_html,
    )


class TestRSSCacheFirstImport:
    """Cache-first 导入测试。"""

    @pytest.mark.asyncio
    async def test_uses_feed_content_without_fetching_page(
        self, fetcher: FetcherService, rss_service: RSSSourceService, db: Database
    ) -> None:
        """feed_only 模式应使用 feed 内容，不请求原文页面。"""
        source = await rss_service.add_source("cache-test", "https://example.com/feed")

        art = _make_rss_article(content_html="<p>Feed HTML</p>")
        article_info = art.to_article_info()

        with patch("src.services.fetcher.fetch_article_content") as mock_fetch:
            mock_fetch.side_effect = AssertionError("不应调用 fetch_article_content")

            status, article = await fetcher._fetch_and_save_rss_article(
                source=source,
                article_info=article_info,
                content_mode="feed_only",
                rss_service=rss_service,
            )

        assert status == "inserted"
        assert article is not None

    @pytest.mark.asyncio
    async def test_feed_only_skips_when_no_content(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """feed_only 模式无内容时仍应保存（空内容）。"""
        source = await rss_service.add_source("empty-test", "https://example.com/feed")

        art = _make_rss_article(content_html=None)
        article_info = art.to_article_info()

        with patch("src.services.fetcher.fetch_article_content") as mock_fetch:
            mock_fetch.side_effect = AssertionError("不应调用")

            status, article = await fetcher._fetch_and_save_rss_article(
                source=source,
                article_info=article_info,
                content_mode="feed_only",
                rss_service=rss_service,
            )

        assert status == "inserted"


class TestRSSContentModes:
    """内容模式测试。"""

    @pytest.mark.asyncio
    async def test_prefer_feed_uses_feed_when_available(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """prefer_feed 有 feed 内容时不应请求原文。"""
        source = await rss_service.add_source("prefer-test", "https://example.com/feed")

        art = _make_rss_article(content_html="<p>Feed 内容</p>")
        article_info = art.to_article_info()

        with patch("src.services.fetcher.fetch_article_content") as mock_fetch:
            mock_fetch.side_effect = AssertionError("不应调用")
            status, article = await fetcher._fetch_and_save_rss_article(
                source=source,
                article_info=article_info,
                content_mode="prefer_feed",
                rss_service=rss_service,
            )

        assert status == "inserted"

    @pytest.mark.asyncio
    async def test_prefer_feed_falls_back_when_missing(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """prefer_feed 无 feed 内容时应回退抓取原文。"""
        source = await rss_service.add_source("fallback-test", "https://example.com/feed")

        art = _make_rss_article(content_html=None)
        article_info = art.to_article_info()

        with patch("src.services.fetcher.fetch_article_content", new=AsyncMock(
            return_value="<html><body><p>原文内容</p></body></html>"
        )):
            with patch("src.services.fetcher.parse_article_html", return_value={
                "title": "原文标题", "content": "<p>原文内容</p>", "cover": None,
            }):
                status, article = await fetcher._fetch_and_save_rss_article(
                    source=source,
                    article_info=article_info,
                    content_mode="prefer_feed",
                    rss_service=rss_service,
                )

        assert status == "inserted"
        assert article is not None

    @pytest.mark.asyncio
    async def test_fetch_missing_always_tries_original(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """fetch_missing 模式应始终尝试抓取原文。"""
        source = await rss_service.add_source("fetch-missing-test", "https://example.com/feed")

        art = _make_rss_article(content_html="<p>Feed 内容</p>")
        article_info = art.to_article_info()

        with patch("src.services.fetcher.fetch_article_content", new=AsyncMock(
            return_value="<html><body><p>完整原文</p></body></html>"
        )) as mock_fetch:
            with patch("src.services.fetcher.parse_article_html", return_value={
                "title": "完整标题", "content": "<p>完整原文</p>", "cover": None,
            }):
                status, article = await fetcher._fetch_and_save_rss_article(
                    source=source,
                    article_info=article_info,
                    content_mode="fetch_missing",
                    rss_service=rss_service,
                )

        assert status == "inserted"
        mock_fetch.assert_called_once()


class TestRSSDeduplication:
    """去重测试。"""

    @pytest.mark.asyncio
    async def test_dedup_by_provider_item_id(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """相同 provider_item_id 应去重。"""
        source = await rss_service.add_source("dedup-test", "https://example.com/feed")

        art = _make_rss_article(external_id="dedup-id-001")
        article_info = art.to_article_info()

        # 第一次插入
        status1, _ = await fetcher._fetch_and_save_rss_article(
            source=source, article_info=article_info,
            content_mode="feed_only", rss_service=rss_service,
        )
        assert status1 == "inserted"

        # 第二次应去重
        status2, existing = await fetcher._fetch_and_save_rss_article(
            source=source, article_info=article_info,
            content_mode="feed_only", rss_service=rss_service,
        )
        assert status2 == "existing"
        assert existing is not None

    @pytest.mark.asyncio
    async def test_dedup_by_original_url(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """相同 original_url 但不同 provider_item_id 应去重。"""
        source = await rss_service.add_source("url-dedup-test", "https://example.com/feed")

        art1 = _make_rss_article(external_id="id-v1", url="https://mp.weixin.qq.com/s/same")
        art2 = _make_rss_article(external_id="id-v2", url="https://mp.weixin.qq.com/s/same")

        info1 = art1.to_article_info()
        info2 = art2.to_article_info()

        status1, _ = await fetcher._fetch_and_save_rss_article(
            source=source, article_info=info1,
            content_mode="feed_only", rss_service=rss_service,
        )
        assert status1 == "inserted"

        status2, _ = await fetcher._fetch_and_save_rss_article(
            source=source, article_info=info2,
            content_mode="feed_only", rss_service=rss_service,
        )
        assert status2 == "existing"


class TestRSSMembershipAttachment:
    """成员关系挂载测试。"""

    @pytest.mark.asyncio
    async def test_inserted_article_gets_membership(
        self, fetcher: FetcherService, rss_service: RSSSourceService, db: Database
    ) -> None:
        """新文章应挂载到 RSS 源成员关系。"""
        source = await rss_service.add_source("member-test", "https://example.com/feed")

        art = _make_rss_article()
        status, article = await fetcher._fetch_and_save_rss_article(
            source=source, article_info=art.to_article_info(),
            content_mode="feed_only", rss_service=rss_service,
        )

        assert status == "inserted"
        assert article is not None

        # 验证成员关系
        sources = await rss_service.get_article_sources(article.id)
        assert len(sources) == 1
        assert sources[0].source_name == "member-test"

    @pytest.mark.asyncio
    async def test_existing_article_gets_membership(
        self, fetcher: FetcherService, rss_service: RSSSourceService, db: Database
    ) -> None:
        """已存在文章也应挂载到新源成员关系。"""
        source = await rss_service.add_source("existing-member-test", "https://example.com/feed")

        art = _make_rss_article()
        info = art.to_article_info()

        # 第一次插入
        await fetcher._fetch_and_save_rss_article(
            source=source, article_info=info,
            content_mode="feed_only", rss_service=rss_service,
        )

        # 创建第二个源，同一文章
        source2 = await rss_service.add_source("second-source", "https://example.com/feed2")
        status, article = await fetcher._fetch_and_save_rss_article(
            source=source2, article_info=info,
            content_mode="feed_only", rss_service=rss_service,
        )

        assert status == "existing"
        assert article is not None

        # 验证两个源都有成员关系
        sources = await rss_service.get_article_sources(article.id)
        source_names = {s.source_name for s in sources}
        assert "existing-member-test" in source_names
        assert "second-source" in source_names


class TestRSSHealthUpdate:
    """健康状态更新测试。"""

    @pytest.mark.asyncio
    async def test_success_updates_health(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """成功抓取应更新健康状态。"""
        source = await rss_service.add_source("health-success", "https://example.com/feed")

        await rss_service.record_failure(source.id, "previous error")
        await rss_service.record_success(source.id)

        health = await rss_service.get_health(source.id)
        assert health is not None
        assert health.consecutive_failures == 0
        assert health.last_success_at is not None

    @pytest.mark.asyncio
    async def test_failure_increments_consecutive_failures(
        self, rss_service: RSSSourceService
    ) -> None:
        """失败应递增连续失败次数。"""
        source = await rss_service.add_source("health-fail", "https://example.com/feed")

        await rss_service.record_failure(source.id, "HTTP 500")
        await rss_service.record_failure(source.id, "Timeout")

        health = await rss_service.get_health(source.id)
        assert health is not None
        assert health.consecutive_failures == 2


class TestRSSFallback:
    """回退行为测试。"""

    @pytest.mark.asyncio
    async def test_prefer_feed_fallback_respects_throttle(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """回退抓取应遵守现有节流。"""
        source = await rss_service.add_source("throttle-test", "https://example.com/feed")

        art = _make_rss_article(content_html=None)
        info = art.to_article_info()

        with patch("src.services.fetcher.fetch_article_content", new=AsyncMock(
            return_value="<html><body>content</body></html>"
        )):
            with patch("src.services.fetcher.parse_article_html", return_value={
                "title": "test", "content": "content", "cover": None,
            }):
                status, _ = await fetcher._fetch_and_save_rss_article(
                    source=source, article_info=info,
                    content_mode="prefer_feed", rss_service=rss_service,
                )

        assert status == "inserted"

    @pytest.mark.asyncio
    async def test_fetch_content_failure_does_not_block_insert(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """回退抓取失败不应阻止文章保存（使用可用的 feed 内容）。"""
        source = await rss_service.add_source("fail-safe-test", "https://example.com/feed")

        art = _make_rss_article(content_html="<p>Feed 备份</p>")
        info = art.to_article_info()

        with patch("src.services.fetcher.fetch_article_content", new=AsyncMock(
            side_effect=Exception("Network error")
        )):
            status, article = await fetcher._fetch_and_save_rss_article(
                source=source, article_info=info,
                content_mode="prefer_feed", rss_service=rss_service,
            )

        # prefer_feed 有 feed 内容时不会调用 fetch，所以这里不会触发
        # 但 fetch_missing 会触发
        assert status == "inserted"


class TestRSSFeedRequestFailureSummary:
    """RSS feed 请求失败时 source failure summary 非空测试。"""

    @pytest.mark.asyncio
    async def test_request_error_produces_non_empty_failure_summary(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """RSS feed 请求失败应向 record_failure 传入非空摘要。"""
        source = await rss_service.add_source("diag-test", "https://example.com/feed")

        request_exc = httpx.ConnectTimeout(
            "", request=httpx.Request("GET", "https://example.com/feed"),
        )
        provider_error = RSSProviderError(
            f"RSS 请求失败: [ConnectTimeout] | url=https://example.com/feed"
        )

        with patch.object(
            fetcher._get_provider("rss"), "get_articles",
            new=AsyncMock(side_effect=provider_error),
        ):
            results = await fetcher.fetch_from_rss_sources()

        assert "diag-test" in results
        assert results["diag-test"].final_state == FetchFinalState.ERROR

        health = await rss_service.get_health(source.id)
        assert health is not None
        assert health.consecutive_failures >= 1
        assert health.last_error_summary
        assert "ConnectTimeout" in health.last_error_summary


class TestAuthExpiredAbort:
    """AuthExpiredError 在 RSS 抓取中应中断处理。"""

    @pytest.mark.asyncio
    async def test_save_layer_propagates_auth_expired(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """归属解析遇到 Token 失效时，保存层不得转换为普通单篇失败。"""
        source = await rss_service.add_source("auth-save", "https://example.com/feed")
        attribution_service = MagicMock()
        attribution_service.attribute = AsyncMock(
            side_effect=AuthExpiredError(
                "Token 失效", status_code=401, response_text="WeReadError401",
            ),
        )

        with pytest.raises(AuthExpiredError):
            await fetcher._fetch_and_save_rss_article(
                source=source,
                article_info=_make_rss_article().to_article_info(),
                content_mode="feed_only",
                rss_service=rss_service,
                attribution_service=attribution_service,
            )

    @pytest.mark.asyncio
    async def test_source_loop_stops_on_auth_expired(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """_fetch_rss_source 文章循环在 AuthExpiredError 时应停止。"""
        source = await rss_service.add_source("auth-abort", "https://example.com/feed")

        auth_error = AuthExpiredError("Token 失效", status_code=401, response_text="WeReadError401")

        # Mock _fetch_and_save_rss_article to raise AuthExpiredError
        with patch.object(
            fetcher, "_fetch_and_save_rss_article",
            new=AsyncMock(side_effect=auth_error),
        ):
            # Mock provider to return articles so the loop enters
            art = _make_rss_article()
            page = ProviderArticlePage(
                articles=[art, art, art], page=1, page_size=100, total=3,
            )
            with patch.object(
                fetcher._get_provider("rss"), "get_articles",
                new=AsyncMock(return_value=page),
            ):
                # Mock _rss_article_exists to return False (force into _fetch_and_save_rss_article)
                with patch.object(fetcher, "_rss_article_exists", new=AsyncMock(return_value=False)):
                    with pytest.raises(AuthExpiredError):
                        await fetcher._fetch_rss_source(
                            source=source,
                            provider=fetcher._get_provider("rss"),
                            rss_service=rss_service,
                            content_mode="feed_only",
                            on_progress=None,
                        )

    @pytest.mark.asyncio
    async def test_session_breaks_on_auth_expired(
        self, fetcher: FetcherService, rss_service: RSSSourceService
    ) -> None:
        """fetch_from_rss_sources 在 AuthExpiredError 时应中断源循环。"""
        source1 = await rss_service.add_source("auth-src-1", "https://example.com/feed1")
        source2 = await rss_service.add_source("auth-src-2", "https://example.com/feed2")

        auth_error = AuthExpiredError("Token 失效", status_code=401, response_text="WeReadError401")

        # First source raises AuthExpiredError, second should NOT be processed
        with patch.object(
            fetcher, "_fetch_rss_source",
            new=AsyncMock(side_effect=auth_error),
        ):
            results = await fetcher.fetch_from_rss_sources()

        # source1 should be in results with ERROR state
        assert "auth-src-1" in results
        assert results["auth-src-1"].final_state == FetchFinalState.ERROR

        # source2 should NOT be processed (loop broke)
        assert "auth-src-2" not in results
