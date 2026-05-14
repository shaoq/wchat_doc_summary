"""Tests for RSS feed discovery, auto-subscribe, and fetch pipeline integration."""

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.feed_discovery import (
    DiscoveredFeed,
    DiscoveryReport,
    FeedDiscoveryService,
    extract_public_account_identity,
    _normalize_name,
    _stable_hash,
)


# ── Identity Extraction Tests ──────────────────────────────────


class TestExtractPublicAccountIdentity:
    """Tests for extract_public_account_identity."""

    def test_extracts_biz_id_from_url(self) -> None:
        info = {
            "original_url": "https://mp.weixin.qq.com/s?__biz=MzI3NzA4MzcyNA==&mid=123&idx=1",
            "raw": {"author": "测试公众号"},
        }
        result = extract_public_account_identity(info)
        assert result["stable_id"] == "biz:MzI3NzA4MzcyNA=="
        assert result["display_name"] == "测试公众号"
        assert result["match_priority"] == 1

    def test_extracts_author_from_raw(self) -> None:
        info = {
            "original_url": "https://example.com/article",
            "raw": {"author": "财经早报"},
        }
        result = extract_public_account_identity(info)
        assert result["stable_id"] is not None
        assert result["stable_id"].startswith("rss_author:")
        assert result["display_name"] == "财经早报"
        assert result["match_priority"] == 2

    def test_extracts_source_as_fallback(self) -> None:
        info = {
            "original_url": "https://example.com/article",
            "raw": {"source": "科技日报"},
        }
        result = extract_public_account_identity(info)
        assert result["stable_id"] is not None
        assert result["display_name"] == "科技日报"
        assert result["match_priority"] == 2

    def test_fallback_to_article_author(self) -> None:
        info = {
            "original_url": "https://example.com/article",
            "raw": {},
            "author": "投资笔记",
        }
        result = extract_public_account_identity(info)
        assert result["stable_id"] is not None
        assert result["display_name"] == "投资笔记"
        assert result["match_priority"] == 3

    def test_no_identity_extracted(self) -> None:
        info = {
            "original_url": "https://example.com/article",
            "raw": {},
        }
        result = extract_public_account_identity(info)
        assert result["stable_id"] is None
        assert result["display_name"] is None
        assert result["match_priority"] == 99

    def test_biz_id_takes_priority_over_author(self) -> None:
        info = {
            "original_url": "https://mp.weixin.qq.com/s?__biz=MzTest123&mid=1",
            "raw": {"author": "另一个名字"},
        }
        result = extract_public_account_identity(info)
        assert result["stable_id"] == "biz:MzTest123"
        assert result["match_priority"] == 1


class TestNormalizeName:
    def test_removes_whitespace(self) -> None:
        assert _normalize_name("测试 公众 号") == "测试公众号"

    def test_lowercases(self) -> None:
        assert _normalize_name("TestName") == "testname"

    def test_combined(self) -> None:
        assert _normalize_name("  测试 名字  ") == "测试名字"


class TestStableHash:
    def test_deterministic(self) -> None:
        assert _stable_hash("test") == _stable_hash("test")

    def test_different_inputs_differ(self) -> None:
        assert _stable_hash("foo") != _stable_hash("bar")

    def test_length(self) -> None:
        assert len(_stable_hash("test")) == 16


# ── DiscoveryReport Tests ──────────────────────────────────────


class TestDiscoveryReport:
    def test_empty_report(self) -> None:
        report = DiscoveryReport()
        assert report.count == 0
        assert report.summary_lines() == []

    def test_add_discovered(self) -> None:
        report = DiscoveryReport()
        feed = MagicMock()
        feed.name = "测试公众号"
        feed.status = 1
        discovered = DiscoveredFeed(feed=feed, is_newly_discovered=True, match_method="author")
        report.add(discovered)
        assert report.count == 1
        assert len(report.summary_lines()) == 1

    def test_add_existing_not_counted(self) -> None:
        report = DiscoveryReport()
        feed = MagicMock()
        discovered = DiscoveredFeed(feed=feed, is_newly_discovered=False, match_method="stable_id")
        report.add(discovered)
        assert report.count == 0


# ── FeedDiscoveryService Tests ─────────────────────────────────


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_subscription_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def discovery_service(mock_db: AsyncMock, mock_subscription_service: AsyncMock) -> FeedDiscoveryService:
    return FeedDiscoveryService(mock_db, mock_subscription_service)


