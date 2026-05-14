"""RSS 源和订阅服务测试 - 覆盖源创建、元数据持久化、公众号推断、成员关系、配额计数。"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from src.models.schema import RSSArticleMembership, RSSSource, RSSSourceHealth
from src.services.rss_source import RSSSourceService
from src.storage.database import Database


@pytest_asyncio.fixture
async def db() -> Database:
    """创建内存数据库。"""
    database = Database(database_url="sqlite+aiosqlite:///:memory:")
    await database.init_db()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def rss_service(db: Database) -> RSSSourceService:
    """创建 RSS 源服务。"""
    return RSSSourceService(db)


class TestRSSSourceCRUD:
    """RSS 源增删改查测试。"""

    @pytest.mark.asyncio
    async def test_add_source(self, rss_service: RSSSourceService) -> None:
        source = await rss_service.add_source(
            source_name="全部",
            feed_url="https://rss.example.com/all?key=abc",
            source_type="aggregate",
        )
        assert source.source_name == "全部"
        assert source.source_type == "aggregate"
        assert source.feed_url == "https://rss.example.com/all?key=abc"
        assert source.provider == "rss"
        assert source.status == 1

    @pytest.mark.asyncio
    async def test_add_category_source(self, rss_service: RSSSourceService) -> None:
        source = await rss_service.add_source(
            source_name="财经",
            feed_url="https://rss.example.com/finance",
            source_type="category",
        )
        assert source.source_type == "category"
        assert source.source_name == "财经"

    @pytest.mark.asyncio
    async def test_add_source_upsert(self, rss_service: RSSSourceService) -> None:
        """重复添加同名源应更新而非报错。"""
        await rss_service.add_source("全部", "https://old.example.com/feed")
        updated = await rss_service.add_source("全部", "https://new.example.com/feed")
        assert updated.feed_url == "https://new.example.com/feed"

        sources = await rss_service.list_sources()
        assert len(sources) == 1

    @pytest.mark.asyncio
    async def test_remove_source(self, rss_service: RSSSourceService) -> None:
        await rss_service.add_source("删除测试", "https://example.com/feed")
        success = await rss_service.remove_source("删除测试")
        assert success is True

        result = await rss_service.get_source("删除测试")
        assert result is None

    @pytest.mark.asyncio
    async def test_remove_nonexistent(self, rss_service: RSSSourceService) -> None:
        success = await rss_service.remove_source("不存在")
        assert success is False

    @pytest.mark.asyncio
    async def test_disable_and_enable_source(self, rss_service: RSSSourceService) -> None:
        await rss_service.add_source("开关测试", "https://example.com/feed")

        success = await rss_service.disable_source("开关测试")
        assert success is True

        source = await rss_service.get_source("开关测试")
        assert source.status == 0

        # 活跃列表不应包含停用源
        active = await rss_service.list_sources(active_only=True)
        assert len(active) == 0

        success = await rss_service.enable_source("开关测试")
        assert success is True

        active = await rss_service.list_sources(active_only=True)
        assert len(active) == 1

    @pytest.mark.asyncio
    async def test_update_source(self, rss_service: RSSSourceService) -> None:
        await rss_service.add_source("更新测试", "https://old.example.com/feed")
        updated = await rss_service.update_source(
            "更新测试",
            feed_url="https://new.example.com/feed",
            provider_metadata={"version": 2},
        )
        assert updated is not None
        assert updated.feed_url == "https://new.example.com/feed"

    @pytest.mark.asyncio
    async def test_list_sources_ordered_by_name(self, rss_service: RSSSourceService) -> None:
        await rss_service.add_source("财经", "https://example.com/fin")
        await rss_service.add_source("全部", "https://example.com/all")
        await rss_service.add_source("科技", "https://example.com/tech")

        sources = await rss_service.list_sources()
        names = [s.source_name for s in sources]
        assert names == sorted(names)


class TestRSSSourceMetadata:
    """SaaS 元数据持久化测试。"""

    @pytest.mark.asyncio
    async def test_store_provider_metadata(self, rss_service: RSSSourceService) -> None:
        metadata = {"vendor": "wechat-rss-saas", "plan": "pro", "source_id": "src_123"}
        source = await rss_service.add_source(
            "元数据测试",
            "https://rss.example.com/feed",
            provider_metadata=metadata,
        )
        assert source.provider_metadata is not None
        import json
        stored = json.loads(source.provider_metadata)
        assert stored["vendor"] == "wechat-rss-saas"
        assert stored["plan"] == "pro"

    @pytest.mark.asyncio
    async def test_api_key_not_stored_in_source(self, rss_service: RSSSourceService) -> None:
        """API Key 不应存储在源记录中。"""
        source = await rss_service.add_source(
            "API Key 测试",
            "https://rss.example.com/feed",
            provider_metadata={"note": "key is in settings"},
        )
        import json
        stored = json.loads(source.provider_metadata)
        assert "api_key" not in stored
        assert "key" not in stored


class TestRSSSourceQuota:
    """配额计数测试。"""

    @pytest.mark.asyncio
    async def test_count_active_sources(self, rss_service: RSSSourceService) -> None:
        await rss_service.add_source("源1", "https://example.com/1")
        await rss_service.add_source("源2", "https://example.com/2")
        await rss_service.add_source("源3", "https://example.com/3")
        await rss_service.disable_source("源3")

        count = await rss_service.count_active_sources()
        assert count == 2

    @pytest.mark.asyncio
    async def test_quota_warning_within_limit(self, rss_service: RSSSourceService) -> None:
        await rss_service.add_source("源1", "https://example.com/1")
        with patch("src.services.rss_source.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(wechat_rss_plan_limit=5)
            is_warning, active_count, plan_limit = await rss_service.check_quota_warning()

        assert is_warning is False
        assert active_count == 1
        assert plan_limit == 5

    @pytest.mark.asyncio
    async def test_quota_warning_exceeded(self, rss_service: RSSSourceService) -> None:
        await rss_service.add_source("源1", "https://example.com/1")
        await rss_service.add_source("源2", "https://example.com/2")
        await rss_service.add_source("源3", "https://example.com/3")

        with patch("src.services.rss_source.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(wechat_rss_plan_limit=2)
            is_warning, active_count, plan_limit = await rss_service.check_quota_warning()

        assert is_warning is True
        assert active_count == 3
        assert plan_limit == 2


class TestRSSSourceHealth:
    """健康状态测试。"""

    @pytest.mark.asyncio
    async def test_record_success(self, rss_service: RSSSourceService) -> None:
        source = await rss_service.add_source("健康测试", "https://example.com/feed")

        await rss_service.record_failure(source.id, "test error")
        await rss_service.record_success(source.id)

        health = await rss_service.get_health(source.id)
        assert health is not None
        assert health.last_success_at is not None
        assert health.consecutive_failures == 0
        assert health.last_error_summary is None

    @pytest.mark.asyncio
    async def test_record_failure(self, rss_service: RSSSourceService) -> None:
        source = await rss_service.add_source("失败测试", "https://example.com/feed")

        await rss_service.record_failure(source.id, "Connection timeout")
        await rss_service.record_failure(source.id, "HTTP 503")

        health = await rss_service.get_health(source.id)
        assert health is not None
        assert health.consecutive_failures == 2
        assert "503" in health.last_error_summary

    @pytest.mark.asyncio
    async def test_record_empty_response(self, rss_service: RSSSourceService) -> None:
        source = await rss_service.add_source("空响应测试", "https://example.com/feed")

        await rss_service.record_empty(source.id)

        health = await rss_service.get_health(source.id)
        assert health is not None
        assert health.empty_response_count == 1
        assert health.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_stale_detection(self, rss_service: RSSSourceService) -> None:
        source = await rss_service.add_source("过期测试", "https://example.com/feed")

        old_time = datetime.now() - timedelta(hours=72)
        await rss_service.record_success(source.id, latest_item_time=old_time)

        with patch("src.services.rss_source.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(rss_stale_threshold_hours=48)
            is_stale = await rss_service.is_stale(source.id)

        assert is_stale is True

    @pytest.mark.asyncio
    async def test_not_stale_with_recent_item(self, rss_service: RSSSourceService) -> None:
        source = await rss_service.add_source("新鲜测试", "https://example.com/feed")
        await rss_service.record_success(source.id, latest_item_time=datetime.now())

        with patch("src.services.rss_source.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(rss_stale_threshold_hours=48)
            is_stale = await rss_service.is_stale(source.id)

        assert is_stale is False


class TestRSSArticleMembership:
    """文章成员关系测试。"""

    @pytest.mark.asyncio
    async def test_add_membership(self, rss_service: RSSSourceService, db: Database) -> None:
        from src.models.schema import Article, Feed

        async with db.get_session() as session:
            feed = Feed(mp_id="test_mp", name="测试公众号", provider="rss")
            session.add(feed)
            await session.flush()
            await session.refresh(feed)

            article = Article(
                feed_id=feed.id, article_id="art_001",
                title="测试文章", provider="rss",
            )
            session.add(article)
            await session.flush()
            await session.refresh(article)
            feed_id = feed.id
            article_id = article.id

        source = await rss_service.add_source("成员测试", "https://example.com/feed")

        membership = await rss_service.add_article_membership(article_id, source.id)
        assert membership.article_id == article_id
        assert membership.source_id == source.id

    @pytest.mark.asyncio
    async def test_membership_idempotent(self, rss_service: RSSSourceService, db: Database) -> None:
        """重复添加同一关系不应报错。"""
        from src.models.schema import Article, Feed

        async with db.get_session() as session:
            feed = Feed(mp_id="test_mp2", name="测试公众号2", provider="rss")
            session.add(feed)
            await session.flush()
            await session.refresh(feed)

            article = Article(
                feed_id=feed.id, article_id="art_002",
                title="测试文章2", provider="rss",
            )
            session.add(article)
            await session.flush()
            await session.refresh(article)
            article_id = article.id

        source = await rss_service.add_source("幂等测试", "https://example.com/feed")

        m1 = await rss_service.add_article_membership(article_id, source.id)
        m2 = await rss_service.add_article_membership(article_id, source.id)
        assert m1.id == m2.id

    @pytest.mark.asyncio
    async def test_multi_category_membership(self, rss_service: RSSSourceService, db: Database) -> None:
        """一篇文章属于多个 RSS 分类源。"""
        from src.models.schema import Article, Feed

        async with db.get_session() as session:
            feed = Feed(mp_id="test_mp3", name="测试公众号3", provider="rss")
            session.add(feed)
            await session.flush()
            await session.refresh(feed)

            article = Article(
                feed_id=feed.id, article_id="art_003",
                title="多分类文章", provider="rss",
            )
            session.add(article)
            await session.flush()
            await session.refresh(article)
            article_id = article.id

        src1 = await rss_service.add_source("财经", "https://example.com/fin", source_type="category")
        src2 = await rss_service.add_source("科技", "https://example.com/tech", source_type="category")

        await rss_service.add_article_membership(article_id, src1.id)
        await rss_service.add_article_membership(article_id, src2.id)

        sources = await rss_service.get_article_sources(article_id)
        assert len(sources) == 2
        source_names = {s.source_name for s in sources}
        assert source_names == {"财经", "科技"}

    @pytest.mark.asyncio
    async def test_source_article_count(self, rss_service: RSSSourceService, db: Database) -> None:
        from src.models.schema import Article, Feed

        async with db.get_session() as session:
            feed = Feed(mp_id="test_mp4", name="测试公众号4", provider="rss")
            session.add(feed)
            await session.flush()
            await session.refresh(feed)

            for i in range(3):
                article = Article(
                    feed_id=feed.id, article_id=f"art_count_{i}",
                    title=f"文章{i}", provider="rss",
                )
                session.add(article)
            await session.flush()

        source = await rss_service.add_source("计数测试", "https://example.com/feed")

        async with db.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Article.id).where(Article.feed_id == feed.id)
            )
            article_ids = list(result.scalars().all())

        for aid in article_ids:
            await rss_service.add_article_membership(aid, source.id)

        count = await rss_service.get_source_article_count(source.id)
        assert count == 3
