"""FetcherService 最小数据库级集成测试。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from src.models.schema import Article
from src.services.fetcher import FetcherService
from src.services.subscription import SubscriptionService
from src.storage.database import Database


@pytest.mark.asyncio
async def test_fetch_feed_persists_article(integration_db: Database) -> None:
    """测试抓取会将文章落库。"""
    subscription_service = SubscriptionService(integration_db)
    await subscription_service.add_subscription("MP_WXS_test", "测试公众号")

    weread_client = MagicMock()
    weread_client.get_articles = AsyncMock(
        return_value={
            "articles": [
                {
                    "id": "article_1",
                    "title": "原始标题",
                    "publish_time": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "page_size": 1,
        }
    )

    fetcher = FetcherService(weread_client, integration_db, subscription_service)
    fetcher.backfill_publish_time = AsyncMock(return_value=0)

    with patch("src.services.fetcher.fetch_article_content", new=AsyncMock(return_value="<html></html>")):
        with patch(
            "src.services.fetcher.parse_article_html",
            return_value={
                "title": "解析标题",
                "content": "<p>正文</p>",
                "cover": "https://example.com/cover.jpg",
                "publish_time": None,
            },
        ):
            articles = await fetcher.fetch_feed("MP_WXS_test", days=None, max_pages=1, page_size=1)

    assert len(articles) == 1

    async with integration_db.get_session() as session:
        result = await session.execute(select(Article).where(Article.article_id == "article_1"))
        article = result.scalar_one_or_none()

    assert article is not None
    assert article.title == "解析标题"


@pytest.mark.asyncio
async def test_backfill_publish_time_updates_missing_article(integration_db: Database) -> None:
    """测试发布时间回填会更新数据库中的空字段。"""
    subscription_service = SubscriptionService(integration_db)
    feed = await subscription_service.add_subscription("MP_WXS_test", "测试公众号")

    async with integration_db.get_session() as session:
        article = Article(
            feed_id=feed.id,
            article_id="article_1",
            title="待回填文章",
            content="<p>正文</p>",
            publish_time=None,
        )
        session.add(article)
        await session.flush()

    weread_client = MagicMock()
    weread_client.get_articles = AsyncMock(
        return_value={
            "articles": [
                {"id": "article_1", "title": "待回填文章", "publish_time": "2026-01-03T09:00:00+00:00"}
            ],
            "page_size": 1,
        }
    )

    fetcher = FetcherService(weread_client, integration_db, subscription_service)
    updated = await fetcher.backfill_publish_time("MP_WXS_test")

    assert updated == 1

    async with integration_db.get_session() as session:
        result = await session.execute(select(Article).where(Article.article_id == "article_1"))
        refreshed = result.scalar_one()

    assert refreshed.publish_time is not None