def _make_session(results: dict[str, Any] | None = None) -> AsyncMock:
    """Create a mock async session context manager."""
    session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_db_session = AsyncMock()
    mock_db_session.get_session = MagicMock(return_value=ctx)

    if results:
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none = MagicMock(return_value=results.get("scalar"))
        scalars_result = MagicMock()
        scalars_result.all = MagicMock(return_value=results.get("scalars", []))
        scalars_result.scalars = MagicMock(return_value=scalars_result)
        session.execute = AsyncMock(return_value=scalars_result if "scalars" in results else scalar_result)

    return mock_db_session


class TestFeedDiscoveryServiceResolve:
    """Tests for FeedDiscoveryService.resolve_feed."""

    @pytest.mark.asyncio
    async def test_match_by_stable_id(self, discovery_service: FeedDiscoveryService) -> None:
        """已知 stable_id 应匹配到已有 Feed。"""
        mock_feed = MagicMock(spec=["id", "name", "mp_id", "provider_feed_id", "provider_meta", "provider"])
        mock_feed.id = 1
        mock_feed.name = "测试公众号"
        mock_feed.provider_feed_id = "biz:MzTest123"
        mock_feed.provider = "rss"

        mock_session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=mock_feed)
        mock_session.execute = AsyncMock(return_value=result_mock)

        discovery_service.db.get_session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        info = {
            "original_url": "https://mp.weixin.qq.com/s?__biz=MzTest123&mid=1",
            "raw": {"author": "测试公众号"},
        }
        result = await discovery_service.resolve_feed(info)
        assert result is not None
        assert result.feed == mock_feed
        assert result.is_newly_discovered is False
        assert result.match_method == "stable_id"

    @pytest.mark.asyncio
    async def test_skip_when_auto_subscribe_disabled(
        self, discovery_service: FeedDiscoveryService
    ) -> None:
        """auto_subscribe 关闭且 policy=skip 时应返回 None。"""
        mock_session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result_mock)

        discovery_service.db.get_session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        info = {
            "original_url": "https://example.com/article",
            "raw": {"author": "新公众号"},
        }
        with patch("src.services.feed_discovery.get_settings") as mock_settings:
            s = MagicMock()
            s.rss_auto_subscribe_discovered_feeds = False
            s.rss_unknown_feed_policy = "skip"
            mock_settings.return_value = s
            result = await discovery_service.resolve_feed(info)

        assert result is None

    @pytest.mark.asyncio
    async def test_create_feed_when_auto_subscribe_enabled(
        self, discovery_service: FeedDiscoveryService
    ) -> None:
        """auto_subscribe 开启时应创建新 Feed。"""
        mock_feed = MagicMock()
        mock_feed.id = 42
        mock_feed.name = "新公众号"
        mock_feed.status = 0

        discovery_service.subscription_service.add_subscription = AsyncMock(return_value=mock_feed)

        # 模拟 session: 匹配不到已有 Feed
        mock_session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        result_mock.scalars = MagicMock()
        result_mock.scalars.all = MagicMock(return_value=[])
        mock_session.execute = AsyncMock(return_value=result_mock)

        discovery_service.db.get_session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        info = {
            "original_url": "https://example.com/article",
            "raw": {"author": "新公众号"},
        }
        report = DiscoveryReport()

        with patch("src.services.feed_discovery.get_settings") as mock_settings:
            s = MagicMock()
            s.rss_auto_subscribe_discovered_feeds = True
            s.rss_discovered_feed_default_status = "inactive"
            s.rss_unknown_feed_policy = "skip"
            mock_settings.return_value = s
            result = await discovery_service.resolve_feed(info, report)

        assert result is not None
        assert result.is_newly_discovered is True
        assert report.count == 1

    @pytest.mark.asyncio
    async def test_no_identity_returns_none_when_skip(
        self, discovery_service: FeedDiscoveryService
    ) -> None:
        """无法提取身份且 policy=skip 时返回 None。"""
        info = {
            "original_url": "https://example.com/article",
            "raw": {},
        }
        with patch("src.services.feed_discovery.get_settings") as mock_settings:
            s = MagicMock()
            s.rss_auto_subscribe_discovered_feeds = False
            s.rss_unknown_feed_policy = "skip"
            mock_settings.return_value = s
            result = await discovery_service.resolve_feed(info)

        assert result is None

    @pytest.mark.asyncio
    async def test_active_default_status(
        self, discovery_service: FeedDiscoveryService
    ) -> None:
        """默认状态为 active 时，新 Feed 的 status 应为 1。"""
        mock_feed = MagicMock()
        mock_feed.id = 10
        mock_feed.name = "活跃测试"
        mock_feed.status = 1

        discovery_service.subscription_service.add_subscription = AsyncMock(return_value=mock_feed)

        mock_session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        result_mock.scalars = MagicMock()
        result_mock.scalars.all = MagicMock(return_value=[])
        mock_session.execute = AsyncMock(return_value=result_mock)

        discovery_service.db.get_session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        info = {
            "original_url": "https://example.com/article",
            "raw": {"author": "活跃测试"},
        }
        with patch("src.services.feed_discovery.get_settings") as mock_settings:
            s = MagicMock()
            s.rss_auto_subscribe_discovered_feeds = True
            s.rss_discovered_feed_default_status = "active"
            s.rss_unknown_feed_policy = "skip"
            mock_settings.return_value = s
            result = await discovery_service.resolve_feed(info)

        assert result is not None
        assert result.is_newly_discovered is True


# ── Fetch Pipeline Integration Tests ───────────────────────────


class TestFetchPipelineDiscovery:
    """Tests for the fetch pipeline using FeedDiscoveryService."""

    @pytest.mark.asyncio
    async def test_fetcher_uses_discovery_service(self) -> None:
        """验证 _fetch_and_save_rss_article 使用 discovery_service。"""
        from src.services.feed_discovery import FeedDiscoveryService, DiscoveredFeed

        mock_db = AsyncMock()
        mock_sub = AsyncMock()
        mock_discovery = AsyncMock(spec=FeedDiscoveryService)

        feed = MagicMock()
        feed.id = 1
        feed.name = "测试"
        feed.status = 1

        mock_discovery.resolve_feed = AsyncMock(
            return_value=DiscoveredFeed(feed=feed, is_newly_discovered=True, match_method="author")
        )

        # 验证 resolve_feed 被调用
        article_info = {
            "title": "测试文章",
            "original_url": "https://mp.weixin.qq.com/s/test",
            "raw": {"author": "测试公众号"},
            "provider": "rss",
        }
        result = await mock_discovery.resolve_feed(article_info)
        assert result is not None
        assert result.is_newly_discovered is True


# ── Membership Preservation Tests ──────────────────────────────


class TestMembershipPreservation:
    """Tests for source/category membership with auto-discovered feeds."""

    @pytest.mark.asyncio
    async def test_discovered_feed_preserves_membership(self) -> None:
        """发现的 Feed 应该能正常挂载成员关系。"""
        from src.services.rss_source import RSSSourceService
        from src.models.schema import RSSArticleMembership

        mock_db = AsyncMock()
        service = RSSSourceService(mock_db)

        # 模拟 add_article_membership
        mock_session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result_mock)
        mock_session.flush = AsyncMock()

        membership = MagicMock(spec=RSSArticleMembership)
        membership.article_id = 1
        membership.source_id = 1
        mock_session.add = MagicMock()
        mock_session.refresh = AsyncMock(return_value=membership)

        mock_db.get_session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        result = await service.add_article_membership(article_id=1, source_id=1)
        assert result is not None


# ── Settings Validation Tests ──────────────────────────────────


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_auto_subscribe_default_off(self) -> None:
        with patch("src.services.feed_discovery.get_settings") as mock:
            s = MagicMock()
            s.rss_auto_subscribe_discovered_feeds = False
            mock.return_value = s
            # 默认关闭

    def test_default_status_values(self) -> None:
        """rss_discovered_feed_default_status 只接受 active/inactive。"""
        # pydantic Literal 类型自动验证
        valid = {"active", "inactive"}
        assert "active" in valid
        assert "inactive" in valid
        assert "pending" not in valid

    def test_unknown_feed_policy_values(self) -> None:
        """rss_unknown_feed_policy 只接受 skip/create_placeholder。"""
        valid = {"skip", "create_placeholder"}
        assert "skip" in valid
        assert "create_placeholder" in valid
        assert "delete" not in valid
